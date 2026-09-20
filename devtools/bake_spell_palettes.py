"""Bake authored isolated casting palettes into their declared local sheets.

Recipes own colors, timing and sourceSheet selection. This tool writes PNGs only;
it neither selects new spell behavior nor changes recipes or resource bindings.
"""

import argparse
import os
from pathlib import Path

import pygame

from game.animation_data import load_animation_data
from game.animation_types import AnimationData, StudioDraftFile
from game.spell_palette import recolor_palette


REPO = Path(__file__).resolve().parents[1]
DEFAULT_DRAFTS = tuple(REPO / "game/data" / bundle / "spell-studio-drafts.json"
                       for bundle in ("codexfx", "spell_recovery", "ice_spells"))


def bake_palettes(data: AnimationData, drafts: StudioDraftFile, *, output_root: Path | None = None) -> tuple[Path, ...]:
    """Use the same authored palette treatment as playback, on isolated layers."""
    outputs = []
    for recipe in (*drafts.spells, *drafts.effectDrafts.values()):
        cast = recipe.cast
        if not cast.enabled:
            continue
        for layer in (cast.weaponGlow, cast.aura, cast.slash, *(cast.effects or ())):
            if layer is None or not layer.enabled or layer.hidden or layer.palette is None:
                continue
            if layer.sourceSheet is None:
                raise ValueError(f"casting palette needs an authored output sheet: {recipe.definitionRef.content_id}/{layer.id}")
            original = data.resources[f"/spritesheets/{layer.category}/{cast.actionClip}.png"]
            source = pygame.image.load(original).convert_alpha()
            noise = (pygame.image.load(data.resources[layer.palette.noiseSheet]).convert_alpha()
                     if layer.palette.noiseSheet is not None else None)
            colored = recolor_palette(source, layer.palette, noise=noise)
            destination = data.resources[layer.sourceSheet]
            if output_root is not None:
                destination = output_root / destination.relative_to(data.media_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(colored, destination)
            outputs.append(destination)
    return tuple(outputs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft-file", type=Path, action="append", default=[],
                        help="Bake only these authored bundles; defaults to the selected local bundles.")
    args = parser.parse_args()
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        data = load_animation_data()
        for path in args.draft_file or DEFAULT_DRAFTS:
            drafts = StudioDraftFile.model_validate_json(path.read_text())
            for output in bake_palettes(data, drafts):
                print(output.relative_to(REPO))
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
