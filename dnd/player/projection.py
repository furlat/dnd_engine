"""Project private recorded facts into the public player packet.

Perception is already resolved by native events. This module selects existing
authority and publishes each event's change to every seat from the session folds
and each seat's knowledge; it keeps no copy of a seat's values and never asks the
live engine what an observer can see.
"""

from collections.abc import Callable, Collection, Iterable, Mapping
from typing import TypeVar
from dataclasses import dataclass, field, replace
from math import floor
from uuid import UUID

from dnd.actions import AttackEvent, JumpEvent, MovementEvent, ShoveEvent, SpellEvent, TraverseConnectorEvent
from dnd.spells.abjuration import CounterspellReactionEvent
from dnd.blocks.base_item import ItemResourceChangeEvent, ItemHoldingsReleasedEvent, ItemLocationStateEvent
from dnd.blocks.equipment import EquipmentEvent
from dnd.core.cells import flag_bits, mask_from_positions, mask_union, shared_cells, shared_values, zeros_left_out
from dnd.types.cells import EMPTY_CELLS, CellMask, CellValues, cell_in, no_cells
from dnd.types.senses import (SensesSnapshot, PerceivedContact, PerceivedLightSource, PerceivedSpatialEffect,
    VolumeSurfaceSight)
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from dnd.types.spell_suppression import SpellSuppression
from dnd.core.base_actions import ActionEvent
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.presentation_geometry import ConePresentationGeometry, LinePresentationGeometry, CubePresentationGeometry
from dnd.core.condition_types import ConditionCategory
from dnd.core.effect_types import ResolutionRef
from dnd.core.content.runtime import HandlerDispatchOutcome
from dnd.core.events import (
    AreaReachEvent,
    DamageAppliedEvent, DeathEvent, DeathSaveEvent, EncounterEvent, EntityCreatedEvent, EntityFactionChangedEvent, ItemDestructionEvent,
    Event, EventPhase, EventType, ForcedMovementEvent, PortalTransferEvent, MechanismActivationEvent, HealEvent, LifeStateChangeEvent,
    RoundEvent, SensoryUpdateEvent, SpatialChangeEvent, SpatialChangeType, SpatialEffectChangeEvent, SpatialEffectInteractionEvent,
    MovementTrajectory, StepMovementEvent, TakeDamageEvent, TemporaryHitPointsChangedEvent, TurnEvent, WorldInitializedEvent, SavingThrowEvent,
)
from dnd.core.life_types import RemainsDisposition
from dnd.core.item_types import ItemConcentrationSlot, ItemEffectPresentationState, ItemIntegrity, ItemLocation
from dnd.types.event_facts import AppliedWorldFact
from dnd.types.class_features import FontConversion
from dnd.types.residues import BodyReleaseRegion, BodyReleaseResult
from dnd.types.summoning import SummonDepartureCause
from dnd.player.audience import (AudienceComposition, ComposedChange, PlayerAudience, apply_settlement, depart_contact,
    resolve_audience)

from dnd.player.actor_projection import fold_birth, fold_completed_actors
from dnd.player.bodies import (ActorChangeViews, View, body_digest, body_stampable, change_fact, change_rows,
    change_views, entering_body, shown_items)
from dnd.types.actor_facts import (ActorFactChange, ActorState, ChangeRow, ConditionFact, ConditionMember, ConditionRow,
    ItemEffectsRow, ItemStateRow)
from dnd.player.facts import (
    ActionCancellation, ActionFact, ActionReaction, ActorChangeFact, AreaReachFact, AttackFact, BodyRecord, ContentAttribution, DamageRequestFact, DamageResultFact,
    DeathSaveFact, ForcedMovementFact, PortalTransferFact, MechanismActivationFact, HealFact, ItemChargeFact, LifeFact,
    MovementFact, ObjectDamageFact, ObjectDestroyedFact, PlayerFact, PlayerInitialization, PlayerLineage,
    PlayerNode, PlayerObject, PlayerHUDPatch, CombatLogAppend,
    PlayerLogEntry, SheetChanges, SheetPatch, SpatialEffectContent, SpatialEffectSighting, SpatialEffectPatch,
    SightingChanges, LightChanges, LightPatch, VolumeSurfaceKey,
    PlayerWorld, PlayerResolution, LightRow, SensoryFact, SensoryRows, ShoveFact, SpatialFact, SpatialEffectStateFact, SpellFact, StepFact, TurnFact,
    VersionRows, WorldUpdate, ItemRecord, TemporaryHitPointsFact, SavingThrowFact, FactionFact, CreationWitness,
    Column, ContainedItem, ObjectState, VisualLoadout,
)
from dnd.player.capture import (CompletedLineage, IntervalEnvelope, ObjectiveRow, SharedLogEntries,
    recorded_actor_change, seat_log_entry)
from dnd.player.sheet_facts import sheet_fact
from dnd.types.actor_sheet import PlayerResourceValue
from dnd.player.event_record import upgrade_recorded_resolutions, upgrade_recorded_spatial_commits
from dnd.player.world_digests import TileDigests, forget_written
from dnd.player.world_stamps import SeatStamps, StampChanges, WorldStamps, merge_world_stamps, unchanged_since
from dnd.player.static_sent import StaticSent, merge_static_sent
from dnd.player.spatial_commits import commit_current
from dnd.player.world_publication import (SensedWorld, disclosed_world_object, object_observed, observed_remnant,
    seat_world_update)
from dnd.player.compatibility import legacy_damage_reference
from dnd.world_facts import WorldFacts, apply_world_fact


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


Row = TypeVar("Row")


def _sighting(effect: PerceivedSpatialEffect, owned: bool) -> SpatialEffectSighting:
    """An effect entering the seat's perception: its visible part (plan §3.2) without its static content, its
    duration only when the seat owns it; its cell lists as sets, its upper volume surfaces by key."""
    return SpatialEffectSighting.model_construct(duration=effect.duration if owned else None,
        positions=mask_from_positions(effect.positions), apparent_presence=effect.apparent_presence,
        trap_state=effect.trap_state, pressed=effect.pressed, direction=effect.direction,
        anchor_item_uuid=effect.anchor_item_uuid, anchor_entity_uuid=effect.anchor_entity_uuid,
        energy_type=effect.energy_type, presence_mode=effect.presence_mode,
        sustainer_item_uuid=effect.sustainer_item_uuid, concentration_slot_uuid=effect.concentration_slot_uuid,
        anchor_position=effect.anchor_position, anchor_elevation_steps=effect.anchor_elevation_steps,
        area_geometry=effect.area_geometry, construction_sections=effect.construction_sections,
        area_propagation=effect.area_propagation, deposit_source=effect.deposit_source,
        visible_volume_positions=mask_from_positions(effect.visible_volume_positions),
        upper_volume_surfaces=tuple(sorted(effect.upper_volume_surfaces, key=_surface_key)),
        suppressions=effect.suppressions)


def _surface_key(row: VolumeSurfaceSight) -> VolumeSurfaceKey:
    return row.position, row.lower_height_planes


def _sighting_changes(before: PerceivedSpatialEffect, after: PerceivedSpatialEffect, owned: bool) -> SightingChanges:
    """The disclosed fields of a perceived effect that differ after the settlement, with their after-values (cell
    sets and volume surfaces aside); a duration only when the seat owns the effect."""
    changes: SightingChanges = {}
    if owned and before.duration != after.duration:
        changes["duration"] = after.duration
    if before.apparent_presence != after.apparent_presence:
        changes["apparent_presence"] = after.apparent_presence
    if before.trap_state != after.trap_state:
        changes["trap_state"] = after.trap_state
    if before.pressed != after.pressed:
        changes["pressed"] = after.pressed
    if before.direction != after.direction:
        changes["direction"] = after.direction
    if before.anchor_item_uuid != after.anchor_item_uuid:
        changes["anchor_item_uuid"] = after.anchor_item_uuid
    if before.anchor_entity_uuid != after.anchor_entity_uuid:
        changes["anchor_entity_uuid"] = after.anchor_entity_uuid
    if before.energy_type != after.energy_type:
        changes["energy_type"] = after.energy_type
    if before.presence_mode != after.presence_mode:
        changes["presence_mode"] = after.presence_mode
    if before.sustainer_item_uuid != after.sustainer_item_uuid:
        changes["sustainer_item_uuid"] = after.sustainer_item_uuid
    if before.concentration_slot_uuid != after.concentration_slot_uuid:
        changes["concentration_slot_uuid"] = after.concentration_slot_uuid
    if before.anchor_position != after.anchor_position:
        changes["anchor_position"] = after.anchor_position
    if before.anchor_elevation_steps != after.anchor_elevation_steps:
        changes["anchor_elevation_steps"] = after.anchor_elevation_steps
    if before.area_geometry != after.area_geometry:
        changes["area_geometry"] = after.area_geometry
    if before.construction_sections != after.construction_sections:
        changes["construction_sections"] = after.construction_sections
    if before.area_propagation != after.area_propagation:
        changes["area_propagation"] = after.area_propagation
    if before.deposit_source != after.deposit_source:
        changes["deposit_source"] = after.deposit_source
    if before.suppressions != after.suppressions:
        changes["suppressions"] = after.suppressions
    return changes


def _sighting_patch(before: PerceivedSpatialEffect, after: PerceivedSpatialEffect, owned: bool,
                    members: int | None) -> SpatialEffectPatch | None:
    """The change of an effect perceived before and after the settlement, as the seat is shown it; None when
    nothing it is shown changed (a revision, or a duration it does not own)."""
    changes = _sighting_changes(before, after, owned)
    held, now = set(before.positions), set(after.positions)
    held_volume, volume = set(before.visible_volume_positions), set(after.visible_volume_positions)
    upper_before = {_surface_key(row): row for row in before.upper_volume_surfaces}
    upper_after = {_surface_key(row): row for row in after.upper_volume_surfaces}
    upper_added = tuple(upper_after[key] for key in sorted(upper_after) if upper_before.get(key) != upper_after[key])
    upper_removed = tuple(key for key in sorted(upper_before) if key not in upper_after)
    if not (changes or held != now or held_volume != volume or upper_added or upper_removed or members is not None):
        return None
    return SpatialEffectPatch(positions_added=mask_from_positions(now - held),
        positions_removed=mask_from_positions(held - now), volume_added=mask_from_positions(volume - held_volume),
        volume_removed=mask_from_positions(held_volume - volume), upper_added=upper_added,
        upper_removed=upper_removed, members=members, changes=changes)


def _uuid_row(uuids: dict[UUID, int], identity: UUID) -> int:
    """An identity's index in a group's `uuids`, appended the first time the group names it."""
    return uuids.setdefault(identity, len(uuids))


def _light_changes(before: PerceivedLightSource, after: PerceivedLightSource, uuids: dict[UUID, int]
                   ) -> LightChanges:
    """A perceived light source's wire fields that differ after the settlement (a revision alone is none)."""
    changes: LightChanges = {}
    if before.position != after.position:
        changes["position"] = after.position
    if before.base_height_steps != after.base_height_steps:
        changes["base_height_steps"] = after.base_height_steps
    if before.very_bright_radius_feet != after.very_bright_radius_feet:
        changes["very_bright_radius_feet"] = after.very_bright_radius_feet
    if before.bright_radius_feet != after.bright_radius_feet:
        changes["bright_radius_feet"] = after.bright_radius_feet
    if before.dim_radius_feet != after.dim_radius_feet:
        changes["dim_radius_feet"] = after.dim_radius_feet
    if before.appearance != after.appearance:
        changes["appearance"] = after.appearance
    if before.actor_anchored != after.actor_anchored:
        changes["actor_anchored"] = after.actor_anchored
    if before.anchor_entity_uuid != after.anchor_entity_uuid:
        changes["anchor_entity"] = (_uuid_row(uuids, after.anchor_entity_uuid)
                                    if after.anchor_entity_uuid is not None else None)
    if before.anchor_item_uuid != after.anchor_item_uuid:
        changes["anchor_item"] = (_uuid_row(uuids, after.anchor_item_uuid)
                                  if after.anchor_item_uuid is not None else None)
    return changes


def _light_row(source: PerceivedLightSource, uuids: dict[UUID, int]) -> LightRow:
    """A light source entering the seat's perception, its identities rows of the group's `uuids`."""
    return LightRow(source=_uuid_row(uuids, source.source_uuid), position=source.position,
        base_height_steps=source.base_height_steps, very_bright_radius_feet=source.very_bright_radius_feet,
        bright_radius_feet=source.bright_radius_feet, dim_radius_feet=source.dim_radius_feet,
        appearance=source.appearance, actor_anchored=source.actor_anchored,
        anchor_entity=_uuid_row(uuids, source.anchor_entity_uuid) if source.anchor_entity_uuid is not None else None,
        anchor_item=_uuid_row(uuids, source.anchor_item_uuid) if source.anchor_item_uuid is not None else None)


@dataclass(frozen=True, slots=True)
class FactCells:
    """A settlement fact's composed cell lists, kept by its walk's table until the group's cell tables are built."""

    visible_added: CellMask
    visible_removed: CellMask
    light_changed: CellValues
    hazards_changed: CellValues


@dataclass(slots=True)
class SensoryTable:
    """One walk's sensory rows, appended by its settlement facts in walk order: the group's `SensoryRows` but its
    cell tables. A settlement names each identity once and nothing is interned, so a fact's indices are the
    group's; `_sensory_rows` builds the cell tables from each fact's `FactCells` (`cells`, in fact order).

    One seat's walk over one group holds it (`SeatWalk.table`)."""

    uuids: dict[UUID, int] = field(default_factory=dict)
    contact_uuid_index: list[int] = field(default_factory=list)
    contacts: list[PerceivedContact] = field(default_factory=list)
    contact_members: list[int] = field(default_factory=list)
    sighting_uuid_index: list[int] = field(default_factory=list)
    sightings: list[SpatialEffectSighting] = field(default_factory=list)
    sighting_members: list[int] = field(default_factory=list)
    patch_uuid_index: list[int] = field(default_factory=list)
    sighting_patches: list[SpatialEffectPatch] = field(default_factory=list)
    retired_uuid_index: list[int] = field(default_factory=list)
    retired_cells: list[CellMask] = field(default_factory=list)
    light_sources: list[LightRow] = field(default_factory=list)
    light_patches: list[LightPatch] = field(default_factory=list)
    cells: list[FactCells] = field(default_factory=list)


def _effect_content(effect: PerceivedSpatialEffect) -> SpatialEffectContent:
    return SpatialEffectContent(content_ref=effect.content_ref, name=effect.name, description=effect.description)


def _settlement_fact(change: ComposedChange, view: SensesSnapshot, state: "ProjectionState", walk: "SeatWalk"
                     ) -> SensoryFact | None:
    """The seat's composed perception change at one settlement (plan §3.1), its rows appended to the walk's
    table; None when nothing the seat is shown changed.

    Each record perceived before and after travels as its change (a patched effect or light source: its changed
    disclosed fields); a record entering perception whole (an effect with its content the first time the seat
    sees it); a record leaving perception by key. Contacts and effects carry the members perceiving them (bit i:
    the audience's `observers[i]`). An effect's duration is shown only to the seat owning it, so a non-owner's
    duration tick sends nothing. Retired cells (plan §8, found-effect memory) name only effects the seat was sent, outside their
    perceived cells after the settlement."""
    table = walk.table
    bits = {member: 1 << index for index, member in enumerate(state.audience.observers)}

    def members(owners: frozenset[UUID]) -> int:
        return sum(bits[member] for member in owners)
    owned, sent, pending = state.owned_spatial_effects, state.static_sent.spatial_content, walk.pending.spatial_content
    entity_changed, entity_removed, object_changed, object_removed = [], [], [], []
    for contacts, changed, removed in ((change.entities, entity_changed, entity_removed),
                                       (change.objects, object_changed, object_removed)):
        for identity, (_, after) in contacts.items():
            if after is None:
                removed.append(_uuid_row(table.uuids, identity))
                continue
            changed.append(len(table.contacts))
            table.contact_uuid_index.append(_uuid_row(table.uuids, identity))
            table.contacts.append(after.contact)
            table.contact_members.append(members(after.members))
    added, patched, effects_removed, retired = [], [], [], []
    content: dict[UUID, SpatialEffectContent] = {}
    for identity, (before_effect, after_effect) in change.effects.items():
        own = identity in owned
        if after_effect is None:
            if before_effect is not None:
                effects_removed.append(_uuid_row(table.uuids, identity))
            continue
        if before_effect is None:
            added.append(len(table.sightings))
            table.sighting_uuid_index.append(_uuid_row(table.uuids, identity))
            table.sightings.append(_sighting(after_effect.effect, own))
            table.sighting_members.append(members(after_effect.members))
            if identity not in sent and identity not in pending:
                content[identity] = _effect_content(after_effect.effect)
                pending.add(identity)
            continue
        patch = _sighting_patch(before_effect.effect, after_effect.effect, own,
            members(after_effect.members) if after_effect.members != before_effect.members else None)
        if patch is not None:
            patched.append(len(table.sighting_patches))
            table.patch_uuid_index.append(_uuid_row(table.uuids, identity))
            table.sighting_patches.append(patch)
    for identity, cells in change.retired.items():
        held = view.spatial_effects.get(identity)
        left = cells.difference(held.positions) if held is not None else cells
        if left and (identity in sent or identity in pending):
            retired.append(len(table.retired_cells))
            table.retired_uuid_index.append(_uuid_row(table.uuids, identity))
            table.retired_cells.append(mask_from_positions(left))
    lights_added, lights_patched, lights_removed = [], [], []
    for identity, (before_light, after_light) in change.lights.items():
        if after_light is None:
            lights_removed.append(_uuid_row(table.uuids, identity))
        elif before_light is None:
            lights_added.append(len(table.light_sources))
            table.light_sources.append(_light_row(after_light, table.uuids))
        elif changes := _light_changes(before_light, after_light, table.uuids):
            lights_patched.append(len(table.light_patches))
            table.light_patches.append(LightPatch(source=_uuid_row(table.uuids, identity), changes=changes))
    if not (change.initial or change.position_changed or change.sense_modes_changed
            or change.passive_perception_changed or change.visual_access_changed
            or not no_cells(change.visible_added) or not no_cells(change.visible_removed)
            or not no_cells(change.light_changed.cells) or not no_cells(change.hazards_changed.cells)
            or entity_changed or entity_removed or object_changed or object_removed or added or patched
            or effects_removed or retired or lights_added or lights_patched or lights_removed):
        return None
    table.cells.append(FactCells(change.visible_added, change.visible_removed, change.light_changed,
                                 change.hazards_changed))
    return SensoryFact(initial=change.initial,
        observer_position=view.position if change.position_changed else None,
        entity_contacts_changed=tuple(entity_changed), entity_contacts_removed=tuple(entity_removed),
        object_contacts_changed=tuple(object_changed), object_contacts_removed=tuple(object_removed),
        sense_modes_changed=change.sense_modes_changed,
        sense_modes=tuple(view.sense_modes) if change.sense_modes_changed else None,
        passive_perception_changed=change.passive_perception_changed,
        passive_perception=view.passive_perception if change.passive_perception_changed else None,
        visual_access_changed=change.visual_access_changed,
        visual_access=view.visual_access if change.visual_access_changed else None, paths_dirty=change.paths_dirty,
        spatial_effects_added=tuple(added), spatial_effects_patched=tuple(patched),
        spatial_effects_removed=tuple(effects_removed), spatial_effect_cells_retired=tuple(retired),
        spatial_effect_content=content, light_sources_added=tuple(lights_added),
        light_sources_patched=tuple(lights_patched), light_sources_removed=tuple(lights_removed))


def _held_item_disclosed(item_uuid: UUID | None, event: Event, observer: PlayerAudience,
                         actors: Mapping[UUID, ActorState], known: Collection[UUID],
                         senses: SensesSnapshot | None) -> bool:
    if any(identity in actors and item_uuid in shown_items(actors[identity], View.CONTROLLER)
           for identity in observer.controlled):
        return True
    return senses is not None and any(identity in known and identity in actors
        and contact.visual and _identified(event, identity, observer)
        and item_uuid in shown_items(actors[identity], View.OBSERVER)
        for identity, contact in senses.entities.items())


def _held_content_at_event(event: Event, observer: PlayerAudience, actors: Mapping[UUID, ActorState],
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


@dataclass(frozen=True, slots=True)
class BodiesStep:
    """One event's change to the session's actors, shared by every seat: its rows (`change_rows`, computed once
    against the fold before the event) in both views (`change_views`)."""

    views: tuple[ActorChangeViews, ...]
    # The actors the event wrote: a seat sent the event's fact drops its stamps of them.
    changed: tuple[UUID, ...] = ()


NO_BODIES_STEP = BodiesStep(())


def _change_fact(event: Event, step: BodiesStep, observer: PlayerAudience, known: Collection[UUID],
                 senses: SensesSnapshot | None, sent: StaticSent, pending: StaticSent) -> ActorChangeFact | None:
    """The seat's part of the event's rows; the looks and profiles it sends join the walk's `pending`."""
    fact = change_fact(event, step.views, observer, known, senses, sent=sent, pending=pending)
    if fact is not None:
        pending.item_looks.update(record.item_uuid for record in fact.items if record.look is not None)
        pending.item_profiles.update(record.item_uuid for record in fact.items if record.profile is not None)
    return fact


def _project_fact(event: Event, observer: PlayerAudience, actors: Mapping[UUID, ActorState],
                  condition: ConditionFact | None, events: tuple[Event, ...],
                  entered: Collection[UUID], known: Collection[UUID],
                  observed_objects: set[UUID], senses: SensesSnapshot | None, keys: "NativeKeys",
                  step: BodiesStep, sent: StaticSent, pending: StaticSent,
                  declaration_senses: DeclarationSenses | None = None
                  ) -> PlayerFact | None:
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
                    previous_state=None, state=None, operation=event.operation,
                    interaction_operation=interaction_operation, removed_positions=positions) if positions else None
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
            raise ValueError("A sensory event is projected by the walk (_settlement_fact)")
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
                        or event.source_entity_uuid in entered)
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
            target_position = event.target_position if event.target_kind == "object" and (
                observer.controls(source) or event.target_position is not None and (
                    _position_allowed(event, event.target_position, observer)
                    or declaration_senses is not None and cell_in(declaration_senses.visible, event.target_position))) else None
            target_height = event.target_base_height_steps if event.target_kind == "object" else None
            if event.application is not None:
                # One target's application: its declaration is its cast's (the node's resolution lineage), whose
                # nodes the same group carries (plan §3.6).
                return SpellFact(target_entity_uuid=target, target_kind=event.target_kind,
                    target_position=target_position, target_base_height_steps=target_height,
                    propagation=event.propagation, attack_outcome=event.attack_outcome)
            return SpellFact(source_entity_uuid=source, target_entity_uuid=target,
                target_kind=event.target_kind, target_position=target_position, target_base_height_steps=target_height,
                behavior_id=event.behavior_id, name=event.name, source_position=source_position,
                cast_origin=event.cast_origin,
                source_item_uuid=event.source_item_uuid if event.source_item_uuid in observed_objects else None,
                declared_target_entity_uuids=tuple(identity for identity in event.declared_target_entity_uuids
                    if (not area and not propagated) or identity in observed_objects
                    or identity in known and _identified(event, identity, observer)),
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
                    if event.entity_uuid in actors
                    and identity in {item for _, item in actors[event.entity_uuid].equipment})))
        case DeathSaveEvent():
            return (None if event.entity_uuid not in known or not _identified(event, event.entity_uuid, observer) else DeathSaveFact(
                entity_uuid=event.entity_uuid, natural_roll=event.natural_roll, succeeded=event.succeeded))
        case SavingThrowEvent():
            return (None if target is None or event.result is None else SavingThrowFact(
                target_entity_uuid=target, ability_name=event.ability_name, succeeded=event.result,
                indomitable_reroll=event.indomitable_reroll,
                effect_id=event.saving_throw_context.effect_id if event.saving_throw_context is not None else None))
        case ItemResourceChangeEvent():
            # The controller's charges fact; any other seat sees a destroyed equipped item's layer go.
            return (ItemChargeFact(source_entity_uuid=event.source_entity_uuid, item_uuid=event.item_uuid,
                charges_after=event.charges_after, stack_count_after=event.stack_count_after,
                item_destroyed=event.item_destroyed, resource_change=event.resource_change)
                if observer.controls(event.source_entity_uuid) else _change_fact(event, step, observer, known,
                    senses, sent, pending))
        case EquipmentEvent() | ItemLocationStateEvent() | ItemHoldingsReleasedEvent():
            return _change_fact(event, step, observer, known, senses, sent, pending)
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
            # A membership on a body, a held item's effect: the bodies' rows (a tile's or a floor object's change
            # is the seat's world update).
            return _change_fact(event, step, observer, known, senses, sent, pending)
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


def _disclosed_member(member: ConditionMember, disclosed: LineageDisclosure) -> ConditionMember:
    state = member.state
    if state is None or not state.concentration_slots:
        return member
    return replace(member, state=state.model_copy(update={
        "concentration_slots": _disclosed_slots(state.concentration_slots, disclosed)}))


def _disclosed_record(record: ItemRecord, disclosed: LineageDisclosure) -> ItemRecord:
    state = record.state
    if state is None or not state.concentration_slots:
        return record
    return replace(record, state=replace(state, concentration_slots=_disclosed_slots(state.concentration_slots,
        disclosed)))


def _disclosed_body(record: BodyRecord, disclosed: LineageDisclosure) -> BodyRecord:
    """A body record with undisclosed casting lineages cleared."""
    body = record.body
    return replace(record, body=replace(body, conditions=tuple(_disclosed_member(row, disclosed)
        for row in body.conditions)), items=tuple(_disclosed_record(row, disclosed) for row in record.items))


def _disclosed_row(row: ChangeRow, disclosed: LineageDisclosure) -> ChangeRow:
    match row:
        case ConditionRow(member=ConditionMember() as member):
            return replace(row, member=_disclosed_member(member, disclosed))
        case ItemStateRow() if "concentration_slots" in row.changes:
            return replace(row, changes={**row.changes, "concentration_slots": _disclosed_slots(
                row.changes["concentration_slots"], disclosed)})
    return row


def _disclosed_change(fact: ActorChangeFact, disclosed: LineageDisclosure) -> ActorChangeFact:
    """An actor change with undisclosed casting lineages cleared."""
    return replace(fact, actors=tuple(replace(change, rows=tuple(_disclosed_row(row, disclosed)
        for row in change.rows)) for change in fact.actors),
        items=tuple(_disclosed_record(row, disclosed) for row in fact.items))


@dataclass(frozen=True, slots=True)
class WalkGroup:
    """One group's seat-independent walk inputs: its versions and their native keys and cursors."""

    keys: NativeKeys
    versions: tuple[ObjectiveRow, ...]
    indexes: Mapping[UUID, int]
    occurrences: frozenset[int]
    version_lineages: Mapping[UUID, UUID]


def _walk_group(session: "SessionProjection", versions: tuple[ObjectiveRow, ...]) -> WalkGroup:
    """Record the group's native keys in the session (their one writer) and the group's frozen walk inputs; a
    group is walked once per session (its events fold the session world)."""
    if not versions or versions[0].event_uuid in session.walked:
        raise ValueError("A session walks each group once, with all its seats")
    session.walked.add(versions[0].event_uuid)
    for row in versions:
        session.versions[row.event_uuid] = row.source_index
        session.lineages.setdefault(row.lineage_uuid, row.source_index)
    indexes = {row.event_uuid: row.source_index for row in versions}
    return WalkGroup(NativeKeys(session.versions, session.lineages), versions, indexes, frozenset(indexes.values()),
        {row.event_uuid: row.lineage_uuid for row in versions})


def _due(events: tuple[Event, ...], indexes: Mapping[UUID, int], starts: list[tuple[Row, int]]
         ) -> dict[UUID, tuple[Row, ...]]:
    """Each start (in cursor order) assigned to the first walk event at or after its cursor, by that event."""
    pending = iter(sorted(starts, key=lambda row: row[1]))
    start = next(pending, None)
    due: dict[UUID, tuple[Row, ...]] = {}
    for event in events:
        rows = []
        while start is not None and start[1] <= indexes[event.uuid]:
            rows.append(start[0])
            start = next(pending, None)
        if rows:
            due[event.uuid] = tuple(rows)
    return due


@dataclass(slots=True)
class SeatWalk:
    """One seat's walk over one group: its events and their schedules, and what the walk builds.

    Plain data owned by the walk and dropped when the group is emitted. The
    seat's projection state is passed to each step, never held here.
    """

    events: tuple[Event, ...]
    # The condition facts by their event (a recorded fact may name none).
    facts: dict[UUID | None, ConditionFact]
    # The shared fold's actor change of each event that has one (E2's record), by event uuid.
    actor_fact_changes: Mapping[UUID, ActorFactChange]
    # The seat's combat-log entries: an initialization's as its capture projected them (`logs`); a lineage's
    # projected at each event from its native log (`native_logs`), with the names of the bodies the seat holds at
    # that event (`names`, its births sent and this walk's, inclusive) and its `log_inputs` as of the operation.
    logs: Mapping[UUID, PlayerLogEntry]
    native_logs: Mapping[UUID, CombatLogEntry]
    names: dict[str, str]
    log_inputs: "SeatLogInputs"
    # The group's renderings, shared by all its seats.
    shared_logs: SharedLogEntries
    by_lineage: dict[UUID, Event]
    # Before each walk event (by uuid): the deliveries whose entry sight is kept, and the objects whose removal starts.
    deliveries_at: dict[UUID, tuple[UUID, ...]]
    removals_at: dict[UUID, tuple[UUID, ...]]
    explicit_destructions: frozenset[UUID]
    table: SensoryTable
    # The bodies the seat holds at this point of the walk (their births sent).
    known: set[UUID]
    # The seat's settlements: at the first sensory event of its members in each, all of them (in walk order);
    # the others are `settled` there (plan §3.1: one composition per settlement).
    settlements: dict[UUID, tuple[SensoryUpdateEvent, ...]] = field(default_factory=dict)
    settled: frozenset[UUID] = frozenset()
    # The bodies that entered the seat's view during the walk.
    entered: set[UUID] = field(default_factory=set)
    # Contacts the seat's view took before the session held their actor (seen before their birth completed):
    # each enters at its birth, if the view still holds it.
    unborn: set[UUID] = field(default_factory=set)
    # An interaction may itself hide the object. Retain its already granted
    # identity at entry; a remote control's undisclosed target gains no identity.
    observed_objects: set[UUID] = field(default_factory=set)
    delivery_declarations: dict[UUID, DeclarationSenses | None] = field(default_factory=dict)
    destroyed_contacts: dict[UUID, PlayerObject] = field(default_factory=dict)
    nodes: list[PlayerNode] = field(default_factory=list)
    bodies: list[BodyRecord] = field(default_factory=list)
    updates: list[WorldUpdate] = field(default_factory=list)
    # The static rows this walk's updates carry, joining the seat's sent set once the group is emitted.
    pending: StaticSent = field(default_factory=StaticSent)
    # The stamp changes this walk's updates make, joining the seat's stamps once the group is emitted.
    stamps: StampChanges = field(default_factory=StampChanges)
    # The versions whose records the seat's world updates carried: each once per seat (a walked event's own, or a
    # change several members saw happen).
    published_sources: set[UUID] = field(default_factory=set)
    content_at_event: dict[UUID, frozenset[str]] = field(default_factory=dict)
    # The walk's projected log entries by native entry (`seat_log_entry`'s memo), one per group and seat.
    retained_logs: dict[int, CombatLogEntry | None] = field(default_factory=dict)
    # The walk's changes to the seat's body stamps, joining them at emission; None drops a stamp.
    body_stamps: dict[UUID, int | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SeatLogInputs:
    """What a seat's combat log reads besides the bodies it holds, as of the operation's start: the connectors it
    sees and the content ids it holds."""

    connectors: frozenset[str] = frozenset()
    content_ids: frozenset[str] = frozenset()


NO_LOG_INPUTS = SeatLogInputs()


def _seat_log(walk: SeatWalk, event: Event, observer: PlayerAudience) -> PlayerLogEntry | None:
    """The seat's entry of an event's combat log: a lineage event's projected now, with the names of the bodies the
    seat holds at this event; an initialization event's as captured."""
    native = walk.native_logs.get(event.uuid)
    if native is None:
        return walk.logs.get(event.uuid)
    return seat_log_entry(native, observer, known_entity_names=walk.names,
        known_connector_uuids=walk.log_inputs.connectors, known_content_ids=walk.log_inputs.content_ids,
        retained_entries=walk.retained_logs, shared=walk.shared_logs)


def _begin_walk(group: WalkGroup, state: "ProjectionState", events: tuple[Event, ...],
                conditions: tuple[ConditionFact, ...], actor_fact_changes: Mapping[UUID, ActorFactChange],
                logs: Mapping[UUID, PlayerLogEntry], native_logs: Mapping[UUID, CombatLogEntry],
                names: Mapping[UUID, str], log_inputs: SeatLogInputs, shared_logs: SharedLogEntries) -> SeatWalk:
    """A seat's walk over a group: its events (old recordings upgraded) and their schedules."""
    events = upgrade_recorded_spatial_commits(events, tuple(
        (row.lineage_uuid, row.event_uuid) for row in sorted(group.versions, key=lambda row: row.source_index)))
    indexes = group.indexes
    by_lineage = {event.lineage_uuid: event for event in events}
    # A delivery can obscure itself; a field removal clears its contact through
    # a sensory child before completing. Retain each event's entry sight: a
    # nested event must not borrow its outer root's earlier observation.
    delivery_starts: dict[UUID, int] = {}
    for version in group.versions:
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
    # A break's sensory children can run before its completion. Capture the
    # contact at the integrity transition's entry; old recordings instead
    # witness the removal which preceded their replacement-object fact.
    destroyed_ids = {event.item_state.item_uuid for event in events
                     if isinstance(event, ItemLocationStateEvent) and event.location is ItemLocation.DESTROYED}
    removal_starts: dict[UUID, int] = {}
    for version in group.versions:
        removed = by_lineage.get(version.lineage_uuid)
        if isinstance(removed, ItemDestructionEvent) and not removed.canceled:
            removal_starts.setdefault(removed.item_uuid, version.source_index)
        elif (isinstance(removed, SpatialChangeEvent) and not removed.canceled
                and removed.change_type is SpatialChangeType.OBJECT_REMOVED and removed.object_uuid in destroyed_ids):
            assert removed.object_uuid is not None
            removal_starts.setdefault(removed.object_uuid, version.source_index)
    sent = state.static_sent
    # A settlement's events share its marker; an event recorded without one is a settlement of its own.
    settlements: dict[int | UUID, list[SensoryUpdateEvent]] = {}
    for event in events:
        if isinstance(event, SensoryUpdateEvent) and state.audience.observes(event.observer_uuid):
            settlements.setdefault(event.settlement if event.settlement is not None else event.uuid, []).append(event)
    return SeatWalk(events=events, facts={row.event_uuid: row for row in conditions},
        actor_fact_changes=actor_fact_changes, logs=logs, native_logs=native_logs,
        names={str(identity): names[identity] for identity in sent.actor_births}, log_inputs=log_inputs,
        shared_logs=shared_logs,
        by_lineage=by_lineage,
        deliveries_at=_due(events, indexes, list(delivery_starts.items())),
        removals_at=_due(events, indexes, list(removal_starts.items())),
        explicit_destructions=frozenset(event.item_uuid for event in events if isinstance(event, ItemDestructionEvent)),
        table=SensoryTable(), known=set(sent.actor_births),
        settlements={members[0].uuid: tuple(members) for members in settlements.values()},
        settled=frozenset(event.uuid for members in settlements.values() for event in members[1:]),
        observed_objects=set(state.observed_objects))


def _enter_event(walk: SeatWalk, state: "ProjectionState", world: WorldFacts, event: Event) -> None:
    """A seat's part of an event before the session folds take its after-values: the captures due at its cursor."""
    view = state.audience_composition.view
    for identity in walk.removals_at.get(event.uuid, ()):
        if view is not None and identity in world.objects and object_observed(world, view, identity):
            walk.destroyed_contacts[identity] = disclosed_world_object(world, view, identity,
                state.static_sent.object_looks | walk.pending.object_looks)
    for lineage in walk.deliveries_at.get(event.uuid, ()):
        senses = view
        walk.delivery_declarations[lineage] = (None if senses is None else DeclarationSenses(
            senses.visible, dict(senses.entities), dict(senses.objects), dict(senses.spatial_effects)))


def _fold_version(session: "SessionProjection", folded: dict[UUID, AppliedWorldFact | None], event: Event,
                  condition: ConditionFact | None) -> AppliedWorldFact | None:
    """The session world's one writer: a version's recorded after-values (E2's fold), once per version and session.

    Returns what the fold applied (recorded in `folded`, the group's folded versions); None where it applied
    nothing (a canceled version applies nothing).
    """
    if event.uuid in folded:
        raise ValueError("A session folds each version once")
    folded[event.uuid] = applied = apply_world_fact(session.world, event, condition)
    if applied is not None:
        forget_written(session.tile_digests, applied)
    return applied


def _fold_actors(actors: dict[UUID, ActorState], names: dict[UUID, str],
                 folded: Mapping[UUID, AppliedWorldFact | None], event: Event,
                 changes: Mapping[UUID, ActorFactChange], condition: ConditionFact | None) -> BodiesStep:
    """The session actors' one writer: a completed version's birth, recorded actor change (E2's record, the
    shared fold's own function) and lifetime end, once per version and session (before the version's world fold,
    which `folded` records). Returns the change's rows in both views, built once for every seat against the
    actors before the change."""
    if event.uuid in folded:
        raise ValueError("A session folds each version once")
    if event.canceled or event.phase is not EventPhase.COMPLETION:
        return NO_BODIES_STEP
    if (born := fold_birth(actors, event)) is not None:
        names[born] = actors[born].name
    change = recorded_actor_change(changes, event)
    if change is None:
        fold_completed_actors(actors, event, None)
        return NO_BODIES_STEP
    rows = change_rows(change, actors, consumed=condition is not None and condition.consumed)
    before = {row.actor_uuid: actors[row.actor_uuid] for row in rows}
    written = fold_completed_actors(actors, event, change)
    return BodiesStep(change_views(rows, before, {identity: actors[identity] for identity in before
                                                  if identity in actors}), written)


def _enter_body(walk: SeatWalk, group: WalkGroup, state: "ProjectionState", actors: Mapping[UUID, ActorState],
                loadout_ids: dict[VisualLoadout, str], event: Event, identity: UUID, visual: bool) -> None:
    """A body entering the seat's view at this event, whole; its birth, its loadout's value and its items' static
    parts the first time."""
    actor = actors.get(identity)
    if actor is None:
        return
    record = entering_body(group.indexes[event.uuid], actor, state.audience, visual=visual,
        birth=identity not in walk.known, sent=state.static_sent, pending=walk.pending, loadout_ids=loadout_ids)
    digest = body_digest(record) if body_stampable(record) else None
    walk.known.add(identity)
    walk.names[str(identity)] = actor.name
    walk.entered.add(identity)
    if (record.birth is None and digest is not None
            and unchanged_since(walk.body_stamps if identity in walk.body_stamps else state.body_stamps,
                                identity, digest)):
        # The seat holds this body as it is: confirmed unchanged, no record.
        return
    walk.bodies.append(record)
    walk.body_stamps[identity] = digest
    walk.pending.item_looks.update(row.item_uuid for row in record.items if row.look is not None)
    walk.pending.item_profiles.update(row.item_uuid for row in record.items if row.profile is not None)
    walk.pending.visual_loadouts.add(record.body.visual_loadout_id)


def _publish_world(walk: SeatWalk, group: WalkGroup, state: "ProjectionState", world: WorldFacts,
                   digests: TileDigests, event: Event,
                   applied: AppliedWorldFact | None, folded: Mapping[UUID, AppliedWorldFact | None],
                   before: CellMask, settlement: tuple[SensoryUpdateEvent, ...] = ()) -> None:
    """The seat's world update at an event (`before`: its composed view's visible cells before the event): what
    the event wrote or, at a settlement of its members (`settlement`, at its first event), what their senses
    changed and what the changes they saw happen wrote (folded at their own versions), each of those once per
    seat."""
    composition, audience = state.audience_composition, state.audience
    records: tuple[AppliedWorldFact, ...] = (applied,) if applied is not None else ()
    # Each record publishes once per seat: a walked event's own, or an observed change's at the first sight of it.
    walk.published_sources.add(event.uuid)
    sensed = None
    if settlement:
        sources = tuple(source for source in dict.fromkeys(row.source_event_uuid for member in settlement
            for row in member.observed_changes) if source not in walk.published_sources)
        walk.published_sources.update(sources)
        records = tuple(record for source in sources if (record := folded.get(source)) is not None)
        sensed = SensedWorld(frozenset(identity for member in settlement
                for identity in (*member.object_contacts_changed, *member.object_contacts_removed)),
            frozenset(identity for member in settlement
                for identity in (*member.spatial_effects_changed, *member.spatial_effects_removed)))
    view = composition.view
    if view is None:
        return
    update = seat_world_update(world, group.indexes[event.uuid], records, before, view, composition.perception,
        audience, sensed, observed=state.observed_objects, granted=state.granted_containers, sent=state.static_sent,
        pending=walk.pending, digests=digests, stamps=SeatStamps(state.world_stamps, walk.stamps))
    if update is not None:
        walk.updates.append(update)


def _leave_event(walk: SeatWalk, group: WalkGroup, state: "ProjectionState", world: WorldFacts,
                 digests: TileDigests, actors: Mapping[UUID, ActorState], loadout_ids: dict[VisualLoadout, str],
                 event: Event,
                 applied: AppliedWorldFact | None,
                 folded: Mapping[UUID, AppliedWorldFact | None], step: BodiesStep) -> None:
    """A seat's part of an event after the session folds took its after-values (`applied`: what the world fold
    applied; `step`: the actors' change and rows): its senses, the bodies entering its view, its world update, its
    node. `folded` holds what each version the group folded so far applied."""
    observer = state.audience
    keys, indexes, facts = group.keys, group.indexes, walk.facts
    settlement = walk.settlements.get(event.uuid, ())
    sensory_fact = None
    # A settlement's later events were composed at its first.
    if not event.canceled and event.uuid not in walk.settled and (applied is not None or settlement):
        composition = state.audience_composition
        before = composition.view.visible if composition.view is not None else EMPTY_CELLS
        if settlement:
            # The settlement's senses, at its first event: the seat's perception and composed view after all of
            # its members' observations, composed once. A body enters when the seat's composed view takes it as
            # a contact (a member regaining a body another holds is no entry); only the members' changed contacts
            # can enter, in their order. A controlled body never enters here: it is always perceived (below).
            held = composition.view.entities if composition.view is not None else {}
            entering = tuple(identity for identity in dict.fromkeys(identity for member in settlement
                for identity in member.entity_contacts_changed)
                if not observer.controls(identity) and (identity not in held or identity not in walk.known))
            change = apply_settlement(composition, observer, state.observer_uuid, settlement)
            view = composition.view
            if view is not None:
                sensory_fact = _settlement_fact(change, view, state, walk)
                for identity in entering:
                    contact = view.entities.get(identity)
                    if contact is not None and identity not in actors:
                        walk.unborn.add(identity)
                    elif contact is not None:
                        _enter_body(walk, group, state, actors, loadout_ids, event, identity, contact.visual)
        _publish_world(walk, group, state, world, digests, event, applied, folded, before, settlement)
    for identity in observer.controlled:
        # A controlled body is always perceived: it enters once the session holds it.
        if identity not in walk.known and identity in actors:
            _enter_body(walk, group, state, actors, loadout_ids, event, identity, True)
    view = state.audience_composition.view
    for identity in tuple(walk.unborn):
        if identity in actors:
            walk.unborn.discard(identity)
            if view is not None and (contact := view.entities.get(identity)) is not None:
                _enter_body(walk, group, state, actors, loadout_ids, event, identity, contact.visual)
    observed_objects = walk.observed_objects
    if (isinstance(event, ActionEvent) and event.source_item_uuid is not None
            and event.source_item_uuid in world.objects
            and object_observed(world, view, event.source_item_uuid)):
        observed_objects.add(event.source_item_uuid)
    if (isinstance(event, (AttackEvent, SpellEvent)) and event.target_kind == "object"
            and event.target_entity_uuid is not None
            and event.target_entity_uuid in world.objects
            and object_observed(world, view, event.target_entity_uuid)):
        observed_objects.add(event.target_entity_uuid)
    declaration_senses = walk.delivery_declarations.get(event.lineage_uuid)
    if (isinstance(event, SpatialChangeEvent)
            and event.change_type is SpatialChangeType.ENTITY_LEFT
            and event.terminal_release is not None
            and event.terminal_release.cause is SummonDepartureCause.DEFEATED):
        # Death removes living contacts before retiring a summon. Retain
        # only the exact causing death's entry sight, never root visibility.
        cause_lineage = (group.version_lineages.get(event.terminal_release.parent_event_uuid)
            if event.terminal_release.parent_event_uuid is not None else None)
        cause = walk.by_lineage.get(cause_lineage) if cause_lineage is not None else None
        if isinstance(cause, DeathEvent) and not cause.canceled and cause.entity_uuid == event.entity_uuid:
            declaration_senses = walk.delivery_declarations.get(cause.lineage_uuid)
    known = walk.known
    # A sensory event's fact is its settlement's composed change, at the settlement's first event of the seat.
    fact = (sensory_fact if isinstance(event, SensoryUpdateEvent) else _project_fact(event, observer, actors,
            facts.get(event.uuid), walk.events, walk.entered, known, observed_objects, view, keys,
            step, state.static_sent, walk.pending, declaration_senses))
    if fact is not None:
        # The seat folds this event's after-values: its stamps of the bodies the event wrote no longer hold.
        walk.body_stamps.update(dict.fromkeys(step.changed))
    if isinstance(fact, SpatialFact) and not event.canceled:
        if (commit_current(state.spatial_commit_cursors, fact, source_cursor=indexes[event.uuid],
                           occurrences=group.occurrences)
                and fact.terminal_departure and fact.entity_uuid is not None and fact.entity_uuid in known):
            depart_contact(state.audience_composition, fact.entity_uuid)
    if isinstance(fact, FactionFact):
        parent = walk.by_lineage.get(event.parent_lineage) if event.parent_lineage is not None else None
        removed = (facts.get(parent.uuid) if parent is not None
            and parent.event_type is EventType.CONDITION_REMOVAL
            and parent.phase is EventPhase.COMPLETION and not parent.canceled
            and parent.target_entity_uuid == fact.entity_uuid else None)
        actor = actors.get(fact.entity_uuid)
        origin = actor.summon_origin if actor is not None else None
        contact = view.entities.get(fact.entity_uuid) if view is not None else None
        if (event.phase is EventPhase.COMPLETION and not event.canceled
                and removed is not None and actor is not None and origin is not None
                and origin.control_condition_uuid is not None
                and removed.condition_uuid == origin.control_condition_uuid
                and any(row.condition_uuid == origin.existence_condition_uuid for row in actor.conditions)
                and contact is not None and contact.visual):
            fact = replace(fact, control_lost=True)
    destroyed_contacts = walk.destroyed_contacts
    if (isinstance(event, TakeDamageEvent) and not event.canceled
            and event.final_damage is not None and event.resulting_hp is not None):
        identity = event.target_entity_uuid
        if identity is not None and (
                identity in world.objects
                and world.objects[identity].item.integrity is ItemIntegrity.INTACT
                and object_observed(world, view, identity)
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
                remnant_state=observed_remnant(event.resulting_state.remnant_state,
                    state.static_sent.object_looks | walk.pending.object_looks)
                    if event.resulting_state is not None else None,
                destruction_outcome=event.resulting_state.destruction_outcome if event.resulting_state is not None else None,
                remains_disposition=event.remains_disposition, previous_item=destroyed.item,
                affected_volume=event.affected_volume,
                resulting_placement=event.resulting_placement)
    if (isinstance(event, ItemLocationStateEvent) and event.location is ItemLocation.DESTROYED
            and event.item_state.item_uuid not in walk.explicit_destructions):
        destroyed = destroyed_contacts.get(event.item_state.item_uuid)
        if destroyed is not None:
            replacement = event.replacement_item_uuid
            if (replacement is None or replacement not in world.objects
                    or not object_observed(world, view, replacement)):
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
    walk.content_at_event[event.uuid] = (_held_content_at_event(event, observer,
        actors, known, view)
        if needs_held_content else frozenset())
    walk.nodes.append(PlayerNode(occurrence=indexes[event.uuid],
        parent_event=_version_key(keys, event.parent_event), parent_lineage=_lineage_key(keys, event.parent_lineage),
        children_lineages=tuple(key for identity in event.children_lineages
            if (key := _lineage_key(keys, identity)) is not None), phase=event.phase,
        canceled=event.canceled, fact=fact, combat_log=_action_log(_seat_log(walk, event, observer), fact, observer),
        turn_execution_id=event.turn_execution_id,
        cancellation=ActionCancellation(phase=event.canceled_from_phase,
            action_economy_spent=event.action_economy_spent, outcome_code=event.outcome_code)
            if event.canceled and isinstance(event, ActionEvent) and fact is not None else None))


def _end_walk(walk: SeatWalk, group: WalkGroup, state: "ProjectionState"
              ) -> tuple[tuple[PlayerNode, ...], tuple[int, ...], tuple[BodyRecord, ...], tuple[WorldUpdate, ...],
                         dict[int, tuple[int, UUID | None]]]:
    """The walked group privately: nodes and each one's lineage (native key), the bodies entering the seat's
    view, world updates.

    Also returns each node's disclosed resolution (its lineage's native key
    and application) by the node's native occurrence. Versions and lineages
    are identified by their native keys (`NativeKeys`) until
    `_public_occurrences`. Sensory facts name rows of the walk's `table` (their cell lists are set by
    `_sensory_rows`).
    """
    keys, disclosed, observer = group.keys, state.disclosed_lineages, state.audience
    nodes, bodies, updates = walk.nodes, walk.bodies, walk.updates
    lineages = tuple(keys.lineages[event.lineage_uuid] for event in walk.events)
    disclosure = LineageDisclosure(disclosed, keys)
    disclosed.update(owner for node, owner in zip(nodes, lineages, strict=True) if node.fact is not None)
    for index, node in enumerate(nodes):
        if isinstance(node.fact, ActorChangeFact):
            nodes[index] = replace(node, fact=_disclosed_change(node.fact, disclosure))
        if isinstance(node.fact, AreaReachFact):
            nodes[index] = replace(node, fact=replace(node.fact,
                previous_reach_lineage=(node.fact.previous_reach_lineage
                    if node.fact.previous_reach_lineage in disclosed else None),
                prerequisite_destruction_lineages=tuple(key
                    for key in node.fact.prerequisite_destruction_lineages if key in disclosed)))
    # Each node's disclosed resolution, by the node's native occurrence.
    resolutions: dict[int, tuple[int, UUID | None]] = {}
    for index, (node, event) in enumerate(zip(nodes, walk.events, strict=True)):
        attributions = _content_attributions(event, node.fact, observer, disclosed, keys,
            walk.content_at_event[event.uuid])
        if attributions:
            nodes[index] = replace(node, content_attributions=attributions)
        resolution = _resolution(keys, event.resolution_ref)
        if resolution is not None and resolution[0] in disclosed:
            resolutions[node.occurrence] = resolution
    for index, row in enumerate(bodies):
        bodies[index] = _disclosed_body(row, disclosure)
    for index, row in enumerate(updates):
        updates[index] = _disclosed_update(row, disclosure)
    return tuple(nodes), lineages, tuple(bodies), tuple(updates), resolutions


def _contained_states(rows: tuple[ContainedItem, ...], value_of: Callable[[ObjectState], ObjectState]
                      ) -> tuple[ContainedItem, ...]:
    return tuple(row if (state := value_of(row.state)) is row.state else replace(row, state=state) for row in rows)


def _mapped_column(column: Column[Row] | None, value_of: Callable[[Row], Row]) -> Column[Row] | None:
    return replace(column, values=tuple(value_of(value) for value in column.values)) if column is not None else None


def _map_world_update(update: WorldUpdate, *, slots: Callable[[tuple[ItemConcentrationSlot, ...]],
                      tuple[ItemConcentrationSlot, ...]] | None = None,
                      effects: Callable[[tuple[ItemEffectPresentationState, ...]],
                      tuple[ItemEffectPresentationState, ...]] | None = None) -> WorldUpdate:
    """The update with `slots` its objects' and contained items' concentration slots and `effects` their item
    effects (an unchanged update stays itself)."""
    objects = update.objects
    if objects is not None and (slots is not None and objects.concentration_slots is not None
                                or effects is not None and objects.item_effects is not None):
        objects = replace(objects,
            concentration_slots=_mapped_column(objects.concentration_slots, slots) if slots is not None
                else objects.concentration_slots,
            item_effects=_mapped_column(objects.item_effects, effects) if effects is not None else objects.item_effects)
    if objects is update.objects and not update.contents and not update.contents_changed:
        return update

    def state_of(value: ObjectState) -> ObjectState:
        if slots is not None and value.concentration_slots:
            value = replace(value, concentration_slots=slots(value.concentration_slots))
        if effects is not None and value.item_effects:
            value = replace(value, item_effects=effects(value.item_effects))
        return value
    return replace(update, objects=objects,
        contents=tuple(replace(row, items=_contained_states(row.items, state_of)) for row in update.contents),
        contents_changed=tuple(replace(row, upserted=_contained_states(row.upserted, state_of))
            for row in update.contents_changed))


def _disclosed_update(update: WorldUpdate, disclosure: LineageDisclosure) -> WorldUpdate:
    """The update with its objects' undisclosed casting lineages cleared."""
    return _map_world_update(update, slots=lambda value: _disclosed_slots(value, disclosure))


def _public_cursor(cursors: dict[int, int], source: int | None) -> int | None:
    # Owners stamp the completed application boundary, one past its event index.
    index = cursors.get(source - 1) if source is not None else None
    return index + 1 if index is not None else None


def _public_item_effects(effects: tuple[ItemEffectPresentationState, ...], cursors: dict[int, int], *, owned: bool = False
                         ) -> tuple[ItemEffectPresentationState, ...]:
    return tuple(effect.model_copy(update={"applied_source_event_cursor": _public_cursor(cursors, effect.applied_source_event_cursor),
        "duration": effect.duration if owned else None})
                 for effect in effects)


def _public_member(member: ConditionMember, cursors: dict[int, int]) -> ConditionMember:
    state = member.state
    if state is None or state.applied_source_event_cursor is None:
        return member
    return replace(member, state=state.model_copy(update={
        "applied_source_event_cursor": _public_cursor(cursors, state.applied_source_event_cursor)}))


def _public_effects(effects: tuple[ItemEffectPresentationState, ...], cursors: dict[int, int]
                    ) -> tuple[ItemEffectPresentationState, ...]:
    """Effects with the seat's cursors (their durations were disclosed with them)."""
    return tuple(effect.model_copy(update={"applied_source_event_cursor": _public_cursor(cursors,
        effect.applied_source_event_cursor)}) if effect.applied_source_event_cursor is not None else effect
        for effect in effects)


def _public_record(record: ItemRecord, cursors: dict[int, int]) -> ItemRecord:
    return replace(record, effects=_public_effects(record.effects, cursors)) if record.effects else record


def _public_body(record: BodyRecord, cursors: dict[int, int]) -> BodyRecord:
    """A body record at the seat's occurrence, with the seat's cursors."""
    body = record.body
    return replace(record, occurrence=cursors[record.occurrence],
        body=replace(body, conditions=tuple(_public_member(row, cursors) for row in body.conditions)),
        items=tuple(_public_record(row, cursors) for row in record.items))


def _public_row(row: ChangeRow, cursors: dict[int, int]) -> ChangeRow:
    match row:
        case ConditionRow(member=ConditionMember() as member):
            return replace(row, member=_public_member(member, cursors))
        case ItemEffectsRow():
            return replace(row, effects=_public_effects(row.effects, cursors))
    return row


def _public_change(fact: ActorChangeFact, cursors: dict[int, int]) -> ActorChangeFact:
    """An actor change with the seat's cursors."""
    return replace(fact, actors=tuple(replace(change, rows=tuple(_public_row(row, cursors) for row in change.rows))
        for change in fact.actors), items=tuple(_public_record(row, cursors) for row in fact.items))


def _public_occurrences(state: "ProjectionState", keys: NativeKeys, nodes: tuple[PlayerNode, ...],
                        node_lineages: tuple[int, ...], versions: tuple[ObjectiveRow, ...],
                        bodies: tuple[BodyRecord, ...], updates: tuple[WorldUpdate, ...],
                        resolutions: Mapping[int, tuple[int, UUID | None]]
                        ) -> tuple[tuple[PlayerNode, ...], VersionRows, tuple[BodyRecord, ...], tuple[WorldUpdate, ...],
                                   tuple[PlayerResolution, ...]]:
    """Admit occurrence identities once and remove undisclosed causal links.

    The walk's native keys become the seat's: a version its occurrence index
    (assigned once, in native order), a lineage the occurrence index of its
    first admitted version. A node's resolution (`resolutions`, by native
    occurrence) becomes an index into the group's resolutions, each distinct
    one once. A node's lineage
    (`node_lineages`) is its version row's; its parent lineage is sent only
    where its group's nodes don't give it (no node of the parent's lineage
    lists it among its children).
    """
    observed_ids = {row.occurrence for row in (*bodies, *updates)}
    observed_ids.update(node.fact.creation.birth_occurrence for node in nodes
        if isinstance(node.fact, SpatialFact) and node.fact.creation is not None)
    admitted = tuple((node, owner) for node, owner in zip(nodes, node_lineages, strict=True)
        if node.fact is not None or node.content_attributions
        or node.occurrence in observed_ids or (node.combat_log is not None
            and not (node.combat_log.data.kind == "empty" and not node.combat_log.source_uuid
                and node.combat_log.entry_type is CombatLogEntryType.ACTION
                and node.combat_log.success is None)))
    admitted_nodes = tuple(node for node, _ in admitted)
    groups = {owner for _, owner in admitted}
    state.disclosed_lineages.update(groups)
    occurrences, lineages = [], []
    for row in versions:
        lineage = keys.lineages[row.lineage_uuid]
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
    stages: dict[int | None, list[int]] = {}
    for node in admitted_nodes:
        if isinstance(node.fact, AreaReachFact):
            stages.setdefault(node.parent_lineage, []).append(node.fact.stage_index)
    owners = []
    for node, owner in admitted:
        owners.append(state.public_lineages[owner])
        fact = node.fact
        if isinstance(fact, AreaReachFact):
            fact = replace(fact, stage_index=sorted(set(stages[node.parent_lineage])).index(fact.stage_index),
                previous_reach_lineage=lineage(fact.previous_reach_lineage),
                prerequisite_destruction_lineages=tuple(public for key in fact.prerequisite_destruction_lineages
                    if (public := lineage(key)) is not None))
        elif isinstance(fact, SpatialFact):
            fact = replace(fact, commit_occurrence=version(fact.commit_occurrence),
                creation=replace(fact.creation, birth_occurrence=state.public_cursors[fact.creation.birth_occurrence])
                    if fact.creation is not None else None)
        elif isinstance(fact, ActionFact) and fact.reaction is not None:
            fact = replace(fact, reaction=replace(fact.reaction, triggered_lineage=lineage(fact.reaction.triggered_lineage)))
        elif isinstance(fact, ActorChangeFact):
            fact = _public_change(fact, state.public_cursors)
        elif isinstance(fact, AttackFact):
            fact = replace(fact, item_effects=_public_item_effects(fact.item_effects, state.public_cursors,
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
            parent_event=version(node.parent_event),
            parent_lineage=lineage(node.parent_lineage),
            children_lineages=tuple(state.public_lineages[key] for key in node.children_lineages if key in groups),
            turn_execution_id=node.turn_execution_id if node.turn_execution_id in state.disclosed_turns else None,
            content_attributions=attributions, resolution=resolution(node.occurrence)))
    # A parent the group's own nodes give (the parent lists this lineage) is not restated.
    children_of: dict[int, set[int]] = {}
    for node, owner in zip(result, owners, strict=True):
        children_of.setdefault(owner, set()).update(node.children_lineages)
    result = [replace(node, parent_lineage=None) if node.parent_lineage is not None
              and owner in children_of.get(node.parent_lineage, ()) else node
              for node, owner in zip(result, owners, strict=True)]
    bodies = tuple(_public_body(row, state.public_cursors) for row in bodies)
    updates = tuple(_map_world_update(replace(row, occurrence=state.public_cursors[row.occurrence]),
        effects=lambda value: _public_item_effects(value, state.public_cursors)) for row in updates)
    return (tuple(result), VersionRows(occurrences=tuple(occurrences), lineages=tuple(lineages)), bodies, updates,
            tuple(resolution_rows))


@dataclass(slots=True)
class SessionProjection:
    """What the seats of one session share in projection, written only by the walk drivers.

    The native keys of every walked version (its cursor) and lineage (its first version's cursor), and the
    session's world and actor folds: the recorded after-values of every walked event (the actors' from their
    births and E2's actor change records), read as of the event by every seat. A walk group is walked once
    (`walked`, its first version), in source order; roots whose versions interleave are one group
    (`capture_context`), so the folds take every change in native order.
    """

    versions: dict[UUID, int] = field(default_factory=dict)
    lineages: dict[UUID, int] = field(default_factory=dict)
    world: WorldFacts = field(default_factory=WorldFacts)
    # The digest of each tile's current value, filled by the publications, forgotten by `_fold_version`'s writes.
    tile_digests: TileDigests = field(default_factory=TileDigests)
    actors: dict[UUID, ActorState] = field(default_factory=dict)
    # Every born actor's name, never popped: the names a seat's combat log may show (its bodies').
    names: dict[UUID, str] = field(default_factory=dict)
    # The content id of every visual loadout a body entered with, by value (a memo: each value digested once).
    loadout_ids: dict[VisualLoadout, str] = field(default_factory=dict)
    walked: set[UUID] = field(default_factory=set)


@dataclass(slots=True)
class ProjectionState:
    """One seat's projection: its knowledge (control, perception, the world objects it observes and the contents
    it sees, what it was sent, its numbering). It holds no bodies, items or world: it reads the session's
    (`SessionProjection.world`, `.actors`). It holds no client state: its perception is its composition, and its
    spatial commit order is kept by the client's rule (`commit_current`).
    """

    generation: UUID
    observer_uuid: UUID
    # The seat's control and observers.
    audience: PlayerAudience
    # The static content the seat was sent, updated from each emitted group.
    static_sent: StaticSent = field(default_factory=StaticSent)
    # The digest of each world record as the seat holds it, updated from each emitted group.
    world_stamps: WorldStamps = field(default_factory=WorldStamps)
    # The digest of each body as the seat holds it (`world_stamps`' rule): its record as last sent whole, until a
    # change the seat is sent drops it.
    body_stamps: dict[UUID, int] = field(default_factory=dict)
    # Disclosed lineages, by their native key (`NativeKeys.lineages`).
    disclosed_lineages: set[int] = field(default_factory=set)
    public_versions: dict[UUID, int] = field(default_factory=dict)
    # Each disclosed lineage's public index, by its native key.
    public_lineages: dict[int, int] = field(default_factory=dict)
    public_cursors: dict[int, int] = field(default_factory=dict)
    disclosed_turns: set[UUID] = field(default_factory=set)
    owned_spatial_effects: set[UUID] = field(default_factory=set)
    # Each entity's last committed spatial transition (`commit_current`), as the client keeps it.
    spatial_commit_cursors: dict[UUID, int] = field(default_factory=dict)
    next_occurrence: int = 0
    next_log_append: int = 0
    # The world objects the seat observes now, and the containers whose contents it sees now.
    observed_objects: set[UUID] = field(default_factory=set)
    granted_containers: set[UUID] = field(default_factory=set)
    audience_composition: AudienceComposition = field(default_factory=AudienceComposition)


def _sensory_rows(nodes: tuple[PlayerNode, ...], table: SensoryTable, observers: int
                  ) -> tuple[tuple[PlayerNode, ...], SensoryRows]:
    """The group's sensory rows and its facts naming them: the walk's table, and the cell tables of the facts'
    cell lists, each distinct row once (`shared_cells`, `shared_values`). A seat with one observer leaves out the
    member columns."""
    sensory = [(at, node.fact) for at, node in enumerate(nodes) if isinstance(node.fact, SensoryFact)]
    if len(sensory) != len(table.cells):
        raise ValueError("Every sensory fact a walk builds is admitted, once")
    cells, cell_bits = shared_cells([mask for row in table.cells for mask in (row.visible_added, row.visible_removed)])
    # A cell coming into view reads zero without a value (`zeros_left_out`).
    light_levels, light_bits = shared_values([zeros_left_out(row.light_changed, row.visible_added) for row in table.cells])
    hazards, hazard_bits = shared_values([zeros_left_out(row.hazards_changed, row.visible_added) for row in table.cells])
    result = list(nodes)
    for number, (at, fact) in enumerate(sensory):
        result[at] = replace(nodes[at], fact=replace(fact, visible_cells_added=cell_bits[2 * number],
            visible_cells_removed=cell_bits[2 * number + 1], effective_light_levels_changed=light_bits[number],
            hazardous_cells_changed=hazard_bits[number]))
    several = observers > 1
    contacts = table.contacts
    return tuple(result), SensoryRows(uuids=tuple(table.uuids), contact_uuid_index=tuple(table.contact_uuid_index),
        contact_positions=tuple(row.position for row in contacts), contact_visual=flag_bits([row.visual for row in contacts]),
        contact_special_senses=tuple(row.special_senses for row in contacts)
            if any(row.special_senses for row in contacts) else (),
        contact_members=tuple(table.contact_members) if several else (),
        sighting_uuid_index=tuple(table.sighting_uuid_index), sightings=tuple(table.sightings),
        sighting_members=tuple(table.sighting_members) if several else (),
        patch_uuid_index=tuple(table.patch_uuid_index), sighting_patches=tuple(table.sighting_patches),
        retired_uuid_index=tuple(table.retired_uuid_index), retired_cells=tuple(table.retired_cells),
        light_sources=tuple(table.light_sources), light_patches=tuple(table.light_patches), cells=cells,
        light_levels=light_levels, hazards=hazards)


def _merge_sent(state: "ProjectionState", walk: SeatWalk) -> None:
    """The emitted group's static rows join what the seat was sent, and its stamp changes the seat's stamps."""
    sent = state.static_sent
    sent.actor_births.update(row.actor_uuid for row in walk.bodies)
    merge_static_sent(sent, walk.pending)
    merge_world_stamps(state.world_stamps, walk.stamps)
    for identity, digest in walk.body_stamps.items():
        if digest is None:
            state.body_stamps.pop(identity, None)
        else:
            state.body_stamps[identity] = digest


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

    if any(row.generation != state.generation or row.observer_uuid != state.observer_uuid for row in appends):
        raise ValueError("Log appends belong to another audience or generation")
    public_logs = tuple(replace(row, encounter_log_index=state.next_log_append + index,
        operation_end_cursor=boundary(row.operation_end_cursor)) for index, row in enumerate(appends))
    state.next_log_append += len(public_logs)
    return public_logs


def known_connector_uuids(session: SessionProjection, state: ProjectionState) -> frozenset[str]:
    """The connectors the seat sees now, both endpoints in its composed view: those its combat log may name.

    The seat's world updates send each connector whose endpoints enter its view and each one written while it
    sees it, so its client holds every one of these (and may keep others it saw before, by memory).
    """
    view = state.audience_composition.view
    if view is None:
        return frozenset()
    return frozenset(str(row.connector_uuid) for row in session.world.connectors.values()
        if all(cell_in(view.visible, point) for point in row.endpoints))


def begin_projections(session: SessionProjection, initializations: tuple[IntervalEnvelope, ...]
                      ) -> tuple[tuple[ProjectionState, PlayerInitialization], ...]:
    """Start the seats' projections from their recorded initializations; no native queries.

    The seats share the startup interval: its completed versions (`world_interval`) are walked once, in cursor
    order, folding the session world, each seat stepping on the versions it admitted.
    """
    if not initializations:
        return ()
    versions, interval = initializations[0].objective_rows, initializations[0].world_interval
    if any(row.objective_rows != versions or row.world_interval != interval for row in initializations[1:]):
        raise ValueError("A session's seats start from one recorded interval")
    group = _walk_group(session, versions)
    shared = dict(interval.events)
    conditions = {row.event_uuid: row for row in interval.conditions}
    changes = interval.actor_fact_changes
    states: list[ProjectionState] = []
    worlds: list[PlayerWorld] = []
    walks: list[SeatWalk] = []
    for initialization in initializations:
        world_event = next((event for _, event in initialization.admitted if isinstance(event, WorldInitializedEvent)), None)
        if world_event is None:
            raise ValueError("player projection requires recorded world initialization")
        world = PlayerWorld(battlefield_id=world_event.battlefield_id, battlefield_name=world_event.battlefield_name,
            bounds=world_event.bounds, width=world_event.width, height=world_event.height)
        if group.indexes[world_event.uuid] not in shared:
            raise ValueError("A seat's admitted world is part of the session's recorded startup world")
        audience = resolve_audience(initialization.observer_uuid, initialization.audience)
        state = ProjectionState(initialization.generation, initialization.observer_uuid, audience)
        # The seat's own effects, known before its walk shows them (their durations are disclosed to it).
        state.owned_spatial_effects.update(event.spatial_effect_uuid for _, event in initialization.admitted
            if isinstance(event, SpatialEffectChangeEvent) and audience.controls(event.source_entity_uuid))
        states.append(state)
        worlds.append(world)
        walks.append(_begin_walk(group, state, tuple(event for _, event in initialization.admitted),
            initialization.conditions, changes, initialization.logs, {}, session.names, NO_LOG_INPUTS,
            SharedLogEntries()))
    steps: dict[int, list[tuple[int, Event]]] = {}
    for seat, walk in enumerate(walks):
        for event in walk.events:
            steps.setdefault(group.indexes[event.uuid], []).append((seat, event))
    folded: dict[UUID, AppliedWorldFact | None] = {}
    for index in sorted(steps.keys() | shared.keys()):
        event = shared[index]
        condition = conditions.get(event.uuid)
        due = steps.get(index, ())
        for seat, row in due:
            _enter_event(walks[seat], states[seat], session.world, row)
        step = _fold_actors(session.actors, session.names, folded, event, changes, condition)
        applied = _fold_version(session, folded, event, condition)
        for seat, row in due:
            _leave_event(walks[seat], group, states[seat], session.world, session.tile_digests,
                         session.actors, session.loadout_ids, row, applied, folded, step)
    return tuple(_emit_initialization(group, state, initialization, walk, world)
        for state, initialization, walk, world in zip(states, initializations, walks, worlds, strict=True))


def _emit_initialization(group: WalkGroup, state: ProjectionState, initialization: IntervalEnvelope, walk: SeatWalk,
                         world: PlayerWorld) -> tuple[ProjectionState, PlayerInitialization]:
    nodes, node_lineages, bodies, updates, resolutions = _end_walk(walk, group, state)
    nodes, rows, bodies, updates, resolution_rows = _public_occurrences(state, group.keys, nodes, node_lineages,
        group.versions, bodies, updates, resolutions)
    nodes, sensory_rows = _sensory_rows(nodes, walk.table, len(state.audience.observers))
    _merge_sent(state, walk)
    return state, PlayerInitialization(generation=initialization.generation, observer_uuid=initialization.observer_uuid,
        world=world, nodes=nodes, version_rows=rows, end_cursor=state.next_occurrence,
        bodies=bodies, world_updates=updates, audience=state.audience, sensory_rows=sensory_rows,
        resolutions=resolution_rows)


def begin_projection(session: SessionProjection, initialization: IntervalEnvelope
                     ) -> tuple[ProjectionState, PlayerInitialization]:
    """One seat's `begin_projections`."""
    return begin_projections(session, (initialization,))[0]


def project_lineages(session: SessionProjection, states: tuple[ProjectionState, ...],
                     lineages: tuple[CompletedLineage, ...], log_inputs: tuple[SeatLogInputs, ...] | None = None
                     ) -> tuple[PlayerLineage | None, ...]:
    """Advance the seats' private projection memory over one closed root, captured for each seat.

    The root's events are walked once, each event stepping every seat with its own retained body. `log_inputs`
    are each seat's, as of the operation's start (none for a recorded sequence).
    """
    for state, lineage in zip(states, lineages, strict=True):
        if (state.generation != lineage.generation or state.observer_uuid != lineage.observer_uuid
                or state.audience != resolve_audience(lineage.observer_uuid, lineage.audience)):
            raise ValueError("recorded lineage belongs to another projection")
    if not lineages:
        return ()
    versions = lineages[0].objective_rows
    if any(lineage.objective_rows is not versions and lineage.objective_rows != versions for lineage in lineages[1:]):
        raise ValueError("The seats of one root walk its one group")
    start_cursors = tuple(state.next_occurrence for state in states)
    for state, lineage in zip(states, lineages):
        state.owned_spatial_effects.update(event.spatial_effect_uuid for event in lineage.events
            if isinstance(event, SpatialEffectChangeEvent) and state.audience.controls(event.source_entity_uuid))
    group = _walk_group(session, versions)
    inputs = log_inputs if log_inputs is not None else tuple(NO_LOG_INPUTS for _ in states)
    shared_logs = SharedLogEntries()
    walks = tuple(_begin_walk(group, state, upgrade_recorded_resolutions(lineage.events),
        lineage.conditions, lineage.actor_fact_changes, {}, lineage.native_logs, session.names, seat_inputs,
        shared_logs)
        for state, lineage, seat_inputs in zip(states, lineages, inputs, strict=True))
    order = tuple(event.uuid for event in walks[0].events)
    if any(tuple(event.uuid for event in walk.events) != order for walk in walks[1:]):
        raise ValueError("The seats of one root walk its events in one order")
    # A change an observer saw before it completed folds at its own (observed) version, before the walk passes it.
    sources = iter(sorted(lineages[0].observed_sources, key=lambda row: group.indexes[row.uuid]))
    source = next(sources, None)
    folded: dict[UUID, AppliedWorldFact | None] = {}
    for position in range(len(order)):
        # Every seat's body of a version the world fold reads is the one shared retained body (a seat's own
        # body differs only for a sensory version, which writes no world).
        event = walks[0].events[position]
        while source is not None and group.indexes[source.uuid] < group.indexes[event.uuid]:
            _fold_version(session, folded, source, None)
            source = next(sources, None)
        condition = walks[0].facts.get(event.uuid)
        for walk, state in zip(walks, states):
            _enter_event(walk, state, session.world, walk.events[position])
        step = _fold_actors(session.actors, session.names, folded, event, walks[0].actor_fact_changes, condition)
        applied = _fold_version(session, folded, event, condition)
        for walk, state in zip(walks, states):
            _leave_event(walk, group, state, session.world, session.tile_digests, session.actors,
                         session.loadout_ids, walk.events[position], applied, folded, step)
    return tuple(_emit_lineage(group, state, lineage, walk, start_cursor)
        for state, lineage, walk, start_cursor in zip(states, lineages, walks, start_cursors))


def _emit_lineage(group: WalkGroup, state: ProjectionState, lineage: CompletedLineage, walk: SeatWalk,
                  start_cursor: int) -> PlayerLineage | None:
    nodes, node_lineages, bodies, updates, resolutions = _end_walk(walk, group, state)
    # Settled initialization needs resulting state only. Presenting a damage
    # operation additionally requires recorded causal ownership, or an explicit
    # current-format unknown owner; old missing fields cannot establish either.
    native_events = {group.keys.versions[event.uuid]: event for event in lineage.events}
    for node in nodes:
        event = native_events[node.occurrence]
        if (isinstance(node.fact, DamageRequestFact) and node.occurrence not in resolutions
                and "resolution_ref" in event._recorded_omissions):
            legacy_damage_reference(event.uuid, event.lineage_uuid, event.parent_lineage, is_request=True)
    if not bodies and not updates and not any(node.fact is not None or node.combat_log is not None
                                              or node.content_attributions for node in nodes):
        return None
    nodes, rows, bodies, updates, resolution_rows = _public_occurrences(state, group.keys, nodes, node_lineages,
        group.versions, bodies, updates, resolutions)
    if not nodes and not bodies and not updates:
        return None
    nodes, sensory_rows = _sensory_rows(nodes, walk.table, len(state.audience.observers))
    _merge_sent(state, walk)
    root_occurrence = state.public_cursors.get(group.keys.versions[lineage.root.uuid])
    root = next((index for index, node in enumerate(nodes) if node.occurrence == root_occurrence), None)
    return PlayerLineage(lineage=rows.lineages[rows.occurrences.index(nodes[root].occurrence)] if root is not None
        else rows.lineages[0],
        root=root, events=nodes, version_rows=rows, start_cursor=start_cursor,
        end_cursor=state.next_occurrence, bodies=bodies, world_updates=updates,
        sensory_rows=sensory_rows, resolutions=resolution_rows)


def project_lineage(session: SessionProjection, state: ProjectionState, lineage: CompletedLineage
                    ) -> PlayerLineage | None:
    """One seat's `project_lineages`."""
    return project_lineages(session, (state,), (lineage,))[0]
