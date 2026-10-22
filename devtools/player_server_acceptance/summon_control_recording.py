"""Save the real summon play journey and its reference-reduced seat states.

The shared acceptance journey casts Animals, commands the wolf to move and
attack, returns to the caster and drops concentration to retire the wolf. Each
seat retains its actual initialization and encoded operations; no native state
is used to fabricate player facts or reference output.
"""
import argparse
import json
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from dnd.core.content.encounters import RosterControllerKind
from dnd.player.audience import PlayerAudience
from dnd.player.facts import PlayerState
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import close_session
from server import worker
from server.protocol import InitializationResponse, PlayerOperation, protocol_identity
from server.worker_protocol import Command, Start
from tests.player.test_summon_controller_ownership import advance_to_input, check_summon_journey, configuration


def record(output: Path, mode: RosterControllerKind) -> None:
    output.mkdir(parents=True, exist_ok=True)
    config = configuration(output, mode)
    audience_ids = {seat.seat_id: uuid4() for seat in config.assignments}
    by_audience = {identity: seat for seat, identity in audience_ids.items()}
    states, counts, requests = {}, {seat: 0 for seat in audience_ids}, []
    adapter = TypeAdapter(PlayerState)
    commands = {seat: 0 for seat in audience_ids}
    original = worker.dispatch

    def save(records):
        for record in records:
            seat = by_audience[record.cursor.audience_id]
            directory = output / seat
            directory.mkdir(exist_ok=True)
            raw = record.model_dump_json().encode()
            (directory / f'{record.cursor.sequence:016}.json').write_bytes(raw)
            if isinstance(record, InitializationResponse):
                decoded = InitializationResponse.model_validate_json(raw)
                states[seat] = reduce_initialization(decoded.initialization, content_additions=decoded.content_additions)
            else:
                states[seat] = reduce_operation(states[seat], PlayerOperation.model_validate_json(raw))
            counts[seat] += 1

    def capture(runtime, request):
        if isinstance(request, Command):
            commands[request.seat_id] += 1
            request = request.model_copy(update={'request': request.request.model_copy(
                update={'command_number': commands[request.seat_id]})})
        result = original(runtime, request)
        save(result[1])
        requests.append(request.model_dump(mode='json'))
        return result

    runtime, _, initializations = worker.start(Start(game_id='summon-control-handoff', game_epoch=uuid4(),
        audience_ids=audience_ids, encounter_id=None, recipe=config.recipe, assignments=config.assignments, test_seed=2))
    try:
        save(initializations)
        worker.dispatch = capture
        advance_to_input(runtime)
        check_summon_journey(runtime, mode)
        for seat, state in states.items():
            assert state.audience == runtime.publications[seat].audience
            (output / seat / 'reference-final-state.json').write_bytes(adapter.dump_json(state, indent=2))
        (output / 'requests.json').write_text(json.dumps(requests, indent=2) + '\n')
        (output / 'receipt.json').write_text(json.dumps({
            'protocol': protocol_identity().model_dump(), 'controller': mode.value, 'seed': 2,
            'journey': ['cast_conjure_animals', 'end_caster_turn', 'summon_choices', 'summon_move',
                'summon_attack', 'end_summon_turn', 'return_to_caster', 'drop_concentration', 'retire_summon'],
            'seats': {seat: {'records': counts[seat], 'final_cursor': runtime.publications[seat].cursor.model_dump(mode='json'),
                'final_audience': TypeAdapter(PlayerAudience).dump_python(states[seat].audience, mode='json')}
                for seat in states},
            'reference_reducer': 'dnd.player.reduction.reduce_initialization / reduce_operation on serialized records',
        }, indent=2) + '\n')
    finally:
        worker.dispatch = original
        close_session(runtime.session)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--controller', choices=('human', 'codex'), default='human')
    args = parser.parse_args()
    record(args.output, RosterControllerKind(args.controller))
    print(f'Saved {args.output}')


if __name__ == '__main__':
    main()
