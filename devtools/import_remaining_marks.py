"""Install the seven delivered condition glyphs through existing media storage."""

import argparse
import json
from pathlib import Path
import shutil

from PIL import Image

from devtools.import_registered_media import DIRECTIONS
from devtools.media_delivery import install_verified_payloads
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage

ROOT = Path(__file__).resolve().parents[1]
MARKS = ("mark_target", "leadership", "field_focus", "life_drain", "no_reactions", "guiding_mark", "anti_heal")


def import_marks(source: Path, *, preserved: Path, production: Path, repo: Path = ROOT) -> None:
    manifest = json.loads((source / "remaining-delivery.json").read_text())
    if manifest["revision"] != "remaining-native-v4":
        raise ValueError("Expected the reviewed remaining-native-v4 delivery")
    assets, storage, payloads = {}, {}, []
    for name in MARKS:
        row = manifest["newComponents"][name]
        width, height = row["cell"]
        count, columns = row["count"], row["columns"]
        with Image.open(source / row["file"]) as image:
            if image.mode != "RGBA" or image.size != (width * columns, height * ((count + columns - 1) // columns)):
                raise ValueError(f"Unexpected glyph format: {name}")
        runtime = "game/assets/remaining_marks/" + Path(row["file"]).name
        payloads.append((row["file"], runtime, row["sha256"]))
        identity = "condition.mark." + name
        assets[identity] = {"assetId": identity, "displayName": name, "sheet": "/remaining-marks/" + name + ".png",
            "frame": {"width": width, "height": height, "rows": 8, "cols": count},
            "fps": row["fps"], "rowOrder": list(DIRECTIONS),
            "phases": {"impact": {"start": 0, "frames": count, "fps": row["fps"], "loop": True}},
            "anchor": {"x": row["pivot"][0] / width, "y": row["pivot"][1] / height},
            "defaultScale": .5, "palettePreview": {"colors": [0xffffff]}}
        parts = [[{"file": runtime, "rect": [(frame % columns)*width, (frame // columns)*height, width, height],
                   "offset": [0, 0]}] for frame in range(count)]
        storage[identity] = {"phases": {"impact": {"layers": [{"parts": parts, "blendMode": "normal"}]}}}
        AuthoredProjectileAsset.model_validate_json(json.dumps(assets[identity]))
        ProjectileStorage.model_validate_json(json.dumps(storage[identity]))
    # Preserve source contracts before touching installed registrations.
    documents = ("REMAINING_HANDOFF.md", "remaining-delivery.json", "remaining-marks.json", "remaining-assets-validation.json")
    for name in documents:
        target = preserved / name
        if target.exists() and target.read_bytes() != (source / name).read_bytes():
            raise ValueError(f"Archived source changed: {name}")
    files = install_verified_payloads(source, tuple(payloads), preserved=preserved, production=production, repo=repo)
    for name in documents:
        shutil.copyfile(source / name, preserved / name)
    bundle = repo / "game/data/necrotic_media"
    bindings_path, assets_path = bundle / "bindings.json", bundle / "projectile-assets.json"
    bindings = json.loads(bindings_path.read_text())
    bindings["projectileStorage"].update(storage)
    previous = {row["assetId"]: row for row in json.loads(assets_path.read_text())}
    previous.update(assets)
    bindings_path.write_text(json.dumps(bindings, indent=2) + "\n")
    assets_path.write_text(json.dumps(list(previous.values()), separators=(",", ":")) + "\n")
    (preserved / "installed-marks.json").write_text(json.dumps(files, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "preserved", "production"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    import_marks(args.source, preserved=args.preserved, production=args.production)
