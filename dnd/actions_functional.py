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

from typing import Any, Callable, Dict, Optional, List, Tuple
from uuid import UUID

from dnd.core.base_actions import (
    BaseAction, TargetType, AvailableTarget, AvailableActionInfo, AvailableActionsResult
)
from dnd.core.events import Event, EventHandler, Trigger, EventType, EventPhase, EventQueue
from dnd.blocks.equipment import WeaponSlot, Weapon, WeaponEquipEvent, WeaponUnequipEvent
from dnd.entity import Entity
from dnd.actions import Move, Dash, Dodge, Disengage, DropConcentration, Hide, Attack, Jump, Shove, PickUp, AttackObject, Drop
from dnd.conditions import create_has_attacked_handler, create_has_taken_damage_handler, create_death_handler
from dnd.spells import ALL_SPELLS
from dnd.blocks.base_item import UsableItem
from dnd.core.base_block import BaseBlock


def setup_standard_actions(entity: Entity) -> None:
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
    # Clear existing templates
    entity.registered_actions = []

    # Register movement and self-targeting actions
    entity.register_action(Move(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Jump(source_entity_uuid=entity.uuid, template=True))  # LOS-based movement
    entity.register_action(Dash(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Dodge(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Disengage(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Hide(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(DropConcentration(source_entity_uuid=entity.uuid, template=True))
    # Note: StandUp is no longer registered - Prone auto-stands at turn start (BG3 style)
    entity.register_action(Shove(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(PickUp(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(AttackObject(source_entity_uuid=entity.uuid, template=True))
    # Note: DropProne is not registered - Prone is applied by spells/effects, not as a voluntary action

    # Register attack templates for currently equipped weapons
    update_weapon_templates(entity)

    # Register event handlers for weapon equip/unequip to auto-update templates
    _setup_weapon_event_handlers(entity)

    # Register global combat state handlers (HasAttacked, HasTakenDamage)
    # These track combat state for features like Extra Attack and Rage Maintenance
    entity.add_event_handler(create_has_attacked_handler(entity.uuid))
    entity.add_event_handler(create_has_taken_damage_handler(entity.uuid))

    # Register death handler (applies Dead condition when DEATH event fires)
    entity.add_event_handler(create_death_handler(entity.uuid))

    # Register Prone auto-stand handler (BG3 style - always present, fires at turn start)
    entity.add_event_handler(_create_prone_auto_stand_handler(entity.uuid))


def _create_prone_auto_stand_handler(entity_uuid: UUID) -> EventHandler:
    """Create handler to auto-stand at turn start (BG3 style).

    This handler is always registered (via setup_standard_actions) and checks
    at turn start if the entity has Prone. If so, it consumes half movement
    and removes the Prone condition.

    Args:
        entity_uuid: The entity this handler is for

    Returns:
        EventHandler that processes TURN_START at EFFECT phase
    """
    def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
        # Only process this entity's turn start
        if event.source_entity_uuid != entity_uuid:
            return None

        entity = Entity.get(entity_uuid)
        if not entity:
            return None

        # Check if prone
        if "Prone" not in entity.active_conditions:
            return None

        # Deduct half movement and remove Prone
        base_movement = entity.action_economy.get_base_value("movement")
        half_movement = base_movement // 2
        entity.action_economy.consume("movement", half_movement)
        entity.remove_condition("Prone")
        return None

    return EventHandler(
        name="Prone Auto-Stand",
        source_entity_uuid=entity_uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.TURN_START,
            event_phase=EventPhase.EFFECT,  # After zone effects (Grease at EXECUTION) apply prone
            event_source_entity_uuid=entity_uuid
        )],
        event_processor=processor
    )


def _setup_weapon_event_handlers(entity: Entity) -> None:
    """Set up event handlers to auto-update attack templates on weapon changes.

    Args:
        entity: The entity to set up handlers for
    """
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


def update_weapon_template(entity: Entity, slot: WeaponSlot) -> None:
    """Update the attack template for a single weapon slot.

    Called when a weapon is equipped or unequipped.

    Args:
        entity: The entity whose template to update
        slot: The weapon slot to update
    """
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


def update_weapon_templates(entity: Entity) -> None:
    """Update attack templates for all weapon slots.

    Args:
        entity: The entity whose templates to update
    """
    for slot in [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF,
                 WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF]:
        update_weapon_template(entity, slot)


def get_available_actions(entity: Entity) -> AvailableActionsResult:
    """Get all available actions for an entity.

    Wrapper around Entity.get_available_actions() for functional API consistency.

    Args:
        entity: The entity to query actions for

    Returns:
        AvailableActionsResult with grouped actions and valid targets
    """
    return entity.get_available_actions()


def execute_action(entity: Entity, template_name: str, target: AvailableTarget,
                    prefer_safe: bool = True) -> Optional[Event]:
    """Execute an action from template + target.

    This is the main execution API that creates an instance and applies it.

    Args:
        entity: The entity executing the action
        template_name: Name of the action template to execute
        target: The target for the action
        prefer_safe: For Move actions, use safe path avoiding hazards when available

    Returns:
        The resulting event, or None if the action failed

    Raises:
        ValueError: If the template is not found or target is invalid
    """
    template = entity.get_action_template(template_name)
    if template is None:
        raise ValueError(f"No template named {template_name}")

    # Create instance with appropriate target
    # prefer_safe is only relevant for position-based movement actions (Move)
    # but passing it generically is harmless — instantiate ignores unknown fields
    # via model_copy(update=...). We only pass it for POSITION types.
    eff_tt = template.effective_target_type
    if eff_tt == TargetType.ENTITY:
        if target.target_uuid is None:
            raise ValueError("ENTITY action requires target_uuid")
        instance = template.instantiate(target_entity_uuid=target.target_uuid)

    elif eff_tt == TargetType.MULTI_ENTITY:
        if target.target_uuid is None:
            raise ValueError("MULTI_ENTITY action requires target_uuid")
        # Extra targets come from target.extra_target_uuids if provided
        extra = target.extra_target_uuids or []
        instance = template.instantiate(
            target_entity_uuid=target.target_uuid,
            extra_target_entity_uuids=extra
        )

    elif eff_tt == TargetType.POSITION_AOE:
        if target.position is None:
            raise ValueError("POSITION_AOE action requires position")
        instance = template.instantiate(end_position=target.position)

    elif eff_tt in (TargetType.POSITION, TargetType.POSITION_PATH, TargetType.POSITION_LOS):
        if target.position is None:
            raise ValueError("POSITION action requires position")
        instance = template.instantiate(end_position=target.position, prefer_safe=prefer_safe)

    elif eff_tt == TargetType.OBJECT:
        if target.target_uuid is None:
            raise ValueError("OBJECT action requires target_uuid")
        instance = template.instantiate(target_entity_uuid=target.target_uuid)

    else:  # SELF
        instance = template.instantiate()

    return instance.apply()


def execute_by_index(
    entity: Entity,
    template_name: str,
    target_index: int,
    extra_target_uuids: Optional[List[str]] = None,
    available: Optional[AvailableActionsResult] = None,
    prefer_safe: bool = True,
) -> Optional[Event]:
    """Execute action by template name and target index.

    This enables "attack 0", "move 3" style commands.

    Args:
        entity: The entity executing the action
        template_name: Name of the action template to execute
        target_index: Index of the target in the valid_targets list
        extra_target_uuids: Additional target UUIDs for multi-target spells (Magic Missile)
        available: Pre-computed available actions (avoids recomputation if caller already has them)

    Returns:
        The resulting event, or None if the action failed

    Raises:
        ValueError: If action or target index not found
    """
    if available is None:
        available = get_available_actions(entity)

    # Find the action info
    action_info: Optional[AvailableActionInfo] = None
    for info in available.all_actions:
        if info.template_name == template_name:
            action_info = info
            break

    if action_info is None:
        raise ValueError(f"Action {template_name} not available")

    # Route item use actions to execute_use_action
    if action_info.is_item_use and action_info.source_item_uuid:
        # Strip __item_<uuid> suffix to get the action's real name
        action_name = template_name.split("__item_")[0] if "__item_" in template_name else template_name
        if action_info.target_type == TargetType.SELF:
            return execute_use_action(entity, action_info.source_item_uuid, action_name)
        target: Optional[AvailableTarget] = None
        for t in action_info.valid_targets:
            if t.index == target_index:
                target = t
                break
        if target is None:
            raise ValueError(f"Target index {target_index} not valid for {template_name}")
        return execute_use_action(entity, action_info.source_item_uuid, action_name, target)

    # Find the target by index
    target = None
    for t in action_info.valid_targets:
        if t.index == target_index:
            target = t
            break

    if target is None:
        raise ValueError(f"Target index {target_index} not valid for {template_name}")

    # For multi-entity actions, attach extra targets to the target object
    if extra_target_uuids:
        # Convert string UUIDs to UUID objects
        target.extra_target_uuids = [UUID(uid) for uid in extra_target_uuids]

    return execute_action(entity, template_name, target, prefer_safe=prefer_safe)


# =============================================================================
# Spell Registration Utilities
# =============================================================================

def register_spell(entity: Entity, spell_class: type, caster_level: int = 1) -> None:
    """Register a spell template on an entity.

    Args:
        entity: The entity to register the spell on
        spell_class: The spell class (e.g., FireBolt, MagicMissile)
        caster_level: The caster's level (for cantrip scaling)
    """
    spell = spell_class(
        source_entity_uuid=entity.uuid,
        caster_level=caster_level,
        template=True
    )
    entity.register_action(spell)


def register_spells_by_name(entity: Entity, spell_names: list, caster_level: int = 1) -> None:
    """Register multiple spells by name from ALL_SPELLS dict.

    Args:
        entity: The entity to register spells on
        spell_names: List of spell names (e.g., ["Fire Bolt", "Magic Missile"])
        caster_level: The caster's level (for cantrip scaling)

    Raises:
        ValueError: If a spell name is not found in ALL_SPELLS
    """

    for name in spell_names:
        if name not in ALL_SPELLS:
            raise ValueError(f"Unknown spell: {name}")
        register_spell(entity, ALL_SPELLS[name], caster_level)


# =============================================================================
# Drop Item (API-only, not registered as template)
# =============================================================================

def execute_drop(entity: Entity, item_uuid: UUID, position: Optional[Tuple[int, int]] = None) -> Optional[Event]:
    """Drop an item from entity's inventory onto the ground.

    Creates a bound Drop action for the specific item and executes it.
    Same pattern as future Use actions — item bound at creation time.

    Args:
        entity: The entity dropping the item
        item_uuid: UUID of the item to drop (must be in entity's inventory)
        position: Grid position to drop at (must be within distance 1).
                  Defaults to entity's position.

    Returns:
        The resulting event, or None if the action failed
    """
    drop_pos = position if position is not None else entity.position
    action = Drop(
        source_entity_uuid=entity.uuid,
        item_uuid=item_uuid,
        end_position=drop_pos,
        template=False
    )
    return action.apply()


# =============================================================================
# Use Item Actions (environment objects / inventory usables)
# =============================================================================

def execute_use_action(
    entity: Entity,
    item_uuid: UUID,
    action_name: str,
    target: Optional[AvailableTarget] = None
) -> Optional[Event]:
    """Execute a use action from a UsableItem.

    Args:
        entity: The entity using the item
        item_uuid: UUID of the UsableItem
        action_name: Name of the action to execute
        target: Optional target for non-SELF actions

    Returns:
        The resulting event, or None if the action failed
    """
    item = BaseBlock.get(item_uuid)
    if not isinstance(item, UsableItem):
        raise ValueError("Item does not support use actions")

    # Strip __item_<uuid> suffix if present (template names have this for uniqueness)
    clean_name = action_name.split("__item_")[0] if "__item_" in action_name else action_name

    templates = item.get_use_actions(entity.uuid)
    template = next((a for a in templates if a.name == clean_name), None)
    if template is None:
        raise ValueError(f"Use action '{action_name}' not found on item")

    # If the action is already a non-template instance (e.g. Torch actions created
    # fresh per get_use_actions() call), use it directly instead of trying to instantiate
    if not template.template:
        instance = template
        if template.target_type == TargetType.ENTITY and target and target.target_uuid:
            instance.target_entity_uuid = target.target_uuid
        elif template.target_type in (TargetType.POSITION, TargetType.POSITION_LOS, TargetType.POSITION_PATH, TargetType.POSITION_AOE) and target and target.position:
            instance.end_position = target.position
        elif template.target_type == TargetType.MULTI_ENTITY and target and target.target_uuid:
            instance.target_entity_uuid = target.target_uuid
            instance.extra_target_entity_uuids = target.extra_target_uuids or []
    # Instantiate based on target type
    elif template.target_type == TargetType.SELF:
        instance = template.instantiate()
    elif template.target_type == TargetType.ENTITY:
        if target is None or target.target_uuid is None:
            raise ValueError("ENTITY use action requires target")
        instance = template.instantiate(target_entity_uuid=target.target_uuid)
    elif template.target_type in (TargetType.POSITION, TargetType.POSITION_LOS, TargetType.POSITION_PATH):
        if target is None or target.position is None:
            raise ValueError("POSITION use action requires position")
        instance = template.instantiate(end_position=target.position)
    elif template.target_type == TargetType.POSITION_AOE:
        if target is None or target.position is None:
            raise ValueError("POSITION_AOE use action requires position")
        instance = template.instantiate(end_position=target.position)
    elif template.target_type == TargetType.MULTI_ENTITY:
        if target is None or target.target_uuid is None:
            raise ValueError("MULTI_ENTITY use action requires target_uuid")
        extra = target.extra_target_uuids or []
        instance = template.instantiate(
            target_entity_uuid=target.target_uuid,
            extra_target_entity_uuids=extra
        )
    else:
        instance = template.instantiate()

    result = instance.apply()

    # Consume charge on successful execution
    if result and not result.canceled:
        charge_cost = template.charge_cost
        item.consume_charge(charge_cost)

    return result


# =============================================================================
# Action Override Helpers (for metamagic, item effects, class abilities)
# =============================================================================

def apply_action_overrides(
    entity: Entity,
    filter_fn: Callable[[BaseAction], bool],
    overrides: Dict[str, Any],
) -> List[UUID]:
    """Set temporary override fields on matching action templates.

    Returns list of modified template UUIDs for cleanup tracking.
    """
    modified: List[UUID] = []
    for template in entity.registered_actions:
        if filter_fn(template):
            for key, value in overrides.items():
                setattr(template, key, value)
            modified.append(template.uuid)
    return modified


def clear_action_overrides(entity: Entity, template_uuids: List[UUID]) -> None:
    """Clear all temporary override fields from specified templates."""
    defaults: Dict[str, Any] = {
        "alt_cost_type": None,
        "alt_extra_costs": [],
        "alt_target_type": None,
        "alt_target_count": None,
        "alt_range": None,
        "alt_skip_slot": False,
    }
    for uid in template_uuids:
        # Find template by UUID in registered_actions
        for template in entity.registered_actions:
            if template.uuid == uid:
                for field, default in defaults.items():
                    if isinstance(default, list):
                        setattr(template, field, list(default))
                    else:
                        setattr(template, field, default)
                break
