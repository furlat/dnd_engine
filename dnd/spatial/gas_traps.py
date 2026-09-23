"""Mundane gas releases with independent stationary cloud ownership."""

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from dnd.conditions import Poisoned
from dnd.core.aoe import Sphere
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType, HazardFilter
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.spatial_effect_definitions import SpatialEffectTransitionDefinition
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.events import (
    Damage, Event, EventHandler, EventPhase, EventQueue, EventType,
    MechanismActivationEvent, SpatialChangeEvent, TurnEvent, Trigger,
)
from dnd.core.gridmap import get_map
from dnd.core.saving_throw_types import SavingThrowContext, SavingThrowEffectTag
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.spatial.area_conditions import AreaCondition, SpatialCondition
from dnd.spatial.transitions import bind_spatial_interactions
from dnd.types.senses import OpticalObscurement, PerceivedSpatialEffect
from dnd.types.spatial_effects import (
    SpatialEffectChangeOperation, SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation, SpatialEffectLayer, SpatialEffectOccupancyPolicy,
    SpatialEffectTransitionAction, SpatialEffectTriggerKind,
)
from dnd.types.traps import TrapDamage, TrapState
from dnd.types.world import OccupancyLayer


GAS_VENT_CONTENT_REF = ContentRef(
    pack_id="content.neurodragon", definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.environment.gas_vent", content_version=1,
    definition_contract_hash="a74aa0ee0fa241101b5c7d3b2551d6386e4817a8ae5ad5e5cadbc4a15d5fdeb0",
)
GAS_CLOUD_CONTENT_REF = GAS_VENT_CONTENT_REF.model_copy(update={
    "content_id": "spatial_effect.environment.poison_gas",
})
GAS_DISPERSAL = (SpatialEffectTransitionDefinition(
    operation=SpatialEffectInteractionOperation.DISPERSE,
    minimum_intensity=SpatialEffectInteractionIntensity.MODERATE,
    action=SpatialEffectTransitionAction.REMOVE_AFFECTED,
),)
GAS_EXPOSURES = frozenset({SpatialEffectTriggerKind.APPEAR,
                         SpatialEffectTriggerKind.ENTER, SpatialEffectTriggerKind.TURN_START})
DEFAULT_GAS_DAMAGE = TrapDamage(dice_count=1, dice_sides=6, damage_type=DamageType.POISON)


class GasCloudSpec(BaseModel):
    """Authored example values, independent of spell/caster rules."""

    model_config = ConfigDict(frozen=True)
    radius_feet: int = Field(default=10, ge=0, multiple_of=5)
    duration_rounds: int = Field(default=3, ge=1)
    save_dc: int = Field(default=12, ge=0)
    damage: TrapDamage = DEFAULT_GAS_DAMAGE
    half_damage_on_success: bool = True
    poisoned_duration_rounds: int | None = Field(default=1, ge=1)
    optical_obscurement: OpticalObscurement | None = None


class GasCloud(AreaCondition):
    """One lingering release; overlapping same-content cells are replaced."""

    name: str = "Poison gas"
    description: str = "A stationary poisonous cloud. Exposure requires a Constitution save."
    content_ref: ContentRef = GAS_CLOUD_CONTENT_REF
    layer: SpatialEffectLayer = SpatialEffectLayer.CLOUD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING
    affected_occupancy_layers: frozenset[OccupancyLayer] = frozenset({OccupancyLayer.GROUND})
    hazard_filter: HazardFilter = HazardFilter.ALL
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = GAS_EXPOSURES
    first_per_turn_trigger_kinds: frozenset[SpatialEffectTriggerKind] = GAS_EXPOSURES
    zone_radius_feet: int = 10
    duration: Duration = Field(default_factory=lambda: Duration(duration=3, duration_type=DurationType.ROUNDS))
    save_dc: int = Field(default=12, ge=0)
    damage: TrapDamage = DEFAULT_GAS_DAMAGE
    half_damage_on_success: bool = True
    poisoned_duration_rounds: int | None = Field(default=1, ge=1)

    def get_spatial_observation(self, positions: set[tuple[int, int]], *,
                               observer_uuid: UUID, discovered: bool = False) -> PerceivedSpatialEffect:
        return PerceivedSpatialEffect(content_ref=self.content_ref, name=self.name,
            description=self.description, positions=tuple(sorted(positions)))

    def _expose(self, entity: Entity, *, parent_event: Event) -> None:
        request = entity.create_saving_throw_request(target_entity_uuid=entity.uuid,
            ability_name="constitution", dc=self.save_dc, parent_event=parent_event.uuid,
            saving_throw_context=SavingThrowContext(cause_id=self.content_ref.content_id,
                effect_id=f"{self.content_ref.content_id}.exposure", is_magical=False,
                condition_id="condition.poisoned" if self.poisoned_duration_rounds is not None else None,
                effect_tags=(SavingThrowEffectTag.POISON,)))
        _, _, saved = entity.saving_throw(request)
        if not saved or self.half_damage_on_success:
            bonus = ModifiableValue.create(source_entity_uuid=self.uuid, target_entity_uuid=entity.uuid,
                base_value=0, value_name="Gas damage")
            damage = Damage(name=self.name, source_entity_uuid=self.uuid, target_entity_uuid=entity.uuid,
                damage_dice=self.damage.dice_sides, dice_numbers=self.damage.dice_count,
                damage_bonus=bonus, damage_type=self.damage.damage_type)
            roll = damage.get_dice(AttackOutcome.HIT).roll
            amount = roll.total // 2 if saved else roll.total
            if amount > 0:
                entity.receive_damage(amount, self.damage.damage_type, self.uuid,
                    damage_rolls=[roll], damages=[damage], parent_event=parent_event.uuid,
                    effect_id=self.content_ref.identity_key)
        if not saved and self.poisoned_duration_rounds is not None:
            entity.add_condition(Poisoned(source_entity_uuid=self.uuid, target_entity_uuid=entity.uuid,
                duration=Duration(duration=self.poisoned_duration_rounds, duration_type=DurationType.ROUNDS,
                                  source_entity_uuid=self.uuid, target_entity_uuid=entity.uuid)),
                parent_event=parent_event)

    def _apply_appearance_effect(self, entity: Entity, *, parent_event: Event) -> None:
        self._expose(entity, parent_event=parent_event)

    def _exposure_handler(self, event_type: EventType) -> EventHandler:
        def expose(event: Event, _source_entity_uuid: UUID) -> None:
            if not isinstance(event, (SpatialChangeEvent, TurnEvent)) or event.entity_uuid is None:
                return
            entity = Entity.get(event.entity_uuid)
            if isinstance(entity, Entity):
                self._expose(entity, parent_event=event)

        return EventHandler(name="Poison gas exposure", source_entity_uuid=self.uuid,
            trigger_conditions=[Trigger(event_type=event_type, event_phase=EventPhase.EFFECT)],
            event_processor=expose)

    def _create_zone_entry_handler(self) -> EventHandler:
        return self._exposure_handler(EventType.SPATIAL_ENTITY_ENTERED)

    def _create_zone_turn_start_handler(self) -> EventHandler:
        return self._exposure_handler(EventType.TURN_START)

    def _apply(self, execution_event: Event):
        modifiers, handlers, children, spatial_handlers, effect = super()._apply(execution_event)
        dispersal = bind_spatial_interactions(condition=self, transitions=GAS_DISPERSAL)
        spatial_handlers.append(dispersal.uuid)
        return modifiers, handlers, children, spatial_handlers, effect


class GasVent(SpatialCondition):
    """A control-driven emitter; released clouds are independent world owners."""

    name: str = "Gas vent"
    content_ref: ContentRef = GAS_VENT_CONTENT_REF
    gas: GasCloudSpec = Field(default_factory=GasCloudSpec)
    trap_state: TrapState = TrapState.READY
    rearm_after_activation: bool = True
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    duration: Duration = Field(default_factory=lambda: Duration(duration=None, duration_type=DurationType.PERMANENT))

    def is_hazard_perceived_by(self, requesting_entity_uuid: UUID | None = None) -> bool:
        observer = BaseBlock.get(requesting_entity_uuid) if requesting_entity_uuid is not None else None
        senses = observer.get_senses() if observer is not None else None
        return (senses is not None and self.uuid in senses.spatial_effects
                or super().is_hazard_perceived_by(requesting_entity_uuid))

    def get_spatial_observation(self, positions: set[tuple[int, int]], *,
                               observer_uuid: UUID, discovered: bool = False) -> PerceivedSpatialEffect | None:
        if not discovered and not self.is_hazard_perceived_by(observer_uuid):
            return None
        state = {TrapState.READY: "Ready to release gas on a control signal.",
                 TrapState.ACTIVATED: "Discharged; reset is required before another release.",
                 TrapState.DEACTIVATED: "Disabled. Previously released gas may remain."}[self.trap_state]
        return PerceivedSpatialEffect(content_ref=self.content_ref, name=self.name,
            description=state, positions=tuple(sorted(positions)), trap_state=self.trap_state)

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

    def fire(self, *, parent_event: Event) -> MechanismActivationEvent:
        event = EventQueue.publish_declaration(MechanismActivationEvent(
            source_entity_uuid=self.uuid, source_entity_name=self.name, mechanism_uuid=self.uuid,
            mechanism_content_ref=self.content_ref, origin_position=self.position,
            direction=(0, 0), end_position=self.position, affected_positions=(),
            parent_event=parent_event.uuid, phase=EventPhase.DECLARATION, use_register=False))
        if event.canceled:
            return event
        if not self.is_active_spatial_condition() or self.trap_state is not TrapState.READY:
            return event.cancel(status_message="Gas vent is not ready")
        event = event.phase_to(EventPhase.EXECUTION)
        if event.canceled:
            return event
        shape = Sphere(source_entity_uuid=self.uuid, target=self.position, radius_feet=self.gas.radius_feet)
        shape.compute_objective(self.position)
        positions = {cell for cell in shape.affected_positions if get_map().has_tile(*cell)
                     and not get_map().is_blocking_propagation(*cell)}
        event = event.phase_to(EventPhase.EFFECT, affected_positions=tuple(sorted(positions)))
        if event.canceled:
            return event
        identity = uuid4()
        cloud = GasCloud(uuid=identity, source_entity_uuid=identity, position=self.position,
            affected_positions=positions, zone_radius_feet=self.gas.radius_feet,
            duration=Duration(duration=self.gas.duration_rounds, duration_type=DurationType.ROUNDS),
            save_dc=self.gas.save_dc, damage=self.gas.damage,
            half_damage_on_success=self.gas.half_damage_on_success,
            poisoned_duration_rounds=self.gas.poisoned_duration_rounds,
            optical_obscurement=self.gas.optical_obscurement)
        self._set_mode(TrapState.ACTIVATED, parent_event=event)
        result = cloud.activate(parent_event=event)
        if result is None or result.canceled or not cloud.applied:
            self._set_mode(TrapState.READY, parent_event=event)
            return event.cancel(status_message="Gas release did not form a cloud")
        if self.rearm_after_activation and self.trap_state is TrapState.ACTIVATED:
            self._set_mode(TrapState.READY, parent_event=event)
        return event.phase_to(EventPhase.COMPLETION, committed=True)


def materialize_gas_vent(position: tuple[int, int], *, gas: GasCloudSpec | None = None,
                         trap_state: TrapState = TrapState.READY, rearm_after_activation: bool = True,
                         stealth_dc: int | None = None, parent_event: Event | None = None) -> GasVent:
    """Install one mundane vent without creating or owning any gas yet."""
    identity = uuid4()
    cause = parent_event
    if cause is None:
        cause = EventQueue.publish_declaration(Event(name="Install gas vent", source_entity_uuid=identity,
            event_type=EventType.BASE_ACTION, use_register=False))
        for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
            if cause.canceled:
                raise RuntimeError("Gas vent installation was canceled")
            cause = cause.phase_to(phase)
    vent = GasVent(uuid=identity, source_entity_uuid=identity, position=position,
        affected_positions={position}, gas=gas or GasCloudSpec(), trap_state=trap_state,
        rearm_after_activation=rearm_after_activation, condition_stealth_dc=stealth_dc)
    result = vent.activate(parent_event=cause)
    if result is None or result.canceled or not vent.applied:
        raise RuntimeError("Gas vent installation failed")
    if parent_event is None:
        cause.phase_to(EventPhase.COMPLETION)
    return vent
