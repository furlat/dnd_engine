"""Register the released control envelope without authoring condition behavior."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
MEDIA = Path("game/assets/control_media")
DIRECTIONS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")


def import_slow(source: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    """Validate the pinned packet before installing its two 128-frame views."""
    row = json.loads((source / "production-handoff/slow-approved-media.json").read_text())["slow_crimson_v7"]
    if (row["frames"], row["loopFrames"], row["duplicateEndpoint"]) != (129, 128, 128):
        raise ValueError("Slow requires the accepted 128-sample loop plus verification endpoint")
    if row["loopSeconds"] != 4 or set(row["cameras"]) != {"0", "1", "2", "3"}:
        raise ValueError("Slow requires four native views of the four-second loop")
    checksums = {}
    for line in (source / "production-handoff/SLOW_SHA256SUMS").read_text().splitlines():
        digest, relative = line.split(maxsplit=1)
        checksums[relative.strip().removeprefix("./")] = digest
    payloads = {}
    for camera in row["cameras"].values():
        if set(camera["layers"]) != {"back", "front"}:
            raise ValueError("Slow requires both body layers")
        for layer in camera["layers"].values():
            if len(layer["frames"]) != row["frames"]:
                raise ValueError("Slow has incomplete sample addresses")
            for frame in layer["frames"]:
                if frame is None or not 0 <= frame["page"] < len(layer["pages"]):
                    raise ValueError("Slow sample refers to an absent page")
            for relative in layer["pages"]:
                origin = (source / relative).resolve()
                if not origin.is_relative_to(source.resolve()):
                    raise ValueError("Slow media path leaves delivery")
                if relative not in payloads:
                    if hashlib.sha256(origin.read_bytes()).hexdigest() != checksums.get(relative):
                        raise ValueError(f"checksum mismatch: {relative}")
                    payloads[relative] = origin
    folder = repo / "game/data/control_media"
    path = folder / "bindings.json"
    bindings = json.loads(path.read_text()) if path.exists() else {"resources": {}, "spells": {}}
    storage = bindings.setdefault("projectileStorage", {})
    path = folder / "projectile-assets.json"
    assets = {asset["assetId"]: asset for asset in json.loads(path.read_text())} if path.exists() else {}
    identities = []
    for side in ("back", "front"):
        identity = f"control.slow.sustain.{side}"
        identities.append(identity)
        views = {}
        for q in range(4):
            layer = row["cameras"][str(q)]["layers"][side]
            parts = [[{"file": (MEDIA / layer["pages"][frame["page"]]).as_posix(),
                "rect": frame["source"], "offset": frame["offset"]}]
                for frame in layer["frames"][:128]]
            views[DIRECTIONS[2 * q]] = parts
            views[DIRECTIONS[2 * q + 1]] = parts
        cell = row["cell"]
        assets[identity] = {"assetId": identity, "displayName": identity, "sheet": f"/control-media/slow/{side}.png",
            "frame": {"width": cell, "height": cell, "rows": 8, "cols": 128},
            "fps": 32, "rowOrder": list(DIRECTIONS),
            "phases": {"impact": {"start": 0, "frames": 128, "fps": 32, "loop": True}},
            "anchor": {"x": row["pivot"][0] / cell, "y": row["pivot"][1] / cell},
            "defaultScale": .5,
            "palettePreview": {"colors": [int(color, 16) for color in row["palette"]]}}
        storage[identity] = {"phases": {"impact": {"layers": [
            {"partsByFacing": views, "blendMode": "normal"}]}}}
    for relative, origin in payloads.items():
        destination = repo / MEDIA / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)
    folder.mkdir(parents=True, exist_ok=True)
    for name, value in (("bindings.json", bindings), ("projectile-assets.json", list(assets.values()))):
        (folder / name).write_text(json.dumps(value, indent=2) + "\n")
    return tuple(identities)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args()
    print(f"Registered {len(import_slow(args.source, repo=args.repo))} Slow layer views")
