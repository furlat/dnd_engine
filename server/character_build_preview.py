"""Parent-safe access to isolated production character visual previews."""

from __future__ import annotations

import subprocess
import sys
from functools import lru_cache

from pydantic import ValidationError

from dnd.core.content.durable_characters import (
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
)
from dnd.core.content.premade_characters import (
    CharacterBuildDraft,
    CharacterLoadoutDraft,
)
from dnd.core.progression import MulticlassSlotRoundingPolicy
from server.character_build_preview_worker import (
    CharacterBuildPreviewWorkerRequest,
)
from server.character_directory_contracts import (
    CharacterBuildVisualPreviewResponse,
)


class CharacterBuildPreviewError(ValueError):
    """Typed route-safe failure from the disposable preview worker."""

    def __init__(self, code: str, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def detail(self) -> dict[str, object]:
        return {"code": self.code, "message": self.message}


@lru_cache(maxsize=64)
def _build_cached_character_preview(
    request_json: str,
) -> CharacterBuildVisualPreviewResponse:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "server.character_build_preview_worker"],
            input=request_json,
            capture_output=True,
            check=False,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired as exc:
        raise CharacterBuildPreviewError(
            "character_build_preview_timeout",
            "Character visual preview materialization timed out.",
            status_code=504,
        ) from exc
    if completed.returncode != 0:
        diagnostic = completed.stderr.strip().splitlines()
        suffix = (
            diagnostic[-1]
            if diagnostic
            else "child process exited without diagnostics"
        )
        raise CharacterBuildPreviewError(
            "character_build_preview_failed",
            f"Character visual preview materialization failed: {suffix}",
            status_code=500,
        )
    try:
        return CharacterBuildVisualPreviewResponse.model_validate_json(
            completed.stdout,
        )
    except ValidationError as exc:
        raise CharacterBuildPreviewError(
            "invalid_character_build_preview",
            "Character visual preview worker returned an invalid payload.",
            status_code=500,
        ) from exc


def build_character_visual_preview(
    *,
    definition: CharacterDefinitionRevisionV2,
    holdings: CharacterHoldingsRevision,
    loadout: CharacterLoadoutRevisionV1,
    normalized_build: CharacterBuildDraft,
    normalized_loadout: CharacterLoadoutDraft,
    preview_digest: str,
    permissive_multiclass_prerequisites: bool,
    multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy,
) -> CharacterBuildVisualPreviewResponse:
    """Project one exact validated build without mutating parent registries."""

    request_json = CharacterBuildPreviewWorkerRequest(
        definition=definition,
        holdings=holdings,
        loadout=loadout,
        normalized_build=normalized_build,
        normalized_loadout=normalized_loadout,
        preview_digest=preview_digest,
        permissive_multiclass_prerequisites=(
            permissive_multiclass_prerequisites
        ),
        multiclass_slot_rounding_policy=(
            multiclass_slot_rounding_policy
        ),
    ).model_dump_json()
    response = _build_cached_character_preview(request_json)
    if (
        response.content_set_digest != definition.content_set_digest
        or response.ruleset_digest != definition.ruleset_digest
        or response.preview_digest != preview_digest
        or response.normalized_build != normalized_build
        or response.normalized_loadout != normalized_loadout
    ):
        raise CharacterBuildPreviewError(
            "character_build_preview_identity_mismatch",
            "Character visual preview worker returned a different build identity.",
            status_code=500,
        )
    return response

__all__ = [
    "CharacterBuildPreviewError",
    "build_character_visual_preview",
]
