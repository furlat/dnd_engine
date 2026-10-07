"""Rejected composition stays cold; movement previews match the chosen route."""

import random
from uuid import uuid4

import pytest

from dnd.actions import MovementEvent
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import HazardFilter
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.player.audience import SeatAssignment
from dnd.player.session import (
    advance_controller, close_session, create_authored_session, create_session,
    discover_player_actions, execute_player_action, preview_player_selection,
)
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.encounter_catalog import encounter_recipe


@pytest.mark.parametrize("assignments", [(), (SeatAssignment("invalid", (("missing", "member"),)),)])
def test_rejected_seat_assignment_does_not_materialize_a_native_world(assignments):
    reset_engine_runtime()
    recipe = encounter_recipe("encounter.lantern_crypt")
    before = EventQueue.event_cursor(), random.getstate()
    try:
        with pytest.raises(ValueError):
            create_authored_session(recipe, seat_assignments=assignments)
        assert (EventQueue.event_cursor(), random.getstate()) == before
        assert Entity.get_all_entities() == []
        # A rejected request must leave the ordinary composition path usable.
        session = create_authored_session(recipe)
        close_session(session)
    finally:
        reset_engine_runtime()
        random.setstate(before[1])


@pytest.mark.parametrize("prefer_safe", [True, False])
def test_movement_preview_matches_execution_route_preference(prefer_safe):
    random_state = random.getstate()
    random.seed(0)
    session = create_session()
    try:
        for _ in range(32):
            operation = advance_controller(session)
            if operation.boundary is not None and operation.boundary.status == "waiting_for_human":
                break
        actor = session.encounter.get_current_entity()
        assert actor is not None
        x, y = actor.position
        hazard = get_map().get_tile(x - 2, y)
        assert hazard is not None
        hazard.add_condition(BaseCondition(name="Visible route hazard", source_entity_uuid=uuid4(),
            target_entity_uuid=hazard.uuid, hazard_filter=HazardFilter.ALL))
        Entity.update_all_entities_senses()
        choices = discover_player_actions(session, actor.uuid)
        move = next(row for row in choices.position_actions if row.behavior_id == "action.move"
            and any(target.position == (x - 3, y) for target in row.valid_targets))
        target = next(row for row in move.valid_targets if row.position == (x - 3, y))
        assert target.path is not None and target.safe_path is not None
        assert target.path != target.safe_path
        before = EventQueue.event_cursor(), random.getstate(), actor.action_economy.movement_remaining()
        safe = preview_player_selection(session, actor.uuid, move, (target,))
        selected = preview_player_selection(session, actor.uuid, move, (target,), prefer_safe=prefer_safe)
        assert (EventQueue.event_cursor(), random.getstate(), actor.action_economy.movement_remaining()) == before
        assert safe.selected_route is not None and safe.selected_route.policy == "safe"
        assert selected.selected_route is not None
        assert selected.selected_route.path == tuple(target.safe_path if prefer_safe else target.path)
        operation = execute_player_action(session, actor.uuid, move, target, prefer_safe=prefer_safe)
        movement = next(row for row in operation.roots if isinstance(row, MovementEvent))
        assert not movement.canceled and tuple(movement.path) == selected.selected_route.path
        assert actor.action_economy.movement_remaining() == before[2] - selected.selected_route.cost_feet
    finally:
        close_session(session)
        random.setstate(random_state)
