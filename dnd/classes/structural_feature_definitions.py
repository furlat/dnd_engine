"""Authored identities for class features installed by structural appliers.

These markers are deliberately not runtime conditions.  The character
composition layer resolves their exact content references and installs
source-owned component grants with reversible receipts.
"""

from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import (
    ContentDeclaration,
    behavior_identity,
    get_content_declaration,
)
from dnd.core.content.runtime import RuntimeBehaviorKind


@behavior_identity(
    definition_kind=ContentDefinitionKind.CLASS_FEATURE,
    runtime_behavior_kind=RuntimeBehaviorKind.CLASS_FEATURE,
    pack_id="content.srd_5_1_cc",
    content_id="class_feature.fighter.remarkable_athlete",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Remarkable Athlete",
        description=(
            "Add half proficiency, rounded up, to Strength, Dexterity, and "
            "Constitution checks that do not already use proficiency, and "
            "increase running long-jump distance by the Strength modifier."
        ),
        tags=(
            "class_feature",
            "fighter",
            "passive",
            "structural_grant",
        ),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="class_feature.fighter.remarkable_athlete",
            visual_variant_key="class_feature.fighter.remarkable_athlete",
            ui_group="class_features.fighter",
        ),
        ordering=ContentOrdering(
            sort_group="class_features.fighter",
            sort_order=70,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor="Fighter: Champion — Remarkable Athlete",
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Declared as a structural feature so character recomposition can "
            "remove its exact proficiency and jump-distance sources without "
            "using a permanent condition instance."
        ),
    ),
)
class RemarkableAthleteStructuralFeature:
    """Identity marker consumed only by the structural grant binding."""


REMARKABLE_ATHLETE_DECLARATION: ContentDeclaration = (
    get_content_declaration(RemarkableAthleteStructuralFeature)
)


@behavior_identity(
    definition_kind=ContentDefinitionKind.CLASS_FEATURE,
    runtime_behavior_kind=RuntimeBehaviorKind.CLASS_FEATURE,
    pack_id="content.srd_5_1_cc",
    content_id="class_feature.barbarian.unarmored_defense",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Unarmored Defense",
        description=(
            "While not wearing armor, Armor Class equals 10 plus Dexterity "
            "and Constitution modifiers; a shield remains permitted."
        ),
        tags=(
            "barbarian",
            "class_feature",
            "passive",
            "structural_grant",
        ),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="item.natural-armor",
            visual_variant_key="class_feature.barbarian.unarmored_defense",
            ui_group="class_features.barbarian",
        ),
        ordering=ContentOrdering(
            sort_group="class_features.barbarian",
            sort_order=10,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor="Barbarian — Unarmored Defense",
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Declared structurally so character recomposition can apply and "
            "remove the first-acquired exclusive AC formula by exact source."
        ),
    ),
)
class BarbarianUnarmoredDefenseStructuralFeature:
    """Identity marker consumed only by the structural grant binding."""


UNARMORED_DEFENSE_DECLARATION: ContentDeclaration = get_content_declaration(
    BarbarianUnarmoredDefenseStructuralFeature,
)


STRUCTURAL_CLASS_FEATURE_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    REMARKABLE_ATHLETE_DECLARATION,
    UNARMORED_DEFENSE_DECLARATION,
)


__all__ = [
    "BarbarianUnarmoredDefenseStructuralFeature",
    "REMARKABLE_ATHLETE_DECLARATION",
    "RemarkableAthleteStructuralFeature",
    "STRUCTURAL_CLASS_FEATURE_DECLARATIONS",
    "UNARMORED_DEFENSE_DECLARATION",
]
