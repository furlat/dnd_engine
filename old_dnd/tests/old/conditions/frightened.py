from old_dnd.monsters.goblin import create_goblin
from old_dnd.monsters.skeleton import create_skeleton
from old_dnd.conditions import Frightened
from old_dnd.logger import Logger
from old_dnd.dnd_enums import DurationType, Ability, Skills
from old_dnd.core import Duration
from old_dnd.tests.printer import print_log_details
from old_dnd.spatial import RegistryHolder

def test_frightened_condition():
    print("=== Testing Frightened Condition and Logging ===\n")

    # Create creatures
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    # Set up initial positions and visibility
    goblin.sensory.update_origin((0, 0))
    skeleton.sensory.update_origin((1, 1))
    visible_tiles = {(1, 1)}  # Skeleton is visible to Goblin
    goblin.sensory.update_fov(visible_tiles)

    print("Initial state:")
    print("Goblin attacks Skeleton (before Frightened)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("Goblin performs Stealth check (before Frightened)")
    stealth_result = goblin.perform_skill_check(Skills.STEALTH, 15)
    print_log_details(stealth_result)

    print("\nApplying Frightened to Goblin (caused by Skeleton)")
    frightened_condition = Frightened(duration=Duration(time=2, type=DurationType.ROUNDS), targeted_entity_id=goblin.id, source_entity_id=skeleton.id)
    condition_log = goblin.condition_manager.add_condition(frightened_condition)
    print_log_details(condition_log)

    print("Goblin attacks Skeleton (while Frightened and can see Skeleton)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("Goblin performs Perception check (while Frightened and can see Skeleton)")
    perception_result = goblin.perform_skill_check(Skills.PERCEPTION, 15)
    print_log_details(perception_result)

    print("\nUpdating visibility: Skeleton is no longer visible to Goblin")
    goblin.sensory.update_fov(set())  # Empty set means Skeleton is not visible

    print("Goblin attacks Skeleton (while Frightened but cannot see Skeleton)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("Goblin performs Athletics check (while Frightened but cannot see Skeleton)")
    athletics_result = goblin.perform_skill_check(Skills.ATHLETICS, 15)
    print_log_details(athletics_result)

    print("\nAdvancing duration for Frightened condition")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("\nAdvancing duration again (condition should be removed)")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Goblin attacks Skeleton (after Frightened expires)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

if __name__ == "__main__":
    test_frightened_condition()