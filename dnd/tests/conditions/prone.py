from infinipy.dnd.statsblock import *
from infinipy.dnd.monsters.goblin import create_goblin
from infinipy.dnd.monsters.skeleton import create_skeleton
from infinipy.dnd.conditions import Prone, Duration, DurationType
from infinipy.dnd.core import Ability

def print_creature_details(creature):
    print(f"{creature.name} Details:")
    print(f"Speed: {creature.speed.walk.get_value(creature)} ft")
    print(f"Armor Class: {creature.armor_class.get_value(creature)}")
    print(f"Hit Points: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Active Conditions: {', '.join([cond for cond in creature.active_conditions.keys()])}")
    print(f"Distances: {creature.distances}")

def perform_attack(attacker, defender):
    attack_action = next(action for action in attacker.actions if isinstance(action, Attack))
    hit, details = attack_action.roll_to_hit(defender, verbose=True)
    print(f"  Advantage status: {details['advantage_status']}")
    print(f"  Attack roll: {details['roll']}, Total: {details['roll'] + details['total_hit_bonus']}, AC: {details['armor_class']}")
    print(f"  Result: {'Hit' if hit else 'Miss'}")

def test_prone_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Prone Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    print("\n2. Setting initial distances")
    goblin.add_distance(skeleton.id, 5)  # Skeleton is 5 feet away from Goblin
    skeleton.add_distance(goblin.id, 5)  # Goblin is 5 feet away from Skeleton
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    print("\n3. Applying Prone condition to Goblin")
    prone_condition = Prone(name="Prone", duration=Duration(time=3, type=DurationType.ROUNDS))
    goblin.apply_condition(prone_condition)
    print_creature_details(goblin)
    
    print("\n4. Goblin attacks Skeleton while prone")
    perform_attack(goblin, skeleton)
    
    print("\n5. Skeleton attacks prone Goblin (within 5 feet)")
    perform_attack(skeleton, goblin)
    
    print("\n6. Moving Skeleton away from Goblin")
    goblin.add_distance(skeleton.id, 15)  # Skeleton is now 15 feet away from Goblin
    skeleton.add_distance(goblin.id, 15)  # Goblin is now 15 feet away from Skeleton
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    print("\n7. Skeleton attacks prone Goblin (beyond 10 feet)")
    perform_attack(skeleton, goblin)
    
    print("\n8. Goblin attacks Skeleton while prone (ranged attack)")
    perform_attack(goblin, skeleton)
    
    print("\n9. Advancing time to expire the Prone condition")
    for _ in range(3):
        goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n10. Goblin attacks Skeleton after Prone condition expires")
    perform_attack(goblin, skeleton)

if __name__ == "__main__":
    test_prone_condition()