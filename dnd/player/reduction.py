"""Reduce and stage saved player packets without native event projection."""

from dataclasses import dataclass, replace
import json
from types import MappingProxyType
from typing import Collection, Iterator, Mapping
from dnd.types.actor import SpatialDisposition
from dnd.core.sensory_fold import copy_senses_snapshot
from dnd.core.effect_types import ResolutionRef
from uuid import UUID

from dnd.core.condition_types import ConditionCategory
from dnd.core.content.descriptors import ContentDescriptor
from dnd.types.cells import CellMask, CellValues
from dnd.types.event_facts import EventType, SpatialChangeType
from dnd.types.senses import PerceivedContact, PerceivedLightSource, PerceivedSpatialEffect, SenseMode, SensoryDelta
from dnd.player.audience import (AudienceComposition, apply_current_audience, audience_view,
    begin_audience_composition, observe_audience, resolve_audience)
from dnd.player.facts import (
    AttackFact, ConditionChangeFact, ConditionFact, DamageRequestFact, DamageResultFact, ObjectDamageFact, EquipmentFact, HealFact, ItemChargeFact, ItemPatch, LifeFact, PlayerItem,
    ActorChanges, PlayerActor, PlayerCharacterSheet, PlayerFact, SheetChanges, PlayerHUDPatch, PlayerHUDSnapshot, PlayerInitialization, PlayerLineage, PlayerNode, PlayerObservation, PlayerSequence,
    PlayerState, PlayerUpdate, SensoryFact, SensoryRows, SpatialEffectContent, SpatialFact, TurnFact, VersionRow,
    WorldUpdate, TemporaryHitPointsFact, FactionFact, joined_effect,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SensoryChanges:
    """A received sensory fact with its group's rows resolved: the client's `SensoryDelta`.

    Not a wire value and never stored; `sensory_changes` builds it once per
    folded fact. (The projector folds the native event it projects.)
    """

    observer_uuid: UUID
    initial: bool
    observer_position: tuple[int, int]
    observer_position_changed: bool
    visible_cells_added: CellMask
    visible_cells_removed: CellMask
    seen_cells_added: CellMask
    effective_light_levels_changed: CellValues
    hazardous_cells_changed: CellValues
    entity_contacts_changed: Mapping[UUID, PerceivedContact]
    entity_contacts_removed: frozenset[UUID]
    object_contacts_changed: Mapping[UUID, PerceivedContact]
    object_contacts_removed: frozenset[UUID]
    spatial_effects_changed: Mapping[UUID, PerceivedSpatialEffect]
    spatial_effects_removed: frozenset[UUID]
    # The static content this fact delivers; the seat holds every other changed effect's.
    spatial_effect_content: Mapping[UUID, SpatialEffectContent]
    light_sources_changed: Mapping[UUID, PerceivedLightSource]
    light_sources_removed: Mapping[UUID, int]
    sense_modes_changed: bool
    sense_modes: tuple[SenseMode, ...] | None
    passive_perception_changed: bool
    passive_perception: int | None
    visual_access_changed: bool
    visual_access: int | None
    paths_dirty: bool


# What the fold applies: a received fact, a sensory fact with its group's rows resolved.
FoldedFact = PlayerFact | SensoryChanges


@dataclass(frozen=True, slots=True)
class PlayerCausalIndex:
    """References into one received group, in its commit (occurrence) order."""
    by_lineage: Mapping[int, PlayerNode]
    by_occurrence: Mapping[int, PlayerNode]
    owned: Mapping[ResolutionRef, tuple[PlayerNode, ...]]
    results: Mapping[ResolutionRef, tuple[PlayerNode, ...]]
    damage_requests: Mapping[int, int]


def index_player_lineage(lineage: PlayerLineage) -> PlayerCausalIndex:
    owned: dict[ResolutionRef, list[PlayerNode]] = {}
    results: dict[ResolutionRef, list[PlayerNode]] = {}
    by_lineage = {row.lineage: row for row in lineage.events}
    damage_requests: dict[int, int] = {}
    for node in lineage.events:
        ancestors: list[int] = []
        current = node
        while current.lineage not in ancestors:
            ancestors.append(current.lineage)
            request = (current.lineage if isinstance(current.fact, DamageRequestFact)
                       else damage_requests.get(current.lineage))
            if request is not None:
                damage_requests.update((identity, request) for identity in ancestors)
                break
            parent = by_lineage.get(current.parent_lineage) if current.parent_lineage is not None else None
            if parent is None:
                break
            current = parent
    for node in sorted(lineage.events, key=lambda row: row.occurrence):
        reference = node.resolution_ref
        if reference is None:
            continue
        owned.setdefault(reference, []).append(node)
        if not node.canceled and isinstance(node.fact, (DamageResultFact, ObjectDamageFact)):
            results.setdefault(reference, []).append(node)
    return PlayerCausalIndex(
        MappingProxyType(by_lineage),
        MappingProxyType({row.occurrence: row for row in lineage.events}),
        MappingProxyType({key: tuple(rows) for key, rows in owned.items()}),
        MappingProxyType({key: tuple(rows) for key, rows in results.items()}),
        MappingProxyType(damage_requests))


# These received families have ordinary state presentation, without a separate
# actor cue. This describes the reducer below; it is not a second dispatcher.
STATE_PRESENTATION_KINDS = frozenset({
    "temporary_hit_points", "spatial", "turn", "sensory", "item_charge", "faction",
})


def copy_target(target: PlayerState) -> PlayerState:
    senses = target.senses
    return replace(target, tiles=dict(target.tiles), objects=dict(target.objects), actors=dict(target.actors),
        items=dict(target.items), spatial_content=dict(target.spatial_content),
        spatial_commit_cursors=dict(target.spatial_commit_cursors),
        senses=None if senses is None else copy_senses_snapshot(senses),
        perception=replace(target.perception,
            members={identity: copy_senses_snapshot(value) for identity, value in target.perception.members.items()},
            contact_cursors=dict(target.perception.contact_cursors),
            effect_cursors=dict(target.perception.effect_cursors),
            effect_absences=dict(target.perception.effect_absences)))


def apply_world_update(target: PlayerState, update: WorldUpdate) -> None:
    target.tiles.update((row.position, row) for row in update.tiles)
    for row in update.tile_changes:
        previous = target.tiles.get(row.position)
        if previous is None:
            raise ValueError("Tile field update requires an already known tile")
        target.tiles[row.position] = previous.model_copy(update=row.changes)
    for identity in update.objects_removed:
        target.objects.pop(identity, None)
    target.objects.update((row.item.item_uuid, row) for row in update.objects)
    target.connectors = update.connectors


def observed_actor(previous: PlayerActor | None, observation: PlayerObservation) -> PlayerActor:
    """The body after an observation's patch; against an absent body the patch is complete."""
    if previous is None:
        if observation.changes.keys() != ActorChanges.__optional_keys__:
            raise ValueError("A first observation must carry the whole body")
        return PlayerActor(uuid=observation.actor_uuid, **observation.changes)
    return replace(previous, **observation.changes)


def apply_item_patches(target: PlayerState, patches: tuple[ItemPatch, ...]) -> None:
    """A patch's components replace the seat's; against an absent record it carries the look."""
    for patch in patches:
        previous = target.items.get(patch.item_uuid)
        if previous is None:
            if patch.look is None:
                raise ValueError("An item's first record requires its look")
            target.items[patch.item_uuid] = PlayerItem(look=patch.look, profile=patch.profile, state=patch.state)
        else:
            target.items[patch.item_uuid] = PlayerItem(
                look=patch.look if patch.look is not None else previous.look,
                profile=patch.profile if patch.profile is not None else previous.profile,
                state=patch.state if patch.state is not None else previous.state)


def observe_body(target: PlayerState, observation: PlayerObservation) -> bool:
    """Apply an observation's body and item patches; False if a terminal lifetime ignores it."""
    previous = target.actors.get(observation.actor_uuid)
    if previous is not None and not previous.present:
        return False  # A later retained observation cannot resurrect a terminal lifetime.
    target.actors[observation.actor_uuid] = observed_actor(previous, observation)
    apply_item_patches(target, observation.items)
    return True


def _observe(target: PlayerState, observation: PlayerObservation, *,
             audience_composition: AudienceComposition | None = None) -> None:
    if not observe_body(target, observation):
        return
    if observation.contact is not None and target.senses is not None:
        target.senses.entities[observation.actor_uuid] = observation.contact
        if audience_composition is not None:
            audience_composition.contact_overrides.add(observation.actor_uuid)


def stage_actors(target: PlayerState, observations: tuple[PlayerObservation, ...]) -> PlayerState:
    """Supply absent bodies for binding; existing historical actors win."""
    result = copy_target(target)
    for observation in observations:
        if observation.actor_uuid not in result.actors:
            _observe(result, observation)
    return result


def stage_lineage(target: PlayerState, lineage: PlayerLineage) -> PlayerState:
    """Supply absent binding contacts without advancing known world geometry."""
    if (target.generation != lineage.generation or target.observer_uuid != lineage.observer_uuid
            or target.viewing_audience != resolve_audience(lineage.observer_uuid, lineage.audience)):
        raise ValueError("player lineage belongs to a different observer or generation")
    result = stage_actors(target, lineage.observations)
    connectors = {row.connector_uuid: row for row in result.connectors}
    for update in lineage.world_updates:
        for tile in update.tiles:
            result.tiles.setdefault(tile.position, tile)
        for obj in update.objects:
            result.objects.setdefault(obj.item.item_uuid, obj)
        for connector in update.connectors:
            connectors.setdefault(connector.connector_uuid, connector)
    result.connectors = tuple(connectors.values())
    return result


def _unique(values: dict, indices: tuple[int, ...]) -> dict:
    if len(values) != len(indices):
        raise ValueError("A sensory fact names two rows of one identity in one list")
    return values


def sensory_changes(fact: SensoryFact, rows: SensoryRows, held: Mapping[UUID, SpatialEffectContent]) -> SensoryChanges:
    """A received sensory fact with its group's rows resolved; a sighting's content is the fact's, else the seat's (`held`).

    An index outside its column raises IndexError, a list naming one identity twice ValueError.
    """
    uuids = rows.uuids

    def contacts(indices: tuple[int, ...]) -> dict[UUID, PerceivedContact]:
        return _unique({uuids[rows.contact_uuid_index[index]]: rows.contacts[index] for index in indices}, indices)

    def identities(indices: tuple[int, ...]) -> frozenset[UUID]:
        return frozenset(_unique(dict.fromkeys(uuids[index] for index in indices), indices))
    effects = {}
    for index in fact.spatial_effect_sightings:
        identity = uuids[rows.sighting_uuid_index[index]]
        content = fact.spatial_effect_content[identity] if identity in fact.spatial_effect_content else held[identity]
        effects[identity] = joined_effect(rows.sightings[index], content)
    return SensoryChanges(observer_uuid=fact.observer_uuid, initial=fact.initial,
        observer_position=fact.observer_position, observer_position_changed=fact.observer_position_changed,
        visible_cells_added=fact.visible_cells_added, visible_cells_removed=fact.visible_cells_removed,
        seen_cells_added=fact.seen_cells_added, effective_light_levels_changed=fact.effective_light_levels_changed,
        hazardous_cells_changed=fact.hazardous_cells_changed,
        entity_contacts_changed=contacts(fact.entity_contacts_changed),
        entity_contacts_removed=identities(fact.entity_contacts_removed),
        object_contacts_changed=contacts(fact.object_contacts_changed),
        object_contacts_removed=identities(fact.object_contacts_removed),
        spatial_effects_changed=_unique(effects, fact.spatial_effect_sightings),
        spatial_effects_removed=identities(fact.spatial_effects_removed),
        spatial_effect_content=fact.spatial_effect_content,
        light_sources_changed=_unique({rows.light_sources[index].source_uuid: rows.light_sources[index]
            for index in fact.light_sources_changed}, fact.light_sources_changed),
        light_sources_removed=_unique({uuids[rows.light_removal_uuid_index[index]]: rows.light_removal_revisions[index]
            for index in fact.light_sources_removed}, fact.light_sources_removed),
        sense_modes_changed=fact.sense_modes_changed, sense_modes=fact.sense_modes,
        passive_perception_changed=fact.passive_perception_changed, passive_perception=fact.passive_perception,
        visual_access_changed=fact.visual_access_changed, visual_access=fact.visual_access, paths_dirty=fact.paths_dirty)


def folded_fact(fact: PlayerFact, rows: SensoryRows, held: Mapping[UUID, SpatialEffectContent]) -> FoldedFact:
    """What the fold applies for a received fact of a group with `rows`: a sensory fact resolved, any other as it is."""
    return sensory_changes(fact, rows, held) if isinstance(fact, SensoryFact) else fact


def apply_player_fact(target: PlayerState, fact: FoldedFact, *, source_cursor: int | None = None,
                      audience_composition: AudienceComposition | None = None) -> None:
    """Fold an already-disclosed committed fact into player memory: its senses and turn part, then its bodies' part."""
    apply_sensed_fact(target, fact, target.actors, source_cursor=source_cursor,
        audience_composition=audience_composition)
    apply_record_fact(target, fact)


def apply_sensed_fact(target: PlayerState, fact: FoldedFact, known: Collection[UUID], *,
                      source_cursor: int | None = None,
                      audience_composition: AudienceComposition | None = None) -> None:
    """The senses and turn part of a committed fact; `known` are the actors the fold has bodies for."""
    match fact:
        case SpatialFact():
            if fact.terminal_departure and fact.entity_uuid is not None and fact.entity_uuid in known:
                if target.senses is not None:
                    target.senses.entities.pop(fact.entity_uuid, None)
                    if audience_composition is not None:
                        audience_composition.contact_overrides.add(fact.entity_uuid)
            elif (target.viewing_audience.controls(fact.entity_uuid)
                    and fact.change_type is SpatialChangeType.ENTITY_ENTERED
                    and target.senses is not None and fact.entity_uuid == target.observer_uuid):
                # Own entry is an explicit permitted contact even when one
                # sensory batch folds an arrival and return to the same cell.
                target.senses = replace(target.senses, position=fact.position)
        case SensoryChanges():
            fold_senses(target, fact, cursor=target.reducer_cursor if source_cursor is None else source_cursor,
                audience_composition=audience_composition)
        case SensoryFact():
            raise ValueError("A sensory fact is folded with its group's rows resolved (sensory_changes)")
        case TurnFact():
            if fact.round_number is not None:
                target.round_number = fact.round_number
            if fact.event_type in (EventType.TURN_START, EventType.TURN_END, EventType.ENCOUNTER_END):
                target.current_actor_uuid = fact.entity_uuid if fact.event_type is EventType.TURN_START else None


def fold_senses(target: PlayerState, delta: SensoryDelta, *, cursor: int,
                audience_composition: AudienceComposition | None) -> None:
    """Fold one member's sensory after-values into the seat's perception and its composed view."""
    if audience_composition is None:
        target.perception = observe_audience(target.perception, target.viewing_audience, delta, cursor)
        target.senses = audience_view(target.perception, target.observer_uuid)
    else:
        apply_current_audience(audience_composition, target.viewing_audience, target.observer_uuid, delta, cursor)
        target.perception, target.senses = audience_composition.perception, audience_composition.view


def apply_record_fact(target: PlayerState, fact: FoldedFact) -> None:
    """The records' part of a committed fact: it changes `target.actors`, `target.items` and `target.spatial_content` only."""
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
                if fact.item_uuid in actor.controlled_items:
                    del target.items[fact.item_uuid]
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
        case SensoryFact():
            raise ValueError("A sensory fact is folded with its group's rows resolved (sensory_changes)")
        case SensoryChanges():
            target.spatial_content.update(fact.spatial_effect_content)
            if fact.observer_position_changed and fact.observer_uuid in target.actors:
                target.actors[fact.observer_uuid] = replace(target.actors[fact.observer_uuid], last_visual_position=fact.observer_position)
            for identity, contact in fact.entity_contacts_changed.items():
                if contact.visual and identity in target.actors and target.actors[identity].present:
                    target.actors[identity] = replace(target.actors[identity], last_visual_position=contact.position)
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
        case EquipmentFact():
            actor = target.actors[fact.source_entity_uuid]
            target.actors[actor.uuid] = replace(actor, **fact.changes)
            apply_item_patches(target, fact.items)
        case ConditionChangeFact():
            actor = target.actors[fact.target_entity_uuid]
            condition = fact.condition
            members = {row.condition_uuid: row for row in actor.conditions}
            change_membership(members, fact)
            target.actors[actor.uuid] = replace(actor, conditions=tuple(members.values()),
                spatial_disposition=(condition.resulting_stats.spatial_disposition
                    if condition.resulting_stats is not None else actor.spatial_disposition),
                normal_hp=(condition.resulting_stats.normal_hp
                    if condition.resulting_stats is not None else actor.normal_hp),
                maximum_hp=(condition.resulting_stats.maximum_hp if condition.resulting_stats is not None else
                    actor.maximum_hp if condition.resulting_max_hp is None else condition.resulting_max_hp),
                armor_class=(condition.resulting_stats.armor_class if condition.resulting_stats is not None else
                    actor.armor_class if condition.resulting_ac is None else condition.resulting_ac),
                resolved_size=(condition.resulting_stats.resolved_size
                    if condition.resulting_stats is not None and condition.resulting_stats.resolved_size is not None
                    else actor.resolved_size))


def commit_current(target: PlayerState, fact: FoldedFact, *, source_cursor: int,
                   occurrences: Collection[int]) -> bool:
    """Record a spatial transition's commit; False if a nested commit supersedes it (it is then not folded)."""
    if (isinstance(fact, SpatialFact) and fact.entity_uuid is not None
            and fact.change_type in (SpatialChangeType.ENTITY_ENTERED, SpatialChangeType.ENTITY_LEFT)):
        if fact.commit_occurrence is None or fact.commit_occurrence not in occurrences:
            raise ValueError(f"Spatial change at cursor {source_cursor} lacks its recorded commit version")
        committed_at = fact.commit_occurrence
        # Only a nested commit supersedes this closing transition. Independent
        # earlier transitions may be retimed (e.g. jump after preflight OAs).
        if committed_at < target.spatial_commit_cursors.get(fact.entity_uuid, -1) < source_cursor:
            return False
        target.spatial_commit_cursors[fact.entity_uuid] = committed_at
    return True


def change_membership(members: dict[UUID, ConditionFact], fact: ConditionChangeFact) -> None:
    """A condition fact's effect on its target's memberships: a removal ends one, an internal condition is never held."""
    if fact.event_type is EventType.CONDITION_REMOVAL:
        members.pop(fact.condition.condition_uuid, None)
    elif fact.condition.category is not ConditionCategory.INTERNAL:
        members[fact.condition.condition_uuid] = fact.condition


def apply_committed_player_fact(target: PlayerState, fact: FoldedFact, *, source_cursor: int,
                               occurrences: Collection[int],
                               audience_composition: AudienceComposition | None = None) -> None:
    """Fold a committed fact without letting an outer move undo nested arrival."""
    if commit_current(target, fact, source_cursor=source_cursor, occurrences=occurrences):
        apply_player_fact(target, fact, source_cursor=source_cursor, audience_composition=audience_composition)


def reduce_nodes(target: PlayerState, nodes: tuple[PlayerNode, ...], versions: tuple[VersionRow, ...],
            observations: tuple[PlayerObservation, ...], updates: tuple[WorldUpdate, ...], rows: SensoryRows) -> PlayerState:
    """Fold received values in source order, including a timed partial group."""
    result = copy_target(target)
    _apply_nodes(result, nodes, versions, observations, updates, rows)
    return result


def occurrence_order(nodes: tuple[PlayerNode, ...],
                     observations: tuple[PlayerObservation, ...]) -> Iterator[PlayerObservation | PlayerNode]:
    """The one fold order of a received group: each node after the observations at or before its version."""
    pending = iter(sorted(observations, key=lambda row: row.occurrence))
    observation = next(pending, None)
    for node in nodes:
        while observation is not None and observation.occurrence <= node.occurrence:
            yield observation
            observation = next(pending, None)
        yield node
    if observation is not None:
        yield observation
    yield from pending


def _apply_nodes(result: PlayerState, nodes: tuple[PlayerNode, ...], versions: tuple[VersionRow, ...],
                 observations: tuple[PlayerObservation, ...], updates: tuple[WorldUpdate, ...], rows: SensoryRows, *,
                 audience_composition: AudienceComposition | None = None) -> None:
    occurrences = {row.source_index for row in versions}
    world_updates = {row.occurrence: row for row in updates}
    for row in occurrence_order(nodes, observations):
        match row:
            case PlayerObservation():
                _observe(result, row, audience_composition=audience_composition)
            case PlayerNode():
                if row.occurrence in world_updates:
                    apply_world_update(result, world_updates[row.occurrence])
                if not row.canceled and row.fact is not None:
                    apply_committed_player_fact(result, folded_fact(row.fact, rows, result.spatial_content),
                        source_cursor=row.occurrence,
                        occurrences=occurrences, audience_composition=audience_composition)


def state_before_event(before: PlayerState, lineage: PlayerLineage, event: PlayerNode) -> PlayerState:
    """Retained subjective state just before a descendant's declaration."""
    first = min(row.source_index for row in lineage.version_rows if row.lineage == event.lineage)
    completed = {row.source_index for row in lineage.version_rows if row.source_index < first}
    events = tuple(row for row in lineage.events if row.occurrence in completed)
    if not events:
        return before
    return reduce_lineage(before, replace(lineage, events=events, end_cursor=first,
        observations=tuple(row for row in lineage.observations if row.occurrence in completed),
        world_updates=tuple(row for row in lineage.world_updates if row.occurrence in completed)))


def reduce_initialization(initialization: PlayerInitialization, *,
                          content_additions: tuple[ContentDescriptor, ...] = ()) -> PlayerState:
    target = PlayerState(generation=initialization.generation, observer_uuid=initialization.observer_uuid,
                         world=initialization.world,
                         audience=resolve_audience(initialization.observer_uuid, initialization.audience))
    target = reduce_nodes(target, initialization.nodes, initialization.version_rows,
                     initialization.observations, initialization.world_updates, initialization.sensory_rows)
    target.reducer_cursor = initialization.end_cursor
    if initialization.hud is not None:
        apply_hud(target, initialization.hud, end_cursor=initialization.end_cursor)
    target.content = tuple(sorted(content_additions, key=lambda row: row.ref.identity_key))
    return target


def apply_hud(target: PlayerState, patch: PlayerHUDPatch, *, end_cursor: int) -> None:
    """Fold a HUD patch into the seat's last display; against no display it is complete."""
    previous = target.hud_snapshot
    if (patch.generation != target.generation or patch.observer_uuid != target.observer_uuid
            or patch.revision > end_cursor or previous is not None and patch.revision < previous.revision):
        raise ValueError("HUD belongs to a different or future operation")
    sheets = {row.actor_uuid: row for row in previous.sheets} if previous is not None else {}
    for row in patch.sheets:
        before = sheets.get(row.actor_uuid)
        if before is None and row.changes.keys() != SheetChanges.__optional_keys__:
            raise ValueError("A first sheet must carry every field")
        sheets[row.actor_uuid] = (PlayerCharacterSheet(actor_uuid=row.actor_uuid, **row.changes) if before is None
            else replace(before, **row.changes))
    initiative = patch.initiative if patch.initiative is not None else previous.initiative if previous is not None else None
    order = (patch.sheet_order if patch.sheet_order is not None
        else tuple(row.actor_uuid for row in previous.sheets) if previous is not None else None)
    if initiative is None or order is None:
        raise ValueError("A first HUD requires its initiative and sheet order")
    target.hud_snapshot = PlayerHUDSnapshot(generation=patch.generation, observer_uuid=patch.observer_uuid,
        revision=patch.revision, initiative=initiative, sheets=tuple(sheets[identity] for identity in order))


def reduce_lineage(target: PlayerState, lineage: PlayerLineage) -> PlayerState:
    result = copy_target(target)
    _apply_lineage(result, lineage)
    return result


def _apply_lineage(target: PlayerState, lineage: PlayerLineage, *,
                   audience_composition: AudienceComposition | None = None) -> None:
    if (target.generation != lineage.generation or target.observer_uuid != lineage.observer_uuid
            or target.viewing_audience != resolve_audience(lineage.observer_uuid, lineage.audience)):
        raise ValueError("player lineage belongs to a different observer or generation")
    if lineage.end_cursor <= target.reducer_cursor:
        raise ValueError("player lineage precedes this reduction position")
    result = target
    _apply_nodes(result, lineage.events, lineage.version_rows, lineage.observations, lineage.world_updates,
        lineage.sensory_rows, audience_composition=audience_composition)
    result.reducer_cursor = lineage.end_cursor


def lineage_branch(lineage: PlayerLineage, root: PlayerNode) -> PlayerLineage:
    by_lineage = {node.lineage: node for node in lineage.events}
    intervals: dict[int, tuple[int, int]] = {}
    for row in lineage.version_rows:
        first, last = intervals.get(row.lineage, (row.source_index, row.source_index))
        intervals[row.lineage] = min(first, row.source_index), max(last, row.source_index)
    first, last = intervals[root.lineage]
    selected: set[int] = set()
    # Privacy can remove an intermediate cause (for example a carried light's
    # update between a walking step and its sensory result). The received
    # occurrence interval still places that unparented result inside this step.
    # Keep its real wire ancestry absent; this is a chronological branch view.
    pending = [root.lineage, *(node.lineage for node in lineage.events
        if node.parent_lineage is None and first <= intervals[node.lineage][0]
        and intervals[node.lineage][1] <= last)]
    while pending:
        identity = pending.pop()
        if identity in selected:
            continue
        selected.add(identity)
        pending.extend(by_lineage[identity].children_lineages)
    nodes = tuple(node for node in lineage.events if node.lineage in selected)
    versions = tuple(row for row in lineage.version_rows if row.lineage in selected)
    identities = {row.source_index for row in versions}
    return replace(lineage, root=next(index for index, node in enumerate(nodes) if node.occurrence == root.occurrence),
        events=nodes, version_rows=versions,
        start_cursor=versions[0].source_index, end_cursor=versions[-1].source_index + 1,
        observations=tuple(row for row in lineage.observations if row.occurrence in identities),
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
    if update.audience != target.viewing_audience:
        raise ValueError("An operation cannot change its authorized audience")
    if update.content_additions:
        content = {row.ref.identity_key: row for row in result.content}
        for descriptor in update.content_additions:
            old = content.get(descriptor.ref.identity_key)
            if old is not None and old != descriptor:
                raise ValueError("An admitted content identity changed its definition")
            content[descriptor.ref.identity_key] = descriptor
        result.content = tuple(content[key] for key in sorted(content))
    composition = None
    for lineage in update.lineages:
        if lineage.start_cursor != result.reducer_cursor:
            raise ValueError("Operation occurrence sequence has a gap")
        if composition is None and any(not node.canceled and isinstance(node.fact, SensoryFact)
                                       for node in lineage.events):
            composition = begin_audience_composition(result.perception, result.observer_uuid)
        _apply_lineage(result, lineage, audience_composition=composition)
    if update.hud is not None:
        apply_hud(result, update.hud, end_cursor=result.reducer_cursor)
    for index, row in enumerate(update.combat_log_appends, len(result.combat_log_appends)):
        if (row.generation != result.generation or row.observer_uuid != result.observer_uuid
                or row.operation_end_cursor > result.reducer_cursor or row.encounter_log_index != index):
            raise ValueError("Standalone log append is out of order or belongs to another audience")
    result.combat_log_appends += update.combat_log_appends
    return result
