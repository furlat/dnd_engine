#!/usr/bin/env python
"""Regression tests for the standard arena directional wall/door hotswap."""

import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dnd.actions_functional import execute_use_action, get_available_actions
from dnd.core.base_block import BaseBlock
from dnd.core.events import EventPhase, EventQueue, EventType, SpatialChangeEvent
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.maps.arena_layout import DOOR_POSITION, WALL_POSITIONS
from server.event_server import setup_arena_combat
from server.mapeditor_support import build_forgotten_crypt_arena_map, reset_editor_world


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


def object_at(position: tuple[int, int], object_type: type):
    grid = get_map()
    for object_uuid in grid.get_objects_at(position):
        obj = BaseBlock.get(object_uuid)
        if isinstance(obj, object_type):
            return obj
    return None


def transition_blocked_all_channels(from_pos: tuple[int, int], to_pos: tuple[int, int], requester_uuid=None) -> bool:
    grid = get_map()
    return (
        not grid.can_transition(from_pos, to_pos, requester_uuid)
        and not grid.can_see_transition(from_pos, to_pos, requester_uuid)
        and not grid.can_light_transition(from_pos, to_pos, requester_uuid)
        and not grid.can_propagate_transition(from_pos, to_pos, requester_uuid)
    )


def transition_open_all_channels(from_pos: tuple[int, int], to_pos: tuple[int, int], requester_uuid=None) -> bool:
    grid = get_map()
    return (
        grid.can_transition(from_pos, to_pos, requester_uuid)
        and grid.can_see_transition(from_pos, to_pos, requester_uuid)
        and grid.can_light_transition(from_pos, to_pos, requester_uuid)
        and grid.can_propagate_transition(from_pos, to_pos, requester_uuid)
    )


def test_live_arena_uses_directional_structures() -> None:
    print("\nTEST: live arena uses directional wall and door")
    setup_arena_combat(player_position=(6, 7), character_class="fighter")
    grid = get_map()
    hero = next(entity for entity in Entity._entity_registry.values() if entity.name == "Hero")
    door = object_at(DOOR_POSITION, DirectionalDoor)

    check("Door is DirectionalDoor", isinstance(door, DirectionalDoor))
    check("Door starts closed", isinstance(door, DirectionalDoor) and not door.is_open)
    check("Door blocks west-side movement/vision/light/propagation", transition_blocked_all_channels((6, 7), (7, 7), hero.uuid))
    check("Door blocks east-side movement/vision/light/propagation", transition_blocked_all_channels((8, 7), (7, 7), hero.uuid))

    for position in WALL_POSITIONS:
        tile = grid.get_tile(*position)
        wall = object_at(position, DirectionalWall)
        check(f"Wall tile {position} remains floor-like", tile is not None and tile.walkable and tile.visible)
        check(f"Wall object {position} is DirectionalWall", isinstance(wall, DirectionalWall))
        for neighbor in ((position[0] - 1, position[1]), (position[0] + 1, position[1]), (position[0], position[1] - 1), (position[0], position[1] + 1)):
            if grid.get_tile(*neighbor) is not None:
                check(f"Wall blocks transition {neighbor}->{position}", transition_blocked_all_channels(neighbor, position, hero.uuid))

    Entity.update_all_entities_senses(max_distance=20)
    visible_objects = hero.senses.objects
    wall_uuids = {
        object_at(position, DirectionalWall).uuid
        for position in WALL_POSITIONS
        if object_at(position, DirectionalWall) is not None
    }
    check("Directional walls do not appear in senses.objects", wall_uuids.isdisjoint(visible_objects))
    check("Directional door appears in senses.objects", isinstance(door, DirectionalDoor) and door.uuid in visible_objects)

    actions = get_available_actions(hero)
    open_actions = [action for action in actions.self_actions if "Open Door" in (action.template_name or "")]
    check("Open Door action is available", bool(open_actions))

    cursor = EventQueue.event_cursor()
    result = execute_use_action(hero, door.uuid, "Open Door") if isinstance(door, DirectionalDoor) else None
    check("Open Door action succeeds", result is not None and not result.canceled)
    check("Door is open", isinstance(door, DirectionalDoor) and door.is_open)
    check("Open door allows west-side crossing for all channels", transition_open_all_channels((6, 7), (7, 7), hero.uuid))
    check("Open door allows east-side crossing for all channels", transition_open_all_channels((8, 7), (7, 7), hero.uuid))

    object_events = [
        event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.SPATIAL_OBJECT_CHANGED
        and event.phase == EventPhase.DECLARATION
    ]
    check("Door open emits SPATIAL_OBJECT_CHANGED", bool(object_events))
    payload = object_events[-1].model_dump(mode="json") if object_events else {}
    check("Door event uses existing event type", payload.get("event_type") == "spatial_object_changed")
    check("Door event carries directional channels", set(payload.get("directional_channels") or []) == {"movement", "vision", "light", "propagation"})
    check("Door event serializes as JSON", bool(json.dumps(payload)))


def test_mapeditor_preset_uses_directional_structures() -> None:
    print("\nTEST: mapeditor crypt preset uses directional wall and door")
    reset_editor_world()
    build_forgotten_crypt_arena_map()
    grid = get_map()

    door = object_at(DOOR_POSITION, DirectionalDoor)
    check("Crypt preset door is DirectionalDoor", isinstance(door, DirectionalDoor))
    check("Crypt preset door starts closed", isinstance(door, DirectionalDoor) and not door.is_open)
    for position in WALL_POSITIONS:
        tile = grid.get_tile(*position)
        wall = object_at(position, DirectionalWall)
        check(f"Crypt wall tile {position} is floor-like", tile is not None and tile.walkable and tile.visible)
        check(f"Crypt wall object {position} is DirectionalWall", isinstance(wall, DirectionalWall))


def test_standard_builders_do_not_contain_legacy_wall_door_setup() -> None:
    print("\nTEST: standard builders do not contain legacy scalar wall/door setup")
    setup_source = inspect.getsource(setup_arena_combat)
    editor_source = inspect.getsource(build_forgotten_crypt_arena_map)
    check("Live arena builder does not instantiate TestDoorA", "TestDoorA(" not in setup_source)
    check("Mapeditor preset builder does not instantiate TestDoorA", "TestDoorA(" not in editor_source)
    check("Live arena builder does not create scalar wall strip", 'name="Wall"' not in setup_source and "walkable=False, visible=False" not in setup_source)
    check("Mapeditor preset builder does not create scalar wall strip", 'name="Wall"' not in editor_source and "walkable=False, visible=False" not in editor_source)


def main() -> None:
    print("=" * 70)
    print("Directional Arena Hotswap Tests")
    print("=" * 70)
    test_live_arena_uses_directional_structures()
    test_mapeditor_preset_uses_directional_structures()
    test_standard_builders_do_not_contain_legacy_wall_door_setup()
    print(f"\nResults: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
