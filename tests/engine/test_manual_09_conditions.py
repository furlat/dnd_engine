"""Focused checks for condition lifecycle."""

from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field

from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, ConditionApplicationEvent, Duration
from dnd.types.conditions import DurationType
from dnd.core.base_object import BaseObject
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import BaseValue, ModifiableValue
from dnd.entities.entity import Entity, EntityConfig
from dnd.entities.entity_creation import create_entity
from tests.engine.support import reset_combat_state


def reset_condition_state() -> None:
    """Clear global state touched by condition tutorial examples."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()


def create_tutorial_entity(
    name: str,
    position: tuple[int, int],
    faction: str | None,
) -> Entity:
    """Create a minimal actor for condition examples."""
    entity_id = uuid4()
    return create_entity(
        entity_id,
        entity_kind_id="test.tutorial_entity",
        name=name,
        config=EntityConfig(
            position=position,
            faction=faction,
            proficiency_bonus=2,
        ),
    )


class TutorialMarkerCondition(BaseCondition):
    """Minimal condition that reaches the effect phase and owns no artifacts."""

    name: str = "TutorialMarker"

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        event = declaration_event.phase_to(EventPhase.EXECUTION, condition=self)
        event = event.phase_to(EventPhase.EFFECT, condition=self)
        return [], [], [], [], event


class TutorialNoEffectCondition(BaseCondition):
    """Condition whose missing effect event makes application cancel."""

    name: str = "TutorialNoEffect"

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        return [], [], [], [], None


class TutorialProficiencyCondition(BaseCondition):
    """Condition that owns one modifier on a target value."""

    name: str = "TutorialProficiency"
    target_value_uuid: UUID = Field(description="Value that receives the condition bonus.")
    bonus: int = Field(default=1, description="Bonus applied while the condition is active.")

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        event = declaration_event.phase_to(EventPhase.EXECUTION, condition=self)
        value = ModifiableValue.get(self.target_value_uuid)
        if value is None:
            raise AssertionError(f"Missing tutorial value {self.target_value_uuid}")

        modifier = NumericalModifier(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            name="Tutorial Proficiency Bonus",
            value=self.bonus,
        )
        modifier_uuid = value.self_static.add_value_modifier(modifier)
        event = event.phase_to(EventPhase.EFFECT, condition=self)
        return [(value.uuid, modifier_uuid)], [], [], [], event


class TutorialChildCondition(BaseCondition):
    """Same-block child condition used by the parent tutorial effect."""

    name: str = "TutorialChild"

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        event = declaration_event.phase_to(EventPhase.EXECUTION, condition=self)
        event = event.phase_to(EventPhase.EFFECT, condition=self)
        return [], [], [], [], event


class TutorialParentCondition(BaseCondition):
    """Parent condition that applies one same-block child condition."""

    name: str = "TutorialParent"

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        if self.target_entity_uuid is None:
            raise AssertionError("Parent condition needs a target entity")
        target = Entity.get(self.target_entity_uuid)
        if target is None:
            raise AssertionError(f"Missing target entity {self.target_entity_uuid}")

        child = TutorialChildCondition(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
        )
        target.add_condition(child, parent_event=declaration_event)

        event = declaration_event.phase_to(EventPhase.EXECUTION, condition=self)
        event = event.phase_to(EventPhase.EFFECT, condition=self)
        return [], [], [child.uuid], [], event


def test_entity_condition_application_creates_events_and_indexes() -> None:
    """A successful condition application completes and indexes the condition."""
    reset_condition_state()
    hero = create_tutorial_entity("Hero", (1, 1), "heroes")
    goblin = create_tutorial_entity("Goblin", (2, 1), "monsters")
    condition = TutorialMarkerCondition(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=goblin.uuid,
    )

    completed = goblin.add_condition(condition)

    assert completed is not None
    assert isinstance(completed, ConditionApplicationEvent)
    assert completed.phase == EventPhase.COMPLETION
    assert completed.event_type == EventType.CONDITION_APPLICATION
    assert completed.condition is condition
    assert condition.applied is True
    assert condition.source_entity_name == "Hero"
    assert condition.target_entity_name == "Goblin"
    assert goblin.active_conditions["TutorialMarker"] is condition
    assert goblin.active_conditions_by_uuid[condition.uuid] is condition
    assert goblin.active_conditions_by_source[hero.uuid] == ["TutorialMarker"]

    phases = {
        event.phase
        for event in EventQueue.get_events_by_type(EventType.CONDITION_APPLICATION)
        if event.lineage_uuid == completed.lineage_uuid
    }
    assert phases == {
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    }


def test_missing_effect_event_cancels_application_without_indexing() -> None:
    """A condition must return an effect event before it can become active."""
    reset_condition_state()
    hero = create_tutorial_entity("Hero", (1, 1), "heroes")
    goblin = create_tutorial_entity("Goblin", (2, 1), "monsters")
    condition = TutorialNoEffectCondition(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=goblin.uuid,
    )

    canceled = goblin.add_condition(condition)

    assert canceled is not None
    assert canceled.canceled is True
    assert canceled.phase == EventPhase.CANCEL
    assert condition.applied is False
    assert "TutorialNoEffect" not in goblin.active_conditions
    assert condition.uuid not in goblin.active_conditions_by_uuid


def test_modifier_condition_owns_and_cleans_its_bonus() -> None:
    """A condition-owned modifier is removed when the condition ends."""
    reset_condition_state()
    hero = create_tutorial_entity("Hero", (1, 1), "heroes")
    goblin = create_tutorial_entity("Goblin", (2, 1), "monsters")
    base_proficiency = goblin.proficiency_bonus.normalized_score
    condition = TutorialProficiencyCondition(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=goblin.uuid,
        target_value_uuid=goblin.proficiency_bonus.uuid,
        bonus=3,
    )

    goblin.add_condition(condition)
    modifier_uuid = condition.modifers_uuids[goblin.proficiency_bonus.uuid][0]

    assert goblin.proficiency_bonus.normalized_score == base_proficiency + 3
    assert modifier_uuid in goblin.proficiency_bonus.self_static.value_modifiers

    goblin.remove_condition("TutorialProficiency")

    assert goblin.proficiency_bonus.normalized_score == base_proficiency
    assert modifier_uuid not in goblin.proficiency_bonus.self_static.value_modifiers
    assert condition.applied is False
    assert goblin.active_conditions == {}


def test_same_name_condition_replaces_and_cleans_the_old_condition() -> None:
    """A newer condition with the same name replaces the old active condition."""
    reset_condition_state()
    hero = create_tutorial_entity("Hero", (1, 1), "heroes")
    goblin = create_tutorial_entity("Goblin", (2, 1), "monsters")
    base_proficiency = goblin.proficiency_bonus.normalized_score
    first = TutorialProficiencyCondition(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=goblin.uuid,
        target_value_uuid=goblin.proficiency_bonus.uuid,
        bonus=5,
    )
    second = TutorialProficiencyCondition(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=goblin.uuid,
        target_value_uuid=goblin.proficiency_bonus.uuid,
        bonus=2,
    )

    goblin.add_condition(first)
    first_modifier_uuid = first.modifers_uuids[goblin.proficiency_bonus.uuid][0]
    assert goblin.proficiency_bonus.normalized_score == base_proficiency + 5

    goblin.add_condition(second)
    second_modifier_uuid = second.modifers_uuids[goblin.proficiency_bonus.uuid][0]

    assert first.applied is False
    assert second.applied is True
    assert goblin.active_conditions == {"TutorialProficiency": second}
    assert first_modifier_uuid not in goblin.proficiency_bonus.self_static.value_modifiers
    assert second_modifier_uuid in goblin.proficiency_bonus.self_static.value_modifiers
    assert goblin.proficiency_bonus.normalized_score == base_proficiency + 2


def test_duration_advancement_expires_and_removes_condition() -> None:
    """Round duration progression removes an expired condition through cleanup."""
    reset_condition_state()
    hero = create_tutorial_entity("Hero", (1, 1), "heroes")
    goblin = create_tutorial_entity("Goblin", (2, 1), "monsters")
    condition = TutorialMarkerCondition(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=goblin.uuid,
        duration=Duration(duration=1, duration_type=DurationType.ROUNDS),
    )

    goblin.add_condition(condition)
    removed = goblin.advance_duration_condition("TutorialMarker", skip_save_throw=True)

    assert removed is True
    assert condition.applied is False
    assert "TutorialMarker" not in goblin.active_conditions
    assert condition.duration.duration == 0


def test_parent_condition_removal_cascades_to_same_block_child_condition() -> None:
    """Removing a parent condition removes its same-block child condition."""
    reset_condition_state()
    hero = create_tutorial_entity("Hero", (1, 1), "heroes")
    goblin = create_tutorial_entity("Goblin", (2, 1), "monsters")
    parent = TutorialParentCondition(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=goblin.uuid,
    )

    goblin.add_condition(parent)
    child = BaseCondition.get(parent.sub_conditions[0])

    assert isinstance(child, TutorialChildCondition)
    assert parent.applied is True
    assert child.applied is True
    assert goblin.active_conditions["TutorialParent"] is parent
    assert goblin.active_conditions["TutorialChild"] is child

    goblin.remove_condition("TutorialParent")

    assert parent.applied is False
    assert child.applied is False
    assert "TutorialParent" not in goblin.active_conditions
    assert "TutorialChild" not in goblin.active_conditions
