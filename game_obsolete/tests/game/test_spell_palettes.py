"""Authored spell colors change actual actor pixels without changing their pose."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pygame
import pytest

from game.animation import ActorContact, BodySample, CastApplication, CastInput, GroundContact, compile_cast, resolve_cast_recipe, sample_cast
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands, load_actor_media, load_cast_rows, load_animation_media
from game.animation_types import ElementColors, LayerColors, PaletteTreatment, RigLayer
from game.body_action import bind_body_action
from dnd.player.facts import SpellFact
from dnd.player.reduction import reduce_lineage
from game.projection import Camera
from game.spell_palette import palette_noise, recolor_palette
from tests.game.player_helpers import player_history
from tests.game.support_conditions_scenarios import support_condition_history


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
        yield load_animation_data(rig_files=(Path("game/data/rigs/goblin01.json"), Path("game/data/rigs/goblin02.json")))
        pygame.quit()


def rgb_set(image):
    opaque = pygame.surfarray.array_alpha(image) == 255
    return {tuple(int(v) for v in pixel) for pixel in pygame.surfarray.array3d(image)[opaque]}


def colors(treatment):
    return {((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in treatment.colors}


def visible_colors(image):
    visible = pygame.surfarray.array_alpha(image) > 0
    return {tuple(int(v) for v in pixel) for pixel in pygame.surfarray.array3d(image)[visible]}


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
    contact = ActorContact("caster", (0, 0), "E", .5)
    recipe = resolve_cast_recipe(data, contact, data.drafts["spell." + spell])
    cast = recipe.cast
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
        rows = {}
        load_cast_rows(data, contact, cast.actionClip, contact.facing, (layer,), rows)
        assert layer.palette is not None and layer.palette.noiseSheet is not None
        for key, image in rows.items():
            raw = baked.subsurface((0, key[3] * rig.cell_height, image.width, image.height))
            assert np.array_equal(pygame.surfarray.array_alpha(raw), pygame.surfarray.array_alpha(image))
            assert visible_colors(image) <= colors(layer.palette)
            assert len(visible_colors(image)) > 1
            expected = recolor_palette(raw, layer.palette,
                noise=palette_noise(data.resources[layer.palette.noiseSheet]),
                cell_size=(rig.cell_width, rig.cell_height))
            assert pygame.image.tobytes(image, "RGBA") == pygame.image.tobytes(expected, "RGBA")


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


@pytest.mark.parametrize("reverse", (False, True))
def test_automatic_cast_palette_replaces_pixels_and_shared_sheet_cache_is_isolated(data, reverse):
    """Two spell palettes sharing one precolored source stay distinct after seeks."""
    original = data.drafts["spell.fire_bolt"]
    layer = original.cast.weaponGlow
    assert layer is not None and layer.sourceSheet is not None
    automatic = layer.model_copy(update={"colors": layer.colors.model_copy(update={"source": "auto"})})
    contact = ActorContact("caster", (0, 0), "E", .5)
    source = CastInput("automatic-hands", contact, (
        CastApplication("hit", ActorContact("target", (4, 0), "W", .5), True, 3, 17),))
    palettes = (ElementColors(primary=0xD44422, secondary=0xFFE4A0, tertiary=0x442211),
                ElementColors(primary=0x22AACC, secondary=0xCCFFFF, tertiary=0x112244))
    timelines = []
    for palette in palettes:
        draft = original.model_copy(update={"elementColors": palette,
            "cast": original.cast.model_copy(update={"weaponGlow": automatic})})
        selected_data = replace(data, drafts={**data.drafts, "spell.fire_bolt": draft})
        timelines.append(compile_cast(selected_data, "spell.fire_bolt", source))
    # Explicit override of exactly the same source must still retain its baked pixels.
    overridden = original.model_copy(update={"cast": original.cast.model_copy(update={
        "weaponGlow": layer.model_copy(update={"colors": layer.colors.model_copy(update={"source": "override"})}),
        "aura": None, "effects": ()})})
    override_data = replace(data, drafts={**data.drafts, "spell.fire_bolt": overridden})
    timelines.append(compile_cast(override_data, "spell.fire_bolt", source))
    rows = {}
    baked = pygame.image.load(data.resources[layer.sourceSheet]).convert_alpha()
    rig = data.rigs[contact.rig_id]
    for index in (reversed(range(3)) if reverse else range(3)):
        timeline = timelines[index]
        resolved = timeline.recipe.cast.weaponGlow
        assert resolved is not None
        previous = set(rows)
        load_cast_rows(data, contact, timeline.recipe.cast.actionClip, "E", (resolved,), rows)
        added = set(rows) - previous
        assert len(added) == 4, "each effective palette needs its own four camera rows"
        for key in added:
            image = rows[key]
            raw = baked.subsurface((0, key[3] * rig.cell_height, image.width, image.height))
            assert np.array_equal(pygame.surfarray.array_alpha(raw), pygame.surfarray.array_alpha(image))
            if index < 2:
                palette = palettes[index]
                assert visible_colors(image) == colors(PaletteTreatment(colors=(
                    palette.tertiary, palette.primary, palette.secondary)))
            else:
                assert pygame.image.tobytes(image, "RGBA") == pygame.image.tobytes(raw, "RGBA")
        snapshot = {key: pygame.image.tobytes(rows[key], "RGBA") for key in added}
        # Sampling and reloading after seeking cannot mutate the prepared colors or timing.
        baseline = timelines[2]
        for elapsed in (250., 100., 250.):
            sample = sample_cast(timeline, elapsed)
            base = sample_cast(baseline, elapsed)
            body = next(body for body in sample.bodies if body.actor_uuid == "caster")
            base_body = next(body for body in base.bodies if body.actor_uuid == "caster")
            assert (body.clip, body.frame, body.facing) == (base_body.clip, base_body.frame, base_body.facing)
            assert resolved in body.cast_layers
            load_cast_rows(data, contact, body.clip, body.facing, body.cast_layers, rows)
        assert all(pygame.image.tobytes(rows[key], "RGBA") == pixels for key, pixels in snapshot.items())


def test_auto_is_the_default_and_fixed_rigs_keep_their_own_accents(data):
    original = data.drafts["spell.fire_bolt"]
    layer = original.cast.weaponGlow
    assert layer is not None
    descriptor = layer.colors.model_dump(exclude={"source"})
    automatic = layer.model_copy(update={"colors": LayerColors.model_validate(descriptor)})
    assert automatic.colors.source == "auto"
    draft = original.model_copy(update={"cast": original.cast.model_copy(update={"weaponGlow": automatic})})
    for rig in ("neuroclient.modular", "smallscale.goblin02"):
        resolved = resolve_cast_recipe(data, ActorContact("caster", (0, 0), "E", .5, rig_id=rig), draft)
        if rig == "neuroclient.modular":
            assert resolved.cast.weaponGlow is not None and resolved.cast.weaponGlow.palette is not None
        else:
            assert resolved.cast.weaponGlow is None and not resolved.cast.effects


def test_actor_only_cast_uses_the_same_automatic_hand_palette(data):
    history = support_condition_history(program="death_ward", self_target=True)
    before, roots = player_history(history, role="caster")
    original = data.drafts["spell.death_ward"]
    layer = original.cast.weaponGlow
    assert layer is not None
    palette = ElementColors(primary=0xA032CD, secondary=0xFCD3FF, tertiary=0x321046)
    draft = original.model_copy(update={"elementColors": palette, "cast": original.cast.model_copy(update={
        "weaponGlow": layer.model_copy(update={"colors": layer.colors.model_copy(update={"source": "auto"})})})})
    selected_data = replace(data, drafts={**data.drafts, "spell.death_ward": draft})
    for root in roots:
        fact = root.root.fact
        if isinstance(fact, SpellFact) and fact.behavior_id == "spell.death_ward":
            cue = bind_body_action(before, root.root, selected_data, start_ms=0, facings={}, contacts={})
            assert cue is not None and cue.cast_layers
            rows = {}
            load_cast_rows(data, cue.contact, cue.clip, cue.contact.facing, cue.cast_layers, rows)
            assert rows
            expected = colors(PaletteTreatment(colors=(palette.tertiary, palette.primary, palette.secondary)))
            assert all(visible_colors(image) and visible_colors(image) <= expected for image in rows.values())
            assert set.union(*(visible_colors(image) for image in rows.values())) == expected
            return
        before = reduce_lineage(before, root)
    pytest.fail("the native cast must be witnessed")


@pytest.mark.parametrize('spell', ('slow', 'flame_strike', 'hold_person', 'cone_of_cold'))
def test_current_spell_hands_match_their_spell_palette_before_release(data, spell):
    contact = ActorContact('caster', (0, 0), 'E', .5)
    draft = data.drafts['spell.' + spell]
    resolved = resolve_cast_recipe(data, contact, draft)
    layer = resolved.cast.weaponGlow
    assert layer is not None and layer.enabled and not layer.hidden
    authored = draft.cast.weaponGlow
    assert authored is not None and authored.palette is not None and layer.palette is not None
    assert layer.palette.gamma == authored.palette.gamma
    assert layer.palette.noiseSheet == authored.palette.noiseSheet
    rows = {}
    load_cast_rows(data, contact, resolved.cast.actionClip, 'E', (layer,), rows)
    expected = colors(PaletteTreatment(colors=(draft.elementColors.tertiary,
        draft.elementColors.primary, draft.elementColors.secondary)))
    rig = data.rigs[contact.rig_id]
    for image in rows.values():
        preparation = image.subsurface((0, 0, int(draft.cast.releaseFrame) * rig.cell_width, rig.cell_height))
        assert visible_colors(preparation) and visible_colors(preparation) <= expected


def test_every_enabled_spell_cast_has_visible_magic_hands(data):
    """Every real cast, including variants/repeats, visibly carries magic energy."""
    missing = []
    for identity, draft in data.drafts.items():
        if not draft.cast.enabled:
            continue  # The actual child weapon attack is verified in its replay tests.
        layer = draft.cast.weaponGlow
        if layer is None or not layer.enabled or layer.hidden or layer.category not in ('Magic1', 'Magic2', 'Magic3'):
            missing.append(identity)
    assert not missing, f"Spells missing casting hands: {missing}"
    contact = ActorContact('caster', (0, 0), 'E', .5)
    # Canonical recipes and separately authored variants must both render correctly.
    checked = set()
    for draft in data.drafts.values():
        if not draft.cast.enabled:
            continue
        resolved = resolve_cast_recipe(data, contact, draft)
        layer = resolved.cast.weaponGlow
        assert layer is not None
        key = (resolved.cast.actionClip, layer.model_dump_json())
        if key in checked:
            continue
        checked.add(key)
        rows = {}
        load_cast_rows(data, contact, resolved.cast.actionClip, contact.facing, (layer,), rows)
        rig = data.rigs[contact.rig_id]
        source_path = layer.sourceSheet or rig.clips[resolved.cast.actionClip].sheets[layer.category]
        source = pygame.image.load(data.resources[source_path]).convert_alpha()
        for row_key, image in rows.items():
            raw = source.subsurface((0, row_key[3] * rig.cell_height, image.width, image.height))
            assert np.array_equal(pygame.surfarray.array_alpha(image), pygame.surfarray.array_alpha(raw))
            preparation = image.subsurface((0, 0, int(resolved.cast.releaseFrame) * rig.cell_width, rig.cell_height))
            assert visible_colors(preparation), draft.definitionRef.content_id
            if layer.colors.source == 'auto':
                palette = draft.elementColors
                expected = colors(PaletteTreatment(colors=(palette.tertiary, palette.primary, palette.secondary)))
                assert visible_colors(image) <= expected


def test_explicit_unbaked_overlay_uses_exact_palette_and_cache_separates_treatment(data):
    """An explicit overlay must not multiply or hue-rotate its original colors."""
    draft = data.drafts['spell.fire_bolt']
    original = draft.cast.weaponGlow
    assert original is not None
    contact = ActorContact('caster', (0, 0), 'E', .5)
    palettes = ((0x180829, 0x9848D8, 0xF0D8FF), (0x062A30, 0x18C8A8, 0xC8FFF0))
    rows = {}
    for palette in palettes:
        layer = original.model_copy(update={'sourceSheet': None, 'palette': None,
            'colors': LayerColors(source='override', primary=palette[1],
                secondary=palette[2], tertiary=palette[0], mode='paletteSwap')})
        previous = set(rows)
        load_cast_rows(data, contact, draft.cast.actionClip, contact.facing, (layer,), rows)
        added = set(rows) - previous
        assert len(added) == 4
        expected = {((value >> 16) & 255, (value >> 8) & 255, value & 255) for value in palette}
        for key in added:
            assert visible_colors(rows[key]) <= expected
            assert visible_colors(rows[key])


def test_full_cast_loader_accepts_explicit_effect_palette_without_hue_policy(data):
    original = data.drafts['spell.fire_bolt']
    assert original.cast.weaponGlow is not None
    layer = original.cast.weaponGlow.model_copy(update={'category': 'Effect4', 'slot': 'aura',
        'sourceSheet': None, 'palette': None,
        'colors': LayerColors(source='override', primary=0x9848D8,
            secondary=0xF0D8FF, tertiary=0x180829, mode='paletteSwap')})
    draft = original.model_copy(update={'cast': original.cast.model_copy(update={
        'weaponGlow': None, 'aura': layer, 'effects': ()})})
    selected = replace(data, drafts={**data.drafts, 'spell.fire_bolt': draft})
    caster = ActorContact('caster', (0, 0), 'E', .5)
    target = ActorContact('target', (4, 0), 'W', .5)
    timeline = compile_cast(selected, 'spell.fire_bolt', CastInput('explicit-aura', caster,
        (CastApplication('hit', target, True, 3, 17),)))
    media = load_animation_media(timeline, {'caster': MODULAR, 'target': MODULAR})
    overlays = [image for key, image in media.body_rows.items() if key[2].startswith('cast:Effect4:')]
    assert len(overlays) == 4
    expected = {(0x18, 0x08, 0x29), (0x98, 0x48, 0xD8), (0xF0, 0xD8, 0xFF)}
    assert all(visible_colors(image) and visible_colors(image) <= expected for image in overlays)
