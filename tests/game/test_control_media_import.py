"""Pinned Slow delivery keeps registered pixels and omits the duplicate endpoint."""

import hashlib
import json

import pytest

from devtools.import_control_media import import_slow
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage


@pytest.fixture
def packet(tmp_path):
    source = tmp_path / "source"
    handoff = source / "production-handoff"
    handoff.mkdir(parents=True)
    payload = b"atlas original bytes"
    (source / "atlas.png").write_bytes(payload)
    (handoff / "SLOW_SHA256SUMS").write_text(f"{hashlib.sha256(payload).hexdigest()}  atlas.png\n")
    row = {"frames": 129, "loopFrames": 128, "loopSeconds": 4, "duplicateEndpoint": 128,
        "cell": 384, "pivot": [192, 241.883063257728], "palette": ["292526", "b14e50"],
        "cameras": {str(q): {"layers": {side: {"pages": ["atlas.png"], "frames": [
            {"page": 0, "source": [frame, q, 1, 1], "offset": [163, 171]}
            for frame in range(129)]} for side in ("back", "front")}} for q in range(4)}}
    (handoff / "slow-approved-media.json").write_text(json.dumps({"slow_crimson_v7": row}))
    return source, tmp_path / "repo", row


def test_complete_loop_preserves_pages_registration_and_authored_recipes(packet):
    source, repo, _ = packet
    folder = repo / "game/data/control_media"
    folder.mkdir(parents=True)
    recipe = {"schema": "dnd.spellStudioDrafts", "version": 3, "spells": []}
    (folder / "spell-studio-drafts.json").write_text(json.dumps(recipe))
    (folder / "bindings.json").write_text(json.dumps({"resources": {}, "spells": {"retained": {"author": "unchanged"}}}))
    assert len(import_slow(source, repo=repo)) == 2
    assert json.loads((folder / "spell-studio-drafts.json").read_text()) == recipe
    bindings = json.loads((folder / "bindings.json").read_text())
    assert bindings["spells"]["retained"] == {"author": "unchanged"}
    assets = {row["assetId"]: AuthoredProjectileAsset.model_validate_json(json.dumps(row))
        for row in json.loads((folder / "projectile-assets.json").read_text())}
    for identity, row in bindings["projectileStorage"].items():
        ProjectileStorage.model_validate_json(json.dumps(row))
        assert assets[identity].anchor.y == pytest.approx(241.883063257728 / 384)
        assert assets[identity].palettePreview.colors == (0x292526, 0xb14e50)
        for q, facing in enumerate(("E", "S", "W", "N")):
            frames = row["phases"]["impact"]["layers"][0]["partsByFacing"][facing]
            assert len(frames) == 128
            assert frames[-1][0]["rect"] == [127, q, 1, 1]
            assert frames[-1][0]["offset"] == [163, 171]
            assert (repo / frames[0][0]["file"]).read_bytes() == (source / "atlas.png").read_bytes()


@pytest.mark.parametrize("failure", ("checksum", "endpoint", "view", "frame", "path"))
def test_invalid_packet_never_partially_installs(packet, failure):
    source, repo, row = packet
    if failure == "checksum":
        (source / "atlas.png").write_bytes(b"corrupt")
    elif failure == "endpoint":
        row["loopFrames"] = 129
    elif failure == "view":
        del row["cameras"]["3"]
    elif failure == "frame":
        row["cameras"]["2"]["layers"]["front"]["frames"].pop()
    else:
        row["cameras"]["3"]["layers"]["front"]["pages"] = ["../../outside.png"]
    (source / "production-handoff/slow-approved-media.json").write_text(json.dumps({"slow_crimson_v7": row}))
    with pytest.raises(ValueError):
        import_slow(source, repo=repo)
    assert not repo.exists()
