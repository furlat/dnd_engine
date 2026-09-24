"""Sparse healing atlases preserve pixels, camera identity and full-canvas origin."""

from dataclasses import replace
import json

import pygame
import pytest

from devtools.import_healing_media import import_bundle
from game.animation import ActorContact, CastApplication, CastInput, compile_cast, view_facing
from game.animation_data import load_animation_data
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage
from game.projectile_media import projectile_frame_layers
from game.registered_media import registered_material
from game.cast_media import cast_media_placement
from game.projection import Camera, project_screen
from tests.game.test_projectile_media import display as display


def test_partial_healing_delivery_preserves_previously_selected_layers(tmp_path):
    source, repo = tmp_path / 'source', tmp_path / 'repo'
    source.mkdir()
    (source / 'media-four-camera.json').write_text('{}')
    folder = repo / 'game/data/healing_spells'
    folder.mkdir(parents=True)
    assets = [{'assetId': 'healing.already_selected.back', 'retained': True}]
    storage = {'healing.already_selected.back': {'phases': {'impact': {'layers': []}}}}
    (folder / 'projectile-assets.json').write_text(json.dumps(assets))
    (folder / 'bindings.json').write_text(json.dumps({'resources': {}, 'projectileStorage': storage}))
    assert import_bundle(source, repo=repo) == ()
    assert json.loads((folder / 'projectile-assets.json').read_text()) == assets
    assert json.loads((folder / 'bindings.json').read_text())['projectileStorage'] == storage


def test_sparse_import_preserves_camera_pixels_pivot_and_separate_recipe(tmp_path):
    source, repo = tmp_path / "source", tmp_path / "repo"
    source.mkdir()
    cameras = {}
    for q in range(4):
        layers = {}
        for side, blue in (("back", 71), ("front", 121)):
            image = pygame.Surface((9, 8), pygame.SRCALPHA)
            image.fill((31 + q * 40, 123, blue, 93), (2, 3, 3, 2))
            filename = f"q{q}-{side}.png"
            pygame.image.save(image, source / filename)
            layers[side] = {"pages": [filename], "frames": [None,
                {"page": 0, "source": [2, 3, 3, 2], "offset": [4, 6]}]}
        cameras[str(q)] = {"layers": layers}
    document = {"lesser_restoration": {"cameras": cameras, "cell": 16, "fps": 144,
        "frames": 2, "pivot": [8, 9.25], "palette": ["336699"]}}
    (source / "media-four-camera.json").write_text(json.dumps(document))
    hand = source / "actors/lesser_restoration/Special1-glow.png"
    hand.parent.mkdir(parents=True)
    pygame.image.save(image, hand)
    folder = repo / "game/data/healing_spells"
    folder.mkdir(parents=True)
    recipe = folder / "spell-studio-drafts.json"
    recipe.write_text('{"independently authored":"unchanged"}\n')
    imported = import_bundle(source, repo=repo)
    assert set(imported) == {"healing.lesser_restoration.back", "healing.lesser_restoration.front"}
    assert recipe.read_text() == '{"independently authored":"unchanged"}\n'
    raw = json.loads((folder / "bindings.json").read_text())["projectileStorage"]
    assets = [AuthoredProjectileAsset.model_validate_json(json.dumps(row))
              for row in json.loads((folder / "projectile-assets.json").read_text())]
    data = load_animation_data()
    # The loader normally resolves these authored paths relative to repo.
    for row in raw.values():
        for layer in row["phases"]["impact"]["layers"]:
            for frames in layer["partsByFacing"].values():
                for parts in frames:
                    for part in parts:
                        part["file"] = str(repo / part["file"])
    changed = replace(data, projectile_storage={key: ProjectileStorage.model_validate_json(json.dumps(row))
                                                for key, row in raw.items()})
    for asset in assets:
        assert asset.anchor.x == .5 and asset.anchor.y == 9.25 / 16
        for q in range(4):
            facing = view_facing("E", q, changed)
            assert not projectile_frame_layers(changed, asset, "impact", 0, facing,
                                                registered_material(asset.assetId, 1), {})
            frame, = projectile_frame_layers(changed, asset, "impact", 1, facing,
                                              registered_material(asset.assetId, 1), {})
            assert frame.image.get_size() == (3, 2)
            assert tuple(frame.image.get_at((0, 0))) == (31 + q * 40, 123, 71 if asset.assetId.endswith("back") else 121, 93)
            assert frame.offset == (4, 6)
    document["lesser_restoration"]["cameras"].pop("3")
    (source / "media-four-camera.json").write_text(json.dumps(document))
    with pytest.raises(ValueError, match="four native camera"):
        import_bundle(source, repo=repo)


def test_production_six_spells_have_four_camera_ground_registration():
    data = load_animation_data()
    for name in ("aid", "lesser_restoration", "greater_restoration", "heal", "mass_cure_wounds", "mass_heal"):
        draft = data.drafts["spell." + name]
        if name == "aid":
            continue
        assert {(track.attachment, track.viewFacing, track.depth) for track in draft.media} == {
            ("target_ground", "E", "behind_body"), ("target_ground", "E", "front_body")}
        for track in draft.media:
            asset = data.projectile_assets[track.assetId]
            assert asset.frame.width == asset.frame.height == 512
            assert asset.anchor.x == .5 and asset.anchor.y == pytest.approx(292.9504169 / 512)
            layer, = data.projectile_storage[track.assetId].phases["impact"].layers
            assert layer.partsByFacing is not None
            assert asset.phases.impact is not None
            for q in range(4):
                parts = layer.partsByFacing[view_facing("E", q, data)]
                assert len(parts) == asset.phases.impact.frames
                assert all(f"q{q}" in str(part.file) for frame in parts for part in frame)


def test_recipient_media_follows_actor_ground_height_and_uniform_scale():
    data = load_animation_data()
    target = ActorContact("recipient", (4, 3), "N", 1, elevation_steps=2)
    caster = ActorContact("caster", (3, 3), "S", 1)
    source = CastInput("healing", caster, (CastApplication("heal", target, False, None, None),))
    timeline = compile_cast(data, "spell.heal", source)
    for q in range(4):
        camera = Camera(quadrant=q)
        for track in timeline.recipe.media:
            first = cast_media_placement(timeline, track, target, camera)
            larger = replace(target, grid=(7, 8), visual_scale=1.5, elevation_steps=3)
            second = cast_media_placement(timeline, track, larger, camera)
            assert first.anchor == project_screen(target.grid, camera, elevation_steps=2)
            assert second.anchor == project_screen(larger.grid, camera, elevation_steps=3)
            assert second.scale == pytest.approx(first.scale * 1.5)
            assert first.rotation == second.rotation == 0
