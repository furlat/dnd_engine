"""Focused API checks for composed games and controller assignment."""

import asyncio
from collections.abc import Iterator
from uuid import UUID

import pytest

from dnd.core.events import EventQueue
from dnd.entity import Entity
from dnd.scenarios.evaluation.battlefield_catalog import BATTLEFIELDS
from dnd.scenarios.evaluation.combatant_catalog import (
    HERO_CONFIGURATIONS,
    MONSTER_PARTY_CONFIGURATIONS,
)
from dnd.scenarios.evaluation.deployment_catalog import DEPLOYMENTS
from dnd.scenarios.evaluation.legacy_recipes import LEGACY_RECIPES
from server import event_server
from server.arena_mode import ArenaApiClient, reset_standard_arena_runtime
from server.event_stream import event_stream
from server.live_replication import drain_subscription


@pytest.fixture(autouse=True)
def clean_game_creation_runtime() -> Iterator[None]:
    """Isolate global engine, process, claim, and session state per test."""
    reset_standard_arena_runtime()
    yield
    reset_standard_arena_runtime()


@pytest.fixture
def client() -> Iterator[ArenaApiClient]:
    """Provide one persistent in-process API client per test."""
    with ArenaApiClient() as api_client:
        yield api_client


@pytest.fixture
def process_starts(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Capture external-agent launches without spawning operating-system processes."""
    starts: list[tuple[str, str]] = []

    def capture_start(session_id: object, base_url: str) -> None:
        starts.append((str(session_id), base_url))

    monkeypatch.setattr(
        event_server.ai_process_manager,
        "start_external_agent",
        capture_start,
    )
    return starts


def _preset_start_request(
    *,
    side_a: str = "human",
    side_b: str = "ai",
    opening_side: str = "side_a",
) -> dict[str, object]:
    """Build the smallest representative game-creation request."""
    return {
        "scenario": {
            "kind": "preset",
            "arena_id": "standard_skeleton_doors",
        },
        "side_a": {"controller": side_a, "name": "Side A"},
        "side_b": {"controller": side_b, "name": "Side B"},
        "opening_side": opening_side,
    }


def _controller_types(entity_rows: list[dict[str, object]]) -> set[str]:
    """Resolve encounter controller kinds for serialized entity rows."""
    encounter = event_server.sim.encounter
    assert encounter is not None
    result = set()
    for row in entity_rows:
        entity = Entity.get(UUID(str(row["uuid"])))
        assert entity is not None
        controller = encounter.get_controller_for(entity.uuid)
        assert controller is not None
        result.add(controller.controller_type)
    return result


def test_catalog_is_a_lossless_projection_of_canonical_content(
    client: ArenaApiClient,
) -> None:
    """The setup UI receives every canonical composition and historical recipe."""
    response = client.get("/game-creation/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == 1
    assert payload["controllers"] == ["human", "ai", "codex"]
    assert payload["opening_sides"] == ["initiative", "side_a", "side_b"]
    assert [row["configuration_id"] for row in payload["hero_configurations"]] == [
        spec.configuration_id for spec in HERO_CONFIGURATIONS
    ]
    berserker = next(
        row
        for row in payload["hero_configurations"]
        if row["configuration_id"] == "hero.barbarian_l5_berserker_torch"
    )
    assert berserker["members"][0]["augmentations"][0] == {
        "kind": "apparel_grant",
        "item_id": "costume",
        "visual_variant_id": "85000004",
        "display_name": "Pit Fighter's Wrap",
    }
    assert [row["configuration_id"] for row in payload["monster_configurations"]] == [
        spec.configuration_id for spec in MONSTER_PARTY_CONFIGURATIONS
    ]
    assert [row["battlefield_id"] for row in payload["battlefields"]] == [
        spec.battlefield_id for spec in BATTLEFIELDS
    ]
    assert all(row["preview"] is not None for row in payload["battlefields"])
    closed = next(
        row
        for row in payload["battlefields"]
        if row["battlefield_id"] == "battlefield.standard_hazards_closed"
    )
    assert any(
        obj["kind"] == "door" and obj["position"] == [7, 7] and obj["is_open"] is False
        for obj in closed["preview"]["objects"]
    )
    assert [row["deployment_id"] for row in payload["deployments"]] == [
        spec.deployment_id for spec in DEPLOYMENTS
    ]
    assert [row["arena_id"] for row in payload["presets"]] == [
        recipe.arena_id for recipe in LEGACY_RECIPES
    ]


def test_preflight_is_pure_and_reports_incompatibility(
    client: ArenaApiClient,
    process_starts: list[tuple[str, str]],
) -> None:
    """Compatibility checks neither replace nor mutate the current live encounter."""
    start = client.post(
        "/game-creation/start",
        json=_preset_start_request(),
    )
    assert start.status_code == 200
    encounter = event_server.sim.encounter
    game = event_server.sim.game
    entities_before = tuple(entity.uuid for entity in Entity.get_all_entities())

    recipe = LEGACY_RECIPES[0]
    valid = client.post(
        "/game-creation/preflight",
        json={
            "hero_configuration_id": recipe.hero_configuration_id,
            "monster_configuration_id": recipe.monster_configuration_id,
            "battlefield_id": recipe.battlefield_id,
            "deployment_id": recipe.deployment_id,
        },
    )
    invalid = client.post(
        "/game-creation/preflight",
        json={
            "hero_configuration_id": recipe.hero_configuration_id,
            "monster_configuration_id": recipe.monster_configuration_id,
            "battlefield_id": "battlefield.open_floor_bright",
            "deployment_id": recipe.deployment_id,
        },
    )

    assert valid.status_code == 200
    assert valid.json()["admitted"] is True
    assert invalid.status_code == 200
    assert invalid.json()["admitted"] is False
    assert {issue["code"] for issue in invalid.json()["issues"]} >= {"battlefield_mismatch"}
    assert event_server.sim.encounter is encounter
    assert event_server.sim.game is game
    assert tuple(entity.uuid for entity in Entity.get_all_entities()) == entities_before
    assert len(process_starts) == 1


def test_human_vs_ai_start_wires_exact_sides_and_join_authority(
    client: ArenaApiClient,
    process_starts: list[tuple[str, str]],
) -> None:
    """One request builds the scene, assigns controllers, and exposes human claims."""
    response = client.post(
        "/game-creation/start",
        json=_preset_start_request(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "waiting_for_human"
    assert payload["entity_uuid"] in payload["side_a"]["human_entity_uuids"]
    assert _controller_types(payload["side_a"]["entities"]) == {"human"}
    assert _controller_types(payload["side_b"]["entities"]) == {"external_ai"}
    assert payload["side_a"]["fallback_ai_session_id"] is None
    assert payload["side_b"]["fallback_ai_session_id"] == process_starts[0][0]
    assert process_starts == [(payload["side_b"]["fallback_ai_session_id"], "http://testserver")]
    recipe = next(row for row in LEGACY_RECIPES if row.arena_id == "standard_skeleton_doors")
    assert {
        row["appearance"]["portrait_key"]
        for row in payload["side_a"]["entities"]
    } == {
        f"{recipe.hero_configuration_id}::{member.actor_id}"
        for member in next(
            spec
            for spec in HERO_CONFIGURATIONS
            if spec.configuration_id == recipe.hero_configuration_id
        ).members
    }
    assert {
        row["appearance"]["portrait_key"]
        for row in payload["side_b"]["entities"]
    } == {
        f"{recipe.monster_configuration_id}::{member.actor_id}"
        for member in next(
            spec
            for spec in MONSTER_PARTY_CONFIGURATIONS
            if spec.configuration_id == recipe.monster_configuration_id
        ).members
    }

    session = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Local Player"},
    )
    join = client.post(
        "/game/join",
        json={
            "session_id": session.json()["session_id"],
            "entity_uuids": payload["side_a"]["human_entity_uuids"],
        },
    )
    assert session.status_code == 200
    assert join.status_code == 200
    assert join.json()["controlled_entities"] == payload["side_a"]["human_entity_uuids"]


def test_live_stream_preserves_cursor_order_during_recursive_movement(
    client: ArenaApiClient,
    process_starts: list[tuple[str, str]],
) -> None:
    """Movement and its sensory children reach clients in storage order."""
    start = client.post(
        "/game-creation/start",
        json=_preset_start_request(),
    )
    assert start.status_code == 200
    payload = start.json()
    hero_uuid = payload["side_a"]["human_entity_uuids"][0]

    session = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Movement Stream Test"},
    )
    session_id = session.json()["session_id"]
    joined = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [hero_uuid]},
    )
    assert joined.status_code == 200

    available = client.get(f"/entity/{hero_uuid}/available-actions").json()
    move = next(
        row for row in available["position_actions"]
        if row["template_name"] == "Move"
    )
    target = move["valid_targets"][0]

    event_stream.ensure_attached()
    event_cursor_before = EventQueue.event_cursor()
    subscription = event_stream.subscribe(max_depth=256)
    try:
        result = client.post(
            "/action/execute",
            json={
                "session_id": session_id,
                "entity_uuid": hero_uuid,
                "template_name": "Move",
                "target_index": target["index"],
                "return_available_actions": False,
                "include_state": False,
            },
        )
        assert result.status_code == 200
        envelopes = asyncio.run(drain_subscription(subscription, limit=256))
    finally:
        event_stream.unsubscribe(subscription)

    live_cursors = [
        envelope["data"].event_cursor
        for envelope in envelopes
        if envelope["event"] == "game_event"
    ]
    replay_cursors = [
        frame.event_cursor
        for frame in event_stream.iter_game_events_since(
            event_cursor_before,
            event_server.sim.encounter,
        )
    ]

    assert process_starts
    assert live_cursors == replay_cursors
    assert live_cursors == list(
        range(event_cursor_before + 1, EventQueue.event_cursor() + 1)
    )


def test_ai_vs_ai_uses_isolated_sessions_and_processes(
    client: ArenaApiClient,
    process_starts: list[tuple[str, str]],
) -> None:
    """Autonomous opponents never share authority or a policy process."""
    response = client.post(
        "/game-creation/start",
        json=_preset_start_request(side_a="ai", side_b="ai"),
    )

    assert response.status_code == 200
    payload = response.json()
    session_a = payload["side_a"]["fallback_ai_session_id"]
    session_b = payload["side_b"]["fallback_ai_session_id"]
    assert payload["status"] == "waiting_for_ai"
    assert session_a != session_b
    assert {session_id for session_id, _ in process_starts} == {session_a, session_b}
    assert _controller_types(payload["side_a"]["entities"]) == {"external_ai"}
    assert _controller_types(payload["side_b"]["entities"]) == {"external_ai"}

    status = client.get("/game/status").json()
    assert status["active"] is True
    assert status["game_id"] == payload["game_id"]
    assert status["creation"]["game_id"] == payload["game_id"]
    sessions = {row["session_id"]: row for row in status["sessions"]}
    controlled_a = {row["uuid"] for row in payload["side_a"]["entities"]}
    controlled_b = {row["uuid"] for row in payload["side_b"]["entities"]}
    assert set(sessions[session_a]["controlled_entities"]) == controlled_a
    assert set(sessions[session_b]["controlled_entities"]) == controlled_b
    assert controlled_a.isdisjoint(controlled_b)


def test_codex_side_claims_exact_entities_over_live_ai_fallback(
    client: ArenaApiClient,
    process_starts: list[tuple[str, str]],
) -> None:
    """Configured Codex play is an exact-side lease with deterministic recovery."""
    response = client.post(
        "/game-creation/start",
        json=_preset_start_request(side_a="codex", side_b="ai"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "waiting_for_codex"
    assert payload["side_a"]["codex_session_id"] is not None
    assert payload["side_a"]["takeover_claim_id"] is not None
    assert payload["side_a"]["fallback_ai_session_id"] is not None
    assert payload["side_b"]["fallback_ai_session_id"] is not None
    assert len(process_starts) == 2
    assert _controller_types(payload["side_a"]["entities"]) == {"codex"}
    assert _controller_types(payload["side_b"]["entities"]) == {"external_ai"}

    claim = event_server.ai_takeover_manager.get_claim(
        UUID(payload["side_a"]["takeover_claim_id"]),
    )
    assert claim is not None
    assert {str(entity_uuid) for entity_uuid in claim.entity_uuids} == {
        row["uuid"] for row in payload["side_a"]["entities"]
    }


def test_observer_join_has_no_entity_authority(
    client: ArenaApiClient,
    process_starts: list[tuple[str, str]],
) -> None:
    """Spectator identity can join the game but can never claim a combatant."""
    start = client.post(
        "/game-creation/start",
        json=_preset_start_request(side_a="ai", side_b="ai"),
    )
    assert start.status_code == 200
    entity_uuid = start.json()["side_a"]["entities"][0]["uuid"]
    session = client.post(
        "/session/create",
        json={"player_type": "observer", "name": "Match Observer"},
    )
    assert session.status_code == 200

    joined = client.post(
        "/game/join",
        json={"session_id": session.json()["session_id"]},
    )
    rejected = client.post(
        "/game/join",
        json={
            "session_id": session.json()["session_id"],
            "entity_uuids": [entity_uuid],
        },
    )

    assert joined.status_code == 200
    assert joined.json()["success"] is True
    assert joined.json()["controlled_entities"] == []
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["code"] == "observer_cannot_control_entities"
