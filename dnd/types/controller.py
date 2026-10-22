"""Passive execution modes shared by controller assignments and native facts."""

from enum import Enum


class ControllerExecutionMode(str, Enum):
    """Whether the encounter executes decisions or waits for external input."""

    AUTONOMOUS = 'autonomous'
    DEFERRED_AUTONOMOUS = 'deferred_autonomous'
    EXTERNAL = 'external'
