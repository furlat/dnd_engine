"""Session-scoped agent telemetry stream."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional

from pydantic import BaseModel

from server.agent_protocol.telemetry import (
    AgentEvent,
    AgentEventPayload,
    AgentHeartbeatPayload,
    AgentStreamSyncPayload,
)
from server.event_stream import BoundedSubscription, DEFAULT_SUBSCRIPTION_MAX_DEPTH

DEFAULT_AGENT_HISTORY_LIMIT = 2048


def make_agent_stream_id(agent_cursor: int, observation_cursor: Optional[int] = None) -> str:
    """Build an SSE id for agent telemetry."""
    return f"a={agent_cursor};o={observation_cursor or 0}"


class AgentEventStream:
    """Per-session fan-out stream for agent runtime telemetry."""

    def __init__(self, history_limit: int = DEFAULT_AGENT_HISTORY_LIMIT) -> None:
        """Create an empty stream."""
        self.history_limit = history_limit
        self._history: Dict[str, Deque[AgentEventPayload]] = defaultdict(lambda: deque(maxlen=self.history_limit))
        self._cursors: Dict[str, int] = defaultdict(int)
        self._subscriptions: Dict[str, List[BoundedSubscription]] = defaultdict(list)
        self._event_payloads: Dict[str, Dict[str, AgentEventPayload]] = defaultdict(dict)

    def clear_all(self) -> None:
        """Clear all history and evict subscribers."""
        for subscriptions in self._subscriptions.values():
            for sub in list(subscriptions):
                sub.try_enqueue({"event": "evicted", "data": {"reason": "server_reset"}, "id": None})
        self._history.clear()
        self._cursors.clear()
        self._subscriptions.clear()
        self._event_payloads.clear()

    def clear_session(self, session_id: str) -> None:
        """Clear history and subscribers for one session."""
        for sub in list(self._subscriptions.get(session_id, [])):
            sub.try_enqueue({"event": "evicted", "data": {"reason": "session_reset"}, "id": None})
        self._history.pop(session_id, None)
        self._cursors.pop(session_id, None)
        self._subscriptions.pop(session_id, None)
        self._event_payloads.pop(session_id, None)

    def current_agent_cursor(self, session_id: str) -> int:
        """Return the current event cursor for one session."""
        return self._cursors.get(session_id, 0)

    def earliest_agent_cursor(self, session_id: str) -> int:
        """Return the first retained event cursor, or the current cursor when empty."""
        history = self._history.get(session_id)
        if history:
            return history[0].agent_cursor
        return self.current_agent_cursor(session_id)

    def is_cursor_evicted(self, session_id: str, since: int) -> bool:
        """Return whether retained history can no longer resume after a cursor."""
        history = self._history.get(session_id)
        if not history:
            return False
        return max(0, since) < history[0].agent_cursor - 1

    def current_stream_id(self, session_id: str, observation_cursor: Optional[int] = None) -> str:
        """Return current SSE id for one session."""
        return make_agent_stream_id(self.current_agent_cursor(session_id), observation_cursor)

    def sync_payload(
        self,
        session_id: str,
        *,
        observation_cursor: Optional[int] = None,
        epoch_id: Optional[str] = None,
        session: Optional[dict[str, Any]] = None,
    ) -> AgentStreamSyncPayload:
        """Build a sync payload."""
        return AgentStreamSyncPayload(
            agent_cursor=self.current_agent_cursor(session_id),
            observation_cursor=observation_cursor,
            epoch_id=epoch_id,
            session=session,
        )

    def heartbeat_payload(
        self,
        session_id: str,
        *,
        observation_cursor: Optional[int] = None,
        epoch_id: Optional[str] = None,
        session: Optional[dict[str, Any]] = None,
    ) -> AgentHeartbeatPayload:
        """Build a heartbeat payload."""
        return AgentHeartbeatPayload(
            server_time=time.time(),
            agent_cursor=self.current_agent_cursor(session_id),
            observation_cursor=observation_cursor,
            epoch_id=epoch_id,
            session=session,
        )

    def publish(self, session_id: str, event: AgentEvent | dict[str, Any]) -> AgentEventPayload:
        """Publish one agent event to history and subscribers."""
        if not isinstance(event, AgentEvent):
            event = AgentEvent.model_validate(event)
        event = event.model_copy(update={"session_id": session_id})
        existing = self._event_payloads.get(session_id, {}).get(event.event_id)
        if existing is not None:
            return existing
        history = self._history[session_id]
        if history.maxlen is not None and len(history) == history.maxlen:
            evicted = history[0]
            self._event_payloads[session_id].pop(evicted.event.event_id, None)
        agent_cursor = self.current_agent_cursor(session_id) + 1
        payload = AgentEventPayload(
            event_index=agent_cursor - 1,
            agent_cursor=agent_cursor,
            observation_cursor=event.observation_cursor,
            epoch_id=event.epoch_id,
            event=event,
        )
        history.append(payload)
        self._event_payloads[session_id][event.event_id] = payload
        self._cursors[session_id] = agent_cursor
        self._publish(session_id, "agent_event", payload)
        return payload

    def publish_many(self, session_id: str, events: list[AgentEvent | dict[str, Any]]) -> list[AgentEventPayload]:
        """Publish several events."""
        return [self.publish(session_id, event) for event in events]

    def iter_agent_events_since(self, session_id: str, since: int, limit: int = 100) -> list[AgentEventPayload]:
        """Return agent events after a cursor."""
        start = max(0, since)
        rows = [payload for payload in self._history.get(session_id, []) if payload.agent_cursor > start]
        if limit > 0:
            rows = rows[:limit]
        return rows

    def subscribe(self, session_id: str, max_depth: int = DEFAULT_SUBSCRIPTION_MAX_DEPTH) -> BoundedSubscription:
        """Subscribe to live events for one session."""
        sub = BoundedSubscription(max_depth=max_depth)
        self._subscriptions[session_id].append(sub)
        return sub

    def unsubscribe(self, session_id: str, sub: BoundedSubscription) -> None:
        """Remove one subscription."""
        if sub in self._subscriptions.get(session_id, []):
            self._subscriptions[session_id].remove(sub)

    def _publish(self, session_id: str, event: str, data: BaseModel) -> None:
        """Fan out one envelope."""
        agent_cursor = int(getattr(data, "agent_cursor", self.current_agent_cursor(session_id)))
        observation_cursor = getattr(data, "observation_cursor", None)
        envelope = {
            "event": event,
            "data": data,
            "id": make_agent_stream_id(agent_cursor, observation_cursor),
        }
        for sub in list(self._subscriptions.get(session_id, [])):
            if not sub.try_enqueue(envelope):
                self.unsubscribe(session_id, sub)


agent_event_stream = AgentEventStream()
