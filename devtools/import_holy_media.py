"""Install the accepted holy component atlases without changing pixels or recipes."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image

from devtools.import_registered_media import DIRECTIONS
from devtools.media_delivery import contained_media_path, install_verified_payloads
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage

ROOT = Path(__file__).resolve().parents[1]


def import_holy_media(source: Path, *, preserved: Path, production: Path, repo: Path = ROOT) -> dict:
    manifests = {name: json.loads((source / name / "manifest.json").read_text())
        for name in (".", "guardian-of-faith", "heroes-feast")}
    if (manifests["."]["revision"] != "relaxed-flow-v5"
            or manifests["guardian-of-faith"]["approvedRevision"] != "lean-horned-v3"
            or manifests["heroes-feast"]["revision"] != "spectral-material-v2"):
        raise ValueError("Expected the three approved holy revisions")
    payloads = []
    for row in manifests["."]["components"]:
        if row["name"] != "contact-radiant":
            payloads.append((row["path"], "game/assets/holy_media/"+row["path"], row["sha256"]))
    for row in manifests["guardian-of-faith"]["assets"]:
        relative = "guardian-of-faith/"+row["path"]
        payloads.append((relative, "game/assets/holy_media/"+relative, row["sha256"]))
    for row in manifests["heroes-feast"]["assets"]:
        if row["file"].startswith("base-"):
            continue  # Empty loader compatibility images are not artwork.
        relative = "heroes-feast/assets/"+row["file"]
        payloads.append((relative, "game/assets/holy_media/"+relative, row["sha256"]))
    # Preserve the complete original authoring package separately from selection.
    for original in source.rglob("*"):
        if not original.is_file():
            continue
        target = contained_media_path(preserved, original.relative_to(source).as_posix())
        if target.exists() and target.read_bytes() != original.read_bytes():
            raise ValueError(f"Preserved holy source differs: {target}")
    for original in source.rglob("*"):
        if original.is_file():
            target = contained_media_path(preserved, original.relative_to(source).as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copyfile(original, target)
    assets, storage = [], {}

    def register(identity: str, size: tuple[int, int], pivot: tuple[float, float], count: int,
                 paths: tuple[str, ...], *, columns: int, start: int = 0,
                 heading_rows: bool = False, loop: bool = True, directed_heading: bool = False) -> None:
        views = {}
        width, height = size
        for row, facing in enumerate(DIRECTIONS):
            bank = (-row-1) % 8 if directed_heading else row
            path = paths[bank if len(paths) == 8 else row//2 if len(paths) == 4 else 0]
            with Image.open(source / path) as image:
                if image.mode != "RGBA":
                    raise ValueError("Holy banks require original straight RGBA")
                expected = ((columns*width, 8*height) if heading_rows else
                    (columns*width, ((start+count+columns-1)//columns)*height))
                if image.size != expected:
                    raise ValueError(f"Unexpected holy bank dimensions: {path}: {image.size}")
            views[facing] = [[{"file": "game/assets/holy_media/"+path,
                "rect": [((start+frame)%columns)*width,
                    row*height if heading_rows else ((start+frame)//columns)*height, width, height],
                "offset": [0, 0]}] for frame in range(count)]
        asset = {"assetId": identity, "displayName": identity, "sheet": "/"+identity+".png", "frame": {"width": width, "height": height,
                "rows": 8, "cols": count}, "fps": 32, "rowOrder": list(DIRECTIONS),
            "phases": {"impact": {"start": 0, "frames": count, "fps": 32, "loop": loop}},
            "anchor": {"x": pivot[0]/width, "y": pivot[1]/height}, "defaultScale": 1,
            "palettePreview": {"colors": [0xffefd0, 0x4ec9a6]}}
        selected = {"phases": {"impact": {"layers": [{"partsByFacing": views, "blendMode": "normal"}]}}}
        AuthoredProjectileAsset.model_validate_json(json.dumps(asset))
        ProjectileStorage.model_validate_json(json.dumps(selected))
        assets.append(asset)
        storage[identity] = selected

    for variant in ("radiant", "necrotic"):
        register("holy.spirit."+variant, (160,160), (80,80), 16,
            ("assets/"+variant+".png",), columns=16, heading_rows=True)
    register("holy.contact.necrotic", (160,224), (80,150), 48,
        ("assets/contact-necrotic.png",), columns=8, loop=False)
    paths = tuple(f"guardian-of-faith/assets/guardian-{index}.png" for index in range(8))
    # The original shared bank contains 64 idle and 32 strike samples.
    register("holy.guardian", (224,288), (112,191), 96, paths, columns=8, loop=False, directed_heading=True)
    register("holy.feast", (384,320), (192,218.5), 64,
        tuple(f"heroes-feast/assets/feast-{index}.png" for index in range(4)), columns=8)
    files = install_verified_payloads(source, tuple(payloads), preserved=preserved,
        production=production, repo=repo)
    folder = repo / "game/data/holy_media"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "bindings.json"
    bindings = json.loads(path.read_text()) if path.exists() else {"resources": {}, "spells": {}, "projectileStorage": {}}
    bindings["projectileStorage"].update(storage)
    path.write_text(json.dumps(bindings, separators=(",", ":"))+"\n")
    (folder / "projectile-assets.json").write_text(json.dumps(assets, separators=(",", ":"))+"\n")
    blade = source / "guardian-of-faith/assets/blade-motion.json"
    (folder / "blade-motion.json").write_bytes(blade.read_bytes())
    receipt = {"source": str(source), "preserved": str(preserved), "files": files,
        "revisions": ["relaxed-flow-v5", "lean-horned-v3", "spectral-material-v2"],
        "identities": [row["assetId"] for row in assets],
        "shared_radiant_contact": "holy.contact.radiant from weather_solar_media/contacts-source.json",
        "blade_motion_sha256": hashlib.sha256(blade.read_bytes()).hexdigest(),
        "manifest_sha256": {name: hashlib.sha256((source/name/"manifest.json").read_bytes()).hexdigest()
            for name in manifests}}
    (folder / "source.json").write_text(json.dumps(receipt, indent=2)+"\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "preserved", "production"):
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    receipt = import_holy_media(args.source, preserved=args.preserved, production=args.production)
    print(f"Installed {len(receipt['identities'])} records / {len(receipt['files'])} original atlases")
