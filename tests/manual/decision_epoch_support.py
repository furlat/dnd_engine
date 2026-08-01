"""Test-only projections over the canonical decision-epoch builder."""

from dnd.ai.contracts.control import AffordanceSet
from dnd.ai.runtime.decision_epoch import (
    _build_affordance_set_and_execution_authority_from_actions,
)
from dnd.core.base_actions import AvailableActionsResult
from dnd.entity import Entity


def build_affordance_set_from_actions(
    actor: Entity,
    actions: AvailableActionsResult,
    observation_cursor: int,
) -> AffordanceSet:
    """Return only public rows for tests that do not execute a selection."""
    affordances, _execution_authority = (
        _build_affordance_set_and_execution_authority_from_actions(
            actor,
            actions,
            observation_cursor,
        )
    )
    return affordances
