"""Authored scenarios retain their specialized characters after factory retirement."""

import pytest

from dnd.core.equipment_types import WeaponSlot
from dnd.scenarios.encounter_catalog import roster_recipe
from tests.engine.authored_character_support import prepare_roster_member


@pytest.mark.parametrize(
    "roster_id,member_id,main_hand,off_hand,ranged,style,asi_ability",
    (
        ("hero.fighter_l5_archer_torch", "hero", "Shortsword", None, "Longbow", "Archery", "dexterity"),
        ("hero.fighter_l5_shield_torch", "hero", "Longsword", "Shield", "Longbow", "Dueling", "strength"),
        ("hero.fighter_l5_great_weapon", "hero", "Greatsword", None, None, "Great Weapon Fighting", "strength"),
        ("hero.fighter_l5_defense", "hero", "Greatsword", None, None, "Defense", "strength"),
        ("hero.fighter_l5_two_weapon", "hero", "Shortsword", "Shortsword", None, "Two-Weapon Fighting", "strength"),
        ("monsters.berserker_duelist", "monster_1", "Greataxe", None, None, None, "strength"),
        ("hero.barbarian_l5_dual_axes", "hero", "Handaxe", "Handaxe", None, None, "strength"),
        ("hero.barbarian_l5_sword_shield", "hero", "Longsword", "Shield", None, None, "strength"),
    ),
)
def test_specialized_martial_loadouts_and_progression(
    roster_id, member_id, main_hand, off_hand, ranged, style, asi_ability,
) -> None:
    actor = prepare_roster_member(roster_recipe(roster_id), member_id)
    assert len(actor.applied_class_levels) == 5
    for slot, expected in (
        (WeaponSlot.MELEE_MAIN, main_hand),
        (WeaponSlot.MELEE_OFF, off_hand),
        (WeaponSlot.RANGED_MAIN, ranged),
    ):
        item = actor.equipment.get_item_by_slot(slot)
        assert (item.name if item is not None else None) == expected
    if style == "Archery":
        assert actor.equipment.ranged_attack_bonus.normalized_score == 2
    elif style == "Defense":
        assert actor.equipment.ac_bonus.normalized_score == 1
    elif style == "Dueling":
        assert actor.equipment.melee_damage_bonus.normalized_score == 2
    elif style == "Two-Weapon Fighting":
        assert actor.equipment.off_hand_melee_ability_bonus.normalized_score == 4
    elif style == "Great Weapon Fighting":
        assert actor.get_event_handler_by_name("Great Weapon Fighting") is not None
    assert actor.ability_scores.get_ability(asi_ability).ability_score.score == (
        16 if asi_ability == "dexterity" else 19
    )


@pytest.mark.parametrize(
    "roster_id,member_id,level,required,forbidden",
    (
        ("hero.sorcerer_l5_standard_torch", "hero", 5,
         {"Thunderwave", "Hold Person", "Fireball"}, set()),
        ("hero.sorcerer_l9_standard_torch", "hero", 9,
         {"Banishment", "Greater Invisibility", "Cone of Cold"}, set()),
        ("hero.sorcerer_l5_projectile_only", "hero", 5,
         {"Fire Bolt", "Ray of Frost", "Magic Missile", "Scorching Ray"},
         {"Fireball", "Lightning Bolt", "Hold Person"}),
        ("monsters.class_mirror_party", "monster_3", 5,
         {"Fireball", "Lightning Bolt", "Slow", "Haste"}, set()),
        ("monsters.concentration_crossroads_cell", "monster_2", 5,
         {"Web", "Hypnotic Pattern", "Slow", "Fireball"}, set()),
        ("monsters.condition_lock_cell", "monster_2", 7,
         {"Command", "Hold Person", "Fear", "Hypnotic Pattern", "Slow", "Banishment"}, set()),
    ),
)
def test_specialized_casters_keep_levels_slots_and_spell_surface(
    roster_id, member_id, level, required, forbidden,
) -> None:
    actor = prepare_roster_member(roster_recipe(roster_id), member_id)
    assert len(actor.applied_class_levels) == level
    names = {action.name for action in actor.registered_actions}
    assert required <= names
    assert not forbidden & names
    assert actor.action_economy.spell_slot_value((level + 1) // 2).normalized_score > 0
    if level == 9:
        assert actor.ability_scores.get_ability("dexterity").ability_score.score == 16
