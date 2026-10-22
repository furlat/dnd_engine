"""Own one SDK attachment, its authorized records, and command receipts."""
import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
import json
from typing import Any
from uuid import uuid4

import httpx
from dnd_player import (ApiError, Connection, Follower, acknowledge, attach, choices, connect,
    follow, preview, receipt, status, submit_command, wait_for_cursor)
from dnd_player.transport import validate

from monty_sandbox.observe import Observer, ignore


@dataclass
class Player:
    connection: Connection
    packets: list[dict[str, Any]] = field(default_factory=list)
    record_bytes: int = 0
    follower: Follower | None = None
    following: asyncio.Task | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    commands: list[dict[str, Any]] = field(default_factory=list)
    unresolved: dict[str, Any] | None = None
    audience: dict[str, Any] | None = None


def consume_record(player: Player, packet: dict, raw: bytes, observe: Observer = ignore) -> None:
    """Retain a record and fold only its ordered current membership."""
    if player.record_bytes + len(raw) > 64 * 1024 * 1024:
        raise RuntimeError('Trial recording quota reached')
    player.packets.append(packet)
    player.record_bytes += len(raw)
    initial = packet.get('initialization')
    if initial is not None:
        player.audience = initial['audience']
        groups = (initial['nodes'],)
    else:
        groups = (lineage['events'] for lineage in packet.get('lineages', []))
    for nodes in groups:
        for node in nodes:
            fact = node.get('fact')
            if not node.get('canceled') and fact is not None and fact['kind'] == 'audience':
                player.audience = fact['audience']
    observe({'kind': 'record', 'cursor': packet['cursor'], 'boundary': packet.get('boundary'), 'bytes': len(raw),
        'audience': player.audience,
        'logs': [node['combat_log']['compact'] for lineage in packet.get('lineages', [])
            for node in lineage['events'] if node.get('combat_log')] +
            [row['entry']['compact'] for row in packet.get('combat_log_appends', [])]})


async def open_player(url: str, credential: str, observe: Observer = ignore,
                      *, expected_attachment_epoch: str | None = None) -> Player:
    connection = await connect(url, credential)
    player = None
    try:
        async with asyncio.timeout(60):
            while connection.bootstrap['status']['published_cursor'] is None:
                await connection.http.aclose()
                await asyncio.sleep(.1)
                connection = await connect(url, credential)
        attached_epoch = connection.bootstrap['status']['attachment_epoch']
        if expected_attachment_epoch is None and attached_epoch is not None:
            raise ValueError('Seat already attached; this client never replaces another player')
        if expected_attachment_epoch != attached_epoch:
            raise ValueError('Expected attachment epoch does not match the current seat attachment')
        await attach(connection, {'acquisition_id': str(uuid4()),
            'expected_attachment_epoch': expected_attachment_epoch})
        player = Player(connection)

        async def consume(packet, raw):
            consume_record(player, packet, raw, observe)

        player.follower = Follower(connection, consume)
        player.following = asyncio.create_task(follow(player.follower), name='monty-player-stream')
        await wait_for_cursor(player.follower, connection.bootstrap['status']['published_cursor'])
        return player
    except BaseException:
        if player is not None and player.following is not None:
            player.following.cancel()
            await asyncio.gather(player.following, return_exceptions=True)
        await connection.http.aclose()
        raise


async def close_player(player: Player) -> None:
    if player.following is not None:
        player.following.cancel()
        await asyncio.gather(player.following, return_exceptions=True)
    await player.connection.http.aclose()


async def read_game(player: Player) -> dict:
    current = await status(player.connection)
    if current['published_cursor'] is not None:
        await wait_for_cursor(player.follower, current['published_cursor'])
    if player.follower.failure is not None:
        raise RuntimeError(str(player.follower.failure))
    await acknowledge(player.connection, player.follower.consumed)
    return {'status': current, 'cursor': player.follower.consumed,
        'audience': player.audience if player.audience is not None else player.connection.bootstrap['audience'],
        'record_count': len(player.packets), 'record_bytes': player.record_bytes,
        'commands': player.commands[-8:], 'unresolved_command': player.unresolved}


def events(records: Sequence[dict], after: int = -1, limit: int = 16) -> dict:
    if after < -1 or not 1 <= limit <= 64:
        raise ValueError('after must be >= -1 and limit between 1 and 64')
    rows = list(records[after + 1:after + 1 + limit])
    return {'records': rows, 'next_after': rows[-1]['cursor']['sequence'] if rows else after,
        'has_more': after + 1 + len(rows) < len(records)}


async def discover(player: Player, force_attack: bool = False) -> dict:
    async with player.lock:
        observation = await read_game(player)
        current = observation['status']
        actor = current['boundary']['input_actor_uuid']
        if actor not in observation['audience']['controlled']:
            raise ValueError('Not a controlled actor input boundary; use game_wait(game_ref)')
        return await choices(player.connection, {'actor_uuid': actor,
            'state_revision': current['boundary']['state_revision'],
            'force_attack': force_attack, 'correlation_id': str(uuid4())})


async def preview_action(player: Player, actor_uuid: str, state_revision: str,
                         discovery_generation: int, selection: dict) -> dict:
    async with player.lock:
        return await preview(player.connection, {'actor_uuid': actor_uuid,
            'state_revision': state_revision, 'discovery_generation': discovery_generation,
            'correlation_id': str(uuid4()), 'selection': selection})


async def submit_saved(player: Player) -> dict:
    """Submit the saved payload with the seat lock held; retain transport ambiguity."""
    try:
        result = await submit_command(player.connection, player.unresolved)
    except ApiError as error:
        # A typed error from this endpoint precedes command admission.
        player.commands[-1]['api_error'] = error.value
        player.unresolved = None
        raise
    player.commands[-1]['receipt'] = result['receipt']
    return result


async def settle(player: Player) -> dict:
    """Called with the seat lock held. Never allocate a replacement command number."""
    command = player.unresolved
    if command is None:
        raise ValueError('No unresolved command')
    async with asyncio.timeout(30):
        while True:
            result = await receipt(player.connection, command['command_number'])
            kind = result['receipt']['kind']
            if kind == 'unknown':
                # Retry the exact saved payload; the server owns deduplication.
                result = await submit_saved(player)
                kind = result['receipt']['kind']
            player.commands[-1]['receipt'] = result['receipt']
            if kind == 'committed':
                await wait_for_cursor(player.follower, result['receipt']['cursor'])
                player.unresolved = None
                return {'receipt': result['receipt'], 'observation': await read_game(player)}
            if kind == 'rejected':
                player.unresolved = None
                return {'receipt': result['receipt'], 'observation': await read_game(player)}
            if kind not in ('pending', 'unknown'):
                raise RuntimeError(f'Command outcome {kind}; new actions blocked')
            # Receipt endpoint has no long-poll; bounded polling checks an actual condition.
            await asyncio.sleep(.05)


async def act(player: Player, actor_uuid: str, state_revision: str, intent: dict) -> dict:
    async with player.lock:
        if player.unresolved is not None:
            raise ValueError('Resolve the previous command with game_receipt(game_ref) before another action')
        current = (await read_game(player))['status']
        command = {'command_number': current['next_command_number'], 'actor_uuid': actor_uuid,
            'state_revision': state_revision, 'intent': intent}
        validate('CommandRequest', command)
        player.unresolved = json.loads(json.dumps(command))
        player.commands.append({'command': player.unresolved, 'receipt': None})
        try:
            await submit_saved(player)
        except httpx.TransportError:
            pass  # Submission may have reached the server. Resolve this saved command.
        return await settle(player)


async def resolve_receipt(player: Player) -> dict:
    async with player.lock:
        return await settle(player)


async def wait_game(player: Player, timeout_seconds: float = 20) -> dict:
    if not 0 < timeout_seconds <= 30:
        raise ValueError('timeout_seconds must be in (0, 30]')
    try:
        async with asyncio.timeout(timeout_seconds):
            while True:
                previous_status = player.follower.status
                previous_cursor = player.follower.consumed
                observation = await read_game(player)
                boundary = observation['status']['boundary']
                if boundary['lifecycle'] in ('outside_encounter', 'terminal', 'failed', 'closed') or (
                        boundary['lifecycle'] in ('waiting_for_human', 'waiting_for_codex') and
                        boundary['input_actor_uuid'] in observation['audience']['controlled']):
                    return {'wait_timed_out': False, **observation}
                # Stream status may lag a consumed operation. Recheck HTTP after progress,
                # including progress during read_game, rather than trusting an old turn.
                async with player.follower.changed:
                    await player.follower.changed.wait_for(lambda: player.follower.failure is not None or
                        player.follower.status != previous_status or player.follower.consumed != previous_cursor)
    except TimeoutError:
        return {'wait_timed_out': True, **await read_game(player)}
