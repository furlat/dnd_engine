"""Canonical authored roster identity and content coverage."""

from __future__ import annotations

from dnd.content.monsters.srd_monster_definitions import SRD_MONSTER_DEFINITIONS
from dnd.content.scenarios.scenario_catalog import (
    AUTHORED_ROSTERS,
    roster_definition,
)
from dnd.content.scenarios.scenario_definitions import RosterItemGrant


def test_roster_catalog_has_exact_audited_counts_and_unique_identity() -> None:
    assert len(AUTHORED_ROSTERS) == 58
    assert sum(len(row.members) for row in AUTHORED_ROSTERS) == 141
    assert len({
        row.roster_id for row in AUTHORED_ROSTERS
    }) == 58
    assert all(
        roster_definition(row.roster_id) is row
        for row in AUTHORED_ROSTERS
    )


def test_every_authored_member_has_an_exact_creature_recipe() -> None:
    for roster in AUTHORED_ROSTERS:
        for member in roster.members:
            assert member.source.kind == "entity"
            assert member.source.entity_id


def test_every_srd_creature_factory_is_represented_in_a_roster() -> None:
    represented_ids = {
        member.source.entity_id
        for roster in AUTHORED_ROSTERS
        for member in roster.members
    }
    assert set(SRD_MONSTER_DEFINITIONS) <= represented_ids


def test_rosters_do_not_repair_ordinary_apparel_as_setup_effects() -> None:
    """Creature/class roots own their normal wardrobe and visual identity."""
    forbidden_prefixes = ("apparel.", "armor.cloth")
    repairs = [
        (
            roster.roster_id,
            member.member_id,
            effect.item_id,
        )
        for roster in AUTHORED_ROSTERS
        for member in roster.members
        for effect in member.scenario_setup_effects
        if isinstance(effect, RosterItemGrant)
        and effect.item_id.startswith(forbidden_prefixes)
    ]
    assert repairs == []


def test_scenario_item_grants_are_real_tactical_setup_not_wardrobes() -> None:
    granted_ids = {
        effect.item_id
        for roster in AUTHORED_ROSTERS
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
