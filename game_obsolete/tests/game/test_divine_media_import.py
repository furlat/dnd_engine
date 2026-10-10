"""Accepted divine phase registration preserves pixels and rejects bad packets."""

import hashlib
import json

import pytest

from devtools.import_divine_media import EFFECTS, import_bundle
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage


@pytest.fixture
def packet(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    payload = b"opaque atlas payload: importer must preserve exact bytes"
    (source / "atlas.png").write_bytes(payload)
    (source / "SHA256SUMS").write_text(f"{hashlib.sha256(payload).hexdigest()}  atlas.png\n")
    manifest = {name: {"fps": 32, "cell": 512, "frames": 128,
        "pivot": [256, 292.9504169], "palette": ["453052"], "cameras": {
            str(q): {"layers": {side: {"pages": ["atlas.png"], "frames": [
                None if frame == 0 else {"page": 0, "source": [frame, 0, 1, 1], "offset": [q, 7]}
                for frame in range(128)]} for side in ("back", "front")}} for q in range(4)}}
        for name in EFFECTS}
    for name in EFFECTS[:2]:
        manifest[name]["hold"] = [47, 111]
    (source / "media.json").write_text(json.dumps(manifest))
    return source, tmp_path / "repo", manifest


def test_phase_views_preserve_source_registration_and_pages(packet):
    source, repo, _ = packet
    assert len(import_bundle(source, repo=repo)) == 18
    folder = repo / "game/data/divine_media"
    assets = {row["assetId"]: AuthoredProjectileAsset.model_validate_json(json.dumps(row))
        for row in json.loads((folder / "projectile-assets.json").read_text())}
    bindings = json.loads((folder / "bindings.json").read_text())
    assert not bindings["spells"]
    for identity, row in bindings["projectileStorage"].items():
        ProjectileStorage.model_validate_json(json.dumps(row))
        assert assets[identity].anchor.y == pytest.approx(292.9504169 / 512)
        for q, facing in enumerate(("E", "S", "W", "N")):
            frames = row["phases"]["impact"]["layers"][0]["partsByFacing"][facing]
            first = 47 if ".hold." in identity else 1
            sample = frames[0 if first == 47 else 1][0]
            assert sample["rect"] == [first, 0, 1, 1] and sample["offset"] == [q, 7]
            assert (repo / sample["file"]).read_bytes() == (source / "atlas.png").read_bytes()
    assert not (folder / "spell-studio-drafts.json").exists()


def test_approved_symbols_keep_head_registration_and_authored_recipes(packet):
    source, repo, manifest = packet
    symbols = {name: manifest[f"divine_condition_{name}"] for name in ("blinded", "deafened")}
    (source / "shared-symbols-approved.json").write_text(json.dumps(symbols))
    folder = repo / "game/data/divine_media"
    folder.mkdir(parents=True)
    authored = {"schema": "dnd.spellStudioDrafts", "version": 3, "spells": []}
    (folder / "spell-studio-drafts.json").write_text(json.dumps(authored))
    (folder / "bindings.json").write_text(json.dumps({"resources": {}, "spells": {"retained": {"author": "unchanged"}}}))
    import_bundle(source, repo=repo)
    assert json.loads((folder / "spell-studio-drafts.json").read_text()) == authored
    assert json.loads((folder / "bindings.json").read_text())["spells"]["retained"] == {"author": "unchanged"}
    assets = {row["assetId"]: row for row in json.loads((folder / "projectile-assets.json").read_text())}
    for condition in ("blinded", "deafened"):
        for side in ("back", "front"):
            row = assets[f"divine.divine_condition_{condition}.sustain.{side}"]
            assert row["phases"]["impact"]["loop"] is True
            assert row["anchorsByFacing"]["E"]["y"] == 8 / 512
            assert row["anchor"]["y"] == pytest.approx(292.9504169 / 512)


@pytest.mark.parametrize("failure", ("checksum", "view", "frame", "hold"))
def test_invalid_delivery_does_not_partially_install(packet, failure):
    source, repo, manifest = packet
    row = manifest[EFFECTS[-1]]
    if failure == "checksum":
        (source / "atlas.png").write_bytes(b"corrupt")
    elif failure == "view":
        del row["cameras"]["3"]
    elif failure == "frame":
        row["cameras"]["2"]["layers"]["back"]["frames"].pop()
    else:
        row["hold"] = [96, 140]
    (source / "media.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        import_bundle(source, repo=repo)
    assert not repo.exists()
