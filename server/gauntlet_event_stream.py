"""Live gauntlet watcher stream."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from ai.evaluation.gauntlet_contract import GauntletEvent, GauntletEventType
from server.event_stream import BoundedSubscription, DEFAULT_SUBSCRIPTION_MAX_DEPTH, EvictedPayload

DEFAULT_GAUNTLET_HISTORY_LIMIT = 2048


def make_gauntlet_stream_id(cursor: int) -> str:
    """Build an SSE id for gauntlet watcher events."""
    return f"g={cursor}"


class LiveGauntletEventStream:
    """Bounded per-gauntlet event history with SSE fan-out."""

    def __init__(self, history_limit: int = DEFAULT_GAUNTLET_HISTORY_LIMIT) -> None:
        """Create an empty stream."""
        self.history_limit = history_limit
        self._history: Deque[GauntletEvent] = deque(maxlen=history_limit)
        self._cursor = 0
        self._subscriptions: Dict[str, List[BoundedSubscription]] = defaultdict(list)

    def clear_all(self) -> None:
        """Clear retained history and evict live subscribers."""
        for subscriptions in self._subscriptions.values():
            for sub in list(subscriptions):
                sub.try_enqueue({"event": "evicted", "data": EvictedPayload(reason="server_reset"), "id": None})
        self._history.clear()
        self._cursor = 0
        self._subscriptions.clear()

    def current_cursor(self) -> int:
        """Return the latest gauntlet event cursor."""
        return self._cursor

    def current_stream_id(self) -> str:
        """Return the current SSE id."""
        return make_gauntlet_stream_id(self._cursor)

    def latest_gauntlet_id(self) -> Optional[str]:
        """Return the most recently observed gauntlet id."""
        for event in reversed(self._history):
            return event.gauntlet_id
        return None

    def gauntlet_ids(self) -> list[str]:
        """Return retained gauntlet ids in first-seen order."""
        seen: set[str] = set()
        rows: list[str] = []
        for event in self._history:
            if event.gauntlet_id in seen:
                continue
            seen.add(event.gauntlet_id)
            rows.append(event.gauntlet_id)
        return rows

    def earliest_cursor(self, gauntlet_id: Optional[str] = None) -> int:
        """Return the earliest retained cursor for a gauntlet or all gauntlets."""
        events = self._events_for(gauntlet_id)
        return events[0].cursor if events else self.current_cursor()

    def is_cursor_evicted(self, since: int, gauntlet_id: Optional[str] = None) -> bool:
        """Return whether retained history can no longer resume after a cursor."""
        events = self._events_for(gauntlet_id)
        if not events:
            return False
        return max(0, since) < events[0].cursor - 1

    def append(
        self,
        *,
        event_type: GauntletEventType,
        gauntlet_id: str,
        match_id: Optional[str] = None,
        match_index: Optional[int] = None,
        status: Optional[str] = None,
        message: Optional[str] = None,
        payload: Optional[dict[str, object]] = None,
    ) -> GauntletEvent:
        """Append and publish one watcher event."""
        self._cursor += 1
        event = GauntletEvent(
            cursor=self._cursor,
            event_type=event_type,
            gauntlet_id=gauntlet_id,
            match_id=match_id,
            match_index=match_index,
            status=status,
            message=message,
            payload=payload or {},
            created_at=_utc_now(),
        )
        self._append_event(event)
        return event

    def publish(self, event: GauntletEvent | dict[str, Any]) -> GauntletEvent:
        """Publish an externally constructed event with a server-owned cursor.

        External gauntlet runners may use local cursors in retained summaries,
        but the live server stream has its own replay namespace. Reassigning
        cursors here keeps SSE ids and history replay monotonic even when
        multiple producers submit events with overlapping local cursors.
        """
        if not isinstance(event, GauntletEvent):
            event = GauntletEvent.model_validate(event)
        self._cursor += 1
        event = event.model_copy(update={"cursor": self._cursor})
        self._append_event(event)
        return event

    def since(self, cursor: int = 0, gauntlet_id: Optional[str] = None, limit: int = 500) -> list[GauntletEvent]:
        """Return retained events after a cursor."""
        rows = [event for event in self._events_for(gauntlet_id) if event.cursor > max(0, cursor)]
        if limit > 0:
            rows = rows[:limit]
        return rows

    def subscribe(
        self,
        gauntlet_id: str,
        max_depth: int = DEFAULT_SUBSCRIPTION_MAX_DEPTH,
    ) -> BoundedSubscription:
        """Subscribe to live events for one gauntlet."""
        sub = BoundedSubscription(max_depth=max_depth)
        self._subscriptions[gauntlet_id].append(sub)
        return sub

    def unsubscribe(self, gauntlet_id: str, sub: BoundedSubscription) -> None:
        """Remove one subscription."""
        if sub in self._subscriptions.get(gauntlet_id, []):
            self._subscriptions[gauntlet_id].remove(sub)

    def _append_event(self, event: GauntletEvent) -> None:
        if self._history.maxlen is not None and len(self._history) == self._history.maxlen:
            self._history.popleft()
        self._history.append(event)
        envelope = {"event": "gauntlet_event", "data": event, "id": make_gauntlet_stream_id(event.cursor)}
        for sub in list(self._subscriptions.get(event.gauntlet_id, [])):
            if not sub.try_enqueue(envelope):
                self.unsubscribe(event.gauntlet_id, sub)

    def _events_for(self, gauntlet_id: Optional[str]) -> list[GauntletEvent]:
        if gauntlet_id is None:
            return list(self._history)
        return [event for event in self._history if event.gauntlet_id == gauntlet_id]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


gauntlet_event_stream = LiveGauntletEventStream()
