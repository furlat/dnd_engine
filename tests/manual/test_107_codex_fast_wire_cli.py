"""Dependency-light CLI contracts for the persistent hot Codex daemon."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from ai.codex_tools import wire_cli


def test_wire_cli_import_does_not_load_engine_or_daemon_graph() -> None:
    """One-shot commands remain a small wire adapter around the stable process."""
    script = """
import json
import sys
import ai.codex_tools.wire_cli
print(json.dumps({
    "dnd": any(name == "dnd" or name.startswith("dnd.") for name in sys.modules),
    "daemon": "ai.codex_tools.hot_runtime" in sys.modules,
    "fastapi": "fastapi" in sys.modules,
    "httpx": "httpx" in sys.modules,
    "policy": any(name == "ai.policy" or name.startswith("ai.policy.") for name in sys.modules),
}))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "dnd": False,
        "daemon": False,
        "fastapi": False,
        "httpx": False,
        "policy": False,
    }


def test_fast_execute_uses_small_revision_then_compact_command_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI never fetches a full turn merely to revision-fence a command."""
    calls: list[tuple[str, str, object]] = []
    revision = {
        "runtime_id": "runtime",
        "session_id": "session",
        "encounter_uuid": "encounter",
        "observation_cursor": 12,
        "epoch_id": "epoch",
        "actor_uuid": "actor",
    }

    def fake_request(
        _base_url: str,
        _token: str,
        method: str,
        path: str,
        payload: object = None,
    ) -> object:
        calls.append((method, path, payload))
        if path == "/v1/revision":
            return revision
        return {"status": "accepted", "resulting_revision": revision}

    monkeypatch.setattr(wire_cli, "_request", fake_request)

    result, raw = wire_cli._run_fast(
        [
            "hot-execute",
            "entity|Attack|uuid=target",
            "--extra-target",
            "target-2",
            "--token",
            "test-token",
        ]
    )

    assert raw is None
    assert result == {"status": "accepted", "resulting_revision": revision}
    assert calls[0][0:2] == ("GET", "/v1/revision")
    assert calls[1][0:2] == ("POST", "/v1/execute/compact")
    assert calls[1][2] == {
        "revision": revision,
        "row_id": "entity|Attack|uuid=target",
        "prefer_safe": True,
        "extra_target_uuids": ["target-2"],
    }


def test_fast_turn_and_transcript_export_use_daemon_owned_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Briefs and complete evidence come from the same persistent process."""
    calls: list[str] = []

    def fake_request(
        _base_url: str,
        _token: str,
        _method: str,
        path: str,
        _payload: object = None,
    ) -> object:
        calls.append(path)
        if path == "/v1/brief":
            return {"revision": {"observation_cursor": 4}, "action_families": []}
        return {"record_count": 3, "records": []}

    monkeypatch.setattr(wire_cli, "_request", fake_request)
    brief, _raw = wire_cli._run_fast(["hot-turn", "--token", "test-token"])
    destination = tmp_path / "session.json"
    exported, _raw = wire_cli._run_fast(
        ["hot-transcript", "--token", "test-token", "--output", str(destination)]
    )

    assert brief == {"revision": {"observation_cursor": 4}, "action_families": []}
    assert exported == {"output": str(destination), "record_count": 3}
    assert json.loads(destination.read_text(encoding="utf-8"))["record_count"] == 3
    assert calls == ["/v1/brief", "/v1/transcript"]
