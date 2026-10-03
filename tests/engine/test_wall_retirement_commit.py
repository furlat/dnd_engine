"""Real concentrated construction teardown commits before removal observations.

Boundary: existing native prepared concentration replacement after a real wall
cast. A later rejected admission preserves the original sections; committed
replacement's callbacks observe the new authority, never an intermediate world.
"""

import pytest

from dnd.conditions import Concentrating
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_block import BaseBlock, PreparedConditionApplication
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.types.world import LightLevel
from dnd.types.summoning import SummonDepartureCause, TerminalOwnerRelease
from dnd.spells.wall_constructions import WallOfIce, WallOfIceZone, WallOfStone, WallOfStoneZone
from tests.engine.test_remaining_walls import cast, scene


@pytest.mark.parametrize('spell,zone_type', [(WallOfIce, WallOfIceZone), (WallOfStone, WallOfStoneZone)])
def test_prepared_wall_replacement_commits_before_any_removal_callback(spell, zone_type):
    caster = scene(spell.model_fields['spell_level'].default)
    cast(spell, caster)
    grid = get_map()
    wall = next(zone for zone in grid.get_spatial_conditions() if isinstance(zone, zone_type))
    sections = tuple(wall.sections)
    previous = caster.active_conditions['Concentrating']
    incoming = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                             spell_name='Replacement')
    prepared = caster.prepare_condition_application(incoming)
    assert isinstance(prepared, PreparedConditionApplication)
    assert caster.active_conditions['Concentrating'] is previous
    snapshots = []
    def observed(event):
        if event.phase is EventPhase.COMPLETION:
            snapshots.append((event.event_type, caster.active_conditions.get('Concentrating'),
                              tuple(grid.get_object_position(identity) for identity in sections)))
    EventQueue.add_on_event_callback(observed)
    try:
        with BaseBlock.condition_removal_scope():
            cursor = EventQueue.event_cursor()
            caster.commit_condition_application(prepared)
            assert caster.active_conditions['Concentrating'] is incoming
            assert all(BaseBlock.get(identity) is None for identity in sections)
            assert all(grid.get_object_position(identity) is None for identity in sections)
            assert not grid.has_spatial_condition(wall.uuid)
            assert EventQueue.event_cursor() == cursor
            assert not snapshots
            caster.publish_condition_application(prepared)
            assert snapshots
            assert all(authority is incoming and not any(positions)
                       for _, authority, positions in snapshots)
        removed = [row for row in snapshots if row[0] is EventType.SPATIAL_OBJECT_REMOVED]
        assert len(removed) == len(sections)
        count = EventQueue.event_cursor()
        caster.publish_condition_application(prepared)
        assert EventQueue.event_cursor() == count
    finally:
        EventQueue.remove_on_event_callback(observed)


@pytest.mark.parametrize('spell,zone_type', [(WallOfIce, WallOfIceZone), (WallOfStone, WallOfStoneZone)])
def test_canceled_concentration_replacement_preserves_wall_and_section_authority(spell, zone_type):
    caster = scene(spell.model_fields['spell_level'].default)
    cast(spell, caster)
    grid = get_map()
    wall = next(zone for zone in grid.get_spatial_conditions() if isinstance(zone, zone_type))
    sections = tuple((identity, BaseBlock.get(identity), grid.get_object_placement(identity))
                     for identity in wall.sections)
    previous = caster.active_conditions['Concentrating']
    incoming = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                             spell_name='Rejected replacement')
    prepared = caster.prepare_condition_application(incoming)
    assert isinstance(prepared, PreparedConditionApplication)
    caster.cancel_condition_application(prepared, 'Destination unavailable')
    assert caster.active_conditions['Concentrating'] is previous and previous.applied
    assert not incoming.applied
    assert grid.get_spatial_condition(wall.uuid) is wall and wall.applied
    assert all(BaseBlock.get(identity) is item and grid.get_object_placement(identity) == placement
               for identity, item, placement in sections)
    assert not grid.can_transition((7, 4), (7, 5), caster.uuid)


def test_stone_replacement_commits_reopened_lighting_before_publication():
    caster = scene(5)
    grid = get_map()
    target = (7, 7)
    grid.set_tile_base_light(target, LightLevel.DARKNESS)
    tile = grid.get_tile(*target)
    assert tile is not None
    cast(WallOfStone, caster)
    grid.add_light_source((7, 3), bright_radius_feet=30, dim_radius_feet=0)
    assert tile.resolved_light_level is LightLevel.DARKNESS
    incoming = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                             spell_name='Replacement')
    prepared = caster.prepare_condition_application(incoming)
    assert isinstance(prepared, PreparedConditionApplication)
    seen_light = []
    def observed(event):
        if event.phase is EventPhase.COMPLETION:
            seen_light.append(tile.resolved_light_level)
    EventQueue.add_on_event_callback(observed)
    try:
        with BaseBlock.condition_removal_scope():
            cursor = EventQueue.event_cursor()
            caster.commit_condition_application(prepared)
            assert tile.resolved_light_level is LightLevel.BRIGHT_LIGHT
            assert EventQueue.event_cursor() == cursor
            caster.publish_condition_application(prepared)
        assert seen_light and all(level is LightLevel.BRIGHT_LIGHT for level in seen_light)
        assert any(event.event_type is EventType.SPATIAL_LIGHT_CHANGED
                   and event.phase is EventPhase.COMPLETION
                   for _, event in EventQueue.iter_events_since(cursor))
    finally:
        EventQueue.remove_on_event_callback(observed)


@pytest.mark.parametrize('spell,zone_type', [(WallOfIce, WallOfIceZone), (WallOfStone, WallOfStoneZone)])
def test_terminal_actor_cleanup_removes_exact_wall_despite_section_veto(spell, zone_type):
    caster = scene(spell.model_fields['spell_level'].default)
    cast(spell, caster)
    grid = get_map()
    wall = next(zone for zone in grid.get_spatial_conditions() if isinstance(zone, zone_type))
    sections = tuple(wall.sections)
    previous = caster.active_conditions['Concentrating']
    release = TerminalOwnerRelease(entity_uuid=caster.uuid, existence_condition_uuid=previous.uuid,
        cause=SummonDepartureCause.EXPIRED)
    unrelated = build_authored_item('weapon.dagger', caster.uuid)
    rejected = []
    def veto(event, _):
        rejected.append(event.uuid)
        return event.cancel(status_message='Reject ordinary section removal')
    guard = EventHandler(name='Keep ordinary objects', source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_REMOVED, event_phase=EventPhase.DECLARATION)],
        event_processor=veto)
    EventQueue.add_event_handler(guard)
    assert caster.remove_condition_by_uuid(previous.uuid, terminal_release=release)
    assert not rejected
    assert not grid.has_spatial_condition(wall.uuid)
    assert all(BaseBlock.get(identity) is None and grid.get_object_position(identity) is None
               for identity in sections)
    assert BaseBlock.get(unrelated.uuid) is unrelated
    with pytest.raises(ValueError, match='exact native owner'):
        unrelated.prepare_retirement(terminal_release=release)
