"""Event-associated tile fields preserve every admitted intermediate state (player schema 16).

A tile the seat perceives before and after an event travels as that event's keyed scalars, light, conditions and
residues; a tile entering perception (a cell coming into view, a tile written whole) travels whole, its surface and
name once per tile uuid.
"""

from copy import deepcopy
from dataclasses import replace
import json
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventPhase, EventType, SpatialChangeEvent, SpatialChangeType
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.player.capture import CompletedLineage
from dnd.player.facts import PlayerLineage, PlayerSequence, PlayerUpdate, TileFieldUpdate, TileStatic
from dnd.player.projection import SessionProjection, begin_projection, project_lineage
from dnd.player.reduction import (decode_player_sequence, encode_player_sequence, reduce_initialization,
    reduce_lineage, reduce_operation, stage_lineage)
from dnd.types.materials import Material, TileSurface
from dnd.types.residues import TileResidueState
from dnd.types.world import LightLevel
from dnd.core.cells import mask_from_positions, mask_positions, values_from_items
from dnd.player.world_columns import pack_tile_columns, unpack_tile_columns
from dnd.types.cells import EMPTY_CELLS
from tests.player.test_projection_local_world import initial, objective, sensory


def light_change(observer, light):
    return SpatialChangeEvent.model_validate(dict(source_entity_uuid=observer,
        use_register=False, phase=EventPhase.COMPLETION, event_type=EventType.SPATIAL_LIGHT_CHANGED,
        change_type=SpatialChangeType.LIGHT_CHANGED, position=(1, 0),
        light_level_map={"1,0": light.value}), context=PASSIVE_EVENT_REPLAY)


def project_event(session, projection, event, index, *, disclosed=True):
    native = CompletedLineage(generation=projection.remembered.generation,
        observer_uuid=projection.remembered.observer_uuid, root=event, events=(event,),
        objective_rows=(objective(index, event),), start_cursor=index, end_cursor=index+1)
    packet = project_lineage(session, projection, native)
    assert (packet is not None) is disclosed
    return packet


def test_known_tile_light_updates_carry_only_changed_fields_at_each_event():
    start = initial((), ((1, 0), (2, 0)), {})
    session = SessionProjection()
    projection, public = begin_projection(session, start)
    before = reduce_initialization(public)
    state = before
    retained = []
    packets = []
    for index, light in enumerate((LightLevel.DIM_LIGHT, LightLevel.DARKNESS,
                                   LightLevel.BRIGHT_LIGHT), start.end_cursor):
        event = light_change(start.observer_uuid, light)
        packet = project_event(session, projection, event, index)
        packets.append(packet)
        update, = packet.world_updates
        assert update.occurrence == projection.public_cursors[index]
        assert update.entered == EMPTY_CELLS and update.tile_columns is None and update.tile_changes == ()
        # A changed resolved light travels as the update's packed values.
        assert update.resolved_light == values_from_items({(1, 0): light.value})
        state = reduce_lineage(state, packet)
        retained.append(state)
        assert state.tiles[(1, 0)].resolved_light is light
        assert state.tiles[(2, 0)] == before.tiles[(2, 0)]
    assert [row.tiles[(1, 0)].resolved_light for row in retained] == [
        LightLevel.DIM_LIGHT, LightLevel.DARKNESS, LightLevel.BRIGHT_LIGHT]
    assert before.tiles[(1, 0)].resolved_light is LightLevel.BRIGHT_LIGHT
    saved = encode_player_sequence(PlayerSequence(initialization=public, lineages=tuple(packets)))
    replay, decoded = decode_player_sequence(saved)
    for packet, expected in zip(decoded, retained):
        replay = reduce_lineage(replay, packet)
        assert replay == expected


def tile_change(observer, tile):
    return SpatialChangeEvent.model_validate(dict(source_entity_uuid=observer,
        use_register=False, phase=EventPhase.COMPLETION, event_type=EventType.SPATIAL_TILE_CHANGED,
        change_type=SpatialChangeType.TILE_CHANGED, position=tile.position,
        tile_state=tile, tile_present=True), context=PASSIVE_EVENT_REPLAY)


def test_a_tile_written_whole_reenters_with_its_conditions_residues_and_clears():
    start = initial((), ((1, 0),), {})
    session = SessionProjection()
    projection, public = begin_projection(session, start)
    before = reduce_initialization(public)
    original = before.tiles[(1, 0)]
    changes = dict(blocks_optics=True, blocks_propagation=True, walking_cost=2, flying_cost=2,
        swimming_cost=2, burrowing_cost=2, elevation_steps=2,
        surface_kind=ElevationSurfaceKind.RAMP, slope_axis=SlopeAxis.EAST_WEST,
        default_light=LightLevel.DIM_LIGHT, resolved_light=LightLevel.DIM_LIGHT,
        condition_names=('Ash',), residues=(TileResidueState(condition_uuid=uuid4(),
            residue_id='test.ash', description='Ash'),))
    enriched = original.model_copy(update=changes)
    packet = project_event(session, projection, tile_change(start.observer_uuid, enriched), start.end_cursor)
    update, = packet.world_updates
    # The cell re-enters: its scalars travel as columns, its residue whole, its static row is already held.
    assert mask_positions(update.entered) == [(1, 0)] and update.tile_statics == () and update.tile_changes == ()
    assert update.tile_columns is not None
    assert unpack_tile_columns(update.tile_columns, {(1, 0): TileStatic(position=(1, 0), tile_uuid=original.tile_uuid,
        surface=original.surface, name=original.name)})[(1, 0)] == enriched.model_copy(update=dict(
            condition_names=(), residues=()))
    assert update.tile_conditions == () and [row.residue_id for row in update.residues] == ['test.ash']
    assert [row.name for row in update.residue_materials] == ['Ash']
    changed = reduce_lineage(before, packet)
    assert changed.tiles[(1, 0)] == enriched
    clears = dict(blocks_optics=False, blocks_propagation=False, walking_cost=0,
        flying_cost=0, swimming_cost=0, burrowing_cost=0, elevation_steps=0,
        surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None,
        default_light=LightLevel(0), resolved_light=LightLevel(0), condition_names=(), residues=())
    cleared = enriched.model_copy(update=clears)
    packet = project_event(session, projection, tile_change(start.observer_uuid, cleared), start.end_cursor+1)
    wire = TypeAdapter(PlayerLineage).dump_json(packet)
    parsed = TypeAdapter(PlayerLineage).validate_json(wire)
    raw = json.loads(wire)['world_updates'][0]
    assert 'residues' not in raw and 'tile_conditions' not in raw and 'tile_statics' not in raw
    after = reduce_lineage(changed, parsed)
    assert after.tiles[(1, 0)] == cleared
    assert changed.tiles[(1, 0)] == enriched and before.tiles[(1, 0)] == original
    # A replaced tile has a new uuid: its static row travels once.
    replacement = cleared.model_copy(update={'tile_uuid': uuid4(), 'name': 'Ramp',
        'surface': TileSurface(base_material=Material.WOOD)})
    packet = project_event(session, projection, tile_change(start.observer_uuid, replacement), start.end_cursor+2)
    assert packet is not None
    assert [row.tile_uuid for row in packet.world_updates[0].tile_statics] == [replacement.tile_uuid]
    assert reduce_lineage(after, packet).tiles[(1, 0)] == replacement
    renamed = replacement.model_copy(update={'name': 'Renamed in place'})
    with pytest.raises(ValueError, match='never change for its uuid'):
        project_event(session, projection, tile_change(start.observer_uuid, renamed), start.end_cursor+3)


def test_hidden_tile_changes_remain_private_until_discovery_and_identity_replacement_is_full():
    start = initial((), ((1, 0),), {})
    session = SessionProjection()
    projection, public = begin_projection(session, start)
    state = reduce_initialization(public)
    hide = project_event(session, projection, sensory(start.observer_uuid, visible_cells_removed=[(1, 0)]), 2)
    state = reduce_lineage(state, hide)
    assert project_event(session, projection, light_change(start.observer_uuid, LightLevel.DIM_LIGHT),
                         3, disclosed=False) is None
    assert state.tiles[(1, 0)].resolved_light is LightLevel.BRIGHT_LIGHT
    reveal = project_event(session, projection, sensory(start.observer_uuid, visible_cells_added=[(1, 0), (2, 0)]), 4)
    update, = reveal.world_updates
    # Both cells enter whole; only (2, 0)'s static row is new to the seat.
    assert mask_positions(update.entered) == [(1, 0), (2, 0)]
    assert [row.position for row in update.tile_statics] == [(2, 0)]
    # The hidden light change reaches the seat when the tile comes back into view, in its columns.
    assert update.tile_columns is not None and update.tile_columns.resolved_light[0] == LightLevel.DIM_LIGHT.value
    assert update.resolved_light == values_from_items({})
    state = reduce_lineage(state, reveal)
    assert state.tiles[(1, 0)].resolved_light is LightLevel.DIM_LIGHT
    old = state.tiles[(1, 0)]
    replacement = old.model_copy(update={'tile_uuid': uuid4(), 'name': 'Replacement'})
    replaced = project_event(session, projection, tile_change(start.observer_uuid, replacement), 5)
    assert [row.tile_uuid for row in replaced.world_updates[0].tile_statics] == [replacement.tile_uuid]
    assert mask_positions(replaced.world_updates[0].entered) == [(1, 0)]
    assert not replaced.world_updates[0].tile_changes
    after = reduce_lineage(state, replaced)
    assert after.tiles[(1, 0)] == replacement and state.tiles[(1, 0)] == old


def test_client_fold_checks_tile_bases_in_event_order_without_staging_future_values():
    start = initial((), ((1, 0),), {})
    session = SessionProjection()
    projection, public = begin_projection(session, start)
    before = reduce_initialization(public)
    packet = project_event(session, projection, light_change(start.observer_uuid, LightLevel.DIM_LIGHT), 2)
    assert stage_lineage(before, packet).tiles[(1, 0)] == before.tiles[(1, 0)]
    update = PlayerUpdate(audience=before.viewing_audience, lineages=(packet,), hud=None,
                          combat_log_appends=(), content_additions=())
    missing = TileFieldUpdate(position=(99, 99), changes={'walking_cost': 3})
    invalid_world = replace(packet.world_updates[0], tile_changes=(*packet.world_updates[0].tile_changes, missing))
    invalid = update.model_copy(update={'lineages': (replace(packet, world_updates=(invalid_world,)),)})
    retained = deepcopy(before)
    with pytest.raises(ValueError, match='already known tile'):
        reduce_operation(before, invalid)
    assert before == retained

    # An introduction earlier in this operation is valid, even when the node
    # carrying it has no ordinary fact. A future introduction cannot repair a gap.
    tile = before.tiles[(1, 0)].model_copy(update={'position': (99, 99), 'tile_uuid': uuid4()})
    entering = dict(entered=mask_from_positions([(99, 99)]), tile_statics=(TileStatic(position=(99, 99),
        tile_uuid=tile.tile_uuid, surface=tile.surface, name=tile.name),), tile_columns=pack_tile_columns({(99, 99): tile}))
    later = project_event(session, projection, light_change(start.observer_uuid, LightLevel.DARKNESS), 3)
    introduction = replace(packet, events=(replace(packet.events[0], fact=None),),
        world_updates=(replace(packet.world_updates[0], tile_changes=(), **entering),))
    patch = replace(later, world_updates=(replace(later.world_updates[0], tile_changes=(missing,)),))
    valid = update.model_copy(update={'lineages': (introduction, patch)})
    actual = reduce_operation(before, valid)
    assert actual.tiles[(99, 99)].walking_cost == 3
    invalid = update.model_copy(update={'lineages': (
        replace(packet, world_updates=(replace(packet.world_updates[0], tile_changes=(missing,)),)),
        replace(later, world_updates=(replace(later.world_updates[0], tile_changes=(), **entering),)))})
    with pytest.raises(ValueError, match='already known tile'):
        reduce_operation(before, invalid)
    assert before == retained


@pytest.mark.parametrize('changes', [
    {'resolved_light': None}, {'condition_names': None}, {'walking_cost': -1},
    {'walking_cost': True}, {'walking_cost': 1.5}, {'tile_uuid': str(uuid4())},
    {'position': [1, 0]}, {'unknown': 1},
])
def test_tile_field_wire_rejects_invalid_values_and_identity_changes(changes):
    with pytest.raises(ValidationError):
        TypeAdapter(TileFieldUpdate).validate_json(json.dumps({'position': [1, 0], 'changes': changes}))
