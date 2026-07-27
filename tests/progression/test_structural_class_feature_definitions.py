"""Exact authored identities for class features applied structurally."""

from dnd.classes.structural_feature_definitions import (
    REMARKABLE_ATHLETE_DECLARATION,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.registration import ContentDeclarationMode
from dnd.core.content.runtime import RuntimeBehaviorKind


def test_remarkable_athlete_is_an_exact_structural_feature_identity() -> None:
    declaration = REMARKABLE_ATHLETE_DECLARATION

    assert declaration.ref.pack_id == "content.srd_5_1_cc"
    assert declaration.ref.definition_kind == ContentDefinitionKind.CLASS_FEATURE
    assert declaration.ref.content_id == (
        "class_feature.fighter.remarkable_athlete"
    )
    assert declaration.mode == ContentDeclarationMode.BEHAVIOR_IDENTITY
    assert declaration.runtime_behavior_kind == RuntimeBehaviorKind.CLASS_FEATURE
    assert "structural_grant" in declaration.descriptor.tags

    resolved = bootstrap_content_system().registry.resolve_definition(
        declaration.ref,
    )
    assert resolved.ref == declaration.ref
    assert resolved.descriptor.presentation.icon_key == "action.jump"
