"""Takeover leases supporting the persistent Codex runtime."""

from __future__ import annotations

from collections.abc import Generator
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from ai.codex_tools import commands as codex_commands
from ai.codex_tools.client import CodexToolClient, CodexToolHTTPError
from ai.observation import (
    ObservationFrame,
    apply_observation_frame,
    materialize_snapshot,
)
from ai.protocol.control import DecisionEpoch
from dnd.controller import CodexController
from dnd.core.events import EventPhase, SensoryUpdateEvent, SensoryUpdateReason
from dnd.entity import Entity
from server import event_server
from server.arena_mode import reset_standard_arena_runtime
from server.session import PlayerType
from tests.manual.test_28_subjective_observation_stream import complete_event, create_observation_game


@pytest.fixture(autouse=True)
def stop_test_external_ai_processes() -> Generator[None, None, None]:
    """Stop external agents started against the in-process test server."""
    yield
    event_server.ai_process_manager.stop_all()


def test_codex_takeover_claims_monsters_and_stops_at_codex_turn() -> None:
    """Codex can claim normal-AI monsters during the human turn."""
    reset_standard_arena_runtime()
    client = TestClient(event_server.app)

    start_response = client.post("/simulation/start-human", params={"character_class": "fighter"})
    takeover_response = client.post("/ai/takeover", json={"faction": "monsters"})
    claim = takeover_response.json()
    hero_uuid = start_response.json()["hero_uuid"]
    human_session = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Arena Player"},
    ).json()["session_id"]
    client.post("/game/join", json={"session_id": human_session, "entity_uuids": [hero_uuid]})
    advance_response = client.post(
        "/action/end-turn",
        json={"session_id": human_session, "entity_uuid": hero_uuid},
    )

    assert start_response.status_code == 200
    assert takeover_response.status_code == 200
    assert {row["entity_name"] for row in claim["claimed_entities"]} == {
        "Skeleton Warrior",
        "Skeleton Archer",
        "Skeleton Warlock",
    }
    assert {row["previous_controller_type"] for row in claim["claimed_entities"]} == {"external_ai"}
    assert {row["current_controller_type"] for row in claim["claimed_entities"]} == {"codex"}
    assert advance_response.json()["status"] == "waiting_for_codex"


def test_explicit_entity_takeover_reports_the_claimed_entity_faction() -> None:
    """Explicit hero ownership cannot retain the request model's monster default."""
    reset_standard_arena_runtime()
    client = TestClient(event_server.app)
    start = client.post(
        "/simulation/start-human",
        params={"character_class": "sorcerer"},
    ).json()

    response = client.post(
        "/ai/takeover",
        json={"entity_uuids": [start["hero_uuid"]]},
    )

    assert response.status_code == 200
    claim = response.json()
    assert claim["faction"] == "heroes"
    assert [row["faction"] for row in claim["claimed_entities"]] == ["heroes"]


def test_codex_takeover_release_restores_normal_ai() -> None:
    """Releasing a claim restores previous controllers and ownership."""
    reset_standard_arena_runtime()
    client = TestClient(event_server.app)

    client.post("/simulation/start-human", params={"character_class": "fighter"})
    claim = client.post("/ai/takeover", json={"faction": "monsters"}).json()
    release_response = client.post(f"/ai/takeover/{claim['claim_id']}/release")
    released = release_response.json()["claim"]
    game_status = client.get("/game/status").json()
    ai_sessions = [session for session in game_status["sessions"] if session["player_type"] == "ai"]
    codex_sessions = [session for session in game_status["sessions"] if session["player_type"] == "codex"]
    encounter = event_server.sim.encounter

    assert release_response.json()["status"] == "released"
    assert {row["current_controller_type"] for row in released["claimed_entities"]} == {"external_ai"}
    assert encounter is not None
    restored_controller_types: set[str] = set()
    for entity in Entity.get_all_entities():
        if entity.faction != "monsters":
            continue
        controller = encounter.get_controller_for(entity.uuid)
        assert controller is not None
        restored_controller_types.add(controller.controller_type)
    assert restored_controller_types == {"external_ai"}
    assert len(ai_sessions) == 1
    assert len(ai_sessions[0]["controlled_entities"]) == 3
    assert codex_sessions[0]["controlled_entities"] == []


def test_takeover_release_preserves_subjective_history_and_appends_state_transition() -> None:
    """Releasing ownership appends state without rewriting prior subjective frames."""
    client, _hero_session_id, _hero, monster, _encounter = create_observation_game()
    claim = client.post("/ai/takeover", json={"faction": "monsters"}).json()
    session_id = claim["session_id"]
    snapshot_payload = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()

    complete_event(SensoryUpdateEvent(
        source_entity_uuid=monster.uuid,
        target_entity_uuid=monster.uuid,
        observer_uuid=monster.uuid,
        cause_event_uuid=UUID("00000000-0000-0000-0000-000000000301"),
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(3, 3)],
        seen_cells_added=[(3, 3)],
        phase=EventPhase.DECLARATION,
    ))
    before_release = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": 0, "limit": 0},
    ).json()["frames"]
    before_models = [ObservationFrame.model_validate(frame) for frame in before_release]

    client.post(f"/ai/takeover/{claim['claim_id']}/release")
    after_release = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": 0, "limit": 0},
    ).json()["frames"]

    assert [ObservationFrame.model_validate(frame) for frame in after_release[:len(before_release)]] == before_models
    appended = after_release[len(before_release):]
    assert appended
    assert [frame["observation_cursor"] for frame in after_release] == list(range(1, len(after_release) + 1))
    assert any(
        frame["source_kind"] == "session_control"
        and frame["state_replacement"]["session"]["controlled_entity_uuids"] == []
        for frame in appended
    )

    replayed = materialize_snapshot(snapshot_payload)
    for frame in after_release:
        replayed = apply_observation_frame(replayed, frame)
    fresh = materialize_snapshot(client.get(f"/ai/sessions/{session_id}/observation/snapshot").json())
    assert replayed.session == fresh.session
    assert replayed.encounter == fresh.encounter
    assert replayed.observers == fresh.observers
    assert replayed.known_entities == fresh.known_entities
    assert replayed.known_objects == fresh.known_objects
    assert replayed.known_tiles == fresh.known_tiles


def test_codex_takeover_conflict_and_force_replace() -> None:
    """Overlapping live claims require force to replace."""
    reset_standard_arena_runtime()
    client = TestClient(event_server.app)
    client.post("/simulation/start-human", params={"character_class": "fighter"})

    first = client.post("/ai/takeover", json={"faction": "monsters"}).json()
    conflict = client.post("/ai/takeover", json={"faction": "monsters"})
    forced = client.post("/ai/takeover", json={"faction": "monsters", "force": True})

    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "takeover_conflict"
    assert forced.json()["claim_id"] != first["claim_id"]
    assert [row["claim_id"] for row in client.get("/ai/takeover").json()["claims"]] == [
        forced.json()["claim_id"]
    ]


def test_policy_source_endpoint_returns_hashable_shared_policy() -> None:
    """The server exposes the exact shared policy source for observability."""
    payload = TestClient(event_server.app).get("/ai/policy/source").json()

    assert payload["policy_name"] == "shared_subjective_hierarchical_policy"
    assert len(payload["source_sha256"]) == 64
    assert payload["line_count"] > 1_000
    assert "class PolicyHost" in payload["source"]
    assert "def evaluate_default_policy" in payload["source"]
    assert all(not path.startswith("ai/external/") for path in payload["source_paths"])


def test_ai_command_advances_when_accepted_action_ends_actor_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stopped actor does not remain the active controlled turn."""
    client, session_id, hero, _monster, _encounter = create_observation_game(second_hero=True)
    ally = next(entity for entity in Entity.get_all_entities() if entity.name == "Observation Ally")
    epoch = DecisionEpoch.model_validate(
        client.get(
            f"/ai/sessions/{session_id}/observation/snapshot"
        ).json()["current_epoch"]
    )
    row = next(row for row in epoch.affordances.position_actions if row.can_afford)

    async def fake_execute_action_by_index(_request: object) -> event_server.ActionResult:
        return event_server.ActionResult(
            success=True,
            message="Actor cannot continue.",
            event_type="test_action",
            entity_hp=0,
            turn_continues=False,
            encounter_ended=False,
        )

    monkeypatch.setattr(event_server, "execute_action_by_index", fake_execute_action_by_index)
    response = client.post(
        f"/ai/sessions/{session_id}/commands/execute",
        json={
            "actor_uuid": str(hero.uuid),
            "basis_epoch_id": epoch.epoch_id,
            "row_id": row.row_id,
        },
    )
    follow_up = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()

    assert response.json()["status"] == "accepted"
    assert response.json()["payload"]["turn_continues"] is False
    assert follow_up["session"]["active_entity_uuid"] == str(ally.uuid)
    assert follow_up["current_epoch"]["actor_uuid"] == str(ally.uuid)


def test_expired_takeover_restores_before_advancement() -> None:
    """Expired claims restore the external AI before encounter advancement."""
    reset_standard_arena_runtime()
    client = TestClient(event_server.app)
    start = client.post("/simulation/start-human", params={"character_class": "fighter"}).json()
    claim = client.post("/ai/takeover", json={"faction": "monsters", "lease_seconds": 0.001}).json()
    stored_claim = event_server.ai_takeover_manager.get_claim(UUID(claim["claim_id"]))
    assert stored_claim is not None
    stored_claim.last_heartbeat_at -= 10.0
    human_session = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Arena Player"},
    ).json()["session_id"]
    client.post("/game/join", json={"session_id": human_session, "entity_uuids": [start["hero_uuid"]]})
    advanced = client.post(
        "/action/end-turn",
        json={"session_id": human_session, "entity_uuid": start["hero_uuid"]},
    )

    assert advanced.json()["status"] == "waiting_for_ai"
    assert client.get("/ai/takeover").json()["claims"] == []


def test_takeover_can_reuse_existing_codex_session() -> None:
    """A takeover may bind to an existing Codex session."""
    reset_standard_arena_runtime()
    client = TestClient(event_server.app)
    client.post("/simulation/start-human", params={"character_class": "fighter"})
    codex_session = client.post(
        "/session/create",
        json={"player_type": "codex", "name": "Hot Codex"},
    ).json()
    claim = client.post(
        "/ai/takeover",
        json={"faction": "monsters", "session_id": codex_session["session_id"]},
    ).json()
    session_row = next(
        session for session in client.get("/game/status").json()["sessions"]
        if session["session_id"] == codex_session["session_id"]
    )

    assert claim["session_id"] == codex_session["session_id"]
    assert session_row["player_type"] == PlayerType.CODEX.value
    assert len(session_row["controlled_entities"]) == 3


def test_takeover_transport_wraps_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lease transport failures become structured errors."""
    client = CodexToolClient("http://127.0.0.1:8765")

    def fail_request(method: str, path: str, **kwargs: object) -> httpx.Response:
        request = httpx.Request(method, f"http://127.0.0.1:8765{path}")
        raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(client.client, "request", fail_request)
    try:
        with pytest.raises(CodexToolHTTPError) as exc_info:
            client.release("claim")
    finally:
        client.close()

    assert exc_info.value.error.code == "request_error"
    assert exc_info.value.error.detail == {"method": "POST", "path": "/ai/takeover/claim/release"}


def test_takeover_transport_adopts_existing_claim_through_heartbeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exact claim adoption renews ownership without creating another claim."""
    client = CodexToolClient("http://127.0.0.1:8765")
    requests: list[tuple[str, str]] = []

    def fake_request(method: str, path: str, **_kwargs: object) -> dict[str, object]:
        requests.append((method, path))
        return {"status": "heartbeat", "claim": _typed_takeover_claim_payload()}

    monkeypatch.setattr(client, "_request", fake_request)
    try:
        adopted = client.resolve_control_claim(claim_id="claim-1", session_id="codex-session")
    finally:
        client.close()

    assert adopted.claim_id == "claim-1"
    assert adopted.session_id == "codex-session"
    assert requests == [("POST", "/ai/takeover/claim-1/heartbeat")]


def test_takeover_transport_rejects_claim_session_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """A supplied session ID strictly identifies the adopted claim."""
    client = CodexToolClient("http://127.0.0.1:8765")
    monkeypatch.setattr(
        client,
        "_request",
        lambda *_args, **_kwargs: {"status": "heartbeat", "claim": _typed_takeover_claim_payload()},
    )
    try:
        with pytest.raises(CodexToolHTTPError) as error:
            client.resolve_control_claim(claim_id="claim-1", session_id="different-session")
    finally:
        client.close()

    assert error.value.error.code == "takeover_claim_session_mismatch"
    assert error.value.error.status_code == 409


def test_codex_cli_separates_takeover_transport_from_typed_hot_runtime_commands() -> None:
    """CLI reads target the persistent local runtime, never snapshot polling."""
    command_names = {
        command.name or command.callback.__name__.replace("_", "-")
        for command in codex_commands.app.registered_commands
        if command.callback is not None
    }

    assert command_names == {
        "heartbeat",
        "hot-end-turn",
        "hot-execute",
        "hot-export",
        "hot-geometry",
        "hot-get",
        "hot-oracle",
        "hot-release",
        "hot-representation",
        "hot-search",
        "hot-serve",
        "hot-turn",
        "hot-watch",
        "release",
        "takeover",
    }
    for removed_name in ("attach", "brief", "actions", "turn", "execute", "end_turn", "watch"):
        assert not hasattr(CodexToolClient, removed_name)


def test_takeover_assigns_codex_controllers_in_registry() -> None:
    """Claimed monsters point at CodexController instances."""
    reset_standard_arena_runtime()
    client = TestClient(event_server.app)
    client.post("/simulation/start-human", params={"character_class": "fighter"})
    client.post("/ai/takeover", json={"faction": "monsters"})
    encounter = event_server.sim.encounter
    assert encounter is not None

    controllers = [
        encounter.get_controller_for(entity.uuid)
        for entity in Entity.get_all_entities()
        if entity.faction == "monsters"
    ]
    assert all(isinstance(controller, CodexController) for controller in controllers)


def _typed_takeover_claim_payload() -> dict[str, object]:
    """Build one complete server-shaped takeover claim for transport tests."""
    return {
        "claim_id": "claim-1",
        "session_id": "codex-session",
        "name": "Codex Validation Monsters",
        "faction": "monsters",
        "created_at": 10.0,
        "last_heartbeat_at": 11.0,
        "lease_seconds": 600.0,
        "expires_at": 611.0,
        "is_expired": False,
        "claimed_entities": [{
            "entity_uuid": "monster-1",
            "entity_name": "Monster",
            "faction": "monsters",
            "previous_controller_uuid": "controller-1",
            "previous_controller_type": "external_ai",
            "current_controller_type": "codex",
            "previous_owner_session_id": "ai-session",
        }],
    }
