"""Immutable policy-facing facts derived from one subjective world."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from ai.protocol.control import ActionAffordance, ActionCapability, ActionEconomyState
from ai.protocol.semantics import ActionSemantics, ActionTag


Position = Tuple[int, int]


class FactModel(BaseModel):
    """Immutable base for derived subjective facts."""

    model_config = ConfigDict(frozen=True)


class ActorFacts(FactModel):
    """Current controlled actor and turn resources."""

    session_id: str = Field(description="Session whose subjective state produced these facts.")
    controlled_entity_uuids: Tuple[str, ...] = Field(description="Entity UUIDs controlled by the session.")
    active_entity_uuid: Optional[str] = Field(default=None, description="Subjectively known active entity UUID.")
    actor_uuid: Optional[str] = Field(default=None, description="Controlled actor UUID when this session can act.")
    is_my_turn: bool = Field(description="Whether the session owns the current decision epoch.")
    position: Optional[Position] = Field(default=None, description="Known actor position.")
    hp: Optional[int] = Field(default=None, description="Known actor hit points.")
    normal_hp: Optional[int] = Field(
        default=None,
        description="Known actor hit points that can be restored by healing.",
    )
    temporary_hp: Optional[int] = Field(
        default=None,
        ge=0,
        description="Known actor temporary hit points.",
    )
    max_hp: Optional[int] = Field(default=None, description="Known actor maximum hit points.")
    healing_blocked: Optional[bool] = Field(
        default=None,
        description="Whether observed rules currently prevent actor healing.",
    )
    conditions: Tuple[str, ...] = Field(default_factory=tuple, description="Known actor conditions.")
    condition_semantic_keys: Optional[Tuple[str, ...]] = Field(
        default=None,
        description="Known stable active condition type keys; None preserves unknown activity.",
    )
    is_concentrating: bool = Field(description="Whether the controlled actor is observed concentrating.")
    faction: Optional[str] = Field(default=None, description="Known actor faction label.")
    economy: Optional[ActionEconomyState] = Field(default=None, description="Authoritative current action economy.")


class ContactFacts(FactModel):
    """Typed indexes into canonical subjective entity facts."""

    controlled_entity_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Known controlled entities.")
    visible_hostile_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Visible living non-controlled contacts.")
    remembered_hostile_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Remembered living non-controlled contacts.")
    visible_ally_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Visible living contacts with a known controlled faction.")
    remembered_ally_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Remembered living contacts with a known controlled faction.")
    visible_unknown_relationship_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Visible living contacts whose faction relationship is unknown.",
    )
    remembered_unknown_relationship_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Remembered living contacts whose faction relationship is unknown.",
    )
    known_dead_entity_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Non-controlled contacts subjectively known to be dead.",
    )
    unknown_contact_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Known identifiers lacking actionable knowledge.")
    entity_replay_tokens: Dict[str, str] = Field(
        default_factory=dict,
        description="Identity-independent disclosed ordering tokens keyed by entity UUID.",
    )
    known_hp_sort_keys: Dict[str, Tuple[bool, int]] = Field(
        default_factory=dict,
        description="Known-HP ordering keys with unknown values sorted last.",
    )
    wounded_fractions: Dict[str, float] = Field(
        default_factory=dict,
        description="Known missing-normal-HP fractions keyed by entity UUID.",
    )
    healthy_fractions: Dict[str, float] = Field(
        default_factory=dict,
        description="Known remaining-normal-HP fractions keyed by entity UUID.",
    )


class ThreatFacts(FactModel):
    """Immediate subjective pressure around the current actor."""

    actor_uuid: Optional[str] = Field(
        default=None,
        description="Controlled actor represented by these threat facts.",
    )
    adjacent_hostile_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Visible living hostiles currently adjacent to the actor.",
    )
    nearest_visible_hostile_uuid: Optional[str] = Field(
        default=None,
        description="Nearest visible hostile by disclosed position.",
    )
    nearest_visible_hostile_distance_cells: Optional[int] = Field(
        default=None,
        ge=0,
        description="Grid-cell distance to the nearest visible hostile.",
    )


class ObjectFacts(FactModel):
    """Typed indexes into canonical subjective object facts."""

    known_object_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="All subjectively known objects.")
    closed_door_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Known closed doors.")
    open_door_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Known open doors.")


class TopologyFacts(FactModel):
    """Typed known topology and useful derived indexes."""

    known_tile_keys: Tuple[str, ...] = Field(default_factory=tuple, description="All known tile keys.")
    hazardous_positions: frozenset[Position] = Field(default_factory=frozenset, description="Known hazardous positions.")
    slow_positions: frozenset[Position] = Field(default_factory=frozenset, description="Known above-normal-cost positions.")
    blocked_positions: frozenset[Position] = Field(default_factory=frozenset, description="Known non-walkable positions.")
    vision_blocker_positions: frozenset[Position] = Field(
        default_factory=frozenset,
        description="Visible positions explicitly occupied by vision-blocking objects.",
    )


class NavigationHistoryFacts(FactModel):
    """Turn-scoped voluntary movement retained in subjective combat logs."""

    actor_uuid: Optional[str] = Field(
        default=None,
        description="Controlled actor whose current turn produced this history.",
    )
    round_number: Optional[int] = Field(
        default=None,
        description="Current actor round represented by the retained path.",
    )
    turn_index: Optional[int] = Field(
        default=None,
        description="Current actor initiative index represented by the retained path.",
    )
    same_turn_path: Tuple[Position, ...] = Field(
        default_factory=tuple,
        description="Ordered cells traversed voluntarily by the actor this turn.",
    )
    visited_positions: frozenset[Position] = Field(
        default_factory=frozenset,
        description="Cells present in the actor's same-turn voluntary path.",
    )


class TargetEffectBlockHypothesis(FactModel):
    """Bounded subjective evidence that one target may block one effect."""

    target_uuid: str = Field(description="Subjectively identified target UUID.")
    effect_id: str = Field(description="Stable effect identity observed in typed damage logs.")
    blocked_episodes: int = Field(ge=1, description="Retained top-level episodes where every application was blocked.")
    total_episodes: int = Field(ge=1, description="Retained top-level episodes containing the target/effect pair.")
    blocked_applications: int = Field(ge=1, description="Blocked applications across retained episodes.")
    total_applications: int = Field(ge=1, description="All applications across retained episodes.")
    episode_log_indices: Tuple[int, ...] = Field(
        description="Absolute subjective top-level log indices retained as independent episodes.",
    )
    latest_log_index: int = Field(ge=0, description="Newest subjective top-level log supporting this hypothesis.")
    block_probability: float = Field(
        gt=0.0,
        lt=1.0,
        description="Beta(1,1) posterior mean for a whole future episode being blocked.",
    )


class CombatMemoryFacts(FactModel):
    """Session-subjective bounded hypotheses derived from visible combat logs."""

    source_log_count: int = Field(ge=0, description="Visible top-level combat-log count used for derivation.")
    hypotheses: Tuple[TargetEffectBlockHypothesis, ...] = Field(
        default_factory=tuple,
        description="Retained hypotheses ordered newest-first with deterministic ties.",
    )
    by_target_effect: Dict[str, TargetEffectBlockHypothesis] = Field(
        default_factory=dict,
        description="Hypotheses keyed by collision-safe target/effect identity.",
    )

    def hypothesis_for(
        self,
        target_uuid: str,
        effect_id: str,
    ) -> Optional[TargetEffectBlockHypothesis]:
        """Return retained evidence for one exact subjective target/effect pair."""
        return self.by_target_effect.get(target_effect_hypothesis_key(target_uuid, effect_id))


def target_effect_hypothesis_key(target_uuid: str, effect_id: str) -> str:
    """Build a collision-safe JSON-compatible index key without parsing names."""
    return f"{len(target_uuid)}:{target_uuid}{effect_id}"


class AffordanceAffectedSetGroup(FactModel):
    """Legal rows sharing one source, semantics contract, and affected set."""

    source_action_id: str = Field(description="Epoch-local source-action identity.")
    semantics_ref: str = Field(description="Shared typed action-semantics reference.")
    canonical_row_id: str = Field(description="Geometry-canonical executable representative.")
    row_ids: Tuple[str, ...] = Field(description="Equivalent row ids in canonical geometry order.")
    affected_entity_uuids: frozenset[str] = Field(
        description="Exact subjective entity set affected by every grouped row.",
    )


class AffordanceIndex(FactModel):
    """Server-issued legal rows indexed by stable typed meaning."""

    epoch_id: Optional[str] = Field(default=None, description="Epoch authorizing these rows.")
    rows: Tuple[ActionAffordance, ...] = Field(default_factory=tuple, description="Legal rows in deterministic order.")
    by_id: Dict[str, ActionAffordance] = Field(default_factory=dict, description="Rows keyed by row id.")
    row_ids_by_bucket: Dict[str, Tuple[str, ...]] = Field(default_factory=dict, description="Row ids grouped by bucket.")
    row_ids_by_semantic_id: Dict[str, Tuple[str, ...]] = Field(default_factory=dict, description="Row ids grouped by semantic family.")
    row_ids_by_tag: Dict[ActionTag, Tuple[str, ...]] = Field(default_factory=dict, description="Row ids grouped by semantic capability.")
    semantics_by_row_id: Dict[str, ActionSemantics] = Field(default_factory=dict, description="Resolved semantic contracts by row id.")
    target_effect_row_ids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Legal row ids whose typed semantics contain conditional target effects.",
    )
    affected_entity_uuids_by_row_id: Dict[str, frozenset[str]] = Field(
        default_factory=dict,
        description="Explicit subjective entity effects keyed by legal row id.",
    )
    primary_target_uuid_by_row_id: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="First explicit target UUID keyed by legal row id.",
    )
    target_geometry_key_by_row_id: Dict[str, Tuple[Tuple[int, int, int], ...]] = Field(
        default_factory=dict,
        description="Canonical disclosed target-position geometry keyed by legal row id.",
    )
    affected_set_groups: Tuple[AffordanceAffectedSetGroup, ...] = Field(
        default_factory=tuple,
        description="Rows normalized once by source, semantics, and affected entities.",
    )
    affected_set_group_indices_by_tag: Dict[ActionTag, Tuple[int, ...]] = Field(
        default_factory=dict,
        description="Affected-set group indexes keyed by semantic capability.",
    )


class CapabilityIndex(FactModel):
    """Non-executable actor capabilities indexed by stable typed meaning."""

    rows: Tuple[ActionCapability, ...] = Field(default_factory=tuple, description="Actor-owned action capabilities.")
    by_id: Dict[str, ActionCapability] = Field(default_factory=dict, description="Capabilities keyed by capability id.")
    capability_ids_by_tag: Dict[ActionTag, Tuple[str, ...]] = Field(
        default_factory=dict,
        description="Capability ids grouped by semantic tag.",
    )
    semantics_by_capability_id: Dict[str, ActionSemantics] = Field(
        default_factory=dict,
        description="Resolved semantic contracts by capability id.",
    )


class AgentFacts(FactModel):
    """Complete typed policy input derived from one subjective world revision."""

    observation_cursor: int = Field(description="Subjective cursor represented by these facts.")
    epoch_id: Optional[str] = Field(default=None, description="Current decision epoch id.")
    actor: ActorFacts = Field(description="Current actor and resource facts.")
    contacts: ContactFacts = Field(description="Subjective entity contact facts.")
    threat: ThreatFacts = Field(description="Immediate subjective threat facts.")
    objects: ObjectFacts = Field(description="Subjective object facts.")
    topology: TopologyFacts = Field(description="Subjective topology facts.")
    navigation: NavigationHistoryFacts = Field(
        default_factory=NavigationHistoryFacts,
        description="Turn-scoped subjective voluntary movement history.",
    )
    combat_memory: CombatMemoryFacts = Field(
        default_factory=lambda: CombatMemoryFacts(source_log_count=0),
        description="Bounded session-subjective combat hypotheses.",
    )
    affordances: AffordanceIndex = Field(description="Current server-issued legal affordances.")
    capabilities: CapabilityIndex = Field(description="Actor-owned possible actions without execution authority.")
