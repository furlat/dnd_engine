"""Finite-only recipes use the same real membership dates as sustained media."""

from dataclasses import replace

import pytest

from devtools.animation_review.control_cases import control_spell_history
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, bind_motion
from game.condition_animation import resolve_condition_appearance
from game.condition_media_lifetime import register_condition_lifetimes, sample_condition_lifetimes
from game.condition_sampling import sample_condition_media
from game.player_reduction import reduce_lineage
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def captured():
    return control_spell_history(program="blindness")


@pytest.mark.parametrize("application,removal", ((True, False), (False, True), (True, True)))
def test_transition_only_recipe_plays_at_real_application_and_removal(captured, application, removal):
    data = load_animation_data()
    identity = "condition.blinded"
    recipe = data.condition_recipes[identity]
    finite = recipe.model_copy(update={
        "persistent": recipe.persistent.model_copy(update={"layers": ()}),
        "application": recipe.application.model_copy(update={
            "effects": recipe.application.effects if application else ()}),
        "removal": recipe.removal.model_copy(update={
            "effects": recipe.removal.effects if removal else ()}),
    })
    data = replace(data, condition_recipes={**data.condition_recipes, identity: finite})
    before, roots = player_history(captured, role="caster")
    records, clock, applied, removed = {}, 0., set(), set()
    for root in roots:
        motion = bind_motion(before, root, data)
        group = None if motion is not None else bind_choreography(before, root, data)
        records = register_condition_lifetimes(records, before, data, absolute_start_ms=clock,
            lineage=root, choreography=group, motion=motion)
        after = reduce_lineage(before, root)
        appearances = {str(actor.uuid): resolve_condition_appearance(actor.conditions,
            data.condition_recipes, data.condition_media) for actor in after.actors.values()}

        def samples(at):
            return tuple(sample for appearance in sample_condition_lifetimes(appearances, records, data, at).values()
                         for layer in appearance.layers for sample in sample_condition_media(data, layer))

        for owner, record in records.items():
            if record.behavior_id != identity:
                continue
            assert record.applied_ms is not None
            if owner not in applied:
                applied.add(owner)
                initial = samples(record.applied_ms + 250)
                assert len(initial) == (2 if application else 0)
                assert all("blinded.application" in sample.asset_id and sample.frame == 36 for sample in initial)
                assert not samples(record.applied_ms + 3500), "Finite application must not silently become a loop"
            if record.removed_ms is not None and owner not in removed:
                removed.add(owner)
                tail = samples(record.removed_ms + 250)
                assert len(tail) == (2 if removal else 0)
                assert all("blinded.removal" in sample.asset_id and sample.frame == 36 for sample in tail)
                assert not samples(record.removed_ms + 700)
        assert motion is not None or group is not None
        clock += (motion.complete_ms if motion is not None else group.complete_ms if group is not None else 0) + 25
        before = after
    assert applied and removed == applied
