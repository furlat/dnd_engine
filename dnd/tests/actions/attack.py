from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Blinded, Paralyzed
from dnd.logger import Logger
from dnd.dnd_enums import AttackType, AttackHand, RangeType, ActionType, DurationType
from dnd.core import Duration
from dnd.actions import Attack, ActionCost
from dnd.tests.printer import print_log_details

def test_attack_class():
    print("=== Testing Attack Class ===\n")

    # Create creatures
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    # Set up initial positions
    goblin.sensory.update_origin((0, 0))
    skeleton.sensory.update_origin((1, 0))  # 5 feet away
    goblin.sensory.update_distance_matrix({(1, 0): 5})
    skeleton.sensory.update_distance_matrix({(0, 0): 5})
    goblin.sensory.update_fov(set([(1, 0)]))
    skeleton.sensory.update_fov(set([(0, 0)]))

    # Create an attack action
    melee_attack = Attack(
        name="Melee Attack",
        description="A basic melee attack",
        cost=[ActionCost(type=ActionType.ACTION, cost=1)],
        attack_type=AttackType.MELEE_WEAPON,
        attack_hand=AttackHand.MELEE_RIGHT,
        range_type=RangeType.REACH,
        range_normal=5
    )

    def print_attack_result(scenario, attack_logs):
        print(f"\n{scenario}")
        for log in attack_logs:
            print_log_details(log)
        print(f"Goblin Actions: {goblin.action_economy.actions.apply(goblin).total_bonus}")
        print(f"Skeleton HP: {skeleton.health.current_hit_points}/{skeleton.health.max_hit_points}")

    def reset_action_economy():
        goblin.action_economy.reset()
        skeleton.action_economy.reset()

    # Scenario 1: Normal Attack
    reset_action_economy()
    attack_logs = melee_attack.apply(goblin, skeleton)
    print_attack_result("Scenario 1: Normal Attack", attack_logs)

    # Scenario 2: Attack with depleted action economy
    reset_action_economy()
    # goblin.action_economy.actions.self_static.add_bonus("test", -1)  # Deplete actions
    attack_logs = melee_attack.apply(goblin, skeleton)
    print_attack_result("Scenario 2: Attack with depleted action economy", attack_logs)
    goblin.action_economy.actions.self_static.remove_effect("test")  # Reset actions

    # Scenario 3: Attack while Blinded
    reset_action_economy()
    blinded_condition = Blinded(duration=Duration(time=1, type=DurationType.ROUNDS), targeted_entity_id=goblin.id)
    goblin.add_condition(blinded_condition)
    attack_logs = melee_attack.apply(goblin, skeleton)
    print_attack_result("Scenario 3: Attack while Blinded", attack_logs)
    goblin.remove_condition("Blinded")

    # Scenario 4: Attack a Paralyzed target
    reset_action_economy()
    paralyzed_condition = Paralyzed(duration=Duration(time=1, type=DurationType.ROUNDS), targeted_entity_id=skeleton.id)
    skeleton.add_condition(paralyzed_condition)
    attack_logs = melee_attack.apply(goblin, skeleton)
    print_attack_result("Scenario 4: Attack a Paralyzed target", attack_logs)
    skeleton.remove_condition("Paralyzed")

    # Scenario 5: Attack out of range
    reset_action_economy()
    skeleton.sensory.update_origin((2, 0))  # 10 feet away
    goblin.sensory.update_distance_matrix({(2, 0): 10})
    attack_logs = melee_attack.apply(goblin, skeleton)
    print_attack_result("Scenario 5: Attack out of range", attack_logs)

    # Scenario 6: Attack with no line of sight
    reset_action_economy()
    goblin.sensory.update_fov(set())
    attack_logs = melee_attack.apply(goblin, skeleton)
    print_attack_result("Scenario 6: Attack with no line of sight", attack_logs)

if __name__ == "__main__":
    test_attack_class()