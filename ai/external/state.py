"""Reduced state for out-of-process AI behavior trees."""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field

from ai.observation.models import ObservationMaterializedState


class ExternalEntity(BaseModel):
    """Entity fact reduced for external AI decisions."""

    uuid: str = Field(description="Entity UUID.")
    name: str = Field(description="Known entity display name.")
    position: Tuple[int, int] = Field(description="Known entity grid position.")
    hp: Optional[int] = Field(default=None, description="Known hit points.")
    is_dead: bool = Field(default=False, description="Whether the entity is known dead.")
    faction: Optional[str] = Field(default=None, description="Known faction label.")
    distance_feet: Optional[int] = Field(default=None, description="Manhattan distance from actor in feet.")


class ExternalKnownObject(BaseModel):
    """Object fact reduced for external AI decisions."""

    uuid: str = Field(description="Object UUID.")
    name: str = Field(description="Known object display name.")
    position: Tuple[int, int] = Field(description="Known object grid position.")
    knowledge_state: str = Field(description="Subjective knowledge state.")
    visible_now: bool = Field(description="Whether this object is currently visible.")
    is_open: Optional[bool] = Field(default=None, description="Known open state for doors and similar objects.")


class ExternalActionTarget(BaseModel):
    """Selectable target row normalized from available-actions payloads."""

    index: int = Field(description="Target index accepted by execution endpoints.")
    target_uuid: Optional[str] = Field(default=None, description="Target entity or object UUID.")
    position: Optional[Tuple[int, int]] = Field(default=None, description="Target grid position.")
    target_name: Optional[str] = Field(default=None, description="Target display name.")
    distance: Optional[int] = Field(default=None, description="Distance from actor in feet.")
    path_cost: Optional[int] = Field(default=None, description="Movement path cost.")
    safe_path_cost: Optional[int] = Field(default=None, description="Safe movement path cost.")
    is_path_hazardous: bool = Field(default=False, description="Whether the path crosses known hazards.")
    path: List[Tuple[int, int]] = Field(default_factory=list, description="Concrete path for the row.")
    safe_path: List[Tuple[int, int]] = Field(default_factory=list, description="Alternative safe path for the row.")


class ExternalActionRow(BaseModel):
    """Action row normalized from the engine's legal affordance payload."""

    template_name: str = Field(description="Template name used for command execution.")
    display_name: str = Field(description="Human-readable action name.")
    action_category: str = Field(description="Engine action category.")
    target_type: str = Field(description="Engine target type.")
    can_afford: bool = Field(description="Whether the actor can pay the action cost.")
    valid_targets: List[ExternalActionTarget] = Field(default_factory=list, description="Selectable target rows.")
    is_item_use: bool = Field(default=False, description="Whether this row is provided by an item or object.")
    source_item_uuid: Optional[str] = Field(default=None, description="Item or object UUID that provides the row.")


class ExternalAgentState(BaseModel):
    """Behavior-tree input built from subjective state and legal actions."""

    observation_cursor: int = Field(description="Highest subjective observation cursor represented.")
    session_id: str = Field(description="AI session UUID.")
    controlled_entity_uuids: List[str] = Field(default_factory=list, description="Entities owned by this AI session.")
    active_entity_uuid: Optional[str] = Field(default=None, description="Current active entity UUID when known.")
    is_my_turn: bool = Field(default=False, description="Whether the active entity belongs to this session.")
    actor_uuid: Optional[str] = Field(default=None, description="Controlled active actor UUID.")
    actor_position: Optional[Tuple[int, int]] = Field(default=None, description="Known active actor position.")
    visible_enemies: List[ExternalEntity] = Field(default_factory=list, description="Visible non-controlled living entities.")
    known_closed_doors: List[ExternalKnownObject] = Field(default_factory=list, description="Known closed doors with positions.")
    entity_actions: List[ExternalActionRow] = Field(default_factory=list, description="Entity-targeting legal rows.")
    position_actions: List[ExternalActionRow] = Field(default_factory=list, description="Position-targeting legal rows.")
    self_actions: List[ExternalActionRow] = Field(default_factory=list, description="Self-targeting legal rows.")
    object_actions: List[ExternalActionRow] = Field(default_factory=list, description="Object-targeting legal rows.")

    @property
    def all_actions(self) -> List[ExternalActionRow]:
        """Return all action rows in execution-search order."""
        return self.entity_actions + self.position_actions + self.self_actions + self.object_actions


def reduce_external_agent_state(
    materialized: ObservationMaterializedState | dict[str, Any],
    available_actions_payload: Optional[dict[str, Any]] = None,
) -> ExternalAgentState:
    """Reduce subjective state and legal action rows for behavior trees.

    Args:
        materialized: Materialized subjective observation state.
        available_actions_payload: Serialized available-actions response for the
            active actor, or `None` when the session is not currently acting.

    Returns:
        Compact external-agent decision state.
    """
    if not isinstance(materialized, ObservationMaterializedState):
        materialized = ObservationMaterializedState.model_validate(materialized)

    controlled = list(materialized.session.controlled_entity_uuids)
    active_uuid = materialized.session.active_entity_uuid
    actor_uuid = active_uuid if materialized.session.is_my_turn and active_uuid in controlled else None
    actor_fact = materialized.known_entities.get(actor_uuid) if actor_uuid else None
    actor_position = actor_fact.position if actor_fact is not None else None

    return ExternalAgentState(
        observation_cursor=materialized.observation_cursor,
        session_id=materialized.session.session_id,
        controlled_entity_uuids=controlled,
        active_entity_uuid=active_uuid,
        is_my_turn=materialized.session.is_my_turn,
        actor_uuid=actor_uuid,
        actor_position=actor_position,
        visible_enemies=_visible_enemies(materialized, controlled, actor_position),
        known_closed_doors=_known_closed_doors(materialized),
        entity_actions=_normalize_actions(available_actions_payload, "entity_actions"),
        position_actions=_normalize_actions(available_actions_payload, "position_actions"),
        self_actions=_normalize_actions(available_actions_payload, "self_actions"),
        object_actions=_normalize_actions(available_actions_payload, "object_actions"),
    )


def _visible_enemies(
    materialized: ObservationMaterializedState,
    controlled_entity_uuids: List[str],
    actor_position: Optional[Tuple[int, int]],
) -> List[ExternalEntity]:
    """Return visible, living, non-controlled entities sorted by distance."""
    controlled = set(controlled_entity_uuids)
    enemies: List[ExternalEntity] = []
    for fact in materialized.known_entities.values():
        if fact.uuid in controlled or fact.controlled:
            continue
        if fact.knowledge_state.value != "visible":
            continue
        if fact.position is None:
            continue
        if fact.is_dead is True:
            continue
        enemies.append(ExternalEntity(
            uuid=fact.uuid,
            name=fact.name,
            position=fact.position,
            hp=fact.hp,
            is_dead=bool(fact.is_dead),
            faction=fact.faction,
            distance_feet=_distance_feet(actor_position, fact.position),
        ))
    return sorted(enemies, key=lambda entity: entity.distance_feet if entity.distance_feet is not None else 999_999)


def _known_closed_doors(materialized: ObservationMaterializedState) -> List[ExternalKnownObject]:
    """Return known closed door-like objects sorted by object UUID."""
    doors: List[ExternalKnownObject] = []
    for obj in materialized.known_objects.values():
        if obj.position is None:
            continue
        is_open = obj.state.get("is_open")
        looks_like_door = "door" in obj.name.lower() or "is_open" in obj.state
        if not looks_like_door or is_open is not False:
            continue
        doors.append(ExternalKnownObject(
            uuid=obj.uuid,
            name=obj.name,
            position=obj.position,
            knowledge_state=obj.knowledge_state.value,
            visible_now=obj.knowledge_state.value == "visible",
            is_open=is_open,
        ))
    return sorted(doors, key=lambda door: door.uuid)


def _normalize_actions(
    payload: Optional[dict[str, Any]],
    bucket_name: str,
) -> List[ExternalActionRow]:
    """Normalize one available-actions bucket."""
    if not payload:
        return []
    rows = payload.get(bucket_name, [])
    if not isinstance(rows, list):
        return []
    return [_normalize_action(row) for row in rows if isinstance(row, dict)]


def _normalize_action(row: dict[str, Any]) -> ExternalActionRow:
    """Normalize one serialized available action row."""
    return ExternalActionRow(
        template_name=str(row.get("template_name", "")),
        display_name=str(row.get("display_name") or row.get("template_name") or ""),
        action_category=str(row.get("action_category", "")),
        target_type=str(row.get("target_type", "")),
        can_afford=bool(row.get("can_afford", False)),
        valid_targets=[
            _normalize_target(target)
            for target in row.get("valid_targets", [])
            if isinstance(target, dict)
        ],
        is_item_use=bool(row.get("is_item_use", False)),
        source_item_uuid=row.get("source_item_uuid"),
    )


def _normalize_target(row: dict[str, Any]) -> ExternalActionTarget:
    """Normalize one serialized target row."""
    return ExternalActionTarget(
        index=int(row.get("index", 0)),
        target_uuid=row.get("target_uuid"),
        position=_optional_position(row.get("position")),
        target_name=row.get("target_name"),
        distance=row.get("distance"),
        path_cost=row.get("path_cost"),
        safe_path_cost=row.get("safe_path_cost"),
        is_path_hazardous=bool(row.get("is_path_hazardous", False)),
        path=_positions(row.get("path", [])),
        safe_path=_positions(row.get("safe_path", [])),
    )


def _distance_feet(
    origin: Optional[Tuple[int, int]],
    target: Tuple[int, int],
) -> Optional[int]:
    """Return Manhattan grid distance in feet."""
    if origin is None:
        return None
    return (abs(origin[0] - target[0]) + abs(origin[1] - target[1])) * 5


def _optional_position(value: Any) -> Optional[Tuple[int, int]]:
    """Normalize a nullable JSON position."""
    if value is None:
        return None
    return (int(value[0]), int(value[1]))


def _positions(values: Iterable[Any]) -> List[Tuple[int, int]]:
    """Normalize JSON position arrays."""
    return [(int(value[0]), int(value[1])) for value in values]
