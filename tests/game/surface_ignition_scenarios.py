"""Recorded native material interactions and movement, with independent owners."""

import random

from dnd.actions import ActionEvent
from dnd.controller import HumanController
from dnd.core.events import EventPhase, EventQueue, SpatialEffectInteractionEvent
from dnd.core.gridmap import get_map
from dnd.core.dice import fixed_dice_faces
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.environmental_conditions import FireSurface, OilSurface, BurningWeb
from dnd.spells.conjuration import WebZone
from dnd.types.spatial_effects import SpatialEffectInteractionOperation
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.game.door_destruction_scenarios import review_actor, walk


def surface_ignition_history() -> CapturedHistory:
    previous_random=random.getstate();reset_engine_runtime()
    battlefield='battlefield.open_floor_bright';build_battlefield(battlefield);game=Game()
    try:
        actors={role:review_actor(game,role.title(),position) for role,position in
            (('operator',(5,6)),('witness',(8,6)))}
        operator=actors['operator']
        for cls,cells in ((OilSurface,{(6,5),(7,5),(8,5)}),(WebZone,{(9,5)})):
            condition=cls(source_entity_uuid=operator.uuid,position=min(cells),affected_positions=cells)
            condition.activate(parent_event=ActionEvent(source_entity_uuid=operator.uuid,phase=EventPhase.EFFECT))
        encounter=Encounter(name='Native ignition and partial dousing',source_entity_uuid=operator.uuid)
        for actor in actors.values():encounter.add_combatant(actor,HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20,1):encounter.start_encounter()
        encounter.start_turn();Entity.update_all_entities_senses()
        baseline=EventQueue.event_cursor()
        initial=capture_interval(name='Material cells and witnesses',start_cursor=0,end_cursor=baseline,
            observer_uuid=operator.uuid,battlefield_id=battlefield)
        before,_=reduce_interval(None,initial)
        second=FireSurface(source_entity_uuid=actors['witness'].uuid,position=(7,5),affected_positions={(7,5)})
        def interact(operation,cells):
            event=EventQueue.publish_declaration(SpatialEffectInteractionEvent(source_entity_uuid=operator.uuid,
                operation=operation,positions=tuple(sorted(cells)),phase=EventPhase.DECLARATION,use_register=False))
            for phase in (EventPhase.EXECUTION,EventPhase.EFFECT,EventPhase.COMPLETION):
                event=event.phase_to(phase)
                if phase is EventPhase.EFFECT and operation is SpatialEffectInteractionOperation.IGNITE:
                    second.activate(parent_event=event)
            assert not event.canceled
            return event
        interact(SpatialEffectInteractionOperation.IGNITE,{(6,5),(7,5),(8,5),(9,5)})
        native_fire=[row for row in get_map().get_spatial_conditions() if isinstance(row,(FireSurface,BurningWeb))]
        assert {p for row in native_fire for p in row.affected_positions}=={(6,5),(7,5),(8,5),(9,5)}
        assert second.applied
        before_hp=operator.get_hp()
        walk(operator,(6,5),dice=(2,2))
        assert operator.get_hp()<before_hp
        walk(operator,(5,6))
        interact(SpatialEffectInteractionOperation.DOUSE,{(6,5)})
        assert second.applied and second.affected_positions=={(7,5)}
        assert not any((6,5) in row.affected_positions for row in get_map().get_spatial_conditions() if isinstance(row,FireSurface))
        interact(SpatialEffectInteractionOperation.DOUSE,{(8,5)})
        assert second.applied
        for _ in range(8):encounter.next_turn()
        assert not any(isinstance(row,(FireSurface,BurningWeb)) for row in get_map().get_spatial_conditions())
        captured=capture_history(before,(),observers=tuple(ObserverCapture(role,a.uuid,baseline) for role,a in actors.items()))
        primary=captured.views['operator'];return CapturedHistory(primary.initialization,before,primary.lineages,captured.views)
    finally:
        game.close();reset_engine_runtime();random.setstate(previous_random)
