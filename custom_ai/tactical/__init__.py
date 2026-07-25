"""Registered stateful tactical policy example."""

from custom_ai.tactical.memory import (
    TacticalActorMemory,
    TacticalActorMemorySnapshot,
    TacticalPolicyMemory,
    reduce_tactical_feedback,
    reduce_tactical_state,
)
from custom_ai.tactical.policy import (
    TACTICAL_POLICY_DESCRIPTOR,
    TACTICAL_POLICY_ID,
    TacticalPolicy,
    register_tactical_policy,
)


__all__ = [
    "TACTICAL_POLICY_DESCRIPTOR",
    "TACTICAL_POLICY_ID",
    "TacticalActorMemory",
    "TacticalActorMemorySnapshot",
    "TacticalPolicy",
    "TacticalPolicyMemory",
    "reduce_tactical_feedback",
    "reduce_tactical_state",
    "register_tactical_policy",
]

