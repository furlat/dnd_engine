"""Studio version conversion preserves selected placements and authored clocks."""

from dataclasses import replace
import json
from math import hypot

import pytest

from game.animation import ActorContact, CastApplication, CastInput, ProjectileSample, compile_cast, project_projectile, sample_cast
from game.animation_data import DATA_ROOT, load_animation_data


@pytest.fixture(scope="module")
def data():
    return load_animation_data(authored_bundles=())


def test_supported_v1_and_v6_decode_to_the_same_explicit_v2_recipe(data, tmp_path):
    source = json.loads((DATA_ROOT / "spell-studio-drafts.materialized.json").read_text())
    fire_bolt = next(row for row in source["spells"] if row["definitionRef"]["content_id"] == "spell.fire_bolt")
    (tmp_path / "bindings.json").write_text(json.dumps({
        "resources": {}, "spells": {"spell.fire_bolt": fire_bolt["definitionRef"]}}))
    (tmp_path / "projectile-assets.json").write_text("[]")
    recipe_path = tmp_path / "spell-studio-drafts.json"
    recipe_path.write_text(json.dumps({"schema": "dnd.spellStudioDrafts", "version": 1, "spells": [fire_bolt]}))
    converted = load_animation_data(authored_bundles=(tmp_path,))
    assert converted.drafts["spell.fire_bolt"] == data.drafts["spell.fire_bolt"]
    explicit = converted.drafts["spell.fire_bolt"]
    assert explicit.projectile is not None
    assert explicit.projectile.sourceAnchor.basis == "rigRoot"
    assert explicit.projectile.sourceAnchor.liftY == -64
    assert explicit.projectile.targetAnchor.axisPx == -16
    assert explicit.projectile.targetAnchor.forwardPx == 0
    recipe_path.write_text(json.dumps({"schema": "dnd.spellStudioDrafts", "version": 2,
        "spells": [explicit.model_dump(mode="json")]}))
    assert load_animation_data(authored_bundles=(tmp_path,)).drafts == converted.drafts
    # Conversion leaves the retained historical source untouched.
    assert fire_bolt["projectile"]["sourceAnchor"]["basis"] == "tileCenter"
    assert fire_bolt["projectile"]["targetAnchor"]["forwardPx"] == -16


def test_target_path_inset_follows_the_actual_oblique_chord_in_each_camera(data):
    recipe = data.drafts["spell.fire_bolt"]
    projectile = recipe.projectile
    assert projectile is not None
    projectile = projectile.model_copy(update={
        "sourceAnchorsByFacing": None,
        "sourceAnchor": projectile.sourceAnchor.model_copy(update={"axisPx": 0}),
        "targetAnchor": projectile.targetAnchor.model_copy(update={"axisPx": 0}),
    })
    source = CastInput("oblique", ActorContact("caster", (1, 1), "S", .5),
        (CastApplication("hit", ActorContact("target", (6, 2), "N", .8, elevation_steps=2), False, None, None),))
    timelines = [compile_cast(replace(data, drafts={**data.drafts, "spell.fire_bolt":
        recipe.model_copy(update={"projectile": projectile.model_copy(update={
            "targetAnchor": projectile.targetAnchor.model_copy(update={"axisPx": inset})})})}),
        "spell.fire_bolt", source) for inset in (0, -12)]
    for quadrant in range(4):
        endpoints = []
        for timeline in timelines:
            delivery, = timeline.applications
            effect = next(row for row in sample_cast(timeline, delivery.travel_start_ms).projectiles
                if isinstance(row, ProjectileSample) and row.phase == "travel")
            endpoints.append(tuple(project_projectile(timeline, replace(effect, progress=t), quadrant).point for t in (0, 1)))
        (start, target), (other_start, inset_target) = endpoints
        assert start == other_start
        dx, dy = target[0]-start[0], target[1]-start[1]
        length = hypot(dx, dy)
        assert (inset_target[0]-target[0], inset_target[1]-target[1]) == pytest.approx(
            (-12*.8*dx/length, -12*.8*dy/length))
