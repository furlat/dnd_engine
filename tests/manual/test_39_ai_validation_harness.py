"""Manual checks for the AI validation rotation harness."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import httpx
import pytest

from ai.codex_tools.client import CodexToolClient
from ai.validation_harness import (
    ValidationArenaInfo,
    ValidationHarnessClient,
    ValidationScheduleEntry,
    build_validation_schedule,
)
from ai.external_selfplay import run_external_selfplay
from dnd.ai.contracts.control import ActionResolutionStatus
from dnd.core.dice import fixed_dice_faces
from dnd.spells.effect_ids import COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
from dnd.scenarios.ai_validation_arenas import list_ai_validation_arena_specs
from dnd.scenarios.evaluation.legacy_recipes import LEGACY_RECIPES


def validation_catalog_rows() -> list[dict[str, object]]:
    """Return validation arena specs in API-like dictionary form."""
    return [
        {
            "arena_id": spec.arena_id,
            "title": spec.title,
            "hero_role": spec.hero_role,
            "tags": list(spec.tags),
            "expected_pressure": list(spec.expected_pressure),
            "map_notes": list(spec.map_notes),
        }
        for spec in list_ai_validation_arena_specs()
    ]


def game_creation_catalog_payload() -> dict[str, object]:
    """Return the canonical catalog subset consumed by the harness."""

    recipes = {recipe.arena_id: recipe for recipe in LEGACY_RECIPES}
    hero_roles: dict[str, str] = {}
    presets: list[dict[str, object]] = []
    for row in validation_catalog_rows():
        arena_id = str(row["arena_id"])
        recipe = recipes[arena_id]
        hero_roles.setdefault(
            recipe.hero_configuration_id,
            str(row["hero_role"]),
        )
        presets.append(
            {
                "arena_id": arena_id,
                "title": row["title"],
                "tags": row["tags"],
                "expected_pressure": row["expected_pressure"],
                "map_notes": row["map_notes"],
                "recipe": {
                    "hero_configuration_id": recipe.hero_configuration_id,
                },
            }
        )
    return {
        "hero_configurations": [
            {"configuration_id": configuration_id, "title": title}
            for configuration_id, title in hero_roles.items()
        ],
        "presets": presets,
    }


def test_validation_schedule_rotates_hero_and_monster_side_focuses() -> None:
    """The default schedule alternates core player roles and monster-side slots."""
    schedule = build_validation_schedule(validation_catalog_rows(), rounds=8)

    assert [entry.focus for entry in schedule] == [
        "sorcerer_hero",
        "skeleton_side",
        "barbarian_hero",
        "skeleton_side",
        "skirmish_hero",
        "skeleton_side",
        "resource_hero",
        "environment_hero",
    ]
    assert [entry.mode for entry in schedule] == [
        "human_hero",
        "codex_monsters",
        "human_hero",
        "codex_monsters",
        "human_hero",
        "codex_monsters",
        "human_hero",
        "human_hero",
    ]
    assert len({entry.arena_id for entry in schedule}) == 8
    assert "standard_skeleton_doors" in {entry.arena_id for entry in schedule}
    assert "skeleton_anti_aoe_split" in {entry.arena_id for entry in schedule}
    assert "caster_crossfire" in {entry.arena_id for entry in schedule}
    assert "double_door_dark_hunt" in {entry.arena_id for entry in schedule}
    assert "goblin_water_skirmish" in {entry.arena_id for entry in schedule}
    assert "item_resource_gauntlet" in {entry.arena_id for entry in schedule}
    assert "arcane_device_control" in {entry.arena_id for entry in schedule}
    assert "skeleton_mark_focus_fire" in {entry.arena_id for entry in schedule}
    assert all(a.arena_id != b.arena_id for a, b in zip(schedule, schedule[1:]))


def test_validation_schedule_reaches_all_validation_arenas_when_extended() -> None:
    """A longer schedule samples the full current arena catalog."""
    catalog = validation_catalog_rows()
    schedule = build_validation_schedule(catalog, rounds=len(catalog) * 2)
    scheduled_ids = {entry.arena_id for entry in schedule}
    crypt_entries = [
        entry for entry in schedule if entry.arena_id == "srd_undead_crypt"
    ]

    assert crypt_entries
    assert {entry.focus for entry in crypt_entries} == {"skeleton_side"}
    assert scheduled_ids == {str(row["arena_id"]) for row in catalog}
    assert all(a.arena_id != b.arena_id for a, b in zip(schedule, schedule[1:]))


def test_validation_schedule_supports_offsets_without_repeating_first_arena() -> None:
    """A start offset can resume the role cycle without immediate arena repetition."""
    schedule = build_validation_schedule(validation_catalog_rows(), rounds=5, start_index=3)

    assert [entry.focus for entry in schedule] == [
        "skeleton_side",
        "skirmish_hero",
        "skeleton_side",
        "resource_hero",
        "environment_hero",
    ]
    assert all(a.arena_id != b.arena_id for a, b in zip(schedule, schedule[1:]))


def test_validation_harness_client_lists_arenas_and_starts_scheduled_entry() -> None:
    """The client prepares, joins, bootstraps, and activates one Codex side."""
    requests: list[tuple[str, str, dict[str, str], object | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        requests.append(
            (request.method, request.url.path, dict(request.url.params), body)
        )
        if request.url.path == "/game-creation/catalog":
            return httpx.Response(200, json=game_creation_catalog_payload())
        if request.url.path == "/game-creation/start":
            assert isinstance(body, dict)
            arena_id = body["scenario"]["arena_id"]
            return httpx.Response(
                200,
                json={
                    "status": "prepared",
                    "preset_arena_id": arena_id,
                    "encounter_uuid": "encounter-id",
                    "side_a": {
                        "entity_assignments": [{"entity_uuid": "hero-id"}],
                    },
                    "side_b": {
                        "entity_assignments": [{"entity_uuid": "monster-id"}],
                        "codex_session_id": "codex-session",
                        "takeover_claim_id": "claim-id",
                    },
                },
            )
        if request.url.path == "/game/join":
            assert isinstance(body, dict)
            return httpx.Response(
                200,
                json={
                    "session_id": body["session_id"],
                    "controlled_entities": body["entity_uuids"],
                },
            )
        if request.url.path == "/replication/bootstrap":
            return httpx.Response(
                200,
                json={
                    "protocol": {
                        "source_stream_id": "source-stream",
                        "generation_id": "generation",
                    },
                    "perspective": {
                        "perspective_epoch_id": "perspective-epoch",
                    },
                },
            )
        if request.url.path == "/game-creation/activate":
            return httpx.Response(200, json={"status": "activated"})
        return httpx.Response(404, json={"detail": "not found"})

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://testserver",
    )
    client = ValidationHarnessClient("http://testserver", client=http_client)

    schedule = client.build_schedule(2)
    result = client.start_entry(schedule[1])

    assert [arena.arena_id for arena in client.list_arenas()][:2] == [
        "standard_skeleton_doors",
        "goblin_water_skirmish",
    ]
    assert schedule[1].mode == "codex_monsters"
    assert result.status == "activated"
    assert result.mode == "codex_monsters"
    assert result.arena_id == schedule[1].arena_id
    assert result.codex_session_id == "codex-session"
    assert result.takeover_claim_id == "claim-id"
    assert [path for _method, path, _params, _body in requests] == [
        "/game-creation/catalog",
        "/game-creation/start",
        "/game/join",
        "/replication/bootstrap",
        "/game-creation/activate",
        "/game-creation/catalog",
    ]
    start_body = requests[1][3]
    assert isinstance(start_body, dict)
    assert start_body["side_a"]["controller"] == "ai"
    assert start_body["side_b"]["controller"] == "codex"
    assert start_body["opening_side"] == "side_a"


def test_validation_harness_human_mode_creates_and_joins_human_session() -> None:
    """Human-hero validation uses native opponents and one canonical session."""

    requests: list[tuple[str, dict[str, object] | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        requests.append((request.url.path, body))
        if request.url.path == "/game-creation/start":
            return httpx.Response(
                200,
                json={
                    "status": "prepared",
                    "preset_arena_id": "standard_skeleton_doors",
                    "encounter_uuid": "encounter-id",
                    "side_a": {
                        "entity_assignments": [{"entity_uuid": "hero-id"}],
                    },
                    "side_b": {
                        "entity_assignments": [{"entity_uuid": "monster-id"}],
                    },
                },
            )
        if request.url.path == "/session/create":
            return httpx.Response(200, json={"session_id": "human-session"})
        if request.url.path == "/game/join":
            assert isinstance(body, dict)
            return httpx.Response(
                200,
                json={
                    "session_id": body["session_id"],
                    "controlled_entities": body["entity_uuids"],
                },
            )
        if request.url.path == "/replication/bootstrap":
            return httpx.Response(
                200,
                json={
                    "protocol": {
                        "source_stream_id": "source-stream",
                        "generation_id": "generation",
                    },
                    "perspective": {
                        "perspective_epoch_id": "perspective-epoch",
                    },
                },
            )
        if request.url.path == "/game-creation/activate":
            return httpx.Response(200, json={"status": "activated"})
        return httpx.Response(404, json={"detail": "not found"})

    client = ValidationHarnessClient(
        "http://testserver",
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="http://testserver",
        ),
    )
    entry = ValidationScheduleEntry(
        sequence=0,
        focus="sorcerer_hero",
        mode="human_hero",
        arena_id="standard_skeleton_doors",
        arena_title="Standard Skeleton Doors",
        hero_role="Sorcerer",
        rationale="human mapping",
    )

    result = client.start_entry(entry)

    assert result.status == "activated"
    assert result.codex_session_id is None
    assert [path for path, _body in requests] == [
        "/game-creation/start",
        "/session/create",
        "/game/join",
        "/replication/bootstrap",
        "/game-creation/activate",
    ]
    start_body = requests[0][1]
    assert start_body is not None
    side_a = start_body["side_a"]
    side_b = start_body["side_b"]
    assert isinstance(side_a, dict)
    assert isinstance(side_b, dict)
    assert side_a["controller"] == "human"
    assert side_b["controller"] == "ai"
    join_body = requests[2][1]
    assert join_body == {
        "session_id": "human-session",
        "entity_uuids": ["hero-id"],
    }


def test_validation_harness_client_supports_context_manager() -> None:
    """The harness client mirrors other tool clients in short smoke scripts."""
    closed = False

    class RecordingClient(httpx.Client):
        def close(self) -> None:
            nonlocal closed
            closed = True
            super().close()

    http_client = RecordingClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"hero_configurations": [], "presets": []},
            )
        ),
        base_url="http://testserver",
    )

    with ValidationHarnessClient("http://testserver", client=http_client) as client:
        assert client.list_arenas() == []

    assert closed is False

    owned_closed = False

    class OwnedRecordingClient(httpx.Client):
        def close(self) -> None:
            nonlocal owned_closed
            owned_closed = True
            super().close()

    owned_http = OwnedRecordingClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"hero_configurations": [], "presets": []},
            )
        ),
        base_url="http://testserver",
    )
    with ValidationHarnessClient("http://testserver", client=owned_http) as client:
        client._owns_client = True
        assert client.list_arenas() == []

    assert owned_closed is True


def test_validation_harness_waits_for_session_turn_boundary() -> None:
    """Probe loops can wait until their human/Codex session is active."""
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.url.path == "/game/status":
            return httpx.Response(
                200,
                json={
                    "active": True,
                    "game_id": "game",
                    "encounter_active": True,
                    "active_entity_uuid": "hero",
                    "sessions": [],
                },
            )
        if request.url.path == "/session/session/ping":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "session_id": "session",
                    "connection_status": "connected",
                    "is_my_turn": True,
                    "active_entity_uuid": "hero",
                    "active_entity_name": "Hero",
                    "controlled_entities": ["hero"],
                },
            )
        return httpx.Response(404, json={"detail": "not found"})

    http_client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver")
    client = ValidationHarnessClient("http://testserver", client=http_client)

    result = client.wait_for_session_boundary("session", timeout_s=1, poll_interval_s=0)

    assert result.status == "session_turn"
    assert result.active_entity_uuid == "hero"
    assert result.active_entity_name == "Hero"
    assert result.samples == 1
    assert ("GET", "/game/status") in requests
    assert ("POST", "/session/session/ping") in requests


def test_validation_harness_reports_finished_encounter_as_boundary_not_timeout() -> None:
    """Completed validation games should not be mislabeled as probe timeouts."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/game/status":
            return httpx.Response(
                200,
                json={
                    "active": True,
                    "game_id": "game",
                    "encounter_active": False,
                    "active_entity_uuid": None,
                    "sessions": [],
                },
            )
        if request.url.path == "/session/session/ping":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "session_id": "session",
                    "connection_status": "connected",
                    "is_my_turn": False,
                    "active_entity_uuid": None,
                    "active_entity_name": None,
                    "controlled_entities": ["hero"],
                },
            )
        return httpx.Response(404, json={"detail": "not found"})

    http_client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver")
    client = ValidationHarnessClient("http://testserver", client=http_client)

    result = client.wait_for_session_boundary("session", timeout_s=1, poll_interval_s=0)

    assert result.status == "encounter_ended"
    assert result.samples == 1


def test_external_selfplay_runs_sorcerer_barbarian_duel_through_epoch_commands() -> None:
    """The fast local runner drives both sides through subjective AI commands."""
    with fixed_dice_faces(*([1] * 400)):
        result = run_external_selfplay("sorcerer_barbarian_duel", max_commands=10)

    assert result.arena_id == "sorcerer_barbarian_duel"
    assert result.command_count == 10
    assert result.session_ids_by_faction.keys() == {"heroes", "monsters"}
    assert sum(1 for trace in result.traces if trace.snapshot_loaded) <= len(result.session_ids_by_faction)
    assert any(not trace.snapshot_loaded for trace in result.traces[1:])
    first_trace, transformed_followup = result.traces[:2]
    assert first_trace.actor_name == "Validation Duel Sorcerer"
    assert first_trace.routine_id == transformed_followup.routine_id == (
        "routine.transform_then_act"
    )
    assert first_trace.routine_step_id == "transform"
    assert transformed_followup.routine_step_id == "act"
    assert transformed_followup.action_category == "spell"
    assert {"pressure", "control_effect"}.intersection(
        transformed_followup.logical_tags
    )
    assert first_trace.command_status == "accepted"
    assert first_trace.affordance_timing == {}
    assert first_trace.reduction_timing == {}
    assert first_trace.reduce_ms == 0
    assert any(
        step.node_path.endswith("Control/HostileControl")
        for step in first_trace.policy_trace
    )
    assert any(
        step.node_path.endswith("Pressure/DirectDamage")
        for step in first_trace.policy_trace
    )
    assert any(
        step.node_path.endswith("Routines/TransformThenAct")
        for step in first_trace.policy_trace
    )
    assert any(
        "TransformThenAct/Revalidate" in step.node_path
        for step in transformed_followup.policy_trace
    )
    assert first_trace.server_timing
    assert first_trace.deep_diagnostics_enabled is True
    assert all(
        trace.deep_diagnostics_enabled is False
        for trace in result.traces[1:]
    )
    server_phases = first_trace.server_timing.get("phases")
    assert isinstance(server_phases, dict)
    assert "build.current_epoch_ms" in server_phases
    assert "execute.action_by_index_ms" in server_phases
    assert first_trace.command_http_ms is not None
    assert first_trace.command_followup_sync_ms is not None
    assert first_trace.command_submit_ms is not None
    assert first_trace.command_submit_ms >= (
        first_trace.command_http_ms
        + first_trace.command_followup_sync_ms
    )
    assert first_trace.pre_command_sync_ms is not None
    assert first_trace.pre_command_frame_fetch_ms is not None
    assert first_trace.pre_command_frame_apply_ms is not None
    assert first_trace.followup_frame_fetch_ms is not None
    assert first_trace.followup_frame_apply_ms is not None
    assert first_trace.frame_fetch_ms == pytest.approx(
        first_trace.pre_command_frame_fetch_ms
        + first_trace.followup_frame_fetch_ms,
        abs=0.002,
    )
    assert first_trace.frame_apply_ms == pytest.approx(
        first_trace.pre_command_frame_apply_ms
        + first_trace.followup_frame_apply_ms,
        abs=0.002,
    )
    assert first_trace.frame_count == (
        first_trace.pre_command_frame_count
        + first_trace.followup_frame_count
    )

    sorcerer_traces = [
        trace for trace in result.traces if trace.actor_faction == "heroes"
    ]
    barbarian_traces = [
        trace for trace in result.traces if trace.actor_faction == "monsters"
    ]
    assert [trace.command_index for trace in result.traces] == list(range(10))
    assert all(trace.command_status == "accepted" for trace in result.traces)
    assert all(
        trace.action_resolution == "completed"
        for trace in result.traces
        if trace.command_type == "execute"
    )
    assert sorcerer_traces[-1].command_type == "end_turn"
    assert barbarian_traces
    assert barbarian_traces[0].turn_index != sorcerer_traces[0].turn_index
    assert barbarian_traces[0].session_id != sorcerer_traces[0].session_id
    assert any(
        trace.action_category == "movement"
        for trace in barbarian_traces
    )
    assert any(
        trace.actor_previous_position is not None
        for trace in barbarian_traces
    )
    barbarian_attacks = [
        trace
        for trace in barbarian_traces
        if trace.action_category == "attack"
    ]
    assert len(barbarian_attacks) >= 2
    assert all("pressure" in trace.logical_tags for trace in barbarian_attacks)


def test_external_selfplay_uses_only_the_shared_policy_host() -> None:
    """Self-play emits decisions from the shared policy host."""
    with fixed_dice_faces(*([10] * 80)):
        result = run_external_selfplay("sorcerer_barbarian_duel", max_commands=1)

    trace = result.traces[0]
    assert trace.reduce_ms == 0
    assert trace.affordance_timing == {}
    assert trace.reduction_timing == {}
    assert any(step.node_path == "PolicyHost/ExecutionConstraints" for step in trace.policy_trace)


def test_external_selfplay_continues_after_counterspell_interruption() -> None:
    """Counterspell is an accepted command with a typed canceled outcome."""
    with fixed_dice_faces(*([10] * 240)):
        result = run_external_selfplay("reaction_counterspell_lab", max_commands=6)

    assert result.arena_id == "reaction_counterspell_lab"
    assert result.command_count > 1
    assert result.status != "command_rejected"
    interrupted = [trace for trace in result.traces if "spell_interruption" in trace.outcome_logical_tags]
    assert interrupted
    assert interrupted[0].command_status == "accepted"
    assert interrupted[0].action_resolution == ActionResolutionStatus.CANCELED.value
    assert interrupted[0].outcome_code == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
    assert interrupted[0].command_message == "The spell was interrupted."
    assert interrupted[0].actor_economy is not None
    assert interrupted[0].actor_economy.actions == 1
    assert interrupted[0].actor_economy.spell_slots[3].current >= 1


def test_external_selfplay_traces_spacing_reference_context() -> None:
    """Positioning probes expose the entity and envelope facts behind holds."""
    with fixed_dice_faces(*([10] * 260)):
        result = run_external_selfplay("teleport_escape_skirmish", max_commands=30)

    holds = [
        trace
        for trace in result.traces
        if (
            trace.reason == "hold_future_tactical_envelope"
            and trace.spacing_floor_cells == 6
        )
    ]

    assert holds
    assert holds[0].reference_entity_name == "Validation Escape Barbarian"
    assert holds[0].reference_entity_position is not None
    assert holds[0].reference_entity_distance_cells is not None
    assert holds[0].spacing_floor_cells == 6
    assert holds[0].spacing_anchor_position == holds[0].actor_position


def test_external_selfplay_traces_area_spell_affected_entities() -> None:
    """Area-spell probes should expose the affected subjective target set."""
    with fixed_dice_faces(*([1] * 260)):
        result = run_external_selfplay("line_aoe_corridor", max_commands=1)

    trace = result.traces[0]

    assert trace.reason == "cast_visible_area_spell"
    assert trace.template_name == "Fireball__slot_3"
    assert trace.affected_enemy_count == 4
    assert trace.affected_controlled_count == 0
    assert set(trace.affected_entity_names) == {
        "Validation Line Guard",
        "Validation Line Archer",
        "Validation Line Mage",
        "Validation Off-Line Goblin",
    }
    assert "target_allocation" in trace.logical_tags


def test_external_selfplay_seed_replays_semantic_decisions_and_outcomes() -> None:
    """A retained seed reproduces action meaning and final actor health."""
    first = run_external_selfplay(
        "standard_skeleton_doors",
        max_commands=10,
        hero_first=True,
        random_seed=8675313,
    )
    second = run_external_selfplay(
        "standard_skeleton_doors",
        max_commands=10,
        hero_first=True,
        random_seed=8675313,
    )

    def semantic_trace(result):
        return [
            (
                trace.actor_name,
                trace.reason,
                trace.target_name,
                tuple(trace.affected_entity_names),
                trace.command_status,
            )
            for trace in result.traces
        ]

    assert semantic_trace(first) == semantic_trace(second)
    assert first.final_hp_by_actor == second.final_hp_by_actor


def test_external_selfplay_seed_replays_across_fresh_processes() -> None:
    """A seed survives fresh UUID allocation after semantic trace normalization."""
    script = """
import json
from ai.external_selfplay import run_external_selfplay
from ai.policy.source import policy_source_snapshot

result = run_external_selfplay(
    "skeleton_anti_aoe_split",
    max_commands=90,
    hero_first=True,
    random_seed=2026071406,
)
payload = {
    "policy_hash": policy_source_snapshot().source_sha256,
    "actor_uuids": sorted({trace.actor_uuid for trace in result.traces}),
    "status": result.status,
    "command_count": result.command_count,
    "final_round": result.final_round,
    "final_hp_by_actor": result.final_hp_by_actor,
    "trace": [
        {
            "actor_name": trace.actor_name,
            "round_number": trace.round_number,
            "turn_index": trace.turn_index,
            "semantic_key": trace.semantic_key,
            "reason": trace.reason,
            "target_name": trace.target_name,
            "affected_entity_names": sorted(trace.affected_entity_names),
            "extra_target_names": trace.extra_target_names,
            "command_status": trace.command_status,
        }
        for trace in result.traces
    ],
}
print("REPLAY_JSON=" + json.dumps(payload, sort_keys=True))
"""

    def replay(hash_seed: str) -> dict[str, object]:
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = hash_seed
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
            env=environment,
        )
        payload_line = next(
            line
            for line in completed.stdout.splitlines()
            if line.startswith("REPLAY_JSON=")
        )
        return json.loads(payload_line.removeprefix("REPLAY_JSON="))

    first = replay("101")
    second = replay("202")
    first_uuids = set(first.pop("actor_uuids"))  # type: ignore[arg-type]
    second_uuids = set(second.pop("actor_uuids"))  # type: ignore[arg-type]

    assert first_uuids.isdisjoint(second_uuids)
    assert first == second


def test_codex_tool_client_supports_direct_context_manager() -> None:
    """Live smoke scripts can use CodexToolClient with standard context syntax."""
    client = CodexToolClient("http://testserver")

    with client as active:
        assert active is client
        assert client.client.is_closed is False

    assert client.client.is_closed is True


def test_validation_schedule_rejects_empty_nonzero_catalog() -> None:
    """A non-empty schedule needs at least one arena row."""
    try:
        build_validation_schedule([], rounds=1)
    except ValueError as exc:
        assert "at least one arena" in str(exc)
    else:
        raise AssertionError("Expected missing arena catalog to fail")


def test_validation_arena_info_accepts_tuple_fields_from_python_specs() -> None:
    """The harness accepts both server JSON and local spec-shaped values."""
    spec = list_ai_validation_arena_specs()[0]
    arena = ValidationArenaInfo.model_validate(
        {
            "arena_id": spec.arena_id,
            "title": spec.title,
            "hero_role": spec.hero_role,
            "tags": spec.tags,
            "expected_pressure": spec.expected_pressure,
            "map_notes": spec.map_notes,
        }
    )

    assert arena.arena_id == "standard_skeleton_doors"
    assert "door" in arena.tags
