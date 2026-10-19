"""Temporary, opt-in movement diagnostics around the unchanged native worker.

Run only through gallery --diagnostic-commands. No payloads are logged. Profiles
include dispatch AND outgoing serialization/framing; ordinary gallery runs never
load this module. Remove this temporary module at the plan's cleanup checkpoint.
"""
import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager
import cProfile
import gc
import json
from dnd.core.cells import mask_count
from pathlib import Path
import pstats
from time import perf_counter, perf_counter_ns, process_time_ns
from unittest.mock import patch

from pydantic import BaseModel, TypeAdapter

from dnd.action_timing import (reset_action_count_recorder, reset_action_timing_recorder,
    set_action_count_recorder, set_action_timing_recorder)
from dnd.blocks import sensory
from dnd.core.events import BaseHandler, EventHandler, EventQueue, SpatialHandler, Trigger
from dnd.core.gridmap import GridMap
from dnd.entity import Entity
from dnd.player import application, audience, projection, reduction
from server import worker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic-commands', required=True)
    parser.add_argument('--coarse-timing', action='store_true')
    args = parser.parse_args()
    selected = {int(value) for value in args.diagnostic_commands.split(',') if value}
    current = None
    profile = None
    action_token = None
    count_token = None
    stack = []
    coverage = []
    span_limit = 120_000

    def increment(key, amount=1):
        if current is not None:
            current['counters'][key] += amount

    @contextmanager
    def span(label, identity=None):
        if current is None:
            yield
            return
        started = perf_counter_ns()
        row = {'name': label, 'start_ns': started, 'children_ns': 0,
            'parent': stack[-1]['name'] if stack else None}
        if identity is not None:
            row.update(identity)
        stack.append(row)
        try:
            yield
        finally:
            ended = perf_counter_ns()
            stack.pop()
            duration = ended-started
            if stack:
                stack[-1]['children_ns'] += duration
            key = (row['parent'], label)
            total = current['spans'].setdefault(key, {'calls': 0, 'inclusive_ns': 0,
                'exclusive_wrapped_ns': 0, 'max_ns': 0})
            total['calls'] += 1
            total['inclusive_ns'] += duration
            total['exclusive_wrapped_ns'] += duration-row['children_ns']
            total['max_ns'] = max(total['max_ns'], duration)
            if len(current['trace']) < span_limit:
                row['end_ns'] = ended
                current['trace'].append(row)
            else:
                current['trace_dropped'] += 1

    def measured(label, original, count=None):
        coverage.append(label)
        def call(*arguments, **keywords):
            if current is None:
                return original(*arguments, **keywords)
            if count is not None:
                count(*arguments, **keywords)
            with span(label):
                return original(*arguments, **keywords)
        return call

    def action_phase(label, started):
        if current is None:
            return
        ended = perf_counter()
        row = current['action_phases'].setdefault(label, {'calls': 0, 'inclusive_ms': 0.0})
        row['calls'] += 1
        row['inclusive_ms'] += (ended-started)*1000
        row['max_ms'] = max(row.get('max_ms', 0.0), (ended-started)*1000)
        if len(current['trace']) < span_limit:
            current['trace'].append({'name': label, 'start_ns': int(started*1e9),
                'end_ns': int(ended*1e9), 'kind': 'existing_action_hook',
                'parent': stack[-1]['name'] if stack else None})
        else:
            current['trace_dropped'] += 1

    gc_start = 0
    def gc_callback(phase, info):
        nonlocal gc_start
        if current is None:
            return
        if phase == 'start':
            gc_start = perf_counter_ns()
        elif gc_start:
            increment('gc.pause_ns', perf_counter_ns()-gc_start)
            increment('gc.collections')
            increment('gc.collected', info['collected'])
            increment('gc.generation_'+str(info['generation'])+'.collections')
            increment('gc.generation_'+str(info['generation'])+'.pause_ns', perf_counter_ns()-gc_start)
            if len(current['trace']) < span_limit:
                current['trace'].append({'name': 'gc.generation_'+str(info['generation']),
                    'start_ns': gc_start, 'end_ns': perf_counter_ns(), 'kind': 'gc',
                    'parent': stack[-1]['name'] if stack else None})
            else:
                current['trace_dropped'] += 1
            gc_start = 0

    def snapshot_count(snapshot):
        if snapshot is not None:
            for label, value in (('seen', mask_count(snapshot.seen)), ('visible', mask_count(snapshot.visible)),
                    ('entities', len(snapshot.entities)), ('objects', len(snapshot.objects)),
                    ('light', mask_count(snapshot.effective_light_levels.cells)),
                    ('hazards', mask_count(snapshot.hazardous_cells.cells)), ('effects', len(snapshot.spatial_effects))):
                increment('snapshot.input_entries.'+label, value)

    def target_count(target):
        increment('target_copy.tiles', len(target.tiles))
        increment('target_copy.objects', len(target.objects))
        increment('target_copy.actors', len(target.actors))
        snapshot_count(target.senses)

    original_read = worker.read_packet
    original_validate = TypeAdapter.validate_json
    original_dispatch = worker.dispatch
    original_write = worker.write_packet

    def finish():
        nonlocal current, profile, action_token, count_token
        if current is None:
            return
        ended = perf_counter_ns()
        cpu_ended = process_time_ns()
        if profile is not None:
            profile.disable()
            reset_action_timing_recorder(action_token)
            reset_action_count_recorder(count_token)
        data = current
        current = None
        data['end_ns'] = ended
        data['elapsed_ms'] = (ended-data['start_ns'])/1e6
        data['cpu_ms'] = (cpu_ended-data.pop('cpu_start_ns'))/1e6
        data['event_cursor_after'] = EventQueue.event_cursor()
        data['diagnostic'] = True
        data['mode'] = 'coarse' if args.coarse_timing else 'full'
        data['cprofile'] = profile is not None
        data['scope'] = ('Dispatch entry through response/public-record encoding and writes; excludes request decode. '
            'Only outer owner wall spans and GC; no cProfile, action/count recorders, per-cell hooks, model or handler wrappers. '
            if args.coarse_timing else 'Decoded request through completed dispatch, response/public-record encoding and writes; includes cProfile and fine wrappers. ')
        data['scope'] += 'Ends before next input read. Still instrumented; never a clean speed sample.'
        if not args.coarse_timing:
            data['directional_fov_note'] = 'Temporary timers and scalar counters add diagnostic overhead. One array solve per group of the origins of a batch (a relight, a sensory settlement, or one query; `compact_window_groups`); settled_predicates counts the edge predicates it settled first. There is no retained ray graph or geometry warmup cache.'
        data['exclusive_note'] = ('exclusive_wrapped_ns removes explicit child wrapper spans only; it is not function self time.'
            if args.coarse_timing else 'exclusive_wrapped_ns removes explicit child wrapper spans only; cProfile supplies function self time. Existing action hooks overlap these spans and each other.')
        data['coverage'] = coverage
        if args.coarse_timing:
            data['navigation_timing_owner'] = {
                'label': 'entity.materialize_navigation',
                'method': 'Entity._materialize_navigation_distance',
                'note': 'The existing navigation label measures the shared worker, including exhausted movement. Public and movement wrappers are not separately timed, so their nested calls are counted once.',
            }
        data['spans'] = [dict(parent=key[0], name=key[1], **value)
            for key, value in data['spans'].items()]
        if profile is not None:
            path = args.output / f"command-{data['command_number']}.pstats"
            profile.dump_stats(str(path))
            functions = [{'file': key[0], 'line': key[1], 'function': key[2],
                'calls': value[1], 'self_ms': value[2]*1000, 'inclusive_ms': value[3]*1000}
                for key, value in pstats.Stats(profile).stats.items()]
            data['top_self'] = sorted(functions, key=lambda row: row['self_ms'], reverse=True)[:45]
            data['top_inclusive'] = sorted(functions, key=lambda row: row['inclusive_ms'], reverse=True)[:45]
        trace = data.pop('trace')
        base = args.output / f"command-{data['command_number']}"
        base.with_suffix('.json').write_text(json.dumps(data, indent=2))
        base.with_suffix('.spans.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in trace))
        profile = action_token = count_token = None

    def read(stream):
        finish()
        return original_read(stream)

    def validate(adapter, data, *arguments, **keywords):
        nonlocal current, profile, action_token, count_token
        started = perf_counter_ns()
        result = original_validate(adapter, data, *arguments, **keywords)
        elapsed = perf_counter_ns()-started
        if adapter is worker.REQUEST_CODEC and result.kind == 'command' and result.request.command_number in selected:
            current = {'command_number': result.request.command_number, 'start_ns': perf_counter_ns(),
                'cpu_start_ns': process_time_ns(), 'request_decode_ms': elapsed/1e6,
                'request_bytes': len(data), 'event_cursor_before': EventQueue.event_cursor(),
                'counters': Counter(), 'spans': {}, 'trace': [], 'trace_dropped': 0,
                'action_phases': {}}
            profile = cProfile.Profile()
            action_token = set_action_timing_recorder(action_phase)
            count_token = set_action_count_recorder(increment)
            profile.enable()
        elif current is not None:
            increment('type_adapter.validate_json.calls')
            increment('type_adapter.validate_json.bytes', len(data))
            increment('type_adapter.validate_json.ns', elapsed)
        return result

    def dispatch(runtime, request):
        nonlocal current
        if args.coarse_timing and request.kind == 'command' and request.request.command_number in selected:
            current = {'command_number': request.request.command_number, 'start_ns': perf_counter_ns(),
                'cpu_start_ns': process_time_ns(), 'request_decode_ms': None, 'request_bytes': None,
                'event_cursor_before': EventQueue.event_cursor(), 'counters': Counter(), 'spans': {},
                'trace': [], 'trace_dropped': 0, 'action_phases': {}}
        with span('worker.dispatch'):
            result = original_dispatch(runtime, request)
        if current is not None:
            current['result_cursors'] = [publication.cursor.model_dump(mode='json')
                for publication in result[0].publications]
            increment('worker.publication_count', len(result[1]))
        return result

    def write(stream, payload):
        increment('worker.frames')
        increment('worker.frame_bytes', len(payload))
        with span('worker.write_packet'):
            return original_write(stream, payload)

    original_handler = EventQueue._invoke_handler
    def invoke(cls, handler, event):
        if current is None:
            return original_handler(handler, event)
        with span('handler.'+handler.get_semantic_key()+'.'+handler.name,
                {'event_uuid': str(event.uuid), 'lineage_uuid': str(event.lineage_uuid),
                 'event_type': event.event_type.value, 'event_phase': event.phase.value,
                 'handler_uuid': str(handler.uuid)}):
            before = EventQueue.event_cursor()
            result = original_handler(handler, event)
            increment('handler.emitted_event_versions', EventQueue.event_cursor()-before)
            increment('handler.invocations')
            return result

    original_global = EventQueue._global_handlers_for_event
    def global_handlers(cls, event, *, positioned):
        increment('discovery.global_lookups')
        with span('events.global_lookup'):
            result = original_global(event, positioned=positioned)
        increment('discovery.global_admitted', len(result))
        return result

    original_candidates = EventQueue._event_trigger_candidates
    def candidates(cls, event, *, include_simple):
        result = original_candidates(event, include_simple=include_simple)
        increment('discovery.indexed_candidates_visited', len(result))
        return result

    original_lookup = EventQueue._get_handlers_for_event
    def lookup(cls, event):
        with span('events.lookup', {'event_uuid': str(event.uuid),
                'lineage_uuid': str(event.lineage_uuid), 'event_type': event.event_type.value,
                'event_phase': event.phase.value} if current is not None else None):
            result = original_lookup(event)
        increment('discovery.final_admitted', len(result))
        return result

    original_trigger = Trigger.__call__
    def trigger(owner, event):
        result = original_trigger(owner, event)
        increment('discovery.base_trigger_tests')
        increment('discovery.base_trigger_matches', int(result))
        return result

    original_dump_json = BaseModel.model_dump_json
    def dump_json(model, *arguments, **keywords):
        with span('model.dump_json'):
            result = original_dump_json(model, *arguments, **keywords)
        increment('model.dump_json.characters', len(result))
        return result

    original_copy = BaseModel.model_copy
    def model_copy(model, *arguments, **keywords):
        increment('model.copy.fields', len(model.__dict__))
        increment('model.copy.deep_calls', int(keywords.get('deep', False)))
        with span('model.copy'):
            return original_copy(model, *arguments, **keywords)

    def world_count(world, occurrence, applied, before, view, *arguments):
        increment('world_update.world_objects_available', len(world.objects))
        increment('world_update.visible_tiles_available', mask_count(view.visible))
        increment('world_update.applied_records', len(applied))

    modules = (
        (worker, 'execute_player_action', 'action.execute', worker.execute_player_action, None),
        (worker, 'capture_application_operation', 'audience.capture_project', worker.capture_application_operation, None),
        (sensory, 'capture_senses_snapshot', 'sensory.snapshot', sensory.capture_senses_snapshot, snapshot_count),
        (sensory, 'emit_sensory_update_delta', 'sensory.delta', sensory.emit_sensory_update_delta, None),
        (reduction, 'copy_target', 'reduction.copy_target', reduction.copy_target, target_count),
        (reduction, 'reduce_nodes', 'reduction.nodes', reduction.reduce_nodes, None),
        (application, 'capture_lineages', 'capture.lineages', application.capture_lineages, None),
        (application, 'project_lineages', 'projection.lineage', application.project_lineages, None),
        (projection, 'seat_world_update', 'projection.world_update', projection.seat_world_update, world_count),
        (projection, '_public_occurrences', 'projection.occurrences', projection._public_occurrences, None),
        (audience, 'apply_current_senses', 'audience.current_member_senses', audience.apply_current_senses, None),
    )
    methods = (
        (sensory.SpatialSensesSystem, '__call__', 'sensory.callback', sensory.SpatialSensesSystem.__call__),
        (sensory.SpatialSensesSystem, 'recompute_observer', 'sensory.full_solve', sensory.SpatialSensesSystem.recompute_observer),
        (GridMap, 'move_light_source', 'grid.move_light', GridMap.move_light_source),
        (GridMap, 'compute_fov_cells', 'grid.fov', GridMap.compute_fov_cells),
        (GridMap, 'compute_paths', 'grid.paths', GridMap.compute_paths),
    )
    if args.coarse_timing:
        modules = (
            (worker, 'execute_player_action', 'worker.execute', worker.execute_player_action, None),
            (worker, 'capture_application_operation', 'worker.capture_application', worker.capture_application_operation, None),
            (sensory, 'emit_sensory_update_delta', 'sensory.delta', sensory.emit_sensory_update_delta, None),
            (application, 'capture_lineages', 'capture.lineages', application.capture_lineages, None),
            (application, 'project_lineages', 'projection.lineage', application.project_lineages, None),
        )
        methods = (
            (sensory.SpatialSensesSystem, 'recompute_observer', 'sensory.recompute_observer', sensory.SpatialSensesSystem.recompute_observer),
            (GridMap, '_compute_directional_fovs', 'grid._compute_directional_fovs', GridMap._compute_directional_fovs),
            (GridMap, 'compute_fov_cells', 'grid.compute_fov_cells', GridMap.compute_fov_cells),
            (GridMap, 'compute_paths', 'grid.compute_paths', GridMap.compute_paths),
            (GridMap, 'move_light_source', 'grid.move_light', GridMap.move_light_source),
            (Entity, '_materialize_navigation_distance', 'entity.materialize_navigation', Entity._materialize_navigation_distance),
        )
    def handler_call(original):
        def call(owner, event, *arguments, **keywords):
            if current is None:
                return original(owner, event, *arguments, **keywords)
            with span('handler.body.'+owner.get_semantic_key()+'.'+owner.name,
                    {'handler_uuid': str(owner.uuid), 'event_uuid': str(event.uuid),
                     'lineage_uuid': str(event.lineage_uuid), 'event_type': event.event_type.value,
                     'event_phase': event.phase.value}):
                increment('handler.body_calls_including_direct_and_preflight')
                return original(owner, event, *arguments, **keywords)
        return call

    with ExitStack() as patches:
        for owner, name, label, original, counter in modules:
            patches.enter_context(patch.object(owner, name, measured(label, original, counter)))
        for owner, name, label, original in methods:
            patches.enter_context(patch.object(owner, name, measured(label, original)))
        patches.enter_context(patch.object(worker, 'read_packet', read))
        patches.enter_context(patch.object(worker, 'write_packet', write))
        patches.enter_context(patch.object(worker, 'dispatch', dispatch))
        if not args.coarse_timing:
            patches.enter_context(patch.object(TypeAdapter, 'validate_json', validate))
            patches.enter_context(patch.object(EventQueue, '_invoke_handler', classmethod(invoke)))
            patches.enter_context(patch.object(EventQueue, '_get_handlers_for_event', classmethod(lookup)))
            patches.enter_context(patch.object(EventQueue, '_event_trigger_candidates', classmethod(candidates)))
            patches.enter_context(patch.object(EventQueue, '_global_handlers_for_event', classmethod(global_handlers)))
            patches.enter_context(patch.object(Trigger, '__call__', trigger))
            for owner, original in ((BaseHandler, BaseHandler.__call__),
                    (EventHandler, EventHandler.__call__), (SpatialHandler, SpatialHandler.__call__)):
                patches.enter_context(patch.object(owner, '__call__', handler_call(original)))
            patches.enter_context(patch.object(BaseModel, 'model_copy', model_copy))
            patches.enter_context(patch.object(BaseModel, 'model_dump_json', dump_json))
        gc.callbacks.append(gc_callback)
        try:
            worker.run_process()
        finally:
            finish()
            gc.callbacks.remove(gc_callback)


if __name__ == '__main__':
    main()
