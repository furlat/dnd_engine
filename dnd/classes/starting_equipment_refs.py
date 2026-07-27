"""Exact SRD starting-equipment package identities used by class data."""

from __future__ import annotations

from types import MappingProxyType

from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.registration import (
    ContentDeclarationMode,
    compute_definition_contract_hash,
)
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
)


_PACK_ID = "content.srd_5_1_cc"
_VERSION = 1
_CONTRACT_HASH = compute_definition_contract_hash(
    mode=ContentDeclarationMode.TYPED_DEFINITION,
    definition_kind=ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE,
    definition_model=StartingEquipmentPackageDefinition,
)


def _ref(class_id: str, preset_id: str) -> ContentRef:
    return ContentRef(
        pack_id=_PACK_ID,
        definition_kind=ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE,
        content_id=f"starting_equipment.{class_id}.{preset_id}",
        content_version=_VERSION,
        definition_contract_hash=_CONTRACT_HASH,
    )


STARTING_EQUIPMENT_PACKAGE_REFS_BY_PRESET = MappingProxyType({
    ("barbarian", "dual_axes"): _ref("barbarian", "dual_axes"),
    ("barbarian", "greataxe"): _ref("barbarian", "greataxe"),
    ("barbarian", "sword_shield"): _ref("barbarian", "sword_shield"),
    ("fighter", "archery"): _ref("fighter", "archery"),
    ("fighter", "dual_wield"): _ref("fighter", "dual_wield"),
    ("fighter", "greatsword"): _ref("fighter", "greatsword"),
    ("fighter", "sword_shield"): _ref("fighter", "sword_shield"),
    ("sorcerer", "dagger"): _ref("sorcerer", "dagger"),
    ("sorcerer", "quarterstaff"): _ref("sorcerer", "quarterstaff"),
})
STARTING_EQUIPMENT_PACKAGE_REFS_BY_CLASS = MappingProxyType({
    class_id: tuple(sorted(
        (
            ref
            for (candidate_class_id, _preset_id), ref
            in STARTING_EQUIPMENT_PACKAGE_REFS_BY_PRESET.items()
            if candidate_class_id == class_id
        ),
        key=lambda ref: ref.identity_key,
    ))
    for class_id in ("barbarian", "fighter", "sorcerer")
})


__all__ = [
    "STARTING_EQUIPMENT_PACKAGE_REFS_BY_CLASS",
    "STARTING_EQUIPMENT_PACKAGE_REFS_BY_PRESET",
]
