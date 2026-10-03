"""Retirement admission failures drain earlier native preparations without mutation.

Exercise actual wall, condition, item and floor event admission. A later callback
may raise; all earlier accepted removals still cancel, even if cleanup also fails.
"""

from uuid import uuid4

import pytest

from dnd.blocks.base_item import BaseItem
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, ConditionRemovalEvent
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, SpatialChangeEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.wall_constructions import WallOfIce, WallOfIceZone
from dnd.types.summoning import SummonDepartureCause
from tests.engine.test_remaining_walls import cast, scene
from tests.engine.test_summon_retirement_ownership import actor, give, release


@pytest.fixture(autouse=True)
def reset():
    reset_engine_runtime(grid_size=(6, 5))
    yield
    reset_engine_runtime()


def attach_condition(owner: BaseBlock, name: str) -> BaseCondition:
    condition = BaseCondition(name=name, source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid)
    owner.add_condition(condition)
    assert condition.applied
    return condition


def test_second_real_wall_section_exception_cancels_first_accepted_removal():
    caster = scene(6)
    cast(WallOfIce, caster)
    grid = get_map()
    wall = next(zone for zone in grid.get_spatial_conditions() if isinstance(zone, WallOfIceZone))
    sections = tuple(wall.sections)
    assert len(sections) == 2
    second = BaseBlock.get(sections[1])
    assert isinstance(second, BaseItem)
    child_condition = attach_condition(second, 'Section state')
    cursor = EventQueue.event_cursor()
    def fail(event, _):
        if isinstance(event, SpatialChangeEvent) and event.object_uuid == sections[1]:
            raise RuntimeError('Second section admission failed')
        return None
    handler = EventHandler(name='Section admission exception', source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_REMOVED, event_phase=EventPhase.EFFECT)],
        event_processor=fail)
    EventQueue.add_event_handler(handler)
    with pytest.raises(RuntimeError, match='Second section admission failed'):
        wall.deactivate()
    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    assert any(isinstance(event, SpatialChangeEvent) and event.object_uuid == sections[0]
               and event.phase is EventPhase.CANCEL for event in events)
    assert any(isinstance(event, ConditionRemovalEvent) and event.condition.uuid == child_condition.uuid
               and event.phase is EventPhase.CANCEL for event in events)
    assert wall.applied and child_condition.applied and tuple(wall.sections) == sections
    assert all(BaseBlock.get(identity) is not None and grid.get_object_position(identity) is not None
               for identity in sections)
    EventQueue.remove_event_handler(handler)
    assert wall.deactivate()
    assert all(BaseBlock.get(identity) is None for identity in sections)


def test_actor_later_floor_exception_drains_condition_and_all_earlier_floor_cancellations():
    game = Game()
    entity = actor(game)
    condition = attach_condition(entity, 'Actor state')
    items = tuple(give(entity, 'weapon.dagger') for _ in range(3))
    cursor = EventQueue.event_cursor()
    def fail(event, _):
        if isinstance(event, SpatialChangeEvent):
            if event.phase is EventPhase.EFFECT and event.object_uuid == items[2].uuid:
                raise RuntimeError('Third placement admission failed')
            if event.phase is EventPhase.CANCEL and event.object_uuid == items[0].uuid:
                raise RuntimeError('First placement cancellation failed')
        if isinstance(event, ConditionRemovalEvent) and event.phase is EventPhase.CANCEL:
            raise RuntimeError('Condition cancellation failed')
        return None
    handler = EventHandler(name='Retirement callback exceptions', source_entity_uuid=entity.uuid,
        trigger_conditions=[
            Trigger(event_type=EventType.SPATIAL_OBJECT_PLACED, event_phase=EventPhase.EFFECT),
            Trigger(event_type=EventType.SPATIAL_OBJECT_PLACED, event_phase=EventPhase.CANCEL),
            Trigger(event_type=EventType.CONDITION_REMOVAL, event_phase=EventPhase.CANCEL)], event_processor=fail)
    EventQueue.add_event_handler(handler)
    with pytest.raises(BaseExceptionGroup) as failure:
        release(game, entity, SummonDepartureCause.DISMISSED)
    assert all(message in repr(failure.value) for message in (
        'Third placement admission failed', 'Condition cancellation failed', 'First placement cancellation failed'))
    canceled = {event.object_uuid for _, event in EventQueue.iter_events_since(cursor)
                if isinstance(event, SpatialChangeEvent) and event.event_type is EventType.SPATIAL_OBJECT_PLACED
                and event.phase is EventPhase.CANCEL}
    assert canceled == {items[0].uuid, items[1].uuid}
    assert condition.applied and entity.inventory.items == {item.uuid: item for item in items}
    assert all(get_map().get_object_position(item.uuid) is None for item in items)
    EventQueue.remove_event_handler(handler)
    prepared = release(game, entity, SummonDepartureCause.DISMISSED)
    assert prepared is not None
    entity.cancel_retirement(prepared.entity)


def test_item_later_supported_admission_exception_drains_earlier_child_after_cleanup_error():
    parent = BaseItem(name='Support', item_id='test.support', source_entity_uuid=uuid4())
    children = tuple(BaseItem(name=f'Attachment {index}', item_id=f'test.attachment_{index}',
        source_entity_uuid=parent.source_entity_uuid, supported_by_uuid=parent.uuid) for index in range(2))
    root_condition = attach_condition(parent, 'Root state')
    first = attach_condition(children[0], 'First attachment')
    second = attach_condition(children[1], 'Second attachment')
    cursor = EventQueue.event_cursor()
    def fail(event, _):
        if not isinstance(event, ConditionRemovalEvent):
            return None
        if event.phase is EventPhase.EFFECT and event.condition.uuid == second.uuid:
            raise RuntimeError('Second attachment admission failed')
        if event.phase is EventPhase.CANCEL and event.condition.uuid == root_condition.uuid:
            raise RuntimeError('Root cancellation failed')
        return None
    handler = EventHandler(name='Attachment callback exceptions', source_entity_uuid=parent.source_entity_uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL, event_phase=phase)
                            for phase in (EventPhase.EFFECT, EventPhase.CANCEL)], event_processor=fail)
    EventQueue.add_event_handler(handler)
    with pytest.raises(BaseExceptionGroup) as failure:
        parent.prepare_retirement()
    assert 'Second attachment admission failed' in repr(failure.value)
    assert 'Root cancellation failed' in repr(failure.value)
    assert any(isinstance(event, ConditionRemovalEvent) and event.condition.uuid == first.uuid
               and event.phase is EventPhase.CANCEL for _, event in EventQueue.iter_events_since(cursor))
    assert all(condition.applied for condition in (root_condition, first, second))
    assert all(BaseBlock.get(item.uuid) is item for item in (parent, *children))
    EventQueue.remove_event_handler(handler)
    prepared = parent.prepare_retirement()
    assert prepared is not None
    parent.cancel_retirement(prepared)
    cursor = EventQueue.event_cursor()
    parent.cancel_retirement(prepared)
    assert EventQueue.event_cursor() == cursor
    with pytest.raises(ValueError, match='Canceled item retirement'):
        parent.commit_retirement(prepared)


def test_native_object_removal_batch_cancels_all_accepted_effects_when_first_cancel_raises():
    grid = get_map()
    items = tuple(BaseItem(name=f'Object {index}', item_id=f'test.object_{index}',
                          source_entity_uuid=uuid4()) for index in range(2))
    for index, item in enumerate(items):
        item.place_on_grid((index + 1, 1))
    prepared = grid.prepare_object_removals(tuple(item.uuid for item in items), clear_object_location=False)
    assert prepared is not None
    def fail(event, _):
        if isinstance(event, SpatialChangeEvent) and event.object_uuid == items[0].uuid:
            raise RuntimeError('First object cancellation failed')
        return None
    handler = EventHandler(name='Cancellation exception', source_entity_uuid=items[0].source_entity_uuid,
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_REMOVED, event_phase=EventPhase.CANCEL)],
        event_processor=fail)
    EventQueue.add_event_handler(handler)
    cursor = EventQueue.event_cursor()
    with pytest.raises(BaseExceptionGroup, match='Object removal cancellation failed'):
        grid.cancel_object_removals(prepared, 'Admission aborted')
    assert {event.object_uuid for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, SpatialChangeEvent) and event.phase is EventPhase.CANCEL} == {item.uuid for item in items}
    assert all(grid.get_object_position(item.uuid) == (index + 1, 1) for index, item in enumerate(items))
