"""Which seat receives which body change: the disclosure of the bodies wire (player schema 16).

Two seats perceive the same party member: the party seat controls it, a goblin's seat only sees it. The controller
receives the member's inventory, item state and durations; the observer its memberships without durations, its
stats, layers and the effects of what it wears; nobody receives an INTERNAL membership, and a change nobody may
see sends no fact at all.
"""

from dataclasses import replace
from uuid import uuid4, uuid5

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.condition_types import ConditionCategory
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.item_types import ItemEffectPresentationState
from dnd.player.actor_projection import apply_presented_change
from dnd.player.application import capture_application_operation, initialize_audiences
from dnd.player.audience import PlayerAudience
from dnd.player.bodies import change_fact, change_rows, change_views
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import ActorChangeFact, PlayerUpdate
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import Session, publish_sheets
from dnd.player.static_sent import StaticSent
from dnd.spells.conjuration import Darkness
from dnd.spells.evocation import Fireball
from dnd.types.actor_facts import ActorFactChange, ActorState, ChangeField, ConditionRow
from tests.player.test_body_fold_agreement import (charges, condition_fact, lit, new_item_worn, released, rounds,
    stats_of, ward, ward_ticks)
from tests.player.test_emitted_update_replica import (INITIALIZATION, Step, cast, enemies, operation_since,
    session)  # noqa: F401  (the session fixture)


def watched(session: Session):
    """The party seat and a seat watching through a goblin, initialized."""
    goblin = enemies(session)[0].uuid
    # A seat that sees through the goblin and controls nothing.
    session.seats['goblin'] = PlayerAudience((), (goblin,))
    sorcerer = session.player_uuids[1]
    session.game.entities[sorcerer].action_economy.set_normal_spell_slot_capacity(
        uuid5(sorcerer, 'disclosure'), {level: 4 for level in range(1, 10)})
    publish_sheets(session)
    return initialize_audiences(session, ui_content_manifest())


def test_live_memberships_reach_the_controller_with_durations_and_the_observer_without(session):
    runtimes, initializations = watched(session)
    catalog = ui_content_manifest()
    clients = {seat: reduce_initialization(INITIALIZATION.validate_json(INITIALIZATION.dump_json(initial)))
               for seat, initial in initializations.items()}
    rows: dict[str, list[ConditionRow]] = {seat: [] for seat in runtimes}
    for step in (Step('darkness west of the party', cast(Darkness, (6, 11), 2)),
                 Step('fireball on the goblins', cast(Fireball, (14, 11), 3))):
        start = EventQueue.event_cursor()
        step.act(session)
        updates = capture_application_operation(runtimes, operation_since(session, start), catalog)
        for seat, update in updates.items():
            update = PlayerUpdate.model_validate_json(update.model_dump_json())
            clients[seat] = reduce_operation(clients[seat], update)
            rows[seat] += [row for lineage in update.lineages for event in lineage.events
                           if isinstance(event.fact, ActorChangeFact) for change in event.fact.actors
                           if change.actor_uuid == session.player_uuids[1]
                           for row in change.rows if isinstance(row, ConditionRow) and row.member is not None]
    # The caster's concentration: its controller holds the duration, the goblin the membership alone.
    assert any(row.member.state.duration is not None for row in rows['party'] if row.member and row.member.state)
    assert rows['goblin'] and all(row.member.state is None or row.member.state.duration is None
                                  for row in rows['goblin'] if row.member)
    # INTERNAL memberships (the damage taken, the spell cast) reach no seat.
    assert all(member.category is not ConditionCategory.INTERNAL for client in clients.values()
               for actor in client.actors.values() for member in actor.conditions)


def hidden_only(actor: ActorState) -> tuple[ActorState, ActorFactChange]:
    _, fact = condition_fact(actor, ConditionCategory.INTERNAL, stats_of(actor))
    return actor, ActorFactChange(actor.uuid, conditions_set=(replace(fact, resulting_stats=None),))


def unworn(actor: ActorState):
    worn = {identity for _, identity in actor.equipment}
    return next(item for item in actor.items if item.item_uuid not in worn)


def unworn_effects(actor: ActorState) -> tuple[ActorState, ActorFactChange]:
    item = unworn(actor)
    return actor, ActorFactChange(None, replaced_item=item.model_copy(update={"item_effects": (
        ItemEffectPresentationState(effect_uuid=uuid4(), behavior_id="condition.test.unworn_glow",
            duration=rounds(4)),)}))


F = ChangeField
CASES = (
    # name, change, the party's fields (None: no fact), the goblin's fields
    ('a membership set', ward, {F.ARMOR_CLASS, F.TEMPORARY_HP, F.CONDITION}, {F.ARMOR_CLASS, F.TEMPORARY_HP, F.CONDITION}),
    ('a duration tick', ward_ticks, {F.CONDITION_DURATION}, None),
    ('a hidden-only change', hidden_only, None, None),
    ('a new item worn', new_item_worn, {F.ARMOR_CLASS, F.INVENTORY, F.LAYER}, {F.ARMOR_CLASS, F.LAYER}),
    ('a worn item released', released, {F.INVENTORY, F.LAYER}, {F.LAYER}),
    ('charges spent', charges, {F.ITEM_STATE}, None),
    ('a worn light lit, with an effect', lit, {F.ITEM_STATE, F.ITEM_EFFECTS, F.LAYER}, {F.ITEM_EFFECTS, F.LAYER}),
    ("an unworn item's effects", unworn_effects, {F.ITEM_EFFECTS}, None),
)


@pytest.mark.parametrize("name, build, controller, observer", CASES, ids=[row[0] for row in CASES])
def test_each_view_receives_the_rows_disclosed_to_it(session, name, build, controller, observer):
    runtimes, _ = watched(session)
    actors = runtimes['party'].session.actors
    identity = next(identity for identity, actor in actors.items() if identity in session.player_uuids
                    and actor.equipment and len(actor.items) > len(actor.equipment))
    held, change = build(actors[identity])
    before = {**actors, identity: held}
    after = dict(before)
    apply_presented_change(after, change)
    views = change_views(change_rows(change, before), before, after)
    received = {}
    for seat in ('party', 'goblin'):
        projection = runtimes[seat].projection
        audience = projection.audience
        header = Event.model_validate(dict(source_entity_uuid=identity, target_entity_uuid=identity,
            event_type=EventType.CONDITION_APPLICATION, phase=EventPhase.COMPLETION, use_register=False,
            identified_entity_observer_uuids={str(identity): frozenset(map(str, audience.observers))}),
            context=PASSIVE_EVENT_REPLAY)
        fact = change_fact(header, views, audience, {identity}, projection.audience_composition.view,
            sent=StaticSent(), pending=StaticSent())
        rows = [row for actor in (fact.actors if fact is not None else ()) if actor.actor_uuid == identity
                for row in actor.rows]
        received[seat] = {row.field for row in rows} or None
        if seat == 'goblin' and fact is not None:
            # What the goblin sees carries no duration and no item's state or profile.
            assert all(effect.duration is None for record in fact.items for effect in record.effects), name
            assert all(record.state is None and record.profile is None for record in fact.items), name
    assert received == {'party': controller, 'goblin': observer}, name
