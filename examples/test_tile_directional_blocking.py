"""Focused tests for tile-owned directional blocking.

These cover the minimal model:
- placed blocks/items carry tile-relative directional blockers
- GridMap propagates those blockers into the owning tile state
- transitions consult both endpoint tiles
- movement, vision, light, and propagation read the same directional facts
- existing spatial events carry optional directional metadata
"""

import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dnd.blocks.base_item import BaseItem
from dnd.actions import Jump
from dnd.core.events import EventPhase, EventQueue, EventType, SpatialChangeEvent, StepMovementEvent
from dnd.core.geometry import supercover_line
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.reactions import opportunity_attack_processor
from dnd.utils import reset_combat_state
from server.api_models import APIGrid, MapEditorSaveMapRequest, MapEditorTilePatch
from server.mapeditor_support import (
    apply_tile_patches,
    build_scratch_map,
    get_editor_snapshot,
    load_saved_editor_map,
    save_current_editor_map,
)
from server.api_models import MapEditorCreateMapRequest


passed = 0
failed = 0


def check(name: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name}")
        failed += 1


def make_grid() -> None:
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 5, 3)


def test_directional_movement_item_propagates_to_tile() -> None:
    print("\nTEST: directional movement item propagates to tile")
    make_grid()
    grid = get_map()

    wall = BaseItem(
        source_entity_uuid=uuid4(),
        name="Tile East Wall",
        is_pickable=False,
        blocks_movement_east=True,
    )
    grid.place_object(wall.uuid, (1, 1))

    tile = grid.get_tile(1, 1)
    assert tile is not None
    check("Cell remains walkable", grid.is_walkable(1, 1))
    check("Tile east side is movement-blocked", not tile.allows_direction("east", "movement"))
    check("Transition out through blocked side fails", not grid.can_transition((1, 1), (2, 1)))
    check("Transition into blocked tile side fails", not grid.can_transition((2, 1), (1, 1)))
    check("Other side remains open", grid.can_transition((1, 1), (0, 1)))


def test_both_endpoint_tiles_are_considered() -> None:
    print("\nTEST: both endpoint tiles are considered")
    make_grid()
    grid = get_map()

    west_half = BaseItem(
        source_entity_uuid=uuid4(),
        name="West Half Wall",
        is_pickable=False,
        blocks_movement_west=True,
    )
    grid.place_object(west_half.uuid, (2, 1))

    check("Neighbor tile's west side blocks crossing from left", not grid.can_transition((1, 1), (2, 1)))
    check("Same tile side blocks crossing from right", not grid.can_transition((2, 1), (1, 1)))
    check("Unrelated north crossing remains open", grid.can_transition((2, 1), (2, 2)))


def test_directional_vision_light_and_propagation() -> None:
    print("\nTEST: directional vision/light/propagation")
    make_grid()
    grid = get_map()

    screen = BaseItem(
        source_entity_uuid=uuid4(),
        name="Directional Screen",
        is_pickable=False,
        blocks_vision_east=True,
        blocks_light_east=True,
        blocks_propagation_east=True,
    )
    grid.place_object(screen.uuid, (1, 1))

    fov = set(grid.compute_fov((1, 1), max_distance=3))
    light = set(grid.compute_light_fov((1, 1), max_distance=3))
    propagation = set(grid.compute_propagation_fov((1, 1), max_distance=3))

    check("Vision cannot cross blocked east side", (2, 1) not in fov)
    check("Light cannot cross blocked east side", (2, 1) not in light)
    check("Propagation cannot cross blocked east side", (2, 1) not in propagation)
    check("West side remains visible", (0, 1) in fov)
    check("West side remains lit", (0, 1) in light)
    check("West side remains in propagation", (0, 1) in propagation)


def test_intrinsic_directional_border_event_metadata() -> None:
    print("\nTEST: intrinsic directional border event metadata")
    make_grid()
    grid = get_map()
    cursor = EventQueue.event_cursor()

    changed = grid.set_tile_directional_border((1, 1), "vision", "east", False)

    events = [
        event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.SPATIAL_TILE_CHANGED
        and event.phase == EventPhase.DECLARATION
    ]
    event = events[-1] if events else None

    check("Setter reports change", changed)
    check("Uses existing SPATIAL_TILE_CHANGED type", event is not None)
    check("Event carries directional position", event is not None and event.directional_position == (1, 1))
    check("Event carries changed direction", event is not None and event.directional_directions == ["east"])
    check("Event carries changed channel", event is not None and event.directional_channels == ["vision"])
    check(
        "Affected positions include both sides",
        event is not None and {(1, 1), (2, 1)} <= event.get_affected_positions(),
    )


def test_object_directional_change_event_metadata() -> None:
    print("\nTEST: object directional change event metadata")
    make_grid()
    grid = get_map()
    lever_wall = BaseItem(source_entity_uuid=uuid4(), name="Shutter", is_pickable=False)
    grid.place_object(lever_wall.uuid, (1, 1))
    cursor = EventQueue.event_cursor()

    lever_wall.set_directional_blocking("movement", "north", True)

    events = [
        event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.SPATIAL_OBJECT_CHANGED
        and event.phase == EventPhase.DECLARATION
    ]
    event = events[-1] if events else None

    check("Uses existing SPATIAL_OBJECT_CHANGED type", event is not None)
    check("Event carries directional channel", event is not None and event.directional_channels == ["movement"])
    check("Event carries directional block map", event is not None and event.directional_blocks_movement["north"])
    check(
        "Object change affects both tile and neighbor",
        event is not None and {(1, 1), (1, 2)} <= event.get_affected_positions(),
    )


def test_supercover_line_geometry() -> None:
    print("\nTEST: supercover line geometry")
    check("Orthogonal line is ordered", supercover_line((0, 0), (3, 0)) == [(0, 0), (1, 0), (2, 0), (3, 0)])
    diagonal = supercover_line((0, 0), (3, 2))
    check("Line starts at origin", diagonal[0] == (0, 0))
    check("Line ends at target", diagonal[-1] == (3, 2))
    check("Line steps are adjacent", all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 1 for a, b in zip(diagonal, diagonal[1:])))


def test_directional_hidden_collision_memory() -> None:
    print("\nTEST: directional hidden collision memory")
    make_grid()
    grid = get_map()
    mover = create_goblin(name="Mover", position=(1, 1), faction="heroes")
    blocker = BaseItem(
        source_entity_uuid=uuid4(),
        name="Hidden East Shutter",
        is_pickable=False,
        blocks_movement_east=True,
        stealth_dc=99,
    )
    grid.place_object(blocker.uuid, (1, 1))
    Entity.update_all_entities_senses()

    check("Hidden directional blocker does not leak in subjective paths", (2, 1) in mover.senses.paths)
    check("Objective transition is blocked", not grid.can_transition((1, 1), (2, 1), mover.uuid))
    check("Subjective transition is open before collision", grid.can_transition((1, 1), (2, 1), mover.uuid, subjective=True))

    from dnd.actions import Move
    move = Move(source_entity_uuid=mover.uuid, end_position=(2, 1), use_movement_cost=False)
    result = move.apply()

    check("Movement result exists", result is not None)
    check("Mover stopped before hidden directional blocker", mover.position == (1, 1))
    check("Cell collision memory remains empty", (2, 1) not in mover.senses.collision_blocked)
    check("Directional collision memory records source side", ((1, 1), "east") in mover.senses.directional_collision_blocked)

    Entity.update_all_entities_senses()
    remembered_path = mover.senses.paths.get((2, 1), [])
    check("Remembered direction avoids same crossing", len(remembered_path) < 2 or remembered_path[1] != (2, 1))
    check("Destination remains reachable from another side", grid.can_transition((2, 2), (2, 1), mover.uuid, subjective=True, directional_collision_blocked=mover.senses.directional_collision_blocked))


def test_forced_movement_and_jump_respect_directional_blocks() -> None:
    print("\nTEST: forced movement and jump respect directional blocks")
    make_grid()
    grid = get_map()
    target = create_skeleton(name="Target", position=(1, 1), faction="monsters")
    wall = BaseItem(
        source_entity_uuid=uuid4(),
        name="Directional Force Wall",
        is_pickable=False,
        blocks_movement_east=True,
        blocks_propagation_east=True,
    )
    grid.place_object(wall.uuid, (1, 1))

    from dnd.actions import Shove
    final_pos, distance, blocked, _blocker = Shove.calculate_final_position((1, 1), (1, 0), 10, target.uuid)
    check("Forced movement stops at directional movement blocker", final_pos == (1, 1) and distance == 0 and blocked)

    jumper = create_goblin(name="Jumper", position=(1, 1), faction="heroes")
    Entity.update_all_entities_senses()
    jump = Jump(source_entity_uuid=jumper.uuid, template=True)
    check("Jump target is visible", (3, 1) in jumper.senses.visible)
    check("Jump excludes propagation-blocked target", (3, 1) not in jump.get_valid_positions())


def test_threat_and_oa_respect_directional_propagation() -> None:
    print("\nTEST: threat and opportunity attack respect directional propagation")
    make_grid()
    grid = get_map()
    attacker = create_skeleton(name="Attacker", position=(1, 1), faction="monsters")
    mover = create_goblin(name="Mover", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses()

    check("Baseline adjacent target is threatened", mover.is_threatened())

    wall = BaseItem(
        source_entity_uuid=uuid4(),
        name="Threat Screen",
        is_pickable=False,
        blocks_propagation_east=True,
    )
    grid.place_object(wall.uuid, (1, 1))
    Entity.update_all_entities_senses()

    check("Directional propagation blocker removes threat", not mover.is_threatened())
    check("Threatened positions exclude blocked neighbor", (2, 1) not in attacker.senses.get_threathened_positions())

    cursor = EventQueue.event_cursor()
    step = StepMovementEvent(
        source_entity_uuid=mover.uuid,
        source_entity_name=mover.name,
        from_position=(2, 1),
        to_position=(3, 1),
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    opportunity_attack_processor(step, attacker.uuid)
    attack_events = [
        event for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type == EventType.ATTACK
    ]
    check("OA does not fire through directional propagation blocker", len(attack_events) == 0)


def test_api_mapeditor_and_event_serialization() -> None:
    print("\nTEST: API, mapeditor, and event serialization")
    make_grid()
    grid = get_map()
    grid.set_tile_directional_border((1, 1), "movement", "east", False)
    api_tile = next(tile for tile in APIGrid.create(grid).tiles if tile.x == 1 and tile.y == 1)
    check("API tile exposes movement direction map", api_tile.directional_blocks_movement["east"])

    cursor = EventQueue.event_cursor()
    grid.set_tile_directional_border((1, 1), "vision", "north", False)
    event = [
        event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent) and event.event_type == EventType.SPATIAL_TILE_CHANGED
    ][-1]
    dumped = event.model_dump(mode="json")
    check("Serialized event keeps existing event type", dumped["event_type"] == "spatial_tile_changed")
    check("Serialized directional position is JSON array", dumped["directional_position"] == [1, 1])
    check("Serialized directional map is JSON object", dumped["directional_blocks_vision"]["north"] is True)

    import os
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        old_dir = os.environ.get("DND_MAPEDITOR_SAVE_DIR")
        os.environ["DND_MAPEDITOR_SAVE_DIR"] = temp_dir
        try:
            build_scratch_map(MapEditorCreateMapRequest(width=3, height=3, origin=(0, 0), default_tile="Floor"))
            snapshot = apply_tile_patches([
                MapEditorTilePatch(
                    x=1,
                    y=1,
                    directional_channel="movement",
                    direction="east",
                    passable=False,
                )
            ])
            patched_tile = next(tile for tile in snapshot.tiles if tile.x == 1 and tile.y == 1)
            check("Mapeditor patch exposes directional state", patched_tile.directional_blocks_movement["east"])
            metadata = save_current_editor_map(MapEditorSaveMapRequest(id="directional_test", name="Directional Test", overwrite=True))
            loaded = load_saved_editor_map(metadata.id)
            loaded_tile = next(tile for tile in loaded.tiles if tile.x == 1 and tile.y == 1)
            check("Mapeditor save/load round-trips directional state", loaded_tile.directional_blocks_movement["east"])
        finally:
            if old_dir is None:
                os.environ.pop("DND_MAPEDITOR_SAVE_DIR", None)
            else:
                os.environ["DND_MAPEDITOR_SAVE_DIR"] = old_dir


if __name__ == "__main__":
    print("=" * 70)
    print("Tile Directional Blocking Tests")
    print("=" * 70)

    test_directional_movement_item_propagates_to_tile()
    test_both_endpoint_tiles_are_considered()
    test_directional_vision_light_and_propagation()
    test_intrinsic_directional_border_event_metadata()
    test_object_directional_change_event_metadata()
    test_supercover_line_geometry()
    test_directional_hidden_collision_memory()
    test_forced_movement_and_jump_respect_directional_blocks()
    test_threat_and_oa_respect_directional_propagation()
    test_api_mapeditor_and_event_serialization()

    print(f"\nResults: {passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
