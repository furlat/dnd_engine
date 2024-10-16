from old_dnd.monsters.goblin import create_goblin
from old_dnd.monsters.skeleton import create_skeleton
from old_dnd.conditions import Unconscious
from old_dnd.logger import Logger
from old_dnd.dnd_enums import DurationType, Ability
from old_dnd.core import Duration
from old_dnd.tests.printer import print_log_details

def test_unconscious_condition():
    print("=== Testing Unconscious Condition and Logging ===\n")

    # Create creatures
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    # Set up initial positions
    goblin.sensory.update_origin((0, 0))
    skeleton.sensory.update_origin((1, 0))  # 5 feet away
    goblin.sensory.update_distance_matrix({(1, 0): 5})
    skeleton.sensory.update_distance_matrix({(0, 0): 5})

    def print_creature_status(creature):
        print(f"{creature.name} Status:")
        print(f"  Actions: {creature.action_economy.actions.apply(creature).total_bonus}")
        print(f"  Bonus Actions: {creature.action_economy.bonus_actions.apply(creature).total_bonus}")
        print(f"  Reactions: {creature.action_economy.reactions.apply(creature).total_bonus}")
        print(f"  Speed: {creature.speed.walk.apply(creature).total_bonus}")
        print(f"  AC: {creature.armor_class.ac.apply(creature).total_bonus}")
        print()

    print("Initial state:")
    print_creature_status(goblin)

    print("Applying Unconscious to Goblin")
    unconscious_condition = Unconscious(duration=Duration(time=2, type=DurationType.ROUNDS), targeted_entity_id=goblin.id)
    condition_log = goblin.condition_manager.add_condition(unconscious_condition)
    print_log_details(condition_log)

    print("Goblin status after Unconscious:")
    print_creature_status(goblin)

    print("Skeleton attacks Unconscious Goblin (within 5 feet)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("Goblin attempts Strength saving throw")
    str_save = goblin.perform_saving_throw(Ability.STR, 10)
    print_log_details(str_save)

    print("Goblin attempts Dexterity saving throw")
    dex_save = goblin.perform_saving_throw(Ability.DEX, 10)
    print_log_details(dex_save)

    print("\nMoving Skeleton away from Goblin")
    skeleton.sensory.update_origin((3, 0))  # 15 feet away
    goblin.sensory.update_distance_matrix({(3, 0): 15})
    skeleton.sensory.update_distance_matrix({(0, 0): 15})

    print("Skeleton attacks Unconscious Goblin (beyond 5 feet)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("\nAdvancing duration for Unconscious condition")
    for _ in range(2):
        advance_result = goblin.condition_manager.advance_durations()
        for log in advance_result:
            print_log_details(log)

    print("Goblin status after Unconscious expires:")
    print_creature_status(goblin)

    print("Goblin attacks Skeleton (no longer Unconscious)")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

if __name__ == "__main__":
    test_unconscious_condition()