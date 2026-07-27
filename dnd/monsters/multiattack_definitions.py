"""Typed authored configurations for SRD monster Multiattack actions."""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field

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
from dnd.core.equipment_types import WeaponSlot


_PACK_ID = "content.srd_5_1_cc"
_SOURCE_ID = "wotc.srd_5_1_cc"


class MultiattackTargetPolicy(str, Enum):
    """How one configured Multiattack selects targets."""

    SINGLE_TARGET_SEQUENCE = "single_target_sequence"


class MultiattackStepDefinition(BaseModel):
    """One ordered weapon-slot repetition in a stat-block Multiattack."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    weapon_slot: WeaponSlot
    count: int = Field(ge=1)


class MultiattackConfigurationDefinition(BaseModel):
    """Exact data specializing the reusable Multiattack engine behavior."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_policy: MultiattackTargetPolicy
    steps: tuple[MultiattackStepDefinition, ...] = Field(min_length=1)


_CONTRACT_HASH = compute_definition_contract_hash(
    mode=ContentDeclarationMode.TYPED_DEFINITION,
    definition_kind=ContentDefinitionKind.ACTION,
    definition_model=MultiattackConfigurationDefinition,
)


def _declaration(
    *,
    content_id: str,
    display_name: str,
    icon_key: str,
    source_anchor: str,
    steps: tuple[tuple[WeaponSlot, int], ...],
    sort_order: int,
) -> ContentDeclaration:
    ref = ContentRef(
        pack_id=_PACK_ID,
        definition_kind=ContentDefinitionKind.ACTION,
        content_id=content_id,
        content_version=1,
        definition_contract_hash=_CONTRACT_HASH,
    )
    return ContentDeclaration(
        ref=ref,
        mode=ContentDeclarationMode.TYPED_DEFINITION,
        descriptor=ContentDescriptor.from_spec(
            ref,
            ContentDescriptorSpec(
                display_name=display_name,
                description=(
                    "Exact ordered attack sequence authored by this SRD "
                    "creature stat block."
                ),
                tags=(
                    "action",
                    "configured_action",
                    "multiattack",
                    "srd_5_1",
                ),
                visibility=ContentVisibility.PUBLIC,
                presentation=ContentPresentation(
                    icon_key=icon_key,
                    visual_variant_key=content_id,
                    vfx_profile="action.monster.multiattack",
                    ui_group="actions.action",
                ),
                ordering=ContentOrdering(
                    sort_group="actions.action",
                    sort_order=sort_order,
                ),
            ),
        ),
        provenance=ContentProvenance(
            primary_source_id=_SOURCE_ID,
            source_anchor=source_anchor,
            relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.REVIEWED,
            notes=(
                "Typed stat-block configuration for the shared Multiattack "
                "runtime behavior; display names are never used as identity. "
                "The current engine deliberately resolves the full sequence "
                "against one selected target even though the general SRD "
                "attack rules permit choosing a target for each constituent "
                "attack unless a stat block says otherwise."
            ),
        ),
        definition_payload=MultiattackConfigurationDefinition(
            target_policy=MultiattackTargetPolicy.SINGLE_TARGET_SEQUENCE,
            steps=tuple(
                MultiattackStepDefinition(
                    weapon_slot=weapon_slot,
                    count=count,
                )
                for weapon_slot, count in steps
            ),
        ),
    )


SRD_MULTIATTACK_CONFIGURATION_DECLARATIONS: tuple[
    ContentDeclaration,
    ...,
] = (
    _declaration(
        content_id="action.monster.multiattack.scout.shortsword",
        display_name="Scout Multiattack: Shortsword",
        icon_key="action.scout-multiattack-shortsword",
        source_anchor="SRD 5.1 (CC-BY-4.0), p. 401, Scout Multiattack",
        steps=((WeaponSlot.MELEE_MAIN, 2),),
        sort_order=1,
    ),
    _declaration(
        content_id="action.monster.multiattack.scout.longbow",
        display_name="Scout Multiattack: Longbow",
        icon_key="action.scout-multiattack-longbow",
        source_anchor="SRD 5.1 (CC-BY-4.0), p. 401, Scout Multiattack",
        steps=((WeaponSlot.RANGED_MAIN, 2),),
        sort_order=2,
    ),
    _declaration(
        content_id="action.monster.multiattack.thug",
        display_name="Thug Multiattack",
        icon_key="action.thug-multiattack",
        source_anchor="SRD 5.1 (CC-BY-4.0), p. 402, Thug Multiattack",
        steps=((WeaponSlot.MELEE_MAIN, 2),),
        sort_order=3,
    ),
    _declaration(
        content_id="action.monster.multiattack.spy",
        display_name="Spy Multiattack",
        icon_key="action.spy-multiattack",
        source_anchor="SRD 5.1 (CC-BY-4.0), p. 402, Spy Multiattack",
        steps=((WeaponSlot.MELEE_MAIN, 2),),
        sort_order=4,
    ),
    _declaration(
        content_id="action.monster.multiattack.bandit_captain.melee",
        display_name="Bandit Captain Multiattack: Melee",
        icon_key="action.bandit-captain-multiattack-melee",
        source_anchor=(
            "SRD 5.1 (CC-BY-4.0), p. 397, Bandit Captain Multiattack"
        ),
        steps=(
            (WeaponSlot.MELEE_MAIN, 2),
            (WeaponSlot.MELEE_OFF, 1),
        ),
        sort_order=5,
    ),
    _declaration(
        content_id="action.monster.multiattack.bandit_captain.ranged",
        display_name="Bandit Captain Multiattack: Ranged",
        icon_key="action.bandit-captain-multiattack-ranged",
        source_anchor=(
            "SRD 5.1 (CC-BY-4.0), p. 397, Bandit Captain Multiattack"
        ),
        steps=((WeaponSlot.RANGED_MAIN, 2),),
        sort_order=6,
    ),
    _declaration(
        content_id="action.monster.multiattack.cult_fanatic",
        display_name="Cult Fanatic Multiattack",
        icon_key="action.cult-fanatic-multiattack",
        source_anchor=(
            "SRD 5.1 (CC-BY-4.0), p. 398, Cult Fanatic Multiattack"
        ),
        steps=((WeaponSlot.MELEE_MAIN, 2),),
        sort_order=7,
    ),
    _declaration(
        content_id="action.monster.multiattack.knight",
        display_name="Knight Multiattack",
        icon_key="action.knight-multiattack",
        source_anchor="SRD 5.1 (CC-BY-4.0), p. 400, Knight Multiattack",
        steps=((WeaponSlot.MELEE_MAIN, 2),),
        sort_order=8,
    ),
    _declaration(
        content_id="action.monster.multiattack.veteran.melee",
        display_name="Veteran Multiattack: Melee",
        icon_key="action.veteran-multiattack-melee",
        source_anchor="SRD 5.1 (CC-BY-4.0), p. 403, Veteran Multiattack",
        steps=(
            (WeaponSlot.MELEE_MAIN, 2),
            (WeaponSlot.MELEE_OFF, 1),
        ),
        sort_order=9,
    ),
    _declaration(
        content_id="action.monster.multiattack.veteran.ranged",
        display_name="Veteran Multiattack: Ranged",
        icon_key="action.veteran-multiattack-ranged",
        source_anchor="SRD 5.1 (CC-BY-4.0), p. 403, Veteran Multiattack",
        steps=((WeaponSlot.RANGED_MAIN, 2),),
        sort_order=10,
    ),
)
SRD_MULTIATTACK_CONFIGURATIONS_BY_CONTENT_ID = MappingProxyType({
    declaration.ref.content_id: declaration
    for declaration in SRD_MULTIATTACK_CONFIGURATION_DECLARATIONS
})


__all__ = [
    "MultiattackConfigurationDefinition",
    "MultiattackStepDefinition",
    "MultiattackTargetPolicy",
    "SRD_MULTIATTACK_CONFIGURATION_DECLARATIONS",
    "SRD_MULTIATTACK_CONFIGURATIONS_BY_CONTENT_ID",
]
