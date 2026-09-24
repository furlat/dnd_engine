"""Install selected support-condition atlas groups without authoring behavior.

The source manifest owns pixels, frame tables and registration. Public Studio
and condition recipes independently own lifecycle and selection.
"""

import argparse
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
MEDIA = Path("game/assets/support_conditions")
DIRECTIONS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")


def import_group(source: Path, group: str, *, repo: Path = ROOT) -> tuple[str, ...]:
    manifest = json.loads((source / "groups" / group / "manifest.json").read_text())
    if not manifest["readiness"]["fourNativeCameras"]:
        raise ValueError(f"{group}: native camera delivery is incomplete")
    folder = repo / "game/data/support_conditions"
    binding_path = folder / "bindings.json"
    bindings = json.loads(binding_path.read_text()) if binding_path.exists() else {"resources": {}, "spells": {}}
    assets_path = folder / "projectile-assets.json"
    assets = {row["assetId"]: row for row in json.loads(assets_path.read_text())} if assets_path.exists() else {}
    storage = bindings.setdefault("projectileStorage", {})
    copied: set[Path] = set()
    imported = []

    def copy(relative: str) -> str:
        origin = (source / relative).resolve()
        if not origin.is_relative_to(source.resolve()):
            raise ValueError(f"media path leaves delivery: {relative}")
        destination = MEDIA / relative
        if destination not in copied:
            (repo / destination).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, repo / destination)
            copied.add(destination)
        return destination.as_posix()

    for name, row in manifest["phases"].items():
        if set(row["cameras"]) != {"0", "1", "2", "3"}:
            raise ValueError(f"{name}: all four native camera banks are required")
        width, height = row["canvas"]
        fps, count, pivot = row["fps"], row["frameCount"], row["pivot"]
        for side in ("back", "front"):
            identity = f"support.{name}.{side}"
            views = {}
            for q in range(4):
                layer = row["cameras"][str(q)]["layers"][side]
                if len(layer["frames"]) != count:
                    raise ValueError(f"{name}/q{q}/{side}: incomplete frame sequence")
                parts = [[] if frame is None else [{
                    "file": copy(layer["pages"][frame["page"]]),
                    "rect": frame["source"], "offset": frame["offset"],
                }] for frame in layer["frames"]]
                # Fixed E world basis chooses E/S/W/N for native q0/q1/q2/q3.
                views[DIRECTIONS[q * 2]] = parts
                views[DIRECTIONS[q * 2 + 1]] = parts
            assets[identity] = {
                "assetId": identity, "displayName": identity, "kind": "projectile",
                "sheet": f"/support-conditions/{name}/{side}.png",
                "frame": {"width": width, "height": height, "rows": 8, "cols": count},
                "fps": fps, "rowOrder": list(DIRECTIONS),
                "phases": {"impact": {"start": 0, "frames": count, "fps": fps, "loop": row["loop"]}},
                "anchor": {"x": pivot[0] / width, "y": pivot[1] / height}, "defaultScale": .5,
                "palettePreview": {"colors": [int(color, 16) for color in row["palette"]]},
            }
            storage[identity] = {"phases": {"impact": {"layers": [
                {"partsByFacing": views, "blendMode": "normal"}]}}}
            imported.append(identity)

    folder.mkdir(parents=True, exist_ok=True)
    binding_path.write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
    assets_path.write_text(json.dumps(list(assets.values()), separators=(",", ":")) + "\n")
    return tuple(imported)


def import_hands(source: Path, *, repo: Path = ROOT) -> None:
    """Copy only the selected Special1 casting sheets; retain other originals privately."""
    hands = json.loads((source / "hands.json").read_text())
    folder = repo / "game/data/support_conditions"
    path = folder / "bindings.json"
    bindings = json.loads(path.read_text()) if path.exists() else {"resources": {}, "spells": {}}
    for name, row in hands.items():
        relative = row["clips"]["Special1"]["file"]
        destination = MEDIA / relative
        (repo / destination).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, repo / destination)
        bindings["resources"][f"/support-conditions/{name}/cast.png"] = destination.as_posix()
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bindings, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument("--hands", action="store_true")
    args = parser.parse_args()
    for selected in args.group:
        print(f"{selected}: installed {len(import_group(args.source, selected))} media layers")
    if args.hands:
        import_hands(args.source)
        print("Installed isolated Special1 hand media")
