"""Actual cancellation/payment facts select bounded authored playback."""

import pytest

from dnd.core.events import EventPhase
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.player_facts import DamageFact, SpellFact
from game.animation import CastSample
from game.combat import BoundCast
from game.presentation_group import presentation_groups, reduce_presentation_group
from tests.game.interruption_scenarios import interruption_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope='module', params=[
    ('sanctuary', 'fire_bolt', True),
    ('sanctuary', 'sacred_flame', True), ('sanctuary', 'magic_missile', True),
    ('counterspell', 'fire_bolt', True), ('counterspell', 'sacred_flame', True),
    ('counterspell', 'magic_missile', True), ('counterspell', 'fireball', True),
    ('counterspell', 'fireball', False),
])
def recorded(request):
    blocker, spell, blocked = request.param
    return request.param, interruption_history(blocker=blocker, spell=spell, blocked=blocked)


@pytest.mark.parametrize('role', ('caster', 'defender'))
def test_saved_cancellation_plays_attempt_without_fabricating_contact(recorded, role):
    (blocker, spell, blocked), native = recorded
    data = load_animation_data()
    state, heads = player_history(native, role=role)
    found = False
    for presentation in presentation_groups(heads):
        head = presentation.primary
        fact = head.root.fact
        if isinstance(fact, SpellFact) and fact.behavior_id == 'spell.' + spell:
            found = True
            group = bind_choreography(state, head, data, reactions=presentation.reactions)
            assert not group.gaps
            assert group.after == reduce_presentation_group(state, presentation)
            if blocker == 'counterspell':
                reaction_ids = {reaction.root.uuid for reaction in presentation.reactions}
                bodies = [cue for cue in group.body_actions if cue.event_uuid in reaction_ids]
                assert len(bodies) == len(reaction_ids) == 1
                reaction = bodies[0]
                assert reaction.start_ms >= 0 and reaction.effect_ms > reaction.start_ms
                assert reaction.feedback is not None
                assert reaction.feedback.text == ('Counterspelled' if blocked else 'Counterspell failed')
                sampled = sample_choreography(group, reaction.effect_ms - 1)
                assert any(body.actor_uuid == reaction.contact.actor_uuid and body.clip == reaction.clip
                           for body in sampled.bodies)
                if blocked:
                    incoming = group.nodes[0]
                    assert reaction.effect_ms == pytest.approx(incoming.start_ms + incoming.bound.timeline.complete_ms)
            if blocked:
                cancellation = head.root.cancellation
                assert cancellation is not None
                assert cancellation.phase is (EventPhase.DECLARATION if blocker == 'sanctuary' else EventPhase.EXECUTION)
                assert cancellation.action_economy_spent == (blocker == 'counterspell')
                assert group.complete_ms > 0 and (group.nodes or group.body_actions)
                assert not any(isinstance(node.fact, DamageFact) and node.fact.stage == 'applied'
                               for node in head.events)
                assert not group.damage and not group.conditions and not group.residue_reveals
                if spell == 'magic_missile':
                    cast = group.nodes[0].bound
                    assert isinstance(cast, BoundCast)
                    attempted = cast.timeline.source.applications
                    assert len(attempted) == len(fact.declared_target_entity_uuids) == 3
                    assert len({row.application_id for row in attempted}) == 3
                    assert all(not row.damage_applied and row.hit is None for row in attempted)
                for elapsed in (0, group.complete_ms / 3, group.complete_ms * .9, group.complete_ms + 100):
                    sample = sample_choreography(group, elapsed)
                    for clip in sample.clips:
                        assert not clip.sample.numbers
                        assert not clip.sample.vitals
                        assert all(projectile.phase != 'impact' for projectile in clip.sample.projectiles)
                        if isinstance(clip.sample, CastSample):
                            assert not clip.sample.delivery_enabled
                assert not sample_choreography(group, group.complete_ms + 100).clips
            else:
                assert not head.root.canceled
                assert any(isinstance(node.fact, DamageFact) and node.fact.stage == 'applied'
                           for node in head.events)
        state = reduce_presentation_group(state, presentation)
    assert found
