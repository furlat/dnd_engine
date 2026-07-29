"""Disposable runtime authority for persistent character equipment changes."""

from __future__ import annotations

import sys
from uuid import UUID

from pydantic import TypeAdapter

from dnd.blocks.base_item import BaseItem, EquippableItem
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.character_materialization import materialize_character
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.base_block import BaseBlock
from dnd.core.content.durable_characters import (
    CharacterHoldingsRevision,
    CharacterItemV1,
)
from dnd.core.content.materialization import CreatureDeploymentRole
from dnd.core.equipment_types import EquipmentSlot
from dnd.core.progression import (
    character_ruleset_digest,
)
from server.character_directory_contracts import (
    CharacterEquipOperation,
    CharacterUnequipOperation,
)
from server.character_equipment_mutation import (
    CharacterEquipmentRejectionCode,
    CharacterEquipmentMutationWorkerRequest,
    CharacterEquipmentMutationWorkerResult,
)

_EQUIPMENT_SLOT_ADAPTER = TypeAdapter(EquipmentSlot)


def _rejected(
    code: CharacterEquipmentRejectionCode,
    message: str,
) -> CharacterEquipmentMutationWorkerResult:
    return CharacterEquipmentMutationWorkerResult(
        accepted=False,
        rejection_code=code,
        message=message,
    )


def _equipment_slot(value: str | None) -> EquipmentSlot | None:
    if value is None:
        return None
    return _EQUIPMENT_SLOT_ADAPTER.validate_python(value)


def _runtime_item(
    *,
    character_item_id: UUID,
    lineage: tuple[tuple[UUID, UUID], ...],
) -> BaseItem | None:
    runtime_item_uuid = next(
        (
            runtime_uuid
            for durable_id, runtime_uuid in lineage
            if durable_id == character_item_id
        ),
        None,
    )
    if runtime_item_uuid is None:
        return None
    candidate = BaseBlock.get(runtime_item_uuid)
    return candidate if isinstance(candidate, BaseItem) else None


def _normalize_holdings(
    request: CharacterEquipmentMutationWorkerRequest,
    lineage: tuple[tuple[UUID, UUID], ...],
) -> CharacterHoldingsRevision:
    items: list[CharacterItemV1] = []
    for durable_item in request.holdings.items:
        runtime_item = _runtime_item(
            character_item_id=durable_item.character_item_id,
            lineage=lineage,
        )
        if runtime_item is None:
            raise RuntimeError(
                "materialized character omitted a durable possession",
            )
        items.append(CharacterItemV1.create(
            character_item_id=durable_item.character_item_id,
            recipe=durable_item.recipe,
            quantity=durable_item.quantity,
            remaining_charges=durable_item.remaining_charges,
            durability_damage=durable_item.durability_damage,
            durable_augmentations=durable_item.durable_augmentations,
            equipped_slot=_equipment_slot(runtime_item.equipped_slot),
        ))
    return CharacterHoldingsRevision.create(
        character_id=request.holdings.character_id,
        holdings_revision=request.holdings.holdings_revision + 1,
        items=tuple(sorted(
            items,
            key=lambda item: item.character_item_id.hex,
        )),
    )


def run_equipment_mutation(
    request: CharacterEquipmentMutationWorkerRequest,
) -> CharacterEquipmentMutationWorkerResult:
    """Materialize one character and execute the engine-owned transaction."""

    content_system = bootstrap_content_system()
    if content_system.content_set_digest != request.expected_content_set_digest:
        raise ValueError(
            "Content set digest changed between directory and equipment worker",
        )
    expected_ruleset_digest = character_ruleset_digest(
        permissive_multiclass_prerequisites=(
            request.permissive_multiclass_prerequisites
        ),
        multiclass_slot_rounding_policy=(
            request.multiclass_slot_rounding_policy
        ),
    )
    if expected_ruleset_digest != request.expected_ruleset_digest:
        raise ValueError(
            "Ruleset digest changed between directory and equipment worker",
        )
    SERVER_CONTENT_SYSTEM_RUNTIME.install(content_system)
    materialized = materialize_character(
        definition=request.definition,
        holdings=request.holdings,
        loadout=request.loadout,
        runtime_entity_uuid=request.definition.character_id,
        display_name="Character Equipment Validation",
        faction="heroes",
        position=(0, 0),
        deployment_role=CreatureDeploymentRole(
            role_id="character.equipment_validation",
        ),
        expected_ruleset_digest=expected_ruleset_digest,
        multiclass_slot_rounding_policy=(
            request.multiclass_slot_rounding_policy
        ),
        permissive_multiclass_prerequisites=(
            request.permissive_multiclass_prerequisites
        ),
    )
    entity = materialized.entity
    operation = request.operation
    runtime_item = _runtime_item(
        character_item_id=operation.character_item_id,
        lineage=materialized.item_lineage,
    )
    if runtime_item is None:
        return _rejected(
            "unknown_character_item_id",
            "Equipment mutation character_item_id is not in character holdings",
        )

    if isinstance(operation, CharacterEquipOperation):
        if not isinstance(runtime_item, EquippableItem):
            return _rejected(
                "equipment_transition_rejected",
                "Durable item is not equippable",
            )
        current_slot = _equipment_slot(runtime_item.equipped_slot)
        if current_slot is operation.target_slot:
            return _rejected(
                "equipment_state_unchanged",
                "Durable item is already equipped in the requested slot",
            )
        if current_slot is not None:
            try:
                equipped = entity.equipment.equip_transaction(
                    runtime_item,
                    operation.target_slot,
                ).succeeded
            except ValueError as exc:
                return _rejected(
                    "equipment_transition_rejected",
                    "Runtime equipment authority rejected the target slot: "
                    f"{exc}",
                )
        else:
            try:
                equipped = entity.equip_item(
                    runtime_item.uuid,
                    operation.target_slot,
                )
            except ValueError as exc:
                return _rejected(
                    "equipment_transition_rejected",
                    "Runtime equipment authority rejected the target slot: "
                    f"{exc}",
                )
        if not equipped:
            return _rejected(
                "equipment_transition_rejected",
                "Runtime equipment authority rejected the equip transaction",
            )
    elif isinstance(operation, CharacterUnequipOperation):
        current_slot = _equipment_slot(runtime_item.equipped_slot)
        if current_slot is None:
            return _rejected(
                "equipment_state_unchanged",
                "Durable item is not equipped",
            )
        if entity.unequip_item(current_slot) is None:
            return _rejected(
                "equipment_transition_rejected",
                "Runtime equipment authority rejected the unequip transaction",
            )
    else:
        raise AssertionError("Unhandled character equipment operation")

    return CharacterEquipmentMutationWorkerResult(
        accepted=True,
        resulting_holdings=_normalize_holdings(
            request,
            materialized.item_lineage,
        ),
    )


def main() -> int:
    request = CharacterEquipmentMutationWorkerRequest.model_validate_json(
        sys.stdin.read(),
    )
    result = run_equipment_mutation(request)
    sys.stdout.write(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CharacterEquipmentMutationWorkerRequest",
    "CharacterEquipmentMutationWorkerResult",
    "run_equipment_mutation",
]
