"""Authored condition lifecycle and provider dependencies survive installation."""

import pytest

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.core.content.descriptors import ContentVisibility
from dnd.core.content.effects import ConditionEffectCoverage
from dnd.core.content.registration import get_content_declaration
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.items.consumables import _ApplyWeaponCoatAction


@pytest.fixture(scope="module")
def loaded_content():
    return bootstrap_content_system(pack_roots=())


def test_every_public_condition_exposes_typed_lifecycle(loaded_content) -> None:
    """Refresh policy and break/removal facts live on condition definitions."""
    public_conditions = tuple(
        declaration
        for declaration in loaded_content.registry.declarations.values()
        if declaration.descriptor.visibility is ContentVisibility.PUBLIC
        and declaration.runtime_behavior_kind is RuntimeBehaviorKind.CONDITION
    )
    assert public_conditions
    assert all(declaration.condition_lifecycle is not None for declaration in public_conditions)
    assert all(declaration.condition_effect_coverage in {
        ConditionEffectCoverage.PROFILED,
        ConditionEffectCoverage.INTERNAL_ONLY,
        ConditionEffectCoverage.LIFECYCLE_ONLY,
    } for declaration in public_conditions)


def test_consumable_keeps_its_authored_condition_dependency(loaded_content) -> None:
    declared = get_content_declaration(_ApplyWeaponCoatAction)
    installed = loaded_content.registry.resolve_definition(declared.ref)
    assert installed.dependencies == declared.dependencies
    applied = tuple(edge.target_ref for edge in installed.dependencies
                    if edge.relation is ContentDependencyRelation.APPLIES_CONDITION)
    assert applied
    assert all(loaded_content.registry.resolve_definition(ref).runtime_behavior_kind
               is RuntimeBehaviorKind.CONDITION for ref in applied)
