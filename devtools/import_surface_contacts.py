"""Install accepted finite ignition onsets, preserving the complete private delivery."""

import argparse
import json
from pathlib import Path

from devtools.art import copy_file, digest, read_manifest, write_json


ROOT = Path(__file__).resolve().parents[1]
CAMERA_ROWS = ("E", "S", "W", "N")
BANKS = (("growth_v36_d0_v0", "growth_v36_d0_v1"),
         ("growth_v36_d1_v0", "growth_v35_d1_v1"),
         ("growth_v35_d2_v0", "growth_v35_d2_v1"),
         ("growth_v35_d3_v0", "growth_v35_d3_v1"))


def import_surface_contacts(source: Path, *, archive: Path, production: Path,
                            repo: Path = ROOT) -> tuple[str, ...]:
    manifest = json.loads((source / "surface-assets.json").read_text())
    checksums = dict(line.split("  ", 1)[::-1]
                     for line in (source / "SHA256SUMS").read_text().splitlines() if line)
    for name, expected in checksums.items():
        original, target = source / name, archive / name
        if digest(original) != expected:
            raise ValueError(f"Changed delivered source: {original}")
        if target.exists() and digest(target) != expected:
            raise ValueError(f"Preserved source differs: {target}")
        copy_file(original, target)
    copy_file(source / "SHA256SUMS", archive / "SHA256SUMS")
    assets, storage, installed = [], {}, {}
    for name in (name for pair in BANKS for name in pair):
        bank = manifest["assets"][name]["media"]
        if bank["fps"] != 32 or bank["hold"][0] != 48 or bank["cell"] != 512:
            raise ValueError(f"Unexpected formation contract: {name}")
        for side in ("back", "front"):
            identity = f"surface-contact.{name}.{side}"
            rows = {}
            for camera, facing in enumerate(CAMERA_ROWS):
                layer = bank["cameras"][str(camera)]["layers"][side]
                frames = layer["frames"][:48]
                pages = {}
                for page in sorted({frame["page"] for frame in frames if frame is not None}):
                    original = layer["pages"][page]
                    relative = Path("game/assets/surface_contacts") / original
                    path = source / original
                    if original not in checksums:
                        raise ValueError(f"Unpinned production page: {original}")
                    if relative.as_posix() not in installed:
                        copy_file(path, repo / relative)
                        copy_file(path, production / relative)
                        installed[relative.as_posix()] = {"path": relative.as_posix(),
                            "sha256": checksums[original], "bytes": path.stat().st_size}
                    pages[page] = relative.as_posix()
                rows[facing] = [[] if frame is None else [{"file": pages[frame["page"]],
                    "rect": frame["source"], "offset": frame["offset"]}] for frame in frames]
            assets.append({"assetId": identity, "displayName": identity, "kind": "projectile",
                "sheet": f"/surface-contact/{name}/{side}.png",
                "frame": {"width": 512, "height": 512, "rows": 8, "cols": 48},
                "fps": 32, "rowOrder": ("E", "SE", "S", "SW", "W", "NW", "N", "NE"),
                "phases": {"impact": {"start": 0, "frames": 48, "fps": 32, "loop": False}},
                "anchor": {"x": bank["pivot"][0]/512, "y": bank["pivot"][1]/512},
                "defaultScale": 1,
                "palettePreview": {"colors": [int(color, 16) for color in bank["palette"]]}})
            storage[identity] = {"phases": {"impact": {"layers": [{"blendMode": "normal",
                "partsByFacing": rows}]}}}
    folder = repo / "game/data/surface_contact_media"
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "projectile-assets.json", assets)
    write_json(folder / "bindings.json", {"resources": {}, "projectileStorage": storage})
    receipt = read_manifest(production)
    files = {row["path"]: row for row in receipt["files"]}
    files.update(installed)
    receipt = {**receipt, "files": [files[path] for path in sorted(files)]}
    write_json(production / "art-manifest.json", receipt)
    write_json(repo / ".runtime/art-manifest.json", receipt)
    write_json(production / "surface-contact-release.json", {"source": str(archive),
        "formation_frames": [0, 48], "fps": 32, "has_xyz": False,
        "files": list(installed.values()), "bytes": sum(row["bytes"] for row in installed.values())})
    return tuple(asset["assetId"] for asset in assets)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    args = parser.parse_args()
    identities = import_surface_contacts(args.source, archive=args.archive, production=args.production)
    print(f"Installed {len(identities)} paired formation records at native 32 FPS.")


if __name__ == "__main__":
    main()
