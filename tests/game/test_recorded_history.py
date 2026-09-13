"""Recorded bytes reproduce native histories through the same presentation."""

import json

import pytest

from dnd.core.base_object import BaseObject
from dnd.core.dice import DiceRoll
from dnd.core.events import EventQueue
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from devtools.animation_review.cases import load_cases
from devtools.animation_review.produce import produce
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.motion import bind_motion, sample_motion
from game.presentation import reduce_lineage
from game.replay import decode_sequence, encode_sequence
from game.player_reduction import reduce_lineage as reduce_player_lineage
from tests.game.player_helpers import player_inputs


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
    player, public_lineages = player_inputs(source.initialization, lineages)
    data = load_animation_data()
    for index, (lineage, public) in enumerate(zip(lineages, public_lineages, strict=True), start=1):
        after = reduce_lineage(before, lineage)
        assert after == expected[index]
        motion = bind_motion(player, public, data)
        if motion is not None:
            assert sample_motion(motion, data, motion.complete_ms).complete
        else:
            group = bind_choreography(player, public, data)
            assert sample_choreography(group, group.complete_ms).complete
        before = after
        player = reduce_player_lineage(player, public)
    assert EventQueue.event_cursor() == 0
    assert BaseObject._registry == {}
    assert DiceRoll._registry == existing_rolls
    assert not Entity.get_all_entities()


def test_native_v2_before_additive_ai_facts_still_replays_presentation() -> None:
    source = produce(next(case for case in load_cases() if case.id == "walk-recovery"))
    payload = json.loads(encode_sequence(source.initialization, source.lineages))
    pending = [payload]
    removed = set()
    additions = {
        "dnd.core.events.EntityCreatedEvent": ("healing_blocked",),
        "dnd.core.events.SensoryUpdateEvent": ("hazardous_cells_changed",),
        "dnd.core.events.SpatialChangeEvent": ("tile_state", "tile_present", "object_state"),
    }
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for key in additions.get(value.get("wire_type", ""), ()):
                value.pop(key)
                removed.add(key)
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    assert {"healing_blocked", "hazardous_cells_changed"} <= removed
    reset_engine_runtime()
    before, lineages = decode_sequence(json.dumps(payload).encode())
    expected = source.before
    for lineage in source.lineages:
        expected = reduce_lineage(expected, lineage)
    for lineage in lineages:
        before = reduce_lineage(before, lineage)
    assert before.actors == expected.actors
    assert before.senses is not None and expected.senses is not None
    assert before.senses.entities == expected.senses.entities
    assert before.senses.visible == expected.senses.visible
    assert EventQueue.event_cursor() == 0


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
