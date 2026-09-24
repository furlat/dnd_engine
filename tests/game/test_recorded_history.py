"""Recorded bytes reproduce native histories through the same presentation."""

import gzip
import json
from pathlib import Path
from uuid import uuid4

import pytest

from dnd.core.base_object import BaseObject, PASSIVE_EVENT_REPLAY
from dnd.actions import AttackEvent, JumpEvent, MovementEvent, ShoveEvent, SpellEvent
from dnd.spells.abjuration import CounterspellReactionEvent
from dnd.core.base_actions import ActionEvent
from dnd.core.dice import DiceRoll
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue, StepMovementEvent, TakeDamageEvent
from dnd.core.creature_types import DamageType
from dnd.core.life_types import LifeState
from dnd.core.equipment_types import WeaponSlot
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from devtools.animation_review.cases import load_cases
from devtools.animation_review.produce import produce
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.motion import bind_motion, sample_motion
from game.presentation import capture_lineage, reduce_lineage
from game.replay import RecordedSequence, capture_history, decode_sequence, encode_sequence
from game.event_record import decode_event, encode_event
from game.player_facts import StepFact
from game.player_reduction import reduce_lineage as reduce_player_lineage
from tests.game.player_helpers import player_inputs
from tests.game.scenarios import _healing_encounter
from tests.game.persistent_spell_scenarios import persistent_spell_history


ACTION_RECEIPT_MODELS = (
    (ActionEvent, {}),
    (AttackEvent, {"weapon_slot": WeaponSlot.MELEE_MAIN}),
    (SpellEvent, {}),
    (MovementEvent, {"start_position": (1, 1), "end_position": (2, 1)}),
    (JumpEvent, {"start_position": (1, 1), "end_position": (2, 1)}),
    (ShoveEvent, {}),
    (CounterspellReactionEvent, {"triggered_event_uuid": uuid4(), "triggered_lineage_uuid": uuid4(),
        "incoming_spell_name": "Fire Bolt", "incoming_spell_level": 0,
        "counterspell_slot_level": 3, "automatic": True, "succeeded": True}),
)


@pytest.mark.parametrize("row", json.loads((Path(__file__).parent / "fixtures/legacy-completed-actions.json").read_text()),
                         ids=lambda row: row["case"] + ":" + row["event"]["behavior_id"])
def test_original_completed_attack_and_jump_rows_preserve_absent_receipt(row):
    reset_engine_runtime()
    original = row["event"]
    assert original["phase"] == "completion" and original["canceled"] is False
    assert "action_economy_spent" not in original
    restored = decode_event(original)
    encoded = encode_event(restored)
    assert "action_economy_spent" not in encoded
    assert decode_event(encoded) == restored
    for key in ("uuid", "lineage_uuid", "parent_event", "parent_lineage", "phase", "canceled",
                "source_entity_uuid", "target_entity_uuid", "behavior_id", "costs", "status_message"):
        assert encoded[key] == original[key]
    assert EventQueue.event_cursor() == 0 and BaseObject._registry == {}


@pytest.mark.parametrize("family", ("device", "door", "web"))
def test_retained_completion_archives_preserve_absent_receipts_on_native_round_trip(family):
    reset_engine_runtime()
    rolls = dict(DiceRoll._registry)
    path = Path(__file__).parent / f"fixtures/legacy-{family}-destruction.json.gz"
    original = gzip.decompress(path.read_bytes())
    restored = RecordedSequence.model_validate_json(original, context=PASSIVE_EVENT_REPLAY)
    blob = encode_sequence(restored.initialization, restored.lineages)
    again = RecordedSequence.model_validate_json(blob, context=PASSIVE_EVENT_REPLAY)
    assert again == restored

    # Check bytes at the actual native boundary, not default-valued model fields.
    expected = json.loads(original)
    actual = json.loads(blob)
    pending = [(expected, actual)]
    checked = 0
    while pending:
        old, new = pending.pop()
        if isinstance(old, dict):
            fields = ({"action_economy_spent", "harmful", "harmful_target_entity_uuids", "target_type"}
                      if old.get("wire_type") == "dnd.actions.SpellEvent"
                      else {"action_economy_spent"}
                      if old.get("wire_type") in {"dnd.core.base_actions.ActionEvent", "dnd.actions.MovementEvent"}
                      else set())
            for name in fields:
                assert name not in old and name not in new
            checked += bool(fields)
            pending.extend((value, new[key]) for key, value in old.items())
        elif isinstance(old, list):
            assert len(old) == len(new)
            pending.extend(zip(old, new, strict=True))
    assert checked > 0
    assert decode_sequence(original) == decode_sequence(blob)
    player, roots = player_inputs(again.initialization, again.lineages)
    for root in roots:
        player = reduce_player_lineage(player, root)
    assert all(node.cancellation is None for root in roots for node in root.events if not node.canceled)
    assert EventQueue.event_cursor() == 0 and BaseObject._registry == {}
    assert DiceRoll._registry == rolls


@pytest.mark.parametrize("model,extra", ACTION_RECEIPT_MODELS)
@pytest.mark.parametrize("spent", (None, False, True), ids=("live-default", "explicit-false", "explicit-true"))
def test_current_recorded_action_receipts_remain_explicit(model, extra, spent):
    reset_engine_runtime()
    values = dict(source_entity_uuid=uuid4(), phase=EventPhase.COMPLETION, use_register=False)
    if spent is not None:
        values["action_economy_spent"] = spent
    event = model(**values, **extra)
    payload = encode_event(event)
    assert payload["action_economy_spent"] is (False if spent is None else spent)
    assert encode_event(decode_event(payload)) == payload
    if spent is None:
        # All registered actions share the same additive receipt contract.
        # Missing archive evidence stays absent; the live default above does not.
        del payload["action_economy_spent"]
        assert "action_economy_spent" not in encode_event(decode_event(payload))
    assert EventQueue.event_cursor() == 0 and BaseObject._registry == {}


@pytest.mark.parametrize("model,extra", ACTION_RECEIPT_MODELS)
def test_legacy_missing_payment_cancellation_is_not_admitted_as_an_unpaid_action(model, extra):
    reset_engine_runtime()
    event = model(source_entity_uuid=uuid4(), phase=EventPhase.CANCEL,
                  canceled=True, use_register=False, **extra)
    payload = encode_event(event)
    del payload["action_economy_spent"]
    with pytest.raises(ValueError, match="incomplete recorded.*action_economy_spent"):
        decode_event(payload)
    assert EventQueue.event_cursor() == 0 and BaseObject._registry == {}


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
