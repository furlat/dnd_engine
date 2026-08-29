"""Public proofs for detached, path-level event knowledge."""

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest

from dnd.actions.standard import AttackEvent, Move, MovementEvent, SpellEvent
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.blocks.sensory import (
    PartyKnowledge,
    Senses,
    capture_senses_snapshot,
    cold_senses_snapshot,
    reduce_sensory_snapshot,
)
from dnd.core.events.entity_events import EntityCreatedEvent
from dnd.core.events.encounter_events import (
    EncounterEndEvent,
    EncounterStartEvent,
    RoundEndEvent,
    RoundStartEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.events.item_events import ItemState
from dnd.core.events.resolution_events import (
    AttackD20RollResultEvent,
    Damage,
    DamageAppliedEvent,
    DamageRollPacket,
    DamageRollResultEvent,
    TakeDamageEvent,
)
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.dice import DiceRoll
from dnd.core.events.events_registry import Event, EventPhase, EventQueue, EventType
from dnd.conditions import Prone
from dnd.core.events.knowledge import (
    CapturedEvent,
    EventArchive,
    EventDelivery,
    EventKnowledge,
    EventKnowledgeRouter,
    KnowledgeDiagnostic,
    KnowledgeMask,
    Known,
    SourceCoverage,
    SourceDisposition,
    Unknown,
    UnknownReason,
)
from dnd.types.abilities import AbilityName
from dnd.types.conditions import ConditionApplicationDisposition
from dnd.types.life import LifeState
from dnd.event_reduction import (
    BASE_EVENT_INTENTIONALLY_SILENT_REASON,
    EventReducer,
    format_event_knowledge,
    format_objective_event,
    format_subjective_delivery,
    format_subjective_delivery_tree,
    party_event_delivery,
    party_event_router,
)
from dnd.core.events.world_events import (
    SensoryUpdateEvent,
    SensoryUpdateReason,
    SpatialChangeEvent,
    SpatialChangeType,
    StepMovementEvent,
    WorldInitializedEvent,
    WorldObjectState,
    WorldTileState,
)
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.types.damage import DamageType
from dnd.types.equipment import WeaponSlot
from dnd.types.materials import Material, TileSurface
from dnd.types.rolls import (
    AdvantageStatus,
    AttackOutcome,
    AutoHitStatus,
    CriticalStatus,
    RollType,
)
from dnd.types.senses import PerceivedContact, SenseMode, SensesType
from dnd.types.creatures import CreatureType, Size
from dnd.types.world import CardinalDirection, LightLevel, WorldEdgeChannel
from dnd.types.world_placement import WorldObjectPlacement, WorldPlacementKind
from tests.engine.support import create_test_monster
from tests.engine.test_senses_light_stealth import reset_senses_state, set_modes


@pytest.fixture(autouse=True)
def clean_event_queue() -> Iterator[None]:
    EventQueue.reset()
    yield
    EventQueue.reset()


def stored_event(**updates: Any) -> Event:
    event = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        use_register=False,
        **updates,
    )
    EventQueue.register(event)
    EventQueue.register(event.phase_to(EventPhase.COMPLETION))
    return event


def register_world_lifecycle(world: WorldInitializedEvent) -> WorldInitializedEvent:
    """Publish a real four-phase world root for pull-reducer examples."""
    declaration = world.model_copy(update={
        "phase": EventPhase.DECLARATION,
        "is_first": True,
        "is_last": False,
        "use_register": False,
    })
    published = EventQueue.publish_preflighted(declaration)
    execution = published.phase_to(EventPhase.EXECUTION)
    effect = execution.phase_to(EventPhase.EFFECT)
    return effect.phase_to(EventPhase.COMPLETION)


def detached_archive(*events: Event) -> EventArchive:
    """Capture policy inputs without inventing queue roots for pure routing tests."""
    generation = EventQueue.generation_id()
    return EventArchive(tuple(
        CapturedEvent(
            generation_id=generation,
            source_index=index,
            _snapshot=event.model_copy(deep=True),
        )
        for index, event in enumerate(events)
    ))


def register_effect_tree(root: Event, *children: Event) -> Event:
    """Register one effect root, its already-parented children, and its terminal."""
    EventQueue.register(root)
    for child in children:
        EventQueue.register(child)
    terminal = root.phase_to(EventPhase.COMPLETION)
    EventQueue.register(terminal)
    return terminal


def test_archive_preserves_real_class_identity_and_detaches_later_mutation() -> None:
    child_uuid = uuid4()
    event = stored_event(children_events=[child_uuid])

    archive = EventArchive.capture_queue_range(0)
    captured = archive.get(0)
    event.children_events.append(uuid4())

    knowledge = EventKnowledge(captured=captured, mask=KnowledgeMask.top())
    children = knowledge.known_items(("children_events",))

    assert captured.event_class is Event
    assert captured.event_uuid == event.uuid
    assert captured.lineage_uuid == event.lineage_uuid
    assert children == Known((child_uuid,))


def test_known_none_is_distinct_from_unknown_and_context_never_leaks() -> None:
    stored_event(context={"secret": "not presentation data"})
    archive = EventArchive.capture_queue_range(0)
    objective = EventKnowledge(archive.get(0), KnowledgeMask.top())
    narrowed = EventKnowledge(
        archive.get(0),
        KnowledgeMask.from_paths(("target_entity_uuid",)),
    )

    assert objective.read(("target_entity_uuid",)) == Known(None)
    assert narrowed.read(("target_entity_uuid",)) == Known(None)
    assert narrowed.read(("name",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("name",),
    )
    assert objective.read(("context",)) == Unknown(
        UnknownReason.NOT_COLD_VALUE,
        ("context",),
    )
    assert objective.known_items(("context",)) == Unknown(
        UnknownReason.NOT_COLD_VALUE,
        ("context",),
    )


def test_mask_join_and_narrowing_are_idempotent() -> None:
    first = KnowledgeMask.from_paths(
        ("name",),
        collection_paths=(("children_events",),),
    )
    second = KnowledgeMask.from_paths(("outcome_code",))

    assert first.union(first) == first
    assert first.intersection(first) == first
    assert first.union(second).union(second) == first.union(second)
    assert first.intersection(KnowledgeMask.top()) == first
    assert first.union(KnowledgeMask.top()) == KnowledgeMask.top()


def test_archive_validates_exact_closed_range() -> None:
    first = stored_event(name="first")
    second = stored_event(name="second")

    archive = EventArchive.capture_queue_range(2, 3)

    assert tuple(entry.source_index for entry in archive.entries) == (2,)
    assert archive.get(2).event_uuid == second.uuid
    assert archive.get(2).event_uuid != first.uuid
    with pytest.raises(ValueError, match="invalid event range"):
        EventArchive.capture_queue_range(0, 5)


def test_router_dispatches_on_exact_real_event_class() -> None:
    source_uuid = uuid4()
    base = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        use_register=False,
    )
    step = StepMovementEvent(
        source_entity_uuid=source_uuid,
        from_position=(0, 0),
        to_position=(1, 0),
        committed=True,
        phase=EventPhase.COMPLETION,
        parent_event=base.uuid,
        use_register=False,
    )
    EventQueue.register(base)
    EventQueue.register(step)
    archive = EventArchive.capture_queue_range(0)
    router: EventKnowledgeRouter[str] = EventKnowledgeRouter()
    router.register(Event, lambda knowledge: knowledge.event_class.__name__)

    base_result = router.dispatch(EventKnowledge(archive.get(0), KnowledgeMask.top()))
    step_result = router.dispatch(EventKnowledge(archive.get(1), KnowledgeMask.top()))

    assert base_result == "Event"
    assert step_result == KnowledgeDiagnostic(
        reason=UnknownReason.NO_CLASS_POLICY,
        source_index=1,
        event_class="StepMovementEvent",
        detail="no exact concrete-event-class policy",
    )
    assert router.covered_classes() == frozenset({Event})


def test_type_mismatch_is_structured_and_payload_free() -> None:
    stored_event()
    captured = EventArchive.capture_queue_range(0).get(0)
    knowledge = EventKnowledge(captured, KnowledgeMask.top())

    mismatch = knowledge.require_class(StepMovementEvent)

    assert mismatch == KnowledgeDiagnostic(
        reason=UnknownReason.TYPE_MISMATCH,
        source_index=0,
        event_class="Event",
        detail="expected exact class StepMovementEvent",
    )


def sensory_update(observer_uuid: UUID, **updates: Any) -> SensoryUpdateEvent:
    values = {
        "source_entity_uuid": observer_uuid,
        "target_entity_uuid": observer_uuid,
        "observer_uuid": observer_uuid,
        "cause_event_uuid": uuid4(),
        "use_register": False,
    }
    # A child gets its own lineage; the causal parent is carried by UUID.
    if updates.get("parent_event") is not None:
        updates.pop("lineage_uuid", None)
    values.update(updates)
    return SensoryUpdateEvent(**values)


def test_slice_3_3_bootstrap_exposes_identity_bounds_only_and_seeds_references() -> None:
    observer_uuid = uuid4()
    tile = WorldTileState(
        tile_uuid=uuid4(),
        position=(2, 2),
        surface=TileSurface(base_material=Material.STONE),
        name="Stone floor",
        blocks_optics=False,
        blocks_propagation=False,
        walking_cost=1,
        flying_cost=1,
        swimming_cost=2,
        burrowing_cost=1,
        elevation_steps=3,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        default_light=LightLevel.BRIGHT_LIGHT,
        resolved_light=LightLevel.BRIGHT_LIGHT,
    )
    world = WorldInitializedEvent(
        source_entity_uuid=observer_uuid,
        battlefield_id="battlefield.open_floor_bright",
        battlefield_name="Open Floor",
        bounds=(0, 0, 4, 4),
        width=4,
        height=4,
        tiles=(tile,),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    register_world_lifecycle(world)
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)

    batch = reducer.reduce_next_committed_tree()

    assert len(batch.deliveries) == 4
    knowledge = next(
        delivery.knowledge
        for delivery in batch.deliveries
        if delivery.knowledge.captured._snapshot.phase is EventPhase.COMPLETION
    )
    assert knowledge.read(("battlefield_id",)) == Known("battlefield.open_floor_bright")
    assert knowledge.read(("bounds",)) == Known((0, 0, 4, 4))
    assert knowledge.read(("tiles", 0, "surface")) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("tiles", 0, "surface"),
    )
    assert knowledge.known_items(("tiles",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("tiles",),
    )
    assert knowledge.known_items(("objects",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("objects",),
    )
    assert knowledge.known_items(("connectors",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("connectors",),
    )
    assert reducer.provenance[((2, 2), ("tile_surface",))] == (
        EventQueue.generation_id(),
        3,
        ("tiles", 0, "surface"),
    )
    assert reducer.provenance[((2, 2), ("tiles", 0, "elevation_steps"))] == (
        EventQueue.generation_id(),
        3,
        ("tiles", 0, "elevation_steps"),
    )


def test_slice_3_3_first_reveal_and_loss_use_exact_old_paths_without_collection_leak() -> None:
    observer_uuid = uuid4()
    tile = WorldTileState(
        tile_uuid=uuid4(),
        position=(2, 2),
        surface=TileSurface(base_material=Material.STONE),
        name="Stone floor",
        blocks_optics=False,
        blocks_propagation=False,
        walking_cost=1,
        flying_cost=1,
        swimming_cost=1,
        burrowing_cost=1,
        elevation_steps=0,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        default_light=LightLevel.BRIGHT_LIGHT,
        resolved_light=LightLevel.BRIGHT_LIGHT,
    )
    world = WorldInitializedEvent(
        source_entity_uuid=observer_uuid,
        battlefield_id="battlefield.open_floor_bright",
        battlefield_name="Open Floor",
        bounds=(0, 0, 4, 4),
        width=4,
        height=4,
        tiles=(tile,),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    register_world_lifecycle(world)
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)
    reducer.reduce_next_committed_tree()

    cause = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    reveal = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        parent_event=cause.uuid,
        lineage_uuid=cause.lineage_uuid,
        cause_event_uuid=cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(2, 2)],
        seen_cells_added=[(2, 2)],
    )
    register_effect_tree(cause, reveal)

    reveal_batch = reducer.reduce_next_committed_tree()
    late = next(
        delivery
        for delivery in reveal_batch.deliveries
        if delivery.knowledge.captured.source_index == 3
    )
    assert late.knowledge.read(("tiles", 0, "surface")) == Known(tile.surface)
    assert late.knowledge.read(("tiles", 0, "walking_cost")) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("tiles", 0, "walking_cost"),
    )
    assert reducer.party_knowledge.visible == frozenset({(2, 2)})

    loss_cause = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    loss = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        parent_event=loss_cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_removed=[(2, 2)],
    )
    register_effect_tree(loss_cause, loss)
    reducer.reduce_next_committed_tree()

    assert reducer.party_knowledge.visible == frozenset()
    assert ((2, 2), ("tile_surface",)) in reducer.provenance


def test_slice_3_3_adjacent_boundary_objects_keep_separate_provenance_and_beyond_stays_unknown() -> None:
    observer_uuid = uuid4()
    tiles = tuple(
        WorldTileState(
            tile_uuid=uuid4(),
            position=position,
            surface=TileSurface(base_material=Material.STONE),
            name="Stone floor",
            blocks_optics=False,
            blocks_propagation=False,
            walking_cost=1,
            flying_cost=1,
            swimming_cost=1,
            burrowing_cost=1,
            elevation_steps=0,
            surface_kind=ElevationSurfaceKind.ORDINARY,
            default_light=LightLevel.BRIGHT_LIGHT,
            resolved_light=LightLevel.BRIGHT_LIGHT,
        )
        for position in ((0, 0), (1, 0), (2, 0))
    )
    first_uuid = uuid4()
    second_uuid = uuid4()
    first_placement = WorldObjectPlacement(
        object_uuid=first_uuid,
        tile_uuid=tiles[0].tile_uuid,
        position=(0, 0),
        kind=WorldPlacementKind.BOUNDARY,
        occupies_bands=True,
        boundary_direction=CardinalDirection.EAST,
        base_height_steps=0,
        top_height_steps=1,
        orientation=CardinalDirection.NORTH,
    )
    second_placement = WorldObjectPlacement(
        object_uuid=second_uuid,
        tile_uuid=tiles[1].tile_uuid,
        position=(1, 0),
        kind=WorldPlacementKind.BOUNDARY,
        occupies_bands=True,
        boundary_direction=CardinalDirection.WEST,
        base_height_steps=0,
        top_height_steps=1,
        orientation=CardinalDirection.NORTH,
    )
    world = WorldInitializedEvent(
        source_entity_uuid=observer_uuid,
        battlefield_id="battlefield.boundary_proof",
        battlefield_name="Boundary Proof",
        bounds=(0, 0, 3, 1),
        width=3,
        height=1,
        tiles=tiles,
        objects=(
            WorldObjectState(
                placement=first_placement,
                item=ItemState(item_uuid=first_uuid, semantic_key="wall.first", name="Wall A"),
            ),
            WorldObjectState(
                placement=second_placement,
                item=ItemState(item_uuid=second_uuid, semantic_key="wall.second", name="Wall B"),
            ),
        ),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    register_world_lifecycle(world)
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)
    reducer.reduce_next_committed_tree()

    cause = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    reveal = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        parent_event=cause.uuid,
        lineage_uuid=cause.lineage_uuid,
        cause_event_uuid=cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(0, 0), (1, 0)],
        object_contacts_changed={
            first_uuid: PerceivedContact(position=(0, 0), visual=True),
            second_uuid: PerceivedContact(position=(1, 0), visual=True),
        },
    )
    register_effect_tree(cause, reveal)

    batch = reducer.reduce_next_committed_tree()
    late = next(
        delivery
        for delivery in batch.deliveries
        if delivery.knowledge.captured.source_index == 3
    )
    assert late.knowledge.read(("objects", 0, "placement")) == Known(first_placement)
    assert late.knowledge.read(("objects", 1, "placement")) == Known(second_placement)
    assert late.knowledge.read(("tiles", 2, "surface")) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("tiles", 2, "surface"),
    )
    assert reducer.provenance[(first_uuid, ("placement",))][1] == 3
    assert reducer.provenance[(second_uuid, ("placement",))][1] == 3


def test_slice_3_3_nonvisual_contact_and_effective_light_never_reopen_visual_or_world_light_paths() -> None:
    observer_uuid = uuid4()
    subject_uuid = uuid4()
    created = EntityCreatedEvent(
        source_entity_uuid=observer_uuid,
        entity_uuid=subject_uuid,
        entity_kind_id="creature.guard",
        entity_name="Guard",
        entity_description="A hidden guard",
        creature_type=CreatureType.HUMANOID,
        size=Size.MEDIUM,
        structural_base_size=Size.MEDIUM,
        weight=10,
        current_hit_points=8,
        maximum_hit_points=8,
        life_state=LifeState.ALIVE,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    EventQueue.register(created)
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)
    reducer.reduce_next_committed_tree()

    cause = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    sensory = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        parent_event=cause.uuid,
        lineage_uuid=cause.lineage_uuid,
        cause_event_uuid=cause.uuid,
        update_reason=SensoryUpdateReason.LIGHT,
        visible_cells_added=[(3, 3)],
        entity_contacts_changed={
            subject_uuid: PerceivedContact(
                position=(3, 3),
                visual=False,
                special_senses=(SensesType.BLINDSIGHT,),
            ),
        },
        effective_light_levels_changed={"3,3": LightLevel.DIM_LIGHT.value},
    )
    terminal = cause.phase_to(EventPhase.COMPLETION)
    for event in (cause, sensory, terminal):
        EventQueue.register(event)

    batch = reducer.reduce_next_committed_tree()
    current = next(
        delivery
        for delivery in batch.deliveries
        if delivery.knowledge.captured.event_uuid == sensory.uuid
    )
    late = next(
        delivery
        for delivery in batch.deliveries
        if delivery.knowledge.captured.source_index == 0
    )
    assert current.knowledge.known_items(("effective_light_levels_changed",)) == Known(
        (("3,3", LightLevel.DIM_LIGHT.value),),
    )
    assert reducer.party_knowledge.effective_light_levels[(3, 3)] is LightLevel.DIM_LIGHT
    assert reducer.party_knowledge.entities[subject_uuid].visual is False
    assert late.knowledge.read(("entity_uuid",)) == Known(subject_uuid)
    assert late.knowledge.read(("entity_name",)) == Known("Guard")
    assert late.knowledge.read(("entity_description",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("entity_description",),
    )
    assert late.knowledge.read(("resolved_light",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("resolved_light",),
    )


def test_slice_3_3_same_batch_unrelated_later_change_is_not_sampled_for_reveal() -> None:
    observer_uuid = uuid4()
    tile = WorldTileState(
        tile_uuid=uuid4(),
        position=(4, 4),
        surface=TileSurface(base_material=Material.STONE),
        name="Stone",
        blocks_optics=False,
        blocks_propagation=False,
        walking_cost=1,
        flying_cost=1,
        swimming_cost=1,
        burrowing_cost=1,
        elevation_steps=0,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        default_light=LightLevel.BRIGHT_LIGHT,
        resolved_light=LightLevel.BRIGHT_LIGHT,
    )
    world = WorldInitializedEvent(
        source_entity_uuid=observer_uuid,
        battlefield_id="battlefield.reveal_order",
        battlefield_name="Reveal Order",
        bounds=(0, 0, 5, 5),
        width=5,
        height=5,
        tiles=(tile,),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    register_world_lifecycle(world)
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)
    reducer.reduce_next_committed_tree()

    cause = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    reveal = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        parent_event=cause.uuid,
        lineage_uuid=cause.lineage_uuid,
        cause_event_uuid=cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(4, 4)],
    )
    unrelated = SpatialChangeEvent(
        source_entity_uuid=uuid4(),
        change_type=SpatialChangeType.TILE_CHANGED,
        position=(4, 4),
        tile_surface=TileSurface(base_material=Material.WATER),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    register_effect_tree(cause, reveal)
    unrelated_root = unrelated.model_copy(update={
        "phase": EventPhase.EFFECT,
        "is_first": True,
        "is_last": False,
    })
    register_effect_tree(unrelated_root)

    batch = reducer.reduce_next_committed_tree()
    unrelated_batch = reducer.reduce_next_committed_tree()
    late = next(
        delivery
        for delivery in batch.deliveries
        if delivery.knowledge.captured.source_index == 3
    )
    assert late.knowledge.read(("tiles", 0, "surface")) == Known(tile.surface)
    assert unrelated_batch.coverage[0].disposition is SourceDisposition.HIDDEN
    assert reducer.provenance[((4, 4), ("tile_surface",))][1] == 8


def test_slice_3_3_reveal_prefers_terminal_owner_reference_over_older_provenance() -> None:
    observer_uuid = uuid4()
    tile = WorldTileState(
        tile_uuid=uuid4(),
        position=(4, 4),
        surface=TileSurface(base_material=Material.STONE),
        name="Stone",
        blocks_optics=False,
        blocks_propagation=False,
        walking_cost=1,
        flying_cost=1,
        swimming_cost=1,
        burrowing_cost=1,
        elevation_steps=0,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        default_light=LightLevel.BRIGHT_LIGHT,
        resolved_light=LightLevel.BRIGHT_LIGHT,
    )
    world = WorldInitializedEvent(
        source_entity_uuid=observer_uuid,
        battlefield_id="battlefield.terminal_owner",
        battlefield_name="Terminal Owner",
        bounds=(0, 0, 5, 5),
        width=5,
        height=5,
        tiles=(tile,),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    register_world_lifecycle(world)
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)
    reducer.reduce_next_committed_tree()

    cause = SpatialChangeEvent(
        source_entity_uuid=uuid4(),
        change_type=SpatialChangeType.TILE_CHANGED,
        position=(4, 4),
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    reveal = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        parent_event=cause.uuid,
        lineage_uuid=cause.lineage_uuid,
        cause_event_uuid=cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(4, 4)],
    )
    terminal = cause.phase_to(
        EventPhase.COMPLETION,
        tile_surface=TileSurface(base_material=Material.WATER),
    )
    for event in (cause, reveal, terminal):
        EventQueue.register(event)

    batch = reducer.reduce_next_committed_tree()
    late = next(
        delivery
        for delivery in batch.deliveries
        if delivery.knowledge.captured.source_index == 6
    )
    assert late.knowledge.read(("tile_surface",)) == Known(
        TileSurface(base_material=Material.WATER),
    )
    assert not any(
        delivery.knowledge.captured.source_index == 0
        and ("tiles", 0, "surface") in delivery.knowledge.mask.paths
        for delivery in batch.deliveries
    )


def test_slice_3_3_duplicate_causative_terminals_fail_without_reducer_state_advance() -> None:
    observer_uuid = uuid4()
    cause = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    sensory = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        parent_event=cause.uuid,
        lineage_uuid=cause.lineage_uuid,
        cause_event_uuid=cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(10, 10)],
    )
    terminal_one = Event(
        source_entity_uuid=cause.source_entity_uuid,
        event_type=cause.event_type,
        lineage_uuid=cause.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    terminal_two = Event(
        source_entity_uuid=cause.source_entity_uuid,
        event_type=cause.event_type,
        lineage_uuid=cause.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    for event in (cause, sensory, terminal_one):
        EventQueue.register(event)
    with pytest.raises(ValueError, match="root|open"):
        EventQueue.register(terminal_two)
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)

    assert reducer.source_cursor == 0
    assert reducer.archives == ()
    assert reducer.party_knowledge.visible == frozenset()
    assert reducer.provenance == {}


def test_slice_3_3_nonterminal_causative_match_is_fatal_without_reducer_state_advance() -> None:
    observer_uuid = uuid4()
    cause = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EXECUTION,
        use_register=False,
    )
    sensory = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        parent_event=cause.uuid,
        lineage_uuid=cause.lineage_uuid,
        cause_event_uuid=cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(11, 11)],
    )
    for event in (cause, sensory):
        EventQueue.register(event)
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)

    assert reducer.reduce_next_committed_tree() is None

    assert reducer.source_cursor == 0
    assert reducer.archives == ()
    assert reducer.party_knowledge.visible == frozenset()
    assert reducer.provenance == {}


def test_slice_3_3_reduction_after_capture_does_not_read_live_grid_or_object_accessors(monkeypatch: pytest.MonkeyPatch) -> None:
    observer_uuid = uuid4()
    event = sensory_update(
        observer_uuid,
        visible_cells_added=[(5, 5)],
        update_reason=SensoryUpdateReason.SPATIAL,
    )
    EventQueue.register(event)
    captured = EventArchive.capture_queue_range(0).get(0)

    def fail(*_args: Any, **_kwargs: Any) -> object:
        raise AssertionError("reduction touched live state")

    monkeypatch.setattr("dnd.core.gridmap.get_map", fail)
    monkeypatch.setattr(BaseBlock, "get_position", fail)
    monkeypatch.setattr(BaseObject, "get", classmethod(fail))

    party = PartyKnowledge.cold(observer_uuid, uuid4())
    delivery = party_event_delivery(captured, party_event_router(party))
    assert delivery is not None and not isinstance(delivery, KnowledgeDiagnostic)
    assert delivery.knowledge.known_items(("visible_cells_added",)) == Known(((5, 5),))


def test_pure_sensory_reducer_is_the_live_senses_replay_implementation() -> None:
    observer_uuid = uuid4()
    contact_uuid = uuid4()
    update = sensory_update(
        observer_uuid,
        observer_position=(2, 3),
        observer_position_changed=True,
        visible_cells_added=[(2, 3), (3, 3)],
        seen_cells_added=[(2, 3), (3, 3)],
        entity_contacts_changed={
            contact_uuid: PerceivedContact(
                position=(3, 3),
                visual=True,
                special_senses=(SensesType.DARKVISION,),
            ),
        },
        effective_light_levels_changed={"2,3": LightLevel.DIM_LIGHT.value},
        sense_modes_changed=True,
        sense_modes=[SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)],
        passive_perception_changed=True,
        passive_perception=13,
        visual_access_changed=True,
        visual_access=0,
        paths_dirty=True,
    )
    expected = reduce_sensory_snapshot(cold_senses_snapshot(), update)
    live = Senses.create(source_entity_uuid=observer_uuid)

    live.apply_sensory_update(update)

    assert capture_senses_snapshot(live) == expected


@pytest.mark.parametrize(
    ("changed_field", "value_field"),
    (
        ("sense_modes_changed", "sense_modes"),
        ("passive_perception_changed", "passive_perception"),
        ("visual_access_changed", "visual_access"),
    ),
)
def test_sensory_reducer_rejects_changed_flags_without_after_values(
    changed_field: str,
    value_field: str,
) -> None:
    observer_uuid = uuid4()
    event = sensory_update(observer_uuid, **{changed_field: True, value_field: None})

    with pytest.raises(ValueError, match="exact after-value"):
        reduce_sensory_snapshot(cold_senses_snapshot(), event)


def test_first_unchanged_sensory_values_retain_the_exact_cold_seed() -> None:
    observer_uuid = uuid4()
    event = sensory_update(
        observer_uuid,
        passive_perception=99,
        sense_modes=[SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=120)],
        visual_access=0,
    )

    after = reduce_sensory_snapshot(cold_senses_snapshot(), event)

    assert after.passive_perception == 0
    assert after.sense_modes == ()
    assert after.sense_modes_hash == hash(())
    assert after.visual_access == 1


def test_two_observer_join_preserves_other_hero_contact_and_brightest_light() -> None:
    first_uuid = uuid4()
    second_uuid = uuid4()
    subject_uuid = uuid4()
    first_update = sensory_update(
        first_uuid,
        visible_cells_added=[(1, 1)],
        seen_cells_added=[(1, 1)],
        entity_contacts_changed={
            subject_uuid: PerceivedContact(
                position=(1, 1),
                visual=False,
                special_senses=(SensesType.BLINDSIGHT,),
            ),
        },
        effective_light_levels_changed={"1,1": LightLevel.DIM_LIGHT.value},
    )
    second_update = sensory_update(
        second_uuid,
        visible_cells_added=[(1, 1)],
        entity_contacts_changed={
            subject_uuid: PerceivedContact(position=(1, 1), visual=True),
        },
        effective_light_levels_changed={"1,1": LightLevel.BRIGHT_LIGHT.value},
    )
    second_loses_contact = sensory_update(
        second_uuid,
        entity_contacts_removed={subject_uuid},
    )
    archive = detached_archive(first_update, second_update, second_loses_contact)

    party = PartyKnowledge.cold(first_uuid, second_uuid)
    party = party.apply(archive.get(0)).apply(archive.get(1))
    assert party.entities[subject_uuid] == PerceivedContact(
        position=(1, 1),
        visual=True,
        special_senses=(SensesType.BLINDSIGHT,),
    )
    party = party.apply(archive.get(2))

    assert party.visible == frozenset({(1, 1)})
    assert party.seen == frozenset({(1, 1)})
    assert party.entities[subject_uuid] == PerceivedContact(
        position=(1, 1),
        visual=False,
        special_senses=(SensesType.BLINDSIGHT,),
    )
    assert party.effective_light_levels[(1, 1)] is LightLevel.BRIGHT_LIGHT


def test_only_controlled_sensory_updates_become_party_deliveries() -> None:
    first_uuid = uuid4()
    second_uuid = uuid4()
    controlled = sensory_update(first_uuid, visible_cells_added=[(2, 2)])
    unrelated = sensory_update(uuid4(), visible_cells_added=[(9, 9)])
    archive = detached_archive(controlled, unrelated)
    party = PartyKnowledge.cold(first_uuid, second_uuid)
    router = party_event_router(party)

    controlled_delivery = party_event_delivery(archive.get(0), router)
    unrelated_delivery = party_event_delivery(archive.get(1), router)

    assert controlled_delivery is not None and not isinstance(
        controlled_delivery,
        KnowledgeDiagnostic,
    )
    assert controlled_delivery.knowledge.event_class is SensoryUpdateEvent
    assert controlled_delivery.knowledge.read(("observer_uuid",)) == Known(first_uuid)
    assert controlled_delivery.knowledge.known_items(("visible_cells_added",)) == Known(
        ((2, 2),),
    )
    assert unrelated_delivery is None


def test_committed_step_exposes_only_event_time_known_geometry() -> None:
    first_uuid = uuid4()
    second_uuid = uuid4()
    enemy_uuid = uuid4()
    step = StepMovementEvent(
        source_entity_uuid=enemy_uuid,
        from_position=(4, 4),
        to_position=(5, 4),
        from_elevation_feet=10,
        to_elevation_feet=15,
        path_index=1,
        total_path_length=3,
        movement_cost=10,
        disclosed_path=((4, 4), (6, 4)),
        committed=True,
        located_position_observer_uuids={"4,4": {str(first_uuid)}, "5,4": set()},
        use_register=False,
    )
    controlled_step = StepMovementEvent(
        source_entity_uuid=first_uuid,
        from_position=(0, 0),
        to_position=(1, 0),
        from_elevation_feet=0,
        to_elevation_feet=5,
        path_index=2,
        total_path_length=4,
        movement_cost=15,
        disclosed_path=((0, 0), (1, 0)),
        committed=True,
        use_register=False,
    )
    archive = detached_archive(step, controlled_step)
    party = PartyKnowledge.cold(first_uuid, second_uuid)

    delivery = party_event_delivery(archive.get(0), party_event_router(party))
    controlled_delivery = party_event_delivery(
        archive.get(1),
        party_event_router(party),
    )

    assert delivery is not None and not isinstance(delivery, KnowledgeDiagnostic)
    assert controlled_delivery is not None and not isinstance(
        controlled_delivery,
        KnowledgeDiagnostic,
    )
    assert delivery.knowledge.read(("committed",)) == Known(True)
    assert delivery.knowledge.read(("trajectory",)) == Known(step.trajectory)
    for path in (
        ("path_index",),
        ("total_path_length",),
        ("movement_cost",),
        ("provocation_policy",),
    ):
        assert delivery.knowledge.read(path) == Unknown(
            UnknownReason.PATH_NOT_READABLE,
            path,
        )
    assert delivery.knowledge.read(("from_position",)) == Known((4, 4))
    assert delivery.knowledge.read(("from_elevation_feet",)) == Known(10)
    assert delivery.knowledge.read(("to_position",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("to_position",),
    )
    assert delivery.knowledge.read(("to_elevation_feet",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("to_elevation_feet",),
    )
    assert delivery.knowledge.read(("disclosed_path",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("disclosed_path",),
    )
    assert controlled_delivery.knowledge.read(("committed",)) == Known(True)
    for path in (
        ("path_index",),
        ("total_path_length",),
        ("movement_cost",),
        ("provocation_policy",),
    ):
        assert controlled_delivery.knowledge.read(path) == Unknown(
            UnknownReason.PATH_NOT_READABLE,
            path,
        )
    assert controlled_delivery.knowledge.read(("trajectory",)) == Known(
        controlled_step.trajectory,
    )
    assert controlled_delivery.knowledge.read(("disclosed_path",)) == Known(
        controlled_step.disclosed_path,
    )
    assert controlled_delivery.knowledge.read(("to_position",)) == Known((1, 0))
    assert controlled_delivery.knowledge.read(("to_elevation_feet",)) == Known(5)


def test_party_identity_and_location_are_independent_event_time_facts() -> None:
    first_uuid = uuid4()
    second_uuid = uuid4()
    enemy_uuid = uuid4()
    event = Event(
        source_entity_uuid=enemy_uuid,
        event_type=EventType.TRIGGER_EVENT,
        identified_entity_observer_uuids={str(enemy_uuid): {str(first_uuid)}},
        located_entity_observer_uuids={str(enemy_uuid): set()},
        use_register=False,
    )
    party = PartyKnowledge.cold(first_uuid, second_uuid)

    assert party.identifies_entity(event, enemy_uuid)
    assert not party.locates_entity(event, enemy_uuid)
    assert party.identifies_entity(event, first_uuid)
    assert party.locates_entity(event, first_uuid)


def test_attack_and_controlled_damage_keep_real_classes_and_cold_fields_only() -> None:
    first_uuid = uuid4()
    second_uuid = uuid4()
    enemy_uuid = uuid4()
    attack = AttackEvent(
        source_entity_uuid=enemy_uuid,
        source_entity_name="Enemy",
        target_entity_uuid=first_uuid,
        target_entity_name="Hero",
        weapon_slot=WeaponSlot.MELEE_MAIN,
        weapon_name="Sword",
        attack_outcome=AttackOutcome.HIT,
        damage_types=[DamageType.SLASHING],
        use_register=False,
    )
    damage = DamageAppliedEvent(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=first_uuid,
        applied_damage=7,
        normal_hit_point_damage=5,
        temporary_hit_point_damage=2,
        resulting_normal_hp=18,
        resulting_temporary_hp=0,
        damage_type=DamageType.SLASHING,
        use_register=False,
    )
    archive = detached_archive(attack, damage)
    party = PartyKnowledge.cold(first_uuid, second_uuid)

    router = party_event_router(party)
    attack_delivery = party_event_delivery(archive.get(0), router)
    damage_delivery = party_event_delivery(archive.get(1), router)

    assert attack_delivery is not None and not isinstance(
        attack_delivery,
        KnowledgeDiagnostic,
    )
    assert attack_delivery.knowledge.event_class is AttackEvent
    assert attack_delivery.knowledge.read(("weapon_name",)) == Known("Sword")
    assert attack_delivery.knowledge.known_items(("damage_types",)) == Known(
        (DamageType.SLASHING,),
    )
    assert attack_delivery.knowledge.read(("attack_bonus",)) == Unknown(
        UnknownReason.NOT_COLD_VALUE,
        ("attack_bonus",),
    )
    assert damage_delivery is not None and not isinstance(
        damage_delivery,
        KnowledgeDiagnostic,
    )
    assert damage_delivery.knowledge.event_class is DamageAppliedEvent
    assert damage_delivery.knowledge.read(("resulting_normal_hp",)) == Known(18)
    assert damage_delivery.knowledge.read(("damages",)) == Unknown(
        UnknownReason.NOT_COLD_VALUE,
        ("damages",),
    )


def test_unadmitted_concrete_class_returns_only_a_policy_diagnostic() -> None:
    class UnadmittedEvent(Event):
        secret: str

    first_uuid = uuid4()
    base_event = Event(
        source_entity_uuid=first_uuid,
        event_type=EventType.TRIGGER_EVENT,
        use_register=False,
    )
    event = UnadmittedEvent(
        source_entity_uuid=first_uuid,
        event_type=EventType.TRIGGER_EVENT,
        secret="must not become a delivery",
        use_register=False,
    )
    archive = detached_archive(base_event, event)
    captured = archive.get(1)
    base_captured = archive.get(0)

    assert party_event_delivery(
        base_captured,
        party_event_router(PartyKnowledge.cold(first_uuid, uuid4())),
    ) is None
    with pytest.raises(
        RuntimeError,
        match=BASE_EVENT_INTENTIONALLY_SILENT_REASON,
    ):
        format_event_knowledge(EventKnowledge(base_captured, KnowledgeMask.top()))

    result = party_event_delivery(
        captured,
        party_event_router(PartyKnowledge.cold(first_uuid, uuid4())),
    )

    assert result == KnowledgeDiagnostic(
        reason=UnknownReason.NO_CLASS_POLICY,
        source_index=1,
        event_class=type(event).__qualname__,
        detail="no exact concrete-event-class policy",
    )
    with pytest.raises(RuntimeError, match="no formatter policy"):
        format_event_knowledge(EventKnowledge(captured, KnowledgeMask.top()))


def test_slice_4_subjective_tree_groups_real_parent_and_counts_delivered_children() -> None:
    observer_uuid = uuid4()
    enemy_uuid = uuid4()
    parent = AttackEvent(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=observer_uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        weapon_name="Parent sword",
        attack_outcome=AttackOutcome.HIT,
        identified_entity_observer_uuids={
            str(enemy_uuid): {str(observer_uuid)},
        },
        use_register=False,
    )
    visible_roll = DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.ATTACK,
        results=[18],
        total=18,
        bonus=0,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=observer_uuid,
        attack_outcome=AttackOutcome.HIT,
    )
    hidden_roll = visible_roll.model_copy(deep=True)
    visible_child = AttackD20RollResultEvent(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=observer_uuid,
        original_roll=visible_roll,
        result=True,
        parent_event=parent.uuid,
        parent_lineage=parent.lineage_uuid,
        identified_entity_observer_uuids={
            str(enemy_uuid): {str(observer_uuid)},
        },
        use_register=False,
    )
    hidden_child = AttackD20RollResultEvent(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=enemy_uuid,
        original_roll=hidden_roll,
        result=True,
        parent_event=parent.uuid,
        parent_lineage=parent.lineage_uuid,
        use_register=False,
    )
    parent.children_events = [visible_child.uuid, hidden_child.uuid]
    archive = detached_archive(hidden_child, parent, visible_child)
    objective_parent = EventKnowledge(archive.get(1), KnowledgeMask.top())
    assert objective_parent.known_items(("children_events",)) == Known(
        (visible_child.uuid, hidden_child.uuid),
    )

    party = PartyKnowledge.cold(observer_uuid, uuid4())
    router = party_event_router(party)
    deliveries = []
    for captured in archive.entries:
        delivery = party_event_delivery(captured, router)
        if delivery is not None:
            assert not isinstance(delivery, KnowledgeDiagnostic)
            deliveries.append(delivery)

    assert len(deliveries) == 2
    lines = format_subjective_delivery_tree(deliveries)
    assert len(lines) == 2
    assert lines[0].startswith("Attack ")
    assert "children_count=1" in lines[0]
    assert lines[1].startswith("  Attack roll ")
    assert str(hidden_child.uuid) not in "\n".join(lines)


def test_slice_3_3_family_masks_keep_private_perceived_fields_unknown() -> None:
    """Perceived families expose public outcomes without private mechanics."""
    observer_uuid = uuid4()
    enemy_uuid = uuid4()
    encounter_uuid = uuid4()
    evidence = {str(enemy_uuid): {str(observer_uuid)}}
    party = PartyKnowledge.cold(observer_uuid, uuid4())

    encounter_start = EncounterStartEvent(
        source_entity_uuid=enemy_uuid,
        encounter_uuid=encounter_uuid,
        combatant_uuids=[observer_uuid, enemy_uuid],
        initiative_order=[observer_uuid, enemy_uuid],
        use_register=False,
    )
    encounter_end = EncounterEndEvent(
        source_entity_uuid=enemy_uuid,
        encounter_uuid=encounter_uuid,
        combatant_uuids=[observer_uuid, enemy_uuid],
        reason="retreat",
        use_register=False,
    )
    movement = MovementEvent(
        source_entity_uuid=enemy_uuid,
        identified_entity_observer_uuids=evidence,
        start_position=(2, 2),
        end_position=(3, 2),
        requested_end_position=(8, 2),
        objective_end_position=(3, 2),
        path=((2, 2), (3, 2), (8, 2)),
        costs=[],
        controller_revalidation=True,
        controller_revalidation_reason="hidden controller detail",
        use_register=False,
    )
    take_damage = TakeDamageEvent(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=enemy_uuid,
        identified_entity_observer_uuids=evidence,
        total_damage=9,
        final_damage=7,
        normal_hit_point_damage_cap=4,
        resulting_hp=3,
        effect_id="private-effect",
        use_register=False,
    )
    spell = SpellEvent(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=enemy_uuid,
        identified_entity_observer_uuids=evidence,
        spell_id="spell.fire-bolt",
        spell_school="evocation",
        save_ability=AbilityName.DEXTERITY,
        save_dc=17,
        save_success=False,
        save_bonus=4,
        source_position=(2, 2),
        aoe_radius_ft=20,
        range_ft=60,
        use_register=False,
    )
    archive = detached_archive(encounter_start, encounter_end, movement, take_damage, spell)
    deliveries = [
        party_event_delivery(captured, party_event_router(party))
        for captured in archive.entries
    ]
    assert all(isinstance(delivery, EventDelivery) for delivery in deliveries)
    start_delivery, end_delivery, movement_delivery, damage_delivery, spell_delivery = deliveries
    assert isinstance(start_delivery, EventDelivery)
    assert isinstance(end_delivery, EventDelivery)
    assert isinstance(movement_delivery, EventDelivery)
    assert isinstance(damage_delivery, EventDelivery)
    assert isinstance(spell_delivery, EventDelivery)

    assert start_delivery.knowledge.known_items(("combatant_uuids",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("combatant_uuids",),
    )
    assert end_delivery.knowledge.known_items(("combatant_uuids",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("combatant_uuids",),
    )
    assert movement_delivery.knowledge.read(("termination_reason",)) == Known(
        movement.termination_reason,
    )
    assert movement_delivery.knowledge.read(("requested_end_position",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("requested_end_position",),
    )
    assert movement_delivery.knowledge.known_items(("costs",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("costs",),
    )
    assert damage_delivery.knowledge.read(("total_damage",)) == Known(9)
    assert damage_delivery.knowledge.read(("resulting_hp",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("resulting_hp",),
    )
    assert spell_delivery.knowledge.read(("spell_id",)) == Known("spell.fire-bolt")
    assert spell_delivery.knowledge.read(("save_success",)) == Known(False)
    assert spell_delivery.knowledge.read(("save_dc",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("save_dc",),
    )
    assert spell_delivery.knowledge.read(("save_bonus",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("save_bonus",),
    )


def test_slice_3_3_controlled_masks_admit_owned_roll_and_condition_consequences() -> None:
    """The controlled party may read its own exact resolution consequences."""
    observer_uuid = uuid4()
    enemy_uuid = uuid4()
    condition = Prone(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=observer_uuid,
    )
    original_roll = DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.ATTACK,
        results=[18],
        total=18,
        bonus=0,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=observer_uuid,
        attack_outcome=AttackOutcome.HIT,
    )
    roll = AttackD20RollResultEvent(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=observer_uuid,
        original_roll=original_roll,
        result=True,
        use_register=False,
    )
    condition_event = ConditionApplicationEvent(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=observer_uuid,
        condition=condition,
        condition_behavior_id=condition.behavior_id,
        resulting_ac=11,
        resulting_max_hp=7,
        application_disposition=ConditionApplicationDisposition.APPLIED,
        use_register=False,
    )
    damage = TakeDamageEvent(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=observer_uuid,
        total_damage=6,
        final_damage=5,
        normal_hit_point_damage_cap=5,
        resulting_hp=12,
        effect_id="controlled-effect",
        use_register=False,
    )
    spell = SpellEvent(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=observer_uuid,
        spell_id="controlled.fire-bolt",
        spell_school="evocation",
        save_ability=AbilityName.DEXTERITY,
        save_dc=18,
        save_success=False,
        save_roll=None,
        save_bonus=3,
        use_register=False,
    )
    archive = detached_archive(roll, condition_event, damage, spell)
    party = PartyKnowledge.cold(observer_uuid, uuid4())
    roll_delivery, condition_delivery, damage_delivery, spell_delivery = [
        party_event_delivery(captured, party_event_router(party))
        for captured in archive.entries
    ]

    assert roll_delivery is not None and not isinstance(roll_delivery, KnowledgeDiagnostic)
    assert roll_delivery.knowledge.read(("result",)) == Known(True)
    assert roll_delivery.knowledge.read(("weapon_slot",)) == Known(None)
    assert condition_delivery is not None and not isinstance(
        condition_delivery,
        KnowledgeDiagnostic,
    )
    assert condition_delivery.knowledge.read(("resulting_ac",)) == Known(11)
    assert condition_delivery.knowledge.read(("condition_behavior_id",)) == Known(
        condition.behavior_id,
    )
    assert damage_delivery is not None and not isinstance(
        damage_delivery,
        KnowledgeDiagnostic,
    )
    assert damage_delivery.knowledge.read(("resulting_hp",)) == Known(12)
    assert damage_delivery.knowledge.read(("normal_hit_point_damage_cap",)) == Known(5)
    assert spell_delivery is not None and not isinstance(
        spell_delivery,
        KnowledgeDiagnostic,
    )
    assert spell_delivery.knowledge.read(("save_dc",)) == Known(18)
    assert spell_delivery.knowledge.read(("save_bonus",)) == Known(3)
    assert spell_delivery.knowledge.read(("save_roll",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("save_roll",),
    )


def test_slice_4_objective_and_subjective_formatting_share_the_captured_event() -> None:
    observer_uuid = uuid4()
    enemy_uuid = uuid4()
    attack = AttackEvent(
        source_entity_uuid=enemy_uuid,
        source_entity_name="Enemy",
        target_entity_uuid=observer_uuid,
        target_entity_name="Hero",
        weapon_slot=WeaponSlot.MELEE_MAIN,
        weapon_name="Longsword",
        attack_outcome=AttackOutcome.HIT,
        damage_types=[DamageType.SLASHING],
        identified_entity_observer_uuids={
            str(enemy_uuid): {str(observer_uuid)},
            str(observer_uuid): {str(observer_uuid)},
        },
        status_message="private objective log text must not be copied",
        use_register=False,
    )
    captured = detached_archive(attack).get(0)
    party = PartyKnowledge.cold(observer_uuid, uuid4())
    delivery = party_event_delivery(captured, party_event_router(party))

    assert delivery is not None and not isinstance(delivery, KnowledgeDiagnostic)
    assert delivery.knowledge.captured is captured
    objective_text = format_objective_event(captured)
    subjective_text = format_subjective_delivery(delivery)
    assert objective_text == format_event_knowledge(
        EventKnowledge(captured, KnowledgeMask.top()),
    )
    assert subjective_text == format_event_knowledge(delivery.knowledge)
    assert objective_text == subjective_text
    assert "private objective log text" not in objective_text
    assert "CombatLogEntry" not in objective_text
    assert "status_message" not in objective_text


def test_slice_4_visible_child_with_hidden_parent_is_a_local_text_root() -> None:
    observer_uuid = uuid4()
    enemy_uuid = uuid4()
    hidden_parent = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        use_register=False,
    )
    visible_child = AttackEvent(
        source_entity_uuid=enemy_uuid,
        source_entity_name="Enemy",
        target_entity_uuid=observer_uuid,
        target_entity_name="Hero",
        weapon_slot=WeaponSlot.MELEE_MAIN,
        weapon_name="Club",
        attack_outcome=AttackOutcome.MISS,
        parent_event=hidden_parent.uuid,
        parent_lineage=hidden_parent.lineage_uuid,
        identified_entity_observer_uuids={
            str(enemy_uuid): {str(observer_uuid)},
        },
        use_register=False,
    )
    archive = detached_archive(hidden_parent, visible_child)
    party = PartyKnowledge.cold(observer_uuid, uuid4())
    delivery = party_event_delivery(archive.get(1), party_event_router(party))

    assert delivery is not None and not isinstance(delivery, KnowledgeDiagnostic)
    text = format_subjective_delivery(delivery)
    assert text.startswith("Attack ")
    assert str(hidden_parent.uuid) not in text
    assert "Club" in text


def test_slice_4_known_base_only_occurrence_has_visible_fallback_text() -> None:
    observer_uuid = uuid4()
    step = StepMovementEvent(
        source_entity_uuid=observer_uuid,
        from_position=(0, 0),
        to_position=(1, 0),
        committed=False,
        use_register=False,
    )
    captured = detached_archive(step).get(0)
    party = PartyKnowledge.cold(observer_uuid, uuid4())
    delivery = party_event_delivery(captured, party_event_router(party))

    assert delivery is not None and not isinstance(delivery, KnowledgeDiagnostic)
    text = format_subjective_delivery(delivery)
    assert text.startswith("Movement step ")
    assert "uuid=" in text


def test_slice_4_hidden_occurrence_has_no_subjective_badge_or_text() -> None:
    hidden = AttackEvent(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
        weapon_slot=WeaponSlot.MELEE_MAIN,
        weapon_name="Hidden weapon",
        attack_outcome=AttackOutcome.HIT,
        use_register=False,
    )
    captured = detached_archive(hidden).get(0)
    party = PartyKnowledge.cold(uuid4(), uuid4())

    assert party_event_delivery(captured, party_event_router(party)) is None


def test_slice_3_3_boundary_roll_and_removal_masks_are_explicit() -> None:
    """Exact boundary families expose only their public or owned fields."""
    observer_uuid = uuid4()
    enemy_uuid = uuid4()
    encounter_uuid = uuid4()
    evidence = {str(enemy_uuid): {str(observer_uuid)}}
    condition = Prone(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=enemy_uuid,
    )
    controlled_condition = Prone(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=observer_uuid,
    )
    damage_spec = Damage(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=enemy_uuid,
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
    )
    damage_roll = DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.DAMAGE,
        results=[4],
        total=4,
        bonus=0,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=enemy_uuid,
        attack_outcome=AttackOutcome.HIT,
    )
    perceived_damage_roll = DamageRollResultEvent(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=enemy_uuid,
        identified_entity_observer_uuids=evidence,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        attack_outcome=AttackOutcome.HIT,
        damage_packets=[
            DamageRollPacket(
                damage=damage_spec,
                original_roll=damage_roll,
                final_roll=damage_roll,
            ),
        ],
        use_register=False,
    )
    controlled_damage_roll = perceived_damage_roll.model_copy(
        update={
            "uuid": uuid4(),
            "source_entity_uuid": observer_uuid,
            "target_entity_uuid": enemy_uuid,
            "identified_entity_observer_uuids": {},
        },
    )
    round_start = RoundStartEvent(
        source_entity_uuid=enemy_uuid,
        encounter_uuid=encounter_uuid,
        round_number=2,
        use_register=False,
    )
    round_end = RoundEndEvent(
        source_entity_uuid=enemy_uuid,
        encounter_uuid=encounter_uuid,
        round_number=2,
        use_register=False,
    )
    turn_start = TurnStartEvent(
        source_entity_uuid=enemy_uuid,
        entity_uuid=enemy_uuid,
        encounter_uuid=encounter_uuid,
        round_number=2,
        turn_index=1,
        actions_available=1,
        bonus_actions_available=1,
        movement_available=30,
        reaction_available=1,
        identified_entity_observer_uuids=evidence,
        use_register=False,
    )
    turn_end = TurnEndEvent(
        source_entity_uuid=enemy_uuid,
        entity_uuid=enemy_uuid,
        encounter_uuid=encounter_uuid,
        round_number=2,
        turn_index=1,
        actions_used=1,
        bonus_actions_used=1,
        movement_used=10,
        identified_entity_observer_uuids=evidence,
        use_register=False,
    )
    removal = ConditionRemovalEvent(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=enemy_uuid,
        condition=condition,
        condition_behavior_id=condition.behavior_id,
        expired=True,
        resulting_ac=13,
        resulting_max_hp=8,
        identified_entity_observer_uuids=evidence,
        use_register=False,
    )
    controlled_removal = ConditionRemovalEvent(
        source_entity_uuid=enemy_uuid,
        target_entity_uuid=observer_uuid,
        condition=controlled_condition,
        condition_behavior_id=controlled_condition.behavior_id,
        expired=False,
        resulting_ac=10,
        resulting_max_hp=7,
        use_register=False,
    )
    events = (
        round_start,
        round_end,
        turn_start,
        turn_end,
        perceived_damage_roll,
        controlled_damage_roll,
        removal,
        controlled_removal,
    )
    archive = detached_archive(*events)
    party = PartyKnowledge.cold(observer_uuid, uuid4())
    deliveries = [
        party_event_delivery(captured, party_event_router(party))
        for captured in archive.entries
    ]
    assert all(
        delivery is not None and not isinstance(delivery, KnowledgeDiagnostic)
        for delivery in deliveries
    )
    (
        round_start_delivery,
        round_end_delivery,
        turn_start_delivery,
        turn_end_delivery,
        perceived_roll_delivery,
        controlled_roll_delivery,
        removal_delivery,
        controlled_removal_delivery,
    ) = deliveries
    assert isinstance(round_start_delivery, EventDelivery)
    assert isinstance(round_end_delivery, EventDelivery)
    assert isinstance(turn_start_delivery, EventDelivery)
    assert isinstance(turn_end_delivery, EventDelivery)
    assert isinstance(perceived_roll_delivery, EventDelivery)
    assert isinstance(controlled_roll_delivery, EventDelivery)
    assert isinstance(removal_delivery, EventDelivery)
    assert isinstance(controlled_removal_delivery, EventDelivery)

    assert round_start_delivery.knowledge.read(("round_number",)) == Known(2)
    assert round_end_delivery.knowledge.read(("round_number",)) == Known(2)
    for delivery in (turn_start_delivery, turn_end_delivery):
        assert delivery.knowledge.read(("entity_uuid",)) == Known(enemy_uuid)
    for path in (("actions_available",), ("movement_available",)):
        assert turn_start_delivery.knowledge.read(path) == Unknown(
            UnknownReason.PATH_NOT_READABLE,
            path,
        )
    for path in (("actions_used",), ("bonus_actions_used",), ("movement_used",)):
        assert turn_end_delivery.knowledge.read(path) == Unknown(
            UnknownReason.PATH_NOT_READABLE,
            path,
        )
    for path in (("damage_packets",), ("attack_outcome",), ("roll_type",)):
        assert perceived_roll_delivery.knowledge.read(path) == Unknown(
            UnknownReason.PATH_NOT_READABLE,
            path,
        )
    assert controlled_roll_delivery.knowledge.read(("attack_outcome",)) == Known(
        AttackOutcome.HIT,
    )
    assert controlled_roll_delivery.knowledge.read(("weapon_slot",)) == Known(
        WeaponSlot.MELEE_MAIN,
    )
    assert removal_delivery.knowledge.read(("condition_behavior_id",)) == Known(
        condition.behavior_id,
    )
    assert removal_delivery.knowledge.read(("expired",)) == Known(True)
    assert removal_delivery.knowledge.read(("application_disposition",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("application_disposition",),
    )
    assert removal_delivery.knowledge.read(("condition",)) == Unknown(
        UnknownReason.NOT_COLD_VALUE,
        ("condition",),
    )
    assert removal_delivery.knowledge.read(("resulting_ac",)) == Unknown(
        UnknownReason.PATH_NOT_READABLE,
        ("resulting_ac",),
    )
    assert controlled_removal_delivery.knowledge.read(("resulting_ac",)) == Known(10)
    assert controlled_removal_delivery.knowledge.read(("resulting_max_hp",)) == Known(7)
    assert controlled_removal_delivery.knowledge.read(("condition",)) == Unknown(
        UnknownReason.NOT_COLD_VALUE,
        ("condition",),
    )


def test_event_reducer_captures_one_tail_and_replays_party_senses() -> None:
    first_uuid = uuid4()
    second_uuid = uuid4()
    first_cause = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    first_update = sensory_update(
        first_uuid,
        observer_position=(2, 2),
        observer_position_changed=True,
        visible_cells_added=[(2, 2)],
        seen_cells_added=[(2, 2)],
        lineage_uuid=first_cause.lineage_uuid,
        parent_event=first_cause.uuid,
        cause_event_uuid=first_cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
    )
    first_terminal = first_cause.phase_to(EventPhase.COMPLETION)
    second_cause = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    second_update = sensory_update(
        second_uuid,
        observer_position=(3, 2),
        observer_position_changed=True,
        visible_cells_added=[(3, 2)],
        seen_cells_added=[(3, 2)],
        lineage_uuid=second_cause.lineage_uuid,
        parent_event=second_cause.uuid,
        cause_event_uuid=second_cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
    )
    second_terminal = second_cause.phase_to(EventPhase.COMPLETION)
    reducer = EventReducer(first_uuid, second_uuid, source_cursor=0)

    for event in (
        first_cause,
        first_update,
        first_terminal,
        second_cause,
        second_update,
        second_terminal,
    ):
        EventQueue.register(event)

    first_batch = reducer.reduce_next_committed_tree()
    second_batch = reducer.reduce_next_committed_tree()
    assert first_batch is not None and second_batch is not None
    assert first_batch.batch_id == (EventQueue.generation_id(), 0, 3)
    assert second_batch.batch_id == (EventQueue.generation_id(), 3, 6)
    assert first_batch.start == 0 and first_batch.stop == 3
    assert second_batch.start == 3 and second_batch.stop == 6
    assert [item.source_index for item in first_batch.coverage] == list(range(3))
    assert [item.source_index for item in second_batch.coverage] == list(range(3, 6))
    assert [item.disposition for item in first_batch.coverage] == [
        SourceDisposition.INTENTIONALLY_SILENT,
        SourceDisposition.DELIVERED,
        SourceDisposition.INTENTIONALLY_SILENT,
    ]
    assert [item.disposition for item in second_batch.coverage] == [
        SourceDisposition.INTENTIONALLY_SILENT,
        SourceDisposition.DELIVERED,
        SourceDisposition.INTENTIONALLY_SILENT,
    ]
    deliveries = (*first_batch.deliveries, *second_batch.deliveries)
    assert len(deliveries) == 2
    assert {
        delivery.knowledge.captured.event_uuid
        for delivery in deliveries
    } == {first_update.uuid, second_update.uuid}
    party_delivery = next(
        delivery
        for delivery in deliveries
        if delivery.knowledge.captured.source_index == 1
    )
    objective = EventKnowledge(
        party_delivery.knowledge.captured,
        KnowledgeMask.top(),
    )
    assert objective.captured is party_delivery.knowledge.captured
    assert (
        objective.event_class,
        objective.captured.event_uuid,
        objective.captured.lineage_uuid,
    ) == (
        party_delivery.knowledge.event_class,
        party_delivery.knowledge.captured.event_uuid,
        party_delivery.knowledge.captured.lineage_uuid,
    )
    assert all(
        coverage.delivery_ids == (delivery.delivery_id,)
        for coverage, delivery in zip(
            (
                item
                for current_batch in (first_batch, second_batch)
                for item in current_batch.coverage
                if item.disposition is SourceDisposition.DELIVERED
            ),
            deliveries,
        )
    )
    assert reducer.party_knowledge.visible == frozenset({(2, 2), (3, 2)})
    assert reducer.source_cursor == 6


def test_event_reducer_repeated_fresh_reduction_has_identical_ids_and_values() -> None:
    observer_uuid = uuid4()
    cause = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    event = sensory_update(
        observer_uuid,
        visible_cells_added=[(4, 4)],
        seen_cells_added=[(4, 4)],
        lineage_uuid=cause.lineage_uuid,
        parent_event=cause.uuid,
        cause_event_uuid=cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
    )
    terminal = cause.phase_to(EventPhase.COMPLETION)
    EventQueue.register(cause)
    EventQueue.register(event)
    EventQueue.register(terminal)
    second_observer_uuid = uuid4()
    first = EventReducer(observer_uuid, second_observer_uuid, source_cursor=0)
    second = EventReducer(observer_uuid, second_observer_uuid, source_cursor=0)

    first_batch = first.reduce_next_committed_tree()
    second_batch = second.reduce_next_committed_tree()
    assert first_batch is not None and second_batch is not None

    assert first_batch.batch_id == second_batch.batch_id
    assert [item.delivery_id for item in first_batch.deliveries] == [
        item.delivery_id for item in second_batch.deliveries
    ]
    assert first_batch.coverage == second_batch.coverage
    assert first.party_knowledge == second.party_knowledge
    assert first_batch.deliveries[0].knowledge.captured.event_uuid == (
        second_batch.deliveries[0].knowledge.captured.event_uuid
    )


def test_event_reducer_rejects_reordered_split_and_generation_ranges_without_advancing() -> None:
    first = Event(
        name="first",
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        use_register=False,
    )
    terminal = first.phase_to(EventPhase.COMPLETION)
    child = Event(
        source_entity_uuid=first.source_entity_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        parent_event=first.uuid,
        use_register=False,
    )
    EventQueue.register(first)
    EventQueue.register(child)
    EventQueue.register(terminal)
    reducer = EventReducer(first.source_entity_uuid, uuid4(), source_cursor=0)

    with pytest.raises(ValueError, match="parentless root"):
        EventQueue.next_committed_tree(1)
    assert EventQueue.next_committed_tree(0) == (first, child, terminal)
    assert reducer.source_cursor == 0

    EventQueue.reset()
    with pytest.raises(RuntimeError, match="generation changed"):
        reducer.reduce_next_committed_tree()
    assert reducer.source_cursor == 0


def test_event_reducer_rejects_cursor_duplicate_or_merged_history_without_advancing() -> None:
    first_uuid = uuid4()
    second_uuid = uuid4()
    first = Event(
        source_entity_uuid=first_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        use_register=False,
    )
    first_terminal = first.phase_to(EventPhase.COMPLETION)
    second = Event(
        source_entity_uuid=second_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        use_register=False,
    )
    second_terminal = second.phase_to(EventPhase.COMPLETION)
    reducer = EventReducer(first_uuid, second_uuid, source_cursor=0)

    for event in (first, first_terminal, second, second_terminal):
        EventQueue.register(event)

    first_batch = reducer.reduce_next_committed_tree()
    second_batch = reducer.reduce_next_committed_tree()
    assert first_batch is not None and second_batch is not None
    assert first_batch.batch_id == (EventQueue.generation_id(), 0, 2)
    assert second_batch.batch_id == (EventQueue.generation_id(), 2, 4)
    assert reducer.source_cursor == 4
    assert len(reducer.archives) == 2
    assert reducer.reduce_next_committed_tree() is None


def test_event_reducer_unadmitted_occurrence_has_error_coverage_without_payload() -> None:
    class UnadmittedEvent(Event):
        secret: str

    observer_uuid = uuid4()
    event = UnadmittedEvent(
        source_entity_uuid=observer_uuid,
        event_type=EventType.TRIGGER_EVENT,
        secret="not a delivery",
        use_register=False,
    )
    EventQueue.register(event)
    terminal = event.phase_to(EventPhase.COMPLETION)
    EventQueue.register(terminal)
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)

    batch = reducer.reduce_next_committed_tree()

    assert batch is not None
    assert batch.deliveries == ()
    assert batch.coverage == (
        SourceCoverage(
            generation_id=EventQueue.generation_id(),
            source_index=0,
            event_uuid=event.uuid,
            disposition=SourceDisposition.ERROR,
        ),
        SourceCoverage(
            generation_id=EventQueue.generation_id(),
            source_index=1,
            event_uuid=terminal.uuid,
            disposition=SourceDisposition.ERROR,
        ),
    )
    assert batch.diagnostics == (
        KnowledgeDiagnostic(
            reason=UnknownReason.NO_CLASS_POLICY,
            source_index=0,
            event_class=type(event).__qualname__,
            detail="no exact concrete-event-class policy",
        ),
        KnowledgeDiagnostic(
            reason=UnknownReason.NO_CLASS_POLICY,
            source_index=1,
            event_class=type(terminal).__qualname__,
            detail="no exact concrete-event-class policy",
        ),
    )
    assert reducer.source_cursor == 2


def test_slice_3_3_hidden_committed_change_updates_reference_without_party_memory() -> None:
    observer_uuid = uuid4()
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)
    hidden_change = SpatialChangeEvent(
        source_entity_uuid=uuid4(),
        change_type=SpatialChangeType.TILE_CHANGED,
        position=(4, 4),
        tile_surface=TileSurface(base_material=Material.STONE),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    hidden_root = hidden_change.model_copy(update={
        "phase": EventPhase.EFFECT,
        "is_first": True,
        "is_last": False,
    })
    register_effect_tree(hidden_root)

    batch = reducer.reduce_next_committed_tree()

    assert batch.coverage[0].disposition is SourceDisposition.HIDDEN
    assert reducer.party_knowledge == PartyKnowledge.cold(
        observer_uuid,
        reducer.party_knowledge.second.observer_uuid,
    )
    position_refs = {
        key: value
        for key, value in reducer.provenance.items()
        if key[0] == (4, 4)
    }
    assert position_refs[((4, 4), ("tile_surface",))] == (
        EventQueue.generation_id(),
        1,
        ("tile_surface",),
    )
    assert ((4, 4), ("position",)) not in reducer.provenance

    cause = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    reveal = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        parent_event=cause.uuid,
        lineage_uuid=cause.lineage_uuid,
        cause_event_uuid=cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(4, 4)],
    )
    register_effect_tree(cause, reveal)
    reveal_batch = reducer.reduce_next_committed_tree()
    late = next(
        delivery
        for delivery in reveal_batch.deliveries
        if delivery.knowledge.captured.source_index == 1
    )
    assert late.knowledge.read(("tile_surface",)) == Known(
        TileSurface(base_material=Material.STONE),
    )
    assert reducer.party_knowledge.visible == frozenset({(4, 4)})


def test_slice_3_3_sensory_grant_resolves_one_closed_causative_terminal() -> None:
    observer_uuid = uuid4()
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)
    cause = Event(
        source_entity_uuid=observer_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    sensory = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        lineage_uuid=cause.lineage_uuid,
        parent_event=cause.uuid,
        cause_event_uuid=cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(6, 6)],
    )
    terminal = cause.phase_to(EventPhase.COMPLETION)
    for event in (cause, sensory, terminal):
        EventQueue.register(event)

    batch = reducer.reduce_next_committed_tree()

    sensory_delivery = next(
        delivery
        for delivery in batch.deliveries
        if delivery.knowledge.captured.event_uuid == sensory.uuid
    )
    assert sensory_delivery.disclosure_cause_source_index == 2
    assert reducer.party_knowledge.visible == frozenset({(6, 6)})
    assert sensory_delivery.knowledge.known_items(("visible_cells_added",)) == Known(
        ((6, 6),),
    )


def test_slice_3_3_hidden_replacement_reacquisition_uses_latest_stable_reference_only() -> None:
    observer_uuid = uuid4()
    tile = WorldTileState(
        tile_uuid=uuid4(),
        position=(4, 4),
        surface=TileSurface(base_material=Material.STONE),
        name="Original stone",
        blocks_optics=False,
        blocks_propagation=False,
        walking_cost=1,
        flying_cost=1,
        swimming_cost=1,
        burrowing_cost=1,
        elevation_steps=0,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        default_light=LightLevel.BRIGHT_LIGHT,
        resolved_light=LightLevel.BRIGHT_LIGHT,
    )
    world = WorldInitializedEvent(
        source_entity_uuid=observer_uuid,
        battlefield_id="battlefield.hidden_replacement",
        battlefield_name="Hidden Replacement",
        bounds=(0, 0, 5, 5),
        width=5,
        height=5,
        tiles=(tile,),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    register_world_lifecycle(world)
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)
    reducer.reduce_next_committed_tree()

    hidden_change = SpatialChangeEvent(
        source_entity_uuid=uuid4(),
        change_type=SpatialChangeType.TILE_CHANGED,
        position=(4, 4),
        tile_surface=TileSurface(base_material=Material.WATER),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    hidden_root = hidden_change.model_copy(update={
        "phase": EventPhase.EFFECT,
        "is_first": True,
        "is_last": False,
    })
    register_effect_tree(hidden_root)
    hidden_batch = reducer.reduce_next_committed_tree()
    assert hidden_batch.coverage[0].disposition is SourceDisposition.HIDDEN
    assert reducer.provenance[((4, 4), ("tile_surface",))] == (
        EventQueue.generation_id(),
        5,
        ("tile_surface",),
    )

    cause = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    reveal = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        parent_event=cause.uuid,
        lineage_uuid=cause.lineage_uuid,
        cause_event_uuid=cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(4, 4)],
    )
    register_effect_tree(cause, reveal)
    batch = reducer.reduce_next_committed_tree()

    late = next(
        delivery
        for delivery in batch.deliveries
        if delivery.knowledge.captured.source_index == 5
    )
    assert late.knowledge.read(("tile_surface",)) == Known(
        TileSurface(base_material=Material.WATER),
    )
    assert not any(
        delivery.knowledge.captured.source_index == 4
        and ("tiles", 0, "surface") in delivery.knowledge.mask.paths
        for delivery in batch.deliveries
    )


def test_slice_3_3_missing_causative_terminal_is_fatal_without_advancing() -> None:
    observer_uuid = uuid4()
    sensory = sensory_update(
        observer_uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(7, 7)],
    )
    EventQueue.register(sensory)
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)

    assert reducer.reduce_next_committed_tree() is None

    assert reducer.source_cursor == 0
    assert reducer.archives == ()
    assert reducer.party_knowledge.visible == frozenset()
    assert reducer.provenance == {}


def test_slice_3_3_reacquisition_keeps_old_source_and_uses_new_batch_disclosure() -> None:
    observer_uuid = uuid4()
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)

    first_cause = SpatialChangeEvent(
        source_entity_uuid=uuid4(),
        change_type=SpatialChangeType.TILE_CHANGED,
        position=(8, 8),
        tile_surface=TileSurface(base_material=Material.STONE),
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    first_sensory = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        lineage_uuid=first_cause.lineage_uuid,
        parent_event=first_cause.uuid,
        cause_event_uuid=first_cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(8, 8)],
    )
    first_terminal = first_cause.phase_to(EventPhase.COMPLETION)
    for event in (first_cause, first_sensory, first_terminal):
        EventQueue.register(event)
    first_batch = reducer.reduce_next_committed_tree()
    loss_cause = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    lost = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        parent_event=loss_cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_removed=[(8, 8)],
    )
    register_effect_tree(loss_cause, lost)
    reducer.reduce_next_committed_tree()
    assert reducer.party_knowledge.visible == frozenset()

    second_cause = Event(
        source_entity_uuid=observer_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    second_sensory = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        lineage_uuid=second_cause.lineage_uuid,
        parent_event=second_cause.uuid,
        cause_event_uuid=second_cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(8, 8)],
    )
    second_terminal = second_cause.phase_to(EventPhase.COMPLETION)
    for event in (second_cause, second_sensory, second_terminal):
        EventQueue.register(event)
    second_batch = reducer.reduce_next_committed_tree()

    current = next(
        delivery
        for delivery in second_batch.deliveries
        if delivery.knowledge.captured.event_uuid == second_sensory.uuid
    )
    late = next(
        delivery
        for delivery in second_batch.deliveries
        if delivery.knowledge.captured.source_index == 2
    )
    assert current.disclosure_cause_source_index == 8
    assert late.disclosure_cause_source_index == 8
    assert late.knowledge.captured.source_index == 2
    assert late.delivery_id != first_batch.deliveries[0].delivery_id
    assert second_batch.coverage[1].delivery_ids == (
        current.delivery_id,
        late.delivery_id,
    )

    third_cause = Event(
        source_entity_uuid=observer_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    third_sensory = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        lineage_uuid=third_cause.lineage_uuid,
        parent_event=third_cause.uuid,
        cause_event_uuid=third_cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(8, 8)],
    )
    third_terminal = third_cause.phase_to(EventPhase.COMPLETION)
    for event in (third_cause, third_sensory, third_terminal):
        EventQueue.register(event)
    third_batch = reducer.reduce_next_committed_tree()
    third_late = next(
        delivery
        for delivery in third_batch.deliveries
        if delivery.knowledge.captured.source_index == 2
    )
    assert third_late.knowledge.captured.source_index == 2
    assert third_late.disclosure_cause_source_index == 11
    assert third_late.delivery_id != late.delivery_id
    assert reducer.party_knowledge.visible == frozenset({(8, 8)})


def test_slice_3_3_wrong_lineage_causative_terminal_is_fatal() -> None:
    observer_uuid = uuid4()
    cause = Event(
        source_entity_uuid=observer_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    sensory = sensory_update(
        observer_uuid,
        phase=EventPhase.COMPLETION,
        parent_event=cause.uuid,
        cause_event_uuid=cause.uuid,
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(9, 9)],
    )
    wrong_lineage_terminal = cause.phase_to(EventPhase.COMPLETION).model_copy(
        update={"lineage_uuid": uuid4()},
    )
    for event in (cause, sensory):
        EventQueue.register(event)
    with pytest.raises(ValueError, match="active root|exact class|lineage"):
        EventQueue.register(wrong_lineage_terminal)
    reducer = EventReducer(observer_uuid, uuid4(), source_cursor=0)

    assert reducer.reduce_next_committed_tree() is None

    assert reducer.source_cursor == 0
    assert reducer.archives == ()
    assert reducer.party_knowledge.visible == frozenset()


def test_slice_3_3_real_engine_wall_light_and_boundary_replay() -> None:
    reset_senses_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    observer_uuid = uuid4()
    other_observer_uuid = uuid4()
    reducer = EventReducer(observer_uuid, other_observer_uuid, source_cursor=0)
    grid = get_map()
    near_wall = build_directional_wall(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    far_wall = build_directional_wall(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    grid.place_object(
        near_wall.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    grid.place_object(
        far_wall.uuid,
        (2, 0),
        boundary_direction=CardinalDirection.WEST,
    )
    grid.add_light_source((0, 0), bright_radius_feet=5, dim_radius_feet=0)
    target = create_test_monster(
        "monster.skeleton",
        source_id=uuid4(),
        name="Beyond boundary",
        position=(3, 0),
        darkvision=False,
    )
    observer = create_test_monster(
        "monster.skeleton",
        source_id=observer_uuid,
        name="Near observer",
        position=(0, 0),
        darkvision=False,
    )
    other_observer = create_test_monster(
        "monster.skeleton",
        source_id=other_observer_uuid,
        name="Far observer",
        position=(5, 0),
        darkvision=False,
    )
    reduced_batches = reducer.drain_committed_trees()
    committed_events = tuple(
        event for _index, event in EventQueue.iter_events_since(0)
    )

    near_placement = next(
        placement
        for placement in grid.get_all_object_placements()
        if placement.object_uuid == near_wall.uuid
    )
    far_placement = next(
        placement
        for placement in grid.get_all_object_placements()
        if placement.object_uuid == far_wall.uuid
    )
    assert observer.uuid == observer_uuid
    assert other_observer.uuid == other_observer_uuid
    assert reduced_batches
    assert grid.get_boundary_objects_at(
        (1, 0), CardinalDirection.EAST,
    ) == {near_wall.uuid}
    assert grid.get_boundary_objects_at(
        (2, 0), CardinalDirection.WEST,
    ) == {far_wall.uuid}
    assert observer.senses.objects[near_wall.uuid].visual is True
    assert far_wall.uuid not in observer.senses.objects
    assert target.uuid not in observer.senses.entities
    assert observer.senses.effective_light_levels[(0, 0)] is LightLevel.BRIGHT_LIGHT

    assert reducer.party_knowledge.objects[near_wall.uuid].visual is True
    assert far_wall.uuid not in reducer.party_knowledge.objects
    assert target.uuid not in reducer.party_knowledge.entities
    assert reducer.party_knowledge.effective_light_levels[(0, 0)] is LightLevel.BRIGHT_LIGHT
    near_source_indices = {
        index
        for index, event in enumerate(committed_events)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == near_wall.uuid
    }
    late_near = next(
        delivery
        for batch in reversed(reduced_batches)
        for delivery in batch.deliveries
        if delivery.knowledge.captured.source_index in near_source_indices
    )
    assert late_near.knowledge.read(("placement",)) == Known(near_placement)
    assert far_placement != near_placement


def test_slice_3_3_real_engine_replays_invisibility_special_sense_and_steps() -> None:
    reset_senses_state(width=8, height=1)
    observer_uuid = uuid4()
    special_observer_uuid = uuid4()
    reducer = EventReducer(observer_uuid, special_observer_uuid, source_cursor=0)
    setup_cursor = EventQueue.event_cursor()
    target = create_test_monster(
        "monster.skeleton",
        source_id=uuid4(),
        name="Target",
        position=(3, 0),
        darkvision=False,
    )
    observer = create_test_monster(
        "monster.skeleton",
        source_id=observer_uuid,
        name="Visual observer",
        position=(0, 0),
        darkvision=False,
    )
    special_observer = create_test_monster(
        "monster.skeleton",
        source_id=special_observer_uuid,
        name="Special observer",
        position=(6, 0),
        darkvision=False,
    )
    set_modes(
        special_observer.uuid,
        [SenseMode(sense_type=SensesType.BLINDSIGHT, range_feet=20)],
    )
    assert observer.senses.entities[target.uuid].visual is True
    assert special_observer.senses.entities[target.uuid].visual is True
    target.set_invisible(True)

    pre_move_events = tuple(
        event
        for _index, event in EventQueue.iter_events_since(setup_cursor)
    )
    pre_move_batches = reducer.drain_committed_trees()
    assert observer.uuid == observer_uuid
    assert special_observer.uuid == special_observer_uuid
    invisibility_updates = [
        event
        for event in pre_move_events
        if isinstance(event, SensoryUpdateEvent)
        and event.update_reason is SensoryUpdateReason.PERCEIVABILITY
    ]
    assert any(
        observer.uuid in {event.observer_uuid for event in invisibility_updates}
        and target.uuid in event.entity_contacts_removed
        for event in invisibility_updates
    )
    assert any(
        special_observer.uuid == event.observer_uuid
        and event.entity_contacts_changed.get(target.uuid) == (
            special_observer.senses.entities[target.uuid]
        )
        and event.entity_contacts_changed[target.uuid].visual is False
        for event in invisibility_updates
    )
    assert target.uuid not in observer.senses.entities
    assert special_observer.senses.entities[target.uuid].visual is False
    assert reducer.party_knowledge.entities[target.uuid].visual is False
    assert reducer.party_knowledge.entities[target.uuid].special_senses == (
        SensesType.BLINDSIGHT,
    )
    assert reducer.party_knowledge.entities[target.uuid] == (
        special_observer.senses.entities[target.uuid]
    )
    assert pre_move_batches and all(batch.coverage for batch in pre_move_batches)

    observer.materialize_navigation(max_distance=8)
    movement_cursor = EventQueue.event_cursor()
    movement = Move(
        source_entity_uuid=observer.uuid,
        end_position=(1, 0),
        use_movement_cost=False,
    ).apply()
    assert movement is not None and not movement.canceled
    movement_events = tuple(
        event
        for _index, event in EventQueue.iter_events_since(movement_cursor)
    )
    movement_batches = reducer.drain_committed_trees()
    entered = [
        event
        for event in movement_events
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.SPATIAL_ENTITY_ENTERED
        and event.phase is EventPhase.COMPLETION
        and event.entity_uuid == observer.uuid
    ]
    self_updates = [
        event
        for event in movement_events
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == observer.uuid
        and event.update_reason is SensoryUpdateReason.SELF_MOVEMENT
    ]
    assert [event.position for event in entered] == [(1, 0)]
    assert [event.observer_position for event in self_updates] == [(1, 0)]
    assert sum(len(batch.coverage) for batch in movement_batches) == len(movement_events)
    assert reducer.source_cursor == EventQueue.event_cursor()
    assert reducer.party_knowledge.entities[target.uuid] == (
        special_observer.senses.entities[target.uuid]
    )
