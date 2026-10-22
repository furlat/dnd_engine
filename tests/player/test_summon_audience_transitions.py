"""Ordered recorded control, observation and removal; no live owners during replay."""

from copy import deepcopy
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from dnd.blocks.sensory import published_senses, spatial_senses_system
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType
from dnd.core.base_actions import ActionEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, EmptyLogData
from dnd.core.events import ControllerAssignmentChangedEvent, EventPhase, EventQueue, SensoryUpdateEvent
from dnd.player.application import capture_application_operation, initialize_audiences
from dnd.player.content_composition import ui_content_manifest
from dnd.player.session import Operation
from dnd.player.audience import AudienceComposition, AudiencePerception, PlayerAudience, apply_settlement, assign_control, composed_view
from dnd.player.capture import capture_interval, capture_lineages
from dnd.player.facts import AudienceFact, BodyRecord, PlayerNode
from dnd.player.projection import SessionProjection, begin_projection, project_lineage
from dnd.player.recorded import RecordedSequence, project_sequence
from dnd.player.reduction import occurrence_order, reduce_initialization, reduce_lineage
from dnd.types.controller import ControllerExecutionMode
from dnd.types.senses import PerceivedContact
from dnd.spells.conjuration import GreaseZone
from tests.player.test_duration_spatial_review import activate, consume, view
from tests.player.test_audience_local_composition import delta, effect
from tests.player.test_recorded_boundary import world
from tests.player.test_emitted_update_replica import session
from tests.sensory_cells import cells


def assignment(actor, owner, *, previous=None, parent=None):
    return EventQueue.publish_completed_fact(ControllerAssignmentChangedEvent(
        source_entity_uuid=actor, entity_uuid=actor, previous_controller_uuid=None,
        controller_uuid=uuid4() if owner is not None else None, previous_execution_mode=None,
        execution_mode=ControllerExecutionMode.EXTERNAL if owner is not None else None,
        previous_external_owner_uuid=previous, new_external_owner_uuid=owner,
        parent_event=parent, phase=EventPhase.COMPLETION, use_register=False))


def test_owner_anchor_controls_observation_without_expanding_other_seats():
    first, second, summon, spectator = (UUID(int=i) for i in range(1, 5))
    owning = PlayerAudience((first, second), (first,))
    foreign = PlayerAudience((spectator,), (spectator, second))
    # Sharing an external controller does not share another caster's senses.
    controlled = assign_control(owning, summon, None, second)
    assert controlled.controlled == (first, second, summon)
    assert controlled.observers == (first,)
    assert assign_control(foreign, summon, None, second) is foreign
    rebound = assign_control(controlled, summon, second, first)
    assert rebound.observers == (first, summon)
    assert assign_control(rebound, summon, first, first) is rebound
    revoked = assign_control(rebound, summon, first, None)
    assert revoked.controlled == owning.controlled and revoked.observers == owning.observers
    assert revoked.revision == 3
    assert assign_control(owning, first, None, None) is owning


@pytest.mark.parametrize('removed_index', [0, 1, 2])
def test_removing_a_member_matches_cold_composition_and_keeps_other_contacts(removed_index):
    identities = tuple(UUID(int=i) for i in (11, 12, 13))
    audience = PlayerAudience(identities, identities)
    current = AudienceComposition()
    subject, shared_effect = UUID(int=20), UUID(int=21)
    events = [delta(identity, initial=True, visible_cells_added=[(index, 0), (4, 0)],
        effective_light_levels_changed={(index, 0): 1, (4, 0): index + 1},
        entity_contacts_changed={subject: PerceivedContact(position=(4, 0), visual=True)},
        spatial_effects_changed={shared_effect: effect(((index, 0), (4, 0)))})
        for index, identity in enumerate(identities)]
    apply_settlement(current, audience, identities[0], events)
    old = deepcopy(current.perception)
    removed = identities[removed_index]
    after = replace(audience, controlled=tuple(i for i in identities if i != removed),
        observers=tuple(i for i in identities if i != removed), revision=1)
    change = apply_settlement(current, after, after.observers[0], (), removed=(removed,))
    expected = AudiencePerception({i: value for i, value in old.members.items() if i != removed})
    assert current.perception == expected
    assert current.view == composed_view(expected, after.observers[0])
    assert subject in current.view.entities
    assert cells(change.visible_removed) == {(removed_index, 0)}
    assert not change.retired  # Lost sight is not witnessed destruction.
    assert set(current.order) == set(after.observers)


@pytest.mark.parametrize('same_group', [False, True])
def test_grant_observe_revoke_replay_uses_membership_at_each_event(world, same_group):
    _, built, (owner, summon) = world
    owner.update_entity_senses(max_distance=2)
    audience = PlayerAudience((owner.uuid,), (owner.uuid,))
    envelope = capture_interval(name='ordered ownership', start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=owner.uuid, audience=audience,
        battlefield_id=built.definition.battlefield_id)
    session = SessionProjection()
    projection, initial = begin_projection(session, envelope)
    state = reduce_initialization(initial)
    saved = deepcopy(state)
    root = ActionEvent(source_entity_uuid=owner.uuid) if same_group else None
    parent = root.uuid if root is not None else None
    grant = assignment(summon.uuid, owner.uuid, parent=parent)
    contact = UUID(int=999)
    observation = delta(summon.uuid, initial=True, visible_cells_added=[(18, 18)],
        entity_contacts_changed={contact: PerceivedContact(position=(18, 18), visual=True)})
    observation = EventQueue.publish_completed_fact(observation.model_copy(update={'parent_event': parent, 'cause_event_uuid': parent}))
    revoke = assignment(summon.uuid, None, previous=owner.uuid, parent=parent)
    # This late private sensory update must be absent from this seat's capture.
    late = EventQueue.publish_completed_fact(delta(summon.uuid, visible_cells_added=[(19, 19)]).model_copy(
        update={'parent_event': parent, 'cause_event_uuid': parent}))
    roots = (root.phase_to(EventPhase.COMPLETION),) if root is not None else (grant, observation, revoke, late)
    natives = capture_lineages(roots, observer_uuid=owner.uuid, audience=audience,
        omit_foreign_sensory_payloads=True)
    publics = []
    for native in natives:
        public = project_lineage(session, projection, native)
        if public is not None:
            publics.append(public)
            granted = set(state.viewing_audience.controlled)
            for row in occurrence_order(public.events, public.bodies):
                if isinstance(row, PlayerNode) and isinstance(row.fact, AudienceFact):
                    granted = set(row.fact.audience.controlled)
                if isinstance(row, BodyRecord) and row.body.controlled_items is not None:
                    assert row.actor_uuid in granted, "Private body details must follow the control grant"
            state = reduce_lineage(state, public)
    facts = [node.fact for group in publics for node in group.events if isinstance(node.fact, AudienceFact)]
    assert [fact.audience.revision for fact in facts] == [1, 2]
    assert facts[0].audience.controlled == (owner.uuid, summon.uuid)
    assert facts[1].audience.controlled == (owner.uuid,)
    assert state.viewing_audience == projection.audience == facts[-1].audience
    assert (18, 18) not in cells(state.senses.visible)
    assert (18, 18) in cells(state.senses.seen)
    assert (19, 19) not in cells(state.senses.seen)
    assert contact not in state.senses.entities
    assert state.actors[summon.uuid].controlled_items is None
    assert saved == reduce_initialization(initial)
    assert owner.uuid in projection.audience_composition.perception.members
    assert summon.uuid not in projection.audience_composition.perception.members
    if same_group:
        assert publics[0].sensory_rows.contact_members  # 1→2→1 must retain explicit member columns.
    archive = RecordedSequence(initialization=envelope, lineages=natives).model_dump_json()
    replay = project_sequence(RecordedSequence.model_validate_json(archive, context=PASSIVE_EVENT_REPLAY))
    assert replay.lineages == tuple(publics)


def test_standalone_logs_use_membership_when_logged_not_the_final_roster(session):
    catalog = ui_content_manifest()
    runtimes, _ = initialize_audiences(session, catalog)
    caster = session.player_uuids[0]
    actor = next(identity for identity in session.game.entities if identity not in session.player_uuids)
    session.logs.log_appends.clear()
    session.logs.log_cursors.clear()
    start = EventQueue.event_cursor()

    def log(text):
        EventQueue.push_combat_log(CombatLogEntry(entry_type=CombatLogEntryType.ACTION,
            source_uuid=str(actor), source_name=session.game.entities[actor].name,
            compact=text, verbose=text, detailed=text, data=EmptyLogData(),
            perceiver_uuids={str(actor)}), actor)

    log('before grant')
    grant = assignment(actor, caster)
    log('during ownership')
    revoke = assignment(actor, None, previous=caster)
    log('after revocation')
    operation = Operation(start_cursor=start, end_cursor=EventQueue.event_cursor(), roots=(grant, revoke),
        original_logs=tuple(session.logs.log_appends), original_log_cursors=tuple(session.logs.log_cursors))
    updates = capture_application_operation(runtimes, operation, catalog)
    messages = [append.entry.compact for update in updates.values() for append in update.combat_log_appends]
    assert messages == ['during ownership']


def test_repeated_grant_removal_discards_observer_layers_even_without_visible_cells():
    anchor = UUID(int=100)
    audience = PlayerAudience((anchor,), (anchor,))
    current = AudienceComposition()
    apply_settlement(current, audience, anchor, (delta(anchor, initial=True),))
    for index in range(10):
        member = UUID(int=101 + index)
        audience = assign_control(audience, member, None, anchor)
        apply_settlement(current, audience, anchor, (delta(member, initial=True,
            visible_cells_added=[] if index % 2 else [(index, 0)]),))
        audience = assign_control(audience, member, anchor, None)
        apply_settlement(current, audience, anchor, (), removed=(member,))
        assert tuple(current.perception.members) == (anchor,)
        assert current.order == (anchor,)
        assert current.view == composed_view(current.perception, anchor)
    assert audience.revision == 20


def test_released_actor_stops_disclosing_its_private_field_clock(world):
    _, built, (owner, summon) = world
    projection, state = view(built, (owner,))
    grant = assignment(summon.uuid, owner.uuid)
    spatial_senses_system.publish_observer_refresh(summon.uuid, published_senses(summon.senses),
        initial=True, parent_event=grant)
    state, _ = consume(projection, state, (grant,))
    zone = GreaseZone(source_entity_uuid=summon.uuid, position=(5, 7), affected_positions={(5, 7)},
        duration=Duration(duration_type=DurationType.ROUNDS, duration=3))
    state, _ = consume(projection, state, (activate(zone, summon),))
    assert state.senses.spatial_effects[zone.uuid].duration.remaining_rounds == 3
    revoke = assignment(summon.uuid, None, previous=owner.uuid)
    state, _ = consume(projection, state, (revoke,))
    cause = ActionEvent(source_entity_uuid=summon.uuid)
    assert not zone.progress_spatial_duration(parent_event=cause)
    state, delivered = consume(projection, state, (cause.phase_to(EventPhase.COMPLETION),))
    assert zone.duration.duration == 2
    assert state.senses.spatial_effects[zone.uuid].duration.remaining_rounds == 3
    assert not delivered, 'The former owner must not receive later private field-clock ticks'
