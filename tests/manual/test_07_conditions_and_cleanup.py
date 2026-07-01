"""Tutorial tests for condition application, ownership, and cleanup."""

from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field

from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, DurationType
from dnd.core.base_object import BaseObject
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import BaseValue, ModifiableValue


class TutorialActor(BaseBlock):
    """Focused condition-bearing block used by manual condition examples."""

    guard_bonus: ModifiableValue = Field(description="Tutorial defensive value.")
    focus_bonus: ModifiableValue = Field(description="Tutorial focus value.")


def create_tutorial_actor(name: str) -> TutorialActor:
    """Create a block with condition support and two tutorial values."""
    actor_id = uuid4()
    return TutorialActor(
        name=name,
        source_entity_uuid=actor_id,
        allow_events_conditions=True,
        guard_bonus=ModifiableValue.create(
            source_entity_uuid=actor_id,
            value_name=f"{name} Guard",
            base_value=10,
        ),
        focus_bonus=ModifiableValue.create(
            source_entity_uuid=actor_id,
            value_name=f"{name} Focus",
            base_value=1,
        ),
    )


def reset_condition_state() -> None:
    """Clear global state touched by these condition lifecycle examples."""
    EventQueue.reset()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    EventQueue.set_combat_log_callback(None)


class GuardedCondition(BaseCondition):
    """Condition that owns one numerical modifier on a target block."""

    name: str = Field(default="Guarded", description="Condition name.")
    description: str = Field(default="+2 guard bonus.", description="Condition description.")

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        """Add the guard modifier and return the owned modifier UUID."""
        block = TutorialActor.get(self.target_entity_uuid)
        assert isinstance(block, TutorialActor)

        modifier_uuid = block.guard_bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                name="Guarded",
                value=2,
            )
        )
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{block.name} is guarded",
            condition=self,
        )
        return [(block.guard_bonus.uuid, modifier_uuid)], [], [], [], effect_event


class ListeningCondition(BaseCondition):
    """Condition that owns an event handler and cleans it up on removal."""

    name: str = Field(default="Listening", description="Condition name.")
    description: str = Field(default="Listens for tutorial actions.", description="Condition description.")

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        """Register a handler owned by the target block."""
        block = TutorialActor.get(self.target_entity_uuid)
        assert isinstance(block, TutorialActor)

        def listener(event: Event, _handler_source_uuid: UUID) -> Optional[Event]:
            return event.model_copy(
                update={
                    "modified": True,
                    "status_message": "Listening condition heard the action",
                }
            )

        handler = EventHandler(
            name="Listening Condition Handler",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=listener,
        )
        block.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{block.name} is listening",
            condition=self,
        )
        return [], [handler.uuid], [], [], effect_event


class FocusBlockedCondition(BaseCondition):
    """Subcondition that caps a tutorial focus value at zero."""

    name: str = Field(default="Focus Blocked", description="Condition name.")
    description: str = Field(default="Focus is capped at zero.", description="Condition description.")

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        """Add a max constraint to the target block's focus value."""
        block = TutorialActor.get(self.target_entity_uuid)
        assert isinstance(block, TutorialActor)

        modifier_uuid = block.focus_bonus.self_static.add_max_constraint(
            NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                name="Focus Blocked",
                value=0,
            )
        )
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{block.name}'s focus is blocked",
            condition=self,
        )
        return [(block.focus_bonus.uuid, modifier_uuid)], [], [], [], effect_event


class StunnedTutorialCondition(BaseCondition):
    """Parent condition that applies a same-block subcondition."""

    name: str = Field(default="Tutorial Stunned", description="Condition name.")
    description: str = Field(default="Applies Focus Blocked as a child.", description="Condition description.")

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        """Apply Focus Blocked as a child condition on the same block."""
        block = TutorialActor.get(self.target_entity_uuid)
        assert isinstance(block, TutorialActor)

        execution_event = declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"{block.name} begins Tutorial Stunned",
            condition=self,
        )
        child = FocusBlockedCondition(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
        )
        child_event = block.add_condition(child, event=execution_event)
        child_uuids = [child.uuid] if child_event and child_event.phase == EventPhase.COMPLETION else []

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{block.name} is stunned",
            condition=self,
        )
        return [], [], child_uuids, [], effect_event


class LinkedMarkCondition(BaseCondition):
    """Condition applied to another block by LinkedAuraCondition."""

    name: str = Field(default="Linked Mark", description="Condition name.")
    description: str = Field(default="Cross-block linked child.", description="Condition description.")


class LinkedAuraCondition(BaseCondition):
    """Parent condition that owns a condition on another block."""

    name: str = Field(default="Linked Aura", description="Condition name.")
    description: str = Field(default="Applies Linked Mark to another block.", description="Condition description.")
    marked_block_uuid: UUID = Field(description="Block that receives the linked mark.")
    child_removal_policy: str = Field(default="any", description="Remove parent when a linked child is removed.")

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Optional[Event]]:
        """Apply Linked Mark to the marked block and track the cross-block link."""
        owner = TutorialActor.get(self.target_entity_uuid)
        marked = TutorialActor.get(self.marked_block_uuid)
        assert isinstance(owner, TutorialActor)
        assert isinstance(marked, TutorialActor)

        execution_event = declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"{owner.name} projects a linked aura",
            condition=self,
        )
        child = LinkedMarkCondition(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=marked.uuid,
        )
        child_event = marked.add_condition(child, event=execution_event)
        if child_event and child_event.phase == EventPhase.COMPLETION:
            self.add_linked_condition(marked.uuid, child.uuid)

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{marked.name} is linked to {owner.name}",
            condition=self,
        )
        return [], [], [], [], effect_event


def test_first_condition_example_prints_visible_cleanup(capsys) -> None:
    """One condition prints application indexes, owned modifier, and cleanup."""
    reset_condition_state()

    actor = create_tutorial_actor("Hero")
    source_id = uuid4()
    condition = GuardedCondition(
        source_entity_uuid=source_id,
        target_entity_uuid=actor.uuid,
    )
    completed = actor.add_condition(condition)
    owned_modifier_count = sum(
        len(modifier_ids) for modifier_ids in condition.modifers_uuids.values()
    )

    readout_lines = [
        f"actor: {actor.name}",
        f"condition applied: {condition.applied}",
        f"completion phase: {completed.phase.value if completed else 'missing'}",
        f"active conditions: {', '.join(actor.active_conditions)}",
        f"guard score while active: {actor.guard_bonus.normalized_score}",
        f"owned modifier count: {owned_modifier_count}",
    ]

    actor.remove_condition("Guarded")
    cleanup_state = (
        "removed" if "Guarded" not in actor.active_conditions else "still active"
    )
    readout_lines.extend(
        [
            f"condition after cleanup: {cleanup_state}",
            f"guard score after cleanup: {actor.guard_bonus.normalized_score}",
        ]
    )

    print("\n".join(readout_lines))

    expected_lines = [
        "actor: Hero",
        "condition applied: True",
        "completion phase: completion",
        "active conditions: Guarded",
        "guard score while active: 12",
        "owned modifier count: 1",
        "condition after cleanup: removed",
        "guard score after cleanup: 10",
    ]
    assert readout_lines == expected_lines
    assert condition.applied is False
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_condition_bearing_actor_prints_block_and_value_state(capsys) -> None:
    """The focused actor example prints condition support and baseline values."""
    reset_condition_state()

    actor = create_tutorial_actor("Hero")

    actor_lines = [
        f"actor: {actor.name}",
        f"condition support: {actor.allow_events_conditions}",
        f"guard score: {actor.guard_bonus.normalized_score}",
        f"focus score: {actor.focus_bonus.normalized_score}",
        f"block lookup: {TutorialActor.get(actor.uuid) is actor}",
    ]

    print("\n".join(actor_lines))

    expected_actor_lines = [
        "actor: Hero",
        "condition support: True",
        "guard score: 10",
        "focus score: 1",
        "block lookup: True",
    ]
    assert actor_lines == expected_actor_lines
    assert capsys.readouterr().out.splitlines() == expected_actor_lines


def test_condition_application_indexes_owned_modifier_and_removal_cleans_it(capsys) -> None:
    """Condition application indexes the condition and owns modifier cleanup."""
    reset_condition_state()
    actor = create_tutorial_actor("Hero")
    source_id = uuid4()

    condition = GuardedCondition(source_entity_uuid=source_id, target_entity_uuid=actor.uuid)
    completed = actor.add_condition(condition)

    assert completed is not None
    assert completed.phase == EventPhase.COMPLETION
    assert condition.applied is True
    assert actor.active_conditions["Guarded"] is condition
    assert actor.active_conditions_by_uuid[condition.uuid] is condition
    assert actor.active_conditions_by_source[source_id] == ["Guarded"]
    assert actor.guard_bonus.normalized_score == 12
    assert condition.modifers_uuids == {
        actor.guard_bonus.uuid: next(iter(condition.modifers_uuids.values()))
    }
    owned_modifier_count = sum(
        len(modifier_ids) for modifier_ids in condition.modifers_uuids.values()
    )

    actor.remove_condition("Guarded")

    assert "Guarded" not in actor.active_conditions
    assert condition.uuid not in actor.active_conditions_by_uuid
    assert actor.active_conditions_by_source[source_id] == []
    assert condition.applied is False
    assert actor.guard_bonus.normalized_score == 10

    modifier_lines = [
        f"completion phase: {completed.phase.value}",
        f"active condition before cleanup: {condition.name}",
        f"source index before cleanup: ['Guarded']",
        f"guard score while active: 12",
        f"owned modifier count: {owned_modifier_count}",
        f"active conditions after cleanup: {list(actor.active_conditions)}",
        f"source index after cleanup: {actor.active_conditions_by_source[source_id]}",
        f"guard score after cleanup: {actor.guard_bonus.normalized_score}",
    ]

    print("\n".join(modifier_lines))

    expected_modifier_lines = [
        "completion phase: completion",
        "active condition before cleanup: Guarded",
        "source index before cleanup: ['Guarded']",
        "guard score while active: 12",
        "owned modifier count: 1",
        "active conditions after cleanup: []",
        "source index after cleanup: []",
        "guard score after cleanup: 10",
    ]
    assert modifier_lines == expected_modifier_lines
    assert capsys.readouterr().out.splitlines() == expected_modifier_lines


def test_condition_owned_event_handler_is_removed_with_condition(capsys) -> None:
    """Condition-owned handlers stop firing after the condition is removed."""
    reset_condition_state()
    actor = create_tutorial_actor("Sentinel")
    source_id = uuid4()

    condition = ListeningCondition(source_entity_uuid=source_id, target_entity_uuid=actor.uuid)
    actor.add_condition(condition)

    heard_event = Event(
        name="Tutorial Action",
        source_entity_uuid=actor.uuid,
        event_type=EventType.BASE_ACTION,
    ).phase_to(EventPhase.EFFECT)

    assert heard_event.status_message == "Listening condition heard the action"
    assert len(condition.event_handlers_uuids) == 1
    active_handler_count = len(condition.event_handlers_uuids)

    actor.remove_condition("Listening")

    quiet_event = Event(
        name="Tutorial Action",
        source_entity_uuid=actor.uuid,
        event_type=EventType.BASE_ACTION,
    ).phase_to(EventPhase.EFFECT)

    assert quiet_event.status_message is None
    assert condition.event_handlers_uuids == []

    handler_lines = [
        f"active handler count: {active_handler_count}",
        f"heard event status: {heard_event.status_message}",
        f"quiet event status: {quiet_event.status_message or 'quiet'}",
        f"handler count after cleanup: {len(condition.event_handlers_uuids)}",
    ]

    print("\n".join(handler_lines))

    expected_handler_lines = [
        "active handler count: 1",
        "heard event status: Listening condition heard the action",
        "quiet event status: quiet",
        "handler count after cleanup: 0",
    ]
    assert handler_lines == expected_handler_lines
    assert capsys.readouterr().out.splitlines() == expected_handler_lines


def test_parent_condition_removes_same_block_subcondition_tree(capsys) -> None:
    """Removing a parent condition removes same-block subconditions."""
    reset_condition_state()
    actor = create_tutorial_actor("Adept")
    source_id = uuid4()

    condition = StunnedTutorialCondition(source_entity_uuid=source_id, target_entity_uuid=actor.uuid)
    actor.add_condition(condition)

    assert "Tutorial Stunned" in actor.active_conditions
    assert "Focus Blocked" in actor.active_conditions
    assert actor.focus_bonus.normalized_score == 0
    assert len(condition.sub_conditions) == 1
    active_before_cleanup = sorted(actor.active_conditions)
    focus_while_blocked = actor.focus_bonus.normalized_score
    subcondition_count = len(condition.sub_conditions)

    actor.remove_condition("Tutorial Stunned")

    assert "Tutorial Stunned" not in actor.active_conditions
    assert "Focus Blocked" not in actor.active_conditions
    assert actor.focus_bonus.normalized_score == 1

    subcondition_lines = [
        f"active before cleanup: {active_before_cleanup}",
        f"focus while blocked: {focus_while_blocked}",
        f"subcondition count: {subcondition_count}",
        f"active after cleanup: {list(actor.active_conditions)}",
        f"focus after cleanup: {actor.focus_bonus.normalized_score}",
    ]

    print("\n".join(subcondition_lines))

    expected_subcondition_lines = [
        "active before cleanup: ['Focus Blocked', 'Tutorial Stunned']",
        "focus while blocked: 0",
        "subcondition count: 1",
        "active after cleanup: []",
        "focus after cleanup: 1",
    ]
    assert subcondition_lines == expected_subcondition_lines
    assert capsys.readouterr().out.splitlines() == expected_subcondition_lines


def test_linked_condition_cleanup_runs_forward_and_reverse(capsys) -> None:
    """Linked children are cleaned with parents, and child removal can remove parent."""
    reset_condition_state()
    owner = create_tutorial_actor("Caster")
    marked = create_tutorial_actor("Target")
    source_id = uuid4()

    forward = LinkedAuraCondition(
        source_entity_uuid=source_id,
        target_entity_uuid=owner.uuid,
        marked_block_uuid=marked.uuid,
    )
    owner.add_condition(forward)

    assert "Linked Aura" in owner.active_conditions
    assert "Linked Mark" in marked.active_conditions
    assert marked.active_conditions["Linked Mark"].parent_link == (owner.uuid, forward.uuid)
    forward_before = (
        "Linked Aura" in owner.active_conditions,
        "Linked Mark" in marked.active_conditions,
    )
    linked_parent = marked.active_conditions["Linked Mark"].parent_link == (
        owner.uuid,
        forward.uuid,
    )

    owner.remove_condition("Linked Aura")

    assert "Linked Aura" not in owner.active_conditions
    assert "Linked Mark" not in marked.active_conditions
    forward_after = (
        "Linked Aura" in owner.active_conditions,
        "Linked Mark" in marked.active_conditions,
    )

    reverse = LinkedAuraCondition(
        source_entity_uuid=source_id,
        target_entity_uuid=owner.uuid,
        marked_block_uuid=marked.uuid,
    )
    owner.add_condition(reverse)

    assert "Linked Aura" in owner.active_conditions
    assert "Linked Mark" in marked.active_conditions
    reverse_before = (
        "Linked Aura" in owner.active_conditions,
        "Linked Mark" in marked.active_conditions,
    )

    marked.remove_condition("Linked Mark")

    assert "Linked Mark" not in marked.active_conditions
    assert "Linked Aura" not in owner.active_conditions
    reverse_after = (
        "Linked Aura" in owner.active_conditions,
        "Linked Mark" in marked.active_conditions,
    )

    linked_lines = [
        f"forward before cleanup: owner={forward_before[0]}, marked={forward_before[1]}",
        f"linked parent recorded: {linked_parent}",
        f"forward after parent cleanup: owner={forward_after[0]}, marked={forward_after[1]}",
        f"reverse before child cleanup: owner={reverse_before[0]}, marked={reverse_before[1]}",
        f"reverse after child cleanup: owner={reverse_after[0]}, marked={reverse_after[1]}",
    ]

    print("\n".join(linked_lines))

    expected_linked_lines = [
        "forward before cleanup: owner=True, marked=True",
        "linked parent recorded: True",
        "forward after parent cleanup: owner=False, marked=False",
        "reverse before child cleanup: owner=True, marked=True",
        "reverse after child cleanup: owner=False, marked=False",
    ]
    assert linked_lines == expected_linked_lines
    assert capsys.readouterr().out.splitlines() == expected_linked_lines


def test_round_duration_expiry_removes_condition_and_owned_modifier(capsys) -> None:
    """Round duration progression removes an expired condition through cleanup."""
    reset_condition_state()
    actor = create_tutorial_actor("Defender")
    source_id = uuid4()

    condition = GuardedCondition(source_entity_uuid=source_id, target_entity_uuid=actor.uuid)
    condition.duration.duration_type = DurationType.ROUNDS
    condition.duration.duration = 2
    actor.add_condition(condition)

    assert actor.guard_bonus.normalized_score == 12
    first_tick_expired = actor.advance_duration("Guarded")
    assert first_tick_expired is False
    assert "Guarded" in actor.active_conditions
    assert condition.duration.duration == 1
    duration_after_first_tick = condition.duration.duration

    second_tick_expired = actor.advance_duration("Guarded")
    assert second_tick_expired is True
    assert "Guarded" not in actor.active_conditions
    assert condition.applied is False
    assert actor.guard_bonus.normalized_score == 10

    duration_lines = [
        "guard score while active: 12",
        f"first tick expired: {first_tick_expired}",
        f"duration after first tick: {duration_after_first_tick}",
        f"second tick expired: {second_tick_expired}",
        f"active after expiry: {'Guarded' in actor.active_conditions}",
        f"guard score after expiry: {actor.guard_bonus.normalized_score}",
    ]

    print("\n".join(duration_lines))

    expected_duration_lines = [
        "guard score while active: 12",
        "first tick expired: False",
        "duration after first tick: 1",
        "second tick expired: True",
        "active after expiry: False",
        "guard score after expiry: 10",
    ]
    assert duration_lines == expected_duration_lines
    assert capsys.readouterr().out.splitlines() == expected_duration_lines
