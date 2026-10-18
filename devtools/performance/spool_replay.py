"""O2 (EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 §5 E0): replay an oracle run's spool through the transport path.

A fresh process, with a hash seed other than the live run's, serves the run's retained spool through the player
server's own routes (`server.app` over `server.recording`, the host's seats at their final publications) and
follows every seat with the SDK transport (`dnd_player.transport.follow`: initialization, event stream, ACK).
The first event stream of each seat is dropped half-way through its second operation, as a dropped connection,
so the follower resumes after the operation it consumed (a seat with two operations or more that did not resume
after a consumed operation fails). The
host serves a copy of the spool, so nothing the host does to its recording can touch the run's. Each record is folded by the client reference fold. After every
record the client state (memory included) must equal the live run's (the manifest's digests), the final states
must match, and the O3 views stored at each operation end must be reproduced. Each seat's digest stamps are
restored from its own records (`stamp_replay`) and must equal the live run's.

    PYTHONHASHSEED=1 PYTHONPATH=<tree>:<tree>/sdk/python/src <python with jsonschema-rs> \\
        devtools/performance/spool_replay.py <oracle directory>

The SDK needs `jsonschema-rs` (sdk/python/pyproject.toml). Exit status 0 when everything matches.
"""

import argparse
import asyncio
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from typing import Any, cast
from uuid import UUID, uuid4

import httpx

from devtools.performance import seat_oracle
from dnd.player.facts import PlayerInitialization, PlayerState, WorldUpdate
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.stamp_replay import replay_world_stamps
from dnd_player import contracts, transport as sdk
from server.app import create_app
from server.config import SeatCredential, ServerConfig
from server.protocol import InitializationResponse, PlayerOperation
from server.recording import AudienceSpool, Recording, close_recording
from server.worker_protocol import Publication


def retained_recording(directory: Path, seats: tuple[str, ...]) -> Recording:
    """A finished run's committed spool as its host holds it: every complete length-prefixed frame of each seat's
    file. The server has no reopening path, so this reads its format: `open_recording`'s file names and
    `stage_record`'s frames (a 4-byte big-endian length, then the payload)."""
    audiences = {}
    for seat in seats:
        path = directory / (sha256(seat.encode()).hexdigest() + '.frames')
        data = path.read_bytes()
        offsets, position = [], 0
        while position + 4 <= len(data):
            size, = struct.unpack('!I', data[position:position + 4])
            if position + 4 + size > len(data):
                break
            offsets.append((position, size))
            position += 4 + size
        audiences[seat] = AudienceSpool(path, path.open('r+b'), offsets, position)
    return Recording(directory, seat_oracle.SPOOL_QUOTA, audiences)


def cut_position(body: bytes) -> int:
    """Where to drop the first event stream: half-way through its second operation event, so the follower has
    consumed one operation and must resume after it; half-way through the stream when it holds one operation."""
    marks: list[int] = []
    index = body.find(b'\nevent: operation')
    while index >= 0 and len(marks) < 2:
        marks.append(index + 1)
        index = body.find(b'\nevent: operation', index + 1)
    if len(marks) < 2:
        return len(body) // 2
    end = body.find(b'\n\n', marks[1])
    return marks[1] + ((end if end >= 0 else len(body)) - marks[1]) // 2


class CutStream(httpx.AsyncBaseTransport):
    """The app's responses; the first event stream is dropped mid-way through its second operation (`cut_position`)."""

    def __init__(self, inner: httpx.AsyncBaseTransport):
        self.inner = inner
        self.resumed_after: list[int] = []  # the `after` cursor of each event stream requested

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self.inner.handle_async_request(request)
        if not request.url.path.endswith('/events'):
            return response
        self.resumed_after.append(int(request.url.params['after']))
        if len(self.resumed_after) > 1:
            return response
        body = await response.aread()
        return httpx.Response(response.status_code, headers=response.headers, content=body[:cut_position(body)])


def stored_views(directory: Path) -> dict[str, dict[int, list[str]]]:
    """The O3 views of the live run, by seat and the sequence of the seat's last record at that operation end."""
    views: dict[str, dict[int, list[str]]] = {}
    with gzip.open(directory / 'views.jsonl.gz', 'rt') as rows:
        for line in rows:
            row = json.loads(line)
            views.setdefault(row['seat'], {}).setdefault(row['sequence'], []).append(seat_oracle.canonical(row['view']))
    return views


def stamp_mismatches(seat: str, initialization: PlayerInitialization, updates: list[WorldUpdate],
                     manifest: dict[str, Any], counts: dict[str, Any]) -> list[dict[str, Any]]:
    """The seat's digest stamps restored from its records against the live run's: they must be equal."""
    memory = PlayerState(generation=initialization.generation, observer_uuid=initialization.observer_uuid,
                         world=initialization.world, audience=initialization.audience)
    restored = seat_oracle.stamp_data(replay_world_stamps(memory, updates))
    live = manifest['world_stamps'][seat]
    counts['stamps'] = {'tiles': len(restored['tiles']), 'objects': len(restored['objects'])}
    return [{'seat': seat, 'kind': 'stamp', 'record': kind, 'key': name, 'live': live[kind].get(name),
             'restored': restored[kind].get(name)}
            for kind in ('tiles', 'objects') for name in sorted(live[kind].keys() | restored[kind].keys())
            if live[kind].get(name) != restored[kind].get(name)]


async def follow_seat(app, seat: str, token: str, digests: list[str], views: dict[int, list[str]],
                      manifest: dict[str, Any]) -> tuple[PlayerState | None, list[dict[str, Any]], dict[str, Any]]:
    """Follow one seat from its initialization to its final cursor; its final state, mismatches and counts."""
    transport = CutStream(httpx.ASGITransport(app=app))
    mismatches: list[dict[str, Any]] = []
    counts: dict[str, Any] = {'records': 0, 'streams_after': [], 'views': 0}
    state: list[PlayerState] = []
    initializations: list[PlayerInitialization] = []
    updates: list[WorldUpdate] = []
    async with httpx.AsyncClient(transport=transport, base_url='http://replay.invalid',
                                 headers={'Authorization': 'Bearer ' + token}) as http:
        connection = sdk.Connection(http, cast(contracts.BootstrapResponse, {}))
        bootstrap, _ = await sdk.request(connection, 'GET', '/api/v1/bootstrap', 'BootstrapResponse')
        sdk.check_protocol(bootstrap['protocol'])
        connection.bootstrap = bootstrap
        await sdk.attach(connection, {'acquisition_id': str(uuid4()), 'expected_attachment_epoch': None})

        async def consume(packet: Any, raw: bytes) -> None:
            if packet['kind'] == 'initialization':
                initial = InitializationResponse.model_validate_json(raw)
                state[:] = [reduce_initialization(initial.initialization, content_additions=initial.content_additions)]
                initializations[:] = [initial.initialization]
                updates[:] = list(initial.initialization.world_updates)
            else:
                operation = PlayerOperation.model_validate_json(raw)
                state[0] = reduce_operation(state[0], operation)
                updates.extend(update for lineage in operation.lineages for update in lineage.world_updates)
            sequence = packet['cursor']['sequence']
            counts['records'] += 1
            digest = seat_oracle.state_digest(state[0])
            if sequence >= len(digests) or digest != digests[sequence]:
                mismatches.append({'seat': seat, 'sequence': sequence, 'kind': 'state'})
            for expected in views.get(sequence, ()):
                counts['views'] += 1
                if seat_oracle.canonical(seat_oracle.client_view(state[0])) != expected:
                    mismatches.append({'seat': seat, 'sequence': sequence, 'kind': 'view'})

        follower = sdk.Follower(connection, consume)
        await sdk.follow(follower, reconnect_timeout=30)
        counts['streams_after'] = transport.resumed_after
    if initializations:
        mismatches.extend(stamp_mismatches(seat, initializations[0], updates, manifest, counts))
    if counts['records'] != len(digests):
        mismatches.append({'seat': seat, 'kind': 'records', 'replayed': counts['records'], 'live': len(digests)})
    # A seat with two operations or more must have resumed after a consumed operation, not from the start.
    if len(digests) >= 3 and (len(transport.resumed_after) < 2 or transport.resumed_after[1] < 1):
        mismatches.append({'seat': seat, 'kind': 'no_resume', 'streams_after': transport.resumed_after})
    return (state[0] if state else None), mismatches, counts


async def replay(directory: Path) -> dict[str, Any]:
    manifest = json.loads((directory / 'manifest.json').read_text())
    seats = tuple(manifest['publications'])
    tokens = {seat: f'replay-credential-{index:06d}-{seat}' for index, seat in enumerate(seats)}
    views = stored_views(directory)
    with gzip.open(directory / 'final_states.json.gz', 'rt') as source:
        finals = json.load(source)
    with tempfile.TemporaryDirectory() as scratch:
        app = create_app(ServerConfig(game_id=manifest['game_id'], encounter_id=None, spool_directory=Path(scratch),
            credentials=tuple(SeatCredential(seat_id=seat, token=tokens[seat]) for seat in seats)))
        host = app.state.player_host
        close_recording(host.recording)  # the empty spool a new host opens; a copy of the run's replaces it
        shutil.copytree(directory / 'spool', Path(scratch) / 'retained')
        host.recording = retained_recording(Path(scratch) / 'retained', seats)
        host.epoch = UUID(manifest['game_epoch'])
        for seat in seats:
            publication = Publication.model_validate(manifest['publications'][seat])
            host.seats[seat].audience_id = publication.cursor.audience_id
            # The retained prefix of a finished game: its stream ends at the final cursor.
            host.seats[seat].publication = publication.model_copy(update={'boundary': publication.boundary.model_copy(
                update={'lifecycle': 'terminal', 'input_actor_uuid': None, 'state_revision': None})})
        results = {}
        try:
            for seat in seats:
                try:
                    final, mismatches, counts = await follow_seat(app, seat, tokens[seat], manifest['digests'][seat],
                                                                  views.get(seat, {}), manifest)
                except (sdk.ApiError, sdk.ProtocolError, httpx.HTTPError) as error:
                    # A transport failure is a replay mismatch: the seat cannot reach its final cursor.
                    final, counts = None, {'records': 0, 'streams_after': [], 'views': 0}
                    mismatches = [{'seat': seat, 'kind': 'transport', 'error': f'{type(error).__name__}: {error}'}]
                if final is None or seat_oracle.canonical(seat_oracle.state_data(final)) != seat_oracle.canonical(finals[seat]):
                    mismatches.append({'seat': seat, 'kind': 'final'})
                results[seat] = {**counts, 'mismatches': mismatches[:20], 'mismatch_count': len(mismatches)}
        finally:
            close_recording(host.recording)
    return {'live_hash_seed': manifest.get('hash_seed'), 'replay_hash_seed': os.environ.get('PYTHONHASHSEED'),
            'passed': all(row['mismatch_count'] == 0 for row in results.values()), 'seats': results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.directory / 'manifest.json').read_text())
    if os.environ.get('PYTHONHASHSEED') in (None, 'random') or os.environ['PYTHONHASHSEED'] == manifest.get('hash_seed'):
        parser.error('set PYTHONHASHSEED to a fixed value other than the live run\'s')
    result = asyncio.run(replay(args.directory))
    (args.directory / 'o2.json').write_text(json.dumps(result, indent=1))
    print(json.dumps({'passed': result['passed'], 'seats': {seat: {key: row[key] for key in
        ('records', 'streams_after', 'views', 'mismatch_count')} for seat, row in result['seats'].items()}}))
    sys.exit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
