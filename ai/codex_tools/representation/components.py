"""Typed payloads and discriminated blocks for Codex representations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai.codex_tools.representation.models import (
    ExposureTiming,
    RepresentationBlock,
)
from ai.codex_tools.representation.predicates import (
    DerivedFactObservation,
    PredicateEvaluation,
)
from ai.knowledge.models import TargetEffectBlockHypothesis
from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationEncounterState,
    ObservationEntityFact,
    ObservationObjectFact,
    ObservationTileFact,
)
from dnd.ai.contracts.control import (
    ActionAffordance,
    ActionCostProfile,
    ActionEconomyState,
    AffordanceSet,
)
from dnd.ai.contracts.semantics import ActionSemanticProvenance


Position = Tuple[int, int]


class ComponentPayload(BaseModel):
    """Immutable base for every typed component payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CoreRevisionPayload(ComponentPayload):
    """Identity of the exact subjective revision represented by an envelope."""

    session_id: str = Field(description="Session whose subjective state is represented.")
    encounter_uuid: Optional[str] = Field(
        default=None,
        description="Subjectively known encounter identity, when an encounter exists.",
    )
    observation_cursor: int = Field(
        ge=0,
        description="Highest subjective observation cursor included in the representation.",
    )
    epoch_id: Optional[str] = Field(
        default=None,
        description="Current decision epoch identity, when the session can act.",
    )
    epoch_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Monotonic session epoch index, when a decision epoch exists.",
    )
    active_entity_uuid: Optional[str] = Field(
        default=None,
        description="Subjectively known active entity identity.",
    )
    actor_uuid: Optional[str] = Field(
        default=None,
        description="Controlled actor authorized by the current epoch.",
    )
    round_number: Optional[int] = Field(
        default=None,
        description="Subjectively known encounter round.",
    )
    turn_index: Optional[int] = Field(
        default=None,
        description="Subjectively known initiative index.",
    )
    encounter_state: Optional[str] = Field(
        default=None,
        description="Subjectively known encounter lifecycle state.",
    )
    is_my_turn: bool = Field(
        description="Whether the session owns the current decision boundary.",
    )


class TurnCorePayload(ComponentPayload):
    """Complete controlled-team and action-economy state for one revision."""

    encounter: Optional[ObservationEncounterState] = Field(
        default=None,
        description="Complete subjectively known encounter state.",
    )
    actor: Optional[ObservationEntityFact] = Field(
        default=None,
        description="Complete subjective fact for the authorized actor.",
    )
    controlled_entities: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Complete subjective facts for all session-controlled entities.",
    )
    economy: Optional[ActionEconomyState] = Field(
        default=None,
        description="Authoritative current economy supplied by the decision epoch.",
    )
    is_terminal: bool = Field(
        description="Whether the subjective encounter state is terminal.",
    )


class ContactLedgerPayload(ComponentPayload):
    """Deterministic partition of known entities by knowledge and relationship."""

    controlled_entities: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Session-controlled subjective entity facts.",
    )
    visible_hostiles: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Visible living contacts known to be hostile.",
    )
    remembered_hostiles: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Seen or remembered living contacts known to be hostile.",
    )
    visible_allies: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Visible non-controlled contacts known to be allied.",
    )
    remembered_allies: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Seen or remembered non-controlled contacts known to be allied.",
    )
    visible_unknown_relationship: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Visible contacts whose faction relationship is unknown.",
    )
    remembered_unknown_relationship: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Remembered contacts whose faction relationship is unknown.",
    )
    known_dead_contacts: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Non-controlled contacts subjectively known to be dead.",
    )
    unknown_contacts: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Known contact identities without actionable current knowledge.",
    )
    knowledge_detail_preserved: bool = Field(
        description="Whether the profile requests explicit knowledge detail in automatic context.",
    )


class KnownObjectSummary(ComponentPayload):
    """Typed automatic summary of one known object."""

    uuid: str = Field(description="Subjectively known object identity.")
    name: str = Field(description="Subjectively known object display name.")
    knowledge_state: KnowledgeState = Field(description="How the session knows the object.")
    observer_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Controlled observers supporting this object fact.",
    )
    position: Optional[Position] = Field(
        default=None,
        description="Known or last-known object position.",
    )
    map_char: Optional[str] = Field(
        default=None,
        description="Known object map glyph.",
    )
    is_open: Optional[bool] = Field(
        default=None,
        description="Typed open state when the subjective object state supplies a boolean.",
    )
    state_keys: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Names of locally inspectable object-state fields omitted from this summary.",
    )


class ObjectLedgerPayload(ComponentPayload):
    """Bounded typed index over subjectively known objects."""

    total_known_objects: int = Field(
        ge=0,
        description="Total known object facts in the canonical subjective state.",
    )
    objects: Tuple[KnownObjectSummary, ...] = Field(
        default_factory=tuple,
        description="Deterministically retained typed object summaries.",
    )
    complete_objects: Optional[Tuple[ObservationObjectFact, ...]] = Field(
        default=None,
        description=(
            "Complete subjective object facts when an explicit compatibility profile "
            "requests lossless automatic exposure."
        ),
    )


class TopologySummaryPayload(ComponentPayload):
    """Neutral aggregate of accumulated subjective topology knowledge."""

    known_tile_count: int = Field(
        ge=0,
        description="Number of canonical subjectively known tile facts.",
    )
    hazardous_positions: Tuple[Position, ...] = Field(
        default_factory=tuple,
        description="Known hazardous positions in coordinate order.",
    )
    slow_positions: Tuple[Position, ...] = Field(
        default_factory=tuple,
        description="Known above-normal-cost positions in coordinate order.",
    )
    blocked_positions: Tuple[Position, ...] = Field(
        default_factory=tuple,
        description="Known non-walkable positions in coordinate order.",
    )
    vision_blocker_positions: Tuple[Position, ...] = Field(
        default_factory=tuple,
        description="Known positions with at least one visible directional vision blocker.",
    )


class SpatialScenePayload(ComponentPayload):
    """Bounded non-ranking scene assembled only from known subjective facts."""

    radius: int = Field(ge=1, description="Chebyshev radius used around scene anchors.")
    anchor_positions: Tuple[Position, ...] = Field(
        default_factory=tuple,
        description="Controlled or known-contact positions defining the scene.",
    )
    entities: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Known entity facts whose positions fall inside the scene.",
    )
    objects: Tuple[ObservationObjectFact, ...] = Field(
        default_factory=tuple,
        description="Known object facts whose positions fall inside the scene.",
    )
    known_tiles: Tuple[ObservationTileFact, ...] = Field(
        default_factory=tuple,
        description="Known tile facts whose positions fall inside the scene.",
    )
    unknown_positions: Tuple[Position, ...] = Field(
        default_factory=tuple,
        description="Coordinates inside scene bounds for which the session has no tile fact.",
    )


class ActionFamilySummary(ComponentPayload):
    """Bounded capability-first summary of one discovered legal action."""

    source_action_id: str = Field(description="Epoch-local discovered-action identity.")
    semantic_key: str = Field(description="Stable engine action-definition identity.")
    template_name: str = Field(description="Engine template name for the discovered action.")
    base_template_name: Optional[str] = Field(
        default=None,
        description="Registered template family before generated variants.",
    )
    display_name: str = Field(description="Human-readable action name.")
    semantic_id: str = Field(description="Stable semantic action family.")
    semantics_ref: str = Field(description="Reference into the epoch semantic catalog.")
    semantic_provenance: ActionSemanticProvenance = Field(
        description="Resolution strength and origin of this action's semantics.",
    )
    bucket: str = Field(description="Server-issued affordance bucket.")
    action_category: str = Field(description="Engine action category.")
    target_type: str = Field(description="Configured target allocation type.")
    row_count: int = Field(ge=1, description="Executable rows generated by this source action.")
    direct_row_id: Optional[str] = Field(
        default=None,
        description="Executable row id only when the source has exactly one legal row.",
    )
    affordable_row_count: int = Field(
        ge=0,
        description="Rows in this family currently marked affordable.",
    )
    cost: ActionCostProfile = Field(description="Shared action-economy and resource cost.")
    target_option_count: int = Field(
        ge=0,
        description="Legal source-level targets available before row expansion.",
    )
    allocation_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Target or projectile allocations available when declared.",
    )
    allow_same_target: Optional[bool] = Field(
        default=None,
        description="Whether repeated target allocation is legal.",
    )
    spell_level: Optional[int] = Field(default=None, ge=0, description="Base spell level when applicable.")
    cast_at_level: Optional[int] = Field(default=None, ge=0, description="Selected spell-slot level when applicable.")
    requires_concentration: bool = Field(description="Whether this action starts or replaces concentration.")
    tags: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Stable semantic tags present on the family rows.",
    )


class ActionCapabilitySummary(ComponentPayload):
    """Bounded actor-owned capability metadata without stochastic internals."""

    capability_id: str = Field(description="Stable actor-owned capability identity.")
    semantic_key: str = Field(description="Stable action-definition identity.")
    action_category: str = Field(description="Engine action category.")
    target_type: str = Field(description="Configured target-allocation type.")
    cost: ActionCostProfile = Field(description="Current cost and affordability profile.")
    range_type: Optional[str] = Field(default=None, description="Reach, ranged, or self range class.")
    normal_range_feet: Optional[int] = Field(default=None, ge=0, description="Normal reach or range.")
    long_range_feet: Optional[int] = Field(default=None, ge=0, description="Optional long range.")
    requires_line_of_sight: bool = Field(description="Whether ordinary use requires visible line of sight.")
    valid_target_filter: str = Field(description="Configured relationship filter.")
    weapon_slot: Optional[str] = Field(default=None, description="Configured weapon slot when applicable.")
    base_spell_level: Optional[int] = Field(default=None, ge=0, description="Intrinsic spell level.")
    cast_at_level: Optional[int] = Field(default=None, ge=0, description="Configured spell-slot variant level.")
    source_item_uuid: Optional[str] = Field(default=None, description="Actor-owned item providing the capability.")
    semantic_id: str = Field(description="Stable semantic action family.")
    semantics_ref: str = Field(description="Reference into the epoch semantic catalog.")
    tags: Tuple[str, ...] = Field(default_factory=tuple, description="Typed semantic capability tags.")


class MultiTargetActionSummary(ComponentPayload):
    """Typed target-allocation summary for one legal multi-target row."""

    row_id: str = Field(description="Executable row identity.")
    display_name: str = Field(description="Human-readable action name.")
    semantic_id: str = Field(description="Stable semantic action family.")
    primary_target_uuid: Optional[str] = Field(
        default=None,
        description="Primary target identity already selected by the row.",
    )
    primary_target_name: Optional[str] = Field(
        default=None,
        description="Primary target display name already selected by the row.",
    )
    selectable_target_count: int = Field(
        ge=0,
        description="Number of legal target options exposed by the source action.",
    )
    allocation_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Total target or projectile allocation when known.",
    )
    extra_target_slots: Optional[int] = Field(
        default=None,
        ge=0,
        description="Additional target identities accepted with this row.",
    )
    allow_same_target: Optional[bool] = Field(
        default=None,
        description="Whether repeated target allocation is legal.",
    )


class ActionSemanticCoverage(ComponentPayload):
    """Coverage of semantic derivation strengths across discovered action sources."""

    source_action_count: int = Field(ge=0, description="Total discovered source actions.")
    exact_count: int = Field(ge=0, description="Sources resolved by registered exact builders.")
    structured_profile_count: int = Field(
        ge=0,
        description="Sources resolved from engine-declared effect profiles.",
    )
    category_fallback_count: int = Field(
        ge=0,
        description="Sources resolved only from structured category metadata.",
    )
    unknown_count: int = Field(ge=0, description="Sources without usable semantic meaning.")
    unknown_semantic_keys: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Stable action-definition keys that remain semantically unknown.",
    )
    capability_count: int = Field(
        default=0,
        ge=0,
        description="Total non-executable actor capabilities checked for semantic coverage.",
    )
    unknown_capability_count: int = Field(
        default=0,
        ge=0,
        description="Actor capabilities that still resolve to action.unknown.",
    )
    unknown_capability_semantic_keys: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Stable capability keys that remain semantically unknown.",
    )


class ActionFamilyPayload(ComponentPayload):
    """Complete legal affordances plus neutral action-family indexes."""

    epoch_id: Optional[str] = Field(
        default=None,
        description="Decision epoch authorizing the contained rows.",
    )
    actor_uuid: Optional[str] = Field(
        default=None,
        description="Actor authorized by the decision epoch.",
    )
    economy: Optional[ActionEconomyState] = Field(
        default=None,
        description="Authoritative economy paired with the legal rows.",
    )
    complete_affordances: Optional[AffordanceSet] = Field(
        default=None,
        description="Complete server-issued legal rows and capabilities for local inspection.",
    )
    total_rows: int = Field(ge=0, description="Total legal executable row count.")
    affordable_rows: int = Field(ge=0, description="Total currently affordable row count.")
    semantic_coverage: ActionSemanticCoverage = Field(
        default_factory=lambda: ActionSemanticCoverage(
            source_action_count=0,
            exact_count=0,
            structured_profile_count=0,
            category_fallback_count=0,
            unknown_count=0,
        ),
        description="Semantic-resolution coverage for every discovered source action.",
    )
    rows_by_bucket: Tuple[Tuple[str, int], ...] = Field(
        default_factory=tuple,
        description="Deterministic row counts by affordance bucket.",
    )
    rows_by_tag: Tuple[Tuple[str, int], ...] = Field(
        default_factory=tuple,
        description="Deterministic row counts by typed semantic tag.",
    )
    total_family_count: int = Field(default=0, ge=0, description="Total discovered action-source families.")
    omitted_family_count: int = Field(
        default=0,
        ge=0,
        description="Source families omitted from automatic context by the profile limit.",
    )
    families: Tuple[ActionFamilySummary, ...] = Field(
        default_factory=tuple,
        description="Profile-bounded source families in first-source occurrence order.",
    )
    multi_target_rows: Tuple[MultiTargetActionSummary, ...] = Field(
        default_factory=tuple,
        description="Profile-bounded multi-target allocation summaries.",
    )
    automatically_expanded_rows: Tuple[ActionAffordance, ...] = Field(
        default_factory=tuple,
        description="Complete rows copied into automatic context when explicitly enabled.",
    )
    capabilities: Tuple[ActionCapabilitySummary, ...] = Field(
        default_factory=tuple,
        description="Profile-bounded capabilities without verbose stochastic outcome internals.",
    )
    total_capability_count: int = Field(
        default=0,
        ge=0,
        description="Total non-executable actor capabilities in the epoch.",
    )
    omitted_capability_count: int = Field(
        default=0,
        ge=0,
        description="Capabilities omitted from automatic context by the profile limit.",
    )


class CombatLogChildSummary(ComponentPayload):
    """One typed direct child of a subjective combat-log record."""

    entry_type: Optional[str] = Field(default=None, description="Visible child log category.")
    source_name: Optional[str] = Field(default=None, description="Visible child source name.")
    source_uuid: Optional[str] = Field(default=None, description="Visible child source identity.")
    target_name: Optional[str] = Field(default=None, description="Visible child target name.")
    target_uuid: Optional[str] = Field(default=None, description="Visible child target identity.")
    compact: Optional[str] = Field(default=None, description="Compact visible child rendering.")
    success: Optional[bool] = Field(default=None, description="Visible child outcome.")


class CombatLogSummary(ComponentPayload):
    """Typed bounded projection of one subjective combat-log record."""

    entry_type: Optional[str] = Field(default=None, description="Visible top-level log category.")
    source_name: Optional[str] = Field(default=None, description="Visible top-level source name.")
    source_uuid: Optional[str] = Field(default=None, description="Visible top-level source identity.")
    target_name: Optional[str] = Field(default=None, description="Visible direct target name.")
    target_uuid: Optional[str] = Field(default=None, description="Visible direct target identity.")
    compact: Optional[str] = Field(default=None, description="Compact visible top-level rendering.")
    verbose: Optional[str] = Field(default=None, description="Verbose visible top-level rendering.")
    success: Optional[bool] = Field(default=None, description="Visible top-level outcome.")
    sub_entries: Tuple[CombatLogChildSummary, ...] = Field(
        default_factory=tuple,
        description="Bounded direct subjective causal children.",
    )
    omitted_sub_entry_count: int = Field(
        ge=0,
        description="Additional direct children available through local inspection.",
    )


class RecentCombatLogsPayload(ComponentPayload):
    """Newest bounded subjective combat-log summaries."""

    source_log_count: int = Field(
        ge=0,
        description="Total canonical subjective top-level log count.",
    )
    logs: Tuple[CombatLogSummary, ...] = Field(
        default_factory=tuple,
        description="Newest retained logs in original subjective order.",
    )


class EntityRevisionChange(ComponentPayload):
    """Typed entity replacement between two subjective decision revisions."""

    entity_uuid: str = Field(description="Changed subjective entity identity.")
    before: Optional[ObservationEntityFact] = Field(
        default=None,
        description="Entity fact at the prior boundary, or null when newly known.",
    )
    after: Optional[ObservationEntityFact] = Field(
        default=None,
        description="Entity fact at the current boundary, or null when forgotten.",
    )


class ObjectRevisionChange(ComponentPayload):
    """Typed object replacement between two subjective decision revisions."""

    object_uuid: str = Field(description="Changed subjective object identity.")
    before: Optional[ObservationObjectFact] = Field(
        default=None,
        description="Object fact at the prior boundary, or null when newly known.",
    )
    after: Optional[ObservationObjectFact] = Field(
        default=None,
        description="Object fact at the current boundary, or null when forgotten.",
    )


class TileRevisionChange(ComponentPayload):
    """Typed tile replacement between two subjective decision revisions."""

    tile_key: str = Field(description="Changed subjective tile identity.")
    before: Optional[ObservationTileFact] = Field(
        default=None,
        description="Tile fact at the prior boundary, or null when newly known.",
    )
    after: Optional[ObservationTileFact] = Field(
        default=None,
        description="Tile fact at the current boundary, or null when forgotten.",
    )


class SubjectiveFrameSummary(ComponentPayload):
    """Causal identity and affected subjective facts from one consumed envelope."""

    observation_cursor: int = Field(ge=0, description="Session-local frame cursor.")
    frame_type: str = Field(description="Subjective frame category.")
    source_kind: Optional[str] = Field(default=None, description="Causal source category.")
    source_command_id: Optional[str] = Field(default=None, description="Controller command correlation id.")
    event_type: Optional[str] = Field(default=None, description="Projected engine event type.")
    event_uuid: Optional[str] = Field(default=None, description="Projected engine event identity.")
    lineage_uuid: Optional[str] = Field(default=None, description="Projected causal lineage identity.")
    phase: Optional[str] = Field(default=None, description="Projected engine event phase.")
    patch_types: Tuple[str, ...] = Field(description="Ordered subjective patch categories.")
    entity_uuids: Tuple[str, ...] = Field(description="Subjective entities referenced by patches.")
    object_uuids: Tuple[str, ...] = Field(description="Subjective objects referenced by patches.")
    tile_keys: Tuple[str, ...] = Field(description="Subjective tiles referenced by patches.")
    has_combat_log: bool = Field(description="Whether this envelope carried a visible combat log.")
    command_status: Optional[str] = Field(default=None, description="Controller command result status.")
    decision_epoch_id: Optional[str] = Field(default=None, description="Replacement decision epoch identity.")


class DecisionDeltaPayload(ComponentPayload):
    """Ordered typed changes since the preceding supplied decision boundary."""

    baseline: bool = Field(
        description="Whether no prior subjective boundary was supplied for comparison.",
    )
    history_gap: bool = Field(
        default=False,
        description="Whether retained envelope history is incomplete for this cursor interval.",
    )
    used_state_diff_fallback: bool = Field(
        default=False,
        description="Whether final-state changes supplement unavailable event history.",
    )
    from_observation_cursor: Optional[int] = Field(
        default=None,
        ge=0,
        description="Prior subjective cursor, when a prior boundary was supplied.",
    )
    to_observation_cursor: int = Field(
        ge=0,
        description="Current subjective cursor represented by the delta.",
    )
    from_epoch_id: Optional[str] = Field(default=None, description="Prior decision epoch identity.")
    to_epoch_id: Optional[str] = Field(default=None, description="Current decision epoch identity.")
    session_changed: bool = Field(description="Whether the subjective session state changed.")
    encounter_changed: bool = Field(description="Whether the subjective encounter state changed.")
    entities: Tuple[EntityRevisionChange, ...] = Field(
        default_factory=tuple,
        description="Entity additions, removals, and replacements in identity order.",
    )
    objects: Tuple[ObjectRevisionChange, ...] = Field(
        default_factory=tuple,
        description="Object additions, removals, and replacements in identity order.",
    )
    tiles: Tuple[TileRevisionChange, ...] = Field(
        default_factory=tuple,
        description="Tile additions, removals, and replacements in key order.",
    )
    new_combat_logs: Tuple[CombatLogSummary, ...] = Field(
        default_factory=tuple,
        description="Typed subjective logs appended since the prior boundary.",
    )
    subjective_frames: Tuple[SubjectiveFrameSummary, ...] = Field(
        default_factory=tuple,
        description="Ordered causal envelopes retained since the prior decision boundary.",
    )


class CombatHypothesisPayload(ComponentPayload):
    """Bounded uncertain combat-memory hypotheses from subjective evidence."""

    source_log_count: int = Field(
        ge=0,
        description="Visible top-level logs used by the hypothesis processor.",
    )
    hypotheses: Tuple[TargetEffectBlockHypothesis, ...] = Field(
        default_factory=tuple,
        description="Retained hypotheses in deterministic processor order.",
    )


class PredicateFocusPayload(ComponentPayload):
    """Automatic attention selection over a complete local predicate ledger."""

    facts: Tuple[DerivedFactObservation, ...] = Field(
        default_factory=tuple,
        description="Derived facts selected because their observations changed.",
    )
    predicates: Tuple[PredicateEvaluation, ...] = Field(
        default_factory=tuple,
        description="Focused three-valued predicate evaluations.",
    )
    complete_fact_count: int = Field(
        ge=0,
        description="Total locally inspectable fact observations.",
    )
    complete_predicate_count: int = Field(
        ge=0,
        description="Total locally inspectable predicate evaluations.",
    )


class RepresentationWarning(ComponentPayload):
    """Stable non-prescriptive warning about a representation gap or state."""

    code: str = Field(description="Stable machine-readable warning identity.")
    message: str = Field(description="Concise non-prescriptive warning text.")
    evidence_refs: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Canonical local paths supporting the warning.",
    )


class WarningPayload(ComponentPayload):
    """Compatibility warning set for the current subjective revision."""

    warnings: Tuple[RepresentationWarning, ...] = Field(
        default_factory=tuple,
        description="Deterministically ordered representation warnings.",
    )


class OracleProposalSummary(ComponentPayload):
    """Policy-independent summary of one separately supplied oracle proposal."""

    intent_kind: str = Field(description="Stable kind of controller intent proposed by the oracle.")
    row_id: Optional[str] = Field(default=None, description="Executable row selected by an execute intent.")
    goal: str = Field(description="Stable tactical objective declared by the oracle.")
    source_node: str = Field(description="Oracle node or planner that produced the proposal.")
    reason: str = Field(description="Oracle-provided decision rationale.")
    score: float = Field(description="Comparable utility reported by the oracle.")
    semantic_tags: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Stable action-semantic tags attached by the oracle.",
    )


class OracleTraceStepSummary(ComponentPayload):
    """Policy-independent summary of one separately supplied oracle trace step."""

    node_path: str = Field(description="Stable path of the evaluated oracle node.")
    status: str = Field(description="Oracle node result.")
    detail: str = Field(description="Guard or selection explanation.")
    proposal_count: int = Field(ge=0, description="Proposals produced by the oracle node.")


class OracleAdviceBasis(ComponentPayload):
    """Exact subjective revision and policy implementation evaluated by an oracle."""

    session_id: str = Field(description="Subjective controller session evaluated.")
    observation_cursor: int = Field(ge=0, description="Subjective cursor evaluated.")
    epoch_id: str = Field(description="Decision epoch evaluated.")
    actor_uuid: str = Field(description="Controlled actor evaluated.")
    policy_id: str = Field(description="Traditional policy implementation identity.")
    policy_version: str = Field(description="Traditional policy implementation version.")


class AdvicePayload(ComponentPayload):
    """Optional policy-oracle data supplied to, but never computed by, projection."""

    available: bool = Field(description="Whether a caller supplied a policy decision.")
    detail: Literal["selected_only", "ranked", "full_trace"] = Field(
        description="Profile-selected amount of supplied oracle detail.",
    )
    basis: Optional[OracleAdviceBasis] = Field(
        default=None,
        description="Exact revision and policy identity behind available advice.",
    )
    evaluation_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Measured policy evaluation time for the cached decision.",
    )
    unavailable_reason: Optional[str] = Field(
        default=None,
        description="Why no policy advice is available.",
    )
    selected: Optional[OracleProposalSummary] = Field(
        default=None,
        description="Selected policy proposal when oracle data was supplied.",
    )
    candidates: Tuple[OracleProposalSummary, ...] = Field(
        default_factory=tuple,
        description="Ranked oracle candidates when the selected detail permits them.",
    )
    trace: Tuple[OracleTraceStepSummary, ...] = Field(
        default_factory=tuple,
        description="Oracle evaluation trace only in full-trace mode.",
    )

    @model_validator(mode="after")
    def validate_availability(self) -> "AdvicePayload":
        """Require complete revision provenance for every available recommendation."""
        if self.available and (self.basis is None or self.selected is None):
            raise ValueError("Available oracle advice requires basis and selected proposal")
        if not self.available and (self.selected is not None or self.candidates or self.trace):
            raise ValueError("Unavailable oracle advice cannot contain proposals or trace")
        return self


class RuntimeStageTiming(ComponentPayload):
    """One externally measured local runtime stage."""

    stage: str = Field(description="Stable measured stage identity.")
    elapsed_ms: float = Field(ge=0, description="Measured local stage duration in milliseconds.")


class RuntimeTelemetryInput(ComponentPayload):
    """Optional observational telemetry supplied to representation projection."""

    stages: Tuple[RuntimeStageTiming, ...] = Field(
        default_factory=tuple,
        description="Externally measured stages in emission order.",
    )
    inspection_count: int = Field(
        default=0,
        ge=0,
        description="Local inspection operations completed for the session.",
    )
    command_count: int = Field(
        default=0,
        ge=0,
        description="Controller commands submitted for the session.",
    )
    resync_count: int = Field(
        default=0,
        ge=0,
        description="Subjective runtime resynchronizations completed for the session.",
    )


class RepresentationTelemetryPayload(ComponentPayload):
    """Observational representation telemetry with no gameplay authority."""

    supplied: bool = Field(description="Whether the caller supplied runtime telemetry.")
    telemetry: Optional[RuntimeTelemetryInput] = Field(
        default=None,
        description="Supplied observational telemetry.",
    )


class EncounterSummaryPayload(ComponentPayload):
    """Conservative post-encounter statistics from subjective evidence only."""

    available: bool = Field(description="Whether the subjective encounter has ended.")
    subjective_only: Literal[True] = Field(
        default=True,
        description="Declares that no objective post-match reveal was consulted.",
    )
    outcome: Literal[
        "ongoing",
        "controlled_survived",
        "controlled_defeated",
        "mixed_or_unknown",
    ] = Field(description="Outcome supportable from controlled and known death facts.")
    subjective_winning_faction: Optional[str] = Field(
        default=None,
        description="Winning faction inferable from terminal subjective facts.",
    )
    winner_basis: Literal[
        "ongoing",
        "controlled_survival",
        "known_survivor",
        "unknown",
    ] = Field(description="Subjective evidence supporting the winning-faction field.")
    rounds_observed: int = Field(ge=0, description="Latest subjectively known round number.")
    turn_starts_observed: int = Field(
        ge=0,
        description="Visible turn-start records in the retained subjective log tree.",
    )
    surviving_controlled_entity_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Controlled entities not subjectively known to be dead.",
    )
    defeated_controlled_entity_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Controlled entities subjectively known to be dead.",
    )
    known_hostile_death_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Non-controlled contacts subjectively known to have died.",
    )
    observed_damage_dealt: int = Field(
        ge=0,
        description="Damage in visible damage records sourced by controlled entities.",
    )
    observed_damage_taken: int = Field(
        ge=0,
        description="Damage in visible damage records targeting controlled entities.",
    )
    observed_healing_received: int = Field(
        ge=0,
        description="Healing in visible heal records targeting controlled entities.",
    )
    observed_conditions_applied: Tuple[Tuple[str, int], ...] = Field(
        default_factory=tuple,
        description="Visible condition-application counts by condition name.",
    )
    observed_event_families: Tuple[Tuple[str, int], ...] = Field(
        default_factory=tuple,
        description="Visible combat-log entry counts by typed entry family.",
    )
    command_count: int = Field(
        default=0,
        ge=0,
        description="Direct commands submitted by this hot runtime.",
    )
    inspection_count: int = Field(
        default=0,
        ge=0,
        description="Local inspection operations completed by this hot runtime.",
    )
    predicate_count: int = Field(
        default=0,
        ge=0,
        description="Declarative predicates present in the current local ledger.",
    )
    incomplete_statistics: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Statistics that cannot be claimed complete from subjective evidence.",
    )


class TypedJsonPresentationPayload(ComponentPayload):
    """Declaration of the canonical typed envelope presentation."""

    format: Literal["application/json"] = Field(
        default="application/json",
        description="Machine-readable presentation media type.",
    )
    schema_version: Literal[1] = Field(
        default=1,
        description="Typed representation-envelope schema version.",
    )
    emitted_component_ids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Components emitted before this presentation marker.",
    )


class ComponentErrorPayload(ComponentPayload):
    """Non-sensitive failure record for one optional representation component."""

    failed_component_id: str = Field(description="Component whose projection failed.")
    failed_component_version: str = Field(description="Version of the failed component.")
    error_type: str = Field(description="Python exception class without exception arguments.")
    message: str = Field(description="Stable non-sensitive component failure summary.")
    recoverable: bool = Field(description="Whether the envelope continued without this component.")


class CoreRevisionBlock(RepresentationBlock[CoreRevisionPayload]):
    """Discriminated block for subjective revision identity."""

    component_id: Literal["core.revision"] = Field(
        default="core.revision",
        description="Stable component discriminator.",
    )


class TurnCoreBlock(RepresentationBlock[TurnCorePayload]):
    """Discriminated block for complete turn core."""

    component_id: Literal["core.turn"] = Field(default="core.turn", description="Stable component discriminator.")


class ContactLedgerBlock(RepresentationBlock[ContactLedgerPayload]):
    """Discriminated block for contact partitions."""

    component_id: Literal["contacts.partition"] = Field(
        default="contacts.partition",
        description="Stable component discriminator.",
    )


class ObjectLedgerBlock(RepresentationBlock[ObjectLedgerPayload]):
    """Discriminated block for known objects."""

    component_id: Literal["objects.known"] = Field(
        default="objects.known",
        description="Stable component discriminator.",
    )


class TopologySummaryBlock(RepresentationBlock[TopologySummaryPayload]):
    """Discriminated block for known topology."""

    component_id: Literal["topology.summary"] = Field(
        default="topology.summary",
        description="Stable component discriminator.",
    )


class SpatialSceneBlock(RepresentationBlock[SpatialScenePayload]):
    """Discriminated block for the neutral spatial scene."""

    component_id: Literal["spatial.scene"] = Field(
        default="spatial.scene",
        description="Stable component discriminator.",
    )


class ActionFamilyBlock(RepresentationBlock[ActionFamilyPayload]):
    """Discriminated block for complete legal affordances and indexes."""

    component_id: Literal["actions.index"] = Field(
        default="actions.index",
        description="Stable component discriminator.",
    )


class RecentCombatLogsBlock(RepresentationBlock[RecentCombatLogsPayload]):
    """Discriminated block for bounded recent combat logs."""

    component_id: Literal["events.recent_logs"] = Field(
        default="events.recent_logs",
        description="Stable component discriminator.",
    )


class DecisionDeltaBlock(RepresentationBlock[DecisionDeltaPayload]):
    """Discriminated block for decision-boundary changes."""

    component_id: Literal["events.decision_delta"] = Field(
        default="events.decision_delta",
        description="Stable component discriminator.",
    )


class CombatHypothesisBlock(RepresentationBlock[CombatHypothesisPayload]):
    """Discriminated block for subjective combat hypotheses."""

    component_id: Literal["memory.combat_hypotheses"] = Field(
        default="memory.combat_hypotheses",
        description="Stable component discriminator.",
    )


class PredicateFocusBlock(RepresentationBlock[PredicateFocusPayload]):
    """Discriminated block for focused logical state."""

    component_id: Literal["predicates.focused"] = Field(
        default="predicates.focused",
        description="Stable component discriminator.",
    )


class WarningBlock(RepresentationBlock[WarningPayload]):
    """Discriminated block for compatibility warnings."""

    component_id: Literal["attention.current_warnings"] = Field(
        default="attention.current_warnings",
        description="Stable component discriminator.",
    )


class AdviceBlock(RepresentationBlock[AdvicePayload]):
    """Discriminated block for optional supplied policy advice."""

    component_id: Literal["oracle.policy"] = Field(
        default="oracle.policy",
        description="Stable component discriminator.",
    )


class RepresentationTelemetryBlock(RepresentationBlock[RepresentationTelemetryPayload]):
    """Discriminated block for observational runtime telemetry."""

    component_id: Literal["telemetry.runtime"] = Field(
        default="telemetry.runtime",
        description="Stable component discriminator.",
    )


class EncounterSummaryBlock(RepresentationBlock[EncounterSummaryPayload]):
    """Discriminated subjective post-encounter summary block."""

    component_id: Literal["encounter.summary"] = Field(
        default="encounter.summary",
        description="Stable component discriminator.",
    )


class TypedJsonPresentationBlock(RepresentationBlock[TypedJsonPresentationPayload]):
    """Discriminated block for canonical typed JSON presentation."""

    component_id: Literal["presentation.typed_json"] = Field(
        default="presentation.typed_json",
        description="Stable component discriminator.",
    )


class ComponentErrorBlock(RepresentationBlock[ComponentErrorPayload]):
    """Discriminated replacement emitted when an optional component fails."""

    component_id: Literal["component.error"] = Field(
        default="component.error",
        description="Stable failure-block discriminator.",
    )


CodexRepresentationBlock = Annotated[
    Union[
        CoreRevisionBlock,
        TurnCoreBlock,
        ContactLedgerBlock,
        ObjectLedgerBlock,
        TopologySummaryBlock,
        SpatialSceneBlock,
        ActionFamilyBlock,
        RecentCombatLogsBlock,
        DecisionDeltaBlock,
        CombatHypothesisBlock,
        PredicateFocusBlock,
        WarningBlock,
        AdviceBlock,
        RepresentationTelemetryBlock,
        EncounterSummaryBlock,
        TypedJsonPresentationBlock,
        ComponentErrorBlock,
    ],
    Field(discriminator="component_id"),
]


class ComponentExposureOmission(ComponentPayload):
    """One manifest component omitted from a particular envelope exposure."""

    component_id: str = Field(description="Registered component identity.")
    configured_exposure: ExposureTiming = Field(description="Exposure selected by the profile.")
    requested_exposure: ExposureTiming = Field(description="Exposure requested for this projection.")
    reason: Literal["disabled", "exposure_mismatch"] = Field(
        description="Why no block was emitted.",
    )


class CodexTurnRepresentation(ComponentPayload):
    """Canonical ordered envelope over typed subjective representation blocks."""

    schema_version: Literal[1] = Field(default=1, description="Envelope schema version.")
    profile_id: str = Field(description="Resolved representation profile identity.")
    profile_version: str = Field(description="Resolved representation profile version.")
    manifest_digest: str = Field(description="Digest of all behavior-affecting profile content.")
    exposure: ExposureTiming = Field(description="Lifecycle exposure represented by this envelope.")
    observation_cursor: int = Field(ge=0, description="Subjective cursor shared by every emitted block.")
    epoch_id: Optional[str] = Field(default=None, description="Decision epoch shared by emitted blocks.")
    generated_at: datetime = Field(description="Offset-aware envelope generation timestamp.")
    blocks: Tuple[CodexRepresentationBlock, ...] = Field(
        default_factory=tuple,
        description="Validated blocks in exact enabled profile order.",
    )
    exposure_omissions: Tuple[ComponentExposureOmission, ...] = Field(
        default_factory=tuple,
        description="Profile components intentionally absent at this exposure.",
    )
    total_timing_ms: float = Field(
        ge=0,
        description="Measured local projection duration in milliseconds.",
    )
    warnings: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Non-fatal envelope-level projection warnings.",
    )
