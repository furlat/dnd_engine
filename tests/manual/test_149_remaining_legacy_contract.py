"""Prone application on the owner's turn when no movement is left."""

from __future__ import annotations

from dnd.conditions import Prone
from tests.engine.test_standard_conditions import (
    configured_entity,
    reset_condition_state,
)


def test_prone_application_during_owner_turn_respects_movement() -> None:
    """Immediate stand is affordable-only: without movement, Prone stays applied.

    The affordable case (mid-turn Prone cancels into an immediate stand) is
    covered by tests/engine/test_standard_conditions.py::
    test_eb_08_009_prone_immediate_stand_on_own_turn_cancels_indexing.
    """
    reset_condition_state()
    immobile = configured_entity("Immobile actor", (2, 1), "heroes")
    immobile.on_turn_start()
    immobile.action_economy.consume("movement", 30)

    completion = immobile.add_condition(
        Prone(
            source_entity_uuid=immobile.uuid,
            target_entity_uuid=immobile.uuid,
        )
    )

    assert completion is not None
    assert completion.canceled is False
    assert "Prone" in immobile.active_conditions
    assert immobile.action_economy.movement_remaining() == 0
