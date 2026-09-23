"""Recorded bytes reproduce native histories through the same presentation."""

import json

import pytest

from dnd.core.base_object import BaseObject, PASSIVE_EVENT_REPLAY
from dnd.actions import AttackEvent
from dnd.core.dice import DiceRoll
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue, StepMovementEvent, TakeDamageEvent
from dnd.core.creature_types import DamageType
from dnd.core.life_types import LifeState
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from devtools.animation_review.cases import load_cases
from devtools.animation_review.produce import produce
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.motion import bind_motion, sample_motion
from game.presentation import capture_lineage, reduce_lineage
from game.replay import RecordedSequence, capture_history, decode_sequence, encode_sequence
from game.player_facts import StepFact
from game.player_reduction import reduce_lineage as reduce_player_lineage
from tests.game.player_helpers import player_inputs
from tests.game.scenarios import _healing_encounter
from tests.game.persistent_spell_scenarios import persistent_spell_history


def test_second_hit_on_dying_actor_replays_native_zero_hp_from_saved_events() -> None:
    with _healing_encounter() as (before, observer, target, _encounter):
        roots = []
        for amount in (target.get_normal_hp(), 1):
            cursor = EventQueue.event_cursor()
            target.receive_damage(amount, DamageType.FIRE, observer.uuid)
            roots.extend(capture_lineage(event, observer_uuid=observer.uuid)
                for _, event in EventQueue.iter_events_since(cursor)
                if event.phase is EventPhase.COMPLETION and event.parent_lineage is None)
        assert target.get_normal_hp() == 0 and target.health.life_state is LifeState.DYING
        assert target.death_save_failures == 1
        identity = target.uuid
        history = capture_history(before, tuple(roots))
        blob = encode_sequence(history.initialization, history.lineages)
    native, restored = decode_sequence(blob)
    public, public_roots = player_inputs(history.initialization, restored)
    injuries = [event for lineage in restored for event in lineage.events
                if isinstance(event, DamageAppliedEvent)]
    assert [event.resulting_normal_hp for event in injuries] == [0, 0]
    for lineage in restored:
        native = reduce_lineage(native, lineage)
    for lineage in public_roots:
        public = reduce_player_lineage(public, lineage)
    assert native.actors[identity].normal_hp == public.actors[identity].normal_hp == 0
    assert native.actors[identity].life_state is public.actors[identity].life_state is LifeState.DYING
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


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
        "dnd.core.events.SensoryUpdateEvent": (
            "hazardous_cells_changed", "spatial_effects_changed", "spatial_effects_removed",
        ),
        "dnd.core.events.SpatialChangeEvent": ("tile_state", "tile_present", "object_state"),
    }
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for key in additions.get(value.get("wire_type", ""), ()):
                previous = value.pop(key)
                if key in {"spatial_effects_changed", "spatial_effects_removed"}:
                    assert not previous
                removed.add(key)
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    assert {"healing_blocked", "hazardous_cells_changed", "spatial_effects_changed", "spatial_effects_removed"} <= removed
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


@pytest.mark.parametrize("delivery", ("melee", "missile"))
def test_recordings_before_interception_owner_preserve_results_without_inventing_provenance(delivery):
    history = persistent_spell_history(program="shield", shield_delivery=delivery)
    encoded = encode_sequence(history.initialization, history.lineages)
    _, current = decode_sequence(encoded)
    original = {event.uuid: (event.canceled, event.intercepted_by_condition_uuid)
                for lineage in current for event in lineage.events
                if isinstance(event, (AttackEvent, TakeDamageEvent))}
    assert any(owner is not None for _, owner in original.values())
    payload = json.loads(encoded)
    pending, removed = [payload], 0
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if value.get("wire_type") in ("dnd.actions.AttackEvent", "dnd.core.events.TakeDamageEvent"):
                value.pop("intercepted_by_condition_uuid")
                removed += 1
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    assert removed
    state, legacy = decode_sequence(json.dumps(payload).encode())
    restored = {event.uuid: (event.canceled, event.intercepted_by_condition_uuid)
                for lineage in legacy for event in lineage.events
                if isinstance(event, (AttackEvent, TakeDamageEvent))}
    assert restored == {identity: (canceled, None) for identity, (canceled, _) in original.items()}
    expected, _ = decode_sequence(encoded)
    for old, new in zip(legacy, current, strict=True):
        state, expected = reduce_lineage(state, old), reduce_lineage(expected, new)
    assert state == expected
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_native_spell_archives_before_subeffect_identity_replay_unchanged() -> None:
    source = produce(next(case for case in load_cases() if case.id == "firebolt-level"))
    payload = json.loads(encode_sequence(source.initialization, source.lineages))
    pending, removed = [payload], 0
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if value.get("wire_type") == "dnd.actions.SpellEvent":
                assert value.pop("effect_id") is None
                removed += 1
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    assert removed > 0
    reset_engine_runtime()
    before, lineages = decode_sequence(json.dumps(payload).encode())
    assert before == source.before and lineages == source.lineages
    player, public = player_inputs(source.initialization, lineages)
    data = load_animation_data()
    for lineage in public:
        bound = bind_choreography(player, lineage, data)
        assert not bound.gaps
        assert sample_choreography(bound, bound.complete_ms).complete
        player = reduce_player_lineage(player, lineage)
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


@pytest.mark.parametrize("case_id", ("walk-recovery", "movement-haste-corners"))
def test_native_archive_before_grant_and_resolved_speed_preserves_unknown_facts(case_id: str) -> None:
    """Older records retain their received state, without invented grant/speed."""
    source = produce(next(case for case in load_cases() if case.id == case_id))
    payload = json.loads(encode_sequence(source.initialization, source.lineages))
    pending = [payload]
    removed: dict[str, int] = {}
    additions = {
        "dnd.core.events.EntityCreatedEvent": "temporary_hit_points_grant",
        "dnd.core.events.StepMovementEvent": "resolved_speed_feet",
    }
    while pending:
        row = pending.pop()
        if isinstance(row, dict):
            field = additions.get(row.get("wire_type", ""))
            if field is not None:
                del row[field]
                removed[field] = removed.get(field, 0) + 1
            pending.extend(row.values())
        elif isinstance(row, list):
            pending.extend(row)
    assert set(removed) == set(additions.values())
    reset_engine_runtime()
    archive = RecordedSequence.model_validate_json(json.dumps(payload), context=PASSIVE_EVENT_REPLAY)
    before, lineages = decode_sequence(json.dumps(payload).encode())
    assert before == source.before
    steps = [event for lineage in lineages for event in lineage.events
             if isinstance(event, StepMovementEvent)]
    assert steps and all(event.resolved_speed_feet is None for event in steps)
    public, roots = player_inputs(archive.initialization, lineages)
    assert all(actor.temporary_hp_grant is None for actor in public.actors.values())
    public_steps = [node.fact for root in roots for node in root.events
                    if isinstance(node.fact, StepFact)]
    assert public_steps and all(fact.resolved_speed_feet is None for fact in public_steps)
    for expected, retained, projected in zip(source.lineages, lineages, roots, strict=True):
        assert retained.root.uuid == expected.root.uuid
        assert retained.root.lineage_uuid == expected.root.lineage_uuid
        assert [(row.uuid, row.parent_event, row.parent_lineage) for row in retained.events] == [
            (row.uuid, row.parent_event, row.parent_lineage) for row in expected.events]
        before = reduce_lineage(before, retained)
        public = reduce_player_lineage(public, projected)
    assert public.senses is not None and before.senses is not None
    assert public.senses.position == before.senses.position
    assert EventQueue.event_cursor() == 0
    assert BaseObject._registry == {} and not Entity.get_all_entities()
