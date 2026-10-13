"""Recorded movement costs remain data after the runtime action is released."""

import gc
import weakref

from dnd.actions import Move
from dnd.core.base_actions import Cost
from dnd.core.events import EventQueue
from dnd.player.event_record import decode_event, encode_event
from dnd.runtime_reset import reset_engine_runtime
from tests.engine.test_navigation_movement_demand import make_actor


def test_movement_history_detaches_costs_from_the_executable_action():
    actor = make_actor()
    try:
        action = Move(source_entity_uuid=actor.uuid, end_position=(6, 0), use_register=False)
        action.costs.append(Cost(name='Extra action cost', cost_type='bonus_actions', cost=1))
        action_ref = weakref.ref(action)
        result = action.apply()
        assert result is not None and not result.canceled
        assert actor.position == (6, 0)
        assert actor.action_economy.movement_remaining() == 0
        assert actor.action_economy.bonus_actions.normalized_score == 0
        history = EventQueue.get_events_by_lineage(result.lineage_uuid)
        recorded = tuple(encode_event(event) for event in history)
        assert len(recorded) >= 4
        assert [(cost.cost_type, cost.cost) for cost in result.costs] == [
            ('bonus_actions', 1), ('movement', 30)]

        # Editing a reusable runtime action cannot rewrite already stored facts.
        for cost in action.costs:
            cost.name = 'Later runtime edit'
            cost.cost_type = 'actions'
            cost.cost = 999
            cost.resource_name = 'later resource'
            cost.resource_cost = 999
        del cost
        assert tuple(encode_event(event) for event in history) == recorded
        del action
        gc.collect()  # Lifetime assertion outside any performance measurement.
        assert action_ref() is None
        assert tuple(encode_event(decode_event(value)) for value in recorded) == recorded
    finally:
        reset_engine_runtime()
