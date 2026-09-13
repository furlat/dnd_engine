"""Assignment knowledge reduced from recorded source facts, without world queries."""

from dataclasses import dataclass, field, replace
from collections.abc import Iterable
from uuid import UUID

from dnd.actor_projection import actor_fact_owner, actor_from_birth, apply_actor_fact, condition_fact
from dnd.ai.contracts.observation import (
    KnowledgeState, ObservationConditionFact, ObservationEffectProtection,
    ObservationEntityFact, ObservationObjectFact, ObservationObserverState,
    ObservationTileFact,
)
from dnd.ai.runtime.world_projection import adjacent_domain, project_object, project_tile
from dnd.blocks.base_item import ItemChargeConsumptionEvent, ItemLocationStateEvent
from dnd.core.condition_types import ConditionTag
from dnd.core.events import (
    EntityCreatedEvent, Event, EventPhase, EventType, SensoryUpdateEvent,
    SpatialChangeEvent, SpatialChangeType, WorldInitializedEvent, WorldModifiedEvent,
)
from dnd.core.life_types import LifeState
from dnd.core.modifiers import ResistanceStatus
from dnd.types.actor_facts import ActorState, ConditionFact
from dnd.types.senses import SensesSnapshot, reduce_senses_snapshot
from dnd.world_facts import WorldFacts, apply_world_fact, world_event_positions


def remember_entity(fact: ObservationEntityFact) -> ObservationEntityFact:
    """Apply the existing native AI memory rule when its last observer loses it."""
    return fact.model_copy(update={
        "knowledge_state": KnowledgeState.REMEMBERED, "observer_uuids": [],
        "controlled": False, "hp": None, "normal_hp": None, "temporary_hp": None,
        "max_hp": None, "healing_blocked": None, "ac": None, "conditions": [],
        "condition_semantic_keys": None, "condition_facts": None,
        "effect_protections": None, "is_concentrating": False,
        "damage_vulnerabilities": [], "damage_resistances": [], "damage_immunities": [],
        "life_state": LifeState.DEAD if fact.life_state is LifeState.DEAD else None,
        "is_dead": True if fact.life_state is LifeState.DEAD else None,
    })


def project_actor(actor: ActorState, observers: list[str], *, controlled: bool,
                  position: tuple[int, int] | None) -> ObservationEntityFact:
    """Select current actor values; condition and modifier evaluation is already done."""
    states = [row.state for row in actor.conditions if row.state is not None]
    affinities = actor.damage_affinities
    return ObservationEntityFact(
        uuid=str(actor.uuid), name=actor.name, knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=observers, controlled=controlled, position=position,
        hp=actor.normal_hp + actor.temporary_hp, normal_hp=actor.normal_hp,
        temporary_hp=actor.temporary_hp, max_hp=actor.maximum_hp,
        healing_blocked=actor.healing_blocked, ac=actor.armor_class,
        conditions=[row.name for row in actor.conditions],
        condition_semantic_keys=sorted(state.semantic_key for state in states),
        condition_facts=sorted((ObservationConditionFact(
            semantic_key=state.semantic_key,
            removal_triggers=sorted(state.removal_triggers, key=lambda trigger: trigger.value),
            agency_denial=state.agency_denial,
            applied_source_event_cursor=state.applied_source_event_cursor,
        ) for state in states), key=lambda row: row.semantic_key),
        effect_protections=sorted((ObservationEffectProtection(
            protection_id=protection.protection_id,
            blocked_effect_ids=sorted(protection.blocked_effect_ids),
            source_condition_semantic_key=state.semantic_key,
        ) for state in states for protection in state.outcome_protections),
            key=lambda row: (row.protection_id, row.source_condition_semantic_key or "")),
        is_concentrating=any(ConditionTag.CONCENTRATION in state.tags for state in states),
        damage_vulnerabilities=[kind for kind, status in affinities if status == ResistanceStatus.VULNERABILITY.value],
        damage_resistances=[kind for kind, status in affinities if status == ResistanceStatus.RESISTANCE.value],
        damage_immunities=[kind for kind, status in affinities if status == ResistanceStatus.IMMUNITY.value],
        creature_type=actor.creature_type, faction=actor.faction,
        life_state=actor.life_state, is_dead=actor.life_state is LifeState.DEAD,
    )


@dataclass(slots=True)
class AIKnowledge:
    """One assignment's current recorded facts and observer-attributed memory."""

    controlled_entity_uuids: tuple[UUID, ...]
    source_cursor: int = 0
    world: WorldFacts = field(default_factory=WorldFacts)
    actors: dict[UUID, ActorState] = field(default_factory=dict)
    senses: dict[UUID, SensesSnapshot] = field(default_factory=dict)
    observers: dict[str, ObservationObserverState] = field(default_factory=dict)
    known_entities: dict[str, ObservationEntityFact] = field(default_factory=dict)
    known_objects: dict[str, ObservationObjectFact] = field(default_factory=dict)
    known_tiles: dict[str, ObservationTileFact] = field(default_factory=dict)
    pending_conditions: dict[UUID, dict[UUID, ConditionFact]] = field(default_factory=dict)
    open_events: dict[UUID, Event] = field(default_factory=dict)

    def consume(self, rows: Iterable[tuple[int, Event, ConditionFact | None]]) -> None:
        """Apply an exact recorded prefix; context/decision authority stays outside."""
        for index, event, condition in rows:
            if index != self.source_cursor:
                raise ValueError("AI source facts must be contiguous and ordered")
            self.source_cursor = index + 1
            self.open_events[event.lineage_uuid] = event
            if event.phase is EventPhase.COMPLETION and not event.canceled:
                self._apply(event, condition if condition is not None else condition_fact(event, source_index=index))
            if event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL):
                self.open_events.pop(event.lineage_uuid, None)

    def _apply(self, event: Event, condition: ConditionFact | None) -> None:
        if isinstance(event, EntityCreatedEvent):
            actor = actor_from_birth(event)
            previous = self.pending_conditions.pop(event.entity_uuid, {})
            self.actors[event.entity_uuid] = replace(actor, conditions=tuple(previous.values()))
            self._refresh_entity(event.entity_uuid)
            if event.entity_uuid in self.senses:
                self._refresh_observer(event.entity_uuid)

        owner = actor_fact_owner(event)
        if owner is not None:
            actor = self.actors.get(owner)
            if actor is not None:
                self.actors[owner] = apply_actor_fact(actor, event, condition)
                self._refresh_entity(owner)
            elif condition is not None and condition.resulting_stats is not None:
                pending = self.pending_conditions.setdefault(owner, {})
                if event.event_type is EventType.CONDITION_REMOVAL:
                    pending.pop(condition.condition_uuid, None)
                else:
                    pending[condition.condition_uuid] = condition

        positions = world_event_positions(self.world, event, condition)
        objects = self._event_objects(event)
        if apply_world_fact(self.world, event, condition):
            self._refresh_world(positions, objects)

        if isinstance(event, SensoryUpdateEvent) and event.observer_uuid in self.controlled_entity_uuids:
            # Spatial owners have committed these after-values before publishing
            # their sensory child, even though the parent terminal version is later.
            parent = event.parent_lineage
            while parent is not None and (ancestor := self.open_events.get(parent)) is not None:
                if isinstance(ancestor, SpatialChangeEvent) and ancestor.change_type is SpatialChangeType.OBJECT_CHANGED:
                    affected = world_event_positions(self.world, ancestor)
                    changed_objects = self._event_objects(ancestor)
                    if apply_world_fact(self.world, ancestor):
                        positions.update(affected)
                        objects.update(changed_objects)
                parent = ancestor.parent_lineage
            before = self.senses.get(event.observer_uuid)
            self.senses[event.observer_uuid] = reduce_senses_snapshot(event.observer_uuid, before, event)
            after = self.senses[event.observer_uuid]
            self._refresh_observer(event.observer_uuid)
            actors = set(event.entity_contacts_changed) | set(event.entity_contacts_removed)
            actors.add(event.observer_uuid)
            objects.update(event.object_contacts_changed)
            objects.update(event.object_contacts_removed)
            positions.update(event.visible_cells_added)
            positions.update(event.visible_cells_removed)
            positions.update(event.seen_cells_added)
            for key in event.hazardous_cells_changed:
                x, y = key.split(",", maxsplit=1)
                positions.add((int(x), int(y)))
            # A different known boundary provider changes subjective movement
            # sides even if the visible field did not change.
            for identity in objects:
                obj = self.world.objects.get(identity)
                if obj is not None:
                    x, y = obj.placement.position
                    positions.update(((x, y), (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
            if event.initial:
                actors.update(after.entities)
                objects.update(after.objects)
                positions.update(after.seen)
            for identity in actors:
                self._refresh_entity(identity)
            self._refresh_world(positions, objects)

    def _refresh_entity(self, identity: UUID) -> None:
        actor = self.actors.get(identity)
        if actor is None:
            return
        observer_ids = sorted(str(observer) for observer, senses in self.senses.items()
                              if observer == identity or identity in senses.entities)
        controlled = identity in self.controlled_entity_uuids
        if observer_ids or controlled:
            if (own := self.senses.get(identity)) is not None:
                position = own.position
            else:
                position = next((self.senses[UUID(observer)].entities[identity].position
                                 for observer in observer_ids if identity in self.senses[UUID(observer)].entities), None)
            self.known_entities[str(identity)] = project_actor(actor, observer_ids, controlled=controlled, position=position)
        elif (previous := self.known_entities.get(str(identity))) is not None and previous.knowledge_state is KnowledgeState.VISIBLE:
            self.known_entities[str(identity)] = remember_entity(previous)

    def _refresh_observer(self, identity: UUID) -> None:
        actor = self.actors.get(identity)
        if actor is None:
            return
        senses = self.senses[identity]
        self.observers[str(identity)] = ObservationObserverState(
            observer_uuid=str(identity), entity_name=actor.name, position=senses.position,
            passive_perception=senses.passive_perception,
            sense_modes=[{"sense_type": mode.sense_type.value, "range_feet": mode.range_feet} for mode in senses.sense_modes],
            visible_cells=sorted(senses.visible), seen_cells=sorted(senses.seen),
            visible_entity_uuids=sorted(str(key) for key in senses.entities),
            visible_object_uuids=sorted(str(key) for key in senses.objects),
        )

    def _refresh_world(self, positions: set[tuple[int, int]], objects: set[UUID]) -> None:
        for identity in objects:
            observers = sorted(str(observer) for observer, senses in self.senses.items() if identity in senses.objects)
            if observers:
                contact = self.senses[UUID(observers[0])].objects[identity]
                fact = project_object(self.world, identity, contact.position, observers)
                if fact is not None:
                    self.known_objects[str(identity)] = fact
            elif (prior := self.known_objects.get(str(identity))) is not None:
                self.known_objects[str(identity)] = prior.model_copy(update={
                    "knowledge_state": KnowledgeState.REMEMBERED, "observer_uuids": [],
                })
        for position in positions:
            visible = sorted(str(observer) for observer, senses in self.senses.items() if position in senses.visible)
            seen = sorted(str(observer) for observer, senses in self.senses.items() if position in senses.seen)
            key = f"{position[0]},{position[1]}"
            if visible:
                self.known_tiles[key] = project_tile(self.world, position, visible, self.senses)
            elif (prior := self.known_tiles.get(key)) is not None:
                self.known_tiles[key] = prior.model_copy(update={"knowledge_state": KnowledgeState.SEEN, "observer_uuids": seen})
            elif seen:
                self.known_tiles[key] = ObservationTileFact(
                    key=key, position=position, knowledge_state=KnowledgeState.SEEN,
                    observer_uuids=seen, adjacent_domain=adjacent_domain(self.world, position),
                )

    def _event_objects(self, event: Event) -> set[UUID]:
        match event:
            case WorldInitializedEvent():
                return set(self.world.objects) | {obj.item.item_uuid for obj in event.objects}
            case WorldModifiedEvent() | SpatialChangeEvent():
                return {event.object_uuid} if event.object_uuid is not None else set()
            case ItemLocationStateEvent():
                return {event.item_state.item_uuid}
            case ItemChargeConsumptionEvent():
                return {event.item_uuid}
        return set()
