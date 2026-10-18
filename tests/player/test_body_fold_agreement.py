"""A seat's client fold of a body agrees with the engine's fold of the same recording.

Each case appends one recorded native fact to a live-recorded startup and
compares the body fields both folds hold: the client's, from the projected
packets, and the engine's, `dnd.actor_projection.apply_actor_fact_change` of the
same recording's actor change: a condition's temporary hit points, an INTERNAL
condition's stats and a seen enemy's destroyed equipped layer each reach the seat
as their own change rows.
"""

from dataclasses import dataclass, replace
import random
from typing import Callable
from uuid import uuid4

import pytest

from dnd.actor_projection import actor_fact_change, apply_actor_fact_change
from dnd.core.condition_types import ConditionDurationSummary, DurationType
from dnd.blocks.base_item import ItemResourceChangeEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.condition_types import ConditionAgencyDenial, ConditionCategory
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.item_types import ItemEffectPresentationState, ItemPresentationState
from dnd.player.capture import CompletedLineage, capture_interval, reduce_interval
from dnd.player.actor_projection import apply_presented_change
from dnd.player.application import initialize_audiences
from dnd.player.bodies import change_fact, change_rows, change_views, entering_body, shown_items, View
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import PlayerActor, PlayerState, PlayerWorld
from dnd.player.projection import SessionProjection, begin_projection, project_lineage
from dnd.player.recorded import RecordedSequence
from dnd.player.reduction import apply_actor_change_fact, enter_body, reduce_initialization, reduce_lineage
from dnd.player.session import Session, close_session, create_session
from dnd.player.static_sent import StaticSent
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.actor import ConditionState, EntityStatsState, TemporaryHitPointsGrant
from dnd.types.actor_facts import ActorFactChange, ActorState, ConditionFact, HeldItem, ItemResources
from tests.player.test_projection_local_world import objective




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
    if not case.controlled:
        # The party sees the enemy: a live fact on it carries its observers' identity grant.
        event = event.model_copy(update={"identified_entity_observer_uuids": {
            str(identity): frozenset(str(observer) for observer in audience.observers)}})
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
            instance_uuid=uuid4(), source_id='condition.test.recorded_ward')))), id='temporary-hp'),
    pytest.param(FoldCase('internal condition raises armor class', True, lambda actor: condition_fact(
        actor, ConditionCategory.INTERNAL, stats_of(actor, armor_class=actor.armor_class + 2))), id='internal-ac'),
    pytest.param(FoldCase('seen enemy\'s equipped item is destroyed', False, destroyed_layer), id='ghost-layer'),
)


@pytest.mark.parametrize('case', CASES)
def test_client_body_fold_matches_the_engine_fold_of_the_same_recording(session, case):
    check(session, case)


# The rows of one change, applied by the client fold, reproduce the session fold's after-values for the fields the
# change names (coordinator ruling (a): the one conversion keys collections against the session fold's before).

def rounds(remaining: int) -> ConditionDurationSummary:
    return ConditionDurationSummary(duration_type=DurationType.ROUNDS, remaining_rounds=remaining)


def member(actor: ActorState, remaining: int) -> ConditionFact:
    """A status membership `actor` holds, lasting `remaining` rounds."""
    _, fact = condition_fact(actor, ConditionCategory.STATUS, stats_of(actor))
    assert fact.state is not None
    return replace(fact, resulting_stats=None, state=fact.state.model_copy(update={"duration": rounds(remaining)}))


def worn(actor: ActorState) -> tuple[str, ItemPresentationState]:
    slot, identity = actor.equipment[0]
    return slot, next(item for item in actor.items if item.item_uuid == identity)


def ward(actor: ActorState) -> tuple[ActorState, ActorFactChange]:
    fact = member(actor, 3)
    return actor, ActorFactChange(actor.uuid, {"armor_class": actor.armor_class + 1, "temporary_hp": 5},
        conditions_set=(fact,))


def ward_ticks(actor: ActorState) -> tuple[ActorState, ActorFactChange]:
    fact = member(actor, 3)
    held = replace(actor, conditions=(*actor.conditions, fact))
    assert fact.state is not None
    return held, ActorFactChange(actor.uuid, conditions_set=(replace(fact, state=fact.state.model_copy(update={
        "duration": rounds(2)})),))


def ward_ends(actor: ActorState) -> tuple[ActorState, ActorFactChange]:
    fact = member(actor, 3)
    return replace(actor, conditions=(fact, *actor.conditions)), ActorFactChange(actor.uuid,
        conditions_removed=(fact.condition_uuid,))


def new_item_worn(actor: ActorState) -> tuple[ActorState, ActorFactChange]:
    _, item = worn(actor)
    return actor, ActorFactChange(actor.uuid, {"armor_class": actor.armor_class + 2}, held_item=HeldItem(
        item.model_copy(update={"item_uuid": uuid4()}), "Neck"))


def rewear(actor: ActorState) -> tuple[ActorState, ActorFactChange]:
    slot, item = worn(actor)
    return actor, ActorFactChange(actor.uuid, held_item=HeldItem(item, slot))


def moved(actor: ActorState) -> tuple[ActorState, ActorFactChange]:
    _, item = worn(actor)
    return actor, ActorFactChange(actor.uuid, held_item=HeldItem(item, "Neck"))


def released(actor: ActorState) -> tuple[ActorState, ActorFactChange]:
    _, item = worn(actor)
    return actor, ActorFactChange(actor.uuid, released_by_owner=item.item_uuid)


def charges(actor: ActorState) -> tuple[ActorState, ActorFactChange]:
    item = actor.items[-1]
    return actor, ActorFactChange(actor.uuid, used_item=ItemResources(item.item_uuid, 3, item.stack_count, False))


def destroyed(actor: ActorState) -> tuple[ActorState, ActorFactChange]:
    _, item = worn(actor)
    return actor, ActorFactChange(actor.uuid, used_item=ItemResources(item.item_uuid, 0, 0, True))


def lit(actor: ActorState) -> tuple[ActorState, ActorFactChange]:
    _, item = worn(actor)
    _, effect = condition_fact(actor, ConditionCategory.STATUS, stats_of(actor))
    return actor, ActorFactChange(None, replaced_item=item.model_copy(update={"is_lit": not item.is_lit,
        "item_effects": (*item.item_effects, ItemEffectPresentationState(effect_uuid=effect.condition_uuid,
            behavior_id="condition.test.recorded_flame", duration=rounds(4)))}))


@dataclass(frozen=True)
class RowCase:
    name: str
    controlled: bool
    change: Callable[[ActorState], tuple[ActorState, ActorFactChange]]


ROW_CASES = tuple(pytest.param(RowCase(name, controlled, build), id=f"{name}-{'controller' if controlled else 'observer'}")
    for name, build in (("membership-set", ward), ("membership-duration", ward_ticks), ("membership-end", ward_ends),
                        ("new-item-worn", new_item_worn), ("rewear-own-slot", rewear), ("move-slot", moved),
                        ("released", released), ("charges", charges), ("destroyed-worn", destroyed),
                        ("item-lit-and-effects", lit))
    for controlled in (True, False))


def seat_view(audience, actor: ActorState) -> PlayerState:
    """A client holding `actor`'s body as it enters this seat's view."""
    seat = PlayerState(generation=uuid4(), observer_uuid=audience.observers[0], world=PlayerWorld(
        battlefield_id="rows", battlefield_name="Rows", bounds=(0, 0, 1, 1), width=2, height=2), audience=audience)
    enter_body(seat, entering_body(0, actor, audience, visual=True, birth=True, sent=StaticSent(), pending=StaticSent()))
    return seat


@pytest.mark.parametrize("case", ROW_CASES)
def test_change_rows_reproduce_the_session_fold_for_the_fields_they_name(session, case):
    runtimes, _ = initialize_audiences(session, ui_content_manifest())
    runtime = runtimes["party"]
    audience = runtime.projection.audience
    identity = next(identity for identity, actor in runtime.session.actors.items()
        if audience.controls(identity) is case.controlled and actor.equipment and len(actor.items) > 1)
    held, change = case.change(runtime.session.actors[identity])
    before = {**runtime.session.actors, identity: held}
    after = dict(before)
    apply_presented_change(after, change)
    # The owner's fact, identified by the seat (an observer sees it as the event's identified owner).
    header = Event.model_validate(dict(source_entity_uuid=identity, target_entity_uuid=identity,
        event_type=EventType.CONDITION_APPLICATION, phase=EventPhase.COMPLETION, use_register=False,
        identified_entity_observer_uuids={str(identity): frozenset(map(str, audience.observers))}),
        context=PASSIVE_EVENT_REPLAY)
    client = seat_view(audience, held)
    sent = StaticSent(item_looks=set(client.items),
        item_profiles={key for key, row in client.items.items() if row.profile})
    fact = change_fact(header, change_views(change_rows(change, before), before, after), audience, {identity}, None,
        sent=sent, pending=StaticSent())
    if fact is not None:
        apply_actor_change_fact(client, fact)
    expected = seat_view(audience, after[identity])
    assert client.actors[identity] == expected.actors[identity], case.name
    view = View.CONTROLLER if case.controlled else View.OBSERVER
    assert {key: client.items[key] for key in shown_items(after[identity], view)} == expected.items, case.name
