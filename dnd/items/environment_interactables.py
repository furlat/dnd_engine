"""Runtime actions and item types for interactive environment objects."""

import random
from typing import Optional, List, cast as type_cast
from uuid import UUID, uuid4
from pydantic import Field

from dnd.core.base_actions import (
    BaseAction,
    ActionEvent,
    TargetType,
    Cost,
)
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.events import Event, EventPhase
from dnd.types.abilities import SkillName
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemDestructionProfile, ItemLocation, ItemPresentationState
from dnd.blocks.base_item import UsableItem
from dnd.blocks.inventory import Inventory
from dnd.entity import Entity
from dnd.items.environment import DirectionalDoor
from dnd.items.environment_controls import control_value, linked_item
from dnd.types.controls import ControlLink as LeverLink
from dnd.items.torches import WallTorch
from dnd.spatial.environmental_conditions import SpikeTrap
from dnd.spatial.portals import Portal
from dnd.spatial.mechanisms import FiniteTrap
from dnd.spatial.jaws import JawTrap
from dnd.spatial.gas_traps import GasVent
from dnd.types.traps import TrapState


class OpenDoorAction(BaseAction):
    """Opens a closed door."""

    name: str = Field(default="Open Door", description="Action name for opening a door.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Door actions target the source user and resolve through source_item_uuid.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for opening a door.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the door item this action opens.",
    )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, DoorObject) or not door.is_active:
            return declaration_event.cancel(status_message="Door not found")
        if door.is_open:
            return declaration_event.cancel(status_message="Door already open")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, DoorObject) or not door.is_active:
            return execution_event.cancel(status_message="Door not found")
        old_blocks_movement = door.blocks_movement
        old_blocks_optics = door.blocks_optics_field
        old_blocks_propagation = door.blocks_propagation_field
        door.is_open = True
        door.blocks_movement = False
        door.blocks_optics_field = False
        door.blocks_propagation_field = False
        door._notify_blocking_changed(
            old_blocks_movement,
            old_blocks_optics,
            old_blocks_propagation,
            parent_event=execution_event.uuid,
        )
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Door opened")
        return effect.with_updates(status_message="Door opened")


class CloseDoorAction(BaseAction):
    """Closes an open door."""

    name: str = Field(default="Close Door", description="Action name for closing a door.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Door actions target the source user and resolve through source_item_uuid.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for closing a door.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the door item this action closes.",
    )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, DoorObject) or not door.is_active:
            return declaration_event.cancel(status_message="Door not found")
        if not door.is_open:
            return declaration_event.cancel(status_message="Door already closed")
        grid = get_map()
        door_pos = grid.get_object_position(door.uuid)
        if door_pos and grid.get_entities_at(door_pos):
            return declaration_event.cancel(status_message="Can't close door — someone is standing in the doorway")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, DoorObject) or not door.is_active:
            return execution_event.cancel(status_message="Door not found")
        old_blocks_movement = door.blocks_movement
        old_blocks_optics = door.blocks_optics_field
        old_blocks_propagation = door.blocks_propagation_field
        door.is_open = False
        door.blocks_movement = True
        door.blocks_optics_field = True
        door.blocks_propagation_field = True
        door._notify_blocking_changed(
            old_blocks_movement,
            old_blocks_optics,
            old_blocks_propagation,
            parent_event=execution_event.uuid,
        )
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Door closed")
        return effect.with_updates(status_message="Door closed")


class DoorObject(UsableItem):
    """Door that surfaces exactly the action valid for its current state."""

    name: str = Field(default="Door", description="Display name for the test door.")
    is_pickable: bool = Field(default=False, description="Doors are fixed environment objects.")
    map_char: str = Field(default="\u03c0", description="Map glyph for the test door.")
    blocks_movement: bool = Field(default=True, description="Closed doors block movement.")
    blocks_optics_field: bool = Field(default=True, description="Closed doors block ordinary optics.")
    blocks_propagation_field: bool = Field(default=True, description="Closed doors block physical propagation.")
    is_open: bool = Field(default=False, description="Whether the door is currently open.")

    is_targetable: bool = True

    def model_post_init(self, __context) -> None:
        super().model_post_init(__context)
        if self.health is None:
            self.health = self.create_item_health(self.uuid, 18)
        if self.destruction_profile is None:
            self.destruction_profile = ItemDestructionProfile(name=f"Broken {self.name}")

    def get_spatial_open_state(self) -> Optional[bool]:
        """Return the door-open state used by spatial event metadata."""
        return self.is_open

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Return open or close actions according to the door state."""
        if not self.is_active:
            return []
        if self.is_open:
            grid = get_map()
            door_pos = grid.get_object_position(self.uuid)
            if door_pos and grid.get_entities_at(door_pos):
                return []
            return [
                self.bind_dynamic_use_action(
                    CloseDoorAction(
                        source_entity_uuid=user_entity_uuid,
                        source_item_uuid=self.uuid,
                        template=True,
                    ),
                )
            ]
        return [
            self.bind_dynamic_use_action(
                OpenDoorAction(
                    source_entity_uuid=user_entity_uuid,
                    source_item_uuid=self.uuid,
                    template=True,
                ),
            )
        ]
class PullLeverAction(BaseAction):
    """Set one linked trap's mechanical state without removing its owner."""

    name: str = Field(default="Pull Lever", description="Action name for pulling a trap lever.")
    description: str = Field(default="Changes the linked trap's mechanical state", description="Action description shown for trap levers.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Trap levers target the source user and resolve through source_item_uuid.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for pulling a trap lever.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the lever item this action pulls.",
    )
    trap_condition_uuid: Optional[UUID] = Field(
        default=None,
        description="Exact installed mechanism UUID controlled by this lever.",
    )
    desired_state: TrapState = TrapState.DEACTIVATED

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        lever = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        if self.source_item_uuid is not None and (not isinstance(lever, TrapLever) or not lever.is_active):
            return declaration_event.cancel(status_message="Lever is unavailable")
        if self.trap_condition_uuid is None:
            return declaration_event.cancel(status_message="No trap linked")
        condition = BaseCondition.get(self.trap_condition_uuid)
        if not isinstance(condition, (SpikeTrap, Portal, FiniteTrap, JawTrap, GasVent)) or not condition.applied:
            return declaration_event.cancel(status_message="Linked trap is unavailable")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        lever = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        if self.source_item_uuid is not None and (not isinstance(lever, TrapLever) or not lever.is_active):
            return execution_event.cancel(status_message="Lever is unavailable")
        if self.trap_condition_uuid is None:
            return execution_event.cancel(status_message="No trap linked")
        condition = BaseCondition.get(self.trap_condition_uuid)
        if not isinstance(condition, (SpikeTrap, Portal, FiniteTrap, JawTrap, GasVent)) or not condition.applied:
            return execution_event.cancel(status_message="Linked trap is unavailable")
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message="Pulling trap lever",
        )
        if effect.canceled:
            return effect
        if isinstance(lever, TrapLever) and not lever.is_active:
            return effect.cancel(status_message="Lever is unavailable")
        if condition.trap_state is not self.desired_state and not condition.set_trap_state(
            self.desired_state, parent_event=effect,
        ):
            return effect.cancel(status_message="Trap state change was rejected")
        lever = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        if isinstance(lever, TrapLever) and lever.is_active:
            # The physical handle moves on a pull, independently of the trap's state.
            lever.is_engaged = not lever.is_engaged
            lever.publish_location_state(ItemLocation.FLOOR, parent_event=effect)
        return effect.with_updates(status_message="Lever pulled")


class TrapLever(UsableItem):
    """Fixed trap control; activation capability and charge budget are independent."""

    name: str = Field(default="Trap Lever", description="Display name for the trap lever.")
    is_pickable: bool = Field(default=False, description="Trap levers are fixed environment objects.")
    map_char: str = Field(default="\u03bb", description="Map glyph for the trap lever.")
    is_engaged: bool = False
    allow_activation: bool = False

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        actions = super().get_use_actions(user_entity_uuid)
        if not self.allow_activation:
            return actions
        available: List[BaseAction] = []
        for action in actions:
            if not isinstance(action, PullLeverAction):
                available.append(action)
                continue
            condition = BaseCondition.get(action.trap_condition_uuid) if action.trap_condition_uuid else None
            if not isinstance(condition, (SpikeTrap, Portal, FiniteTrap, JawTrap, GasVent)) or not condition.applied:
                continue
            if isinstance(condition, (FiniteTrap, JawTrap, GasVent)):
                action.desired_state = (TrapState.DEACTIVATED if condition.trap_state is TrapState.READY
                                        else TrapState.READY)
                action.name = {TrapState.READY: "Deactivate Trap", TrapState.ACTIVATED: "Reset Trap",
                               TrapState.DEACTIVATED: "Arm Trap"}[condition.trap_state]
            else:
                action.desired_state = (TrapState.ACTIVATED if self.is_engaged
                                        else TrapState.DEACTIVATED)
                action.name = "Activate Trap" if action.desired_state is TrapState.ACTIVATED else "Deactivate Trap"
            available.append(action)
        return available

    def to_item_presentation_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemPresentationState:
        """Expose the one exact authored mechanism identity."""
        targets = {
            action.trap_condition_uuid
            for action in self.use_action_templates
            if isinstance(action, PullLeverAction)
            and action.trap_condition_uuid is not None
        }
        if len(targets) > 1:
            raise ValueError("Trap Lever has multiple distinct condition targets")
        return super().to_item_presentation_state(
            stack_count=stack_count,
        ).model_copy(update={
            "linked_spatial_condition_uuid": next(iter(targets), None),
            "is_engaged": self.is_engaged,
        })


class ToggleLeverAction(BaseAction):
    """Move the handle after its linked item's requested state is satisfied."""

    name: str = "Toggle Lever"
    target_type: TargetType = TargetType.SELF
    costs: List[Cost] = Field(default_factory=list)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        lever = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        if not isinstance(lever, ControlLever) or not lever.is_active:
            return declaration_event.cancel(status_message="Lever not found")
        target = lever.get_linked_item()
        if target is None:
            return declaration_event.cancel(status_message="Linked item not found")
        desired_value = lever.link.engaged_value if not lever.is_engaged else not lever.link.engaged_value
        if control_value(target) != desired_value and not target.get_use_actions(self.source_entity_uuid):
            return declaration_event.cancel(status_message="Linked item cannot change state")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        lever = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        if not isinstance(lever, ControlLever) or not lever.is_active:
            return execution_event.cancel(status_message="Lever not found")
        target = lever.get_linked_item()
        if target is None:
            return execution_event.cancel(status_message="Linked item not found")
        next_engaged = not lever.is_engaged
        desired_value = lever.link.engaged_value if next_engaged else not lever.link.engaged_value
        effect = execution_event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        if not lever.is_active:
            return effect.cancel(status_message="Lever is unavailable")
        if control_value(target) != desired_value:
            actions = target.get_use_actions(self.source_entity_uuid)
            if not actions:
                return effect.cancel(status_message="Linked item cannot change state")
            action = actions[0].instantiate() if actions[0].template else actions[0]
            result = action.apply(parent_event=effect)
            if result is None or result.canceled or control_value(target) != desired_value:
                return effect.cancel(status_message="Linked item did not change state")
        if lever.is_active:
            lever.is_engaged = next_engaged
            lever.publish_location_state(ItemLocation.FLOOR, parent_event=effect)
        return effect.with_updates(status_message="Lever engaged" if next_engaged else "Lever disengaged")


class ControlLever(UsableItem):
    """A reusable handle with one private, explicitly typed item connection."""

    name: str = "Control Lever"
    is_pickable: bool = False
    is_engaged: bool = False
    link: LeverLink

    def get_linked_item(self) -> WallTorch | DirectionalDoor | None:
        return linked_item(self.link)

    def to_item_presentation_state(self, *, stack_count: Optional[int] = None) -> ItemPresentationState:
        return super().to_item_presentation_state(stack_count=stack_count).model_copy(
            update={"is_engaged": self.is_engaged},
        )

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        if not self.is_active:
            return []
        return [self.bind_dynamic_use_action(ToggleLeverAction(
            source_entity_uuid=user_entity_uuid,
            source_item_uuid=self.uuid,
            template=True,
        ))]


class OpenChestAction(BaseAction):
    """Open a chest without transferring its private contents."""

    name: str = "Open Chest"
    target_type: TargetType = TargetType.SELF
    costs: List[Cost] = Field(default_factory=list)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        chest = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        if not isinstance(chest, StorageChest) or not chest.is_active or chest.is_open:
            return declaration_event.cancel(status_message="Chest cannot open")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        chest = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        if not isinstance(chest, StorageChest) or not chest.is_active:
            return execution_event.cancel(status_message="Chest not found")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        if not effect.canceled:
            chest.set_open(True, parent_event=effect)
        return effect


class CloseChestAction(BaseAction):
    """Close a chest independently of its remaining contents."""

    name: str = "Close Chest"
    target_type: TargetType = TargetType.SELF
    costs: List[Cost] = Field(default_factory=list)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        chest = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        if not isinstance(chest, StorageChest) or not chest.is_active or not chest.is_open:
            return declaration_event.cancel(status_message="Chest cannot close")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        chest = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        if not isinstance(chest, StorageChest) or not chest.is_active:
            return execution_event.cancel(status_message="Chest not found")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        if not effect.canceled:
            chest.set_open(False, parent_event=effect)
        return effect


class LootAllAction(BaseAction):
    """Transfer all items from a container to the entity's inventory."""

    name: str = Field(default="Loot All", description="Action name for looting a chest.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Chest looting targets the source user and resolves through source_item_uuid.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for looting a chest.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the chest item this action loots.",
    )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No chest linked")
        chest = BaseBlock.get(self.source_item_uuid)
        if not isinstance(chest, StorageChest) or not chest.is_active:
            return declaration_event.cancel(status_message="Chest not found")
        if not chest.is_open:
            return declaration_event.cancel(status_message="Chest is closed")
        if not chest.chest_inventory.items:
            return declaration_event.cancel(status_message="Chest is empty")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No chest linked")
        chest = BaseBlock.get(self.source_item_uuid)
        if not isinstance(chest, StorageChest) or not chest.is_active:
            return execution_event.cancel(status_message="Chest not found")
        looted = 0
        for item in list(chest.chest_inventory.items.values()):
            if entity.loot_item(item, parent_event=execution_event):
                looted += 1
        effect = execution_event.phase_to(
            EventPhase.EFFECT, status_message=f"Looted {looted} items")
        return effect.with_updates(
            status_message=f"Looted {looted} items from chest")


class StorageChest(UsableItem):
    """A fixed container with an independent lid and optional looting/breakage."""

    is_open: bool = False

    name: str = Field(default="Chest", description="Display name for the storage chest.")
    is_pickable: bool = Field(default=False, description="Chests are fixed environment objects by default.")
    map_char: str = Field(default="\u03a9", description="Map glyph for the storage chest.")
    is_targetable: bool = Field(default=False, description="Whether attacks can target this chest.")
    chest_inventory: Inventory = Field(
        default_factory=lambda: Inventory(source_entity_uuid=uuid4(), name="Chest Storage"),
        description="Inventory block containing nested chest contents.",
    )

    def get_spatial_open_state(self) -> bool:
        return self.is_open

    def set_open(self, is_open: bool, *, parent_event: Event) -> None:
        if not self.is_active or self.is_open == is_open:
            return
        self.is_open = is_open
        self.publish_location_state(ItemLocation.FLOOR, parent_event=parent_event)

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        if not self.is_active:
            return []
        lid_action = CloseChestAction if self.is_open else OpenChestAction
        actions = [self.bind_dynamic_use_action(lid_action(
            source_entity_uuid=user_entity_uuid,
            source_item_uuid=self.uuid,
            template=True,
        ))]
        if self.is_open and self.chest_inventory.items:
            actions.extend(super().get_use_actions(user_entity_uuid))
        return actions

    def get_storage_block(self) -> BaseBlock:
        """Expose contained items through the canonical item-storage capability."""
        return self.chest_inventory

    def _on_destroy(self, parent_event: Optional[Event]) -> None:
        """Spill all contents onto the ground at chest's position."""
        pos = self.position
        if pos is None:
            return
        for item_uuid in list(self.chest_inventory.items.keys()):
            item = self.chest_inventory.remove_item(item_uuid)
            if item:
                item.owner_uuid = None
                item.stored_in_uuid = None
                item.place_on_grid(pos, parent_event=parent_event.uuid if parent_event is not None else None)


class RestAction(BaseAction):
    """Rest at a campfire to heal."""

    name: str = Field(default="Rest", description="Action name for taking a campfire rest.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Campfire rest targets the acting entity.")
    costs: List[Cost] = Field(default_factory=list, description="No-cost action-economy payload for campfire rest.")
    source_item_uuid: Optional[UUID] = Field(default=None, description="UUID of the campfire item used for rest.")

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")
        heal_amount = random.randint(1, 6)
        entity.receive_healing(
            heal_amount, entity.uuid,
            source_description="Campfire Rest",
            parent_event=execution_event.uuid
        )
        effect = execution_event.phase_to(
            EventPhase.EFFECT, status_message=f"Healed {heal_amount}")
        return effect.with_updates(
            status_message="Rested at campfire")


class CookAction(BaseAction):
    """Cook at a campfire for temporary HP."""

    name: str = Field(default="Cook", description="Action name for cooking at a campfire.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Campfire cooking targets the acting entity.")
    costs: List[Cost] = Field(default_factory=list, description="No-cost action-economy payload for campfire cooking.")
    source_item_uuid: Optional[UUID] = Field(default=None, description="UUID of the campfire item used for cooking.")

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")
        entity.health.add_temporary_hit_points(3, self.source_entity_uuid, parent_event=execution_event.uuid)
        effect = execution_event.phase_to(
            EventPhase.EFFECT, status_message="Gained 3 temp HP")
        return effect.with_updates(
            status_message="Cooked at campfire")


class ActivateDeviceAction(BaseAction):
    """Activate an arcane device. Requires Arcana proficiency (static pre_validate check)."""

    name: str = Field(default="Activate Device", description="Action name for using an arcane device.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Arcane devices target the acting entity.")
    costs: List[Cost] = Field(default_factory=list, description="No-cost action-economy payload for device activation.")
    source_item_uuid: Optional[UUID] = Field(default=None, description="UUID of the arcane device item being used.")
    heal_amount: int = Field(default=5, description="Hit points restored by the arcane device.")

    def validate_requirements_for_discovery(self) -> bool:
        """Require Arcana proficiency independently of action affordability."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False
        skill = entity.skill_set.get_skill(type_cast(SkillName, "arcana"))
        return (
            skill.proficiency
            and super().validate_requirements_for_discovery()
        )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Device activated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")
        entity.receive_healing(
            self.heal_amount, entity.uuid,
            source_description="Arcane Device",
            parent_event=execution_event.uuid
        )
        effect = execution_event.phase_to(EventPhase.EFFECT,
            status_message=f"Healed {self.heal_amount} HP")
        return effect.with_updates(status_message="Arcane device activated")


class ArcaneDevice(UsableItem):
    """Environment object requiring Arcana proficiency to use."""

    name: str = Field(default="Arcane Device", description="Display name for the arcane device.")
    is_pickable: bool = Field(default=False, description="Arcane devices are fixed environment objects.")
