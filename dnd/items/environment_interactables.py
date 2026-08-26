"""Runtime actions and item types for interactive environment objects."""

import random
from typing import Optional, List, cast as type_cast
from uuid import UUID, uuid4
from pydantic import Field

from dnd.core.base_actions import (
    BaseAction,
    TargetType,
    Cost,
)
from dnd.core.events.action_events import (
    ActionEvent,
)
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
)
from dnd.core.events.item_events import ItemState
from dnd.types.abilities import SkillName
from dnd.types.items import ItemLocation
from dnd.core.gridmap import get_map
from dnd.blocks.base_item import (
    UsableItem,
)
from dnd.blocks.inventory import Inventory
from dnd.spatial.environmental_conditions import SpikeTrap
from dnd.entities.entity import Entity


class PullLeverAction(BaseAction):
    """Deactivate one linked, independently owned spike condition."""

    name: str = Field(default="Pull Lever", description="Action name for pulling a trap lever.")
    description: str = Field(default="Deactivates a trap", description="Action description shown for trap levers.")
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
        description="Exact spike condition UUID removed when this lever is pulled.",
    )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.trap_condition_uuid is None:
            return declaration_event.cancel(status_message="No trap linked")
        condition = BaseCondition.get(self.trap_condition_uuid)
        if not isinstance(condition, SpikeTrap) or not condition.applied:
            return declaration_event.cancel(status_message="Linked trap is unavailable")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.trap_condition_uuid is None:
            return execution_event.cancel(status_message="No trap linked")
        condition = BaseCondition.get(self.trap_condition_uuid)
        if not isinstance(condition, SpikeTrap) or not condition.applied:
            return execution_event.cancel(status_message="Linked trap is unavailable")
        condition.deactivate(parent_event=execution_event)
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Trap deactivated")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Lever pulled")


class TrapLever(UsableItem):
    """Fixed lever fixture that usually has one charge and one use template."""

    name: str = Field(default="Trap Lever", description="Display name for the trap lever.")
    is_pickable: bool = Field(default=False, description="Trap levers are fixed environment objects.")

    def to_item_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemState:
        """Expose the exact authored condition target without serializing actions."""
        targets = {
            action.trap_condition_uuid
            for action in self.use_action_templates
            if isinstance(action, PullLeverAction)
            and action.trap_condition_uuid is not None
        }
        if len(targets) > 1:
            raise ValueError("Trap Lever has multiple distinct condition targets")
        linked_uuid = next(iter(targets), None)
        return super().to_item_state(stack_count=stack_count).model_copy(
            update={"linked_spatial_condition_uuid": linked_uuid},
        )


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
        if not isinstance(chest, StorageChest):
            return declaration_event.cancel(status_message="Chest not found")
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
        if not isinstance(chest, StorageChest):
            return execution_event.cancel(status_message="Chest not found")
        looted = 0
        for item_uuid in list(chest.chest_inventory.items.keys()):
            item = chest.chest_inventory.remove_item(item_uuid)
            if item and entity.loot_item(item):
                looted += 1
        effect = execution_event.phase_to(
            EventPhase.EFFECT, status_message=f"Looted {looted} items")
        return effect.phase_to(
            EventPhase.COMPLETION, status_message=f"Looted {looted} items from chest")


class StorageChest(UsableItem):
    """A chest that can be looted. Optionally breakable."""

    name: str = Field(default="Chest", description="Display name for the storage chest.")
    is_pickable: bool = Field(default=False, description="Chests are fixed environment objects by default.")
    is_targetable: bool = Field(default=False, description="Whether attacks can target this chest.")
    chest_inventory: Inventory = Field(
        default_factory=lambda: Inventory(source_entity_uuid=uuid4(), name="Chest Storage"),
        description="Inventory block containing nested chest contents.",
    )

    def get_storage_block(self) -> BaseBlock:
        """Expose contained items through the canonical item-storage capability."""
        return self.chest_inventory

    def _on_destroy(self, parent_event: Optional[Event]) -> None:
        """Spill all contents onto the ground at chest's position."""
        _ = parent_event
        pos = get_map().get_object_position(self.uuid)
        if pos is None:
            return
        for item_uuid in list(self.chest_inventory.items.keys()):
            item = self.chest_inventory.remove_item(item_uuid)
            if item:
                item.owner_uuid = None
                item.stored_in_uuid = None
                item.place_on_grid(pos)
                item.publish_location_state(
                    ItemLocation.FLOOR,
                    world_placement=get_map().get_object_placement(item.uuid),
                    parent_event=parent_event,
                )


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
        return effect.phase_to(
            EventPhase.COMPLETION, status_message="Rested at campfire")


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
        effect = execution_event.phase_to(
            EventPhase.EFFECT, status_message="Gained 3 temp HP")
        entity.grant_temporary_hit_points(
            3,
            self.source_entity_uuid,
            source_description="Campfire Cooking",
            parent_event=effect.uuid,
        )
        return effect.phase_to(
            EventPhase.COMPLETION, status_message="Cooked at campfire")


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
        return effect.phase_to(EventPhase.COMPLETION,
            status_message="Arcane device activated")


class ArcaneDevice(UsableItem):
    """Environment object requiring Arcana proficiency to use."""

    name: str = Field(default="Arcane Device", description="Display name for the arcane device.")
    is_pickable: bool = Field(default=False, description="Arcane devices are fixed environment objects.")
