"""Audience capture retains causal evidence without unrelated sensory payloads."""

import pytest

from dnd.actions_functional import execute_use_action
from dnd.conditions import Invisible
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, EmptyLogData
from dnd.core.effect_types import ObservedChangeRef
from dnd.core.events import EventPhase, EventQueue, SensoryUpdateEvent, StepMovementEvent
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.items.torches import build_torch
from dnd.player.application import capture_application_operation, initialize_audiences, seat_capture_inputs
from dnd.player.audience import PlayerAudience
from dnd.player.capture import Disposition, capture_context, capture_interval, capture_lineages
from dnd.player.capture import reduce_interval, reduce_lineage as reduce_native_lineage
from dnd.player.event_record import decode_event, encode_event
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import ActionFact, SensoryFact
from dnd.player.projection import SeatLogInputs, SessionProjection, begin_projection, project_lineage, project_lineages
from dnd.player.recorded import RecordedSequence, project_sequence
from dnd.player.reduction import reduce_initialization, reduce_lineage
from dnd.player.session import Operation
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import LightLevel
from tests.player.test_recorded_boundary import world
from tests.player.test_emitted_update_replica import session
from dnd.core.cells import mask_from_positions
from dnd.types.cells import cell_in, no_cells, no_rows
from tests.sensory_cells import packed_cells


@pytest.mark.parametrize('members', [(0,), (1,), (0, 1)])
def test_each_audience_gets_identical_light_facts_and_cold_replay(world, members):
    game, built, actors = world
    for actor in actors:
        actor.update_entity_senses(max_distance=8)
    identities = tuple(actors[index].uuid for index in members)
    observer = identities[0]
    audience = PlayerAudience(identities, identities)
    initial = capture_interval(name='audience light capture', start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=observer, audience=audience,
        battlefield_id=built.definition.battlefield_id)
    full_session, admitted_session = SessionProjection(), SessionProjection()
    full_projection, first = begin_projection(full_session, initial)
    admitted_projection, same_first = begin_projection(admitted_session, initial)
    assert first == same_first
    state = reduce_initialization(first)
    full_native, _ = reduce_interval(None, initial)
    admitted_native, _ = reduce_interval(None, initial)
    packets, captured, complete = [], [], []
    omitted = 0
    for light in (LightLevel.DIM_LIGHT, LightLevel.DARKNESS, LightLevel.BRIGHT_LIGHT):
        cursor = EventQueue.event_cursor()
        assert get_map().set_tile_base_light((5, 6), light)
        roots = tuple(event for _, event in EventQueue.iter_events_since(cursor)
            if event.parent_lineage is None and event.phase is EventPhase.COMPLETION)
        full = capture_lineages(roots, observer_uuid=observer, audience=audience)
        admitted = capture_lineages(roots, observer_uuid=observer, audience=audience, omit_foreign_sensory_payloads=True)
        assert len(full) == len(admitted)
        for reference, candidate in zip(full, admitted):
            full_native = reduce_native_lineage(full_native, reference)
            admitted_native = reduce_native_lineage(admitted_native, candidate)
            assert admitted_native == full_native
            assert candidate.objective_rows == reference.objective_rows
            assert candidate.observed_sources == reference.observed_sources
            originals = {event.uuid: event for event in reference.events}
            for identity, disposition in candidate.dispositions:
                assert disposition is Disposition.NOT_DISCLOSED
                assert not audience.observes(originals[identity].observer_uuid)
                omitted += 1
            expected = project_lineage(full_session, full_projection, reference)
            actual = project_lineage(admitted_session, admitted_projection, candidate)
            assert actual == expected
            assert actual is not None
            state = reduce_lineage(state, actual)
            packets.append(actual)
            captured.append(candidate)
            complete.append(reference)
        # The seat loses the grant before learning the now-hidden Tile value: its members' settlement is
        # composed once (plan §3.1), so no member's partial view grants it.
        expected_light = LightLevel.DIM_LIGHT if light is LightLevel.DARKNESS else light
        assert state.tiles[(5, 6)].resolved_light is expected_light
        assert cell_in(state.senses.visible, (5, 6)) is (light is not LightLevel.DARKNESS)
    assert (omitted > 0) is (len(members) == 1)
    saved = RecordedSequence(initialization=initial, lineages=tuple(captured)).model_dump_json()
    original = RecordedSequence(initialization=initial, lineages=tuple(complete)).model_dump_json()
    game.close()
    reset_engine_runtime()
    cold = project_sequence(RecordedSequence.model_validate_json(saved, context=PASSIVE_EVENT_REPLAY))
    assert cold.lineages == tuple(packets)
    assert project_sequence(RecordedSequence.model_validate_json(
        original, context=PASSIVE_EVENT_REPLAY)) == cold
    replayed = reduce_initialization(cold.initialization)
    for packet in cold.lineages:
        replayed = reduce_lineage(replayed, packet)
    assert replayed == state


@pytest.mark.parametrize('guard', ['context', 'log', 'handler'])
def test_foreign_sensory_with_additional_evidence_keeps_its_full_capture(world, guard):
    # Capture boundary input: these are typed recorded fields, not a claim that
    # the ordinary sensory producer emits combat logs or handler presentations.
    _, built, (owner, foreign) = world
    owner.update_entity_senses(max_distance=8)
    initial = capture_interval(name='additional sensory evidence', start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=owner.uuid,
        battlefield_id=built.definition.battlefield_id)
    event = SensoryUpdateEvent(source_entity_uuid=foreign.uuid, observer_uuid=foreign.uuid,
        use_register=False, phase=EventPhase.COMPLETION,
        **packed_cells(dict(visible_cells_added=[(5, 6)], effective_light_levels_changed={(5, 6): 3})))
    if guard == 'context':
        event.context = {'annotation': ['retained source']}
    elif guard == 'log':
        event.combat_log = CombatLogEntry(entry_type=CombatLogEntryType.ACTION,
            source_uuid=str(foreign.uuid), source_name=foreign.name,
            compact='Witness report', verbose='Witness report', detailed='Witness report',
            perceiver_uuids={str(owner.uuid)},
            identified_entity_observer_uuids={str(foreign.uuid): {str(owner.uuid)}},
            data=EmptyLogData())
    else:
        encoded = encode_event(event)
        encoded['effective_handler_presentations'] = [dict(dispatch_index=0,
            handler_name='Recorded reaction', behavior_id='reaction.recorded',
            provided_by_id='reaction.recorded', origin_root_id=None,
            source_entity_uuid=str(owner.uuid), triggering_event_uuid=str(event.uuid),
            triggering_lineage_uuid=str(event.lineage_uuid), emitted_lineage_uuids=[],
            outcome='modified_event')]
        event = decode_event(encoded)
    event = EventQueue.register(event)
    full = capture_lineages((event,), observer_uuid=owner.uuid)
    admitted = capture_lineages((event,), observer_uuid=owner.uuid,
        omit_foreign_sensory_payloads=True)
    assert admitted == full
    assert not admitted[0].dispositions
    assert decode_event(encode_event(admitted[0].root)).visible_cells_added == mask_from_positions([(5, 6)])
    full_session, admitted_session = SessionProjection(), SessionProjection()
    full_projection, _ = begin_projection(full_session, initial)
    admitted_projection, _ = begin_projection(admitted_session, initial)
    expected = project_lineage(full_session, full_projection, full[0])
    actual = project_lineage(admitted_session, admitted_projection, admitted[0])
    assert actual == expected
    if guard != 'context':
        assert actual is not None
        node, = actual.events
        if guard == 'log':
            assert node.combat_log is not None
            assert node.combat_log.source_uuid == str(foreign.uuid)
        else:
            attribution, = node.content_attributions
            assert attribution.behavior_id == 'reaction.recorded'
            assert attribution.source_entity_uuid == owner.uuid
    archive = RecordedSequence(initialization=initial, lineages=admitted).model_dump_json()
    cold = project_sequence(RecordedSequence.model_validate_json(archive, context=PASSIVE_EVENT_REPLAY))
    assert cold.lineages == (() if actual is None else (actual,))


def test_exact_referenced_foreign_sensory_version_remains_complete(world):
    _, _, (owner, foreign) = world
    root = StepMovementEvent(source_entity_uuid=owner.uuid,
        from_position=(5, 5), to_position=(5, 6))
    source = SensoryUpdateEvent(source_entity_uuid=foreign.uuid, observer_uuid=foreign.uuid,
        phase=EventPhase.COMPLETION, parent_event=root.uuid, cause_event_uuid=root.uuid,
        **packed_cells(dict(visible_cells_added=[(5, 6)], effective_light_levels_changed={(5, 6): 3})))
    SensoryUpdateEvent(source_entity_uuid=owner.uuid, observer_uuid=owner.uuid,
        phase=EventPhase.COMPLETION, parent_event=root.uuid, cause_event_uuid=root.uuid,
        observed_changes=(ObservedChangeRef(source_event_uuid=source.uuid,
            source_index=EventQueue.get_event_index(source.uuid),
            resolution_ref=source.resolution_ref, field='position', owner_uuid=foreign.uuid),))
    root = root.phase_to(EventPhase.COMPLETION)
    full = capture_lineages((root,), observer_uuid=owner.uuid)
    admitted = capture_lineages((root,), observer_uuid=owner.uuid,
        omit_foreign_sensory_payloads=True)
    assert admitted == full
    assert not admitted[0].dispositions
    retained = next(event for event in admitted[0].events if event.uuid == source.uuid)
    assert decode_event(encode_event(retained)).visible_cells_added == mask_from_positions([(5, 6)])


def test_invisible_torch_user_keeps_witness_light_children_without_disclosing_action(world):
    _, built, (owner, witness) = world
    torch = build_torch(owner.uuid)
    assert owner.loot_item(torch)
    owner.add_condition(Invisible(source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid))
    for actor in (owner, witness):
        actor.update_entity_senses(max_distance=8)
    initial = capture_interval(name='unseen torch user', start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=witness.uuid,
        battlefield_id=built.definition.battlefield_id)
    full_session, admitted_session = SessionProjection(), SessionProjection()
    full_projection, public = begin_projection(full_session, initial)
    admitted_projection, _ = begin_projection(admitted_session, initial)
    state = reduce_initialization(public)
    for action in ('Ignite Torch', 'Extinguish Torch'):
        root = execute_use_action(owner, torch.uuid, action)
        assert root is not None and not root.canceled
        arguments = dict(observer_uuid=witness.uuid)
        full = capture_lineages((root,), **arguments)
        admitted = capture_lineages((root,), **arguments, omit_foreign_sensory_payloads=True)
        assert any(row.dispositions for row in admitted)
        packets = []
        for reference, candidate in zip(full, admitted, strict=True):
            assert candidate.observed_sources == reference.observed_sources
            actual = project_lineage(admitted_session, admitted_projection, candidate)
            assert actual == project_lineage(full_session, full_projection, reference)
            if actual is not None:
                packets.append(actual)
                state = reduce_lineage(state, actual)
        assert not any(isinstance(node.fact, ActionFact)
            for packet in packets for node in packet.events)
        assert any(isinstance(node.fact, SensoryFact) and not no_rows(node.fact.effective_light_levels_changed)
            for packet in packets for node in packet.events)


def test_split_seat_application_lineages_equal_independent_full_capture(session):
    session.seats.clear()
    session.seats.update({str(identity): PlayerAudience((identity,), (identity,))
        for identity in session.player_uuids})
    catalog = ui_content_manifest()
    runtimes, _ = initialize_audiences(session, catalog)
    references, _ = initialize_audiences(session, catalog)
    actor = session.game.entities[session.player_uuids[0]]
    start = EventQueue.event_cursor()
    Entity.update_entity_position(actor, (11, 10))
    operation = Operation(start_cursor=start, end_cursor=EventQueue.event_cursor(),
        roots=tuple(event for _, event in EventQueue.iter_events_since(start)
            if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)))
    actual = capture_application_operation(runtimes, operation, catalog)
    context = capture_context(next(iter(references.values())).capture, operation.roots)
    # The reference captures every seat's full payloads, then projects each walk group for all seats of its session.
    captured, inputs = {}, []
    for seat, reference in references.items():
        known = seat_capture_inputs(reference)
        inputs.append(SeatLogInputs(known.connectors, known.content_ids))
        captured[seat] = capture_lineages(operation.roots, observer_uuid=reference.projection.observer_uuid,
            audience=session.seats[seat], context=context)
    shared = next(iter(references.values())).session
    expected = {seat: [] for seat in references}
    for group in range(len(context.groups)):
        for seat, packet in zip(references, project_lineages(shared,
                tuple(reference.projection for reference in references.values()),
                tuple(rows[group] for rows in captured.values()), tuple(inputs)), strict=True):
            if packet is not None:
                expected[seat].append(packet)
    for seat in references:
        assert actual[seat].lineages == tuple(expected[seat])
