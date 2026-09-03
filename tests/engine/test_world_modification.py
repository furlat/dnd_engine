"""Public structural-authoring event and materialization contracts."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.blocks.base_item import BaseItem
from dnd.conditions import Hidden
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_object import BaseObject
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    SpatialChangeEvent,
    SensoryUpdateEvent,
    Trigger,
    TraversalConnectorChangeEvent,
    WorldConnectorState,
    WorldInitializedEvent,
    WorldModifiedEvent,
    WorldObjectState,
    WorldTileState,
)
from dnd.core.creature_types import DamageType
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.core.traversal_connectors import (
    ConnectorProvocationPolicy,
    TraversalConnectorDefinition,
    TraversalConnectorKind,
)
from dnd.core.values import BaseValue, ModifiableValue
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.core.world_edges import SlopeAxis
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.items.torches import WallTorch
from dnd.content.items.environment_item_builders import build_oil_barrel
from dnd.monsters.bestiary import create_skeleton
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.area_conditions import SpatialCondition
from dnd.types.materials import Material, TileSurface
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectBlockingPolicy,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
)
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from dnd.types.world import LightLevel
from tests.engine.support import create_test_entity
from dnd.world_authoring import (
    move_world_item,
    orient_world_item,
    place_world_item,
    project_world_connector,
    project_world_object,
    project_world_tile,
    register_world_connector,
    remove_world_connector,
    remove_world_tile,
    remove_world_item,
    replace_world_connector,
    set_world_tile,
    set_world_tile_base_light,
    set_world_tile_elevation,
    set_world_connector_enabled,
)


class DestructionWitnessItem(BaseItem):
    """Test item whose destruction behavior must not run on unplacement."""

    destruction_count: int = 0
    removal_callback_count: int = 0

    def _on_destroy(self, parent_event: Event | None) -> None:
        self.destruction_count += 1

    def on_grid_object_removed(
        self,
        position: tuple[int, int],
        clear_location: bool = True,
    ) -> None:
        self.removal_callback_count += 1
        super().on_grid_object_removed(position, clear_location)


def _events_since(cursor: int) -> tuple[Event, ...]:
    return tuple(event for _, event in EventQueue.iter_events_since(cursor))


def _cold_world_maps(
    initialized: WorldInitializedEvent,
) -> tuple[
    dict[tuple[int, int], WorldTileState],
    dict[UUID, WorldObjectState],
    dict[UUID, WorldConnectorState],
]:
    """Build the future renderer's three structural maps from cold values."""
    return (
        {
            state.position: state.model_copy(deep=True)
            for state in initialized.tiles
        },
        {
            state.item.item_uuid: state.model_copy(deep=True)
            for state in initialized.objects
        },
        {
            state.connector_uuid: state.model_copy(deep=True)
            for state in initialized.connectors
        },
    )


def _apply_cold_world_root(
    tiles: dict[tuple[int, int], WorldTileState],
    objects: dict[UUID, WorldObjectState],
    connectors: dict[UUID, WorldConnectorState],
    root: WorldModifiedEvent,
) -> None:
    """Fold one validated root without consulting any live engine owner."""
    after = root.after.model_copy(deep=True) if root.after is not None else None
    if root.tile_position is not None:
        if after is None:
            tiles.pop(root.tile_position, None)
        else:
            tiles[root.tile_position] = after
        return
    if root.object_uuid is not None:
        if after is None:
            objects.pop(root.object_uuid, None)
        else:
            objects[root.object_uuid] = after
        return
    assert root.connector_uuid is not None
    if after is None:
        connectors.pop(root.connector_uuid, None)
    else:
        connectors[root.connector_uuid] = after


def _copy_closed_event_interval(
    generation: UUID,
    start_cursor: int,
    end_cursor: int,
) -> tuple[Event, ...]:
    """Detach one bounded in-process presentation interval before yielding."""
    if EventQueue.generation_id() != generation:
        raise ValueError("event generation changed before interval copy")
    current_cursor = EventQueue.event_cursor()
    if not 0 <= start_cursor <= end_cursor <= current_cursor:
        raise ValueError("invalid closed event interval")
    copied = tuple(
        event.model_copy(deep=True)
        for index, event in EventQueue.iter_events_since(start_cursor)
        if index < end_cursor
    )
    if EventQueue.generation_id() != generation:
        raise ValueError("event generation changed during interval copy")
    return copied


def _tile_graph_uuids(tile) -> tuple[set, set]:
    """Return the exact BaseValue/BaseObject identities locally owned by a Tile."""
    values = set()
    modifiers = set()
    for value in (
        tile.walking_cost,
        tile.flying_cost,
        tile.swimming_cost,
        tile.burrowing_cost,
    ):
        values.add(value.uuid)
        for channel in (
            value.self_static,
            value.to_target_static,
            value.self_contextual,
            value.to_target_contextual,
        ):
            values.add(channel.uuid)
            modifiers.update(channel.get_all_modifier_uuids())
    return values, modifiers


def _assert_tile_replacement_rejected(
    message: str,
    *,
    position: tuple[int, int] = (0, 0),
) -> None:
    """Assert one live reference rejects before any world root is emitted."""
    grid = get_map()
    tile = grid.get_tile(*position)
    assert tile is not None
    cursor = EventQueue.event_cursor()
    with pytest.raises(ValueError, match=message):
        set_world_tile(
            position,
            author_uuid=uuid4(),
            name="Rejected replacement",
        )
    assert grid.get_tile(*position) is tile
    assert EventQueue.event_cursor() == cursor


def _tile_state(
    *,
    tile_uuid=None,
    position: tuple[int, int] = (2, 3),
    name: str = "Stone Floor",
) -> WorldTileState:
    return WorldTileState(
        tile_uuid=tile_uuid or uuid4(),
        position=position,
        surface=TileSurface(base_material=Material.STONE),
        name=name,
        blocks_optics=False,
        blocks_propagation=False,
        walking_cost=1,
        flying_cost=1,
        swimming_cost=0,
        burrowing_cost=0,
        elevation_steps=0,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
        default_light=LightLevel.BRIGHT_LIGHT,
        resolved_light=LightLevel.BRIGHT_LIGHT,
    )


def test_world_modified_tile_value_round_trips_as_the_same_union_member() -> None:
    """A detached client can recover the exact concrete cold state member."""
    after = _tile_state()
    completed = WorldModifiedEvent(
        source_entity_uuid=uuid4(),
        tile_position=after.position,
        before=None,
        after=after,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )

    restored = WorldModifiedEvent.model_validate_json(
        completed.model_dump_json(),
    )

    assert restored == completed
    assert type(restored.after) is WorldTileState


def test_world_modified_rejects_ambiguous_targets_and_noop_completion() -> None:
    """One completed root addresses exactly one real structural transition."""
    state = _tile_state()
    with pytest.raises(ValidationError, match="exactly one target"):
        WorldModifiedEvent(
            source_entity_uuid=uuid4(),
            tile_position=state.position,
            object_uuid=uuid4(),
            after=state,
            phase=EventPhase.COMPLETION,
            use_register=False,
        )
    with pytest.raises(ValidationError, match="must change state"):
        WorldModifiedEvent(
            source_entity_uuid=uuid4(),
            tile_position=state.position,
            before=state,
            after=state,
            phase=EventPhase.COMPLETION,
            use_register=False,
        )


def test_world_modified_keeps_after_state_out_of_precompletion_phases() -> None:
    """A successful materialized after-value exists only after owner commit."""
    state = _tile_state()
    with pytest.raises(ValidationError, match="completion-only"):
        WorldModifiedEvent(
            source_entity_uuid=uuid4(),
            tile_position=state.position,
            after=state,
            phase=EventPhase.EFFECT,
            use_register=False,
        )


def test_world_modified_phase_transitions_revalidate_copied_values() -> None:
    """The real Event.phase_to path cannot bypass the cold-value contract."""
    state = _tile_state()
    declaration = WorldModifiedEvent(
        source_entity_uuid=uuid4(),
        tile_position=state.position,
        before=None,
        phase=EventPhase.DECLARATION,
        use_register=False,
    )

    with pytest.raises(ValueError, match="requires state"):
        declaration.phase_to(EventPhase.COMPLETION)
    with pytest.raises(ValueError, match="completion-only"):
        declaration.phase_to(EventPhase.EFFECT, after=state)

    completion = declaration.phase_to(EventPhase.COMPLETION, after=state)
    assert completion.phase is EventPhase.COMPLETION
    assert completion.after == state


def test_world_initialization_reuses_public_cold_projections() -> None:
    """Initial and future dynamic materialization share one state contract."""
    reset_engine_runtime()
    build_battlefield("battlefield.elevation_proving_ground")
    world = next(
        event
        for _, event in EventQueue.iter_events_since(0)
        if isinstance(event, WorldInitializedEvent)
    )
    grid = get_map()

    assert world.tiles == tuple(
        project_world_tile(tile)
        for _, tile in sorted(grid.get_all_tiles().items())
    )
    projected_objects: list[WorldObjectState] = []
    for placement in sorted(
        grid.iter_object_placements(),
        key=lambda row: (row.position, str(row.object_uuid)),
    ):
        item = BaseBlock.get(placement.object_uuid)
        assert isinstance(item, BaseItem)
        projected_objects.append(project_world_object(item, placement))
    assert world.objects == tuple(projected_objects)
    assert world.connectors == tuple(
        project_world_connector(connector)
        for connector in grid.get_all_connectors()
    )


def test_tile_authoring_adds_one_cold_root_and_existing_mechanical_child() -> None:
    """Adding support publishes complete materialization around existing mechanics."""
    reset_engine_runtime()
    cursor = EventQueue.event_cursor()

    completed = set_world_tile(
        (2, 3),
        author_uuid=uuid4(),
        surface=TileSurface(base_material=Material.WATER),
        name="Shallow Water",
        walking_cost=2,
        swimming_cost=1,
        default_light=LightLevel.DIM_LIGHT,
    )

    assert completed is not None
    assert completed.phase is EventPhase.COMPLETION
    assert completed.before is None
    assert type(completed.after) is WorldTileState
    assert completed.after.surface.base_material is Material.WATER
    tile = get_map().get_tile(2, 3)
    assert tile is not None
    assert completed.after == project_world_tile(tile)
    events = _events_since(cursor)
    children = [
        event
        for event in events
        if isinstance(event, SpatialChangeEvent)
        and event.parent_lineage == completed.lineage_uuid
    ]
    assert children
    assert all(event.lineage_uuid != completed.lineage_uuid for event in children)


def test_semantic_only_tile_replacement_has_no_fake_spatial_work() -> None:
    """Surface/name edits replace cold state without invalidating mechanics."""
    reset_engine_runtime()
    grid = get_map()
    previous = grid.set_tile(0, 0, fire_event=False)
    revisions = (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
        grid.illumination_revision,
    )
    cursor = EventQueue.event_cursor()

    completed = set_world_tile(
        (0, 0),
        author_uuid=uuid4(),
        surface=TileSurface(
            base_material=Material.STONE,
            description="polished flagstone",
        ),
        name="Polished Floor",
    )

    assert completed is not None
    assert completed.before.tile_uuid == previous.uuid
    assert completed.after.tile_uuid != previous.uuid
    assert completed.after.name == "Polished Floor"
    assert (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
        grid.illumination_revision,
    ) == revisions
    events = _events_since(cursor)
    assert not any(isinstance(event, SpatialChangeEvent) for event in events)


def test_equal_and_invalid_tile_requests_allocate_nothing_and_emit_nothing() -> None:
    """No-op and invalid requests stop before identity or event allocation."""
    reset_engine_runtime()
    grid = get_map()
    tile = grid.set_tile(0, 0, fire_event=False)
    cursor = EventQueue.event_cursor()
    blocks = dict(BaseBlock._registry)
    values = dict(BaseValue._registry)
    objects = dict(BaseObject._registry)

    assert set_world_tile(
        (0, 0),
        author_uuid=uuid4(),
        surface=tile.surface,
    ) is None
    assert EventQueue.event_cursor() == cursor
    assert BaseBlock._registry == blocks
    assert BaseValue._registry == values
    assert BaseObject._registry == objects

    with pytest.raises(ValueError, match="nonnegative strict integer"):
        set_world_tile(
            (1, 0),
            author_uuid=uuid4(),
            walking_cost=-1,
        )
    assert grid.get_tile(1, 0) is None
    assert EventQueue.event_cursor() == cursor
    assert BaseBlock._registry == blocks
    assert BaseValue._registry == values
    assert BaseObject._registry == objects


def test_tile_replacement_releases_only_the_displaced_owned_graph() -> None:
    """Detachment clears local values/modifiers and preserves imported/sibling owners."""
    reset_engine_runtime()
    grid = get_map()
    previous = grid.set_tile(0, 0, fire_event=False)
    sibling = grid.set_tile(1, 0, fire_event=False)
    imported_owner = ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=7,
        value_name="Imported owner",
    )
    imported_owner.set_target_entity(previous.uuid)
    previous.walking_cost.set_target_entity(imported_owner.source_entity_uuid)
    previous.walking_cost.set_from_target(imported_owner)
    old_values, old_modifiers = _tile_graph_uuids(previous)
    sibling_values, sibling_modifiers = _tile_graph_uuids(sibling)

    completed = set_world_tile(
        (0, 0),
        author_uuid=uuid4(),
        name="Replacement",
    )

    assert completed is not None
    assert BaseBlock.get(previous.uuid) is None
    assert all(BaseValue.get(value_uuid) is None for value_uuid in old_values)
    assert all(BaseObject.get(modifier_uuid) is None for modifier_uuid in old_modifiers)
    assert BaseValue.get(imported_owner.uuid) is imported_owner
    assert all(BaseValue.get(value_uuid) is not None for value_uuid in sibling_values)
    assert all(BaseObject.get(modifier_uuid) is not None for modifier_uuid in sibling_modifiers)
    assert grid.get_tile(1, 0) is sibling


def test_tile_detachment_authenticates_root_channel_and_modifier_ownership() -> None:
    """A foreign empty channel or modifier cannot be unregistered as Tile-owned."""
    reset_engine_runtime()
    grid = get_map()
    tile = grid.set_tile(0, 0, fire_event=False)
    foreign_value = ModifiableValue.create(
        source_entity_uuid=uuid4(),
        value_name="Foreign channel owner",
    )
    original_channel = tile.walking_cost.to_target_contextual
    tile.walking_cost.to_target_contextual = foreign_value.to_target_contextual
    cursor = EventQueue.event_cursor()

    with pytest.raises(ValueError, match="channel ownership"):
        set_world_tile((0, 0), author_uuid=uuid4(), name="Rejected")

    assert grid.get_tile(0, 0) is tile
    assert BaseValue.get(foreign_value.to_target_contextual.uuid) is (
        foreign_value.to_target_contextual
    )
    assert EventQueue.event_cursor() == cursor

    tile.walking_cost.to_target_contextual = original_channel
    foreign_modifier = NumericalModifier.create(
        source_entity_uuid=uuid4(),
        name="Foreign movement effect",
        value=1,
    )
    tile.walking_cost.self_static.add_value_modifier(foreign_modifier)
    with pytest.raises(ValueError, match="modifier ownership"):
        set_world_tile((0, 0), author_uuid=uuid4(), name="Rejected again")
    assert BaseObject.get(foreign_modifier.uuid) is foreign_modifier


def test_tile_detachment_rejects_same_owner_root_and_channel_aliases() -> None:
    """Distinct Tile-owned graph slots cannot alias and leak displaced rows."""
    reset_engine_runtime()
    grid = get_map()
    tile = grid.set_tile(0, 0, fire_event=False)
    original_channel = tile.walking_cost.to_target_contextual
    tile.walking_cost.to_target_contextual = tile.flying_cost.to_target_contextual
    cursor = EventQueue.event_cursor()

    with pytest.raises(ValueError, match="channel identities"):
        set_world_tile((0, 0), author_uuid=uuid4(), name="Rejected channel alias")

    assert grid.get_tile(0, 0) is tile
    assert BaseValue.get(original_channel.uuid) is original_channel
    assert EventQueue.event_cursor() == cursor

    tile.walking_cost.to_target_contextual = original_channel
    original_root = tile.walking_cost
    tile.walking_cost = tile.flying_cost
    with pytest.raises(ValueError, match="value identities"):
        set_world_tile((0, 0), author_uuid=uuid4(), name="Rejected root alias")
    assert grid.get_tile(0, 0) is tile
    assert BaseValue.get(original_root.uuid) is original_root
    assert EventQueue.event_cursor() == cursor


def test_tile_detachment_rejects_same_owner_modifier_aliases() -> None:
    """A Tile modifier row cannot be owned by two local channel slots."""
    reset_engine_runtime()
    grid = get_map()
    tile = grid.set_tile(0, 0, fire_event=False)
    walking_base = tile.walking_cost.get_base_modifier()
    flying_base = tile.flying_cost.get_base_modifier()
    assert walking_base is not None
    assert flying_base is not None
    tile.flying_cost.self_static.remove_value_modifier(flying_base.uuid)
    tile.flying_cost.self_static.add_value_modifier(walking_base)
    cursor = EventQueue.event_cursor()

    with pytest.raises(ValueError, match="modifier identities"):
        set_world_tile((0, 0), author_uuid=uuid4(), name="Rejected modifier alias")

    assert grid.get_tile(0, 0) is tile
    assert BaseObject.get(walking_base.uuid) is walking_base
    assert BaseObject.get(flying_base.uuid) is flying_base
    assert EventQueue.event_cursor() == cursor


def test_tile_detachment_rejects_modifier_stored_under_foreign_key() -> None:
    """Cleanup keys must authenticate the same registry rows as their values."""
    reset_engine_runtime()
    grid = get_map()
    tile = grid.set_tile(0, 0, fire_event=False)
    walking_base = tile.walking_cost.get_base_modifier()
    assert walking_base is not None
    foreign = NumericalModifier.create(
        source_entity_uuid=uuid4(),
        name="Foreign key owner",
        value=1,
    )
    tile.walking_cost.self_static.value_modifiers.pop(walking_base.uuid)
    tile.walking_cost.self_static.value_modifiers[foreign.uuid] = walking_base
    cursor = EventQueue.event_cursor()

    with pytest.raises(ValueError, match="key does not match identity"):
        set_world_tile((0, 0), author_uuid=uuid4(), name="Rejected wrong key")

    assert grid.get_tile(0, 0) is tile
    assert BaseObject.get(walking_base.uuid) is walking_base
    assert BaseObject.get(foreign.uuid) is foreign
    assert EventQueue.event_cursor() == cursor


def test_tile_detachment_authenticates_the_tile_registry_row() -> None:
    """Cleanup cannot unregister another block occupying the Tile UUID row."""
    reset_engine_runtime()
    grid = get_map()
    tile = grid.set_tile(0, 0, fire_event=False)
    foreign = BaseBlock(
        uuid=tile.uuid,
        source_entity_uuid=uuid4(),
        name="Foreign block row",
    )
    cursor = EventQueue.event_cursor()

    with pytest.raises(ValueError, match="Tile registry ownership"):
        set_world_tile((0, 0), author_uuid=uuid4(), name="Rejected block row")

    assert grid.get_tile(0, 0) is tile
    assert BaseBlock.get(tile.uuid) is foreign
    assert EventQueue.event_cursor() == cursor


def test_tile_detachment_rejects_owned_condition_handler_and_light() -> None:
    """Tile-owned live runtime members must be removed by their own owners."""
    reset_engine_runtime(grid_size=(1, 1))
    grid = get_map()
    tile = grid.get_tile(0, 0)
    assert tile is not None

    condition = BaseCondition(
        name="Tile marker",
        source_entity_uuid=tile.uuid,
        target_entity_uuid=tile.uuid,
    )
    assert tile.add_condition(condition) is not None
    _assert_tile_replacement_rejected("direct conditions")
    assert tile.remove_condition(condition.name)

    def observe(_event: Event, _source_uuid) -> None:
        return None

    handler = EventHandler(
        source_entity_uuid=tile.uuid,
        name="Tile-owned observer",
        trigger_conditions=[Trigger(
            event_type=EventType.BASE_ACTION,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=observe,
    )
    tile.add_event_handler(handler)
    _assert_tile_replacement_rejected("event handlers")
    tile.remove_event_handler(handler)

    light_uuid = grid.add_light_source(
        (0, 0),
        bright_radius_feet=0,
        dim_radius_feet=0,
        anchor_uuid=tile.uuid,
    )
    _assert_tile_replacement_rejected("light sources")
    grid.remove_light_source(light_uuid)
    assert light_uuid not in tile.get_attached_light_sources()


def test_tile_detachment_rejects_entity_and_spatial_condition_references() -> None:
    """Occupancy and independent spatial coverage retain their support Tile."""
    reset_engine_runtime(grid_size=(2, 1))
    create_test_entity(
        name="Tile occupant",
        config=EntityConfig(position=(0, 0)),
    )
    _assert_tile_replacement_rejected("entity occupancy")

    reset_engine_runtime(grid_size=(2, 1))
    source_uuid = uuid4()
    spatial = SpatialCondition(
        name="Tile field",
        source_entity_uuid=source_uuid,
        content_ref=ContentRef(
            pack_id="test.world_authoring",
            definition_kind=ContentDefinitionKind.CONDITION,
            content_id="condition.spatial.tile_field",
            content_version=1,
            definition_contract_hash="0" * 64,
        ),
        position=(0, 0),
        affected_positions={(0, 0)},
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        blocking_policy=SpatialEffectBlockingPolicy.FOOTPRINT,
    )
    cause = Event(
        name="Place test field",
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.EFFECT,
    )
    completion = spatial.activate(parent_event=cause)
    assert completion is not None
    _assert_tile_replacement_rejected("spatial conditions")
    assert spatial.deactivate(parent_event=completion)


def test_tile_detachment_rejects_center_and_boundary_world_objects() -> None:
    """Both placement bands retain the Tile that authenticates their support."""
    reset_engine_runtime(grid_size=(1, 1))
    center = BaseItem(
        source_entity_uuid=uuid4(),
        item_id="test.world.center_marker",
        name="Center marker",
    )
    center.place_on_grid((0, 0))
    assert get_map().get_object_placement(center.uuid) is not None
    _assert_tile_replacement_rejected("world objects")

    reset_engine_runtime(grid_size=(1, 1))
    boundary = DirectionalWall(
        source_entity_uuid=uuid4(),
        item_id="test.world.boundary_wall",
        name="Boundary wall",
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    boundary.place_on_grid(
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    assert get_map().get_object_placement(boundary.uuid) is not None
    _assert_tile_replacement_rejected("world objects")


def test_tile_detachment_rejects_connector_support() -> None:
    """A live connector endpoint retains each exact support Tile identity."""
    reset_engine_runtime(grid_size=(2, 1))
    connector = get_map().register_connector(
        TraversalConnectorDefinition(
            authored_id="connector.test.tile_guard",
            kind=TraversalConnectorKind.PASSAGE,
            presentation_key="passage",
            endpoint_positions=((0, 0), (1, 0)),
            movement_cost_feet=5,
            bidirectional=True,
            enabled=True,
            provocation_policy=(
                ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT
            ),
        )
    )
    assert connector is not None
    _assert_tile_replacement_rejected("connectors")


def test_tile_removal_veto_is_precommit_and_cancels_the_world_root() -> None:
    """A detailed declaration veto leaves Tile/index/graph authoritative."""
    reset_engine_runtime()
    grid = get_map()
    tile = grid.set_tile(0, 0, fire_event=False)
    tile_values, tile_modifiers = _tile_graph_uuids(tile)

    def reject(event: Event, _source_uuid) -> Event:
        return event.cancel("remove rejected")

    handler = EventHandler(
        source_entity_uuid=uuid4(),
        name="Reject Tile removal",
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=reject,
    )
    EventQueue.add_event_handler(handler)
    cursor = EventQueue.event_cursor()
    try:
        with pytest.raises(ValueError, match="canceled"):
            remove_world_tile((0, 0), author_uuid=uuid4())
    finally:
        EventQueue.remove_event_handler(handler)

    assert grid.get_tile(0, 0) is tile
    assert grid.get_tile_by_uuid(tile.uuid) is tile
    assert BaseBlock.get(tile.uuid) is tile
    assert all(BaseValue.get(value_uuid) is not None for value_uuid in tile_values)
    assert all(BaseObject.get(modifier_uuid) is not None for modifier_uuid in tile_modifiers)
    events = _events_since(cursor)
    assert any(
        isinstance(event, WorldModifiedEvent)
        and event.phase is EventPhase.CANCEL
        for event in events
    )
    assert not any(
        isinstance(event, WorldModifiedEvent)
        and event.phase is EventPhase.COMPLETION
        for event in events
    )


def test_world_tile_elevation_uses_the_existing_typed_child() -> None:
    """Support height remains a GridMap-owned mechanical change under the root."""
    reset_engine_runtime()
    grid = get_map()
    grid.set_tile(0, 0, fire_event=False)
    revision = grid.movement_revision
    cursor = EventQueue.event_cursor()

    completed = set_world_tile_elevation(
        (0, 0),
        height=1,
        surface_kind=ElevationSurfaceKind.RAMP,
        slope_axis=SlopeAxis.EAST_WEST,
        author_uuid=uuid4(),
    )

    assert completed is not None
    assert completed.before.elevation_steps == 0
    assert completed.after.elevation_steps == 1
    assert grid.movement_revision == revision + 1
    assert any(
        event.event_type is EventType.SPATIAL_TILE_CHANGED
        and event.parent_lineage == completed.lineage_uuid
        for event in _events_since(cursor)
    )


def test_full_tile_support_change_invalidates_paths_through_the_existing_child() -> None:
    """Height/slope replacement is traversal mechanics, not semantic metadata."""
    reset_engine_runtime()
    grid = get_map()
    grid.set_tile(0, 0, fire_event=False)
    revision = grid.movement_revision
    cursor = EventQueue.event_cursor()

    completed = set_world_tile(
        (0, 0),
        author_uuid=uuid4(),
        height=1,
        elevation_surface_kind=ElevationSurfaceKind.RAMP,
        slope_axis=SlopeAxis.EAST_WEST,
    )

    assert completed is not None
    assert completed.after.elevation_steps == 1
    assert grid.movement_revision == revision + 1
    assert any(
        isinstance(event, SpatialChangeEvent)
        and event.parent_lineage == completed.lineage_uuid
        for event in _events_since(cursor)
    )


def test_invalid_elevation_owner_reference_fails_before_world_declaration() -> None:
    """Known support guards do not strand an accepted world root."""
    reset_engine_runtime()
    grid = get_map()
    tile = grid.set_tile(0, 0, fire_event=False)
    marker = BaseItem(
        source_entity_uuid=uuid4(),
        item_id="test.world.marker",
        name="Marker",
    )
    placement = grid.place_object(marker.uuid, (0, 0))
    assert placement is not None
    cursor = EventQueue.event_cursor()

    with pytest.raises(ValueError, match="center objects"):
        set_world_tile_elevation(
            (0, 0),
            height=1,
            surface_kind=ElevationSurfaceKind.ORDINARY,
            slope_axis=None,
            author_uuid=uuid4(),
        )

    assert grid.get_tile(0, 0) is tile
    assert EventQueue.event_cursor() == cursor


def test_successful_tile_removal_has_cold_absence_and_releases_owned_graph() -> None:
    """A free support disappears only after its detailed child is accepted."""
    reset_engine_runtime()
    grid = get_map()
    tile = grid.set_tile(0, 0, fire_event=False)
    before = project_world_tile(tile)
    values, modifiers = _tile_graph_uuids(tile)

    completed = remove_world_tile((0, 0), author_uuid=uuid4())

    assert completed is not None
    assert completed.before == before
    assert completed.after is None
    assert grid.get_tile(0, 0) is None
    assert grid.get_tile_by_uuid(tile.uuid) is None
    assert BaseBlock.get(tile.uuid) is None
    assert all(BaseValue.get(value_uuid) is None for value_uuid in values)
    assert all(BaseObject.get(modifier_uuid) is None for modifier_uuid in modifiers)


def test_masked_base_light_changes_only_the_authored_root() -> None:
    """A brighter active source masks default-light semantics from observers."""
    reset_engine_runtime()
    grid = get_map()
    grid.set_tile(
        0,
        0,
        default_light=LightLevel.DARKNESS,
        fire_event=False,
    )
    grid.add_light_source(
        (0, 0),
        bright_radius_feet=5,
        dim_radius_feet=0,
    )
    tile = grid.get_tile(0, 0)
    assert tile is not None
    assert tile.resolved_light_level is LightLevel.BRIGHT_LIGHT
    revision = grid.illumination_revision
    cursor = EventQueue.event_cursor()

    completed = set_world_tile_base_light(
        (0, 0),
        level=LightLevel.DIM_LIGHT,
        author_uuid=uuid4(),
    )

    assert completed is not None
    assert completed.before.default_light is LightLevel.DARKNESS
    assert completed.after.default_light is LightLevel.DIM_LIGHT
    assert completed.after.resolved_light is LightLevel.BRIGHT_LIGHT
    assert grid.illumination_revision == revision
    events = _events_since(cursor)
    assert not any(isinstance(event, SpatialChangeEvent) for event in events)


def test_masked_full_tile_replacement_preserves_light_without_fake_child() -> None:
    """A semantic/default edit under brighter illumination remains root-only."""
    reset_engine_runtime()
    grid = get_map()
    grid.set_tile(
        0,
        0,
        default_light=LightLevel.DARKNESS,
        fire_event=False,
    )
    grid.apply_light_modifier(
        uuid4(),
        {(0, 0)},
        LightLevel.VERY_BRIGHT,
    )
    revision = grid.illumination_revision
    cursor = EventQueue.event_cursor()

    completed = set_world_tile(
        (0, 0),
        author_uuid=uuid4(),
        name="Renamed illuminated floor",
        default_light=LightLevel.DIM_LIGHT,
    )

    assert completed is not None
    assert completed.before.resolved_light is LightLevel.VERY_BRIGHT
    assert completed.after.default_light is LightLevel.DIM_LIGHT
    assert completed.after.resolved_light is LightLevel.VERY_BRIGHT
    assert grid.illumination_revision == revision
    assert not any(
        isinstance(event, SpatialChangeEvent)
        for event in _events_since(cursor)
    )


def test_unmasked_and_canceled_base_light_changes_obey_precommit_ordering() -> None:
    """Real light deltas publish once; a declaration veto preserves defaults."""
    reset_engine_runtime()
    grid = get_map()
    grid.set_tile(0, 0, fire_event=False)
    tile = grid.get_tile(0, 0)
    assert tile is not None
    revision = grid.illumination_revision
    completed = set_world_tile_base_light(
        (0, 0),
        level=LightLevel.DARKNESS,
        author_uuid=uuid4(),
    )
    assert completed is not None
    assert tile.default_light is LightLevel.DARKNESS
    assert grid.illumination_revision == revision + 1

    def reject(event: Event, _source_uuid) -> Event:
        return event.cancel("light rejected")

    handler = EventHandler(
        source_entity_uuid=uuid4(),
        name="Reject Tile light",
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_LIGHT_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=reject,
    )
    EventQueue.add_event_handler(handler)
    revision = grid.illumination_revision
    try:
        with pytest.raises(ValueError, match="canceled"):
            set_world_tile_base_light(
                (0, 0),
                level=LightLevel.BRIGHT_LIGHT,
                author_uuid=uuid4(),
            )
    finally:
        EventQueue.remove_event_handler(handler)
    assert tile.default_light is LightLevel.DARKNESS
    assert tile.resolved_light_level is LightLevel.DARKNESS
    assert grid.illumination_revision == revision

    execution_handler = EventHandler(
        source_entity_uuid=uuid4(),
        name="Reject Tile light execution",
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_LIGHT_CHANGED,
            event_phase=EventPhase.EXECUTION,
        )],
        event_processor=reject,
    )
    EventQueue.add_event_handler(execution_handler)
    cursor = EventQueue.event_cursor()
    try:
        with pytest.raises(ValueError, match="canceled"):
            set_world_tile_base_light(
                (0, 0),
                level=LightLevel.BRIGHT_LIGHT,
                author_uuid=uuid4(),
            )
    finally:
        EventQueue.remove_event_handler(execution_handler)
    assert tile.default_light is LightLevel.DARKNESS
    assert tile.resolved_light_level is LightLevel.DARKNESS
    assert grid.illumination_revision == revision
    assert any(
        event.event_type is EventType.SPATIAL_LIGHT_CHANGED
        and event.phase is EventPhase.CANCEL
        for event in _events_since(cursor)
    )


def test_base_light_effect_is_an_observable_non_vetoable_committed_fact() -> None:
    """A returned cancellation cannot rewrite state or starve later reactions."""
    reset_engine_runtime(grid_size=(1, 1))
    observed: list[LightLevel] = []

    def corrupt_view(event: Event, _source_uuid) -> None:
        assert isinstance(event, SpatialChangeEvent)
        assert event.light_level_map is not None
        assert event.senses_hint is not None
        assert event.senses_hint.light_changed_positions is not None
        event.light_level_map.clear()
        event.senses_hint.light_changed_positions.clear()

    def reject(event: Event, _source_uuid) -> Event:
        return event.cancel("too late to veto committed light")

    def observe(event: Event, _source_uuid) -> None:
        assert isinstance(event, SpatialChangeEvent)
        assert event.light_level_map == {"0,0": LightLevel.DARKNESS.value}
        assert event.senses_hint is not None
        assert event.senses_hint.light_changed_positions == {(0, 0)}
        tile = get_map().get_tile(0, 0)
        assert tile is not None
        observed.append(tile.resolved_light_level)

    corrupting = EventHandler(
        source_entity_uuid=uuid4(),
        name="Mutate committed light view",
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_LIGHT_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=corrupt_view,
    )
    rejecting = EventHandler(
        source_entity_uuid=uuid4(),
        name="Reject committed light",
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_LIGHT_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=reject,
    )
    observing = EventHandler(
        source_entity_uuid=uuid4(),
        name="Observe committed light",
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_LIGHT_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=observe,
    )
    EventQueue.add_event_handler(corrupting)
    EventQueue.add_event_handler(rejecting)
    EventQueue.add_event_handler(observing)
    cursor = EventQueue.event_cursor()
    try:
        completed = set_world_tile_base_light(
            (0, 0),
            level=LightLevel.DARKNESS,
            author_uuid=uuid4(),
        )
    finally:
        EventQueue.remove_event_handler(corrupting)
        EventQueue.remove_event_handler(rejecting)
        EventQueue.remove_event_handler(observing)

    assert completed is not None
    assert observed == [LightLevel.DARKNESS]
    light_lineages = {
        event.lineage_uuid
        for event in _events_since(cursor)
        if event.event_type is EventType.SPATIAL_LIGHT_CHANGED
    }
    assert len(light_lineages) == 1
    stored_effect = next(
        event
        for event in _events_since(cursor)
        if event.event_type is EventType.SPATIAL_LIGHT_CHANGED
        and event.phase is EventPhase.EFFECT
    )
    assert isinstance(stored_effect, SpatialChangeEvent)
    assert stored_effect.light_level_map == {
        "0,0": LightLevel.DARKNESS.value,
    }
    assert stored_effect.senses_hint is not None
    assert stored_effect.senses_hint.light_changed_positions == {(0, 0)}
    assert not any(
        event.phase is EventPhase.CANCEL
        and event.lineage_uuid in light_lineages
        for event in _events_since(cursor)
    )


def test_base_light_committed_effect_preserves_hidden_reveal_reaction() -> None:
    """Hidden observes the committed Tile state and removes itself normally."""
    reset_engine_runtime(grid_size=(1, 1))
    hidden = create_skeleton(
        name="Hidden on authored Tile",
        position=(0, 0),
        darkvision=False,
    )
    hidden.compose_entity()
    Game().deploy_entity(hidden, hidden.position)
    hidden.add_condition(
        Hidden(
            source_entity_uuid=hidden.uuid,
            target_entity_uuid=hidden.uuid,
            stealth_result=30,
        )
    )
    assert "Hidden" in hidden.active_conditions

    completed = set_world_tile_base_light(
        (0, 0),
        level=LightLevel.VERY_BRIGHT,
        author_uuid=uuid4(),
    )

    assert completed is not None
    assert "Hidden" not in hidden.active_conditions


def _attached_world_condition(
    item: BaseItem,
    position: tuple[int, int],
) -> SpatialCondition:
    """Activate one minimal condition attached to a world-object UUID."""
    condition = SpatialCondition(
        name="Attached test field",
        source_entity_uuid=item.uuid,
        content_ref=ContentRef(
            pack_id="test.world_authoring",
            definition_kind=ContentDefinitionKind.CONDITION,
            content_id="condition.spatial.attached_world_item",
            content_version=1,
            definition_contract_hash="0" * 64,
        ),
        position=position,
        affected_positions={position},
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        anchor_kind=SpatialEffectAnchorKind.WORLD_OBJECT,
        anchor_uuid=item.uuid,
        blocking_policy=SpatialEffectBlockingPolicy.FOOTPRINT,
    )
    cause = Event(
        name="Attach test field",
        source_entity_uuid=item.uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.EFFECT,
    )
    assert condition.activate(parent_event=cause) is not None
    return condition


def test_world_item_center_placement_has_one_cold_root_and_spatial_child() -> None:
    """A registered unowned BaseItem materializes through its existing owner."""
    reset_engine_runtime(grid_size=(2, 1))
    item = BaseItem(
        source_entity_uuid=uuid4(),
        item_id="test.world.center_item",
        name="Center Item",
    )
    cursor = EventQueue.event_cursor()

    completed = place_world_item(
        item,
        (0, 0),
        orientation=CardinalDirection.NORTH,
        author_uuid=uuid4(),
    )

    placement = get_map().get_object_placement(item.uuid)
    assert placement is not None
    assert item.position == (0, 0)
    assert item.tile_uuid == placement.tile_uuid
    assert completed.before is None
    assert completed.after == project_world_object(item, placement)
    events = _events_since(cursor)
    assert any(
        event.event_type is EventType.SPATIAL_OBJECT_PLACED
        and event.phase is EventPhase.COMPLETION
        and event.parent_lineage == completed.lineage_uuid
        for event in events
    )


def test_incident_tiles_may_each_own_their_adjacent_boundary_wall() -> None:
    """The two directed Tile sides are independent placement authorities."""
    reset_engine_runtime(grid_size=(2, 1))
    west = DirectionalWall(
        source_entity_uuid=uuid4(),
        item_id="test.world.wall.west_owner",
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    east = DirectionalWall(
        source_entity_uuid=uuid4(),
        item_id="test.world.wall.east_owner",
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )

    place_world_item(
        west,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
        author_uuid=uuid4(),
    )
    place_world_item(
        east,
        (1, 0),
        boundary_direction=CardinalDirection.WEST,
        author_uuid=uuid4(),
    )

    grid = get_map()
    assert grid.get_boundary_objects_at(
        (0, 0), CardinalDirection.EAST,
    ) == {west.uuid}
    assert grid.get_boundary_objects_at(
        (1, 0), CardinalDirection.WEST,
    ) == {east.uuid}


@pytest.mark.parametrize(
    "location_fields",
    (
        {"owner_uuid": uuid4()},
        {"stored_in_uuid": uuid4()},
        {"is_equipped": True},
        {"equipped_slot": "main_hand"},
        {"tile_uuid": uuid4()},
    ),
)
def test_world_item_placement_rejects_competing_location_authority(
    location_fields,
) -> None:
    """Inventory, equipment, and floor mirrors cannot coexist with placement."""
    reset_engine_runtime(grid_size=(1, 1))
    item = BaseItem(
        source_entity_uuid=uuid4(),
        item_id="test.world.location_guard",
        **location_fields,
    )
    cursor = EventQueue.event_cursor()

    with pytest.raises(ValueError, match="authority"):
        place_world_item(item, (0, 0), author_uuid=uuid4())

    assert get_map().get_object_placement(item.uuid) is None
    assert EventQueue.event_cursor() == cursor


def test_canceled_world_item_placement_leaves_grid_and_floor_mirror_unchanged() -> None:
    """The BaseItem mirror is written only from a committed GridMap result."""
    reset_engine_runtime(grid_size=(1, 1))
    item = BaseItem(
        source_entity_uuid=uuid4(),
        item_id="test.world.canceled_placement",
    )
    initial_position = item.position

    def reject(event: Event, _source_uuid) -> Event:
        return event.cancel("placement rejected")

    handler = EventHandler(
        source_entity_uuid=uuid4(),
        name="Reject object placement",
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_OBJECT_PLACED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=reject,
    )
    EventQueue.add_event_handler(handler)
    cursor = EventQueue.event_cursor()
    try:
        with pytest.raises(ValueError, match="canceled"):
            place_world_item(item, (0, 0), author_uuid=uuid4())
    finally:
        EventQueue.remove_event_handler(handler)

    assert get_map().get_object_placement(item.uuid) is None
    assert item.tile_uuid is None
    assert item.position == initial_position
    events = _events_since(cursor)
    assert any(
        isinstance(event, WorldModifiedEvent)
        and event.phase is EventPhase.CANCEL
        for event in events
    )


def test_world_item_move_and_orientation_publish_exact_cold_transitions() -> None:
    """Movement and facing reuse placement mechanics and synchronize one mirror."""
    reset_engine_runtime(grid_size=(3, 1))
    item = BaseItem(
        source_entity_uuid=uuid4(),
        item_id="test.world.movable_item",
    )
    place_world_item(item, (0, 0), author_uuid=uuid4())
    cursor = EventQueue.event_cursor()

    moved = move_world_item(
        item,
        (1, 0),
        orientation=CardinalDirection.EAST,
        author_uuid=uuid4(),
    )

    assert moved is not None
    assert moved.before.placement.position == (0, 0)
    assert moved.after.placement.position == (1, 0)
    assert moved.after.placement.orientation is CardinalDirection.EAST
    assert item.position == (1, 0)
    assert item.tile_uuid == moved.after.placement.tile_uuid
    movement_events = _events_since(cursor)
    assert {
        event.event_type
        for event in movement_events
        if event.parent_lineage == moved.lineage_uuid
        and event.phase is EventPhase.COMPLETION
    } >= {
        EventType.SPATIAL_OBJECT_REMOVED,
        EventType.SPATIAL_OBJECT_PLACED,
    }

    cursor = EventQueue.event_cursor()
    oriented = orient_world_item(
        item,
        CardinalDirection.SOUTH,
        author_uuid=uuid4(),
    )
    assert oriented is not None
    assert oriented.before.placement.position == (1, 0)
    assert oriented.after.placement.position == (1, 0)
    assert oriented.after.placement.tile_uuid == oriented.before.placement.tile_uuid
    assert oriented.after.placement.orientation is CardinalDirection.SOUTH
    assert any(
        event.event_type is EventType.SPATIAL_OBJECT_CHANGED
        and event.parent_lineage == oriented.lineage_uuid
        for event in _events_since(cursor)
    )

    cursor = EventQueue.event_cursor()
    assert orient_world_item(
        item,
        CardinalDirection.SOUTH,
        author_uuid=uuid4(),
    ) is None
    assert move_world_item(
        item,
        (1, 0),
        orientation=CardinalDirection.SOUTH,
        author_uuid=uuid4(),
    ) is None
    assert EventQueue.event_cursor() == cursor


def test_rejected_move_arrival_cancels_departure_and_preserves_both_owners() -> None:
    """An admitted departure cannot remain as an orphan EFFECT fact."""
    reset_engine_runtime(grid_size=(2, 1))
    item = BaseItem(
        source_entity_uuid=uuid4(),
        item_id="test.world.rejected_arrival",
    )
    place_world_item(item, (0, 0), author_uuid=uuid4())
    previous = get_map().get_object_placement(item.uuid)
    assert previous is not None

    def reject_arrival(event: Event, _source_uuid) -> Event:
        return event.cancel("arrival rejected")

    handler = EventHandler(
        source_entity_uuid=uuid4(),
        name="Reject move arrival",
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_OBJECT_PLACED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=reject_arrival,
    )
    EventQueue.add_event_handler(handler)
    cursor = EventQueue.event_cursor()
    try:
        with pytest.raises(ValueError, match="canceled"):
            move_world_item(item, (1, 0), author_uuid=uuid4())
    finally:
        EventQueue.remove_event_handler(handler)

    assert get_map().get_object_placement(item.uuid) == previous
    assert item.position == previous.position
    assert item.tile_uuid == previous.tile_uuid
    events = _events_since(cursor)
    departure_effect = next(
        event
        for event in events
        if event.event_type is EventType.SPATIAL_OBJECT_REMOVED
        and event.phase is EventPhase.EFFECT
    )
    assert any(
        event.phase is EventPhase.CANCEL
        and event.lineage_uuid == departure_effect.lineage_uuid
        for event in events
    )
    assert any(
        isinstance(event, WorldModifiedEvent)
        and event.phase is EventPhase.CANCEL
        for event in events
    )


def test_attached_condition_blocks_position_edits_but_not_orientation() -> None:
    """The finite preflight preserves an active condition and its handler."""
    reset_engine_runtime(grid_size=(2, 1))
    item = BaseItem(
        source_entity_uuid=uuid4(),
        item_id="test.world.condition_anchor",
    )
    place_world_item(item, (0, 0), author_uuid=uuid4())
    condition = _attached_world_condition(item, (0, 0))
    handlers = (
        tuple(condition.event_handlers_uuids),
        tuple(condition.spatial_handler_uuids),
    )
    footprint = set(condition.affected_positions)
    cursor = EventQueue.event_cursor()

    with pytest.raises(ValueError, match="active spatial condition"):
        move_world_item(item, (1, 0), author_uuid=uuid4())
    with pytest.raises(ValueError, match="active spatial condition"):
        remove_world_item(item, author_uuid=uuid4())
    assert EventQueue.event_cursor() == cursor

    oriented = orient_world_item(
        item,
        CardinalDirection.EAST,
        author_uuid=uuid4(),
    )
    assert oriented is not None
    assert condition.is_active_spatial_condition()
    assert set(condition.affected_positions) == footprint
    assert (
        tuple(condition.event_handlers_uuids),
        tuple(condition.spatial_handler_uuids),
    ) == handlers


def test_placement_rejects_an_already_active_attached_condition_pre_root() -> None:
    """A new anchor position is not invented for an existing live condition."""
    reset_engine_runtime(grid_size=(1, 1))
    item = BaseItem(
        source_entity_uuid=uuid4(),
        item_id="test.world.unplaced_condition_anchor",
    )
    condition = _attached_world_condition(item, (0, 0))
    cursor = EventQueue.event_cursor()

    with pytest.raises(ValueError, match="active spatial condition"):
        place_world_item(item, (0, 0), author_uuid=uuid4())

    assert get_map().get_object_placement(item.uuid) is None
    assert condition.is_active_spatial_condition()
    assert EventQueue.event_cursor() == cursor


def test_world_item_removal_unplaces_without_destroying_or_unregistering() -> None:
    """Structural absence is distinct from the item's gameplay destruction."""
    reset_engine_runtime(grid_size=(1, 1))
    item = DestructionWitnessItem(
        source_entity_uuid=uuid4(),
        item_id="test.world.destruction_witness",
    )
    place_world_item(item, (0, 0), author_uuid=uuid4())

    completed = remove_world_item(item, author_uuid=uuid4())

    assert completed.before.item.item_uuid == item.uuid
    assert completed.after is None
    assert get_map().get_object_placement(item.uuid) is None
    assert item.tile_uuid is None
    assert item.position == (0, 0)
    assert item.destruction_count == 0
    assert item.removal_callback_count == 0
    assert BaseBlock.get(item.uuid) is item


def test_lit_wall_torch_follows_move_suppresses_on_remove_and_resumes() -> None:
    """GridMap owns one persistent attached-light identity across presence edits."""
    reset_engine_runtime(grid_size=(5, 1))
    grid = get_map()
    for position in range(5):
        assert grid.set_tile_base_light(
            (position, 0),
            LightLevel.DARKNESS,
        )
    torch = WallTorch(
        source_entity_uuid=uuid4(),
        item_id="test.world.wall_torch",
        very_bright_radius_feet=5,
        bright_radius_feet=0,
        dim_radius_feet=0,
    )
    place_world_item(torch, (0, 0), author_uuid=uuid4())
    assert torch.light() is not None
    light_uuid, = torch.get_attached_light_sources()
    assert grid.get_light_source_position(light_uuid) == (0, 0)
    assert grid.get_tile(0, 0).resolved_light_level is LightLevel.VERY_BRIGHT

    cursor = EventQueue.event_cursor()
    moved = move_world_item(torch, (2, 0), author_uuid=uuid4())
    assert moved is not None
    assert grid.get_light_source_position(light_uuid) == (2, 0)
    assert torch.get_attached_light_sources() == {light_uuid}
    move_events = _events_since(cursor)
    detailed_lineages = {
        event.lineage_uuid
        for event in move_events
        if event.parent_lineage == moved.lineage_uuid
        and event.event_type is EventType.SPATIAL_OBJECT_PLACED
    }
    assert any(
        event.event_type is EventType.SPATIAL_LIGHT_CHANGED
        and event.parent_lineage in detailed_lineages
        for event in move_events
    )

    removed = remove_world_item(torch, author_uuid=uuid4())
    assert removed.after is None
    assert torch.is_lit
    assert torch.get_attached_light_sources() == {light_uuid}
    assert grid.get_light_source_position(light_uuid) == (2, 0)
    assert all(
        tile.resolved_light_level is LightLevel.DARKNESS
        for tile in grid.get_all_tiles().values()
    )

    replaced = place_world_item(torch, (4, 0), author_uuid=uuid4())
    assert replaced.after.placement.position == (4, 0)
    assert grid.get_light_source_position(light_uuid) == (4, 0)
    assert torch.get_attached_light_sources() == {light_uuid}
    assert grid.get_tile(4, 0).resolved_light_level is LightLevel.VERY_BRIGHT


def _world_ladder(
    *,
    endpoint_positions: tuple[tuple[int, int], tuple[int, int]] = (
        (0, 0),
        (1, 0),
    ),
    presentation_key: str = "ladder.stone",
    movement_cost_feet: int = 5,
    enabled: bool = True,
) -> TraversalConnectorDefinition:
    """Return one exact immutable connector definition for authoring tests."""
    return TraversalConnectorDefinition(
        authored_id="connector.test.world_ladder",
        kind=TraversalConnectorKind.LADDER,
        presentation_key=presentation_key,
        endpoint_positions=endpoint_positions,
        movement_cost_feet=movement_cost_feet,
        bidirectional=True,
        enabled=enabled,
        provocation_policy=ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT,
    )


def _connector_world() -> None:
    """Create three adjacent supports with distinct exact elevations."""
    reset_engine_runtime(grid_size=(3, 1))
    grid = get_map()
    assert grid.set_tile_elevation(
        (1, 0),
        height=1,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )
    assert grid.set_tile_elevation(
        (2, 0),
        height=2,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )


def test_world_connector_registration_materializes_complete_cold_state() -> None:
    """Registration exposes semantic presentation and authenticated supports."""
    _connector_world()
    grid = get_map()
    cursor = EventQueue.event_cursor()

    completed = register_world_connector(
        _world_ladder(),
        author_uuid=uuid4(),
    )

    assert completed.before is None
    connector = grid.get_connector(completed.connector_uuid)
    assert connector is not None
    assert completed.after == project_world_connector(connector)
    assert completed.after.presentation_key == "ladder.stone"
    assert completed.after.support_tile_uuids == (
        grid.get_tile(0, 0).uuid,
        grid.get_tile(1, 0).uuid,
    )
    assert completed.after.endpoint_elevations_feet == (0, 5)
    events = _events_since(cursor)
    assert any(
        isinstance(event, TraversalConnectorChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.parent_lineage == completed.lineage_uuid
        for event in events
    )


def test_world_connector_replace_preserves_identity_and_reindexes_supports() -> None:
    """Replacement changes one immutable value and the existing GridMap indexes."""
    _connector_world()
    grid = get_map()
    registered = register_world_connector(
        _world_ladder(),
        author_uuid=uuid4(),
    )
    previous = grid.get_connector(registered.connector_uuid)
    assert previous is not None
    cursor = EventQueue.event_cursor()

    completed = replace_world_connector(
        previous.uuid,
        _world_ladder(
            endpoint_positions=((1, 0), (2, 0)),
            presentation_key="ladder.wood",
            movement_cost_feet=10,
        ),
        author_uuid=uuid4(),
    )

    assert completed is not None
    replacement = grid.get_connector(previous.uuid)
    assert replacement is not None
    assert replacement.uuid == previous.uuid
    assert replacement.authored_id == previous.authored_id
    assert replacement.revision == previous.revision + 1
    assert completed.before == project_world_connector(previous)
    assert completed.after == project_world_connector(replacement)
    assert grid.get_connectors_at((0, 0)) == ()
    assert grid.get_connectors_at((1, 0)) == (replacement,)
    assert grid.get_connectors_at((2, 0)) == (replacement,)
    assert any(
        isinstance(event, TraversalConnectorChangeEvent)
        and event.parent_lineage == completed.lineage_uuid
        for event in _events_since(cursor)
    )


def test_equal_connector_replacement_is_pre_root_and_allocation_free() -> None:
    """Definition equality leaves identity, indexes, revision, and events exact."""
    _connector_world()
    grid = get_map()
    registered = register_world_connector(
        _world_ladder(),
        author_uuid=uuid4(),
    )
    connector = grid.get_connector(registered.connector_uuid)
    assert connector is not None
    revision = grid.connector_revision
    endpoint_indexes = (
        grid.get_connectors_at((0, 0)),
        grid.get_connectors_at((1, 0)),
    )
    cursor = EventQueue.event_cursor()

    assert replace_world_connector(
        connector.uuid,
        connector.definition(),
        author_uuid=uuid4(),
    ) is None

    assert grid.get_connector(connector.uuid) is connector
    assert grid.connector_revision == revision
    assert (
        grid.get_connectors_at((0, 0)),
        grid.get_connectors_at((1, 0)),
    ) == endpoint_indexes
    assert EventQueue.event_cursor() == cursor


def test_world_connector_enable_disable_and_remove_are_exact_roots() -> None:
    """Typed state changes preserve identity until explicit structural removal."""
    _connector_world()
    grid = get_map()
    registered = register_world_connector(
        _world_ladder(),
        author_uuid=uuid4(),
    )
    connector = grid.get_connector(registered.connector_uuid)
    assert connector is not None

    disabled_root = set_world_connector_enabled(
        connector.uuid,
        False,
        author_uuid=uuid4(),
    )
    assert disabled_root is not None
    disabled = grid.get_connector(connector.uuid)
    assert disabled is not None
    assert disabled.uuid == connector.uuid
    assert disabled.authored_id == connector.authored_id
    assert disabled.revision == connector.revision + 1
    assert disabled_root.before.enabled is True
    assert disabled_root.after.enabled is False

    cursor = EventQueue.event_cursor()
    assert set_world_connector_enabled(
        connector.uuid,
        False,
        author_uuid=uuid4(),
    ) is None
    assert EventQueue.event_cursor() == cursor

    enabled_root = set_world_connector_enabled(
        connector.uuid,
        True,
        author_uuid=uuid4(),
    )
    assert enabled_root is not None
    enabled = grid.get_connector(connector.uuid)
    assert enabled is not None and enabled.enabled

    removed_root = remove_world_connector(
        connector.uuid,
        author_uuid=uuid4(),
    )
    assert removed_root is not None
    assert removed_root.before == project_world_connector(enabled)
    assert removed_root.after is None
    assert grid.get_connector(connector.uuid) is None
    assert grid.get_connector_by_authored_id(connector.authored_id) is None
    assert grid.get_connectors_at((0, 0)) == ()
    assert grid.get_connectors_at((1, 0)) == ()

    cursor = EventQueue.event_cursor()
    assert remove_world_connector(
        connector.uuid,
        author_uuid=uuid4(),
    ) is None
    assert EventQueue.event_cursor() == cursor


def test_invalid_and_duplicate_connector_edits_fail_before_world_root() -> None:
    """Known support and identity failures never strand an accepted root."""
    reset_engine_runtime(grid_size=(1, 1))
    cursor = EventQueue.event_cursor()
    with pytest.raises(ValueError, match="no support Tile"):
        register_world_connector(_world_ladder(), author_uuid=uuid4())
    assert EventQueue.event_cursor() == cursor
    assert get_map().get_all_connectors() == ()

    _connector_world()
    registered = register_world_connector(
        _world_ladder(),
        author_uuid=uuid4(),
    )
    cursor = EventQueue.event_cursor()
    with pytest.raises(ValueError, match="duplicate connector authored_id"):
        register_world_connector(_world_ladder(), author_uuid=uuid4())
    assert EventQueue.event_cursor() == cursor
    assert len(get_map().get_all_connectors()) == 1
    assert get_map().get_connector(registered.connector_uuid) is not None


def test_canceled_connector_detail_cancels_root_without_partial_indexes() -> None:
    """A typed connector veto leaves all GridMap connector owners unchanged."""
    _connector_world()
    grid = get_map()
    revision = grid.connector_revision

    def reject(event: Event, _source_uuid) -> Event:
        return event.cancel("connector rejected")

    handler = EventHandler(
        source_entity_uuid=uuid4(),
        name="Reject world connector",
        trigger_conditions=[Trigger(
            event_type=EventType.TRAVERSAL_CONNECTOR_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=reject,
    )
    EventQueue.add_event_handler(handler)
    cursor = EventQueue.event_cursor()
    try:
        with pytest.raises(ValueError, match="canceled"):
            register_world_connector(_world_ladder(), author_uuid=uuid4())
    finally:
        EventQueue.remove_event_handler(handler)

    assert grid.connector_revision == revision
    assert grid.get_all_connectors() == ()
    events = _events_since(cursor)
    assert any(
        isinstance(event, WorldModifiedEvent)
        and event.phase is EventPhase.CANCEL
        for event in events
    )
    assert not any(
        isinstance(event, WorldModifiedEvent)
        and event.phase is EventPhase.COMPLETION
        for event in events
    )


def test_world_root_completes_after_descendants_inside_a_closed_interval() -> None:
    """A renderer interval contains the settled tree even when a monitor appends."""
    reset_engine_runtime(grid_size=(4, 1))
    grid = get_map()
    for x in range(4):
        assert grid.set_tile_base_light((x, 0), LightLevel.DARKNESS)
    torch = WallTorch(
        source_entity_uuid=uuid4(),
        item_id="test.world.interval_torch",
        very_bright_radius_feet=5,
        bright_radius_feet=0,
        dim_radius_feet=0,
    )
    place_world_item(torch, (0, 0), author_uuid=uuid4())
    assert torch.light() is not None

    def append_diagnostic(completed: Event) -> None:
        Event(
            source_entity_uuid=completed.source_entity_uuid,
            name="Passive world-edit diagnostic",
            event_type=EventType.BASE_ACTION,
            phase=EventPhase.COMPLETION,
        )

    EventQueue.add_on_event_callback(
        append_diagnostic,
        event_types={EventType.WORLD_MODIFIED},
        phases={EventPhase.COMPLETION},
    )
    generation = EventQueue.generation_id()
    start_cursor = EventQueue.event_cursor()
    try:
        root = move_world_item(torch, (3, 0), author_uuid=uuid4())
    finally:
        EventQueue.remove_on_event_callback(append_diagnostic)
    assert root is not None
    end_cursor = EventQueue.event_cursor()

    indexed = tuple(EventQueue.iter_events_since(start_cursor))
    root_index = EventQueue.get_event_index(root.uuid)
    assert root_index is not None
    diagnostic_index = next(
        index
        for index, event in indexed
        if event.name == "Passive world-edit diagnostic"
    )
    assert root_index < diagnostic_index

    descendant_lineages: set[UUID] = set()
    changed = True
    while changed:
        changed = False
        accepted_parents = {root.lineage_uuid, *descendant_lineages}
        for _, event in indexed:
            if (
                event.parent_lineage in accepted_parents
                and event.lineage_uuid not in descendant_lineages
            ):
                descendant_lineages.add(event.lineage_uuid)
                changed = True
    descendant_completions = tuple(
        (index, event)
        for index, event in indexed
        if event.lineage_uuid in descendant_lineages
        and event.phase is EventPhase.COMPLETION
    )
    assert descendant_completions
    assert all(index < root_index for index, _ in descendant_completions)
    assert any(
        event.event_type is EventType.SPATIAL_OBJECT_PLACED
        and event.lineage_uuid in root.children_lineages
        for _, event in descendant_completions
    )
    assert any(
        event.event_type is EventType.SPATIAL_LIGHT_CHANGED
        for _, event in descendant_completions
    )

    copied = _copy_closed_event_interval(
        generation,
        start_cursor,
        end_cursor,
    )
    assert tuple(event.uuid for event in copied) == tuple(
        event.uuid for _, event in indexed
    )
    assert any(event.uuid == root.uuid for event in copied)

    late = Event(
        source_entity_uuid=uuid4(),
        name="Later unrelated event",
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.COMPLETION,
    )
    assert all(event.uuid != late.uuid for event in copied)

    reset_engine_runtime()
    with pytest.raises(ValueError, match="generation changed"):
        _copy_closed_event_interval(generation, start_cursor, end_cursor)


def test_cold_initialization_and_world_roots_fold_to_live_structure() -> None:
    """Detached structural values converge without replaying engine mechanics."""
    reset_engine_runtime()
    build_battlefield("battlefield.open_floor_bright")
    initialized = next(
        event
        for _, event in EventQueue.iter_events_since(0)
        if isinstance(event, WorldInitializedEvent)
    )
    roots: list[WorldModifiedEvent] = []

    tile_root = set_world_tile(
        (0, 0),
        author_uuid=uuid4(),
        surface=TileSurface(base_material=Material.WATER),
        name="Shallow Water",
        walking_cost=2,
        flying_cost=1,
        swimming_cost=1,
        burrowing_cost=0,
    )
    assert tile_root is not None
    roots.append(tile_root)
    elevation_root = set_world_tile_elevation(
        (1, 0),
        height=1,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
        author_uuid=uuid4(),
    )
    assert elevation_root is not None
    roots.append(elevation_root)
    removed_tile_root = remove_world_tile((2, 0), author_uuid=uuid4())
    assert removed_tile_root is not None
    roots.append(removed_tile_root)

    item = BaseItem(
        source_entity_uuid=uuid4(),
        item_id="test.world.materialized_marker",
        name="Materialized Marker",
    )
    roots.append(place_world_item(item, (3, 3), author_uuid=uuid4()))
    moved_root = move_world_item(
        item,
        (4, 3),
        orientation=CardinalDirection.EAST,
        author_uuid=uuid4(),
    )
    assert moved_root is not None
    roots.append(moved_root)

    connector_root = register_world_connector(
        TraversalConnectorDefinition(
            authored_id="connector.test.materialized_passage",
            kind=TraversalConnectorKind.PASSAGE,
            presentation_key="passage.stone",
            endpoint_positions=((5, 5), (6, 5)),
            movement_cost_feet=5,
            bidirectional=True,
            enabled=True,
            provocation_policy=(
                ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT
            ),
        ),
        author_uuid=uuid4(),
    )
    roots.append(connector_root)
    disabled_root = set_world_connector_enabled(
        connector_root.connector_uuid,
        False,
        author_uuid=uuid4(),
    )
    assert disabled_root is not None
    roots.append(disabled_root)

    grid = get_map()
    expected_tiles = {
        position: project_world_tile(tile)
        for position, tile in grid.get_all_tiles().items()
    }
    placement = grid.get_object_placement(item.uuid)
    assert placement is not None
    expected_objects = {item.uuid: project_world_object(item, placement)}
    expected_connectors = {
        connector.uuid: project_world_connector(connector)
        for connector in grid.get_all_connectors()
    }
    cold_initialized = initialized.model_copy(
        update={"use_register": False},
        deep=True,
    )
    cold_roots = tuple(
        root.model_copy(update={"use_register": False}, deep=True)
        for root in roots
    )

    reset_engine_runtime()
    assert get_map().get_all_tiles() == {}
    assert get_map().iter_object_placements() == ()
    assert get_map().get_all_connectors() == ()
    assert BaseBlock.get(item.uuid) is None

    materialized_tiles, materialized_objects, materialized_connectors = (
        _cold_world_maps(cold_initialized)
    )
    for root in cold_roots:
        _apply_cold_world_root(
            materialized_tiles,
            materialized_objects,
            materialized_connectors,
            root,
        )

    assert materialized_tiles == expected_tiles
    assert materialized_objects == expected_objects
    assert materialized_connectors == expected_connectors


def test_gameplay_door_torch_and_damage_do_not_emit_world_roots() -> None:
    """Concrete gameplay events remain distinct from structural authoring."""
    reset_engine_runtime(grid_size=(6, 1))
    door = DirectionalDoor(
        source_entity_uuid=uuid4(),
        item_id="test.world.gameplay_door",
    )
    place_world_item(
        door,
        (1, 0),
        boundary_direction=CardinalDirection.EAST,
        author_uuid=uuid4(),
    )
    torch = WallTorch(
        source_entity_uuid=uuid4(),
        item_id="test.world.gameplay_torch",
    )
    place_world_item(torch, (3, 0), author_uuid=uuid4())
    damage_source = uuid4()
    barrel = build_oil_barrel(damage_source)
    place_world_item(barrel, (5, 0), author_uuid=uuid4())
    cursor = EventQueue.event_cursor()

    door.open()
    door.close()
    assert torch.light() is not None
    torch.put_out()
    assert barrel.receive_damage(
        1,
        DamageType.BLUDGEONING,
        damage_source,
    ) == 1
    assert get_map().get_object_position(barrel.uuid) == (5, 0)

    gameplay_events = _events_since(cursor)
    assert gameplay_events
    assert not any(
        isinstance(event, WorldModifiedEvent)
        for event in gameplay_events
    )


def test_objective_move_keeps_two_observer_reductions_independent() -> None:
    """One root moves objective state while each observer gets one real delta."""
    reset_engine_runtime(grid_size=(30, 1))
    near = create_test_entity(
        name="Near observer",
        config=EntityConfig(position=(0, 0)),
    )
    far = create_test_entity(
        name="Far observer",
        config=EntityConfig(position=(29, 0)),
    )
    marker = BaseItem(
        source_entity_uuid=uuid4(),
        item_id="test.world.subjective_marker",
        name="Subjective Marker",
        include_in_senses_objects=True,
    )
    place_world_item(marker, (1, 0), author_uuid=uuid4())
    Entity.update_all_entities_senses(max_distance=5)
    assert marker.uuid in near.senses.objects
    assert marker.uuid not in far.senses.objects
    cursor = EventQueue.event_cursor()

    root = move_world_item(marker, (28, 0), author_uuid=uuid4())
    assert root is not None

    assert marker.uuid not in near.senses.objects
    assert marker.uuid in far.senses.objects
    contact_updates = tuple(
        event
        for event in _events_since(cursor)
        if isinstance(event, SensoryUpdateEvent)
        and (
            marker.uuid in event.object_contacts_changed
            or marker.uuid in event.object_contacts_removed
        )
    )
    assert len(contact_updates) == 2
    assert {event.observer_uuid for event in contact_updates} == {
        near.uuid,
        far.uuid,
    }
    near_update = next(
        event for event in contact_updates if event.observer_uuid == near.uuid
    )
    far_update = next(
        event for event in contact_updates if event.observer_uuid == far.uuid
    )
    assert near_update.object_contacts_removed == {marker.uuid}
    assert marker.uuid in far_update.object_contacts_changed
    assert all(event.cause_event_uuid != root.uuid for event in contact_updates)
