"""Projection helpers for agent-observer retained telemetry."""

from __future__ import annotations

from typing import Any, Iterable

from ai.subjective.models import AgentEventPayload, AgentEventHistoryResponse


_HISTORY_METADATA_KEYS = frozenset(
    {
        "count",
        "total",
        "next_agent_cursor",
        "earliest_agent_cursor",
        "resync_required",
    }
)


def extract_agent_event_payloads(payload: Any) -> list[AgentEventPayload]:
    """Extract observer-ready agent event rows from retained JSON-like data.

    Args:
        payload: Retained artifact JSON, agent-event history JSON, raw list of
            agent event rows, or already validated Pydantic models.

    Returns:
        Agent event payloads normalized to the live stream envelope shape.

    Raises:
        ValueError: If no known telemetry row collection is present.
    """
    rows = _first_event_rows(payload)
    if rows is None:
        raise ValueError("No agent telemetry events found in retained payload.")
    return [
        _normalize_agent_event_row(row, index)
        for index, row in enumerate(rows)
    ]


def project_agent_event_history(payload: Any) -> AgentEventHistoryResponse:
    """Build a history response from retained observer telemetry rows.

    Args:
        payload: Retained artifact JSON, history JSON, or raw event rows.

    Returns:
        Cursor-addressed event history suitable for observer replay.
    """
    if isinstance(payload, AgentEventHistoryResponse):
        return _validate_history_metadata(payload)
    if isinstance(payload, dict):
        for key in ("agent_events_response", "agent_events", "agent_event_history"):
            nested = payload.get(key)
            if nested is not None:
                return project_agent_event_history(nested)
        if isinstance(payload.get("events"), list) and _has_history_metadata(payload):
            return _validate_history_metadata(AgentEventHistoryResponse.model_validate(payload))

    events = extract_agent_event_payloads(payload)
    total = max((event.agent_cursor for event in events), default=0)
    earliest = events[0].agent_cursor if events else total
    return _validate_history_metadata(
        AgentEventHistoryResponse(
            events=events,
            count=len(events),
            total=total,
            next_agent_cursor=total,
            earliest_agent_cursor=earliest,
            resync_required=False,
        )
    )


def _has_history_metadata(payload: dict[str, Any]) -> bool:
    """Return whether a dict claims to be a cursor-addressed history."""
    return any(key in payload for key in _HISTORY_METADATA_KEYS)


def _validate_history_metadata(history: AgentEventHistoryResponse) -> AgentEventHistoryResponse:
    """Reject retained history envelopes whose cursor metadata lies."""
    if history.count != len(history.events):
        raise ValueError("Agent event count does not match retained rows.")

    for field_name in ("total", "next_agent_cursor", "earliest_agent_cursor"):
        if getattr(history, field_name) < 0:
            raise ValueError(f"Agent event {field_name} must be non-negative.")

    cursors = [event.agent_cursor for event in history.events]
    if any(cursor <= 0 for cursor in cursors):
        raise ValueError("Agent event cursors must be positive.")
    if cursors != sorted(cursors) or len(cursors) != len(set(cursors)):
        raise ValueError("Agent event cursors must be unique and ordered.")

    if not cursors:
        if history.next_agent_cursor > history.total:
            raise ValueError("Agent event next cursor cannot exceed total for empty history.")
        if history.earliest_agent_cursor > history.total:
            raise ValueError("Agent event earliest cursor cannot exceed total.")
        return history

    first_cursor = cursors[0]
    last_cursor = cursors[-1]
    if history.total < last_cursor:
        raise ValueError("Agent event total cursor predates retained rows.")
    if history.next_agent_cursor != last_cursor:
        raise ValueError("Agent event next cursor does not match retained rows.")
    if history.earliest_agent_cursor > first_cursor:
        raise ValueError("Agent event earliest cursor is newer than returned rows.")
    return history


def _first_event_rows(payload: Any) -> Iterable[Any] | None:
    """Return the first recognized telemetry row collection."""
    if isinstance(payload, AgentEventHistoryResponse):
        return payload.events
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None
    for key in ("agent_events_response", "agent_events", "agent_event_history"):
        nested = payload.get(key)
        if nested is not None:
            rows = _first_event_rows(nested)
            if rows is not None:
                return rows
    events = payload.get("events")
    return events if isinstance(events, list) else None


def _normalize_agent_event_row(row: Any, index: int) -> AgentEventPayload:
    """Normalize one row to `AgentEventPayload`."""
    if isinstance(row, AgentEventPayload):
        return row
    if not isinstance(row, dict):
        raise ValueError(f"Agent telemetry row {index} is not an object.")
    if "event" in row and "agent_cursor" in row:
        return AgentEventPayload.model_validate(row)
    if "event_type" not in row:
        raise ValueError(f"Agent telemetry row {index} has no event payload.")
    cursor = int(row.get("agent_cursor") or index + 1)
    return AgentEventPayload.model_validate(
        {
            "event_index": row.get("event_index", index),
            "agent_cursor": cursor,
            "observation_cursor": row.get("observation_cursor"),
            "epoch_id": row.get("epoch_id"),
            "event": row,
        }
    )
