"""
Functional API for action setup and execution.

This module provides functions to setup, query, and execute actions for entities.
It serves as the main API for action management, keeping Entity free from
circular import dependencies with the actions module.

Usage:
    from dnd.actions_functional import setup_standard_actions, get_available_actions, execute_action

    # After creating an entity
    entity = Entity.create(...)
    setup_standard_actions(entity)

    # Query available actions
    available = get_available_actions(entity)

    # Execute an action
    event = execute_action(entity, "Attack_MELEE_MAIN", target)
"""

from typing import Optional, TYPE_CHECKING
from uuid import UUID

from dnd.core.base_actions import (
    TargetType, AvailableTarget, AvailableActionInfo, AvailableActionsResult
)
from dnd.core.events import Event, EventHandler, Trigger, EventType, EventPhase, EventQueue
from dnd.blocks.equipment import WeaponSlot, Weapon

if TYPE_CHECKING:
    from dnd.entity import Entity


def setup_standard_actions(entity: 'Entity') -> None:
    """Register standard D&D 5e actions for an entity.

    This sets up the base actions available to all entities:
    - Move (position targeting)
    - Dash, Dodge, Disengage, StandUp (self targeting)
    - Attack templates for equipped weapons (entity targeting)

    Also registers event handlers to auto-update attack templates
    when weapons are equipped/unequipped.

    Args:
        entity: The entity to set up actions for
    """
    from dnd.actions import Move, Dash, Dodge, Disengage, StandUp

    # Clear existing templates
    entity.registered_actions = []

    # Register movement and self-targeting actions
    entity.register_action(Move(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Dash(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Dodge(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Disengage(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(StandUp(source_entity_uuid=entity.uuid, template=True))
    # Note: DropProne is not registered - Prone is applied by spells/effects, not as a voluntary action

    # Register attack templates for currently equipped weapons
    update_weapon_templates(entity)

    # Register event handlers for weapon equip/unequip to auto-update templates
    _setup_weapon_event_handlers(entity)


def _setup_weapon_event_handlers(entity: 'Entity') -> None:
    """Set up event handlers to auto-update attack templates on weapon changes.

    Args:
        entity: The entity to set up handlers for
    """
    from dnd.entity import Entity
    from dnd.blocks.equipment import WeaponEquipEvent, WeaponUnequipEvent

    entity_uuid = entity.uuid

    def _on_weapon_equip(event: Event, _source: UUID) -> Optional[Event]:
        """Handler for weapon equip events - updates attack templates."""
        if event.source_entity_uuid == entity_uuid:
            if isinstance(event, WeaponEquipEvent) and isinstance(event.slot, WeaponSlot):
                ent = Entity.get(entity_uuid)
                if ent:
                    update_weapon_template(ent, event.slot)
        return event

    def _on_weapon_unequip(event: Event, _source: UUID) -> Optional[Event]:
        """Handler for weapon unequip events - updates attack templates."""
        if event.source_entity_uuid == entity_uuid:
            if isinstance(event, WeaponUnequipEvent) and isinstance(event.slot, WeaponSlot):
                ent = Entity.get(entity_uuid)
                if ent:
                    update_weapon_template(ent, event.slot)
        return event

    equip_handler = EventHandler(
        source_entity_uuid=entity.uuid,
        name=f"WeaponEquipHandler_{entity.uuid}",
        trigger_conditions=[Trigger(event_type=EventType.WEAPON_EQUIP, event_phase=EventPhase.EFFECT)],
        event_processor=_on_weapon_equip
    )
    unequip_handler = EventHandler(
        source_entity_uuid=entity.uuid,
        name=f"WeaponUnequipHandler_{entity.uuid}",
        trigger_conditions=[Trigger(event_type=EventType.WEAPON_UNEQUIP, event_phase=EventPhase.EFFECT)],
        event_processor=_on_weapon_unequip
    )
    EventQueue.add_event_handler(equip_handler)
    EventQueue.add_event_handler(unequip_handler)


def update_weapon_template(entity: 'Entity', slot: WeaponSlot) -> None:
    """Update the attack template for a single weapon slot.

    Called when a weapon is equipped or unequipped.

    Args:
        entity: The entity whose template to update
        slot: The weapon slot to update
    """
    from dnd.actions import Attack

    # Remove existing template for this slot if any
    template_name = f"Attack_{slot.value}"
    entity.unregister_action(template_name)

    # Register new template if weapon equipped
    weapon = entity.equipment._get_weapon_by_slot(slot)
    if weapon is not None and isinstance(weapon, Weapon):
        entity.register_action(Attack(
            source_entity_uuid=entity.uuid,
            weapon_slot=slot,
            name=template_name,
            template=True
        ))


def update_weapon_templates(entity: 'Entity') -> None:
    """Update attack templates for all weapon slots.

    Args:
        entity: The entity whose templates to update
    """
    for slot in [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF,
                 WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF]:
        update_weapon_template(entity, slot)


def get_available_actions(entity: 'Entity') -> AvailableActionsResult:
    """Get all available actions for an entity.

    Wrapper around Entity.get_available_actions() for functional API consistency.

    Args:
        entity: The entity to query actions for

    Returns:
        AvailableActionsResult with grouped actions and valid targets
    """
    return entity.get_available_actions()


def execute_action(entity: 'Entity', template_name: str, target: AvailableTarget) -> Optional[Event]:
    """Execute an action from template + target.

    This is the main execution API that creates an instance and applies it.

    Args:
        entity: The entity executing the action
        template_name: Name of the action template to execute
        target: The target for the action

    Returns:
        The resulting event, or None if the action failed

    Raises:
        ValueError: If the template is not found or target is invalid
    """
    template = entity.get_action_template(template_name)
    if template is None:
        raise ValueError(f"No template named {template_name}")

    # Create instance with appropriate target
    if template.target_type == TargetType.ENTITY:
        if target.target_uuid is None:
            raise ValueError("ENTITY action requires target_uuid")
        instance = template.instantiate(target_entity_uuid=target.target_uuid)

    elif template.target_type == TargetType.POSITION:
        if target.position is None:
            raise ValueError("POSITION action requires position")
        instance = template.instantiate(end_position=target.position)

    else:  # SELF
        instance = template.instantiate()

    return instance.apply()


def execute_by_index(entity: 'Entity', template_name: str, target_index: int) -> Optional[Event]:
    """Execute action by template name and target index.

    This enables "attack 0", "move 3" style commands.

    Args:
        entity: The entity executing the action
        template_name: Name of the action template to execute
        target_index: Index of the target in the valid_targets list

    Returns:
        The resulting event, or None if the action failed

    Raises:
        ValueError: If action or target index not found
    """
    available = get_available_actions(entity)

    # Find the action info
    action_info: Optional[AvailableActionInfo] = None
    for info in available.all_actions:
        if info.template_name == template_name:
            action_info = info
            break

    if action_info is None:
        raise ValueError(f"Action {template_name} not available")

    # Find the target by index
    target: Optional[AvailableTarget] = None
    for t in action_info.valid_targets:
        if t.index == target_index:
            target = t
            break

    if target is None:
        raise ValueError(f"Target index {target_index} not valid for {template_name}")

    return execute_action(entity, template_name, target)
