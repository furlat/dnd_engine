"""Truthful durable evidence for direct Codex-controlled runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from ai.evaluation.direct_codex_artifacts import (
    DirectCodexArtifactCollector,
    DirectCodexFrictionCategory,
    DirectCodexFrictionAnnotation,
    DirectCodexPerspective,
    DirectCodexRotationSlot,
    DirectCodexRunArtifact,
    start_direct_codex_validation_run,
    write_direct_codex_run_artifact,
)
from ai.protocol.semantics import EffectCertainty, WorldEffectAnchor, WorldEffectScope


def test_direct_codex_artifact_round_trip_preserves_raw_subjective_evidence(
    tmp_path: Path,
) -> None:
    """The artifact retains typed source responses without derived run claims."""
    client, _requests = _artifact_client(
        snapshot=_snapshot_payload(observation_cursor=3),
        frames=_frames_payload(start_cursor=3),
        agent_events=_agent_events_payload(),
    )
    collector = DirectCodexArtifactCollector("http://testserver", client=client)
    initial_snapshot = collector.capture_initial_snapshot("session-1")

    artifact = collector.collect(
        initial_snapshot=initial_snapshot,
        rotation=DirectCodexRotationSlot(
            sequence=12,
            focus="barbarian_hero",
            mode="codex_hero",
            arena_id="double_door_dark_hunt",
        ),
        perspective=DirectCodexPerspective(
            session_id="session-1",
            takeover_claim_id="claim-1",
            faction="heroes",
            controlled_entity_uuids=["hero-1"],
        ),
        manual_friction=[
            DirectCodexFrictionAnnotation(
                category=DirectCodexFrictionCategory.LATENCY_REGRESSION,
                note="Movement-row normalization exceeded the local latency budget.",
                observation_cursor=4,
                epoch_id="epoch-1",
                command_id="command-1",
                surface="turn",
            )
        ],
        run_id="direct-codex-round-trip",
        source_revision="working-tree-test",
    )
    path = write_direct_codex_run_artifact(artifact, tmp_path)
    loaded = DirectCodexRunArtifact.model_validate_json(path.read_text(encoding="utf-8"))

    assert loaded == artifact
    assert loaded.artifact_type == "direct_codex_run"
    assert loaded.initial_subjective_snapshot.observation_cursor == 3
    frame = loaded.observation_frames_response.frames[0]
    assert frame.command_result is not None
    assert frame.command_result.command_id == "command-1"
    assert frame.command_result.payload == {"action": "Rage", "accepted": True}
    assert loaded.agent_events_response.events[0].event.event_type == "policy.selected"
    assert loaded.manual_friction[0].observation_cursor == 4
    assert "winner" not in DirectCodexRunArtifact.model_fields
    assert "performance" not in DirectCodexRunArtifact.model_fields
    assert "subjectivity" not in DirectCodexRunArtifact.model_fields


def test_direct_codex_artifact_writer_refuses_overwrite(tmp_path: Path) -> None:
    """A direct run id can create exactly one durable evidence file."""
    artifact = _collect_artifact(run_id="immutable-direct-run")

    write_direct_codex_run_artifact(artifact, tmp_path)

    with pytest.raises(FileExistsError):
        write_direct_codex_run_artifact(artifact, tmp_path)


def test_empty_agent_telemetry_remains_empty_evidence() -> None:
    """Missing Codex telemetry is retained as absence rather than zero metrics."""
    artifact = _collect_artifact(
        run_id="empty-telemetry",
        agent_events=_agent_events_payload(events=[]),
    )

    assert artifact.agent_events_response.events == []
    assert artifact.agent_events_response.count == 0
    assert artifact.agent_events_response.total == 0
    assert artifact.agent_events_response.resync_required is False
    dumped = artifact.model_dump(mode="json")
    assert "latency" not in dumped
    assert "winner" not in dumped
    assert "subjectivity" not in dumped


def test_collector_uses_only_subjective_evidence_endpoints() -> None:
    """Collection cannot read objective state, visibility, logs, or action APIs."""
    client, requests = _artifact_client(
        snapshot=_snapshot_payload(observation_cursor=7),
        frames=_frames_payload(start_cursor=7, frames=[]),
        agent_events=_agent_events_payload(events=[]),
    )
    collector = DirectCodexArtifactCollector("http://testserver", client=client)

    initial_snapshot = collector.capture_initial_snapshot("session-1")
    collector.collect(
        initial_snapshot=initial_snapshot,
        rotation=_rotation(),
        perspective=_perspective(),
        run_id="allowlist-test",
    )

    assert requests == [
        (
            "GET",
            "/ai/sessions/session-1/observation/snapshot",
            {},
        ),
        (
            "GET",
            "/ai/sessions/session-1/observation/frames",
            {"since": "7", "limit": "0"},
        ),
        (
            "GET",
            "/ai/sessions/session-1/agent-events",
            {"since": "0", "limit": "0"},
        ),
    ]
    forbidden_fragments = (
        "/state",
        "/visibility",
        "/available-actions",
        "/events/subscribe",
        "/combat-log",
    )
    assert all(
        fragment not in path
        for _method, path, _params in requests
        for fragment in forbidden_fragments
    )


def test_direct_validation_starter_captures_snapshot_before_returning() -> None:
    """Direct validation startup returns only after the bootstrap evidence exists."""
    client, requests = _direct_start_client(
        snapshot=_snapshot_payload(observation_cursor=12),
    )

    started = start_direct_codex_validation_run(
        "http://testserver",
        arena_id="double_door_dark_hunt",
        sequence=13,
        focus="skeleton_side",
        client=client,
    )

    assert started.rotation == DirectCodexRotationSlot(
        sequence=13,
        focus="skeleton_side",
        mode="codex_monsters",
        arena_id="double_door_dark_hunt",
    )
    assert started.perspective == DirectCodexPerspective(
        session_id="session-1",
        takeover_claim_id="claim-1",
        faction="monsters",
        controlled_entity_uuids=["hero-1"],
    )
    assert started.initial_snapshot.observation_cursor == 12
    assert requests == [
        ("GET", "/simulation/ai-validation-arenas", {}),
        (
            "POST",
            "/simulation/start-ai-validation",
            {"arena_id": "double_door_dark_hunt", "mode": "codex_monsters"},
        ),
        ("GET", "/ai/sessions/session-1/observation/snapshot", {}),
    ]


def test_direct_validation_starter_rejects_modes_without_codex_session() -> None:
    """A direct run context cannot be created without a Codex session id."""
    client, _requests = _direct_start_client(
        snapshot=_snapshot_payload(observation_cursor=12),
        start_payload={
            "status": "waiting_for_human",
            "arena_id": "double_door_dark_hunt",
            "mode": "human_hero",
            "ai_session_id": "ai-session",
        },
    )

    with pytest.raises(ValueError, match="did not create a Codex session"):
        start_direct_codex_validation_run(
            "http://testserver",
            arena_id="double_door_dark_hunt",
            sequence=13,
            focus="skeleton_side",
            mode="human_hero",
            client=client,
        )


def test_collector_rejects_malformed_subjective_payloads() -> None:
    """HTTP JSON is validated before it can become durable evidence."""
    client, _requests = _artifact_client(
        snapshot={"observation_cursor": 0},
        frames=_frames_payload(start_cursor=0, frames=[]),
        agent_events=_agent_events_payload(events=[]),
    )
    collector = DirectCodexArtifactCollector("http://testserver", client=client)

    with pytest.raises(ValidationError):
        collector.capture_initial_snapshot("session-1")


def test_direct_artifact_reader_migrates_only_known_pre_location_semantics() -> None:
    """Historical information and topology effects gain exact typed locations."""
    raw_artifact = _collect_artifact(run_id="legacy-information-effects").model_dump(mode="json")
    raw_artifact["initial_subjective_snapshot"]["current_epoch"] = _legacy_epoch_payload(
        scope_refs=(
            "selected_target.observation_frontier",
            "selected_object.far_side",
        ),
        topology_effects=(
            {
                "operation": "open",
                "subject_ref": "selected_object",
                "affects_movement": True,
                "affects_vision": True,
            },
            {
                "operation": "deactivate_hazard",
                "subject_ref": "selected_object.linked_hazard_region",
                "affects_hazards": True,
            },
        ),
    )

    loaded = DirectCodexRunArtifact.model_validate(raw_artifact)

    epoch = loaded.initial_subjective_snapshot.current_epoch
    assert epoch is not None
    semantics = next(iter(epoch.affordances.semantic_catalog.values()))
    assert [effect.anchor for effect in semantics.information_effects] == [
        WorldEffectAnchor.SELECTED_TARGET,
        WorldEffectAnchor.SELECTED_OBJECT,
    ]
    assert [effect.scope for effect in semantics.information_effects] == [
        WorldEffectScope.FRONTIER,
        WorldEffectScope.FRONTIER,
    ]
    assert [effect.certainty for effect in semantics.topology_effects] == [
        EffectCertainty.GUARANTEED,
        EffectCertainty.GUARANTEED,
    ]
    assert [effect.anchor for effect in semantics.topology_effects] == [
        WorldEffectAnchor.SELECTED_OBJECT,
        WorldEffectAnchor.SELECTED_OBJECT,
    ]
    assert [effect.scope for effect in semantics.topology_effects] == [
        WorldEffectScope.TARGET,
        WorldEffectScope.HAZARD_REGION,
    ]


def test_direct_artifact_reader_rejects_unknown_incomplete_information_effect() -> None:
    """Read compatibility cannot invent locations for unknown historical shapes."""
    raw_artifact = _collect_artifact(run_id="unknown-information-effect").model_dump(mode="json")
    raw_artifact["initial_subjective_snapshot"]["current_epoch"] = _legacy_epoch_payload(
        scope_refs=("selected_target.unrecognized_region",)
    )

    with pytest.raises(ValidationError):
        DirectCodexRunArtifact.model_validate(raw_artifact)


def test_direct_artifact_reader_rejects_unknown_incomplete_topology_effect() -> None:
    """Read compatibility cannot invent locations for unknown topology operations."""
    raw_artifact = _collect_artifact(run_id="unknown-topology-effect").model_dump(mode="json")
    raw_artifact["initial_subjective_snapshot"]["current_epoch"] = _legacy_epoch_payload(
        scope_refs=(),
        topology_effects=({"operation": "toggle", "subject_ref": "unknown"},),
    )

    with pytest.raises(ValidationError):
        DirectCodexRunArtifact.model_validate(raw_artifact)


def _collect_artifact(
    *,
    run_id: str,
    agent_events: dict[str, Any] | None = None,
) -> DirectCodexRunArtifact:
    """Collect one compact direct-run artifact through the real collector API."""
    client, _requests = _artifact_client(
        snapshot=_snapshot_payload(observation_cursor=0),
        frames=_frames_payload(start_cursor=0, frames=[]),
        agent_events=agent_events or _agent_events_payload(events=[]),
    )
    collector = DirectCodexArtifactCollector("http://testserver", client=client)
    initial_snapshot = collector.capture_initial_snapshot("session-1")
    return collector.collect(
        initial_snapshot=initial_snapshot,
        rotation=_rotation(),
        perspective=_perspective(),
        run_id=run_id,
    )


def _legacy_epoch_payload(
    *,
    scope_refs: tuple[str, ...],
    topology_effects: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    """Build a valid epoch carrying pre-anchor information-effect payloads."""
    return {
        "epoch_id": "legacy-epoch",
        "epoch_index": 1,
        "basis_observation_cursor": 0,
        "reason": "snapshot",
        "actor_uuid": "hero-1",
        "round_number": 1,
        "turn_index": 0,
        "economy": {"actor_uuid": "hero-1"},
        "affordances": {
            "actor_uuid": "hero-1",
            "computed_at_observation_cursor": 0,
            "semantic_catalog": {
                "legacy-information-semantics": {
                    "semantic_id": "legacy.information",
                    "information_effects": [
                        {
                            "operation": "reveal_frontier",
                            "certainty": "potential",
                            "scope_ref": scope_ref,
                        }
                        for scope_ref in scope_refs
                    ],
                    "topology_effects": list(topology_effects),
                }
            },
        },
    }


def _artifact_client(
    *,
    snapshot: dict[str, Any],
    frames: dict[str, Any],
    agent_events: dict[str, Any],
) -> tuple[httpx.Client, list[tuple[str, str, dict[str, str]]]]:
    """Create a recording HTTP client for the collector allowlist."""
    requests: list[tuple[str, str, dict[str, str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        requests.append((request.method, path, dict(request.url.params)))
        if path.endswith("/observation/snapshot"):
            return httpx.Response(200, json=snapshot)
        if path.endswith("/observation/frames"):
            return httpx.Response(200, json=frames)
        if path.endswith("/agent-events"):
            return httpx.Response(200, json=agent_events)
        return httpx.Response(500, json={"detail": f"unexpected endpoint: {path}"})

    return (
        httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="http://testserver",
        ),
        requests,
    )


def _direct_start_client(
    *,
    snapshot: dict[str, Any],
    start_payload: dict[str, Any] | None = None,
) -> tuple[httpx.Client, list[tuple[str, str, dict[str, str]]]]:
    """Create a recording HTTP client for direct validation startup."""
    requests: list[tuple[str, str, dict[str, str]]] = []
    payload = start_payload or {
        "status": "waiting_for_ai",
        "arena_id": "double_door_dark_hunt",
        "mode": "codex_monsters",
        "ai_session_id": "ai-session",
        "codex_session_id": "session-1",
        "takeover_claim_id": "claim-1",
        "encounter_uuid": "encounter-1",
        "hero_uuid": "hero-1",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        requests.append((request.method, path, dict(request.url.params)))
        if path == "/simulation/ai-validation-arenas":
            return httpx.Response(200, json={
                "arenas": [
                    {
                        "arena_id": "double_door_dark_hunt",
                        "title": "Double Door Dark Hunt",
                        "hero_role": "level 5 barbarian",
                        "tags": ["doors", "skeletons"],
                        "expected_pressure": [],
                        "map_notes": [],
                    }
                ]
            })
        if path == "/simulation/start-ai-validation":
            return httpx.Response(200, json=payload)
        if path == "/ai/sessions/session-1/observation/snapshot":
            return httpx.Response(200, json=snapshot)
        return httpx.Response(500, json={"detail": f"unexpected endpoint: {path}"})

    return (
        httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="http://testserver",
        ),
        requests,
    )


def _snapshot_payload(*, observation_cursor: int) -> dict[str, Any]:
    """Build one valid subjective snapshot payload."""
    return {
        "observation_cursor": observation_cursor,
        "source_event_cursor": 11,
        "source_combat_log_cursor": 2,
        "session": {
            "session_id": "session-1",
            "player_type": "codex",
            "name": "Codex Hero",
            "connection_status": "connected",
            "controlled_entity_uuids": ["hero-1"],
            "active_entity_uuid": "hero-1",
            "active_entity_name": "Barbarian",
            "is_my_turn": True,
        },
        "observers": [],
        "known_entities": [],
        "known_objects": [],
        "known_tiles": [],
        "combat_logs": [],
    }


def _frames_payload(
    *,
    start_cursor: int,
    frames: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a complete frame-history response after the bootstrap cursor."""
    rows = frames
    if rows is None:
        rows = [
            {
                "observation_cursor": start_cursor + 1,
                "frame_type": "command_result",
                "source_kind": "controller_command",
                "source_command_id": "command-1",
                "command_result": {
                    "status": "accepted",
                    "command_id": "command-1",
                    "session_id": "session-1",
                    "actor_uuid": "hero-1",
                    "requested_epoch_id": "epoch-1",
                    "current_epoch_id": "epoch-1",
                    "row_id": "self|Rage|index=0",
                    "message": "accepted",
                    "payload": {"action": "Rage", "accepted": True},
                    "accepted_at_observation_cursor": start_cursor + 1,
                },
            }
        ]
    next_cursor = rows[-1]["observation_cursor"] if rows else start_cursor
    return {
        "frames": rows,
        "count": len(rows),
        "total": start_cursor + len(rows),
        "next_observation_cursor": next_cursor,
    }


def _agent_events_payload(
    *,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a complete retained agent-event response."""
    rows = events
    if rows is None:
        rows = [
            {
                "event_index": 0,
                "agent_cursor": 1,
                "observation_cursor": 4,
                "epoch_id": "epoch-1",
                "event": {
                    "event_id": "agent-event-1",
                    "session_id": "session-1",
                    "actor_uuid": "hero-1",
                    "epoch_id": "epoch-1",
                    "observation_cursor": 4,
                    "event_type": "policy.selected",
                    "level": "info",
                    "source": "codex",
                    "summary": "Selected Rage.",
                    "payload": {"row_id": "self|Rage|index=0"},
                    "tags": ["decision"],
                    "created_at": 1.0,
                },
            }
        ]
    return {
        "events": rows,
        "count": len(rows),
        "total": len(rows),
        "next_agent_cursor": len(rows),
        "earliest_agent_cursor": 1 if rows else 0,
        "resync_required": False,
    }


def _rotation() -> DirectCodexRotationSlot:
    """Return the compact rotation identity used by helper tests."""
    return DirectCodexRotationSlot(
        sequence=1,
        focus="barbarian_hero",
        mode="codex_hero",
        arena_id="double_door_dark_hunt",
    )


def _perspective() -> DirectCodexPerspective:
    """Return the direct Codex session perspective used by helper tests."""
    return DirectCodexPerspective(
        session_id="session-1",
        takeover_claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=["hero-1"],
    )
