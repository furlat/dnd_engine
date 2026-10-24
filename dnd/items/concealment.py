"""Hidden objects: a condition that hides an object's presence, what it does, or what it holds."""

from typing import List, Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.actions import entity_action_economy_cost_evaluator
from dnd.blocks.base_item import BaseItem
from dnd.core.action_types import ActionSelection
from dnd.core.base_actions import ActionEvent, BaseAction, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.concealment_types import Camouflage, ConcealedAspect, concealment, with_failure
from dnd.core.condition_types import ConditionCategory, DurationType
from dnd.core.dice import RollType
from dnd.core.events import Event, EventPhase
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.items.environment_interactables import StorageChest
from dnd.types.abilities import SkillName
from dnd.types.discovery import ActorScan
from dnd.types.physical_access import PhysicalAccess


class Concealed(BaseCondition):
    """What an object hides, as its `concealment` record: its presence (a note, loot, a lever in an alcove),
    what it does (a secret door, a hidden button) or what it holds (a desk's drawer, a false back).

    The record holds the DC, the finding skill, who knows it and who searched and missed. Perception notices
    a hidden presence or hidden actions, and the area Search finds them; only Search Inside finds hidden
    contents, and finding them removes this condition: the compartment is then open for everyone. An object
    holds one per aspect, each named by its aspect (`install_concealment`).
    """

    name: str = Field(default="Concealed", description="Condition name.")
    description: str = Field(default="Something about it is hidden.", description="Rules summary.")
    condition_category: ConditionCategory = ConditionCategory.INTERNAL
    duration: Duration = Field(default_factory=lambda: Duration(duration=None, duration_type=DurationType.PERMANENT))

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        host = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if self.concealment is None or not isinstance(host, BaseItem):
            return [], [], [], [], declaration_event.cancel(status_message="Only an object's record can hide it")
        if self.concealment.aspect is ConcealedAspect.CONTENTS and not isinstance(host, StorageChest):
            return [], [], [], [], declaration_event.cancel(status_message="Only a body with contents can hide them")
        return [], [], [], [], declaration_event.phase_to(EventPhase.EFFECT)

    def on_membership_changed(self, event: Event) -> None:
        """A placed object hidden or found again is re-observed by those who see its cell."""
        host = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if (self.concealment is not None and self.concealment.aspect is ConcealedAspect.PRESENCE
                and host is not None and get_map().get_object_position(host.uuid) is not None):
            host._notify_perceivability_changed(parent_event=event.uuid)


class SearchInside(BaseAction):
    """Search one desk, cabinet, board or body for hidden contents: its record's skill against its DC.

    Success removes the hiding condition, so the contents are open for everyone; a miss is the searcher's for
    good, one try per creature. The roll publishes no DC, and success and failure read alike when it is empty.
    """

    name: str = Field(default="Search Inside", description="Action name.")
    description: str = Field(default="Search this for anything tucked away", description="Player-facing summary.")
    target_type: TargetType = Field(default=TargetType.OBJECT, description="Targets the searchable body.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Search Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def get_physical_access(self) -> Optional[PhysicalAccess]:
        return PhysicalAccess.HAND

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        item = BaseBlock.get(selection.target_uuids[0]) if selection.target_uuids else None
        holder = item.concealment_holder(ConcealedAspect.CONTENTS) if item is not None else None
        record = holder.concealment if holder is not None else None
        if record is None:
            return "Nothing to search"
        return "Already searched" if self.source_entity_uuid in record.failed_by else None

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        holder = item.concealment_holder(ConcealedAspect.CONTENTS) if isinstance(item, StorageChest) else None
        record = holder.concealment if holder is not None else None
        if not isinstance(entity, Entity) or not isinstance(item, StorageChest) or holder is None or record is None:
            return execution_event.cancel(status_message="Nothing to search")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        roll = entity.roll_d20(entity.skill_bonus(target_entity_uuid=None, skill_name=record.skill),
                               RollType.CHECK, skill_name=record.skill, parent_event=effect.uuid)
        if roll.total < record.dc:
            get_map().record_concealment(((holder, with_failure(record, entity.uuid)),))
            return effect.with_updates(status_message=f"{entity.name} finds nothing in {item.name}")
        item.remove_condition_by_uuid(holder.uuid, parent_event=effect)  # its removal republishes the body
        return effect.with_updates(status_message=(f"{entity.name} finds something in {item.name}"
                                                   if item.chest_inventory.items else f"{entity.name} finds nothing in {item.name}"))


def install_concealment(item: BaseItem, aspect: ConcealedAspect, dc: int, *, skill: SkillName = "perception",
                        shows: Optional[Camouflage] = None) -> Concealed:
    """Hide one object's presence, actions or contents behind a DC, or camouflage it as what it `shows`."""
    hidden = Concealed(name=f"Concealed {aspect.value}", source_entity_uuid=item.uuid, target_entity_uuid=item.uuid,
                       concealment=concealment(dc, aspect, skill=skill, shows=shows))
    result = item.add_condition(hidden)
    if result is None or result.canceled or not hidden.applied:
        raise RuntimeError(f"{item.name} could not be hidden")
    return hidden
