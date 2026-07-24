"""Revision-scoped derived facts, declarative predicates, and focus selection."""

from __future__ import annotations

from enum import Enum
import re
import time
from typing import Mapping, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai.knowledge.models import AgentFacts
from server.agent_protocol.observation import SubjectiveWorldState
from server.agent_protocol.semantics import (
    ActionTag,
    ComparisonOperator,
    FactExpression,
    FactOperator,
    FactPredicate,
    FactValue,
    TruthValue,
    evaluate_fact_expression,
)


MAX_EXPRESSION_DEPTH = 12
MAX_EXPRESSION_NODES = 128
_NAMESPACED_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


class PredicateLedgerModel(BaseModel):
    """Immutable base for predicate-ledger wire and persistence contracts."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class FactValueType(str, Enum):
    """Scalar value type produced by a registered derived fact."""

    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"


class FactSemanticIntent(str, Enum):
    """Stable reason a built-in fact exists in the agent representation."""

    ACTOR_STATE = "actor_state"
    ACTION_ECONOMY = "action_economy"
    CONTACT_SUMMARY = "contact_summary"
    OBJECT_SUMMARY = "object_summary"
    TOPOLOGY_SUMMARY = "topology_summary"
    AFFORDANCE_SUMMARY = "affordance_summary"
    MEMORY_SUMMARY = "memory_summary"
    ENCOUNTER_LIFECYCLE = "encounter_lifecycle"


class FactSourceDomain(str, Enum):
    """Subjective input domain read by a derived fact evaluator."""

    WORLD_STATE = "subjective_world_state"
    AGENT_FACTS = "agent_facts"


class FactTriggerPoint(str, Enum):
    """Runtime boundary at which a derived fact may be refreshed."""

    SUBJECTIVE_REVISION = "subjective_revision"


class FactPersistenceScope(str, Enum):
    """Lifetime guaranteed for a fact observation."""

    REVISION = "revision"


class FactSubjectivityContract(str, Enum):
    """Information boundary promised by a derived fact."""

    SESSION_SUBJECTIVE_ONLY = "session_subjective_only"


class FocusOverflowOrdering(str, Enum):
    """Deterministic ordering used when focus exceeds its item budget."""

    PRIORITY_THEN_ID = "priority_then_id"


class DerivedFactDefinition(PredicateLedgerModel):
    """Auditable definition of one built-in subjective scalar fact."""

    fact_id: str = Field(description="Stable namespaced fact identifier.")
    version: str = Field(default="1.0.0", description="Evaluator contract version.")
    description: str = Field(description="Human-readable meaning of the fact.")
    value_type: FactValueType = Field(description="Scalar type produced when known.")
    semantic_intent: FactSemanticIntent = Field(description="Why the fact is exposed.")
    dependencies: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Other stable fact ids needed to interpret this fact.",
    )
    source_domains: tuple[FactSourceDomain, ...] = Field(
        description="Subjective inputs read by the built-in evaluator.",
    )
    trigger_points: tuple[FactTriggerPoint, ...] = Field(
        default=(FactTriggerPoint.SUBJECTIVE_REVISION,),
        description="Runtime boundaries that invalidate the observation.",
    )
    persistence_scope: FactPersistenceScope = Field(
        default=FactPersistenceScope.REVISION,
        description="Lifetime of one computed observation.",
    )
    subjectivity_contract: FactSubjectivityContract = Field(
        default=FactSubjectivityContract.SESSION_SUBJECTIVE_ONLY,
        description="Information boundary used by the evaluator.",
    )
    evaluator_id: str = Field(description="Stable built-in evaluator identity.")
    evaluator_version: str = Field(default="1.0.0", description="Built-in evaluator version.")

    @field_validator("fact_id")
    @classmethod
    def validate_fact_id(cls, value: str) -> str:
        """Require stable namespaced identifiers independent of display text."""
        if _NAMESPACED_ID_PATTERN.fullmatch(value) is None:
            raise ValueError("fact_id must be a lowercase namespaced identifier")
        return value


class DerivedFactObservation(PredicateLedgerModel):
    """One typed fact value evaluated for an exact subjective revision."""

    fact_id: str = Field(description="Registered fact identifier.")
    observation_cursor: int = Field(ge=0, description="Subjective revision represented.")
    epoch_id: Optional[str] = Field(default=None, description="Decision epoch represented, if any.")
    value: FactValue = Field(default=None, description="Known scalar value, or null when unknown.")
    truth: TruthValue = Field(description="Knownness, or the value itself for booleans.")
    evidence_refs: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Stable subjective inputs supporting the observation.",
    )
    evaluator_id: str = Field(description="Evaluator that produced this observation.")
    evaluator_version: str = Field(description="Version of the evaluator used.")
    changed: bool = Field(default=False, description="Whether the observation changed from the prior revision.")
    error: Optional[str] = Field(default=None, description="Evaluator failure retained without fabricating false.")

    @model_validator(mode="after")
    def validate_truth_matches_value(self) -> "DerivedFactObservation":
        """Keep boolean truth and scalar knownness internally consistent."""
        if self.error is not None and self.truth is not TruthValue.UNKNOWN:
            raise ValueError("A failed fact observation must be UNKNOWN")
        if self.value is None and self.truth is not TruthValue.UNKNOWN:
            raise ValueError("A null fact observation must be UNKNOWN")
        if isinstance(self.value, bool):
            expected = TruthValue.TRUE if self.value else TruthValue.FALSE
            if self.truth is not expected:
                raise ValueError("Boolean fact truth must agree with its value")
        elif self.value is not None and self.truth is not TruthValue.TRUE:
            raise ValueError("A known scalar fact must use TRUE as its availability truth")
        return self


class PredicateDefinition(PredicateLedgerModel):
    """Session-local declarative proposition over registered scalar facts."""

    predicate_id: str = Field(description="Stable namespaced predicate identifier.")
    version: str = Field(default="1.0.0", description="Declarative contract version.")
    description: str = Field(description="Human-readable proposition meaning.")
    semantic_intent: str = Field(
        min_length=1,
        description="Declared purpose of this proposition, not tactical truth.",
    )
    expression: FactExpression = Field(description="JSON-native three-valued expression.")

    @field_validator("predicate_id")
    @classmethod
    def validate_predicate_id(cls, value: str) -> str:
        """Require a stable namespace for session-authored declarations."""
        if _NAMESPACED_ID_PATTERN.fullmatch(value) is None:
            raise ValueError("predicate_id must be a lowercase namespaced identifier")
        return value


class PredicateEvaluation(PredicateLedgerModel):
    """Three-valued result of one predicate at an exact revision."""

    predicate_id: str = Field(description="Registered predicate identifier.")
    observation_cursor: int = Field(ge=0, description="Subjective revision represented.")
    epoch_id: Optional[str] = Field(default=None, description="Decision epoch represented, if any.")
    truth: TruthValue = Field(description="Three-valued predicate result.")
    referenced_fact_ids: tuple[str, ...] = Field(description="Facts read by the expression.")
    evidence_refs: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Subjective evidence inherited from referenced facts.",
    )
    changed: bool = Field(default=False, description="Whether truth or an input fact changed.")
    previous_truth: Optional[TruthValue] = Field(default=None, description="Prior result when one exists.")
    elapsed_ms: float = Field(ge=0.0, description="Local deterministic evaluation time.")


class PredicateFocusProfile(PredicateLedgerModel):
    """Attention rules selecting predicates for automatic presentation only."""

    profile_id: str = Field(description="Stable focus-profile identity.")
    always_include: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Predicate ids included in every automatic presentation.",
    )
    include_when_true: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Predicate ids included automatically when their result is true.",
    )
    include_when_false: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Predicate ids included automatically when their result is false.",
    )
    include_when_unknown: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Predicate ids included automatically when their result is unknown.",
    )
    include_when_changed: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Predicate ids included automatically when their value changed.",
    )
    query_only: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Predicate ids excluded from automatic output but available to inspection.",
    )
    max_automatic_items: int = Field(
        default=16,
        ge=0,
        description="Maximum predicate evaluations placed in automatic output.",
    )
    overflow_ordering: FocusOverflowOrdering = Field(
        default=FocusOverflowOrdering.PRIORITY_THEN_ID,
        description="Deterministic ordering used when matching predicates exceed the budget.",
    )

    @field_validator("profile_id")
    @classmethod
    def validate_profile_id(cls, value: str) -> str:
        """Keep profile identity stable in experiment manifests."""
        if _NAMESPACED_ID_PATTERN.fullmatch(value) is None:
            raise ValueError("profile_id must be a lowercase namespaced identifier")
        return value

    @field_validator(
        "always_include",
        "include_when_true",
        "include_when_false",
        "include_when_unknown",
        "include_when_changed",
        "query_only",
    )
    @classmethod
    def validate_predicate_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Reject unstable focus entries and duplicate declarations."""
        if len(values) != len(set(values)):
            raise ValueError("focus predicate ids must be unique within each rule")
        if any(_NAMESPACED_ID_PATTERN.fullmatch(value) is None for value in values):
            raise ValueError("focus rules require lowercase namespaced predicate ids")
        return values


class PredicateFocusResult(PredicateLedgerModel):
    """Bounded automatic view selected from a complete predicate ledger."""

    profile_id: str = Field(description="Focus profile applied.")
    selected: tuple[PredicateEvaluation, ...] = Field(description="Automatically exposed evaluations.")
    matched_count: int = Field(ge=0, description="Evaluations matching before the item budget.")
    omitted_count: int = Field(ge=0, description="Matched evaluations excluded by the item budget.")
    query_only_count: int = Field(ge=0, description="Registered evaluations explicitly reserved for inspection.")


class PredicateLedgerSnapshot(PredicateLedgerModel):
    """Complete fact and predicate ledger for one subjective revision."""

    observation_cursor: int = Field(ge=0, description="Subjective revision represented.")
    epoch_id: Optional[str] = Field(default=None, description="Decision epoch represented, if any.")
    facts: tuple[DerivedFactObservation, ...] = Field(description="Complete registered fact observations.")
    predicates: tuple[PredicateEvaluation, ...] = Field(description="Complete registered predicate evaluations.")
    focus: Optional[PredicateFocusResult] = Field(
        default=None,
        description="Optional automatic selection; complete ledgers remain above.",
    )

    def fact(self, fact_id: str) -> DerivedFactObservation:
        """Return one fact observation by stable identity."""
        for observation in self.facts:
            if observation.fact_id == fact_id:
                return observation
        raise KeyError(fact_id)

    def predicate(self, predicate_id: str) -> PredicateEvaluation:
        """Return one predicate evaluation by stable identity."""
        for evaluation in self.predicates:
            if evaluation.predicate_id == predicate_id:
                return evaluation
        raise KeyError(predicate_id)

    def known_fact_values(self) -> dict[str, FactValue]:
        """Return only known values for three-valued expression evaluation."""
        return {
            observation.fact_id: observation.value
            for observation in self.facts
            if observation.truth is not TruthValue.UNKNOWN
        }


class PredicateLedger:
    """Mutable session-local catalog producing immutable revision snapshots."""

    def __init__(self, *, include_builtin_predicates: bool = True) -> None:
        self._fact_definitions = {
            definition.fact_id: definition
            for definition in builtin_fact_definitions()
        }
        self._predicate_definitions: dict[str, PredicateDefinition] = {}
        if include_builtin_predicates:
            for definition in builtin_predicate_definitions():
                self.register_predicate(definition)
        self._latest_snapshot: Optional[PredicateLedgerSnapshot] = None

    @property
    def fact_definitions(self) -> tuple[DerivedFactDefinition, ...]:
        """Return the deterministic complete built-in fact catalog."""
        return tuple(self._fact_definitions[key] for key in sorted(self._fact_definitions))

    @property
    def predicate_definitions(self) -> tuple[PredicateDefinition, ...]:
        """Return all registered predicates in deterministic identity order."""
        return tuple(self._predicate_definitions[key] for key in sorted(self._predicate_definitions))

    def register_predicate(
        self,
        definition: PredicateDefinition | Mapping[str, object],
    ) -> PredicateDefinition:
        """Validate and register one JSON-native predicate definition.

        No evaluator source, imports, callables, or executable payload is part of
        this contract. Mapping input is accepted solely through Pydantic's
        declarative validation boundary.
        """
        parsed = (
            definition
            if isinstance(definition, PredicateDefinition)
            else PredicateDefinition.model_validate(definition)
        )
        if parsed.predicate_id in self._predicate_definitions:
            raise ValueError(f"Predicate already registered: {parsed.predicate_id}")
        depth, nodes = _expression_shape(parsed.expression)
        if depth > MAX_EXPRESSION_DEPTH:
            raise ValueError(
                f"Predicate expression depth {depth} exceeds {MAX_EXPRESSION_DEPTH}"
            )
        if nodes > MAX_EXPRESSION_NODES:
            raise ValueError(
                f"Predicate expression node count {nodes} exceeds {MAX_EXPRESSION_NODES}"
            )
        referenced = _referenced_fact_ids(parsed.expression)
        missing = sorted(referenced.difference(self._fact_definitions))
        if missing:
            raise ValueError(f"Predicate references unregistered facts: {', '.join(missing)}")
        self._predicate_definitions[parsed.predicate_id] = parsed
        return parsed

    def evaluate(
        self,
        world: SubjectiveWorldState,
        agent_facts: AgentFacts,
        *,
        focus_profile: Optional[PredicateFocusProfile] = None,
        previous_snapshot: Optional[PredicateLedgerSnapshot] = None,
    ) -> PredicateLedgerSnapshot:
        """Evaluate the complete catalog against one aligned subjective revision."""
        _validate_revision_alignment(world, agent_facts)
        previous = previous_snapshot if previous_snapshot is not None else self._latest_snapshot
        if previous is not None and previous.observation_cursor >= world.observation_cursor:
            previous = None
        previous_facts = {
            observation.fact_id: observation
            for observation in previous.facts
        } if previous is not None else {}

        fact_observations = tuple(
            _evaluate_builtin_fact(
                definition,
                world,
                agent_facts,
                previous_facts.get(definition.fact_id),
            )
            for definition in self.fact_definitions
        )
        known_values = {
            observation.fact_id: observation.value
            for observation in fact_observations
            if observation.truth is not TruthValue.UNKNOWN
        }
        observation_by_id = {
            observation.fact_id: observation
            for observation in fact_observations
        }
        previous_predicates = {
            evaluation.predicate_id: evaluation
            for evaluation in previous.predicates
        } if previous is not None else {}
        evaluations = tuple(
            _evaluate_predicate_definition(
                definition,
                world,
                known_values,
                observation_by_id,
                previous_predicates.get(definition.predicate_id),
            )
            for definition in self.predicate_definitions
        )
        snapshot = PredicateLedgerSnapshot(
            observation_cursor=world.observation_cursor,
            epoch_id=agent_facts.epoch_id,
            facts=fact_observations,
            predicates=evaluations,
        )
        if focus_profile is not None:
            snapshot = self.apply_focus(snapshot, focus_profile)
        self._latest_snapshot = snapshot
        return snapshot

    def apply_focus(
        self,
        snapshot: PredicateLedgerSnapshot,
        profile: PredicateFocusProfile,
    ) -> PredicateLedgerSnapshot:
        """Attach a bounded automatic selection without changing either ledger."""
        registered = set(self._predicate_definitions)
        configured = _focus_profile_ids(profile)
        missing = sorted(configured.difference(registered))
        if missing:
            raise ValueError(f"Focus profile references unregistered predicates: {', '.join(missing)}")

        query_only = set(profile.query_only)
        priority_by_id: dict[str, int] = {}

        def include(predicate_ids: Sequence[str], priority: int) -> None:
            for predicate_id in predicate_ids:
                if predicate_id not in query_only:
                    priority_by_id[predicate_id] = min(
                        priority,
                        priority_by_id.get(predicate_id, priority),
                    )

        include(profile.always_include, 0)
        evaluations = {row.predicate_id: row for row in snapshot.predicates}
        include(
            tuple(
                predicate_id
                for predicate_id in profile.include_when_changed
                if evaluations[predicate_id].changed
            ),
            1,
        )
        include(
            tuple(
                predicate_id
                for predicate_id in profile.include_when_true
                if evaluations[predicate_id].truth is TruthValue.TRUE
            ),
            2,
        )
        include(
            tuple(
                predicate_id
                for predicate_id in profile.include_when_false
                if evaluations[predicate_id].truth is TruthValue.FALSE
            ),
            3,
        )
        include(
            tuple(
                predicate_id
                for predicate_id in profile.include_when_unknown
                if evaluations[predicate_id].truth is TruthValue.UNKNOWN
            ),
            4,
        )
        ordered_ids = sorted(
            priority_by_id,
            key=lambda predicate_id: (priority_by_id[predicate_id], predicate_id),
        )
        selected_ids = ordered_ids[:profile.max_automatic_items]
        result = PredicateFocusResult(
            profile_id=profile.profile_id,
            selected=tuple(evaluations[predicate_id] for predicate_id in selected_ids),
            matched_count=len(ordered_ids),
            omitted_count=max(0, len(ordered_ids) - len(selected_ids)),
            query_only_count=sum(predicate_id in evaluations for predicate_id in query_only),
        )
        return snapshot.model_copy(update={"focus": result})

    def reset_history(self) -> None:
        """Forget change-detection history without changing registered definitions."""
        self._latest_snapshot = None


def builtin_fact_definitions() -> tuple[DerivedFactDefinition, ...]:
    """Return the stable first-delivery fact catalog."""
    definitions = [
        _fact_definition(
            "actor.is_active",
            FactValueType.BOOLEAN,
            FactSemanticIntent.ACTOR_STATE,
            "Whether this session controls the active actor.",
        ),
        _fact_definition(
            "actor.hp",
            FactValueType.INTEGER,
            FactSemanticIntent.ACTOR_STATE,
            "Known current actor hit points.",
        ),
        _fact_definition(
            "actor.max_hp",
            FactValueType.INTEGER,
            FactSemanticIntent.ACTOR_STATE,
            "Known maximum actor hit points.",
        ),
        _fact_definition(
            "actor.hp_fraction",
            FactValueType.FLOAT,
            FactSemanticIntent.ACTOR_STATE,
            "Known current hit-point fraction.",
            dependencies=("actor.hp", "actor.max_hp"),
        ),
        _fact_definition(
            "actor.is_wounded",
            FactValueType.BOOLEAN,
            FactSemanticIntent.ACTOR_STATE,
            "Whether known actor hit points are below maximum.",
            dependencies=("actor.hp", "actor.max_hp"),
        ),
        _fact_definition(
            "actor.is_concentrating",
            FactValueType.BOOLEAN,
            FactSemanticIntent.ACTOR_STATE,
            "Whether the active actor is observed concentrating.",
        ),
        _fact_definition(
            "actor.action_available",
            FactValueType.BOOLEAN,
            FactSemanticIntent.ACTION_ECONOMY,
            "Whether at least one standard action remains.",
        ),
        _fact_definition(
            "actor.bonus_action_available",
            FactValueType.BOOLEAN,
            FactSemanticIntent.ACTION_ECONOMY,
            "Whether at least one bonus action remains.",
        ),
        _fact_definition(
            "actor.reaction_available",
            FactValueType.BOOLEAN,
            FactSemanticIntent.ACTION_ECONOMY,
            "Whether at least one reaction remains.",
        ),
        _fact_definition(
            "actor.movement_remaining",
            FactValueType.INTEGER,
            FactSemanticIntent.ACTION_ECONOMY,
            "Known movement remaining in feet.",
        ),
        _fact_definition(
            "contacts.visible_hostile_count",
            FactValueType.INTEGER,
            FactSemanticIntent.CONTACT_SUMMARY,
            "Visible living hostile count.",
        ),
        _fact_definition(
            "contacts.remembered_hostile_count",
            FactValueType.INTEGER,
            FactSemanticIntent.CONTACT_SUMMARY,
            "Remembered living hostile count.",
        ),
        _fact_definition(
            "contacts.visible_ally_count",
            FactValueType.INTEGER,
            FactSemanticIntent.CONTACT_SUMMARY,
            "Visible living ally count.",
        ),
        _fact_definition(
            "contacts.unknown_relationship_count",
            FactValueType.INTEGER,
            FactSemanticIntent.CONTACT_SUMMARY,
            "Visible or remembered contacts with unknown relationship.",
        ),
        _fact_definition(
            "objects.known_closed_door_count",
            FactValueType.INTEGER,
            FactSemanticIntent.OBJECT_SUMMARY,
            "Subjectively known closed-door count.",
        ),
        _fact_definition(
            "topology.known_hazard_count",
            FactValueType.INTEGER,
            FactSemanticIntent.TOPOLOGY_SUMMARY,
            "Known hazardous-position count.",
        ),
        _fact_definition(
            "topology.known_slow_count",
            FactValueType.INTEGER,
            FactSemanticIntent.TOPOLOGY_SUMMARY,
            "Known slow-position count.",
        ),
        _fact_definition(
            "affordances.total_count",
            FactValueType.INTEGER,
            FactSemanticIntent.AFFORDANCE_SUMMARY,
            "Current server-issued affordance count.",
        ),
        _fact_definition(
            "affordances.affordable_count",
            FactValueType.INTEGER,
            FactSemanticIntent.AFFORDANCE_SUMMARY,
            "Currently affordable affordance count.",
        ),
        _fact_definition(
            "memory.effect_block_hypothesis_count",
            FactValueType.INTEGER,
            FactSemanticIntent.MEMORY_SUMMARY,
            "Retained effect-block hypothesis count.",
        ),
        _fact_definition(
            "encounter.is_terminal",
            FactValueType.BOOLEAN,
            FactSemanticIntent.ENCOUNTER_LIFECYCLE,
            "Whether the subjective encounter is ended.",
            source_domains=(FactSourceDomain.WORLD_STATE,),
        ),
    ]
    definitions.extend(
        _fact_definition(
            _tag_fact_id(tag),
            FactValueType.INTEGER,
            FactSemanticIntent.AFFORDANCE_SUMMARY,
            f"Affordance row count carrying the stable {tag.value} semantic tag.",
        )
        for tag in ActionTag
    )
    return tuple(definitions)


def builtin_predicate_definitions() -> tuple[PredicateDefinition, ...]:
    """Return neutral built-in propositions without tactical preferences."""
    return (
        _comparison_predicate(
            "actor.can_act",
            "Whether the controlled actor has a standard action.",
            "actor.action_available",
            ComparisonOperator.EQUALS,
            True,
        ),
        _comparison_predicate(
            "contacts.has_visible_hostile",
            "Whether at least one hostile is currently visible.",
            "contacts.visible_hostile_count",
            ComparisonOperator.GREATER_THAN,
            0,
        ),
        _comparison_predicate(
            "contacts.has_remembered_hostile",
            "Whether at least one hostile is remembered but not visible.",
            "contacts.remembered_hostile_count",
            ComparisonOperator.GREATER_THAN,
            0,
        ),
        _comparison_predicate(
            "objects.has_known_closed_door",
            "Whether at least one closed door is known.",
            "objects.known_closed_door_count",
            ComparisonOperator.GREATER_THAN,
            0,
        ),
        _comparison_predicate(
            "topology.has_known_hazard",
            "Whether at least one hazardous position is known.",
            "topology.known_hazard_count",
            ComparisonOperator.GREATER_THAN,
            0,
        ),
        _comparison_predicate(
            "affordances.has_legal_action",
            "Whether the current epoch contains an affordance.",
            "affordances.total_count",
            ComparisonOperator.GREATER_THAN,
            0,
        ),
        _comparison_predicate(
            "memory.has_effect_block_hypothesis",
            "Whether subjective combat memory retains an effect-block hypothesis.",
            "memory.effect_block_hypothesis_count",
            ComparisonOperator.GREATER_THAN,
            0,
        ),
        _comparison_predicate(
            "encounter.is_terminal",
            "Whether the encounter has reached its terminal state.",
            "encounter.is_terminal",
            ComparisonOperator.EQUALS,
            True,
        ),
    )


def _fact_definition(
    fact_id: str,
    value_type: FactValueType,
    intent: FactSemanticIntent,
    description: str,
    *,
    dependencies: tuple[str, ...] = (),
    source_domains: tuple[FactSourceDomain, ...] = (FactSourceDomain.AGENT_FACTS,),
) -> DerivedFactDefinition:
    """Build one built-in fact definition with stable evaluator identity."""
    return DerivedFactDefinition(
        fact_id=fact_id,
        description=description,
        value_type=value_type,
        semantic_intent=intent,
        dependencies=dependencies,
        source_domains=source_domains,
        evaluator_id=f"builtin.{fact_id}",
    )


def _comparison_predicate(
    predicate_id: str,
    description: str,
    fact_id: str,
    comparison: ComparisonOperator,
    expected_value: FactValue,
) -> PredicateDefinition:
    """Build one built-in comparison predicate over a registered fact."""
    return PredicateDefinition(
        predicate_id=predicate_id,
        description=description,
        semantic_intent="neutral_state_proposition",
        expression=FactExpression(
            operator=FactOperator.PREDICATE,
            predicate=FactPredicate(
                fact_id=fact_id,
                comparison=comparison,
                expected_value=expected_value,
            ),
        ),
    )


def _validate_revision_alignment(world: SubjectiveWorldState, facts: AgentFacts) -> None:
    """Reject facts derived from a different subjective cursor or epoch."""
    if world.observation_cursor != facts.observation_cursor:
        raise ValueError(
            "SubjectiveWorldState and AgentFacts must represent the same observation cursor"
        )
    world_epoch_id = world.current_epoch.epoch_id if world.current_epoch is not None else None
    if world_epoch_id != facts.epoch_id:
        raise ValueError("SubjectiveWorldState and AgentFacts must represent the same decision epoch")


def _evaluate_builtin_fact(
    definition: DerivedFactDefinition,
    world: SubjectiveWorldState,
    facts: AgentFacts,
    previous: Optional[DerivedFactObservation],
) -> DerivedFactObservation:
    """Evaluate one built-in fact and preserve errors as unknown observations."""
    try:
        value, evidence_refs = _builtin_fact_value(definition.fact_id, world, facts)
        _validate_fact_value(definition, value)
        truth = _truth_for_fact_value(value)
        error = None
    except Exception as exc:
        value = None
        evidence_refs = tuple(domain.value for domain in definition.source_domains)
        truth = TruthValue.UNKNOWN
        error = f"{type(exc).__name__}: {exc}"
    changed = previous is not None and (
        previous.value != value or previous.truth is not truth or previous.error != error
    )
    return DerivedFactObservation(
        fact_id=definition.fact_id,
        observation_cursor=world.observation_cursor,
        epoch_id=facts.epoch_id,
        value=value,
        truth=truth,
        evidence_refs=evidence_refs,
        evaluator_id=definition.evaluator_id,
        evaluator_version=definition.evaluator_version,
        changed=changed,
        error=error,
    )


def _builtin_fact_value(
    fact_id: str,
    world: SubjectiveWorldState,
    facts: AgentFacts,
) -> tuple[FactValue, tuple[str, ...]]:
    """Return one built-in value and its subjective evidence references."""
    actor = facts.actor
    economy = actor.economy
    actor_known = actor.actor_uuid is not None
    fixed: dict[str, tuple[FactValue, tuple[str, ...]]] = {
        "actor.is_active": (actor.is_my_turn, ("agent_facts.actor.is_my_turn",)),
        "actor.hp": (actor.hp if actor_known else None, ("agent_facts.actor.hp",)),
        "actor.max_hp": (actor.max_hp if actor_known else None, ("agent_facts.actor.max_hp",)),
        "actor.hp_fraction": (
            actor.hp / actor.max_hp
            if actor_known and actor.hp is not None and actor.max_hp is not None and actor.max_hp > 0
            else None,
            ("agent_facts.actor.hp", "agent_facts.actor.max_hp"),
        ),
        "actor.is_wounded": (
            actor.hp < actor.max_hp
            if actor_known and actor.hp is not None and actor.max_hp is not None
            else None,
            ("agent_facts.actor.hp", "agent_facts.actor.max_hp"),
        ),
        "actor.is_concentrating": (
            actor.is_concentrating if actor_known else None,
            ("agent_facts.actor.is_concentrating",),
        ),
        "actor.action_available": (
            economy.actions > 0 if actor_known and economy is not None else None,
            ("agent_facts.actor.economy.actions",),
        ),
        "actor.bonus_action_available": (
            economy.bonus_actions > 0 if actor_known and economy is not None else None,
            ("agent_facts.actor.economy.bonus_actions",),
        ),
        "actor.reaction_available": (
            economy.reactions > 0 if actor_known and economy is not None else None,
            ("agent_facts.actor.economy.reactions",),
        ),
        "actor.movement_remaining": (
            economy.movement_remaining if actor_known and economy is not None else None,
            ("agent_facts.actor.economy.movement_remaining",),
        ),
        "contacts.visible_hostile_count": (
            len(facts.contacts.visible_hostile_uuids),
            ("agent_facts.contacts.visible_hostile_uuids",),
        ),
        "contacts.remembered_hostile_count": (
            len(facts.contacts.remembered_hostile_uuids),
            ("agent_facts.contacts.remembered_hostile_uuids",),
        ),
        "contacts.visible_ally_count": (
            len(facts.contacts.visible_ally_uuids),
            ("agent_facts.contacts.visible_ally_uuids",),
        ),
        "contacts.unknown_relationship_count": (
            len(facts.contacts.visible_unknown_relationship_uuids)
            + len(facts.contacts.remembered_unknown_relationship_uuids),
            (
                "agent_facts.contacts.visible_unknown_relationship_uuids",
                "agent_facts.contacts.remembered_unknown_relationship_uuids",
            ),
        ),
        "objects.known_closed_door_count": (
            len(facts.objects.closed_door_uuids),
            ("agent_facts.objects.closed_door_uuids",),
        ),
        "topology.known_hazard_count": (
            len(facts.topology.hazardous_positions),
            ("agent_facts.topology.hazardous_positions",),
        ),
        "topology.known_slow_count": (
            len(facts.topology.slow_positions),
            ("agent_facts.topology.slow_positions",),
        ),
        "affordances.total_count": (
            len(facts.affordances.rows),
            ("agent_facts.affordances.rows",),
        ),
        "affordances.affordable_count": (
            sum(1 for row in facts.affordances.rows if row.can_afford),
            ("agent_facts.affordances.rows.can_afford",),
        ),
        "memory.effect_block_hypothesis_count": (
            len(facts.combat_memory.hypotheses),
            ("agent_facts.combat_memory.hypotheses",),
        ),
        "encounter.is_terminal": (
            world.encounter.state == "ended" if world.encounter is not None else None,
            ("subjective_world_state.encounter.state",),
        ),
    }
    if fact_id in fixed:
        return fixed[fact_id]
    tag_prefix = "affordances.tag_count."
    if fact_id.startswith(tag_prefix):
        tag = ActionTag(fact_id.removeprefix(tag_prefix))
        return (
            len(facts.affordances.row_ids_by_tag.get(tag, ())),
            (f"agent_facts.affordances.row_ids_by_tag.{tag.value}",),
        )
    raise KeyError(f"No built-in evaluator for {fact_id}")


def _validate_fact_value(definition: DerivedFactDefinition, value: FactValue) -> None:
    """Validate an evaluator value against its declared logical type."""
    if value is None:
        return
    valid = {
        FactValueType.BOOLEAN: isinstance(value, bool),
        FactValueType.INTEGER: isinstance(value, int) and not isinstance(value, bool),
        FactValueType.FLOAT: isinstance(value, float),
        FactValueType.STRING: isinstance(value, str),
    }[definition.value_type]
    if not valid:
        raise TypeError(
            f"{definition.fact_id} produced {type(value).__name__}, expected {definition.value_type.value}"
        )


def _truth_for_fact_value(value: FactValue) -> TruthValue:
    """Map a typed fact value to its three-valued observation truth."""
    if value is None:
        return TruthValue.UNKNOWN
    if isinstance(value, bool):
        return TruthValue.TRUE if value else TruthValue.FALSE
    return TruthValue.TRUE


def _evaluate_predicate_definition(
    definition: PredicateDefinition,
    world: SubjectiveWorldState,
    known_values: Mapping[str, FactValue],
    observations: Mapping[str, DerivedFactObservation],
    previous: Optional[PredicateEvaluation],
) -> PredicateEvaluation:
    """Evaluate one declarative predicate against aligned local fact values."""
    started = time.perf_counter()
    referenced = tuple(sorted(_referenced_fact_ids(definition.expression)))
    truth = evaluate_fact_expression(definition.expression, known_values)
    evidence_refs = tuple(sorted({
        evidence_ref
        for fact_id in referenced
        for evidence_ref in observations[fact_id].evidence_refs
    }))
    changed_input = any(observations[fact_id].changed for fact_id in referenced)
    changed = previous is not None and (previous.truth is not truth or changed_input)
    return PredicateEvaluation(
        predicate_id=definition.predicate_id,
        observation_cursor=world.observation_cursor,
        epoch_id=world.current_epoch.epoch_id if world.current_epoch is not None else None,
        truth=truth,
        referenced_fact_ids=referenced,
        evidence_refs=evidence_refs,
        changed=changed,
        previous_truth=previous.truth if previous is not None else None,
        elapsed_ms=(time.perf_counter() - started) * 1000.0,
    )


def _expression_shape(expression: FactExpression) -> tuple[int, int]:
    """Return recursive depth and node count for one expression tree."""
    if not expression.operands:
        return 1, 1
    child_shapes = tuple(_expression_shape(operand) for operand in expression.operands)
    return 1 + max(depth for depth, _ in child_shapes), 1 + sum(nodes for _, nodes in child_shapes)


def _referenced_fact_ids(expression: FactExpression) -> set[str]:
    """Collect every fact identity referenced by an expression tree."""
    referenced: set[str] = set()
    if expression.operator is FactOperator.PREDICATE and expression.predicate is not None:
        referenced.add(expression.predicate.fact_id)
        if expression.predicate.expected_fact_id is not None:
            referenced.add(expression.predicate.expected_fact_id)
    for operand in expression.operands:
        referenced.update(_referenced_fact_ids(operand))
    return referenced


def _focus_profile_ids(profile: PredicateFocusProfile) -> set[str]:
    """Return every predicate identity mentioned by one focus profile."""
    return set().union(
        profile.always_include,
        profile.include_when_true,
        profile.include_when_false,
        profile.include_when_unknown,
        profile.include_when_changed,
        profile.query_only,
    )


def _tag_fact_id(tag: ActionTag) -> str:
    """Return the built-in count-fact identity for one action tag."""
    return f"affordances.tag_count.{tag.value}"
