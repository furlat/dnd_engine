"""Exact persistent starting possessions for the SRD Acolyte background."""

from __future__ import annotations

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


_CONTRACT_HASH = compute_definition_contract_hash(
    mode=ContentDeclarationMode.TYPED_DEFINITION,
    definition_kind=ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE,
    definition_model=StartingEquipmentPackageDefinition,
)
ACOLYTE_STARTING_HOLDINGS_REF = ContentRef(
    pack_id="content.srd_5_1_cc",
    definition_kind=ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE,
    content_id="starting_holdings.background.acolyte",
    content_version=1,
    definition_contract_hash=_CONTRACT_HASH,
)
ACOLYTE_STARTING_HOLDINGS_DEFINITION = StartingEquipmentPackageDefinition(
    entries=(
        StartingEquipmentPackageEntry(item_id="gear.holy_symbol"),
        StartingEquipmentPackageEntry(item_id="gear.prayer_book"),
        StartingEquipmentPackageEntry(
            item_id="gear.incense",
            quantity=5,
        ),
        StartingEquipmentPackageEntry(
            item_id="gear.vestments",
        ),
        StartingEquipmentPackageEntry(item_id="gear.common_clothes"),
    ),
)


ACOLYTE_STARTING_HOLDINGS_DECLARATION = ContentDeclaration(
    ref=ACOLYTE_STARTING_HOLDINGS_REF,
    mode=ContentDeclarationMode.TYPED_DEFINITION,
    descriptor=ContentDescriptor.from_spec(
        ACOLYTE_STARTING_HOLDINGS_REF,
        ContentDescriptorSpec(
            display_name="Acolyte Starting Possessions",
            description=(
                "A holy symbol, prayer book, five sticks of incense, "
                "vestments, and common clothes."
            ),
            tags=(
                "acolyte",
                "background_equipment",
                "character_creation",
                "srd_5_1",
                "starting_holdings",
            ),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                visual_variant_key="starting_holdings.background.acolyte",
                ui_group="starting_holdings.background",
            ),
            ordering=ContentOrdering(
                sort_group="starting_holdings.background",
                sort_order=10,
            ),
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor="SRD 5.1 Backgrounds: Acolyte — Equipment",
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Every durable item fact is represented exactly. The SRD's "
            "15 gp is not claimed because no canonical durable currency "
            "owner exists in the engine."
        ),
    ),
    definition_payload=ACOLYTE_STARTING_HOLDINGS_DEFINITION,
    dependencies=(),
)


__all__ = [
    "ACOLYTE_STARTING_HOLDINGS_DECLARATION",
    "ACOLYTE_STARTING_HOLDINGS_DEFINITION",
    "ACOLYTE_STARTING_HOLDINGS_REF",
]
