"""Native discovered loot crosses the cold subjective boundary exactly once."""

from uuid import uuid4

import pytest

from dnd.actions_functional import execute_available_action, execute_use_action
from dnd.blocks.base_item import BaseItem
from dnd.conditions import Blinded
from dnd.content.items.environment_item_builders import build_storage_chest
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import Duration
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.condition_types import DurationType
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, SpatialChangeEvent, Trigger
from dnd.core.item_types import ItemIntegrity
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.environment_interactables import StorageChest
from dnd.player.capture import capture_interval, capture_lineages
from dnd.player.projection import SessionProjection, begin_projection, project_lineage
from dnd.player.recorded import RecordedSequence, project_sequence
from dnd.player.reduction import (
    decode_player_sequence, encode_player_sequence, reduce_initialization, reduce_lineage,
)
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.world_authoring import place_world_item


@pytest.fixture
def cache_world():
    reset_engine_runtime()
    built = build_battlefield("battlefield.field_cache_bright")
    game = Game()
    actor = Entity.create(uuid4(), "Collector", config=EntityConfig(position=(4, 7)))
    actor.compose_entity()
    game.deploy_entity(actor, (4, 7))
    actor.update_entity_senses(max_distance=12)
    chest = BaseBlock.get(built.object_uuids["field_cache"])
    assert isinstance(chest, StorageChest)
    try:
        yield game, built, actor, chest
    finally:
        game.close()
        reset_engine_runtime()


def initialization(built, actor):
    return capture_interval(name="native storage loot", start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=actor.uuid,
        battlefield_id=built.definition.battlefield_id)


def rows(actor, chest):
    return [row for row in actor.get_available_actions().all_actions
        if row.source_item_uuid == chest.uuid and row.loot_item_uuid is not None]


def use(actor, chest, name):
    result = execute_use_action(actor, chest.uuid, name)
    assert result is not None and not result.canceled, result
    return result


def test_one_all_close_reopen_survive_cold_serialization(cache_world):
    game, built, actor, chest = cache_world
    original = {item.uuid: item.item_id for item in chest.chest_inventory.items.values()}
    assert len(original) == 5 and len(set(original.values())) == 5
    initial = initialization(built, actor)
    session = SessionProjection()
    projection, public = begin_projection(session, initial)
    state = reduce_initialization(public)
    assert state.objects[chest.uuid].contained_items is None
    assert rows(actor, chest) == []
    recorded = []
    expected_contents = [None]
    expected_holdings = [set()]

    def commit(root, contents, holdings):
        nonlocal state
        native = capture_lineages((root,), observer_uuid=actor.uuid,
            known_actor_uuids=frozenset(state.actors))
        assert native and not any(row.dispositions for row in native)
        recorded.extend(native)
        for lineage in native:
            packet = project_lineage(session, projection, lineage)
            assert packet is not None
            state = reduce_lineage(state, packet)
            observed = state.objects[chest.uuid].contained_items
            assert (None if observed is None else {row.item_uuid for row in observed}) == contents
            assert set(state.actors[actor.uuid].controlled_items) == holdings
            expected_contents.append(contents)
            expected_holdings.append(holdings)

    commit(use(actor, chest, "Open Chest"), set(original), set())
    available = rows(actor, chest)
    assert {row.loot_item_uuid for row in available} == set(original)
    assert len({row.template_name for row in available}) == len(original)
    for row in available:
        assert row.behavior_id == "action.environment.storage_chest.loot"
        assert row.is_item_use and len(row.valid_targets) == 1
        assert row.valid_targets[0].index == 0
    chosen = available[0]
    root = execute_available_action(actor, chosen, chosen.valid_targets[0])
    assert root is not None and not root.canceled
    commit(root, set(original) - {chosen.loot_item_uuid}, {chosen.loot_item_uuid})
    assert chosen.loot_item_uuid not in {row.loot_item_uuid for row in rows(actor, chest)}
    commit(use(actor, chest, "Loot All"), set(), set(original))
    assert rows(actor, chest) == []
    commit(use(actor, chest, "Close Chest"), None, set(original))
    commit(use(actor, chest, "Open Chest"), set(), set(original))
    actor_uuid, chest_uuid = actor.uuid, chest.uuid
    saved = RecordedSequence(initialization=initial, lineages=tuple(recorded)).model_dump_json()
    # No live entity, object or native map remains when the same public packets
    # are produced and reduced from their serialized original facts.
    game.close()
    reset_engine_runtime()
    cold = project_sequence(RecordedSequence.model_validate_json(saved, context=PASSIVE_EVENT_REPLAY))
    state, lineages = decode_player_sequence(encode_player_sequence(cold))
    states = [state]
    for lineage in lineages:
        state = reduce_lineage(state, lineage)
        states.append(state)
    assert len(states) == len(expected_contents)
    for state, contents, holdings in zip(states, expected_contents, expected_holdings, strict=True):
        observed = state.objects[chest_uuid].contained_items
        assert (None if observed is None else {row.item_uuid for row in observed}) == contents
        assert set(state.actors[actor_uuid].controlled_items) == holdings


@pytest.mark.parametrize("interference", ("closed", "transferred", "other_holder", "full"))
def test_stale_single_loot_cannot_transfer_after_authority_changes(cache_world, interference):
    game, _, actor, chest = cache_world
    use(actor, chest, "Open Chest")
    chosen = rows(actor, chest)[0]
    if interference == "closed":
        use(actor, chest, "Close Chest")
    elif interference == "transferred":
        result = execute_available_action(actor, chosen, chosen.valid_targets[0])
        assert result is not None and not result.canceled
    elif interference == "other_holder":
        other = Entity.create(uuid4(), "Other collector", config=EntityConfig(position=(4, 8)))
        other.compose_entity()
        game.deploy_entity(other, (4, 8))
        assert other.loot_item(chest.chest_inventory.items[chosen.loot_item_uuid])
    else:
        actor.inventory.max_slots = 0
    before = (set(chest.chest_inventory.items), set(actor.inventory.items))
    rejected = execute_available_action(actor, chosen, chosen.valid_targets[0])
    assert rejected is None or rejected.canceled
    assert (set(chest.chest_inventory.items), set(actor.inventory.items)) == before


def test_full_stack_merge_removes_source_child_in_cold_view(cache_world):
    _, built, actor, _ = cache_world
    chest = build_storage_chest("Stack fixture", include_loot_all_action=True)
    # Native inventory's supported stack fixture: matching identity/category,
    # with two distinct item UUIDs; only the destination stack survives.
    incoming = BaseItem(source_entity_uuid=chest.uuid, item_id="test.stack",
        name="Stack", stack_id="test.stack", max_stack=10, stack_count=3)
    held = BaseItem(source_entity_uuid=actor.uuid, item_id="test.stack",
        name="Stack", stack_id="test.stack", max_stack=10, stack_count=2)
    assert chest.chest_inventory.add_item(incoming)
    assert actor.loot_item(held)
    # Public world authoring publishes this exact native fixture's children;
    # the catalog-transfer test above uses unchanged authored contents.
    place_world_item(chest, (4, 8), author_uuid=actor.uuid)
    actor.update_entity_senses(max_distance=12)
    use(actor, chest, "Open Chest")
    session = SessionProjection()
    projection, public = begin_projection(session, initialization(built, actor))
    state = reduce_initialization(public)
    assert {row.item_uuid for row in state.objects[chest.uuid].contained_items} == {incoming.uuid}
    chosen = next(row for row in rows(actor, chest) if row.loot_item_uuid == incoming.uuid)
    root = execute_available_action(actor, chosen, chosen.valid_targets[0])
    assert root is not None and not root.canceled
    for native in capture_lineages((root,), observer_uuid=actor.uuid,
            known_actor_uuids=frozenset(state.actors)):
        packet = project_lineage(session, projection, native)
        assert packet is not None
        state = reduce_lineage(state, packet)
    assert incoming.uuid not in chest.chest_inventory.items
    assert incoming.uuid not in actor.inventory.items
    assert held.stack_count == 5
    assert state.objects[chest.uuid].contained_items == ()
    assert held.uuid in state.actors[actor.uuid].controlled_items and state.items[held.uuid].state.stack_count == 5


def test_losing_sight_clears_contents_and_does_not_discover_private_items(cache_world):
    _, built, actor, chest = cache_world
    use(actor, chest, "Open Chest")
    session = SessionProjection()
    projection, public = begin_projection(session, initialization(built, actor))
    state = reduce_initialization(public)
    assert len(state.objects[chest.uuid].contained_items) == 5
    blinded = actor.add_condition(Blinded(source_entity_uuid=actor.uuid,
        target_entity_uuid=actor.uuid,
        duration=Duration(duration=3, duration_type=DurationType.ROUNDS)), check_save_throw=False)
    assert blinded is not None
    assert rows(actor, chest) == []
    for native in capture_lineages((blinded,), observer_uuid=actor.uuid,
            known_actor_uuids=frozenset(state.actors)):
        packet = project_lineage(session, projection, native)
        assert packet is not None
        state = reduce_lineage(state, packet)
    assert chest.uuid not in state.objects or state.objects[chest.uuid].contained_items is None


def test_partial_loot_all_keeps_exact_remaining_contents_visible(cache_world):
    _, built, actor, chest = cache_world
    use(actor, chest, "Open Chest")
    actor.inventory.max_slots = 1
    session = SessionProjection()
    projection, public = begin_projection(session, initialization(built, actor))
    state = reduce_initialization(public)
    original = {row.item_uuid for row in state.objects[chest.uuid].contained_items}
    root = use(actor, chest, "Loot All")
    for native in capture_lineages((root,), observer_uuid=actor.uuid,
            known_actor_uuids=frozenset(state.actors)):
        packet = project_lineage(session, projection, native)
        assert packet is not None
        state = reduce_lineage(state, packet)
    remaining = {row.item_uuid for row in state.objects[chest.uuid].contained_items}
    holdings = set(state.actors[actor.uuid].controlled_items)
    assert len(remaining) == 4 and len(holdings) == 1
    assert not remaining & holdings and remaining | holdings == original


def test_broken_retained_storage_is_disclosed_but_floor_item_is_not_storage(cache_world):
    _, built, actor, chest = cache_world
    floor = BaseItem(source_entity_uuid=actor.uuid, item_id="test.floor", name="Floor item")
    place_world_item(floor, (4, 8), author_uuid=actor.uuid)
    children = set(chest.chest_inventory.items)
    # Native placement admission rejects spilling; the same container retains
    # its items, so both native Loot and public contents must remain available.
    veto = EventHandler(name="Retain rejected spill", source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_PLACED,
            event_phase=EventPhase.EFFECT)],
        event_processor=lambda event, _: event.cancel(status_message="Fixture rejects spill")
            if isinstance(event, SpatialChangeEvent) and event.object_uuid in children else event)
    EventQueue.add_event_handler(veto)
    try:
        chest.destroy()
    finally:
        EventQueue.remove_event_handler(veto)
    actor.update_entity_senses(max_distance=12)
    assert chest.integrity is ItemIntegrity.DESTROYED and not chest.is_open
    assert set(chest.chest_inventory.items) == children
    _, public = begin_projection(SessionProjection(), initialization(built, actor))
    state = reduce_initialization(public)
    assert state.objects[floor.uuid].contained_items is None
    assert {row.item_uuid for row in state.objects[chest.uuid].contained_items} == children
    choices = rows(actor, chest)
    assert {row.loot_item_uuid for row in choices} == children
    chosen = choices[0]
    result = execute_available_action(actor, chosen, chosen.valid_targets[0])
    assert result is not None and not result.canceled
    assert chosen.loot_item_uuid in actor.inventory.items
