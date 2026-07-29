"""Exact normalization and preview gates for multi-character rosters."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    DEFAULT_CHARACTER_RULESET_DIGEST,
    BuiltinSingleClassBuild,
    compose_builtin_character_revisions,
)
from dnd.content_system.character_appearance import (
    FIGHTER_HUMAN_APPEARANCE,
)
from dnd.core.content.character_deployment import (
    CharacterDeploymentSnapshot,
)
from dnd.core.content.encounters import (
    FixedRosterOpeningPolicy,
    OwnedCharacterRosterSource,
    RosterControllerDefaults,
    RosterControllerKind,
)
from dnd.core.progression import MulticlassSlotRoundingPolicy
from dnd.scenarios.encounter_assembler import prepare_encounter_recipe
from dnd.scenarios.encounter_catalog import AUTHORED_ROSTER_RECIPES_BY_ID
from dnd.scenarios.encounter_compatibility import (
    resolve_encounter_positions,
)
from server.api_models import (
    GameCreationAuthoredRosterSelection,
    GameCreationComposeRequest,
    GameCreationOwnedCharacterControllerOverride,
    GameCreationOwnedCharacterRosterSelection,
    GameCreationRosterSlotSelection,
    GameCreationSavedRosterSelection,
)
from server.game_creation_composition import (
    GameCreationCompositionError,
    normalize_encounter_recipe,
)
from server.game_creation_preview import (
    build_game_creation_encounter_visual_preview,
)
from server.game_directory.contracts import SavedEncounterRosterRecord


def _snapshot(
    character_id: UUID,
    display_name: str,
) -> CharacterDeploymentSnapshot:
    content_system = bootstrap_content_system()
    revisions = compose_builtin_character_revisions(
        character_id=character_id,
        build=BuiltinSingleClassBuild(
            class_id="fighter",
            level=1,
            equipment_preset="sword_shield",
            appearance=FIGHTER_HUMAN_APPEARANCE,
            fighting_style="dueling",
        ),
        content_system=content_system,
    )
    return CharacterDeploymentSnapshot(
        character_id=character_id,
        character_row_version=1,
        display_name=display_name,
        definition=revisions.definition,
        holdings=revisions.holdings,
        loadout=revisions.loadout,
        expected_ruleset_digest=DEFAULT_CHARACTER_RULESET_DIGEST,
        multiclass_slot_rounding_policy=(
            MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
        ),
        permissive_multiclass_prerequisites=True,
    )


def _request(
    first_id: UUID,
    second_id: UUID,
    *,
    default_controller: RosterControllerKind,
) -> GameCreationComposeRequest:
    default_policy = (
        "builtin.basic"
        if default_controller is RosterControllerKind.AI
        else None
    )
    return GameCreationComposeRequest(
        title="Two Character Test",
        roster_slots=(
            GameCreationRosterSlotSelection(
                roster_slot_id="players",
                roster=GameCreationOwnedCharacterRosterSelection(
                    title="Owned Party",
                    character_ids=(first_id, second_id),
                    member_controller_overrides=(
                        GameCreationOwnedCharacterControllerOverride(
                            character_id=second_id,
                            controller="ai",
                            policy_id="builtin.basic",
                        ),
                    ),
                ),
                faction_id="players",
                deployment_zone_id="zone_1",
                controller_defaults=RosterControllerDefaults(
                    controller=default_controller,
                    participant_name="Local Party",
                    policy_id=default_policy,
                ),
            ),
            GameCreationRosterSlotSelection(
                roster_slot_id="opposition",
                roster=GameCreationAuthoredRosterSelection(
                    roster_id="monsters.skeleton_trio",
                ),
                faction_id="opposition",
                deployment_zone_id="zone_2",
                controller_defaults=RosterControllerDefaults(
                    controller=RosterControllerKind.AI,
                    participant_name="Opposition",
                    policy_id="builtin.basic",
                ),
            ),
        ),
        battlefield_id="battlefield.open_floor_bright",
        deployment_id="neutral.battlefield.open_floor_bright",
        opening_policy=FixedRosterOpeningPolicy(
            roster_slot_id="players",
        ),
    )


def test_normalization_preserves_two_owned_sources_across_controller_changes(
) -> None:
    first_id = uuid4()
    second_id = uuid4()
    deployments = {
        first_id: _snapshot(first_id, "First"),
        second_id: _snapshot(second_id, "Second"),
    }
    human_recipe, human_report = normalize_encounter_recipe(
        _request(
            first_id,
            second_id,
            default_controller=RosterControllerKind.HUMAN,
        ),
        character_deployments=deployments,
    )
    codex_recipe, codex_report = normalize_encounter_recipe(
        _request(
            first_id,
            second_id,
            default_controller=RosterControllerKind.CODEX,
        ),
        character_deployments=deployments,
    )

    assert human_report.admitted
    assert codex_report.admitted
    human_roster = human_recipe.roster_slots[0].roster
    codex_roster = codex_recipe.roster_slots[0].roster
    assert human_roster == codex_roster
    assert human_roster.recipe_digest == codex_roster.recipe_digest
    assert tuple(
        member.source.character_id
        for member in human_roster.members
        if isinstance(member.source, OwnedCharacterRosterSource)
    ) == (first_id, second_id)
    assert (
        human_recipe.roster_slots[0].controller_defaults.controller
        is RosterControllerKind.HUMAN
    )
    assert (
        codex_recipe.roster_slots[0].controller_defaults.controller
        is RosterControllerKind.CODEX
    )
    assert human_recipe.recipe_digest != codex_recipe.recipe_digest


def test_two_owned_characters_materialize_and_preview_from_the_same_recipe(
) -> None:
    first_id = uuid4()
    second_id = uuid4()
    deployments = {
        first_id: _snapshot(first_id, "First"),
        second_id: _snapshot(second_id, "Second"),
    }
    recipe, report = normalize_encounter_recipe(
        _request(
            first_id,
            second_id,
            default_controller=RosterControllerKind.HUMAN,
        ),
        character_deployments=deployments,
    )
    assert report.admitted

    assembled = prepare_encounter_recipe(
        recipe,
        character_deployments=deployments,
    )
    assert tuple(
        entity.name
        for entity in assembled.entities_by_roster_slot["players"]
    ) == ("First", "Second")

    content_digest = bootstrap_content_system().content_set_digest
    preview = build_game_creation_encounter_visual_preview(
        recipe,
        character_deployments=deployments,
        expected_content_set_digest=content_digest,
        expected_ruleset_digest=DEFAULT_CHARACTER_RULESET_DIGEST,
    )
    assert preview.encounter_recipe_digest == recipe.recipe_digest
    assert tuple(
        member.entity.name
        for member in preview.rosters[0].members
    ) == ("First", "Second")
    assert tuple(
        roster.roster_slot_id for roster in preview.rosters
    ) == ("players", "opposition")


def test_saved_roster_selection_reuses_exact_recipe_and_rejects_stale_identity(
) -> None:
    source = AUTHORED_ROSTER_RECIPES_BY_ID[
        "hero.fighter_l5_shield_torch"
    ]
    saved_recipe = source.model_copy(update={
        "roster_id": "roster.saved.fighter",
        "title": "Saved Fighter",
    })
    saved_recipe = type(source).create(
        roster_id=saved_recipe.roster_id,
        title=saved_recipe.title,
        members=saved_recipe.members,
        tags=saved_recipe.tags,
        required_battlefield_capabilities=(
            saved_recipe.required_battlefield_capabilities
        ),
        forbidden_battlefield_capabilities=(
            saved_recipe.forbidden_battlefield_capabilities
        ),
    )
    now = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
    record = SavedEncounterRosterRecord(
        saved_roster_id="saved.roster.fighter",
        owner_principal_id=uuid4(),
        title=saved_recipe.title,
        recipe=saved_recipe,
        recipe_digest=saved_recipe.recipe_digest,
        revision=3,
        created_at=now,
        updated_at=now,
    )
    source_request = _request(
        uuid4(),
        uuid4(),
        default_controller=RosterControllerKind.HUMAN,
    )
    saved_selection = GameCreationSavedRosterSelection(
        saved_roster_id=record.saved_roster_id,
        expected_revision=record.revision,
        expected_recipe_digest=record.recipe_digest,
    )
    request = source_request.model_copy(update={
        "roster_slots": (
            source_request.roster_slots[0].model_copy(update={
                "roster": saved_selection,
            }),
            source_request.roster_slots[1],
        ),
    })

    recipe, compatibility = normalize_encounter_recipe(
        request,
        saved_rosters={record.saved_roster_id: record},
    )

    assert compatibility.admitted
    assert recipe.roster_slots[0].roster == saved_recipe
    assert recipe.roster_slots[0].roster.recipe_digest == record.recipe_digest

    stale_request = request.model_copy(update={
        "roster_slots": (
            request.roster_slots[0].model_copy(update={
                "roster": saved_selection.model_copy(update={
                    "expected_revision": record.revision - 1,
                }),
            }),
            request.roster_slots[1],
        ),
    })
    with pytest.raises(
        GameCreationCompositionError,
        match="changed during composition",
    ):
        normalize_encounter_recipe(
            stale_request,
            saved_rosters={record.saved_roster_id: record},
        )


def test_portable_closed_hazard_deployment_admits_owned_character_vs_goblins(
) -> None:
    character_id = uuid4()
    deployment = _snapshot(character_id, "Portable Hero")
    source_request = _request(
        character_id,
        uuid4(),
        default_controller=RosterControllerKind.HUMAN,
    )
    request = source_request.model_copy(update={
        "title": "Portable Hero vs Goblins",
        "battlefield_id": "battlefield.standard_hazards_closed",
        "deployment_id": (
            "neutral.battlefield.standard_hazards_closed"
        ),
        "roster_slots": (
            source_request.roster_slots[0].model_copy(update={
                "roster": GameCreationOwnedCharacterRosterSelection(
                    title="Owned Hero",
                    character_ids=(character_id,),
                ),
            }),
            source_request.roster_slots[1].model_copy(update={
                "roster": GameCreationAuthoredRosterSelection(
                    roster_id="monsters.goblin_water_cell",
                ),
            }),
        ),
    })

    recipe, compatibility = normalize_encounter_recipe(
        request,
        character_deployments={character_id: deployment},
    )

    assert compatibility.admitted
    positions, issues = resolve_encounter_positions(recipe)
    assert issues == ()
    assert tuple(positions["players"].values()) == ((2, 7),)

    preview = build_game_creation_encounter_visual_preview(
        recipe,
        character_deployments={character_id: deployment},
        expected_content_set_digest=(
            bootstrap_content_system().content_set_digest
        ),
        expected_ruleset_digest=DEFAULT_CHARACTER_RULESET_DIGEST,
    )
    assert preview.encounter_recipe_digest == recipe.recipe_digest
    assert tuple(
        len(roster.members) for roster in preview.rosters
    ) == (1, 3)
