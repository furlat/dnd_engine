"""Encounter, turn, and controller lifecycle vocabulary."""

from enum import Enum, StrEnum


class EncounterState(str, Enum):
    """Current state of an encounter."""

    NOT_STARTED = "not_started"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class TurnState(str, Enum):
    """Current state of a turn."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    ENDED = "ended"


class ControllerExecutionMode(str, Enum):
    """Whether the encounter executes decisions or waits for external input."""

    AUTONOMOUS = "autonomous"
    EXTERNAL = "external"


class AdvanceStatus(StrEnum):
    """Closed result of advancing one encounter controller boundary."""

    ERROR = "error"
    ENCOUNTER_ENDED = "encounter_ended"
    ADVANCED_AUTONOMOUS = "advanced_autonomous"
    AUTONOMOUS_ACTION_COMPLETED = "autonomous_action_completed"
    WAITING_FOR_EXTERNAL = "waiting_for_external"
    WAITING_FOR_HUMAN = "waiting_for_human"


__all__ = [
    "AdvanceStatus",
    "ControllerExecutionMode",
    "EncounterState",
    "TurnState",
]
