"""Gallery Crowd (GC) stress fixture for the single-pass propagation plan (§1, §9.4).

The authored Lantern Gallery seed recipe (`gallery_crowd_seed_recipe.json`) is
extended to a crowd: a sorcerer and three allies at the west entry, a Fireball
cluster and an Ice Storm cluster of torch-carrying fighters, spread witnesses,
all hall wall torches lit and one oil barrel beside the Fireball cluster.

One case per fresh worker process (`server.worker.run_process`). Modes:

- ordinary: complete-operation timings only;
- counts: `dnd.action_timing` counters and inclusive phases (not timing-qualified);
- profile: cProfile plus counters (not timing-qualified).

Spell cases measure construct → native apply → operation → both-audience
publication → encoding. Choices cases measure the worker requests Choices
(miss, then hit), Preview and Command.
"""

import argparse
import cProfile
from collections import Counter
from functools import partial
import json
from pathlib import Path
import pstats
import sys
from time import perf_counter
from uuid import uuid4, uuid5

from dnd.action_timing import (reset_action_count_recorder, reset_action_timing_recorder,
    set_action_count_recorder, set_action_timing_recorder)
from dnd.actions import DropConcentration, Move
from dnd.content.items.environment_item_builders import build_oil_barrel
from dnd.core.base_block import BaseBlock
from dnd.core.content.encounters import (EncounterDeploymentSpec, EncounterDeploymentZone, EncounterRecipe,
    EncounterRosterMember, EncounterRosterRecipe, PremadeCharacterRosterSource, RosterSpellGrant,
    RosterStartingDamage)
from dnd.core.content.registration import get_content_declaration
from dnd.core.creature_types import DamageType
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.items.torches import WallTorch
from dnd.player import application, session
from dnd.player.commands import ActionSelection
from dnd.spells.catalog_content import SPELL_CATALOG_METADATA_BY_NAME, SPELL_CONTENT_IDENTITY_SPECS
from server import worker
from server.protocol import ChoicesRequest, CommandRequest, EndTurnIntent, ExecuteSelectionIntent, PreviewRequest
from server.worker_protocol import Advance, Choices, Command, Preview, Start


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEED = HERE / 'gallery_crowd_seed_recipe.json'
OUTPUT = ROOT / '.runtime' / 'single-pass' / 'gallery_crowd'
FIGHTER = 'hero.fighter_l5_shield_torch'
CASTER_NAME = 'Expedition sorcerer'  # the seed's amber member

CASTER = (26, 10)
ALLIES = ((25, 12), (25, 8), (26, 8))
FIREBALL_AIM = (42, 10)
NEAR_AIM = (38, 10)  # 60 ft from the caster: the cluster's west edge, inside 60-ft spell ranges
FIREBALL_CLUSTER = (*((x, 10) for x in range(38, 47)), (42, 11))
ICE_STORM_AIM = (58, 20)
ICE_STORM_CLUSTER = (*((x, 20) for x in range(56, 61)), (58, 21))
WITNESSES = tuple((x, y) for y in (20, 26) for x in (30, 34, 38, 46, 50))
OIL_BARREL = (44, 11)
# Fragile members carry starting damage so the blasts kill some and leave others standing.
FRAGILE_DAMAGE = 38
FRAGILE = frozenset((*FIREBALL_CLUSTER[:6], *ICE_STORM_CLUSTER[:4]))
# Wall torch mounts of the Lantern Gallery (battlefield_catalog._furnish_lantern_gallery).
WALL_TORCHES = (*((x, y) for x in (26, 34, 42, 50, 58, 66, 70) for y in (2, 37)),
    *((x, y) for x in (24, 71) for y in (10, 18, 26, 34)),
    *((x, y) for x in (41, 57) for y in (12, 28)))
GODMODE_SPECS = tuple(spec for spec in SPELL_CONTENT_IDENTITY_SPECS
    if SPELL_CATALOG_METADATA_BY_NAME[spec.display_name].aoe is not None
    or SPELL_CATALOG_METADATA_BY_NAME[spec.display_name].target_type == 'position_aoe'
    or spec.content_id in ('spell.acid_splash', 'spell.chain_lightning',
                          'spell.magic_missile', 'spell.scorching_ray'))


def _member(member_id, display_name, role, *, effects=()):
    return EncounterRosterMember(member_id=member_id, display_name=display_name, deployment_role=role,
        source=PremadeCharacterRosterSource(premade_id=FIGHTER), scenario_setup_effects=effects)


def _fragile(position):
    if position not in FRAGILE:
        return ()
    return (RosterStartingDamage(amount=FRAGILE_DAMAGE, damage_type=DamageType.PIERCING),)


def crowd_recipe(seed, *, godmode):
    """The seed recipe with the GC roster and deployment; content refs stay the seed's."""
    seed_recipe = EncounterRecipe.model_validate(seed['recipe'])
    amber_slot, blue_slot = seed_recipe.roster_slots
    caster = amber_slot.roster.members[0]
    if godmode:
        grant = RosterSpellGrant(caster_level=20, spell_refs=tuple(
            get_content_declaration(spec.spell_type).ref for spec in GODMODE_SPECS))
        caster = caster.model_copy(update={'scenario_setup_effects': (*caster.scenario_setup_effects, grant)})
    amber_members = (caster, *(_member(f'ally_{index}', f'Gallery ally {index}', f'ally_{index}')
        for index in range(1, len(ALLIES) + 1)))
    blue_positions = (*FIREBALL_CLUSTER, *ICE_STORM_CLUSTER, *WITNESSES)
    blue_members = tuple(_member(f'crowd_{index}', f'Gallery crowd {index}', f'crowd_{index}',
        effects=_fragile(position)) for index, position in enumerate(blue_positions, start=1))
    slots = []
    for slot, members in ((amber_slot, amber_members), (blue_slot, blue_members)):
        roster = EncounterRosterRecipe.create(roster_id=slot.roster.roster_id, title=slot.roster.title,
            members=members)
        slots.append(slot.model_copy(update={'roster': roster}))
    deployment = EncounterDeploymentSpec.create(deployment_id='deployment.gallery_crowd', title='Gallery crowd',
        battlefield_id=seed_recipe.battlefield_id, zones=(
            EncounterDeploymentZone(zone_id=amber_slot.deployment_zone_id, ordered_slots=(CASTER, *ALLIES)),
            EncounterDeploymentZone(zone_id=blue_slot.deployment_zone_id, ordered_slots=blue_positions)))
    return EncounterRecipe.create(encounter_id='encounter.gallery_crowd', title='Gallery crowd',
        roster_slots=tuple(slots), battlefield_id=seed_recipe.battlefield_id, deployment=deployment,
        opening_policy=seed_recipe.opening_policy)


def start_request(godmode):
    seed = json.loads(SEED.read_text())
    recipe = crowd_recipe(seed, godmode=godmode)
    amber, blue = recipe.roster_slots
    assignments = (
        {'seat_id': 'amber', 'controlled': [[amber.roster_slot_id, member.member_id]
            for member in amber.roster.members], 'observers': None},
        {'seat_id': 'blue', 'controlled': [[blue.roster_slot_id, member.member_id]
            for member in blue.roster.members], 'observers': None},
    )
    return Start.model_validate({'game_id': 'gallery-crowd', 'game_epoch': uuid4(),
        'audience_ids': {'amber': uuid4(), 'blue': uuid4()}, 'encounter_id': None,
        'recipe': recipe.model_dump(mode='json'), 'assignments': assignments, 'test_seed': seed['test_seed']})


class Driver:
    """Worker requests addressed to the seat that currently holds input."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.command_number = 0

    def dispatch(self, request):
        reply, _, response = worker.dispatch(self.runtime, request)
        if reply.rejection is not None or reply.query_error is not None:
            raise AssertionError(f'{type(request).__name__} rejected: {reply.rejection or reply.query_error}')
        return response

    def settle(self):
        while worker.needs_advance(self.runtime.session):
            self.dispatch(Advance())

    def input_seat(self):
        self.settle()
        for seat, publication in self.runtime.publications.items():
            if publication.boundary.input_actor_uuid is not None:
                return seat, publication.boundary.input_actor_uuid
        raise AssertionError('No seat holds input')

    def choices(self, seat, actor_uuid):
        publication = self.runtime.publications[seat]
        return self.dispatch(Choices(seat_id=seat, request=ChoicesRequest(actor_uuid=actor_uuid,
            state_revision=publication.state_revision, force_attack=False, correlation_id=uuid4())))

    def preview(self, seat, actor_uuid, generation, selection):
        publication = self.runtime.publications[seat]
        return self.dispatch(Preview(seat_id=seat, request=PreviewRequest(actor_uuid=actor_uuid,
            state_revision=publication.state_revision, discovery_generation=generation,
            correlation_id=uuid4(), selection=selection)))

    def command(self, seat, actor_uuid, intent):
        self.command_number += 1
        publication = self.runtime.publications[seat]
        return self.dispatch(Command(seat_id=seat, request=CommandRequest(command_number=self.command_number,
            actor_uuid=actor_uuid, state_revision=publication.state_revision, intent=intent)))

    def turn_of(self, accepts):
        """End turns until an input actor satisfies `accepts(seat, actor)`; returns (seat, actor uuid)."""
        for _ in range(64):
            seat, actor_uuid = self.input_seat()
            if accepts(seat, self.runtime.session.game.entities[actor_uuid]):
                return seat, actor_uuid
            self.command(seat, actor_uuid, EndTurnIntent())
        raise AssertionError('No input actor was accepted')


def prepare_world(runtime, caster_uuid):
    """Light the hall, place the barrel, open every spell slot; returns setup facts."""
    grid = get_map()
    torches = [torch for position in WALL_TORCHES for identity in grid.get_objects_at(position)
        if isinstance(torch := BaseBlock.get(identity), WallTorch)]
    if len(torches) != len(WALL_TORCHES):
        raise AssertionError(f'Expected {len(WALL_TORCHES)} wall torches, found {len(torches)}')
    for torch in torches:
        torch.light()
    barrel = build_oil_barrel(caster_uuid)
    barrel.place_on_grid(OIL_BARREL)
    caster = runtime.session.game.entities[caster_uuid]
    caster.action_economy.set_normal_spell_slot_capacity(uuid5(caster.uuid, 'gallery-crowd'),
        {level: 10 for level in range(1, 10)})
    entities = runtime.session.game.entities.values()
    return {'wall_torches_lit': sum(torch.is_lit for torch in torches), 'creatures': len(entities),
        'caster': {'name': caster.name, 'position': caster.position}, 'oil_barrel': OIL_BARREL}


def actor_states(runtime):
    return {entity.name: {'position': entity.position, 'damage_taken': entity.health.damage_taken,
        'life_state': entity.health.life_state.value} for entity in runtime.session.game.entities.values()}


class Measurement:
    """Recorders for one measured operation, chosen by the mode."""

    def __init__(self, mode):
        self.mode = mode
        self.counts = Counter()
        self.phases = Counter()
        self.phase_calls = Counter()
        self.profiler = cProfile.Profile() if mode == 'profile' else None

    def _phase(self, name, started):
        self.phases[name] += (perf_counter() - started) * 1000
        self.phase_calls[name] += 1

    def run(self, operation):
        if self.mode == 'ordinary':
            return operation()
        count_token = set_action_count_recorder(lambda name, value: self.counts.update({name: value}))
        timing_token = set_action_timing_recorder(self._phase)
        if self.profiler is not None:
            self.profiler.enable()
        try:
            return operation()
        finally:
            if self.profiler is not None:
                self.profiler.disable()
            reset_action_timing_recorder(timing_token)
            reset_action_count_recorder(count_token)

    def report(self):
        if self.mode == 'ordinary':
            return {}
        result = {'timing_qualified': False, 'counts': dict(sorted(self.counts.items())),
            'phases': [{'name': name, 'inclusive_ms': elapsed, 'calls': self.phase_calls[name]}
                for name, elapsed in self.phases.most_common()]}
        if self.profiler is not None:
            profile = pstats.Stats(self.profiler).get_stats_profile()
            rows = [{'file': row.file_name, 'line': row.line_number, 'function': function, 'calls': row.ncalls,
                'self_ms': row.tottime * 1000, 'inclusive_ms': row.cumtime * 1000}
                for function, row in profile.func_profiles.items()]
            result['top_self'] = sorted(rows, key=lambda row: row['self_ms'], reverse=True)[:60]
            result['top_inclusive'] = sorted(rows, key=lambda row: row['inclusive_ms'], reverse=True)[:60]
        return result


def measured_operation(runtime, mode, kind, action_factory):
    measurement = Measurement(mode)
    before = actor_states(runtime)
    cursor = EventQueue.event_cursor()
    marks = {}

    def operation():
        marks['start'] = perf_counter()
        action = action_factory()
        marks['constructed'] = perf_counter()
        outcome = action.apply()
        runtime.session.encounter.check_deaths()
        marks['native'] = perf_counter()
        result = session._operation(runtime.session, cursor)
        marks['operation'] = perf_counter()
        updates = application.capture_application_operation(runtime.audiences, result, runtime.catalog)
        marks['published'] = perf_counter()
        encoded = {seat: len(update.model_dump_json().encode('utf-8')) for seat, update in updates.items()}
        marks['encoded'] = perf_counter()
        return outcome, encoded

    outcome, encoded = measurement.run(operation)
    if outcome is None or outcome.canceled or outcome.phase.value != 'completion':
        reason = outcome.status_message if outcome is not None else 'no outcome'
        raise AssertionError(f'{kind}: the action failed to complete ({reason})')
    after = actor_states(runtime)
    completed = Counter(event.event_type.value for _, event in EventQueue.iter_events_since(cursor)
        if event.phase.value == 'completion' and not event.canceled)
    span = lambda first, second: (marks[second] - marks[first]) * 1000
    return {'kind': kind, 'construction_ms': span('start', 'constructed'), 'native_ms': span('constructed', 'native'),
        'operation_ms': span('native', 'operation'), 'publication_ms': span('operation', 'published'),
        'encoding_ms': span('published', 'encoded'), 'total_ms': span('start', 'encoded'),
        'event_versions': EventQueue.event_cursor() - cursor, 'completed_facts': dict(completed.most_common()),
        'encoded_bytes': encoded,
        'outcome': outcome.model_dump(mode='json', include={'name', 'total_targets', 'total_damage'}),
        'deaths': sorted(name for name, state in after.items()
            if state['life_state'] != before[name]['life_state']),
        'damaged': sum(state['damage_taken'] != before[name]['damage_taken'] for name, state in after.items()),
        **measurement.report()}


def measured_request(mode, kind, request):
    measurement = Measurement(mode)
    started = perf_counter()
    response = measurement.run(request)
    elapsed = (perf_counter() - started) * 1000
    return response, {'kind': kind, 'total_ms': elapsed,
        'response_bytes': len(response.model_dump_json().encode('utf-8')) if response is not None else 0,
        **measurement.report()}


def _spec(content_id):
    return next(spec for spec in SPELL_CONTENT_IDENTITY_SPECS if spec.content_id == content_id)


def _uuid_named(runtime, name):
    return next(identity for identity, entity in runtime.session.game.entities.items() if entity.name == name)


def cast(content_id, *, aim=None, targets=()):
    """One measured cast: `aim` for area spells, `targets` (entity names) for targeted ones."""
    return ('cast', content_id, aim, targets)


DROP_CONCENTRATION = ('drop_concentration', None, None, ())
END_TURN = ('end_turn', None, None, ())


def move(destination):
    """One measured caster step (the caster carries a lit torch)."""
    return ('move', None, destination, ())


def sequence_case(*steps):
    """Measure each step in order in one fresh world (e.g. a cast, then a dispel)."""

    def case(runtime, driver, mode, caster_uuid):
        operations = []
        caster = runtime.session.game.entities[caster_uuid]
        for index, (kind, content_id, aim, targets) in enumerate(steps):
            if index:
                # Each step is its own turn's action; refresh the economy outside the measurement.
                caster.action_economy.reset_all_costs()
            if kind == 'drop_concentration':
                operations.append(measured_operation(runtime, mode, 'concentration_drop',
                    partial(DropConcentration, source_entity_uuid=caster_uuid, use_register=False)))
                continue
            if kind == 'move':
                operations.append(measured_operation(runtime, mode, f'move_to_{aim[0]}_{aim[1]}',
                    partial(Move, source_entity_uuid=caster_uuid, end_position=aim, use_register=False)))
                continue
            if kind == 'end_turn':
                seat, actor_uuid = driver.input_seat()
                _, row = measured_request(mode, 'end_turn_and_next_start',
                    lambda: driver.command(seat, actor_uuid, EndTurnIntent()))
                operations.append(row)
                continue
            spec = _spec(content_id)
            fields = {}
            if aim is not None:
                fields['end_position'] = aim
            if targets:
                uuids = [caster_uuid if name == CASTER_NAME else _uuid_named(runtime, name) for name in targets]
                fields['target_entity_uuid'] = uuids[0]
                fields['extra_target_entity_uuids'] = uuids[1:]
            factory = partial(spec.spell_type, source_entity_uuid=caster_uuid, use_register=False,
                caster_level=20, cast_at_level=spec.level, **fields)
            operations.append(measured_operation(runtime, mode, content_id, factory))
        return operations
    return case


def crowd(*indices):
    return tuple(f'Gallery crowd {index}' for index in indices)


ALLY_NAMES = (CASTER_NAME, *(f'Gallery ally {index}' for index in range(1, len(ALLIES) + 1)))


def choices_case(accepts, behavior_id, aim):
    """Choices miss and hit, then Preview and Command of `behavior_id` aimed nearest `aim`."""

    def case(runtime, driver, mode, caster_uuid):
        seat, actor_uuid = driver.turn_of(accepts)
        _, miss_row = measured_request(mode, 'choices_miss', lambda: driver.choices(seat, actor_uuid))
        hit, hit_row = measured_request(mode, 'choices_hit', lambda: driver.choices(seat, actor_uuid))
        choices = hit.choices
        rows = (*choices.self_actions, *choices.entity_actions, *choices.position_actions, *choices.object_actions)
        miss_row['rows'] = len(rows)
        miss_row['target_rows'] = sum(len(pool) for pool in choices.target_sets)
        operations = [miss_row, hit_row]
        matching = [row for row in rows if row.behavior_id == behavior_id and row.can_afford
            and choices.target_sets[row.target_set]]
        miss_row['measured_behavior'] = behavior_id if matching else None
        if not matching:
            return operations
        action = min(matching, key=lambda row: row.cast_at_level or 0)
        pool = choices.target_sets[action.target_set]

        def distance(target):
            position = choices.positions[target.position] if target.kind == 'position' else None
            return (abs(position[0] - aim[0]) + abs(position[1] - aim[1])) if position is not None else 10**6
        target = min(pool, key=distance)
        selection = ActionSelection(action_index=action.discovery_index, target_indices=(target.index,),
            extra_target_positions=(), prefer_safe=False)
        preview, preview_row = measured_request(mode, 'preview',
            lambda: driver.preview(seat, actor_uuid, choices.discovery_generation, selection))
        preview_row['can_confirm'] = preview.preview.can_confirm
        operations.append(preview_row)
        if preview.preview.can_confirm:
            _, command_row = measured_request(mode, 'command', lambda: driver.command(seat, actor_uuid,
                ExecuteSelectionIntent(discovery_generation=choices.discovery_generation, selection=selection)))
            operations.append(command_row)
        return operations
    return case


CASES = {
    # P1/P2 gate rows (P0b-1).
    'fireball': (False, sequence_case(cast('spell.fireball', aim=FIREBALL_AIM))),
    'sleet_storm': (False, sequence_case(cast('spell.sleet_storm', aim=FIREBALL_AIM), DROP_CONCENTRATION)),
    'ice_storm': (False, sequence_case(cast('spell.ice_storm', aim=ICE_STORM_AIM))),
    'choices_caster': (True, choices_case(lambda seat, actor: actor.name == CASTER_NAME, 'spell.fireball', FIREBALL_AIM)),
    'choices_fighter': (False, choices_case(lambda seat, actor: seat == 'blue', 'action.attack', CASTER)),
    # P3 gate rows (P0b-2), by index pattern (§1).
    'circle_of_death': (False, sequence_case(cast('spell.circle_of_death', aim=(46, 20)))),
    'holy_aura': (False, sequence_case(cast('spell.holy_aura', targets=ALLY_NAMES))),
    'magic_missile': (False, sequence_case(cast('spell.magic_missile', targets=crowd(7, 8, 9)))),
    'chain_lightning': (False, sequence_case(cast('spell.chain_lightning', targets=crowd(7, 6, 8, 9)))),
    'mass_heal': (False, sequence_case(cast('spell.mass_heal', targets=ALLY_NAMES))),
    'grease': (False, sequence_case(cast('spell.grease', aim=NEAR_AIM))),
    'web': (False, sequence_case(cast('spell.web', aim=NEAR_AIM), DROP_CONCENTRATION)),
    'spike_growth': (False, sequence_case(cast('spell.spike_growth', aim=NEAR_AIM), DROP_CONCENTRATION)),
    'cloudkill': (False, sequence_case(cast('spell.cloudkill', aim=NEAR_AIM), DROP_CONCENTRATION)),
    'darkness_daylight': (False, sequence_case(cast('spell.darkness', aim=NEAR_AIM),
        cast('spell.daylight', aim=NEAR_AIM))),
    'delayed_blast_fireball': (False, sequence_case(cast('spell.delayed_blast_fireball', aim=FIREBALL_AIM))),
    # Ordered: Thunderwave pushes the two northern allies 10 ft into Spike Growth.
    'thunderwave_spike_growth': (False, sequence_case(cast('spell.spike_growth', aim=(26, 5)),
        cast('spell.thunderwave', aim=(26, 8)))),
    # Routine rows.
    'caster_steps': (False, sequence_case(move((27, 10)), move((28, 10)), move((27, 10)))),
    'turn_start': (False, sequence_case(END_TURN, END_TURN)),
}


def run(args):
    godmode, case = CASES[args.case]
    report = {'status': 'running', 'case': args.case, 'mode': args.mode, 'godmode': godmode,
        'timing_qualified': args.mode == 'ordinary', 'python': sys.version, 'operations': []}
    runtime = None
    try:
        started = perf_counter()
        runtime, _, _ = worker.start(start_request(godmode))
        report['startup_ms'] = (perf_counter() - started) * 1000
        driver = Driver(runtime)
        caster_uuid = next(identity for identity, entity in runtime.session.game.entities.items()
            if entity.name == CASTER_NAME)
        started = perf_counter()
        report['setup'] = prepare_world(runtime, caster_uuid)
        report['setup_ms'] = (perf_counter() - started) * 1000
        report['operations'] = case(runtime, driver, args.mode, caster_uuid)
        report['status'] = 'passed'
    except BaseException as error:
        report['status'] = 'failed'
        report['error_type'] = type(error).__name__
        report['error'] = str(error)[:1500]
        raise
    finally:
        if runtime is not None:
            session.close_session(runtime.session)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, default=str))
        print(json.dumps({'status': report['status'], 'case': args.case, 'mode': args.mode,
            'report': str(args.output), 'operations': [{key: row.get(key) for key in (
                'kind', 'total_ms', 'native_ms', 'publication_ms', 'event_versions', 'deaths')}
                for row in report['operations']]}, default=str), flush=True)


def entry():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True, choices=tuple(CASES))
    parser.add_argument('--mode', choices=('ordinary', 'counts', 'profile'), default='ordinary')
    parser.add_argument('--name', required=True, help='report file stem under .runtime/single-pass/gallery_crowd')
    args = parser.parse_args()
    if Path(args.name).name != args.name:
        parser.error('--name must be a file stem')
    args.output = OUTPUT / f'{args.name}.json'
    if args.output.exists():
        raise FileExistsError(args.output)
    worker.main = partial(run, args)
    worker.run_process()


if __name__ == '__main__':
    entry()
