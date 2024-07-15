from dnd.statsblock import *
from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Blinded, Duration, DurationType

def print_creature_details(creature):
    print(f"{creature.name} Details:")
    print(f"Speed: {creature.speed.walk.get_value(creature)} ft")
    print(f"Armor Class: {creature.armor_class.get_value(creature)}")
    print(f"Hit Points: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Proficiency Bonus: +{creature.proficiency_bonus}")
    print(f"Active Conditions: {', '.join([cond for cond in creature.active_conditions.keys()])}")
    print(f"Line of Sight: {creature.line_of_sight}")
    print(f"Distances: {creature.distances}")

def test_blinded_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Blinded Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    print_creature_details(skeleton)

    print("\n2. Setting up line of sight and distances")
    goblin.refresh_line_of_sight({skeleton.id})
    skeleton.refresh_line_of_sight({goblin.id})
    goblin.add_distance(skeleton.id, 5)  # Skeleton is 5 feet away from Goblin
    skeleton.add_distance(goblin.id, 5)  # Goblin is 5 feet away from Skeleton
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    print("\n3. Applying Blinded condition to Goblin")
    blinded_condition = Blinded(name="Blinded", duration=Duration(time=3, type=DurationType.ROUNDS))
    goblin.apply_condition(blinded_condition)
    print_creature_details(goblin)
    
    print("\n4. Goblin attempts a normal Perception check")
    roll, total, dc = goblin.perform_skill_check(Skills.PERCEPTION, 15, context={'requires_sight': False}, return_roll=True)
    success = total >= dc
    print(f"  Result: {'Success' if success else 'Failure'}, Roll: {roll}, Total: {total}, DC: {dc}")
    
    print("\n5. Goblin attempts a sight-based Perception check")
    roll, total, dc = goblin.perform_skill_check(Skills.PERCEPTION, 15, context={'requires_sight': True}, return_roll=True)
    success = total >= dc
    print(f"  Result: {'Success' if success else 'Failure'}, Roll: {roll}, Total: {total}, DC: {dc}")
    
    print("\n6. Goblin attacks Skeleton")
    perform_attack(goblin, skeleton)
    
    print("\n7. Skeleton attacks Blinded Goblin")
    perform_attack(skeleton, goblin)
    
    print("\n8. Moving Skeleton away from Goblin")
    goblin.add_distance(skeleton.id, 30)  # Skeleton is now 30 feet away from Goblin
    skeleton.add_distance(goblin.id, 30)  # Goblin is now 30 feet away from Skeleton
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    print("\n9. Goblin attacks Skeleton (out of range)")
    perform_attack(goblin, skeleton)
    
    print("\n10. Advancing time to expire the Blinded condition")
    for _ in range(3):
        goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n11. Goblin attacks Skeleton after Blinded condition expires")
    perform_attack(goblin, skeleton)

def perform_attack(attacker, defender):
    attack_action = next(action for action in attacker.actions if isinstance(action, Attack))
    success, message = attack_action.apply(defender)
    print(f"  {message}")
    print(f"  Result: {'Hit' if success else 'Miss'}")

if __name__ == "__main__":
    test_blinded_condition()