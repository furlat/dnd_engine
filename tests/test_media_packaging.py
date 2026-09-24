"""Offline packs preserve logical samples, registrations and original payloads."""

import copy
import gzip
import json
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from PIL import Image
import pytest

from devtools.art import export_art
from devtools.pack_media import build_media, plan_media


def setup(tmp_path: Path):
    source, archive, data = tmp_path / "source", tmp_path / "archive", tmp_path / "data"
    folder = source / "game/assets/tiny"
    folder.mkdir(parents=True)
    for facing in ("E", "W"):
        for frame in range(4):
            image = Image.new("RGBA", (2, 2), (frame * 40, 70, 90, 128))
            image.putpixel((0, 0), (12, 34, 56, 0))
            image.save(folder / f"color-{facing}-{frame}.png")
        for frame in (0, 6):
            (folder / f"xyz-{facing}-{frame}.bin.gz").write_bytes(gzip.compress(
                f"unchanged paired packet {facing}/{frame}".encode(), mtime=0))
    export_art(source, archive)
    manifest = json.loads((archive / "art-manifest.json").read_text())
    selected = {"files": [r for r in manifest["files"] if not r["path"].endswith("color-E-2.png")]}
    originals = {r["path"]: (archive / r["path"]).read_bytes() for r in manifest["files"]}
    pattern = "game/assets/tiny/xyz-{direction}-{frame}.bin.gz"
    sources = {facing: [{"pattern": "game/assets/tiny/xyz-E-{frame}.bin.gz", "blendMode": "normal",
                        "pivot": pivot}] for facing, pivot in (("E", [1.25, 2.5]), ("W", [4.75, 6.5]))}
    bindings = {"resources": {}, "projectileStorage": {
        "color": {"phases": {"impact": {"layers": [{"pattern": "game/assets/tiny/color-{direction}-{frame}.png",
                                                      "blendMode": "add", "gain": .5}]}}},
        "combined": {"phases": {"impact": {"surfaceFrames": {"pattern": pattern,
            "frameIndices": [0, 6, 6], "bounds": [-16, 16], "verticalScale": 1.25,
            "positionScale": .5, "blendModes": ["normal", "add"]}}}},
        "components": {"phases": {"impact": {"surfaceFrames": {"componentsByFacing": sources,
            "frameIndices": [0, 6, 6], "bounds": [-8, 8], "verticalScale": 2}}}},
    }}
    (data / "sample").mkdir(parents=True)
    (data / "sample/bindings.json").write_text(json.dumps(bindings, indent=2) + "\n")
    assets = [{"assetId": name, "frame": {"width": 2, "height": 2}, "rowOrder": ["E", "W"],
               "phases": {"impact": {"frames": count, "fps": 144, "loop": False}},
               "anchor": {"x": .3, "y": .6}}
              for name, count in (("color", 4), ("combined", 3), ("components", 3))]
    (data / "sample/projectile-assets.json").write_text(json.dumps(assets))
    phases = [{"asset": name, "phase": "impact", "storage": kind} for name, kind in (
        ("color", "loose_color_frames"), ("combined", "loose_combined_packets"),
        ("components", "loose_component_packets"))]
    return archive, data, selected, phases, bindings, originals


def test_metadata_plan_keeps_clocks_sparse_indices_and_shared_bank_registration(tmp_path):
    archive, data, selected, phases, bindings, _ = setup(tmp_path)
    # Planning never needs source payloads to be present.
    for path in (archive / "game/assets/tiny").iterdir():
        path.unlink()
    plan = plan_media(selected, phases, data, page_size=4)
    updates = plan["binding_updates"]["sample/bindings.json"]
    color = updates["color"]["impact"]["after"]["layers"][0]
    assert [page["firstFrame"] for page in color["pages"]["E"]] == [0, 3]
    assert color["gain"] == .5 and color["blendMode"] == "add"
    for name in ("combined", "components"):
        original = bindings["projectileStorage"][name]["phases"]["impact"]["surfaceFrames"]
        packed = updates[name]["impact"]["after"]["surfaceFrames"]
        assert packed["frameIndices"] == [0, 6, 6]
        assert packed["bounds"] == original["bounds"]
        assert packed["verticalScale"] == original["verticalScale"]
    parts = updates["components"]["impact"]["after"]["surfaceFrames"]["componentsByFacing"]
    assert parts["E"][0]["pivot"] == [1.25, 2.5]
    assert parts["W"][0]["pivot"] == [4.75, 6.5]
    assert parts["E"][0]["archive"] == parts["W"][0]["archive"]
    assert plan["summary"]["shared_archive_references"] == 1


def test_build_preserves_png_rgba_and_zip_member_bytes_with_current_binding_patch(tmp_path):
    archive, data, selected, phases, bindings, originals = setup(tmp_path)
    before = (data / "sample/bindings.json").read_bytes()
    asset_before = (data / "sample/projectile-assets.json").read_bytes()
    plan = plan_media(selected, phases, data, page_size=4)
    output = tmp_path / "packed"
    result = build_media(plan, archive, data, output)
    assert (data / "sample/bindings.json").read_bytes() == before
    assert (data / "sample/projectile-assets.json").read_bytes() == asset_before
    for job in plan["jobs"]:
        if job["kind"] == "xyz_archive":
            with ZipFile(output / job["output"]) as bundle:
                assert all(info.compress_type == ZIP_STORED for info in bundle.infolist())
                for member in job["members"]:
                    assert bundle.read(member["member"]) == originals[member["source"]]
        else:
            with Image.open(output / job["output"]) as page:
                for frame in job["frames"]:
                    x, y, width, height = frame["rect"]
                    with Image.open(archive / frame["source"]) as source:
                        assert page.crop((x, y, x + width, y + height)).tobytes() == source.tobytes()
    assert result["encoded_bytes"] == sum((output / row["path"]).stat().st_size for row in result["files"])
    assert all((archive / name).read_bytes() == payload for name, payload in originals.items())
    expected = copy.deepcopy(bindings)
    for name, phases in plan["binding_updates"]["sample/bindings.json"].items():
        for phase, change in phases.items():
            expected["projectileStorage"][name]["phases"][phase] = change["after"]
    assert json.loads((output / "bindings/sample/bindings.json").read_text()) == expected


def test_build_rejects_changed_bindings_or_missing_input_before_writing_output(tmp_path):
    archive, data, selected, phases, bindings, _ = setup(tmp_path)
    plan = plan_media(selected, phases, data, page_size=4)
    path = data / "sample/bindings.json"
    bindings["projectileStorage"]["color"]["phases"]["impact"]["layers"][0]["gain"] = .75
    path.write_text(json.dumps(bindings))
    output = tmp_path / "packed"
    with pytest.raises(ValueError, match="changed since planning"):
        build_media(plan, archive, data, output)
    assert not output.exists()
    bindings["projectileStorage"]["color"]["phases"]["impact"]["layers"][0]["gain"] = .5
    path.write_text(json.dumps(bindings))
    (archive / plan["inputs"][0]["path"]).unlink()
    with pytest.raises(ValueError, match="Missing"):
        build_media(plan, archive, data, output)
    assert not output.exists()
