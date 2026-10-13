"""Record an actual Expedition-seat walk through the authored Lantern Gallery.

Only public SDK discovery, preview and commands drive the encounter. The journal
contains original response bytes; the current engine player reducer is read-only
decision input. The distant curator is deliberately not an attack target.
"""
import argparse
import asyncio
import json
from pathlib import Path
import socket
import sys
from time import monotonic, perf_counter_ns
from unittest.mock import patch
from uuid import UUID, uuid4

from dnd_player import transport
from dnd_player import (Follower, attach, choices, connect, follow,
    preview, receipt, status, submit_command, wait_for_cursor)
from dnd.player.facts import PlayerState
from dnd.player.reduction import reduce_initialization, reduce_operation
from server.protocol import InitializationResponse, PlayerOperation
from devtools.player_server_acceptance.fixtures import configuration


ROUTE = (
    ('Crypt passage', 'open'), ('move', (10, 6)),
    ('Burial hall door', 'open'), ('move', (13, 6)),
    ('Gallery passage', 'open'), ('move', (22, 6)),
    ('Lantern gallery door', 'open'),
    ('gallery_entry', (26, 6)), ('gallery_nave', (46, 6)),
    ('gallery_centre', (46, 20)), ('gallery_far', (68, 20)),
)
SELECTION_POLICY = 'semantic-ties-v1'


def target_key(target):
    return (target['target_name'] or '', tuple(target['position'] or ()), target['target_kind'])


def action_key(row):
    return (row['behavior_id'], row['provided_by_id'], row['origin_root_id'] or '',
        row['template_name'].split('__item_')[0], row['display_name'], row['weapon_slot'] or '')


def target_description(target):
    return {'kind': target['target_kind'], 'name': target['target_name'],
        'position': target['position'], 'path': target['path'], 'safe_path': target['safe_path']}


def observer_order(state):
    return [{'name': state.actors[identity].name, 'uuid': str(identity)}
        for identity in sorted(state.viewing_audience.observers, key=str)]


def rows(discovered):
    return [row for key in ('entity_actions', 'position_actions', 'self_actions', 'object_actions')
        for row in discovered[key] if row['can_afford'] and row['valid_targets']]


def move_toward(available, current, destinations):
    if not destinations:
        return None
    distance = lambda p: min(abs(p[0]-d[0])+abs(p[1]-d[1]) for d in destinations)
    offered = [(row, target) for row in available if row['behavior_id'] == 'action.move'
        for target in row['valid_targets'] if target['position'] is not None
        and distance(target['position']) < distance(current)]
    return min(offered, key=lambda pair: (distance(pair[1]['position']), pair[1]['path_cost'] or 0,
        target_key(pair[1]), action_key(pair[0])), default=None)


def select(state, actor, discovered, stage, leader):
    available = rows(discovered)
    current = state.actors[UUID(actor)].last_visual_position
    enemies = {str(key) for key, value in state.actors.items()
        if key not in state.viewing_audience.controlled and value.present
        and value.normal_hp > 0 and value.name != 'Gallery Curator'}
    attacks = [(row, target) for row in available
        if row['performs_attack'] or row['behavior_id'] == 'spell.magic_missile'
        for target in row['valid_targets'] if target['target_uuid'] in enemies]
    if attacks:
        return min(attacks, key=lambda pair: (pair[0]['behavior_id'] != 'spell.magic_missile',
            pair[0]['behavior_id'] != 'spell.fire_bolt', pair[1]['distance'] or 0,
            target_key(pair[1]), action_key(pair[0]))), stage
    if actor != leader:
        # The other original hero stays with the expedition, using offered paths.
        destination = state.actors[UUID(leader)].last_visual_position
        selected = move_toward(available, current, (destination,))
        return selected, stage
    name, goal = ROUTE[stage]
    if goal == 'open':
        identity = next((str(key) for key, value in state.objects.items() if value.item.name == name), None)
        option = next((row for row in discovered['world_interactions']
            if row['subject_uuid'] == identity and row['behavior_id'].endswith('.open')), None)
        if option is None:
            raise RuntimeError(f'No disclosed opening interaction for route door {name}')
        for row in available:
            if row['behavior_id'] != option['behavior_id'] or row['template_name'] != option['template_name']:
                continue
            target = next((target for target in row['valid_targets']
                if row['source_item_uuid'] == identity or target['target_uuid'] == identity), None)
            if target is not None:
                return (row, target), stage + 1
        selected = move_toward(available, current, option['contact_positions'])
    else:
        selected = move_toward(available, current, (goal,))
    if selected is not None:
        return selected, stage
    dash = next((row for row in available if row['behavior_id'] == 'action.dash'), None)
    return ((dash, dash['valid_targets'][0]) if dash else None), stage


async def record(url, token, output, diagnostic_commands=(), reference_trace=None, coarse_timing=False,
                 receipt_poll_seconds=.01):
    journal = output / 'journal'
    journal.mkdir()
    connection = await connect(url, token)
    while connection.bootstrap['status']['published_cursor'] is None:
        await connection.http.aclose()
        await asyncio.sleep(.05)
        connection = await connect(url, token)
    await attach(connection, {'acquisition_id': str(uuid4()),
        'expected_attachment_epoch': connection.bootstrap['status']['attachment_epoch']})
    state: PlayerState | None = None
    records = byte_count = 0
    stream_rows, consume_rows, ack_rows = [], [], []
    original_sse = transport.sse_records
    original_ack = transport.acknowledge

    async def measured_sse(chunks):
        async for event, event_id, raw in original_sse(chunks):
            stream_rows.append({'event': event, 'event_id': event_id,
                'complete_record_ns': perf_counter_ns(), 'bytes': len(raw)})
            yield event, event_id, raw

    async def measured_ack(client, cursor):
        start = perf_counter_ns()
        try:
            return await original_ack(client, cursor)
        finally:
            ack_rows.append({'sequence': cursor['sequence'], 'start_ns': start,
                'end_ns': perf_counter_ns()})

    async def consume(packet, raw):
        nonlocal state, records, byte_count
        entered = perf_counter_ns()
        byte_count += len(raw)
        if byte_count > 512 * 1024 * 1024:
            raise RuntimeError('Actual recording exceeded 512 MiB quota')
        path = journal / f"{packet['cursor']['sequence']:016}.json"
        if path.exists() and path.read_bytes() != raw:
            raise RuntimeError('Server replay changed bytes at a committed cursor')
        path.write_bytes(raw)
        file_done = perf_counter_ns()
        if packet['kind'] == 'initialization':
            parsed = InitializationResponse.model_validate_json(raw)
            state = reduce_initialization(parsed.initialization, content_additions=parsed.content_additions)
        else:
            assert state is not None
            state = reduce_operation(state, PlayerOperation.model_validate_json(raw))
        reduced = perf_counter_ns()
        consume_rows.append({'sequence': packet['cursor']['sequence'], 'kind': packet['kind'],
            'entered_ns': entered, 'file_done_ns': file_done, 'reduced_ns': reduced,
            'file_ms': (file_done-entered)/1e6, 'validate_reduce_ms': (reduced-file_done)/1e6,
            'bytes': len(raw)})
        records += 1

    instrumentation = patch.multiple(transport, sse_records=measured_sse, acknowledge=measured_ack)
    instrumentation.start()
    follower = Follower(connection, consume)
    following = asyncio.create_task(follow(follower))
    stage = 0
    leader = None
    trace, milestones = [], []
    ordering = None
    started = monotonic()
    try:
        async with asyncio.timeout(1200):
            while stage < len(ROUTE):
                if following.done():
                    await following
                    raise RuntimeError('Encounter ended before the gallery route completed')
                now = await status(connection)
                if now['published_cursor'] is not None:
                    await wait_for_cursor(follower, now['published_cursor'])
                actor = now['boundary']['input_actor_uuid']
                if actor is None:
                    await asyncio.sleep(.02)
                    continue
                assert state is not None
                if ordering is None:
                    ordering = observer_order(state)
                    (output / 'fixture-order.json').write_text(json.dumps({
                        'selection_policy': SELECTION_POLICY, 'observer_uuid_order': ordering,
                        'entity_uuid_policy': 'native random UUIDs; no UUID or gameplay overrides'}, indent=2))
                    if reference_trace is not None:
                        expected = reference_trace[0]['observer_order']
                        if [row['name'] for row in ordering] != expected:
                            raise RuntimeError(f'Observer UUID order differs from reference: '
                                f'{[row["name"] for row in ordering]} != {expected}; '
                                'this run cannot establish identical event-prefix ordering')
                if leader is None:
                    leader = next(str(key) for key in state.viewing_audience.controlled
                        if state.actors[key].name == 'Shield Fighter')
                name, goal = ROUTE[stage]
                current = state.actors[UUID(leader)].last_visual_position
                if goal != 'open' and tuple(current) == goal:
                    milestones.append({'name': name, 'position': list(current), 'cursor': follower.consumed,
                        'commands': len(trace), 'disclosed_tiles': len(state.tiles),
                        'disclosed_objects': len(state.objects), 'seconds': monotonic() - started})
                    (output / 'milestones.json').write_text(json.dumps(milestones, indent=2))
                    print(json.dumps({'milestone': milestones[-1]}), flush=True)
                    stage += 1
                    continue
                await transport.acknowledge(connection, follower.consumed)
                revision = now['boundary']['state_revision']
                choices_start = perf_counter_ns()
                answer = await choices(connection, {'actor_uuid': actor, 'state_revision': revision,
                    'force_attack': False, 'correlation_id': str(uuid4())})
                choices_end = perf_counter_ns()
                preview_ns = 0
                preview_calls = 0
                discovered = answer['choices']
                selected, next_stage = select(state, actor, discovered, stage, leader)
                intent, label, behavior = {'kind': 'end_turn'}, 'End turn', None
                selected_targets = []
                semantic_action = {'actor_name': state.actors[UUID(actor)].name, 'kind': 'end_turn'}
                if selected is not None:
                    row, target = selected
                    selected_targets.append(target_description(target))
                    selection = {'action_index': row['discovery_index'], 'target_indices': [target['index']],
                        'extra_target_positions': []}
                    for _ in range(12):
                        preview_start = perf_counter_ns()
                        result = await preview(connection, {'actor_uuid': actor, 'state_revision': revision,
                            'discovery_generation': discovered['discovery_generation'],
                            'correlation_id': str(uuid4()), 'selection': selection})
                        preview_ns += perf_counter_ns()-preview_start
                        preview_calls += 1
                        if result['preview']['can_confirm']:
                            break
                        options = result['preview']['next_targets']
                        if not options:
                            raise RuntimeError(f'Native preview rejected route selection: {result}')
                        chosen = min(options, key=target_key)
                        selection['target_indices'].append(chosen['index'])
                        selected_targets.append(target_description(chosen))
                    else:
                        raise RuntimeError('Native preview selection did not complete')
                    intent = {'kind': 'execute_selection', 'discovery_generation': discovered['discovery_generation'],
                        'selection': selection}
                    label, behavior = row['display_name'], row['behavior_id']
                    semantic_action = {'actor_name': state.actors[UUID(actor)].name,
                        'kind': 'execute_selection', 'action': list(action_key(row)),
                        'targets': selected_targets, 'extra_target_positions': selection['extra_target_positions']}
                if reference_trace is not None:
                    index = len(trace)
                    if index >= len(reference_trace) or semantic_action != reference_trace[index]['semantic_command']:
                        expected = reference_trace[index]['semantic_command'] if index < len(reference_trace) else None
                        raise RuntimeError(f'Native command {index + 1} differs from reference before submission: '
                            f'{semantic_action} != {expected}')
                command = {'command_number': now['next_command_number'], 'actor_uuid': actor,
                    'state_revision': revision, 'intent': intent}
                before_position = state.actors[UUID(actor)].last_visual_position
                submit_start = perf_counter_ns()
                outcome = await submit_command(connection, command)
                submit_end = perf_counter_ns()
                polls = 0
                while outcome['receipt']['kind'] == 'pending':
                    await asyncio.sleep(receipt_poll_seconds)
                    outcome = await receipt(connection, command['command_number'])
                    polls += 1
                committed_observed = perf_counter_ns()
                if outcome['receipt']['kind'] != 'committed':
                    raise RuntimeError(f'Command did not commit: {outcome}')
                await wait_for_cursor(follower, outcome['receipt']['cursor'])
                consumed = perf_counter_ns()
                stage = next_stage
                trace.append({'command': command, 'action': label, 'behavior_id': behavior, 'stage': stage,
                    'selection_policy': SELECTION_POLICY, 'semantic_command': semantic_action,
                    'observer_order': [row['name'] for row in ordering],
                    'actor_name': state.actors[UUID(actor)].name,
                    'before_position': before_position,
                    'timing': {'submit_start_ns': submit_start, 'submit_response_ns': submit_end,
                        'committed_receipt_ns': committed_observed, 'consumed_ns': consumed,
                        'submit_to_committed_ms': (committed_observed-submit_start)/1e6,
                        'submit_to_consumed_ms': (consumed-submit_start)/1e6,
                        'submit_response_ms': (submit_end-submit_start)/1e6,
                        'choices_ms': (choices_end-choices_start)/1e6,
                        'preview_ms': preview_ns/1e6, 'preview_calls': preview_calls,
                        'receipt_polls': polls, 'poll_sleep_seconds': receipt_poll_seconds,
                        'diagnostic': bool(diagnostic_commands),
                        'diagnostic_mode': 'coarse' if coarse_timing else 'full' if diagnostic_commands else None,
                        'worker_profile_selected': not coarse_timing and command['command_number'] in diagnostic_commands,
                        'worker_timing_selected': command['command_number'] in diagnostic_commands},
                    'position': state.actors[UUID(actor)].last_visual_position,
                    'hp': state.actors[UUID(actor)].normal_hp, 'cursor': follower.consumed,
                    'committed_receipt': outcome['receipt'],
                    'disclosed_tiles': len(state.tiles), 'disclosed_objects': len(state.objects)})
                (output / 'trace.json').write_text(json.dumps(trace, indent=2))
                print(json.dumps({key: value for key, value in trace[-1].items() if key != 'command'}), flush=True)
                if len(trace) >= 400:
                    raise RuntimeError('Route exceeded 400 actual commands')
        if reference_trace is not None and len(trace) != len(reference_trace):
            raise RuntimeError(f'Route command count differs from reference: {len(trace)} != {len(reference_trace)}')
        final = {'scenario': 'encounter.lantern_gallery', 'actor_uuid': leader,
            'actor_name': state.actors[UUID(leader)].name, 'commands': len(trace), 'records': records,
            'bytes': byte_count, 'final_cursor': follower.consumed, 'terminal': follower.completed,
            'final_position': state.actors[UUID(leader)].last_visual_position,
            'disclosed_tiles': len(state.tiles), 'disclosed_objects': len(state.objects),
            'seconds': monotonic() - started,
            'source': 'Original public SDK response bytes, current Python reducer, native choices/preview/commands. No state edits or synthetic packets.'}
        final['measurement'] = 'SDK submit to observed committed receipt/result cursor; includes normal polling and probe interference; separate stream/reduction/file/ACK timings. The entire diagnostic run is excluded from ordinary summaries.'
        final['diagnostic_commands'] = sorted(diagnostic_commands)
        final['diagnostic_mode'] = 'coarse' if coarse_timing else 'full' if diagnostic_commands else None
        final['selection_policy'] = SELECTION_POLICY
        final['reference_commands_matched'] = len(reference_trace) if reference_trace is not None else None
        final['observer_uuid_order'] = ordering
        final['comparison_note'] = ('Native entity UUIDs remain random. Reference checks require the same '
            'observer order and resolved command semantics; journal comparison remains required. '
            'Historical runs without this selection policy are separate cohorts.')
        (output / 'result.json').write_text(json.dumps(final, indent=2))
        print(json.dumps(final, indent=2), flush=True)
    finally:
        following.cancel()
        await asyncio.gather(following, return_exceptions=True)
        await connection.http.aclose()
        instrumentation.stop()
        for filename, values in (('probe-stream.jsonl', stream_rows),
                ('probe-consumption.jsonl', consume_rows), ('probe-ack.jsonl', ack_rows)):
            (output / filename).write_text(''.join(json.dumps(row)+'\n' for row in values))


async def run(args):
    if args.receipt_poll_ms <= 0:
        raise ValueError('--receipt-poll-ms must be positive')
    if args.coarse_timing and not args.diagnostic_commands.strip(', '):
        raise ValueError('--coarse-timing requires --diagnostic-commands')
    reference = json.loads(args.reference_trace.read_text()) if args.reference_trace is not None else None
    if reference is not None and (not reference or any(row.get('selection_policy') != SELECTION_POLICY
            or 'semantic_command' not in row or 'observer_order' not in row for row in reference)):
        raise ValueError('Reference trace must come from the semantic-ties-v1 runner; historical traces lack resolved target inputs')
    if reference is not None:
        # Item-bound discovery names contain run UUIDs, while their authored
        # template and disclosed display name identify the same native choice.
        for row in reference:
            action = row['semantic_command'].get('action')
            if action is not None:
                action[3] = action[3].split('__item_')[0]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    settings = configuration('crypt_gallery', output)
    config = output / 'server.json'
    config.write_text(settings.model_dump_json(indent=2))
    config.chmod(0o600)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    selected = {int(value) for value in args.diagnostic_commands.split(',') if value}
    with (output / 'server.log').open('wb') as log:
        entry = 'devtools.player_server_acceptance.movement_profile_host' if selected else \
            'devtools.player_server_acceptance.test_host'
        host_entry = ['-m', entry]
        host = await asyncio.create_subprocess_exec(sys.executable, *host_entry, '--config', str(config),
            '--stop', str(output / 'server.stop'), '--result', str(output / 'host-result.json'),
            '--port', str(port),
            *(['--diagnostic-commands', args.diagnostic_commands] if selected else []),
            *(['--coarse-timing'] if args.coarse_timing else []),
            stdout=log, stderr=log)
        try:
            async with asyncio.timeout(90):
                while not (output / 'host.ready').exists():
                    if host.returncode is not None:
                        raise RuntimeError('Owned host exited during startup; inspect server.log')
                    await asyncio.sleep(.05)
            async with asyncio.timeout(1250):
                await record(f'http://127.0.0.1:{port}', settings.credentials[0].token, output, selected, reference,
                    args.coarse_timing, args.receipt_poll_ms / 1000)
        finally:
            (output / 'server.stop').touch()
            await asyncio.wait_for(host.wait(), 25)
        if host.returncode != 0:
            raise RuntimeError('Owned host failed; inspect server.log')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic-commands', default='',
        help='Temporary full-path instrumentation and cProfile, e.g. 36,50; exclude this entire run from latency summaries.')
    parser.add_argument('--coarse-timing', action='store_true',
        help='With diagnostic commands, record outer owner wall spans and GC only; no cProfile or per-cell hooks. Still instrumented.')
    parser.add_argument('--reference-trace', type=Path,
        help='Reject different observer ordering or resolved native commands before submission; use a new semantic-ties-v1 reference.')
    parser.add_argument('--receipt-poll-ms', type=float, default=10,
        help='Receipt polling cadence. Use matching cadence in comparisons; 1 ms resolves the final 9.5 ms target.')
    asyncio.run(run(parser.parse_args()))
