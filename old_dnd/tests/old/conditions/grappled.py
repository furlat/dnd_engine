from old_dnd.monsters.goblin import create_goblin
from old_dnd.monsters.skeleton import create_skeleton
from old_dnd.conditions import Grappled
from old_dnd.logger import Logger
from old_dnd.dnd_enums import DurationType
from old_dnd.core import Duration
from old_dnd.tests.printer import print_log_details

def test_grappled_condition():
    print("=== Testing Grappled Condition and Logging ===\n")

    # Create creatures
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    def print_speeds(creature):
        print(f"{creature.name}'s Speeds:")
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj = getattr(creature.speed, speed_type)
            speed_value_obj = speed_obj.apply(creature)
            speed_value = speed_value_obj.total_bonus
            print(f"  {speed_type.capitalize()}: {speed_value} ft")
            max_constraints = speed_value_obj.max_constraints
        print()

    print("Initial speeds:")
    print_speeds(goblin)

    print("Applying Grappled to Goblin")
    grappled_condition = Grappled(duration=Duration(time=2, type=DurationType.ROUNDS), targeted_entity_id=goblin.id, source_entity_id=skeleton.id)
    condition_log = goblin.condition_manager.add_condition(grappled_condition)
    print_log_details(condition_log)

    print("Speeds after applying Grappled:")
    print_speeds(goblin)

    print("Adding a 'Magic Boost' of 10 ft to walk speed:")
    goblin.speed.walk.self_static.add_bonus("Magic Boost", 10)
    print_speeds(goblin)

    print("\nAdvancing duration for Grappled condition")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Speeds on second turn (still Grappled):")
    print_speeds(goblin)

    print("\nAdvancing duration for Grappled condition again (condition should be removed)")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Speeds after Grappled expires:")
    print_speeds(goblin)

    print("Removing 'Magic Boost':")
    goblin.speed.walk.remove_effect("Magic Boost")
    print_speeds(goblin)

if __name__ == "__main__":
    test_grappled_condition()