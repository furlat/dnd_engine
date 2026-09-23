"""Ground-entry portals: one native owner for bare entrances and portal hatches."""

from uuid import UUID, uuid4

from pydantic import Field, model_validator

from dnd.actions import resolve_paid_entry_retreats
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType, HazardFilter
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import (
    Event, EventHandler, EventPhase, EventQueue, EventType, PortalTransferEvent,
    SpatialChangeEvent, Trigger,
)
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.spatial.area_conditions import SpatialCondition
from dnd.types.senses import PerceivedSpatialEffect
from dnd.types.spatial_effects import (
    SpatialEffectChangeOperation, SpatialEffectLayer, SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
)
from dnd.types.traps import TrapState
from dnd.types.world import OccupancyLayer


PORTAL_CONTENT_REF = ContentRef(
    pack_id="content.neurodragon", definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.environment.portal", content_version=1,
    # Required legacy content metadata, as for the other native spatial records.
    # Execution and replay do not compute or validate asset/source fingerprints.
    definition_contract_hash="a74aa0ee0fa241101b5c7d3b2551d6386e4817a8ae5ad5e5cadbc4a15d5fdeb0",
)
PORTAL_HATCH_CONTENT_REF = PORTAL_CONTENT_REF.model_copy(update={
    "content_id": "spatial_effect.environment.portal_hatch",
})


class Portal(SpatialCondition):
    """An installed entrance with a private, authored exit on the same map.

    Content identity selects its appearance. State and ground contact select
    its behavior; neither the sprite nor a spell/caster is a gameplay owner.
    """

    name: str = "Portal"
    description: str = "A magical passage to another location."
    exit_position: tuple[int, int]
    trap_state: TrapState = TrapState.ACTIVATED
    content_ref: ContentRef = PORTAL_CONTENT_REF
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    affected_occupancy_layers: frozenset[OccupancyLayer] = frozenset({OccupancyLayer.GROUND})
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.ENTER})
    duration: Duration = Field(default_factory=lambda: Duration(
        duration=None, duration_type=DurationType.PERMANENT))
    hazard_filter: HazardFilter = HazardFilter.ALL

    @model_validator(mode="after")
    def validate_exit(self) -> "Portal":
        if self.exit_position in self.affected_positions:
            raise ValueError("Portal exit must be outside its entrance footprint")
        return self

    def is_hazard_perceived_by(self, requesting_entity_uuid: UUID | None = None) -> bool:
        if self.trap_state is TrapState.ACTIVATED:
            return True
        observer = BaseBlock.get(requesting_entity_uuid) if requesting_entity_uuid else None
        senses = observer.get_senses() if observer is not None else None
        return bool(senses is not None and self.uuid in senses.spatial_effects) or super().is_hazard_perceived_by(
            requesting_entity_uuid)

    def is_hazardous_for(self, entity_uuid: UUID | None = None, *,
                         occupancy_layer: OccupancyLayer = OccupancyLayer.GROUND) -> bool:
        return self.trap_state is not TrapState.DEACTIVATED and super().is_hazardous_for(
            entity_uuid, occupancy_layer=occupancy_layer)

    def get_spatial_observation(self, positions: set[tuple[int, int]], *,
                                observer_uuid: UUID, discovered: bool = False) -> PerceivedSpatialEffect | None:
        if not discovered and not self.is_hazard_perceived_by(observer_uuid):
            return None
        text = {
            TrapState.READY: "Closed and armed; ground contact opens the passage.",
            TrapState.ACTIVATED: "An open passage transports creatures touching its entrance.",
            TrapState.DEACTIVATED: "Closed and disabled. Entry has no effect.",
        }[self.trap_state]
        return PerceivedSpatialEffect(content_ref=self.content_ref, name=self.name,
            description=text, positions=tuple(sorted(positions)), trap_state=self.trap_state)

    def set_trap_state(self, state: TrapState, *, parent_event: Event) -> bool:
        if not self.is_active_spatial_condition() or self.trap_state is state:
            return False
        positions = set(self.affected_positions)
        effect = self._open_change(SpatialEffectChangeOperation.STATE_CHANGED,
            previous_positions=positions, affected_positions=positions,
            parent_event=parent_event, trap_state=state, previous_trap_state=self.trap_state)
        self.trap_state = state
        if state is TrapState.ACTIVATED:
            self.condition_stealth_dc = None
        self._complete_change(effect)
        if state is TrapState.ACTIVATED:
            # Publish the revealed entrance before moving its witnesses away.
            # Both consequences belong to the still-open triggering event;
            # completed change facts cannot acquire new child lineages.
            self._transfer_occupants(parent_event=parent_event)
        return True

    def _transfer_occupants(self, *, parent_event: Event) -> None:
        occupants = {identity for position in self.affected_positions
                     for identity in get_map().get_entities_at(position)}
        for identity in sorted(occupants, key=str):
            entity = Entity.get(identity)
            if isinstance(entity, Entity):
                self.transfer(entity, parent_event=parent_event)

    def transfer(self, entity: Entity, *, parent_event: Event) -> PortalTransferEvent | None:
        """Commit one free crossing, then resolve the exit's ordinary consequences."""
        if (not self.is_active_spatial_condition() or self.trap_state is not TrapState.ACTIVATED
                or entity.position not in self.affected_positions
                or not self.affects_occupancy_layer(entity.occupancy_layer)):
            return None
        event = EventQueue.publish_declaration(PortalTransferEvent(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=entity.uuid,
            target_entity_name=entity.name, portal_uuid=self.uuid, portal_content_ref=self.content_ref,
            start_position=entity.position, end_position=self.exit_position,
            parent_event=parent_event.uuid, phase=EventPhase.DECLARATION, use_register=False))
        if event.canceled:
            return event
        grid = get_map()
        if (not grid.has_tile(*self.exit_position)
                or grid.get_entities_at(self.exit_position)
                or not grid.is_walkable_for(*self.exit_position, entity.uuid)):
            return event.cancel(status_message="Portal exit is blocked")
        event = event.phase_to(EventPhase.EXECUTION)
        if event.canceled:
            return event
        event = event.phase_to(EventPhase.EFFECT)
        if event.canceled:
            return event
        cursor = EventQueue.event_cursor()
        Entity.update_entity_position(entity, self.exit_position, parent_event=event.uuid,
                                      occupancy_layer=OccupancyLayer.GROUND)
        # end_position is the crossing itself, even if the arrival causes a retreat.
        resolve_paid_entry_retreats(entity, since_cursor=cursor, parent_event=event)
        return event.phase_to(EventPhase.COMPLETION, committed=True)

    def _apply(self, execution_event: Event) -> tuple[
        list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event,
    ]:
        modifiers, handlers, children, spatial_handlers, effect = super()._apply(execution_event)

        def enter(event: Event, _source_entity_uuid: UUID) -> Event | None:
            if not isinstance(event, SpatialChangeEvent) or not self.admits_occupancy_transition(event):
                return None
            entity = Entity.get(event.entity_uuid) if event.entity_uuid is not None else None
            if not isinstance(entity, Entity) or entity.position != event.position:
                return None
            if self.trap_state is TrapState.READY:
                self.set_trap_state(TrapState.ACTIVATED, parent_event=event)
            else:
                self.transfer(entity, parent_event=event)
            return None

        handler = EventHandler(name="Portal Ground Entry", source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_ENTITY_ENTERED,
                                        event_phase=EventPhase.EFFECT)], event_processor=enter)
        EventQueue.add_spatial_handler(handler, set(self.affected_positions),
                                      EventType.SPATIAL_ENTITY_ENTERED, EventPhase.EFFECT)
        spatial_handlers.append(handler.uuid)
        if self.trap_state is TrapState.ACTIVATED:
            self._transfer_occupants(parent_event=effect)
        return modifiers, handlers, children, spatial_handlers, effect


def materialize_portal(positions: set[tuple[int, int]], exit_position: tuple[int, int], *,
                       trap_state: TrapState = TrapState.ACTIVATED,
                       content_ref: ContentRef = PORTAL_CONTENT_REF,
                       stealth_dc: int | None = None, parent_event: Event | None = None) -> Portal:
    """Install a bare portal or hatch using the same native mechanism."""
    if not positions:
        raise ValueError("Portal requires an entrance footprint")
    source_uuid = uuid4()
    cause = parent_event
    if cause is None:
        cause = EventQueue.publish_declaration(Event(name="Install Portal",
            event_type=EventType.BASE_ACTION, source_entity_uuid=source_uuid,
            phase=EventPhase.DECLARATION, use_register=False))
        for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
            if cause.canceled:
                raise RuntimeError("Portal installation was canceled")
            cause = cause.phase_to(phase)
    if cause.canceled:
        raise RuntimeError("Portal installation was canceled")
    portal = Portal(source_entity_uuid=source_uuid, position=min(positions),
        affected_positions=positions, exit_position=exit_position,
        trap_state=trap_state, content_ref=content_ref, condition_stealth_dc=stealth_dc)
    result = portal.activate(parent_event=cause)
    if result is None or result.canceled or not portal.applied:
        raise RuntimeError("Portal installation failed")
    if parent_event is None:
        cause.phase_to(EventPhase.COMPLETION)
    return portal
