from dnd.statsblock import *
from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Deafened, Duration, DurationType

def print_creature_details(creature):
    print(f"{creature.name} Details:")
    print(f"Speed: {creature.speed.walk.get_value(creature)} ft")
    print(f"Armor Class: {creature.armor_class.get_value(creature)}")
    print(f"Hit Points: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Proficiency Bonus: +{creature.proficiency_bonus}")
    print(f"Active Conditions: {', '.join([cond[0] for cond in creature.active_conditions.keys()])}")

def test_deafened_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Deafened Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    
    print("\n2. Applying Deafened condition to Goblin")
    deafened_condition = Deafened(name="Deafened", duration=Duration(time=3, type=DurationType.ROUNDS))
    goblin.apply_condition(deafened_condition)
    print_creature_details(goblin)
    
    print("\n3. Goblin attempts a normal Perception check")
    result = goblin.perform_skill_check(Skills.PERCEPTION, 15, context={'requires_hearing': False}, return_roll=True)
    print(f"  Roll: {result[0]}, Total: {result[1]}, DC: {result[2]}, Success: {result[1] >= result[2]}")
    
    print("\n4. Goblin attempts a hearing-based Perception check")
    result = goblin.perform_skill_check(Skills.PERCEPTION, 15, context={'requires_hearing': True}, return_roll=True)
    print(f"  Roll: {result[0]}, Total: {result[1]}, DC: {result[2]}, Success: {result[1] >= result[2]}")
    
    print("\n5. Goblin attempts a Performance check (which often involves hearing)")
    result = goblin.perform_skill_check(Skills.PERFORMANCE, 15, context={'requires_hearing': True}, return_roll=True)
    print(f"  Roll: {result[0]}, Total: {result[1]}, DC: {result[2]}, Success: {result[1] >= result[2]}")
    
    print("\n6. Goblin attempts an Athletics check (not hearing-dependent)")
    result = goblin.perform_skill_check(Skills.ATHLETICS, 15, context={'requires_hearing': False}, return_roll=True)
    print(f"  Roll: {result[0]}, Total: {result[1]}, DC: {result[2]}, Success: {result[1] >= result[2]}")
    
    print("\n7. Advancing time to expire the Deafened condition")
    for _ in range(3):
        goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n8. Goblin attempts a hearing-based Perception check after Deafened condition expires")
    result = goblin.perform_skill_check(Skills.PERCEPTION, 15, context={'requires_hearing': True}, return_roll=True)
    print(f"  Roll: {result[0]}, Total: {result[1]}, DC: {result[2]}, Success: {result[1] >= result[2]}")

if __name__ == "__main__":
    test_deafened_condition()