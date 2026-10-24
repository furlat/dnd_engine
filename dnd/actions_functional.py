"""Functional API for action setup, discovery, and execution.

The functional layer keeps action construction and execution routes out of
`Entity` while preserving a direct API for callers that do not want to work
with registered templates manually.
"""

from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, Optional, List, Tuple, cast
from uuid import UUID

from dnd.core.base_actions import (
    BaseAction, TargetType, AvailableTarget, AvailableActionInfo,
    AvailableActionsResult, AvailableSelectionPreview, SelectedRoute, prefers_safe_movement_path,
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
from dnd.types.world import MovementMode
from dnd.core.action_types import ActionAffordance, ActionSelection
from dnd.types.discovery import ActorScan
from dnd.core.content.runtime import BehaviorBinding
from dnd.entity import Entity
from dnd.actions import Move, Swim, Dash, Dodge, Disengage, DropConcentration, ShakeAwake, AllyHelp, HelpAttack, Hide, Search, Attack, Jump, Shove, PickUp, Drop, SpellAction, TraverseConnector
from dnd.items.container_traps import DisarmTrap
from dnd.items.locks import ForceLock, LockShut, PickLock, Unlock
from dnd.items.concealment import SearchInside
from dnd.items.shoving import ShoveObject
from dnd.items.water_fixtures import WorkPump
from dnd.summoning.actions import DismissSummon
from dnd.conditions import (
    create_has_attacked_handler,
    create_has_taken_damage_handler,
)
from dnd.blocks.base_item import UsableItem
from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import get_map

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
    source_handlers = EventQueue.get_handlers_by_source_entity(entity.uuid)
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
    for action in tuple(entity.registered_actions):
        entity.unregister_action_by_uuid(action.uuid)
    _remove_standard_action_handlers(entity)

    for action, behavior_id in (
        (Move(source_entity_uuid=entity.uuid, template=True), "action.move"),
        (Move(source_entity_uuid=entity.uuid, template=True, name="Flying Movement", movement_mode=MovementMode.FLYING), "action.move"),
        (Swim(source_entity_uuid=entity.uuid, template=True), "action.swim"),
        (Jump(source_entity_uuid=entity.uuid, template=True), "action.jump"),
        (TraverseConnector(source_entity_uuid=entity.uuid, template=True,
            interaction_affordance=ActionAffordance(surface="world", binding="connector", default_priority=100)),
            "action.traverse_connector"),
        (Dash(source_entity_uuid=entity.uuid, template=True), "action.dash"),
        (Dodge(source_entity_uuid=entity.uuid, template=True), "action.dodge"),
        (
            Disengage(source_entity_uuid=entity.uuid, template=True),
            "action.disengage",
        ),
        (Hide(source_entity_uuid=entity.uuid, template=True), "action.hide"),
        (Search(source_entity_uuid=entity.uuid, template=True), "action.search"),
        (SearchInside(source_entity_uuid=entity.uuid, template=True), "action.environment.search"),
        (ShoveObject(source_entity_uuid=entity.uuid, template=True), "action.environment.shove_object"),
        (WorkPump(source_entity_uuid=entity.uuid, template=True), "action.environment.work_pump"),
        (DisarmTrap(source_entity_uuid=entity.uuid, template=True), "action.environment.trap.disarm"),
        (Unlock(source_entity_uuid=entity.uuid, template=True), "action.environment.lock.unlock"),
        (LockShut(source_entity_uuid=entity.uuid, template=True), "action.environment.lock.lock"),
        (PickLock(source_entity_uuid=entity.uuid, template=True), "action.environment.lock.pick"),
        (ForceLock(source_entity_uuid=entity.uuid, template=True), "action.environment.lock.force"),
        (
            DropConcentration(source_entity_uuid=entity.uuid, template=True),
            "action.drop_concentration",
        ),
        (
            ShakeAwake(source_entity_uuid=entity.uuid, template=True),
            "action.shake_awake",
        ),
        (AllyHelp(source_entity_uuid=entity.uuid,template=True),"action.ally_help"),
        (HelpAttack(source_entity_uuid=entity.uuid,template=True),"action.help_attack"),
        (Shove(source_entity_uuid=entity.uuid, template=True), "action.shove"),
        (PickUp(source_entity_uuid=entity.uuid, template=True,
            interaction_affordance=ActionAffordance(surface="world", default_priority=100)), "action.pick_up"),
        (Drop(source_entity_uuid=entity.uuid, template=True), "action.core.drop"),
        (DismissSummon(source_entity_uuid=entity.uuid, template=True), "action.summon.dismiss"),
    ):
        action.behavior_binding = BehaviorBinding(
            behavior_id=behavior_id,
            provided_by_id=behavior_id,
            runtime_owner_uuid=entity.uuid,
        )
        entity.register_action(action)

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
        current_movement = entity.action_economy.movement_remaining()
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
    entity.add_event_handler(equip_handler)
    entity.add_event_handler(unequip_handler)


def update_weapon_template(entity: Entity, slot: WeaponSlot) -> None:
    """Update the attack template for a single weapon slot.

    Args:
        entity: Entity whose template should be refreshed.
        slot: Weapon slot to inspect.
    """
    template_name = f"Attack_{slot.value}"
    entity.unregister_action(template_name)

    weapon = entity.equipment._get_weapon_by_slot(slot)
    if isinstance(weapon, Weapon) or (weapon is None and slot is WeaponSlot.MELEE_MAIN):
        action = Attack(
            source_entity_uuid=entity.uuid,
            weapon_slot=slot,
            name=template_name,
            template=True,
            behavior_binding=BehaviorBinding(
                behavior_id="action.attack",
                provided_by_id="action.attack",
                runtime_owner_uuid=entity.uuid,
            ),
        )
        entity.register_action(action)


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
    target_filter: str = "enemies",
    include_aoe_preview: bool = True,
) -> AvailableActionsResult:
    """Get all available actions for an entity.

    Wrapper around Entity.get_available_actions() for functional API consistency.

    Args:
        entity: Entity to query.
        legal_only: When true, omit unaffordable rows from discovery.

    Returns:
        Grouped actions and valid targets.
    """
    return entity.get_available_actions(legal_only=legal_only, target_filter=target_filter,
        include_aoe_preview=include_aoe_preview)


def row_selection(
    entity: Entity,
    form: BaseAction,
    primary: AvailableTarget,
    extra_target_uuids: Tuple[UUID, ...] = (),
    extra_target_positions: Tuple[Tuple[int, int], ...] = (),
    *,
    cast_at_level: Optional[int] = None,
    prefer_safe: bool = True,
) -> ActionSelection:
    """The exact selection a discovery row and its chosen targets name, by uuid (plan §14.4b).

    The row's form carries the payment, source item and authored choices; the
    chosen targets, positions, level and route preference complete it.
    """
    own = form.current_selection()
    position_selection = form.get_position_selection()
    if extra_target_positions and (position_selection is None
                                   or position_selection.kind not in ("path", "entity_destination")):
        raise ValueError("This action does not select additional positions")
    target_type = form.effective_target_type
    if target_type in (TargetType.ENTITY, TargetType.CREATURE_OR_OBJECT, TargetType.MULTI_ENTITY, TargetType.OBJECT):
        if primary.target_uuid is None:
            raise ValueError(f"{target_type.value} action requires target_uuid")
        if position_selection is not None and position_selection.kind == "entity_destination" and len(
                extra_target_positions) != 1:
            raise ValueError("Choose exactly one destination")
        target_uuids, positions = (primary.target_uuid, *extra_target_uuids), extra_target_positions
    elif target_type in (TargetType.POSITION_AOE, TargetType.POSITION, TargetType.POSITION_PATH, TargetType.POSITION_LOS):
        if primary.position is None:
            raise ValueError(f"{target_type.value} action requires position")
        target_uuids, positions = (), (primary.position, *extra_target_positions)
    elif form.source_item_uuid is not None and not own.target_uuids:
        # Item uses historically bind their owner explicitly; other SELF actions keep their own selection.
        target_uuids, positions = (entity.uuid,), own.positions
    else:
        target_uuids, positions = own.target_uuids, own.positions
    return replace(own, target_uuids=target_uuids, positions=positions, prefer_safe=prefer_safe,
                   cast_at_level=cast_at_level if cast_at_level is not None else own.cast_at_level)


def _selected_movement_route(
    entity: Entity,
    target: AvailableTarget,
    *,
    prefer_safe: bool,
) -> SelectedRoute | None:
    """Choose an affordable path from the selected discovery target.

    Args:
        entity: Entity paying the movement cost.
        target: Server-disclosed movement target selected by index.
        prefer_safe: Whether an affordable disclosed safe route is preferred.

    Returns:
        The exact path to bind, or `None` when discovery supplied no path.
    """
    movement_remaining = entity.action_economy.movement_remaining()
    if prefers_safe_movement_path(target, movement_remaining, prefer_safe=prefer_safe):
        assert target.safe_path is not None
        assert target.safe_path_cost is not None
        return SelectedRoute(path=tuple(target.safe_path), cost_feet=target.safe_path_cost,
            affordable_endpoint=target.safe_path[-1], policy="safe", is_hazardous=False,
            opportunity_attack_exposures=tuple(target.safe_path_opportunity_attack_exposures))
    if target.path is not None:
        if target.path_cost is None:
            raise ValueError("Disclosed movement route has no native cost")
        return SelectedRoute(path=tuple(target.path), cost_feet=target.path_cost,
            affordable_endpoint=target.path[-1], policy="normal", is_hazardous=target.is_path_hazardous,
            opportunity_attack_exposures=tuple(target.opportunity_attack_exposures))
    return None


def get_extra_position_options(
    entity: Entity, action_info: AvailableActionInfo, target: AvailableTarget,
    extra_target_positions: Optional[List[Tuple[int, int]]] = None,
) -> List[Tuple[int, int]]:
    """Query the next position allocation for one exact discovered action."""
    if target.position is None:
        raise ValueError("Second-point selection requires a first position")
    template = action_info.execution_template
    if template is None:
        raise ValueError("Position options require the original discovery row")
    selection = template.get_position_selection()
    if selection is not None and selection.kind == "entity_destination":
        if target.target_uuid is None:
            return []
        template = performed_action(entity, action_info).with_selection(
            replace(template.current_selection(), target_uuids=(target.target_uuid,)))
    return template.get_valid_extra_target_positions(target.position, extra_target_positions or ())


def allocation_limit(action_info: AvailableActionInfo, template: Optional[BaseAction]) -> Optional[int]:
    """How many targets a selection of this row may name at the template's level.

    An unbounded set (`any_number_of_targets`) counts the row's admitted recipients at any level.
    """
    if template is None or template.any_number_of_targets:
        return action_info.num_projectiles
    return template.get_multi_target_count()


def validated_extra_target_uuids(
    action_info: AvailableActionInfo,
    primary_target: AvailableTarget,
    extra_target_uuids: Optional[List[str]],
    scan: ActorScan,
    template: Optional[BaseAction] = None,
) -> List[UUID]:
    """Validate additional targets against one exact engine discovery row.

    Membership in the row's pool is the shape check; the complete allocation
    then passes the action's own admission on the actor's perceived scan.
    ``template`` is the row's action at the selected level (plan D17): its
    allocation count and rule decide, not the listed level's.
    """
    if not extra_target_uuids:
        return []
    template = template if template is not None else action_info.execution_template
    limit = allocation_limit(action_info, template)
    if action_info.target_type != TargetType.MULTI_ENTITY or limit is None:
        raise ValueError("Additional targets require a multi-entity action")
    if len(extra_target_uuids) + 1 > limit:
        raise ValueError("Additional targets exceed the action allocation count")
    try:
        selected = [UUID(target_uuid) for target_uuid in extra_target_uuids]
    except ValueError as exc:
        raise ValueError("Additional target UUID is invalid") from exc
    # Secondary recipients are any listed target or anything the actor perceives,
    # picked by uuid (plan §14.1, §14.4); the admission below decides legality.
    legal_target_uuids = {target.target_uuid for target in action_info.valid_targets if target.target_uuid is not None}
    legal_target_uuids.update(scan.creatures, scan.objects, (scan.actor_uuid,))
    if any(target_uuid not in legal_target_uuids for target_uuid in selected):
        raise ValueError("Additional target is absent from the discovered target options")
    allocation = [
        *([primary_target.target_uuid] if primary_target.target_uuid is not None else []),
        *selected,
    ]
    if action_info.allow_same_target is False and len(set(allocation)) != len(allocation):
        raise ValueError("Action requires unique target allocation")
    if template is not None:
        reason = template.discovery_error(scan, replace(template.current_selection(), target_uuids=tuple(allocation)))
        if reason is not None:
            raise ValueError(reason)
    return selected


def secondary_candidates(entity: Entity, action_info: AvailableActionInfo, scan: ActorScan) -> List[AvailableTarget]:
    """The row's listed targets, then every other creature and object the actor perceives (one primary's preview)."""
    listed = list(action_info.valid_targets)
    known = {target.target_uuid for target in listed}
    for kind, records in (("creature", scan.creatures), ("object", scan.objects)):
        for identity in sorted(records, key=str):
            if identity in known:
                continue
            block = BaseBlock.get(identity)
            position = records[identity].position
            listed.append(AvailableTarget(index=len(listed), target_uuid=identity, target_kind=kind,
                target_name=block.name if block is not None else None, position=position,
                distance=entity.senses.get_feet_distance(position)))
    return listed


def free_aim_target(action_info: AvailableActionInfo, position: Tuple[int, int]) -> AvailableTarget:
    """One aim a client chose inside a row's free-aim region (plan §14.4); execution validates it."""
    if action_info.position_region is None:
        raise ValueError("This action has no free-aim region")
    return AvailableTarget(index=len(action_info.valid_targets), position=position)


def is_free_aim(action_info: AvailableActionInfo, target: AvailableTarget) -> bool:
    """A position chosen in the row's region rather than one of its listed targets."""
    return (action_info.position_region is not None and target.target_uuid is None
            and target.position is not None and target not in action_info.valid_targets)


def performed_action(entity: Entity, action_info: AvailableActionInfo) -> BaseAction:
    """The action a row's selection names: the registered action its form shows, or the item's own use action.

    A row's form is a discovery view; the executable instance is bound once,
    from this action, by `Entity.perform`.
    """
    form = action_info.execution_template
    if form is None:
        raise ValueError("Execution requires the original discovery row")
    if action_info.is_item_use:
        return form
    registered = entity.get_registered_action(form.registered_template_uuid or form.uuid)
    if registered is None:
        raise ValueError("The row's action is no longer registered")
    return registered


def row_form_at_level(entity: Entity, action_info: AvailableActionInfo, cast_at_level: Optional[int]) -> BaseAction:
    """The row's form at the selected level: one of the row's `cast_levels` (plan D17)."""
    form = action_info.execution_template
    if form is None:
        raise ValueError("Execution requires the original discovery row")
    if cast_at_level is None or cast_at_level == action_info.cast_at_level:
        return form
    if cast_at_level not in action_info.cast_levels:
        raise ValueError("This spell cannot be cast at that level now")
    return performed_action(entity, action_info).with_selection(
        replace(form.current_selection(), cast_at_level=cast_at_level))


def execute_available_action(
    entity: Entity,
    action_info: AvailableActionInfo,
    target: AvailableTarget,
    *,
    extra_target_uuids: Optional[List[str]] = None,
    prefer_safe: bool = True,
    extra_target_positions: Optional[List[Tuple[int, int]]] = None,
    cast_at_level: Optional[int] = None,
) -> Optional[Event]:
    """Perform one exact discovery row's selection, by uuid, without name lookup (plan §14.4b)."""
    form = row_form_at_level(entity, action_info, cast_at_level)
    validated_extras = validated_extra_target_uuids(
        action_info,
        target,
        extra_target_uuids,
        entity.action_scan(subjective=True),
        form,
    ) if extra_target_uuids else []
    if action_info.is_item_use and action_info.source_item_uuid:
        if action_info.target_type == TargetType.SELF:
            return execute_use_action(entity, action_info.source_item_uuid, discovered_template=form)
        return execute_use_action(entity, action_info.source_item_uuid, target=target,
            extra_target_uuids=tuple(validated_extras),
            extra_target_positions=extra_target_positions, discovered_template=form)
    return entity.perform(performed_action(entity, action_info), row_selection(entity, form, target,
        tuple(validated_extras), tuple(extra_target_positions or ()), cast_at_level=cast_at_level,
        prefer_safe=prefer_safe))


def selection_admission_error(
    entity: Entity, action_info: AvailableActionInfo,
    selected_targets: tuple[AvailableTarget, ...] = (),
    extra_target_positions: tuple[Tuple[int, int], ...] = (), *,
    cast_at_level: Optional[int] = None,
) -> Optional[str]:
    """Why this ordered selection cannot be confirmed (None when it can): preview's admission alone."""
    if not action_info.valid_targets and action_info.position_region is None:
        return action_info.availability_status.value.replace("_", " ")
    if not selected_targets:
        return "Choose a target" if action_info.valid_targets else "Choose a point"
    return _admitted_selection(entity, action_info, selected_targets, extra_target_positions, cast_at_level).reason


@dataclass(frozen=True)
class _SelectionAdmission:
    """A non-empty ordered selection bound to its row template, and why it cannot be confirmed.

    A malformed selection has a reason and no binding.
    """

    reason: Optional[str]
    template: Optional[BaseAction] = None
    bound: Optional[BaseAction] = None
    scan: Optional[ActorScan] = None


def _admitted_selection(
    entity: Entity, action_info: AvailableActionInfo, selected_targets: tuple[AvailableTarget, ...],
    extra_target_positions: tuple[Tuple[int, int], ...], cast_at_level: Optional[int],
) -> _SelectionAdmission:
    """The row form bound to a non-empty ordered selection, with its admission reason."""
    primary = selected_targets[0]
    if primary not in action_info.valid_targets and not is_free_aim(action_info, primary):
        return _SelectionAdmission("Target is no longer admitted")
    try:
        template = row_form_at_level(entity, action_info, cast_at_level)
        scan = entity.action_scan(subjective=True)
        extras = validated_extra_target_uuids(action_info, primary,
            [str(target.target_uuid) for target in selected_targets[1:]], scan, template)
        if action_info.target_type is not TargetType.MULTI_ENTITY and len(selected_targets) != 1:
            raise ValueError("This action selects one target")
        position_selection = template.get_position_selection()
        if (position_selection is not None and position_selection.kind == "entity_destination"
                and len(extra_target_positions) > 1):
            raise ValueError("Choose exactly one destination")
        if position_selection is not None and position_selection.kind == "entity_destination" and not extra_target_positions:
            # A creature chosen before its destination: the selection is not complete yet.
            selection = replace(template.current_selection(),
                                target_uuids=(primary.target_uuid,) if primary.target_uuid is not None else ())
        else:
            selection = row_selection(entity, template, primary, tuple(extras), extra_target_positions,
                                      cast_at_level=cast_at_level)
        # The instance Command would execute, admitted through the one admission path (plan §14.3b).
        bound = performed_action(entity, action_info).with_selection(selection)
        reason = bound.requirements_error(scan, selection) or bound.handler_admission_error(subjective=True)
        if (reason is None and action_info.target_type is TargetType.POSITION_AOE and template.aoe_require_targets
                and is_free_aim(action_info, primary) and not entity.preview_aoe_target(
                    template, primary, include_dead=action_info._aoe_include_dead).affected_entity_uuids):
            # An area that requires a creature admits a free aim only where its area holds one, as discovery lists.
            reason = "No creature in the area"
    except ValueError as error:
        return _SelectionAdmission(str(error))
    return _SelectionAdmission(reason, template, bound, scan)


def preview_available_selection(
    entity: Entity, action_info: AvailableActionInfo,
    selected_targets: tuple[AvailableTarget, ...] = (),
    extra_target_positions: tuple[Tuple[int, int], ...] = (), *,
    prefer_safe: bool = True,
    include_aoe_effects: bool = True,
    cast_at_level: Optional[int] = None,
) -> AvailableSelectionPreview:
    """Inspect an ordered discovery prefix without instantiation or events.

    The retained row is the authority. Already admitted destinations need no
    second discovery/preflight; compound selections use shared pure predicates.
    Execution still performs ordinary native validation at submission.
    """
    if not action_info.valid_targets and action_info.position_region is None:
        return AvailableSelectionPreview(can_confirm=False,
            reason=action_info.availability_status.value.replace("_", " "))
    if not selected_targets:
        return AvailableSelectionPreview(can_confirm=False,
            reason="Choose a target" if action_info.valid_targets else "Choose a point",
            next_targets=tuple(action_info.valid_targets))
    admission = _admitted_selection(entity, action_info, selected_targets, extra_target_positions, cast_at_level)
    if admission.bound is None or admission.template is None or admission.scan is None:
        return AvailableSelectionPreview(can_confirm=False, reason=admission.reason)
    template, bound, scan, reason = admission.template, admission.bound, admission.scan, admission.reason
    primary = selected_targets[0]
    selection = template.get_position_selection()
    try:
        pool = secondary_candidates(entity, action_info, scan)
        next_targets: list[AvailableTarget] = []
        limit = allocation_limit(action_info, template)
        if action_info.target_type is TargetType.MULTI_ENTITY and len(selected_targets) < (limit or 1):
            for candidate in pool:
                try:
                    validated_extra_target_uuids(action_info, primary,
                        [str(target.target_uuid) for target in (*selected_targets[1:], candidate)], scan, template)
                except ValueError:
                    continue
                next_targets.append(candidate)
        next_positions = (tuple(get_extra_position_options(entity, action_info, primary,
                           list(extra_target_positions)))
                          if selection is not None and selection.kind in ("path", "entity_destination") else ())
        identities = (tuple(bound.get_all_targets())
            if primary.target_uuid is not None and action_info.target_type is not TargetType.POSITION_AOE
            else ())
        geometry = bound.get_selection_geometry()
        area_preview = "not_applicable"
        affected_positions = tuple(primary.affected_positions or ())
        affected_entity_uuids: tuple[UUID, ...] = ()
        affected_entity_names: tuple[str, ...] = ()
        if action_info.target_type is TargetType.POSITION_AOE:
            area_preview = "deferred"
            affected_positions = ()
            if include_aoe_effects:
                area_target = (primary if primary.affected_positions is not None
                    else entity.preview_aoe_target(template, primary,
                        include_dead=action_info._aoe_include_dead))
                area_preview = "computed"
                affected_positions = tuple(area_target.affected_positions or ())
                affected_entity_uuids = tuple(area_target.affected_entity_uuids or ())
                affected_entity_names = tuple(area_target.affected_entity_names or ())
                origin=bound.get_effect_origin_for_preview()
                if origin is not None:
                    included=[index for index,identity in enumerate(affected_entity_uuids)
                        if EventQueue.preview_application_admitted(origin,entity.uuid,identity)]
                    affected_entity_uuids=tuple(affected_entity_uuids[index] for index in included)
                    affected_entity_names=tuple(affected_entity_names[index] for index in included if index<len(affected_entity_names))
                if template.aoe_shape is not None and primary.position is not None:
                    geometry = template.aoe_shape.presentation_geometry(primary.position, entity.position)
        return AvailableSelectionPreview(can_confirm=reason is None, reason=reason,
            selected_route=(_selected_movement_route(entity, primary, prefer_safe=prefer_safe)
                if isinstance(template, Move) else None),
            effective_target_uuids=identities, next_targets=tuple(next_targets),
            next_positions=next_positions, geometry=geometry,
            affected_positions=affected_positions, area_preview=area_preview,
            affected_entity_uuids=affected_entity_uuids,
            affected_entity_names=affected_entity_names)
    except ValueError as error:
        return AvailableSelectionPreview(can_confirm=False, reason=str(error))


def execute_by_index(
    entity: Entity,
    template_name: str,
    target_index: int,
    extra_target_uuids: Optional[List[str]] = None,
    available: Optional[AvailableActionsResult] = None,
    prefer_safe: bool = True,
    *,
    extra_target_positions: Optional[List[Tuple[int, int]]] = None,
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
        extra_target_positions=extra_target_positions,
    )


def register_spell(
    entity: Entity,
    spell_class: type[SpellAction],
    caster_level: int = 1,
    *,
    spellcasting_source_id: Optional[UUID] = None,
) -> None:
    """Register a spell template on an entity.

    Args:
        entity: Entity receiving the spell template.
        spell_class: Spell action class to instantiate as a template.
        caster_level: Caster level used for scaling spell templates.
        spellcasting_source_id: Exact registered source owning this spell.
            None preserves the legacy default spellcasting ability.
    """
    spell = spell_class(
        source_entity_uuid=entity.uuid,
        caster_level=caster_level,
        spellcasting_source_id=spellcasting_source_id,
        template=True
    )
    entity.register_action(spell)


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
    return entity.perform(action, action.current_selection())


def execute_use_action(
    entity: Entity,
    item_uuid: UUID,
    action_name: Optional[str] = None,
    target: Optional[AvailableTarget] = None,
    *,
    extra_target_uuids: Tuple[UUID, ...] = (),
    extra_target_positions: Optional[List[Tuple[int, int]]] = None,
    discovered_template: Optional[BaseAction] = None,
) -> Optional[Event]:
    """Execute a use action from a UsableItem.

    Args:
        entity: Entity using the item.
        item_uuid: UUID of the usable item.
        action_name: The item's use action name, when no discovered row form is given.
        target: Optional target for non-self use actions.

    Returns:
        Resulting event, or `None` if execution failed.

    Raises:
        ValueError: If the item is not usable or the named use action is absent.
    """
    item = BaseBlock.get(item_uuid)
    if not isinstance(item, UsableItem):
        raise ValueError("Item does not support use actions")

    grid = get_map()
    if grid.get_object_placement(item_uuid) is not None and grid.manual_object_contact(entity.uuid, item_uuid) is None:
        raise ValueError("Item is out of reach")

    clean_name = action_name.split("__item_")[0] if action_name is not None else None
    offered = () if item.hides_actions_from(entity.faction, entity.uuid) else item.get_use_actions(entity.uuid)
    template = discovered_template or next(
        (action for action in offered if action.get_discovery_template_name() == clean_name), None)
    if template is None:
        raise ValueError(f"Use action '{action_name}' not found on item")
    if template.source_item_uuid != item_uuid or template.source_entity_uuid != entity.uuid:
        raise ValueError("Discovered item action belongs to a different source")

    charge_cost = template.charge_cost
    if item.charges != -1 and item.charges < charge_cost:
        raise ValueError(f"Use action '{template.name}' requires {charge_cost} charges")

    chosen = target or AvailableTarget(index=0, target_uuid=entity.uuid)
    return entity.perform(template, row_selection(entity, template, chosen, extra_target_uuids,
        tuple(extra_target_positions or ())))


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
