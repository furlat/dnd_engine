"""Focused tests for durable player identity, characters, and reconnect policy."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from ai.game_server_profiles import EMBEDDED_AI_WORKER_APPLICATION
from server.game_directory.repository import GameDirectoryRepository
from server.game_gateway import create_gateway_app
from server.hosted_worker import HostedWorkerManager
from server.runtime_authority import RuntimeAuthorityCache


PEPPER = b"player-identity-test-pepper"


def _headers(identity: dict[str, object]) -> dict[str, str]:
    """Return principal authentication headers for a typed identity response."""

    principal = identity["principal"]
    assert isinstance(principal, dict)
    return {
        "X-Dnd-Principal-Id": str(principal["principal_id"]),
        "X-Dnd-Principal-Capability": str(identity["principal_capability"]),
    }


def _game_request(identity: dict[str, object], character_id: str) -> dict[str, object]:
    """Return one composed game that deploys the persistent Sorcerer."""

    principal = identity["principal"]
    assert isinstance(principal, dict)
    return {
        "principal_id": principal["principal_id"],
        "principal_capability": identity["principal_capability"],
        "display_name": "Persistent Hero Test",
        "creation": {
            "scenario": {
                "kind": "composed",
                "hero_configuration_id": "hero.sorcerer_l5_standard_torch",
                "monster_configuration_id": "monsters.skeleton_trio",
                "battlefield_id": "battlefield.standard_hazards_closed",
                "deployment_id": "neutral.battlefield.standard_hazards_closed",
            },
            "side_a": {"controller": "human", "name": "Hero"},
            "side_b": {"controller": "ai", "name": "Skeletons"},
            "opening_side": "side_a",
        },
        "owner_side": "side_a",
        "visibility_policy": "public",
        "observer_policy": "public",
        "client_kind": "neuroclient",
        "client_instance_id": "browser-a",
        "character_id": character_id,
    }


def test_name_identity_is_shared_while_browser_credentials_are_independent(
    tmp_path: Path,
) -> None:
    """Case and whitespace variants resolve one principal with separate secrets."""

    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    app = create_gateway_app(
        repository=repository,
        worker_manager=HostedWorkerManager(tmp_path / "runtime"),
        capability_pepper=PEPPER,
    )
    with TestClient(app) as client:
        first = client.post(
            "/directory/players/identify",
            json={"display_name": "  Tommaso  ", "client_instance_id": "browser-a"},
        )
        second = client.post(
            "/directory/players/identify",
            json={"display_name": "tommaso", "client_instance_id": "browser-b"},
        )

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        first_identity = first.json()
        second_identity = second.json()
        assert first_identity["principal"]["principal_id"] == second_identity["principal"]["principal_id"]
        assert first_identity["credential_id"] != second_identity["credential_id"]
        assert first_identity["principal_capability"] != second_identity["principal_capability"]
        assert first_identity["authentication_kind"] == "name_only_local"
        assert client.get("/directory/players/me", headers=_headers(first_identity)).status_code == 200
        assert client.get("/directory/players/me", headers=_headers(second_identity)).status_code == 200

    repository.close()


def test_character_deployment_and_parallel_or_replacing_reconnect(
    tmp_path: Path,
) -> None:
    """Identity ownership survives browsers and controls explicit attachment policy."""

    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    authority_cache = RuntimeAuthorityCache()
    workers = HostedWorkerManager(
        tmp_path / "runtime",
        worker_application=EMBEDDED_AI_WORKER_APPLICATION,
        startup_timeout_seconds=20.0,
    )
    app = create_gateway_app(
        repository=repository,
        worker_manager=workers,
        authority_cache=authority_cache,
        capability_pepper=PEPPER,
    )
    with TestClient(app) as client:
        browser_a = client.post(
            "/directory/players/identify",
            json={"display_name": "Tommaso", "client_instance_id": "browser-a"},
        ).json()
        browser_b = client.post(
            "/directory/players/identify",
            json={"display_name": "TOMMASO", "client_instance_id": "browser-b"},
        ).json()
        stranger = client.post(
            "/directory/players/identify",
            json={"display_name": "Someone Else", "client_instance_id": "browser-c"},
        ).json()

        character_response = client.post(
            "/directory/characters",
            headers=_headers(browser_a),
            json={
                "display_name": "Sol",
                "preset_configuration_id": "hero.sorcerer_l5_standard_torch",
            },
        )
        assert character_response.status_code == 200, character_response.text
        character = character_response.json()

        created_response = client.post(
            "/games",
            json=_game_request(browser_a, character["character_id"]),
        )
        assert created_response.status_code == 200, created_response.text
        created = created_response.json()
        game_id = created["game"]["game_id"]
        membership_id = created["connection"]["membership"]["membership_id"]
        session_id = created["connection"]["runtime_session_id"]
        first_token = created["connection"]["runtime_token"]
        runtime_bootstrap = f"/games/{game_id}/runtime/replication/bootstrap"

        profile = client.get("/directory/players/me", headers=_headers(browser_b))
        assert profile.status_code == 200, profile.text
        assert [row["character_id"] for row in profile.json()["characters"]] == [
            character["character_id"]
        ]
        seat = next(
            row
            for row in profile.json()["game_seats"]
            if row["membership"]["membership_id"] == membership_id
        )
        assert len(seat["active_attachments"]) == 1

        denied = client.post(
            f"/games/{game_id}/reconnect",
            json={
                "principal_id": stranger["principal"]["principal_id"],
                "principal_capability": stranger["principal_capability"],
                "membership_id": membership_id,
                "client_kind": "neuroclient",
                "client_instance_id": "browser-c",
                "attachment_policy": "parallel",
            },
        )
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "membership_not_owned"

        parallel_response = client.post(
            f"/games/{game_id}/reconnect",
            json={
                "principal_id": browser_b["principal"]["principal_id"],
                "principal_capability": browser_b["principal_capability"],
                "membership_id": membership_id,
                "client_kind": "neuroclient",
                "client_instance_id": "browser-b",
                "attachment_policy": "parallel",
            },
        )
        assert parallel_response.status_code == 200, parallel_response.text
        parallel = parallel_response.json()
        assert parallel["replaced_attachment_ids"] == []
        assert parallel["connection"]["runtime_session_id"] == session_id
        second_token = parallel["connection"]["runtime_token"]
        assert client.get(
            runtime_bootstrap,
            params={"session_id": session_id},
            headers={"Authorization": f"Bearer {first_token}"},
        ).status_code == 200
        assert client.get(
            runtime_bootstrap,
            params={"session_id": session_id},
            headers={"Authorization": f"Bearer {second_token}"},
        ).status_code == 200

        replace_response = client.post(
            f"/games/{game_id}/reconnect",
            json={
                "principal_id": browser_b["principal"]["principal_id"],
                "principal_capability": browser_b["principal_capability"],
                "membership_id": membership_id,
                "client_kind": "neuroclient",
                "client_instance_id": "browser-b-replacement",
                "attachment_policy": "replace_existing",
            },
        )
        assert replace_response.status_code == 200, replace_response.text
        replaced = replace_response.json()
        assert len(replaced["replaced_attachment_ids"]) == 2
        assert client.get(
            runtime_bootstrap,
            params={"session_id": session_id},
            headers={"Authorization": f"Bearer {first_token}"},
        ).status_code == 403
        assert client.get(
            runtime_bootstrap,
            params={"session_id": session_id},
            headers={"Authorization": f"Bearer {second_token}"},
        ).status_code == 403
        assert client.get(
            runtime_bootstrap,
            params={"session_id": session_id},
            headers={"Authorization": f"Bearer {replaced['connection']['runtime_token']}"},
        ).status_code == 200

        deployments = repository.list_character_deployments(UUID(character["character_id"]))
        assert len(deployments) == 1
        assert str(deployments[0].game_id) == game_id
        assert str(deployments[0].entity_uuid) in created["connection"]["controlled_entity_uuids"]

    repository.close()
