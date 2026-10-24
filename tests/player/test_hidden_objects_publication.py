"""Hidden contents and a secret door reach a seat only once its party has found them."""

from uuid import uuid4

import pytest

from dnd.actions_functional import execute_available_action, execute_use_action, setup_standard_actions
from dnd.content.items.environment_item_builders import build_secret_door
from dnd.core.base_block import BaseBlock
from dnd.core.concealment_types import ConcealedAspect
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.concealment import install_concealment
from dnd.items.environment_interactables import StorageChest
from dnd.player.capture import capture_interval, capture_lineages
from dnd.player.projection import SessionProjection, begin_projection, project_lineage
from dnd.player.reduction import reduce_initialization, reduce_lineage
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.types.world import CardinalDirection


@pytest.fixture
def cache_world():
    reset_engine_runtime()
    built = build_battlefield("battlefield.field_cache_bright")
    game = Game()
    actor = Entity.create(uuid4(), "Collector", config=EntityConfig(position=(4, 7)))
    actor.compose_entity()
    setup_standard_actions(actor)
    game.deploy_entity(actor, (4, 7))
    actor.update_entity_senses(max_distance=12)
    chest = BaseBlock.get(built.object_uuids["field_cache"])
    assert isinstance(chest, StorageChest)
    try:
        yield built, actor, chest
    finally:
        game.close()
        reset_engine_runtime()


def seat(built, actor):
    session = SessionProjection()
    projection, public = begin_projection(session, capture_interval(name="hidden objects", start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=actor.uuid, battlefield_id=built.definition.battlefield_id))
    return session, projection, reduce_initialization(public)


def act(session, projection, state, actor, name, target=None, faces=(20,)):
    info = next(row for row in actor.get_available_actions().all_actions if row.template_name.split("__")[0] == name)
    choice = next(option for option in info.valid_targets if target is None or option.target_uuid == target.uuid)
    actor.action_economy.reset_all_costs()
    with fixed_dice_faces(*faces):
        root = execute_available_action(actor, info, choice)
    assert root is not None and not root.canceled, root
    for native in capture_lineages((root,), observer_uuid=actor.uuid):
        packet = project_lineage(session, projection, native)
        if packet is not None:
            state = reduce_lineage(state, packet)
    return state


def test_hidden_contents_are_never_sent_before_a_search_finds_them(cache_world):
    built, actor, chest = cache_world
    install_concealment(chest, ConcealedAspect.CONTENTS, 13)
    assert execute_use_action(actor, chest.uuid, "Open Chest") is not None
    session, projection, state = seat(built, actor)
    assert state.objects[chest.uuid].contained_items is None  # open, in sight, and still nothing to see
    state = act(session, projection, state, actor, "Search Inside", chest)
    contents = state.objects[chest.uuid].contained_items
    assert contents is not None and {row.item_uuid for row in contents} == set(chest.chest_inventory.items)


def test_a_secret_door_is_sent_to_a_seat_only_once_its_party_finds_it(cache_world):
    built, actor, _ = cache_world
    door = build_secret_door(dc=15)
    door.place_on_grid((4, 7), boundary_direction=CardinalDirection.EAST)
    actor.update_entity_senses(max_distance=12)
    session, projection, state = seat(built, actor)
    assert door.uuid not in state.objects
    state = act(session, projection, state, actor, "Search")
    assert state.objects[door.uuid].item.item_id == "environment.door.secret_stone"
