"""Real HTTP providers driving the current in-process encounter and replay.

This lane exercises provider transport, isolated policy assignments and native
execution. The retired hosted game's creation/session/replacement HTTP routes
are deliberately not a dependency; application-level replacement remains
outside this current engine boundary.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any, TextIO
from uuid import UUID, uuid4

import httpx

from dnd.ai.feedback import NativeAIDecisionOutcome
from dnd.ai.instrumentation import AIInstrumentation
from dnd.ai.policies.basic import BASIC_POLICY_ID
from dnd.ai.runtime.controller import NativeAIController
from dnd.content_system.creature_materialization import materialize_creature
from dnd.controller import ControllerStepResult
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter, EncounterState
from dnd.entity import Entity
from dnd.game import Game
from dnd.monsters.configured_srd_creatures import CONFIGURED_SRD_CREATURE_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.player_facts import AttackFact, MovementFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import PresentationTarget, capture_interval, reduce_interval
from game.replay import ObserverCapture, RecordedSequence, capture_history
from server.external_ai_protocol import ExternalAIAssignmentOpenRequest, ExternalAIProtocolIdentity
from server.registered_ai_controller import RegisteredAIController
from server.registered_ai_provider import RegisteredAIProviderCatalog
from services.ai_policy_server.policies import EXTERNAL_BASIC_POLICY_ID, EXTERNAL_TACTICAL_POLICY_ID


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_LIVE_TEST_POLICY_ID = "test.external.end-turn"


@dataclass(frozen=True, slots=True)
class _LiveProvider:
    url: str
    provider_id: str
    capacity: int


@dataclass(frozen=True, slots=True)
class _Matchup:
    game: Game
    encounter: Encounter
    actors: tuple[Entity, ...]
    native: tuple[NativeAIController, ...]
    remote: tuple[RegisteredAIController, ...]
    before: PresentationTarget
    start_cursor: int



def _allocate_ports(count: int) -> tuple[int, ...]:
    sockets: list[socket.socket] = []
    try:
        for _ in range(count):
            reserved = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            reserved.bind(("127.0.0.1", 0))
            sockets.append(reserved)
        return tuple(
            int(reserved.getsockname()[1])
            for reserved in sockets
        )
    finally:
        for reserved in sockets:
            reserved.close()



def _process_output(log: TextIO) -> str:
    log.flush()
    log.seek(0)
    return log.read()



def _wait_until_ready(
    *,
    process: subprocess.Popen[str],
    log: TextIO,
    url: str,
    path: str,
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = "no request attempted"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                f"server process exited with {process.returncode}:\n"
                f"{_process_output(log)}"
            )
        try:
            response = httpx.get(
                f"{url}{path}",
                timeout=0.5,
            )
            if response.status_code == 200:
                payload = response.json()
                if isinstance(payload, dict):
                    return payload
                raise AssertionError("readiness response was not an object")
            last_error = f"HTTP {response.status_code}: {response.text}"
        except httpx.HTTPError as error:
            last_error = f"{type(error).__name__}: {error}"
        time.sleep(0.05)
    raise AssertionError(
        f"server did not become ready at {url}{path}: {last_error}\n"
        f"{_process_output(log)}"
    )



def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)



def _require_success(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    return payload



def _assignment_rows(
    audit: dict[str, Any],
    *,
    game_id: str,
) -> list[dict[str, Any]]:
    assignments = audit["assignments"]
    assert isinstance(assignments, list)
    return [
        row
        for row in assignments
        if isinstance(row, dict) and row["game_id"] == game_id
    ]



def _assert_isolated_assignments(
    rows: list[dict[str, Any]],
    expected_entity_uuids: set[str],
    *,
    expected_assignment_ids: set[str],
    policy_id: str | dict[str, str],
) -> None:
    assert len(rows) == len(expected_entity_uuids)
    assert {row["assignment_id"] for row in rows} == (
        expected_assignment_ids
    )
    assert len({row["token_digest"] for row in rows}) == len(rows)
    assert len({row["policy_instance_id"] for row in rows}) == len(rows)
    assert len({row["memory_instance_id"] for row in rows}) == len(rows)
    assert {
        row["controlled_entity_uuids"][0]
        for row in rows
    } == expected_entity_uuids
    for row in rows:
        controlled = row["controlled_entity_uuids"]
        assert len(controlled) == 1
        expected_policy_id = (
            policy_id[controlled[0]]
            if isinstance(policy_id, dict)
            else policy_id
        )
        assert row["policy_id"] == expected_policy_id



def _assert_decision_isolation(
    rows: list[dict[str, Any]],
    *,
    require_every_assignment: bool = True,
) -> None:
    for row in rows:
        controlled_uuid = row["controlled_entity_uuids"][0]
        decision_ids = row["decision_ids"]
        if not decision_ids:
            assert require_every_assignment is False
            assert row["decision_actors"] == []
            assert row["memory_actor_uuids"] == []
            assert row["decision_intents"] == []
            continue
        assert decision_ids == list(range(1, len(decision_ids) + 1))
        assert set(row["decision_actors"]) == {controlled_uuid}
        assert row["memory_actor_uuids"] == [controlled_uuid]
        assert len(row["decision_intents"]) == len(decision_ids)



def _execute_actors(rows: list[dict[str, Any]]) -> set[str]:
    return {
        row["controlled_entity_uuids"][0]
        for row in rows
        if any(
            intent["kind"] == "execute"
            for intent in row["decision_intents"]
        )
    }



def test_reference_provider_cli_binds_configured_free_port() -> None:
    """The shipped provider entry point honors isolated deployment settings."""
    (port,) = _allocate_ports(1)
    url = f"http://127.0.0.1:{port}"
    log = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "services.ai_policy_server",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--provider-id",
            "reference.cli-test",
            "--capacity",
            "1",
        ],
        cwd=_REPOSITORY_ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        handshake = _wait_until_ready(
            process=process,
            log=log,
            url=url,
            path="/handshake",
        )
        assert handshake["provider_id"] == "reference.cli-test"
        assert handshake["capacity"] == 1
        assert [
            policy["policy_id"]
            for policy in handshake["policies"]
        ] == ["external.basic", "external.tactical"]
    finally:
        _stop_process(process)
        log.close()




@contextmanager
def _running_live_provider() -> Iterator[_LiveProvider]:
    (port,) = _allocate_ports(1)
    url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "tests.ai.live_socket_provider_app:app",
             "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
            cwd=_REPOSITORY_ROOT, stdout=log, stderr=subprocess.STDOUT, text=True,
        )
        try:
            handshake = _wait_until_ready(process=process, log=log, url=url, path="/handshake")
            yield _LiveProvider(url, str(handshake["provider_id"]), int(handshake["capacity"]))
        finally:
            _stop_process(process)


async def _build_matchup(
    catalog: RegisteredAIProviderCatalog, game_id: str, policies: tuple[str, str],
) -> _Matchup:
    reset_engine_runtime()
    build_battlefield("battlefield.open_floor_bright")
    game = Game()
    positions = ((3, 5), (3, 8), (11, 5), (11, 8))
    actors = tuple(materialize_creature(
        CONFIGURED_SRD_CREATURE_RECIPES_BY_ID["knight"],
        runtime_entity_uuid=uuid4(), display_name=f"Side {index // 2 + 1} knight {index % 2 + 1}",
        faction=f"side_{index // 2 + 1}", position=position,
        deployment_role=CreatureDeploymentRole(role_id=f"encounter.actor_{index}"),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    ) for index, position in enumerate(positions))
    for actor in actors:
        actor.compose_entity()
        game.deploy_entity(actor, actor.position)
    Entity.update_all_entities_senses()
    encounter = Encounter(name=game_id, source_entity_uuid=uuid4())
    native: list[NativeAIController] = []
    remote: list[RegisteredAIController] = []
    for index, actor in enumerate(actors):
        policy_id = policies[index // 2]
        assignment_id = f"{game_id}:actor_{index}"
        if policy_id == BASIC_POLICY_ID:
            controller = NativeAIController.create(
                source_entity_uuid=actor.uuid, game_id=game_id, assignment_id=assignment_id,
                controlled_entity_uuids=(actor.uuid,), policy_id=policy_id,
            )
            native.append(controller)
        else:
            controller = await RegisteredAIController.create(
                source_entity_uuid=actor.uuid, game_id=game_id, assignment_id=assignment_id,
                controlled_entity_uuids=(actor.uuid,), policy_id=policy_id,
                provider_catalog=catalog, instrumentation=AIInstrumentation(),
            )
            remote.append(controller)
        encounter.add_combatant(actor, controller)
    # Explicit alternating order makes the integration fixture independent of initiative rolls.
    encounter.initiative_order = [actors[index].uuid for index in (0, 2, 1, 3)]
    encounter.start_encounter()
    start_cursor = EventQueue.event_cursor()
    initial = capture_interval(
        name="before provider decisions", start_cursor=0, end_cursor=start_cursor,
        observer_uuid=actors[0].uuid, battlefield_id="battlefield.open_floor_bright",
    )
    before, _ = reduce_interval(None, initial)
    return _Matchup(game, encounter, actors, tuple(native), tuple(remote), before, start_cursor)


async def _advance_matchup(match: _Matchup, *, rounds: int) -> None:
    """Drive real encounter boundaries with one awaited remote decision at a time."""
    encounter = match.encounter
    last_epochs: dict[UUID, int] = {}
    for _ in range(96):
        if encounter.state is EncounterState.ENDED or encounter.round_number > rounds:
            break
        result = encounter.advance_one_controller_action_boundary()
        if result.status == "waiting_for_ai_provider":
            actor = encounter.get_current_entity()
            controller = encounter.get_current_controller()
            assert actor is not None and isinstance(controller, RegisteredAIController)
            context = encounter.build_current_turn_context()
            cursor = EventQueue.event_cursor()
            pending = await controller.request_intent(actor, context)
            # Network completion proposes an intent; it has not mutated the authoritative game.
            assert EventQueue.event_cursor() == cursor
            assert encounter.get_current_entity() is actor
            assert encounter.get_current_controller() is controller
            world = controller.world
            assert world is not None and world.current_epoch is not None
            epoch = world.current_epoch
            assert epoch.actor_uuid == str(actor.uuid)
            assert epoch.basis_observation_cursor == world.observation_cursor
            assert epoch.epoch_index > last_epochs.get(controller.uuid, 0)
            last_epochs[controller.uuid] = epoch.epoch_index
            with EventQueue.batch_on_event_callbacks():
                step = pending if isinstance(pending, ControllerStepResult) else controller.resolve_pending_intent(
                    actor, encounter.build_current_turn_context(), pending,
                )
                result = encounter.resolve_deferred_controller_step(
                    entity_uuid=actor.uuid, controller_uuid=controller.uuid, step=step,
                )
        assert result.status in {
            "autonomous_action_completed", "advanced_autonomous", "deferred_action_completed", "encounter_ended",
        }, result
    else:
        raise AssertionError(f"matchup exceeded 96 decision boundaries in round {encounter.round_number}")
    feedback = [row for controller in match.native for row in controller.assignment.feedback]
    feedback.extend(row for controller in match.remote for row in controller.feedback)
    assert feedback
    assert not [row for row in feedback if row.outcome in {
        NativeAIDecisionOutcome.FAILED, NativeAIDecisionOutcome.REJECTED, NativeAIDecisionOutcome.LIMIT_REACHED,
    }]


def _record_both_sides(match: _Matchup) -> dict[str, bytes]:
    history = capture_history(match.before, (), observers=(
        ObserverCapture("side_1", match.actors[0].uuid, match.start_cursor),
        ObserverCapture("side_2", match.actors[2].uuid, match.start_cursor),
    ))
    return {role: native.model_dump_json().encode() for role, native in history.views.items()}


def _assert_saved_subjective_actions(payloads: dict[str, bytes], sides: tuple[set[UUID], set[UUID]]) -> None:
    """Both observers receive complete native action lineages after producer disposal."""
    assert EventQueue.event_cursor() == 0
    for payload in payloads.values():
        native = RecordedSequence.model_validate_json(payload, context=PASSIVE_EVENT_REPLAY)
        received, lineages = decode_player_sequence(encode_player_sequence(project_sequence(native)))
        sources: set[UUID] = set()
        for lineage in lineages:
            assert lineage.root.parent_lineage is None
            assert lineage.root.phase in {EventPhase.COMPLETION, EventPhase.CANCEL}
            node_ids = {node.lineage_uuid for node in lineage.events}
            assert all(child in node_ids for node in lineage.events for child in node.children_lineages)
            sources.update(node.fact.source_entity_uuid for node in lineage.events
                           if isinstance(node.fact, (AttackFact, MovementFact))
                           and node.phase is EventPhase.COMPLETION and not node.canceled)
            received = reduce_lineage(received, lineage)
        assert all(sources.intersection(side) for side in sides), sources
    assert EventQueue.event_cursor() == 0


async def _exercise_matchup(
    catalog: RegisteredAIProviderCatalog, provider: httpx.AsyncClient, live: _LiveProvider,
    *, game_id: str, policies: tuple[str, str], end_turn_only: bool = False,
) -> None:
    match = await _build_matchup(catalog, game_id, policies)
    sides = tuple({actor.uuid for actor in match.actors[start:start + 2]} for start in (0, 2))
    expected = {str(actor_uuid) for controller in match.remote for actor_uuid in controller.controlled_entity_uuids}
    try:
        audit = _require_success(await provider.get("/test/audit"))
        rows = _assignment_rows(audit, game_id=game_id)
        _assert_isolated_assignments(
            rows, expected, expected_assignment_ids={controller.assignment_id for controller in match.remote},
            policy_id={str(controller.controlled_entity_uuids[0]): controller.policy_id for controller in match.remote},
        )
        info = catalog.provider(live.provider_id)
        assert audit["active_assignments"] == info.active_assignments == len(match.remote)
        assert info.available_capacity == live.capacity - len(match.remote)
        if info.available_capacity == 0:
            overflow = ExternalAIAssignmentOpenRequest(
                protocol=ExternalAIProtocolIdentity(), assignment_id=f"{game_id}:overflow", generation=1,
                assignment_token="capacity-overflow-token-00000000000000000000000000000000",
                game_id=game_id, controlled_entity_uuids=("capacity-overflow-actor",),
                policy_id=EXTERNAL_BASIC_POLICY_ID,
            )
            rejected = await provider.post("/assignments/open", json=overflow.model_dump(mode="json"))
            assert rejected.status_code == 429
            assert rejected.json()["detail"]["code"] == "provider_capacity_exhausted"
        await _advance_matchup(match, rounds=2 if end_turn_only else 1)
        audit = _require_success(await provider.get("/test/audit"))
        rows = _assignment_rows(audit, game_id=game_id)
        _assert_decision_isolation(rows, require_every_assignment=end_turn_only)
        if end_turn_only:
            assert all(len(row["decision_ids"]) == 2 for row in rows)
            assert all(row["decision_rounds"] == [1, 2] for row in rows)
            saved = {}
        else:
            executed = _execute_actors(rows)
            for side in sides:
                remote_side = {str(identity) for identity in side} & expected
                if remote_side:
                    assert executed.intersection(remote_side)
            saved = _record_both_sides(match)
    finally:
        for controller in match.remote:
            await controller.close()
        for controller in match.native:
            controller.close()
        match.game.close()
        reset_engine_runtime()
    audit = _require_success(await provider.get("/test/audit"))
    assert audit["active_assignments"] == catalog.provider(live.provider_id).active_assignments == 0
    closed = _assignment_rows(audit, game_id=game_id)
    assert len(closed) == len(match.remote)
    assert all(row["closed"] and row["close_token_digest"] == row["token_digest"] for row in closed)
    if saved:
        _assert_saved_subjective_actions(saved, (sides[0], sides[1]))


def test_real_socket_native_external_and_external_external_matrix() -> None:
    """Shipped policies execute native turns over HTTP and release every assignment."""
    async def exercise(live: _LiveProvider) -> None:
        catalog = RegisteredAIProviderCatalog()
        async with httpx.AsyncClient(base_url=live.url, timeout=30) as provider:
            try:
                registered = await catalog.register(provider_id=live.provider_id, base_url=live.url)
                assert live.capacity == registered.capacity == 4
                assert {policy.policy_id for policy in registered.policies} == {
                    EXTERNAL_BASIC_POLICY_ID, EXTERNAL_TACTICAL_POLICY_ID, _LIVE_TEST_POLICY_ID,
                }
                for name, policies in (
                    ("native-external", (BASIC_POLICY_ID, EXTERNAL_BASIC_POLICY_ID)),
                    ("external-external", (EXTERNAL_BASIC_POLICY_ID, EXTERNAL_TACTICAL_POLICY_ID)),
                    ("isolated-end-turn", (_LIVE_TEST_POLICY_ID, _LIVE_TEST_POLICY_ID)),
                ):
                    await _exercise_matchup(catalog, provider, live, game_id=name, policies=policies,
                                            end_turn_only=name == "isolated-end-turn")
                await catalog.unregister(live.provider_id)
                assert catalog.providers() == ()
            finally:
                await catalog.close()
                reset_engine_runtime()
    with _running_live_provider() as live:
        asyncio.run(exercise(live))
