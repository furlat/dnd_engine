"""Native perception follows committed entity and center-object membership."""

from dataclasses import replace

import pytest

from dnd.blocks.base_item import BaseItem, WorldItem
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.core.gridmap import get_map
from dnd.core.modifiers import ContextualNumericalModifier, NumericalModifier
from dnd.player.event_record import decode_event, encode_event
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldPlacementKind, WorldPlacementSpec
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state
from tests.engine.test_sensory_initial_replay import sensory_since
from dnd.core.values import Channel, Kind, add_modifier
from dnd.core.sensory_fold import reduce_senses_snapshot


@pytest.fixture(autouse=True)
def arena():
    reset_senses_state(width=7, height=4)
    yield
    reset_engine_runtime()


def assert_recorded_perception(observer):
    replayed = None
    for event in sensory_since(observer.uuid):
        replayed = reduce_senses_snapshot(observer.uuid, replayed,
            decode_event(encode_event(event)))
    assert replayed is not None
    assert replace(replayed, paths_dirty=False) == replace(
        capture_senses_snapshot(observer.senses), paths_dirty=False)


def test_multiband_center_contact_follows_rotation_movement_and_removal():
    observer = create_skeleton(name="Observer", position=(0, 1), darkvision=False)
    target = create_skeleton(name="Shared-cell occupant", position=(3, 1), darkvision=False)
    item = WorldItem(source_entity_uuid=observer.uuid, item_id="test.contact.tall",
        world_placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.CENTER,
            occupies_bands=False, vertical_extent_steps=3,
            footprint_offsets=((0, 0), (1, 0))))
    item.place_on_grid((2, 1))
    observer.update_entity_senses(max_distance=6)
    assert observer.senses.objects[item.uuid].position == (2, 1)
    assert target.uuid in observer.senses.entities
    historical = capture_senses_snapshot(observer.senses)
    grid = get_map()
    for height in (0, 1, 2):
        assert grid.get_center_objects_at((3, 1), height) == {item.uuid}
    assert grid.get_center_objects_at((3, 1), 3) == set()
    grid.get_entities_at(target.position).clear()
    grid.get_center_objects_at((3, 1)).clear()
    assert grid.get_entities_at(target.position) == {target.uuid}
    assert grid.get_center_objects_at((3, 1)) == {item.uuid}

    grid.orient_object(item.uuid, CardinalDirection.NORTH)
    assert grid.get_center_objects_at((3, 1)) == set()
    assert observer.senses.objects[item.uuid].position == (2, 1)
    grid.move_object(item.uuid, (4, 1))
    assert observer.senses.objects[item.uuid].position == (4, 1)
    assert historical.objects[item.uuid].position == (2, 1)
    assert_recorded_perception(observer)
    assert grid.remove_object(item.uuid)
    assert item.uuid not in observer.senses.objects
    assert target.uuid in observer.senses.entities
    assert_recorded_perception(observer)


@pytest.mark.parametrize("remove", [False, True])
def test_contact_callback_changes_center_membership_before_object_observation(remove):
    observer = create_skeleton(name="Observer", position=(0, 1), darkvision=False)
    target = create_skeleton(name="Hidden contact", position=(3, 1), darkvision=False)
    item = BaseItem(source_entity_uuid=observer.uuid, item_id="test.contact.callback")
    if remove:
        item.place_on_grid(target.position)
    observer.update_entity_senses(max_distance=6)
    target.stealth_dc = 20
    pending = True

    def change_membership(_source, _target, _context):
        nonlocal pending
        if pending:
            pending = False
            if remove:
                assert get_map().remove_object(item.uuid)
            else:
                item.place_on_grid(target.position)
        return NumericalModifier(source_entity_uuid=observer.uuid, value=0,
            use_register=False)

    add_modifier(observer.skill_set.get_skill("perception").skill_bonus, Channel.SELF_CONTEXTUAL, Kind.VALUE, ContextualNumericalModifier(source_entity_uuid=observer.uuid,
            callable=change_membership))
    observer.update_entity_senses(max_distance=6)
    assert not pending
    assert (item.uuid in observer.senses.objects) is (not remove)
    assert target.uuid not in observer.senses.entities
    assert_recorded_perception(observer)
