"""One logical world change publishes one fact and settles each observer once (plan §5.5, P2)."""

from collections import Counter
from contextlib import contextmanager
from dnd.action_timing import reset_action_count_recorder, set_action_count_recorder
from dnd.core.base_block import LightLevel
from dnd.core.condition_types import DurationType
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import Event, EventPhase, EventQueue, EventType, SpatialChangeEvent
from dnd.core.gridmap import get_map
from dnd.spatial.area_conditions import AreaCondition
from dnd.spells.conjuration import FogCloudZone
from dnd.types.spatial_effects import SpatialEffectLayer, SpatialEffectOccupancyPolicy
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state


def _content_ref(name: str) -> ContentRef:
    return ContentRef(pack_id="test.settlement", definition_kind=ContentDefinitionKind.CONDITION,
        content_id=f"condition.settlement.{name}", content_version=1, definition_contract_hash="0" * 64)


def _cause(source_uuid) -> Event:
    return Event(name="Settlement test cause", event_type=EventType.BASE_ACTION, phase=EventPhase.EFFECT,
        source_entity_uuid=source_uuid)


@contextmanager
def _counting():
    counts: Counter[str] = Counter()
    token = set_action_count_recorder(lambda name, value: counts.update({name: value}))
    try:
        yield counts
    finally:
        reset_action_count_recorder(token)


def _completed(cursor: int, event_type: EventType) -> list:
    return [event for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type is event_type and event.phase is EventPhase.COMPLETION and not event.canceled]


def _tile_rows(cursor: int) -> list[dict[tuple[int, int], int]]:
    """Walking cost per cell carried by each committed tile fact's keyed changes since `cursor`."""
    facts = _completed(cursor, EventType.SPATIAL_TILE_CHANGED)
    assert all(isinstance(fact, SpatialChangeEvent) for fact in facts)
    return [{change.position: change.fields["walking_cost"] for change in fact.keyed_tile_changes} for fact in facts]


def test_terrain_install_and_removal_each_publish_one_tile_fact() -> None:
    """Difficult terrain over six cells is one committed tile fact, not six."""
    reset_senses_state(width=8, height=3)
    observer = create_skeleton(name="Observer", position=(0, 1), darkvision=False)
    cells = {(x, 1) for x in range(3, 7)} | {(3, 0), (4, 0)}
    zone = AreaCondition(name="Test mud", source_entity_uuid=observer.uuid, content_ref=_content_ref("mud"),
        position=(3, 1), affected_positions=set(cells), layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING, adds_difficult_terrain=True)

    cursor = EventQueue.event_cursor()
    with _counting() as counts:
        assert zone.activate(parent_event=_cause(observer.uuid)) is not None
    assert _tile_rows(cursor) == [{cell: 2 for cell in cells}]
    assert counts["sensory.full_recompute"] == 0

    cursor = EventQueue.event_cursor()
    assert zone.deactivate(parent_event=_cause(observer.uuid))
    assert _tile_rows(cursor) == [{cell: 1 for cell in cells}]


def test_duration_tick_refreshes_the_effect_without_resolving_observers() -> None:
    """A surviving tick changes only the observed duration: one reducer pass, no recompute."""
    reset_senses_state(width=8, height=3)
    observer = create_skeleton(name="Observer", position=(0, 1), darkvision=False)
    zone = FogCloudZone(source_entity_uuid=observer.uuid, position=(4, 0), affected_positions={(4, 0), (4, 1)})
    zone.duration.duration_type = DurationType.ROUNDS
    zone.duration.duration = 3
    assert zone.activate(parent_event=_cause(observer.uuid)) is not None
    observed = set(observer.senses.spatial_effects)
    assert zone.uuid in observed, sorted(map(str, observed))

    with _counting() as counts:
        assert not zone.progress_spatial_duration(parent_event=_cause(observer.uuid))
    assert counts["sensory.full_recompute"] == 0
    assert counts["sensory.reducer_call"] == 1
    observed_duration = observer.senses.spatial_effects[zone.uuid].duration
    assert observed_duration == zone.snapshot_duration(), (str(observed_duration), str(zone.snapshot_duration()))


def test_one_blocker_change_publishes_one_light_fact_for_every_source_it_moves() -> None:
    """Two torches re-lit by one new wall: one light fact for the cause, not one per source."""
    reset_senses_state(width=9, height=3, default_light=LightLevel.DARKNESS)
    create_skeleton(name="Observer", position=(0, 1), darkvision=False)
    grid = get_map()
    grid.add_light_source((2, 1), bright_radius_feet=15, dim_radius_feet=0)
    grid.add_light_source((6, 1), bright_radius_feet=15, dim_radius_feet=0)

    cursor = EventQueue.event_cursor()
    grid.set_tile(4, 1, blocks_optics=True, blocks_propagation=True, default_light=LightLevel.DARKNESS)
    light_facts = (_completed(cursor, EventType.SPATIAL_LIGHT_CHANGED)
        + _completed(cursor, EventType.SPATIAL_LIGHT_SOURCES_CHANGED))
    assert len(light_facts) == 1


def _settlements(cursor: int) -> list[tuple[object, int | None]]:
    """Each sensory update since `cursor`: its observer and settlement marker, in order."""
    return [(event.observer_uuid, event.settlement) for event in _completed(cursor, EventType.SENSORY_UPDATE)]


def test_observers_settled_together_share_one_settlement() -> None:
    """One change settles every observer it reaches in one pass, marked as one settlement; the next change is
    another settlement."""
    reset_senses_state(width=8, height=3)
    first = create_skeleton(name="First", position=(0, 1), darkvision=False)
    second = create_skeleton(name="Second", position=(7, 1), darkvision=False)
    zone = FogCloudZone(source_entity_uuid=first.uuid, position=(4, 0), affected_positions={(4, 0), (4, 1)})

    cursor = EventQueue.event_cursor()
    assert zone.activate(parent_event=_cause(first.uuid)) is not None
    settled = _settlements(cursor)
    assert {observer for observer, _ in settled} == {first.uuid, second.uuid}
    markers = {marker for _, marker in settled}
    assert len(markers) == 1 and None not in markers

    cursor = EventQueue.event_cursor()
    assert zone.deactivate(parent_event=_cause(first.uuid))
    later = {marker for _, marker in _settlements(cursor)}
    assert len(later) == 1 and later.isdisjoint(markers)
