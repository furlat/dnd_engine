"""Canonical subjective world projection for every AI execution mode.

This module owns knowledge semantics.  It knows engine entities, senses, tiles,
and immutable remembered facts, but it knows nothing about HTTP sessions,
journals, subscriptions, or controller transport.  Native policies consume the
projected world directly; server transports wrap the same facts in cursored
frames.
"""

from __future__ import annotations

from typing import Any, Iterable
from uuid import UUID

from dnd.ai.contracts.control import DecisionEpoch
from dnd.ai.contracts.observation import (
    AdjacentOffset,
    KnowledgeState,
    ObservationConditionFact,
    ObservationEffectProtection,
    ObservationEncounterState,
    ObservationEntityFact,
    ObservationObjectFact,
    ObservationObserverState,
    ObservationSessionState,
    ObservationSpatialEffectFact,
    ObservationTileFact,
    SpatialDomainKnowledge,
    SubjectiveWorldState,
)
from dnd.blocks.base_item import BaseItem
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_tiles import Tile
from dnd.core.condition_types import ConditionTag
from dnd.core.creature_types import DamageType
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemObservationState
from dnd.core.life_types import LifeState
from dnd.core.modifiers import ResistanceStatus
from dnd.entity import Entity
from dnd.spatial_effects import SpatialEffect


_adjacent_domain_cache_revision: int | None = None
_adjacent_domain_cache: dict[
    tuple[int, int],
    dict[AdjacentOffset, SpatialDomainKnowledge],
] = {}


def clear_subjective_projection_fact_cache() -> None:
    """Clear projection-only spatial caches after an engine reset."""
    global _adjacent_domain_cache_revision
    _adjacent_domain_cache_revision = None
    _adjacent_domain_cache.clear()


def resolve_controlled_observers(
    controlled_entity_uuids: Iterable[UUID],
) -> tuple[Entity, ...]:
    """Resolve live controlled entities in stable order."""
    return tuple(
        entity
        for entity_uuid in sorted(set(controlled_entity_uuids), key=str)
        if (entity := Entity.get(entity_uuid)) is not None
    )


def project_subjective_world(
    *,
    observation_cursor: int,
    session: ObservationSessionState,
    encounter: ObservationEncounterState | None,
    controlled_entity_uuids: Iterable[UUID],
    prior_world: SubjectiveWorldState | None,
    combat_logs: Iterable[dict[str, Any]] = (),
    current_epoch: DecisionEpoch | None = None,
    epoch_cursor: int | None = None,
) -> SubjectiveWorldState:
    """Project one complete retained AI world from current engine knowledge."""
    controlled = frozenset(controlled_entity_uuids)
    observers = resolve_controlled_observers(controlled)
    if controlled and not observers:
        raise ValueError("subjective projection has no live controlled observers")
    return SubjectiveWorldState(
        observation_cursor=observation_cursor,
        session=session,
        encounter=encounter,
        observers={
            str(observer.uuid): project_observer_state(observer)
            for observer in observers
        },
        known_entities=project_known_entities(
            controlled_entity_uuids=controlled,
            observers=observers,
            prior_world=prior_world,
        ),
        known_objects=project_known_objects(
            observers=observers,
            prior_world=prior_world,
        ),
        known_tiles=project_known_tiles(
            observers=observers,
            prior_world=prior_world,
        ),
        combat_logs=list(combat_logs),
        current_epoch=current_epoch,
        epoch_cursor=observation_cursor if epoch_cursor is None else epoch_cursor,
    )


def project_observer_state(observer: Entity) -> ObservationObserverState:
    """Project one controlled observer's current sensory cache."""
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


def project_known_entities(
    *,
    controlled_entity_uuids: Iterable[UUID],
    observers: Iterable[Entity],
    prior_world: SubjectiveWorldState | None,
) -> dict[str, ObservationEntityFact]:
    """Project visible entities and retain conservative last-known facts."""
    controlled = frozenset(controlled_entity_uuids)
    observer_rows = tuple(observers)
    visible = {
        entity_uuid
        for observer in observer_rows
        for entity_uuid in observer.senses.entities
    }
    visible.update(controlled)
    facts = {
        str(entity_uuid): project_entity_fact(
            entity_uuid,
            controlled_entity_uuids=controlled,
            observers=observer_rows,
        )
        for entity_uuid in sorted(visible, key=str)
        if Entity.get(entity_uuid) is not None
    }
    if prior_world is not None:
        for entity_uuid, fact in prior_world.known_entities.items():
            facts.setdefault(entity_uuid, remember_entity_fact(fact))
    return dict(sorted(facts.items()))


def project_entity_fact(
    entity_uuid: UUID,
    *,
    controlled_entity_uuids: Iterable[UUID],
    observers: Iterable[Entity],
    fallback_state: KnowledgeState = KnowledgeState.VISIBLE,
    remembered_position: tuple[int, int] | None = None,
) -> ObservationEntityFact:
    """Project one entity under explicit current or event-time evidence."""
    entity = Entity.get(entity_uuid)
    if entity is None:
        raise ValueError(f"known entity {entity_uuid} is missing")
    controlled = entity_uuid in frozenset(controlled_entity_uuids)
    observer_uuids = observers_that_see(entity_uuid, observers)
    visible = bool(observer_uuids) or controlled
    knowledge_state = KnowledgeState.VISIBLE if visible else fallback_state
    if not visible and knowledge_state is KnowledgeState.UNKNOWN:
        raise ValueError(f"entity {entity_uuid} has no subjective evidence")

    include_live_details = visible or knowledge_state is KnowledgeState.VISIBLE
    if include_live_details:
        (
            hp,
            normal_hp,
            temporary_hp,
            max_hp,
            life_state,
            is_dead,
            healing_blocked,
        ) = entity_health_details(entity)
        vulnerabilities, resistances, immunities = damage_affinities(entity)
        conditions = tuple(entity.active_conditions.values())
    else:
        hp = normal_hp = temporary_hp = max_hp = None
        life_state = None
        is_dead = None
        healing_blocked = None
        vulnerabilities = resistances = immunities = []
        conditions = ()

    return ObservationEntityFact(
        uuid=str(entity.uuid),
        name=entity.name,
        knowledge_state=knowledge_state,
        observer_uuids=observer_uuids,
        controlled=controlled,
        position=entity.position if include_live_details else remembered_position,
        hp=hp,
        normal_hp=normal_hp,
        temporary_hp=temporary_hp,
        max_hp=max_hp,
        healing_blocked=healing_blocked,
        ac=entity.ac_bonus().normalized_score if include_live_details else None,
        conditions=list(entity.active_conditions) if include_live_details else [],
        condition_semantic_keys=(
            sorted(condition_semantic_key(condition) for condition in conditions)
            if include_live_details
            else None
        ),
        condition_facts=(
            sorted(
                (project_condition_fact(condition) for condition in conditions),
                key=lambda fact: fact.semantic_key,
            )
            if include_live_details
            else None
        ),
        effect_protections=(
            project_effect_protections(entity) if include_live_details else None
        ),
        is_concentrating=(
            any(ConditionTag.CONCENTRATION in condition.tags for condition in conditions)
            if include_live_details
            else False
        ),
        damage_vulnerabilities=vulnerabilities,
        damage_resistances=resistances,
        damage_immunities=immunities,
        creature_type=entity.creature_type.value if include_live_details else None,
        faction=entity.faction if include_live_details else None,
        life_state=life_state,
        is_dead=is_dead,
    )


def remember_entity_fact(fact: ObservationEntityFact) -> ObservationEntityFact:
    """Strip mutable/private details from an entity that is no longer visible."""
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
            "life_state": LifeState.DEAD if fact.life_state is LifeState.DEAD else None,
            "is_dead": True if fact.life_state is LifeState.DEAD else None,
        }
    )


def entity_health_details(
    entity: Entity,
) -> tuple[int, int, int, int, LifeState, bool, bool]:
    """Return the canonical visible health projection for one entity."""
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
    return (
        normal_hp + temporary_hp,
        normal_hp,
        temporary_hp,
        max_hp,
        entity.health.life_state,
        entity.health.life_state is LifeState.DEAD,
        entity.health.is_healing_blocked(),
    )


def damage_affinities(entity: Entity) -> tuple[list[str], list[str], list[str]]:
    """Return visible damage affinity labels for an entity."""
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


def condition_semantic_key(condition: BaseCondition) -> str:
    """Return one canonical condition identity."""
    return condition.get_semantic_key()


def project_condition_fact(
    condition: BaseCondition,
    *,
    applied_source_event_cursor: int | None = None,
) -> ObservationConditionFact:
    """Project public condition behavior used by AI policy."""
    return ObservationConditionFact(
        semantic_key=condition_semantic_key(condition),
        removal_triggers=sorted(
            condition.removal_triggers,
            key=lambda trigger: trigger.value,
        ),
        agency_denial=condition.agency_denial,
        applied_source_event_cursor=(
            condition.applied_source_event_cursor
            if applied_source_event_cursor is None
            else applied_source_event_cursor
        ),
    )


def project_effect_protections(
    entity: Entity,
) -> list[ObservationEffectProtection]:
    """Project typed protections supplied by visible conditions."""
    return sorted(
        (
            ObservationEffectProtection(
                protection_id=protection.protection_id,
                blocked_effect_ids=sorted(protection.blocked_effect_ids),
                source_condition_semantic_key=condition_semantic_key(condition),
            )
            for condition in entity.active_conditions.values()
            for protection in condition.outcome_protections
        ),
        key=lambda protection: (
            protection.protection_id,
            protection.source_condition_semantic_key or "",
        ),
    )


def observers_that_see(
    entity_uuid: UUID,
    observers: Iterable[Entity],
) -> list[str]:
    """Return the controlled observers with current entity evidence."""
    return sorted(
        str(observer.uuid)
        for observer in observers
        if entity_uuid == observer.uuid or entity_uuid in observer.senses.entities
    )


def observers_that_see_position(
    position: tuple[int, int],
    observers: Iterable[Entity],
) -> list[str]:
    """Return the controlled observers with current position evidence."""
    return sorted(
        str(observer.uuid)
        for observer in observers
        if observer.senses.visible.get(position, False)
    )


def project_known_objects(
    *,
    observers: Iterable[Entity],
    prior_world: SubjectiveWorldState | None,
) -> dict[str, ObservationObjectFact]:
    """Project visible objects and retain their last-known public facts."""
    object_observers: dict[UUID, set[str]] = {}
    object_positions: dict[UUID, tuple[int, int]] = {}
    for observer in observers:
        for object_uuid, position in observer.senses.objects.items():
            object_observers.setdefault(object_uuid, set()).add(str(observer.uuid))
            object_positions[object_uuid] = position
    facts = {
        str(object_uuid): fact
        for object_uuid in sorted(object_observers, key=str)
        if (
            fact := project_object_fact(
                object_uuid,
                object_positions.get(object_uuid),
                object_observers[object_uuid],
            )
        )
        is not None
    }
    if prior_world is not None:
        for object_uuid, fact in prior_world.known_objects.items():
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


def project_object_fact(
    object_uuid: UUID,
    position: tuple[int, int] | None,
    observer_uuids: Iterable[str],
) -> ObservationObjectFact | None:
    """Project one currently visible engine object."""
    obj = BaseBlock.get(object_uuid)
    if not isinstance(obj, BaseItem):
        return None
    observer_ids = tuple(sorted(observer_uuids))
    return ObservationObjectFact(
        uuid=str(object_uuid),
        name=obj.name or "Object",
        knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=list(observer_ids),
        position=position or obj.position,
        map_char=obj.get_map_char(),
        state=project_object_state(obj, observer_ids),
    )


def project_known_tiles(
    *,
    observers: Iterable[Entity],
    prior_world: SubjectiveWorldState | None,
) -> dict[str, ObservationTileFact]:
    """Project current tiles while retaining immutable event-time memories."""
    visible_by_position: dict[tuple[int, int], set[str]] = {}
    seen_by_position: dict[tuple[int, int], set[str]] = {}
    for observer in observers:
        observer_uuid = str(observer.uuid)
        for position, visible in observer.senses.visible.items():
            if visible:
                visible_by_position.setdefault(position, set()).add(observer_uuid)
        for position in observer.senses.seen:
            seen_by_position.setdefault(position, set()).add(observer_uuid)

    facts: dict[str, ObservationTileFact] = {}
    hazards_present = get_map().has_any_hazards()
    for position in sorted(set(visible_by_position) | set(seen_by_position)):
        key = subjective_tile_key(position)
        if position in visible_by_position:
            facts[key] = project_visible_tile_fact(
                position,
                visible_by_position[position],
                hazards_present=hazards_present,
            )
            continue
        previous = prior_world.known_tiles.get(key) if prior_world is not None else None
        facts[key] = (
            previous.model_copy(
                update={
                    "knowledge_state": KnowledgeState.SEEN,
                    "observer_uuids": sorted(seen_by_position[position]),
                }
            )
            if previous is not None
            else ObservationTileFact(
                key=key,
                position=position,
                knowledge_state=KnowledgeState.SEEN,
                observer_uuids=sorted(seen_by_position[position]),
                adjacent_domain=adjacent_domain_knowledge(position),
            )
        )
    if prior_world is not None:
        for key, fact in prior_world.known_tiles.items():
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


def project_visible_tile_fact(
    position: tuple[int, int],
    observer_uuids: Iterable[str],
    *,
    hazards_present: bool | None = None,
) -> ObservationTileFact:
    """Project one visible tile from current public engine facts."""
    observer_ids = sorted(observer_uuids)
    grid = get_map()
    tile = grid.get_tile(*position)
    if tile is None:
        return ObservationTileFact(
            key=subjective_tile_key(position),
            position=position,
            knowledge_state=KnowledgeState.VISIBLE,
            observer_uuids=observer_ids,
            adjacent_domain=adjacent_domain_knowledge(position),
        )
    first_observer = observer_ids[0] if observer_ids else None
    observers = [
        observer
        for observer_id in observer_ids
        if (observer := BaseBlock.get(UUID(observer_id))) is not None
    ]
    visible_conditions = list(tile.active_conditions.values())
    visible_effects: list[SpatialEffect] = []
    for block in grid.get_spatial_effect_blocks_at(position):
        if not isinstance(block, SpatialEffect):
            raise TypeError(
                "Grid spatial-effect index contains a non-effect block",
            )
        effect = block
        controllers = tuple(effect.active_conditions.values())
        if controllers and not any(
            controller.condition_stealth_dc is None
            or controller.condition_stealth_dc
            < observer.get_passive_perception()
            for controller in controllers
            for observer in observers
        ):
            continue
        visible_effects.append(effect)
        visible_conditions.extend(effect.active_conditions.values())
    visible_condition_names = sorted(
        condition.name
        for condition in visible_conditions
        if (
            condition.name is not None
            and (
                condition.condition_stealth_dc is None
                or any(
                    condition.condition_stealth_dc
                    < observer.get_passive_perception()
                    for observer in observers
                )
            )
        )
    )
    is_hazardous = (
        grid.is_position_hazardous_for(
            position[0],
            position[1],
            UUID(first_observer) if first_observer else None,
        )
        if (grid.has_any_hazards() if hazards_present is None else hazards_present)
        else False
    )
    return ObservationTileFact(
        key=subjective_tile_key(position),
        position=position,
        knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=observer_ids,
        name=tile.name,
        walkable=tile.walkable,
        walking_cost=int(tile.walking_cost.normalized_score),
        is_hazardous=is_hazardous,
        conditions=visible_condition_names,
        spatial_effects=[
            ObservationSpatialEffectFact(
                runtime_uuid=str(effect.uuid),
                content_ref=effect.content_ref,
                layer=effect.layer,
                anchor_kind=effect.anchor_kind,
                trigger_kinds=sorted(
                    effect.trigger_kinds,
                    key=lambda trigger: trigger.value,
                ),
            )
            for effect in sorted(
                visible_effects,
                key=lambda row: (
                    row.layer.value,
                    row.content_ref.identity_key,
                    str(row.uuid),
                ),
            )
        ],
        light_level=tile.resolved_light_level.value,
        directional_blocks_movement=directional_blocks(tile, "movement"),
        directional_blocks_vision=directional_blocks(tile, "vision"),
        directional_blocks_light=directional_blocks(tile, "light"),
        directional_blocks_propagation=directional_blocks(tile, "propagation"),
        adjacent_domain=adjacent_domain_knowledge(position),
    )


def adjacent_domain_knowledge(
    position: tuple[int, int],
) -> dict[AdjacentOffset, SpatialDomainKnowledge]:
    """Disclose only known local boundaries around one perceived tile."""
    global _adjacent_domain_cache_revision
    grid = get_map()
    revision = grid.movement_revision
    if _adjacent_domain_cache_revision != revision:
        _adjacent_domain_cache_revision = revision
        _adjacent_domain_cache.clear()
    cached = _adjacent_domain_cache.get(position)
    if cached is not None:
        return dict(cached)
    result = {
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
    _adjacent_domain_cache[position] = result
    return dict(result)


def directional_blocks(tile: Tile, channel: str) -> dict[str, bool]:
    """Return visible directional blockers for one tile channel."""
    return {
        direction: not tile.allows_direction(direction, channel)
        for direction in ("north", "south", "east", "west")
    }


def project_object_state(
    obj: BaseItem,
    observer_uuids: Iterable[str],
) -> ItemObservationState:
    """Return the item's closed state under the authorized observer union."""
    observer_ids = tuple(observer_uuids)
    requesting_entity_uuid = (
        UUID(observer_ids[0])
        if observer_ids
        else None
    )
    state = obj.to_item_observation_state(requesting_entity_uuid)
    if any(obj.is_hazardous_for(UUID(observer_uuid)) for observer_uuid in observer_ids):
        return state.model_copy(update={"is_hazardous": True})
    return state


def subjective_tile_key(position: tuple[int, int]) -> str:
    """Return the stable key for one subjective tile fact."""
    return f"{position[0]},{position[1]}"


__all__ = [
    "adjacent_domain_knowledge",
    "clear_subjective_projection_fact_cache",
    "condition_semantic_key",
    "damage_affinities",
    "directional_blocks",
    "entity_health_details",
    "observers_that_see",
    "observers_that_see_position",
    "project_condition_fact",
    "project_effect_protections",
    "project_entity_fact",
    "project_known_entities",
    "project_known_objects",
    "project_known_tiles",
    "project_object_fact",
    "project_object_state",
    "project_observer_state",
    "project_subjective_world",
    "project_visible_tile_fact",
    "remember_entity_fact",
    "resolve_controlled_observers",
    "subjective_tile_key",
]
