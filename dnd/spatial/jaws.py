"""A ground-contact jaw owns one capture independently of overlapping effects."""

from uuid import UUID, uuid4

from pydantic import Field

from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import ConditionCategory, DurationType, HazardFilter
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.creature_types import DamageType
from dnd.core.events import (
    Event, EventHandler, EventPhase, EventQueue, EventType, MechanismActivationEvent,
    SpatialChangeEvent, Trigger,
)
from dnd.core.gridmap import get_map
from dnd.core.saving_throw_types import SavingThrowContext
from dnd.entity import Entity
from dnd.spatial.area_conditions import SpatialCondition
from dnd.spatial.restraints import EscapeSpatialRestraintAction, SpatialRestraintSource
from dnd.spatial.trap_payloads import apply_trap_payload, retreat_after_saved_entry
from dnd.types.senses import PerceivedSpatialEffect
from dnd.types.abilities import SkillName
from dnd.types.spatial_effects import SpatialEffectChangeOperation, SpatialEffectLayer, SpatialEffectOccupancyPolicy
from dnd.types.traps import TrapDamage, TrapPayload, TrapState
from dnd.types.world import OccupancyLayer


JAW_TRAP_CONTENT_REF = ContentRef(
    pack_id="content.neurodragon", definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.environment.jaw_trap", content_version=1,
    definition_contract_hash="a74aa0ee0fa241101b5c7d3b2551d6386e4817a8ae5ad5e5cadbc4a15d5fdeb0",
)
class ForceJawOpen(EscapeSpatialRestraintAction):
    name: str = "Force jaws open"
    skill_name: SkillName = "athletics"


class SlipFreeOfJaw(EscapeSpatialRestraintAction):
    name: str = "Slip free of jaws"
    skill_name: SkillName = "acrobatics"


class JawRestrained(SpatialRestraintSource):
    name: str = "Jaw restraint"
    description: str = "Held by one closed jaw until escaped, opened or removed."
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, frozen=True)
    escape_action_types = (ForceJawOpen, SlipFreeOfJaw)

    def get_display_name(self) -> str:
        return "Jaw restraint"


class JawTrap(SpatialCondition):
    """An armed jaw closes once; reset and removal release its exact source."""

    name: str = "Jaw trap"
    content_ref: ContentRef = JAW_TRAP_CONTENT_REF
    trap_state: TrapState = TrapState.READY
    save_dc: int = Field(default=12, ge=0)
    escape_dc: int = Field(default=12, ge=0)
    payload: TrapPayload = Field(default_factory=lambda: TrapPayload(damages=(
        TrapDamage(dice_count=1, dice_sides=6, damage_type=DamageType.PIERCING),
    )))
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    affected_occupancy_layers: frozenset[OccupancyLayer] = frozenset({OccupancyLayer.GROUND})
    hazard_filter: HazardFilter = HazardFilter.ALL
    duration: Duration = Field(default_factory=lambda: Duration(duration=None, duration_type=DurationType.PERMANENT))

    def is_hazard_perceived_by(self, requesting_entity_uuid: UUID | None = None) -> bool:
        observer = BaseBlock.get(requesting_entity_uuid) if requesting_entity_uuid is not None else None
        senses = observer.get_senses() if observer is not None else None
        return (senses is not None and self.uuid in senses.spatial_effects
                or super().is_hazard_perceived_by(requesting_entity_uuid))

    def is_hazardous_for(self, entity_uuid: UUID | None = None, *,
                         occupancy_layer: OccupancyLayer = OccupancyLayer.GROUND) -> bool:
        return self.trap_state is TrapState.READY and super().is_hazardous_for(
            entity_uuid, occupancy_layer=occupancy_layer)

    def get_spatial_observation(self, positions: set[tuple[int, int]], *,
                               observer_uuid: UUID, discovered: bool = False) -> PerceivedSpatialEffect | None:
        if not discovered and not self.is_hazard_perceived_by(observer_uuid):
            return None
        if self.trap_state is TrapState.READY:
            description = "Open and armed; ground contact closes the jaws."
        elif self.trap_state is TrapState.DEACTIVATED:
            description = "Open and disabled."
        else:
            description = "Closed and holding a creature." if self.linked_conditions else "Closed and empty; reset before reuse."
        return PerceivedSpatialEffect(content_ref=self.content_ref, name=self.name, description=description,
            positions=tuple(sorted(positions)), trap_state=self.trap_state)

    def _publish_state(self, *, parent_event: Event, previous_state: TrapState) -> None:
        positions = set(self.affected_positions)
        change = self._open_change(SpatialEffectChangeOperation.STATE_CHANGED,
            previous_positions=positions, affected_positions=positions, parent_event=parent_event,
            previous_trap_state=previous_state, trap_state=self.trap_state)
        self._complete_change(change)

    def unlink_condition(self, condition_uuid: UUID, *, parent_event: Event) -> None:
        super().unlink_condition(condition_uuid, parent_event=parent_event)
        if self.is_active_spatial_condition():
            self._publish_state(parent_event=parent_event, previous_state=self.trap_state)

    def _release_capture(self, *, parent_event: Event) -> bool:
        for target_uuid, condition_uuid in tuple(self.linked_conditions):
            target = Entity.get(target_uuid)
            if isinstance(target, Entity) and not target.remove_condition_by_uuid(condition_uuid, parent_event=parent_event):
                return False
        return not self.linked_conditions

    def set_trap_state(self, state: TrapState, *, parent_event: Event) -> bool:
        if state is TrapState.ACTIVATED:
            return self.fire(parent_event=parent_event).committed
        if not self.is_active_spatial_condition() or self.trap_state is state:
            return False
        if not self._release_capture(parent_event=parent_event):
            return False
        previous = self.trap_state
        self.trap_state = state
        self._publish_state(parent_event=parent_event, previous_state=previous)
        return True

    def fire(self, *, parent_event: Event) -> MechanismActivationEvent:
        event = EventQueue.publish_declaration(MechanismActivationEvent(
            source_entity_uuid=self.uuid, source_entity_name=self.name, mechanism_uuid=self.uuid,
            mechanism_content_ref=self.content_ref, origin_position=self.position, direction=(0, 0),
            affected_positions=(self.position,), end_position=self.position,
            parent_event=parent_event.uuid, use_register=False))
        if event.canceled:
            return event
        if not self.is_active_spatial_condition() or self.trap_state is not TrapState.READY:
            return event.cancel(status_message="Jaws are not armed")
        event = event.phase_to(EventPhase.EXECUTION)
        if event.canceled:
            return event
        occupants = [entity for identity in sorted(get_map().get_entities_at(self.position), key=str)
                     if isinstance((entity := Entity.get(identity)), Entity)
                     and self.affects_occupancy_layer(entity.occupancy_layer)]
        target = occupants[0] if occupants else None
        event = event.phase_to(EventPhase.EFFECT, target_entity_uuid=target.uuid if target is not None else None)
        if event.canceled:
            return event
        self.trap_state = TrapState.ACTIVATED
        self.condition_stealth_dc = None
        if target is not None:
            request = target.create_saving_throw_request(target_entity_uuid=target.uuid, ability_name="dexterity",
                dc=self.save_dc, parent_event=event.uuid, saving_throw_context=SavingThrowContext(
                    cause_id=self.content_ref.content_id, effect_id=f"{self.content_ref.content_id}.capture", is_magical=False))
            _, _, saved = target.saving_throw(request)
            if saved:
                retreat_after_saved_entry(target, parent_event=event)
            else:
                apply_trap_payload(target, self.payload, source_uuid=self.uuid, content_ref=self.content_ref,
                                   name=self.name, parent_event=event)
                if target.position == self.position and self.trap_state is TrapState.ACTIVATED:
                    source = JawRestrained(source_entity_uuid=self.uuid, target_entity_uuid=target.uuid,
                        source_spatial_condition_uuid=self.uuid, check_dc=self.escape_dc, tags=set())
                    applied = target.add_condition(source, parent_event=event)
                    if applied is not None and not applied.canceled:
                        self.add_linked_condition(target.uuid, source.uuid)
        self._publish_state(parent_event=event, previous_state=TrapState.READY)
        return event.phase_to(EventPhase.COMPLETION, committed=True)

    def _apply(self, execution_event: Event) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event]:
        modifiers, handlers, children, spatial_handlers, effect = super()._apply(execution_event)

        def contact(event: Event, _source_uuid: UUID) -> Event | None:
            if not isinstance(event, SpatialChangeEvent):
                return None
            if event.event_type is EventType.SPATIAL_ENTITY_ENTERED:
                if self.trap_state is TrapState.READY and self.admits_occupancy_transition(event):
                    entity = Entity.get(event.entity_uuid) if event.entity_uuid is not None else None
                    if isinstance(entity, Entity) and entity.position == event.position:
                        self.fire(parent_event=event)
            elif event.entity_uuid is not None:
                target = Entity.get(event.entity_uuid)
                if isinstance(target, Entity) and (target.position not in self.affected_positions
                        or not self.affects_occupancy_layer(target.occupancy_layer)):
                    for target_uuid, condition_uuid in tuple(self.linked_conditions):
                        if target_uuid == target.uuid:
                            target.remove_condition_by_uuid(condition_uuid, parent_event=event)
            return None

        for event_type in (EventType.SPATIAL_ENTITY_ENTERED, EventType.SPATIAL_ENTITY_LEFT):
            handler = EventHandler(name="Jaw contact", source_entity_uuid=self.uuid,
                trigger_conditions=[Trigger(event_type=event_type, event_phase=EventPhase.EFFECT)], event_processor=contact)
            EventQueue.add_spatial_handler(handler, set(self.affected_positions), event_type, EventPhase.EFFECT)
            spatial_handlers.append(handler.uuid)
        return modifiers, handlers, children, spatial_handlers, effect


def materialize_jaw_trap(position: tuple[int, int], *, payload: TrapPayload | None = None,
                         save_dc: int = 12, escape_dc: int = 12, trap_state: TrapState = TrapState.READY,
                         stealth_dc: int | None = None, parent_event: Event | None = None) -> JawTrap:
    """Install one native jaw, independent of its trigger/appearance."""
    identity = uuid4()
    cause = parent_event
    if cause is None:
        cause = EventQueue.publish_declaration(Event(name="Install jaw trap", event_type=EventType.BASE_ACTION,
            source_entity_uuid=identity, use_register=False)).phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
    trap = JawTrap(uuid=identity, source_entity_uuid=identity, position=position, affected_positions={position},
        save_dc=save_dc, escape_dc=escape_dc, trap_state=trap_state, condition_stealth_dc=stealth_dc,
        payload=payload or TrapPayload(damages=(TrapDamage(dice_count=1, dice_sides=6, damage_type=DamageType.PIERCING),)))
    result = trap.activate(parent_event=cause)
    if result is None or result.canceled or not trap.applied:
        raise RuntimeError("Jaw installation failed")
    if parent_event is None:
        cause.phase_to(EventPhase.COMPLETION)
    return trap
