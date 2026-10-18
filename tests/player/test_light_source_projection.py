"""Disclosed item light after-values survive the player boundary unchanged."""

from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.actions_functional import execute_use_action
from dnd.content.items.environment_item_builders import build_wall_torch
from dnd.core.base_actions import ActionEvent
from dnd.core.events import EntityCreatedEvent, EventPhase, EventQueue, EventType, SensoryUpdateEvent
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.torches import build_torch
from dnd.player.capture import CompletedLineage, ObjectiveRow, capture_interval, capture_lineages
from dnd.types.actor_facts import HeldItem
from dnd.player.audience import PlayerAudience
from dnd.player.projection import SessionProjection, begin_projection, project_lineage
from dnd.player.event_record import RecordedEvent, encode_event
from dnd.player.reduction import reduce_initialization, reduce_lineage
from dnd.player.recorded import RecordedSequence, project_sequence
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.cells import mask_positions
from dnd.types.cells import cell_in
from dnd.types.world import LightLevel
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from pydantic import TypeAdapter


@pytest.fixture
def world():
    reset_engine_runtime()
    built = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    actors = []
    for name, position in (("Carrier", (5, 5)), ("Witness", (6, 5))):
        actor = Entity.create(uuid4(), name, config=EntityConfig(position=position))
        actor.compose_entity()
        game.deploy_entity(actor, position)
        actors.append(actor)
    try:
        yield built, actors
    finally:
        game.close()
        reset_engine_runtime()


def capture(built, observer):
    return capture_interval(name="source-light projection", start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=observer.uuid,
        battlefield_id=built.definition.battlefield_id)


def with_recorded_holdings(envelope, actor_uuid, item, slot):
    """The recorded startup with the actor holding this item value, worn in `slot`, from its birth on (a value
    boundary: the session's actors fold the recorded births and actor changes)."""
    interval = envelope.world_interval
    equipment = ((slot, item.item_uuid),) if slot is not None else ()
    events = tuple((index, event.model_copy(update={"items": (item,), "equipment": equipment}))
        if isinstance(event, EntityCreatedEvent) and event.entity_uuid == actor_uuid else (index, event)
        for index, event in interval.events)
    changes = {identity: replace(change, held_item=HeldItem(item, slot))
               if change.held_item is not None and change.held_item.item.item_uuid == item.item_uuid else change
               for identity, change in interval.actor_fact_changes.items()}
    return replace(envelope, world_interval=replace(interval, events=events, actor_fact_changes=changes))


def test_fixed_source_overrides_and_native_activation_survive_reduction(world):
    built, (owner, _) = world
    torch = build_wall_torch()
    torch.very_bright_radius_feet = 7
    torch.bright_radius_feet = 17
    torch.dim_radius_feet = 23
    torch.place_on_grid((5, 6))
    owner.update_entity_senses(max_distance=8)
    session = SessionProjection()
    projection, initial = begin_projection(session, capture(built, owner))
    state = reduce_initialization(initial)
    assert state.objects[torch.uuid].item.is_lit is False
    for lit in (True, False, True):
        action = next(row for row in owner.get_available_actions().all_actions
            if row.source_item_uuid == torch.uuid)
        root = execute_use_action(owner, torch.uuid, action.template_name)
        assert root is not None and not root.canceled
        for native in capture_lineages((root,), observer_uuid=owner.uuid,
                known_actor_uuids=frozenset(state.actors)):
            assert not native.dispositions
            packet = project_lineage(session, projection, native)
            if packet is not None:
                state = reduce_lineage(state, packet)
        item = state.objects[torch.uuid].item
        assert (item.is_lit, item.very_bright_radius_feet,
            item.bright_radius_feet, item.dim_radius_feet) == (lit, 7, 17, 23)


def test_carried_source_keeps_inventory_private_to_controller(world):
    built, (owner, witness) = world
    torch = build_torch(owner.uuid)
    torch.bright_radius_feet = 35
    torch.dim_radius_feet = 15
    assert owner.loot_item(torch)
    views = {}
    for observer in (owner, witness):
        observer.update_entity_senses(max_distance=8)
        session = SessionProjection()
        projection, initial = begin_projection(session, capture(built, observer))
        views[observer.uuid] = session, projection, reduce_initialization(initial)
    for lit in (True, False, True):
        root = execute_use_action(owner, torch.uuid, "Ignite Torch" if lit else "Extinguish Torch")
        assert root is not None and not root.canceled
        for observer in (owner, witness):
            session, projection, state = views[observer.uuid]
            for native in capture_lineages((root,), observer_uuid=observer.uuid,
                    known_actor_uuids=frozenset(state.actors)):
                assert not native.dispositions
                codec = TypeAdapter(tuple[RecordedEvent, ...])
                restored = codec.validate_json(codec.dump_json(native.events))
                assert tuple(type(row) for row in restored) == tuple(type(row) for row in native.events)
                packet = project_lineage(session, projection, native)
                if packet is not None:
                    state = reduce_lineage(state, packet)
            views[observer.uuid] = session, projection, state
            actor = state.actors[owner.uuid]
            assert not any(row.item_uuid == torch.uuid for row in actor.visual_loadout.layers)
            if observer is owner:
                assert torch.uuid in actor.controlled_items
                item = state.items[torch.uuid]
                assert item.state is not None
                assert (item.state.is_lit, item.look.bright_radius_feet, item.look.dim_radius_feet) == (lit, 35, 15)
            else:
                assert actor.controlled_items is None
                assert torch.uuid not in state.objects
                assert torch.uuid not in state.items


@pytest.mark.parametrize("lit", (False, True))
def test_disclosed_equipment_source_after_values_preserve_activation(world, lit):
    # Value-boundary test: portable torches are intentionally not equippable.
    # Supply an admitted equipment record to test the general VisualItem DTO;
    # this does not claim that the native torch supports an equip command.
    built, (owner, witness) = world
    torch = build_torch(owner.uuid)
    assert owner.loot_item(torch)
    witness.update_entity_senses(max_distance=8)
    captured = capture(built, witness)
    item = torch.to_item_presentation_state().model_copy(update={
        "is_lit": lit, "very_bright_radius_feet": 6, "bright_radius_feet": 19, "dim_radius_feet": 31})
    _, initial = begin_projection(SessionProjection(), with_recorded_holdings(captured, owner.uuid, item,
        "weapon_melee_off"))
    state = reduce_initialization(initial)
    actor = state.actors[owner.uuid]
    source, = actor.visual_loadout.layers
    assert actor.controlled_items is None
    record = state.items[source.item_uuid]
    # A foreign equipped item discloses its look only.
    assert record.profile is None and record.state is None
    assert (source.is_lit, record.look.very_bright_radius_feet,
        record.look.bright_radius_feet, record.look.dim_radius_feet) == (lit, 6, 19, 31)


@pytest.mark.parametrize('equipped', (False, True))
@pytest.mark.parametrize('foreign_handler', (False, True))
def test_recorded_content_attribution_uses_foreign_equipment_grants(world, equipped, foreign_handler):
    # Recorded-value boundary: as above, this supplies equipment facts rather
    # than claiming a portable torch supports a native equip command.
    built, (owner, witness) = world
    torch = build_torch(owner.uuid)
    assert owner.loot_item(torch)
    witness.update_entity_senses(max_distance=8)
    initial = capture(built, witness)
    item = torch.to_item_presentation_state()
    initial = with_recorded_holdings(initial, owner.uuid, item, "weapon_melee_off" if equipped else None)
    source = witness.uuid if foreign_handler else owner.uuid
    event = ActionEvent.model_validate(dict(name='Use recorded equipment', use_register=False,
        source_entity_uuid=source, phase=EventPhase.COMPLETION,
        behavior_id='action.recorded_use', provided_by_id=item.item_id, origin_root_id=item.item_id,
        source_item_uuid=None if foreign_handler else item.item_uuid,
        source_item_presentation=None if foreign_handler else item,
        identified_entity_observer_uuids={str(owner.uuid): {str(witness.uuid)},
            str(witness.uuid): {str(witness.uuid)}}),
        context=PASSIVE_EVENT_REPLAY)
    payload = encode_event(event)
    if foreign_handler:
        payload['effective_handler_presentations'] = [dict(dispatch_index=0,
            handler_name='Recorded equipment reaction', behavior_id='reaction.recorded_equipment',
            provided_by_id=item.item_id, origin_root_id=item.item_id,
            source_entity_uuid=str(owner.uuid), triggering_event_uuid=str(event.uuid),
            triggering_lineage_uuid=str(event.lineage_uuid), emitted_lineage_uuids=[],
            outcome='modified_event')]
    event = TypeAdapter(RecordedEvent).validate_python(payload, context=PASSIVE_EVENT_REPLAY)
    index = initial.end_cursor
    row = ObjectiveRow(source_index=index, event_uuid=event.uuid, lineage_uuid=event.lineage_uuid,
        parent_event=None, parent_lineage=None, event_type=event.event_type.value,
        event_class='ActionEvent', phase=event.phase.value, source_uuid=source, source_name=None,
        target_uuid=None, target_name=None, turn_execution_id=None, status=None, outcome=None,
        canceled=False, modified=False)
    lineage = CompletedLineage(generation=initial.generation, observer_uuid=witness.uuid,
        root=event, events=(event,), objective_rows=(row,), start_cursor=index, end_cursor=index+1)
    session = SessionProjection()
    projection, _ = begin_projection(session, initial)
    packet = project_lineage(session, projection, lineage)
    assert packet is not None
    assert packet.root is not None
    node = packet.events[packet.root]
    role = 'effective_handler' if foreign_handler else 'behavior'
    attribution, = (value for value in node.content_attributions if value.role == role)
    expected_provider = item.item_id if equipped else None
    assert (attribution.provided_by_id, attribution.origin_root_id) == (expected_provider, expected_provider)
    if not foreign_handler:
        assert [value.behavior_id for value in node.content_attributions if value.role == 'source_item'] == (
            [item.item_id] if equipped else [])
    saved = RecordedSequence(initialization=initial, lineages=(lineage,)).model_dump_json()
    restored = RecordedSequence.model_validate_json(saved, context=PASSIVE_EVENT_REPLAY)
    assert project_sequence(restored).lineages == (packet,)


def test_shared_light_tile_after_values_precede_parent_completion_and_survive_cold_replay(world):
    built, (first, second) = world
    audience = PlayerAudience((first.uuid, second.uuid), (first.uuid, second.uuid))
    for actor in (first, second):
        actor.update_entity_senses(max_distance=8)
    initial = capture_interval(name="shared light", start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=first.uuid, audience=audience,
        battlefield_id=built.definition.battlefield_id)
    session = SessionProjection()
    projection, public = begin_projection(session, initial)
    state = reduce_initialization(public)
    position, neighbor = (5, 6), (5, 7)
    unchanged = state.tiles[neighbor]
    lineages, packets = [], []

    for light in (LightLevel.DIM_LIGHT, LightLevel.DARKNESS, LightLevel.BRIGHT_LIGHT):
        cursor = EventQueue.event_cursor()
        assert get_map().set_tile_base_light(position, light)
        roots = tuple(event for _, event in EventQueue.iter_events_since(cursor)
            if event.parent_lineage is None and event.phase is EventPhase.COMPLETION)
        captured = capture_lineages(roots, observer_uuid=first.uuid, audience=audience,
            known_actor_uuids=frozenset(state.actors))
        children = [event for row in captured for event in row.events
            if isinstance(event, SensoryUpdateEvent)]
        assert {event.observer_uuid for event in children} == {first.uuid, second.uuid}
        for native in captured:
            assert not native.dispositions
            packet = project_lineage(session, projection, native)
            assert packet is not None
            packets.append(packet)
            lineages.append(native)
            indexes = {row.event_uuid: row.source_index for row in native.objective_rows}
            light_completion = next(event for event in native.events
                if event.event_type is EventType.SPATIAL_LIGHT_CHANGED
                and event.phase is EventPhase.COMPLETION)
            for update in packet.world_updates:
                assert set(mask_positions(update.entered)) <= {position}
                assert {row.position for row in update.tile_changes} <= {position}
                assert not update.objects and not update.objects_removed
            # The light's after-value reaches the seat at the first observer's sight of it, before the light's
            # completion (which carries the same after-value again).
            earliest = min(cursor for cursor, public in projection.public_cursors.items()
                if public == packet.world_updates[0].occurrence)
            assert earliest < indexes[light_completion.uuid]
            state = reduce_lineage(state, packet)
        # The first observer's source after-value is projected while the other
        # observer still grants this cell. Darkness is remembered at that prefix
        # before the second child's visibility removal closes the shared grant.
        assert state.tiles[position].resolved_light is light
        assert cell_in(state.senses.visible, position) is (light is not LightLevel.DARKNESS)
        assert state.tiles[neighbor] == unchanged

    saved = RecordedSequence(initialization=initial, lineages=tuple(lineages)).model_dump_json()
    cold = project_sequence(RecordedSequence.model_validate_json(saved, context=PASSIVE_EVENT_REPLAY))
    assert cold.lineages == tuple(packets)
    replayed = reduce_initialization(cold.initialization)
    for packet in cold.lineages:
        replayed = reduce_lineage(replayed, packet)
    assert replayed == state
