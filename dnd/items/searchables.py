"""Searchable bodies: a desk, a false-backed wardrobe, a loose board, whose contents a Search frees."""

from typing import List, Literal, Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.actions import entity_action_economy_cost_evaluator
from dnd.blocks.base_item import BaseItem
from dnd.core.action_types import ActionSelection
from dnd.core.base_actions import ActionEvent, BaseAction, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import ConditionCategory, DurationType
from dnd.core.dice import RollType
from dnd.core.events import Event, EventPhase
from dnd.entity import Entity
from dnd.items.environment_interactables import StorageChest
from dnd.types.discovery import ActorScan
from dnd.types.physical_access import PhysicalAccess


class SearchGate(BaseCondition):
    """What a searchable body hides: its contents stay out of reach until a Search beats the DC.

    The body itself stays in plain view and senses are unaffected; every searchable body carries
    a gate, so being searchable says nothing about whether anything is inside.
    """

    name: str = Field(default="Search gate", description="Condition name.")
    description: str = Field(default="Its contents are only found by a search.", description="Rules summary.")
    condition_category: ConditionCategory = ConditionCategory.INTERNAL
    duration: Duration = Field(default_factory=lambda: Duration(duration=None, duration_type=DurationType.PERMANENT))
    dc: int = Field(default=13, ge=0)
    skill: Literal["perception", "investigation"] = "perception"
    found: bool = False

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not isinstance(BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None, StorageChest):
            return [], [], [], [], declaration_event.cancel(status_message="Only a body with contents can be searched")
        return [], [], [], [], declaration_event.phase_to(EventPhase.EFFECT)

    def gates_owner_contents(self) -> bool:
        return not self.found


def search_gate_on(item: BaseItem) -> SearchGate | None:
    return next((condition for condition in item.active_conditions.values() if isinstance(condition, SearchGate)), None)


class SearchBody(BaseAction):
    """Search one searchable body: its own skill against its DC; success frees its contents.

    The roll publishes no DC, and success and failure read alike when the body is empty.
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
        gate = search_gate_on(item) if isinstance(item, BaseItem) else None
        if gate is None:
            return "Nothing to search"
        return "Already searched" if gate.found else None

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        gate = search_gate_on(item) if isinstance(item, StorageChest) else None
        if not isinstance(entity, Entity) or not isinstance(item, StorageChest) or gate is None or gate.found:
            return execution_event.cancel(status_message="Nothing to search")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        roll = entity.roll_d20(entity.skill_bonus(target_entity_uuid=None, skill_name=gate.skill),
                               RollType.CHECK, skill_name=gate.skill, parent_event=effect.uuid)
        if roll.total >= gate.dc:
            gate.found = True
            if item.chest_inventory.items:
                return effect.with_updates(status_message=f"{entity.name} finds something in {item.name}")
        return effect.with_updates(status_message=f"{entity.name} finds nothing in {item.name}")


def install_search_gate(body: StorageChest, *, dc: int = 13,
                        skill: Literal["perception", "investigation"] = "perception") -> SearchGate:
    """Make one container's contents findable only by a Search."""
    gate = SearchGate(source_entity_uuid=body.uuid, target_entity_uuid=body.uuid, dc=dc, skill=skill)
    result = body.add_condition(gate)
    if result is None or result.canceled or not gate.applied:
        raise RuntimeError(f"{body.name} could not be made searchable")
    return gate
