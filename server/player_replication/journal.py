"""Perspective-partitioned journal for canonical subjective replication.

This module deliberately knows nothing about engine ``Event`` subclasses,
routes, sessions, or SSE formatting.  A mapper receives an immutable projection
context and returns the canonical route-free DTO that the journal validates,
retains, and fans out.

Observation and combat-log histories have independent cursor domains.  The
source-event cursor is a causal watermark carried by observation frames; an
otherwise hidden source batch is represented by an empty frame rather than by
leaking an event payload.  A combat-log slot is always retained as a slot even
when its subjective entry is ``None``.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from threading import RLock
from typing import Deque, Optional, Protocol, TypeVar

from pydantic import ValidationError

from server.player_replication_contract import (
    PlayerReplicationProtocolIdentity,
    PlayerReplicationWatermarks,
    SubjectiveCombatLogDelivery,
    SubjectiveCombatLogFrame,
    SubjectiveCombatLogFramesResponse,
    SubjectiveFrameDelivery,
    SubjectiveFramesResponse,
    SubjectivePerspective,
    SubjectiveReplicatedWorld,
    SubjectiveReplicationBootstrap,
    SubjectiveReplicationFrame,
    SubjectiveStreamDelivery,
    SubjectiveSyncDelivery,
)


DEFAULT_OBSERVATION_RETENTION = 4096
DEFAULT_COMBAT_LOG_RETENTION = 4096
DEFAULT_SUBSCRIPTION_DEPTH = 512


class SubjectiveJournalError(RuntimeError):
    """Base error raised by the canonical player journal."""


class SubjectiveJournalIdentityError(SubjectiveJournalError):
    """A generation or perspective was used with the wrong partition."""


class SubjectiveJournalInvariantError(SubjectiveJournalError):
    """A producer attempted to commit a non-contiguous canonical value."""


class SubjectiveJournalResyncRequired(SubjectiveJournalError):
    """The requested consumed cursor is no longer retained exactly."""

    def __init__(self, *, requested_cursor: int, retained_from_cursor: int) -> None:
        self.requested_cursor = requested_cursor
        self.retained_from_cursor = retained_from_cursor
        super().__init__(
            "requested cursor "
            f"{requested_cursor} precedes retained boundary {retained_from_cursor}"
        )


class SubjectiveJournalUnhealthyError(SubjectiveJournalError):
    """Projection failed and this partition can no longer prove continuity."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"subjective replication journal is unhealthy: {reason}")


class SubjectiveProjectionError(SubjectiveJournalError):
    """An injected projection boundary failed closed."""


class SubjectiveSubscriptionClosedError(SubjectiveJournalError):
    """A subscription cannot continue without reconnecting or resynchronizing."""

    def __init__(self, reason: str, *, resync_required: bool) -> None:
        self.reason = reason
        self.resync_required = resync_required
        super().__init__(f"subjective subscription closed: {reason}")


@dataclass(frozen=True)
class SubjectiveJournalPartitionKey:
    """Complete namespace for one authority-stable player timeline."""

    source_stream_id: str
    generation_id: str
    perspective_epoch_id: str

    def __post_init__(self) -> None:
        if not self.source_stream_id:
            raise ValueError("source_stream_id must not be empty")
        if not self.generation_id:
            raise ValueError("generation_id must not be empty")
        if not self.perspective_epoch_id:
            raise ValueError("perspective_epoch_id must not be empty")


@dataclass(frozen=True)
class SubjectiveFrameProjectionContext:
    """Cursor and authority facts supplied to an event-to-frame mapper."""

    protocol: PlayerReplicationProtocolIdentity
    perspective: SubjectivePerspective
    previous_watermarks: PlayerReplicationWatermarks
    next_observation_cursor: int


@dataclass(frozen=True)
class SubjectiveCombatLogProjectionContext:
    """Cursor and authority facts supplied to a source-log projector."""

    protocol: PlayerReplicationProtocolIdentity
    perspective: SubjectivePerspective
    previous_watermarks: PlayerReplicationWatermarks
    next_combat_log_cursor: int


@dataclass(frozen=True)
class SubjectiveWorldProjectionContext:
    """Atomic captured boundary supplied to a world snapshot projector."""

    protocol: PlayerReplicationProtocolIdentity
    perspective: SubjectivePerspective
    captured_watermarks: PlayerReplicationWatermarks


FrameSourceT = TypeVar("FrameSourceT", contravariant=True)
CombatLogSourceT = TypeVar("CombatLogSourceT", contravariant=True)


class SubjectiveFrameProjector(Protocol[FrameSourceT]):
    """Injectable engine-batch to canonical observation-frame boundary."""

    def project_frame(
        self,
        source: FrameSourceT,
        context: SubjectiveFrameProjectionContext,
    ) -> SubjectiveReplicationFrame:
        """Project one already-captured source batch without mutating the journal."""
        ...


class SubjectiveCombatLogProjector(Protocol[CombatLogSourceT]):
    """Injectable objective-slot to nullable subjective-log boundary."""

    def project_combat_log(
        self,
        source: CombatLogSourceT,
        context: SubjectiveCombatLogProjectionContext,
    ) -> SubjectiveCombatLogFrame:
        """Project one exact source slot, retaining hidden slots as ``None``."""
        ...


class SubjectiveWorldProjector(Protocol):
    """Injectable current-state to renderer-complete subjective world boundary."""

    def project_world(
        self,
        context: SubjectiveWorldProjectionContext,
    ) -> SubjectiveReplicatedWorld:
        """Project the world at exactly the supplied captured watermarks."""
        ...


@dataclass(frozen=True)
class _SubscriptionTerminal:
    reason: str
    resync_required: bool


_SubscriptionItem = SubjectiveStreamDelivery | _SubscriptionTerminal


class SubjectiveSubscription:
    """Bounded queue of immutable canonical live deliveries for one subscriber."""

    def __init__(self, *, max_depth: int) -> None:
        if max_depth < 1:
            raise ValueError("max_depth must be positive")
        self._queue: asyncio.Queue[_SubscriptionItem] = asyncio.Queue(maxsize=max_depth)
        self._closed = False
        self._terminal: Optional[_SubscriptionTerminal] = None

    @property
    def closed(self) -> bool:
        """Return whether this subscriber has been terminated."""
        return self._closed

    @property
    def resync_required(self) -> bool:
        """Return whether reconnecting requires a fresh bootstrap."""
        return bool(self._terminal and self._terminal.resync_required)

    def enqueue(self, delivery: SubjectiveStreamDelivery) -> bool:
        """Queue one delivery, terminating this subscriber on overflow."""
        if self._closed:
            return False
        try:
            self._queue.put_nowait(delivery)
            return True
        except asyncio.QueueFull:
            self.close("subscriber_queue_overflow", resync_required=True)
            return False

    def close(self, reason: str, *, resync_required: bool) -> None:
        """Discard queued data and install one deterministic terminal marker."""
        if self._closed:
            return
        terminal = _SubscriptionTerminal(
            reason=reason,
            resync_required=resync_required,
        )
        self._closed = True
        self._terminal = terminal
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._queue.put_nowait(terminal)

    async def get(self) -> SubjectiveStreamDelivery:
        """Wait for one delivery or raise the terminal stream condition."""
        if self._closed and self._queue.empty() and self._terminal is not None:
            raise SubjectiveSubscriptionClosedError(
                self._terminal.reason,
                resync_required=self._terminal.resync_required,
            )
        item = await self._queue.get()
        if isinstance(item, _SubscriptionTerminal):
            raise SubjectiveSubscriptionClosedError(
                item.reason,
                resync_required=item.resync_required,
            )
        return item


@dataclass(frozen=True)
class SubjectiveSubscriptionSnapshot:
    """Atomic subscribe barrier plus exact histories captured through it."""

    subscription: SubjectiveSubscription
    sync: SubjectiveSyncDelivery
    observation_backfill: SubjectiveFramesResponse
    combat_log_backfill: SubjectiveCombatLogFramesResponse
    backfill_deliveries: tuple[
        SubjectiveFrameDelivery | SubjectiveCombatLogDelivery,
        ...,
    ]


class SubjectiveReplicationJournal:
    """One exact generation-and-perspective player replication partition."""

    def __init__(
        self,
        *,
        protocol: PlayerReplicationProtocolIdentity,
        perspective: SubjectivePerspective,
        initial_source_event_cursor: int = 0,
        observation_retention: int = DEFAULT_OBSERVATION_RETENTION,
        combat_log_retention: int = DEFAULT_COMBAT_LOG_RETENTION,
    ) -> None:
        if initial_source_event_cursor < 0:
            raise ValueError("initial_source_event_cursor must be nonnegative")
        if observation_retention < 1:
            raise ValueError("observation_retention must be positive")
        if combat_log_retention < 1:
            raise ValueError("combat_log_retention must be positive")

        self.protocol = protocol
        self.perspective = perspective
        self.partition_key = SubjectiveJournalPartitionKey(
            source_stream_id=protocol.source_stream_id,
            generation_id=protocol.generation_id,
            perspective_epoch_id=perspective.perspective_epoch_id,
        )
        self._observation_retention = observation_retention
        self._combat_log_retention = combat_log_retention
        self._frames: Deque[SubjectiveReplicationFrame] = deque()
        self._combat_log_deliveries: Deque[SubjectiveCombatLogDelivery] = deque()
        self._accepted_presentation_ids: set[str] = set()
        self._subscriptions: list[SubjectiveSubscription] = []
        self._lock = RLock()
        self._watermarks = PlayerReplicationWatermarks(
            source_event_cursor=initial_source_event_cursor,
            observation_cursor=0,
            presentation_cursor=0,
            combat_log_cursor=0,
        )
        self._retained_from_observation_cursor = 0
        self._retained_from_observation_watermarks = self._watermarks
        self._retained_from_combat_log_cursor = 0
        self._unhealthy_reason: Optional[str] = None

    @property
    def watermarks(self) -> PlayerReplicationWatermarks:
        """Return the current independent captured boundaries."""
        with self._lock:
            return self._watermarks

    @property
    def retained_from_observation_cursor(self) -> int:
        """Return the oldest consumed observation boundary still resumable."""
        with self._lock:
            return self._retained_from_observation_cursor

    @property
    def retained_from_combat_log_cursor(self) -> int:
        """Return the oldest consumed combat-log boundary still resumable."""
        with self._lock:
            return self._retained_from_combat_log_cursor

    @property
    def healthy(self) -> bool:
        """Return whether this journal can still prove exact continuity."""
        with self._lock:
            return self._unhealthy_reason is None

    @property
    def unhealthy_reason(self) -> Optional[str]:
        """Return the first terminal projection or invariant failure."""
        with self._lock:
            return self._unhealthy_reason

    def project_and_append_frame(
        self,
        source: FrameSourceT,
        projector: SubjectiveFrameProjector[FrameSourceT],
    ) -> SubjectiveReplicationFrame:
        """Project and atomically commit one source batch, failing closed."""
        with self._lock:
            self._require_healthy()
            context = SubjectiveFrameProjectionContext(
                protocol=self.protocol,
                perspective=self.perspective,
                previous_watermarks=self._watermarks,
                next_observation_cursor=self._watermarks.observation_cursor + 1,
            )
            try:
                frame = projector.project_frame(source, context)
            except Exception as exc:
                reason = f"frame projection failed: {type(exc).__name__}: {exc}"
                self._mark_unhealthy(reason)
                raise SubjectiveProjectionError(reason) from exc
            return self.append_frame(frame)

    def append_frame(
        self,
        frame: SubjectiveReplicationFrame,
    ) -> SubjectiveReplicationFrame:
        """Commit one canonical exact observation transaction."""
        with self._lock:
            return self._append_frame(frame)

    def _append_frame(
        self,
        frame: SubjectiveReplicationFrame,
    ) -> SubjectiveReplicationFrame:
        """Commit one frame while the journal mutation lock is held."""
        self._require_healthy()
        try:
            canonical = SubjectiveReplicationFrame.model_validate_json(
                frame.model_dump_json()
            )
            self._validate_frame(canonical)
        except (SubjectiveJournalError, ValidationError, ValueError) as exc:
            reason = f"invalid observation frame: {exc}"
            self._mark_unhealthy(reason)
            if isinstance(exc, SubjectiveJournalError):
                raise
            raise SubjectiveJournalInvariantError(reason) from exc

        if len(self._frames) == self._observation_retention:
            evicted = self._frames.popleft()
            self._retained_from_observation_cursor = evicted.watermarks.observation_cursor
            self._retained_from_observation_watermarks = evicted.watermarks
        self._frames.append(canonical)
        self._accepted_presentation_ids.update(
            cue.presentation_id for cue in canonical.presentation
        )
        self._watermarks = canonical.watermarks
        self._fan_out(SubjectiveFrameDelivery(frame=canonical))
        return canonical

    def project_and_append_combat_log(
        self,
        source: CombatLogSourceT,
        projector: SubjectiveCombatLogProjector[CombatLogSourceT],
    ) -> SubjectiveCombatLogFrame:
        """Project and atomically commit one exact source-log slot."""
        with self._lock:
            self._require_healthy()
            context = SubjectiveCombatLogProjectionContext(
                protocol=self.protocol,
                perspective=self.perspective,
                previous_watermarks=self._watermarks,
                next_combat_log_cursor=self._watermarks.combat_log_cursor + 1,
            )
            try:
                frame = projector.project_combat_log(source, context)
            except Exception as exc:
                reason = f"combat-log projection failed: {type(exc).__name__}: {exc}"
                self._mark_unhealthy(reason)
                raise SubjectiveProjectionError(reason) from exc
            return self.append_combat_log(frame)

    def append_combat_log(
        self,
        frame: SubjectiveCombatLogFrame,
    ) -> SubjectiveCombatLogFrame:
        """Commit one contiguous subjective slot, including hidden ``None`` slots."""
        with self._lock:
            return self._append_combat_log(frame)

    def _append_combat_log(
        self,
        frame: SubjectiveCombatLogFrame,
    ) -> SubjectiveCombatLogFrame:
        """Commit one log slot while the journal mutation lock is held."""
        self._require_healthy()
        try:
            canonical = SubjectiveCombatLogFrame.model_validate_json(
                frame.model_dump_json()
            )
            self._validate_combat_log_frame(canonical)
        except (SubjectiveJournalError, ValidationError, ValueError) as exc:
            reason = f"invalid combat-log frame: {exc}"
            self._mark_unhealthy(reason)
            if isinstance(exc, SubjectiveJournalError):
                raise
            raise SubjectiveJournalInvariantError(reason) from exc

        if len(self._combat_log_deliveries) == self._combat_log_retention:
            evicted = self._combat_log_deliveries.popleft()
            self._retained_from_combat_log_cursor = evicted.frame.combat_log_cursor
        self._watermarks = self._watermarks.model_copy(
            update={"combat_log_cursor": canonical.combat_log_cursor}
        )
        delivery = SubjectiveCombatLogDelivery(
            watermarks=self._watermarks,
            frame=canonical,
        )
        self._combat_log_deliveries.append(delivery)
        self._fan_out(delivery)
        return canonical

    def observation_window(
        self,
        *,
        from_observation_cursor: int,
        limit: Optional[int] = None,
    ) -> SubjectiveFramesResponse:
        """Return an exact retained observation window or require resync."""
        with self._lock:
            return self._observation_window(
                from_observation_cursor=from_observation_cursor,
                limit=limit,
            )

    def _observation_window(
        self,
        *,
        from_observation_cursor: int,
        limit: Optional[int] = None,
    ) -> SubjectiveFramesResponse:
        """Capture an observation window while the journal lock is held."""
        self._require_healthy()
        if from_observation_cursor < 0:
            raise ValueError("from_observation_cursor must be nonnegative")
        if limit is not None and limit < 1:
            raise ValueError("limit must be positive when supplied")
        if from_observation_cursor < self._retained_from_observation_cursor:
            raise SubjectiveJournalResyncRequired(
                requested_cursor=from_observation_cursor,
                retained_from_cursor=self._retained_from_observation_cursor,
            )
        current = self._watermarks.observation_cursor
        if from_observation_cursor > current:
            raise SubjectiveJournalInvariantError(
                f"requested observation cursor {from_observation_cursor} exceeds current {current}"
            )

        through_cursor = current
        if limit is not None:
            through_cursor = min(through_cursor, from_observation_cursor + limit)
        frames = tuple(
            frame
            for frame in self._frames
            if from_observation_cursor
            < frame.watermarks.observation_cursor
            <= through_cursor
        )
        from_watermarks = self._observation_boundary(from_observation_cursor)
        through_watermarks = frames[-1].watermarks if frames else from_watermarks
        return SubjectiveFramesResponse(
            source_stream_id=self.protocol.source_stream_id,
            generation_id=self.protocol.generation_id,
            perspective_epoch_id=self.perspective.perspective_epoch_id,
            retained_from_observation_cursor=self._retained_from_observation_cursor,
            from_watermarks=from_watermarks,
            through_watermarks=through_watermarks,
            captured_watermarks=self._watermarks,
            frames=frames,
        )

    def combat_log_window(
        self,
        *,
        from_combat_log_cursor: int,
        limit: Optional[int] = None,
    ) -> SubjectiveCombatLogFramesResponse:
        """Return an exact retained nullable combat-log window or require resync."""
        with self._lock:
            return self._combat_log_window(
                from_combat_log_cursor=from_combat_log_cursor,
                limit=limit,
            )

    def _combat_log_window(
        self,
        *,
        from_combat_log_cursor: int,
        limit: Optional[int] = None,
    ) -> SubjectiveCombatLogFramesResponse:
        """Capture a combat-log window while the journal lock is held."""
        self._require_healthy()
        if from_combat_log_cursor < 0:
            raise ValueError("from_combat_log_cursor must be nonnegative")
        if limit is not None and limit < 1:
            raise ValueError("limit must be positive when supplied")
        if from_combat_log_cursor < self._retained_from_combat_log_cursor:
            raise SubjectiveJournalResyncRequired(
                requested_cursor=from_combat_log_cursor,
                retained_from_cursor=self._retained_from_combat_log_cursor,
            )
        current = self._watermarks.combat_log_cursor
        if from_combat_log_cursor > current:
            raise SubjectiveJournalInvariantError(
                f"requested combat-log cursor {from_combat_log_cursor} exceeds current {current}"
            )
        through_cursor = current
        if limit is not None:
            through_cursor = min(through_cursor, from_combat_log_cursor + limit)
        frames = tuple(
            delivery.frame
            for delivery in self._combat_log_deliveries
            if from_combat_log_cursor
            < delivery.frame.combat_log_cursor
            <= through_cursor
        )
        return SubjectiveCombatLogFramesResponse(
            source_stream_id=self.protocol.source_stream_id,
            generation_id=self.protocol.generation_id,
            perspective_epoch_id=self.perspective.perspective_epoch_id,
            retained_from_cursor=self._retained_from_combat_log_cursor,
            from_cursor=from_combat_log_cursor,
            through_cursor=through_cursor,
            frames=frames,
            total=current,
        )

    def bootstrap(self, world: SubjectiveReplicatedWorld) -> SubjectiveReplicationBootstrap:
        """Build an atomic renderer seed plus all retained nullable log slots."""
        with self._lock:
            return self._bootstrap(world)

    def _bootstrap(
        self,
        world: SubjectiveReplicatedWorld,
    ) -> SubjectiveReplicationBootstrap:
        """Build a bootstrap while the journal lock fixes its cursor barrier."""
        self._require_healthy()
        try:
            canonical_world = SubjectiveReplicatedWorld.model_validate_json(
                world.model_dump_json()
            )
            logs = self._combat_log_window(
                from_combat_log_cursor=self._retained_from_combat_log_cursor
            )
            return SubjectiveReplicationBootstrap(
                protocol=self.protocol,
                perspective=self.perspective,
                watermarks=self._watermarks,
                world=canonical_world,
                combat_log_frames=logs,
            )
        except (ValidationError, ValueError) as exc:
            reason = f"invalid subjective bootstrap projection: {exc}"
            self._mark_unhealthy(reason)
            raise SubjectiveProjectionError(reason) from exc

    def project_bootstrap(
        self,
        projector: SubjectiveWorldProjector,
    ) -> SubjectiveReplicationBootstrap:
        """Project and validate a world snapshot at the current captured boundary."""
        with self._lock:
            self._require_healthy()
            context = SubjectiveWorldProjectionContext(
                protocol=self.protocol,
                perspective=self.perspective,
                captured_watermarks=self._watermarks,
            )
            try:
                world = projector.project_world(context)
            except Exception as exc:
                reason = f"world projection failed: {type(exc).__name__}: {exc}"
                self._mark_unhealthy(reason)
                raise SubjectiveProjectionError(reason) from exc
            return self._bootstrap(world)

    def sync_delivery(self) -> SubjectiveSyncDelivery:
        """Return the current partition identity and captured cursor boundary."""
        with self._lock:
            return self._sync_delivery()

    def _sync_delivery(self) -> SubjectiveSyncDelivery:
        """Build a sync delivery while the journal lock fixes its barrier."""
        self._require_healthy()
        return SubjectiveSyncDelivery(
            protocol=self.protocol,
            perspective=self.perspective,
            watermarks=self._watermarks,
        )

    def subscribe(
        self,
        *,
        max_depth: int = DEFAULT_SUBSCRIPTION_DEPTH,
    ) -> SubjectiveSubscription:
        """Atomically queue sync first, then register for future live deliveries."""
        with self._lock:
            self._require_healthy()
            subscription = SubjectiveSubscription(max_depth=max_depth)
            if not subscription.enqueue(self._sync_delivery()):
                raise SubjectiveSubscriptionClosedError(
                    "subscriber_queue_overflow",
                    resync_required=True,
                )
            self._subscriptions.append(subscription)
            return subscription

    def subscribe_with_backfill(
        self,
        *,
        from_observation_cursor: int,
        from_combat_log_cursor: int,
        max_depth: int = DEFAULT_SUBSCRIPTION_DEPTH,
    ) -> SubjectiveSubscriptionSnapshot:
        """Atomically fix barrier B, backfill through B, then queue live values after B."""
        with self._lock:
            self._require_healthy()
            sync = self._sync_delivery()
            observation_backfill = self._observation_window(
                from_observation_cursor=from_observation_cursor,
            )
            combat_log_backfill = self._combat_log_window(
                from_combat_log_cursor=from_combat_log_cursor,
            )
            if observation_backfill.captured_watermarks != sync.watermarks:
                raise SubjectiveJournalInvariantError(
                    "observation backfill was not captured at the subscribe barrier"
                )
            if combat_log_backfill.total != sync.watermarks.combat_log_cursor:
                raise SubjectiveJournalInvariantError(
                    "combat-log backfill was not captured at the subscribe barrier"
                )
            backfill_deliveries = self._merge_backfill_deliveries(
                observation_backfill,
                combat_log_backfill,
            )
            subscription = SubjectiveSubscription(max_depth=max_depth)
            if not subscription.enqueue(sync):
                raise SubjectiveSubscriptionClosedError(
                    "subscriber_queue_overflow",
                    resync_required=True,
                )
            self._subscriptions.append(subscription)
            return SubjectiveSubscriptionSnapshot(
                subscription=subscription,
                sync=sync,
                observation_backfill=observation_backfill,
                combat_log_backfill=combat_log_backfill,
                backfill_deliveries=backfill_deliveries,
            )

    def unsubscribe(self, subscription: SubjectiveSubscription) -> None:
        """Remove one live subscriber without affecting the journal."""
        with self._lock:
            if subscription in self._subscriptions:
                self._subscriptions.remove(subscription)
            subscription.close("subscriber_unsubscribed", resync_required=False)

    def close(self, reason: str = "journal_closed") -> None:
        """Close subscribers when a generation or authority epoch is retired."""
        with self._lock:
            self._mark_unhealthy(reason)

    def _validate_frame(self, frame: SubjectiveReplicationFrame) -> None:
        key = self.partition_key
        if (
            frame.source_stream_id != key.source_stream_id
            or frame.generation_id != key.generation_id
            or frame.perspective_epoch_id != key.perspective_epoch_id
        ):
            raise SubjectiveJournalIdentityError(
                "observation frame does not belong to this journal partition"
            )
        expected_observation_cursor = self._watermarks.observation_cursor + 1
        if frame.watermarks.observation_cursor != expected_observation_cursor:
            raise SubjectiveJournalInvariantError(
                "observation cursor must advance by exactly one"
            )
        if frame.presentation_from_cursor != self._watermarks.presentation_cursor:
            raise SubjectiveJournalInvariantError(
                "presentation window must begin at the previous presentation watermark"
            )
        if not frame.watermarks.dominates(self._watermarks):
            raise SubjectiveJournalInvariantError("frame watermarks moved backwards")
        if frame.watermarks.combat_log_cursor != self._watermarks.combat_log_cursor:
            raise SubjectiveJournalInvariantError(
                "observation frame cannot manufacture a combat-log cursor"
            )
        reused_presentation_ids = self._accepted_presentation_ids.intersection(
            cue.presentation_id for cue in frame.presentation
        )
        if reused_presentation_ids:
            reused = ", ".join(sorted(reused_presentation_ids))
            raise SubjectiveJournalInvariantError(
                "presentation IDs must be unique for the entire live journal "
                f"partition; already accepted: {reused}"
            )

    def _validate_combat_log_frame(self, frame: SubjectiveCombatLogFrame) -> None:
        key = self.partition_key
        if (
            frame.source_stream_id != key.source_stream_id
            or frame.generation_id != key.generation_id
            or frame.perspective_epoch_id != key.perspective_epoch_id
        ):
            raise SubjectiveJournalIdentityError(
                "combat-log frame does not belong to this journal partition"
            )
        if frame.combat_log_cursor != self._watermarks.combat_log_cursor + 1:
            raise SubjectiveJournalInvariantError(
                "combat-log cursor must advance by exactly one"
            )
        if (
            self._combat_log_deliveries
            and frame.event_cursor
            < self._combat_log_deliveries[-1].frame.event_cursor
        ):
            raise SubjectiveJournalInvariantError(
                "combat-log source-event barriers must be nondecreasing"
            )
        if frame.event_cursor > self._watermarks.source_event_cursor:
            raise SubjectiveJournalInvariantError(
                "combat-log barrier exceeds the consumed source-event watermark"
            )

    def _merge_backfill_deliveries(
        self,
        observation_backfill: SubjectiveFramesResponse,
        combat_log_backfill: SubjectiveCombatLogFramesResponse,
    ) -> tuple[SubjectiveFrameDelivery | SubjectiveCombatLogDelivery, ...]:
        """Restore the journal's exact cross-channel order through one barrier."""

        frame_deliveries = tuple(
            SubjectiveFrameDelivery(frame=frame)
            for frame in observation_backfill.frames
        )
        log_deliveries = tuple(
            delivery
            for delivery in self._combat_log_deliveries
            if combat_log_backfill.from_cursor
            < delivery.frame.combat_log_cursor
            <= combat_log_backfill.through_cursor
        )
        merged: list[SubjectiveFrameDelivery | SubjectiveCombatLogDelivery] = []
        frame_index = 0
        log_index = 0
        while frame_index < len(frame_deliveries) and log_index < len(log_deliveries):
            frame_delivery = frame_deliveries[frame_index]
            log_delivery = log_deliveries[log_index]
            frame_watermarks = frame_delivery.frame.watermarks
            log_watermarks = log_delivery.watermarks
            if log_watermarks.dominates(frame_watermarks):
                merged.append(frame_delivery)
                frame_index += 1
                continue
            if frame_watermarks.dominates(log_watermarks):
                merged.append(log_delivery)
                log_index += 1
                continue
            raise SubjectiveJournalInvariantError(
                "retained subjective deliveries do not have one canonical order"
            )
        merged.extend(frame_deliveries[frame_index:])
        merged.extend(log_deliveries[log_index:])
        return tuple(merged)

    def _observation_boundary(self, observation_cursor: int) -> PlayerReplicationWatermarks:
        if observation_cursor == self._retained_from_observation_cursor:
            return self._retained_from_observation_watermarks
        for frame in self._frames:
            if frame.watermarks.observation_cursor == observation_cursor:
                return frame.watermarks
        raise SubjectiveJournalInvariantError(
            f"retained observation boundary {observation_cursor} is missing"
        )

    def _fan_out(self, delivery: SubjectiveStreamDelivery) -> None:
        for subscription in tuple(self._subscriptions):
            if not subscription.enqueue(delivery):
                self._subscriptions.remove(subscription)

    def _require_healthy(self) -> None:
        if self._unhealthy_reason is not None:
            raise SubjectiveJournalUnhealthyError(self._unhealthy_reason)

    def _mark_unhealthy(self, reason: str) -> None:
        if self._unhealthy_reason is not None:
            return
        self._unhealthy_reason = reason
        for subscription in tuple(self._subscriptions):
            subscription.close(reason, resync_required=True)
        self._subscriptions.clear()


class SubjectiveJournalStore:
    """Registry partitioned by source stream, generation, and authority epoch."""

    def __init__(self) -> None:
        self._journals: dict[
            SubjectiveJournalPartitionKey,
            SubjectiveReplicationJournal,
        ] = {}
        self._retired_keys: set[SubjectiveJournalPartitionKey] = set()
        self._lock = RLock()

    def open(
        self,
        *,
        protocol: PlayerReplicationProtocolIdentity,
        perspective: SubjectivePerspective,
        initial_source_event_cursor: int = 0,
        observation_retention: int = DEFAULT_OBSERVATION_RETENTION,
        combat_log_retention: int = DEFAULT_COMBAT_LOG_RETENTION,
    ) -> SubjectiveReplicationJournal:
        """Return one exact partition, rejecting epoch reuse under new authority."""
        with self._lock:
            key = SubjectiveJournalPartitionKey(
                source_stream_id=protocol.source_stream_id,
                generation_id=protocol.generation_id,
                perspective_epoch_id=perspective.perspective_epoch_id,
            )
            if key in self._retired_keys:
                raise SubjectiveJournalIdentityError(
                    "retired generation/perspective partition cannot be reused"
                )
            existing = self._journals.get(key)
            if existing is not None:
                if existing.protocol != protocol or existing.perspective != perspective:
                    raise SubjectiveJournalIdentityError(
                        "journal partition key was reused with different protocol or authority"
                    )
                return existing
            journal = SubjectiveReplicationJournal(
                protocol=protocol,
                perspective=perspective,
                initial_source_event_cursor=initial_source_event_cursor,
                observation_retention=observation_retention,
                combat_log_retention=combat_log_retention,
            )
            self._journals[key] = journal
            return journal

    def get(self, key: SubjectiveJournalPartitionKey) -> SubjectiveReplicationJournal:
        """Return one exact partition without any generation or epoch fallback."""
        with self._lock:
            journal = self._journals.get(key)
            if journal is None:
                raise SubjectiveJournalIdentityError(
                    "subjective replication journal partition does not exist"
                )
            return journal

    def discard_uninitialized(
        self,
        key: SubjectiveJournalPartitionKey,
        journal: SubjectiveReplicationJournal,
    ) -> None:
        """Abort a provisional open without creating a retired-key tombstone."""
        with self._lock:
            existing = self._journals.get(key)
            if existing is journal:
                self._journals.pop(key)

    def retire(self, key: SubjectiveJournalPartitionKey) -> None:
        """Remove one partition and force every subscriber to resynchronize."""
        with self._lock:
            journal = self._journals.pop(key, None)
            if journal is not None:
                journal.close("journal_partition_retired")
                self._retired_keys.add(key)

    def clear_generation(self, *, source_stream_id: str, generation_id: str) -> None:
        """Retire every perspective belonging to one exact source generation."""
        with self._lock:
            keys = tuple(
                key
                for key in self._journals
                if key.source_stream_id == source_stream_id
                and key.generation_id == generation_id
            )
            for key in keys:
                self.retire(key)

    def clear_all(self) -> None:
        """Close every partition and release process-lifetime tombstones."""
        with self._lock:
            for key in tuple(self._journals):
                self.retire(key)
            self._retired_keys.clear()


subjective_journal_store = SubjectiveJournalStore()


__all__ = [
    "DEFAULT_COMBAT_LOG_RETENTION",
    "DEFAULT_OBSERVATION_RETENTION",
    "DEFAULT_SUBSCRIPTION_DEPTH",
    "SubjectiveCombatLogProjectionContext",
    "SubjectiveCombatLogProjector",
    "SubjectiveFrameProjectionContext",
    "SubjectiveFrameProjector",
    "SubjectiveJournalError",
    "SubjectiveJournalIdentityError",
    "SubjectiveJournalInvariantError",
    "SubjectiveJournalPartitionKey",
    "SubjectiveJournalResyncRequired",
    "SubjectiveJournalStore",
    "SubjectiveJournalUnhealthyError",
    "SubjectiveProjectionError",
    "SubjectiveReplicationJournal",
    "SubjectiveSubscription",
    "SubjectiveSubscriptionClosedError",
    "SubjectiveSubscriptionSnapshot",
    "SubjectiveWorldProjectionContext",
    "SubjectiveWorldProjector",
    "subjective_journal_store",
]
