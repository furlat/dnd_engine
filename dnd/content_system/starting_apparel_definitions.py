"""Exact persistent starting-apparel packages for custom characters."""

from __future__ import annotations

from types import MappingProxyType

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


def _entry(item_id: str, slot: BodyPart) -> StartingEquipmentPackageEntry:
    return StartingEquipmentPackageEntry(
        item_id=item_id,
        equipped_slot=slot,
    )


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
            _entry("apparel.common_clothes.farmhand_tunic", BodyPart.BODY),
            _entry("apparel.leather_shoes.brown", BodyPart.FEET),
        )),
    ),
    (
        "travelers_clothes",
        "Traveler's Clothes",
        20,
        StartingEquipmentPackageDefinition(entries=(
            _entry("apparel.travelers_clothes.thief_garb", BodyPart.BODY),
            _entry("apparel.leather_boots.dark", BodyPart.FEET),
        )),
    ),
    (
        "fine_clothes",
        "Fine Clothes",
        30,
        StartingEquipmentPackageDefinition(entries=(
            _entry("apparel.fine_clothes", BodyPart.BODY),
            _entry("apparel.leather_shoes.brown", BodyPart.FEET),
        )),
    ),
    (
        "robes",
        "Robes",
        40,
        StartingEquipmentPackageDefinition(entries=(
            _entry("apparel.robes.hedge_wizard", BodyPart.BODY),
            _entry("apparel.cloth_shoes.blue", BodyPart.FEET),
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
                "The package authenticates exact direct apparel identities; "
                "class armor remains mechanically authoritative when both "
                "occupy the body slot."
            ),
        ),
        definition_payload=definition,
        dependencies=(),
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
