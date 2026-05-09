#!/usr/bin/env python
"""Focused tests for tile-owned directional walls and doors."""

import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dnd.actions import Attack, Jump, Move, Shove
from dnd.actions_functional import execute_use_action, setup_standard_actions
from dnd.core.events import EventPhase, EventQueue, EventType, SpatialChangeEvent, StepMovementEvent, WeaponSlot
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.items.environment import CloseDirectionalDoorAction, DirectionalDoor, DirectionalWall
from dnd.items.weapons import create_shortbow
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.reactions import opportunity_attack_processor
from dnd.utils import reset_combat_state
from server.event_stream import event_stream, format_sse, make_stream_id


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


def make_grid(width: int = 7, height: int = 5) -> None:
    reset_combat_state()
    get_map().create_rectangle(0, 0, width, height)


def setup_actor(name: str, position: tuple[int, int], faction: str = "heroes"):
    actor = create_goblin(name=name, position=position, faction=faction)
    setup_standard_actions(actor)
    return actor


def object_change_events_since(cursor: int) -> list[SpatialChangeEvent]:
    return [
        event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.SPATIAL_OBJECT_CHANGED
        and event.phase == EventPhase.DECLARATION
    ]


def test_directional_wall_blocks_only_configured_sides() -> None:
    print("\nTEST: directional wall blocks only configured sides")
    make_grid()
    grid = get_map()

    wall = DirectionalWall(source_entity_uuid=uuid4(), blocked_directions=("east",))
    grid.place_object(wall.uuid, (2, 2))
    tile = grid.get_tile(2, 2)

    check("Wall cell remains walkable", grid.is_walkable(2, 2))
    check("Wall object has no scalar movement block", not wall.blocks_walking())
    check("Wall object has no scalar vision block", not wall.blocks_vision())
    check("East movement transition is blocked", not grid.can_transition((2, 2), (3, 2)))
    check("East vision transition is blocked", not grid.can_see_transition((2, 2), (3, 2)))
    check("East light transition is blocked", not grid.can_light_transition((2, 2), (3, 2)))
    check("East propagation transition is blocked", not grid.can_propagate_transition((2, 2), (3, 2)))
    check("West movement remains open", grid.can_transition((2, 2), (1, 2)))
    check("North movement remains open", grid.can_transition((2, 2), (2, 3)))
    check("Tile state records east movement block", tile is not None and not tile.allows_direction("east", "movement"))

    fov = set(grid.compute_fov((2, 2), max_distance=3))
    light = set(grid.compute_light_fov((2, 2), max_distance=3))
    propagation = set(grid.compute_propagation_fov((2, 2), max_distance=3))
    check("FOV cannot cross wall side", (3, 2) not in fov)
    check("Light cannot cross wall side", (3, 2) not in light)
    check("Propagation cannot cross wall side", (3, 2) not in propagation)


def test_directional_wall_multi_side_and_thick_wall() -> None:
    print("\nTEST: multi-side and thick directional walls")
    make_grid()
    grid = get_map()

    corner = DirectionalWall(
        source_entity_uuid=uuid4(),
        blocked_directions=("north", "east"),
        blocked_channels=("movement", "vision"),
    )
    grid.place_object(corner.uuid, (2, 2))
    check("Multi-side wall blocks north movement", not grid.can_transition((2, 2), (2, 3)))
    check("Multi-side wall blocks east vision", not grid.can_see_transition((2, 2), (3, 2)))
    check("Unconfigured propagation remains open", grid.can_propagate_transition((2, 2), (3, 2)))

    half_a = DirectionalWall(source_entity_uuid=uuid4(), blocked_directions=("east",), blocked_channels=("movement",))
    half_b = DirectionalWall(source_entity_uuid=uuid4(), blocked_directions=("west",), blocked_channels=("movement",))
    grid.place_object(half_a.uuid, (1, 1))
    grid.place_object(half_b.uuid, (2, 1))
    check("Thick wall blocks from left endpoint", not grid.can_transition((1, 1), (2, 1)))
    check("Thick wall blocks from right endpoint", not grid.can_transition((2, 1), (1, 1)))
    check("Thick wall leaves unrelated side open", grid.can_transition((2, 1), (2, 2)))


def test_wall_excluded_from_senses_and_actions() -> None:
    print("\nTEST: structural wall does not spam senses or actions")
    make_grid()
    grid = get_map()
    hero = setup_actor("Hero", (1, 2))
    wall = DirectionalWall(source_entity_uuid=uuid4(), blocked_directions=("east",))
    grid.place_object(wall.uuid, (2, 2))

    Entity.update_all_entities_senses()
    actions = hero.get_available_actions()

    check("Wall is not listed in senses.objects", wall.uuid not in hero.senses.objects)
    object_target_uuids = {
        target.target_uuid
        for action in actions.object_actions
        for target in action.valid_targets
    }
    check("Wall is not listed in object target actions", wall.uuid not in object_target_uuids)
    use_item_uuids = {
        action.source_item_uuid
        for action in actions.all_actions
        if action.is_item_use
    }
    check("Wall does not surface environment use actions", wall.uuid not in use_item_uuids)


def test_directional_door_closed_open_cycle() -> None:
    print("\nTEST: directional door closed/open cycle")
    make_grid()
    grid = get_map()
    hero = setup_actor("Hero", (1, 2))
    target = create_skeleton(name="Target", position=(4, 2), faction="monsters")
    door = DirectionalDoor(source_entity_uuid=uuid4(), blocked_directions=("east",))
    grid.place_object(door.uuid, (2, 2))
    Entity.update_all_entities_senses()

    check("Door cell remains walkable while closed", grid.is_walkable(2, 2))
    check("Door has no scalar movement block", not door.blocks_walking())
    check("Door has no scalar vision block", not door.blocks_vision())
    check("Closed door blocks movement side", not grid.can_transition((2, 2), (3, 2)))
    check("Closed door blocks FOV side", (4, 2) not in hero.senses.visible)
    check("Closed door hides target", target.uuid not in hero.senses.entities)
    check("Closed door blocks light side", (3, 2) not in set(grid.compute_light_fov((2, 2), max_distance=3)))
    check("Closed door blocks propagation side", (3, 2) not in set(grid.compute_propagation_fov((2, 2), max_distance=3)))
    check("Door appears in senses.objects", door.uuid in hero.senses.objects)

    actions = hero.get_available_actions()
    open_actions = [action for action in actions.self_actions if action.source_item_uuid == door.uuid and "Open Door" in action.template_name]
    check("Closed door surfaces Open Door action", bool(open_actions))

    result = execute_use_action(hero, door.uuid, "Open Door")
    Entity.update_all_entities_senses()
    check("Open Door action succeeds", result is not None and not result.canceled)
    check("Door is open", door.is_open)
    check("Open door allows movement side", grid.can_transition((2, 2), (3, 2)))
    check("Open door allows FOV to target", target.uuid in hero.senses.entities)
    check("Open door allows light side", (3, 2) in set(grid.compute_light_fov((2, 2), max_distance=3)))
    check("Open door allows propagation side", (3, 2) in set(grid.compute_propagation_fov((2, 2), max_distance=3)))

    actions = hero.get_available_actions()
    close_actions = [action for action in actions.self_actions if action.source_item_uuid == door.uuid and "Close Door" in action.template_name]
    check("Open door surfaces Close Door action", bool(close_actions))


def test_door_preserves_unrelated_blockers_and_close_occupancy() -> None:
    print("\nTEST: directional door preserves unrelated blockers and validates close occupancy")
    make_grid()
    grid = get_map()
    hero = setup_actor("Hero", (1, 2))
    door = DirectionalDoor(source_entity_uuid=uuid4(), blocked_directions=("east",))
    grid.place_object(door.uuid, (2, 2))

    door.set_directional_blocking("movement", "west", True)
    door.open()
    check("Opening clears configured east movement blocker", grid.can_transition((2, 2), (3, 2)))
    check("Opening preserves unrelated west movement blocker", not grid.can_transition((2, 2), (1, 2)))

    Entity.update_entity_position(hero, (2, 2))
    close = CloseDirectionalDoorAction(source_entity_uuid=hero.uuid, source_item_uuid=door.uuid)
    result = close.apply()
    check("Close action cancels when entity stands on door tile", result is not None and result.canceled)
    check("Door remains open after blocked close", door.is_open)
    check("Door returns no close action while occupied", door.get_use_actions(hero.uuid) == [])


def test_door_object_event_and_sse_payload() -> None:
    print("\nTEST: directional door event and SSE payload")
    make_grid()
    grid = get_map()
    door = DirectionalDoor(source_entity_uuid=uuid4(), blocked_directions=("east",))
    grid.place_object(door.uuid, (2, 2))
    event_stream.ensure_attached()

    cursor = EventQueue.event_cursor()
    door.open()
    events = object_change_events_since(cursor)
    event = events[-1] if events else None
    dumped = event.model_dump(mode="json") if event else {}

    check("Door open emits one object changed declaration", len(events) == 1)
    check("Event uses existing SPATIAL_OBJECT_CHANGED type", event is not None and event.event_type == EventType.SPATIAL_OBJECT_CHANGED)
    check("Event carries door open state", event is not None and event.object_is_open is True)
    check("Event carries directional position", dumped.get("directional_position") == [2, 2])
    check("Event carries changed direction", dumped.get("directional_directions") == ["east"])
    check("Event carries all changed channels", set(dumped.get("directional_channels", [])) == {"movement", "vision", "light", "propagation"})
    check("Event carries movement block map", dumped.get("directional_blocks_movement", {}).get("east") is False)

    payloads = [
        payload for payload in event_stream.iter_game_events_since(cursor, None)
        if payload.event.event_type == EventType.SPATIAL_OBJECT_CHANGED
    ]
    check("Event stream builds object changed game_event payload", bool(payloads))
    if payloads:
        payload = payloads[-1]
        frame = format_sse("game_event", payload, make_stream_id(payload.event_cursor, payload.combat_log_cursor))
        data = json.loads("\n".join(line.removeprefix("data: ") for line in frame.splitlines() if line.startswith("data: ")))
        check("SSE keeps game_event envelope", "event: game_event" in frame)
        check("SSE serializes directional object position", data["event"]["directional_position"] == [2, 2])
        check("SSE keeps object event type", data["event"]["event_type"] == "spatial_object_changed")


def test_hidden_directional_wall_collision_memory() -> None:
    print("\nTEST: hidden directional wall collision memory")
    make_grid()
    grid = get_map()
    mover = setup_actor("Mover", (2, 2))
    wall = DirectionalWall(
        source_entity_uuid=uuid4(),
        name="Hidden Wall",
        blocked_directions=("east",),
        blocked_channels=("movement",),
        stealth_dc=99,
    )
    grid.place_object(wall.uuid, (2, 2))
    Entity.update_all_entities_senses()

    check("Hidden wall does not leak in subjective paths", (3, 2) in mover.senses.paths)
    check("Objective movement is blocked", not grid.can_transition((2, 2), (3, 2), mover.uuid))
    check("Subjective movement is open before collision", grid.can_transition((2, 2), (3, 2), mover.uuid, subjective=True))

    result = Move(source_entity_uuid=mover.uuid, end_position=(3, 2), use_movement_cost=False).apply()
    check("Movement result exists", result is not None)
    check("Mover stays before hidden wall", mover.position == (2, 2))
    check("Cell collision memory remains empty", (3, 2) not in mover.senses.collision_blocked)
    check("Directional collision memory records source side", ((2, 2), "east") in mover.senses.directional_collision_blocked)
    check(
        "Remembered blocker does not poison destination from another side",
        grid.can_transition(
            (3, 3), (3, 2), mover.uuid, subjective=True,
            directional_collision_blocked=mover.senses.directional_collision_blocked,
        ),
    )


def test_forced_movement_jump_threat_and_ranged_disadvantage() -> None:
    print("\nTEST: forced movement, jump, threat, OA, and ranged disadvantage")
    make_grid()
    grid = get_map()

    target = create_skeleton(name="Push Target", position=(2, 2), faction="monsters")
    wall = DirectionalWall(source_entity_uuid=uuid4(), blocked_directions=("east",), blocked_channels=("movement", "propagation"))
    grid.place_object(wall.uuid, (2, 2))
    final_pos, distance, blocked, _blocker = Shove.calculate_final_position((2, 2), (1, 2), 10, target.uuid)
    check("Forced movement stops at directional wall", final_pos == (2, 2) and distance == 0 and blocked)

    jumper = setup_actor("Jumper", (2, 2), faction="heroes")
    Entity.update_all_entities_senses()
    jump = Jump(source_entity_uuid=jumper.uuid, template=True)
    check("Jump target past wall is visible", (4, 2) in jumper.senses.visible)
    check("Jump excludes propagation-blocked landing", (4, 2) not in jump.get_valid_positions())

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 7, 5)
    attacker = create_skeleton(name="Attacker", position=(2, 2), faction="monsters")
    mover = setup_actor("Mover", (3, 2), faction="heroes")
    Entity.update_all_entities_senses()
    check("Baseline adjacent mover is threatened", mover.is_threatened())

    screen = DirectionalWall(source_entity_uuid=uuid4(), blocked_directions=("east",), blocked_channels=("propagation",))
    grid.place_object(screen.uuid, (2, 2))
    Entity.update_all_entities_senses()
    check("Propagation wall removes threat", not mover.is_threatened())
    check("Threatened positions exclude blocked neighbor", (3, 2) not in attacker.senses.get_threathened_positions())

    cursor = EventQueue.event_cursor()
    step = StepMovementEvent(
        source_entity_uuid=mover.uuid,
        source_entity_name=mover.name,
        from_position=(3, 2),
        to_position=(4, 2),
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    opportunity_attack_processor(step, attacker.uuid)
    attack_events = [event for _, event in EventQueue.iter_events_since(cursor) if event.event_type == EventType.ATTACK]
    check("OA does not fire through propagation wall", len(attack_events) == 0)

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 7, 5)
    archer = create_skeleton(name="Archer", position=(3, 3), faction="heroes")
    adjacent_enemy = create_goblin(name="Adjacent Enemy", position=(2, 3), faction="monsters")
    far_target = create_goblin(name="Far Target", position=(5, 3), faction="monsters")
    bow = create_shortbow(archer.uuid)
    archer.equipment.equip(bow, WeaponSlot.RANGED_MAIN)
    Entity.update_all_entities_senses()
    check("Baseline archer is threatened", archer.is_threatened())

    attack = Attack(source_entity_uuid=archer.uuid, target_entity_uuid=far_target.uuid, weapon_slot=WeaponSlot.RANGED_MAIN)
    declaration = attack._create_declaration_event(use_register=False)
    validated = attack._validate(declaration) if declaration is not None else None
    check("Baseline ranged attack sees threatened state", validated is not None and validated.is_threatened)

    blocker = DirectionalWall(source_entity_uuid=uuid4(), blocked_directions=("east",), blocked_channels=("propagation",))
    grid.place_object(blocker.uuid, adjacent_enemy.position)
    Entity.update_all_entities_senses()
    attack = Attack(source_entity_uuid=archer.uuid, target_entity_uuid=far_target.uuid, weapon_slot=WeaponSlot.RANGED_MAIN)
    declaration = attack._create_declaration_event(use_register=False)
    validated = attack._validate(declaration) if declaration is not None else None
    check("Directional propagation wall removes ranged threatened state", validated is not None and not validated.is_threatened)


def main() -> None:
    print("=" * 76)
    print("Directional Environment Item Tests")
    print("=" * 76)
    test_directional_wall_blocks_only_configured_sides()
    test_directional_wall_multi_side_and_thick_wall()
    test_wall_excluded_from_senses_and_actions()
    test_directional_door_closed_open_cycle()
    test_door_preserves_unrelated_blockers_and_close_occupancy()
    test_door_object_event_and_sse_payload()
    test_hidden_directional_wall_collision_memory()
    test_forced_movement_jump_threat_and_ranged_disadvantage()
    print(f"\nResults: {passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
