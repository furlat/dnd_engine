"""Functional API for action setup, discovery, and execution.

The functional layer keeps action construction and execution routes out of
`Entity` while preserving a direct API for callers that do not want to work
with registered templates manually.
"""

from typing import Any, Callable, Dict, Optional, List, Tuple, cast
from uuid import UUID, uuid4

from dnd.core.base_actions import (
    BaseAction, TargetType, AvailableTarget, AvailableActionInfo,
    AvailableActionsResult, SPELL_SLOT_TEMPLATE_SEPARATOR,
)
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.blocks.equipment import Weapon, WeaponEquipEvent, WeaponUnequipEvent
from dnd.core.equipment_types import WeaponSlot
from dnd.entity import Entity
from dnd.actions import Move, Swim, Dash, Dodge, Disengage, DropConcentration, ShakeAwake, Hide, Attack, Jump, Shove, PickUp, AttackObject, Drop
from dnd.conditions import (
    create_has_attacked_handler,
    create_has_taken_damage_handler,
)
from dnd.spells import ALL_SPELLS
from dnd.blocks.base_item import UsableItem, consume_item_charge_before_action_completion
from dnd.core.base_block import BaseBlock

STANDARD_ENTITY_HANDLER_NAMES = {
    "HasAttacked Tracker",
    "HasTakenDamage Tracker",
    "Prone Auto-Stand",
}


def _standard_weapon_handler_names(entity_uuid: UUID) -> set[str]:
    """Return direct weapon-template handler names for an entity."""
    return {
        f"WeaponEquipHandler_{entity_uuid}",
        f"WeaponUnequipHandler_{entity_uuid}",
    }


def _remove_standard_action_handlers(entity: Entity) -> None:
    """Remove handlers installed by prior standard-action setup runs.

    Args:
        entity: Entity whose standard handlers should be replaced.
    """
    for handler_name in STANDARD_ENTITY_HANDLER_NAMES:
        for handler in list(entity.get_event_handlers_by_name(handler_name)):
            entity.remove_event_handler(handler)

    weapon_handler_names = _standard_weapon_handler_names(entity.uuid)
    source_handlers = list(EventQueue._event_handlers_by_source_entity_uuid.get(entity.uuid, []))
    for handler in source_handlers:
        if handler.name in weapon_handler_names:
            if handler.uuid in entity.event_handlers:
                entity.remove_event_handler(handler)
            else:
                EventQueue.remove_event_handler(handler)


def setup_standard_actions(entity: Entity) -> None:
    """Register standard D&D 5e actions for an entity.

    Registers movement, self-targeting combat options, object interactions,
    weapon attack templates, and the handlers that keep those templates and
    combat-state markers current. Prone auto-stand is registered here; voluntary
    Stand Up and Drop Prone are not standard templates in this engine.

    Args:
        entity: Entity that receives standard action templates and handlers.
    """
    entity.registered_actions = []
    _remove_standard_action_handlers(entity)

    entity.register_action(Move(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Swim(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Jump(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Dash(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Dodge(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Disengage(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Hide(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(DropConcentration(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(ShakeAwake(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Shove(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(PickUp(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(AttackObject(source_entity_uuid=entity.uuid, template=True))

    update_weapon_templates(entity)

    _setup_weapon_event_handlers(entity)

    entity.add_event_handler(create_has_attacked_handler(entity.uuid))
    entity.add_event_handler(create_has_taken_damage_handler(entity.uuid))
    entity.add_event_handler(_create_prone_auto_stand_handler(entity.uuid))


def _create_prone_auto_stand_handler(entity_uuid: UUID) -> EventHandler:
    """Create the turn-start handler that removes Prone by spending movement.

    The handler listens at TURN_START/EFFECT so zone effects that apply Prone
    earlier in the same turn can be observed before auto-stand runs.

    Args:
        entity_uuid: Entity that owns the handler.

    Returns:
        Event handler that processes the entity's own turn start.
    """
    def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
        if event.source_entity_uuid != entity_uuid:
            return None

        entity = Entity.get(entity_uuid)
        if not entity:
            return None

        if "Prone" not in entity.active_conditions:
            return None

        base_movement = entity.action_economy.get_base_value("movement")
        half_movement = base_movement // 2
        current_movement = entity.action_economy.movement.normalized_score
        if current_movement < half_movement:
            return None
        entity.action_economy.consume("movement", half_movement)
        entity.remove_condition("Prone")
        return None

    return EventHandler(
        name="Prone Auto-Stand",
        source_entity_uuid=entity_uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.TURN_START,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=entity_uuid
        )],
        event_processor=processor
    )


def _setup_weapon_event_handlers(entity: Entity) -> None:
    """Set up event handlers to auto-update attack templates on weapon changes.

    Args:
        entity: Entity whose equipped weapons drive attack templates.
    """
    entity_uuid = entity.uuid

    def _on_weapon_equip(event: Event, _source: UUID) -> Optional[Event]:
        """Refresh the attack template for an equipped weapon slot."""
        if event.source_entity_uuid == entity_uuid:
            if isinstance(event, WeaponEquipEvent) and isinstance(event.slot, WeaponSlot):
                ent = Entity.get(entity_uuid)
                if ent:
                    update_weapon_template(ent, event.slot)
        return event

    def _on_weapon_unequip(event: Event, _source: UUID) -> Optional[Event]:
        """Refresh the attack template for an unequipped weapon slot."""
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

    Args:
        entity: Entity whose template should be refreshed.
        slot: Weapon slot to inspect.
    """
    template_name = f"Attack_{slot.value}"
    entity.unregister_action(template_name)

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
        entity: Entity whose weapon attack templates should be refreshed.
    """
    for slot in [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF,
                 WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF]:
        update_weapon_template(entity, slot)


def get_available_actions(
    entity: Entity,
    *,
    legal_only: bool = False,
) -> AvailableActionsResult:
    """Get all available actions for an entity.

    Wrapper around Entity.get_available_actions() for functional API consistency.

    Args:
        entity: Entity to query.
        legal_only: When true, omit unaffordable rows from discovery.

    Returns:
        Grouped actions and valid targets.
    """
    return entity.get_available_actions(legal_only=legal_only)


def _parse_spell_variant_template_name(template_name: str) -> Tuple[str, Optional[int]]:
    """Split a generated spell-variant execution name.

    Args:
        template_name: Action name from discovery.

    Returns:
        Base template name and optional cast level.
    """
    if SPELL_SLOT_TEMPLATE_SEPARATOR not in template_name:
        return template_name, None
    base_name, _, slot_level_text = template_name.rpartition(SPELL_SLOT_TEMPLATE_SEPARATOR)
    if not base_name:
        return template_name, None
    try:
        slot_level = int(slot_level_text)
    except ValueError:
        return template_name, None
    if slot_level < 1 or slot_level > 9:
        return template_name, None
    return base_name, slot_level


def _resolve_executable_template(entity: Entity, template_name: str) -> BaseAction:
    """Resolve a registered template or generated discovery variant.

    Args:
        entity: Acting entity.
        template_name: Action name from discovery.

    Returns:
        Registered template or generated non-template discovery variant.

    Raises:
        ValueError: If no matching template can be resolved.
    """
    base_name, cast_at_level = _parse_spell_variant_template_name(template_name)
    template = entity.get_action_template(base_name)
    if template is not None:
        if cast_at_level is None:
            return template
        create_variant = getattr(template, "_create_variant", None)
        if not template.is_spell or not callable(create_variant):
            raise ValueError(f"Action {template_name} is not a spell variant")
        variant_factory = cast(Callable[..., BaseAction], create_variant)
        return variant_factory(cast_at_level=cast_at_level)

    for registered_template in entity.registered_actions:
        for variant in registered_template.get_discovery_variants(entity):
            if variant.get_discovery_template_name() == template_name:
                return variant
    raise ValueError(f"No template named {template_name}")


def _bind_executable_action(action: BaseAction, **overrides) -> BaseAction:
    """Bind target fields onto a template or generated variant.

    Args:
        action: Registered template or non-template generated variant.
        **overrides: Target fields to set on the executable copy.

    Returns:
        Executable action instance.
    """
    if action.template:
        return action.instantiate(**overrides)

    update_dict: dict = {
        "uuid": uuid4(),
        "template": False,
        "use_register": False,
    }
    update_dict.update(overrides)
    return action.model_copy(deep=True, update=update_dict)


def _disclosed_movement_path(
    entity: Entity,
    target: AvailableTarget,
    *,
    prefer_safe: bool,
) -> Optional[List[Tuple[int, int]]]:
    """Choose an affordable path from the selected discovery target.

    Args:
        entity: Entity paying the movement cost.
        target: Server-disclosed movement target selected by index.
        prefer_safe: Whether an affordable disclosed safe route is preferred.

    Returns:
        The exact path to bind, or `None` when discovery supplied no path.
    """
    movement_remaining = entity.action_economy.movement.normalized_score
    if (
        prefer_safe
        and target.safe_path is not None
        and target.safe_path_cost is not None
        and target.safe_path_cost <= movement_remaining
    ):
        return list(target.safe_path)
    if target.path is not None:
        return list(target.path)
    return None


def execute_action(entity: Entity, template_name: str, target: AvailableTarget,
                    prefer_safe: bool = True) -> Optional[Event]:
    """Execute an action from template + target.

    Creates a one-shot instance from the selected template, binds the target
    fields required by that template's effective target type, and applies it.

    Args:
        entity: Acting entity.
        template_name: Registered template name.
        target: Selected target from discovery.
        prefer_safe: Whether movement actions prefer a discovered safe path.

    Returns:
        Resulting event, or `None` if execution failed.

    Raises:
        ValueError: If the template is not found or the target is invalid.
    """
    template = _resolve_executable_template(entity, template_name)
    return _execute_bound_action(entity, template, target, prefer_safe=prefer_safe)


def _execute_bound_action(
    entity: Entity,
    template: BaseAction,
    target: AvailableTarget,
    *,
    prefer_safe: bool,
) -> Optional[Event]:
    """Execute one exact discovered action object against an authorized target."""

    eff_tt = template.effective_target_type
    if eff_tt == TargetType.ENTITY:
        if target.target_uuid is None:
            raise ValueError("ENTITY action requires target_uuid")
        instance = _bind_executable_action(template, target_entity_uuid=target.target_uuid)

    elif eff_tt == TargetType.MULTI_ENTITY:
        if target.target_uuid is None:
            raise ValueError("MULTI_ENTITY action requires target_uuid")
        extra = target.extra_target_uuids or []
        instance = _bind_executable_action(
            template,
            target_entity_uuid=target.target_uuid,
            extra_target_entity_uuids=extra
        )

    elif eff_tt == TargetType.POSITION_AOE:
        if target.position is None:
            raise ValueError("POSITION_AOE action requires position")
        instance = _bind_executable_action(template, end_position=target.position)

    elif eff_tt in (TargetType.POSITION, TargetType.POSITION_PATH, TargetType.POSITION_LOS):
        if target.position is None:
            raise ValueError("POSITION action requires position")
        position_overrides: dict[str, object] = {
            "end_position": target.position,
            "prefer_safe": prefer_safe,
        }
        if isinstance(template, Move):
            disclosed_path = _disclosed_movement_path(
                entity,
                target,
                prefer_safe=prefer_safe,
            )
            if disclosed_path is not None:
                position_overrides["path"] = disclosed_path
        instance = _bind_executable_action(template, **position_overrides)

    elif eff_tt == TargetType.OBJECT:
        if target.target_uuid is None:
            raise ValueError("OBJECT action requires target_uuid")
        instance = _bind_executable_action(template, target_entity_uuid=target.target_uuid)

    else:
        instance = _bind_executable_action(template)

    return instance.apply()


def _validated_extra_target_uuids(
    action_info: AvailableActionInfo,
    primary_target: AvailableTarget,
    extra_target_uuids: Optional[List[str]],
) -> List[UUID]:
    """Validate additional targets against one exact engine discovery row."""
    if not extra_target_uuids:
        return []
    if action_info.target_type != TargetType.MULTI_ENTITY or action_info.num_projectiles is None:
        raise ValueError("Additional targets require a multi-entity action")
    if len(extra_target_uuids) + 1 > action_info.num_projectiles:
        raise ValueError("Additional targets exceed the action allocation count")
    try:
        selected = [UUID(target_uuid) for target_uuid in extra_target_uuids]
    except ValueError as exc:
        raise ValueError("Additional target UUID is invalid") from exc
    legal_target_uuids = {
        target.target_uuid
        for target in action_info.valid_targets
        if target.target_uuid is not None
    }
    if any(target_uuid not in legal_target_uuids for target_uuid in selected):
        raise ValueError("Additional target is absent from the discovered target options")
    allocation = [
        *([primary_target.target_uuid] if primary_target.target_uuid is not None else []),
        *selected,
    ]
    if action_info.allow_same_target is False and len(set(allocation)) != len(allocation):
        raise ValueError("Action requires unique target allocation")
    return selected


def execute_available_action(
    entity: Entity,
    action_info: AvailableActionInfo,
    target: AvailableTarget,
    *,
    extra_target_uuids: Optional[List[str]] = None,
    prefer_safe: bool = True,
) -> Optional[Event]:
    """Execute one exact discovery row without name lookup or target mutation."""
    validated_extras = _validated_extra_target_uuids(
        action_info,
        target,
        extra_target_uuids,
    )
    bound_target = target.model_copy(
        deep=True,
        update={"extra_target_uuids": validated_extras or None},
    )
    if action_info.is_item_use and action_info.source_item_uuid:
        action_name = (
            action_info.template_name.split("__item_")[0]
            if "__item_" in action_info.template_name
            else action_info.template_name
        )
        if action_info.target_type == TargetType.SELF:
            return execute_use_action(entity, action_info.source_item_uuid, action_name)
        return execute_use_action(
            entity,
            action_info.source_item_uuid,
            action_name,
            bound_target,
        )
    template = action_info.execution_template
    if template is None:
        template = _resolve_executable_template(entity, action_info.template_name)
    return _execute_bound_action(
        entity,
        template,
        bound_target,
        prefer_safe=prefer_safe,
    )


def execute_by_index(
    entity: Entity,
    template_name: str,
    target_index: int,
    extra_target_uuids: Optional[List[str]] = None,
    available: Optional[AvailableActionsResult] = None,
    prefer_safe: bool = True,
) -> Optional[Event]:
    """Execute action by template name and target index.

    Enables controller commands such as "attack 0" and "move 3". Item-use
    templates are routed to `execute_use_action()`.

    Args:
        entity: Acting entity.
        template_name: Template name from discovery.
        target_index: Index inside the selected action's `valid_targets`.
        extra_target_uuids: Additional UUID strings for multi-entity actions.
        available: Optional precomputed discovery result.
        prefer_safe: Whether movement actions prefer a discovered safe path.

    Returns:
        Resulting event, or `None` if execution failed.

    Raises:
        ValueError: If the action or target index is unavailable.
    """
    if available is None:
        available = get_available_actions(entity)

    action_info: Optional[AvailableActionInfo] = None
    for info in available.all_actions:
        if info.template_name == template_name:
            action_info = info
            break

    if action_info is None:
        raise ValueError(f"Action {template_name} not available")

    target = None
    for t in action_info.valid_targets:
        if t.index == target_index:
            target = t
            break

    if target is None:
        raise ValueError(f"Target index {target_index} not valid for {template_name}")

    return execute_available_action(
        entity,
        action_info,
        target,
        extra_target_uuids=extra_target_uuids,
        prefer_safe=prefer_safe,
    )


def register_spell(entity: Entity, spell_class: type, caster_level: int = 1) -> None:
    """Register a spell template on an entity.

    Args:
        entity: Entity receiving the spell template.
        spell_class: Spell action class to instantiate as a template.
        caster_level: Caster level used for scaling spell templates.
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
        entity: Entity receiving spell templates.
        spell_names: Spell names present in `ALL_SPELLS`.
        caster_level: Caster level used for scaling spell templates.

    Raises:
        ValueError: If a spell name is unknown.
    """

    for name in spell_names:
        if name not in ALL_SPELLS:
            raise ValueError(f"Unknown spell: {name}")
        register_spell(entity, ALL_SPELLS[name], caster_level)


def execute_drop(entity: Entity, item_uuid: UUID, position: Optional[Tuple[int, int]] = None) -> Optional[Event]:
    """Drop an item from entity's inventory onto the ground.

    Creates a bound Drop action for the specific item and executes it.
    Same pattern as future Use actions: item bound at creation time.

    Args:
        entity: Entity dropping the item.
        item_uuid: UUID of the item to drop from inventory.
        position: Grid position to drop at (must be within distance 1).
            Defaults to the entity's current position.

    Returns:
        Resulting event, or `None` if execution failed.
    """
    drop_pos = position if position is not None else entity.position
    action = Drop(
        source_entity_uuid=entity.uuid,
        item_uuid=item_uuid,
        end_position=drop_pos,
        template=False
    )
    return action.apply()


def execute_use_action(
    entity: Entity,
    item_uuid: UUID,
    action_name: str,
    target: Optional[AvailableTarget] = None
) -> Optional[Event]:
    """Execute a use action from a UsableItem.

    Args:
        entity: Entity using the item.
        item_uuid: UUID of the usable item.
        action_name: Use action name, with or without the discovery suffix.
        target: Optional target for non-self use actions.

    Returns:
        Resulting event, or `None` if execution failed.

    Raises:
        ValueError: If the item is not usable or the named use action is absent.
    """
    item = BaseBlock.get(item_uuid)
    if not isinstance(item, UsableItem):
        raise ValueError("Item does not support use actions")

    clean_name = action_name.split("__item_")[0] if "__item_" in action_name else action_name

    templates = item.get_use_actions(entity.uuid)
    template = next(
        (
            action
            for action in templates
            if action.get_discovery_template_name() == clean_name
        ),
        None,
    )
    if template is None:
        raise ValueError(f"Use action '{action_name}' not found on item")

    charge_cost = template.charge_cost
    if item.charges != -1 and item.charges < charge_cost:
        raise ValueError(f"Use action '{action_name}' requires {charge_cost} charges")

    if not template.template:
        instance = template
        if template.target_type == TargetType.ENTITY and target and target.target_uuid:
            instance.target_entity_uuid = target.target_uuid
        elif template.target_type in (TargetType.POSITION, TargetType.POSITION_LOS, TargetType.POSITION_PATH, TargetType.POSITION_AOE) and target and target.position:
            instance.end_position = target.position
        elif template.target_type == TargetType.MULTI_ENTITY and target and target.target_uuid:
            instance.target_entity_uuid = target.target_uuid
            instance.extra_target_entity_uuids = target.extra_target_uuids or []
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

    EventQueue.add_pre_completion_callback(consume_item_charge_before_action_completion)
    result = instance.apply()

    return result


def apply_action_overrides(
    entity: Entity,
    filter_fn: Callable[[BaseAction], bool],
    overrides: Dict[str, Any],
) -> List[UUID]:
    """Set temporary override fields on matching action templates.

    Args:
        entity: Entity whose registered templates are inspected.
        filter_fn: Predicate selecting templates to mutate.
        overrides: Field/value pairs to assign on selected templates.

    Returns:
        UUIDs of modified templates for later cleanup.
    """
    modified: List[UUID] = []
    for template in entity.registered_actions:
        if filter_fn(template):
            for key, value in overrides.items():
                setattr(template, key, value)
            modified.append(template.uuid)
    return modified


def clear_action_overrides(entity: Entity, template_uuids: List[UUID]) -> None:
    """Clear temporary override fields from selected templates.

    Args:
        entity: Entity whose registered templates are inspected.
        template_uuids: Template UUIDs returned by `apply_action_overrides()`.
    """
    defaults: Dict[str, Any] = {
        "alt_cost_type": None,
        "alt_extra_costs": [],
        "alt_target_type": None,
        "alt_target_count": None,
        "alt_range": None,
        "alt_skip_slot": False,
    }
    for uid in template_uuids:
        for template in entity.registered_actions:
            if template.uuid == uid:
                for field, default in defaults.items():
                    if field not in template.__class__.model_fields:
                        continue
                    if isinstance(default, list):
                        setattr(template, field, list(default))
                    else:
                        setattr(template, field, default)
                break
