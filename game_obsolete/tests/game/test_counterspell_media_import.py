"""Counterspell intake preserves pixels and converts atlas registration once."""

from dataclasses import replace
import json
from pathlib import Path

import pygame

from devtools.import_counterspell_media import import_bundle
from game.animation_data import load_animation_data
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage
from game.registered_media import registered_media_blits


def test_import_keeps_camera_pixels_pivot_and_media_only_scope(tmp_path: Path) -> None:
    source, repo = tmp_path / "source", tmp_path / "repo"
    source.mkdir()
    shared = pygame.Surface((18, 3), pygame.SRCALPHA)
    banks = {}
    keys = [f"{outcome}-q{quadrant}" for outcome in ("success", "failure") for quadrant in range(4)]
    for index, key in enumerate([*keys, "dissipation"]):
        shared.fill((31 + index, 67, 103, 211), (index * 2, 0, 2, 3))
        banks[key] = {"pages": ["shared.png"], "fps": 144,
            "nativeSize": [8, 10], "nativePivot": [3, 7], "frames": [
                {"page": 0, "source": [index * 2, 0, 2, 3], "offset": [-1, -2]}, None]}
    banks["globe"] = {"pages": ["must-not-be-copied.png"]}
    pygame.image.save(shared, source / "shared.png")
    (source / "actors").mkdir()
    pygame.image.save(shared, source / "actors/counterspell-hands.png")
    (source / "media.json").write_text(json.dumps(banks))
    (source / "manifest.json").write_text(json.dumps({"media": "media.json", "recipes": {
        "counterspell": {"success": keys[:4], "failure": keys[4:], "palette": ["1f4367"]},
        "incoming_dissipation": {"media": "dissipation"},
        "globe_of_invulnerability": {"media": "globe"}}}))
    authored = repo / "game/data/interruptions.json"
    authored.parent.mkdir(parents=True)
    authored.write_bytes(b'"independent authored timing"\n')

    selected = import_bundle(source, repo=repo)
    assert len(selected) == 9 and import_bundle(source, repo=repo) == selected
    assert authored.read_bytes() == b'"independent authored timing"\n'
    copied = list((repo / "game/assets/counterspell_media").rglob("*.png"))
    assert len(copied) == 2
    assert all(path.read_bytes() == (source / "shared.png").read_bytes() for path in copied)
    folder = repo / "game/data/counterspell_media"
    assets = {row["assetId"]: AuthoredProjectileAsset.model_validate_json(json.dumps(row))
              for row in json.loads((folder / "projectile-assets.json").read_text())}
    bindings = json.loads((folder / "bindings.json").read_text())
    assert (repo / bindings["resources"]["/counterspell-media/cast-hands.png"]).read_bytes() == (
        source / "actors/counterspell-hands.png").read_bytes()
    storage = {identity: ProjectileStorage.model_validate_json(json.dumps(row))
               for identity, row in bindings["projectileStorage"].items()}
    data = replace(load_animation_data(), projectile_assets=assets, projectile_storage=storage, media_root=repo)

    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        for index, identity in enumerate(selected):
            asset = assets[identity]
            assert asset.fps == 144 and asset.anchor.x == 3 / 8 and asset.anchor.y == 7 / 10
            assert asset.phases.impact is not None and not asset.phases.impact.loop
            for facing in ("N", "E"):
                image, destination, blend = registered_media_blits(
                    data, identity, "impact", 0, facing, scale=2, anchor=(100, 100), rows={})[0]
                assert destination == (98, 96) and image.get_size() == (4, 6)
                assert tuple(image.get_at((0, 0))) == (31 + index, 67, 103, 211)
                assert blend == 0
                assert not registered_media_blits(
                    data, identity, "impact", 1, facing, scale=2, anchor=(100, 100), rows={})
    finally:
        pygame.quit()
