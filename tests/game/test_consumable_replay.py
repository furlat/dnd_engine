"""Actual potion consumption survives saved player input without private leaks."""

from uuid import uuid4

import pytest

from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.base_item import ItemChargeConsumptionEvent
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventPhase, EventQueue
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.player_facts import ItemChargeFact
from game.player_projection import decode_player_sequence, encode_player_sequence, project_sequence, reduce_lineage
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, RecordedSequence, capture_history


def consumed_potion_history(stack_count: int) -> tuple[CapturedHistory, str]:
    reset_engine_runtime()
    build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        drinker = Entity.create(uuid4(), "Drinker", config=EntityConfig(position=(3, 3), faction="heroes"))
        watcher = Entity.create(uuid4(), "Watcher", config=EntityConfig(position=(5, 3), faction="heroes"))
        potion = build_authored_item("consumable.potion_haste", drinker.uuid)
        potion.stack_count = stack_count
        drinker.install_initial_items(((potion, None),))
        for actor in (drinker, watcher):
            setup_standard_actions(actor)
            actor.compose_entity()
            game.deploy_entity(actor, actor.position)
        cursor = EventQueue.event_cursor()
        startup = capture_interval(name="before drinking", start_cursor=0, end_cursor=cursor,
            observer_uuid=drinker.uuid, battlefield_id="battlefield.open_floor_bright")
        before, _ = reduce_interval(None, startup)
        available = get_available_actions(drinker)
        action = next(row for row in available.all_actions
                      if row.behavior_id == "action.item.potion_haste.drink"
                      and row.valid_targets)
        event = execute_by_index(drinker, action.template_name, action.valid_targets[0].index, available=available)
        assert event is not None and event.phase is EventPhase.COMPLETION and not event.canceled
        assert (potion.uuid in drinker.inventory.items) == (stack_count > 1)
        assert drinker.action_economy.bonus_actions.normalized_score == 0
        consumption, = (row for _, row in EventQueue.iter_events_since(cursor)
                        if isinstance(row, ItemChargeConsumptionEvent) and row.phase is EventPhase.COMPLETION)
        assert consumption.item_destroyed == (stack_count == 1)
        assert consumption.charges_after == (0 if stack_count == 1 else 1)
        return capture_history(before, (), observers=(
            ObserverCapture("drinker", drinker.uuid, cursor),
            ObserverCapture("watcher", watcher.uuid, cursor),
        )), str(potion.uuid)
    finally:
        game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("stack_count", (1, 2))
def test_consumed_potion_updates_only_recorded_owned_inventory(stack_count: int) -> None:
    history, potion_uuid = consumed_potion_history(stack_count)
    received = {}
    for role, native in history.views.items():
        restored = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        received[role] = decode_player_sequence(encode_player_sequence(project_sequence(restored)))
    before, roots = received["drinker"]
    owned = before.actors[before.observer_uuid].controlled_items
    assert owned is not None and potion_uuid in {str(item.item_uuid) for item in owned}
    after = before
    for root in roots:
        after = reduce_lineage(after, root)
    remaining = after.actors[after.observer_uuid].controlled_items
    assert remaining is not None
    remaining_potion = [item for item in remaining if str(item.item_uuid) == potion_uuid]
    assert len(remaining_potion) == (0 if stack_count == 1 else 1)
    if remaining_potion:
        assert (remaining_potion[0].stack_count, remaining_potion[0].charges) == (stack_count - 1, 1)
    charges = [node.fact for root in roots for node in root.events if isinstance(node.fact, ItemChargeFact)]
    assert len(charges) == 1 and charges[0].item_destroyed == (stack_count == 1)
    assert EventQueue.event_cursor() == 0

    other, other_roots = received["watcher"]
    assert not any(isinstance(node.fact, ItemChargeFact) for root in other_roots for node in root.events)
    for root in other_roots:
        other = reduce_lineage(other, root)
    assert other.actors[before.observer_uuid].controlled_items is None
