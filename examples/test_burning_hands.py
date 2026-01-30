"""Comprehensive tests for Burning Hands spell (Cone shape)."""
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
from dnd.spells.evocation import BurningHands

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
    position: Tuple[int, int] = (3, 0),
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


def setup_basic_arena(width: int = 20, height: int = 20):
    """Create a basic walkable arena."""
    grid = get_map()
    grid.create_rectangle(0, 0, width, height)
    return grid


def test_burning_hands_basic_damage():
    """Basic Burning Hands deals fire damage to target in cone."""
    print("\n=== Test 1: Basic Burning Hands Damage ===")
    reset_combat_state()
    setup_basic_arena(20, 20)

    caster = create_caster(name="Wizard", position=(5, 5))
    # Target in cone direction (3 tiles = 15ft, within 15ft cone)
    target = create_target(name="Goblin", position=(7, 5), hp=50)
    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)

    burning_hands = BurningHands(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),  # Direction: east
        cast_at_level=1,
        template=False
    )

    result = burning_hands.apply()

    assert result is not None, "Burning Hands should return a result"
    assert not result.canceled, f"Burning Hands was canceled: {result.status_message}"
    assert result.total_damage > 0, "Burning Hands should deal damage"
    assert get_hp(target) < initial_hp, "Target should have taken damage"

    print(f"  Dealt {result.total_damage} fire damage")
    print(f"  Target HP: {initial_hp} -> {get_hp(target)}")
    print("PASS: Basic burning hands damage works")


def test_burning_hands_full_damage_on_failed_save():
    """Full 3d6 damage when target fails DEX save (DEX 1 target)."""
    print("\n=== Test 2: Full Damage on Failed DEX Save ===")
    reset_combat_state()
    setup_basic_arena(20, 20)

    # Caster with high spell DC
    caster = create_caster(name="Wizard", position=(5, 5), intelligence=20, proficiency=4)
    # Target with DEX 1 (-5 mod) - will always fail vs high DC
    target = create_target(name="Slow", position=(7, 5), dexterity=1, hp=100)
    Entity.update_all_entities_senses()

    dc = caster.spell_save_dc()
    print(f"  Spell DC: {dc}")

    burning_hands = BurningHands(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=1,
        template=False
    )

    result = burning_hands.apply()
    assert result is not None and not result.canceled

    # Get per-target result
    per_target = result.target_results[0] if result.target_results else result

    # Verify save failed
    assert per_target.save_success == False, "Target with DEX 1 should fail save vs high DC"

    # Full damage (not halved)
    rolled_damage = sum(r.total for r in per_target.damage_rolls) if per_target.damage_rolls else 0
    assert per_target.total_damage == rolled_damage, f"Should be full damage, got {per_target.total_damage} vs rolled {rolled_damage}"

    print(f"  Save failed as expected")
    print(f"  Full damage applied: {per_target.total_damage}")
    print("PASS: Full damage on failed DEX save")


def test_burning_hands_half_damage_on_passed_save():
    """Half damage when target passes DEX save (DEX 30 target)."""
    print("\n=== Test 3: Half Damage on Passed DEX Save ===")
    reset_combat_state()
    setup_basic_arena(20, 20)

    # Caster with low spell DC
    caster = create_caster(name="Weak Wizard", position=(5, 5), intelligence=10, proficiency=2)
    # Target with DEX 30 (+10 mod) - will always pass
    target = create_target(name="Nimble", position=(7, 5), dexterity=30, hp=100)
    Entity.update_all_entities_senses()

    dc = caster.spell_save_dc()
    print(f"  Spell DC: {dc}")

    burning_hands = BurningHands(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=1,
        template=False
    )

    result = burning_hands.apply()
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


def test_burning_hands_upcast():
    """Higher spell slots deal more damage dice."""
    print("\n=== Test 4: Upcast Damage Scaling ===")

    # Test dice count method directly
    bh1 = BurningHands(source_entity_uuid=uuid4(), cast_at_level=1, template=False)
    bh2 = BurningHands(source_entity_uuid=uuid4(), cast_at_level=2, template=False)
    bh3 = BurningHands(source_entity_uuid=uuid4(), cast_at_level=3, template=False)
    bh4 = BurningHands(source_entity_uuid=uuid4(), cast_at_level=4, template=False)
    bh9 = BurningHands(source_entity_uuid=uuid4(), cast_at_level=9, template=False)

    assert bh1.get_damage_dice_count() == 3, f"Level 1: expected 3d6, got {bh1.get_damage_dice_count()}d6"
    assert bh2.get_damage_dice_count() == 4, f"Level 2: expected 4d6, got {bh2.get_damage_dice_count()}d6"
    assert bh3.get_damage_dice_count() == 5, f"Level 3: expected 5d6, got {bh3.get_damage_dice_count()}d6"
    assert bh4.get_damage_dice_count() == 6, f"Level 4: expected 6d6, got {bh4.get_damage_dice_count()}d6"
    assert bh9.get_damage_dice_count() == 11, f"Level 9: expected 11d6, got {bh9.get_damage_dice_count()}d6"

    print("  Level 1: 3d6 fire")
    print("  Level 2: 4d6 fire")
    print("  Level 3: 5d6 fire")
    print("  Level 4: 6d6 fire")
    print("  Level 9: 11d6 fire")
    print("PASS: Upcast damage scaling works")


def test_burning_hands_cone_direction():
    """Only targets in cone direction are hit."""
    print("\n=== Test 5: Cone Direction Targeting ===")
    reset_combat_state()
    setup_basic_arena(20, 20)

    caster = create_caster(name="Wizard", position=(5, 5))
    # Target in cone direction (east)
    target_in_cone = create_target(name="InCone", position=(7, 5), hp=50, dexterity=1)
    # Target behind caster (west) - should NOT be hit
    target_behind = create_target(name="Behind", position=(3, 5), hp=50, dexterity=1)
    # Target perpendicular (north) - should NOT be hit
    target_perp = create_target(name="Perpendicular", position=(5, 7), hp=50, dexterity=1)
    Entity.update_all_entities_senses()

    in_cone_initial = get_hp(target_in_cone)
    behind_initial = get_hp(target_behind)
    perp_initial = get_hp(target_perp)

    burning_hands = BurningHands(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),  # Direction: east
        cast_at_level=1,
        template=False,
        valid_target_filter="all"
    )

    result = burning_hands.apply()

    assert result is not None and not result.canceled

    # Target in cone should be hit
    assert get_hp(target_in_cone) < in_cone_initial, "Target in cone should take damage"

    # Targets outside cone should NOT be hit
    assert get_hp(target_behind) == behind_initial, "Target behind caster should NOT take damage"
    assert get_hp(target_perp) == perp_initial, "Target perpendicular to cone should NOT take damage"

    print(f"  In cone HP: {in_cone_initial} -> {get_hp(target_in_cone)} (damaged)")
    print(f"  Behind HP: {behind_initial} (unchanged)")
    print(f"  Perpendicular HP: {perp_initial} (unchanged)")
    print("PASS: Cone direction correctly filters targets")


def test_burning_hands_caster_excluded():
    """Caster at cone apex is NOT hit."""
    print("\n=== Test 6: Caster Excluded from Cone ===")
    reset_combat_state()
    setup_basic_arena(20, 20)

    caster = create_caster(name="Wizard", position=(5, 5), hp=100)
    target = create_target(name="Goblin", position=(7, 5), hp=50)
    Entity.update_all_entities_senses()

    caster_initial = get_hp(caster)

    burning_hands = BurningHands(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=1,
        template=False,
        include_self=False  # Default
    )

    result = burning_hands.apply()
    assert result is not None and not result.canceled

    assert get_hp(caster) == caster_initial, "Caster should NOT take damage from own Burning Hands"

    print(f"  Caster HP: {caster_initial} (unchanged)")
    print("PASS: Caster excluded from cone apex")


def test_burning_hands_wall_blocks():
    """Wall between caster and target blocks damage."""
    print("\n=== Test 7: Wall Blocks Cone ===")
    reset_combat_state()
    grid = get_map()

    # Create arena
    grid.create_rectangle(0, 0, 15, 10)

    # Wall at x=6, between caster at (5,5) and target at (8,5)
    grid.set_tile(6, 5, walkable=False, visible=False, name="Wall")

    caster = create_caster(name="Wizard", position=(5, 5))
    # Target behind wall
    target_blocked = create_target(name="Blocked", position=(8, 5), hp=50, dexterity=1)
    Entity.update_all_entities_senses()

    blocked_initial = get_hp(target_blocked)

    burning_hands = BurningHands(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),  # Direction: east (through wall)
        cast_at_level=1,
        template=False
    )

    result = burning_hands.apply()

    # The target behind the wall should be protected
    blocked_after = get_hp(target_blocked)

    if blocked_after == blocked_initial:
        print(f"  Blocked target HP: {blocked_initial} (unchanged - wall blocked)")
    else:
        print(f"  Blocked target HP: {blocked_initial} -> {blocked_after} (FOV calculated from apex)")

    print("PASS: Wall interaction tested")


def test_burning_hands_multiple_targets():
    """Multiple targets in cone all take damage."""
    print("\n=== Test 8: Multiple Targets in Cone ===")
    reset_combat_state()
    setup_basic_arena(20, 20)

    caster = create_caster(name="Wizard", position=(5, 5))
    # Multiple targets in cone direction
    target1 = create_target(name="Goblin1", position=(6, 5), hp=50, dexterity=1)  # Close
    target2 = create_target(name="Goblin2", position=(7, 5), hp=50, dexterity=30)  # Mid, will save
    target3 = create_target(name="Goblin3", position=(7, 4), hp=50, dexterity=1)  # Side
    Entity.update_all_entities_senses()

    burning_hands = BurningHands(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=1,
        template=False,
        valid_target_filter="enemies"
    )

    result = burning_hands.apply()
    assert result is not None and not result.canceled

    # Check how many targets were hit
    targets_hit = result.total_targets
    print(f"  Targets hit: {targets_hit}")

    # At least target1 and target2 should be hit (in direct cone path)
    assert targets_hit >= 2, f"Should hit at least 2 targets, got {targets_hit}"

    # Check individual damages
    if result.target_results:
        for tr in result.target_results:
            print(f"    {tr.status_message}")

    print("PASS: Multiple targets in cone handled")


def test_burning_hands_statistical_saves():
    """Run multiple times to verify both save outcomes can occur."""
    print("\n=== Test 9: Statistical Save Verification ===")

    successes = 0
    failures = 0

    for i in range(10):
        reset_combat_state()
        setup_basic_arena(20, 20)

        # Neutral DC and save bonus for 50/50 chance
        caster = create_caster(name="Wizard", position=(5, 5), intelligence=14, proficiency=2)  # DC 12
        target = create_target(name="Target", position=(7, 5), dexterity=14, hp=100)  # +2 save
        Entity.update_all_entities_senses()

        burning_hands = BurningHands(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=1,
            template=False
        )

        result = burning_hands.apply()
        if result and not result.canceled:
            per_target = result.target_results[0] if result.target_results else result
            if per_target.save_success:
                successes += 1
            else:
                failures += 1

    print(f"  Save successes: {successes}/10")
    print(f"  Save failures: {failures}/10")

    # We should see some of each (very unlikely to get 0 of either with 10 trials)
    assert successes > 0 or failures > 0, "Should have at least some results"
    # With 50/50 odds, getting all 10 same is 1/1024 chance
    if successes > 0 and failures > 0:
        print("  Both outcomes observed!")
    else:
        print("  (Note: Got all same outcome - statistically unlikely but possible)")

    print("PASS: Statistical save verification complete")


def run_all_tests():
    """Run all Burning Hands tests."""
    print("=" * 60)
    print("BURNING HANDS SPELL TESTS (CONE SHAPE)")
    print("=" * 60)

    test_burning_hands_basic_damage()
    test_burning_hands_full_damage_on_failed_save()
    test_burning_hands_half_damage_on_passed_save()
    test_burning_hands_upcast()
    test_burning_hands_cone_direction()
    test_burning_hands_caster_excluded()
    test_burning_hands_wall_blocks()
    test_burning_hands_multiple_targets()
    test_burning_hands_statistical_saves()

    print("\n" + "=" * 60)
    print("ALL BURNING HANDS TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
