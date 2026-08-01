"""Runtime behavior bindings preserve one validated authored dependency chain."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from dnd.content_system.behavior_bindings import BehaviorBinder
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.content_system.runtime import (
    ContentSystemRuntime,
    SERVER_CONTENT_SYSTEM_RUNTIME,
)
from dnd.actions import (
    Attack,
    CORE_STANDARD_ACTION_DECLARATIONS,
    Move,
)
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.base_item import UsableItem
from dnd.conditions import (
    CORE_STANDARD_CONDITION_DECLARATIONS,
    Concentrating,
)
from dnd.core.base_actions import ActionEvent, BaseAction
from dnd.core.base_conditions import BaseCondition
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentVisibility,
)
from dnd.core.content.effects import (
    AuthoredConditionEffect,
    AuthoredConditionEffectBranch,
    AuthoredConditionEffectProfile,
    AutomaticConditionEffectGate,
    ConditionEffectDisposition,
    ConditionEffectOperation,
    ConditionEffectTarget,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.item_definitions import (
    ItemDefinition,
    ItemPersistencePolicy,
)
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
    ContentSource,
    ContentSourceFamily,
    RulesBaseline,
)
from dnd.core.content.registration import (
    behavior_content_ref,
    behavior_identity,
    get_content_declaration,
    item_factory,
)
from dnd.core.content.registry import (
    ContentRegistryBuilder,
    NonConstructibleContentError,
)
from dnd.core.content.runtime import (
    BehaviorBinding,
    RuntimeBehaviorKind,
    active_runtime_behavior_binding,
    bind_runtime_action_before_admission,
    bind_runtime_behavior_child,
    bind_runtime_handler_before_admission,
    runtime_behavior_binding_gateway,
    runtime_behavior_provider,
)
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventHandler, EventQueue, EventType
from dnd.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime


_PACK_ID = "fixture.behavior_binding"
_SOURCE = ContentSource(
    source_id="fixture.behavior_binding.source",
    source_family=ContentSourceFamily.FIXTURE_INTERNAL,
    title="Runtime behavior binding fixture",
    source_version="1",
    rules_baseline=RulesBaseline.ENGINE_NEUTRAL,
    license_id="INTERNAL-TEST",
    canonical_uri="https://example.invalid/runtime-behavior-binding",
    document_digest="d" * 64,
    attribution_text="Internal deterministic runtime-binding fixture.",
)
_PROVENANCE = ContentProvenance(
    primary_source_id=_SOURCE.source_id,
    source_anchor="Runtime behavior binding fixture",
    relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
    fidelity=ContentFidelity.COMPLETE,
    review_status=ContentReviewStatus.REVIEWED,
)


class _NoParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _UnboundInternalBehavior:
    """Explicit unbound implementation of the runtime behavior-owner surface."""

    behavior_binding: BehaviorBinding | None = None


@behavior_identity(
    definition_kind=ContentDefinitionKind.RULE_PRIMITIVE,
    runtime_behavior_kind=RuntimeBehaviorKind.SYSTEM,
    pack_id=_PACK_ID,
    content_id="handler.clockwork_charge",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Clockwork Charge Handler",
        visibility=ContentVisibility.INTERNAL,
    ),
    provenance=_PROVENANCE,
)
class _ClockworkChargeHandler(EventHandler):
    pass


_HANDLER_REF = get_content_declaration(_ClockworkChargeHandler).ref


@behavior_identity(
    definition_kind=ContentDefinitionKind.CONDITION,
    runtime_behavior_kind=RuntimeBehaviorKind.CONDITION,
    pack_id=_PACK_ID,
    content_id="condition.clockwork_charge",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Clockwork Charge",
        visibility=ContentVisibility.INTERNAL,
    ),
    provenance=_PROVENANCE,
    dependencies=(
        ContentDependency(
            relation=ContentDependencyRelation.INSTALLS_HANDLER,
            target_ref=_HANDLER_REF,
        ),
    ),
)
class _ClockworkChargeCondition(BaseCondition):
    pass


_CONDITION_REF = get_content_declaration(_ClockworkChargeCondition).ref


def _automatic_apply_profile(
    *,
    source_ref: ContentRef,
    target: ConditionEffectTarget,
) -> AuthoredConditionEffectProfile:
    return AuthoredConditionEffectProfile(
        branches=(
            AuthoredConditionEffectBranch(
                branch_id="clockwork-charge",
                disposition=ConditionEffectDisposition.BENEFICIAL,
                gates=(AutomaticConditionEffectGate(),),
                effects=(
                    AuthoredConditionEffect(
                        effect_id="apply-clockwork-charge",
                        source_ref=source_ref,
                        operation=ConditionEffectOperation.APPLY,
                        condition_ref=_CONDITION_REF,
                        target=target,
                    ),
                ),
            ),
        ),
    )


_ACTION_DECLARED_REF = behavior_content_ref(
    definition_kind=ContentDefinitionKind.ACTION,
    runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
    pack_id=_PACK_ID,
    content_id="action.wind_clockwork",
    version=1,
)


@behavior_identity(
    definition_kind=ContentDefinitionKind.ACTION,
    runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
    pack_id=_PACK_ID,
    content_id="action.wind_clockwork",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Wind Clockwork",
        visibility=ContentVisibility.PUBLIC,
    ),
    provenance=_PROVENANCE,
    dependencies=(
        ContentDependency(
            relation=ContentDependencyRelation.APPLIES_CONDITION,
            target_ref=_CONDITION_REF,
        ),
    ),
    condition_effect_profile=_automatic_apply_profile(
        source_ref=_ACTION_DECLARED_REF,
        target=ConditionEffectTarget.SELECTED_TARGET,
    ),
)
class _WindClockworkAction(BaseAction):
    pass


_ACTION_REF = get_content_declaration(_WindClockworkAction).ref


@item_factory(
    pack_id=_PACK_ID,
    content_id="item.clockwork",
    version=1,
    parameters=_NoParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Clockwork",
        visibility=ContentVisibility.PUBLIC,
    ),
    provenance=_PROVENANCE,
    item_definition=ItemDefinition(
        persistence_policy=ItemPersistencePolicy.POSSESSION,
    ),
    dependencies=(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=_ACTION_REF,
        ),
    ),
)
def _build_clockwork(
    context: object,
    parameters: _NoParameters,
) -> tuple[object, _NoParameters]:
    return context, parameters


_ROOT_REF = get_content_declaration(_build_clockwork).ref


@item_factory(
    pack_id=_PACK_ID,
    content_id="item.unrelated",
    version=1,
    parameters=_NoParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Unrelated Item",
        visibility=ContentVisibility.INTERNAL,
    ),
    provenance=_PROVENANCE,
    item_definition=ItemDefinition(
        persistence_policy=ItemPersistencePolicy.POSSESSION,
    ),
)
def _build_unrelated(
    context: object,
    parameters: _NoParameters,
) -> tuple[object, _NoParameters]:
    return context, parameters


_UNRELATED_ROOT_REF = get_content_declaration(_build_unrelated).ref


_FEATURE_DECLARED_REF = behavior_content_ref(
    definition_kind=ContentDefinitionKind.CLASS_FEATURE,
    runtime_behavior_kind=RuntimeBehaviorKind.CLASS_FEATURE,
    pack_id=_PACK_ID,
    content_id="class_feature.clockwork_training",
    version=1,
)


@behavior_identity(
    definition_kind=ContentDefinitionKind.CLASS_FEATURE,
    runtime_behavior_kind=RuntimeBehaviorKind.CLASS_FEATURE,
    pack_id=_PACK_ID,
    content_id="class_feature.clockwork_training",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Clockwork Training",
        visibility=ContentVisibility.PUBLIC,
    ),
    provenance=_PROVENANCE,
    dependencies=(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=_ACTION_REF,
        ),
        ContentDependency(
            relation=ContentDependencyRelation.APPLIES_CONDITION,
            target_ref=_CONDITION_REF,
        ),
        ContentDependency(
            relation=ContentDependencyRelation.INSTALLS_HANDLER,
            target_ref=_HANDLER_REF,
        ),
    ),
    condition_effect_profile=_automatic_apply_profile(
        source_ref=_FEATURE_DECLARED_REF,
        target=ConditionEffectTarget.ACTOR,
    ),
)
class _ClockworkTrainingFeature:
    pass


_FEATURE_REF = get_content_declaration(_ClockworkTrainingFeature).ref


def _registry():
    builder = ContentRegistryBuilder()
    builder.add_source(_SOURCE)
    for declaration_source in (
        _ClockworkChargeHandler,
        _ClockworkChargeCondition,
        _WindClockworkAction,
        _build_clockwork,
        _build_unrelated,
        _ClockworkTrainingFeature,
    ):
        builder.add_declaration(get_content_declaration(declaration_source))
    return builder.freeze(pack_dependencies={_PACK_ID: frozenset()})


def _processor(event: Event, source_entity_uuid: UUID) -> Event:
    del source_entity_uuid
    return event


def _runtime_chain(
    owner_uuid: UUID,
) -> tuple[
    _WindClockworkAction,
    _ClockworkChargeCondition,
    _ClockworkChargeHandler,
]:
    action = _WindClockworkAction(
        source_entity_uuid=owner_uuid,
        use_register=False,
    )
    condition = _ClockworkChargeCondition(
        source_entity_uuid=owner_uuid,
        target_entity_uuid=owner_uuid,
        use_register=False,
    )
    handler = _ClockworkChargeHandler(
        source_entity_uuid=owner_uuid,
        event_processor=_processor,
        content_kind=RuntimeBehaviorKind.SYSTEM,
        use_register=False,
    )
    return action, condition, handler


def test_binder_attributes_one_action_condition_handler_vertical_chain() -> None:
    owner_uuid = uuid4()
    action, condition, handler = _runtime_chain(owner_uuid)
    binder = BehaviorBinder(_registry())

    action_binding = binder.bind(
        action,
        declaration_source=_WindClockworkAction,
        expected_kind=RuntimeBehaviorKind.ACTION,
        provided_by_ref=_ROOT_REF,
        origin_root_ref=_ROOT_REF,
        runtime_owner_uuid=owner_uuid,
    )
    condition_binding = binder.bind(
        condition,
        declaration_source=_ClockworkChargeCondition,
        expected_kind=RuntimeBehaviorKind.CONDITION,
        provided_by_ref=_ACTION_REF,
        origin_root_ref=_ROOT_REF,
        runtime_owner_uuid=owner_uuid,
    )
    handler_binding = binder.bind(
        handler,
        declaration_source=_ClockworkChargeHandler,
        expected_kind=RuntimeBehaviorKind.SYSTEM,
        provided_by_ref=_CONDITION_REF,
        origin_root_ref=_ROOT_REF,
        runtime_owner_uuid=owner_uuid,
    )

    assert action_binding == BehaviorBinding(
        definition_ref=_ACTION_REF,
        provided_by_ref=_ROOT_REF,
        origin_root_ref=_ROOT_REF,
        runtime_owner_uuid=owner_uuid,
    )
    assert condition_binding.definition_ref == _CONDITION_REF
    assert condition_binding.provided_by_ref == _ACTION_REF
    assert handler_binding.definition_ref == _HANDLER_REF
    assert handler_binding.provided_by_ref == _CONDITION_REF

    for behavior in (action, condition, handler):
        assert "behavior_binding" not in behavior.model_dump()
        copied = behavior.model_copy(deep=True)
        assert copied.behavior_binding == behavior.behavior_binding


def test_explicit_provider_child_binding_uses_item_and_action_dependency_closure() -> None:
    """Declared children bind through exact providers without fallback inference."""
    owner_uuid = uuid4()
    item = UsableItem(
        source_entity_uuid=owner_uuid,
        content_ref=_ROOT_REF,
    )
    action, condition, _ = _runtime_chain(owner_uuid)
    binder = BehaviorBinder(_registry())

    with runtime_behavior_binding_gateway(binder):
        action_binding = bind_runtime_behavior_child(
            action,
            provider=item,
            runtime_owner_uuid=item.uuid,
        )
        condition_binding = bind_runtime_behavior_child(
            condition,
            provider=action,
            runtime_owner_uuid=owner_uuid,
        )

    assert action_binding == BehaviorBinding(
        definition_ref=_ACTION_REF,
        provided_by_ref=_ROOT_REF,
        origin_root_ref=_ROOT_REF,
        runtime_owner_uuid=item.uuid,
    )
    assert condition_binding == BehaviorBinding(
        definition_ref=_CONDITION_REF,
        provided_by_ref=_ACTION_REF,
        origin_root_ref=_ROOT_REF,
        runtime_owner_uuid=owner_uuid,
    )

    unrelated = UsableItem(
        source_entity_uuid=owner_uuid,
        content_ref=_UNRELATED_ROOT_REF,
    )
    other_action, _, _ = _runtime_chain(owner_uuid)
    with runtime_behavior_binding_gateway(binder):
        with pytest.raises(ValueError, match="not reachable from provider"):
            bind_runtime_behavior_child(
                other_action,
                provider=unrelated,
                runtime_owner_uuid=unrelated.uuid,
            )


def test_structural_provider_ref_binds_declared_behaviors_without_fake_provider() -> None:
    """Structural grants attribute declared behaviors to one exact feature."""
    owner_uuid = uuid4()
    action, condition, handler = _runtime_chain(owner_uuid)
    binder = BehaviorBinder(_registry())

    action_binding = binder.bind_granted(
        action,
        provider_ref=_FEATURE_REF,
        runtime_owner_uuid=owner_uuid,
    )
    condition_binding = binder.bind_granted(
        condition,
        provider_ref=_FEATURE_REF,
        runtime_owner_uuid=owner_uuid,
    )
    handler_binding = binder.bind_granted(
        handler,
        provider_ref=_FEATURE_REF,
        runtime_owner_uuid=owner_uuid,
    )

    assert action_binding == BehaviorBinding(
        definition_ref=_ACTION_REF,
        provided_by_ref=_FEATURE_REF,
        origin_root_ref=None,
        runtime_owner_uuid=owner_uuid,
    )
    assert condition_binding == BehaviorBinding(
        definition_ref=_CONDITION_REF,
        provided_by_ref=_FEATURE_REF,
        origin_root_ref=None,
        runtime_owner_uuid=owner_uuid,
    )
    assert handler_binding == BehaviorBinding(
        definition_ref=_HANDLER_REF,
        provided_by_ref=_FEATURE_REF,
        origin_root_ref=None,
        runtime_owner_uuid=owner_uuid,
    )


def test_structural_provider_ref_gives_private_handler_stable_identity() -> None:
    """An undeclared implementation handler inherits only its exact provider."""
    owner_uuid = uuid4()
    handler = EventHandler(
        name="Clockwork Recharge",
        source_entity_uuid=owner_uuid,
        event_processor=_processor,
        use_register=False,
    )
    binder = BehaviorBinder(_registry())

    binding = binder.bind_granted(
        handler,
        provider_ref=_FEATURE_REF,
        runtime_owner_uuid=owner_uuid,
    )

    assert binding == BehaviorBinding(
        definition_ref=_FEATURE_REF,
        provided_by_ref=_FEATURE_REF,
        origin_root_ref=None,
        runtime_owner_uuid=owner_uuid,
    )
    assert handler.content_kind is RuntimeBehaviorKind.CLASS_FEATURE
    assert handler.semantic_key == (
        f"{_FEATURE_REF.identity_key}#handler.clockwork_recharge"
    )

    invalid = EventHandler(
        name="Clockwork Inventory",
        content_kind=RuntimeBehaviorKind.ITEM,
        source_entity_uuid=owner_uuid,
        event_processor=_processor,
        use_register=False,
    )
    with pytest.raises(ValueError, match="not a supported runtime behavior"):
        binder.bind_granted(
            invalid,
            provider_ref=_FEATURE_REF,
            runtime_owner_uuid=owner_uuid,
        )


def test_structural_provider_ref_requires_exact_dependency_reachability() -> None:
    owner_uuid = uuid4()
    action, _, _ = _runtime_chain(owner_uuid)

    with pytest.raises(ValueError, match="not reachable from provider"):
        BehaviorBinder(_registry()).bind_granted(
            action,
            provider_ref=_UNRELATED_ROOT_REF,
            runtime_owner_uuid=owner_uuid,
        )


def test_content_runtime_exposes_structural_provider_binding() -> None:
    owner_uuid = uuid4()
    action, _, _ = _runtime_chain(owner_uuid)
    runtime = ContentSystemRuntime()
    runtime.install(LoadedContentSystem(
        registry=_registry(),
        packs=(),
        built_in_artifact_digest="a" * 64,
        content_set_digest="b" * 64,
    ))

    binding = runtime.bind_granted_behavior(
        action,
        provider_ref=_FEATURE_REF,
        runtime_owner_uuid=owner_uuid,
    )

    assert binding == BehaviorBinding(
        definition_ref=_ACTION_REF,
        provided_by_ref=_FEATURE_REF,
        origin_root_ref=None,
        runtime_owner_uuid=owner_uuid,
    )


def test_structural_bindings_survive_action_and_handler_admission() -> None:
    """Admission preserves exact pre-bound grants and fences runtime owners."""
    reset_engine_runtime(grid_size=(4, 4))
    entity = _core_entity()
    owner_uuid = entity.uuid
    action, active_condition, _ = _runtime_chain(owner_uuid)
    action.template = True
    handler = EventHandler(
        name="Clockwork Recharge",
        source_entity_uuid=owner_uuid,
        event_processor=_processor,
        use_register=False,
    )
    binder = BehaviorBinder(_registry())
    action_binding = binder.bind_granted(
        action,
        provider_ref=_FEATURE_REF,
        runtime_owner_uuid=owner_uuid,
    )
    handler_binding = binder.bind_granted(
        handler,
        provider_ref=_FEATURE_REF,
        runtime_owner_uuid=owner_uuid,
    )
    binder.bind_granted(
        active_condition,
        provider_ref=_FEATURE_REF,
        runtime_owner_uuid=owner_uuid,
    )

    with runtime_behavior_binding_gateway(binder):
        with runtime_behavior_provider(active_condition):
            entity.register_action(action)
            entity.add_event_handler(handler)

    assert entity.registered_actions[-1] is action
    assert action.behavior_binding is action_binding
    assert entity.event_handlers[handler.uuid] is handler
    assert handler.behavior_binding is handler_binding
    with pytest.raises(ValueError, match="different owner"):
        bind_runtime_action_before_admission(
            action,
            runtime_owner_uuid=uuid4(),
        )
    mismatched_handler = EventHandler(
        name="Clockwork Mismatch",
        source_entity_uuid=uuid4(),
        event_processor=_processor,
        use_register=False,
    )
    binder.bind_granted(
        mismatched_handler,
        provider_ref=_FEATURE_REF,
        runtime_owner_uuid=owner_uuid,
    )
    with pytest.raises(ValueError, match="different owner"):
        bind_runtime_handler_before_admission(mismatched_handler)


def test_provider_owned_handler_keeps_distinct_reaction_kind() -> None:
    """A condition may provide a reaction handler without relabeling it."""
    owner_uuid = uuid4()
    _, condition, _ = _runtime_chain(owner_uuid)
    binder = BehaviorBinder(_registry())
    binder.bind(
        condition,
        declaration_source=_ClockworkChargeCondition,
        expected_kind=RuntimeBehaviorKind.CONDITION,
        provided_by_ref=_ACTION_REF,
        origin_root_ref=_ROOT_REF,
        runtime_owner_uuid=owner_uuid,
    )
    reaction = EventHandler(
        name="Clockwork Parry",
        semantic_key="fixture.clockwork_parry",
        content_kind=RuntimeBehaviorKind.REACTION,
        source_entity_uuid=owner_uuid,
        event_processor=_processor,
        use_register=False,
    )

    binding = binder.bind_child(
        reaction,
        provider=condition,
        runtime_owner_uuid=owner_uuid,
    )

    assert reaction.content_kind is RuntimeBehaviorKind.REACTION
    assert reaction.semantic_key == "fixture.clockwork_parry"
    assert binding == BehaviorBinding(
        definition_ref=_CONDITION_REF,
        provided_by_ref=_CONDITION_REF,
        origin_root_ref=_ROOT_REF,
        runtime_owner_uuid=owner_uuid,
    )
    invalid = EventHandler(
        name="Clockwork Inventory",
        content_kind=RuntimeBehaviorKind.ITEM,
        source_entity_uuid=owner_uuid,
        event_processor=_processor,
        use_register=False,
    )
    with pytest.raises(ValueError, match="not a supported runtime behavior"):
        binder.bind_child(
            invalid,
            provider=condition,
            runtime_owner_uuid=owner_uuid,
        )


def test_action_events_freeze_active_binding_without_serializing_runtime_state() -> None:
    """Causal event versions retain exact authored identity outside raw payloads."""
    owner_uuid = uuid4()
    action, _, _ = _runtime_chain(owner_uuid)
    binder = BehaviorBinder(_registry())
    binding = binder.bind(
        action,
        declaration_source=_WindClockworkAction,
        expected_kind=RuntimeBehaviorKind.ACTION,
        provided_by_ref=_ROOT_REF,
        origin_root_ref=_ROOT_REF,
        runtime_owner_uuid=owner_uuid,
    )

    with runtime_behavior_provider(action):
        declaration = ActionEvent.from_costs(
            [],
            source_entity_uuid=owner_uuid,
            use_register=False,
        )

    assert declaration.behavior_binding == binding
    assert declaration.model_copy(deep=True).behavior_binding == binding
    assert "behavior_binding" not in declaration.model_dump()
    assert "behavior_binding" not in declaration.model_dump(mode="json")


def test_unbound_internal_behavior_masks_outer_authored_provider_scope() -> None:
    """Private children cannot inherit across an undeclared causal boundary."""
    owner_uuid = uuid4()
    action, _, _ = _runtime_chain(owner_uuid)
    binder = BehaviorBinder(_registry())
    binding = binder.bind(
        action,
        declaration_source=_WindClockworkAction,
        expected_kind=RuntimeBehaviorKind.ACTION,
        provided_by_ref=_ROOT_REF,
        origin_root_ref=_ROOT_REF,
        runtime_owner_uuid=owner_uuid,
    )

    with runtime_behavior_provider(action):
        assert active_runtime_behavior_binding() == binding
        with runtime_behavior_provider(_UnboundInternalBehavior()):
            assert active_runtime_behavior_binding() is None
        assert active_runtime_behavior_binding() == binding
    assert active_runtime_behavior_binding() is None


def test_handler_emitted_action_event_freezes_handler_binding() -> None:
    """Non-movement reactions inherit the exact handler that emitted them."""
    owner_uuid = uuid4()
    _, _, handler = _runtime_chain(owner_uuid)
    binder = BehaviorBinder(_registry())
    binding = binder.bind(
        handler,
        declaration_source=_ClockworkChargeHandler,
        expected_kind=RuntimeBehaviorKind.SYSTEM,
        provided_by_ref=_CONDITION_REF,
        origin_root_ref=_ROOT_REF,
        runtime_owner_uuid=owner_uuid,
    )
    emitted: list[ActionEvent] = []

    def emit(event: Event, source_entity_uuid: UUID) -> Event:
        emitted.append(ActionEvent(
            source_entity_uuid=source_entity_uuid,
            parent_event=event.uuid,
        ))
        return event

    handler.event_processor = emit
    trigger = Event(
        event_type=EventType.TRIGGER_EVENT,
        source_entity_uuid=owner_uuid,
        use_register=False,
    )

    EventQueue._invoke_handler(handler, trigger)

    assert [event.behavior_binding for event in emitted] == [binding]
    assert "behavior_binding" not in emitted[0].model_dump()


def test_behavior_binding_is_frozen_and_rebinding_is_exactly_idempotent() -> None:
    owner_uuid = uuid4()
    action, _, _ = _runtime_chain(owner_uuid)
    binder = BehaviorBinder(_registry())
    first = binder.bind(
        action,
        declaration_source=_WindClockworkAction,
        expected_kind=RuntimeBehaviorKind.ACTION,
        provided_by_ref=_ROOT_REF,
        origin_root_ref=_ROOT_REF,
        runtime_owner_uuid=owner_uuid,
    )
    second = binder.bind(
        action,
        declaration_source=_WindClockworkAction,
        expected_kind=RuntimeBehaviorKind.ACTION,
        provided_by_ref=_ROOT_REF,
        origin_root_ref=_ROOT_REF,
        runtime_owner_uuid=owner_uuid,
    )

    assert second is first
    with pytest.raises(ValidationError, match="frozen"):
        first.runtime_owner_uuid = uuid4()
    with pytest.raises(ValueError, match="conflicting content binding"):
        binder.bind(
            action,
            declaration_source=_WindClockworkAction,
            expected_kind=RuntimeBehaviorKind.ACTION,
            provided_by_ref=_ROOT_REF,
            origin_root_ref=_ROOT_REF,
            runtime_owner_uuid=uuid4(),
        )


def test_binder_rejects_kind_and_runtime_family_disagreement() -> None:
    owner_uuid = uuid4()
    action, condition, handler = _runtime_chain(owner_uuid)
    binder = BehaviorBinder(_registry())

    with pytest.raises(ValueError, match="declared action, expected spell"):
        binder.bind(
            action,
            declaration_source=_WindClockworkAction,
            expected_kind=RuntimeBehaviorKind.SPELL,
            provided_by_ref=_ROOT_REF,
            runtime_owner_uuid=owner_uuid,
        )
    with pytest.raises(TypeError, match="action cannot bind a BaseCondition"):
        binder.bind(
            condition,
            declaration_source=_WindClockworkAction,
            expected_kind=RuntimeBehaviorKind.ACTION,
            provided_by_ref=_ROOT_REF,
            runtime_owner_uuid=owner_uuid,
        )
    condition.content_kind = RuntimeBehaviorKind.TRAIT
    with pytest.raises(ValueError, match="Condition content kind"):
        binder.bind(
            condition,
            declaration_source=_ClockworkChargeCondition,
            expected_kind=RuntimeBehaviorKind.CONDITION,
            provided_by_ref=_ACTION_REF,
            runtime_owner_uuid=owner_uuid,
        )
    with pytest.raises(ValueError, match="Handler content kind"):
        handler.content_kind = RuntimeBehaviorKind.TRAIT
        binder.bind(
            handler,
            declaration_source=_ClockworkChargeHandler,
            expected_kind=RuntimeBehaviorKind.SYSTEM,
            provided_by_ref=_CONDITION_REF,
            runtime_owner_uuid=owner_uuid,
        )


def test_binder_rejects_unreachable_providers_and_roots() -> None:
    owner_uuid = uuid4()
    action, condition, _ = _runtime_chain(owner_uuid)
    binder = BehaviorBinder(_registry())

    with pytest.raises(ValueError, match="not reachable from provider"):
        binder.bind(
            condition,
            declaration_source=_ClockworkChargeCondition,
            expected_kind=RuntimeBehaviorKind.CONDITION,
            provided_by_ref=_HANDLER_REF,
            runtime_owner_uuid=owner_uuid,
        )
    with pytest.raises(ValueError, match="not reachable from origin root"):
        binder.bind(
            action,
            declaration_source=_WindClockworkAction,
            expected_kind=RuntimeBehaviorKind.ACTION,
            provided_by_ref=_ROOT_REF,
            origin_root_ref=_UNRELATED_ROOT_REF,
            runtime_owner_uuid=owner_uuid,
        )
    with pytest.raises(NonConstructibleContentError, match="metadata-only"):
        binder.bind(
            action,
            declaration_source=_WindClockworkAction,
            expected_kind=RuntimeBehaviorKind.ACTION,
            provided_by_ref=_ACTION_REF,
            origin_root_ref=_ACTION_REF,
            runtime_owner_uuid=owner_uuid,
        )


def test_binder_requires_the_exact_registered_decorator_source() -> None:
    owner_uuid = uuid4()
    action, _, _ = _runtime_chain(owner_uuid)
    binder = BehaviorBinder(_registry())

    @behavior_identity(
        definition_kind=ContentDefinitionKind.ACTION,
        runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
        pack_id=_PACK_ID,
        content_id="action.wind_clockwork",
        version=1,
        descriptor=ContentDescriptorSpec(
            display_name="Wind Clockwork",
            visibility=ContentVisibility.PUBLIC,
        ),
        provenance=_PROVENANCE,
        dependencies=(
            ContentDependency(
                relation=ContentDependencyRelation.APPLIES_CONDITION,
                target_ref=_CONDITION_REF,
            ),
        ),
    )
    class EquivalentButUnregisteredAction:
        pass

    with pytest.raises(ValueError, match="exact declaration installed"):
        binder.bind(
            action,
            declaration_source=EquivalentButUnregisteredAction,
            expected_kind=RuntimeBehaviorKind.ACTION,
            provided_by_ref=_ROOT_REF,
            runtime_owner_uuid=owner_uuid,
        )

    with pytest.raises(ValueError, match="has no content declaration"):
        binder.bind(
            action,
            declaration_source=object,
            expected_kind=RuntimeBehaviorKind.ACTION,
            provided_by_ref=_ROOT_REF,
            runtime_owner_uuid=owner_uuid,
        )


def _install_core_behavior_runtime() -> None:
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())


def _core_entity() -> Entity:
    owner_uuid = uuid4()
    return Entity.create(
        source_entity_uuid=owner_uuid,
        name="Core behavior owner",
        config=EntityConfig(),
    )


def test_core_behavior_declaration_tuples_are_exact_and_public() -> None:
    action_ids = tuple(
        declaration.ref.content_id
        for declaration in CORE_STANDARD_ACTION_DECLARATIONS
    )
    condition_ids = tuple(
        declaration.ref.content_id
        for declaration in CORE_STANDARD_CONDITION_DECLARATIONS
    )

    assert action_ids == (
        "action.move",
        "action.swim",
        "action.attack",
        "action.dash",
        "action.dodge",
        "action.disengage",
        "action.drop_concentration",
        "action.shake_awake",
        "action.hide",
        "action.jump",
        "action.shove",
        "action.pick_up",
        "action.attack_object",
    )
    assert condition_ids == (
        "condition.underwater",
        "condition.blinded",
        "condition.charmed",
        "condition.dashing",
        "condition.deafened",
        "condition.exhaustion",
        "condition.dodging",
        "condition.disengaging",
        "condition.frightened",
        "condition.grappled",
        "condition.incapacitated",
        "condition.invisible",
        "condition.paralyzed",
        "condition.petrified",
        "condition.poisoned",
        "condition.prone",
        "condition.stunned",
        "condition.restrained",
        "condition.unconscious",
        "condition.concentrating",
        "condition.no_reactions",
        "condition.hidden",
    )
    for declaration in (
        *CORE_STANDARD_ACTION_DECLARATIONS,
        *CORE_STANDARD_CONDITION_DECLARATIONS,
    ):
        assert declaration.ref.pack_id == "core.rules"
        assert declaration.descriptor.visibility == ContentVisibility.PUBLIC
        assert declaration.runtime_behavior_kind in {
            RuntimeBehaviorKind.ACTION,
            RuntimeBehaviorKind.CONDITION,
        }


def test_standard_action_registration_binds_exact_self_provided_identity() -> None:
    _install_core_behavior_runtime()
    reset_engine_runtime(grid_size=(4, 4))
    entity = _core_entity()
    setup_standard_actions(entity)
    entity.register_action(Attack(
        source_entity_uuid=entity.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=True,
    ))

    assert sorted(
        get_content_declaration(type(action)).ref.identity_key
        for action in entity.registered_actions
    ) == sorted(
        declaration.ref.identity_key
        for declaration in CORE_STANDARD_ACTION_DECLARATIONS
    )
    for action in entity.registered_actions:
        declaration = get_content_declaration(type(action))
        binding = action.behavior_binding
        assert binding == BehaviorBinding(
            definition_ref=declaration.ref,
            provided_by_ref=declaration.ref,
            origin_root_ref=None,
            runtime_owner_uuid=entity.uuid,
        )
        assert action.get_semantic_key() == (
            f"{type(action).__module__}.{type(action).__qualname__}"
        )
        assert action.get_semantic_key() != declaration.ref.identity_key
        assert "behavior_binding" not in action.model_dump()
        assert (
            action.model_copy(deep=True).behavior_binding
            == action.behavior_binding
        )


def test_condition_binds_before_its_handler_enters_the_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_core_behavior_runtime()
    reset_engine_runtime(grid_size=(4, 4))
    entity = _core_entity()
    observed_at_admission: list[BehaviorBinding | None] = []
    original_add = EventQueue.add_event_handler

    def checked_add(
        cls: type[EventQueue],
        handler: EventHandler,
    ) -> None:
        del cls
        observed_at_admission.append(handler.behavior_binding)
        original_add(handler)

    monkeypatch.setattr(
        EventQueue,
        "add_event_handler",
        classmethod(checked_add),
    )
    condition = Concentrating(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        spell_name="Focused fixture",
    )
    result = entity.add_condition(condition, check_save_throw=False)

    assert result is not None and not result.canceled
    declaration = get_content_declaration(Concentrating)
    expected = BehaviorBinding(
        definition_ref=declaration.ref,
        provided_by_ref=declaration.ref,
        origin_root_ref=None,
        runtime_owner_uuid=entity.uuid,
    )
    assert condition.behavior_binding == expected
    assert condition.get_semantic_key() == declaration.ref.identity_key
    assert condition.get_content_kind() == RuntimeBehaviorKind.CONDITION
    assert observed_at_admission == [expected]

    handler = next(
        handler
        for handler in entity.event_handlers.values()
        if handler.name.startswith("Concentration Check")
    )
    assert handler.behavior_binding == expected
    assert handler.content_kind == RuntimeBehaviorKind.CONDITION
    assert handler.get_semantic_key().startswith(
        f"{declaration.ref.identity_key}#handler.",
    )
    assert "behavior_binding" not in condition.model_dump()
    assert (
        condition.model_copy(deep=True).behavior_binding
        == condition.behavior_binding
    )


def test_decorated_core_behavior_missing_from_registry_fails_closed() -> None:
    owner_uuid = uuid4()
    move = Move(
        source_entity_uuid=owner_uuid,
        template=True,
        use_register=False,
    )

    with pytest.raises(KeyError, match="core.rules:action:action.move"):
        BehaviorBinder(_registry()).bind_independent(
            move,
            runtime_owner_uuid=owner_uuid,
        )


def test_undecorated_subclass_does_not_inherit_authored_identity() -> None:
    _install_core_behavior_runtime()
    reset_engine_runtime(grid_size=(4, 4))

    class CustomMove(Move):
        pass

    entity = _core_entity()
    custom = CustomMove(
        source_entity_uuid=entity.uuid,
        template=True,
        use_register=False,
    )
    with pytest.raises(ValueError, match="has no content declaration"):
        get_content_declaration(CustomMove)

    entity.register_action(custom)
    assert custom.behavior_binding is None
    assert custom.get_semantic_key().endswith(
        ".test_undecorated_subclass_does_not_inherit_authored_identity."
        "<locals>.CustomMove",
    )


def test_declared_behavior_without_installed_runtime_fails_closed() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    script = """
from uuid import uuid4
from dnd.actions import Move
from dnd.entity import Entity, EntityConfig

owner_uuid = uuid4()
entity = Entity.create(
    source_entity_uuid=owner_uuid,
    name="Missing runtime",
    config=EntityConfig(),
)
entity.register_action(Move(source_entity_uuid=owner_uuid, template=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert (
        "Content system is not installed for declared runtime behavior"
        in completed.stderr
    )


def test_core_owner_layers_import_only_the_cold_binding_leaf() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    owner_paths = (
        repository_root / "dnd" / "core" / "base_actions.py",
        repository_root / "dnd" / "core" / "base_conditions.py",
        repository_root / "dnd" / "core" / "base_block.py",
        repository_root / "dnd" / "core" / "events.py",
        repository_root / "dnd" / "entity.py",
    )
    forbidden: list[str] = []
    for path in owner_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.startswith("dnd.content_system")
            ):
                forbidden.append(
                    f"{path.relative_to(repository_root)}:{node.lineno}",
                )
            if isinstance(node, ast.Import):
                forbidden.extend(
                    f"{path.relative_to(repository_root)}:{node.lineno}"
                    for alias in node.names
                    if alias.name.startswith("dnd.content_system")
                )
    assert forbidden == []
