"""Parent-safe access to isolated persistent equipment rule execution."""

from __future__ import annotations

import subprocess
import sys
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from dnd.core.content.durable_characters import (
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
)
from dnd.core.progression import MulticlassSlotRoundingPolicy
from server.character_directory_contracts import CharacterEquipmentOperation
from server.game_directory.errors import ConflictError


CharacterEquipmentRejectionCode: TypeAlias = Literal[
    "unknown_character_item_id",
    "equipment_state_unchanged",
    "equipment_transition_rejected",
]


class CharacterEquipmentMutationWorkerRequest(BaseModel):
    """Complete authenticated state needed for one isolated gear transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    definition: CharacterDefinitionRevisionV2
    holdings: CharacterHoldingsRevision
    loadout: CharacterLoadoutRevisionV1
    operation: CharacterEquipmentOperation
    expected_content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    permissive_multiclass_prerequisites: bool
    multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy

    @model_validator(mode="after")
    def _validate_identity(self) -> "CharacterEquipmentMutationWorkerRequest":
        if (
            self.definition.character_id != self.holdings.character_id
            or self.definition.character_id != self.loadout.character_id
        ):
            raise ValueError(
                "equipment mutation revisions must share one character identity",
            )
        if (
            self.definition.content_set_digest
            != self.expected_content_set_digest
        ):
            raise ValueError(
                "equipment mutation content identity differs from definition",
            )
        if self.definition.ruleset_digest != self.expected_ruleset_digest:
            raise ValueError(
                "equipment mutation ruleset identity differs from definition",
            )
        return self


class CharacterEquipmentMutationWorkerResult(BaseModel):
    """Closed success/rejection result emitted by the disposable worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    resulting_holdings: CharacterHoldingsRevision | None = None
    rejection_code: CharacterEquipmentRejectionCode | None = None
    message: str | None = None

    @model_validator(mode="after")
    def _validate_result(self) -> "CharacterEquipmentMutationWorkerResult":
        if self.accepted:
            if (
                self.resulting_holdings is None
                or self.rejection_code is not None
                or self.message is not None
            ):
                raise ValueError(
                    "accepted equipment result must contain only holdings",
                )
        elif (
            self.resulting_holdings is not None
            or not self.rejection_code
            or not self.message
        ):
            raise ValueError(
                "rejected equipment result requires a code and message",
            )
        return self


class CharacterEquipmentMutationRejected(ConflictError):
    """The authoritative runtime equipment transaction rejected the request."""


class CharacterEquipmentMutationError(RuntimeError):
    """The isolated equipment authority could not produce a valid result."""


def mutate_character_equipment(
    *,
    definition: CharacterDefinitionRevisionV2,
    holdings: CharacterHoldingsRevision,
    loadout: CharacterLoadoutRevisionV1,
    operation: CharacterEquipmentOperation,
    expected_content_set_digest: str,
    expected_ruleset_digest: str,
    permissive_multiclass_prerequisites: bool,
    multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy,
) -> CharacterHoldingsRevision:
    """Execute one gear transition without mutating parent process registries."""

    worker_request = CharacterEquipmentMutationWorkerRequest(
        definition=definition,
        holdings=holdings,
        loadout=loadout,
        operation=operation,
        expected_content_set_digest=expected_content_set_digest,
        expected_ruleset_digest=expected_ruleset_digest,
        permissive_multiclass_prerequisites=(
            permissive_multiclass_prerequisites
        ),
        multiclass_slot_rounding_policy=multiclass_slot_rounding_policy,
    )
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "server.character_equipment_mutation_worker",
            ],
            input=worker_request.model_dump_json(),
            capture_output=True,
            check=False,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired as exc:
        raise CharacterEquipmentMutationError(
            "Character equipment validation timed out",
        ) from exc
    if completed.returncode != 0:
        diagnostic = completed.stderr.strip().splitlines()
        suffix = (
            diagnostic[-1]
            if diagnostic
            else "child process exited without diagnostics"
        )
        raise CharacterEquipmentMutationError(
            f"Character equipment validation failed: {suffix}",
        )
    try:
        result = CharacterEquipmentMutationWorkerResult.model_validate_json(
            completed.stdout,
        )
    except ValidationError as exc:
        raise CharacterEquipmentMutationError(
            "Character equipment worker returned an invalid result",
        ) from exc
    if not result.accepted:
        raise CharacterEquipmentMutationRejected(
            f"Character equipment rejected "
            f"({result.rejection_code}): {result.message}",
        )
    holdings_result = result.resulting_holdings
    if holdings_result is None:
        raise CharacterEquipmentMutationError(
            "Accepted character equipment result omitted holdings",
        )
    if (
        holdings_result.character_id != definition.character_id
        or holdings_result.holdings_revision
        != holdings.holdings_revision + 1
    ):
        raise CharacterEquipmentMutationError(
            "Character equipment worker returned mismatched holdings identity",
        )
    return holdings_result


__all__ = [
    "CharacterEquipmentMutationWorkerRequest",
    "CharacterEquipmentMutationWorkerResult",
    "CharacterEquipmentMutationError",
    "CharacterEquipmentMutationRejected",
    "mutate_character_equipment",
]
