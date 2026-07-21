"""Executable and authenticated policy-generation definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict, Field

from ai.policy.candidates import PolicyCandidateSet
from ai.policy.contracts import PolicyContext
from ai.policy.default import DefaultPolicyEvaluation
from ai.policy.memory import RoutineProgress
from ai.policy.routines import (
    RoutinePlan,
    RoutinePlanningInstrumentation,
    RoutineRevalidation,
)


CandidateBuilder = Callable[[PolicyContext], PolicyCandidateSet]
RoutinePlanner = Callable[
    [
        PolicyContext,
        Optional[RoutineProgress],
        RoutineRevalidation,
        Optional[PolicyCandidateSet],
        Optional[RoutinePlanningInstrumentation],
    ],
    tuple[RoutinePlan, ...],
]
PolicyEvaluator = Callable[
    [PolicyContext, tuple[RoutinePlan, ...], Optional[PolicyCandidateSet]],
    DefaultPolicyEvaluation,
]


class PolicyGenerationRole(str, Enum):
    """Lifecycle role of an executable policy generation."""

    BASELINE = "baseline"
    CANDIDATE = "candidate"


class PolicyGenerationIdentity(BaseModel):
    """Serializable identity of one executable policy implementation."""

    model_config = ConfigDict(frozen=True)

    generation_id: str = Field(description="Stable generation identifier used in schedules and traces.")
    policy_name: str = Field(description="Stable policy-family identifier.")
    policy_version: str = Field(description="Human-readable behavior version.")
    role: PolicyGenerationRole = Field(description="Baseline or candidate role in a promotion experiment.")
    implementation_path: str = Field(description="Repository-relative executable generation module.")
    implementation_paths: tuple[str, ...] = Field(
        description="Complete ordered source manifest that defines this generation's behavior."
    )
    implementation_sha256: str = Field(description="SHA-256 of the exact generation module source.")
    shared_substrate_sha256: str = Field(
        description="SHA-256 of the shared subjective facts, routines, semantics, and host substrate."
    )
    executable_sha256: str = Field(
        description="SHA-256 binding the generation implementation to its shared substrate."
    )
    observation_schema_version: int = Field(default=1, ge=1, description="Required subjective observation schema.")
    affordance_schema_version: int = Field(default=1, ge=1, description="Required decision-epoch schema.")


@dataclass(frozen=True)
class PolicyImplementation:
    """All behavior-selecting callables for one immutable policy generation.

    Transport, subjective projection, command validation, and engine execution
    remain shared. Candidate construction, bounded routine planning, and tree
    evaluation are explicit generation-owned seams so a baseline does not turn
    into the candidate merely because its identity string differs.
    """

    identity: PolicyGenerationIdentity
    build_candidates: CandidateBuilder
    plan_routines: RoutinePlanner
    evaluate: PolicyEvaluator


def build_generation_identity(
    *,
    generation_id: str,
    policy_name: str,
    policy_version: str,
    role: PolicyGenerationRole,
    implementation_path: Path,
    implementation_paths: tuple[Path, ...] | None = None,
    repository_root: Path,
    shared_substrate_sha256: str,
) -> PolicyGenerationIdentity:
    """Authenticate one executable generation module and shared substrate."""
    resolved = implementation_path.resolve()
    root = repository_root.resolve()
    source_paths = implementation_paths or (implementation_path,)
    resolved_paths = tuple(path.resolve() for path in source_paths)
    relative_paths = tuple(path.relative_to(root).as_posix() for path in resolved_paths)
    relative_path = resolved.relative_to(root).as_posix()
    manifest = b"".join(
        relative.encode("utf-8") + b"\0" + path.read_bytes() + b"\0"
        for relative, path in zip(relative_paths, resolved_paths, strict=True)
    )
    implementation_sha256 = sha256(manifest).hexdigest()
    executable_sha256 = sha256(
        f"{generation_id}\0{implementation_sha256}\0{shared_substrate_sha256}".encode("utf-8")
    ).hexdigest()
    return PolicyGenerationIdentity(
        generation_id=generation_id,
        policy_name=policy_name,
        policy_version=policy_version,
        role=role,
        implementation_path=relative_path,
        implementation_paths=relative_paths,
        implementation_sha256=implementation_sha256,
        shared_substrate_sha256=shared_substrate_sha256,
        executable_sha256=executable_sha256,
    )
