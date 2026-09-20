"""Existing authored media retains its identity and the Studio execution data."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

from pydantic import TypeAdapter
import pygame

from devtools import import_codexfx_presentation as importer
from game.animation_types import AuthoredProjectileAsset, StudioDraftFile


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "game/data/codexfx"


def test_authored_export_is_locally_decodable_and_preserves_source_contract() -> None:
    assets = TypeAdapter(tuple[AuthoredProjectileAsset, ...]).validate_json(
        (DATA / "projectile-assets.json").read_text()
    )
    resources = json.loads((DATA / "bindings.json").read_text())["resources"]
    assert len(assets) == 1
    asset = assets[0]
    source = json.loads((DATA / "source" / asset.assetId / "asset.json").read_text())
    sheet = ROOT / resources[asset.sheet]
    assert pygame.image.load(sheet).get_size() == (11264, 2048)
    assert (asset.frame.width, asset.frame.height, asset.frame.cols, asset.frame.rows) == (256, 256, 44, 8)
    assert asset.rowOrder == ("E", "SE", "S", "SW", "W", "NW", "N", "NE")
    assert asset.phases.cast is not None and asset.phases.impact is not None
    for phase, expected in ((asset.phases.cast, (0, 16, False)),
                            (asset.phases.travel, (16, 10, True)),
                            (asset.phases.impact, (26, 18, False))):
        assert (phase.start, phase.frames, phase.loop) == expected
        assert phase.fps == 24
    assert (asset.anchor.x, asset.anchor.y, asset.defaultScale) == (0.5, 1, 0.5)
    assert (source["sheet"]["sampling"], source["sheet"]["blend"], source["sheet"]["alphaMode"]) == (
        "nearest", "add", "straight",
    )


def test_authored_media_selection_preserves_existing_studio_choreography() -> None:
    original = StudioDraftFile.model_validate_json(
        (ROOT / "game/data/neuroclient/spell-studio-drafts.materialized.json").read_text()
    )
    imported = StudioDraftFile.model_validate_json((DATA / "spell-studio-drafts.json").read_text())
    assert len(imported.spells) == 1
    after = imported.spells[0]
    before = next(row for row in original.spells if row.definitionRef == after.definitionRef)
    assert after.definitionRef.content_id == "spell.magic_missile"
    assert (after.cast, after.condition, after.elementColors) == (
        before.cast, before.condition, before.elementColors,
    )
    first, second = before.projectile, after.projectile
    assert first is not None and second is not None
    assert first.geometry.enabled and first.sprite is None
    assert not second.geometry.enabled and second.sprite is not None
    assert second.scale == 0.5
    assert (second.sprite.tint, second.sprite.alpha, second.sprite.blendMode) == (0xFFFFFF, 1, "add")
    assert (second.sprite.offsetX, second.sprite.offsetY) == (0, 0)
    assert (second.trajectory, second.orientation, second.sourceAnchor, second.targetAnchor,
            second.sourceAnchorsByFacing, second.speedPxPerSecond, second.minimumTravelDurationMs,
            second.missileStaggerMs, second.depthMode) == (
        first.trajectory, first.orientation, first.sourceAnchor, first.targetAnchor,
        first.sourceAnchorsByFacing, first.speedPxPerSecond, first.minimumTravelDurationMs,
        first.missileStaggerMs, first.depthMode,
    )
    assert second.prepare == first.prepare  # Available cast frames do not enable preparation.
    assert not second.prepare.enabled
    for phase in (second.travel, second.impact):
        assert phase.enabled and phase.assetId == second.sprite.assetId
    assert after.damage is not None
    assert after.damage.floatingNumber.label == "Force"
    assert (after.damage.hitFlash.frame, after.damage.hitFlash.durationMs) == (0, 150)
    palette = after.damage.hitFlash.palette
    assert palette is not None
    assert palette.colors == (2229802, 3409984, 4721232, 6163803, 7803494,
                              9509492, 11217541, 12927895, 14442667)
    assert (palette.gamma, palette.noiseSheet, palette.untinted) == (.65, None, False)


def test_media_reimport_preserves_authored_recipe_and_other_bindings(tmp_path, monkeypatch) -> None:
    """An offline media update cannot erase a subsequently approved palette."""
    destination = tmp_path / "selected"
    data_root = destination / "game/data/codexfx"
    data_root.mkdir(parents=True)
    for filename in ("spell-studio-drafts.json", "projectile-assets.json", "bindings.json"):
        shutil.copyfile(DATA / filename, data_root / filename)
    recipe_path = data_root / "spell-studio-drafts.json"
    recipes = json.loads(recipe_path.read_text())
    recipes["effectDrafts"] = {"spell.magic_missile.child": recipes["spells"][0]}
    recipe_path.write_text(json.dumps(recipes))
    original_recipe = recipe_path.read_bytes()
    bindings_path = data_root / "bindings.json"
    bindings = json.loads(bindings_path.read_text())
    bindings["resources"]["/retained-casting-layer.png"] = "game/assets/retained-casting-layer.png"
    bindings_path.write_text(json.dumps(bindings))

    entry, = json.loads((DATA / "projectile-assets.json").read_text())
    package = tmp_path / "export"
    source = DATA / "source" / entry["assetId"]
    shutil.copytree(source, package)
    manifest = json.loads((package / "asset.json").read_text())
    sheet = package / manifest["sheet"]["uri"]
    sheet.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / bindings["resources"][entry["sheet"]], sheet)

    # Only the external exporter process is substituted. The local import,
    # selected data, packaging writes and media copy follow the production path.
    def external_converter(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, json.dumps(entry), "")

    monkeypatch.setattr(importer.subprocess, "run", external_converter)
    monkeypatch.setattr(sys, "argv", ["import_codexfx_presentation",
        "--pipeline-root", str(tmp_path / "pipeline"), "--source-python", sys.executable,
        "--package", str(package), "--spell-id", "spell.magic_missile",
        "--output-root", str(destination)])
    importer.main()

    assert (data_root / "spell-studio-drafts.json").read_bytes() == original_recipe
    assert json.loads(bindings_path.read_text()) == bindings
    copied_sheet = destination / bindings["resources"][entry["sheet"]]
    assert copied_sheet.read_bytes() == sheet.read_bytes()
    updated, = json.loads((data_root / "projectile-assets.json").read_text())
    assert updated["phases"] == entry["phases"]
