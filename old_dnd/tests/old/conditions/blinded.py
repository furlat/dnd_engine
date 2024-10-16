from old_dnd.monsters.goblin import create_goblin
from old_dnd.monsters.skeleton import create_skeleton
from old_dnd.conditions import Blinded
from old_dnd.logger import Logger
from old_dnd.dnd_enums import Skills, Ability, DurationType, AttackHand, AdvantageStatus
from old_dnd.core import Duration

from old_dnd.dnd_enums import AdvantageStatus, AutoHitStatus, CriticalStatus, HitReason, CriticalReason
from old_dnd.tests.printer import print_log_details

def test_blinded_condition():
    print("=== Testing Blinded Condition and Logging ===\n")

    # Create creatures
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    print("Turn 1: Applying Blinded to Goblin at the start of its turn")
    blinded_condition = Blinded(duration=Duration(time=2, type=DurationType.ROUNDS), targeted_entity_id=goblin.id)
    condition_log = goblin.condition_manager.add_condition(blinded_condition)
    print_log_details(condition_log)

    print("Goblin's Turn 1 actions:")
    
    print("Goblin attempts a sight-based Perception check (should auto-fail due to Blinded):")
    context = {"requires_sight": True}
    perception_result = goblin.perform_skill_check(Skills.PERCEPTION, 15, context=context)
    print_log_details(perception_result)

    print("Goblin attempts a hearing-based Perception check (should not auto-fail):")
    context = {"requires_sight": False}
    perception_result = goblin.perform_skill_check(Skills.PERCEPTION, 15, context=context)
    print_log_details(perception_result)

    print("Goblin (Blinded) attacks Skeleton:")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("\nSkeleton's Turn 1:")
    print("Skeleton attacks Goblin (Blinded):")
    skeleton_attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(skeleton_attack_result)

    print("\nTurn 2: Start of Goblin's turn, advancing duration")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Goblin's Turn 2 actions (still Blinded):")
    print("Goblin attacks Skeleton:")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

    print("\nSkeleton's Turn 2:")
    print("Skeleton attacks Goblin (Blinded):")
    skeleton_attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(skeleton_attack_result)

    print("\nTurn 3: Start of Goblin's turn, advancing duration again (condition should be removed)")
    advance_result = goblin.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Goblin's Turn 3 actions (no longer Blinded):")
    print("Goblin attacks Skeleton:")
    attack_result = goblin.perform_melee_attack(skeleton.id)
    print_log_details(attack_result)

if __name__ == "__main__":
    test_blinded_condition()

if __name__ == "__main__":
    test_blinded_condition()