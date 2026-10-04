"""Native threshold/prevention outcomes drive contacts without invented damage."""

import pytest

from dnd.core.life_types import LifeState
from game.animation import media_target_applies, media_phase_anchor_ms
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.player_facts import DamageResultFact, LifeFact
from game.player_reduction import reduce_lineage
from tests.game.player_helpers import player_history
from tests.game.power_word_scenarios import power_word_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.mark.parametrize("program,outcome", [
    ("kill", "applied"), ("kill", "threshold"), ("kill", "ward"), ("kill", "prone"),
    ("stun", "applied"), ("stun", "threshold"), ("stun", "immune"),
])
def test_native_words_only_show_the_contact_the_recipient_received(data, program, outcome):
    history = power_word_history(program=program, outcome=outcome)
    for observer in ("caster", "recipient"):
        state, roots = player_history(history, role=observer)
        contacts = 0
        for root in roots:
            group = bind_choreography(state, root, data)
            assert not group.gaps
            assert not any(isinstance(row.fact, DamageResultFact) for row in root.events)
            for clip in group.nodes:
                if not isinstance(clip.bound, BoundCast):
                    continue
                timeline = clip.bound.timeline
                assert timeline.recipe.definitionRef.content_id == "spell.power_word_" + program
                expected = outcome in ("applied", "prone")
                for track in timeline.recipe.media:
                    assert any(media_target_applies(track, app) for app in timeline.source.applications) == expected
                if program == "kill":
                    deaths = [cue for cue in group.lifecycle if isinstance(cue.event.fact, LifeFact)
                              and cue.event.fact.new_state is LifeState.DEAD]
                    assert bool(deaths) == expected
                    asset = data.projectile_assets['necrotic.kill.front']
                    assert asset.phases.impact is not None
                    impact = media_phase_anchor_ms(asset.phases.impact, 'contact', fps=asset.fps)
                    assert timeline.recipe.contact.delayMs == impact
                    for cue in deaths:
                        assert cue.start_ms == pytest.approx(clip.start_ms + timeline.release_ms + impact)
                contacts += 1
            state = reduce_lineage(state, root)
        assert contacts == 1
