"""Bake isolated casting layers and bind exact exported target palettes offline.

The game consumes the resulting recipes and local PNGs; this source package is
never opened during startup or playback. Only the approved spell inventory is
selected. Existing actor, attachment, number and death authoring is retained.
"""

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil

import pygame

from game.animation import resolve_damage
from game.animation_data import load_animation_data
from game.animation_types import PaletteTreatment
from game.spell_palette import recolor_palette


REPO = Path(__file__).resolve().parents[1]
DEFAULT_DRAFTS = (
    "game/data/neuroclient/spell-studio-drafts.materialized.json",
    "game/data/codexfx/spell-studio-drafts.json",
    "game/data/spell_recovery/spell-studio-drafts.json",
)
APPROVED = frozenset(("fire_bolt", "fireball", "magic_missile", "acid_splash",
    "guiding_bolt", "eldritch_blast", "ray_of_frost", "ice_knife", "chill_touch"))


def read(path: Path):
    return json.loads(path.read_text())


def luminance(color: tuple[int, int, int] | list[int]) -> float:
    return sum(a * b for a, b in zip(color, (.2126, .7152, .0722)))


def ordered_palette(colors, *, dark: bool = False) -> tuple[int, ...]:
    selected = (color for color in colors if luminance(color) < 180) if dark else (
        color for color in colors if luminance(color) > 12)
    return tuple((r << 16) | (g << 8) | b for r, g, b in sorted(selected, key=luminance))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vfx-root", type=Path, required=True)
    parser.add_argument("--draft-file", type=Path, action="append", default=[])
    args = parser.parse_args()
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))
    data = load_animation_data()
    root = args.vfx_root
    palettes = {row["spell"].removeprefix("spell."): row["palette"]
                for row in read(root / "color-revision/delivery.json")["coverage"] if "palette" in row}
    palettes.update({name: row["revised"] for name, row in read(root / "color-revision/palettes.json").items()})
    ice = root / "ice-spells/production-v8"
    palettes.update({row["id"]: row["palette"]["colors"] for row in read(ice / "manifest.json")["spells"]})
    missile = data.drafts["spell.magic_missile"].projectile
    assert missile is not None and missile.sprite is not None
    palettes["magic_missile"] = [((c >> 16) & 255, (c >> 8) & 255, c & 255)
        for c in data.projectile_assets[missile.sprite.assetId].palettePreview.colors]
    files = {REPO / path: read(REPO / path) for path in DEFAULT_DRAFTS}
    files.update({path.resolve(): read(path) for path in args.draft_file})
    selected = {row["definitionRef"]["content_id"]: (path, row)
                for path, raw in files.items() for row in raw["spells"]}
    bindings_path = REPO / "game/data/spell_recovery/bindings.json"
    bindings = read(bindings_path)
    noise_key = "/spell-palettes/source-hand-noise.png"
    noise_relative = Path("game/assets/spell_recovery/palettes/source-hand-noise.png")
    (REPO / noise_relative).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ice / "source-hand-noise.png", REPO / noise_relative)
    bindings["resources"][noise_key] = noise_relative.as_posix()
    changed = set()
    treatments = {}
    for identity, (path, recipe) in selected.items():
        name = identity.removeprefix("spell.")
        if name not in APPROVED:
            continue
        if path == REPO / DEFAULT_DRAFTS[0]:
            # Keep the imported NeuroClient oracle usable without optional media.
            path = REPO / DEFAULT_DRAFTS[2]
            recipe = deepcopy(recipe)
            files[path]["spells"].append(recipe)
        colors = palettes[name]
        dark = name == "chill_touch"
        treatment = PaletteTreatment(colors=ordered_palette(colors, dark=dark),
            gamma=1.1 if dark else .65, noiseSheet=noise_key if dark else None, untinted=dark)
        treatments[identity] = treatment.model_dump(mode="json")
        if recipe.get("damage") is None:
            # This imported missile recipe uses the existing global Force context.
            assert name == "magic_missile"
            recipe["damage"] = resolve_damage(data, "Force").model_dump(mode="json")
        recipe["damage"]["hitFlash"].update(frame=0, durationMs=150,
            palette=treatment.model_dump(mode="json"))
        cast = recipe["cast"]
        layers = [cast.get("weaponGlow"), cast.get("aura"), cast.get("slash"), *(cast.get("effects") or [])]
        for layer in layers:
            if layer is None or not layer["enabled"] or layer["hidden"]:
                continue
            # Use each original isolated category, not an already recolored export.
            original = data.resources[f'/spritesheets/{layer["category"]}/{cast["actionClip"]}.png']
            source = pygame.image.load(original).convert_alpha()
            palette = tuple((r << 16) | (g << 8) | b for r, g, b in sorted(colors, key=luminance)) if dark else ordered_palette(colors)
            colored = recolor_palette(source, PaletteTreatment(colors=palette))
            stem = f'{name}-{layer["slot"]}'
            relative = Path("game/assets/spell_recovery/palettes") / f"{stem}.png"
            pygame.image.save(colored, REPO / relative)
            resource = f"/spell-palettes/{stem}.png"
            bindings["resources"][resource] = relative.as_posix()
            layer["sourceSheet"] = resource
        changed.add(path)
        print(f"{identity}: exact {len(treatment.colors)}-color target ramp, 150ms contact flash")
    for path in changed:
        path.write_text(json.dumps(files[path], indent=2) + "\n")
    bindings_path.write_text(json.dumps(bindings, indent=2) + "\n")
    for path in {draft.parent / "bindings.json" for draft in files if draft != REPO / DEFAULT_DRAFTS[0]}:
        binding = read(path)
        edited = False
        for recipe in binding.get("effectDrafts", {}).values():
            identity = recipe["definitionRef"]["content_id"]
            if identity in treatments and recipe.get("damage") is not None:
                recipe["damage"]["hitFlash"].update(frame=0, durationMs=150, palette=treatments[identity])
                edited = True
        if edited:
            path.write_text(json.dumps(binding, indent=2) + "\n")
    pygame.quit()


if __name__ == "__main__":
    main()
