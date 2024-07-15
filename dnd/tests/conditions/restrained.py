from dnd.statsblock import StatsBlock
from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Restrained, Duration, DurationType
from dnd.actions import Attack
from dnd.core import Ability, Skills

def print_creature_details(creature: StatsBlock):
    print(f"{creature.name} Details:")
    print(f"HP: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Speed: Walk {creature.speed.get_speed('walk', creature)} ft")
    print(f"Active Conditions: {', '.join([cond for cond in creature.active_conditions.keys()])}")

def test_restrained_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Restrained Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    
    def perform_attack_and_check(attacker, defender, description):
        print(f"\n--- {attacker.name} attacks {defender.name} ({description}) ---")
        attack_action = next(action for action in attacker.actions if isinstance(action, Attack))
        hit, details = attack_action.roll_to_hit(defender, verbose=True)
        print(f"  Advantage status: {details['advantage_status']}")
        print(f"  Attack roll: {details['roll']}, Total: {details['roll'] + details['total_hit_bonus']}, AC: {details['armor_class']}")
        print(f"  Result: {'Hit' if hit else 'Miss'}")

    def perform_saving_throw(creature, ability, dc, description):
        print(f"\n--- {creature.name} performs {ability.value} saving throw ({description}) ---")
        success = creature.perform_saving_throw(ability, dc)
        saving_throw = creature.saving_throws.get_ability(ability)
        advantage_status = saving_throw.bonus.get_advantage_status(creature)
        print(f"  Advantage status: {advantage_status}")
        print(f"  Result: {'Success' if success else 'Failure'}")

    print("\n2. Goblin attacks and performs Dexterity saving throw before being Restrained")
    perform_attack_and_check(goblin, skeleton, "before Restrained")
    perform_saving_throw(goblin, Ability.DEX, 15, "before Restrained")
    
    print("\n3. Applying Restrained condition to Goblin")
    restrained_condition = Restrained(name="Restrained", duration=Duration(time=3, type=DurationType.ROUNDS))
    goblin.apply_condition(restrained_condition)
    print_creature_details(goblin)
    
    print("\n4. Goblin attacks and performs Dexterity saving throw while Restrained")
    perform_attack_and_check(goblin, skeleton, "while Restrained")
    perform_saving_throw(goblin, Ability.DEX, 15, "while Restrained")
    
    print("\n5. Advancing time to expire the Restrained condition")
    for _ in range(3):
        goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n6. Goblin attacks and performs Dexterity saving throw after Restrained condition expires")
    perform_attack_and_check(goblin, skeleton, "after Restrained expires")
    perform_saving_throw(goblin, Ability.DEX, 15, "after Restrained expires")

if __name__ == "__main__":
    test_restrained_condition()