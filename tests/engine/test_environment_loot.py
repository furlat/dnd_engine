"""Discovered chest looting preserves holdings and causal item facts."""

from uuid import uuid4

import pytest

from dnd.actions_functional import execute_use_action
from dnd.blocks.base_item import BaseItem, ItemLocationStateEvent
from dnd.content.items.environment_item_builders import build_storage_chest
from dnd.core.events import EventPhase, EventQueue
from dnd.core.item_types import ItemLocation
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime


@pytest.mark.parametrize(
    ("max_slots", "already_full", "accepted_count"),
    [(None, False, 2), (1, True, 0), (1, False, 1)],
    ids=("all-accepted", "full-inventory", "partially-accepted"),
)
def test_loot_all_preserves_rejected_items_and_records_accepted_transfers(
    max_slots: int | None, already_full: bool, accepted_count: int,
) -> None:
    reset_engine_runtime(grid_size=(4, 4))
    game = Game()
    try:
        actor = Entity.create(
            uuid4(), "Collector", config=EntityConfig(position=(1, 1)),
        )
        actor.compose_entity()
        game.deploy_entity(actor, (1, 1))
        actor.inventory.max_slots = max_slots
        if already_full:
            assert actor.loot_item(BaseItem(
                source_entity_uuid=actor.uuid, item_id="test.item.pack", name="Pack",
            ))
        original_inventory = set(actor.inventory.items)
        chest = build_storage_chest("Loot Chest", include_loot_all_action=True, is_open=True)
        chest.chest_inventory.source_entity_uuid = chest.uuid
        items = [
            BaseItem(
                source_entity_uuid=chest.uuid,
                item_id=f"test.item.{name.lower()}", name=name, weight=1,
            )
            for name in ("Gem", "Ring")
        ]
        for item in items:
            assert chest.chest_inventory.add_item(item)
        chest.place_on_grid((2, 1))
        actor.update_entity_senses(max_distance=4)
        actions = [
            row for row in actor.get_available_actions().all_actions
            if row.source_item_uuid == chest.uuid
            and row.template_name.startswith("Loot All")
        ]
        assert len(actions) == 1

        cursor = EventQueue.event_cursor()
        completion = execute_use_action(actor, chest.uuid, actions[0].template_name)

        assert completion is not None and not completion.canceled
        accepted = items[:accepted_count]
        retained = items[accepted_count:]
        assert set(actor.inventory.items) == original_inventory | {
            item.uuid for item in accepted
        }
        assert set(chest.chest_inventory.items) == {item.uuid for item in retained}
        for item in accepted:
            assert item.owner_uuid == actor.uuid
            assert item.stored_in_uuid == actor.inventory.uuid
        for item in retained:
            assert item.owner_uuid == chest.uuid
            assert item.stored_in_uuid == chest.chest_inventory.uuid

        facts = [
            event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, ItemLocationStateEvent)
            and event.phase is EventPhase.COMPLETION
        ]
        assert len(facts) == accepted_count
        assert {event.item_state.item_uuid for event in facts} == {
            item.uuid for item in accepted
        }
        for event in facts:
            assert event.location is ItemLocation.INVENTORY
            assert event.owner_uuid == actor.uuid
            assert event.container_uuid == actor.inventory.uuid
            assert event.item_state.stack_count == 1
            assert event.parent_lineage == completion.lineage_uuid
            assert event.parent_event is not None
            assert event.world_placement is None

        remaining_actions = [
            row for row in actor.get_available_actions().all_actions
            if row.source_item_uuid == chest.uuid
            and row.template_name.startswith("Loot All")
        ]
        assert bool(remaining_actions) == bool(retained)
    finally:
        game.close()
        reset_engine_runtime()
