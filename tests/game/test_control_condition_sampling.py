"""Authored condition media: continuous phases, finite transitions and clear tails."""

from dataclasses import replace
from uuid import uuid4

import pytest

from game.animation_data import load_animation_data
from game.condition_animation import ConditionAppearance, resolve_condition_appearance
from game.condition_media_lifetime import ConditionMediaLifetime, sample_condition_lifetimes
from game.condition_sampling import sample_condition_media
from game.actor_facts import ConditionFact
from dnd.core.condition_types import ConditionCategory


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


def cue(data, identity):
    actor, owner = uuid4(), uuid4()
    member = ConditionFact(uuid4(), owner, identity, ConditionCategory.STATUS, identity, None, None)
    appearance = resolve_condition_appearance((member,), data.condition_recipes, data.condition_media)
    record = ConditionMediaLifetime(actor, owner, identity, applied_ms=1000)
    return str(actor), appearance, record


def samples(data, actor, appearance, record, time):
    layers = sample_condition_lifetimes({actor: appearance}, {record.owner_uuid: record}, data, time)[actor].layers
    return tuple((row.layer.attachment, item) for row in layers for item in sample_condition_media(data, row))


def test_sleep_uses_advancing_loop_and_arbitrary_phase_clear_without_restarting(data):
    actor, appearance, record = cue(data, "condition.spell.sleep")
    assert appearance.label is None and appearance.body_pose == "Die"
    assert not samples(data, actor, appearance, record, 1000)
    half = samples(data, actor, appearance, record, 1100)
    assert len(half) == 2 and all(attachment == "face" and row.alpha == pytest.approx(.5)
                                  for attachment, row in half)
    long = samples(data, actor, appearance, record, 19435)
    assert len(long) == 2 and all(row.frame == int(18435 * .032) % 128 for _, row in long)
    cleared = replace(record, removed_ms=19435,
        removed_layers=tuple(layer.layer.assetId for layer in appearance.layers))
    tail = samples(data, actor, ConditionAppearance(), cleared, 19635)
    assert len(tail) == 2
    assert all(row.frame == int(18635 * .032) % 128 and row.alpha == pytest.approx(.5) for _, row in tail)
    assert not samples(data, actor, ConditionAppearance(), cleared, 19835)
    assert samples(data, actor, appearance, record, 19435) == long


@pytest.mark.parametrize("identity,stem", (("condition.blinded", "blinded"), ("condition.deafened", "deafened")))
def test_senses_use_authored_intro_loop_and_finite_removal(data, identity, stem):
    actor, appearance, record = cue(data, identity)
    initial = samples(data, actor, appearance, record, 1250)
    assert len(initial) == 2 and all(f"{stem}.application" in row.asset_id for _, row in initial)
    sustained = samples(data, actor, appearance, record, 3500)
    assert len(sustained) == 2 and all(f"{stem}.sustain" in row.asset_id for _, row in sustained)
    cleared = replace(record, removed_ms=3600,
        removed_layers=tuple(layer.layer.assetId for layer in appearance.layers))
    tail = samples(data, actor, ConditionAppearance(), cleared, 3850)
    assert len(tail) == 2 and all(f"{stem}.removal" in row.asset_id and row.frame == 8 for _, row in tail)
    assert not samples(data, actor, ConditionAppearance(), cleared, 4300)


def test_command_executes_on_recorded_activation_then_never_returns_to_pending(data):
    actor, appearance, record = cue(data, "condition.spell.command.halt")
    pending = samples(data, actor, appearance, record, 5000)
    assert len(pending) == 2 and all("command.sustain" in row.asset_id for _, row in pending)
    activated = replace(record, activated_ms=5100)
    execution = samples(data, actor, appearance, activated, 5350)
    assert len(execution) == 2 and all("command.execute" in row.asset_id and row.frame == 8
                                     for _, row in execution)
    assert not samples(data, actor, appearance, activated, 7000)
    cleared = replace(activated, removed_ms=5400,
        removed_layers=tuple(layer.layer.assetId for layer in appearance.layers))
    tail = samples(data, actor, ConditionAppearance(), cleared, 5450)
    assert len(tail) == 2 and all("command.execute" in row.asset_id for _, row in tail)
    canceled = replace(record, removed_ms=1200,
        removed_layers=tuple(layer.layer.assetId for layer in appearance.layers))
    assert all("command.removal" in row.asset_id
               for _, row in samples(data, actor, ConditionAppearance(), canceled, 1450))


def test_charm_flower_hearts_and_sustain_overlap_by_authored_offsets(data):
    actor, appearance, record = cue(data, "condition.charmed")
    early = samples(data, actor, appearance, record, 1200)
    assert len(early) == 2 and all("charm_flower" in row.asset_id for _, row in early)
    overlap = samples(data, actor, appearance, record, 1500)
    assert len(overlap) == 4
    assert any("charm_hearts" in row.asset_id for _, row in overlap)
    later = samples(data, actor, appearance, record, 1700)
    assert any("charmed.sustain" in row.asset_id for _, row in later)


def test_clear_during_sleep_fade_never_brightens_the_clearing_particles(data):
    actor, appearance, record = cue(data, "condition.spell.sleep")
    cleared = replace(record, removed_ms=1100,
        removed_layers=tuple(layer.layer.assetId for layer in appearance.layers))
    for at, opacity in ((1100, .5), (1150, .4375), (1200, .375), (1300, .25)):
        layers = samples(data, actor, ConditionAppearance(), cleared, at)
        assert len(layers) == 2
        assert all(row.alpha == pytest.approx(opacity) and row.frame == int((at - 1000) * .032)
                   for _, row in layers)
