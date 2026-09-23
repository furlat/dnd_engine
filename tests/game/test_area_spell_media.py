"""Authored area media stays registered, finite and separate from recipients."""

from dataclasses import replace
import json
from pathlib import Path

import pygame
import pytest

from devtools.import_area_spells import DIRECTIONS, cube_cell, import_bundle
from game.animation import ActorContact, CastApplication, CastInput, GroundContact, compile_cast, sample_cast
from game.animation_data import load_animation_data
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage, StudioDraftFile
from game.cast_media import cast_media_draw_commands
from game.projection import Camera
from game.registered_media import registered_media_blits


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_area_import_keeps_authored_recipes_and_exact_registered_translucent_parts(tmp_path):
    source, repo = tmp_path / "source", tmp_path / "repo"
    data = repo / "game/data/area_spells"
    write_json(data / "spell-studio-drafts.json", {"author": "independent recipe"})
    authored = (data / "spell-studio-drafts.json").read_bytes()
    write_json(data / "bindings.json", {"resources": {"local-art": "game/assets/local.png"},
        "spells": {"spell.authored": {"keep": True}}})
    palette = [[20, 40, 60], [160, 180, 200]]
    for folder in ("burning-hands-review", "aoe-crest-review/sheets", "gust-wave-review/whole-sheets"):
        (source / folder).mkdir(parents=True, exist_ok=True)
    sheet = pygame.Surface((512, 256), pygame.SRCALPHA)
    sheet.fill((25, 45, 65, 73), (11, 17, 5, 7))
    sheet.fill((160, 180, 200, 191), (256 + 13, 19, 6, 8))
    pygame.image.save(sheet, source / "aoe-crest-review/sheets/two.png")
    one = pygame.Surface((32, 32), pygame.SRCALPHA)
    one.fill((160, 180, 200, 73), (3, 5, 7, 9))
    pygame.image.save(one, source / "burning-hands-review/one.png")
    pygame.image.save(one, source / "gust-wave-review/whole-sheets/one.png")
    write_json(source / "burning-hands-review/manifest.json", {
        "cell": 32, "frames": 1, "fps": 144, "palette": palette,
        "directions": {d: {"pivot": [16, 24], "pages": [{"file": "one.png", "firstFrame": 0,
            "frameCount": 1, "columns": 1}]} for d in DIRECTIONS}})
    pages = [{"file": "two.png", "firstFrame": 0, "frameCount": 2, "columns": 2}]
    write_json(source / "aoe-crest-review/manifest.json", {
        "cell": 256, "pivot": [128, 192], "captureFps": 144,
        "spells": {"thunderwave": {"palette": palette, "directions": {
            bank: {"frames": 2, "cells": {"_".join(map(str, cube_cell(bank, d, l))): {
                "phases": {"back": pages, "front": pages}}
                for d in range(3) for l in range(-1, 2)}} for bank in ("SE", "SW", "NW", "NE")}}}})
    write_json(source / "aoe-crest-review/frame-bounds.json", {"two.png": [[11, 17, 16, 24], [13, 19, 19, 27]]})
    write_json(source / "gust-wave-review/whole-manifest.json", {
        "frames": 1, "fps": 144, "palette": palette,
        "directions": {d: {"pivot": [300, 500], "pages": ["one.png"],
            "frames": [[[0, 3, 5, 7, 9, 77, 81]]]} for d in DIRECTIONS}})
    for folder, name in (("aoe-crest-review/actors/burning_hands", "hand-glow.png"),
                         ("aoe-crest-review/actors/thunderwave", "Special1-glow.png"),
                         ("gust-wave-review/actors/gust_of_wind", "hand-glow.png")):
        (source / folder).mkdir(parents=True)
        pygame.image.save(one, source / folder / name)

    import_bundle(source, repo=repo)

    assert (data / "spell-studio-drafts.json").read_bytes() == authored
    bindings = json.loads((data / "bindings.json").read_text())
    assert bindings["spells"] == {"spell.authored": {"keep": True}}
    assert bindings["resources"]["local-art"] == "game/assets/local.png"
    crest = bindings["projectileStorage"]["area.thunderwave.v10.1.0.back"]["phases"]["impact"]["layers"][0]
    for index, expected in enumerate(((11, 17, 5, 7), (269, 19, 6, 8))):
        part, = crest["partsByFacing"]["SE"][index]
        actual = pygame.image.load(repo / part["file"]).subsurface(part["rect"])
        assert pygame.image.tobytes(actual, "RGBA") == pygame.image.tobytes(sheet.subsurface(expected), "RGBA")
        assert part["offset"] == [expected[0] % 256, expected[1]]
    gust = bindings["projectileStorage"]["area.gust_of_wind.v4"]["phases"]["impact"]["layers"][0]
    part, = gust["partsByFacing"]["N"][0]
    assert part["rect"] == [3, 5, 7, 9] and part["offset"] == [77, 81]
    assert pygame.image.tobytes(pygame.image.load(repo / part["file"]), "RGBA") == pygame.image.tobytes(one, "RGBA")


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.fixture(scope="module", autouse=True)
def display():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((1, 1))
        yield
        pygame.quit()


@pytest.mark.parametrize("spell", ("burning_hands", "thunderwave", "gust_of_wind"))
def test_one_registered_area_renders_identically_with_or_without_recipients(data, spell):
    caster = ActorContact("caster", (3, 5), "SE", 1, elevation_steps=2)
    target = ActorContact("target", (4, 5), "NW", 1, hp=40, elevation_steps=2)
    source = CastInput("area", caster, (), GroundContact(caster.grid, 2), area_direction=(1, 0))
    empty = compile_cast(data, "spell." + spell, source)
    hit = compile_cast(data, "spell." + spell, replace(source,
        applications=(CastApplication("hit", target, spell != "gust_of_wind", 8 if spell != "gust_of_wind" else None,
            32 if spell != "gust_of_wind" else None, damage_type="fire" if spell == "burning_hands" else "thunder"),)))
    time = empty.release_ms + 350
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=.35).with_focus(caster.grid, elevation_steps=2)
        first = cast_media_draw_commands(empty, sample_cast(empty, time), camera, None, {})
        second = cast_media_draw_commands(hit, sample_cast(hit, time), camera, None, {})
        assert first and len(first) == len(second)
        assert any(pygame.surfarray.array_alpha(command.surface).any() for command in first)
        for left, right in zip(first, second, strict=True):
            assert left.destination == right.destination and left.key == right.key
            assert pygame.image.tobytes(left.surface, "RGBA") == pygame.image.tobytes(right.surface, "RGBA")
        assert not sample_cast(hit, time).projectiles
        assert not cast_media_draw_commands(empty, sample_cast(empty, empty.complete_ms), camera, None, {})
    arrival = hit.applications[0].travel_end_ms
    assert arrival == pytest.approx(hit.release_ms + ({"burning_hands": 155, "gust_of_wind": 205,
                                                       "thunderwave": 29 / 144 * 1000}[spell]))
    if spell == "gust_of_wind":
        assert sample_cast(hit, arrival).vitals[0].flash is None
    else:
        assert sample_cast(hit, arrival - .01).vitals[0].flash is None
        assert sample_cast(hit, arrival).vitals[0].flash is not None
        assert sample_cast(hit, arrival + 150).vitals[0].flash is None


@pytest.mark.parametrize("scale", (.35, .5, .75))
def test_contiguous_atlas_bands_match_an_unsplit_translucent_canvas(data, tmp_path, scale):
    """Packing cannot add gaps or double-blended seams at ordinary review zooms."""
    sheet = pygame.Surface((64, 256), pygame.SRCALPHA)
    sheet.fill((40, 80, 120, 97))
    path = tmp_path / "bands.png"
    pygame.image.save(sheet, path)
    asset_id = "test.contiguous_bands"
    authored = data.projectile_assets["area.gust_of_wind.v4"].model_dump(mode="json")
    authored.update(assetId=asset_id, frame={"width": 64, "height": 256, "cols": 1, "rows": 8},
                    anchor={"x": .5, "y": .5}, anchorsByFacing=None)
    authored["phases"] = {"impact": {"start": 0, "frames": 1, "fps": 144, "loop": False}}
    asset = AuthoredProjectileAsset.model_validate_json(json.dumps(authored))
    bands = [{"file": str(path), "rect": [0, top, 64, 32], "offset": [0, top]}
             for top in range(0, 256, 32)]
    storage = ProjectileStorage.model_validate_json(json.dumps({"phases": {"impact": {
        "layers": [{"blendMode": "normal", "partsByFacing": {direction: [bands] for direction in DIRECTIONS}}]}}}))
    packed = replace(data, projectile_assets={**data.projectile_assets, asset_id: asset},
                     projectile_storage={**data.projectile_storage, asset_id: storage})
    actual = pygame.Surface((240, 240), pygame.SRCALPHA)
    for image, destination, blend in registered_media_blits(packed, asset_id, "impact", 0, "E",
            scale=scale, anchor=(120, 120), rows={}):
        actual.blit(image, destination, special_flags=blend)
    expected = pygame.Surface(actual.get_size(), pygame.SRCALPHA)
    rectangle = pygame.Rect(round(120 - 32 * scale), round(120 - 128 * scale),
                            round(64 * scale), round(256 * scale))
    expected.blit(pygame.transform.scale(sheet, rectangle.size), rectangle.topleft)
    assert pygame.image.tobytes(actual, "RGBA") == pygame.image.tobytes(expected, "RGBA")


def test_authored_area_recipes_roundtrip_as_plain_json_including_cell_contacts():
    path = Path(__file__).resolve().parents[2] / "game/data/area_spells/spell-studio-drafts.json"
    original = json.loads(path.read_text())
    recipes = StudioDraftFile.model_validate_json(json.dumps(original))
    serialized = recipes.model_dump_json(by_alias=True)
    restored = StudioDraftFile.model_validate_json(serialized)
    assert restored == recipes
    assert restored.model_dump_json(by_alias=True) == serialized
    for authored, exported in zip(original["spells"], json.loads(serialized)["spells"], strict=True):
        assert exported["contact"] == {"delayMs": 0, "speedTilesPerSecond": None,
                                       "cellsByFacing": None, **authored["contact"]}
        for original_track, exported_track in zip(authored["media"], exported["media"], strict=True):
            for field, value in original_track.items():
                assert exported_track[field] == value
