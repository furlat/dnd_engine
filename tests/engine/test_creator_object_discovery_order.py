"""Explicit creator knowledge preserves native placement order in object actions."""

from uuid import UUID, uuid4

import pytest

from dnd.actions_functional import get_available_actions, setup_standard_actions
from dnd.blocks.base_item import BaseItem
from dnd.core.gridmap import get_map
from dnd.entity import EntityConfig
from dnd.runtime_reset import reset_engine_runtime
from tests.engine.support import create_test_entity


@pytest.fixture
def creator():
    reset_engine_runtime(grid_size=(4, 3))
    entity = create_test_entity(name="Creator", config=EntityConfig(position=(1, 1)))
    setup_standard_actions(entity)
    yield entity
    reset_engine_runtime()


def hidden_item(source, number, *, known=True):
    item = BaseItem(uuid=UUID(int=number), source_entity_uuid=source,
        item_id=f"test.creator_order.item{number}", name=f"Created item {number}",
        is_invisible=True, known_to_creator=known)
    item.place_on_grid((2, 1))
    return item


def check_pickup_order(creator, expected):
    creator.update_entity_senses(max_distance=4)
    identities = [item.uuid for item in expected]
    assert list(creator.senses.objects) == identities
    assert all(not contact.visual for contact in creator.senses.objects.values())
    pickup = next(action for action in get_available_actions(creator).object_actions
        if action.template_name == "Pick Up")
    assert [target.target_uuid for target in pickup.valid_targets] == identities
    assert [target.index for target in pickup.valid_targets] == list(range(len(expected)))


def test_creator_object_action_order_survives_move_and_appends_replacement(creator):
    # UUID/hash order differs from both authored placement and creator grouping.
    first = hidden_item(creator.uuid, 3)
    hidden_item(uuid4(), 8)
    second = hidden_item(creator.uuid, 1)
    hidden_item(creator.uuid, 9, known=False)
    third = hidden_item(creator.uuid, 2)
    check_pickup_order(creator, (first, second, third))

    grid = get_map()
    grid.move_object(first.uuid, (1, 2))
    check_pickup_order(creator, (first, second, third))
    assert grid.remove_object(first.uuid)
    check_pickup_order(creator, (second, third))
    first.place_on_grid((2, 1))
    check_pickup_order(creator, (second, third, first))


def test_source_reindex_preserves_placement_order_inside_existing_creator_group(creator):
    other_source = uuid4()
    first = hidden_item(other_source, 3)
    second = hidden_item(creator.uuid, 1)
    third = hidden_item(other_source, 2)
    check_pickup_order(creator, (second,))

    # A source reindex on the same committed placement does not append it.
    first.source_entity_uuid = creator.uuid
    get_map().refresh_object_known_source(first)
    check_pickup_order(creator, (first, second))
    third.source_entity_uuid = creator.uuid
    get_map().refresh_object_known_source(third)
    check_pickup_order(creator, (first, second, third))
    first.source_entity_uuid = other_source
    get_map().refresh_object_known_source(first)
    check_pickup_order(creator, (second, third))
    first.source_entity_uuid = creator.uuid
    get_map().refresh_object_known_source(first)
    check_pickup_order(creator, (first, second, third))
