"""Authored spell colors change actual actor pixels without changing their pose."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pygame
import pytest

from game.animation import ActorContact, BodySample, CastApplication, CastInput, GroundContact, compile_cast, sample_cast
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands, load_actor_media
from game.animation_types import PaletteTreatment, RigLayer
from game.projection import Camera
from game.spell_palette import recolor_palette


SPELLS = ("fire_bolt", "fireball", "magic_missile", "acid_splash", "guiding_bolt", "eldritch_blast",
          "ray_of_frost", "ice_knife", "chill_touch", "ice_knife.burst")
MODULAR = (RigLayer("body", "NakedBody"), RigLayer("head", "Head22"),
           RigLayer("chest", "Chest14", tint=0xAA4444), RigLayer("shadow", "Shadow", alpha=.5))
GOBLIN = (RigLayer("body", "Goblin01"), RigLayer("shadow", "Goblin01Shadow", alpha=.5))


@pytest.fixture(scope="module")
def data():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((800, 600))
        yield load_animation_data(rig_files=(Path("game/data/rigs/goblin01.json"),))
        pygame.quit()


def rgb_set(image):
    opaque = pygame.surfarray.array_alpha(image) == 255
    return {tuple(int(v) for v in pixel) for pixel in pygame.surfarray.array3d(image)[opaque]}


def colors(treatment):
    return {((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in treatment.colors}


@pytest.mark.parametrize("spell", SPELLS)
def test_each_authored_spell_flashes_exact_palette_for_150ms_and_continues_taking_damage(data, spell):
    target = ActorContact("target", (4, -2), "W", .5, hp=20)
    source = CastInput("palette", ActorContact("caster", (0, 0), "E", .5), (
        CastApplication("injury", target, True, 4, 16, damage_type="Force"),),
        GroundContact(target.grid) if spell in ("fireball", "ice_knife.burst") else None)
    timeline = compile_cast(data, "spell." + spell, source)
    application, = timeline.applications
    start = application.damage_start_ms
    assert start is not None and application.flash_ms == start
    damage = timeline.recipe.damage
    assert damage is not None
    expected = damage.hitFlash.palette
    assert isinstance(expected, PaletteTreatment)
    moments = [(start, True), (start + 149.9, True), (start + 150, False)]
    if start > 0:
        moments.insert(0, (start - .001, False))
    for elapsed, flashing in moments:
        sample = sample_cast(timeline, elapsed)
        vital = next(v for v in sample.vitals if v.actor_uuid == "target")
        assert vital.flash == (expected if flashing else None)
    reaction = next(b for b in sample_cast(timeline, start + 200).bodies if b.actor_uuid == "target")
    assert reaction.clip == "TakeDamage" and reaction.frame > 0
    assert application.hp_ms == pytest.approx(start + damage.floatingNumber.frame * 1000 / 12)


@pytest.mark.parametrize("rig,appearance", (("neuroclient.modular", MODULAR), ("smallscale.goblin01", GOBLIN)))
@pytest.mark.parametrize("quadrant", range(4))
def test_palette_flash_preserves_real_actor_silhouette_and_equipment_after_seek(data, rig, appearance, quadrant):
    contact = ActorContact("target", (2, 2), "W", .5, rig_id=rig)
    rows = load_actor_media(data, ((contact, appearance, ("TakeDamage",)),), all_facings=True)
    body = BodySample("target", "TakeDamage", 1, "W")
    camera = Camera(quadrant=quadrant, zoom=1)
    treatment = data.drafts["spell.eldritch_blast"].damage.hitFlash.palette
    assert treatment is not None

    def draw(flash=None, frame=body):
        return {command[4][6]: command[1] for command in actor_draw_commands(
            data, frame, contact, appearance, rows, camera, flash=flash)}

    ordinary = draw()
    flashed = draw(treatment)
    assert np.array_equal(pygame.surfarray.array_alpha(ordinary["actor"]), pygame.surfarray.array_alpha(flashed["actor"]))
    assert rgb_set(flashed["actor"]) <= colors(treatment)
    assert len(rgb_set(flashed["actor"])) > 2
    assert pygame.image.tobytes(flashed["actor_shadow"], "RGBA") == pygame.image.tobytes(ordinary["actor_shadow"], "RGBA")
    draw(treatment, replace(body, frame=8))
    assert pygame.image.tobytes(draw()["actor"], "RGBA") == pygame.image.tobytes(ordinary["actor"], "RGBA")
    assert pygame.image.tobytes(draw(treatment)["actor"], "RGBA") == pygame.image.tobytes(flashed["actor"], "RGBA")


def test_dark_noise_treatment_preserves_body_alpha_and_has_black_and_green_regions(data):
    contact = ActorContact("target", (2, 2), "W", .5)
    rows = load_actor_media(data, ((contact, MODULAR, ("TakeDamage",)),), all_facings=True)
    treatment = data.drafts["spell.chill_touch"].damage.hitFlash.palette
    assert treatment is not None and treatment.untinted and treatment.noiseSheet is not None
    body = BodySample("target", "TakeDamage", 1, "W")
    images = [next(c[1] for c in actor_draw_commands(data, body, contact, MODULAR, rows, Camera(), flash=flash)
                   if c[4][6] == "actor") for flash in (None, treatment)]
    assert np.array_equal(pygame.surfarray.array_alpha(images[0]), pygame.surfarray.array_alpha(images[1]))
    actual = rgb_set(images[1])
    assert actual <= colors(treatment) and (0, 0, 0) in actual and len(actual) >= 3


@pytest.mark.parametrize("spell", tuple(s for s in SPELLS if s != "magic_missile"))
def test_selected_cast_overlay_has_exact_spell_colors_and_complete_rig_geometry(data, spell):
    recipe = data.drafts["spell." + spell]
    flash = recipe.damage.hitFlash.palette
    assert flash is not None
    cast = recipe.cast
    allowed = colors(flash)
    if spell == "chill_touch":
        assert recipe.projectile is not None and recipe.projectile.sprite is not None
        allowed = {((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in
            data.projectile_assets[recipe.projectile.sprite.assetId].palettePreview.colors}
    for layer in (cast.weaponGlow, cast.aura, cast.slash, *(cast.effects or ())):
        if layer is None or not layer.enabled or layer.hidden:
            continue
        assert layer.sourceSheet is not None
        baked = pygame.image.load(data.resources[layer.sourceSheet]).convert_alpha()
        rig = data.rigs[data.root_rig]
        clip = rig.clips[cast.actionClip]
        assert baked.width >= clip.frames * rig.cell_width
        assert baked.height >= (max(rig.facing_rows.values()) + 1) * rig.cell_height
        alpha = pygame.surfarray.array_alpha(baked)
        assert np.any(alpha == 0) and np.any(alpha > 0)
        assert rgb_set(baked) <= allowed
        assert len(rgb_set(baked)) > 1


def test_authored_palette_roundtrips_as_data_and_mapping_preserves_partial_alpha(data):
    treatment = data.drafts["spell.fireball"].damage.hitFlash.palette
    assert treatment is not None
    restored = PaletteTreatment.model_validate_json(treatment.model_dump_json())
    source = pygame.Surface((5, 1), pygame.SRCALPHA)
    for x in range(5):
        source.set_at((x, 0), (x * 50, x * 50, x * 50, x * 60))
    result = recolor_palette(source, restored)
    assert np.array_equal(pygame.surfarray.array_alpha(source), pygame.surfarray.array_alpha(result))
    assert {tuple(result.get_at((x, 0))[:3]) for x in range(5)} <= colors(restored)
