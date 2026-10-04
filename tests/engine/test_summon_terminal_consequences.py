"""Terminal creature removal cannot install new conditions on its ending owner."""

from uuid import uuid4

import pytest

from dnd.conditions import Concentrating
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.items.torches import build_torch
from dnd.spells.transmutation import HasteEffect
from dnd.summoning.actions import DismissSummon
from dnd.spatial.environmental_conditions import WetSurface
from tests.engine.test_summoning_lifecycle import battle, cast_one


def held_condition(target, source, kind):
    haste = HasteEffect(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
                        apply_lethargy=kind == 'haste')
    assert not target.add_condition(haste).canceled
    if kind == 'haste':
        return haste, haste
    # Suppression retains the live owner; terminal removal still tears it down once.
    haste.set_suppression(uuid4(), True)
    assert haste.applied and not haste.contributions_active()
    return haste, haste


def depart(member, caster, method):
    if method == 'dismiss':
        caster.action_economy.reset_all_costs()
        result = DismissSummon(source_entity_uuid=caster.uuid, target_entity_uuid=member.entity.uuid).apply()
        assert result is not None and not result.canceled
    else:
        member.existence.duration.duration = 1
        member.entity.turn_duration_interval = (uuid4(), 1)
        assert member.entity.advance_duration_condition('Summoned')


@pytest.mark.parametrize('method', ['dismiss', 'expire'])
@pytest.mark.parametrize('kind', ['haste', 'suppression'])
def test_terminal_summon_removal_skips_only_ending_actor_condition_consequences(battle, method, kind):
    game, encounter, system, caster, _enemy = battle
    member = cast_one(battle)
    departing = member.entity
    effect, haste = held_condition(departing, caster, kind)
    cursor = EventQueue.event_cursor()
    depart(member, caster, method)
    assert Entity.get(departing.uuid) is None
    assert game.get_entity(departing.uuid) is None
    assert get_map().get_entity_position(departing.uuid) is None
    assert departing.uuid not in system.memberships
    assert departing.uuid not in encounter.combatants
    assert not departing.active_conditions and not effect.applied and not haste.applied
    assert not any(isinstance(event, ConditionApplicationEvent)
                   and event.target_entity_uuid == departing.uuid and event.phase is EventPhase.COMPLETION
                   for _, event in EventQueue.iter_events_since(cursor))


@pytest.mark.parametrize('method', ['dismiss', 'expire'])
@pytest.mark.parametrize('kind', ['haste', 'suppression'])
def test_terminal_summon_removal_keeps_normal_consequence_on_surviving_recipient(battle, method, kind):
    game, _encounter, system, caster, recipient = battle
    member = cast_one(battle)
    effect, haste = held_condition(recipient, member.entity, kind)
    sustain = Concentrating(source_entity_uuid=member.entity.uuid, target_entity_uuid=member.entity.uuid,
                            spell_name='Recipient effect')
    assert not member.entity.add_condition(sustain).canceled
    sustain.add_linked_condition(recipient.uuid, effect.uuid)
    depart(member, caster, method)
    assert game.get_entity(recipient.uuid) is recipient and recipient.is_deployed
    assert member.entity.uuid not in system.memberships
    if kind == 'haste':
        assert not haste.applied
        assert 'Haste Lethargy' in recipient.active_conditions
    else:
        assert not haste.applied and 'Haste' not in recipient.active_conditions
        assert not recipient.action_economy.get_restricted_action_grants()


@pytest.mark.parametrize('method', ['dismiss', 'expire'])
def test_wet_surface_manifestation_retires_in_the_shared_native_graph(battle, method):
    game, _, _, caster, _ = battle
    member = cast_one(battle)
    water = WetSurface(source_entity_uuid=caster.uuid, position=member.entity.position,
                       affected_positions={member.entity.position})
    water.activate(parent_event=Event(source_entity_uuid=caster.uuid, event_type=EventType.CAST_SPELL,
                                      phase=EventPhase.EFFECT))
    assert 'Wet' in member.entity.active_conditions
    cursor = EventQueue.event_cursor()
    depart(member, caster, method)
    assert game.get_entity(member.entity.uuid) is None
    assert not member.entity.active_conditions
    removals = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ConditionRemovalEvent) and event.phase is EventPhase.COMPLETION
        and event.condition.name == 'Wet']
    assert len(removals) == 1
    assert water.applied


def test_lit_acquired_torch_publication_failure_does_not_strand_departing_summon(battle):
    game, encounter, system, caster, _ = battle
    member = cast_one(battle)
    torch = build_torch(member.entity.uuid)
    assert member.entity.loot_item(torch)
    torch.ignite(member.entity.uuid)
    assert torch.is_lit
    position = member.entity.position
    observed = []

    def fail_light_publication(event):
        if event.event_type is EventType.SPATIAL_LIGHT_CHANGED:
            observed.append(event.uuid)
            raise RuntimeError('Injected torch light publication failure')

    EventQueue.add_pre_completion_callback(fail_light_publication)
    with pytest.raises(BaseExceptionGroup):
        depart(member, caster, 'expire')
    assert observed
    assert game.get_entity(member.entity.uuid) is None
    assert Entity.get(member.entity.uuid) is None
    assert member.entity.uuid not in system.memberships
    assert member.entity.uuid not in encounter.combatants
    assert get_map().get_entity_position(member.entity.uuid) is None
    assert not member.entity.has_runtime_agency()
    assert not torch.is_lit
    assert torch.owner_uuid is None and torch.stored_in_uuid is None
    assert get_map().get_object_position(torch.uuid) == position
