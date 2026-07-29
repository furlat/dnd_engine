"""Real-process validation for native and registered-provider AI matchups."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any, TextIO

import httpx

from dnd.ai.policies.basic import BASIC_POLICY_ID
from dnd.scenarios.encounter_catalog import (
    AUTHORED_DEPLOYMENTS_BY_ID,
    AUTHORED_ENCOUNTER_RECIPES_BY_ID,
)
from server.external_ai_protocol import (
    ExternalAIAssignmentOpenRequest,
    ExternalAIProtocolIdentity,
)
from services.ai_policy_server.policies import (
    EXTERNAL_BASIC_POLICY_ID,
    EXTERNAL_TACTICAL_POLICY_ID,
)


_ADMIN_TOKEN = "live-matrix-admin-token"
_ADMIN_HEADERS = {"Authorization": f"Bearer {_ADMIN_TOKEN}"}
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_LIVE_TEST_POLICY_ID = "test.external.end-turn"


@dataclass(frozen=True, slots=True)
class _LiveServers:
    main_url: str
    provider_url: str
    provider_id: str
    provider_capacity: int


@dataclass(frozen=True, slots=True)
class _ObserverReplication:
    session_id: str
    source_stream_id: str
    generation_id: str
    perspective_epoch_id: str
    from_combat_log_cursor: int


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


@contextmanager
def _running_live_servers() -> Iterator[_LiveServers]:
    provider_port, main_port = _allocate_ports(2)
    provider_url = f"http://127.0.0.1:{provider_port}"
    main_url = f"http://127.0.0.1:{main_port}"
    provider_log = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    main_log = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    provider = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tests.ai.live_socket_provider_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(provider_port),
            "--log-level",
            "warning",
        ],
        cwd=_REPOSITORY_ROOT,
        stdout=provider_log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    main: subprocess.Popen[str] | None = None
    try:
        handshake = _wait_until_ready(
            process=provider,
            log=provider_log,
            url=provider_url,
            path="/handshake",
        )
        environment = {
            **os.environ,
            "DND_AI_PROVIDER_ADMIN_TOKEN": _ADMIN_TOKEN,
        }
        main = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "server.event_server",
                "--host",
                "127.0.0.1",
                "--port",
                str(main_port),
            ],
            cwd=_REPOSITORY_ROOT,
            env=environment,
            stdout=main_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _wait_until_ready(
            process=main,
            log=main_log,
            url=main_url,
            path="/game-creation/catalog",
        )
        yield _LiveServers(
            main_url=main_url,
            provider_url=provider_url,
            provider_id=str(handshake["provider_id"]),
            provider_capacity=int(handshake["capacity"]),
        )
    finally:
        if main is not None:
            _stop_process(main)
        _stop_process(provider)
        main_log.close()
        provider_log.close()


def _require_success(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    return payload


def _compose_payload(
    *,
    roster_1_policy_id: str | None,
    roster_2_policy_id: str | None,
    arena_id: str = "standard_skeleton_doors",
) -> dict[str, Any]:
    encounter = AUTHORED_ENCOUNTER_RECIPES_BY_ID[
        f"encounter.{arena_id}"
    ]
    deployment = AUTHORED_DEPLOYMENTS_BY_ID[
        f"neutral.{encounter.battlefield_id}"
    ]
    return {
        "title": encounter.title,
        "roster_slots": [
            {
                "roster_slot_id": roster_slot.roster_slot_id,
                "roster": {
                    "kind": "authored_roster",
                    "roster_id": roster_slot.roster.roster_id,
                },
                "faction_id": roster_slot.faction_id,
                "deployment_zone_id": roster_slot.deployment_zone_id,
                "controller_defaults": {
                    "controller": (
                        "ai" if policy_id is not None else "human"
                    ),
                    "participant_name": roster_slot.roster.title,
                    "policy_id": policy_id,
                    "member_overrides": [],
                },
            }
            for roster_slot, policy_id in zip(
                encounter.roster_slots,
                (roster_1_policy_id, roster_2_policy_id),
                strict=True,
            )
        ],
        "battlefield_id": encounter.battlefield_id,
        "deployment_id": deployment.deployment_id,
        "opening_policy": {
            "kind": "fixed_roster",
            "roster_slot_id": encounter.roster_slots[0].roster_slot_id,
        },
    }


def _start_normalized_game(
    main: httpx.Client,
    composed: dict[str, Any],
) -> dict[str, Any]:
    started = _require_success(
        main.post(
            "/game-creation/start",
            json={
                "expected_content_set_digest": (
                    composed["content_set_digest"]
                ),
                "expected_ruleset_digest": composed["ruleset_digest"],
                "recipe": composed["recipe"],
            },
        )
    )
    assert started["recipe_digest"] == composed["recipe"]["recipe_digest"]
    return started


def _compose_and_start(
    main: httpx.Client,
    *,
    roster_1_policy_id: str,
    roster_2_policy_id: str,
    arena_id: str = "standard_skeleton_doors",
) -> dict[str, Any]:
    composed = _require_success(
        main.post(
            "/game-creation/compose",
            json=_compose_payload(
                roster_1_policy_id=roster_1_policy_id,
                roster_2_policy_id=roster_2_policy_id,
                arena_id=arena_id,
            ),
        )
    )
    assert composed["compatibility"]["admitted"] is True
    return _start_normalized_game(main, composed)


def _roster_assignments(
    creation: dict[str, Any],
    roster_slot_id: str,
) -> list[dict[str, Any]]:
    roster = next(
        row
        for row in creation["rosters"]
        if row["roster_slot_id"] == roster_slot_id
    )
    assignments = roster["entity_assignments"]
    assert isinstance(assignments, list)
    return assignments


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


def _wait_for_audit(
    provider: httpx.Client,
    predicate: Callable[[dict[str, Any]], bool],
    *,
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = _require_success(provider.get("/test/audit"))
        if predicate(latest):
            return latest
        time.sleep(0.05)
    raise AssertionError(f"provider audit condition timed out: {latest}")


def _activate_with_observer(
    main: httpx.Client,
    creation: dict[str, Any],
) -> _ObserverReplication:
    all_entities = [
        row["entity_uuid"]
        for roster in creation["rosters"]
        for row in roster["entity_assignments"]
    ]
    session = _require_success(
        main.post(
            "/session/create",
            json={"player_type": "observer", "name": "Live matrix observer"},
        )
    )
    session_id = session["session_id"]
    joined = _require_success(
        main.post(
            "/game/join",
            json={
                "session_id": session_id,
                "observer_entity_uuids": all_entities,
                "active_observer_uuid": all_entities[0],
            },
        )
    )
    assert joined["success"] is True
    bootstrap = _require_success(
        main.get(
            "/replication/bootstrap",
            params={"session_id": session_id},
        )
    )
    activated = _require_success(
        main.post(
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
    )
    assert activated["status"] == "activated"
    return _ObserverReplication(
        session_id=session_id,
        source_stream_id=bootstrap["protocol"]["source_stream_id"],
        generation_id=bootstrap["protocol"]["generation_id"],
        perspective_epoch_id=bootstrap["perspective"][
            "perspective_epoch_id"
        ],
        from_combat_log_cursor=bootstrap["watermarks"][
            "combat_log_cursor"
        ],
    )


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


_AUTHORITATIVE_ACTION_LOG_TYPES = {
    "action",
    "attack",
    "movement",
    "multi_entity_action",
    "spell_damage",
}


def _action_log_sources(payload: dict[str, Any]) -> set[str]:
    sources: set[str] = set()

    def visit(entry: dict[str, Any]) -> None:
        if entry["entry_type"] in _AUTHORITATIVE_ACTION_LOG_TYPES:
            sources.add(entry["source_uuid"])
        for child in entry["sub_entries"]:
            visit(child)

    for frame in payload["frames"]:
        entry = frame["entry"]
        if isinstance(entry, dict):
            visit(entry)
    return sources


def _wait_for_replication_action_groups(
    main: httpx.Client,
    replication: _ObserverReplication,
    actor_groups: tuple[set[str], ...],
    *,
    timeout_seconds: float = 45.0,
) -> set[str]:
    deadline = time.monotonic() + timeout_seconds
    latest_sources: set[str] = set()
    while time.monotonic() < deadline:
        payload = _require_success(
            main.get(
                "/replication/combat-log",
                params={
                    "session_id": replication.session_id,
                    "expected_source_stream_id": (
                        replication.source_stream_id
                    ),
                    "expected_generation_id": replication.generation_id,
                    "expected_perspective_epoch_id": (
                        replication.perspective_epoch_id
                    ),
                    "from_combat_log_cursor": (
                        replication.from_combat_log_cursor
                    ),
                },
            )
        )
        latest_sources = _action_log_sources(payload)
        if all(latest_sources.intersection(group) for group in actor_groups):
            return latest_sources
        time.sleep(0.05)
    raise AssertionError(
        "replication did not expose authoritative actions for actor groups "
        f"{actor_groups}; observed sources={latest_sources}"
    )


def _close_with_human_replacement(main: httpx.Client) -> None:
    composed = _require_success(
        main.post(
            "/game-creation/compose",
            json=_compose_payload(
                roster_1_policy_id=None,
                roster_2_policy_id=None,
            ),
        )
    )
    replacement = _start_normalized_game(main, composed)
    assert replacement["status"] == "prepared"


def _replace_and_verify_assignment_close(
    main: httpx.Client,
    provider: httpx.Client,
    *,
    game_id: str,
) -> None:
    _close_with_human_replacement(main)
    closed = _wait_for_audit(
        provider,
        lambda audit: (
            audit["active_assignments"] == 0
            and all(
                row["closed"]
                for row in _assignment_rows(
                    audit,
                    game_id=game_id,
                )
            )
        ),
    )
    for row in _assignment_rows(closed, game_id=game_id):
        assert row["close_token_digest"] == row["token_digest"]


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


def test_real_socket_native_external_and_external_external_matrix() -> None:
    """Exercise both matchup modes and every external character lifecycle."""
    with _running_live_servers() as servers:
        assert servers.provider_capacity == 4
        with (
            httpx.Client(base_url=servers.main_url, timeout=30) as main,
            httpx.Client(base_url=servers.provider_url, timeout=30) as provider,
        ):
            registered = _require_success(
                main.post(
                    "/admin/ai/providers",
                    headers=_ADMIN_HEADERS,
                    json={
                        "provider_id": servers.provider_id,
                        "base_url": servers.provider_url,
                    },
                )
            )
            assert registered["provider_id"] == servers.provider_id
            assert {
                policy["policy_id"]
                for policy in registered["policies"]
            } == {
                "external.basic",
                "external.tactical",
                _LIVE_TEST_POLICY_ID,
            }

            native_external = _compose_and_start(
                main,
                roster_1_policy_id=BASIC_POLICY_ID,
                roster_2_policy_id=EXTERNAL_BASIC_POLICY_ID,
            )
            native_assignments = _roster_assignments(
                native_external,
                "roster_1",
            )
            external_assignments = _roster_assignments(
                native_external,
                "roster_2",
            )
            assert {
                row["policy_execution"] for row in native_assignments
            } == {"in_process"}
            assert {
                row["provider_id"] for row in native_assignments
            } == {None}
            assert {
                row["policy_execution"] for row in external_assignments
            } == {"registered_provider"}
            assert {
                row["provider_id"] for row in external_assignments
            } == {servers.provider_id}
            first_game_id = native_external["game_id"]
            first_native_entities = {
                row["entity_uuid"]
                for row in native_assignments
            }
            first_external_entities = {
                row["entity_uuid"]
                for row in external_assignments
            }
            first_audit = _require_success(provider.get("/test/audit"))
            first_rows = _assignment_rows(
                first_audit,
                game_id=first_game_id,
            )
            _assert_isolated_assignments(
                first_rows,
                first_external_entities,
                expected_assignment_ids={
                    (
                        f"{first_game_id}:roster_2:"
                        f"{assignment['member_id']}"
                    )
                    for assignment in external_assignments
                },
                policy_id=EXTERNAL_BASIC_POLICY_ID,
            )
            assert first_audit["active_assignments"] == 3

            first_replication = _activate_with_observer(
                main,
                native_external,
            )
            first_audit = _wait_for_audit(
                provider,
                lambda audit: bool(
                    _execute_actors(
                        _assignment_rows(
                            audit,
                            game_id=first_game_id,
                        )
                    )
                ),
            )
            first_rows = _assignment_rows(
                first_audit,
                game_id=first_game_id,
            )
            _assert_decision_isolation(
                first_rows,
                require_every_assignment=False,
            )
            first_external_execute_actors = _execute_actors(first_rows)
            assert first_external_execute_actors
            _wait_for_replication_action_groups(
                main,
                first_replication,
                (
                    first_native_entities,
                    first_external_execute_actors,
                ),
            )
            _require_success(main.post("/simulation/pause"))
            _replace_and_verify_assignment_close(
                main,
                provider,
                game_id=first_game_id,
            )

            shipped_external_external = _compose_and_start(
                main,
                roster_1_policy_id=EXTERNAL_BASIC_POLICY_ID,
                roster_2_policy_id=EXTERNAL_TACTICAL_POLICY_ID,
            )
            second_roster_1_assignments = _roster_assignments(
                shipped_external_external,
                "roster_1",
            )
            second_roster_2_assignments = _roster_assignments(
                shipped_external_external,
                "roster_2",
            )
            assert {
                row["policy_execution"]
                for row in second_roster_1_assignments
            } == {"registered_provider"}
            assert {
                row["policy_execution"]
                for row in second_roster_2_assignments
            } == {"registered_provider"}
            second_game_id = shipped_external_external["game_id"]
            second_roster_1_entities = {
                row["entity_uuid"]
                for row in second_roster_1_assignments
            }
            second_roster_2_entities = {
                row["entity_uuid"]
                for row in second_roster_2_assignments
            }
            second_external_entities = {
                *second_roster_1_entities,
                *second_roster_2_entities,
            }
            second_audit = _require_success(provider.get("/test/audit"))
            second_rows = _assignment_rows(
                second_audit,
                game_id=second_game_id,
            )
            _assert_isolated_assignments(
                second_rows,
                second_external_entities,
                expected_assignment_ids={
                    *{
                        (
                            f"{second_game_id}:roster_1:"
                            f"{assignment['member_id']}"
                        )
                        for assignment in second_roster_1_assignments
                    },
                    *{
                        (
                            f"{second_game_id}:roster_2:"
                            f"{assignment['member_id']}"
                        )
                        for assignment in second_roster_2_assignments
                    },
                },
                policy_id={
                    **{
                        entity_uuid: EXTERNAL_BASIC_POLICY_ID
                        for entity_uuid in second_roster_1_entities
                    },
                    **{
                        entity_uuid: EXTERNAL_TACTICAL_POLICY_ID
                        for entity_uuid in second_roster_2_entities
                    },
                },
            )
            assert second_audit["active_assignments"] == 4
            catalog = _require_success(main.get("/game-creation/catalog"))
            external_option = next(
                option
                for option in catalog["ai_policies"]
                if option["descriptor"]["policy_id"]
                == EXTERNAL_BASIC_POLICY_ID
            )
            assert external_option["active_assignments"] == 4
            assert external_option["available_capacity"] == 0

            overflow = ExternalAIAssignmentOpenRequest(
                protocol=ExternalAIProtocolIdentity(),
                assignment_id="live-capacity-overflow",
                generation=1,
                assignment_token=(
                    "capacity-overflow-token-"
                    "00000000000000000000000000000000"
                ),
                game_id=second_game_id,
                controlled_entity_uuids=("capacity-overflow-actor",),
                policy_id=EXTERNAL_BASIC_POLICY_ID,
            )
            rejected = provider.post(
                "/assignments/open",
                json=overflow.model_dump(mode="json"),
            )
            assert rejected.status_code == 429
            assert rejected.json()["detail"]["code"] == (
                "provider_capacity_exhausted"
            )

            second_replication = _activate_with_observer(
                main,
                shipped_external_external,
            )
            second_audit = _wait_for_audit(
                provider,
                lambda audit: (
                    bool(
                        _execute_actors(
                            [
                                row
                                for row in _assignment_rows(
                                    audit,
                                    game_id=second_game_id,
                                )
                                if row["controlled_entity_uuids"][0]
                                in second_roster_1_entities
                            ]
                        )
                    )
                    and bool(
                        _execute_actors(
                            [
                                row
                                for row in _assignment_rows(
                                    audit,
                                    game_id=second_game_id,
                                )
                                if row["controlled_entity_uuids"][0]
                                in second_roster_2_entities
                            ]
                        )
                    )
                ),
            )
            second_rows = _assignment_rows(
                second_audit,
                game_id=second_game_id,
            )
            _assert_decision_isolation(
                second_rows,
                require_every_assignment=False,
            )
            second_roster_1_execute_actors = _execute_actors(
                [
                    row
                    for row in second_rows
                    if row["controlled_entity_uuids"][0]
                    in second_roster_1_entities
                ]
            )
            second_roster_2_execute_actors = _execute_actors(
                [
                    row
                    for row in second_rows
                    if row["controlled_entity_uuids"][0]
                    in second_roster_2_entities
                ]
            )
            _wait_for_replication_action_groups(
                main,
                second_replication,
                (
                    second_roster_1_execute_actors,
                    second_roster_2_execute_actors,
                ),
            )
            _require_success(main.post("/simulation/pause"))
            _replace_and_verify_assignment_close(
                main,
                provider,
                game_id=second_game_id,
            )

            isolated_external_external = _compose_and_start(
                main,
                roster_1_policy_id=_LIVE_TEST_POLICY_ID,
                roster_2_policy_id=_LIVE_TEST_POLICY_ID,
            )
            isolated_game_id = isolated_external_external["game_id"]
            isolated_entities = {
                row["entity_uuid"]
                for roster in isolated_external_external["rosters"]
                for row in roster["entity_assignments"]
            }
            isolated_audit = _require_success(provider.get("/test/audit"))
            isolated_rows = _assignment_rows(
                isolated_audit,
                game_id=isolated_game_id,
            )
            _assert_isolated_assignments(
                isolated_rows,
                isolated_entities,
                expected_assignment_ids={
                    (
                        f"{isolated_game_id}:"
                        f"{roster['roster_slot_id']}:"
                        f"{assignment['member_id']}"
                    )
                    for roster in isolated_external_external["rosters"]
                    for assignment in roster["entity_assignments"]
                },
                policy_id=_LIVE_TEST_POLICY_ID,
            )
            assert isolated_audit["active_assignments"] == 4

            _activate_with_observer(main, isolated_external_external)
            isolated_audit = _wait_for_audit(
                provider,
                lambda audit: all(
                    len(row["decision_ids"]) >= 2
                    for row in _assignment_rows(
                        audit,
                        game_id=isolated_game_id,
                    )
                ),
            )
            isolated_rows = _assignment_rows(
                isolated_audit,
                game_id=isolated_game_id,
            )
            _assert_decision_isolation(isolated_rows)
            _require_success(main.post("/simulation/pause"))
            _replace_and_verify_assignment_close(
                main,
                provider,
                game_id=isolated_game_id,
            )

            removed = _require_success(
                main.delete(
                    f"/admin/ai/providers/{servers.provider_id}",
                    headers=_ADMIN_HEADERS,
                )
            )
            assert removed["provider_id"] == servers.provider_id
