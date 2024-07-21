from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Stunned
from dnd.logger import Logger
from dnd.dnd_enums import DurationType, Ability
from dnd.core import Duration
from dnd.tests.printer import print_log_details

def test_stunned_condition():
    print("=== Testing Stunned Condition and Logging ===\n")

    # Create creatures
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    def print_creature_status(creature):
        print(f"{creature.name} Status:")
        print(f"  Actions: {creature.action_economy.actions.apply(creature).total_bonus}")
        print(f"  Bonus Actions: {creature.action_economy.bonus_actions.apply(creature).total_bonus}")
        print(f"  Reactions: {creature.action_economy.reactions.apply(creature).total_bonus}")
        print(f"  Speed: {creature.speed.walk.apply(creature).total_bonus}")
        print()

    print("Initial state:")
    print_creature_status(goblin)

    print("Applying Stunned to Goblin")
    stunned_condition = Stunned(duration=Duration(time=2, type=DurationType.ROUNDS), targeted_entity_id=goblin.id)
    condition_log = goblin.condition_manager.add_condition(stunned_condition)
    print_log_details(condition_log)

    print("Goblin status after Stunned:")
    print_creature_status(goblin)

    print("Skeleton attacks Stunned Goblin")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("Goblin attempts Strength saving throw")
    str_save = goblin.perform_saving_throw(Ability.STR, 10)
    print_log_details(str_save)

    print("Goblin attempts Dexterity saving throw")
    dex_save = goblin.perform_saving_throw(Ability.DEX, 10)
    print_log_details(dex_save)

    print("Goblin attempts Wisdom saving throw")
    wis_save = goblin.perform_saving_throw(Ability.WIS, 10)
    print_log_details(wis_save)

    print("\nAdvancing duration for Stunned condition")
    for _ in range(2):
        advance_result = goblin.condition_manager.advance_durations()
        for log in advance_result:
            print_log_details(log)

    print("Goblin status after Stunned expires:")
    print_creature_status(goblin)

    print("Skeleton attacks Goblin (no longer Stunned)")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

if __name__ == "__main__":
    test_stunned_condition()