"""Finite physical trap activations, authored independently of trigger fixtures."""

from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.creature_types import DamageType
from dnd.core.events import Event, EventPhase, EventQueue, EventType, MechanismActivationEvent
from dnd.core.gridmap import get_map
from dnd.core.saving_throw_types import SavingThrowContext
from dnd.entity import Entity
from dnd.spatial.area_conditions import SpatialCondition
from dnd.spatial.trap_payloads import apply_trap_payload, retreat_after_saved_entry
from dnd.types.abilities import AbilityName
from dnd.types.senses import PerceivedSpatialEffect
from dnd.types.spatial_effects import SpatialEffectChangeOperation, SpatialEffectLayer, SpatialEffectOccupancyPolicy
from dnd.types.traps import TrapDamage, TrapPayload, TrapState
from dnd.types.world import OccupancyLayer


DART_LAUNCHER_CONTENT_REF = ContentRef(
    pack_id="content.neurodragon", definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.environment.dart_launcher", content_version=1,
    definition_contract_hash="a74aa0ee0fa241101b5c7d3b2551d6386e4817a8ae5ad5e5cadbc4a15d5fdeb0",
)
SWINGING_BLADE_CONTENT_REF = DART_LAUNCHER_CONTENT_REF.model_copy(update={
    "content_id": "spatial_effect.environment.swinging_blade",
})
CRUSHER_CONTENT_REF = DART_LAUNCHER_CONTENT_REF.model_copy(update={
    "content_id": "spatial_effect.environment.crusher",
})


class LaneGeometry(BaseModel):
    """A fixed straight lane, stopped by the first barrier or eligible creature."""

    model_config = ConfigDict(frozen=True)
    kind: Literal["lane"] = "lane"
    range_feet: int = Field(default=30, ge=5, multiple_of=5)


class AreaGeometry(BaseModel):
    """Authored struck cells relative to the mechanism's forward/right axes."""

    model_config = ConfigDict(frozen=True)
    kind: Literal["area"] = "area"
    offsets: tuple[tuple[int, int], ...] = ((0, 0),)


class TrapSave(BaseModel):
    """Physical avoidance, separate from a payload's optional poison save."""

    model_config = ConfigDict(frozen=True)
    ability: AbilityName = "dexterity"
    dc: int = Field(default=12, ge=0)
    half_damage_on_success: bool = False
    retreat_on_success: bool = False


class FiniteTrap(SpatialCondition):
    """One pulse owner; darts, blade strokes and crushers differ through data."""

    name: str = "Trap mechanism"
    content_ref: ContentRef = DART_LAUNCHER_CONTENT_REF
    geometry: Annotated[LaneGeometry | AreaGeometry, Field(discriminator="kind")]
    direction: tuple[int, int] = (1, 0)
    avoidance: TrapSave = Field(default_factory=TrapSave)
    payload: TrapPayload = Field(default_factory=lambda: TrapPayload(damages=(
        TrapDamage(dice_count=1, dice_sides=6, damage_type=DamageType.PIERCING),
    )))
    trap_state: TrapState = TrapState.READY
    rearm_after_activation: bool = True
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    affected_occupancy_layers: frozenset[OccupancyLayer] = frozenset({OccupancyLayer.GROUND})
    duration: Duration = Field(default_factory=lambda: Duration(
        duration=None, duration_type=DurationType.PERMANENT))

    @model_validator(mode="after")
    def validate_direction(self) -> "FiniteTrap":
        if self.direction not in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            raise ValueError("Finite trap direction must be a cardinal unit vector")
        return self

    def is_hazard_perceived_by(self, requesting_entity_uuid: UUID | None = None) -> bool:
        observer = BaseBlock.get(requesting_entity_uuid) if requesting_entity_uuid is not None else None
        senses = observer.get_senses() if observer is not None else None
        return (senses is not None and self.uuid in senses.spatial_effects
                or super().is_hazard_perceived_by(requesting_entity_uuid))

    def get_spatial_observation(self, positions: set[tuple[int, int]], *,
                               observer_uuid: UUID, discovered: bool = False) -> PerceivedSpatialEffect | None:
        if not discovered and not self.is_hazard_perceived_by(observer_uuid):
            return None
        state = {TrapState.READY: "Ready for a control signal.",
                 TrapState.ACTIVATED: "Activated; reset is required before another discharge.",
                 TrapState.DEACTIVATED: "Disabled."}[self.trap_state]
        observer = BaseBlock.get(observer_uuid)
        senses = observer.get_senses() if observer is not None else None
        observed_anchor = (self.anchor_uuid if senses is not None
            and self.anchor_uuid in senses.objects else None)
        return PerceivedSpatialEffect(content_ref=self.content_ref, name=self.name,
            description=state, positions=tuple(sorted(positions)), trap_state=self.trap_state,
            direction=self.direction, anchor_item_uuid=observed_anchor)

    def snapshot_mechanism_state(self) -> TrapState:
        return self.trap_state

    def _set_mode(self, state: TrapState, *, parent_event: Event) -> bool:
        if not self.is_active_spatial_condition() or self.trap_state is state:
            return False
        positions = set(self.affected_positions)
        change = self._open_change(SpatialEffectChangeOperation.STATE_CHANGED,
            previous_positions=positions, affected_positions=positions,
            parent_event=parent_event, previous_trap_state=self.trap_state, trap_state=state)
        self.trap_state = state
        if state is TrapState.ACTIVATED:
            self.condition_stealth_dc = None
        self._complete_change(change)
        return True

    def set_trap_state(self, state: TrapState, *, parent_event: Event) -> bool:
        if state is TrapState.ACTIVATED:
            return self.fire(parent_event=parent_event).committed
        return self._set_mode(state, parent_event=parent_event)

    def _occupants(self, position: tuple[int, int]) -> tuple[Entity, ...]:
        return tuple(entity for identity in sorted(get_map().get_entities_at(position), key=str)
                     if isinstance((entity := Entity.get(identity)), Entity)
                     and self.affects_occupancy_layer(entity.occupancy_layer))

    def _resolve_geometry(self) -> tuple[tuple[tuple[int, int], ...], tuple[Entity, ...]]:
        grid = get_map()
        dx, dy = self.direction
        if isinstance(self.geometry, LaneGeometry):
            positions: list[tuple[int, int]] = []
            current = self.position
            for _ in range(self.geometry.range_feet // 5):
                following = current[0] + dx, current[1] + dy
                if (not grid.has_tile(*following)
                        or not grid.can_propagate_transition(current, following)
                        or grid.is_blocking_propagation(*following)):
                    break
                positions.append(following)
                occupants = self._occupants(following)
                if occupants:
                    return tuple(positions), occupants[:1]
                current = following
            return tuple(positions), ()
        candidate = {(self.position[0] + forward * dx - right * dy,
                      self.position[1] + forward * dy + right * dx)
                     for forward, right in self.geometry.offsets}
        area_positions = tuple(sorted(position for position in grid.filter_propagation_positions(self.position, candidate)
                                 if not grid.is_blocking_propagation(*position)))
        occupants = {entity.uuid: entity for position in area_positions for entity in self._occupants(position)}
        return area_positions, tuple(occupants[identity] for identity in sorted(occupants, key=str))

    def _apply_payload(self, entity: Entity, *, parent_event: Event) -> None:
        request = entity.create_saving_throw_request(target_entity_uuid=entity.uuid,
            ability_name=self.avoidance.ability, dc=self.avoidance.dc, parent_event=parent_event.uuid,
            saving_throw_context=SavingThrowContext(cause_id=self.content_ref.content_id,
                effect_id=f"{self.content_ref.content_id}.avoidance", is_magical=False))
        _, _, saved = entity.saving_throw(request)
        if not self.is_active_spatial_condition() or self.trap_state is not TrapState.ACTIVATED:
            return
        if saved and self.avoidance.retreat_on_success:
            retreat_after_saved_entry(entity, parent_event=parent_event)
        if not self.is_active_spatial_condition() or self.trap_state is not TrapState.ACTIVATED:
            return
        if saved and not self.avoidance.half_damage_on_success:
            return
        apply_trap_payload(entity, self.payload, source_uuid=self.uuid, content_ref=self.content_ref,
                           name=self.name, parent_event=parent_event, half_damage=saved,
                           apply_condition=not saved)

    def fire(self, *, parent_event: Event) -> MechanismActivationEvent:
        """Resolve one requested pulse, even when its final mode remains Ready."""
        event = EventQueue.publish_declaration(MechanismActivationEvent(
            source_entity_uuid=self.uuid, source_entity_name=self.name, mechanism_uuid=self.uuid,
            mechanism_content_ref=self.content_ref,
            origin_position=self.position, direction=self.direction, affected_positions=(), end_position=self.position,
            parent_event=parent_event.uuid, phase=EventPhase.DECLARATION, use_register=False))
        if event.canceled:
            return event
        if not self.is_active_spatial_condition() or self.trap_state is not TrapState.READY:
            return event.cancel(status_message="Mechanism is not ready")
        event = event.phase_to(EventPhase.EXECUTION)
        if event.canceled:
            return event
        if not self.is_active_spatial_condition() or self.trap_state is not TrapState.READY:
            return event.cancel(status_message="Mechanism is no longer ready")
        positions, targets = self._resolve_geometry()
        event = event.phase_to(EventPhase.EFFECT, affected_positions=positions,
            end_position=positions[-1] if positions else self.position,
            target_entity_uuid=targets[0].uuid if isinstance(self.geometry, LaneGeometry) and targets else None)
        if event.canceled:
            return event
        if not self.is_active_spatial_condition() or self.trap_state is not TrapState.READY:
            return event.cancel(status_message="Mechanism is no longer ready")
        self._set_mode(TrapState.ACTIVATED, parent_event=event)
        for target in targets:
            if not self.is_active_spatial_condition() or self.trap_state is not TrapState.ACTIVATED:
                break
            self._apply_payload(target, parent_event=event)
        if self.rearm_after_activation and self.trap_state is TrapState.ACTIVATED:
            self._set_mode(TrapState.READY, parent_event=event)
        return event.phase_to(EventPhase.COMPLETION, committed=True)


def materialize_finite_trap(position: tuple[int, int], *, geometry: LaneGeometry | AreaGeometry,
                            direction: tuple[int, int] = (1, 0), payload: TrapPayload | None = None,
                            avoidance: TrapSave | None = None, content_ref: ContentRef = DART_LAUNCHER_CONTENT_REF,
                            name: str = "Trap mechanism", trap_state: TrapState = TrapState.READY,
                            rearm_after_activation: bool = True, stealth_dc: int | None = None,
                            parent_event: Event | None = None) -> FiniteTrap:
    """Install authored mechanism data through the ordinary spatial lifecycle."""
    identity = uuid4()
    cause = parent_event
    if cause is None:
        cause = EventQueue.publish_declaration(Event(name="Install trap mechanism",
            source_entity_uuid=identity, event_type=EventType.BASE_ACTION, use_register=False))
        for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
            if cause.canceled:
                raise RuntimeError("Mechanism installation was canceled")
            cause = cause.phase_to(phase)
    trap = FiniteTrap(uuid=identity, source_entity_uuid=identity, position=position, affected_positions={position},
        content_ref=content_ref, name=name, geometry=geometry, direction=direction,
        avoidance=avoidance or TrapSave(), payload=payload or TrapPayload(damages=(
            TrapDamage(dice_count=1, dice_sides=6, damage_type=DamageType.PIERCING),)),
        trap_state=trap_state, rearm_after_activation=rearm_after_activation, condition_stealth_dc=stealth_dc)
    result = trap.activate(parent_event=cause)
    if result is None or result.canceled or not trap.applied:
        raise RuntimeError("Mechanism installation failed")
    if parent_event is None:
        cause.phase_to(EventPhase.COMPLETION)
    return trap
