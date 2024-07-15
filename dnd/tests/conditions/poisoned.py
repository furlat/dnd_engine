from dnd.statsblock import StatsBlock
from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Poisoned, Duration, DurationType
from dnd.actions import Attack
from dnd.core import Skills

def print_creature_details(creature: StatsBlock):
    print(f"{creature.name} Details:")
    print(f"HP: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Active Conditions: {', '.join([cond for cond in creature.active_conditions.keys()])}")

def test_poisoned_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Poisoned Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    
    def perform_attack_and_check(attacker, defender, description):
        print(f"\n--- {attacker.name} attacks {defender.name} ({description}) ---")
        attack_action = next(action for action in attacker.actions if isinstance(action, Attack))
        hit, details = attack_action.roll_to_hit(defender, verbose=True)
        print(f"  Advantage status: {details['advantage_status']}")
        print(f"  Attack roll: {details['roll']}, Total: {details['roll'] + details['total_hit_bonus']}, AC: {details['armor_class']}")
        print(f"  Result: {'Hit' if hit else 'Miss'}")

    def perform_skill_check(creature, skill, dc, description):
        print(f"\n--- {creature.name} performs {skill.value} check ({description}) ---")
        roll, total, _ = creature.perform_skill_check(skill, dc, return_roll=True)
        skill_obj = creature.skills.get_skill(skill)
        advantage_status = skill_obj.bonus.get_advantage_status(creature)
        print(f"  Advantage status: {advantage_status}")
        print(f"  Skill check roll: {roll}, Total: {total}, DC: {dc}")
        print(f"  Result: {'Success' if total >= dc else 'Failure'}")

    print("\n2. Goblin attacks and performs skill check before being Poisoned")
    perform_attack_and_check(goblin, skeleton, "before Poisoned")
    perform_skill_check(goblin, Skills.STEALTH, 15, "before Poisoned")
    
    print("\n3. Applying Poisoned condition to Goblin")
    poisoned_condition = Poisoned(name="Poisoned", duration=Duration(time=3, type=DurationType.ROUNDS))
    goblin.apply_condition(poisoned_condition)
    print_creature_details(goblin)
    
    print("\n4. Goblin attacks and performs skill check while Poisoned")
    perform_attack_and_check(goblin, skeleton, "while Poisoned")
    perform_skill_check(goblin, Skills.PERCEPTION, 15, "while Poisoned")
    
    print("\n5. Advancing time to expire the Poisoned condition")
    for _ in range(3):
        goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n6. Goblin attacks and performs skill check after Poisoned condition expires")
    perform_attack_and_check(goblin, skeleton, "after Poisoned expires")
    perform_skill_check(goblin, Skills.INTIMIDATION, 15, "after Poisoned expires")

if __name__ == "__main__":
    test_poisoned_condition()