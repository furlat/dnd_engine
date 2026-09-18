"""Fixed light actions publish their real item state for recorded playback."""

from uuid import uuid4

import pytest

from dnd.actions_functional import execute_use_action
from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.content.items.environment_item_builders import build_standing_torch, build_wall_torch
from dnd.core.events import EventPhase, EventQueue
from dnd.core.item_types import ItemLocation
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.world_facts import WorldFacts, apply_world_fact


@pytest.mark.parametrize("fixture_kind", ("standing", "wall"))
def test_fixed_torch_actions_record_lit_after_values_and_preserve_parentage(
    fixture_kind: str,
) -> None:
    reset_engine_runtime(grid_size=(4, 4))
    game = Game()
    try:
        actor = Entity.create(uuid4(), "Operator", config=EntityConfig(position=(1, 1)))
        actor.compose_entity()
        game.deploy_entity(actor, actor.position)
        fixture = build_standing_torch() if fixture_kind == "standing" else build_wall_torch()
        fixture.place_on_grid((2, 1))
        actor.update_entity_senses(max_distance=4)
        recorded = WorldFacts()

        for expected_lit in (True, False, True):
            available = next(
                row for row in actor.get_available_actions().all_actions
                if row.source_item_uuid == fixture.uuid
            )
            cursor = EventQueue.event_cursor()
            root = execute_use_action(actor, fixture.uuid, available.template_name)
            assert root is not None and not root.canceled
            facts = [
                event for _, event in EventQueue.iter_events_since(cursor)
                if isinstance(event, ItemLocationStateEvent)
                and event.phase is EventPhase.COMPLETION
                and event.item_state.item_uuid == fixture.uuid
            ]
            assert len(facts) == 1
            fact = facts[0]
            assert fact.location is ItemLocation.FLOOR
            assert fact.item_state.is_lit is expected_lit
            assert fact.world_placement is not None
            assert fact.world_placement.position == (2, 1)
            assert fact.parent_event is not None
            parent = EventQueue.get_event_by_uuid(fact.parent_event)
            assert parent is not None
            while parent.parent_event is not None:
                parent = EventQueue.get_event_by_uuid(parent.parent_event)
                assert parent is not None
            assert parent.lineage_uuid == root.lineage_uuid
            assert apply_world_fact(recorded, fact)
            assert recorded.objects[fixture.uuid].item.is_lit is expected_lit

            cursor = EventQueue.event_cursor()
            if expected_lit:
                fixture.light()
            else:
                fixture.put_out()
            assert EventQueue.event_cursor() == cursor
    finally:
        game.close()
        reset_engine_runtime()
