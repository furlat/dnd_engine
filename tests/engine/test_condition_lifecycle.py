"""Engine semantic tests for condition application and cleanup."""

from contextlib import contextmanager
import random
from typing import Iterator
from uuid import UUID, uuid4

import pytest
from pydantic import Field

from dnd.blocks.base_item import (
    BaseItem,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, ConditionApplicationEvent, Duration
from dnd.types.conditions import DurationType
from dnd.core.base_object import BaseObject
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    SpatialHandler,
    Trigger,
)
from dnd.core.events.check_events import (
    SavingThrowEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import BaseValue, ModifiableValue
from dnd.entity import Entity, EntityConfig
from tests.engine.support import reset_combat_state


@contextmanager
def fixed_randint(value: int) -> Iterator[None]:
    """Force `random.randint()` to return one value inside the context."""
    original = random.randint
    random.randint = lambda _low, _high: value
    try:
        yield
    finally:
        random.randint = original


def reset_condition_state() -> None:
    """Clear global state touched by these condition examples."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    get_map().create_rectangle(0, 0, 12, 12)


def configured_entity(
    name: str,
    position: tuple[int, int] = (1, 1),
    faction: str | None = "heroes",
) -> Entity:
    """Create a deterministic entity for condition lifecycle tests."""
    source_uuid = uuid4()
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=14),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=12),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(hit_dice_value=8, hit_dice_count=2, mode="maximums")
            ]
        ),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    return Entity.create(source_entity_uuid=source_uuid, name=name, config=config)


class EngineBookMarkerCondition(BaseCondition):
    """Minimal condition that applies through execution and effect phases."""

    name: str = "EngineBookMarker"

    def _apply(
        self, declaration_event: Event
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event]:
        event = declaration_event.phase_to(EventPhase.EXECUTION, condition=self)
        event = event.phase_to(EventPhase.EFFECT, condition=self)
        return [], [], [], [], event


class EngineBookNoEffectCondition(BaseCondition):
    """Condition whose `_apply()` intentionally does not produce an effect event."""

    name: str = "EngineBookNoEffect"

    def _apply(
        self, declaration_event: Event
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], None]:
        return [], [], [], [], None


class EngineBookCanceledEffectCondition(BaseCondition):
    """Condition whose `_apply()` returns a canceled event after starting."""

    name: str = "EngineBookCanceledEffect"

    def _apply(
        self, declaration_event: Event
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event]:
        event = declaration_event.phase_to(EventPhase.EXECUTION, condition=self)
        return [], [], [], [], event.cancel("canceled during condition application")


class EngineBookExceptionalStateCondition(BaseCondition):
    """Condition that installs direct state and then fails during apply."""

    name: str = "EngineBookExceptionalState"
    provisional_state_active: bool = Field(default=False, exclude=True)

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event]:
        del declaration_event
        self.provisional_state_active = True
        raise RuntimeError("condition apply failed after provisional state")

    def _release_owned_runtime_state(
        self,
        *,
        parent_event: Event | None = None,
    ) -> None:
        del parent_event
        self.provisional_state_active = False


class EngineBookModifierCondition(BaseCondition):
    """Condition that owns a single numerical modifier on one value."""

    name: str = "EngineBookModifier"
    target_value_uuid: UUID = Field(description="ModifiableValue UUID to modify.")
    bonus: int = Field(default=1, description="Numerical bonus applied by the condition.")

    def _apply(
        self, declaration_event: Event
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event]:
        value = ModifiableValue.get(self.target_value_uuid)
        assert isinstance(value, ModifiableValue)
        modifier_uuid = value.self_static.add_value_modifier(
            NumericalModifier(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                name=self.name,
                value=self.bonus,
            )
        )
        event = declaration_event.phase_to(EventPhase.EXECUTION, condition=self)
        event = event.phase_to(EventPhase.EFFECT, condition=self)
        return [(value.uuid, modifier_uuid)], [], [], [], event


class EngineBookSubCondition(BaseCondition):
    """Child condition used to verify same-block recursive cleanup."""

    name: str = "EngineBookSub"

    def _apply(
        self, declaration_event: Event
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event]:
        event = declaration_event.phase_to(EventPhase.EXECUTION, condition=self)
        event = event.phase_to(EventPhase.EFFECT, condition=self)
        return [], [], [], [], event


class EngineBookParentCondition(BaseCondition):
    """Parent condition that applies one sub-condition to the same entity."""

    name: str = "EngineBookParent"

    def _apply(
        self, declaration_event: Event
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid)
        assert isinstance(target, Entity)
        child = EngineBookSubCondition(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
        )
        target.add_condition(child, parent_event=declaration_event)
        event = declaration_event.phase_to(EventPhase.EXECUTION, condition=self)
        event = event.phase_to(EventPhase.EFFECT, condition=self)
        return [], [], [child.uuid], [], event


class EngineBookHandlerCondition(BaseCondition):
    """Condition that owns one trigger-based event handler."""

    name: str = "EngineBookHandler"
    calls: list[str] = Field(default_factory=list, exclude=True)

    def _apply(
        self, declaration_event: Event
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event]:
        assert self.target_entity_uuid is not None

        def record_call(event: Event, _source_uuid: UUID) -> Event:
            self.calls.append(event.status_message or "called")
            return event

        handler = EventHandler(
            name="EngineBookHandler owned callback",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=record_call,
        )
        EventQueue.add_event_handler(handler)
        event = declaration_event.phase_to(EventPhase.EXECUTION, condition=self)
        event = event.phase_to(EventPhase.EFFECT, condition=self)
        return [], [handler.uuid], [], [], event


class EngineBookSpatialCondition(BaseCondition):
    """Condition that owns one position-indexed spatial handler."""

    name: str = "EngineBookSpatial"
    positions: set[tuple[int, int]] = Field(
        default_factory=set,
        description="Grid positions where the owned spatial handler fires.",
    )
    calls: list[tuple[int, int]] = Field(default_factory=list, exclude=True)

    def _apply(
        self, declaration_event: Event
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event]:
        def record_entry(event: Event, _source_uuid: UUID) -> Event:
            self.calls.append(getattr(event, "position"))
            return event

        handler = SpatialHandler(
            name="EngineBookSpatial owned callback",
            source_entity_uuid=self.source_entity_uuid,
            positions=self.positions,
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT,
            event_processor=record_entry,
        )
        EventQueue.add_spatial_handler(handler)
        event = declaration_event.phase_to(EventPhase.EXECUTION, condition=self)
        event = event.phase_to(EventPhase.EFFECT, condition=self)
        return [], [], [], [handler.uuid], event


def test_eb_07_001_entity_condition_application_events_and_indexes() -> None:
    """EB-07-001: Entity.add_condition creates events and indexes applied conditions."""
    reset_condition_state()
    source = configured_entity("Source", position=(1, 1))
    target = configured_entity("Target", position=(2, 1), faction="monsters")
    condition = EngineBookMarkerCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )

    completed = target.add_condition(condition)

    assert completed is not None
    assert isinstance(completed, ConditionApplicationEvent)
    assert completed.phase == EventPhase.COMPLETION
    assert completed.event_type == EventType.CONDITION_APPLICATION
    assert completed.condition is condition
    assert condition.applied is True
    assert condition.source_entity_name == "Source"
    assert condition.target_entity_name == "Target"
    assert target.active_conditions["EngineBookMarker"] is condition
    assert target.active_conditions_by_uuid[condition.uuid] is condition
    assert "EngineBookMarker" in target.active_conditions_by_source[source.uuid]

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


def test_eb_07_002_apply_without_effect_event_cancels_and_does_not_index() -> None:
    """EB-07-002: `_apply()` must return an effect event for application to stick."""
    reset_condition_state()
    source = configured_entity("Source")
    target = configured_entity("Target", position=(2, 1))
    condition = EngineBookNoEffectCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )

    canceled = target.add_condition(condition)

    assert canceled is not None
    assert canceled.canceled is True
    assert canceled.phase == EventPhase.CANCEL
    assert condition.applied is False
    assert "EngineBookNoEffect" not in target.active_conditions
    assert condition.uuid not in target.active_conditions_by_uuid


def test_spatial_handler_inherits_enabled_and_default_source_execution() -> None:
    """Spatial discovery adds no second callable contract over BaseHandler."""
    reset_condition_state()
    source_uuid = uuid4()
    calls: list[UUID] = []

    def record_source(event: Event, handler_source_uuid: UUID) -> Event:
        calls.append(handler_source_uuid)
        return event

    handler = SpatialHandler(
        source_entity_uuid=source_uuid,
        positions={(1, 1)},
        event_type=EventType.SPATIAL_ENTITY_ENTERED,
        event_phase=EventPhase.EFFECT,
        event_processor=record_source,
    )
    event = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.SPATIAL_ENTITY_ENTERED,
        phase=EventPhase.EFFECT,
    )

    assert handler(event) is event
    assert calls == [source_uuid]

    handler.enabled = False
    assert handler(event) is None
    assert calls == [source_uuid]


def test_eb_07_003_canceled_apply_event_discards_uncommitted_condition() -> None:
    """EB-07-003: a canceled application leaves no active or global identity."""
    reset_condition_state()
    source = configured_entity("Source")
    target = configured_entity("Target", position=(2, 1))
    condition = EngineBookCanceledEffectCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )

    canceled = target.add_condition(condition)

    assert canceled is not None
    assert canceled.phase == EventPhase.CANCEL
    assert canceled.canceled is True
    assert condition.applied is False
    assert "EngineBookCanceledEffect" not in target.active_conditions
    assert condition.uuid not in target.active_conditions_by_uuid
    assert BaseCondition.get(condition.uuid) is None
    assert not any(
        event.phase is EventPhase.COMPLETION
        for event in EventQueue.get_events_by_type(
            EventType.CONDITION_APPLICATION,
        )
        if event.lineage_uuid == canceled.lineage_uuid
    )


def test_exceptional_condition_apply_releases_direct_state_and_identity() -> None:
    """An exception inside `_apply()` rolls back subclass state and registry."""
    reset_condition_state()
    source = configured_entity("Source")
    target = configured_entity("Target", position=(2, 1))
    condition = EngineBookExceptionalStateCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )

    with pytest.raises(
        RuntimeError,
        match="condition apply failed after provisional state",
    ):
        target.add_condition(condition)

    assert condition.provisional_state_active is False
    assert condition.applied is False
    assert condition.uuid not in target.active_conditions_by_uuid
    assert BaseCondition.get(condition.uuid) is None


def test_canceled_condition_effect_rolls_back_provisional_modifier() -> None:
    """A veto at the effect boundary rolls back state created by `_apply()`."""
    reset_condition_state()
    source = configured_entity("Source")
    target = configured_entity("Target", position=(2, 1))
    original_bonus = target.proficiency_bonus.normalized_score

    def cancel_condition_effect(event: Event, _source_uuid: UUID) -> Event:
        return event.cancel("condition effect rejected")

    target.add_event_handler(EventHandler(
        name="Reject condition effect",
        source_entity_uuid=target.uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.CONDITION_APPLICATION,
                event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=target.uuid,
            ),
        ],
        event_processor=cancel_condition_effect,
    ))
    condition = EngineBookModifierCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
        target_value_uuid=target.proficiency_bonus.uuid,
        bonus=5,
    )

    canceled = target.add_condition(condition)

    assert canceled is not None
    assert canceled.canceled is True
    assert condition.applied is False
    assert target.proficiency_bonus.normalized_score == original_bonus
    assert "EngineBookModifier" not in target.active_conditions
    assert condition.uuid not in target.active_conditions_by_uuid
    assert BaseCondition.get(condition.uuid) is None


def test_canceled_condition_removal_preserves_active_indexes_and_state() -> None:
    """A removal veto leaves the condition fully active and addressable."""
    reset_condition_state()
    source = configured_entity("Source")
    target = configured_entity("Target", position=(2, 1))
    original_bonus = target.proficiency_bonus.normalized_score
    condition = EngineBookModifierCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
        target_value_uuid=target.proficiency_bonus.uuid,
        bonus=5,
    )
    target.add_condition(condition)

    def cancel_removal(event: Event, _source_uuid: UUID) -> Event:
        return event.cancel("condition removal rejected")

    target.add_event_handler(EventHandler(
        name="Reject condition removal",
        source_entity_uuid=target.uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.CONDITION_REMOVAL,
                event_phase=EventPhase.DECLARATION,
                event_target_entity_uuid=target.uuid,
            ),
        ],
        event_processor=cancel_removal,
    ))

    removed = target.remove_condition("EngineBookModifier")

    assert removed is False
    assert condition.applied is True
    assert target.proficiency_bonus.normalized_score == original_bonus + 5
    assert target.active_conditions["EngineBookModifier"] is condition
    assert target.active_conditions_by_uuid[condition.uuid] is condition
    assert "EngineBookModifier" in target.active_conditions_by_source[source.uuid]
    assert BaseCondition.get(condition.uuid) is condition


def test_eb_07_004_entity_immunity_and_application_save_cancel_before_apply() -> None:
    """EB-07-004: Entity gates can cancel a condition before `_apply()`."""
    reset_condition_state()
    source = configured_entity("Source")
    immune_target = configured_entity("Immune Target", position=(2, 1))
    immune_target.add_condition_immunity("EngineBookMarker")
    immune_condition = EngineBookMarkerCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=immune_target.uuid,
    )

    immune_result = immune_target.add_condition(immune_condition)

    assert immune_result is not None
    assert immune_result.canceled is True
    assert immune_condition.applied is False
    assert "EngineBookMarker" not in immune_target.active_conditions

    saving_target = configured_entity("Saving Target", position=(3, 1))
    saved_condition = EngineBookMarkerCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=saving_target.uuid,
        application_saving_throw=SavingThrowEvent(
            source_entity_uuid=source.uuid,
            target_entity_uuid=saving_target.uuid,
            ability_name="dexterity",
            dc=5,
        ),
    )

    with fixed_randint(20):
        save_result = saving_target.add_condition(saved_condition)

    assert save_result is not None
    assert save_result.canceled is True
    assert saved_condition.applied is False
    assert "EngineBookMarker" not in saving_target.active_conditions


def test_eb_07_005_same_name_replacement_cleans_old_condition_state() -> None:
    """EB-07-005: a newer same-name condition replaces and cleans the old one."""
    reset_condition_state()
    source = configured_entity("Source")
    target = configured_entity("Target", position=(2, 1))
    value_uuid = target.proficiency_bonus.uuid
    original_base = target.proficiency_bonus.normalized_score

    old_condition = EngineBookModifierCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
        target_value_uuid=value_uuid,
        bonus=5,
    )
    new_condition = EngineBookModifierCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
        target_value_uuid=value_uuid,
        bonus=2,
    )

    target.add_condition(old_condition)
    assert target.proficiency_bonus.normalized_score == original_base + 5

    target.add_condition(new_condition)

    assert old_condition.applied is False
    assert new_condition.applied is True
    assert target.active_conditions["EngineBookModifier"] is new_condition
    assert old_condition.uuid not in target.active_conditions_by_uuid
    assert target.proficiency_bonus.normalized_score == original_base + 2


def test_eb_07_006_parent_removal_cascades_to_same_block_subconditions() -> None:
    """EB-07-006: same-block sub-conditions are removed with their parent."""
    reset_condition_state()
    source = configured_entity("Source")
    target = configured_entity("Target", position=(2, 1))
    parent = EngineBookParentCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )

    target.add_condition(parent)

    assert parent.applied is True
    assert len(parent.sub_conditions) == 1
    sub_condition = BaseCondition.get(parent.sub_conditions[0])
    assert isinstance(sub_condition, EngineBookSubCondition)
    assert sub_condition.applied is True
    assert target.active_conditions["EngineBookParent"] is parent
    assert target.active_conditions["EngineBookSub"] is sub_condition

    target.remove_condition("EngineBookParent")

    assert parent.applied is False
    assert sub_condition.applied is False
    assert "EngineBookParent" not in target.active_conditions
    assert "EngineBookSub" not in target.active_conditions


def test_eb_07_007_linked_conditions_clean_forward_and_notify_reverse() -> None:
    """EB-07-007: linked child cleanup works both parent-to-child and child-to-parent."""
    reset_condition_state()
    source = configured_entity("Source")
    parent_block = configured_entity("Parent", position=(2, 1))
    child_block = configured_entity("Child", position=(3, 1), faction="monsters")

    forward_parent = EngineBookMarkerCondition(
        name="EngineBookLinkedParent",
        source_entity_uuid=source.uuid,
        target_entity_uuid=parent_block.uuid,
    )
    forward_child = EngineBookMarkerCondition(
        name="EngineBookLinkedChild",
        source_entity_uuid=source.uuid,
        target_entity_uuid=child_block.uuid,
    )
    parent_block.add_condition(forward_parent)
    child_block.add_condition(forward_child)
    forward_parent.add_linked_condition(child_block.uuid, forward_child.uuid)

    assert forward_child.parent_link == (parent_block.uuid, forward_parent.uuid)

    parent_block.remove_condition("EngineBookLinkedParent")

    assert forward_parent.applied is False
    assert forward_child.applied is False
    assert "EngineBookLinkedParent" not in parent_block.active_conditions
    assert "EngineBookLinkedChild" not in child_block.active_conditions

    reverse_parent = EngineBookMarkerCondition(
        name="EngineBookReverseParent",
        source_entity_uuid=source.uuid,
        target_entity_uuid=parent_block.uuid,
        child_removal_policy="last",
    )
    reverse_child = EngineBookMarkerCondition(
        name="EngineBookReverseChild",
        source_entity_uuid=source.uuid,
        target_entity_uuid=child_block.uuid,
    )
    parent_block.add_condition(reverse_parent)
    child_block.add_condition(reverse_child)
    reverse_parent.add_linked_condition(child_block.uuid, reverse_child.uuid)

    child_block.remove_condition("EngineBookReverseChild")

    assert reverse_child.applied is False
    assert reverse_parent.applied is False
    assert "EngineBookReverseParent" not in parent_block.active_conditions


def test_eb_07_008_owned_event_and_spatial_handlers_are_removed_on_cleanup() -> None:
    """EB-07-008: condition cleanup unregisters owned event and spatial handlers."""
    reset_condition_state()
    source = configured_entity("Source")
    target = configured_entity("Target", position=(2, 1))

    handler_condition = EngineBookHandlerCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(handler_condition)
    handler_uuid = handler_condition.event_handlers_uuids[0]

    Event(
        source_entity_uuid=target.uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="before cleanup",
    ).phase_to(EventPhase.EFFECT)
    assert handler_condition.calls == ["before cleanup"]

    target.remove_condition("EngineBookHandler")
    assert handler_uuid not in EventQueue._event_handlers
    assert EventHandler.get(handler_uuid) is None
    assert BaseCondition.get(handler_condition.uuid) is None

    Event(
        source_entity_uuid=target.uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="after cleanup",
    ).phase_to(EventPhase.EFFECT)
    assert handler_condition.calls == ["before cleanup"]

    spatial_condition = EngineBookSpatialCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
        positions={(4, 4)},
    )
    target.add_condition(spatial_condition)
    spatial_uuid = spatial_condition.spatial_handler_uuids[0]
    assert EventQueue.get_spatial_handlers_at((4, 4))

    target.move((4, 4))
    assert spatial_condition.calls == [(4, 4)]

    target.remove_condition("EngineBookSpatial")
    assert spatial_uuid not in EventQueue._spatial_handlers
    assert SpatialHandler.get(spatial_uuid) is None
    assert BaseCondition.get(spatial_condition.uuid) is None
    assert EventQueue.get_spatial_handlers_at((4, 4)) == []

    target.move((5, 4))
    target.move((4, 4))
    assert spatial_condition.calls == [(4, 4)]


def test_eb_07_009_entity_duration_advancement_expires_and_removes_condition() -> None:
    """EB-07-009: Entity duration advancement removes expired conditions."""
    reset_condition_state()
    source = configured_entity("Source")
    target = configured_entity("Target", position=(2, 1))
    condition = EngineBookMarkerCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
        duration=Duration(duration=1, duration_type=DurationType.ROUNDS),
    )

    target.add_condition(condition)

    removed = target.advance_duration_condition("EngineBookMarker", skip_save_throw=True)

    assert removed is True
    assert condition.applied is False
    assert "EngineBookMarker" not in target.active_conditions


def test_eb_07_010_baseblock_add_condition_skips_canceled_no_effect() -> None:
    """EB-07-010: BaseBlock.add_condition skips a canceled no-effect result."""
    reset_condition_state()
    source = configured_entity("Source")
    tile = get_map().get_tile(4, 4)
    assert tile is not None
    condition = EngineBookNoEffectCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=tile.uuid,
    )

    canceled = tile.add_condition(condition)

    assert canceled is not None
    assert canceled.phase == EventPhase.CANCEL
    assert canceled.canceled is True
    assert condition.applied is False
    assert "EngineBookNoEffect" not in tile.active_conditions
    assert condition.uuid not in tile.active_conditions_by_uuid
    assert tile.active_conditions_by_source[source.uuid] == []
    assert BaseCondition.get(condition.uuid) is None

    tile.remove_condition("EngineBookNoEffect")

    assert "EngineBookNoEffect" not in tile.active_conditions
    assert condition.uuid not in tile.active_conditions_by_uuid


def test_eb_07_011_child_removal_policies_any_last_and_none() -> None:
    """EB-07-011: linked child removal policy controls parent cleanup."""
    reset_condition_state()
    source = configured_entity("Source")

    any_parent_block = configured_entity("Any Parent", position=(1, 1))
    any_child_block_a = configured_entity("Any Child A", position=(2, 1), faction="monsters")
    any_child_block_b = configured_entity("Any Child B", position=(3, 1), faction="monsters")
    any_parent = EngineBookMarkerCondition(
        name="EngineBookAnyParent",
        source_entity_uuid=source.uuid,
        target_entity_uuid=any_parent_block.uuid,
        child_removal_policy="any",
    )
    any_child_a = EngineBookMarkerCondition(
        name="EngineBookAnyChildA",
        source_entity_uuid=source.uuid,
        target_entity_uuid=any_child_block_a.uuid,
    )
    any_child_b = EngineBookMarkerCondition(
        name="EngineBookAnyChildB",
        source_entity_uuid=source.uuid,
        target_entity_uuid=any_child_block_b.uuid,
    )
    any_parent_block.add_condition(any_parent)
    any_child_block_a.add_condition(any_child_a)
    any_child_block_b.add_condition(any_child_b)
    any_parent.add_linked_condition(any_child_block_a.uuid, any_child_a.uuid)
    any_parent.add_linked_condition(any_child_block_b.uuid, any_child_b.uuid)

    any_child_block_a.remove_condition("EngineBookAnyChildA")

    assert any_parent.applied is False
    assert any_child_a.applied is False
    assert any_child_b.applied is False
    assert "EngineBookAnyParent" not in any_parent_block.active_conditions
    assert "EngineBookAnyChildB" not in any_child_block_b.active_conditions

    last_parent_block = configured_entity("Last Parent", position=(4, 1))
    last_child_block_a = configured_entity("Last Child A", position=(5, 1), faction="monsters")
    last_child_block_b = configured_entity("Last Child B", position=(6, 1), faction="monsters")
    last_parent = EngineBookMarkerCondition(
        name="EngineBookLastParent",
        source_entity_uuid=source.uuid,
        target_entity_uuid=last_parent_block.uuid,
        child_removal_policy="last",
    )
    last_child_a = EngineBookMarkerCondition(
        name="EngineBookLastChildA",
        source_entity_uuid=source.uuid,
        target_entity_uuid=last_child_block_a.uuid,
    )
    last_child_b = EngineBookMarkerCondition(
        name="EngineBookLastChildB",
        source_entity_uuid=source.uuid,
        target_entity_uuid=last_child_block_b.uuid,
    )
    last_parent_block.add_condition(last_parent)
    last_child_block_a.add_condition(last_child_a)
    last_child_block_b.add_condition(last_child_b)
    last_parent.add_linked_condition(last_child_block_a.uuid, last_child_a.uuid)
    last_parent.add_linked_condition(last_child_block_b.uuid, last_child_b.uuid)

    last_child_block_a.remove_condition("EngineBookLastChildA")

    assert last_parent.applied is True
    assert last_child_a.applied is False
    assert last_child_b.applied is True
    assert last_parent_block.active_conditions["EngineBookLastParent"] is last_parent

    last_child_block_b.remove_condition("EngineBookLastChildB")

    assert last_parent.applied is False
    assert last_child_b.applied is False
    assert "EngineBookLastParent" not in last_parent_block.active_conditions

    none_parent_block = configured_entity("None Parent", position=(7, 1))
    none_child_block = configured_entity("None Child", position=(8, 1), faction="monsters")
    none_parent = EngineBookMarkerCondition(
        name="EngineBookNoneParent",
        source_entity_uuid=source.uuid,
        target_entity_uuid=none_parent_block.uuid,
        child_removal_policy="none",
    )
    none_child = EngineBookMarkerCondition(
        name="EngineBookNoneChild",
        source_entity_uuid=source.uuid,
        target_entity_uuid=none_child_block.uuid,
    )
    none_parent_block.add_condition(none_parent)
    none_child_block.add_condition(none_child)
    none_parent.add_linked_condition(none_child_block.uuid, none_child.uuid)

    none_child_block.remove_condition("EngineBookNoneChild")

    assert none_parent.applied is True
    assert none_child.applied is False
    assert none_parent_block.active_conditions["EngineBookNoneParent"] is none_parent
    assert none_parent.linked_conditions == [(none_child_block.uuid, none_child.uuid)]


def test_eb_07_012_removal_save_succeeds_before_duration_decrements() -> None:
    """EB-07-012: successful removal saves remove before duration progress."""
    reset_condition_state()
    source = configured_entity("Source")
    target = configured_entity("Target", position=(2, 1))
    condition = EngineBookMarkerCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
        duration=Duration(duration=2, duration_type=DurationType.ROUNDS),
        removal_saving_throw=SavingThrowEvent(
            source_entity_uuid=source.uuid,
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=5,
        ),
    )

    target.add_condition(condition)

    with fixed_randint(20):
        removed = target.advance_duration_condition("EngineBookMarker")

    assert removed is True
    assert condition.applied is False
    assert "EngineBookMarker" not in target.active_conditions
    assert condition.duration.duration == 2


def test_eb_07_013_item_conditions_index_expire_and_destroy_cleanly() -> None:
    """EB-07-013: BaseItem condition lifecycle uses BaseBlock cleanup plus destroy."""
    reset_condition_state()
    source = configured_entity("Source")
    item = BaseItem(source_entity_uuid=source.uuid, name="Conditioned Wand")
    assert item.allow_events_conditions is True

    first = EngineBookMarkerCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=item.uuid,
    )
    completed = item.add_condition(first)

    assert completed is not None
    assert completed.phase == EventPhase.COMPLETION
    assert first.applied is True
    assert item.active_conditions["EngineBookMarker"] is first
    assert item.active_conditions_by_uuid[first.uuid] is first
    assert item.active_conditions_by_source[source.uuid] == ["EngineBookMarker"]

    replacement = EngineBookMarkerCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=item.uuid,
    )
    item.add_condition(replacement)

    assert first.applied is False
    assert replacement.applied is True
    assert item.active_conditions["EngineBookMarker"] is replacement
    assert first.uuid not in item.active_conditions_by_uuid
    assert item.active_conditions_by_source[source.uuid] == ["EngineBookMarker"]

    no_effect = EngineBookNoEffectCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=item.uuid,
    )
    canceled = item.add_condition(no_effect)

    assert canceled is not None
    assert canceled.canceled is True
    assert no_effect.applied is False
    assert "EngineBookNoEffect" not in item.active_conditions
    assert no_effect.uuid not in item.active_conditions_by_uuid

    timed = EngineBookMarkerCondition(
        name="EngineBookItemTimed",
        source_entity_uuid=source.uuid,
        target_entity_uuid=item.uuid,
        duration=Duration(duration=1, duration_type=DurationType.ROUNDS),
    )
    item.add_condition(timed)

    assert item.advance_duration("EngineBookItemTimed") is True
    assert timed.applied is False
    assert "EngineBookItemTimed" not in item.active_conditions

    destroy_condition = EngineBookMarkerCondition(
        name="EngineBookDestroyCleanup",
        source_entity_uuid=source.uuid,
        target_entity_uuid=item.uuid,
    )
    item.add_condition(destroy_condition)

    item.destroy()

    assert destroy_condition.applied is False
    assert item.active_conditions == {}
    assert item.uuid not in BaseBlock._registry
