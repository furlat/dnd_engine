"""Filesystem/setup lane: observable CLI behavior with tiny local art bundles."""

import json
from argparse import Namespace
from pathlib import Path
import subprocess
import sys

import pytest

from devtools.art import install


SCRIPT = Path(__file__).resolve().parents[1] / "devtools/art.py"


def run(*args: object, ok: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                            capture_output=True, text=True)
    assert (result.returncode == 0) == ok, result.stdout + result.stderr
    return result


def bundle(tmp_path: Path) -> tuple[Path, Path]:
    source, private = tmp_path / "authoring", tmp_path / "private"
    assets = source / "game/assets/example"
    assets.mkdir(parents=True)
    for name, data in {"color.png": b"pixels", "000.bin.gz": b"xyz companion",
                       "manifest.json": b'{"frames": 1}', "position.png": b"footpoints"}.items():
        (assets / name).write_bytes(data)
    run("export", "--root", source, "--destination", private)
    return source, private


def test_complete_install_repeat_update_and_cache_preservation(tmp_path):
    source, private = bundle(tmp_path)
    target = tmp_path / "engine"
    cache = target / "game/assets/local-cache.bin"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"keep me")
    run("install", "--source", private, "--root", target)
    run("check", "--root", target, "--hashes")
    repeat = run("install", "--source", private, "--root", target)
    assert "0 copied" in repeat.stdout
    for path in (source / "game/assets").rglob("*"):
        if path.is_file():
            assert (target / path.relative_to(source)).read_bytes() == path.read_bytes()
    # A new release can change pixels without changing file size.
    (source / "game/assets/example/color.png").write_bytes(b"second")
    updated = tmp_path / "updated"
    run("export", "--root", source, "--destination", updated)
    run("install", "--source", updated, "--root", target)
    assert (target / "game/assets/example/color.png").read_bytes() == b"second"
    assert cache.read_bytes() == b"keep me"
    assert (source / "game/assets/example/000.bin.gz").read_bytes() == b"xyz companion"


def test_missing_companion_rejects_install_before_changing_existing_art(tmp_path):
    _, private = bundle(tmp_path)
    target = tmp_path / "engine"
    existing = target / "game/assets/example/color.png"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"working installation")
    (private / "game/assets/example/000.bin.gz").unlink()
    result = run("install", "--source", private, "--root", target, ok=False)
    assert "000.bin.gz" in result.stderr
    assert existing.read_bytes() == b"working installation"


def test_deep_integrity_check_is_explicit_and_missing_setup_explains_install(tmp_path):
    _, private = bundle(tmp_path)
    (private / "game/assets/example/color.png").write_bytes(b"BROKEN")
    target = tmp_path / "engine"
    run("install", "--source", private, "--root", target)
    run("check", "--root", target)
    result = run("check", "--root", target, "--hashes", ok=False)
    assert "color.png" in result.stderr
    result = run("check", "--root", tmp_path / "absent", ok=False)
    assert "PRIVATE_ART.md" in result.stderr


def test_receipt_reuse_missing_file_repair_and_explicit_reinstall(tmp_path):
    _, private = bundle(tmp_path)
    target = tmp_path / "engine"
    run("install", "--source", private, "--root", target)
    color = target / "game/assets/example/color.png"
    packet = target / "game/assets/example/000.bin.gz"
    color.write_bytes(b"edited")
    # Ordinary repeat installation trusts its receipt and does not compare all
    # payload contents. Explicit deep checking detects edits, reinstall repairs.
    repeat = run("install", "--source", private, "--root", target)
    assert "0 copied" in repeat.stdout
    assert color.read_bytes() == b"edited"
    run("check", "--root", target, "--hashes", ok=False)
    packet.unlink()
    repaired = run("install", "--source", private, "--root", target)
    assert "1 copied" in repaired.stdout
    assert packet.read_bytes() == b"xyz companion"
    assert color.read_bytes() == b"edited"
    restored = run("install", "--source", private, "--root", target, "--reinstall")
    assert "4 copied" in restored.stdout
    assert color.read_bytes() == b"pixels"
    run("check", "--root", target, "--hashes")


def test_private_manifest_cannot_write_public_code_or_follow_escape(tmp_path):
    _, private = bundle(tmp_path)
    manifest_path = private / "art-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for bad in ("game/assets/../../game/play.py", "game/play.py", "/tmp/outside"):
        manifest["files"][0]["path"] = bad
        manifest_path.write_text(json.dumps(manifest))
        run("install", "--source", private, "--root", tmp_path / "engine", ok=False)


def test_export_preserves_existing_private_directory_and_rejects_lfs_pointers(tmp_path):
    source, private = bundle(tmp_path)
    run("export", "--root", source, "--destination", private, ok=False)
    (source / "game/assets/example/color.png").write_bytes(
        b"version https://git-lfs.github.com/spec/v1\noid sha256:unhydrated\n")
    run("export", "--root", source, "--destination", tmp_path / "pointer-export", ok=False)


def test_install_rejects_symlink_into_public_code(tmp_path):
    _, private = bundle(tmp_path)
    target = tmp_path / "engine"
    public = target / "game/example"
    public.mkdir(parents=True)
    (public / "color.png").write_bytes(b"do not replace")
    (target / "game/assets").symlink_to(target / "game", target_is_directory=True)
    run("install", "--source", private, "--root", target, ok=False)
    assert (public / "color.png").read_bytes() == b"do not replace"


def test_install_receipt_is_metadata_not_a_second_asset_tree(tmp_path):
    _, private = bundle(tmp_path)
    target = tmp_path / "engine"
    run("install", "--source", private, "--root", target)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    # No payload lives below the receipt's .runtime directory. Its manifest
    # must not consult this unrelated tree while comparing published entries.
    (target / ".runtime/game").symlink_to(unrelated, target_is_directory=True)
    repeat = run("install", "--source", private, "--root", target)
    assert "0 copied" in repeat.stdout
    run("check", "--root", target)
    assert not list(unrelated.iterdir())


@pytest.mark.parametrize("side,leaf", (("source", False), ("source", True),
                                       ("destination", False), ("destination", True)))
def test_install_rechecks_parent_and_leaf_links_between_calls(tmp_path, side, leaf):
    _, private = bundle(tmp_path)
    target = tmp_path / "engine"
    args = Namespace(cache=tmp_path / "cache", root=target, source=private, reinstall=False)
    install(args)
    root = private if side == "source" else target
    selected = root / "game/assets/example"
    if leaf:
        selected /= "color.png"
    protected = tmp_path / "protected"
    selected.rename(protected)
    selected.symlink_to(protected, target_is_directory=not leaf)
    # The second call is deliberately in the same process: no remembered
    # directory approval from the first call may hide this replacement.
    args.reinstall = side == "source"
    with pytest.raises(ValueError, match="symlink"):
        install(args)
    preserved = protected if leaf else protected / "color.png"
    assert preserved.read_bytes() == b"pixels"


def test_install_rejects_unhydrated_source_before_replacing_files(tmp_path):
    _, private = bundle(tmp_path)
    target = tmp_path / "engine"
    run("install", "--source", private, "--root", target)
    before = (target / "game/assets/example/color.png").read_bytes()
    pointer = b"version https://git-lfs.github.com/spec/v1\noid sha256:unhydrated\n"
    (private / "game/assets/example/color.png").write_bytes(pointer)
    manifest = json.loads((private / "art-manifest.json").read_text())
    next(row for row in manifest["files"] if row["path"].endswith("color.png"))["bytes"] = len(pointer)
    (private / "art-manifest.json").write_text(json.dumps(manifest))
    run("install", "--source", private, "--root", target, ok=False)
    assert (target / "game/assets/example/color.png").read_bytes() == before
