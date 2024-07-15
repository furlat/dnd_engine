from dnd.statsblock import StatsBlock
from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Charmed, Duration, DurationType
from dnd.actions import Attack
from dnd.core import Skills

def print_creature_details(creature: StatsBlock):
    print(f"{creature.name} Details:")
    print(f"Speed: {creature.speed.walk.get_value(creature)} ft")
    print(f"Armor Class: {creature.armor_class.get_value(creature)}")
    print(f"Hit Points: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Proficiency Bonus: +{creature.proficiency_bonus}")
    print(f"Active Conditions: {', '.join([cond for cond in creature.active_conditions.keys()])}")

def test_charmed_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Charmed Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    def perform_attack(attacker, defender, description):
        print(f"\n--- {attacker.name} attacks {defender.name} ({description}) ---")
        attack_action = next(action for action in attacker.actions if isinstance(action, Attack))
        hit, details = attack_action.roll_to_hit(defender, verbose=True)
        print(f"  Auto-fail: {details['auto_fail']}")
        print(f"  Auto-success: {details['auto_success']}")
        print(f"  Advantage status: {details['advantage_status']}")
        print(f"  Attack roll: {details['roll']}, Total: {details['roll'] + details['total_hit_bonus']}, AC: {details['armor_class']}")
        print(f"  Result: {'Hit' if hit else 'Miss'}")
    def perform_social_check(source, target, skill, dc, description):
        print(f"\n--- {source.name} uses {skill.value} on {target.name} ({description}) ---")
        roll, total, _ = source.perform_skill_check(skill, dc, target, return_roll=True)
        skill_obj = source.skills.get_skill(skill)
        advantage_status = skill_obj.get_advantage_status(source, target)
        print(f"  Advantage status: {advantage_status}")
        print(f"  Skill check roll: {roll}, Total: {total}, DC: {dc}")
        print(f"  Result: {'Success' if total >= dc else 'Failure'}")

    print("\n2. Skeleton attacks Goblin and Goblin uses Persuasion on Skeleton (no conditions)")
    perform_attack(skeleton, goblin, "no conditions")
    perform_social_check(goblin, skeleton, Skills.PERSUASION, 15, "no conditions")
    
    print("\n3. Applying Charmed condition to Skeleton")
    charmed_condition = Charmed(name="Charmed", duration=Duration(time=1, type=DurationType.ROUNDS), source_entity_id=goblin.id)
    skeleton.apply_condition(charmed_condition)
    print_creature_details(skeleton)
    
    print("\n4. Skeleton tries to attack Goblin and Goblin uses Persuasion on Skeleton (Charmed condition)")
    perform_attack(skeleton, goblin, "while Charmed")
    perform_social_check(goblin, skeleton, Skills.PERSUASION, 15, "while Skeleton is Charmed")
    
    print("\n5. Advancing time to expire the Charmed condition")
    skeleton.update_conditions()
    print_creature_details(skeleton)
    
    print("\n6. Skeleton attacks Goblin and Goblin uses Persuasion on Skeleton (after Charmed expires)")
    perform_attack(skeleton, goblin, "after Charmed expires")
    perform_social_check(goblin, skeleton, Skills.PERSUASION, 15, "after Charmed expires")

if __name__ == "__main__":
    test_charmed_condition()