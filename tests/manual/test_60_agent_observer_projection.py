"""Retained telemetry projection for the agent observer."""

import pytest

from ai.evaluation.agent_observer_projection import (
    extract_agent_event_payloads,
    project_agent_event_history,
)


def test_direct_codex_artifact_shape_projects_to_agent_event_history() -> None:
    """Direct Codex artifacts should replay through the observer contract."""
    artifact_payload = {
        "artifact_type": "direct_codex_run",
        "run_id": "observer-projection",
        "agent_events_response": {
            "events": [
                _agent_event_payload(
                    1,
                    "policy.decision_evaluated",
                    payload={"decision": {"candidates": [], "selected": {"reason": "test"}}},
                ),
                _agent_event_payload(
                    2,
                    "command.submitted",
                    payload={"selected_command": {"row_id": "entity|Attack|uuid=target", "reason": "test"}},
                ),
            ],
            "count": 2,
            "total": 2,
            "next_agent_cursor": 2,
            "earliest_agent_cursor": 1,
            "resync_required": False,
        },
    }

    history = project_agent_event_history(artifact_payload)

    assert history.count == 2
    assert history.total == 2
    assert [row.agent_cursor for row in history.events] == [1, 2]
    assert [row.event.event_type for row in history.events] == [
        "policy.decision_evaluated",
        "command.submitted",
    ]
    assert history.events[1].event.payload["selected_command"]["row_id"] == "entity|Attack|uuid=target"


def test_raw_agent_event_rows_are_normalized_for_observer_replay() -> None:
    """Older retained rows without envelopes should gain stable cursors."""
    rows = [
        {
            "session_id": "session-1",
            "event_type": "command.ack.accepted",
            "source": "ai.subjective.runtime",
            "summary": "accepted",
            "payload": {"status": "accepted"},
        },
        {
            "session_id": "session-1",
            "agent_cursor": 9,
            "event_type": "runtime.command_timing",
            "source": "ai.subjective.runtime",
            "summary": "timing",
            "payload": {"total_ms": 3.5},
        },
    ]

    events = extract_agent_event_payloads(rows)
    history = project_agent_event_history(rows)

    assert [event.agent_cursor for event in events] == [1, 9]
    assert history.count == 2
    assert history.total == 9
    assert history.earliest_agent_cursor == 1
    assert history.events[1].event.payload["total_ms"] == 3.5


def test_raw_events_dict_without_history_metadata_is_normalized() -> None:
    """A lightweight retained dict with only rows should not need cursors yet."""
    history = project_agent_event_history(
        {
            "events": [
                {
                    "session_id": "session-1",
                    "event_type": "policy.epoch_received",
                    "source": "ai.subjective.runtime",
                    "summary": "epoch",
                    "payload": {"epoch_id": "epoch-1"},
                }
            ]
        }
    )

    assert history.count == 1
    assert history.total == 1
    assert history.next_agent_cursor == 1
    assert history.events[0].event.event_type == "policy.epoch_received"


def test_retained_history_with_bad_count_is_rejected() -> None:
    """Full history metadata should not be silently recomputed."""
    payload = _agent_history_payload()
    payload["agent_events_response"]["count"] = 99

    with pytest.raises(ValueError, match="count"):
        project_agent_event_history(payload)


def test_retained_history_with_bad_cursor_order_is_rejected() -> None:
    """Cursor order is part of the retained observer evidence contract."""
    payload = _agent_history_payload()
    events = payload["agent_events_response"]["events"]
    payload["agent_events_response"]["events"] = [events[1], events[0]]

    with pytest.raises(ValueError, match="unique and ordered"):
        project_agent_event_history(payload)


def test_retained_history_with_bad_next_cursor_is_rejected() -> None:
    """The next cursor must describe the final returned retained event."""
    payload = _agent_history_payload()
    payload["agent_events_response"]["next_agent_cursor"] = 1

    with pytest.raises(ValueError, match="next cursor"):
        project_agent_event_history(payload)


def test_missing_agent_telemetry_rows_are_rejected() -> None:
    """A retained artifact without telemetry should not silently look empty."""
    with pytest.raises(ValueError, match="No agent telemetry events"):
        extract_agent_event_payloads({"artifact_type": "direct_codex_run"})


def _agent_history_payload() -> dict:
    """Build a valid full history-shaped retained artifact."""
    return {
        "artifact_type": "direct_codex_run",
        "agent_events_response": {
            "events": [
                _agent_event_payload(1, "policy.decision_evaluated", payload={"decision": {}}),
                _agent_event_payload(2, "command.submitted", payload={"selected_command": {}}),
            ],
            "count": 2,
            "total": 2,
            "next_agent_cursor": 2,
            "earliest_agent_cursor": 1,
            "resync_required": False,
        },
    }


def _agent_event_payload(
    cursor: int,
    event_type: str,
    *,
    payload: dict,
) -> dict:
    """Build one stream-shaped agent event payload."""
    return {
        "event_index": cursor - 1,
        "agent_cursor": cursor,
        "observation_cursor": cursor + 10,
        "epoch_id": f"epoch-{cursor}",
        "event": {
            "event_id": f"event-{cursor}",
            "session_id": "session-1",
            "actor_uuid": "actor-1",
            "epoch_id": f"epoch-{cursor}",
            "observation_cursor": cursor + 10,
            "event_type": event_type,
            "level": "info",
            "source": "test",
            "summary": event_type,
            "payload": payload,
            "tags": ["observer"],
            "created_at": float(cursor),
        },
    }
