from infinipy.dnd.statsblock import *
from infinipy.dnd.monsters.goblin import create_goblin
from infinipy.dnd.monsters.skeleton import create_skeleton
from infinipy.dnd.conditions import Stunned, Duration, DurationType

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

def perform_attack(attacker, defender):
    attack_action = next(action for action in attacker.actions if isinstance(action, Attack))
    hit, details = attack_action.roll_to_hit(defender, verbose=True)
    print(f"  Advantage status: {details['advantage_status']}")
    print(f"  Attack roll: {details['roll']}, Total: {details['roll'] + details['total_hit_bonus']}, AC: {details['armor_class']}")
    print(f"  Result: {'Hit' if hit else 'Miss'}")

def test_stunned_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Stunned Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    
    print("\n2. Applying Stunned condition to Goblin")
    stunned_condition = Stunned(name="Stunned", duration=Duration(time=3, type=DurationType.ROUNDS))
    goblin.apply_condition(stunned_condition)
    print_creature_details(goblin)
    
    print("\n3. Goblin attempts to move")
    print(f"Goblin movement speed: {goblin.speed.walk.get_value(goblin)} ft")
    
    print("\n4. Goblin attempts to take an action")
    print(f"Available actions: {goblin.action_economy.actions.get_value(goblin)}")
    
    print("\n5. Skeleton attacks Stunned Goblin")
    perform_attack(skeleton, goblin)
    
    print("\n6. Goblin attempts a Strength saving throw")
    success = goblin.perform_saving_throw(Ability.STR, 10)
    print(f"Strength saving throw result: {'Success' if success else 'Failure'}")
    
    print("\n7. Goblin attempts a Dexterity saving throw")
    success = goblin.perform_saving_throw(Ability.DEX, 10)
    print(f"Dexterity saving throw result: {'Success' if success else 'Failure'}")
    
    print("\n8. Goblin attempts a Wisdom saving throw")
    success = goblin.perform_saving_throw(Ability.WIS, 10)
    print(f"Wisdom saving throw result: {'Success' if success else 'Failure'}")
    
    print("\n9. Advancing time to expire the Stunned condition")
    for _ in range(3):
        goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n10. Skeleton attacks Goblin after Stunned condition expires")
    perform_attack(skeleton, goblin)

if __name__ == "__main__":
    test_stunned_condition()