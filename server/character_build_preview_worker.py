"""Disposable runtime for exact character-build visual projection."""

from __future__ import annotations

import sys

from pydantic import BaseModel, ConfigDict, Field

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.character_materialization import materialize_character
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.content.durable_characters import (
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
)
from dnd.core.content.materialization import CreatureDeploymentRole
from dnd.core.content.premade_characters import (
    CharacterBuildDraft,
    CharacterLoadoutDraft,
)
from dnd.core.progression import (
    MulticlassSlotRoundingPolicy,
    character_ruleset_digest,
)
from server.character_directory_contracts import (
    CharacterBuildVisualPreviewResponse,
)
from server.player_replication.world_projection import (
    build_entity_visual_loadout,
)
from server.world_projection import project_entity_summary


class CharacterBuildPreviewWorkerRequest(BaseModel):
    """Complete authenticated input for one isolated materialization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    definition: CharacterDefinitionRevisionV2
    holdings: CharacterHoldingsRevision
    loadout: CharacterLoadoutRevisionV1
    normalized_build: CharacterBuildDraft
    normalized_loadout: CharacterLoadoutDraft
    preview_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    permissive_multiclass_prerequisites: bool
    multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy


def build_worker_preview(
    request: CharacterBuildPreviewWorkerRequest,
) -> CharacterBuildVisualPreviewResponse:
    content_system = bootstrap_content_system()
    definition = request.definition
    if content_system.content_set_digest != definition.content_set_digest:
        raise ValueError(
            "Content set digest changed between parent and preview worker.",
        )
    expected_ruleset_digest = character_ruleset_digest(
        permissive_multiclass_prerequisites=(
            request.permissive_multiclass_prerequisites
        ),
        multiclass_slot_rounding_policy=(
            request.multiclass_slot_rounding_policy
        ),
    )
    if definition.ruleset_digest != expected_ruleset_digest:
        raise ValueError(
            "Ruleset digest changed between parent and preview worker.",
        )
    if (
        definition.character_id != request.holdings.character_id
        or definition.character_id != request.loadout.character_id
    ):
        raise ValueError("Preview revisions do not share one character identity.")

    SERVER_CONTENT_SYSTEM_RUNTIME.install(content_system)
    materialized = materialize_character(
        definition=definition,
        holdings=request.holdings,
        loadout=request.loadout,
        runtime_entity_uuid=definition.character_id,
        display_name="Character Preview",
        faction="heroes",
        position=(0, 0),
        deployment_role=CreatureDeploymentRole(
            role_id="character.preview",
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
    return CharacterBuildVisualPreviewResponse(
        content_set_digest=content_system.content_set_digest,
        ruleset_digest=expected_ruleset_digest,
        preview_digest=request.preview_digest,
        normalized_build=request.normalized_build,
        normalized_loadout=request.normalized_loadout,
        entity=project_entity_summary(entity),
        visual_loadout=build_entity_visual_loadout(entity),
    )


def main() -> int:
    request = CharacterBuildPreviewWorkerRequest.model_validate_json(
        sys.stdin.read(),
    )
    response = build_worker_preview(request)
    sys.stdout.write(response.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
