"""Pure read-only catalogs and compatibility preflight for game creation."""

from __future__ import annotations

from typing import Any

from dnd.scenarios.ai_validation_arenas import list_ai_validation_arena_specs
from dnd.scenarios.evaluation.battlefield_catalog import BATTLEFIELDS, get_battlefield
from dnd.scenarios.evaluation.combatant_catalog import (
    HERO_CONFIGURATIONS,
    MONSTER_PARTY_CONFIGURATIONS,
    get_combatant_configuration,
)
from dnd.scenarios.evaluation.compatibility import CompatibilityReport, check_compatibility
from dnd.scenarios.evaluation.deployment_catalog import DEPLOYMENTS, get_deployment
from dnd.scenarios.evaluation.legacy_recipes import LEGACY_RECIPES
from server.api_models import (
    GameCreationCatalogResponse,
    GameCreationPreflightRequest,
    GameCreationPreset,
)


class GameCreationCatalogError(ValueError):
    """Describe an invalid read-only game-creation catalog lookup.

    Attributes:
        code: Stable machine-readable failure code.
        message: Human-readable failure description.
        context: JSON-compatible correction context for API clients.
    """

    def __init__(self, code: str, message: str, **context: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = context

    def detail(self) -> dict[str, Any]:
        """Return the shared structured API error payload."""
        return {
            "code": self.code,
            "message": self.message,
            **self.context,
        }


def build_game_creation_catalog() -> GameCreationCatalogResponse:
    """Build the canonical game-creation catalog without engine mutation.

    Returns:
        Complete controller, composition, battlefield, deployment, and preset
        catalog consumed by standalone and hosted clients.
    """
    specs_by_id = {
        spec.arena_id: spec
        for spec in list_ai_validation_arena_specs()
    }
    presets = [
        GameCreationPreset(
            arena_id=recipe.arena_id,
            title=specs_by_id[recipe.arena_id].title,
            tags=list(specs_by_id[recipe.arena_id].tags),
            expected_pressure=list(specs_by_id[recipe.arena_id].expected_pressure),
            map_notes=list(specs_by_id[recipe.arena_id].map_notes),
            recipe=recipe,
        )
        for recipe in LEGACY_RECIPES
    ]
    return GameCreationCatalogResponse(
        controllers=["human", "ai", "codex"],
        opening_sides=["initiative", "side_a", "side_b"],
        hero_configurations=list(HERO_CONFIGURATIONS),
        monster_configurations=list(MONSTER_PARTY_CONFIGURATIONS),
        battlefields=list(BATTLEFIELDS),
        deployments=list(DEPLOYMENTS),
        presets=presets,
    )


def preflight_game_creation(
    request: GameCreationPreflightRequest,
) -> CompatibilityReport:
    """Check one catalog composition without constructing engine state.

    Args:
        request: Four canonical scenario component identifiers.

    Returns:
        Static compatibility report for the selected components.

    Raises:
        GameCreationCatalogError: If any component identifier is unknown.
    """
    try:
        hero = get_combatant_configuration(request.hero_configuration_id)
        monsters = get_combatant_configuration(request.monster_configuration_id)
        battlefield = get_battlefield(request.battlefield_id)
        deployment = get_deployment(request.deployment_id)
    except ValueError as exc:
        raise GameCreationCatalogError(
            "invalid_game_creation_component",
            str(exc),
            selection=request.model_dump(mode="json"),
            valid_hero_configuration_ids=[
                spec.configuration_id for spec in HERO_CONFIGURATIONS
            ],
            valid_monster_configuration_ids=[
                spec.configuration_id for spec in MONSTER_PARTY_CONFIGURATIONS
            ],
            valid_battlefield_ids=[spec.battlefield_id for spec in BATTLEFIELDS],
            valid_deployment_ids=[spec.deployment_id for spec in DEPLOYMENTS],
        ) from exc
    return check_compatibility(hero, monsters, battlefield, deployment)
