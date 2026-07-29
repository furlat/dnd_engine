"""Typed data-driven policy ranking primitives.

The candidate boundary is deliberately not an action or world DTO.  Runtime
adapters derive candidates from the canonical subjective state and legal
affordances while retaining the authoritative decision object unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Callable, Generic, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.ai.contracts.semantics import ActionTag
from dnd.ai.policy import PolicyDescriptor


StateT = TypeVar("StateT")
MemoryT = TypeVar("MemoryT")
DecisionT = TypeVar("DecisionT")


class PolicyMetric(str, Enum):
    """Small stable vocabulary understood by data-driven policy rules."""

    URGENCY = "urgency"
    EXPECTED_DAMAGE = "expected_damage"
    EXPECTED_HEALING = "expected_healing"
    CONTROL_VALUE = "control_value"
    DEFENSE_VALUE = "defense_value"
    PROGRESS = "progress"
    INFORMATION_VALUE = "information_value"
    RESOURCE_COST = "resource_cost"
    RISK = "risk"


class PolicyMetricValue(BaseModel):
    """One finite derived value attached to a policy candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    metric: PolicyMetric
    value: float


@dataclass(frozen=True, slots=True)
class PolicyCandidate(Generic[DecisionT]):
    """Policy-only view retaining an opaque canonical decision."""

    candidate_id: str
    decision: DecisionT
    semantic_tags: frozenset[ActionTag]
    metrics: tuple[PolicyMetricValue, ...] = ()
    replay_key: tuple[str, ...] = ()
    affordable: bool = True

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("policy candidate_id must not be empty")
        object.__setattr__(self, "semantic_tags", frozenset(self.semantic_tags))
        object.__setattr__(self, "metrics", tuple(self.metrics))
        object.__setattr__(self, "replay_key", tuple(self.replay_key))
        metric_names = tuple(value.metric for value in self.metrics)
        if len(metric_names) != len(set(metric_names)):
            raise ValueError(
                f"policy candidate {self.candidate_id!r} has duplicate metrics"
            )
        if any(not math.isfinite(value.value) for value in self.metrics):
            raise ValueError(
                f"policy candidate {self.candidate_id!r} has a non-finite metric"
            )

    def metric_value(self, metric: PolicyMetric) -> float:
        """Return one derived value, treating an absent metric as neutral zero."""
        return next(
            (value.value for value in self.metrics if value.metric is metric),
            0.0,
        )


class PolicyMetricThreshold(BaseModel):
    """Inclusive candidate filter over one derived metric."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    metric: PolicyMetric
    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> "PolicyMetricThreshold":
        if self.minimum is None and self.maximum is None:
            raise ValueError("a policy metric threshold requires at least one bound")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("policy metric threshold minimum exceeds maximum")
        return self


class PolicyScoreTerm(BaseModel):
    """Weighted contribution to a rule-local candidate score."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    metric: PolicyMetric
    weight: float


class PolicyRuleSpec(BaseModel):
    """One ordered, inspectable candidate selection rule."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    rule_id: str = Field(
        min_length=1,
        pattern=r"^[a-z][a-z0-9_.-]*$",
    )
    required_tags: tuple[ActionTag, ...] = ()
    any_tags: tuple[ActionTag, ...] = ()
    forbidden_tags: tuple[ActionTag, ...] = ()
    thresholds: tuple[PolicyMetricThreshold, ...] = ()
    score_terms: tuple[PolicyScoreTerm, ...] = ()
    base_score: float = 0.0
    requires_affordable: bool = True

    @model_validator(mode="after")
    def validate_unique_contract(self) -> "PolicyRuleSpec":
        for name, values in (
            ("required_tags", self.required_tags),
            ("any_tags", self.any_tags),
            ("forbidden_tags", self.forbidden_tags),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name} contains duplicate action tags")
        threshold_metrics = tuple(value.metric for value in self.thresholds)
        if len(threshold_metrics) != len(set(threshold_metrics)):
            raise ValueError("thresholds contains duplicate policy metrics")
        score_metrics = tuple(value.metric for value in self.score_terms)
        if len(score_metrics) != len(set(score_metrics)):
            raise ValueError("score_terms contains duplicate policy metrics")
        if set(self.required_tags) & set(self.forbidden_tags):
            raise ValueError("a required action tag cannot also be forbidden")
        return self

    def matches(self, candidate: PolicyCandidate[DecisionT]) -> bool:
        """Return whether one candidate satisfies this rule."""
        if self.requires_affordable and not candidate.affordable:
            return False
        tags = candidate.semantic_tags
        if not set(self.required_tags).issubset(tags):
            return False
        if self.any_tags and not set(self.any_tags).intersection(tags):
            return False
        if set(self.forbidden_tags).intersection(tags):
            return False
        for threshold in self.thresholds:
            value = candidate.metric_value(threshold.metric)
            if threshold.minimum is not None and value < threshold.minimum:
                return False
            if threshold.maximum is not None and value > threshold.maximum:
                return False
        return True

    def score(self, candidate: PolicyCandidate[DecisionT]) -> float:
        """Compute this rule's finite score for one matching candidate."""
        score = self.base_score + sum(
            candidate.metric_value(term.metric) * term.weight
            for term in self.score_terms
        )
        if not math.isfinite(score):
            raise ValueError(f"policy rule {self.rule_id!r} produced a non-finite score")
        return score


class PolicySpec(BaseModel):
    """Serializable ordered policy program."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    descriptor: PolicyDescriptor
    rules: tuple[PolicyRuleSpec, ...]

    @model_validator(mode="after")
    def validate_rules(self) -> "PolicySpec":
        if not self.rules:
            raise ValueError("a policy specification requires at least one rule")
        rule_ids = tuple(rule.rule_id for rule in self.rules)
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("policy specification contains duplicate rule ids")
        return self

    @property
    def specification_sha256(self) -> str:
        """Return a canonical hash suitable for replay and diagnostics metadata."""
        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(payload.encode("utf-8")).hexdigest()


class DataDrivenPolicy(Generic[StateT, MemoryT, DecisionT]):
    """Deterministic ordered-rule policy over runtime-derived candidates."""

    def __init__(
        self,
        *,
        specification: PolicySpec,
        candidate_provider: Callable[
            [StateT, MemoryT],
            Sequence[PolicyCandidate[DecisionT]],
        ],
        end_turn_factory: Callable[[StateT], DecisionT],
    ) -> None:
        self._specification = specification
        self._candidate_provider = candidate_provider
        self._end_turn_factory = end_turn_factory

    @property
    def descriptor(self) -> PolicyDescriptor:
        return self._specification.descriptor

    @property
    def specification(self) -> PolicySpec:
        return self._specification

    def decide(self, state: StateT, memory: MemoryT) -> DecisionT:
        """Select the first rule's best candidate or explicitly end the turn."""
        candidates = tuple(self._candidate_provider(state, memory))
        candidate_ids = tuple(candidate.candidate_id for candidate in candidates)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate provider returned duplicate candidate ids")
        for rule in self._specification.rules:
            matching = tuple(
                candidate
                for candidate in candidates
                if rule.matches(candidate)
            )
            if not matching:
                continue
            scores = {
                candidate.candidate_id: rule.score(candidate)
                for candidate in matching
            }
            best_score = max(scores.values())
            best = min(
                (
                    candidate
                    for candidate in matching
                    if scores[candidate.candidate_id] == best_score
                ),
                key=lambda candidate: (
                    candidate.replay_key or (candidate.candidate_id,),
                    candidate.candidate_id,
                ),
            )
            return best.decision
        return self._end_turn_factory(state)
