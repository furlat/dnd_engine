"""Package selected support exports without authoring spell or condition behavior."""

import argparse
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
SPELLS = frozenset(("cure_wounds", "healing_word", "prayer_of_healing", "guidance",
                    "resistance", "shield_of_faith", "light", "thaumaturgy"))
WEAPON_CHARGE_SHEETS = ("Melee3-Attack6-charge.png", "Ranged1-Attack3-charge.png")


def _read(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def import_bundle(source: Path, *, repo: Path = ROOT) -> None:
    manifest = json.loads((source / "manifest.json").read_text())
    folder = repo / "game/data/support_spells"
    bindings = _read(folder / "bindings.json", {"resources": {}, "spells": {}})
    assets = {row["assetId"]: row for row in _read(folder / "projectile-assets.json", [])}
    resources = _read(repo / "game/data/assets.json", {"schema_version": 1, "resources": {}})
    conditions = _read(repo / "game/data/condition-media.json",
                       {"schema": "dnd.conditionLayerMedia", "version": 1, "layers": {}})
    storage = bindings.setdefault("projectileStorage", {})

    def copy(relative: str) -> Path:
        destination = Path("game/assets/support_spells") / relative
        (repo / destination).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, repo / destination)
        return destination

    for spell in manifest["spells"]:
        name = spell["id"]
        if name not in SPELLS:
            continue
        for depth, phase in spell["phases"].items():
            identity = f"support.{name}.{depth}"
            cell = phase["cell"]
            anchor = {"x": phase["pivot"][0] / cell, "y": phase["pivot"][1] / cell}
            assets[identity] = {
                "assetId": identity, "displayName": identity, "kind": "projectile",
                "sheet": f"/support-spells/{name}/{depth}.png",
                "frame": {"width": cell, "height": cell, "rows": 8, "cols": phase["frames"]},
                "fps": phase["fps"], "rowOrder": spell["directions"],
                "phases": {"impact": {"start": 0, "frames": phase["frames"],
                                      "fps": phase["fps"], "loop": False}},
                "anchor": anchor, "anchorsByFacing": {facing: anchor for facing in spell["directions"]},
                "defaultScale": .5,
                "palettePreview": {"colors": [r * 65536 + g * 256 + b
                    for r, g, b in spell["palette"]["colors"]]},
            }
            pages = {facing: [{"file": copy(page["file"]).as_posix(),
                              **{key: page[key] for key in ("firstFrame", "frameCount", "columns")}}
                             for page in entries] for facing, entries in phase["pages"].items()}
            storage[identity] = {"phases": {"impact": {"layers": [{"pages": pages, "blendMode": "normal"}]}}}
        bindings["resources"][f"/support-spells/{name}/cast.png"] = copy(spell["cast"]["sourceLayer"]).as_posix()
        pose = spell.get("conditionPose")
        if pose is not None:
            for depth, facings in pose["layers"].items():
                identity = f"support.{name}.{depth}"
                images = {}
                for facing, file in facings.items():
                    image_id = f"{identity}.{facing}"
                    images[facing] = image_id
                    resources["resources"][image_id] = {
                        "path": copy(file).relative_to("game/assets").as_posix(),
                        "native_size": [pose["cell"], pose["cell"]],
                        "pivot": pose["pivot"], "scale": 1,
                    }
                conditions["layers"][identity] = {"category": name, "animation": "static",
                                                  "images_by_facing": images}
    for sheet in WEAPON_CHARGE_SHEETS:
        bindings["resources"][f"/support-spells/true_strike/{sheet}"] = copy(f"weapon-charge/{sheet}").as_posix()
    _write(folder / "bindings.json", bindings)
    _write(folder / "projectile-assets.json", list(assets.values()))
    _write(repo / "game/data/assets.json", resources)
    _write(repo / "game/data/condition-media.json", conditions)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    import_bundle(parser.parse_args().source)


if __name__ == "__main__":
    main()
