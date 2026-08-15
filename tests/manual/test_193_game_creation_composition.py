"""Exact authored-roster normalization and preview gates."""

from __future__ import annotations

import pytest

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    DEFAULT_CHARACTER_RULESET_DIGEST,
)
from dnd.core.content.encounters import FixedRosterOpeningPolicy
from dnd.scenarios.encounter_assembler import prepare_encounter_recipe
from dnd.scenarios.encounter_catalog import AUTHORED_ROSTER_RECIPES_BY_ID
from server.api_models import (
    GameCreationAuthoredRosterSelection,
    GameCreationComposeRequest,
    GameCreationRosterSlotSelection,
)
from server.game_creation_composition import (
    GameCreationCompositionError,
    normalize_encounter_recipe,
)
from server.game_creation_preview import (
    build_game_creation_encounter_visual_preview,
)


def _request(*, participant_name: str = "Local Party") -> GameCreationComposeRequest:
    return GameCreationComposeRequest(
        title="Authored Composition Test",
        roster_slots=(
            GameCreationRosterSlotSelection(
                roster_slot_id="players",
                roster=GameCreationAuthoredRosterSelection(
                    roster_id="hero.fighter_l5_archer_torch",
                ),
                faction_id="players",
                deployment_zone_id="zone_1",
                participant_name=participant_name,
            ),
            GameCreationRosterSlotSelection(
                roster_slot_id="opposition",
                roster=GameCreationAuthoredRosterSelection(
                    roster_id="monsters.skeleton_trio",
                ),
                faction_id="opposition",
                deployment_zone_id="zone_2",
                participant_name="Opposition",
            ),
        ),
        battlefield_id="battlefield.standard_hazards_closed",
        deployment_id="neutral.battlefield.standard_hazards_closed",
        opening_policy=FixedRosterOpeningPolicy(roster_slot_id="players"),
    )


def test_normalization_resolves_exact_authored_rosters() -> None:
    recipe, report = normalize_encounter_recipe(_request())

    assert report.admitted
    assert recipe.roster_slots[0].roster is AUTHORED_ROSTER_RECIPES_BY_ID[
        "hero.fighter_l5_archer_torch"
    ]
    assert recipe.roster_slots[1].roster is AUTHORED_ROSTER_RECIPES_BY_ID[
        "monsters.skeleton_trio"
    ]
    assert all(
        member.source.kind == "authored_creature"
        for slot in recipe.roster_slots
        for member in slot.roster.members
    )


def test_participant_presentation_changes_only_encounter_identity() -> None:
    local, _ = normalize_encounter_recipe(_request(participant_name="Local"))
    remote, _ = normalize_encounter_recipe(_request(participant_name="Remote"))

    assert local.roster_slots[0].roster == remote.roster_slots[0].roster
    assert local.recipe_digest != remote.recipe_digest


def test_unknown_authored_roster_is_rejected() -> None:
    request = _request().model_copy(deep=True)
    first = request.roster_slots[0].model_copy(update={
        "roster": GameCreationAuthoredRosterSelection(
            roster_id="missing.roster",
        ),
    })
    request = request.model_copy(update={
        "roster_slots": (first, request.roster_slots[1]),
    })

    with pytest.raises(GameCreationCompositionError, match="unknown authored roster"):
        normalize_encounter_recipe(request)


def test_authored_recipe_materializes_and_previews_without_database() -> None:
    recipe, report = normalize_encounter_recipe(_request())
    content_system = bootstrap_content_system()

    preview = build_game_creation_encounter_visual_preview(
        recipe,
        expected_content_set_digest=content_system.content_set_digest,
        expected_ruleset_digest=DEFAULT_CHARACTER_RULESET_DIGEST,
    )
    assembled = prepare_encounter_recipe(recipe)

    assert report.admitted
    assert preview.encounter_recipe_digest == recipe.recipe_digest
    assert sum(len(roster.members) for roster in preview.rosters) == len(
        assembled.entities
    )
