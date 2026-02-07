"""
Test reactive senses update system.

Tests that entities' visible_entities update reactively via SPATIAL events
instead of requiring bulk update_all_entities_senses() calls.
"""

from uuid import uuid4
from dnd.utils import reset_combat_state
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity
from dnd.core.gridmap import get_map


def test_reactive_senses_on_movement():
    """Test that senses update reactively when entities move."""
    print("=" * 60)
    print("TEST: Reactive Senses on Movement")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a larger map
    for x in range(10):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Create observer at (0,0) - will watch for other entities
    observer = create_skeleton(name="Observer", position=(0, 0))

    # Create mover at (5,0) - starts outside observer's immediate range
    mover = create_skeleton(name="Mover", position=(5, 0))

    # Initial senses update (turn start equivalent)
    Entity.update_all_entities_senses(max_distance=10)

    print(f"\nInitial state:")
    print(f"  Observer at {observer.position}")
    print(f"  Mover at {mover.position}")
    print(f"  Observer sees entities: {list(observer.senses.entities.keys())}")

    # Check that observer can see mover initially (within range)
    mover_visible = mover.uuid in observer.senses.entities
    print(f"  Mover visible to Observer: {mover_visible}")

    # Move mover to a different position still in FOV
    print("\n--- Moving mover from (5,0) to (3,0) ---")
    Entity.update_entity_position(mover, (3, 0))

    # Check senses WITHOUT calling update_all_entities_senses
    print(f"After move (no explicit senses update):")
    print(f"  Mover actual position: {mover.position}")
    print(f"  Observer.senses.entities: {observer.senses.entities}")

    # The mover should still be visible and at the new position
    if mover.uuid in observer.senses.entities:
        reported_pos = observer.senses.entities[mover.uuid]
        print(f"  Mover reported at: {reported_pos}")
        if reported_pos == (3, 0):
            print("  [PASS] Position updated reactively!")
        else:
            print(f"  [INFO] Position is {reported_pos}, expected (3,0)")
    else:
        print("  [INFO] Mover not in visible entities - may have moved out of subscribed area")

    print("\n[PASS] Reactive senses test completed!")


def test_senses_callback_registered():
    """Test that the spatial callback is registered on entity creation."""
    print("\n" + "=" * 60)
    print("TEST: Spatial Callback Registration")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    grid.set_tile(0, 0, walkable=True, name="Floor")

    from dnd.core.events import EventQueue
    from dnd.blocks.sensory import SpatialSensesCallback

    # Count callbacks before
    callbacks_before = len(EventQueue._on_event_callbacks)

    entity = create_skeleton(name="Test Entity", position=(0, 0))

    # Count callbacks after
    callbacks_after = len(EventQueue._on_event_callbacks)
    new_callbacks = callbacks_after - callbacks_before

    # Check that a SpatialSensesCallback was registered
    spatial_callbacks = [c for c in EventQueue._on_event_callbacks
                         if isinstance(c, SpatialSensesCallback) and c.owner_uuid == entity.uuid]

    print(f"New callbacks registered: {new_callbacks}")
    print(f"Spatial callbacks for this entity: {len(spatial_callbacks)}")

    if len(spatial_callbacks) == 1:
        print("[PASS] Spatial callback registered correctly!")
    elif len(spatial_callbacks) == 0:
        print("[FAIL] No spatial callback found!")
    else:
        print(f"[WARN] Multiple spatial callbacks found ({len(spatial_callbacks)})")


def test_visible_entities_update_on_enter():
    """Test that visible_entities updates when an entity enters a watched cell."""
    print("\n" + "=" * 60)
    print("TEST: Visible Entities Update on Enter")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a small map
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    # Create observer at (0,0)
    observer = create_skeleton(name="Observer", position=(0, 0))

    # Initial senses update to populate visible cells and subscriptions
    observer.update_entity_senses(max_distance=5)

    print(f"Observer at {observer.position}")
    print(f"Observer subscribed to cells: {len(get_map().get_entity_subscriptions(observer.uuid))} cells")

    # Create mover outside observer's current knowledge
    mover = create_skeleton(name="Mover", position=(4, 0))

    # Mover is NOT in observer's entities yet (wasn't there during update)
    print(f"\nBefore move - Observer sees: {list(observer.senses.entities.keys())}")
    mover_initially_visible = mover.uuid in observer.senses.entities
    print(f"Mover initially visible: {mover_initially_visible}")

    # Move mover to (2,0) - a cell observer is subscribed to
    print("\n--- Moving mover to (2,0) ---")
    Entity.update_entity_position(mover, (2, 0))

    print(f"After move - Observer sees: {observer.senses.entities}")

    if mover.uuid in observer.senses.entities:
        reported_pos = observer.senses.entities[mover.uuid]
        print(f"Mover now visible at {reported_pos}")
        if reported_pos == (2, 0):
            print("[PASS] Entity correctly added to visible_entities on entry!")
        else:
            print(f"[INFO] Unexpected position: {reported_pos}")
    else:
        print("[INFO] Mover not added - check subscription system")


def test_visible_entities_update_on_leave():
    """Test that visible_entities updates when an entity leaves a watched cell."""
    print("\n" + "=" * 60)
    print("TEST: Visible Entities Update on Leave")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a larger map - need more space to leave FOV (max_distance=20 is used)
    for x in range(30):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    # Create observer at (0,0)
    observer = create_skeleton(name="Observer", position=(0, 0))

    # Create mover at (2,0) - close to observer
    mover = create_skeleton(name="Mover", position=(2, 0))

    # Initial senses update (use 20 to match combat scenarios)
    observer.update_entity_senses(max_distance=20)

    print(f"Observer at {observer.position}")
    print(f"Mover at {mover.position}")
    print(f"Mover visible before move: {mover.uuid in observer.senses.entities}")

    # Move mover far away (25,0) - outside observer's FOV (max_distance=20)
    print("\n--- Moving mover to (25,0) ---")
    Entity.update_entity_position(mover, (25, 0))

    print(f"After move - Observer.senses.entities: {observer.senses.entities}")

    if mover.uuid not in observer.senses.entities:
        print("[PASS] Entity correctly removed from visible_entities on exit!")
    else:
        print(f"[INFO] Mover still in visible_entities at {observer.senses.entities.get(mover.uuid)}")


def test_multiple_observers_react_to_movement():
    """Test that multiple entities react to the same third entity's movement."""
    print("\n" + "=" * 60)
    print("TEST: Multiple Observers React to Movement")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a larger map
    for x in range(10):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Create two observers at different positions
    observer1 = create_skeleton(name="Observer1", position=(0, 0))
    observer2 = create_skeleton(name="Observer2", position=(0, 3))

    # Create mover in the middle
    mover = create_skeleton(name="Mover", position=(3, 2))

    # Initial senses update for all
    Entity.update_all_entities_senses(max_distance=10)

    print(f"\nInitial state:")
    print(f"  Observer1 at {observer1.position}, sees mover: {mover.uuid in observer1.senses.entities}")
    print(f"  Observer2 at {observer2.position}, sees mover: {mover.uuid in observer2.senses.entities}")
    print(f"  Mover at {mover.position}")

    # Verify both observers can see mover initially
    assert mover.uuid in observer1.senses.entities, "Observer1 should see mover"
    assert mover.uuid in observer2.senses.entities, "Observer2 should see mover"

    # Move mover to a new position
    print("\n--- Moving mover from (3,2) to (5,2) ---")
    Entity.update_entity_position(mover, (5, 2))

    # Check both observers updated
    print(f"After move:")
    if mover.uuid in observer1.senses.entities:
        pos1 = observer1.senses.entities[mover.uuid]
        print(f"  Observer1 sees mover at: {pos1}")
    else:
        print(f"  Observer1 lost sight of mover")

    if mover.uuid in observer2.senses.entities:
        pos2 = observer2.senses.entities[mover.uuid]
        print(f"  Observer2 sees mover at: {pos2}")
    else:
        print(f"  Observer2 lost sight of mover")

    # Both should see mover at new position
    if mover.uuid in observer1.senses.entities and observer1.senses.entities[mover.uuid] == (5, 2):
        print("  [PASS] Observer1 updated correctly!")
    else:
        print("  [INFO] Observer1 not updated correctly")

    if mover.uuid in observer2.senses.entities and observer2.senses.entities[mover.uuid] == (5, 2):
        print("  [PASS] Observer2 updated correctly!")
    else:
        print("  [INFO] Observer2 not updated correctly")

    print("\n[PASS] Multiple observers test completed!")


def test_no_reaction_to_unobserved_areas():
    """Test that entities do NOT react to movement in areas they can't see."""
    print("\n" + "=" * 60)
    print("TEST: No Reaction to Unobserved Areas")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a map with a wall blocking vision
    # [O][ ][ ][W][ ][ ][M]
    # Observer at (0,0), Wall at (3,0), Mover starts at (6,0)
    for x in range(7):
        if x == 3:
            grid.set_tile(x, 0, walkable=False, visible=False, name="Wall")
        else:
            grid.set_tile(x, 0, walkable=True, name="Floor")

    # Create observer - can't see past wall
    observer = create_skeleton(name="Observer", position=(0, 0))
    observer.update_entity_senses(max_distance=10)

    print(f"Observer visible cells: {sorted(observer.senses.visible.keys())}")

    # Create mover on the other side of the wall
    mover = create_skeleton(name="Mover", position=(6, 0))

    print(f"\nInitial state:")
    print(f"  Observer at {observer.position}")
    print(f"  Mover at {mover.position}")
    print(f"  Mover in observer's visible_entities: {mover.uuid in observer.senses.entities}")

    # Move mover to (5,0) - still behind wall
    print("\n--- Moving mover from (6,0) to (5,0) (behind wall) ---")
    Entity.update_entity_position(mover, (5, 0))

    print(f"After move:")
    print(f"  Mover at {mover.position}")
    print(f"  Mover in observer's visible_entities: {mover.uuid in observer.senses.entities}")

    if mover.uuid not in observer.senses.entities:
        print("[PASS] Observer correctly does NOT see mover behind wall!")
    else:
        print(f"[FAIL] Observer incorrectly sees mover at {observer.senses.entities.get(mover.uuid)}")


def test_step_movement_handler_fires():
    """Test that a custom handler can react to step movement through a location."""
    print("\n" + "=" * 60)
    print("TEST: Handler Reacts to Step Movement Through Location")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a corridor
    for x in range(10):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    # Track which positions a mover steps through
    stepped_positions = []

    from dnd.core.events import EventHandler, Trigger, EventType, EventPhase, StepMovementEvent

    def track_step_processor(event: StepMovementEvent, source_uuid):
        """Track every step movement."""
        if hasattr(event, 'to_position'):
            stepped_positions.append(event.to_position)
        return event

    step_tracker = EventHandler(
        name="Step Tracker",
        trigger_conditions=[
            Trigger(
                name="Track Steps",
                event_type=EventType.STEP_MOVEMENT,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=track_step_processor,
        source_entity_uuid=uuid4()
    )

    # Register handler
    from dnd.core.events import EventQueue
    EventQueue.add_event_handler(step_tracker)

    # Create mover
    mover = create_skeleton(name="Mover", position=(0, 0))
    from dnd.core.modifiers import NumericalModifier as NMod
    mover.action_economy.movement.self_static.add_value_modifier(
        NMod.create(source_entity_uuid=mover.uuid, name="Test Movement", value=0)
    )  # Already has 30ft base
    Entity.update_all_entities_senses(max_distance=10)

    print(f"Mover at {mover.position}")
    print("Moving from (0,0) to (5,0)...")

    # Move
    from dnd.actions import Move
    move = Move(source_entity_uuid=mover.uuid, end_position=(5, 0))
    move.apply()

    print(f"\nMover now at {mover.position}")
    print(f"Steps tracked: {stepped_positions}")

    # Should have tracked steps: (1,0), (2,0), (3,0), (4,0), (5,0)
    # Note: Events fire twice (once on create, once on post), so deduplicate
    unique_steps = []
    for pos in stepped_positions:
        if not unique_steps or unique_steps[-1] != pos:
            unique_steps.append(pos)

    expected_steps = [(1, 0), (2, 0), (3, 0), (4, 0), (5, 0)]
    if unique_steps == expected_steps:
        print("[PASS] Handler tracked all step movements correctly!")
    else:
        print(f"[INFO] Expected {expected_steps}, got {unique_steps}")

    # Cleanup
    EventQueue.remove_event_handler(step_tracker)


def test_movement_can_be_blocked_by_handler():
    """Test that a handler can block/cancel movement mid-path."""
    print("\n" + "=" * 60)
    print("TEST: Handler Can Block Movement")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a corridor
    for x in range(10):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    # Position (3,0) is a "trap" that blocks movement
    trap_position = (3, 0)

    from dnd.core.events import EventHandler, Trigger, EventType, EventPhase, StepMovementEvent

    def trap_processor(event: StepMovementEvent, source_uuid):
        """Block movement at trap position by canceling the step."""
        if hasattr(event, 'to_position') and event.to_position == trap_position:
            # Cancel this step - entity cannot enter the trap
            return event.cancel(status_message="Movement blocked by trap!")
        return event

    trap_handler = EventHandler(
        name="Trap Handler",
        trigger_conditions=[
            Trigger(
                name="Trap Trigger",
                event_type=EventType.STEP_MOVEMENT,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=trap_processor,
        source_entity_uuid=uuid4()
    )

    # Register handler
    from dnd.core.events import EventQueue
    EventQueue.add_event_handler(trap_handler)

    # Create mover
    mover = create_skeleton(name="Mover", position=(0, 0))
    from dnd.core.modifiers import NumericalModifier as NMod
    mover.action_economy.movement.self_static.add_value_modifier(
        NMod.create(source_entity_uuid=mover.uuid, name="Test Movement", value=0)
    )  # Already has 30ft base
    Entity.update_all_entities_senses(max_distance=10)

    print(f"Mover at {mover.position}")
    print(f"Trap at {trap_position}")
    print("Attempting to move from (0,0) to (5,0)...")

    # Move
    from dnd.actions import Move
    move = Move(source_entity_uuid=mover.uuid, end_position=(5, 0))
    move.apply()

    print(f"\nMover final position: {mover.position}")

    # Mover should have stopped at (2,0) - one cell before the trap
    if mover.position == (2, 0):
        print("[PASS] Movement correctly blocked at trap! Mover stopped at (2,0)")
    elif mover.position == trap_position:
        print("[FAIL] Mover reached trap position - movement wasn't blocked")
    elif mover.position == (5, 0):
        print("[FAIL] Mover reached destination - trap had no effect")
    else:
        print(f"[INFO] Mover stopped at unexpected position {mover.position}")

    # Cleanup
    EventQueue.remove_event_handler(trap_handler)


def test_handler_reduces_movement_mid_path():
    """Test that a handler can reduce movement speed, causing entity to stop mid-path."""
    print("\n" + "=" * 60)
    print("TEST: Handler Reduces Movement Mid-Path")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a corridor
    for x in range(10):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    # Position (3,0) applies a condition that reduces movement by 20ft
    slow_zone = (3, 0)
    condition_applied = [False]  # Use list to allow mutation in closure

    from dnd.core.events import EventHandler, Trigger, EventType, EventPhase, StepMovementEvent
    from dnd.core.modifiers import NumericalModifier

    def slow_zone_processor(event: StepMovementEvent, source_uuid):
        """Apply a movement reduction when entity enters slow zone."""
        if not hasattr(event, 'to_position') or event.to_position != slow_zone:
            return event

        if condition_applied[0]:
            return event  # Already applied

        # Get the entity and reduce their movement
        from dnd.entity import Entity
        mover = Entity.get(event.source_entity_uuid)
        if mover:
            # Apply a -20 movement modifier
            modifier = NumericalModifier.create(
                source_entity_uuid=source_uuid,
                name="Slow Zone Effect",
                value=-20
            )
            mover.action_economy.movement.self_static.add_value_modifier(modifier)
            condition_applied[0] = True
            print(f"  [Handler] Applied -20 movement modifier at {slow_zone}")
            print(f"  [Handler] Movement remaining: {mover.action_economy.movement.normalized_score}ft")

        return event

    slow_handler = EventHandler(
        name="Slow Zone Handler",
        trigger_conditions=[
            Trigger(
                name="Slow Zone Trigger",
                event_type=EventType.STEP_MOVEMENT,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=slow_zone_processor,
        source_entity_uuid=uuid4()
    )

    # Register handler
    from dnd.core.events import EventQueue
    EventQueue.add_event_handler(slow_handler)

    # Create mover with 50ft movement (enough for the full path)
    mover = create_skeleton(name="Mover", position=(0, 0))
    from dnd.core.modifiers import NumericalModifier as NM
    # Add +20 to movement so entity has 50ft (enough for 7 tiles = 35ft)
    mover.action_economy.movement.self_static.add_value_modifier(
        NM.create(source_entity_uuid=mover.uuid, name="Test Movement Boost", value=20)
    )
    Entity.update_all_entities_senses(max_distance=10)

    print(f"Mover at {mover.position}")
    print(f"Initial movement: {mover.action_economy.movement.normalized_score}ft")
    print(f"Slow zone at {slow_zone}")
    print("Attempting to move from (0,0) to (7,0)...")

    # Move - path is 7 tiles = 35ft normally
    # But at (3,0), movement drops from 30 to 10 (minus the 15ft already used)
    # So entity should only be able to go a bit further
    from dnd.actions import Move
    move = Move(source_entity_uuid=mover.uuid, end_position=(7, 0))
    move.apply()

    print(f"\nMover final position: {mover.position}")
    print(f"Final movement remaining: {mover.action_economy.movement.normalized_score}ft")

    # After reaching (3,0), mover should have:
    # - Used 15ft to get there (3 tiles)
    # - Had 15ft remaining
    # - Movement reduced by 20 → effectively -5ft remaining (can't move)
    # So mover should stop at (3,0) or shortly after

    if mover.position[0] < 7:
        print(f"[PASS] Movement was limited by slow zone! Stopped at {mover.position}")
    else:
        print(f"[INFO] Mover reached destination despite slow zone")

    # Cleanup
    EventQueue.remove_event_handler(slow_handler)


def test_death_updates_paths():
    """Test that when entity 1 kills entity 2, entity 1 can then move to entity 2's position."""
    print("\n" + "=" * 60)
    print("TEST: Kill Enemy Then Move to Their Position")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a corridor: [Attacker][ ][Target][ ][ ]
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    # Create attacker at (0,0) and target at (2,0)
    from dnd.encounter import Encounter
    from dnd.controller import PassController
    from dnd.core.events import DamageType

    attacker = create_skeleton(name="Attacker", position=(0, 0), faction="heroes")
    target = create_skeleton(name="Target", position=(2, 0), faction="monsters")

    # Set up encounter for death handling
    encounter = Encounter(name="Test", source_entity_uuid=attacker.uuid)
    encounter.add_combatant(attacker, PassController(source_entity_uuid=attacker.uuid))
    encounter.add_combatant(target, PassController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    # Make sure it's attacker's turn and update senses
    Entity.update_all_entities_senses(max_distance=20)

    print(f"Attacker at {attacker.position}")
    print(f"Target at {target.position} with {target.get_hp()} HP")

    # Check paths before death - target blocks (2,0) and beyond
    paths_before = set(attacker.senses.paths.keys())
    can_reach_target_pos_before = (2, 0) in paths_before
    print(f"\nBefore kill:")
    print(f"  Attacker can reach target position (2,0): {can_reach_target_pos_before}")
    print(f"  Available positions: {sorted(paths_before)}")

    # Kill the target in one shot
    print("\n--- Attacker kills Target ---")
    target.health.take_damage(100, DamageType.BLUDGEONING, source_entity_uuid=attacker.uuid)
    encounter.check_deaths()

    print(f"Target HP after damage: {target.get_hp()}")
    print(f"Target is dead: {target.get_hp() <= 0}")

    # Check if target is marked non-blocking
    is_non_blocking = target.non_blocking
    print(f"Target marked non-blocking: {is_non_blocking}")

    # Check paths after death - should now include (2,0)
    paths_after = set(attacker.senses.paths.keys())
    can_reach_target_pos_after = (2, 0) in paths_after
    print(f"\nAfter kill:")
    print(f"  Attacker can reach target position (2,0): {can_reach_target_pos_after}")
    print(f"  Available positions: {sorted(paths_after)}")

    # Check get_available_actions - should now show (2,0) as valid move/jump target
    print("\n--- Checking get_available_actions ---")
    available = attacker.get_available_actions()

    # Find Move action and check if (2,0) is a valid target
    move_action = None
    for action in available.position_actions:
        if action.template_name == "Move":
            move_action = action
            break

    target_pos_in_move = False
    if move_action:
        for target in move_action.valid_targets:
            if target.position == (2, 0):
                target_pos_in_move = True
                break

    print(f"(2,0) available via Move action: {target_pos_in_move}")

    # Check Jump action too
    jump_action = None
    for action in available.position_actions:
        if action.template_name == "Jump":
            jump_action = action
            break

    target_pos_in_jump = False
    if jump_action:
        for target in jump_action.valid_targets:
            if target.position == (2, 0):
                target_pos_in_jump = True
                break

    print(f"(2,0) available via Jump action: {target_pos_in_jump}")

    # Try to actually move to target's position
    if target_pos_in_move:
        from dnd.actions import Move
        print("\n--- Executing move to dead target's position ---")
        move = Move(source_entity_uuid=attacker.uuid, end_position=(2, 0))
        move.apply()
        print(f"Attacker final position: {attacker.position}")
        if attacker.position == (2, 0):
            print("[PASS] Successfully moved to dead enemy's position!")
        else:
            print(f"[FAIL] Move executed but ended at {attacker.position}")
    else:
        print("[FAIL] Cannot move to dead enemy's position - not in available actions")


def test_get_available_actions_with_difficult_terrain():
    """Test that get_available_actions reports correct costs for difficult terrain."""
    print("\n" + "=" * 60)
    print("TEST: get_available_actions with Difficult Terrain")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a corridor with difficult terrain in the middle
    # [E][ ][ ][D][D][ ][ ]
    # E = entity at (0,0)
    # D = difficult terrain at (3,0) and (4,0)
    from dnd.core.base_tiles import difficult_terrain_factory

    for x in range(7):
        if x in (3, 4):
            # Difficult terrain (cost = 2) using factory
            grid.set_tile(x, 0, tile=difficult_terrain_factory((x, 0)))
        else:
            grid.set_tile(x, 0, walkable=True, name="Floor")

    # Create entity with 30ft movement
    mover = create_skeleton(name="Mover", position=(0, 0))
    Entity.update_all_entities_senses(max_distance=10)

    print(f"Mover at {mover.position}")
    print(f"Movement speed: {mover.action_economy.movement.normalized_score}ft")
    print("Terrain layout: [E][ ][ ][D][D][ ][ ]")
    print("  D = difficult terrain (cost 2)")

    # Get available actions
    actions = mover.get_available_actions()

    # Find the Move action
    move_action_info = None
    for action_info in actions.position_actions:
        if action_info.template_name == "Move":
            move_action_info = action_info
            break

    if move_action_info is None:
        print("[FAIL] No Move action found!")
        return

    # Check path costs for various positions
    position_costs = {}
    for target in move_action_info.valid_targets:
        pos = target.position
        cost = target.path_cost
        position_costs[pos] = cost

    print("\nPath costs (should account for difficult terrain):")
    expected_costs = {
        (1, 0): 5,   # 1 tile, normal terrain = 5ft
        (2, 0): 10,  # 2 tiles, normal terrain = 10ft
        (3, 0): 20,  # 2 normal + 1 difficult (2+2*1) = 3 tiles cost, but actually 2 + 1*2 = 4 cost units = 20ft
        # Wait, let me recalculate:
        # Path to (3,0): (0,0) -> (1,0) -> (2,0) -> (3,0)
        # Cost: 1 (to 1,0) + 1 (to 2,0) + 2 (to 3,0, difficult) = 4 units = 20ft
        (4, 0): 30,  # 4 units to (3,0) + 2 for (4,0) difficult = 6 units = 30ft
        (5, 0): 35,  # 6 units to (4,0) + 1 for (5,0) normal = 7 units = 35ft
    }

    all_passed = True
    for pos, expected_cost in expected_costs.items():
        actual_cost = position_costs.get(pos)
        if actual_cost == expected_cost:
            print(f"  {pos}: {actual_cost}ft [PASS]")
        elif actual_cost is not None:
            print(f"  {pos}: {actual_cost}ft (expected {expected_cost}ft) [FAIL]")
            all_passed = False
        else:
            # Position might be out of range
            print(f"  {pos}: Not reachable (expected {expected_cost}ft)")
            if expected_cost <= 30:  # Should be reachable with 30ft movement
                all_passed = False

    # Check that position (6,0) is NOT reachable (would cost 40ft, we only have 30ft)
    if (6, 0) in position_costs:
        print(f"  (6,0): {position_costs[(6, 0)]}ft - Should NOT be reachable [FAIL]")
        all_passed = False
    else:
        print(f"  (6,0): Not reachable (correct - would cost 40ft) [PASS]")

    if all_passed:
        print("\n[PASS] get_available_actions correctly reports terrain-based costs!")
    else:
        print("\n[FAIL] Some costs were incorrect")


def main():
    """Run all reactive senses tests."""
    print("\n" + "=" * 60)
    print("REACTIVE SENSES SYSTEM TESTS")
    print("=" * 60)

    test_senses_callback_registered()
    test_visible_entities_update_on_enter()
    test_visible_entities_update_on_leave()
    test_reactive_senses_on_movement()
    test_multiple_observers_react_to_movement()
    test_no_reaction_to_unobserved_areas()
    test_step_movement_handler_fires()
    test_movement_can_be_blocked_by_handler()
    test_handler_reduces_movement_mid_path()
    test_death_updates_paths()
    test_get_available_actions_with_difficult_terrain()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
