from dnd.statsblock import StatsBlock
from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Incapacitated, Duration, DurationType
from dnd.core import ActionType

def print_creature_details(creature: StatsBlock):
    print(f"{creature.name} Details:")
    print(f"HP: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Action Economy:")
    print(f"  Actions: {creature.action_economy.actions.get_value(creature)}")
    print(f"  Bonus Actions: {creature.action_economy.bonus_actions.get_value(creature)}")
    print(f"  Reactions: {creature.action_economy.reactions.get_value(creature)}")
    print(f"Active Conditions: {', '.join([cond for cond in creature.active_conditions.keys()])}")

def check_action_availability(creature: StatsBlock, action_type: ActionType):
    if action_type == ActionType.ACTION:
        available = creature.action_economy.actions.get_value(creature) > 0
    elif action_type == ActionType.BONUS_ACTION:
        available = creature.action_economy.bonus_actions.get_value(creature) > 0
    elif action_type == ActionType.REACTION:
        available = creature.action_economy.reactions.get_value(creature) > 0
    else:
        available = False
    
    print(f"{creature.name} attempts to use a {action_type.value}: {'Available' if available else 'Not Available'}")
    return available

def test_incapacitated_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Incapacitated Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    
    print("\n2. Checking action availability before Incapacitated")
    check_action_availability(goblin, ActionType.ACTION)
    check_action_availability(goblin, ActionType.BONUS_ACTION)
    check_action_availability(goblin, ActionType.REACTION)
    
    print("\n3. Applying Incapacitated condition to Goblin")
    incapacitated_condition = Incapacitated(name="Incapacitated", duration=Duration(time=2, type=DurationType.ROUNDS))
    goblin.apply_condition(incapacitated_condition)
    print_creature_details(goblin)
    
    print("\n4. Checking action availability while Incapacitated")
    check_action_availability(goblin, ActionType.ACTION)
    check_action_availability(goblin, ActionType.BONUS_ACTION)
    check_action_availability(goblin, ActionType.REACTION)
    
    print("\n5. Simulating 'Haste' effect while Incapacitated")
    goblin.action_economy.actions.add_static_modifier("Haste", 1)
    print_creature_details(goblin)
    check_action_availability(goblin, ActionType.ACTION)
    
    print("\n6. Advancing time to expire the Incapacitated condition")
    for _ in range(2):
        goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n7. Checking action availability after Incapacitated condition expires")
    check_action_availability(goblin, ActionType.ACTION)
    check_action_availability(goblin, ActionType.BONUS_ACTION)
    check_action_availability(goblin, ActionType.REACTION)

if __name__ == "__main__":
    test_incapacitated_condition()