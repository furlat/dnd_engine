"""Focused integration checks for the external shared-policy subprocess."""

import json

from ai.knowledge import derive_agent_facts
from ai.observation import materialize_snapshot
from ai.policy import PolicyGoal, PolicyHost
from dnd.entity import Entity
from server import event_server
from server.arena_mode import ArenaApiClient, reset_standard_arena_runtime


def _move_target_index(actions_payload: dict[str, object], position: tuple[int, int]) -> int:
    """Return the public Move target index for one grid position."""
    for action in actions_payload.get("position_actions", []):  # type: ignore[union-attr]
        if not isinstance(action, dict) or action.get("template_name") != "Move":
            continue
        for target in action.get("valid_targets", []):
            if isinstance(target, dict) and tuple(target.get("position") or ()) == position:
                return int(target["index"])
    raise AssertionError(f"Move target {position} was not present")


def test_start_human_creates_ai_session_and_spawns_once(monkeypatch) -> None:
    """The human arena assigns all monsters to one shared-policy subprocess."""
    reset_standard_arena_runtime()
    starts: list[tuple[str, str]] = []

    def fake_start_external_agent(session_id, base_url: str) -> None:
        starts.append((str(session_id), base_url))

    monkeypatch.setattr(
        event_server.ai_process_manager,
        "start_external_agent",
        fake_start_external_agent,
    )

    client = ArenaApiClient()
    response = client.post(
        "/simulation/start-human",
        params={"character_class": "fighter"},
    )
    payload = response.json()
    game_status = client.get("/game/status").json()
    monsters = [entity for entity in Entity.get_all_entities() if entity.faction == "monsters"]
    encounter = event_server.sim.encounter
    assert encounter is not None
    controller_types = {
        controller.controller_type
        for monster in monsters
        for controller in [encounter.get_controller_for(monster.uuid)]
        if controller is not None
    }
    ai_sessions = [session for session in game_status["sessions"] if session["player_type"] == "ai"]

    assert response.status_code == 200
    assert payload["status"] == "waiting_for_human"
    assert payload["entity_uuid"] == payload["hero_uuid"]
    assert payload["ai_session_id"] == starts[0][0]
    assert starts == [(payload["ai_session_id"], "http://testserver")]
    assert controller_types == {"external_ai"}
    assert len(ai_sessions) == 1
    assert ai_sessions[0]["name"] == "AI Monsters"
    assert len(ai_sessions[0]["controlled_entities"]) == 3

def test_pre_contact_side_move_does_not_create_monster_target_pressure(monkeypatch) -> None:
    """The streamed epoch and shared policy remain strictly session-subjective."""
    reset_standard_arena_runtime()
    monkeypatch.setattr(
        event_server.ai_process_manager,
        "start_external_agent",
        lambda _session_id, _base_url: None,
    )

    client = ArenaApiClient()
    start = client.post("/simulation/start-human", params={"character_class": "sorcerer"})
    assert start.status_code == 200
    start_payload = start.json()
    hero_uuid = start_payload["hero_uuid"]
    monster_session_id = start_payload["ai_session_id"]
    bootstrap = client.get(f"/ai/sessions/{monster_session_id}/observation/snapshot")
    assert bootstrap.status_code == 200
    bootstrap_cursor = bootstrap.json()["observation_cursor"]
    bootstrap_text = json.dumps(bootstrap.json())
    assert str(hero_uuid) not in bootstrap_text
    assert "Hero" not in bootstrap_text

    session = client.post("/session/create", json={"player_type": "human", "name": "Arena Player"})
    assert session.status_code == 200
    hero_session_id = session.json()["session_id"]
    join = client.post(
        "/game/join",
        json={"session_id": hero_session_id, "entity_uuids": [hero_uuid]},
    )
    assert join.status_code == 200

    hero_actions = client.get(f"/entity/{hero_uuid}/available-actions")
    assert hero_actions.status_code == 200
    side_move_index = _move_target_index(hero_actions.json(), (2, 8))
    move = client.post(
        "/action/execute",
        json={
            "session_id": hero_session_id,
            "entity_uuid": hero_uuid,
            "template_name": "Move",
            "target_index": side_move_index,
        },
    )
    assert move.status_code == 200
    end_turn = client.post(
        "/action/end-turn",
        json={"session_id": hero_session_id, "entity_uuid": hero_uuid},
    )
    assert end_turn.status_code == 200

    frames = client.get(
        f"/ai/sessions/{monster_session_id}/observation/frames",
        params={"since": bootstrap_cursor, "limit": 200},
    )
    assert frames.status_code == 200
    stream_text = json.dumps(frames.json())
    assert str(hero_uuid) not in stream_text
    assert "Hero" not in stream_text

    snapshot_response = client.get(f"/ai/sessions/{monster_session_id}/observation/snapshot")
    assert snapshot_response.status_code == 200
    snapshot_text = json.dumps(snapshot_response.json())
    assert str(hero_uuid) not in snapshot_text
    assert "Hero" not in snapshot_text
    world = materialize_snapshot(snapshot_response.json())
    facts = derive_agent_facts(world).facts
    decision = PolicyHost().decide(world, facts=facts)

    assert facts.contacts.visible_hostile_uuids == tuple()
    assert facts.contacts.remembered_hostile_uuids == tuple()
    assert decision.selected.goal not in {
        PolicyGoal.DIRECT_PRESSURE,
        PolicyGoal.HOSTILE_CONTROL,
    }


def test_start_codex_monsters_mode_spawns_shared_policy_hero(monkeypatch) -> None:
    """Codex-monsters mode assigns the hero to the same external policy stack."""
    reset_standard_arena_runtime()
    starts: list[tuple[str, str]] = []

    def fake_start_external_agent(session_id, base_url: str) -> None:
        starts.append((str(session_id), base_url))

    monkeypatch.setattr(
        event_server.ai_process_manager,
        "start_external_agent",
        fake_start_external_agent,
    )

    client = ArenaApiClient()
    response = client.post("/simulation/start-codex-monsters", params={"character_class": "fighter"})
    payload = response.json()
    game_status = client.get("/game/status").json()
    encounter = event_server.sim.encounter
    assert encounter is not None
    hero = next(entity for entity in Entity.get_all_entities() if entity.faction == "heroes")
    monsters = [entity for entity in Entity.get_all_entities() if entity.faction == "monsters"]
    hero_controller = encounter.get_controller_for(hero.uuid)
    monster_controller_types = {
        controller.controller_type
        for monster in monsters
        for controller in [encounter.get_controller_for(monster.uuid)]
        if controller is not None
    }
    ai_sessions = [session for session in game_status["sessions"] if session["player_type"] == "ai"]

    assert response.status_code == 200
    assert payload["mode"] == "codex_monsters"
    assert starts == [(payload["hero_ai_session_id"], "http://testserver")]
    assert hero_controller is not None
    assert hero_controller.controller_type == "external_ai"
    assert monster_controller_types == {"codex"}
    assert len(payload["monsters"]) == 3
    assert len(ai_sessions) == 1
    assert ai_sessions[0]["name"] == "AI Hero"
    assert ai_sessions[0]["controlled_entities"] == [str(hero.uuid)]


def test_ai_process_diagnostics_and_reset_cleanup(monkeypatch) -> None:
    """Process diagnostics remain exposed and reset stops tracked subprocesses."""
    reset_standard_arena_runtime()
    stop_calls: list[str] = []
    monkeypatch.setattr(
        event_server.ai_process_manager,
        "stop_all",
        lambda: stop_calls.append("stop"),
    )

    client = ArenaApiClient()
    status_response = client.get("/ai/processes")
    reset_response = client.post("/simulation/reset")

    assert status_response.status_code == 200
    assert status_response.json() == {"processes": [], "running_session_ids": []}
    assert reset_response.status_code == 200
    assert reset_response.json()["status"] == "reset"
    assert stop_calls == ["stop"]
