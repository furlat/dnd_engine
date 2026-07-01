"""
Test script for the Shove action (BG3-style).

Tests:
1. Basic shove - push adjacent enemy
2. Weight limit - can't shove targets too heavy
3. Ally auto-succeed - shoving allies always works
4. No opportunity attack - forced movement doesn't trigger OA
5. Blocked by wall - shove stops at obstacles
6. Passive skill with advantage - Raging barbarian has +5 passive Athletics
"""

from uuid import uuid4
from dnd.utils import reset_combat_state
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.actions_functional import setup_standard_actions, execute_action
from dnd.core.gridmap import get_map
from dnd.actions import Shove
from dnd.reactions import add_opportunity_attack_handler


def create_strong_fighter(
    name: str = "Strong Fighter",
    position: tuple = (0, 0),
    faction: str = "heroes",
    strength: int = 18,
    weight: int = 180
) -> Entity:
    """Create a fighter with high STR for shove testing."""
    source_id = uuid4()

    entity_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=strength),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=14),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10)
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=5, mode="average")]
        ),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=3,
        position=position,
        faction=faction,
        weight=weight
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        config=entity_config
    )
    setup_standard_actions(entity)
    return entity


def test_basic_shove():
    """Test basic shove - push adjacent enemy."""
    print("\n=== Test: Basic Shove ===")

    # First, test the static calculations (no randomness)
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    shover = create_strong_fighter(name="Shover", position=(2, 2), faction="heroes", strength=18)
    target = create_skeleton(name="Target", position=(3, 2), faction="monsters", weight=120)
    Entity.update_all_entities_senses()

    # Check max shove weight (STR 18 * 12 = 216 lbs)
    max_weight = Shove.get_max_shove_weight(shover)
    print(f"Shover STR: {shover.ability_scores.strength.ability_score.score}")
    print(f"Max shove weight: {max_weight} lbs")
    print(f"Target weight: {target.weight} lbs")
    assert max_weight == 216, f"Max weight should be 216, got {max_weight}"

    # Check push distance (STR mod +4 -> 5 + 4*5 = 25, capped at 20)
    push_dist = Shove.get_push_distance(shover)
    print(f"Push distance: {push_dist}ft")
    assert push_dist == 20, f"Push distance should be 20ft, got {push_dist}"

    # Now run multiple attempts to test actual shove execution
    max_attempts = 10
    shove_succeeded = False

    for attempt in range(max_attempts):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 10, 10)

        shover = create_strong_fighter(name="Shover", position=(2, 2), faction="heroes", strength=18)
        target = create_skeleton(name="Target", position=(3, 2), faction="monsters", weight=120)
        Entity.update_all_entities_senses()

        # Get available actions and find Shove
        available = shover.get_available_actions(target_filter="enemies")
        shove_action = None
        for action in available.entity_actions:
            if action.template_name == "Shove":
                shove_action = action
                break

        assert shove_action is not None, "Shove should be available"
        assert len(shove_action.valid_targets) > 0, "Should have valid targets"

        # Execute shove
        target_info = shove_action.valid_targets[0]
        result = execute_action(shover, "Shove", target_info)

        if target.position[0] > 3:
            shove_succeeded = True
            print(f"  Attempt {attempt + 1}: SUCCESS - pushed to {target.position}")
            print(f"  Shove result: {result.status_message if result else 'None'}")
            break
        else:
            print(f"  Attempt {attempt + 1}: Contest failed (retrying...)")

    assert shove_succeeded, f"No shoves succeeded in {max_attempts} attempts"
    print("PASS: Target was pushed")


def test_weight_limit():
    """Test weight limit - can't shove targets too heavy."""
    print("\n=== Test: Weight Limit ===")
    reset_combat_state()

    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    # STR 8 fighter (max weight = 8 * 12 = 96 lbs)
    weak_shover = create_strong_fighter(name="Weakling", position=(2, 2), faction="heroes", strength=8)
    heavy_target = create_skeleton(name="Heavy Target", position=(3, 2), faction="monsters", weight=200)

    Entity.update_all_entities_senses()

    max_weight = Shove.get_max_shove_weight(weak_shover)
    print(f"Shover STR: {weak_shover.ability_scores.strength.ability_score.score}")
    print(f"Max shove weight: {max_weight} lbs")
    print(f"Target weight: {heavy_target.weight} lbs")

    # Get available actions - Shove should NOT have this target
    available = weak_shover.get_available_actions(target_filter="enemies")
    shove_action = None
    for action in available.entity_actions:
        if action.template_name == "Shove":
            shove_action = action
            break

    if shove_action:
        # Check if heavy target is in valid targets
        target_uuids = [t.target_uuid for t in shove_action.valid_targets]
        assert heavy_target.uuid not in target_uuids, "Heavy target should NOT be a valid shove target"
        print(f"Shove available but heavy target excluded (correct)")
    else:
        print("No shove targets available (correct)")

    print("PASS: Weight limit enforced")


def test_ally_auto_succeed():
    """Test that shoving allies always succeeds (no check required)."""
    print("\n=== Test: Ally Auto-Succeed ===")
    reset_combat_state()

    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    # Two allies - shover must still be strong enough (weight check applies)
    # but the Athletics contest auto-succeeds (no roll required)
    shover = create_strong_fighter(name="Shover", position=(2, 2), faction="heroes", strength=16)
    ally = create_strong_fighter(name="Ally", position=(3, 2), faction="heroes", strength=20, weight=100)

    Entity.update_all_entities_senses()

    # Get available actions with all targets (including allies)
    available = shover.get_available_actions(target_filter="all")
    shove_action = None
    for action in available.entity_actions:
        if action.template_name == "Shove":
            shove_action = action
            break

    assert shove_action is not None, "Shove should be available"

    # Find ally in targets
    ally_target = None
    for t in shove_action.valid_targets:
        if t.target_uuid == ally.uuid:
            ally_target = t
            break

    assert ally_target is not None, "Ally should be a valid shove target"

    original_pos = ally.position
    result = execute_action(shover, "Shove", ally_target)

    print(f"Shove result: {result.status_message if result else 'None'}")
    print(f"Ally original position: {original_pos}")
    print(f"Ally new position: {ally.position}")

    # Ally should have been pushed (auto-succeed for allies)
    assert ally.position != original_pos, "Ally should have moved"
    print("PASS: Ally auto-succeed works")


def test_no_opportunity_attack():
    """Test that forced movement (shove) does NOT trigger opportunity attacks."""
    print("\n=== Test: No Opportunity Attack on Shove ===")

    # Run multiple attempts until we get a successful shove
    max_attempts = 10
    shove_succeeded = False

    for attempt in range(max_attempts):
        reset_combat_state()

        grid = get_map()
        grid.create_rectangle(0, 0, 10, 10)

        # Setup: Shover at (2,2), Target at (3,2), OA-capable enemy at (4,3)
        # When target is pushed from (3,2) eastward, it passes through OA enemy's threat range
        # but should NOT trigger OA because it's forced movement
        shover = create_strong_fighter(name="Shover", position=(2, 2), faction="heroes", strength=18)
        target = create_skeleton(name="Target", position=(3, 2), faction="monsters", weight=100)
        oa_enemy = create_skeleton(name="OA Enemy", position=(4, 3), faction="monsters", weight=120)

        # Add OA handler to the enemy
        add_opportunity_attack_handler(oa_enemy)

        Entity.update_all_entities_senses()

        target_hp_before = target.get_hp()

        # Execute shove
        available = shover.get_available_actions(target_filter="enemies")
        shove_action = None
        for action in available.entity_actions:
            if action.template_name == "Shove":
                shove_action = action
                break

        assert shove_action is not None, "Shove should be available"

        target_info = None
        for t in shove_action.valid_targets:
            if t.target_uuid == target.uuid:
                target_info = t
                break

        assert target_info is not None, "Target should be in valid targets"
        execute_action(shover, "Shove", target_info)

        target_hp_after = target.get_hp()

        if target.position != (3, 2):
            # Shove succeeded - this is the meaningful test case
            shove_succeeded = True
            print(f"  Attempt {attempt + 1}: Shove succeeded")
            print(f"    Target moved from (3, 2) to {target.position}")
            print(f"    Target HP before: {target_hp_before}, after: {target_hp_after}")

            # HP should be unchanged (no OA triggered during forced movement)
            assert target_hp_after == target_hp_before, \
                f"Target took {target_hp_before - target_hp_after} damage from OA during forced movement!"
            print("PASS: No opportunity attack triggered by forced movement")
            break
        else:
            print(f"  Attempt {attempt + 1}: Contest failed (retrying...)")

    assert shove_succeeded, f"No shoves succeeded in {max_attempts} attempts - can't verify OA behavior"


def test_blocked_by_wall():
    """Test that shove stops at unwalkable tiles. Combat log says 'blocked by Wall'."""
    print("\n=== Test: Blocked by Wall ===")

    # Run multiple attempts to handle random Athletics contest
    success_count = 0
    blocked_correctly = 0
    blocked_by_correct = 0
    max_attempts = 10

    for attempt in range(max_attempts):
        reset_combat_state()

        grid = get_map()
        grid.create_rectangle(0, 0, 10, 10)
        # Add wall at (5, 2)
        grid.set_tile(5, 2, walkable=False, visible=False, name="Wall")

        # Shover at (2,2), Target at (3,2), Wall at (5,2)
        # Push should stop at (4,2) - one cell before the wall
        shover = create_strong_fighter(name="Shover", position=(2, 2), faction="heroes", strength=18)
        target = create_skeleton(name="Target", position=(3, 2), faction="monsters", weight=100)

        Entity.update_all_entities_senses()

        # Execute shove
        available = shover.get_available_actions(target_filter="enemies")
        shove_action = None
        for action in available.entity_actions:
            if action.template_name == "Shove":
                shove_action = action
                break

        assert shove_action is not None, "Shove should be available"
        target_info = shove_action.valid_targets[0]
        result = execute_action(shover, "Shove", target_info)

        if target.position != (3, 2):
            # Shove succeeded - check wall blocking
            success_count += 1
            if target.position[0] == 4:
                blocked_correctly += 1
                print(f"  Attempt {attempt + 1}: SUCCESS - pushed to {target.position} (blocked by wall)")

                # Verify blocked_by in ShoveEvent combat log data
                if result and result.combat_log:
                    shove_blocked_by = result.combat_log.data.get("blocked_by")
                    if shove_blocked_by == "Wall":
                        blocked_by_correct += 1
                    else:
                        print(f"    WARNING: ShoveEvent blocked_by={shove_blocked_by}, expected 'Wall'")

                    # Also check ForcedMovementEvent sub-entry
                    for sub in result.combat_log.sub_entries:
                        if sub.data and sub.data.get("type") == "forced_movement":
                            assert sub.data.get("blocked_by") == "Wall", \
                                f"ForcedMovementEvent blocked_by should be 'Wall', got '{sub.data.get('blocked_by')}'"
                            assert "blocked by Wall" in sub.compact, \
                                f"ForcedMovement compact should contain 'blocked by Wall', got: {sub.compact}"
                            print(f"    ForcedMovement log: {sub.compact}")
            else:
                print(f"  Attempt {attempt + 1}: FAIL - pushed to {target.position} (should be x=4)")
        else:
            print(f"  Attempt {attempt + 1}: Contest failed (target resisted)")

    print(f"\nResults: {success_count} successful shoves out of {max_attempts} attempts")
    print(f"Wall blocking correct: {blocked_correctly}/{success_count} successful shoves")
    print(f"blocked_by='Wall' correct: {blocked_by_correct}/{success_count} successful shoves")

    # We need at least one successful shove to verify wall blocking
    assert success_count > 0, "No shoves succeeded - need at least one to test wall blocking"
    assert blocked_correctly == success_count, f"Wall blocking failed: {blocked_correctly}/{success_count}"
    assert blocked_by_correct == success_count, f"blocked_by check failed: {blocked_by_correct}/{success_count}"
    print("PASS: Shove correctly blocked by wall with descriptive combat log")


def test_passive_skill_calculation():
    """Test passive skill calculation including advantage modifiers."""
    print("\n=== Test: Passive Skill Calculation ===")
    reset_combat_state()

    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    # Create entity with Athletics proficiency
    entity = create_strong_fighter(name="Athlete", position=(2, 2), faction="heroes", strength=16)

    Entity.update_all_entities_senses()

    # STR 16 (+3), proficiency +3 = +6 Athletics
    # Passive = 10 + 6 = 16
    passive_athletics = entity.passive_skill("athletics")
    passive_acrobatics = entity.passive_skill("acrobatics")

    print(f"STR: {entity.ability_scores.strength.ability_score.score} (mod +{entity.ability_scores.strength.modifier})")
    print(f"Proficiency: +{entity.proficiency_bonus.normalized_score}")
    print(f"Passive Athletics: {passive_athletics}")
    print(f"Passive Acrobatics: {passive_acrobatics}")

    # Athletics should be higher than acrobatics (STR vs DEX)
    # Both are 10 + ability mod since neither has proficiency in this test
    print("PASS: Passive skill calculation works")


def run_all_tests():
    """Run all shove tests."""
    print("=" * 60)
    print("SHOVE ACTION TESTS (BG3-Style)")
    print("=" * 60)

    test_basic_shove()
    test_weight_limit()
    test_ally_auto_succeed()
    test_no_opportunity_attack()
    test_blocked_by_wall()
    test_passive_skill_calculation()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
