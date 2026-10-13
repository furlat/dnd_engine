"""Exclusive server current state publishes the same detached operations as replay."""

from copy import deepcopy
from dataclasses import replace
import random
from uuid import uuid4

import pytest

from dnd.conditions import Poisoned
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, EmptyLogData
from dnd.core.events import EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.player.application import capture_application_operation, initialize_audiences
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import PlayerUpdate
from dnd.player.reduction import apply_current_operation, prepare_current_operation, reduce_operation
from dnd.player.session import Operation, close_session, create_session, snapshot_player_hud
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import LightLevel


@pytest.fixture
def session():
    state = random.getstate()
    random.seed(0)
    value = create_session()
    try:
        yield value
    finally:
        close_session(value)
        reset_engine_runtime()
        random.setstate(state)


def condition_operation(session):
    target = session.game.entities[session.player_uuids[0]]
    start = EventQueue.event_cursor()
    target.add_condition(Poisoned(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    roots = tuple(event for _, event in EventQueue.iter_events_since(start)
        if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
    return Operation(start_cursor=start, end_cursor=EventQueue.event_cursor(), roots=roots,
        hud_by_seat=tuple((seat, snapshot_player_hud(session, audience=audience))
            for seat, audience in session.seats.items()))


def test_exclusive_current_operation_matches_cold_public_replay(session):
    catalog = ui_content_manifest()
    runtime, _ = initialize_audiences(session, catalog, exclusive_current=True)
    reference, _ = initialize_audiences(session, catalog)
    before = deepcopy(runtime['party'].latest)
    frozen_before = deepcopy(before)
    operation = condition_operation(session)
    expected = capture_application_operation(reference, operation, catalog)['party']
    actual = capture_application_operation(runtime, operation, catalog)['party']
    assert actual == expected
    assert runtime['party'].latest == reference['party'].latest
    detached = PlayerUpdate.model_validate_json(actual.model_dump_json())
    close_session(session)
    reset_engine_runtime()
    assert reduce_operation(before, detached) == runtime['party'].latest
    assert before == frozen_before


@pytest.mark.parametrize('exclusive', [False, True])
def test_later_seat_capture_failure_preserves_all_published_current_states(session, exclusive):
    audience = next(iter(session.seats.values()))
    session.seats.clear()
    session.seats.update(first=audience, second=audience)
    catalog = ui_content_manifest()
    runtime, _ = initialize_audiences(session, catalog, exclusive_current=exclusive)
    before = {seat: deepcopy(value.latest) for seat, value in runtime.items()}
    operation = condition_operation(session)
    first, second = operation.hud_by_seat
    invalid = replace(operation, hud_by_seat=(first, (second[0], replace(second[1], observer_uuid=uuid4()))))
    with pytest.raises(ValueError, match='another audience'):
        capture_application_operation(runtime, invalid, catalog)
    assert {seat: value.latest for seat, value in runtime.items()} == before


def test_owned_preflight_rejects_late_invalid_hud_before_applying_valid_facts(session):
    catalog = ui_content_manifest()
    owned, _ = initialize_audiences(session, catalog, exclusive_current=True)
    reference, _ = initialize_audiences(session, catalog)
    before = deepcopy(owned['party'].latest)
    update = capture_application_operation(reference, condition_operation(session), catalog)['party']
    invalid = update.model_copy(update={'hud': replace(update.hud, revision=update.hud.revision + 1000)})
    with pytest.raises(ValueError, match='future operation'):
        prepare_current_operation(owned['party'].latest, invalid, log_count=0)
    assert owned['party'].latest == before
    prepared = prepare_current_operation(owned['party'].latest, update, log_count=0)
    apply_current_operation(owned['party'].latest, update, prepared, owned['party'].current_composition)
    assert owned['party'].latest == reduce_operation(before, update)


def logged_movement_operation(session, destination):
    actor = session.game.entities[session.player_uuids[0]]
    start = EventQueue.event_cursor()
    Entity.update_entity_position(actor, destination)
    text = f'{actor.name} checks the passage at {destination}.'
    EventQueue.push_combat_log(CombatLogEntry(entry_type=CombatLogEntryType.ACTION,
        source_uuid=str(actor.uuid), source_name=actor.name,
        compact=text, verbose=text, detailed=text, data=EmptyLogData()), actor.uuid)
    originals = tuple(session.logs.log_appends)
    session.logs.log_appends.clear()
    assert originals
    return Operation(start_cursor=start, end_cursor=EventQueue.event_cursor(),
        roots=tuple(event for _, event in EventQueue.iter_events_since(start)
            if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)),
        original_logs=originals,
        hud_by_seat=tuple((seat, snapshot_player_hud(session, audience=audience))
            for seat, audience in session.seats.items()))


def test_owned_log_history_matches_public_replay_across_native_operations(session):
    catalog = ui_content_manifest()
    owned, _ = initialize_audiences(session, catalog, exclusive_current=True)
    reference, _ = initialize_audiences(session, catalog)
    initial = deepcopy(owned['party'].latest)
    frozen_initial = deepcopy(initial)
    published_logs = initial.combat_log_appends
    encoded = []
    accepted = []
    for destination in ((11, 10), (12, 10), (11, 10)):
        operation = logged_movement_operation(session, destination)
        expected = capture_application_operation(reference, operation, catalog)['party']
        actual = capture_application_operation(owned, operation, catalog)['party']
        assert actual == expected
        assert actual.combat_log_appends
        published_logs += actual.combat_log_appends
        assert owned['party'].committed_log_count == len(published_logs)
        public_current = replace(owned['party'].latest, combat_log_appends=published_logs)
        assert public_current == reference['party'].latest
        accepted.append(deepcopy(public_current))
        encoded.append(actual.model_dump_json())
    assert tuple(row.encounter_log_index for row in published_logs) == tuple(range(len(published_logs)))
    close_session(session)
    reset_engine_runtime()
    replayed = initial
    prior_states = []
    for packet, expected in zip(encoded, accepted):
        prior_states.append((replayed, deepcopy(replayed)))
        replayed = reduce_operation(replayed, PlayerUpdate.model_validate_json(packet))
        assert replayed == expected
    assert initial == frozen_initial
    assert all(previous == frozen for previous, frozen in prior_states)


def test_out_of_order_later_seat_withholds_all_current_states_and_admission_metadata(session):
    audience = next(iter(session.seats.values()))
    session.seats.clear()
    session.seats.update(first=audience, second=audience)
    catalog = ui_content_manifest()
    owned, _ = initialize_audiences(session, catalog, exclusive_current=True)
    # This audience has already advanced past the next operation's start. Capture
    # still succeeds; the canonical reducer must reject its occurrence boundary.
    owned['second'].latest.reducer_cursor += 1
    before = {seat: deepcopy(runtime.latest) for seat, runtime in owned.items()}
    counts = {seat: runtime.committed_log_count for seat, runtime in owned.items()}
    metadata = {seat: (dict(runtime.known_names), set(runtime.known_content_ids),
        set(runtime.known_content_keys), runtime.known_connector_ids, runtime.known_connector_values,
        runtime.content_catalog) for seat, runtime in owned.items()}
    operation = logged_movement_operation(session, (11, 10))
    with pytest.raises(ValueError, match='Operation occurrence sequence has a gap'):
        capture_application_operation(owned, operation, catalog)
    assert {seat: runtime.latest for seat, runtime in owned.items()} == before
    assert {seat: runtime.committed_log_count for seat, runtime in owned.items()} == counts
    assert {seat: (runtime.known_names, runtime.known_content_ids, runtime.known_content_keys,
        runtime.known_connector_ids, runtime.known_connector_values, runtime.content_catalog)
        for seat, runtime in owned.items()} == metadata


@pytest.mark.parametrize('exclusive', [False, True])
def test_later_seat_missing_tile_base_withholds_all_current_states_and_metadata(session, exclusive):
    audience = next(iter(session.seats.values()))
    session.seats.clear()
    session.seats.update(first=audience, second=audience)
    catalog = ui_content_manifest()
    runtimes, _ = initialize_audiences(session, catalog, exclusive_current=exclusive)
    position = session.game.entities[session.player_uuids[0]].position
    assert runtimes['first'].latest.tiles[position].resolved_light is not LightLevel.DIM_LIGHT
    # Fault injection at the public reduction boundary: this seat has lost a
    # previously disclosed base. Its producer still correctly emits a field update.
    del runtimes['second'].latest.tiles[position]
    before = {seat: deepcopy(runtime.latest) for seat, runtime in runtimes.items()}
    counts = {seat: runtime.committed_log_count for seat, runtime in runtimes.items()}
    metadata = {seat: (dict(runtime.known_names), set(runtime.known_content_ids),
        set(runtime.known_content_keys), runtime.known_connector_ids, runtime.known_connector_values,
        runtime.content_catalog) for seat, runtime in runtimes.items()}
    start = EventQueue.event_cursor()
    # Carried sources already make this cell VERY_BRIGHT; an ambient change
    # would be masked. A native cap changes the resolved, observable value.
    assert get_map().apply_light_modifier(uuid4(), {position}, LightLevel.DIM_LIGHT, cap=True) == {position}
    operation = Operation(start_cursor=start, end_cursor=EventQueue.event_cursor(),
        roots=tuple(event for _, event in EventQueue.iter_events_since(start)
            if event.parent_lineage is None and event.phase is EventPhase.COMPLETION),
        hud_by_seat=tuple((seat, snapshot_player_hud(session, audience=value))
            for seat, value in session.seats.items()))
    with pytest.raises(ValueError, match='already known tile'):
        capture_application_operation(runtimes, operation, catalog)
    assert {seat: runtime.latest for seat, runtime in runtimes.items()} == before
    assert {seat: runtime.committed_log_count for seat, runtime in runtimes.items()} == counts
    assert {seat: (runtime.known_names, runtime.known_content_ids, runtime.known_content_keys,
        runtime.known_connector_ids, runtime.known_connector_values, runtime.content_catalog)
        for seat, runtime in runtimes.items()} == metadata
