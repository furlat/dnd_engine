"""Stable human- and machine-readable explanations of option proofs."""

from __future__ import annotations

from ai.planning.contracts import OptionContract


def explain_option(option: OptionContract) -> tuple[str, ...]:
    """Render a concise deterministic explanation of one composed option."""
    lines = [
        f"option:{option.option_id}",
        f"consistent:{str(option.consistent).lower()}",
        f"requires_observation:{str(option.requires_observation).lower()}",
    ]
    for prerequisite in option.proof.prerequisites:
        lines.append(
            "precondition:"
            f"{prerequisite.step_id}:"
            f"{prerequisite.kind.value}:"
            f"{prerequisite.truth.value}:"
            f"{','.join(prerequisite.referenced_fact_ids) or 'none'}"
        )
    for resource in option.proof.resources:
        lines.append(
            "resource:"
            f"{resource.resource_id}:"
            f"minimum={resource.minimum_initial_amount}:"
            f"delta={resource.final_delta}"
        )
    for barrier in option.proof.observation_barriers:
        lines.append(
            f"observation_barrier:{barrier.after_step_id}:{','.join(barrier.reasons)}"
        )
    for conflict in option.proof.conflicts:
        lines.append(f"conflict:{conflict.step_id}:{conflict.detail}")
    return tuple(lines)

