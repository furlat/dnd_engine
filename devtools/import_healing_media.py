"""Copy recipient healing atlases, preserving camera, crop and ground registration.

Offline storage conversion only. Studio and condition recipes own behavior.
"""

import argparse
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
MEDIA = Path("game/assets/healing_spells")
DIRECTIONS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")
SPELLS = ("aid", "lesser_restoration", "greater_restoration", "heal", "mass_cure_wounds", "mass_heal")


def import_bundle(source: Path, *, manifest: str = "media-four-camera.json", repo: Path = ROOT) -> tuple[str, ...]:
    catalog = json.loads((source / manifest).read_text())
    if "aid" in catalog:
        lifecycle = json.loads((source / "aid-lifecycle.json").read_text())
        catalog["aid_hold"] = {**catalog["aid"], **lifecycle["phases"]["hold"]}
    folder = repo / "game/data/healing_spells"
    binding_path = folder / "bindings.json"
    bindings = json.loads(binding_path.read_text()) if binding_path.exists() else {"resources": {}, "spells": {}}
    assets, storage, copied = [], {}, set()

    def copy(relative: str) -> str:
        destination = MEDIA / relative
        if destination not in copied:
            (repo / destination).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, repo / destination)
            copied.add(destination)
        return destination.as_posix()

    for name, row in catalog.items():
        if name not in SPELLS and name != "aid_hold":
            continue
        # Do not silently manufacture three absent camera views.
        if set(row["cameras"]) != {"0", "1", "2", "3"}:
            raise ValueError(f"{name}: all four native camera banks are required")
        cell, fps, count = row["cell"], row["fps"], row["frames"]
        pivot = row["pivot"]
        for side in ("back", "front"):
            identity = f"healing.{name}.{side}"
            views = {}
            for q in range(4):
                layer = row["cameras"][str(q)]["layers"][side]
                if len(layer["frames"]) != count:
                    raise ValueError(f"{name}/q{q}/{side}: incomplete frame sequence")
                parts = [[] if frame is None else [{
                    "file": copy(layer["pages"][frame["page"]]),
                    "rect": frame["source"], "offset": frame["offset"],
                }] for frame in layer["frames"]]
                # Fixed E world basis selects E/S/W/N for q0/q1/q2/q3.
                # Intermediate body-facing rows are unused by these recipes.
                views[DIRECTIONS[q * 2]] = parts
                views[DIRECTIONS[q * 2 + 1]] = parts
            assets.append({
                "assetId": identity, "displayName": identity, "kind": "projectile",
                "sheet": f"/healing-spells/{name}/{side}.png",
                "frame": {"width": cell, "height": cell, "rows": 8, "cols": count},
                "fps": fps, "rowOrder": list(DIRECTIONS),
                "phases": {"impact": {"start": 0, "frames": count, "fps": fps, "loop": name == "aid_hold"}},
                "anchor": {"x": pivot[0] / cell, "y": pivot[1] / cell}, "defaultScale": .5,
                "palettePreview": {"colors": [int(color, 16) for color in row["palette"]]},
            })
            storage[identity] = {"phases": {"impact": {"layers": [
                {"partsByFacing": views, "blendMode": "normal"}]}}}
        if name in SPELLS:
            bindings["resources"][f"/healing-spells/{name}/cast.png"] = copy(f"actors/{name}/Special1-glow.png")

    bindings["projectileStorage"] = storage
    folder.mkdir(parents=True, exist_ok=True)
    binding_path.write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
    (folder / "projectile-assets.json").write_text(json.dumps(assets, separators=(",", ":")) + "\n")
    return tuple(storage)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", default="media-four-camera.json")
    args = parser.parse_args()
    print(f"Installed {len(import_bundle(args.source, manifest=args.manifest))} recipient media layers.")
