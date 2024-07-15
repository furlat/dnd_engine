from infinipy.dnd.statsblock import *
from infinipy.dnd.monsters.goblin import create_goblin
from infinipy.dnd.monsters.skeleton import create_skeleton
from infinipy.dnd.conditions import Invisible, Duration, DurationType
from infinipy.dnd.core import Sense, SensesType

def print_creature_details(creature):
    print(f"{creature.name} Details:")
    print(f"Speed: {creature.speed.walk.get_value(creature)} ft")
    print(f"Armor Class: {creature.armor_class.get_value(creature)}")
    print(f"Hit Points: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Proficiency Bonus: +{creature.proficiency_bonus}")
    print(f"Active Conditions: {', '.join([cond[0] for cond in creature.active_conditions.keys()])}")
    print(f"Senses: {', '.join([f'{sense.type.value} {sense.range}ft' for sense in creature.senses])}")
    print(f"Line of Sight: {creature.line_of_sight}")

def perform_attack(attacker, defender):
    attack_action = next(action for action in attacker.actions if isinstance(action, Attack))
    hit, details = attack_action.roll_to_hit(defender, verbose=True)
    print(f"  Advantage status: {details['advantage_status']}")
    print(f"  Attack roll: {details['roll']}, Total: {details['roll'] + details['total_hit_bonus']}, AC: {details['armor_class']}")
    print(f"  Result: {'Hit' if hit else 'Miss'}")

def test_invisible_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Invisible Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    print_creature_details(skeleton)

    print("\n1a. Adding Goblin to Skeleton's line of sight")
    skeleton.line_of_sight.add(goblin.id)
    print_creature_details(skeleton)
    
    print("\n2. Applying Invisible condition to Goblin")
    invisible_condition = Invisible(name="Invisible", duration=Duration(time=3, type=DurationType.ROUNDS))
    goblin.apply_condition(invisible_condition)
    print_creature_details(goblin)
    
    print("\n3. Goblin attacks Skeleton while invisible")
    perform_attack(goblin, skeleton)
    
    print("\n4. Skeleton attacks invisible Goblin")
    perform_attack(skeleton, goblin)
    
    print("\n5. Adding Truesight to Skeleton")
    skeleton.senses.append(Sense(type=SensesType.TRUESIGHT, range=30))
    print_creature_details(skeleton)
    
    print("\n6. Skeleton attacks invisible Goblin with Truesight")
    perform_attack(skeleton, goblin)
    
    print("\n7. Goblin attacks Skeleton with Truesight")
    perform_attack(goblin, skeleton)
    
    print("\n8. Removing Truesight and adding Tremorsense to Skeleton")
    skeleton.senses = [sense for sense in skeleton.senses if sense.type != SensesType.TRUESIGHT]
    skeleton.senses.append(Sense(type=SensesType.TREMORSENSE, range=30))
    print_creature_details(skeleton)
    
    print("\n9. Skeleton attacks invisible Goblin with Tremorsense")
    perform_attack(skeleton, goblin)
    
    print("\n10. Goblin attacks Skeleton with Tremorsense")
    perform_attack(goblin, skeleton)
    
    print("\n11. Removing Goblin from Skeleton's line of sight")
    skeleton.line_of_sight.remove(goblin.id)
    print_creature_details(skeleton)
    
    print("\n12. Skeleton attacks invisible Goblin with Tremorsense (out of line of sight)")
    perform_attack(skeleton, goblin)
    
    print("\n13. Goblin attacks Skeleton with Tremorsense (out of line of sight)")
    perform_attack(goblin, skeleton)
    
    print("\n14. Advancing time to expire the Invisible condition")
    for _ in range(3):
        goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n15. Goblin attacks Skeleton after Invisible condition expires")
    perform_attack(goblin, skeleton)

if __name__ == "__main__":
    test_invisible_condition()