"""Selected furniture keeps one body and owns only its actual debris terrain."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.actions import Move
from dnd.actions_functional import setup_standard_actions
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.world_prop_builders import DEBRIS_CONTENT_REF, WORLD_PROP_PROFILES, build_world_prop
from dnd.core.base_block import BaseBlock, MovementMode
from dnd.core.creature_types import DamageType
from dnd.core.events import (
    Event, EventHandler, EventPhase, EventQueue, EventType, ItemDestructionEvent,
    SpatialChangeEvent, SpatialEffectChangeEvent, Trigger,
)
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.area_conditions import AreaCondition
from dnd.spatial.environmental_conditions import OilSurface
from dnd.types.spatial_effects import SpatialEffectAnchorKind, SpatialEffectLayer, SpatialEffectOccupancyPolicy
from dnd.types.world import CardinalDirection


@pytest.fixture
def game() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(8, 8))
    instance = Game()
    yield instance
    instance.close()
    reset_engine_runtime()


def walking_cost(position: tuple[int, int]) -> int:
    tile = get_map().get_tile(*position)
    assert tile is not None
    return tile.get_movement_cost(MovementMode.WALKING)


@pytest.mark.parametrize("item_id", tuple(WORLD_PROP_PROFILES))
def test_registered_furniture_breaks_once_and_preserves_its_physical_identity(game: Game, item_id: str):
    prop = build_authored_item(item_id, uuid4())
    placement = prop.place_on_grid((3, 3))
    profile = WORLD_PROP_PROFILES[item_id]
    tiles = {point: get_map().get_tile(*point) for point in placement.positions}
    hp = profile.hit_points
    assert prop.get_hp() == hp and len(placement.positions) == len(profile.footprint_offsets)
    assert placement.top_height_steps - placement.base_height_steps == profile.vertical_extent_steps
    assert all(get_map().get_center_objects_at(point) == {prop.uuid} for point in placement.positions)
    assert all(not get_map().is_walkable_for(*point) for point in placement.positions)
    cursor = EventQueue.event_cursor()
    prop.receive_damage(hp // 2, DamageType.BLUDGEONING, prop.uuid)
    assert prop.get_hp() == hp - hp // 2 and prop.integrity is ItemIntegrity.INTACT
    assert not get_map().get_spatial_conditions()
    prop.receive_damage(hp - hp // 2, DamageType.BLUDGEONING, prop.uuid)
    assert BaseBlock.get(prop.uuid) is prop and prop.integrity is ItemIntegrity.DESTROYED
    assert prop.get_hp() == 0 and prop.name == profile.destroyed_name
    assert not prop.blocks_walking() and not prop.blocks_optics_at_center() and not prop.blocks_propagation()
    after = get_map().get_object_placement(prop.uuid)
    assert after is not None and after.positions == placement.positions and not after.occupies_bands
    assert after.top_height_steps - after.base_height_steps == 1
    assert all(get_map().is_walkable_for(*point) for point in placement.positions)
    assert all(get_map().get_tile(*point) is tile for point, tile in tiles.items())
    assert all(walking_cost(point) == (2 if profile.difficult_debris else 1) for point in placement.positions)
    completed = [event for _, event in EventQueue.iter_events_since(cursor) if event.phase is EventPhase.COMPLETION]
    destruction, = [event for event in completed if isinstance(event, ItemDestructionEvent)]
    by_lineage = {event.lineage_uuid: event for event in completed}
    for consequence in (event for event in completed if isinstance(event, SpatialEffectChangeEvent)):
        parent = consequence.parent_lineage
        while parent is not None and parent in by_lineage and parent != destruction.lineage_uuid:
            parent = by_lineage[parent].parent_lineage
        assert parent == destruction.lineage_uuid
    prop.destroy()
    assert sum(isinstance(event, ItemDestructionEvent) and event.phase is EventPhase.COMPLETION
               for _, event in EventQueue.iter_events_since(cursor)) == 1


@pytest.mark.parametrize("item_id,occludes", (
    ("environment.furniture.wardrobe", True),
    ("environment.furniture.bookshelf", True),
    ("environment.furniture.winged_statue", False),
    ("environment.furniture.work_stool", False),
))
def test_authored_prop_channels_control_sight_and_area_reach_until_broken(game: Game, item_id: str, occludes: bool):
    prop = build_authored_item(item_id, uuid4())
    prop.place_on_grid((3, 3))
    grid = get_map()
    # Real cached queries must change when destruction clears the obstruction.
    assert ((4, 3) in grid.compute_fov((2, 3), 5)) is not occludes
    assert ((4, 3) in grid.compute_propagation_fov((2, 3), 5)) is not occludes
    assert not grid.is_walkable_for(3, 3)
    prop.receive_damage(prop.get_hp(), DamageType.BLUDGEONING, prop.uuid)
    assert (4, 3) in grid.compute_fov((2, 3), 5)
    assert (4, 3) in grid.compute_propagation_fov((2, 3), 5)
    assert grid.is_walkable_for(3, 3)


def test_initial_wreck_owns_no_ground_effect_until_its_placement_is_committed(game: Game):
    cursor = EventQueue.event_cursor()
    bed = build_world_prop("environment.furniture.bed", integrity=ItemIntegrity.DESTROYED)
    assert bed.get_hp() == 0 and not get_map().get_spatial_conditions()
    bed.place_on_grid((3, 3))
    assert walking_cost((3, 3)) == walking_cost((4, 3)) == 2
    assert len(get_map().get_spatial_conditions()) == 1
    assert not any(isinstance(event, ItemDestructionEvent) for _, event in EventQueue.iter_events_since(cursor))


def test_wreck_disposal_removes_only_its_owned_terrain_and_preserves_actual_movement(game: Game):
    cause = Event(source_entity_uuid=uuid4(), name="Existing oil", event_type=EventType.BASE_ACTION)
    oil = OilSurface(source_entity_uuid=uuid4(), position=(4, 3), affected_positions={(4, 3)})
    oil.activate(parent_event=cause)
    cause.phase_to(EventPhase.COMPLETION)
    bed = build_world_prop("environment.furniture.bed")
    bed.place_on_grid((3, 3))
    bed.receive_damage(18, DamageType.BLUDGEONING, bed.uuid)
    assert (walking_cost((3, 3)), walking_cost((4, 3))) == (2, 3)
    actor = Entity.create(uuid4(), "Walker", config=EntityConfig(position=(3, 2)))
    setup_standard_actions(actor)
    actor.compose_entity()
    game.deploy_entity(actor, (3, 2))
    actor.update_entity_senses()
    budget = actor.action_economy.movement.normalized_score
    move = Move(source_entity_uuid=actor.uuid, path=[(3, 2), (3, 3)], end_position=(3, 3)).apply()
    assert move is not None
    assert not move.canceled, move.status_message
    assert actor.position == (3, 3)
    assert budget - actor.action_economy.movement.normalized_score == 10
    bed.retire()
    assert (walking_cost((3, 3)), walking_cost((4, 3))) == (1, 2)
    assert get_map().get_spatial_conditions() == [oil]
    assert oil.is_active_spatial_condition()


def test_rotated_and_relocated_wreck_updates_one_region_and_removal_releases_every_cell(game: Game):
    bed = build_world_prop("environment.furniture.bed", integrity=ItemIntegrity.DESTROYED)
    bed.place_on_grid((3, 3))
    region, = get_map().get_spatial_conditions()
    assert isinstance(region, AreaCondition)
    rotated = get_map().orient_object(bed.uuid, CardinalDirection.NORTH)
    assert set(rotated.positions) == {(3, 3), (3, 4)}
    assert get_map().get_spatial_conditions() == [region]
    assert region.affected_positions == set(rotated.positions)
    assert walking_cost((4, 3)) == 1 and walking_cost((3, 4)) == 2
    moved = get_map().move_object(bed.uuid, (5, 3), orientation=CardinalDirection.NORTH)
    assert region.affected_positions == set(moved.positions) == {(5, 3), (5, 4)}
    assert walking_cost((3, 3)) == walking_cost((3, 4)) == 1
    assert walking_cost((5, 3)) == walking_cost((5, 4)) == 2
    assert get_map().remove_object(bed.uuid)
    assert not get_map().get_spatial_conditions()
    assert walking_cost((5, 3)) == walking_cost((5, 4)) == 1
    bed.place_on_grid((2, 2))
    assert walking_cost((2, 2)) == walking_cost((3, 2)) == 2


def test_rejected_wreck_placement_and_relocation_cannot_create_or_move_debris(game: Game):
    bed = build_world_prop("environment.furniture.bed", integrity=ItemIntegrity.DESTROYED)

    def reject(event: Event, _source: UUID) -> Event | None:
        if isinstance(event, SpatialChangeEvent) and event.object_uuid == bed.uuid:
            return event.cancel(status_message="The attempted placement is prevented")
        return None

    handler = EventHandler(source_entity_uuid=bed.uuid, name="Prevent relocation",
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_PLACED,
                                    event_phase=EventPhase.EFFECT)], event_processor=reject)
    EventQueue.add_event_handler(handler)
    with pytest.raises(ValueError, match="placement was canceled"):
        bed.place_on_grid((3, 3))
    assert not get_map().get_spatial_conditions() and walking_cost((3, 3)) == 1
    EventQueue.remove_event_handler(handler)
    bed.place_on_grid((3, 3))
    region, = get_map().get_spatial_conditions()
    assert isinstance(region, AreaCondition)
    EventQueue.add_event_handler(handler)
    with pytest.raises(ValueError, match="arrival was canceled"):
        get_map().move_object(bed.uuid, (5, 3))
    assert get_map().get_spatial_conditions() == [region]
    assert region.affected_positions == {(3, 3), (4, 3)}
    assert walking_cost((3, 3)) == walking_cost((4, 3)) == 2
    assert walking_cost((5, 3)) == walking_cost((6, 3)) == 1


@pytest.mark.parametrize("requires_intact", (True, False))
def test_world_object_attachment_honors_its_authored_integrity_lifetime(game: Game, requires_intact: bool):
    table = build_world_prop("environment.furniture.table")
    table.place_on_grid((3, 3))
    cause = Event(source_entity_uuid=table.uuid, name="Attach area", event_type=EventType.BASE_ACTION)
    area = AreaCondition(source_entity_uuid=table.uuid, name="Attached terrain",
        content_ref=DEBRIS_CONTENT_REF, position=(3, 3), affected_positions={(3, 3)},
        layer=SpatialEffectLayer.FIELD, occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        anchor_kind=SpatialEffectAnchorKind.WORLD_OBJECT, anchor_uuid=table.uuid,
        requires_intact_item=requires_intact, adds_difficult_terrain=True)
    area.activate(parent_event=cause)
    cause.phase_to(EventPhase.COMPLETION)
    assert walking_cost((3, 3)) == 2
    table.receive_damage(18, DamageType.BLUDGEONING, table.uuid)
    assert area.is_active_spatial_condition() is (not requires_intact)
    assert walking_cost((3, 3)) == (1 if requires_intact else 2)
    table.retire()
    assert not area.is_active_spatial_condition() and walking_cost((3, 3)) == 1
