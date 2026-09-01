"""Maintained exact-owner proofs for runtime behavior bindings."""

from uuid import UUID, uuid4

import pytest

from dnd.content_system.behavior_bindings import BehaviorBinder
from dnd.core.base_actions import BaseAction
from dnd.core.base_conditions import BaseCondition
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import ContentDescriptorSpec, ContentVisibility
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import behavior_identity, get_content_declaration
from dnd.core.content.runtime import BehaviorBinding, RuntimeBehaviorKind
from dnd.core.events import Event, EventHandler


_PACK_ID = "fixture.behavior_binding"
_PROVENANCE = ContentProvenance(
    primary_source_id="fixture.behavior_binding.source",
    source_anchor="Runtime behavior binding fixture",
    relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
    fidelity=ContentFidelity.COMPLETE,
    review_status=ContentReviewStatus.REVIEWED,
)


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
    dependencies=(ContentDependency(
        relation=ContentDependencyRelation.INSTALLS_HANDLER,
        target_ref=_HANDLER_REF,
    ),),
)
class _ClockworkChargeCondition(BaseCondition):
    pass


_CONDITION_REF = get_content_declaration(_ClockworkChargeCondition).ref


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
    dependencies=(ContentDependency(
        relation=ContentDependencyRelation.APPLIES_CONDITION,
        target_ref=_CONDITION_REF,
    ),),
)
class _WindClockworkAction(BaseAction):
    pass


_ACTION_REF = get_content_declaration(_WindClockworkAction).ref
_ROOT_ID = "item.clockwork"


def _binder() -> BehaviorBinder:
    return BehaviorBinder({
        source: get_content_declaration(source)
        for source in (
            _ClockworkChargeHandler,
            _ClockworkChargeCondition,
            _WindClockworkAction,
        )
    })


def _processor(event: Event, source_entity_uuid: UUID) -> Event:
    del source_entity_uuid
    return event


def _runtime_chain(owner_uuid: UUID):
    return (
        _WindClockworkAction(source_entity_uuid=owner_uuid, use_register=False),
        _ClockworkChargeCondition(
            source_entity_uuid=owner_uuid,
            target_entity_uuid=owner_uuid,
            use_register=False,
        ),
        _ClockworkChargeHandler(
            source_entity_uuid=owner_uuid,
            event_processor=_processor,
            content_kind=RuntimeBehaviorKind.SYSTEM,
            use_register=False,
        ),
    )


def test_binder_attributes_one_action_condition_handler_vertical_chain() -> None:
    owner_uuid = uuid4()
    action, condition, handler = _runtime_chain(owner_uuid)
    binder = _binder()

    action_binding = binder.bind_direct_child(
        action,
        provided_by_id=_ROOT_ID,
        origin_root_id=_ROOT_ID,
        runtime_owner_uuid=owner_uuid,
    )
    condition_binding = binder.bind_child(
        condition,
        provider_binding=action_binding,
        runtime_owner_uuid=owner_uuid,
    )
    handler_binding = binder.bind_child(
        handler,
        provider_binding=condition_binding,
        runtime_owner_uuid=owner_uuid,
    )

    assert action_binding == BehaviorBinding(
        behavior_id=_ACTION_REF.content_id,
        provided_by_id=_ROOT_ID,
        origin_root_id=_ROOT_ID,
        runtime_owner_uuid=owner_uuid,
    )
    assert condition_binding.behavior_id == _CONDITION_REF.content_id
    assert condition_binding.provided_by_id == _ACTION_REF.content_id
    assert handler_binding.behavior_id == _HANDLER_REF.content_id
    assert handler_binding.provided_by_id == _CONDITION_REF.content_id


def test_binder_requires_the_exact_registered_decorator_source() -> None:
    """A matching decorator is insufficient without exact cold admission."""
    owner_uuid = uuid4()
    binder = _binder()

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
        dependencies=(ContentDependency(
            relation=ContentDependencyRelation.APPLIES_CONDITION,
            target_ref=_CONDITION_REF,
        ),),
    )
    class EquivalentButUnregisteredAction(BaseAction):
        pass

    with pytest.raises(ValueError, match="no cold class admission"):
        binder.bind_direct_child(
            EquivalentButUnregisteredAction(
                source_entity_uuid=owner_uuid,
                use_register=False,
            ),
            provided_by_id=_ROOT_ID,
            origin_root_id=_ROOT_ID,
            runtime_owner_uuid=owner_uuid,
        )
