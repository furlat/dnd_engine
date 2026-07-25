"""Typed policy input, proposal, decision, and trace contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai.knowledge.models import AgentFacts
from dnd.ai.contracts.observation import SubjectiveWorldState
from dnd.ai.contracts.immutable import FrozenDict
from dnd.ai.contracts.semantics import (
    ActionTag,
    ConcentrationOperation,
    EffectDisposition,
    EffectCertainty,
    InformationOperation,
    OutcomeKind,
    SelfSetupDuration,
    SelfSetupMaintenanceSemantics,
    TruthValue,
)
from dnd.ai.contracts.control import ActionAffordance, OpportunityAttackExposure
from dnd.ai.contracts.decision import (
    EndTurnIntent,
    ExecuteIntent,
    PolicyIntent,
)


class PolicyModel(BaseModel):
    """Immutable base for one policy evaluation result."""

    model_config = ConfigDict(frozen=True)


class NodeStatus(str, Enum):
    """Behavior-tree node result without executing a command."""

    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


class PolicyGoal(str, Enum):
    """Stable tactical objective represented by one proposal."""

    DIRECT_PRESSURE = "direct_pressure"
    HOSTILE_CONTROL = "hostile_control"
    CONTROL_PRESERVATION = "control_preservation"
    CONDITIONAL_TARGET_EFFECT = "conditional_target_effect"
    SELF_SETUP = "self_setup"
    SURVIVAL_RECOVERY = "survival_recovery"
    POSITION_AND_SURVIVAL = "position_and_survival"
    INFORMATION_GATHERING = "information_gathering"
    ROUTINE = "routine"
    END_TURN = "end_turn"
    OTHER = "other"


class UtilityComponent(PolicyModel):
    """One named and inspectable contribution to a proposal score."""

    name: str = Field(description="Stable utility feature name.")
    raw_value: float = Field(description="Observed feature value.")
    weight: float = Field(description="Configured feature weight.")
    contribution: float = Field(description="Raw value multiplied by weight.")
    reason: str = Field(default="", description="Human-readable feature interpretation.")


class TargetApplicationEvidence(PolicyModel):
    """Number of outcome applications assigned to one subjective entity."""

    entity_uuid: str = Field(description="Subjectively known affected entity UUID.")
    applications: int = Field(ge=1, description="Independent outcome applications assigned to the entity.")


class DamageBlockerEvidence(PolicyModel):
    """Visible typed protection that fully blocks one modeled damage effect."""

    protection_id: str = Field(description="Stable identity of the protection rule.")
    effect_id: str = Field(description="Stable damage-effect identity blocked by the rule.")
    source_condition_semantic_key: Optional[str] = Field(
        default=None,
        description="Visible condition type that supplied the protection.",
    )


class EffectBlockHypothesisEvidence(PolicyModel):
    """Bounded observed risk that one target may block one exact effect."""

    target_uuid: str = Field(description="Subjectively identified target UUID.")
    effect_id: str = Field(description="Stable effect identity represented by the evidence.")
    blocked_episodes: int = Field(ge=1, description="Retained whole-action blocker episodes.")
    total_episodes: int = Field(ge=1, description="Retained episodes containing the target/effect pair.")
    blocked_applications: int = Field(ge=1, description="Blocked applications across retained episodes.")
    total_applications: int = Field(ge=1, description="All applications across retained episodes.")
    episode_log_indices: Tuple[int, ...] = Field(description="Subjective log indices supporting the estimate.")
    block_probability: float = Field(
        gt=0.0,
        lt=1.0,
        description="Posterior probability assigned once to the complete future action.",
    )


class DamageOutcomeEvidence(PolicyModel):
    """Inspectable outcome estimate for one subjective target allocation."""

    entity_uuid: str = Field(description="Subjectively known target UUID.")
    applications: int = Field(ge=1, description="Outcome applications represented by this estimate.")
    expected_raw_damage: float = Field(ge=0.0, description="Expected rolled damage before known HP capping.")
    expected_hp_loss: float = Field(ge=0.0, description="Expected reduction in known current HP.")
    expected_waste: float = Field(ge=0.0, description="Expected damage beyond known current HP.")
    defeat_probability: float = Field(ge=0.0, le=1.0, description="Probability modeled damage reaches known HP.")
    nonzero_probability: float = Field(ge=0.0, le=1.0, description="Probability modeled damage is nonzero.")
    guaranteed_zero: bool = Field(
        default=False,
        description="Whether disclosed facts prove that the effect deals zero damage.",
    )
    released_control_condition_semantic_keys: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Visible damage-ending control conditions this outcome may remove.",
    )
    expected_enemy_agency_restored: float = Field(
        default=0.0,
        ge=0.0,
        description="Expected surviving enemy turn agency restored by positive damage.",
    )
    blocker_evidence: Tuple[DamageBlockerEvidence, ...] = Field(
        default_factory=tuple,
        description="Visible typed protections responsible for guaranteed-zero damage.",
    )
    effect_block_hypothesis: Optional[EffectBlockHypothesisEvidence] = Field(
        default=None,
        description="Observed non-certain blocker risk applied once to this action allocation.",
    )
    model_scope: str = Field(description="Explicit subjective inputs represented by the estimate.")


class HealingOutcomeEvidence(PolicyModel):
    """Inspectable deterministic healing estimate for one known recipient."""

    entity_uuid: str = Field(description="Subjectively known entity receiving healing.")
    current_normal_hp: int = Field(description="Known restorable hit points before healing.")
    maximum_hp: int = Field(gt=0, description="Known maximum normal hit points.")
    expected_raw_healing: float = Field(ge=0.0, description="Literal healing declared by action semantics.")
    expected_hp_restored: float = Field(ge=0.0, description="Healing retained after the known maximum-HP cap.")
    expected_waste: float = Field(ge=0.0, description="Healing exceeding known missing normal hit points.")
    model_scope: str = Field(description="Explicit subjective inputs represented by the estimate.")


class SelfSetupOutcomeEvidence(PolicyModel):
    """Typed durable setup consequences used by one utility proposal."""

    semantic_id: str = Field(description="Stable semantic family of the setup action.")
    duration: SelfSetupDuration = Field(description="Declared lifetime class of the setup.")
    maximum_duration_rounds: Optional[int] = Field(
        default=None,
        gt=0,
        description="Known upper duration bound when the engine supplies one.",
    )
    condition_fact_ids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Actor condition facts guaranteed by successful execution.",
    )
    active_condition_semantic_keys: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Stable condition type keys used to detect an already-active setup.",
    )
    armor_class_bonus: int = Field(default=0, ge=0, description="Known armor-class increase.")
    movement_speed_multiplier: float = Field(default=1.0, ge=1.0, description="Known speed multiplier.")
    extra_actions_per_turn: int = Field(default=0, ge=0, description="Known additional general actions per turn.")
    grants_outgoing_attack_advantage: bool = Field(description="Whether actor attacks gain advantage.")
    grants_incoming_attack_disadvantage: bool = Field(description="Whether incoming attacks gain disadvantage.")
    grants_invisibility: bool = Field(description="Whether the actor becomes invisible.")
    incapacitates_on_removal: bool = Field(description="Whether ordinary removal carries incapacitation.")
    maintenance: Optional[SelfSetupMaintenanceSemantics] = Field(
        default=None,
        description="Disclosed stochastic setup-retention rule.",
    )
    first_maintenance_success_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Exact success probability of the first disclosed maintenance check.",
    )


class TargetPlanEvidence(PolicyModel):
    """Complete subjective target allocation underlying one proposal."""

    primary_target_uuid: Optional[str] = Field(default=None, description="Primary selected entity when present.")
    selected_target_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Ordered entity selections including repeated targets.",
    )
    affected_entity_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Stable unique entities explicitly affected by the row and allocation.",
    )
    hostile_entity_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Affected entities currently known as visible hostiles.",
    )
    controlled_entity_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Affected entities controlled by the session.",
    )
    allied_entity_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Affected visible entities subjectively known to share the controlled faction.",
    )
    applications: Tuple[TargetApplicationEvidence, ...] = Field(
        default_factory=tuple,
        description="Per-entity stochastic application counts.",
    )


class TargetEffectOutcomeEvidence(PolicyModel):
    """Selected target and semantic branch used by a conditional effect action."""

    entity_uuid: str = Field(description="Subjectively known recipient UUID.")
    effect_id: str = Field(description="Stable target-effect branch identity.")
    disposition: EffectDisposition = Field(description="Whether the selected branch helps or harms the recipient.")
    outcome_kind: OutcomeKind = Field(description="Mechanism controlling whether the branch applies.")
    condition_semantic_keys: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Stable conditions expected when the branch applies.",
    )


class CapabilityProjectionScope(str, Enum):
    """Spatial revision represented by a future capability projection."""

    FUTURE_TURN = "future_turn"
    MOVEMENT_ENDPOINT = "movement_endpoint"


class CapabilityModelStatus(str, Enum):
    """Knowledge state of a capability outcome estimate."""

    MODELED = "modeled"
    UNMODELED = "unmodeled"
    INSUFFICIENT_FACTS = "insufficient_facts"
    GUARANTEED_ZERO = "guaranteed_zero"


class CapabilityRangeState(str, Enum):
    """Current relationship between a projection and normal action range."""

    IN_RANGE = "in_range"
    OUT_OF_RANGE = "out_of_range"


class CapabilityResourceRequirement(PolicyModel):
    """Persistent resource required by a future-turn capability."""

    resource_id: str = Field(description="Stable spell-slot, named-resource, or item-charge identifier.")
    required: int = Field(ge=1, description="Amount consumed by one execution.")
    available: int = Field(ge=0, description="Amount currently disclosed by the decision epoch.")


class CapabilityTargetProjection(PolicyModel):
    """One capability evaluated against one subjective target and origin.

    This is derived policy evidence. It grants no action legality and never
    adds target facts that were absent from the session-subjective world.
    """

    projection_scope: CapabilityProjectionScope = Field(description="Spatial revision represented by the projection.")
    capability_id: str = Field(description="Actor-owned capability evaluated by the policy.")
    semantic_id: str = Field(description="Typed action meaning referenced by the capability.")
    target_entity_uuid: str = Field(description="Visible subjective target used for both outcome and geometry.")
    origin_position: Tuple[int, int] = Field(description="Known actor or movement-endpoint position used for geometry.")
    target_position: Tuple[int, int] = Field(description="Known subjective target position used for geometry.")
    distance_feet: int = Field(ge=0, description="Engine distance from origin to target.")
    normal_range_feet: int = Field(ge=5, description="Normal action range used by the future envelope.")
    preferred_minimum_range_feet: int = Field(ge=0, description="Preferred lower range bound for this capability.")
    range_state: CapabilityRangeState = Field(description="Whether the target is currently inside normal range.")
    requires_line_of_sight: bool = Field(description="Whether the action normally requires a visible line.")
    line_of_sight: TruthValue = Field(description="Line state derived only from subjective topology.")
    turn_refresh_assumed: bool = Field(description="Whether turn-local economy was assumed to refresh.")
    persistent_requirements: Tuple[CapabilityResourceRequirement, ...] = Field(
        default_factory=tuple,
        description="Spell slots, named resources, and item charges that do not refresh each turn.",
    )
    affordable_after_refresh: bool = Field(description="Whether disclosed persistent pools can pay the capability.")
    affordability_reasons: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Stable persistent resource identifiers that cannot be paid.",
    )
    concentration_operation: Optional[ConcentrationOperation] = Field(
        default=None,
        description="Typed concentration transition declared by the action semantics.",
    )
    actor_is_concentrating: bool = Field(description="Whether the actor is subjectively known to concentrate.")
    replaces_concentration: bool = Field(description="Whether this capability would replace active concentration.")
    model_status: CapabilityModelStatus = Field(description="Why pressure is modeled, unknown, or exactly zero.")
    expected_hp_loss: Optional[float] = Field(default=None, ge=0, description="Expected known-target HP loss when modeled.")
    defeat_probability: Optional[float] = Field(default=None, ge=0, le=1, description="Known-target defeat probability when modeled.")
    nonzero_probability: Optional[float] = Field(default=None, ge=0, le=1, description="Probability of nonzero HP loss when modeled.")
    pressure_value: Optional[float] = Field(default=None, ge=0, description="Policy pressure value derived from the modeled outcome.")
    model_scope: Optional[str] = Field(default=None, description="Subjective information scope consumed by the outcome estimator.")
    eligible: bool = Field(description="Whether this pair may define a future tactical envelope.")
    rejection_reasons: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Typed reasons this pair is excluded from future-envelope selection.",
    )

    @model_validator(mode="after")
    def validate_projection_consistency(self) -> "CapabilityTargetProjection":
        """Reject status, geometry, and concentration contradictions."""
        modeled_values = (
            self.expected_hp_loss,
            self.defeat_probability,
            self.nonzero_probability,
            self.pressure_value,
        )
        if self.model_status in {
            CapabilityModelStatus.MODELED,
            CapabilityModelStatus.GUARANTEED_ZERO,
        }:
            if any(value is None for value in modeled_values):
                raise ValueError("modeled capability projections require outcome values")
        elif any(value is not None for value in modeled_values) or self.model_scope is not None:
            raise ValueError("unknown capability projections cannot contain invented outcome values")
        if self.model_status is CapabilityModelStatus.GUARANTEED_ZERO:
            if self.pressure_value != 0 or self.nonzero_probability != 0:
                raise ValueError("guaranteed-zero projections require exact zero pressure")
        expected_range_state = (
            CapabilityRangeState.IN_RANGE
            if self.distance_feet <= self.normal_range_feet
            else CapabilityRangeState.OUT_OF_RANGE
        )
        if self.range_state is not expected_range_state:
            raise ValueError("range state does not match projection geometry")
        expected_replacement = (
            self.actor_is_concentrating
            and self.concentration_operation is ConcentrationOperation.START_OR_REPLACE
        )
        if self.replaces_concentration is not expected_replacement:
            raise ValueError("concentration replacement does not match the typed transition")
        if self.eligible and self.rejection_reasons:
            raise ValueError("eligible projections cannot contain rejection reasons")
        if self.eligible and self.model_status in {
            CapabilityModelStatus.UNMODELED,
            CapabilityModelStatus.GUARANTEED_ZERO,
        }:
            raise ValueError("unmodeled and guaranteed-zero projections are not actionable envelopes")
        return self


class SpacingEvidence(PolicyModel):
    """Subjective geometry used by a positioning or hold proposal."""

    reference_entity_uuid: Optional[str] = Field(default=None, description="Nearest visible hostile used as spacing reference.")
    reference_position: Optional[Tuple[int, int]] = Field(default=None, description="Known position of the spacing reference.")
    current_distance_cells: Optional[int] = Field(default=None, ge=0, description="Current actor-reference grid distance.")
    selected_distance_cells: Optional[int] = Field(default=None, ge=0, description="Distance after the proposed movement or hold.")
    spacing_floor_cells: int = Field(ge=0, description="Minimum preferred hostile spacing.")
    hostile_spacing_deficit_cells: int = Field(
        default=0,
        ge=0,
        description="Remaining distance needed to reach the hostile spacing floor.",
    )
    anchor_position: Optional[Tuple[int, int]] = Field(default=None, description="Proposed actor position or hold anchor.")
    nearest_controlled_ally_distance_cells: Optional[int] = Field(
        default=None,
        ge=0,
        description="Nearest controlled ally distance at the proposed anchor.",
    )
    ally_spacing_floor_cells: int = Field(default=0, ge=0, description="Preferred anti-area ally spacing.")
    ally_spacing_deficit_cells: Optional[int] = Field(
        default=None,
        ge=0,
        description="Remaining distance needed to reach the controlled-ally spacing floor.",
    )
    normal_attack_range_cells: Optional[int] = Field(
        default=None,
        ge=0,
        description="Longest typed normal tactical range available to the actor.",
    )
    offensive_range_deficit_cells: Optional[int] = Field(
        default=None,
        ge=0,
        description="Distance beyond the actor's longest typed normal tactical range.",
    )
    opportunity_attack_exposures: Tuple[OpportunityAttackExposure, ...] = Field(
        default_factory=tuple,
        description="Visible hostile threat exits priced by the selected route.",
    )
    capability_target_projection: Optional[CapabilityTargetProjection] = Field(
        default=None,
        description="Selected capability, target, resource, concentration, and outcome projection.",
    )


class ExplorationEvidence(PolicyModel):
    """Subjective frontier or remembered-contact geometry for exploration."""

    anchor_position: Tuple[int, int] = Field(description="Proposed movement destination or world-effect anchor.")
    movement_cost: int = Field(ge=0, description="Known path cost, or zero for a non-movement action.")
    revisited_this_turn: bool = Field(
        default=False,
        description="Whether the proposed destination is in the actor's voluntary same-turn path.",
    )
    unknown_frontier_count: int = Field(
        ge=0,
        description="Adjacent positions absent from accumulated subjective tile knowledge.",
    )
    remembered_target_uuid: Optional[str] = Field(
        default=None,
        description="Remembered contact whose last-known position guides investigation.",
    )
    current_remembered_distance: Optional[int] = Field(
        default=None,
        ge=0,
        description="Current distance in feet from the remembered contact.",
    )
    selected_remembered_distance: Optional[int] = Field(
        default=None,
        ge=0,
        description="Distance in feet after the proposed movement.",
    )
    expanded_remembered_search: bool = Field(
        default=False,
        description="Whether the destination expands a cleared last-known-position search.",
    )
    remembered_search_attempt: int = Field(
        default=0,
        ge=0,
        description="Completed investigation movements already retained for this contact.",
    )
    remembered_search_novelty_feet: int = Field(
        default=0,
        ge=0,
        description="Minimum distance from previously investigated positions.",
    )
    hazardous_route: bool = Field(description="Whether only a known hazardous route is supplied.")
    slow_path_cells: int = Field(ge=0, description="Known slow-terrain cells on the selected route.")
    information_operations: Tuple[InformationOperation, ...] = Field(
        default_factory=tuple,
        description="Typed positive information operations represented by the proposal.",
    )
    effect_certainty: Optional[EffectCertainty] = Field(
        default=None,
        description="Strongest declared certainty among represented information effects.",
    )
    effect_radius_feet: Optional[int] = Field(
        default=None,
        ge=0,
        description="Largest represented information-effect radius when declared.",
    )
    projected_unknown_position_count: int = Field(
        default=0,
        ge=0,
        description="Accumulated frontier positions inside the typed effect region.",
    )
    projected_obscured_position_count: int = Field(
        default=0,
        ge=0,
        description="Known dark or dim positions inside the typed effect region.",
    )
    granted_sense_types: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="New typed senses the controlled observer would gain.",
    )
    recipient_uuid: Optional[str] = Field(
        default=None,
        description="Controlled observer receiving a sense grant, when relevant.",
    )
    limited_resource_cost: float = Field(
        default=0.0,
        ge=0.0,
        description="Spell-slot, named-resource, and finite-item cost represented by the proposal.",
    )
    replaces_concentration: bool = Field(
        default=False,
        description="Whether executing the information action replaces observed concentration.",
    )


class ControlPreservationTargetEvidence(PolicyModel):
    """One newly established damage-ending control state worth preserving."""

    entity_uuid: str = Field(description="Subjectively visible controlled hostile.")
    condition_semantic_keys: Tuple[str, ...] = Field(
        description="Typed damage-ending full-agency conditions established this turn.",
    )
    expected_enemy_agency_preserved: float = Field(
        ge=0.0,
        description="Expected surviving enemy agency retained by withholding damage.",
    )


class ControlPreservationEvidence(PolicyModel):
    """Inspectable basis for yielding after establishing fragile control."""

    targets: Tuple[ControlPreservationTargetEvidence, ...] = Field(
        description="Visible controlled hostiles whose next turn remains denied.",
    )


class PolicyEvidence(PolicyModel):
    """Typed decision evidence carried unchanged through host and adapters."""

    target_plan: Optional[TargetPlanEvidence] = Field(default=None, description="Target allocation when relevant.")
    target_effects: Tuple[TargetEffectOutcomeEvidence, ...] = Field(
        default_factory=tuple,
        description="Per-recipient semantic branches selected by a conditional target effect.",
    )
    damage_outcomes: Tuple[DamageOutcomeEvidence, ...] = Field(
        default_factory=tuple,
        description="Per-target damage estimates used by scoring.",
    )
    healing: Optional[HealingOutcomeEvidence] = Field(
        default=None,
        description="Deterministic healing estimate when relevant.",
    )
    self_setup: Optional[SelfSetupOutcomeEvidence] = Field(
        default=None,
        description="Typed durable self-setup consequences when relevant.",
    )
    spacing: Optional[SpacingEvidence] = Field(default=None, description="Positioning geometry when relevant.")
    exploration: Optional[ExplorationEvidence] = Field(
        default=None,
        description="Subjective information-gathering geometry when relevant.",
    )
    control_preservation: Optional[ControlPreservationEvidence] = Field(
        default=None,
        description="Newly established damage-ending control preserved by yielding.",
    )


class PolicyProposal(PolicyModel):
    """One policy candidate over the current typed context."""

    intent: PolicyIntent = Field(description="Proposed controller intent.")
    goal: PolicyGoal = Field(default=PolicyGoal.OTHER, description="Stable tactical objective owning the proposal.")
    source_node: str = Field(description="Tree node or planner that produced the proposal.")
    reason: str = Field(description="Concise decision rationale.")
    score: float = Field(default=0.0, description="Comparable utility inside the owning choice point.")
    replay_key: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Identity-independent semantic ordering used only to break equal utility.",
    )
    utility_components: Tuple[UtilityComponent, ...] = Field(
        default_factory=tuple,
        description="Named contributions whose sum produces the score.",
    )
    semantic_tags: frozenset[ActionTag] = Field(default_factory=frozenset, description="Typed capabilities of the selected action.")
    evidence: PolicyEvidence = Field(default_factory=PolicyEvidence, description="Typed subjective basis for the proposal.")


class PolicyTraceStep(PolicyModel):
    """One inspectable behavior-tree or planner evaluation step."""

    node_path: str = Field(description="Stable path of the evaluated node.")
    status: NodeStatus = Field(description="Node outcome.")
    detail: str = Field(default="", description="Guard or selection explanation.")
    proposal_count: int = Field(default=0, ge=0, description="Proposals produced by this node.")


class NodeResult(PolicyModel):
    """Pure behavior-tree result containing proposals rather than side effects."""

    status: NodeStatus = Field(description="Node outcome.")
    proposals: Tuple[PolicyProposal, ...] = Field(default_factory=tuple, description="Candidates produced by this subtree.")
    trace: Tuple[PolicyTraceStep, ...] = Field(default_factory=tuple, description="Ordered subtree trace.")


class PolicyDecision(PolicyModel):
    """Selected proposal plus every candidate and evaluation trace."""

    selected: PolicyProposal = Field(description="Proposal selected for command submission.")
    candidates: Tuple[PolicyProposal, ...] = Field(default_factory=tuple, description="Candidates considered at the final choice point.")
    trace: Tuple[PolicyTraceStep, ...] = Field(default_factory=tuple, description="Complete decision trace.")


class PolicyDecisionCorrelation(PolicyModel):
    """Subjective revision identity shared by one policy decision event."""

    session_id: str = Field(description="Session whose subjective world was evaluated.")
    actor_uuid: str = Field(description="Controlled actor authorized by the epoch.")
    epoch_id: str = Field(description="Decision epoch evaluated by the policy.")
    observation_cursor: int = Field(ge=0, description="Subjective cursor used for evaluation.")
    decision_id: str = Field(description="Stable identity of this policy binding.")


class PolicyDecisionTelemetry(PolicyModel):
    """Canonical inspectable policy result emitted once per fresh binding."""

    schema_version: Literal[2] = Field(default=2, description="Policy telemetry schema version.")
    event_id: str = Field(description="Idempotency key used by the agent-event stream.")
    decision_id: str = Field(description="Stable identity of this policy binding.")
    policy_id: str = Field(description="Policy definition that produced the decision.")
    policy_version: str = Field(description="Version of the policy definition and scoring contract.")
    controller_mode: str = Field(description="Controller adapter consuming the shared policy.")
    correlation: PolicyDecisionCorrelation = Field(description="Subjective decision revision.")
    decision: PolicyDecision = Field(description="Exact selected proposal, candidates, and trace.")


class PolicyExecutionConstraints(PolicyModel):
    """Turn-local semantic exclusions learned from authoritative command results."""

    blocked_row_ids: frozenset[str] = Field(
        default_factory=frozenset,
        description="Exact current-epoch rows excluded after a rejected submission.",
    )
    blocked_semantic_keys: frozenset[str] = Field(
        default_factory=frozenset,
        description="Action families excluded for the current turn after a family-level failure.",
    )
    blocked_action_categories: frozenset[str] = Field(
        default_factory=frozenset,
        description="Engine action categories temporarily excluded by an observed interruption.",
    )

    def allows(self, row: ActionAffordance) -> bool:
        """Return whether one server-issued row remains eligible for policy ranking."""
        return (
            row.row_id not in self.blocked_row_ids
            and row.semantic_key not in self.blocked_semantic_keys
            and row.action_category not in self.blocked_action_categories
        )

    @property
    def replay_key(self) -> tuple[str, ...]:
        """Return a deterministic identity for cache and telemetry correlation."""
        return (
            *(f"row:{value}" for value in sorted(self.blocked_row_ids)),
            *(f"semantic:{value}" for value in sorted(self.blocked_semantic_keys)),
            *(f"category:{value}" for value in sorted(self.blocked_action_categories)),
        )


class RememberedContactSearchState(PolicyModel):
    """Actor-scoped negative-observation memory for one remembered contact."""

    entity_uuid: str = Field(description="Remembered subjective contact identity.")
    last_known_position: Tuple[int, int] = Field(description="Position anchoring the current search episode.")
    completed_investigations: int = Field(
        default=0,
        ge=0,
        description="Accepted investigation movements completed without reacquiring the contact.",
    )
    investigated_positions: Tuple[Tuple[int, int], ...] = Field(
        default_factory=tuple,
        description="Destinations already inspected during this search episode.",
    )


class PolicyControlMemoryView(PolicyModel):
    """Immutable non-world control memory supplied to shared policy evaluation."""

    remembered_contact_searches: Tuple[RememberedContactSearchState, ...] = Field(
        default_factory=tuple,
        description="Search episodes derived only from prior subjective decisions and observations.",
    )


class PolicyEvaluationIndex(PolicyModel):
    """Immutable decision-local projections reused by policy reducers.

    The index contains only facts already disclosed by the subjective world and
    legal rows already present in its current decision epoch. It is bound to one
    observation cursor and epoch so cached ordering or target data cannot cross
    decision revisions.
    """

    observation_cursor: int = Field(
        default=-1,
        description="Subjective observation revision represented by the index.",
    )
    epoch_id: Optional[str] = Field(
        default=None,
        description="Decision epoch represented by row indexes, when active.",
    )
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

    @classmethod
    def from_facts(cls, facts: AgentFacts) -> "PolicyEvaluationIndex":
        """Reference projections produced during typed fact derivation.

        Args:
            facts: Typed subjective facts for one observation and epoch revision.

        Returns:
            An immutable decision index without rewalking entities or rows.
        """
        return cls.model_construct(
            observation_cursor=facts.observation_cursor,
            epoch_id=facts.epoch_id,
            entity_replay_tokens=facts.contacts.entity_replay_tokens,
            known_hp_sort_keys=facts.contacts.known_hp_sort_keys,
            wounded_fractions=facts.contacts.wounded_fractions,
            healthy_fractions=facts.contacts.healthy_fractions,
            affected_entity_uuids_by_row_id=(
                facts.affordances.affected_entity_uuids_by_row_id
            ),
            primary_target_uuid_by_row_id=(
                facts.affordances.primary_target_uuid_by_row_id
            ),
            target_geometry_key_by_row_id=(
                facts.affordances.target_geometry_key_by_row_id
            ),
        )

    def model_post_init(self, __context: Any) -> None:
        """Freeze nested mappings after validation."""
        for field_name in (
            "entity_replay_tokens",
            "known_hp_sort_keys",
            "wounded_fractions",
            "healthy_fractions",
            "affected_entity_uuids_by_row_id",
            "primary_target_uuid_by_row_id",
            "target_geometry_key_by_row_id",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, FrozenDict):
                object.__setattr__(self, field_name, FrozenDict(value))


class PolicyContext(PolicyModel):
    """Shared deterministic and LLM policy input for one decision epoch."""

    world: SubjectiveWorldState = Field(description="Canonical session-subjective world.")
    facts: AgentFacts = Field(description="Typed derived policy facts for the same cursor.")
    execution_constraints: PolicyExecutionConstraints = Field(
        default_factory=PolicyExecutionConstraints,
        description="Authoritative-result exclusions applied before shared utility ranking.",
    )
    control_memory: PolicyControlMemoryView = Field(
        default_factory=PolicyControlMemoryView,
        description="Actor-scoped non-derivable control memory visible to every policy adapter.",
    )
    evaluation_index: PolicyEvaluationIndex = Field(
        default_factory=PolicyEvaluationIndex,
        description="Cursor-bound disclosed ordering, HP, and legal-row projections.",
        exclude=True,
    )
    deadline_monotonic: Optional[float] = Field(default=None, description="Optional local decision deadline.")

    def model_post_init(self, __context: Any) -> None:
        """Build the decision-local index when callers omit it."""
        if "evaluation_index" not in self.model_fields_set:
            object.__setattr__(
                self,
                "evaluation_index",
                PolicyEvaluationIndex.from_facts(self.facts),
            )

    def validate_alignment(self) -> None:
        """Raise when world, facts, and epoch do not describe one revision."""
        if self.world.observation_cursor != self.facts.observation_cursor:
            raise ValueError("Policy facts do not match the subjective world cursor")
        world_epoch_id = self.world.current_epoch.epoch_id if self.world.current_epoch is not None else None
        if world_epoch_id != self.facts.epoch_id:
            raise ValueError("Policy facts do not match the subjective decision epoch")
        if self.evaluation_index.observation_cursor != self.world.observation_cursor:
            raise ValueError("Policy evaluation index does not match the subjective world cursor")
        if self.evaluation_index.epoch_id != world_epoch_id:
            raise ValueError("Policy evaluation index does not match the subjective decision epoch")
