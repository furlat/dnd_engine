"""Typed authored evidence for condition application and removal."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.conditions import Poisoned, Prone
from dnd.core.base_conditions import (
    BaseCondition,
    ConditionApplicationEvent,
    ConditionRemovalEvent,
)
from dnd.core.combat_log import CombatLogEntry, ConditionLogData
from dnd.types.conditions import ConditionApplicationDisposition
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from tests.engine.support import create_test_monster
from dnd.runtime_reset import reset_engine_runtime


def _condition_ref(
    content_id: str,
    *,
    digest_char: str,
) -> ContentRef:
    """Create one exact synthetic authored condition identity."""
    return ContentRef(
        pack_id="fixture.condition_evidence",
        definition_kind=ContentDefinitionKind.CONDITION,
        content_id=content_id,
        content_version=1,
        definition_contract_hash=digest_char * 64,
    )


def _binding(ref: ContentRef, owner_uuid: UUID) -> BehaviorBinding:
    """Bind a synthetic condition directly to its authored definition."""
    return BehaviorBinding(
        definition_ref=ref,
        provided_by_ref=ref,
        runtime_owner_uuid=owner_uuid,
    )


def _condition(
    *,
    binding: BehaviorBinding | None,
    obscures_perceivability: bool = False,
) -> BaseCondition:
    """Build a condition without invoking entity mechanics."""
    source_uuid = uuid4()
    target_uuid = (
        binding.runtime_owner_uuid
        if binding is not None
        else uuid4()
    )
    return BaseCondition(
        name="Marked",
        semantic_key="legacy.marked.family",
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        source_entity_name="Source",
        target_entity_name="Target",
        behavior_binding=binding,
        obscures_perceivability=obscures_perceivability,
    )


@pytest.mark.parametrize(
    ("disposition", "success"),
    (
        (ConditionApplicationDisposition.APPLIED, True),
        (ConditionApplicationDisposition.PROMOTED, True),
        (ConditionApplicationDisposition.REJECTED, False),
        (ConditionApplicationDisposition.RETAINED_STRONGER, False),
        (ConditionApplicationDisposition.IMMUNE, False),
    ),
)
def test_application_log_has_closed_disposition_and_bound_identity(
    disposition: ConditionApplicationDisposition,
    success: bool,
) -> None:
    """Every application outcome retains one typed identity and result."""
    owner_uuid = uuid4()
    ref = _condition_ref(
        "condition.fixture.marked",
        digest_char="a",
    )
    condition = _condition(binding=_binding(ref, owner_uuid))

    event = condition.declare_event(
        application_disposition=disposition,
    )
    log = event.generate_combat_log()

    assert isinstance(event, ConditionApplicationEvent)
    assert event.condition_content_identity == ref.identity_key
    assert log is not None
    assert log.success is success
    data = ConditionLogData.model_validate(log.data)
    assert data.condition_name == "Marked"
    assert data.condition_content_identity == ref.identity_key
    assert data.application_disposition is disposition
    assert data.reveals_target is False


def test_removal_log_uses_same_bound_identity_and_reveal_fact() -> None:
    """Removal carries authored identity and condition-owned reveal meaning."""
    owner_uuid = uuid4()
    ref = _condition_ref(
        "condition.fixture.hidden_mark",
        digest_char="b",
    )
    condition = _condition(
        binding=_binding(ref, owner_uuid),
        obscures_perceivability=True,
    )

    application = condition.declare_event()
    removal = condition._declare_removal_event(expired=True)
    log = removal.generate_combat_log()

    assert isinstance(removal, ConditionRemovalEvent)
    assert application.condition_content_identity == ref.identity_key
    assert removal.condition_content_identity == ref.identity_key
    assert log is not None
    data = ConditionLogData.model_validate(log.data)
    assert data.condition_name == "Marked"
    assert data.condition_content_identity == ref.identity_key
    assert data.application_disposition is None
    assert data.reveals_target is True


def test_declaration_identity_does_not_follow_later_binding_mutation() -> None:
    """Event-time identity remains frozen even if the live object changes."""
    owner_uuid = uuid4()
    original_ref = _condition_ref(
        "condition.fixture.original",
        digest_char="c",
    )
    replacement_ref = _condition_ref(
        "condition.fixture.replacement",
        digest_char="d",
    )
    condition = _condition(binding=_binding(original_ref, owner_uuid))
    event = condition.declare_event()

    condition.behavior_binding = _binding(replacement_ref, owner_uuid)
    log = event.generate_combat_log()

    assert event.condition_content_identity == original_ref.identity_key
    assert log is not None
    data = ConditionLogData.model_validate(log.data)
    assert data.condition_content_identity == original_ref.identity_key


def test_unbound_condition_never_invents_authored_identity() -> None:
    """Name, semantic key, and Python type are not identity fallbacks."""
    condition = _condition(binding=None)

    application = condition.declare_event()
    removal = condition._declare_removal_event()
    application_log = application.generate_combat_log()
    removal_log = removal.generate_combat_log()

    assert condition.get_semantic_key() == "legacy.marked.family"
    assert application.condition_content_identity is None
    assert removal.condition_content_identity is None
    assert application_log is not None
    assert removal_log is not None
    assert ConditionLogData.model_validate(
        application_log.data,
    ).condition_content_identity is None
    assert ConditionLogData.model_validate(
        removal_log.data,
    ).condition_content_identity is None


@pytest.mark.parametrize(
    "condition_content_identity",
    (None, "fixture.condition_evidence:condition:condition.forged@1"),
)
def test_bound_condition_events_reject_missing_or_mismatched_identity(
    condition_content_identity: str | None,
) -> None:
    """A bound condition and its event-time scalar have one authority."""
    owner_uuid = uuid4()
    ref = _condition_ref(
        "condition.fixture.authoritative",
        digest_char="e",
    )
    condition = _condition(binding=_binding(ref, owner_uuid))
    common = {
        "name": "Marked",
        "condition": condition,
        "source_entity_uuid": condition.source_entity_uuid,
        "target_entity_uuid": condition.target_entity_uuid,
        "condition_content_identity": condition_content_identity,
        "use_register": False,
    }

    with pytest.raises(ValidationError, match="condition content identity"):
        ConditionApplicationEvent(**common)
    with pytest.raises(ValidationError, match="condition content identity"):
        ConditionRemovalEvent(**common)


def test_condition_identity_rewrite_cancels_before_storage_or_application() -> None:
    """A lifecycle handler cannot forge bound condition evidence."""
    reset_engine_runtime(grid_size=(4, 4))
    skeleton = create_test_monster("monster.skeleton", 
        name="Marked Skeleton",
        position=(1, 1),
        faction="monsters",
    )
    condition = Prone(
        source_entity_uuid=skeleton.uuid,
        target_entity_uuid=skeleton.uuid,
    )
    forged_identity = (
        "fixture.condition_evidence:condition:condition.forged@1"
    )

    def forge_identity(event: Event, _source_uuid: UUID) -> Event | None:
        if isinstance(event, ConditionApplicationEvent):
            return event.model_copy(
                update={
                    "condition_content_identity": forged_identity,
                    "modified": True,
                },
            )
        return None

    EventQueue.add_event_handler(
        EventHandler(
            name="Forge Condition Identity",
            source_entity_uuid=skeleton.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CONDITION_APPLICATION,
                    event_phase=EventPhase.DECLARATION,
                    event_target_entity_uuid=skeleton.uuid,
                )
            ],
            event_processor=forge_identity,
        )
    )

    result = skeleton.add_condition(condition)

    assert isinstance(result, ConditionApplicationEvent)
    assert result.canceled
    assert result.phase is EventPhase.CANCEL
    assert condition.behavior_binding is not None
    expected_identity = (
        condition.behavior_binding.definition_ref.identity_key
    )
    assert result.condition_content_identity == expected_identity
    assert "Prone" not in skeleton.active_conditions
    stored = [
        event
        for event in EventQueue._all_events
        if isinstance(event, ConditionApplicationEvent)
    ]
    assert stored
    assert all(
        type(event) is ConditionApplicationEvent
        and event.condition_content_identity == expected_identity
        for event in stored
    )


def test_posted_condition_cancel_is_validated_before_callbacks() -> None:
    """Canonical cancel cannot self-publish forged condition identity."""
    reset_engine_runtime(grid_size=(4, 4))
    skeleton = create_test_monster("monster.skeleton", 
        name="Posted Cancel Skeleton",
        position=(1, 1),
        faction="monsters",
    )
    condition = Prone(
        source_entity_uuid=skeleton.uuid,
        target_entity_uuid=skeleton.uuid,
    )
    forged_identity = (
        "fixture.condition_evidence:condition:condition.forged@1"
    )
    observed: list[tuple[EventPhase, bool, str | None]] = []

    def capture(event: Event) -> None:
        if isinstance(event, ConditionApplicationEvent):
            observed.append(
                (
                    event.phase,
                    event.canceled,
                    event.condition_content_identity,
                ),
            )

    def forge_cancel(event: Event, _source_uuid: UUID) -> Event | None:
        if isinstance(event, ConditionApplicationEvent):
            return event.cancel(
                status_message="forged handler cancel",
                condition_content_identity=forged_identity,
            )
        return None

    EventQueue.add_on_event_callback(capture)
    EventQueue.add_event_handler(
        EventHandler(
            name="Post Forged Condition Cancel",
            source_entity_uuid=skeleton.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CONDITION_APPLICATION,
                    event_phase=EventPhase.EXECUTION,
                    event_target_entity_uuid=skeleton.uuid,
                )
            ],
            event_processor=forge_cancel,
        )
    )
    try:
        result = skeleton.add_condition(condition)
    finally:
        EventQueue.remove_on_event_callback(capture)

    assert isinstance(result, ConditionApplicationEvent)
    assert result.canceled
    assert result.phase is EventPhase.CANCEL
    assert result.canceled_from_phase is EventPhase.EXECUTION
    assert condition.behavior_binding is not None
    expected_identity = (
        condition.behavior_binding.definition_ref.identity_key
    )
    assert "Prone" not in skeleton.active_conditions
    assert all(identity == expected_identity for _, _, identity in observed)
    assert observed == [
        (EventPhase.DECLARATION, False, expected_identity),
        (EventPhase.EXECUTION, False, expected_identity),
        (EventPhase.CANCEL, True, expected_identity),
    ]


def test_posted_condition_completion_is_rejected_before_effect_commit() -> None:
    """An EFFECT handler cannot publish an unearned completion version."""
    reset_engine_runtime(grid_size=(4, 4))
    skeleton = create_test_monster("monster.skeleton", 
        name="Lifecycle Rewrite Skeleton",
        position=(1, 1),
        faction="monsters",
    )
    condition = Prone(
        source_entity_uuid=skeleton.uuid,
        target_entity_uuid=skeleton.uuid,
    )
    observed: list[tuple[EventPhase, bool]] = []
    combat_logs: list[CombatLogEntry] = []

    def capture(event: Event) -> None:
        if isinstance(event, ConditionApplicationEvent):
            observed.append((event.phase, event.canceled))

    def forge_completion(
        event: Event,
        _source_uuid: UUID,
    ) -> Event | None:
        if isinstance(event, ConditionApplicationEvent):
            return event.phase_to(
                EventPhase.COMPLETION,
                lineage_uuid=uuid4(),
                parent_event=event.uuid,
                condition_content_identity=(
                    "fixture.condition_evidence:condition:"
                    "condition.forged@1"
                ),
            )
        return None

    EventQueue.add_on_event_callback(capture)
    EventQueue.set_combat_log_callback(
        lambda event: combat_logs.append(event.combat_log)
        if event.combat_log is not None
        else None,
    )
    EventQueue.add_event_handler(
        EventHandler(
            name="Post Forged Condition Completion",
            source_entity_uuid=skeleton.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CONDITION_APPLICATION,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=skeleton.uuid,
                )
            ],
            event_processor=forge_completion,
        )
    )
    try:
        result = skeleton.add_condition(condition)
    finally:
        EventQueue.remove_on_event_callback(capture)
        EventQueue.set_combat_log_callback(None)

    assert isinstance(result, ConditionApplicationEvent)
    assert result.canceled
    assert result.phase is EventPhase.CANCEL
    assert result.canceled_from_phase is EventPhase.EFFECT
    assert not condition.applied
    assert "Prone" not in skeleton.active_conditions
    stored = [
        event
        for event in EventQueue._all_events
        if isinstance(event, ConditionApplicationEvent)
    ]
    assert len({event.lineage_uuid for event in stored}) == 1
    assert combat_logs == []
    assert observed == [
        (EventPhase.DECLARATION, False),
        (EventPhase.EXECUTION, False),
        (EventPhase.EFFECT, False),
        (EventPhase.CANCEL, True),
    ]


def test_in_place_condition_identity_rewrite_uses_detached_proposal() -> None:
    """Mutable handlers cannot alter the already-observed stored version."""
    reset_engine_runtime(grid_size=(4, 4))
    skeleton = create_test_monster("monster.skeleton", 
        name="In-place Rewrite Skeleton",
        position=(1, 1),
        faction="monsters",
    )
    condition = Prone(
        source_entity_uuid=skeleton.uuid,
        target_entity_uuid=skeleton.uuid,
    )

    def forge_in_place(event: Event, _source_uuid: UUID) -> Event | None:
        if isinstance(event, ConditionApplicationEvent):
            event.condition_content_identity = (
                "fixture.condition_evidence:condition:condition.forged@1"
            )
            event.modified = True
            return event
        return None

    EventQueue.add_event_handler(
        EventHandler(
            name="Mutate Condition Identity In Place",
            source_entity_uuid=skeleton.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CONDITION_APPLICATION,
                    event_phase=EventPhase.DECLARATION,
                    event_target_entity_uuid=skeleton.uuid,
                )
            ],
            event_processor=forge_in_place,
        )
    )

    result = skeleton.add_condition(condition)

    assert isinstance(result, ConditionApplicationEvent)
    assert result.canceled
    assert condition.behavior_binding is not None
    expected_identity = (
        condition.behavior_binding.definition_ref.identity_key
    )
    assert "Prone" not in skeleton.active_conditions
    stored = [
        event
        for event in EventQueue._all_events
        if isinstance(event, ConditionApplicationEvent)
    ]
    assert stored
    assert all(
        event.condition_content_identity == expected_identity
        for event in stored
    )


def test_condition_disposition_rewrite_cannot_contradict_mechanics() -> None:
    """Handlers cannot relabel an installed condition as immune."""
    reset_engine_runtime(grid_size=(4, 4))
    skeleton = create_test_monster("monster.skeleton", 
        name="Disposition Rewrite Skeleton",
        position=(1, 1),
        faction="monsters",
    )
    condition = Prone(
        source_entity_uuid=skeleton.uuid,
        target_entity_uuid=skeleton.uuid,
    )

    def forge_immunity(event: Event, _source_uuid: UUID) -> Event | None:
        if isinstance(event, ConditionApplicationEvent):
            return event.model_copy(
                update={
                    "application_disposition": (
                        ConditionApplicationDisposition.IMMUNE
                    ),
                    "modified": True,
                },
            )
        return None

    EventQueue.add_event_handler(
        EventHandler(
            name="Forge Condition Immunity",
            source_entity_uuid=skeleton.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CONDITION_APPLICATION,
                    event_phase=EventPhase.DECLARATION,
                    event_target_entity_uuid=skeleton.uuid,
                )
            ],
            event_processor=forge_immunity,
        )
    )

    result = skeleton.add_condition(condition)

    assert isinstance(result, ConditionApplicationEvent)
    assert result.canceled
    assert not condition.applied
    assert "Prone" not in skeleton.active_conditions
    stored = [
        event
        for event in EventQueue._all_events
        if isinstance(event, ConditionApplicationEvent)
    ]
    assert stored
    assert all(
        event.application_disposition
        is ConditionApplicationDisposition.APPLIED
        for event in stored
    )


def test_removal_identity_rewrite_cancels_before_storage() -> None:
    """Removal identity has the same pre-observation lifecycle guard."""
    reset_engine_runtime(grid_size=(4, 4))
    owner_uuid = uuid4()
    ref = _condition_ref(
        "condition.fixture.removal_authority",
        digest_char="f",
    )
    condition = _condition(binding=_binding(ref, owner_uuid))

    def forge_identity(event: Event, _source_uuid: UUID) -> Event | None:
        if isinstance(event, ConditionRemovalEvent):
            return event.model_copy(
                update={
                    "condition_content_identity": (
                        "fixture.condition_evidence:condition:"
                        "condition.forged@1"
                    ),
                    "modified": True,
                },
            )
        return None

    EventQueue.add_event_handler(
        EventHandler(
            name="Forge Removal Identity",
            source_entity_uuid=owner_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CONDITION_REMOVAL,
                    event_phase=EventPhase.DECLARATION,
                )
            ],
            event_processor=forge_identity,
        )
    )

    result = EventQueue.publish_declaration(
        condition._declare_removal_event(),
    )

    assert result.canceled
    assert result.phase is EventPhase.CANCEL
    assert result.condition_content_identity == ref.identity_key
    stored = [
        event
        for event in EventQueue._all_events
        if isinstance(event, ConditionRemovalEvent)
    ]
    assert stored
    assert all(
        type(event) is ConditionRemovalEvent
        and event.condition_content_identity == ref.identity_key
        for event in stored
    )


def test_immune_entity_application_returns_and_logs_typed_truth() -> None:
    """Rules immunity is a canceled application with one typed log."""
    reset_engine_runtime(grid_size=(4, 4))
    skeleton = create_test_monster("monster.skeleton", 
        name="Immune Skeleton",
        position=(1, 1),
        faction="monsters",
    )
    condition = Poisoned(
        source_entity_uuid=skeleton.uuid,
        target_entity_uuid=skeleton.uuid,
    )
    logs: list[CombatLogEntry] = []

    def capture(event: Event) -> None:
        if event.combat_log is not None:
            logs.append(event.combat_log)

    EventQueue.set_combat_log_callback(capture)
    try:
        result = skeleton.add_condition(condition)
    finally:
        EventQueue.set_combat_log_callback(None)

    assert isinstance(result, ConditionApplicationEvent)
    assert result.canceled
    assert (
        result.application_disposition
        is ConditionApplicationDisposition.IMMUNE
    )
    assert condition.behavior_binding is not None
    expected_identity = (
        condition.behavior_binding.definition_ref.identity_key
    )
    assert result.condition_content_identity == expected_identity
    assert "Poisoned" not in skeleton.active_conditions
    assert len(logs) == 1
    data = ConditionLogData.model_validate(logs[0].data)
    assert data.condition_name == "Poisoned"
    assert data.condition_content_identity == expected_identity
    assert (
        data.application_disposition
        is ConditionApplicationDisposition.IMMUNE
    )
    assert logs[0].success is False
