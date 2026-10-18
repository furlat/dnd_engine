"""Serial native owner. No HTTP handlers, sockets, renderer or client rules."""
from collections import Counter
from contextlib import redirect_stdout
from dataclasses import dataclass
import gc
from hashlib import sha256
import random
import sys
from time import perf_counter
from uuid import UUID, uuid4

from pydantic import BaseModel

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.actions_functional import free_aim_target
from dnd.controller import HumanController
from dnd.core.events import EventQueue
from dnd.core.content.descriptors import ContentVisibility
from dnd.encounter import EncounterState, TurnState
from dnd.player.application import AudienceRuntime, capture_application_operation, initialize_audiences, seat_content
from dnd.player.commands import ActionSelection, CommandRejected
from dnd.player.content import UIContentManifest
from dnd.player.content_composition import ui_content_manifest
from dnd.player.selection import selection_target_pool
from dnd.player.session import (Session, advance_controller, close_session, create_authored_session, create_session,
    _player_choices_for_transport, encoded_player_choices, end_player_turn, equip_player_item, execute_player_action,
    preview_player_selection, toggle_player_handler, unequip_player_item, prepare_player_spells, study_player_spell_mastery)
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.encounter_catalog import encounter_recipe
from server.framing import MAX_PACKET_BYTES, read_packet, write_packet
from server.protocol import (BoundaryState, ChoicesResponse, ContentResponse, InitializationResponse,
    PlayerCursor, PlayerOperation, PreviewResponse, protocol_identity)
from server.worker_protocol import (Advance, Choices, Close, Command, EndGame, Preview, Publication, Reply,
    Request, REQUEST_CODEC, Start)


@dataclass(slots=True)
class Runtime:
    session: Session
    catalog: UIContentManifest
    audiences: dict[str, AudienceRuntime]
    publications: dict[str, Publication]


def boundary(session: Session, seat: str, revision: str) -> BoundaryState:
    encounter = session.encounter
    actor = encounter.get_current_entity()
    if encounter.state is EncounterState.ENDED:
        return BoundaryState(lifecycle='outside_encounter', input_actor_uuid=None, state_revision=revision)
    if encounter.state is not EncounterState.ACTIVE:
        return BoundaryState(lifecycle='terminal', input_actor_uuid=None, state_revision=None)
    waiting = (encounter.turn_state is TurnState.IN_PROGRESS and actor is not None
        and isinstance(encounter.get_current_controller(), HumanController))
    input_actor = actor.uuid if waiting and actor is not None and session.seats[seat].controls(actor.uuid) else None
    return BoundaryState(lifecycle='waiting_for_human' if input_actor is not None else 'advancing',
        input_actor_uuid=input_actor, state_revision=revision if input_actor is not None else None)


def needs_advance(session: Session) -> bool:
    return session.encounter.state is EncounterState.ACTIVE and not (
        session.encounter.turn_state is TurnState.IN_PROGRESS
        and isinstance(session.encounter.get_current_controller(), HumanController))


def start(request: Start) -> tuple[Runtime, Reply, tuple[BaseModel, ...]]:
    random.seed(request.test_seed)
    if not SERVER_CONTENT_SYSTEM_RUNTIME.is_installed:
        SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    if request.player_builds is not None and (request.recipe is not None or request.assignments is not None):
        raise ValueError("Direct player builds require the ordinary skirmish deployment")
    if request.recipe is not None or request.assignments is not None:
        reset_engine_runtime()
        recipe = request.recipe or encounter_recipe(request.encounter_id or 'encounter.lantern_crypt')
        session = create_authored_session(recipe, seat_assignments=request.assignments)
    else:
        session = create_session(encounter_id=request.encounter_id, player_builds=request.player_builds)
    try:
        if set(session.seats) != set(request.audience_ids):
            raise ValueError('Configured credentials must match native external seats')
        catalog = ui_content_manifest()
        public_content = tuple(descriptor for _, descriptor in catalog.content
            if descriptor.visibility is ContentVisibility.PUBLIC)
        content_revision = sha256(ContentResponse(revision='public', descriptors=public_content).model_dump_json().encode()).hexdigest()
        audiences, initializations = initialize_audiences(session, catalog)
        publications = {}
        records = []
        for seat, initial in initializations.items():
            cursor = PlayerCursor(game_id=request.game_id, game_epoch=request.game_epoch,
                audience_id=request.audience_ids[seat], sequence=0)
            revision = str(uuid4())
            publication = Publication(seat_id=seat, cursor=cursor, state_revision=revision,
                boundary=boundary(session, seat, revision), audience=audiences[seat].projection.audience,
                content_revision=content_revision)
            publications[seat] = publication
            records.append(InitializationResponse(protocol=protocol_identity(), cursor=cursor,
                content_revision=content_revision, content_additions=seat_content(audiences[seat]),
                initialization=initial))
        return Runtime(session, catalog, audiences, publications), Reply(publications=tuple(publications.values()),
            encounter_name=session.encounter.name, needs_advance=needs_advance(session), has_response=True), tuple(records)
    except BaseException:
        close_session(session)
        raise


def authorize(runtime: Runtime, seat: str, actor: UUID, revision: str, *, outside_encounter: bool = False) -> None:
    audience = runtime.session.seats.get(seat)
    if audience is None or not audience.controls(actor):
        raise CommandRejected('not_your_turn')
    publication = runtime.publications[seat]
    if publication.state_revision != revision:
        raise CommandRejected('stale_state')
    if outside_encounter and runtime.session.encounter.state is EncounterState.ENDED:
        native = runtime.session.game.entities.get(actor)
        if native is not None and native.active_encounter_uuid is None:
            return
    if boundary(runtime.session, seat, revision).input_actor_uuid != actor:
        raise CommandRejected('not_your_turn')


def retained_selection(runtime: Runtime, seat: str, actor: UUID, generation: int, selection: ActionSelection):
    cache = runtime.session.discovery
    choices = cache.original
    if (cache.seat_id != seat or cache.generation != generation or cache.revision != cache.discovery_revision
            or cache.cursor != EventQueue.event_cursor() or choices is None or choices.entity_uuid != actor):
        raise CommandRejected('stale_discovery')
    if not 0 <= selection.action_index < len(choices.all_actions):
        raise CommandRejected('invalid_selection')
    row = choices.all_actions[selection.action_index]
    if row.position_region is not None and not selection.target_indices:
        # A free aim: the first position is the aim, validated when previewed or executed.
        if not selection.extra_target_positions:
            raise CommandRejected('invalid_selection')
        return row, (free_aim_target(row, selection.extra_target_positions[0]),), selection.extra_target_positions[1:]
    pool = {target.index: target for target in selection_target_pool(row, selection.target_indices)}
    if any(index < 0 or index not in pool for index in selection.target_indices):
        raise CommandRejected('invalid_selection')
    return row, tuple(pool[index] for index in selection.target_indices), selection.extra_target_positions


def dispatch(runtime: Runtime, request: Request) -> tuple[Reply, tuple[BaseModel, ...], BaseModel | None]:
    session = runtime.session
    if isinstance(request, (Start, EndGame, Close)):
        raise ValueError('Unexpected lifecycle request')
    if isinstance(request, (Choices, Preview, Command)):
        authorize(runtime, request.seat_id, request.request.actor_uuid, request.request.state_revision,
            outside_encounter=not isinstance(request, Command) or request.request.intent.kind != "end_turn")
    if isinstance(request, Choices):
        query = request.request
        publication = runtime.publications[request.seat_id]
        response = ChoicesResponse(**publication.cursor.model_dump(exclude={'sequence'}),
            state_revision=publication.state_revision, correlation_id=query.correlation_id, force_attack=query.force_attack,
            choices=_player_choices_for_transport(session, query.actor_uuid, force_attack=query.force_attack, seat_id=request.seat_id))
        return Reply(has_response=True), (), response
    if isinstance(request, Preview):
        query = request.request
        row, selected, extra_positions = retained_selection(runtime, request.seat_id, query.actor_uuid,
            query.discovery_generation, query.selection)
        response = PreviewResponse(**runtime.publications[request.seat_id].cursor.model_dump(exclude={'sequence'}),
            state_revision=query.state_revision, request=query,
            preview=preview_player_selection(session, query.actor_uuid, row, selected, extra_positions,
                prefer_safe=query.selection.prefer_safe, cast_at_level=query.selection.cast_at_level))
        return Reply(has_response=True), (), response
    if isinstance(request, Advance):
        operation = advance_controller(session)
        if operation.boundary is not None and operation.boundary.status == 'error':
            raise RuntimeError('Native controller failed')
    else:
        command = request.request
        match command.intent:
            case intent if intent.kind == 'execute_selection':
                row, selected, extra_positions = retained_selection(runtime, request.seat_id, command.actor_uuid,
                    intent.discovery_generation, intent.selection)
                if not selected or any(target.target_uuid is None for target in selected[1:]):
                    raise CommandRejected('invalid_selection')
                operation = execute_player_action(session, command.actor_uuid, row, selected[0],
                    extra_target_uuids=tuple(target.target_uuid for target in selected[1:]),
                    extra_target_positions=extra_positions,
                    prefer_safe=intent.selection.prefer_safe, cast_at_level=intent.selection.cast_at_level)
            case intent if intent.kind == 'prepare_spells':
                operation = prepare_player_spells(session, command.actor_uuid, intent.selection)
            case intent if intent.kind == 'study_spell_mastery':
                operation=study_player_spell_mastery(session,command.actor_uuid,intent.selection)
            case intent if intent.kind == 'end_turn':
                operation = end_player_turn(session, command.actor_uuid)
            case intent if intent.kind == 'equip':
                operation = equip_player_item(session, command.actor_uuid, intent.item.item_uuid, intent.item.slot)
            case intent if intent.kind == 'unequip':
                operation = unequip_player_item(session, command.actor_uuid, intent.item.slot)
            case intent if intent.kind == 'toggle_handler':
                if intent.discovery_generation != session.discovery.generation or session.discovery.seat_id != request.seat_id:
                    raise CommandRejected('stale_discovery')
                operation = toggle_player_handler(session, command.actor_uuid, intent.handler.handler_uuid, intent.handler.enabled)
            case _:
                raise AssertionError('Unreachable command variant')
    updates = capture_application_operation(runtime.audiences, operation, runtime.catalog)
    records = []
    publications = []
    for seat, update in updates.items():
        previous = runtime.publications[seat]
        next_boundary = boundary(session, seat, previous.state_revision)
        owns_command = isinstance(request, Command) and request.seat_id == seat
        if not (owns_command or update.lineages or update.combat_log_appends or update.content_additions
                or update.hud is not None or next_boundary != previous.boundary):
            continue
        revision = str(uuid4())
        next_boundary = boundary(session, seat, revision)
        cursor = PlayerCursor(**previous.cursor.model_dump(exclude={'sequence'}), sequence=previous.cursor.sequence + 1)
        publication = previous.model_copy(update={'cursor': cursor, 'state_revision': revision, 'boundary': next_boundary})
        record = PlayerOperation(audience=update.audience, lineages=update.lineages, hud=update.hud,
            combat_log_appends=update.combat_log_appends, content_additions=update.content_additions,
            protocol=protocol_identity(), cursor=cursor,
            state_revision=revision, command_number=request.request.command_number if isinstance(request, Command) and owns_command else None,
            boundary=next_boundary)
        publications.append(publication)
        records.append(record)
    for publication in publications:
        runtime.publications[publication.seat_id] = publication
    return Reply(publications=tuple(publications), needs_advance=needs_advance(session)), tuple(records), None


def response_bytes(session: Session, response: BaseModel) -> bytes:
    """One response's wire bytes. Choices reuses the encoding of its retained choices (plan PD2).

    `choices` is the response's last field, so the envelope without it, reopened,
    followed by that encoding is byte-identical to encoding the whole.
    """
    if isinstance(response, ChoicesResponse):
        envelope = response.model_dump_json(exclude={'choices'}).encode()
        return envelope[:-1] + b',"choices":' + encoded_player_choices(session, response.choices) + b'}'
    return response.model_dump_json().encode()


def collect_between_requests() -> tuple[int, Counter]:
    """The worker's one collection point, after a request's reply is written.

    Automatic collection is off (`run_process`): reference counting frees what the
    engine drops, and requests create almost no reference cycles. Here the objects
    the request left are scanned once, cycles found are counted by type (each one is
    a bug to fix in the code that created it), and the survivors are frozen, so the
    next collection scans only what the next request leaves, whatever the world's size.
    """
    gc.set_debug(gc.DEBUG_SAVEALL)
    try:
        found = gc.collect()
        cycles = Counter(type(member).__name__ for member in gc.garbage)
        gc.garbage.clear()
    finally:
        gc.set_debug(0)
    if found:
        gc.collect()
        print(f'gc: collection found {found} objects in reference cycles: {dict(cycles.most_common(8))}',
            file=sys.stderr)
    gc.freeze()
    return found, cycles


def collect_frozen_cycles() -> tuple[int, Counter]:
    """The deep check, for test and measurement runs (and EndGame's own unfreeze): every frozen
    survivor is scanned once more, so a cycle that formed among older objects (a removed
    condition, a dead creature) is found and reported. It is a full-heap pass, so it never runs
    between gameplay requests; a cycle it finds is a bug to fix where it is created."""
    gc.unfreeze()
    return collect_between_requests()


def main() -> None:
    output = sys.stdout.buffer
    runtime = None
    with redirect_stdout(sys.stderr):
        try:
            while (payload := read_packet(sys.stdin.buffer)) is not None:
                request = REQUEST_CODEC.validate_json(payload)
                before = EventQueue.event_cursor()
                started = perf_counter()
                response = encoded = None
                try:
                    if isinstance(request, Close):
                        break
                    if isinstance(request, EndGame):
                        if runtime is None or any(publication.cursor.game_epoch != request.game_epoch
                                for publication in runtime.publications.values()):
                            raise ValueError('EndGame does not own the active native world')
                        close_session(runtime.session)
                        runtime = None
                        reset_engine_runtime()
                        # The ended game's frozen survivors are scanned once more, so no cycle
                        # of it outlives the game; then only the import graph is frozen again.
                        gc.unfreeze()
                        gc.collect()
                        gc.freeze()
                        reply, records = Reply(ended_epoch=request.game_epoch), ()
                    elif runtime is None:
                        if not isinstance(request, Start):
                            raise ValueError('Native owner has not started')
                        runtime, reply, records = start(request)
                        encoded = ContentResponse(revision=next(iter(runtime.publications.values())).content_revision,
                            descriptors=tuple(descriptor for _, descriptor in runtime.catalog.content
                                if descriptor.visibility is ContentVisibility.PUBLIC)).model_dump_json().encode()
                    else:
                        reply, records, response = dispatch(runtime, request)
                        encoded = None if response is None else response_bytes(runtime.session, response)
                except CommandRejected as error:
                    if EventQueue.event_cursor() != before:
                        raise RuntimeError('A command rejected after mutating native state') from error
                    code = str(error)
                    reason = code if code in ('stale_state', 'stale_discovery', 'not_your_turn') else 'invalid_selection'
                    reply = Reply(rejection=reason, needs_advance=needs_advance(runtime.session) if runtime is not None else False)
                    records = ()
                if encoded is not None and len(encoded) > MAX_PACKET_BYTES and isinstance(request, (Choices, Preview)):
                    reply = Reply(query_error='response_too_large')
                    encoded = None
                reply = reply.model_copy(update={'elapsed_ms': (perf_counter() - started) * 1000})
                write_packet(output, reply.model_dump_json().encode())
                for record in records:
                    write_packet(output, record.model_dump_json().encode())
                if encoded is not None:
                    write_packet(output, encoded)
                # Do not hold the preceding game's decoded command/results at
                # the next EndGame boundary. Loop variables also retain values.
                request = response = encoded = reply = records = None
                record = None
                collect_between_requests()
        finally:
            if runtime is not None:
                close_session(runtime.session)


def run_process() -> None:
    """Enter a fresh worker; imported schemas live until process exit.

    The pre-Start import graph is frozen, then automatic collection is off: each
    request's survivors are collected and frozen after its reply
    (`collect_between_requests`). EndGame unfreezes and collects the ended game, so
    its graph never stays frozen into the reusable import graph.
    """
    if SERVER_CONTENT_SYSTEM_RUNTIME.is_installed or EventQueue.event_cursor() != 0:
        raise RuntimeError('Worker process entry requires a fresh native runtime')
    protocol_identity()
    gc.collect()
    gc.freeze()
    gc.disable()
    main()


if __name__ == '__main__':
    run_process()
