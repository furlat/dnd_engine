"""Deterministic transcript of Gallery Crowd operations, and its comparison across two source trees.

record: run one `gallery_crowd.py` case from a source tree with deterministic identities and dice, and write,
per measured operation, every stored event version (fields, identity and location grants, handler
presentations, combat log), the encounter combat-log slice and every seat's published update (its exact
encoded JSON). Identities come from a seeded generator, dice faces from a dedicated seeded generator (so a
change in other random draws cannot move a die), and the process hash seed must be fixed by the caller.
Identities the value layer mints (in dnd/core/values.py) come from a third generator: the engine orders
entities, items and conditions by identity, so a change in how many identities values mint must not move them.
Identities drawn by the standard action templates added after the E0 baselines (60adf05eb) come from a fourth
(`_POST_BASELINE_TEMPLATES`): every creature registers them, so their draws would move every later identity.

    PYTHONHASHSEED=0 PYTHONPATH=<tree> python devtools/performance/gallery_transcript.py record <tree> <out.json> \
        --case fireball --mode ordinary --name <stem> [--seats faction|character|batch:N]

Every argument after the output path goes to the tree's own `gallery_crowd.py`, including its seat layout
(`--seats`, default `faction`): record both trees of a comparison with the same layout. With `--oracle DIR` the
recording is also the oracle run whose O3 views later runs compare against: its identities repeat across runs. A tree whose harness
predates the layouts (before E0 of the event-native publication plan) records `faction` and accepts no `--seats`.
Its harness also published none of its own world edits, so its first operation's published updates differ from a
later harness's even where the engine is identical; compare such trees on events and logs only.

compare: report whether two recordings are equal after uuid (first appearance, in the engine's own order:
dicts keep their insertion order, so identities the engine keys by never sort by their raw values) and timestamp
normalization, after projecting both onto a named representation. Published seat updates are compared
byte for byte after uuid normalization. The engine on PYTHONPATH is imported but not run.

    PYTHONPATH=<tree> python devtools/performance/gallery_transcript.py compare <base.json> <new.json> \
        [--representation value-read|value-record|world-16]

The `value-read` representation (value read context as data, PR 2026-10-17) projects the d20, attack and
contest bonus fields that became evaluated readings onto their normalized score, advantage, critical and
auto-hit states, drops the per-value target, context and imported channels from value dumps, and moves a
damage bonus's context onto its damage packet. It does not hide the target of damage packets and of damage
and healing rolls: those now carry the read's target where the base left the value's unset target (None).

The `value-record` representation (value layer as data, PH-2 2026-10-18) projects every value dump (the old
channel graph, a value record, or a composed read in a damage or healing packet) onto the read it gives with no
target or context: name, owner, score, normalized score, advantage, critical and auto-hit states. Block dumps
lose their `values` dict: a block's values are its value fields (still dumped, and named by `values_dict_*`).

The `world-16` representation (the schema-16 world wire, E3-world 2026-10-18) drops every lineage's
`world_updates` from both sides' published seat updates before their uuid normalization; the rest of each update
(nodes, occurrence numbering, version rows, bodies, sensory rows, HUD, combat log, content) must stay equal.
"""

import argparse
import importlib.util
import json
import os
import random
import re
import sys
import uuid
from pathlib import Path

# Identities and dice are fixed before the engine is imported: identities from a seeded generator, die faces from
# a dedicated one (`dnd.core.dice` draws faces through `random.randint`), other draws from the seeded module RNG.
_IDENTITIES = random.Random(20261017)
_VALUE_IDENTITIES = random.Random(20261018)
_ORACLE_IDENTITIES = random.Random(20261019)
_TEMPLATE_IDENTITIES = random.Random(20261020)
_ORACLE = 'devtools/performance/seat_oracle.py'
# Standard action templates every creature registers that the E0 baseline recordings (60adf05eb) predate, by class
# name: the NPC lane's Help Attack (SRD Help, aiding an ally's attack), 2026-10-18.
_POST_BASELINE_TEMPLATES = frozenset({'HelpAttack'})


def _identity() -> uuid.UUID:
    """A seeded identity; those the value layer mints (in dnd/core/values.py, directly or through a pydantic
    default factory) come from their own generator, so a change in how many identities values mint does not
    shift entity, item or event identities, which the engine orders by. Identities minted while the seat oracle
    reads the live engine (`--oracle`: an unpublished birth fact per perceived body) come from a third one, so
    an oracle run keeps the engine identities of a run without it. Identities drawn while a post-baseline standard
    template is constructed (pydantic's __init__ of a `_POST_BASELINE_TEMPLATES` instance) come from a fourth, so
    adding such a template to every creature keeps the baseline's entity, item and event identities."""
    frame = sys._getframe(1)
    caller = frame
    while caller is not None:
        if caller.f_code.co_filename.endswith(_ORACLE):
            return uuid.UUID(int=_ORACLE_IDENTITIES.getrandbits(128), version=4)
        if (caller.f_code.co_name == '__init__' and '/pydantic' in caller.f_code.co_filename
                and type(caller.f_locals.get('self')).__name__ in _POST_BASELINE_TEMPLATES):
            return uuid.UUID(int=_TEMPLATE_IDENTITIES.getrandbits(128), version=4)
        caller = caller.f_back
    while frame is not None and '/pydantic' in frame.f_code.co_filename:
        frame = frame.f_back
    minted_by_values = frame is not None and frame.f_code.co_filename.endswith('dnd/core/values.py')
    generator = _VALUE_IDENTITIES if minted_by_values else _IDENTITIES
    return uuid.UUID(int=generator.getrandbits(128), version=4)


uuid.uuid4 = _identity
random.seed(4242)
random.randint = random.Random(17).randint

from pydantic import TypeAdapter  # noqa: E402
from dnd.core.content.runtime import EffectiveHandlerPresentation  # noqa: E402  (after the deterministic patches above)
from dnd.core.events import EventQueue  # noqa: E402
from dnd.encounter import Encounter  # noqa: E402

UUID_PATTERN = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
TIME_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
READING_FIELDS = ('bonus', 'attack_bonus', 'ac', 'shover_athletics', 'target_ac')
READING_PROJECTION = ('normalized_score', 'advantage', 'critical', 'auto_hit')
VALUE_STATE_FIELDS = ('from_target_static', 'from_target_contextual', 'target_entity_uuid', 'target_entity_name',
                      'context')
CHANNEL_STATE_FIELDS = ('target_entity_uuid', 'target_entity_name', 'context')
CHANNELS = ('self_static', 'to_target_static', 'self_contextual', 'to_target_contextual')
# Handler presentations are frozen dataclasses, not models: one adapter dumps them.
PRESENTATIONS = TypeAdapter(tuple[EffectiveHandlerPresentation, ...])


def record(tree: Path, out: Path) -> None:
    spec = importlib.util.spec_from_file_location('gallery_crowd', tree / 'devtools' / 'performance' / 'gallery_crowd.py')
    gallery = importlib.util.module_from_spec(spec)
    sys.modules['gallery_crowd'] = gallery
    spec.loader.exec_module(gallery)

    def dump_event(event):
        # Child links live in the queue's lineage index (P7b), not in the frozen stored version.
        children, lineage_children = EventQueue.child_links(event)
        fields = event.model_dump(mode='json', exclude={'combat_log'})
        fields.update(children_events=[str(identity) for identity in children],
                      lineage_children_events=[str(identity) for identity in lineage_children])
        row = {'cls': type(event).__name__,
               'fields': fields,
               'identified': {str(k): sorted(map(str, v)) for k, v in event.identified_entity_observer_uuids.items()},
               'located': {str(k): sorted(map(str, v)) for k, v in event.located_entity_observer_uuids.items()},
               'located_pos': {str(k): sorted(map(str, v)) for k, v in event.located_position_observer_uuids.items()},
               'presentations': PRESENTATIONS.dump_python(event.effective_handler_presentations, mode='json')}
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
    # Requests (choices, AI advances) publish through the worker, which bound the function by name.
    gallery.worker.capture_application_operation = captured
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
    os.environ['GALLERY_IDENTITIES'] = 'seeded'  # an oracle run's manifest: its identities repeat across recordings
    try:
        gallery.entry()
    finally:
        out.write_text(json.dumps(operations, default=str))
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
    for key, item in value.items():
        if key in READING_FIELDS and isinstance(item, dict):
            projected[key] = {field: item.get(field) for field in READING_PROJECTION}
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


VALUE_RECORD_FIELDS = ('name', 'source_entity_uuid', 'score', 'normalized_score', 'advantage', 'critical', 'auto_hit')


def _project_value_record(value):
    """Both sides onto the value-record representation: a value (an old channel graph dump, a record or a
    composed read) becomes the read it gives with no target or context."""
    if isinstance(value, list):
        return [_project_value_record(item) for item in value]
    if not isinstance(value, dict):
        return value
    if ('self_static' in value and 'to_target_static' in value) or (
            'normalized_score' in value and ('parts' in value or 'modifiers' in value)):
        return {field: value.get(field) for field in VALUE_RECORD_FIELDS}
    block = 'values_dict_uuid_name' in value
    return {key: _project_value_record(item) for key, item in value.items() if not (block and key == 'values')}


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


def _without_world_updates(update: str) -> str:
    """A published seat update without its lineages' world updates (`world-16`)."""
    value = json.loads(update)
    for lineage in value.get('lineages', ()):
        lineage.pop('world_updates', None)
    return json.dumps(value)


def compare(base_path: Path, new_path: Path, representation: str | None) -> int:
    loaded = []
    for path in (base_path, new_path):
        operations = json.loads(path.read_text())
        published = [[{seat: update for seat, update in seats.items()} for seats in op.pop('published')]
                     for op in operations]
        body = _clean(operations)
        if representation == 'value-read':
            body = _project_value_read(body)
        elif representation == 'value-record':
            body = _project_value_record(body)
        if representation == 'world-16':
            published = [[{seat: _without_world_updates(update) for seat, update in seats.items()} for seats in op]
                         for op in published]
        loaded.append((json.loads(_normalized(json.dumps(body))),
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
    parser.add_argument('--representation', choices=('value-read', 'value-record', 'world-16'), default=None)
    args = parser.parse_args()
    sys.exit(compare(args.base, args.new, args.representation))


if __name__ == '__main__':
    main()
