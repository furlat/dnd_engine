"""
Test Magic Missile with MULTI_ENTITY target type.

Tests:
1. Single target (all darts to one enemy)
2. Split targets (darts distributed among multiple enemies)
3. Upcast with extra darts
4. Validation: enemies only filter
5. Validation: same target allowed

Run: python examples/test_magic_missile_multi.py
"""

from uuid import uuid4

# Reset state first
from dnd.utils import reset_combat_state, get_hp, set_hp
from dnd.core.gridmap import get_map
reset_combat_state()

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.spells.evocation import MagicMissile


def create_test_caster(name: str = "Caster", position: tuple = (0, 0)) -> Entity:
    """Create a caster with spell slots."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            intelligence=AbilityConfig(ability_score=16),  # +3 modifier
        ),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3, 3: 2},
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=5, mode="average")]),
        proficiency_bonus=2,
        position=position
    )

    return Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config
    )


def create_test_target(name: str = "Target", position: tuple = (5, 0), hp: int = 30, faction: str = "enemies") -> Entity:
    """Create a target entity with HP."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=5, mode="average")]),
        position=position,
        faction=faction
    )

    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config
    )
    # Optionally adjust HP if needed for specific test (already has ~22 HP from config)
    return entity


def test_single_target_all_darts():
    """Test that all 3 darts go to a single target when only one target specified."""
    print("\n=== Test 1: Single Target (All Darts) ===")

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)  # Create floor tiles for LOS
    caster = create_test_caster("Wizard", (0, 0))
    caster.faction = "heroes"
    target = create_test_target("Goblin", (5, 0), hp=30, faction="enemies")

    Entity.update_all_entities_senses(max_distance=20)

    initial_hp = get_hp(target)
    print(f"Target HP before: {initial_hp}")

    # Create spell with single target
    spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=1
    )

    # Check number of projectiles
    assert spell.get_num_projectiles() == 3, f"Expected 3 darts, got {spell.get_num_projectiles()}"

    # Check target list fills with primary
    targets = spell.get_all_targets()
    assert len(targets) == 3, f"Expected 3 targets (repeats), got {len(targets)}"
    assert all(t == target.uuid for t in targets), "All darts should target same enemy"

    # Execute spell
    result = spell.apply()
    assert result is not None, "Spell should execute"
    assert not result.canceled, f"Spell should not be canceled: {result.status_message}"

    final_hp = get_hp(target)
    damage_dealt = initial_hp - final_hp
    print(f"Target HP after: {final_hp}")
    print(f"Total damage: {damage_dealt}")

    # 3 darts * (1d4+1) = 3 * (2-5) = 6-15 damage
    assert damage_dealt >= 6, f"Expected at least 6 damage, got {damage_dealt}"
    assert damage_dealt <= 15, f"Expected at most 15 damage, got {damage_dealt}"

    # Check result aggregation
    assert result.total_targets == 3, f"Expected 3 target results, got {result.total_targets}"
    assert result.total_damage == damage_dealt, f"Expected total_damage={damage_dealt}, got {result.total_damage}"

    print(f"  All 3 darts hit single target for {damage_dealt} total damage")


def test_split_targets():
    """Test distributing darts among multiple targets."""
    print("\n=== Test 2: Split Targets ===")

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)  # Create floor tiles for LOS
    caster = create_test_caster("Wizard", (0, 0))
    caster.faction = "heroes"
    target1 = create_test_target("Goblin1", (5, 0), hp=30, faction="enemies")
    target2 = create_test_target("Goblin2", (5, 5), hp=30, faction="enemies")
    target3 = create_test_target("Goblin3", (0, 5), hp=30, faction="enemies")

    Entity.update_all_entities_senses(max_distance=20)

    hp1_before = get_hp(target1)
    hp2_before = get_hp(target2)
    hp3_before = get_hp(target3)

    # Create spell with all three as targets (1 dart each)
    spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target1.uuid,
        extra_target_entity_uuids=[target2.uuid, target3.uuid],
        cast_at_level=1
    )

    # Check target list
    targets = spell.get_all_targets()
    assert len(targets) == 3, f"Expected 3 targets, got {len(targets)}"
    assert targets[0] == target1.uuid
    assert targets[1] == target2.uuid
    assert targets[2] == target3.uuid

    # Execute
    result = spell.apply()
    assert result is not None, "Spell should execute"
    assert not result.canceled, f"Spell should not be canceled: {result.status_message}"

    hp1_after = get_hp(target1)
    hp2_after = get_hp(target2)
    hp3_after = get_hp(target3)

    dmg1 = hp1_before - hp1_after
    dmg2 = hp2_before - hp2_after
    dmg3 = hp3_before - hp3_after
    total = dmg1 + dmg2 + dmg3

    print(f"  Goblin1: {hp1_before} -> {hp1_after} ({dmg1} damage)")
    print(f"  Goblin2: {hp2_before} -> {hp2_after} ({dmg2} damage)")
    print(f"  Goblin3: {hp3_before} -> {hp3_after} ({dmg3} damage)")
    print(f"  Total: {total} damage across 3 targets")

    # Each dart does 1d4+1 = 2-5 damage
    assert dmg1 >= 2 and dmg1 <= 5, f"Dart 1 damage should be 2-5, got {dmg1}"
    assert dmg2 >= 2 and dmg2 <= 5, f"Dart 2 damage should be 2-5, got {dmg2}"
    assert dmg3 >= 2 and dmg3 <= 5, f"Dart 3 damage should be 2-5, got {dmg3}"
    assert result.total_targets == 3
    assert result.total_damage == total


def test_upcast_extra_darts():
    """Test upcasting adds extra darts."""
    print("\n=== Test 3: Upcast Extra Darts ===")

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)  # Create floor tiles for LOS
    caster = create_test_caster("Wizard", (0, 0))
    caster.faction = "heroes"
    target = create_test_target("Orc", (5, 0), hp=50, faction="enemies")

    Entity.update_all_entities_senses(max_distance=20)

    initial_hp = get_hp(target)

    # Cast at level 3 (base 1) = 2 extra darts = 5 total
    spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=3
    )

    assert spell.get_num_projectiles() == 5, f"Expected 5 darts at L3, got {spell.get_num_projectiles()}"

    targets = spell.get_all_targets()
    assert len(targets) == 5, f"Expected 5 target entries, got {len(targets)}"

    result = spell.apply()
    assert result is not None and not result.canceled

    final_hp = get_hp(target)
    damage = initial_hp - final_hp

    print(f"  5 darts (upcast L3) dealt {damage} damage")
    # 5 darts * (1d4+1) = 5 * (2-5) = 10-25 damage
    assert damage >= 10 and damage <= 25, f"Expected 10-25 damage, got {damage}"
    assert result.total_targets == 5


def test_validation_enemies_only():
    """Test that Magic Missile only allows enemy targets."""
    print("\n=== Test 4: Validation - Enemies Only ===")

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)  # Create floor tiles for LOS
    caster = create_test_caster("Wizard", (0, 0))
    caster.faction = "heroes"
    ally = create_test_target("Ally Fighter", (2, 0), hp=30, faction="heroes")

    Entity.update_all_entities_senses(max_distance=20)

    # Try to target ally
    spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=1
    )

    result = spell.apply()
    assert result is not None, "Should get result"
    assert result.canceled, "Spell should be canceled when targeting ally"
    assert "not an enemy" in result.status_message.lower() or "enemy" in result.status_message.lower(), \
        f"Expected enemy validation message, got: {result.status_message}"

    print(f"  Correctly rejected ally target: {result.status_message}")


def test_same_target_allowed():
    """Test that allow_same_target=True allows duplicates."""
    print("\n=== Test 5: Same Target Allowed ===")

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)  # Create floor tiles for LOS
    caster = create_test_caster("Wizard", (0, 0))
    caster.faction = "heroes"
    target = create_test_target("Goblin", (5, 0), hp=30, faction="enemies")

    Entity.update_all_entities_senses(max_distance=20)

    # Explicitly specify same target 3 times
    spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        extra_target_entity_uuids=[target.uuid, target.uuid],
        cast_at_level=1
    )

    assert spell.allow_same_target == True, "MagicMissile should allow same target"

    targets = spell.get_all_targets()
    assert len(targets) == 3, f"Expected 3 targets, got {len(targets)}"
    assert all(t == target.uuid for t in targets), "All should be same target"

    result = spell.apply()
    assert result is not None and not result.canceled, \
        f"Should allow same target repeated: {result.status_message if result else 'None'}"

    print(f"  Correctly allowed same target 3 times, dealt {result.total_damage} damage")


def run_all_tests():
    """Run all Magic Missile multi-target tests."""
    print("=" * 60)
    print("MAGIC MISSILE MULTI-ENTITY TESTS")
    print("=" * 60)

    test_single_target_all_darts()
    test_split_targets()
    test_upcast_extra_darts()
    test_validation_enemies_only()
    test_same_target_allowed()

    print("\n" + "=" * 60)
    print("ALL MAGIC MISSILE MULTI-ENTITY TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
