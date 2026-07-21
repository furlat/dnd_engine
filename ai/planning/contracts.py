"""Typed contracts for composed logical policy options."""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field
from ai.protocol.immutable import FrozenDict

from ai.protocol.semantics import (
    ActionSemantics,
    ConditionalEffect,
    FactExpression,
    FactValue,
    InformationEffect,
    LogicalEffect,
    ResourceEffect,
    StochasticEffect,
    TopologyEffect,
    TruthValue,
)


class PlanningModel(BaseModel):
    """Immutable base for logical planning contracts."""

    model_config = ConfigDict(frozen=True)


class RequirementKind(str, Enum):
    """How one step prerequisite relates to the preceding chain."""

    SATISFIED = "satisfied"
    EXTERNAL = "external"
    CONTINGENT = "contingent"
    OBSERVATION_DEFERRED = "observation_deferred"
    CONFLICT = "conflict"


class LogicalStep(PlanningModel):
    """One primitive or authored step available for option composition."""

    step_id: str = Field(description="Stable step identity.")
    description: str = Field(default="", description="Human-readable step purpose.")
    preconditions: FactExpression = Field(description="Subjective facts required before this step.")
    guaranteed_effects: Tuple[LogicalEffect, ...] = Field(
        default_factory=tuple,
        description="Effects established whenever the step successfully completes.",
    )
    conditional_effects: Tuple[ConditionalEffect, ...] = Field(
        default_factory=tuple,
        description="Effects established only when their logical guard holds.",
    )
    stochastic_effects: Tuple[StochasticEffect, ...] = Field(
        default_factory=tuple,
        description="Effects controlled by an uncertain resolution branch.",
    )
    resource_effects: Tuple[ResourceEffect, ...] = Field(
        default_factory=tuple,
        description="Action-economy and named-resource transitions.",
    )
    topology_effects: Tuple[TopologyEffect, ...] = Field(
        default_factory=tuple,
        description="World-topology transitions caused by the step.",
    )
    information_effects: Tuple[InformationEffect, ...] = Field(
        default_factory=tuple,
        description="Subjective information transitions caused by the step.",
    )
    explicit_observation_barrier: bool = Field(
        default=False,
        description="Whether execution must stop for fresh subjective observations.",
    )
    source_semantics: Optional[ActionSemantics] = Field(
        default=None,
        description="Complete primitive action contract when this step wraps an affordance.",
    )

    @classmethod
    def from_action_semantics(
        cls,
        step_id: str,
        semantics: ActionSemantics,
        *,
        description: str = "",
        explicit_observation_barrier: bool = False,
    ) -> "LogicalStep":
        """Build one composable step without copying policy utility."""
        return cls(
            step_id=step_id,
            description=description,
            preconditions=semantics.planning_preconditions,
            guaranteed_effects=semantics.guaranteed_effects,
            conditional_effects=semantics.conditional_effects,
            source_semantics=semantics,
            stochastic_effects=semantics.stochastic_effects,
            resource_effects=semantics.resource_effects,
            topology_effects=semantics.topology_effects,
            information_effects=semantics.information_effects,
            explicit_observation_barrier=explicit_observation_barrier,
        )


class PrerequisiteProof(PlanningModel):
    """Inspectable classification of one step's complete precondition."""

    step_id: str = Field(description="Step whose prerequisite was evaluated.")
    expression: FactExpression = Field(description="Complete prerequisite expression.")
    truth: TruthValue = Field(description="Truth under effects guaranteed by the chain prefix.")
    kind: RequirementKind = Field(description="How the prerequisite is handled by the option.")
    referenced_fact_ids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Stable facts read by the expression.",
    )
    established_by_step_ids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Prior guaranteed steps contributing referenced facts.",
    )
    detail: str = Field(description="Stable explanation of the classification.")


class EffectProvenance(PlanningModel):
    """Latest guaranteed effect establishing one abstract fact."""

    fact_id: str = Field(description="Established fact.")
    step_id: str = Field(description="Step that most recently changed it.")
    effect: LogicalEffect = Field(description="Effect applied by the step.")
    resulting_value: FactValue = Field(
        default=None,
        description="Known resulting value, or null when the transition remains symbolic.",
    )


class LogicalConflict(PlanningModel):
    """A proved contradiction preventing unconditional chain execution."""

    step_id: str = Field(description="Step blocked by the contradiction.")
    expression: FactExpression = Field(description="Prerequisite proved false.")
    referenced_fact_ids: Tuple[str, ...] = Field(description="Facts read by the prerequisite.")
    detail: str = Field(description="Stable conflict explanation.")


class ContingentBranch(PlanningModel):
    """Conditional or stochastic effects that cannot become guaranteed truth."""

    source_step_id: str = Field(description="Step producing the branch.")
    branch_kind: str = Field(description="conditional or stochastic.")
    condition: Optional[FactExpression] = Field(
        default=None,
        description="Logical condition guarding a conditional branch.",
    )
    outcome_kind: Optional[str] = Field(
        default=None,
        description="Resolution mechanism for a stochastic branch.",
    )
    probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Disclosed branch probability when known.",
    )
    effects: Tuple[LogicalEffect, ...] = Field(description="Effects established on this branch.")


class ObservationBarrier(PlanningModel):
    """Boundary beyond which logical planning requires real sensory feedback."""

    after_step_id: str = Field(description="Step after which fresh observation is required.")
    reasons: Tuple[str, ...] = Field(description="Typed reasons deterministic propagation stopped.")
    information_effects: Tuple[InformationEffect, ...] = Field(
        default_factory=tuple,
        description="Declared information opportunities without predicted content.",
    )
    topology_effects: Tuple[TopologyEffect, ...] = Field(
        default_factory=tuple,
        description="Topology changes capable of altering future perception.",
    )


class ResourceProjection(PlanningModel):
    """Prefix-safe resource requirement and final delta for one option."""

    resource_id: str = Field(description="Action-economy or named resource.")
    minimum_initial_amount: int = Field(
        ge=0,
        description="Smallest initial amount required by every deterministic prefix.",
    )
    final_delta: int = Field(description="Acquired/restored amount minus consumed amount.")
    total_consumed: int = Field(ge=0, description="Total deterministic consumption.")
    total_restored_or_acquired: int = Field(
        ge=0,
        description="Total deterministic restoration or acquisition.",
    )


class CompositionProof(PlanningModel):
    """Complete inspectable evidence for one forward-composed chain."""

    prerequisites: Tuple[PrerequisiteProof, ...] = Field(description="One classification per composed step.")
    effect_provenance: Tuple[EffectProvenance, ...] = Field(
        description="Latest guaranteed writer for every derived fact.",
    )
    conflicts: Tuple[LogicalConflict, ...] = Field(default_factory=tuple, description="Proved contradictions.")
    contingent_branches: Tuple[ContingentBranch, ...] = Field(
        default_factory=tuple,
        description="Branches deliberately excluded from guaranteed truth.",
    )
    observation_barriers: Tuple[ObservationBarrier, ...] = Field(
        default_factory=tuple,
        description="Sensory boundaries stopping deterministic propagation.",
    )
    resources: Tuple[ResourceProjection, ...] = Field(
        default_factory=tuple,
        description="Prefix-safe deterministic resource projections.",
    )


class OptionContract(PlanningModel):
    """Logical prerequisites and consequences derived for one action chain."""

    option_id: str = Field(description="Stable identity of the composed option.")
    steps: Tuple[LogicalStep, ...] = Field(description="Ordered primitive or authored steps.")
    initial_preconditions: Tuple[FactExpression, ...] = Field(
        default_factory=tuple,
        description="Unresolved requirements that must hold before option execution.",
    )
    guaranteed_effects: Tuple[LogicalEffect, ...] = Field(
        default_factory=tuple,
        description="Latest guaranteed effects before the first observation barrier.",
    )
    final_known_facts: Dict[str, FactValue] = Field(
        default_factory=dict,
        description="Known abstract values after the deterministic option prefix.",
    )
    completion: FactExpression = Field(description="Desired state used to recognize option completion.")

    invalidation: FactExpression = Field(description="Facts requiring option abandonment or repair.")
    proof: CompositionProof = Field(description="Evidence supporting every derived contract field.")
    consistent: bool = Field(description="Whether the deterministic prefix is contradiction-free.")
    requires_observation: bool = Field(
        description="Whether execution must stop for fresh subjective information.",
    )

    def model_post_init(self, context: object) -> None:
        """Freeze the derived fact mapping after Pydantic validation."""
        del context
        object.__setattr__(self, "final_known_facts", FrozenDict(self.final_known_facts))


class RegressionCandidate(PlanningModel):
    """Bounded backward-regressed chain verified by forward composition."""

    step_ids: Tuple[str, ...] = Field(description="Ordered step identities.")
    remaining_preconditions: Tuple[FactExpression, ...] = Field(
        description="Requirements not established inside the chain.",
    )
    option: OptionContract = Field(description="Forward verification of the regressed chain.")

