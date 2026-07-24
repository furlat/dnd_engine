"""Server-side live gauntlet watcher checks."""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from ai.evaluation.gauntlet import build_gauntlet_schedule, build_gauntlet_summary
from ai.evaluation.gauntlet import GauntletEvent as RunnerGauntletEvent
from ai.evaluation.gauntlet import GauntletSummary as RunnerGauntletSummary
from ai.evaluation.gauntlet import run_ai_gauntlet
from server.agent_protocol.gauntlet import GauntletEvent
from server.agent_protocol.gauntlet import GauntletEvent as ContractGauntletEvent
from server.agent_protocol.gauntlet import GauntletSummary as ContractGauntletSummary
from ai.evaluation.tournament import EloConfig, TournamentSummary
from ai.external_selfplay import ExternalSelfPlayResult, ExternalSelfPlayTrace
from server import event_server
from server.event_stream import format_sse
from server.gauntlet_event_stream import LiveGauntletEventStream


def test_runner_and_server_share_gauntlet_contract_models() -> None:
    """Gauntlet runner and server watcher should not drift into duplicate models."""
    assert RunnerGauntletEvent is ContractGauntletEvent
    assert RunnerGauntletSummary is ContractGauntletSummary


def test_gauntlet_live_stream_replays_by_cursor_and_serializes_sse() -> None:
    """Live watcher events should be replayable and use shared SSE framing."""
    stream = LiveGauntletEventStream()
    first = stream.append(event_type="GAUNTLET_STARTED", gauntlet_id="g1", status="running")
    second = stream.append(event_type="MATCH_STARTED", gauntlet_id="g1", match_id="m1", match_index=0)
    stream.append(event_type="GAUNTLET_STARTED", gauntlet_id="g2", status="running")

    replay = stream.since(first.cursor, gauntlet_id="g1")
    frame = format_sse("gauntlet_event", second, f"g={second.cursor}")

    assert [event.cursor for event in replay] == [second.cursor]
    assert frame.startswith("id: g=2\n")
    assert "event: gauntlet_event\n" in frame
    assert '"event_type": "MATCH_STARTED"' in frame


def test_gauntlet_history_endpoint_returns_live_events_without_summary() -> None:
    """Live gauntlet history should be observable before the summary is written."""
    event_server.gauntlet_event_stream.clear_all()
    event_server.gauntlet_event_stream.append(
        event_type="GAUNTLET_STARTED",
        gauntlet_id="live-g",
        status="running",
    )
    client = TestClient(event_server.app)

    response = client.get("/ai/gauntlets/live-g/events", params={"since": 0})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["events"][0]["event_type"] == "GAUNTLET_STARTED"
    assert payload["resync_required"] is False


def test_live_gauntlet_watch_endpoint_projects_events_without_summary() -> None:
    """The monitor should observe an in-flight gauntlet before retained JSON exists."""
    event_server.gauntlet_event_stream.clear_all()
    event_server.gauntlet_event_stream.append(
        event_type="GAUNTLET_STARTED",
        gauntlet_id="live-only-g",
        status="running",
        payload={"mode": "rotation", "scheduled_count": 2},
    )
    event_server.gauntlet_event_stream.append(
        event_type="MATCH_STARTED",
        gauntlet_id="live-only-g",
        match_id="m1",
        match_index=0,
        status="running",
        payload={"arena_id": "standard_skeleton_doors"},
    )
    client = TestClient(event_server.app)

    latest = client.get("/ai/gauntlets/live/latest")
    watch = client.get("/ai/gauntlets/live-only-g/watch")

    assert latest.status_code == 200
    assert latest.json()["gauntlet_id"] == "live-only-g"
    assert latest.json()["mode"] == "rotation"
    assert watch.status_code == 200
    assert watch.json()["status"] == "running"
    assert watch.json()["active_match_id"] == "m1"
    assert watch.json()["pending_count"] == 2
    assert watch.json()["completed_count"] == 0
    assert watch.json()["failed_count"] == 0
    assert watch.json()["gate_status"] == "running"
    assert watch.json()["gate_reasons"] == ["pending_matches"]
    assert watch.json()["subjectivity_status"] == "not_run"
    assert watch.json()["latency_status"] == "not_run"


def test_live_gauntlet_watch_endpoint_updates_counts_from_progress_events() -> None:
    """Live watcher state should derive completed counts and audit fields from events."""
    event_server.gauntlet_event_stream.clear_all()
    event_server.gauntlet_event_stream.append(
        event_type="GAUNTLET_STARTED",
        gauntlet_id="live-progress-g",
        status="running",
        payload={"mode": "smoke", "scheduled_count": 2},
    )
    event_server.gauntlet_event_stream.append(
        event_type="MATCH_STARTED",
        gauntlet_id="live-progress-g",
        match_id="m1",
        match_index=0,
        status="running",
    )
    event_server.gauntlet_event_stream.append(
        event_type="MATCH_PROGRESS",
        gauntlet_id="live-progress-g",
        match_id="m1",
        match_index=0,
        status="encounter_ended",
        payload={
            "arena_id": "standard_skeleton_doors",
            "outcome": "heroes",
            "command_count": 3,
            "elapsed_ms": 12.5,
            "command_status_counts": {"accepted": 3},
            "subjectivity_status": "passed",
            "subjectivity_violation_count": 0,
            "max_command_total_ms": 4.0,
            "max_server_command_ms": 2.5,
            "max_local_decision_ms": 1.0,
            "run_artifact_path": "runs/m1.json",
        },
    )
    event_server.gauntlet_event_stream.append(
        event_type="RATING_UPDATED",
        gauntlet_id="live-progress-g",
        match_id="m1",
        match_index=0,
        status="ratings_updated",
        payload={"rating_after": {"standard_skeleton_doors::heroes": 1016.0}},
    )
    event_server.gauntlet_event_stream.append(
        event_type="MATCH_COMPLETED",
        gauntlet_id="live-progress-g",
        match_id="m1",
        match_index=0,
        status="encounter_ended",
        payload={"outcome": "heroes"},
    )
    client = TestClient(event_server.app)

    watch = client.get("/ai/gauntlets/live-progress-g/watch")

    assert watch.status_code == 200
    payload = watch.json()
    assert payload["active_match_id"] is None
    assert payload["completed_count"] == 1
    assert payload["pending_count"] == 1
    assert payload["latest_outcome"] == "heroes"
    assert payload["command_status_counts"] == {"accepted": 3}
    assert payload["ratings"] == {"standard_skeleton_doors::heroes": 1016.0}
    assert payload["performance"]["match_count"] == 1
    assert payload["performance"]["max_command_total_ms"] == 4.0
    assert payload["performance"]["max_server_command_ms"] == 2.5
    assert payload["performance"]["max_local_decision_ms"] == 1.0
    assert payload["artifact_paths"] == ["runs/m1.json"]
    assert payload["subjectivity_status"] == "passed"
    assert payload["latency_status"] == "passed"


def test_gauntlet_event_ingest_publishes_external_events() -> None:
    """External gauntlet processes should be able to feed the live watcher stream."""
    event_server.gauntlet_event_stream.clear_all()
    client = TestClient(event_server.app)
    event = GauntletEvent(
        cursor=1,
        event_type="MATCH_PROGRESS",
        gauntlet_id="external-g",
        match_id="m1",
        match_index=0,
        status="encounter_ended",
        payload={"command_count": 3},
        created_at="2026-07-16T00:00:00+00:00",
    )

    post = client.post("/ai/gauntlets/events", json={"events": [event.model_dump(mode="json")]})
    history = client.get("/ai/gauntlets/external-g/events", params={"since": 0})

    assert post.status_code == 200
    assert post.json()["count"] == 1
    assert history.status_code == 200
    assert history.json()["events"][0]["event_type"] == "MATCH_PROGRESS"
    assert history.json()["events"][0]["payload"]["command_count"] == 3


def test_gauntlet_event_ingest_uses_server_monotonic_cursors() -> None:
    """Server-side watcher cursors should not trust runner-local event cursors."""
    event_server.gauntlet_event_stream.clear_all()
    event_server.gauntlet_event_stream.append(
        event_type="GAUNTLET_STARTED",
        gauntlet_id="external-g",
        status="running",
    )
    client = TestClient(event_server.app)
    first = GauntletEvent(
        cursor=1,
        event_type="MATCH_STARTED",
        gauntlet_id="external-g",
        match_id="m1",
        match_index=0,
        status="running",
        created_at="2026-07-16T00:00:00+00:00",
    )
    second = GauntletEvent(
        cursor=1,
        event_type="MATCH_PROGRESS",
        gauntlet_id="external-g",
        match_id="m1",
        match_index=0,
        status="encounter_ended",
        payload={"command_count": 3},
        created_at="2026-07-16T00:00:01+00:00",
    )

    response = client.post(
        "/ai/gauntlets/events",
        json={"events": [first.model_dump(mode="json"), second.model_dump(mode="json")]},
    )
    history = client.get("/ai/gauntlets/external-g/events", params={"since": 0})

    assert response.status_code == 200
    assert [event["cursor"] for event in response.json()["events"]] == [2, 3]
    assert [event["cursor"] for event in history.json()["events"]] == [1, 2, 3]
    assert history.json()["total"] == 3
    assert history.json()["next_cursor"] == 3


def test_runner_can_publish_directly_to_server_live_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gauntlet runs should feed the same live stream consumed by watcher endpoints."""
    def fake_selfplay(
        arena_id: str,
        *,
        max_commands: int,
        hero_first: bool,
        random_seed: int,
    ) -> ExternalSelfPlayResult:
        return ExternalSelfPlayResult(
            arena_id=arena_id,
            status="encounter_ended",
            command_count=max_commands,
            elapsed_ms=1.5,
            session_ids_by_faction={"heroes": "hero-session", "monsters": "monster-session"},
            final_hp_by_actor={"Hero": 8, "Skeleton": 0},
            final_faction_by_actor={"Hero": "heroes", "Skeleton": "monsters"},
            traces=[
                ExternalSelfPlayTrace(
                    command_index=0,
                    round_number=1,
                    turn_index=0,
                    session_id="hero-session",
                    actor_uuid="hero-uuid",
                    actor_name="Hero",
                    actor_faction="heroes",
                    entity_action_count=0,
                    position_action_count=0,
                    command_type="end_turn",
                    reason="test command",
                    command_status="accepted",
                    total_ms=4.0,
                    local_decision_ms=1.25,
                    server_timing={"total_ms": 2.75},
                    subjective_known_entity_uuids=["hero-uuid"],
                    subjective_known_entity_positions=[],
                    subjective_known_object_uuids=[],
                    subjective_known_object_positions=[],
                    subjective_known_tile_positions=[],
                    subjective_visible_cell_positions=[],
                    subjective_seen_cell_positions=[],
                    subjective_affordance_row_ids=[],
                    subjective_affordance_target_uuids=[],
                    subjective_affordance_target_positions=[],
                    audit_controlled_entity_uuids=["hero-uuid"],
                    audit_authorized_entity_uuids=["hero-uuid"],
                    audit_authorized_object_uuids=[],
                    audit_authorized_positions=[],
                )
            ],
        )

    monkeypatch.setattr("ai.evaluation.gauntlet.run_external_selfplay", fake_selfplay)
    event_server.gauntlet_event_stream.clear_all()
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[44])

    summary = run_ai_gauntlet(
        schedule,
        max_commands=3,
        gauntlet_output_directory=None,
        event_stream=event_server.gauntlet_event_stream,
    )
    client = TestClient(event_server.app)
    history = client.get(f"/ai/gauntlets/{schedule.gauntlet_id}/events", params={"since": 0}).json()

    event_types = [event["event_type"] for event in history["events"]]
    assert event_types == [
        "GAUNTLET_STARTED",
        "MATCH_STARTED",
        "MATCH_PROGRESS",
        "RATING_UPDATED",
        "MATCH_COMPLETED",
        "SUMMARY_WRITTEN",
        "GAUNTLET_COMPLETED",
    ]
    assert history["events"][0]["payload"]["scheduled_count"] == 1
    assert [event.event_type for event in summary.events] == event_types
    progress = next(event for event in history["events"] if event["event_type"] == "MATCH_PROGRESS")
    rating = next(event for event in history["events"] if event["event_type"] == "RATING_UPDATED")
    assert progress["payload"]["command_count"] == 3
    assert progress["payload"]["outcome"] == "heroes"
    assert progress["payload"]["max_command_total_ms"] == 4.0
    assert progress["payload"]["max_server_command_ms"] == 2.75
    assert progress["payload"]["max_local_decision_ms"] == 1.25
    assert progress["payload"]["command_total_p95_ms"] == 4.0
    assert progress["payload"]["command_total_p99_ms"] == 4.0
    assert progress["payload"]["server_command_p95_ms"] == 2.75
    assert progress["payload"]["server_command_p99_ms"] == 2.75
    assert progress["payload"]["local_decision_p95_ms"] == 1.25
    assert progress["payload"]["local_decision_p99_ms"] == 1.25
    assert rating["payload"]["rating_after"]["standard_skeleton_doors::heroes"] == 1016.0
    assert summary.matches[0].max_server_command_ms == 2.75
    assert summary.performance is not None
    assert summary.performance.max_server_command_ms == 2.75
    assert summary.performance.command_total_p95_ms == 4.0
    assert summary.performance.command_total_p99_ms == 4.0
    assert summary.completed_count == 1
    assert summary.failed_count == 0


def test_runner_emits_match_failed_for_stale_completed_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stale command evidence should fail the gauntlet event even after encounter end."""
    def fake_selfplay(
        arena_id: str,
        *,
        max_commands: int,
        hero_first: bool,
        random_seed: int,
    ) -> ExternalSelfPlayResult:
        return ExternalSelfPlayResult(
            arena_id=arena_id,
            status="encounter_ended",
            command_count=1,
            elapsed_ms=1.5,
            session_ids_by_faction={"heroes": "hero-session"},
            final_hp_by_actor={"Hero": 8, "Skeleton": 0},
            final_faction_by_actor={"Hero": "heroes", "Skeleton": "monsters"},
            traces=[
                ExternalSelfPlayTrace(
                    command_index=0,
                    round_number=1,
                    turn_index=0,
                    session_id="hero-session",
                    actor_uuid="hero-uuid",
                    actor_name="Hero",
                    actor_faction="heroes",
                    entity_action_count=0,
                    position_action_count=0,
                    command_type="end_turn",
                    reason="test stale command",
                    command_status="stale",
                    subjective_known_entity_uuids=["hero-uuid"],
                    subjective_known_entity_positions=[],
                    subjective_known_object_uuids=[],
                    subjective_known_object_positions=[],
                    subjective_known_tile_positions=[],
                    subjective_visible_cell_positions=[],
                    subjective_seen_cell_positions=[],
                    subjective_affordance_row_ids=[],
                    subjective_affordance_target_uuids=[],
                    subjective_affordance_target_positions=[],
                    audit_controlled_entity_uuids=["hero-uuid"],
                    audit_authorized_entity_uuids=["hero-uuid"],
                    audit_authorized_object_uuids=[],
                    audit_authorized_positions=[],
                )
            ],
        )

    monkeypatch.setattr("ai.evaluation.gauntlet.run_external_selfplay", fake_selfplay)
    event_server.gauntlet_event_stream.clear_all()
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[44])

    summary = run_ai_gauntlet(
        schedule,
        max_commands=3,
        gauntlet_output_directory=None,
        event_stream=event_server.gauntlet_event_stream,
    )
    history = event_server.gauntlet_event_stream.since(0, gauntlet_id=schedule.gauntlet_id)
    failed = next(event for event in history if event.event_type == "MATCH_FAILED")

    assert failed.message == "stale_command"
    assert failed.payload["command_status_counts"] == {"stale": 1}
    assert summary.completed_count == 0
    assert summary.failed_count == 1
    assert summary.failure_rows[0].reason == "stale_command"


def test_latest_gauntlet_summary_and_watch_endpoint_use_retained_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Watcher endpoints should project retained summary JSON without fabricating values."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[1])
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[],
    )
    summary = build_gauntlet_summary(schedule, tournament)
    (tmp_path / f"{summary.gauntlet_id}.json").write_text(summary.model_dump_json(), encoding="utf-8")
    (tmp_path / "latest.json").write_text(summary.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(event_server, "GAUNTLET_SUMMARY_DIRECTORY", tmp_path)
    event_server.gauntlet_event_stream.clear_all()
    event_server.gauntlet_event_stream.append(
        event_type="GAUNTLET_STARTED",
        gauntlet_id=summary.gauntlet_id,
        status="running",
    )
    event_server.gauntlet_event_stream.append(
        event_type="MATCH_STARTED",
        gauntlet_id=summary.gauntlet_id,
        match_id="m1",
        match_index=0,
        status="running",
    )
    client = TestClient(event_server.app)

    latest = client.get("/ai/gauntlets/latest")
    watch = client.get(f"/ai/gauntlets/{summary.gauntlet_id}/watch")

    assert latest.status_code == 200
    assert latest.json()["gauntlet_id"] == summary.gauntlet_id
    assert watch.status_code == 200
    assert watch.json()["status"] == "running"
    assert watch.json()["active_match_id"] == "m1"
    assert watch.json()["pending_count"] == 1
    assert watch.json()["subjectivity_status"] == "not_run"
    assert watch.json()["gate_status"] == "not_run"
    assert watch.json()["gate_reasons"] == ["pending_matches"]
    assert watch.json()["performance"] is None
    assert watch.json()["artifact_paths"] == []
