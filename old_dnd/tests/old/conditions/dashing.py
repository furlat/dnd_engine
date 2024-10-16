from old_dnd.monsters.goblin import create_goblin
from old_dnd.conditions import Dashing
from old_dnd.logger import Logger
from old_dnd.dnd_enums import DurationType
from old_dnd.core import Duration
from old_dnd.tests.printer import print_log_details

def test_dashing_condition():
    print("=== Testing Dashing Condition and Logging ===\n")

    # Create creature
    goblin = create_goblin("Goblin")

    def print_speeds(creature):
        print(f"{creature.name}'s Speeds:")
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj = getattr(creature.speed, speed_type)
            speed_value = speed_obj.apply(creature).total_bonus
            print(f"  {speed_type.capitalize()}: {speed_value} ft")
        print()

    print("Initial speeds:")
    print_speeds(goblin)

    print("Turn 1: Applying Dashing to Goblin")
    dashing_condition = Dashing(duration=Duration(time=2, type=DurationType.ROUNDS), targeted_entity_id=goblin.id)
    condition_log = goblin.condition_manager.add_condition(dashing_condition)
    print_log_details(condition_log)

    print("Speeds after applying Dashing:")
    print_speeds(goblin)

    print("Adding a 'Magic Boost' of 10 ft to walk speed:")
    goblin.speed.walk.self_static.add_bonus("Magic Boost", 10)
    print_speeds(goblin)

    print("\nTurn 2: Advancing duration for Dashing condition")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Speeds on Turn 2 (still Dashing):")
    print_speeds(goblin)

    print("\nTurn 3: Advancing duration for Dashing condition again (condition should be removed)")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Speeds after Dashing expires:")
    print_speeds(goblin)

    print("Removing 'Magic Boost':")
    goblin.speed.walk.remove_effect("Magic Boost")
    print_speeds(goblin)

if __name__ == "__main__":
    test_dashing_condition()