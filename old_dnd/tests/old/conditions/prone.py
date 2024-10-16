from old_dnd.monsters.goblin import create_goblin
from old_dnd.monsters.skeleton import create_skeleton
from old_dnd.conditions import Prone
from old_dnd.logger import Logger
from old_dnd.dnd_enums import DurationType
from old_dnd.core import Duration
from old_dnd.tests.printer import print_log_details

def test_prone_condition():
    print("=== Testing Prone Condition and Logging ===\n")

    # Create creatures
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    # Set up initial positions
    goblin.sensory.update_origin((0, 0))
    skeleton.sensory.update_origin((1, 0))  # 5 feet away
    goblin.sensory.update_distance_matrix({(1, 0): 5})
    skeleton.sensory.update_distance_matrix({(0, 0): 5})

    print("Initial state:")
    print("Goblin attacks Skeleton (before Prone)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("\nApplying Prone to Goblin")
    prone_condition = Prone(duration=Duration(time=3, type=DurationType.ROUNDS), targeted_entity_id=goblin.id)
    condition_log = goblin.condition_manager.add_condition(prone_condition)
    print_log_details(condition_log)

    print("Goblin attacks Skeleton (while Prone)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("Skeleton attacks Goblin (Prone, within 5 feet)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("\nMoving Skeleton away from Goblin")
    skeleton.sensory.update_origin((3, 0))  # 15 feet away
    goblin.sensory.update_distance_matrix({(3, 0): 15})
    skeleton.sensory.update_distance_matrix({(0, 0): 15})

    print("Skeleton attacks Goblin (Prone, beyond 5 feet)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("Goblin attacks Skeleton (Prone, ranged attack)")
    attack_result = goblin.perform_ranged_attack(skeleton.id)
    print_log_details(attack_result)

    print("\nAdvancing duration for Prone condition")
    for _ in range(3):
        advance_result = goblin.condition_manager.advance_durations()
        for log in advance_result:
            print_log_details(log)

    print("Goblin attacks Skeleton (after Prone expires)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

if __name__ == "__main__":
    test_prone_condition()