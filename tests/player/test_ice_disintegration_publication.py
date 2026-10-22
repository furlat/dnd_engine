"""A real full Ice section removal keeps only the audience's current contact.

Input: Wall of Ice, optional loss of blue sight, then Disintegrate.
Boundary: native action through detached application updates and client fold.
Expected: one witnessed destruction per seeing seat, no stale-sight disclosure.
"""

from contextlib import contextmanager

import pytest

from dnd.actions_functional import register_spell
from dnd.conditions import Blinded
from dnd.core.base_block import BaseBlock
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, ItemDestructionEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.core.life_types import RemainsDisposition
from dnd.player.application import capture_application_operation
from dnd.player.facts import ObjectDestroyedFact, PlayerUpdate
from dnd.player.reduction import reduce_operation
from dnd.spells.transmutation import Disintegrate
from dnd.spells.wall_constructions import FrigidAirZone, WallOfIce, WallOfIceZone
from tests.player.test_emitted_update_replica import operation_since
from tests.player.test_handoff_discovery_regressions import submit
from tests.player.test_solid_wall_transport import clients_at_boundary, fold_records, selection_preview, wall_world


def capture(runtime, clients, cursor):
    updates = capture_application_operation(runtime.audiences,
        operation_since(runtime.session, cursor), runtime.catalog)
    detached = {seat: PlayerUpdate.model_validate_json(update.model_dump_json())
        for seat, update in updates.items()}
    for seat, update in detached.items():
        clients[seat] = reduce_operation(clients[seat], update)
    return detached


@contextmanager
def ice_section(*, hidden_blue=False):
    with wall_world(WallOfIce, displaced=False) as world:
        runtime, seat, publication = world
        caster = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        clients = clients_at_boundary(runtime)
        discovered, selection, preview = selection_preview(world, 'spell.wall_of_ice', 'right',
            positions=((6, 6), (8, 6)))
        assert preview.can_confirm
        records = submit(runtime, seat, caster, discovered, selection, 20)
        fold_records(runtime, clients, records)
        owner, = (zone for zone in get_map().get_spatial_conditions() if isinstance(zone, WallOfIceZone))
        identity, = owner.sections
        assert all(identity in client.senses.objects for client in clients.values())
        if hidden_blue:
            cursor = EventQueue.event_cursor()
            for observer in runtime.audiences['blue'].projection.audience.observers:
                actor = runtime.session.game.entities[observer]
                result = actor.add_condition(Blinded(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid))
                assert result is not None and not result.canceled
            capture(runtime, clients, cursor)
            assert identity not in clients['blue'].senses.objects
        register_spell(caster, Disintegrate, caster_level=20)
        caster.action_economy.reset_all_costs()
        spell, = (action for action in caster.registered_actions if isinstance(action, Disintegrate))
        yield runtime, clients, identity, spell


@pytest.mark.parametrize('hidden_blue,hide_on_cast', [(False, False), (True, False), (False, True)])
def test_full_ice_section_disintegration_publishes_current_observed_contact(hidden_blue, hide_on_cast):
    with ice_section(hidden_blue=hidden_blue) as (runtime, clients, identity, spell):
        if hide_on_cast:
            def lose_sight(event, _):
                for observer in runtime.audiences['blue'].projection.audience.observers:
                    actor = runtime.session.game.entities[observer]
                    condition = actor.add_condition(Blinded(source_entity_uuid=actor.uuid,
                        target_entity_uuid=actor.uuid), parent_event=event)
                    assert condition is not None and not condition.canceled
            EventQueue.add_event_handler(EventHandler(name='Lose sight during cast',
                source_entity_uuid=spell.source_entity_uuid,
                trigger_conditions=[Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EFFECT)],
                event_processor=lose_sight))
        cursor = EventQueue.event_cursor()
        with fixed_dice_faces(*([4] * 100)):
            result = spell.instantiate(target_entity_uuid=identity, cast_at_level=6).apply()
        assert result is not None and not result.canceled
        native = [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, ItemDestructionEvent) and event.phase is EventPhase.COMPLETION]
        assert len(native) == 1 and native[0].item_uuid == identity
        assert BaseBlock.get(identity) is None
        assert any(isinstance(zone, FrigidAirZone) for zone in get_map().get_spatial_conditions())
        updates = capture(runtime, clients, cursor)
        for seat, update in updates.items():
            facts = [node.fact for group in update.lineages for node in group.events
                if isinstance(node.fact, ObjectDestroyedFact)]
            if seat == 'blue' and (hidden_blue or hide_on_cast):
                assert not facts
                assert identity in clients[seat].objects  # Its last-seen memory is not a removal witness.
                assert identity not in clients[seat].senses.objects
            else:
                fact, = facts
                assert fact.object_uuid == identity
                assert fact.remains_disposition is RemainsDisposition.DISINTEGRATED
                assert fact.previous_item is not None and fact.previous_item.item_uuid == identity
                assert fact.placement == native[0].previous_placement
                assert fact.affected_volume is None
                assert identity not in clients[seat].objects


def test_refused_full_ice_removal_publishes_no_destruction():
    with ice_section() as (runtime, clients, identity, spell):
        EventQueue.add_event_handler(EventHandler(name='Refuse Ice removal',
            source_entity_uuid=spell.source_entity_uuid,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_REMOVED, event_phase=EventPhase.EFFECT)],
            event_processor=lambda event, _: event.cancel(status_message='Removal refused')))
        cursor = EventQueue.event_cursor()
        result = spell.instantiate(target_entity_uuid=identity, cast_at_level=6).apply()
        assert result is not None and result.canceled
        updates = capture(runtime, clients, cursor)
        assert BaseBlock.get(identity) is not None
        assert not any(isinstance(zone, FrigidAirZone) for zone in get_map().get_spatial_conditions())
        for seat, update in updates.items():
            assert not any(isinstance(node.fact, ObjectDestroyedFact)
                for group in update.lineages for node in group.events)
            assert identity in clients[seat].objects and identity in clients[seat].senses.objects
