"""Standalone local games use the durable directory lifecycle and leases."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
import random
import time
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.core.content.durable_characters import (
    CharacterDefinitionRevisionV2,
    CharacterLoadoutRevisionV1,
)
from dnd.core.content.encounters import EncounterRosterRecipe
from dnd.core.events import EventQueue
from dnd.core.life_types import LifeState
from dnd.encounter import TurnState
from dnd.entity import Entity
from dnd.scenarios.encounter_catalog import AUTHORED_ROSTER_RECIPES_BY_ID
from server.character_directory_contracts import (
    CharacterLoadoutMutationRequest,
    CharacterLoadoutDraft,
    CreateCharacterRequest,
)
from server.character_directory_service import CharacterDirectoryService
from server.game_directory.contracts import (
    ArtifactCreate,
    CharacterRevisionBundleCommit,
    ExecutionKind,
    GameLifecycleState,
)
from server.game_directory.errors import ConflictError
from server.game_directory.local_profiles import LocalProfileManager
from server.local_game_lifecycle import (
    LocalTerminalCommitEnvelope,
    StandaloneLocalGameCoordinator,
)
from server.objective_replay import ObjectiveReplayBundle
from server.player_replay import SubjectivePlayerReplayArchive
from server import event_server


_PEPPER = b"standalone-local-game-lifecycle"


def _create_character(
    service: CharacterDirectoryService,
    owner_id: UUID,
) -> UUID:
    catalog = service.build_creation_catalog()
    plan = next(
        row
        for row in catalog.creation_plans
        if (
            row.source_premade_id
            == "hero.fighter_2_sorcerer_3_spellblade"
        )
    )
    settings = service.ensure_profile_settings(owner_id)
    created = service.create_character(
        owner_id,
        CreateCharacterRequest(
            display_name="Spellblade",
            build=plan.build,
            loadout=CharacterLoadoutDraft(),
            creation_plan_id=plan.plan_id,
            creation_plan_digest=plan.plan_digest,
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


def _compose_start_payload(
    client: TestClient,
    *,
    character_ids: tuple[UUID, ...] = (),
    player_roster_selection: dict[str, Any] | None = None,
    player_controller: str = "human",
    second_character_controller: str | None = None,
    opponent_controller: str = "human",
    opponent_roster_id: str = "monsters.skeleton_trio",
    battlefield_id: str = "battlefield.open_floor_bright",
    deployment_id: str = "neutral.battlefield.open_floor_bright",
) -> dict[str, Any]:
    def controller(kind: str, name: str) -> dict[str, object]:
        row: dict[str, object] = {
            "controller": kind,
            "participant_name": name,
            "member_overrides": [],
        }
        if kind == "ai":
            row["policy_id"] = "builtin.basic"
        return row

    character_overrides: list[dict[str, object]] = []
    if second_character_controller is not None:
        assert len(character_ids) >= 2
        override: dict[str, object] = {
            "character_id": str(character_ids[1]),
            "controller": second_character_controller,
        }
        if second_character_controller == "ai":
            override["policy_id"] = "builtin.basic"
        character_overrides.append(override)
    player_roster: dict[str, object]
    if player_roster_selection is not None:
        player_roster = player_roster_selection
    elif character_ids:
        player_roster = {
            "kind": "owned_characters",
            "title": "Owned Party",
            "character_ids": [str(value) for value in character_ids],
            "member_controller_overrides": character_overrides,
        }
    else:
        player_roster = {
            "kind": "authored_roster",
            "roster_id": "hero.fighter_l5_archer_torch",
        }
    composed = client.post(
        "/game-creation/compose",
        json={
            "title": "Local Lifecycle Test",
            "roster_slots": [
                {
                    "roster_slot_id": "players",
                    "roster": player_roster,
                    "faction_id": "players",
                    "deployment_zone_id": "zone_1",
                    "controller_defaults": controller(
                        player_controller,
                        "Players",
                    ),
                },
                {
                    "roster_slot_id": "opposition",
                    "roster": {
                        "kind": "authored_roster",
                        "roster_id": opponent_roster_id,
                    },
                    "faction_id": "opposition",
                    "deployment_zone_id": "zone_2",
                    "controller_defaults": controller(
                        opponent_controller,
                        "Opposition",
                    ),
                },
            ],
            "battlefield_id": battlefield_id,
            "deployment_id": deployment_id,
            "opening_policy": {
                "kind": "fixed_roster",
                "roster_slot_id": "players",
            },
        },
    )
    assert composed.status_code == 200, composed.text
    body = composed.json()
    return {
        "expected_content_set_digest": body["content_set_digest"],
        "expected_ruleset_digest": body["ruleset_digest"],
        "recipe": body["recipe"],
    }


def test_standalone_composes_saved_roster_from_active_local_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local saved-roster CRUD feeds the one exact composition route."""
    monkeypatch.setenv(
        "DND_LOCAL_PROFILE_RUNTIME_ROOT",
        str(tmp_path / "runtime"),
    )
    monkeypatch.delenv("DND_LOCAL_PROFILE_ID", raising=False)
    monkeypatch.delenv("DND_GAME_WORKER", raising=False)
    source = AUTHORED_ROSTER_RECIPES_BY_ID[
        "hero.fighter_l5_shield_torch"
    ]
    saved_recipe = EncounterRosterRecipe.create(
        roster_id="roster.saved.local-fighter",
        title="Local Saved Fighter",
        members=source.members,
        tags=("saved",),
        required_battlefield_capabilities=(
            source.required_battlefield_capabilities
        ),
        forbidden_battlefield_capabilities=(
            source.forbidden_battlefield_capabilities
        ),
    )

    with TestClient(event_server.app) as client:
        profile = client.get("/directory/local-profile").json()
        headers = {
            "X-Dnd-Principal-Id": profile["profile_id"],
            "X-Dnd-Principal-Capability": profile[
                "principal_capability"
            ],
        }
        saved_response = client.post(
            "/directory/encounter-rosters",
            headers=headers,
            json={
                "title": saved_recipe.title,
                "recipe": saved_recipe.model_dump(mode="json"),
            },
        )
        assert saved_response.status_code == 200, saved_response.text
        saved = saved_response.json()

        composed = _compose_start_payload(
            client,
            player_roster_selection={
                "kind": "saved_roster",
                "saved_roster_id": saved["saved_roster_id"],
                "expected_revision": saved["revision"],
                "expected_recipe_digest": saved["recipe_digest"],
            },
        )

    assert composed["recipe"]["roster_slots"][0]["roster"] == (
        saved_recipe.model_dump(mode="json")
    )


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
        character_ids=(character_id,),
        membership_roster_slot_id="players",
    )
    coordinator.pin_characters({character_id: uuid4()})
    coordinator.activate()
    coordinator.interrupt("test_complete")

    assert len(notifications) == 3
    assert notifications == sorted(notifications)
    assert len(set(notifications)) == 3


def _drive_ai_game_to_terminal_boundary(
    coordinator: StandaloneLocalGameCoordinator,
    game_id: UUID,
    *,
    expect_staged_intent: bool,
) -> None:
    """Wait for the canonical automatic AI executor to reach persistence."""

    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
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
        time.sleep(0.05)
    pytest.fail(
        "AI game did not reach its terminal persistence boundary within "
        "60 seconds",
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
        character_ids=(character_id,),
        membership_roster_slot_id="players",
    )

    assert len(prepared.characters) == 1
    prepared_character = prepared.characters[0]
    assert prepared_character.snapshot.character_id == character_id
    assert prepared.game.execution_kind is ExecutionKind.LOCAL
    assert prepared.game.lifecycle_state is GameLifecycleState.STARTING
    assert prepared.game.engine_game_id is None
    assert prepared.membership.game_id == prepared.game.game_id
    assert prepared.membership.principal_id == owner_id
    active_lease = service.repository.get_active_character_deployment_lease(
        character_id,
    )
    assert active_lease is not None
    assert active_lease.lease_id == prepared_character.lease_id

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

    deployment = coordinator.pin_characters({character_id: uuid4()})[0]
    assert deployment.lease_id == prepared_character.lease_id
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


def test_two_character_roster_is_leased_pinned_and_released_together(
    tmp_path: Path,
) -> None:
    coordinator, service, owner_id = _coordinator(tmp_path)
    first_id = _create_character(service, owner_id)
    second_id = _create_character(service, owner_id)

    prepared = coordinator.prepare(
        creation_manifest={"kind": "two-character-test"},
        scenario_kind="encounter_recipe",
        scenario_id="fixture.two-character-roster",
        display_name="Two Character Roster",
        character_ids=(first_id, second_id),
        membership_roster_slot_id="players",
    )
    assert tuple(
        row.snapshot.character_id for row in prepared.characters
    ) == (first_id, second_id)
    assert all(
        service.repository.get_active_character_deployment_lease(
            character_id,
        )
        is not None
        for character_id in (first_id, second_id)
    )

    entity_uuids = {
        first_id: uuid4(),
        second_id: uuid4(),
    }
    deployments = coordinator.pin_characters(entity_uuids)
    assert tuple(row.character_id for row in deployments) == (
        first_id,
        second_id,
    )
    assert tuple(row.entity_uuid for row in deployments) == (
        entity_uuids[first_id],
        entity_uuids[second_id],
    )
    coordinator.activate()
    coordinator.interrupt("two_character_test_complete")
    assert all(
        service.repository.get_active_character_deployment_lease(
            character_id,
        )
        is None
        for character_id in (first_id, second_id)
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
        character_ids=(character_id,),
        membership_roster_slot_id="players",
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
        character_ids=(character_id,),
        membership_roster_slot_id="players",
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
        plan = next(
            row
            for row in catalog["creation_plans"]
            if row["source_premade_id"]
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
                "build": plan["build"],
                "loadout": plan["loadout"],
                "creation_plan_id": plan["plan_id"],
                "creation_plan_digest": plan["plan_digest"],
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
            json=_compose_start_payload(
                client,
                character_ids=(character_id,),
                opponent_roster_id="monsters.goblin_water_cell",
                battlefield_id="battlefield.standard_hazards_closed",
                deployment_id=(
                    "neutral.battlefield.standard_hazards_closed"
                ),
            ),
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
            json=_compose_start_payload(client),
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


def test_standalone_compose_rebases_prior_content_character_before_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A population-only content advance preserves exact durable characters."""

    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("DND_LOCAL_PROFILE_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.delenv("DND_LOCAL_PROFILE_ID", raising=False)
    monkeypatch.delenv("DND_GAME_WORKER", raising=False)

    with TestClient(event_server.app) as client:
        profile = client.get("/directory/local-profile").json()
        catalog = client.get("/character-creation/catalog").json()
        plan = next(
            row
            for row in catalog["creation_plans"]
            if row["source_premade_id"]
            == "hero.fighter_2_sorcerer_3_spellblade"
        )
        headers = {
            "X-Dnd-Principal-Id": profile["profile_id"],
            "X-Dnd-Principal-Capability": profile[
                "principal_capability"
            ],
        }
        created = client.post(
            "/directory/characters",
            headers=headers,
            json={
                "display_name": "Prior Content Spellblade",
                "build": plan["build"],
                "loadout": plan["loadout"],
                "creation_plan_id": plan["plan_id"],
                "creation_plan_digest": plan["plan_digest"],
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
        service = event_server.app.state.character_directory
        assert isinstance(service, CharacterDirectoryService)
        owner_id = UUID(profile["profile_id"])
        current = service.get_character_snapshot(owner_id, character_id)
        source_definition = current.definition.definition
        assert isinstance(source_definition, CharacterDefinitionRevisionV2)
        source_loadout = current.loadout.loadout
        prior_content_digest = "f" * 64
        prior_definition = CharacterDefinitionRevisionV2.create(
            character_id=character_id,
            definition_revision=source_definition.definition_revision + 1,
            body_recipe=source_definition.body_recipe,
            species_ref=source_definition.species_ref,
            species_variant_ref=source_definition.species_variant_ref,
            background_ref=source_definition.background_ref,
            immutable_origin_choices=(
                source_definition.immutable_origin_choices
            ),
            appearance=source_definition.appearance,
            base_ability_scores=source_definition.base_ability_scores,
            flexible_ability_bonuses=(
                source_definition.flexible_ability_bonuses
            ),
            class_levels=source_definition.class_levels,
            premade_id=source_definition.premade_id,
            earned_character_level=(
                source_definition.earned_character_level
            ),
            content_set_digest=prior_content_digest,
            ruleset_digest=source_definition.ruleset_digest,
        )
        prior_loadout = CharacterLoadoutRevisionV1.create(
            character_id=character_id,
            loadout_revision=source_loadout.loadout_revision + 1,
            based_on_definition_revision=(
                prior_definition.definition_revision
            ),
            prepared_spells=source_loadout.prepared_spells,
            feature_toggles=source_loadout.feature_toggles,
        )
        service.repository.commit_character_revisions(
            CharacterRevisionBundleCommit(
                character_id=character_id,
                expected_row_version=current.character.row_version,
                expected_heads=current.heads,
                require_no_active_deployment=True,
                new_definition=prior_definition,
                new_loadout=prior_loadout,
            ),
        )

        start_request = _compose_start_payload(
            client,
            character_ids=(character_id,),
            opponent_roster_id="monsters.goblin_water_cell",
        )
        rebased = service.get_character_snapshot(owner_id, character_id)
        assert (
            rebased.definition.definition.content_set_digest
            == catalog["content_set_digest"]
        )
        assert (
            rebased.definition.definition.definition_revision
            == prior_definition.definition_revision + 1
        )
        assert (
            rebased.loadout.loadout.based_on_definition_revision
            == rebased.definition.definition.definition_revision
        )
        assert tuple(
            record.definition.content_set_digest
            for record in service.get_definition_history(
                owner_id,
                character_id,
            ).definitions
        )[-2:] == (
            prior_content_digest,
            catalog["content_set_digest"],
        )

        started = client.post(
            "/game-creation/start",
            json=start_request,
        )
        assert started.status_code == 200, started.text


@pytest.mark.parametrize("second_controller", ["ai", "codex"])
def test_standalone_two_owned_characters_preserve_member_controllers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    second_controller: str,
) -> None:
    """Standalone start keeps ordered character sources across control kinds."""
    monkeypatch.setenv(
        "DND_LOCAL_PROFILE_RUNTIME_ROOT",
        str(tmp_path / "runtime"),
    )
    monkeypatch.delenv("DND_LOCAL_PROFILE_ID", raising=False)
    monkeypatch.delenv("DND_GAME_WORKER", raising=False)

    with TestClient(event_server.app) as client:
        profile = client.get("/directory/local-profile").json()
        catalog = client.get("/character-creation/catalog").json()
        plan = next(
            row
            for row in catalog["creation_plans"]
            if row["source_premade_id"]
            == "hero.fighter_2_sorcerer_3_spellblade"
        )
        headers = {
            "X-Dnd-Principal-Id": profile["profile_id"],
            "X-Dnd-Principal-Capability": profile[
                "principal_capability"
            ],
        }
        character_ids: list[UUID] = []
        for display_name in ("First Local", "Second Local"):
            created = client.post(
                "/directory/characters",
                headers=headers,
                json={
                    "display_name": display_name,
                    "build": plan["build"],
                    "loadout": plan["loadout"],
                    "creation_plan_id": plan["plan_id"],
                    "creation_plan_digest": plan["plan_digest"],
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
            character_ids.append(
                UUID(created.json()["character"]["character_id"]),
            )

        started = client.post(
            "/game-creation/start",
            json=_compose_start_payload(
                client,
                character_ids=tuple(character_ids),
                player_controller="human",
                second_character_controller=second_controller,
            ),
        )
        assert started.status_code == 200, started.text
        payload = started.json()
        assignments = payload["rosters"][0]["entity_assignments"]
        assert [UUID(row["character_id"]) for row in assignments] == (
            character_ids
        )
        assert [row["controller"] for row in assignments] == [
            "human",
            second_controller,
        ]
        coordinator = event_server._active_local_game_coordinator()
        assert coordinator is not None
        current = coordinator.current
        assert current is not None
        assert [
            row.snapshot.character_id for row in current.characters
        ] == character_ids
        for character_id, assignment in zip(
            character_ids,
            assignments,
            strict=True,
        ):
            lease = (
                coordinator.repository.get_active_character_deployment_lease(
                    character_id,
                )
            )
            assert lease is not None
            deployments = coordinator.repository.list_character_deployments(
                character_id,
            )
            assert str(deployments[-1].entity_uuid) == assignment[
                "entity_uuid"
            ]
        if second_controller == "ai":
            assert assignments[1]["policy_id"] == "builtin.basic"
            assert assignments[1]["codex_session_id"] is None
        else:
            assert assignments[1]["policy_id"] is None
            assert assignments[1]["codex_session_id"] is not None


def test_standalone_two_owned_humans_both_wait_for_player_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ending Human A cannot autonomously execute or end Human B's turn."""
    monkeypatch.setenv(
        "DND_LOCAL_PROFILE_RUNTIME_ROOT",
        str(tmp_path / "runtime"),
    )
    monkeypatch.delenv("DND_LOCAL_PROFILE_ID", raising=False)
    monkeypatch.delenv("DND_GAME_WORKER", raising=False)

    with TestClient(event_server.app) as client:
        profile = client.get("/directory/local-profile").json()
        catalog = client.get("/character-creation/catalog").json()
        plan = next(
            row
            for row in catalog["creation_plans"]
            if row["source_premade_id"]
            == "hero.fighter_2_sorcerer_3_spellblade"
        )
        headers = {
            "X-Dnd-Principal-Id": profile["profile_id"],
            "X-Dnd-Principal-Capability": profile[
                "principal_capability"
            ],
        }
        character_ids: list[UUID] = []
        for display_name in ("Human A", "Human B"):
            created = client.post(
                "/directory/characters",
                headers=headers,
                json={
                    "display_name": display_name,
                    "build": plan["build"],
                    "loadout": plan["loadout"],
                    "creation_plan_id": plan["plan_id"],
                    "creation_plan_digest": plan["plan_digest"],
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
            character_ids.append(
                UUID(created.json()["character"]["character_id"]),
            )

        started = client.post(
            "/game-creation/start",
            json=_compose_start_payload(
                client,
                character_ids=tuple(character_ids),
                player_controller="human",
                opponent_controller="ai",
                opponent_roster_id="monsters.goblin_water_cell",
            ),
        )
        assert started.status_code == 200, started.text
        assignments = started.json()["rosters"][0]["entity_assignments"]
        assert [row["controller"] for row in assignments] == [
            "human",
            "human",
        ]
        first_uuid, second_uuid = (
            UUID(row["entity_uuid"]) for row in assignments
        )
        encounter = event_server.sim.encounter
        assert encounter is not None
        remaining = [
            entity_uuid
            for entity_uuid in encounter.initiative_order
            if entity_uuid not in {first_uuid, second_uuid}
        ]
        encounter.initiative_order = [
            first_uuid,
            remaining[0],
            second_uuid,
            *remaining[1:],
        ]
        encounter.current_turn_index = 0

        created_session = client.post(
            "/session/create",
            json={"player_type": "human", "name": "Party Owner"},
        )
        assert created_session.status_code == 200, created_session.text
        session_id = created_session.json()["session_id"]
        joined = client.post(
            "/game/join",
            json={
                "session_id": session_id,
                "entity_uuids": [
                    str(first_uuid),
                    str(second_uuid),
                ],
            },
        )
        assert joined.status_code == 200, joined.text
        assert set(joined.json()["controlled_entities"]) == {
            str(first_uuid),
            str(second_uuid),
        }
        bootstrap_response = client.get(
            "/replication/bootstrap",
            params={"session_id": session_id},
        )
        assert bootstrap_response.status_code == 200, bootstrap_response.text
        bootstrap = bootstrap_response.json()
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
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            current = encounter.get_current_entity()
            if (
                current is not None
                and current.uuid == first_uuid
                and encounter.turn_state is TurnState.IN_PROGRESS
            ):
                break
            time.sleep(0.01)
        current = encounter.get_current_entity()
        assert current is not None
        assert current.uuid == first_uuid
        assert encounter.turn_state is TurnState.IN_PROGRESS

        ended = client.post(
            "/action/end-turn",
            json={
                "session_id": session_id,
                "entity_uuid": str(first_uuid),
            },
        )
        assert ended.status_code == 200, ended.text
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            current = encounter.get_current_entity()
            if (
                current is not None
                and current.uuid == second_uuid
                and encounter.turn_state is TurnState.IN_PROGRESS
            ):
                break
            time.sleep(0.01)
        current = encounter.get_current_entity()
        assert current is not None
        assert current.uuid == second_uuid
        assert encounter.turn_state is TurnState.IN_PROGRESS

        second_turn_count = encounter.combatants[second_uuid].turn_count
        time.sleep(0.1)
        current = encounter.get_current_entity()
        assert current is not None
        assert current.uuid == second_uuid
        assert encounter.turn_state is TurnState.IN_PROGRESS
        assert encounter.combatants[second_uuid].turn_count == second_turn_count
        available_response = client.get(
            f"/entity/{second_uuid}/available-actions",
            params={"session_id": session_id},
        )
        assert available_response.status_code == 200, available_response.text
        move = next(
            row
            for row in available_response.json()["position_actions"]
            if (
                row["template_name"] == "Move"
                and row["availability_status"] == "available"
            )
        )
        second_entity = Entity.get(second_uuid)
        assert second_entity is not None
        move_target = next(
            target
            for target in move["valid_targets"]
            if target["position"] != list(second_entity.position)
        )
        moved = client.post(
            "/action/execute",
            json={
                "session_id": session_id,
                "entity_uuid": str(second_uuid),
                "template_name": "Move",
                "target_index": move_target["index"],
                "return_available_actions": False,
            },
        )
        assert moved.status_code == 200, moved.text


def test_ai_match_publishes_local_terminal_replays_and_game_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # This test owns terminal persistence and replay publication, not the
    # statistical duration of an arbitrary AI matchup.  Freeze its dice stream
    # so the canonical autonomous match reaches the same terminal boundary on
    # every run.
    random.seed(20260730)
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
        plan = next(
            row
            for row in catalog["creation_plans"]
            if row["source_premade_id"]
            == "hero.fighter_2_sorcerer_3_spellblade"
        )
        created = client.post(
            "/directory/characters",
            headers=headers,
            json={
                "display_name": "Terminal Spellblade",
                "build": plan["build"],
                "loadout": plan["loadout"],
                "creation_plan_id": plan["plan_id"],
                "creation_plan_digest": plan["plan_digest"],
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
            json=_compose_start_payload(
                client,
                character_ids=(character_id,),
                player_controller="ai",
                opponent_controller="ai",
                opponent_roster_id="monsters.berserker_duelist",
            ),
        )
        assert started.status_code == 200, started.text
        payload = started.json()
        game_id = UUID(payload["game_id"])
        observer_uuids = [
            row["entity_uuid"]
            for roster in payload["rosters"]
            for row in roster["entity_assignments"]
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
        assert current.characters[0].deployment_id is not None
        membership_id = current.membership.membership_id
        deployment_id = current.characters[0].deployment_id
        _drive_ai_game_to_terminal_boundary(
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
            plan = next(
                row
                for row in catalog["creation_plans"]
                if row["source_premade_id"]
                == "hero.fighter_2_sorcerer_3_spellblade"
            )
            created = client.post(
                "/directory/characters",
                headers=headers,
                json={
                    "display_name": "Recoverable Spellblade",
                    "build": plan["build"],
                    "loadout": plan["loadout"],
                    "creation_plan_id": plan["plan_id"],
                    "creation_plan_digest": plan["plan_digest"],
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
                json=_compose_start_payload(
                    client,
                    character_ids=(character_id,),
                    player_controller="human",
                    opponent_controller="human",
                ),
            )
            assert started.status_code == 200, started.text
            payload = started.json()
            game_id = UUID(payload["game_id"])
            observer_uuids = [
                row["entity_uuid"]
                for roster in payload["rosters"]
                for row in roster["entity_assignments"]
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
            assert current.characters[0].deployment_id is not None
            deployment_id = current.characters[0].deployment_id

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

            async def finish_activated_encounter() -> None:
                """Serialize the fixture mutation behind activation startup."""
                combat_task = event_server.sim.combat_task
                if combat_task is not None:
                    await combat_task
                encounter = event_server.sim.encounter
                assert encounter is not None
                encounter.end_encounter(
                    "deterministic staged-terminal recovery fixture",
                )

            assert client.portal is not None
            client.portal.call(finish_activated_encounter)
            _drive_ai_game_to_terminal_boundary(
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
            stored_artifacts: dict[str, bytes] = {}
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
                stored_artifacts[key] = stored
            envelope = LocalTerminalCommitEnvelope.model_validate(
                staged_payload,
            )
            objective_replay = ObjectiveReplayBundle.model_validate_json(
                stored_artifacts["objective_replay_artifact"],
            )
            subjective_replay = (
                SubjectivePlayerReplayArchive.model_validate_json(
                    stored_artifacts["subjective_replay_artifact"],
                )
            )
            conflicting_evidence = envelope.evidence.model_copy(
                update={"source_event_digest": "0" * 64},
            )
            with pytest.raises(
                ConflictError,
                match="differs from the staged terminal commit",
            ):
                coordinator.complete_terminal(
                    evidence=conflicting_evidence,
                    objective_replay=objective_replay,
                    subjective_replay=subjective_replay,
                )
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
            coordinator.complete_terminal(
                evidence=envelope.evidence,
                objective_replay=objective_replay,
                subjective_replay=subjective_replay,
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
