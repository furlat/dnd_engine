"""Materialization store for subjective runtime state."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from server.agent_protocol.observation_replay import apply_observation_frame, materialize_snapshot
from server.agent_protocol.observation import ObservationFrame, ObservationFrameType, ObservationSnapshot, SubjectiveWorldState
from server.agent_protocol.control import CommandResult
from ai.subjective.models import AgentState
from ai.subjective.semantic_pool import SemanticContractPool


class ApplyResultKind(str, Enum):
    """Outcome of applying one subjective frame."""

    APPLIED = "applied"
    DUPLICATE = "duplicate"
    GAP = "gap"


class ApplyResult(BaseModel):
    """Result of applying one frame to the subjective store."""

    kind: ApplyResultKind = Field(description="Apply outcome.")
    world: SubjectiveWorldState = Field(description="World state after the apply attempt.")
    previous_world: Optional[SubjectiveWorldState] = Field(default=None, description="World state before an applied frame.")
    expected_cursor: Optional[int] = Field(default=None, description="Expected cursor for gap results.")
    actual_cursor: Optional[int] = Field(default=None, description="Actual cursor for gap results.")


class PendingCommandLifecycle(BaseModel):
    """Two-phase local state for one submitted controller command."""

    command_id: str = Field(description="Controller-selected command correlation id.")
    actor_uuid: Optional[str] = Field(default=None, description="Actor that submitted the command.")
    requested_epoch_id: Optional[str] = Field(
        default=None,
        description="Decision epoch authorizing the submitted command.",
    )
    row_id: Optional[str] = Field(default=None, description="Submitted legal-affordance row id.")
    ack: Optional[CommandResult] = Field(
        default=None,
        description="Compact HTTP acknowledgement when it has arrived.",
    )
    result: Optional[CommandResult] = Field(default=None, description="Authoritative streamed command result.")
    control_cursor: Optional[int] = Field(
        default=None,
        description="Cursor of the correlated replacement epoch or epoch-clear frame.",
    )

    @property
    def complete(self) -> bool:
        """Return whether both result and replacement control context arrived."""
        return self.result is not None and self.control_cursor is not None


class SubjectiveStore:
    """Local materialization store for one AI session."""

    def __init__(self) -> None:
        """Create an empty store."""
        self.world: Optional[SubjectiveWorldState] = None
        self.agent_state = AgentState()
        self.observation_frames: list[ObservationFrame] = []
        self.snapshot_observation_cursor = 0
        self.command_results: list[CommandResult] = []
        self.pending_commands: dict[str, PendingCommandLifecycle] = {}
        self.command_control_cursors: dict[str, int] = {}
        self.semantic_contracts = SemanticContractPool()

    def load_snapshot(self, snapshot: ObservationSnapshot | dict[str, Any]) -> SubjectiveWorldState:
        """Load a fresh observation snapshot.

        Args:
            snapshot: Snapshot payload from the server.

        Returns:
            Newly materialized world state.
        """
        if not isinstance(snapshot, ObservationSnapshot):
            snapshot = ObservationSnapshot.model_validate(self.semantic_contracts.prepare_snapshot(snapshot))
        else:
            prepared_epoch = self.semantic_contracts.prepare_epoch(snapshot.current_epoch)
            if prepared_epoch is not snapshot.current_epoch:
                snapshot = snapshot.model_copy(update={"current_epoch": prepared_epoch})
        self.world = materialize_snapshot(snapshot)
        self.agent_state = AgentState()
        self.observation_frames.clear()
        self.snapshot_observation_cursor = snapshot.observation_cursor
        self.command_results.clear()
        self.pending_commands.clear()
        self.command_control_cursors.clear()
        return self.world

    def register_pending_command(
        self,
        command_id: str,
        ack: Optional[CommandResult] = None,
        *,
        actor_uuid: Optional[str] = None,
        requested_epoch_id: Optional[str] = None,
        row_id: Optional[str] = None,
    ) -> None:
        """Track one command before submission and merge its later acknowledgement.

        Args:
            command_id: Controller-selected command correlation id.
            ack: Compact HTTP acknowledgement when already available.
            actor_uuid: Actor submitting the command before acknowledgement.
            requested_epoch_id: Epoch authorizing the command before acknowledgement.
            row_id: Submitted affordance row before acknowledgement.
        """
        existing = self.pending_commands.get(command_id)
        lifecycle = PendingCommandLifecycle(
            command_id=command_id,
            actor_uuid=(
                ack.actor_uuid
                if ack is not None and ack.actor_uuid is not None
                else actor_uuid or (existing.actor_uuid if existing is not None else None)
            ),
            requested_epoch_id=(
                ack.requested_epoch_id
                if ack is not None and ack.requested_epoch_id is not None
                else requested_epoch_id or (
                    existing.requested_epoch_id if existing is not None else None
                )
            ),
            row_id=(
                ack.row_id
                if ack is not None and ack.row_id is not None
                else row_id or (existing.row_id if existing is not None else None)
            ),
            ack=ack or (existing.ack if existing is not None else None),
            result=self.get_command_result(command_id),
            control_cursor=self.command_control_cursors.get(command_id),
        )
        if not lifecycle.complete:
            self.pending_commands[command_id] = lifecycle

    def discard_pending_command(self, command_id: str) -> None:
        """Forget one command whose transport failed before stream completion."""
        self.pending_commands.pop(command_id, None)

    def command_control_seen(self, command_id: str) -> bool:
        """Return whether a correlated epoch or clear frame has been applied."""
        return command_id in self.command_control_cursors

    def mark_command_control_seen(self, command_id: str, cursor: int) -> None:
        """Record a command's replacement control frame and finish it if possible."""
        self.command_control_cursors[command_id] = cursor
        lifecycle = self.pending_commands.get(command_id)
        if lifecycle is None:
            return
        lifecycle.control_cursor = cursor
        if lifecycle.complete:
            self.pending_commands.pop(command_id, None)

    def get_command_result(self, command_id: str) -> Optional[CommandResult]:
        """Return a streamed command result by id when present."""
        for result in reversed(self.command_results):
            if result.command_id == command_id:
                return result
        return None

    def apply_frame(
        self,
        frame: ObservationFrame | dict[str, Any],
        *,
        capture_previous: bool = True,
    ) -> ApplyResult:
        """Apply one observation frame idempotently.

        Args:
            frame: Observation frame from polling or SSE.
            capture_previous: Whether to deep-copy the prior world for hook
                context. Replay batches can capture once and skip later copies.

        Returns:
            Apply result including gap/duplicate status.
        """
        if self.world is None:
            raise RuntimeError("SubjectiveStore.load_snapshot() must be called before apply_frame().")
        supplied_cursor = frame.observation_cursor if isinstance(frame, ObservationFrame) else frame.get("observation_cursor")
        if type(supplied_cursor) is int:
            early_result = self._reject_noncontiguous_cursor(supplied_cursor)
            if early_result is not None:
                return early_result
        if not isinstance(frame, ObservationFrame):
            frame = ObservationFrame.model_validate(self.semantic_contracts.prepare_frame(frame))
        else:
            prepared_epoch = self.semantic_contracts.prepare_epoch(frame.decision_epoch)
            if prepared_epoch is not frame.decision_epoch:
                frame = frame.model_copy(update={"decision_epoch": prepared_epoch})

        rejected = self._reject_noncontiguous_cursor(frame.observation_cursor)
        if rejected is not None:
            return rejected

        previous = self.world if capture_previous else None
        next_world = apply_observation_frame(self.world, frame)
        if frame.command_result is not None:
            self.command_results.append(frame.command_result)
            if frame.command_result.command_id is not None:
                command_id = frame.command_result.command_id
                lifecycle = self.pending_commands.get(command_id)
                if lifecycle is not None:
                    lifecycle.result = frame.command_result
                    if lifecycle.complete:
                        self.pending_commands.pop(command_id, None)
        if (
            frame.frame_type == ObservationFrameType.DECISION_EPOCH
            and frame.source_command_id is not None
        ):
            self.mark_command_control_seen(
                frame.source_command_id,
                frame.observation_cursor,
            )
        self.world = next_world
        self.observation_frames.append(frame)
        return ApplyResult(kind=ApplyResultKind.APPLIED, world=self.world, previous_world=previous)

    def frames_after(self, observation_cursor: int) -> tuple[ObservationFrame, ...]:
        """Return retained subjective frames after one local cursor in source order."""
        return tuple(
            frame
            for frame in self.observation_frames
            if frame.observation_cursor > observation_cursor
        )

    def _reject_noncontiguous_cursor(self, cursor: int) -> Optional[ApplyResult]:
        """Return duplicate or gap state without parsing rejected frame content."""
        if self.world is None:
            raise RuntimeError("SubjectiveStore.load_snapshot() must be called before apply_frame().")
        expected = self.world.observation_cursor + 1
        if cursor <= self.world.observation_cursor:
            return ApplyResult(kind=ApplyResultKind.DUPLICATE, world=self.world)
        if cursor != expected:
            return ApplyResult(
                kind=ApplyResultKind.GAP,
                world=self.world,
                expected_cursor=expected,
                actual_cursor=cursor,
            )
        return None
