"""Typer command surface for Codex controller tools."""

from __future__ import annotations

import json
from typing import Optional

import typer

from ai.codex_tools.client import CodexToolClient, CodexToolHTTPError

app = typer.Typer(help="Typed tools for hot Codex control of D&D engine sessions.")


@app.command()
def takeover(
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
    faction: str = typer.Option("monsters", "--faction"),
    session_id: Optional[str] = typer.Option(None, "--session-id"),
    name: str = typer.Option("Codex Monsters", "--name"),
    force: bool = typer.Option(False, "--force"),
    lease_seconds: float = typer.Option(120.0, "--lease-seconds"),
) -> None:
    """Claim a faction for Codex control."""
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
    """Release a Codex takeover claim."""
    with _client(base_url) as client:
        _emit(client.release(claim_id))


@app.command()
def heartbeat(
    claim_id: str = typer.Option(..., "--claim-id"),
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
) -> None:
    """Refresh a Codex takeover claim."""
    with _client(base_url) as client:
        _emit(client.heartbeat(claim_id))


@app.command()
def brief(
    session_id: str = typer.Option(..., "--session-id"),
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
) -> None:
    """Show the current subjective Codex session brief."""
    with _client(base_url) as client:
        _emit(client.brief(session_id).model_dump(mode="json"))


@app.command()
def actions(
    session_id: str = typer.Option(..., "--session-id"),
    entity_uuid: str = typer.Option(..., "--entity"),
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
    basis_cursor: Optional[int] = typer.Option(None, "--basis-cursor"),
) -> None:
    """List executable action row ids for one controlled entity."""
    with _client(base_url) as client:
        _emit(client.actions(session_id, entity_uuid, basis_cursor).model_dump(mode="json"))


@app.command()
def execute(
    session_id: str = typer.Option(..., "--session-id"),
    entity_uuid: str = typer.Option(..., "--entity"),
    row_id: str = typer.Option(..., "--row-id"),
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
    prefer_safe: bool = typer.Option(True, "--prefer-safe/--no-prefer-safe"),
) -> None:
    """Execute one action row id."""
    with _client(base_url) as client:
        _emit(client.execute(session_id, entity_uuid, row_id, prefer_safe).model_dump(mode="json"))


@app.command("end-turn")
def end_turn(
    session_id: str = typer.Option(..., "--session-id"),
    entity_uuid: str = typer.Option(..., "--entity"),
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
) -> None:
    """End the active turn for one controlled entity."""
    with _client(base_url) as client:
        _emit(client.end_turn(session_id, entity_uuid))


@app.command()
def watch(
    session_id: str = typer.Option(..., "--session-id"),
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
    claim_id: Optional[str] = typer.Option(None, "--claim-id"),
    since: int = typer.Option(0, "--since"),
    read_timeout_seconds: float = typer.Option(15.0, "--read-timeout-seconds"),
) -> None:
    """Block until the Codex session has a relevant subjective update."""
    with _client(base_url) as client:
        _emit(client.watch(
            session_id,
            claim_id=claim_id,
            since=since,
            read_timeout_seconds=read_timeout_seconds,
        ).model_dump(mode="json"))


class _client:
    """Context manager for CodexToolClient with CLI error handling."""

    def __init__(self, base_url: str) -> None:
        """Create the context manager."""
        self.client = CodexToolClient(base_url)

    def __enter__(self) -> CodexToolClient:
        """Return the managed client."""
        return self.client

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        """Close the client and convert tool errors to CLI output."""
        self.client.close()
        if isinstance(exc, CodexToolHTTPError):
            _emit({"error": exc.error.model_dump(mode="json")})
            raise typer.Exit(1)
        return False


def _emit(payload: object) -> None:
    """Print a JSON payload."""
    typer.echo(json.dumps(payload, indent=2, default=str))
