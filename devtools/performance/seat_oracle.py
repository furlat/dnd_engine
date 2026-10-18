"""Seat oracles over a live Gallery Crowd world (EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 §5 E0).

O1, perceived equality. At an operation's end each seat's perceived view is built twice, in one shape, and
`differences` lists every record held on one side only and every differing field of a record held on both:

- the reference, from the live engine: every member's current senses (`capture_senses_snapshot`), composed by
  `audience_view`; the visible cells' live tiles (`Tile.to_world_tile_state`); the live placed objects
  (`project_world_object`) through the seats' world publication rule (`world_publication.object_observed` and
  `disclosed_world_object`, which read no seat memory); the live connectors (`project_world_connector`); each perceived body read from its live aggregate
  (`Entity._entity_created_event`, `actor_from_birth`) and disclosed by the body record a seat receives when the
  body enters its view (`bodies.entering_body`, folded by the client's `enter_body`), which also withholds
  durations from non-owners (an effect's duration is withheld by the same rule applied to its live owner, the
  effect's condition's source);
- the client's, from the reference fold of the records the seat received (`dnd.player.reduction`), as held.

Both sides are what the seat perceives now: the composed visible cells with their light and hazard, each
member's visible cells (today's wire carries them; under Q1 (a) they leave it in E3, so O3 differs there by
design), the tiles of visible cells, the objects touching a visible cell or held
as a contact (each on its faces seen now, with the attachments in view and the protections of providers perceived
now: `_perceived_object`, the rest being seat memory), the connectors with both endpoints visible, the visible
cells of effects, the light sources with a visible footprint cell, the bodies of contacts and of the seat's own
members, and any living body the client draws at a visible cell without a contact (a ghost).

Fields left out of both sides, none of them a current perceived value:
- `applied_source_event_cursor` (conditions, item effects): the seat's own occurrence numbering;
- a condition's `event_uuid`, `resulting_*` and `consumed`: values as of its event (the body holds the current ones);
- an effect's `owner_revision`: the seat's own numbering of the effect's changes (`_observe_spatial_revisions`);
- a non-visual contact's `last_visual_position`: the last sighting.

O3: the client side of O1, written per operation and seat, is the perceived-state baseline (`views.jsonl.gz`).

O4, the disclosure boundary: a seat's knowledge is the union over operations of the flat (category, key, field
path, value) leaves of everything its client holds, memory included (`held_view`, O1's shapes and excluded
fields); each operation's new leaves are written per seat (`held.jsonl.gz`). Against a base run, every leaf the
new run's seat holds at operation k that the base run's did not hold by k is a leak: knowledge too early or
extra. An empty O4 report means no seat ever learned anything the base did not tell it; a change of wire shape
shows as leaks too and is listed by the lane that makes it.

`python seat_oracle.py compare <base> <new>` runs O3 and O4 on two runs recorded through gallery_transcript.py
(seeded identities: the views and leaves are keyed by them). O2's live side: `state_digest` of each seat's
whole client state after each record, and the spool of its records written through `server.recording`;
`spool_replay.py` replays it in a fresh process.
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
from dnd.core.item_types import ItemIntegrity
from dnd.core.events import WorldConnectorState, WorldTileState
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.player.actor_facts import ActorState
from dnd.player.audience import AudiencePerception, PlayerAudience, audience_view
from dnd.player.facts import (PlayerActor, PlayerCharacterSheet, PlayerItem, PlayerObject, PlayerState,
    SpatialEffectContent)
from dnd.player.bodies import entering_body
from dnd.player.reduction import enter_body
from dnd.player.static_sent import StaticSent
from dnd.player.world_publication import disclosed_world_object, object_observed
from dnd.player.session import Session
from dnd.types.actor_facts import ConditionMember
from dnd.types.cells import cell_in
from dnd.types.senses import PerceivedContact, PerceivedLightSource, PerceivedSpatialEffect, SensesSnapshot
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldObjectPlacement, boundary_sides, placement_support_cells
from dnd.world_authoring import project_world_connector, project_world_object
from dnd.world_facts import WorldFacts, _put_object, _Written, world_objects_at
from server.config import ServerConfig
from server.recording import Recording, close_recording, commit_records, open_recording, stage_record

Position = tuple[int, int]
View = dict[str, dict[str, Any]]
SPOOL_QUOTA: int = ServerConfig.model_fields['spool_limit_bytes'].default  # the server's per-seat spool limit
EXAMPLES = 3  # differences kept per class, seat and operation in the report

STATE = TypeAdapter(PlayerState)
TILE = TypeAdapter(WorldTileState)
OBJECT = TypeAdapter(PlayerObject)
CONNECTOR = TypeAdapter(WorldConnectorState)
ACTOR = TypeAdapter(PlayerActor)
ITEM = TypeAdapter(PlayerItem)
CONDITION = TypeAdapter(ConditionMember)
CONTACT = TypeAdapter(PerceivedContact)
EFFECT = TypeAdapter(PerceivedSpatialEffect)
LIGHT = TypeAdapter(PerceivedLightSource)
SPATIAL_CONTENT = TypeAdapter(SpatialEffectContent)
SHEET = TypeAdapter(PlayerCharacterSheet)

# Categories of a view, in report order.
# An object's members are exact only when its row is sent (D2): the client's `object_members` is "as of the
# last row", so they are no current perceived value here.
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
             visible: set[Position] | None) -> dict[str, Any]:
    """The visible part of each composed effect: its cells each member sees now (plan §3.2), and the members.
    With `visible` None (O4), every held cell."""
    result = {}
    for identity, effect in composed.items():
        seen_by = {str(member): sorted(key(position) for position in held.positions
                                       if visible is None or cell_in(senses.visible, position))
            for member, senses in members.items() if (held := senses.spatial_effects.get(identity)) is not None}
        positions = {position for position in effect.positions if visible is None or position in visible}
        if positions:
            result[str(identity)] = {**_effect(effect, positions), 'members': {
                member: cells for member, cells in seen_by.items() if cells}}
    return result


def _lights(composed: Mapping[UUID, PerceivedLightSource], members: Mapping[UUID, SensesSnapshot],
            visible: set[Position] | None) -> dict[str, Any]:
    """Each composed light source with its footprint on visible cells, and the members holding it. With
    `visible` None (O4), every held source with its whole footprint."""
    names = {key(position) for position in visible} if visible is not None else None
    result = {}
    for identity, source in composed.items():
        footprint = {cell: level for cell, level in source.affected_tiles.items() if names is None or cell in names}
        if visible is None or footprint or tuple(source.position) in visible:
            data = LIGHT.dump_python(source, mode='json')
            data['affected_tiles'] = dict(sorted(footprint.items()))
            data['members'] = sorted(str(member) for member, senses in members.items() if identity in senses.light_sources)
            result[str(identity)] = data
    return result


def _condition(condition: ConditionMember) -> dict[str, Any]:
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
        if item is not None:
            _schema16_item(item)
            for effect in item.get('effects', ()):
                effect.pop('applied_source_event_cursor', None)  # the seat's occurrence numbering
    return dict(items)


def _schema16_item(item: dict[str, Any]) -> None:
    """A held item in the schema-16 shape: before it, the effects travelled in the look (base recordings)."""
    look = item.get('look')
    if look is not None and 'item_effects' in look:
        item['effects'] = look.pop('item_effects')
    item.setdefault('effects', [])


def _shown_item_uuids(actor: PlayerActor, owned: bool) -> tuple[UUID, ...]:
    """The items whose records a body shows: its controller's inventory, anyone else's equipped layers."""
    if owned:
        return actor.controlled_items or ()
    return tuple(dict.fromkeys(layer.item_uuid for layer in actor.visual_loadout.layers))


def _seen_faces(placement: WorldObjectPlacement, visible: set[Position]) -> set[CardinalDirection]:
    """A boundary object's faces seen now: each face whose viewing cell is visible (`boundary_sides`, the one
    rule for a boundary's incident cells)."""
    return {face for face, cell in boundary_sides(placement) if cell in visible}


def _perceived_object(obj: PlayerObject, visible: set[Position], in_view: Collection[UUID],
                      effects: Mapping[UUID, PerceivedSpatialEffect],
                      contacts: Mapping[UUID, PerceivedContact]) -> PlayerObject:
    """A client-held object as perceived now: residues on the faces seen now, the attachments in view, the
    protections of providers perceived now, on cells seen now, and the contents while they are seen (open or
    broken, in visual contact: the client's display policy for the contents it keeps). The reference is the
    publication's `disclosed_world_object`, which reads no seat memory, so a slip in this restriction shows
    instead of hiding."""
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
    contact = contacts.get(obj.item.item_uuid)
    shown = (contact is not None and contact.visual
             and (obj.item.is_open is True or obj.item.integrity is ItemIntegrity.DESTROYED))
    return replace(obj, item=replace(obj.item, surface_residues=residues, remnant_state=remnant,
                                     construction_suppressions=protections),
                   contained_items=obj.contained_items if shown else None)


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
               if placement_support_cells(obj.placement) & visible or identity in senses.objects}
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
            senses.spatial_effects, senses.objects), mode='json') for identity in sorted(in_view, key=str)},
        'connectors': {str(row.connector_uuid): CONNECTOR.dump_python(row, mode='json')
                       for row in state.connectors.values() if all(tuple(point) in visible for point in row.endpoints)},
        'actors': actors,
    }


def held_view(state: PlayerState) -> View:
    """O4: everything the client holds, memory included, in O1's shapes and without O1's excluded fields: the
    current cells and contacts, every seen cell, every held effect, light, tile, object, connector, body (with its
    last sighting), item record, effect content, admitted content identity, the HUD and the turn. Left out as
    bookkeeping, not knowledge: the fold's cursors and arbitration provenance (`reducer_cursor`,
    `spatial_commit_cursors`, the perception's cursors and absences) and the combat log (plan Q2, gated apart)."""
    senses = state.senses
    members = state.perception.members or ({state.observer_uuid: senses} if senses is not None else {})
    hud = state.hud_snapshot
    return {
        'cells': _cells(senses, _visible(senses)) if senses is not None else {},
        'seen': {key(position): True for position in mask_positions(senses.seen)} if senses is not None else {},
        'member_cells': {str(member): sorted(key(position) for position in mask_positions(held.visible))
                         for member, held in members.items()},
        'entities': _contacts(senses.entities, members, objects=False) if senses is not None else {},
        'object_contacts': _contacts(senses.objects, members, objects=True) if senses is not None else {},
        'effects': _effects(senses.spatial_effects, members, None) if senses is not None else {},
        'lights': _lights(senses.light_sources, members, None) if senses is not None else {},
        'tiles': {key(position): TILE.dump_python(tile, mode='json') for position, tile in state.tiles.items()},
        'objects': {str(identity): OBJECT.dump_python(obj, mode='json') for identity, obj in state.objects.items()},
        'connectors': {str(row.connector_uuid): CONNECTOR.dump_python(row, mode='json')
                       for row in state.connectors.values()},
        'actors': {str(identity): {'body': _body(actor, True)} for identity, actor in state.actors.items()},
        'items': _items({str(identity): ITEM.dump_python(item, mode='json') for identity, item in state.items.items()}),
        'spatial_content': {str(identity): SPATIAL_CONTENT.dump_python(content, mode='json')
                            for identity, content in state.spatial_content.items()},
        'content': {row.ref.identity_key: True for row in state.content},
        'hud': {str(sheet.actor_uuid): SHEET.dump_python(sheet, mode='json') for sheet in hud.sheets}
               | {'initiative': {'order': ','.join(map(str, hud.initiative))}}
               if hud is not None else {},
        'turn': {'current': {'actor': str(state.current_actor_uuid), 'round': state.round_number}},
    }


Leaf = tuple[str, str, str, str]  # category, record key, field path, canonical value


def _flatten(category: str, name: str, path: str, value: Any, found: set[Leaf]) -> None:
    if isinstance(value, dict):
        if not value:
            found.add((category, name, path, '{}'))
        for field_name, item in value.items():
            _flatten(category, name, f'{path}.{field_name}' if path else field_name, item, found)
    elif isinstance(value, list):
        if not value:
            found.add((category, name, path, '[]'))
        for item in value:  # a list is a set of facts: one leaf per element
            found.add((category, name, f'{path}[]', canonical(item)))
    else:
        found.add((category, name, path, canonical(value)))


def leaves(view: View) -> set[Leaf]:
    """A view as its flat (category, key, field path, value) leaves."""
    found: set[Leaf] = set()
    for category, records in view.items():
        for name, value in records.items():
            _flatten(category, name, '', value, found)
    return found


@dataclass(slots=True)
class LiveWorld:
    """One operation end's live reads, shared by every seat: bodies and tiles read once each, when first needed."""

    session: Session
    actors: dict[UUID, ActorState | None] = field(default_factory=dict)
    tiles: dict[Position, WorldTileState | None] = field(default_factory=dict)
    # Every placed object's live value, indexed by the recorded world's own writer.
    objects: WorldFacts = field(default_factory=WorldFacts)


def live_world(session: Session) -> LiveWorld:
    world = LiveWorld(session)
    for placement in get_map().iter_object_placements():
        item = BaseBlock.get(placement.object_uuid)
        if not isinstance(item, BaseItem):
            raise TypeError(f'Placed object {placement.object_uuid} is not a BaseItem')
        _put_object(world.objects, placement.object_uuid, project_world_object(item, placement), _Written())
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
    # An effect's duration is disclosed to its owner's controllers only (the rule of `_public_occurrences`,
    # applied to the live owner: the effect's condition's source).
    senses = replace(senses, spatial_effects={identity: effect if audience.controls(_effect_owner(identity))
        else effect.model_copy(update={'duration': None}) for identity, effect in senses.spatial_effects.items()})
    visible = _visible(senses)
    candidates = world_objects_at(world.objects, visible) | (senses.objects.keys() & world.objects.objects.keys())
    observed = {identity for identity in candidates if object_observed(world.objects, senses, identity)}
    actors = {}
    for identity, visual in _perceived_bodies(senses.entities, audience):
        state = _live_actor(world, identity)
        entity = world.session.game.entities.get(identity)
        if state is None or entity is None:
            actors[str(identity)] = None
            continue
        contact = senses.entities.get(identity)
        state = replace(state, last_visual_position=(contact.position if contact is not None else entity.position)
                        if visual else None)
        # The seat's body record of this body entering its view now, as its client folds it.
        record = entering_body(0, state, audience, visual=visual, birth=True, sent=StaticSent(), pending=StaticSent())
        held = PlayerState(generation=client.generation, observer_uuid=client.observer_uuid, world=client.world,
            audience=audience)
        enter_body(held, record)
        body = replace(held.actors[identity], last_visual_position=state.last_visual_position)
        actors[str(identity)] = {'body': _body(body, visual), 'items': _items({
            str(row.item_uuid): ITEM.dump_python(held.items[row.item_uuid], mode='json') for row in record.items})}
    return {
        'cells': _cells(senses, visible),
        'member_cells': {str(member): sorted(key(position) for position in mask_positions(held.visible))
                         for member, held in members.items()},
        'entities': _contacts(senses.entities, members, objects=False),
        'object_contacts': _contacts(senses.objects, members, objects=True),
        'effects': _effects(senses.spatial_effects, members, visible),
        'lights': _lights(senses.light_sources, members, visible),
        'tiles': {key(position): TILE.dump_python(tile, mode='json') if (tile := _live_tile(world, position)) else None
                  for position in sorted(visible)},
        'objects': {str(identity): OBJECT.dump_python(disclosed_world_object(world.objects, senses, identity, observed),
                                                      mode='json') for identity in sorted(observed, key=str)},
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
        if category not in reference or category not in client:
            continue  # a view recorded before the category existed (O3 against an older base)
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
    (`views.jsonl.gz`), the O4 knowledge each operation added (`held.jsonl.gz`, with `known` the union so far
    per seat), and per seat the digest of its client state after each received record."""

    directory: Path
    recording: Recording
    views: IO[str]
    held: IO[str]
    digests: dict[str, list[str]]
    known: dict[str, set[Leaf]]
    report: list[dict[str, Any]] = field(default_factory=list)


def open_oracle(directory: Path, seats: Iterable[str]) -> Oracle:
    seats = tuple(seats)
    directory.mkdir(parents=True, exist_ok=False)
    return Oracle(directory, open_recording(directory / 'spool', seats, SPOOL_QUOTA),
                  gzip.open(directory / 'views.jsonl.gz', 'wt'), gzip.open(directory / 'held.jsonl.gz', 'wt'),
                  {seat: [] for seat in seats}, {seat: set() for seat in seats})


def receive(oracle: Oracle, seat: str, sequence: int, payload: bytes, state: PlayerState) -> None:
    """One record as the host spools it (stage, then commit), and the client state it folded into."""
    commit_records(oracle.recording, {seat: stage_record(oracle.recording, seat, sequence, payload)})
    oracle.digests[seat].append(state_digest(state))


def check(oracle: Oracle, operation: int, kind: str, session: Session, states: Mapping[str, PlayerState]) -> dict[str, Any]:
    """O1 for every seat at one operation's end; the client views are written as O3 rows, and the leaves of its
    whole held state that it did not hold before as O4 rows."""
    world = live_world(session)
    seats = {}
    for seat, state in states.items():
        held = client_view(state)
        rows = differences(live_view(world, session.seats[seat], state), held)
        sequence = len(oracle.digests[seat]) - 1
        oracle.views.write(canonical({'operation': operation, 'kind': kind, 'seat': seat,
                                      'sequence': sequence, 'view': held}) + '\n')
        added = leaves(held_view(state)) - oracle.known[seat]
        oracle.known[seat] |= added
        oracle.held.write(canonical({'operation': operation, 'kind': kind, 'seat': seat, 'sequence': sequence,
                                     'added': sorted(added)}) + '\n')
        seats[seat] = {'differences': len(rows), 'classes': summarize(rows), 'examples': examples(rows)}
    result = {'operation': operation, 'kind': kind, 'differences': sum(row['differences'] for row in seats.values()),
              'seats': seats}
    oracle.report.append(result)
    return result


def close_oracle(oracle: Oracle, manifest: dict[str, Any], states: Mapping[str, PlayerState]) -> None:
    """The replay manifest (identities, final publications, digests), each seat's final client state, the O1 report."""
    close_recording(oracle.recording)
    oracle.views.close()
    oracle.held.close()
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


def _schema16_view(view: View) -> View:
    """A stored view in the schema-16 item shape (base recordings held item effects in the look)."""
    for actor in view.get('actors', {}).values():
        for item in (actor or {}).get('items', {}).values():
            if item is not None:
                _schema16_item(item)
    return view


def _schema16_leaf(leaf: Leaf) -> Leaf:
    """A stored O4 leaf in the schema-16 item shape."""
    category, name, path, value = leaf
    if category == 'items' and path.startswith('look.item_effects'):
        return category, name, 'effects' + path[len('look.item_effects'):], value
    return leaf


def _view_rows(directory: Path) -> dict[tuple[int, str, str], View]:
    with gzip.open(directory / 'views.jsonl.gz', 'rt') as rows:
        return {(row['operation'], row['kind'], row['seat']): _schema16_view(row['view']) for row in map(json.loads, rows)}


def _held_rows(directory: Path) -> dict[str, list[tuple[int, str, list[Leaf]]]]:
    rows: dict[str, list[tuple[int, str, list[Leaf]]]] = {}
    with gzip.open(directory / 'held.jsonl.gz', 'rt') as source:
        for row in map(json.loads, source):
            rows.setdefault(row['seat'], []).append((row['operation'], row['kind'],
                [_schema16_leaf((leaf[0], leaf[1], leaf[2], leaf[3])) for leaf in row['added']]))
    return rows


def knowledge_leaks(base: Iterable[Leaf], new: Iterable[Leaf]) -> list[Leaf]:
    """O4 at one operation: what the new run's seat holds that the base run's did not hold by then."""
    return sorted(set(new) - set(base))


def compare_knowledge(base: Path, new: Path) -> dict[str, list[dict[str, Any]]]:
    """O4 between two oracle runs: per seat, each leaf of the new run's knowledge union at operation k that is
    absent from the base run's union at k, reported at the first such operation (learned earlier, or extra)."""
    before, after = _held_rows(base), _held_rows(new)
    report: dict[str, list[dict[str, Any]]] = {}
    for seat in sorted(before.keys() | after.keys()):
        base_known: set[Leaf] = set()
        new_known: set[Leaf] = set()
        reported: set[Leaf] = set()
        base_rows, new_rows = before.get(seat, []), after.get(seat, [])
        for index in range(max(len(base_rows), len(new_rows))):
            if index < len(base_rows):
                base_known.update(base_rows[index][2])
            if index < len(new_rows):
                operation, kind, added = new_rows[index]
                new_known.update(added)
                for leaf in knowledge_leaks(base_known, new_known - reported):
                    reported.add(leaf)
                    report.setdefault(seat, []).append({'operation': operation, 'kind': kind, 'category': leaf[0],
                        'key': leaf[1], 'field': leaf[2], 'value': leaf[3]})
    return report


def compare_views(base: Path, new: Path) -> dict[str, Any]:
    """O3: two oracle runs' perceived client states, operation by operation and seat by seat (the base's view
    in the reference role of `differences`). Views are keyed by identities, so both runs must have been recorded
    with seeded identities (`gallery_transcript.py record ... --oracle DIR`)."""
    for directory in (base, new):
        if json.loads((directory / 'manifest.json').read_text()).get('identities') != 'seeded':
            raise ValueError(f'{directory}: not recorded with seeded identities; its views are not comparable')
    before, after = _view_rows(base), _view_rows(new)
    rows = {}
    for name in sorted(before.keys() | after.keys()):
        if name not in before or name not in after:
            rows[f'{name[0]}:{name[1]}:{name[2]}'] = {'only_in': 'base' if name in before else 'new'}
        elif canonical(before[name]) != canonical(after[name]):
            found = differences(before[name], after[name])
            rows[f'{name[0]}:{name[1]}:{name[2]}'] = {'classes': summarize(found), 'examples': examples(found)}
    leaks = compare_knowledge(base, new)
    return {'equal': not rows, 'compared': len(before.keys() & after.keys()), 'differing': rows,
            'knowledge_bounded': not leaks, 'leaks': leaks}


def main() -> None:
    parser = argparse.ArgumentParser(description='O3 and O4: compare the perceived client states of two oracle runs, '
                                     'and report what the new run\'s seats knew that the base run\'s did not.')
    parser.add_argument('command', choices=('compare',))
    parser.add_argument('base', type=Path)
    parser.add_argument('new', type=Path)
    args = parser.parse_args()
    result = compare_views(args.base, args.new)
    leak_classes: dict[str, int] = {}
    for rows in result['leaks'].values():
        for row in rows:
            name = f"{row['category']}:{row['field']}"
            leak_classes[name] = leak_classes.get(name, 0) + 1
    print(json.dumps({'equal': result['equal'], 'compared': result['compared'],
                      'differing': {name: row.get('classes', row) for name, row in result['differing'].items()},
                      'knowledge_bounded': result['knowledge_bounded'], 'leak_classes': leak_classes,
                      'leaks': {seat: rows[:20] for seat, rows in result['leaks'].items()}}, indent=1))
    sys.exit(0 if result['equal'] and result['knowledge_bounded'] else 1)


if __name__ == '__main__':
    main()
