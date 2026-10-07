"""Actual SDK command-to-consumption timings; no native engine imports."""
import argparse
import asyncio
import json
from pathlib import Path
import statistics
from time import perf_counter, time_ns
from uuid import uuid4

import httpx

from dnd_player import Follower, acknowledge, attach, connect, follow, receipt, status, submit_command, wait_for_cursor
from devtools.player_server_acceptance.combat_http import intent as combat_intent


def summary(values):
    if not values:
        return {'samples': 0}
    ordered = sorted(values)
    result = {'samples': len(values), 'mean_ms': statistics.fmean(values), 'median_ms': statistics.median(values),
        'minimum_ms': min(values), 'maximum_ms': max(values)}
    if len(values) >= 100:
        result.update(p95_ms=ordered[(95 * len(values) + 99) // 100 - 1], p99_ms=ordered[(99 * len(values) + 99) // 100 - 1])
    return result


async def monitor(args):
    config = json.loads(args.config.read_text())
    token = config['credentials'][0]['token']
    async with httpx.AsyncClient(base_url=args.url, headers={'Authorization': 'Bearer ' + token}, timeout=10) as http:
        bootstrap = (await http.get('/api/v1/bootstrap')).json()['status']
        headers = {'X-Game-Epoch': bootstrap['game_epoch'], 'X-Audience-Id': bootstrap['audience_id']}
        paths = {'health': '/health', 'status': '/api/v1/games/' + bootstrap['game_id'] + '/status'}
        rows = []
        (args.output / 'monitor.ready').touch()
        while not (args.output / 'monitor.start').exists():
            if (args.output / 'monitor.stop').exists():
                (args.output / 'monitor.json').write_text(json.dumps({'aborted_before_start': True}))
                return
            await asyncio.sleep(.01)
        while not (args.output / 'monitor.stop').exists() or len(rows) < 200:
            for kind, path in paths.items():
                started = perf_counter()
                response = await http.get(path, headers=headers)
                elapsed = (perf_counter() - started) * 1000
                response.raise_for_status()
                response.json()
                rows.append({'kind': kind, 'ms': elapsed})
            await asyncio.sleep(.005)
    (args.output / 'monitor.json').write_text(json.dumps({'summaries': {
        kind: summary([row['ms'] for row in rows if row['kind'] == kind]) for kind in paths}, 'rows': rows}, indent=2))


async def client(args):
    config = json.loads(args.config.read_text())
    connections = {}
    followers = {}
    tasks = []
    counts = {}
    byte_counts = {}
    commands = {}
    rows = []
    progress = {}
    try:
        for credential in config['credentials']:
            seat = credential['seat_id']
            connection = await connect(args.url, credential['token'])
            connections[seat] = connection
            current = connection.bootstrap['status']
            while current['published_cursor'] is None:
                await asyncio.sleep(.05)
                current = await status(connection)
            # status() verifies the original game, epoch and audience before
            # refreshing the attachment epoch; retain the bootstrap identity.
            connection.bootstrap['status'] = current
            await attach(connection, {'acquisition_id': str(uuid4()),
                'expected_attachment_epoch': current['attachment_epoch']})
            directory = args.output / seat
            directory.mkdir()
            counts[seat] = byte_counts[seat] = commands[seat] = 0
            async def consume(packet, raw, seat=seat, directory=directory):
                assert packet['cursor']['sequence'] == counts[seat]
                byte_counts[seat] += len(raw)
                if byte_counts[seat] > 128 * 1024 * 1024:
                    raise RuntimeError('Probe disk-recording quota exceeded')
                (directory / f"{packet['cursor']['sequence']:06}.json").write_bytes(raw)
                counts[seat] += 1
            followers[seat] = Follower(connection, consume)
            tasks.append(asyncio.create_task(follow(followers[seat])))
        while not (args.output / 'monitor.ready').exists():
            await asyncio.sleep(.01)
        async with asyncio.timeout(30):
            while True:
                eligible = None
                for seat, connection in connections.items():
                    current = await status(connection)
                    await wait_for_cursor(followers[seat], current['published_cursor'])
                    await acknowledge(connection, followers[seat].consumed)
                    if current['boundary']['lifecycle'] == 'waiting_for_human' and current['boundary']['input_actor_uuid'] is not None:
                        eligible = seat, current
                if eligible is not None:
                    seat, current = eligible
                    (args.output / 'first-human-boundary.json').write_text(json.dumps({
                        'observed_unix_ns': time_ns(), 'seat': seat, 'cursor': current['published_cursor'],
                        'boundary': current['boundary'], 'scope': 'SDK observed and consumed the initialized published cursor of every seat and an own waiting-for-human boundary; includes SDK process startup, connection, attachment, validation, recording, consumption and acknowledgement.'}, indent=2))
                    break
                await asyncio.sleep(.01)
        (args.output / 'monitor.start').touch()
        async with asyncio.timeout(240):
            for _ in range(args.commands):
                while True:
                    eligible = None
                    terminal = True
                    for seat, connection in connections.items():
                        current = await status(connection)
                        await wait_for_cursor(followers[seat], current['published_cursor'])
                        await acknowledge(connection, followers[seat].consumed)
                        boundary = current['boundary']
                        terminal = terminal and boundary['lifecycle'] == 'terminal'
                        if boundary['input_actor_uuid'] is not None and boundary['lifecycle'] == 'waiting_for_human':
                            eligible = seat, connection, current
                    if eligible is not None:
                        break
                    if terminal:
                        break
                    await asyncio.sleep(.001)
                if terminal:
                    break
                seat, connection, current = eligible
                evidence = {'action': 'end_turn', 'discovery_ms': None, 'preview_ms': [], 'targets': []}
                intent = {'kind': 'end_turn'}
                if args.combat_case is not None:
                    intent, evidence = await combat_intent(connection, args.combat_case, seat,
                        current['boundary']['input_actor_uuid'], current['boundary']['state_revision'], progress)
                command = {'command_number': current['next_command_number'], 'actor_uuid': current['boundary']['input_actor_uuid'],
                    'state_revision': current['boundary']['state_revision'], 'intent': intent}
                started = perf_counter()
                response = await submit_command(connection, command)
                submitted = perf_counter()
                while response['receipt']['kind'] == 'pending':
                    await asyncio.sleep(.001)
                    response = await receipt(connection, command['command_number'])
                committed = perf_counter()
                if response['receipt']['kind'] != 'committed':
                    raise AssertionError(response)
                await wait_for_cursor(followers[seat], response['receipt']['cursor'])
                consumed = perf_counter()
                await acknowledge(connection, followers[seat].consumed)
                rows.append({'seat': seat, 'command_number': command['command_number'], **evidence,
                    'cursor': response['receipt']['cursor'], 'submit_ms': (submitted - started) * 1000,
                    'committed_ms': (committed - started) * 1000, 'consumed_ms': (consumed - started) * 1000,
                    'acknowledged_ms': (perf_counter() - started) * 1000})
                commands[seat] += 1
        for seat, connection in connections.items():
            current = await status(connection)
            await wait_for_cursor(followers[seat], current['published_cursor'])
            await acknowledge(connection, followers[seat].consumed)
        if args.combat_case is not None and all(follower.status is not None
                and follower.status['boundary']['lifecycle'] == 'terminal' for follower in followers.values()):
            await asyncio.gather(*tasks)
        result = {'commands': commands, 'records': counts, 'bytes': byte_counts,
            'consumed': {seat: follower.consumed for seat, follower in followers.items()},
            'latencies': {key: summary([row[key] for row in rows]) for key in ('submit_ms', 'committed_ms', 'consumed_ms', 'acknowledged_ms')},
            'rows': rows, 'terminal': all(follower.completed for follower in followers.values()), 'combat_case': args.combat_case}
        (args.output / 'result.json').write_text(json.dumps(result, indent=2))
        if args.combat_case is not None and not result['terminal']:
            raise AssertionError('Finite combat exceeded the command budget')
        if args.combat_case is not None:
            expected = 'action.attack' if args.combat_case in ('melee', 'ranged') else \
                'spell.fireball' if args.combat_case == 'fireball_six_goblins' else 'spell.' + args.combat_case
            if not any(row['action'] == expected for row in rows):
                raise AssertionError(f'Finite fight did not exercise requested {expected}')
    finally:
        (args.output / 'monitor.stop').touch()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.gather(*(connection.http.aclose() for connection in connections.values()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('client', 'monitor'))
    parser.add_argument('--url', required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--commands', type=int, default=200)
    parser.add_argument('--combat-case')
    args = parser.parse_args()
    asyncio.run({'client': client, 'monitor': monitor}[args.mode](args))


if __name__ == '__main__':
    main()
