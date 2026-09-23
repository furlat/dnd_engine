"""Boundary crossings trigger a wire; air and teleport arrivals do not."""

import pytest

from dnd.actions import Jump, Move
from dnd.core.events import EventQueue, EventPhase, MechanismActivationEvent
from dnd.spatial.mechanisms import materialize_finite_trap, LaneGeometry
from dnd.spatial.triggers import materialize_tripwire
from dnd.spells.conjuration import MistyStep
from dnd.types.controls import ActivationLink
from tests.engine.test_pressure_plates import game as game, actor


@pytest.mark.parametrize("kind,start,end,expected", (
    ("walk", (1, 1), (2, 1), 1), ("walk", (2, 1), (1, 1), 1),
    ("walk", (1, 2), (2, 2), 0), ("jump", (1, 1), (2, 1), 0),
    ("teleport", (1, 1), (2, 1), 0),
))
def test_only_grounded_physical_edge_crossing_fires(game, kind, start, end, expected):
    traveler = actor(game, start)
    launcher = materialize_finite_trap((7, 3), geometry=LaneGeometry(), direction=(-1, 0))
    materialize_tripwire((1, 1), (2, 1), ActivationLink(target_condition_uuid=launcher.uuid))
    traveler.update_entity_senses()
    command = {"walk": Move, "jump": Jump, "teleport": MistyStep}[kind]
    kwargs = {"prefer_safe": False} if kind == "walk" else {}
    result = command(source_entity_uuid=traveler.uuid, end_position=end, **kwargs).apply()
    assert result is not None and not result.canceled
    shots = [event for _, event in EventQueue.iter_events_since(0)
        if isinstance(event, MechanismActivationEvent) and event.mechanism_uuid == launcher.uuid
        and event.phase is EventPhase.COMPLETION and event.committed]
    assert len(shots) == expected
