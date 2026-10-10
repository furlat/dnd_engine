"""Install selected accepted utility atlases with their original trimmed pivots."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image
from pydantic import TypeAdapter

from devtools.import_registered_media import DIRECTIONS
from devtools.media_delivery import install_verified_payloads
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage

ROOT = Path(__file__).resolve().parents[1]


def import_cast_glows(source: Path, hand_source: Path, *, preserved: Path,
                     production: Path, repo: Path = ROOT) -> dict:
    """Bake the delivered source-atop hand color/fade at original pose frames.

    Only isolated existing glow pixels are changed. Runtime uses the ordinary
    literal actor layer with the source's screen blend; recipes stay untouched.
    """
    originals = {"hand-glow.png": hand_source.read_bytes(),
                 "review.js": (source / "review.js").read_bytes()}
    with Image.open(hand_source) as sheet:
        if sheet.mode != "RGBA" or sheet.size != (1920, 1024):
            raise ValueError("Expected original Attack5 hand glow, fifteen frames and eight rows")
        original_alpha = sheet.getchannel("A")
    for name, content in originals.items():
        path = preserved / name
        if path.exists() and path.read_bytes() != content:
            raise ValueError(f"Preserved utility cast source differs: {name}")
    bundle = repo / "game/data/utility_media"
    bindings = json.loads((bundle / "bindings.json").read_text())
    for program in ("antimagic", "telekinesis"):
        key = f"/utility/{program}/Attack5-hands.png"
        path = f"game/assets/utility_media/{program}-Attack5-hands.png"
        if key in bindings["resources"] and bindings["resources"][key] != path:
            raise ValueError(f"Conflicting utility hand resource: {key}")
        bindings["resources"][key] = path
    derived = preserved / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    for name, content in originals.items():
        (preserved / name).write_bytes(content)
    payloads = []
    for program, color in (("antimagic", (156, 133, 215)), ("telekinesis", (121, 205, 234))):
        image = Image.new("RGBA", (1920, 1024), (*color, 0))
        alpha = original_alpha.copy()
        for frame in range(15):
            u = max(0., min(1., (frame / 12 - .75) / .5))
            opacity = .65 * (1 - u * u * (3 - 2 * u))
            box = (frame * 128, 0, (frame + 1) * 128, 1024)
            alpha.paste(original_alpha.crop(box).point([round(value * opacity) for value in range(256)]), box)
        image.putalpha(alpha)
        name = f"{program}-Attack5-hands.png"
        image.save(derived / name)
        payloads.append((name, f"game/assets/utility_media/{name}",
                         hashlib.sha256((derived / name).read_bytes()).hexdigest()))
    files = install_verified_payloads(derived, tuple(payloads), preserved=derived,
        production=production, repo=repo)
    (bundle / "bindings.json").write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
    receipt = {"source": str(source), "hand_source": str(hand_source), "preserved": str(preserved),
        "originals": {name: hashlib.sha256(content).hexdigest() for name, content in originals.items()},
        "files": files, "adaptation": "Original source-atop colors and .65*(1-smooth(.75,1.25,t)) opacity sampled at fifteen original 12fps Attack5 frames; runtime screen blend."}
    (bundle / "cast-hands-source.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def import_utility_media(source: Path, *, preserved: Path, production: Path,
                         repo: Path = ROOT, program: str = "telekinesis") -> dict:
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest["acceptedReviewRevision"] != "grounded-layering-v2" or manifest["fps"] != 32 or manifest["actorFloorBaked"]:
        raise ValueError("Expected the accepted isolated utility delivery")
    if program not in ("telekinesis", "antimagic"):
        raise ValueError("Select telekinesis or antimagic")
    metadata = ("manifest.json", "HANDOFF.md", "approval.json", "review.js")
    for name in metadata:
        target = preserved / name
        if target.exists() and target.read_bytes() != (source / name).read_bytes():
            raise ValueError(f"Archived utility metadata differs: {name}")
    selected = {key: row for key, row in manifest["banks"].items()
        if key.startswith("hand-" if program == "telekinesis" else "antimagic-")}
    expected = ({f"hand-{phase}-{camera}-{side}" for phase in ("grab", "hold", "release")
        for camera in range(4) for side in ("back", "front")} if program == "telekinesis"
        else {"antimagic-back", "antimagic-front"})
    if set(selected) != expected:
        raise ValueError("Utility delivery is missing a selected phase/camera/layer")
    folder = repo / "game/data/utility_media"
    path = folder / "bindings.json"
    bindings = json.loads(path.read_text()) if path.exists() else {"resources": {}, "spells": {}, "projectileStorage": {}}
    path = folder / "projectile-assets.json"
    assets = {row["assetId"]: row for row in json.loads(path.read_text())} if path.exists() else {}
    identities = []
    phases = ("grab", "hold", "release") if program == "telekinesis" else ("hold",)
    for phase in phases:
        count = 64 if phase == "hold" else 32
        for side in ("back", "front"):
            identity = f"utility.{program}.{phase}.{side}"
            views = {}
            pivot_y = 400 + next(iter(selected.values()))["pivot"][1] % 1
            for camera in range(4):
                row = selected[f"hand-{phase}-{camera}-{side}" if program == "telekinesis" else f"antimagic-{side}"]
                width, height = row["cell"]
                if row["frames"] != count or row["columns"] != 8 or min(width, height) <= 0:
                    raise ValueError("Unexpected utility atlas address layout")
                offset_y = pivot_y - row["pivot"][1]
                if abs(offset_y - round(offset_y)) > 1e-6:
                    raise ValueError("Camera banks require one common subpixel registration")
                parts = [[{"file": "game/assets/utility_media/" + row["file"],
                    "rect": [(frame % 8) * width, (frame // 8) * height, width, height],
                    "offset": [round(256 - row["pivot"][0]), round(offset_y)]}]
                    for frame in range(count)]
                views[DIRECTIONS[2 * camera]] = parts
                views[DIRECTIONS[2 * camera + 1]] = parts
            asset = {"assetId": identity, "displayName": identity, "sheet": f"/utility/{program}/{phase}/{side}.png",
                "frame": {"width": 512, "height": 512, "rows": 8, "cols": count},
                "fps": 32, "rowOrder": list(DIRECTIONS),
                "phases": {"impact": {"start": 0, "frames": count, "fps": 32, "loop": phase == "hold"}},
                "anchor": {"x": .5, "y": pivot_y / 512}, "defaultScale": 1,
                "palettePreview": {"colors": [0xd1e9e7, 0x79cdea, 0x3882a2]}}
            storage = {"phases": {"impact": {"layers": [{"partsByFacing": views, "blendMode": "normal"}]}}}
            TypeAdapter(AuthoredProjectileAsset).validate_json(json.dumps(asset))
            TypeAdapter(ProjectileStorage).validate_json(json.dumps(storage))
            if identity in assets and assets[identity] != asset or identity in bindings["projectileStorage"] and bindings["projectileStorage"][identity] != storage:
                raise ValueError(f"Conflicting selected utility registration: {identity}")
            assets[identity] = asset
            bindings["projectileStorage"][identity] = storage
            identities.append(identity)
    files = install_verified_payloads(source, tuple((row["file"], "game/assets/utility_media/" + row["file"], row["sha256"])
        for row in selected.values()), preserved=preserved, production=production, repo=repo)
    for name in metadata:
        shutil.copyfile(source / name, preserved / name)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "bindings.json").write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
    (folder / "projectile-assets.json").write_text(json.dumps(list(assets.values()), separators=(",", ":")) + "\n")
    receipt = {"source": str(source), "preserved": str(preserved), "files": files, "identities": identities,
        "manifest_sha256": hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest()}
    (folder / f"{program}-source.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--preserved", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--program", choices=("telekinesis", "antimagic"), default="telekinesis")
    args = parser.parse_args()
    receipt = import_utility_media(args.source, preserved=args.preserved, production=args.production, program=args.program)
    print(f"Installed {len(receipt['identities'])} records / {len(receipt['files'])} unchanged utility atlases")
