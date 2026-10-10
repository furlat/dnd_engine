"""Install only Fly's approved original Longstrider wind dependency.

No recipes are written. The 128 source samples remain archived; registered
formation/hold/release windows share the two unchanged original atlas pages.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FACINGS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def import_wind(source: Path, *, preserved: Path, production: Path, repo: Path = ROOT) -> dict:
    manifest = source / "final-utility-batch/wind.json"
    rows = json.loads(manifest.read_text())
    payloads = {}
    for side in ("back", "front"):
        row = rows[f"longstrider-{side}"]
        if row["fps"] != 32 or row["hold"] != [31, 95] or len(row["frames"]) != 128:
            raise ValueError("Fly requires the accepted 32 FPS Longstrider wind windows")
        for relative in row["pages"]:
            path = (source / "nature-utility-batch" / relative).resolve()
            if not path.is_relative_to((source / "nature-utility-batch").resolve()):
                raise ValueError("wind source leaves the approved directory")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != row["sha256"][relative]:
                raise ValueError(f"wind source checksum mismatch: {relative}")
            with Image.open(path) as image:
                for frame in row["frames"]:
                    if frame is None:
                        continue
                    x, y, width, height = frame["source"]
                    if min(x, y) < 0 or min(width, height) <= 0 or x + width > image.width or y + height > image.height:
                        raise ValueError("wind source frame leaves its original page")
            payloads[relative] = (path, digest)
    # All source bytes and destinations are admitted before copying anything.
    for relative, (origin, _) in payloads.items():
        for target in (preserved / relative, repo / "game/assets/fly_wind" / relative,
                       production / "game/assets/fly_wind" / relative):
            if target.exists() and not target.is_file():
                raise ValueError(f"wind destination is not a file: {target}")
            if target.is_file() and target.read_bytes() != origin.read_bytes():
                raise ValueError(f"refusing to overwrite different wind source bytes: {target}")
            if any(parent.exists() and not parent.is_dir() for parent in target.parents):
                raise ValueError(f"wind destination parent is not a directory: {target}")
    bundle = repo / "game/data/support_conditions"
    bindings = json.loads((bundle / "bindings.json").read_text())
    assets = {row["assetId"]: row for row in json.loads((bundle / "projectile-assets.json").read_text())}
    identities = []
    for side in ("back", "front"):
        row = rows[f"longstrider-{side}"]
        for phase, first, count, loop in (("apply", 0, 31, False), ("hold", 31, 64, True), ("release", 95, 33, False)):
            identity = f"support.fly.wind.{phase}.{side}"
            identities.append(identity)
            parts = [[] if frame is None else [{"file": f"game/assets/fly_wind/{row['pages'][frame['page']]}",
                       "rect": frame["source"], "offset": frame["offset"]}]
                     for frame in row["frames"][first:first + count]]
            cell = row["cell"]
            assets[identity] = {"assetId": identity, "displayName": identity, "sheet": f"/fly-wind/{phase}/{side}.png",
                "frame": {"width": cell, "height": cell, "rows": 8, "cols": count},
                "fps": 32, "rowOrder": list(FACINGS),
                "phases": {"impact": {"start": 0, "frames": count, "fps": 32, "loop": loop}},
                "anchor": {"x": row["pivot"][0] / cell, "y": row["pivot"][1] / cell},
                "defaultScale": 1 / row["captureZoom"] / 2,
                "palettePreview": {"colors": [0x263f4b, 0x426a7b, 0x71c5e5]}}
            bindings.setdefault("projectileStorage", {})[identity] = {"phases": {"impact": {"layers": [
                {"partsByFacing": {facing: parts for facing in FACINGS}, "blendMode": "normal"}]}}}
    manifest_path = production / "art-manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    private = json.loads(manifest_bytes)
    installed = {row["path"]: row for row in private["files"]}
    receipt = {"source": str(source), "windows": {"apply": [0, 31], "hold": [31, 95], "release": [95, 128]},
        "fps": 32, "identities": identities, "files": [], "source_metadata": "wind.json"}
    preserved.mkdir(parents=True, exist_ok=True)
    if not (preserved / "previous-art-manifest.json").exists():
        (preserved / "previous-art-manifest.json").write_bytes(manifest_bytes)
    shutil.copyfile(manifest, preserved / "wind.json")
    for name in ("HANDOFF.md", "approval.json"):
        shutil.copyfile(source / "final-utility-batch" / name, preserved / name)
    for relative, (origin, digest) in payloads.items():
        local_path = f"game/assets/fly_wind/{relative}"
        for target in (preserved / relative, repo / local_path, production / local_path):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError(f"wind copy checksum mismatch: {target}")
        installed[local_path] = {"path": local_path, "bytes": origin.stat().st_size, "sha256": digest}
        receipt["files"].append(installed[local_path])
    private["files"] = sorted(installed.values(), key=lambda row: row["path"])
    private["total_bytes"] = sum(row["bytes"] for row in private["files"])
    write(manifest_path, private)
    (bundle / "bindings.json").write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
    (bundle / "projectile-assets.json").write_text(json.dumps(list(assets.values()), separators=(",", ":")) + "\n")
    write(bundle / "fly-wind-source.json", receipt)
    write(preserved / "install-receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--preserved", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(import_wind(args.source, preserved=args.preserved, production=args.production), indent=2))
