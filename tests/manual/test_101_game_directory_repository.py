"""Focused durability and authority tests for the game-directory repository."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from dnd.scenarios.encounter_catalog import AUTHORED_ENCOUNTER_RECIPES_BY_ID
from server.game_directory.contracts import (
    AccessGrantCreate,
    ArtifactCreate,
    ArtifactKind,
    AttachmentCreate,
    ClientKind,
    EntityAssignmentCreate,
    ExecutionKind,
    GameCreate,
    GameLifecycleState,
    GrantKind,
    MembershipCapabilities,
    MembershipCreate,
    MembershipRole,
    PrincipalCreate,
    PrincipalKind,
    ProducerKind,
    VisibilityPolicy,
    WorkerCreate,
    WorkerState,
    WorkerTransportKind,
)
from server.game_directory.errors import ConflictError, StaleVersionError
from server.game_directory.repository import GameDirectoryRepository

NOW = datetime(2026, 7, 21, 18, 30, tzinfo=UTC)
PEPPER = b"restart-stable-test-pepper"


def _open(path: Path) -> GameDirectoryRepository:
    """Open a deterministic repository for restart tests."""

    return GameDirectoryRepository(path, capability_pepper=PEPPER, clock=lambda: NOW)


def test_full_control_plane_round_trip_survives_restart_without_plaintext_secrets(
    tmp_path: Path,
) -> None:
    """Game placement, authority, reconnect identity, and evidence survive restart."""

    database_path = tmp_path / "directory.sqlite3"
    repository = _open(database_path)
    principal = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Player One",
            metadata={"locale": "en"},
        )
    )
    worker = repository.create_worker(
        WorkerCreate(
            state=WorkerState.READY,
            pid=42001,
            process_group_id=42001,
            host_id="local-wsl",
            transport_kind=WorkerTransportKind.UNIX_SOCKET,
            private_locator="/tmp/dnd-worker-a.sock",
            protocol_hash="protocol-v1",
            engine_version="engine-test",
        )
    )
    game = repository.create_game(
        GameCreate(
            worker_id=worker.worker_id,
            worker_generation=worker.worker_generation,
            created_by_principal_id=principal.principal_id,
            lifecycle_state=GameLifecycleState.STARTING,
            visibility_policy=VisibilityPolicy.UNLISTED,
            scenario_kind="arena",
            scenario_id="bridge",
            display_name="Bridge Test",
            creation_manifest={"arena_id": "bridge", "sides": ["heroes", "monsters"]},
            seed=73,
            ruleset_version="bg3-single-v1",
            engine_version="engine-test",
            content_digest="content-abc",
        )
    )
    game = repository.transition_game(
        game.game_id,
        expected_row_version=game.row_version,
        lifecycle_state=GameLifecycleState.ACTIVE,
        engine_game_id=uuid4(),
    )
    membership = repository.create_membership(
        MembershipCreate(
            game_id=game.game_id,
            principal_id=principal.principal_id,
            role=MembershipRole.PLAYER,
            side_id="heroes",
            controller_kind="human",
            capabilities=MembershipCapabilities(
                may_connect=True,
                may_observe_public_state=True,
                may_control_entities=True,
            ),
        )
    )
    entity_uuid = uuid4()
    assignment = repository.assign_entity(
        EntityAssignmentCreate(
            game_id=game.game_id,
            membership_id=membership.membership_id,
            entity_uuid=entity_uuid,
            entity_name="Hero",
            faction="heroes",
            side_id="heroes",
            controller_kind="human",
            authority_epoch=membership.authority_epoch,
        )
    )
    issued_grant = repository.issue_access_grant(
        AccessGrantCreate(
            game_id=game.game_id,
            membership_id=membership.membership_id,
            issued_to_principal_id=principal.principal_id,
            grant_kind=GrantKind.RECONNECT,
            scope={"mode": "control", "side_id": "heroes"},
            expires_at=NOW + timedelta(hours=2),
            max_uses=3,
            issued_by_principal_id=principal.principal_id,
        )
    )
    runtime_session_id = uuid4()
    first_attachment = repository.open_attachment(
        AttachmentCreate(
            runtime_session_id=runtime_session_id,
            game_id=game.game_id,
            membership_id=membership.membership_id,
            worker_id=worker.worker_id,
            worker_generation=worker.worker_generation,
            client_kind=ClientKind.NEUROCLIENT,
            client_instance_id="browser-tab-a",
            authority_epoch=membership.authority_epoch,
        )
    )
    repository.close_attachment(
        first_attachment.attachment.attachment_id,
        reason="browser_reload",
        last_event_cursor=41,
        last_combat_log_cursor=17,
    )
    second_attachment = repository.open_attachment(
        AttachmentCreate(
            runtime_session_id=runtime_session_id,
            game_id=game.game_id,
            membership_id=membership.membership_id,
            worker_id=worker.worker_id,
            worker_generation=worker.worker_generation,
            client_kind=ClientKind.NEUROCLIENT,
            client_instance_id="browser-tab-b",
            authority_epoch=membership.authority_epoch,
        )
    )
    artifact = repository.publish_artifact(
        ArtifactCreate(
            game_id=game.game_id,
            artifact_kind=ArtifactKind.CREATION_MANIFEST,
            schema_version="dnd.creation.v1",
            media_type="application/json",
            uri="artifacts/creation-abc.json",
            byte_size=128,
            content_digest="a" * 64,
            producer_kind=ProducerKind.DIRECTORY,
            producer_version="phase-1",
        )
    )
    repository.close()

    raw = sqlite3.connect(database_path)
    persisted_grant_hash = raw.execute(
        "SELECT secret_hash FROM access_grants WHERE grant_id = ?",
        (str(issued_grant.grant.grant_id),),
    ).fetchone()[0]
    persisted_runtime_hashes = {
        row[0]
        for row in raw.execute(
            "SELECT runtime_token_hash FROM attachments WHERE membership_id = ?",
            (str(membership.membership_id),),
        ).fetchall()
    }
    raw.close()

    assert persisted_grant_hash != issued_grant.capability
    assert issued_grant.capability not in persisted_grant_hash
    assert first_attachment.runtime_token not in persisted_runtime_hashes
    assert second_attachment.runtime_token not in persisted_runtime_hashes
    assert len(persisted_runtime_hashes) == 2

    restarted = _open(database_path)
    assert restarted.get_principal(principal.principal_id) == principal
    assert restarted.get_worker(worker.worker_id) == worker
    assert restarted.get_game(game.game_id) == game
    assert restarted.get_membership(membership.membership_id) == membership
    assert restarted.list_entity_assignments(game.game_id) == (assignment,)
    assert restarted.list_artifacts(game.game_id) == (artifact,)
    latest = restarted.get_latest_attachment_for_membership(membership.membership_id)
    assert latest.attachment_id == second_attachment.attachment.attachment_id
    assert latest.runtime_session_id == runtime_session_id
    assert restarted.verify_access_grant(
        issued_grant.grant.grant_id,
        issued_grant.capability,
        consume=True,
    ).uses == 1
    restarted.close()


def test_authority_and_lifecycle_updates_use_compare_and_swap(tmp_path: Path) -> None:
    """Stale game rows and membership epochs cannot overwrite current authority."""

    repository = _open(tmp_path / "directory.sqlite3")
    principal = repository.create_principal(
        PrincipalCreate(principal_kind=PrincipalKind.HUMAN, display_name="Owner")
    )
    game = repository.create_game(
        GameCreate(
            created_by_principal_id=principal.principal_id,
            scenario_kind="arena",
            scenario_id="test",
            display_name="CAS Test",
            creation_manifest={},
            ruleset_version="one-ruleset",
            engine_version="test",
            content_digest="content",
        )
    )
    transitioned = repository.transition_game(
        game.game_id,
        expected_row_version=game.row_version,
        lifecycle_state=GameLifecycleState.STARTING,
    )
    assert transitioned.row_version == game.row_version + 1
    with pytest.raises(StaleVersionError):
        repository.transition_game(
            game.game_id,
            expected_row_version=game.row_version,
            lifecycle_state=GameLifecycleState.ACTIVE,
        )

    membership = repository.create_membership(
        MembershipCreate(
            game_id=game.game_id,
            principal_id=principal.principal_id,
            role=MembershipRole.OWNER,
            capabilities=MembershipCapabilities(may_connect=True, may_manage_game=True),
        )
    )
    updated = repository.update_membership_authority(
        membership.membership_id,
        expected_authority_epoch=membership.authority_epoch,
        membership_state=membership.membership_state,
        capabilities=MembershipCapabilities(
            may_connect=True,
            may_manage_game=True,
            may_manage_members=True,
        ),
    )
    assert updated.authority_epoch == membership.authority_epoch + 1
    with pytest.raises(StaleVersionError):
        repository.update_membership_authority(
            membership.membership_id,
            expected_authority_epoch=membership.authority_epoch,
            membership_state=membership.membership_state,
            capabilities=membership.capabilities,
        )
    repository.close()


def test_local_game_execution_kind_round_trips_through_repository(tmp_path: Path) -> None:
    """A single-player local game is a first-class durable directory record."""

    database_path = tmp_path / "local-profile.sqlite3"
    repository = _open(database_path)
    principal = repository.create_principal(
        PrincipalCreate(principal_kind=PrincipalKind.HUMAN, display_name="Local Player")
    )
    created = repository.create_game(
        GameCreate(
            created_by_principal_id=principal.principal_id,
            execution_kind=ExecutionKind.LOCAL,
            scenario_kind="arena",
            scenario_id="single-player",
            display_name="Local Adventure",
            creation_manifest={"profile_mode": "single_player"},
            ruleset_version="one-ruleset",
            engine_version="test",
            content_digest="content",
        )
    )
    repository.close()

    restarted = _open(database_path)
    loaded = restarted.get_game(created.game_id)
    restarted.close()

    assert created.execution_kind is ExecutionKind.LOCAL
    assert loaded == created
    assert loaded.execution_kind is ExecutionKind.LOCAL


def test_historical_launch_manifest_exposes_its_exact_encounter_recipe(
    tmp_path: Path,
) -> None:
    """History does not decode an old launch envelope as today's request DTO."""
    repository = _open(tmp_path / "historical-recipe.sqlite3")
    principal = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Historical Player",
        ),
    )
    recipe = AUTHORED_ENCOUNTER_RECIPES_BY_ID[
        "encounter.standard_skeleton_doors"
    ]
    created = repository.create_game(
        GameCreate(
            created_by_principal_id=principal.principal_id,
            execution_kind=ExecutionKind.LOCAL,
            scenario_kind="encounter_recipe",
            scenario_id=recipe.encounter_id,
            display_name=recipe.title,
            creation_manifest={
                "recipe": recipe.model_dump(mode="json"),
                "expected_ruleset_digest": "1" * 64,
            },
            ruleset_version="one-ruleset",
            engine_version="test",
            content_digest="0" * 64,
        ),
    )
    repository.close()

    assert created.encounter_recipe == recipe
    assert "expected_content_set_digest" not in created.creation_manifest


def test_cross_game_entity_assignment_is_rejected(tmp_path: Path) -> None:
    """A membership cannot control an entity belonging to another game."""

    repository = _open(tmp_path / "directory.sqlite3")
    principal = repository.create_principal(
        PrincipalCreate(principal_kind=PrincipalKind.HUMAN, display_name="Player")
    )
    games = [
        repository.create_game(
            GameCreate(
                created_by_principal_id=principal.principal_id,
                scenario_kind="arena",
                scenario_id=f"arena-{index}",
                display_name=f"Game {index}",
                creation_manifest={"index": index},
                ruleset_version="one-ruleset",
                engine_version="test",
                content_digest="content",
            )
        )
        for index in range(2)
    ]
    membership = repository.create_membership(
        MembershipCreate(
            game_id=games[0].game_id,
            principal_id=principal.principal_id,
            role=MembershipRole.PLAYER,
            capabilities=MembershipCapabilities(may_connect=True, may_control_entities=True),
        )
    )
    with pytest.raises(ConflictError, match="different games"):
        repository.assign_entity(
            EntityAssignmentCreate(
                game_id=games[1].game_id,
                membership_id=membership.membership_id,
                entity_uuid=uuid4(),
                entity_name="Wrong World Hero",
                controller_kind="human",
                authority_epoch=membership.authority_epoch,
            )
        )
    repository.close()
