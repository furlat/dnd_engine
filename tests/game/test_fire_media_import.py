"""Fixed-origin fire delivery keeps source samples, phase boundaries and recipes."""

import hashlib
import json

import pytest

from devtools.import_fire_media import import_continual_flame, import_flame_strike
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage


@pytest.fixture
def packet(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    payload = b"accepted original atlas bytes"
    (source / "atlas.png").write_bytes(payload)
    (source / "SHA256SUMS").write_text(f"{hashlib.sha256(payload).hexdigest()}  atlas.png\n")
    row = {"frames": 112, "fps": 32, "hold": [48, 112], "fixedFlameBase": True,
        "cell": 512, "pivot": [256, 292.9504172279467], "palette": ["644761", "fff0c8"],
        "cameras": {str(q): {"layers": {side: {"pages": ["atlas.png"], "frames": [
            None if frame < 12 else {"page": 0, "source": [frame, q, 1, 1], "offset": [245, 247]}
            for frame in range(112)]} for side in ("back", "front")}} for q in range(4)}}
    (source / "media.json").write_text(json.dumps({"continual_anchor_v41_0": row}))
    return source, tmp_path / "repo", row


def test_onset_and_maintained_windows_preserve_anchor_and_recipe(packet):
    source, repo, _ = packet
    folder = repo / "game/data/fire_media"
    folder.mkdir(parents=True)
    recipe = {"schema": "dnd.spellStudioDrafts", "version": 3, "spells": []}
    (folder / "spell-studio-drafts.json").write_text(json.dumps(recipe))
    (folder / "bindings.json").write_text(json.dumps({"spells": {"retained": {"author": "unchanged"}}}))
    assert len(import_continual_flame(source, repo=repo)) == 4
    assert json.loads((folder / "spell-studio-drafts.json").read_text()) == recipe
    bindings = json.loads((folder / "bindings.json").read_text())
    assert bindings["spells"]["retained"] == {"author": "unchanged"}
    assets = {row["assetId"]: AuthoredProjectileAsset.model_validate_json(json.dumps(row))
        for row in json.loads((folder / "projectile-assets.json").read_text())}
    for identity, storage in bindings["projectileStorage"].items():
        ProjectileStorage.model_validate_json(json.dumps(storage))
        phase = "apply" if ".apply." in identity else "hold"
        asset = assets[identity]
        assert asset.anchor.y == pytest.approx(292.9504172279467 / 512)
        assert asset.palettePreview.colors == (0x644761, 0xfff0c8)
        for q, facing in enumerate(("E", "S", "W", "N")):
            frames = storage["phases"]["impact"]["layers"][0]["partsByFacing"][facing]
            assert len(frames) == (48 if phase == "apply" else 64)
            assert frames[0] == ([] if phase == "apply" else [{
                "file": "game/assets/fire_media/atlas.png", "rect": [48, q, 1, 1], "offset": [245, 247]}])
            assert frames[-1][0]["rect"] == [47 if phase == "apply" else 111, q, 1, 1]
            assert (repo / frames[-1][0]["file"]).read_bytes() == (source / "atlas.png").read_bytes()


@pytest.mark.parametrize("failure", ("checksum", "window", "view", "frame", "path"))
def test_invalid_source_cannot_install_partial_fire_bank(packet, failure):
    source, repo, row = packet
    if failure == "checksum":
        (source / "atlas.png").write_bytes(b"corrupt")
    elif failure == "window":
        row["hold"] = [47, 112]
    elif failure == "view":
        del row["cameras"]["3"]
    elif failure == "frame":
        row["cameras"]["2"]["layers"]["front"]["frames"].pop()
    else:
        row["cameras"]["3"]["layers"]["front"]["pages"] = ["../../outside.png"]
    (source / "media.json").write_text(json.dumps({"continual_anchor_v41_0": row}))
    with pytest.raises(ValueError):
        import_continual_flame(source, repo=repo)
    assert not repo.exists()


def test_finite_pillar_preserves_all_cameras_and_existing_flame_entries(packet):
    source, repo, row = packet
    import_continual_flame(source, repo=repo)
    row = dict(row)
    row.update(frames=96, radiusFeet=10, heightFeet=40, cell=1024,
        pivot=[512, 770.6529205956267])
    row.pop("hold")
    for camera in row["cameras"].values():
        for layer in camera["layers"].values():
            layer["frames"] = layer["frames"][:96]
    (source / "media.json").write_text(json.dumps({"flame_strike": row}))
    assert len(import_flame_strike(source, repo=repo)) == 2
    folder = repo / "game/data/fire_media"
    assets = {r["assetId"]: AuthoredProjectileAsset.model_validate_json(json.dumps(r))
        for r in json.loads((folder / "projectile-assets.json").read_text())}
    assert len(assets) == 6
    for side in ("back", "front"):
        asset = assets[f"fire.flame_strike.finite.{side}"]
        assert asset.phases.impact is not None
        assert asset.phases.impact.frames == 96 and not asset.phases.impact.loop
        assert asset.anchor.y == pytest.approx(770.6529205956267 / 1024)
