"""Real control casts remain complete through saved subjective replay and binding."""

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue
from dnd.entity import Entity
from devtools.animation_review.control_cases import control_spell_history
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, bind_motion
from game.condition_media_lifetime import register_condition_lifetimes
from game.player_facts import SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.mark.parametrize("program,saved", [(p, False) for p in (
    "charm", "blindness", "deafness", "grovel", "halt", "flee", "color-spray",
    "silence", "blindness-overlap", "deafness-overlap", "sleep-long")]
    + [(p, True) for p in ("charm", "blindness", "deafness")])
def test_native_control_history_round_trips_and_binds_both_players(data, program, saved):
    history = control_spell_history(program=program, saved=saved)
    assert len(history.views) == 2
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
    for role, native in history.views.items():
        native = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        packet = encode_player_sequence(project_sequence(native))
        before, roots = decode_player_sequence(packet)
        assert b"objective_rows" not in packet and b"identified_entity_observer_uuids" not in packet
        clock, records = 0., {}
        for root in roots:
            identities = {node.lineage_uuid for node in root.events}
            assert all(child in identities for node in root.events for child in node.children_lineages)
            motion = bind_motion(before, root, data)
            group = None if motion is not None else bind_choreography(before, root, data)
            gaps = (tuple(gap for reaction in motion.reactions for gap in reaction.choreography.gaps)
                    if motion is not None else group.gaps)
            assert not gaps, (program, role, root.root.fact, gaps)
            records = register_condition_lifetimes(records, before, data, absolute_start_ms=clock,
                lineage=root, motion=motion, choreography=group)
            clock += (motion.complete_ms if motion is not None else group.complete_ms) + 25
            before = reduce_lineage(before, root)
        if program in ("blindness", "deafness"):
            casts = [node.fact for root in roots for node in root.events
                if isinstance(node.fact, SpellFact) and node.fact.behavior_id == "spell.blindness_deafness"]
            assert casts and {fact.effect_id for fact in casts} == {"control.blinded" if program == "blindness" else "control.deafened"}
        assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
