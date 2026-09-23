"""Shared native physical damage and optional poison rider for trap owners."""

from uuid import UUID

from dnd.actions import commit_forced_movement
from dnd.conditions import Poisoned
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType
from dnd.core.content.identities import ContentRef
from dnd.core.dice import AttackOutcome
from dnd.core.events import Damage, Event, EventPhase, EventQueue, EventType, ForcedMovementEvent, SpatialChangeEvent
from dnd.core.gridmap import get_map
from dnd.core.saving_throw_types import SavingThrowContext, SavingThrowEffectTag
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.types.traps import TrapPayload
from dnd.types.world import OccupancyLayer


def retreat_after_saved_entry(entity: Entity, *, parent_event: Event) -> ForcedMovementEvent | None:
    """Avoid an entry-triggered mechanism by returning to the actual vacated cell."""
    entry: Event | None = parent_event
    while entry is not None:
        if (isinstance(entry, SpatialChangeEvent) and entry.event_type is EventType.SPATIAL_ENTITY_ENTERED
                and entry.entity_uuid == entity.uuid):
            break
        entry = entry.get_parent_event()
    if not isinstance(entry, SpatialChangeEvent) or entry.position != entity.position:
        return None
    destination = entry.old_position
    if (destination is None or destination == entity.position or entity.occupancy_layer is not OccupancyLayer.GROUND
            or not get_map().can_transition(entity.position, destination, entity.uuid)):
        return None
    event = EventQueue.publish_declaration(ForcedMovementEvent(
        source_entity_uuid=parent_event.source_entity_uuid, target_entity_uuid=entity.uuid,
        source_entity_name=parent_event.source_entity_name, target_entity_name=entity.name,
        start_position=entity.position, end_position=destination,
        direction=(destination[0]-entity.position[0], destination[1]-entity.position[1]),
        intended_distance=5, actual_distance=5, cause="saved_entry_avoidance",
        parent_event=parent_event.uuid, use_register=False))
    for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
        if event.canceled:
            return event
        event = event.phase_to(phase)
    return commit_forced_movement(entity, event, parent_event=parent_event)


def apply_trap_payload(entity: Entity, payload: TrapPayload, *, source_uuid: UUID,
                       content_ref: ContentRef, name: str, parent_event: Event,
                       half_damage: bool = False, apply_condition: bool = True) -> None:
    """Apply authored consequences after the owning mechanism resolves avoidance."""
    for component in payload.damages:
        bonus = ModifiableValue.create(source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
            base_value=0, value_name="Trap damage")
        damage = Damage(name=name, source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
            damage_dice=component.dice_sides, dice_numbers=component.dice_count,
            damage_bonus=bonus, damage_type=component.damage_type)
        roll = damage.get_dice(AttackOutcome.HIT).roll
        amount = roll.total // 2 if half_damage else roll.total
        if amount > 0:
            entity.receive_damage(amount, component.damage_type, source_uuid,
                damage_rolls=[roll], damages=[damage], parent_event=parent_event.uuid,
                effect_id=content_ref.identity_key)
    condition = payload.condition
    if not apply_condition or condition is None:
        return
    request = entity.create_saving_throw_request(target_entity_uuid=entity.uuid,
        ability_name=condition.save_ability, dc=condition.save_dc, parent_event=parent_event.uuid,
        saving_throw_context=SavingThrowContext(cause_id=content_ref.content_id,
            effect_id=f"{content_ref.content_id}.poisoned_save", condition_id=condition.condition_id,
            is_magical=False, effect_tags=(SavingThrowEffectTag.POISON,)))
    _, _, resisted = entity.saving_throw(request)
    if not resisted:
        entity.add_condition(Poisoned(source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
            duration=Duration(duration=condition.duration_rounds, duration_type=DurationType.ROUNDS,
                              source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid)), parent_event=parent_event)
