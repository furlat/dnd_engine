"""Accepted sensory media follows real grants and removal in saved player input."""

import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography, bind_motion
from game.condition_media_lifetime import register_condition_lifetimes
from dnd.player.reduction import reduce_lineage
from tests.game.player_helpers import player_history
from tests.game.support_conditions_scenarios import support_condition_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.mark.parametrize("program", ["darkvision", "see_invisibility", "true_seeing"])
def test_sensory_grant_keeps_exact_owner_and_retires_on_native_removal(data, program):
    captured = support_condition_history(program=program)
    before, roots = player_history(captured, role="caster")
    records, clock = {}, 0.0
    for root in roots:
        motion = bind_motion(before, root, data)
        group = None if motion is not None else bind_choreography(before, root, data)
        records = register_condition_lifetimes(records, before, data, absolute_start_ms=clock,
            lineage=root, choreography=group, motion=motion)
        assert motion is not None or group is not None
        clock += (motion.complete_ms if motion is not None else group.complete_ms) + 25
        before = reduce_lineage(before, root)
    owned = [r for r in records.values() if r.behavior_id == "condition.spell." + program]
    assert len(owned) == 1
    assert owned[0].applied_ms is not None
    assert owned[0].removed_ms is not None
    assert owned[0].removed_ms > owned[0].applied_ms
    assert not any(c.behavior_id == "condition.spell." + program for a in before.actors.values() for c in a.conditions)
    layers = data.condition_recipes["condition.spell." + program].persistent.layers
    assert {layer.drawOrder for layer in layers} == {"behind_body", "in_front_of_body"}
    for layer in layers:
        media = data.condition_media[layer.assetId]
        application = data.projectile_assets[media.application_asset_id]
        hold = data.projectile_assets[media.asset_id]
        assert application.phases.impact.frames / application.phases.impact.fps == 4
        assert hold.phases.impact.loop
        assert media.removal_fade_ms == 600
        assert media.world_basis == "SE"
