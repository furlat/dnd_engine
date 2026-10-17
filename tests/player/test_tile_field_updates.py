"""Event-associated tile fields preserve every admitted intermediate state."""

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
from dnd.player.facts import PlayerLineage, PlayerSequence, PlayerUpdate, TileFieldUpdate
from dnd.player.projection import begin_projection, project_lineage
from dnd.player.reduction import (decode_player_sequence, encode_player_sequence, reduce_initialization,
    reduce_lineage, reduce_operation, stage_lineage)
from dnd.types.materials import Material, TileSurface
from dnd.types.residues import TileResidueState
from dnd.types.world import LightLevel
from tests.player.test_projection_local_world import initial, objective, sensory


def light_change(observer, light):
    return SpatialChangeEvent.model_validate(dict(source_entity_uuid=observer,
        use_register=False, phase=EventPhase.COMPLETION, event_type=EventType.SPATIAL_LIGHT_CHANGED,
        change_type=SpatialChangeType.LIGHT_CHANGED, position=(1, 0),
        light_level_map={"1,0": light.value}), context=PASSIVE_EVENT_REPLAY)


def project_event(projection, event, index, *, disclosed=True):
    native = CompletedLineage(generation=projection.remembered.generation,
        observer_uuid=projection.remembered.observer_uuid, root=event, events=(event,),
        objective_rows=(objective(index, event),), start_cursor=index, end_cursor=index+1)
    packet = project_lineage(projection, native)
    assert (packet is not None) is disclosed
    return packet


def test_known_tile_light_updates_carry_only_changed_fields_at_each_event():
    start = initial((), ((1, 0), (2, 0)), {})
    projection, public = begin_projection(start)
    before = reduce_initialization(public)
    state = before
    retained = []
    packets = []
    for index, light in enumerate((LightLevel.DIM_LIGHT, LightLevel.DARKNESS,
                                   LightLevel.BRIGHT_LIGHT), start.end_cursor):
        event = light_change(start.observer_uuid, light)
        packet = project_event(projection, event, index)
        packets.append(packet)
        update, = packet.world_updates
        assert update.occurrence == projection.public_cursors[index]
        assert update.tiles == ()
        change, = update.tile_changes
        assert change.position == (1, 0)
        assert change.changes == {"resolved_light": light}
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


def test_tile_field_updates_preserve_clears_and_replace_nested_values():
    start = initial((), ((1, 0),), {})
    projection, public = begin_projection(start)
    before = reduce_initialization(public)
    original = before.tiles[(1, 0)]
    changes = dict(name='Ramp', surface=TileSurface(base_material=Material.WOOD),
        blocks_optics=True, blocks_propagation=True, walking_cost=2, flying_cost=2,
        swimming_cost=2, burrowing_cost=2, elevation_steps=2,
        surface_kind=ElevationSurfaceKind.RAMP, slope_axis=SlopeAxis.EAST_WEST,
        default_light=LightLevel.DIM_LIGHT, resolved_light=LightLevel.DIM_LIGHT,
        condition_names=('Ash',), residues=(TileResidueState(condition_uuid=uuid4(),
            residue_id='test.ash', description='Ash'),))
    enriched = original.model_copy(update=changes)
    packet = project_event(projection, tile_change(start.observer_uuid, enriched), start.end_cursor)
    delta, = packet.world_updates[0].tile_changes
    assert delta.changes == changes
    changed = reduce_lineage(before, packet)
    clears = dict(blocks_optics=False, blocks_propagation=False, walking_cost=0,
        flying_cost=0, swimming_cost=0, burrowing_cost=0, elevation_steps=0,
        surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None,
        default_light=LightLevel(0), resolved_light=LightLevel(0), condition_names=(), residues=())
    cleared = enriched.model_copy(update=clears)
    packet = project_event(projection, tile_change(start.observer_uuid, cleared), start.end_cursor+1)
    wire = TypeAdapter(PlayerLineage).dump_json(packet)
    parsed = TypeAdapter(PlayerLineage).validate_json(wire)
    raw = json.loads(wire)['world_updates'][0]['tile_changes'][0]['changes']
    assert raw['slope_axis'] is None and raw['condition_names'] == [] and raw['residues'] == []
    assert raw['blocks_optics'] is False and raw['walking_cost'] == raw['resolved_light'] == 0
    assert 'name' not in raw and 'surface' not in raw
    assert parsed.world_updates[0].tile_changes[0].changes == clears
    after = reduce_lineage(changed, parsed)
    assert after.tiles[(1, 0)] == cleared
    assert after.tiles[(1, 0)].name == 'Ramp'
    assert changed.tiles[(1, 0)] == enriched and before.tiles[(1, 0)] == original


def test_hidden_tile_changes_remain_private_until_discovery_and_identity_replacement_is_full():
    start = initial((), ((1, 0),), {})
    projection, public = begin_projection(start)
    state = reduce_initialization(public)
    hide = project_event(projection, sensory(start.observer_uuid, visible_cells_removed=[(1, 0)]), 2)
    state = reduce_lineage(state, hide)
    assert project_event(projection, light_change(start.observer_uuid, LightLevel.DIM_LIGHT),
                         3, disclosed=False) is None
    assert state.tiles[(1, 0)].resolved_light is LightLevel.BRIGHT_LIGHT
    reveal = project_event(projection, sensory(start.observer_uuid, visible_cells_added=[(1, 0), (2, 0)]), 4)
    assert [tile.position for update in reveal.world_updates for tile in update.tiles] == [(2, 0)]
    assert [row.position for update in reveal.world_updates for row in update.tile_changes] == [(1, 0)]
    state = reduce_lineage(state, reveal)
    old = state.tiles[(1, 0)]
    replacement = old.model_copy(update={'tile_uuid': uuid4(), 'name': 'Replacement'})
    replaced = project_event(projection, tile_change(start.observer_uuid, replacement), 5)
    assert replaced.world_updates[0].tiles == (replacement,)
    assert not replaced.world_updates[0].tile_changes
    after = reduce_lineage(state, replaced)
    assert after.tiles[(1, 0)] == replacement and state.tiles[(1, 0)] == old


def test_client_fold_checks_tile_bases_in_event_order_without_staging_future_values():
    start = initial((), ((1, 0),), {})
    projection, public = begin_projection(start)
    before = reduce_initialization(public)
    packet = project_event(projection, light_change(start.observer_uuid, LightLevel.DIM_LIGHT), 2)
    assert stage_lineage(before, packet).tiles[(1, 0)] == before.tiles[(1, 0)]
    update = PlayerUpdate(audience=before.viewing_audience, lineages=(packet,), hud=None,
                          combat_log_appends=(), content_additions=())
    missing = TileFieldUpdate(position=(99, 99), changes={'resolved_light': LightLevel.DARKNESS})
    invalid_world = replace(packet.world_updates[0], tile_changes=(*packet.world_updates[0].tile_changes, missing))
    invalid = update.model_copy(update={'lineages': (replace(packet, world_updates=(invalid_world,)),)})
    retained = deepcopy(before)
    with pytest.raises(ValueError, match='already known tile'):
        reduce_operation(before, invalid)
    assert before == retained

    # An introduction earlier in this operation is valid, even when the node
    # carrying it has no ordinary fact. A future introduction cannot repair a gap.
    tile = before.tiles[(1, 0)].model_copy(update={'position': (99, 99), 'tile_uuid': uuid4()})
    later = project_event(projection, light_change(start.observer_uuid, LightLevel.DARKNESS), 3)
    introduction = replace(packet, events=(replace(packet.events[0], fact=None),),
        world_updates=(replace(packet.world_updates[0], tiles=(tile,), tile_changes=()),))
    patch = replace(later, world_updates=(replace(later.world_updates[0], tiles=(), tile_changes=(missing,)),))
    valid = update.model_copy(update={'lineages': (introduction, patch)})
    actual = reduce_operation(before, valid)
    assert actual.tiles[(99, 99)].resolved_light is LightLevel.DARKNESS
    invalid = update.model_copy(update={'lineages': (
        replace(packet, world_updates=(replace(packet.world_updates[0], tiles=(), tile_changes=(missing,)),)),
        replace(later, world_updates=(replace(later.world_updates[0], tiles=(tile,), tile_changes=()),)))})
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
