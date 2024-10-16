from old_dnd.monsters.goblin import create_goblin
from old_dnd.monsters.skeleton import create_skeleton
from old_dnd.conditions import Dodging
from old_dnd.logger import Logger
from old_dnd.dnd_enums import DurationType, Ability
from old_dnd.core import Duration
from old_dnd.tests.printer import print_log_details

def test_dodging_condition():
    print("=== Testing Dodging Condition and Logging ===\n")

    # Create creatures
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    print("Initial state:")
    print("Skeleton attacks Goblin (before Dodging)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("Goblin performs Dexterity saving throw (before Dodging)")
    dex_save_result = goblin.perform_saving_throw(Ability.DEX, 15)
    print_log_details(dex_save_result)

    print("\nTurn 1: Applying Dodging to Goblin")
    dodging_condition = Dodging(duration=Duration(time=2, type=DurationType.ROUNDS), targeted_entity_id=goblin.id)
    condition_log = goblin.condition_manager.add_condition(dodging_condition)
    print_log_details(condition_log)

    print("Skeleton attacks Goblin (while Dodging)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("Goblin performs Dexterity saving throw (while Dodging)")
    dex_save_result = goblin.perform_saving_throw(Ability.DEX, 15)
    print_log_details(dex_save_result)

    print("\nTurn 2: Advancing duration for Dodging condition")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Skeleton attacks Goblin (still Dodging)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("\nTurn 3: Advancing duration for Dodging condition again (condition should be removed)")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Skeleton attacks Goblin (after Dodging expires)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("Goblin performs Dexterity saving throw (after Dodging expires)")
    dex_save_result = goblin.perform_saving_throw(Ability.DEX, 15)
    print_log_details(dex_save_result)

if __name__ == "__main__":
    test_dodging_condition()