"""Canonical native-AI game-creation and activation regressions."""

from collections.abc import Iterator
import time
from uuid import UUID

import pytest

from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.encounter import EncounterState, TurnState
from dnd.entity import Entity
from server import event_server
from server.arena_mode import ArenaApiClient, reset_standard_arena_runtime


@pytest.fixture(autouse=True)
def clean_native_game_creation_runtime() -> Iterator[None]:
    """Isolate process-global engine and server state around each regression."""
    reset_standard_arena_runtime()
    yield
    reset_standard_arena_runtime()


@pytest.fixture
def client() -> Iterator[ArenaApiClient]:
    """Keep one in-process application lifespan open for each check."""
    with ArenaApiClient() as api_client:
        yield api_client


def _start_request(
    *,
    side_a: str = "human",
    side_b: str = "ai",
) -> dict[str, object]:
    """Build one stable scenario request for native-controller checks."""
    return {
        "scenario": {
            "kind": "preset",
            "arena_id": "standard_skeleton_doors",
        },
        "side_a": {"controller": side_a, "name": "Side A"},
        "side_b": {"controller": side_b, "name": "Side B"},
        "opening_side": "side_a",
    }


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
    client: ArenaApiClient,
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


def test_ai_game_creation_is_prepared_without_session_http_or_gameplay(
    client: ArenaApiClient,
) -> None:
    """Creation installs native controllers but cannot begin the encounter."""
    response = client.post(
        "/game-creation/start",
        json=_start_request(side_a="ai", side_b="ai"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "prepared"
    assert "entity_uuid" not in payload
    assert "round" not in payload
    assert "turn_index" not in payload
    assert payload["side_a"]["policy_id"] == "builtin.basic"
    assert payload["side_a"]["policy_execution"] == "in_process"
    assert payload["side_a"]["provider_id"] is None
    assert payload["side_b"]["policy_id"] == "builtin.basic"
    assert payload["side_b"]["policy_execution"] == "in_process"
    assert payload["side_b"]["provider_id"] is None
    assert _controller_types(payload["side_a"]["entity_assignments"]) == {
        "native_ai"
    }
    assert _controller_types(payload["side_b"]["entity_assignments"]) == {
        "native_ai"
    }
    side_a_controllers = _controller_uuids(payload["side_a"]["entity_assignments"])
    side_b_controllers = _controller_uuids(payload["side_b"]["entity_assignments"])
    assert len(side_a_controllers) == 1
    assert len(side_b_controllers) == 1
    assert side_a_controllers.isdisjoint(side_b_controllers)

    encounter = event_server.sim.encounter
    assert encounter is not None
    assert encounter.state is EncounterState.NOT_STARTED
    assert encounter.turn_state is TurnState.NOT_STARTED
    assert encounter.round_number == 0
    assert EventQueue.get_events_by_type(EventType.ENCOUNTER_START) == []
    assert EventQueue.get_events_by_type(EventType.TURN_START) == []
    assert event_server.sim.get_session_manager().sessions == {}
    assert all(
        row["entity_uuid"]
        for side in (payload["side_a"], payload["side_b"])
        for row in side["entity_assignments"]
        if Entity.get(UUID(row["entity_uuid"])) is not None
    )


def test_unknown_policy_is_rejected_before_replacing_the_prepared_game(
    client: ArenaApiClient,
) -> None:
    """Registry validation is a cold preflight, not partial game creation."""
    first = client.post(
        "/game-creation/start",
        json=_start_request(side_a="human", side_b="human"),
    )
    assert first.status_code == 200
    first_encounter = event_server.sim.encounter
    first_game = event_server.sim.game
    assert first_encounter is not None
    assert first_game is not None

    request = _start_request(side_a="human", side_b="ai")
    side_b = request["side_b"]
    assert isinstance(side_b, dict)
    side_b["policy_id"] = "custom.missing"
    rejected = client.post("/game-creation/start", json=request)

    assert rejected.status_code == 400
    assert rejected.json()["detail"]["code"] == "ai_policy_not_registered"
    assert event_server.sim.encounter is first_encounter
    assert event_server.sim.game is first_game
    assert first_encounter.state is EncounterState.NOT_STARTED


def test_explicit_custom_policy_uses_the_registered_side_assignment(
    client: ArenaApiClient,
) -> None:
    """Server composition selects a custom policy without dynamic discovery."""
    request = _start_request(side_a="human", side_b="ai")
    side_b = request["side_b"]
    assert isinstance(side_b, dict)
    side_b["policy_id"] = "custom.tactical"

    response = client.post("/game-creation/start", json=request)

    assert response.status_code == 200
    payload = response.json()
    assert payload["side_b"]["policy_id"] == "custom.tactical"
    assert payload["side_b"]["policy_execution"] == "in_process"
    assert payload["side_b"]["provider_id"] is None
    encounter = event_server.sim.encounter
    assert encounter is not None
    row = payload["side_b"]["entity_assignments"][0]
    controller = encounter.get_controller_for(UUID(row["entity_uuid"]))
    assert controller is not None
    assert controller.controller_type == "native_ai"
    assert controller.policy_id == "custom.tactical"
    assert controller.assignment.policy_binding.descriptor.policy_id == (
        "custom.tactical"
    )


def test_activation_requires_exact_joined_bootstrap_identity_and_is_idempotent(
    client: ArenaApiClient,
) -> None:
    """Only a joined, bootstrapped perspective may release encounter start."""
    started = client.post(
        "/game-creation/start",
        json=_start_request(side_a="human", side_b="human"),
    )
    assert started.status_code == 200
    payload = started.json()
    controlled = [
        row["entity_uuid"]
        for row in payload["side_a"]["entity_assignments"]
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
    client: ArenaApiClient,
) -> None:
    """Later native turns use the same bounded coordinator as activation."""
    started = client.post(
        "/game-creation/start",
        json=_start_request(side_a="human", side_b="ai"),
    )
    assert started.status_code == 200
    payload = started.json()
    hero_uuid = payload["side_a"]["entity_assignments"][0]["entity_uuid"]
    native_rows = payload["side_b"]["entity_assignments"]
    encounter = event_server.sim.encounter
    assert encounter is not None
    native_controller = encounter.get_controller_for(
        UUID(native_rows[0]["entity_uuid"])
    )
    assert native_controller is not None
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
            encounter.get_current_entity() is None
            or str(encounter.get_current_entity().uuid) != hero_uuid
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
    client: ArenaApiClient,
) -> None:
    """An observer can join before start and replay every autonomous boundary."""
    started = client.post(
        "/game-creation/start",
        json=_start_request(side_a="ai", side_b="ai"),
    )
    assert started.status_code == 200
    payload = started.json()
    observer_uuids = [
        row["entity_uuid"]
        for side in (payload["side_a"], payload["side_b"])
        for row in side["entity_assignments"]
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
    assert len(event_server.sim.native_ai_controllers) == 2
    for controller in event_server.sim.native_ai_controllers:
        feedback = controller.assignment.feedback
        assert feedback
        assert {
            row.outcome.value
            for row in feedback
        }.isdisjoint({"rejected", "failed"})
