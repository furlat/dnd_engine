"""Inspectable source snapshot for the shared subjective policy stack."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, Field


POLICY_NAME = "shared_subjective_hierarchical_policy"
POLICY_VERSION = "2026-07-18.shared-policy-v32-candidate-valuation"
CONTROLLER_PROFILE = "unified_ai_current"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
POLICY_SOURCE_RELATIVE_PATHS = (
    "ai/protocol/control.py",
    "ai/protocol/semantics.py",
    "ai/semantics/actions.py",
    "ai/subjective/epochs.py",
    "ai/knowledge/deriver.py",
    "ai/knowledge/models.py",
    "ai/knowledge/topology.py",
    "ai/policy/candidates.py",
    "ai/policy/commands.py",
    "ai/policy/contracts.py",
    "ai/policy/default.py",
    "ai/policy/economy.py",
    "ai/policy/host.py",
    "ai/policy/memory.py",
    "ai/policy/outcomes.py",
    "ai/knowledge/replay.py",
    "ai/policy/routines.py",
    "ai/policy/tree.py",
    "ai/policy/utility.py",
    "ai/policy/generations/current_candidate.py",
    "ai/policy/generations/current_scoring.py",
)
POLICY_SOURCE_PATHS = tuple(REPOSITORY_ROOT / path for path in POLICY_SOURCE_RELATIVE_PATHS)


class PolicySourceSnapshot(BaseModel):
    """Versioned source manifest for the shared traditional and LLM policy."""

    policy_name: str = Field(description="Stable policy identifier.")
    policy_version: str = Field(description="Human-readable policy version label.")
    source_path: str = Field(description="Primary repository-relative policy entry point.")
    source_paths: list[str] = Field(description="Ordered repository-relative paths in the source manifest.")
    source_sha256: str = Field(description="SHA-256 hash of the exact composite source manifest.")
    line_count: int = Field(description="Number of lines in the composite source manifest.")
    source: str = Field(description="Exact composite policy source manifest.")


def policy_source() -> str:
    """Return a deterministic manifest of every decision-bearing source file."""
    sections = []
    for relative_path, source_path in zip(POLICY_SOURCE_RELATIVE_PATHS, POLICY_SOURCE_PATHS):
        source = source_path.read_text(encoding="utf-8")
        sections.append(f"### {relative_path}\n{source.rstrip()}\n")
    return "\n".join(sections)


def policy_source_snapshot() -> PolicySourceSnapshot:
    """Return a versioned, hashable snapshot for the shared policy stack."""
    source = policy_source()
    return PolicySourceSnapshot(
        policy_name=POLICY_NAME,
        policy_version=POLICY_VERSION,
        source_path="ai/policy/host.py",
        source_paths=list(POLICY_SOURCE_RELATIVE_PATHS),
        source_sha256=sha256(source.encode("utf-8")).hexdigest(),
        line_count=len(source.splitlines()),
        source=source,
    )
