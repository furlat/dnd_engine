from old_dnd.monsters.goblin import create_goblin
from old_dnd.monsters.skeleton import create_skeleton
from old_dnd.conditions import Incapacitated
from old_dnd.logger import Logger
from old_dnd.dnd_enums import DurationType, ActionType
from old_dnd.core import Duration
from old_dnd.tests.printer import print_log_details

def test_incapacitated_condition():
    print("=== Testing Incapacitated Condition and Logging ===\n")

    # Create creature
    goblin = create_goblin("Goblin")

    def print_action_economy(creature):
        print(f"{creature.name}'s Action Economy:")
        print(f"  Actions: {creature.action_economy.actions.apply(creature).total_bonus}")
        print(f"  Bonus Actions: {creature.action_economy.bonus_actions.apply(creature).total_bonus}")
        print(f"  Reactions: {creature.action_economy.reactions.apply(creature).total_bonus}")
        print()

    def print_speeds(creature):
        print(f"{creature.name}'s Speeds:")
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj = getattr(creature.speed, speed_type)
            speed_value = speed_obj.apply(creature).total_bonus
            print(f"  {speed_type.capitalize()}: {speed_value} ft")
        print()

    print("Initial state:")
    print_action_economy(goblin)
    print_speeds(goblin)

    print("Applying Incapacitated to Goblin")
    incapacitated_condition = Incapacitated(duration=Duration(time=2, type=DurationType.ROUNDS), targeted_entity_id=goblin.id)
    condition_log = goblin.condition_manager.add_condition(incapacitated_condition)
    print_log_details(condition_log)

    print("Action economy and speeds after applying Incapacitated:")
    print_action_economy(goblin)
    print_speeds(goblin)

    print("Adding a 'Haste' bonus of 1 action:")
    goblin.action_economy.actions.self_static.add_bonus("Haste", 1)
    print_action_economy(goblin)

    print("\nAdvancing duration for Incapacitated condition")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Action economy and speeds on second turn (still Incapacitated):")
    print_action_economy(goblin)
    print_speeds(goblin)

    print("\nAdvancing duration again (condition should be removed)")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Action economy and speeds after Incapacitated expires:")
    print_action_economy(goblin)
    print_speeds(goblin)

    print("Removing 'Haste' bonus:")
    goblin.action_economy.actions.remove_effect("Haste")
    print_action_economy(goblin)

if __name__ == "__main__":
    test_incapacitated_condition()