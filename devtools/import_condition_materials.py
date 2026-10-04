"""Preserve accepted shared-condition material sources and rasterize their exact fetter mark."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import pygame

from devtools.media_delivery import contained_media_path, install_verified_payloads

ROOT = Path(__file__).resolve().parents[1]


def import_materials(source: Path, *, preserved: Path, production: Path, repo: Path = ROOT) -> None:
    originals = [(source / name, contained_media_path(preserved, name)) for name in
        ("HANDOFF.md", "Petrified.gdshader", "condition-material.js", "browser-validation.json")]
    for origin, target in originals:
        content = origin.read_bytes()
        if target.exists() and target.read_bytes() != content:
            raise ValueError(f"Archived condition source differs: {origin.name}")
    texture = "assets/earth-rock-color.png"
    install_verified_payloads(source, ((texture, "game/assets/shared_conditions/earth-rock-color.png",
        hashlib.sha256((source / texture).read_bytes()).hexdigest()),),
        preserved=preserved, production=production, repo=repo)
    for origin, target in originals:
        shutil.copyfile(origin, target)
    # Literal port of drawRestrainedMark: two rounded cuffs, two links, center rivet.
    # This is the delivered vector cue, with no reconstructed creature pixels.
    mark = pygame.Surface((64, 48), pygame.SRCALPHA)
    for x in (-17, 4):
        pygame.draw.rect(mark, "#30434f", (32+x, 13, 13, 21), width=3, border_radius=5)
    for y in (-3, 3):
        pygame.draw.line(mark, "#ffd47c", (27, 24+y), (37, 24+y), width=2)
    pygame.draw.rect(mark, "#ffd47c", (30, 23, 4, 4))
    derived = preserved / "derived"
    derived.mkdir(exist_ok=True)
    glyph = derived / "restrained.png"
    pygame.image.save(mark, glyph)
    install_verified_payloads(derived, (("restrained.png", "game/assets/shared_conditions/restrained.png",
        hashlib.sha256(glyph.read_bytes()).hexdigest()),),
        preserved=derived, production=production, repo=repo)
    bundle = repo / "game/data/necrotic_media"
    bindings = json.loads((bundle / "bindings.json").read_text())
    bindings["resources"]["/shared-conditions/stone.png"] = "game/assets/shared_conditions/earth-rock-color.png"
    identity = "control.restrained.mark"
    bindings["projectileStorage"][identity] = {"phases": {"impact": {"layers": [{"parts": [[{
        "file": "game/assets/shared_conditions/restrained.png", "rect": [0, 0, 64, 48], "offset": [0, 0]}]],
        "blendMode": "normal"}]}}}
    assets = {row["assetId"]: row for row in json.loads((bundle / "projectile-assets.json").read_text())}
    assets[identity] = {"assetId": identity, "displayName": "Restrained fetter cue", "kind": "projectile",
        "sheet": "/shared-conditions/restrained.png", "frame": {"width": 64, "height": 48, "rows": 8, "cols": 1},
        "fps": 32, "rowOrder": ["S", "SE", "E", "NE", "N", "NW", "W", "SW"], "phases": {"impact": {"start": 0, "frames": 1, "fps": 32, "loop": True}},
        "anchor": {"x": .5, "y": 35/48}, "defaultScale": .5, "palettePreview": {"colors": [0x30434f, 0xffd47c]}}
    (bundle / "bindings.json").write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
    (bundle / "projectile-assets.json").write_text(json.dumps(list(assets.values()), separators=(",", ":")) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "preserved", "production"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    import_materials(args.source, preserved=args.preserved, production=args.production)
