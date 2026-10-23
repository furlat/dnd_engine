"""Locks and bars on doors and containers, opened by key, Thieves' Tools or force."""

from typing import List, Literal, Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.actions import entity_action_economy_cost_evaluator
from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.core.action_types import ActionSelection
from dnd.core.base_actions import ActionEvent, BaseAction, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import DurationType
from dnd.core.dice import RollType
from dnd.core.events import Event, EventPhase
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemEffectPresentationState, ItemLocation
from dnd.entity import Entity
from dnd.items.environment import DirectionalDoor
from dnd.items.environment_interactables import StorageChest
from dnd.types.abilities import SkillName
from dnd.types.discovery import ActorScan
from dnd.types.physical_access import PhysicalAccess
from dnd.types.world_placement import CARDINAL_DELTAS

THIEVES_TOOLS_ID = "tool.thieves_tools"
KEY_ID = "tool.key"


class Lock(BaseCondition):
    """A lock or a bar holding a door or container shut while locked.

    A lock opens with its exact key (no roll), with Thieves' Tools (Sleight of Hand against
    lock_dc) or by force (Athletics against force_dc, which breaks it and bursts the owner open).
    A bar has no lock to pick and no key: it sits on one side of a door's boundary, the owner tile
    or the tile across, and is lifted and set only from there. Others see only that the owner is
    locked or barred; DCs and the key stay hidden.
    """

    name: str = Field(default="Lock", description="Condition name.")
    description: str = Field(default="Holds this door or container shut.", description="Rules summary.")
    semantic_key: Optional[str] = "condition.environment.lock"
    duration: Duration = Field(default_factory=lambda: Duration(duration=None, duration_type=DurationType.PERMANENT))
    locked: bool = True
    lock_dc: int | None = Field(default=15, ge=0, description="Sleight of Hand DC to pick; None for a bar.")
    force_dc: int = Field(default=15, ge=0, description="Athletics DC to force it open.")
    key_uuid: UUID | None = Field(default=None, description="The exact key item that works it.")
    bar_side: Literal["owner", "across"] | None = Field(
        default=None, description="For a bar: the side of the door's boundary it is worked from.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        owner = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if owner is None or owner.get_spatial_open_state() is None:
            return [], [], [], [], declaration_event.cancel(status_message="Only things that open take a lock")
        if self.bar_side is not None and self.bar_cell() is None:
            return [], [], [], [], declaration_event.cancel(status_message="A bar needs a placed door")
        return [], [], [], [], declaration_event.phase_to(EventPhase.EFFECT)

    def holds_owner_shut(self) -> bool:
        return self.locked

    def snapshot_item_effect(self) -> ItemEffectPresentationState | None:
        if not self.locked:
            return None
        barred = self.bar_side is not None
        return ItemEffectPresentationState(duration=self.duration.snapshot_summary(), effect_uuid=self.uuid,
            behavior_id=self.get_semantic_key(), display_name="Barred" if barred else "Locked",
            description="Barred." if barred else "Locked.",
            applied_source_event_cursor=self.applied_source_event_cursor)

    def bar_cell(self) -> Tuple[int, int] | None:
        """The boundary-side tile a bar is worked from: the door's owner tile or the one across."""
        placement = get_map().get_object_placement(self.target_entity_uuid) if self.target_entity_uuid else None
        if placement is None or placement.boundary_direction is None:
            return None
        if self.bar_side == "owner":
            return placement.position
        dx, dy = CARDINAL_DELTAS[placement.boundary_direction]
        return placement.position[0] + dx, placement.position[1] + dy

    def worked_by(self, entity: Entity) -> bool:
        """Its key in the actor's inventory, or for a bar, the actor on the bar's side."""
        if self.bar_side is not None:
            return entity.position == self.bar_cell()
        return self.key_uuid is not None and self.key_uuid in entity.inventory.items

    def set_locked(self, locked: bool, *, parent_event: Event) -> None:
        owner = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(owner, BaseItem) or self.locked == locked:
            return
        self.locked = locked
        owner.publish_location_state(ItemLocation.FLOOR, parent_event=parent_event)


def lock_on(item: BaseItem) -> Lock | None:
    return next((condition for condition in item.active_conditions.values() if isinstance(condition, Lock)), None)


def install_lock(owner: BaseItem, *, lock_dc: int | None = 15, force_dc: int = 15,
                 key: BaseItem | None = None, bar_side: Literal["owner", "across"] | None = None) -> Lock:
    """Lock one closed door or container: with a key and a pick DC, or as a bar on one side of a door."""
    if owner.get_spatial_open_state():
        raise ValueError(f"{owner.name} must be closed to be locked")
    lock = Lock(source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid, lock_dc=lock_dc,
                force_dc=force_dc, key_uuid=key.uuid if key is not None else None, bar_side=bar_side)
    result = owner.add_condition(lock)
    if result is None or result.canceled or not lock.applied:
        raise RuntimeError(f"{owner.name} could not be locked")
    return lock


class _LockAction(BaseAction):
    """An action on one lock within reach; subclasses say when it applies and what it does."""

    target_type: TargetType = Field(default=TargetType.OBJECT, description="Targets the locked object.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Lock Action Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def get_physical_access(self) -> Optional[PhysicalAccess]:
        return PhysicalAccess.HAND

    def lock_error(self, entity: Entity, item: BaseItem, lock: Lock) -> Optional[str]:
        raise NotImplementedError

    def work(self, entity: Entity, item: BaseItem, lock: Lock, effect: ActionEvent) -> str:
        raise NotImplementedError

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(selection.target_uuids[0]) if selection.target_uuids else None
        lock = lock_on(item) if isinstance(item, BaseItem) else None
        if not isinstance(entity, Entity) or not isinstance(item, BaseItem) or lock is None:
            return "No lock here"
        return self.lock_error(entity, item, lock)

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        lock = lock_on(item) if isinstance(item, BaseItem) else None
        if not isinstance(entity, Entity) or not isinstance(item, BaseItem) or lock is None:
            return execution_event.cancel(status_message="No lock here")
        error = self.lock_error(entity, item, lock)
        if error is not None:
            return execution_event.cancel(status_message=error)
        effect = execution_event.phase_to(EventPhase.EFFECT)
        return effect.with_updates(status_message=self.work(entity, item, lock, effect))


def _check(entity: Entity, skill: SkillName, parent_event: ActionEvent) -> int:
    return entity.roll_d20(entity.skill_bonus(target_entity_uuid=None, skill_name=skill),
                           RollType.CHECK, skill_name=skill, parent_event=parent_event.uuid).total


def _thieves_tools(entity: Entity) -> UsableItem | None:
    return next((item for item in entity.inventory.items.values()
                 if isinstance(item, UsableItem) and item.item_id == THIEVES_TOOLS_ID), None)


class Unlock(_LockAction):
    """Unlock with its key, or lift a bar from its side; no roll."""

    name: str = Field(default="Unlock", description="Action name.")
    description: str = Field(default="Unlock with the right key, or lift a bar from its side",
                             description="Player-facing summary.")

    def lock_error(self, entity: Entity, item: BaseItem, lock: Lock) -> Optional[str]:
        if not lock.locked:
            return "Not locked"
        return None if lock.worked_by(entity) else "Needs its key"

    def work(self, entity: Entity, item: BaseItem, lock: Lock, effect: ActionEvent) -> str:
        lock.set_locked(False, parent_event=effect)
        return f"{entity.name} {'lifts the bar on' if lock.bar_side is not None else 'unlocks'} {item.name}"


class LockShut(_LockAction):
    """Lock a closed door or container with its key, or set a bar from its side."""

    name: str = Field(default="Lock", description="Action name.")
    description: str = Field(default="Lock with the right key, or set a bar from its side",
                             description="Player-facing summary.")

    def lock_error(self, entity: Entity, item: BaseItem, lock: Lock) -> Optional[str]:
        if lock.locked:
            return "Already locked"
        if item.get_spatial_open_state():
            return "Close it first"
        return None if lock.worked_by(entity) else "Needs its key"

    def work(self, entity: Entity, item: BaseItem, lock: Lock, effect: ActionEvent) -> str:
        lock.set_locked(True, parent_event=effect)
        return f"{entity.name} {'bars' if lock.bar_side is not None else 'locks'} {item.name}"


class PickLock(_LockAction):
    """Pick a lock: Dexterity (Sleight of Hand) with Thieves' Tools; a failure breaks one set."""

    name: str = Field(default="Pick Lock", description="Action name.")
    description: str = Field(default="Pick the lock (Sleight of Hand, needs Thieves' Tools)",
                             description="Player-facing summary.")

    def lock_error(self, entity: Entity, item: BaseItem, lock: Lock) -> Optional[str]:
        if not lock.locked or lock.lock_dc is None:
            return "Nothing to pick"
        return None if _thieves_tools(entity) is not None else "Needs Thieves' Tools"

    def work(self, entity: Entity, item: BaseItem, lock: Lock, effect: ActionEvent) -> str:
        tools = _thieves_tools(entity)
        assert tools is not None and lock.lock_dc is not None
        if _check(entity, "sleight_of_hand", effect) >= lock.lock_dc:
            lock.set_locked(False, parent_event=effect)
            return f"{entity.name} picks the lock on {item.name}"
        tools.consume_charge_with_event(1, entity.uuid, effect)
        return f"{entity.name}'s Thieves' Tools break in the lock"


class ForceLock(_LockAction):
    """Force a lock or bar: Strength (Athletics) against its force DC; success breaks it and bursts it open."""

    name: str = Field(default="Force Lock", description="Action name.")
    description: str = Field(default="Force it open (Athletics)", description="Player-facing summary.")

    def lock_error(self, entity: Entity, item: BaseItem, lock: Lock) -> Optional[str]:
        return None if lock.locked else "Not locked"

    def work(self, entity: Entity, item: BaseItem, lock: Lock, effect: ActionEvent) -> str:
        if _check(entity, "athletics", effect) < lock.force_dc:
            return f"{item.name} holds"
        item.remove_condition_by_uuid(lock.uuid, parent_event=effect)
        if isinstance(item, DirectionalDoor):
            item.request_open(True, parent_event=effect)
        elif isinstance(item, StorageChest):
            item.set_open(True, parent_event=effect)
        return f"{entity.name} forces {item.name} open"


def build_thieves_tools(source_entity_uuid: UUID, quantity: int = 1) -> UsableItem:
    """A stack of Thieves' Tools; a failed pick breaks one set."""
    return UsableItem(source_entity_uuid=source_entity_uuid, item_id=THIEVES_TOOLS_ID, name="Thieves' Tools",
        description="Picks, a small file and a mirror on a handle.", tags=["tool", "thieves_tools"],
        stack_id=THIEVES_TOOLS_ID, stack_count=quantity, max_stack=10, charges=1, max_charges=1,
        is_consumable=True, weight=1)


def build_key(source_entity_uuid: UUID, name: str = "Key") -> BaseItem:
    """One key; the lock it works names this exact item."""
    return BaseItem(source_entity_uuid=source_entity_uuid, item_id=KEY_ID, name=name,
                    description="A key.", tags=["key"])
