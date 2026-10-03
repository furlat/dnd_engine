"""Native membership admission, committed publication and exact sustain loss."""

from uuid import uuid4

import pytest

from dnd.conditions import Concentrating, Invisible, InvisibilityEffect, GreaterInvisibilityEffect
from dnd.core.base_block import BaseBlock, PreparedConditionApplication
from dnd.core.base_conditions import BaseCondition, ConditionRemovalEvent
from dnd.core.condition_types import (
    ConditionTag, InvoluntarySustainLoss, SustainLossCause, SustainLossPolicy,
)
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.entity import Entity, EntityConfig
from dnd.core.gridmap import get_map
from dnd.spells.abjuration import AntimagicFieldZone, BanishedCondition
from dnd.spells.transmutation import HasteEffect
from tests.engine.test_combat_actions import reset_core_action_state, strong_entity
from dnd.types.summoning import SummonDepartureCause, TerminalOwnerRelease
from tests.engine.support import reset_combat_state


@pytest.fixture(autouse=True)
def reset():
    reset_combat_state()
    yield
    reset_combat_state()


def owner(name: str) -> Entity:
    return Entity.create(source_entity_uuid=uuid4(), name=name, config=EntityConfig())


def condition(actor: BaseBlock, name: str, **kwargs) -> BaseCondition:
    return BaseCondition(name=name, source_entity_uuid=actor.uuid,
                         target_entity_uuid=actor.uuid, **kwargs)


def completions(kind: EventType):
    return [event for event in EventQueue.get_events_by_type(kind)
            if event.phase is EventPhase.COMPLETION]


def test_prepared_replacement_keeps_previous_authority_until_committed_and_publishes_once():
    actor = owner('Recipient')
    previous = condition(actor, 'Effect')
    actor.add_condition(previous)
    old_completion_count = len(completions(EventType.CONDITION_APPLICATION))
    replacement = condition(actor, 'Effect')
    prepared = actor.prepare_condition_application(replacement)
    assert isinstance(prepared, PreparedConditionApplication)
    assert actor.active_conditions['Effect'] is previous
    assert previous.applied and not replacement.applied
    assert len(completions(EventType.CONDITION_APPLICATION)) == old_completion_count
    settled = []
    hook = BaseBlock.register_condition_graph_settled_hook(
        lambda rows: settled.append((rows, actor.active_conditions['Effect'].uuid,
                                    len(completions(EventType.CONDITION_APPLICATION)))))
    try:
        with BaseBlock.condition_removal_scope():
            actor.commit_condition_application(prepared)
            assert actor.active_conditions['Effect'] is replacement
            assert not previous.applied
            assert not settled
            assert not completions(EventType.CONDITION_REMOVAL)
            actor.publish_condition_application(prepared)
            actor.publish_condition_application(prepared)
            assert not settled
        assert len(settled) == 1
        rows, active_uuid, count = settled[0]
        assert [row.condition_uuid for row in rows] == [previous.uuid]
        assert active_uuid == replacement.uuid and count == old_completion_count + 1
        assert len(completions(EventType.CONDITION_REMOVAL)) == 1
    finally:
        BaseBlock.remove_condition_graph_settled_hook(hook)


def test_canceled_new_concentration_preparation_preserves_previous_effect_and_slot():
    caster, recipient = owner('Caster'), owner('Recipient')
    previous = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                             spell_name='Previous')
    child = condition(recipient, 'Existing effect')
    recipient.add_condition(child)
    caster.add_condition(previous)
    previous.add_linked_condition(recipient.uuid, child.uuid)
    before_slots = previous.snapshot_concentration_slots()
    incoming = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                             spell_name='Incoming')
    prepared = caster.prepare_condition_application(incoming)
    assert isinstance(prepared, PreparedConditionApplication)
    assert caster.active_conditions['Concentrating'] is previous
    assert recipient.active_conditions['Existing effect'] is child
    assert previous.snapshot_concentration_slots() == before_slots
    assert not completions(EventType.CONDITION_REMOVAL)
    caster.cancel_condition_application(prepared, 'Later deployment rejected')
    assert caster.active_conditions['Concentrating'] is previous
    assert recipient.active_conditions['Existing effect'] is child
    assert previous.snapshot_concentration_slots() == before_slots
    assert not completions(EventType.CONDITION_REMOVAL)


def test_involuntary_sustain_loss_releases_required_branch_despite_unrelated_veto():
    caster, required_actor, ordinary_actor = owner('Caster'), owner('Required'), owner('Ordinary')
    concentration = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                                  spell_name='Mixed ownership')
    required = condition(required_actor, 'Required existence', sustain_loss_policy=SustainLossPolicy.REQUIRED)
    ordinary = condition(ordinary_actor, 'Ordinary effect')
    required_actor.add_condition(required)
    ordinary_actor.add_condition(ordinary)
    caster.add_condition(concentration)
    concentration.add_linked_condition(required_actor.uuid, required.uuid)
    concentration.add_linked_condition(ordinary_actor.uuid, ordinary.uuid)

    def veto(event, _source):
        if isinstance(event, ConditionRemovalEvent):
            return event.cancel(status_message='Ordinary veto')
        return None

    caster.add_event_handler(EventHandler(name='Removal veto', source_entity_uuid=caster.uuid,
        event_processor=veto, trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL,
                                                           event_phase=EventPhase.DECLARATION)]))
    cause = Event(event_type=EventType.DAMAGE_APPLIED, source_entity_uuid=caster.uuid)
    loss = InvoluntarySustainLoss(SustainLossCause.FAILED_SAVE, concentration.uuid, cause.uuid)
    assert not caster.release_involuntary_sustain(loss)
    assert not required.applied and 'Required existence' not in required_actor.active_conditions
    assert ordinary.applied and concentration.applied
    assert (required_actor.uuid, required.uuid) not in concentration.linked_conditions
    assert all((required_actor.uuid, required.uuid) not in slot.linked_entries
               for slot in concentration.concentration_slots.values())
    removals = completions(EventType.CONDITION_REMOVAL)
    assert len(removals) == 1
    assert removals[0].condition.uuid == required.uuid


def test_terminal_removal_is_exact_and_child_receipts_keep_existence_context():
    actor = owner('Ending actor')
    existence = condition(actor, 'Existence')
    child = condition(actor, 'Control', parent_condition=existence.uuid)
    actor.add_condition(existence)
    actor.add_condition(child)
    existence.sub_conditions.append(child.uuid)
    release = TerminalOwnerRelease(entity_uuid=actor.uuid, existence_condition_uuid=existence.uuid,
                                   cause=SummonDepartureCause.EXPIRED)
    rows = []
    hook = BaseBlock.register_condition_graph_settled_hook(lambda batch: rows.extend(batch))
    try:
        with pytest.raises(ValueError, match='exact existence'):
            actor.remove_condition_by_uuid(child.uuid, terminal_release=release)
        assert actor.remove_condition_by_uuid(existence.uuid, terminal_release=release)
        assert not actor.active_conditions
        assert [row.condition_uuid for row in rows] == [child.uuid, existence.uuid]
        assert all(row.terminal_release == release for row in rows)
        assert all(EventQueue.get_event_by_uuid(row.removal_event_uuid) is not None for row in rows)
    finally:
        BaseBlock.remove_condition_graph_settled_hook(hook)


def test_settled_callback_failure_does_not_skip_other_committed_cleanup():
    actor = owner('Recipient')
    effect = condition(actor, 'Effect')
    actor.add_condition(effect)
    observed = []

    def failing(_receipts):
        raise RuntimeError('First cleanup failed')

    first = BaseBlock.register_condition_graph_settled_hook(failing)
    second = BaseBlock.register_condition_graph_settled_hook(lambda rows: observed.extend(rows))
    try:
        with pytest.raises(RuntimeError, match='First cleanup failed'):
            actor.remove_condition('Effect')
        assert not effect.applied
        assert [row.condition_uuid for row in observed] == [effect.uuid]
        assert len(completions(EventType.CONDITION_REMOVAL)) == 1
    finally:
        BaseBlock.remove_condition_graph_settled_hook(first)
        BaseBlock.remove_condition_graph_settled_hook(second)


class FailingRemovalPublication(BaseCondition):
    def on_membership_changed(self, event: Event) -> None:
        if not self.applied:
            raise RuntimeError('Native resulting-state publisher failed')


def test_publication_failure_still_settles_committed_membership_and_remaining_facts():
    actor = owner('Recipient')
    effect = FailingRemovalPublication(name='Effect', source_entity_uuid=actor.uuid,
                                       target_entity_uuid=actor.uuid)
    actor.add_condition(effect)
    settled = []
    hook = BaseBlock.register_condition_graph_settled_hook(lambda rows: settled.extend(rows))
    try:
        with pytest.raises(BaseExceptionGroup, match='publication failed'):
            actor.remove_condition('Effect')
        assert not effect.applied and not actor.active_conditions
        assert [row.condition_uuid for row in settled] == [effect.uuid]
        assert len(completions(EventType.CONDITION_REMOVAL)) == 1
    finally:
        BaseBlock.remove_condition_graph_settled_hook(hook)




@pytest.mark.parametrize('condition_type', [Invisible, InvisibilityEffect, GreaterInvisibilityEffect, HasteEffect])
@pytest.mark.parametrize('failure', ['cancel', 'raise'])
def test_failed_incoming_effect_leaves_no_flag_grant_or_modifier(condition_type, failure):
    actor = owner('Recipient')
    before = actor.snapshot_entity_stats()
    incoming = condition_type(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)

    def reject(event, _source):
        if failure == 'raise':
            raise RuntimeError('Effect admission failed')
        return event.cancel(status_message='Effect admission rejected')

    actor.add_event_handler(EventHandler(name='Reject effect', source_entity_uuid=actor.uuid,
        event_processor=reject, trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION,
            event_phase=EventPhase.EFFECT, event_target_entity_uuid=actor.uuid)]))
    if failure == 'raise':
        with pytest.raises(RuntimeError, match='Effect admission failed'):
            actor.prepare_condition_application(incoming)
    else:
        denied = actor.prepare_condition_application(incoming)
        assert isinstance(denied, Event) and denied.canceled
    assert actor.snapshot_entity_stats() == before
    assert not actor.is_invisible
    assert not actor.action_economy.get_restricted_action_grants()
    assert not actor.active_conditions
    assert not incoming.applied


def test_exception_in_replacement_removal_unwinds_incoming_haste():
    actor = owner('Recipient')
    previous = HasteEffect(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)
    actor.add_condition(previous)
    before = actor.snapshot_entity_stats()
    grants = actor.action_economy.get_restricted_action_grants()
    incoming = HasteEffect(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)

    def fail(event, _source):
        raise RuntimeError('Replacement admission failed')

    actor.add_event_handler(EventHandler(name='Reject replacement', source_entity_uuid=actor.uuid,
        event_processor=fail, trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL,
            event_phase=EventPhase.EFFECT, event_target_entity_uuid=actor.uuid)]))
    with pytest.raises(RuntimeError, match='Replacement admission failed'):
        actor.prepare_condition_application(incoming)
    assert actor.active_conditions['Haste'] is previous
    assert actor.snapshot_entity_stats() == before
    assert actor.action_economy.get_restricted_action_grants() == grants
    assert set(actor.active_conditions) == {'Haste'}


@pytest.mark.parametrize('condition_type', [Invisible, InvisibilityEffect, GreaterInvisibilityEffect, HasteEffect])
def test_native_removal_commit_is_silent_and_publishes_consequences_afterward(condition_type):
    actor = owner('Recipient')
    effect = condition_type(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)
    actor.add_condition(effect)
    prepared = BaseBlock.prepare_owned_condition_removals((actor,), parent_event=None)
    assert prepared is not None
    with BaseBlock.condition_removal_scope():
        cursor = EventQueue.event_cursor()
        BaseBlock.commit_owned_condition_removals(prepared)
        assert EventQueue.event_cursor() == cursor
        assert not actor.active_conditions
        assert not actor.is_invisible
        assert not actor.action_economy.get_restricted_action_grants()
        BaseBlock.publish_owned_condition_removals(prepared)
        if condition_type is HasteEffect:
            assert 'Haste Lethargy' in actor.active_conditions
        cursor = EventQueue.event_cursor()
        BaseBlock.publish_owned_condition_removals(prepared)
        assert EventQueue.event_cursor() == cursor


def banishment_scene():
    reset_core_action_state()
    caster = strong_entity('Caster', (1, 1), 'heroes')
    target = strong_entity('Banished', (3, 3), 'monsters')
    occupant = strong_entity('Occupant', (4, 3), 'monsters')
    banished = BanishedCondition(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    target.add_condition(banished)
    previous = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                             spell_name='Banishment')
    caster.add_condition(previous)
    previous.add_linked_condition(target.uuid, banished.uuid)
    Entity.update_entity_position(occupant, target.position)
    return caster, target, occupant, previous, banished


def test_banishment_return_is_reserved_and_canceled_replacement_does_not_relocate():
    caster, target, occupant, previous, banished = banishment_scene()
    incoming = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                             spell_name='Rejected replacement')
    prepared = caster.prepare_condition_application(incoming)
    assert isinstance(prepared, PreparedConditionApplication)
    assert set(incoming.prepared_removal_occupancies()) == {(3, 3), (3, 4)}
    assert target.is_spatially_suspended and occupant.position == (3, 3)
    caster.cancel_condition_application(prepared, 'Incoming summon cannot claim return tile')
    assert caster.active_conditions['Concentrating'] is previous
    assert banished.applied and target.is_spatially_suspended
    assert occupant.position == (3, 3)
    assert not banished.prepared_removal_occupancies()


def test_banishment_return_and_displacement_commit_without_callbacks():
    caster, target, occupant, _previous, banished = banishment_scene()
    incoming = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                             spell_name='Replacement')
    prepared = caster.prepare_condition_application(incoming)
    assert isinstance(prepared, PreparedConditionApplication)
    observed = []
    def observe(event):
        if event.event_type is EventType.SPATIAL_ENTITY_ENTERED:
            observed.append((caster.active_conditions.get('Concentrating'), target.position, occupant.position))
    EventQueue.add_on_event_callback(observe)
    try:
        with BaseBlock.condition_removal_scope():
            cursor = EventQueue.event_cursor()
            caster.commit_condition_application(prepared)
            assert EventQueue.event_cursor() == cursor and not observed
            assert not banished.applied and target.is_deployed
            assert get_map().get_entities_at((3, 3)) == {target.uuid}
            assert occupant.position == (3, 4)
            caster.publish_condition_application(prepared)
            assert observed and all(row == (incoming, (3, 3), (3, 4)) for row in observed)
    finally:
        EventQueue.remove_on_event_callback(observe)


def test_exception_after_banishment_admission_cancels_return_and_keeps_old_graph():
    caster, target, occupant, previous, banished = banishment_scene()
    child = condition(caster, 'Second effect')
    caster.add_condition(child)
    previous.add_linked_condition(caster.uuid, child.uuid)
    incoming = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                             spell_name='Replacement')
    def fail(event, _source):
        if isinstance(event, ConditionRemovalEvent) and event.condition.uuid == child.uuid:
            raise RuntimeError('Second child admission failed')
        return None
    caster.add_event_handler(EventHandler(name='Reject second child', source_entity_uuid=caster.uuid,
        event_processor=fail, trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL,
                                                           event_phase=EventPhase.EFFECT)]))
    with pytest.raises(RuntimeError, match='Second child admission failed'):
        caster.prepare_condition_application(incoming)
    assert caster.active_conditions['Concentrating'] is previous
    assert set(previous.linked_conditions) == {(target.uuid, banished.uuid), (caster.uuid, child.uuid)}
    assert banished.applied and child.applied and target.is_spatially_suspended
    assert occupant.position == (3, 3) and not banished.prepared_removal_occupancies()


def test_antimagic_field_replacement_commits_before_suppressed_condition_restoration():
    reset_core_action_state()
    caster = strong_entity('Caster', (1, 1), 'heroes')
    target = strong_entity('Recipient', (2, 1), 'heroes')
    haste = HasteEffect(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
                        tags={ConditionTag.MAGICAL})
    target.add_condition(haste)
    cause = Event(event_type=EventType.CAST_SPELL, source_entity_uuid=caster.uuid)
    field = AntimagicFieldZone(source_entity_uuid=caster.uuid, anchor_uuid=caster.uuid,
                              position=caster.position, faction=caster.faction)
    field.activate(parent_event=cause)
    assert not haste.applied and not target.action_economy.get_restricted_action_grants()
    previous = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                             spell_name='Antimagic Field')
    caster.add_condition(previous)
    previous.add_linked_condition(field.uuid, field.uuid)
    incoming = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                             spell_name='Replacement')
    prepared = caster.prepare_condition_application(incoming)
    assert isinstance(prepared, PreparedConditionApplication)
    with BaseBlock.condition_removal_scope():
        cursor = EventQueue.event_cursor()
        caster.commit_condition_application(prepared)
        assert EventQueue.event_cursor() == cursor
        assert caster.active_conditions['Concentrating'] is incoming
        assert not field.applied and not haste.applied
        assert not target.active_conditions
        caster.publish_condition_application(prepared)
        assert haste.applied and target.active_conditions['Haste'] is haste
        assert len(target.action_economy.get_restricted_action_grants()) == 1


@pytest.mark.parametrize('condition_type', [Invisible, InvisibilityEffect, GreaterInvisibilityEffect, HasteEffect])
def test_replacement_keeps_incoming_direct_state_owned_after_old_removal(condition_type):
    actor = owner('Recipient')
    previous = condition_type(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)
    actor.add_condition(previous)
    incoming = condition_type(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)
    prepared = actor.prepare_condition_application(incoming)
    assert isinstance(prepared, PreparedConditionApplication)
    with BaseBlock.condition_removal_scope():
        actor.commit_condition_application(prepared)
        if condition_type is HasteEffect:
            assert [grant.owner_uuid for grant in actor.action_economy.get_restricted_action_grants()] == [incoming.uuid]
        else:
            assert actor.is_invisible
        actor.publish_condition_application(prepared)
        assert actor.active_conditions[incoming.name] is incoming
        if condition_type is not HasteEffect:
            assert actor.is_invisible


def test_stale_banishment_return_admission_cannot_partially_replace_concentration():
    caster, target, occupant, previous, banished = banishment_scene()
    incoming = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                             spell_name='Replacement')
    prepared = caster.prepare_condition_application(incoming)
    assert isinstance(prepared, PreparedConditionApplication)
    Entity.update_entity_position(occupant, (4, 3))
    with BaseBlock.condition_removal_scope():
        with pytest.raises(RuntimeError, match='no longer matches native state'):
            caster.commit_condition_application(prepared)
    caster.cancel_condition_application(prepared, 'Objective occupancy changed')
    assert caster.active_conditions['Concentrating'] is previous
    assert target.is_spatially_suspended and banished.applied
    assert occupant.position == (4, 3)


def test_mandatory_retirement_restores_external_banished_target_only():
    caster, target, occupant, _previous, _banished = banishment_scene()
    existence = condition(caster, 'Summoned existence')
    caster.add_condition(existence)
    # The ending actor is also banished, but must never reappear during retirement.
    self_banished = BanishedCondition(source_entity_uuid=target.uuid, target_entity_uuid=caster.uuid)
    caster.add_condition(self_banished)
    release = TerminalOwnerRelease(entity_uuid=caster.uuid, existence_condition_uuid=existence.uuid,
                                   cause=SummonDepartureCause.EXPIRED)
    prepared = BaseBlock.prepare_owned_condition_removals((caster,), parent_event=None,
                                                         terminal_release=release)
    assert prepared is not None
    with BaseBlock.condition_removal_scope(terminal_release=release):
        cursor = EventQueue.event_cursor()
        BaseBlock.commit_owned_condition_removals(prepared)
        assert EventQueue.event_cursor() == cursor
        assert target.is_deployed and occupant.position == (3, 4)
        assert caster.is_spatially_suspended and not caster.is_deployed
        BaseBlock.publish_owned_condition_removals(prepared)
        assert caster.is_spatially_suspended and not caster.is_deployed
