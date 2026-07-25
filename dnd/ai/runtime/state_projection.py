"""Retained subjective state projection shared by every AI deployment.

The projector is deliberately assignment-owned.  It reads only facts visible
to the assignment's controlled observers, retains immutable last-known facts,
and builds decision authority beside (but never inside) the public world.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable
from uuid import UUID

from dnd.ai.contracts.control import DecisionEpochReason
from dnd.ai.contracts.observation import (
    AdjacentOffset,
    KnowledgeState,
    ObservationCombatantState,
    ObservationConditionFact,
    ObservationEffectProtection,
    ObservationEncounterState,
    ObservationEntityFact,
    ObservationObjectFact,
    ObservationObserverState,
    ObservationSessionState,
    ObservationTileFact,
    SpatialDomainKnowledge,
    SubjectiveWorldState,
)
from dnd.ai.runtime.decision_epoch import DecisionEpochBuild, build_decision_epoch
from dnd.controller import TurnContext
from dnd.core.base_block import BaseBlock
from dnd.core.condition_types import ConditionTag
from dnd.core.events import EventQueue
from dnd.core.life_types import LifeState
from dnd.core.modifiers import DamageType, ResistanceStatus
from dnd.core.gridmap import get_map
from dnd.entity import Entity


@dataclass(frozen=True, slots=True)
class AIDecisionState:
    """One public subjective state and its private exact execution authority."""

    world: SubjectiveWorldState
    epoch_build: DecisionEpochBuild


class SubjectiveAIStateProjector:
    """Project one side's retained knowledge without any transport/session layer."""

    def __init__(
        self,
        *,
        assignment_id: str,
        controlled_entity_uuids: tuple[UUID, ...],
    ) -> None:
        if not assignment_id:
            raise ValueError("assignment_id must not be empty")
        if not controlled_entity_uuids:
            raise ValueError("AI assignment must control at least one entity")
        if len(controlled_entity_uuids) != len(set(controlled_entity_uuids)):
            raise ValueError("controlled_entity_uuids contains duplicates")
        self._assignment_id = assignment_id
        self._controlled_entity_uuids = tuple(
            sorted(controlled_entity_uuids, key=str)
        )
        self._observation_cursor = 0
        self._world: SubjectiveWorldState | None = None

    @property
    def world(self) -> SubjectiveWorldState | None:
        """Return the most recently projected immutable model."""
        return self._world

    @property
    def observation_cursor(self) -> int:
        """Return the latest assignment-local projection cursor."""
        return self._observation_cursor

    def project_decision(
        self,
        actor: Entity,
        context: TurnContext,
        *,
        reason: DecisionEpochReason,
    ) -> AIDecisionState:
        """Project current knowledge and build exact action authority once."""
        world = self.project_world(actor, context)
        epoch_build = build_decision_epoch(
            actor,
            epoch_namespace=self._assignment_id,
            round_number=context.round_number,
            turn_index=context.turn_index,
            observation_cursor=world.observation_cursor,
            reason=reason,
        )
        if epoch_build is None:
            raise ValueError("active AI actor cannot build a decision epoch")
        world = world.model_copy(update={"current_epoch": epoch_build.epoch})
        self._world = world
        return AIDecisionState(world=world, epoch_build=epoch_build)

    def project_world(
        self,
        actor: Entity,
        context: TurnContext,
    ) -> SubjectiveWorldState:
        """Refresh subjective facts while retaining only prior unseen values."""
        if actor.uuid not in self._controlled_entity_uuids:
            raise ValueError("actor is not controlled by this AI assignment")
        self._observation_cursor += 1
        observers = self._controlled_observers()
        visible_entities = {
            entity_uuid
            for observer in observers
            for entity_uuid in observer.senses.entities
        }
        visible_entities.update(self._controlled_entity_uuids)

        session = self._session_state(actor)
        observer_states = {
            str(observer.uuid): _observer_state(observer)
            for observer in observers
        }
        known_entities = self._known_entities(
            observers=observers,
            visible_entity_uuids=visible_entities,
        )
        known_objects = self._known_objects(observers)
        known_tiles = self._known_tiles(observers)
        encounter = self._encounter_state(
            actor=actor,
            context=context,
            observers=observers,
            visible_entity_uuids=visible_entities,
        )
        self._world = SubjectiveWorldState(
            observation_cursor=self._observation_cursor,
            session=session,
            encounter=encounter,
            observers=observer_states,
            known_entities=known_entities,
            known_objects=known_objects,
            known_tiles=known_tiles,
            combat_logs=list(self._world.combat_logs) if self._world else [],
            current_epoch=None,
            epoch_cursor=self._observation_cursor,
        )
        return self._world

    def _controlled_observers(self) -> tuple[Entity, ...]:
        observers = tuple(
            entity
            for entity_uuid in self._controlled_entity_uuids
            for entity in [Entity.get(entity_uuid)]
            if entity is not None
        )
        if not observers:
            raise ValueError("AI assignment has no live controlled entities")
        return observers

    def _session_state(self, actor: Entity) -> ObservationSessionState:
        return ObservationSessionState(
            session_id=self._assignment_id,
            player_type="ai",
            name=f"AI {self._assignment_id}",
            connection_status="connected",
            controlled_entity_uuids=[
                str(entity_uuid) for entity_uuid in self._controlled_entity_uuids
            ],
            active_entity_uuid=str(actor.uuid),
            active_entity_name=actor.name,
            is_my_turn=True,
        )

    def _known_entities(
        self,
        *,
        observers: tuple[Entity, ...],
        visible_entity_uuids: set[UUID],
    ) -> dict[str, ObservationEntityFact]:
        facts = {
            str(entity_uuid): _visible_entity_fact(
                entity_uuid,
                controlled=entity_uuid in self._controlled_entity_uuids,
                observer_uuids=_observers_that_see(entity_uuid, observers),
            )
            for entity_uuid in sorted(visible_entity_uuids, key=str)
            if Entity.get(entity_uuid) is not None
        }
        if self._world is None:
            return facts
        for entity_uuid, fact in self._world.known_entities.items():
            if entity_uuid in facts:
                continue
            facts[entity_uuid] = _remembered_entity_fact(fact)
        return dict(sorted(facts.items()))

    def _known_objects(
        self,
        observers: tuple[Entity, ...],
    ) -> dict[str, ObservationObjectFact]:
        object_observers: dict[UUID, set[str]] = {}
        object_positions: dict[UUID, tuple[int, int]] = {}
        for observer in observers:
            for object_uuid, position in observer.senses.objects.items():
                object_observers.setdefault(object_uuid, set()).add(
                    str(observer.uuid)
                )
                object_positions[object_uuid] = position
        facts: dict[str, ObservationObjectFact] = {}
        for object_uuid in sorted(object_observers, key=str):
            obj = BaseBlock.get(object_uuid)
            if obj is None:
                continue
            facts[str(object_uuid)] = ObservationObjectFact(
                uuid=str(object_uuid),
                name=obj.name or "Object",
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=sorted(object_observers[object_uuid]),
                position=object_positions.get(object_uuid, obj.position),
                map_char=getattr(obj, "map_char", None),
                state=_object_state(obj),
            )
        if self._world is not None:
            for object_uuid, fact in self._world.known_objects.items():
                facts.setdefault(
                    object_uuid,
                    fact.model_copy(
                        update={
                            "knowledge_state": KnowledgeState.REMEMBERED,
                            "observer_uuids": [],
                        }
                    ),
                )
        return dict(sorted(facts.items()))

    def _known_tiles(
        self,
        observers: tuple[Entity, ...],
    ) -> dict[str, ObservationTileFact]:
        visible_by_position: dict[tuple[int, int], set[str]] = {}
        seen_by_position: dict[tuple[int, int], set[str]] = {}
        for observer in observers:
            observer_uuid = str(observer.uuid)
            for position, visible in observer.senses.visible.items():
                if visible:
                    visible_by_position.setdefault(position, set()).add(
                        observer_uuid
                    )
            for position in observer.senses.seen:
                seen_by_position.setdefault(position, set()).add(observer_uuid)

        facts: dict[str, ObservationTileFact] = {}
        for position in sorted(
            set(visible_by_position) | set(seen_by_position)
        ):
            key = _tile_key(position)
            if position in visible_by_position:
                facts[key] = _visible_tile_fact(
                    position,
                    visible_by_position[position],
                )
                continue
            previous = (
                self._world.known_tiles.get(key) if self._world is not None else None
            )
            if previous is None:
                facts[key] = ObservationTileFact(
                    key=key,
                    position=position,
                    knowledge_state=KnowledgeState.SEEN,
                    observer_uuids=sorted(seen_by_position[position]),
                    adjacent_domain=_adjacent_domain_knowledge(position),
                )
            else:
                facts[key] = previous.model_copy(
                    update={
                        "knowledge_state": KnowledgeState.SEEN,
                        "observer_uuids": sorted(seen_by_position[position]),
                    }
                )
        if self._world is not None:
            for key, fact in self._world.known_tiles.items():
                facts.setdefault(
                    key,
                    fact.model_copy(
                        update={
                            "knowledge_state": KnowledgeState.SEEN,
                            "observer_uuids": [],
                        }
                    ),
                )
        return dict(sorted(facts.items()))

    def _encounter_state(
        self,
        *,
        actor: Entity,
        context: TurnContext,
        observers: tuple[Entity, ...],
        visible_entity_uuids: set[UUID],
    ) -> ObservationEncounterState | None:
        if context.encounter_uuid is None:
            return None
        rows: list[ObservationCombatantState] = []
        for entity_uuid in context.initiative_order:
            if entity_uuid not in visible_entity_uuids:
                continue
            entity = Entity.get(entity_uuid)
            if entity is None:
                continue
            rows.append(
                ObservationCombatantState(
                    uuid=str(entity_uuid),
                    name=entity.name,
                    initiative=context.initiative_totals.get(entity_uuid),
                    life_state=entity.health.life_state,
                    is_dead=entity.health.life_state is LifeState.DEAD,
                    is_controlled=entity_uuid in self._controlled_entity_uuids,
                    knowledge_state=KnowledgeState.VISIBLE,
                    observer_uuids=_observers_that_see(entity_uuid, observers),
                )
            )
        subjective_turn_index = next(
            (
                index
                for index, row in enumerate(rows)
                if row.uuid == str(actor.uuid)
            ),
            -1,
        )
        return ObservationEncounterState(
            uuid=str(context.encounter_uuid),
            name=context.encounter_name or "Encounter",
            state=context.encounter_state or "active",
            round_number=context.round_number,
            current_turn_index=subjective_turn_index,
            current_entity_uuid=str(actor.uuid),
            current_entity_name=actor.name,
            turn_started_source_event_cursor=(
                context.turn_started_source_event_cursor
            ),
            initiative_order=rows,
        )


def _observer_state(observer: Entity) -> ObservationObserverState:
    return ObservationObserverState(
        observer_uuid=str(observer.uuid),
        entity_name=observer.name,
        position=observer.position,
        passive_perception=observer.get_passive_perception(),
        sense_modes=[
            {
                "sense_type": mode.sense_type.value,
                "range_feet": mode.range_feet,
            }
            for mode in observer.senses.get_sense_modes()
        ],
        visible_cells=sorted(
            position
            for position, visible in observer.senses.visible.items()
            if visible
        ),
        seen_cells=sorted(observer.senses.seen),
        visible_entity_uuids=sorted(
            str(entity_uuid) for entity_uuid in observer.senses.entities
        ),
        visible_object_uuids=sorted(
            str(object_uuid) for object_uuid in observer.senses.objects
        ),
    )


def _visible_entity_fact(
    entity_uuid: UUID,
    *,
    controlled: bool,
    observer_uuids: list[str],
) -> ObservationEntityFact:
    entity = Entity.get(entity_uuid)
    if entity is None:
        raise ValueError(f"visible entity {entity_uuid} is missing")
    max_hp = (
        entity.health.get_max_hit_dices_points(
            entity.ability_scores.get_ability(
                "constitution"
            ).get_combined_values().normalized_score
        )
        + entity.health.max_hit_points_bonus.normalized_score
    )
    normal_hp = max_hp - entity.health.damage_taken
    temporary_hp = entity.health.temporary_hit_points.normalized_score
    vulnerabilities, resistances, immunities = _damage_affinities(entity)
    conditions = tuple(entity.active_conditions.values())
    return ObservationEntityFact(
        uuid=str(entity.uuid),
        name=entity.name,
        knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=observer_uuids,
        controlled=controlled,
        position=entity.position,
        hp=normal_hp + temporary_hp,
        normal_hp=normal_hp,
        temporary_hp=temporary_hp,
        max_hp=max_hp,
        healing_blocked=entity.health.is_healing_blocked(),
        ac=entity.ac_bonus().normalized_score,
        conditions=list(entity.active_conditions),
        condition_semantic_keys=sorted(
            condition.get_semantic_key() for condition in conditions
        ),
        condition_facts=sorted(
            (
                ObservationConditionFact(
                    semantic_key=condition.get_semantic_key(),
                    removal_triggers=sorted(
                        condition.removal_triggers,
                        key=lambda trigger: trigger.value,
                    ),
                    agency_denial=condition.agency_denial,
                    applied_source_event_cursor=(
                        condition.applied_source_event_cursor
                    ),
                )
                for condition in conditions
            ),
            key=lambda fact: fact.semantic_key,
        ),
        effect_protections=sorted(
            (
                ObservationEffectProtection(
                    protection_id=protection.protection_id,
                    blocked_effect_ids=sorted(protection.blocked_effect_ids),
                    source_condition_semantic_key=condition.get_semantic_key(),
                )
                for condition in conditions
                for protection in condition.outcome_protections
            ),
            key=lambda protection: (
                protection.protection_id,
                protection.source_condition_semantic_key or "",
            ),
        ),
        is_concentrating=any(
            ConditionTag.CONCENTRATION in condition.tags
            for condition in conditions
        ),
        damage_vulnerabilities=vulnerabilities,
        damage_resistances=resistances,
        damage_immunities=immunities,
        creature_type=entity.creature_type.value,
        faction=entity.faction,
        life_state=entity.health.life_state,
        is_dead=entity.health.life_state is LifeState.DEAD,
    )


def _remembered_entity_fact(
    fact: ObservationEntityFact,
) -> ObservationEntityFact:
    return fact.model_copy(
        update={
            "knowledge_state": KnowledgeState.REMEMBERED,
            "observer_uuids": [],
            "controlled": False,
            "hp": None,
            "normal_hp": None,
            "temporary_hp": None,
            "max_hp": None,
            "healing_blocked": None,
            "ac": None,
            "conditions": [],
            "condition_semantic_keys": None,
            "condition_facts": None,
            "effect_protections": None,
            "is_concentrating": False,
            "damage_vulnerabilities": [],
            "damage_resistances": [],
            "damage_immunities": [],
            "creature_type": None,
            "faction": None,
            "life_state": (
                LifeState.DEAD if fact.life_state is LifeState.DEAD else None
            ),
            "is_dead": True if fact.life_state is LifeState.DEAD else None,
        }
    )


def _damage_affinities(entity: Entity) -> tuple[list[str], list[str], list[str]]:
    vulnerabilities: list[str] = []
    resistances: list[str] = []
    immunities: list[str] = []
    for damage_type in DamageType:
        status = entity.health.get_resistance(damage_type)
        if status is ResistanceStatus.VULNERABILITY:
            vulnerabilities.append(damage_type.value)
        elif status is ResistanceStatus.RESISTANCE:
            resistances.append(damage_type.value)
        elif status is ResistanceStatus.IMMUNITY:
            immunities.append(damage_type.value)
    return vulnerabilities, resistances, immunities


def _observers_that_see(
    entity_uuid: UUID,
    observers: tuple[Entity, ...],
) -> list[str]:
    return sorted(
        str(observer.uuid)
        for observer in observers
        if entity_uuid == observer.uuid or entity_uuid in observer.senses.entities
    )


def _visible_tile_fact(
    position: tuple[int, int],
    observer_uuids: Iterable[str],
) -> ObservationTileFact:
    observer_ids = sorted(observer_uuids)
    grid = get_map()
    tile = grid.get_tile(*position)
    if tile is None:
        return ObservationTileFact(
            key=_tile_key(position),
            position=position,
            knowledge_state=KnowledgeState.VISIBLE,
            observer_uuids=observer_ids,
            adjacent_domain=_adjacent_domain_knowledge(position),
        )
    observer_uuid = UUID(observer_ids[0]) if observer_ids else None
    hazardous = (
        grid.is_position_hazardous_for(*position, observer_uuid)
        if grid.has_any_hazards()
        else False
    )
    return ObservationTileFact(
        key=_tile_key(position),
        position=position,
        knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=observer_ids,
        name=tile.name,
        walkable=tile.walkable,
        walking_cost=int(tile.walking_cost.normalized_score),
        is_hazardous=hazardous,
        conditions=list(tile.active_conditions),
        light_level=tile.resolved_light_level.value,
        directional_blocks_movement=_directional_blocks(tile, "movement"),
        directional_blocks_vision=_directional_blocks(tile, "vision"),
        directional_blocks_light=_directional_blocks(tile, "light"),
        directional_blocks_propagation=_directional_blocks(
            tile,
            "propagation",
        ),
        adjacent_domain=_adjacent_domain_knowledge(position),
    )


def _adjacent_domain_knowledge(
    position: tuple[int, int],
) -> dict[AdjacentOffset, SpatialDomainKnowledge]:
    grid = get_map()
    return {
        offset: (
            SpatialDomainKnowledge.INVALID
            if grid.get_tile(
                position[0] + offset.delta[0],
                position[1] + offset.delta[1],
            )
            is None
            else SpatialDomainKnowledge.UNKNOWN
        )
        for offset in AdjacentOffset
    }


def _directional_blocks(tile: Any, channel: str) -> dict[str, bool]:
    return {
        direction: not tile.allows_direction(direction, channel)
        for direction in ("north", "south", "east", "west")
    }


def _object_state(obj: BaseBlock) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for field_name in (
        "is_open",
        "blocked_directions",
        "blocked_channels",
        "blocks_movement",
        "blocks_vision",
        "blocks_vision_field",
        "is_pickable",
        "is_usable",
        "charges",
        "stack_count",
        "is_hazardous",
        "hazardous",
    ):
        if not hasattr(obj, field_name):
            continue
        safe = _json_safe_state_value(getattr(obj, field_name))
        if safe is not None:
            state[field_name] = safe
    return state


def _json_safe_state_value(value: Any) -> Any:
    if callable(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (tuple, list, set)):
        values = (
            sorted(value, key=str) if isinstance(value, set) else value
        )
        return [
            safe
            for item in values
            if (safe := _json_safe_state_value(item)) is not None
        ]
    if isinstance(value, dict):
        return {
            str(key): safe
            for key, item in value.items()
            if (safe := _json_safe_state_value(item)) is not None
        }
    return None


def _tile_key(position: tuple[int, int]) -> str:
    return f"{position[0]},{position[1]}"


def current_source_event_cursor() -> int:
    """Return the objective cursor only for diagnostics/replay correlation."""
    return EventQueue.event_cursor()
