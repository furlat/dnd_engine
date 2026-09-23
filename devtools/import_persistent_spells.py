"""Copy declared persistent-spell media; authored recipes remain independent."""

import argparse
import json
from math import isclose
from pathlib import Path
import shutil

from game.projection import project_world


ROOT = Path(__file__).resolve().parents[1]
DIRECTIONS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")
CAMERA_ROWS = ("E", "S", "W", "N")


def read_document(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def camera_rows(views: dict, *, source_scale: float = 1) -> dict:
    """Use numerical projection bases rather than camera naming conventions."""
    result = {}
    for quadrant, facing in enumerate(CAMERA_ROWS):
        origin = project_world((0, 0), quadrant=quadrant)
        basis = {axis: tuple((value - origin[i]) * source_scale for i, value in enumerate(
            project_world(point, quadrant=quadrant)))
            for axis, point in (("X", (1, 0)), ("Z", (0, 1)))}
        matches = [view for view in views.values() if all(
            isclose(view["groundBasis"][axis][i], coordinate, abs_tol=1e-6)
            for axis, coordinates in basis.items() for i, coordinate in enumerate(coordinates))]
        if len(matches) != 1:
            raise ValueError(f"Expected one declared source view for camera quadrant {quadrant}")
        result[facing] = matches[0]
    return result


def import_terrain(source: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    """Import only published four-view components and their explicit windows."""
    manifest = json.loads((source / "manifest.json").read_text())
    original = Path(manifest["originalPackage"])
    actor_data = json.loads((original / "actors.json").read_text())
    folder = repo / "game/data/persistent_spells"
    target_root = Path("game/assets/persistent_spells/terrain")
    bindings = read_document(folder / "bindings.json", {"resources": {}, "projectileStorage": {}})
    assets = {row["assetId"]: row for row in read_document(folder / "projectile-assets.json", [])}
    storage = bindings.setdefault("projectileStorage", {})
    copied = set()

    def copy(root: Path, relative: str) -> str:
        destination = target_root / relative
        if destination not in copied:
            (repo / destination).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / relative, repo / destination)
            copied.add(destination)
        return destination.as_posix()

    imported = []
    for name, component in manifest["components"].items():
        views = camera_rows(component["views"])
        reference = views["E"]
        # The terrain contract declares centered 384/256 canvases. Cropped
        # offsets are relative to this pivot, not the visible image bounds.
        width = height = 384 if name == "grease" else 256
        pivot = reference["pivot"]
        family = "grease" if name.startswith("grease") else "spike_growth"
        palette = [r * 65536 + g * 256 + b for r, g, b in actor_data[family]["palette"]]
        for phase, (begin, end) in component["phases"].items():
            identity = f"persistent.{name}.{phase}"
            count = end - begin
            assets[identity] = {
                "assetId": identity, "displayName": identity, "kind": "projectile",
                "sheet": f"/persistent-spells/{name}/{phase}.png",
                "frame": {"width": width, "height": height, "rows": 8, "cols": count},
                "fps": reference["fps"], "rowOrder": list(DIRECTIONS),
                "phases": {"impact": {"start": 0, "frames": count,
                    "fps": reference["fps"], "loop": phase == "hold"}},
                "anchor": {"x": pivot[0] / width, "y": pivot[1] / height},
                "defaultScale": .5, "palettePreview": {"colors": palette},
            }
            rows = {}
            for facing, view in views.items():
                rows[facing] = [[] if address is None else [{
                    "file": copy(source, view["pages"][address["page"]]),
                    "rect": address["source"],
                    "offset": [int(address["offset"][axis] + view["pivot"][axis]) for axis in range(2)],
                }] for address in view["rects"][begin:end]]
            storage[identity] = {"phases": {"impact": {"layers": [
                {"blendMode": "normal", "partsByFacing": rows}]}}}
            imported.append(identity)
    for family in actor_data:
        bindings["resources"][f"/persistent-spells/{family}/cast.png"] = copy(
            original, f"actors/{family}-hands.png")
    folder.mkdir(parents=True, exist_ok=True)
    for name, value in (("bindings.json", bindings), ("projectile-assets.json", list(assets.values()))):
        (folder / name).write_text(json.dumps(value, separators=(",", ":")) + "\n")
    return tuple(imported)


def import_protection(manifest_path: Path, *, name: str, repo: Path = ROOT) -> tuple[str, ...]:
    """Translate paired source lifecycle storage, preserving registration."""
    source = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    folder = repo / "game/data/persistent_spells"
    bindings = read_document(folder / "bindings.json", {"resources": {}, "projectileStorage": {}})
    assets = {row["assetId"]: row for row in read_document(folder / "projectile-assets.json", [])}
    views = {key: {**view, "groundBasis": {"X": view["camera"]["basisX"], "Z": view["camera"]["basisZ"]}}
             for key, view in manifest["views"].items()}
    source_scale = abs(next(iter(views.values()))["groundBasis"]["X"][0]) / 64
    views = camera_rows(views, source_scale=source_scale)
    pivot = manifest["pivot"]
    width, height = manifest["canvasSize"]
    palette = [int(value, 16) for value in manifest["palette"]]
    target_root = Path("game/assets/persistent_spells/protection")
    copied = set()
    imported = []
    for side in ("back", "front"):
        for phase, window in (("apply", manifest["apply"]), ("hold", manifest["hold"]),
                              ("clear_mask", (0, manifest["clear"]["frames"]))):
            begin, end = window
            identity = f"persistent.{name}.{side}.{phase}"
            rows = {}
            for facing, view in views.items():
                bank = (manifest["clear"]["mask"] if manifest["clear"].get("sharedAcrossCamerasAndLayers")
                        else view[side]["clearMask"]) if phase == "clear_mask" else view[side]
                frames = []
                for address in bank["frames"][begin:end]:
                    if address is None:
                        frames.append([])
                        continue
                    path = bank["pages"][address["page"]]
                    destination = target_root / path
                    if destination not in copied:
                        (repo / destination).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source / path, repo / destination)
                        copied.add(destination)
                    frames.append([{"file": destination.as_posix(), "rect": address["source"],
                                    "offset": address["offset"]}])
                rows[facing] = frames
            assets[identity] = {"assetId": identity, "displayName": identity, "kind": "projectile",
                "sheet": f"/persistent-spells/{name}/{side}/{phase}.png",
                "frame": {"width": width, "height": height, "rows": 8, "cols": end - begin},
                "fps": manifest["fps"], "rowOrder": list(DIRECTIONS),
                "phases": {"impact": {"start": 0, "frames": end - begin,
                    "fps": manifest["fps"], "loop": phase == "hold"}},
                "anchor": {"x": pivot[0] / width, "y": pivot[1] / height}, "defaultScale": .5,
                "palettePreview": {"colors": [0xFFFFFF] if phase == "clear_mask" else palette}}
            bindings["projectileStorage"][identity] = {"phases": {"impact": {"layers": [
                {"blendMode": "normal", "partsByFacing": rows}]}}}
            imported.append(identity)
    folder.mkdir(parents=True, exist_ok=True)
    for filename, value in (("bindings.json", bindings), ("projectile-assets.json", list(assets.values()))):
        (folder / filename).write_text(json.dumps(value, separators=(",", ":")) + "\n")
    return tuple(imported)


def import_shield_contacts(manifest_path: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    """Incoming direction selects an asset; numerical camera basis selects rows."""
    source = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    folder = repo / "game/data/persistent_spells"
    bindings = read_document(folder / "bindings.json", {"resources": {}, "projectileStorage": {}})
    assets = {row["assetId"]: row for row in read_document(folder / "projectile-assets.json", [])}
    views = {key: {**view, "groundBasis": {"X": view["camera"]["basisX"], "Z": view["camera"]["basisZ"]}}
             for key, view in manifest["views"].items()}
    source_scale = abs(next(iter(views.values()))["groundBasis"]["X"][0]) / 64
    views = camera_rows(views, source_scale=source_scale)
    width, height = manifest["canvasSize"]
    pivot = manifest["pivot"]
    palette = [int(value, 16) for value in manifest["palette"]]
    imported = []
    for direction in DIRECTIONS:
        for side in ("back", "front"):
            identity = f"persistent.shield.hit.{direction}.{side}"
            rows = {}
            for facing, view in views.items():
                bank = view["directions"][direction]["layers"][side]
                for relative in bank["pages"]:
                    destination = repo / "game/assets/persistent_spells/protection" / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source / relative, destination)
                rows[facing] = [[] if row is None else [{
                    "file": (Path("game/assets/persistent_spells/protection") / bank["pages"][row["page"]]).as_posix(),
                    "rect": row["source"], "offset": row["offset"]}] for row in bank["frames"]]
            count = len(rows["E"])
            assets[identity] = {"assetId": identity, "displayName": identity, "kind": "projectile",
                "sheet": f"/persistent-spells/shield/hit/{direction}/{side}.png",
                "frame": {"width": width, "height": height, "rows": 8, "cols": count},
                "fps": manifest["fps"], "rowOrder": list(DIRECTIONS),
                "phases": {"impact": {"start": 0, "frames": count, "fps": manifest["fps"], "loop": False}},
                "anchor": {"x": pivot[0] / width, "y": pivot[1] / height},
                "defaultScale": .5, "palettePreview": {"colors": palette}}
            bindings["projectileStorage"][identity] = {"phases": {"impact": {"layers": [
                {"blendMode": "normal", "partsByFacing": rows}]}}}
            imported.append(identity)
    for filename, value in (("bindings.json", bindings), ("projectile-assets.json", list(assets.values()))):
        (folder / filename).write_text(json.dumps(value, separators=(",", ":")) + "\n")
    return tuple(imported)


def import_volume(manifest_path: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    """Package declared color and raw world coordinates without changing either."""
    source = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("complete") is not True:
        raise ValueError("Volume import requires a complete four-camera delivery")
    windows = {phase: manifest[phase] for phase in ("apply", "hold")}
    if any(not 0 <= begin < end for begin, end in windows.values()):
        raise ValueError("Volume phase windows must be nonempty forward intervals")
    required_frames = max(end for _, end in windows.values())
    views = camera_rows({key: {**view, "groundBasis": {
        "X": view["camera"]["basisX"], "Z": view["camera"]["basisZ"]}}
        for key, view in manifest["views"].items()})
    if manifest["positionEncoding"]["format"] != "RGBA8_RAW_XZ_UNORM16":
        raise ValueError("Volume storage requires the declared raw X/Z encoding")
    bounds = [manifest["positionEncoding"][key] for key in ("min", "max")]
    for view in views.values():
        if view["color"]["rects"] != view["position"]["rects"]:
            raise ValueError("Volume color and raw coordinates must share registration")
        if len(view["color"]["rects"]) < required_frames:
            raise ValueError("Every volume camera must cover the complete declared phase windows")
    name = manifest["spell"]
    folder = repo / "game/data/persistent_spells"
    bindings = read_document(folder / "bindings.json", {"resources": {}, "projectileStorage": {}})
    assets = {row["assetId"]: row for row in read_document(folder / "projectile-assets.json", [])}
    target_root = Path("game/assets/persistent_spells/volumes") / name
    copied = set()

    def copy(relative: str) -> str:
        destination = target_root / relative
        if destination not in copied:
            (repo / destination).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, repo / destination)
            copied.add(destination)
        return destination.as_posix()

    width, height = manifest["canvasSize"]
    pivot = manifest["pivot"]
    imported = []
    for phase in ("apply", "hold"):
        begin, end = windows[phase]
        identity = f"persistent.{name}.{phase}"
        rows = {}
        for facing, view in views.items():
            rows[facing] = [[] if address is None else [{
                "file": copy(view["color"]["pages"][address["page"]]),
                "rect": address["source"],
                "offset": [int(address["offset"][axis] + pivot[axis]) for axis in range(2)],
                "footpoint": {"file": copy(view["position"]["pages"][address["page"]]), "bounds": bounds},
            }] for address in view["color"]["rects"][begin:end]]
        assets[identity] = {"assetId": identity, "displayName": identity, "kind": "projectile",
            "sheet": f"/persistent-spells/{name}/{phase}.png",
            "frame": {"width": width, "height": height, "rows": 8, "cols": end - begin},
            "fps": manifest["fps"], "rowOrder": list(DIRECTIONS),
            "phases": {"impact": {"start": 0, "frames": end - begin,
                "fps": manifest["fps"], "loop": phase == "hold"}},
            "anchor": {"x": pivot[0] / width, "y": pivot[1] / height},
            "defaultScale": .5, "palettePreview": {"colors": [int(color, 16) for color in manifest["palette"]]}}
        bindings["projectileStorage"][identity] = {"phases": {"impact": {"layers": [
            {"blendMode": "normal", "partsByFacing": rows}]}}}
        imported.append(identity)
    folder.mkdir(parents=True, exist_ok=True)
    for filename, value in (("bindings.json", bindings), ("projectile-assets.json", list(assets.values()))):
        (folder / filename).write_text(json.dumps(value, separators=(",", ":")) + "\n")
    return tuple(imported)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terrain", type=Path)
    parser.add_argument("--protection", type=Path)
    parser.add_argument("--shield-contacts", type=Path)
    parser.add_argument("--volume", type=Path)
    parser.add_argument("--name", default="shield")
    args = parser.parse_args()
    if args.terrain:
        imported = import_terrain(args.terrain)
    elif args.shield_contacts:
        imported = import_shield_contacts(args.shield_contacts)
    elif args.protection:
        imported = import_protection(args.protection, name=args.name)
    elif args.volume:
        imported = import_volume(args.volume)
    else:
        parser.error("Select a delivered terrain, protection, shield-contact or volume manifest")
    print(f"Imported {len(imported)} declared media phases; behavior authoring unchanged.")


if __name__ == "__main__":
    main()
