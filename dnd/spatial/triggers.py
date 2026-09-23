"""Ground pressure sensors connected to existing native environment operations."""

from uuid import UUID, uuid4

from pydantic import Field, model_validator

from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, SpatialChangeEvent, StepMovementEvent, ForcedMovementEvent, MechanismActivationEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.items.environment import DirectionalDoor
from dnd.items.environment_controls import linked_item, request_control
from dnd.spatial.area_conditions import SpatialCondition
from dnd.spatial.environmental_conditions import SpikeTrap
from dnd.spatial.mechanisms import FiniteTrap
from dnd.spatial.gas_traps import GasVent
from dnd.spatial.jaws import JawTrap
from dnd.spatial.portals import Portal
from dnd.types.controls import ActivationLink, ControlLink
from dnd.types.senses import PerceivedSpatialEffect
from dnd.types.spatial_effects import SpatialEffectChangeOperation, SpatialEffectLayer, SpatialEffectOccupancyPolicy
from dnd.types.traps import TrapState
from dnd.types.world import OccupancyLayer


PRESSURE_PLATE_CONTENT_REF = ContentRef(
    pack_id="content.neurodragon", definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.environment.pressure_plate", content_version=1,
    definition_contract_hash="a74aa0ee0fa241101b5c7d3b2551d6386e4817a8ae5ad5e5cadbc4a15d5fdeb0",
)


class PressurePlate(SpatialCondition):
    """Local grounded occupancy produces edges, not a second occupant registry."""

    name: str = "Pressure Plate"
    description: str = "A pressure-operated floor plate."
    content_ref: ContentRef = PRESSURE_PLATE_CONTENT_REF
    link: ControlLink | ActivationLink | tuple[ActivationLink, ...]
    pressed: bool = False
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    duration: Duration = Field(default_factory=lambda: Duration(
        duration=None, duration_type=DurationType.PERMANENT))

    def get_spatial_observation(self, positions: set[tuple[int, int]], *,
                                observer_uuid: UUID, discovered: bool = False) -> PerceivedSpatialEffect | None:
        if not discovered and not self.is_hazard_perceived_by(observer_uuid):
            return None
        return PerceivedSpatialEffect(content_ref=self.content_ref, name=self.name,
            description="The plate is pressed down." if self.pressed else "The plate is released.",
            positions=tuple(sorted(positions)), pressed=self.pressed)

    def _refresh_pressure(self, parent_event: Event) -> None:
        grid = get_map()
        occupied = any(
            isinstance(actor := Entity.get(identity), Entity)
            and actor.occupancy_layer is OccupancyLayer.GROUND
            for position in self.affected_positions for identity in grid.get_entities_at(position))
        if occupied is self.pressed:
            return
        positions = set(self.affected_positions)
        effect = self._open_change(SpatialEffectChangeOperation.STATE_CHANGED,
            previous_positions=positions, affected_positions=positions, parent_event=parent_event,
            previous_pressed=self.pressed, pressed=occupied)
        # Nested movement caused by the output must observe the new contact state.
        self.pressed = occupied
        self._send_output(parent_event=effect)
        self._complete_change(effect)

    def _send_output(self, *, parent_event: Event) -> None:
        if isinstance(self.link, ControlLink):
            request_control(self.link, self.pressed, controller_uuid=self.uuid, parent_event=parent_event)
        elif self.pressed:
            # One actual press emits all authored pulses even if the first
            # mechanism moves its recipient and releases this same plate.
            links = self.link if isinstance(self.link, tuple) else (self.link,)
            for link in links:
                activate_link(link, parent_event=parent_event)

    def _apply(self, execution_event: Event) -> tuple[
        list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event,
    ]:
        modifiers, handlers, children, spatial_handlers, effect = super()._apply(execution_event)

        def changed(event: Event, _source: UUID) -> Event | None:
            if isinstance(event, SpatialChangeEvent):
                # Membership is already committed for BOTH departure and arrival,
                # including same-cell takeoff/landing. Internal moves retain pressure.
                self._refresh_pressure(event)
            return None

        for event_type in (EventType.SPATIAL_ENTITY_LEFT, EventType.SPATIAL_ENTITY_ENTERED):
            handler = EventHandler(name="Pressure Contact", source_entity_uuid=self.source_entity_uuid,
                trigger_conditions=[Trigger(event_type=event_type, event_phase=EventPhase.EFFECT)],
                event_processor=changed)
            EventQueue.add_spatial_handler(handler, set(self.affected_positions), event_type, EventPhase.EFFECT)
            spatial_handlers.append(handler.uuid)
        self._refresh_pressure(effect)
        return modifiers, handlers, children, spatial_handlers, effect

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        if isinstance(self.link, ControlLink):
            target = linked_item(self.link)
            if isinstance(target, DirectionalDoor):
                target.cancel_pending_close(self.uuid)
            if self.pressed and parent_event is not None:
                self.pressed = False
                self._send_output(parent_event=parent_event)
        super()._release_owned_runtime_state(parent_event=parent_event)


def materialize_pressure_plate(positions: set[tuple[int, int]], link: ControlLink | ActivationLink | tuple[ActivationLink, ...],
                               *, stealth_dc: int | None = None,
                               parent_event: Event | None = None) -> PressurePlate:
    """Install a plate; an existing occupant immediately engages its authored link."""
    if not positions:
        raise ValueError("Pressure plate requires a footprint")
    source = uuid4()
    cause = parent_event
    if cause is None:
        cause = EventQueue.publish_declaration(Event(name="Install Pressure Plate",
            event_type=EventType.BASE_ACTION, source_entity_uuid=source,
            phase=EventPhase.DECLARATION, use_register=False))
        for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
            if cause.canceled:
                raise RuntimeError("Pressure plate installation canceled")
            cause = cause.phase_to(phase)
    plate = PressurePlate(source_entity_uuid=source, position=min(positions),
        affected_positions=positions, link=link, condition_stealth_dc=stealth_dc)
    result = plate.activate(parent_event=cause)
    if result is None or result.canceled or not plate.applied:
        raise RuntimeError("Pressure plate installation failed")
    if parent_event is None:
        cause.phase_to(EventPhase.COMPLETION)
    return plate


def activate_link(link: ActivationLink, *, parent_event: Event) -> None:
    """Dispatch a private exact connection to its existing native mechanism."""
    mechanism = get_map().get_spatial_condition(link.target_condition_uuid)
    if isinstance(mechanism, (FiniteTrap, JawTrap, GasVent)):
        mechanism.fire(parent_event=parent_event)
    elif isinstance(mechanism, (SpikeTrap, Portal)) and mechanism.trap_state is TrapState.READY:
        mechanism.set_trap_state(TrapState.ACTIVATED, parent_event=parent_event)


TRIPWIRE_CONTENT_REF = PRESSURE_PLATE_CONTENT_REF.model_copy(update={
    "content_id": "spatial_effect.environment.tripwire",
})


class Tripwire(SpatialCondition):
    """A grounded crossing of one authored grid boundary emits one pulse."""

    name: str = "Tripwire"
    content_ref: ContentRef = TRIPWIRE_CONTENT_REF
    link: ActivationLink
    across: tuple[int, int]
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    duration: Duration = Field(default_factory=lambda: Duration(
        duration=None, duration_type=DurationType.PERMANENT))

    @model_validator(mode="after")
    def validate_edge(self) -> "Tripwire":
        if sum(abs(a - b) for a, b in zip(self.position, self.across)) != 1:
            raise ValueError("Tripwire requires adjacent edge cells")
        return self

    def get_spatial_observation(self, positions: set[tuple[int, int]], *,
                                observer_uuid: UUID, discovered: bool = False) -> PerceivedSpatialEffect | None:
        if not discovered and not self.is_hazard_perceived_by(observer_uuid):
            return None
        return PerceivedSpatialEffect(content_ref=self.content_ref, name=self.name,
            description="A taut wire triggers its connected mechanism when crossed on foot.",
            positions=tuple(sorted(positions)), anchor_position=self.position if self.position in positions else None,
            direction=(self.across[0] - self.position[0], self.across[1] - self.position[1]))

    def _apply(self, execution_event: Event) -> tuple[
        list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event,
    ]:
        modifiers, handlers, children, spatial_handlers, effect = super()._apply(execution_event)

        def crossed(event: Event, _source: UUID) -> Event | None:
            if (not isinstance(event, SpatialChangeEvent)
                    or event.occupancy_layer is not OccupancyLayer.GROUND
                    or event.previous_occupancy_layer is not OccupancyLayer.GROUND
                    or {event.old_position, event.position} != {self.position, self.across}):
                return None
            parent = EventQueue.get_event_by_uuid(event.parent_event) if event.parent_event else None
            if not isinstance(parent, (StepMovementEvent, ForcedMovementEvent)):
                return None  # Relocation, deployment and removal are not crossings.
            actor = Entity.get(event.entity_uuid) if event.entity_uuid else None
            if not isinstance(actor, Entity) or actor.position != event.position:
                return None
            pulse = EventQueue.publish_declaration(MechanismActivationEvent(
                name="Tripwire Crossing", source_entity_uuid=self.uuid, target_entity_uuid=actor.uuid,
                mechanism_uuid=self.uuid, mechanism_content_ref=self.content_ref,
                origin_position=self.position, direction=(self.across[0] - self.position[0],
                    self.across[1] - self.position[1]), affected_positions=tuple(sorted(self.affected_positions)),
                end_position=event.position, parent_event=event.uuid, use_register=False))
            for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
                if pulse.canceled:
                    return None
                pulse = pulse.phase_to(phase)
            if not pulse.canceled:
                activate_link(self.link, parent_event=pulse)
                pulse.phase_to(EventPhase.COMPLETION, committed=True)
            return None

        handler = EventHandler(name="Tripwire Crossing", source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_ENTITY_ENTERED, event_phase=EventPhase.EFFECT)],
            event_processor=crossed)
        EventQueue.add_spatial_handler(handler, set(self.affected_positions),
            EventType.SPATIAL_ENTITY_ENTERED, EventPhase.EFFECT)
        spatial_handlers.append(handler.uuid)
        return modifiers, handlers, children, spatial_handlers, effect


def materialize_tripwire(position: tuple[int, int], across: tuple[int, int], link: ActivationLink,
                         *, stealth_dc: int | None = None, parent_event: Event | None = None) -> Tripwire:
    source = uuid4()
    cause = parent_event
    if cause is None:
        cause = EventQueue.publish_declaration(Event(name="Install Tripwire", source_entity_uuid=source,
            event_type=EventType.BASE_ACTION, use_register=False))
        for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
            if cause.canceled:
                raise RuntimeError("Tripwire installation canceled")
            cause = cause.phase_to(phase)
    wire = Tripwire(source_entity_uuid=source, position=position, across=across,
        affected_positions={position, across}, link=link, condition_stealth_dc=stealth_dc)
    result = wire.activate(parent_event=cause)
    if result is None or result.canceled or not wire.applied:
        raise RuntimeError("Tripwire installation failed")
    if parent_event is None:
        cause.phase_to(EventPhase.COMPLETION)
    return wire
