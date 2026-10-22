"""Reduce and stage saved player packets without native event projection."""

from dataclasses import dataclass, replace
import json
from typing import Collection, Iterator, Mapping, Sequence
from dnd.types.actor import SpatialDisposition
from dnd.types.actor_facts import (ChangeField, ChangeRow, ConditionMember, ConditionRow, DispositionRow, DurationRow,
    GrantRow, InventoryRow, ItemEffectsRow, ItemStateRow, LayerRow, NumberRow, SizeRow, WeaponSetRow, dropped, upserted)
from dnd.types.item_parts import VisualItem
from dnd.core.cells import (CellRows, bit_rows, layer_rows, mask_positions, mask_rows, mask_union, selected_mask,
    selected_values, update_cells)
from dnd.core.sensory_fold import copy_senses_snapshot, sense_modes_key
from uuid import UUID

from dnd.core.content.descriptors import ContentDescriptor
from dnd.core.item_types import ItemEffectPresentationState
from dnd.core.life_types import LifeState
from dnd.types.cells import EMPTY_CELLS, EMPTY_VALUES, CellMask, cell_in
from dnd.types.event_facts import EventType, SpatialChangeType
from dnd.types.senses import PerceivedContact, PerceivedSpatialEffect, SensesSnapshot
from dnd.player.audience import PlayerAudience, perceived_entities, resolve_audience
from dnd.player.facts import (
    AudienceFact, ActorBirth, ActorChangeFact, BodyRecord, ItemRecord, AttackFact, DamageResultFact, HealFact, ItemChargeFact, LifeFact, PlayerItem,
    PlayerActor, PlayerCharacterSheet, PlayerFact, SheetChanges, SheetPatch, PlayerHUDPatch, PlayerHUDSnapshot, PlayerInitialization, PlayerLineage, PlayerNode, PlayerSequence,
    PlayerState, PlayerUpdate, SensoryFact, SensoryRows, SpatialEffectContent, SpatialEffectSighting, SpatialFact, TurnFact,
    VersionRows, WorldUpdate, TemporaryHitPointsFact, FactionFact, PlayerObject, StaticStore, PlayerLightSource,
    PlayerResolution, SpellFact, LightPatch, LightRow, SpatialEffectPatch,
)
from dnd.player.spatial_commits import commit_current
from dnd.player.world_columns import join_floor_item, unpack_object_rows, unpack_placement, unpack_tile_columns
from dnd.player.world_reduction import fold_static_rows, fold_world_update


# These received families have ordinary state presentation, without a separate
# actor cue. This describes the reducer below; it is not a second dispatcher.
STATE_PRESENTATION_KINDS = frozenset({
    "temporary_hit_points", "spatial", "turn", "sensory", "audience", "item_charge", "faction",
})


def copy_target(target: PlayerState) -> PlayerState:
    senses = target.senses
    return replace(target, tiles=dict(target.tiles), objects=dict(target.objects),
        object_members=dict(target.object_members), connectors=dict(target.connectors),
        static=StaticStore(tiles=dict(target.static.tiles), tile_looks=dict(target.static.tile_looks),
            residues=dict(target.static.residues),
            object_looks=dict(target.static.object_looks),
            boundary_structures=dict(target.static.boundary_structures),
            visual_loadouts=dict(target.static.visual_loadouts)), actors=dict(target.actors),
        items=dict(target.items), spatial_content=dict(target.spatial_content),
        spatial_commit_cursors=dict(target.spatial_commit_cursors),
        senses=None if senses is None else copy_senses_snapshot(senses),
        entity_members=dict(target.entity_members), object_contact_members=dict(target.object_contact_members),
        effect_members=dict(target.effect_members), light_sources=dict(target.light_sources),
        remembered_effects=dict(target.remembered_effects))


def enter_item(target: PlayerState, record: ItemRecord) -> None:
    """An item entering the seat's view: static parts kept from the first time, dynamic parts replaced whole.

    The seat's item records are never pruned; a record without a look needs one the seat already holds.
    """
    previous = target.items.get(record.item_uuid)
    look = record.look if record.look is not None else previous.look if previous is not None else None
    if look is None:
        raise ValueError("An item's first record requires its look")
    target.items[record.item_uuid] = PlayerItem(look=look,
        profile=record.profile if record.profile is not None else previous.profile if previous is not None else None,
        state=record.state if record.state is not None else previous.state if previous is not None else None,
        effects=record.effects)


def _birth(actor: PlayerActor) -> ActorBirth:
    """The birth fields a seat holds for a body."""
    return ActorBirth(name=actor.name, character_body_id=actor.character_body_id,
        creature_content_ref=actor.creature_content_ref, appearance=actor.appearance,
        structural_base_size=actor.structural_base_size, manifestation=actor.manifestation)


def enter_body(target: PlayerState, record: BodyRecord) -> None:
    """A body entering the seat's view: every changeable field replaced, its birth held from the first record.

    Its visual loadout is the value of its content id (sent with the record the first time, then held). The items
    it shows without a record have no effects. The last visual position stays perception (contacts set it); a
    terminal lifetime ignores the record.
    """
    previous = target.actors.get(record.actor_uuid)
    if previous is not None and not previous.present:
        return
    birth = record.birth if record.birth is not None else _birth(previous) if previous is not None else None
    if birth is None:
        raise ValueError("A body's first record requires its birth")
    body = record.body
    loadouts = target.static.visual_loadouts
    if record.loadout is not None and loadouts.setdefault(body.visual_loadout_id, record.loadout) != record.loadout:
        raise ValueError("A visual loadout id names one value")
    loadout = loadouts[body.visual_loadout_id]
    target.actors[record.actor_uuid] = PlayerActor(uuid=record.actor_uuid, name=birth.name,
        character_body_id=birth.character_body_id, creature_content_ref=birth.creature_content_ref,
        appearance=birth.appearance, structural_base_size=birth.structural_base_size,
        manifestation=birth.manifestation, visual_loadout=loadout, normal_hp=body.normal_hp,
        maximum_hp=body.maximum_hp, temporary_hp=body.temporary_hp, temporary_hp_grant=body.temporary_hp_grant,
        life_state=body.life_state, armor_class=body.armor_class, conditions=body.conditions,
        controlled_items=body.controlled_items, occupancy_layer=body.occupancy_layer,
        resolved_size=body.resolved_size, faction=body.faction, remains_disposition=body.remains_disposition,
        spatial_disposition=body.spatial_disposition,
        last_visual_position=previous.last_visual_position if previous is not None else None)
    for item in record.items:
        enter_item(target, item)
    recorded = {item.item_uuid for item in record.items}
    shown = (body.controlled_items if body.controlled_items is not None
             else tuple(dict.fromkeys(layer.item_uuid for layer in loadout.layers)))
    for identity in shown:
        if identity not in recorded and (held := target.items.get(identity)) is not None and held.effects:
            target.items[identity] = replace(held, effects=())


def _condition_key(member: ConditionMember) -> UUID:
    return member.condition_uuid


def _layer_slot(layer: VisualItem) -> str:
    return layer.slot


def _item_uuid(identity: UUID) -> UUID:
    return identity


def _effect_key(effect: ItemEffectPresentationState) -> UUID:
    return effect.effect_uuid


def _changed_item(target: PlayerState, row: DurationRow | ItemEffectsRow | ItemStateRow) -> None:
    """An item row's change to the seat's record of that item; a record the seat lacks stays absent."""
    item_uuid = row.item_uuid
    record = target.items.get(item_uuid) if item_uuid is not None else None
    if item_uuid is None or record is None:
        return
    match row:
        case DurationRow():
            effect = next((effect for effect in record.effects if effect.effect_uuid == row.key), None)
            if effect is not None:
                target.items[item_uuid] = replace(record, effects=upserted(record.effects, _effect_key,
                    effect.model_copy(update={"duration": row.duration})))
        case ItemEffectsRow():
            target.items[item_uuid] = replace(record, effects=row.effects)
        case ItemStateRow():
            if record.state is not None:
                target.items[item_uuid] = replace(record, state=replace(record.state, **row.changes))


def _changed_actor(target: PlayerState, actor: PlayerActor, row: ChangeRow) -> PlayerActor:
    """One row applied to a body (or, for an item row, to the seat's record of that item), in dict order."""
    match row:
        case NumberRow(field=ChangeField.NORMAL_HP):
            return replace(actor, normal_hp=row.value)
        case NumberRow(field=ChangeField.MAXIMUM_HP):
            return replace(actor, maximum_hp=row.value)
        case NumberRow(field=ChangeField.TEMPORARY_HP):
            return replace(actor, temporary_hp=row.value)
        case NumberRow(field=ChangeField.ARMOR_CLASS):
            return replace(actor, armor_class=row.value)
        case GrantRow():
            return replace(actor, temporary_hp_grant=row.value)
        case SizeRow():
            return replace(actor, resolved_size=row.value)
        case DispositionRow():
            return replace(actor, spatial_disposition=row.value)
        case WeaponSetRow():
            return replace(actor, visual_loadout=replace(actor.visual_loadout, active_weapon_set=row.value))
        case ConditionRow(member=None):
            return replace(actor, conditions=dropped(actor.conditions, _condition_key, row.condition_uuid))
        case ConditionRow(member=ConditionMember() as member):
            return replace(actor, conditions=upserted(actor.conditions, _condition_key, member))
        case DurationRow(field=ChangeField.CONDITION_DURATION):
            held = next((member for member in actor.conditions if member.condition_uuid == row.key), None)
            if held is None or held.state is None:
                return actor
            return replace(actor, conditions=upserted(actor.conditions, _condition_key,
                replace(held, state=held.state.model_copy(update={"duration": row.duration}))))
        case LayerRow(layer=None):
            return replace(actor, visual_loadout=replace(actor.visual_loadout,
                layers=dropped(actor.visual_loadout.layers, _layer_slot, row.slot)))
        case LayerRow(layer=VisualItem() as layer):
            return replace(actor, visual_loadout=replace(actor.visual_loadout,
                layers=upserted(actor.visual_loadout.layers, _layer_slot, layer)))
        case InventoryRow():
            if actor.controlled_items is None:
                raise ValueError("inventory rows require the controlled actor's inventory")
            return replace(actor, controlled_items=upserted(actor.controlled_items, _item_uuid, row.item_uuid)
                if row.held else dropped(actor.controlled_items, _item_uuid, row.item_uuid))
        case DurationRow() | ItemEffectsRow() | ItemStateRow():
            _changed_item(target, row)
    return actor


def apply_actor_change_fact(target: PlayerState, fact: ActorChangeFact) -> None:
    """An event's change to the seat's bodies: the items entering its view, then each actor's rows in order.

    A terminal lifetime ignores its rows.
    """
    for record in fact.items:
        enter_item(target, record)
    for change in fact.actors:
        actor = target.actors[change.actor_uuid]
        if not actor.present:
            continue
        for row in change.rows:
            actor = _changed_actor(target, actor, row)
        target.actors[actor.uuid] = actor


def clear_unseen_positions(target: PlayerState) -> None:
    """A cell the seat sees shows what is there: a living body last seen on a visible cell that is no longer a
    contact is no longer drawn there (its other values stay remembered)."""
    senses = target.senses
    if senses is None:
        return
    audience = target.viewing_audience
    for identity, actor in tuple(target.actors.items()):
        position = actor.last_visual_position
        if (position is not None and actor.present and actor.life_state is not LifeState.DEAD
                and not audience.controls(identity) and identity not in senses.entities
                and cell_in(senses.visible, position)):
            target.actors[identity] = replace(actor, last_visual_position=None)


def stage_actors(target: PlayerState, bodies: tuple[BodyRecord, ...]) -> PlayerState:
    """Supply absent bodies for binding; existing historical actors win."""
    result = copy_target(target)
    for record in bodies:
        if record.actor_uuid not in result.actors:
            enter_body(result, record)
    return result


def stage_static(target: PlayerState, updates: tuple[WorldUpdate, ...]) -> None:
    """The updates' static rows, which never change for their id: a partial fold of a group reads them."""
    for update in updates:
        fold_static_rows(target.static, update)


def stage_lineage(target: PlayerState, lineage: PlayerLineage) -> PlayerState:
    """Supply absent binding contacts without advancing known world geometry."""
    result = stage_actors(target, lineage.bodies)
    stage_static(result, lineage.world_updates)
    for update in lineage.world_updates:
        if update.tile_columns is not None:
            for position, tile in unpack_tile_columns(update.tile_columns, result.static.tiles,
                    result.static.tile_looks).items():
                result.tiles.setdefault(position, tile)
        for row in unpack_object_rows(update.objects):
            if row.placement is not None and row.item_uuid not in result.objects:
                result.objects[row.item_uuid] = PlayerObject(
                    placement=unpack_placement(row.item_uuid, row.placement, result.static.tiles),
                    item=join_floor_item(result.static.object_looks[row.item_uuid], row.state,
                        result.static.boundary_structures))
        for connector in update.connectors:
            result.connectors.setdefault(connector.connector_uuid, connector)
    return result


def _unique(values: dict, indices: tuple[int, ...]) -> dict:
    if len(values) != len(indices):
        raise ValueError("A sensory fact names two rows of one identity in one list")
    return values


@dataclass(frozen=True, slots=True, eq=False)
class ComposedValues:
    """A schema-16 group's rows as the fold reads them, resolved once per group: contact values and cell tables."""

    rows: SensoryRows
    contacts: tuple[PerceivedContact, ...]
    cells: CellRows
    light_levels: CellRows
    hazards: CellRows


def composed_values(rows: SensoryRows) -> ComposedValues:
    visual = set(bit_rows(rows.contact_visual, len(rows.contact_positions)).tolist())
    senses = rows.contact_special_senses or ((),) * len(rows.contact_positions)
    contacts = tuple(PerceivedContact.model_construct(position=position, visual=index in visual,
        special_senses=senses[index]) for index, position in enumerate(rows.contact_positions))
    return ComposedValues(rows, contacts, mask_rows(rows.cells), layer_rows(rows.light_levels), layer_rows(rows.hazards))


def _row_members(column: tuple[int, ...], index: int, observers: int) -> int:
    """A row's member bitset; a one-observer seat's rows leave it out (they are that observer's)."""
    if column:
        return column[index]
    if observers != 1:
        raise ValueError("A seat with several observers names the members of each row")
    return 1


def _sighted_effect(sighting: SpatialEffectSighting, content: SpatialEffectContent) -> PerceivedSpatialEffect:
    """The perceived effect of an entering sighting and its content (both validated); its cell sets in cell order."""
    return PerceivedSpatialEffect.model_construct(duration=sighting.duration, content_ref=content.content_ref,
        name=content.name, description=content.description, positions=tuple(mask_positions(sighting.positions)),
        owner_revision=None, apparent_presence=sighting.apparent_presence,
        trap_state=sighting.trap_state, pressed=sighting.pressed, direction=sighting.direction,
        anchor_item_uuid=sighting.anchor_item_uuid, anchor_entity_uuid=sighting.anchor_entity_uuid,
        energy_type=sighting.energy_type, presence_mode=sighting.presence_mode,
        sustainer_item_uuid=sighting.sustainer_item_uuid, concentration_slot_uuid=sighting.concentration_slot_uuid,
        anchor_position=sighting.anchor_position, anchor_elevation_steps=sighting.anchor_elevation_steps,
        area_geometry=sighting.area_geometry, construction_sections=sighting.construction_sections,
        area_propagation=sighting.area_propagation, deposit_source=sighting.deposit_source,
        visible_volume_positions=tuple(mask_positions(sighting.visible_volume_positions)),
        upper_volume_surfaces=sighting.upper_volume_surfaces, suppressions=sighting.suppressions)


def _changed_cells(held: tuple[tuple[int, int], ...], added: CellMask, removed: CellMask) -> tuple[tuple[int, int], ...]:
    """A held cell set after a change that removes held cells and adds new ones."""
    cells, gone, new = set(held), set(mask_positions(removed)), set(mask_positions(added))
    if not gone <= cells or new & cells:
        raise ValueError("A patch removes only held cells and adds only new ones")
    return tuple(sorted((cells - gone) | new))


def _patched_effect(before: PerceivedSpatialEffect, patch: SpatialEffectPatch) -> PerceivedSpatialEffect:
    """A perceived effect after its patch: cell sets changed, upper surfaces changed by key, changed fields replaced."""
    removed = set(patch.upper_removed)
    upper = {(row.position, row.lower_height_planes): row for row in before.upper_volume_surfaces}
    if not removed <= upper.keys():
        raise ValueError("A patch removes only held volume surfaces")
    for key in removed:
        del upper[key]
    upper.update(((row.position, row.lower_height_planes), row) for row in patch.upper_added)
    return before.model_copy(update={**patch.changes,
        "positions": _changed_cells(before.positions, patch.positions_added, patch.positions_removed),
        "visible_volume_positions": _changed_cells(before.visible_volume_positions, patch.volume_added,
                                                   patch.volume_removed),
        "upper_volume_surfaces": tuple(upper[key] for key in sorted(upper))})


def _light_source(row: LightRow, uuids: tuple[UUID, ...]) -> PlayerLightSource:
    return PlayerLightSource(source_uuid=uuids[row.source], position=row.position,
        base_height_steps=row.base_height_steps, very_bright_radius_feet=row.very_bright_radius_feet,
        bright_radius_feet=row.bright_radius_feet, dim_radius_feet=row.dim_radius_feet, appearance=row.appearance,
        actor_anchored=row.actor_anchored,
        anchor_entity_uuid=uuids[row.anchor_entity] if row.anchor_entity is not None else None,
        anchor_item_uuid=uuids[row.anchor_item] if row.anchor_item is not None else None)


def _patched_light(before: PlayerLightSource, patch: LightPatch, uuids: tuple[UUID, ...]) -> PlayerLightSource:
    """A perceived light source with its patch's changed fields; anchors name `uuids` (None: undisclosed)."""
    changes = patch.changes
    entity, item = changes.get("anchor_entity"), changes.get("anchor_item")
    return replace(before,
        position=changes.get("position", before.position),
        base_height_steps=changes.get("base_height_steps", before.base_height_steps),
        very_bright_radius_feet=changes.get("very_bright_radius_feet", before.very_bright_radius_feet),
        bright_radius_feet=changes.get("bright_radius_feet", before.bright_radius_feet),
        dim_radius_feet=changes.get("dim_radius_feet", before.dim_radius_feet),
        appearance=changes.get("appearance", before.appearance),
        actor_anchored=changes.get("actor_anchored", before.actor_anchored),
        anchor_entity_uuid=(uuids[entity] if entity is not None else None) if "anchor_entity" in changes
            else before.anchor_entity_uuid,
        anchor_item_uuid=(uuids[item] if item is not None else None) if "anchor_item" in changes
            else before.anchor_item_uuid)


def _remember_effects(memory: dict[UUID, PerceivedSpatialEffect], effects: Mapping[UUID, PerceivedSpatialEffect],
                      left: Mapping[UUID, tuple[PerceivedSpatialEffect, set[tuple[int, int]]]],
                      retired: Mapping[UUID, set[tuple[int, int]]], visible: CellMask) -> None:
    """The client's effect memory after a change (plan §3.2; found effects are kept until a member saw their cells empty).

    Cells that left an effect's visible part are remembered with the effect as last perceived. A remembered
    cell is forgotten when it is in the effect's visible part again (it is perceived), when a member saw the
    effect leave it (`retired`), or, for an apparent effect, when the cell is seen without it: anyone seeing an
    apparent effect's cell perceives it there. A concealed effect's cell seen by a member that never found it
    stays remembered.
    """
    for identity, (row, cells) in left.items():
        held = memory.get(identity)
        if cells or held is not None:
            memory[identity] = row.model_copy(update={
                "positions": tuple(sorted(cells | set(held.positions if held is not None else ()))),
                "visible_volume_positions": (), "upper_volume_surfaces": ()})
    for identity in tuple(memory):
        row = memory[identity]
        current = effects.get(identity)
        perceived = set(current.positions) if current is not None else set()
        gone = retired.get(identity, set())
        apparent = (current if current is not None else row).apparent_presence
        kept = tuple(position for position in row.positions if position not in perceived and position not in gone
                     and not (apparent and cell_in(visible, position)))
        if not kept:
            del memory[identity]
        elif kept != row.positions:
            memory[identity] = row.model_copy(update={"positions": kept})


def fold_composed_sensory(target: PlayerState, fact: SensoryFact, values: ComposedValues) -> None:
    """Fold one settlement's change of the seat's composed perception (a received fact of the group `values`).

    It updates what the seat perceives now (`senses`: cells, contacts, effects and the anchor's scalars), the
    members perceiving each contact and effect, the light sources perceived now, and the client's memory: seen
    cells are every cell seen visible; effects keep their remembered cells (`_remember_effects`). The anchor's
    changed position places the stream observer's body, and visual contacts the bodies the seat holds. A list
    naming a record the seat does not hold (or, for an entering record, does hold) raises ValueError.
    """
    rows = values.rows
    uuids = rows.uuids
    observers = len(target.viewing_audience.observers)
    held = target.senses
    if fact.initial:
        if held is not None:
            raise ValueError("A seat's perception enters once")
        if fact.observer_position is None or fact.passive_perception is None or fact.visual_access is None:
            raise ValueError("An initial sensory fact carries the position and every capability after-value")
        held = SensesSnapshot(position=fact.observer_position, visible=EMPTY_CELLS, seen=EMPTY_CELLS, entities={},
            objects={}, effective_light_levels=EMPTY_VALUES, paths_dirty=False,
            passive_perception=fact.passive_perception, sense_modes_key=sense_modes_key(()), sense_modes=(),
            visual_access=fact.visual_access)
    elif held is None:
        raise ValueError("A sensory change requires the seat's entered perception")
    added = selected_mask(values.cells, fact.visible_cells_added)
    visible, light, hazard = update_cells(held.visible, held.effective_light_levels, held.hazardous_cells,
        selected_mask(values.cells, fact.visible_cells_removed), added,
        selected_values(values.light_levels, fact.effective_light_levels_changed),
        selected_values(values.hazards, fact.hazardous_cells_changed))

    entities, objects = dict(held.entities), dict(held.objects)
    for contacts, members, changed, gone in (
            (entities, target.entity_members, fact.entity_contacts_changed, fact.entity_contacts_removed),
            (objects, target.object_contact_members, fact.object_contacts_changed, fact.object_contacts_removed)):
        for identity in _unique(dict.fromkeys(uuids[index] for index in gone), gone):
            if identity not in contacts:
                raise ValueError("A removed contact is one the seat perceives")
            del contacts[identity]
            del members[identity]
        for index in changed:
            identity = uuids[rows.contact_uuid_index[index]]
            contacts[identity] = values.contacts[index]
            members[identity] = _row_members(rows.contact_members, index, observers)
        _unique(dict.fromkeys(uuids[rows.contact_uuid_index[index]] for index in changed), changed)

    target.spatial_content.update(fact.spatial_effect_content)
    effects = dict(held.spatial_effects)
    # Each effect whose visible part lost cells: its row as last perceived and those cells.
    left: dict[UUID, tuple[PerceivedSpatialEffect, set[tuple[int, int]]]] = {}
    for identity in _unique(dict.fromkeys(uuids[index] for index in fact.spatial_effects_removed),
                            fact.spatial_effects_removed):
        row = effects.pop(identity, None)
        if row is None:
            raise ValueError("A removed effect is one the seat perceives")
        del target.effect_members[identity]
        left[identity] = row, set(row.positions)
    for index in fact.spatial_effects_patched:
        identity = uuids[rows.patch_uuid_index[index]]
        before = effects.get(identity)
        if before is None:
            raise ValueError("A patched effect is one the seat perceives")
        patch = rows.sighting_patches[index]
        effects[identity] = after = _patched_effect(before, patch)
        if patch.members is not None:
            target.effect_members[identity] = patch.members
        left[identity] = after, set(mask_positions(patch.positions_removed))
    _unique(dict.fromkeys(uuids[rows.patch_uuid_index[index]] for index in fact.spatial_effects_patched),
            fact.spatial_effects_patched)
    for index in fact.spatial_effects_added:
        identity = uuids[rows.sighting_uuid_index[index]]
        if identity in effects:
            raise ValueError("An entering effect is one the seat does not perceive")
        content = target.spatial_content.get(identity)
        if content is None:
            raise ValueError("An entering effect's content was sent before or with it")
        effects[identity] = _sighted_effect(rows.sightings[index], content)
        target.effect_members[identity] = _row_members(rows.sighting_members, index, observers)
    retired = _unique({uuids[rows.retired_uuid_index[index]]: set(mask_positions(rows.retired_cells[index]))
                       for index in fact.spatial_effect_cells_retired}, fact.spatial_effect_cells_retired)
    _remember_effects(target.remembered_effects, effects, left, retired, visible)

    lights = target.light_sources
    for identity in _unique(dict.fromkeys(uuids[index] for index in fact.light_sources_removed),
                            fact.light_sources_removed):
        if lights.pop(identity, None) is None:
            raise ValueError("A removed light source is one the seat perceives")
    for index in fact.light_sources_patched:
        patch = rows.light_patches[index]
        before_light = lights.get(uuids[patch.source])
        if before_light is None:
            raise ValueError("A patched light source is one the seat perceives")
        lights[uuids[patch.source]] = _patched_light(before_light, patch, uuids)
    for index in fact.light_sources_added:
        source = rows.light_sources[index]
        if uuids[source.source] in lights:
            raise ValueError("An entering light source is one the seat does not perceive")
        lights[uuids[source.source]] = _light_source(source, uuids)

    modes = (tuple(mode.model_copy(deep=True) for mode in fact.sense_modes)
             if fact.sense_modes_changed and fact.sense_modes is not None else None)
    target.senses = replace(held, visible=visible, seen=mask_union(held.seen, added), entities=entities,
        objects=objects, effective_light_levels=light, hazardous_cells=hazard, spatial_effects=effects,
        position=fact.observer_position if fact.observer_position is not None else held.position,
        paths_dirty=held.paths_dirty or fact.paths_dirty,
        passive_perception=(fact.passive_perception if fact.passive_perception_changed
            and fact.passive_perception is not None else held.passive_perception),
        sense_modes=modes if modes is not None else held.sense_modes,
        sense_modes_key=sense_modes_key(modes) if modes is not None else held.sense_modes_key,
        visual_access=(fact.visual_access if fact.visual_access_changed
            and fact.visual_access is not None else held.visual_access))
    if fact.observer_position is not None and target.observer_uuid in target.actors:
        target.actors[target.observer_uuid] = replace(target.actors[target.observer_uuid],
            last_visual_position=fact.observer_position)
    for index in fact.entity_contacts_changed:
        identity, contact = uuids[rows.contact_uuid_index[index]], values.contacts[index]
        if contact.visual and identity in target.actors and target.actors[identity].present:
            target.actors[identity] = replace(target.actors[identity], last_visual_position=contact.position)


def _apply_audience(target: PlayerState, audience: PlayerAudience) -> None:
    """Advance membership and remap cached member bits once at its occurrence."""
    before = target.viewing_audience
    if audience.revision != before.revision + 1 or target.observer_uuid not in audience.observers:
        raise ValueError("Audience membership must advance one revision and retain the stream observer")
    if before.observers != audience.observers:
        positions = {identity: 1 << index for index, identity in enumerate(audience.observers)}
        remap = tuple((1 << index, positions.get(identity, 0)) for index, identity in enumerate(before.observers))
        for rows in (target.entity_members, target.object_contact_members, target.effect_members, target.object_members):
            for identity, bits in rows.items():
                rows[identity] = sum(new for old, new in remap if bits & old)
    for identity in before.controlled:
        if not audience.controls(identity) and (actor := target.actors.get(identity)) is not None:
            target.actors[identity] = replace(actor, controlled_items=None)
    if target.hud_snapshot is not None:
        target.hud_snapshot = replace(target.hud_snapshot,
            sheets=tuple(sheet for sheet in target.hud_snapshot.sheets if audience.controls(sheet.actor_uuid)))
    target.audience = audience


def apply_player_fact(target: PlayerState, fact: PlayerFact, values: ComposedValues) -> None:
    """Fold an already-disclosed committed fact of a group (`values`) into player memory: a sensory fact by the
    composed fold, a spatial or turn fact's senses and turn part, then any other fact's records part."""
    match fact:
        case AudienceFact():
            _apply_audience(target, fact.audience)
            if fact.sensory is not None:
                fold_composed_sensory(target, fact.sensory, values)
            clear_unseen_positions(target)
            return
        case SensoryFact():
            fold_composed_sensory(target, fact, values)
            clear_unseen_positions(target)
            return
        case SpatialFact():
            senses = target.senses
            if (fact.terminal_departure and fact.entity_uuid is not None and fact.entity_uuid in target.actors
                    and senses is not None):
                # A witnessed terminal departure ends the entity's contact for every member (`depart_contact`).
                target.senses = replace(senses, entities={identity: contact for identity, contact
                    in senses.entities.items() if identity != fact.entity_uuid})
                target.entity_members.pop(fact.entity_uuid, None)
            elif (target.viewing_audience.controls(fact.entity_uuid)
                    and fact.change_type is SpatialChangeType.ENTITY_ENTERED
                    and senses is not None and fact.entity_uuid == target.observer_uuid):
                # Own entry is an explicit permitted contact even when one
                # sensory batch folds an arrival and return to the same cell.
                target.senses = replace(senses, position=fact.position)
        case TurnFact():
            if fact.round_number is not None:
                target.round_number = fact.round_number
            if fact.event_type in (EventType.TURN_START, EventType.TURN_END, EventType.ENCOUNTER_END):
                target.current_actor_uuid = fact.entity_uuid if fact.event_type is EventType.TURN_START else None
    apply_record_fact(target, fact)


def apply_record_fact(target: PlayerState, fact: PlayerFact) -> None:
    """The records' part of a committed fact other than a sensory one (`fold_composed_sensory` folds both parts of
    that): it changes `target.actors` and `target.items` only."""
    match fact:
        case FactionFact():
            actor = target.actors.get(fact.entity_uuid)
            if actor is not None:
                target.actors[actor.uuid] = replace(actor, faction=fact.faction_after)
        case SpatialFact():
            if fact.terminal_departure and fact.entity_uuid is not None and fact.entity_uuid in target.actors:
                actor = target.actors[fact.entity_uuid]
                target.actors[actor.uuid] = replace(actor, present=False, last_visual_position=None, occupancy_layer=None)
                return
            actor = target.actors.get(fact.entity_uuid) if fact.entity_uuid is not None else None
            if actor is not None and fact.change_type is SpatialChangeType.ENTITY_ENTERED:
                actor = replace(actor, spatial_disposition=SpatialDisposition.PRESENT)
                target.actors[actor.uuid] = actor
            if actor is not None and fact.occupancy_layer is not None:
                target.actors[actor.uuid] = replace(actor, occupancy_layer=fact.occupancy_layer)
            if (actor is not None and target.viewing_audience.controls(fact.entity_uuid)
                    and fact.change_type is SpatialChangeType.ENTITY_ENTERED):
                target.actors[actor.uuid] = replace(target.actors[actor.uuid], last_visual_position=fact.position)
        case ItemChargeFact():
            actor = target.actors[fact.source_entity_uuid]
            if actor.controlled_items is None or not target.viewing_audience.controls(actor.uuid):
                raise ValueError("item charges require the controlled actor's inventory")
            if fact.item_destroyed:
                # The seat's item record stays (static records are never pruned).
                target.actors[actor.uuid] = replace(actor,
                    controlled_items=tuple(identity for identity in actor.controlled_items if identity != fact.item_uuid),
                    visual_loadout=replace(actor.visual_loadout, layers=tuple(layer for layer in actor.visual_loadout.layers
                        if layer.item_uuid != fact.item_uuid)))
            elif fact.item_uuid in actor.controlled_items:
                record = target.items[fact.item_uuid]
                if record.state is None:
                    raise ValueError("item charges require the controlled item's state")
                target.items[fact.item_uuid] = replace(record, state=replace(record.state,
                    charges=fact.charges_after, stack_count=fact.stack_count_after))
        case AttackFact():
            actor = target.actors.get(fact.source_entity_uuid)
            if actor is not None:
                stance = fact.weapon_set
                target.actors[actor.uuid] = replace(actor, visual_loadout=replace(actor.visual_loadout, active_weapon_set=stance))
        case DamageResultFact(stage="applied"):
            actor = target.actors[fact.target_entity_uuid]
            if fact.resulting_normal_hp is None or fact.resulting_temporary_hp is None:
                raise ValueError("applied damage requires exact committed HP")
            target.actors[actor.uuid] = replace(actor, normal_hp=fact.resulting_normal_hp, temporary_hp=fact.resulting_temporary_hp,
                temporary_hp_grant=actor.temporary_hp_grant if fact.resulting_temporary_hp > 0 else None)
        case HealFact(was_blocked=False):
            actor = target.actors[fact.target_entity_uuid]
            if fact.resulting_normal_hp is None or fact.resulting_temporary_hp is None:
                raise ValueError("healing requires exact committed HP")
            target.actors[actor.uuid] = replace(actor, normal_hp=fact.resulting_normal_hp, temporary_hp=fact.resulting_temporary_hp,
                temporary_hp_grant=actor.temporary_hp_grant if fact.resulting_temporary_hp > 0 else None)
        case TemporaryHitPointsFact():
            actor = target.actors[fact.entity_uuid]
            target.actors[actor.uuid] = replace(actor, temporary_hp=fact.resulting_temporary_hp, temporary_hp_grant=fact.grant)
        case LifeFact():
            actor = target.actors[fact.entity_uuid]
            target.actors[actor.uuid] = replace(actor, life_state=fact.new_state, normal_hp=fact.normal_hit_points,
                remains_disposition=fact.remains_disposition)
        case ActorChangeFact():
            apply_actor_change_fact(target, fact)


def apply_committed_player_fact(target: PlayerState, fact: PlayerFact, values: ComposedValues, *,
                               source_cursor: int, occurrences: Collection[int]) -> None:
    """Fold a committed fact without letting an outer move undo nested arrival."""
    if commit_current(target.spatial_commit_cursors, fact, source_cursor=source_cursor, occurrences=occurrences):
        apply_player_fact(target, fact, values)


def reduce_nodes(target: PlayerState, nodes: tuple[PlayerNode, ...], versions: VersionRows,
            bodies: tuple[BodyRecord, ...], updates: tuple[WorldUpdate, ...], rows: SensoryRows) -> PlayerState:
    """Fold received values in source order, including a timed partial group."""
    result = copy_target(target)
    _apply_nodes(result, nodes, versions, bodies, updates, rows)
    return result


def occurrence_order(nodes: tuple[PlayerNode, ...],
                     bodies: tuple[BodyRecord, ...]) -> Iterator[BodyRecord | PlayerNode]:
    """Bodies precede their node except at a membership transition: grant/revoke
    takes effect before any private body details at that same occurrence."""
    pending = iter(sorted(bodies, key=lambda row: row.occurrence))
    observation = next(pending, None)
    for node in nodes:
        while observation is not None and observation.occurrence < node.occurrence:
            yield observation
            observation = next(pending, None)
        membership = isinstance(node.fact, AudienceFact)
        if membership:
            yield node
        while observation is not None and observation.occurrence == node.occurrence:
            yield observation
            observation = next(pending, None)
        if not membership:
            yield node
    if observation is not None:
        yield observation
    yield from pending


def _apply_nodes(result: PlayerState, nodes: tuple[PlayerNode, ...], versions: VersionRows,
                 bodies: tuple[BodyRecord, ...], updates: tuple[WorldUpdate, ...], rows: SensoryRows) -> None:
    occurrences = set(versions.occurrences)
    world_updates = {row.occurrence: row for row in updates}
    values = composed_values(rows)
    for row in occurrence_order(nodes, bodies):
        match row:
            case BodyRecord():
                enter_body(result, row)
            case PlayerNode():
                membership = row.fact if not row.canceled and isinstance(row.fact, AudienceFact) else None
                if membership is not None:
                    _apply_audience(result, membership.audience)
                if row.occurrence in world_updates:
                    fold_world_update(result, world_updates[row.occurrence])
                if membership is not None:
                    if membership.sensory is not None:
                        fold_composed_sensory(result, membership.sensory, values)
                    clear_unseen_positions(result)
                elif not row.canceled and row.fact is not None:
                    apply_committed_player_fact(result, row.fact, values, source_cursor=row.occurrence,
                        occurrences=occurrences)


def node_lineages(nodes: Sequence[PlayerNode], versions: VersionRows) -> tuple[int, ...]:
    """Each received node's lineage: its version row's."""
    owner = dict(zip(versions.occurrences, versions.lineages))
    return tuple(owner[node.occurrence] for node in nodes)


def parent_lineages(nodes: Sequence[PlayerNode], versions: VersionRows) -> dict[int, int]:
    """Each lineage's parent in a received group: the lineage of the node listing it among its children, else
    the parent its own node names (one its group does not carry)."""
    lineages = node_lineages(nodes, versions)
    parents: dict[int, int] = {}
    for node, owner in zip(nodes, lineages):
        for child in node.children_lineages:
            parents.setdefault(child, owner)
    for node, owner in zip(nodes, lineages):
        if node.parent_lineage is not None:
            parents.setdefault(owner, node.parent_lineage)
    return parents


def check_spell_declarations(nodes: Sequence[PlayerNode], versions: VersionRows,
                             resolutions: Sequence[PlayerResolution]) -> None:
    """A target's spell application carries no declaration: its cast's does, on a node of the cast's lineage in
    the same group (plan §3.6). Raises ValueError when a group sends an application without its cast."""
    declared = {owner for node, owner in zip(nodes, node_lineages(nodes, versions))
                if isinstance(node.fact, SpellFact) and node.fact.source_entity_uuid is not None}
    for node in nodes:
        if (isinstance(node.fact, SpellFact) and node.fact.source_entity_uuid is None and node.resolution is not None
                and resolutions[node.resolution].application_id is not None
                and resolutions[node.resolution].lineage not in declared):
            raise ValueError("A spell application's group carries its cast's declaration")


def state_before_event(before: PlayerState, lineage: PlayerLineage, event: PlayerNode) -> PlayerState:
    """Retained subjective state just before a descendant's declaration."""
    versions = lineage.version_rows
    own = node_lineages((event,), versions)[0]
    first = min(occurrence for occurrence, owner in zip(versions.occurrences, versions.lineages) if owner == own)
    completed = {occurrence for occurrence in versions.occurrences if occurrence < first}
    events = tuple(row for row in lineage.events if row.occurrence in completed)
    if not events:
        return before
    result = copy_target(before)
    stage_static(result, lineage.world_updates)
    _apply_lineage(result, replace(lineage, events=events, end_cursor=first,
        bodies=tuple(row for row in lineage.bodies if row.occurrence in completed),
        world_updates=tuple(row for row in lineage.world_updates if row.occurrence in completed)))
    return result


def reduce_initialization(initialization: PlayerInitialization, *,
                          content_additions: tuple[ContentDescriptor, ...] = ()) -> PlayerState:
    target = PlayerState(generation=initialization.generation, observer_uuid=initialization.observer_uuid,
                         world=initialization.world,
                         audience=resolve_audience(initialization.observer_uuid, initialization.audience))
    check_spell_declarations(initialization.nodes, initialization.version_rows, initialization.resolutions)
    target = reduce_nodes(target, initialization.nodes, initialization.version_rows,
                     initialization.bodies, initialization.world_updates, initialization.sensory_rows)
    target.reducer_cursor = initialization.end_cursor
    if initialization.hud is not None:
        apply_hud(target, initialization.hud)
    target.content = tuple(sorted(content_additions, key=lambda row: row.ref.identity_key))
    return target


def changed_sheet(before: PlayerCharacterSheet, patch: SheetPatch) -> PlayerCharacterSheet:
    """A held sheet with a patch's fields; its resource values replace those of rows the sheet holds."""
    values = {row.key: row for row in patch.resource_values}
    sheet = replace(before, **patch.changes)
    if not values:
        return sheet
    if not values.keys() <= {row.key for row in sheet.resources}:
        raise ValueError("Resource values name a row the sheet does not hold")
    return replace(sheet, resources=tuple(replace(row, current=value.current, maximum=value.maximum)
        if (value := values.get(row.key)) is not None else row for row in sheet.resources))


def apply_hud(target: PlayerState, patch: PlayerHUDPatch) -> None:
    """Fold a HUD patch into the seat's display; a sheet it does not hold arrives whole and is appended."""
    previous = target.hud_snapshot
    sheets = {row.actor_uuid: row for row in previous.sheets} if previous is not None else {}
    for row in patch.sheets:
        before = sheets.get(row.actor_uuid)
        if before is None and (row.changes.keys() != SheetChanges.__optional_keys__ or row.resource_values):
            raise ValueError("A first sheet must carry every field")
        sheets[row.actor_uuid] = (PlayerCharacterSheet(actor_uuid=row.actor_uuid, **row.changes)
            if before is None else changed_sheet(before, row))
    initiative = patch.initiative if patch.initiative is not None else previous.initiative if previous is not None else None
    if initiative is None:
        raise ValueError("A first HUD requires its initiative")
    target.hud_snapshot = PlayerHUDSnapshot(initiative=initiative, sheets=tuple(sheets.values()))


def displayed_initiative(target: PlayerState) -> tuple[UUID, ...]:
    """The initiative the seat shows: the received order's part it perceives now."""
    if target.hud_snapshot is None:
        return ()
    perceived = perceived_entities(target.viewing_audience, target.senses)
    return tuple(identity for identity in target.hud_snapshot.initiative if identity in perceived)


def reduce_lineage(target: PlayerState, lineage: PlayerLineage) -> PlayerState:
    result = copy_target(target)
    _apply_lineage(result, lineage)
    return result


def _apply_lineage(target: PlayerState, lineage: PlayerLineage) -> None:
    if lineage.end_cursor <= target.reducer_cursor:
        raise ValueError("player lineage precedes this reduction position")
    result = target
    _apply_nodes(result, lineage.events, lineage.version_rows, lineage.bodies, lineage.world_updates,
        lineage.sensory_rows)
    result.reducer_cursor = lineage.end_cursor


def lineage_branch(lineage: PlayerLineage, root: PlayerNode) -> PlayerLineage:
    """A root's branch of a received group; its folds first stage the group's statics (`stage_static`)."""
    versions = lineage.version_rows
    owners = node_lineages(lineage.events, versions)
    parents = parent_lineages(lineage.events, versions)
    children: dict[int, list[int]] = {}
    for node, owner in zip(lineage.events, owners):
        children.setdefault(owner, []).extend(node.children_lineages)
    intervals: dict[int, tuple[int, int]] = {}
    for occurrence, owner in zip(versions.occurrences, versions.lineages):
        first, last = intervals.get(owner, (occurrence, occurrence))
        intervals[owner] = min(first, occurrence), max(last, occurrence)
    root_lineage = node_lineages((root,), versions)[0]
    first, last = intervals[root_lineage]
    selected: set[int] = set()
    # Privacy can remove an intermediate cause (for example a carried light's
    # update between a walking step and its sensory result). The received
    # occurrence interval still places that unparented result inside this step.
    # Keep its real wire ancestry absent; this is a chronological branch view.
    pending = [root_lineage, *(owner for owner in owners
        if owner not in parents and first <= intervals[owner][0] and intervals[owner][1] <= last)]
    while pending:
        identity = pending.pop()
        if identity in selected:
            continue
        selected.add(identity)
        pending.extend(children.get(identity, ()))
    nodes = tuple(node for node, owner in zip(lineage.events, owners) if owner in selected)
    kept = [(occurrence, owner) for occurrence, owner in zip(versions.occurrences, versions.lineages) if owner in selected]
    identities = {occurrence for occurrence, _ in kept}
    return replace(lineage, root=next(index for index, node in enumerate(nodes) if node.occurrence == root.occurrence),
        events=nodes, version_rows=VersionRows(occurrences=tuple(row[0] for row in kept),
            lineages=tuple(row[1] for row in kept)),
        start_cursor=kept[0][0], end_cursor=kept[-1][0] + 1,
        bodies=tuple(row for row in lineage.bodies if row.occurrence in identities),
        world_updates=tuple(row for row in lineage.world_updates if row.occurrence in identities))


def encode_player_sequence(sequence: PlayerSequence) -> bytes:
    return sequence.model_dump_json(warnings="error").encode("utf-8")


def decode_player_sequence(payload: bytes) -> tuple[PlayerState, tuple[PlayerLineage, ...]]:
    """Decode current public packets; older versions require native reprojection."""
    raw = json.loads(payload)
    if isinstance(raw, dict) and (type(raw.get("schema_version")) is not int
            or raw["schema_version"] != PlayerSequence.model_fields["schema_version"].default):
        raise ValueError("Unsupported player schema version; reproject the preserved native recording")
    sequence = PlayerSequence.model_validate_json(payload)
    return reduce_initialization(sequence.initialization), sequence.lineages


def reduce_operation(target: PlayerState, update: PlayerUpdate) -> PlayerState:
    """The client fold of one received operation (live clients, probes and saved replay)."""
    result = copy_target(target)
    if update.generation != target.generation or update.observer_uuid != target.observer_uuid:
        raise ValueError("An operation belongs to another observer or generation")
    if update.content_additions:
        content = {row.ref.identity_key: row for row in result.content}
        for descriptor in update.content_additions:
            old = content.get(descriptor.ref.identity_key)
            if old is not None and old != descriptor:
                raise ValueError("An admitted content identity changed its definition")
            content[descriptor.ref.identity_key] = descriptor
        result.content = tuple(content[key] for key in sorted(content))
    for lineage in update.lineages:
        if lineage.start_cursor != result.reducer_cursor:
            raise ValueError("Operation occurrence sequence has a gap")
        check_spell_declarations(lineage.events, lineage.version_rows, lineage.resolutions)
        _apply_lineage(result, lineage)
    if update.hud is not None:
        apply_hud(result, update.hud)
    for index, row in enumerate(update.combat_log_appends, len(result.combat_log_appends)):
        if (row.generation != result.generation or row.observer_uuid != result.observer_uuid
                or row.operation_end_cursor > result.reducer_cursor or row.encounter_log_index != index):
            raise ValueError("Standalone log append is out of order or belongs to another audience")
    result.combat_log_appends += update.combat_log_appends
    return result
