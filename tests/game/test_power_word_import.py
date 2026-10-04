"""An invalid bank cannot alter the installed release or preserved originals."""

import hashlib
import json
from pathlib import Path

import pytest

from devtools.import_necrotic_media import import_necrotic_media
from devtools.media_delivery import contained_media_path


@pytest.fixture
def delivery(tmp_path):
    source, preserved, production, repo = (tmp_path / name for name in ("source", "archive", "production", "repo"))
    source.mkdir()
    production.mkdir()
    (source / "atlas.png").write_bytes(b"original payload")
    digest = hashlib.sha256(b"original payload").hexdigest()
    row = dict(frames=1, cell=384, fps=32, pivot=[192, 250], palette=["ffffff"],
        layers={side: dict(pages=["atlas.png"], frames=[dict(page=0, source=[0, 0, 10, 10], offset=[190, 200])])
                for side in ("back", "front")}, sha256={"atlas.png": digest})
    manifest = {name: dict(row, revision="native-family-v1" if name == "stunned" else "native-family-v2")
                for name in ("kill", "stun", "stunned")}
    (source / "media.json").write_text(json.dumps(manifest))
    for name in ("HANDOFF.md", "APPROVED_HANDOFF.md", "NOTES.md", "delivery-receipt.json"):
        (source / name).write_text("original metadata")
    (production / "art-manifest.json").write_text('{"files": [], "total_bytes": 0}')
    return source, preserved, production, repo


@pytest.mark.parametrize("defect", ("negative-page", "missing-side", "zero-frames", "crop", "metadata"))
def test_import_rejects_incomplete_or_conflicting_delivery_before_writes(delivery, defect):
    source, preserved, production, repo = delivery
    original = (production / "art-manifest.json").read_bytes()
    manifest = json.loads((source / "media.json").read_text())
    last = manifest["stunned"]
    if defect == "negative-page":
        last["layers"]["front"]["frames"][0]["page"] = -1
    elif defect == "missing-side":
        del last["layers"]["back"]
    elif defect == "zero-frames":
        last["frames"] = 0
    elif defect == "crop":
        last["layers"]["front"]["frames"][0]["offset"] = [383, 383]
    else:
        preserved.mkdir()
        (preserved / "HANDOFF.md").write_text("retained earlier original")
    (source / "media.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        import_necrotic_media(source, preserved=preserved, production=production, repo=repo)
    assert (production / "art-manifest.json").read_bytes() == original
    assert not repo.exists()
    assert not (preserved / "atlas.png").exists()


@pytest.mark.parametrize("address", ("../outside.png", "game/assets/../../outside.png", "/tmp/outside.png"))
def test_archive_addresses_reject_traversal(tmp_path, address):
    with pytest.raises(ValueError):
        contained_media_path(tmp_path, address)


def test_archive_destination_cannot_follow_a_symlink_outside_its_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "escape").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        contained_media_path(root, "escape/outside.png")


def test_import_preserves_bytes_and_existing_recipe_on_repeat(delivery):
    source, preserved, production, repo = delivery
    receipt = import_necrotic_media(source, preserved=preserved, production=production, repo=repo)
    recipe = repo / "game/data/necrotic_media/power-words-draft.json"
    recipe.write_text("human authored recipe")
    repeated = import_necrotic_media(source, preserved=preserved, production=production, repo=repo)
    assert repeated == receipt
    assert recipe.read_text() == "human authored recipe"
    assert (preserved / "atlas.png").read_bytes() == (source / "atlas.png").read_bytes()
    assert (repo / "game/assets/necrotic_media/atlas.png").read_bytes() == (source / "atlas.png").read_bytes()
