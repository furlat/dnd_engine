# frightened.py

from dnd.statsblock import StatsBlock
from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Frightened, Duration, DurationType
from dnd.actions import Attack
from dnd.core import Skills, Ability

def print_creature_details(creature: StatsBlock):
    print(f"{creature.name} Details:")
    print(f"HP: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Active Conditions: {', '.join([cond for cond in creature.active_conditions.keys()])}")
    print(f"Line of Sight: {creature.line_of_sight}")

def test_frightened_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Frightened Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    print_creature_details(skeleton)
    
    print("\n2. Applying Frightened condition to Goblin")
    frightened_condition = Frightened(name="Frightened", duration=Duration(time=3, type=DurationType.ROUNDS), source_entity_id=skeleton.id)
    goblin.apply_condition(frightened_condition)
    goblin.refresh_line_of_sight({skeleton.id})
    print_creature_details(goblin)
    
    print("\n3. Goblin attacks while Frightened (Skeleton in sight)")
    perform_attack(goblin, skeleton)
    
    print("\n4. Goblin performs Stealth check while Frightened (Skeleton in sight)")
    perform_ability_check(goblin, Ability.DEX, Skills.STEALTH, 15)
    
    print("\n5. Removing Skeleton from Goblin's line of sight")
    goblin.refresh_line_of_sight(set())
    print_creature_details(goblin)
    
    print("\n6. Goblin attacks while Frightened (Skeleton not in sight)")
    perform_attack(goblin, skeleton)
    
    print("\n7. Goblin performs Perception check while Frightened (Skeleton not in sight)")
    perform_ability_check(goblin, Ability.WIS, Skills.PERCEPTION, 15)
    
    print("\n8. Advancing time to expire the Frightened condition")
    for _ in range(3):
        goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n9. Goblin attacks after Frightened condition expires")
    perform_attack(goblin, skeleton)
    
    print("\n10. Goblin performs Intimidation check after Frightened condition expires")
    perform_ability_check(goblin, Ability.CHA, Skills.INTIMIDATION, 15)

def perform_attack(attacker, defender):
    attack_action = next(action for action in attacker.actions if isinstance(action, Attack))
    hit, details = attack_action.roll_to_hit(defender, verbose=True)
    print(f"  Advantage status: {details['advantage_status']}")
    print(f"  Attack roll: {details['roll']}, Total: {details['roll'] + details['total_hit_bonus']}, AC: {details['armor_class']}")
    print(f"  Result: {'Hit' if hit else 'Miss'}")

def perform_ability_check(creature, ability, skill, dc):
    roll, total, _ = creature.perform_skill_check(skill, dc, return_roll=True)
    ability_score = creature.ability_scores.get_ability(ability)
    advantage_status = ability_score.get_advantage_status(creature)
    print(f"  Ability: {ability.value}, Skill: {skill.value}")
    print(f"  Advantage status: {advantage_status}")
    print(f"  Ability check roll: {roll}, Total: {total}, DC: {dc}")
    print(f"  Result: {'Success' if total >= dc else 'Failure'}")

if __name__ == "__main__":
    test_frightened_condition()