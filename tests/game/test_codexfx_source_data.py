"""Existing authored media retains its identity and the Studio execution data."""

from hashlib import sha256
import json
from pathlib import Path

from pydantic import TypeAdapter
import pygame

from game.animation_types import AuthoredProjectileAsset, StudioDraftFile


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "game/data/codexfx"


def test_authored_export_is_locally_decodable_and_preserves_source_contract() -> None:
    provenance = json.loads((DATA / "provenance.json").read_text())
    for relative, expected in provenance["outputs"].items():
        assert sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    assets = TypeAdapter(tuple[AuthoredProjectileAsset, ...]).validate_json(
        (DATA / "projectile-assets.json").read_text()
    )
    resources = json.loads((DATA / "bindings.json").read_text())["resources"]
    assert len(assets) == 1
    asset = assets[0]
    source = json.loads((DATA / "source" / asset.assetId / "asset.json").read_text())
    sheet = ROOT / resources[asset.sheet]
    assert sha256(sheet.read_bytes()).hexdigest() == source["sheet"]["sha256"]
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
    assert (after.cast, after.condition, after.damage, after.elementColors) == (
        before.cast, before.condition, before.damage, before.elementColors,
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
