from old_dnd.monsters.goblin import create_goblin
from old_dnd.monsters.skeleton import create_skeleton
from old_dnd.conditions import Paralyzed
from old_dnd.logger import Logger
from old_dnd.dnd_enums import DurationType, Ability
from old_dnd.core import Duration
from old_dnd.tests.printer import print_log_details

def test_paralyzed_condition():
    print("=== Testing Paralyzed Condition and Logging ===\n")

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
        print()

    print("Initial state:")
    print_creature_status(goblin)

    print("Applying Paralyzed to Goblin")
    paralyzed_condition = Paralyzed(duration=Duration(time=2, type=DurationType.ROUNDS), targeted_entity_id=goblin.id)
    condition_log = goblin.condition_manager.add_condition(paralyzed_condition)
    print_log_details(condition_log)

    print("Goblin status after Paralyzed:")
    print_creature_status(goblin)

    print("Skeleton attacks Paralyzed Goblin (within 5 feet)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("Goblin attempts Strength saving throw")
    str_save = goblin.perform_saving_throw(Ability.STR, 10)
    print_log_details(str_save)

    print("Goblin attempts Dexterity saving throw")
    dex_save = goblin.perform_saving_throw(Ability.DEX, 10)
    print_log_details(dex_save)

    print("\nMoving Skeleton away from Goblin")
    skeleton.sensory.update_origin((2, 0))  # 10 feet away
    goblin.sensory.update_distance_matrix({(2, 0): 10})
    skeleton.sensory.update_distance_matrix({(0, 0): 10})

    print("Skeleton attacks Paralyzed Goblin (beyond 5 feet)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("\nAdvancing duration for Paralyzed condition")
    for _ in range(2):
        advance_result = goblin.condition_manager.advance_durations()
        for log in advance_result:
            print_log_details(log)

    print("Goblin status after Paralyzed expires:")
    print_creature_status(goblin)

    print("Skeleton attacks Goblin (no longer Paralyzed)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

if __name__ == "__main__":
    test_paralyzed_condition()