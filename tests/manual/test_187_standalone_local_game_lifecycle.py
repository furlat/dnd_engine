"""Standalone local games use the durable directory lifecycle and leases."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.core.events import EventQueue
from dnd.core.life_types import LifeState
from dnd.entity import Entity
from server.character_directory_contracts import (
    CharacterLoadoutMutationRequest,
    CharacterLoadoutDraft,
    CreateCharacterRequest,
)
from server.character_directory_service import CharacterDirectoryService
from server.game_directory.contracts import (
    ArtifactCreate,
    ExecutionKind,
    GameLifecycleState,
)
from server.game_directory.errors import ConflictError
from server.game_directory.local_profiles import LocalProfileManager
from server.local_game_lifecycle import StandaloneLocalGameCoordinator
from server import event_server


_PEPPER = b"standalone-local-game-lifecycle"


def _create_character(
    service: CharacterDirectoryService,
    owner_id: UUID,
) -> UUID:
    catalog = service.build_creation_catalog()
    premade = next(
        row
        for row in catalog.premades
        if row.premade_id == "hero.fighter_2_sorcerer_3_spellblade"
    )
    settings = service.ensure_profile_settings(owner_id)
    created = service.create_character(
        owner_id,
        CreateCharacterRequest(
            display_name="Spellblade",
            build=premade.build,
            loadout=CharacterLoadoutDraft(),
            expected_content_set_digest=catalog.content_set_digest,
            expected_ruleset_digest=settings.ruleset_digest,
            idempotency_key=uuid4(),
        ),
    )
    return created.character.character_id


def _coordinator(
    tmp_path: Path,
    *,
    on_mutation: Callable[[], None] | None = None,
) -> tuple[
    StandaloneLocalGameCoordinator,
    CharacterDirectoryService,
    UUID,
]:
    manager = LocalProfileManager(
        capability_pepper=_PEPPER,
        runtime_root=tmp_path,
    )
    handle = manager.create_profile("Local Player")
    content_system = bootstrap_content_system()
    service = CharacterDirectoryService(handle.repository, content_system)
    coordinator = StandaloneLocalGameCoordinator(
        repository=handle.repository,
        character_directory=service,
        artifact_root=handle.artifacts_root,
        owner_principal_id=handle.profile_id,
        content_digest=content_system.content_set_digest,
        on_mutation=on_mutation,
    )
    return coordinator, service, handle.profile_id


def test_local_lifecycle_notifies_after_each_durable_boundary(
    tmp_path: Path,
) -> None:
    """Open SSE subscribers observe every lifecycle event-producing boundary."""

    notifications: list[int] = []
    coordinator, service, owner_id = _coordinator(
        tmp_path,
        on_mutation=lambda: notifications.append(
            len(
                service.repository.list_directory_events(
                    since_cursor=0,
                    limit=1_000,
                )
            ),
        ),
    )
    character_id = _create_character(service, owner_id)

    coordinator.prepare(
        creation_manifest={"kind": "test"},
        scenario_kind="composed",
        scenario_id="fixture.directory-notifications",
        display_name="Directory Notifications",
        character_id=character_id,
    )
    coordinator.pin_character(uuid4())
    coordinator.activate()
    coordinator.interrupt("test_complete")

    assert len(notifications) == 3
    assert notifications == sorted(notifications)
    assert len(set(notifications)) == 3


def _drive_ai_game_to_terminal_boundary(
    client: TestClient,
    coordinator: StandaloneLocalGameCoordinator,
    game_id: UUID,
    *,
    expect_staged_intent: bool,
) -> None:
    """Run AI turns serially through the public simulation control surface."""

    paused = client.post("/simulation/pause")
    assert paused.status_code == 200, paused.text
    for _turn in range(500):
        game = coordinator.repository.get_game(game_id)
        pending = coordinator.repository.get_pending_local_terminal_commit(
            game_id,
        )
        if expect_staged_intent and pending is not None:
            return
        if (
            not expect_staged_intent
            and game.lifecycle_state is GameLifecycleState.ENDED
        ):
            return
        stepped = client.post("/simulation/step")
        assert stepped.status_code == 200, stepped.text
    pytest.fail(
        "AI game did not reach its terminal persistence boundary within "
        "500 serial turns",
    )


def test_prepare_pins_local_game_identity_and_exclusively_leases_character(
    tmp_path: Path,
) -> None:
    coordinator, service, owner_id = _coordinator(tmp_path)
    character_id = _create_character(service, owner_id)

    prepared = coordinator.prepare(
        creation_manifest={"kind": "test"},
        scenario_kind="composed",
        scenario_id="fixture.spellblade",
        display_name="Spellblade Test",
        character_id=character_id,
    )

    assert prepared.character_snapshot is not None
    assert prepared.character_snapshot.character_id == character_id
    assert prepared.game.execution_kind is ExecutionKind.LOCAL
    assert prepared.game.lifecycle_state is GameLifecycleState.STARTING
    assert prepared.game.engine_game_id is None
    assert prepared.membership.game_id == prepared.game.game_id
    assert prepared.membership.principal_id == owner_id
    active_lease = service.repository.get_active_character_deployment_lease(
        character_id,
    )
    assert active_lease is not None
    assert active_lease.lease_id == prepared.lease_id

    snapshot = service.get_character_snapshot(owner_id, character_id)
    with pytest.raises(ConflictError, match="active deployment"):
        service.update_loadout(
            owner_id,
            character_id,
            CharacterLoadoutMutationRequest(
                idempotency_key=uuid4(),
                expected_row_version=snapshot.character.row_version,
                expected_heads=snapshot.heads,
                loadout=CharacterLoadoutDraft(),
                expected_content_set_digest=(
                    service.content_system.content_set_digest
                ),
                expected_ruleset_digest=(
                    service.ensure_profile_settings(owner_id).ruleset_digest
                ),
            ),
        )

    deployment = coordinator.pin_character(uuid4())
    assert deployment is not None
    assert deployment.lease_id == prepared.lease_id
    assert deployment.game_id == prepared.game.game_id
    assert deployment.pin_state == "pinned"

    active = coordinator.activate()
    assert active.lifecycle_state is GameLifecycleState.ACTIVE
    assert active.engine_game_id == prepared.game.game_id

    interrupted = coordinator.interrupt("test_interrupted")
    assert interrupted is not None
    assert interrupted.lifecycle_state is GameLifecycleState.INTERRUPTED
    assert (
        service.repository.get_active_character_deployment_lease(character_id)
        is None
    )


def test_recover_marks_abandoned_local_games_interrupted_and_releases_leases(
    tmp_path: Path,
) -> None:
    coordinator, service, owner_id = _coordinator(tmp_path)
    character_id = _create_character(service, owner_id)
    prepared = coordinator.prepare(
        creation_manifest={"kind": "test"},
        scenario_kind="composed",
        scenario_id="fixture.crash",
        display_name="Crash Recovery",
        character_id=character_id,
    )

    recovered = StandaloneLocalGameCoordinator(
        repository=service.repository,
        character_directory=service,
        artifact_root=tmp_path / "profiles" / str(owner_id) / "artifacts",
        owner_principal_id=owner_id,
        content_digest=bootstrap_content_system().content_set_digest,
    ).recover_abandoned_games()

    assert recovered == (prepared.game.game_id,)
    assert (
        service.repository.get_game(prepared.game.game_id).lifecycle_state
        is GameLifecycleState.INTERRUPTED
    )
    assert (
        service.repository.get_active_character_deployment_lease(character_id)
        is None
    )


def test_nonreplay_termination_rolls_back_lease_release_when_transition_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator, service, owner_id = _coordinator(tmp_path)
    character_id = _create_character(service, owner_id)
    prepared = coordinator.prepare(
        creation_manifest={"kind": "test"},
        scenario_kind="composed",
        scenario_id="fixture.atomic-interrupt",
        display_name="Atomic Interrupt",
        character_id=character_id,
    )
    coordinator.activate()
    original_transition = (
        service.repository._transition_game_in_transaction
    )

    def fail_after_lease_release(*_args, **_kwargs):
        raise RuntimeError("injected transition failure")

    monkeypatch.setattr(
        service.repository,
        "_transition_game_in_transaction",
        fail_after_lease_release,
    )
    with pytest.raises(RuntimeError, match="injected transition failure"):
        coordinator.interrupt("injected_atomicity_test")

    assert (
        service.repository.get_game(prepared.game.game_id).lifecycle_state
        is GameLifecycleState.ACTIVE
    )
    assert (
        service.repository.get_active_character_deployment_lease(character_id)
        is not None
    )

    monkeypatch.setattr(
        service.repository,
        "_transition_game_in_transaction",
        original_transition,
    )
    interrupted = coordinator.interrupt("injected_atomicity_test")
    assert interrupted is not None
    assert interrupted.lifecycle_state is GameLifecycleState.INTERRUPTED
    assert (
        service.repository.get_active_character_deployment_lease(character_id)
        is None
    )


def test_terminal_commit_callback_is_ordered_after_subjective_replay_finalizer(
) -> None:
    """The durable terminal barrier must follow canonical replay sealing."""

    event_server.canonical_subjective_replication_runtime.ensure_attached()
    event_server._ensure_local_terminal_callback()
    callbacks = EventQueue._on_event_batch_callbacks
    assert callbacks.index(
        event_server.canonical_subjective_replication_runtime._on_event_batch,
    ) < callbacks.index(event_server._on_local_terminal_event_batch)


def test_terminal_publication_retries_once_when_subjective_replay_becomes_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient open segment commits on its exact close signal without polling."""

    encounter_uuid = uuid4()
    game_id = uuid4()
    fake_encounter = object()

    class FakeCoordinator:
        def __init__(self) -> None:
            self.current = SimpleNamespace(
                game=SimpleNamespace(game_id=game_id),
            )
            self.complete_calls = 0

        def complete_terminal(self, **_kwargs: object) -> object:
            self.complete_calls += 1
            self.current = None
            return object()

    coordinator = FakeCoordinator()
    subjective_attempts = 0
    cleanup_calls = 0

    def build_subjective(_capture: object) -> object:
        nonlocal subjective_attempts
        subjective_attempts += 1
        if subjective_attempts == 1:
            raise event_server.WorkerPlayerReplayNotReady(
                "canonical player replay segments are still being finalized"
            )
        return object()

    async def close_registered_ai(_encounter: object) -> None:
        nonlocal cleanup_calls
        cleanup_calls += 1

    monkeypatch.setattr(
        event_server,
        "_active_local_game_coordinator",
        lambda: coordinator,
    )
    monkeypatch.setattr(
        event_server.Encounter,
        "get",
        lambda candidate_uuid: (
            fake_encounter if candidate_uuid == encounter_uuid else None
        ),
    )
    monkeypatch.setattr(
        event_server.game_summary_store,
        "get_evidence",
        lambda candidate_game_id: (
            object() if candidate_game_id == game_id else None
        ),
    )
    monkeypatch.setattr(
        event_server.game_summary_store,
        "get_replay_capture",
        lambda candidate_game_id: (
            object() if candidate_game_id == game_id else None
        ),
    )
    monkeypatch.setattr(
        event_server,
        "build_worker_objective_replay",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        event_server,
        "build_worker_subjective_replays",
        build_subjective,
    )
    monkeypatch.setattr(
        event_server,
        "_close_registered_ai_after_terminal",
        close_registered_ai,
    )

    async def exercise() -> None:
        assert event_server._publish_local_terminal_game(encounter_uuid) is False
        assert coordinator.complete_calls == 0

        event_server._on_subjective_replay_source_closed(str(encounter_uuid))
        await asyncio.sleep(0)
        assert coordinator.complete_calls == 1
        assert subjective_attempts == 2
        assert cleanup_calls == 1

        event_server._on_subjective_replay_source_closed(str(encounter_uuid))
        assert coordinator.complete_calls == 1
        assert subjective_attempts == 2

    asyncio.run(exercise())


def test_standalone_game_creation_uses_durable_local_game_and_pinned_character(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("DND_LOCAL_PROFILE_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.delenv("DND_LOCAL_PROFILE_ID", raising=False)
    monkeypatch.delenv("DND_GAME_WORKER", raising=False)

    with TestClient(event_server.app) as client:
        profile = client.get("/directory/local-profile").json()
        catalog = client.get("/character-creation/catalog").json()
        premade = next(
            row
            for row in catalog["premades"]
            if row["premade_id"]
            == "hero.fighter_2_sorcerer_3_spellblade"
        )
        headers = {
            "X-Dnd-Principal-Id": profile["profile_id"],
            "X-Dnd-Principal-Capability": profile["principal_capability"],
        }
        created = client.post(
            "/directory/characters",
            headers=headers,
            json={
                "display_name": "Local Spellblade",
                "build": premade["build"],
                "loadout": premade["loadout"],
                "expected_content_set_digest": catalog["content_set_digest"],
                "expected_ruleset_digest": profile["settings"][
                    "ruleset_digest"
                ],
                "idempotency_key": str(uuid4()),
            },
        )
        assert created.status_code == 200, created.text
        character_id = UUID(created.json()["character"]["character_id"])

        started = client.post(
            "/game-creation/start",
            json={
                "character_id": str(character_id),
                "scenario": {
                    "kind": "composed",
                    "hero_configuration_id": (
                        "hero.fighter_l5_archer_torch"
                    ),
                    "monster_configuration_id": "monsters.skeleton_trio",
                    "battlefield_id": (
                        "battlefield.standard_hazards_closed"
                    ),
                    "deployment_id": (
                        "neutral.battlefield.standard_hazards_closed"
                    ),
                },
                "side_a": {"controller": "human", "name": "Hero"},
                "side_b": {"controller": "human", "name": "Opposition"},
                "opening_side": "side_a",
            },
        )
        assert started.status_code == 200, started.text
        game_id = UUID(started.json()["game_id"])
        coordinator = event_server._active_local_game_coordinator()
        assert coordinator is not None
        game = coordinator.repository.get_game(game_id)
        assert game.execution_kind is ExecutionKind.LOCAL
        assert game.lifecycle_state is GameLifecycleState.STARTING
        assert event_server.sim.game is not None
        assert event_server.sim.game.game_id == game_id
        deployments = coordinator.repository.list_character_deployments(
            character_id,
        )
        assert len(deployments) == 1
        assert deployments[0].game_id == game_id
        assert deployments[0].pin_state == "pinned"
        assert (
            coordinator.repository.get_active_character_deployment_lease(
                character_id,
            )
            is not None
        )

        replaced = client.post(
            "/game-creation/start",
            json={
                "scenario": {
                    "kind": "preset",
                    "arena_id": "standard_skeleton_doors",
                },
                "side_a": {"controller": "human", "name": "Hero"},
                "side_b": {"controller": "human", "name": "Opposition"},
                "opening_side": "side_a",
            },
        )
        assert replaced.status_code == 200, replaced.text
        assert (
            coordinator.repository.get_game(game_id).lifecycle_state
            is GameLifecycleState.INTERRUPTED
        )
        assert (
            coordinator.repository.get_active_character_deployment_lease(
                character_id,
            )
            is None
        )


def test_ai_match_publishes_local_terminal_replays_and_game_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DND_LOCAL_PROFILE_RUNTIME_ROOT",
        str(tmp_path / "runtime"),
    )
    monkeypatch.delenv("DND_LOCAL_PROFILE_ID", raising=False)
    monkeypatch.delenv("DND_GAME_WORKER", raising=False)

    with TestClient(event_server.app) as client:
        profile = client.get("/directory/local-profile").json()
        headers = {
            "X-Dnd-Principal-Id": profile["profile_id"],
            "X-Dnd-Principal-Capability": profile[
                "principal_capability"
            ],
        }
        catalog = client.get("/character-creation/catalog").json()
        premade = next(
            row
            for row in catalog["premades"]
            if row["premade_id"]
            == "hero.fighter_2_sorcerer_3_spellblade"
        )
        created = client.post(
            "/directory/characters",
            headers=headers,
            json={
                "display_name": "Terminal Spellblade",
                "build": premade["build"],
                "loadout": premade["loadout"],
                "expected_content_set_digest": catalog[
                    "content_set_digest"
                ],
                "expected_ruleset_digest": profile["settings"][
                    "ruleset_digest"
                ],
                "idempotency_key": str(uuid4()),
            },
        )
        assert created.status_code == 200, created.text
        character_id = UUID(created.json()["character"]["character_id"])
        started = client.post(
            "/game-creation/start",
            json={
                "character_id": str(character_id),
                "scenario": {
                    "kind": "composed",
                    "hero_configuration_id": (
                        "hero.fighter_l5_archer_torch"
                    ),
                    "monster_configuration_id": "monsters.skeleton_trio",
                    "battlefield_id": (
                        "battlefield.standard_hazards_closed"
                    ),
                    "deployment_id": (
                        "neutral.battlefield.standard_hazards_closed"
                    ),
                },
                "side_a": {"controller": "ai", "name": "Heroes"},
                "side_b": {"controller": "ai", "name": "Skeletons"},
                "opening_side": "side_a",
            },
        )
        assert started.status_code == 200, started.text
        payload = started.json()
        game_id = UUID(payload["game_id"])
        observer_uuids = [
            row["entity_uuid"]
            for side in (payload["side_a"], payload["side_b"])
            for row in side["entity_assignments"]
        ]
        materialized_combatants = [
            Entity.get(UUID(entity_uuid))
            for entity_uuid in observer_uuids
        ]
        assert all(entity is not None for entity in materialized_combatants)
        assert all(
            not entity.uses_death_saves
            for entity in materialized_combatants
            if entity is not None
        )
        session = client.post(
            "/session/create",
            json={"player_type": "observer", "name": "Local Observer"},
        ).json()
        session_id = session["session_id"]
        joined = client.post(
            "/game/join",
            json={
                "session_id": session_id,
                "entity_uuids": [],
                "observer_entity_uuids": observer_uuids,
                "active_observer_uuid": observer_uuids[0],
            },
        )
        assert joined.status_code == 200, joined.text
        bootstrap = client.get(
            "/replication/bootstrap",
            params={"session_id": session_id},
        ).json()
        activated = client.post(
            "/game-creation/activate",
            json={
                "session_id": session_id,
                "expected_source_stream_id": bootstrap["protocol"][
                    "source_stream_id"
                ],
                "expected_generation_id": bootstrap["protocol"][
                    "generation_id"
                ],
                "expected_perspective_epoch_id": bootstrap["perspective"][
                    "perspective_epoch_id"
                ],
            },
        )
        assert activated.status_code == 200, activated.text

        coordinator = event_server._active_local_game_coordinator()
        assert coordinator is not None
        current = coordinator.current
        assert current is not None
        assert current.deployment_id is not None
        membership_id = current.membership.membership_id
        deployment_id = current.deployment_id
        _drive_ai_game_to_terminal_boundary(
            client,
            coordinator,
            game_id,
            expect_staged_intent=False,
        )

        artifacts = coordinator.repository.list_artifacts(game_id)
        assert {artifact.artifact_kind.value for artifact in artifacts} == {
            "replay_bundle",
            "subjective_replay_bundle",
        }
        assert coordinator.repository.get_current_summary(game_id) is not None
        assert (
            coordinator.repository.get_pending_local_terminal_commit(game_id)
            is None
        )
        assert coordinator.current is None
        character = coordinator.repository.get_character(character_id)
        assert character.current_holdings_revision == 2
        settlement = (
            coordinator.repository.get_character_settlement_by_deployment(
                deployment_id,
            )
        )
        assert settlement.game_id == game_id
        assert settlement.character_id == character_id
        assert (
            coordinator.repository.get_active_character_deployment_lease(
                character_id,
            )
            is None
        )

        history = client.get("/games", headers=headers)
        assert history.status_code == 200, history.text
        assert game_id in {
            UUID(row["game_id"]) for row in history.json()["games"]
        }
        game_read = client.get(f"/games/{game_id}", headers=headers)
        assert game_read.status_code == 200, game_read.text
        summary_read = client.get(
            f"/games/{game_id}/summary",
            headers=headers,
        )
        assert summary_read.status_code == 200, summary_read.text
        final_life_states = {
            entity["final"]["life_state"]
            for entity in summary_read.json()["summary"]["entities"]
            if entity["final"] is not None
        }
        assert LifeState.DEAD.value in final_life_states
        assert LifeState.DYING.value not in final_life_states
        assert LifeState.STABLE.value not in final_life_states
        objective_read = client.get(
            f"/games/{game_id}/diagnostics/objective-replay",
            headers=headers,
        )
        assert objective_read.status_code == 200, objective_read.text
        assert objective_read.json()["game_id"] == str(game_id)
        subjective_read = client.get(
            f"/games/{game_id}/memberships/{membership_id}/replay",
            headers=headers,
        )
        assert subjective_read.status_code == 200, subjective_read.text
        assert subjective_read.json()["membership_id"] == str(
            membership_id,
        )


def test_staged_character_terminal_recovers_after_finalize_failure_and_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("DND_LOCAL_PROFILE_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.delenv("DND_LOCAL_PROFILE_ID", raising=False)
    monkeypatch.delenv("DND_GAME_WORKER", raising=False)

    game_id: UUID
    character_id: UUID
    deployment_id: UUID
    headers: dict[str, str]
    with pytest.raises(RuntimeError, match="injected settlement failure"):
        with TestClient(event_server.app) as client:
            profile = client.get("/directory/local-profile").json()
            headers = {
                "X-Dnd-Principal-Id": profile["profile_id"],
                "X-Dnd-Principal-Capability": profile[
                    "principal_capability"
                ],
            }
            catalog = client.get("/character-creation/catalog").json()
            premade = next(
                row
                for row in catalog["premades"]
                if row["premade_id"]
                == "hero.fighter_2_sorcerer_3_spellblade"
            )
            created = client.post(
                "/directory/characters",
                headers=headers,
                json={
                    "display_name": "Recoverable Spellblade",
                    "build": premade["build"],
                    "loadout": premade["loadout"],
                    "expected_content_set_digest": catalog[
                        "content_set_digest"
                    ],
                    "expected_ruleset_digest": profile["settings"][
                        "ruleset_digest"
                    ],
                    "idempotency_key": str(uuid4()),
                },
            )
            assert created.status_code == 200, created.text
            character_id = UUID(
                created.json()["character"]["character_id"],
            )
            started = client.post(
                "/game-creation/start",
                json={
                    "character_id": str(character_id),
                    "scenario": {
                        "kind": "composed",
                        "hero_configuration_id": (
                            "hero.fighter_l5_archer_torch"
                        ),
                        "monster_configuration_id": (
                            "monsters.skeleton_trio"
                        ),
                        "battlefield_id": (
                            "battlefield.standard_hazards_closed"
                        ),
                        "deployment_id": (
                            "neutral.battlefield.standard_hazards_closed"
                        ),
                    },
                    "side_a": {"controller": "ai", "name": "Heroes"},
                    "side_b": {
                        "controller": "ai",
                        "name": "Skeletons",
                    },
                    "opening_side": "side_a",
                },
            )
            assert started.status_code == 200, started.text
            payload = started.json()
            game_id = UUID(payload["game_id"])
            observer_uuids = [
                row["entity_uuid"]
                for side in (payload["side_a"], payload["side_b"])
                for row in side["entity_assignments"]
            ]
            session = client.post(
                "/session/create",
                json={
                    "player_type": "observer",
                    "name": "Recovery Observer",
                },
            ).json()
            session_id = session["session_id"]
            joined = client.post(
                "/game/join",
                json={
                    "session_id": session_id,
                    "entity_uuids": [],
                    "observer_entity_uuids": observer_uuids,
                    "active_observer_uuid": observer_uuids[0],
                },
            )
            assert joined.status_code == 200, joined.text
            bootstrap = client.get(
                "/replication/bootstrap",
                params={"session_id": session_id},
            ).json()
            coordinator = event_server._active_local_game_coordinator()
            assert coordinator is not None
            current = coordinator.current
            assert current is not None
            assert current.deployment_id is not None
            deployment_id = current.deployment_id

            def injected_settlement_failure(*_args, **_kwargs):
                raise RuntimeError("injected settlement failure")

            monkeypatch.setattr(
                coordinator.repository,
                "_commit_terminal_settlement_in_transaction",
                injected_settlement_failure,
            )
            activated = client.post(
                "/game-creation/activate",
                json={
                    "session_id": session_id,
                    "expected_source_stream_id": bootstrap["protocol"][
                        "source_stream_id"
                    ],
                    "expected_generation_id": bootstrap["protocol"][
                        "generation_id"
                    ],
                    "expected_perspective_epoch_id": bootstrap[
                        "perspective"
                    ]["perspective_epoch_id"],
                },
            )
            assert activated.status_code == 200, activated.text
            _drive_ai_game_to_terminal_boundary(
                client,
                coordinator,
                game_id,
                expect_staged_intent=True,
            )
            pending = (
                coordinator.repository.get_pending_local_terminal_commit(
                    game_id,
                )
            )
            assert pending is not None

            _, staged_payload, _ = pending
            assert set(staged_payload) == {
                "game_id",
                "evidence",
                "objective_replay_artifact",
                "subjective_replay_artifact",
                "settlement_bundle",
                "lease_id",
            }
            assert "objective_replay" not in staged_payload
            assert "subjective_replay" not in staged_payload
            assert "events" not in str(staged_payload)
            assert "frames" not in str(staged_payload)
            for key in (
                "objective_replay_artifact",
                "subjective_replay_artifact",
            ):
                descriptor = ArtifactCreate.model_validate(
                    staged_payload[key],
                )
                stored = coordinator.artifact_store.read_bytes(
                    descriptor.content_digest,
                )
                assert len(stored) == descriptor.byte_size
            assert (
                coordinator.repository.get_game(game_id).lifecycle_state
                is GameLifecycleState.ACTIVE
            )
            assert coordinator.repository.list_artifacts(game_id) == ()
            assert (
                coordinator.repository.get_character(
                    character_id,
                ).current_holdings_revision
                == 1
            )
            assert (
                coordinator.repository.get_active_character_deployment_lease(
                    character_id,
                )
                is not None
            )

    with TestClient(event_server.app) as recovered_client:
        coordinator = event_server._active_local_game_coordinator()
        assert coordinator is not None
        game = coordinator.repository.get_game(game_id)
        assert game.lifecycle_state is GameLifecycleState.ENDED
        assert (
            coordinator.repository.get_pending_local_terminal_commit(game_id)
            is None
        )
        assert (
            coordinator.repository.get_active_character_deployment_lease(
                character_id,
            )
            is None
        )
        settlement = (
            coordinator.repository.get_character_settlement_by_deployment(
                deployment_id,
            )
        )
        assert settlement.game_id == game_id
        assert (
            coordinator.repository.get_character(
                character_id,
            ).current_holdings_revision
            == 2
        )
        history = recovered_client.get("/games", headers=headers)
        assert history.status_code == 200, history.text
        assert game_id in {
            UUID(row["game_id"]) for row in history.json()["games"]
        }
