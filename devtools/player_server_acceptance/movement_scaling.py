"""Opt-in live SDK movement scaling, with separate plain and diagnostic lanes.

Example (run only when coordinated with other live lanes):
  uv run --no-sync python -m devtools.player_server_acceptance.movement_scaling run \
      --axis objects --size large --samples 5 --output .runtime/scaling/objects-large

Warm-up commands are real SDK operations and are excluded from the movement
cohort. The worker's fixture hook is setup only; it never executes a player move.
The diagnostic worker/marker plumbing is temporary and removed at plan step 7.
"""
import argparse
import asyncio
from collections import Counter, deque
from contextlib import ExitStack
import cProfile
import gc
import json
from pathlib import Path
import pstats
import socket
import sys
from time import monotonic, perf_counter_ns
from types import CodeType, FrameType, FunctionType, ModuleType, TracebackType
from unittest.mock import patch
from uuid import UUID, uuid4

from dnd_player import (Follower, acknowledge, action_options, attach, binding_position, binding_value, choices, connect, follow,
    preview, receipt, status, submit_command, wait_for_cursor)
from devtools.player_server_acceptance import test_host
from devtools.player_server_acceptance.gallery import move_toward, rows
from devtools.player_server_acceptance.http_performance import summary
from devtools.player_server_acceptance.movement_scaling_fixture import (
    END, LEVELS, MOVER, SIZES, START, configuration, mutate_remote, prepare)
from dnd.blocks.sensory import SpatialSensesSystem, spatial_senses_system
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.dice import Dice, DiceRoll
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.values import BaseValue
from dnd.encounter import Encounter
from dnd.player.reduction import reduce_initialization, reduce_operation
from server import connection as worker_connection, worker
from server.protocol import InitializationResponse, PlayerOperation


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def census(runtime):
    """Diagnostic cardinalities, read without materializing registry copies."""
    grid = get_map()
    return {'events': EventQueue.event_cursor(), 'tiles': len(grid._tiles),
        'objects': len(grid._object_placements), 'conditions': len(grid._spatial_conditions),
        'observers': len(spatial_senses_system.senses_by_observer),
        'event_handlers': len(EventQueue._event_handlers),
        'spatial_handlers': len(EventQueue._spatial_handlers),
        'current_indexes': {
            'support_column_chunks': len(grid._support_columns),
            'contact_chunks': len(grid._contact_candidate_cells),
            'fov_origins': len(grid._fov_cache),
            'path_queries': len(grid._path_cache),
        },
        'seats': len(runtime.audiences),
        'audiences': {seat: {'remembered_tiles': len(owner.projection.remembered.tiles),
            'remembered_objects': len(owner.projection.remembered.objects),
            'seen': len(owner.projection.remembered.senses.seen) if owner.projection.remembered.senses else 0,
            'visible': len(owner.projection.remembered.senses.visible) if owner.projection.remembered.senses else 0,
            'fields': {runtime.session.game.entities[identity].name: {
                'max_distance': senses._field.max_distance if senses._field else None,
                'optical_route_cells': len(senses._field.optical_routes) if senses._field else 0,
                'visible_cells': len(senses.visible)}
                for identity in runtime.session.seats[seat].observers
                if (senses := spatial_senses_system.senses_by_observer.get(identity)) is not None}}
            for seat, owner in runtime.audiences.items()}}


def heap_census(runtime):
    """Scalar ownership evidence only; allocation here invalidates latency claims."""
    started = perf_counter_ns()
    generation_objects = [len(gc.get_objects(generation)) for generation in range(3)]
    gc_stats_before = gc.get_stats()
    objects = gc.get_objects()
    collectible = {id(value) for value in objects}
    counts, sizes = Counter(), Counter()
    for value in objects:
        name = type(value).__module__ + '.' + type(value).__qualname__
        counts[name] += 1
        sizes[name] += sys.getsizeof(value)
    del value

    def graph(roots):
        visited, counted = set(), set()
        by_type, shallow_bytes, edges = Counter(), 0, 0
        pending = list(roots)
        while pending:
            value = pending.pop()
            identity = id(value)
            if identity in visited or not gc.is_tracked(value):
                continue
            if isinstance(value, (type, ModuleType, CodeType, FrameType, TracebackType)):
                continue
            visited.add(identity)
            references = gc.get_referents(value)
            if identity in collectible:
                counted.add(identity)
                by_type[type(value).__module__ + '.' + type(value).__qualname__] += 1
                shallow_bytes += sys.getsizeof(value)
                edges += len(references)
            if isinstance(value, FunctionType):
                # Follow captured runtime owners, never a function's globals.
                references = [part for part in (value.__defaults__,
                    value.__kwdefaults__, value.__closure__) if part is not None]
            # Frozen root containers can own newly collectible descendants.
            # Bound methods/partials retain their native receivers/arguments.
            pending.extend(references)
        return counted, {'objects': len(counted), 'shallow_bytes': shallow_bytes,
            'reference_edges': edges, 'types': dict(by_type.most_common())}

    roots = {
        'native_history': [EventQueue._all_events],
        'native_history_indexes': [EventQueue._events_by_lineage,
            EventQueue._events_by_uuid, EventQueue._event_indexes_by_uuid,
            EventQueue._events_by_type, EventQueue._events_by_phase,
            EventQueue._events_by_source, EventQueue._events_by_target],
        'native_current': [get_map(), BaseBlock._registry, BaseObject._registry,
            BaseValue._registry, Dice._registry, DiceRoll._registry, runtime.session],
        'audience_current': [runtime.catalog, *runtime.audiences.values()],
    }
    reached, summaries = {}, {}
    for name, values in roots.items():
        reached[name], summaries[name] = graph(values)
    union = set().union(*reached.values())
    intersections = {left + ' & ' + right: len(reached[left] & reached[right])
        for index, left in enumerate(reached) for right in tuple(reached)[index + 1:]}
    metadata = {}

    def metadata_value(name, value):
        identity = id(value)
        identities, row = metadata.setdefault(name,
            (set(), {'objects': 0, 'collectible': 0, 'shallow_bytes': 0}))
        if identity not in identities:
            identities.add(identity)
            row['objects'] += 1
            row['collectible'] += identity in collectible
            row['shallow_bytes'] += sys.getsizeof(value)

    for event in EventQueue._all_events:
        for name, value in (
            ('event_models', event), ('model_dicts', event.__dict__),
            ('model_field_sets', event.__pydantic_fields_set__),
            ('model_private_dicts', event.__pydantic_private__),
            ('children_events', event.children_events),
            ('lineage_children_events', event.lineage_children_events),
            ('children_lineages', event.children_lineages),
            ('identified_grants', event.identified_entity_observer_uuids),
            ('located_grants', event.located_entity_observer_uuids),
            ('position_grants', event.located_position_observer_uuids)):
            metadata_value(name, value)
        for grants in (event.identified_entity_observer_uuids,
                       event.located_entity_observer_uuids,
                       event.located_position_observer_uuids):
            for observers in grants.values():
                metadata_value('grant_sets', observers)
    return {
        'scope': 'Allocation/ownership diagnostic only; not latency evidence. '
            'Counted objects were in gc.get_objects at snapshot time. Frozen root '
            'containers are traversed but not counted. Owner subsets overlap. '
            'Function globals, classes, modules, code, frames and tracebacks are '
            'excluded; bound receivers and function defaults/closures are followed. '
            'Reference-edge counts include raw outgoing links to excluded graphs; '
            'event metadata categories can share the same underlying containers. '
            'Shallow sizes are not RSS or total memory. Census allocations and '
            'natural GC perturb the lane; no collection-policy change.',
        'events': EventQueue.event_cursor(),
        'event_families': dict(Counter(type(event).__name__
            for event in EventQueue._all_events).most_common()),
        'gc_enabled': gc.isenabled(), 'gc_threshold': gc.get_threshold(),
        'generation_objects_before_snapshot': generation_objects,
        'gc_stats_before_census': gc_stats_before,
        'frozen_objects': gc.get_freeze_count(), 'gc_stats': gc.get_stats(),
        'tracked_objects': sum(counts.values()),
        'tracked_types': dict(counts.most_common()),
        'tracked_shallow_bytes_by_type': dict(sizes.most_common()),
        'owner_graphs': summaries, 'owner_intersections': intersections,
        'owner_union_objects': len(union),
        'tracked_outside_owner_union': len(collectible - union),
        'native_event_metadata': {name: row for name, (_, row) in metadata.items()},
        'registries': {'blocks': len(BaseBlock._registry),
            'objects': len(BaseObject._registry), 'values': len(BaseValue._registry),
            'dice': len(Dice._registry), 'rolls': len(DiceRoll._registry)},
        'elapsed_ms': (perf_counter_ns() - started) / 1e6,
    }


def run_worker(args):
    original_create = worker.create_authored_session
    original_dispatch, original_read = worker.dispatch, worker.read_packet
    runtime = None
    profile = None
    measured = None
    work_counts = Counter()
    remote_mutated = False
    gc_started = None
    original_advance_boundary = Encounter.advance_one_controller_action_boundary

    def gc_timing(phase, info):
        nonlocal gc_started
        if measured is None:
            return
        if phase == 'start':
            gc_started = perf_counter_ns()
        elif gc_started is not None:
            ended = perf_counter_ns()
            measured['gc_pauses'].append({'generation': info['generation'],
                'start_ns': gc_started, 'end_ns': ended,
                'collected': info['collected'], 'uncollectable': info['uncollectable']})
            gc_started = None

    def advance_boundary(encounter, *arguments, **keywords):
        nonlocal remote_mutated
        result = original_advance_boundary(encounter, *arguments, **keywords)
        if args.remote_mutation and not remote_mutated and result.status == 'waiting_for_human':
            mutate_remote()
            remote_mutated = True
        # The original advance_controller captures this interval once, after
        # both turn-start and remote-mutation events/logs have settled.
        return result

    original_candidates = EventQueue._event_trigger_candidates
    original_observers = SpatialSensesSystem.candidate_observer_uuids
    original_optics = GridMap.capture_optical_obscurements

    def candidates(cls, event, *, include_simple):
        result = original_candidates(event, include_simple=include_simple)
        if profile is not None:
            work_counts['handler_index_candidates_visited'] += len(result)
        return result

    def observers(owner, event):
        result = original_observers(owner, event)
        if profile is not None:
            work_counts['candidate_observers'] += len(result)
        return result

    def optics(owner, origin, radius):
        result = original_optics(owner, origin, radius)
        if profile is not None:
            work_counts['optical_contributing_cells'] += len(result)
            work_counts['optical_contributing_owners'] += sum(map(len, result.values()))
        return result

    def create(*arguments, **keywords):
        return prepare(original_create(*arguments, **keywords), args.axis, args.amount)

    def finish():
        nonlocal profile, measured, gc_started
        if profile is not None:
            profile.disable()
        completed = measured
        measured = None
        gc_started = None
        if completed is not None and args.gc_timing:
            completed['end_ns'] = perf_counter_ns()
        final_heap = (heap_census(runtime)
            if completed is not None and args.heap_census
            and completed['sample'] == args.samples else None)
        if runtime is not None:
            current = census(runtime)
            write_json(args.output / 'census.json', current)
            if completed is not None:
                completed['after'] = current
                completed['work_counts'] = dict(work_counts)
                if profile is not None:
                    destination = args.output / f"command-{completed['sample']}.pstats"
                    profile.dump_stats(str(destination))
                    completed['functions'] = [{'file': key[0], 'line': key[1], 'name': key[2],
                        'calls': value[1], 'self_ms': value[2] * 1000,
                        'inclusive_ms': value[3] * 1000}
                        for key, value in pstats.Stats(profile).stats.items()]
                write_json(args.output / f"command-{completed['sample']}.json", completed)
        if final_heap is not None:
            # Publish completion only after the ordinary census is also ready.
            write_json(args.output / 'heap-after.json', final_heap)
        profile = measured = None
        work_counts.clear()

    def read(stream):
        # Native framing has completed before these diagnostics are written.
        finish()
        return original_read(stream)

    def dispatch(owner, request):
        nonlocal runtime, profile, measured
        runtime = owner
        marker = args.output / 'measure-next.json'
        if request.kind == 'command' and marker.exists():
            selected = json.loads(marker.read_text())
            if (selected['seat'] == request.seat_id
                    and selected['command_number'] == request.request.command_number):
                before = census(owner)
                if args.heap_census and selected['sample'] == 1:
                    write_json(args.output / 'heap-before.json', heap_census(owner))
                selected = {**selected, 'before': before,
                    'diagnostic': args.diagnostic or args.heap_census,
                    'heap_census_lane': args.heap_census}
                if args.gc_timing:
                    selected.update(start_ns=perf_counter_ns(), gc_pauses=[])
                measured = selected
                marker.unlink()
                if args.diagnostic:
                    profile = cProfile.Profile()
                    profile.enable()
        return original_dispatch(owner, request)

    with ExitStack() as patches:
        patches.enter_context(patch.object(worker, 'create_authored_session', create))
        patches.enter_context(patch.object(worker, 'dispatch', dispatch))
        patches.enter_context(patch.object(worker, 'read_packet', read))
        if args.remote_mutation:
            patches.enter_context(patch.object(Encounter, 'advance_one_controller_action_boundary', advance_boundary))
        if args.diagnostic:
            patches.enter_context(patch.object(EventQueue, '_event_trigger_candidates', classmethod(candidates)))
            patches.enter_context(patch.object(SpatialSensesSystem, 'candidate_observer_uuids', observers))
            patches.enter_context(patch.object(GridMap, 'capture_optical_obscurements', optics))
        if args.gc_timing:
            gc.callbacks.append(gc_timing)
        try:
            worker.run_process()
        finally:
            if args.gc_timing:
                gc.callbacks.remove(gc_timing)
            finish()


async def run_host(args):
    async def launch():
        process = await asyncio.create_subprocess_exec(sys.executable, '-m', __spec__.name,
            'worker', '--output', str(args.output), '--axis', args.axis,
            '--amount', str(args.amount),
            '--samples', str(args.samples),
            *(['--remote-mutation'] if args.remote_mutation else []),
            *(['--gc-timing'] if args.gc_timing else []),
            *(['--heap-census'] if args.heap_census else []),
            *(['--diagnostic'] if args.diagnostic else []),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        diagnostics = deque(maxlen=64)
        return worker_connection.Connection(process, diagnostics,
            asyncio.create_task(worker_connection._drain(process.stderr, diagnostics)))

    args.config = args.output / 'server.json'
    args.stop = args.output / 'server.stop'
    args.result = args.output / 'host-result.json'
    args.host = '127.0.0.1'
    args.worker_profile = None
    args.profile_census_after = 0
    with patch.object(worker_connection, 'launch', launch):
        await test_host.run(args)


def local_result(state):
    """Stable local values; remote memory and incidental UUIDs stay separate."""
    def local(position):
        return position is not None and 0 <= position[0] < 15 and 0 <= position[1] < 15
    senses = state.senses
    return {'actors': sorted((actor.name, actor.last_visual_position, actor.normal_hp,
            actor.life_state.value, actor.present)
            for actor in state.actors.values() if local(actor.last_visual_position)),
        'visible': sorted(position for position in senses.visible if local(position)) if senses else [],
        'light': sorted((position, int(value)) for position, value in senses.effective_light_levels.items()
            if local(position)) if senses else [],
        'objects': sorted((value.item.name, tuple(value.placement.positions))
            for value in state.objects.values() if any(local(position) for position in value.placement.positions)),
        'local_seen': sorted(position for position in senses.seen if local(position)) if senses else [],
        'entity_contacts': sorted((state.actors[identity].name, contact.position, contact.visual,
            tuple(mode.value for mode in contact.special_senses)) for identity, contact in senses.entities.items()
            if local(contact.position)) if senses else [],
        'object_contacts': sorted((state.objects[identity].item.name, contact.position, contact.visual,
            tuple(mode.value for mode in contact.special_senses)) for identity, contact in senses.objects.items()
            if local(contact.position) and identity in state.objects) if senses else [],
        'hazards': sorted((position, hazardous) for position, hazardous in senses.hazardous_cells.items()
            if local(position)) if senses else [],
        'spatial_effects': [effect.model_dump(mode='json', exclude={'condition_uuid', 'source_entity_uuid'})
            for effect in senses.spatial_effects.values()
            if any(local(position) for position in effect.positions)] if senses else []}


def operation_shape(packet):
    """Retain ordered public event kinds and logs for the local-output check."""
    def log_value(entry):
        if entry is None:
            return None
        return {key: entry[key] for key in ('entry_type', 'source_name', 'target_name',
            'compact', 'verbose', 'detailed', 'success')}
    if packet['kind'] == 'initialization':
        return {'kind': 'initialization'}
    return {'kind': packet['kind'],
        'lineages': [{'root_disclosed': lineage['root'] is not None,
            'events': [(node['phase'], node['canceled'],
                node['fact']['kind'] if node['fact'] else None, log_value(node['combat_log']))
                for node in lineage['events']],
            'observations': len(lineage['observations']),
            'world_updates': len(lineage['world_updates'])} for lineage in packet['lineages']],
        'logs': [log_value(row['entry']) for row in packet['combat_log_appends']]}


async def record(args, settings, url):
    clients, followers, states, tasks, counts = {}, {}, {}, [], {}
    public_records = {}
    rows_out, samples = [], []
    started = monotonic()
    try:
        for credential in settings.credentials:
            seat = credential.seat_id
            client = await connect(url, credential.token)
            clients[seat] = client
            current = client.bootstrap['status']
            while current['published_cursor'] is None:
                await asyncio.sleep(.05)
                current = await status(client)
            client.bootstrap['status'] = current
            await attach(client, {'acquisition_id': str(uuid4()),
                'expected_attachment_epoch': current['attachment_epoch']})
            directory = args.output / 'journal' / seat
            directory.mkdir(parents=True)
            counts[seat] = {'records': 0, 'bytes': 0}
            public_records[seat] = []

            async def consume(packet, raw, seat=seat, directory=directory):
                sequence = packet['cursor']['sequence']
                if sequence != counts[seat]['records']:
                    raise AssertionError(f'Non-contiguous recorded cursor for {seat}: {sequence}')
                counts[seat]['records'] += 1
                counts[seat]['bytes'] += len(raw)
                if counts[seat]['bytes'] > 1024 * 1024 * 1024:
                    raise RuntimeError('Scaling recording exceeded 1 GiB per seat')
                (directory / f'{sequence:016}.json').write_bytes(raw)
                public_records[seat].append(operation_shape(packet))
                if packet['kind'] == 'initialization':
                    parsed = InitializationResponse.model_validate_json(raw)
                    states[seat] = reduce_initialization(parsed.initialization,
                        content_additions=parsed.content_additions)
                else:
                    states[seat] = reduce_operation(states[seat], PlayerOperation.model_validate_json(raw))

            followers[seat] = Follower(client, consume)
            tasks.append(asyncio.create_task(follow(followers[seat])))

        async def current_turn():
            while True:
                for task in tasks:
                    if task.done():
                        await task
                        raise RuntimeError('Encounter ended before the scaling lane finished')
                eligible = None
                for seat, client in clients.items():
                    now = await status(client)
                    await wait_for_cursor(followers[seat], now['published_cursor'])
                    await acknowledge(client, followers[seat].consumed)
                    if now['boundary']['input_actor_uuid'] is not None:
                        eligible = seat, client, now
                if eligible is not None:
                    return eligible
                await asyncio.sleep(.001)

        await current_turn()
        mover_seat = next(seat for seat, state in states.items()
            if any(state.actors[identity].name == MOVER for identity in state.viewing_audience.controlled))
        mover_uuid = next(identity for identity, actor in states[mover_seat].actors.items() if actor.name == MOVER)

        def movement_remaining():
            hud = states[mover_seat].hud_snapshot
            sheet = next(sheet for sheet in hud.sheets if sheet.actor_uuid == mover_uuid)
            return next(resource.current for resource in sheet.resources if resource.key == 'movement')

        async def command(destination=None, sample=None, phase='warmup', dash=False):
            seat, client, now = await current_turn()
            actor = now['boundary']['input_actor_uuid']
            revision = now['boundary']['state_revision']
            intent, action = {'kind': 'end_turn'}, 'end_turn'
            choices_ms = preview_ms = 0.0
            state = states[seat]
            before = local_result(states[mover_seat]) if sample is not None else None
            budget_before = movement_remaining()
            position = state.actors[UUID(actor)].last_visual_position
            if UUID(actor) == mover_uuid and (destination is not None or dash):
                discovery_start = perf_counter_ns()
                discovered = (await choices(client, {'actor_uuid': actor, 'state_revision': revision,
                    'force_attack': False, 'correlation_id': str(uuid4())}))['choices']
                choices_ms = (perf_counter_ns() - discovery_start) / 1e6
                available = rows(discovered)
                if dash:
                    row = next(row for row in available if row['behavior_id'] == 'action.dash')
                    selected = row, action_options(discovered, row)[0]
                else:
                    selected = move_toward(discovered, available, position, (destination,))
                if selected is not None:
                    row, target = selected
                    if sample is not None and (tuple(binding_position(discovered, target)) != destination or binding_value(target, 'path_cost') != 30):
                        raise AssertionError('Measured selection is not the required ordinary six-cell move')
                    selection = {'action_index': row['discovery_index'], 'target_indices': [target['index']],
                        'extra_target_positions': []}
                    preview_start = perf_counter_ns()
                    result = await preview(client, {'actor_uuid': actor, 'state_revision': revision,
                        'discovery_generation': discovered['discovery_generation'],
                        'correlation_id': str(uuid4()), 'selection': selection})
                    preview_ms = (perf_counter_ns() - preview_start) / 1e6
                    if not result['preview']['can_confirm']:
                        raise AssertionError('Native movement preview did not confirm the selected path')
                    intent = {'kind': 'execute_selection',
                        'discovery_generation': discovered['discovery_generation'], 'selection': selection}
                    action = row['behavior_id']
            if sample is not None and action != 'action.move':
                raise AssertionError('Measured command must be an available movement action')
            request = {'command_number': now['next_command_number'], 'actor_uuid': actor,
                'state_revision': revision, 'intent': intent}
            prior_records = {key: value.copy() for key, value in counts.items()}
            if sample is not None:
                write_json(args.output / 'measure-next.json', {'sample': sample, 'seat': seat,
                    'command_number': request['command_number']})
            submit_start = perf_counter_ns()
            outcome = await submit_command(client, request)
            submit_end = perf_counter_ns()
            polls = 0
            while outcome['receipt']['kind'] == 'pending':
                await asyncio.sleep(.001)
                outcome = await receipt(client, request['command_number'])
                polls += 1
            committed = perf_counter_ns()
            if outcome['receipt']['kind'] != 'committed':
                raise AssertionError(f'Native command rejected: {outcome}')
            await wait_for_cursor(followers[seat], outcome['receipt']['cursor'])
            consumed = perf_counter_ns()
            # Drain every seat before a next sample; output growth is real work.
            for audience, client_for_seat in clients.items():
                published = await status(client_for_seat)
                await wait_for_cursor(followers[audience], published['published_cursor'])
                await acknowledge(client_for_seat, followers[audience].consumed)
            row = {'phase': phase, 'seat': seat, 'command_number': request['command_number'],
                'action': action, 'cursor': outcome['receipt']['cursor'], 'before_position': position,
                'position': states[mover_seat].actors[mover_uuid].last_visual_position,
                'choices_ms': choices_ms, 'preview_ms': preview_ms,
                'submit_ms': (submit_end - submit_start) / 1e6,
                'committed_ms': (committed - submit_start) / 1e6,
                'consumed_ms': (consumed - submit_start) / 1e6,
                'receipt_polls': polls, 'receipt_poll_sleep_seconds': .001,
                'movement_before': budget_before, 'movement_after': movement_remaining(),
                'output': {key: {kind: counts[key][kind] - prior_records[key][kind]
                    for kind in ('records', 'bytes')} for key in counts}}
            rows_out.append(row)
            if sample is not None:
                if tuple(row['position']) != destination:
                    raise AssertionError('Committed movement did not reach its previewed destination')
                expected_budget = (60, 30) if args.positive_budget else (30, 0)
                if (row['movement_before'], row['movement_after']) != expected_budget:
                    raise AssertionError(f'Measured movement budget differs from {expected_budget}: {row}')
                row.update(sample=sample, local_before=before, local_after=local_result(states[mover_seat]))
                row['public_operation_shape'] = {key: public_records[key][prior_records[key]['records']:]
                    for key in counts}
                samples.append(row)
            with (args.output / 'commands.jsonl').open('a') as stream:
                stream.write(json.dumps(row) + '\n')
            return row

        async def move_to(destination):
            while tuple(states[mover_seat].actors[mover_uuid].last_visual_position) != destination:
                await command(destination)

        async def fresh_mover_turn():
            # End the current turn even if it belongs to the mover, so every
            # measured command starts with its full normal movement allowance.
            await command()
            while UUID((await current_turn())[2]['boundary']['input_actor_uuid']) != mover_uuid:
                await command()

        # A remote-change comparison measures the first local command after the
        # native mutation. Its matched reference also uses --first-move.
        if not args.first_move:
            await move_to(END)
            await move_to(START)
        initial = json.loads((args.output / 'census.json').read_text())
        if args.axis in ('objects', 'optical_conditions', 'nonoptical_conditions', 'handlers'):
            realized = initial['objects'] if args.axis == 'objects' else initial['conditions']
            if realized < args.amount:
                raise AssertionError(f'Native fixture retained only {realized} requested owners out of {args.amount}')
        warmup_start = monotonic()
        if args.axis == 'history':
            while json.loads((args.output / 'census.json').read_text())['events'] < initial['events'] + args.amount:
                await command()
        if args.axis == 'memory':
            initial_seen = len(states[mover_seat].senses.seen)
            await move_to((7, 6))
            destination_y = 12
            while len(states[mover_seat].senses.seen) < initial_seen + args.amount:
                destination_y += 6
                if destination_y >= 1500:
                    raise RuntimeError('Authored exploration corridor exhausted before the requested memory count')
                await move_to((7, destination_y))
            await move_to((7, 6))
            await move_to(START)
        warmup_seconds = monotonic() - warmup_start
        for index in range(args.samples):
            if index != 0 or not args.first_move:
                await fresh_mover_turn()
            if args.positive_budget:
                await command(dash=True, phase='budget_setup')
            destination = END if tuple(states[mover_seat].actors[mover_uuid].last_visual_position) == START else START
            await command(destination, sample=index + 1, phase='measured')
        if args.heap_census:
            while not (args.output / 'heap-after.json').exists():
                await asyncio.sleep(.01)
        final_census = json.loads((args.output / 'census.json').read_text())
        if args.axis == 'sight_radius':
            for stage in (initial, final_census):
                actual = stage['audiences'][mover_seat]['fields'][MOVER]['max_distance']
                if actual != args.amount:
                    raise AssertionError(f'Ordinary command changed the configured sight radius: {actual}')
        result = {'axis': args.axis, 'size': args.size, 'amount': args.amount,
            'diagnostic': args.diagnostic or args.heap_census,
            'cprofile': args.diagnostic, 'heap_census_lane': args.heap_census,
            'remote_mutation': args.remote_mutation,
            'gc_timing': args.gc_timing,
            'first_move': args.first_move,
            'positive_budget': args.positive_budget,
            'samples': samples, 'latencies': {key: summary([row[key] for row in samples])
                for key in ('committed_ms', 'consumed_ms', 'choices_ms', 'preview_ms')},
            'initial_census': initial, 'final_census': final_census,
            'warmup_seconds': warmup_seconds, 'elapsed_seconds': monotonic() - started,
            'operations': len(rows_out), 'records': counts,
            'measurement': 'SDK submit through observed committed receipt; original recorded cursor consumed and ACKed. Setup, discovery, preview, warm-up and post-receipt reduction excluded from this endpoint; concurrent probe interference remains included.',
            'confounds': (['Native remote Grease owners add spatial conditions and their real handler registrations; compare their counts separately.']
                if args.axis == 'handlers' else
                ['Remote creatures also add native observers, default possessions and owned handlers; reaction_handlers explicitly installs native opportunity attacks on opposing creatures with a reaction budget and adjacent melee threat.']
                if args.axis in ('observers', 'reaction_handlers') else []),
            'history_scope': 'Requested history amount is additional native event versions after startup and common route warm-up; actual retained counts are reported, never forged.',
            'p95_scope': 'Only qualifying measured six-cell moves count; p95 is emitted only at 100 or more samples.'}
        if args.heap_census:
            result['measurement'] = ('Allocation/ownership diagnostic, not speed evidence. '
                'Full heap censuses before first move and after last move perturb '
                'allocation/GC and receipt/probe timing. Raw timings are retained.')
            result['p95_scope'] = 'No latency acceptance claim from this heap-census lane.'
        result['probe_overhead'] = 'Plain and diagnostic lanes include command marker lookup and an O(seats) pre-command cardinality census inside SDK elapsed. These temporary hooks are removed for the final clean latency lane.'
        write_json(args.output / 'result.json', result)
        print(json.dumps({'axis': args.axis, 'size': args.size, 'samples': len(samples),
            'operations': len(rows_out), 'latencies': result['latencies']}), flush=True)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.gather(*(client.http.aclose() for client in clients.values()))


async def run(args):
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    args.amount = LEVELS[args.axis][SIZES.index(args.size)]
    settings = configuration(args.axis, args.amount, args.output)
    config = args.output / 'server.json'
    config.write_text(settings.model_dump_json(indent=2))
    config.chmod(0o600)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with (args.output / 'server.log').open('wb') as log:
        host = await asyncio.create_subprocess_exec(sys.executable, '-m', __spec__.name,
            'host', '--output', str(args.output), '--axis', args.axis, '--amount', str(args.amount),
            '--samples', str(args.samples),
            '--port', str(port), *(['--diagnostic'] if args.diagnostic else []),
            *(['--gc-timing'] if args.gc_timing else []),
            *(['--heap-census'] if args.heap_census else []),
            *(['--remote-mutation'] if args.remote_mutation else []), stdout=log, stderr=log)
        try:
            async with asyncio.timeout(args.timeout):
                while not (args.output / 'host.ready').exists():
                    if host.returncode is not None:
                        raise RuntimeError('Scaling host exited during startup; see server.log')
                    await asyncio.sleep(.05)
                await record(args, settings, f'http://127.0.0.1:{port}')
        finally:
            (args.output / 'server.stop').touch()
            await asyncio.wait_for(host.wait(), 30)
        if host.returncode != 0:
            raise RuntimeError('Scaling host failed; see server.log')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('run', 'host', 'worker', 'compare'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--axis', choices=tuple(LEVELS), default='baseline')
    parser.add_argument('--size', choices=SIZES, default='small')
    parser.add_argument('--amount', type=int, default=0)
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--timeout', type=float, default=3600)
    parser.add_argument('--port', type=int)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--gc-timing', action='store_true',
        help='Record passive GC pause timings without changing collection policy or enabling cProfile')
    parser.add_argument('--heap-census', action='store_true',
        help='Allocation-only lane: full heap ownership census before first and after last sample')
    parser.add_argument('--remote-mutation', action='store_true')
    parser.add_argument('--first-move', action='store_true')
    parser.add_argument('--positive-budget', action='store_true',
        help='Execute native SDK Dash outside the clock, then measure a six-cell move leaving 30 feet')
    parser.add_argument('--reference', type=Path)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('--samples must be positive')
    if args.remote_mutation:
        args.first_move = True
    if args.positive_budget and args.first_move:
        parser.error('--positive-budget is separate from first-move/remote-mutation: Dash warms navigation')
    if args.first_move and args.axis in ('memory', 'history'):
        parser.error('--first-move is a separate remote-change lane, not a warm-up axis')
    if args.mode == 'worker':
        run_worker(args)
    elif args.mode == 'host':
        asyncio.run(run_host(args))
    elif args.mode == 'run':
        asyncio.run(run(args))
    else:
        if args.reference is None:
            parser.error('compare requires --reference')
        before_result = json.loads((args.reference / 'result.json').read_text())
        after_result = json.loads((args.output / 'result.json').read_text())
        if before_result.get('positive_budget', False) != after_result.get('positive_budget', False):
            raise AssertionError('Comparison requires the same navigation budget cohort')
        before, after = before_result['samples'], after_result['samples']
        if len(before) != len(after):
            raise AssertionError('Comparison requires equal sample counts')
        for index, (old, new) in enumerate(zip(before, after), 1):
            for key in ('action', 'before_position', 'position', 'local_before', 'local_after',
                    'public_operation_shape', 'movement_before', 'movement_after'):
                if old[key] != new[key]:
                    raise AssertionError(f'Local output differs in sample {index}, field {key}')
        print(f'Equivalent local results for {len(after)} ordinary movement samples')


if __name__ == '__main__':
    main()
