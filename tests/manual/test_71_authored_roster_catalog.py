"""Canonical authored roster identity and content coverage."""

from __future__ import annotations

from dnd.core.content.encounters import (
    AuthoredCreatureRosterSource,
    RosterItemGrant,
)
from dnd.monsters.configured_srd_creatures import (
    PLAYABLE_SRD_CREATURE_RECIPES_BY_ID,
)
from dnd.scenarios.encounter_catalog import (
    AUTHORED_ROSTER_RECIPES,
    roster_recipe,
)


def test_roster_catalog_has_exact_audited_counts_and_unique_identity() -> None:
    assert len(AUTHORED_ROSTER_RECIPES) == 58
    assert sum(len(row.members) for row in AUTHORED_ROSTER_RECIPES) == 141
    assert len({
        row.roster_id for row in AUTHORED_ROSTER_RECIPES
    }) == 58
    assert len({
        row.recipe_digest for row in AUTHORED_ROSTER_RECIPES
    }) == 58
    assert all(
        roster_recipe(row.roster_id) is row
        for row in AUTHORED_ROSTER_RECIPES
    )


def test_every_authored_member_has_an_exact_creature_recipe() -> None:
    for roster in AUTHORED_ROSTER_RECIPES:
        for member in roster.members:
            assert isinstance(
                member.source,
                AuthoredCreatureRosterSource,
            )
            member.source.recipe.verify_integrity()
            assert (
                member.source.recipe.ref.definition_kind.value
                == "creature"
            )


def test_every_srd_creature_factory_is_represented_in_a_roster() -> None:
    represented_refs = {
        member.source.recipe.ref.identity_key
        for roster in AUTHORED_ROSTER_RECIPES
        for member in roster.members
        if isinstance(member.source, AuthoredCreatureRosterSource)
    }
    assert {
        recipe.ref.identity_key
        for recipe in PLAYABLE_SRD_CREATURE_RECIPES_BY_ID.values()
    } <= represented_refs


def test_rosters_do_not_repair_ordinary_apparel_as_setup_effects() -> None:
    """Creature/class roots own their normal wardrobe and visual identity."""
    forbidden_prefixes = ("apparel.", "armor.cloth")
    repairs = [
        (
            roster.roster_id,
            member.member_id,
            effect.recipe.ref.content_id,
        )
        for roster in AUTHORED_ROSTER_RECIPES
        for member in roster.members
        for effect in member.scenario_setup_effects
        if isinstance(effect, RosterItemGrant)
        and effect.recipe.ref.content_id.startswith(forbidden_prefixes)
    ]
    assert repairs == []


def test_scenario_item_grants_are_real_tactical_setup_not_wardrobes() -> None:
    granted_ids = {
        effect.recipe.ref.content_id
        for roster in AUTHORED_ROSTER_RECIPES
        for member in roster.members
        for effect in member.scenario_setup_effects
        if isinstance(effect, RosterItemGrant)
    }
    assert {
        "equipment.portable_torch",
        "consumable.healing_potion",
        "spell_item.scroll_fireball",
        "weapon.longbow",
    } <= granted_ids
    assert all(
        not content_id.startswith(("apparel.", "armor.cloth"))
        for content_id in granted_ids
    )
