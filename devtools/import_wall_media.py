"""Install delivered wall atlases; authored behavior is a separate public input."""

import argparse
import json
from pathlib import Path

from devtools.art import copy_file, digest, read_manifest, write_json


ROOT = Path(__file__).resolve().parents[1]
ROW_ORDER = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")
CAMERA_ROWS = ("E", "S", "W", "N")


def import_wall_media(manifest_path: Path, *, archive: Path, production: Path,
                      repo: Path = ROOT, merge: bool = False) -> tuple[str, ...]:
    manifest = json.loads(manifest_path.read_text())
    source = Path(manifest["assetRoot"])
    checksums: dict[str, str] = {}
    for line in (manifest_path.parent / "SHA256SUMS").read_text().splitlines():
        if line:
            checksum, name = line.split("  ", 1)
            checksums[str(Path(name) if Path(name).is_absolute() else source / name)] = checksum
    folder = repo / "game/data/wall_media"
    relative_root = Path("game/assets/wall_media")
    assets, storage, installed = [], {}, {}
    bindings_path = folder / "bindings.json"
    previous = json.loads(bindings_path.read_text()) if bindings_path.exists() else {}
    # Preserve every delivered pinned file, not just phase-selected pages.
    for name, expected in checksums.items():
        original = Path(name)
        actual = digest(original)
        if actual != expected:
            raise ValueError(f"Delivered wall source checksum changed: {original}")
        destination = archive / original.relative_to(source)
        if destination.exists() and digest(destination) != actual:
            raise ValueError(f"Preserved source differs; choose a new archive: {destination}")
        copy_file(original, destination)
    handoff = archive / "handoff"
    handoff.mkdir(parents=True, exist_ok=True)
    for path in manifest_path.parent.iterdir():
        if path.is_file():
            target = handoff / path.name
            if target.exists() and digest(target) != digest(path):
                raise ValueError(f"Preserved handoff differs: {target}")
            copy_file(path, target)
    for name, bank in manifest["assets"].items():
        begin, end = bank["hold"]
        if bank["fps"] != manifest["fps"] or not 0 < begin < end == bank["frames"]:
            raise ValueError(f"Inconsistent wall lifecycle: {name}")
        if set(bank["cameras"]) != {"0", "1", "2", "3"}:
            raise ValueError(f"Wall bank requires four native cameras: {name}")
        for side in ("back", "front"):
            for phase, low, high in (("apply", 0, begin), ("hold", begin, end)):
                identity = f"wall.{name}.{side}.{phase}"
                rows = {}
                for camera, facing in enumerate(CAMERA_ROWS):
                    layer = bank["cameras"][str(camera)]["layers"][side]
                    if len(layer["frames"]) != bank["frames"]:
                        raise ValueError(f"Incomplete wall layer: {identity}/{camera}")
                    paths = []
                    for page in layer["pages"]:
                        target = relative_root / page
                        path = source / page
                        if str(path) not in checksums or digest(path) != checksums[str(path)]:
                            raise ValueError(f"Wall page lacks matching delivery checksum: {page}")
                        if target.as_posix() not in installed:
                            copy_file(path, repo / target)
                            copy_file(path, production / target)
                            installed[target.as_posix()] = {"path": target.as_posix(),
                                "bytes": path.stat().st_size, "sha256": digest(path)}
                        paths.append(target.as_posix())
                    rows[facing] = [[] if frame is None else [{"file": paths[frame["page"]],
                        "rect": frame["source"], "offset": frame["offset"]}]
                        for frame in layer["frames"][low:high]]
                cell = bank["cell"]
                assets.append({"assetId": identity, "displayName": identity, "sheet": f"/wall-media/{name}/{side}/{phase}.png",
                    "frame": {"width": cell, "height": cell, "rows": 8, "cols": high - low},
                    "fps": bank["fps"], "rowOrder": ROW_ORDER,
                    "phases": {"impact": {"start": 0, "frames": high - low,
                        "fps": bank["fps"], "loop": phase == "hold"}},
                    "anchor": {"x": bank["pivot"][0] / cell, "y": bank["pivot"][1] / cell},
                    "defaultScale": 1, "palettePreview": {"colors": [int(color, 16) for color in bank["palette"]]}})
                storage[identity] = {"phases": {"impact": {"layers": [
                    {"blendMode": "normal", "partsByFacing": rows}]}}}
    folder.mkdir(parents=True, exist_ok=True)
    if merge:
        existing_assets = json.loads((folder / "projectile-assets.json").read_text())
        by_identity = {row["assetId"]: row for row in existing_assets}
        for asset in assets:
            if asset["assetId"] in by_identity and by_identity[asset["assetId"]] != asset:
                raise ValueError(f"Wall extension conflicts with registered asset: {asset['assetId']}")
            by_identity[asset["assetId"]] = asset
        old_storage = previous.get("projectileStorage", {})
        for identity, row in storage.items():
            if identity in old_storage:
                original = json.loads(json.dumps(old_storage[identity]))
                for phase in original["phases"].values():
                    for layer in phase["layers"]:
                        for frames in layer["partsByFacing"].values():
                            for frame in frames:
                                for part in frame:
                                    part.pop("colorMasks", None)
                if original != row:
                    raise ValueError(f"Wall extension conflicts with registered crops: {identity}")
                storage[identity] = old_storage[identity]
        storage = {**old_storage, **storage}
        write_json(folder / "projectile-assets.json", list(by_identity.values()))
    else:
        write_json(folder / "projectile-assets.json", assets)
    # Import updates only storage; separately authored spell refs survive reruns.
    write_json(bindings_path, {**previous, "resources": previous.get("resources", {}), "projectileStorage": storage})
    receipt = read_manifest(production)
    files = {row["path"]: row for row in receipt["files"]}
    files.update(installed)
    receipt = {**receipt, "files": [files[path] for path in sorted(files)]}
    write_json(production / "art-manifest.json", receipt)
    write_json(repo / ".runtime/art-manifest.json", receipt)
    write_json(production / ("wall-directional-release.json" if merge else "wall-of-fire-release.json"), {"source": str(archive),
        "accepted_review": manifest.get("acceptedReview", str(archive / "handoff/APPROVAL.json")
            if (manifest_path.parent / "APPROVAL.json").exists() else None), "files": list(installed.values()),
        "fps": manifest["fps"], "new_bytes": sum(row["bytes"] for row in installed.values())})
    return tuple(asset["assetId"] for asset in assets)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--merge", action="store_true", help="Add a companion without replacing registered cardinal banks.")
    args = parser.parse_args()
    imported = import_wall_media(args.manifest, archive=args.archive, production=args.production, merge=args.merge)
    print(f"Imported {len(imported)} wall phase records; original pages and pivots preserved.")


if __name__ == "__main__":
    main()
