"""Copy approved projectile color revisions without replacing current recipes."""

import argparse
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    delivery = json.loads((args.source / "delivery.json").read_text())
    palette = json.loads((args.source / "palettes.json").read_text())
    selected = {"eldritch_blast", "fireball_b", "fireball_explosion", "fireball_smoke"}
    copied = 0
    for row in delivery["media"]:
        path = Path(row["path"])
        if path.parts[:3] != ("game", "assets", "spell_recovery") or path.parts[3] not in selected:
            continue
        destination = ROOT / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.source / delivery["assetRoot"] / path, destination)
        copied += 1
    assets_path = ROOT / "game/data/spell_recovery/projectile-assets.json"
    assets = json.loads(assets_path.read_text())
    for asset in assets:
        spell = "eldritch_blast" if "eldritch" in asset["assetId"] else "fireball" if "fireball" in asset["assetId"] else None
        if spell is not None:
            asset["palettePreview"]["colors"] = [r*65536+g*256+b for r,g,b in palette[spell]["revised"]]
    assets_path.write_text(json.dumps(assets,indent=2)+"\n")
    print(f"Copied {copied} approved color-only phase frames; current recipes retained.")


if __name__ == "__main__":
    main()
