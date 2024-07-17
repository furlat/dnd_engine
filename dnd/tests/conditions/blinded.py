from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Blinded, Duration
from dnd.logger import Logger, EffectTarget
from dnd.dnd_enums import Skills, Ability, DurationType
from dnd.actions import Attack

def print_creature_details(creature):
    print(f"{creature.name} Details:")
    print(f"HP: {creature.hp}/{creature.health.max_hit_points}")
    print(f"AC: {creature.armor_class_value}")
    print(f"Active Conditions: {', '.join(creature.active_conditions.keys())}")
    print("Actions:")
    for attack in creature.actions:
        print(attack.action_docstring())
    print()

def print_log_details(log):
    print(f"Log Type: {log.log_type}")
    print(f"Timestamp: {log.timestamp}")
    if hasattr(log, 'action_name'):
        print(f"Action: {log.action_name}")
    if hasattr(log, 'condition_name'):
        print(f"Condition: {log.condition_name}")
    print(f"Source ID: {log.source_id}")
    print(f"Target ID: {log.target_id}")
    if hasattr(log, 'success'):
        print(f"Success: {log.success}")
    if hasattr(log, 'applied'):
        print(f"Applied: {log.applied}")
    if hasattr(log, 'effects'):
        print("Effects:")
        for effect in log.effects:
            print(f"  Target: {effect.target.target_type}, Type: {effect.effect_type}")
    if hasattr(log, 'details'):
        print("Details:")
        for key, value in log.details.model_dump().items():
            print(f"  {key}: {value}")
    print()

def test_blinded_condition():
    print("=== Testing Blinded Condition and Logging ===\n")

    goblin = create_goblin()
    skeleton = create_skeleton()

    print("Initial State:")
    print_creature_details(goblin)
    print_creature_details(skeleton)

    # Apply Blinded condition to Goblin
    blinded_condition = Blinded(duration=Duration(time=2, type=DurationType.ROUNDS))
    print("\nApplying Blinded to Goblin:")
    condition_log = goblin.apply_condition(blinded_condition)
    print_creature_details(goblin)
    print("Condition Application Log:")
    print_log_details(condition_log)

    # Goblin attempts a Perception check
    print("Goblin attempts a Perception check (with disadvantage due to Blinded):")
    context = {"requires_sight": True}
    perception_result = goblin.skills.perform_skill_check(Skills.PERCEPTION, goblin,dc=15,context=context, return_log=True)
    print(type(perception_result))
    print_log_details(perception_result)

    # Goblin attacks Skeleton
    print("Goblin (Blinded) attacks Skeleton:")
    attack_action = next(action for action in goblin.actions if isinstance(action, Attack))
    attack_result = attack_action.apply([skeleton])
    for log in attack_result:
        print_log_details(log)

    # Skeleton attacks Goblin
    print("Skeleton attacks Goblin (Blinded):")
    skeleton_attack = next(action for action in skeleton.actions if isinstance(action, Attack))
    skeleton_attack_result = skeleton_attack.apply([goblin])
    for log in skeleton_attack_result:
        print_log_details(log)

    # Remove Blinded condition from Goblin
    print("\nRemoving Blinded condition from Goblin:")
    remove_condition_log = goblin.remove_condition("Blinded")
    print_creature_details(goblin)
    print("Condition Removal Log:")
    print_log_details(remove_condition_log)

    # Goblin attacks Skeleton again (no longer Blinded)
    print("Goblin attacks Skeleton (no longer Blinded):")
    attack_result = attack_action.apply([skeleton])
    for log in attack_result:
        print_log_details(log)

    # Print all logs
    print("\n=== All Logs ===")
    all_logs = Logger.get_logs()
    for log in all_logs:
        print_log_details(log)

if __name__ == "__main__":
    test_blinded_condition()