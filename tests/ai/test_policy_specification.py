"""Focused contract tests for dependency-neutral native policy primitives."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dnd.ai.contracts.semantics import ActionTag
from dnd.ai.policies.basic import BASIC_POLICY_SPEC
from dnd.ai.policy import PolicyDescriptor
from dnd.ai.specification import (
    PolicyCandidate,
    PolicyMetric,
    PolicyMetricThreshold,
    PolicyMetricValue,
    PolicyRuleSpec,
    PolicySpec,
)


def test_policy_descriptor_and_specification_are_frozen_and_round_trip() -> None:
    encoded = BASIC_POLICY_SPEC.model_dump_json()
    restored = PolicySpec.model_validate_json(encoded)

    assert restored == BASIC_POLICY_SPEC
    assert restored.specification_sha256 == BASIC_POLICY_SPEC.specification_sha256
    with pytest.raises(ValidationError):
        restored.descriptor.policy_id = "changed"  # type: ignore[misc]


def test_policy_specification_rejects_duplicate_rule_ids() -> None:
    descriptor = PolicyDescriptor(
        policy_id="test.duplicate",
        version="1",
        display_name="Duplicate",
    )
    rule = PolicyRuleSpec(rule_id="same")

    with pytest.raises(ValidationError, match="duplicate rule ids"):
        PolicySpec(descriptor=descriptor, rules=(rule, rule))


def test_policy_candidate_rejects_duplicate_metrics() -> None:
    urgency = PolicyMetricValue(metric=PolicyMetric.URGENCY, value=1.0)

    with pytest.raises(ValueError, match="duplicate metrics"):
        PolicyCandidate(
            candidate_id="candidate",
            decision="decision",
            semantic_tags=frozenset({ActionTag.SUPPORT_HEAL}),
            metrics=(urgency, urgency),
        )


def test_policy_metric_threshold_requires_a_coherent_bound() -> None:
    with pytest.raises(ValidationError, match="at least one bound"):
        PolicyMetricThreshold(metric=PolicyMetric.RISK)
    with pytest.raises(ValidationError, match="minimum exceeds maximum"):
        PolicyMetricThreshold(
            metric=PolicyMetric.RISK,
            minimum=2.0,
            maximum=1.0,
        )

