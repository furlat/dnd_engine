"""Curse import preserves frames/pivots and rejects corrupt deliveries atomically."""

import hashlib
import json
from pathlib import Path

import pygame
import pytest

from devtools.import_curse_media import BANKS, import_bundle
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage


def source_packet(root: Path) -> Path:
    root.mkdir()
    atlas = pygame.Surface((96, 1), pygame.SRCALPHA)
    for i in range(96):
        atlas.set_at((i, 0), (i, 37, 121, 73 + i))
    pygame.image.save(atlas, root / "bank.png")
    digest = hashlib.sha256((root / "bank.png").read_bytes()).hexdigest()
    (root / "SOURCE-SHA256SUMS").write_text(f"{digest}  bank.png\n")
    banks = {}
    for name in BANKS:
        count = 96 if "_loop_" in name else 40
        banks[name] = {"cell": 8, "ortho": 8, "targetY": 1, "frames": count,
            "pivot": [4, 5.25], "palette": ["112233"], "cameras": {
                str(q): {"layers": {side: {"pages": ["bank.png"], "frames": [
                    None if i == 0 else {"page": 0, "source": [i, 0, 1, 1], "offset": [q, 3]}
                    for i in range(count)]} for side in ("back", "front")}} for q in range(4)}}
    (root / "curse-assets.json").write_text(json.dumps({"schema": "codexfx.bestow-curse.v1",
        "fps": 32, "assets": banks}))
    return root


def test_phase_views_keep_original_samples_and_do_not_write_behavior(tmp_path):
    source = source_packet(tmp_path / "source")
    repo = tmp_path / "repo"
    folder = repo / "game/data/curse_media"
    folder.mkdir(parents=True)
    recipe = folder / "spell-studio-drafts.json"
    recipe.write_bytes(b'{"independently authored":true}\n')
    selected = import_bundle(source, source_root=source, repo=repo)
    assert len(selected) == 40
    assert import_bundle(source, source_root=source, repo=repo) == selected
    assert recipe.read_bytes() == b'{"independently authored":true}\n'
    storage = json.loads((folder / "bindings.json").read_text())["projectileStorage"]
    assets = {r["assetId"]: AuthoredProjectileAsset.model_validate_json(json.dumps(r))
        for r in json.loads((folder / "projectile-assets.json").read_text())}
    for name in BANKS:
        for side in ("back", "front"):
            phase = "hold" if "_loop_" in name else "finite"
            identity = f"curse.{name}.{phase}.{side}"
            ProjectileStorage.model_validate_json(json.dumps(storage[identity]))
            assert assets[identity].anchor.y == 5.25 / 8
            views = storage[identity]["phases"]["impact"]["layers"][0]["partsByFacing"]
            for q, direction in enumerate(("E", "S", "W", "N")):
                frames = views[direction]
                assert len(frames) == (64 if phase == "hold" else 40)
                first = frames[0 if phase == "hold" else 1][0]
                assert first["rect"] == [32 if phase == "hold" else 1, 0, 1, 1]
                assert first["offset"] == [q, 3]
                assert (repo / first["file"]).read_bytes() == (source / "bank.png").read_bytes()
    identity = "curse.curse_rings_loop_v13.apply.back"
    frames = storage[identity]["phases"]["impact"]["layers"][0]["partsByFacing"]["E"]
    assert not frames[0] and len(frames) == 32
    assert frames[-1][0]["rect"] == [31, 0, 1, 1]


@pytest.mark.parametrize("failure", ("checksum", "missing_view", "missing_frame", "escaping_path"))
def test_invalid_packet_does_not_partially_install(tmp_path, failure):
    source = source_packet(tmp_path / "source")
    manifest = json.loads((source / "curse-assets.json").read_text())
    bank = manifest["assets"][BANKS[-1]]
    if failure == "checksum":
        (source / "bank.png").write_bytes(b"corrupt")
    elif failure == "missing_view":
        del bank["cameras"]["3"]
    elif failure == "missing_frame":
        bank["cameras"]["3"]["layers"]["front"]["frames"].pop()
    else:
        bank["cameras"]["3"]["layers"]["front"]["pages"] = ["../outside.png"]
    (source / "curse-assets.json").write_text(json.dumps(manifest))
    repo = tmp_path / "repo"
    with pytest.raises(ValueError):
        import_bundle(source, source_root=source, repo=repo)
    assert not repo.exists()
