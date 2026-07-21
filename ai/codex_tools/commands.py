"""CLI entry point for the persistent Codex runtime and takeover leases."""

from __future__ import annotations

import json
from typing import Optional

import typer
import uvicorn

from ai.codex_tools.client import CodexToolClient, CodexToolHTTPError
from ai.codex_tools.hot_runtime import (
    HotCodexSession,
    create_hot_codex_app,
    hot_attach_info,
    new_hot_codex_token,
)
from ai.runtime_performance import latency_sensitive_gc

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


def _emit(payload: object) -> None:
    """Print one JSON payload."""
    typer.echo(json.dumps(payload, indent=2, default=str))
