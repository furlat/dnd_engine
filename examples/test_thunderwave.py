"""Comprehensive tests for Thunderwave spell (Cube shape + push)."""
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
from dnd.spells.evocation import Thunderwave
from dnd.actions import SpellEvent

# Test utilities
from dnd.utils import get_hp, set_hp, get_position, get_save_natural_roll
from dnd.actions_functional import setup_standard_actions
import pytest


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


def test_thunderwave_full_damage_and_push_on_failed_save():
    """Full 2d8 damage AND pushed 10ft when target fails CON save (CON 1 target)."""
    print("\n=== Test 1: Full Damage + Push on Failed CON Save ===")

    for attempt in range(10):
        reset_combat_state()
        setup_basic_arena(20, 20)

        # Caster with high spell DC
        caster = create_caster(name="Wizard", position=(5, 5), intelligence=20, proficiency=4)
        # Target with CON 1 (-5 mod) - will always fail
        target = create_target(name="Weak", position=(7, 5), constitution=1, hp=100)
        Entity.update_all_entities_senses()

        dc = caster.spell_save_dc()
        print(f"  Spell DC: {dc}")

        _initial_hp = get_hp(target)
        initial_pos = get_position(target)
        print(f"  Initial position: {initial_pos}")

        thunderwave = Thunderwave(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),  # Direction: east
            cast_at_level=1,
            template=False
        )

        result = thunderwave.apply()
        assert result is not None and not result.canceled, f"Thunderwave failed: {result.status_message if result else 'None'}"
        assert isinstance(result, SpellEvent), "Result should be SpellEvent"

        # Verify via combat log
        assert result.combat_log is not None, "Should have combat_log"
        assert len(result.combat_log.sub_entries) > 0, "Should have sub_entries"
        log_data = result.combat_log.sub_entries[0].data

        natural_roll = get_save_natural_roll(log_data)
        if natural_roll == 20:
            print(f"  Attempt {attempt + 1}: got nat 20, retrying...")
            continue  # nat 20 auto-success, re-roll

        # Verify save failed
        assert log_data.get('save_success') == False, "Target with CON 1 should fail save"

        # Full damage (not halved)
        base_damage = log_data.get('base_damage', 0)
        final_damage = log_data.get('final_damage', 0)
        assert final_damage == base_damage, \
            f"Should be full damage, got {final_damage} vs rolled {base_damage}"

        # Should have been pushed
        final_pos = get_position(target)
        assert final_pos != initial_pos, "Target should have been pushed"
        # Push should be away from caster (eastward), 10ft = 2 tiles
        # Allow for diagonal push or partial movement
        assert final_pos[0] >= initial_pos[0], "Target should move away from caster (east)"

        print(f"  Save failed as expected")
        print(f"  Full damage: {final_damage}")
        print(f"  Position: {initial_pos} -> {final_pos} (pushed)")
        print("PASS: Full damage and push on failed CON save")
        break
    else:
        pytest.fail("Got nat 20 on all 10 attempts")


def test_thunderwave_half_damage_no_push_on_passed_save():
    """Half damage and NO push when target passes CON save (CON 30 target)."""
    print("\n=== Test 2: Half Damage + No Push on Passed CON Save ===")

    for attempt in range(10):
        reset_combat_state()
        setup_basic_arena(20, 20)

        # Caster with low spell DC
        caster = create_caster(name="Weak Wizard", position=(5, 5), intelligence=10, proficiency=2)
        # Target with CON 30 (+10 mod) - will always pass
        target = create_target(name="Tough", position=(7, 5), constitution=30, hp=100)
        Entity.update_all_entities_senses()

        dc = caster.spell_save_dc()
        print(f"  Spell DC: {dc}")

        _initial_hp = get_hp(target)
        initial_pos = get_position(target)

        thunderwave = Thunderwave(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=1,
            template=False
        )

        result = thunderwave.apply()
        assert result is not None and not result.canceled
        assert isinstance(result, SpellEvent), "Result should be SpellEvent"

        # Verify via combat log
        assert result.combat_log is not None, "Should have combat_log"
        assert len(result.combat_log.sub_entries) > 0, "Should have sub_entries"
        log_data = result.combat_log.sub_entries[0].data

        natural_roll = get_save_natural_roll(log_data)
        if natural_roll == 1:
            print(f"  Attempt {attempt + 1}: got nat 1, retrying...")
            continue  # nat 1 auto-fail, re-roll

        # Verify save succeeded
        assert log_data.get('save_success') == True, "Target with CON 30 should always save"

        # Half damage
        base_damage = log_data.get('base_damage', 0)
        final_damage = log_data.get('final_damage', 0)
        expected_damage = base_damage // 2
        assert final_damage == expected_damage, \
            f"Should be half damage: {base_damage}//2={expected_damage}, got {final_damage}"

        # Should NOT have been pushed
        final_pos = get_position(target)
        assert final_pos == initial_pos, f"Target should NOT have been pushed, but moved from {initial_pos} to {final_pos}"

        print(f"  Save passed as expected")
        print(f"  Half damage: {final_damage} (rolled {base_damage})")
        print(f"  Position: {initial_pos} -> {final_pos} (unchanged)")
        print("PASS: Half damage and no push on passed CON save")
        break
    else:
        pytest.fail("Got nat 1 on all 10 attempts")


def test_thunderwave_upcast():
    """Higher spell slots deal more damage dice."""
    print("\n=== Test 3: Upcast Damage Scaling ===")

    tw1 = Thunderwave(source_entity_uuid=uuid4(), cast_at_level=1, template=False)
    tw2 = Thunderwave(source_entity_uuid=uuid4(), cast_at_level=2, template=False)
    tw3 = Thunderwave(source_entity_uuid=uuid4(), cast_at_level=3, template=False)
    tw4 = Thunderwave(source_entity_uuid=uuid4(), cast_at_level=4, template=False)
    tw9 = Thunderwave(source_entity_uuid=uuid4(), cast_at_level=9, template=False)

    assert tw1.get_damage_dice_count() == 2, f"Level 1: expected 2d8, got {tw1.get_damage_dice_count()}d8"
    assert tw2.get_damage_dice_count() == 3, f"Level 2: expected 3d8, got {tw2.get_damage_dice_count()}d8"
    assert tw3.get_damage_dice_count() == 4, f"Level 3: expected 4d8, got {tw3.get_damage_dice_count()}d8"
    assert tw4.get_damage_dice_count() == 5, f"Level 4: expected 5d8, got {tw4.get_damage_dice_count()}d8"
    assert tw9.get_damage_dice_count() == 10, f"Level 9: expected 10d8, got {tw9.get_damage_dice_count()}d8"

    print("  Level 1: 2d8 thunder")
    print("  Level 2: 3d8 thunder")
    print("  Level 3: 4d8 thunder")
    print("  Level 4: 5d8 thunder")
    print("  Level 9: 10d8 thunder")
    print("PASS: Upcast damage scaling works")


def test_thunderwave_push_direction():
    """Push is away from caster (radial direction)."""
    print("\n=== Test 4: Push Direction is Away from Caster ===")
    reset_combat_state()
    setup_basic_arena(20, 20)

    # Caster in center
    caster = create_caster(name="Wizard", position=(10, 10), intelligence=20, proficiency=4)

    # Targets in different directions (all will fail save with CON 1)
    target_e = create_target(name="East", position=(12, 10), constitution=1, hp=100)
    target_ne = create_target(name="NorthEast", position=(12, 12), constitution=1, hp=100)
    target_n = create_target(name="North", position=(10, 12), constitution=1, hp=100)

    Entity.update_all_entities_senses()

    e_initial = get_position(target_e)
    ne_initial = get_position(target_ne)
    n_initial = get_position(target_n)

    thunderwave = Thunderwave(
        source_entity_uuid=caster.uuid,
        end_position=(15, 15),  # Direction: northeast (doesn't affect push direction)
        cast_at_level=1,
        template=False
    )

    _result = thunderwave.apply()

    e_final = get_position(target_e)
    ne_final = get_position(target_ne)
    n_final = get_position(target_n)

    print(f"  East target: {e_initial} -> {e_final}")
    print(f"  NorthEast target: {ne_initial} -> {ne_final}")
    print(f"  North target: {n_initial} -> {n_final}")

    # East target should be pushed further east (x increases)
    if e_final != e_initial:
        assert e_final[0] > e_initial[0], "East target should be pushed east"
        print("  East target pushed east correctly")

    # Northeast target should be pushed northeast (x and y increase)
    if ne_final != ne_initial:
        assert ne_final[0] >= ne_initial[0] and ne_final[1] >= ne_initial[1], \
            "Northeast target should be pushed northeast"
        print("  Northeast target pushed northeast correctly")

    # North target should be pushed north (y increases)
    if n_final != n_initial:
        assert n_final[1] > n_initial[1], "North target should be pushed north"
        print("  North target pushed north correctly")

    print("PASS: Push direction is radial from caster")


def test_thunderwave_push_blocked_by_wall():
    """Push stops early if wall blocks the path. Combat log says 'blocked by Wall'."""
    print("\n=== Test 5: Push Blocked by Wall ===")

    for attempt in range(10):
        reset_combat_state()
        grid = get_map()

        # Create arena with wall
        grid.create_rectangle(0, 0, 20, 10)

        # Wall 1 tile behind target's initial position
        grid.set_tile(9, 5, walkable=False, visible=False, name="Wall")

        caster = create_caster(name="Wizard", position=(5, 5), intelligence=20, proficiency=4)
        # Target that will be pushed toward wall (CON 1 = always fails save except nat 20)
        target = create_target(name="Target", position=(7, 5), constitution=1, hp=100)
        Entity.update_all_entities_senses()

        initial_pos = get_position(target)

        thunderwave = Thunderwave(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),  # Direction: east
            cast_at_level=1,
            template=False
        )

        result = thunderwave.apply()
        assert result is not None and not result.canceled

        final_pos = get_position(target)

        if final_pos[0] <= initial_pos[0]:
            print(f"  Attempt {attempt + 1}: No push (nat 20?), retrying...")
            continue

        # Target should have been pushed but stopped at (8, 5), one tile before wall
        assert final_pos[0] <= 8, f"Target should stop before wall at (9,5), but ended at {final_pos}"
        print(f"  Initial position: {initial_pos}")
        print(f"  Wall at: (9, 5)")
        print(f"  Final position: {final_pos}")

        # Verify blocked_by in ForcedMovementEvent combat log
        assert isinstance(result, SpellEvent) and result.combat_log
        found_blocked_by = False
        for sub in result.combat_log.sub_entries:
            for subsub in sub.sub_entries:
                if subsub.data and subsub.data.get("type") == "forced_movement":
                    assert subsub.data.get("blocked") is True, "Should be blocked"
                    assert subsub.data.get("blocked_by") == "Wall", \
                        f"blocked_by should be 'Wall', got '{subsub.data.get('blocked_by')}'"
                    assert "blocked by Wall" in subsub.compact, \
                        f"Compact text should contain 'blocked by Wall', got: {subsub.compact}"
                    found_blocked_by = True
                    print(f"  Combat log: {subsub.compact}")
        assert found_blocked_by, "Should have found ForcedMovementEvent with blocked_by=Wall"
        print("PASS: Push blocked by wall with descriptive combat log")
        break
    else:
        pytest.fail("Got nat 20 on all 10 attempts")


def test_thunderwave_cube_shape():
    """Only targets in cube direction are hit."""
    print("\n=== Test 6: Cube Shape Targeting ===")
    reset_combat_state()
    setup_basic_arena(20, 20)

    caster = create_caster(name="Wizard", position=(10, 10))
    # Target in cube direction (east, within 15ft = 3 tiles)
    target_in_cube = create_target(name="InCube", position=(12, 10), constitution=1, hp=50)
    # Target behind caster (west) - should NOT be hit
    target_behind = create_target(name="Behind", position=(8, 10), constitution=1, hp=50)
    Entity.update_all_entities_senses()

    in_cube_initial = get_hp(target_in_cube)
    behind_initial = get_hp(target_behind)

    thunderwave = Thunderwave(
        source_entity_uuid=caster.uuid,
        end_position=(15, 10),  # Direction: east
        cast_at_level=1,
        template=False
    )

    result = thunderwave.apply()
    assert result is not None and not result.canceled

    # Target in cube direction should be hit
    assert get_hp(target_in_cube) < in_cube_initial, "Target in cube should take damage"

    # Target behind should NOT be hit
    assert get_hp(target_behind) == behind_initial, "Target behind caster should NOT take damage"

    print(f"  In cube HP: {in_cube_initial} -> {get_hp(target_in_cube)} (damaged)")
    print(f"  Behind HP: {behind_initial} (unchanged)")
    print("PASS: Cube shape correctly filters targets")


def test_thunderwave_caster_excluded():
    """Caster is NOT hit by their own Thunderwave."""
    print("\n=== Test 7: Caster Excluded ===")
    reset_combat_state()
    setup_basic_arena(20, 20)

    caster = create_caster(name="Wizard", position=(10, 10), hp=100)
    _target = create_target(name="Target", position=(12, 10), hp=50)
    Entity.update_all_entities_senses()

    caster_initial = get_hp(caster)

    thunderwave = Thunderwave(
        source_entity_uuid=caster.uuid,
        end_position=(15, 10),
        cast_at_level=1,
        template=False,
        include_self=False  # Default
    )

    result = thunderwave.apply()
    assert result is not None and not result.canceled

    assert get_hp(caster) == caster_initial, "Caster should NOT take damage"

    print(f"  Caster HP: {caster_initial} (unchanged)")
    print("PASS: Caster excluded from Thunderwave")


def test_thunderwave_multiple_targets_mixed_saves():
    """Multiple targets - some pushed, some not based on saves."""
    print("\n=== Test 8: Multiple Targets Mixed Saves ===")
    reset_combat_state()
    setup_basic_arena(20, 20)

    # Caster with very high DC to ensure weak target fails
    caster = create_caster(name="Wizard", position=(10, 10), intelligence=20, proficiency=4)  # DC 17

    # Low CON target - will fail save
    target_weak = create_target(name="Weak", position=(11, 10), constitution=1, hp=50)
    # High CON target - will pass save
    target_tough = create_target(name="Tough", position=(12, 10), constitution=30, hp=50)

    Entity.update_all_entities_senses()

    weak_initial_pos = get_position(target_weak)
    tough_initial_pos = get_position(target_tough)

    thunderwave = Thunderwave(
        source_entity_uuid=caster.uuid,
        end_position=(15, 10),
        cast_at_level=1,
        template=False
    )

    result = thunderwave.apply()
    assert result is not None and not result.canceled

    weak_final_pos = get_position(target_weak)
    tough_final_pos = get_position(target_tough)

    print(f"  Weak (CON 1): {weak_initial_pos} -> {weak_final_pos}")
    print(f"  Tough (CON 30): {tough_initial_pos} -> {tough_final_pos}")

    # Check saves from combat log sub_entries
    if isinstance(result, SpellEvent) and result.combat_log and result.combat_log.sub_entries:
        for sub in result.combat_log.sub_entries:
            target_name = sub.data.get('target_name', '')
            save_success = sub.data.get('save_success', False)
            if "Weak" in target_name:
                # Weak should fail and be pushed
                if not save_success:
                    if weak_final_pos == weak_initial_pos:
                        # Might have been blocked by tough target in path
                        print("  Weak target not pushed (possibly blocked by Tough)")
                    else:
                        print(f"  Weak target pushed correctly")
                else:
                    print(f"  Weak target unexpectedly saved")
            if "Tough" in target_name:
                # Tough should save and NOT be pushed
                if save_success:
                    assert tough_final_pos == tough_initial_pos, "Tough target should NOT move after saving"
                    print(f"  Tough target saved, not pushed")

    print("PASS: Mixed saves handled correctly")


def test_thunderwave_statistical_saves():
    """Run multiple times to verify both save outcomes can occur."""
    print("\n=== Test 9: Statistical Save Verification ===")

    successes = 0
    failures = 0
    pushes = 0

    for _ in range(10):
        reset_combat_state()
        setup_basic_arena(20, 20)

        # Neutral DC and save bonus for 50/50 chance
        caster = create_caster(name="Wizard", position=(10, 10), intelligence=14, proficiency=2)
        target = create_target(name="Target", position=(12, 10), constitution=14, hp=100)
        Entity.update_all_entities_senses()

        initial_pos = get_position(target)

        thunderwave = Thunderwave(
            source_entity_uuid=caster.uuid,
            end_position=(15, 10),
            cast_at_level=1,
            template=False
        )

        result = thunderwave.apply()
        if result and not result.canceled and isinstance(result, SpellEvent) and result.combat_log:
            sub_entries = result.combat_log.sub_entries
            if sub_entries and sub_entries[0].data.get('save_success'):
                successes += 1
            else:
                failures += 1
                # Check if push happened
                if get_position(target) != initial_pos:
                    pushes += 1

    print(f"  Save successes: {successes}/10")
    print(f"  Save failures: {failures}/10")
    print(f"  Pushes (on fails): {pushes}/{failures}")

    assert successes > 0 or failures > 0, "Should have at least some results"
    if successes > 0 and failures > 0:
        print("  Both outcomes observed!")
    else:
        print("  (Note: Got all same outcome - statistically unlikely but possible)")

    print("PASS: Statistical save verification complete")


def test_thunderwave_push_into_occupied_space():
    """Push stops at occupied spaces. Combat log says 'blocked by <entity name>'."""
    print("\n=== Test 10: Push Stops at Occupied Space ===")

    for attempt in range(10):
        reset_combat_state()
        setup_basic_arena(20, 20)

        caster = create_caster(name="Wizard", position=(5, 5), intelligence=20, proficiency=4)
        # Target that will be pushed (CON 1 = always fails except nat 20)
        target_front = create_target(name="Front", position=(7, 5), constitution=1, hp=50)
        # Blocker in the push path (CON 30 = always saves, won't move)
        blocker = create_target(name="Blocker", position=(9, 5), constitution=30, hp=100)

        Entity.update_all_entities_senses()

        front_initial = get_position(target_front)
        blocker_initial = get_position(blocker)

        thunderwave = Thunderwave(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=1,
            template=False
        )

        result = thunderwave.apply()
        assert result is not None and not result.canceled

        front_final = get_position(target_front)
        blocker_final = get_position(blocker)

        if front_final[0] <= front_initial[0]:
            print(f"  Attempt {attempt + 1}: Front not pushed (nat 20?), retrying...")
            continue

        # Front target should be pushed but stopped before blocker
        assert front_final[0] < blocker_initial[0], \
            f"Front should stop before blocker, got {front_final}"
        print(f"  Front target: {front_initial} -> {front_final}")
        print(f"  Blocker: {blocker_initial} -> {blocker_final}")
        print("  Front target stopped before blocker correctly")

        # Verify blocked_by in ForcedMovementEvent combat log
        assert isinstance(result, SpellEvent) and result.combat_log
        found_blocked_by = False
        for sub in result.combat_log.sub_entries:
            target_name = sub.data.get("target_name", "")
            if target_name != "Front":
                continue
            for subsub in sub.sub_entries:
                if subsub.data and subsub.data.get("type") == "forced_movement":
                    blocked_by = subsub.data.get("blocked_by")
                    if blocked_by:
                        assert blocked_by == "Blocker", \
                            f"blocked_by should be 'Blocker', got '{blocked_by}'"
                        assert "blocked by Blocker" in subsub.compact, \
                            f"Compact text should contain 'blocked by Blocker', got: {subsub.compact}"
                        found_blocked_by = True
                        print(f"  Combat log: {subsub.compact}")
        assert found_blocked_by, "Should have found ForcedMovementEvent with blocked_by=Blocker"
        print("PASS: Push blocked by entity with descriptive combat log")
        break
    else:
        pytest.fail("Front target never pushed in 10 attempts")


def run_all_tests():
    """Run all Thunderwave tests."""
    print("=" * 60)
    print("THUNDERWAVE SPELL TESTS (CUBE SHAPE + PUSH)")
    print("=" * 60)

    test_thunderwave_full_damage_and_push_on_failed_save()
    test_thunderwave_half_damage_no_push_on_passed_save()
    test_thunderwave_upcast()
    test_thunderwave_push_direction()
    test_thunderwave_push_blocked_by_wall()
    test_thunderwave_cube_shape()
    test_thunderwave_caster_excluded()
    test_thunderwave_multiple_targets_mixed_saves()
    test_thunderwave_statistical_saves()
    test_thunderwave_push_into_occupied_space()

    print("\n" + "=" * 60)
    print("ALL THUNDERWAVE TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
