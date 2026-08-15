"""Authored SRD starting-equipment packages for implemented classes."""

from __future__ import annotations

from types import MappingProxyType

from dnd.classes.starting_equipment_refs import (
    STARTING_EQUIPMENT_PACKAGE_REFS_BY_CLASS,
    STARTING_EQUIPMENT_PACKAGE_REFS_BY_PRESET,
)
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
from dnd.items.armors import (
    CHAIN_MAIL_RECIPE,
    SHIELD_RECIPE,
    STUDDED_LEATHER_RECIPE,
)
from dnd.items.weapons import (
    DAGGER_RECIPE,
    GREATAXE_RECIPE,
    GREATSWORD_RECIPE,
    HANDAXE_RECIPE,
    LONGBOW_RECIPE,
    LONGSWORD_RECIPE,
    QUARTERSTAFF_RECIPE,
    SHORTSWORD_RECIPE,
)


def _entry(
    recipe,
    *,
    equipped_slot=None,
) -> StartingEquipmentPackageEntry:
    return StartingEquipmentPackageEntry(
        recipe=recipe,
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
            _entry(CHAIN_MAIL_RECIPE, equipped_slot=BodyPart.BODY),
            _entry(LONGSWORD_RECIPE, equipped_slot=WeaponSlot.MELEE_MAIN),
            _entry(SHIELD_RECIPE, equipped_slot=WeaponSlot.MELEE_OFF),
        )),
    ),
    (
        "fighter",
        "greatsword",
        "Fighter: Greatsword",
        20,
        StartingEquipmentPackageDefinition(entries=(
            _entry(CHAIN_MAIL_RECIPE, equipped_slot=BodyPart.BODY),
            _entry(GREATSWORD_RECIPE, equipped_slot=WeaponSlot.MELEE_MAIN),
        )),
    ),
    (
        "fighter",
        "dual_wield",
        "Fighter: Dual Wield",
        30,
        StartingEquipmentPackageDefinition(entries=(
            _entry(CHAIN_MAIL_RECIPE, equipped_slot=BodyPart.BODY),
            _entry(SHORTSWORD_RECIPE, equipped_slot=WeaponSlot.MELEE_MAIN),
            _entry(SHORTSWORD_RECIPE, equipped_slot=WeaponSlot.MELEE_OFF),
        )),
    ),
    (
        "fighter",
        "archery",
        "Fighter: Archery",
        40,
        StartingEquipmentPackageDefinition(entries=(
            _entry(STUDDED_LEATHER_RECIPE, equipped_slot=BodyPart.BODY),
            _entry(SHORTSWORD_RECIPE, equipped_slot=WeaponSlot.MELEE_MAIN),
            _entry(LONGBOW_RECIPE, equipped_slot=WeaponSlot.RANGED_MAIN),
        )),
    ),
    (
        "barbarian",
        "greataxe",
        "Barbarian: Greataxe",
        10,
        StartingEquipmentPackageDefinition(entries=(
            _entry(GREATAXE_RECIPE, equipped_slot=WeaponSlot.MELEE_MAIN),
        )),
    ),
    (
        "barbarian",
        "dual_axes",
        "Barbarian: Dual Axes",
        20,
        StartingEquipmentPackageDefinition(entries=(
            _entry(HANDAXE_RECIPE, equipped_slot=WeaponSlot.MELEE_MAIN),
            _entry(HANDAXE_RECIPE, equipped_slot=WeaponSlot.MELEE_OFF),
        )),
    ),
    (
        "barbarian",
        "sword_shield",
        "Barbarian: Sword and Shield",
        30,
        StartingEquipmentPackageDefinition(entries=(
            _entry(LONGSWORD_RECIPE, equipped_slot=WeaponSlot.MELEE_MAIN),
            _entry(SHIELD_RECIPE, equipped_slot=WeaponSlot.MELEE_OFF),
        )),
    ),
    (
        "sorcerer",
        "dagger",
        "Sorcerer: Dagger",
        10,
        StartingEquipmentPackageDefinition(entries=(
            _entry(DAGGER_RECIPE, equipped_slot=WeaponSlot.MELEE_MAIN),
        )),
    ),
    (
        "sorcerer",
        "quarterstaff",
        "Sorcerer: Quarterstaff",
        20,
        StartingEquipmentPackageDefinition(entries=(
            _entry(QUARTERSTAFF_RECIPE, equipped_slot=WeaponSlot.MELEE_MAIN),
        )),
    ),
)


def _dependencies(
    definition: StartingEquipmentPackageDefinition,
) -> tuple[ContentDependency, ...]:
    rows = {
        entry.recipe.ref.identity_key: ContentDependency(
            relation=ContentDependencyRelation.EQUIPS_ITEM,
            target_ref=entry.recipe.ref,
            phase=ContentDependencyPhase.CONSTRUCTION,
            notes="Starting package equips this exact SRD item recipe.",
        )
        for entry in definition.entries
    }
    return tuple(rows[key] for key in sorted(rows))


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
                    "Exact SRD item recipes and initial equipped slots for "
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
                related_content_refs=tuple(sorted(
                    {
                        entry.recipe.ref.identity_key: entry.recipe.ref
                        for entry in definition.entries
                    }.values(),
                    key=lambda item_ref: item_ref.identity_key,
                )),
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
                "Contains only SRD-owned item recipes so the SRD class layer "
                "does not depend on deployment-specific content. Neurodragon "
                "premades add their own curated inventory separately."
            ),
        ),
        definition_payload=definition,
        dependencies=_dependencies(definition),
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
