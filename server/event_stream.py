"""Resumable server-sent event stream for browser clients."""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, SerializeAsAny

from dnd.core.combat_log import CombatLogEntry
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.encounter import Encounter


DEFAULT_SUBSCRIPTION_MAX_DEPTH = 512


class StreamSyncPayload(BaseModel):
    event_cursor: int
    combat_log_cursor: int
    session: Optional[Dict[str, Any]] = None


class GameEventPayload(BaseModel):
    event_index: int
    event_cursor: int
    combat_log_cursor: int
    event: SerializeAsAny[Event]


class CombatLogPayload(BaseModel):
    log_index: int
    event_cursor: int
    combat_log_cursor: int
    entry: CombatLogEntry


class HeartbeatPayload(BaseModel):
    server_time: float
    event_cursor: int
    combat_log_cursor: int
    session: Optional[Dict[str, Any]] = None


class EvictedPayload(BaseModel):
    reason: str


def make_stream_id(event_cursor: int, combat_log_cursor: int) -> str:
    """Build a readable composite SSE id."""
    return f"e={event_cursor};l={combat_log_cursor}"


def format_sse(event: str, data: BaseModel | Dict[str, Any], event_id: Optional[str] = None) -> str:
    """Format one SSE frame."""
    lines: List[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    payload = (
        json.dumps(data, default=str)
        if isinstance(data, dict)
        else json.dumps(data.model_dump(mode="json"), default=str)
    )
    for line in payload.splitlines():
        lines.append(f"data: {line}")
    lines.append("")
    return "\n".join(lines) + "\n"


class BoundedSubscription:
    """Per-client queue with explicit eviction on overflow."""

    def __init__(self, max_depth: int = DEFAULT_SUBSCRIPTION_MAX_DEPTH) -> None:
        self._queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=max_depth)
        self._evicted = False

    @property
    def evicted(self) -> bool:
        return self._evicted

    def try_enqueue(self, envelope: Dict[str, Any]) -> bool:
        if self._evicted:
            return False
        try:
            self._queue.put_nowait(envelope)
            return True
        except asyncio.QueueFull:
            self._evicted = True
            while not self._queue.empty():
                with contextlib.suppress(asyncio.QueueEmpty):
                    self._queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                self._queue.put_nowait({
                    "event": "evicted",
                    "data": EvictedPayload(reason="subscriber_queue_overflow"),
                    "id": None,
                })
            return False

    async def get(self) -> Dict[str, Any]:
        return await self._queue.get()


class DndEventStream:
    """Fan-out bridge from EventQueue and Encounter combat log to SSE clients."""

    def __init__(self) -> None:
        self._subscriptions: List[BoundedSubscription] = []
        self._pending_logs_by_lineage: Dict[str, List[CombatLogPayload]] = {}

    def start(self) -> None:
        EventQueue.add_on_event_callback(self._on_event)
        Encounter.add_combat_log_listener(self._on_combat_log)

    def ensure_attached(self) -> None:
        """Reattach after EventQueue.reset(), which clears passive callbacks."""
        self.start()

    def stop(self) -> None:
        EventQueue.remove_on_event_callback(self._on_event)
        Encounter.remove_combat_log_listener(self._on_combat_log)
        for sub in list(self._subscriptions):
            sub.try_enqueue({
                "event": "evicted",
                "data": EvictedPayload(reason="server_shutdown"),
                "id": None,
            })
        self._subscriptions.clear()
        self._pending_logs_by_lineage.clear()

    def subscribe(self, max_depth: int = DEFAULT_SUBSCRIPTION_MAX_DEPTH) -> BoundedSubscription:
        sub = BoundedSubscription(max_depth=max_depth)
        self._subscriptions.append(sub)
        return sub

    def unsubscribe(self, sub: BoundedSubscription) -> None:
        if sub in self._subscriptions:
            self._subscriptions.remove(sub)

    def current_event_cursor(self) -> int:
        return EventQueue.event_cursor()

    def current_combat_log_cursor(self, encounter: Optional[Encounter]) -> int:
        return len(encounter.combat_log) if encounter is not None else 0

    def current_stream_id(self, encounter: Optional[Encounter]) -> str:
        return make_stream_id(
            self.current_event_cursor(),
            self.current_combat_log_cursor(encounter),
        )

    def iter_game_events_since(self, since: int, encounter: Optional[Encounter]) -> List[GameEventPayload]:
        return [
            self._game_event_payload(index, event, encounter)
            for index, event in EventQueue.iter_events_since(since)
        ]

    def iter_combat_logs_since(
        self,
        encounter: Optional[Encounter],
        since: int,
    ) -> List[CombatLogPayload]:
        if encounter is None:
            return []
        start = max(0, since)
        return [
            self._combat_log_payload(index, entry, encounter)
            for index, entry in enumerate(encounter.combat_log[start:], start=start)
        ]

    def _on_event(self, event: Event) -> None:
        index = EventQueue.get_event_index(event.uuid)
        if index is None:
            return
        encounter = Encounter.get_active()
        payload = self._game_event_payload(index, event, encounter)
        self._publish("game_event", payload)

        if event.phase == EventPhase.COMPLETION:
            pending = self._pending_logs_by_lineage.pop(str(event.lineage_uuid), [])
            for log_payload in pending:
                self._publish("combat_log", log_payload)

    def _on_combat_log(
        self,
        encounter: Encounter,
        index: int,
        entry: CombatLogEntry,
        event: Event,
    ) -> None:
        payload = self._combat_log_payload(index, entry, encounter)
        if event.use_register and EventQueue.get_event_index(event.uuid) is None:
            key = str(event.lineage_uuid)
            self._pending_logs_by_lineage.setdefault(key, []).append(payload)
            return
        self._publish("combat_log", payload)

    def _game_event_payload(
        self,
        index: int,
        event: Event,
        encounter: Optional[Encounter],
    ) -> GameEventPayload:
        return GameEventPayload(
            event_index=index,
            event_cursor=index + 1,
            combat_log_cursor=self.current_combat_log_cursor(encounter),
            event=event,
        )

    def _combat_log_payload(
        self,
        index: int,
        entry: CombatLogEntry,
        encounter: Optional[Encounter],
    ) -> CombatLogPayload:
        return CombatLogPayload(
            log_index=index,
            event_cursor=self.current_event_cursor(),
            combat_log_cursor=index + 1,
            entry=entry,
        )

    def _publish(self, event: str, data: BaseModel) -> None:
        event_cursor = int(getattr(data, "event_cursor", self.current_event_cursor()))
        combat_log_cursor = int(getattr(data, "combat_log_cursor", 0))
        envelope = {
            "event": event,
            "data": data,
            "id": make_stream_id(event_cursor, combat_log_cursor),
        }
        for sub in list(self._subscriptions):
            if not sub.try_enqueue(envelope):
                self.unsubscribe(sub)


event_stream = DndEventStream()
