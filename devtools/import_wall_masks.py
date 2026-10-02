"""Install registered side/base classification without replacing wall RGBA."""

import argparse
import json
from pathlib import Path

from devtools.art import copy_file, digest, read_manifest, write_json


ROOT = Path(__file__).resolve().parents[1]
CAMERA_ROWS = ("E", "S", "W", "N")


def import_wall_masks(source: Path, *, archive: Path, production: Path,
                      repo: Path = ROOT, merge: bool = False) -> int:
    manifest = json.loads((source / "mask-assets.json").read_text())
    if manifest["fps"] != 32:
        raise ValueError("Wall mask clock must match the installed native 32 FPS")
    checksums = {}
    for line in (source / "SHA256SUMS").read_text().splitlines():
        if line:
            expected, name = line.split("  ", 1)
            relative = Path(name).relative_to(source) if Path(name).is_absolute() else Path(name)
            checksums[relative.as_posix()] = expected
    for name, expected in checksums.items():
        original, target = source / name, archive / name
        if digest(original) != expected:
            raise ValueError(f"Changed delivered mask source: {original}")
        if target.exists() and digest(target) != expected:
            raise ValueError(f"Preserved mask differs: {target}")
        copy_file(original, target)
    copy_file(source / "SHA256SUMS", archive / "SHA256SUMS")
    control = source / "original-rgba-sha256.json"
    if control.exists():
        for name, expected in json.loads(control.read_text()).items():
            original = Path(name)
            installed = repo / "game/assets/wall_media" / original.relative_to(original.parents[3])
            if digest(installed) != expected:
                raise ValueError(f"Installed RGBA differs from mask registration control: {installed}")
    else:
        color = json.loads((source / "wall-assets.json").read_text())
        for bank in color["assets"].values():
            for camera in bank["cameras"].values():
                for layer in camera["layers"].values():
                    for page in layer["pages"]:
                        installed = repo / "game/assets/wall_media" / page
                        if page not in checksums or digest(installed) != checksums[page]:
                            raise ValueError(f"Installed RGBA differs from companion control: {installed}")
    path = repo / "game/data/wall_media/bindings.json"
    bindings = json.loads(path.read_text())
    installed = {}
    for name, bank in manifest["assets"].items():
        for side in ("back", "front"):
            for phase, low, high in (("apply", 0, 48), ("hold", 48, 112)):
                identity = f"wall.{name}.{side}.{phase}"
                rows = bindings["projectileStorage"][identity]["phases"]["impact"]["layers"][0]["partsByFacing"]
                for camera, facing in enumerate(CAMERA_ROWS):
                    layer = bank["cameras"][str(camera)]["layers"][side]
                    for sign in ("positive", "negative"):
                        masks = layer[manifest.get("signs", {}).get(sign, sign)]
                        for index, frame in enumerate(masks["frames"][low:high]):
                            parts = rows[facing][index]
                            if frame is None:
                                if parts:
                                    raise ValueError(f"Wall mask omits an original frame: {identity}")
                                continue
                            if len(parts) != 1 or parts[0]["rect"] != frame["source"] or parts[0]["offset"] != frame["offset"]:
                                raise ValueError(f"Wall mask crop differs: {identity}/{camera}/{index}")
                            page = masks["pages"][frame["page"]]
                            relative = Path("game/assets/wall_masks") / page
                            if page not in checksums:
                                raise ValueError(f"Mask page is not pinned: {page}")
                            if relative.as_posix() not in installed:
                                copy_file(source / page, repo / relative)
                                copy_file(source / page, production / relative)
                                installed[relative.as_posix()] = {"path": relative.as_posix(),
                                    "sha256": checksums[page], "bytes": (source / page).stat().st_size}
                            parts[0].setdefault("colorMasks", {})[sign] = relative.as_posix()
    write_json(path, bindings)
    receipt = read_manifest(production)
    files = {row["path"]: row for row in receipt["files"]}
    files.update(installed)
    receipt = {**receipt, "files": [files[path] for path in sorted(files)]}
    write_json(production / "art-manifest.json", receipt)
    write_json(repo / ".runtime/art-manifest.json", receipt)
    write_json(production / ("wall-directional-mask-release.json" if merge else "wall-safe-mask-release.json"), {"source": str(archive),
        "fps": 32, "files": list(installed.values()), "bytes": sum(row["bytes"] for row in installed.values())})
    return sum(row["bytes"] for row in installed.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--merge", action="store_true", help="Preserve the earlier cardinal release receipt.")
    args = parser.parse_args()
    size = import_wall_masks(args.source, archive=args.archive, production=args.production, merge=args.merge)
    print(f"Installed {size:,} bytes of registered R8 masks; original RGBA unchanged.")


if __name__ == "__main__":
    main()
