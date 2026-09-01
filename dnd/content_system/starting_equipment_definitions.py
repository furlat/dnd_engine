"""Authored SRD starting-equipment packages for implemented classes."""

from __future__ import annotations

from types import MappingProxyType

from dnd.classes.starting_equipment_refs import (
    STARTING_EQUIPMENT_PACKAGE_REFS_BY_CLASS,
    STARTING_EQUIPMENT_PACKAGE_REFS_BY_PRESET,
)
from dnd.core.content.descriptors import (
    ContentDescriptor,
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import (
    ContentDeclaration,
    ContentDeclarationMode,
)
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
    StartingEquipmentPackageEntry,
)
from dnd.core.equipment_types import BodyPart, WeaponSlot
def _entry(
    item_id: str,
    *,
    equipped_slot=None,
) -> StartingEquipmentPackageEntry:
    return StartingEquipmentPackageEntry(
        item_id=item_id,
        equipped_slot=equipped_slot,
    )


_PACKAGE_ROWS: tuple[
    tuple[
        str,
        str,
        str,
        int,
        StartingEquipmentPackageDefinition,
    ],
    ...,
] = (
    (
        "fighter",
        "sword_shield",
        "Fighter: Sword and Shield",
        10,
        StartingEquipmentPackageDefinition(entries=(
            _entry("armor.chain_mail", equipped_slot=BodyPart.BODY),
            _entry("weapon.longsword", equipped_slot=WeaponSlot.MELEE_MAIN),
            _entry("shield.shield", equipped_slot=WeaponSlot.MELEE_OFF),
        )),
    ),
    (
        "fighter",
        "greatsword",
        "Fighter: Greatsword",
        20,
        StartingEquipmentPackageDefinition(entries=(
            _entry("armor.chain_mail", equipped_slot=BodyPart.BODY),
            _entry("weapon.greatsword", equipped_slot=WeaponSlot.MELEE_MAIN),
        )),
    ),
    (
        "fighter",
        "dual_wield",
        "Fighter: Dual Wield",
        30,
        StartingEquipmentPackageDefinition(entries=(
            _entry("armor.chain_mail", equipped_slot=BodyPart.BODY),
            _entry("weapon.shortsword", equipped_slot=WeaponSlot.MELEE_MAIN),
            _entry("weapon.shortsword", equipped_slot=WeaponSlot.MELEE_OFF),
        )),
    ),
    (
        "fighter",
        "archery",
        "Fighter: Archery",
        40,
        StartingEquipmentPackageDefinition(entries=(
            _entry("armor.studded_leather", equipped_slot=BodyPart.BODY),
            _entry("weapon.shortsword", equipped_slot=WeaponSlot.MELEE_MAIN),
            _entry("weapon.longbow", equipped_slot=WeaponSlot.RANGED_MAIN),
        )),
    ),
    (
        "barbarian",
        "greataxe",
        "Barbarian: Greataxe",
        10,
        StartingEquipmentPackageDefinition(entries=(
            _entry("weapon.greataxe", equipped_slot=WeaponSlot.MELEE_MAIN),
        )),
    ),
    (
        "barbarian",
        "dual_axes",
        "Barbarian: Dual Axes",
        20,
        StartingEquipmentPackageDefinition(entries=(
            _entry("weapon.handaxe", equipped_slot=WeaponSlot.MELEE_MAIN),
            _entry("weapon.handaxe", equipped_slot=WeaponSlot.MELEE_OFF),
        )),
    ),
    (
        "barbarian",
        "sword_shield",
        "Barbarian: Sword and Shield",
        30,
        StartingEquipmentPackageDefinition(entries=(
            _entry("weapon.longsword", equipped_slot=WeaponSlot.MELEE_MAIN),
            _entry("shield.shield", equipped_slot=WeaponSlot.MELEE_OFF),
        )),
    ),
    (
        "sorcerer",
        "dagger",
        "Sorcerer: Dagger",
        10,
        StartingEquipmentPackageDefinition(entries=(
            _entry("weapon.dagger", equipped_slot=WeaponSlot.MELEE_MAIN),
        )),
    ),
    (
        "sorcerer",
        "quarterstaff",
        "Sorcerer: Quarterstaff",
        20,
        StartingEquipmentPackageDefinition(entries=(
            _entry("weapon.quarterstaff", equipped_slot=WeaponSlot.MELEE_MAIN),
        )),
    ),
)


def _declaration(
    *,
    class_id: str,
    preset_id: str,
    display_name: str,
    sort_order: int,
    definition: StartingEquipmentPackageDefinition,
) -> ContentDeclaration:
    ref = STARTING_EQUIPMENT_PACKAGE_REFS_BY_PRESET[(class_id, preset_id)]
    return ContentDeclaration(
        ref=ref,
        mode=ContentDeclarationMode.TYPED_DEFINITION,
        descriptor=ContentDescriptor.from_spec(
            ref,
            ContentDescriptorSpec(
                display_name=display_name,
                description=(
                    "Exact SRD items and initial equipped slots for "
                    "this implemented class equipment preset."
                ),
                tags=(
                    "character_creation",
                    "player_capable",
                    "srd_5_1",
                    "starting_equipment",
                    class_id,
                ),
                visibility=ContentVisibility.PUBLIC,
                presentation=ContentPresentation(
                    visual_variant_key=ref.content_id,
                    ui_group=f"starting_equipment.{class_id}",
                ),
                ordering=ContentOrdering(
                    sort_group=f"starting_equipment.{class_id}",
                    sort_order=sort_order,
                ),
            ),
        ),
        provenance=ContentProvenance(
            primary_source_id="wotc.srd_5_1_cc",
            source_anchor=(
                "SRD 5.1 class starting equipment adapted to implemented "
                f"{class_id}/{preset_id} engine presets"
            ),
            relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
            fidelity=ContentFidelity.COMPLETE,
            review_status=ContentReviewStatus.REVIEWED,
            notes=(
                "Contains only direct SRD item identities so the class layer "
                "does not depend on deployment-specific content. Neurodragon "
                "premades add their own curated inventory separately."
            ),
        ),
        definition_payload=definition,
        dependencies=(),
    )


STARTING_EQUIPMENT_PACKAGE_DECLARATIONS = tuple(
    _declaration(
        class_id=class_id,
        preset_id=preset_id,
        display_name=display_name,
        sort_order=sort_order,
        definition=definition,
    )
    for (
        class_id,
        preset_id,
        display_name,
        sort_order,
        definition,
    ) in _PACKAGE_ROWS
)
STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET = MappingProxyType({
    (class_id, preset_id): declaration
    for (
        class_id,
        preset_id,
        _display_name,
        _sort_order,
        _definition,
    ), declaration in zip(
        _PACKAGE_ROWS,
        STARTING_EQUIPMENT_PACKAGE_DECLARATIONS,
        strict=True,
    )
})


__all__ = [
    "STARTING_EQUIPMENT_PACKAGE_DECLARATIONS",
    "STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET",
    "STARTING_EQUIPMENT_PACKAGE_REFS_BY_CLASS",
]
