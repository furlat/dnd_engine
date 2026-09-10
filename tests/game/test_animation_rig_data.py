"""Explicit local rig bindings preserve source bytes and reject unusable data."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from game.animation_data import DATA_ROOT, load_animation_data


BINDING = DATA_ROOT.parent / "rigs/goblin01.json"
RIG_ID = "smallscale.goblin01"


def test_root_binding_reuses_imported_metadata_without_fixed_rig_dependency() -> None:
    data = load_animation_data()
    assert set(data.rigs) == {data.root_rig}
    root = data.rigs[data.root_rig]
    assert (root.cell_width, root.cell_height, root.origin_y_from_ground) == (
        data.rig.CELL_W, data.rig.CELL_H, data.rig.RIG_ORIGIN_Y_FROM_GROUND,
    )
    assert root.facing_rows == data.rig.FACING_ROW
    assert root.slot_order == data.rig.SLOT_RENDER_ORDER
    assert root.slot_categories == data.rig.SLOT_CATEGORIES
    for name, clip in root.clips.items():
        assert (clip.source_clip, clip.frames, clip.fps) == (name, data.rig.SHEET_COLS, data.rig.ANIM_FPS)
        for category, url in clip.sheets.items():
            assert url == f"/spritesheets/{category}/{name}.png"
            assert url in data.resources


def test_explicit_goblin_binding_preserves_original_sheets_and_semantic_mapping() -> None:
    data = load_animation_data(rig_files=(BINDING,))
    document = json.loads(BINDING.read_text())
    rig = data.rigs[RIG_ID]
    assert rig.model_dump(mode="json") == document["rig"]
    assert {name: clip.source_clip for name, clip in rig.clips.items()} == {
        "Idle": "Idle", "TakeDamage": "TakeDamage 1", "Die": "Die 1",
        "Run": "Run", "Rolling": "Roll 1",
        "Attack1": "Attack 1", "Attack2": "Attack 2",
    }
    assert (rig.cell_width, rig.cell_height, rig.origin_y_from_ground) == (128, 128, 41)
    assert rig.slot_order == ("shadow", "body")
    assert rig.slot_categories == {"body": ("Goblin01",), "shadow": ("Goblin01Shadow",)}
    copied = document["provenance"]["files"]
    for url, record in copied.items():
        path = data.resources[url]
        assert path.is_relative_to((DATA_ROOT.parent.parent / "assets/rigs").resolve())
        payload = path.read_bytes()
        assert len(payload) == record["bytes"]
        assert hashlib.sha256(payload).hexdigest() == record["sha256"]
    with pytest.raises(TypeError):
        data.rigs["unexpected"] = rig
    with pytest.raises(TypeError):
        rig.clips["unexpected"] = rig.clips["Idle"]
    with pytest.raises(TypeError):
        rig.clips["Idle"].sheets["unexpected"] = "/unexpected.png"


@pytest.mark.parametrize("case,error", [
    ("repeated-file", "duplicate body rig identity"),
    ("root-identity", "duplicate body rig identity"),
    ("duplicate-row", "eight distinct facing rows"),
    ("missing-row", "eight distinct facing rows"),
    ("unknown-category", "declared rig categories"),
    ("unbound-sheet", "clip resources and local bindings differ"),
    ("missing-file", "missing local animation resource"),
    ("outside-assets", "escapes local asset directory"),
    ("relative-escape", "invalid local animation resource path"),
    ("different-columns", "sheet dimensions differ"),
    ("zero-fps", "greater than 0"),
    ("zero-frames", "greater than or equal to 1"),
    ("duplicate-json-key", "duplicate JSON key"),
])
def test_unusable_additional_rig_rejected_before_playback(tmp_path: Path, case: str, error: str) -> None:
    document = json.loads(BINDING.read_text())
    rig = document["rig"]
    first = next(iter(document["resources"]))
    if case == "root-identity":
        document["rig_id"] = "neuroclient.modular"
    elif case == "duplicate-row":
        rig["facing_rows"]["E"] = rig["facing_rows"]["W"]
    elif case == "missing-row":
        del rig["facing_rows"]["N"]
    elif case == "unknown-category":
        rig["clips"]["Idle"]["sheets"]["invented"] = first
    elif case == "unbound-sheet":
        rig["clips"]["Idle"]["sheets"]["Goblin01"] = "/rigs/unbound.png"
    elif case == "missing-file":
        document["resources"][first] = "game/assets/rigs/goblin01/missing.png"
    elif case == "outside-assets":
        document["resources"][first] = "game/assets/neuroclient/spritesheets/NakedBody/Idle.png"
    elif case == "relative-escape":
        document["resources"][first] = "../outside.png"
    elif case == "different-columns":
        rig["clips"]["Idle"]["frames"] = 14
    elif case == "zero-fps":
        rig["clips"]["Idle"]["fps"] = 0
    elif case == "zero-frames":
        rig["clips"]["Idle"]["frames"] = 0
    path = tmp_path / "rig.json"
    source = json.dumps(document)
    if case == "duplicate-json-key":
        source = source.replace('"rig_id":', '"rig_id":"duplicate", "rig_id":', 1)
    path.write_text(source)
    with pytest.raises(ValueError, match=error):
        load_animation_data(rig_files=(path, path) if case == "repeated-file" else (path,))


def test_archive_provenance_is_not_a_runtime_readiness_requirement(tmp_path: Path) -> None:
    document = json.loads(BINDING.read_text())
    document["provenance"]["archive"]["name"] = "/absent/source/archive.zip"
    for record in document["provenance"]["files"].values():
        record["archive_member"] = "/absent/source/member.png"
    path = tmp_path / "rig.json"
    path.write_text(json.dumps(document))
    assert RIG_ID in load_animation_data(rig_files=(path,)).rigs


@pytest.fixture
def small_archive(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """Two real sheets exercise the CLI without the external purchased ZIP."""
    document = json.loads(BINDING.read_text())
    document["rig"]["clips"] = {"Idle": document["rig"]["clips"]["Idle"]}
    urls = set(document["rig"]["clips"]["Idle"]["sheets"].values())
    resources = {url: path for url, path in document["resources"].items() if url in urls}
    document["resources"] = resources
    files = {url: source for url, source in document["provenance"]["files"].items() if url in urls}
    document["provenance"]["files"] = files
    archive = tmp_path / "two-sheets.zip"
    repository = DATA_ROOT.parents[2]
    with zipfile.ZipFile(archive, "w") as package:
        for url, source in files.items():
            package.writestr(source["archive_member"], (repository / resources[url]).read_bytes())
    document["provenance"]["archive"] = {
        "name": archive.name, "bytes": archive.stat().st_size,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }
    binding = tmp_path / "two-sheets.json"
    binding.write_text(json.dumps(document))
    return archive, binding, resources


def run_import(archive: Path, binding: Path, output: Path, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(DATA_ROOT.parents[2] / "devtools/import_fixed_rig.py"),
               "--archive", str(archive), "--binding", str(binding), "--output-root", str(output)]
    return subprocess.run(command + (["--check"] if check else []), capture_output=True, text=True, check=False)


def test_offline_import_copies_exact_members_and_check_detects_changed_output(
        tmp_path: Path, small_archive: tuple[Path, Path, dict[str, str]]) -> None:
    archive, binding, resources = small_archive
    output = tmp_path / "result"
    imported = run_import(archive, binding, output)
    assert imported.returncode == 0, imported.stderr
    for relative in resources.values():
        assert (output / relative).read_bytes() == (DATA_ROOT.parents[2] / relative).read_bytes()
    assert run_import(archive, binding, output, check=True).returncode == 0
    changed = output / next(iter(resources.values()))
    changed.write_bytes(b"changed")
    checked = run_import(archive, binding, output, check=True)
    assert checked.returncode != 0
    assert "differs from original source" in checked.stderr
    assert changed.read_bytes() == b"changed"


@pytest.mark.parametrize("collision", ["destination", "parent"])
def test_offline_import_rejects_later_collision_without_overwriting_earlier_file(
        tmp_path: Path, small_archive: tuple[Path, Path, dict[str, str]], collision: str) -> None:
    archive, binding, resources = small_archive
    output = tmp_path / "result"
    first, second = (output / relative for relative in resources.values())
    first.parent.mkdir(parents=True)
    first.write_bytes(b"retain this previous file")
    if collision == "destination":
        second.mkdir(parents=True)
    else:
        second.parent.write_bytes(b"parent is a file")
    rejected = run_import(archive, binding, output)
    assert rejected.returncode != 0
    assert "rig destination" in rejected.stderr
    assert first.read_bytes() == b"retain this previous file"
