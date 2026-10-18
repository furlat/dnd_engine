"""Gallery Crowd (GC) stress fixture for the single-pass propagation plan (§1, §9.4).

The authored Lantern Gallery seed recipe (`gallery_crowd_seed_recipe.json`) is
extended to a crowd: a sorcerer and three allies at the west entry, a Fireball
cluster and an Ice Storm cluster of torch-carrying fighters, spread witnesses,
all hall wall torches lit and one oil barrel beside the Fireball cluster.

One case per fresh worker process (`server.worker.run_process`). Modes:

- ordinary: complete-operation timings only;
- counts: `dnd.action_timing` counters and inclusive phases (not timing-qualified);
- profile: cProfile plus counters (not timing-qualified).

Spell cases measure construct → native apply → operation → every-seat
publication → encoding. Choices cases measure the worker requests Choices
(miss, then hit), Preview and Command.

Seats (`--seats`, plan EVENT_NATIVE_PUBLICATION E0): `faction` (G1, one seat per human slot: amber 4, blue 26),
`character` (G2, one seat per member) or `batch:N` (G3 with N=5: blue in seats of N, amber one seat), all
through the worker's Start assignments.

Every seat's records are folded by the client reference fold (`dnd.player.reduction`) from their wire bytes,
outside the measured spans: each row reports per seat the record's bytes, its combat-log bytes (plan Q2) and
the client fold time. The harness's own world edits (`prepare_world`, a case's setup) are published to every
seat as one unmeasured operation before the first measured one. `--oracle DIR` adds O1 at every operation end,
O3 views and the O2 spool (`seat_oracle.py`, replayed by `spool_replay.py`).
"""

import argparse
import cProfile
import gc
from collections import Counter
from dataclasses import dataclass, field, replace
from functools import partial
import json
import os
from pathlib import Path
import pstats
import sys
from random import Random
from time import perf_counter
from uuid import uuid4, uuid5

from pydantic import BaseModel

from dnd.action_timing import (reset_action_count_recorder, reset_action_timing_recorder,
    set_action_count_recorder, set_action_timing_recorder)
from dnd.actions import DropConcentration, Move
from dnd.actions_functional import preview_available_selection, selection_admission_error
from dnd.ai.policies.basic import BASIC_POLICY_ID
from dnd.content.characters.premades import CLERIC_PREMADE_ID
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.content.items.environment_item_builders import build_oil_barrel
from dnd.controller import HumanController
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import build_creatable_models
from dnd.core.cells import mask_positions
from dnd.core.content.encounters import (AuthoredCreatureRosterSource, DamageAffinityStatus, EncounterDeploymentSpec,
    EncounterDeploymentZone, EncounterRecipe, EncounterRosterMember, EncounterRosterRecipe,
    PremadeCharacterRosterSource, RosterControllerDefaults, RosterControllerKind, RosterDamageAffinity,
    RosterSpellGrant, RosterStartingDamage)
from dnd.core.content.registration import get_content_declaration
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.encounter import EncounterState, TurnState
from dnd.items.environment import DirectionalDoor
from dnd.items.torches import WallTorch
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.player import application, session
from dnd.player.commands import ActionSelection
from dnd.player.facts import PlayerState
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.spatial.gas_traps import materialize_gas_vent
from dnd.spatial.portals import materialize_portal
from dnd.spatial.triggers import materialize_pressure_plate
from dnd.spells.catalog_content import SPELL_CATALOG_METADATA_BY_NAME, SPELL_CONTENT_IDENTITY_SPECS
from dnd.spells.conjuration import Entangle
from dnd.types.event_facts import EventPhase
from dnd.types.controls import ActivationLink
from dnd.types.traps import TrapState
from devtools.performance import seat_oracle
from server import worker
from server.protocol import (ChoicesRequest, CommandRequest, EndTurnIntent, ExecuteSelectionIntent,
    InitializationResponse, PlayerOperation, PreviewRequest, protocol_identity)
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
# Room re-entry (plan E0): the party waits outside the hall. The caster stands in the passage at the gallery
# door, seeing the lit hall through it; the allies stand in the burial hall off the line of both doors. A crowd
# member on the passage side works the door while the caster is away.
GALLERY_DOOR = 'Lantern gallery door'  # (24, 6), on the cell's west side
PASSAGE_DOOR = 'Gallery passage'  # (20, 6), on the cell's east side
REENTRY_PARTY = ((22, 6), (14, 2), (14, 10), (17, 2))
DOOR_KEEPER = (23, 6)  # a door is worked from a cell touching its face (reach 0)
DOOR_KEEPER_NAME = f'Gallery crowd {len(CROWD) + 1}'
REENTRY_OUT = ((21, 6), (20, 6), (19, 6), (18, 5), (18, 4))  # the caster's steps out of sight of the hall
HALL_X = 24  # the hall's cells are those with x >= 24 (the passage is x 21-23, the burial hall x 12-20)


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


def immune_party_roster(caster):
    """The GC roster with every party member immune to every damage type (`RosterDamageAffinity`, applied before
    initiative). The crowd's attacks still roll to hit and for damage, and the caster's area spells still reach
    the allies; the damage is reduced to 0, so no party member goes down."""
    (party, party_slots), crowd = crowd_roster(caster)
    immunity = tuple(RosterDamageAffinity(status=DamageAffinityStatus.IMMUNITY, damage_type=damage_type,
        label='Gallery party immunity') for damage_type in DamageType)
    return (tuple(member.model_copy(update={'scenario_setup_effects': (*member.scenario_setup_effects, *immunity)})
        for member in party), party_slots), crowd


def reentry_roster(caster):
    """The party outside the hall (REENTRY_PARTY); the door keeper joins the crowd."""
    (party, _), crowd = _party(caster), _crowd((*CROWD, DOOR_KEEPER))
    return (party, REENTRY_PARTY), crowd


ROSTERS = {'crowd': crowd_roster, 'wall': wall_roster, 'undead': undead_roster, 'damaged_party': damaged_party_roster,
           'immune_party': immune_party_roster, 'reentry': reentry_roster}


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


def seat_layout(text):
    """`faction`, `character` or `batch:N` (N ≥ 1)."""
    kind, _, size = text.partition(':')
    if text in ('faction', 'character') or (kind == 'batch' and size.isdigit() and int(size) >= 1):
        return text
    raise argparse.ArgumentTypeError(f'unknown seat layout {text!r}: faction, character or batch:N')


def slot_seats(slot, layout):
    """One human slot's seats as (seat id, member addresses): the whole slot (`faction`), one per member
    (`character`), or for the blue slot consecutive members in seats of N (`batch:N`, other slots whole)."""
    addresses = tuple((slot.roster_slot_id, member.member_id) for member in slot.roster.members)
    if layout == 'character':
        return tuple((f'{slot.roster_slot_id}.{member}', ((slot_id, member),)) for slot_id, member in addresses)
    if layout.startswith('batch:') and slot.roster_slot_id == 'blue':
        size = int(layout.removeprefix('batch:'))
        return tuple((f'blue.{start // size + 1}', addresses[start:start + size])
            for start in range(0, len(addresses), size))
    return ((slot.roster_slot_id, addresses),)


def start_request(godmode, recipe_options, layout):
    """The Start request with `layout`'s seats over the human-controlled slots, each seat controlling (and
    observing through) its members; and the slot of each seat."""
    seed = json.loads(SEED.read_text())
    recipe = crowd_recipe(seed, godmode=godmode, **recipe_options)
    seats = tuple((seat, slot.roster_slot_id, addresses) for slot in recipe.roster_slots
        if slot.controller_defaults.controller is RosterControllerKind.HUMAN
        for seat, addresses in slot_seats(slot, layout))
    assignments = tuple({'seat_id': seat, 'controlled': [list(address) for address in addresses], 'observers': None}
        for seat, _, addresses in seats)
    request = Start.model_validate({'game_id': 'gallery-crowd', 'game_epoch': uuid4(),
        'audience_ids': {seat: uuid4() for seat, _, _ in seats}, 'encounter_id': None,
        'recipe': recipe.model_dump(mode='json'), 'assignments': assignments, 'test_seed': seed['test_seed']})
    return request, {seat: slot for seat, slot, _ in seats}


@dataclass(slots=True)
class SeatClients:
    """Each seat's client: the slot its members come from, the reference fold of every record it received,
    and the oracle outputs when `--oracle` is given."""

    layout: str
    slots: dict[str, str]
    states: dict[str, PlayerState] = field(default_factory=dict)
    oracle: seat_oracle.Oracle | None = None


def log_bytes(record, payload):
    """The bytes the combat log takes in a record's encoding `payload` (plan Q2: counted apart): its nodes'
    entries and its standalone appends, as the record's size less that of the record without them."""
    stripped = record.model_copy(update={'combat_log_appends': (), 'lineages': tuple(
        replace(lineage, events=tuple(replace(node, combat_log=None) for node in lineage.events))
        for lineage in record.lineages)})
    return len(payload) - len(stripped.model_dump_json().encode())


def world_bytes(record, payload):
    """The bytes the world updates take in a record's encoding `payload` (E3-world's column): the record's size
    less that of the record without them."""
    stripped = record.model_copy(update={'lineages': tuple(replace(lineage, world_updates=())
        for lineage in record.lineages)})
    return len(payload) - len(stripped.model_dump_json().encode())


def initialize_clients(clients, publications, records):
    """Fold each seat's initialization record (Start's records, in its publications' order) from its wire bytes."""
    for publication, record in zip(publications, records, strict=True):
        payload = record.model_dump_json().encode()
        initial = InitializationResponse.model_validate_json(payload)
        state = reduce_initialization(initial.initialization, content_additions=initial.content_additions)
        clients.states[publication.seat_id] = state
        if clients.oracle is not None:
            seat_oracle.receive(clients.oracle, publication.seat_id, 0, payload, state)


def deliver(clients, records):
    """Fold each (seat, record) into the seat's client from its wire bytes, as a client does; the record's
    bytes, combat-log bytes and fold time per seat."""
    rows = {}
    for seat, record in records:
        payload = record.model_dump_json().encode()
        started = perf_counter()
        clients.states[seat] = reduce_operation(clients.states[seat], PlayerOperation.model_validate_json(payload))
        fold_ms = (perf_counter() - started) * 1000
        row = rows.setdefault(seat, {'bytes': 0, 'log_bytes': 0, 'world_bytes': 0, 'fold_ms': 0.0})
        row['bytes'] += len(payload)
        row['log_bytes'] += log_bytes(record, payload)
        row['world_bytes'] += world_bytes(record, payload)
        row['fold_ms'] += fold_ms
        if clients.oracle is not None:
            seat_oracle.receive(clients.oracle, seat, record.cursor.sequence, payload, clients.states[seat])
    return rows


def publish(runtime, updates):
    """`worker.dispatch`'s publication of an operation the harness ran itself, which no request owns: each seat
    whose update says something or whose boundary moved gets its next cursor, revision and record."""
    records = []
    for seat, update in updates.items():
        previous = runtime.publications[seat]
        if not (update.lineages or update.combat_log_appends or update.content_additions or update.hud is not None
                or worker.boundary(runtime.session, seat, previous.state_revision) != previous.boundary):
            continue
        cursor = previous.cursor.model_copy(update={'sequence': previous.cursor.sequence + 1})
        # A fresh token per record, as the worker's, but drawn from no generator: the identities a transcript
        # seeds (gallery_transcript.py) stay those of a harness that publishes nothing itself.
        revision = str(uuid5(cursor.audience_id, f'harness-publication:{cursor.sequence}'))
        boundary = worker.boundary(runtime.session, seat, revision)
        runtime.publications[seat] = previous.model_copy(update={'cursor': cursor, 'state_revision': revision,
            'boundary': boundary})
        records.append((seat, PlayerOperation(audience=update.audience, lineages=update.lineages, hud=update.hud,
            combat_log_appends=update.combat_log_appends, content_additions=update.content_additions,
            protocol=protocol_identity(), cursor=cursor, state_revision=revision, command_number=None,
            boundary=boundary)))
    return records


def byte_report(rows):
    """An operation's seat updates: each seat's bytes and combat-log bytes, the largest update with its
    combat-log and other bytes, the largest non-log bytes, and the client fold time."""
    if not rows:
        return {'seat_bytes': {}, 'largest_update': None, 'largest_non_log': None,
                'client_fold_ms': {'max': 0.0, 'total': 0.0, 'records': 0}}
    largest = max(rows, key=lambda seat: rows[seat]['bytes'])
    non_log = max(rows, key=lambda seat: rows[seat]['bytes'] - rows[seat]['log_bytes'])
    return {'seat_bytes': {seat: {'bytes': row['bytes'], 'log_bytes': row['log_bytes'],
                                  'world_bytes': row['world_bytes']} for seat, row in rows.items()},
        'largest_update': {'seat': largest, 'bytes': rows[largest]['bytes'], 'log_bytes': rows[largest]['log_bytes'],
            'non_log_bytes': rows[largest]['bytes'] - rows[largest]['log_bytes'],
            'world_bytes': rows[largest]['world_bytes']},
        'largest_non_log': {'seat': non_log, 'bytes': rows[non_log]['bytes'] - rows[non_log]['log_bytes']},
        'client_fold_ms': {'max': max(row['fold_ms'] for row in rows.values()),
            'total': sum(row['fold_ms'] for row in rows.values()), 'records': len(rows)}}


class Driver:
    """Worker requests addressed to the seat that currently holds input; their records wait in `pending`
    until the seats' clients receive them, outside any measured span."""

    def __init__(self, runtime, clients):
        self.runtime = runtime
        self.clients = clients
        self.pending = []
        self.setup_rows = []  # the byte reports of the harness's unmeasured setup publications
        self.command_number = 0

    def dispatch(self, request):
        reply, records, response = worker.dispatch(self.runtime, request)
        if reply.rejection is not None or reply.query_error is not None:
            raise AssertionError(f'{type(request).__name__} rejected: {reply.rejection or reply.query_error}')
        self.pending.extend((publication.seat_id, record)
                            for publication, record in zip(reply.publications, records, strict=True))
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
        """End turns until an input actor satisfies `accepts(its seat's slot, actor)`; returns (seat, actor uuid)."""
        for _ in range(64):
            seat, actor_uuid = self.input_seat()
            if accepts(self.clients.slots[seat], self.runtime.session.game.entities[actor_uuid]):
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


def incomplete_models():
    """Every model class whose validation schema is not built yet (conditions and actions defer theirs)."""
    incomplete, seen, stack = set(), set(), [BaseModel]
    while stack:
        for subclass in stack.pop().__subclasses__():
            if subclass not in seen:
                seen.add(subclass)
                stack.append(subclass)
                if not subclass.__pydantic_complete__:
                    incomplete.add(subclass)
    return incomplete


def built_since(incomplete):
    """The classes of `incomplete` whose schema has been built since."""
    return sorted(f'{model.__module__}.{model.__qualname__}' for model in incomplete if model.__pydantic_complete__)


class Measurement:
    """Recorders for one measured operation, chosen by the mode."""

    def __init__(self, mode):
        self.mode = mode
        self.counts = Counter()
        self.phases = Counter()
        self.phase_calls = Counter()
        self.profiler = cProfile.Profile() if mode == 'profile' else None
        self.collections = Counter()
        self.collection_ms = Counter()
        self.young_survivors = 0
        self.gc_debt_ms = 0.0
        self.cycles_found = 0
        self.cycle_types = {}
        self._collection_started = 0.0
        self._young_before = 0
        self.schema_builds = []

    def _collection(self, phase, info):
        """gc callback: count and time every collection inside the operation; a young pass's survivors are promoted."""
        generation = info['generation']
        if phase == 'start':
            self._collection_started = perf_counter()
            self._young_before = gc.get_count()[0]
            return
        self.collections[generation] += 1
        self.collection_ms[generation] += (perf_counter() - self._collection_started) * 1000
        if generation == 0:
            self.young_survivors += max(self._young_before - info['collected'], 0)

    def _phase(self, name, started):
        self.phases[name] += (perf_counter() - started) * 1000
        self.phase_calls[name] += 1

    def run(self, operation):
        """Run `operation`; its schema builds are read outside its timed span."""
        incomplete = incomplete_models()
        gc.callbacks.append(self._collection)
        try:
            return self._run(operation)
        finally:
            gc.callbacks.remove(self._collection)
            self.schema_builds = built_since(incomplete)

    def _run(self, operation):
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

    def collect_after(self):
        """The worker's collection point after a request (`worker.collect_between_requests`), outside the
        timed span: its time and the reference cycles it found are reported with the op that left them."""
        started = perf_counter()
        found, cycles = worker.collect_between_requests()
        self.gc_debt_ms = (perf_counter() - started) * 1000
        self.cycles_found = found
        self.cycle_types = dict(cycles.most_common(8))

    def gc_report(self):
        return {'schema_builds': self.schema_builds, 'gc': {'collections': {str(generation): count for generation, count in sorted(self.collections.items())},
            'ms': {str(generation): round(elapsed, 3) for generation, elapsed in sorted(self.collection_ms.items())},
            'young_survivors': self.young_survivors, 'collect_after_ms': round(self.gc_debt_ms, 3),
            'cycles_found': self.cycles_found, 'cycle_types': self.cycle_types}}

    def report(self):
        if self.mode == 'ordinary':
            return self.gc_report()
        result = {**self.gc_report(), 'timing_qualified': False, 'counts': dict(sorted(self.counts.items())),
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


def receive_pending(driver):
    """Records of unmeasured requests reach their seats' clients; the fold's garbage is collected unmeasured."""
    if driver.pending:
        deliver(driver.clients, driver.pending)
        driver.pending.clear()
        worker.collect_between_requests()


def after_operation(driver, kind, records):
    """An operation's records reach the seats' clients after its measurement and post-reply collection; with
    `--oracle`, O1 runs at its end. What they leave is collected unmeasured. Returns the byte report."""
    report = byte_report(deliver(driver.clients, records))
    oracle = driver.clients.oracle
    if oracle is not None:
        result = seat_oracle.check(oracle, len(oracle.report), kind, driver.runtime.session, driver.clients.states)
        report['o1_differences'] = result['differences']
    worker.collect_between_requests()
    return report


def publish_setup(driver, cursor, kind='setup'):
    """The harness's own world edits since `cursor` reach every seat as one unmeasured operation."""
    runtime = driver.runtime
    receive_pending(driver)
    updates = application.capture_application_operation(runtime.audiences, session._operation(runtime.session, cursor),
        runtime.catalog)
    return after_operation(driver, kind, publish(runtime, updates))


def measured_operation(driver, mode, kind, action_factory, faces=()):
    """One measured action; `faces` fixes the die faces its rolls consume (e.g. a save that must succeed)."""
    runtime = driver.runtime
    receive_pending(driver)
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
        return outcome, encoded, updates

    outcome, encoded, updates = measurement.run(operation)
    measurement.collect_after()
    if outcome is None or outcome.canceled or outcome.phase.value != 'completion':
        reason = outcome.status_message if outcome is not None else 'no outcome'
        raise AssertionError(f'{kind}: the action failed to complete ({reason})')
    seats = after_operation(driver, kind, publish(runtime, updates))
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
        **seats, **measurement.report()}


def measured_request(driver, mode, kind, request):
    """One measured worker request (`request` dispatches it through `driver`)."""
    receive_pending(driver)
    measurement = Measurement(mode)
    cursor = EventQueue.event_cursor()
    span = {}

    def timed():
        started = perf_counter()
        try:
            return request()
        finally:
            span['ms'] = (perf_counter() - started) * 1000
    response = measurement.run(timed)
    measurement.collect_after()
    elapsed = span['ms']
    versions = EventQueue.event_cursor() - cursor
    records, driver.pending = driver.pending, []
    seats = after_operation(driver, kind, records)
    return response, {'kind': kind, 'total_ms': elapsed, 'event_versions': versions,
        'response_bytes': len(response.model_dump_json().encode('utf-8')) if response is not None else 0,
        **seats, **measurement.report()}


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


def check(description, holds):
    """An unmeasured check of the world between measured steps: `holds(runtime)` must be true."""
    return ('check', description, holds, (), None, {}, ())


def caster_hall_cells(runtime):
    """How many hall cells the caster sees now (its published senses)."""
    caster = runtime.session.game.entities[_uuid_named(runtime, CASTER_NAME)]
    return sum(1 for x, _ in mask_positions(capture_senses_snapshot(caster.senses).visible) if x >= HALL_X)


def door(name, *, actor):
    """One measured use of the door named `name` by `actor`: Close Door if it is open, else Open Door."""
    return ('door', name, None, (), actor, {}, ())


def door_named(name):
    return next(door for placement in get_map().iter_object_placements()
        if isinstance(door := BaseBlock.get(placement.object_uuid), DirectionalDoor) and door.name == name)


def sequence_case(*steps, setup=None):
    """Measure each step in order in one fresh world (e.g. a cast, then a dispel), after an unmeasured `setup`,
    published to every seat (a trap materialized mid-game included: its install root is a `MechanismInstallEvent`)."""

    def case(runtime, driver, mode, caster_uuid):
        if setup is not None:
            cursor = EventQueue.event_cursor()
            setup(runtime)
            driver.setup_rows.append(publish_setup(driver, cursor, 'case_setup'))
        # The harness constructs these spells itself, outside any creature's content: build each as the
        # template a caster holds is built at character creation (its class and what it can create).
        incomplete = incomplete_models()
        for kind, content_id, *_ in steps:
            if kind == 'cast':
                spell_type = SPELL_TYPES[content_id][0]
                spell_type.model_rebuild()
                build_creatable_models(spell_type)
        harness_built = built_since(incomplete)
        operations = []
        encounter = runtime.session.encounter
        for index, (kind, content_id, aim, targets, actor_name, fields, faces) in enumerate(steps):
            actor_uuid = _uuid_named(runtime, actor_name) if actor_name is not None else None
            if index and actor_uuid is not None:
                # Each step is its own turn's action; refresh the economy outside the measurement.
                runtime.session.game.entities[actor_uuid].action_economy.reset_all_costs()
            if kind == 'drop_concentration':
                operations.append(measured_operation(driver, mode, 'concentration_drop',
                    partial(DropConcentration, source_entity_uuid=actor_uuid, use_register=False)))
                continue
            if kind == 'move':
                operations.append(measured_operation(driver, mode, f'move_to_{aim[0]}_{aim[1]}',
                    partial(Move, source_entity_uuid=actor_uuid, end_position=aim, use_register=False, **fields)))
                continue
            if kind == 'use':
                actor = runtime.session.game.entities[actor_uuid]
                template = next(action for action in actor.registered_actions if action.semantic_key == content_id)
                operations.append(measured_operation(driver, mode, content_id, template.instantiate))
                continue
            if kind == 'check':
                if not aim(runtime):
                    raise AssertionError(f'Check failed before step {index}: {content_id}')
                continue
            if kind == 'door':
                if actor_uuid is None:
                    raise AssertionError('A door step names its actor')
                target = door_named(content_id)
                template, = target.get_use_actions(actor_uuid)
                operations.append(measured_operation(driver, mode, 'door_close' if target.is_open else 'door_open',
                    template.instantiate))
                continue
            if kind in ('end_turn', 'end_round'):
                round_number = encounter.round_number
                for _ in range(64):
                    seat, input_uuid = driver.input_seat()
                    _, row = measured_request(driver, mode, 'end_turn_and_next_start',
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
            operations.append(measured_operation(driver, mode, content_id, factory, faces))
        if operations:
            operations[0]['harness_built'] = harness_built
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


def open_doors(*names):
    """Setup: open the named doors."""

    def setup(runtime):
        for name in names:
            door_named(name).open()
    return setup


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
        _, row = measured_request(driver, mode, 'ai_decision', lambda: driver.dispatch(Advance()))
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
        _, miss_row = measured_request(driver, mode, 'choices_miss', lambda: driver.choices(seat, actor_uuid))
        hit, hit_row = measured_request(driver, mode, 'choices_hit', lambda: driver.choices(seat, actor_uuid))
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
        preview, preview_row = measured_request(driver, mode, 'preview',
            lambda: driver.preview(seat, actor_uuid, choices.discovery_generation, selection))
        preview_row['can_confirm'] = preview.preview.can_confirm
        operations.append(preview_row)
        if preview.preview.can_confirm:
            _, command_row = measured_request(driver, mode, 'command', lambda: driver.command(seat, actor_uuid,
                ExecuteSelectionIntent(discovery_generation=choices.discovery_generation, selection=selection)))
            operations.append(command_row)
        return operations
    return case


def _admitted_positions(actor, row, target, level):
    """Command's admission of one listed target, completing its vertices or destination through preview's options."""
    positions = ()
    kind = row.position_selection.kind if row.position_selection is not None else 'single'
    for _ in range(8):
        reason = selection_admission_error(actor, row, (target,), positions, cast_at_level=level)
        if reason is None or kind not in ('path', 'entity_destination'):
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
        schema_builds = []  # schema builds inside the case's Choices and Command requests (not its restarts)

        def counted(request):
            incomplete = incomplete_models()
            try:
                return request()
            finally:
                schema_builds.extend(built_since(incomplete))
        counted(lambda: driver.choices(seat, actor_uuid))
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
            choices = counted(lambda: driver.choices(seat, input_uuid)).choices
            rows = driver.runtime.session.discovery.original.all_actions
            return seat, input_uuid, choices, next((row for row in rows
                if _row_key(row) == key and row.can_afford and row.valid_targets), None)

        def restart():
            session.close_session(driver.runtime.session)
            fresh, _ = begin_world(godmode, recipe_options or {}, driver.clients.layout)
            driver.runtime, driver.clients, driver.pending = fresh.runtime, fresh.clients, []
            driver.setup_rows.clear()
            prepare_published(driver)
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
                counted(lambda: driver.command(seat, input_uuid, ExecuteSelectionIntent(
                    discovery_generation=choices.discovery_generation, selection=selection)))
            except AssertionError as error:
                admission_cancels.append({'row': key[0], 'rejected': str(error)})
                continue
            outcome = _root_outcome(cursor, input_uuid)
            executed.append({'row': key[0], **(outcome or {'event': None})})
            if outcome is not None and outcome['canceled'] and not outcome['reached_execution']:
                admission_cancels.append({'row': key[0], **outcome})
        return [{'kind': 'agreement', 'rows': sum(1 for row in original.all_actions if row.can_afford),
            'checked_selections': checked, 'refused': refused, 'samples': len(keys), 'worlds': worlds,
            'executed': executed, 'admission_cancels': admission_cancels, 'schema_builds': schema_builds}]
    return case



def memory_census(kind, started_round, found, cycles, elapsed, seat_clients):
    """The worker's round check. Since E0 the heap also holds the harness's `seat_clients` client folds (and
    their garbage reaches the scans), so these counts are not the worker's alone."""
    with open('/proc/self/statm') as statm:
        rss_pages = int(statm.read().split()[1])
    return {'kind': kind, 'round': started_round, 'ms': elapsed, 'cycles_found': found,
        'cycle_types': dict(cycles.most_common(8)), 'frozen_objects': gc.get_freeze_count(),
        'tracked_unfrozen': len(gc.get_objects()), 'rss_mb': rss_pages * 4096 / 2**20,
        'includes_seat_clients': seat_clients}


def long_game_case(turns):
    """Seeded play for `turns` human turns. Each turn makes up to three Choices → Preview → Command rounds with a
    random affordable row and target, then ends the turn; the native AI plays every other turn. At each round end
    the worker's round check runs (`worker.collect_frozen_cycles`) and the memory census is recorded.

    The case runs on the `immune_party` roster: on the plain roster the crowd downs the whole party in round 1
    (dying, then stable), the basic policy never finishes a downed character and every later round is AI-only.
    Roster immunity is the one existing setup effect that keeps all four members up and acting while the crowd
    still attacks them (each attack rolls to hit and for damage; the damage is reduced to 0); starting damage
    only lowers hit points and healing items run out.

    The game stops after `turns` human turns, when the encounter ends, or after a full round in which no seat had
    input; fewer than 90% of `turns` human turns fails the case (the rules may still take a turn: a Haste potion's
    lethargy). The last row is the per-round curve: each request kind's count, mean and max ms and the cycles its
    collections found, and the round check's RSS; and the case's wall time."""

    def case(runtime, driver, mode, caster_uuid):
        case_started = perf_counter()
        rng = Random(20261017)
        encounter = runtime.session.encounter
        operations = []
        human_turns = Counter()  # by round
        last_input_round = encounter.round_number - 1  # past last_input_round + 1, a full round had no input

        def request(kind, call, **fields):
            """(accepted, response); an Advance is accepted with no response body."""
            round_before = encounter.round_number
            try:
                response, row = measured_request(driver, mode, kind, call)
            except AssertionError as error:
                operations.append({'kind': 'rejected', 'request': kind, 'round': round_before,
                    'error': str(error)[:200]})
                return False, None
            operations.append({**row, **fields, 'round': round_before})
            if encounter.round_number != round_before:
                started = perf_counter()
                found, cycles = worker.collect_frozen_cycles()
                operations.append(memory_census('round_check', round_before, found, cycles,
                    (perf_counter() - started) * 1000, len(driver.clients.states)))
            return True, response

        stop = f'{turns} human turns'
        while sum(human_turns.values()) < turns:
            while worker.needs_advance(runtime.session) and encounter.round_number <= last_input_round + 1:
                if not request('advance', lambda: driver.dispatch(Advance()))[0]:
                    break
            if encounter.state is not EncounterState.ACTIVE:
                stop = 'the encounter ended'
                break
            if encounter.round_number > last_input_round + 1:
                stop = f'round {encounter.round_number - 1} had no input'
                break
            holders = [(seat, publication.boundary.input_actor_uuid) for seat, publication in runtime.publications.items()
                if publication.boundary.input_actor_uuid is not None]
            if not holders:
                stop = 'no seat holds input'
                break
            seat, actor_uuid = holders[0]
            last_input_round = encounter.round_number
            human_turns[encounter.round_number] += 1
            for _ in range(3):
                accepted, response = request('choices', lambda: driver.choices(seat, actor_uuid))
                if not accepted:
                    break
                choices = response.choices
                rows = [row for row in (*choices.self_actions, *choices.entity_actions, *choices.position_actions,
                    *choices.object_actions) if row.can_afford and choices.target_sets[row.target_set]]
                if not rows:
                    break
                action = rng.choice(rows)
                target = rng.choice(choices.target_sets[action.target_set])
                selection = ActionSelection(action_index=action.discovery_index, target_indices=(target.index,),
                    extra_target_positions=(), prefer_safe=False)
                accepted, preview = request('preview', lambda: driver.preview(seat, actor_uuid,
                    choices.discovery_generation, selection))
                if not accepted or not preview.preview.can_confirm:
                    continue
                request('command', lambda: driver.command(seat, actor_uuid,
                    ExecuteSelectionIntent(discovery_generation=choices.discovery_generation, selection=selection)),
                    behavior=action.behavior_id)
                if runtime.publications[seat].boundary.input_actor_uuid != actor_uuid:
                    break
            if runtime.publications[seat].boundary.input_actor_uuid == actor_uuid:
                request('end_turn', lambda: driver.command(seat, actor_uuid, EndTurnIntent()))
        started = perf_counter()
        found, cycles = worker.collect_frozen_cycles()
        operations.append(memory_census('final_check', encounter.round_number, found, cycles,
            (perf_counter() - started) * 1000, len(driver.clients.states)))
        checks = {row['round']: row for row in operations if row['kind'] in ('round_check', 'final_check')}
        curve = []
        for round_number, check in sorted(checks.items()):
            requests = [row for row in operations if row['round'] == round_number and 'total_ms' in row]
            kinds = {}
            for kind in dict.fromkeys(row['kind'] for row in requests):
                times = [row['total_ms'] for row in requests if row['kind'] == kind]
                kinds[kind] = {'count': len(times), 'mean_ms': sum(times) / len(times), 'max_ms': max(times),
                    'cycles_found': sum(row['gc']['cycles_found'] for row in requests if row['kind'] == kind)}
            curve.append({'round': round_number, 'human_turns': human_turns[round_number], 'requests': kinds,
                'rejected': sum(row['round'] == round_number for row in operations if row['kind'] == 'rejected'),
                'request_cycles_found': sum(row['gc']['cycles_found'] for row in requests),
                'check': check['kind'], 'check_ms': check['ms'], 'check_cycles_found': check['cycles_found'],
                'rss_mb': check['rss_mb']})
        played = sum(human_turns.values())
        operations.append({'kind': 'round_curve', 'human_turns': played, 'expected_turns': turns, 'stop': stop,
            'wall_ms': (perf_counter() - case_started) * 1000, 'rounds': curve})
        if played < 0.9 * turns:
            raise AssertionError(f'long_game: the human seat had {played} of {turns} turns ({stop}); '
                f'turns by round {dict(sorted(human_turns.items()))}')
        return operations
    return case

CASES = {
    # P1/P2 gate rows (P0b-1).
    'fireball': (False, sequence_case(cast('spell.fireball', aim=FIREBALL_AIM))),
    'sleet_storm': (False, sequence_case(cast('spell.sleet_storm', aim=FIREBALL_AIM), DROP_CONCENTRATION)),
    'ice_storm': (False, sequence_case(cast('spell.ice_storm', aim=ICE_STORM_AIM))),
    'choices_caster': (True, choices_case(lambda slot, actor: actor.name == CASTER_NAME, 'spell.fireball', FIREBALL_AIM)),
    'choices_fighter': (False, choices_case(lambda slot, actor: slot == 'blue', 'action.attack', CASTER)),
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
    # Plan E0: the caster sees the lit hall through the open door, steps out of sight, the door keeper closes and
    # reopens the door, the caster steps back to where it saw the hall (in the passage, at the door) and sees it
    # again. Each step and each door use is measured; the checks are not.
    'room_reentry': (False, sequence_case(
        check('the caster sees the hall', lambda runtime: caster_hall_cells(runtime) >= 100),
        *(move(step) for step in REENTRY_OUT),
        check('the caster sees none of the hall', lambda runtime: caster_hall_cells(runtime) == 0),
        door(GALLERY_DOOR, actor=DOOR_KEEPER_NAME), door(GALLERY_DOOR, actor=DOOR_KEEPER_NAME),
        *(move(step) for step in reversed((REENTRY_PARTY[0], *REENTRY_OUT[:-1]))),
        check('the caster sees the hall again', lambda runtime: caster_hall_cells(runtime) >= 100),
        setup=open_doors(GALLERY_DOOR, PASSAGE_DOOR)), {'roster': 'reentry'}),
    'ai_decision': (False, ai_turn_case, {'blue_ai': True}),
    'long_game': (True, long_game_case(50), {'blue_ai': True, 'roster': 'immune_party'}),
    # Gate (b) of PD1b: discovery and Command agree.
    'agreement_caster': (True, agreement_case(lambda slot, actor: actor.name == CASTER_NAME, True)),
    'agreement_fighter': (False, agreement_case(lambda slot, actor: slot == 'blue', False)),
}


def begin_world(godmode, recipe_options, layout, oracle=None):
    """A fresh world started by the worker with `layout`'s seats, and a driver whose seat clients hold their
    initialization records; the Start request's own time (ms)."""
    request, slots = start_request(godmode, recipe_options, layout)
    started = perf_counter()
    runtime, reply, records = worker.start(request)
    elapsed = (perf_counter() - started) * 1000
    try:
        driver = Driver(runtime, SeatClients(layout, slots,
            oracle=seat_oracle.open_oracle(oracle, slots) if oracle is not None else None))
        initialize_clients(driver.clients, reply.publications, records)
    except BaseException:
        session.close_session(runtime.session)
        raise
    return driver, elapsed


def prepare_published(driver):
    """`prepare_world`, then its edits published to every seat; the caster, the setup facts and its time (ms)."""
    caster_uuid = _uuid_named(driver.runtime, CASTER_NAME)
    cursor = EventQueue.event_cursor()
    started = perf_counter()
    setup = prepare_world(driver.runtime, caster_uuid)
    elapsed = (perf_counter() - started) * 1000
    driver.setup_rows.append(publish_setup(driver, cursor))
    return caster_uuid, setup, elapsed


def finish_oracle(driver, game_epoch):
    """The O2 manifest: the game's identities and each seat's final publication (its retained head). Its
    `identities` is 'seeded' when gallery_transcript.py records the run with its seeded generators (it sets
    GALLERY_IDENTITIES); only then do the O3 views compare across runs (`seat_oracle.compare_views`)."""
    runtime = driver.runtime
    seat_oracle.close_oracle(driver.clients.oracle, {'game_id': 'gallery-crowd', 'game_epoch': str(game_epoch),
        'hash_seed': os.environ.get('PYTHONHASHSEED'), 'identities': os.environ.get('GALLERY_IDENTITIES', 'random'), 'layout': driver.clients.layout,
        'slots': driver.clients.slots,
        'publications': {seat: publication.model_dump(mode='json') for seat, publication in runtime.publications.items()},
        # The restore check of O2: each seat's live digest stamps.
        'world_stamps': {seat: seat_oracle.stamp_data(audience.projection.world_stamps)
                         for seat, audience in runtime.audiences.items()}},
        driver.clients.states)


def run(args):
    godmode, case, *variant = CASES[args.case]
    recipe_options = variant[0] if variant else {}
    report = {'status': 'running', 'case': args.case, 'mode': args.mode, 'godmode': godmode,
        'recipe_options': recipe_options, 'seats': args.seats, 'oracle': str(args.oracle) if args.oracle else None,
        'timing_qualified': args.mode == 'ordinary' and args.oracle is None, 'python': sys.version, 'operations': []}
    driver = None
    try:
        driver, report['startup_ms'] = begin_world(godmode, recipe_options, args.seats, args.oracle)
        report['seat_slots'] = driver.clients.slots
        caster_uuid, report['setup'], report['setup_ms'] = prepare_published(driver)
        report['operations'] = case(driver.runtime, driver, args.mode, caster_uuid)
        receive_pending(driver)
        report['setup_publications'] = driver.setup_rows
        report['status'] = 'passed'
    except BaseException as error:
        report['status'] = 'failed'
        report['error_type'] = type(error).__name__
        report['error'] = str(error)[:1500]
        raise
    finally:
        if driver is not None:
            if driver.clients.oracle is not None:
                finish_oracle(driver, next(iter(driver.runtime.publications.values())).cursor.game_epoch)
            session.close_session(driver.runtime.session)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, default=str))
        print(json.dumps({'status': report['status'], 'case': args.case, 'mode': args.mode, 'seats': args.seats,
            'report': str(args.output), 'operations': [{key: row.get(key) for key in (
                'kind', 'total_ms', 'native_ms', 'publication_ms', 'event_versions', 'deaths', 'schema_builds',
                'largest_update', 'o1_differences')
                if key in row or row.get('kind') != 'agreement'}
                for row in report['operations']]}, default=str), flush=True)


def entry():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--case', required=True, choices=tuple(CASES))
    parser.add_argument('--mode', choices=('ordinary', 'counts', 'profile'), default='ordinary')
    parser.add_argument('--name', required=True, help='report file stem under .runtime/single-pass/gallery_crowd')
    parser.add_argument('--seats', type=seat_layout, default='faction',
        help='seat layout: faction (G1), character (G2) or batch:N (G3 with N=5); default faction')
    parser.add_argument('--oracle', type=Path, default=None,
        help='new directory for the O1 report, O3 views and the O2 spool (not timing-qualified)')
    args = parser.parse_args()
    if Path(args.name).name != args.name:
        parser.error('--name must be a file stem')
    if args.oracle is not None and args.case.startswith('agreement'):
        parser.error('--oracle follows one world; agreement cases restart theirs')
    args.output = OUTPUT / f'{args.name}.json'
    if args.output.exists():
        raise FileExistsError(args.output)
    worker.main = partial(run, args)
    worker.run_process()


if __name__ == '__main__':
    entry()
