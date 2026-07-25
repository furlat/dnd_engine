"""Inspectable source snapshot for the client-facing subjective policy stack."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from server.agent_protocol.telemetry import PolicySourceManifest


POLICY_NAME = "shared_subjective_hierarchical_policy"
POLICY_VERSION = "2026-07-18.shared-policy-v32-candidate-valuation"
CONTROLLER_PROFILE = "unified_ai_current"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
POLICY_SOURCE_RELATIVE_PATHS = (
    "dnd/ai/contracts/control.py",
    "dnd/ai/contracts/semantics.py",
    "dnd/ai/runtime/action_semantics.py",
    "dnd/ai/runtime/decision_epoch.py",
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


def policy_source() -> str:
    """Return a deterministic manifest of every decision-bearing source file."""
    sections = []
    for relative_path, source_path in zip(POLICY_SOURCE_RELATIVE_PATHS, POLICY_SOURCE_PATHS):
        source = source_path.read_text(encoding="utf-8")
        sections.append(f"### {relative_path}\n{source.rstrip()}\n")
    return "\n".join(sections)


def policy_source_snapshot() -> PolicySourceManifest:
    """Build the client-owned policy source manifest supplied to observers."""
    source = policy_source()
    return PolicySourceManifest(
        policy_name=POLICY_NAME,
        policy_version=POLICY_VERSION,
        source_path="ai/policy/host.py",
        source_paths=list(POLICY_SOURCE_RELATIVE_PATHS),
        source_sha256=sha256(source.encode("utf-8")).hexdigest(),
        line_count=len(source.splitlines()),
        source=source,
    )
