from old_dnd.monsters.goblin import create_goblin
from old_dnd.monsters.skeleton import create_skeleton
from old_dnd.conditions import Poisoned
from old_dnd.logger import Logger
from old_dnd.dnd_enums import DurationType, Skills
from old_dnd.core import Duration
from old_dnd.tests.printer import print_log_details

def test_poisoned_condition():
    print("=== Testing Poisoned Condition and Logging ===\n")

    # Create creatures
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    print("Initial state:")
    print("Goblin attacks Skeleton (before Poisoned)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("Goblin performs Stealth check (before Poisoned)")
    stealth_result = goblin.perform_skill_check(Skills.STEALTH, 15)
    print_log_details(stealth_result)

    print("\nApplying Poisoned to Goblin")
    poisoned_condition = Poisoned(duration=Duration(time=3, type=DurationType.ROUNDS), targeted_entity_id=goblin.id)
    condition_log = goblin.condition_manager.add_condition(poisoned_condition)
    print_log_details(condition_log)

    print("Goblin attacks Skeleton (while Poisoned)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("Goblin performs Perception check (while Poisoned)")
    perception_result = goblin.perform_skill_check(Skills.PERCEPTION, 15)
    print_log_details(perception_result)

    print("\nAdvancing duration for Poisoned condition")
    for _ in range(3):
        advance_result = goblin.condition_manager.advance_durations()
        for log in advance_result:
            print_log_details(log)

    print("Goblin attacks Skeleton (after Poisoned expires)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("Goblin performs Intimidation check (after Poisoned expires)")
    intimidation_result = goblin.perform_skill_check(Skills.INTIMIDATION, 15)
    print_log_details(intimidation_result)
    print(intimidation_result)

if __name__ == "__main__":
    test_poisoned_condition()