"""Traps on containers: sprung by the container's own committed open, disarmed with a toolkit."""

from typing import ClassVar, List, Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.actions import entity_action_economy_cost_evaluator
from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.conditions import Paralyzed, Poisoned
from dnd.core.action_types import ActionSelection
from dnd.core.base_actions import ActionEvent, BaseAction, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.concealment_types import concealment, knows
from dnd.core.condition_types import ConditionCategory, DurationType
from dnd.core.content.identities import ContentRef
from dnd.core.dice import RollType
from dnd.core.events import Event, EventHandler, EventPhase, EventType, Trigger
from dnd.core.gridmap import CrossingChannel, get_map
from dnd.core.saving_throw_types import DamageSaveContext, SavingThrowContext, SavingThrowEffectTag
from dnd.entity import Entity
from dnd.items.environment_interactables import StorageChest
from dnd.spatial.area_conditions import SpatialCondition
from dnd.spatial.environmental_conditions import SPIKE_TRAP_CONTENT_REF, install_authored_area_condition
from dnd.spatial.mechanisms import DART_LAUNCHER_CONTENT_REF, TrapSave
from dnd.spatial.trap_payloads import apply_trap_payload
from dnd.types.discovery import ActorScan
from dnd.types.senses import PerceivedSpatialEffect
from dnd.types.spatial_effects import SpatialEffectChangeOperation, SpatialEffectLayer, SpatialEffectOccupancyPolicy
from dnd.types.world import OccupancyLayer
from dnd.types.physical_access import PhysicalAccess
from dnd.core.creature_types import DamageType
from dnd.types.traps import TrapDamage, TrapPayload, TrapState

TRAP_DISARM_TOOLKIT_ID = "tool.trap_disarm_toolkit"


class NeedleParalysis(BaseCondition):
    """Poison-needle paralysis; a Constitution save at each of the victim's turn ends ends it."""
    creates = (Paralyzed,)

    name: str = Field(default="Needle paralysis", description="Condition name.")
    description: str = Field(default="Paralyzed by a poison needle; repeat the Constitution save at the end of each turn.",
                             description="Rules summary.")
    save_dc: int = Field(default=13, description="Repeat save DC.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Needle paralysis target not found")
        paralyzed = Paralyzed(source_entity_uuid=self.source_entity_uuid, target_entity_uuid=target.uuid,
                              parent_condition=self.uuid)
        target.add_condition(paralyzed, parent_event=declaration_event)
        handler = EventHandler(name="Needle paralysis repeat save", source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT,
                                        event_source_entity_uuid=target.uuid)],
            event_processor=self._repeat_save)
        target.add_event_handler(handler)
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, status_message=f"{target.name} is paralyzed by a needle")
        return [], [handler.uuid], [paralyzed.uuid], [], effect_event

    def _repeat_save(self, event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        target = Entity.get(source_entity_uuid)
        if not isinstance(target, Entity):
            return event
        request = target.create_saving_throw_request(target.uuid, "constitution", self.save_dc,
            parent_event=event.uuid, saving_throw_context=SavingThrowContext(
                cause_id="trap.container.poison_needle", effect_id="trap.container.poison_needle.repeat_save",
                condition_id="condition.paralyzed", is_magical=False, effect_tags=(SavingThrowEffectTag.POISON,)))
        _, _, saved = target.saving_throw(request)
        if saved and self.name in target.active_conditions:
            target.remove_condition(self.name, parent_event=event)
        return event


CONTAINER_NEEDLE_CONTENT_REF = SPIKE_TRAP_CONTENT_REF.model_copy(update={
    "content_id": "spatial_effect.environment.container_needle",
})


class ContainerTrap(SpatialCondition):
    """A poison needle in a container's lock: a fixed cell effect naming its container, sprung once.

    It is perceived as floor traps are: passive Perception above its DC, a search that found it, or an
    earlier observation. Its container's `TrapMount` owns it: the container's committed open springs it
    and breaking the container ends it. Containers never move, so it needs no anchor that follows one.
    """
    creates = (NeedleParalysis, Poisoned)  # Poisoned: a darts payload's condition (`apply_trap_payload`)
    crossing_channels: ClassVar[frozenset[CrossingChannel] | None] = frozenset()

    name: str = "Poison needle"
    description: str = "A hidden needle pricks whoever opens this container."
    content_ref: ContentRef = CONTAINER_NEEDLE_CONTENT_REF
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    affected_occupancy_layers: frozenset[OccupancyLayer] = frozenset({OccupancyLayer.GROUND})
    duration: Duration = Field(default_factory=lambda: Duration(duration=None, duration_type=DurationType.PERMANENT))
    container_uuid: UUID
    trap_state: TrapState = TrapState.READY
    disarm_dc: int = Field(default=13, ge=0)
    save_dc: int = Field(default=13, ge=0)
    paralysis_rounds: int = Field(default=10, ge=1)
    # Darts instead of the needle: the dart launcher's data, its avoidance save and its payload.
    avoidance: TrapSave | None = None
    payload: TrapPayload | None = None

    def get_spatial_observation(self, positions: set[tuple[int, int]], *,
                               observer_uuid: UUID) -> PerceivedSpatialEffect | None:
        state = {TrapState.READY: "Armed.", TrapState.ACTIVATED: "Sprung.", TrapState.DEACTIVATED: "Disarmed."}
        observer = BaseBlock.get(observer_uuid)
        senses = observer.get_senses() if observer is not None else None
        return PerceivedSpatialEffect(content_ref=self.content_ref, name=self.name,
            description=state[self.trap_state], positions=tuple(sorted(positions)), trap_state=self.trap_state,
            anchor_item_uuid=self.container_uuid if senses is not None and self.container_uuid in senses.objects else None)

    def snapshot_mechanism_state(self) -> TrapState:
        return self.trap_state

    def _set_state(self, state: TrapState, *, parent_event: Event) -> bool:
        """Leave the armed state once; whoever sees the needle sprung or disarmed learns it (`exposes`)."""
        if not self.is_active_spatial_condition() or self.trap_state is not TrapState.READY:
            return False
        positions = set(self.affected_positions)
        change = self._open_change(SpatialEffectChangeOperation.STATE_CHANGED, previous_positions=positions,
            affected_positions=positions, parent_event=parent_event,
            previous_trap_state=self.trap_state, trap_state=state, exposes=True)
        self.trap_state = state
        self.observation_revision += 1
        self._complete_change(change)
        return True

    def spring(self, victim_uuid: UUID, *, parent_event: Event) -> None:
        """Fire once at the creature handling the container."""
        if not self._set_state(TrapState.ACTIVATED, parent_event=parent_event):
            return
        victim = Entity.get(victim_uuid)
        if not isinstance(victim, Entity):
            return
        if self.avoidance is not None and self.payload is not None:
            self._fire_darts(victim, self.avoidance, self.payload, parent_event=parent_event)
            return
        request = victim.create_saving_throw_request(victim.uuid, "constitution", self.save_dc,
            parent_event=parent_event.uuid, saving_throw_context=SavingThrowContext(
                cause_id=self.content_ref.content_id, effect_id=f"{self.content_ref.content_id}.prick",
                condition_id="condition.paralyzed", is_magical=False, effect_tags=(SavingThrowEffectTag.POISON,)))
        _, _, saved = victim.saving_throw(request)
        if not saved:
            victim.add_condition(NeedleParalysis(source_entity_uuid=self.container_uuid,
                target_entity_uuid=victim.uuid, save_dc=self.save_dc,
                duration=Duration(duration=self.paralysis_rounds, duration_type=DurationType.ROUNDS,
                                  source_entity_uuid=victim.uuid, target_entity_uuid=victim.uuid)),
                parent_event=parent_event)

    def _fire_darts(self, victim: Entity, avoidance: TrapSave, payload: TrapPayload, *, parent_event: Event) -> None:
        """The opener's avoidance save, then the payload, as the dart launcher resolves its pulse."""
        request = victim.create_saving_throw_request(victim.uuid, avoidance.ability, avoidance.dc,
            parent_event=parent_event.uuid, saving_throw_context=SavingThrowContext(
                cause_id=self.content_ref.content_id, effect_id=f"{self.content_ref.content_id}.avoidance",
                is_magical=False))
        _, _, saved = victim.saving_throw(request)
        if saved and not avoidance.half_damage_on_success:
            return
        apply_trap_payload(victim, payload, source_uuid=self.uuid, content_ref=self.content_ref, name=self.name,
            parent_event=parent_event, half_damage=saved, apply_condition=not saved,
            damage_save=DamageSaveContext(ability=avoidance.ability, success=saved,
                                          success_fraction=0.5 if avoidance.half_damage_on_success else 0))

    def disarm(self, *, parent_event: Event) -> None:
        self._set_state(TrapState.DEACTIVATED, parent_event=parent_event)


class TrapMount(BaseCondition):
    """The container's own link to its needle: its committed open springs it, its breaking ends it."""
    creates = (ContainerTrap,)

    name: str = Field(default="Trap mount", description="Condition name.")
    condition_category: ConditionCategory = ConditionCategory.INTERNAL
    duration: Duration = Field(default_factory=lambda: Duration(duration=None, duration_type=DurationType.PERMANENT))

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not isinstance(BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None, StorageChest):
            return [], [], [], [], declaration_event.cancel(status_message="A container trap needs a container")
        return [], [], [], [], declaration_event.phase_to(EventPhase.EFFECT)

    def on_owner_opened(self, event: Event) -> None:
        for _, identity in self.linked_conditions:
            trap = BaseCondition.get(identity)
            if isinstance(trap, ContainerTrap):
                trap.spring(event.source_entity_uuid, parent_event=event)


def ready_trap_known_to(item: BaseItem, observer_uuid: UUID) -> ContainerTrap | None:
    """The armed trap of this container, when this observer knows it."""
    position = get_map().get_object_position(item.uuid)
    observer = BaseBlock.get(observer_uuid)
    return next((condition for condition in (get_map().get_spatial_conditions_at(position) if position else ())
                 if isinstance(condition, ContainerTrap) and condition.container_uuid == item.uuid
                 and condition.trap_state is TrapState.READY and observer is not None
                 and knows(condition.concealment, observer.faction, observer.uuid)),
                None)


# R49's container darts, four +5 attacks of 1d4 piercing, as the dart launcher's Dexterity save (the human, 24 October).
CONTAINER_DARTS = (TrapSave(ability="dexterity", dc=13),
                   TrapPayload(damages=(TrapDamage(dice_count=4, dice_sides=4, damage_type=DamageType.PIERCING),)))


def install_container_trap(container: StorageChest, *, detect_dc: int = 13, disarm_dc: int = 13,
                           save_dc: int = 13, darts: tuple[TrapSave, TrapPayload] | None = None,
                           parent_event: Event | None = None) -> ContainerTrap:
    """Arm one placed container with a hidden poison needle, or with `darts` (the dart launcher's avoidance save
    and payload: R49's four +5 darts of 1d4 piercing become a DC 13 Dexterity save against 4d4)."""
    position = get_map().get_object_position(container.uuid)
    if position is None:
        raise ValueError(f"{container.name} must be placed before it is trapped")
    looks = ({"name": "Dart trap", "description": "Hidden darts fire at whoever opens this container.",
              "content_ref": DART_LAUNCHER_CONTENT_REF, "avoidance": darts[0], "payload": darts[1]}
             if darts is not None else {})
    trap = ContainerTrap(source_entity_uuid=container.uuid, position=position, affected_positions={position},
        container_uuid=container.uuid, concealment=concealment(detect_dc), disarm_dc=disarm_dc, save_dc=save_dc,
        **looks)
    install_authored_area_condition(trap, parent_event=parent_event)
    mount = TrapMount(source_entity_uuid=container.uuid, target_entity_uuid=container.uuid)
    result = container.add_condition(mount, parent_event=parent_event)
    if result is None or result.canceled or not mount.applied:
        raise RuntimeError(f"{container.name} could not hold its trap")
    mount.add_linked_condition(trap.uuid, trap.uuid)
    return trap


class DisarmTrap(BaseAction):
    """Disarm a found container trap: Dexterity (Sleight of Hand) with a Trap Disarm Toolkit.

    Success spends the trap and keeps the kit; failure consumes the kit and springs the trap.
    """
    creates = (NeedleParalysis,)

    name: str = Field(default="Disarm Trap", description="Action name.")
    description: str = Field(default="Disarm a trap you have found (Sleight of Hand, needs a Trap Disarm Toolkit)",
                             description="Player-facing summary.")
    target_type: TargetType = Field(default=TargetType.OBJECT, description="Targets the trapped object.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Disarm Trap Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def get_physical_access(self) -> Optional[PhysicalAccess]:
        return PhysicalAccess.HAND

    def _toolkit(self, entity: Entity) -> UsableItem | None:
        return next((item for item in entity.inventory.items.values()
                     if isinstance(item, UsableItem) and item.item_id == TRAP_DISARM_TOOLKIT_ID), None)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(selection.target_uuids[0]) if selection.target_uuids else None
        if not isinstance(entity, Entity) or not isinstance(item, BaseItem):
            return "Nothing to disarm"
        if self._toolkit(entity) is None:  # the cheap check first: most creatures carry no kit
            return "Needs a Trap Disarm Toolkit"
        if ready_trap_known_to(item, entity.uuid) is None:
            return "No trap found here"
        return None

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not isinstance(entity, Entity) or not isinstance(item, BaseItem):
            return execution_event.cancel(status_message="Nothing to disarm")
        trap = ready_trap_known_to(item, entity.uuid)
        toolkit = self._toolkit(entity)
        if trap is None or toolkit is None:
            return execution_event.cancel(status_message="The trap cannot be disarmed now")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        roll = entity.roll_d20(entity.skill_bonus(target_entity_uuid=None, skill_name="sleight_of_hand"),
                               RollType.CHECK, skill_name="sleight_of_hand", parent_event=effect.uuid)
        if roll.total >= trap.disarm_dc:
            trap.disarm(parent_event=effect)
            return effect.with_updates(status_message=f"{entity.name} disarms the {trap.name.lower()}")
        toolkit.consume_charge_with_event(1, entity.uuid, effect)
        trap.spring(entity.uuid, parent_event=effect)
        return effect.with_updates(status_message=f"The toolkit snaps and the {trap.name.lower()} springs")


def build_trap_disarm_toolkit(source_entity_uuid: UUID, quantity: int = 1) -> UsableItem:
    """A Trap Disarm Toolkit stack; a failed disarm uses one up."""
    return UsableItem(source_entity_uuid=source_entity_uuid, item_id=TRAP_DISARM_TOOLKIT_ID,
        name="Trap Disarm Toolkit", description="Wires, shims and clamps for making a trap safe.",
        tags=["tool", "trap_disarm"], stack_id=TRAP_DISARM_TOOLKIT_ID, stack_count=quantity, max_stack=10,
        charges=1, max_charges=1, is_consumable=True, weight=1)

