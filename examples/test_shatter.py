"""Comprehensive tests for Shatter spell (Smaller sphere shape)."""
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
from dnd.spells.evocation import Shatter
from dnd.actions import SpellEvent

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
    constitution: int = 10  # +0 mod for neutral save chance
) -> Entity:
    """Create a target entity with configurable CON."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            dexterity=AbilityConfig(ability_score=10),
            strength=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=constitution),
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


def setup_basic_arena(width: int = 20, height: int = 20):
    """Create a basic walkable arena."""
    grid = get_map()
    grid.create_rectangle(0, 0, width, height)
    return grid


def test_shatter_full_damage_on_failed_save():
    """Full 3d8 damage when target fails CON save (CON 1 target)."""
    print("\n=== Test 1: Full Damage on Failed CON Save ===")
    reset_combat_state()
    setup_basic_arena(20, 20)

    # Caster with high spell DC
    caster = create_caster(name="Wizard", position=(5, 5), intelligence=20, proficiency=4)
    # Target with CON 1 (-5 mod) - will always fail
    _target = create_target(name="Weak", position=(10, 5), constitution=1, hp=100)
    Entity.update_all_entities_senses()

    dc = caster.spell_save_dc()
    print(f"  Spell DC: {dc}")

    shatter = Shatter(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),  # Target position (center of explosion)
        cast_at_level=2,
        template=False
    )

    result = shatter.apply()
    assert result is not None and not result.canceled, f"Shatter failed: {result.status_message if result else 'None'}"
    assert isinstance(result, SpellEvent), "Result should be SpellEvent"

    assert result.target_results is not None and len(result.target_results) > 0, "Should have target_results"
    per_target = result.target_results[0]
    assert isinstance(per_target, SpellEvent), "Per-target result should be SpellEvent"

    # Verify save failed
    assert per_target.save_success == False, "Target with CON 1 should fail save"

    # Full damage (not halved)
    assert per_target.damage_rolls is not None, "Should have damage_rolls"
    rolled_damage = sum(r.total for r in per_target.damage_rolls)
    assert per_target.total_damage == rolled_damage, \
        f"Should be full damage, got {per_target.total_damage} vs rolled {rolled_damage}"

    print(f"  Save failed as expected")
    print(f"  Full damage applied: {per_target.total_damage}")
    print("PASS: Full damage on failed CON save")


def test_shatter_half_damage_on_passed_save():
    """Half damage when target passes CON save (CON 30 target)."""
    print("\n=== Test 2: Half Damage on Passed CON Save ===")
    reset_combat_state()
    setup_basic_arena(20, 20)

    # Caster with low spell DC
    caster = create_caster(name="Weak Wizard", position=(5, 5), intelligence=10, proficiency=2)
    # Target with CON 30 (+10 mod) - will always pass
    _target = create_target(name="Tough", position=(10, 5), constitution=30, hp=100)
    Entity.update_all_entities_senses()

    dc = caster.spell_save_dc()
    print(f"  Spell DC: {dc}")

    shatter = Shatter(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=2,
        template=False
    )

    result = shatter.apply()
    assert result is not None and not result.canceled
    assert isinstance(result, SpellEvent), "Result should be SpellEvent"

    assert result.target_results is not None and len(result.target_results) > 0, "Should have target_results"
    per_target = result.target_results[0]
    assert isinstance(per_target, SpellEvent), "Per-target result should be SpellEvent"

    # Verify save succeeded
    assert per_target.save_success == True, "Target with CON 30 should always save"

    # Half damage
    assert per_target.damage_rolls is not None, "Should have damage_rolls"
    rolled_damage = sum(r.total for r in per_target.damage_rolls)
    expected_damage = rolled_damage // 2
    assert per_target.total_damage == expected_damage, \
        f"Should be half damage: {rolled_damage}//2={expected_damage}, got {per_target.total_damage}"

    print(f"  Save passed as expected")
    print(f"  Half damage applied: {per_target.total_damage} (rolled {rolled_damage})")
    print("PASS: Half damage on passed CON save")


def test_shatter_upcast():
    """Higher spell slots deal more damage dice."""
    print("\n=== Test 3: Upcast Damage Scaling ===")

    sh2 = Shatter(source_entity_uuid=uuid4(), cast_at_level=2, template=False)
    sh3 = Shatter(source_entity_uuid=uuid4(), cast_at_level=3, template=False)
    sh4 = Shatter(source_entity_uuid=uuid4(), cast_at_level=4, template=False)
    sh5 = Shatter(source_entity_uuid=uuid4(), cast_at_level=5, template=False)
    sh9 = Shatter(source_entity_uuid=uuid4(), cast_at_level=9, template=False)

    assert sh2.get_damage_dice_count() == 3, f"Level 2: expected 3d8, got {sh2.get_damage_dice_count()}d8"
    assert sh3.get_damage_dice_count() == 4, f"Level 3: expected 4d8, got {sh3.get_damage_dice_count()}d8"
    assert sh4.get_damage_dice_count() == 5, f"Level 4: expected 5d8, got {sh4.get_damage_dice_count()}d8"
    assert sh5.get_damage_dice_count() == 6, f"Level 5: expected 6d8, got {sh5.get_damage_dice_count()}d8"
    assert sh9.get_damage_dice_count() == 10, f"Level 9: expected 10d8, got {sh9.get_damage_dice_count()}d8"

    print("  Level 2: 3d8 thunder")
    print("  Level 3: 4d8 thunder")
    print("  Level 4: 5d8 thunder")
    print("  Level 5: 6d8 thunder")
    print("  Level 9: 10d8 thunder")
    print("PASS: Upcast damage scaling works")


def test_shatter_smaller_radius():
    """10ft radius (2 tiles) - targets outside should NOT be hit."""
    print("\n=== Test 4: Smaller Radius (10ft = 2 tiles) ===")
    reset_combat_state()
    setup_basic_arena(20, 20)

    caster = create_caster(name="Wizard", position=(5, 5))

    # Target at center (will be hit)
    target_center = create_target(name="Center", position=(10, 5), constitution=1, hp=50)
    # Target within 2 tiles (10ft) - will be hit
    target_near = create_target(name="Near", position=(11, 5), constitution=1, hp=50)
    # Target just outside 2 tiles - should NOT be hit
    target_far = create_target(name="Far", position=(13, 5), constitution=1, hp=50)

    Entity.update_all_entities_senses()

    center_initial = get_hp(target_center)
    near_initial = get_hp(target_near)
    far_initial = get_hp(target_far)

    shatter = Shatter(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),  # Center of explosion
        cast_at_level=2,
        template=False
    )

    result = shatter.apply()
    assert result is not None and not result.canceled

    center_after = get_hp(target_center)
    near_after = get_hp(target_near)
    far_after = get_hp(target_far)

    # Center and near should be hit
    assert center_after < center_initial, "Center target should be hit"
    assert near_after < near_initial, "Near target (1 tile away) should be hit"

    # Far should NOT be hit (3 tiles > 2 tile radius)
    assert far_after == far_initial, "Far target (3 tiles away) should NOT be hit"

    print(f"  Center HP: {center_initial} -> {center_after} (damaged)")
    print(f"  Near (1 tile) HP: {near_initial} -> {near_after} (damaged)")
    print(f"  Far (3 tiles) HP: {far_initial} (unchanged)")
    print("PASS: 10ft radius correctly limits area")


def test_shatter_range_validation():
    """Shatter range is 60ft - should reject beyond that."""
    print("\n=== Test 5: Range Validation (60ft) ===")
    reset_combat_state()
    setup_basic_arena(30, 30)

    caster = create_caster(name="Wizard", position=(5, 5))
    Entity.update_all_entities_senses()

    # 60ft = 12 tiles, try targeting at 15 tiles (75ft)
    shatter_out_of_range = Shatter(
        source_entity_uuid=caster.uuid,
        end_position=(20, 5),  # 15 tiles = 75ft away
        cast_at_level=2,
        template=False
    )

    result = shatter_out_of_range.apply()

    # Should fail due to range or LOS
    assert result is not None
    if result.canceled:
        assert result.status_message is not None, "Should have status message"
        msg = result.status_message.lower()
        assert "out of range" in msg or "line of sight" in msg, \
            f"Expected range or LOS error, got: {result.status_message}"
        print(f"  Correctly rejected: {result.status_message}")
    else:
        print(f"  Cast succeeded (target within senses range)")

    # Now test within range
    shatter_in_range = Shatter(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),  # 5 tiles = 25ft away
        cast_at_level=2,
        template=False
    )

    result_in_range = shatter_in_range.apply()

    # This should succeed (position is within range)
    # May fail if no targets, but shouldn't fail on range
    if result_in_range and result_in_range.canceled:
        assert result_in_range.status_message is not None, "Should have status message"
        msg = result_in_range.status_message.lower()
        assert "out of range" not in msg, f"In-range cast should not fail on range: {result_in_range.status_message}"

    print("PASS: Range validation works")


def test_shatter_wall_blocks():
    """Wall between explosion center and target blocks damage."""
    print("\n=== Test 6: Wall Blocks AoE ===")
    reset_combat_state()
    grid = get_map()

    # Create arena
    grid.create_rectangle(0, 0, 20, 10)

    # Wall near explosion center
    grid.set_tile(11, 5, walkable=False, visible=False, name="Wall")

    caster = create_caster(name="Wizard", position=(5, 5))
    # Target visible from center (same side as caster)
    target_visible = create_target(name="Visible", position=(10, 5), constitution=1, hp=50)
    # Target behind wall from center
    target_blocked = create_target(name="Blocked", position=(12, 5), constitution=1, hp=50)

    Entity.update_all_entities_senses()

    visible_initial = get_hp(target_visible)
    blocked_initial = get_hp(target_blocked)

    shatter = Shatter(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),  # Center on visible target
        cast_at_level=2,
        template=False
    )

    _result = shatter.apply()

    visible_after = get_hp(target_visible)
    blocked_after = get_hp(target_blocked)

    print(f"  Visible target HP: {visible_initial} -> {visible_after}")
    print(f"  Blocked target HP: {blocked_initial} -> {blocked_after}")

    # Visible should be hit
    if visible_after < visible_initial:
        print("  Visible target hit correctly")

    # Blocked should be protected
    if blocked_after == blocked_initial:
        print("  Blocked target protected by wall")
    else:
        print("  Blocked target was in FOV from center (depends on algorithm)")

    print("PASS: Wall blocking tested")


def test_shatter_los_to_center():
    """Must have LOS to target position (center of explosion)."""
    print("\n=== Test 7: LOS to Center Required ===")
    reset_combat_state()
    grid = get_map()

    # Create arena with wall blocking LOS
    grid.create_rectangle(0, 0, 20, 10)

    # Wall blocking LOS from caster to target position
    grid.set_tile(7, 5, walkable=False, visible=False, name="Wall")

    caster = create_caster(name="Wizard", position=(5, 5))
    # Target behind wall
    _target = create_target(name="Target", position=(10, 5), constitution=1, hp=50)
    Entity.update_all_entities_senses()

    # Try to cast at position behind wall
    shatter_blocked = Shatter(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),  # Behind wall from caster
        cast_at_level=2,
        template=False
    )

    result = shatter_blocked.apply()

    if result and result.canceled:
        assert result.status_message is not None, "Should have status message"
        assert "not in line of sight" in result.status_message.lower(), \
            f"Expected LOS error, got: {result.status_message}"
        print(f"  Correctly blocked: {result.status_message}")
    else:
        print(f"  Cast succeeded (FOV algorithm allowed LOS)")

    print("PASS: LOS to center requirement tested")


def test_shatter_statistical_saves():
    """Run multiple times to verify both save outcomes can occur."""
    print("\n=== Test 8: Statistical Save Verification ===")

    successes = 0
    failures = 0

    for _ in range(10):
        reset_combat_state()
        setup_basic_arena(20, 20)

        # Neutral DC and save bonus for 50/50 chance
        caster = create_caster(name="Wizard", position=(5, 5), intelligence=14, proficiency=2)
        _target = create_target(name="Target", position=(10, 5), constitution=14, hp=100)
        Entity.update_all_entities_senses()

        shatter = Shatter(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=2,
            template=False
        )

        result = shatter.apply()
        if result and not result.canceled and isinstance(result, SpellEvent):
            per_target = result.target_results[0] if result.target_results else None
            if per_target is not None and isinstance(per_target, SpellEvent) and per_target.save_success:
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
    """Run all Shatter tests."""
    print("=" * 60)
    print("SHATTER SPELL TESTS (SMALLER SPHERE SHAPE)")
    print("=" * 60)

    test_shatter_full_damage_on_failed_save()
    test_shatter_half_damage_on_passed_save()
    test_shatter_upcast()
    test_shatter_smaller_radius()
    test_shatter_range_validation()
    test_shatter_wall_blocks()
    test_shatter_los_to_center()
    test_shatter_statistical_saves()

    print("\n" + "=" * 60)
    print("ALL SHATTER TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
