"""Canonical native-AI game-creation and activation regressions."""

from collections.abc import Iterator
import time
from uuid import UUID, uuid4

import pytest

from dnd.ai.runtime.controller import NativeAIController
from dnd.core.events import (
    EventPhase,
    EventQueue,
    EventType,
    MovementTrajectory,
    StepMovementEvent,
)
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.entity import Entity
from server import event_server
from server.combat_log_source import CombatLogSourceError
from server.event_stream import event_stream
from tests.manual.server_test_client import (
    ServerTestClient,
    reset_server_test_runtime,
)
from tests.manual.game_creation_test_support import (
    compose_and_preview,
    roster_result,
    start_composed_game,
)


@pytest.fixture(autouse=True)
def clean_native_game_creation_runtime() -> Iterator[None]:
    """Isolate process-global engine and server state around each regression."""
    reset_server_test_runtime()
    yield
    reset_server_test_runtime()


@pytest.fixture
def client() -> Iterator[ServerTestClient]:
    """Keep one in-process application lifespan open for each check."""
    with ServerTestClient() as api_client:
        yield api_client


def _controller_types(rows: list[dict[str, object]]) -> set[str]:
    encounter = event_server.sim.encounter
    assert encounter is not None
    result: set[str] = set()
    for row in rows:
        controller = encounter.get_controller_for(UUID(str(row["entity_uuid"])))
        assert controller is not None
        result.add(controller.controller_type)
    return result


def _controller_uuids(rows: list[dict[str, object]]) -> set[UUID]:
    encounter = event_server.sim.encounter
    assert encounter is not None
    result: set[UUID] = set()
    for row in rows:
        controller = encounter.get_controller_for(UUID(str(row["entity_uuid"])))
        assert controller is not None
        result.add(controller.uuid)
    return result


def test_core_catalog_always_exposes_native_ai_without_managed_service(
    client: ServerTestClient,
) -> None:
    """Native AI is an engine capability, not a registered transport service."""
    response = client.get("/game-creation/catalog")

    assert response.status_code == 200
    assert response.json()["controllers"] == ["human", "ai", "codex"]
    assert [
        policy["descriptor"]["policy_id"]
        for policy in response.json()["ai_policies"]
    ] == ["builtin.basic", "custom.tactical"]
    assert all(
        policy["execution"] == "in_process"
        and policy["provider_id"] is None
        and policy["capacity"] is None
        and policy["active_assignments"] is None
        and policy["available_capacity"] is None
        for policy in response.json()["ai_policies"]
    )


def test_consecutive_prepared_games_replace_the_exact_objective_source(
    client: ServerTestClient,
) -> None:
    """A new prepared world cannot retain the prior objective source owner."""
    _first_composition, _first_payload = start_composed_game(
        client,
        controllers=("human", "human"),
    )
    first_encounter = event_server.sim.encounter
    assert first_encounter is not None
    assert event_stream.source_encounter is first_encounter

    _second_composition, second_payload = start_composed_game(
        client,
        controllers=("human", "human"),
    )
    second_encounter = event_server.sim.encounter
    assert second_encounter is not None
    assert second_encounter is not first_encounter
    assert event_stream.source_encounter is second_encounter

    controlled = roster_result(
        second_payload,
        "roster_1",
    )["entity_assignments"][0]["entity_uuid"]
    created = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Replacement owner"},
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    joined = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [controlled]},
    )
    assert joined.status_code == 200

    bootstrap = client.get(
        "/replication/bootstrap",
        params={"session_id": session_id},
    )

    assert bootstrap.status_code == 200, bootstrap.text
    assert bootstrap.json()["protocol"]["source_stream_id"] == str(
        second_encounter.uuid
    )


def test_prepared_objective_source_rejects_a_foreign_encounter(
    client: ServerTestClient,
) -> None:
    """Diagnostics cannot silently replace the prepared source owner."""
    _composition, _payload = start_composed_game(
        client,
        controllers=("human", "human"),
    )
    prepared = event_server.sim.encounter
    assert prepared is not None
    assert event_stream.source_encounter is prepared
    foreign = Encounter(
        name="Foreign prepared source",
        source_entity_uuid=prepared.source_entity_uuid,
    )

    with pytest.raises(CombatLogSourceError, match="installed source"):
        event_stream.install_prepared_source(foreign)
    with pytest.raises(CombatLogSourceError, match="objective source"):
        event_stream.capture_objective_source_snapshot(foreign)

    assert event_stream.source_encounter is prepared


def test_real_bootstrap_route_returns_typed_deferral_during_poisoned_batch(
    client: ServerTestClient,
) -> None:
    """The live GET producer emits the raw requester-safe 409 contract."""
    _composition, payload = start_composed_game(
        client,
        controllers=("human", "human"),
    )
    encounter = event_server.sim.encounter
    assert encounter is not None
    controlled = roster_result(
        payload,
        "roster_1",
    )["entity_assignments"][0]["entity_uuid"]
    actor = Entity.get(UUID(controlled))
    assert actor is not None
    created = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Deferred route owner"},
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    joined = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [controlled]},
    )
    assert joined.status_code == 200

    with EventQueue.batch_on_event_callbacks():
        StepMovementEvent(
            source_entity_uuid=actor.uuid,
            source_entity_name=actor.name,
            from_position=actor.position,
            to_position=actor.position,
            path_index=1,
            total_path_length=2,
            movement_cost=0,
            trajectory=MovementTrajectory.PATH,
            disclosed_path=(actor.position, actor.position),
            committed=False,
            parent_event=uuid4(),
            phase=EventPhase.COMPLETION,
        )
        deferred = client.get(
            "/replication/bootstrap",
            params={"session_id": session_id},
        )
        assert deferred.status_code == 409
        assert deferred.headers["cache-control"] == "private, no-store"
        assert deferred.json() == {
            "code": "source_batch_in_flight",
            "retryable": True,
            "source_stream_id": str(encounter.uuid),
            "generation_id": str(EventQueue.generation_id()),
        }

    recovered = client.get(
        "/replication/bootstrap",
        params={"session_id": session_id},
    )
    assert recovered.status_code == 200, recovered.text


def test_ai_game_creation_is_prepared_without_session_http_or_gameplay(
    client: ServerTestClient,
) -> None:
    """Creation installs native controllers but cannot begin the encounter."""
    _composition, payload = start_composed_game(
        client,
        controllers=("ai", "ai"),
    )
    first_roster = roster_result(payload, "roster_1")
    second_roster = roster_result(payload, "roster_2")
    first_assignments = first_roster["entity_assignments"]
    second_assignments = second_roster["entity_assignments"]
    assert payload["status"] == "prepared"
    assert "entity_uuid" not in payload
    assert "round" not in payload
    assert "turn_index" not in payload
    assert {
        (row["policy_id"], row["policy_execution"], row["provider_id"])
        for row in first_assignments + second_assignments
    } == {("builtin.basic", "in_process", None)}
    assert _controller_types(first_assignments) == {
        "native_ai"
    }
    assert _controller_types(second_assignments) == {
        "native_ai"
    }
    first_controllers = _controller_uuids(first_assignments)
    second_controllers = _controller_uuids(second_assignments)
    assert len(first_controllers) == len(first_assignments)
    assert len(second_controllers) == len(second_assignments)
    assert first_controllers.isdisjoint(second_controllers)

    encounter = event_server.sim.encounter
    assert encounter is not None
    assert event_stream.source_encounter is encounter
    assert encounter.state is EncounterState.NOT_STARTED
    assert encounter.turn_state is TurnState.NOT_STARTED
    assert encounter.round_number == 0
    assert EventQueue.get_events_by_type(EventType.ENCOUNTER_START) == []
    assert EventQueue.get_events_by_type(EventType.TURN_START) == []
    assert event_server.sim.get_session_manager().sessions == {}
    assert all(
        row["entity_uuid"]
        for roster in payload["rosters"]
        for row in roster["entity_assignments"]
        if Entity.get(UUID(row["entity_uuid"])) is not None
    )


def test_unknown_policy_is_rejected_before_replacing_the_prepared_game(
    client: ServerTestClient,
) -> None:
    """Registry validation is a cold preflight, not partial game creation."""
    _first_composition, _first_payload = start_composed_game(
        client,
        controllers=("human", "human"),
    )
    first_encounter = event_server.sim.encounter
    first_game = event_server.sim.game
    assert first_encounter is not None
    assert first_game is not None

    composition = compose_and_preview(
        client,
        controllers=("human", "ai"),
        policy_ids=(None, "custom.missing"),
    )
    rejected = client.post(
        "/game-creation/start",
        json=composition["exact_start_request"],
    )

    assert rejected.status_code == 400
    assert rejected.json()["detail"]["code"] == "ai_policy_not_registered"
    assert event_server.sim.encounter is first_encounter
    assert event_server.sim.game is first_game
    assert first_encounter.state is EncounterState.NOT_STARTED


def test_explicit_custom_policy_uses_the_registered_side_assignment(
    client: ServerTestClient,
) -> None:
    """Server composition selects a custom policy without dynamic discovery."""
    _composition, payload = start_composed_game(
        client,
        controllers=("human", "ai"),
        policy_ids=(None, "custom.tactical"),
    )
    assignments = roster_result(
        payload,
        "roster_2",
    )["entity_assignments"]
    assert {
        (row["policy_id"], row["policy_execution"], row["provider_id"])
        for row in assignments
    } == {("custom.tactical", "in_process", None)}
    encounter = event_server.sim.encounter
    assert encounter is not None
    row = assignments[0]
    controller = encounter.get_controller_for(UUID(row["entity_uuid"]))
    assert isinstance(controller, NativeAIController)
    assert controller.controller_type == "native_ai"
    assert controller.policy_id == "custom.tactical"
    assert controller.assignment.policy_binding.descriptor.policy_id == (
        "custom.tactical"
    )


def test_activation_requires_exact_joined_bootstrap_identity_and_is_idempotent(
    client: ServerTestClient,
) -> None:
    """Only a joined, bootstrapped perspective may release encounter start."""
    _composition, payload = start_composed_game(
        client,
        controllers=("human", "human"),
    )
    controlled = [
        row["entity_uuid"]
        for row in roster_result(
            payload,
            "roster_1",
        )["entity_assignments"]
    ]
    created_session = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Activation Owner"},
    )
    assert created_session.status_code == 200
    session_id = created_session.json()["session_id"]
    joined = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": controlled},
    )
    assert joined.status_code == 200
    bootstrap_response = client.get(
        "/replication/bootstrap",
        params={"session_id": session_id},
    )
    assert bootstrap_response.status_code == 200
    bootstrap = bootstrap_response.json()
    activation = {
        "session_id": session_id,
        "expected_source_stream_id": bootstrap["protocol"]["source_stream_id"],
        "expected_generation_id": bootstrap["protocol"]["generation_id"],
        "expected_perspective_epoch_id": bootstrap["perspective"][
            "perspective_epoch_id"
        ],
    }

    stale = client.post(
        "/game-creation/activate",
        json={**activation, "expected_generation_id": "stale-generation"},
    )

    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "replication_identity_changed"
    encounter = event_server.sim.encounter
    assert encounter is not None
    assert encounter.state is EncounterState.NOT_STARTED
    assert EventQueue.get_events_by_type(EventType.ENCOUNTER_START) == []

    accepted = client.post("/game-creation/activate", json=activation)

    assert accepted.status_code == 200
    assert accepted.json()["status"] == "activated"
    deadline = time.monotonic() + 1.0
    while (
        not EventQueue.get_events_by_type(EventType.ENCOUNTER_START)
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)
    encounter_start_count = len(
        EventQueue.get_events_by_type(EventType.ENCOUNTER_START)
    )
    assert encounter_start_count == 1
    deadline = time.monotonic() + 1.0
    while (
        encounter.turn_state is not TurnState.IN_PROGRESS
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)
    assert encounter.turn_state is TurnState.IN_PROGRESS

    duplicate = client.post("/game-creation/activate", json=activation)

    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "already_active"
    assert len(EventQueue.get_events_by_type(EventType.ENCOUNTER_START)) == (
        encounter_start_count
    )


def test_human_end_turn_schedules_native_side_and_returns_to_player(
    client: ServerTestClient,
) -> None:
    """Later native turns use the same bounded coordinator as activation."""
    _composition, payload = start_composed_game(
        client,
        controllers=("human", "ai"),
    )
    hero_uuid = roster_result(
        payload,
        "roster_1",
    )["entity_assignments"][0]["entity_uuid"]
    native_rows = roster_result(
        payload,
        "roster_2",
    )["entity_assignments"]
    encounter = event_server.sim.encounter
    assert encounter is not None
    native_controller = encounter.get_controller_for(
        UUID(native_rows[0]["entity_uuid"])
    )
    assert isinstance(native_controller, NativeAIController)
    assert native_controller.controller_type == "native_ai"

    created_session = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Native AI Opponent"},
    )
    session_id = created_session.json()["session_id"]
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
    activated = client.post(
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
    assert activated.status_code == 200
    deadline = time.monotonic() + 1.0
    while (
        encounter.turn_state is not TurnState.IN_PROGRESS
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)
    assert encounter.turn_state is TurnState.IN_PROGRESS

    native_started_at = time.perf_counter()
    ended = client.post(
        "/action/end-turn",
        json={"session_id": session_id, "entity_uuid": hero_uuid},
    )

    assert ended.status_code == 200
    assert ended.json()["status"] == "advancement_scheduled"
    deadline = time.monotonic() + 10.0
    while (
        encounter.state is EncounterState.ACTIVE
        and (
            (current_entity := encounter.get_current_entity()) is None
            or str(current_entity.uuid) != hero_uuid
            or encounter.turn_state is not TurnState.IN_PROGRESS
        )
        and time.monotonic() < deadline
    ):
        status = client.get("/game/status")
        assert status.status_code == 200
    if encounter.state is not EncounterState.ENDED:
        current = encounter.get_current_entity()
        assert current is not None
        assert str(current.uuid) == hero_uuid
        assert encounter.turn_state is TurnState.IN_PROGRESS
    assert time.perf_counter() - native_started_at < 5.0
    assert native_controller.assignment.feedback


def test_ai_match_replays_from_pre_activation_bootstrap_and_keeps_advancing(
    client: ServerTestClient,
) -> None:
    """An observer can join before start and replay every autonomous boundary."""
    _composition, payload = start_composed_game(
        client,
        controllers=("ai", "ai"),
    )
    observer_uuids = [
        row["entity_uuid"]
        for roster in payload["rosters"]
        for row in roster["entity_assignments"]
    ]
    session = client.post(
        "/session/create",
        json={"player_type": "observer", "name": "Pre-start Observer"},
    )
    assert session.status_code == 200
    session_id = session.json()["session_id"]
    joined = client.post(
        "/game/join",
        json={
            "session_id": session_id,
            "entity_uuids": [],
            "observer_entity_uuids": observer_uuids,
            "active_observer_uuid": observer_uuids[0],
        },
    )
    assert joined.status_code == 200
    bootstrap_response = client.get(
        "/replication/bootstrap",
        params={"session_id": session_id},
    )
    assert bootstrap_response.status_code == 200
    bootstrap = bootstrap_response.json()
    initial_watermarks = bootstrap["watermarks"]
    activation = {
        "session_id": session_id,
        "expected_source_stream_id": bootstrap["protocol"]["source_stream_id"],
        "expected_generation_id": bootstrap["protocol"]["generation_id"],
        "expected_perspective_epoch_id": bootstrap["perspective"][
            "perspective_epoch_id"
        ],
    }

    activated = client.post("/game-creation/activate", json=activation)

    assert activated.status_code == 200
    encounter = event_server.sim.encounter
    assert encounter is not None
    autonomous_started_at = time.perf_counter()
    deadline = time.monotonic() + 10.0
    completed_turns: list[object] = []
    while time.monotonic() < deadline:
        completed_turns = [
            event
            for event in EventQueue.get_events_by_type(EventType.TURN_END)
            if event.phase is EventPhase.COMPLETION
        ]
        if len(completed_turns) >= 2 or encounter.state is EncounterState.ENDED:
            break
        status = client.get("/game/status")
        assert status.status_code == 200
    autonomous_elapsed = time.perf_counter() - autonomous_started_at
    assert len(completed_turns) >= 2 or encounter.state is EncounterState.ENDED
    event_server.sim.paused = True
    assert client.get("/game/status").status_code == 200

    identity_params = {
        "session_id": session_id,
        "expected_source_stream_id": activation["expected_source_stream_id"],
        "expected_generation_id": activation["expected_generation_id"],
        "expected_perspective_epoch_id": activation[
            "expected_perspective_epoch_id"
        ],
    }
    frames_response = client.get(
        "/replication/frames",
        params={
            **identity_params,
            "from_observation_cursor": initial_watermarks[
                "observation_cursor"
            ],
        },
    )
    logs_response = client.get(
        "/replication/combat-log",
        params={
            **identity_params,
            "from_combat_log_cursor": initial_watermarks[
                "combat_log_cursor"
            ],
        },
    )

    assert frames_response.status_code == 200, frames_response.text
    assert logs_response.status_code == 200, logs_response.text
    frames = frames_response.json()["frames"]
    cues = [
        cue
        for frame in frames
        for cue in frame["presentation"]
    ]
    presentation_cursors = [
        cue["presentation_cursor"]
        for cue in cues
    ]
    assert presentation_cursors == sorted(presentation_cursors)
    transitions = [
        cue["transition"]
        for cue in cues
        if cue["kind"] == "encounter"
    ]
    assert transitions[0] == "start"
    assert transitions.count("turn_start") >= 2
    assert transitions.count("turn_end") >= 2 or encounter.state is EncounterState.ENDED
    assert any(
        cue["kind"] in {"attack", "movement", "spell", "item_action", "shove"}
        for cue in cues
    )
    logs = logs_response.json()
    assert logs["projection"] == "subjective"
    assert logs["from_cursor"] == initial_watermarks["combat_log_cursor"]
    assert logs["through_cursor"] >= logs["from_cursor"]
    assert any(frame is not None for frame in logs["frames"])
    phase_totals_ms: dict[str, float] = {}
    for timing in event_server.sim.native_ai_instrumentation.timing_snapshot():
        phase = timing.phase.value
        phase_totals_ms[phase] = (
            phase_totals_ms.get(phase, 0.0)
            + timing.wall_duration_ns / 1_000_000
        )
    assert phase_totals_ms["decision_total"] > 0.0
    assert autonomous_elapsed < 10.0, phase_totals_ms
    assert len(event_server.sim.native_ai_controllers) == len(
        observer_uuids,
    )
    exercised_controllers = [
        controller
        for controller in event_server.sim.native_ai_controllers
        if controller.assignment.feedback
    ]
    assert len(exercised_controllers) >= 2
    for controller in exercised_controllers:
        feedback = controller.assignment.feedback
        assert {
            row.outcome.value
            for row in feedback
        }.isdisjoint({"rejected", "failed"})
