"""One authoritative dispatcher for already-discovered engine action bindings."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Callable, Optional

from dnd.action_timing import (
    reset_action_timing_recorder,
    set_action_timing_recorder,
)
from dnd.actions import MovementEvent
from dnd.actions_functional import execute_available_action
from dnd.core.action_execution import (
    MovementContinuationGuard,
    movement_continuation_scope,
)
from dnd.core.base_actions import AvailableActionInfo, AvailableTarget
from dnd.core.events import Event
from dnd.entity import Entity


ActionDispatchTimingRecorder = Callable[[str, float], None]


class ActionDispatchError(ValueError):
    """Raised when a caller presents an invalid discovered action binding."""


@dataclass(frozen=True, slots=True)
class ActionDispatchResult:
    """Engine result and movement continuation facts from one dispatch."""

    event: Optional[Event]
    movement_termination_reason: Optional[str] = None
    movement_revalidation_reason: Optional[str] = None

    @property
    def canceled(self) -> bool:
        """Return whether the authoritative event was absent or canceled."""
        return self.event is None or self.event.canceled


def dispatch_available_action(
    entity: Entity,
    *,
    action_info: AvailableActionInfo,
    target: AvailableTarget,
    extra_target_uuids: tuple[str, ...] = (),
    prefer_safe: bool = True,
    movement_guard: Optional[MovementContinuationGuard] = None,
    record_timing: Optional[ActionDispatchTimingRecorder] = None,
) -> ActionDispatchResult:
    """Execute one exact discovery row and target without rediscovery."""
    if not action_info.can_afford:
        raise ActionDispatchError("Discovered action is not affordable")
    if not any(candidate is target for candidate in action_info.valid_targets):
        raise ActionDispatchError(
            "Target is not the exact target authorized by this discovery row"
        )
    template = action_info.execution_template
    if template is not None and template.source_entity_uuid != entity.uuid:
        raise ActionDispatchError(
            "Discovered action belongs to a different actor"
        )

    continuation_scope = (
        movement_continuation_scope(movement_guard)
        if movement_guard is not None
        else nullcontext()
    )
    timing_token = (
        set_action_timing_recorder(record_timing)
        if record_timing is not None
        else None
    )
    try:
        with continuation_scope:
            event = execute_available_action(
                entity,
                action_info,
                target,
                extra_target_uuids=list(extra_target_uuids) or None,
                prefer_safe=prefer_safe,
            )
    finally:
        if timing_token is not None:
            reset_action_timing_recorder(timing_token)

    if not isinstance(event, MovementEvent):
        return ActionDispatchResult(event=event)
    return ActionDispatchResult(
        event=event,
        movement_termination_reason=event.termination_reason.value,
        movement_revalidation_reason=event.controller_revalidation_reason,
    )
