"""Real process commands use detached facts and reject stale choices without spending."""

import os
from uuid import uuid4

from game.player_commands import ActionSelection
from game.player_facts import StepFact
from game.player_reduction import reduce_initialization, reduce_lineage
from game.runtime_connection import launch_runtime, submit_request, poll_reply, close_runtime, RuntimeFailure
from game.runtime_protocol import (
    StartRequest, StartedReply, AdvanceRequest, OperationReply, DiscoverRequest, DiscoveryReply,
    PreviewRequest, PreviewReply, ActionRequest, RejectedReply, CloseRequest, ClosedReply,
    RuntimeRequest,
)


def test_worker_movement_preview_commit_and_stale_rejection() -> None:
    connection = launch_runtime()

    def exchange(request: RuntimeRequest):
        submit_request(connection, request)
        assert connection.reply_ready.wait(40), (request.kind, b"".join(connection.diagnostics).decode())
        response = poll_reply(connection)
        assert not isinstance(response, RuntimeFailure), (response, b"".join(connection.diagnostics).decode())
        assert response is not None and response.request_id == request.request_id
        return response

    try:
        assert connection.process.pid != os.getpid()
        first = exchange(StartRequest(request_id=0, test_seed=0))
        assert isinstance(first, StartedReply)
        state = reduce_initialization(first.initialization)
        advanced = exchange(AdvanceRequest(request_id=1, generation=state.generation))
        assert isinstance(advanced, OperationReply) and advanced.boundary_status == "waiting_for_human"
        for lineage in advanced.lineages:
            state = reduce_lineage(state, lineage)
        actor = state.current_actor_uuid
        assert actor is not None
        discovered = exchange(DiscoverRequest(request_id=2, generation=state.generation, actor_uuid=actor))
        assert isinstance(discovered, DiscoveryReply)
        choices = discovered.choices
        index, move = next((i, row) for i, row in enumerate(choices.all_actions)
            if row.behavior_id == "action.move" and row.valid_targets)
        destination = min(move.valid_targets, key=lambda row: row.path_cost or 0)
        selection = ActionSelection(index, (destination.index,))
        prefix = dict(generation=state.generation, actor_uuid=actor, discovery_generation=choices.discovery_generation)
        preview = exchange(PreviewRequest(request_id=3, selection=selection, **prefix))
        assert isinstance(preview, PreviewReply) and preview.preview.can_confirm
        # The same detached choice cannot act in another encounter generation.
        invalid = exchange(ActionRequest(request_id=4, selection=selection,
            **dict(prefix, generation=uuid4())))
        assert isinstance(invalid, RejectedReply)
        result = exchange(ActionRequest(request_id=5, selection=selection, **prefix))
        assert isinstance(result, OperationReply)
        for lineage in result.lineages:
            state = reduce_lineage(state, lineage)
        steps = [node.fact for lineage in result.lineages for node in lineage.events
            if isinstance(node.fact, StepFact) and node.fact.committed]
        assert [steps[0].from_position, *(step.to_position for step in steps)] == destination.path
        assert state.actors[actor].last_visual_position == destination.position
        stale = exchange(ActionRequest(request_id=6, selection=selection, **prefix))
        assert isinstance(stale, RejectedReply)
        refreshed = exchange(DiscoverRequest(request_id=7, generation=state.generation, actor_uuid=actor))
        assert isinstance(refreshed, DiscoveryReply)
        assert refreshed.choices.remaining_movement == choices.remaining_movement - destination.path_cost
        assert isinstance(exchange(CloseRequest(request_id=8, generation=state.generation)), ClosedReply)
        assert connection.received_bytes > 0 and connection.sent_bytes > 0
    finally:
        close_runtime(connection)
    assert connection.process.poll() == 0, (connection.process.returncode, b"".join(connection.diagnostics).decode())


def test_worker_reports_native_failure_and_refuses_further_commands() -> None:
    connection = launch_runtime()
    try:
        submit_request(connection, StartRequest(request_id=0, encounter_id='encounter.missing'))
        assert connection.reply_ready.wait(40)
        failure = poll_reply(connection)
        assert isinstance(failure, RuntimeFailure)
        connection.process.wait(timeout=5)
        assert connection.process.returncode != 0
        assert b'Traceback' in b''.join(connection.diagnostics)
        try:
            submit_request(connection, StartRequest(request_id=1))
        except RuntimeError:
            pass
        else:
            raise AssertionError('A failed native process accepted another command')
    finally:
        close_runtime(connection)
    assert not connection.io_thread.is_alive() and not connection.stderr_thread.is_alive()


def test_quit_during_pending_native_operation_closes_process_and_pipes() -> None:
    connection = launch_runtime()
    try:
        submit_request(connection, StartRequest(request_id=0, test_seed=0))
        assert connection.reply_ready.wait(40)
        started = poll_reply(connection)
        assert isinstance(started, StartedReply), started
        submit_request(connection, AdvanceRequest(request_id=1, generation=started.initialization.generation))
    finally:
        close_runtime(connection)
    assert connection.process.poll() == 0, b''.join(connection.diagnostics).decode()
    assert not connection.io_thread.is_alive() and not connection.stderr_thread.is_alive()
