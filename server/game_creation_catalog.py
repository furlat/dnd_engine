"""Pure read-only roster and encounter catalog for game creation."""

from __future__ import annotations

from typing import Sequence

from dnd.scenarios.encounter_catalog import (
    AUTHORED_DEPLOYMENTS,
    AUTHORED_ENCOUNTER_RECIPES,
    AUTHORED_ROSTER_RECIPES,
)
from dnd.scenarios.battlefield_catalog import BATTLEFIELDS
from server.api_models import (
    GameCreationAIPolicyOption,
    GameCreationCatalogResponse,
    GameCreationControllerKind,
)


def build_game_creation_catalog(
    *,
    controllers: Sequence[GameCreationControllerKind],
    ai_policies: Sequence[GameCreationAIPolicyOption],
) -> GameCreationCatalogResponse:
    """Return content plus the caller's explicitly executable controllers."""
    return GameCreationCatalogResponse(
        controllers=list(controllers),
        ai_policies=sorted(
            ai_policies,
            key=lambda option: option.descriptor.policy_id,
        ),
        roster_recipes=AUTHORED_ROSTER_RECIPES,
        encounter_recipes=AUTHORED_ENCOUNTER_RECIPES,
        battlefields=list(BATTLEFIELDS),
        deployments=AUTHORED_DEPLOYMENTS,
    )


__all__ = [
    "build_game_creation_catalog",
]
