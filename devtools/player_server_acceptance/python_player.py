"""Independent installed-SDK opponent; no engine or server imports."""
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

from dnd_player import (ApiError, Follower, acknowledge, attach, choices, connect, follow,
    preview, receipt, status, submit_command, wait_for_cursor)


async def play():
    connection = await connect(os.environ['PLAYER_URL'], os.environ['PLAYER_TOKEN'])
    output = Path(os.environ['PLAYER_OUTPUT']); output.mkdir(parents=True, exist_ok=True)
    while connection.bootstrap['status']['published_cursor'] is None:
        await connection.http.aclose()
        await asyncio.sleep(.05)
        connection = await connect(os.environ['PLAYER_URL'], os.environ['PLAYER_TOKEN'])
    await attach(connection, {'acquisition_id': str(uuid4()), 'expected_attachment_epoch': connection.bootstrap['status']['attachment_epoch']})
    count, byte_count = 0, 0
    async def consume(packet, raw):
        nonlocal count, byte_count
        byte_count += len(raw)
        if byte_count > 128 * 1024 * 1024:
            raise RuntimeError('Acceptance recording quota exceeded')
        (output / f"{packet['cursor']['sequence']:06}.json").write_bytes(raw)
        count += 1
    follower = Follower(connection, consume)
    task = asyncio.create_task(follow(follower))
    commands = 0
    try:
        async with asyncio.timeout(120):
            while not task.done():
                current = await status(connection)
                head = current['published_cursor']
                if head is not None:
                    await wait_for_cursor(follower, head)
                actor = current['boundary']['input_actor_uuid']
                if actor is None or current['boundary']['lifecycle'] != 'waiting_for_human':
                    await asyncio.sleep(.02)
                    continue
                # Explicit ACK makes command readiness deterministic for this record-only consumer.
                await acknowledge(connection, follower.consumed)
                current = await status(connection)
                revision = current['boundary']['state_revision']
                if current['boundary']['input_actor_uuid'] != actor or revision is None:
                    continue
                query = {'actor_uuid': actor, 'state_revision': revision, 'force_attack': False, 'correlation_id': str(uuid4())}
                discovered = await choices(connection, query)
                actions = discovered['choices']
                candidates = [row for row in actions['entity_actions'] if row['performs_attack'] and row['can_afford'] and row['valid_targets']]
                intent = {'kind': 'end_turn'}
                if not candidates:
                    movement = next((row for row in actions['position_actions'] if row['behavior_id'] == 'action.move' and row['can_afford'] and row['valid_targets']), None)
                    if movement is not None:
                        target = min(movement['valid_targets'], key=lambda t: abs(t['position'][0] - 7) + abs(t['position'][1] - 7))
                        movement = dict(movement, valid_targets=[target])
                        candidates = [movement]
                if candidates:
                    row = candidates[0]
                    selection = {'action_index': row['discovery_index'], 'target_indices': [row['valid_targets'][0]['index']], 'extra_target_positions': []}
                    result = await preview(connection, {'actor_uuid': actor, 'state_revision': revision,
                        'discovery_generation': actions['discovery_generation'], 'correlation_id': str(uuid4()), 'selection': selection})
                    if not result['preview']['can_confirm']:
                        raise AssertionError('Single weapon target did not complete selection')
                    intent = {'kind': 'execute_selection', 'discovery_generation': actions['discovery_generation'], 'selection': selection}
                command = {'command_number': current['next_command_number'], 'actor_uuid': actor, 'state_revision': revision, 'intent': intent}
                pending = await submit_command(connection, command)
                # Same payload retry must never execute twice.
                await submit_command(connection, command)
                while pending['receipt']['kind'] == 'pending':
                    await asyncio.sleep(.01)
                    pending = await receipt(connection, command['command_number'])
                if pending['receipt']['kind'] != 'committed':
                    raise AssertionError(pending)
                await wait_for_cursor(follower, pending['receipt']['cursor'])
                commands += 1
                if commands > 80:
                    raise AssertionError('Encounter did not terminate')
            await task
        (output / 'result.json').write_text(json.dumps({'language': 'python', 'commands': commands,
            'records': count, 'bytes': byte_count, 'final_cursor': follower.consumed, 'terminal': follower.completed}))
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await connection.http.aclose()


if __name__ == '__main__':
    asyncio.run(play())
