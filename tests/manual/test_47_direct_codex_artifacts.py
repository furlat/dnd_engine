"""Truthful durable evidence for direct Codex-controlled runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from ai.codex_tools.artifacts import (
    DirectCodexArtifactCollector,
    DirectCodexFrictionCategory,
    DirectCodexFrictionAnnotation,
    DirectCodexPerspective,
    DirectCodexRotationSlot,
    DirectCodexRunArtifact,
    start_direct_codex_run,
    write_direct_codex_run_artifact,
)
from ai.codex_tools.direct_game import DirectCodexGameStart
from dnd.ai.contracts.semantics import EffectCertainty, WorldEffectAnchor, WorldEffectScope
from dnd.scenarios.encounter_catalog import (
    encounter_recipe,
)


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
            mode="codex_roster",
            encounter_id="encounter.double_door_dark_hunt",
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


def test_v1_arena_identity_migrates_to_exact_encounter_identity() -> None:
    artifact = _collect_artifact(run_id="legacy-arena-identity")
    payload = artifact.model_dump(mode="json")
    payload["schema_version"] = 1
    payload["rotation"]["arena_id"] = "double_door_dark_hunt"
    del payload["rotation"]["encounter_id"]

    migrated = DirectCodexRunArtifact.model_validate(payload)

    assert migrated.schema_version == 2
    assert (
        migrated.rotation.encounter_id
        == "encounter.double_door_dark_hunt"
    )


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


def test_direct_codex_starter_captures_snapshot_before_returning() -> None:
    """Direct Codex startup returns only after bootstrap evidence exists."""
    client, requests = _direct_start_client(
        snapshot=_snapshot_payload(observation_cursor=12),
    )
    rotation = DirectCodexRotationSlot(
        sequence=13,
        focus="skeleton_side",
        mode="codex_roster",
        encounter_id="encounter.double_door_dark_hunt",
    )

    started = start_direct_codex_run(
        "http://testserver",
        rotation=rotation,
        client=client,
    )

    assert started.start_result == DirectCodexGameStart(
        activation_status="activated",
        encounter_id="encounter.double_door_dark_hunt",
        encounter_uuid="encounter-1",
        game_id="game-1",
        session_id="session-1",
        takeover_claim_id="claim-1",
        controlled_entity_uuids=("hero-1",),
    )
    assert started.rotation == rotation
    assert started.perspective == DirectCodexPerspective(
        session_id="session-1",
        takeover_claim_id="claim-1",
        faction="monsters",
        controlled_entity_uuids=["hero-1"],
    )
    assert started.initial_snapshot.observation_cursor == 12
    assert requests == [
        ("GET", "/game-creation/catalog", {}),
        ("POST", "/game-creation/compose", {}),
        (
            "POST",
            "/game-creation/start",
            {},
        ),
        ("POST", "/game/join", {}),
        ("GET", "/replication/bootstrap", {"session_id": "session-1"}),
        ("POST", "/game-creation/activate", {}),
        ("GET", "/ai/sessions/session-1/observation/snapshot", {}),
    ]


def test_direct_codex_starter_requires_complete_codex_assignment() -> None:
    """A direct run cannot begin without exact Codex authority."""
    client, _requests = _direct_start_client(
        snapshot=_snapshot_payload(observation_cursor=12),
        start_payload=_prepared_direct_payload(codex=False),
    )

    with pytest.raises(ValueError, match="complete Codex assignment"):
        start_direct_codex_run(
            "http://testserver",
            rotation=DirectCodexRotationSlot(
                sequence=13,
                focus="skeleton_side",
                mode="codex_roster",
                encounter_id="encounter.double_door_dark_hunt",
            ),
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
    """Create a recording HTTP client for direct Codex startup."""
    requests: list[tuple[str, str, dict[str, str]]] = []
    payload = start_payload or _prepared_direct_payload(codex=True)
    recipe = encounter_recipe(
        "encounter.double_door_dark_hunt",
    )
    content_digest = "3" * 64
    ruleset_digest = "4" * 64

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        requests.append((request.method, path, dict(request.url.params)))
        if path == "/game-creation/catalog":
            return httpx.Response(200, json={
                "schema_version": 3,
                "encounter_recipes": [
                    recipe.model_dump(mode="json"),
                ],
            })
        if path == "/game-creation/compose":
            body = json.loads(request.content)
            assert [
                slot["controller_defaults"]["controller"]
                for slot in body["roster_slots"]
            ] == ["ai", "codex"]
            return httpx.Response(200, json={
                "schema_version": 1,
                "content_set_digest": content_digest,
                "ruleset_digest": ruleset_digest,
                "recipe": recipe.model_dump(mode="json"),
            })
        if path == "/game-creation/start":
            body = json.loads(request.content)
            assert body == {
                "expected_content_set_digest": content_digest,
                "expected_ruleset_digest": ruleset_digest,
                "recipe": recipe.model_dump(mode="json"),
            }
            return httpx.Response(200, json=payload)
        if path == "/game/join":
            body = json.loads(request.content)
            assert body == {
                "session_id": "session-1",
                "entity_uuids": ["hero-1"],
            }
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "game_id": "game-1",
                    "session_id": body["session_id"],
                    "controlled_entities": body["entity_uuids"],
                },
            )
        if path == "/replication/bootstrap":
            return httpx.Response(
                200,
                json={
                    "protocol": {
                        "source_stream_id": "source-stream",
                        "generation_id": "generation",
                    },
                    "perspective": {
                        "perspective_epoch_id": "perspective-epoch",
                    },
                },
            )
        if path == "/game-creation/activate":
            body = json.loads(request.content)
            assert body == {
                "session_id": "session-1",
                "expected_source_stream_id": "source-stream",
                "expected_generation_id": "generation",
                "expected_perspective_epoch_id": "perspective-epoch",
            }
            return httpx.Response(200, json={
                "status": "activated",
                "game_id": "game-1",
                "encounter_uuid": "encounter-1",
            })
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


def _prepared_direct_payload(*, codex: bool) -> dict[str, Any]:
    """Return exact roster results for one direct-start transport fixture."""
    recipe = encounter_recipe(
        "encounter.double_door_dark_hunt",
    )
    rosters = []
    for roster_index, roster_slot in enumerate(recipe.roster_slots):
        controller = (
            "codex"
            if codex and roster_index == 1
            else "ai"
        )
        assignments = []
        for member_index, _member in enumerate(
            roster_slot.roster.members,
        ):
            assignment: dict[str, Any] = {
                "entity_uuid": (
                    "hero-1"
                    if controller == "codex" and member_index == 0
                    else f"entity-{roster_index}-{member_index}"
                ),
                "controller": controller,
            }
            if controller == "codex":
                assignment.update({
                    "codex_session_id": (
                        "session-1"
                        if member_index == 0
                        else f"session-{member_index + 1}"
                    ),
                    "takeover_claim_id": (
                        "claim-1"
                        if member_index == 0
                        else f"claim-{member_index + 1}"
                    ),
                })
            assignments.append(assignment)
        rosters.append({
            "roster_slot_id": roster_slot.roster_slot_id,
            "entity_assignments": assignments,
        })
    return {
        "schema_version": 2,
        "status": "prepared",
        "recipe_digest": recipe.recipe_digest,
        "encounter_uuid": "encounter-1",
        "game_id": "game-1",
        "rosters": rosters,
    }


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
        mode="codex_roster",
        encounter_id="encounter.double_door_dark_hunt",
    )


def _perspective() -> DirectCodexPerspective:
    """Return the direct Codex session perspective used by helper tests."""
    return DirectCodexPerspective(
        session_id="session-1",
        takeover_claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=["hero-1"],
    )
