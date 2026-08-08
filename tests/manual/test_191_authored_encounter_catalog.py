"""Canonical authored encounter inventory and assembly closure."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.content_system.spell_catalog_composition import (
    SPELL_CATALOG_COMPOSITION_BY_NAME,
)
from dnd.core.content.encounters import (
    AuthoredCreatureRosterSource,
    EncounterRosterRecipe,
    RosterSpellGrant,
)
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.gridmap import get_map
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import BATTLEFIELDS, build_battlefield
from dnd.scenarios.encounter_assembler import prepare_encounter_recipe
from dnd.scenarios.encounter_catalog import (
    AUTHORED_DEPLOYMENTS,
    AUTHORED_ENCOUNTER_RECIPES,
    AUTHORED_ROSTER_RECIPES,
    encounter_recipe,
    roster_recipe,
)


def test_authored_catalog_inventory_is_complete_and_exact() -> None:
    assert len(BATTLEFIELDS) == 10
    assert len(AUTHORED_DEPLOYMENTS) == 10
    assert len(AUTHORED_ROSTER_RECIPES) == 58
    assert sum(len(row.members) for row in AUTHORED_ROSTER_RECIPES) == 141
    assert len(AUTHORED_ENCOUNTER_RECIPES) == 39

    assert len({
        row.battlefield_id for row in BATTLEFIELDS
    }) == len(BATTLEFIELDS)
    assert len({
        row.roster_id for row in AUTHORED_ROSTER_RECIPES
    }) == len(AUTHORED_ROSTER_RECIPES)
    assert len({
        row.encounter_id for row in AUTHORED_ENCOUNTER_RECIPES
    }) == len(AUTHORED_ENCOUNTER_RECIPES)

    for roster in AUTHORED_ROSTER_RECIPES:
        assert roster_recipe(roster.roster_id) is roster
        for member in roster.members:
            assert isinstance(member.source, AuthoredCreatureRosterSource)
            assert member.source.recipe.ref.definition_kind.value == "creature"
            member.source.recipe.verify_integrity()

    for encounter in AUTHORED_ENCOUNTER_RECIPES:
        assert encounter_recipe(encounter.encounter_id) is encounter
        assert encounter.tags == ("authored",)
        assert encounter.deployment.deployment_id == (
            f"deployment.{encounter.encounter_id}"
        )


def test_only_reusable_neutral_deployments_are_public() -> None:
    assert {
        deployment.battlefield_id
        for deployment in AUTHORED_DEPLOYMENTS
    } == {
        battlefield.battlefield_id for battlefield in BATTLEFIELDS
    }
    assert all(
        deployment.deployment_id
        == f"neutral.{deployment.battlefield_id}"
        for deployment in AUTHORED_DEPLOYMENTS
    )
    assert all(
        "portable" in deployment.tags
        for deployment in AUTHORED_DEPLOYMENTS
    )
    assert {
        encounter.deployment.deployment_id
        for encounter in AUTHORED_ENCOUNTER_RECIPES
    }.isdisjoint({
        deployment.deployment_id
        for deployment in AUTHORED_DEPLOYMENTS
    })


def test_every_reusable_slot_is_walkable_on_its_battlefield() -> None:
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    try:
        for deployment in AUTHORED_DEPLOYMENTS:
            reset_engine_runtime()
            build_battlefield(deployment.battlefield_id)
            grid = get_map()
            blocked = [
                position
                for zone in deployment.zones
                for position in zone.ordered_slots
                if not grid.is_walkable_for(*position)
            ]
            assert not blocked, (deployment.deployment_id, blocked)
    finally:
        reset_engine_runtime()


def test_every_authored_encounter_prepares_through_canonical_assembler() -> None:
    for recipe in AUTHORED_ENCOUNTER_RECIPES:
        assembled = prepare_encounter_recipe(recipe)
        addresses = {
            address
            for address in assembled.entities_by_member_address
        }
        expected = {
            (slot.roster_slot_id, member.member_id)
            for slot in recipe.roster_slots
            for member in slot.roster.members
        }
        assert addresses == expected, recipe.encounter_id
        assert assembled.compatibility.admitted, recipe.encounter_id
        assert assembled.recipe is recipe
    reset_engine_runtime()


def test_every_authored_spell_matrix_preserves_requested_runtime_spells() -> None:
    """Scenario-only spell matrices must survive canonical roster migration."""
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    all_rosters: tuple[EncounterRosterRecipe, ...] = (
        *AUTHORED_ROSTER_RECIPES,
        *(
            slot.roster
            for encounter in AUTHORED_ENCOUNTER_RECIPES
            for slot in encounter.roster_slots
        ),
    )
    audited_members = 0
    try:
        for roster in all_rosters:
            for member in roster.members:
                source = member.source
                if not isinstance(source, AuthoredCreatureRosterSource):
                    continue
                requested_names = tuple(
                    cast(
                        list[str],
                        source.recipe.parameters.get("spell_names", []),
                    ),
                )
                if not requested_names:
                    continue
                audited_members += 1
                reset_engine_runtime()
                entity = materialize_creature(
                    source.recipe,
                    runtime_entity_uuid=uuid4(),
                    display_name=member.display_name,
                    faction="spell-matrix-audit",
                    position=(0, 0),
                    deployment_role=CreatureDeploymentRole(
                        role_id="audit.spell_matrix",
                    ),
                    possession_mode=(
                        CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
                    ),
                )
                materialized_names = {
                    action.name for action in entity.registered_actions
                }
                granted_identities = [
                    ref.identity_key
                    for effect in member.scenario_setup_effects
                    if isinstance(effect, RosterSpellGrant)
                    for ref in effect.spell_refs
                ]
                assert len(granted_identities) == len(
                    set(granted_identities),
                ), (roster.roster_id, member.member_id)
                missing_identities = {
                    SPELL_CATALOG_COMPOSITION_BY_NAME[
                        name
                    ].declaration.ref.identity_key
                    for name in requested_names
                    if name not in materialized_names
                }
                assert missing_identities <= set(granted_identities), (
                    roster.roster_id,
                    member.member_id,
                    sorted(missing_identities - set(granted_identities)),
                )
    finally:
        reset_engine_runtime()
    assert audited_members == 26


def test_payloads_do_not_export_retired_scenario_ontology() -> None:
    serialized = repr([
        encounter.model_dump(mode="json")
        for encounter in AUTHORED_ENCOUNTER_RECIPES
    ])
    for retired in (
        "hero_configuration_id",
        "monster_configuration_id",
        "side_kind",
        "hero_slots",
        "monster_slots",
        "source_arena_id",
        "rating_eligible",
        "legacy.",
        "historical_validation",
    ):
        assert retired not in serialized
