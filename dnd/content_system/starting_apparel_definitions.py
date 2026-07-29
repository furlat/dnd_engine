"""Exact persistent starting-apparel packages for custom characters."""

from __future__ import annotations

from types import MappingProxyType

from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptor,
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
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
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
    StartingEquipmentPackageEntry,
)
from dnd.core.equipment_types import BodyPart
from dnd.items.apparel_presets import (
    BLUE_CLOTH_SHOES_PRESET,
    BROWN_LEATHER_SHOES_PRESET,
    DARK_BOOTS_PRESET,
    FARMHAND_TUNIC_PRESET,
    HEDGE_WIZARD_ROBE_PRESET,
    THIEF_GARB_PRESET,
)
from dnd.items.authored_variant_presets import (
    AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESET_ID,
)


STARTING_APPAREL_CHOICE_ID = "character.creation.starting_apparel"
_PACK_ID = "content.neurodragon"
_VERSION = 1
_CONTRACT_HASH = compute_definition_contract_hash(
    mode=ContentDeclarationMode.TYPED_DEFINITION,
    definition_kind=ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE,
    definition_model=StartingEquipmentPackageDefinition,
)


def _ref(apparel_id: str) -> ContentRef:
    return ContentRef(
        pack_id=_PACK_ID,
        definition_kind=ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE,
        content_id=f"starting_apparel.{apparel_id}",
        content_version=_VERSION,
        definition_contract_hash=_CONTRACT_HASH,
    )


def _entry(preset, slot: BodyPart) -> StartingEquipmentPackageEntry:
    return StartingEquipmentPackageEntry(
        recipe=preset.recipe,
        equipped_slot=slot,
    )


_NOBLE_ATTIRE_PRESET = AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESET_ID[
    "item_variant.fine_clothes.noble_s_attire"
]
_PACKAGE_ROWS: tuple[
    tuple[
        str,
        str,
        int,
        StartingEquipmentPackageDefinition,
    ],
    ...,
] = (
    (
        "common_clothes",
        "Common Clothes",
        10,
        StartingEquipmentPackageDefinition(entries=(
            _entry(FARMHAND_TUNIC_PRESET, BodyPart.BODY),
            _entry(BROWN_LEATHER_SHOES_PRESET, BodyPart.FEET),
        )),
    ),
    (
        "travelers_clothes",
        "Traveler's Clothes",
        20,
        StartingEquipmentPackageDefinition(entries=(
            _entry(THIEF_GARB_PRESET, BodyPart.BODY),
            _entry(DARK_BOOTS_PRESET, BodyPart.FEET),
        )),
    ),
    (
        "fine_clothes",
        "Fine Clothes",
        30,
        StartingEquipmentPackageDefinition(entries=(
            _entry(_NOBLE_ATTIRE_PRESET, BodyPart.BODY),
            _entry(BROWN_LEATHER_SHOES_PRESET, BodyPart.FEET),
        )),
    ),
    (
        "robes",
        "Robes",
        40,
        StartingEquipmentPackageDefinition(entries=(
            _entry(HEDGE_WIZARD_ROBE_PRESET, BodyPart.BODY),
            _entry(BLUE_CLOTH_SHOES_PRESET, BodyPart.FEET),
        )),
    ),
)


def _declaration(
    *,
    apparel_id: str,
    display_name: str,
    sort_order: int,
    definition: StartingEquipmentPackageDefinition,
) -> ContentDeclaration:
    ref = _ref(apparel_id)
    related_refs = tuple(sorted(
        {
            entry.recipe.ref.identity_key: entry.recipe.ref
            for entry in definition.entries
        }.values(),
        key=lambda item_ref: item_ref.identity_key,
    ))
    return ContentDeclaration(
        ref=ref,
        mode=ContentDeclarationMode.TYPED_DEFINITION,
        descriptor=ContentDescriptor.from_spec(
            ref,
            ContentDescriptorSpec(
                display_name=display_name,
                description=(
                    "Exact persistent body and footwear presentation selected "
                    "independently of class starting equipment."
                ),
                tags=(
                    "character_creation",
                    "player_capable",
                    "starting_apparel",
                    "neurodragon",
                ),
                visibility=ContentVisibility.PUBLIC,
                presentation=ContentPresentation(
                    visual_variant_key=ref.content_id,
                    ui_group="starting_apparel",
                ),
                ordering=ContentOrdering(
                    sort_group="starting_apparel",
                    sort_order=sort_order,
                ),
                related_content_refs=related_refs,
            ),
        ),
        provenance=ContentProvenance(
            primary_source_id="neurodragon.original_b2b3930",
            source_anchor=(
                "NeuroDragon authored layered apparel inventory selected "
                f"for custom character creation: {apparel_id}"
            ),
            relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
            fidelity=ContentFidelity.COMPLETE,
            review_status=ContentReviewStatus.REVIEWED,
            notes=(
                "The package authenticates exact reviewed recipe variants; "
                "class armor remains mechanically authoritative when both "
                "occupy the body slot."
            ),
        ),
        definition_payload=definition,
        dependencies=tuple(
            ContentDependency(
                relation=ContentDependencyRelation.EQUIPS_ITEM,
                target_ref=item_ref,
                phase=ContentDependencyPhase.CONSTRUCTION,
                notes=(
                    "Starting apparel grants this exact reviewed item recipe."
                ),
            )
            for item_ref in related_refs
        ),
    )


STARTING_APPAREL_PACKAGE_DECLARATIONS = tuple(
    _declaration(
        apparel_id=apparel_id,
        display_name=display_name,
        sort_order=sort_order,
        definition=definition,
    )
    for apparel_id, display_name, sort_order, definition in _PACKAGE_ROWS
)
STARTING_APPAREL_PACKAGE_REFS = tuple(
    declaration.ref for declaration in STARTING_APPAREL_PACKAGE_DECLARATIONS
)
STARTING_APPAREL_PACKAGE_DECLARATIONS_BY_ID = MappingProxyType({
    apparel_id: declaration
    for (
        apparel_id,
        _display_name,
        _sort_order,
        _definition,
    ), declaration in zip(
        _PACKAGE_ROWS,
        STARTING_APPAREL_PACKAGE_DECLARATIONS,
        strict=True,
    )
})


__all__ = [
    "STARTING_APPAREL_CHOICE_ID",
    "STARTING_APPAREL_PACKAGE_DECLARATIONS",
    "STARTING_APPAREL_PACKAGE_DECLARATIONS_BY_ID",
    "STARTING_APPAREL_PACKAGE_REFS",
]
