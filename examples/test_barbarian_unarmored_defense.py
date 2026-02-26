"""
Test Barbarian Unarmored Defense

Tests:
1. Unarmored Defense adds CON modifier to AC when not wearing armor
2. Wearing armor disables Unarmored Defense (uses armor AC instead)
3. Shields still work with Unarmored Defense (+2 AC)
4. Removing armor re-enables Unarmored Defense
5. Different CON scores produce correct AC values
"""

from uuid import uuid4

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import EquipmentConfig, UnarmoredAc
from dnd.core.events import BodyPart
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.core.events import WeaponSlot
from dnd.core.gridmap import get_map
from dnd.utils import reset_combat_state
from dnd.actions_functional import setup_standard_actions
from dnd.items.weapons import create_greataxe
from dnd.items.armors import create_leather_armor, create_chain_shirt, create_shield, create_cloth_armor


def create_test_barbarian(
    name: str = "Test Barbarian",
    position: tuple = (0, 0),
    dex_score: int = 14,
    con_score: int = 16
) -> Entity:
    """Create a simple barbarian for testing Unarmored Defense."""
    source_id = uuid4()

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=dex_score),
            constitution=AbilityConfig(ability_score=con_score),
            intelligence=AbilityConfig(ability_score=8),
            wisdom=AbilityConfig(ability_score=12),
            charisma=AbilityConfig(ability_score=10)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=12,
            hit_dice_count=1,
            mode="average"
        )]),
        equipment=EquipmentConfig(unarmored_ac_type=UnarmoredAc.BARBARIAN),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        config=config
    )

    setup_standard_actions(entity)

    # Equip weapon but no armor
    axe = create_greataxe(entity.uuid)
    entity.equipment.equip(axe, WeaponSlot.MELEE_MAIN)

    return entity


def test_unarmored_defense_basic():
    """Test that Unarmored Defense adds CON modifier to AC."""
    print("\n=== Test: Unarmored Defense Basic ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    # DEX 14 (+2), CON 16 (+3)
    barbarian = create_test_barbarian(dex_score=14, con_score=16)

    # AC should be 10 + DEX + CON = 10 + 2 + 3 = 15 from creation
    ac = barbarian.ac_bonus().normalized_score
    con_mod = barbarian.ability_scores.constitution.modifier
    dex_mod = barbarian.ability_scores.dexterity.modifier
    expected_ac = 10 + dex_mod + con_mod

    print(f"  DEX modifier: +{dex_mod}")
    print(f"  CON modifier: +{con_mod}")
    print(f"  AC with Unarmored Defense: {ac}")
    print(f"  Expected: 10 + {dex_mod} + {con_mod} = {expected_ac}")

    assert ac == expected_ac, f"Expected AC {expected_ac}, got {ac}"
    print("  [PASS] Unarmored Defense correctly adds CON modifier")


def test_unarmored_defense_disabled_by_armor():
    """Test that wearing armor disables Unarmored Defense."""
    print("\n=== Test: Armor Disables Unarmored Defense ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    # DEX 14 (+2), CON 16 (+3)
    barbarian = create_test_barbarian(dex_score=14, con_score=16)

    # AC with Unarmored Defense: 10 + 2 + 3 = 15
    unarmored_ac = barbarian.ac_bonus().normalized_score
    print(f"  AC with Unarmored Defense: {unarmored_ac}")
    assert unarmored_ac == 15, f"Expected unarmored AC 15, got {unarmored_ac}"

    # Equip leather armor (AC 11 + DEX)
    leather = create_leather_armor(barbarian.uuid)
    barbarian.equipment.equip(leather)

    # AC should now be armor-based: 11 + DEX = 11 + 2 = 13
    # Unarmored Defense should NOT apply (leather armor is worse than unarmored!)
    armored_ac = barbarian.ac_bonus().normalized_score
    print(f"  AC with Leather Armor: {armored_ac}")
    print(f"  (Leather: 11 + DEX 2 = 13, Unarmored would be 15)")

    # The armor AC is 13, but Unarmored Defense is contextual and returns None when armored
    # So we get armor AC, not unarmored AC
    assert armored_ac == 13, f"Expected armored AC 13, got {armored_ac}"
    assert armored_ac < unarmored_ac, "Wearing armor should disable Unarmored Defense"
    print("  [PASS] Armor correctly disables Unarmored Defense")


def test_unarmored_defense_with_shield():
    """Test that shields work with Unarmored Defense."""
    print("\n=== Test: Shield Works With Unarmored Defense ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    # DEX 14 (+2), CON 16 (+3)
    barbarian = create_test_barbarian(dex_score=14, con_score=16)

    # AC with Unarmored Defense: 10 + 2 + 3 = 15
    unarmored_ac = barbarian.ac_bonus().normalized_score
    print(f"  AC with Unarmored Defense (no shield): {unarmored_ac}")
    assert unarmored_ac == 15, f"Expected unarmored AC 15, got {unarmored_ac}"

    # Equip shield (+2 AC)
    shield = create_shield(barbarian.uuid)
    barbarian.equipment.equip(shield, WeaponSlot.MELEE_OFF)

    # AC should now be: 10 + DEX + CON + Shield = 10 + 2 + 3 + 2 = 17
    shielded_ac = barbarian.ac_bonus().normalized_score
    print(f"  AC with Unarmored Defense + Shield: {shielded_ac}")
    print(f"  Expected: 10 + DEX 2 + CON 3 + Shield 2 = 17")

    assert shielded_ac == 17, f"Expected shielded AC 17, got {shielded_ac}"
    print("  [PASS] Shield correctly stacks with Unarmored Defense")


def test_removing_armor_restores_unarmored():
    """Test that removing armor re-enables Unarmored Defense."""
    print("\n=== Test: Removing Armor Restores Unarmored Defense ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    # DEX 14 (+2), CON 16 (+3)
    barbarian = create_test_barbarian(dex_score=14, con_score=16)

    initial_ac = barbarian.ac_bonus().normalized_score
    print(f"  Initial AC (Unarmored): {initial_ac}")
    assert initial_ac == 15

    # Equip chain shirt (AC 13 + DEX max 2)
    chain_shirt = create_chain_shirt(barbarian.uuid)
    barbarian.equipment.equip(chain_shirt)

    armored_ac = barbarian.ac_bonus().normalized_score
    print(f"  AC with Chain Shirt: {armored_ac}")
    # Chain shirt: 13 + min(DEX, 2) = 13 + 2 = 15
    assert armored_ac == 15, f"Expected chain shirt AC 15, got {armored_ac}"

    # Remove armor
    barbarian.equipment.unequip(BodyPart.BODY)

    restored_ac = barbarian.ac_bonus().normalized_score
    print(f"  AC after removing armor: {restored_ac}")

    assert restored_ac == initial_ac, f"Expected restored AC {initial_ac}, got {restored_ac}"
    print("  [PASS] Removing armor correctly restores Unarmored Defense")


def test_unarmored_defense_high_con():
    """Test Unarmored Defense with high CON score."""
    print("\n=== Test: High CON Unarmored Defense ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    # DEX 16 (+3), CON 20 (+5) - like a high-level barbarian
    barbarian = create_test_barbarian(dex_score=16, con_score=20)

    # AC should be: 10 + DEX + CON = 10 + 3 + 5 = 18
    ac = barbarian.ac_bonus().normalized_score
    dex_mod = barbarian.ability_scores.dexterity.modifier
    con_mod = barbarian.ability_scores.constitution.modifier
    expected_ac = 10 + dex_mod + con_mod

    print(f"  DEX 16 (+{dex_mod}), CON 20 (+{con_mod})")
    print(f"  AC: {ac}")
    print(f"  Expected: 10 + {dex_mod} + {con_mod} = {expected_ac}")

    assert ac == expected_ac, f"Expected AC {expected_ac}, got {ac}"
    print("  [PASS] High CON Unarmored Defense works correctly")


def test_unarmored_defense_low_con():
    """Test Unarmored Defense with low CON score."""
    print("\n=== Test: Low CON Unarmored Defense ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    # DEX 14 (+2), CON 10 (+0)
    barbarian = create_test_barbarian(dex_score=14, con_score=10)

    # AC should be: 10 + DEX + CON = 10 + 2 + 0 = 12
    ac = barbarian.ac_bonus().normalized_score
    con_mod = barbarian.ability_scores.constitution.modifier

    print(f"  CON modifier: +{con_mod}")
    print(f"  AC with Unarmored Defense: {ac}")

    # With +0 CON, Unarmored Defense provides no benefit over base
    expected_ac = 10 + 2 + 0  # 12
    assert ac == expected_ac, f"Expected AC {expected_ac}, got {ac}"
    print("  [PASS] Low CON Unarmored Defense correctly provides no bonus")


def test_unarmored_defense_with_cloth_armor():
    """Test that cloth armor doesn't disable Unarmored Defense."""
    print("\n=== Test: Cloth Armor Allows Unarmored Defense ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    # DEX 14 (+2), CON 16 (+3)
    barbarian = create_test_barbarian(dex_score=14, con_score=16)

    # AC with Unarmored Defense: 10 + 2 + 3 = 15
    unarmored_ac = barbarian.ac_bonus().normalized_score
    print(f"  AC with Unarmored Defense (no armor): {unarmored_ac}")
    assert unarmored_ac == 15, f"Expected unarmored AC 15, got {unarmored_ac}"

    # Equip cloth armor (should NOT disable Unarmored Defense)
    cloth = create_cloth_armor(barbarian.uuid)
    barbarian.equipment.equip(cloth)

    # AC should STILL be unarmored: 10 + DEX + CON = 15
    cloth_ac = barbarian.ac_bonus().normalized_score
    print(f"  AC with Cloth Armor: {cloth_ac}")
    print(f"  (Cloth counts as unarmored, so CON bonus still applies)")

    assert cloth_ac == unarmored_ac, f"Expected cloth AC {unarmored_ac}, got {cloth_ac}"
    print("  [PASS] Cloth armor correctly allows Unarmored Defense")


if __name__ == "__main__":
    print("=" * 60)
    print("BARBARIAN UNARMORED DEFENSE TESTS")
    print("=" * 60)

    test_unarmored_defense_basic()
    test_unarmored_defense_disabled_by_armor()
    test_unarmored_defense_with_shield()
    test_removing_armor_restores_unarmored()
    test_unarmored_defense_high_con()
    test_unarmored_defense_low_con()
    test_unarmored_defense_with_cloth_armor()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
