"""Focused API checks for composed games and controller assignment."""

import asyncio
from collections.abc import Iterator
from pathlib import Path
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
from server.agent_runtime.service import AgentLaunchRequest
from server.agent_runtime.service_manager import AgentServiceStartError
from server.agent_runtime.subprocess_service import (
    AgentProcessSpec,
    SubprocessAgentService,
)
from server.arena_mode import ArenaApiClient, reset_standard_arena_runtime
from server.event_stream import event_stream
from server.live_replication import drain_subscription


class _RouteTestLauncher:
    """Registered capability probe; route tests replace actual batch spawning."""

    service_id = "tests.game-creation-agent"

    def preflight(self, _required_agents: int) -> None:
        return None

    def build_process_spec(self, request: AgentLaunchRequest) -> AgentProcessSpec:
        return AgentProcessSpec(
            argv=("unused-route-test-agent", str(request.session_id)),
            cwd=Path(__file__).resolve().parents[2],
        )


@pytest.fixture(autouse=True)
def clean_game_creation_runtime() -> Iterator[None]:
    """Isolate global engine, process, claim, and session state per test."""
    service_id = event_server.agent_service_manager.service_id
    if service_id is not None:
        event_server.agent_service_manager.unregister_service(service_id)
    reset_standard_arena_runtime()
    yield
    reset_standard_arena_runtime()
    service_id = event_server.agent_service_manager.service_id
    if service_id is not None:
        event_server.agent_service_manager.unregister_service(service_id)


@pytest.fixture
def client() -> Iterator[ArenaApiClient]:
    """Provide one persistent in-process API client per test."""
    with ArenaApiClient() as api_client:
        yield api_client


@pytest.fixture
def process_starts(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Capture external-agent launches without spawning operating-system processes."""
    starts: list[tuple[str, str]] = []
    event_server.agent_service_manager.register_service(
        SubprocessAgentService(_RouteTestLauncher())
    )

    async def capture_start(
        requests: tuple[AgentLaunchRequest, ...],
    ) -> tuple[object, ...]:
        starts.extend(
            (str(request.session_id), request.base_url)
            for request in requests
        )
        return ()

    monkeypatch.setattr(
        event_server.agent_service_manager,
        "start_agents",
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


def _controller_types(assignment_rows: list[dict[str, object]]) -> set[str]:
    """Resolve encounter controller kinds for control-plane assignment rows."""
    encounter = event_server.sim.encounter
    assert encounter is not None
    result = set()
    for row in assignment_rows:
        entity = Entity.get(UUID(str(row["entity_uuid"])))
        assert entity is not None
        controller = encounter.get_controller_for(entity.uuid)
        assert controller is not None
        result.add(controller.controller_type)
    return result


def test_unregistered_catalog_exposes_only_runnable_human_controller(
    client: ArenaApiClient,
) -> None:
    """The core server never advertises managed controllers it cannot launch."""
    assert event_server.agent_service_manager.has_service is False

    response = client.get("/game-creation/catalog")

    assert response.status_code == 200
    assert response.json()["controllers"] == ["human"]


def test_unregistered_ai_start_is_rejected_before_live_game_mutation(
    client: ArenaApiClient,
) -> None:
    """A missing launcher cannot replace a healthy game with a brainless AI game."""
    baseline = client.post(
        "/game-creation/start",
        json=_preset_start_request(side_a="human", side_b="human"),
    )
    assert baseline.status_code == 200
    encounter_before = event_server.sim.encounter
    game_before = event_server.sim.game
    creation_before = event_server.sim.current_creation
    entity_uuids_before = tuple(
        entity.uuid for entity in Entity.get_all_entities()
    )
    manager = event_server.sim.get_session_manager()
    session_ids_before = tuple(manager.sessions)
    game_ids_before = tuple(manager.games)
    generation_before = EventQueue.generation_id()
    event_cursor_before = EventQueue.event_cursor()
    session_statuses_before = event_server.agent_service_manager.session_statuses()

    rejected = client.post(
        "/game-creation/start",
        json=_preset_start_request(side_a="human", side_b="ai"),
    )

    assert rejected.status_code == 503
    assert rejected.json()["detail"]["code"] == "agent_service_unavailable"
    assert event_server.sim.encounter is encounter_before
    assert event_server.sim.game is game_before
    assert event_server.sim.current_creation is creation_before
    assert tuple(entity.uuid for entity in Entity.get_all_entities()) == entity_uuids_before
    assert tuple(manager.sessions) == session_ids_before
    assert tuple(manager.games) == game_ids_before
    assert EventQueue.generation_id() == generation_before
    assert EventQueue.event_cursor() == event_cursor_before
    assert event_server.agent_service_manager.session_statuses() == session_statuses_before


def test_agent_spawn_failure_aborts_partial_game_and_allows_clean_retry(
    client: ArenaApiClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A registered service failure leaves no sessions, claims, or engine scene."""
    event_server.agent_service_manager.register_service(
        SubprocessAgentService(_RouteTestLauncher())
    )

    async def reject_batch(
        _requests: tuple[AgentLaunchRequest, ...],
    ) -> tuple[object, ...]:
        raise AgentServiceStartError("agent executable refused")

    monkeypatch.setattr(
        event_server.agent_service_manager,
        "start_agents",
        reject_batch,
    )
    rejected = client.post(
        "/game-creation/start",
        json=_preset_start_request(side_a="codex", side_b="ai"),
    )

    manager = event_server.sim.get_session_manager()
    assert rejected.status_code == 500
    assert rejected.json()["detail"]["code"] == "agent_service_start_failed"
    assert event_server.sim.encounter is None
    assert event_server.sim.game is None
    assert event_server.sim.current_creation is None
    assert Entity.get_all_entities() == []
    assert manager.sessions == {}
    assert manager.games == {}
    assert manager.active_game is None
    assert event_server.ai_takeover_manager.active_claims() == []
    assert event_server.agent_service_manager.session_statuses() == []

    async def accept_batch(
        _requests: tuple[AgentLaunchRequest, ...],
    ) -> tuple[object, ...]:
        return ()

    monkeypatch.setattr(
        event_server.agent_service_manager,
        "start_agents",
        accept_batch,
    )
    retry = client.post(
        "/game-creation/start",
        json=_preset_start_request(side_a="human", side_b="ai"),
    )
    assert retry.status_code == 200
    assert retry.json()["status"] == "waiting_for_human"


def test_post_spawn_advance_failure_aborts_partial_game(
    client: ArenaApiClient,
    process_starts: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Initial advancement remains inside the managed-start transaction."""
    stop_calls: list[str] = []
    async def capture_stop_all() -> None:
        stop_calls.append("stop")

    monkeypatch.setattr(
        event_server.agent_service_manager,
        "stop_all",
        capture_stop_all,
    )

    async def fail_advance(*_args: object, **_kwargs: object):
        raise RuntimeError("initial advance refused")

    monkeypatch.setattr(event_server, "advance_encounter", fail_advance)

    with pytest.raises(RuntimeError, match="initial advance refused"):
        client.post(
            "/game-creation/start",
            json=_preset_start_request(side_a="human", side_b="ai"),
        )

    manager = event_server.sim.get_session_manager()
    assert len(process_starts) == 1
    assert stop_calls == ["stop", "stop"]
    assert event_server.sim.encounter is None
    assert event_server.sim.game is None
    assert manager.sessions == {}
    assert manager.games == {}
    assert Entity.get_all_entities() == []


def test_catalog_is_a_lossless_projection_of_canonical_content(
    client: ArenaApiClient,
    process_starts: list[tuple[str, str]],
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
    side_a_assignments = payload["side_a"]["entity_assignments"]
    side_b_assignments = payload["side_b"]["entity_assignments"]
    human_entity_uuids = [row["entity_uuid"] for row in side_a_assignments]
    assert payload["status"] == "waiting_for_human"
    assert payload["entity_uuid"] in human_entity_uuids
    assert _controller_types(side_a_assignments) == {"human"}
    assert _controller_types(side_b_assignments) == {"external_ai"}
    assert all(set(row) == {"entity_uuid", "entity_name", "faction"} for row in side_a_assignments + side_b_assignments)
    assert payload["side_a"]["fallback_ai_session_id"] is None
    assert payload["side_b"]["fallback_ai_session_id"] == process_starts[0][0]
    assert process_starts == [(payload["side_b"]["fallback_ai_session_id"], "http://testserver")]
    recipe = next(row for row in LEGACY_RECIPES if row.arena_id == "standard_skeleton_doors")
    objective_entities = client.get("/diagnostics/objective/bootstrap").json()["world"]["state"]["entities"]
    side_a_ids = set(human_entity_uuids)
    side_b_ids = {row["entity_uuid"] for row in side_b_assignments}
    assert {
        row["appearance"]["portrait_key"]
        for row in objective_entities
        if row["uuid"] in side_a_ids
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
        for row in objective_entities
        if row["uuid"] in side_b_ids
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
            "entity_uuids": human_entity_uuids,
        },
    )
    assert session.status_code == 200
    assert join.status_code == 200
    assert join.json()["controlled_entities"] == human_entity_uuids


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
    hero_uuid = payload["side_a"]["entity_assignments"][0]["entity_uuid"]

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

    available = client.get(
        f"/entity/{hero_uuid}/available-actions",
        params={"session_id": session_id},
    ).json()
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
    assert process_starts
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
    assert _controller_types(payload["side_a"]["entity_assignments"]) == {"external_ai"}
    assert _controller_types(payload["side_b"]["entity_assignments"]) == {"external_ai"}

    status = client.get("/game/status").json()
    assert status["active"] is True
    assert status["game_id"] == payload["game_id"]
    assert status["creation"]["game_id"] == payload["game_id"]
    sessions = {row["session_id"]: row for row in status["sessions"]}
    controlled_a = {row["entity_uuid"] for row in payload["side_a"]["entity_assignments"]}
    controlled_b = {row["entity_uuid"] for row in payload["side_b"]["entity_assignments"]}
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
    assert _controller_types(payload["side_a"]["entity_assignments"]) == {"codex"}
    assert _controller_types(payload["side_b"]["entity_assignments"]) == {"external_ai"}

    claim = event_server.ai_takeover_manager.get_claim(
        UUID(payload["side_a"]["takeover_claim_id"]),
    )
    assert claim is not None
    assert {str(entity_uuid) for entity_uuid in claim.entity_uuids} == {
        row["entity_uuid"] for row in payload["side_a"]["entity_assignments"]
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
    entity_uuid = start.json()["side_a"]["entity_assignments"][0]["entity_uuid"]
    session = client.post(
        "/session/create",
        json={"player_type": "observer", "name": "Match Observer"},
    )
    assert session.status_code == 200

    joined = client.post(
        "/game/join",
        json={
            "session_id": session.json()["session_id"],
            "observer_entity_uuids": [entity_uuid],
            "active_observer_uuid": entity_uuid,
        },
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
    assert joined.json()["observer_entities"] == [entity_uuid]
    assert joined.json()["active_observer_uuid"] == entity_uuid
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["code"] == "observer_cannot_control_entities"
