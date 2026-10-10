"""Delivered spell packaging preserves pixels, clocks and authored ownership."""

import json
from pathlib import Path

import pygame
import pytest

from devtools.import_pending_spells import import_bundle
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage


DIRECTIONS = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def png(root: Path, relative: str, width: int = 16) -> bytes:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    image = pygame.Surface((width, 8), pygame.SRCALPHA)
    image.fill((12, 39, 77, 83), (1, 2, width - 2, 3))
    pygame.image.save(image, path)
    return path.read_bytes()


def test_finite_import_preserves_pages_pivots_and_independent_recipes(tmp_path: Path):
    source, repo = tmp_path / "source", tmp_path / "repo"
    finite = source / "delivery-next-spells-directions-v1"
    original = png(finite, "spells/inflict_wounds/page.png")
    write_json(finite / "manifest.json", {"spells": [{
        "id": "inflict_wounds", "frames": 3, "fps": 144, "frameSize": [8, 8],
        "pivot": [4, 5.25], "palette": ["0c274d"], "columns": 2, "framesPerPage": 2,
        "directions": {facing: {"layers": {depth: ["spells/inflict_wounds/page.png"] * 2
                        for depth in ("back", "front")}} for facing in DIRECTIONS}}]})
    folder = repo / "game/data/pending_spells"
    recipe = b'{"independent authored recipe":true}\n'
    write_json(folder / "bindings.json", {"resources": {"existing": "kept.png"},
        "spells": {"spell.inflict_wounds": {"independent": True}}, "projectileStorage": {},
        "actionDeliveries": {"reaction.spell.hellish_rebuke": "spell.hellish_rebuke"}})
    (folder / "spell-studio-drafts.json").write_bytes(recipe)

    assert import_bundle(source, repo=repo) == ("inflict_wounds",)
    assert import_bundle(source, repo=repo) == ("inflict_wounds",)

    assert (folder / "spell-studio-drafts.json").read_bytes() == recipe
    bindings = json.loads((folder / "bindings.json").read_text())
    assert bindings["spells"] == {"spell.inflict_wounds": {"independent": True}}
    assert bindings["actionDeliveries"] == {"reaction.spell.hellish_rebuke": "spell.hellish_rebuke"}
    assert bindings["resources"] == {"existing": "kept.png"}
    assets = json.loads((folder / "projectile-assets.json").read_text())
    assert {row["assetId"] for row in assets} == {"pending.inflict_wounds.back", "pending.inflict_wounds.front"}
    for row in assets:
        asset = AuthoredProjectileAsset.model_validate_json(json.dumps(row))
        assert asset.phases.impact is not None
        assert (asset.phases.impact.frames, asset.phases.impact.fps, asset.phases.impact.loop) == (3, 144, False)
        assert asset.anchor.x == .5 and asset.anchor.y == 5.25 / 8
        assert asset.defaultScale == .5 and asset.palettePreview.colors == (0x0C274D,)
        storage = ProjectileStorage.model_validate_json(json.dumps(bindings["projectileStorage"][asset.assetId]))
        layer, = storage.phases["impact"].layers
        assert layer.blendMode == "normal" and layer.pages is not None
        assert set(layer.pages) == set(DIRECTIONS)
        for pages in layer.pages.values():
            assert [(page.firstFrame, page.frameCount, page.columns) for page in pages] == [(0, 2, 2), (2, 1, 2)]
            assert all((repo / page.file).read_bytes() == original for page in pages)


@pytest.mark.parametrize("group,name,kind", [("buffs", "bane_sustain", "loop"),
                                             ("buffs", "bless", "application"),
                                             ("movement", "flight", "flight"),
                                             ("movement", "jump", "loop")])
def test_published_components_import_before_whole_delivery_is_complete(
    tmp_path: Path, group: str, name: str, kind: str,
):
    source, repo = tmp_path / "source", tmp_path / "repo"
    write_json(source / "delivery-next-spells-directions-v1/manifest.json", {"spells": []})
    supplement = source / f"delivery-{group}-directions-v1"
    original = png(supplement, "media/page.png", 32)
    component = {"kind": kind, "playbackFrames": 3, "capturedFrames": 4,
        "spec": {"palette": ["0c274d"]}, "directions": {facing: {"layers": {
            depth: {"pages": [{"file": "media/page.png", "firstFrame": 0,
                "frameCount": 4, "columns": 4, "sha256": "source-only-metadata"}],
                "checks": {"source-only": True}} for depth in ("back", "front")}}
            for facing in DIRECTIONS}}
    write_json(supplement / "manifest.json", {"complete": False, "directions": DIRECTIONS,
        "cell": [8, 8], "groundPivot": [4, 5.25], "fps": 144, "components": {name: component}})
    hand = None
    if name == "bless":
        hand = png(source / "buffs-review", "actors/bless/Special1-glow.png")
        write_json(source / "buffs-review/delivery/manifest.json", {"spells": [{
            "id": "bless", "stage": "application", "cast": {"sourceLayer": "actors/bless/Special1-glow.png"}}]})
    if name == "jump":
        hand = png(source / "movement-review", "actors/jump-hands.png")

    assert import_bundle(source, repo=repo) == (name,)

    folder = repo / "game/data/pending_spells"
    assets = json.loads((folder / "projectile-assets.json").read_text())
    bindings = json.loads((folder / "bindings.json").read_text())
    if hand is None:
        assert bindings["resources"] == {}
    else:
        assert set(bindings["resources"]) == {f"/pending-spells/{name}/cast.png"}
        assert (repo / bindings["resources"][f"/pending-spells/{name}/cast.png"]).read_bytes() == hand
    for row in assets:
        asset = AuthoredProjectileAsset.model_validate_json(json.dumps(row))
        assert asset.phases.impact is not None
        assert asset.phases.impact.frames == 3 and asset.phases.impact.loop == (kind == "loop")
        storage = ProjectileStorage.model_validate_json(json.dumps(bindings["projectileStorage"][asset.assetId]))
        layer, = storage.phases["impact"].layers
        assert layer.pages is not None
        for pages in layer.pages.values():
            page, = pages
            assert (page.firstFrame, page.frameCount, page.columns) == (0, 3, 4)
            assert (repo / page.file).read_bytes() == original
