from dnd.statsblock import *
from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Paralyzed, Duration, DurationType
from dnd.core import Ability

def print_creature_details(creature):
    print(f"{creature.name} Details:")
    print(f"Speed: {creature.speed.walk.get_value(creature)} ft")
    print(f"Armor Class: {creature.armor_class.get_value(creature)}")
    print(f"Hit Points: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Proficiency Bonus: +{creature.proficiency_bonus}")
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
    if hit:
        damage = attack_action.roll_damage()
        print(f"  Damage: {damage}")

def test_paralyzed_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Paralyzed Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    print("\n2. Setting distances")
    goblin.add_distance(skeleton.id, 5)  # Skeleton is 5 feet away from Goblin
    skeleton.add_distance(goblin.id, 5)  # Goblin is 5 feet away from Skeleton
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    print("\n3. Applying Paralyzed condition to Goblin")
    paralyzed_condition = Paralyzed(name="Paralyzed", duration=Duration(time=3, type=DurationType.ROUNDS))
    goblin.apply_condition(paralyzed_condition)
    print_creature_details(goblin)
    
    print("\n4. Skeleton attacks Paralyzed Goblin (within 5 feet)")
    perform_attack(skeleton, goblin)
    
    print("\n5. Moving Skeleton away from Goblin")
    goblin.add_distance(skeleton.id, 10)  # Skeleton is now 10 feet away from Goblin
    skeleton.add_distance(goblin.id, 10)  # Goblin is now 10 feet away from Skeleton
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    print("\n6. Skeleton attacks Paralyzed Goblin (beyond 5 feet)")
    perform_attack(skeleton, goblin)
    
    print("\n7. Advancing time to expire the Paralyzed condition")
    for _ in range(3):
        goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n8. Skeleton attacks Goblin after Paralyzed condition expires")
    perform_attack(skeleton, goblin)

if __name__ == "__main__":
    test_paralyzed_condition()