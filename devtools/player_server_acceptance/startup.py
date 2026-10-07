"""Fresh native-worker startup decomposition on Windows or Linux, without graphics."""
from time import perf_counter
STARTED = perf_counter()

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
from uuid import uuid4

from devtools.player_server_acceptance.fixtures import configuration
from dnd.core.events import EventQueue
from dnd.player.session import close_session
from player_server.worker import dispatch, needs_advance, start
from player_server.worker_protocol import Advance, Start

IMPORTED = perf_counter()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('crypt', 'two_sides', 'per_entity'), default='crypt')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = configuration(args.mode, args.output.parent)
    request = Start(game_id=config.game_id, game_epoch=uuid4(),
        audience_ids={seat.seat_id: uuid4() for seat in config.credentials}, encounter_id=config.encounter_id,
        recipe=config.recipe, assignments=config.assignments, test_seed=0)
    before = perf_counter()
    runtime, reply, records = start(request)
    ready = perf_counter()
    encoded_bytes = sum(len(record.model_dump_json()) for record in records)
    encoded = perf_counter()
    advances = 0
    while needs_advance(runtime.session):
        reply, records, _ = dispatch(runtime, Advance())
        encoded_bytes += sum(len(record.model_dump_json()) for record in records)
        advances += 1
    completed = perf_counter()
    root = Path(__file__).resolve().parents[2]
    result = {'mode': args.mode, 'python': sys.version, 'executable': sys.executable,
        'platform': platform.platform(), 'source': str(root),
        'scope': 'Fresh native process; includes imports/startup/capture/encoding/advance; excludes HTTP host and pipe launch',
        'import_ms': (IMPORTED - STARTED) * 1000, 'start_capture_ms': (ready - before) * 1000,
        'encode_ms': (encoded - ready) * 1000, 'advance_encode_ms': (completed - encoded) * 1000,
        'total_ms': (completed - STARTED) * 1000, 'bytes': encoded_bytes, 'advances': advances,
        'events': EventQueue.event_cursor(), 'seats': len(runtime.audiences),
        'source_sha256': {path: sha256((root/path).read_bytes()).hexdigest() for path in (
            'dnd/core/events.py', 'dnd/player/capture.py', 'dnd/player/application.py',
            'dnd/player/session.py', 'player_server/worker.py', 'uv.lock')}}
    close_session(runtime.session)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
