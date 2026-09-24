"""Package accepted golden shell camera banks and collision response unchanged."""

import argparse
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
DIRECTIONS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")


def import_bundle(source: Path, repo: Path = ROOT) -> None:
    catalog = json.loads((source / "media.json").read_text())
    folder = repo / "game/data/globe_media"
    folder.mkdir(parents=True, exist_ok=True)
    bindings_path = folder / "bindings.json"
    bindings = json.loads(bindings_path.read_text()) if bindings_path.exists() else {"resources": {}, "spells": {}}
    assets_path = folder / "projectile-assets.json"
    assets = {row["assetId"]: row for row in json.loads(assets_path.read_text())} if assets_path.exists() else {}
    storage, copied = bindings.setdefault("projectileStorage", {}), set()
    for name, first, count, loop in (("apply", 0, 96, False), ("hold", 96, 576, True),
                                     ("response", 41, 278, False)):
        for side in ("back", "front"):
            asset_id = f"globe.{name}.{side}"
            views = {}
            for q in range(4):
                row = catalog[f"{'physics' if name == 'response' else 'globe'}-q{q}-{side}"]
                parts = []
                for frame in row["frames"][first:first + count]:
                    relative = row["pages"][frame["page"]]
                    destination = Path("game/assets/globe_media") / relative
                    if destination not in copied:
                        (repo / destination).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source / relative, repo / destination)
                        copied.add(destination)
                    parts.append([{"file": destination.as_posix(), "rect": frame["source"],
                        "offset": [224 + frame["offset"][0], 224 + frame["offset"][1]]}])
                # The spatial drawer uses E as fixed-world shell basis. Odd
                # rows share that camera; waves select quarter turns only.
                views[DIRECTIONS[q * 2]] = parts
                views[DIRECTIONS[q * 2 + 1]] = parts
            storage[asset_id] = {"phases": {"impact": {"layers": [
                {"partsByFacing": views, "blendMode": "normal"}]}}}
            assets[asset_id] = {"assetId": asset_id, "displayName": asset_id, "kind": "projectile",
                "sheet": f"/globe/{name}/{side}", "frame": {"width": 448, "height": 448, "rows": 8, "cols": count},
                "fps": 144, "rowOrder": list(DIRECTIONS),
                "phases": {"impact": {"start": 0, "frames": count, "fps": 144, "loop": loop}},
                "anchor": {"x": .5, "y": .5}, "defaultScale": .5,
                "palettePreview": {"colors": [0xffe49c, 0xd29b38, 0x6c451a]}}
    bindings["projectileStorage"] = storage
    bindings_path.write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
    assets_path.write_text(json.dumps(list(assets.values()), separators=(",", ":")) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    import_bundle(args.source)
    print("Installed golden Globe apply, hold and contact windows in four camera banks.")
