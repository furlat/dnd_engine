from dnd.core.events import EventHandler, Trigger, EventType, EventPhase, WeaponSlot
from dnd.actions import AttackEvent, MovementEvent, Attack, entity_action_economy_cost_evaluator
from dnd.core.base_actions import Cost
from dnd.entity import Entity
from uuid import UUID
from typing import Optional


def opportunity_attack_processor(event: MovementEvent, source_entity_uuid: UUID) -> Optional[MovementEvent]:
    """checks if movement event is an opportunity attack, source entity uuid is the entity that 
    added this trigger to the event q, the event.source_entity_uuid is the entity that is moving
    
    this is a quite greed approach since any movement will trigger this check"""
    #first we get the source entity
    reaction_source_entity = Entity.get(source_entity_uuid)
    event_source_entity = Entity.get(event.source_entity_uuid)
    if reaction_source_entity is None or event_source_entity is None:
        return event
    threathened_positions = reaction_source_entity.senses.get_threathened_positions()


    if event.path and event.start_position in threathened_positions and any(position not in threathened_positions for position in event.path) and len(event.costs)>0:
        # the source entity starts from a threathened position and paths outside of it
        reaction_attack = Attack(name="Opportunity Attack",
                                 source_entity_uuid=source_entity_uuid,
                                 target_entity_uuid=event.source_entity_uuid,
                                 parent_event=event,
                                 weapon_slot=WeaponSlot.MAIN_HAND,
                                 use_register=False,
                                 costs=[Cost(name="Opportunity Attack Cost",cost_type="reactions",cost=1,evaluator=entity_action_economy_cost_evaluator)]
        )
        if reaction_attack.pre_validate():
            print(f"Opportunity attack {reaction_attack.name} validated")
            reaction_attack.add_to_register() 
            reaction_attack.apply(parent_event=event)
            return event

        
        
        return event
    return event


def create_opputinity_attack_handler(source_entity_uuid: UUID) -> EventHandler:
    return EventHandler(name="Opportunity Attack Handler",
                        trigger_conditions=[Trigger(name="Opportunity Attack Trigger",
                                     event_type=EventType.MOVEMENT,
                                     event_phase=EventPhase.EFFECT)],
                        event_processor=opportunity_attack_processor,
                        source_entity_uuid=source_entity_uuid)

def add_opportunity_attack_handler(entity: Entity):
    entity.add_event_handler(create_opputinity_attack_handler(entity.uuid))
