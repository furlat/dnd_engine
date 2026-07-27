"""Explicit authored identities for directly registered player reactions."""

from __future__ import annotations

from dataclasses import dataclass

from dnd.classes.paladin import DivineSmiteHandler
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
    resolve_content_icon_key,
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
from dnd.core.events import EventHandler
from dnd.reactions import OpportunityAttackHandler


@dataclass(frozen=True, slots=True)
class ReactionBehaviorIdentitySpec:
    """One reviewed class-to-reaction identity association."""

    handler_type: type[EventHandler]
    pack_id: str
    content_id: str
    display_name: str
    description: str
    icon_key: str
    source_anchor: str
    sort_group: str
    sort_order: int


REACTION_BEHAVIOR_IDENTITY_SPECS: tuple[
    ReactionBehaviorIdentitySpec,
    ...,
] = (
    ReactionBehaviorIdentitySpec(
        handler_type=OpportunityAttackHandler,
        pack_id="core.rules",
        content_id="reaction.opportunity_attack",
        display_name="Opportunity Attack",
        description=(
            "Use a reaction to make one melee attack when a hostile creature "
            "leaves the actor's reach."
        ),
        icon_key="reaction.opportunity-attack-handler",
        source_anchor=(
            "SRD 5.1 (CC-BY-4.0), Combat: Opportunity Attacks"
        ),
        sort_group="reactions.standard",
        sort_order=10,
    ),
    ReactionBehaviorIdentitySpec(
        handler_type=DivineSmiteHandler,
        pack_id="content.srd_5_1_cc",
        content_id="reaction.class_feature.paladin.divine_smite",
        display_name="Divine Smite",
        description=(
            "Spend a selected spell-slot level to add radiant damage to a "
            "successful melee weapon hit."
        ),
        icon_key="reaction.class_feature.paladin.divine_smite",
        source_anchor=(
            "SRD 5.1 (CC-BY-4.0), Classes: Paladin, Divine Smite"
        ),
        sort_group="reactions.class_features",
        sort_order=10,
    ),
)


def _declare_reaction_behavior(
    spec: ReactionBehaviorIdentitySpec,
) -> ContentDeclaration:
    """Attach one exact metadata-only declaration to its concrete handler."""
    try:
        get_content_declaration(spec.handler_type)
    except ValueError:
        pass
    else:
        raise ValueError(
            f"{spec.handler_type!r} already owns a content declaration",
        )

    decorator = behavior_identity(
        definition_kind=ContentDefinitionKind.REACTION,
        runtime_behavior_kind=RuntimeBehaviorKind.REACTION,
        pack_id=spec.pack_id,
        content_id=spec.content_id,
        version=1,
        descriptor=ContentDescriptorSpec(
            display_name=spec.display_name,
            description=spec.description,
            tags=("reaction", "srd"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                icon_key=spec.icon_key,
                visual_variant_key=spec.content_id.removeprefix("reaction."),
                vfx_profile=spec.content_id,
                ui_group=spec.sort_group,
            ),
            ordering=ContentOrdering(
                sort_group=spec.sort_group,
                sort_order=spec.sort_order,
            ),
        ),
        provenance=ContentProvenance(
            primary_source_id="wotc.srd_5_1_cc",
            source_anchor=spec.source_anchor,
            relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.REVIEWED,
            notes=(
                "Existing playable reaction behavior; exact identity does not "
                "claim that every optional rules edge case is implemented."
            ),
        ),
    )
    decorator(spec.handler_type)
    declaration = get_content_declaration(spec.handler_type)
    if (
        declaration.ref.pack_id != spec.pack_id
        or declaration.ref.definition_kind
        is not ContentDefinitionKind.REACTION
        or declaration.ref.content_id != spec.content_id
        or declaration.runtime_behavior_kind
        is not RuntimeBehaviorKind.REACTION
        or declaration.descriptor.presentation.icon_key
        != resolve_content_icon_key(
            declaration.ref,
            spec.icon_key,
        )[0]
    ):
        raise ValueError(
            "Reaction behavior declaration disagrees with its explicit spec "
            f"for {spec.handler_type!r}",
        )
    return declaration


REACTION_BEHAVIOR_DECLARATIONS: tuple[ContentDeclaration, ...] = tuple(
    _declare_reaction_behavior(spec)
    for spec in REACTION_BEHAVIOR_IDENTITY_SPECS
)

if len({
    declaration.ref.identity_key
    for declaration in REACTION_BEHAVIOR_DECLARATIONS
}) != len(REACTION_BEHAVIOR_DECLARATIONS):
    raise ValueError("Reaction behavior identity inventory is not one-to-one")


__all__ = [
    "REACTION_BEHAVIOR_DECLARATIONS",
    "REACTION_BEHAVIOR_IDENTITY_SPECS",
    "ReactionBehaviorIdentitySpec",
]
