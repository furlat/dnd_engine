"""Cold recorded-SDK audit using the production player reducer, without a world.

Run with the standalone SDK installed, or PYTHONPATH=sdk/python/src. The memory
pass discards each decoded packet; it measures transport decoding separately
from the replay's intentionally retained permitted state and reference index.
"""
import argparse
from collections import Counter
import gc
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from time import perf_counter
import tracemalloc
from typing import Any

from dnd_player import transport as sdk
from pydantic import TypeAdapter

from dnd.player.facts import PlayerState
from dnd.player.reduction import reduce_initialization, reduce_operation
from player_server.protocol import InitializationResponse, PlayerOperation

WORKING_BUDGET = 128 * 1024 * 1024
STATE = TypeAdapter(PlayerState)


def records(directory: Path) -> list[Path]:
    return sorted((p for p in directory.glob('*.json') if p.stem.isdecimal()), key=lambda p: int(p.stem))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def check_hud(value: dict | None, controlled: set[str]) -> None:
    if value is not None:
        require({row['actor_uuid'] for row in value['sheets']} <= controlled,
            'HUD includes a character sheet outside seat control')


def record_log(entry: dict, digest: Any, counts: Counter) -> None:
    counts['log:' + entry['entry_type']] += 1
    text = {key: entry[key] for key in ('entry_type', 'source_name', 'target_name', 'compact', 'verbose', 'detailed', 'success')}
    digest.update(json.dumps(text, sort_keys=True, separators=(',', ':')).encode())
    for child in entry['sub_entries']:
        record_log(child, digest, counts)


def check_group(group: dict, controlled: set[str], events: dict[str, int], lineages: set[str], counts: Counter, logs: Any) -> None:
    nodes = group.get('events', group.get('nodes', []))
    rows = group['version_rows']
    start = group.get('start_cursor', 0)
    require([row['source_index'] for row in rows] == list(range(start, group['end_cursor'])), 'Occurrence coordinates are not dense')
    for row in rows:
        identity, position = row['event_uuid'], row['source_index']
        require(identity not in events or events[identity] == position, 'Occurrence identity changed public coordinate')
        events[identity] = position
        lineages.add(row['lineage_uuid'])
    for node in nodes:
        if node['combat_log'] is not None:
            record_log(node['combat_log'], logs, counts)
        require(node['uuid'] in events, 'Node has no disclosed occurrence')
        for key in ('parent_event',):
            require(node[key] is None or node[key] in events, f'Undisclosed {key}')
        require(node['parent_lineage'] is None or node['parent_lineage'] in lineages, 'Undisclosed parent lineage')
        require(set(node['children_lineages']) <= lineages, 'Undisclosed child lineage')
        reference = node['resolution_ref']
        if reference is not None:
            require(reference['lineage_uuid'] in lineages, 'Undisclosed resolution owner')
            counts['application_references' if reference['kind'] == 'application' else 'event_references'] += 1
        fact = node['fact']
        if fact is None:
            continue
        counts['fact:' + fact['kind']] += 1
        if fact['kind'] == 'sensory':
            for change in fact['observed_changes']:
                require(events.get(change['source_event_uuid']) == change['source_index'], 'Sensory occurrence reference is not closed')
        if fact['kind'] == 'spatial' and fact['commit_event_uuid'] is not None:
            require(fact['commit_event_uuid'] in events, 'Spatial commit occurrence is not disclosed')
        if fact['kind'] == 'equipment' and fact['controlled_items'] is not None:
            require(fact['source_entity_uuid'] in controlled, 'Foreign equipment exposes private inventory')
        if fact['kind'] == 'damage' and fact['stage'] == 'applied':
            counts['applied_damage'] += 1
        if fact['kind'] == 'turn' and fact['event_type'] == 'encounter_end':
            counts['encounter_end'] += 1
        if fact['kind'] == 'spell' and fact['application'] is not None:
            counts['spell_applications'] += 1
            if fact['application']['index'] > 0:
                counts['nonfirst_spell_applications'] += 1
    for observation in group['observations']:
        require(observation['event_uuid'] in events, 'Observation references an undisclosed occurrence')
        actor = observation['actor']
        if actor['controlled_items'] is not None:
            require(actor['uuid'] in controlled, 'Foreign observation exposes private inventory')
    for update in group['world_updates']:
        require(update['event_uuid'] in events, 'World update references an undisclosed occurrence')
    check_hud(group.get('hud_snapshot'), controlled)


def replay_stream(directory: Path) -> dict[str, Any]:
    paths = records(directory)
    require(bool(paths), 'No numbered public records')
    metadata = json.loads((directory / 'result.json').read_bytes())
    events: dict[str, int] = {}
    lineages: set[str] = set()
    counts: Counter = Counter()
    state: PlayerState | None = None
    scope: dict = {}
    controlled: set[str] = set()
    byte_count = 0
    maximum_record = 0
    command_numbers = []
    transcript = sha256()
    logs = sha256()
    final_boundary = None
    started = perf_counter()
    for sequence, path in enumerate(paths):
        require(int(path.stem) == sequence, 'Numbered recording has a sequence gap')
        raw = path.read_bytes()
        packet = sdk.decode('InitializationResponse' if sequence == 0 else 'PlayerOperation', raw)
        sdk.check_protocol(packet['protocol'])
        require(packet['cursor']['sequence'] == sequence, 'Cursor differs from recording position')
        if sequence == 0:
            scope = {key: packet['cursor'][key] for key in ('game_id', 'game_epoch', 'audience_id')}
            controlled = set(packet['initialization']['audience']['controlled'])
        require(all(packet['cursor'][key] == value for key, value in scope.items()), 'Game/epoch/audience changed')
        for descriptor in packet['content_additions']:
            require(descriptor['visibility'] in ('public', 'observed'), 'Forbidden catalog visibility')
        if sequence == 0:
            check_group(packet['initialization'], controlled, events, lineages, counts, logs)
            initial = InitializationResponse.model_validate_json(raw)
            state = reduce_initialization(initial.initialization, content_additions=initial.content_additions)
        else:
            require(set(packet['audience']['controlled']) == controlled, 'Unexpected control membership change')
            for group in packet['lineages']:
                check_group(group, controlled, events, lineages, counts, logs)
            check_hud(packet['hud'], controlled)
            actor = packet['boundary']['input_actor_uuid']
            require(actor is None or actor in controlled, 'Boundary exposes an unowned input actor')
            operation = PlayerOperation.model_validate_json(raw)
            assert state is not None
            state = reduce_operation(state, operation)
            for row in packet['combat_log_appends']:
                record_log(row['entry'], logs, counts)
            final_boundary = packet['boundary']
            if packet['command_number'] is not None:
                command_numbers.append(packet['command_number'])
        transcript.update(len(raw).to_bytes(8, 'big'))
        transcript.update(raw)
        byte_count += len(raw)
        maximum_record = max(maximum_record, len(raw))
    require(metadata['records'] == len(paths) and metadata['bytes'] == byte_count, 'Consumer receipt and retained records differ')
    require(metadata['final_cursor'] == packet['cursor'], 'Consumer final cursor and retained prefix differ')
    require(command_numbers == list(range(1, metadata['commands'] + 1)), 'Own commands are not recorded exactly once in number order')
    require(metadata['terminal'] and final_boundary is not None and final_boundary['lifecycle'] == 'terminal', 'Recording did not reach native terminal boundary')
    require(counts['encounter_end'] > 0, 'Terminal recording lacks admitted encounter-end fact')
    assert state is not None
    require(all(actor.controlled_items is None or str(actor.uuid) in controlled for actor in state.actors.values()), 'Reduced state retained a foreign inventory')
    state_bytes = json.dumps(STATE.dump_python(state, mode='json'), sort_keys=True, separators=(',', ':')).encode()
    return {'directory': str(directory), 'language': metadata['language'], 'scope': scope, 'records': len(paths),
        'bytes': byte_count, 'maximum_record_bytes': maximum_record, 'commands': len(command_numbers), 'final_sequence': sequence,
        'occurrences': len(events), 'lineages': len(lineages), 'reducer_cursor': state.reducer_cursor,
        'controlled': sorted(controlled), 'facts': dict(sorted(counts.items())), 'terminal': True,
        'state_sha256': sha256(state_bytes).hexdigest(), 'transcript_sha256': transcript.hexdigest(),
        'combat_log_text_sha256': logs.hexdigest(),
        'catalog_entries': len(state.content), 'standalone_log_entries': len(state.combat_log_appends),
        'actors': [{'uuid': str(actor.uuid), 'name': actor.name, 'controlled': str(actor.uuid) in controlled,
            'normal_hp': actor.normal_hp, 'maximum_hp': actor.maximum_hp, 'life_state': actor.life_state.value,
            'present': actor.present, 'position': actor.last_visual_position, 'faction': actor.faction}
            for actor in sorted(state.actors.values(), key=lambda row: row.name)], 'seconds': perf_counter() - started}


def python_decode_memory(paths: list[Path]) -> dict[str, Any]:
    """Raw bytes + decoded packet + schema validation, one record at a time."""
    gc.collect()
    tracemalloc.start()
    started = perf_counter()
    try:
        for path in paths:
            raw = path.read_bytes()
            value = sdk.decode('InitializationResponse' if int(path.stem) == 0 else 'PlayerOperation', raw)
            del value, raw
        retained, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {'records': len(paths), 'peak_traced_allocation_bytes': peak, 'retained_traced_allocation_bytes': retained,
        'within_128_mib': peak <= WORKING_BUDGET, 'seconds_instrumented': perf_counter() - started,
        'scope': 'SDK read/decode/schema validation; imports completed before tracing; no reducer or history retained'}


NODE_MEMORY = r'''
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const {decode} = await import(pathToFileURL(process.argv[1]));
const paths = JSON.parse(readFileSync(0, 'utf8'));
global.gc();
const baseline = process.memoryUsage();
let maxHeap = baseline.heapUsed, maxExternal = baseline.external, maxWorking = 0;
const started = performance.now();
for (const path of paths) {
  global.gc();
  const raw = readFileSync(path);
  const root = /[/\\]0+\.json$/.test(path) ? 'InitializationResponse' : 'PlayerOperation';
  const value = decode(root, raw);
  if (value.cursor.sequence < 0) throw new Error('Invalid cursor');
  const memory = process.memoryUsage();
  maxHeap = Math.max(maxHeap, memory.heapUsed); maxExternal = Math.max(maxExternal, memory.external);
  maxWorking = Math.max(maxWorking, memory.heapUsed + memory.external - baseline.heapUsed - baseline.external);
}
global.gc();
console.log(JSON.stringify({records: paths.length, baseline_heap_bytes: baseline.heapUsed,
  peak_sampled_heap_bytes: maxHeap, peak_sampled_external_bytes: maxExternal,
  peak_sampled_working_delta_bytes: maxWorking, peak_process_rss_bytes: process.resourceUsage().maxRSS * 1024,
  within_128_mib: maxWorking <= 128 * 1024 * 1024, seconds_instrumented: (performance.now() - started) / 1000,
  scope: 'SDK read/decode/schema validation; sample after every decode, collect between records; no reducer/history; RSS includes imports'}));
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--typescript-sdk', type=Path, default=Path('sdk/player-typescript/dist/index.js'))
    parser.add_argument('--memory', action='store_true')
    args = parser.parse_args()
    directories = sorted({path.parent for root in args.inputs for path in root.rglob('result.json')})
    result: dict[str, Any] = {'protocol': sdk.IDENTITY, 'streams': [], 'failures': []}
    for directory in directories:
        try:
            report = replay_stream(directory)
            result['streams'].append(report)
            print(json.dumps({'stream': str(directory), 'records': report['records'], 'terminal': True}), flush=True)
        except (ValueError, KeyError, sdk.ProtocolError) as error:
            result['failures'].append({'directory': str(directory), 'error': str(error)})
            print(json.dumps(result['failures'][-1]), flush=True)
    comparisons = []
    by_directory = {row['directory']: row for row in result['streams']}
    for path, swapped in by_directory.items():
        directory = Path(path)
        if not directory.parent.name.endswith('-swapped'):
            continue
        original_path = str(directory.parent.parent / directory.parent.name.removesuffix('-swapped') / directory.name)
        original = by_directory.get(original_path)
        if original is None:
            continue
        compared_fields = ('records', 'commands', 'final_sequence', 'reducer_cursor', 'facts', 'catalog_entries', 'combat_log_text_sha256')
        equal = all(original[key] == swapped[key] for key in compared_fields)
        actors = lambda row: [{key: value for key, value in actor.items() if key != 'uuid'} for actor in row['actors']]
        comparisons.append({'original': original_path, 'swapped': path, 'same_permitted_outcome_and_log': equal and actors(original) == actors(swapped),
            'scope': 'Per-seat final actor values, fact/log counts, original log text and own command/operation counts; opaque identities excluded'})
    result['language_swap_comparisons'] = comparisons
    if args.memory:
        paths = [path for directory in directories for path in records(directory)]
        result['python_decode_memory'] = python_decode_memory(paths)
        process = subprocess.run(['node', '--expose-gc', '--input-type=module', '-e', NODE_MEMORY,
            str(args.typescript_sdk.resolve())], input=json.dumps([str(path.resolve()) for path in paths]),
            text=True, capture_output=True, check=True)
        result['typescript_decode_memory'] = json.loads(process.stdout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    require(bool(directories) and not result['failures'], 'One or more recorded streams failed cold replay')
    if args.memory:
        require(result['python_decode_memory']['within_128_mib'] and result['typescript_decode_memory']['within_128_mib'], 'Decoded working budget exceeded')


if __name__ == '__main__':
    main()
