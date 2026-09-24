"""Copy approved spell pages and registration metadata; never author behavior."""

import argparse
import json
from pathlib import Path
import shutil

from devtools.import_spell_recovery import asset
from devtools.media_delivery import owns_selected_media


ROOT = Path(__file__).resolve().parents[1]
MEDIA = Path("game/assets/ice_spells")


def read(path: Path):
    return json.loads(path.read_text())


def import_bundle(source: Path, *, repo: Path = ROOT) -> None:
    manifest = read(source / "manifest.json")
    destination = repo / "game/data/ice_spells"
    bindings = read(destination / "bindings.json")
    assets = {row["assetId"]: row for row in read(destination / "projectile-assets.json")}
    for spell in manifest["spells"]:
        name = spell["id"]
        colors = sorted(spell["palette"]["colors"], key=lambda rgb: sum(a*b for a,b in zip(rgb, (.2126,.7152,.0722))))
        encoded = [r*65536+g*256+b for r,g,b in colors]
        for phase_name in ("travel", "impact"):
            if phase_name not in spell["phases"]:
                continue
            phase = spell["phases"][phase_name]
            size = phase.get("cell", spell["cell"])
            identity = f"ice.v8.{name}.{phase_name}"
            if not owns_selected_media(bindings["projectileStorage"], identity, MEDIA.as_posix()):
                continue
            layers = [phase_name]
            if name == "ray_of_frost" and phase_name == "travel":
                layers.append("travelIce")
            if name == "ice_knife" and phase_name == "impact":
                layers.append("impactLight")
            record = asset(identity, name.replace("_", " ").title()+" · "+phase_name, size,
                spell["directions"], {phase_name:{"start":0,"frames":phase["frames"],"fps":144,"loop":phase_name=="travel"}}, encoded)
            record["anchorsByFacing"] = {f:{"x":xy[0]/size,"y":xy[1]/size}
                                          for f,xy in spell["registration"][phase_name].items()}
            assets[identity] = record
            storage = []
            for layer_name in layers:
                raw = spell["phases"][layer_name]
                pages = {}
                for direction, entries in raw["directions"].items():
                    pages[direction] = []
                    for page in entries:
                        path = MEDIA / page["file"]
                        target = repo / path
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source / page["file"], target)
                        pages[direction].append({"file":path.as_posix(), **{key:page[key] for key in ("firstFrame","frameCount","columns")}})
                storage.append({"pages":pages,"blendMode":"add" if raw["blend"]=="add" else "normal", "gain":raw.get("gain",1)})
            bindings["projectileStorage"][identity] = {"phases":{phase_name:{"layers":storage}}}
    # Existing authored noise resource: copy its source without changing its owner or treatment.
    noise_path = read(repo / "game/data/spell_recovery/bindings.json")["resources"]["/spell-palettes/source-hand-noise.png"]
    target = repo / noise_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "source-hand-noise.png", target)
    for name, value in (("bindings.json", bindings), ("projectile-assets.json", list(assets.values()))):
        (destination / name).write_text(json.dumps(value, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    import_bundle(args.source)
    print("Imported ice spell pages and registration; authored spells and child effects retained.")


if __name__ == "__main__":
    main()
