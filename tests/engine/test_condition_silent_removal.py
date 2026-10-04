"""Native state removal commits before visibility/light/manifestation observers."""

from uuid import uuid4

import pytest

from dnd.conditions import Concentrating, Hidden, Restrained
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_block import BaseBlock, PreparedConditionApplication
from dnd.core.base_conditions import ConditionRemovalEvent
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.spells.conjuration import ProduceFlameEffect, SpiritGuardiansSlowSource, SpiritGuardiansSlowed, WebRestrained
from dnd.spells.divination import SeeInvisibilityEffect, TrueSeeingEffect
from dnd.spells.evocation import ContinualFlameCondition, LightEffect, FireShieldEffect
from dnd.spells.transmutation import DarkvisionEffect
from dnd.types.senses import SenseMode, SensesType
from dnd.types.world import LightLevel
from tests.engine.support import reset_combat_state
from tests.engine.test_combat_actions import reset_core_action_state, strong_entity


@pytest.fixture(autouse=True)
def arena():
    reset_core_action_state()
    yield
    reset_combat_state()


def replacement(caster):
    incoming = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, spell_name='Replacement')
    prepared = caster.prepare_condition_application(incoming)
    assert isinstance(prepared, PreparedConditionApplication)
    return incoming, prepared


def sustain(caster, target, effect):
    old = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, spell_name='Previous')
    caster.add_condition(old)
    old.add_linked_condition(target.uuid, effect.uuid)
    return old


@pytest.mark.parametrize('kind', [Hidden, SeeInvisibilityEffect, TrueSeeingEffect, DarkvisionEffect])
def test_perception_condition_removal_commits_before_observers(kind):
    caster = strong_entity('Caster', (1, 1), 'heroes')
    target = strong_entity('Recipient', (2, 1), 'heroes')
    modes = tuple(target.senses.sense_modes)
    effect = kind(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    target.add_condition(effect)
    sustain(caster, target, effect)
    incoming, prepared = replacement(caster)
    seen = []
    def observe(event):
        if event.event_type is EventType.SPATIAL_PERCEIVABILITY_CHANGED:
            seen.append(caster.active_conditions.get('Concentrating'))
    EventQueue.add_on_event_callback(observe)
    try:
        with BaseBlock.condition_removal_scope():
            cursor = EventQueue.event_cursor()
            caster.commit_condition_application(prepared)
            assert EventQueue.event_cursor() == cursor and not seen
            assert not effect.applied and target.stealth_dc is None
            assert tuple(target.senses.sense_modes) == modes
            caster.publish_condition_application(prepared)
            assert seen and all(owner is incoming for owner in seen)
    finally:
        EventQueue.remove_on_event_callback(observe)


@pytest.mark.parametrize('kind,sense,distance', [
    (SeeInvisibilityEffect, SensesType.SEE_INVISIBLE, 0),
    (TrueSeeingEffect, SensesType.TRUESIGHT, 120),
    (DarkvisionEffect, SensesType.DARKVISION, 60),
])
def test_removing_granted_sense_preserves_same_baseline_sense(kind, sense, distance):
    target = strong_entity('Recipient', (2, 1), 'heroes')
    original = SenseMode(sense_type=sense, range_feet=distance)
    target.senses.sense_modes.append(original)
    effect = kind(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid)
    target.add_condition(effect)
    assert target.remove_condition_by_uuid(effect.uuid)
    assert any(mode is original for mode in target.senses.sense_modes)
    assert sum(mode.sense_type is sense and mode.range_feet == distance for mode in target.senses.sense_modes) == 1


@pytest.mark.parametrize('kind', [LightEffect, ProduceFlameEffect, FireShieldEffect])
def test_light_condition_removal_commits_before_light_observers(kind):
    caster = strong_entity('Caster', (1, 1), 'heroes')
    target = strong_entity('Recipient', (2, 1), 'heroes')
    grid = get_map()
    grid.set_tile_base_light(target.position, LightLevel.DARKNESS)
    tile = grid.get_tile(*target.position)
    assert tile is not None
    effect = kind(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    target.add_condition(effect)
    assert tile.resolved_light_level is LightLevel.BRIGHT_LIGHT
    sustain(caster, target, effect)
    incoming, prepared = replacement(caster)
    seen = []
    def observe(event):
        if event.event_type is EventType.SPATIAL_LIGHT_CHANGED:
            seen.append((caster.active_conditions.get('Concentrating'), tile.resolved_light_level))
    EventQueue.add_on_event_callback(observe)
    try:
        with BaseBlock.condition_removal_scope():
            cursor = EventQueue.event_cursor()
            caster.commit_condition_application(prepared)
            assert EventQueue.event_cursor() == cursor and not seen
            assert tile.resolved_light_level is LightLevel.DARKNESS
            assert not effect.applied
            caster.publish_condition_application(prepared)
            assert seen and all(row == (incoming, LightLevel.DARKNESS) for row in seen)
    finally:
        EventQueue.remove_on_event_callback(observe)


def test_continual_flame_item_owner_retains_light_observation_until_publication():
    caster = strong_entity('Caster', (1, 1), 'heroes')
    grid = get_map()
    grid.set_tile_base_light(caster.position, LightLevel.DARKNESS)
    tile = grid.get_tile(*caster.position)
    assert tile is not None
    item = build_authored_item("weapon.club", caster.uuid)
    item.place_on_grid(caster.position)
    flame = ContinualFlameCondition(source_entity_uuid=caster.uuid, target_entity_uuid=item.uuid)
    item.add_condition(flame, parent_event=Event(event_type=EventType.CAST_SPELL, source_entity_uuid=caster.uuid))
    assert tile.resolved_light_level is LightLevel.BRIGHT_LIGHT
    sustain(caster, item, flame)
    incoming, prepared = replacement(caster)
    with BaseBlock.condition_removal_scope():
        cursor = EventQueue.event_cursor()
        caster.commit_condition_application(prepared)
        assert EventQueue.event_cursor() == cursor
        assert tile.resolved_light_level is LightLevel.DARKNESS
        caster.publish_condition_application(prepared)
    # Item-owned light removal publishes only after the replacement commits.
    lights = [event for _, event in EventQueue.iter_events_since(cursor)
              if event.event_type is EventType.SPATIAL_LIGHT_CHANGED and event.phase is EventPhase.COMPLETION]
    assert len(lights) == 1 and caster.active_conditions['Concentrating'] is incoming


def membership(kind, target):
    kwargs = {'check_dc': 12} if kind is WebRestrained else {}
    effect = kind(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
                  source_spatial_condition_uuid=uuid4(), **kwargs)
    target.add_condition(effect)
    return effect


@pytest.mark.parametrize('kind,manifestation', [(WebRestrained, Restrained), (SpiritGuardiansSlowSource, SpiritGuardiansSlowed)])
def test_shared_manifestation_is_preserved_then_removed_silently_with_last_source(kind, manifestation):
    caster = strong_entity('Caster', (1, 1), 'heroes')
    target = strong_entity('Recipient', (2, 1), 'heroes')
    first, second = membership(kind, target), membership(kind, target)
    public = next(condition for condition in target.active_conditions.values() if isinstance(condition, manifestation))
    sustain(caster, target, first)
    _, prepared = replacement(caster)
    with BaseBlock.condition_removal_scope():
        cursor = EventQueue.event_cursor()
        caster.commit_condition_application(prepared)
        assert EventQueue.event_cursor() == cursor
        assert public.applied and second.applied and not first.applied
        caster.publish_condition_application(prepared)
    removals = BaseBlock.prepare_owned_condition_removals((target,), parent_event=None)
    assert removals is not None
    with BaseBlock.condition_removal_scope():
        cursor = EventQueue.event_cursor()
        BaseBlock.commit_owned_condition_removals(removals)
        assert EventQueue.event_cursor() == cursor
        assert not public.applied and not second.applied
        assert target.action_economy.movement_remaining() == 30
        BaseBlock.publish_owned_condition_removals(removals)
        assert not target.active_conditions


@pytest.mark.parametrize('kind,manifestation', [(WebRestrained, Restrained), (SpiritGuardiansSlowSource, SpiritGuardiansSlowed)])
def test_shared_manifestation_removal_veto_is_admitted_before_source_replacement(kind, manifestation):
    caster = strong_entity('Caster', (1, 1), 'heroes')
    target = strong_entity('Recipient', (2, 1), 'heroes')
    source = membership(kind, target)
    public = next(condition for condition in target.active_conditions.values() if isinstance(condition, manifestation))
    previous = sustain(caster, target, source)
    def veto(event, _source):
        if isinstance(event, ConditionRemovalEvent) and event.condition is public:
            return event.cancel(status_message='Preserve public manifestation')
        return None
    caster.add_event_handler(EventHandler(name='Native public child veto', source_entity_uuid=caster.uuid,
        event_processor=veto, trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL, event_phase=EventPhase.DECLARATION)]))
    incoming = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, spell_name='Rejected')
    denied = caster.prepare_condition_application(incoming)
    assert isinstance(denied, Event) and denied.canceled
    assert source.applied and public.applied
    assert caster.active_conditions['Concentrating'] is previous


@pytest.mark.parametrize('kind', [Hidden, SeeInvisibilityEffect, TrueSeeingEffect, DarkvisionEffect])
def test_rejected_prepared_perception_effect_leaves_no_provisional_sense_or_stealth(kind):
    target = strong_entity('Recipient', (2, 1), 'heroes')
    before = tuple(target.senses.sense_modes)
    incoming = kind(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid)
    prepared = target.prepare_condition_application(incoming)
    assert isinstance(prepared, PreparedConditionApplication)
    assert target.stealth_dc is None and tuple(target.senses.sense_modes) == before
    target.cancel_condition_application(prepared, 'Later placement rejected')
    assert target.stealth_dc is None and tuple(target.senses.sense_modes) == before
    assert not target.active_conditions
