"""Causal behavior identity active while rules code emits child facts."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Optional

from dnd.types.behaviors import validate_behavior_id


@dataclass(frozen=True, slots=True)
class ActiveBehavior:
    """Direct semantic ownership inherited by child events and behaviors."""

    behavior_id: str
    provided_by_id: str
    origin_root_id: Optional[str]

    def __post_init__(self) -> None:
        validate_behavior_id(self.behavior_id)
        validate_behavior_id(self.provided_by_id, "provided_by_id")
        if self.origin_root_id is not None:
            validate_behavior_id(self.origin_root_id, "origin_root_id")


_ACTIVE_BEHAVIOR: ContextVar[ActiveBehavior | None] = ContextVar(
    "dnd_active_behavior",
    default=None,
)


@contextmanager
def behavior_scope(
    *,
    behavior_id: str,
    provided_by_id: str,
    origin_root_id: Optional[str],
) -> Iterator[None]:
    """Expose direct causal identity while one behavior executes."""
    token = _ACTIVE_BEHAVIOR.set(ActiveBehavior(
        behavior_id=behavior_id,
        provided_by_id=provided_by_id,
        origin_root_id=origin_root_id,
    ))
    try:
        yield
    finally:
        _ACTIVE_BEHAVIOR.reset(token)


def active_behavior() -> ActiveBehavior | None:
    """Return the direct behavior identity active in this causal scope."""
    return _ACTIVE_BEHAVIOR.get()


__all__ = ["ActiveBehavior", "active_behavior", "behavior_scope"]
