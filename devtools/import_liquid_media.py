"""Package selected liquid pixels and aligned footpoints; author no gameplay."""

import argparse
import json
from math import isclose
from pathlib import Path
import shutil

from game.animation_types import Facing8
from game.projection import project_world


ROOT = Path(__file__).resolve().parents[1]
CAMERA_ROWS: tuple[Facing8, ...] = ("E", "S", "W", "N")
DIRECTIONS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")


def _read(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def _camera_views(document: dict) -> dict[Facing8, dict]:
    """Match numerical projection bases, independent of the exporter's labels."""
    result = {}
    for quadrant, facing in enumerate(CAMERA_ROWS):
        origin = project_world((0, 0), quadrant=quadrant)
        basis = {axis: tuple((value - origin[i]) / 2 for i, value in enumerate(
            project_world(point, quadrant=quadrant))) for axis, point in (("X", (1, 0)), ("Z", (0, 1)))}
        matches = [view for view in document["views"].values() if all(
            isclose(view["groundBasis"][axis][i], coordinate, abs_tol=1e-6)
            for axis, coordinates in basis.items() for i, coordinate in enumerate(coordinates))]
        if len(matches) != 1:
            raise ValueError(f"Liquid export needs one view for camera quadrant {quadrant}")
        result[facing] = matches[0]
    return result


def import_bundle(source: Path, *, material: str, variant: int,
                  palette: tuple[int, ...], repo: Path = ROOT) -> tuple[str, ...]:
    """Copy explicit split-camera delivery; preserve other assets and recipes."""
    document = json.loads((source / "media.json").read_text())
    views = _camera_views(document)
    first, last = document["loop"]
    if last != document["frames"]:
        raise ValueError("Liquid loop must finish at the delivered final observation")
    for view in views.values():
        streams = view["streams"]
        if streams["air"]["rects"] != streams["position"]["rects"]:
            raise ValueError("Air color and footpoints must have identical packing")
        if any(len(streams[name]["rects"]) != last for name in ("air", "floor", "position")):
            raise ValueError("Liquid streams must retain every observation")
    folder = repo / "game/data/liquid_media"
    media = Path("game/assets/liquid_media") / f"{material}-s{variant}"
    bindings = _read(folder / "bindings.json", {"resources": {}, "projectileStorage": {}})
    assets = {row["assetId"]: row for row in _read(folder / "projectile-assets.json", [])}
    storage = bindings.setdefault("projectileStorage", {})
    copied: set[Path] = set()

    def copy(relative: str) -> str:
        destination = media / relative
        if destination not in copied:
            (repo / destination).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, repo / destination)
            copied.add(destination)
        return destination.as_posix()

    def parts(view: dict, channel: str, begin: int, end: int) -> list[list[dict]]:
        stream = view["streams"][channel]
        result = []
        for frame in range(begin, end):
            address = stream["rects"][frame]
            if address is None:
                result.append([])
                continue
            row = {"file": copy(stream["pages"][address["page"]]), "rect": address["source"],
                "offset": [address["offset"][axis] + document["pivot"][axis] for axis in range(2)]}
            if channel == "air":
                row["footpoint"] = {"file": copy(view["streams"]["position"]["pages"][address["page"]]),
                    "bounds": document["worldBounds"]}
            result.append([row])
        return result

    imported = []
    for channel in ("floor", "air"):
        for phase, begin, end in (("application", 0, first), ("sustain", first, last)):
            identity = f"liquid.{material}.s{variant}.{channel}.{phase}"
            count = end - begin
            assets[identity] = {
                "assetId": identity, "displayName": identity, "kind": "projectile",
                "sheet": f"/liquid-media/{material}/s{variant}/{channel}/{phase}.png",
                "frame": {"width": 384, "height": 384, "rows": 8, "cols": count},
                "fps": document["fps"], "rowOrder": list(DIRECTIONS),
                "phases": {"impact": {"start": 0, "frames": count,
                    "fps": document["fps"], "loop": phase == "sustain"}},
                "anchor": {"x": document["pivot"][0] / 384, "y": document["pivot"][1] / 384},
                "defaultScale": 1, "palettePreview": {"colors": list(palette)},
                "source": {"package": source.name, "asset": f"{material}-s{variant}",
                    "notes": f"Unchanged source observations [{begin},{end}); four numerical camera bases; raw XY footpoints."},
            }
            storage[identity] = {"phases": {"impact": {"layers": [{"blendMode": "normal",
                "partsByFacing": {facing: parts(view, channel, begin, end) for facing, view in views.items()}}]}}}
            imported.append(identity)
    folder.mkdir(parents=True, exist_ok=True)
    for name, value in (("bindings.json", bindings), ("projectile-assets.json", list(assets.values()))):
        (folder / name).write_text(json.dumps(value, separators=(",", ":")) + "\n")
    return tuple(imported)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--material", required=True)
    parser.add_argument("--variant", type=int, required=True)
    parser.add_argument("--palette", nargs="+", type=lambda color: int(color, 16), required=True)
    args = parser.parse_args()
    imported = import_bundle(args.source, material=args.material, variant=args.variant,
                             palette=tuple(args.palette), repo=args.repo)
    print(f"Imported {len(imported)} liquid media views; no behavior documents changed.")


if __name__ == "__main__":
    main()
