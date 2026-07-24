"""Pydantic models for session-subjective observation streams."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from server.agent_protocol.control import CommandResult, DecisionEpoch
from dnd.core.condition_types import ConditionAgencyDenial, ConditionRemovalTrigger
from dnd.core.life_types import LifeState


class KnowledgeState(str, Enum):
    """Subjective knowledge state for a fact in the observation layer."""

    VISIBLE = "visible"
    SEEN = "seen"
    REMEMBERED = "remembered"
    UNKNOWN = "unknown"


class AdjacentOffset(str, Enum):
    """Stable eight-neighbor offset keys for local spatial-domain knowledge."""

    NEGATIVE_X_NEGATIVE_Y = "-1,-1"
    NEGATIVE_X_ZERO_Y = "-1,0"
    NEGATIVE_X_POSITIVE_Y = "-1,1"
    ZERO_X_NEGATIVE_Y = "0,-1"
    ZERO_X_POSITIVE_Y = "0,1"
    POSITIVE_X_NEGATIVE_Y = "1,-1"
    POSITIVE_X_ZERO_Y = "1,0"
    POSITIVE_X_POSITIVE_Y = "1,1"

    @property
    def delta(self) -> Tuple[int, int]:
        """Return the integer coordinate delta encoded by this key."""
        dx, dy = self.value.split(",", maxsplit=1)
        return int(dx), int(dy)


class SpatialDomainKnowledge(str, Enum):
    """Subjective validity of one coordinate adjacent to a known tile."""

    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class ObservationFrameType(str, Enum):
    """Top-level frame categories emitted by the observation projector."""

    EVENT = "event"
    COMBAT_LOG = "combat_log"
    PATCH = "patch"
    STATE_REPLACEMENT = "state_replacement"
    DECISION_EPOCH = "decision_epoch"
    COMMAND_RESULT = "command_result"


class ObservationSourceKind(str, Enum):
    """Causal source category for a subjective observation frame."""

    ENGINE_EVENT = "engine_event"
    COMBAT_LOG = "combat_log"
    SENSORY_EVENT = "sensory_event"
    CONTROLLER_COMMAND = "controller_command"
    DECISION_EPOCH = "decision_epoch"
    SESSION_CONTROL = "session_control"


class ObservationPatchType(str, Enum):
    """Patch categories understood by the materialized observation state."""

    SESSION = "session"
    ENCOUNTER = "encounter"
    OBSERVER = "observer"
    ENTITY = "entity"
    OBJECT = "object"
    TILE = "tile"
    COMBAT_LOG = "combat_log"
    DECISION_EPOCH = "decision_epoch"
    COMMAND_RESULT = "command_result"


class ObservationSessionState(BaseModel):
    """Session identity and turn authority visible to one controller."""

    session_id: str = Field(description="Session UUID that owns this subjective observation stream.")
    player_type: str = Field(description="Controller type associated with the session.")
    name: str = Field(description="Display name for the session.")
    connection_status: str = Field(description="Current connection status for the session.")
    controlled_entity_uuids: List[str] = Field(default_factory=list, description="Entity UUIDs controlled by the session.")
    active_entity_uuid: Optional[str] = Field(default=None, description="Current acting entity UUID when visible to this session.")
    active_entity_name: Optional[str] = Field(default=None, description="Current acting entity name when visible to this session.")
    is_my_turn: bool = Field(default=False, description="Whether the current active entity belongs to this session.")


class ObservationCombatantState(BaseModel):
    """Initiative-row state as known to the observing session."""

    uuid: Optional[str] = Field(default=None, description="Combatant UUID when known to the session.")
    name: str = Field(description="Combatant display name or an unknown placeholder.")
    initiative: Optional[int] = Field(default=None, description="Initiative total when known.")
    life_state: Optional[LifeState] = Field(default=None, description="Authoritative lifecycle state when known.")
    is_dead: Optional[bool] = Field(default=None, description="Death state when known.")
    is_controlled: bool = Field(default=False, description="Whether this combatant is controlled by the session.")
    knowledge_state: KnowledgeState = Field(description="Subjective knowledge state for this combatant.")
    observer_uuids: List[str] = Field(default_factory=list, description="Controlled observers that currently know this combatant.")


class ObservationEncounterState(BaseModel):
    """Encounter and turn state projected into one session's knowledge."""

    uuid: str = Field(description="Encounter UUID serialized as text.")
    name: str = Field(description="Encounter display name.")
    state: str = Field(description="Encounter lifecycle state.")
    round_number: int = Field(description="Current combat round.")
    current_turn_index: int = Field(description="Current subjective initiative index, or -1 when the active combatant is unknown.")
    current_entity_uuid: Optional[str] = Field(default=None, description="Current acting entity UUID when known.")
    current_entity_name: Optional[str] = Field(default=None, description="Current acting entity name when known.")
    turn_started_source_event_cursor: Optional[int] = Field(
        default=None,
        ge=0,
        description="Source event cursor of the known current turn-start boundary.",
    )
    initiative_order: List[ObservationCombatantState] = Field(default_factory=list, description="Initiative rows currently visible or controlled by the session.")


class ObservationObserverState(BaseModel):
    """Per-controlled-entity senses and perception cache exposed to the session."""

    observer_uuid: str = Field(description="Controlled entity UUID whose senses produced this observer state.")
    entity_name: str = Field(description="Controlled entity display name.")
    position: Tuple[int, int] = Field(description="Observer's current grid position.")
    passive_perception: int = Field(description="Observer passive perception.")
    sense_modes: List[Dict[str, Any]] = Field(default_factory=list, description="Active sense modes for this observer.")
    visible_cells: List[Tuple[int, int]] = Field(default_factory=list, description="Cells currently visible to this observer.")
    seen_cells: List[Tuple[int, int]] = Field(default_factory=list, description="Cells previously seen by this observer.")
    visible_entity_uuids: List[str] = Field(default_factory=list, description="Entity UUIDs currently visible to this observer.")
    visible_object_uuids: List[str] = Field(default_factory=list, description="Object UUIDs currently visible to this observer.")


class ObservationEffectProtection(BaseModel):
    """Visible condition-owned protection against identified effects."""

    protection_id: str = Field(description="Stable identity of the protection rule.")
    blocked_effect_ids: List[str] = Field(
        default_factory=list,
        description="Stable effect identities fully blocked by the protection.",
    )
    source_condition_semantic_key: Optional[str] = Field(
        default=None,
        description="Stable visible condition type that supplied the protection.",
    )


class ObservationConditionFact(BaseModel):
    """Visible runtime semantics for one active condition."""

    semantic_key: str = Field(description="Stable condition type identity.")
    removal_triggers: List[ConditionRemovalTrigger] = Field(
        default_factory=list,
        description="Visible state transitions that remove this condition.",
    )
    agency_denial: ConditionAgencyDenial = Field(
        default=ConditionAgencyDenial.NONE,
        description="Turn agency denied while this complete condition remains active.",
    )
    applied_source_event_cursor: Optional[int] = Field(
        default=None,
        ge=0,
        description="Source event cursor of the condition application boundary.",
    )


class ObservationEntityFact(BaseModel):
    """Subjective entity fact known by a session."""

    uuid: str = Field(description="Entity UUID serialized as text.")
    name: str = Field(description="Entity display name when known.")
    knowledge_state: KnowledgeState = Field(description="How the session currently knows this entity.")
    observer_uuids: List[str] = Field(default_factory=list, description="Controlled observers that currently see or remember this entity.")
    controlled: bool = Field(default=False, description="Whether the entity is controlled by the session.")
    position: Optional[Tuple[int, int]] = Field(default=None, description="Known or last-known grid position.")
    hp: Optional[int] = Field(default=None, description="Known current hit points.")
    normal_hp: Optional[int] = Field(
        default=None,
        description="Known current restorable hit points before temporary protection.",
    )
    temporary_hp: Optional[int] = Field(
        default=None,
        ge=0,
        description="Known temporary hit points layered over normal hit points.",
    )
    max_hp: Optional[int] = Field(default=None, description="Known maximum hit points.")
    healing_blocked: Optional[bool] = Field(
        default=None,
        description="Whether the entity is currently unable to regain normal hit points.",
    )
    ac: Optional[int] = Field(default=None, description="Known Armor Class.")
    conditions: List[str] = Field(default_factory=list, description="Known active condition names.")
    condition_semantic_keys: Optional[List[str]] = Field(
        default=None,
        description="Known stable active condition type keys; None means this detail is not currently known.",
    )
    condition_facts: Optional[List[ObservationConditionFact]] = Field(
        default=None,
        description="Visible typed lifecycle facts; None means condition details are not currently known.",
    )
    effect_protections: Optional[List[ObservationEffectProtection]] = Field(
        default=None,
        description="Visible typed protections; None means live protection details are unknown.",
    )
    is_concentrating: bool = Field(
        default=False,
        description="Whether the visible entity has a typed active concentration condition.",
    )
    damage_vulnerabilities: List[str] = Field(default_factory=list, description="Known damage types that are especially effective.")
    damage_resistances: List[str] = Field(default_factory=list, description="Known damage types that are reduced.")
    damage_immunities: List[str] = Field(default_factory=list, description="Known damage types that have no effect.")
    creature_type: Optional[str] = Field(default=None, description="Known creature type when currently observable.")
    faction: Optional[str] = Field(default=None, description="Known faction label.")
    life_state: Optional[LifeState] = Field(default=None, description="Known authoritative lifecycle state.")
    is_dead: Optional[bool] = Field(default=None, description="Known death state.")


class ObservationObjectFact(BaseModel):
    """Subjective object fact known by a session."""

    uuid: str = Field(description="Object UUID serialized as text.")
    name: str = Field(description="Object display name when known.")
    knowledge_state: KnowledgeState = Field(description="How the session currently knows this object.")
    observer_uuids: List[str] = Field(default_factory=list, description="Controlled observers that currently see or remember this object.")
    position: Optional[Tuple[int, int]] = Field(default=None, description="Known or last-known grid position.")
    map_char: Optional[str] = Field(default=None, description="Map glyph used by object renderers when known.")
    state: Dict[str, Any] = Field(default_factory=dict, description="Known object state fields.")


class ObservationTileFact(BaseModel):
    """Subjective tile fact known by a session."""

    key: str = Field(description="Stable tile key in the form 'x,y'.")
    position: Tuple[int, int] = Field(description="Tile grid position.")
    knowledge_state: KnowledgeState = Field(description="How the session currently knows this tile.")
    observer_uuids: List[str] = Field(default_factory=list, description="Controlled observers that see or have seen this tile.")
    name: Optional[str] = Field(default=None, description="Terrain name when currently visible.")
    walkable: Optional[bool] = Field(default=None, description="Walkability when currently visible.")
    walking_cost: Optional[int] = Field(default=None, description="Movement cost when currently visible.")
    is_hazardous: Optional[bool] = Field(default=None, description="Hazard state when currently visible.")
    conditions: List[str] = Field(default_factory=list, description="Known visible tile condition names.")
    light_level: Optional[int] = Field(default=None, description="Resolved light level when currently visible.")
    directional_blocks_movement: Dict[str, bool] = Field(default_factory=dict, description="Visible directional movement blockers.")
    directional_blocks_vision: Dict[str, bool] = Field(default_factory=dict, description="Visible directional vision blockers.")
    directional_blocks_light: Dict[str, bool] = Field(default_factory=dict, description="Visible directional light blockers.")
    directional_blocks_propagation: Dict[str, bool] = Field(default_factory=dict, description="Visible directional propagation blockers.")
    adjacent_domain: Dict[AdjacentOffset, SpatialDomainKnowledge] = Field(
        default_factory=dict,
        description=(
            "Subjective validity of adjacent coordinates; unknown reveals no "
            "terrain or occupancy, while invalid records a perceived map boundary."
        ),
    )


class ObservationStateReplacement(BaseModel):
    """Complete subjective materialization carried by a control-boundary frame."""

    session: ObservationSessionState = Field(description="Session state after the control transition.")
    encounter: Optional[ObservationEncounterState] = Field(default=None, description="Subjective encounter state after the transition.")
    observers: List[ObservationObserverState] = Field(default_factory=list, description="Complete controlled-observer set after the transition.")
    known_entities: List[ObservationEntityFact] = Field(default_factory=list, description="Complete entity knowledge after the transition.")
    known_objects: List[ObservationObjectFact] = Field(default_factory=list, description="Complete object knowledge after the transition.")
    known_tiles: List[ObservationTileFact] = Field(default_factory=list, description="Complete tile knowledge after the transition.")
    combat_logs: List[Dict[str, Any]] = Field(default_factory=list, description="Complete visible combat-log history after the transition.")
    current_epoch: Optional[DecisionEpoch] = Field(default=None, description="Decision epoch after the transition, when already available.")


class ObservationPatch(BaseModel):
    """Single mutation to a materialized subjective observation state."""

    patch_type: ObservationPatchType = Field(description="Patch category.")
    reason: str = Field(description="Reason or source event category for the patch.")
    observer_uuid: Optional[str] = Field(default=None, description="Observer UUID associated with this patch when applicable.")
    entity_uuid: Optional[str] = Field(default=None, description="Entity UUID associated with this patch when applicable.")
    object_uuid: Optional[str] = Field(default=None, description="Object UUID associated with this patch when applicable.")
    tile_key: Optional[str] = Field(default=None, description="Tile key associated with this patch when applicable.")
    data: Dict[str, Any] = Field(default_factory=dict, description="Patch payload in JSON-compatible form.")


class ObservationFrame(BaseModel):
    """Cursor-addressed subjective update frame for one session."""

    observation_cursor: int = Field(description="Session-local cursor after this frame is observed.")
    frame_type: ObservationFrameType = Field(description="Frame category.")
    source_kind: Optional[ObservationSourceKind] = Field(default=None, description="Causal source category for this subjective frame.")
    source_command_id: Optional[str] = Field(default=None, description="Controller command id that caused this frame, when applicable.")
    event_type: Optional[str] = Field(default=None, description="Source engine event type when this frame came from an event.")
    event_uuid: Optional[str] = Field(default=None, description="Source event UUID for debugging and reconciliation.")
    lineage_uuid: Optional[str] = Field(default=None, description="Source event lineage UUID for debugging and reconciliation.")
    phase: Optional[str] = Field(default=None, description="Source event phase when applicable.")
    source_event_cursor: Optional[int] = Field(default=None, description="Raw engine event cursor paired with this frame.")
    source_combat_log_cursor: Optional[int] = Field(default=None, description="Raw combat-log cursor paired with this frame.")
    patches: List[ObservationPatch] = Field(default_factory=list, description="Patches produced by this frame.")
    combat_log: Optional[Dict[str, Any]] = Field(default=None, description="Filtered combat-log entry when visible to the session.")
    state_replacement: Optional[ObservationStateReplacement] = Field(
        default=None,
        description="Complete subjective state replacement for rare session-control boundaries.",
    )
    decision_epoch: Optional[DecisionEpoch] = Field(default=None, description="Current decision epoch after this frame, if the session can act.")
    command_result: Optional[CommandResult] = Field(default=None, description="Command result paired with this frame, when applicable.")


class ObservationFramesResponse(BaseModel):
    """Paged subjective frame response for replay and polling."""

    frames: List[ObservationFrame] = Field(default_factory=list, description="Projected frames after the requested observation cursor.")
    count: int = Field(description="Number of frames returned.")
    total: int = Field(description="Total projected frames currently visible to the session.")
    next_observation_cursor: int = Field(description="Cursor after the final returned frame, or the requested cursor when empty.")


class ObservationSnapshot(BaseModel):
    """Full materialization seed for a session-subjective observation stream."""

    observation_cursor: int = Field(description="Session-local observation cursor represented by this snapshot.")
    source_event_cursor: int = Field(description="Raw engine event cursor at snapshot time.")
    source_combat_log_cursor: int = Field(description="Raw combat-log cursor at snapshot time.")
    session: ObservationSessionState = Field(description="Session identity and turn state.")
    encounter: Optional[ObservationEncounterState] = Field(default=None, description="Encounter state when an encounter exists.")
    observers: List[ObservationObserverState] = Field(default_factory=list, description="Per-controlled-entity observer states.")
    known_entities: List[ObservationEntityFact] = Field(default_factory=list, description="Entity facts known to this session.")
    known_objects: List[ObservationObjectFact] = Field(default_factory=list, description="Object facts known to this session.")
    known_tiles: List[ObservationTileFact] = Field(default_factory=list, description="Tile facts known to this session.")
    combat_logs: List[Dict[str, Any]] = Field(default_factory=list, description="Visible combat-log entries known to this session.")
    current_epoch: Optional[DecisionEpoch] = Field(default=None, description="Current decision epoch when the session owns the active actor.")


class SubjectiveWorldState(BaseModel):
    """Canonical session-subjective world rebuilt from snapshots and frames."""

    observation_cursor: int = Field(description="Highest observation cursor applied to this materialized state.")
    session: ObservationSessionState = Field(description="Current session state.")
    encounter: Optional[ObservationEncounterState] = Field(default=None, description="Current encounter state.")
    observers: Dict[str, ObservationObserverState] = Field(default_factory=dict, description="Observer states keyed by observer UUID.")
    known_entities: Dict[str, ObservationEntityFact] = Field(
        default_factory=dict,
        description="Known entity facts keyed by entity UUID.",
    )
    known_objects: Dict[str, ObservationObjectFact] = Field(
        default_factory=dict,
        description="Known object facts keyed by object UUID.",
    )
    known_tiles: Dict[str, ObservationTileFact] = Field(
        default_factory=dict,
        description="Known tile facts keyed by tile key.",
    )
    combat_logs: List[Dict[str, Any]] = Field(default_factory=list, description="Visible combat-log entries applied during replay.")
    current_epoch: Optional[DecisionEpoch] = Field(default=None, description="Current legal decision epoch for this session.")
    epoch_cursor: int = Field(default=0, description="Highest applied decision-epoch index.")
