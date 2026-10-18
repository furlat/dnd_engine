"""Project private recorded facts into the public player packet.

Perception is already resolved by native events. This module selects existing
authority, remembers last-observed world values, and copies committed facts;
it never asks the live engine what an observer can see.
"""

from collections.abc import Callable, Collection, Iterable, Iterator, Mapping
from typing import TypeVar
from dataclasses import dataclass, field, replace
from math import floor
from uuid import UUID

from dnd.actions import AttackEvent, JumpEvent, MovementEvent, ShoveEvent, SpellEvent, TraverseConnectorEvent
from dnd.spells.abjuration import CounterspellReactionEvent
from dnd.blocks.base_item import ItemResourceChangeEvent, ItemHoldingsReleasedEvent, ItemLocationStateEvent
from dnd.blocks.equipment import EquipmentEvent
from dnd.core.cells import (flag_bits, mask_from_positions, mask_positions, mask_union, shared_cells, shared_values,
    values_from_items, zeros_left_out)
from dnd.types.cells import EMPTY_CELLS, CellMask, CellValues, cell_in, no_cells
from dnd.types.senses import SensesSnapshot, PerceivedContact, PerceivedLightSource, PerceivedSpatialEffect
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from dnd.types.spell_suppression import SpellSuppression
from dnd.core.base_actions import ActionEvent
from dnd.core.combat_log import CombatLogEntryType
from dnd.core.presentation_geometry import ConePresentationGeometry, LinePresentationGeometry, CubePresentationGeometry
from dnd.core.condition_types import ConditionCategory
from dnd.core.effect_types import ApplicationMembership, ResolutionRef
from dnd.core.content.runtime import HandlerDispatchOutcome
from dnd.core.events import (
    AreaReachEvent,
    DamageAppliedEvent, DeathEvent, DeathSaveEvent, EncounterEvent, EntityCreatedEvent, EntityFactionChangedEvent, ItemDestructionEvent,
    Event, EventPhase, EventType, ForcedMovementEvent, PortalTransferEvent, MechanismActivationEvent, HealEvent, LifeStateChangeEvent,
    RoundEvent, SensoryUpdateEvent, SpatialChangeEvent, SpatialChangeType, SpatialEffectChangeEvent, SpatialEffectInteractionEvent,
    MovementTrajectory, StepMovementEvent, TakeDamageEvent, TemporaryHitPointsChangedEvent, TurnEvent, WorldInitializedEvent, SavingThrowEvent,
    WorldObjectState,
)
from dnd.core.life_types import RemainsDisposition
from dnd.core.item_types import ItemConcentrationSlot, ItemEffectPresentationState, ItemIntegrity, ItemLocation, ItemPresentationState, ItemRemnantState
from dnd.types.world import CardinalDirection
from dnd.types.event_facts import WorldTileChanges, WorldTileState
from dnd.types.class_features import FontConversion
from dnd.types.residues import BodyReleaseRegion, BodyReleaseResult, ObjectResidueState
from dnd.types.summoning import SummonDepartureCause
from dnd.player.audience import AudienceComposition, PlayerAudience, depart_contact, resolve_audience

from dnd.player.actor_facts import ActorState, ConditionFact, PresentationTarget
from dnd.player.actor_projection import actor_fact_owner, actor_from_birth, apply_actor_fact
from dnd.actor_projection import remove_previous_item_holdings
from dnd.player.facts import (
    ActionCancellation, ActionFact, ActionReaction, ActorChanges, AreaReachFact, AttackFact, ConditionChangeFact, ItemEffectChangeFact, ContentAttribution, DamageRequestFact, DamageResultFact,
    DeathSaveFact, EquipmentFact, FloorItem, ForcedMovementFact, PortalTransferFact, MechanismActivationFact, HealFact, ItemChargeFact, LifeFact,
    MovementFact, ObjectDamageFact, ObjectDestroyedFact, PlayerActor, PlayerFact, PlayerInitialization, PlayerLineage,
    PlayerNode, PlayerObject, PlayerObservation, PlayerState, PlayerHUDPatch, CombatLogAppend,
    PlayerLogEntry, SheetChanges, SheetPatch, SpatialEffectContent, SpatialEffectSighting,
    PlayerWorld, PlayerResolution, LightRow, SensoryFact, SensoryRows, ShoveFact, SpellApplication, SpatialFact, SpatialEffectStateFact, SpellFact, StepFact, TurnFact,
    VersionRows, VisualItem, VisualLoadout, WorldUpdate, ItemLook, ItemPatch, ItemProfile, ItemState, PlayerItem, TileFieldUpdate, TemporaryHitPointsFact, SavingThrowFact, FactionFact, CreationWitness,
)
from dnd.player.capture import ActorAdmission, CompletedLineage, IntervalEnvelope, ObjectiveRow, apply_world_fact
from dnd.player.sheet_facts import sheet_fact
from dnd.types.actor_sheet import PlayerResourceValue
from dnd.player.event_record import upgrade_recorded_resolutions, upgrade_recorded_spatial_commits
from dnd.player.static_sent import StaticSent
from dnd.player.reduction import (apply_record_fact, apply_world_update, change_membership,
    commit_current, fold_senses, observe_body, observed_actor, occurrence_order)
from dnd.player.compatibility import legacy_damage_reference
from dnd.world_facts import world_event_objects, world_event_footprints, world_objects_at


def _identified(event: Event, identity: UUID | None, observer: PlayerAudience) -> bool:
    return identity is not None and (observer.controls(identity) or observer.granted(
        event.identified_entity_observer_uuids.get(str(identity), set())))


def _action_name(event: ActionEvent, observer: PlayerAudience) -> str | None:
    if event.font_conversion is None or observer.controls(event.source_entity_uuid):
        return event.name
    return ("Convert slot to sorcery points" if event.font_conversion.direction == "slot_to_points"
        else "Convert sorcery points to slot")


def _action_log(log: PlayerLogEntry | None, fact: PlayerFact | None,
                observer: PlayerAudience) -> PlayerLogEntry | None:
    """Keep a foreign conversion's resource amounts out of its public label too."""
    if (log is None or log.data.kind != "action" or not isinstance(fact, ActionFact) or fact.font_conversion is None
            or observer.controls(fact.source_entity_uuid)):
        return log
    description = log.data.effect_description if log.data.kind == "action" else ""
    compact = f"{{cyan:{log.source_name or 'Unknown'}}} uses {{bold:{fact.name}}}"
    verbose = compact + (f"\n  {description}" if description else "")
    return replace(log, compact=compact, verbose=verbose, detailed=verbose,
        data=log.data.model_copy(update={"action_name": fact.name}))


def _position_allowed(event: Event, position: tuple[int, int], observer: PlayerAudience) -> bool:
    return observer.granted(event.located_position_observer_uuids.get(
        f"{position[0]},{position[1]}", set()))


def _step_allowed(event: StepMovementEvent, observer: PlayerAudience) -> bool:
    return _identified(event, event.source_entity_uuid, observer) and (
        observer.controls(event.source_entity_uuid) or all(_position_allowed(event, position, observer)
            for position in (event.disclosed_path or (event.from_position, event.to_position))))


def _forced_allowed(event: ForcedMovementEvent, observer: PlayerAudience) -> bool:
    return _identified(event, event.target_entity_uuid, observer) and (
        any(observer.controls(identity) for identity in (event.source_entity_uuid, event.target_entity_uuid))
        or all(_position_allowed(event, point, observer)
               for point in (event.disclosed_path or (event.start_position, event.end_position))))


def _visual_loadout(actor: ActorState) -> VisualLoadout:
    items = {item.item_uuid: item for item in actor.items}
    return VisualLoadout(active_weapon_set=actor.active_weapon_set, layers=tuple(
        VisualItem(slot=slot, item_uuid=identity, item_id=items[identity].item_id, is_lit=items[identity].is_lit)
        for slot, identity in actor.equipment))


def _item_look(item: ItemPresentationState) -> ItemLook:
    return ItemLook(item_id=item.item_id, item_kind=item.item_kind, visual_item_name=item.visual_item_name,
        visual_variant_id=item.visual_variant_id, equipped_visual_policy=item.equipped_visual_policy,
        item_effects=item.item_effects, very_bright_radius_feet=item.very_bright_radius_feet,
        bright_radius_feet=item.bright_radius_feet, dim_radius_feet=item.dim_radius_feet)


def _item_profile(item: ItemPresentationState) -> ItemProfile:
    return ItemProfile(name=item.name, description=item.description, rarity=item.rarity, weight=item.weight,
        value=item.value, tags=item.tags, is_pickable=item.is_pickable, is_equippable=item.is_equippable,
        is_usable=item.is_usable, is_targetable=item.is_targetable, door_mechanism=item.door_mechanism,
        door_swing=item.door_swing, stack_id=item.stack_id, damage_dice=item.damage_dice,
        damage_type=item.damage_type, weapon_properties=item.weapon_properties, armor_type=item.armor_type,
        armor_ac=item.armor_ac, shield_ac_bonus=item.shield_ac_bonus, max_charges=item.max_charges,
        max_stack=item.max_stack, is_consumable=item.is_consumable, map_char=item.map_char,
        include_in_senses_objects=item.include_in_senses_objects,
        include_in_adjacent_senses_objects=item.include_in_adjacent_senses_objects,
        include_in_available_object_actions=item.include_in_available_object_actions,
        maximum_hit_points=item.maximum_hit_points, concentration_capacity=item.concentration_capacity,
        boundary_structure=item.boundary_structure)


def _item_state(item: ItemPresentationState) -> ItemState:
    return ItemState(stack_count=item.stack_count, charges=item.charges, integrity=item.integrity,
        destruction_outcome=item.destruction_outcome, remnant_state=item.remnant_state,
        current_hit_points=item.current_hit_points, concentration_slots=item.concentration_slots,
        construction_owner_uuid=item.construction_owner_uuid, construction_geometry=item.construction_geometry,
        construction_suppressions=item.construction_suppressions, known_to_creator=item.known_to_creator,
        supported_by_uuid=item.supported_by_uuid, contact_passage=item.contact_passage,
        surface_residues=item.surface_residues, linked_spatial_condition_uuid=item.linked_spatial_condition_uuid,
        is_open=item.is_open, is_engaged=item.is_engaged, blocks_movement=item.blocks_movement,
        blocks_optics=item.blocks_optics, blocks_propagation=item.blocks_propagation, is_lit=item.is_lit)


# One walk's item records: by (item, whether its controller's), the recorded value and the record built from it.
ItemRecords = dict[tuple[UUID, bool], tuple[ItemPresentationState, ItemPatch]]


def _item_record(item: ItemPresentationState, controlled: bool, records: ItemRecords) -> ItemPatch:
    """An item's record: look, profile and state for its controller, the look for anyone else.

    A walk builds it once per recorded value: bodies observed again in the
    walk hold the same frozen item values, which map to the same record.
    """
    key = item.item_uuid, controlled
    held = records.get(key)
    if held is not None and held[0] is item:
        return held[1]
    record = (ItemPatch(item_uuid=item.item_uuid, look=_item_look(item), profile=_item_profile(item),
        state=_item_state(item)) if controlled else ItemPatch(item_uuid=item.item_uuid, look=_item_look(item)))
    records[key] = item, record
    return record


def _item_records(actor: ActorState, observer: PlayerAudience, records: ItemRecords) -> tuple[ItemPatch, ...]:
    """Each item a body shows, with every component the seat may know: look, profile and state of
    its controller's inventory, the look of an equipped item to anyone else."""
    if observer.controls(actor.uuid):
        return tuple(_item_record(item, True, records) for item in actor.items)
    items = {item.item_uuid: item for item in actor.items}
    return tuple(_item_record(items[identity], False, records)
        for identity in dict.fromkeys(identity for _, identity in actor.equipment))


def item_patch(before: PlayerItem | None, after: ItemPatch) -> ItemPatch:
    """The components of a disclosed record `after` that the seat's record `before` lacks or holds otherwise."""
    return ItemPatch(item_uuid=after.item_uuid,
        look=after.look if before is None or before.look != after.look else None,
        profile=after.profile if before is None or before.profile != after.profile else None,
        state=after.state if before is None or before.state != after.state else None)


def _public_actor(actor: ActorState, observer: PlayerAudience) -> PlayerActor:
    return PlayerActor(uuid=actor.uuid, name=actor.name,
        character_body_id=actor.character_body_id, creature_content_ref=actor.creature_content_ref,
        appearance=actor.appearance, visual_loadout=_visual_loadout(actor),
        normal_hp=actor.normal_hp, maximum_hp=actor.maximum_hp,
        temporary_hp=actor.temporary_hp, life_state=actor.life_state,
        remains_disposition=actor.remains_disposition,
        spatial_disposition=actor.spatial_disposition,
        temporary_hp_grant=actor.temporary_hp_grant,
        armor_class=actor.armor_class, conditions=actor.conditions,
        resolved_size=actor.resolved_size, structural_base_size=actor.structural_base_size,
        last_visual_position=actor.last_visual_position, faction=actor.faction,
        manifestation=actor.summon_origin.manifestation if actor.summon_origin is not None else None,
        occupancy_layer=(actor.occupancy_layer
                         if observer.controls(actor.uuid) or actor.last_visual_position is not None else None),
        controlled_items=tuple(item.item_uuid for item in actor.items) if observer.controls(actor.uuid) else None)


def actor_changes(before: PlayerActor | None, after: PlayerActor) -> ActorChanges:
    """The patch that turns the seat's body `before` (absent: every field) into `after`."""
    changes: ActorChanges = {}
    if before is None or before.name != after.name:
        changes["name"] = after.name
    if before is None or before.character_body_id != after.character_body_id:
        changes["character_body_id"] = after.character_body_id
    if before is None or before.creature_content_ref != after.creature_content_ref:
        changes["creature_content_ref"] = after.creature_content_ref
    if before is None or before.appearance != after.appearance:
        changes["appearance"] = after.appearance
    if before is None or before.visual_loadout != after.visual_loadout:
        changes["visual_loadout"] = after.visual_loadout
    if before is None or before.normal_hp != after.normal_hp:
        changes["normal_hp"] = after.normal_hp
    if before is None or before.maximum_hp != after.maximum_hp:
        changes["maximum_hp"] = after.maximum_hp
    if before is None or before.temporary_hp != after.temporary_hp:
        changes["temporary_hp"] = after.temporary_hp
    if before is None or before.life_state != after.life_state:
        changes["life_state"] = after.life_state
    if before is None or before.armor_class != after.armor_class:
        changes["armor_class"] = after.armor_class
    if before is None or before.conditions != after.conditions:
        changes["conditions"] = after.conditions
    if before is None or before.last_visual_position != after.last_visual_position:
        changes["last_visual_position"] = after.last_visual_position
    if before is None or before.controlled_items != after.controlled_items:
        changes["controlled_items"] = after.controlled_items
    if before is None or before.occupancy_layer != after.occupancy_layer:
        changes["occupancy_layer"] = after.occupancy_layer
    if before is None or before.temporary_hp_grant != after.temporary_hp_grant:
        changes["temporary_hp_grant"] = after.temporary_hp_grant
    if before is None or before.resolved_size != after.resolved_size:
        changes["resolved_size"] = after.resolved_size
    if before is None or before.structural_base_size != after.structural_base_size:
        changes["structural_base_size"] = after.structural_base_size
    if before is None or before.manifestation != after.manifestation:
        changes["manifestation"] = after.manifestation
    if before is None or before.faction != after.faction:
        changes["faction"] = after.faction
    if before is None or before.present != after.present:
        changes["present"] = after.present
    if before is None or before.remains_disposition != after.remains_disposition:
        changes["remains_disposition"] = after.remains_disposition
    if before is None or before.spatial_disposition != after.spatial_disposition:
        changes["spatial_disposition"] = after.spatial_disposition
    return changes


def _holdings(actor: ActorState, observer: PlayerAudience) -> ActorChanges:
    """A body's loadout and, for its controller, its inventory."""
    return {"visual_loadout": _visual_loadout(actor), "controlled_items": tuple(item.item_uuid for item in actor.items)
        if observer.controls(actor.uuid) else None}


def _gear_observation(occurrence: int, actor: ActorState, observer: PlayerAudience,
                      records: ItemRecords) -> PlayerObservation:
    """A holdings change seen on a known body."""
    return PlayerObservation(occurrence=occurrence, actor_uuid=actor.uuid, changes=_holdings(actor, observer),
        contact=None, items=_item_records(actor, observer, records))


def _sighting(effect: PerceivedSpatialEffect) -> SpatialEffectSighting:
    """A perceived effect without its static content; its sorted cell lists are sent as sets."""
    return SpatialEffectSighting.model_construct(duration=effect.duration, positions=mask_from_positions(effect.positions),
        owner_revision=effect.owner_revision, apparent_presence=effect.apparent_presence,
        trap_state=effect.trap_state, pressed=effect.pressed, direction=effect.direction,
        anchor_item_uuid=effect.anchor_item_uuid, anchor_entity_uuid=effect.anchor_entity_uuid,
        energy_type=effect.energy_type, presence_mode=effect.presence_mode,
        sustainer_item_uuid=effect.sustainer_item_uuid, concentration_slot_uuid=effect.concentration_slot_uuid,
        anchor_position=effect.anchor_position, anchor_elevation_steps=effect.anchor_elevation_steps,
        area_geometry=effect.area_geometry, construction_sections=effect.construction_sections,
        area_propagation=effect.area_propagation, deposit_source=effect.deposit_source,
        visible_volume_positions=mask_from_positions(effect.visible_volume_positions),
        upper_volume_surfaces=effect.upper_volume_surfaces, suppressions=effect.suppressions)


@dataclass(frozen=True, slots=True)
class FactRow:
    """A sensory fact's observer and native cell lists, kept by its group's table until the group's rows are built."""

    observer_uuid: UUID
    visible_cells_added: CellMask
    visible_cells_removed: CellMask
    seen_cells_added: CellMask
    effective_light_levels_changed: CellValues
    hazardous_cells_changed: CellValues


@dataclass(slots=True)
class SensoryTable:
    """One group's sensory values as its projection walks them: one row per fact entry, in walk order.

    A local of one group's projection (`_project_nodes` through `_shared_rows`).
    Until `_shared_rows`, a sensory fact's indices name these rows (its removed
    contacts and effects `removed_uuids`); each row is named by the one fact
    that appended it. A fact's `observer` names its own row of `facts` (its
    observer and native cell lists). `_shared_rows` keeps the
    named rows, each distinct value once, builds the group's cell row tables
    and renumbers the facts to the group's `SensoryRows`.
    """

    contact_uuids: list[UUID] = field(default_factory=list)
    contacts: list[PerceivedContact] = field(default_factory=list)
    sighting_uuids: list[UUID] = field(default_factory=list)
    sightings: list[SpatialEffectSighting] = field(default_factory=list)
    light_sources: list[PerceivedLightSource] = field(default_factory=list)
    light_removal_uuids: list[UUID] = field(default_factory=list)
    light_removal_revisions: list[int] = field(default_factory=list)
    removed_uuids: list[UUID] = field(default_factory=list)
    facts: list[FactRow] = field(default_factory=list)
    # Each effect's sightings built so far in the group, with the perceived value each was built from.
    built_sightings: dict[UUID, list[tuple[PerceivedSpatialEffect, SpatialEffectSighting]]] = field(default_factory=dict)


Row = TypeVar("Row")


def _appended(column: list[Row], values: Iterable[Row]) -> tuple[int, ...]:
    """Append values as rows of a column; their indices."""
    start = len(column)
    column.extend(values)
    return tuple(range(start, len(column)))


def _keyed(keys: list[UUID], column: list[Row], values: Mapping[UUID, Row]) -> tuple[int, ...]:
    """Append a map's entries as rows of a keyed column pair; their indices."""
    keys.extend(values)
    return _appended(column, values.values())


def _effect_content(effect: PerceivedSpatialEffect) -> SpatialEffectContent:
    return SpatialEffectContent(content_ref=effect.content_ref, name=effect.name, description=effect.description)


def _group_sighting(table: SensoryTable, identity: UUID, effect: PerceivedSpatialEffect) -> SpatialEffectSighting:
    """An effect's sighting, built once per equal perceived value in the group (observers often see the same)."""
    built = table.built_sightings.setdefault(identity, [])
    for perceived, sighting in built:
        if perceived is effect or perceived == effect:
            return sighting
    sighting = _sighting(effect)
    built.append((effect, sighting))
    return sighting


def _sensory_fact(event: SensoryUpdateEvent, keys: "NativeKeys", table: SensoryTable) -> SensoryFact:
    """The public fact of an observed sensory event; its observer, cells, changed and removed values are rows appended to `table`."""
    observer = _appended(table.facts, (FactRow(observer_uuid=event.observer_uuid,
        visible_cells_added=event.visible_cells_added, visible_cells_removed=event.visible_cells_removed,
        seen_cells_added=event.seen_cells_added, effective_light_levels_changed=event.effective_light_levels_changed,
        hazardous_cells_changed=event.hazardous_cells_changed),))[0]
    return SensoryFact(observer=observer, initial=event.initial,
        observer_position=event.observer_position, observer_position_changed=event.observer_position_changed,
        light_sources_changed=_appended(table.light_sources, event.light_sources_changed.values()),
        light_sources_removed=_keyed(table.light_removal_uuids, table.light_removal_revisions, event.light_sources_removed),
        spatial_effect_sightings=_keyed(table.sighting_uuids, table.sightings,
            {identity: _group_sighting(table, identity, effect) for identity, effect in event.spatial_effects_changed.items()}),
        spatial_effect_content={identity: _effect_content(effect) for identity, effect in event.spatial_effects_changed.items()},
        spatial_effects_removed=_appended(table.removed_uuids, event.spatial_effects_removed),
        cause_occurrence=_version_key(keys, event.cause_event_uuid),
        entity_contacts_changed=_keyed(table.contact_uuids, table.contacts, event.entity_contacts_changed),
        entity_contacts_removed=_appended(table.removed_uuids, event.entity_contacts_removed),
        object_contacts_changed=_keyed(table.contact_uuids, table.contacts, event.object_contacts_changed),
        object_contacts_removed=_appended(table.removed_uuids, event.object_contacts_removed),
        sense_modes_changed=event.sense_modes_changed,
        sense_modes=tuple(event.sense_modes) if event.sense_modes is not None else None,
        passive_perception_changed=event.passive_perception_changed,
        passive_perception=event.passive_perception, visual_access_changed=event.visual_access_changed,
        visual_access=event.visual_access, paths_dirty=event.paths_dirty)


def _held_item_disclosed(item_uuid: UUID | None, event: Event, observer: PlayerAudience,
                         actors: dict[UUID, ActorState], known: Collection[UUID],
                         senses: SensesSnapshot | None) -> bool:
    if any(identity in actors and any(item.item_uuid == item_uuid for item in actors[identity].items)
           for identity in observer.controlled):
        return True
    return senses is not None and any(identity in known and identity in actors
        and contact.visual and _identified(event, identity, observer)
        and any(equipped == item_uuid for _, equipped in actors[identity].equipment)
        for identity, contact in senses.entities.items())


def _held_content_at_event(event: Event, observer: PlayerAudience, actors: dict[UUID, ActorState],
                           known: Collection[UUID], senses: SensesSnapshot | None) -> frozenset[str]:
    holders = set(observer.controlled)
    if senses is not None:
        holders.update(identity for identity, contact in senses.entities.items()
            if contact.visual and identity in known and _identified(event, identity, observer))
    result = set()
    for identity in holders:
        actor = actors.get(identity)
        if actor is None:
            continue
        equipped = {item for _, item in actor.equipment}
        result.update(item.item_id for item in actor.items
            if observer.controls(identity) or item.item_uuid in equipped)
    return frozenset(result)


@dataclass(frozen=True, slots=True)
class DeclarationSenses:
    """Detached event-entry grants; explored history is not a delivery grant."""

    visible: CellMask
    entities: dict[UUID, PerceivedContact]
    objects: dict[UUID, PerceivedContact]
    spatial_effects: dict[UUID, PerceivedSpatialEffect]


def _project_fact(event: Event, observer: PlayerAudience, actors: dict[UUID, ActorState],
                  condition: ConditionFact | None, events: tuple[Event, ...],
                  admissions: tuple[ActorAdmission, ...], known: Collection[UUID],
                  observed_objects: set[UUID], senses: SensesSnapshot | None, keys: "NativeKeys",
                  records: ItemRecords, declaration_senses: DeclarationSenses | None = None) -> PlayerFact | None:
    source = event.source_entity_uuid if event.source_entity_uuid in known and _identified(event, event.source_entity_uuid, observer) else None
    target = event.target_entity_uuid if event.target_entity_uuid in known and _identified(event, event.target_entity_uuid, observer) else None
    match event:
        case AreaReachEvent():
            positions = tuple(position for position in event.newly_reached_positions
                if _position_allowed(event, position, observer)
                or senses is not None and cell_in(senses.visible, position))
            if not positions:
                return None
            return AreaReachFact(stage_index=event.stage_index, newly_reached_positions=positions,
                previous_reach_lineage=_lineage_key(keys, event.previous_reach_lineage_uuid),
                prerequisite_destruction_lineages=tuple(key for identity in event.prerequisite_destruction_lineages
                    if (key := _lineage_key(keys, identity)) is not None))
        case SpatialEffectChangeEvent():
            interaction_operation = None
            by_lineage = {row.lineage_uuid: row for row in events}
            parent = by_lineage.get(event.parent_lineage) if event.parent_lineage is not None else None
            while parent is not None:
                if isinstance(parent, SpatialEffectInteractionEvent) and not parent.canceled:
                    interaction_operation = parent.operation
                    break
                parent = by_lineage.get(parent.parent_lineage) if parent.parent_lineage is not None else None
            if event.operation is SpatialEffectChangeOperation.REMOVED:
                # Removal's sensory child has already dropped the field. Only
                # its own entry contact can witness this mechanical removal;
                # a remembered field or ordinary sight loss grants nothing.
                if declaration_senses is None or senses is None:
                    return None
                observed = declaration_senses.spatial_effects.get(event.spatial_effect_uuid)
                if observed is None:
                    return None
                positions = tuple(position for position in event.previous_positions
                    if position in observed.positions
                    and (cell_in(declaration_senses.visible, position) or position in observed.visible_volume_positions)
                    and cell_in(senses.visible, position))
                return SpatialEffectStateFact(spatial_effect_uuid=event.spatial_effect_uuid,
                    positions=positions, previous_state=None, state=None,
                    operation=event.operation, interaction_operation=interaction_operation,
                    removed_positions=positions) if positions else None
            observed = senses.spatial_effects.get(event.spatial_effect_uuid) if senses is not None else None
            if event.operation is SpatialEffectChangeOperation.FOOTPRINT_CHANGED:
                prior = declaration_senses.spatial_effects.get(event.spatial_effect_uuid) if declaration_senses is not None else None
                removed_positions = tuple(position for position in event.previous_positions
                    if position not in event.affected_positions and prior is not None and position in prior.positions
                    and declaration_senses is not None and cell_in(declaration_senses.visible, position)
                    and senses is not None and cell_in(senses.visible, position))
                positions = tuple(position for position in event.affected_positions
                    if observed is not None and position in observed.positions
                    and senses is not None and (cell_in(senses.visible, position) or position in observed.visible_volume_positions))
                return SpatialEffectStateFact(spatial_effect_uuid=event.spatial_effect_uuid,
                    positions=positions, previous_state=None, state=None, operation=event.operation,
                    interaction_operation=interaction_operation, removed_positions=removed_positions
                    ) if positions or removed_positions else None
            if observed is None or (event.operation is not SpatialEffectChangeOperation.CREATED
                    and (event.previous_trap_state is None or event.trap_state is None)
                    and (event.previous_pressed is None or event.pressed is None)):
                return None
            # Fixture identity and cells are granted by this observer's recorded
            # sensory after-values. Unlike movement, native spatial-condition
            # events do not carry separate coordinate-grant metadata.
            positions = tuple(position for position in event.affected_positions
                if position in observed.positions and senses is not None
                and (cell_in(senses.visible, position) or position in observed.visible_volume_positions))
            return SpatialEffectStateFact(spatial_effect_uuid=event.spatial_effect_uuid,
                positions=positions, previous_state=event.previous_trap_state, state=event.trap_state,
                operation=event.operation, previous_pressed=event.previous_pressed,
                pressed=event.pressed, interaction_operation=interaction_operation) if positions else None
        case SensoryUpdateEvent():
            raise ValueError("A sensory event is projected by the walk (_sensory_fact)")
        case StepMovementEvent():
            if not _step_allowed(event, observer):
                return None
            return StepFact(source_entity_uuid=event.source_entity_uuid,
                from_position=event.from_position, to_position=event.to_position,
                from_elevation_feet=event.from_elevation_feet, to_elevation_feet=event.to_elevation_feet,
                disclosed_path=event.disclosed_path, trajectory=event.trajectory,
                provocation_policy=event.provocation_policy, committed=event.committed,
                resolved_speed_feet=event.resolved_speed_feet,
                movement_mode=event.movement_mode, from_layer=event.from_layer, to_layer=event.to_layer)
        case MovementEvent() | JumpEvent():
            steps = tuple(row for row in events if isinstance(row, StepMovementEvent)
                          and row.parent_lineage == event.lineage_uuid)
            observed = (source is not None or any(_identified(row, event.source_entity_uuid, observer) for row in steps)
                        or any(row.actor.uuid == event.source_entity_uuid for row in admissions))
            if not observed:
                return None
            atomic = isinstance(event, JumpEvent) and (
                observer.controls(event.source_entity_uuid) or bool(steps) and all(_step_allowed(row, observer) for row in steps)
                and set(event.path or ()).issubset({position for row in steps
                    for position in (row.disclosed_path or (row.from_position, row.to_position))}))
            # The trajectory ends at its last committed step. A portal or paid
            # retreat can change the native action's final position afterward.
            landing = max((row for row in steps if row.committed), key=lambda row: row.path_index, default=None)
            return MovementFact(source_entity_uuid=event.source_entity_uuid, trajectory=event.trajectory,
                start_position=event.start_position if atomic else None,
                end_position=(landing.to_position if landing is not None else event.start_position) if atomic else None,
                requested_end_position=event.requested_end_position if atomic and (
                    observer.controls(source) or event.requested_end_position in (event.path or ())) else None,
                path=tuple(event.path or ()) if atomic else (),
                start_elevation_feet=event.start_elevation_feet if atomic and isinstance(event, JumpEvent) else None,
                end_elevation_feet=(landing.to_elevation_feet if landing is not None else event.start_elevation_feet)
                    if atomic and isinstance(event, JumpEvent) else None,
                movement_mode=(event.movement_mode if observer.controls(event.source_entity_uuid)
                               or any(_step_allowed(row, observer) for row in steps) else None),
                start_layer=event.start_layer if atomic or observer.controls(event.source_entity_uuid) else None,
                end_layer=event.end_layer if atomic or observer.controls(event.source_entity_uuid) else None)
        case TraverseConnectorEvent():
            steps = tuple(row for row in events if isinstance(row, StepMovementEvent)
                          and row.parent_lineage == event.lineage_uuid)
            if source is None and not any(_step_allowed(row, observer) for row in steps):
                return None
            return MovementFact(source_entity_uuid=event.source_entity_uuid,
                trajectory=MovementTrajectory.CONNECTOR_TRANSFER,
                connector_presentation_key=event.connector_presentation_key)
        case AttackEvent():
            if event.target_kind == "object":
                target = event.target_entity_uuid if event.target_entity_uuid in observed_objects else None
            if source is None or target is None:
                return None
            deflection_visible = (event.projectile_deflection_position is not None
                and event.intercepted_by_condition_uuid is not None
                and any(snapshot is not None
                    and (owner := snapshot.spatial_effects.get(event.intercepted_by_condition_uuid)) is not None
                    and tuple(floor(value+.5) for value in event.projectile_deflection_position) in owner.positions
                    and cell_in(snapshot.visible, tuple(floor(value+.5) for value in event.projectile_deflection_position))
                    for snapshot in (senses, declaration_senses)))
            return AttackFact(source_entity_uuid=source, target_entity_uuid=target,
                behavior_id=event.behavior_id, name=event.name, weapon_slot=event.weapon_slot,
                attack_outcome=event.attack_outcome, damage_types=tuple(event.damage_types),
                intercepted_by_condition_uuid=event.intercepted_by_condition_uuid,
                projectile_deflection_position=event.projectile_deflection_position if deflection_visible else None,
                source_item_id=event.source_item_presentation.item_id if event.source_item_presentation is not None else None,
                source_item_uuid=event.source_item_uuid,
                item_effects=event.source_item_presentation.item_effects if event.source_item_presentation is not None else (),
                target_kind=event.target_kind,
                target_position=event.target_position if event.target_kind == "object" and (
                    observer.controls(source) or event.target_position is not None and (
                        _position_allowed(event, event.target_position, observer)
                        or declaration_senses is not None and cell_in(declaration_senses.visible, event.target_position))) else None,
                target_base_height_steps=event.target_base_height_steps if event.target_kind == "object" else None,
                attack_source_kind=event.attack_source_kind)
        case SpellEvent():
            if event.target_kind == "object":
                target = event.target_entity_uuid if event.target_entity_uuid in observed_objects or (
                    _held_item_disclosed(event.target_entity_uuid, event, observer, actors, known, senses)) else None
            if source is None or (event.target_entity_uuid is not None and target is None):
                return None
            area = event.area_geometry is not None
            propagated = event.propagation is not None or any(
                isinstance(child, SpellEvent) and child.parent_lineage == event.lineage_uuid
                and child.propagation is not None for child in events)
            if not area and not propagated and event.target_kind == "creature" and any(
                    not _identified(event, identity, observer) and identity not in observed_objects
                    for identity in event.declared_target_entity_uuids):
                return None
            if event.propagation is not None and not observer.controls(source) and any(
                    (endpoint.kind == "creature" and not _identified(event, endpoint.uuid, observer)
                     or endpoint.kind == "object" and endpoint.uuid not in observed_objects)
                    or not (_position_allowed(event, endpoint.position, observer)
                        or senses is not None and cell_in(senses.visible, endpoint.position)
                        or declaration_senses is not None and cell_in(declaration_senses.visible, endpoint.position))
                    for endpoint in (event.propagation.source, event.propagation.target)):
                return None
            source_position = event.source_position
            if source_position is not None and not observer.controls(event.source_entity_uuid) and not _position_allowed(event, source_position, observer):
                # Locating an actor at completion grants its received contact,
                # not an earlier declaration coordinate (e.g. teleport origin).
                contact = senses.entities.get(source) if senses is not None else None
                declared_contact = declaration_senses.entities.get(source) if declaration_senses is not None else None
                observed_declaration = (declared_contact is not None and declared_contact.visual
                    and declared_contact.position == source_position)
                if not observed_declaration and (
                        not observer.granted(event.located_entity_observer_uuids.get(str(source), set()))
                        or contact is None or contact.position != source_position):
                    source_position = None
            # A direction pick may lie beyond the visible map; it is not the
            # line/cone's world anchor. Disclose only its observed native origin.
            area_position = (event.area_geometry.origin
                if isinstance(event.area_geometry, (ConePresentationGeometry, LinePresentationGeometry, CubePresentationGeometry))
                else event.aoe_position)
            if area_position is not None and not (_position_allowed(event, area_position, observer)
                    or senses is not None and cell_in(senses.visible, area_position)
                    or declaration_senses is not None and cell_in(declaration_senses.visible, area_position)):
                area_position = None
            resolved_positions = event.resolved_area_positions
            if resolved_positions is not None:
                resolved_positions = tuple(position for position in resolved_positions
                    if _position_allowed(event, position, observer)
                    or senses is not None and cell_in(senses.visible, position)
                    or declaration_senses is not None and cell_in(declaration_senses.visible, position))
            return SpellFact(source_entity_uuid=source, target_entity_uuid=target,
                target_kind=event.target_kind,
                target_position=event.target_position if event.target_kind == "object" and (
                    observer.controls(source) or event.target_position is not None and (
                        _position_allowed(event, event.target_position, observer)
                        or declaration_senses is not None and cell_in(declaration_senses.visible, event.target_position))) else None,
                target_base_height_steps=event.target_base_height_steps if event.target_kind == "object" else None,
                behavior_id=event.behavior_id, name=event.name, source_position=source_position,
                cast_origin=event.cast_origin,
                source_item_uuid=event.source_item_uuid if event.source_item_uuid in observed_objects else None,
                declared_target_entity_uuids=tuple(identity for identity in event.declared_target_entity_uuids
                    if (not area and not propagated) or identity in observed_objects
                    or identity in known and _identified(event, identity, observer)),
                application=_application(keys, event.application),
                propagation=event.propagation,
                attack_outcome=event.attack_outcome,
                effect_id=event.effect_id,
                aoe_position=area_position,
                area_geometry=event.area_geometry if area_position is not None else None,
                area_propagation=event.area_propagation,
                resolved_area_positions=resolved_positions,
                suppressions=tuple(SpellSuppression(provider_uuid=suppression.provider_uuid,
                    positions=tuple(position for position in suppression.positions
                        if _position_allowed(event, position, observer)
                        or senses is not None and cell_in(senses.visible, position)))
                    for suppression in event.suppressions
                    if (senses is not None and suppression.provider_uuid in senses.spatial_effects)
                    or (declaration_senses is not None and suppression.provider_uuid in declaration_senses.spatial_effects)))
        case ShoveEvent():
            return (None if source is None or target is None else ShoveFact(
                source_entity_uuid=source, target_entity_uuid=target, behavior_id=event.behavior_id,
                contest_success=event.contest_success, push_distance=event.push_distance,
                knocked_prone=event.knocked_prone))
        case MechanismActivationEvent():
            observed = senses.spatial_effects.get(event.mechanism_uuid) if senses is not None else None
            if observed is None and declaration_senses is not None:
                observed = declaration_senses.spatial_effects.get(event.mechanism_uuid)
            # Environmental discharges have no moving actor from which to infer
            # coordinate grants. Preserve this release's already witnessed cells
            # when its own cloud obscures them before completion.
            visible = mask_union(senses.visible if senses is not None else EMPTY_CELLS,
                declaration_senses.visible if declaration_senses is not None else EMPTY_CELLS)
            positions = tuple(position for position in event.affected_positions if cell_in(visible, position))
            origin = event.origin_position if event.origin_position is not None and cell_in(visible, event.origin_position) else None
            if origin is None and not positions:
                return None
            return MechanismActivationFact(mechanism_uuid=event.mechanism_uuid if observed is not None else None,
                mechanism_content_id=event.mechanism_content_ref.content_id, target_entity_uuid=target,
                origin_position=origin, direction=event.direction, affected_positions=positions,
                end_position=event.end_position if event.end_position is not None and cell_in(visible, event.end_position) else None,
                committed=event.committed)
        case PortalTransferEvent():
            if target is None:
                return None
            departure = event.start_position if (observer.controls(target)
                or _position_allowed(event, event.start_position, observer)) else None
            arrival = event.end_position if event.committed and (observer.controls(target)
                or _position_allowed(event, event.end_position, observer)) else None
            if departure is None and arrival is None:
                return None
            owner = next((row for row in events if row.lineage_uuid == event.parent_lineage), None)
            return PortalTransferFact(target_entity_uuid=target,
                # A revealed hatch observation may complete after its nested
                # transfer. Join only this observer's actual retained evidence.
                portal_uuid=event.portal_uuid if departure is not None and (
                    senses is not None and event.portal_uuid in senses.spatial_effects
                    or declaration_senses is not None and event.portal_uuid in declaration_senses.spatial_effects
                    or any(isinstance(row, SensoryUpdateEvent) and observer.observes(row.observer_uuid)
                        and event.portal_uuid in row.spatial_effects_changed for row in events)) else None,
                start_position=departure, end_position=arrival, committed=event.committed,
                portal_content_id=(event.portal_content_ref.content_id if event.portal_content_ref is not None
                    else owner.behavior_id if isinstance(owner, SpellEvent) else None))
        case ForcedMovementEvent():
            if target is None or not _forced_allowed(event, observer):
                return None
            return ForcedMovementFact(source_entity_uuid=source, target_entity_uuid=target,
                start_position=event.start_position, end_position=event.end_position, actual_distance=event.actual_distance,
                disclosed_path=event.disclosed_path, start_elevation_feet=event.start_elevation_feet,
                end_elevation_feet=event.end_elevation_feet, drop_feet=event.drop_feet,
                landing_kind=event.landing_kind)
        case TakeDamageEvent():
            return (None if target is None else DamageRequestFact( source_entity_uuid=source,
                target_entity_uuid=target, intercepted_by_condition_uuid=event.intercepted_by_condition_uuid,
                relentless_rage=event.relentless_rage,
                source_condition_uuid=event.source_condition_uuid if (
                    senses is not None and event.source_condition_uuid in senses.spatial_effects
                    or source is not None and source in actors and any(
                        member.condition_uuid == event.source_condition_uuid
                        and member.category is not ConditionCategory.INTERNAL
                        for member in actors[source].conditions)) else None))
        case DamageAppliedEvent():
            if target is None:
                return None
            spatial_source = event.spatial_source if event.applied_damage > 0 else None
            if spatial_source is not None:
                effect = (senses.spatial_effects.get(spatial_source.spatial_effect_uuid)
                          if senses is not None else None)
                contact = senses.entities.get(target) if senses is not None else None
                if (effect is None or spatial_source.position not in effect.positions
                        or senses is None or not cell_in(senses.visible, spatial_source.position)
                        or not (observer.controls(target) or contact is not None and contact.visual
                            and contact.position == spatial_source.target_position)):
                    spatial_source = None
            release = None
            recorded = event.body_release
            if recorded is not None:
                contact = senses.entities.get(target) if senses is not None else None
                located = (observer.controls(target) or _position_allowed(event, recorded.position, observer)
                    or observer.granted(event.located_entity_observer_uuids.get(str(target), set()))
                    and contact is not None and contact.visual and contact.position == recorded.position)
                if not located:
                    # Entry payloads can complete before their sensory child.
                    # A disclosed native edge already grants its reached cell.
                    by_lineage = {row.lineage_uuid: row for row in events}
                    parent = event.parent_lineage
                    while parent is not None and parent in by_lineage:
                        ancestor = by_lineage[parent]
                        if (isinstance(ancestor, StepMovementEvent)
                                and ancestor.source_entity_uuid == target and _step_allowed(ancestor, observer)
                                and recorded.position in (ancestor.disclosed_path or (
                                    ancestor.from_position, ancestor.to_position))
                                or isinstance(ancestor, ForcedMovementEvent)
                                and ancestor.target_entity_uuid == target and _forced_allowed(ancestor, observer)
                                and recorded.position in (ancestor.start_position, ancestor.end_position)):
                            located = True
                            break
                        parent = ancestor.parent_lineage
                if located:
                    deposited = recorded.deposited_position
                    if (deposited is not None and deposited != recorded.position
                            and not _position_allowed(event, deposited, observer)
                            and (senses is None or not cell_in(senses.visible, deposited))):
                        deposited = None
                    regions = []
                    for region in recorded.regions:
                        positions = tuple(cell for cell in region.positions
                            if cell == recorded.position or _position_allowed(event, cell, observer)
                            or senses is not None and cell_in(senses.visible, cell))
                        if positions:
                            regions.append(BodyReleaseRegion(ellipse=region.ellipse,
                                elevation_steps=region.elevation_steps, positions=positions))
                    release = BodyReleaseResult(release_id=recorded.release_id, position=recorded.position,
                        occupancy_layer=recorded.occupancy_layer, deposited_position=deposited,
                        pattern=recorded.pattern, critical_hit=recorded.critical_hit, regions=tuple(regions),
                        primary_damage_type=recorded.primary_damage_type,
                        secondary_damage_type=recorded.secondary_damage_type)
            return DamageResultFact( source_entity_uuid=source, target_entity_uuid=target,
                applied_damage=event.applied_damage, resulting_normal_hp=event.resulting_normal_hp,
                resulting_temporary_hp=event.resulting_temporary_hp, damage_type=event.damage_type,
                spatial_source=spatial_source,
                source_condition_uuid=event.source_condition_uuid if (
                    senses is not None and event.source_condition_uuid in senses.spatial_effects
                    or source is not None and source in actors and any(
                        member.condition_uuid == event.source_condition_uuid
                        and member.category is not ConditionCategory.INTERNAL
                        for member in actors[source].conditions)) else None,
                body_release=release, effect_id=event.effect_id if event.effect_id is not None and senses is not None
                    and any(effect.content_ref.identity_key == event.effect_id
                            for effect in senses.spatial_effects.values()) else None)
        case HealEvent():
            return (None if target is None else HealFact(source_entity_uuid=source, target_entity_uuid=target,
                actual_healing=event.actual_healing, was_blocked=event.was_blocked,
                source_condition_uuid=event.source_condition_uuid if target in actors and any(
                    member.condition_uuid == event.source_condition_uuid
                    and member.category is not ConditionCategory.INTERNAL
                    for member in actors[target].conditions) else None,
                resulting_normal_hp=event.resulting_normal_hp, resulting_temporary_hp=event.resulting_temporary_hp))
        case TemporaryHitPointsChangedEvent():
            return (None if event.entity_uuid not in known or not _identified(event, event.entity_uuid, observer)
                    else TemporaryHitPointsFact(entity_uuid=event.entity_uuid,
                        resulting_temporary_hp=event.resulting_temporary_hp, grant=event.grant))
        case EntityFactionChangedEvent():
            located = (observer.controls(event.entity_uuid) or observer.granted(event.located_entity_observer_uuids.get(str(event.entity_uuid), set())))
            return (FactionFact(entity_uuid=event.entity_uuid, faction_after=event.faction_after)
                    if event.entity_uuid in known and _identified(event, event.entity_uuid, observer) and located else None)
        case LifeStateChangeEvent():
            return (None if event.entity_uuid not in known or not _identified(event, event.entity_uuid, observer) else LifeFact(
                entity_uuid=event.entity_uuid, previous_state=event.previous_state, new_state=event.new_state,
                reason=event.reason, normal_hit_points=event.normal_hit_points,
                remains_disposition=event.remains_disposition,
                preserved_equipped_item_uuids=tuple(identity
                    for death in events if isinstance(death, DeathEvent) and not death.canceled
                    and death.phase is EventPhase.COMPLETION
                    and death.lineage_uuid == event.parent_lineage
                    for identity in death.preserved_item_uuids
                    if identity in {item for _, item in actors[event.entity_uuid].equipment})))
        case DeathSaveEvent():
            return (None if event.entity_uuid not in known or not _identified(event, event.entity_uuid, observer) else DeathSaveFact(
                entity_uuid=event.entity_uuid, natural_roll=event.natural_roll, succeeded=event.succeeded))
        case SavingThrowEvent():
            return (None if target is None or event.result is None else SavingThrowFact(
                target_entity_uuid=target, ability_name=event.ability_name, succeeded=event.result,
                indomitable_reroll=event.indomitable_reroll,
                effect_id=event.saving_throw_context.effect_id if event.saving_throw_context is not None else None))
        case ItemResourceChangeEvent():
            return (ItemChargeFact(source_entity_uuid=event.source_entity_uuid, item_uuid=event.item_uuid,
                charges_after=event.charges_after, stack_count_after=event.stack_count_after,
                item_destroyed=event.item_destroyed, resource_change=event.resource_change) if observer.controls(event.source_entity_uuid) else None)
        case EquipmentEvent() | ItemLocationStateEvent() | ItemHoldingsReleasedEvent():
            owner = actor_fact_owner(event)
            if owner is None or owner not in known or owner not in actors or not _identified(event, owner, observer):
                return None
            actor = actors[owner]
            return EquipmentFact(source_entity_uuid=owner, changes={**_holdings(actor, observer),
                "armor_class": actor.armor_class}, items=_item_records(actor, observer, records))
        case SpatialChangeEvent():
            if event.change_type in (SpatialChangeType.OBJECT_PLACED, SpatialChangeType.OBJECT_REMOVED,
                                     SpatialChangeType.OBJECT_CHANGED):
                if event.canceled or event.phase is not EventPhase.COMPLETION or event.object_uuid is None:
                    return None
                snapshot = declaration_senses if event.change_type is SpatialChangeType.OBJECT_REMOVED else senses
                contact = snapshot.objects.get(event.object_uuid) if snapshot is not None else None
                placement = event.previous_placement if event.change_type is SpatialChangeType.OBJECT_REMOVED else event.placement
                if contact is None or placement is None or contact.position not in placement.positions:
                    return None
                return SpatialFact(change_type=event.change_type, entity_uuid=None, object_uuid=event.object_uuid,
                    position=contact.position, commit_occurrence=_version_key(keys, event.commit_event_uuid))
            identified_entity = event.entity_uuid if _identified(event, event.entity_uuid, observer) else None
            own_position = observer.controls(identified_entity)
            if event.change_type not in (SpatialChangeType.ENTITY_ENTERED, SpatialChangeType.ENTITY_LEFT,
                                         SpatialChangeType.PERCEIVABILITY_CHANGED, SpatialChangeType.MOVEMENT_COLLISION):
                return None
            parent = next((row for row in events if row.lineage_uuid == event.parent_lineage), None)
            parent_geometry = (
                isinstance(parent, ForcedMovementEvent) and parent.target_entity_uuid == event.entity_uuid
                and _forced_allowed(parent, observer)
                or isinstance(parent, StepMovementEvent) and parent.source_entity_uuid == event.entity_uuid
                and _step_allowed(parent, observer))
            departed_contact = (declaration_senses.entities.get(event.entity_uuid)
                if declaration_senses is not None and event.entity_uuid is not None else None)
            terminal = (event.change_type is SpatialChangeType.ENTITY_LEFT
                and event.phase is EventPhase.COMPLETION and not event.canceled
                and event.terminal_release is not None
                and event.terminal_release.entity_uuid == event.entity_uuid)
            witnessed_departure = (terminal and departed_contact is not None
                and departed_contact.visual and departed_contact.position == event.position)
            located_arrival = (event.change_type is SpatialChangeType.ENTITY_ENTERED
                and observer.granted(event.located_entity_observer_uuids.get(str(event.entity_uuid), set())))
            if identified_entity is None or not (own_position or parent_geometry or located_arrival or witnessed_departure
                                                or _position_allowed(event, event.position, observer)):
                return None
            departure = (event.position if event.change_type is SpatialChangeType.ENTITY_LEFT
                         else event.old_position)
            arrival = (event.position if event.change_type is SpatialChangeType.ENTITY_ENTERED
                       else event.old_position)
            departure_allowed = own_position or parent_geometry or witnessed_departure or (
                departure is not None and _position_allowed(event, departure, observer))
            arrival_allowed = own_position or parent_geometry or located_arrival or (
                arrival is not None and _position_allowed(event, arrival, observer))
            contact = senses.entities.get(identified_entity) if senses is not None else None
            birth = next((row for row in events if isinstance(row, EntityCreatedEvent)
                and row.entity_uuid == event.entity_uuid
                and row.phase is EventPhase.COMPLETION and not row.canceled
                and row.parent_lineage is not None and row.parent_lineage == event.parent_lineage
                and row.summon_origin is not None
                and row.summon_origin.cast_lineage_uuid == row.parent_lineage), None)
            creation = (CreationWitness(birth_occurrence=keys.versions[birth.uuid], manifestation=birth.summon_origin.manifestation)
                if event.change_type is SpatialChangeType.ENTITY_ENTERED
                and event.phase is EventPhase.COMPLETION and not event.canceled
                and event.old_position is None and event.previous_occupancy_layer is None
                and birth is not None and birth.summon_origin is not None
                and contact is not None and contact.visual and contact.position == event.position else None)
            return SpatialFact(change_type=event.change_type, entity_uuid=identified_entity, position=event.position,
                commit_occurrence=_version_key(keys, event.commit_event_uuid),
                previous_occupancy_layer=event.previous_occupancy_layer if departure_allowed else None,
                occupancy_layer=event.occupancy_layer if arrival_allowed else None,
                terminal_departure=terminal,
                terminal_cause=event.terminal_release.cause if witnessed_departure and event.terminal_release is not None else None,
                creation=creation)
        case TurnEvent():
            return (TurnFact(event_type=event.event_type, entity_uuid=event.entity_uuid, round_number=event.round_number)
                if _identified(event, event.entity_uuid, observer) else None)
        case RoundEvent():
            return TurnFact(event_type=event.event_type, entity_uuid=None, round_number=event.round_number)
        case EncounterEvent():
            return TurnFact(event_type=event.event_type, entity_uuid=None, round_number=None)
        case _ if condition is not None:
            item = condition.resulting_item
            if item is not None:
                return (ItemEffectChangeFact(item_uuid=item.item_uuid,
                    effect_uuid=condition.condition_uuid, event_type=event.event_type)
                    if item.item_uuid in observed_objects or _held_item_disclosed(
                        item.item_uuid, event, observer, actors, known, senses) else None)
            return (None if target is None or condition.category is ConditionCategory.INTERNAL else
                ConditionChangeFact(target_entity_uuid=target, event_type=event.event_type, condition=condition,
                    consumed=condition.consumed))
        case CounterspellReactionEvent():
            return (None if source is None or target is None else ActionFact(
                source_entity_uuid=source, target_entity_uuid=target,
                behavior_id=event.behavior_id, name=event.name,
                reaction=ActionReaction(triggered_lineage=_lineage_key(keys, event.triggered_lineage_uuid),
                    succeeded=event.succeeded, automatic=event.automatic)))
        case ActionEvent():
            object_target = event.target_entity_uuid if event.target_entity_uuid in observed_objects else target
            return (None if source is None else ActionFact(source_entity_uuid=source, target_entity_uuid=object_target,
                behavior_id=event.behavior_id, name=_action_name(event, observer),
                font_conversion=(event.font_conversion if observer.controls(source) else
                    FontConversion(direction=event.font_conversion.direction)
                    if event.font_conversion is not None else None),
                source_item_uuid=event.source_item_uuid if event.source_item_uuid in observed_objects else None))
    return None


def _application(keys: "NativeKeys", application: ApplicationMembership | None) -> SpellApplication | None:
    """A spell's application named by its owning lineage's native key; none without a key for that lineage."""
    key = _lineage_key(keys, application.lineage_uuid) if application is not None else None
    if application is None or key is None:
        return None
    return SpellApplication(lineage=key, application_id=application.application_id, index=application.index)


def _resolution(keys: "NativeKeys", reference: ResolutionRef | None) -> tuple[int, UUID | None] | None:
    """A resolution reference as its lineage's native key and its application's identity, if it has one."""
    if reference is None or (key := _lineage_key(keys, reference.lineage_uuid)) is None:
        return None
    return key, reference.application_id if reference.kind == "application" else None


def _content_attributions(event: Event, fact: PlayerFact | None, observer: PlayerAudience,
                          disclosed_lineages: set[int], keys: "NativeKeys",
                          known_content: frozenset[str]) -> tuple[ContentAttribution, ...]:
    result: list[ContentAttribution] = []
    def provider(identity: str | None) -> str | None:
        return identity if observer.controls(event.source_entity_uuid) or identity in known_content else None

    if fact is not None and isinstance(event, ActionEvent) and event.behavior_id is not None:
        result.append(ContentAttribution(role="behavior", behavior_id=event.behavior_id,
            provided_by_id=provider(event.provided_by_id), origin_root_id=provider(event.origin_root_id)))
    if (fact is not None and isinstance(event, ActionEvent) and event.source_item_presentation is not None
            and (observer.controls(event.source_entity_uuid) or event.source_item_presentation.item_id in known_content)):
        result.append(ContentAttribution(role="source_item", behavior_id=event.source_item_presentation.item_id))
    for evidence in event.effective_handler_presentations:
        if not _identified(event, evidence.source_entity_uuid, observer):
            continue
        emitted = tuple(key for identity in evidence.emitted_lineage_uuids
            if (key := _lineage_key(keys, identity)) is not None and key in disclosed_lineages)
        if evidence.outcome is HandlerDispatchOutcome.EMITTED_EVENTS and not emitted:
            continue
        result.append(ContentAttribution(role="effective_handler", behavior_id=evidence.behavior_id,
            provided_by_id=evidence.provided_by_id if observer.controls(evidence.source_entity_uuid) or evidence.provided_by_id in known_content else None,
            origin_root_id=evidence.origin_root_id if observer.controls(evidence.source_entity_uuid) or evidence.origin_root_id in known_content else None,
            source_entity_uuid=evidence.source_entity_uuid,
            triggering_occurrence=_version_key(keys, evidence.triggering_event_uuid),
            triggering_lineage=_lineage_key(keys, evidence.triggering_lineage_uuid),
            emitted_lineages=emitted, handler_name=evidence.handler_name,
            dispatch_index=evidence.dispatch_index, outcome=evidence.outcome))
    return tuple(result)


def _observed_remnant(state: ItemRemnantState | None, known_objects: Collection[UUID],
                      observed_objects: Collection[UUID] = ()) -> ItemRemnantState | None:
    """A composite never supplies identities or pixels of undisclosed attachments."""
    if state is None:
        return None
    return state.model_copy(update={"intact_supported_items": tuple(
        identity for identity in state.intact_supported_items
        if identity in known_objects or identity in observed_objects)})


def _floor_item(item: ItemPresentationState, residues: tuple[ObjectResidueState, ...]) -> FloorItem:
    return FloorItem(item_uuid=item.item_uuid, item_id=item.item_id, name=item.name,
        visual_item_name=item.visual_item_name, visual_variant_id=item.visual_variant_id,
        stack_count=item.stack_count, is_pickable=item.is_pickable, item_effects=item.item_effects,
        map_char=item.map_char, boundary_structure=item.boundary_structure,
        contact_passage=item.contact_passage,
        supported_by_uuid=item.supported_by_uuid,
        blocks_propagation=item.blocks_propagation,
        is_open=item.is_open, is_lit=item.is_lit, is_engaged=item.is_engaged,
        very_bright_radius_feet=item.very_bright_radius_feet,
        bright_radius_feet=item.bright_radius_feet,
        dim_radius_feet=item.dim_radius_feet,
        surface_residues=residues, current_hit_points=item.current_hit_points, maximum_hit_points=item.maximum_hit_points,
        concentration_capacity=item.concentration_capacity, concentration_slots=item.concentration_slots,
        door_mechanism=item.door_mechanism, door_swing=item.door_swing, remnant_state=item.remnant_state,
        integrity=item.integrity, destruction_outcome=item.destruction_outcome,
        construction_owner_uuid=item.construction_owner_uuid, construction_geometry=item.construction_geometry,
        construction_suppressions=item.construction_suppressions, known_to_creator=item.known_to_creator)


_DELTAS = {CardinalDirection.NORTH: (0, 1), CardinalDirection.SOUTH: (0, -1),
           CardinalDirection.EAST: (1, 0), CardinalDirection.WEST: (-1, 0)}
_OPPOSITE = {CardinalDirection.NORTH: CardinalDirection.SOUTH,
             CardinalDirection.SOUTH: CardinalDirection.NORTH,
             CardinalDirection.EAST: CardinalDirection.WEST,
             CardinalDirection.WEST: CardinalDirection.EAST}


def _object_observed(world: PresentationTarget, identity: UUID) -> bool:
    senses = world.senses
    if senses is None:
        return False
    if identity in senses.objects:
        return True
    obj = world.objects[identity]
    # An attachment has its own native observation grant. A visible supporting
    # wall is not permission to disclose a hidden insert.
    if obj.item.supported_by_uuid is not None:
        return False
    direction = obj.placement.boundary_direction
    if direction is None or obj.item.boundary_structure is None:
        return False
    x, y = obj.placement.position
    dx, dy = _DELTAS[direction]
    # Boundary appearance belongs to either observed incident support, including
    # a wall which stops its author's cell from entering optical visibility.
    return cell_in(senses.visible, (x, y)) or cell_in(senses.visible, (x + dx, y + dy))


def _observed_object(world: PresentationTarget, remembered: PlayerState, identity: UUID,
                     observed_objects: Collection[UUID]) -> PlayerObject:
    """Refresh seen wall faces while preserving the last observation of others."""
    obj = world.objects[identity]
    direction = obj.placement.boundary_direction
    visible_faces: set[CardinalDirection] = set()
    if direction is not None and world.senses is not None:
        x, y = obj.placement.position
        dx, dy = _DELTAS[direction]
        if cell_in(world.senses.visible, (x, y)):
            visible_faces.add(_OPPOSITE[direction])
        if cell_in(world.senses.visible, (x + dx, y + dy)):
            visible_faces.add(direction)
    previous = remembered.objects.get(identity)
    retained: dict[UUID, ObjectResidueState] = {}
    if previous is not None:
        for residue in previous.item.surface_residues:
            faces = tuple(face for face in residue.faces if face not in visible_faces)
            if faces:
                retained[residue.condition_uuid] = residue.model_copy(update={"faces": faces})
    for residue in obj.item.surface_residues:
        faces = {face for face in residue.faces if face in visible_faces}
        if not faces:
            continue
        prior = retained.get(residue.condition_uuid)
        if prior is not None:
            faces.update(prior.faces)
        retained[residue.condition_uuid] = residue.model_copy(update={
            "faces": tuple(sorted(faces, key=lambda face: face.value)),
        })
    senses = world.senses
    previous = remembered.objects.get(identity)
    retained_suppressions = ({row.provider_uuid: row for row in previous.item.construction_suppressions}
        if previous is not None else {})
    suppressions = []
    for outcome in obj.item.construction_suppressions:
        provider = senses.spatial_effects.get(outcome.provider_uuid) if senses is not None else None
        retained_suppression = retained_suppressions.get(outcome.provider_uuid)
        if provider is not None and provider.area_geometry is not None:
            retained_suppression = outcome.model_copy(update={"provider_content_ref": provider.content_ref,
                "area_geometry": provider.area_geometry, "anchor_elevation_steps": provider.anchor_elevation_steps})
        if retained_suppression is not None:
            admitted = {position for position in outcome.positions if senses is not None and cell_in(senses.visible, position)}
            suppressions.append(retained_suppression.model_copy(update={"positions": tuple(sorted(admitted))}))
    item = obj.item.model_copy(update={"remnant_state": _observed_remnant(
        obj.item.remnant_state, remembered.objects, observed_objects),
        "construction_suppressions": tuple(suppressions)})
    contact = senses.objects.get(identity) if senses is not None else None
    contained_items = None
    if (obj.contained_items is not None and (item.is_open is True or item.integrity is ItemIntegrity.DESTROYED)
            and contact is not None and contact.visual):
        contained_items = tuple(_floor_item(child, ()) for child in obj.contained_items)
    return PlayerObject(placement=obj.placement, item=_floor_item(item,
        tuple(retained[identity] for identity in sorted(retained, key=str))),
        contained_items=contained_items)


def _observed_plain_or_object(world: PresentationTarget, remembered: PlayerState, identity: UUID,
                              index: "WorldProjectionIndex") -> PlayerObject:
    """`_observed_object`, reusing a plain placed object's value while its inputs are unchanged.

    Without side faces, residues, suppressions or a remnant (and no remembered
    residues), the observation depends only on the recorded value and whether
    its contact is visual.
    """
    obj = world.objects[identity]
    item = obj.item
    previous = remembered.objects.get(identity)
    if (obj.placement.boundary_direction is not None or item.surface_residues or item.construction_suppressions
            or item.remnant_state is not None or (previous is not None and previous.item.surface_residues)):
        return _observed_object(world, remembered, identity, index.observed)
    contact = world.senses.objects.get(identity) if world.senses is not None else None
    visual = contact is not None and contact.visual
    cached = index.observed_values.get(identity)
    if cached is not None and cached[0] is obj and cached[1] == visual:
        return cached[2]
    value = _observed_object(world, remembered, identity, index.observed)
    index.observed_values[identity] = (obj, visual, value)
    return value


@dataclass(slots=True)
class WorldProjectionIndex:
    """Audience memberships over current contacts and last-observed placements."""

    observed: set[UUID] = field(default_factory=set)
    remembered_positions: dict[tuple[int, int], set[UUID]] = field(default_factory=dict)
    remembered_order: dict[UUID, int] = field(default_factory=dict)
    next_order: int = 0
    knowledge_removed: set[UUID] = field(default_factory=set)
    # A plain placed object's last observation with its two inputs: the frozen
    # recorded value (replaced on every change) and whether the contact is visual.
    observed_values: dict[UUID, tuple[WorldObjectState, bool, PlayerObject]] = field(default_factory=dict)


def _remember_object(index: WorldProjectionIndex, before: PlayerObject | None,
                     after: PlayerObject | None) -> None:
    if before is not None:
        identity = before.item.item_uuid
        for position in before.placement.positions:
            members = index.remembered_positions[position]
            members.remove(identity)
            if not members:
                del index.remembered_positions[position]
        if after is None:
            del index.remembered_order[identity]
    if after is not None:
        identity = after.item.item_uuid
        if identity not in index.remembered_order:
            index.remembered_order[identity] = index.next_order
            index.next_order += 1
        for position in after.placement.positions:
            index.remembered_positions.setdefault(position, set()).add(identity)


def _tile_changes(before: WorldTileState, after: WorldTileState) -> WorldTileChanges:
    changes: WorldTileChanges = {}
    if before.surface != after.surface:
        changes['surface'] = after.surface
    if before.name != after.name:
        changes['name'] = after.name
    if before.blocks_optics != after.blocks_optics:
        changes['blocks_optics'] = after.blocks_optics
    if before.blocks_propagation != after.blocks_propagation:
        changes['blocks_propagation'] = after.blocks_propagation
    if before.walking_cost != after.walking_cost:
        changes['walking_cost'] = after.walking_cost
    if before.flying_cost != after.flying_cost:
        changes['flying_cost'] = after.flying_cost
    if before.swimming_cost != after.swimming_cost:
        changes['swimming_cost'] = after.swimming_cost
    if before.burrowing_cost != after.burrowing_cost:
        changes['burrowing_cost'] = after.burrowing_cost
    if before.elevation_steps != after.elevation_steps:
        changes['elevation_steps'] = after.elevation_steps
    if before.surface_kind != after.surface_kind:
        changes['surface_kind'] = after.surface_kind
    if before.slope_axis != after.slope_axis:
        changes['slope_axis'] = after.slope_axis
    if before.default_light != after.default_light:
        changes['default_light'] = after.default_light
    if before.condition_names != after.condition_names:
        changes['condition_names'] = after.condition_names
    if before.residues != after.residues:
        changes['residues'] = after.residues
    return changes


def _world_update(world: PresentationTarget, remembered: PlayerState, occurrence: int,
                  positions: set[tuple[int, int]], object_positions: set[tuple[int, int]], identities: set[UUID],
                  index: WorldProjectionIndex) -> WorldUpdate | None:
    senses = world.senses
    if senses is None or world.world is None:
        return None
    tiles = []
    tile_changes = []
    lights: dict[tuple[int, int], int] = {}
    for position in sorted(positions):
        current = world.tiles.get(position)
        previous = remembered.tiles.get(position)
        # A tile the seat holds as the recorded value itself is unchanged.
        if current is None or previous is current or not cell_in(senses.visible, position):
            continue
        if previous is None or previous.tile_uuid != current.tile_uuid:
            tiles.append(current)
        elif previous != current:
            changes = _tile_changes(previous, current)
            if changes:
                tile_changes.append(TileFieldUpdate(position=position, changes=changes))
            if previous.resolved_light != current.resolved_light:
                lights[position] = current.resolved_light
    identities.update(world_objects_at(world.recorded_world, object_positions))
    for position in object_positions & index.remembered_positions.keys():
        identities.update(index.remembered_positions[position])
    constructions = world.recorded_world.constructions_by_position
    for position in object_positions & constructions.keys():
        identities.update(constructions[position])
    # A removal keeps the entry knowledge grant for this event. Its dependents
    # observe the loss at the next world projection, matching the recorded fold.
    for identity in identities | index.knowledge_removed:
        identities.update(world.recorded_world.remnants_by_item.get(identity, ()))
    index.knowledge_removed.clear()
    observed_ids = {identity for identity in identities
        if identity in world.objects and _object_observed(world, identity)}
    index.observed.difference_update(identities)
    index.observed.update(observed_ids)
    observed = {identity: _observed_plain_or_object(world, remembered, identity, index)
                for identity in observed_ids}
    removed = tuple(sorted((identity for identity in identities
        if identity in remembered.objects and identity not in observed
        and any(cell_in(senses.visible, position) for position in remembered.objects[identity].placement.positions)),
        key=index.remembered_order.__getitem__))
    changed = {identity: value for identity, value in observed.items()
               if (held := remembered.objects.get(identity)) is not value and held != value}
    # Remembered silhouettes may remain out of sight. Contents are current
    # observations, so losing the grant clears them without exposing new state.
    for identity in identities:
        previous = remembered.objects.get(identity)
        if (previous is not None and identity not in observed and identity not in removed
                and previous.contained_items is not None):
            changed[identity] = replace(previous, contained_items=None)
    objects = tuple(changed[identity] for identity in sorted(changed, key=str))
    connectors = tuple(row for row in world.recorded_world.connectors.values()
                       if all(cell_in(senses.visible, point) for point in row.endpoints))
    if (not tiles and not tile_changes and not lights and not objects and not removed
            and connectors == remembered.connectors):
        return None
    update = WorldUpdate(occurrence=occurrence, tiles=tuple(tiles), objects=objects,
                         objects_removed=removed, connectors=connectors, tile_changes=tuple(tile_changes),
                         resolved_light=values_from_items(lights))
    for identity in removed:
        _remember_object(index, remembered.objects[identity], None)
    for obj in objects:
        _remember_object(index, remembered.objects.get(obj.item.item_uuid), obj)
    index.knowledge_removed.update(removed)
    apply_world_update(remembered, update)
    return update


@dataclass(frozen=True, slots=True)
class NativeKeys:
    """The walk's version and lineage identities: a version's native cursor, a lineage's first version's.

    `_public_occurrences` maps both to the seat's occurrence indices.
    """

    versions: Mapping[UUID, int]
    lineages: Mapping[UUID, int]


def _version_key(keys: NativeKeys, identity: UUID | None) -> int | None:
    return keys.versions.get(identity) if identity is not None else None


def _lineage_key(keys: NativeKeys, identity: UUID | None) -> int | None:
    return keys.lineages.get(identity) if identity is not None else None


def _remember_versions(versions: dict[UUID, int], lineages: dict[UUID, int], rows: tuple[ObjectiveRow, ...]) -> None:
    for row in rows:
        versions[row.event_uuid] = row.source_index
        lineages.setdefault(row.lineage_uuid, row.source_index)


@dataclass(frozen=True, slots=True)
class LineageDisclosure:
    """The lineages disclosed to the seat (native keys) and the keys of native lineage identities."""

    disclosed: set[int]
    keys: NativeKeys


def _lineage_disclosed(disclosure: LineageDisclosure, identity: UUID | None) -> bool:
    key = _lineage_key(disclosure.keys, identity)
    return key is not None and key in disclosure.disclosed


def _disclosed_slots(slots: tuple[ItemConcentrationSlot, ...], disclosed: LineageDisclosure
                     ) -> tuple[ItemConcentrationSlot, ...]:
    return tuple(slot if _lineage_disclosed(disclosed, slot.cast_lineage_uuid) else
                 slot.model_copy(update={"cast_lineage_uuid": None}) for slot in slots)


def _disclosed_item(item: ItemPresentationState, disclosed: LineageDisclosure) -> ItemPresentationState:
    return item.model_copy(update={"concentration_slots": _disclosed_slots(item.concentration_slots, disclosed)})


def _disclosed_condition(condition: ConditionFact, disclosed: LineageDisclosure) -> ConditionFact:
    state = condition.state
    return replace(condition,
        state=state.model_copy(update={"concentration_slots": _disclosed_slots(state.concentration_slots, disclosed)})
            if state is not None else None,
        resulting_item=_disclosed_item(condition.resulting_item, disclosed)
            if condition.resulting_item is not None else None)


def _disclosed_changes(changes: ActorChanges, disclosed: LineageDisclosure) -> ActorChanges:
    if "conditions" not in changes:
        return changes
    return {**changes, "conditions": tuple(_disclosed_condition(row, disclosed) for row in changes["conditions"])}


def _disclosed_items(patches: tuple[ItemPatch, ...], disclosed: LineageDisclosure) -> tuple[ItemPatch, ...]:
    """The records with undisclosed casting lineages cleared; a record without concentration slots is itself."""
    return tuple(replace(row, state=replace(row.state, concentration_slots=_disclosed_slots(
        row.state.concentration_slots, disclosed))) if row.state is not None and row.state.concentration_slots else row
        for row in patches)


def _project_nodes(events: tuple[Event, ...], versions: tuple[ObjectiveRow, ...],
                   admissions: tuple[ActorAdmission, ...], conditions: tuple[ConditionFact, ...],
                   private_world: PresentationTarget, private_actors: dict[UUID, ActorState],
                   observer: PlayerAudience, known_actors: Collection[UUID],
                   remembered: PlayerState, disclosed: set[int], world_index: WorldProjectionIndex,
                   audience_composition: AudienceComposition, logs: Mapping[UUID, PlayerLogEntry],
                   keys: NativeKeys, table: SensoryTable, observed_sources: tuple[Event, ...] = ()
                   ) -> tuple[tuple[PlayerNode, ...], tuple[PlayerObservation, ...], tuple[WorldUpdate, ...],
                              frozenset[int], frozenset[int], dict[int, tuple[int, UUID | None]]]:
    """Walk one lineage privately: nodes, observed bodies and items (complete values, not yet patches), world updates.

    The walk folds senses and world, not bodies: it reads which actors the
    seat has bodies for and their condition memberships. The seat's bodies
    change only when the emitted lineage is folded (`_emit_bodies`). Also
    returns the spatial facts the walk's commit order superseded, and the
    removals of a known membership, whose value `_emit_bodies` takes from the
    seat's body, and each node's disclosed resolution (its lineage's native
    key and application) by the node's native occurrence. Versions and
    lineages are identified by their native keys (`NativeKeys`) until
    `_public_occurrences`. Sensory facts name rows of the group's `table`.
    """
    events = upgrade_recorded_spatial_commits(events, tuple(
        (row.lineage_uuid, row.event_uuid) for row in sorted(versions, key=lambda row: row.source_index)))
    indexes = {row.event_uuid: row.source_index for row in versions}
    occurrences = frozenset(indexes.values())
    disclosure = LineageDisclosure(disclosed, keys)
    by_version = {event.uuid: event for event in (*observed_sources, *events)}
    facts = {row.event_uuid: row for row in conditions}
    observations: list[PlayerObservation] = []
    updates: list[WorldUpdate] = []
    nodes: list[PlayerNode] = []
    # The actors the seat has bodies for, and the condition memberships it holds, at this point of the walk.
    known: set[UUID] = set(known_actors)
    members: dict[UUID, dict[UUID, ConditionFact]] = {}

    def held_conditions(identity: UUID) -> dict[UUID, ConditionFact]:
        if identity not in members:
            members[identity] = {row.condition_uuid: row for row in remembered.actors[identity].conditions}
        return members[identity]

    superseded: set[int] = set()
    known_removals: set[int] = set()
    content_at_event: dict[UUID, frozenset[str]] = {}
    pending = iter(sorted(admissions, key=lambda row: indexes[row.event_uuid]))
    admission = next(pending, None)
    by_lineage = {event.lineage_uuid: event for event in events}
    version_lineages = {row.event_uuid: row.lineage_uuid for row in versions}
    # A delivery can obscure itself; a field removal clears its contact through
    # a sensory child before completing. Retain each event's entry sight: a
    # nested event must not borrow its outer root's earlier observation.
    delivery_starts: dict[UUID, int] = {}
    for version in versions:
        declared = by_lineage.get(version.lineage_uuid)
        if (isinstance(declared, (MechanismActivationEvent, DeathEvent))
                or isinstance(declared, (AttackEvent, SpellEvent)) and declared.target_kind == "object"
                or isinstance(declared, SpellEvent) and declared.area_geometry is not None
                or isinstance(declared, SpatialChangeEvent) and (
                    declared.terminal_release is not None and declared.change_type is SpatialChangeType.ENTITY_LEFT
                    or declared.change_type is SpatialChangeType.OBJECT_REMOVED)
                or isinstance(declared, SpatialEffectChangeEvent)
                and declared.operation in (SpatialEffectChangeOperation.REMOVED, SpatialEffectChangeOperation.FOOTPRINT_CHANGED)):
            delivery_starts.setdefault(version.lineage_uuid, version.source_index)
    pending_deliveries = iter(sorted(delivery_starts.items(), key=lambda row: row[1]))
    next_delivery = next(pending_deliveries, None)
    delivery_declarations: dict[UUID, DeclarationSenses | None] = {}
    # A break's sensory children can run before its completion. Capture the
    # contact at the integrity transition's entry; old recordings instead
    # witness the removal which preceded their replacement-object fact.
    destroyed_ids = {event.item_state.item_uuid for event in events
                     if isinstance(event, ItemLocationStateEvent) and event.location is ItemLocation.DESTROYED}
    explicit_destructions = {event.item_uuid for event in events if isinstance(event, ItemDestructionEvent)}
    removal_starts: dict[UUID, int] = {}
    for version in versions:
        removed = by_lineage.get(version.lineage_uuid)
        if isinstance(removed, ItemDestructionEvent) and not removed.canceled:
            removal_starts.setdefault(removed.item_uuid, version.source_index)
        elif (isinstance(removed, SpatialChangeEvent) and not removed.canceled
                and removed.change_type is SpatialChangeType.OBJECT_REMOVED and removed.object_uuid in destroyed_ids):
            assert removed.object_uuid is not None
            removal_starts.setdefault(removed.object_uuid, version.source_index)
    pending_removals = iter(sorted(removal_starts.items(), key=lambda row: row[1]))
    next_removal = next(pending_removals, None)
    destroyed_contacts: dict[UUID, PlayerObject] = {}
    # An interaction may itself hide the object. Retain its already granted
    # identity at entry; a remote control's undisclosed target gains no identity.
    observed_objects = set(world_index.observed)
    records: ItemRecords = {}
    for event in events:
        while next_removal is not None and next_removal[1] <= indexes[event.uuid]:
            identity = next_removal[0]
            if identity in private_world.objects and _object_observed(private_world, identity):
                destroyed_contacts[identity] = _observed_object(
                    private_world, remembered, identity, world_index.observed)
            next_removal = next(pending_removals, None)
        while next_delivery is not None and next_delivery[1] <= indexes[event.uuid]:
            senses = private_world.senses
            delivery_declarations[next_delivery[0]] = (None if senses is None else DeclarationSenses(
                senses.visible, dict(senses.entities), dict(senses.objects), dict(senses.spatial_effects)))
            next_delivery = next(pending_deliveries, None)
        while admission is not None and indexes[admission.event_uuid] <= indexes[event.uuid]:
            private_actors[admission.actor.uuid] = admission.actor
            observed = _public_actor(admission.actor, observer)
            observations.append(PlayerObservation(occurrence=indexes[admission.event_uuid], actor_uuid=observed.uuid,
                changes=actor_changes(None, observed), contact=admission.contact,
                items=_item_records(admission.actor, observer, records)))
            known.add(observed.uuid)
            members[observed.uuid] = {row.condition_uuid: row for row in observed.conditions}
            admission = next(pending, None)
        if not event.canceled:
            if isinstance(event, EntityCreatedEvent):
                private_actors[event.entity_uuid] = actor_from_birth(event)
            owner = actor_fact_owner(event)
            if isinstance(event, ItemLocationStateEvent):
                removed_holders = remove_previous_item_holdings(private_actors, event)
                for identity in removed_holders:
                    contact = private_world.senses.entities.get(identity) if private_world.senses is not None else None
                    if identity in known and (observer.controls(identity) or contact is not None and contact.visual):
                        observations.append(_gear_observation(indexes[event.uuid], private_actors[identity], observer,
                            records))
            if owner is not None and owner in private_actors:
                private_actors[owner] = apply_actor_fact(private_actors[owner], event, facts.get(event.uuid))
            condition = facts.get(event.uuid)
            owned_item = condition.resulting_item if condition is not None else None
            if owned_item is not None:
                for identity, actor in tuple(private_actors.items()):
                    if not any(item.item_uuid == owned_item.item_uuid for item in actor.items):
                        continue
                    actor = replace(actor, items=tuple(owned_item if item.item_uuid == owned_item.item_uuid else item
                                                       for item in actor.items))
                    private_actors[identity] = actor
                    contact = private_world.senses.entities.get(identity) if private_world.senses is not None else None
                    if identity in known and (observer.controls(identity) or contact is not None and contact.visual):
                        observations.append(_gear_observation(indexes[event.uuid], actor, observer, records))
            positions, object_positions = world_event_footprints(private_world.recorded_world, event, condition)
            changed_objects = world_event_objects(private_world.recorded_world, event, condition)
            changed_objects.update(world_objects_at(private_world.recorded_world, object_positions))
            # Sensory tile after-values belong to that observer's current grant.
            # A full offline capture may also contain foreign sensory payloads;
            # those must behave exactly like the audience-pruned live capture.
            world_changed = (False if isinstance(event, SensoryUpdateEvent)
                else apply_world_fact(private_world, event, condition))
            if isinstance(event, SensoryUpdateEvent) and observer.observes(event.observer_uuid):
                for source_uuid in dict.fromkeys(row.source_event_uuid for row in event.observed_changes):
                    source = by_version.get(source_uuid)
                    if source is not None and not source.canceled:
                        source_positions, source_object_positions = world_event_footprints(private_world.recorded_world, source)
                        positions.update(source_positions)
                        object_positions.update(source_object_positions)
                        changed_objects.update(world_event_objects(private_world.recorded_world, source))
                        changed_objects.update(world_objects_at(private_world.recorded_world, source_object_positions))
                        apply_world_fact(private_world, source)
                added = mask_positions(event.visible_cells_added)
                positions.update(added)
                object_positions.update(added)
                object_positions.update(mask_positions(event.visible_cells_removed))
                changed_objects.update(event.object_contacts_changed)
                changed_objects.update(event.object_contacts_removed)
                for identity in set(event.spatial_effects_changed) | event.spatial_effects_removed:
                    changed_objects.update(private_world.recorded_world.constructions_by_provider.get(identity, ()))
                fold_senses(remembered, event, cursor=indexes[event.uuid], audience_composition=audience_composition)
                private_world.senses = remembered.senses
                world_changed = True
            if world_changed:
                update = _world_update(private_world, remembered, indexes[event.uuid], positions, object_positions,
                    changed_objects, world_index)
                if update is not None:
                    updates.append(update)
        if (isinstance(event, ActionEvent) and event.source_item_uuid is not None
                and event.source_item_uuid in private_world.objects
                and _object_observed(private_world, event.source_item_uuid)):
            observed_objects.add(event.source_item_uuid)
        if (isinstance(event, (AttackEvent, SpellEvent)) and event.target_kind == "object"
                and event.target_entity_uuid is not None
                and event.target_entity_uuid in private_world.objects
                and _object_observed(private_world, event.target_entity_uuid)):
            observed_objects.add(event.target_entity_uuid)
        declaration_senses = delivery_declarations.get(event.lineage_uuid)
        if (isinstance(event, SpatialChangeEvent)
                and event.change_type is SpatialChangeType.ENTITY_LEFT
                and event.terminal_release is not None
                and event.terminal_release.cause is SummonDepartureCause.DEFEATED):
            # Death removes living contacts before retiring a summon. Retain
            # only the exact causing death's entry sight, never root visibility.
            cause_lineage = (version_lineages.get(event.terminal_release.parent_event_uuid)
                if event.terminal_release.parent_event_uuid is not None else None)
            cause = by_lineage.get(cause_lineage) if cause_lineage is not None else None
            if isinstance(cause, DeathEvent) and not cause.canceled and cause.entity_uuid == event.entity_uuid:
                declaration_senses = delivery_declarations.get(cause.lineage_uuid)
        fact = ((_sensory_fact(event, keys, table) if observer.observes(event.observer_uuid) else None)
            if isinstance(event, SensoryUpdateEvent) else _project_fact(event, observer, private_actors,
                facts.get(event.uuid), events, admissions, known, observed_objects, private_world.senses, keys,
                records, declaration_senses))
        condition_target = event.target_entity_uuid
        if (fact is None and event.event_type is EventType.CONDITION_REMOVAL
                and observer.controls(event.source_entity_uuid) and condition_target is not None
                and condition_target in known):
            # The source receives the end of its own already-known membership.
            # That does not disclose the absent recipient's current stats or place:
            # `_emit_bodies` sends the member value the seat holds.
            removed = facts.get(event.uuid)
            if removed is not None and removed.condition_uuid in held_conditions(condition_target):
                fact = ConditionChangeFact(target_entity_uuid=condition_target, event_type=event.event_type,
                    condition=removed)
                known_removals.add(indexes[event.uuid])
        if isinstance(fact, ConditionChangeFact) and not event.canceled:
            change_membership(held_conditions(fact.target_entity_uuid), fact)
        if isinstance(fact, SpatialFact) and not event.canceled:
            if commit_current(remembered, fact, source_cursor=indexes[event.uuid], occurrences=occurrences):
                if fact.terminal_departure and fact.entity_uuid is not None and fact.entity_uuid in known:
                    depart_contact(audience_composition, fact.entity_uuid)
            else:
                superseded.add(indexes[event.uuid])
        if isinstance(fact, FactionFact):
            parent = by_lineage.get(event.parent_lineage) if event.parent_lineage is not None else None
            removed = (facts.get(parent.uuid) if parent is not None
                and parent.event_type is EventType.CONDITION_REMOVAL
                and parent.phase is EventPhase.COMPLETION and not parent.canceled
                and parent.target_entity_uuid == fact.entity_uuid else None)
            actor = private_actors.get(fact.entity_uuid)
            origin = actor.summon_origin if actor is not None else None
            contact = private_world.senses.entities.get(fact.entity_uuid) if private_world.senses is not None else None
            if (event.phase is EventPhase.COMPLETION and not event.canceled
                    and removed is not None and actor is not None and origin is not None
                    and origin.control_condition_uuid is not None
                    and removed.condition_uuid == origin.control_condition_uuid
                    and any(row.condition_uuid == origin.existence_condition_uuid for row in actor.conditions)
                    and contact is not None and contact.visual):
                fact = replace(fact, control_lost=True)
        if (isinstance(event, TakeDamageEvent) and not event.canceled
                and event.final_damage is not None and event.resulting_hp is not None):
            identity = event.target_entity_uuid
            if identity is not None and (
                    identity in private_world.objects
                    and private_world.objects[identity].item.integrity is ItemIntegrity.INTACT
                    and _object_observed(private_world, identity)
                    or identity in destroyed_contacts):
                components = event.resolution.components if event.resolution is not None else ()
                fact = ObjectDamageFact(object_uuid=identity, applied_damage=event.final_damage,
                    resulting_hp=event.resulting_hp,
                    damage_type=components[0].damage_type if len(components) == 1 else None)
        if (isinstance(event, ItemDestructionEvent) and not event.canceled
                and (event.remains_disposition is RemainsDisposition.DISINTEGRATED
                     or event.resulting_state is not None and event.resulting_state.integrity is ItemIntegrity.DESTROYED)):
            destroyed = destroyed_contacts.get(event.item_uuid)
            if destroyed is not None:
                fact = ObjectDestroyedFact(object_uuid=destroyed.item.item_uuid,
                    placement=destroyed.placement, item_id=destroyed.item.item_id,
                    remnant_state=_observed_remnant(event.resulting_state.remnant_state,
                        remembered.objects, observed_objects) if event.resulting_state is not None else None,
                    destruction_outcome=event.resulting_state.destruction_outcome if event.resulting_state is not None else None,
                    remains_disposition=event.remains_disposition, previous_item=destroyed.item,
                    affected_volume=event.affected_volume,
                    resulting_placement=event.resulting_placement)
        if (isinstance(event, ItemLocationStateEvent) and event.location is ItemLocation.DESTROYED
                and event.item_state.item_uuid not in explicit_destructions):
            destroyed = destroyed_contacts.get(event.item_state.item_uuid)
            if destroyed is not None:
                replacement = event.replacement_item_uuid
                if (replacement is None or replacement not in private_world.objects
                        or not _object_observed(private_world, replacement)):
                    replacement = None
                fact = ObjectDestroyedFact(object_uuid=destroyed.item.item_uuid,
                    replacement_uuid=replacement, placement=destroyed.placement, item_id=destroyed.item.item_id,
                    remnant_state=event.item_state.remnant_state)
        # Only foreign action/handler attribution can consult held-content
        # knowledge. Capture it at this event boundary when there is a consumer.
        needs_held_content = (
            fact is not None and isinstance(event, ActionEvent)
            and not observer.controls(event.source_entity_uuid)
        ) or any(not observer.controls(row.source_entity_uuid)
                 for row in event.effective_handler_presentations)
        content_at_event[event.uuid] = (_held_content_at_event(event, observer,
            private_actors, known, private_world.senses)
            if needs_held_content else frozenset())
        nodes.append(PlayerNode(occurrence=indexes[event.uuid], lineage=keys.lineages[event.lineage_uuid],
            parent_event=_version_key(keys, event.parent_event), parent_lineage=_lineage_key(keys, event.parent_lineage),
            children_lineages=tuple(key for identity in event.children_lineages
                if (key := _lineage_key(keys, identity)) is not None), phase=event.phase,
            canceled=event.canceled, fact=fact, combat_log=_action_log(logs.get(event.uuid), fact, observer),
            turn_execution_id=event.turn_execution_id,
            cancellation=ActionCancellation(phase=event.canceled_from_phase,
                action_economy_spent=event.action_economy_spent, outcome_code=event.outcome_code)
                if event.canceled and isinstance(event, ActionEvent) and fact is not None else None))
    disclosed.update(node.lineage for node in nodes if node.fact is not None)
    disclosed_versions = {row.source_index for row in versions if keys.lineages[row.lineage_uuid] in disclosed}
    for index, node in enumerate(nodes):
        if isinstance(node.fact, SensoryFact):
            if node.fact.cause_occurrence is not None and node.fact.cause_occurrence not in disclosed_versions:
                nodes[index] = replace(node, fact=replace(node.fact, cause_occurrence=None))
        elif isinstance(node.fact, SpellFact) and node.fact.application is not None:
            if node.fact.application.lineage not in disclosed:
                nodes[index] = replace(node, fact=replace(node.fact, application=None))
        elif isinstance(node.fact, ConditionChangeFact):
            nodes[index] = replace(node, fact=replace(node.fact,
                condition=_disclosed_condition(node.fact.condition, disclosure)))
        elif isinstance(node.fact, EquipmentFact):
            nodes[index] = replace(node, fact=replace(node.fact, items=_disclosed_items(node.fact.items, disclosure)))
        if isinstance(node.fact, AreaReachFact):
            nodes[index] = replace(node, fact=replace(node.fact,
                previous_reach_lineage=(node.fact.previous_reach_lineage
                    if node.fact.previous_reach_lineage in disclosed else None),
                prerequisite_destruction_lineages=tuple(key
                    for key in node.fact.prerequisite_destruction_lineages if key in disclosed)))
    # Each node's disclosed resolution, by the node's native occurrence.
    resolutions: dict[int, tuple[int, UUID | None]] = {}
    for index, (node, event) in enumerate(zip(nodes, events, strict=True)):
        attributions = _content_attributions(event, node.fact, observer, disclosed, keys, content_at_event[event.uuid])
        if attributions:
            nodes[index] = replace(node, content_attributions=attributions)
        resolution = _resolution(keys, event.resolution_ref)
        if resolution is not None and resolution[0] in disclosed:
            resolutions[node.occurrence] = resolution
    for index, row in enumerate(observations):
        changes, items = _disclosed_changes(row.changes, disclosure), _disclosed_items(row.items, disclosure)
        if changes is not row.changes or items != row.items:
            observations[index] = replace(row, changes=changes, items=items)
    for index, row in enumerate(updates):
        objects = tuple(_disclosed_object(obj, disclosure) for obj in row.objects)
        if objects != row.objects:
            updates[index] = replace(row, objects=objects)
    for identity in {obj.item.item_uuid for update in updates for obj in update.objects}:
        if identity in remembered.objects:
            remembered.objects[identity] = _disclosed_object(remembered.objects[identity], disclosure)
    return (tuple(nodes), tuple(observations), tuple(updates), frozenset(superseded), frozenset(known_removals),
            resolutions)


def _disclosed_object(obj: PlayerObject, disclosed: LineageDisclosure) -> PlayerObject:
    """The object with undisclosed casting lineages cleared; an object without concentration slots is itself."""
    if not obj.item.concentration_slots and not any(item.concentration_slots for item in obj.contained_items or ()):
        return obj
    return replace(obj, item=replace(obj.item,
        concentration_slots=_disclosed_slots(obj.item.concentration_slots, disclosed)),
        contained_items=tuple(replace(item,
            concentration_slots=_disclosed_slots(item.concentration_slots, disclosed))
            for item in obj.contained_items) if obj.contained_items is not None else None)


def _public_condition(condition: ConditionFact, cursors: dict[int, int], versions: dict[UUID, int], *, owned: bool) -> ConditionFact:
    state = condition.state
    return replace(condition, event_uuid=condition.event_uuid if condition.event_uuid in versions else None,
        resulting_item=condition.resulting_item.model_copy(update={"item_effects":
            _public_item_effects(condition.resulting_item.item_effects, cursors, owned=owned)})
            if condition.resulting_item is not None else None,
        state=state.model_copy(update={"applied_source_event_cursor": _public_cursor(cursors, state.applied_source_event_cursor),
            "duration": state.duration if owned else None})
            if state is not None else None)


def _public_cursor(cursors: dict[int, int], source: int | None) -> int | None:
    # Owners stamp the completed application boundary, one past its event index.
    index = cursors.get(source - 1) if source is not None else None
    return index + 1 if index is not None else None


def _public_item_effects(effects: tuple[ItemEffectPresentationState, ...], cursors: dict[int, int], *, owned: bool = False
                         ) -> tuple[ItemEffectPresentationState, ...]:
    return tuple(effect.model_copy(update={"applied_source_event_cursor": _public_cursor(cursors, effect.applied_source_event_cursor),
        "duration": effect.duration if owned else None})
                 for effect in effects)


def _public_changes(changes: ActorChanges, cursors: dict[int, int], versions: dict[UUID, int], *,
                    owned: bool) -> ActorChanges:
    if "conditions" not in changes:
        return changes
    return {**changes, "conditions": tuple(_public_condition(row, cursors, versions, owned=owned)
        for row in changes["conditions"])}


def _public_items(patches: tuple[ItemPatch, ...], cursors: dict[int, int], *, owned: bool) -> tuple[ItemPatch, ...]:
    """The records with the seat's cursors on their item effects; a record without effects is itself."""
    return tuple(replace(row, look=replace(row.look, item_effects=_public_item_effects(
        row.look.item_effects, cursors, owned=owned))) if row.look is not None and row.look.item_effects else row
        for row in patches)


def _public_object(obj: PlayerObject, cursors: dict[int, int]) -> PlayerObject:
    """The object with the seat's cursors on its item effects; an object without effects is itself."""
    if not obj.item.item_effects and not any(item.item_effects for item in obj.contained_items or ()):
        return obj
    return replace(obj, item=replace(obj.item, item_effects=_public_item_effects(obj.item.item_effects, cursors)),
        contained_items=tuple(replace(item, item_effects=_public_item_effects(item.item_effects, cursors))
            for item in obj.contained_items) if obj.contained_items is not None else None)


def _sightings(table: SensoryTable, fact: SensoryFact) -> Iterator[tuple[int, UUID, SpatialEffectSighting]]:
    """A fact's sighting rows: index, effect and sighting."""
    return ((index, table.sighting_uuids[index], table.sightings[index]) for index in fact.spatial_effect_sightings)


def _map_sightings(table: SensoryTable, nodes: tuple[PlayerNode, ...],
                   value_of: Callable[[UUID, SpatialEffectSighting], SpatialEffectSighting]) -> None:
    """Replace each sighting row the nodes' sensory facts name with `value_of` it (a row has one naming fact)."""
    for node in nodes:
        if isinstance(node.fact, SensoryFact):
            for index in node.fact.spatial_effect_sightings:
                table.sightings[index] = value_of(table.sighting_uuids[index], table.sightings[index])


def _observe_spatial_revisions(state: "ProjectionState", nodes: tuple[PlayerNode, ...], table: SensoryTable) -> None:
    """Correlate member slices privately; count only changes in admitted evidence."""
    batches: dict[tuple[UUID, int | None], dict[UUID, SpatialEffectSighting]] = {}
    for node in nodes:
        if isinstance(node.fact, SensoryFact):
            for _, identity, effect in _sightings(table, node.fact):
                batches.setdefault((identity, effect.owner_revision), {})[table.facts[node.fact.observer].observer_uuid] = effect.model_copy(
                    update={"owner_revision": None})
    for (identity, native_revision), observations in batches.items():
        key = identity, native_revision
        changed = any(state.spatial_values.get((observer, identity)) != value
                      for observer, value in observations.items())
        if key not in state.spatial_versions:
            revision = state.spatial_revisions.get(identity, -1) + changed
            state.spatial_revisions[identity] = revision
            state.spatial_versions[key] = revision
        state.spatial_values.update(((observer, identity), value) for observer, value in observations.items())


def _public_occurrences(state: "ProjectionState", nodes: tuple[PlayerNode, ...], versions: tuple[ObjectiveRow, ...],
                        observations: tuple[PlayerObservation, ...], updates: tuple[WorldUpdate, ...],
                        known_removals: frozenset[int], table: SensoryTable,
                        resolutions: Mapping[int, tuple[int, UUID | None]]
                        ) -> tuple[tuple[PlayerNode, ...], VersionRows, tuple[PlayerObservation, ...], tuple[WorldUpdate, ...],
                                   tuple[PlayerResolution, ...]]:
    """Admit occurrence identities once and remove undisclosed causal links.

    The walk's native keys become the seat's: a version its occurrence index
    (assigned once, in native order), a lineage the occurrence index of its
    first admitted version. A sighting's seat value is a row of `table`. A
    node's resolution (`resolutions`, by native occurrence) becomes an index
    into the group's resolutions, each distinct one once.
    """
    _map_sightings(table, nodes, lambda identity, effect: effect.model_copy(
        update={"duration": effect.duration if identity in state.owned_spatial_effects else None}))
    touched_spatial = {(table.facts[node.fact.observer].observer_uuid, identity) for node in nodes
        if isinstance(node.fact, SensoryFact)
        for identity in (*(identity for _, identity, _ in _sightings(table, node.fact)),
                         *(table.removed_uuids[index] for index in node.fact.spatial_effects_removed))}
    previous_spatial = {key: state.spatial_values[key] for key in touched_spatial if key in state.spatial_values}
    previous_revisions = {identity: state.spatial_revisions[identity] for _, identity in touched_spatial
        if identity in state.spatial_revisions}
    _observe_spatial_revisions(state, nodes, table)
    # The content the seat holds at each node, as `_emit_bodies` will fold it.
    content_held = dict(state.remembered.spatial_content)
    filtered = []
    for node in nodes:
        fact = node.fact
        if isinstance(fact, SensoryFact):
            observer = table.facts[fact.observer].observer_uuid
            changed = []
            for index, identity, effect in _sightings(table, fact):
                key = observer, identity
                value = effect.model_copy(update={"owner_revision": None})
                content = fact.spatial_effect_content[identity]
                if (previous_spatial.get(key) != value or previous_revisions.get(identity)
                        != state.spatial_versions[(identity, effect.owner_revision)]
                        or content_held.get(identity, content) != content):
                    changed.append(index)
                    if not node.canceled:
                        content_held[identity] = content
                previous_spatial[key] = value
            for identity in (table.removed_uuids[index] for index in fact.spatial_effects_removed):
                previous_spatial.pop((observer, identity), None)
                state.spatial_values.pop((observer, identity), None)
            if tuple(changed) != fact.spatial_effect_sightings:
                fact = replace(fact, spatial_effect_sightings=tuple(changed))
            cells = table.facts[fact.observer]
            if not (fact.initial or fact.observer_position_changed or not no_cells(cells.effective_light_levels_changed.cells)
                    or not no_cells(cells.visible_cells_added) or not no_cells(cells.visible_cells_removed)
                    or not no_cells(cells.seen_cells_added)
                    or fact.entity_contacts_changed or fact.entity_contacts_removed
                    or fact.object_contacts_changed or fact.object_contacts_removed
                    or fact.sense_modes_changed or fact.passive_perception_changed or fact.visual_access_changed
                    or not no_cells(cells.hazardous_cells_changed.cells) or fact.spatial_effect_sightings
                    or fact.spatial_effects_removed or fact.light_sources_changed or fact.light_sources_removed):
                fact = None
            if fact is not node.fact:
                node = replace(node, fact=fact)
        filtered.append(node)
    nodes = tuple(filtered)
    observed_ids = {row.occurrence for row in (*observations, *updates)}
    observed_ids.update(node.fact.creation.birth_occurrence for node in nodes
        if isinstance(node.fact, SpatialFact) and node.fact.creation is not None)
    admitted_nodes = tuple(node for node in nodes if node.fact is not None or node.content_attributions
        or node.occurrence in observed_ids or (node.combat_log is not None
            and not (node.combat_log.data.kind == "empty" and not node.combat_log.source_uuid
                and node.combat_log.entry_type is CombatLogEntryType.ACTION
                and node.combat_log.success is None)))
    groups = {node.lineage for node in admitted_nodes}
    state.disclosed_lineages.update(groups)
    occurrences, lineages = [], []
    for row in versions:
        lineage = state.lineage_keys[row.lineage_uuid]
        if lineage not in groups and row.source_index not in observed_ids:
            continue
        if row.event_uuid not in state.public_versions:
            state.public_versions[row.event_uuid] = state.next_occurrence
            state.public_cursors[row.source_index] = state.next_occurrence
            state.next_occurrence += 1
        state.public_lineages.setdefault(lineage, state.public_versions[row.event_uuid])
        occurrences.append(state.public_versions[row.event_uuid])
        lineages.append(state.public_lineages[lineage])

    def lineage(key: int | None) -> int | None:
        """A disclosed lineage's public index; an undisclosed one is no reference."""
        return state.public_lineages.get(key) if key is not None and key in state.disclosed_lineages else None

    def version(cursor: int | None) -> int | None:
        return state.public_cursors.get(cursor) if cursor is not None else None
    for node in admitted_nodes:
        if isinstance(node.fact, TurnFact) and node.fact.entity_uuid is not None and node.turn_execution_id is not None:
            state.disclosed_turns.add(node.turn_execution_id)
    result = []
    resolution_rows: dict[PlayerResolution, int] = {}

    def resolution(occurrence: int) -> int | None:
        """The node's disclosed resolution as a row of the group's resolutions."""
        native = resolutions.get(occurrence)
        public = lineage(native[0]) if native is not None else None
        if native is None or public is None:
            return None
        return resolution_rows.setdefault(PlayerResolution(lineage=public, application_id=native[1]), len(resolution_rows))
    # A sighting's revision becomes the seat's count of its admitted changes.
    # Once per row (each row has one naming fact): the mapped revision is the seat's, not a native one.
    _map_sightings(table, admitted_nodes, lambda identity, effect: effect.model_copy(
        update={"owner_revision": state.spatial_versions[(identity, effect.owner_revision)]}))
    stages: dict[int | None, list[int]] = {}
    for node in admitted_nodes:
        if isinstance(node.fact, AreaReachFact):
            stages.setdefault(node.parent_lineage, []).append(node.fact.stage_index)
    for node in admitted_nodes:
        fact = node.fact
        if isinstance(fact, AreaReachFact):
            fact = replace(fact, stage_index=sorted(set(stages[node.parent_lineage])).index(fact.stage_index),
                previous_reach_lineage=lineage(fact.previous_reach_lineage),
                prerequisite_destruction_lineages=tuple(public for key in fact.prerequisite_destruction_lineages
                    if (public := lineage(key)) is not None))
        elif isinstance(fact, SensoryFact):
            fact = replace(fact, cause_occurrence=version(fact.cause_occurrence))
        elif isinstance(fact, SpellFact) and fact.application is not None:
            owner = lineage(fact.application.lineage)
            fact = replace(fact, application=replace(fact.application, lineage=owner) if owner is not None else None)
        elif isinstance(fact, SpatialFact):
            fact = replace(fact, commit_occurrence=version(fact.commit_occurrence),
                creation=replace(fact.creation, birth_occurrence=state.public_cursors[fact.creation.birth_occurrence])
                    if fact.creation is not None else None)
        elif isinstance(fact, ActionFact) and fact.reaction is not None:
            fact = replace(fact, reaction=replace(fact.reaction, triggered_lineage=lineage(fact.reaction.triggered_lineage)))
        elif isinstance(fact, ConditionChangeFact) and node.occurrence not in known_removals:
            fact = replace(fact, condition=_public_condition(fact.condition, state.public_cursors, state.public_versions,
                owned=state.audience.controls(fact.target_entity_uuid)))
        elif isinstance(fact, AttackFact):
            fact = replace(fact, item_effects=_public_item_effects(fact.item_effects, state.public_cursors,
                owned=state.audience.controls(fact.source_entity_uuid)))
        elif isinstance(fact, EquipmentFact):
            fact = replace(fact, items=_public_items(fact.items, state.public_cursors,
                owned=state.audience.controls(fact.source_entity_uuid)))
        elif isinstance(fact, ObjectDestroyedFact) and fact.previous_item is not None:
            fact = replace(fact, previous_item=replace(fact.previous_item,
                item_effects=_public_item_effects(fact.previous_item.item_effects, state.public_cursors)))
        attributions = tuple(replace(row,
            triggering_occurrence=version(row.triggering_occurrence),
            triggering_lineage=lineage(row.triggering_lineage),
            emitted_lineages=tuple(public for key in row.emitted_lineages if (public := lineage(key)) is not None),
            dispatch_index=index if row.dispatch_index is not None else None)
            for index, row in enumerate(node.content_attributions))
        result.append(replace(node, fact=fact, occurrence=state.public_cursors[node.occurrence],
            lineage=state.public_lineages[node.lineage], parent_event=version(node.parent_event),
            parent_lineage=lineage(node.parent_lineage),
            children_lineages=tuple(state.public_lineages[key] for key in node.children_lineages if key in groups),
            turn_execution_id=node.turn_execution_id if node.turn_execution_id in state.disclosed_turns else None,
            content_attributions=attributions, resolution=resolution(node.occurrence)))
    observations = tuple(replace(row, occurrence=state.public_cursors[row.occurrence],
        changes=_public_changes(row.changes, state.public_cursors, state.public_versions,
        owned=state.audience.controls(row.actor_uuid)), items=_public_items(row.items,
        state.public_cursors, owned=state.audience.controls(row.actor_uuid))) for row in observations)
    updates = tuple(replace(row, occurrence=state.public_cursors[row.occurrence],
        objects=tuple(_public_object(obj, state.public_cursors) for obj in row.objects)) for row in updates)
    return (tuple(result), VersionRows(occurrences=tuple(occurrences), lineages=tuple(lineages)), observations, updates,
            tuple(resolution_rows))


@dataclass(slots=True)
class ProjectionState:
    """Private recorded aggregates and last-observed memory for one observer.

    `remembered` is the audience's one fold. Its actors, world, connectors,
    last published HUD and admitted content equal its client's: actors change
    only through the client's reducer on the emitted patches and facts
    (`_emit_bodies`). Its senses are the projector's own (no contacts from
    admitted observations).
    """

    world: PresentationTarget
    actors: dict[UUID, ActorState]
    remembered: PlayerState
    # The seat's control and observers. `remembered` holds the same value for the client functions it still runs.
    audience: PlayerAudience
    # The static content the seat was sent, updated from each emitted group.
    static_sent: StaticSent = field(default_factory=StaticSent)
    # Disclosed lineages, by their native key (`NativeKeys.lineages`).
    disclosed_lineages: set[int] = field(default_factory=set)
    public_versions: dict[UUID, int] = field(default_factory=dict)
    # The walk's native keys of every captured version and lineage, and each disclosed lineage's public index.
    version_cursors: dict[UUID, int] = field(default_factory=dict)
    lineage_keys: dict[UUID, int] = field(default_factory=dict)
    public_lineages: dict[int, int] = field(default_factory=dict)
    public_cursors: dict[int, int] = field(default_factory=dict)
    disclosed_turns: set[UUID] = field(default_factory=set)
    owned_spatial_effects: set[UUID] = field(default_factory=set)
    spatial_values: dict[tuple[UUID, UUID], SpatialEffectSighting] = field(default_factory=dict)
    spatial_versions: dict[tuple[UUID, int | None], int] = field(default_factory=dict)
    spatial_revisions: dict[UUID, int] = field(default_factory=dict)
    next_occurrence: int = 0
    next_log_append: int = 0
    world_index: WorldProjectionIndex = field(default_factory=WorldProjectionIndex)
    audience_composition: AudienceComposition = field(default_factory=AudienceComposition)


def _item_patches(remembered: PlayerState, records: tuple[ItemPatch, ...]) -> tuple[ItemPatch, ...]:
    """Each disclosed record as the patch against the seat's record of that item; unchanged items drop out."""
    return tuple(patch for row in records if (patch := item_patch(remembered.items.get(row.item_uuid), row)).look
        is not None or patch.profile is not None or patch.state is not None)


def _light_row(source: PerceivedLightSource, uuid: Callable[[UUID], int]) -> LightRow:
    """A perceived light source as a row of its group, its identities given by `uuid`."""
    return LightRow(source=uuid(source.source_uuid), revision=source.revision, position=source.position,
        base_height_steps=source.base_height_steps, very_bright_radius_feet=source.very_bright_radius_feet,
        bright_radius_feet=source.bright_radius_feet, dim_radius_feet=source.dim_radius_feet,
        appearance=source.appearance, actor_anchored=source.actor_anchored,
        anchor_entity=uuid(source.anchor_entity_uuid) if source.anchor_entity_uuid is not None else None,
        anchor_item=uuid(source.anchor_item_uuid) if source.anchor_item_uuid is not None else None,
        affected_tiles=values_from_items({_tile(key): level.value for key, level in source.affected_tiles.items()}))


def _tile(key: str) -> tuple[int, int]:
    """A light footprint's tile key ("x,y") as a cell."""
    x, y = key.split(",")
    return int(x), int(y)


def _shared_rows(nodes: tuple[PlayerNode, ...], table: SensoryTable
                 ) -> tuple[tuple[PlayerNode, ...], SensoryRows, tuple[PerceivedContact, ...]]:
    """The values the group's sensory facts name, each distinct value once in naming order, and the facts naming them so.

    A value equal (`is`, else `==`) to an earlier row of its identity is that
    row. The facts' cell lists become subsets of the group's cell row tables
    (`shared_cells`, `shared_values`). Also returns the contact rows' values.
    """
    uuids: dict[UUID, int] = {}
    contact_keys: list[int] = []
    contacts: list[PerceivedContact] = []
    sighting_keys: list[int] = []
    sightings: list[SpatialEffectSighting] = []
    removal_keys: list[int] = []
    revisions: list[int] = []
    lights: list[PerceivedLightSource] = []
    # Each identity's rows per column: by uuid index, lights by source uuid.
    contact_rows: dict[int, list[int]] = {}
    sighting_rows: dict[int, list[int]] = {}
    removal_rows: dict[int, list[int]] = {}
    light_rows: dict[UUID, list[int]] = {}

    def uuid(identity: UUID) -> int:
        return uuids.setdefault(identity, len(uuids))

    def interned(numbers: list[int], column: list[Row], value: Row) -> int:
        for number in numbers:
            if column[number] is value or column[number] == value:
                return number
        numbers.append(len(column))
        column.append(value)
        return numbers[-1]

    def keyed(rows: dict[int, list[int]], keys: list[int], column: list[Row], identity: UUID, value: Row) -> int:
        key = uuid(identity)
        count = len(column)
        number = interned(rows.setdefault(key, []), column, value)
        if number == count:
            keys.append(key)
        return number

    def contact(index: int) -> int:
        return keyed(contact_rows, contact_keys, contacts, table.contact_uuids[index], table.contacts[index])
    # The sensory facts, by node index, with their table rows.
    sensory = [(at, node.fact, table.facts[node.fact.observer]) for at, node in enumerate(nodes)
               if isinstance(node.fact, SensoryFact)]
    cells, cell_bits = shared_cells([mask for _, _, row in sensory
        for mask in (row.visible_cells_added, row.visible_cells_removed, row.seen_cells_added)])
    # A cell coming into view reads zero without a value (`zeros_left_out`).
    light_levels, light_bits = shared_values([zeros_left_out(row.effective_light_levels_changed, row.visible_cells_added)
        for _, _, row in sensory])
    hazards, hazard_bits = shared_values([zeros_left_out(row.hazardous_cells_changed, row.visible_cells_added)
        for _, _, row in sensory])
    result = list(nodes)
    for number, (at, fact, row) in enumerate(sensory):
        result[at] = replace(nodes[at], fact=replace(fact, observer=uuid(row.observer_uuid),
                visible_cells_added=cell_bits[3 * number], visible_cells_removed=cell_bits[3 * number + 1],
                seen_cells_added=cell_bits[3 * number + 2], effective_light_levels_changed=light_bits[number],
                hazardous_cells_changed=hazard_bits[number],
                entity_contacts_changed=tuple(contact(index) for index in fact.entity_contacts_changed),
                entity_contacts_removed=tuple(uuid(table.removed_uuids[index]) for index in fact.entity_contacts_removed),
                object_contacts_changed=tuple(contact(index) for index in fact.object_contacts_changed),
                object_contacts_removed=tuple(uuid(table.removed_uuids[index]) for index in fact.object_contacts_removed),
                spatial_effect_sightings=tuple(keyed(sighting_rows, sighting_keys, sightings, table.sighting_uuids[index],
                    table.sightings[index]) for index in fact.spatial_effect_sightings),
                spatial_effects_removed=tuple(uuid(table.removed_uuids[index]) for index in fact.spatial_effects_removed),
                light_sources_changed=tuple(interned(light_rows.setdefault(table.light_sources[index].source_uuid, []),
                    lights, table.light_sources[index]) for index in fact.light_sources_changed),
                light_sources_removed=tuple(keyed(removal_rows, removal_keys, revisions, table.light_removal_uuids[index],
                    table.light_removal_revisions[index]) for index in fact.light_sources_removed)))
    light_table = tuple(_light_row(source, uuid) for source in lights)
    return tuple(result), SensoryRows(uuids=tuple(uuids), contact_uuid_index=tuple(contact_keys),
        contact_positions=tuple(row.position for row in contacts), contact_visual=flag_bits([row.visual for row in contacts]),
        contact_special_senses=tuple(row.special_senses for row in contacts)
            if any(row.special_senses for row in contacts) else (),
        sighting_uuid_index=tuple(sighting_keys), sightings=tuple(sightings),
        light_sources=light_table, light_removal_uuid_index=tuple(removal_keys),
        light_removal_revisions=tuple(revisions), cells=cells, light_levels=light_levels, hazards=hazards), tuple(contacts)


def _emit_bodies(remembered: PlayerState, nodes: tuple[PlayerNode, ...], observations: tuple[PlayerObservation, ...],
                 superseded: frozenset[int], known_removals: frozenset[int], rows: SensoryRows,
                 contacts: tuple[PerceivedContact, ...]) -> tuple[tuple[PlayerNode, ...], tuple[PlayerObservation, ...]]:
    """Fold the emitted lineage's bodies and items into the seat's, in its client's order.

    Each observed (public) body and each equipment fact becomes the patch
    against the body and item records the seat holds at that point; the
    seat's actors and items change only through the client's reducer on those
    patches and on the emitted facts. An observation that changes nothing and
    carries no contact is not sent. The removal of a known membership carries
    the member value the seat holds.
    """
    emitted: list[PlayerObservation] = []
    result: list[PlayerNode] = []
    for row in occurrence_order(nodes, observations):
        match row:
            case PlayerObservation():
                before = remembered.actors.get(row.actor_uuid)
                if before is not None and not before.present:
                    continue
                patch = replace(row, changes=actor_changes(before, observed_actor(before, row)),
                    items=_item_patches(remembered, row.items))
                if not patch.changes and not patch.items and patch.contact is None:
                    continue
                observe_body(remembered, patch)
                emitted.append(patch)
            case PlayerNode():
                fact = row.fact
                if isinstance(fact, EquipmentFact):
                    before = remembered.actors[fact.source_entity_uuid]
                    fact = replace(fact, changes=actor_changes(before, replace(before, **fact.changes)),
                        items=_item_patches(remembered, fact.items))
                    row = replace(row, fact=fact)
                elif isinstance(fact, SensoryFact):
                    # Content travels once per seat (again only if it changed).
                    fact = replace(fact, spatial_effect_content={identity: fact.spatial_effect_content[identity]
                        for identity in (rows.uuids[rows.sighting_uuid_index[index]] for index in fact.spatial_effect_sightings)
                        if remembered.spatial_content.get(identity) != fact.spatial_effect_content[identity]})
                    row = replace(row, fact=fact)
                elif isinstance(fact, ConditionChangeFact) and row.occurrence in known_removals:
                    member = next((member for member in remembered.actors[fact.target_entity_uuid].conditions
                        if member.condition_uuid == fact.condition.condition_uuid), None)
                    if member is None:
                        raise ValueError("A known removal names a membership its seat does not hold")
                    fact = replace(fact, condition=replace(member, event_uuid=fact.condition.event_uuid, resulting_stats=None,
                        resulting_max_hp=None, resulting_ac=None, resulting_tile=None, resulting_item=None))
                    row = replace(row, fact=fact)
                if not row.canceled and fact is not None and row.occurrence not in superseded:
                    apply_record_fact(remembered, fact, rows, contacts)
                result.append(row)
    return tuple(result), tuple(emitted)


def project_hud(audience: PlayerAudience, events: Iterable[Event],
                before: tuple[tuple[UUID, ...], frozenset[UUID]] | None,
                order_after: tuple[UUID, ...], perceived_after: frozenset[UUID]) -> PlayerHUDPatch | None:
    """The seat's HUD patch for one group of recorded events: an initialization (`before` None) or an operation.

    Sheets: per controlled actor, its sheet publications' groups and its own events' after-values
    (`sheet_fact`) folded in source order, the published actors first, in publication order. Initiative: `before` is the
    session fold's encounter order and the seat's composed perception at the group's start, `*_after`
    the same at its end; the end order's
    perceived part is sent at initialization, when the order change shows under the end perception, or
    when anything entered perception (the client hides what left it).
    """
    changes: dict[UUID, SheetChanges] = {}
    values: dict[UUID, dict[str, PlayerResourceValue]] = {}
    published: list[UUID] = []
    for event in events:
        fact = sheet_fact(event) if event.phase is EventPhase.COMPLETION and not event.canceled else None
        if fact is None or not audience.controls(fact.actor_uuid):
            continue
        if fact.publication and fact.actor_uuid not in published:
            published.append(fact.actor_uuid)
        held = changes.setdefault(fact.actor_uuid, {})
        if "resources" in fact.changes:
            # A whole resource tuple replaces any row values before it.
            values.pop(fact.actor_uuid, None)
        held.update(fact.changes)
        if fact.resource_values and "resources" in held:
            by_key = {row.key: row for row in fact.resource_values}
            held["resources"] = tuple(replace(row, current=value.current, maximum=value.maximum)
                if (value := by_key.get(row.key)) is not None else row for row in held["resources"])
        elif fact.resource_values:
            values.setdefault(fact.actor_uuid, {}).update((row.key, row) for row in fact.resource_values)
    order = (*published, *(identity for identity in changes if identity not in published))
    sheets = tuple(SheetPatch(actor_uuid=identity, changes=changes[identity],
        resource_values=tuple(values.get(identity, {}).values())) for identity in order)

    def perceived_part(initiative: tuple[UUID, ...]) -> tuple[UUID, ...]:
        return tuple(identity for identity in initiative if identity in perceived_after)
    initiative = perceived_part(order_after) if (before is None or not perceived_after <= before[1]
        or perceived_part(before[0]) != perceived_part(order_after)) else None
    return PlayerHUDPatch(initiative=initiative, sheets=sheets) if initiative is not None or sheets else None


def project_log_appends(state: ProjectionState, appends: tuple[CombatLogAppend, ...]) -> tuple[CombatLogAppend, ...]:
    """Map already-admitted native log appends into this audience's ordering."""
    def boundary(native_cursor: int) -> int:
        # Public occurrences increase in insertion order, including late
        # disclosures of older native events. The first qualifying occurrence
        # backwards is the conservative gate; current updates usually hit first.
        return next((local + 1 for native, local in reversed(state.public_cursors.items())
                     if native < native_cursor), 0)

    if any(row.generation != state.world.generation or row.observer_uuid != state.world.observer_uuid
           for row in appends):
        raise ValueError("Log appends belong to another audience or generation")
    public_logs = tuple(replace(row, encounter_log_index=state.next_log_append + index,
        operation_end_cursor=boundary(row.operation_end_cursor)) for index, row in enumerate(appends))
    state.next_log_append += len(public_logs)
    return public_logs


def known_connector_uuids(state: ProjectionState) -> frozenset[str]:
    """The connectors the seat sees now, both endpoints in its composed view: those its combat log may name.

    Every change of the view or of a connector is followed by a world update of the seat, which sends exactly
    these, so they are the connectors its client holds as visible.
    """
    view = state.audience_composition.view
    if view is None:
        return frozenset()
    return frozenset(str(row.connector_uuid) for row in state.world.recorded_world.connectors.values()
        if all(cell_in(view.visible, point) for point in row.endpoints))


def _public_set(state: ProjectionState, cursors: frozenset[int]) -> frozenset[int]:
    """The public occurrences of the walk's native versions that were admitted."""
    return frozenset(state.public_cursors[cursor] for cursor in cursors if cursor in state.public_cursors)


def begin_projection(initialization: IntervalEnvelope) -> tuple[ProjectionState, PlayerInitialization]:
    """Start a projection from recorded initialization; no native queries."""
    world_event = next((event for _, event in initialization.admitted if isinstance(event, WorldInitializedEvent)), None)
    if world_event is None:
        raise ValueError("player projection requires recorded world initialization")
    world = PlayerWorld(battlefield_id=world_event.battlefield_id, battlefield_name=world_event.battlefield_name,
        bounds=world_event.bounds, width=world_event.width, height=world_event.height)
    private_world = PresentationTarget(generation=initialization.generation, observer_uuid=initialization.observer_uuid)
    audience = resolve_audience(initialization.observer_uuid, initialization.audience)
    remembered = PlayerState(generation=initialization.generation, observer_uuid=initialization.observer_uuid,
        world=world, audience=audience)
    actors: dict[UUID, ActorState] = {}
    versions = initialization.objective_rows
    state = ProjectionState(private_world, actors, remembered, audience)
    _remember_versions(state.version_cursors, state.lineage_keys, versions)
    table = SensoryTable()
    nodes, observations, updates, superseded, known_removals, resolutions = _project_nodes(
        tuple(event for _, event in initialization.admitted), versions, initialization.admissions,
        initialization.conditions, private_world, actors, audience, state.static_sent.actor_births, remembered,
        state.disclosed_lineages, state.world_index,
        state.audience_composition, initialization.logs, NativeKeys(state.version_cursors, state.lineage_keys), table)
    state.owned_spatial_effects.update(event.spatial_effect_uuid for _, event in initialization.admitted
        if isinstance(event, SpatialEffectChangeEvent) and audience.controls(event.source_entity_uuid))
    nodes, rows, observations, updates, resolution_rows = _public_occurrences(state, nodes, versions, observations,
        updates, known_removals, table, resolutions)
    nodes, sensory_rows, contacts = _shared_rows(nodes, table)
    nodes, observations = _emit_bodies(remembered, nodes, observations, _public_set(state, superseded),
        _public_set(state, known_removals), sensory_rows, contacts)
    state.static_sent.actor_births.update(row.actor_uuid for row in observations)
    initial = PlayerInitialization(generation=initialization.generation, observer_uuid=initialization.observer_uuid,
        world=world, nodes=nodes, version_rows=rows, end_cursor=state.next_occurrence,
        observations=observations, world_updates=updates, audience=audience, sensory_rows=sensory_rows,
        resolutions=resolution_rows)
    return state, initial


def project_lineage(state: ProjectionState, lineage: CompletedLineage) -> PlayerLineage | None:
    """Advance the same private projection memory over one closed root."""
    if (state.world.generation != lineage.generation or state.world.observer_uuid != lineage.observer_uuid
            or state.audience != resolve_audience(lineage.observer_uuid, lineage.audience)):
        raise ValueError("recorded lineage belongs to another projection")
    start_cursor = state.next_occurrence
    state.owned_spatial_effects.update(event.spatial_effect_uuid for event in lineage.events
        if isinstance(event, SpatialEffectChangeEvent) and state.audience.controls(event.source_entity_uuid))
    versions = lineage.objective_rows
    _remember_versions(state.version_cursors, state.lineage_keys, versions)
    table = SensoryTable()
    nodes, observations, updates, superseded, known_removals, resolutions = _project_nodes(
        upgrade_recorded_resolutions(lineage.events), versions, lineage.admissions, lineage.conditions, state.world,
        state.actors, state.audience, state.static_sent.actor_births, state.remembered, state.disclosed_lineages,
        state.world_index, state.audience_composition,
        lineage.logs, NativeKeys(state.version_cursors, state.lineage_keys), table, lineage.observed_sources)
    # Settled initialization needs resulting state only. Presenting a damage
    # operation additionally requires recorded causal ownership, or an explicit
    # current-format unknown owner; old missing fields cannot establish either.
    native_events = {state.version_cursors[event.uuid]: event for event in lineage.events}
    for node in nodes:
        event = native_events[node.occurrence]
        if (isinstance(node.fact, DamageRequestFact) and node.occurrence not in resolutions
                and "resolution_ref" in event._recorded_omissions):
            legacy_damage_reference(event.uuid, event.lineage_uuid, event.parent_lineage, is_request=True)
    if not observations and not updates and not any(node.fact is not None or node.combat_log is not None
                                                   or node.content_attributions for node in nodes):
        return None
    nodes, rows, observations, updates, resolution_rows = _public_occurrences(state, nodes, versions, observations,
        updates, known_removals, table, resolutions)
    if not nodes and not observations and not updates:
        return None
    nodes, sensory_rows, contacts = _shared_rows(nodes, table)
    nodes, observations = _emit_bodies(state.remembered, nodes, observations, _public_set(state, superseded),
        _public_set(state, known_removals), sensory_rows, contacts)
    state.static_sent.actor_births.update(row.actor_uuid for row in observations)
    root_occurrence = state.public_cursors.get(state.version_cursors[lineage.root.uuid])
    root = next((index for index, node in enumerate(nodes) if node.occurrence == root_occurrence), None)
    return PlayerLineage(generation=lineage.generation, observer_uuid=lineage.observer_uuid,
        lineage=nodes[root].lineage if root is not None else rows.lineages[0],
        root=root, events=nodes, version_rows=rows, start_cursor=start_cursor,
        end_cursor=state.next_occurrence, observations=observations, world_updates=updates, audience=state.audience,
        sensory_rows=sensory_rows, resolutions=resolution_rows)
