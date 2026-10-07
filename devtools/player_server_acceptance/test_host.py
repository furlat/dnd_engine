"""Owned acceptance host with a stop file, including Windows interop cleanup."""
import argparse
import asyncio
from collections import deque
from contextlib import nullcontext
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from time import time_ns
from unittest.mock import patch

import uvicorn

from player_server.app import create_app
from player_server import connection
from player_server.config import ServerConfig


async def run(args):
    app = create_app(ServerConfig.model_validate_json(args.config.read_bytes()))
    host = app.state.player_host
    worker_process = None
    server = uvicorn.Server(uvicorn.Config(app, host=args.host, port=args.port, log_level='warning',
        timeout_graceful_shutdown=5))
    async def first_human_publication():
        nonlocal worker_process
        async with host.changed:
            await host.changed.wait_for(lambda: all(seat.publication is not None for seat in host.seats.values())
                and any(seat.publication is not None
                    and seat.publication.boundary.lifecycle == 'waiting_for_human'
                    and seat.publication.boundary.input_actor_uuid is not None for seat in host.seats.values()))
            observed = time_ns()
            worker_process = host.process.process if host.process is not None else None
            publications = {key: {'cursor': seat.publication.cursor.model_dump(mode='json'),
                'boundary': seat.publication.boundary.model_dump(mode='json')}
                for key, seat in host.seats.items() if seat.publication is not None}
        args.result.with_name('host-first-human-boundary.json').write_text(json.dumps({
            'observed_unix_ns': observed, 'publications': publications,
            'scope': 'Host observed all seat initial publications committed and at least one published waiting-for-human boundary; includes native process launch, imports, pre-Start policy, initialization, advancement, encoding, pipe transfer and recording commit. Excludes SDK startup, attachment and consumption.'}, indent=2))

    async def watch():
        announced = False
        while not args.stop.exists():
            if server.started and not announced:
                args.result.with_name('host.ready').touch()
                announced = True
            await asyncio.sleep(.05)
        server.should_exit = True
    watcher = asyncio.create_task(watch())
    publication_watcher = asyncio.create_task(first_human_publication())
    async def profiled_launch():
        process = await asyncio.create_subprocess_exec(sys.executable, '-m',
            'devtools.player_server_acceptance.gc_worker', '--output', str(args.worker_profile),
            '--census-after-commands', str(args.profile_census_after),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        diagnostics = deque(maxlen=64)
        return connection.Connection(process, diagnostics, asyncio.create_task(connection._drain(process.stderr, diagnostics)))
    try:
        with patch.object(connection, 'launch', profiled_launch) if args.worker_profile is not None else nullcontext():
            await server.serve()
    finally:
        watcher.cancel()
        publication_watcher.cancel()
        await asyncio.gather(watcher, publication_watcher, return_exceptions=True)
        root = Path(__file__).resolve().parents[2]
        args.result.write_text(json.dumps({'pid': os.getpid(), 'worker_pid': None if worker_process is None else worker_process.pid,
            'worker_returncode': None if worker_process is None else worker_process.returncode,
            'timings': host.timings, 'delivery_bytes': host.delivery_bytes, 'query_bytes': host.query_bytes,
            'receipt_bytes': {key: seat.receipt_bytes for key, seat in host.seats.items()},
            'receipt_counts': {key: len(seat.receipts) for key, seat in host.seats.items()},
            'spool_bytes': {key: spool.committed_bytes for key, spool in host.recording.audiences.items()},
            'source_sha256': {path: sha256((root / path).read_bytes()).hexdigest() for path in (
                'dnd/core/events.py', 'dnd/core/aoe.py', 'dnd/player/capture.py', 'dnd/player/application.py',
                'dnd/player/session.py',
                'dnd/player/content_composition.py', 'dnd/player/reduction.py', 'dnd/entity.py',
                'dnd/core/values.py', 'dnd/blocks/health.py', 'dnd/blocks/abilities.py',
                'dnd/blocks/equipment.py', 'dnd/player/projection.py', 'player_server/worker.py',
                'dnd/controller.py', 'dnd/encounter.py', 'dnd/core/base_object.py',
                'dnd/core/gridmap.py', 'dnd/blocks/sensory.py', 'player_server/protocol.py',
                'player_server/host.py', 'player_server/app.py', 'sdk/python/src/dnd_player/transport.py',
                'sdk/python/pyproject.toml', 'uv.lock')}}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--stop', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8795)
    parser.add_argument('--worker-profile', type=Path)
    parser.add_argument('--profile-census-after', type=int, default=200)
    asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    main()
