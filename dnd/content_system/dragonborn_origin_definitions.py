"""Typed declarations for the ten SRD 5.1 Dragonborn ancestries."""

from __future__ import annotations

from types import MappingProxyType

from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptor,
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.dragonborn import (
    DragonbornAncestry,
    DragonbornAncestryFeatureDefinition,
    DragonbornBreathGeometry,
    DragonbornDamageType,
    DragonbornSaveAbility,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import (
    ContentDeclaration,
    ContentDeclarationMode,
    compute_definition_contract_hash,
)
from dnd.origins.dragonborn import DRAGONBORN_BREATH_WEAPON_REF


_PACK_ID = "content.srd_5_1_cc"
_VERSION = 1
_DEFINITION_KIND = ContentDefinitionKind.TRAIT
_CONTRACT_HASH = compute_definition_contract_hash(
    mode=ContentDeclarationMode.TYPED_DEFINITION,
    definition_kind=_DEFINITION_KIND,
    definition_model=DragonbornAncestryFeatureDefinition,
)


def _ref(ancestry: DragonbornAncestry) -> ContentRef:
    return ContentRef(
        pack_id=_PACK_ID,
        definition_kind=_DEFINITION_KIND,
        content_id=f"trait.origin.dragonborn.ancestry.{ancestry.value}",
        content_version=_VERSION,
        definition_contract_hash=_CONTRACT_HASH,
    )


def _declaration(
    *,
    ancestry: DragonbornAncestry,
    damage_type: DragonbornDamageType,
    breath_geometry: DragonbornBreathGeometry,
    save_ability: DragonbornSaveAbility,
    sort_order: int,
) -> ContentDeclaration:
    ref = _ref(ancestry)
    display_ancestry = ancestry.value.title()
    geometry_label = (
        "30-by-5-foot line"
        if breath_geometry is DragonbornBreathGeometry.LINE
        else "15-foot cone"
    )
    definition = DragonbornAncestryFeatureDefinition(
        ancestry=ancestry,
        damage_type=damage_type,
        breath_geometry=breath_geometry,
        save_ability=save_ability,
        line_length_feet=(
            30
            if breath_geometry is DragonbornBreathGeometry.LINE
            else None
        ),
        line_width_feet=(
            5
            if breath_geometry is DragonbornBreathGeometry.LINE
            else None
        ),
        cone_length_feet=(
            15
            if breath_geometry is DragonbornBreathGeometry.CONE
            else None
        ),
    )
    return ContentDeclaration(
        ref=ref,
        mode=ContentDeclarationMode.TYPED_DEFINITION,
        descriptor=ContentDescriptor.from_spec(
            ref,
            ContentDescriptorSpec(
                display_name=f"{display_ancestry} Draconic Ancestry",
                description=(
                    f"Gain resistance to {damage_type.lower()} damage "
                    f"and a {geometry_label} Breath Weapon using a "
                    f"{save_ability.upper()} save."
                ),
                tags=(
                    "character_creation",
                    "dragonborn",
                    "origin_feature",
                    "srd_5_1",
                ),
                visibility=ContentVisibility.PUBLIC,
                presentation=ContentPresentation(
                    visual_variant_key=(
                        f"dragonborn_ancestry_{ancestry.value}"
                    ),
                    ui_group="origin_features.dragonborn",
                ),
                ordering=ContentOrdering(
                    sort_group="origin_features.dragonborn",
                    sort_order=sort_order,
                ),
            ),
        ),
        provenance=ContentProvenance(
            primary_source_id="wotc.srd_5_1_cc",
            source_anchor=(
                "SRD 5.1 Races: Dragonborn Traits — Draconic Ancestry and "
                "Breath Weapon"
            ),
            relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
            fidelity=ContentFidelity.COMPLETE,
            review_status=ContentReviewStatus.REVIEWED,
            notes=(
                "One exact ancestry selection owns its resistance and "
                "configures the shared Breath Weapon behavior."
            ),
        ),
        definition_payload=definition,
        dependencies=(
            ContentDependency(
                relation=ContentDependencyRelation.GRANTS_ACTION,
                target_ref=DRAGONBORN_BREATH_WEAPON_REF,
                notes=(
                    "The selected ancestry configures and grants one Breath "
                    "Weapon action."
                ),
            ),
        ),
    )


_ANCESTRY_RULES: tuple[
    tuple[
        DragonbornAncestry,
        DragonbornDamageType,
        DragonbornBreathGeometry,
        DragonbornSaveAbility,
    ],
    ...,
] = (
    (
        DragonbornAncestry.BLACK,
        "Acid",
        DragonbornBreathGeometry.LINE,
        "dexterity",
    ),
    (
        DragonbornAncestry.BLUE,
        "Lightning",
        DragonbornBreathGeometry.LINE,
        "dexterity",
    ),
    (
        DragonbornAncestry.BRASS,
        "Fire",
        DragonbornBreathGeometry.LINE,
        "dexterity",
    ),
    (
        DragonbornAncestry.BRONZE,
        "Lightning",
        DragonbornBreathGeometry.LINE,
        "dexterity",
    ),
    (
        DragonbornAncestry.COPPER,
        "Acid",
        DragonbornBreathGeometry.LINE,
        "dexterity",
    ),
    (
        DragonbornAncestry.GOLD,
        "Fire",
        DragonbornBreathGeometry.CONE,
        "dexterity",
    ),
    (
        DragonbornAncestry.GREEN,
        "Poison",
        DragonbornBreathGeometry.CONE,
        "constitution",
    ),
    (
        DragonbornAncestry.RED,
        "Fire",
        DragonbornBreathGeometry.CONE,
        "dexterity",
    ),
    (
        DragonbornAncestry.SILVER,
        "Cold",
        DragonbornBreathGeometry.CONE,
        "constitution",
    ),
    (
        DragonbornAncestry.WHITE,
        "Cold",
        DragonbornBreathGeometry.CONE,
        "constitution",
    ),
)

DRAGONBORN_ANCESTRY_DECLARATIONS = tuple(sorted(
    (
        _declaration(
            ancestry=ancestry,
            damage_type=damage_type,
            breath_geometry=breath_geometry,
            save_ability=save_ability,
            sort_order=index * 10,
        )
        for index, (
            ancestry,
            damage_type,
            breath_geometry,
            save_ability,
        ) in enumerate(_ANCESTRY_RULES, start=1)
    ),
    key=lambda declaration: declaration.ref.identity_key,
))

DRAGONBORN_ANCESTRY_DECLARATIONS_BY_ANCESTRY = MappingProxyType({
    definition.ancestry: declaration
    for declaration in DRAGONBORN_ANCESTRY_DECLARATIONS
    if isinstance(
        (definition := declaration.definition_payload),
        DragonbornAncestryFeatureDefinition,
    )
})


__all__ = [
    "DRAGONBORN_ANCESTRY_DECLARATIONS",
    "DRAGONBORN_ANCESTRY_DECLARATIONS_BY_ANCESTRY",
]
