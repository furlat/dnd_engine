"""Server selections preserve native route choice from preview to execution."""
import json
import random
from uuid import uuid4

import pytest

from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import HazardFilter
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.player.facts import StepFact
from dnd.player.session import close_session
from server.protocol import ChoicesRequest, CommandRequest, PreviewRequest
from server.worker import dispatch, needs_advance, start
from server.worker_protocol import Advance, Choices, Command, Preview, Start


@pytest.mark.parametrize("preference", [None, True, False], ids=["omitted", "safe", "normal"])
def test_previewed_route_is_the_committed_route(preference):
    random_state = random.getstate()
    runtime, _, _ = start(Start(game_id="route-choice", game_epoch=uuid4(),
        audience_ids={"party": uuid4()}, encounter_id=None, recipe=None,
        assignments=None, test_seed=0))
    try:
        while needs_advance(runtime.session):
            dispatch(runtime, Advance())
        actor = runtime.session.encounter.get_current_entity()
        assert actor is not None
        x, y = actor.position
        hazard = get_map().get_tile(x - 2, y)
        assert hazard is not None
        hazard.add_condition(BaseCondition(name="Visible route hazard", source_entity_uuid=uuid4(),
            target_entity_uuid=hazard.uuid, hazard_filter=HazardFilter.ALL))
        Entity.update_all_entities_senses()
        revision = runtime.publications["party"].state_revision
        _, _, discovered = dispatch(runtime, Choices(seat_id="party", request=ChoicesRequest(
            actor_uuid=actor.uuid, state_revision=revision, force_attack=False, correlation_id=uuid4())))
        move = next(row for row in discovered.choices.position_actions if row.behavior_id == "action.move"
            and any(target.position == (x - 3, y) for target in row.valid_targets))
        target = next(row for row in move.valid_targets if row.position == (x - 3, y))
        assert target.path is not None and target.safe_path is not None and target.path != target.safe_path
        selection = {"action_index": move.discovery_index, "target_indices": [target.index]}
        if preference is not None:
            selection["prefer_safe"] = preference
        body = {"actor_uuid": str(actor.uuid), "state_revision": revision,
            "discovery_generation": discovered.choices.discovery_generation,
            "correlation_id": str(uuid4()), "selection": selection}
        before = EventQueue.event_cursor(), random.getstate(), actor.action_economy.movement_remaining()
        _, _, response = dispatch(runtime, Preview(seat_id="party",
            request=PreviewRequest.model_validate_json(json.dumps(body))))
        assert (EventQueue.event_cursor(), random.getstate(), actor.action_economy.movement_remaining()) == before
        route = response.preview.selected_route
        assert response.preview.can_confirm and route is not None
        assert route.policy == ("normal" if preference is False else "safe")
        assert route.path == tuple(target.path if preference is False else target.safe_path)
        assert response.request.selection.prefer_safe is (preference is not False)
        command = {"command_number": 1, "actor_uuid": str(actor.uuid), "state_revision": revision,
            "intent": {"kind": "execute_selection", "discovery_generation": body["discovery_generation"],
                "selection": selection}}
        _, records, _ = dispatch(runtime, Command(seat_id="party",
            request=CommandRequest.model_validate_json(json.dumps(command))))
        steps = {node.lineage_uuid: node.fact for record in records for lineage in record.lineages
            for node in lineage.events if isinstance(node.fact, StepFact) and node.fact.committed
            and node.fact.source_entity_uuid == actor.uuid}
        assert tuple((step.from_position, step.to_position) for step in steps.values()) == tuple(
            zip(route.path, route.path[1:]))
        assert actor.position == target.position
        assert actor.action_economy.movement_remaining() == before[2] - route.cost_feet
    finally:
        close_session(runtime.session)
        random.setstate(random_state)


@pytest.mark.parametrize("value", [0, 1, "false", None])
def test_route_preference_requires_a_json_boolean(value):
    with pytest.raises(ValueError):
        PreviewRequest.model_validate_json(json.dumps({"actor_uuid": str(uuid4()), "state_revision": "r",
            "discovery_generation": 1, "correlation_id": str(uuid4()),
            "selection": {"action_index": 0, "target_indices": [0], "prefer_safe": value}}))
