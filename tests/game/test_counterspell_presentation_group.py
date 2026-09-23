"""Real Counterspell roots stay independent while their playback shares a head."""

import pytest

from dnd.spells.abjuration import CounterspellReactionEvent
from game.player_facts import ActionFact, SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation_group import presentation_groups, reduce_presentation_group
from game.replay import RecordedSequence, decode_sequence, encode_sequence
from tests.game.interruption_scenarios import interruption_history


@pytest.fixture(scope="module", params=(True, False))
def history(request):
    return request.param, interruption_history(blocker="counterspell", spell="fireball", blocked=request.param)


@pytest.mark.parametrize("role", ("caster", "defender"))
def test_counterspell_recording_preserves_result_and_causal_group(history, role):
    succeeded, recorded = history
    native = recorded.views[role]
    _, restored = decode_sequence(encode_sequence(native.initialization, native.lineages))
    reactions = [head for head in restored if isinstance(head.root, CounterspellReactionEvent)]
    assert len(reactions) == 1
    assert reactions[0].root.parent_lineage is None
    public = project_sequence(RecordedSequence(initialization=native.initialization, lineages=restored))
    before, heads = decode_player_sequence(encode_player_sequence(public))
    groups = presentation_groups(heads)
    # Every native root remains exactly once and in its received order.
    assert tuple(head for group in groups for head in group.lineages) == heads
    paired = [group for group in groups if group.reactions]
    assert len(paired) == 1
    group = paired[0]
    assert isinstance(group.primary.root.fact, SpellFact)
    assert group.primary.root.fact.behavior_id == "spell.fireball"
    assert group.primary.root.canceled is succeeded
    reaction, = group.reactions
    assert reaction.root.parent_lineage is None
    fact = reaction.root.fact
    assert isinstance(fact, ActionFact) and fact.reaction is not None
    assert fact.behavior_id == "reaction.spell.counterspell"
    assert fact.reaction.triggered_lineage_uuid == group.primary.root.lineage_uuid
    assert fact.reaction.succeeded is succeeded
    assert fact.reaction.automatic is False
    ordinary = before
    for head in heads:
        ordinary = reduce_lineage(ordinary, head)
    grouped = before
    for item in groups:
        grouped = reduce_presentation_group(grouped, item)
    assert grouped == ordinary
    # A separately received reaction remains present even without its trigger.
    isolated, = presentation_groups((reaction,))
    assert isolated.primary == reaction and isolated.lineages == (reaction,)
    assert not isolated.reactions
