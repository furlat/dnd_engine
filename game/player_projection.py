"""Project private recorded facts once, then reduce only the player packet.

Perception is already resolved by native events. This module selects existing
authority, remembers last-observed world values, and copies committed facts;
it never asks the live engine what an observer can see.
"""

from dataclasses import dataclass, replace
from uuid import UUID

from dnd.actions import AttackEvent, JumpEvent, MovementEvent, ShoveEvent, SpellEvent
from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.blocks.equipment import EquipmentEvent
from dnd.blocks.sensory import reduce_senses_snapshot
from dnd.core.base_actions import ActionEvent
from dnd.core.condition_types import ConditionCategory
from dnd.core.content.runtime import HandlerDispatchOutcome
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.events import (
    DamageAppliedEvent, DeathSaveEvent, EncounterEvent, EntityCreatedEvent,
    Event, EventType, ForcedMovementEvent, HealEvent, LifeStateChangeEvent,
    RoundEvent, SensoryUpdateEvent, SpatialChangeEvent, SpatialChangeType,
    StepMovementEvent, TakeDamageEvent, TurnEvent, WorldInitializedEvent,
)
from dnd.core.item_types import ItemPresentationState
from dnd.types.world import CardinalDirection
from game.actor_facts import ActorState, ConditionFact, actor_fact_owner, actor_from_birth, apply_actor_fact
from game.player_facts import (
    ActionFact, AttackFact, ConditionChangeFact, ContentAttribution, DamageFact,
    DeathSaveFact, EquipmentFact, FloorItem, ForcedMovementFact, HealFact, LifeFact,
    MovementFact, PlayerActor, PlayerFact, PlayerInitialization, PlayerLineage,
    PlayerNode, PlayerObject, PlayerObservation, PlayerSequence, PlayerState,
    PlayerWorld, SensoryFact, ShoveFact, SpatialFact, SpellFact, StepFact, TurnFact,
    VersionRow, VisualItem, VisualLoadout, WorldUpdate,
)
from game.presentation import ActorAdmission, CompletedLineage, IntervalEnvelope, ObjectiveRow, PresentationTarget, apply_world_fact
from game.replay import RecordedSequence


def _identified(event: Event, identity: UUID | None, observer: UUID) -> bool:
    return identity is not None and (identity == observer or str(observer) in
        event.identified_entity_observer_uuids.get(str(identity), set()))


def _position_allowed(event: Event, position: tuple[int, int], observer: UUID) -> bool:
    return str(observer) in event.located_position_observer_uuids.get(
        f"{position[0]},{position[1]}", set())


def _step_allowed(event: StepMovementEvent, observer: UUID) -> bool:
    return _identified(event, event.source_entity_uuid, observer) and (
        event.source_entity_uuid == observer or all(_position_allowed(event, position, observer)
            for position in (event.disclosed_path or (event.from_position, event.to_position))))


def _forced_allowed(event: ForcedMovementEvent, observer: UUID) -> bool:
    return _identified(event, event.target_entity_uuid, observer) and (
        observer in (event.source_entity_uuid, event.target_entity_uuid)
        or all(_position_allowed(event, point, observer) for point in (event.start_position, event.end_position)))


def _visual_loadout(actor: ActorState) -> VisualLoadout:
    items = {item.item_uuid: item for item in actor.items}
    return VisualLoadout(active_weapon_set=actor.active_weapon_set, layers=tuple(
        VisualItem(slot=slot, item_uuid=identity, item_id=items[identity].item_id,
            item_kind=items[identity].item_kind, visual_item_name=items[identity].visual_item_name,
            visual_variant_id=items[identity].visual_variant_id,
            equipped_visual_policy=items[identity].equipped_visual_policy)
        for slot, identity in actor.equipment))


def _public_actor(actor: ActorState, observer: UUID) -> PlayerActor:
    return PlayerActor(uuid=actor.uuid, name=actor.name,
        character_body_id=actor.character_body_id, creature_content_ref=actor.creature_content_ref,
        appearance=actor.appearance, visual_loadout=_visual_loadout(actor),
        normal_hp=actor.normal_hp, maximum_hp=actor.maximum_hp,
        temporary_hp=actor.temporary_hp, life_state=actor.life_state,
        armor_class=actor.armor_class, conditions=actor.conditions,
        last_visual_position=actor.last_visual_position,
        controlled_items=actor.items if actor.uuid == observer else None)


def _sensory_fact(event: SensoryUpdateEvent) -> SensoryFact:
    return SensoryFact(observer_uuid=event.observer_uuid, initial=event.initial,
        observer_position=event.observer_position, observer_position_changed=event.observer_position_changed,
        effective_light_levels_changed=dict(event.effective_light_levels_changed),
        cause_event_uuid=event.cause_event_uuid,
        visible_cells_added=tuple(event.visible_cells_added), visible_cells_removed=tuple(event.visible_cells_removed),
        seen_cells_added=tuple(event.seen_cells_added),
        entity_contacts_changed=dict(event.entity_contacts_changed),
        entity_contacts_removed=frozenset(event.entity_contacts_removed),
        object_contacts_changed=dict(event.object_contacts_changed),
        object_contacts_removed=frozenset(event.object_contacts_removed),
        sense_modes_changed=event.sense_modes_changed,
        sense_modes=tuple(event.sense_modes) if event.sense_modes is not None else None,
        passive_perception_changed=event.passive_perception_changed,
        passive_perception=event.passive_perception, visual_access_changed=event.visual_access_changed,
        visual_access=event.visual_access, paths_dirty=event.paths_dirty)


def _project_fact(event: Event, observer: UUID, actors: dict[UUID, ActorState],
                  condition: ConditionFact | None, events: tuple[Event, ...],
                  admissions: tuple[ActorAdmission, ...], known: set[UUID]) -> PlayerFact | None:
    source = event.source_entity_uuid if event.source_entity_uuid in known and _identified(event, event.source_entity_uuid, observer) else None
    target = event.target_entity_uuid if event.target_entity_uuid in known and _identified(event, event.target_entity_uuid, observer) else None
    match event:
        case SensoryUpdateEvent():
            return _sensory_fact(event) if event.observer_uuid == observer else None
        case StepMovementEvent():
            if not _step_allowed(event, observer):
                return None
            return StepFact(source_entity_uuid=event.source_entity_uuid,
                from_position=event.from_position, to_position=event.to_position,
                from_elevation_feet=event.from_elevation_feet, to_elevation_feet=event.to_elevation_feet,
                disclosed_path=event.disclosed_path, trajectory=event.trajectory,
                provocation_policy=event.provocation_policy, committed=event.committed)
        case MovementEvent() | JumpEvent():
            steps = tuple(row for row in events if isinstance(row, StepMovementEvent)
                          and row.parent_lineage == event.lineage_uuid)
            observed = (source is not None or any(_identified(row, event.source_entity_uuid, observer) for row in steps)
                        or any(row.actor.uuid == event.source_entity_uuid for row in admissions))
            if not observed:
                return None
            atomic = isinstance(event, JumpEvent) and (
                event.source_entity_uuid == observer or bool(steps) and all(_step_allowed(row, observer) for row in steps)
                and set(event.path or ()).issubset({position for row in steps
                    for position in (row.disclosed_path or (row.from_position, row.to_position))}))
            return MovementFact(source_entity_uuid=event.source_entity_uuid, trajectory=event.trajectory,
                start_position=event.start_position if atomic else None,
                end_position=event.end_position if atomic else None,
                requested_end_position=event.requested_end_position if atomic else None,
                path=tuple(event.path or ()) if atomic else (),
                start_elevation_feet=event.start_elevation_feet if atomic and isinstance(event, JumpEvent) else None,
                end_elevation_feet=event.end_elevation_feet if atomic and isinstance(event, JumpEvent) else None)
        case AttackEvent():
            if source is None or target is None:
                return None
            return AttackFact(source_entity_uuid=source, target_entity_uuid=target,
                behavior_id=event.behavior_id, name=event.name, weapon_slot=event.weapon_slot,
                attack_outcome=event.attack_outcome, damage_types=tuple(event.damage_types),
                source_item_id=event.source_item_presentation.item_id if event.source_item_presentation is not None else None)
        case SpellEvent():
            if source is None or (event.target_entity_uuid is not None and target is None):
                return None
            if any(not _identified(event, identity, observer) for identity in event.declared_target_entity_uuids):
                return None
            if event.source_position is not None and event.source_entity_uuid != observer and not _position_allowed(event, event.source_position, observer):
                # Existing exact actor-location evidence also authenticates the
                # declaration coordinate; not every action owns position grants.
                if str(observer) not in event.located_entity_observer_uuids.get(str(source), set()):
                    return None
            return SpellFact(source_entity_uuid=source, target_entity_uuid=target,
                behavior_id=event.behavior_id, name=event.name, source_position=event.source_position,
                declared_target_entity_uuids=tuple(event.declared_target_entity_uuids),
                application_id=event.application_id, application_index=event.application_index)
        case ShoveEvent():
            return (None if source is None or target is None else ShoveFact(
                source_entity_uuid=source, target_entity_uuid=target, behavior_id=event.behavior_id,
                contest_success=event.contest_success, push_distance=event.push_distance,
                knocked_prone=event.knocked_prone))
        case ForcedMovementEvent():
            if target is None or not _forced_allowed(event, observer):
                return None
            return ForcedMovementFact(source_entity_uuid=source, target_entity_uuid=target,
                start_position=event.start_position, end_position=event.end_position, actual_distance=event.actual_distance)
        case TakeDamageEvent():
            return (None if target is None else DamageFact(stage="taken", source_entity_uuid=source, target_entity_uuid=target))
        case DamageAppliedEvent():
            return (None if target is None else DamageFact(stage="applied", source_entity_uuid=source, target_entity_uuid=target,
                applied_damage=event.applied_damage, resulting_normal_hp=event.resulting_normal_hp,
                resulting_temporary_hp=event.resulting_temporary_hp, damage_type=event.damage_type))
        case HealEvent():
            return (None if target is None else HealFact(source_entity_uuid=source, target_entity_uuid=target,
                actual_healing=event.actual_healing, was_blocked=event.was_blocked,
                resulting_normal_hp=event.resulting_normal_hp, resulting_temporary_hp=event.resulting_temporary_hp))
        case LifeStateChangeEvent():
            return (None if event.entity_uuid not in known or not _identified(event, event.entity_uuid, observer) else LifeFact(
                entity_uuid=event.entity_uuid, previous_state=event.previous_state, new_state=event.new_state,
                reason=event.reason, normal_hit_points=event.normal_hit_points))
        case DeathSaveEvent():
            return (None if event.entity_uuid not in known or not _identified(event, event.entity_uuid, observer) else DeathSaveFact(
                entity_uuid=event.entity_uuid, natural_roll=event.natural_roll, succeeded=event.succeeded))
        case EquipmentEvent() | ItemLocationStateEvent():
            owner = actor_fact_owner(event)
            if owner is None or owner not in known or owner not in actors or not _identified(event, owner, observer):
                return None
            actor = actors[owner]
            return EquipmentFact(source_entity_uuid=owner, visual_loadout=_visual_loadout(actor),
                armor_class=actor.armor_class, controlled_items=actor.items if owner == observer else None)
        case SpatialChangeEvent():
            identified_entity = event.entity_uuid if _identified(event, event.entity_uuid, observer) else None
            own_position = identified_entity == observer
            if event.change_type not in (SpatialChangeType.ENTITY_ENTERED, SpatialChangeType.ENTITY_LEFT,
                                         SpatialChangeType.PERCEIVABILITY_CHANGED, SpatialChangeType.MOVEMENT_COLLISION):
                return None
            parent = next((row for row in events if row.lineage_uuid == event.parent_lineage), None)
            parent_geometry = (
                isinstance(parent, ForcedMovementEvent) and parent.target_entity_uuid == event.entity_uuid
                and _forced_allowed(parent, observer)
                or isinstance(parent, StepMovementEvent) and parent.source_entity_uuid == event.entity_uuid
                and _step_allowed(parent, observer))
            located_arrival = (event.change_type is SpatialChangeType.ENTITY_ENTERED
                and str(observer) in event.located_entity_observer_uuids.get(str(event.entity_uuid), set()))
            if identified_entity is None or not (own_position or parent_geometry or located_arrival
                                                or _position_allowed(event, event.position, observer)):
                return None
            return SpatialFact(change_type=event.change_type, entity_uuid=identified_entity, position=event.position)
        case TurnEvent():
            return TurnFact(event_type=event.event_type, entity_uuid=event.entity_uuid
                if _identified(event, event.entity_uuid, observer) else None, round_number=event.round_number)
        case RoundEvent():
            return TurnFact(event_type=event.event_type, entity_uuid=None, round_number=event.round_number)
        case EncounterEvent():
            return TurnFact(event_type=event.event_type, entity_uuid=None, round_number=None)
        case _ if condition is not None:
            return (None if target is None or condition.category is ConditionCategory.INTERNAL else
                ConditionChangeFact(target_entity_uuid=target, event_type=event.event_type, condition=condition))
        case ActionEvent():
            return (None if source is None else ActionFact(source_entity_uuid=source, target_entity_uuid=target,
                behavior_id=event.behavior_id, name=event.name))
    return None


def _content_attributions(event: Event, fact: PlayerFact | None, observer: UUID,
                          disclosed_lineages: set[UUID]) -> tuple[ContentAttribution, ...]:
    result: list[ContentAttribution] = []
    if fact is not None and isinstance(event, ActionEvent) and event.behavior_id is not None:
        result.append(ContentAttribution(role="behavior", behavior_id=event.behavior_id,
            provided_by_id=event.provided_by_id, origin_root_id=event.origin_root_id))
    if fact is not None and isinstance(event, ActionEvent) and event.source_item_presentation is not None:
        result.append(ContentAttribution(role="source_item", behavior_id=event.source_item_presentation.item_id))
    for evidence in event.effective_handler_presentations:
        if not _identified(event, evidence.source_entity_uuid, observer):
            continue
        emitted = tuple(identity for identity in evidence.emitted_lineage_uuids if identity in disclosed_lineages)
        if evidence.outcome is HandlerDispatchOutcome.EMITTED_EVENTS and not emitted:
            continue
        result.append(ContentAttribution(role="effective_handler", behavior_id=evidence.behavior_id,
            provided_by_id=evidence.provided_by_id, origin_root_id=evidence.origin_root_id,
            source_entity_uuid=evidence.source_entity_uuid, triggering_event_uuid=evidence.triggering_event_uuid,
            triggering_lineage_uuid=evidence.triggering_lineage_uuid,
            emitted_lineage_uuids=emitted, handler_name=evidence.handler_name,
            dispatch_index=evidence.dispatch_index, outcome=evidence.outcome))
    return tuple(result)


def _floor_item(item: ItemPresentationState) -> FloorItem:
    return FloorItem(item_uuid=item.item_uuid, item_id=item.item_id, name=item.name,
        visual_item_name=item.visual_item_name, visual_variant_id=item.visual_variant_id,
        map_char=item.map_char, boundary_structure=item.boundary_structure,
        is_open=item.is_open, is_lit=item.is_lit)


_DELTAS = {CardinalDirection.NORTH: (0, 1), CardinalDirection.SOUTH: (0, -1),
           CardinalDirection.EAST: (1, 0), CardinalDirection.WEST: (-1, 0)}


def _object_observed(world: PresentationTarget, identity: UUID) -> bool:
    senses = world.senses
    if senses is None:
        return False
    if identity in senses.objects:
        return True
    obj = world.objects[identity]
    direction = obj.placement.boundary_direction
    if direction is None or obj.item.boundary_structure is None:
        return False
    x, y = obj.placement.position
    dx, dy = _DELTAS[direction]
    # Boundary appearance belongs to either observed incident support, including
    # a wall which stops its author's cell from entering optical visibility.
    return (x, y) in senses.visible or (x + dx, y + dy) in senses.visible


def _world_update(world: PresentationTarget, remembered: PlayerState, event_uuid: UUID) -> WorldUpdate | None:
    senses = world.senses
    if senses is None or world.world is None:
        return None
    tiles = tuple(world.tiles[position] for position in sorted(senses.visible) if position in world.tiles
                  and remembered.tiles.get(position) != world.tiles[position])
    observed = {identity: PlayerObject(placement=obj.placement, item=_floor_item(obj.item))
                for identity, obj in world.objects.items() if _object_observed(world, identity)}
    objects = tuple(observed[identity] for identity in sorted(observed, key=str)
                    if remembered.objects.get(identity) != observed[identity])
    removed = tuple(identity for identity, obj in remembered.objects.items()
                    if identity not in observed and obj.placement.position in senses.visible)
    connectors = tuple(row for row in world.world.connectors
                       if all(point in senses.visible for point in row.endpoints))
    if not tiles and not objects and not removed and connectors == remembered.connectors:
        return None
    update = WorldUpdate(event_uuid=event_uuid, tiles=tiles, objects=objects,
                         objects_removed=removed, connectors=connectors)
    _apply_world_update(remembered, update)
    return update


def _versions(rows: tuple[ObjectiveRow, ...]) -> tuple[VersionRow, ...]:
    return tuple(VersionRow(source_index=row.source_index, event_uuid=row.event_uuid,
                            lineage_uuid=row.lineage_uuid) for row in rows)


def _project_nodes(events: tuple[Event, ...], versions: tuple[VersionRow, ...],
                   admissions: tuple[ActorAdmission, ...], conditions: tuple[ConditionFact, ...],
                   private_world: PresentationTarget, private_actors: dict[UUID, ActorState],
                   remembered: PlayerState) -> tuple[tuple[PlayerNode, ...], tuple[PlayerObservation, ...], tuple[WorldUpdate, ...]]:
    observer = remembered.observer_uuid
    indexes = {row.event_uuid: row.source_index for row in versions}
    facts = {row.event_uuid: row for row in conditions}
    observations: list[PlayerObservation] = []
    updates: list[WorldUpdate] = []
    nodes: list[PlayerNode] = []
    pending = iter(sorted(admissions, key=lambda row: indexes[row.event_uuid]))
    admission = next(pending, None)
    by_lineage = {event.lineage_uuid: event for event in events}
    for event in events:
        while admission is not None and indexes[admission.event_uuid] <= indexes[event.uuid]:
            private_actors[admission.actor.uuid] = admission.actor
            observed = _public_actor(admission.actor, observer)
            observations.append(PlayerObservation(event_uuid=admission.event_uuid, actor=observed, contact=admission.contact))
            remembered.actors[observed.uuid] = observed
            admission = next(pending, None)
        if not event.canceled:
            if isinstance(event, EntityCreatedEvent):
                private_actors[event.entity_uuid] = actor_from_birth(event)
            owner = actor_fact_owner(event)
            if owner is not None and owner in private_actors:
                private_actors[owner] = apply_actor_fact(private_actors[owner], event, facts.get(event.uuid))
            apply_world_fact(private_world, event)
            if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == observer:
                # Native spatial commits publish their sensory child before
                # their own completion. Its exact recorded parent after-value
                # was already true when this contact/visibility was captured.
                parent = event.parent_lineage
                while parent is not None and parent in by_lineage:
                    ancestor = by_lineage[parent]
                    if isinstance(ancestor, SpatialChangeEvent) and ancestor.change_type is SpatialChangeType.OBJECT_CHANGED:
                        apply_world_fact(private_world, ancestor)
                    parent = ancestor.parent_lineage
                private_world.senses = reduce_senses_snapshot(observer, private_world.senses, event)
            update = _world_update(private_world, remembered, event.uuid)
            if update is not None:
                updates.append(update)
        fact = _project_fact(event, observer, private_actors, facts.get(event.uuid), events, admissions, set(remembered.actors))
        nodes.append(PlayerNode(uuid=event.uuid, lineage_uuid=event.lineage_uuid,
            parent_event=event.parent_event, parent_lineage=event.parent_lineage,
            children_lineages=tuple(event.children_lineages), phase=event.phase,
            canceled=event.canceled, fact=fact, combat_log=event.combat_log))
    disclosed = {node.lineage_uuid for node in nodes if node.fact is not None}
    nodes = [replace(node, content_attributions=_content_attributions(event, node.fact, observer, disclosed))
             for node, event in zip(nodes, events, strict=True)]
    return tuple(nodes), tuple(observations), tuple(updates)


@dataclass(slots=True)
class ProjectionState:
    """Private recorded aggregates and last-observed memory for one observer."""

    world: PresentationTarget
    actors: dict[UUID, ActorState]
    remembered: PlayerState


def begin_projection(initialization: IntervalEnvelope) -> tuple[ProjectionState, PlayerInitialization]:
    """Start a projection from recorded initialization; no native queries."""
    world_event = next((event for _, event in initialization.admitted if isinstance(event, WorldInitializedEvent)), None)
    if world_event is None:
        raise ValueError("player projection requires recorded world initialization")
    world = PlayerWorld(battlefield_id=world_event.battlefield_id, battlefield_name=world_event.battlefield_name,
        bounds=world_event.bounds, width=world_event.width, height=world_event.height)
    private_world = PresentationTarget(generation=initialization.generation, observer_uuid=initialization.observer_uuid)
    remembered = PlayerState(generation=initialization.generation, observer_uuid=initialization.observer_uuid, world=world)
    actors: dict[UUID, ActorState] = {}
    versions = _versions(initialization.objective_rows)
    nodes, observations, updates = _project_nodes(tuple(event for _, event in initialization.admitted),
        versions, initialization.admissions, initialization.conditions, private_world, actors, remembered)
    initial = PlayerInitialization(generation=initialization.generation, observer_uuid=initialization.observer_uuid,
        world=world, nodes=nodes, version_rows=versions, end_cursor=initialization.end_cursor,
        observations=observations, world_updates=updates)
    return ProjectionState(private_world, actors, remembered), initial


def project_lineage(state: ProjectionState, lineage: CompletedLineage) -> PlayerLineage | None:
    """Advance the same private projection memory over one closed root."""
    if state.world.generation != lineage.generation or state.world.observer_uuid != lineage.observer_uuid:
        raise ValueError("recorded lineage belongs to another projection")
    versions = _versions(lineage.objective_rows)
    nodes, observations, updates = _project_nodes(lineage.events, versions, lineage.admissions,
        lineage.conditions, state.world, state.actors, state.remembered)
    if not observations and not updates and not any(node.fact is not None or node.combat_log is not None
                                                   or node.content_attributions for node in nodes):
        return None
    root = next(node for node in nodes if node.uuid == lineage.root.uuid)
    return PlayerLineage(generation=lineage.generation, observer_uuid=lineage.observer_uuid,
        root=root, events=nodes, version_rows=versions, start_cursor=lineage.start_cursor,
        end_cursor=lineage.end_cursor, observations=observations, world_updates=updates)


def project_sequence(native: RecordedSequence) -> PlayerSequence:
    """Produce one observer's packet entirely from their private saved capture."""
    state, initial = begin_projection(native.initialization)
    return PlayerSequence(initialization=initial, lineages=tuple(
        projected for row in native.lineages if (projected := project_lineage(state, row)) is not None))


def copy_target(target: PlayerState) -> PlayerState:
    senses = target.senses
    return replace(target, tiles=dict(target.tiles), objects=dict(target.objects), actors=dict(target.actors),
        senses=None if senses is None else replace(senses, visible=set(senses.visible), seen=set(senses.seen),
            entities=dict(senses.entities), objects=dict(senses.objects), effective_light_levels=dict(senses.effective_light_levels)))


def _apply_world_update(target: PlayerState, update: WorldUpdate) -> None:
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
        _apply_world_update(result, update)
    return result


def _apply_fact(target: PlayerState, fact: PlayerFact) -> None:
    match fact:
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


def _reduce(target: PlayerState, nodes: tuple[PlayerNode, ...], versions: tuple[VersionRow, ...],
            observations: tuple[PlayerObservation, ...], updates: tuple[WorldUpdate, ...]) -> PlayerState:
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
            _apply_world_update(result, world_updates[node.uuid])
        if not node.canceled and node.fact is not None:
            _apply_fact(result, node.fact)
    return result


def reduce_initialization(initialization: PlayerInitialization) -> PlayerState:
    target = PlayerState(generation=initialization.generation, observer_uuid=initialization.observer_uuid,
                         world=initialization.world)
    target = _reduce(target, initialization.nodes, initialization.version_rows,
                     initialization.observations, initialization.world_updates)
    target.reducer_cursor = initialization.end_cursor
    return target


def reduce_lineage(target: PlayerState, lineage: PlayerLineage) -> PlayerState:
    if target.generation != lineage.generation or target.observer_uuid != lineage.observer_uuid:
        raise ValueError("player lineage belongs to a different observer or generation")
    if lineage.end_cursor <= target.reducer_cursor:
        raise ValueError("player lineage precedes this reduction position")
    result = _reduce(target, lineage.events, lineage.version_rows, lineage.observations, lineage.world_updates)
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
