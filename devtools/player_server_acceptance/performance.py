"""Gate B measurements through the unchanged native worker and public encoding.

The retention lane intentionally paces operations; latency excludes that pacing.
No native events, capture, authorization, logs or audiences are disabled.
"""
from time import perf_counter
IMPORT_STARTED = perf_counter()

import argparse
import cProfile
import gc
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import pstats
import resource
import statistics
import subprocess
import sys
import time
from typing import Any
from uuid import uuid4

from dnd.action_timing import reset_action_timing_recorder, set_action_timing_recorder
from dnd.core.events import EventQueue
from dnd.player.commands import ActionSelection
from dnd.player.session import close_session
from devtools.player_server_acceptance.fixtures import configuration
from server.protocol import ChoicesRequest, CommandRequest, EndTurnIntent, ExecuteSelectionIntent, PreviewRequest
from server.worker import Runtime, dispatch, needs_advance, start
from server.worker_protocol import Advance, Choices, Command, Preview, Start

IMPORT_SECONDS = perf_counter() - IMPORT_STARTED


def fingerprint() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    paths = ('uv.lock', 'pyproject.toml', 'server/worker.py', 'dnd/player/session.py',
        'dnd/player/capture.py', 'dnd/player/application.py', 'dnd/player/facts.py',
        'dnd/player/projection.py', 'dnd/player/reduction.py', 'dnd/core/events.py',
        'dnd/core/action_types.py', 'dnd/core/base_actions.py')
    return {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
        'source': str(root), 'cwd': os.getcwd(), 'filesystem': 'Windows-mounted source under /mnt/c; fresh process does not imply cold disk',
        'sha256': {path: sha256((root / path).read_bytes()).hexdigest() for path in paths}}


ENVIRONMENT = fingerprint()


def summary(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    result = {'samples': len(values), 'minimum_ms': min(values), 'median_ms': statistics.median(values),
        'maximum_ms': max(values), 'mean_ms': statistics.fmean(values)}
    if len(values) >= 100:
        result.update(p95_ms=ordered[(95 * len(values) + 99) // 100 - 1],
            p99_ms=ordered[(99 * len(values) + 99) // 100 - 1])
    return result


def resident_bytes() -> int:
    return int(Path('/proc/self/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')


def encode(records, response=None, reply=None) -> tuple[int, float]:
    started = perf_counter()
    size = sum(len(record.model_dump_json().encode()) for record in records)
    if response is not None:
        size += len(response.model_dump_json().encode())
    if reply is not None:
        size += len(reply.model_dump_json().encode())
    return size, (perf_counter() - started) * 1000


def request(runtime: Runtime, command) -> tuple[Any, dict[str, Any]]:
    before = EventQueue.event_cursor()
    phases: dict[str, list[float]] = {}
    token = set_action_timing_recorder(lambda phase, start: phases.setdefault(phase, []).append((perf_counter() - start) * 1000))
    started = perf_counter()
    try:
        reply, records, response = dispatch(runtime, command)
    finally:
        reset_action_timing_recorder(token)
    elapsed = (perf_counter() - started) * 1000
    size, encoded = encode(records, response, reply)
    return response, {'kind': command.kind, 'history_before': before, 'history_after': EventQueue.event_cursor(),
        'new_events': EventQueue.event_cursor() - before,
        'public_roots': sum(len(record.lineages) for record in records),
        'public_records': len(records), 'bytes': size, 'dispatch_ms': elapsed, 'encode_ms': encoded,
        'total_execution_ms': elapsed + encoded, 'action_phases_ms': phases}


def create(mode: str, output: Path) -> tuple[Runtime, dict[str, Any]]:
    config = configuration(mode, output)
    value = Start(game_id='performance', game_epoch=uuid4(),
        audience_ids={seat.seat_id: uuid4() for seat in config.assignments}, encounter_id=None,
        recipe=config.recipe, assignments=config.assignments, test_seed=2)
    started = perf_counter()
    runtime, reply, records = start(value)
    native_start = (perf_counter() - started) * 1000
    size, encoded = encode(records, reply=reply)
    advances = []
    while needs_advance(runtime.session):
        _, row = request(runtime, Advance())
        advances.append(row)
    return runtime, {'import_ms': IMPORT_SECONDS * 1000, 'native_start_capture_ms': native_start,
        'initialization_encode_ms': encoded, 'initialization_bytes': size,
        'to_first_input_advances': advances, 'history_at_first_input': EventQueue.event_cursor(),
        'seats': len(runtime.audiences), 'actors': len(runtime.session.game.entities)}


def owner(runtime: Runtime) -> tuple[str, Any]:
    for seat, publication in runtime.publications.items():
        if publication.boundary.input_actor_uuid is not None:
            return seat, publication
    raise RuntimeError('No external native input boundary')


def discover(runtime: Runtime) -> tuple[Any, dict[str, Any]]:
    return request(runtime, choices_request(runtime))


def choices_request(runtime: Runtime):
    seat, publication = owner(runtime)
    return Choices(seat_id=seat, request=ChoicesRequest(actor_uuid=publication.boundary.input_actor_uuid,
        state_revision=publication.state_revision, force_attack=False, correlation_id=uuid4()))


def movement(runtime: Runtime, choices):
    seat, publication = owner(runtime)
    for row in choices.choices.position_actions:
        if row.behavior_id != 'action.move' or not row.can_afford or not row.valid_targets:
            continue
        # Fixture workload takes a legal offered neighbouring endpoint; the
        # retained native selection and preview decide affordability/legality.
        actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        home_x = 6 if actor.faction == 'amber' else 9
        away_x = 5 if actor.faction == 'amber' else 10
        home_y = 6 if actor.name.endswith('1') else 8
        targets = [target for target in row.valid_targets if target.position in ((home_x, home_y), (away_x, home_y))]
        if not targets:
            continue
        target = min(targets, key=lambda target: (target.distance or 0, target.index))
        selection = ActionSelection(action_index=row.discovery_index, target_indices=(target.index,), extra_target_positions=())
        return seat, publication, row, selection
    return None


def preview_request(runtime: Runtime, choices):
    selected = movement(runtime, choices)
    if selected is None:
        raise RuntimeError('No movement offered for preview sample')
    seat, publication, row, selection = selected
    return Preview(seat_id=seat, request=PreviewRequest(actor_uuid=publication.boundary.input_actor_uuid,
        state_revision=publication.state_revision, discovery_generation=choices.choices.discovery_generation,
        correlation_id=uuid4(), selection=selection))


def end_turn(runtime: Runtime, number: int):
    seat, publication = owner(runtime)
    return Command(seat_id=seat, request=CommandRequest(command_number=number,
        actor_uuid=publication.boundary.input_actor_uuid, state_revision=publication.state_revision,
        intent=EndTurnIntent()))


def step(runtime: Runtime, number: int, *, move: bool) -> list[dict[str, Any]]:
    if needs_advance(runtime.session):
        return [request(runtime, Advance())[1]]
    if move:
        choices, discovered = discover(runtime)
        if movement(runtime, choices) is None:
            return [discovered, request(runtime, end_turn(runtime, number))[1]]
        query = preview_request(runtime, choices)
        preview, inspected = request(runtime, query)
        if preview.preview.can_confirm:
            command = Command(seat_id=query.seat_id, request=CommandRequest(command_number=number,
                actor_uuid=query.request.actor_uuid, state_revision=query.request.state_revision,
                intent=ExecuteSelectionIntent(discovery_generation=query.request.discovery_generation,
                    selection=query.request.selection)))
            return [discovered, inspected, request(runtime, command)[1]]
    return [request(runtime, end_turn(runtime, number))[1]]


def throughput(args) -> dict[str, Any]:
    runtime, startup = create(args.configuration, args.output)
    rows = []
    collections = []
    collection_started = {}
    def record_gc(phase, info):
        generation = info['generation']
        if phase == 'start':
            collection_started[generation] = perf_counter()
        else:
            collections.append({'generation': generation,
                'elapsed_ms': (perf_counter() - collection_started.pop(generation)) * 1000,
                'collected': info['collected'], 'uncollectable': info['uncollectable'],
                'native_history': EventQueue.event_cursor()})
    gc.callbacks.append(record_gc)
    started = perf_counter()
    try:
        for number in range(1, args.samples + 1):
            if all(publication.boundary.lifecycle == 'terminal' for publication in runtime.publications.values()):
                break
            rows.extend(step(runtime, number, move=True))
        by_kind = {kind: summary([row['total_execution_ms'] for row in rows if row['kind'] == kind])
            for kind in sorted({row['kind'] for row in rows})}
        return {'kind': 'throughput', 'configuration': args.configuration, 'startup': startup,
            'elapsed_seconds': perf_counter() - started, 'requested_iterations': args.samples,
            'native_operations': sum(row['new_events'] > 0 for row in rows),
            'final_history': EventQueue.event_cursor(), 'execution_and_encode_by_kind': by_kind,
            'rows': rows, 'collections': collections, 'rss_current_bytes': resident_bytes(),
            'environment': ENVIRONMENT}
    finally:
        gc.callbacks.remove(record_gc)
        close_session(runtime.session)


def paths(args) -> dict[str, Any]:
    runtime, startup = create(args.configuration, args.output)
    _, publication = owner(runtime)
    actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    before = EventQueue.event_cursor()
    rows = []
    try:
        for _ in range(args.samples + 1):
            phases: dict[str, list[float]] = {}
            token = set_action_timing_recorder(lambda phase, start: phases.setdefault(phase, []).append((perf_counter() - start) * 1000))
            started = perf_counter()
            try:
                actor.materialize_navigation(path_max_distance=11)
            finally:
                reset_action_timing_recorder(token)
            rows.append({'total_ms': (perf_counter() - started) * 1000, 'phases_ms': phases,
                'admitted_paths': len(actor.senses.paths), 'safe_paths': len(actor.senses.safe_paths)})
        profiler = cProfile.Profile()
        profiler.runcall(actor.materialize_navigation, path_max_distance=11)
        profiler.dump_stats(str(args.output / 'navigation-warm.pstats'))
        assert EventQueue.event_cursor() == before, 'Derived navigation unexpectedly changed native history'
        assert all(row['admitted_paths'] == rows[0]['admitted_paths'] for row in rows), 'Stable native query changed paths'
        return {'kind': 'paths', 'configuration': args.configuration, 'startup': startup,
            'query': {'path_max_distance': 11, 'map': runtime.session.battlefield.definition.battlefield_id,
                'actors': len(runtime.session.game.entities)},
            'cold': rows[0], 'warm': summary([row['total_ms'] for row in rows[1:]]), 'rows': rows,
            'history_unchanged': True, 'environment': ENVIRONMENT}
    finally:
        close_session(runtime.session)


def retention(args) -> dict[str, Any]:
    runtime, startup = create(args.configuration, args.output)
    rows = []
    samples = []
    started = perf_counter()
    iterations = 0
    journal = args.output / 'retention-progress.ndjson'
    try:
        with journal.open('w') as log:
            while perf_counter() - started < args.duration or iterations < 100:
                before = perf_counter()
                measured = step(runtime, iterations + 1, move=iterations % 5 == 0)
                rows.extend(measured)
                iterations += 1
                sample = {'elapsed_seconds': perf_counter() - started, 'iteration': iterations,
                    'history': EventQueue.event_cursor(), 'rss_high_water_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                    'rss_current_bytes': resident_bytes(),
                    'actor_count': len(runtime.session.game.entities),
                    'audience_actor_counts': {seat: len(view.latest.actors) for seat, view in runtime.audiences.items()},
                    'audience_occurrences': {seat: view.latest.reducer_cursor for seat, view in runtime.audiences.items()},
                    'rows': measured}
                samples.append(sample)
                log.write(json.dumps(sample) + '\n'); log.flush()
                wait = args.interval - (perf_counter() - before)
                if wait > 0 and perf_counter() - started < args.duration:
                    time.sleep(wait)
        return {'kind': 'retention', 'configuration': args.configuration, 'startup': startup,
            'elapsed_seconds': perf_counter() - started, 'native_iterations': iterations,
            'latency_excludes_pacing': True, 'samples': samples,
            'dispatch': summary([row['dispatch_ms'] for row in rows]),
            'encode': summary([row['encode_ms'] for row in rows]), 'environment': ENVIRONMENT}
    finally:
        close_session(runtime.session)


def profile(runtime: Runtime, command, destination: Path) -> dict[str, Any]:
    profiler = cProfile.Profile()
    profiler.enable()
    _, measured = request(runtime, command)
    profiler.disable()
    profiler.dump_stats(str(destination))
    stats = pstats.Stats(profiler)
    owners = []
    for (filename, line, function), (primitive, total, self_time, cumulative, callers) in stats.stats.items():
        if '/dnd_engine/' in filename:
            owners.append({'file': filename, 'line': line, 'function': function, 'calls': total,
                'self_ms': self_time * 1000, 'inclusive_ms': cumulative * 1000,
                'callers': [{'file': key[0], 'line': key[1], 'function': key[2]} for key in callers]})
    return {'measurement': measured, 'profile': str(destination),
        'top_inclusive': sorted(owners, key=lambda row: row['inclusive_ms'], reverse=True)[:35],
        'top_self': sorted(owners, key=lambda row: row['self_ms'], reverse=True)[:25]}


def history(args) -> dict[str, Any]:
    runtime, startup = create(args.configuration, args.output)
    tiers = []
    number = 0
    try:
        for target in args.histories:
            while EventQueue.event_cursor() < target or needs_advance(runtime.session):
                number += 1
                step(runtime, number, move=False)
            before = EventQueue.event_cursor()
            cold_discovery = profile(runtime, choices_request(runtime), args.output / f'discovery-cold-{target}.pstats')
            discovery = []
            for _ in range(args.samples):
                choices, row = discover(runtime)
                discovery.append(row)
            query = preview_request(runtime, choices)
            cold_preview = profile(runtime, query, args.output / f'preview-cold-{target}.pstats')
            previews = [request(runtime, query)[1] for _ in range(args.samples)]
            warm_discovery = profile(runtime, choices_request(runtime), args.output / f'discovery-warm-{target}.pstats')
            warm_preview = profile(runtime, query, args.output / f'preview-warm-{target}.pstats')
            measured = profile(runtime, end_turn(runtime, number + 1), args.output / f'history-{target}.pstats')
            index = EventQueue._event_indexes_by_uuid
            integers = {id(value): value for value in index.values()}
            index_cost = {'entries': len(index), 'dict_shallow_bytes': sys.getsizeof(index),
                'unique_integer_values': len(integers),
                'integer_value_bytes': sum(sys.getsizeof(value) for value in integers.values()),
                'uuid_objects_shared_with_existing_indexes': True}
            tiers.append({'target_history': target, 'actual_history': before, 'queries': args.samples,
                'discovery_dispatch': summary([row['dispatch_ms'] for row in discovery]),
                'discovery_encode': summary([row['encode_ms'] for row in discovery]),
                'preview_dispatch': summary([row['dispatch_ms'] for row in previews]),
                'preview_encode': summary([row['encode_ms'] for row in previews]), 'profiled_end_turn': measured,
                'native_uuid_index': index_cost, 'cold_discovery_profile': cold_discovery,
                'cold_preview_profile': cold_preview, 'warm_discovery_profile': warm_discovery,
                'warm_preview_profile': warm_preview})
            print(json.dumps({'target_history': target, 'actual_history': before,
                'discovery_mean_ms': tiers[-1]['discovery_dispatch']['mean_ms'],
                'preview_mean_ms': tiers[-1]['preview_dispatch']['mean_ms']}), flush=True)
        return {'kind': 'history', 'configuration': args.configuration, 'startup': startup,
            'tiers': tiers, 'environment': ENVIRONMENT}
    finally:
        close_session(runtime.session)


def startup(args) -> dict[str, Any]:
    runtime, measured = create(args.configuration, args.output)
    close_session(runtime.session)
    return {'kind': 'startup', 'configuration': args.configuration, **measured, 'environment': ENVIRONMENT}


def startups(args) -> dict[str, Any]:
    rows = []
    for index in range(10):
        destination = args.output / f'process-{index:02}'
        started = perf_counter()
        completed = subprocess.run([sys.executable, '-m', 'devtools.player_server_acceptance.performance',
            'startup', '--configuration', args.configuration, '--output', str(destination)], capture_output=True, text=True)
        elapsed = (perf_counter() - started) * 1000
        (args.output / f'process-{index:02}.log').write_text(completed.stdout + completed.stderr)
        completed.check_returncode()
        row = json.loads((destination / 'result.json').read_text())
        row['fresh_process_wall_ms'] = elapsed
        rows.append(row)
        print(json.dumps({'fresh_process': index, 'wall_ms': elapsed}), flush=True)
    return {'kind': 'startups', 'configuration': args.configuration, 'fresh_processes': 10,
        'wall': summary([row['fresh_process_wall_ms'] for row in rows]),
        'imports': summary([row['import_ms'] for row in rows]),
        'native_start_capture': summary([row['native_start_capture_ms'] for row in rows]),
        'initialization_encode': summary([row['initialization_encode_ms'] for row in rows]),
        'runs': rows, 'environment': ENVIRONMENT}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('retention', 'history', 'startup', 'startups', 'throughput', 'paths'))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--configuration', default='two_sides', choices=('two_sides', 'per_entity', 'mixed'))
    parser.add_argument('--duration', type=float, default=900)
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--histories', nargs='+', type=int, default=[100, 1000, 10000])
    parser.add_argument('--samples', type=int, default=100)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = {'retention': retention, 'history': history, 'startup': startup, 'startups': startups,
        'throughput': throughput, 'paths': paths}[args.mode](args)
    (args.output / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({'kind': args.mode, 'result': str(args.output / 'result.json')}), flush=True)


if __name__ == '__main__':
    main()
