"""Received owner removal freezes held art and starts finite color retirement."""

from dataclasses import replace
import json
from uuid import uuid4

import pygame
import pytest
from pydantic import ValidationError

from dnd.core.condition_types import ConditionCategory
from game.actor_facts import ConditionFact
from game.animation_data import load_animation_data
from game.animation_types import AuthoredProjectilePhase, AuthoredProjectilePhases
from game.condition_animation import resolve_condition_appearance
from game.condition_media import ConditionLayerMedia, ConditionMediaSource, load_condition_media
from game.condition_media_lifetime import ConditionMediaLifetime, sample_condition_lifetimes
from game.condition_sampling import sample_condition_media


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    original = load_animation_data()
    template = next(iter(original.projectile_assets.values()))
    assets = dict(original.projectile_assets)
    for name, count, loop in (("release.test.apply", 53, False),
                              ("release.test.hold", 1, True),
                              ("release.test.clear", 87, False)):
        assets[name] = template.model_copy(update={"assetId": name, "fps": 32,
            "phases": AuthoredProjectilePhases(impact=AuthoredProjectilePhase(
                start=0, frames=count, fps=32, loop=loop))})
    recipe = original.condition_recipes["condition.spell.slow"]
    media = dict(original.condition_media)
    for layer in recipe.persistent.layers:
        media[layer.assetId] = ConditionLayerMedia(layer.category, layer.animation,
            asset_id="release.test.hold", application_asset_id="release.test.apply",
            application_mode="sequence", removal_asset_id="release.test.clear",
            removal_crossfade_ms=150)
    yield replace(original, projectile_assets=assets, condition_media=media)
    pygame.quit()


def owner_fact(owner):
    return ConditionFact(condition_uuid=owner, behavior_id="condition.spell.slow",
        category=ConditionCategory.CONDITION, event_uuid=uuid4(), name="Slow",
        resulting_max_hp=None, resulting_ac=None)


def sampled(data, actor, records, time, members=()):
    appearance = resolve_condition_appearance(members, data.condition_recipes, data.condition_media)
    layers = sample_condition_lifetimes({str(actor): appearance}, records, data, time)[str(actor)].layers
    return tuple(sample for layer in layers for sample in sample_condition_media(data, layer))


@pytest.mark.parametrize("removed", (500., 3000.))
def test_removal_freezes_current_binding_or_hold_then_finishes_finite_release(data, removed):
    actor, owner = uuid4(), uuid4()
    layers = tuple(layer.assetId for layer in data.condition_recipes["condition.spell.slow"].persistent.layers)
    record = ConditionMediaLifetime(actor, owner, "condition.spell.slow", applied_ms=0,
        removed_ms=removed, removed_layers=layers)
    records = {owner: record}
    outgoing = "release.test.apply" if removed < 53 * 1000 / 32 else "release.test.hold"
    expected_frame = 16 if removed == 500 else 0
    first = sampled(data, actor, records, removed)
    assert len(first) == 2 and all(s.asset_id == outgoing and s.frame == expected_frame for s in first)
    overlap = sampled(data, actor, records, removed + 75)
    assert len(overlap) == 4
    assert all(s.alpha == pytest.approx(.5) for s in overlap)
    assert all(s.frame == expected_frame for s in overlap if s.asset_id == outgoing)
    clear = sampled(data, actor, records, removed + 150)
    assert len(clear) == 2 and all(s.asset_id == "release.test.clear" and s.frame == 4 for s in clear)
    assert sampled(data, actor, records, removed + 2700)
    assert not sampled(data, actor, records, removed + 87 * 1000 / 32)
    # Seeking again does not mutate a frozen outgoing sample or its owner clock.
    assert sampled(data, actor, records, removed + 75) == overlap


def test_unknown_application_enters_quiet_hold_and_other_owner_suppresses_release(data):
    actor, owner, remaining = uuid4(), uuid4(), uuid4()
    layers = tuple(layer.assetId for layer in data.condition_recipes["condition.spell.slow"].persistent.layers)
    record = ConditionMediaLifetime(actor, owner, "condition.spell.slow",
        removed_ms=3000, removed_layers=layers)
    first = sampled(data, actor, {owner: record}, 3000)
    assert first and all(s.asset_id == "release.test.hold" for s in first)
    records = {owner: record, remaining: ConditionMediaLifetime(actor, remaining, "condition.spell.slow")}
    kept = sampled(data, actor, records, 3075, (owner_fact(remaining),))
    assert len(kept) == 2 and all(s.asset_id == "release.test.hold" and s.alpha == 1 for s in kept)


def test_color_release_fields_load_and_default_without_changing_mask_contract(tmp_path):
    default = ConditionMediaSource(category="test", animation="loop")
    assert default.removal_asset_id is None and default.removal_crossfade_ms == 0
    for overrides in ({"removal_crossfade_ms": 150},
                      {"asset_id": "hold", "removal_asset_id": "clear", "removal_mask_asset_id": "mask"}):
        with pytest.raises(ValidationError):
            ConditionMediaSource.model_validate_json(json.dumps({"category": "test", "animation": "loop", **overrides}))
    source = tmp_path / "media.json"
    source.write_text(json.dumps({"schema": "dnd.conditionLayerMedia", "version": 1,
        "layers": {"test": {"category": "test", "animation": "loop", "asset_id": "hold",
            "removal_asset_id": "clear", "removal_crossfade_ms": 150}}}))
    resources = tmp_path / "bindings.json"
    resources.write_text('{"resources":{}}')
    loaded = load_condition_media(source, resources, tmp_path)["test"]
    assert loaded.removal_asset_id == "clear" and loaded.removal_crossfade_ms == 150


@pytest.mark.parametrize("loop,frames", ((True, 87), (False, 1)))
def test_invalid_release_cannot_restart_forever_or_end_before_crossfade(data, loop, frames):
    actor, owner = uuid4(), uuid4()
    asset = data.projectile_assets["release.test.clear"].model_copy(update={
        "phases": AuthoredProjectilePhases(impact=AuthoredProjectilePhase(
            start=0, frames=frames, fps=32, loop=loop))})
    changed = replace(data, projectile_assets={**data.projectile_assets, asset.assetId: asset})
    layers = tuple(layer.assetId for layer in data.condition_recipes["condition.spell.slow"].persistent.layers)
    record = ConditionMediaLifetime(actor, owner, "condition.spell.slow", applied_ms=0,
        removed_ms=3000, removed_layers=layers)
    with pytest.raises(ValueError):
        sampled(changed, actor, {owner: record}, 3010)
