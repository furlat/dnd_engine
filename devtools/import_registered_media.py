"""Offline registration of pinned paired32FPS color banks into existing storage."""

import hashlib
import json
from pathlib import Path
import shutil

DIRECTIONS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")


def import_registered_bank(source: Path, row: dict, program: str,
                 windows: tuple[tuple[str, int, int], ...], repo: Path, *,
                 bundle: str, default_scale: float = 1) -> tuple[str, ...]:
    media_root = Path("game/assets") / bundle
    if row["fps"] != 32:
        raise ValueError("Registered media requires32FPS")
    if any(first < 0 or count <= 0 or first+count > row["frames"] for _,first,count in windows):
        raise ValueError("Selected media window is outside the source")
    if set(row["cameras"]) != {"0", "1", "2", "3"}:
        raise ValueError("Registered media requires four native views")
    checksums = {}
    for line in (source / "SHA256SUMS").read_text().splitlines():
        digest, relative = line.split(maxsplit=1)
        checksums[relative.strip().removeprefix("./")] = digest
    payloads = {}
    for camera in row["cameras"].values():
        if set(camera["layers"]) != {"back", "front"}:
            raise ValueError("Registered media requires paired layers")
        for layer in camera["layers"].values():
            if len(layer["frames"]) != row["frames"]:
                raise ValueError("Incomplete Registered media frame addresses")
            for frame in layer["frames"]:
                if frame is not None and not 0 <= frame["page"] < len(layer["pages"]):
                    raise ValueError("Registered media sample refers to absent page")
            for relative in layer["pages"]:
                origin = (source / relative).resolve()
                if not origin.is_relative_to(source.resolve()):
                    raise ValueError("Registered media path leaves delivery")
                if relative not in payloads:
                    if hashlib.sha256(origin.read_bytes()).hexdigest() != checksums.get(relative):
                        raise ValueError(f"checksum mismatch: {relative}")
                    payloads[relative] = origin
    folder = repo / "game/data" / bundle
    path = folder / "bindings.json"
    bindings = json.loads(path.read_text()) if path.exists() else {"resources": {}, "spells": {}}
    storage = bindings.setdefault("projectileStorage", {})
    path = folder / "projectile-assets.json"
    assets = {asset["assetId"]: asset for asset in json.loads(path.read_text())} if path.exists() else {}
    identities = []
    for phase, first, count in windows:
        for side in ("back", "front"):
            identity = f"{bundle.removesuffix('_media')}.{program}.{phase}.{side}"
            identities.append(identity)
            views = {}
            for q in range(4):
                layer = row["cameras"][str(q)]["layers"][side]
                parts = [[] if frame is None else [{
                    "file": (media_root / layer["pages"][frame["page"]]).as_posix(),
                    "rect": frame["source"], "offset": frame["offset"]}]
                    for frame in layer["frames"][first:first + count]]
                views[DIRECTIONS[2 * q]] = parts
                views[DIRECTIONS[2 * q + 1]] = parts
            cell = row["cell"]
            assets[identity] = {"assetId": identity, "displayName": identity, "kind": "projectile",
                "sheet": f"/{bundle}/{program}/{phase}/{side}.png",
                "frame": {"width": cell, "height": cell, "rows": 8, "cols": count},
                "fps": 32, "rowOrder": list(DIRECTIONS),
                "phases": {"impact": {"start": 0, "frames": count, "fps": 32, "loop": phase == "hold"}},
                "anchor": {"x": row["pivot"][0] / cell, "y": row["pivot"][1] / cell},
                "defaultScale": default_scale,
                "palettePreview": {"colors": [int(color, 16) for color in row["palette"]]}}
            storage[identity] = {"phases": {"impact": {"layers": [
                {"partsByFacing": views, "blendMode": "normal"}]}}}
    for relative, origin in payloads.items():
        destination = repo / media_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)
    folder.mkdir(parents=True, exist_ok=True)
    for name, value in (("bindings.json", bindings), ("projectile-assets.json", list(assets.values()))):
        (folder / name).write_text(json.dumps(value, indent=2) + "\n")
    return tuple(identities)

