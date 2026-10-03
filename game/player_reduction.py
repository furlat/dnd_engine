"""Reduce and stage saved player packets without native event projection."""

from dataclasses import dataclass, replace
import json
from game.recording_compat import upgrade_player_sequence
from types import MappingProxyType
from typing import Mapping
from dnd.core.effect_types import ResolutionRef
from uuid import UUID

from dnd.core.condition_types import ConditionCategory
from dnd.core.events import EventType, SpatialChangeType
from dnd.types.senses import reduce_senses_snapshot
from game.player_facts import (
    AttackFact, ConditionChangeFact, DamageRequestFact, DamageResultFact, ObjectDamageFact, EquipmentFact, HealFact, ItemChargeFact, LifeFact,
    PlayerFact, PlayerInitialization, PlayerLineage, PlayerNode, PlayerObservation, PlayerSequence,
    PlayerState, SensoryFact, SpatialFact, TurnFact, VersionRow, WorldUpdate, TemporaryHitPointsFact, FactionFact,
)


@dataclass(frozen=True, slots=True)
class PlayerCausalIndex:
    """References into one received group, in its native commit order."""
    by_lineage: Mapping[UUID, PlayerNode]
    by_uuid: Mapping[UUID, PlayerNode]
    source_order: Mapping[UUID, int]
    owned: Mapping[ResolutionRef, tuple[PlayerNode, ...]]
    results: Mapping[ResolutionRef, tuple[PlayerNode, ...]]
    damage_requests: Mapping[UUID, UUID]


def index_player_lineage(lineage: PlayerLineage) -> PlayerCausalIndex:
    source_order = {row.event_uuid: row.source_index for row in lineage.version_rows}
    owned: dict[ResolutionRef, list[PlayerNode]] = {}
    results: dict[ResolutionRef, list[PlayerNode]] = {}
    by_lineage = {row.lineage_uuid: row for row in lineage.events}
    damage_requests: dict[UUID, UUID] = {}
    for node in lineage.events:
        ancestors: list[UUID] = []
        current = node
        while current.lineage_uuid not in ancestors:
            ancestors.append(current.lineage_uuid)
            request = (current.lineage_uuid if isinstance(current.fact, DamageRequestFact)
                       else damage_requests.get(current.lineage_uuid))
            if request is not None:
                damage_requests.update((identity, request) for identity in ancestors)
                break
            parent = by_lineage.get(current.parent_lineage) if current.parent_lineage is not None else None
            if parent is None:
                break
            current = parent
    for node in sorted(lineage.events, key=lambda row: source_order[row.uuid]):
        reference = node.resolution_ref
        if reference is None:
            continue
        owned.setdefault(reference, []).append(node)
        if not node.canceled and isinstance(node.fact, (DamageResultFact, ObjectDamageFact)):
            results.setdefault(reference, []).append(node)
    return PlayerCausalIndex(
        MappingProxyType(by_lineage),
        MappingProxyType({row.uuid: row for row in lineage.events}), MappingProxyType(source_order),
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
        spatial_commit_cursors=dict(target.spatial_commit_cursors),
        senses=None if senses is None else replace(senses, visible=set(senses.visible), seen=set(senses.seen),
            entities=dict(senses.entities), objects=dict(senses.objects),
            effective_light_levels=dict(senses.effective_light_levels), hazardous_cells=dict(senses.hazardous_cells),
            spatial_effects=dict(senses.spatial_effects)))


def apply_world_update(target: PlayerState, update: WorldUpdate) -> None:
    target.tiles.update((row.position, row) for row in update.tiles)
    for identity in update.objects_removed:
        target.objects.pop(identity, None)
    target.objects.update((row.item.item_uuid, row) for row in update.objects)
    target.connectors = update.connectors


def _observe(target: PlayerState, observation: PlayerObservation) -> None:
    previous = target.actors.get(observation.actor.uuid)
    if previous is not None and not previous.present:
        return  # A later retained observation cannot resurrect a terminal lifetime.
    target.actors[observation.actor.uuid] = observation.actor
    if observation.contact is not None and target.senses is not None:
        target.senses.entities[observation.actor.uuid] = observation.contact


def stage_actors(target: PlayerState, observations: tuple[PlayerObservation, ...]) -> PlayerState:
    """Supply absent bodies for binding; existing historical actors win."""
    result = copy_target(target)
    for observation in observations:
        if observation.actor.uuid not in result.actors:
            _observe(result, observation)
    return result


def observe_actors(target: PlayerState, observations: tuple[PlayerObservation, ...]) -> PlayerState:
    """Apply actual event-time observations, including a reacquired actor."""
    result = copy_target(target)
    for observation in observations:
        _observe(result, observation)
    return result


def stage_lineage(target: PlayerState, lineage: PlayerLineage) -> PlayerState:
    """Supply absent binding contacts without advancing known world geometry."""
    if target.generation != lineage.generation or target.observer_uuid != lineage.observer_uuid:
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


def _apply_fact(target: PlayerState, fact: PlayerFact) -> None:
    match fact:
        case FactionFact():
            actor = target.actors.get(fact.entity_uuid)
            if actor is not None:
                target.actors[actor.uuid] = replace(actor, faction=fact.faction_after)
        case SpatialFact():
            if fact.terminal_departure and fact.entity_uuid is not None and fact.entity_uuid in target.actors:
                actor = target.actors[fact.entity_uuid]
                target.actors[actor.uuid] = replace(actor, present=False, last_visual_position=None, occupancy_layer=None)
                if target.senses is not None:
                    target.senses.entities.pop(actor.uuid, None)
                return
            actor = target.actors.get(fact.entity_uuid) if fact.entity_uuid is not None else None
            if actor is not None and fact.occupancy_layer is not None:
                target.actors[actor.uuid] = replace(actor, occupancy_layer=fact.occupancy_layer)
            if (fact.entity_uuid == target.observer_uuid
                    and fact.change_type is SpatialChangeType.ENTITY_ENTERED):
                # Own entry is an explicit permitted contact even when one
                # sensory batch folds an arrival and return to the same cell.
                if target.senses is not None:
                    target.senses = replace(target.senses, position=fact.position)
                if actor is not None:
                    target.actors[actor.uuid] = replace(target.actors[actor.uuid], last_visual_position=fact.position)
        case ItemChargeFact():
            actor = target.actors[fact.source_entity_uuid]
            if actor.controlled_items is None or actor.uuid != target.observer_uuid:
                raise ValueError("item charges require the controlled actor's inventory")
            items = tuple(item.model_copy(update={
                "charges": fact.charges_after, "stack_count": fact.stack_count_after,
            }) if item.item_uuid == fact.item_uuid else item for item in actor.controlled_items
                if not (fact.item_destroyed and item.item_uuid == fact.item_uuid))
            layers = tuple(layer for layer in actor.visual_loadout.layers
                           if not (fact.item_destroyed and layer.item_uuid == fact.item_uuid))
            target.actors[actor.uuid] = replace(actor, controlled_items=items,
                visual_loadout=replace(actor.visual_loadout, layers=layers))
        case SensoryFact():
            target.senses = reduce_senses_snapshot(target.observer_uuid, target.senses, fact)
            if fact.observer_position_changed and target.observer_uuid in target.actors:
                target.actors[target.observer_uuid] = replace(target.actors[target.observer_uuid], last_visual_position=fact.observer_position)
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
            target.actors[actor.uuid] = replace(actor, life_state=fact.new_state, normal_hp=fact.normal_hit_points)
        case EquipmentFact():
            actor = target.actors.get(fact.source_entity_uuid)
            if actor is not None:
                target.actors[actor.uuid] = replace(actor, visual_loadout=fact.visual_loadout,
                    armor_class=fact.armor_class, controlled_items=fact.controlled_items)
        case ConditionChangeFact():
            actor = target.actors[fact.target_entity_uuid]
            condition = fact.condition
            members = {row.condition_uuid: row for row in actor.conditions}
            if fact.event_type is EventType.CONDITION_REMOVAL:
                members.pop(condition.condition_uuid, None)
            elif condition.category is not ConditionCategory.INTERNAL:
                members[condition.condition_uuid] = condition
            target.actors[actor.uuid] = replace(actor, conditions=tuple(members.values()),
                normal_hp=(condition.resulting_stats.normal_hp
                    if condition.resulting_stats is not None else actor.normal_hp),
                maximum_hp=(condition.resulting_stats.maximum_hp if condition.resulting_stats is not None else
                    actor.maximum_hp if condition.resulting_max_hp is None else condition.resulting_max_hp),
                armor_class=(condition.resulting_stats.armor_class if condition.resulting_stats is not None else
                    actor.armor_class if condition.resulting_ac is None else condition.resulting_ac),
                resolved_size=(condition.resulting_stats.resolved_size
                    if condition.resulting_stats is not None and condition.resulting_stats.resolved_size is not None
                    else actor.resolved_size))
        case TurnFact():
            if fact.round_number is not None:
                target.round_number = fact.round_number
            if fact.event_type in (EventType.TURN_START, EventType.TURN_END, EventType.ENCOUNTER_END):
                target.current_actor_uuid = fact.entity_uuid if fact.event_type is EventType.TURN_START else None


def reduce_nodes(target: PlayerState, nodes: tuple[PlayerNode, ...], versions: tuple[VersionRow, ...],
            observations: tuple[PlayerObservation, ...], updates: tuple[WorldUpdate, ...]) -> PlayerState:
    """Fold received values in source order, including a timed partial group."""
    result = copy_target(target)
    indexes = {row.event_uuid: row.source_index for row in versions}
    pending = iter(sorted(observations, key=lambda row: indexes[row.event_uuid]))
    observation = next(pending, None)
    world_updates = {row.event_uuid: row for row in updates}
    for node in nodes:
        while observation is not None and indexes[observation.event_uuid] <= indexes[node.uuid]:
            _observe(result, observation)
            observation = next(pending, None)
        if node.uuid in world_updates:
            apply_world_update(result, world_updates[node.uuid])
        if not node.canceled and node.fact is not None:
            if (isinstance(node.fact, SpatialFact) and node.fact.entity_uuid is not None
                    and node.fact.change_type in (SpatialChangeType.ENTITY_ENTERED, SpatialChangeType.ENTITY_LEFT)):
                # The producer identifies the actual commit publication. An
                # enclosing completion cannot restore a superseded membership.
                if node.fact.commit_event_uuid is None or node.fact.commit_event_uuid not in indexes:
                    raise ValueError(f"Spatial change {node.uuid} lacks its recorded commit version")
                committed_at = indexes[node.fact.commit_event_uuid]
                # Only a nested commit supersedes this closing transition.
                # Independent earlier transitions can be deliberately retimed
                # (e.g. jump takeoff after all preflight opportunity attacks).
                if committed_at < result.spatial_commit_cursors.get(node.fact.entity_uuid, -1) < indexes[node.uuid]:
                    continue
                result.spatial_commit_cursors[node.fact.entity_uuid] = committed_at
            _apply_fact(result, node.fact)
    if observation is not None:
        _observe(result, observation)
    for remaining in pending:
        _observe(result, remaining)
    return result


def state_before_event(before: PlayerState, lineage: PlayerLineage, event: PlayerNode) -> PlayerState:
    """Retained subjective state just before a descendant's declaration."""
    first = min(row.source_index for row in lineage.version_rows if row.lineage_uuid == event.lineage_uuid)
    completed = {row.event_uuid for row in lineage.version_rows if row.source_index < first}
    events = tuple(row for row in lineage.events if row.uuid in completed)
    if not events:
        return before
    return reduce_lineage(before, replace(lineage, events=events, end_cursor=first,
        observations=tuple(row for row in lineage.observations if row.event_uuid in completed),
        world_updates=tuple(row for row in lineage.world_updates if row.event_uuid in completed)))


def reduce_initialization(initialization: PlayerInitialization) -> PlayerState:
    target = PlayerState(generation=initialization.generation, observer_uuid=initialization.observer_uuid,
                         world=initialization.world)
    target = reduce_nodes(target, initialization.nodes, initialization.version_rows,
                     initialization.observations, initialization.world_updates)
    target.reducer_cursor = initialization.end_cursor
    return target


def reduce_lineage(target: PlayerState, lineage: PlayerLineage) -> PlayerState:
    if target.generation != lineage.generation or target.observer_uuid != lineage.observer_uuid:
        raise ValueError("player lineage belongs to a different observer or generation")
    if lineage.end_cursor <= target.reducer_cursor:
        raise ValueError("player lineage precedes this reduction position")
    result = reduce_nodes(target, lineage.events, lineage.version_rows, lineage.observations, lineage.world_updates)
    result.reducer_cursor = lineage.end_cursor
    return result


def lineage_branch(lineage: PlayerLineage, root: PlayerNode) -> PlayerLineage:
    by_lineage = {node.lineage_uuid: node for node in lineage.events}
    selected: set[UUID] = set()
    pending = [root.lineage_uuid]
    while pending:
        identity = pending.pop()
        if identity in selected:
            continue
        selected.add(identity)
        pending.extend(by_lineage[identity].children_lineages)
    nodes = tuple(node for node in lineage.events if node.lineage_uuid in selected)
    versions = tuple(row for row in lineage.version_rows if row.lineage_uuid in selected)
    identities = {row.event_uuid for row in versions}
    return replace(lineage, root=root, events=nodes, version_rows=versions,
        start_cursor=versions[0].source_index, end_cursor=versions[-1].source_index + 1,
        observations=tuple(row for row in lineage.observations if row.event_uuid in identities),
        world_updates=tuple(row for row in lineage.world_updates if row.event_uuid in identities))


def encode_player_sequence(sequence: PlayerSequence) -> bytes:
    return sequence.model_dump_json(warnings="error").encode("utf-8")


def decode_player_sequence(payload: bytes) -> tuple[PlayerState, tuple[PlayerLineage, ...]]:
    raw = json.loads(payload)
    if raw.get("schema_version", 1) == 1:
        payload = json.dumps(upgrade_player_sequence(raw)).encode("utf-8")
    sequence = PlayerSequence.model_validate_json(payload)
    return reduce_initialization(sequence.initialization), sequence.lineages
