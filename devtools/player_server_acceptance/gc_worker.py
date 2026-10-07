"""Private measurement wrapper around the exact production worker loop."""
import argparse
from collections import Counter
import gc
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter
import weakref

from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.values import BaseValue
from player_server import worker


def rss_bytes():
    path = Path('/proc/self/status')
    if not path.exists():
        return None
    for line in path.read_text().splitlines():
        if line.startswith('VmRSS:'):
            return int(line.split()[1]) * 1024
    return None


def tracked_graph():
    objects = gc.get_objects()
    counts, sizes = Counter(), Counter()
    for value in objects:
        kind = type(value).__module__ + '.' + type(value).__name__
        counts[kind] += 1
        sizes[kind] += sys.getsizeof(value)
    del value, objects
    return {'tracked_by_type': dict(counts), 'tracked_shallow_bytes_by_type': dict(sizes)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--census-after-commands', type=int, default=200)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    source_sha256 = {path: sha256((root / path).read_bytes()).hexdigest() for path in (
        'dnd/player/content_composition.py', 'dnd/player/reduction.py', 'dnd/player/capture.py',
        'dnd/player/application.py', 'dnd/entity.py', 'dnd/core/values.py',
        'dnd/blocks/health.py', 'dnd/blocks/abilities.py', 'dnd/blocks/equipment.py',
        'dnd/player/projection.py', 'dnd/controller.py', 'dnd/encounter.py',
        'dnd/core/base_object.py', 'dnd/core/gridmap.py', 'dnd/blocks/sensory.py',
        'player_server/protocol.py', 'player_server/worker.py', 'uv.lock')}
    original_start, original_dispatch = worker.start, worker.dispatch
    original_main, original_identity = worker.main, worker.protocol_identity
    original_freeze, original_collect = gc.freeze, gc.collect
    policy = {'gc_enabled_before': gc.isenabled(), 'threshold_before': gc.get_threshold()}
    current = {'kind': 'imports'}
    rows, collections, censuses = [], [], []
    gc_started = {}
    command_count = 0
    inside_census = False

    def record_gc(phase, info):
        generation = info['generation']
        if phase == 'start':
            gc_started[generation] = perf_counter()
        else:
            collections.append({'generation': generation, 'elapsed_ms': (perf_counter() - gc_started.pop(generation)) * 1000,
                'collected': info['collected'], 'uncollectable': info['uncollectable'],
                'current_request': dict(current), 'history': EventQueue.event_cursor(), 'inside_census': inside_census})

    def census(runtime, name):
        nonlocal inside_census
        inside_census = True
        started = perf_counter()
        graph = tracked_graph()
        censuses.append({'name': name, 'history': EventQueue.event_cursor(), 'allocated_blocks': sys.getallocatedblocks(),
            'gc_count': gc.get_count(), **graph, 'frozen_objects': gc.get_freeze_count(), 'rss_bytes': rss_bytes(),
            'registered_values': len(BaseValue._registry),
            'registered_values_by_type': dict(Counter(type(value).__name__ for value in BaseValue._registry.values())),
            'registered_values_by_name': dict(Counter(value.name for value in BaseValue._registry.values())),
            'registered_objects': len(BaseObject._registry),
            'registered_objects_by_type': dict(Counter(type(value).__name__ for value in BaseObject._registry.values())),
            'catalog_descriptors': len(runtime.catalog.content),
            'audience_content_counts': {seat: len(view.latest.content) for seat, view in runtime.audiences.items()},
            'census_ms': (perf_counter() - started) * 1000})
        inside_census = False

    def measured_start(request):
        current.update(kind='start')
        result = original_start(request)
        current.update(kind='post_start_cycle_probe')
        cycle = set()
        cycle.add(cycle.add)
        reference = weakref.ref(cycle)
        del cycle
        collected = gc.collect(0)
        policy['post_start_cycle_probe'] = {'collected': collected, 'cycle_reclaimed': reference() is None,
            'gc_enabled': gc.isenabled(), 'threshold': gc.get_threshold(),
            'scope': 'Instrumentation-only generation-0 cycle proof after Start; no GC threshold or enabled-state change.'}
        assert reference() is None and gc.isenabled()
        current.update(kind='start')
        census(result[0], 'after_start')
        args.output.with_suffix('.ready').touch()
        return result

    def measured_dispatch(runtime, request):
        nonlocal command_count
        current.clear()
        current.update(kind=request.kind, history_before=EventQueue.event_cursor(),
            public_sequence=max(view.cursor.sequence for view in runtime.publications.values()))
        if request.kind == 'command':
            current.update(command_number=request.request.command_number, seat=request.seat_id)
        before = sys.getallocatedblocks()
        started = perf_counter()
        result = original_dispatch(runtime, request)
        rows.append({**current, 'elapsed_ms': (perf_counter() - started) * 1000,
            'allocated_block_delta': sys.getallocatedblocks() - before, 'history_after': EventQueue.event_cursor(),
            'gc_count': gc.get_count()})
        if request.kind == 'command':
            command_count += 1
            if command_count == args.census_after_commands:
                census(runtime, f'after_{command_count}_commands')
        return result

    def measured_identity():
        started = perf_counter()
        result = original_identity()
        policy['protocol_warm_ms'] = (perf_counter() - started) * 1000
        return result

    def measured_collect():
        started = perf_counter()
        result = original_collect()
        policy['pre_start_collection_ms'] = (perf_counter() - started) * 1000
        return result

    def measured_freeze():
        nonlocal inside_census
        inside_census = True
        started = perf_counter()
        policy['before_freeze_graph'] = tracked_graph()
        policy['before_freeze_rss_bytes'] = rss_bytes()
        policy['before_freeze_native_event_cursor'] = EventQueue.event_cursor()
        policy['before_freeze_registered_objects'] = len(BaseObject._registry)
        policy['before_freeze_registered_values'] = len(BaseValue._registry)
        policy['pre_freeze_census_ms'] = (perf_counter() - started) * 1000
        inside_census = False
        started = perf_counter()
        original_freeze()
        policy['freeze_ms'] = (perf_counter() - started) * 1000
        policy['frozen_objects'] = gc.get_freeze_count()

    def measured_main():
        policy['entry_prelude_instrumented_ms'] = (perf_counter() - entry_started) * 1000
        worker.protocol_identity = original_identity
        gc.collect, gc.freeze = original_collect, original_freeze
        original_main()

    gc.callbacks.append(record_gc)
    worker.start, worker.dispatch = measured_start, measured_dispatch
    worker.main, worker.protocol_identity = measured_main, measured_identity
    gc.collect, gc.freeze = measured_collect, measured_freeze
    entry_started = perf_counter()
    try:
        worker.run_process()
    finally:
        gc.callbacks.remove(record_gc)
        worker.start, worker.dispatch = original_start, original_dispatch
        worker.main, worker.protocol_identity = original_main, original_identity
        gc.collect, gc.freeze = original_collect, original_freeze
        policy.update(gc_enabled_after=gc.isenabled(), threshold_after=gc.get_threshold(),
            frozen_objects_after=gc.get_freeze_count(), rss_bytes_after=rss_bytes())
        args.output.write_text(json.dumps({'scope': 'Instrumentation-only HTTP cohort; censuses and cycle proof add latency and are not benchmark samples. Calls exact production run_process policy.',
            'censuses': censuses, 'collections': collections, 'requests': rows,
            'source_sha256': source_sha256, 'process_policy': policy}, indent=2))


if __name__ == '__main__':
    main()
