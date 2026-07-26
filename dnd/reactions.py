"""Reaction handlers for combat movement triggers."""

from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventHandler, Trigger, EventType, EventPhase, StepMovementEvent
from dnd.actions import Attack, entity_action_economy_cost_evaluator
from dnd.core.base_actions import Cost
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.entity import Entity
from uuid import UUID
from typing import Optional


def opportunity_attack_processor(event: StepMovementEvent, source_entity_uuid: UUID) -> Optional[StepMovementEvent]:
    """Check if a single movement step triggers an opportunity attack.

    Triggers when an entity leaves a threatened position to a non-threatened position.

    Args:
        event: Movement step being processed.
        source_entity_uuid: Entity that could make the opportunity attack.

    Returns:
        The processed step event.
    """
    reaction_source_entity = Entity.get(source_entity_uuid)
    event_source_entity = Entity.get(event.source_entity_uuid)
    if reaction_source_entity is None or event_source_entity is None:
        return event

    if reaction_source_entity.uuid == event_source_entity.uuid:
        return event

    if reaction_source_entity.is_ally(event_source_entity):
        return event

    if "Disengaging" in event_source_entity.active_conditions:
        return event

    threatened_positions = reaction_source_entity.senses.get_threathened_positions()

    if event.from_position in threatened_positions and event.to_position not in threatened_positions:
        reaction_attack = Attack(
            name="Opportunity Attack",
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=event.source_entity_uuid,
            parent_event=event,
            weapon_slot=WeaponSlot.MELEE_MAIN,
            use_register=False,
            costs=[Cost(
                name="Opportunity Attack Cost",
                cost_type="reactions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator
            )]
        )
        if reaction_attack.pre_validate():
            reaction_attack.add_to_register()
            reaction_attack.apply(parent_event=event)

    return event


class OpportunityAttackHandler(EventHandler):
    """Direct player-toggleable reaction with one authored behavior identity."""


def create_opportunity_attack_handler(
    source_entity_uuid: UUID,
) -> OpportunityAttackHandler:
    """Create an opportunity-attack handler for one entity.

    Args:
        source_entity_uuid: Entity that owns the reaction handler.

    Returns:
        Player-toggleable step-movement handler.
    """
    return OpportunityAttackHandler(
        name="Opportunity Attack Handler",
        semantic_key="reaction.opportunity_attack",
        content_kind=RuntimeBehaviorKind.REACTION,
        trigger_conditions=[Trigger(
            name="Opportunity Attack Trigger",
            event_type=EventType.STEP_MOVEMENT,
            event_phase=EventPhase.EFFECT
        )],
        event_processor=opportunity_attack_processor,
        source_entity_uuid=source_entity_uuid,
        player_toggleable=True
    )


def create_opputinity_attack_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create opportunity-attack handler using the legacy misspelled API name."""
    return create_opportunity_attack_handler(source_entity_uuid)


def add_opportunity_attack_handler(entity: Entity) -> None:
    """Register an opportunity-attack handler on an entity.

    Args:
        entity: Entity receiving the reaction handler.
    """
    entity.add_event_handler(create_opportunity_attack_handler(entity.uuid))
