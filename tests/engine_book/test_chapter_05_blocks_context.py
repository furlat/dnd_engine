"""Engine book parity tests for blocks, context, and cleanup boundaries."""

from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field

from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import DurationType
from dnd.core.base_object import BaseObject
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import BaseValue, ModifiableValue


class LeafBlock(BaseBlock):
    """Small nested block used by the engine-book examples."""

    leaf_value: ModifiableValue = Field(description="A value owned by the leaf block.")


class ParentBlock(BaseBlock):
    """Small parent block with one direct value and one nested block."""

    direct_value: ModifiableValue = Field(description="A value owned directly by the parent.")
    child: LeafBlock = Field(description="Nested child block.")


class MarkerCondition(BaseCondition):
    """Condition with no side effects beyond lifecycle events."""

    name: str = "MarkerCondition"

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        event = declaration_event.phase_to(EventPhase.EXECUTION)
        event = event.phase_to(EventPhase.EFFECT)
        return [], [], [], [], event


class ValueBonusCondition(BaseCondition):
    """Condition that adds one numerical modifier to a specific value."""

    name: str = "ValueBonusCondition"
    target_value_uuid: UUID = Field(description="Value that receives the modifier.")
    bonus: int = Field(default=2, description="Numerical bonus to add while applied.")

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        event = declaration_event.phase_to(EventPhase.EXECUTION)
        value = ModifiableValue.get(self.target_value_uuid)
        if value is None:
            raise AssertionError(f"Missing value {self.target_value_uuid}")
        modifier = NumericalModifier(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            name="Engine Book Bonus",
            value=self.bonus,
        )
        modifier_uuid = value.self_static.add_value_modifier(modifier)
        event = event.phase_to(EventPhase.EFFECT)
        return [(value.uuid, modifier_uuid)], [], [], [], event


class NoEffectCondition(BaseCondition):
    """Condition whose apply hook returns no effect event."""

    name: str = "NoEffectCondition"

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        return [], [], [], [], None


def reset_block_state() -> None:
    """Clear global state touched by these block examples."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()


def make_value(source_uuid: UUID, name: str, base_value: int = 0) -> ModifiableValue:
    """Create a named value for synthetic block examples."""
    return ModifiableValue.create(
        source_entity_uuid=source_uuid,
        value_name=name,
        base_value=base_value,
    )


def make_parent_block(source_uuid: UUID) -> ParentBlock:
    """Create a parent block whose explicit fields share one source UUID."""
    child = LeafBlock(
        source_entity_uuid=source_uuid,
        name="Child Block",
        leaf_value=make_value(source_uuid, "Leaf Value", 3),
    )
    return ParentBlock(
        source_entity_uuid=source_uuid,
        name="Parent Block",
        direct_value=make_value(source_uuid, "Direct Value", 5),
        child=child,
    )


def test_eb_05_001_blocks_discover_direct_and_deep_values() -> None:
    """EB-05-001: blocks index direct values and direct child blocks."""
    reset_block_state()
    source_uuid = uuid4()
    block = make_parent_block(source_uuid)

    assert BaseBlock.get(block.uuid) is block
    assert BaseBlock.get(block.child.uuid) is block.child
    assert block.get_value_from_name("Direct Value") is block.direct_value
    assert block.get_block_from_name("Child Block") is block.child
    assert block.get_value_from_name("Leaf Value") is None

    shallow_values = block.get_values()
    deep_values = block.get_values(deep=True)
    assert shallow_values == [block.direct_value]
    assert {value.uuid for value in deep_values} == {
        block.direct_value.uuid,
        block.child.leaf_value.uuid,
    }
    assert block.values_dict_name_uuid == {"Direct Value": block.direct_value.uuid}
    assert block.blocks_dict_name_uuid == {"Child Block": block.child.uuid}


def test_eb_05_002_target_propagation_reaches_values_and_child_blocks() -> None:
    """EB-05-002: block target propagation recurses through owned objects."""
    reset_block_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    block = make_parent_block(source_uuid)

    block.set_target_entity(target_uuid, "Target")

    assert block.target_entity_uuid == target_uuid
    assert block.direct_value.target_entity_uuid == target_uuid
    assert block.direct_value.self_static.target_entity_uuid == target_uuid
    assert block.direct_value.to_target_contextual.target_entity_uuid == target_uuid
    assert block.child.target_entity_uuid == target_uuid
    assert block.child.leaf_value.target_entity_uuid == target_uuid

    block.clear_target_entity()

    assert block.target_entity_uuid is None
    assert block.direct_value.target_entity_uuid is None
    assert block.direct_value.from_target_static is None
    assert block.child.target_entity_uuid is None
    assert block.child.leaf_value.target_entity_uuid is None


def test_eb_05_003_context_propagation_reaches_contextual_channels() -> None:
    """EB-05-003: block context propagation reaches contextual value channels."""
    reset_block_state()
    source_uuid = uuid4()
    block = make_parent_block(source_uuid)
    context = {"range": "melee", "cover": "none"}

    block.set_context(context)

    assert block.context is context
    assert block.direct_value.context is context
    assert block.direct_value.self_contextual.context is context
    assert block.direct_value.to_target_contextual.context is context
    assert block.direct_value.self_static.context is None
    assert block.child.context is context
    assert block.child.leaf_value.context is context

    block.clear_context()

    assert block.context is None
    assert block.direct_value.context is None
    assert block.direct_value.self_contextual.context is None
    assert block.direct_value.to_target_contextual.context is None
    assert block.child.context is None
    assert block.child.leaf_value.context is None


def test_eb_05_013_constructor_source_propagates_after_field_discovery() -> None:
    """EB-05-013: constructor source propagation reaches explicit fields."""
    reset_block_state()
    parent_source_uuid = uuid4()
    foreign_source_uuid = uuid4()
    target_uuid = uuid4()
    foreign_leaf_value = make_value(foreign_source_uuid, "Foreign Leaf Value", 1)
    foreign_child = LeafBlock(
        source_entity_uuid=foreign_source_uuid,
        name="Foreign Child",
        leaf_value=foreign_leaf_value,
    )
    foreign_direct_value = make_value(foreign_source_uuid, "Foreign Direct Value", 2)

    block = ParentBlock(
        source_entity_uuid=parent_source_uuid,
        target_entity_uuid=target_uuid,
        target_entity_name="Target",
        context={"phase": "construction"},
        name="Parent With Foreign Fields",
        direct_value=foreign_direct_value,
        child=foreign_child,
    )

    assert block.values == {foreign_direct_value.uuid: foreign_direct_value}
    assert block.blocks == {foreign_child.uuid: foreign_child}
    assert block.source_entity_uuid == parent_source_uuid
    assert block.direct_value.source_entity_uuid == parent_source_uuid
    assert block.child.source_entity_uuid == parent_source_uuid
    assert block.child.leaf_value.source_entity_uuid == parent_source_uuid
    assert block.direct_value.target_entity_uuid == target_uuid
    assert block.child.target_entity_uuid == target_uuid
    assert block.child.leaf_value.target_entity_uuid == target_uuid
    assert block.direct_value.context == {"phase": "construction"}
    assert block.child.context == {"phase": "construction"}
    assert block.child.leaf_value.context == {"phase": "construction"}


def test_eb_05_004_conditions_are_gated_by_allow_events_conditions() -> None:
    """EB-05-004: BaseBlock ignores conditions unless lifecycle is enabled."""
    reset_block_state()
    source_uuid = uuid4()
    inert_block = make_parent_block(source_uuid)
    condition = MarkerCondition(
        source_entity_uuid=source_uuid,
        target_entity_uuid=inert_block.uuid,
    )

    assert inert_block.add_condition(condition) is None
    assert inert_block.active_conditions == {}
    assert condition.applied is False

    active_block = make_parent_block(source_uuid)
    active_block.allow_events_conditions = True
    active_condition = MarkerCondition(
        source_entity_uuid=source_uuid,
        target_entity_uuid=active_block.uuid,
    )

    applied_event = active_block.add_condition(active_condition)

    assert applied_event is not None
    assert applied_event.phase == EventPhase.COMPLETION
    assert active_block.active_conditions["MarkerCondition"] is active_condition
    assert active_block.active_conditions_by_uuid[active_condition.uuid] is active_condition
    assert active_block.active_conditions_by_source[source_uuid] == ["MarkerCondition"]

    active_block.remove_condition("MarkerCondition")

    assert active_block.active_conditions == {}
    assert active_condition.applied is False


def test_eb_05_005_condition_cleanup_removes_owned_modifiers() -> None:
    """EB-05-005: BaseBlock removal asks the condition to clean own modifiers."""
    reset_block_state()
    source_uuid = uuid4()
    block = make_parent_block(source_uuid)
    block.allow_events_conditions = True
    condition = ValueBonusCondition(
        source_entity_uuid=source_uuid,
        target_entity_uuid=block.uuid,
        target_value_uuid=block.direct_value.uuid,
        bonus=7,
    )

    base_score = block.direct_value.normalized_score
    block.add_condition(condition)

    assert block.direct_value.normalized_score == base_score + 7
    assert list(condition.modifers_uuids) == [block.direct_value.uuid]
    assert len(condition.modifers_uuids[block.direct_value.uuid]) == 1
    modifier_uuid = condition.modifers_uuids[block.direct_value.uuid][0]
    assert modifier_uuid in block.direct_value.self_static.value_modifiers

    block.remove_condition("ValueBonusCondition")

    assert block.direct_value.normalized_score == base_score
    assert condition.applied is False
    assert block.active_conditions == {}


def test_eb_05_006_linked_conditions_are_removed_across_blocks() -> None:
    """EB-05-006: BaseBlock removal traverses linked conditions on other blocks."""
    reset_block_state()
    source_uuid = uuid4()
    parent_block = make_parent_block(source_uuid)
    child_block = make_parent_block(source_uuid)
    parent_block.allow_events_conditions = True
    child_block.allow_events_conditions = True

    parent_condition = MarkerCondition(
        source_entity_uuid=source_uuid,
        target_entity_uuid=parent_block.uuid,
    )
    child_condition = MarkerCondition(
        source_entity_uuid=source_uuid,
        target_entity_uuid=child_block.uuid,
        name="LinkedMarkerCondition",
    )

    parent_block.add_condition(parent_condition)
    child_block.add_condition(child_condition)
    parent_condition.add_linked_condition(child_block.uuid, child_condition.uuid)

    assert "MarkerCondition" in parent_block.active_conditions
    assert "LinkedMarkerCondition" in child_block.active_conditions
    assert child_condition.parent_link == (parent_block.uuid, parent_condition.uuid)

    parent_block.remove_condition("MarkerCondition")

    assert parent_block.active_conditions == {}
    assert child_block.active_conditions == {}
    assert parent_condition.applied is False
    assert child_condition.applied is False


def test_eb_05_007_event_handlers_are_owned_and_removed_by_block() -> None:
    """EB-05-007: handler ownership is local and mirrored into EventQueue."""
    reset_block_state()
    source_uuid = uuid4()
    block = make_parent_block(source_uuid)
    block.allow_events_conditions = True
    calls = 0

    def processor(event: Event, _: UUID) -> Event:
        nonlocal calls
        calls += 1
        return event

    handler = EventHandler(
        source_entity_uuid=source_uuid,
        name="Engine Book Handler",
        trigger_conditions=[
            Trigger(
                event_type=EventType.BASE_ACTION,
                event_phase=EventPhase.EXECUTION,
            )
        ],
        event_processor=processor,
    )

    block.add_event_handler(handler)
    assert block.get_event_handler_by_name("engine book handler") is handler
    assert EventQueue._event_handlers[handler.uuid] is handler

    Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.EXECUTION)
    assert calls == 1

    block.remove_event_handler(handler)
    assert handler.uuid not in block.event_handlers
    assert handler.uuid not in EventQueue._event_handlers


def test_eb_05_011_handler_toggles_only_affect_player_toggleable_handlers() -> None:
    """EB-05-011: block toggle helpers only affect player-toggleable handlers."""
    reset_block_state()
    source_uuid = uuid4()
    block = make_parent_block(source_uuid)
    block.allow_events_conditions = True
    calls: list[str] = []
    trigger = Trigger(
        event_type=EventType.BASE_ACTION,
        event_phase=EventPhase.EXECUTION,
    )

    def locked_processor(event: Event, _: UUID) -> Event:
        calls.append("locked")
        return event

    def toggleable_processor(event: Event, _: UUID) -> Event:
        calls.append("toggleable")
        return event

    locked_handler = EventHandler(
        source_entity_uuid=source_uuid,
        name="Locked Handler",
        player_toggleable=False,
        trigger_conditions=[trigger],
        event_processor=locked_processor,
    )
    toggleable_handler = EventHandler(
        source_entity_uuid=source_uuid,
        name="Toggleable Handler",
        player_toggleable=True,
        trigger_conditions=[trigger],
        event_processor=toggleable_processor,
    )

    block.add_event_handler(locked_handler)
    block.add_event_handler(toggleable_handler)

    assert block.set_handler_enabled("Locked Handler", False) is False
    assert locked_handler.enabled is True
    assert block.set_handler_enabled("Toggleable Handler", False) is True
    assert toggleable_handler.enabled is False

    Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.EXECUTION)
    assert calls == ["locked"]

    assert block.set_handler_enabled_by_uuid(toggleable_handler.uuid, True) is True
    assert toggleable_handler.enabled is True

    Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.EXECUTION)
    assert calls == ["locked", "locked", "toggleable"]


def test_eb_05_012_condition_immunity_storage_is_gated_and_named() -> None:
    """EB-05-012: condition immunity helpers store static and contextual rows."""
    reset_block_state()
    source_uuid = uuid4()
    inert_block = make_parent_block(source_uuid)

    inert_block.add_condition_immunity("Poisoned", immunity_name="Antitoxin")
    assert inert_block.condition_immunities == []
    assert inert_block.contextual_condition_immunities == {}

    active_block = make_parent_block(source_uuid)
    active_block.allow_events_conditions = True

    def bravery_check(
        block: BaseBlock,
        target: Optional[BaseBlock],
        context: Optional[dict],
    ) -> bool:
        return context is not None and context.get("source") == "dragon"

    active_block.add_condition_immunity("Prone")
    active_block.add_condition_immunity("Poisoned", immunity_name="Antitoxin")
    active_block.add_condition_immunity(
        "Frightened",
        immunity_name="Bravery",
        immunity_check=bravery_check,
    )

    assert active_block.condition_immunities == [
        ("Prone", None),
        ("Poisoned", "Antitoxin"),
    ]
    assert active_block.contextual_condition_immunities["Frightened"] == [
        ("Bravery", bravery_check)
    ]
    assert active_block.contextual_immunity_names == {"Frightened": ["Bravery"]}
    assert bravery_check(active_block, None, {"source": "dragon"}) is True

    try:
        active_block.add_condition_immunity("Charmed", immunity_check=bravery_check)
    except ValueError as exc:
        assert str(exc) == (
            "Immunity name is required when adding a contextual BaseCondition immunity"
        )
    else:
        raise AssertionError("Contextual condition immunity without a name should fail")

    active_block.remove_condition_immunity("Poisoned")
    assert active_block.condition_immunities == [("Prone", None)]

    active_block.remove_condition_immunity("Frightened")
    assert active_block.contextual_condition_immunities == {}
    assert active_block.contextual_immunity_names == {}


def test_eb_05_008_advance_duration_expires_conditions_without_saves() -> None:
    """EB-05-008: BaseBlock duration advancement expires conditions directly."""
    reset_block_state()
    source_uuid = uuid4()
    block = make_parent_block(source_uuid)
    block.allow_events_conditions = True
    condition = MarkerCondition(
        source_entity_uuid=source_uuid,
        target_entity_uuid=block.uuid,
        duration=Duration(
            source_entity_uuid=source_uuid,
            target_entity_uuid=block.uuid,
            duration=1,
            duration_type=DurationType.ROUNDS,
        ),
    )

    block.add_condition(condition)
    expired = block.advance_duration("MarkerCondition")

    assert expired is True
    assert condition.applied is False
    assert block.active_conditions == {}


def test_eb_05_009_same_name_condition_replaces_old_condition() -> None:
    """EB-05-009: same-name conditions replace and clean the old condition."""
    reset_block_state()
    source_uuid = uuid4()
    block = make_parent_block(source_uuid)
    block.allow_events_conditions = True

    first_condition = ValueBonusCondition(
        source_entity_uuid=source_uuid,
        target_entity_uuid=block.uuid,
        target_value_uuid=block.direct_value.uuid,
        bonus=3,
    )
    second_condition = ValueBonusCondition(
        source_entity_uuid=source_uuid,
        target_entity_uuid=block.uuid,
        target_value_uuid=block.direct_value.uuid,
        bonus=9,
    )
    base_score = block.direct_value.normalized_score

    block.add_condition(first_condition)
    first_modifier_uuid = first_condition.modifers_uuids[block.direct_value.uuid][0]
    assert block.direct_value.normalized_score == base_score + 3
    assert block.active_conditions["ValueBonusCondition"] is first_condition
    assert first_condition.applied is True

    block.add_condition(second_condition)
    second_modifier_uuid = second_condition.modifers_uuids[block.direct_value.uuid][0]

    assert first_condition.applied is False
    assert second_condition.applied is True
    assert block.active_conditions == {"ValueBonusCondition": second_condition}
    assert block.active_conditions_by_uuid == {second_condition.uuid: second_condition}
    assert block.active_conditions_by_source[source_uuid] == ["ValueBonusCondition"]
    assert first_modifier_uuid not in block.direct_value.self_static.value_modifiers
    assert second_modifier_uuid in block.direct_value.self_static.value_modifiers
    assert block.direct_value.normalized_score == base_score + 9


def test_eb_05_014_duplicate_name_replacement_updates_source_indexes() -> None:
    """EB-05-014: duplicate-name replacement moves the source index entry."""
    reset_block_state()
    first_source_uuid = uuid4()
    second_source_uuid = uuid4()
    block = make_parent_block(first_source_uuid)
    block.allow_events_conditions = True
    first_condition = ValueBonusCondition(
        source_entity_uuid=first_source_uuid,
        target_entity_uuid=block.uuid,
        target_value_uuid=block.direct_value.uuid,
        bonus=2,
    )
    second_condition = ValueBonusCondition(
        source_entity_uuid=second_source_uuid,
        target_entity_uuid=block.uuid,
        target_value_uuid=block.direct_value.uuid,
        bonus=6,
    )
    base_score = block.direct_value.normalized_score

    block.add_condition(first_condition)
    first_modifier_uuid = first_condition.modifers_uuids[block.direct_value.uuid][0]

    assert block.active_conditions_by_source[first_source_uuid] == ["ValueBonusCondition"]
    assert block.direct_value.normalized_score == base_score + 2

    block.add_condition(second_condition)
    second_modifier_uuid = second_condition.modifers_uuids[block.direct_value.uuid][0]

    assert first_condition.applied is False
    assert second_condition.applied is True
    assert block.active_conditions == {"ValueBonusCondition": second_condition}
    assert block.active_conditions_by_uuid == {second_condition.uuid: second_condition}
    assert block.active_conditions_by_source[first_source_uuid] == []
    assert block.active_conditions_by_source[second_source_uuid] == ["ValueBonusCondition"]
    assert first_modifier_uuid not in block.direct_value.self_static.value_modifiers
    assert second_modifier_uuid in block.direct_value.self_static.value_modifiers
    assert block.direct_value.normalized_score == base_score + 6


def test_eb_05_010_no_effect_condition_returns_cancel_without_indexing() -> None:
    """EB-05-010: canceled no-effect applications are not indexed by block."""
    reset_block_state()
    source_uuid = uuid4()
    block = make_parent_block(source_uuid)
    block.allow_events_conditions = True
    condition = NoEffectCondition(
        source_entity_uuid=source_uuid,
        target_entity_uuid=block.uuid,
    )

    event = block.add_condition(condition)

    assert event is not None
    assert event.canceled is True
    assert event.phase == EventPhase.CANCEL
    assert event.status_message == (
        "Condition NoEffectCondition was not applied - _apply() returned no effect event"
    )
    assert condition.applied is False
    assert block.active_conditions == {}
    assert block.active_conditions_by_uuid == {}
    assert block.active_conditions_by_source[source_uuid] == []


if __name__ == "__main__":
    test_eb_05_001_blocks_discover_direct_and_deep_values()
    test_eb_05_002_target_propagation_reaches_values_and_child_blocks()
    test_eb_05_003_context_propagation_reaches_contextual_channels()
    test_eb_05_013_constructor_source_propagates_after_field_discovery()
    test_eb_05_004_conditions_are_gated_by_allow_events_conditions()
    test_eb_05_005_condition_cleanup_removes_owned_modifiers()
    test_eb_05_006_linked_conditions_are_removed_across_blocks()
    test_eb_05_007_event_handlers_are_owned_and_removed_by_block()
    test_eb_05_011_handler_toggles_only_affect_player_toggleable_handlers()
    test_eb_05_012_condition_immunity_storage_is_gated_and_named()
    test_eb_05_008_advance_duration_expires_conditions_without_saves()
    test_eb_05_009_same_name_condition_replaces_old_condition()
    test_eb_05_014_duplicate_name_replacement_updates_source_indexes()
    test_eb_05_010_no_effect_condition_returns_cancel_without_indexing()
    print("PASS: engine book block/context tests")
