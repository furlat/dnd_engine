from old_dnd.monsters.goblin import create_goblin
from old_dnd.monsters.skeleton import create_skeleton
from old_dnd.conditions import Charmed
from old_dnd.logger import Logger
from old_dnd.dnd_enums import Skills, DurationType, AttackHand
from old_dnd.core import Duration

from old_dnd.tests.printer import print_log_details


def test_charmed_condition():
    print("=== Testing Charmed Condition and Logging ===\n")

    # Create creatures
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    print("Turn 1: Applying Charmed to Skeleton (charmed by Goblin)")
    charmed_condition = Charmed(duration=Duration(time=2, type=DurationType.ROUNDS), targeted_entity_id=skeleton.id, source_entity_id=goblin.id)
    condition_log = skeleton.condition_manager.add_condition(charmed_condition)
    print_log_details(condition_log)

    print("Skeleton's Turn 1 actions:")
    
    print("Skeleton (Charmed) attempts to attack Goblin (should auto-miss):")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("Skeleton (Charmed) attacks another target:")
    dummy_target = create_goblin("Dummy")
    attack_result = skeleton.perform_melee_attack(dummy_target.id)
    print_log_details(attack_result)

    print("\nGoblin's Turn 1:")
    print("Goblin uses Persuasion on Skeleton (Charmed, should have advantage):")
    persuasion_result = goblin.perform_skill_check(Skills.PERSUASION, 15, target_id=skeleton.id)
    print_log_details(persuasion_result)

    print("\nTurn 2: Start of Skeleton's turn, advancing duration")
    advance_result = skeleton.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Skeleton's Turn 2 actions (still Charmed):")
    print("Skeleton attempts to attack Goblin (should still auto-miss):")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("\nGoblin's Turn 2:")
    print("Goblin uses Intimidation on Skeleton (Charmed, should have advantage):")
    intimidation_result = goblin.perform_skill_check(Skills.INTIMIDATION, 15, target_id=skeleton.id)
    print_log_details(intimidation_result)

    print("\nTurn 3: Start of Skeleton's turn, advancing duration again (condition should be removed)")
    advance_result = skeleton.condition_manager.advance_durations()
    for log in advance_result:
        print_log_details(log)

    print("Skeleton's Turn 3 actions (no longer Charmed):")
    print("Skeleton attacks Goblin (should be possible now):")
    attack_result = skeleton.perform_melee_attack(goblin.id)
    print_log_details(attack_result)

    print("\nGoblin's Turn 3:")
    print("Goblin uses Deception on Skeleton (no longer Charmed, should not have advantage):")
    deception_result = goblin.perform_skill_check(Skills.DECEPTION, 15, target_id=skeleton.id)
    print_log_details(deception_result)

if __name__ == "__main__":
    test_charmed_condition()