"""Select source-time samples and repack support atlases into a new offline stage."""

import json
from pathlib import Path

from PIL import Image

from devtools.art import write_json
from devtools.pack_environment import page_cells


def _within(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Support media path leaves its root: {relative}")
    return path


def _repack_layer(source: Path, output: Path, layer: dict, indices: list[int],
                  base: str, page_size: int) -> dict:
    selected = [layer["frames"][index] for index in indices]
    cells = [{"source": layer["pages"][frame["page"]], "source_rect": frame["source"],
              "frame": index} for index, frame in enumerate(selected) if frame is not None]
    frames: list[dict | None] = [None] * len(indices)
    pages = []
    if not cells:
        return {**layer, "pages": pages, "frames": frames}
    cell = (max(row["source_rect"][2] for row in cells),
            max(row["source_rect"][3] for row in cells))
    jobs, _ = page_cells(cells, cell, base, page_size)
    source_path, source_image = None, None
    try:
        for page_index, job in enumerate(jobs):
            target = _within(output, job["output"])
            target.parent.mkdir(parents=True, exist_ok=True)
            with Image.new("RGBA", tuple(job["canvas"])) as page:
                for entry in job["cells"]:
                    if entry["source"] != source_path:
                        if source_image is not None:
                            source_image.close()
                        source_path = entry["source"]
                        with Image.open(_within(source, source_path)) as image:
                            source_image = image.convert("RGBA")
                    sx, sy, width, height = entry["source_rect"]
                    x, y = entry["rect"][:2]
                    if (source_image is None or min(sx, sy) < 0 or min(width, height) <= 0
                            or sx + width > source_image.width or sy + height > source_image.height):
                        raise ValueError(f"Invalid source crop: {entry['source_rect']}")
                    with source_image.crop((sx, sy, sx + width, sy + height)) as pixels:
                        page.paste(pixels, (x, y))
                    frames[entry["frame"]] = {**selected[entry["frame"]], "page": page_index,
                                              "source": [x, y, width, height]}
                page.save(target)
            pages.append(job["output"])
    finally:
        if source_image is not None:
            source_image.close()
    return {**layer, "pages": pages, "frames": frames}


def repack_group(source: Path, group: str, output: Path, *, fps: int = 32,
                 page_size: int = 2048) -> dict:
    """Write selected pages and a compatible group manifest; never alter originals.

    Output sample k selects floor(k * source_fps / fps), without interpolation.
    Phase duration must be exactly representable at the requested frame rate.
    Crops, offsets, camera registration, palette and RGBA values stay unchanged.
    Isolated casting hands retain their separate native rig clock and source.
    """
    if output.exists() or output.is_symlink():
        raise ValueError("Support media output directory must be new")
    source, output = source.resolve(), output.resolve()
    if output.is_relative_to(source):
        raise ValueError("Support media output must be outside its source")
    manifest_path = f"groups/{group}/manifest.json"
    manifest = json.loads(_within(source, manifest_path).read_text())
    if not manifest["readiness"]["fourNativeCameras"]:
        raise ValueError(f"{group}: native camera delivery is incomplete")
    selections = {}
    for name, phase in manifest["phases"].items():
        source_fps, count = phase["fps"], phase["frameCount"]
        if source_fps <= 0 or fps <= 0 or fps > source_fps or count <= 0:
            raise ValueError(f"{name}: invalid source or selected frame rate/count")
        output_count, remainder = divmod(count * fps, source_fps)
        if remainder:
            raise ValueError(f"{name}: phase duration is not exact at {fps} FPS")
        if phase["composition"] != "billboard":
            raise ValueError(f"{name}: support repacking requires billboard media")
        if set(phase["cameras"]) != {"0", "1", "2", "3"}:
            raise ValueError(f"{name}: all four native camera banks are required")
        for camera in phase["cameras"].values():
            if set(camera["layers"]) != {"back", "front"}:
                raise ValueError(f"{name}: back and front layers are required")
            if any(len(layer["frames"]) != count for layer in camera["layers"].values()):
                raise ValueError(f"{name}: incomplete frame sequence")
        selections[name] = [index * source_fps // fps for index in range(output_count)]

    output.mkdir(parents=True)
    for name, phase in manifest["phases"].items():
        indices = selections[name]
        phase["sourceSampling"] = {"fps": phase["fps"], "frameCount": phase["frameCount"],
                                   "frameIndices": indices}
        phase["fps"], phase["frameCount"] = fps, len(indices)
        if "frames" in phase:
            phase["frames"] = len(indices)
        for quadrant, camera in phase["cameras"].items():
            for side, layer in camera["layers"].items():
                camera["layers"][side] = _repack_layer(
                    source, output, layer, indices, f"media/{name}/q{quadrant}/{side}", page_size)
    manifest["assetRoot"] = str(output)
    write_json(_within(output, manifest_path), manifest)
    return manifest
