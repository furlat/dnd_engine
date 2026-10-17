"""Current-field hazard updates preserve native deltas and parent invalidation."""

import pytest

from dnd.blocks.sensory import capture_senses_snapshot
from dnd.core.base_block import LightLevel
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.player.event_record import decode_event, encode_event
from dnd.residues import BLOOD_RESIDUE, CORROSIVE_RESIDUE, deposit_residue, remove_tile_residue
from dnd.spells.conjuration import FogCloudZone
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state
from tests.engine.test_sensory_initial_replay import sensory_since
from dnd.types.cells import no_cells, value_at
from dnd.core.cells import values_items
from dnd.core.sensory_fold import reduce_senses_snapshot


@pytest.mark.parametrize("profile,hazardous", [(BLOOD_RESIDUE, False), (CORROSIVE_RESIDUE, True)])
def test_native_residue_updates_preserve_contacts_light_and_clean_hazard_entries(profile, hazardous):
    reset_senses_state(width=5, height=2)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    target = create_skeleton(name="Visible target", position=(3, 1), darkvision=False)
    tile = get_map().get_tile(2, 1)
    assert tile is not None
    observer.materialize_navigation(max_distance=5)
    before = capture_senses_snapshot(observer.senses)
    assert value_at(before.hazardous_cells, tile.position) == 0
    assert target.uuid in before.entities

    cursor = EventQueue.event_cursor()
    residue = deposit_residue(tile, profile)
    assert residue is not None
    updates = sensory_since(observer.uuid, cursor)
    assert bool(updates) is hazardous
    replayed = before
    for event in updates:
        assert values_items(event.hazardous_cells_changed) == [((2, 1), 1)]
        assert event.paths_dirty
        assert no_cells(event.visible_cells_added) and no_cells(event.visible_cells_removed)
        assert not event.entity_contacts_changed and not event.entity_contacts_removed
        assert not event.object_contacts_changed and not event.object_contacts_removed
        assert no_cells(event.effective_light_levels_changed.cells)
        replayed = reduce_senses_snapshot(observer.uuid, replayed, decode_event(encode_event(event)))
    assert replayed == capture_senses_snapshot(observer.senses)

    # A repeated inert deposit publishes a tile after-value, with no sensory delta.
    if not hazardous:
        cursor = EventQueue.event_cursor()
        assert deposit_residue(tile, profile) is not None
        assert sensory_since(observer.uuid, cursor) == ()
        assert capture_senses_snapshot(observer.senses) == before

    observer.materialize_navigation(max_distance=5)
    before_removal = capture_senses_snapshot(observer.senses)
    cursor = EventQueue.event_cursor()
    assert remove_tile_residue(tile, residue.residue_id)
    updates = sensory_since(observer.uuid, cursor)
    assert bool(updates) is hazardous
    replayed = before_removal
    for event in updates:
        assert values_items(event.hazardous_cells_changed) == [((2, 1), 0)]
        assert event.paths_dirty
        replayed = reduce_senses_snapshot(observer.uuid, replayed, decode_event(encode_event(event)))
    assert replayed == capture_senses_snapshot(observer.senses)
    assert replayed.visible == before.visible and replayed.entities == before.entities
    assert replayed.effective_light_levels == before.effective_light_levels
    assert replayed.hazardous_cells == before.hazardous_cells


@pytest.mark.parametrize("with_volume", [False, True])
def test_movement_parent_invalidates_navigation_materialized_after_light_child(with_volume):
    reset_senses_state(width=8, height=3, default_light=LightLevel.DARKNESS)
    mover = create_skeleton(name="Moving observer", position=(0, 1), darkvision=False)
    create_skeleton(name="Contact", position=(3, 1), darkvision=False)
    if with_volume:
        fog = FogCloudZone(source_entity_uuid=mover.uuid, position=(4, 0),
            affected_positions={(4, 0), (4, 1)})
        fog.activate(parent_event=None)
    get_map().add_light_source(mover.position, bright_radius_feet=10,
        dim_radius_feet=20, anchor_uuid=mover.uuid)
    mover.update_entity_senses(max_distance=7)
    before = capture_senses_snapshot(mover.senses)
    if with_volume:
        assert fog.uuid in before.spatial_effects
    materialized = []

    def consume_light_boundary(event):
        # A public navigation consumer can resolve the child field before its
        # movement parent completes. That parent still has a path-dirty fact.
        mover.materialize_navigation(max_distance=7)
        materialized.append(capture_senses_snapshot(mover.senses))

    EventQueue.add_on_event_callback(consume_light_boundary,
        event_types={EventType.SPATIAL_LIGHT_CHANGED}, phases={EventPhase.COMPLETION})
    cursor = EventQueue.event_cursor()
    try:
        Entity.update_entity_position(mover, (1, 1))
    finally:
        EventQueue.remove_on_event_callback(consume_light_boundary)
    assert len(materialized) == 1
    assert materialized[0].position == (1, 1) and not materialized[0].paths_dirty
    updates = sensory_since(mover.uuid, cursor)
    parent_updates = [event for event in updates
        if EventQueue.get_event_by_uuid(event.cause_event_uuid).event_type is EventType.SPATIAL_ENTITY_ENTERED]
    assert len(parent_updates) == 1
    parent = parent_updates[0]
    assert parent.paths_dirty
    assert no_cells(parent.visible_cells_added) and no_cells(parent.visible_cells_removed)
    assert not parent.entity_contacts_changed and not parent.object_contacts_changed
    assert no_cells(parent.effective_light_levels_changed.cells) and no_cells(parent.hazardous_cells_changed.cells)
    assert not parent.spatial_effects_changed and not parent.spatial_effects_removed
    replayed = before
    for event in updates:
        replayed = reduce_senses_snapshot(mover.uuid, replayed, decode_event(encode_event(event)))
    assert replayed == capture_senses_snapshot(mover.senses)


def test_stationary_observer_hazards_follow_moving_light_and_hidden_removal():
    reset_senses_state(width=12, height=3, default_light=LightLevel.DARKNESS)
    grid = get_map()
    observer = create_skeleton(name="Stationary observer", position=(5, 1), darkvision=False)
    carrier = create_skeleton(name="Light carrier", position=(2, 1), darkvision=False)
    old_cell, new_cell = (2, 0), (8, 0)
    old_tile, new_tile = grid.get_tile(*old_cell), grid.get_tile(*new_cell)
    assert old_tile is not None and new_tile is not None
    old_residue = deposit_residue(old_tile, CORROSIVE_RESIDUE)
    assert old_residue is not None
    assert deposit_residue(new_tile, CORROSIVE_RESIDUE) is not None
    grid.add_light_source(carrier.position, bright_radius_feet=10,
        dim_radius_feet=0, anchor_uuid=carrier.uuid)
    observer.update_entity_senses(max_distance=11)
    assert value_at(capture_senses_snapshot(observer.senses).hazardous_cells, old_cell) == 1
    assert value_at(capture_senses_snapshot(observer.senses).hazardous_cells, new_cell) is None

    replayed = capture_senses_snapshot(observer.senses)
    for destination in ((8, 1), (2, 1)):
        cursor = EventQueue.event_cursor()
        Entity.update_entity_position(carrier, destination)
        for event in sensory_since(observer.uuid, cursor):
            replayed = reduce_senses_snapshot(observer.uuid, replayed, decode_event(encode_event(event)))
        assert replayed == capture_senses_snapshot(observer.senses)
        if destination == (8, 1):
            assert value_at(capture_senses_snapshot(observer.senses).hazardous_cells, old_cell) is None
            assert value_at(capture_senses_snapshot(observer.senses).hazardous_cells, new_cell) == 1
            cursor = EventQueue.event_cursor()
            assert remove_tile_residue(old_tile, old_residue.residue_id)
            assert sensory_since(observer.uuid, cursor) == ()
        else:
            assert value_at(capture_senses_snapshot(observer.senses).hazardous_cells, old_cell) == 0
            assert value_at(capture_senses_snapshot(observer.senses).hazardous_cells, new_cell) is None
