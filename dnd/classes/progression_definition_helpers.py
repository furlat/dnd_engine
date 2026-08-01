"""Shared pure builders for authored class progression definitions."""

from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.durable_characters import (
    BuildChoiceRequirement,
    ChoiceRequirementKind,
    ClassDefinition,
    ProficiencySubject,
    ProficiencySubjectKind,
    SubclassDefinition,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import (
    ContentDeclarationMode,
    compute_definition_contract_hash,
)


def typed_progression_ref(
    *,
    pack_id: str,
    version: int,
    definition_kind: ContentDefinitionKind,
    content_id: str,
    definition_model: type[ClassDefinition] | type[SubclassDefinition],
) -> ContentRef:
    """Build the exact ref for one typed class or subclass definition."""
    return ContentRef(
        pack_id=pack_id,
        definition_kind=definition_kind,
        content_id=content_id,
        content_version=version,
        definition_contract_hash=compute_definition_contract_hash(
            mode=ContentDeclarationMode.TYPED_DEFINITION,
            definition_kind=definition_kind,
            definition_model=definition_model,
        ),
    )


def proficiency_subject(
    kind: ProficiencySubjectKind,
    subject_id: str,
) -> ProficiencySubject:
    """Build one canonical proficiency subject."""
    return ProficiencySubject(subject_kind=kind, subject_id=subject_id)


def single_ref_choice(
    *,
    choice_id: str,
    choice_kind: ChoiceRequirementKind,
    allowed_refs: tuple[ContentRef, ...] = (),
    count: int = 1,
    minimum_selections: int | None = None,
) -> BuildChoiceRequirement:
    """Build one bounded choice over exact content refs."""
    return BuildChoiceRequirement(
        choice_id=choice_id,
        choice_kind=choice_kind,
        minimum_selections=(
            count if minimum_selections is None else minimum_selections
        ),
        maximum_selections=count,
        allowed_refs=allowed_refs,
    )


def ordered_refs(*refs: ContentRef) -> tuple[ContentRef, ...]:
    """Return exact refs in deterministic identity order."""
    return tuple(sorted(refs, key=lambda ref: ref.identity_key))


def structural_progression_provenance(
    source_anchor: str,
) -> ContentProvenance:
    """Build the common reviewed SRD structural-progression provenance."""
    return ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=source_anchor,
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Pure additive structural definition; runtime mechanics are "
            "installed separately through exact source-owned grant bindings."
        ),
    )


def progression_dependencies(
    refs: tuple[ContentRef, ...],
    *,
    relation: ContentDependencyRelation,
    notes: str,
) -> tuple[ContentDependency, ...]:
    """Build one deterministic unique dependency ledger."""
    unique = {ref.identity_key: ref for ref in refs}
    return tuple(
        ContentDependency(
            relation=relation,
            target_ref=ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes=notes,
        )
        for _, ref in sorted(unique.items())
    )


__all__ = [
    "ordered_refs",
    "proficiency_subject",
    "progression_dependencies",
    "single_ref_choice",
    "structural_progression_provenance",
    "typed_progression_ref",
]
