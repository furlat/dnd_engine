"""Dependency-light HTTP CLI for an already running hot Codex daemon."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_FAST_COMMANDS = {
    "hot-end-turn",
    "hot-execute",
    "hot-export",
    "hot-geometry",
    "hot-get",
    "hot-health",
    "hot-oracle",
    "hot-release",
    "hot-representation",
    "hot-search",
    "hot-transcript",
    "hot-transcript-status",
    "hot-turn",
    "hot-watch",
}


class WireCliError(RuntimeError):
    """Structured local daemon or command-line failure."""


def main(argv: Optional[list[str]] = None) -> None:
    """Dispatch hot calls locally and heavy lifecycle commands out of process."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] not in _FAST_COMMANDS:
        _exec_heavy(arguments)
    try:
        result, raw_text = _run_fast(arguments)
    except WireCliError as exc:
        _print_json({"error": {"code": "wire_cli_error", "message": str(exc)}})
        raise SystemExit(1) from exc
    if raw_text is not None:
        print(raw_text)
    elif result is not None:
        _print_json(result)


def _run_fast(arguments: list[str]) -> tuple[Optional[Any], Optional[str]]:
    """Parse and execute one dependency-light daemon operation."""
    command = arguments[0]
    parser = argparse.ArgumentParser(prog=f"ai.codex_tools {command}")
    _add_connection_options(parser)

    if command == "hot-execute":
        parser.add_argument("row_id")
        parser.add_argument("--extra-target", action="append", default=None)
        route_group = parser.add_mutually_exclusive_group()
        route_group.add_argument("--prefer-safe", dest="prefer_safe", action="store_true")
        route_group.add_argument("--ordinary-route", dest="prefer_safe", action="store_false")
        parser.set_defaults(prefer_safe=True)
    elif command == "hot-get":
        parser.add_argument("--pointer", action="append", required=True)
    elif command == "hot-search":
        parser.add_argument("pattern")
        parser.add_argument("--root", action="append", default=[])
        parser.add_argument("--limit", type=int, default=50)
    elif command == "hot-geometry":
        parser.add_argument("--operation", required=True)
        parser.add_argument("--origin")
        parser.add_argument("--target")
        parser.add_argument("--row-id")
        parser.add_argument("--target-index", type=int)
        route_group = parser.add_mutually_exclusive_group()
        route_group.add_argument("--prefer-safe", dest="prefer_safe", action="store_true")
        route_group.add_argument("--ordinary-route", dest="prefer_safe", action="store_false")
        parser.set_defaults(prefer_safe=True)
    elif command == "hot-oracle":
        parser.add_argument(
            "--detail",
            choices=("selected_only", "ranked", "full_trace"),
            default="selected_only",
        )
    elif command in {"hot-export", "hot-transcript"}:
        parser.add_argument("--output", type=Path)

    parsed = parser.parse_args(arguments[1:])
    local_url = parsed.local_url.rstrip("/")
    token = parsed.token or os.environ.get("NEURODRAGON_CODEX_TOKEN")
    if not token:
        raise WireCliError("--token or NEURODRAGON_CODEX_TOKEN is required")

    if command == "hot-health":
        return _request(local_url, token, "GET", "/v1/health"), None
    if command == "hot-turn":
        return _request(local_url, token, "GET", "/v1/brief"), None
    if command == "hot-watch":
        return _request(local_url, token, "POST", "/v1/watch/brief", {}), None
    if command == "hot-representation":
        return _request(local_url, token, "GET", "/v1/representation/current"), None
    if command == "hot-release":
        return _request(local_url, token, "POST", "/v1/release", {}), None
    if command == "hot-transcript-status":
        return _request(local_url, token, "GET", "/v1/transcript/status"), None
    if command == "hot-transcript":
        transcript = _request(local_url, token, "GET", "/v1/transcript")
        if parsed.output is not None:
            parsed.output.write_text(_canonical_json(transcript) + "\n", encoding="utf-8")
            return {"output": str(parsed.output), "record_count": transcript["record_count"]}, None
        return transcript, None
    if command == "hot-export":
        exported = _request(local_url, token, "GET", "/v1/inspect/export")
        canonical = exported["export"]["canonical_json"]
        if parsed.output is not None:
            parsed.output.write_text(canonical + "\n", encoding="utf-8")
            return {
                "output": str(parsed.output),
                "document_digest": exported["export"]["document_digest"],
                "byte_count": exported["export"]["byte_count"],
            }, None
        return None, canonical

    revision = _request(local_url, token, "GET", "/v1/revision")
    if command == "hot-execute":
        return _request(
            local_url,
            token,
            "POST",
            "/v1/execute/compact",
            {
                "revision": revision,
                "row_id": parsed.row_id,
                "prefer_safe": parsed.prefer_safe,
                "extra_target_uuids": parsed.extra_target,
            },
        ), None
    if command == "hot-end-turn":
        return _request(
            local_url,
            token,
            "POST",
            "/v1/end-turn/compact",
            {"revision": revision},
        ), None
    if command == "hot-get":
        return _request(
            local_url,
            token,
            "POST",
            "/v1/inspect/get",
            {"revision": revision, "query": {"pointers": parsed.pointer}},
        ), None
    if command == "hot-search":
        return _request(
            local_url,
            token,
            "POST",
            "/v1/inspect/search",
            {
                "revision": revision,
                "query": {"pattern": parsed.pattern, "roots": parsed.root, "limit": parsed.limit},
            },
        ), None
    if command == "hot-geometry":
        return _request(
            local_url,
            token,
            "POST",
            "/v1/geometry/query",
            {
                "revision": revision,
                "query": {
                    "operation": parsed.operation,
                    "origin": _position(parsed.origin),
                    "target": _position(parsed.target),
                    "row_id": parsed.row_id,
                    "target_index": parsed.target_index,
                    "prefer_safe": parsed.prefer_safe,
                },
            },
        ), None
    if command == "hot-oracle":
        return _request(
            local_url,
            token,
            "POST",
            "/v1/representation/oracle",
            {"revision": revision, "detail": parsed.detail},
        ), None
    raise WireCliError(f"Unsupported fast command: {command}")


def _add_connection_options(parser: argparse.ArgumentParser) -> None:
    """Add common authenticated loopback options."""
    parser.add_argument("--local-url", default="http://127.0.0.1:8765")
    parser.add_argument("--token", default=None)


def _request(
    base_url: str,
    token: str,
    method: str,
    path: str,
    payload: Optional[dict[str, Any]] = None,
) -> Any:
    """Make one authenticated JSON request to the persistent daemon."""
    encoded = None if payload is None else _canonical_json(payload).encode("utf-8")
    request = Request(
        f"{base_url}{path}",
        data=encoded,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=300.0) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise WireCliError(f"daemon returned HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise WireCliError(f"cannot reach hot daemon at {base_url}: {exc.reason}") from exc


def _position(value: Optional[str]) -> Optional[list[int]]:
    """Parse an optional x,y grid coordinate into JSON form."""
    if value is None:
        return None
    try:
        x_text, y_text = value.split(",", maxsplit=1)
        return [int(x_text), int(y_text)]
    except ValueError as exc:
        raise WireCliError("positions must use the form x,y") from exc


def _canonical_json(value: Any) -> str:
    """Return deterministic compact JSON for wire payloads and artifacts."""
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _print_json(value: Any) -> None:
    """Print readable JSON while retaining a small response surface."""
    print(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True))


def _exec_heavy(arguments: list[str]) -> None:
    """Replace this lightweight process with the existing lifecycle CLI."""
    os.execv(
        sys.executable,
        [sys.executable, "-m", "ai.codex_tools.heavy_cli", *arguments],
    )
