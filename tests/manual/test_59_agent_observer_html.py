"""Static contracts for the agent observer HTML."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OBSERVER_HTML = REPOSITORY_ROOT / "ai" / "AI_AGENT_OBSERVER.html"
AI_README = REPOSITORY_ROOT / "ai" / "readme.md"


def test_agent_observer_targets_agent_event_stream_only() -> None:
    """The observer should consume replay and SSE telemetry endpoints."""
    html = OBSERVER_HTML.read_text(encoding="utf-8")

    assert 'id="ao-api-base"' in html
    assert 'id="ao-session-id"' in html
    assert 'id="ao-session-list"' in html
    assert 'id="ao-load-sessions"' in html
    assert 'id="ao-load-history"' in html
    assert 'id="ao-artifact-file"' in html
    assert 'id="ao-connect"' in html
    assert 'id="ao-disconnect"' in html
    assert 'id="ao-agent-cursor"' in html
    assert 'id="ao-observation-cursor"' in html
    assert 'id="ao-epoch-id"' in html
    assert 'id="ao-latest-command"' in html
    assert 'id="ao-latest-decision"' in html
    assert 'id="ao-candidates"' in html
    assert 'id="ao-command-flow"' in html
    assert 'id="ao-timings"' in html
    assert 'id="ao-type-counts"' in html
    assert 'id="ao-detail"' in html
    assert "/ai/sessions" in html
    assert "/ai/sessions/" in html
    assert "/agent-events?since=" in html
    assert "/agent-events/subscribe?since=" in html
    assert "loadSessions" in html
    assert "selectSessionFromList" in html
    assert "loadArtifactFile" in html
    assert "extractAgentEventRows" in html
    assert "normalizeAgentEventRow" in html
    assert "new EventSource" in html
    assert 'addEventListener("sync"' in html
    assert 'addEventListener("agent_event"' in html
    assert 'addEventListener("heartbeat"' in html
    assert 'addEventListener("evicted"' in html


def test_agent_observer_derives_policy_and_command_audit_panels_locally() -> None:
    """Observer should turn telemetry payloads into decision and command views."""
    html = OBSERVER_HTML.read_text(encoding="utf-8")

    assert "renderDerivedTelemetry" in html
    assert "renderLatestDecision" in html
    assert "renderLatestCommand" in html
    assert "renderCandidates" in html
    assert "renderCommandFlow" in html
    assert "renderTimings" in html
    assert "candidateRowsFromDecision" in html
    assert "policy.decision_evaluated" in html
    assert "command.stream_result" in html
    assert "command.ack" in html
    assert "runtime.command_timing" in html
    assert "selected_command" in html
    assert "row_id" in html
    assert "routine_id" in html


def test_agent_observer_can_load_retained_artifact_event_history() -> None:
    """Retained JSON artifacts should replay through the same event renderer."""
    html = OBSERVER_HTML.read_text(encoding="utf-8")

    assert "agent_events_response" in html
    assert "agent_events" in html
    assert "agent_event_history" in html
    assert "No agent telemetry events found in selected JSON." in html
    assert "Loaded ${rows.length} retained agent events" in html
    assert "disconnect(false)" in html


def test_agent_observer_rejects_bad_retained_history_metadata() -> None:
    """History-shaped retained JSON should not be silently recomputed in UI."""
    html = OBSERVER_HTML.read_text(encoding="utf-8")

    assert "findAgentEventRows" in html
    assert "hasAgentHistoryMetadata" in html
    assert "validateAgentEventHistoryMetadata" in html
    assert "Agent telemetry count does not match retained rows." in html
    assert "Agent telemetry cursors must be unique and ordered." in html
    assert "Agent telemetry next cursor does not match retained rows." in html
    assert "Agent telemetry total cursor predates retained rows." in html
    assert "Agent telemetry history contains invalid event rows." in html


def test_agent_observer_renders_correlation_fields_without_objective_polling() -> None:
    """Observer UI should expose telemetry correlation fields without debug polling."""
    html = OBSERVER_HTML.read_text(encoding="utf-8")

    assert "agent_cursor" in html
    assert "observation_cursor" in html
    assert "epoch_id" in html
    assert "event_type" in html
    assert "actor_uuid" in html
    assert "summary" in html
    assert "payload" in html
    assert "/available-actions" not in html
    assert "/state" not in html
    assert "/visibility" not in html


def test_ai_readme_documents_agent_observer_contract() -> None:
    """The AI package docs should make the observer discoverable."""
    readme = AI_README.read_text(encoding="utf-8")

    assert "## Agent Observer" in readme
    assert "ai/AI_AGENT_OBSERVER.html" in readme
    assert "GET /ai/sessions" in readme
    assert "GET /ai/sessions/{session_id}/agent-events?since=<cursor>&limit=<n>" in readme
    assert "GET /ai/sessions/{session_id}/agent-events/subscribe?since=<cursor>" in readme
    assert "agent_events_response.events" in readme
    assert "ai.evaluation.agent_observer_projection" in readme
    assert "AgentEventHistoryResponse" in readme
    assert "same local renderer as the live SSE stream" in readme
    assert "not gameplay authority" in readme
