"""Pure structural identities used by Sorcerer character composition.

These immutable definitions contain authored choice data only.  They never
construct an action, condition, handler, or Entity; runtime installation is a
separate exact-ContentRef grant-binding concern.
"""

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from dnd.content_system.action_definitions import (
    ACTION_BEHAVIOR_DECLARATIONS,
)
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
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
    behavior_identity,
    get_content_declaration,
)
from dnd.core.content.runtime import RuntimeBehaviorKind


_PACK_ID = "content.srd_5_1_cc"
_VERSION = 1
_ACTION_REFS_BY_CONTENT_ID = {
    declaration.ref.content_id: declaration.ref
    for declaration in ACTION_BEHAVIOR_DECLARATIONS
}


def _grants_action(content_id: str) -> tuple[ContentDependency, ...]:
    try:
        action_ref = _ACTION_REFS_BY_CONTENT_ID[content_id]
    except KeyError as error:
        raise RuntimeError(
            f"Sorcerer structural feature names unknown action {content_id}",
        ) from error
    return (
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=action_ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Installed while this selected Metamagic feature is owned.",
        ),
    )


class SorcererStructuralFeatureKind(str, Enum):
    """Closed structural feature roles consumed by Sorcerer composition."""

    METAMAGIC_OPTION = "metamagic_option"
    DRACONIC_ANCESTRY = "draconic_ancestry"
    ELEMENTAL_AFFINITY = "elemental_affinity"
    DRAGON_WINGS = "dragon_wings"
    DRACONIC_PRESENCE = "draconic_presence"
    SORCEROUS_RESTORATION = "sorcerous_restoration"


class SorcererMetamagicOption(str, Enum):
    """The eight metamagic options published by SRD 5.1."""

    CAREFUL_SPELL = "careful_spell"
    DISTANT_SPELL = "distant_spell"
    EMPOWERED_SPELL = "empowered_spell"
    EXTENDED_SPELL = "extended_spell"
    HEIGHTENED_SPELL = "heightened_spell"
    QUICKENED_SPELL = "quickened_spell"
    SUBTLE_SPELL = "subtle_spell"
    TWINNED_SPELL = "twinned_spell"


class DraconicAncestry(str, Enum):
    """The ten exact dragon ancestries published by SRD 5.1."""

    BLACK = "black"
    BLUE = "blue"
    BRASS = "brass"
    BRONZE = "bronze"
    COPPER = "copper"
    GOLD = "gold"
    GREEN = "green"
    RED = "red"
    SILVER = "silver"
    WHITE = "white"


DraconicDamageType = Literal[
    "acid",
    "cold",
    "fire",
    "lightning",
    "poison",
]


class SorcererStructuralFeatureDefinition(BaseModel):
    """Cold typed payload for one exact structural Sorcerer feature."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_kind: SorcererStructuralFeatureKind
    metamagic_option: SorcererMetamagicOption | None = None
    draconic_ancestry: DraconicAncestry | None = None
    ancestry_damage_type: DraconicDamageType | None = None
    short_rest_sorcery_point_recovery: int | None = None

    @model_validator(mode="after")
    def _validate_closed_payload(self) -> Self:
        if self.feature_kind is SorcererStructuralFeatureKind.METAMAGIC_OPTION:
            if self.metamagic_option is None:
                raise ValueError("metamagic feature requires metamagic_option")
            if (
                self.draconic_ancestry is not None
                or self.ancestry_damage_type is not None
                or self.short_rest_sorcery_point_recovery is not None
            ):
                raise ValueError("metamagic feature carries unrelated fields")
            return self
        if self.feature_kind is SorcererStructuralFeatureKind.DRACONIC_ANCESTRY:
            if (
                self.draconic_ancestry is None
                or self.ancestry_damage_type is None
            ):
                raise ValueError(
                    "draconic ancestry requires dragon and damage type",
                )
            if (
                self.metamagic_option is not None
                or self.short_rest_sorcery_point_recovery is not None
            ):
                raise ValueError(
                    "draconic ancestry carries unrelated fields",
                )
            return self
        if (
            self.feature_kind
            is SorcererStructuralFeatureKind.SORCEROUS_RESTORATION
        ):
            if self.short_rest_sorcery_point_recovery != 4:
                raise ValueError(
                    "Sorcerous Restoration recovers exactly four points",
                )
            if (
                self.metamagic_option is not None
                or self.draconic_ancestry is not None
                or self.ancestry_damage_type is not None
            ):
                raise ValueError(
                    "Sorcerous Restoration carries unrelated fields",
                )
            return self
        if any((
            self.metamagic_option is not None,
            self.draconic_ancestry is not None,
            self.ancestry_damage_type is not None,
            self.short_rest_sorcery_point_recovery is not None,
        )):
            raise ValueError("marker feature carries unrelated fields")
        return self


def _provenance(source_anchor: str) -> ContentProvenance:
    return ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=source_anchor,
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Immutable structural choice/feature definition. Runtime "
            "mechanics are installed separately through exact grant bindings."
        ),
    )


_STRUCTURAL_DEFINITION_BY_MARKER: dict[
    type[object],
    SorcererStructuralFeatureDefinition,
] = {}


def _structural_feature(
    *,
    content_id: str,
    display_name: str,
    description: str,
    definition: SorcererStructuralFeatureDefinition,
    icon_key: str,
    ui_group: str,
    sort_order: int,
    dependencies: tuple[ContentDependency, ...] = (),
):
    identity_decorator = behavior_identity(
        definition_kind=ContentDefinitionKind.CLASS_FEATURE,
        runtime_behavior_kind=RuntimeBehaviorKind.CLASS_FEATURE,
        pack_id=_PACK_ID,
        content_id=content_id,
        version=_VERSION,
        descriptor=ContentDescriptorSpec(
            display_name=display_name,
            description=description,
            tags=(
                "class_feature",
                "sorcerer",
                "structural_grant",
                definition.feature_kind.value,
            ),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                icon_key=icon_key,
                visual_variant_key=content_id,
                ui_group=ui_group,
            ),
            ordering=ContentOrdering(
                sort_group=ui_group,
                sort_order=sort_order,
            ),
        ),
        provenance=_provenance(
            f"SRD 5.1 Sorcerer: {display_name}",
        ),
        dependencies=dependencies,
    )

    def decorate(marker_type: type[object]) -> type[object]:
        decorated = identity_decorator(marker_type)
        _STRUCTURAL_DEFINITION_BY_MARKER[decorated] = definition
        return decorated

    return decorate


@_structural_feature(
    content_id="class_feature.sorcerer.metamagic.careful_spell",
    display_name="Careful Spell",
    description=(
        "Spend 1 sorcery point to let selected creatures automatically "
        "succeed on a saving throw forced by the spell."
    ),
    definition=SorcererStructuralFeatureDefinition(
        feature_kind=SorcererStructuralFeatureKind.METAMAGIC_OPTION,
        metamagic_option=SorcererMetamagicOption.CAREFUL_SPELL,
    ),
    icon_key="condition.dnd-classes-sorcerer-metamagicactive",
    ui_group="class_features.sorcerer.metamagic",
    sort_order=10,
)
class CarefulSpellStructuralFeature:
    """Typed identity for the Careful Spell choice."""


@_structural_feature(
    content_id="class_feature.sorcerer.metamagic.distant_spell",
    display_name="Distant Spell",
    description=(
        "Spend 1 sorcery point to double a spell's range, or make a touch "
        "spell reach 30 feet."
    ),
    definition=SorcererStructuralFeatureDefinition(
        feature_kind=SorcererStructuralFeatureKind.METAMAGIC_OPTION,
        metamagic_option=SorcererMetamagicOption.DISTANT_SPELL,
    ),
    icon_key="condition.dnd-classes-sorcerer-sorcerypointsfeature",
    ui_group="class_features.sorcerer.metamagic",
    sort_order=20,
    dependencies=_grants_action(
        "action.class.sorcerer.distant_spell",
    ),
)
class DistantSpellStructuralFeature:
    """Typed identity for the Distant Spell choice."""


@_structural_feature(
    content_id="class_feature.sorcerer.metamagic.empowered_spell",
    display_name="Empowered Spell",
    description=(
        "Spend 1 sorcery point to reroll spell damage dice up to the "
        "Charisma modifier and use the new rolls."
    ),
    definition=SorcererStructuralFeatureDefinition(
        feature_kind=SorcererStructuralFeatureKind.METAMAGIC_OPTION,
        metamagic_option=SorcererMetamagicOption.EMPOWERED_SPELL,
    ),
    icon_key="condition.dnd-classes-sorcerer-metamagicactive",
    ui_group="class_features.sorcerer.metamagic",
    sort_order=30,
)
class EmpoweredSpellStructuralFeature:
    """Typed identity for the Empowered Spell choice."""


@_structural_feature(
    content_id="class_feature.sorcerer.metamagic.extended_spell",
    display_name="Extended Spell",
    description=(
        "Spend 1 sorcery point to double a spell duration of at least 1 "
        "minute, up to 24 hours."
    ),
    definition=SorcererStructuralFeatureDefinition(
        feature_kind=SorcererStructuralFeatureKind.METAMAGIC_OPTION,
        metamagic_option=SorcererMetamagicOption.EXTENDED_SPELL,
    ),
    icon_key="condition.dnd-classes-sorcerer-metamagicactive",
    ui_group="class_features.sorcerer.metamagic",
    sort_order=40,
)
class ExtendedSpellStructuralFeature:
    """Typed identity for the Extended Spell choice."""


@_structural_feature(
    content_id="class_feature.sorcerer.metamagic.heightened_spell",
    display_name="Heightened Spell",
    description=(
        "Spend 3 sorcery points to give one target disadvantage on its first "
        "saving throw against the spell."
    ),
    definition=SorcererStructuralFeatureDefinition(
        feature_kind=SorcererStructuralFeatureKind.METAMAGIC_OPTION,
        metamagic_option=SorcererMetamagicOption.HEIGHTENED_SPELL,
    ),
    icon_key="condition.dnd-classes-sorcerer-metamagicactive",
    ui_group="class_features.sorcerer.metamagic",
    sort_order=50,
)
class HeightenedSpellStructuralFeature:
    """Typed identity for the Heightened Spell choice."""


@_structural_feature(
    content_id="class_feature.sorcerer.metamagic.quickened_spell",
    display_name="Quickened Spell",
    description=(
        "Spend 2 sorcery points to cast a one-action spell as a bonus action."
    ),
    definition=SorcererStructuralFeatureDefinition(
        feature_kind=SorcererStructuralFeatureKind.METAMAGIC_OPTION,
        metamagic_option=SorcererMetamagicOption.QUICKENED_SPELL,
    ),
    icon_key="action.quickened-spell",
    ui_group="class_features.sorcerer.metamagic",
    sort_order=60,
    dependencies=_grants_action(
        "action.class.sorcerer.quickened_spell",
    ),
)
class QuickenedSpellStructuralFeature:
    """Typed identity for the Quickened Spell choice."""


@_structural_feature(
    content_id="class_feature.sorcerer.metamagic.subtle_spell",
    display_name="Subtle Spell",
    description=(
        "Spend 1 sorcery point to cast without somatic or verbal components."
    ),
    definition=SorcererStructuralFeatureDefinition(
        feature_kind=SorcererStructuralFeatureKind.METAMAGIC_OPTION,
        metamagic_option=SorcererMetamagicOption.SUBTLE_SPELL,
    ),
    icon_key="condition.dnd-classes-sorcerer-metamagicactive",
    ui_group="class_features.sorcerer.metamagic",
    sort_order=70,
)
class SubtleSpellStructuralFeature:
    """Typed identity for the Subtle Spell choice."""


@_structural_feature(
    content_id="class_feature.sorcerer.metamagic.twinned_spell",
    display_name="Twinned Spell",
    description=(
        "Spend sorcery points to add a second target to an eligible "
        "single-target spell."
    ),
    definition=SorcererStructuralFeatureDefinition(
        feature_kind=SorcererStructuralFeatureKind.METAMAGIC_OPTION,
        metamagic_option=SorcererMetamagicOption.TWINNED_SPELL,
    ),
    icon_key="action.twinned-spell",
    ui_group="class_features.sorcerer.metamagic",
    sort_order=80,
    dependencies=_grants_action(
        "action.class.sorcerer.twinned_spell",
    ),
)
class TwinnedSpellStructuralFeature:
    """Typed identity for the Twinned Spell choice."""


def _ancestry_definition(
    ancestry: DraconicAncestry,
    damage_type: DraconicDamageType,
) -> SorcererStructuralFeatureDefinition:
    return SorcererStructuralFeatureDefinition(
        feature_kind=SorcererStructuralFeatureKind.DRACONIC_ANCESTRY,
        draconic_ancestry=ancestry,
        ancestry_damage_type=damage_type,
    )


@_structural_feature(
    content_id="class_feature.sorcerer.draconic_ancestry.black",
    display_name="Black Dragon Ancestry",
    description="Black dragon ancestry associates later features with acid.",
    definition=_ancestry_definition(DraconicAncestry.BLACK, "acid"),
    icon_key="spell.acid-splash",
    ui_group="class_features.sorcerer.draconic_ancestry",
    sort_order=10,
)
class BlackDragonAncestryStructuralFeature:
    """Typed identity for Black Dragon ancestry."""


@_structural_feature(
    content_id="class_feature.sorcerer.draconic_ancestry.blue",
    display_name="Blue Dragon Ancestry",
    description=(
        "Blue dragon ancestry associates later features with lightning."
    ),
    definition=_ancestry_definition(DraconicAncestry.BLUE, "lightning"),
    icon_key="spell.lightning-bolt",
    ui_group="class_features.sorcerer.draconic_ancestry",
    sort_order=20,
)
class BlueDragonAncestryStructuralFeature:
    """Typed identity for Blue Dragon ancestry."""


@_structural_feature(
    content_id="class_feature.sorcerer.draconic_ancestry.brass",
    display_name="Brass Dragon Ancestry",
    description="Brass dragon ancestry associates later features with fire.",
    definition=_ancestry_definition(DraconicAncestry.BRASS, "fire"),
    icon_key="spell.fire-bolt",
    ui_group="class_features.sorcerer.draconic_ancestry",
    sort_order=30,
)
class BrassDragonAncestryStructuralFeature:
    """Typed identity for Brass Dragon ancestry."""


@_structural_feature(
    content_id="class_feature.sorcerer.draconic_ancestry.bronze",
    display_name="Bronze Dragon Ancestry",
    description=(
        "Bronze dragon ancestry associates later features with lightning."
    ),
    definition=_ancestry_definition(DraconicAncestry.BRONZE, "lightning"),
    icon_key="spell.lightning-bolt",
    ui_group="class_features.sorcerer.draconic_ancestry",
    sort_order=40,
)
class BronzeDragonAncestryStructuralFeature:
    """Typed identity for Bronze Dragon ancestry."""


@_structural_feature(
    content_id="class_feature.sorcerer.draconic_ancestry.copper",
    display_name="Copper Dragon Ancestry",
    description="Copper dragon ancestry associates later features with acid.",
    definition=_ancestry_definition(DraconicAncestry.COPPER, "acid"),
    icon_key="spell.acid-splash",
    ui_group="class_features.sorcerer.draconic_ancestry",
    sort_order=50,
)
class CopperDragonAncestryStructuralFeature:
    """Typed identity for Copper Dragon ancestry."""


@_structural_feature(
    content_id="class_feature.sorcerer.draconic_ancestry.gold",
    display_name="Gold Dragon Ancestry",
    description="Gold dragon ancestry associates later features with fire.",
    definition=_ancestry_definition(DraconicAncestry.GOLD, "fire"),
    icon_key="spell.fire-bolt",
    ui_group="class_features.sorcerer.draconic_ancestry",
    sort_order=60,
)
class GoldDragonAncestryStructuralFeature:
    """Typed identity for Gold Dragon ancestry."""


@_structural_feature(
    content_id="class_feature.sorcerer.draconic_ancestry.green",
    display_name="Green Dragon Ancestry",
    description=(
        "Green dragon ancestry associates later features with poison."
    ),
    definition=_ancestry_definition(DraconicAncestry.GREEN, "poison"),
    icon_key="spell.poison-spray",
    ui_group="class_features.sorcerer.draconic_ancestry",
    sort_order=70,
)
class GreenDragonAncestryStructuralFeature:
    """Typed identity for Green Dragon ancestry."""


@_structural_feature(
    content_id="class_feature.sorcerer.draconic_ancestry.red",
    display_name="Red Dragon Ancestry",
    description="Red dragon ancestry associates later features with fire.",
    definition=_ancestry_definition(DraconicAncestry.RED, "fire"),
    icon_key="spell.fire-bolt",
    ui_group="class_features.sorcerer.draconic_ancestry",
    sort_order=80,
)
class RedDragonAncestryStructuralFeature:
    """Typed identity for Red Dragon ancestry."""


@_structural_feature(
    content_id="class_feature.sorcerer.draconic_ancestry.silver",
    display_name="Silver Dragon Ancestry",
    description="Silver dragon ancestry associates later features with cold.",
    definition=_ancestry_definition(DraconicAncestry.SILVER, "cold"),
    icon_key="spell.ray-of-frost",
    ui_group="class_features.sorcerer.draconic_ancestry",
    sort_order=90,
)
class SilverDragonAncestryStructuralFeature:
    """Typed identity for Silver Dragon ancestry."""


@_structural_feature(
    content_id="class_feature.sorcerer.draconic_ancestry.white",
    display_name="White Dragon Ancestry",
    description="White dragon ancestry associates later features with cold.",
    definition=_ancestry_definition(DraconicAncestry.WHITE, "cold"),
    icon_key="spell.ray-of-frost",
    ui_group="class_features.sorcerer.draconic_ancestry",
    sort_order=100,
)
class WhiteDragonAncestryStructuralFeature:
    """Typed identity for White Dragon ancestry."""


@_structural_feature(
    content_id="class_feature.sorcerer.elemental_affinity",
    display_name="Elemental Affinity",
    description=(
        "Add Charisma to one matching ancestry spell damage roll per cast, "
        "and spend 1 sorcery point for 1 hour of matching resistance."
    ),
    definition=SorcererStructuralFeatureDefinition(
        feature_kind=SorcererStructuralFeatureKind.ELEMENTAL_AFFINITY,
    ),
    icon_key="condition.dnd-classes-sorcerer-elementalaffinity",
    ui_group="class_features.sorcerer.draconic_bloodline",
    sort_order=60,
    dependencies=(
        *_grants_action(
            "action.class.sorcerer.elemental_affinity.resistance",
        ),
    ),
)
class ElementalAffinityStructuralFeature:
    """Typed identity for the level-six Draconic Bloodline feature."""


@_structural_feature(
    content_id="class_feature.sorcerer.dragon_wings",
    display_name="Dragon Wings",
    description=(
        "Manifest or dismiss dragon wings as a bonus action, gaining a flying "
        "speed equal to current speed while the wings remain."
    ),
    definition=SorcererStructuralFeatureDefinition(
        feature_kind=SorcererStructuralFeatureKind.DRAGON_WINGS,
    ),
    icon_key="spell.haste",
    ui_group="class_features.sorcerer.draconic_bloodline",
    sort_order=140,
    dependencies=(
        *_grants_action(
            "action.class.sorcerer.dragon_wings.toggle",
        ),
    ),
)
class DragonWingsStructuralFeature:
    """Typed identity for Dragon Wings."""


@_structural_feature(
    content_id="class_feature.sorcerer.draconic_presence",
    display_name="Draconic Presence",
    description=(
        "Spend 5 sorcery points to concentrate on a 60-foot aura of awe or "
        "fear for up to 1 minute."
    ),
    definition=SorcererStructuralFeatureDefinition(
        feature_kind=SorcererStructuralFeatureKind.DRACONIC_PRESENCE,
    ),
    icon_key="spell.fear",
    ui_group="class_features.sorcerer.draconic_bloodline",
    sort_order=180,
    dependencies=(
        *_grants_action(
            "action.class.sorcerer.draconic_presence",
        ),
    ),
)
class DraconicPresenceStructuralFeature:
    """Typed identity for Draconic Presence."""


@_structural_feature(
    content_id="class_feature.sorcerer.sorcerous_restoration",
    display_name="Sorcerous Restoration",
    description=(
        "Regain 4 expended sorcery points whenever a short rest finishes."
    ),
    definition=SorcererStructuralFeatureDefinition(
        feature_kind=SorcererStructuralFeatureKind.SORCEROUS_RESTORATION,
        short_rest_sorcery_point_recovery=4,
    ),
    icon_key="condition.dnd-classes-sorcerer-sorcerypointsfeature",
    ui_group="class_features.sorcerer",
    sort_order=200,
)
class SorcerousRestorationStructuralFeature:
    """Typed identity for Sorcerous Restoration."""


def _declaration(marker_type: type[object]) -> ContentDeclaration:
    return get_content_declaration(marker_type)


CAREFUL_SPELL_DECLARATION = _declaration(CarefulSpellStructuralFeature)
DISTANT_SPELL_DECLARATION = _declaration(DistantSpellStructuralFeature)
EMPOWERED_SPELL_DECLARATION = _declaration(EmpoweredSpellStructuralFeature)
EXTENDED_SPELL_DECLARATION = _declaration(ExtendedSpellStructuralFeature)
HEIGHTENED_SPELL_DECLARATION = _declaration(HeightenedSpellStructuralFeature)
QUICKENED_SPELL_DECLARATION = _declaration(QuickenedSpellStructuralFeature)
SUBTLE_SPELL_DECLARATION = _declaration(SubtleSpellStructuralFeature)
TWINNED_SPELL_DECLARATION = _declaration(TwinnedSpellStructuralFeature)

BLACK_DRAGON_ANCESTRY_DECLARATION = _declaration(
    BlackDragonAncestryStructuralFeature,
)
BLUE_DRAGON_ANCESTRY_DECLARATION = _declaration(
    BlueDragonAncestryStructuralFeature,
)
BRASS_DRAGON_ANCESTRY_DECLARATION = _declaration(
    BrassDragonAncestryStructuralFeature,
)
BRONZE_DRAGON_ANCESTRY_DECLARATION = _declaration(
    BronzeDragonAncestryStructuralFeature,
)
COPPER_DRAGON_ANCESTRY_DECLARATION = _declaration(
    CopperDragonAncestryStructuralFeature,
)
GOLD_DRAGON_ANCESTRY_DECLARATION = _declaration(
    GoldDragonAncestryStructuralFeature,
)
GREEN_DRAGON_ANCESTRY_DECLARATION = _declaration(
    GreenDragonAncestryStructuralFeature,
)
RED_DRAGON_ANCESTRY_DECLARATION = _declaration(
    RedDragonAncestryStructuralFeature,
)
SILVER_DRAGON_ANCESTRY_DECLARATION = _declaration(
    SilverDragonAncestryStructuralFeature,
)
WHITE_DRAGON_ANCESTRY_DECLARATION = _declaration(
    WhiteDragonAncestryStructuralFeature,
)

ELEMENTAL_AFFINITY_DECLARATION = _declaration(
    ElementalAffinityStructuralFeature,
)
DRAGON_WINGS_DECLARATION = _declaration(DragonWingsStructuralFeature)
DRACONIC_PRESENCE_DECLARATION = _declaration(
    DraconicPresenceStructuralFeature,
)
SORCEROUS_RESTORATION_DECLARATION = _declaration(
    SorcerousRestorationStructuralFeature,
)

METAMAGIC_OPTION_DECLARATIONS: tuple[ContentDeclaration, ...] = tuple(
    sorted(
        (
            CAREFUL_SPELL_DECLARATION,
            DISTANT_SPELL_DECLARATION,
            EMPOWERED_SPELL_DECLARATION,
            EXTENDED_SPELL_DECLARATION,
            HEIGHTENED_SPELL_DECLARATION,
            QUICKENED_SPELL_DECLARATION,
            SUBTLE_SPELL_DECLARATION,
            TWINNED_SPELL_DECLARATION,
        ),
        key=lambda declaration: declaration.ref.identity_key,
    )
)
DRACONIC_ANCESTRY_DECLARATIONS: tuple[ContentDeclaration, ...] = tuple(
    sorted(
        (
            BLACK_DRAGON_ANCESTRY_DECLARATION,
            BLUE_DRAGON_ANCESTRY_DECLARATION,
            BRASS_DRAGON_ANCESTRY_DECLARATION,
            BRONZE_DRAGON_ANCESTRY_DECLARATION,
            COPPER_DRAGON_ANCESTRY_DECLARATION,
            GOLD_DRAGON_ANCESTRY_DECLARATION,
            GREEN_DRAGON_ANCESTRY_DECLARATION,
            RED_DRAGON_ANCESTRY_DECLARATION,
            SILVER_DRAGON_ANCESTRY_DECLARATION,
            WHITE_DRAGON_ANCESTRY_DECLARATION,
        ),
        key=lambda declaration: declaration.ref.identity_key,
    )
)
SORCERER_STRUCTURAL_FEATURE_DECLARATIONS: tuple[
    ContentDeclaration,
    ...,
] = tuple(
    sorted(
        (
            *METAMAGIC_OPTION_DECLARATIONS,
            *DRACONIC_ANCESTRY_DECLARATIONS,
            ELEMENTAL_AFFINITY_DECLARATION,
            DRAGON_WINGS_DECLARATION,
            DRACONIC_PRESENCE_DECLARATION,
            SORCEROUS_RESTORATION_DECLARATION,
        ),
        key=lambda declaration: declaration.ref.identity_key,
    )
)

SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF: Mapping[
    ContentRef,
    SorcererStructuralFeatureDefinition,
] = MappingProxyType({
    get_content_declaration(marker_type).ref: definition
    for marker_type, definition in _STRUCTURAL_DEFINITION_BY_MARKER.items()
})


__all__ = [
    "CAREFUL_SPELL_DECLARATION",
    "DISTANT_SPELL_DECLARATION",
    "DRACONIC_ANCESTRY_DECLARATIONS",
    "DRACONIC_PRESENCE_DECLARATION",
    "DRAGON_WINGS_DECLARATION",
    "DraconicAncestry",
    "DraconicDamageType",
    "ELEMENTAL_AFFINITY_DECLARATION",
    "EMPOWERED_SPELL_DECLARATION",
    "EXTENDED_SPELL_DECLARATION",
    "HEIGHTENED_SPELL_DECLARATION",
    "METAMAGIC_OPTION_DECLARATIONS",
    "QUICKENED_SPELL_DECLARATION",
    "SORCERER_STRUCTURAL_FEATURE_DECLARATIONS",
    "SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF",
    "SORCEROUS_RESTORATION_DECLARATION",
    "SUBTLE_SPELL_DECLARATION",
    "SorcererMetamagicOption",
    "SorcererStructuralFeatureDefinition",
    "SorcererStructuralFeatureKind",
    "TWINNED_SPELL_DECLARATION",
]
