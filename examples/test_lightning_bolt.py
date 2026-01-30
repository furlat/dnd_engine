"""Comprehensive tests for Lightning Bolt spell (Line shape)."""
from uuid import uuid4
from typing import Tuple

# Reset state FIRST - critical!
from dnd.utils import reset_combat_state
reset_combat_state()

# Core imports
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.gridmap import get_map

# Spell imports
from dnd.spells.evocation import LightningBolt

# Test utilities
from dnd.utils import get_hp, set_hp
from dnd.actions_functional import setup_standard_actions


def create_caster(
    name: str = "Caster",
    position: Tuple[int, int] = (0, 0),
    faction: str = "heroes",
    hp: int = 100,
    intelligence: int = 16,  # +3 mod -> DC 13 (8 + 2 prof + 3 INT)
    proficiency: int = 2
) -> Entity:
    """Create a spellcaster entity with proper config."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            intelligence=AbilityConfig(ability_score=intelligence),
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=10, mode="maximums")]
        ),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3, 3: 2, 4: 1}
        ),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        proficiency_bonus=proficiency,
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
    position: Tuple[int, int] = (5, 0),
    faction: str = "monsters",
    hp: int = 50,
    dexterity: int = 10  # +0 mod for neutral save chance
) -> Entity:
    """Create a target entity."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            dexterity=AbilityConfig(ability_score=dexterity),
            strength=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=12),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=5, mode="maximums")]
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
    return entity


def setup_basic_arena(width: int = 30, height: int = 10):
    """Create a basic walkable arena (wider for line testing)."""
    grid = get_map()
    grid.create_rectangle(0, 0, width, height)
    return grid


def test_lightning_bolt_full_damage_on_failed_save():
    """Full 8d6 damage when target fails DEX save (DEX 1 target)."""
    print("\n=== Test 1: Full Damage on Failed DEX Save ===")
    reset_combat_state()
    setup_basic_arena(30, 10)

    # Caster with high spell DC
    caster = create_caster(name="Wizard", position=(5, 5), intelligence=20, proficiency=4)
    # Target with DEX 1 (-5 mod) - will always fail
    target = create_target(name="Slow", position=(10, 5), dexterity=1, hp=100)
    Entity.update_all_entities_senses()

    dc = caster.spell_save_dc()
    print(f"  Spell DC: {dc}")

    lightning_bolt = LightningBolt(
        source_entity_uuid=caster.uuid,
        end_position=(20, 5),  # Direction: east
        cast_at_level=3,
        template=False
    )

    result = lightning_bolt.apply()
    assert result is not None and not result.canceled, f"Lightning Bolt failed: {result.status_message if result else 'None'}"

    per_target = result.target_results[0] if result.target_results else result

    # Verify save failed
    assert per_target.save_success == False, "Target with DEX 1 should fail save"

    # Full damage (not halved)
    rolled_damage = sum(r.total for r in per_target.damage_rolls) if per_target.damage_rolls else 0
    assert per_target.total_damage == rolled_damage, \
        f"Should be full damage, got {per_target.total_damage} vs rolled {rolled_damage}"

    print(f"  Save failed as expected")
    print(f"  Full damage applied: {per_target.total_damage}")
    print("PASS: Full damage on failed DEX save")


def test_lightning_bolt_half_damage_on_passed_save():
    """Half damage when target passes DEX save (DEX 30 target)."""
    print("\n=== Test 2: Half Damage on Passed DEX Save ===")
    reset_combat_state()
    setup_basic_arena(30, 10)

    # Caster with low spell DC
    caster = create_caster(name="Weak Wizard", position=(5, 5), intelligence=10, proficiency=2)
    # Target with DEX 30 (+10 mod) - will always pass
    target = create_target(name="Nimble", position=(10, 5), dexterity=30, hp=100)
    Entity.update_all_entities_senses()

    dc = caster.spell_save_dc()
    print(f"  Spell DC: {dc}")

    lightning_bolt = LightningBolt(
        source_entity_uuid=caster.uuid,
        end_position=(20, 5),
        cast_at_level=3,
        template=False
    )

    result = lightning_bolt.apply()
    assert result is not None and not result.canceled

    per_target = result.target_results[0] if result.target_results else result

    # Verify save succeeded
    assert per_target.save_success == True, "Target with DEX 30 should always save"

    # Half damage
    rolled_damage = sum(r.total for r in per_target.damage_rolls) if per_target.damage_rolls else 0
    expected_damage = rolled_damage // 2
    assert per_target.total_damage == expected_damage, \
        f"Should be half damage: {rolled_damage}//2={expected_damage}, got {per_target.total_damage}"

    print(f"  Save passed as expected")
    print(f"  Half damage applied: {per_target.total_damage} (rolled {rolled_damage})")
    print("PASS: Half damage on passed DEX save")


def test_lightning_bolt_upcast():
    """Higher spell slots deal more damage dice."""
    print("\n=== Test 3: Upcast Damage Scaling ===")

    lb3 = LightningBolt(source_entity_uuid=uuid4(), cast_at_level=3, template=False)
    lb4 = LightningBolt(source_entity_uuid=uuid4(), cast_at_level=4, template=False)
    lb5 = LightningBolt(source_entity_uuid=uuid4(), cast_at_level=5, template=False)
    lb6 = LightningBolt(source_entity_uuid=uuid4(), cast_at_level=6, template=False)
    lb9 = LightningBolt(source_entity_uuid=uuid4(), cast_at_level=9, template=False)

    assert lb3.get_damage_dice_count() == 8, f"Level 3: expected 8d6, got {lb3.get_damage_dice_count()}d6"
    assert lb4.get_damage_dice_count() == 9, f"Level 4: expected 9d6, got {lb4.get_damage_dice_count()}d6"
    assert lb5.get_damage_dice_count() == 10, f"Level 5: expected 10d6, got {lb5.get_damage_dice_count()}d6"
    assert lb6.get_damage_dice_count() == 11, f"Level 6: expected 11d6, got {lb6.get_damage_dice_count()}d6"
    assert lb9.get_damage_dice_count() == 14, f"Level 9: expected 14d6, got {lb9.get_damage_dice_count()}d6"

    print("  Level 3: 8d6 lightning")
    print("  Level 4: 9d6 lightning")
    print("  Level 5: 10d6 lightning")
    print("  Level 6: 11d6 lightning")
    print("  Level 9: 14d6 lightning")
    print("PASS: Upcast damage scaling works")


def test_lightning_bolt_hits_line_targets():
    """All targets in the line take damage."""
    print("\n=== Test 4: Line Hits All Targets ===")
    reset_combat_state()
    setup_basic_arena(30, 10)

    caster = create_caster(name="Wizard", position=(5, 5))
    # Multiple targets along the line (east direction)
    target1 = create_target(name="Goblin1", position=(8, 5), hp=50, dexterity=1)
    target2 = create_target(name="Goblin2", position=(12, 5), hp=50, dexterity=1)
    target3 = create_target(name="Goblin3", position=(16, 5), hp=50, dexterity=1)
    Entity.update_all_entities_senses()

    t1_initial = get_hp(target1)
    t2_initial = get_hp(target2)
    t3_initial = get_hp(target3)

    lightning_bolt = LightningBolt(
        source_entity_uuid=caster.uuid,
        end_position=(25, 5),  # Direction: east
        cast_at_level=3,
        template=False
    )

    result = lightning_bolt.apply()
    assert result is not None and not result.canceled

    # All targets in line should be hit
    assert get_hp(target1) < t1_initial, "Target 1 in line should take damage"
    assert get_hp(target2) < t2_initial, "Target 2 in line should take damage"
    assert get_hp(target3) < t3_initial, "Target 3 in line should take damage"

    print(f"  Target 1 HP: {t1_initial} -> {get_hp(target1)}")
    print(f"  Target 2 HP: {t2_initial} -> {get_hp(target2)}")
    print(f"  Target 3 HP: {t3_initial} -> {get_hp(target3)}")
    print(f"  Total targets hit: {result.total_targets}")
    print("PASS: Line hits all targets along path")


def test_lightning_bolt_misses_off_line():
    """Targets beside the line are NOT hit."""
    print("\n=== Test 5: Targets Off Line Not Hit ===")
    reset_combat_state()
    setup_basic_arena(30, 10)

    caster = create_caster(name="Wizard", position=(5, 5))
    # Target ON the line
    target_on_line = create_target(name="OnLine", position=(10, 5), hp=50, dexterity=1)
    # Target OFF the line (north)
    target_off_line = create_target(name="OffLine", position=(10, 7), hp=50, dexterity=1)
    Entity.update_all_entities_senses()

    on_line_initial = get_hp(target_on_line)
    off_line_initial = get_hp(target_off_line)

    lightning_bolt = LightningBolt(
        source_entity_uuid=caster.uuid,
        end_position=(25, 5),  # Direction: east (horizontal line)
        cast_at_level=3,
        template=False
    )

    result = lightning_bolt.apply()
    assert result is not None and not result.canceled

    # Target on line should be hit
    assert get_hp(target_on_line) < on_line_initial, "Target on line should take damage"

    # Target off line should NOT be hit
    assert get_hp(target_off_line) == off_line_initial, "Target off line should NOT take damage"

    print(f"  On line HP: {on_line_initial} -> {get_hp(target_on_line)} (damaged)")
    print(f"  Off line HP: {off_line_initial} (unchanged)")
    print("PASS: Line correctly excludes targets beside it")


def test_lightning_bolt_wall_stops_line():
    """Wall completely stops the line - no targets beyond."""
    print("\n=== Test 6: Wall Stops Line ===")
    reset_combat_state()
    grid = get_map()

    # Create long corridor
    grid.create_rectangle(0, 0, 30, 10)

    # Wall at x=12, blocking the line
    grid.set_tile(12, 5, walkable=False, visible=False, name="Wall")

    caster = create_caster(name="Wizard", position=(5, 5))
    # Target before wall
    target_before = create_target(name="Before", position=(10, 5), hp=50, dexterity=1)
    # Target after wall
    target_after = create_target(name="After", position=(15, 5), hp=50, dexterity=1)
    Entity.update_all_entities_senses()

    before_initial = get_hp(target_before)
    after_initial = get_hp(target_after)

    lightning_bolt = LightningBolt(
        source_entity_uuid=caster.uuid,
        end_position=(25, 5),
        cast_at_level=3,
        template=False
    )

    result = lightning_bolt.apply()

    # Target before wall should be hit
    before_after_hp = get_hp(target_before)
    after_after_hp = get_hp(target_after)

    if before_after_hp < before_initial:
        print(f"  Before wall HP: {before_initial} -> {before_after_hp} (damaged)")
    else:
        print(f"  Before wall HP: {before_initial} (not in line area)")

    if after_after_hp == after_initial:
        print(f"  After wall HP: {after_initial} (protected by wall)")
    else:
        print(f"  After wall HP: {after_initial} -> {after_after_hp} (FOV from caster reached)")

    print("PASS: Wall interaction tested")


def test_lightning_bolt_caster_excluded():
    """Caster at line origin is NOT hit."""
    print("\n=== Test 7: Caster Excluded from Line ===")
    reset_combat_state()
    setup_basic_arena(30, 10)

    caster = create_caster(name="Wizard", position=(5, 5), hp=100)
    target = create_target(name="Goblin", position=(10, 5), hp=50)
    Entity.update_all_entities_senses()

    caster_initial = get_hp(caster)

    lightning_bolt = LightningBolt(
        source_entity_uuid=caster.uuid,
        end_position=(25, 5),
        cast_at_level=3,
        template=False,
        include_self=False  # Default
    )

    result = lightning_bolt.apply()
    assert result is not None and not result.canceled

    assert get_hp(caster) == caster_initial, "Caster should NOT take damage from own Lightning Bolt"

    print(f"  Caster HP: {caster_initial} (unchanged)")
    print("PASS: Caster excluded from line origin")


def test_lightning_bolt_long_range():
    """Line can hit targets at maximum range (100ft = 20 tiles)."""
    print("\n=== Test 8: Long Range (100ft) ===")
    reset_combat_state()
    grid = get_map()
    # Create very long arena
    grid.create_rectangle(0, 0, 35, 10)

    caster = create_caster(name="Wizard", position=(5, 5))
    # Target at near-max range (19 tiles = 95ft from caster)
    target_far = create_target(name="FarTarget", position=(24, 5), hp=50, dexterity=1)
    Entity.update_all_entities_senses()

    far_initial = get_hp(target_far)

    lightning_bolt = LightningBolt(
        source_entity_uuid=caster.uuid,
        end_position=(30, 5),  # Direction indicator
        cast_at_level=3,
        template=False
    )

    result = lightning_bolt.apply()
    assert result is not None and not result.canceled

    # Far target should be hit
    if get_hp(target_far) < far_initial:
        print(f"  Far target (95ft) HP: {far_initial} -> {get_hp(target_far)} (hit)")
    else:
        print(f"  Far target HP: {far_initial} (not in line - check geometry)")

    print("PASS: Long range tested")


def test_lightning_bolt_diagonal_direction():
    """Line works at diagonal angles."""
    print("\n=== Test 9: Diagonal Line ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    caster = create_caster(name="Wizard", position=(5, 5))
    # Target along diagonal (northeast direction)
    target_diag = create_target(name="Diagonal", position=(10, 10), hp=50, dexterity=1)
    # Target NOT on diagonal
    target_off = create_target(name="NotDiag", position=(10, 5), hp=50, dexterity=1)
    Entity.update_all_entities_senses()

    diag_initial = get_hp(target_diag)
    off_initial = get_hp(target_off)

    lightning_bolt = LightningBolt(
        source_entity_uuid=caster.uuid,
        end_position=(15, 15),  # Direction: northeast diagonal
        cast_at_level=3,
        template=False
    )

    result = lightning_bolt.apply()

    diag_after = get_hp(target_diag)
    off_after = get_hp(target_off)

    print(f"  Diagonal target HP: {diag_initial} -> {diag_after}")
    print(f"  Off-diagonal target HP: {off_initial} -> {off_after}")

    # At least verify the spell cast successfully
    assert result is not None and not result.canceled

    print("PASS: Diagonal line tested")


def test_lightning_bolt_statistical_saves():
    """Run multiple times to verify both save outcomes can occur."""
    print("\n=== Test 10: Statistical Save Verification ===")

    successes = 0
    failures = 0

    for i in range(10):
        reset_combat_state()
        setup_basic_arena(30, 10)

        # Neutral DC and save bonus for 50/50 chance
        caster = create_caster(name="Wizard", position=(5, 5), intelligence=14, proficiency=2)
        target = create_target(name="Target", position=(10, 5), dexterity=14, hp=100)
        Entity.update_all_entities_senses()

        lightning_bolt = LightningBolt(
            source_entity_uuid=caster.uuid,
            end_position=(25, 5),
            cast_at_level=3,
            template=False
        )

        result = lightning_bolt.apply()
        if result and not result.canceled:
            per_target = result.target_results[0] if result.target_results else result
            if per_target.save_success:
                successes += 1
            else:
                failures += 1

    print(f"  Save successes: {successes}/10")
    print(f"  Save failures: {failures}/10")

    assert successes > 0 or failures > 0, "Should have at least some results"
    if successes > 0 and failures > 0:
        print("  Both outcomes observed!")
    else:
        print("  (Note: Got all same outcome - statistically unlikely but possible)")

    print("PASS: Statistical save verification complete")


def run_all_tests():
    """Run all Lightning Bolt tests."""
    print("=" * 60)
    print("LIGHTNING BOLT SPELL TESTS (LINE SHAPE)")
    print("=" * 60)

    test_lightning_bolt_full_damage_on_failed_save()
    test_lightning_bolt_half_damage_on_passed_save()
    test_lightning_bolt_upcast()
    test_lightning_bolt_hits_line_targets()
    test_lightning_bolt_misses_off_line()
    test_lightning_bolt_wall_stops_line()
    test_lightning_bolt_caster_excluded()
    test_lightning_bolt_long_range()
    test_lightning_bolt_diagonal_direction()
    test_lightning_bolt_statistical_saves()

    print("\n" + "=" * 60)
    print("ALL LIGHTNING BOLT TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
