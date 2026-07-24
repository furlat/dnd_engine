"""Command-line entry point for structured AI gauntlets."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Optional, cast

import httpx
import typer

from ai.evaluation.gauntlet import (
    GauntletEvent,
    GauntletEventStream,
    GauntletEventType,
    GauntletMode,
    GauntletSchedule,
    GauntletSummary,
    apply_gauntlet_latency_audit,
    build_gauntlet_schedule,
    build_regression_schedule,
    run_ai_gauntlet,
    validate_gauntlet_summary_evidence,
)


class GauntletModeOption(str, Enum):
    """CLI-safe gauntlet mode values."""

    smoke = "smoke"
    rotation = "rotation"
    content = "content"
    regression = "regression"
    release = "release"


app = typer.Typer(help="Run structured NeuroDragon AI gauntlets.")


@app.command("schedule")
def schedule_command(
    mode: GauntletModeOption = typer.Option(GauntletModeOption.smoke, "--mode"),
    arena_id: Optional[list[str]] = typer.Option(None, "--arena-id", help="Arena id. Repeat to override mode defaults."),
    seed: Optional[list[int]] = typer.Option(None, "--seed", help="Seed. Repeat to override mode defaults."),
    policy_version: Optional[str] = typer.Option(None, "--policy-version"),
    regression_source: Optional[Path] = typer.Option(None, "--regression-source", help="Retained gauntlet summary JSON to replay failures from."),
) -> None:
    """Print a deterministic gauntlet schedule without running matches."""
    schedule = _build_schedule(mode, arena_id, seed, policy_version, regression_source)
    _emit(schedule.model_dump(mode="json"))


@app.command("run")
def run_command(
    mode: GauntletModeOption = typer.Option(GauntletModeOption.smoke, "--mode"),
    arena_id: Optional[list[str]] = typer.Option(None, "--arena-id", help="Arena id. Repeat to override mode defaults."),
    seed: Optional[list[int]] = typer.Option(None, "--seed", help="Seed. Repeat to override mode defaults."),
    policy_version: Optional[str] = typer.Option(None, "--policy-version"),
    max_commands: Optional[int] = typer.Option(
        None,
        "--max-commands",
        min=1,
        help="Maximum commands per match. Defaults by gauntlet mode.",
    ),
    runs_output_directory: Path = typer.Option(Path("ai/evidence/runs"), "--runs-output-directory"),
    gauntlet_output_directory: Path = typer.Option(Path("evidence/gauntlets"), "--gauntlet-output-directory"),
    no_run_artifacts: bool = typer.Option(False, "--no-run-artifacts"),
    no_summary_file: bool = typer.Option(False, "--no-summary-file"),
    watcher_base_url: Optional[str] = typer.Option(None, "--watcher-base-url", help="Backend URL that should receive live gauntlet watcher events."),
    regression_source: Optional[Path] = typer.Option(None, "--regression-source", help="Retained gauntlet summary JSON to replay failures from."),
    require_gate_pass: bool = typer.Option(False, "--require-gate-pass", help="Exit nonzero after writing evidence unless the summary gate passed."),
    require_latency_pass: bool = typer.Option(False, "--require-latency-pass", help="Exit nonzero after writing evidence unless the retained latency audit passed."),
) -> None:
    """Run a gauntlet and print its compact JSON summary."""
    schedule = _build_schedule(mode, arena_id, seed, policy_version, regression_source)
    effective_max_commands = max_commands if max_commands is not None else _default_max_commands_for_mode(mode)
    event_stream = HttpMirroringGauntletEventSink(watcher_base_url) if watcher_base_url else None
    try:
        summary = run_ai_gauntlet(
            schedule,
            max_commands=effective_max_commands,
            runs_output_directory=None if no_run_artifacts else runs_output_directory,
            gauntlet_output_directory=None if no_summary_file else gauntlet_output_directory,
            event_stream=event_stream,
        )
    finally:
        if event_stream is not None:
            event_stream.close()
    _emit(summary.model_dump(mode="json"))
    if require_gate_pass and summary.gate_status != "passed":
        raise typer.Exit(code=2)
    if require_latency_pass and summary.latency_status != "passed":
        raise typer.Exit(code=3)


@app.command("check")
def check_command(
    summary_path: Path = typer.Argument(..., help="Retained gauntlet summary JSON to check."),
    require_gate_pass: bool = typer.Option(False, "--require-gate-pass", help="Exit nonzero unless the retained summary gate passed."),
    require_latency_pass: bool = typer.Option(False, "--require-latency-pass", help="Exit nonzero unless the retained summary latency audit passed."),
) -> None:
    """Print and optionally gate-check one retained gauntlet summary."""
    summary = apply_gauntlet_latency_audit(GauntletSummary.model_validate_json(summary_path.read_text(encoding="utf-8")))
    validate_gauntlet_summary_evidence(summary)
    _emit(summary.model_dump(mode="json"))
    if require_gate_pass and summary.gate_status != "passed":
        raise typer.Exit(code=2)
    if require_latency_pass and summary.latency_status != "passed":
        raise typer.Exit(code=3)


class HttpMirroringGauntletEventSink:
    """Local gauntlet event sink that mirrors events to a running backend."""

    def __init__(self, base_url: str, client: Optional[httpx.Client] = None) -> None:
        """Create a mirror for `/ai/gauntlets/events`."""
        self.base_url = base_url.rstrip("/")
        self._local = GauntletEventStream()
        self._client = client or httpx.Client(base_url=self.base_url, timeout=10.0)
        self._owns_client = client is None

    def append(
        self,
        *,
        event_type: GauntletEventType,
        gauntlet_id: str,
        match_id: Optional[str] = None,
        match_index: Optional[int] = None,
        status: Optional[str] = None,
        message: Optional[str] = None,
        payload: Optional[dict[str, object]] = None,
    ) -> GauntletEvent:
        """Append locally and publish the same event to the backend."""
        event = self._local.append(
            event_type=event_type,
            gauntlet_id=gauntlet_id,
            match_id=match_id,
            match_index=match_index,
            status=status,
            message=message,
            payload=payload,
        )
        response = self._client.post("/ai/gauntlets/events", json={"events": [event.model_dump(mode="json")]})
        response.raise_for_status()
        return event

    def since(self, cursor: int = 0) -> list[GauntletEvent]:
        """Return local retained events after a cursor."""
        return self._local.since(cursor)

    def close(self) -> None:
        """Close the owned HTTP client."""
        if self._owns_client:
            self._client.close()


def _build_schedule(
    mode: GauntletModeOption,
    arena_ids: Optional[list[str]],
    seeds: Optional[list[int]],
    policy_version: Optional[str],
    regression_source: Optional[Path],
) -> GauntletSchedule:
    if regression_source is not None:
        summary = apply_gauntlet_latency_audit(GauntletSummary.model_validate_json(regression_source.read_text(encoding="utf-8")))
        validate_gauntlet_summary_evidence(summary)
        return build_regression_schedule(summary, policy_version=policy_version)
    return build_gauntlet_schedule(
        cast(GauntletMode, mode.value),
        arena_ids=arena_ids,
        seeds=seeds,
        policy_version=policy_version,
    )


def _default_max_commands_for_mode(mode: GauntletModeOption) -> int:
    """Return a mode-appropriate command cap for CLI gauntlet runs."""
    if mode == GauntletModeOption.content:
        return 200
    if mode == GauntletModeOption.release:
        return 240
    if mode == GauntletModeOption.regression:
        return 200
    return 80


def _emit(payload: object) -> None:
    """Print one JSON payload."""
    typer.echo(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    app()
