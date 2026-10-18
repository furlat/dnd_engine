"""Seat oracles over a live Gallery Crowd world (EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 §5 E0).

O1, perceived equality. At an operation's end each seat's perceived view is built twice, in one shape, and
`differences` lists every record held on one side only and every differing field of a record held on both:

- the reference, from the live engine: every member's current senses (`capture_senses_snapshot`), composed by
  `audience_view`; the visible cells' live tiles (`Tile.to_world_tile_state`); the live placed objects
  (`project_world_object`) through the projector's object rule (`_object_observed`, `_observed_object`, with no
  seat memory); the live connectors (`project_world_connector`); each perceived body read from its live aggregate
  (`Entity._entity_created_event`, `actor_from_birth`) and disclosed by `_public_actor`, `_public_condition`,
  `_item_records` and `_public_items`, which also withhold durations from non-owners;
- the client's, from the reference fold of the records the seat received (`dnd.player.reduction`), as held.

Both sides are what the seat perceives now: the composed visible cells with their light and hazard, each
member's visible cells (Q1 attribution), the tiles of visible cells, the objects touching a visible cell or held
as a contact (each on its faces seen now, with the attachments in view and the protections of providers perceived
now: `_perceived_object`, the rest being seat memory), the connectors with both endpoints visible, the visible
cells of effects, the light sources with a visible footprint cell, the bodies of contacts and of the seat's own
members, and any living body the client draws at a visible cell without a contact (a ghost).

Fields left out of both sides, none of them a current perceived value:
- `applied_source_event_cursor` (conditions, item effects): the seat's own occurrence numbering;
- a condition's `event_uuid`, `resulting_*` and `consumed`: values as of its event (the body holds the current ones);
- an effect's `owner_revision`: the seat's own numbering of the effect's changes (`_observe_spatial_revisions`);
- a non-visual contact's `last_visual_position`: the last sighting.

O3: the client side of O1, written per operation and seat, is the perceived-state baseline (`views.jsonl.gz`);
`python seat_oracle.py compare <base> <new>` compares two runs' views. O2's live side: `state_digest` of each seat's
whole client state (memory included) after each record, and the spool of its records written through
`server.recording`; `spool_replay.py` replays it in a fresh process.
"""

import argparse
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field, replace
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import IO, Any
from uuid import UUID

from pydantic import TypeAdapter

from dnd.actor_projection import actor_from_birth
from dnd.blocks.base_item import BaseItem
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.cells import mask_positions, values_items
from dnd.core.events import WorldConnectorState, WorldObjectState, WorldTileState
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.player.actor_facts import ActorState, PresentationTarget
from dnd.player.audience import AudiencePerception, PlayerAudience, audience_view, light_sources
from dnd.player.facts import PlayerActor, PlayerItem, PlayerObject, PlayerState
from dnd.player.projection import (_item_records, _object_observed, _observed_object, _public_actor,
    _public_condition, _public_items)
from dnd.player.session import Session
from dnd.types.actor_facts import ConditionFact
from dnd.types.cells import cell_in
from dnd.types.senses import PerceivedContact, PerceivedLightSource, PerceivedSpatialEffect, SensesSnapshot
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldObjectPlacement, WorldPlacementKind
from dnd.world_authoring import project_world_connector, project_world_object
from dnd.world_facts import CARDINAL_DELTAS, WorldFacts
from server.recording import Recording, close_recording, commit_records, open_recording, stage_record

Position = tuple[int, int]
View = dict[str, dict[str, Any]]
SPOOL_QUOTA = 1024 ** 3  # the server's default per-seat spool limit (server/config.py)
EXAMPLES = 3  # differences kept per class, seat and operation in the report

STATE = TypeAdapter(PlayerState)
TILE = TypeAdapter(WorldTileState)
OBJECT = TypeAdapter(PlayerObject)
CONNECTOR = TypeAdapter(WorldConnectorState)
ACTOR = TypeAdapter(PlayerActor)
ITEM = TypeAdapter(PlayerItem)
CONDITION = TypeAdapter(ConditionFact)
CONTACT = TypeAdapter(PerceivedContact)
EFFECT = TypeAdapter(PerceivedSpatialEffect)
LIGHT = TypeAdapter(PerceivedLightSource)

# Categories of a view, in report order.
CATEGORIES = ('cells', 'member_cells', 'entities', 'object_contacts', 'effects', 'lights', 'tiles', 'objects',
              'connectors', 'actors')
# Values as of an event, not current state: what the client folds them into (the body) is compared instead.
EVENT_TIME_CONDITION_FIELDS = ('event_uuid', 'resulting_max_hp', 'resulting_ac', 'resulting_stats',
                               'resulting_tile', 'resulting_item', 'consumed')


def key(position: Position) -> str:
    return f'{position[0]},{position[1]}'


def canonical(value: Any) -> str:
    """JSON with sorted keys: map order carries no meaning, sequence order does."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def state_digest(state: PlayerState) -> str:
    """The whole client state (memory included), for O2's live-against-replay comparison."""
    return sha256(canonical(STATE.dump_python(state, mode='json')).encode()).hexdigest()


def state_data(state: PlayerState) -> Any:
    return STATE.dump_python(state, mode='json')


def support_cells(placement: WorldObjectPlacement) -> set[Position]:
    """The cells a placed object touches: its supports and, for a boundary, the opposite incident cell
    (the recorded world's object index, `dnd.world_facts._index_object`)."""
    cells = set(placement.positions)
    if placement.kind is WorldPlacementKind.BOUNDARY and placement.boundary_direction is not None:
        dx, dy = CARDINAL_DELTAS[placement.boundary_direction]
        cells.add((placement.position[0] + dx, placement.position[1] + dy))
    return cells


def _visible(senses: SensesSnapshot) -> set[Position]:
    return set(mask_positions(senses.visible))


def _cells(senses: SensesSnapshot, visible: set[Position]) -> dict[str, Any]:
    light = dict(values_items(senses.effective_light_levels))
    hazard = dict(values_items(senses.hazardous_cells))
    return {key(position): {'light': light.get(position, 0), 'hazard': hazard.get(position, 0)}
            for position in sorted(visible)}


def _contacts(composed: Mapping[UUID, PerceivedContact], members: Mapping[UUID, SensesSnapshot], *,
              objects: bool) -> dict[str, Any]:
    """Each composed contact (position, visual) with the contact each member holds of it (Q1 attribution)."""
    return {str(identity): {'position': list(contact.position), 'visual': contact.visual, 'members': {
        str(member): CONTACT.dump_python(held, mode='json') for member, senses in members.items()
        if (held := (senses.objects if objects else senses.entities).get(identity)) is not None}}
        for identity, contact in composed.items()}


def _effect(effect: PerceivedSpatialEffect, positions: set[Position]) -> dict[str, Any]:
    data = EFFECT.dump_python(effect, mode='json')
    data.pop('owner_revision')  # the seat's own numbering of the effect's changes (`_observe_spatial_revisions`)
    data['positions'] = sorted(key(position) for position in positions)
    return data


def _effects(composed: Mapping[UUID, PerceivedSpatialEffect], members: Mapping[UUID, SensesSnapshot],
             visible: set[Position]) -> dict[str, Any]:
    """The visible part of each composed effect: its cells each member sees now (plan §3.2), and the members."""
    result = {}
    for identity, effect in composed.items():
        seen_by = {str(member): sorted(key(position) for position in held.positions if cell_in(senses.visible, position))
            for member, senses in members.items() if (held := senses.spatial_effects.get(identity)) is not None}
        positions = {position for position in effect.positions if position in visible}
        if positions:
            result[str(identity)] = {**_effect(effect, positions), 'members': {
                member: cells for member, cells in seen_by.items() if cells}}
    return result


def _lights(composed: Mapping[UUID, PerceivedLightSource], members: Mapping[UUID, SensesSnapshot],
            visible: set[Position]) -> dict[str, Any]:
    """Each composed light source with its footprint on visible cells, and the members holding it."""
    names = {key(position) for position in visible}
    result = {}
    for identity, source in composed.items():
        footprint = {cell: level for cell, level in source.affected_tiles.items() if cell in names}
        if footprint or tuple(source.position) in visible:
            data = LIGHT.dump_python(source, mode='json')
            data['affected_tiles'] = dict(sorted(footprint.items()))
            data['members'] = sorted(str(member) for member, senses in members.items() if identity in senses.light_sources)
            result[str(identity)] = data
    return result


def _condition(condition: ConditionFact) -> dict[str, Any]:
    data = CONDITION.dump_python(condition, mode='json')
    for name in EVENT_TIME_CONDITION_FIELDS:
        data.pop(name, None)
    state = data.get('state')
    if state is not None:
        state.pop('applied_source_event_cursor', None)  # the seat's occurrence numbering
    return data


def _body(actor: PlayerActor, visual: bool) -> dict[str, Any]:
    data = ACTOR.dump_python(actor, mode='json')
    data['conditions'] = sorted((_condition(row) for row in actor.conditions), key=lambda row: row['condition_uuid'])
    if not visual:
        data.pop('last_visual_position')  # a non-visual contact keeps the last visual sighting
    return data


def _items(items: Mapping[str, dict[str, Any] | None]) -> dict[str, Any]:
    for item in items.values():
        if item is not None and item.get('look') is not None:
            for effect in item['look'].get('item_effects', ()):
                effect.pop('applied_source_event_cursor', None)  # the seat's occurrence numbering
    return dict(items)


def _shown_item_uuids(actor: PlayerActor, owned: bool) -> tuple[UUID, ...]:
    """The items whose records a body shows: its controller's inventory, anyone else's equipped layers."""
    if owned:
        return actor.controlled_items or ()
    return tuple(dict.fromkeys(layer.item_uuid for layer in actor.visual_loadout.layers))


def _seen_faces(placement: WorldObjectPlacement, visible: set[Position]) -> set[CardinalDirection]:
    """A boundary object's faces seen now: its owner cell's side if that cell is visible, the far side if the
    opposite incident cell is (the projector's face rule in `_observed_object`)."""
    if placement.boundary_direction is None:
        return set()
    dx, dy = CARDINAL_DELTAS[placement.boundary_direction]
    x, y = placement.position
    opposite = next(direction for direction, delta in CARDINAL_DELTAS.items() if delta == (-dx, -dy))
    return ({opposite} if (x, y) in visible else set()) | ({placement.boundary_direction}
                                                          if (x + dx, y + dy) in visible else set())


def _perceived_object(obj: PlayerObject, visible: set[Position], in_view: Collection[UUID],
                      effects: Mapping[UUID, PerceivedSpatialEffect]) -> PlayerObject:
    """An object as perceived now, on either side: residues on the faces seen now, the attachments in view, and
    the protections of providers perceived now, on cells seen now. The projector's `_observed_object` adds what
    a seat remembers of the rest; O1 compares current perception only."""
    faces = _seen_faces(obj.placement, visible)
    residues = tuple(row.model_copy(update={'faces': tuple(face for face in row.faces if face in faces)})
                     for row in obj.item.surface_residues if any(face in faces for face in row.faces))
    remnant = obj.item.remnant_state
    if remnant is not None:
        remnant = remnant.model_copy(update={'intact_supported_items': tuple(
            identity for identity in remnant.intact_supported_items if identity in in_view)})
    protections = tuple(row.model_copy(update={'positions': tuple(position for position in row.positions
                                                                   if tuple(position) in visible)})
                        for row in obj.item.construction_suppressions
                        if (provider := effects.get(row.provider_uuid)) is not None and provider.area_geometry is not None)
    return replace(obj, item=replace(obj.item, surface_residues=residues, remnant_state=remnant,
                                     construction_suppressions=protections))


def _perceived_bodies(contacts: Mapping[UUID, PerceivedContact], audience: PlayerAudience
                      ) -> list[tuple[UUID, bool]]:
    """The bodies a seat perceives now, each with whether it is seen: its contacts and its own members."""
    bodies = {identity: contact.visual for identity, contact in contacts.items()}
    for member in audience.observers:
        bodies.setdefault(member, True)
    return sorted(bodies.items(), key=lambda row: str(row[0]))


def client_view(state: PlayerState) -> View:
    """What the client holds now in its currently visible cells, and its current contacts' bodies."""
    senses = state.senses
    if senses is None:
        return {category: {} for category in CATEGORIES}
    audience = state.viewing_audience
    members = state.perception.members or {state.observer_uuid: senses}
    visible = _visible(senses)
    actors = {}
    for identity, visual in _perceived_bodies(senses.entities, audience):
        actor = state.actors.get(identity)
        if actor is None:
            actors[str(identity)] = None
            continue
        actors[str(identity)] = {'body': _body(actor, visual), 'items': _items({
            str(item): ITEM.dump_python(state.items[item], mode='json') if item in state.items else None
            for item in _shown_item_uuids(actor, audience.controls(identity))})}
    # A living body held at a visible cell without a contact is a ghost (a corpse is no contact: it stays drawn).
    for identity, actor in state.actors.items():
        if (str(identity) not in actors and actor.present and actor.life_state is not LifeState.DEAD
                and actor.last_visual_position is not None and tuple(actor.last_visual_position) in visible):
            actors[str(identity)] = {'body': _body(actor, True), 'items': {}, 'held_without_contact': True}
    in_view = {identity for identity, obj in state.objects.items()
               if support_cells(obj.placement) & visible or identity in senses.objects}
    return {
        'cells': _cells(senses, visible),
        'member_cells': {str(member): sorted(key(position) for position in mask_positions(held.visible))
                         for member, held in members.items()},
        'entities': _contacts(senses.entities, members, objects=False),
        'object_contacts': _contacts(senses.objects, members, objects=True),
        'effects': _effects(senses.spatial_effects, members, visible),
        'lights': _lights(senses.light_sources, members, visible),
        'tiles': {key(position): TILE.dump_python(state.tiles[position], mode='json')
                  if position in state.tiles else None for position in sorted(visible)},
        'objects': {str(identity): OBJECT.dump_python(_perceived_object(state.objects[identity], visible, in_view,
            senses.spatial_effects), mode='json') for identity in sorted(in_view, key=str)},
        'connectors': {str(row.connector_uuid): CONNECTOR.dump_python(row, mode='json') for row in state.connectors
                       if all(tuple(point) in visible for point in row.endpoints)},
        'actors': actors,
    }


@dataclass(slots=True)
class LiveWorld:
    """One operation end's live reads, shared by every seat: bodies and tiles read once each, when first needed."""

    session: Session
    actors: dict[UUID, ActorState | None] = field(default_factory=dict)
    tiles: dict[Position, WorldTileState | None] = field(default_factory=dict)
    placements: tuple[WorldObjectPlacement, ...] = ()
    objects: dict[UUID, WorldObjectState] = field(default_factory=dict)


def live_world(session: Session) -> LiveWorld:
    world = LiveWorld(session, placements=get_map().iter_object_placements())
    for placement in world.placements:
        item = BaseBlock.get(placement.object_uuid)
        if isinstance(item, BaseItem):
            world.objects[placement.object_uuid] = project_world_object(item, placement)
    return world


def _live_actor(world: LiveWorld, identity: UUID) -> ActorState | None:
    if identity not in world.actors:
        entity = world.session.game.entities.get(identity)
        # The aggregate's own complete after-values, as its birth fact reads them (not published).
        world.actors[identity] = actor_from_birth(entity._entity_created_event()) if entity is not None else None
    return world.actors[identity]


def _live_tile(world: LiveWorld, position: Position) -> WorldTileState | None:
    if position not in world.tiles:
        tile = get_map().get_tile(*position)
        world.tiles[position] = tile.to_world_tile_state() if tile is not None else None
    return world.tiles[position]


def _effect_owner(identity: UUID) -> UUID | None:
    """The live spatial effect's owner (its condition's source); none once it has ended."""
    condition = BaseObject.get(identity)
    return condition.source_entity_uuid if condition is not None else None


def live_members(session: Session, audience: PlayerAudience) -> dict[UUID, SensesSnapshot]:
    """Each member's current published senses."""
    return {member: capture_senses_snapshot(entity.senses) for member in audience.observers
            if (entity := session.game.entities.get(member)) is not None}


def live_view(world: LiveWorld, audience: PlayerAudience, client: PlayerState) -> View:
    """The reference: what the seat perceives now, read from the live engine and disclosed by the projector's
    functions. `client` supplies only identities: the seat's generation, stream observer and world bounds."""
    members = live_members(world.session, audience)
    senses = audience_view(AudiencePerception(members=members), client.observer_uuid)
    if senses is None:
        return {category: {} for category in CATEGORIES}
    # An effect's duration is disclosed to its owner's controllers only (`_public_occurrences`).
    senses = replace(senses, spatial_effects={identity: effect if audience.controls(_effect_owner(identity))
        else effect.model_copy(update={'duration': None}) for identity, effect in senses.spatial_effects.items()})
    visible = _visible(senses)
    lights, _ = light_sources(AudiencePerception(members=members))
    target = PresentationTarget(generation=client.generation, observer_uuid=client.observer_uuid,
        recorded_world=WorldFacts(objects={identity: value for identity, value in world.objects.items()
            if support_cells(value.placement) & visible or identity in senses.objects}), senses=senses)
    observed = {identity for identity in target.objects if _object_observed(target, identity)}
    unremembered = PlayerState(generation=client.generation, observer_uuid=client.observer_uuid, world=client.world)
    actors = {}
    for identity, visual in _perceived_bodies(senses.entities, audience):
        state = _live_actor(world, identity)
        entity = world.session.game.entities.get(identity)
        if state is None or entity is None:
            actors[str(identity)] = None
            continue
        owned = audience.controls(identity)
        contact = senses.entities.get(identity)
        state = replace(state, last_visual_position=(contact.position if contact is not None else entity.position)
                        if visual else None)
        # The projector's disclosure of a body and its item records to this seat (`_public_changes`, `_public_items`).
        body = _public_actor(state, audience)
        body = replace(body, conditions=tuple(_public_condition(row, {}, {}, owned=owned) for row in body.conditions))
        actors[str(identity)] = {'body': _body(body, visual), 'items': _items({
            str(row.item_uuid): ITEM.dump_python(PlayerItem(look=row.look, profile=row.profile, state=row.state),
                                                 mode='json')
            for row in _public_items(_item_records(state, audience, {}), {}, owned=owned) if row.look is not None})}
    return {
        'cells': _cells(senses, visible),
        'member_cells': {str(member): sorted(key(position) for position in mask_positions(held.visible))
                         for member, held in members.items()},
        'entities': _contacts(senses.entities, members, objects=False),
        'object_contacts': _contacts(senses.objects, members, objects=True),
        'effects': _effects(senses.spatial_effects, members, visible),
        'lights': _lights(lights, members, visible),
        'tiles': {key(position): TILE.dump_python(tile, mode='json') if (tile := _live_tile(world, position)) else None
                  for position in sorted(visible)},
        'objects': {str(identity): OBJECT.dump_python(_perceived_object(_observed_object(target, unremembered, identity,
            observed), visible, observed, senses.spatial_effects), mode='json') for identity in sorted(observed, key=str)},
        'connectors': {str(row.connector_uuid): CONNECTOR.dump_python(row, mode='json')
                       for row in map(project_world_connector, get_map().get_all_connectors())
                       if all(tuple(point) in visible for point in row.endpoints)},
        'actors': actors,
    }


def _leaves(reference: Any, client: Any, path: str, found: list[tuple[str, Any, Any]]) -> None:
    if isinstance(reference, dict) and isinstance(client, dict):
        for name in sorted(reference.keys() | client.keys()):
            _leaves(reference.get(name, '<absent>'), client.get(name, '<absent>'), f'{path}.{name}' if path else name, found)
    elif reference != client:
        found.append((path, reference, client))


def differences(reference: View, client: View) -> list[dict[str, Any]]:
    """Every record held on one side only, and every differing field of a record held on both."""
    rows = []
    for category in CATEGORIES:
        expected, held = reference[category], client[category]
        for name in sorted(expected.keys() | held.keys()):
            if name not in held:
                rows.append({'category': category, 'key': name, 'kind': 'missing', 'reference': expected[name]})
            elif name not in expected:
                rows.append({'category': category, 'key': name, 'kind': 'extra', 'client': held[name]})
            elif expected[name] != held[name]:
                found: list[tuple[str, Any, Any]] = []
                _leaves(expected[name], held[name], '', found)
                for path, left, right in found:
                    if isinstance(left, list) and isinstance(right, list) and all(isinstance(row, str) for row in left + right):
                        left, right = sorted(set(left) - set(right)), sorted(set(right) - set(left))
                    rows.append({'category': category, 'key': name, 'kind': 'field', 'field': path,
                                 'reference': left, 'client': right})
    return rows


def signature(row: Mapping[str, Any]) -> str:
    """A difference's class across operations and seats: category, kind and field, without identities."""
    return f"{row['category']}:{row['kind']}:{row.get('field', '')}"


def examples(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    """The first rows of each class."""
    result: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        kept = result.setdefault(signature(row), [])
        if len(kept) < EXAMPLES:
            kept.append(row)
    return result


def summarize(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        name = signature(row)
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


@dataclass(slots=True)
class Oracle:
    """One oracle run's outputs under `directory`: the seats' spool (`server.recording`), the O3 views
    (`views.jsonl.gz`), and per seat the digest of its client state after each received record."""

    directory: Path
    recording: Recording
    views: IO[str]
    digests: dict[str, list[str]]
    report: list[dict[str, Any]] = field(default_factory=list)


def open_oracle(directory: Path, seats: Iterable[str]) -> Oracle:
    seats = tuple(seats)
    directory.mkdir(parents=True, exist_ok=False)
    return Oracle(directory, open_recording(directory / 'spool', seats, SPOOL_QUOTA),
                  gzip.open(directory / 'views.jsonl.gz', 'wt'), {seat: [] for seat in seats})


def receive(oracle: Oracle, seat: str, sequence: int, payload: bytes, state: PlayerState) -> None:
    """One record as the host spools it (stage, then commit), and the client state it folded into."""
    commit_records(oracle.recording, {seat: stage_record(oracle.recording, seat, sequence, payload)})
    oracle.digests[seat].append(state_digest(state))


def check(oracle: Oracle, operation: int, kind: str, session: Session, states: Mapping[str, PlayerState]) -> dict[str, Any]:
    """O1 for every seat at one operation's end; the client views are written as O3 rows."""
    world = live_world(session)
    seats = {}
    for seat, state in states.items():
        held = client_view(state)
        rows = differences(live_view(world, session.seats[seat], state), held)
        oracle.views.write(canonical({'operation': operation, 'kind': kind, 'seat': seat,
                                      'sequence': len(oracle.digests[seat]) - 1, 'view': held}) + '\n')
        seats[seat] = {'differences': len(rows), 'classes': summarize(rows), 'examples': examples(rows)}
    result = {'operation': operation, 'kind': kind, 'differences': sum(row['differences'] for row in seats.values()),
              'seats': seats}
    oracle.report.append(result)
    return result


def close_oracle(oracle: Oracle, manifest: dict[str, Any], states: Mapping[str, PlayerState]) -> None:
    """The replay manifest (identities, final publications, digests), each seat's final client state, the O1 report."""
    close_recording(oracle.recording)
    oracle.views.close()
    with gzip.open(oracle.directory / 'final_states.json.gz', 'wt') as out:
        out.write(canonical({seat: state_data(state) for seat, state in states.items()}))
    classes: dict[str, dict[str, int]] = {}
    for result in oracle.report:
        for seat, row in result['seats'].items():
            for name, count in row['classes'].items():
                classes.setdefault(name, {})
                classes[name][seat] = classes[name].get(seat, 0) + count
    (oracle.directory / 'manifest.json').write_text(json.dumps({**manifest, 'digests': oracle.digests}, indent=1))
    (oracle.directory / 'o1.json').write_text(json.dumps({'classes': classes, 'operations': oracle.report}, indent=1))


def _view_rows(directory: Path) -> dict[tuple[int, str, str], View]:
    with gzip.open(directory / 'views.jsonl.gz', 'rt') as rows:
        return {(row['operation'], row['kind'], row['seat']): row['view'] for row in map(json.loads, rows)}


def compare_views(base: Path, new: Path) -> dict[str, Any]:
    """O3: two oracle runs' perceived client states, operation by operation and seat by seat (the base's view
    in the reference role of `differences`)."""
    before, after = _view_rows(base), _view_rows(new)
    rows = {}
    for name in sorted(before.keys() | after.keys()):
        if name not in before or name not in after:
            rows[f'{name[0]}:{name[1]}:{name[2]}'] = {'only_in': 'base' if name in before else 'new'}
        elif canonical(before[name]) != canonical(after[name]):
            found = differences(before[name], after[name])
            rows[f'{name[0]}:{name[1]}:{name[2]}'] = {'classes': summarize(found), 'examples': examples(found)}
    return {'equal': not rows, 'compared': len(before.keys() & after.keys()), 'differing': rows}


def main() -> None:
    parser = argparse.ArgumentParser(description='O3: compare the perceived client states of two oracle runs.')
    parser.add_argument('command', choices=('compare',))
    parser.add_argument('base', type=Path)
    parser.add_argument('new', type=Path)
    args = parser.parse_args()
    result = compare_views(args.base, args.new)
    print(json.dumps({'equal': result['equal'], 'compared': result['compared'],
                      'differing': {name: row.get('classes', row) for name, row in result['differing'].items()}}, indent=1))
    sys.exit(0 if result['equal'] else 1)


if __name__ == '__main__':
    main()
