"""Stable semantic registry for engine action families."""

from ai.semantics.actions import (
    action_semantics_for_available_action,
    end_turn_action_semantics,
)

__all__ = [
    "action_semantics_for_available_action",
    "end_turn_action_semantics",
]
