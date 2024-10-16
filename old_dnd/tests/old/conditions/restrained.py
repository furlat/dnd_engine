from old_dnd.monsters.goblin import create_goblin
from old_dnd.monsters.skeleton import create_skeleton
from old_dnd.conditions import Restrained
from old_dnd.logger import Logger
from old_dnd.dnd_enums import DurationType, Ability
from old_dnd.core import Duration
from old_dnd.tests.printer import print_log_details

def test_restrained_condition():
    print("=== Testing Restrained Condition and Logging ===\n")

    # Create creatures
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    def print_creature_status(creature):
        print(f"{creature.name} Status:")
        print(f"  Speed: {creature.speed.walk.apply(creature).total_bonus}")
        print(f"  Attack Bonus: {creature.attacks_manager.hit_bonus.apply(creature).advantage_tracker.status}")
        print(f"  DEX Save Bonus: {creature.saving_throws.get_ability(Ability.DEX).bonus.apply(creature).advantage_tracker.status}")
        print(f"  AC: {creature.armor_class.ac.apply(creature).total_bonus}")
        print()

    print("Initial state:")
    print_creature_status(goblin)

    print("Applying Restrained to Goblin")
    restrained_condition = Restrained(duration=Duration(time=2, type=DurationType.ROUNDS), targeted_entity_id=goblin.id)
    condition_log = goblin.condition_manager.add_condition(restrained_condition)
    print_log_details(condition_log)

    print("Goblin status after Restrained:")
    print_creature_status(goblin)

    print("Goblin attacks Skeleton (while Restrained)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("Skeleton attacks Goblin (Restrained)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("Goblin attempts Dexterity saving throw")
    dex_save = goblin.perform_saving_throw(Ability.DEX, 10)
    print_log_details(dex_save)

    print("\nAdvancing duration for Restrained condition")
    for _ in range(2):
        advance_result = goblin.condition_manager.advance_durations()
        for log in advance_result:
            print_log_details(log)

    print("Goblin status after Restrained expires:")
    print_creature_status(goblin)

    print("Goblin attacks Skeleton (no longer Restrained)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("Skeleton attacks Goblin (no longer Restrained)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

if __name__ == "__main__":
    test_restrained_condition()