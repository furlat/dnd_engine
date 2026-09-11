"""Recorded bytes reproduce native histories through the same presentation."""

import json

import pytest

from dnd.core.base_object import BaseObject
from dnd.core.dice import DiceRoll
from dnd.core.events import EventQueue
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from devtools.animation_review.cases import load_cases, produce
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.motion import bind_motion, sample_motion
from game.presentation import reduce_lineage
from game.replay import decode_sequence, encode_sequence


@pytest.mark.parametrize("case_id", (
    "walk-recovery", "shove-spikes-lethal", "firebolt-level",
    "movement-haste-corners", "telekinesis-displacement", "healing-dying",
))
def test_saved_bytes_preserve_every_successor_and_concrete_lineage(case_id: str) -> None:
    source = produce(next(case for case in load_cases() if case.id == case_id))
    expected = [source.before]
    for lineage in source.lineages:
        expected.append(reduce_lineage(expected[-1], lineage))
    payload = encode_sequence(source.initialization, source.lineages)
    reset_engine_runtime()
    existing_rolls = dict(DiceRoll._registry)
    before, lineages = decode_sequence(payload)
    assert before == source.before
    assert lineages == source.lineages
    data = load_animation_data()
    for index, lineage in enumerate(lineages, start=1):
        after = reduce_lineage(before, lineage)
        assert after == expected[index]
        motion = bind_motion(before, lineage, data)
        if motion is not None:
            assert sample_motion(motion, data, motion.complete_ms).complete
        else:
            group = bind_choreography(before, lineage, data)
            assert sample_choreography(group, group.complete_ms).complete
        before = after
    assert EventQueue.event_cursor() == 0
    assert BaseObject._registry == {}
    assert DiceRoll._registry == existing_rolls
    assert not Entity.get_all_entities()


def test_incomplete_recorded_event_does_not_invent_identity() -> None:
    source = produce(next(case for case in load_cases() if case.id == "ranged-hit"))
    payload = json.loads(encode_sequence(source.initialization, source.lineages))
    del payload["lineages"][0]["root"]["uuid"]
    reset_engine_runtime()
    existing_rolls = dict(DiceRoll._registry)
    with pytest.raises(ValueError, match="incomplete recorded.*uuid"):
        decode_sequence(json.dumps(payload).encode())
    assert EventQueue.event_cursor() == 0
    assert BaseObject._registry == {}
    assert DiceRoll._registry == existing_rolls
