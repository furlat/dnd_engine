"""Shared runtime-to-directory character holdings settlement bridge.

The engine owns live item objects while the directory owns immutable character
revisions.  This module is the single cold terminal boundary between them.  It
contains no gateway transport and performs no database access.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeOrigin,
)
from dnd.core.base_block import BaseBlock
from dnd.core.content.character_deployment import CharacterDeploymentSnapshot
from dnd.core.content.durable_characters import (
    CharacterHoldingsRevision,
    CharacterItemV1,
)
from dnd.core.equipment_types import (
    BodyPart,
    EquipmentSlot,
    RingSlot,
    WeaponSlot,
)
from server.game_directory.canonical import canonical_digest
from server.game_directory.contracts import (
    CharacterRevisionBundleCommit,
    CharacterRevisionHeads,
    CharacterSettlementCreate,
    PinnedCharacterDeploymentRecord,
)


class WorkerCharacterHoldingsEvidence(BaseModel):
    """Exact final holdings projected by one terminal worker generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    game_id: UUID
    generation_id: UUID
    terminal_event_cursor: int = Field(ge=1)
    terminal_combat_log_cursor: int = Field(ge=0)
    runtime_entity_uuid: UUID
    character_id: UUID
    expected_row_version: int = Field(ge=1)
    expected_heads: CharacterRevisionHeads
    resulting_holdings: CharacterHoldingsRevision

    @model_validator(mode="after")
    def _validate_transition(self) -> "WorkerCharacterHoldingsEvidence":
        if self.resulting_holdings.character_id != self.character_id:
            raise ValueError(
                "terminal holdings evidence character identity differs from "
                "its resulting revision",
            )
        if (
            self.resulting_holdings.holdings_revision
            != self.expected_heads.holdings_revision + 1
        ):
            raise ValueError(
                "terminal holdings revision must follow the pinned opening "
                "revision",
            )
        return self


def project_terminal_character_holdings(
    snapshot: CharacterDeploymentSnapshot,
    *,
    game_id: UUID,
    generation_id: UUID,
    terminal_event_cursor: int,
    terminal_combat_log_cursor: int,
    runtime_entity_uuid: UUID,
) -> WorkerCharacterHoldingsEvidence:
    """Project one pinned runtime's exact final durable holdings."""

    opening_by_id = {
        item.character_item_id: item for item in snapshot.holdings.items
    }
    persisted_binding_ids = {
        binding.character_item_id
        for binding in ITEM_RUNTIME_BINDINGS.bindings.values()
        if binding.origin is ItemRuntimeOrigin.PERSISTED
    }
    if persisted_binding_ids != set(opening_by_id):
        raise RuntimeError(
            "runtime item bindings do not exactly cover the pinned character "
            "holdings",
        )
    settled: list[CharacterItemV1] = []
    for runtime_item_uuid, binding in sorted(
        ITEM_RUNTIME_BINDINGS.bindings.items(),
        key=lambda row: row[0].hex,
    ):
        if binding.origin not in {
            ItemRuntimeOrigin.PERSISTED,
            ItemRuntimeOrigin.LOOT,
            ItemRuntimeOrigin.REWARD,
        }:
            continue
        runtime_item = BaseBlock.get(runtime_item_uuid)
        if not isinstance(runtime_item, BaseItem):
            continue
        if runtime_item.owner_uuid != runtime_entity_uuid:
            continue
        character_item_id = binding.character_item_id or uuid5(
            snapshot.character_id,
            "dnd-engine:character-loot:v1:"
            f"{game_id}:{runtime_item_uuid}",
        )
        opening = opening_by_id.get(character_item_id)
        settled.append(
            CharacterItemV1.create(
                character_item_id=character_item_id,
                recipe=binding.recipe,
                quantity=runtime_item.stack_count,
                remaining_charges=(
                    runtime_item.charges
                    if isinstance(runtime_item, UsableItem)
                    and runtime_item.max_charges >= 0
                    else None
                ),
                durability_damage=(
                    runtime_item.health.damage_taken
                    if runtime_item.health is not None
                    else None
                ),
                durable_augmentations=(
                    () if opening is None else opening.durable_augmentations
                ),
                equipped_slot=_equipment_slot(runtime_item.equipped_slot),
            ),
        )
    holdings = CharacterHoldingsRevision.create(
        character_id=snapshot.character_id,
        holdings_revision=snapshot.holdings.holdings_revision + 1,
        items=tuple(
            sorted(
                settled,
                key=lambda item: item.character_item_id.hex,
            ),
        ),
    )
    return WorkerCharacterHoldingsEvidence(
        game_id=game_id,
        generation_id=generation_id,
        terminal_event_cursor=terminal_event_cursor,
        terminal_combat_log_cursor=terminal_combat_log_cursor,
        runtime_entity_uuid=runtime_entity_uuid,
        character_id=snapshot.character_id,
        expected_row_version=snapshot.character_row_version,
        expected_heads=CharacterRevisionHeads(
            definition_revision=snapshot.definition.definition_revision,
            definition_digest=snapshot.definition.definition_digest,
            holdings_revision=snapshot.holdings.holdings_revision,
            holdings_digest=snapshot.holdings.holdings_digest,
            loadout_revision=snapshot.loadout.loadout_revision,
            loadout_digest=snapshot.loadout.loadout_digest,
        ),
        resulting_holdings=holdings,
    )


def build_terminal_settlement_bundle(
    evidence: WorkerCharacterHoldingsEvidence,
    deployment: PinnedCharacterDeploymentRecord,
    *,
    settlement_namespace: str,
) -> CharacterRevisionBundleCommit:
    """Bind worker-owned holdings evidence to gateway-owned deployment facts."""

    if not settlement_namespace:
        raise ValueError("settlement namespace cannot be empty")
    expected = evidence.expected_heads
    if (
        deployment.game_id != evidence.game_id
        or deployment.character_id != evidence.character_id
        or deployment.entity_uuid != evidence.runtime_entity_uuid
        or deployment.definition_revision != expected.definition_revision
        or deployment.definition_digest != expected.definition_digest
        or deployment.holdings_revision != expected.holdings_revision
        or deployment.holdings_digest != expected.holdings_digest
        or deployment.loadout_revision != expected.loadout_revision
        or deployment.loadout_digest != expected.loadout_digest
    ):
        raise ValueError(
            "terminal holdings evidence differs from its pinned deployment",
        )
    holdings = evidence.resulting_holdings
    return CharacterRevisionBundleCommit(
        character_id=evidence.character_id,
        expected_row_version=evidence.expected_row_version,
        expected_heads=expected,
        new_holdings=holdings,
        settlement=CharacterSettlementCreate(
            settlement_id=uuid5(
                deployment.deployment_id,
                settlement_namespace,
            ),
            deployment_id=deployment.deployment_id,
            game_id=evidence.game_id,
            character_id=evidence.character_id,
            starting_holdings_revision=expected.holdings_revision,
            starting_holdings_digest=expected.holdings_digest,
            resulting_holdings_revision=holdings.holdings_revision,
            resulting_holdings_digest=holdings.holdings_digest,
            delta_digest=canonical_digest(
                {
                    "starting_holdings_digest": expected.holdings_digest,
                    "resulting_holdings_digest": holdings.holdings_digest,
                },
            ),
        ),
    )


def _equipment_slot(value: str | None) -> EquipmentSlot | None:
    """Decode the dependency-neutral equipment-slot union."""

    if value is None:
        return None
    for slot_type in (WeaponSlot, BodyPart, RingSlot):
        try:
            return slot_type(value)
        except ValueError:
            continue
    raise ValueError(f"Unknown runtime equipment slot {value!r}")


__all__ = [
    "WorkerCharacterHoldingsEvidence",
    "build_terminal_settlement_bundle",
    "project_terminal_character_holdings",
]
