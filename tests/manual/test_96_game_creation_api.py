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
    """Isolate global engine, claim, controller, and session state per test."""
    reset_standard_arena_runtime()
    yield
    reset_standard_arena_runtime()


@pytest.fixture
def client() -> Iterator[ArenaApiClient]:
    """Provide one persistent in-process API client per test."""
    with ArenaApiClient() as api_client:
        yield api_client


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


def test_catalog_is_a_lossless_projection_of_canonical_content(
    client: ArenaApiClient,
) -> None:
    """The setup UI receives every canonical composition and historical recipe."""
    response = client.get("/game-creation/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == 1
    assert payload["controllers"] == ["human", "ai", "codex"]
    assert [
        row["descriptor"]["policy_id"]
        for row in payload["ai_policies"]
    ] == [
        "builtin.basic",
        "custom.tactical",
    ]
    assert all(
        row["execution"] == "in_process"
        and row["provider_id"] is None
        and row["capacity"] is None
        and row["active_assignments"] is None
        and row["available_capacity"] is None
        for row in payload["ai_policies"]
    )
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


def test_openapi_has_one_game_creation_and_native_ai_path(
    client: ArenaApiClient,
) -> None:
    """Deleted managed-service and scenario-start aliases cannot return."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = set(response.json()["paths"])
    assert {
        "/game-creation/catalog",
        "/game-creation/preflight",
        "/game-creation/start",
        "/game-creation/activate",
    }.issubset(paths)
    assert "/ai/service" not in paths
    assert "/ai/sessions/{session_id}/service-ready" not in paths
    assert not {
        "/simulation/start-human",
        "/simulation/start-ai-validation",
        "/simulation/start-codex-monsters",
        "/simulation/start-aoe-test",
        "/simulation/start-pvp",
        "/simulation/start",
        "/simulation/reset",
    }.intersection(paths)


def test_preflight_is_pure_and_reports_incompatibility(
    client: ArenaApiClient,
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


def test_human_vs_ai_start_wires_exact_sides_and_join_authority(
    client: ArenaApiClient,
) -> None:
    """Preparation wires native controllers without manufacturing AI sessions."""
    response = client.post(
        "/game-creation/start",
        json=_preset_start_request(),
    )

    assert response.status_code == 200
    payload = response.json()
    side_a_assignments = payload["side_a"]["entity_assignments"]
    side_b_assignments = payload["side_b"]["entity_assignments"]
    human_entity_uuids = [row["entity_uuid"] for row in side_a_assignments]
    assert payload["status"] == "prepared"
    assert _controller_types(side_a_assignments) == {"human"}
    assert _controller_types(side_b_assignments) == {"native_ai"}
    assert all(set(row) == {"entity_uuid", "entity_name", "faction"} for row in side_a_assignments + side_b_assignments)
    assert payload["side_a"]["policy_id"] is None
    assert payload["side_a"]["policy_execution"] is None
    assert payload["side_a"]["provider_id"] is None
    assert payload["side_b"]["policy_id"] == "builtin.basic"
    assert payload["side_b"]["policy_execution"] == "in_process"
    assert payload["side_b"]["provider_id"] is None
    assert event_server.sim.get_session_manager().sessions == {}
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
    bootstrap_response = client.get(
        "/replication/bootstrap",
        params={"session_id": session_id},
    )
    assert bootstrap_response.status_code == 200
    bootstrap = bootstrap_response.json()
    activation = client.post(
        "/game-creation/activate",
        json={
            "session_id": session_id,
            "expected_source_stream_id": bootstrap["protocol"][
                "source_stream_id"
            ],
            "expected_generation_id": bootstrap["protocol"]["generation_id"],
            "expected_perspective_epoch_id": bootstrap["perspective"][
                "perspective_epoch_id"
            ],
        },
    )
    assert activation.status_code == 200

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
    assert live_cursors == list(
        range(event_cursor_before + 1, EventQueue.event_cursor() + 1)
    )


def test_codex_side_claims_exact_entities_over_native_ai_fallback(
    client: ArenaApiClient,
) -> None:
    """Configured Codex play is an exact-side lease with deterministic recovery."""
    response = client.post(
        "/game-creation/start",
        json=_preset_start_request(side_a="codex", side_b="ai"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "prepared"
    assert payload["side_a"]["codex_session_id"] is not None
    assert payload["side_a"]["takeover_claim_id"] is not None
    assert payload["side_a"]["policy_id"] == "builtin.basic"
    assert payload["side_a"]["policy_execution"] == "in_process"
    assert payload["side_a"]["provider_id"] is None
    assert payload["side_b"]["policy_id"] == "builtin.basic"
    assert payload["side_b"]["policy_execution"] == "in_process"
    assert payload["side_b"]["provider_id"] is None
    assert _controller_types(payload["side_a"]["entity_assignments"]) == {"codex"}
    assert _controller_types(payload["side_b"]["entity_assignments"]) == {"native_ai"}
    assert len(event_server.sim.native_ai_controllers) == 2
    assert event_server.sim.get_session_manager().sessions.keys() == {
        UUID(payload["side_a"]["codex_session_id"])
    }

    claim = event_server.ai_takeover_manager.get_claim(
        UUID(payload["side_a"]["takeover_claim_id"]),
    )
    assert claim is not None
    assert {str(entity_uuid) for entity_uuid in claim.entity_uuids} == {
        row["entity_uuid"] for row in payload["side_a"]["entity_assignments"]
    }
    released = client.post(
        f"/ai/takeover/{payload['side_a']['takeover_claim_id']}/release",
    )
    assert released.status_code == 200
    assert _controller_types(payload["side_a"]["entity_assignments"]) == {
        "native_ai"
    }


def test_observer_join_has_no_entity_authority(
    client: ArenaApiClient,
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
