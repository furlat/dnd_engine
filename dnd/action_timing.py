"""Optional low-level timing hooks for action execution."""

from __future__ import annotations

import time
from contextvars import ContextVar, Token
from typing import Callable, Optional


ActionTimingRecorder = Callable[[str, float], None]

_action_timing_recorder: ContextVar[Optional[ActionTimingRecorder]] = ContextVar(
    "action_timing_recorder",
    default=None,
)


def set_action_timing_recorder(recorder: Optional[ActionTimingRecorder]) -> Token[Optional[ActionTimingRecorder]]:
    """Install an action timing recorder for the current context."""
    return _action_timing_recorder.set(recorder)


def reset_action_timing_recorder(token: Token[Optional[ActionTimingRecorder]]) -> None:
    """Restore the previous action timing recorder."""
    _action_timing_recorder.reset(token)


def record_action_timing(phase: str, started_at: float) -> None:
    """Record one elapsed action phase when a recorder is active."""
    recorder = _action_timing_recorder.get()
    if recorder is not None:
        recorder(phase, started_at)


def record_action_elapsed(phase: str, elapsed_seconds: float) -> None:
    """Record an already-accumulated elapsed action phase."""
    recorder = _action_timing_recorder.get()
    if recorder is not None:
        recorder(phase, time.perf_counter() - elapsed_seconds)


def action_timing_enabled() -> bool:
    """Return whether the current context has an action timing recorder."""
    return _action_timing_recorder.get() is not None
