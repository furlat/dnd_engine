"""Agent telemetry stream checks."""

import logging

import httpx
import pytest

from ai.subjective.models import AgentEvent
from ai.subjective.runtime import HttpAgentEventSink
from server import event_server
from server.agent_event_stream import AgentEventStream
from server.event_stream import format_sse
from server.session import PlayerType
from tests.manual.test_28_subjective_observation_stream import create_observation_game


def test_agent_events_are_session_scoped_and_replayable() -> None:
    """Posted agent events receive monotonic cursors and replay by session."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    event = {
        "session_id": session_id,
        "actor_uuid": str(hero.uuid),
        "event_type": "policy.tick",
        "source": "test",
        "summary": "tick",
        "payload": {"ranked": []},
    }

    post_response = client.post(f"/ai/sessions/{session_id}/agent-events", json={"events": [event]})
    replay_response = client.get(f"/ai/sessions/{session_id}/agent-events", params={"since": 0})

    assert post_response.status_code == 200
    assert post_response.json()["events"][0]["agent_cursor"] == 1
    assert replay_response.status_code == 200
    assert replay_response.json()["count"] == 1
    assert replay_response.json()["events"][0]["event"]["event_type"] == "policy.tick"
    assert replay_response.json()["next_agent_cursor"] == 1


def test_ai_session_index_lists_observable_agent_sessions_without_tactical_state() -> None:
    """The observer session index should expose metadata, not objective state."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    event_server.agent_event_stream.clear_session(session_id)
    client.post(
        f"/ai/sessions/{session_id}/agent-events",
        json={
            "events": [{
                "session_id": session_id,
                "actor_uuid": str(hero.uuid),
                "event_type": "policy.tick",
                "source": "test",
                "summary": "tick",
            }]
        },
    )

    response = client.get("/ai/sessions")

    assert response.status_code == 200
    payload = response.json()
    rows = payload["sessions"]
    row = next(row for row in rows if row["session_id"] == session_id)
    assert row["player_type"] == PlayerType.AI.value
    assert row["name"] == "Observation Agent"
    assert row["is_active_turn"] is True
    assert row["active_controlled_entity_uuid"] == str(hero.uuid)
    assert row["agent_cursor"] == 1
    assert row["earliest_agent_cursor"] == 1
    assert row["observation_cursor"] is not None
    assert row["controlled_entities"] == [{
        "entity_uuid": str(hero.uuid),
        "entity_name": "Observation Hero",
        "faction": "heroes",
        "controller_type": "human",
        "is_active_actor": True,
    }]
    assert str(monster.uuid) not in str(row)
    assert "position" not in row["controlled_entities"][0]
    assert "hp" not in row["controlled_entities"][0]


def test_session_cannot_read_other_session_agent_history() -> None:
    """Session histories are separate streams."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    manager = event_server.sim.get_session_manager()
    other_session = manager.create_session(PlayerType.AI, "Other Agent")
    if event_server.sim.game is not None:
        event_server.sim.game.add_player(other_session)

    client.post(
        f"/ai/sessions/{session_id}/agent-events",
        json={
            "events": [{
                "session_id": session_id,
                "event_type": "policy.tick",
                "source": "test",
                "summary": "tick",
            }]
        },
    )
    other_history = client.get(f"/ai/sessions/{other_session.session_id}/agent-events").json()

    assert other_history["events"] == []
    assert other_history["total"] == 0


def test_agent_stream_uses_existing_sse_formatter() -> None:
    """Agent stream payloads are serializable by the shared SSE helper."""
    stream = AgentEventStream()
    payload = stream.publish(
        "session",
        AgentEvent(
            session_id="session",
            event_type="policy.tick",
            source="test",
            summary="tick",
        ),
    )

    frame = format_sse("agent_event", payload, stream.current_stream_id("session", payload.observation_cursor))

    assert frame.startswith("id: a=1;o=0\n")
    assert "event: agent_event\n" in frame
    assert '"agent_cursor": 1' in frame


def test_agent_stream_reuses_cursor_for_duplicate_event_id() -> None:
    """A telemetry retry is idempotent within the retained event history."""
    stream = AgentEventStream()
    subscription = stream.subscribe("session")
    event = AgentEvent(
        event_id="policy-decision:stable",
        session_id="session",
        event_type="policy.decision_evaluated",
        source="ai.policy.host",
        summary="Policy decision evaluated.",
    )

    first = stream.publish("session", event)
    duplicate = stream.publish("session", event)

    assert duplicate is first
    assert duplicate.agent_cursor == 1
    assert stream.current_agent_cursor("session") == 1
    assert len(stream.iter_agent_events_since("session", 0)) == 1
    assert subscription.evicted is False


@pytest.mark.parametrize("status_code", [400, 500])
def test_http_agent_event_sink_reports_unsuccessful_status(
    caplog: pytest.LogCaptureFixture,
    status_code: int,
) -> None:
    """Best-effort telemetry must expose failed delivery without affecting play."""
    transport = httpx.MockTransport(lambda _request: httpx.Response(status_code))
    event = AgentEvent(
        event_id="policy-decision:stable",
        session_id="session",
        event_type="policy.decision_evaluated",
        source="ai.policy.host",
        summary="Policy decision evaluated.",
    )

    with httpx.Client(transport=transport, base_url="http://testserver") as client:
        sink = HttpAgentEventSink(client, "session")
        with caplog.at_level(logging.ERROR, logger="ai.subjective.runtime"):
            sink.emit(event)

    assert "failed to post agent events" in caplog.text


def test_agent_stream_subscription_eviction_uses_bounded_queue() -> None:
    """Overflowing a subscription marks it evicted through the shared queue type."""
    stream = AgentEventStream()
    subscription = stream.subscribe("session", max_depth=1)

    stream.publish("session", {"session_id": "session", "event_type": "one", "source": "test", "summary": "one"})
    stream.publish("session", {"session_id": "session", "event_type": "two", "source": "test", "summary": "two"})

    assert subscription.evicted is True


def test_agent_event_cursor_remains_absolute_after_history_rollover() -> None:
    """Bounded retention never reuses a session cursor or event index."""
    stream = AgentEventStream(history_limit=2)

    published = [
        stream.publish(
            "session",
            {
                "session_id": "session",
                "event_type": f"event.{index}",
                "source": "test",
                "summary": f"event {index}",
            },
        )
        for index in range(4)
    ]

    assert [row.agent_cursor for row in published] == [1, 2, 3, 4]
    assert [row.event_index for row in published] == [0, 1, 2, 3]
    assert stream.current_agent_cursor("session") == 4
    assert [row.agent_cursor for row in stream.iter_agent_events_since("session", 0)] == [3, 4]
    assert stream.earliest_agent_cursor("session") == 3
    assert stream.is_cursor_evicted("session", 0) is True
    assert stream.is_cursor_evicted("session", 2) is False


def test_clearing_agent_session_starts_a_new_cursor_domain() -> None:
    """A cleared session does not inherit cursor state from its old stream."""
    stream = AgentEventStream(history_limit=2)
    stream.publish(
        "session",
        {"session_id": "session", "event_type": "before", "source": "test", "summary": "before"},
    )

    stream.clear_session("session")
    published = stream.publish(
        "session",
        {"session_id": "session", "event_type": "after", "source": "test", "summary": "after"},
    )

    assert published.agent_cursor == 1
    assert published.event_index == 0


def test_agent_history_endpoint_signals_evicted_replay_cursor(monkeypatch) -> None:
    """History clients are told when bounded retention cannot satisfy replay."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    stream = event_server.agent_event_stream
    stream.clear_session(session_id)
    monkeypatch.setattr(stream, "history_limit", 2)
    for index in range(4):
        stream.publish(
            session_id,
            AgentEvent(
                session_id=session_id,
                actor_uuid=str(hero.uuid),
                event_type=f"event.{index}",
                source="test",
                summary=f"event {index}",
            ),
        )

    response = client.get(f"/ai/sessions/{session_id}/agent-events", params={"since": 0})

    assert response.status_code == 200
    payload = response.json()
    assert payload["resync_required"] is True
    assert payload["earliest_agent_cursor"] == 3
    assert [row["agent_cursor"] for row in payload["events"]] == [3, 4]
