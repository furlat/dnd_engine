"""Real imported media preload and deterministic Pygame frame boundaries."""

from dataclasses import replace
import json
from pathlib import Path
from types import MappingProxyType

import pygame
import pytest

from dnd.core.life_types import LifeState
from game.animation import ActorContact, CastApplication, CastInput, compile_cast, sample_cast
from game.animation_data import load_animation_data
from game.animation_draw import RigLayer, draw_animation, load_animation_media
from game.animation_types import BodyRig, StudioSpellDraft
from game.projection import Camera, project_screen


APPEARANCE = tuple(RigLayer(slot, category, alpha=0.5 if slot == "shadow" else 1) for slot, category in (
    ("body", "NakedBody"), ("head", "Head22"), ("helmet", "Head15"),
    ("chest", "Chest14"), ("legs", "Legs1"), ("belt", "Belt2"),
    ("shoes", "Shoes1"), ("shadow", "Shadow"), ("weapon", "Melee1"),
))
APPEARANCES = {"caster": APPEARANCE, "target": APPEARANCE}
GOBLIN_APPEARANCE = (RigLayer("shadow", "Goblin01Shadow", alpha=0.5),
                     RigLayer("body", "Goblin01"))


@pytest.fixture(scope="module")
def screen():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        try:
            yield pygame.display.set_mode((800, 500))
        finally:
            pygame.quit()


@pytest.fixture(scope="module")
def timeline():
    rig_file = Path(__file__).resolve().parents[2] / "game/data/rigs/goblin01.json"
    data = load_animation_data(rig_files=(rig_file,))
    document = data.drafts["spell.fire_bolt"].model_dump(mode="json", exclude_unset=True)
    document["cast"]["recovery"]["enabled"] = True
    draft = StudioSpellDraft.model_validate_json(json.dumps(document))
    data = replace(data, drafts=MappingProxyType({**data.drafts, "spell.fire_bolt": draft}))
    source = CastInput("draw-reference", ActorContact("caster", (0, 0), "S", 0.5), (
        CastApplication("application-1", ActorContact("target", (3, -3), "W", 0.5, hp=20),
                        damage_applied=True, damage_total=7, resulting_hp=13),
    ))
    return compile_cast(data, "spell.fire_bolt", source)


@pytest.fixture(scope="module")
def media(screen, timeline):
    return load_animation_media(timeline, APPEARANCES)


def render_pixels(screen, timeline, media, elapsed):
    screen.fill((0, 0, 0))
    camera = Camera(quadrant=0, zoom=1, viewport=screen.get_size()).with_focus((1.5, -1.5))
    draw_animation(screen, timeline, sample_cast(timeline, elapsed), media, camera)
    return pygame.image.tobytes(screen, "RGB")


@pytest.mark.parametrize("broken", ["missing", "corrupt"])
def test_required_gear_must_be_usable_before_preload_finishes(screen, timeline, tmp_path: Path, broken: str) -> None:
    resources = dict(timeline.data.resources)
    gear_url = "/spritesheets/Chest14/Idle.png"
    if broken == "missing":
        del resources[gear_url]
    else:
        resources[gear_url] = tmp_path / "corrupt.png"
        resources[gear_url].write_bytes(b"not a PNG")
    data = replace(timeline.data, resources=MappingProxyType(resources))
    candidate = compile_cast(data, "spell.fire_bolt", timeline.source)
    with pytest.raises((ValueError, pygame.error)):
        load_animation_media(candidate, APPEARANCES)


@pytest.mark.parametrize("target_rig", ["neuroclient.modular", "smallscale.goblin01"])
def test_preloaded_media_draws_every_phase_after_source_links_are_removed(
    screen, timeline, tmp_path: Path, target_rig: str,
) -> None:
    resources = {}
    for index, (url, source) in enumerate(timeline.data.resources.items()):
        link = tmp_path / f"resource-{index}.png"
        link.symlink_to(source)
        resources[url] = link
    data = replace(timeline.data, resources=MappingProxyType(resources))
    source = replace(timeline.source, applications=(replace(
        timeline.source.applications[0], target=replace(timeline.source.applications[0].target, rig_id=target_rig),
    ),))
    candidate = compile_cast(data, "spell.fire_bolt", source)
    appearance = APPEARANCE if target_rig == "neuroclient.modular" else GOBLIN_APPEARANCE
    loaded = load_animation_media(candidate, {"caster": APPEARANCE, "target": appearance})
    for link in resources.values():
        link.unlink()
    assert all(not link.exists() for link in resources.values())
    for elapsed in (0, 100, 900, 1900, 2800, 4000):
        assert any(render_pixels(screen, candidate, loaded, elapsed)), elapsed
    lethal = compile_cast(data, "spell.fire_bolt", replace(
        source, applications=(replace(source.applications[0], resulting_hp=0, resulting_life_state=LifeState.DEAD),),
    ))
    assert any(render_pixels(screen, lethal, loaded, lethal.complete_ms))


def test_seeking_back_restores_identical_pixels_after_other_phases(screen, timeline, media) -> None:
    expected = render_pixels(screen, timeline, media, 900)
    assert any(expected)
    for elapsed in (1900, 2800, 4000, 0, 100):
        render_pixels(screen, timeline, media, elapsed)
    assert render_pixels(screen, timeline, media, 900) == expected
    assert render_pixels(screen, timeline, media, 2800) != expected


@pytest.fixture(scope="module", params=("W", "NW"))
def fixed_scene(request, screen, timeline):
    source = replace(timeline.source, applications=(replace(
        timeline.source.applications[0], target=replace(
            timeline.source.applications[0].target, rig_id="smallscale.goblin01", facing=request.param,
        ),
    ),))
    candidate = compile_cast(timeline.data, "spell.fire_bolt", source)
    appearances = {"caster": APPEARANCE, "target": GOBLIN_APPEARANCE}
    return candidate, load_animation_media(candidate, appearances)


@pytest.mark.parametrize("quadrant", range(4))
def test_fixed_target_matches_actual_sheet_and_support_in_every_direction(screen, fixed_scene, quadrant) -> None:
    candidate, loaded = fixed_scene
    contact = candidate.source.applications[0].target
    camera = Camera(quadrant=quadrant, zoom=1, viewport=screen.get_size()).with_focus((1.5, -1.5))
    screen.fill((0, 0, 0))
    draw_animation(screen, candidate, sample_cast(candidate, 0), loaded, camera)

    # The inspected Goblin sheets are E, SE, S, SW, W, NW, N, NE. At this
    # reference scale each 128px cell draws at its original pixel dimensions.
    row = ((4 if contact.facing == "W" else 5) + 2 * quadrant) % 8
    binding = candidate.data.rigs[contact.rig_id].clips["Idle"]
    expected = pygame.Surface((128, 128))
    expected.fill((0, 0, 0))
    for category, opacity in (("Goblin01Shadow", 128), ("Goblin01", 255)):
        sheet = pygame.image.load(candidate.data.resources[binding.sheets[category]]).convert_alpha()
        cell = sheet.subsurface((0, row * 128, 128, 128)).copy()
        cell.set_alpha(opacity)
        expected.blit(cell, (0, 0))
    ground = project_screen(contact.grid, camera)
    target_rect = pygame.Rect(round(ground[0] - 64), round(ground[1] - 87), 128, 128)
    assert pygame.image.tobytes(screen.subsurface(target_rect), "RGB") == pygame.image.tobytes(expected, "RGB")


def test_fixed_target_hit_and_death_seek_restore_pixels_without_reloading(screen, fixed_scene) -> None:
    candidate, loaded = fixed_scene
    assert candidate.applications[0].damage_start_ms is not None
    hit_time = candidate.applications[0].damage_start_ms + 250
    expected_hit = render_pixels(screen, candidate, loaded, hit_time)
    assert sample_cast(candidate, hit_time).bodies[1].clip == "TakeDamage"
    lethal = compile_cast(candidate.data, "spell.fire_bolt", replace(
        candidate.source, applications=(replace(
            candidate.source.applications[0], resulting_hp=0, resulting_life_state=LifeState.DEAD,
        ),),
    ))
    corpse = render_pixels(screen, lethal, loaded, lethal.complete_ms)
    assert sample_cast(lethal, lethal.complete_ms).bodies[1].frame == 14
    assert corpse != expected_hit
    render_pixels(screen, candidate, loaded, 0)
    assert render_pixels(screen, candidate, loaded, hit_time) == expected_hit
    assert render_pixels(screen, lethal, loaded, lethal.complete_ms) == corpse


def test_different_rigs_can_use_the_same_category_names(screen, timeline) -> None:
    rig = timeline.data.rigs["smallscale.goblin01"]
    document = rig.model_dump(mode="json")
    document["slot_categories"] = {"body": ["NakedBody"], "shadow": ["Shadow"]}
    for clip in document["clips"].values():
        clip["sheets"] = {"NakedBody": clip["sheets"]["Goblin01"],
                          "Shadow": clip["sheets"]["Goblin01Shadow"]}
    shared_names = BodyRig.model_validate_json(json.dumps(document))
    source = replace(timeline.source, applications=(replace(
        timeline.source.applications[0], target=replace(timeline.source.applications[0].target, rig_id="smallscale.goblin01"),
    ),))
    original = compile_cast(timeline.data, "spell.fire_bolt", source)
    expected = render_pixels(screen, original, load_animation_media(
        original, {"caster": APPEARANCE, "target": GOBLIN_APPEARANCE},
    ), 0)
    data = replace(timeline.data, rigs=MappingProxyType({**timeline.data.rigs, "smallscale.goblin01": shared_names}))
    candidate = compile_cast(data, "spell.fire_bolt", source)
    appearance = (RigLayer("body", "NakedBody"), RigLayer("shadow", "Shadow", alpha=0.5))
    loaded = load_animation_media(candidate, {"caster": APPEARANCE, "target": appearance})
    assert render_pixels(screen, candidate, loaded, 0) == expected


def test_fixed_rig_origin_moves_body_and_feedback_together(screen, fixed_scene) -> None:
    original, loaded = fixed_scene
    rig = original.data.rigs["smallscale.goblin01"]
    document = rig.model_dump(mode="json")
    document["origin_y_from_ground"] += 12
    shifted = BodyRig.model_validate_json(json.dumps(document))
    data = replace(original.data, rigs=MappingProxyType({**original.data.rigs, "smallscale.goblin01": shifted}))
    candidate = compile_cast(data, "spell.fire_bolt", original.source)
    camera = Camera(quadrant=0, zoom=1, viewport=screen.get_size()).with_focus((1.5, -1.5))
    frames = []
    for cast in (original, candidate):
        assert cast.applications[0].number_ms is not None
        sample = sample_cast(cast, cast.applications[0].number_ms + 100)
        assert sample.numbers
        # Exercise the public raster boundary for this actor and its feedback;
        # caster/projectile timing has separate evaluator and space proofs.
        selected = replace(sample, bodies=(sample.bodies[1],), projectiles=())
        screen.fill((0, 0, 0))
        draw_animation(screen, cast, selected, loaded, camera)
        frames.append(screen.copy())
    expected = pygame.Surface(screen.get_size())
    expected.fill((0, 0, 0))
    expected.blit(frames[0], (0, 12))
    assert pygame.image.tobytes(frames[1], "RGB") == pygame.image.tobytes(expected, "RGB")


@pytest.mark.parametrize("broken", ["missing-shadow", "wrong-dimensions", "removable-weapon"])
def test_fixed_rig_media_failures_are_rejected_before_drawing(screen, timeline, broken) -> None:
    data = timeline.data
    rig = data.rigs["smallscale.goblin01"]
    appearance = GOBLIN_APPEARANCE
    if broken == "missing-shadow":
        resources = dict(data.resources)
        del resources[rig.clips["TakeDamage"].sheets["Goblin01Shadow"]]
        data = replace(data, resources=MappingProxyType(resources))
    elif broken == "wrong-dimensions":
        document = rig.model_dump(mode="json")
        document["cell_width"] = 64
        changed = BodyRig.model_validate_json(json.dumps(document))
        data = replace(data, rigs=MappingProxyType({**data.rigs, "smallscale.goblin01": changed}))
    else:
        appearance += (RigLayer("weapon", "Melee1"),)
    source = replace(timeline.source, applications=(replace(
        timeline.source.applications[0], target=replace(timeline.source.applications[0].target, rig_id="smallscale.goblin01"),
    ),))
    with pytest.raises(ValueError):
        candidate = compile_cast(data, "spell.fire_bolt", source)
        load_animation_media(candidate, {"caster": APPEARANCE, "target": appearance})
