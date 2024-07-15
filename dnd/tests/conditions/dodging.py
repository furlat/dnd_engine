from dnd.statsblock import StatsBlock
from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Dodging, Duration, DurationType
from dnd.actions import Attack
from dnd.core import Ability, Skills

def print_creature_details(creature: StatsBlock):
    print(f"{creature.name} Details:")
    print(f"HP: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Active Conditions: {', '.join([cond for cond in creature.active_conditions.keys()])}")

def test_dodging_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Dodging Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    def perform_attack_and_check(attacker, defender, description):
        print(f"\n--- {attacker.name} attacks {defender.name} ({description}) ---")
        attack_action = next(action for action in attacker.actions if isinstance(action, Attack))
        hit, details = attack_action.roll_to_hit(defender, verbose=True)
        advantage_status = defender.armor_class.gives_attacker_disadvantage(defender, attacker)
        print(f"  Defender gives attacker disadvantage: {advantage_status}")
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

    print("\n2. Skeleton attacks Goblin and Goblin performs Dexterity saving throw before Dodging")
    perform_attack_and_check(skeleton, goblin, "before Dodging")
    perform_saving_throw(goblin, Ability.DEX, 15, "before Dodging")
    
    print("\n3. Applying Dodging condition to Goblin")
    dodging_condition = Dodging(name="Dodging", duration=Duration(time=1, type=DurationType.ROUNDS))
    goblin.apply_condition(dodging_condition)
    print_creature_details(goblin)
    
    print("\n4. Skeleton attacks Goblin and Goblin performs Dexterity saving throw while Dodging")
    perform_attack_and_check(skeleton, goblin, "while Dodging")
    perform_saving_throw(goblin, Ability.DEX, 15, "while Dodging")
    
    print("\n5. Advancing time to expire the Dodging condition")
    goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n6. Skeleton attacks Goblin and Goblin performs Dexterity saving throw after Dodging expires")
    perform_attack_and_check(skeleton, goblin, "after Dodging expires")
    perform_saving_throw(goblin, Ability.DEX, 15, "after Dodging expires")

if __name__ == "__main__":
    test_dodging_condition()