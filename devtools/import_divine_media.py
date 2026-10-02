"""Register accepted divine atlas phase views without authoring spell behavior."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
MEDIA = Path("game/assets/divine_media")
DIRECTIONS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")
EFFECTS = ("beacon_of_hope", "daylight", "mass_healing_word", "divine_word",
           "divine_proclamation", "divine_condition_blinded", "divine_condition_deafened")


def import_bundle(source: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    """Verify the entire selected packet before copying any atlas page."""
    manifest = json.loads((source / "media.json").read_text())
    symbols_path = source / "shared-symbols-approved.json"
    if symbols_path.exists():
        symbols = json.loads(symbols_path.read_text())
        for condition in ("blinded", "deafened"):
            manifest[f"divine_condition_{condition}"] = symbols[condition]
    checksums = {}
    for line in (source / "SHA256SUMS").read_text().splitlines():
        digest, relative = line.split(maxsplit=1)
        checksums[relative.strip().removeprefix("./")] = digest
    payloads = {}
    for name in EFFECTS:
        row = manifest[name]
        if row["fps"] != 32 or set(row["cameras"]) != {"0", "1", "2", "3"}:
            raise ValueError(f"{name}: accepted native 32-FPS four-view delivery required")
        hold = row.get("hold")
        if hold is not None and not 0 < hold[0] < hold[1] <= row["frames"]:
            raise ValueError(f"{name}: invalid maintained window")
        for camera in row["cameras"].values():
            if set(camera["layers"]) != {"back", "front"}:
                raise ValueError(f"{name}: paired rear/front layers required")
            for layer in camera["layers"].values():
                if len(layer["frames"]) != row["frames"]:
                    raise ValueError(f"{name}: incomplete frame addresses")
                for frame in layer["frames"]:
                    if frame is not None and not 0 <= frame["page"] < len(layer["pages"]):
                        raise ValueError(f"{name}: absent atlas page")
                for relative in layer["pages"]:
                    origin = (source / relative).resolve()
                    if not origin.is_relative_to(source.resolve()):
                        raise ValueError("divine media path leaves delivery")
                    if relative not in payloads:
                        if hashlib.sha256(origin.read_bytes()).hexdigest() != checksums.get(relative):
                            raise ValueError(f"checksum mismatch: {relative}")
                        payloads[relative] = origin
    folder = repo / "game/data/divine_media"
    path = folder / "bindings.json"
    bindings = json.loads(path.read_text()) if path.exists() else {"resources": {}, "spells": {}}
    storage = bindings.setdefault("projectileStorage", {})
    path = folder / "projectile-assets.json"
    assets = {row["assetId"]: row for row in json.loads(path.read_text())} if path.exists() else {}
    for name in EFFECTS:
        row = manifest[name]
        hold = row.get("hold")
        symbol = name.startswith("divine_condition_")
        windows = (("apply", 0, hold[0], False), ("hold", hold[0], hold[1] - hold[0], True)) if hold else (
            ("sustain" if symbol else "finite", 0, row["frames"], symbol),)
        for phase, first, count, loop in windows:
            for side in ("back", "front"):
                identity = f"divine.{name}.{phase}.{side}"
                views = {}
                for q in range(4):
                    layer = row["cameras"][str(q)]["layers"][side]
                    parts = [[] if frame is None else [{
                        "file": (MEDIA / layer["pages"][frame["page"]]).as_posix(),
                        "rect": frame["source"], "offset": frame["offset"]}]
                        for frame in layer["frames"][first:first + count]]
                    views[DIRECTIONS[q * 2]] = parts
                    views[DIRECTIONS[q * 2 + 1]] = parts
                # Shared symbols omit cell; the packet contract fixes every canvas at512px.
                cell = row.get("cell", 512)
                assets[identity] = {"assetId": identity, "displayName": identity, "kind": "projectile",
                    "sheet": f"/divine-media/{name}/{phase}/{side}.png",
                    "frame": {"width": cell, "height": cell, "rows": 8, "cols": count},
                    "fps": 32, "rowOrder": list(DIRECTIONS),
                    "phases": {"impact": {"start": 0, "frames": count, "fps": 32, "loop": loop}},
                    "anchor": {"x": row["pivot"][0] / cell, "y": row["pivot"][1] / cell},
                    "defaultScale": .5,
                    "palettePreview": {"colors": [int(color, 16) for color in row["palette"]]}}
                if symbol:
                    anchors = {}
                    for q in range(4):
                        bottom = max((frame["offset"][1] + frame["source"][3]
                            for layer in row["cameras"][str(q)]["layers"].values()
                            for frame in layer["frames"] if frame is not None), default=row["pivot"][1])
                        anchor = {"x": row["pivot"][0] / cell, "y": bottom / cell}
                        anchors[DIRECTIONS[q * 2]] = anchor
                        anchors[DIRECTIONS[q * 2 + 1]] = anchor
                    assets[identity]["anchorsByFacing"] = anchors
                storage[identity] = {"phases": {"impact": {"layers": [
                    {"partsByFacing": views, "blendMode": "normal"}]}}}
    for relative, origin in payloads.items():
        destination = repo / MEDIA / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)
    folder.mkdir(parents=True, exist_ok=True)
    for name, value in (("bindings.json", bindings), ("projectile-assets.json", list(assets.values()))):
        (folder / name).write_text(json.dumps(value, indent=2) + "\n")
    return tuple(assets)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args()
    print(f"Registered {len(import_bundle(args.source, repo=args.repo))} divine phase layers")
