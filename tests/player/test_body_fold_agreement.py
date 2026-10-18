"""A seat's client fold of a body agrees with the engine's fold of the same recording.

Each case appends one recorded native fact to a live-recorded startup and
compares the body fields both folds hold: the client's, from the projected
packets, and the engine's, `dnd.actor_projection.apply_actor_fact_change` of the
same recording's actor change. The expected failures are latent on today's head (the live
engine also emits a second fact that repairs the body); they turn green
with E3-bodies of agent_docs/plans/EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18.md.
"""

from dataclasses import dataclass
import random
from typing import Callable
from uuid import uuid4

import pytest

from dnd.actor_projection import actor_fact_change, apply_actor_fact_change
from dnd.blocks.base_item import ItemResourceChangeEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.condition_types import ConditionAgencyDenial, ConditionCategory
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.player.capture import CompletedLineage, capture_interval, reduce_interval
from dnd.player.facts import PlayerActor
from dnd.player.projection import SessionProjection, begin_projection, project_lineage
from dnd.player.recorded import RecordedSequence
from dnd.player.reduction import reduce_initialization, reduce_lineage
from dnd.player.session import Session, close_session, create_session
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.actor import ConditionState, EntityStatsState, TemporaryHitPointsGrant
from dnd.types.actor_facts import ActorState, ConditionFact
from tests.player.test_projection_local_world import objective


PLAN = 'turns green with E3-bodies (EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 §5 E1)'


@pytest.fixture
def session():
    state = random.getstate()
    random.seed(0)
    value = create_session()
    try:
        yield value
    finally:
        close_session(value)
        reset_engine_runtime()
        random.setstate(state)


def condition_fact(actor: ActorState, category: ConditionCategory, stats: EntityStatsState
                   ) -> tuple[Event, ConditionFact]:
    """A recorded condition application on `actor`: its header and its committed fact."""
    header = Event.model_validate(dict(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid,
        event_type=EventType.CONDITION_APPLICATION, phase=EventPhase.COMPLETION, use_register=False),
        context=PASSIVE_EVENT_REPLAY)
    identity = uuid4()
    state = ConditionState(condition_uuid=identity, name='Recorded Ward', category=category,
        semantic_key='condition.test.recorded_ward', tags=(), removal_triggers=(),
        agency_denial=ConditionAgencyDenial.NONE, outcome_protections=())
    return header, ConditionFact(event_uuid=header.uuid, condition_uuid=identity, name=state.name,
        category=category, behavior_id=None, resulting_max_hp=None, resulting_ac=None, state=state,
        resulting_stats=stats)


def stats_of(actor: ActorState, **changes) -> EntityStatsState:
    """The actor's recorded stats with the case's changed after-values."""
    return EntityStatsState(normal_hp=actor.normal_hp, maximum_hp=actor.maximum_hp,
        temporary_hp=actor.temporary_hp, temporary_hp_grant=actor.temporary_hp_grant,
        armor_class=actor.armor_class, resolved_size=actor.resolved_size,
        spatial_disposition=actor.spatial_disposition, healing_blocked=actor.healing_blocked,
        damage_affinities=actor.damage_affinities).model_copy(update=changes)


def destroyed_layer(actor: ActorState) -> tuple[Event, None]:
    """A recorded consumption that destroys the actor's first equipped item."""
    identity = actor.equipment[0][1]
    item = next(row for row in actor.items if row.item_uuid == identity)
    return ItemResourceChangeEvent.model_validate(dict(source_entity_uuid=actor.uuid, item_uuid=identity,
        item_id=item.item_id, charges_before=0, charges_after=0, stack_count_before=1, stack_count_after=1,
        item_destroyed=True, phase=EventPhase.COMPLETION, use_register=False), context=PASSIVE_EVENT_REPLAY), None


@dataclass(frozen=True)
class FoldCase:
    name: str
    # Which body: a party member (controlled, self-observed) or an enemy the party sees.
    controlled: bool
    fact: Callable[[ActorState], tuple[Event, ConditionFact | None]]


def client_body(actor: PlayerActor) -> dict[str, object]:
    """The client's body fields that the engine fold also holds (`engine_body`)."""
    return dict(normal_hp=actor.normal_hp, maximum_hp=actor.maximum_hp, temporary_hp=actor.temporary_hp,
        temporary_hp_grant=actor.temporary_hp_grant, armor_class=actor.armor_class,
        layers=tuple((row.slot, row.item_uuid) for row in actor.visual_loadout.layers))


def engine_body(actor: ActorState) -> dict[str, object]:
    """The engine fold's body fields that the client also holds (`client_body`)."""
    return dict(normal_hp=actor.normal_hp, maximum_hp=actor.maximum_hp, temporary_hp=actor.temporary_hp,
        temporary_hp_grant=actor.temporary_hp_grant, armor_class=actor.armor_class, layers=actor.equipment)


def check(session: Session, case: FoldCase) -> None:
    audience = session.seats['party']
    startup = capture_interval(name='startup', start_cursor=0, end_cursor=EventQueue.event_cursor(),
        observer_uuid=audience.observers[0], audience=audience,
        battlefield_id=session.battlefield.definition.battlefield_id)
    engine, _ = reduce_interval(None, startup)
    identity = next(identity for identity in engine.actors
        if audience.controls(identity) is case.controlled and engine.actors[identity].equipment)
    before = engine.actors[identity]
    event, fact = case.fact(before)
    index = startup.end_cursor
    change = actor_fact_change(event, fact)
    assert change is not None
    # The recording carries the actor change its capture records for the fact.
    lineage = CompletedLineage(generation=startup.generation, observer_uuid=startup.observer_uuid, root=event,
        events=(event,), objective_rows=(objective(index, event),), start_cursor=index, end_cursor=index + 1,
        conditions=() if fact is None else (fact,), audience=audience, actor_fact_changes={event.uuid: change})
    recorded = RecordedSequence.model_validate_json(RecordedSequence(initialization=startup,
        lineages=(lineage,)).model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    projected = SessionProjection()
    projection, initial = begin_projection(projected, recorded.initialization)
    client = reduce_initialization(initial)
    assert client_body(client.actors[identity]) == engine_body(before), case.name
    packet = project_lineage(projected, projection, recorded.lineages[0])
    if packet is not None:
        client = reduce_lineage(client, packet)
    actors = {identity: before}
    apply_actor_fact_change(actors, change)
    expected = engine_body(actors[identity])
    assert expected != engine_body(before), case.name
    assert client_body(client.actors[identity]) == expected, case.name


CASES = (
    # Smoke: a visible condition's armor class reaches its own seat today.
    pytest.param(FoldCase('visible condition raises armor class', True, lambda actor: condition_fact(
        actor, ConditionCategory.STATUS, stats_of(actor, armor_class=actor.armor_class + 2))), id='visible-ac'),
    pytest.param(FoldCase('condition grants temporary hit points', True, lambda actor: condition_fact(
        actor, ConditionCategory.STATUS, stats_of(actor, temporary_hp=7, temporary_hp_grant=TemporaryHitPointsGrant(
            instance_uuid=uuid4(), source_id='condition.test.recorded_ward')))), id='temporary-hp',
        marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
            'the client folds a condition\'s resulting_stats without temporary_hp and its grant '
            '(reduction.py ConditionChangeFact) while the engine applies them (actor_projection.actor_fact_change); '
            f'latent on head: every live writer also emits TemporaryHitPointsChangedEvent; {PLAN}'))),
    pytest.param(FoldCase('internal condition raises armor class', True, lambda actor: condition_fact(
        actor, ConditionCategory.INTERNAL, stats_of(actor, armor_class=actor.armor_class + 2))), id='internal-ac',
        marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
            'an INTERNAL condition publishes no fact (projection._project_fact), so its resulting_stats never '
            f'reach the seat while the engine fold applies them; no live reproduction found on head; {PLAN}'))),
    pytest.param(FoldCase('seen enemy\'s equipped item is destroyed', False, destroyed_layer), id='ghost-layer',
        marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
            'only the controller receives ItemChargeFact (projection._project_fact), so other seats keep the '
            'destroyed item\'s loadout layer while the engine fold removes it; latent on head: the engine '
            f'publishes ItemLocationState(DESTROYED) first, which already sends a gear observation; {PLAN}'))),
)


@pytest.mark.parametrize('case', CASES)
def test_client_body_fold_matches_the_engine_fold_of_the_same_recording(session, case):
    check(session, case)
