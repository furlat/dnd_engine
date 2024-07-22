from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.dnd_enums import ActionType, RangeType, TargetType
from dnd.actions import (
    ActionEconomyPrerequisite,
    LineOfSightPrerequisite,
    RangePrerequisite,
    TargetTypePrerequisite,
    PathExistsPrerequisite,
    MovementBudgetPrerequisite,
    PrerequisiteDetails
)
from dnd.tests.printer import print_log_details

def test_action_economy_prerequisite():
    print("=== Testing ActionEconomyPrerequisite ===")
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    prereq = ActionEconomyPrerequisite(name="Action Test", action_type=ActionType.ACTION, cost=1)
    passed, details = prereq.check(goblin, skeleton, {})
    print(f"ActionEconomyPrerequisite (cost 1): Passed = {passed}")
    print_log_details(details)

    # Test with insufficient actions
    goblin.action_economy.actions.self_static.add_bonus("test", -1)
    passed, details = prereq.check(goblin, skeleton, {})
    print(f"ActionEconomyPrerequisite (insufficient actions): Passed = {passed}")
    print_log_details(details)

def test_line_of_sight_prerequisite():
    print("\n=== Testing LineOfSightPrerequisite ===")
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    # Set up positions and visibility
    goblin.sensory.update_origin((0, 0))
    skeleton.sensory.update_origin((1, 1))
    goblin.sensory.update_fov({(1, 1)})

    prereq = LineOfSightPrerequisite(name="LoS Test")
    passed, details = prereq.check(goblin, skeleton, {})
    print(f"LineOfSightPrerequisite (visible): Passed = {passed}")
    print_log_details(details)

    # Test with no line of sight
    goblin.sensory.update_fov(set())
    passed, details = prereq.check(goblin, skeleton, {})
    print(f"LineOfSightPrerequisite (not visible): Passed = {passed}")
    print_log_details(details)

def test_range_prerequisite():
    print("\n=== Testing RangePrerequisite ===")
    goblin = create_goblin("Goblin")
    skeleton = create_skeleton("Skeleton")

    # Set up positions and distance
    goblin.sensory.update_origin((0, 0))
    skeleton.sensory.update_origin((1, 0))
    goblin.sensory.update_distance_matrix({(1, 0): 5})

    prereq = RangePrerequisite(name="Range Test", range_type=RangeType.REACH, range_normal=5)
    passed, details = prereq.check(goblin, skeleton, {})
    print(f"RangePrerequisite (in range): Passed = {passed}")
    print_log_details(details)

    # Test with target out of range
    skeleton.sensory.update_origin((2, 0))
    goblin.sensory.update_distance_matrix({(2, 0): 10})
    passed, details = prereq.check(goblin, skeleton, {})
    print(f"RangePrerequisite (out of range): Passed = {passed}")
    print_log_details(details)



def test_path_exists_prerequisite():
    print("\n=== Testing PathExistsPrerequisite ===")
    goblin = create_goblin("Goblin")

    goblin.sensory.update_origin((0, 0))
    target_position = (1, 1)
    goblin.sensory.update_paths({target_position: [(0, 0), (0, 1), (1, 1)]})

    prereq = PathExistsPrerequisite(name="Path Test")
    passed, details = prereq.check(goblin, target_position, {})
    print(f"PathExistsPrerequisite (path exists): Passed = {passed}")
    print_log_details(details)

    # Test with no path
    no_path_position = (5, 5)
    passed, details = prereq.check(goblin, no_path_position, {})
    print(f"PathExistsPrerequisite (no path): Passed = {passed}")
    print_log_details(details)

def test_movement_budget_prerequisite():
    print("\n=== Testing MovementBudgetPrerequisite ===")
    goblin = create_goblin("Goblin")

    goblin.sensory.update_origin((0, 0))
    target_position = (1, 1)
    path = [(0, 0), (0, 1), (1, 1)]
    goblin.sensory.update_paths({target_position: path})

    prereq = MovementBudgetPrerequisite(name="Movement Budget Test")
    passed, details = prereq.check(goblin, target_position, {})
    print(f"MovementBudgetPrerequisite (sufficient budget): Passed = {passed}")
    print_log_details(details)

    # Test with insufficient movement budget
    goblin.action_economy.movement.self_static.add_bonus("test", -25)  # Reduce movement to 5
    passed, details = prereq.check(goblin, target_position, {})
    print(f"MovementBudgetPrerequisite (insufficient budget): Passed = {passed}")
    print_log_details(details)

if __name__ == "__main__":
    test_action_economy_prerequisite()
    test_line_of_sight_prerequisite()
    test_range_prerequisite()
    test_path_exists_prerequisite()
    test_movement_budget_prerequisite()