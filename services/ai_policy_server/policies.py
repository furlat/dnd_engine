"""Provider-owned policy identities backed by reusable decision logic."""

from __future__ import annotations

from custom_ai.tactical import (
    TacticalPolicy,
    TacticalPolicyMemory,
    reduce_tactical_feedback,
    reduce_tactical_state,
)
from dnd.ai.contracts.decision import PolicyIntent
from dnd.ai.contracts.observation import SubjectiveWorldState
from dnd.ai.policies.basic import (
    BasicPolicyMemory,
    CanonicalBasicPolicy,
    CanonicalPolicyRegistry,
    create_basic_policy,
    reduce_basic_feedback,
    reduce_basic_state,
)
from dnd.ai.policy import PolicyDescriptor


EXTERNAL_BASIC_POLICY_ID = "external.basic"
EXTERNAL_BASIC_POLICY_DESCRIPTOR = PolicyDescriptor(
    policy_id=EXTERNAL_BASIC_POLICY_ID,
    version="2",
    display_name="External Basic",
    description=(
        "Reference-provider execution of the deterministic bounded basic "
        "decision policy."
    ),
)

EXTERNAL_TACTICAL_POLICY_ID = "external.tactical"
EXTERNAL_TACTICAL_POLICY_DESCRIPTOR = PolicyDescriptor(
    policy_id=EXTERNAL_TACTICAL_POLICY_ID,
    version="1",
    display_name="External Tactical",
    description=(
        "Reference-provider execution of the stateful deterministic "
        "focus-fire policy."
    ),
)


class ExternalBasicPolicy:
    """Provider identity over the reusable logic-only basic policy."""

    descriptor = EXTERNAL_BASIC_POLICY_DESCRIPTOR

    def __init__(self) -> None:
        self._policy: CanonicalBasicPolicy = create_basic_policy()

    def decide(
        self,
        state: SubjectiveWorldState,
        memory: BasicPolicyMemory,
    ) -> PolicyIntent:
        return self._policy.decide(state, memory)


class ExternalTacticalPolicy:
    """Provider identity over the reusable logic-only tactical policy."""

    descriptor = EXTERNAL_TACTICAL_POLICY_DESCRIPTOR

    def __init__(self) -> None:
        self._policy = TacticalPolicy()

    def decide(
        self,
        state: SubjectiveWorldState,
        memory: TacticalPolicyMemory,
    ) -> PolicyIntent:
        return self._policy.decide(state, memory)


def register_external_basic_policy(
    registry: CanonicalPolicyRegistry,
) -> None:
    """Register provider-owned basic identity with fresh assignment memory."""
    registry.register(
        descriptor=EXTERNAL_BASIC_POLICY_DESCRIPTOR,
        policy_factory=ExternalBasicPolicy,
        memory_factory=BasicPolicyMemory,
        reduce_state=reduce_basic_state,
        reduce_feedback=reduce_basic_feedback,
    )


def register_external_tactical_policy(
    registry: CanonicalPolicyRegistry,
) -> None:
    """Register provider-owned tactical identity with fresh assignment memory."""
    registry.register(
        descriptor=EXTERNAL_TACTICAL_POLICY_DESCRIPTOR,
        policy_factory=ExternalTacticalPolicy,
        memory_factory=TacticalPolicyMemory,
        reduce_state=reduce_tactical_state,
        reduce_feedback=reduce_tactical_feedback,
    )


__all__ = [
    "EXTERNAL_BASIC_POLICY_DESCRIPTOR",
    "EXTERNAL_BASIC_POLICY_ID",
    "EXTERNAL_TACTICAL_POLICY_DESCRIPTOR",
    "EXTERNAL_TACTICAL_POLICY_ID",
    "ExternalBasicPolicy",
    "ExternalTacticalPolicy",
    "register_external_basic_policy",
    "register_external_tactical_policy",
]
