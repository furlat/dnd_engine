"""Revision stamps for re-entry (player schema 16): a record re-entering a seat's perception travels whole only
when something wrote it since the seat last had it whole; otherwise the seat keeps it as it holds it.

Recorded events in, the seat's world updates and client worlds out. A kept record must leave the client exactly
as a whole send would, and the seat's stamps must be restorable from the updates it received.
"""

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.cells import mask_positions
from dnd.core.events import EventPhase, SpatialChangeEvent, SpatialChangeType, WorldModifiedEvent
from dnd.core.item_types import ItemConcentrationSlot, ItemRemnantState
from dnd.player.capture import CompletedLineage
from dnd.player.facts import PlayerState
from dnd.player.projection import SessionProjection, begin_projection, project_lineage
from dnd.player.reduction import reduce_initialization, reduce_lineage
from dnd.player.revision_stamps import unchanged_since
from dnd.player.stamp_replay import replay_revision_stamps
from dnd.player.world_columns import unpack_object_rows
from dnd.types.senses import PerceivedContact
from dnd.types.world import CardinalDirection, LightLevel
from dnd.types.world_placement import BoundaryStructure, BoundaryStructureKind
from dnd.types.materials import Material
from tests.player.test_projection_local_world import initial, item, objective, placed, sensory


def walk(start, events):
    """Each event projected as its own lineage: the client world after each, each packet's world updates, and
    whether the seat's stamps restored from every update it received equal its live stamps."""
    session = SessionProjection()
    projection, public = begin_projection(session, start)
    states, packets = [reduce_initialization(public)], []
    received = list(public.world_updates)
    for index, event in enumerate(events, start=start.end_cursor):
        packet = project_lineage(session, projection, CompletedLineage(generation=start.generation,
            observer_uuid=start.observer_uuid, root=event, events=(event,), objective_rows=(objective(index, event),),
            start_cursor=index, end_cursor=index + 1))
        states.append(states[-1] if packet is None else reduce_lineage(states[-1], packet))
        packets.append(packet.world_updates if packet is not None else ())
        received.extend(packets[-1])
    native_of = {public_index: native for native, public_index in projection.public_cursors.items()}
    restored = replay_revision_stamps(PlayerState(generation=public.generation, observer_uuid=public.observer_uuid,
        world=public.world, audience=public.audience), received, native_of)
    return states, packets, restored == projection.revision_stamps


def world(state):
    return state.tiles, state.objects, state.object_members


def light(observer, cell, level):
    return SpatialChangeEvent.model_validate(dict(source_entity_uuid=observer, use_register=False,
        phase=EventPhase.COMPLETION, change_type=SpatialChangeType.LIGHT_CHANGED, position=cell,
        light_level_map={f"{cell[0]},{cell[1]}": level.value}), context=PASSIVE_EVENT_REPLAY)


def renamed(observer, obj, name):
    after = obj.model_copy(update={'item': obj.item.model_copy(update={'name': name})})
    return WorldModifiedEvent.model_validate(dict(source_entity_uuid=observer, use_register=False,
        phase=EventPhase.COMPLETION, object_uuid=obj.item.item_uuid, before=obj, after=after),
        context=PASSIVE_EVENT_REPLAY)


def seen(cell):
    return PerceivedContact(position=cell, visual=True, special_senses=())


def box_scene():
    """A box on a cell the seat sees, in its contact."""
    box = placed(item('Box'), (1, 0))
    return box, initial((box,), ((1, 0),), {box.item.item_uuid: seen((1, 0))})


def test_an_unwritten_tile_and_object_reenter_kept_and_leave_the_client_as_a_whole_send():
    box, start = box_scene()
    identity = box.item.item_uuid
    observer = start.observer_uuid
    states, packets, restored = walk(start, (
        sensory(observer, visible_cells_removed=[(1, 0)], object_contacts_removed={identity}),
        sensory(observer, visible_cells_added=[(1, 0)], object_contacts_changed={identity: seen((1, 0))}),
    ))
    update, = packets[1]
    assert mask_positions(update.tiles_unchanged) == [(1, 0)] and update.tile_columns is None
    assert update.objects_unchanged == (identity,) and update.objects is None
    assert world(states[2]) == world(states[0])
    assert restored


def test_a_record_written_while_unseen_reenters_whole():
    box, start = box_scene()
    identity = box.item.item_uuid
    observer = start.observer_uuid
    states, packets, restored = walk(start, (
        sensory(observer, visible_cells_removed=[(1, 0)], object_contacts_removed={identity}),
        light(observer, (1, 0), LightLevel.DIM_LIGHT),
        renamed(observer, box, 'Crate'),
        sensory(observer, visible_cells_added=[(1, 0)], object_contacts_changed={identity: seen((1, 0))}),
    ))
    update, = packets[3]
    assert not mask_positions(update.tiles_unchanged) and update.tile_columns is not None and not update.objects_unchanged
    assert [row.item_uuid for row in unpack_object_rows(update.objects)] == [identity]
    assert states[4].tiles[(1, 0)].resolved_light is LightLevel.DIM_LIGHT
    assert states[4].objects[identity].item.name == 'Crate'
    assert restored


def test_a_keyed_change_seen_in_view_does_not_vouch_for_the_whole_record():
    """A keyed change carries only what it wrote; the record's next re-entry is whole."""
    box, start = box_scene()
    identity = box.item.item_uuid
    observer = start.observer_uuid
    states, packets, restored = walk(start, (
        light(observer, (1, 0), LightLevel.DIM_LIGHT),
        sensory(observer, visible_cells_removed=[(1, 0)], object_contacts_removed={identity}),
        sensory(observer, visible_cells_added=[(1, 0)], object_contacts_changed={identity: seen((1, 0))}),
    ))
    assert [mask_positions(row.entered) for row in packets[0]] == [[]]
    update, = packets[2]
    assert update.tile_columns is not None and not mask_positions(update.tiles_unchanged)
    assert update.objects_unchanged == (identity,)
    assert world(states[3]) == world(states[1])
    assert restored


def test_an_object_the_client_dropped_unobserved_travels_whole_when_seen_again():
    box, start = box_scene()
    identity = box.item.item_uuid
    observer = start.observer_uuid
    states, packets, restored = walk(start, (
        sensory(observer, visible_cells_removed=[(1, 0)], object_contacts_removed={identity}),
        # The cell re-enters with the box out of contact: the client drops what it held there.
        sensory(observer, visible_cells_added=[(1, 0)]),
        sensory(observer, object_contacts_changed={identity: seen((1, 0))}),
    ))
    assert identity not in states[2].objects
    update, = packets[2]
    assert [row.item_uuid for row in unpack_object_rows(update.objects)] == [identity] and not update.objects_unchanged
    assert states[3].objects[identity] == states[0].objects[identity]
    assert restored


def test_a_face_newly_seen_or_a_view_disclosed_field_needs_the_object_whole():
    """A face the seat's last row did not show needs its residues; a remnant (its known attachments) and a
    concentration slot naming a cast lineage (the lineages disclosed) follow the seat's knowledge, not the record."""
    wall = placed(item('Wall').model_copy(update={'boundary_structure': BoundaryStructure(
        structure=BoundaryStructureKind.WALL, material=Material.STONE, blocked_channels=())}),
        (1, 0), direction=CardinalDirection.EAST)
    ruin = placed(item('Ruin').model_copy(update={'remnant_state': ItemRemnantState(door_open=True)}), (4, 0))
    altar = placed(item('Altar').model_copy(update={'concentration_slots': (ItemConcentrationSlot(
        slot_uuid=ruin.item.item_uuid, cast_lineage_uuid=wall.item.item_uuid, spell_name='Light'),)}), (5, 0))
    walls, ruins, altars = wall.item.item_uuid, ruin.item.item_uuid, altar.item.item_uuid
    start = initial((wall, ruin, altar), ((1, 0), (4, 0), (5, 0)), {ruins: seen((4, 0)), altars: seen((5, 0))})
    observer = start.observer_uuid
    _, packets, restored = walk(start, (
        sensory(observer, visible_cells_removed=[(1, 0), (4, 0), (5, 0)], object_contacts_removed={ruins, altars}),
        # The wall comes back through its east face, which the seat's last row of it did not show.
        sensory(observer, visible_cells_added=[(2, 0), (4, 0), (5, 0)],
                object_contacts_changed={ruins: seen((4, 0)), altars: seen((5, 0))}),
    ))
    update, = packets[1]
    assert {row.item_uuid for row in unpack_object_rows(update.objects)} == {walls, ruins, altars}
    assert not update.objects_unchanged
    assert restored


def test_the_rule_is_the_seats_stamp_against_the_records_last_write():
    assert unchanged_since(7, 7) and unchanged_since(7, 3)
    assert not unchanged_since(7, 8) and not unchanged_since(None, 3) and not unchanged_since(7, None)


def test_a_seat_with_no_stamps_reenters_whole():
    """The restore's fallback: without stamps every re-entering record travels whole, as before stamps."""
    box, start = box_scene()
    identity = box.item.item_uuid
    observer = start.observer_uuid
    session = SessionProjection()
    projection, _ = begin_projection(session, start)
    events = (sensory(observer, visible_cells_removed=[(1, 0)], object_contacts_removed={identity}),
              sensory(observer, visible_cells_added=[(1, 0)], object_contacts_changed={identity: seen((1, 0))}))
    for index, event in enumerate(events, start=start.end_cursor):
        # The seat restored without its stamps.
        projection.revision_stamps.tiles.clear()
        projection.revision_stamps.objects.clear()
        packet = project_lineage(session, projection, CompletedLineage(generation=start.generation,
            observer_uuid=start.observer_uuid, root=event, events=(event,), objective_rows=(objective(index, event),),
            start_cursor=index, end_cursor=index + 1))
    assert packet is not None
    update, = packet.world_updates
    assert update.tile_columns is not None and [row.item_uuid for row in unpack_object_rows(update.objects)] == [identity]
