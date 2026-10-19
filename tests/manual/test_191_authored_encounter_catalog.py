"""Canonical authored encounter inventory and assembly closure."""

from __future__ import annotations

from dnd.content.characters.premades import PREMADE_CHARACTER_BUILDS
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.content_system.spell_catalog_composition import (
    SPELL_CATALOG_COMPOSITION_BY_NAME,
)
from dnd.core.content.encounters import (
    AuthoredCreatureRosterSource,
    EncounterRosterRecipe,
    PremadeCharacterRosterSource,
    RosterSpellGrant,
)
from dnd.core.gridmap import get_map
from tests.engine.authored_character_support import prepare_roster_member
from dnd.game import Game
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
    assert len(BATTLEFIELDS) == 20
    assert len(AUTHORED_DEPLOYMENTS) == 9
    assert len(AUTHORED_ROSTER_RECIPES) == 60
    assert sum(len(row.members) for row in AUTHORED_ROSTER_RECIPES) == 146
    assert len(AUTHORED_ENCOUNTER_RECIPES) == 42

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
            if isinstance(member.source, PremadeCharacterRosterSource):
                assert member.source.premade_id in PREMADE_CHARACTER_BUILDS
                continue
            assert isinstance(member.source, AuthoredCreatureRosterSource)
            assert member.source.recipe.ref.definition_kind.value == "creature"
            member.source.recipe.verify_integrity()

    for encounter in AUTHORED_ENCOUNTER_RECIPES:
        assert encounter_recipe(encounter.encounter_id) is encounter
        assert encounter.tags
        expected_deployment = {
            "encounter.storehouse_demo": "deployment.storehouse_demo",
            "encounter.lantern_crypt": "deployment.lantern_crypt",
            "encounter.lantern_gallery": "deployment.lantern_gallery",
        }.get(encounter.encounter_id, f"deployment.{encounter.encounter_id}")
        assert encounter.deployment.deployment_id == expected_deployment


def test_only_reusable_neutral_deployments_are_public() -> None:
    assert {
        deployment.battlefield_id
        for deployment in AUTHORED_DEPLOYMENTS
    } == {
        "battlefield.standard_hazards_closed", "battlefield.open_floor_bright",
        "battlefield.standard_hazards_open", "battlefield.double_door_dark",
        "battlefield.arcane_device_bright", "battlefield.reveal_labyrinth_dark",
        "battlefield.field_cache_bright", "battlefield.multi_object_dark",
        "battlefield.open_floor_dark",
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
        reset_engine_runtime()
        assembled = prepare_encounter_recipe(recipe, game=Game())
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
    """Original spell requests survive in both reusable and embedded rosters."""
    expected_spells = {
        "scenario.sorcerer_l5_standard": {
            "Fire Bolt", "Ray of Frost", "Magic Missile", "Burning Hands",
            "Thunderwave", "Scorching Ray", "Hold Person", "Shatter",
            "Invisibility", "Fireball", "Lightning Bolt",
        },
        "scenario.sorcerer_l9_standard": {
            "Fire Bolt", "Ray of Frost", "Magic Missile", "Thunderwave",
            "Scorching Ray", "Hold Person", "Shatter", "Invisibility",
            "Fireball", "Lightning Bolt", "Hypnotic Pattern", "Slow", "Haste",
            "Banishment", "Greater Invisibility", "Cone of Cold", "Cloudkill",
        },
        "scenario.sorcerer_l5_projectile": {
            "Fire Bolt", "Ray of Frost", "Magic Missile", "Scorching Ray",
        },
        "scenario.sorcerer_l5_mirror": {
            "Fire Bolt", "Ray of Frost", "Magic Missile", "Scorching Ray",
            "Hold Person", "Haste", "Slow", "Fireball", "Lightning Bolt",
        },
        "scenario.sorcerer_l5_control": {
            "Fire Bolt", "Ray of Frost", "Magic Missile", "Hold Person",
            "Web", "Hypnotic Pattern", "Slow", "Fireball",
        },
        "scenario.sorcerer_l7_lock": {
            "Fire Bolt", "Ray of Frost", "Hold Person", "Fear",
            "Hypnotic Pattern", "Slow", "Banishment",
        },
    }
    all_rosters: tuple[EncounterRosterRecipe, ...] = (
        *AUTHORED_ROSTER_RECIPES,
        *(slot.roster for encounter in AUTHORED_ENCOUNTER_RECIPES
          for slot in encounter.roster_slots),
    )
    audited_members = 0
    try:
        for roster in all_rosters:
            for member in roster.members:
                source = member.source
                if not isinstance(source, PremadeCharacterRosterSource):
                    continue
                if source.premade_id not in expected_spells:
                    continue
                audited_members += 1
                entity = prepare_roster_member(roster, member.member_id)
                materialized_names = {action.name for action in entity.registered_actions}
                assert expected_spells[source.premade_id] <= materialized_names, (
                    roster.roster_id, member.member_id,
                    expected_spells[source.premade_id] - materialized_names,
                )
                granted_identities = [
                    ref.identity_key
                    for effect in member.scenario_setup_effects
                    if isinstance(effect, RosterSpellGrant)
                    for ref in effect.spell_refs
                ]
                assert len(granted_identities) == len(set(granted_identities)), (
                    roster.roster_id, member.member_id,
                )
                runtime_spell_identities = {
                    SPELL_CATALOG_COMPOSITION_BY_NAME[name].declaration.ref.identity_key
                    for name in materialized_names
                    if name in SPELL_CATALOG_COMPOSITION_BY_NAME
                }
                assert set(granted_identities) <= runtime_spell_identities
    finally:
        reset_engine_runtime()
    assert audited_members == 25


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
