from old_dnd.monsters.goblin import create_goblin
from old_dnd.conditions import Deafened
from old_dnd.logger import Logger
from old_dnd.dnd_enums import DurationType, Skills
from old_dnd.core import Duration
from old_dnd.tests.printer import print_log_details

def test_deafened_condition():
    print("=== Testing Deafened Condition and Logging ===\n")

    # Create creature
    goblin = create_goblin("Goblin")

    print("Turn 1: Applying Deafened to Goblin")
    deafened_condition = Deafened(duration=Duration(time=2, type=DurationType.ROUNDS), targeted_entity_id=goblin.id)
    condition_log = goblin.condition_manager.add_condition(deafened_condition)
    print_log_details(condition_log)

    print("Goblin attempts a normal Perception check:")
    perception_result = goblin.perform_skill_check(Skills.PERCEPTION, 15, context={'requires_hearing': False})
    print_log_details(perception_result)

    print("Goblin attempts a hearing-based Perception check (should auto-fail):")
    hearing_perception_result = goblin.perform_skill_check(Skills.PERCEPTION, 15, context={'requires_hearing': True})
    print_log_details(hearing_perception_result)

    print("Goblin attempts a Performance check (often involves hearing, should auto-fail):")
    performance_result = goblin.perform_skill_check(Skills.PERFORMANCE, 15, context={'requires_hearing': True})
    print_log_details(performance_result)

    print("Goblin attempts an Athletics check (not hearing-dependent):")
    athletics_result = goblin.perform_skill_check(Skills.ATHLETICS, 15, context={'requires_hearing': False})
    print_log_details(athletics_result)

    print("\nTurn 2: Advancing duration for Deafened condition")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("\nTurn 3: Advancing duration for Deafened condition again (condition should be removed)")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Goblin attempts a hearing-based Perception check after Deafened expires:")
    final_perception_result = goblin.perform_skill_check(Skills.PERCEPTION, 15, context={'requires_hearing': True})
    print_log_details(final_perception_result)

if __name__ == "__main__":
    test_deafened_condition()