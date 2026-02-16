"""Performance profiling for light source movement.

Measures where time is spent when moving a light source anchored to an entity.
"""

import time
from uuid import uuid4
from dnd.utils import reset_combat_state
from dnd.entity import Entity
from dnd.core.base_block import LightLevel
from dnd.core.gridmap import get_map
from dnd.core.events import EventQueue
from dnd.monsters.bestiary import create_skeleton
from dnd.actions_functional import setup_standard_actions


def profile_light_source_move():
    """Profile a single light source move on a dark 20x20 grid."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    # Make all tiles dark
    for x in range(20):
        for y in range(20):
            t = grid.get_tile(x, y)
            if t:
                t.default_light = LightLevel.DARKNESS

    carrier = create_skeleton(name="Torch Bearer", position=(5, 5))
    setup_standard_actions(carrier)
    Entity.update_all_entities_senses()

    # Add light source (20ft bright, 40ft dim)
    print("--- Adding light source ---")
    t0 = time.perf_counter()
    ls_uuid = grid.add_light_source(
        position=(5, 5),
        bright_radius_feet=20,
        dim_radius_feet=40,
        anchor_uuid=carrier.uuid
    )
    t1 = time.perf_counter()
    source = grid._light_sources[ls_uuid]
    print(f"  add_light_source: {t1-t0:.4f}s")
    print(f"  affected tiles: {len(source.affected_tiles)}")

    # Count how many events fire during a move
    event_count = [0]
    original_register = EventQueue.register

    def counting_register(event):
        event_count[0] += 1
        return original_register(event)

    EventQueue.register = staticmethod(counting_register)

    # Profile: move light source directly (no entity movement)
    print("\n--- Moving light source directly (5,5) -> (6,5) ---")
    event_count[0] = 0
    t0 = time.perf_counter()
    grid.move_light_source(ls_uuid, (6, 5))
    t1 = time.perf_counter()
    print(f"  move_light_source: {t1-t0:.4f}s")
    print(f"  events fired: {event_count[0]}")

    # Profile: move via entity position update (triggers callback)
    print("\n--- Moving entity (triggers light callback) (6,5) -> (7,5) ---")
    event_count[0] = 0
    t0 = time.perf_counter()
    Entity.update_entity_position(carrier, (7, 5))
    t1 = time.perf_counter()
    print(f"  Entity.update_entity_position: {t1-t0:.4f}s")
    print(f"  events fired: {event_count[0]}")

    # Restore original
    EventQueue.register = original_register

    # Check how many tiles actually CHANGED between old and new position
    # For a 1-tile move, most tiles overlap
    print("\n--- Delta analysis for 1-tile move ---")
    _old_pos = (7, 5)
    new_pos = (8, 5)
    old_tiles = set(source.affected_tiles.keys())

    # Compute what tiles WOULD be affected at new position
    import math
    total_radius_tiles = max((source.bright_radius_feet + source.dim_radius_feet) // 5, 1)
    bright_radius_tiles = max(source.bright_radius_feet // 5, 1)
    new_visible = grid.compute_fov(new_pos, total_radius_tiles)
    new_tiles = {}
    for pos in new_visible:
        dx = pos[0] - new_pos[0]
        dy = pos[1] - new_pos[1]
        dist = math.sqrt(dx*dx + dy*dy)
        if dist <= bright_radius_tiles:
            new_tiles[pos] = LightLevel.BRIGHT_LIGHT
        else:
            new_tiles[pos] = LightLevel.DIM_LIGHT
    new_tile_set = set(new_tiles.keys())

    only_old = old_tiles - new_tile_set
    only_new = new_tile_set - old_tiles
    overlap = old_tiles & new_tile_set
    same_level = sum(1 for p in overlap if source.affected_tiles.get(p) == new_tiles.get(p))

    print(f"  Old affected: {len(old_tiles)} tiles")
    print(f"  New affected: {len(new_tile_set)} tiles")
    print(f"  Only in old (remove): {len(only_old)} tiles")
    print(f"  Only in new (add): {len(only_new)} tiles")
    print(f"  Overlap: {len(overlap)} tiles")
    print(f"  Overlap with SAME level: {same_level} tiles (skip these!)")
    print(f"  Overlap with DIFFERENT level: {len(overlap) - same_level} tiles")
    print(f"  Tiles actually changing: {len(only_old) + len(only_new) + (len(overlap) - same_level)}")
    print(f"  Current approach touches: {len(old_tiles) + len(new_tile_set)} tiles (remove all + add all)")


def profile_notify_light_changed():
    """Profile the cost of a single _notify_light_changed() call."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    _carrier = create_skeleton(name="Observer", position=(5, 5))
    Entity.update_all_entities_senses()

    tile = grid.get_tile(3, 3)
    assert tile is not None
    tile.default_light = LightLevel.DARKNESS

    # Time a single light change
    print("\n--- Single _notify_light_changed() ---")
    t0 = time.perf_counter()
    fog = uuid4()
    tile.add_obscurement(fog, LightLevel.DARKNESS)  # no change, won't fire
    t1 = time.perf_counter()
    print(f"  add_obscurement (no resolved change): {t1-t0:.6f}s")

    # Now cause an actual change
    tile.remove_light_modifier(fog)
    tile.default_light = LightLevel.BRIGHT_LIGHT
    t0 = time.perf_counter()
    fog2 = uuid4()
    tile.add_obscurement(fog2, LightLevel.DARKNESS)  # BRIGHT -> DARKNESS, fires event
    t1 = time.perf_counter()
    print(f"  add_obscurement (BRIGHT->DARKNESS, fires event): {t1-t0:.6f}s")


def profile_multi_observer(observer_counts=(1, 2, 5, 10)):
    """Profile light source movement with multiple observers on the grid.

    Each observer has senses and a spatial callback registered, so light
    changes trigger senses re-evaluation for ALL observers that subscribe
    to affected tiles.
    """
    print("\n--- Multi-observer scaling ---")
    print(f"{'Observers':>10} | {'add_light':>10} | {'move_light':>10} | {'entity_move':>11} | {'events':>7}")
    print("-" * 65)

    for n_observers in observer_counts:
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        # Make all tiles dark
        for x in range(20):
            for y in range(20):
                t = grid.get_tile(x, y)
                if t:
                    t.default_light = LightLevel.DARKNESS

        # Create the torch carrier
        carrier = create_skeleton(name="Torch Bearer", position=(5, 5))
        setup_standard_actions(carrier)

        # Create observers spread across the grid
        observers = []
        observer_positions = [
            (2, 2), (8, 2), (2, 8), (8, 8), (10, 10),
            (15, 5), (5, 15), (15, 15), (0, 0), (19, 19),
        ]
        for i in range(n_observers - 1):  # -1 because carrier is already an observer
            pos = observer_positions[i % len(observer_positions)]
            obs = create_skeleton(name=f"Observer_{i+1}", position=pos)
            setup_standard_actions(obs)
            observers.append(obs)

        Entity.update_all_entities_senses()

        # Profile: add light source
        t0 = time.perf_counter()
        ls_uuid = grid.add_light_source(
            position=(5, 5),
            bright_radius_feet=20,
            dim_radius_feet=40,
            anchor_uuid=carrier.uuid,
        )
        t_add = time.perf_counter() - t0

        # Count events during move
        event_count = [0]
        original_register = EventQueue.register

        def counting_register(event):
            event_count[0] += 1
            return original_register(event)

        EventQueue.register = staticmethod(counting_register)

        # Profile: move light source directly
        event_count[0] = 0
        t0 = time.perf_counter()
        grid.move_light_source(ls_uuid, (6, 5))
        t_move = time.perf_counter() - t0

        # Profile: entity position update (triggers light callback + senses)
        event_count[0] = 0
        t0 = time.perf_counter()
        Entity.update_entity_position(carrier, (7, 5))
        t_entity = time.perf_counter() - t0
        n_events = event_count[0]

        EventQueue.register = original_register

        print(f"{n_observers:>10} | {t_add:>9.4f}s | {t_move:>9.4f}s | {t_entity:>10.4f}s | {n_events:>7}")

    print()


if __name__ == "__main__":
    print("=" * 60)
    print("LIGHT SOURCE PERFORMANCE PROFILING")
    print("=" * 60)

    profile_notify_light_changed()
    print()
    profile_light_source_move()
    print()
    profile_multi_observer()
