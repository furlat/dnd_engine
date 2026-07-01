"""
Test that spell attack crits correctly double dice (not quadruple).

The bug: spells were manually doubling dice_numbers THEN passing attack_outcome=CRIT
to get_dice(), which doubles again inside Dice._roll(). Result: 4x dice on crit instead of 2x.

Fix: pass un-doubled dice_numbers and let get_dice(attack_outcome=outcome, crit_extra_dice=extra)
handle all crit doubling.

Tests all 7 spell attack types: Fire Bolt, Ray of Frost, Scorching Ray, Shocking Grasp,
Guiding Bolt, Eldritch Blast, Chill Touch.
"""
from uuid import uuid4
from typing import Tuple

# Reset state FIRST
from dnd.utils import reset_combat_state
reset_combat_state()

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.dice import DiceRoll
from dnd.core.events import RollType
from dnd.core.gridmap import get_map

from dnd.spells.evocation import (
    FireBolt, RayOfFrost, ScorchingRay, ShockingGrasp, GuidingBolt, EldritchBlast,
)
from dnd.spells.necromancy import ChillTouch

from dnd.utils import (
    set_hp, force_spell_attack_hit, force_spell_attack_crit,
    remove_spell_attack_modifier, setup_combat_arena,
)
from dnd.actions_functional import setup_standard_actions, register_spell


def create_caster(
    name: str = "Caster",
    position: Tuple[int, int] = (0, 0),
    faction: str = "heroes",
    hp: int = 200,
) -> Entity:
    """Create a spellcaster with CHA-based casting."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            charisma=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=20, mode="maximums")]
        ),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3, 3: 2}
        ),
        spellcasting=SpellcastingConfig(spellcasting_ability="charisma"),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config,
    )
    set_hp(entity, hp)
    setup_standard_actions(entity)
    return entity


def create_target(
    name: str = "Target",
    position: Tuple[int, int] = (1, 0),
    faction: str = "monsters",
    hp: int = 500,
) -> Entity:
    """Create a high-HP target."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=50, mode="maximums")]
        ),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config,
    )
    set_hp(entity, hp)
    setup_standard_actions(entity)
    return entity


def setup_arena():
    """Create a walkable arena."""
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)
    return grid


def get_damage_dice_count() -> int:
    """Find the most recent DAMAGE DiceRoll and return its dice count."""
    damage_rolls = [
        dr for dr in DiceRoll._registry.values()
        if dr.roll_type == RollType.DAMAGE
    ]
    assert damage_rolls, "No damage rolls found!"
    results = damage_rolls[-1].results
    assert isinstance(results, list), f"Expected list results, got {type(results)}"
    return len(results)


def clear_dice_registry():
    """Clear DiceRoll registry between tests."""
    DiceRoll._registry.clear()


# ============================================================================
# Tests
# ============================================================================

passed = 0
failed = 0


def run_spell_crit_test(
    spell_class: type,
    spell_name: str,
    expected_base_dice: int,
    expected_crit_dice: int,
    caster_level: int = 1,
    target_distance: int = 1,
):
    """Generic test for spell crit dice count."""
    global passed, failed

    reset_combat_state()
    setup_arena()

    caster = create_caster(position=(0, 0))
    target = create_target(position=(target_distance, 0))
    register_spell(caster, spell_class, caster_level=caster_level)

    encounter = setup_combat_arena(caster, target)
    encounter.start_encounter()
    encounter.start_turn()

    # Force hit + crit (AUTOHIT prevents nat-1 misses, AUTOCRIT upgrades to crit)
    hit_mod = force_spell_attack_hit(caster)
    crit_mod = force_spell_attack_crit(caster)

    # Clear dice registry to isolate our spell's damage roll
    clear_dice_registry()

    # Cast the spell
    spell = spell_class(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=caster_level,
    )
    spell.apply()

    # Remove modifiers
    remove_spell_attack_modifier(caster, hit_mod)
    remove_spell_attack_modifier(caster, crit_mod)

    # Find the damage roll
    damage_rolls = [
        dr for dr in DiceRoll._registry.values()
        if dr.roll_type == RollType.DAMAGE
    ]

    if not damage_rolls:
        print(f"  FAIL {spell_name}: No damage roll found (spell may have missed)")
        failed += 1
        return

    results = damage_rolls[-1].results
    assert isinstance(results, list), f"Expected list results for {spell_name}"
    actual_dice = len(results)

    if actual_dice == expected_crit_dice:
        print(f"  PASS {spell_name}: crit rolled {actual_dice} dice (correct: {expected_base_dice}x2)")
        passed += 1
    else:
        print(f"  FAIL {spell_name}: crit rolled {actual_dice} dice, expected {expected_crit_dice} (base {expected_base_dice} x2)")
        if actual_dice == expected_base_dice * 4:
            print(f"       ^ BUG: double-doubling detected ({expected_base_dice}x4 = {actual_dice})")
        failed += 1


def test_cantrip_crit_dice_level1():
    """Test cantrip crit dice at level 1 (1 base die)."""
    print("\n=== Test: Cantrip Crit Dice (Level 1) ===")

    # Fire Bolt: 1d10 -> crit 2d10
    run_spell_crit_test(FireBolt, "Fire Bolt L1", expected_base_dice=1, expected_crit_dice=2, caster_level=1)

    # Ray of Frost: 1d8 -> crit 2d8
    run_spell_crit_test(RayOfFrost, "Ray of Frost L1", expected_base_dice=1, expected_crit_dice=2, caster_level=1)

    # Shocking Grasp: 1d8 -> crit 2d8
    run_spell_crit_test(ShockingGrasp, "Shocking Grasp L1", expected_base_dice=1, expected_crit_dice=2, caster_level=1)

    # Eldritch Blast: 1d10 -> crit 2d10
    run_spell_crit_test(EldritchBlast, "Eldritch Blast L1", expected_base_dice=1, expected_crit_dice=2, caster_level=1)

    # Chill Touch: 1d8 -> crit 2d8
    run_spell_crit_test(ChillTouch, "Chill Touch L1", expected_base_dice=1, expected_crit_dice=2, caster_level=1)


def test_cantrip_crit_dice_level5():
    """Test cantrip crit dice at level 5 (2 base dice)."""
    print("\n=== Test: Cantrip Crit Dice (Level 5) ===")

    # Fire Bolt: 2d10 -> crit 4d10
    run_spell_crit_test(FireBolt, "Fire Bolt L5", expected_base_dice=2, expected_crit_dice=4, caster_level=5)

    # Eldritch Blast: 2d10 -> crit 4d10
    run_spell_crit_test(EldritchBlast, "Eldritch Blast L5", expected_base_dice=2, expected_crit_dice=4, caster_level=5)

    # Ray of Frost: 2d8 -> crit 4d8
    run_spell_crit_test(RayOfFrost, "Ray of Frost L5", expected_base_dice=2, expected_crit_dice=4, caster_level=5)

    # Chill Touch: 2d8 -> crit 4d8
    run_spell_crit_test(ChillTouch, "Chill Touch L5", expected_base_dice=2, expected_crit_dice=4, caster_level=5)


def test_leveled_spell_crit_dice():
    """Test leveled spell attack crit dice."""
    print("\n=== Test: Leveled Spell Crit Dice ===")

    # Scorching Ray: 2d6 per ray -> crit 4d6 per ray
    run_spell_crit_test(ScorchingRay, "Scorching Ray", expected_base_dice=2, expected_crit_dice=4, caster_level=5)

    # Guiding Bolt: 4d6 at level 1 -> crit 8d6
    run_spell_crit_test(GuidingBolt, "Guiding Bolt L1", expected_base_dice=4, expected_crit_dice=8, caster_level=5)


# ============================================================================
# Run
# ============================================================================

if __name__ == "__main__":
    test_cantrip_crit_dice_level1()
    test_cantrip_crit_dice_level5()
    test_leveled_spell_crit_dice()

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("ALL SPELL CRIT DICE TESTS PASSED!")
    else:
        print(f"FAILURES: {failed} tests need attention")
        exit(1)
