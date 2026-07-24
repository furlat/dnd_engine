"""Focused end-to-end tests for the multi-game gateway handshake."""

from __future__ import annotations

import asyncio
import httpx
from pathlib import Path
import time
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from ai.game_server_profiles import EMBEDDED_AI_WORKER_APPLICATION
from ai.remote_connection import redeem_remote_agent_grant
from dnd.core.base_object import BaseObject
from dnd.scenarios.evaluation.legacy_recipes import LEGACY_RECIPES
from server.game_creation_catalog import build_game_creation_catalog
from server.game_directory.repository import GameDirectoryRepository
from server.game_gateway import create_gateway_app
from server.hosted_worker import HostedWorkerManager
from server.runtime_authority import RuntimeAuthorityCache


PEPPER = b"gateway-test-capability-pepper"


def _creation_body(principal: dict[str, Any]) -> dict[str, Any]:
    """Return one deterministic human-versus-AI hosted-game request."""
    return {
        "principal_id": principal["principal"]["principal_id"],
        "principal_capability": principal["principal_capability"],
        "display_name": "Gateway Doors",
        "creation": {
            "scenario": {"kind": "preset", "arena_id": "standard_skeleton_doors"},
            "side_a": {"controller": "human", "name": "Gateway Human"},
            "side_b": {"controller": "ai", "name": "Gateway AI"},
            "opening_side": "side_a",
        },
        "owner_side": "side_a",
        "visibility_policy": "public",
        "observer_policy": "public",
        "client_kind": "neuroclient",
        "client_instance_id": "owner-browser",
    }


def test_prewarmed_worker_is_claimed_without_cold_process_start(tmp_path: Path) -> None:
    """A ready reserve worker removes interpreter import time from game creation."""

    async def exercise_pool() -> None:
        workers = HostedWorkerManager(
            tmp_path / "runtime",
            worker_application=EMBEDDED_AI_WORKER_APPLICATION,
            warm_pool_size=1,
            startup_timeout_seconds=20.0,
        )
        await workers.prewarm()
        assert workers.warm_worker_count() == 1

        game_id = uuid4()
        started_at = time.perf_counter()
        placement = await workers.start(
            game_id,
            public_game_base_url=f"http://gateway/games/{game_id}/runtime",
        )
        claim_elapsed = time.perf_counter() - started_at

        assert placement.hosted_game_id == game_id
        assert placement.state.value == "ready"
        assert workers.active_game_ids() == (game_id,)
        assert claim_elapsed < 2.0
        await workers.stop_all()

    asyncio.run(exercise_pool())


def test_gateway_exposes_shared_read_only_creation_and_spell_catalogs(
    tmp_path: Path,
) -> None:
    """Catalog and preflight requests use no database game or worker mutation."""
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    workers = HostedWorkerManager(tmp_path / "runtime")
    app = create_gateway_app(
        repository=repository,
        worker_manager=workers,
        capability_pepper=PEPPER,
    )
    recipe = LEGACY_RECIPES[0]
    registered_objects_before = dict(BaseObject._registry)

    with TestClient(app) as client:
        capabilities_response = client.get("/server/capabilities")
        catalog_response = client.get("/game-creation/catalog")
        valid_response = client.post(
            "/game-creation/preflight",
            json={
                "hero_configuration_id": recipe.hero_configuration_id,
                "monster_configuration_id": recipe.monster_configuration_id,
                "battlefield_id": recipe.battlefield_id,
                "deployment_id": recipe.deployment_id,
            },
        )
        invalid_response = client.post(
            "/game-creation/preflight",
            json={
                "hero_configuration_id": "hero.unknown",
                "monster_configuration_id": recipe.monster_configuration_id,
                "battlefield_id": recipe.battlefield_id,
                "deployment_id": recipe.deployment_id,
            },
        )
        spells_response = client.get("/catalog/spells")

        assert capabilities_response.status_code == 200
        assert capabilities_response.headers["server-timing"].startswith("app;dur=")
        assert capabilities_response.json() == {
            "server_mode": "gateway",
            "game_directory_enabled": True,
            "persistent_game_history": True,
            "isolated_game_workers": True,
        }
        assert catalog_response.status_code == 200
        assert catalog_response.json() == build_game_creation_catalog(
            ("human",),
        ).model_dump(mode="json")
        assert valid_response.status_code == 200
        assert valid_response.json()["admitted"] is True
        assert invalid_response.status_code == 400
        assert invalid_response.json()["detail"]["code"] == (
            "invalid_game_creation_component"
        )
        assert "hero.unknown" in invalid_response.json()["detail"]["selection"].values()
        assert spells_response.status_code == 200
        spells = {row["id"] for row in spells_response.json()["spells"]}
        assert {"fire_bolt", "magic_missile", "fireball"} <= spells
        assert repository.list_games() == ()
        assert workers.active_game_ids() == ()
        assert BaseObject._registry == registered_objects_before

    repository.close()


def test_core_gateway_rejects_managed_ai_before_spawning_worker(
    tmp_path: Path,
) -> None:
    """Core-only gateway admission agrees with its human-only catalog."""
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    workers = HostedWorkerManager(tmp_path / "runtime")
    app = create_gateway_app(
        repository=repository,
        worker_manager=workers,
        capability_pepper=PEPPER,
    )

    with TestClient(app) as client:
        owner = client.post(
            "/directory/principals/guest",
            json={"display_name": "Core Owner"},
        ).json()
        rejected = client.post("/games", json=_creation_body(owner))

    assert rejected.status_code == 503
    assert rejected.json()["detail"]["code"] == "agent_service_unavailable"
    assert workers.active_game_ids() == ()
    assert repository.list_games() == ()
    repository.close()


def test_managed_ai_gateway_catalog_matches_worker_composition(
    tmp_path: Path,
) -> None:
    """The AI-owned gateway advertises only capabilities proved at worker boot."""
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    workers = HostedWorkerManager(
        tmp_path / "runtime",
        worker_application=EMBEDDED_AI_WORKER_APPLICATION,
    )
    app = create_gateway_app(
        repository=repository,
        worker_manager=workers,
        capability_pepper=PEPPER,
    )

    with TestClient(app) as client:
        catalog = client.get("/game-creation/catalog")

    assert catalog.status_code == 200
    assert catalog.json() == build_game_creation_catalog().model_dump(
        mode="json",
    )
    assert workers.active_game_ids() == ()
    repository.close()


def test_gateway_creates_reconnects_observes_and_stops_isolated_game(tmp_path: Path) -> None:
    """Cold handshakes create fresh hot capabilities without DB runtime access."""
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    workers = HostedWorkerManager(
        tmp_path / "runtime",
        worker_application=EMBEDDED_AI_WORKER_APPLICATION,
        startup_timeout_seconds=20.0,
    )
    app = create_gateway_app(
        repository=repository,
        worker_manager=workers,
        authority_cache=RuntimeAuthorityCache(),
        capability_pepper=PEPPER,
    )

    with TestClient(app) as client:
        preflight = client.options(
            f"/games/{uuid4()}/runtime/state",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "*"

        owner_response = client.post(
            "/directory/principals/guest",
            json={"display_name": "Owner"},
        )
        assert owner_response.status_code == 200
        owner = owner_response.json()

        created_response = client.post("/games", json=_creation_body(owner))
        assert created_response.status_code == 200, created_response.text
        created = created_response.json()
        game_id = UUID(created["game"]["game_id"])
        connection = created["connection"]
        assert connection["game_id"] == str(game_id)
        assert connection["access_mode"] == "participant"
        assert len(connection["controlled_entity_uuids"]) == 1
        assert connection["engine_base_url"].endswith(f"/games/{game_id}/runtime")

        runtime_path = f"/games/{game_id}/runtime/replication/bootstrap"
        with repository.forbid_hot_path_access():
            bootstrap = client.get(
                runtime_path,
                params={"session_id": connection["runtime_session_id"]},
                headers={"Authorization": f"Bearer {connection['runtime_token']}"},
            )
        assert bootstrap.status_code == 200, bootstrap.text
        assert (
            bootstrap.json()["perspective"]["controlled_entity_uuids"]
            == connection["controlled_entity_uuids"]
        )
        assert client.get(runtime_path).status_code == 403
        assert client.post(
            f"/games/{game_id}/runtime/simulation/reset",
            headers={"Authorization": f"Bearer {connection['runtime_token']}"},
        ).status_code == 403
        assert client.post(
            f"/games/{game_id}/runtime/simulation/pause",
            headers={"Authorization": f"Bearer {connection['runtime_token']}"},
        ).status_code == 403

        reconnect_response = client.post(
            f"/games/{game_id}/attachments",
            json={
                "grant_id": created["reconnect_grant_id"],
                "capability": created["reconnect_capability"],
                "client_kind": "neuroclient",
                "client_instance_id": "owner-browser-reloaded",
            },
        )
        assert reconnect_response.status_code == 200, reconnect_response.text
        reconnect = reconnect_response.json()["connection"]
        assert reconnect["runtime_session_id"] == connection["runtime_session_id"]
        assert reconnect["runtime_token"] != connection["runtime_token"]

        observer_response = client.post(
            "/directory/principals/guest",
            json={"display_name": "Observer"},
        )
        observer = observer_response.json()
        observe_response = client.post(
            f"/games/{game_id}/observers",
            json={
                "principal_id": observer["principal"]["principal_id"],
                "principal_capability": observer["principal_capability"],
                "client_kind": "neuroclient",
                "client_instance_id": "observer-browser",
            },
        )
        assert observe_response.status_code == 200, observe_response.text
        observer_connection = observe_response.json()["connection"]
        assert observer_connection["access_mode"] == "observer"
        assert observer_connection["controlled_entity_uuids"] == []
        assert observer_connection["observer_entity_uuids"]
        assert observer_connection["active_observer_uuid"] in observer_connection["observer_entity_uuids"]
        observer_bootstrap = client.get(
            runtime_path,
            params={"session_id": observer_connection["runtime_session_id"]},
            headers={"Authorization": f"Bearer {observer_connection['runtime_token']}"},
        )
        assert observer_bootstrap.status_code == 200
        assert (
            observer_bootstrap.json()["perspective"]["controlled_entity_uuids"]
            == []
        )

        public_games = client.get("/games")
        assert public_games.status_code == 200
        assert [row["game_id"] for row in public_games.json()["games"]] == [str(game_id)]

        wrong_game_bootstrap = client.get(
            f"/games/{uuid4()}/runtime/replication/bootstrap",
            params={"session_id": connection["runtime_session_id"]},
            headers={"Authorization": f"Bearer {connection['runtime_token']}"},
        )
        assert wrong_game_bootstrap.status_code == 403

        stopped = client.post(
            f"/games/{game_id}/stop",
            json={
                "principal_id": owner["principal"]["principal_id"],
                "principal_capability": owner["principal_capability"],
            },
        )
        assert stopped.status_code == 200, stopped.text
        assert stopped.json()["stopped"] is True
        assert stopped.json()["game"]["lifecycle_state"] == "interrupted"
        assert workers.placement(game_id) is None

    repository.close()


def test_gateway_refuses_automatic_owner_side_before_spawning(tmp_path: Path) -> None:
    """A directory owner cannot claim a side configured for autonomous AI."""
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    workers = HostedWorkerManager(tmp_path / "runtime")
    app = create_gateway_app(
        repository=repository,
        worker_manager=workers,
        capability_pepper=PEPPER,
    )
    with TestClient(app) as client:
        owner = client.post(
            "/directory/principals/guest",
            json={"display_name": "Owner"},
        ).json()
        body = _creation_body(owner)
        body["creation"]["side_a"]["controller"] = "ai"
        response = client.post("/games", json=body)

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "owner_side_is_automatic"
    assert repository.list_games() == ()
    repository.close()


def test_ai_match_publishes_canonical_summary_from_terminal_event(tmp_path: Path) -> None:
    """The cold plane persists a worker summary only after EncounterEndEvent."""
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    workers = HostedWorkerManager(
        tmp_path / "runtime",
        worker_application=EMBEDDED_AI_WORKER_APPLICATION,
        startup_timeout_seconds=20.0,
    )
    app = create_gateway_app(
        repository=repository,
        worker_manager=workers,
        capability_pepper=PEPPER,
    )
    with TestClient(app) as client:
        owner = client.post(
            "/directory/principals/guest",
            json={"display_name": "Tournament Observer"},
        ).json()
        body = _creation_body(owner)
        body["creation"] = {
            "scenario": {"kind": "preset", "arena_id": "sorcerer_barbarian_duel"},
            "side_a": {"controller": "ai", "name": "Sorcerer AI"},
            "side_b": {"controller": "ai", "name": "Barbarian AI"},
            "opening_side": "initiative",
        }
        body["owner_side"] = "observer"
        body["client_instance_id"] = "tournament-watcher"
        body["visibility_policy"] = "private"
        created = client.post("/games", json=body)
        assert created.status_code == 200, created.text
        game_id = UUID(created.json()["game"]["game_id"])

        assert client.get(f"/games/{game_id}/summary").status_code == 404

        deadline = time.monotonic() + 30.0
        owner_auth = {
            "X-Dnd-Principal-Id": owner["principal"]["principal_id"],
            "X-Dnd-Principal-Capability": owner["principal_capability"],
        }
        summary_response = client.get(f"/games/{game_id}/summary", headers=owner_auth)
        while summary_response.status_code == 404 and time.monotonic() < deadline:
            time.sleep(0.05)
            summary_response = client.get(f"/games/{game_id}/summary", headers=owner_auth)

        assert summary_response.status_code == 200, summary_response.text
        summary_record = summary_response.json()
        assert summary_record["summary"]["schema_name"] == "dnd.game-summary"
        assert summary_record["summary"]["outcome"]["terminal_event_observed"] is True
        assert summary_record["summary_digest"] == summary_record["summary"]["canonical_sha256"]
        assert client.get(f"/games/{game_id}/summary").status_code == 404
        game = repository.get_game(game_id)
        assert game.lifecycle_state.value == "ended"
        assert game.current_summary_digest == summary_record["summary_digest"]
        assert any(
            event.event_type == "summary_ready"
            for event in repository.list_directory_events(game_id=game_id, limit=100)
        )

        stopped = client.post(
            f"/games/{game_id}/stop",
            json={
                "principal_id": owner["principal"]["principal_id"],
                "principal_capability": owner["principal_capability"],
            },
        )
        assert stopped.status_code == 200
        assert stopped.json()["stopped"] is True

    repository.close()


def test_autonomous_composed_match_persists_summary_within_half_second(
    tmp_path: Path,
) -> None:
    """Gateway persistence follows worker summary readiness within 500 ms."""
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    workers = HostedWorkerManager(
        tmp_path / "runtime",
        worker_application=EMBEDDED_AI_WORKER_APPLICATION,
        startup_timeout_seconds=20.0,
    )
    app = create_gateway_app(
        repository=repository,
        worker_manager=workers,
        capability_pepper=PEPPER,
    )
    with TestClient(app) as client:
        owner = client.post(
            "/directory/principals/guest",
            json={"display_name": "Fast Match Observer"},
        ).json()
        body = _creation_body(owner)
        body["creation"] = {
            "scenario": {
                "kind": "composed",
                "hero_configuration_id": "hero.sorcerer_l5_standard_torch",
                "monster_configuration_id": "monsters.goblin_water_cell",
                "battlefield_id": "battlefield.standard_hazards_closed",
                "deployment_id": "neutral.battlefield.standard_hazards_closed",
            },
            "side_a": {"controller": "ai", "name": "Sorcerer AI"},
            "side_b": {"controller": "ai", "name": "Goblin AI"},
            "opening_side": "side_a",
        }
        body["owner_side"] = "observer"
        body["client_instance_id"] = "fast-match-watcher"
        created = client.post("/games", json=body)
        assert created.status_code == 200, created.text
        game_id = UUID(created.json()["game"]["game_id"])
        owner_auth = {
            "X-Dnd-Principal-Id": owner["principal"]["principal_id"],
            "X-Dnd-Principal-Capability": owner["principal_capability"],
        }

        worker_ready_at: float | None = None
        gateway_ready_at: float | None = None
        summary_response = client.get(f"/games/{game_id}/summary", headers=owner_auth)
        transport = httpx.HTTPTransport(uds=str(workers.socket_path(game_id)))
        with httpx.Client(
            transport=transport,
            base_url="http://game-worker",
            timeout=2.0,
        ) as worker_client:
            deadline = time.monotonic() + 20.0
            while time.monotonic() < deadline:
                if worker_ready_at is None:
                    worker_response = worker_client.get("/game/evidence/summary")
                    if worker_response.status_code == 200:
                        worker_ready_at = time.monotonic()
                if summary_response.status_code == 404:
                    summary_response = client.get(
                        f"/games/{game_id}/summary",
                        headers=owner_auth,
                    )
                    if summary_response.status_code == 200:
                        gateway_ready_at = time.monotonic()
                if worker_ready_at is not None and gateway_ready_at is not None:
                    break
                time.sleep(0.01)

        assert worker_ready_at is not None
        assert summary_response.status_code == 200, summary_response.text
        assert gateway_ready_at is not None
        assert gateway_ready_at - worker_ready_at < 0.5
        summary_record = summary_response.json()
        assert summary_record["summary"]["schema_version"] == 2
        assert summary_record["summary"]["outcome"]["terminal_event_observed"] is True
        game = repository.get_game(game_id)
        assert game.lifecycle_state.value == "ended"
        assert game.current_summary_digest == summary_record["summary_digest"]

    repository.close()


def test_remote_agent_uses_public_subjective_runtime_without_engine_access(tmp_path: Path) -> None:
    """A remote policy process attaches through the same capability flow as Codex."""
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    workers = HostedWorkerManager(
        tmp_path / "runtime",
        worker_application=EMBEDDED_AI_WORKER_APPLICATION,
        startup_timeout_seconds=20.0,
    )
    app = create_gateway_app(
        repository=repository,
        worker_manager=workers,
        capability_pepper=PEPPER,
    )
    with TestClient(app) as client:
        owner = client.post(
            "/directory/principals/guest",
            json={"display_name": "Human Host"},
        ).json()
        body = _creation_body(owner)
        body["creation"]["side_b"] = {"controller": "codex", "name": "Remote Side"}
        created_response = client.post("/games", json=body)
        assert created_response.status_code == 200, created_response.text
        created = created_response.json()
        game_id = UUID(created["game"]["game_id"])
        side = created["creation"]["side_b"]
        fallback_session_id = side["fallback_ai_session_id"]
        codex_session_id = side["codex_session_id"]
        assert fallback_session_id
        assert codex_session_id
        assert fallback_session_id != codex_session_id
        worker_transport = httpx.HTTPTransport(
            uds=str(workers.socket_path(game_id))
        )
        with httpx.Client(
            transport=worker_transport,
            base_url="http://game-worker",
        ) as worker_client:
            service = worker_client.get("/ai/service")
        assert service.status_code == 200
        fallback_status = next(
            row
            for row in service.json()["sessions"]
            if row["session_id"] == fallback_session_id
        )
        assert fallback_status["ready"] is True

        remote_identity = client.post(
            "/directory/principals/guest",
            json={"display_name": "Remote Policy"},
        ).json()
        grant_response = client.post(
            f"/games/{game_id}/agent-grants",
            json={
                "principal_id": owner["principal"]["principal_id"],
                "principal_capability": owner["principal_capability"],
                "agent_principal_id": remote_identity["principal"]["principal_id"],
                "side_id": "side_b",
            },
        )
        assert grant_response.status_code == 200, grant_response.text
        grant = grant_response.json()
        assert grant["runtime_session_id"] == codex_session_id

        connection_model = redeem_remote_agent_grant(
            gateway_url=str(client.base_url),
            game_id=game_id,
            grant_id=UUID(grant["grant_id"]),
            grant_capability=grant["grant_capability"],
            client_instance_id="remote-policy-process",
            client=client,
        )
        connection = connection_model.model_dump(mode="json")
        assert connection["access_mode"] == "agent"
        assert connection["runtime_session_id"] == grant["runtime_session_id"]
        assert connection["controlled_entity_uuids"] == grant["controlled_entity_uuids"]
        assert connection["takeover_claim_uuids"] == [grant["takeover_claim_id"]]

        heartbeat = client.post(
            f"/games/{game_id}/runtime/ai/takeover/{grant['takeover_claim_id']}/heartbeat",
            headers={"Authorization": f"Bearer {connection['runtime_token']}"},
        )
        assert heartbeat.status_code == 200, heartbeat.text
        wrong_heartbeat = client.post(
            f"/games/{game_id}/runtime/ai/takeover/{uuid4()}/heartbeat",
            headers={"Authorization": f"Bearer {connection['runtime_token']}"},
        )
        assert wrong_heartbeat.status_code == 403

        snapshot = client.get(
            f"/games/{game_id}/runtime/ai/sessions/{connection['runtime_session_id']}/observation/snapshot",
            headers={"Authorization": f"Bearer {connection['runtime_token']}"},
        )
        assert snapshot.status_code == 200, snapshot.text
        assert snapshot.json()["session"]["session_id"] == connection["runtime_session_id"]
        objective_state = client.get(
            f"/games/{game_id}/runtime/state",
            headers={"Authorization": f"Bearer {connection['runtime_token']}"},
        )
        assert objective_state.status_code == 403
        session_directory = client.get(
            f"/games/{game_id}/runtime/ai/sessions",
            headers={"Authorization": f"Bearer {connection['runtime_token']}"},
        )
        assert session_directory.status_code == 403
        cross_session = client.get(
            f"/games/{game_id}/runtime/ai/sessions/{uuid4()}/observation/snapshot",
            headers={"Authorization": f"Bearer {connection['runtime_token']}"},
        )
        assert cross_session.status_code == 403

        stopped = client.post(
            f"/games/{game_id}/stop",
            json={
                "principal_id": owner["principal"]["principal_id"],
                "principal_capability": owner["principal_capability"],
            },
        )
        assert stopped.status_code == 200

    repository.close()
