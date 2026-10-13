"""Worker commands preserve the submitted ordered selection without dropping aims.

Boundary: Choices -> Preview/Command. Extra position/self choices are rejected
before mutation; a single admitted choice still executes without a Preview.
"""

import random
from uuid import uuid4

import pytest

from dnd.core.events import EventQueue
from dnd.player.commands import ActionSelection, CommandRejected
from dnd.player.session import snapshot_player_hud
from server.protocol import CommandRequest, ExecuteSelectionIntent, PreviewRequest
from server.worker import dispatch
from server.worker_protocol import Command, Preview
from tests.player.test_compact_choices import request_choices, rows, world


def options(world, behavior_id):
    runtime, _, publication = world
    choices = request_choices(world).choices
    action = next(row for row in rows(choices) if row.behavior_id == behavior_id and row.can_afford)
    targets = choices.target_sets[action.target_set]
    if behavior_id == "action.move":
        actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        target = next(target for target in targets
            if choices.positions[target.position] == (actor.position[0] + 1, actor.position[1]))
    elif behavior_id == "spell.fireball":
        target = next(target for target in targets if choices.positions[target.position] == (10, 7))
    else:
        target = targets[0]
    return choices, action, targets, target


def state(world):
    runtime, seat, publication = world
    actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    return (EventQueue.event_cursor(), random.getstate(), actor.position,
        snapshot_player_hud(runtime.session, audience=runtime.session.seats[seat]))


@pytest.mark.parametrize("behavior_id", ["action.move", "spell.fireball", "action.dodge"])
def test_extra_position_or_self_selection_rejects_without_native_mutation(world, behavior_id):
    runtime, seat, publication = world
    choices, action, targets, target = options(world, behavior_id)
    additional = (target if behavior_id == "action.dodge"
        else next(candidate for candidate in targets if candidate.index != target.index))
    selection = ActionSelection(action_index=action.discovery_index,
        target_indices=(target.index, additional.index))
    before = state(world)
    _, _, response = dispatch(runtime, Preview(seat_id=seat, request=PreviewRequest(
        actor_uuid=choices.entity_uuid, state_revision=publication.state_revision,
        discovery_generation=choices.discovery_generation, correlation_id=uuid4(), selection=selection)))
    assert not response.preview.can_confirm
    assert state(world) == before
    with pytest.raises(CommandRejected, match="invalid_selection"):
        dispatch(runtime, Command(seat_id=seat, request=CommandRequest(command_number=1,
            actor_uuid=choices.entity_uuid, state_revision=publication.state_revision,
            intent=ExecuteSelectionIntent(discovery_generation=choices.discovery_generation, selection=selection))))
    assert state(world) == before


@pytest.mark.parametrize("behavior_id", ["action.move", "spell.fireball", "action.dodge"])
def test_single_position_or_self_command_executes_without_preview(world, behavior_id):
    runtime, seat, publication = world
    choices, action, _, target = options(world, behavior_id)
    before = EventQueue.event_cursor()
    reply, records, _ = dispatch(runtime, Command(seat_id=seat, request=CommandRequest(command_number=1,
        actor_uuid=choices.entity_uuid, state_revision=publication.state_revision,
        intent=ExecuteSelectionIntent(discovery_generation=choices.discovery_generation,
            selection=ActionSelection(action_index=action.discovery_index, target_indices=(target.index,))))))
    assert reply.rejection is None and records
    assert EventQueue.event_cursor() > before
    if behavior_id == "action.move":
        assert runtime.session.game.entities[choices.entity_uuid].position == choices.positions[target.position]
