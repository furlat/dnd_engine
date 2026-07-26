"""Administrator CLI for deterministic content-pack inspection and validation."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from typing import TextIO

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin import BUILT_IN_PACK_VERSIONS
from dnd.content_system.configuration import configured_content_pack_roots
from dnd.content_system.pack_loader import discover_content_packs


CLI_SCHEMA_VERSION = 1
CONTENT_SYSTEM_FAILURE_EXIT_CODE = 1
CONTENT_SYSTEM_FAILURE_CODE = "content_system_validation_failed"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m dnd.content_system.cli",
        description="Inspect and validate the configured D&D content set.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "list",
        help="List cold built-in and installed external pack identities.",
    )
    commands.add_parser(
        "validate",
        help="Fully load and freeze the configured content set.",
    )
    commands.add_parser(
        "digest",
        help="Emit the fully validated content-set digest.",
    )
    return parser


def _list_payload(
    environment: Mapping[str, str] | None,
) -> dict[str, object]:
    roots = configured_content_pack_roots(environment)
    external_packs = discover_content_packs(roots)
    packs: list[dict[str, object]] = [
        {
            "origin": "built_in",
            "pack_id": pack_id,
            "pack_version": pack_version,
        }
        for pack_id, pack_version in sorted(BUILT_IN_PACK_VERSIONS.items())
    ]
    packs.extend(
        {
            "origin": "external",
            "pack_digest": pack.discovery_pack_digest,
            "pack_id": pack.manifest.pack_id,
            "pack_version": pack.manifest.pack_version,
        }
        for pack in external_packs
    )
    return {
        "command": "list",
        "ok": True,
        "packs": packs,
        "schema_version": CLI_SCHEMA_VERSION,
    }


def _validated_payload(
    command: str,
    environment: Mapping[str, str] | None,
) -> dict[str, object]:
    roots = configured_content_pack_roots(environment)
    loaded = bootstrap_content_system(pack_roots=roots)
    return {
        "command": command,
        "content_set_digest": loaded.content_set_digest,
        "ok": True,
        "schema_version": CLI_SCHEMA_VERSION,
    }


def _failure_payload(command: str, error: Exception) -> dict[str, object]:
    return {
        "command": command,
        "diagnostic": {
            "code": CONTENT_SYSTEM_FAILURE_CODE,
            "exception_type": type(error).__name__,
            "message": str(error),
        },
        "ok": False,
        "schema_version": CLI_SCHEMA_VERSION,
    }


def _write_json(stream: TextIO, payload: Mapping[str, object]) -> None:
    stream.write(
        json.dumps(
            dict(payload),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
    )
    stream.write("\n")
    stream.flush()


def main(
    argv: Sequence[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one administrator command and return its process exit code."""
    output = sys.stdout if stdout is None else stdout
    error_output = sys.stderr if stderr is None else stderr
    arguments = _build_parser().parse_args(
        None if argv is None else list(argv),
    )
    command = str(arguments.command)
    try:
        payload = (
            _list_payload(environment)
            if command == "list"
            else _validated_payload(command, environment)
        )
    except Exception as error:
        _write_json(error_output, _failure_payload(command, error))
        return CONTENT_SYSTEM_FAILURE_EXIT_CODE
    _write_json(output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
