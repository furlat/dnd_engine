"""Public transfer cues explain existing clocks, without changing their results."""

import pytest
from pydantic import TypeAdapter

from game.animation_data import load_animation_data
from game.choreography import bind_choreography, walk_bound_timelines, BoundChoreography
from dnd.player.reduction import reduce_lineage, state_before_event, lineage_branch
from dnd.player.facts import ForcedMovementFact
from game.forced_movement import bind_forced_movement
from game.timing_evidence import TimingEvidence, validate_timing_evidence
from tests.game.player_helpers import player_history
from tests.game.portal_scenarios import portal_history
from tests.game.forced_movement_scenarios import forced_movement_history


@pytest.fixture(scope='module')
def data():
    return load_animation_data()


def check(rows):
    assert rows and not validate_timing_evidence(rows)
    codec = TypeAdapter(tuple[TimingEvidence, ...])
    assert codec.validate_json(codec.dump_json(rows)) == rows


@pytest.mark.parametrize('role', ('traveler', 'arrival', 'departure'))
def test_portal_clock_provenance_preserves_independent_endpoint_grants(data, role):
    before, roots = player_history(portal_history(program='hatch-walk'), role=role)
    found = 0
    for root in roots:
        group = bind_choreography(before, root, data)
        for visit in walk_bound_timelines(group):
            if not isinstance(visit.timeline, BoundChoreography):
                continue
            for cue in visit.timeline.portals:
                found += 1
                check(cue.timing_evidence)
                values = {row.target.anchor: row.at_ms for row in cue.timing_evidence}
                assert values['arrival'] == cue.arrival_ms
                assert values['settled'] == cue.settled_ms
                assert values['complete'] == cue.complete_ms
                if role == 'arrival':
                    assert cue.departure is None and cue.portal_uuid is None
                    assert all(source.reference.kind != 'spatial' for row in cue.timing_evidence for source in row.inputs)
        assert group.after == reduce_lineage(before, root)
        before = group.after
    assert found


@pytest.mark.parametrize('mechanism', ('shove', 'telekinesis'))
def test_displacement_cues_explain_brace_travel_and_native_spatial_admissions(data, mechanism):
    history = forced_movement_history(mechanism=mechanism, seed=1 if mechanism == 'telekinesis' else 0,
        destination=(6, 4) if mechanism == 'telekinesis' else None)
    before, roots = player_history(history)
    found = 0
    for root in roots:
        group = bind_choreography(before, root, data)
        for visit in walk_bound_timelines(group):
            if not isinstance(visit.timeline, BoundChoreography):
                continue
            for shove in visit.timeline.shoves:
                check(shove.timing_evidence)
                assert shove.timing_evidence[-1].at_ms == shove.contact_ms
            for cue in visit.timeline.forced_movement:
                found += 1
                check(cue.timing_evidence)
                for identity, when in cue.arrivals:
                    assert any(row.target.identity == identity and row.at_ms == when for row in cue.timing_evidence)
                complete = [row.at_ms for row in cue.timing_evidence if row.target.anchor == 'complete']
                assert complete[-1] == cue.complete_ms
        if mechanism == 'telekinesis':
            # Production Telekinesis selects a body-hop owner. Exercise this
            # standalone binder on the same admitted displacement branch rather
            # than claiming its production route uses ForcedMovementCue.
            for event in root.events:
                if isinstance(event.fact, ForcedMovementFact):
                    cue = bind_forced_movement(state_before_event(before, root, event),
                        lineage_branch(root, event), data, 100., {})
                    check(cue.timing_evidence)
                    assert any(row.target.anchor == 'contact' and row.at_ms == cue.travel_end_ms
                               for row in cue.timing_evidence)
                    found += 1
        assert group.after == reduce_lineage(before, root)
        before = group.after
    assert found
