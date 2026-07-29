"""Focused tests for durable player identity, characters, and reconnect policy."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

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


def _game_request(
    client: TestClient,
    identity: dict[str, object],
    character_id: str,
) -> dict[str, object]:
    """Compose once and return the exact hosted start request."""

    principal = identity["principal"]
    assert isinstance(principal, dict)
    composed = client.post(
        "/game-creation/compose",
        headers=_headers(identity),
        json={
            "title": "Persistent Hero Test",
            "roster_slots": [
                {
                    "roster_slot_id": "players",
                    "roster": {
                        "kind": "owned_characters",
                        "title": "Owned Character",
                        "character_ids": [character_id],
                        "member_controller_overrides": [],
                    },
                    "faction_id": "players",
                    "deployment_zone_id": "zone_1",
                    "controller_defaults": {
                        "controller": "human",
                        "participant_name": "Hero",
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
                        "participant_name": "Skeletons",
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
    assert composed.status_code == 200, composed.text
    normalized = composed.json()
    return {
        "principal_id": principal["principal_id"],
        "principal_capability": identity["principal_capability"],
        "display_name": "Persistent Hero Test",
        "creation": {
            "expected_content_set_digest": normalized[
                "content_set_digest"
            ],
            "expected_ruleset_digest": normalized["ruleset_digest"],
            "recipe": normalized["recipe"],
        },
        "owner_roster_slot_id": "players",
        "visibility_policy": "public",
        "observer_policy": "public",
        "client_kind": "neuroclient",
        "client_instance_id": "browser-a",
    }


def _create_premade_character(
    client: TestClient,
    identity: dict[str, object],
    *,
    premade_id: str,
    display_name: str,
) -> dict[str, object]:
    """Create one catalog premade through the canonical public route."""

    catalog_response = client.get("/character-creation/catalog")
    assert catalog_response.status_code == 200, catalog_response.text
    plan = next(
        row
        for row in catalog_response.json()["creation_plans"]
        if row["source_premade_id"] == premade_id
    )
    profile_response = client.get(
        "/directory/players/me",
        headers=_headers(identity),
    )
    assert profile_response.status_code == 200, profile_response.text
    profile = profile_response.json()
    response = client.post(
        "/directory/characters",
        headers=_headers(identity),
        json={
            "display_name": display_name,
            "build": plan["build"],
            "loadout": plan["loadout"],
            "creation_plan_id": plan["plan_id"],
            "creation_plan_digest": plan["plan_digest"],
            "expected_content_set_digest": (
                catalog_response.json()["content_set_digest"]
            ),
            "expected_ruleset_digest": profile["settings"]["ruleset_digest"],
            "idempotency_key": str(uuid4()),
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["definition"]["definition"]["premade_id"] == premade_id
    return payload


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
        profile = client.get(
            "/directory/players/me",
            headers=_headers(first_identity),
        )
        assert profile.status_code == 200
        assert profile.json()["settings"]["settings_version"] == 1
        assert (
            profile.json()["settings"]["multiclass_slot_rounding_policy"]
            == "srd_5_2_round_up"
        )
        assert client.get("/directory/players/me", headers=_headers(second_identity)).status_code == 200

        updated = client.put(
            "/directory/players/me/settings",
            headers=_headers(second_identity),
            json={
                "expected_settings_version": 1,
                "permissive_multiclass_prerequisites": False,
                "multiclass_slot_rounding_policy": "srd_5_1_round_down",
                "allow_respec": False,
                "spell_preparation_policy": "out_of_combat",
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["settings_version"] == 2
        assert updated.json()["permissive_multiclass_prerequisites"] is False
        assert updated.json()["ruleset_digest"] != profile.json()["settings"][
            "ruleset_digest"
        ]

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
    workers = HostedWorkerManager(tmp_path / "runtime")
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

        character = _create_premade_character(
            client,
            browser_a,
            display_name="Sol",
            premade_id="hero.sorcerer_l5_standard_torch",
        )["character"]
        assert character["revision_state"] == "canonical"
        assert character["current_definition_revision"] == 1
        assert character["current_holdings_revision"] == 1

        definition_response = client.get(
            f"/directory/characters/{character['character_id']}/definition",
            headers=_headers(browser_b),
        )
        assert definition_response.status_code == 200, definition_response.text
        definition_record = definition_response.json()
        assert definition_record["definition"]["character_id"] == character["character_id"]
        assert (
            definition_record["definition"]["premade_id"]
            == "hero.sorcerer_l5_standard_torch"
        )
        assert definition_record["definition"]["schema_version"] == 2
        assert definition_record["definition"]["earned_character_level"] == 5
        assert definition_record["definition"]["body_recipe"]["ref"][
            "definition_kind"
        ] == "creature"

        denied_definition = client.get(
            f"/directory/characters/{character['character_id']}/definition",
            headers=_headers(stranger),
        )
        assert denied_definition.status_code == 403
        assert denied_definition.json()["detail"]["code"] == "character_not_owned"

        created_response = client.post(
            "/games",
            json=_game_request(
                client,
                browser_a,
                character["character_id"],
            ),
        )
        assert created_response.status_code == 200, created_response.text
        created = created_response.json()
        game_id = created["game"]["game_id"]
        membership_id = created["connection"]["membership"]["membership_id"]
        session_id = created["connection"]["runtime_session_id"]
        first_token = created["connection"]["runtime_token"]
        runtime_bootstrap = f"/games/{game_id}/runtime/replication/bootstrap"
        controlled_entity_uuid = created["connection"][
            "controlled_entity_uuids"
        ][0]

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
        actions_response = client.get(
            (
                f"/games/{game_id}/runtime/entity/"
                f"{controlled_entity_uuid}/available-actions"
            ),
            params={"session_id": session_id},
            headers={"Authorization": f"Bearer {first_token}"},
        )
        assert actions_response.status_code == 200, actions_response.text
        action_rows = [
            row
            for key in (
                "entity_actions",
                "position_actions",
                "self_actions",
                "object_actions",
            )
            for row in actions_response.json()[key]
        ]
        assert any(
            "Fire Bolt" in {
                row.get("name"),
                row.get("template_name"),
            }
            for row in action_rows
        )
        assert not any(
            "Action Surge" in {
                row.get("name"),
                row.get("template_name"),
            }
            for row in action_rows
        )
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
        assert deployments[0].pin_state == "pinned"
        assert deployments[0].definition_revision == 1
        assert deployments[0].holdings_revision == 1

    repository.close()


def test_character_head_change_during_worker_start_fails_and_releases_lease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A worker may not launch a snapshot whose durable heads moved meanwhile."""

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
        identity = client.post(
            "/directory/players/identify",
            json={
                "display_name": "Racing Player",
                "client_instance_id": "browser-a",
            },
        ).json()
        character = _create_premade_character(
            client,
            identity,
            display_name="Racing Sorcerer",
            premade_id="hero.sorcerer_l5_standard_torch",
        )
        character_id = UUID(character["character"]["character_id"])
        acquire = repository.acquire_character_deployment_leases

        def acquire_after_concurrent_mutation(
            requests,
        ):
            assert requests
            with repository._database.transaction(
                "test_concurrent_character_mutation",
            ) as connection:
                connection.execute(
                    """
                    UPDATE characters
                    SET row_version = row_version + 1
                    WHERE character_id = ?
                    """,
                    (str(requests[0].character_id),),
                )
            return acquire(requests)

        monkeypatch.setattr(
            repository,
            "acquire_character_deployment_leases",
            acquire_after_concurrent_mutation,
        )

        response = client.post(
            "/games",
            json=_game_request(client, identity, str(character_id)),
        )

        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == (
            "character_heads_changed_during_deployment"
        )
        assert (
            repository.get_active_character_deployment_lease(character_id)
            is None
        )
        assert workers.active_game_ids() == ()

    repository.close()
