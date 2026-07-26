"""Exact authored identity for every active player-visible condition."""

from __future__ import annotations

from collections.abc import Iterable

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_IDENTITY_SPECS,
)
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionCategory
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.descriptors import ContentVisibility
from dnd.core.content.registration import get_content_declaration
from dnd.core.content.runtime import RuntimeBehaviorKind
from server.content_catalog import build_public_content_catalog


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
    """Every visible leaf owns one exact non-Python-path declaration."""
    descendants = _active_descendants(BaseCondition)
    leaves = _leaf_types(descendants)
    public = tuple(
        condition_type
        for condition_type in leaves
        if _condition_category(condition_type) is not ConditionCategory.INTERNAL
    )
    declarations = tuple(
        get_content_declaration(condition_type)
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


def test_every_public_condition_definition_resolves_in_public_catalog() -> None:
    """Production-visible condition definitions have an exact catalog join."""
    loaded = bootstrap_content_system()
    catalog = build_public_content_catalog(loaded)
    public_keys = {
        entry.ref.identity_key
        for entry in catalog.entries
    }
    leaves = _leaf_types(_active_descendants(BaseCondition))

    declarations = tuple(
        get_content_declaration(condition_type)
        for condition_type in leaves
        if _condition_category(condition_type) is not ConditionCategory.INTERNAL
    )
    expected_keys = {
        declaration.ref.identity_key
        for declaration in declarations
        if declaration.descriptor.visibility is ContentVisibility.PUBLIC
    }
    developer_keys = {
        declaration.ref.identity_key
        for declaration in declarations
        if declaration.descriptor.visibility is ContentVisibility.DEVELOPER
    }
    assert expected_keys <= public_keys
    assert developer_keys.isdisjoint(public_keys)


def test_internal_condition_leaves_are_not_public_catalog_definitions() -> None:
    """Technical markers must not become player-authored condition content."""
    loaded = bootstrap_content_system()
    catalog = build_public_content_catalog(loaded)
    public_keys = {
        entry.ref.identity_key
        for entry in catalog.entries
    }
    leaves = _leaf_types(_active_descendants(BaseCondition))

    for condition_type in leaves:
        if _condition_category(condition_type) is not ConditionCategory.INTERNAL:
            continue
        namespace = condition_type.__dict__
        declaration = namespace.get("__dnd_content_declaration__")
        if declaration is not None:
            assert declaration.ref.identity_key not in public_keys
