"""Authenticated identity for the active advanced policy."""

from __future__ import annotations

from pathlib import Path

from ai.policy.default import evaluate_default_policy
from ai.policy.definitions import (
    PolicyImplementation,
    build_generation_identity,
)
from ai.policy.generations.current_candidate import (
    build_current_candidate_set,
    plan_current_routines,
)
from ai.policy.source import POLICY_NAME, POLICY_VERSION, REPOSITORY_ROOT, policy_source_snapshot


ACTIVE_GENERATION_ID = "policy.advanced.v32"
_ACTIVE_BEHAVIOR_PATHS = tuple(
    REPOSITORY_ROOT / path
    for path in (
        "ai/policy/generations/current_candidate.py",
        "ai/policy/generations/current_commitments.py",
        "ai/policy/generations/current_annotations.py",
        "ai/policy/generations/current_options.py",
        "ai/planning/contracts.py",
        "ai/planning/composition.py",
        "ai/planning/registry.py",
        "ai/policy/generations/current_scoring.py",
        "ai/policy/default.py",
        "ai/policy/candidates.py",
        "ai/policy/economy.py",
        "ai/policy/outcomes.py",
        "ai/policy/routines.py",
        "ai/policy/tree.py",
        "ai/policy/utility.py",
    )
)
def _build_active_implementation() -> PolicyImplementation:
    substrate_hash = policy_source_snapshot().source_sha256
    identity = build_generation_identity(
        generation_id=ACTIVE_GENERATION_ID,
        policy_name=POLICY_NAME,
        policy_version=POLICY_VERSION,
        implementation_path=Path(__file__).with_name("current_candidate.py"),
        implementation_paths=_ACTIVE_BEHAVIOR_PATHS,
        repository_root=REPOSITORY_ROOT,
        shared_substrate_sha256=substrate_hash,
    )
    return PolicyImplementation(
        identity=identity,
        build_candidates=build_current_candidate_set,
        plan_routines=plan_current_routines,
        evaluate=evaluate_default_policy,
    )


ACTIVE_POLICY_IMPLEMENTATION = _build_active_implementation()


def get_active_policy_implementation() -> PolicyImplementation:
    """Return the sole advanced policy implementation used by the runtime."""
    return ACTIVE_POLICY_IMPLEMENTATION
