"""Public world-state contracts for independent spatial conditions."""

from uuid import UUID, uuid4

import pytest

from dnd.core.condition_types import DurationType
from dnd.core.base_block import BaseBlock, LightLevel, MovementMode
from dnd.core.base_conditions import BaseCondition
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import ResistanceStatus
from dnd.content.items.environment_item_builders import (
    OilBarrel,
    build_oil_barrel,
)
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    SpatialEffectInteractionEvent,
    TakeDamageEvent,
    Trigger,
)
from dnd.core.gridmap import get_map
from dnd.conditions import Concentrating
from dnd.entity import Entity
from dnd.game import Game
from dnd.items.environment_interactables import PullLeverAction
from dnd.monsters.bestiary import create_goblin as _create_goblin
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.area_conditions import AreaCondition, SpatialCondition
from dnd.spatial.environmental_conditions import (
    BurningWeb,
    ElectrifiedWater,
    FireSurface,
    IceSurface,
    OilSurface,
    SpikeTrap,
    SteamCloud,
    Wet,
    WetSurface,
    WetSurfaceMembership,
    materialize_spike_trap_condition,
)
from dnd.spatial.memberships import (
    MembershipAreaCondition,
    SpatialConditionMembershipSource,
)
from dnd.types.spatial_effects import (
    SpatialEffectBlockingPolicy,
    SpatialEffectAnchorKind,
    SpatialEffectChangeOperation,
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
)


def create_goblin(*args, **kwargs) -> Entity:
    """Create and explicitly deploy one goblin for spatial tests."""
    entity = _create_goblin(*args, **kwargs)
    entity.compose_entity()
    Game().deploy_entity(entity, entity.position)
    return entity


class _TestMembershipSource(SpatialConditionMembershipSource):
    """Test-only source lease for one public manifestation."""

    def create_manifestation(self, target: Entity) -> BaseCondition:
        return BaseCondition(
            name="Area Manifestation",
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
        )


class _TestMembershipArea(MembershipAreaCondition):
    """Test-only area using the generic source-membership seam."""

    def membership_source_class(
        self,
    ) -> type[SpatialConditionMembershipSource]:
        return _TestMembershipSource


class _FailingAreaCondition(AreaCondition):
    """Test-only incoming condition that fails after provisional mechanics."""

    def _apply(self, execution_event: Event):
        super()._apply(execution_event)
        raise RuntimeError("injected area activation failure")


def _content_ref(name: str) -> ContentRef:
    return ContentRef(
        pack_id="test.spatial",
        definition_kind=ContentDefinitionKind.CONDITION,
        content_id=f"condition.spatial.{name}",
        content_version=1,
        definition_contract_hash="0" * 64,
    )


def _cause(source_uuid: UUID) -> Event:
    return Event(
        name="Spatial condition test cause",
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.EFFECT,
        source_entity_uuid=source_uuid,
    )


def _publish_interaction(
    source_uuid: UUID,
    *,
    operation: SpatialEffectInteractionOperation,
    positions: set[tuple[int, int]],
    intensity: SpatialEffectInteractionIntensity = (
        SpatialEffectInteractionIntensity.MINOR
    ),
) -> SpatialEffectInteractionEvent:
    declaration = EventQueue.publish_declaration(
        SpatialEffectInteractionEvent(
            source_entity_uuid=source_uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
            operation=operation,
            positions=tuple(sorted(positions)),
            intensity=intensity,
        ),
    )
    execution = declaration.phase_to(EventPhase.EXECUTION)
    effect = execution.phase_to(EventPhase.EFFECT)
    completion = effect.phase_to(EventPhase.COMPLETION)
    assert isinstance(completion, SpatialEffectInteractionEvent)
    return completion


def _condition(
    source_uuid: UUID,
    *,
    name: str = "test_area",
    positions: set[tuple[int, int]],
    occupancy_policy: SpatialEffectOccupancyPolicy = (
        SpatialEffectOccupancyPolicy.OVERLAPPING
    ),
) -> SpatialCondition:
    return SpatialCondition(
        source_entity_uuid=source_uuid,
        content_ref=_content_ref(name),
        position=min(positions),
        affected_positions=positions,
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=occupancy_policy,
        blocking_policy=SpatialEffectBlockingPolicy.FOOTPRINT,
    )


def test_independent_condition_is_one_owner_across_every_covered_tile() -> None:
    """Activation exposes the same condition and mechanics across its footprint."""
    reset_engine_runtime(grid_size=(4, 1))
    source_uuid = uuid4()
    condition = _condition(
        source_uuid,
        positions={(0, 0), (1, 0), (2, 0)},
    )

    completion = condition.activate(parent_event=_cause(source_uuid))

    assert completion is not None
    assert completion.phase is EventPhase.COMPLETION
    assert condition.applied
    assert get_map().get_spatial_conditions() == [condition]
    for x in range(3):
        tile = get_map().get_tile(x, 0)
        assert tile is not None
        assert tile.get_conditions() == {condition.uuid: condition}
        assert not get_map().is_walkable_for(x, 0)

    assert condition.deactivate(parent_event=completion)
    assert get_map().get_spatial_conditions() == []
    assert not condition.applied
    for x in range(3):
        tile = get_map().get_tile(x, 0)
        assert tile is not None
        assert tile.get_conditions() == {}


def test_footprint_replacement_updates_retained_added_and_removed_tiles() -> None:
    """One footprint command changes Tile membership without duplicate state."""
    reset_engine_runtime(grid_size=(4, 1))
    source_uuid = uuid4()
    condition = _condition(
        source_uuid,
        positions={(0, 0), (1, 0)},
    )
    completion = condition.activate(parent_event=_cause(source_uuid))
    assert completion is not None

    assert condition.change_footprint(
        {(1, 0), (2, 0)},
        parent_event=completion,
    )

    tile_zero = get_map().get_tile(0, 0)
    tile_one = get_map().get_tile(1, 0)
    tile_two = get_map().get_tile(2, 0)
    assert tile_zero is not None and tile_zero.get_conditions() == {}
    assert tile_one is not None and tile_one.get_conditions() == {
        condition.uuid: condition,
    }
    assert tile_two is not None and tile_two.get_conditions() == {
        condition.uuid: condition,
    }
    assert condition.affected_positions == {(1, 0), (2, 0)}
    assert condition.deactivate(parent_event=completion)


def test_area_condition_moves_terrain_and_light_with_one_footprint() -> None:
    """Area mechanics follow exact removed, retained, and added cells."""
    reset_engine_runtime(grid_size=(4, 1))
    source_uuid = uuid4()
    condition = AreaCondition(
        name="Moving Area",
        source_entity_uuid=source_uuid,
        content_ref=_content_ref("moving_area"),
        position=(0, 0),
        affected_positions={(0, 0), (1, 0)},
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        adds_difficult_terrain=True,
        sets_light_level=LightLevel.DARKNESS,
        light_is_cap=True,
    )

    completion = condition.activate(parent_event=_cause(source_uuid))

    assert completion is not None
    for x in (0, 1):
        tile = get_map().get_tile(x, 0)
        assert tile is not None
        assert tile.get_movement_cost(MovementMode.WALKING) == 2
        assert tile.resolved_light_level is LightLevel.DARKNESS

    assert condition.change_footprint(
        {(1, 0), (2, 0)},
        parent_event=completion,
    )
    old_tile = get_map().get_tile(0, 0)
    retained_tile = get_map().get_tile(1, 0)
    added_tile = get_map().get_tile(2, 0)
    assert old_tile is not None
    assert retained_tile is not None
    assert added_tile is not None
    assert old_tile.get_movement_cost(MovementMode.WALKING) == 1
    assert old_tile.resolved_light_level is LightLevel.BRIGHT_LIGHT
    assert retained_tile.get_movement_cost(MovementMode.WALKING) == 2
    assert retained_tile.resolved_light_level is LightLevel.DARKNESS
    assert added_tile.get_movement_cost(MovementMode.WALKING) == 2
    assert added_tile.resolved_light_level is LightLevel.DARKNESS

    assert condition.deactivate(parent_event=completion)
    for x in (1, 2):
        tile = get_map().get_tile(x, 0)
        assert tile is not None
        assert tile.get_movement_cost(MovementMode.WALKING) == 1
        assert tile.resolved_light_level is LightLevel.BRIGHT_LIGHT


def test_entity_anchored_area_translates_from_committed_movement() -> None:
    """An attached area follows its entity through the existing event path."""
    reset_engine_runtime(grid_size=(5, 1))
    anchor = create_goblin(name="Area Anchor", position=(1, 0))
    cause = _cause(anchor.uuid)
    condition = AreaCondition(
        name="Attached Area",
        source_entity_uuid=anchor.uuid,
        content_ref=_content_ref("attached_area"),
        position=(1, 0),
        affected_positions={(1, 0), (2, 0)},
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        anchor_kind=SpatialEffectAnchorKind.ENTITY,
        anchor_uuid=anchor.uuid,
    )
    completion = condition.activate(parent_event=cause)
    assert completion is not None
    assert len(condition.event_handlers_uuids) == 1

    Entity.update_entity_position(
        anchor,
        (2, 0),
        parent_event=cause.uuid,
    )

    assert condition.position == (2, 0)
    assert condition.affected_positions == {(2, 0), (3, 0)}
    assert get_map().get_tile(1, 0).get_conditions() == {}
    assert get_map().get_tile(3, 0).get_conditions() == {
        condition.uuid: condition,
    }
    assert condition.deactivate(parent_event=completion)


def test_area_membership_is_source_owned_across_entry_exit_and_removal() -> None:
    """Creature state remains a child of its exact independent area owner."""
    reset_engine_runtime(grid_size=(3, 1))
    occupant = create_goblin(name="Area Occupant", position=(0, 0))
    cause = _cause(occupant.uuid)
    condition = _TestMembershipArea(
        name="Membership Area",
        source_entity_uuid=occupant.uuid,
        content_ref=_content_ref("membership_area"),
        position=(0, 0),
        affected_positions={(0, 0), (1, 0)},
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.LEAVE,
        }),
        membership_trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
        }),
    )

    cursor = EventQueue.event_cursor()
    completion = condition.activate(parent_event=cause)

    assert completion is not None
    membership = condition.find_membership(occupant)
    assert isinstance(membership, _TestMembershipSource)
    manifestations = [
        active
        for active in occupant.active_conditions_by_uuid.values()
        if active.name == "Area Manifestation"
    ]
    assert len(manifestations) == 1
    assert manifestations[0].parent_condition == membership.uuid
    activation_events = [
        event for _, event in EventQueue.iter_events_since(cursor)
    ]
    created_effect = next(
        event
        for event in activation_events
        if event.event_type is EventType.SPATIAL_EFFECT_CHANGED
        and event.spatial_effect_uuid == condition.uuid
        and event.operation is SpatialEffectChangeOperation.CREATED
        and event.phase is EventPhase.EFFECT
    )
    membership_declaration = next(
        event
        for event in activation_events
        if event.event_type is EventType.CONDITION_APPLICATION
        and event.condition is membership
        and event.phase is EventPhase.DECLARATION
    )
    membership_terminal = next(
        index
        for index, event in enumerate(activation_events)
        if event.event_type is EventType.CONDITION_APPLICATION
        and event.condition is membership
        and event.phase is EventPhase.COMPLETION
    )
    created_terminal = next(
        index
        for index, event in enumerate(activation_events)
        if event.event_type is EventType.SPATIAL_EFFECT_CHANGED
        and event.spatial_effect_uuid == condition.uuid
        and event.operation is SpatialEffectChangeOperation.CREATED
        and event.phase is EventPhase.COMPLETION
    )
    root_terminal = next(
        index
        for index, event in enumerate(activation_events)
        if event.uuid == completion.uuid
    )
    assert membership_declaration.parent_event == created_effect.uuid
    assert membership_terminal < created_terminal < root_terminal

    Entity.update_entity_position(
        occupant,
        (1, 0),
        parent_event=cause.uuid,
    )
    assert condition.find_membership(occupant) is membership

    Entity.update_entity_position(
        occupant,
        (2, 0),
        parent_event=cause.uuid,
    )
    assert condition.find_membership(occupant) is None
    assert all(
        active.name != "Area Manifestation"
        for active in occupant.active_conditions_by_uuid.values()
    )

    Entity.update_entity_position(
        occupant,
        (0, 0),
        parent_event=cause.uuid,
    )
    assert condition.find_membership(occupant) is not None
    assert condition.deactivate(parent_event=completion)
    assert condition.find_membership(occupant) is None
    assert occupant.active_conditions_by_uuid == {}


def test_invalid_or_exclusive_footprints_do_not_partially_mutate_world() -> None:
    """Admission rejects bad cells and occupied exclusive layers atomically."""
    reset_engine_runtime(grid_size=(2, 1))
    source_uuid = uuid4()
    incumbent = _condition(
        source_uuid,
        name="exclusive_a",
        positions={(0, 0)},
        occupancy_policy=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
    )
    incumbent_completion = incumbent.activate(parent_event=_cause(source_uuid))
    assert incumbent_completion is not None

    incoming = _condition(
        source_uuid,
        name="exclusive_b",
        positions={(0, 0), (1, 0)},
        occupancy_policy=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
    )
    with pytest.raises(ValueError, match="authored material transformation"):
        incoming.activate(parent_event=_cause(source_uuid))

    assert get_map().get_spatial_conditions() == [incumbent]
    assert incoming.affected_positions == set()
    tile_one = get_map().get_tile(1, 0)
    assert tile_one is not None and tile_one.get_conditions() == {}

    incumbent.duration.duration_type = DurationType.ROUNDS
    incumbent.duration.duration = 1
    assert incumbent.progress_spatial_duration(parent_event=incumbent_completion)
    assert get_map().get_spatial_conditions() == []


def test_matching_exclusive_conditions_arbitrate_and_transfer_exact_cells() -> None:
    """A stronger matching condition owns overlap without duplicate mechanics."""
    reset_engine_runtime(grid_size=(3, 1))
    source_uuid = uuid4()
    content_ref = _content_ref("exclusive_material")
    incumbent = AreaCondition(
        name="Incumbent Material",
        source_entity_uuid=source_uuid,
        content_ref=content_ref,
        position=(0, 0),
        affected_positions={(0, 0), (1, 0)},
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
        arbitration_potency=1,
        adds_difficult_terrain=True,
    )
    incumbent_completion = incumbent.activate(parent_event=_cause(source_uuid))
    assert incumbent_completion is not None

    incoming = AreaCondition(
        name="Stronger Material",
        source_entity_uuid=source_uuid,
        content_ref=content_ref,
        position=(1, 0),
        affected_positions={(1, 0), (2, 0)},
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
        arbitration_potency=2,
        adds_difficult_terrain=True,
    )
    incoming_completion = incoming.activate(parent_event=_cause(source_uuid))

    assert incoming_completion is not None
    assert incumbent.affected_positions == {(0, 0)}
    assert incoming.affected_positions == {(1, 0), (2, 0)}
    for x, owner in ((0, incumbent), (1, incoming), (2, incoming)):
        tile = get_map().get_tile(x, 0)
        assert tile is not None
        assert tile.get_conditions() == {owner.uuid: owner}
        assert tile.get_movement_cost(MovementMode.WALKING) == 2


def test_failed_authorized_replacement_restores_incumbent_world_state() -> None:
    """A failed incoming application leaves the installed condition untouched."""
    reset_engine_runtime(grid_size=(2, 1))
    source_uuid = uuid4()
    incumbent = AreaCondition(
        name="Oil-like Material",
        source_entity_uuid=source_uuid,
        content_ref=_content_ref("incumbent_material"),
        position=(0, 0),
        affected_positions={(0, 0), (1, 0)},
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
        adds_difficult_terrain=True,
    )
    incumbent_completion = incumbent.activate(parent_event=_cause(source_uuid))
    assert incumbent_completion is not None

    incoming = _FailingAreaCondition(
        name="Failed Replacement",
        source_entity_uuid=source_uuid,
        content_ref=_content_ref("replacement_material"),
        position=(0, 0),
        affected_positions={(0, 0), (1, 0)},
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
        adds_difficult_terrain=True,
    )
    with pytest.raises(RuntimeError, match="injected area activation failure"):
        incoming.activate(
            parent_event=_cause(source_uuid),
            replacing_condition_uuid=incumbent.uuid,
        )

    assert get_map().get_spatial_conditions() == [incumbent]
    assert incumbent.affected_positions == {(0, 0), (1, 0)}
    assert BaseCondition.get(incoming.uuid) is None
    for x in range(2):
        tile = get_map().get_tile(x, 0)
        assert tile is not None
        assert tile.get_conditions() == {incumbent.uuid: incumbent}
        assert tile.get_movement_cost(MovementMode.WALKING) == 2


def test_authorized_replacement_retires_complete_incumbent() -> None:
    """A successful authored replacement removes the old condition exactly once."""
    reset_engine_runtime(grid_size=(1, 1))
    source_uuid = uuid4()
    incumbent = _condition(
        source_uuid,
        name="replace_from",
        positions={(0, 0)},
        occupancy_policy=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
    )
    incumbent_completion = incumbent.activate(parent_event=_cause(source_uuid))
    assert incumbent_completion is not None
    incoming = _condition(
        source_uuid,
        name="replace_to",
        positions={(0, 0)},
        occupancy_policy=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
    )

    incoming_completion = incoming.activate(
        parent_event=_cause(source_uuid),
        replacing_condition_uuid=incumbent.uuid,
    )

    assert incoming_completion is not None
    assert not incumbent.applied
    assert BaseCondition.get(incumbent.uuid) is None
    assert get_map().get_spatial_conditions() == [incoming]
    tile = get_map().get_tile(0, 0)
    assert tile is not None
    assert tile.get_conditions() == {incoming.uuid: incoming}


def test_fire_surface_reacts_directly_to_partial_and_complete_dousing() -> None:
    """The live interaction event shrinks and then retires one fire owner."""
    reset_engine_runtime(grid_size=(3, 1))
    source_uuid = uuid4()
    fire = FireSurface(
        source_entity_uuid=source_uuid,
        position=(0, 0),
        affected_positions={(0, 0), (1, 0)},
    )
    completion = fire.activate(parent_event=_cause(source_uuid))
    assert completion is not None
    assert len(fire.spatial_handler_uuids) == 2

    _publish_interaction(
        source_uuid,
        operation=SpatialEffectInteractionOperation.DOUSE,
        positions={(1, 0), (2, 0)},
    )

    assert fire.applied
    assert fire.affected_positions == {(0, 0)}
    assert get_map().get_spatial_conditions_at((1, 0)) == []
    _publish_interaction(
        source_uuid,
        operation=SpatialEffectInteractionOperation.DOUSE,
        positions={(1, 0)},
    )
    assert fire.applied

    _publish_interaction(
        source_uuid,
        operation=SpatialEffectInteractionOperation.DOUSE,
        positions={(0, 0)},
    )

    assert not fire.applied
    assert BaseCondition.get(fire.uuid) is None
    assert get_map().get_spatial_conditions() == []


def test_oil_ignition_replaces_exact_cells_with_authored_fire() -> None:
    """A live ignition event transfers only intersecting oil cells to fire."""
    reset_engine_runtime(grid_size=(2, 1))
    oil_source_uuid = uuid4()
    ignition_source_uuid = uuid4()
    oil = OilSurface(
        source_entity_uuid=oil_source_uuid,
        faction="hazards",
        position=(0, 0),
        affected_positions={(0, 0), (1, 0)},
    )
    completion = oil.activate(parent_event=_cause(oil_source_uuid))
    assert completion is not None

    _publish_interaction(
        ignition_source_uuid,
        operation=SpatialEffectInteractionOperation.IGNITE,
        positions={(1, 0)},
    )

    assert oil.applied
    assert oil.affected_positions == {(0, 0)}
    fires = [
        condition
        for condition in get_map().get_spatial_conditions()
        if isinstance(condition, FireSurface)
    ]
    assert len(fires) == 1
    fire = fires[0]
    assert fire.source_entity_uuid == ignition_source_uuid
    assert fire.faction == "hazards"
    assert fire.position == (1, 0)
    assert fire.affected_positions == {(1, 0)}
    assert fire.duration.duration == 3
    assert get_map().get_spatial_conditions_at((0, 0)) == [oil]
    assert get_map().get_spatial_conditions_at((1, 0)) == [fire]
    tile_zero = get_map().get_tile(0, 0)
    tile_one = get_map().get_tile(1, 0)
    assert tile_zero is not None and tile_one is not None
    assert tile_zero.get_movement_cost(MovementMode.WALKING) == 2
    assert tile_one.get_movement_cost(MovementMode.WALKING) == 1


def test_block_owned_parent_retires_independent_spatial_child_before_terminal() -> None:
    """An ordinary dependency uses the spatial condition's exact owner path."""
    reset_engine_runtime(grid_size=(2, 1))
    source_uuid = uuid4()
    owner = BaseBlock(
        source_entity_uuid=source_uuid,
        allow_events_conditions=True,
    )
    parent = BaseCondition(
        name="Spatial Parent",
        source_entity_uuid=source_uuid,
        target_entity_uuid=owner.uuid,
    )
    parent_completion = owner.add_condition(
        parent,
        parent_event=_cause(source_uuid),
    )
    assert parent_completion is not None

    child = _condition(source_uuid, positions={(0, 0), (1, 0)})
    child_completion = child.activate(parent_event=parent_completion)
    assert child_completion is not None
    parent.add_linked_condition(child.uuid, child.uuid)

    cursor = EventQueue.event_cursor()
    assert owner.remove_condition(
        parent.name,
        parent_event=child_completion,
    )

    events = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
    ]
    parent_effect = next(
        event
        for event in events
        if event.event_type is EventType.CONDITION_REMOVAL
        if event.condition is parent and event.phase is EventPhase.EFFECT
    )
    spatial_effect = next(
        event
        for event in events
        if event.event_type is EventType.SPATIAL_EFFECT_CHANGED
        and event.spatial_effect_uuid == child.uuid
        and event.operation is SpatialEffectChangeOperation.REMOVED
        and event.phase is EventPhase.EFFECT
    )
    child_declaration = next(
        event
        for event in events
        if event.event_type is EventType.CONDITION_REMOVAL
        if event.condition is child and event.phase is EventPhase.DECLARATION
    )
    child_terminal = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is child
        and event.phase is EventPhase.COMPLETION
    )
    spatial_terminal = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.SPATIAL_EFFECT_CHANGED
        and event.spatial_effect_uuid == child.uuid
        and event.operation is SpatialEffectChangeOperation.REMOVED
        and event.phase is EventPhase.COMPLETION
    )
    parent_terminal = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is parent
        and event.phase is EventPhase.COMPLETION
    )
    child_effect = next(
        event
        for event in events
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is child
        and event.phase is EventPhase.EFFECT
    )
    assert child_declaration.parent_event == parent_effect.uuid
    assert spatial_effect.parent_event == child_effect.uuid
    assert spatial_terminal < child_terminal < parent_terminal
    assert BaseCondition.get(child.uuid) is None
    assert get_map().get_spatial_conditions() == []


def test_spatial_parent_retires_block_owned_child_before_terminal() -> None:
    """SpatialCondition locally owns cross-block descendant cleanup."""
    reset_engine_runtime(grid_size=(2, 1))
    source_uuid = uuid4()
    child_owner = BaseBlock(
        source_entity_uuid=source_uuid,
        allow_events_conditions=True,
    )
    child = BaseCondition(
        name="Spatial Membership",
        source_entity_uuid=source_uuid,
        target_entity_uuid=child_owner.uuid,
    )
    child_completion = child_owner.add_condition(
        child,
        parent_event=_cause(source_uuid),
    )
    assert child_completion is not None

    parent = _condition(source_uuid, positions={(0, 0), (1, 0)})
    parent_completion = parent.activate(parent_event=child_completion)
    assert parent_completion is not None
    parent.add_linked_condition(child_owner.uuid, child.uuid)

    cursor = EventQueue.event_cursor()
    assert parent.deactivate(parent_event=parent_completion)

    events = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
    ]
    parent_effect = next(
        event
        for event in events
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is parent
        and event.phase is EventPhase.EFFECT
    )
    spatial_effect = next(
        event
        for event in events
        if event.event_type is EventType.SPATIAL_EFFECT_CHANGED
        and event.spatial_effect_uuid == parent.uuid
        and event.operation is SpatialEffectChangeOperation.REMOVED
        and event.phase is EventPhase.EFFECT
    )
    child_declaration = next(
        event
        for event in events
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is child
        and event.phase is EventPhase.DECLARATION
    )
    child_terminal = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is child
        and event.phase is EventPhase.COMPLETION
    )
    spatial_terminal = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.SPATIAL_EFFECT_CHANGED
        and event.spatial_effect_uuid == parent.uuid
        and event.operation is SpatialEffectChangeOperation.REMOVED
        and event.phase is EventPhase.COMPLETION
    )
    parent_terminal = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is parent
        and event.phase is EventPhase.COMPLETION
    )
    assert spatial_effect.parent_event == parent_effect.uuid
    assert child_declaration.parent_event == spatial_effect.uuid
    assert child_terminal < spatial_terminal < parent_terminal
    assert child_owner.active_conditions == {}
    assert get_map().get_spatial_conditions() == []


def test_removing_linked_child_retires_spatial_parent_with_any_policy() -> None:
    """A child's accepted removal directly causes its spatial parent cleanup."""
    reset_engine_runtime(grid_size=(2, 1))
    source_uuid = uuid4()
    cause = _cause(source_uuid)
    parent = _condition(source_uuid, positions={(0, 0), (1, 0)})
    parent.child_removal_policy = "any"
    assert parent.activate(parent_event=cause) is not None

    owner = BaseBlock(
        source_entity_uuid=source_uuid,
        allow_events_conditions=True,
    )
    child = BaseCondition(
        name="Any-policy spatial child",
        source_entity_uuid=source_uuid,
        target_entity_uuid=owner.uuid,
    )
    assert owner.add_condition(child, parent_event=cause) is not None
    parent.add_linked_condition(owner.uuid, child.uuid)

    cursor = EventQueue.event_cursor()
    assert owner.remove_condition(child.name, parent_event=cause)
    events = [event for _, event in EventQueue.iter_events_since(cursor)]

    child_effect = next(
        event
        for event in events
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is child
        and event.phase is EventPhase.EFFECT
    )
    parent_declaration = next(
        event
        for event in events
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is parent
        and event.phase is EventPhase.DECLARATION
    )
    parent_effect = next(
        event
        for event in events
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is parent
        and event.phase is EventPhase.EFFECT
    )
    spatial_effect = next(
        event
        for event in events
        if event.event_type is EventType.SPATIAL_EFFECT_CHANGED
        and event.spatial_effect_uuid == parent.uuid
        and event.operation is SpatialEffectChangeOperation.REMOVED
        and event.phase is EventPhase.EFFECT
    )
    spatial_terminal = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.SPATIAL_EFFECT_CHANGED
        and event.spatial_effect_uuid == parent.uuid
        and event.operation is SpatialEffectChangeOperation.REMOVED
        and event.phase is EventPhase.COMPLETION
    )
    parent_terminal = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is parent
        and event.phase is EventPhase.COMPLETION
    )
    child_terminal = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is child
        and event.phase is EventPhase.COMPLETION
    )

    assert parent_declaration.parent_event == child_effect.uuid
    assert spatial_effect.parent_event == parent_effect.uuid
    assert spatial_terminal < parent_terminal < child_terminal
    assert owner.active_conditions == {}
    assert get_map().get_spatial_conditions() == []


def test_removing_last_linked_child_retires_spatial_parent_with_last_policy() -> None:
    """A last-child policy keeps the field until its final child is removed."""
    reset_engine_runtime(grid_size=(2, 1))
    source_uuid = uuid4()
    cause = _cause(source_uuid)
    parent = _condition(source_uuid, positions={(0, 0), (1, 0)})
    parent.child_removal_policy = "last"
    assert parent.activate(parent_event=cause) is not None

    owners = [
        BaseBlock(source_entity_uuid=source_uuid, allow_events_conditions=True)
        for _ in range(2)
    ]
    children = [
        BaseCondition(
            name=f"Last-policy spatial child {index}",
            source_entity_uuid=source_uuid,
            target_entity_uuid=owner.uuid,
        )
        for index, owner in enumerate(owners)
    ]
    for owner, child in zip(owners, children):
        assert owner.add_condition(child, parent_event=cause) is not None
        parent.add_linked_condition(owner.uuid, child.uuid)

    assert owners[0].remove_condition(children[0].name, parent_event=cause)
    assert parent.applied
    assert get_map().get_spatial_condition(parent.uuid) is parent
    assert parent.linked_conditions == [(owners[1].uuid, children[1].uuid)]

    cursor = EventQueue.event_cursor()
    assert owners[1].remove_condition(children[1].name, parent_event=cause)
    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    child_effect = next(
        event
        for event in events
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is children[1]
        and event.phase is EventPhase.EFFECT
    )
    parent_declaration = next(
        event
        for event in events
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is parent
        and event.phase is EventPhase.DECLARATION
    )
    spatial_terminal = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.SPATIAL_EFFECT_CHANGED
        and event.spatial_effect_uuid == parent.uuid
        and event.operation is SpatialEffectChangeOperation.REMOVED
        and event.phase is EventPhase.COMPLETION
    )
    child_terminal = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is children[1]
        and event.phase is EventPhase.COMPLETION
    )

    assert parent_declaration.parent_event == child_effect.uuid
    assert spatial_terminal < child_terminal
    assert get_map().get_spatial_conditions() == []
    assert all(owner.active_conditions == {} for owner in owners)


def test_spatial_child_veto_preserves_the_entire_owned_graph() -> None:
    """A vetoed descendant leaves the field, children, and links unchanged."""
    reset_engine_runtime(grid_size=(2, 1))
    source_uuid = uuid4()
    parent = _condition(source_uuid, positions={(0, 0), (1, 0)})
    cause = _cause(source_uuid)
    assert parent.activate(parent_event=cause) is not None
    owners = [
        BaseBlock(source_entity_uuid=source_uuid, allow_events_conditions=True)
        for _ in range(2)
    ]
    children = [
        BaseCondition(
            name=f"Spatial child {index}",
            source_entity_uuid=source_uuid,
            target_entity_uuid=owner.uuid,
        )
        for index, owner in enumerate(owners)
    ]
    for owner, child in zip(owners, children):
        assert owner.add_condition(child, parent_event=cause) is not None
        parent.add_linked_condition(owner.uuid, child.uuid)

    def veto_second_child(event: Event, _source_uuid: UUID) -> Event:
        return event.cancel("second child remains active")

    owners[1].add_event_handler(EventHandler(
        name="Keep second spatial child",
        source_entity_uuid=owners[1].uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.CONDITION_REMOVAL,
            event_phase=EventPhase.DECLARATION,
            event_target_entity_uuid=owners[1].uuid,
        )],
        event_processor=veto_second_child,
    ))
    original_links = list(parent.linked_conditions)
    original_positions = set(parent.affected_positions)

    assert not parent.deactivate(parent_event=cause)
    assert parent.applied
    assert get_map().get_spatial_condition(parent.uuid) is parent
    assert parent.affected_positions == original_positions
    assert parent.linked_conditions == original_links
    assert all(child.applied for child in children)
    assert all(
        owner.active_conditions_by_uuid[child.uuid] is child
        for owner, child in zip(owners, children)
    )


def test_multi_slot_concentration_veto_preserves_slot_and_spatial_children() -> None:
    """Dropping one slot is atomic across its zone and all owned descendants."""
    reset_engine_runtime(grid_size=(4, 1))
    caster = create_goblin(name="Two-slot caster", position=(0, 0))
    cause = _cause(caster.uuid)
    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="First Field",
    )
    assert caster.add_condition(concentration, parent_event=cause) is not None
    first_slot = concentration.get_slot_by_spell_name("First Field")
    assert first_slot is not None
    first_zone = _condition(caster.uuid, positions={(1, 0)})
    assert first_zone.activate(parent_event=cause) is not None
    concentration.add_linked_condition(first_zone.uuid, first_zone.uuid)
    second_slot = concentration.add_slot("Second Field")
    second_zone = _condition(caster.uuid, positions={(2, 0)})
    assert second_zone.activate(parent_event=cause) is not None
    concentration.add_linked_condition(second_zone.uuid, second_zone.uuid)

    owners = [
        BaseBlock(source_entity_uuid=caster.uuid, allow_events_conditions=True)
        for _ in range(2)
    ]
    children = [
        BaseCondition(
            name=f"Slot child {index}",
            source_entity_uuid=caster.uuid,
            target_entity_uuid=owner.uuid,
        )
        for index, owner in enumerate(owners)
    ]
    for owner, child in zip(owners, children):
        assert owner.add_condition(child, parent_event=cause) is not None
        first_zone.add_linked_condition(owner.uuid, child.uuid)

    def veto_second_child(event: Event, _source_uuid: UUID) -> Event:
        return event.cancel("slot child remains active")

    owners[1].add_event_handler(EventHandler(
        name="Keep second slot child",
        source_entity_uuid=owners[1].uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.CONDITION_REMOVAL,
            event_phase=EventPhase.DECLARATION,
            event_target_entity_uuid=owners[1].uuid,
        )],
        event_processor=veto_second_child,
    ))
    original_links = list(concentration.linked_conditions)
    original_first_links = list(first_zone.linked_conditions)

    assert not concentration.drop_slot(first_slot, parent_event=cause)
    assert set(concentration.concentration_slots) == {first_slot, second_slot}
    assert concentration.linked_conditions == original_links
    assert first_zone.linked_conditions == original_first_links
    assert get_map().get_spatial_condition(first_zone.uuid) is first_zone
    assert get_map().get_spatial_condition(second_zone.uuid) is second_zone
    assert all(child.applied for child in children)


def test_spike_trap_uses_one_handler_reveals_once_and_extends_by_identity() -> None:
    """SpikeTrap is one persistent owner, not one marker per covered Tile."""
    reset_engine_runtime(grid_size=(4, 1))
    source_uuid = uuid4()
    cause = _cause(source_uuid)
    trap = SpikeTrap(
        source_entity_uuid=source_uuid,
        position=(1, 0),
        affected_positions={(1, 0), (2, 0)},
        condition_stealth_dc=15,
    )

    activation = trap.activate(parent_event=cause)

    assert activation is not None
    assert len(trap.spatial_handler_uuids) == 1
    handler_uuid = trap.spatial_handler_uuids[0]
    registration = EventQueue.get_spatial_handler_registration(handler_uuid)
    assert registration is not None
    assert registration[1] == frozenset({(1, 0), (2, 0)})
    assert get_map().get_tile(1, 0).get_conditions() == {trap.uuid: trap}
    assert get_map().get_tile(2, 0).get_conditions() == {trap.uuid: trap}

    mover = create_goblin(name="Trap Target", position=(0, 0))
    hp_before = mover.get_hp()
    cursor = EventQueue.event_cursor()

    with fixed_dice_faces(1, 1):
        Entity.update_entity_position(
            mover,
            (1, 0),
            parent_event=cause.uuid,
        )

    assert mover.get_hp() == hp_before - 2
    assert trap.condition_stealth_dc is None
    reveals = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type is EventType.SPATIAL_EFFECT_CHANGED
        and event.operation is SpatialEffectChangeOperation.REVEALED
        and event.spatial_effect_uuid == trap.uuid
        and event.phase is EventPhase.COMPLETION
    ]
    assert len(reveals) == 1

    with fixed_dice_faces(1, 1):
        Entity.update_entity_position(
            mover,
            (2, 0),
            parent_event=cause.uuid,
        )
    assert mover.get_hp() == hp_before - 4
    assert len([
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type is EventType.SPATIAL_EFFECT_CHANGED
        and event.operation is SpatialEffectChangeOperation.REVEALED
        and event.spatial_effect_uuid == trap.uuid
        and event.phase is EventPhase.COMPLETION
    ]) == 1

    assert trap.extend_footprint({(3, 0)}, parent_event=activation)
    registration = EventQueue.get_spatial_handler_registration(handler_uuid)
    assert registration is not None
    assert registration[1] == frozenset({(1, 0), (2, 0), (3, 0)})
    assert get_map().get_tile(3, 0).get_conditions() == {trap.uuid: trap}

    assert trap.deactivate(parent_event=activation)
    assert EventQueue.get_spatial_handler_registration(handler_uuid) is None
    assert get_map().get_spatial_conditions() == []


def test_pull_lever_targets_one_spike_condition_identity() -> None:
    """A lever removes its linked network without handler or Tile bookkeeping."""
    reset_engine_runtime(grid_size=(4, 1))
    linked = materialize_spike_trap_condition({(1, 0)})
    unrelated = materialize_spike_trap_condition({(3, 0)})
    actor = create_goblin(name="Lever User", position=(0, 0))
    cursor = EventQueue.event_cursor()

    result = PullLeverAction(
        source_entity_uuid=actor.uuid,
        target_entity_uuid=actor.uuid,
        trap_condition_uuid=linked.uuid,
    ).apply()

    assert result is not None
    assert result.phase is EventPhase.COMPLETION
    assert not linked.applied
    assert unrelated.applied
    assert get_map().get_spatial_conditions() == [unrelated]
    linked_tile = get_map().get_tile(1, 0)
    unrelated_tile = get_map().get_tile(3, 0)
    assert linked_tile is not None and linked_tile.get_conditions() == {}
    assert unrelated_tile is not None and unrelated_tile.get_conditions() == {
        unrelated.uuid: unrelated,
    }

    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    removal_terminal_index = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.condition is linked
        and event.phase is EventPhase.COMPLETION
    )
    action_terminal_index = next(
        index
        for index, event in enumerate(events)
        if event.uuid == result.uuid
    )
    assert removal_terminal_index < action_terminal_index


def test_oil_barrel_destruction_uses_direct_material_transition() -> None:
    """The authored barrel spills Oil and fire damage transforms that Oil."""
    reset_engine_runtime(grid_size=(4, 2))
    source_uuid = uuid4()
    mundane = build_oil_barrel(source_uuid)
    burning = build_oil_barrel(source_uuid)
    mundane.place_on_grid((1, 0))
    burning.place_on_grid((2, 0))
    cursor = EventQueue.event_cursor()

    mundane.receive_damage(20, DamageType.BLUDGEONING, source_uuid)
    burning.receive_damage(20, DamageType.FIRE, source_uuid)

    mundane_conditions = get_map().get_spatial_conditions_at((1, 0))
    burning_conditions = get_map().get_spatial_conditions_at((2, 0))
    assert len(mundane_conditions) == 1
    assert isinstance(mundane_conditions[0], OilSurface)
    assert len(burning_conditions) == 1
    assert isinstance(burning_conditions[0], FireSurface)

    emitted = [event for _, event in EventQueue.iter_events_since(cursor)]
    damage_effects = [
        event
        for event in emitted
        if isinstance(event, TakeDamageEvent)
        and event.phase is EventPhase.EFFECT
    ]
    interaction_phases = [
        event.phase
        for event in emitted
        if isinstance(event, SpatialEffectInteractionEvent)
        and event.source_object_uuid == burning.uuid
    ]
    assert len(damage_effects) == 2
    assert interaction_phases == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]


def test_overlapping_wet_sources_share_one_manifestation_until_last_release() -> None:
    """Exact source leases sustain one public Wet manifestation."""
    reset_engine_runtime(grid_size=(3, 3))
    target = create_goblin(name="Wet target", position=(1, 1))
    cause = _cause(target.uuid)
    surface = WetSurface(
        source_entity_uuid=target.uuid,
        position=(1, 1),
        affected_positions={(1, 1)},
    )
    steam = SteamCloud(
        source_entity_uuid=target.uuid,
        position=(1, 1),
        affected_positions={(1, 1)},
    )

    surface.activate(parent_event=cause)
    steam.activate(parent_event=cause)

    wet_conditions = [
        condition
        for condition in target.active_conditions_by_uuid.values()
        if isinstance(condition, Wet)
    ]
    wet_memberships = [
        condition
        for condition in target.active_conditions_by_uuid.values()
        if isinstance(condition, WetSurfaceMembership)
    ]
    assert len(wet_conditions) == 1
    assert {
        membership.source_spatial_condition_uuid
        for membership in wet_memberships
    } == {surface.uuid, steam.uuid}
    assert target.health.get_resistance(DamageType.FIRE) is (
        ResistanceStatus.RESISTANCE
    )
    assert target.health.get_resistance(DamageType.COLD) is (
        ResistanceStatus.VULNERABILITY
    )
    assert target.health.get_resistance(DamageType.LIGHTNING) is (
        ResistanceStatus.VULNERABILITY
    )

    assert surface.deactivate(parent_event=cause)
    assert len([
        condition
        for condition in target.active_conditions_by_uuid.values()
        if isinstance(condition, Wet)
    ]) == 1
    assert [
        condition.source_spatial_condition_uuid
        for condition in target.active_conditions_by_uuid.values()
        if isinstance(condition, WetSurfaceMembership)
    ] == [steam.uuid]
    assert target.health.get_resistance(DamageType.FIRE) is (
        ResistanceStatus.RESISTANCE
    )

    assert steam.deactivate(parent_event=cause)
    assert not any(
        isinstance(condition, Wet)
        for condition in target.active_conditions_by_uuid.values()
    )
    assert target.health.get_resistance(DamageType.FIRE) is ResistanceStatus.NONE


def test_wet_material_transitions_preserve_exact_cells() -> None:
    """Wet replacements and secondary clouds stay local to selected cells."""
    reset_engine_runtime(grid_size=(5, 3))
    source_uuid = uuid4()
    cause = _cause(source_uuid)
    wet = WetSurface(
        source_entity_uuid=source_uuid,
        position=(1, 1),
        affected_positions={(1, 1), (2, 1), (3, 1), (4, 1)},
    )
    wet.activate(parent_event=cause)

    _publish_interaction(
        source_uuid,
        operation=SpatialEffectInteractionOperation.FREEZE,
        positions={(1, 1)},
    )

    _publish_interaction(
        source_uuid,
        operation=SpatialEffectInteractionOperation.ELECTRIFY,
        positions={(2, 1)},
    )
    _publish_interaction(
        source_uuid,
        operation=SpatialEffectInteractionOperation.VAPORIZE,
        positions={(3, 1)},
    )

    assert wet.affected_positions == {(4, 1)}
    frozen = get_map().get_spatial_conditions_at((1, 1))
    assert len(frozen) == 1 and isinstance(frozen[0], IceSurface)
    electrified = get_map().get_spatial_conditions_at((2, 1))
    assert len(electrified) == 1
    assert isinstance(electrified[0], ElectrifiedWater)
    first_steam = get_map().get_spatial_conditions_at((3, 1))
    assert len(first_steam) == 1 and isinstance(first_steam[0], SteamCloud)

    _publish_interaction(
        source_uuid,
        operation=SpatialEffectInteractionOperation.VAPORIZE,
        positions={(1, 1)},
    )
    _publish_interaction(
        source_uuid,
        operation=SpatialEffectInteractionOperation.VAPORIZE,
        positions={(2, 1)},
    )

    for position in ((1, 1), (2, 1), (3, 1)):
        vaporized = get_map().get_spatial_conditions_at(position)
        assert len(vaporized) == 1
        assert isinstance(vaporized[0], SteamCloud)
    assert get_map().get_spatial_conditions_at((4, 1)) == [wet]


def test_electrified_water_appearance_wets_damages_and_freezes() -> None:
    """Appearance mechanics settle before the material can transform."""
    reset_engine_runtime(grid_size=(3, 3))
    target = create_goblin(name="Conductive target", position=(1, 1))
    cause = _cause(target.uuid)
    water = ElectrifiedWater(
        source_entity_uuid=target.uuid,
        position=(1, 1),
        affected_positions={(1, 1)},
    )
    hp_before = target.get_hp()

    with fixed_dice_faces(1):
        water.activate(parent_event=cause)

    assert target.get_hp() == hp_before - 2
    assert any(
        isinstance(condition, Wet)
        for condition in target.active_conditions_by_uuid.values()
    )

    _publish_interaction(
        target.uuid,
        operation=SpatialEffectInteractionOperation.FREEZE,
        positions={(1, 1)},
    )

    conditions = get_map().get_spatial_conditions_at((1, 1))
    assert len(conditions) == 1 and isinstance(conditions[0], IceSurface)
    assert not any(
        isinstance(condition, Wet)
        for condition in target.active_conditions_by_uuid.values()
    )


def test_ice_appearance_and_burning_web_dousing_use_direct_conditions() -> None:
    """APPEAR and dousing execute without hosts or controller lookups."""
    reset_engine_runtime(grid_size=(4, 3))
    target = create_goblin(name="Slipping target", position=(1, 1))
    web_target = create_goblin(name="Web target", position=(3, 1))
    cause = _cause(target.uuid)
    ice = IceSurface(
        source_entity_uuid=target.uuid,
        position=(1, 1),
        affected_positions={(1, 1)},
    )
    web = BurningWeb(
        source_entity_uuid=target.uuid,
        position=(2, 1),
        affected_positions={(2, 1)},
    )

    with fixed_dice_faces(1):
        ice.activate(parent_event=cause)
    web.activate(parent_event=cause)

    assert "Prone" in target.active_conditions
    hp_before = web_target.get_hp()
    with fixed_dice_faces(1, 1):
        Entity.update_entity_position(
            web_target,
            (2, 1),
            parent_event=cause.uuid,
        )
    assert web_target.get_hp() == hp_before
    with fixed_dice_faces(1, 1):
        web_target.on_turn_start(round_number=1, turn_index=0)
    assert web_target.get_hp() == hp_before - 2

    _publish_interaction(
        target.uuid,
        operation=SpatialEffectInteractionOperation.DOUSE,
        positions={(2, 1)},
    )
    assert get_map().get_spatial_conditions_at((2, 1)) == []
