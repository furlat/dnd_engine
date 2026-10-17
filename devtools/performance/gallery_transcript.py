"""Deterministic transcript of Gallery Crowd operations, and its comparison across two source trees.

record: run one `gallery_crowd.py` case from a source tree with deterministic identities and dice, and write,
per measured operation, every stored event version (fields, identity and location grants, handler
presentations, combat log), the encounter combat-log slice and every seat's published update (its exact
encoded JSON). Identities come from a seeded generator, dice faces from a dedicated seeded generator (so a
change in other random draws cannot move a die), and the process hash seed must be fixed by the caller.

    PYTHONHASHSEED=0 PYTHONPATH=<tree> python devtools/performance/gallery_transcript.py record <tree> <out.json> \
        --case fireball --mode ordinary --name <stem>

compare: report whether two recordings are equal after uuid (first appearance) and timestamp
normalization, after projecting both onto a named representation. Published seat updates are compared
byte for byte after uuid normalization. The engine on PYTHONPATH is imported but not run.

    PYTHONPATH=<tree> python devtools/performance/gallery_transcript.py compare <base.json> <new.json> \
        [--representation value-read]

The `value-read` representation (value read context as data, PR 2026-10-17) drops the d20, attack and
contest bonus fields that became evaluated readings, drops the per-value target, context and imported
channels from value dumps, moves a damage bonus's context onto its damage packet, and drops the target of
damage and healing rolls (now the packet's target, formerly the bonus value's own target).
"""

import argparse
import importlib.util
import json
import random
import re
import sys
import uuid
from pathlib import Path

# Identities and dice are fixed before the engine is imported: identities from a seeded generator, die faces from
# a dedicated one (`dnd.core.dice` draws faces through `random.randint`), other draws from the seeded module RNG.
_IDENTITIES = random.Random(20261017)
uuid.uuid4 = lambda: uuid.UUID(int=_IDENTITIES.getrandbits(128), version=4)
random.seed(4242)
random.randint = random.Random(17).randint

from dnd.core.events import EventQueue  # noqa: E402  (after the deterministic patches above)
from dnd.encounter import Encounter  # noqa: E402

UUID_PATTERN = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
TIME_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
READING_FIELDS = ('bonus', 'attack_bonus', 'ac', 'shover_athletics', 'target_ac')
VALUE_STATE_FIELDS = ('from_target_static', 'from_target_contextual', 'target_entity_uuid', 'target_entity_name',
                      'context')
CHANNEL_STATE_FIELDS = ('target_entity_uuid', 'target_entity_name', 'context')
CHANNELS = ('self_static', 'to_target_static', 'self_contextual', 'to_target_contextual')


def record(tree: Path, out: Path) -> None:
    spec = importlib.util.spec_from_file_location('gallery_crowd', tree / 'devtools' / 'performance' / 'gallery_crowd.py')
    gallery = importlib.util.module_from_spec(spec)
    sys.modules['gallery_crowd'] = gallery
    spec.loader.exec_module(gallery)

    def dump_event(event):
        row = {'cls': type(event).__name__,
               'fields': event.model_dump(mode='json', exclude={'combat_log'}),
               'identified': {str(k): sorted(map(str, v)) for k, v in event.identified_entity_observer_uuids.items()},
               'located': {str(k): sorted(map(str, v)) for k, v in event.located_entity_observer_uuids.items()},
               'located_pos': {str(k): sorted(map(str, v)) for k, v in event.located_position_observer_uuids.items()},
               'presentations': [presentation.model_dump(mode='json')
                                 for presentation in event.effective_handler_presentations]}
        if event.combat_log is not None:
            row['log'] = event.combat_log.model_dump(mode='json')
        return row

    operations = []
    published = []
    capture = gallery.application.capture_application_operation

    def captured(*args, **kwargs):
        updates = capture(*args, **kwargs)
        published.append({str(seat): update.model_dump_json() for seat, update in
                          sorted(updates.items(), key=lambda item: str(item[0]))})
        return updates

    gallery.application.capture_application_operation = captured
    run = gallery.Measurement.run

    def measured(self, operation):
        start = EventQueue.event_cursor()
        encounter = Encounter.get_active()
        log_start = len(encounter.combat_log) if encounter else 0
        published.clear()
        try:
            return run(self, operation)
        finally:
            encounter = Encounter.get_active()
            operations.append({
                'versions': EventQueue.event_cursor() - start,
                'events': [dump_event(event) for _, event in EventQueue.iter_events_since(start)],
                'combat_log': [entry.model_dump(mode='json') for entry in
                               (encounter.combat_log[log_start:] if encounter else [])],
                'published': list(published),
            })

    gallery.Measurement.run = measured
    try:
        gallery.entry()
    finally:
        out.write_text(json.dumps(operations, sort_keys=True, default=str))
        print(f"TRANSCRIPT {out} operations={len(operations)} versions={[op['versions'] for op in operations]}",
              file=sys.stderr)


def _clean(value):
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items() if key != 'timestamp'}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, str) and TIME_PATTERN.match(value):
        return '<time>'
    return value


def _project_value_read(value):
    """Both sides onto the value-read representation."""
    if isinstance(value, list):
        return [_project_value_read(item) for item in value]
    if not isinstance(value, dict):
        return value
    projected = {}
    is_value = 'self_static' in value and 'to_target_static' in value
    is_damage = 'damage_dice' in value and 'damage_bonus' in value
    is_packet_roll = 'roll_uuid' in value and value.get('roll_type') in ('Damage', 'Heal')
    for key, item in value.items():
        if is_packet_roll and key == 'target_entity_uuid':
            continue
        if key in READING_FIELDS and isinstance(item, dict):
            continue
        if is_value and key in VALUE_STATE_FIELDS:
            continue
        if is_value and key in CHANNELS and isinstance(item, dict):
            projected[key] = {k: _project_value_read(v) for k, v in item.items() if k not in CHANNEL_STATE_FIELDS}
            continue
        projected[key] = _project_value_read(item)
    if is_damage and projected.get('context') is None and isinstance(value.get('damage_bonus'), dict):
        projected['context'] = value['damage_bonus'].get('context')
    return projected


def _normalized(text: str) -> str:
    names: dict[str, str] = {}
    return UUID_PATTERN.sub(lambda match: names.setdefault(match.group(0), f'U{len(names)}'), text)


def _first_differences(a, b, path='', limit=12, found=None):
    found = [] if found is None else found
    if len(found) >= limit:
        return found
    if type(a) is not type(b):
        found.append((path, a, b))
    elif isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                found.append((f'{path}.{key}', a.get(key, '<absent>'), b.get(key, '<absent>')))
            else:
                _first_differences(a[key], b[key], f'{path}.{key}', limit, found)
    elif isinstance(a, list):
        if len(a) != len(b):
            found.append((f'{path}[len]', len(a), len(b)))
        for index, (left, right) in enumerate(zip(a, b)):
            _first_differences(left, right, f'{path}[{index}]', limit, found)
    elif a != b:
        found.append((path, a, b))
    return found


def compare(base_path: Path, new_path: Path, representation: str | None) -> int:
    loaded = []
    for path in (base_path, new_path):
        operations = json.loads(path.read_text())
        published = [[{seat: update for seat, update in seats.items()} for seats in op.pop('published')]
                     for op in operations]
        body = _clean(operations)
        if representation == 'value-read':
            body = _project_value_read(body)
        loaded.append((json.loads(_normalized(json.dumps(body, sort_keys=True))),
                       [[{seat: _normalized(update) for seat, update in seats.items()} for seats in op]
                        for op in published]))
    (base, base_published), (new, new_published) = loaded
    differences = _first_differences(base, new)
    published_equal = base_published == new_published
    for path, left, right in differences:
        print(f'DIFF {path}\n  base: {str(left)[:300]}\n  new:  {str(right)[:300]}')
    print(f"COMPARE events/logs {'identical' if not differences else 'DIFFERENT'}; "
          f"published updates {'byte-identical' if published_equal else 'DIFFERENT'}")
    return 0 if not differences and published_equal else 1


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == 'record':
        tree, out = Path(sys.argv[2]).resolve(), Path(sys.argv[3])
        del sys.argv[1:4]
        record(tree, out)
        return
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('compare',))
    parser.add_argument('base', type=Path)
    parser.add_argument('new', type=Path)
    parser.add_argument('--representation', choices=('value-read',), default=None)
    args = parser.parse_args()
    sys.exit(compare(args.base, args.new, args.representation))


if __name__ == '__main__':
    main()
