"""Sole native session owner for live play; launched as a separate module."""

from contextlib import redirect_stdout
from dataclasses import dataclass
import random
import sys
from time import perf_counter

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.base_actions import AvailableActionInfo, AvailableTarget
from dnd.core.events import EventQueue
from dnd.player.selection import selection_target_pool
from dnd.player.facts import PlayerState
from dnd.player.content import UIContentManifest
from dnd.player.application import AudienceRuntime, initialize_audiences, capture_application_operation
from dnd.player.commands import CommandRejected
from dnd.player.content_composition import ui_content_manifest
from game.runtime_protocol import (
    REQUEST_CODEC, REPLY_CODEC, RuntimeRequest, RuntimeReply, StartRequest, StartedReply,
    AdvanceRequest, DiscoverRequest, DiscoveryReply, ChoiceRequest, PreviewRequest, PreviewReply,
    ActionRequest, EndTurnRequest, EquipRequest, UnequipRequest, HandlerRequest,
    CloseRequest, ClosedReply, OperationReply, RejectedReply, read_packet, write_packet,
)
from dnd.player.session import (
    Session, Operation, create_session, close_session,
    advance_controller, discover_player_actions, preview_player_selection, execute_player_action,
    end_player_turn, equip_player_item, unequip_player_item, toggle_player_handler,
)


@dataclass(slots=True)
class NativeRuntime:
    session: Session
    audiences: dict[str, AudienceRuntime]
    catalog: UIContentManifest

    @property
    def latest(self) -> PlayerState:
        return next(iter(self.audiences.values())).latest


def start_runtime(request: StartRequest) -> tuple[NativeRuntime, StartedReply]:
    if request.test_seed is not None:
        random.seed(request.test_seed)
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    session = create_session(encounter_id=request.encounter_id,
        player_positions=request.player_positions, enemy_positions=request.enemy_positions,
        player_builds=request.player_builds)
    try:
        catalog = ui_content_manifest()
        audiences, initializations = initialize_audiences(session, catalog)
        return NativeRuntime(session, audiences, catalog), StartedReply(
            request_id=request.request_id, initialization=next(iter(initializations.values())),
            encounter_name=session.encounter.name, ui_content=UIContentManifest(
                content=tuple((row.ref, row) for row in next(iter(audiences.values())).latest.content),
                feature_ids=catalog.feature_ids, item_ids=catalog.item_ids))
    except BaseException:
        close_session(session)
        raise


def capture_operation(runtime: NativeRuntime, request_id: int, operation: Operation) -> OperationReply:
    """Capture the whole committed operation before allowing another mutation."""
    start_cursor = runtime.latest.reducer_cursor
    update = next(iter(capture_application_operation(runtime.audiences, operation, runtime.catalog).values()))
    return OperationReply(request_id=request_id, generation=runtime.latest.generation,
        start_cursor=start_cursor, end_cursor=runtime.latest.reducer_cursor,
        lineages=update.lineages, hud=update.hud, combat_log_appends=update.combat_log_appends,
        content_additions=update.content_additions,
        boundary_status=operation.boundary.status if operation.boundary is not None else None)


def retained_choice(runtime: NativeRuntime, request: PreviewRequest | ActionRequest
                    ) -> tuple[AvailableActionInfo, tuple[AvailableTarget, ...]]:
    choices = runtime.session.discovery.detached
    if choices is None or not 0 <= request.selection.action_index < len(choices.all_actions):
        raise CommandRejected("This action is no longer available")
    row = choices.all_actions[request.selection.action_index]
    pool = selection_target_pool(row, request.selection.target_indices)
    targets = {target.index: target for target in pool}
    if any(index not in targets for index in request.selection.target_indices):
        raise CommandRejected("This target is not admitted")
    return row, tuple(targets[index] for index in request.selection.target_indices)


def dispatch(runtime: NativeRuntime, request: RuntimeRequest) -> RuntimeReply:
    if isinstance(request, StartRequest):
        raise CommandRejected("This encounter is already running")
    if request.generation != runtime.latest.generation:
        raise CommandRejected("This command belongs to an earlier encounter")
    session = runtime.session
    if isinstance(request, ChoiceRequest):
        cache = session.discovery
        if (cache.detached is None or cache.detached.entity_uuid != request.actor_uuid
                or cache.generation != request.discovery_generation
                or cache.cursor != EventQueue.event_cursor()):
            raise CommandRejected("This selection is stale; choose again")
    match request:
        case CloseRequest():
            return ClosedReply(request_id=request.request_id)
        case DiscoverRequest():
            return DiscoveryReply(request_id=request.request_id, generation=runtime.latest.generation,
                choices=discover_player_actions(session, request.actor_uuid, force_attack=request.force_attack),
                force_attack=request.force_attack)
        case PreviewRequest():
            row, selected = retained_choice(runtime, request)
            return PreviewReply(request_id=request.request_id, generation=runtime.latest.generation,
                preview=preview_player_selection(session, request.actor_uuid, row, selected,
                    request.selection.extra_target_positions))
        case AdvanceRequest():
            operation = advance_controller(session)
        case ActionRequest():
            row, selected = retained_choice(runtime, request)
            if not selected:
                raise CommandRejected("Choose a target")
            operation = execute_player_action(session, request.actor_uuid, row, selected[0],
                extra_target_uuids=tuple(target.target_uuid for target in selected[1:] if target.target_uuid is not None),
                extra_target_positions=request.selection.extra_target_positions)
        case EndTurnRequest():
            operation = end_player_turn(session, request.actor_uuid)
        case EquipRequest():
            operation = equip_player_item(session, request.actor_uuid, request.command.item_uuid, request.command.slot)
        case UnequipRequest():
            operation = unequip_player_item(session, request.actor_uuid, request.command.slot)
        case HandlerRequest():
            operation = toggle_player_handler(session, request.actor_uuid, request.command.handler_uuid,
                request.command.enabled)
    return capture_operation(runtime, request.request_id, operation)


def main() -> None:
    protocol_output = sys.stdout.buffer
    runtime: NativeRuntime | None = None
    last_request = -1
    # Native diagnostics cannot corrupt the framed protocol output.
    with redirect_stdout(sys.stderr):
        try:
            while (payload := read_packet(sys.stdin.buffer)) is not None:
                request = REQUEST_CODEC.validate_json(payload)
                started = perf_counter()
                cursor = EventQueue.event_cursor()
                try:
                    if request.request_id <= last_request:
                        raise ValueError("Request identities must increase")
                    last_request = request.request_id
                    if runtime is None:
                        if not isinstance(request, StartRequest):
                            raise ValueError("The encounter has not started")
                        runtime, reply = start_runtime(request)
                    else:
                        reply = dispatch(runtime, request)
                except CommandRejected as error:
                    # A rejection is safe only before mutation. Never hide a
                    # partial native transaction or automatically retry it.
                    if EventQueue.event_cursor() != cursor:
                        raise
                    reply = RejectedReply(request_id=request.request_id, message=str(error))
                if isinstance(reply, ClosedReply) and runtime is not None:
                    close_session(runtime.session)
                    runtime = None
                reply = reply.model_copy(update={"elapsed_ms": (perf_counter() - started) * 1000})
                write_packet(protocol_output, REPLY_CODEC.dump_json(reply))
                if isinstance(reply, ClosedReply):
                    break
        finally:
            if runtime is not None:
                close_session(runtime.session)


if __name__ == "__main__":
    main()
