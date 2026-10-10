"""Delivered phase pages preserve pixels/clocks and cannot rewrite behavior."""

import json
from pathlib import Path
import subprocess
import sys

import pygame

from devtools.import_cantrip_media import import_bundle, import_projectile_media


def test_bundle_and_selected_projectile_reimports_preserve_authoring_and_independent_phase_pages(tmp_path: Path):
    source, repo = tmp_path / "source", tmp_path / "repo"
    source.mkdir()
    folder = repo / "game/data/cantrips"
    folder.mkdir(parents=True)
    recipe = b'{"independent authored behavior":true}\n'
    (folder / "spell-studio-drafts.json").write_bytes(recipe)
    other = {"assetId": "other", "author": "keep"}
    original = {"assetId": "cantrip.sample.full", "displayName": "Authored name", "defaultScale": .5,
                "phases": {"impact": {"frames": 360}}}
    (folder / "projectile-assets.json").write_text(json.dumps([original, other]))
    bindings = {"resources": {"cast": "hand.png"}, "spells": {"spell.sample": {"keep": True}},
                "projectileStorage": {"other": {"keep": True}}}
    (folder / "bindings.json").write_text(json.dumps(bindings))
    directions = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]
    phase_pages = {
        "travel": [{"file": "travel-0.png", "firstFrame": 0, "frameCount": 2, "columns": 2},
                   {"file": "travel-1.png", "firstFrame": 2, "frameCount": 1, "columns": 1}],
        "impact": [{"file": "impact.png", "firstFrame": 0, "frameCount": 4, "columns": 4}],
    }
    for pages in phase_pages.values():
        for page in pages:
            image = pygame.Surface((8 * page["columns"], 8), pygame.SRCALPHA)
            for frame in range(page["frameCount"]):
                image.fill((19 + frame, 51, 9, 73 + frame), (8 * frame + 1, 2, 3, 4))
            pygame.image.save(image, source / page["file"])
    manifest = {"assetId": "cantrip.sample.full", "cell": 8, "pivot": [3, 5], "directions": directions,
                "palette": {"colors": [[19, 51, 9], [22, 51, 9]]}, "phases": {
                    "travel": {"frames": 3, "fps": 144, "loop": True,
                               "pages": {facing: phase_pages["travel"] for facing in directions}},
                    "impact": {"frames": 4, "fps": 72, "loop": False,
                               "pages": {facing: phase_pages["impact"] for facing in directions}},
                }}
    (source / "manifest.json").write_text(json.dumps(manifest))

    bundle = tmp_path / "bundle"
    sheets = bundle / "review-sheets"
    sheets.mkdir(parents=True)
    phase = {"cell": 8, "pivot": [4, 4], "frames": 4, "fps": 24,
             "pages": {facing: phase_pages["impact"] for facing in directions}}
    (sheets / "manifest.json").write_text(json.dumps({"spells": [
        {"id": name, "directions": directions, "palette": {"colors": [[19, 51, 9]]},
         "phases": {"full": phase}} for name in ("sample", "another")]}))
    (sheets / "impact.png").write_bytes((source / "impact.png").read_bytes())
    for name in ("sample", "another"):
        glow = bundle / "actors" / name / "hand-glow.png"
        glow.parent.mkdir(parents=True)
        glow.write_bytes((source / "impact.png").read_bytes())

    # Explicitly selecting the older bundle is allowed; its later replacement
    # becomes an explicit input to ordinary reimports, not an ordering accident.
    import_bundle(bundle, projectile_sources=(), repo=repo)
    import_projectile_media(source, repo=repo)
    import_bundle(bundle, projectile_sources=(source,), repo=repo)
    import_projectile_media(source, repo=repo)
    selected_assets = (folder / "projectile-assets.json").read_bytes()
    selected_bindings = (folder / "bindings.json").read_bytes()
    import_bundle(bundle, projectile_sources=(source,), repo=repo)
    assert (folder / "projectile-assets.json").read_bytes() == selected_assets
    assert (folder / "bindings.json").read_bytes() == selected_bindings

    assert (folder / "spell-studio-drafts.json").read_bytes() == recipe
    imported_asset, unrelated_asset, bundle_asset = json.loads((folder / "projectile-assets.json").read_text())
    assert unrelated_asset == other
    assert bundle_asset["assetId"] == "cantrip.another.full"
    assert imported_asset["displayName"] == original["displayName"]
    assert imported_asset["defaultScale"] == .5
    assert imported_asset["frame"] == {"width": 8, "height": 8, "rows": 8, "cols": 4}
    assert imported_asset["rowOrder"] == directions
    assert imported_asset["anchor"] == {"x": 3 / 8, "y": 5 / 8}
    assert imported_asset["anchorsByFacing"] == {facing: {"x": 3 / 8, "y": 5 / 8} for facing in directions}
    assert imported_asset["palettePreview"]["colors"] == [0x133309, 0x163309]
    assert imported_asset["phases"] == {
        "travel": {"start": 0, "frames": 3, "fps": 144, "loop": True},
        "impact": {"start": 0, "frames": 4, "fps": 72, "loop": False},
    }
    imported_bindings = json.loads((folder / "bindings.json").read_text())
    assert imported_bindings["resources"]["cast"] == bindings["resources"]["cast"]
    assert (repo / imported_bindings["resources"]["/cantrips/another/cast.png"]).read_bytes() == (
        source / "impact.png").read_bytes()
    assert imported_bindings["spells"] == bindings["spells"]
    assert imported_bindings["projectileStorage"]["other"] == bindings["projectileStorage"]["other"]
    for name, pages in phase_pages.items():
        layer, = imported_bindings["projectileStorage"]["cantrip.sample.full"]["phases"][name]["layers"]
        assert layer["blendMode"] == "normal"
        for facing in directions:
            for delivered, imported in zip(pages, layer["pages"][facing], strict=True):
                assert {key: imported[key] for key in ("firstFrame", "frameCount", "columns")} == {
                    key: delivered[key] for key in ("firstFrame", "frameCount", "columns")}
                assert (repo / imported["file"]).read_bytes() == (source / delivered["file"]).read_bytes()


def test_bare_bundle_cli_requires_explicit_media_selection_before_writing(tmp_path: Path):
    result = subprocess.run([sys.executable, "-m", "devtools.import_cantrip_media", "--source", str(tmp_path)],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert "--selected-projectile" in result.stderr and "--bundle-only" in result.stderr
    assert not list(tmp_path.iterdir())
