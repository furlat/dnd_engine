"""Focused checks for blocks, ownership, context, and cleanup."""

from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field

from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_object import BaseObject
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
)
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import BaseValue, ModifiableValue


class TutorialLeafBlock(BaseBlock):
    """Nested tutorial block with one owned value."""

    leaf_value: ModifiableValue = Field(description="Value owned by the leaf block.")


class TutorialSheetBlock(BaseBlock):
    """Tutorial block with one direct value and one child block."""

    armor_class: ModifiableValue = Field(description="Value owned directly by the sheet.")
    leaf: TutorialLeafBlock = Field(description="Nested child block.")


class TutorialMarkerCondition(BaseCondition):
    """Condition with lifecycle state and no modifier side effects."""

    name: str = "TutorialMarker"

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        event = declaration_event.phase_to(EventPhase.EXECUTION)
        event = event.phase_to(EventPhase.EFFECT)
        return [], [], [], [], event


class TutorialArmorBonusCondition(BaseCondition):
    """Condition that owns one numerical modifier on a tutorial value."""

    name: str = "TutorialArmorBonus"
    target_value_uuid: UUID = Field(description="Value that receives the bonus.")
    bonus: int = Field(default=2, description="Armor bonus while the condition is active.")

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        event = declaration_event.phase_to(EventPhase.EXECUTION)
        value = ModifiableValue.get(self.target_value_uuid)
        if value is None:
            raise AssertionError(f"Missing tutorial value {self.target_value_uuid}")

        modifier = NumericalModifier(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            name="Tutorial Armor Bonus",
            value=self.bonus,
        )
        modifier_uuid = value.self_static.add_value_modifier(modifier)
        event = event.phase_to(EventPhase.EFFECT)
        return [(value.uuid, modifier_uuid)], [], [], [], event


def reset_block_state() -> None:
    """Clear global state touched by block tutorial examples."""
    EventQueue.reset()
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()


def create_tutorial_value(source_entity_uuid: UUID, name: str, base_value: int) -> ModifiableValue:
    """Create a named value for the tutorial block graph."""
    return ModifiableValue.create(
        source_entity_uuid=source_entity_uuid,
        value_name=name,
        base_value=base_value,
    )


def create_tutorial_sheet(source_entity_uuid: UUID) -> TutorialSheetBlock:
    """Create a sheet block with one direct value and one nested block."""
    leaf = TutorialLeafBlock(
        source_entity_uuid=source_entity_uuid,
        name="Tutorial Leaf",
        leaf_value=create_tutorial_value(source_entity_uuid, "Leaf Bonus", 3),
    )
    return TutorialSheetBlock(
        source_entity_uuid=source_entity_uuid,
        name="Tutorial Sheet",
        armor_class=create_tutorial_value(source_entity_uuid, "Armor Class", 10),
        leaf=leaf,
    )


def test_blocks_discover_direct_children_values_and_deep_values() -> None:
    """Blocks index direct owned fields and can traverse values recursively."""
    reset_block_state()
    hero_id = uuid4()

    sheet = create_tutorial_sheet(hero_id)

    assert BaseBlock.get(sheet.uuid) is sheet
    assert BaseBlock.get(sheet.leaf.uuid) is sheet.leaf
    assert sheet.get_value_from_name("Armor Class") is sheet.armor_class
    assert sheet.get_block_from_name("Tutorial Leaf") is sheet.leaf
    assert sheet.get_value_from_name("Leaf Bonus") is None

    assert sheet.get_values() == [sheet.armor_class]
    assert {value.uuid for value in sheet.get_values(deep=True)} == {
        sheet.armor_class.uuid,
        sheet.leaf.leaf_value.uuid,
    }
    assert sheet.values_dict_name_uuid == {"Armor Class": sheet.armor_class.uuid}
    assert sheet.blocks_dict_name_uuid == {"Tutorial Leaf": sheet.leaf.uuid}


def test_constructor_normalizes_source_target_and_context_into_the_block_tree() -> None:
    """A parent block normalizes explicit child fields to its own identity."""
    reset_block_state()
    hero_id = uuid4()
    old_owner_id = uuid4()
    goblin_id = uuid4()
    context = {"range": "melee", "cover": "none"}

    foreign_leaf = TutorialLeafBlock(
        source_entity_uuid=old_owner_id,
        name="Foreign Leaf",
        leaf_value=create_tutorial_value(old_owner_id, "Leaf Bonus", 1),
    )
    foreign_armor = create_tutorial_value(old_owner_id, "Armor Class", 12)

    sheet = TutorialSheetBlock(
        source_entity_uuid=hero_id,
        target_entity_uuid=goblin_id,
        target_entity_name="Goblin",
        context=context,
        name="Tutorial Sheet",
        armor_class=foreign_armor,
        leaf=foreign_leaf,
    )

    assert sheet.armor_class.source_entity_uuid == hero_id
    assert sheet.leaf.source_entity_uuid == hero_id
    assert sheet.leaf.leaf_value.source_entity_uuid == hero_id
    assert sheet.armor_class.target_entity_uuid == goblin_id
    assert sheet.leaf.target_entity_uuid == goblin_id
    assert sheet.leaf.leaf_value.target_entity_uuid == goblin_id
    assert sheet.armor_class.context == context
    assert sheet.leaf.context == context
    assert sheet.leaf.leaf_value.context == context


def test_target_and_context_propagation_reaches_values_and_children() -> None:
    """Target and context changes propagate through a block's owned tree."""
    reset_block_state()
    hero_id = uuid4()
    goblin_id = uuid4()
    context = {"range": "melee"}
    sheet = create_tutorial_sheet(hero_id)

    sheet.set_target_entity(goblin_id, "Goblin")
    sheet.set_context(context)

    assert sheet.target_entity_uuid == goblin_id
    assert sheet.armor_class.target_entity_uuid == goblin_id
    assert sheet.armor_class.self_static.target_entity_uuid == goblin_id
    assert sheet.armor_class.to_target_contextual.target_entity_uuid == goblin_id
    assert sheet.leaf.target_entity_uuid == goblin_id
    assert sheet.leaf.leaf_value.target_entity_uuid == goblin_id

    assert sheet.context is context
    assert sheet.armor_class.context is context
    assert sheet.armor_class.self_contextual.context is context
    assert sheet.armor_class.to_target_contextual.context is context
    assert sheet.armor_class.self_static.context is None
    assert sheet.leaf.context is context
    assert sheet.leaf.leaf_value.context is context

    sheet.clear()

    assert sheet.target_entity_uuid is None
    assert sheet.armor_class.target_entity_uuid is None
    assert sheet.armor_class.from_target_static is None
    assert sheet.context is None
    assert sheet.armor_class.self_contextual.context is None
    assert sheet.leaf.leaf_value.context is None


def test_condition_lifecycle_is_opt_in_and_cleanup_removes_owned_modifiers() -> None:
    """Blocks only apply conditions when enabled, and cleanup removes bonuses."""
    reset_block_state()
    hero_id = uuid4()
    inert_sheet = create_tutorial_sheet(hero_id)
    inert_condition = TutorialMarkerCondition(
        source_entity_uuid=hero_id,
        target_entity_uuid=inert_sheet.uuid,
    )

    assert inert_sheet.add_condition(inert_condition) is None
    assert inert_sheet.active_conditions == {}
    assert inert_condition.applied is False

    active_sheet = create_tutorial_sheet(hero_id)
    active_sheet.allow_events_conditions = True
    armor_bonus = TutorialArmorBonusCondition(
        source_entity_uuid=hero_id,
        target_entity_uuid=active_sheet.uuid,
        target_value_uuid=active_sheet.armor_class.uuid,
        bonus=4,
    )

    base_armor_class = active_sheet.armor_class.normalized_score
    applied_event = active_sheet.add_condition(armor_bonus)

    assert applied_event is not None
    assert applied_event.phase == EventPhase.COMPLETION
    assert active_sheet.active_conditions["TutorialArmorBonus"] is armor_bonus
    assert active_sheet.active_conditions_by_uuid[armor_bonus.uuid] is armor_bonus
    assert active_sheet.active_conditions_by_source[hero_id] == ["TutorialArmorBonus"]
    assert active_sheet.armor_class.normalized_score == base_armor_class + 4

    active_sheet.remove_condition("TutorialArmorBonus")

    assert active_sheet.armor_class.normalized_score == base_armor_class
    assert active_sheet.active_conditions == {}
    assert armor_bonus.applied is False


def test_linked_condition_cleanup_crosses_block_boundaries() -> None:
    """Removing a parent condition also removes linked child conditions."""
    reset_block_state()
    hero_id = uuid4()
    parent_sheet = create_tutorial_sheet(hero_id)
    child_sheet = create_tutorial_sheet(hero_id)
    parent_sheet.allow_events_conditions = True
    child_sheet.allow_events_conditions = True

    parent_condition = TutorialMarkerCondition(
        source_entity_uuid=hero_id,
        target_entity_uuid=parent_sheet.uuid,
    )
    child_condition = TutorialMarkerCondition(
        source_entity_uuid=hero_id,
        target_entity_uuid=child_sheet.uuid,
        name="LinkedTutorialMarker",
    )

    parent_sheet.add_condition(parent_condition)
    child_sheet.add_condition(child_condition)
    parent_condition.add_linked_condition(child_sheet.uuid, child_condition.uuid)

    assert "TutorialMarker" in parent_sheet.active_conditions
    assert "LinkedTutorialMarker" in child_sheet.active_conditions
    assert child_condition.parent_link == (parent_sheet.uuid, parent_condition.uuid)

    parent_sheet.remove_condition("TutorialMarker")

    assert parent_sheet.active_conditions == {}
    assert child_sheet.active_conditions == {}
    assert parent_condition.applied is False
    assert child_condition.applied is False
