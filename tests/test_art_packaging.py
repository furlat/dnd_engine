"""Offline release selection uses published metadata and preserves source art."""

import json
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

from devtools.pack_art import build_plan, finish_release, propose_bindings, stage


ROOT = Path(__file__).resolve().parents[1]


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


def bundle(tmp_path: Path) -> tuple[Path, Path]:
    source, archive = tmp_path / "authoring", tmp_path / "archive"
    folder = source / "game/assets/tiny"
    folder.mkdir(parents=True)
    for name, content in {"first.png": b"pixels", "second.png": b"pixels",
                          "xyz.bin.gz": b"numeric companion", "unused.png": b"source only"}.items():
        (folder / name).write_bytes(content)
    subprocess.run([sys.executable, "devtools/art.py", "export", "--root", str(source),
                    "--destination", str(archive)], cwd=ROOT, check=True, capture_output=True)
    manifest = json.loads((archive / "art-manifest.json").read_text())
    rows = [{"path": row["path"], "bytes": row["bytes"], "source_content_id": row["sha256"],
             "decision": "archive_only" if row["path"].endswith("unused.png") else "production"}
            for row in manifest["files"]]
    return archive, write_jsonl(tmp_path / "inventory.jsonl", rows)


def test_plan_uses_metadata_without_opening_or_requiring_payloads(tmp_path):
    archive, inventory = bundle(tmp_path)
    for file in (archive / "game/assets/tiny").iterdir():
        file.unlink()
    plan = build_plan(archive, inventory, None)
    assert plan["counts"]["selected_references"] == 3
    assert plan["counts"]["payload_files"] == 3
    assert plan["counts"]["selected_bytes"] == 29
    assert plan["applied_aliases"] == {}


def test_selected_alias_release_installs_into_empty_tree_without_altering_archive(tmp_path):
    archive, inventory = bundle(tmp_path)
    alias = write_jsonl(tmp_path / "applied.jsonl", [{
        "path": "game/assets/tiny/second.png", "canonical": "game/assets/tiny/first.png"}])
    plan = build_plan(archive, inventory, alias, "public-test-release")
    assert plan["counts"]["payload_files"] == 2
    assert plan["counts"]["payload_bytes"] == 23
    destination = tmp_path / "production"
    stage(archive, destination, plan)
    selected = {p.name: p.read_bytes() for p in (destination / "game/assets/tiny").iterdir()}
    assert selected == {"first.png": b"pixels", "xyz.bin.gz": b"numeric companion"}
    assert (archive / "game/assets/tiny/second.png").read_bytes() == b"pixels"
    assert (archive / "game/assets/tiny/unused.png").read_bytes() == b"source only"
    installed = tmp_path / "game-checkout"
    result = subprocess.run([sys.executable, "devtools/art.py", "install", "--source", str(destination),
                             "--root", str(installed)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert {p.name for p in (installed / "game/assets/tiny").iterdir()} == set(selected)
    assert not (installed / "game/data").exists()
    assert json.loads((installed / ".runtime/art-manifest.json").read_text())["code_release"] == "public-test-release"


@pytest.mark.parametrize("change", ["missing", "identity", "unresolved"])
def test_plan_rejects_incomplete_or_stale_inventory(tmp_path, change):
    archive, inventory = bundle(tmp_path)
    rows = [json.loads(line) for line in inventory.read_text().splitlines()]
    if change == "missing":
        rows.pop()
    elif change == "identity":
        rows[0]["source_content_id"] = "0" * 64
    else:
        rows[0]["decision"] = "unknown"
    write_jsonl(inventory, rows)
    with pytest.raises(ValueError):
        build_plan(archive, inventory, None)


def test_unapplied_duplicate_stays_and_wrong_alias_cannot_drop_companion(tmp_path):
    archive, inventory = bundle(tmp_path)
    assert len(build_plan(archive, inventory, None)["files"]) == 3
    alias = write_jsonl(tmp_path / "wrong.jsonl", [{
        "path": "game/assets/tiny/xyz.bin.gz", "canonical": "game/assets/tiny/first.png"}])
    with pytest.raises(ValueError, match="different published payload"):
        build_plan(archive, inventory, alias)


def test_stage_preflights_missing_input_and_preserves_existing_destinations(tmp_path):
    archive, inventory = bundle(tmp_path)
    plan = build_plan(archive, inventory, None)
    destination = tmp_path / "production"
    packet = archive / "game/assets/tiny/xyz.bin.gz"
    packet.unlink()
    with pytest.raises(ValueError, match="xyz.bin.gz"):
        stage(archive, destination, plan)
    assert not destination.exists()
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("private work")
    with pytest.raises(ValueError, match="must be new"):
        stage(archive, destination, plan)
    assert sentinel.read_text() == "private work"
    with pytest.raises(ValueError, match="outside"):
        stage(archive, archive / "nested-production", plan)


def test_plan_cli_writes_only_requested_metadata_outside_archive(tmp_path):
    archive, inventory = bundle(tmp_path)
    output = tmp_path / "plan.json"
    command = [sys.executable, "-m", "devtools.pack_art", "plan", "--archive", str(archive),
               "--inventory", str(inventory), "--output"]
    result = subprocess.run([*command, str(output)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())["counts"]["payload_files"] == 3
    result = subprocess.run([*command, str(archive / "new.json")], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0
    assert not (archive / "new.json").exists()


def test_binding_proposal_changes_only_explicit_addresses_and_keeps_source_unmodified(tmp_path):
    archive, inventory = bundle(tmp_path)
    plan = build_plan(archive, inventory, None)
    name, canonical = "game/assets/tiny/second.png", "game/assets/tiny/first.png"
    candidates = write_jsonl(tmp_path / "candidates.jsonl", [{"path": name, "canonical": canonical}])
    bindings_root = tmp_path / "data"
    path = bindings_root / "sample/bindings.json"
    path.parent.mkdir(parents=True)
    document = {"resources": {"logical-resource": name}, "projectileStorage": {
        "sample": {"phases": {"impact": {"layers": [{"blendMode": "normal", "parts": [[{
            "file": name, "rect": [12, 34, 2, 2], "offset": [-10, 5],
            "footpoint": {"file": name, "bounds": [-16, 16]}}]]},
            {"blendMode": "add", "pattern": "untouched/{frame}.png"}]}}}}, "source": name}
    path.write_text(json.dumps(document, indent=2) + "\n")
    before = path.read_bytes()
    output = tmp_path / "proposal"
    result = propose_bindings(plan, candidates, bindings_root, output)
    assert result["candidate_aliases"] == 1
    assert result["candidate_bytes"] == 6
    assert path.read_bytes() == before
    changed = json.loads((output / "bindings/sample/bindings.json").read_text())
    expected = json.loads(before)
    expected["resources"]["logical-resource"] = canonical
    part = expected["projectileStorage"]["sample"]["phases"]["impact"]["layers"][0]["parts"][0][0]
    part["file"] = canonical
    part["footpoint"]["file"] = canonical
    assert changed == expected
    assert "a/game/data/sample/bindings.json" in (output / "public-bindings.patch").read_text()
    # A proposal alone never removes the old file from a staged selection.
    assert len(plan["files"]) == 3


def finalization_fixture(tmp_path):
    archive, inventory = bundle(tmp_path)
    base = tmp_path / "base"
    stage(archive, base, build_plan(archive, inventory, None))
    data = tmp_path / "data"
    (data / "sample").mkdir(parents=True)
    media_after = {"surfaceFrames": {"archive": {"file": "game/assets/packed/spell.zip",
                                                 "memberPattern": "{frame:04}.bin.gz"},
                                      "frameIndices": [0, 3], "positionScale": .5}}
    environment_after = {"path": "packed/lever.png", "rect": [0, 0, 2, 2], "pivot": [1, 2]}
    (data / "sample/bindings.json").write_text(json.dumps({"projectileStorage": {
        "tiny": {"phases": {"impact": media_after}}}}))
    (data / "assets.json").write_text(json.dumps({"resources": {"lever": environment_after}}))
    packs = []
    for kind, name, replaced, updates in (
        ("packed_media", "spell.zip", "first.png", {"sample/bindings.json": {"tiny": {
            "impact": {"before": {}, "after": media_after}}}}),
        ("packed_environment", "lever.png", "second.png", {"assets.json": [
            {"section": "resources", "key": "lever", "before": {}, "after": environment_after}]}),
    ):
        folder = tmp_path / kind
        target = folder / "game/assets/packed" / name
        target.parent.mkdir(parents=True)
        target.write_bytes(b"new packed pixels or packet members")
        manifest = folder / "packed.json"
        manifest.write_text(json.dumps({"version": 1, "kind": kind,
            "files": [{"path": "game/assets/packed/" + name, "bytes": target.stat().st_size}],
            "replaced_inputs": ["game/assets/tiny/" + replaced], "binding_updates": updates}))
        packs.append(manifest)
    return base, data, packs


def test_finish_builds_clean_manifest_reusing_base_ids_and_preserving_all_inputs(tmp_path):
    base, data, packs = finalization_fixture(tmp_path)
    before = json.loads((base / "art-manifest.json").read_text())
    output = tmp_path / "final"
    result = finish_release(base, packs, data, output, code_release="matching-code")
    assert result["files"] == 3 and result["replaced_files"] == 2
    manifest = json.loads((output / "art-manifest.json").read_text())
    assert manifest["code_release"] == "matching-code"
    source_companion = next(row for row in before["files"] if row["path"].endswith("xyz.bin.gz"))
    assert source_companion in manifest["files"]
    for row in manifest["files"]:
        assert (output / row["path"]).stat().st_size == row["bytes"]
        assert hashlib.sha256((output / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    assert not (output / "game/assets/tiny/first.png").exists()
    assert not (output / "game/assets/tiny/second.png").exists()
    assert not (output / "game/data").exists()
    assert (base / "game/assets/tiny/first.png").read_bytes() == b"pixels"
    assert (base / "game/assets/tiny/second.png").read_bytes() == b"pixels"
    assert all(path.exists() for path in packs)
    kept = tmp_path / "retained"
    result = finish_release(base, packs, data, kept,
                            retain_sources=("game/assets/tiny/first.png",))
    assert result["replaced_files"] == 1 and result["files"] == 4
    assert (kept / "game/assets/tiny/first.png").read_bytes() == b"pixels"


def test_finish_rejects_unapplied_or_modified_binding_before_writing(tmp_path):
    base, data, packs = finalization_fixture(tmp_path)
    binding = data / "sample/bindings.json"
    doc = json.loads(binding.read_text())
    doc["projectileStorage"]["tiny"]["phases"]["impact"]["surfaceFrames"]["positionScale"] = 2
    binding.write_text(json.dumps(doc))
    output = tmp_path / "final"
    with pytest.raises(ValueError, match="Packing binding not applied"):
        finish_release(base, packs, data, output)
    assert not output.exists()
