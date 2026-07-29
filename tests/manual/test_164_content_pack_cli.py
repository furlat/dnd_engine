"""Deterministic administrator CLI for installed content packs."""

from __future__ import annotations

import json
import os
from io import StringIO
from pathlib import Path

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin import BUILT_IN_PACK_VERSIONS
from dnd.content_system.cli import main
from dnd.content_system.configuration import DEFAULT_CONTENT_PACK_ROOT
from dnd.content_system.pack_loader import discover_content_packs


def _write_pack(
    root: Path,
    *,
    pack_id: str = "fixture.cli",
    package_name: str = "fixture_cli_pack",
    engine_content_api: int = 2,
) -> Path:
    pack_directory = root / "fixture"
    package_directory = pack_directory / "src" / package_name
    package_directory.mkdir(parents=True)
    (pack_directory / "content-pack.toml").write_text(
        "\n".join(
            (
                "schema_version = 1",
                f'pack_id = "{pack_id}"',
                'pack_version = "2.3.4"',
                f"engine_content_api = {engine_content_api}",
                'python_root = "src"',
                f'python_package = "{package_name}"',
                "",
            ),
        ),
        encoding="utf-8",
    )
    (package_directory / "__init__.py").write_text("", encoding="utf-8")
    return pack_directory


def _run(
    command: str,
    *,
    pack_root: Path,
) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    exit_code = main(
        (command,),
        environment={"DND_CONTENT_PACK_ROOTS": str(pack_root)},
        stdout=stdout,
        stderr=stderr,
    )
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _canonical_json(payload: dict[str, object]) -> str:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"


def test_list_is_cold_deterministic_and_includes_builtin_and_external_identity(
    tmp_path: Path,
) -> None:
    """Listing identifies every pack without importing its executable package."""
    root = tmp_path / "packs"
    root.mkdir()
    pack_directory = _write_pack(
        root,
        package_name="fixture_cli_list_pack",
    )
    import_marker = pack_directory / "imported.marker"
    package_init = (
        pack_directory
        / "src"
        / "fixture_cli_list_pack"
        / "__init__.py"
    )
    package_init.write_text(
        "\n".join(
            (
                "from pathlib import Path",
                f"Path({str(import_marker)!r}).write_text('imported')",
                "",
            ),
        ),
        encoding="utf-8",
    )
    external = discover_content_packs((root,))[0]

    exit_code, stdout, stderr = _run("list", pack_root=root)

    expected_packs: list[dict[str, object]] = [
        {
            "origin": "built_in",
            "pack_id": pack_id,
            "pack_version": pack_version,
        }
        for pack_id, pack_version in sorted(BUILT_IN_PACK_VERSIONS.items())
    ]
    expected_packs.append(
        {
            "origin": "external",
            "pack_digest": external.discovery_pack_digest,
            "pack_id": "fixture.cli",
            "pack_version": "2.3.4",
        },
    )
    assert exit_code == 0
    assert stdout == _canonical_json(
        {
            "command": "list",
            "ok": True,
            "packs": expected_packs,
            "schema_version": 1,
        },
    )
    assert stderr == ""
    assert not import_marker.exists()


def test_validate_fully_loads_and_freezes_the_shared_configured_system(
    tmp_path: Path,
) -> None:
    """Validation returns the exact identity of the fully frozen registry."""
    root = tmp_path / "packs"
    root.mkdir()
    _write_pack(root, package_name="fixture_cli_validate_pack")
    expected = bootstrap_content_system(
        pack_roots=(DEFAULT_CONTENT_PACK_ROOT, root),
    )

    exit_code, stdout, stderr = _run("validate", pack_root=root)

    assert exit_code == 0
    assert stdout == _canonical_json(
        {
            "command": "validate",
            "content_set_digest": expected.content_set_digest,
            "ok": True,
            "schema_version": 1,
        },
    )
    assert stderr == ""


def test_digest_emits_the_exact_shared_content_set_digest(tmp_path: Path) -> None:
    """The digest command is a machine-readable deployment identity probe."""
    root = tmp_path / "packs"
    root.mkdir()
    _write_pack(root, package_name="fixture_cli_digest_pack")
    expected = bootstrap_content_system(
        pack_roots=(DEFAULT_CONTENT_PACK_ROOT, root),
    )

    exit_code, stdout, stderr = _run("digest", pack_root=root)

    assert exit_code == 0
    assert stdout == _canonical_json(
        {
            "command": "digest",
            "content_set_digest": expected.content_set_digest,
            "ok": True,
            "schema_version": 1,
        },
    )
    assert stderr == ""


def test_invalid_pack_returns_one_exact_nonzero_structured_diagnostic(
    tmp_path: Path,
) -> None:
    """Administrators receive stable JSON, never a partial success or traceback."""
    root = tmp_path / "packs"
    root.mkdir()
    _write_pack(
        root,
        pack_id="fixture.invalid",
        package_name="fixture_invalid_pack",
        engine_content_api=999,
    )

    exit_code, stdout, stderr = _run("validate", pack_root=root)

    assert exit_code == 1
    assert stdout == ""
    assert stderr == _canonical_json(
        {
            "command": "validate",
            "diagnostic": {
                "code": "content_system_validation_failed",
                "exception_type": "ValueError",
                "message": (
                    "Pack fixture.invalid requires engine content API 999; "
                    "supported API is 2"
                ),
            },
            "ok": False,
            "schema_version": 1,
        },
    )


def test_cli_uses_only_the_configured_root_contract(tmp_path: Path) -> None:
    """The standard deployment environment variable is the sole root input."""
    root = tmp_path / "packs"
    root.mkdir()
    _write_pack(root, package_name="fixture_cli_roots_pack")
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        ("list",),
        environment={
            "DND_CONTENT_PACK_ROOTS": os.pathsep.join((str(root), str(root))),
        },
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    payload = json.loads(stdout.getvalue())
    assert [row["pack_id"] for row in payload["packs"]].count("fixture.cli") == 1
