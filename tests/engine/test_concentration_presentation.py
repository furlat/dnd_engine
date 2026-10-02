"""Committed actor concentration state exposes slot identity without recipient links."""

from dnd.actions import DropConcentration
from dnd.actions_functional import register_spell, get_available_actions, execute_available_action
from dnd.spells.catalog_content import SPELL_CONTENT_IDENTITY_BY_NAME
from dnd.conditions import Concentrating
from dnd.core.base_conditions import ConditionRemovalEvent, ConditionStateChangedEvent
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.modifiers import NumericalModifier
from tests.manual.test_device_concentration import setup_device
from tests.manual.test_131_inventory_use_actions_legacy_contract import force_save


def committed_states(cursor, owner):
    return [event.condition_state for _,event in EventQueue.iter_events_since(cursor)
        if isinstance(event,ConditionStateChangedEvent) and event.target_entity_uuid==owner
        and event.phase is EventPhase.COMPLETION and not event.canceled]


def two_spells():
    caster,targets,_=setup_device()
    caster.max_concentration_slots.self_static.add_value_modifier(NumericalModifier(
        name='Two native slots',value=1,source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid))
    force_save(targets[1],'wisdom',succeeds=False)
    for name in ('Web','Hold Person'):
        register_spell(caster,SPELL_CONTENT_IDENTITY_BY_NAME[name].spell_type,caster_level=7)
    def cast(behavior,target):
        row,choice=next((row,choice) for row in get_available_actions(caster).all_actions
            if row.behavior_id==behavior for choice in row.valid_targets
            if choice.position==target.position or choice.target_uuid==target.uuid)
        with fixed_dice_faces(*([10]*30)):
            return execute_available_action(caster,row,choice)
    cursor=EventQueue.event_cursor()
    result=cast('spell.web',targets[0])
    assert result is not None and not result.canceled
    first=caster.active_conditions['Concentrating']
    assert isinstance(first,Concentrating)
    slot=first.snapshot_state().concentration_slots[0]
    assert slot.spell_id=='spell.web'
    assert any(state.concentration_slots==(slot,) for state in committed_states(cursor,caster.uuid))
    caster.action_economy.reset_all_costs()
    result=cast('spell.hold_person',targets[1])
    assert result is not None and not result.canceled
    current=caster.active_conditions['Concentrating']
    assert isinstance(current,Concentrating) and current.uuid!=first.uuid
    slots=current.snapshot_state().concentration_slots
    assert len(slots)==2 and slot in slots
    assert any(state.concentration_slots==slots for state in committed_states(cursor,caster.uuid))
    return caster,targets,current,slot


def test_retained_actor_slot_survives_root_replacement_and_specific_drop_publication():
    caster,targets,current,slot=two_spells()
    cursor=EventQueue.event_cursor()
    result=DropConcentration(source_entity_uuid=caster.uuid,target_spell='Web').apply()
    assert result is not None and not result.canceled
    assert 'Restrained' not in targets[0].active_conditions and 'Hold Person' in targets[1].active_conditions
    remaining=current.snapshot_state().concentration_slots
    assert len(remaining)==1 and remaining[0].spell_id=='spell.hold_person'
    states=committed_states(cursor,caster.uuid)
    assert states and all(slot not in state.concentration_slots for state in states)
    assert any(state.concentration_slots==remaining for state in states)


def test_rejected_slot_drop_publishes_no_successful_removal_and_preserves_other_slot():
    caster,targets,current,_slot=two_spells()
    before=current.snapshot_state().concentration_slots
    def veto(event, _source):
        if isinstance(event,ConditionRemovalEvent) and event.condition.name=='Hold Person':
            return event.cancel(status_message='Keep native Hold owner')
        return None
    caster.add_event_handler(EventHandler(name='Native child-removal veto',source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL,event_phase=EventPhase.DECLARATION)],
        event_processor=veto))
    cursor=EventQueue.event_cursor()
    result=DropConcentration(source_entity_uuid=caster.uuid,target_spell='Hold Person').apply()
    assert result is not None and result.canceled
    assert current.snapshot_state().concentration_slots==before
    assert 'Hold Person' in targets[1].active_conditions and 'Restrained' in targets[0].active_conditions
    assert all(state.concentration_slots==before for state in committed_states(cursor,caster.uuid))
