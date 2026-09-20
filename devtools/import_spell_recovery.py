"""Import selected spell media and packaging, leaving authored recipes untouched.

The approved color revision is a required packaging input. See the bundle README.
"""

import argparse
import json
from pathlib import Path
import shutil

from devtools.import_spell_color_revision import import_revision


REPO = Path(__file__).resolve().parents[1]
MEDIA = Path("game/assets/spell_recovery")
POINTS = ("acid_splash", "guiding_bolt", "eldritch_blast")


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def copy_frames(source: Path, relative: Path, directions, count: int, *, repo: Path) -> None:
    for direction in directions:
        destination = repo / relative / direction
        destination.mkdir(parents=True, exist_ok=True)
        for frame in range(count):
            name = f"{frame:02}.png"
            shutil.copyfile(source / direction / name, destination / name)


def asset(identity: str, name: str, cell: int, directions, phases, colors):
    return {
        "assetId": identity, "displayName": name, "kind": "projectile",
        "sheet": f"/authored-vfx/spell-recovery/{identity}",
        "frame": {"width": cell, "height": cell, "rows": 8,
                  "cols": max(p["start"] + p["frames"] for p in phases.values())},
        "fps": 24, "rowOrder": directions, "phases": phases,
        "anchor": {"x": 0.5, "y": 0.5}, "defaultScale": 0.5,
        "palettePreview": {"colors": colors},
    }


def import_bundle(vfx_root: Path, neuroclient_app: Path, color_revision: Path, *, repo: Path = REPO) -> None:
    # Read the chosen delivery before writing: ordinary import always includes it.
    read(color_revision / "delivery.json")
    data = repo / "game/data/spell_recovery"
    bindings = read(data / "bindings.json")
    existing_assets = {row["assetId"]: row for row in read(data / "projectile-assets.json")}
    release = vfx_root / "spell-recovery/release"
    manifests = {row["id"]: row for row in read(release / "manifest.json")}
    for name in POINTS:
        source = manifests[name]
        identity = f"recovered.{name}.dense.v1"
        phases = {key: {field: value[field] for field in ("start", "frames", "fps", "loop")}
                  for key, value in source["phases"].items()}
        storage = {}
        for key, value in phases.items():
            local = MEDIA / name / key
            copy_frames(release / name / key, local, source["rows"], value["frames"], repo=repo)
            storage[key] = {"layers": [
                {"pattern": (local / "{direction}/{frame:02}.png").as_posix(), "blendMode": "add"}]}
        bindings["projectileStorage"][identity] = {"phases": storage}
        record = existing_assets[identity]
        record.update(frame={"width": source["cell"], "height": source["cell"], "rows": 8,
                             "cols": max(p["start"] + p["frames"] for p in phases.values())},
                      rowOrder=source["rows"], phases=phases)
    magic = Path("spritesheets/Magic3/Special1.png")
    destination = repo / MEDIA / magic
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(neuroclient_app / "public" / magic, destination)
    bindings["resources"]["/" + magic.as_posix()] = (MEDIA / magic).as_posix()

    fire_root = vfx_root / "library-selection/release"
    fire = read(fire_root / "shared-fireball-20ft.json")
    for key in ("travel", "impact"):
        raw = fire[key]
        identity = fire["assetId"] + ".travel" if key == "travel" else fire["assetId"]
        phase = {"start": 0, "frames": raw["frames"], "fps": raw["fps"], "loop": raw["loop"]}
        record = existing_assets[identity]
        record.update(frame={"width": raw["cell"], "height": raw["cell"], "rows": 8, "cols": raw["frames"]},
                      rowOrder=fire["rowOrder"], phases={key: phase})
        layers = []
        sources = [("fireball_b", "add")] if key == "travel" else [("fireball_smoke", "normal"), ("fireball_explosion", "add")]
        for source_name, blend in sources:
            local = MEDIA / source_name
            copy_frames(fire_root / source_name, local, fire["rowOrder"], raw["frames"], repo=repo)
            layers.append({"pattern": (local / "{direction}/{frame:02}.png").as_posix(), "blendMode": blend})
        bindings["projectileStorage"][identity] = {"phases": {key: {"layers": layers}}}
    for name, value in (("bindings.json", bindings), ("projectile-assets.json", list(existing_assets.values()))):
        (data / name).write_text(json.dumps(value, indent=2) + "\n")
    import_revision(color_revision, repo=repo)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vfx-root", type=Path, required=True)
    parser.add_argument("--neuroclient-app", type=Path, required=True)
    parser.add_argument("--color-revision", type=Path, required=True,
                        help="Approved revision delivery directory; prevents restoring the original colors.")
    args = parser.parse_args()
    import_bundle(args.vfx_root, args.neuroclient_app, args.color_revision)
    print("Imported selected spell media with the chosen color revision; authored recipes retained.")


if __name__ == "__main__":
    main()
