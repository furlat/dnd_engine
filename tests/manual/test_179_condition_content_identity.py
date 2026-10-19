"""Exact authored identity for every active player-visible condition."""

from __future__ import annotations

from collections.abc import Iterable

from devtools.generate_event_contract import import_dnd_modules

from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_IDENTITY_SPECS,
)
from dnd.core.base_conditions import BaseCondition
from dnd.content_system.builtin_inventory import BUILT_IN_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.core.condition_types import ConditionCategory
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.registration import get_content_declaration
from dnd.core.content.runtime import RuntimeBehaviorKind


def _active_descendants(
    condition_type: type[BaseCondition],
) -> set[type[BaseCondition]]:
    descendants: set[type[BaseCondition]] = set()
    for child_type in condition_type.__subclasses__():
        if child_type.__module__.startswith("dnd."):
            descendants.add(child_type)
        descendants.update(_active_descendants(child_type))
    return descendants


def _leaf_types(
    condition_types: Iterable[type[BaseCondition]],
) -> tuple[type[BaseCondition], ...]:
    active = set(condition_types)
    return tuple(sorted(
        (
            condition_type
            for condition_type in active
            if not any(
                child_type in active
                for child_type in condition_type.__subclasses__()
            )
        ),
        key=lambda condition_type: (
            condition_type.__module__,
            condition_type.__qualname__,
        ),
    ))


def _condition_category(
    condition_type: type[BaseCondition],
) -> ConditionCategory:
    value = condition_type.model_fields["condition_category"].default
    assert isinstance(value, ConditionCategory)
    return value


def test_active_condition_inventory_is_exact_and_fully_declared() -> None:
    """Live catalog condition leaves own exact identities; direct class grants are separate."""
    import_dnd_modules()
    descendants = _active_descendants(BaseCondition)
    declared = {condition_type for condition_type in BUILT_IN_BEHAVIOR_DECLARATIONS_BY_CLASS
                if issubclass(condition_type, BaseCondition)}
    assert declared <= descendants
    leaves = _leaf_types(declared)
    public = tuple(
        condition_type
        for condition_type in leaves
        if _condition_category(condition_type) is not ConditionCategory.INTERNAL
    )
    declarations = tuple(
        BUILT_IN_BEHAVIOR_DECLARATIONS_BY_CLASS[condition_type]
        for condition_type in public
    )
    assert len({
        declaration.ref.identity_key
        for declaration in declarations
    }) == len(public)
    assert {
        spec.condition_type
        for spec in CONDITION_BEHAVIOR_IDENTITY_SPECS
    } <= set(descendants)
    assert all(
        declaration.ref.definition_kind
        in {
            ContentDefinitionKind.CONDITION,
            ContentDefinitionKind.TRAIT,
            ContentDefinitionKind.FEAT,
            ContentDefinitionKind.CLASS_FEATURE,
        }
        for declaration in declarations
    )
    assert all(
        declaration.runtime_behavior_kind
        in {
            RuntimeBehaviorKind.CONDITION,
            RuntimeBehaviorKind.TRAIT,
            RuntimeBehaviorKind.FEAT,
            RuntimeBehaviorKind.CLASS_FEATURE,
        }
        for declaration in declarations
    )
    assert all(
        not declaration.ref.content_id.startswith("unbound.")
        for declaration in declarations
    )


