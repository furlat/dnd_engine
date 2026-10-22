"""Repeatable summon ownership measurements at the real serial worker boundary.

Setup and an excluded warmup precede each case's fresh-scene samples. Native
phase hooks run only in a separate diagnostic sample. The capture clock wraps
and forwards the production capture function unchanged; no events or senses
are disabled. Run before/after with the same arguments, checkout and runtime.
"""
from dataclasses import replace
import argparse
import gc
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter
from uuid import uuid4

from dnd.action_timing import (reset_action_count_recorder, reset_action_timing_recorder,
    set_action_count_recorder, set_action_timing_recorder)
from dnd.actions_functional import register_spell
from dnd.blocks.sensory import spatial_senses_system
from dnd.controller import ControllerExecutionMode
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EntityCreatedEvent, EventQueue, SensoryUpdateEvent, StepMovementEvent
from dnd.player.commands import ActionSelection
from dnd.player.session import close_session
from dnd.spells.summoning import ConjureAnimals, ConjureFey, SpiritualWeapon
from dnd.types.character_progression import CharacterClass, PreparedSpellSelection
from devtools.player_server_acceptance.fixtures import combat_configuration
from server import worker
from server.protocol import (ChoicesRequest, CommandRequest, EndTurnIntent,
    ExecuteSelectionIntent, PreviewRequest)
from server.worker_protocol import Advance, Choices, Command, Preview, Start
from tests.progression.prepared_class_support import prepared_build


SPELLS = {
    'animals': ('spell.conjure_animals', 3, (('form', 'wolf'),)),
    'fey': ('spell.conjure_fey', 6, (('form', 'wolf'),)),
    'dragon': ('spell.summon_dragon', 5, (('form', 'red'),)),
    'sphere': ('spell.flaming_sphere', 2, (('form', 'flaming_sphere'),)),
    'planar': ('spell.planar_ally', 6, (('form', 'deva'),)),
    'weapon': ('spell.spiritual_weapon', 2, (('form', 'spiritual_weapon'),)),
    'elemental': ('spell.conjure_elemental', 5, (('form', 'fire_elemental'),)),
}
CASES = ('ordinary', 'animals', 'fey', 'dragon', 'sphere', 'planar', 'multiple', 'split_animals', 'crowded_fireball')


def owner(runtime):
    return next((seat, row) for seat, row in runtime.publications.items()
        if row.boundary.input_actor_uuid is not None)


def end_request(runtime):
    seat, publication = owner(runtime)
    return Command(seat_id=seat, request=CommandRequest(command_number=1,
        actor_uuid=publication.boundary.input_actor_uuid, state_revision=publication.state_revision,
        intent=EndTurnIntent()))


def await_actor(runtime, identity=None):
    for _ in range(180):
        if worker.needs_advance(runtime.session):
            worker.dispatch(runtime, Advance())
            continue
        seat, publication = owner(runtime)
        if identity is None or publication.boundary.input_actor_uuid == identity:
            return seat, publication
        worker.dispatch(runtime, end_request(runtime))
    raise RuntimeError('Actor did not reach an external input boundary')


def build(class_id, spells):
    result = replace(prepared_build(class_id, 11), name=f'Benchmark {class_id.value}', faction='heroes',
        prepared_spells=(PreparedSpellSelection(f'{class_id.value}.spellcasting', tuple(spells)),))
    return replace(result, scribed_spell_ids=tuple(spells)) if class_id is CharacterClass.WIZARD else result


def create(case):
    if case in ('split_animals', 'crowded_fireball'):
        config = combat_configuration('conjure_animals' if case == 'split_animals' else 'fireball_six_goblins', Path('/unused'), seed=2)
        runtime, _, _ = worker.start(Start(game_id='summon-control-timings', game_epoch=uuid4(),
            audience_ids={seat.seat_id: uuid4() for seat in config.assignments}, encounter_id=None,
            recipe=config.recipe, assignments=config.assignments, test_seed=2))
    else:
        wizard = build(CharacterClass.WIZARD, ('spell.summon_dragon', 'spell.flaming_sphere', 'spell.conjure_elemental', 'spell.fireball'))
        cleric = build(CharacterClass.CLERIC, ('spell.planar_ally', 'spell.healing_word'))
        runtime, _, _ = worker.start(Start(game_id='summon-control-timings', game_epoch=uuid4(),
            audience_ids={'party': uuid4()}, encounter_id=None, recipe=None, assignments=None,
            test_seed=2, player_builds=(wizard, cleric)))
        if case in ('animals', 'fey', 'multiple'):
            register_spell(runtime.session.game.entities[runtime.session.player_uuids[0]],
                ConjureAnimals if case == 'animals' else SpiritualWeapon if case == 'multiple' else ConjureFey, caster_level=11)
    desired = runtime.session.player_uuids[1 if case == 'planar' else 0]
    await_actor(runtime, desired)
    return runtime


def population(runtime):
    return {'retained_native_entities': len(runtime.session.game.entities),
        'registered_native_observers': len(spatial_senses_system.senses_by_observer),
        'summons': len(runtime.session.summoning.memberships),
        'seats': {seat: {'controlled': len(audience.controlled), 'observers': len(audience.observers)}
            for seat, audience in runtime.session.seats.items()}}


def measure(runtime, request):
    before = EventQueue.event_cursor()
    capture_ms = 0.0
    original_capture = worker.capture_application_operation

    def timed_capture(*args, **kwargs):
        nonlocal capture_ms
        started = perf_counter()
        result = original_capture(*args, **kwargs)
        capture_ms += (perf_counter() - started) * 1000
        return result

    worker.capture_application_operation = timed_capture
    started = perf_counter()
    try:
        reply, records, response = worker.dispatch(runtime, request)
    finally:
        elapsed = (perf_counter() - started) * 1000
        worker.capture_application_operation = original_capture
    if reply.rejection is not None:
        raise RuntimeError(f'Rejected benchmark operation: {reply.rejection}')
    started = perf_counter()
    encoded = [reply.model_dump_json().encode(), *(record.model_dump_json().encode() for record in records)]
    if response is not None:
        encoded.append(worker.response_bytes(runtime.session, response))
    encode_ms = (perf_counter() - started) * 1000
    result = {'kind': request.kind, 'dispatch_ms': elapsed, 'capture_ms': capture_ms,
        'native_and_dispatch_other_ms': elapsed - capture_ms, 'encode_ms': encode_ms,
        'total_execution_ms': elapsed + encode_ms, 'events': EventQueue.event_cursor() - before,
        'public_records': len(records), 'bytes': sum(map(len, encoded)), 'largest_packet_bytes': max(map(len, encoded)),
        'birth_events': 0, 'movement_step_events': 0, 'sensory_events': 0, 'sensory_observers_updated': 0}
    observers = set()
    for _, event in EventQueue.iter_events_since(before):
        if isinstance(event, EntityCreatedEvent):
            result['birth_events'] += 1
        if isinstance(event, StepMovementEvent):
            result['movement_step_events'] += 1
        if isinstance(event, SensoryUpdateEvent):
            result['sensory_events'] += 1
            observers.add(event.observer_uuid)
    result['sensory_observers_updated'] = len(observers)
    del reply, records, encoded
    started = perf_counter()
    collected, cycles = worker.collect_between_requests()
    result['post_reply_gc_ms'] = (perf_counter() - started) * 1000
    result['collected_cycle_objects'] = collected
    result['cycle_types'] = dict(cycles)
    return response, result


def discover(runtime):
    seat, publication = owner(runtime)
    response, timing = measure(runtime, Choices(seat_id=seat, request=ChoicesRequest(
        actor_uuid=publication.boundary.input_actor_uuid, state_revision=publication.state_revision,
        force_attack=False, correlation_id=uuid4())))
    return response.choices, timing


def choose(choices, behavior, level=None, facets=(), position=None, target=None):
    rows = choices.entity_actions + choices.position_actions + choices.self_actions + choices.object_actions
    candidates = [row for row in rows if row.behavior_id == behavior and row.can_afford
        and (level is None or row.cast_at_level in (None, level))
        and all(any(facet.key == key and facet.value == value for facet in row.variant_facets) for key, value in facets)]
    if not candidates:
        raise RuntimeError(f'No offered affordable {behavior} level={level} facets={facets}; offered={[ (r.behavior_id, r.cast_at_level, r.variant_facets) for r in rows if r.behavior_id == behavior ]}')
    row = candidates[0]
    bindings = choices.target_sets[row.target_set]
    extra = ()
    if position is not None:
        matching = [binding for binding in bindings if binding.position is not None and choices.positions[binding.position] == position]
        selected = (matching[0].index,) if matching else ()
        extra = () if matching else (position,)
    elif target is not None:
        selected = (next(binding.index for binding in bindings if binding.kind == 'subject' and choices.subjects[binding.subject].uuid == target),)
    else:
        selected = (bindings[0].index,)
    return ActionSelection(action_index=row.discovery_index, target_indices=selected, extra_target_positions=extra, cast_at_level=level)


def execute(runtime, choices, selection):
    seat, publication = owner(runtime)
    common = dict(actor_uuid=publication.boundary.input_actor_uuid, state_revision=publication.state_revision)
    _, preview = measure(runtime, Preview(seat_id=seat, request=PreviewRequest(**common,
        discovery_generation=choices.discovery_generation, selection=selection, correlation_id=uuid4())))
    _, command = measure(runtime, Command(seat_id=seat, request=CommandRequest(**common, command_number=1,
        intent=ExecuteSelectionIntent(discovery_generation=choices.discovery_generation, selection=selection))))
    return preview, command


def cast(runtime, name, position):
    choices, discovery = discover(runtime)
    behavior, level, facets = SPELLS[name]
    preview, command = execute(runtime, choices, choose(choices, behavior, level, facets, position))
    return {'choices': discovery, 'preview': preview, 'cast': command}


def first_summon_step(runtime, summon_ids):
    entry_steps = []

    def advance(request):
        actor = runtime.session.encounter.get_current_entity()
        _, timing = measure(runtime, request)
        timing['actor_is_summon'] = actor is not None and actor.uuid in summon_ids
        entry_steps.append(timing)

    advance(end_request(runtime))
    for _ in range(180):
        actor = runtime.session.encounter.get_current_entity()
        if actor is not None and actor.uuid in summon_ids:
            controller = runtime.session.encounter.get_controller_for(actor.uuid)
            if controller.execution_mode is not ControllerExecutionMode.EXTERNAL:
                _, result = measure(runtime, Advance())
                result['support'] = 'native_automatic_step'
                result['entry_steps'] = entry_steps
                return result
            while worker.needs_advance(runtime.session):
                advance(Advance())
            choices, discovery = discover(runtime)
            origin = actor.position
            destination = min((position for position in choices.positions if position != origin),
                key=lambda position: abs(position[0] - origin[0]) + abs(position[1] - origin[1]))
            selection = choose(choices, 'action.move', position=destination)
            # Identical discovery/preview queries exercise their existing cached path.
            _, cached_discovery = discover(runtime)
            seat, publication = owner(runtime)
            _, preview = measure(runtime, Preview(seat_id=seat, request=PreviewRequest(
                actor_uuid=actor.uuid, state_revision=publication.state_revision,
                discovery_generation=choices.discovery_generation, selection=selection, correlation_id=uuid4())))
            cached_preview, movement = execute(runtime, choices, selection)
            repeated = []
            for _ in range(2):
                following, discovery_again = discover(runtime)
                origin = actor.position
                destination = min((position for position in following.positions if position != origin),
                    key=lambda position: abs(position[0] - origin[0]) + abs(position[1] - origin[1]))
                preview_again, movement_again = execute(runtime, following,
                    choose(following, 'action.move', position=destination))
                repeated.append({'choices': discovery_again, 'preview': preview_again, 'movement': movement_again})
            return {'support': 'external_input', 'entry_steps': entry_steps,
                'entry_total_ms': sum(row['total_execution_ms'] for row in entry_steps),
                'entry_max_ms': max(row['total_execution_ms'] for row in entry_steps),
                'choices': discovery, 'cached_choices': cached_discovery, 'preview': preview,
                'cached_preview': cached_preview, 'movement': movement, 'repeated': repeated}
        if worker.needs_advance(runtime.session):
            advance(Advance())
        else:
            advance(end_request(runtime))
    raise RuntimeError('Summon did not receive a turn')


def run_case(case, diagnostic=False):
    started = perf_counter()
    runtime = create(case)
    setup_ms = (perf_counter() - started) * 1000
    phases, counts = {}, {}
    timing_token = set_action_timing_recorder(lambda phase, start: phases.setdefault(phase, []).append((perf_counter() - start) * 1000)) if diagnostic else None
    count_token = set_action_count_recorder(lambda key, value: counts.__setitem__(key, counts.get(key, 0) + value)) if diagnostic else None
    result = {'setup_ms_excluded': setup_ms, 'before': population(runtime), 'operations': {}}
    try:
        worker.collect_between_requests()
        with fixed_dice_faces(*([2] * 4000)):
            if case == 'ordinary':
                choices, result['operations']['choices'] = discover(runtime)
                selection = choose(choices, 'action.move')
                preview, command = execute(runtime, choices, selection)
                result['operations'].update(preview=preview, movement=command)
            elif case == 'crowded_fireball':
                choices, result['operations']['choices'] = discover(runtime)
                preview, command = execute(runtime, choices, choose(choices, 'spell.fireball', 3, position=(10, 7)))
                result['operations'].update(preview=preview, fireball=command)
            else:
                spell = 'animals' if case == 'split_animals' else 'sphere' if case == 'multiple' else case
                position = (7, 7) if case == 'split_animals' else (12, 10)
                result['operations'].update(cast(runtime, spell, position))
                if case == 'multiple':
                    result['operations'].update({f'second_{key}': value for key, value in cast(runtime, 'weapon', (12, 12)).items()})
                result['after_cast'] = population(runtime)
                summon_ids = tuple(runtime.session.summoning.memberships)
                if not summon_ids:
                    raise RuntimeError('Summon cast committed without a deployed summon')
                result['external_command'] = {'supported': any(audience.controls(summon_ids[-1]) for audience in runtime.session.seats.values()),
                    'measurement': 'Actual assigned controller; external movement runs only when the seat receives authority.'}
                if case in ('animals', 'dragon', 'split_animals', 'multiple'):
                    result['operations']['first_summon_turn'] = first_summon_step(runtime, summon_ids)
                elif case in ('fey', 'sphere'):
                    choices, result['operations']['release_choices'] = discover(runtime)
                    preview, command = execute(runtime, choices, choose(choices, 'action.drop_concentration'))
                    result['operations'].update(release_preview=preview, release=command)
                    if case == 'fey':
                        result['operations']['hostile_fey_turn'] = first_summon_step(runtime, summon_ids)
                elif case == 'planar':
                    caster = owner(runtime)[1].boundary.input_actor_uuid
                    worker.dispatch(runtime, end_request(runtime))
                    await_actor(runtime, caster)
                    choices, result['operations']['dismiss_choices'] = discover(runtime)
                    preview, command = execute(runtime, choices, choose(choices, 'action.summon.dismiss', target=summon_ids[0]))
                    result['operations'].update(dismiss_preview=preview, dismiss=command)
            result['after'] = population(runtime)
        if diagnostic:
            result['diagnostic_phases_ms'] = {key: {'calls': len(values), 'sum': sum(values), 'maximum': max(values)} for key, values in phases.items()}
            result['diagnostic_counts'] = counts
        return result
    finally:
        if timing_token is not None:
            reset_action_timing_recorder(timing_token)
            reset_action_count_recorder(count_token)
        close_session(runtime.session)
        del runtime
        gc.unfreeze()
        gc.collect()
        gc.freeze()


def summary(samples):
    result = {}
    for operation in samples[0]['operations']:
        rows = [sample['operations'][operation] for sample in samples]
        result[operation] = {}
        if rows[0].get('support') == 'external_input':
            result[operation] = summary([{'operations': {key: row[key] for key in ('choices', 'cached_choices', 'preview', 'cached_preview', 'movement')}} for row in rows])
            for key in ('entry_total_ms', 'entry_max_ms'):
                values = [row[key] for row in rows]
                result[operation][key] = {'median': statistics.median(values), 'minimum': min(values), 'maximum': max(values)}
            result[operation]['repeated'] = summary([{'operations': step} for row in rows for step in row['repeated']])
            continue
        for key in ('dispatch_ms', 'capture_ms', 'native_and_dispatch_other_ms', 'encode_ms', 'total_execution_ms', 'post_reply_gc_ms', 'events', 'bytes', 'sensory_events', 'sensory_observers_updated'):
            if key in rows[0]:
                values = [row[key] for row in rows]
                result[operation][key] = {'median': statistics.median(values), 'minimum': min(values), 'maximum': max(values)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--label', default='baseline')
    parser.add_argument('--case', choices=CASES, action='append')
    parser.add_argument('--no-diagnostic', action='store_true')
    args = parser.parse_args()
    gc.disable()
    gc.collect()
    gc.freeze()
    report = {'label': args.label, 'samples_per_case': args.samples, 'seed': 2,
        'environment': {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
            'source': str(Path(__file__).resolve().parents[2]), 'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()},
        'method': {'boundary': 'real Start, Choices, Preview, Command and Advance; canonical worker response encoding',
            'latency': 'one excluded fresh-scene warmup, then fresh-scene repetitions; no native timing/count hooks',
            'native_and_dispatch_other_ms': 'dispatch minus capture; includes authorization, operation publication and metadata; not a pure native CPU clock',
            'gc': 'worker automatic GC disabled, collect_between_requests after response encoding; response envelope may remain retained by the querying caller',
            'setup': 'excluded scene/character composition and advancement to designated caster',
            'builds': 'real level-11 creator Wizard and Cleric; Animals/Fey documented register_spell scenario grants because creator has no Druid/Warlock class; multiple scene also grants Spiritual Weapon to permit two paid casts in one caster turn without killing the small opposing party between casters; split and crowded use existing specialized level-7 generic_caster roster fixture',
            'dice': 'seed 2; measured scenario operations use fixed face 2',
            'native_observers': 'retained_native_entities counts native game registry entries, not living observer index membership; registered_native_observers is the actual spatial_senses_system observer table size; sensory_observers_updated counts actual emitted SensoryUpdateEvent observer UUIDs',
            'diagnostic': 'separate instrumented fresh scene; phase timings may nest and must not be summed as total'}, 'cases': {}}
    for case in args.case or CASES:
        print(f'{case}: warmup', flush=True)
        warmup = run_case(case)
        samples = []
        for number in range(args.samples):
            print(f'{case}: sample {number + 1}/{args.samples}', flush=True)
            samples.append(run_case(case))
        report['cases'][case] = {'warmup_excluded': warmup, 'samples': samples, 'summary': summary(samples)}
        if not args.no_diagnostic:
            print(f'{case}: diagnostic (excluded)', flush=True)
            report['cases'][case]['diagnostic_excluded'] = run_case(case, diagnostic=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Saved {args.output}', flush=True)


if __name__ == '__main__':
    main()
