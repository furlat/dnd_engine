"""Copy approved projectile color revisions without replacing current recipes."""

import argparse
import json
from pathlib import Path
import shutil

from devtools.media_delivery import owns_selected_media


ROOT = Path(__file__).resolve().parents[1]
REVISED_ASSETS = {
    "recovered.eldritch_blast.dense.v1": "eldritch_blast",
    "shared.fireball.20ft-ground.smoke.v3.travel": "fireball",
    "shared.fireball.20ft-ground.smoke.v3": "fireball",
}


def import_revision(source: Path, *, repo: Path = ROOT) -> int:
    delivery = json.loads((source / "delivery.json").read_text())
    palette = json.loads((source / "palettes.json").read_text())
    selected = {"eldritch_blast", "fireball_b", "fireball_explosion", "fireball_smoke"}
    copied = 0
    for row in delivery["media"]:
        path = Path(row["path"])
        if path.parts[:3] != ("game", "assets", "spell_recovery") or path.parts[3] not in selected:
            continue
        destination = repo / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / delivery["assetRoot"] / path, destination)
        copied += 1
    assets_path = repo / "game/data/spell_recovery/projectile-assets.json"
    assets = json.loads(assets_path.read_text())
    bindings = json.loads((assets_path.parent / "bindings.json").read_text())
    for asset in assets:
        spell = REVISED_ASSETS.get(asset["assetId"])
        if spell is not None and owns_selected_media(
                bindings.get("projectileStorage", {}), asset["assetId"], "game/assets/spell_recovery"):
            asset["palettePreview"]["colors"] = [r*65536+g*256+b for r,g,b in palette[spell]["revised"]]
    assets_path.write_text(json.dumps(assets,indent=2)+"\n")
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    copied = import_revision(args.source)
    print(f"Copied {copied} approved color-only phase frames; authored recipes retained.")


if __name__ == "__main__":
    main()
