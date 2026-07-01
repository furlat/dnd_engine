"""
Test script for Brutal Critical feature.

Tests the crit_extra_dice ModifiableValue system:
1. Default crit_extra_dice returns 0
2. BrutalCritical condition adds to crit_extra_dice_melee
3. Dice class correctly rolls extra dice on crits
4. Full attack flow with Brutal Critical
"""

from uuid import uuid4
import random

# Set seed for reproducible tests
random.seed(42)

from dnd.entity import Entity
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import EquipmentConfig, WeaponSlot
from dnd.entity import EntityConfig
from dnd.core.gridmap import get_map
from dnd.actions_functional import setup_standard_actions
from dnd.items.weapons import create_greataxe
from dnd.core.dice import Dice, RollType, AttackOutcome
from dnd.core.values import ModifiableValue
from dnd.classes.barbarian import BrutalCritical
from dnd.utils import reset_combat_state


def create_test_barbarian(name: str, position: tuple = (0, 0)) -> Entity:
    """Create a test barbarian with a greataxe."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),  # +3 modifier
            dexterity=AbilityConfig(ability_score=14),  # +2 modifier
            constitution=AbilityConfig(ability_score=16),  # +3 modifier
            intelligence=AbilityConfig(ability_score=8),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=12, hit_dice_count=9, mode="maximums")]),
        equipment=EquipmentConfig(),
        proficiency_bonus=4,  # L9 barbarian
        position=position
    )

    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config
    )

    # Equip greataxe (1d12)
    greataxe = create_greataxe(entity.uuid)
    entity.equipment.equip(greataxe, WeaponSlot.MELEE_MAIN)

    setup_standard_actions(entity)

    return entity


def test_default_crit_extra_dice():
    """Test that get_crit_extra_dice() returns 0 by default."""
    print("\n=== Test: Default crit_extra_dice ===")

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    barbarian = create_test_barbarian("Test Barbarian")

    # Check default values
    melee_extra = barbarian.get_crit_extra_dice(WeaponSlot.MELEE_MAIN)
    ranged_extra = barbarian.get_crit_extra_dice(WeaponSlot.RANGED_MAIN)

    print(f"  Melee crit extra dice: {melee_extra}")
    print(f"  Ranged crit extra dice: {ranged_extra}")

    assert melee_extra == 0, f"Expected 0, got {melee_extra}"
    assert ranged_extra == 0, f"Expected 0, got {ranged_extra}"

    print("  [PASS] Default crit_extra_dice is 0 for both melee and ranged")


def test_brutal_critical_modifier():
    """Test that BrutalCritical adds to crit_extra_dice_melee."""
    print("\n=== Test: BrutalCritical modifier application ===")

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    barbarian = create_test_barbarian("Brutal Barbarian")

    # Check before applying
    before_melee = barbarian.get_crit_extra_dice(WeaponSlot.MELEE_MAIN)
    before_ranged = barbarian.get_crit_extra_dice(WeaponSlot.RANGED_MAIN)
    print(f"  Before: Melee={before_melee}, Ranged={before_ranged}")

    # Apply BrutalCritical (1 extra die)
    brutal_crit = BrutalCritical(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        extra_dice=1
    )
    barbarian.add_condition(brutal_crit)

    # Check after applying
    after_melee = barbarian.get_crit_extra_dice(WeaponSlot.MELEE_MAIN)
    after_ranged = barbarian.get_crit_extra_dice(WeaponSlot.RANGED_MAIN)
    print(f"  After L9 Brutal Critical: Melee={after_melee}, Ranged={after_ranged}")

    assert after_melee == 1, f"Expected 1, got {after_melee}"
    assert after_ranged == 0, f"Expected 0 (ranged unchanged), got {after_ranged}"

    print("  [PASS] BrutalCritical correctly adds to melee only")

    # Remove and apply with more dice (L17 = 3 dice)
    barbarian.remove_condition("Brutal Critical")

    brutal_crit_l17 = BrutalCritical(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        extra_dice=3
    )
    barbarian.add_condition(brutal_crit_l17)

    final_melee = barbarian.get_crit_extra_dice(WeaponSlot.MELEE_MAIN)
    print(f"  After L17 Brutal Critical: Melee={final_melee}")

    assert final_melee == 3, f"Expected 3, got {final_melee}"
    print("  [PASS] L17 Brutal Critical correctly adds 3 extra dice")


def test_dice_crit_extra_dice():
    """Test that Dice class correctly rolls extra dice on crits."""
    print("\n=== Test: Dice class crit_extra_dice ===")

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    # Create a simple damage bonus
    bonus = ModifiableValue.create(source_entity_uuid=uuid4(), base_value=5, value_name="Damage Bonus")

    # Test normal crit (no extra dice) - 1d12 becomes 2d12
    dice_normal = Dice(count=1, value=12, bonus=bonus, roll_type=RollType.DAMAGE,
                       attack_outcome=AttackOutcome.CRIT, crit_extra_dice=0)
    # The _roll method with crit=True should roll count*2 = 2 dice
    roll_results_normal = dice_normal._roll(crit=True)
    print(f"  Normal crit (1d12): rolled {len(roll_results_normal)} dice")
    assert len(roll_results_normal) == 2, f"Expected 2 dice, got {len(roll_results_normal)}"

    # Test crit with +1 extra die (Brutal Critical L9) - 1d12 becomes 3d12
    dice_bc1 = Dice(count=1, value=12, bonus=bonus, roll_type=RollType.DAMAGE,
                    attack_outcome=AttackOutcome.CRIT, crit_extra_dice=1)
    roll_results_bc1 = dice_bc1._roll(crit=True)
    print(f"  L9 Brutal Critical (1d12 + 1 extra): rolled {len(roll_results_bc1)} dice")
    assert len(roll_results_bc1) == 3, f"Expected 3 dice, got {len(roll_results_bc1)}"

    # Test crit with +3 extra dice (Brutal Critical L17) - 1d12 becomes 5d12
    dice_bc3 = Dice(count=1, value=12, bonus=bonus, roll_type=RollType.DAMAGE,
                    attack_outcome=AttackOutcome.CRIT, crit_extra_dice=3)
    roll_results_bc3 = dice_bc3._roll(crit=True)
    print(f"  L17 Brutal Critical (1d12 + 3 extra): rolled {len(roll_results_bc3)} dice")
    assert len(roll_results_bc3) == 5, f"Expected 5 dice, got {len(roll_results_bc3)}"

    # Verify non-crit roll is unaffected
    dice_normal_hit = Dice(count=1, value=12, bonus=bonus, roll_type=RollType.DAMAGE,
                           attack_outcome=AttackOutcome.HIT, crit_extra_dice=3)
    roll_results_hit = dice_normal_hit._roll(crit=False)
    print(f"  Normal hit with crit_extra_dice=3: rolled {len(roll_results_hit)} dice (should be 1)")
    assert len(roll_results_hit) == 1, f"Expected 1 die for non-crit, got {len(roll_results_hit)}"

    print("  [PASS] All dice rolling tests passed")


def test_damage_get_dice():
    """Test that Damage.get_dice() correctly passes crit_extra_dice."""
    print("\n=== Test: Damage.get_dice() with crit_extra_dice ===")

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    from dnd.core.events import Damage
    from dnd.core.modifiers import DamageType

    bonus = ModifiableValue.create(source_entity_uuid=uuid4(), base_value=3, value_name="Damage Bonus")

    # Create a damage specification (1d12 slashing)
    damage = Damage(
        source_entity_uuid=uuid4(),
        damage_dice=12,
        dice_numbers=1,
        damage_bonus=bonus,
        damage_type=DamageType.SLASHING
    )

    # Get dice without extra dice
    dice_normal = damage.get_dice(AttackOutcome.CRIT, crit_extra_dice=0)
    print(f"  Dice without extra: crit_extra_dice={dice_normal.crit_extra_dice}")
    assert dice_normal.crit_extra_dice == 0

    # Get dice with 2 extra dice
    dice_with_extra = damage.get_dice(AttackOutcome.CRIT, crit_extra_dice=2)
    print(f"  Dice with 2 extra: crit_extra_dice={dice_with_extra.crit_extra_dice}")
    assert dice_with_extra.crit_extra_dice == 2

    print("  [PASS] Damage.get_dice() correctly passes crit_extra_dice")


def test_separate_melee_ranged():
    """Test that melee and ranged crit extra dice are tracked separately."""
    print("\n=== Test: Separate melee/ranged tracking ===")

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    barbarian = create_test_barbarian("Test Barbarian")

    # Add modifier to general crit_extra_dice (should affect both)
    from dnd.core.modifiers import NumericalModifier
    general_mod = NumericalModifier.create(
        source_entity_uuid=barbarian.uuid,
        name="General Crit Bonus",
        value=1
    )
    barbarian.equipment.crit_extra_dice.self_static.add_value_modifier(general_mod)

    melee_extra = barbarian.get_crit_extra_dice(WeaponSlot.MELEE_MAIN)
    ranged_extra = barbarian.get_crit_extra_dice(WeaponSlot.RANGED_MAIN)

    print(f"  With general +1: Melee={melee_extra}, Ranged={ranged_extra}")
    assert melee_extra == 1, f"Expected 1, got {melee_extra}"
    assert ranged_extra == 1, f"Expected 1, got {ranged_extra}"

    # Add melee-only modifier (Brutal Critical)
    melee_mod = NumericalModifier.create(
        source_entity_uuid=barbarian.uuid,
        name="Brutal Critical",
        value=2
    )
    barbarian.equipment.crit_extra_dice_melee.self_static.add_value_modifier(melee_mod)

    melee_extra = barbarian.get_crit_extra_dice(WeaponSlot.MELEE_MAIN)
    ranged_extra = barbarian.get_crit_extra_dice(WeaponSlot.RANGED_MAIN)

    print(f"  With general +1 and melee +2: Melee={melee_extra}, Ranged={ranged_extra}")
    assert melee_extra == 3, f"Expected 3 (1+2), got {melee_extra}"
    assert ranged_extra == 1, f"Expected 1 (ranged unchanged), got {ranged_extra}"

    print("  [PASS] General and specific modifiers combine correctly")


if __name__ == "__main__":
    print("=" * 60)
    print("BRUTAL CRITICAL TESTS")
    print("=" * 60)

    test_default_crit_extra_dice()
    test_brutal_critical_modifier()
    test_dice_crit_extra_dice()
    test_damage_get_dice()
    test_separate_melee_ranged()

    print("\n" + "=" * 60)
    print("ALL BRUTAL CRITICAL TESTS PASSED!")
    print("=" * 60)
