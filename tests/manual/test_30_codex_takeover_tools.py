"""Runtime Codex takeover and typed tool contracts."""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from ai.codex_tools.client import find_choice, normalize_actions
from dnd.controller import CodexController
from dnd.entity import Entity
from server import event_server
from server.arena_mode import reset_standard_arena_runtime
from server.session import PlayerType


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
    assert start_response.json()["monster_ai"] == "external"
    assert takeover_response.status_code == 200
    assert claim["session_id"]
    assert {row["entity_name"] for row in claim["claimed_entities"]} == {
        "Skeleton Warrior",
        "Skeleton Archer",
        "Skeleton Warlock",
    }
    assert {row["previous_controller_type"] for row in claim["claimed_entities"]} == {"external_ai"}
    assert {row["current_controller_type"] for row in claim["claimed_entities"]} == {"codex"}
    assert advance_response.status_code == 200
    assert advance_response.json()["status"] == "waiting_for_codex"


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

    assert release_response.status_code == 200
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
    assert len(codex_sessions) == 1
    assert codex_sessions[0]["controlled_entities"] == []


def test_codex_takeover_conflict_and_force_replace() -> None:
    """Overlapping live claims require force to replace."""
    reset_standard_arena_runtime()
    client = TestClient(event_server.app)

    client.post("/simulation/start-human", params={"character_class": "fighter"})
    first = client.post("/ai/takeover", json={"faction": "monsters"}).json()
    conflict_response = client.post("/ai/takeover", json={"faction": "monsters"})
    forced_response = client.post("/ai/takeover", json={"faction": "monsters", "force": True})
    active_claims = client.get("/ai/takeover").json()["claims"]

    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"]["code"] == "takeover_conflict"
    assert forced_response.status_code == 200
    assert forced_response.json()["claim_id"] != first["claim_id"]
    assert [claim["claim_id"] for claim in active_claims] == [forced_response.json()["claim_id"]]


def test_expired_takeover_restores_before_advancement() -> None:
    """Expired Codex claims restore the external AI controller before advancement."""
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
    advance_response = client.post(
        "/action/end-turn",
        json={"session_id": human_session, "entity_uuid": start["hero_uuid"]},
    )

    assert advance_response.status_code == 200
    assert advance_response.json()["status"] == "waiting_for_ai"
    assert client.get("/ai/takeover").json()["claims"] == []


def test_takeover_can_reuse_existing_codex_session() -> None:
    """A caller can attach takeover to an existing Codex session."""
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
    game_status = client.get("/game/status").json()
    session_row = next(
        session for session in game_status["sessions"]
        if session["session_id"] == codex_session["session_id"]
    )

    assert claim["session_id"] == codex_session["session_id"]
    assert session_row["player_type"] == PlayerType.CODEX.value
    assert len(session_row["controlled_entities"]) == 3


def test_codex_tool_action_row_ids_are_resolvable() -> None:
    """Tool action row ids preserve enough data to execute fresh rows."""
    payload = {
        "basis_cursor": 12,
        "computed_at_observation_cursor": 13,
        "entity_actions": [
            {
                "template_name": "Attack_RANGED_MAIN",
                "display_name": "Shortbow",
                "action_category": "attack",
                "target_type": "entity",
                "can_afford": True,
                "valid_targets": [
                    {"index": 0, "target_uuid": "hero-uuid", "target_name": "Hero", "distance": 30}
                ],
            }
        ],
        "position_actions": [
            {
                "template_name": "Move",
                "display_name": "Move",
                "action_category": "movement",
                "target_type": "position_path",
                "can_afford": True,
                "valid_targets": [
                    {"index": 4, "position": [8, 7], "distance": 20}
                ],
            }
        ],
        "self_actions": [],
        "object_actions": [],
    }

    actions = normalize_actions("session", "actor", payload)
    attack = find_choice(actions, "entity_actions|Attack_RANGED_MAIN|uuid=hero-uuid")
    movement = find_choice(actions, "position_actions|Move|pos=8,7")

    assert actions.raw_counts == {
        "entity_actions": 1,
        "position_actions": 1,
        "self_actions": 0,
        "object_actions": 0,
    }
    assert attack is not None
    assert attack.target.target_index == 0
    assert movement is not None
    assert movement.target.target_index == 4


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
