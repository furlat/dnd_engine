"""Real area conditions appear at contact and spread on the historical clock."""

import pytest

from devtools.animation_review.cases import load_cases
from devtools.animation_review.produce import produce
from dnd.core.events import EventQueue
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.player_facts import SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.fixture(scope="module", params=("empty", "wall-east", "repeat"))
def recording(request):
    case = next(row for row in load_cases() if row.id == "spell-handoff-fireball-" + request.param)
    return produce(case)


def ash(state):
    return {position: tuple(row.condition_uuid for row in tile.residues if row.residue_id == "residue.ashen")
            for position, tile in state.tiles.items()
            if any(row.residue_id == "residue.ashen" for row in tile.residues)}


def wall_ash(state):
    return {identity: obj.item.surface_residues for identity, obj in state.objects.items()
            if obj.item.surface_residues}


@pytest.mark.parametrize("role", ("caster", "perceiver"))
def test_recorded_ashen_begins_at_contact_and_spreads_before_blast_ends(data, recording, role):
    state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(recording.views[role])))
    for lineage in lineages:
        after = reduce_lineage(state, lineage)
        if isinstance(lineage.root.fact, SpellFact):
            group = bind_choreography(state, lineage, data)
            assert not group.gaps
            node, = group.nodes
            ground = node.bound.timeline.ground_delivery
            assert ground is not None
            at = node.start_ms + ground.travel_end_ms
            before_contact = sample_choreography(group, at - .001).displayed
            contact = sample_choreography(group, at).displayed
            later = sample_choreography(group, at + 500).displayed
            assert ash(before_contact) == ash(state)
            assert wall_ash(before_contact) == wall_ash(state)
            assert ground.target.grid in ash(contact), "The impact center must darken at contact, not head completion"
            assert ash(later) == ash(after)
            assert wall_ash(later) == wall_ash(after)
            assert at + 500 < group.complete_ms
            if not ash(state):
                middle = sample_choreography(group, at + 200).displayed
                assert set(ash(contact)) < set(ash(middle)) < set(ash(later))
            else:
                for elapsed in (0, at, at + 200, at + 500):
                    assert ash(sample_choreography(group, elapsed).displayed) == ash(state)
            # Seeking back reselects retained state; it cannot consume reveal steps.
            assert ash(sample_choreography(group, at - .001).displayed) == ash(state)
        state = after
    assert EventQueue.event_cursor() == 0
