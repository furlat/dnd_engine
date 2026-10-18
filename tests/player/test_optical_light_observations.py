"""Authoritative optical observations cross live/cold player boundaries privately."""

from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from dnd.actions_functional import execute_use_action
from dnd.conditions import Invisible
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.base_tiles import tile_light_contributions
from dnd.core.events import EventPhase, EventQueue, EventType, SensoryUpdateEvent
from dnd.core.gridmap import get_map
from dnd.core.view import cell_visible
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.torches import build_torch
from dnd.items.environment import DirectionalWall
from dnd.core.sensory_fold import reduce_senses_snapshot
from dnd.player.audience import (AudienceComposition, AudiencePerception, PlayerAudience, apply_settlement,
    composed_view)
from dnd.player.capture import capture_interval, capture_lineages
from dnd.player.projection import SessionProjection, begin_projection, project_lineage
from dnd.player.reduction import reduce_initialization, reduce_lineage
from dnd.player.recorded import RecordedSequence, project_sequence
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.types.senses import PerceivedLightSource, SenseMode, SensesType
from dnd.types.world import CardinalDirection, LightLevel
from dnd.core.cells import mask_positions
from dnd.types.cells import value_at


@pytest.fixture
def room():
    reset_engine_runtime()
    built = build_battlefield('battlefield.open_floor_dark')
    game = Game()
    actors = []
    for name, position in (('Carrier', (5, 5)), ('Witness', (6, 5))):
        actor = Entity.create(uuid4(), name, config=EntityConfig(position=position))
        actor.senses.sense_modes = [SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)]
        actor.compose_entity()
        game.deploy_entity(actor, position)
        actors.append(actor)
    try:
        yield built, actors, game
    finally:
        game.close()
        reset_engine_runtime()


def start(built, witness, max_distance=8):
    witness.update_entity_senses(max_distance=max_distance)
    initial = capture_interval(name='optical observations', start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=witness.uuid,
        battlefield_id=built.definition.battlefield_id)
    session = SessionProjection()
    projection, public = begin_projection(session, initial)
    return initial, (session, projection), reduce_initialization(public)


def advance(seat, state, roots, witness):
    session, projection = seat
    natives, packets = [], []
    for native in capture_lineages(roots, observer_uuid=witness.uuid,
            known_actor_uuids=frozenset(state.actors)):
        packet = project_lineage(session, projection, native)
        natives.append(native)
        if packet is not None:
            packets.append(packet)
            state = reduce_lineage(state, packet)
    return state, natives, packets


def roots_since(cursor):
    return tuple(event for _, event in EventQueue.iter_events_since(cursor)
        if event.parent_lineage is None and event.phase is EventPhase.COMPLETION)


def assert_objective(state):
    for position in mask_positions(state.senses.visible):
        assert state.tiles[position].resolved_light == get_map().get_tile(*position).resolved_light_level


def test_live_carried_torch_private_identity_and_current_tiles_survive_cold_replay(room):
    built, (owner, witness), game = room
    torch = build_torch(owner.uuid)
    assert owner.loot_item(torch)
    initial, seat, state = start(built, witness)
    assert not state.light_sources
    assert_objective(state)
    assert state.tiles[(5, 5)].resolved_light is LightLevel.DARKNESS
    # Darkvision's effective value is explicitly NOT the objective tile value.
    assert value_at(state.senses.effective_light_levels, (5, 5)) == LightLevel.DIM_LIGHT
    natives, packets, retained = [], [], []
    for lit in (True, False, True):
        before = state
        root = execute_use_action(owner, torch.uuid, 'Ignite Torch' if lit else 'Extinguish Torch')
        assert root is not None and not root.canceled
        state, rows, projected = advance(seat, state, (root,), witness)
        natives.extend(rows); packets.extend(projected)
        retained.append((before, replace(before, tiles=dict(before.tiles))))
        assert_objective(state)
        assert state.actors[owner.uuid].controlled_items is None
        assert not any(row.item_uuid == torch.uuid for row in state.actors[owner.uuid].visual_loadout.layers)
        assert torch.uuid not in state.objects
        assert bool(state.light_sources) is lit
        if lit:
            identity, source = next(iter(state.light_sources.items()))
            assert identity == source.source_uuid and identity not in (owner.uuid, torch.uuid)
            assert source.anchor_entity_uuid == owner.uuid and source.anchor_item_uuid is None
            assert source.appearance == 'torch' and source.position == owner.position
            assert source.actor_anchored
            assert (source.very_bright_radius_feet, source.bright_radius_feet, source.dim_radius_feet) == (
                torch.very_bright_radius_feet, torch.bright_radius_feet, torch.dim_radius_feet)
        assert all(before == frozen for before, frozen in retained)
    saved = RecordedSequence(initialization=initial, lineages=tuple(natives)).model_dump_json()
    # Remove all native owners before reprojecting; no live light query is legal here.
    game.close()
    reset_engine_runtime()
    cold = project_sequence(RecordedSequence.model_validate_json(saved, context=PASSIVE_EVENT_REPLAY))
    assert cold.lineages == tuple(packets)
    final = reduce_initialization(cold.initialization)
    for packet in cold.lineages:
        final = reduce_lineage(final, packet)
    assert final == state


def test_silent_initial_ignition_exposes_current_emitter_and_replays_without_live_owners(room):
    built, (owner, witness), game = room
    torch = build_torch(owner.uuid)
    assert owner.loot_item(torch)
    # Native setup semantics: source registration is deliberately silent before
    # entity creation commitment. The original world snapshot stays dark.
    get_map().add_light_source(owner.position, bright_radius_feet=20, dim_radius_feet=20,
        anchor_uuid=owner.uuid, appearance='torch', publish_event=False)
    initial, _, state = start(built, witness)
    source, = state.light_sources.values()
    assert source.anchor_entity_uuid == owner.uuid
    assert source.position == owner.position
    assert get_map().get_tile(*owner.position).resolved_light_level is LightLevel.BRIGHT_LIGHT
    game.close()
    reset_engine_runtime()
    cold = project_sequence(RecordedSequence.model_validate_json(
        RecordedSequence(initialization=initial, lineages=()).model_dump_json(), context=PASSIVE_EVENT_REPLAY))
    assert reduce_initialization(cold.initialization) == state


def test_unseen_offscreen_emitter_exposes_optics_without_actor_or_inventory_identity(room):
    built, (owner, witness), game = room
    torch = build_torch(owner.uuid)
    assert owner.loot_item(torch)
    owner.add_condition(Invisible(source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid))
    initial, seat, state = start(built, witness)
    assert owner.uuid not in state.senses.entities
    root = execute_use_action(owner, torch.uuid, 'Ignite Torch')
    assert root is not None and not root.canceled
    state, _, _ = advance(seat, state, (root,), witness)
    source, = state.light_sources.values()
    assert source.position == owner.position
    assert source.anchor_entity_uuid is None and source.anchor_item_uuid is None
    assert source.actor_anchored
    assert source.source_uuid not in (owner.uuid, torch.uuid)
    assert_objective(state)
    # Offscreen origin is allowed while its current footprint is visible.
    witness.senses.sense_modes = []
    witness.update_entity_senses(max_distance=1)
    _, seat, state = start(built, witness)
    witness.update_entity_senses(max_distance=1)
    cursor = EventQueue.event_cursor()
    Entity.update_entity_position(owner, (3, 5))
    state, _, _ = advance(seat, state, roots_since(cursor), witness)
    source, = state.light_sources.values()
    assert source.position == (3, 5) and not cell_visible(witness.senses.cells, source.position)
    assert source.anchor_entity_uuid is None
    assert source.anchor_item_uuid is None
    assert any(source.source_uuid in tile_light_contributions(get_map().get_tile(*position))[0]
        for position in mask_positions(state.senses.visible))


def test_observer_movement_keeps_stationary_descriptor_until_no_contribution_is_visible(room):
    built, (_, witness), _ = room
    source_id = get_map().add_light_source((5, 5), 5, 5)
    witness.senses.sense_modes = []
    _, seat, state = start(built, witness, max_distance=1)
    source = state.light_sources[source_id]
    assert source.position == (5, 5)
    for position in ((6, 6), (7, 5)):
        previous_visible = state.senses.visible
        cursor = EventQueue.event_cursor()
        Entity.update_entity_position(witness, position)
        updates = [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == witness.uuid]
        assert updates
        assert all(not event.light_sources_changed and not event.light_sources_removed
            for event in updates)
        state, _, _ = advance(seat, state, roots_since(cursor), witness)
        assert state.senses.visible != previous_visible
        assert state.light_sources == {source_id: source}
    cursor = EventQueue.event_cursor()
    Entity.update_entity_position(witness, (10, 5))
    state, _, _ = advance(seat, state, roots_since(cursor), witness)
    # The client keeps no removal: a source leaving perception is sent by key.
    assert not state.light_sources
    assert all(source_id not in tile_light_contributions(get_map().get_tile(*position))[0]
        for position in mask_positions(state.senses.visible))


def test_capture_keeps_the_source_descriptor(room):
    built, (_, witness), _ = room
    identity = uuid4()
    source = PerceivedLightSource(source_uuid=identity, revision=1, position=(5, 5),
        base_height_steps=0, very_bright_radius_feet=0, bright_radius_feet=10,
        dim_radius_feet=10)
    cursor = EventQueue.event_cursor()
    event = SensoryUpdateEvent(source_entity_uuid=witness.uuid, observer_uuid=witness.uuid,
        light_sources_changed={identity: source}, phase=EventPhase.COMPLETION)
    lineage, = capture_lineages((event,), observer_uuid=witness.uuid)
    interval = capture_interval(name='detached optical descriptor', start_cursor=cursor,
        end_cursor=EventQueue.event_cursor(), observer_uuid=witness.uuid,
        battlefield_id=built.definition.battlefield_id)
    retained = [lineage.root, next(row for _, row in interval.admitted if row.uuid == event.uuid)]
    expected = source.model_copy(deep=True)
    for captured in retained:
        assert captured.light_sources_changed == {identity: expected}


def test_constant_max_source_movement_extinction_and_rediscovery_are_not_light_rule_events(room):
    built, (owner, witness), game = room
    grid = get_map()
    for position in grid.get_all_tiles():
        grid.set_tile_base_light(position, LightLevel.VERY_BRIGHT)
    torch = build_torch(owner.uuid)
    assert owner.loot_item(torch)
    _, seat, state = start(built, witness)
    sources = []
    for command in ('Ignite Torch', 'Extinguish Torch'):
        cursor = EventQueue.event_cursor()
        root = execute_use_action(owner, torch.uuid, command)
        assert root is not None and not root.canceled
        events = tuple(event for _, event in EventQueue.iter_events_since(cursor))
        assert not any(event.event_type is EventType.SPATIAL_LIGHT_CHANGED for event in events)
        assert any(event.event_type is EventType.SPATIAL_LIGHT_SOURCES_CHANGED for event in events)
        state, _, _ = advance(seat, state, (root,), witness)
        assert all(grid.get_tile(*position).resolved_light_level is LightLevel.VERY_BRIGHT
            for position in mask_positions(state.senses.visible))
        sources.append(dict(state.light_sources))
    assert sources[0] and not sources[1]
    # Two equal sources: removing one retains the real other contributor.
    first = grid.add_light_source((5, 5), 10, 10)
    second = grid.add_light_source((5, 5), 10, 10)
    witness.update_entity_senses(max_distance=2)
    assert {first, second} <= witness.senses.light_sources.keys()
    cursor = EventQueue.event_cursor()
    grid.move_light_source(first, (9, 5))
    updates = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == witness.uuid]
    assert updates and any(first in row.light_sources_changed for row in updates)
    assert witness.senses.light_sources[first].position == (9, 5)
    moved_revision = witness.senses.light_sources[first].revision
    grid.remove_light_source(first)
    assert first not in witness.senses.light_sources and second in witness.senses.light_sources
    assert witness.senses.light_source_removals[first] > moved_revision


def test_shared_revision_union_never_joins_old_position_or_resurrects_removed_source():
    first, second, identity = UUID(int=1), UUID(int=2), UUID(int=3)
    audience = PlayerAudience((first, second), (first, second))
    def row(revision, position, anchor=None):
        return PerceivedLightSource(source_uuid=identity, revision=revision, position=position,
            base_height_steps=0, bright_radius_feet=10, dim_radius_feet=10,
            very_bright_radius_feet=0, anchor_entity_uuid=anchor)
    old = row(1, (0, 0))
    other = row(1, (0, 0), anchor=second)
    moved = row(2, (2, 0))
    events = []
    for observer, source in ((first, old), (second, other)):
        events.append(SensoryUpdateEvent.model_validate(dict(observer_uuid=observer,
            source_entity_uuid=observer, initial=True, observer_position=(0,0),
            observer_position_changed=True, passive_perception_changed=True, passive_perception=10,
            visual_access_changed=True, visual_access=1, sense_modes_changed=True, sense_modes=[],
            light_sources_changed={identity: source}, phase=EventPhase.COMPLETION, use_register=False),
            context=PASSIVE_EVENT_REPLAY))
    events.extend(SensoryUpdateEvent.model_validate(dict(observer_uuid=first, source_entity_uuid=first,
        phase=EventPhase.COMPLETION, use_register=False, **values), context=PASSIVE_EVENT_REPLAY)
        for values in ({'light_sources_changed': {identity:moved}},
            {'light_sources_removed':{identity:3}}))
    members = {}
    current = AudienceComposition()
    for index, event in enumerate(events):
        members[event.observer_uuid] = reduce_senses_snapshot(event.observer_uuid, members.get(event.observer_uuid), event)
        apply_settlement(current, audience, first, (event,))
        expected = composed_view(AudiencePerception(dict(members)), first)
        assert current.view == expected
        if index == 1:
            # Rows of one revision join: the first member's, with the anchor another discloses.
            assert expected.light_sources[identity] == old.model_copy(update={'anchor_entity_uuid': second})
        elif index == 2:
            assert expected.light_sources[identity] == moved
        elif index == 3:
            assert identity not in expected.light_sources
            assert expected.light_source_removals[identity] == 3


def test_compact_descriptors_preserve_native_occlusion_caps_and_ambient_light(room):
    built, (owner, witness), _ = room
    grid = get_map()
    source_id = grid.add_light_source((5, 5), 15, 15)
    _, seat, state = start(built, witness)
    target = (6, 5)
    source = state.light_sources[source_id]
    native_revision = witness.senses.light_sources[source_id].revision
    assert tile_light_contributions(grid.get_tile(*target))[0][source_id] is LightLevel.BRIGHT_LIGHT
    cap_id = uuid4()
    cursor = EventQueue.event_cursor()
    grid.apply_light_modifier(cap_id, {target}, LightLevel.DIM_LIGHT, cap=True)
    state, _, _ = advance(seat, state, roots_since(cursor), witness)
    assert state.tiles[target].resolved_light is LightLevel.DIM_LIGHT
    illuminations, caps = tile_light_contributions(grid.get_tile(*target))
    assert illuminations[source_id] is LightLevel.BRIGHT_LIGHT
    assert caps[cap_id] is LightLevel.DIM_LIGHT
    # A baseline change hidden under the cap still changes native physics.
    cursor = EventQueue.event_cursor()
    grid.set_tile_base_light(target, LightLevel.BRIGHT_LIGHT)
    state, _, _ = advance(seat, state, roots_since(cursor), witness)
    assert grid.get_tile(*target).default_light is LightLevel.BRIGHT_LIGHT
    assert grid.get_tile(*target).resolved_light_level is LightLevel.DIM_LIGHT
    assert not any(event.event_type is EventType.SPATIAL_LIGHT_CHANGED
        for _, event in EventQueue.iter_events_since(cursor))
    cursor = EventQueue.event_cursor()
    grid.remove_light_modifier(cap_id, {target})
    state, _, _ = advance(seat, state, roots_since(cursor), witness)
    assert state.tiles[target].resolved_light is LightLevel.BRIGHT_LIGHT
    wall = DirectionalWall(source_entity_uuid=witness.uuid, item_id='test.optical.obstruction')
    cursor = EventQueue.event_cursor()
    wall.place_on_grid((5, 5), boundary_direction=CardinalDirection.EAST)
    state, _, _ = advance(seat, state, roots_since(cursor), witness)
    # The wall changes the source's native revision, not what the seat is shown of it: nothing is sent.
    assert witness.senses.light_sources[source_id].revision > native_revision
    assert state.light_sources[source_id] == source
    assert source_id not in tile_light_contributions(grid.get_tile(*target))[0]
    assert state.tiles[target].resolved_light is LightLevel.BRIGHT_LIGHT  # actual ambient, not leaking emitter
    cursor = EventQueue.event_cursor()
    assert grid.remove_object(wall.uuid)
    state, _, _ = advance(seat, state, roots_since(cursor), witness)
    assert tile_light_contributions(grid.get_tile(*target))[0][source_id] is LightLevel.BRIGHT_LIGHT


def test_legacy_sensory_records_without_optical_fields_remain_replayable():
    observer = UUID(int=7)
    value = dict(observer_uuid=observer, source_entity_uuid=observer, initial=True,
        observer_position=(0,0), observer_position_changed=True, passive_perception_changed=True,
        passive_perception=10, visual_access_changed=True, visual_access=1,
        sense_modes_changed=True, sense_modes=[], phase=EventPhase.COMPLETION, use_register=False)
    event = SensoryUpdateEvent.model_validate(value, context=PASSIVE_EVENT_REPLAY)
    view = composed_view(AudiencePerception({observer: reduce_senses_snapshot(observer, None, event)}), observer)
    assert view.light_sources == {} and view.light_source_removals == {}
