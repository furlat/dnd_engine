from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Invisible
from dnd.logger import Logger
from dnd.dnd_enums import DurationType, SensesType
from dnd.core import Duration, Sense
from dnd.tests.printer import print_log_details

def test_invisible_condition():
    print("=== Testing Invisible Condition and Logging ===\n")

    # Create creatures
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    # Set up initial positions and visibility
    goblin.sensory.update_origin((0, 0))
    skeleton.sensory.update_origin((1, 1))
    visible_tiles = {(1, 1)}
    goblin.sensory.update_fov(visible_tiles)
    skeleton.sensory.update_fov({(0, 0)})

    print("Initial state:")
    print("Goblin attacks Skeleton (before Invisible)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("Applying Invisible to Goblin")
    invisible_condition = Invisible(duration=Duration(time=3, type=DurationType.ROUNDS), targeted_entity_id=goblin.id)
    condition_log = goblin.condition_manager.add_condition(invisible_condition)
    print_log_details(condition_log)

    print("Goblin attacks Skeleton (while Invisible)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("Skeleton attacks Goblin (while Goblin is Invisible)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("\nAdding Truesight to Skeleton")
    skeleton.sensory.senses.append(Sense(type=SensesType.TRUESIGHT, range=30))

    print("Skeleton attacks Goblin (with Truesight)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("Goblin attacks Skeleton (Skeleton has Truesight)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("\nRemoving Truesight and adding Tremorsense to Skeleton")
    skeleton.sensory.senses = [sense for sense in skeleton.sensory.senses if sense.type != SensesType.TRUESIGHT]
    skeleton.sensory.senses.append(Sense(type=SensesType.TREMORSENSE, range=30))

    print("Skeleton attacks Goblin (with Tremorsense)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("\nAdvancing duration for Invisible condition")
    for _ in range(3):
        advance_result = goblin.condition_manager.advance_durations()
        for log in advance_result:
            print_log_details(log)

    print("Goblin attacks Skeleton (after Invisible expires)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

if __name__ == "__main__":
    test_invisible_condition()