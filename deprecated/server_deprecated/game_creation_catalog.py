"""Pure read-only roster and encounter catalog for game creation."""

from __future__ import annotations

from dnd.scenarios.encounter_catalog import (
    AUTHORED_DEPLOYMENTS,
    AUTHORED_ENCOUNTER_RECIPES,
    AUTHORED_ROSTER_RECIPES,
)
from dnd.scenarios.battlefield_catalog import BATTLEFIELDS
from server.api_models import (
    GameCreationCatalogResponse,
)


def build_game_creation_catalog() -> GameCreationCatalogResponse:
    """Return the human-playable authored game catalog."""
    return GameCreationCatalogResponse(
        roster_recipes=AUTHORED_ROSTER_RECIPES,
        encounter_recipes=AUTHORED_ENCOUNTER_RECIPES,
        battlefields=list(BATTLEFIELDS),
        deployments=AUTHORED_DEPLOYMENTS,
    )


__all__ = [
    "build_game_creation_catalog",
]
