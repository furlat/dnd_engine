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
from dnd.actions_functional import preview_available_selection, selection_admission_error
from dnd.ai.policies.basic import BASIC_POLICY_ID
from dnd.content.characters.premades import CLERIC_PREMADE_ID
from dnd.content.items.environment_item_builders import build_oil_barrel
from dnd.controller import HumanController
from dnd.core.base_block import BaseBlock
from dnd.core.content.encounters import (AuthoredCreatureRosterSource, EncounterDeploymentSpec,
    EncounterDeploymentZone, EncounterRecipe, EncounterRosterMember, EncounterRosterRecipe,
    PremadeCharacterRosterSource, RosterControllerDefaults, RosterControllerKind, RosterSpellGrant,
    RosterStartingDamage)
from dnd.core.content.registration import get_content_declaration
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.encounter import TurnState
from dnd.items.torches import WallTorch
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.player import application, session
from dnd.player.commands import ActionSelection
from dnd.spatial.gas_traps import materialize_gas_vent
from dnd.spatial.portals import materialize_portal
from dnd.spatial.triggers import materialize_pressure_plate
from dnd.spells.catalog_content import SPELL_CATALOG_METADATA_BY_NAME, SPELL_CONTENT_IDENTITY_SPECS
from dnd.spells.conjuration import Entangle
from dnd.types.event_facts import EventPhase
from dnd.types.controls import ActivationLink
from dnd.types.traps import TrapState
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
# Entangle is implemented natively but absent from the spell catalog; the id is local to this harness.
SPELL_TYPES = {**{spec.content_id: (spec.spell_type, spec.level) for spec in SPELL_CONTENT_IDENTITY_SPECS},
    'spell.entangle': (Entangle, 1)}
CROWD = (*FIREBALL_CLUSTER, *ICE_STORM_CLUSTER, *WITNESSES)
# Turn Undead (P-g2): the cleric takes ally 1's slot (25, 12); six skeletons stand within 30 ft of it.
CLERIC_NAME = 'Gallery cleric'
SKELETONS = tuple((x, y) for y in (13, 14) for x in (28, 29, 30))
# Wall of Stone (P-h): a closed loop of 10 sections. With these three witnesses moved onto it, 4 stand on the
# loop and are displaced outside ('right' of each clockwise section); the witness at (34, 20) is enclosed.
WALL_OF_STONE = ((30, 18), (36, 18), (36, 22), (30, 22), (30, 18))
WALL_WITNESSES = ((32, 18), (35, 18), (36, 21))
# Heal row: starting damage of the caster and allies 1-3 (ally 1 starts at 0 of 44 hit points).
PARTY_DAMAGE = (20, 44, 30, 10)
# Mechanism rows (P-g1): the caster's first step east presses the plate.
PLATE = (27, 10)
GAS_VENT = (42, 12)  # under the Fireball cluster
PORTAL_ENTRANCES = WITNESSES[:3]  # one closed one-cell portal under each, exits 10 rows south
PORTAL_DROP = 10


def _member(member_id, display_name, role, *, effects=(), source=None):
    return EncounterRosterMember(member_id=member_id, display_name=display_name, deployment_role=role,
        source=source or PremadeCharacterRosterSource(premade_id=FIGHTER), scenario_setup_effects=effects)


def _fragile(position):
    if position not in FRAGILE:
        return ()
    return (RosterStartingDamage(amount=FRAGILE_DAMAGE, damage_type=DamageType.PIERCING),)


def _party(caster, damage=(0,) * (len(ALLIES) + 1)):
    """Amber: the seed caster and the fighter allies, with optional starting damage, and their slots."""
    members = (caster, *(_member(f'ally_{index}', f'Gallery ally {index}', f'ally_{index}')
        for index in range(1, len(ALLIES) + 1)))
    members = tuple(member.model_copy(update={'scenario_setup_effects': (*member.scenario_setup_effects,
        RosterStartingDamage(amount=amount, damage_type=DamageType.PIERCING))}) if amount else member
        for member, amount in zip(members, damage, strict=True))
    return members, (CASTER, *ALLIES)


def _crowd(positions):
    """Blue: one torch-carrying fighter per position (fragile at FRAGILE positions), and the positions."""
    return tuple(_member(f'crowd_{index}', f'Gallery crowd {index}', f'crowd_{index}', effects=_fragile(position))
        for index, position in enumerate(positions, start=1)), tuple(positions)


def crowd_roster(caster):
    """The GC roster: ((amber members, slots), (blue members, slots))."""
    return _party(caster), _crowd(CROWD)


def wall_roster(caster):
    """Three far witnesses stand on the Wall of Stone loop instead."""
    return _party(caster), _crowd((*FIREBALL_CLUSTER, *ICE_STORM_CLUSTER, *WITNESSES[:5], *WITNESSES[8:],
        *WALL_WITNESSES))


def undead_roster(caster):
    """The Life Cleric replaces ally 1; six skeletons replace the last six witnesses."""
    (sorcerer, _, *allies), party_slots = _party(caster)
    cleric = _member('cleric', CLERIC_NAME, 'cleric', source=PremadeCharacterRosterSource(premade_id=CLERIC_PREMADE_ID))
    skeletons = tuple(_member(f'skeleton_{index}', f'Gallery skeleton {index}', f'skeleton_{index}',
        source=AuthoredCreatureRosterSource(recipe=BESTIARY_CREATURE_RECIPES_BY_ID['skeleton']))
        for index in range(1, len(SKELETONS) + 1))
    crowd, crowd_slots = _crowd((*FIREBALL_CLUSTER, *ICE_STORM_CLUSTER, *WITNESSES[:4]))
    return ((sorcerer, cleric, *allies), party_slots), ((*crowd, *skeletons), (*crowd_slots, *SKELETONS))


def damaged_party_roster(caster):
    """The GC roster with PARTY_DAMAGE on the party."""
    return _party(caster, PARTY_DAMAGE), _crowd(CROWD)


ROSTERS = {'crowd': crowd_roster, 'wall': wall_roster, 'undead': undead_roster, 'damaged_party': damaged_party_roster}


def crowd_recipe(seed, *, godmode, roster='crowd', blue_ai=False):
    """The seed recipe with a GC roster (ROSTERS) and its deployment; content refs stay the seed's.

    `blue_ai` gives the blue slot to the native basic policy; it then has no seat.
    """
    seed_recipe = EncounterRecipe.model_validate(seed['recipe'])
    amber_slot, blue_slot = seed_recipe.roster_slots
    caster = amber_slot.roster.members[0]
    if godmode:
        grant = RosterSpellGrant(caster_level=20, spell_refs=tuple(
            get_content_declaration(spec.spell_type).ref for spec in GODMODE_SPECS))
        caster = caster.model_copy(update={'scenario_setup_effects': (*caster.scenario_setup_effects, grant)})
    (amber_members, amber_positions), (blue_members, blue_positions) = ROSTERS[roster](caster)
    blue_controller = RosterControllerDefaults(controller=RosterControllerKind.AI,
        participant_name=blue_slot.controller_defaults.participant_name,
        policy_id=BASIC_POLICY_ID) if blue_ai else blue_slot.controller_defaults
    slots = []
    for slot, members, controller in ((amber_slot, amber_members, amber_slot.controller_defaults),
                                      (blue_slot, blue_members, blue_controller)):
        roster_recipe = EncounterRosterRecipe.create(roster_id=slot.roster.roster_id, title=slot.roster.title,
            members=members)
        slots.append(slot.model_copy(update={'roster': roster_recipe, 'controller_defaults': controller}))
    deployment = EncounterDeploymentSpec.create(deployment_id='deployment.gallery_crowd', title='Gallery crowd',
        battlefield_id=seed_recipe.battlefield_id, zones=(
            EncounterDeploymentZone(zone_id=amber_slot.deployment_zone_id, ordered_slots=amber_positions),
            EncounterDeploymentZone(zone_id=blue_slot.deployment_zone_id, ordered_slots=blue_positions)))
    return EncounterRecipe.create(encounter_id='encounter.gallery_crowd', title='Gallery crowd',
        roster_slots=tuple(slots), battlefield_id=seed_recipe.battlefield_id, deployment=deployment,
        opening_policy=seed_recipe.opening_policy)


def start_request(godmode, recipe_options):
    """One seat per human-controlled slot, controlling all of its members."""
    seed = json.loads(SEED.read_text())
    recipe = crowd_recipe(seed, godmode=godmode, **recipe_options)
    human = tuple(slot for slot in recipe.roster_slots
        if slot.controller_defaults.controller is RosterControllerKind.HUMAN)
    assignments = tuple({'seat_id': slot.roster_slot_id, 'controlled': [[slot.roster_slot_id, member.member_id]
        for member in slot.roster.members], 'observers': None} for slot in human)
    return Start.model_validate({'game_id': 'gallery-crowd', 'game_epoch': uuid4(),
        'audience_ids': {slot.roster_slot_id: uuid4() for slot in human}, 'encounter_id': None,
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


def measured_operation(runtime, mode, kind, action_factory, faces=()):
    """One measured action; `faces` fixes the die faces its rolls consume (e.g. a save that must succeed)."""
    measurement = Measurement(mode)
    before = actor_states(runtime)
    cursor = EventQueue.event_cursor()
    marks = {}

    def operation():
        marks['start'] = perf_counter()
        action = action_factory()
        marks['constructed'] = perf_counter()
        if faces:
            with fixed_dice_faces(*faces):
                outcome = action.apply()
        else:
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
            if name in before and state['life_state'] != before[name]['life_state']),
        'damaged': sum(name in before and state['damage_taken'] != before[name]['damage_taken']
            for name, state in after.items()),
        'arrived': sorted(after.keys() - before.keys()), 'departed': sorted(before.keys() - after.keys()),
        **measurement.report()}


def measured_request(mode, kind, request):
    measurement = Measurement(mode)
    cursor = EventQueue.event_cursor()
    started = perf_counter()
    response = measurement.run(request)
    elapsed = (perf_counter() - started) * 1000
    return response, {'kind': kind, 'total_ms': elapsed, 'event_versions': EventQueue.event_cursor() - cursor,
        'response_bytes': len(response.model_dump_json().encode('utf-8')) if response is not None else 0,
        **measurement.report()}


def _uuid_named(runtime, name):
    return next(identity for identity, entity in runtime.session.game.entities.items() if entity.name == name)


def cast(content_id, *, aim=None, targets=(), caster=CASTER_NAME, faces=(), **fields):
    """One measured cast by `caster`: `aim` for area spells, `targets` (entity names) for targeted ones;
    `faces` fixes its die faces; `fields` are further spell fields (e.g. a summon form or wall vertices)."""
    return ('cast', content_id, aim, targets, caster, fields, faces)


DROP_CONCENTRATION = ('drop_concentration', None, None, (), CASTER_NAME, {}, ())
END_TURN = ('end_turn', None, None, (), None, {}, ())
END_ROUND = ('end_round', None, None, (), None, {}, ())  # END_TURN until the round number advances


def move(destination, *, mover=CASTER_NAME, **fields):
    """One measured step of `mover` (the caster carries a lit torch); `fields` are further Move fields."""
    return ('move', None, destination, (), mover, fields, ())


def use(behavior_id, *, actor):
    """One measured use of `actor`'s registered action `behavior_id` (e.g. Turn Undead)."""
    return ('use', behavior_id, None, (), actor, {}, ())


def sequence_case(*steps, setup=None):
    """Measure each step in order in one fresh world (e.g. a cast, then a dispel), after an unmeasured `setup`."""

    def case(runtime, driver, mode, caster_uuid):
        if setup is not None:
            setup(runtime)
        operations = []
        encounter = runtime.session.encounter
        for index, (kind, content_id, aim, targets, actor_name, fields, faces) in enumerate(steps):
            actor_uuid = _uuid_named(runtime, actor_name) if actor_name is not None else None
            if index and actor_uuid is not None:
                # Each step is its own turn's action; refresh the economy outside the measurement.
                runtime.session.game.entities[actor_uuid].action_economy.reset_all_costs()
            if kind == 'drop_concentration':
                operations.append(measured_operation(runtime, mode, 'concentration_drop',
                    partial(DropConcentration, source_entity_uuid=actor_uuid, use_register=False)))
                continue
            if kind == 'move':
                operations.append(measured_operation(runtime, mode, f'move_to_{aim[0]}_{aim[1]}',
                    partial(Move, source_entity_uuid=actor_uuid, end_position=aim, use_register=False, **fields)))
                continue
            if kind == 'use':
                actor = runtime.session.game.entities[actor_uuid]
                template = next(action for action in actor.registered_actions if action.semantic_key == content_id)
                operations.append(measured_operation(runtime, mode, content_id, template.instantiate))
                continue
            if kind in ('end_turn', 'end_round'):
                round_number = encounter.round_number
                for _ in range(64):
                    seat, input_uuid = driver.input_seat()
                    _, row = measured_request(mode, 'end_turn_and_next_start',
                        lambda: driver.command(seat, input_uuid, EndTurnIntent()))
                    row['round'] = encounter.round_number
                    operations.append(row)
                    if kind == 'end_turn' or encounter.round_number != round_number:
                        break
                else:
                    raise AssertionError('The round did not advance')
                continue
            spell_type, level = SPELL_TYPES[content_id]
            fields = dict(fields)
            if aim is not None:
                fields['end_position'] = aim
            if targets:
                uuids = [caster_uuid if name == CASTER_NAME else _uuid_named(runtime, name) for name in targets]
                fields['target_entity_uuid'] = uuids[0]
                fields['extra_target_entity_uuids'] = uuids[1:]
            factory = partial(spell_type, source_entity_uuid=actor_uuid, use_register=False,
                caster_level=20, cast_at_level=level, **fields)
            operations.append(measured_operation(runtime, mode, content_id, factory, faces))
        return operations
    return case


def open_slots(*names):
    """Setup: open every spell slot of the named non-caster members, so each can hold its own concentration."""

    def setup(runtime):
        for name in names:
            entity = runtime.session.game.entities[_uuid_named(runtime, name)]
            entity.action_economy.set_normal_spell_slot_capacity(uuid5(entity.uuid, 'gallery-crowd'),
                {level: 10 for level in range(1, 10)})
    return setup


def gas_vent_plate(runtime):
    """Setup: a pressure plate on the caster's next step, wired to a gas vent under the Fireball cluster."""
    vent = materialize_gas_vent(GAS_VENT)
    materialize_pressure_plate({PLATE}, ActivationLink(target_condition_uuid=vent.uuid))


def portal_plate(runtime):
    """Setup: one closed one-cell portal under each of three witnesses, all opened by one plate.

    A portal has a single exit cell and cancels a transfer onto an occupied exit, so three occupants
    of one portal would commit one transfer; three portals commit three.
    """
    portals = tuple(materialize_portal({position}, (position[0], position[1] + PORTAL_DROP),
        trap_state=TrapState.READY) for position in PORTAL_ENTRANCES)
    materialize_pressure_plate({PLATE}, tuple(ActivationLink(target_condition_uuid=portal.uuid)
        for portal in portals))


def ai_turn_case(runtime, driver, mode, caster_uuid):
    """End human turns until a living native-AI combatant is current, then measure each Advance of its turn
    (one policy decision each; the first also starts the turn unless the previous command did)."""
    encounter = runtime.session.encounter
    for _ in range(64):
        if (not isinstance(encounter.get_current_controller(), HumanController)
                and encounter.get_current_combatant().is_alive):
            break
        if worker.needs_advance(runtime.session):
            driver.dispatch(Advance())
        else:
            seat, actor_uuid = driver.input_seat()
            driver.command(seat, actor_uuid, EndTurnIntent())
    else:
        raise AssertionError('No native AI turn came up')
    actor = encounter.get_current_entity()
    operations = []
    while True:
        turn_started = encounter.turn_state is TurnState.IN_PROGRESS
        _, row = measured_request(mode, 'ai_decision', lambda: driver.dispatch(Advance()))
        row.update({'actor': actor.name, 'turn_already_started': turn_started})
        operations.append(row)
        if (len(operations) == 4 or encounter.get_current_entity().uuid != actor.uuid
                or encounter.turn_state is not TurnState.IN_PROGRESS):
            return operations


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


def _admitted_positions(actor, row, target, level):
    """Command's admission of one listed target, completing a vertex path through preview's next vertices."""
    positions = ()
    kind = row.position_selection.kind if row.position_selection is not None else 'single'
    for _ in range(8):
        reason = selection_admission_error(actor, row, (target,), positions, cast_at_level=level)
        if reason is None or kind != 'path':
            return reason, positions
        preview = preview_available_selection(actor, row, (target,), positions, include_aoe_effects=False,
            cast_at_level=level)
        if not preview.next_positions:
            return reason, positions
        positions = (*positions, preview.next_positions[0])
    return reason, positions


def _root_outcome(cursor, actor_uuid):
    """The actor's root action lineage since `cursor`: its last phase and whether it ever reached execution."""
    phases, last = {}, {}
    for _, event in EventQueue.iter_events_since(cursor):
        if event.parent_lineage is None and event.source_entity_uuid == actor_uuid:
            phases.setdefault(event.lineage_uuid, set()).add(event.phase)
            last[event.lineage_uuid] = event
    if not last:
        return None
    lineage, event = next(iter(last.items()))
    return {'event': event.name, 'phase': event.phase.value, 'canceled': event.canceled,
        'reached_execution': EventPhase.EXECUTION in phases[lineage], 'status': event.status_message}


def _row_key(row):
    """A row's identity across worlds: its name without the item uuid, and its display name."""
    return row.template_name.split('__item_')[0], row.display_name


def agreement_case(accepts, godmode, recipe_options=None):
    """Gate (b): discovery and Command agree on every row x listed target x castable level.

    Every affordable row's listed targets pass Command's admission (`selection_admission_error`) at every
    castable level. Then one sample per row (its first admitted target at the listed level) is executed through
    Command on a fresh discovery and must not cancel at admission (a root lineage that never reached
    execution). A sample whose row an earlier sample made unavailable (Silence on the caster) runs in a fresh world.
    """

    def case(runtime, driver, mode, caster_uuid):
        seat, actor_uuid = driver.turn_of(accepts)
        actor = runtime.session.game.entities[actor_uuid]
        driver.choices(seat, actor_uuid)
        original = runtime.session.discovery.original
        checked, refused, keys = 0, [], []
        for row in original.all_actions:
            if not row.can_afford or not row.valid_targets:
                continue
            for target in row.valid_targets:
                for level in (row.cast_levels or (None,)):
                    checked += 1
                    reason, positions = _admitted_positions(actor, row, target, level)
                    if reason is not None:
                        refused.append({'row': row.template_name, 'target': target.index,
                            'target_uuid': target.target_uuid, 'position': target.position, 'level': level,
                            'positions': positions, 'reason': reason})
                    elif _row_key(row) not in keys:
                        keys.append(_row_key(row))

        def current_row(key):
            seat, input_uuid = driver.input_seat()
            choices = driver.choices(seat, input_uuid).choices
            rows = driver.runtime.session.discovery.original.all_actions
            return seat, input_uuid, choices, next((row for row in rows
                if _row_key(row) == key and row.can_afford and row.valid_targets), None)

        def restart():
            session.close_session(driver.runtime.session)
            driver.runtime, _, _ = worker.start(start_request(godmode, recipe_options or {}))
            prepare_world(driver.runtime, _uuid_named(driver.runtime, CASTER_NAME))
            driver.turn_of(accepts)

        executed, admission_cancels, worlds = [], [], 1
        for key in keys:
            driver.runtime.session.game.entities[driver.input_seat()[1]].action_economy.reset_all_costs()
            seat, input_uuid, choices, row = current_row(key)
            if row is None:
                restart()
                worlds += 1
                seat, input_uuid, choices, row = current_row(key)
            if row is None:
                executed.append({'row': key[0], 'skipped': 'not rediscovered in a fresh world'})
                continue
            entity = driver.runtime.session.game.entities[input_uuid]
            level = row.cast_at_level
            chosen = next(((target, positions) for target in row.valid_targets
                for reason, positions in (_admitted_positions(entity, row, target, level),) if reason is None), None)
            if chosen is None:
                admission_cancels.append({'row': key[0], 'rejected': 'no listed target admitted on rediscovery'})
                continue
            target, positions = chosen
            selection = ActionSelection(action_index=row.discovery_index, target_indices=(target.index,),
                extra_target_positions=positions, prefer_safe=False, cast_at_level=level)
            cursor = EventQueue.event_cursor()
            try:
                driver.command(seat, input_uuid, ExecuteSelectionIntent(
                    discovery_generation=choices.discovery_generation, selection=selection))
            except AssertionError as error:
                admission_cancels.append({'row': key[0], 'rejected': str(error)})
                continue
            outcome = _root_outcome(cursor, input_uuid)
            executed.append({'row': key[0], **(outcome or {'event': None})})
            if outcome is not None and outcome['canceled'] and not outcome['reached_execution']:
                admission_cancels.append({'row': key[0], **outcome})
        return [{'kind': 'agreement', 'rows': sum(1 for row in original.all_actions if row.can_afford),
            'checked_selections': checked, 'refused': refused, 'samples': len(keys), 'worlds': worlds,
            'executed': executed, 'admission_cancels': admission_cancels}]
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
    # Remaining §1 rows (P0b-2). A third entry holds `crowd_recipe` options (roster variant, AI blue slot).
    'turn_undead': (False, sequence_case(use('action.class.cleric.turn_undead', actor=CLERIC_NAME)),
        {'roster': 'undead'}),
    'gas_vent_plate': (False, sequence_case(move(PLATE, prefer_safe=False), setup=gas_vent_plate)),
    'portal_plate': (False, sequence_case(move(PLATE, prefer_safe=False), setup=portal_plate)),
    # The single die is the enclosed witness's Dexterity save: a 20 makes it the escaper.
    'wall_of_stone': (False, sequence_case(cast('spell.wall_of_stone', aim=WALL_OF_STONE[0], faces=(20,),
        extra_target_positions=WALL_OF_STONE[1:], displacement_side='right')), {'roster': 'wall'}),
    'summon_retirement': (False, sequence_case(cast('spell.conjure_animals', aim=(28, 10), form_id='wolf'),
        DROP_CONCENTRATION)),
    # The wind line points east from the caster; each step drags it one cell further into the cluster.
    'gust_of_wind_walk': (False, sequence_case(cast('spell.gust_of_wind', aim=(27, 10)),
        *(move((x, 10)) for x in range(27, 33)))),
    # Along y=7 the 15-ft emanation sweeps the cluster's row (y=10) while staying out of reach.
    'spirit_guardians_walk': (False, sequence_case(cast('spell.spirit_guardians'),
        *(move((x, 7)) for x in range(29, 47, 3)))),
    # One concentration per caster: allies 1 and 3 hold Entangle and Gust of Wind.
    'round_step_zones': (False, sequence_case(cast('spell.sleet_storm', aim=FIREBALL_AIM),
        cast('spell.entangle', aim=(34, 20), caster='Gallery ally 1'),
        cast('spell.gust_of_wind', aim=(27, 8), caster='Gallery ally 3'), END_ROUND,
        setup=open_slots('Gallery ally 1', 'Gallery ally 3'))),
    'mass_healing_word': (False, sequence_case(cast('spell.mass_healing_word', targets=ALLY_NAMES)),
        {'roster': 'damaged_party'}),
    'ai_decision': (False, ai_turn_case, {'blue_ai': True}),
    # Gate (b) of PD1b: discovery and Command agree.
    'agreement_caster': (True, agreement_case(lambda seat, actor: actor.name == CASTER_NAME, True)),
    'agreement_fighter': (False, agreement_case(lambda seat, actor: seat == 'blue', False)),
}


def run(args):
    godmode, case, *variant = CASES[args.case]
    recipe_options = variant[0] if variant else {}
    report = {'status': 'running', 'case': args.case, 'mode': args.mode, 'godmode': godmode,
        'recipe_options': recipe_options, 'timing_qualified': args.mode == 'ordinary', 'python': sys.version,
        'operations': []}
    runtime = None
    try:
        started = perf_counter()
        runtime, _, _ = worker.start(start_request(godmode, recipe_options))
        report['startup_ms'] = (perf_counter() - started) * 1000
        driver = Driver(runtime)
        caster_uuid = next(identity for identity, entity in runtime.session.game.entities.items()
            if entity.name == CASTER_NAME)
        started = perf_counter()
        report['setup'] = prepare_world(runtime, caster_uuid)
        report['setup_ms'] = (perf_counter() - started) * 1000
        report['operations'] = case(runtime, driver, args.mode, caster_uuid)
        runtime = driver.runtime  # a case may continue in a fresh world
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
                'kind', 'total_ms', 'native_ms', 'publication_ms', 'event_versions', 'deaths')
                if key in row or row.get('kind') != 'agreement'}
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
