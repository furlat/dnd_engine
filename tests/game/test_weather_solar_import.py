"""Selected weather deliveries are validated before the installed release changes."""

import hashlib
import json

from PIL import Image
import pytest

from devtools.import_weather_solar_media import import_weather_solar


@pytest.fixture
def delivery(tmp_path):
    source, preserved, production, repo = (tmp_path / name for name in ("source", "archive", "production", "repo"))
    source.mkdir()
    production.mkdir()
    Image.new("RGBA", (8, 8), (65, 100, 130, 255)).save(source / "atlas.png")
    digest = hashlib.sha256((source / "atlas.png").read_bytes()).hexdigest()
    layer = {"pages": ["atlas.png"], "frames": [{"page": 0, "source": [0, 0, 8, 8], "offset": [0, 0]}] * 96}
    bank = dict(frames=96, cell=8, fps=32, pivot=[4, 6], fragmentCount=8,
        revision="textured-fracture-v3", layers={side: layer for side in ("back", "front")},
        sha256={"atlas.png": digest})
    (source / "media.json").write_text(json.dumps({name: bank for name in
        ("ground0", "ground1", "ground2", "ground3", "contact0", "contact1")}))
    (source / "approval.json").write_text(json.dumps({"revision": "textured-fracture-v3"}))
    (source / "operator.gd").write_text("original operator")
    (production / "art-manifest.json").write_text('{"files": [], "total_bytes": 0}')
    return source, preserved, production, repo


@pytest.mark.parametrize("defect", ("crop", "hash", "archive-conflict", "traversal", "missing-side"))
def test_invalid_final_bank_cannot_partially_install(delivery, defect):
    source, preserved, production, repo = delivery
    original = (production / "art-manifest.json").read_bytes()
    manifest = json.loads((source / "media.json").read_text())
    bank = manifest["contact1"]
    if defect == "crop":
        bank["layers"]["front"]["frames"][-1]["source"] = [7, 7, 8, 8]
    elif defect == "hash":
        bank["sha256"]["atlas.png"] = "0" * 64
    elif defect == "traversal":
        bank["layers"]["front"]["pages"] = ["../atlas.png"]
    elif defect == "missing-side":
        del bank["layers"]["back"]
    else:
        preserved.mkdir()
        (preserved / "operator.gd").write_text("earlier original")
    (source / "media.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, FileNotFoundError)):
        import_weather_solar(source, "ice", preserved=preserved, production=production, repo=repo)
    assert (production / "art-manifest.json").read_bytes() == original
    assert not repo.exists()
    assert not (preserved / "atlas.png").exists()


def test_repeat_preserves_originals_and_authored_recipe(delivery):
    source, preserved, production, repo = delivery
    first = import_weather_solar(source, "ice", preserved=preserved, production=production, repo=repo)
    recipe = repo / "game/data/weather_solar_media/weather-draft.json"
    recipe.write_text("human authored recipe")
    second = import_weather_solar(source, "ice", preserved=preserved, production=production, repo=repo)
    assert second == first
    assert recipe.read_text() == "human authored recipe"
    for name in ("atlas.png", "operator.gd", "media.json", "approval.json"):
        assert (source / name).read_bytes() == (preserved / name).read_bytes()
    assert (repo / "game/assets/weather_solar_media/ice/atlas.png").read_bytes() == (source / "atlas.png").read_bytes()
