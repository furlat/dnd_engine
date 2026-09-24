"""Offline environment pages preserve observable cells and authored registration."""

import json
from pathlib import Path

from PIL import Image
import pytest

from devtools.art import export_art
from devtools.pack_environment import build_environment, plan_environment


def setup(tmp_path: Path, *, shared_depth: bool = False):
    source, archive, data = tmp_path / "source", tmp_path / "archive", tmp_path / "data"
    folder = source / "game/assets/environment"
    (folder / "lever").mkdir(parents=True)
    for name, cell in (("color", 2), ("depth", 1), ("frame", 2)):
        with Image.new("RGBA", (3 * cell, 4 * cell)) as image:
            for y in range(image.height):
                for x in range(image.width):
                    image.putpixel((x, y), (x * 20, y * 20, 199, 0 if x == y else 127))
            image.save(folder / ("lever/depth.png" if name == "depth" and shared_depth else f"{name}.png"))
    for frame in range(3):
        with Image.new("RGBA", (2, 2), (10, 20, frame * 50, 0)) as image:
            image.save(folder / f"lever/{frame}.png")
    export_art(source, archive)
    selection = json.loads((archive / "art-manifest.json").read_text())
    bank = {"path": "environment/color.png", "cell": [2, 2], "frame_count": 3,
            "rows": ["e", "s", "w", "n"], "frame_path": "environment/frame.png",
            "ground_pivot": [1, 2], "sample_times_ms": [0, 37, 91], "scale": 1.007874,
            "state_change_frame": 2, "release_frame": 1,
            "pivots_by_pose": {"e": [.25, 1.75]},
            "actor_depth": {"path": "environment/depth.png", "cell": [1, 1],
                            "depth_range": [-4, 4], "pixels_per_unit_by_pose": {"e": 12.5}}}
    resources = {f"lever.{i}": {"path": f"environment/lever/{i}.png", "native_size": [2, 2],
                               "pivot": [.5, 1.5], "scale": 1.5} for i in range(3)}
    if shared_depth:
        bank["actor_depth"]["path"] = "environment/lever/depth.png"
        resources["lever.depth"] = {"path": "environment/lever/depth.png",
                                    "native_size": [3, 4], "pivot": [0, 0], "scale": 1}
    data.mkdir()
    (data / "environment_art.json").write_text(json.dumps({"banks": {"tiny": bank}}))
    (data / "assets.json").write_text(json.dumps({"resources": resources}))
    return archive, data, selection, bank, resources


def test_shared_depth_strip_stays_installed_for_the_unpacked_resource_consumer(tmp_path):
    archive, data, selection, _, _ = setup(tmp_path, shared_depth=True)
    # 3px pages fit the 2px body cell and 1px bank depth cell, while the
    # independent 3x4 resource keeps its existing strip sampler.
    plan = plan_environment(selection, archive, data, page_size=3)
    depth_path = "game/assets/environment/lever/depth.png"
    assert depth_path in {row["path"] for row in plan["inputs"]}
    assert depth_path in {row["path"] for row in plan["retained_resources"]}
    result = build_environment(plan, archive, data, tmp_path / "packed")
    assert depth_path not in result["replaced_inputs"]
    assert "game/assets/environment/color.png" in result["replaced_inputs"]
    assert "depth_frames_by_pose" in result["binding_updates"]["environment_art.json"][0]["after"]
    assert not any(row["key"] == "lever.depth" for row in result["binding_updates"]["assets.json"])


def test_all_poses_color_depth_and_static_cells_survive_lossless_pages(tmp_path):
    archive, data, selection, bank, resources = setup(tmp_path)
    originals = {r["path"]: (archive / r["path"]).read_bytes() for r in selection["files"]}
    before = {name: (data / name).read_bytes() for name in ("assets.json", "environment_art.json")}
    plan = plan_environment(selection, archive, data, page_size=4)
    output = tmp_path / "packed"
    result = build_environment(plan, archive, data, output)
    packed = result["binding_updates"]["environment_art.json"][0]["after"]
    assert all(len(packed["frames_by_pose"][pose]) == 3 for pose in bank["rows"])
    assert all(len(packed["depth_frames_by_pose"][pose]) == 3 for pose in bank["rows"])
    for field in ("cell", "rows", "frame_count", "scale", "ground_pivot", "pivots_by_pose",
                  "sample_times_ms", "state_change_frame", "release_frame"):
        assert packed[field] == bank[field]
    assert "path" not in packed and "frame_path" not in packed
    assert packed["actor_depth"] == {k: v for k, v in bank["actor_depth"].items() if k != "path"}
    for job in plan["jobs"]:
        with Image.open(output / job["output"]) as page:
            for cell in job["cells"]:
                sx, sy, sw, sh = cell["source_rect"]
                x, y, width, height = cell["rect"]
                with Image.open(archive / cell["source"]) as original:
                    expected = original.crop((sx, sy, sx + sw, sy + sh))
                    assert page.crop((x, y, x + width, y + height)).tobytes() == expected.tobytes()
    for change in result["binding_updates"]["assets.json"]:
        assert change["after"]["native_size"] == resources[change["key"]]["native_size"]
        assert change["after"]["pivot"] == [.5, 1.5] and change["after"]["scale"] == 1.5
    assert plan["summary"]["static_frame_cells"] == 4
    assert plan["summary"]["maximum_page_decoded_bytes"] <= 4 * 4 * 4
    assert all((archive / name).read_bytes() == payload for name, payload in originals.items())
    assert all((data / name).read_bytes() == payload for name, payload in before.items())


def test_environment_build_checks_current_binding_and_missing_input_before_writing(tmp_path):
    archive, data, selection, bank, _ = setup(tmp_path)
    plan = plan_environment(selection, archive, data, page_size=4)
    path = data / "environment_art.json"
    bank["state_change_frame"] = 1
    path.write_text(json.dumps({"banks": {"tiny": bank}}))
    output = tmp_path / "packed"
    with pytest.raises(ValueError, match="changed since planning"):
        build_environment(plan, archive, data, output)
    assert not output.exists()
    bank["state_change_frame"] = 2
    path.write_text(json.dumps({"banks": {"tiny": bank}}))
    (archive / plan["inputs"][0]["path"]).unlink()
    with pytest.raises(ValueError, match="Missing"):
        build_environment(plan, archive, data, output)
    assert not output.exists()
