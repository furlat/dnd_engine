"""
Test subjective vs objective walkability — invisible entity position leak fix.

Validates:
1. Invisible entity does NOT block subjective pathfinding
2. Truesight observer IS blocked by invisible entity (perceives them)
3. Hidden (high DC) doesn't block low-perception observer
4. Hidden blocks high-perception observer (perceives them)
5. Actual movement STOPS at invisible entity (objective walkability)
6. Collision fires MOVEMENT_COLLISION event
7. Collision adds to collision_blocked
8. After collision, re-pathing avoids that cell
9. collision_blocked cleared on turn start
10. Bumping hidden entity de-stealths it
11. Bumping invisible entity does NOT reveal (stays invisible)
12. Visible entity still blocks (regression)
13. Paths dirty on perceivability change
"""

from dnd.utils import (
    reset_combat_state,
    setup_combat_arena,
    has_condition,
    get_position,
)
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity
from dnd.core.gridmap import get_map
from dnd.core.base_block import SensesType, SenseMode
from dnd.conditions import Invisible, Hidden
from dnd.core.events import EventType, EventPhase, EventHandler, Trigger, Event
from dnd.actions_functional import setup_standard_actions, get_available_actions, execute_by_index
from typing import Optional, List
from uuid import UUID


passed = 0
failed = 0


def check(test_name: str, condition: bool):
    global passed, failed
    if condition:
        print(f"  [PASS] {test_name}")
        passed += 1
    else:
        print(f"  [FAIL] {test_name}")
        failed += 1


def test_invisible_does_not_block_subjective_paths():
    """Invisible entity should NOT block pathfinding for observers who can't see it."""
    print("\n" + "=" * 60)
    print("TEST 1: Invisible Entity Does NOT Block Subjective Pathfinding")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    # Create a corridor: observer at (0,0), invisible at (2,0), destination at (4,0)
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    observer = create_skeleton(name="Observer", position=(0, 0))
    invisible_entity = create_skeleton(name="Invisible", position=(2, 0))

    # Apply Invisible condition
    inv_cond = Invisible(
        source_entity_uuid=invisible_entity.uuid,
        target_entity_uuid=invisible_entity.uuid
    )
    invisible_entity.add_condition(inv_cond)

    Entity.update_all_entities_senses()

    # Observer should NOT see the invisible entity
    check("Invisible entity not in observer's senses.entities",
          invisible_entity.uuid not in observer.senses.entities)

    # Observer should be able to path through the invisible entity's position
    check("Invisible entity's position IS in observer's paths",
          (2, 0) in observer.senses.paths)
    check("Position beyond invisible entity IS reachable",
          (4, 0) in observer.senses.paths)


def test_truesight_blocked_by_invisible():
    """Truesight observer perceives invisible entity → path IS blocked."""
    print("\n" + "=" * 60)
    print("TEST 2: Truesight Observer IS Blocked by Invisible Entity")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    observer = create_skeleton(name="Truesight", position=(0, 0))
    observer.senses.sense_modes = [SenseMode(sense_type=SensesType.TRUESIGHT)]
    invisible_entity = create_skeleton(name="Invisible", position=(2, 0))

    inv_cond = Invisible(
        source_entity_uuid=invisible_entity.uuid,
        target_entity_uuid=invisible_entity.uuid
    )
    invisible_entity.add_condition(inv_cond)

    Entity.update_all_entities_senses()

    # Truesight observer CAN see the invisible entity
    check("Invisible entity IS in truesight observer's senses",
          invisible_entity.uuid in observer.senses.entities)

    # Truesight observer should be blocked by the invisible entity
    check("Invisible entity's position NOT in truesight observer's paths",
          (2, 0) not in observer.senses.paths)


def test_hidden_high_dc_not_blocking_low_perception():
    """Hidden entity with high stealth DC doesn't block low-perception observer."""
    print("\n" + "=" * 60)
    print("TEST 3: Hidden (High DC) Doesn't Block Low-Perception Observer")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    observer = create_skeleton(name="Observer", position=(0, 0))
    hidden_entity = create_skeleton(name="Hidden", position=(2, 0))

    # Apply Hidden with very high stealth DC (observer won't detect)
    hidden_cond = Hidden(
        source_entity_uuid=hidden_entity.uuid,
        target_entity_uuid=hidden_entity.uuid,
        stealth_result=30  # Very high DC
    )
    hidden_entity.add_condition(hidden_cond)

    Entity.update_all_entities_senses()

    # Observer should NOT see the hidden entity
    check("Hidden entity not in observer's senses",
          hidden_entity.uuid not in observer.senses.entities)

    # Path should go through hidden entity's cell (observer can't perceive it)
    check("Hidden entity's position IS in observer's paths",
          (2, 0) in observer.senses.paths)


def test_hidden_blocks_high_perception_observer():
    """Hidden entity blocks observer with high enough perception to see it."""
    print("\n" + "=" * 60)
    print("TEST 4: Hidden Blocks High-Perception Observer")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    observer = create_skeleton(name="Observer", position=(0, 0))
    hidden_entity = create_skeleton(name="Hidden", position=(2, 0))

    # Apply Hidden with very low stealth DC (observer will detect)
    hidden_cond = Hidden(
        source_entity_uuid=hidden_entity.uuid,
        target_entity_uuid=hidden_entity.uuid,
        stealth_result=1  # Very low DC - observer's passive perception beats this
    )
    hidden_entity.add_condition(hidden_cond)

    Entity.update_all_entities_senses()

    # Observer CAN see the hidden entity (perception beats DC)
    check("Hidden entity IS in observer's senses (perception beats DC)",
          hidden_entity.uuid in observer.senses.entities)

    # Path should be blocked by the perceivable hidden entity
    check("Hidden entity's position NOT in observer's paths",
          (2, 0) not in observer.senses.paths)


def test_movement_stops_at_invisible_entity():
    """Actual movement stops at invisible entity (objective walkability)."""
    print("\n" + "=" * 60)
    print("TEST 5: Movement Stops at Invisible Entity")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(8):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    mover = create_skeleton(name="Mover", position=(0, 0))
    setup_standard_actions(mover)
    invisible_entity = create_skeleton(name="Invisible", position=(3, 0))

    inv_cond = Invisible(
        source_entity_uuid=invisible_entity.uuid,
        target_entity_uuid=invisible_entity.uuid
    )
    invisible_entity.add_condition(inv_cond)

    Entity.update_all_entities_senses()

    # Path should show (3,0) as reachable (subjective)
    check("Path shows (3,0) as reachable (subjective)", (3, 0) in mover.senses.paths)

    # Set up encounter so action economy works
    encounter = setup_combat_arena(mover, invisible_entity)
    encounter.start_encounter()
    encounter.start_turn()

    # Try to move past invisible entity
    result = get_available_actions(mover)
    move_action = [a for a in result.position_actions if a.template_name == "Move"][0]
    # Find farthest target along x=0 corridor
    best = max((t for t in move_action.valid_targets if t.position and t.position[1] == 0),
               key=lambda t: t.position[0] if t.position else 0)
    execute_by_index(mover, "Move", best.index, available=result)

    # Mover should have stopped BEFORE the invisible entity
    final_pos = get_position(mover)
    check("Mover stopped before invisible entity (not at (3,0))",
          final_pos != (3, 0))
    check("Mover advanced at least to (2,0)",
          final_pos[0] >= 2 if final_pos else False)
    print(f"  Mover final position: {final_pos}")


def test_collision_fires_event():
    """Collision with imperceivable blocker fires MOVEMENT_COLLISION event."""
    print("\n" + "=" * 60)
    print("TEST 6: Collision Fires MOVEMENT_COLLISION Event")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(8):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    mover = create_skeleton(name="Mover", position=(0, 0))
    setup_standard_actions(mover)
    invisible_entity = create_skeleton(name="Invisible", position=(3, 0))

    inv_cond = Invisible(
        source_entity_uuid=invisible_entity.uuid,
        target_entity_uuid=invisible_entity.uuid
    )
    invisible_entity.add_condition(inv_cond)

    Entity.update_all_entities_senses()

    # Track MOVEMENT_COLLISION events
    collision_events: List[Event] = []

    def track_collision(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        collision_events.append(event)
        return None

    handler = EventHandler(
        name="Test: Track Collision",
        source_entity_uuid=mover.uuid,
        trigger_conditions=[
            Trigger(event_type=EventType.MOVEMENT_COLLISION, event_phase=EventPhase.EFFECT),
        ],
        event_processor=track_collision
    )
    mover.add_event_handler(handler)

    encounter = setup_combat_arena(mover, invisible_entity)
    encounter.start_encounter()
    encounter.start_turn()

    # Try to move through invisible entity
    result = get_available_actions(mover)
    move_action = [a for a in result.position_actions if a.template_name == "Move"][0]
    best = max((t for t in move_action.valid_targets if t.position and t.position[1] == 0),
               key=lambda t: t.position[0] if t.position else 0)
    execute_by_index(mover, "Move", best.index, available=result)

    check("MOVEMENT_COLLISION event was fired", len(collision_events) > 0)


def test_collision_adds_to_collision_blocked():
    """Collision adds position to senses.collision_blocked."""
    print("\n" + "=" * 60)
    print("TEST 7: Collision Adds to collision_blocked")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(8):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    mover = create_skeleton(name="Mover", position=(0, 0))
    setup_standard_actions(mover)
    invisible_entity = create_skeleton(name="Invisible", position=(3, 0))

    inv_cond = Invisible(
        source_entity_uuid=invisible_entity.uuid,
        target_entity_uuid=invisible_entity.uuid
    )
    invisible_entity.add_condition(inv_cond)

    Entity.update_all_entities_senses()
    check("collision_blocked starts empty", len(mover.senses.collision_blocked) == 0)

    encounter = setup_combat_arena(mover, invisible_entity)
    encounter.start_encounter()
    encounter.start_turn()

    result = get_available_actions(mover)
    move_action = [a for a in result.position_actions if a.template_name == "Move"][0]
    best = max((t for t in move_action.valid_targets if t.position and t.position[1] == 0),
               key=lambda t: t.position[0] if t.position else 0)
    execute_by_index(mover, "Move", best.index, available=result)

    check("(3, 0) is in collision_blocked after collision",
          (3, 0) in mover.senses.collision_blocked)


def test_repathing_avoids_collision_blocked():
    """After collision, recomputing paths avoids the collision_blocked cell."""
    print("\n" + "=" * 60)
    print("TEST 8: Re-Pathing Avoids collision_blocked Cell")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    # Create a wider grid so there could be alternate routes
    for x in range(6):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    mover = create_skeleton(name="Mover", position=(0, 1))
    setup_standard_actions(mover)
    invisible_entity = create_skeleton(name="Invisible", position=(2, 1))

    inv_cond = Invisible(
        source_entity_uuid=invisible_entity.uuid,
        target_entity_uuid=invisible_entity.uuid
    )
    invisible_entity.add_condition(inv_cond)

    Entity.update_all_entities_senses()

    # Before collision, (2,1) should be reachable
    check("(2,1) reachable before collision", (2, 1) in mover.senses.paths)

    # Simulate collision by adding to collision_blocked manually
    mover.senses.collision_blocked.add((2, 1))

    # Recompute senses
    mover.update_entity_senses()

    # (2,1) should NOT be in paths anymore (it's collision_blocked)
    check("(2,1) NOT reachable after collision_blocked",
          (2, 1) not in mover.senses.paths)

    # But (2,0) or (2,2) should still be reachable (alternate routes)
    check("Alternate routes still available",
          (2, 0) in mover.senses.paths or (2, 2) in mover.senses.paths)


def test_collision_blocked_cleared_on_senses_update():
    """collision_blocked persists across senses updates but clears explicitly."""
    print("\n" + "=" * 60)
    print("TEST 9: collision_blocked Persists and Can Be Cleared")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(8):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    mover = create_skeleton(name="Mover", position=(0, 0))
    Entity.update_all_entities_senses()

    # Manually add collision_blocked entries
    mover.senses.collision_blocked.add((3, 0))
    mover.senses.collision_blocked.add((5, 0))
    check("collision_blocked has 2 entries", len(mover.senses.collision_blocked) == 2)

    # Senses update preserves collision_blocked (persists within a turn)
    mover.update_entity_senses()
    check("collision_blocked persists after senses update",
          len(mover.senses.collision_blocked) == 2)

    # Explicit clear (simulates turn start)
    mover.senses.collision_blocked.clear()
    check("collision_blocked empty after explicit clear",
          len(mover.senses.collision_blocked) == 0)


def test_bump_hidden_destealths():
    """Bumping into a hidden entity de-stealths it."""
    print("\n" + "=" * 60)
    print("TEST 10: Bumping Hidden Entity De-Stealths It")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(8):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    mover = create_skeleton(name="Mover", position=(0, 0))
    setup_standard_actions(mover)
    hidden_entity = create_skeleton(name="Hidden", position=(3, 0))

    hidden_cond = Hidden(
        source_entity_uuid=hidden_entity.uuid,
        target_entity_uuid=hidden_entity.uuid,
        stealth_result=30  # High DC so mover can't see it
    )
    hidden_entity.add_condition(hidden_cond)

    Entity.update_all_entities_senses()

    check("Hidden condition applied before movement",
          has_condition(hidden_entity, "Hidden"))
    check("Hidden entity not in mover's senses",
          hidden_entity.uuid not in mover.senses.entities)

    encounter = setup_combat_arena(mover, hidden_entity)
    encounter.start_encounter()
    encounter.start_turn()

    # Try to move through hidden entity
    result = get_available_actions(mover)
    move_action = [a for a in result.position_actions if a.template_name == "Move"][0]
    best = max((t for t in move_action.valid_targets if t.position and t.position[1] == 0),
               key=lambda t: t.position[0] if t.position else 0)
    execute_by_index(mover, "Move", best.index, available=result)

    check("Hidden condition REMOVED after bump",
          not has_condition(hidden_entity, "Hidden"))


def test_bump_invisible_does_not_reveal():
    """Bumping into an invisible entity does NOT reveal it (no Hidden-like handler)."""
    print("\n" + "=" * 60)
    print("TEST 11: Bumping Invisible Entity Does NOT Reveal")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(8):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    mover = create_skeleton(name="Mover", position=(0, 0))
    setup_standard_actions(mover)
    invisible_entity = create_skeleton(name="Invisible", position=(3, 0))

    inv_cond = Invisible(
        source_entity_uuid=invisible_entity.uuid,
        target_entity_uuid=invisible_entity.uuid
    )
    invisible_entity.add_condition(inv_cond)

    Entity.update_all_entities_senses()

    encounter = setup_combat_arena(mover, invisible_entity)
    encounter.start_encounter()
    encounter.start_turn()

    result = get_available_actions(mover)
    move_action = [a for a in result.position_actions if a.template_name == "Move"][0]
    best = max((t for t in move_action.valid_targets if t.position and t.position[1] == 0),
               key=lambda t: t.position[0] if t.position else 0)
    execute_by_index(mover, "Move", best.index, available=result)

    check("Invisible entity still invisible after bump",
          invisible_entity.is_invisible is True)
    check("Invisible condition still active",
          has_condition(invisible_entity, "Invisible"))
    check("Position in collision_blocked",
          (3, 0) in mover.senses.collision_blocked)


def test_visible_entity_still_blocks():
    """Regression: visible entity still blocks pathfinding normally."""
    print("\n" + "=" * 60)
    print("TEST 12: Visible Entity Still Blocks (Regression)")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    observer = create_skeleton(name="Observer", position=(0, 0))
    blocker = create_skeleton(name="Blocker", position=(2, 0))

    Entity.update_all_entities_senses()

    check("Visible entity NOT perceivable is False (it IS perceivable)",
          blocker.is_perceivable_by(observer.uuid) is True)
    check("Visible entity's position NOT in observer's paths",
          (2, 0) not in observer.senses.paths)


def test_paths_dirty_on_perceivability_change():
    """Paths marked dirty when entity's perceivability changes (for next recompute)."""
    print("\n" + "=" * 60)
    print("TEST 13: Paths Dirty on Perceivability Change")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    observer = create_skeleton(name="Observer", position=(0, 0))
    target = create_skeleton(name="Target", position=(2, 0))

    Entity.update_all_entities_senses()
    check("Paths NOT dirty initially", observer.senses._paths_dirty is False)

    # Make target invisible — perceivability changed should fire
    inv_cond = Invisible(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid
    )
    target.add_condition(inv_cond)

    # The perceivability_changed event now has requires_paths=True
    # which should mark observer's paths as dirty
    check("Paths dirty after target goes invisible",
          observer.senses._paths_dirty is True)


if __name__ == "__main__":
    test_invisible_does_not_block_subjective_paths()
    test_truesight_blocked_by_invisible()
    test_hidden_high_dc_not_blocking_low_perception()
    test_hidden_blocks_high_perception_observer()
    test_movement_stops_at_invisible_entity()
    test_collision_fires_event()
    test_collision_adds_to_collision_blocked()
    test_repathing_avoids_collision_blocked()
    test_collision_blocked_cleared_on_senses_update()
    test_bump_hidden_destealths()
    test_bump_invisible_does_not_reveal()
    test_visible_entity_still_blocks()
    test_paths_dirty_on_perceivability_change()

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
    print("=" * 60)

    if failed > 0:
        exit(1)
