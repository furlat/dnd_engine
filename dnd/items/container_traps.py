"""Traps on containers: sprung by the container's own committed open, disarmed with a toolkit."""

from typing import List, Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.actions import entity_action_economy_cost_evaluator
from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.conditions import Paralyzed
from dnd.core.action_types import ActionSelection
from dnd.core.base_actions import ActionEvent, BaseAction, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import ConditionCategory, DurationType
from dnd.core.dice import RollType
from dnd.core.events import Event, EventHandler, EventPhase, EventType, Trigger
from dnd.core.saving_throw_types import SavingThrowContext, SavingThrowEffectTag
from dnd.entity import Entity
from dnd.items.environment_interactables import StorageChest
from dnd.types.discovery import ActorScan
from dnd.types.physical_access import PhysicalAccess
from dnd.types.traps import TrapState

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


class ContainerTrap(BaseCondition):
    """A poison needle in a container's lock, sprung once by its first committed open.

    Detection uses the inherited condition DC; destroying the container removes the trap.
    """
    creates = (NeedleParalysis,)

    name: str = Field(default="Poison needle", description="Condition name.")
    description: str = Field(default="A hidden needle pricks whoever opens this container.",
                             description="Rules summary.")
    condition_category: ConditionCategory = ConditionCategory.INTERNAL
    duration: Duration = Field(default_factory=lambda: Duration(duration=None, duration_type=DurationType.PERMANENT))
    trap_state: TrapState = TrapState.READY
    disarm_dc: int = Field(default=13, ge=0)
    save_dc: int = Field(default=13, ge=0)
    paralysis_rounds: int = Field(default=10, ge=1)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not isinstance(BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None, StorageChest):
            return [], [], [], [], declaration_event.cancel(status_message="A container trap needs a container")
        return [], [], [], [], declaration_event.phase_to(EventPhase.EFFECT)

    def is_hazard_perceived_by(self, observer_uuid: UUID) -> bool:
        """The concealment rule floor traps use: passive Perception, or a search that found it."""
        observer = Entity.get(observer_uuid)
        return isinstance(observer, Entity) and not self.is_concealed_from(
            observer_uuid, observer.get_passive_perception())

    def disarm(self) -> None:
        """Make the armed needle safe; a disarmed needle is plain to see."""
        if self.trap_state is TrapState.READY:
            self.trap_state = TrapState.DEACTIVATED
            self.condition_stealth_dc = None

    def on_owner_opened(self, event: Event) -> None:
        self.spring(event.source_entity_uuid, parent_event=event)

    def spring(self, victim_uuid: UUID, *, parent_event: Event) -> None:
        """Fire once at the creature handling the container; the spent needle is plain to see."""
        if self.trap_state is not TrapState.READY:
            return
        self.trap_state = TrapState.ACTIVATED
        self.condition_stealth_dc = None
        victim = Entity.get(victim_uuid)
        if not isinstance(victim, Entity):
            return
        request = victim.create_saving_throw_request(victim.uuid, "constitution", self.save_dc,
            parent_event=parent_event.uuid, saving_throw_context=SavingThrowContext(
                cause_id="trap.container.poison_needle", effect_id="trap.container.poison_needle.prick",
                condition_id="condition.paralyzed", is_magical=False, effect_tags=(SavingThrowEffectTag.POISON,)))
        _, _, saved = victim.saving_throw(request)
        if not saved:
            victim.add_condition(NeedleParalysis(source_entity_uuid=self.target_entity_uuid or victim.uuid,
                target_entity_uuid=victim.uuid, save_dc=self.save_dc,
                duration=Duration(duration=self.paralysis_rounds, duration_type=DurationType.ROUNDS,
                                  source_entity_uuid=victim.uuid, target_entity_uuid=victim.uuid)),
                parent_event=parent_event)


def ready_trap_known_to(item: BaseItem, observer_uuid: UUID) -> ContainerTrap | None:
    """The item's armed trap when this observer perceives it."""
    return next((condition for condition in item.active_conditions.values()
                 if isinstance(condition, ContainerTrap) and condition.trap_state is TrapState.READY
                 and condition.is_hazard_perceived_by(observer_uuid)), None)


def install_container_trap(container: StorageChest, *, detect_dc: int = 13, disarm_dc: int = 13,
                           save_dc: int = 13) -> ContainerTrap:
    """Arm one container with a hidden poison needle."""
    trap = ContainerTrap(source_entity_uuid=container.uuid, target_entity_uuid=container.uuid,
                         condition_stealth_dc=detect_dc, disarm_dc=disarm_dc, save_dc=save_dc)
    result = container.add_condition(trap)
    if result is None or result.canceled or not trap.applied:
        raise RuntimeError(f"{container.name} could not be trapped")
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
        if ready_trap_known_to(item, entity.uuid) is None:
            return "No trap found here"
        if self._toolkit(entity) is None:
            return "Needs a Trap Disarm Toolkit"
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
            trap.disarm()
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

