"""A real paid Counterspell stops relocation without inventing departure media."""

import pytest

from dnd.core.events import SpatialChangeType
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.player_facts import SpatialFact, SpellFact
from game.presentation_group import presentation_groups, reduce_presentation_group
from tests.game.interruption_scenarios import interruption_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def history():
    return interruption_history(blocker="counterspell", spell="misty_step")


@pytest.mark.parametrize("role", ("caster", "defender"))
def test_countered_misty_step_has_no_departure_or_arrival(history, role):
    data = load_animation_data()
    state, roots = player_history(history, role=role)
    for presentation in presentation_groups(roots):
        root = presentation.primary.root
        if isinstance(root.fact, SpellFact) and root.fact.behavior_id == "spell.misty_step":
            assert root.canceled and root.cancellation is not None
            assert root.cancellation.action_economy_spent
            actor_id = root.fact.source_entity_uuid
            origin = state.actors[actor_id].last_visual_position
            assert not any(isinstance(node.fact, SpatialFact)
                and node.fact.entity_uuid == actor_id
                and node.fact.change_type in (SpatialChangeType.ENTITY_LEFT, SpatialChangeType.ENTITY_ENTERED)
                for node in presentation.primary.events)
            group = bind_choreography(state, presentation.primary, data, reactions=presentation.reactions)
            assert not group.gaps and not group.stationary_media
            assert group.after == reduce_presentation_group(state, presentation)
            assert group.after.actors[actor_id].last_visual_position == origin
            incoming = next(cue for cue in group.body_actions if cue.event_uuid == root.uuid)
            reaction, = group.reaction_media
            assert incoming.complete_ms == incoming.effect_ms == reaction.start_ms
            for time in (incoming.effect_ms - 1, incoming.effect_ms + 1, group.complete_ms + 1):
                sample = sample_choreography(group, time)
                assert sample.displayed.actors[actor_id].last_visual_position == origin
                assert not sample.stationary_media and not sample.portals
            return
        state = reduce_presentation_group(state, presentation)
    raise AssertionError("No recorded Misty Step attempt")
