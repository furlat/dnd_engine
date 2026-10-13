"""Discarded item queries release actions; retained choices and history survive."""

import gc
import weakref

import pytest

from dnd.actions_functional import execute_available_action
from dnd.content.items.environment_item_builders import build_standing_torch, build_wall_torch
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.items.torches import build_torch
from dnd.player.event_record import decode_event, encode_event
from tests.player.test_light_source_projection import world


@pytest.mark.parametrize('kind', ('portable', 'standing', 'wall'))
def test_discarded_torch_queries_release_actions_while_held_choices_execute(world, kind):
    _, (owner, _) = world
    if kind == 'portable':
        torch = build_torch(owner.uuid)
        assert owner.loot_item(torch)
    else:
        torch = build_standing_torch() if kind == 'standing' else build_wall_torch()
        torch.place_on_grid((5, 6))
    owner.update_entity_senses(max_distance=8)
    history = []
    for expected_lit in (True, False, True):
        held = next(row for row in owner.get_available_actions().all_actions
            if row.source_item_uuid == torch.uuid)
        template = held.execution_template
        assert template is not None
        binding = template.behavior_binding
        assert binding is not None and binding.runtime_owner_uuid == torch.uuid
        registered = frozenset(BaseObject._registry)
        cursor = EventQueue.event_cursor()
        discarded = []
        for _ in range(20):
            actions = torch.get_use_actions(owner.uuid)
            assert len(actions) == 1
            assert actions[0].name == template.name
            assert actions[0].behavior_binding == binding
            discarded.extend(weakref.ref(action) for action in actions)
        del actions
        gc.collect()  # Lifetime assertion only, outside performance measurement.
        assert all(reference() is None for reference in discarded)
        assert frozenset(BaseObject._registry) == registered
        assert EventQueue.event_cursor() == cursor

        root = execute_available_action(owner, held, held.valid_targets[0])
        assert root is not None and not root.canceled
        assert root.source_item_uuid == torch.uuid
        assert torch.is_lit is expected_lit
        history.extend((event, encode_event(event))
            for event in EventQueue.get_events_by_lineage(root.lineage_uuid))
        for original, recorded in history:
            assert EventQueue.get_event_by_uuid(original.uuid) is original
            assert encode_event(original) == recorded
            assert encode_event(decode_event(recorded)) == recorded
