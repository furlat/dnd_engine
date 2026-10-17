"""Perception-arrays spike on the Gallery Crowd: after every measured op, every published
observer's array recompute is compared with its settled Senses, and timed against a
full `recompute_observer` on the same state.

Usage: run_spike.py <worktree> --case <case> --mode ordinary --name <stem>
Rows go to <worktree>/.runtime/perception_arrays_spike/<stem>.jsonl; a summary to stderr.
"""

import cProfile
import importlib.util
import json
import os
import pstats
import statistics
import sys
from pathlib import Path
from time import perf_counter

from dnd.action_timing import reset_action_timing_recorder, set_action_timing_recorder
from dnd.blocks.sensory import capture_senses_snapshot, spatial_senses_system
from dnd.core.base_block import BaseBlock
from dnd.core.geometry import supercover_line_relative
from dnd.core.gridmap import get_map

from devtools.perception_arrays_spike.frame_routes import FRAME_RADIUS, SIDE, frame_route_table
from devtools.perception_arrays_spike.observer_arrays import array_recompute, materialize, new_caches, surface_rays
from devtools.perception_arrays_spike.world_arrays import build_world_arrays

SRC = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location('gallery_crowd', SRC / 'devtools' / 'performance' / 'gallery_crowd.py')
gallery = importlib.util.module_from_spec(spec)
sys.modules['gallery_crowd'] = gallery
spec.loader.exec_module(gallery)

FIELDS = ('visible', 'entities', 'objects', 'hazardous_cells', 'effective_light_levels')
NAME = sys.argv[sys.argv.index('--name') + 1]
OUT = SRC / '.runtime' / 'perception_arrays_spike' / f'{NAME}.jsonl'
OUT.parent.mkdir(parents=True, exist_ok=True)
state = {'kind': None, 'op': 0, 'rows': [], 'mismatches': {}, 'examples': {}, 'surface_checks': 0, 'checks': 0}
caches = new_caches()
profiler = cProfile.Profile() if os.environ.get('SPIKE_PROFILE') else None


def verify_route_table():
    """The spike's radius-80 table walks exactly the engine's supercover lines."""
    cells, lengths = frame_route_table()
    for row in range(0, cells.shape[0], 7):
        dx, dy = row // SIDE - FRAME_RADIUS, row % SIDE - FRAME_RADIUS
        expected = [(x + FRAME_RADIUS) * SIDE + y + FRAME_RADIUS for x, y in supercover_line_relative(dx, dy)]
        assert cells[row, :lengths[row]].tolist() == expected, (dx, dy)


verify_route_table()


def settled_fields(senses):
    snapshot = capture_senses_snapshot(senses)
    return {'visible': snapshot.visible, 'entities': snapshot.entities, 'objects': snapshot.objects,
            'hazardous_cells': snapshot.hazardous_cells, 'effective_light_levels': snapshot.effective_light_levels}


def field_entrances(senses):
    """(light position, ordinary, special) of every settled first-surface entrance; rays carry no own position."""
    field = senses._field
    if field is None:
        return None
    return {(ray.light_position, ray.ordinary, ray.special)
            for volume in field.volume_fields.values() for ray in volume.entrances}


def diff(key, expected, got):
    if key == 'visible':
        return {'settled_only': sorted(expected - got)[:6], 'array_only': sorted(got - expected)[:6],
                'counts': (len(expected), len(got))}
    keys = set(expected) | set(got)
    return {str(k): (str(expected.get(k)), str(got.get(k))) for k in sorted(keys, key=str)
            if expected.get(k) != got.get(k)}


def note(kind, observer, detail):
    state['mismatches'][kind] = state['mismatches'].get(kind, 0) + 1
    examples = state['examples'].setdefault(kind, [])
    if len(examples) < 3:
        examples.append({'op': state['kind'], 'observer': observer, 'diff': str(detail)[:600]})


def check_operation():
    system = spatial_senses_system
    grid = get_map()
    started = perf_counter()
    world = build_world_arrays(grid, perf_counter)
    world_ms = (perf_counter() - started) * 1000
    op = {'op': state['op'], 'kind': state['kind'], 'world_ms': world_ms, 'world_phases_ms': world.timings_ms,
          'observers': []}
    for uuid, senses in sorted(system.senses_by_observer.items(), key=lambda row: str(row[0])):
        owner = BaseBlock.get(uuid)
        if owner is None or uuid not in system.published_observers:
            continue
        name = owner.name
        settled = settled_fields(senses)
        settled_surfaces = field_entrances(senses)
        t0 = perf_counter()
        first = array_recompute(world, caches, grid, uuid, owner, senses)
        t1 = perf_counter()
        if profiler is not None:
            profiler.enable()
        view = array_recompute(world, caches, grid, uuid, owner, senses)
        if profiler is not None:
            profiler.disable()
        t2 = perf_counter()
        got = materialize(view)
        t3 = perf_counter()
        for key in FIELDS:
            if settled[key] != got[key]:
                note(key, name, diff(key, settled[key], got[key]))
        state['checks'] += 1
        if settled_surfaces:
            state['surface_checks'] += 1
            arrays = {(light, ordinary, special) for _, light, ordinary, special in surface_rays(view)}
            if not settled_surfaces <= arrays:
                note('surface_entrances', name, {'settled_only': sorted(settled_surfaces - arrays)[:6]})
        t4 = perf_counter()
        system.recompute_observer(uuid)
        t5 = perf_counter()
        phases = {}
        token = set_action_timing_recorder(
            lambda phase, started: phases.__setitem__(phase, phases.get(phase, 0.0) + (perf_counter() - started) * 1000))
        try:
            system.recompute_observer(uuid)
        finally:
            reset_action_timing_recorder(token)
        cold = settled_fields(senses)
        for key in FIELDS:
            if settled[key] != cold[key]:
                note(f'oracle_{key}', name, diff(key, settled[key], cold[key]))
        op['observers'].append({
            'observer': name, 'visible': len(got['visible']), 'entities': len(got['entities']),
            'objects': len(got['objects']), 'surfaces': int(view.surface_rows.size),
            'array_first_ms': (t1 - t0) * 1000, 'array_ms': (t2 - t1) * 1000, 'materialize_ms': (t3 - t2) * 1000,
            'array_phases_us': {k: v / 1000 for k, v in view.phases_ns.items()}, 'fov_cache_hit_first': first.fov_cache_hit,
            'counts': view.counts,
            'old_ms': (t5 - t4) * 1000,
            'old_phases_ms': {k.removeprefix('sensory.recompute.'): v for k, v in phases.items()
                              if k.startswith('sensory.recompute.')}})
    op['targets_memoized'] = len(world.targets)
    op['sides_memoized'] = len(world.side_channels)
    state['rows'].append(op)
    with OUT.open('a') as handle:
        handle.write(json.dumps(op) + '\n')
    if op['observers']:
        old = [row['old_ms'] for row in op['observers']]
        new = [row['array_ms'] for row in op['observers']]
        print(f"SPIKE op {state['op']} {state['kind']}: observers={len(old)} world={world_ms:.2f}ms "
              f"array sum={sum(new):.2f}ms med={statistics.median(new):.3f} | old sum={sum(old):.1f}ms "
              f"med={statistics.median(old):.2f} | mismatches so far {state['mismatches']}", file=sys.stderr)


original_operation, original_request, original_run = (gallery.measured_operation, gallery.measured_request,
                                                      gallery.Measurement.run)


def measured_operation(runtime, mode, kind, *args, **kwargs):
    state['kind'] = kind
    return original_operation(runtime, mode, kind, *args, **kwargs)


def measured_request(mode, kind, request):
    state['kind'] = kind
    return original_request(mode, kind, request)


def run(self, operation):
    try:
        return original_run(self, operation)
    finally:
        state['op'] += 1
        check_operation()


gallery.measured_operation = measured_operation
gallery.measured_request = measured_request
gallery.Measurement.run = run
try:
    gallery.entry()
finally:
    print(f"SPIKE checks: {state['checks']} observer states, {state['surface_checks']} with settled volume "
          f"entrances; mismatches: {json.dumps(state['mismatches'])}", file=sys.stderr)
    for kind, examples in state['examples'].items():
        for example in examples:
            print(f"SPIKE example {kind}: {json.dumps(example)}", file=sys.stderr)
    print(f"SPIKE rows: {OUT}", file=sys.stderr)
    if profiler is not None:
        pstats.Stats(profiler, stream=sys.stderr).sort_stats('tottime').print_stats(25)
