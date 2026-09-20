"""Reduce and stage saved player packets without native event projection."""

from dataclasses import replace
from uuid import UUID

from dnd.core.condition_types import ConditionCategory
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.events import EventType, SpatialChangeType
from dnd.types.senses import reduce_senses_snapshot
from game.player_facts import (
    AttackFact, ConditionChangeFact, DamageFact, EquipmentFact, HealFact, ItemChargeFact, LifeFact,
    PlayerFact, PlayerInitialization, PlayerLineage, PlayerNode, PlayerObservation, PlayerSequence,
    PlayerState, SensoryFact, SpatialFact, TurnFact, VersionRow, WorldUpdate, TemporaryHitPointsFact,
)


def copy_target(target: PlayerState) -> PlayerState:
    senses = target.senses
    return replace(target, tiles=dict(target.tiles), objects=dict(target.objects), actors=dict(target.actors),
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
    if target.generation != lineage.generation or target.observer_uuid != lineage.observer_uuid:
        raise ValueError("player lineage belongs to a different observer or generation")
    result = stage_actors(target, lineage.observations)
    for update in lineage.world_updates:
        apply_world_update(result, update)
    return result


def _apply_fact(target: PlayerState, fact: PlayerFact) -> None:
    match fact:
        case SpatialFact():
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
                if contact.visual and identity in target.actors:
                    target.actors[identity] = replace(target.actors[identity], last_visual_position=contact.position)
        case AttackFact():
            actor = target.actors.get(fact.source_entity_uuid)
            if actor is not None:
                stance = WeaponSet.RANGED if fact.weapon_slot in (WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF) else WeaponSet.MELEE
                target.actors[actor.uuid] = replace(actor, visual_loadout=replace(actor.visual_loadout, active_weapon_set=stance))
        case DamageFact(stage="applied"):
            actor = target.actors[fact.target_entity_uuid]
            if fact.resulting_normal_hp is None or fact.resulting_temporary_hp is None:
                raise ValueError("applied damage requires exact committed HP")
            target.actors[actor.uuid] = replace(actor, normal_hp=fact.resulting_normal_hp, temporary_hp=fact.resulting_temporary_hp)
        case HealFact(was_blocked=False):
            actor = target.actors[fact.target_entity_uuid]
            if fact.resulting_normal_hp is None or fact.resulting_temporary_hp is None:
                raise ValueError("healing requires exact committed HP")
            target.actors[actor.uuid] = replace(actor, normal_hp=fact.resulting_normal_hp, temporary_hp=fact.resulting_temporary_hp)
        case TemporaryHitPointsFact():
            actor = target.actors[fact.entity_uuid]
            target.actors[actor.uuid] = replace(actor, temporary_hp=fact.resulting_temporary_hp)
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
                maximum_hp=actor.maximum_hp if condition.resulting_max_hp is None else condition.resulting_max_hp,
                armor_class=actor.armor_class if condition.resulting_ac is None else condition.resulting_ac)
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
            _apply_fact(result, node.fact)
    if observation is not None:
        _observe(result, observation)
    for remaining in pending:
        _observe(result, remaining)
    return result


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
    sequence = PlayerSequence.model_validate_json(payload)
    return reduce_initialization(sequence.initialization), sequence.lineages
