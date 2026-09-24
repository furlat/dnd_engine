"""Offline source-time selection preserves four-camera support pixels and registration."""

from fractions import Fraction
import json
from pathlib import Path

from PIL import Image
import pytest

from devtools.repack_support_media import repack_group


def delivery(tmp_path: Path, count: int = 288, *, loop: bool = False) -> tuple[Path, dict]:
    source = tmp_path / "original"
    source.mkdir()
    cameras = {}
    for quadrant in range(4):
        layers = {}
        for side_index, side in enumerate(("back", "front")):
            pages = [f"native/q{quadrant}/{side}-{page}.png" for page in range(3)]
            frames: list[dict | None] = [None] * count
            for page_index, name in enumerate(pages):
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with Image.new("RGBA", (36, 3)) as page:
                    for index in range(1, 18):
                        frame_page = 2 if index == 17 else index // 9
                        if frame_page != page_index or (quadrant == 3 and side == "front"):
                            continue
                        x, width, height = (index % 9) * 4, 2 + index % 2, 2 + index % 2
                        for sy in range(height):
                            for sx in range(width):
                                page.putpixel((x + sx, sy),
                                              (quadrant * 40 + side_index, index, sx + 20,
                                               0 if sx == sy == 0 else 127 + sy))
                        frames[index] = {"page": page_index, "source": [x, 0, width, height],
                                         "offset": [index % 3, 5 - index % 2]}
                    page.save(path)
            layers[side] = {"pages": pages, "frames": frames}
        cameras[str(quadrant)] = {"position": [quadrant, 10.5, -quadrant], "layers": layers}
    phase = {"id": "support", "canvas": [9, 10], "pivot": [4.5, 7.75], "fps": 144,
             "frameCount": count, "frames": count, "palette": ["112233", "ffeedd"],
             "composition": "billboard", "worldBasis": "fixed_world", "loop": loop,
             "sourcePixelScale": .5, "cameras": cameras}
    manifest = {"schema": "dnd.privateSupportDelivery", "version": 1, "group": "tiny",
                "readiness": {"fourNativeCameras": True}, "assetRoot": str(source),
                "phases": {"support": phase}, "handsManifest": "hands.json",
                "ordinaryRemoval": {"phaseAdvance": True, "fadeMs": 450}}
    path = source / "groups/tiny/manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest))
    (source / "hands.json").write_text('{"fps":12}')
    return source, manifest


def crop(root: Path, layer: dict, frame: dict) -> bytes:
    x, y, width, height = frame["source"]
    with Image.open(root / layer["pages"][frame["page"]]) as page:
        with page.crop((x, y, x + width, y + height)) as pixels:
            return pixels.tobytes()


@pytest.mark.parametrize(("native_count", "output_count", "loop"),
                         [(288, 64, False), (216, 48, True), (864, 192, True), (432, 96, False)])
def test_32fps_pages_preserve_selected_pixels_registration_and_exact_duration(
        tmp_path, native_count, output_count, loop):
    source, original = delivery(tmp_path, native_count, loop=loop)
    originals = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    output = tmp_path / "selected"
    converted = repack_group(source, "tiny", output, page_size=8)
    assert converted == json.loads((output / "groups/tiny/manifest.json").read_text())
    old, new = original["phases"]["support"], converted["phases"]["support"]
    assert new["fps"] == 32 and new["frameCount"] == new["frames"] == output_count
    assert Fraction(native_count, 144) == Fraction(output_count, 32)
    indices = new["sourceSampling"]["frameIndices"]
    assert indices[:6] == [0, 4, 9, 13, 18, 22]
    assert indices[32] == 144
    assert new["sourceSampling"]["fps"] == 144
    assert new["sourceSampling"]["frameCount"] == native_count
    for key in ("canvas", "pivot", "palette", "composition", "worldBasis", "loop", "sourcePixelScale"):
        assert new[key] == old[key]
    assert converted["ordinaryRemoval"] == original["ordinaryRemoval"]
    used = set()
    for quadrant in ("0", "1", "2", "3"):
        assert new["cameras"][quadrant]["position"] == old["cameras"][quadrant]["position"]
        for side in ("back", "front"):
            old_layer, new_layer = old["cameras"][quadrant]["layers"][side], new["cameras"][quadrant]["layers"][side]
            assert len(new_layer["frames"]) == output_count
            assert new_layer["frames"][0] is None
            for native_index, new_frame in zip(indices, new_layer["frames"], strict=True):
                old_frame = old_layer["frames"][native_index]
                if old_frame is None:
                    assert new_frame is None
                    continue
                assert new_frame["offset"] == old_frame["offset"]
                assert new_frame["source"][2:] == old_frame["source"][2:]
                assert crop(output, new_layer, new_frame) == crop(source, old_layer, old_frame)
            used.update(new_layer["pages"])
    assert {path.relative_to(output).as_posix() for path in output.rglob("*.png")} == used
    for relative in used:
        with Image.open(output / relative) as page:
            # Every native frame has a distinct green channel, including hidden RGB.
            assert page.mode == "RGBA"
            assert set(page.tobytes()[1::4]) <= {0, 4, 9, 13}
    assert converted["phases"]["support"]["cameras"]["3"]["layers"]["front"]["pages"] == []
    assert not (output / "native").exists() and not (output / "hands.json").exists()
    assert all((source / relative).read_bytes() == data for relative, data in originals.items())


@pytest.mark.parametrize("problem", ["fractional_duration", "missing_camera", "existing_output", "inside_source"])
def test_rejects_inexact_or_incomplete_delivery_and_preserves_existing_files(tmp_path, problem):
    source, manifest = delivery(tmp_path)
    output = tmp_path / "selected"
    if problem == "fractional_duration":
        manifest["phases"]["support"]["frameCount"] = 287
    elif problem == "missing_camera":
        del manifest["phases"]["support"]["cameras"]["3"]
    elif problem == "existing_output":
        output.mkdir()
        (output / "original.txt").write_text("keep")
    else:
        output = source / "selected"
    (source / "groups/tiny/manifest.json").write_text(json.dumps(manifest))
    originals = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    with pytest.raises(ValueError):
        repack_group(source, "tiny", output)
    assert all((source / relative).read_bytes() == data for relative, data in originals.items())
    if problem == "existing_output":
        assert (output / "original.txt").read_text() == "keep"
    else:
        assert not output.exists()
