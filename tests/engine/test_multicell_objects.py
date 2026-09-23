"""One physical object has several supports, without duplicating its identity."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.actions import AttackObject, PickUp
from dnd.actions_functional import execute_use_action, get_available_actions, setup_standard_actions
from dnd.blocks.base_item import BaseItem, WorldItem
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_wall, build_storage_chest
from dnd.core.base_actions import ActionEvent
from dnd.core.base_block import BaseBlock, LightLevel
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    Event, EventHandler, EventPhase, EventQueue, EventType, ItemDestructionEvent,
    SpatialChangeEvent, SpatialHandler, Trigger,
)
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemDestructionProfile, ItemIntegrity
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldObjectPlacement, WorldPlacementKind, WorldPlacementSpec
from dnd.world_facts import WorldFacts, apply_world_fact, world_event_positions


@pytest.fixture
def arena() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(9, 9))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


def actor(game: Game, position: tuple[int, int]) -> Entity:
    result = Entity.create(uuid4(), "Furniture tester", config=EntityConfig(position=position))
    setup_standard_actions(result)
    result.install_initial_items(((build_authored_item("weapon.longsword", result.uuid), WeaponSlot.MELEE_MAIN),))
    result.compose_entity()
    game.deploy_entity(result, position)
    return result


def furniture(*, offsets: tuple[tuple[int, int], ...] = ((0, 0), (1, 0)),
              pickable: bool = False) -> WorldItem:
    result = WorldItem(
        item_id="test.long_furniture", name="Long furniture", source_entity_uuid=uuid4(),
        is_pickable=pickable, is_targetable=True, blocks_movement=True,
        blocks_optics_field=True, blocks_propagation_field=True,
        world_placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.CENTER,
            occupies_bands=True, vertical_extent_steps=1, footprint_offsets=offsets),
        destruction_profile=ItemDestructionProfile(name="Small wreck",
            placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.CENTER,
                occupies_bands=False, vertical_extent_steps=1)),
    )
    result.health = result.create_item_health(result.uuid, 8)
    return result


def placement(item: BaseItem) -> WorldObjectPlacement:
    result = get_map().get_object_placement(item.uuid)
    assert result is not None
    return result


def object_choices(observer: Entity, item: BaseItem) -> list:
    return [target for action in get_available_actions(observer).object_actions
            for target in action.valid_targets if target.target_uuid == item.uuid]


def test_one_identity_reindexes_rotation_move_and_removal(arena: Game) -> None:
    grid = get_map()
    item = furniture()
    item.place_on_grid((2, 3))
    original = placement(item)
    assert original.positions == ((2, 3), (3, 3))
    assert all(grid.get_center_objects_at(point) == {item.uuid} for point in original.positions)
    assert all(not grid.is_walkable_for(*point) for point in original.positions)
    assert set(original.positions) <= grid.get_barrier_positions()
    assert len(grid.iter_object_placements()) == 1
    with pytest.raises(ValueError, match="world objects"):
        grid.validate_tile_detachment((3, 3))
    with pytest.raises(ValueError, match="center objects"):
        grid.set_tile_elevation((3, 3), height=1,
            surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)

    seen: list[Event] = []
    def record(event: Event, _source: UUID | None) -> Event:
        seen.append(event)
        return event
    handler = SpatialHandler(name="Watch both footprint ends", source_entity_uuid=uuid4(),
        positions={(3, 3), (2, 4)}, event_type=EventType.SPATIAL_OBJECT_CHANGED,
        event_phase=EventPhase.EFFECT, event_processor=record)
    EventQueue.add_spatial_handler(handler)
    rotated = grid.orient_object(item.uuid, CardinalDirection.NORTH)
    assert rotated.positions == ((2, 3), (2, 4))
    assert grid.get_center_objects_at((3, 3)) == set()
    assert grid.get_center_objects_at((2, 4)) == {item.uuid}
    assert len(seen) == 1
    fact = next(event for _, event in EventQueue.iter_events_since(0)
                if isinstance(event, SpatialChangeEvent) and event.placement == rotated
                and event.phase is EventPhase.COMPLETION)
    assert fact.get_affected_positions() == {(2, 3), (3, 3), (2, 4)}
    cold = WorldFacts()
    assert apply_world_fact(cold, fact)
    assert cold.objects[item.uuid].placement == rotated
    assert {(2, 3), (3, 3), (2, 4)} <= world_event_positions(cold, fact)

    moved = grid.move_object(item.uuid, (5, 3), orientation=CardinalDirection.SOUTH)
    assert moved.positions == ((5, 3), (5, 2))
    assert all(not grid.get_center_objects_at(point) for point in rotated.positions)
    assert grid.remove_object(item.uuid)
    assert all(not grid.get_center_objects_at(point) for point in moved.positions)
    assert grid.validate_tile_detachment((5, 2)).uuid == moved.covered_supports[1].tile_uuid


@pytest.mark.parametrize("obstacle", ["missing", "uneven", "occupied"])
def test_invalid_second_support_never_commits_partial_placement(arena: Game, obstacle: str) -> None:
    grid = get_map()
    if obstacle == "missing":
        grid.remove_tile(3, 3)
    elif obstacle == "uneven":
        grid.set_tile_elevation((3, 3), height=1,
            surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    else:
        other = furniture(offsets=((0, 0),))
        other.place_on_grid((3, 3))
    item = furniture()
    with pytest.raises(ValueError):
        item.place_on_grid((2, 3))
    assert grid.get_object_placement(item.uuid) is None
    assert item.uuid not in grid.get_center_objects_at((2, 3))
    assert item.uuid not in grid.get_center_objects_at((3, 3))


def test_rejected_rotation_preserves_all_previous_supports(arena: Game) -> None:
    grid = get_map()
    item = furniture()
    item.place_on_grid((2, 3))
    previous = placement(item)
    blocker = furniture(offsets=((0, 0),))
    blocker.place_on_grid((2, 4))
    with pytest.raises(ValueError, match="collides"):
        grid.orient_object(item.uuid, CardinalDirection.NORTH)
    assert placement(item) == previous
    assert all(item.uuid in grid.get_center_objects_at(point) for point in previous.positions)
    assert grid.get_center_objects_at((2, 4)) == {blocker.uuid}


@pytest.mark.parametrize("multi_cell", [False, True])
def test_rectangle_replacement_rejects_supported_objects_before_changing_any_tile(
    arena: Game, multi_cell: bool,
) -> None:
    grid = get_map()
    item = furniture(offsets=((0, 0), (1, 0)) if multi_cell else ((0, 0),))
    item.place_on_grid((3, 3) if multi_cell else (4, 3))
    prior_placement = placement(item)
    # The first cell is free; the second is the nonanchor support in the
    # multi-cell case. Rejection must preserve both cells, not only the occupied one.
    previous = {position: grid.get_tile(*position) for position in ((4, 2), (4, 3))}
    cursor = EventQueue.event_cursor()
    with pytest.raises(ValueError, match="world objects"):
        grid.create_rectangle(4, 2, 1, 2, name="Replacement floor", walking_cost=2)
    assert placement(item) == prior_placement
    assert EventQueue.event_cursor() == cursor
    for position, tile in previous.items():
        assert tile is not None
        assert grid.get_tile(*position) is tile
        assert BaseBlock.get(tile.uuid) is tile
    assert grid.get_center_objects_at((4, 3)) == {item.uuid}

    item.retire()
    grid.create_rectangle(4, 2, 1, 2, name="Replacement floor", walking_cost=2)
    for position, old_tile in previous.items():
        tile = grid.get_tile(*position)
        assert old_tile is not None and tile is not None and tile.uuid != old_tile.uuid
        assert tile.name == "Replacement floor"
        assert BaseBlock.get(old_tile.uuid) is None


def test_far_end_attack_and_same_identity_destruction_update_only_real_supports(arena: Game) -> None:
    attacker = actor(arena, (4, 3))
    item = furniture()
    item.place_on_grid((2, 3))
    tile_ids = tuple(support.tile_uuid for support in placement(item).covered_supports)
    attacker.update_entity_senses(max_distance=1)
    assert (2, 3) not in attacker.senses.visible
    assert attacker.senses.objects[item.uuid].position == (3, 3)
    assert object_choices(attacker, item)
    assert all(choice.position == (3, 3) for choice in object_choices(attacker, item))
    assert get_map().manual_object_contact(attacker.uuid, item.uuid) == (3, 3)
    cursor = EventQueue.event_cursor()
    for remaining in (4, 0):
        attacker.action_economy.reset_all_costs()
        with fixed_dice_faces(4):
            result = AttackObject(source_entity_uuid=attacker.uuid, target_entity_uuid=item.uuid).apply()
        assert result is not None and not result.canceled
        assert item.get_hp() == remaining
    assert BaseBlock.get(item.uuid) is item
    assert item.integrity is ItemIntegrity.DESTROYED
    assert placement(item).positions == ((2, 3),)
    assert get_map().is_walkable_for(3, 3, attacker.uuid)
    assert item.uuid not in attacker.senses.objects
    # Paths are deliberately refreshed on action discovery, not every sensory fact.
    get_available_actions(attacker)
    assert (3, 3) in attacker.senses.paths
    assert tuple(get_map().get_tile(x, 3).uuid for x in (2, 3)) == tile_ids
    broken = [event for _, event in EventQueue.iter_events_since(cursor)
              if isinstance(event, ItemDestructionEvent) and event.phase is EventPhase.COMPLETION]
    assert len(broken) == 1 and broken[0].get_affected_positions() == {(2, 3), (3, 3)}


def test_far_end_pickup_releases_whole_footprint(arena: Game) -> None:
    picker = actor(arena, (4, 3))
    item = furniture(pickable=True)
    item.place_on_grid((2, 3))
    result = PickUp(source_entity_uuid=picker.uuid, target_entity_uuid=item.uuid).apply()
    assert result is not None and not result.canceled
    assert item.uuid in picker.inventory.items
    assert get_map().get_object_placement(item.uuid) is None
    assert all(item.uuid not in get_map().get_center_objects_at(point) for point in ((2, 3), (3, 3)))


@pytest.mark.parametrize("diagonal", [False, True])
def test_manual_reach_cannot_pass_an_unrelated_wall_or_blocked_corner(arena: Game, diagonal: bool) -> None:
    attacker = actor(arena, (3, 3))
    target_pos = (4, 4) if diagonal else (4, 3)
    item = furniture(offsets=((0, 0),))
    item.place_on_grid(target_pos)
    wall = build_directional_wall()
    wall.place_on_grid((3, 3), boundary_direction=CardinalDirection.EAST)
    if diagonal:
        second = build_directional_wall()
        second.place_on_grid((3, 3), boundary_direction=CardinalDirection.NORTH)
    assert get_map().manual_object_contact(attacker.uuid, item.uuid) is None
    result = AttackObject(source_entity_uuid=attacker.uuid, target_entity_uuid=item.uuid).apply()
    assert result is not None and result.canceled
    assert item.get_hp() == 8
    wall.retire()
    assert get_map().manual_object_contact(attacker.uuid, item.uuid) == target_pos


def test_stale_attack_rechecks_after_execution_interception(arena: Game) -> None:
    attacker = actor(arena, (4, 3))
    item = furniture()
    item.place_on_grid((2, 3))
    def move_target(event: Event, _source: UUID | None) -> Event:
        if isinstance(event, ActionEvent) and event.target_entity_uuid == item.uuid:
            get_map().move_object(item.uuid, (6, 6), parent_event=event.uuid)
        return event
    handler = EventHandler(name="Move away during execution", source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(event_type=EventType.BASE_ACTION, event_phase=EventPhase.EXECUTION)],
        event_processor=move_target)
    EventQueue.add_event_handler(handler)
    result = AttackObject(source_entity_uuid=attacker.uuid, target_entity_uuid=item.uuid).apply()
    assert result is not None and result.canceled
    assert placement(item).position == (6, 6) and item.get_hp() == 8


def test_manual_use_discovery_and_execution_reject_wall_and_stale_distance(arena: Game) -> None:
    operator = actor(arena, (3, 3))
    chest = build_storage_chest("Chest", include_loot_all_action=False)
    chest.place_on_grid((4, 3))
    operator.update_entity_senses()
    assert any(row.source_item_uuid == chest.uuid for row in get_available_actions(operator).all_actions)
    wall = build_directional_wall()
    wall.place_on_grid((3, 3), boundary_direction=CardinalDirection.EAST)
    assert not any(row.source_item_uuid == chest.uuid for row in get_available_actions(operator).all_actions)
    with pytest.raises(ValueError, match="out of reach"):
        execute_use_action(operator, chest.uuid, "Open Chest")
    wall.retire()
    get_map().move_object(chest.uuid, (7, 3))
    with pytest.raises(ValueError, match="out of reach"):
        execute_use_action(operator, chest.uuid, "Open Chest")
    assert not chest.is_open


def test_nonanchor_geometry_change_updates_light_outside_anchor_range(arena: Game) -> None:
    grid = get_map()
    item = furniture(offsets=((0, 0), (1, 0), (2, 0)))
    item.place_on_grid((1, 3))
    shadow = (2, 3)
    grid.set_tile_base_light(shadow, LightLevel.DARKNESS)
    grid.add_light_source((4, 3), bright_radius_feet=10, dim_radius_feet=0)
    assert grid.get_tile(*shadow).resolved_light_level is LightLevel.DARKNESS
    grid.orient_object(item.uuid, CardinalDirection.NORTH)
    assert grid.get_tile(*shadow).resolved_light_level is LightLevel.BRIGHT_LIGHT


def test_old_single_cell_record_normalizes_from_recorded_anchor_only(arena: Game) -> None:
    item = furniture(offsets=((0, 0),))
    item.place_on_grid((2, 3))
    current = placement(item)
    old = current.model_dump()
    old.pop("covered_supports")
    recovered = WorldObjectPlacement.model_validate(old)
    assert recovered == current
    assert WorldObjectPlacement.model_validate_json(current.model_dump_json()) == current
    with pytest.raises(ValidationError):
        WorldPlacementSpec(kind=WorldPlacementKind.BOUNDARY, occupies_bands=True,
            vertical_extent_steps=1, footprint_offsets=((0, 0), (1, 0)))
