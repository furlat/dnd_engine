"""Selected control phase views preserve original pixels, registration and ownership."""

from dataclasses import replace
import json
from pathlib import Path
import shutil

import pygame
import pytest
import numpy as np

from devtools.import_control_spells import CASTS, DIRECTIONS, import_bundle
from game.animation import ActorContact, CastInput, GroundContact, compile_cast, view_facing
from game.animation_data import load_animation_data
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage
from game.cast_media import cast_media_placement
from game.projectile_media import ProjectileFrameCache, projectile_frame_layers
from game.projection import Camera, TILE_WIDTH, project_screen
from game.registered_media import registered_material, registered_media_blits


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    root.mkdir()

    def media(prefix: str, frames: int = 576, red: int = 23) -> dict:
        layers = {}
        for depth, green in (("back", 51), ("front", 101)):
            pages = []
            bounds = []
            for first in range(0, frames, 64):
                sheet = pygame.Surface((64, 64), pygame.SRCALPHA)
                for local in range(min(64, frames - first)):
                    frame = first + local
                    if frame == 0:
                        bounds.append(None)
                        continue
                    color = (red, green, frame % 251, 73 + frame % 100)
                    sheet.fill(color, (local % 8 * 8 + 1, local // 8 * 8 + 2, 3, 4))
                    bounds.append([1, 2, 4, 6])
                path = f"{prefix}/{depth}-{first // 64}.png"
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(sheet, root / path)
                pages.append(path)
            layers[depth] = {"pages": pages, "bounds": bounds, "columns": 8, "perPage": 64}
        return {"cell": 8, "frames": frames, "fps": 144, "pivot": [4, 5.25],
                "scale": 1, "layers": layers}

    common = media("common")
    # Unselected entries point at nonexistent files, so accidental selection
    # cannot be hidden by valid replacement media.
    catalog = {name: common for name in (
        "charm_flower", "charm_hearts", "loop_charmed", "blinded", "loop_blinded",
        "deafened", "loop_deafened", "command", "loop_command", "silence", "loop_silence")}
    catalog["charmed"] = {"unselected": "no obsolete application"}
    catalog["sleep"] = {"unselected": "no old finite sleep"}
    catalog["loop_sleep"] = {"unselected": "no old ground pivot"}
    write_json(root / "media.json", catalog)
    write_json(root / "actors.json", {name: {"palette": ["173366", "7799cc"]} for name in CASTS})
    conditions = {}
    for name in ("charmed", "blinded", "deafened", "command"):
        phases = {"sustain": {"asset": "loop_" + name, "frames": [0, 575]}}
        if name != "charmed":
            phases.update(application={"asset": name, "frames": [0, 71]},
                          clear={"asset": name, "frames": [490, 575]})
        if name == "command":
            phases["execute"] = {"asset": name, "frames": [374, 575]}
        conditions[name] = phases
    write_json(root / "lifecycle-contract.json", {"conditions": conditions,
        "silence": {"application": {"asset": "silence", "frames": [0, 215]},
                    "sustain": {"asset": "loop_silence", "frames": [0, 575]}}})
    write_json(root / "color-directions.json", {facing: media(f"colors/{facing}", 192, 31 + row)
                                                for row, facing in enumerate(DIRECTIONS)})
    write_json(root / "color-hand-anchors.json", {facing: [-1 + row / 4, -1.5]
                                                for row, facing in enumerate(DIRECTIONS)})
    sleep = media("sleep-sustain-v1/media")
    for layer in sleep["layers"].values():
        layer["pages"] = [str(Path(path).relative_to("sleep-sustain-v1")) for path in layer["pages"]]
    sleep.update(pivot=[4, 3.25], palette=["173366", "7799cc"])
    write_json(root / "sleep-sustain-v1/manifest.json", sleep)
    hand = pygame.Surface((8, 8), pygame.SRCALPHA)
    hand.fill((21, 155, 231, 83))
    (root / "actors").mkdir()
    for name in CASTS:
        pygame.image.save(hand, root / f"actors/{name}-hands.png")
    return root


def test_import_keeps_authored_owners_and_exact_phase_pixels(source: Path, tmp_path: Path):
    repo = tmp_path / "repo"
    folder = repo / "game/data/control_spells"
    write_json(folder / "bindings.json", {"resources": {"existing": "unchanged.png"},
        "spells": {"spell.command": {"authored": True}}, "projectileStorage": {"other": {"keep": True}}})
    write_json(folder / "projectile-assets.json", [{"assetId": "other", "keep": True}])
    authored = b'{"independent authored behavior":true}\n'
    for path in (folder / "spell-studio-drafts.json", repo / "game/data/condition-recipes.json",
                 repo / "game/data/condition-media.json"):
        path.write_bytes(authored)

    selected = import_bundle(source, repo=repo)
    assert len(selected) == 34
    assert import_bundle(source, repo=repo) == selected
    for path in (folder / "spell-studio-drafts.json", repo / "game/data/condition-recipes.json",
                 repo / "game/data/condition-media.json"):
        assert path.read_bytes() == authored
    bindings = json.loads((folder / "bindings.json").read_text())
    assets = {row["assetId"]: row for row in json.loads((folder / "projectile-assets.json").read_text())}
    assert bindings["spells"] == {"spell.command": {"authored": True}}
    assert bindings["resources"]["existing"] == "unchanged.png"
    assert bindings["projectileStorage"]["other"] == {"keep": True}
    assert assets["other"] == {"assetId": "other", "keep": True}
    for name in CASTS:
        assert (repo / bindings["resources"][f"/control-spells/{name}/cast.png"]).read_bytes() == (
            source / f"actors/{name}-hands.png").read_bytes()

    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        base = load_animation_data()
        records = {identity: AuthoredProjectileAsset.model_validate_json(json.dumps(assets[identity]))
                   for identity in selected}
        storage = {identity: ProjectileStorage.model_validate_json(json.dumps(bindings["projectileStorage"][identity]))
                   for identity in selected}
        data = replace(base, projectile_assets=records, projectile_storage=storage, media_root=repo)
        cache = ProjectileFrameCache(limit_bytes=1024 * 1024)
        for stem, first, count in (("blinded.application", 0, 72), ("blinded.removal", 490, 86),
                                   ("command.execute", 374, 202), ("silence.application", 0, 216),
                                   ("sleep.sustain", 0, 576)):
            for side, green in (("back", 51), ("front", 101)):
                identity = f"control.{stem}.{side}"
                asset = records[identity]
                assert asset.phases.impact is not None and asset.phases.impact.frames == count
                assert asset.fps == 144 and asset.anchor.y == (3.25 if stem == "sleep.sustain" else 5.25) / 8
                assert storage[identity].phases["impact"].layers[0].partsByFacing is None
                for local in (0, 63, count - 1):
                    frame = first + local
                    for facing in DIRECTIONS:
                        images = projectile_frame_layers(data, asset, "impact", local, facing,
                            registered_material(identity, 1), {}, cache=cache)
                        if frame == 0:
                            assert not images
                            continue
                        image, = images
                        assert image.offset == (1, 2) and image.image.size == (3, 4)
                        assert tuple(image.image.get_at((0, 0))) == (23, green, frame % 251, 73 + frame % 100)
                        blit, = registered_media_blits(data, identity, "impact", local, facing,
                                                      scale=2, anchor=(100, 100), rows={})
                        assert blit[1] == (94, round(100 + (2 - asset.anchor.y * 8) * 2))
        for row, facing in enumerate(DIRECTIONS):
            identity = "control.color_spray.front"
            asset = records[identity]
            assert asset.anchorsByFacing is not None
            anchor = asset.anchorsByFacing[facing]
            assert (anchor.x, anchor.y) == ((3 + row / 4) / 8, 3.75 / 8)
            image, = projectile_frame_layers(data, asset, "impact", 191, facing,
                registered_material(identity, 1), {}, cache=cache)
            assert tuple(image.image.get_at((0, 0))) == (31 + row, 101, 191, 164)
    finally:
        pygame.quit()


def test_control_reimport_preserves_selected_color_spray_surface_delivery(source: Path, tmp_path: Path):
    repo = tmp_path / 'repo'
    folder = repo / 'game/data/control_spells'
    current = Path(__file__).resolve().parents[2] / 'game/data/control_spells'
    folder.mkdir(parents=True)
    for name in ('bindings.json', 'projectile-assets.json'):
        shutil.copyfile(current / name, folder / name)
    before_storage = json.loads((folder / 'bindings.json').read_text())['projectileStorage']
    before_assets = {row['assetId']: row for row in json.loads((folder / 'projectile-assets.json').read_text())}
    shutil.rmtree(source / 'colors')  # This superseded raster delivery is not needed.

    imported = import_bundle(source, repo=repo)

    after_storage = json.loads((folder / 'bindings.json').read_text())['projectileStorage']
    after_assets = {row['assetId']: row for row in json.loads((folder / 'projectile-assets.json').read_text())}
    for side in ('back', 'front'):
        identity = 'control.color_spray.' + side
        assert identity not in imported
        assert after_storage[identity] == before_storage[identity]
        assert after_assets[identity] == before_assets[identity]


@pytest.fixture(scope="module")
def authored():
    return load_animation_data()


@pytest.mark.parametrize("direction", DIRECTIONS)
@pytest.mark.parametrize("body_scale,width_scale", ((1., 1.), (.7, 1.2)))
def test_color_cone_emits_from_actual_release_hand_in_every_camera(authored, direction, body_scale, width_scale):
    axes = dict(zip(DIRECTIONS, ((1, -1), (1, 0), (1, 1), (0, 1),
                                 (-1, 1), (-1, 0), (-1, -1), (0, -1)), strict=True))
    caster = ActorContact("caster", (3, 5), "S", body_scale, elevation_steps=2,
                          visual_scale_x=width_scale)
    timeline = compile_cast(authored, "spell.color_spray", CastInput("color", caster, (),
        GroundContact(caster.grid, 2), area_direction=axes[direction]))
    assert timeline.facing == direction
    glow = timeline.recipe.cast.weaponGlow
    assert glow is not None and glow.sourceSheet is not None
    sheet = pygame.image.load(authored.resources[glow.sourceSheet])
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=.75).with_focus(caster.grid, elevation_steps=2)
        facing = view_facing(timeline.facing, quadrant, authored)
        cell = sheet.subsurface((7 * 128, DIRECTIONS.index(facing) * 128, 128, 128))
        # The exporter measured this exact release-frame hand-alpha centroid.
        # Read the real hand pixels, independent of the authored socket records.
        alpha = pygame.surfarray.array_alpha(cell).astype(float)
        xx, yy = np.indices(alpha.shape)
        hand = (float((xx * alpha).sum() / alpha.sum()), float((yy * alpha).sum() / alpha.sum()))
        ground = project_screen(caster.grid, camera, elevation_steps=2)
        factor = body_scale * TILE_WIDTH / authored.rig.TILE_W * camera.zoom
        expected = (ground[0] + (hand[0] - 64) * factor * width_scale,
                    ground[1] + (hand[1] - 87) * factor)
        # Original export registration: 1.62x1.8 reference body and the same
        # fixed-size three-cell cone. Re-registration must remove this baked
        # hand displacement, not scale the cone with the actor.
        export_scale = .8888888895833333
        emitted_pixel = (384 + (hand[0] - 64) * 1.62 / export_scale,
                         425.5692192 + (hand[1] - 87) * 1.8 / export_scale)
        for track in timeline.recipe.media:
            placement = cast_media_placement(timeline, track, caster, camera)
            # The paired packet pivot is the whole-effect ground origin;
            # registration subtracts the baked emission point before applying
            # the same live hand socket. The field dimensions stay fixed.
            actual = (placement.anchor[0] + (emitted_pixel[0] - 384) * placement.scale,
                      placement.anchor[1] + (emitted_pixel[1] - 425.56921900345867) * placement.scale)
            assert placement.scale == pytest.approx(export_scale * camera.zoom)
            assert actual == pytest.approx(expected, abs=.001)
