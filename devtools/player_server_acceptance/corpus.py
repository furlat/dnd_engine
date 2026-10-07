"""Exercise every exported fact family using existing native scenarios, without drawing.

This is a serialization/cold-reduction corpus, separate from the SDK gameplay lane.
No images, new spells, alternative rules, or test-only server endpoints are involved.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from types import UnionType
from typing import Annotated, Union, get_args, get_origin

from jsonschema import Draft202012Validator
from pydantic import TypeAdapter

from devtools.animation_review.cases import load_cases
from devtools.animation_review.produce import produce
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.player.facts import PlayerFact, PlayerState
from dnd.player.recorded import RecordedSequence, project_sequence
from dnd.player.reduction import decode_player_sequence, encode_player_sequence, reduce_initialization, reduce_lineage
from player_server.protocol import public_schema

CASES = ('conceal-greater-invisibility', 'support-cure-wounds', 'device-break-fireball',
    'spell-web-mage', 'spell-web-cannon', 'shove-success', 'shove-spikes-lethal',
    'equipment-melee-to-ranged', 'death-save-success', 'mechanism-darts',
    'portal-hatch-walk', 'pending-false-life-depletion', 'summoning-fey-jaguar')
STATE = TypeAdapter(PlayerState)


def fact_names(owner):
    if get_origin(owner) is Annotated:
        return fact_names(get_args(owner)[0])
    if get_origin(owner) in (UnionType, Union):
        return set().union(*(fact_names(member) for member in get_args(owner)))
    return {owner.__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    cases = {case.id: case for case in load_cases()}
    schema = public_schema()
    validators = {name: Draft202012Validator({'$defs': schema['$defs'], '$ref': '#/$defs/' + name})
        for name in ('PlayerInitialization', 'PlayerLineage')}
    expected = fact_names(PlayerFact)
    observed = Counter()
    rows = []
    started = perf_counter()
    for name in CASES:
        begun = perf_counter()
        history = produce(cases[name])
        views = history.views or {'source': RecordedSequence(initialization=history.initialization, lineages=history.lineages)}
        row = {'case': name, 'views': []}
        for role, native in views.items():
            sequence = project_sequence(native)
            raw = encode_player_sequence(sequence)
            payload = json.loads(raw)
            validators['PlayerInitialization'].validate(payload['initialization'])
            for lineage in payload['lineages']:
                validators['PlayerLineage'].validate(lineage)
            warm = reduce_initialization(sequence.initialization)
            cold, lineages = decode_player_sequence(raw)
            for group in (sequence.initialization, *sequence.lineages):
                for node in group.nodes if group is sequence.initialization else group.events:
                    if node.fact is not None:
                        observed[type(node.fact).__name__] += 1
            for lineage in sequence.lineages:
                warm = reduce_lineage(warm, lineage)
            for lineage in lineages:
                cold = reduce_lineage(cold, lineage)
            if STATE.dump_python(warm) != STATE.dump_python(cold):
                raise AssertionError(f'{name}/{role}: cold state differs from in-memory public state')
            (args.output / f'{name}--{role}.json').write_bytes(raw)
            row['views'].append({'role': role, 'bytes': len(raw), 'sha256': sha256(raw).hexdigest(),
                'lineages': len(lineages), 'final_cursor': cold.reducer_cursor})
        row['seconds'] = perf_counter() - begun
        rows.append(row)
        print(name, 'passed', round(row['seconds'], 3), flush=True)
    report = {'schema_digest': sha256(json.dumps(schema, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'scope': 'Native fixtures -> production projection -> exported schema -> JSON -> shared cold reducer; no HTTP or graphics claim',
        'cases': rows, 'fact_counts': dict(sorted(observed.items())), 'missing_facts': sorted(expected - observed.keys()),
        'seconds': perf_counter() - started}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['missing_facts']:
        raise AssertionError(f"Unexercised exported facts: {report['missing_facts']}")
    print('PASS', len(rows), 'cases', len(observed), 'fact families', flush=True)


if __name__ == '__main__':
    main()
