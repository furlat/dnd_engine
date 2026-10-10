"""CLI entry point for the persistent Codex runtime and takeover leases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional, cast

import typer
import uvicorn
from pydantic import BaseModel

from ai.codex_tools.client import CodexToolClient, CodexToolHTTPError
from ai.codex_tools.hot_runtime import (
    HotCodexEndTurnRequest,
    HotCodexExecuteRequest,
    HotCodexGeometryRequest,
    HotCodexInspectionGetRequest,
    HotCodexInspectionSearchRequest,
    HotCodexOracleRequest,
    HotCodexSession,
    create_hot_codex_app,
    hot_attach_info,
    new_hot_codex_token,
)
from ai.codex_tools.local_client import HotCodexClientError, HotCodexLocalClient
from ai.codex_tools.representation.geometry import GeometryOperation, GeometryQuery
from ai.codex_tools.representation.inspection import InspectionGetRequest, InspectionSearchRequest
from ai.codex_tools.representation.profiles import BALANCED_V2_PROFILE_ID
from server.runtime_performance import latency_sensitive_gc

app = typer.Typer(help="Persistent typed Codex control of D&D engine sessions.")


@app.command("hot-serve")
def hot_serve(
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
    faction: str = typer.Option("monsters", "--faction"),
    entity_uuid: Optional[list[str]] = typer.Option(None, "--entity"),
    claim_id: Optional[str] = typer.Option(None, "--claim-id"),
    session_id: Optional[str] = typer.Option(None, "--session-id"),
    name: str = typer.Option("Codex", "--name"),
    force: bool = typer.Option(False, "--force"),
    lease_seconds: float = typer.Option(120.0, "--lease-seconds"),
    listen_host: str = typer.Option("127.0.0.1", "--listen-host"),
    port: int = typer.Option(8765, "--port"),
    bearer_token: Optional[str] = typer.Option(None, "--token", envvar="NEURODRAGON_CODEX_TOKEN"),
    representation_profile: str = typer.Option(
        BALANCED_V2_PROFILE_ID,
        "--profile",
        help="Typed Codex representation profile used for automatic context.",
    ),
    transcript_directory: Path = typer.Option(
        Path("game_logs/codex_sessions"),
        "--transcript-directory",
        help="Append-only subjective session evidence directory.",
    ),
    command_diagnostics: bool = typer.Option(
        False,
        "--command-diagnostics/--no-command-diagnostics",
        help="Request deep server timing trees in command results.",
    ),
) -> None:
    """Run one authenticated daemon over a persistent local subjective runtime."""
    if listen_host not in {"127.0.0.1", "localhost", "::1"}:
        raise typer.BadParameter("The hot Codex daemon must listen on loopback")
    if claim_id is not None and force:
        raise typer.BadParameter("--claim-id cannot be combined with --force")
    token = bearer_token or new_hot_codex_token()
    with latency_sensitive_gc():
        session = HotCodexSession.attach(
            base_url=base_url,
            faction=faction,
            entity_uuids=entity_uuid,
            claim_id=claim_id,
            session_id=session_id,
            name=name,
            force=force,
            lease_seconds=lease_seconds,
            representation_profile_id=representation_profile,
            transcript_directory=transcript_directory,
            include_command_diagnostics=command_diagnostics,
        )
        app_instance = create_hot_codex_app(session, bearer_token=token)
        descriptor = hot_attach_info(session, token).model_dump(mode="json")
        descriptor["local_url"] = f"http://{listen_host}:{port}"
        _emit(descriptor)
        try:
            uvicorn.run(app_instance, host=listen_host, port=port, log_level="warning")
        finally:
            session.release()


@app.command()
def takeover(
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
    faction: str = typer.Option("monsters", "--faction"),
    session_id: Optional[str] = typer.Option(None, "--session-id"),
    name: str = typer.Option("Codex Monsters", "--name"),
    force: bool = typer.Option(False, "--force"),
    lease_seconds: float = typer.Option(120.0, "--lease-seconds"),
) -> None:
    """Create a takeover lease for a persistent Codex runtime."""
    with _client(base_url) as client:
        _emit(client.takeover(
            faction=faction,
            session_id=session_id,
            name=name,
            force=force,
            lease_seconds=lease_seconds,
        ))


@app.command()
def release(
    claim_id: str = typer.Option(..., "--claim-id"),
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
) -> None:
    """Release a Codex takeover lease."""
    with _client(base_url) as client:
        _emit(client.release(claim_id))


@app.command()
def heartbeat(
    claim_id: str = typer.Option(..., "--claim-id"),
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
) -> None:
    """Refresh a Codex takeover lease."""
    with _client(base_url) as client:
        _emit(client.heartbeat(claim_id))


@app.command("hot-turn")
def hot_turn(
    local_url: str = typer.Option("http://127.0.0.1:8765", "--local-url"),
    token: str = typer.Option(..., "--token", envvar="NEURODRAGON_CODEX_TOKEN"),
) -> None:
    """Print the current typed compatibility turn view."""
    with _hot_client(local_url, token) as client:
        _emit(client.turn())


@app.command("hot-watch")
def hot_watch(
    local_url: str = typer.Option("http://127.0.0.1:8765", "--local-url"),
    token: str = typer.Option(..., "--token", envvar="NEURODRAGON_CODEX_TOKEN"),
) -> None:
    """Wait for a controlled decision epoch and print its typed turn view."""
    with _hot_client(local_url, token) as client:
        _emit(client.watch())


@app.command("hot-representation")
def hot_representation(
    local_url: str = typer.Option("http://127.0.0.1:8765", "--local-url"),
    token: str = typer.Option(..., "--token", envvar="NEURODRAGON_CODEX_TOKEN"),
) -> None:
    """Print the active profile-driven representation envelope."""
    with _hot_client(local_url, token) as client:
        _emit(client.representation())


@app.command("hot-export")
def hot_export(
    local_url: str = typer.Option("http://127.0.0.1:8765", "--local-url"),
    token: str = typer.Option(..., "--token", envvar="NEURODRAGON_CODEX_TOKEN"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    """Export canonical complete local subjective JSON for rg or jq."""
    with _hot_client(local_url, token) as client:
        exported = client.inspection_export().export
    if output is not None:
        output.write_text(exported.canonical_json + "\n", encoding="utf-8")
        _emit({
            "output": str(output),
            "document_digest": exported.document_digest,
            "byte_count": exported.byte_count,
        })
        return
    typer.echo(exported.canonical_json)


@app.command("hot-get")
def hot_get(
    pointer: list[str] = typer.Option(..., "--pointer"),
    local_url: str = typer.Option("http://127.0.0.1:8765", "--local-url"),
    token: str = typer.Option(..., "--token", envvar="NEURODRAGON_CODEX_TOKEN"),
) -> None:
    """Read exact canonical JSON pointers from the current local revision."""
    with _hot_client(local_url, token) as client:
        revision = client.turn().revision
        _emit(client.inspection_get(HotCodexInspectionGetRequest(
            revision=revision,
            query=InspectionGetRequest(pointers=tuple(pointer)),
        )))


@app.command("hot-search")
def hot_search(
    pattern: str = typer.Argument(...),
    root: Optional[list[str]] = typer.Option(None, "--root"),
    limit: int = typer.Option(50, "--limit", min=1, max=500),
    local_url: str = typer.Option("http://127.0.0.1:8765", "--local-url"),
    token: str = typer.Option(..., "--token", envvar="NEURODRAGON_CODEX_TOKEN"),
) -> None:
    """Search canonical subjective paths and scalar values locally."""
    with _hot_client(local_url, token) as client:
        revision = client.turn().revision
        _emit(client.inspection_search(HotCodexInspectionSearchRequest(
            revision=revision,
            query=InspectionSearchRequest(
                pattern=pattern,
                roots=tuple(root or ()),
                limit=limit,
            ),
        )))


@app.command("hot-geometry")
def hot_geometry(
    operation: GeometryOperation = typer.Option(..., "--operation"),
    origin: Optional[str] = typer.Option(None, "--origin", help="Grid position as x,y."),
    target: Optional[str] = typer.Option(None, "--target", help="Grid position as x,y."),
    row_id: Optional[str] = typer.Option(None, "--row-id"),
    target_index: Optional[int] = typer.Option(None, "--target-index", min=0),
    prefer_safe: bool = typer.Option(True, "--prefer-safe/--ordinary-route"),
    local_url: str = typer.Option("http://127.0.0.1:8765", "--local-url"),
    token: str = typer.Option(..., "--token", envvar="NEURODRAGON_CODEX_TOKEN"),
) -> None:
    """Evaluate typed distance, line-of-sight, or row-route geometry."""
    with _hot_client(local_url, token) as client:
        revision = client.turn().revision
        query = GeometryQuery(
            operation=operation,
            origin=_position(origin) if origin is not None else None,
            target=_position(target) if target is not None else None,
            row_id=row_id,
            target_index=target_index,
            prefer_safe=prefer_safe,
        )
        _emit(client.geometry(HotCodexGeometryRequest(revision=revision, query=query)))


@app.command("hot-oracle")
def hot_oracle(
    detail: str = typer.Option("selected_only", "--detail"),
    local_url: str = typer.Option("http://127.0.0.1:8765", "--local-url"),
    token: str = typer.Option(..., "--token", envvar="NEURODRAGON_CODEX_TOKEN"),
) -> None:
    """Request the explicitly separated traditional-policy oracle."""
    if detail not in {"selected_only", "ranked", "full_trace"}:
        raise typer.BadParameter("--detail must be selected_only, ranked, or full_trace")
    with _hot_client(local_url, token) as client:
        revision = client.turn().revision
        _emit(client.oracle(HotCodexOracleRequest(
            revision=revision,
            detail=cast(Literal["selected_only", "ranked", "full_trace"], detail),
        )))


@app.command("hot-execute")
def hot_execute(
    row_id: str = typer.Argument(...),
    extra_target: Optional[list[str]] = typer.Option(None, "--extra-target"),
    prefer_safe: bool = typer.Option(True, "--prefer-safe/--ordinary-route"),
    local_url: str = typer.Option("http://127.0.0.1:8765", "--local-url"),
    token: str = typer.Option(..., "--token", envvar="NEURODRAGON_CODEX_TOKEN"),
) -> None:
    """Execute one server-issued row from the current local revision."""
    with _hot_client(local_url, token) as client:
        revision = client.turn().revision
        _emit(client.execute(HotCodexExecuteRequest(
            revision=revision,
            row_id=row_id,
            prefer_safe=prefer_safe,
            extra_target_uuids=extra_target,
        )))


@app.command("hot-end-turn")
def hot_end_turn(
    local_url: str = typer.Option("http://127.0.0.1:8765", "--local-url"),
    token: str = typer.Option(..., "--token", envvar="NEURODRAGON_CODEX_TOKEN"),
) -> None:
    """End the exact current controlled epoch."""
    with _hot_client(local_url, token) as client:
        revision = client.turn().revision
        _emit(client.end_turn(HotCodexEndTurnRequest(revision=revision)))


@app.command("hot-release")
def hot_release(
    local_url: str = typer.Option("http://127.0.0.1:8765", "--local-url"),
    token: str = typer.Option(..., "--token", envvar="NEURODRAGON_CODEX_TOKEN"),
) -> None:
    """Release the task-local runtime and its takeover claim."""
    with _hot_client(local_url, token) as client:
        _emit(client.release())


class _client:
    """Context manager for takeover transport with structured CLI failures."""

    def __init__(self, base_url: str) -> None:
        """Create the managed takeover transport."""
        self.client = CodexToolClient(base_url)

    def __enter__(self) -> CodexToolClient:
        """Return the managed transport."""
        return self.client

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        """Close transport and convert structured errors to CLI output."""
        self.client.close()
        if isinstance(exc, CodexToolHTTPError):
            _emit({"error": exc.error.model_dump(mode="json")})
            raise typer.Exit(1)
        return False


class _hot_client:
    """Context manager for the typed task-local Codex transport."""

    def __init__(self, local_url: str, token: str) -> None:
        """Create the managed local transport."""
        self.client = HotCodexLocalClient(local_url, token)

    def __enter__(self) -> HotCodexLocalClient:
        """Return the managed typed client."""
        return self.client

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        """Close transport and convert structured local failures to CLI JSON."""
        self.client.close()
        if isinstance(exc, HotCodexClientError):
            _emit({"error": exc.failure.model_dump(mode="json")})
            raise typer.Exit(1)
        return False


def _position(value: str) -> tuple[int, int]:
    """Parse one strict comma-separated grid position."""
    try:
        x_text, y_text = value.split(",", maxsplit=1)
        return int(x_text), int(y_text)
    except (ValueError, TypeError) as exc:
        raise typer.BadParameter("positions must use the form x,y") from exc


def _emit(payload: object) -> None:
    """Print one JSON payload."""
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json")
    typer.echo(json.dumps(payload, indent=2, default=str))
