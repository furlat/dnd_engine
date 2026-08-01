"""Focused end-to-end tests for the multi-game gateway handshake."""

from __future__ import annotations

import asyncio
import httpx
from pathlib import Path
import time
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from ai.remote_connection import redeem_remote_agent_grant
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    DEFAULT_CHARACTER_RULESET_DIGEST,
)
from dnd.core.base_object import BaseObject
from dnd.core.content.encounters import (
    EncounterRecipe,
    EncounterRosterRecipe,
    RosterControllerDefaults,
    RosterControllerKind,
)
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.encounter_catalog import (
    AUTHORED_ENCOUNTER_RECIPES_BY_ID,
    AUTHORED_ROSTER_RECIPES_BY_ID,
)
from server.event_stream import event_stream
from server.ai_policy_composition import server_native_ai_policy_options
from server.game_artifact_store import GameArtifactStore
from server.game_creation_catalog import build_game_creation_catalog
from server.game_directory.security import hash_capability
from server.game_directory.contracts import (
    ArtifactKind,
    GameCreate,
    GameLifecycleState,
    PrincipalCreate,
    PrincipalKind,
    WorkerCreate,
    WorkerState,
    WorkerTransportKind,
)
from server.game_directory.repository import GameDirectoryRepository
from server.game_gateway import ENGINE_VERSION, GameGatewayService, create_gateway_app
from server.game_summary_store import WorkerGameSummaryStore
from server.hosted_worker import HostedWorkerManager
from tests.manual.live_replication_support import create_stream_scene, execute_stream_attack
from server.objective_replay import ObjectiveReplayBundle
from server.player_replay import SubjectivePlayerReplayArchive
from server.runtime_authority import RuntimeAuthorityCache
from server.worker_replay import build_worker_objective_replay
from server.worker_terminal_spool import WorkerTerminalSpool


PEPPER = b"gateway-test-capability-pepper"


def _gateway_creation_catalog():
    """Build the exact native-only controller surface hosted workers execute."""
    return build_game_creation_catalog(
        controllers=("human", "ai", "codex"),
        ai_policies=server_native_ai_policy_options(),
    )


def _configured_recipe(
    *,
    encounter_id: str = "encounter.standard_skeleton_doors",
    first_controller: RosterControllerKind = RosterControllerKind.HUMAN,
    second_controller: RosterControllerKind = RosterControllerKind.AI,
) -> EncounterRecipe:
    source = AUTHORED_ENCOUNTER_RECIPES_BY_ID[encounter_id]
    controllers = (first_controller, second_controller)
    slots = tuple(
        slot.model_copy(update={
            "controller_defaults": RosterControllerDefaults(
                controller=controller,
                participant_name=f"{slot.roster.title} Controller",
                policy_id=(
                    "builtin.basic"
                    if controller is RosterControllerKind.AI
                    else None
                ),
            ),
        })
        for slot, controller in zip(
            source.roster_slots,
            controllers,
            strict=True,
        )
    )
    return EncounterRecipe.create(
        encounter_id=source.encounter_id,
        title=source.title,
        roster_slots=slots,
        battlefield_id=source.battlefield_id,
        deployment=source.deployment,
        opening_policy=source.opening_policy,
        notable_positions=source.notable_positions,
        tags=source.tags,
    )


def _creation_body(
    principal: dict[str, Any],
    *,
    recipe: EncounterRecipe | None = None,
    owner_roster_slot_id: str | None = "roster_1",
) -> dict[str, Any]:
    """Return one deterministic human-versus-AI hosted-game request."""
    selected_recipe = recipe or _configured_recipe()
    return {
        "principal_id": principal["principal"]["principal_id"],
        "principal_capability": principal["principal_capability"],
        "display_name": "Gateway Doors",
        "creation": {
            "expected_content_set_digest": (
                bootstrap_content_system().content_set_digest
            ),
            "expected_ruleset_digest": DEFAULT_CHARACTER_RULESET_DIGEST,
            "recipe": selected_recipe.model_dump(mode="json"),
        },
        "owner_roster_slot_id": owner_roster_slot_id,
        "visibility_policy": "public",
        "observer_policy": "public",
        "client_kind": "neuroclient",
        "client_instance_id": "owner-browser",
    }


def _principal_headers(principal: dict[str, Any]) -> dict[str, str]:
    return {
        "X-Dnd-Principal-Id": principal["principal"]["principal_id"],
        "X-Dnd-Principal-Capability": principal["principal_capability"],
    }


def _create_premade_character(
    client: TestClient,
    principal: dict[str, Any],
    *,
    premade_id: str,
    display_name: str,
) -> dict[str, Any]:
    catalog_response = client.get("/character-creation/catalog")
    assert catalog_response.status_code == 200, catalog_response.text
    catalog = catalog_response.json()
    plan = next(
        row
        for row in catalog["creation_plans"]
        if row["source_premade_id"] == premade_id
    )
    profile_response = client.get(
        "/directory/players/me",
        headers=_principal_headers(principal),
    )
    assert profile_response.status_code == 200, profile_response.text
    created = client.post(
        "/directory/characters",
        headers=_principal_headers(principal),
        json={
            "display_name": display_name,
            "build": plan["build"],
            "loadout": plan["loadout"],
            "creation_plan_id": plan["plan_id"],
            "creation_plan_digest": plan["plan_digest"],
            "expected_content_set_digest": catalog["content_set_digest"],
            "expected_ruleset_digest": profile_response.json()["settings"][
                "ruleset_digest"
            ],
            "idempotency_key": str(uuid4()),
        },
    )
    assert created.status_code == 200, created.text
    return created.json()


def _compose_two_character_roster(
    client: TestClient,
    principal: dict[str, Any],
    *,
    character_ids: tuple[UUID, UUID],
    second_controller: str,
) -> dict[str, Any]:
    override: dict[str, object] = {
        "character_id": str(character_ids[1]),
        "controller": second_controller,
    }
    if second_controller == "ai":
        override["policy_id"] = "builtin.basic"
    response = client.post(
        "/game-creation/compose",
        headers=_principal_headers(principal),
        json={
            "title": "Two Owned Characters",
            "roster_slots": [
                {
                    "roster_slot_id": "players",
                    "roster": {
                        "kind": "owned_characters",
                        "title": "Owned Party",
                        "character_ids": [
                            str(character_id)
                            for character_id in character_ids
                        ],
                        "member_controller_overrides": [override],
                    },
                    "faction_id": "players",
                    "deployment_zone_id": "zone_1",
                    "controller_defaults": {
                        "controller": "human",
                        "participant_name": "Owner",
                        "policy_id": None,
                        "member_overrides": [],
                    },
                },
                {
                    "roster_slot_id": "opposition",
                    "roster": {
                        "kind": "authored_roster",
                        "roster_id": "monsters.skeleton_trio",
                    },
                    "faction_id": "opposition",
                    "deployment_zone_id": "zone_2",
                    "controller_defaults": {
                        "controller": "ai",
                        "participant_name": "Opposition",
                        "policy_id": "builtin.basic",
                        "member_overrides": [],
                    },
                },
            ],
            "battlefield_id": "battlefield.open_floor_bright",
            "deployment_id": "neutral.battlefield.open_floor_bright",
            "opening_policy": {
                "kind": "fixed_roster",
                "roster_slot_id": "players",
            },
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_prewarmed_worker_is_claimed_without_cold_process_start(tmp_path: Path) -> None:
    """A ready reserve worker removes interpreter import time from game creation."""

    async def exercise_pool() -> None:
        workers = HostedWorkerManager(
            tmp_path / "runtime",
            warm_pool_size=1,
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
    """Catalog and exact preview use no game or worker mutation."""
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
    recipe = _configured_recipe()
    registered_objects_before = dict(BaseObject._registry)

    with TestClient(app) as client:
        capabilities_response = client.get("/server/capabilities")
        catalog_response = client.get("/game-creation/catalog")
        principal = client.post(
            "/directory/principals/guest",
            json={"display_name": "Preview Owner"},
        ).json()
        valid_response = client.post(
            "/game-creation/preview",
            headers={
                "X-Dnd-Principal-Id": principal["principal"]["principal_id"],
                "X-Dnd-Principal-Capability": (
                    principal["principal_capability"]
                ),
            },
            json={
                "expected_content_set_digest": (
                    bootstrap_content_system().content_set_digest
                ),
                "expected_ruleset_digest": (
                    DEFAULT_CHARACTER_RULESET_DIGEST
                ),
                "recipe": recipe.model_dump(mode="json"),
            },
        )
        retired_response = client.post("/game-creation/preflight", json={})
        spells_response = client.get("/catalog/spells")
        content_manifest_response = client.get("/content/manifest")
        content_catalog_response = client.get("/content/catalog")
        cached_content_catalog_response = client.get(
            "/content/catalog",
            headers={
                "If-None-Match": content_catalog_response.headers["etag"],
            },
        )

        assert capabilities_response.status_code == 200
        assert capabilities_response.headers["server-timing"].startswith("app;dur=")
        assert capabilities_response.json() == {
            "server_mode": "gateway",
            "game_directory_enabled": True,
            "persistent_game_history": True,
            "isolated_game_workers": True,
        }
        assert catalog_response.status_code == 200
        assert catalog_response.json() == _gateway_creation_catalog().model_dump(
            mode="json",
        )
        assert valid_response.status_code == 200
        assert valid_response.json()["encounter_recipe_digest"] == (
            recipe.recipe_digest
        )
        assert retired_response.status_code == 404
        assert not any(
            getattr(route, "path", "")
            == "/game-creation/preview/configurations/{configuration_id}"
            for route in app.routes
        )
        assert spells_response.status_code == 200
        spells = {row["id"] for row in spells_response.json()["spells"]}
        assert {"fire_bolt", "magic_missile", "fireball"} <= spells
        assert content_manifest_response.status_code == 200
        assert content_catalog_response.status_code == 200
        assert cached_content_catalog_response.status_code == 304
        assert content_manifest_response.json()["content_set_digest"] == (
            content_catalog_response.json()["content_set_digest"]
        )
        assert content_manifest_response.json()["content_set_digest"] == (
            app.state.content_system.content_set_digest
        )
        assert not any(
            getattr(route, "path", "").startswith("/content/v")
            for route in app.routes
        )
        assert repository.list_games() == ()
        assert workers.active_game_ids() == ()
        assert BaseObject._registry == registered_objects_before

    repository.close()


def test_core_gateway_exposes_native_ai_without_spawning_worker(
    tmp_path: Path,
) -> None:
    """Native AI belongs to the core catalog without a service composition."""
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
        catalog = client.get("/game-creation/catalog")

    assert catalog.status_code == 200
    assert catalog.json() == _gateway_creation_catalog().model_dump(mode="json")
    assert workers.active_game_ids() == ()
    assert repository.list_games() == ()
    repository.close()


def test_gateway_composes_owner_saved_roster_at_exact_revision_and_digest(
    tmp_path: Path,
) -> None:
    """Saved roster storage is a usable, owner-scoped composer input."""
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
    source = AUTHORED_ROSTER_RECIPES_BY_ID[
        "hero.fighter_l5_shield_torch"
    ]
    saved_recipe = EncounterRosterRecipe.create(
        roster_id="roster.saved.gateway-fighter",
        title="Gateway Fighter",
        members=source.members,
        tags=("saved",),
        required_battlefield_capabilities=(
            source.required_battlefield_capabilities
        ),
        forbidden_battlefield_capabilities=(
            source.forbidden_battlefield_capabilities
        ),
    )

    with TestClient(app) as client:
        owner = client.post(
            "/directory/principals/guest",
            json={"display_name": "Roster Owner"},
        ).json()
        other = client.post(
            "/directory/principals/guest",
            json={"display_name": "Other Principal"},
        ).json()
        saved_response = client.post(
            "/directory/encounter-rosters",
            headers=_principal_headers(owner),
            json={
                "title": saved_recipe.title,
                "recipe": saved_recipe.model_dump(mode="json"),
            },
        )
        assert saved_response.status_code == 200, saved_response.text
        saved = saved_response.json()
        assert saved["saved_roster_id"].startswith("saved.roster.")
        assert saved["saved_roster_id"] != saved["recipe"]["roster_id"]
        replacement_recipe = EncounterRosterRecipe.create(
            roster_id="roster.saved.gateway-fighter.revision-2",
            title=saved_recipe.title,
            members=saved_recipe.members,
            tags=saved_recipe.tags,
            required_battlefield_capabilities=(
                saved_recipe.required_battlefield_capabilities
            ),
            forbidden_battlefield_capabilities=(
                saved_recipe.forbidden_battlefield_capabilities
            ),
        )
        replaced_response = client.put(
            (
                "/directory/encounter-rosters/"
                f"{saved['saved_roster_id']}"
            ),
            headers=_principal_headers(owner),
            json={
                "title": saved_recipe.title,
                "recipe": replacement_recipe.model_dump(mode="json"),
                "expected_revision": saved["revision"],
                "expected_recipe_digest": saved["recipe_digest"],
            },
        )
        assert replaced_response.status_code == 200, replaced_response.text
        replaced = replaced_response.json()
        assert replaced["saved_roster_id"] == saved["saved_roster_id"]
        assert replaced["revision"] == saved["revision"] + 1
        assert replaced["recipe"]["roster_id"] == (
            replacement_recipe.roster_id
        )
        saved = replaced
        saved_recipe = replacement_recipe
        compose_body = {
            "title": "Saved Roster Duel",
            "roster_slots": [
                {
                    "roster_slot_id": "players",
                    "roster": {
                        "kind": "saved_roster",
                        "saved_roster_id": saved["saved_roster_id"],
                        "expected_revision": saved["revision"],
                        "expected_recipe_digest": saved["recipe_digest"],
                    },
                    "faction_id": "players",
                    "deployment_zone_id": "zone_1",
                    "controller_defaults": {
                        "controller": "human",
                        "participant_name": "Saved Party",
                        "policy_id": None,
                        "member_overrides": [],
                    },
                },
                {
                    "roster_slot_id": "opposition",
                    "roster": {
                        "kind": "authored_roster",
                        "roster_id": "monsters.skeleton_trio",
                    },
                    "faction_id": "opposition",
                    "deployment_zone_id": "zone_2",
                    "controller_defaults": {
                        "controller": "ai",
                        "participant_name": "Opposition",
                        "policy_id": "builtin.basic",
                        "member_overrides": [],
                    },
                },
            ],
            "battlefield_id": "battlefield.open_floor_bright",
            "deployment_id": "neutral.battlefield.open_floor_bright",
            "opening_policy": {
                "kind": "fixed_roster",
                "roster_slot_id": "players",
            },
        }

        composed = client.post(
            "/game-creation/compose",
            headers=_principal_headers(owner),
            json=compose_body,
        )
        assert composed.status_code == 200, composed.text
        assert composed.json()["recipe"]["roster_slots"][0]["roster"] == (
            saved_recipe.model_dump(mode="json")
        )

        unauthorized = client.post(
            "/game-creation/compose",
            headers=_principal_headers(other),
            json=compose_body,
        )
        assert unauthorized.status_code == 404

        compose_body["roster_slots"][0]["roster"]["expected_revision"] = (
            saved["revision"] + 1
        )
        stale = client.post(
            "/game-creation/compose",
            headers=_principal_headers(owner),
            json=compose_body,
        )
        assert stale.status_code == 400
        assert stale.json()["detail"]["code"] == (
            "game_creation_composition_invalid"
        )

    assert workers.active_game_ids() == ()
    repository.close()


def test_gateway_creates_reconnects_observes_and_stops_isolated_game(tmp_path: Path) -> None:
    """Cold handshakes create fresh hot capabilities without DB runtime access."""
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    workers = HostedWorkerManager(tmp_path / "runtime")
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
        assert created["creation"]["status"] == "prepared"
        assert created["game"]["lifecycle_state"] == "active"
        assert created["game"]["content_digest"] == (
            bootstrap_content_system().content_set_digest
        )
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
        assert bootstrap.json()["watermarks"]["source_event_cursor"] > 0
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


@pytest.mark.parametrize("second_controller", ["ai", "codex"])
def test_hosted_two_owned_characters_preserve_sources_and_member_controllers(
    tmp_path: Path,
    second_controller: str,
) -> None:
    """Hosted normalization, launch, authority, and pinning use one recipe."""
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    workers = HostedWorkerManager(tmp_path / "runtime")
    app = create_gateway_app(
        repository=repository,
        worker_manager=workers,
        authority_cache=RuntimeAuthorityCache(),
        capability_pepper=PEPPER,
    )
    with TestClient(app) as client:
        owner = client.post(
            "/directory/principals/guest",
            json={"display_name": "Two Character Owner"},
        ).json()
        first = _create_premade_character(
            client,
            owner,
            premade_id="hero.fighter_l5_shield_torch",
            display_name="First Owned",
        )
        second = _create_premade_character(
            client,
            owner,
            premade_id="hero.sorcerer_l5_standard_torch",
            display_name="Second Owned",
        )
        character_ids = (
            UUID(first["character"]["character_id"]),
            UUID(second["character"]["character_id"]),
        )
        composed = _compose_two_character_roster(
            client,
            owner,
            character_ids=character_ids,
            second_controller=second_controller,
        )
        created_response = client.post(
            "/games",
            json={
                "principal_id": owner["principal"]["principal_id"],
                "principal_capability": owner["principal_capability"],
                "display_name": "Two Owned Characters",
                "creation": {
                    "expected_content_set_digest": composed[
                        "content_set_digest"
                    ],
                    "expected_ruleset_digest": composed["ruleset_digest"],
                    "recipe": composed["recipe"],
                },
                "owner_roster_slot_id": "players",
                "visibility_policy": "private",
                "observer_policy": "disabled",
                "client_kind": "neuroclient",
                "client_instance_id": (
                    f"two-character-{second_controller}"
                ),
            },
        )
        assert created_response.status_code == 200, created_response.text
        created = created_response.json()
        game_id = UUID(created["game"]["game_id"])
        assignments = created["creation"]["rosters"][0][
            "entity_assignments"
        ]
        assert [UUID(row["character_id"]) for row in assignments] == list(
            character_ids,
        )
        assert [row["controller"] for row in assignments] == [
            "human",
            second_controller,
        ]
        assert created["connection"]["controlled_entity_uuids"] == [
            assignments[0]["entity_uuid"],
        ]
        if second_controller == "ai":
            assert assignments[1]["policy_id"] == "builtin.basic"
            assert assignments[1]["codex_session_id"] is None
        else:
            assert assignments[1]["policy_id"] is None
            assert assignments[1]["codex_session_id"] is not None
        for character_id, assignment in zip(
            character_ids,
            assignments,
            strict=True,
        ):
            lease = repository.get_active_character_deployment_lease(
                character_id,
            )
            assert lease is not None
            assert lease.game_id == game_id
            deployments = repository.list_character_deployments(
                character_id,
            )
            assert deployments[-1].game_id == game_id
            assert str(deployments[-1].entity_uuid) == assignment[
                "entity_uuid"
            ]

        stopped = client.post(
            f"/games/{game_id}/stop",
            json={
                "principal_id": owner["principal"]["principal_id"],
                "principal_capability": owner["principal_capability"],
            },
        )
        assert stopped.status_code == 200, stopped.text
        assert all(
            repository.get_active_character_deployment_lease(
                character_id,
            )
            is None
            for character_id in character_ids
        )
    repository.close()


def test_gateway_preserves_automatic_roster_and_attaches_owner_as_observer(
    tmp_path: Path,
) -> None:
    """Changing a controller never swaps combatants or grants false control."""
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
        recipe = _configured_recipe(
            first_controller=RosterControllerKind.AI,
        )
        body = _creation_body(owner, recipe=recipe)
        response = client.post("/games", json=body)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["creation"]["recipe_digest"] == recipe.recipe_digest
        assert payload["connection"]["access_mode"] == "observer"
        assert payload["connection"]["controlled_entity_uuids"] == []
        assert tuple(
            row["member_id"]
            for row in payload["creation"]["rosters"][0][
                "entity_assignments"
            ]
        ) == tuple(
            member.member_id
            for member in recipe.roster_slots[0].roster.members
        )
        stopped = client.post(
            f"/games/{payload['game']['game_id']}/stop",
            json={
                "principal_id": owner["principal"]["principal_id"],
                "principal_capability": owner["principal_capability"],
            },
        )
        assert stopped.status_code == 200
    repository.close()


def test_ai_match_publishes_canonical_terminal_evidence_from_terminal_event(
    tmp_path: Path,
) -> None:
    """A real worker publishes summary and both replays only after encounter end."""
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    workers = HostedWorkerManager(tmp_path / "runtime")
    app = create_gateway_app(
        repository=repository,
        worker_manager=workers,
        capability_pepper=PEPPER,
        artifact_root=tmp_path / "artifacts",
    )
    with TestClient(app) as client:
        owner = client.post(
            "/directory/principals/guest",
            json={"display_name": "Tournament Observer"},
        ).json()
        body = _creation_body(
            owner,
            recipe=_configured_recipe(
                encounter_id="encounter.sorcerer_barbarian_duel",
                first_controller=RosterControllerKind.AI,
                second_controller=RosterControllerKind.AI,
            ),
            owner_roster_slot_id=None,
        )
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
        artifacts = {
            artifact.artifact_kind: artifact
            for artifact in repository.list_artifacts(game_id)
        }
        assert {
            ArtifactKind.REPLAY_BUNDLE,
            ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE,
        } <= artifacts.keys()
        artifact_store = GameArtifactStore(tmp_path / "artifacts")
        objective = ObjectiveReplayBundle.model_validate_json(
            artifact_store.read_bytes(
                artifacts[ArtifactKind.REPLAY_BUNDLE].content_digest
            )
        )
        subjective = SubjectivePlayerReplayArchive.model_validate_json(
            artifact_store.read_bytes(
                artifacts[ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE].content_digest
            )
        )
        assert objective.terminal_event_cursor == game.final_event_cursor
        assert objective.terminal_combat_log_cursor == (
            game.final_combat_log_cursor
        )
        assert subjective.terminal_source_event_cursor == (
            game.final_event_cursor
        )
        assert subjective.terminal_combat_log_cursor == (
            game.final_combat_log_cursor
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


def test_small_terminal_evidence_archival_persists_within_half_second(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The deterministic cold archival path persists small evidence in 500 ms."""

    event_stream.stop()
    reset_engine_runtime()
    event_stream.ensure_attached()
    game_id = uuid4()
    scene = create_stream_scene()
    summary_store = WorkerGameSummaryStore()
    summary_store.bind_directory_game_id(scene.encounter.uuid, game_id)
    summary_store.capture_active_encounter(scene.encounter)
    execute_stream_attack(scene.hero, scene.monster, scene.encounter)
    scene.encounter.end_encounter("deterministic persistence fixture")
    evidence = summary_store.get_evidence(game_id)
    capture = summary_store.get_replay_capture(game_id)
    assert evidence is not None
    assert capture is not None
    replay = build_worker_objective_replay(
        capture,
        encounter=scene.encounter,
        stream=event_stream,
    )
    subjective = SubjectivePlayerReplayArchive(
        game_id=str(game_id),
        encounter_uuid=str(scene.encounter.uuid),
        terminal_source_event_cursor=capture.terminal_event_cursor,
        terminal_combat_log_cursor=capture.terminal_combat_log_cursor,
        opened_partition_count=0,
        membership_replays=(),
    )

    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    principal_capability = "terminal-fixture-capability"
    principal = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.SERVICE,
            display_name="Terminal Fixture",
            credential_hash=hash_capability(principal_capability, PEPPER),
        )
    )
    service = GameGatewayService(
        repository,
        HostedWorkerManager(tmp_path / "runtime"),
        RuntimeAuthorityCache(),
        GameArtifactStore(tmp_path / "artifacts"),
        capability_pepper=PEPPER,
    )
    worker_record = repository.create_worker(
        WorkerCreate(
            state=WorkerState.ACTIVE,
            pid=999_999,
            process_group_id=999_999,
            host_id="terminal-fixture",
            transport_kind=WorkerTransportKind.UNIX_SOCKET,
            private_locator=str(tmp_path / "terminal-fixture.sock"),
            protocol_hash="terminal-fixture",
            engine_version=ENGINE_VERSION,
        )
    )
    game = repository.create_game(
        GameCreate(
            game_id=game_id,
            worker_id=worker_record.worker_id,
            worker_generation=worker_record.worker_generation,
            created_by_principal_id=principal.principal_id,
            scenario_kind="test",
            scenario_id="small-terminal-evidence",
            display_name="Small Terminal Evidence",
            creation_manifest={},
            ruleset_version="test",
            engine_version=ENGINE_VERSION,
            content_digest="small-terminal-evidence",
        )
    )
    repository.transition_game(
        game_id,
        expected_row_version=game.row_version,
        lifecycle_state=GameLifecycleState.ACTIVE,
    )
    WorkerTerminalSpool(
        service.worker_manager.runtime_directory(game_id),
    ).publish(
        game_id=game_id,
        worker_instance_id=worker_record.worker_id,
        worker_generation=worker_record.worker_generation,
        summary=evidence,
        objective_replay=replay,
        subjective_replay=subjective,
    )

    async def persist() -> tuple[bool, float]:
        def reject_http(request: httpx.Request) -> httpx.Response:
            raise AssertionError(
                f"durable terminal adoption called worker HTTP at {request.url.path}",
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(reject_http),
            base_url="http://terminal-worker",
        ) as client:
            started_at = time.perf_counter()
            persisted = await service._persist_worker_summary_if_ready(
                game_id,
                client,
            )
            return persisted, time.perf_counter() - started_at

    try:
        persisted, elapsed = asyncio.run(persist())
        assert persisted is True
        assert elapsed < 0.5
        ended = repository.get_game(game_id)
        assert ended.lifecycle_state is GameLifecycleState.ENDED
        assert ended.final_event_cursor == replay.terminal_event_cursor
        assert ended.final_combat_log_cursor == replay.terminal_combat_log_cursor
        assert {
            artifact.artifact_kind
            for artifact in repository.list_artifacts(game_id)
        } == {
            ArtifactKind.REPLAY_BUNDLE,
            ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE,
        }
    finally:
        asyncio.run(service.close())
        repository.close()
        event_stream.stop()
        reset_engine_runtime()


def test_codex_grant_uses_public_subjective_runtime_over_native_fallback(
    tmp_path: Path,
) -> None:
    """A remote Codex process attaches without replacing native fallback."""
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
            json={"display_name": "Human Host"},
        ).json()
        body = _creation_body(
            owner,
            recipe=_configured_recipe(
                second_controller=RosterControllerKind.CODEX,
            ),
        )
        created_response = client.post("/games", json=body)
        assert created_response.status_code == 200, created_response.text
        created = created_response.json()
        game_id = UUID(created["game"]["game_id"])
        codex_assignment = created["creation"]["rosters"][1][
            "entity_assignments"
        ][0]
        codex_session_id = codex_assignment["codex_session_id"]
        assert codex_assignment["policy_id"] is None
        assert codex_assignment["policy_execution"] is None
        assert codex_assignment["provider_id"] is None
        assert codex_session_id

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
                "roster_slot_id": "roster_2",
                "member_id": codex_assignment["member_id"],
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
