"""Dependency-neutral policy interfaces and identities.

Policies own decision logic only.  Projection, timing, validation, execution,
feedback reduction, and lifecycle supervision are responsibilities of the
native AI runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field


StateT_contra = TypeVar("StateT_contra", contravariant=True)
MemoryT_contra = TypeVar("MemoryT_contra", contravariant=True)
DecisionT_co = TypeVar("DecisionT_co", covariant=True)


class PolicyDescriptor(BaseModel):
    """Stable serializable identity for one policy implementation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(
        min_length=1,
        pattern=r"^[a-z][a-z0-9_.-]*$",
        description="Stable registry key, such as ``builtin.basic``.",
    )
    version: str = Field(
        min_length=1,
        description="Behavior version recorded in diagnostics and replay metadata.",
    )
    display_name: str = Field(min_length=1, description="Human-readable policy name.")
    description: str = Field(default="", description="Concise policy behavior summary.")
    deterministic: bool = Field(
        default=True,
        description="Whether identical state, memory, and seed inputs produce the same decision.",
    )


class Policy(
    Protocol[StateT_contra, MemoryT_contra, DecisionT_co],
):
    """Pure decision surface implemented by native and custom policies."""

    @property
    def descriptor(self) -> PolicyDescriptor:
        """Return the stable identity of this policy implementation."""
        ...

    def decide(
        self,
        state: StateT_contra,
        memory: MemoryT_contra,
    ) -> DecisionT_co:
        """Choose one decision without performing engine or transport work."""
        ...


@dataclass(frozen=True, slots=True)
class StatelessPolicyMemory:
    """Explicit per-assignment memory for policies that retain no state."""

