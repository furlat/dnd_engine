"""Archived tests for the old subprocess CLI.

These tests are intentionally outside the active pytest testpaths. They preserve
the old CLI behavior while the supported runtime moves to server and in-process
controller surfaces.
"""

import json
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

ARCHIVE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ARCHIVE_ROOT))

import cli.orchestrator as orchestrator  # noqa: E402
from cli.log_filter import ANON_NAME, filter_combat_log  # noqa: E402


def test_archived_codex_orchestrator_builds_guarded_codex_exec_invocation() -> None:
    """Archived CLI orchestration uses codex exec and entity guards."""
    with tempfile.TemporaryDirectory() as tmpdir:
        prompt_file = Path(tmpdir) / "prompt.md"
        prompt_file.write_text("SYSTEM PROMPT")
        slot = orchestrator.PlayerSlot(
            slot_id="hero",
            token="abc123",
            faction="heroes",
            prompt_file=prompt_file,
        )

        cmd, stdin_prompt = orchestrator.build_codex_exec_invocation(
            slot,
            "TURN PROMPT",
            allow_write=False,
            expected_entity_uuid="entity-uuid",
        )

        assert cmd[0:2] == ["codex", "exec"]
        assert "--json" in cmd
        assert "--cd" in cmd
        assert cmd[-1] == "-"
        assert "claude" not in " ".join(cmd).lower()
        assert "SYSTEM PROMPT" in stdin_prompt
        assert "TURN PROMPT" in stdin_prompt
        assert "uv run python -m cli.agent --token abc123 --expect-entity entity-uuid <command>" in stdin_prompt
        assert "Do not write files during this game turn." in stdin_prompt

        slot.codex_session_id = "session-uuid"
        resume_cmd, _ = orchestrator.build_codex_exec_invocation(
            slot,
            "NEXT TURN",
            expected_entity_uuid="entity-uuid",
        )
        assert resume_cmd[0:3] == ["codex", "exec", "resume"]
        assert "session-uuid" in resume_cmd


def test_archived_codex_stream_metrics_track_current_item_events(tmp_path: Path) -> None:
    """Archived CLI item streams count commands, usage, and trajectory steps."""
    command = (
        "/bin/bash -lc 'uv run python -m cli.agent --token abc123 "
        "--expect-entity entity-uuid use \"Drink Greater Invisibility Potion\"'"
    )
    end_command = (
        "/bin/bash -lc 'uv run python -m cli.agent --token abc123 "
        "--expect-entity entity-uuid end'"
    )
    events = [
        {"type": "thread.started", "thread_id": "codex-thread-id"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "Taking the turn."}},
        {"type": "item.started", "item": {"type": "command_execution", "command": command}},
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": command,
                "aggregated_output": "OK: Drink Greater Invisibility Potion\n",
                "exit_code": 0,
            },
        },
        {"type": "item.started", "item": {"type": "command_execution", "command": end_command}},
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": end_command,
                "aggregated_output": "OK: Encounter already ended. No turn to end.\n",
                "exit_code": 0,
            },
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 40,
                "output_tokens": 12,
                "reasoning_output_tokens": 7,
            },
        },
    ]

    result = orchestrator.TurnResult()
    for event in events:
        orchestrator._classify_stream_event(result, event, "abc123")

    metrics = result.build_metrics("hero", "Hero", 1)

    assert result.session_id == "codex-thread-id"
    assert metrics.game_actions == 2
    assert metrics.action_list == ["use Drink Greater Invisibility Potion", "end"]
    assert metrics.thinking_steps == 1
    assert metrics.input_tokens == 100
    assert metrics.cache_read_tokens == 40
    assert metrics.output_tokens == 12
    assert metrics.time_to_first_action_s >= 0

    trajectory = tmp_path / "trajectory.md"
    raw_output = "\n".join(json.dumps(event) for event in events)
    orchestrator.append_trajectory_turn(
        raw_output,
        "TURN PROMPT",
        "Hero",
        1,
        trajectory,
        token="abc123",
        is_first_turn=True,
    )
    text = trajectory.read_text()
    assert "(no actions taken)" not in text
    assert "Input: `use Drink Greater Invisibility Potion`" in text
    assert "OK: Drink Greater Invisibility Potion" in text
    assert "Input: `end`" in text


def test_archived_combat_log_filter_reveals_only_parent_marked_aoe_targets() -> None:
    """Archived CLI AoE log filtering reveals only targets marked by the parent log."""
    hero_uuid = str(uuid4())
    revealed_uuid = str(uuid4())
    still_hidden_uuid = str(uuid4())
    stale_visible = {hero_uuid}
    parent_entry = {
        "entry_type": "multi_entity_action",
        "source_uuid": hero_uuid,
        "target_uuid": None,
        "source_name": "Hero Wizard",
        "target_name": None,
        "compact": "Hero Wizard uses Fireball",
        "verbose": "Hero Wizard uses Fireball -> 2 targets",
        "detailed": "Hero Wizard uses Fireball -> 2 targets",
        "perceiver_uuids": [hero_uuid],
        "revealed_entity_uuids": [revealed_uuid],
        "sub_entries": [
            {
                "entry_type": "spell_save",
                "source_uuid": hero_uuid,
                "target_uuid": revealed_uuid,
                "source_name": "Hero Wizard",
                "target_name": "Revealed Rogue",
                "compact": "Revealed Rogue: DEX save FAIL",
                "verbose": "Revealed Rogue: DEX save FAIL, 15 fire",
                "detailed": "Revealed Rogue: DEX save FAIL, 15 fire",
                "perceiver_uuids": [revealed_uuid],
                "revealed_entity_uuids": [],
                "sub_entries": [],
            },
            {
                "entry_type": "spell_save",
                "source_uuid": hero_uuid,
                "target_uuid": still_hidden_uuid,
                "source_name": "Hero Wizard",
                "target_name": "Still Hidden",
                "compact": "Still Hidden: DEX save SAVE",
                "verbose": "Still Hidden: DEX save SAVE, 7 fire",
                "detailed": "Still Hidden: DEX save SAVE, 7 fire",
                "perceiver_uuids": [hero_uuid],
                "revealed_entity_uuids": [],
                "sub_entries": [],
            },
        ],
    }

    filtered = filter_combat_log([parent_entry], [hero_uuid], stale_visible)

    assert len(filtered) == 1
    parent = filtered[0]
    assert parent["source_name"] == "Hero Wizard"
    assert parent["revealed_entity_uuids"] == [revealed_uuid]
    assert len(parent["sub_entries"]) == 2

    revealed_sub = parent["sub_entries"][0]
    still_hidden_sub = parent["sub_entries"][1]
    assert revealed_sub["target_name"] == "Revealed Rogue"
    assert "Revealed Rogue" in revealed_sub["verbose"]
    assert ANON_NAME not in revealed_sub["verbose"]
    assert still_hidden_sub["source_name"] == "Hero Wizard"
    assert still_hidden_sub["target_name"] == ANON_NAME
    assert "Still Hidden" not in still_hidden_sub["verbose"]
    assert still_hidden_sub["verbose"] == f"{ANON_NAME}: DEX save SAVE, 7 fire"
