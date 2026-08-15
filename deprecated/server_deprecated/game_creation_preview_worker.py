"""Cold-process production projector for one normalized encounter recipe."""

from __future__ import annotations

import json
import sys
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.content.encounters import EncounterRecipe
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.encounter_assembler import prepare_encounter_recipe
from server.game_creation_preview_contracts import (
    GameCreationEncounterVisualPreviewResponse,
    GameCreationMemberVisualPreview,
    GameCreationRosterVisualPreview,
)
from server.player_replication.world_projection import (
    build_entity_visual_loadout,
)
from server.world_projection import project_entity_summary


class PreviewWorkerRequest(BaseModel):
    """Validated stdin envelope for one exact encounter preview."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    recipe: EncounterRecipe


def build_worker_preview(
    request: PreviewWorkerRequest,
) -> GameCreationEncounterVisualPreviewResponse:
    """Materialize and project one recipe entirely in this child process."""
    reset_engine_runtime()
    content_system = bootstrap_content_system()
    if content_system.content_set_digest != request.expected_content_set_digest:
        raise ValueError(
            "Content set digest changed between parent and preview worker.",
        )
    SERVER_CONTENT_SYSTEM_RUNTIME.install(content_system)
    assembled = prepare_encounter_recipe(request.recipe)
    rosters: list[GameCreationRosterVisualPreview] = []
    for roster_slot in request.recipe.roster_slots:
        members: list[GameCreationMemberVisualPreview] = []
        for member in roster_slot.roster.members:
            entity = assembled.entities_by_member_address[
                (roster_slot.roster_slot_id, member.member_id)
            ]
            preview_uuid = str(uuid5(
                NAMESPACE_URL,
                (
                    "dnd-engine:encounter-preview:"
                    f"{request.recipe.recipe_digest}:"
                    f"{roster_slot.roster_slot_id}:{member.member_id}"
                ),
            ))
            members.append(GameCreationMemberVisualPreview(
                member_id=member.member_id,
                deployment_role=member.deployment_role,
                entity=project_entity_summary(entity).model_copy(
                    update={"uuid": preview_uuid},
                ),
                visual_loadout=build_entity_visual_loadout(entity).model_copy(
                    update={"entity_uuid": preview_uuid},
                ),
            ))
        rosters.append(GameCreationRosterVisualPreview(
            roster_slot_id=roster_slot.roster_slot_id,
            roster_id=roster_slot.roster.roster_id,
            title=roster_slot.roster.title,
            members=tuple(members),
        ))
    return GameCreationEncounterVisualPreviewResponse(
        content_set_digest=content_system.content_set_digest,
        ruleset_digest=request.expected_ruleset_digest,
        encounter_recipe_digest=request.recipe.recipe_digest,
        rosters=tuple(rosters),
    )


def serve() -> int:
    """Serve newline-delimited preview requests in one isolated generation."""
    sys.stdout.write(json.dumps({
        "kind": "ready",
        "protocol_version": 1,
    }, sort_keys=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = PreviewWorkerRequest.model_validate_json(line)
            response = build_worker_preview(request)
            envelope = {
                "kind": "preview",
                "payload": response.model_dump(mode="json"),
            }
        except Exception as exc:
            envelope = {
                "kind": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
        sys.stdout.write(
            json.dumps(
                envelope,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
        )
        sys.stdout.flush()
    return 0


def main() -> int:
    """Read one request from stdin and write one response to stdout."""
    if sys.argv[1:] == ["--serve"]:
        return serve()
    request = PreviewWorkerRequest.model_validate_json(sys.stdin.read())
    response = build_worker_preview(request)
    sys.stdout.write(response.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
