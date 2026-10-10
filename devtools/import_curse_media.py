"""Install the accepted Bestow Curse selection without writing animation recipes.

Source atlases remain unchanged. Warmup and maintain are registered views into
the same pages; clear and resisted banks remain distinct finite sequences.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
MEDIA = Path("game/assets/curse_media")
DIRECTIONS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")
MARKS = ("ability_burden", "bent_strike", "action_denial", "necrotic_wound")
BANKS = ("curse_touch_v8", "curse_rings_loop_v13", "curse_rings_release_v13", *(
    f"curse_{mark}_{phase}_source_v{14 if mark == 'necrotic_wound' else 12}"
    for mark in MARKS for phase in ("loop", "release", "resisted")))


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def import_bundle(source: Path, *, source_root: Path, repo: Path = ROOT) -> tuple[str, ...]:
    """Validate all selected payloads before mutating the chosen destination."""
    manifest = json.loads((source / "curse-assets.json").read_text())
    if manifest["schema"] != "codexfx.bestow-curse.v1" or manifest["fps"] != 32:
        raise ValueError("Bestow Curse requires the accepted native 32-FPS contract")
    checksums = {}
    for line in (source / "SOURCE-SHA256SUMS").read_text().splitlines():
        digest, relative = line.split(maxsplit=1)
        checksums[relative.strip()] = digest
    selected = {name: manifest["assets"][name] for name in BANKS}
    payloads: dict[str, Path] = {}
    for name, row in selected.items():
        if set(row["cameras"]) != {"0", "1", "2", "3"}:
            raise ValueError(f"{name}: four native views required")
        if row["frames"] < 96 and "_loop_" in name:
            raise ValueError(f"{name}: maintain interior is incomplete")
        for view in row["cameras"].values():
            if set(view["layers"]) != {"back", "front"}:
                raise ValueError(f"{name}: rear/front pair required")
            for layer in view["layers"].values():
                if len(layer["frames"]) != row["frames"]:
                    raise ValueError(f"{name}: incomplete frame addresses")
                for frame in layer["frames"]:
                    if frame is not None and not 0 <= frame["page"] < len(layer["pages"]):
                        raise ValueError(f"{name}: frame references an absent page")
                for relative in layer["pages"]:
                    path = (source_root / relative).resolve()
                    if not path.is_relative_to(source_root.resolve()):
                        raise ValueError("curse media path leaves source root")
                    if relative not in payloads:
                        if hashlib.sha256(path.read_bytes()).hexdigest() != checksums.get(relative):
                            raise ValueError(f"checksum mismatch: {relative}")
                        payloads[relative] = path
    folder = repo / "game/data/curse_media"
    path = folder / "bindings.json"
    bindings = json.loads(path.read_text()) if path.exists() else {"resources": {}, "spells": {}}
    path = folder / "projectile-assets.json"
    assets = {r["assetId"]: r for r in json.loads(path.read_text())} if path.exists() else {}
    storage = bindings.setdefault("projectileStorage", {})
    imported = []
    for name, row in selected.items():
        windows = (("apply", 0, 32, False), ("hold", 32, 64, True)) if "_loop_" in name else (
            ("finite", 0, row["frames"], False),)
        for phase, first, count, loop in windows:
            for side in ("back", "front"):
                identity = f"curse.{name}.{phase}.{side}"
                views = {}
                for q in range(4):
                    layer = row["cameras"][str(q)]["layers"][side]
                    parts = [[] if f is None else [{"file": (MEDIA / layer["pages"][f["page"]]).as_posix(),
                        "rect": f["source"], "offset": f["offset"]}]
                        for f in layer["frames"][first:first + count]]
                    views[DIRECTIONS[q * 2]] = parts
                    views[DIRECTIONS[q * 2 + 1]] = parts
                cell = row["cell"]
                assets[identity] = {"assetId": identity, "displayName": identity, "sheet": f"/curse-media/{name}/{phase}/{side}.png",
                    "frame": {"width": cell, "height": cell, "rows": 8, "cols": count},
                    "fps": 32, "rowOrder": list(DIRECTIONS),
                    "phases": {"impact": {"start": 0, "frames": count, "fps": 32, "loop": loop}},
                    "anchor": {"x": row["pivot"][0] / cell, "y": row["pivot"][1] / cell},
                    "defaultScale": .5,
                    "palettePreview": {"colors": [int(c, 16) for c in row["palette"]]},
                    "source": {"package": "bestow-curse-8aa6f9ef813c", "asset": name,
                        "notes": f"Unchanged atlas samples {first}..{first + count - 1}; source pivot."}}
                mark = next((mark for mark in MARKS if name.startswith(f"curse_{mark}_")), None)
                if mark is not None:
                    # One registered lower edge for apply, hold, clear and resisted;
                    # the original ground pivot remains in anchor/source-registration.
                    anchors = {}
                    for q in range(4):
                        bottom = max((frame["offset"][1] + frame["source"][3]
                            for bank_name, bank in selected.items()
                            if bank_name.startswith(f"curse_{mark}_")
                            for layer in bank["cameras"][str(q)]["layers"].values()
                            for frame in layer["frames"] if frame is not None), default=row["pivot"][1])
                        anchor = {"x": row["pivot"][0] / cell, "y": bottom / cell}
                        anchors[DIRECTIONS[q * 2]] = anchor
                        anchors[DIRECTIONS[q * 2 + 1]] = anchor
                    assets[identity]["anchorsByFacing"] = anchors
                storage[identity] = {"phases": {"impact": {"layers": [
                    {"partsByFacing": views, "blendMode": "normal"}]}}}
                imported.append(identity)
    for relative, origin in payloads.items():
        destination = repo / MEDIA / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)
    _write(folder / "bindings.json", bindings)
    _write(folder / "projectile-assets.json", list(assets.values()))
    _write(folder / "source-registration.json", {"schema": "dnd.curseSourceRegistration", "version": 1,
        "package": "bestow-curse-8aa6f9ef813c", "hasXYZ": False,
        "banks": {name: {key: row[key] for key in ("cell", "ortho", "targetY", "pivot", "frames")}
            for name, row in selected.items()},
        "payloads": {relative: {"sha256": checksums[relative], "bytes": origin.stat().st_size}
            for relative, origin in payloads.items()}})
    return tuple(imported)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args()
    print(f"Registered {len(import_bundle(args.source, source_root=args.source_root, repo=args.repo))} curse phase layers")
