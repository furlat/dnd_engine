"""Recorded object interactions commit at the reach, independently of latest."""

from uuid import UUID

import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.player_facts import ActionFact
from game.player_reduction import reduce_lineage
from tests.game.environment_scenarios import environment_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def lights():
    return environment_history()


@pytest.fixture(scope="module")
def animation_data():
    return load_animation_data()


@pytest.mark.parametrize("role", ("operator", "witness"))
def test_recorded_light_and_contact_change_at_hand_extension(lights, animation_data, role):
    before, roots = player_history(lights, role=role)
    for root in roots:
        fact = root.root.fact
        if isinstance(fact, ActionFact) and fact.behavior_id == "action.environment.wall_torch.extinguish":
            break
        before = reduce_lineage(before, root)
    else:
        pytest.fail("No disclosed extinguish interaction")
    bound = bind_choreography(before, root, animation_data)
    cue, = bound.body_actions
    source = UUID(cue.contact.actor_uuid)
    item = cue.interaction_object_uuid
    assert item is not None
    latest = reduce_lineage(before, root)
    assert not latest.objects[item].item.is_lit
    pending = sample_choreography(bound, cue.effect_ms - 1)
    reached = sample_choreography(bound, cue.effect_ms)
    assert pending.displayed.objects[item].item.is_lit
    assert not reached.displayed.objects[item].item.is_lit
    if role == "witness":
        assert pending.displayed.senses is not None and source in pending.displayed.senses.entities
        assert reached.displayed.senses is not None and source not in reached.displayed.senses.entities
    assert not reached.complete, "the arm must still retract after the state change"
    assert sample_choreography(bound, cue.effect_ms - 1) == pending, "seeking must restore the pre-contact state"
    assert sample_choreography(bound, cue.effect_ms) == reached, "sampling must not mutate retained state"
