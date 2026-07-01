"""Pydantic contracts for Codex controller tools."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    """Structured error returned by Codex tools."""

    code: str = Field(description="Machine-readable error code.")
    message: str = Field(description="Human-readable error message.")
    status_code: Optional[int] = Field(default=None, description="HTTP status code when applicable.")
    detail: Any = Field(default=None, description="Original error detail when available.")


class BriefEntity(BaseModel):
    """Compact entity fact for Codex turn briefs."""

    uuid: str = Field(description="Entity UUID.")
    name: str = Field(description="Entity display name.")
    position: Optional[Tuple[int, int]] = Field(default=None, description="Known grid position.")
    hp: Optional[int] = Field(default=None, description="Known hit points.")
    max_hp: Optional[int] = Field(default=None, description="Known maximum hit points.")
    ac: Optional[int] = Field(default=None, description="Known armor class.")
    faction: Optional[str] = Field(default=None, description="Known faction.")
    knowledge_state: str = Field(description="Subjective knowledge state.")
    controlled: bool = Field(description="Whether this entity is controlled by this session.")
    is_dead: Optional[bool] = Field(default=None, description="Known death state.")


class BriefObject(BaseModel):
    """Compact object fact for Codex turn briefs."""

    uuid: str = Field(description="Object UUID.")
    name: str = Field(description="Object display name.")
    position: Optional[Tuple[int, int]] = Field(default=None, description="Known grid position.")
    knowledge_state: str = Field(description="Subjective knowledge state.")
    state: dict[str, Any] = Field(default_factory=dict, description="Known object state.")


class BriefResult(BaseModel):
    """Current subjective brief for a Codex session."""

    session_id: str = Field(description="Codex session UUID.")
    observation_cursor: int = Field(description="Observation cursor represented by the brief.")
    is_my_turn: bool = Field(description="Whether a controlled entity is active.")
    active_entity_uuid: Optional[str] = Field(default=None, description="Active entity UUID when known.")
    active_entity_name: Optional[str] = Field(default=None, description="Active entity name when known.")
    controlled_entities: list[BriefEntity] = Field(default_factory=list, description="Controlled entity facts.")
    visible_entities: list[BriefEntity] = Field(default_factory=list, description="Visible entity facts.")
    known_objects: list[BriefObject] = Field(default_factory=list, description="Known object facts.")
    recent_combat_logs: list[dict[str, Any]] = Field(default_factory=list, description="Recent visible combat logs.")


class ActionTargetChoice(BaseModel):
    """Selectable target for one Codex action choice."""

    target_index: int = Field(description="Engine target index.")
    target_uuid: Optional[str] = Field(default=None, description="Target entity or object UUID.")
    target_name: Optional[str] = Field(default=None, description="Target display name.")
    position: Optional[Tuple[int, int]] = Field(default=None, description="Target grid position.")
    distance: Optional[int] = Field(default=None, description="Distance in feet when supplied.")


class ActionChoice(BaseModel):
    """One executable Codex action row."""

    row_id: str = Field(description="Stable CLI-level row reference for execution.")
    bucket: str = Field(description="Available-actions bucket name.")
    template_name: str = Field(description="Engine action template name.")
    display_name: str = Field(description="Human-readable action name.")
    action_category: str = Field(description="Engine action category.")
    target_type: str = Field(description="Engine target type.")
    can_afford: bool = Field(description="Whether the actor can pay the action cost.")
    target: ActionTargetChoice = Field(description="Selected target row.")
    is_item_use: bool = Field(default=False, description="Whether the row came from an item or object.")
    source_item_uuid: Optional[str] = Field(default=None, description="Item or object UUID providing this action.")


class ActionsResult(BaseModel):
    """Available Codex action choices for one entity."""

    session_id: str = Field(description="Codex session UUID.")
    entity_uuid: str = Field(description="Acting entity UUID.")
    basis_cursor: Optional[int] = Field(default=None, description="Observation cursor used as the action basis.")
    computed_at_observation_cursor: Optional[int] = Field(default=None, description="Observation cursor at computation time.")
    choices: list[ActionChoice] = Field(default_factory=list, description="Executable action choices.")
    raw_counts: dict[str, int] = Field(default_factory=dict, description="Original action bucket sizes.")


class ExecuteResult(BaseModel):
    """Result of executing one Codex tool action."""

    status: str = Field(description="Tool execution status.")
    row_id: str = Field(description="Requested row id.")
    payload: dict[str, Any] = Field(default_factory=dict, description="Server action result payload.")
    refreshed_actions: Optional[ActionsResult] = Field(default=None, description="Fresh actions when row resolution failed.")
    error: Optional[ToolError] = Field(default=None, description="Structured tool error when execution failed.")


class WatchResult(BaseModel):
    """Result returned by the blocking watch tool."""

    status: str = Field(description="Watch result status.")
    session_id: str = Field(description="Codex session UUID.")
    observation_cursor: int = Field(description="Latest observation cursor.")
    event: Optional[str] = Field(default=None, description="SSE event name that woke the watcher.")
    brief: BriefResult = Field(description="Current subjective brief.")
    frame: Optional[dict[str, Any]] = Field(default=None, description="Observation frame that woke the watcher.")
