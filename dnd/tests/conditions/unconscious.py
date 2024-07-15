from infinipy.dnd.statsblock import *
from infinipy.dnd.monsters.goblin import create_goblin
from infinipy.dnd.monsters.skeleton import create_skeleton
from infinipy.dnd.conditions import Unconscious, Duration, DurationType
from infinipy.dnd.core import Ability

def print_creature_details(creature):
    print(f"{creature.name} Details:")
    print(f"Speed: {creature.speed.walk.get_value(creature)} ft")
    print(f"Armor Class: {creature.armor_class.get_value(creature)}")
    print(f"Hit Points: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Active Conditions: {', '.join([cond for cond in creature.active_conditions.keys()])}")
    print(f"Available Actions: {creature.action_economy.actions.get_value(creature)}")
    print(f"Available Bonus Actions: {creature.action_economy.bonus_actions.get_value(creature)}")
    print(f"Available Reactions: {creature.action_economy.reactions.get_value(creature)}")
    print(f"Distances: {creature.distances}")

def perform_attack(attacker, defender):
    attack_action = next(action for action in attacker.actions if isinstance(action, Attack))
    hit, details = attack_action.roll_to_hit(defender, verbose=True)
    print(f"  Advantage status: {details['advantage_status']}")
    print(f"  Attack roll: {details['roll']}, Total: {details['roll'] + details['total_hit_bonus']}, AC: {details['armor_class']}")
    print(f"  Result: {'Hit' if hit else 'Miss'}")
    print(f"  Critical: {details['is_auto_critical'] or details['is_critical_hit']}")

def test_unconscious_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Unconscious Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    print("\n2. Setting initial distances")
    goblin.add_distance(skeleton.id, 5)  # Skeleton is 5 feet away from Goblin
    skeleton.add_distance(goblin.id, 5)  # Goblin is 5 feet away from Skeleton
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    print("\n3. Applying Unconscious condition to Goblin")
    unconscious_condition = Unconscious(name="Unconscious", duration=Duration(time=3, type=DurationType.ROUNDS))
    goblin.apply_condition(unconscious_condition)
    print_creature_details(goblin)
    
    print("\n4. Goblin attempts to take an action")
    print(f"Available actions: {goblin.action_economy.actions.get_value(goblin)}")
    
    print("\n5. Skeleton attacks Unconscious Goblin (within 5 feet)")
    perform_attack(skeleton, goblin)
    
    print("\n6. Goblin attempts a Strength saving throw")
    success = goblin.perform_saving_throw(Ability.STR, 10)
    print(f"Strength saving throw result: {'Success' if success else 'Failure'}")
    
    print("\n7. Goblin attempts a Dexterity saving throw")
    success = goblin.perform_saving_throw(Ability.DEX, 10)
    print(f"Dexterity saving throw result: {'Success' if success else 'Failure'}")
    
    print("\n8. Moving Skeleton away from Goblin")
    goblin.add_distance(skeleton.id, 15)  # Skeleton is now 15 feet away from Goblin
    skeleton.add_distance(goblin.id, 15)  # Goblin is now 15 feet away from Skeleton
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    print("\n9. Skeleton attacks Unconscious Goblin (beyond 5 feet)")
    perform_attack(skeleton, goblin)
    
    print("\n10. Advancing time to expire the Unconscious condition")
    for _ in range(3):
        goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n11. Goblin attacks Skeleton after Unconscious condition expires")
    perform_attack(goblin, skeleton)

if __name__ == "__main__":
    test_unconscious_condition()