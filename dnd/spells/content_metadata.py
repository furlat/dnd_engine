"""Cold authored spell metadata shared by declarations and catalog projections."""

from collections.abc import Callable
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.core.content.dependencies import ContentDependency
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import behavior_identity
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.types.abilities import AbilityName
from dnd.core.creature_types import DamageType


_DefinitionT = TypeVar("_DefinitionT")
_SPELL_CATALOG_METADATA_ATTRIBUTE = "__dnd_spell_catalog_metadata__"

SpellCatalogTargetType = Literal[
    "self",
    "entity",
    "multi_entity",
    "position",
    "position_aoe",
]
SpellCatalogRangeType = Literal["self", "touch", "ranged"]
SpellCatalogProjectileType = Literal[
    "bolt",
    "ray",
    "orb",
    "beam",
    "dart",
    "spray",
    "radiance",
    "touch",
    "rain",
]
SpellCatalogAoeShapeType = Literal[
    "sphere",
    "cone",
    "line",
    "cube",
    "cylinder",
]
SpellCatalogDelivery = Literal[
    "self",
    "touch",
    "single_projectile",
    "missile_volley",
    "aoe",
    "aoe_projectile",
    "beam",
    "ray",
    "none",
]


class SpellCatalogSavingThrowSpec(BaseModel):
    """One distinct saving throw used by a spell, in effect order."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ability: AbilityName
    dc_source: Literal["caster_spell_save_dc"]


class SpellCatalogMultiTargetSpec(BaseModel):
    """Exact base-cast target allocation for a multi-entity spell."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_targets: int = Field(ge=1)
    max_targets: int = Field(ge=1)
    allow_same_target: bool
    projectiles_per_cast: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validate_target_bounds(self) -> "SpellCatalogMultiTargetSpec":
        if self.max_targets < self.min_targets:
            raise ValueError("maximum targets cannot be below minimum targets")
        return self


class SpellCatalogAoeSpec(BaseModel):
    """One primary authored spell area using the current wire dimensions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    shape: SpellCatalogAoeShapeType
    radius_ft: int | None = Field(default=None, gt=0)
    length_ft: int | None = Field(default=None, gt=0)
    width_ft: int | None = Field(default=None, gt=0)
    height_ft: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _validate_dimensions(self) -> "SpellCatalogAoeSpec":
        dimensions = (
            self.radius_ft,
            self.length_ft,
            self.width_ft,
            self.height_ft,
        )
        if self.shape == "sphere":
            expected = (self.radius_ft, None, None, None)
        elif self.shape == "cone":
            expected = (None, self.length_ft, None, None)
        elif self.shape == "line":
            expected = (None, self.length_ft, self.width_ft, None)
        elif self.shape == "cube":
            expected = (None, self.length_ft, self.width_ft, self.height_ft)
        else:
            expected = (self.radius_ft, None, None, self.height_ft)
        if dimensions != expected or all(value is None for value in dimensions):
            raise ValueError(
                f"{self.shape} area has incompatible or missing dimensions",
            )
        if self.shape == "line" and (
            self.length_ft is None or self.width_ft is None
        ):
            raise ValueError("line area requires length and width")
        if self.shape == "cube" and (
            self.length_ft is None
            or self.width_ft is None
            or self.height_ft is None
        ):
            raise ValueError("cube area requires length, width, and height")
        if self.shape == "cylinder" and (
            self.radius_ft is None or self.height_ft is None
        ):
            raise ValueError("cylinder area requires radius and height")
        return self


class SpellCatalogMetadata(BaseModel):
    """Reviewed catalog facts for one public spell root.

    Every field is authored.  No field is recovered from a display name,
    Python source, class path, or runtime instance.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_id: str = Field(pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
    description: str = Field(min_length=1)
    target_type: SpellCatalogTargetType
    range_type: SpellCatalogRangeType
    range_ft: int = Field(ge=0)
    delivery: SpellCatalogDelivery
    projectile_type: SpellCatalogProjectileType | None
    aoe: SpellCatalogAoeSpec | None
    damage_types: tuple[DamageType, ...]
    healing: bool
    attack_roll: bool
    saving_throws: tuple[SpellCatalogSavingThrowSpec, ...]
    concentration: bool
    ritual: bool
    verbal: bool
    somatic: bool | None
    material: bool | None
    classes: tuple[str, ...]
    subclasses: tuple[str, ...]
    multi_target: SpellCatalogMultiTargetSpec | None
    recommended_asset_tags: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_semantics(self) -> "SpellCatalogMetadata":
        if len(self.damage_types) != len(set(self.damage_types)):
            raise ValueError("spell catalog damage types must be unique")
        save_abilities = tuple(row.ability for row in self.saving_throws)
        if len(save_abilities) != len(set(save_abilities)):
            raise ValueError("spell catalog saving throws must be distinct")
        if len(self.recommended_asset_tags) != len(
            set(self.recommended_asset_tags)
        ):
            raise ValueError("spell catalog asset tags must be unique")
        if self.target_type == "multi_entity" and self.multi_target is None:
            raise ValueError("multi-entity spell requires multi-target metadata")
        if self.target_type != "multi_entity" and self.multi_target is not None:
            raise ValueError(
                "non-multi-entity spell cannot carry multi-target metadata",
            )
        if self.delivery in {
            "single_projectile",
            "missile_volley",
            "aoe_projectile",
            "beam",
            "ray",
        } and self.projectile_type is None:
            raise ValueError("projectile delivery requires a projectile type")
        if self.delivery in {"aoe", "aoe_projectile"} and self.aoe is None:
            raise ValueError("area delivery requires authored area metadata")
        return self


def attach_spell_catalog_metadata(
    definition: _DefinitionT,
    metadata: SpellCatalogMetadata,
) -> _DefinitionT:
    """Attach one exact catalog record directly to its spell class."""
    namespace = getattr(definition, "__dict__", None)
    existing = (
        namespace.get(_SPELL_CATALOG_METADATA_ATTRIBUTE)
        if namespace is not None
        else None
    )
    if existing is not None and existing != metadata:
        raise ValueError(f"{definition!r} already has different spell metadata")
    setattr(definition, _SPELL_CATALOG_METADATA_ATTRIBUTE, metadata)
    return definition


def get_spell_catalog_metadata(definition: object) -> SpellCatalogMetadata:
    """Return only metadata authored directly for ``definition``."""
    namespace = getattr(definition, "__dict__", None)
    metadata = (
        namespace.get(_SPELL_CATALOG_METADATA_ATTRIBUTE)
        if namespace is not None
        else None
    )
    if not isinstance(metadata, SpellCatalogMetadata):
        raise ValueError(f"{definition!r} has no authored spell catalog metadata")
    return metadata


def srd_spell_identity(
    *,
    content_id: str,
    display_name: str,
    description: str,
    school: str,
    level: int,
    source_page: int,
    sort_order: int,
    icon_key: str | None = None,
    dependencies: tuple[ContentDependency, ...] = (),
) -> Callable[[_DefinitionT], _DefinitionT]:
    """Declare one existing SRD spell class as metadata-only content.

    This helper deliberately creates no spell factory. It only gives the
    already-authored runtime class an exact, code-free identity that item and
    creature definitions may reference in their dependency closure.
    """
    level_tag = "cantrip" if level == 0 else f"level_{level}"
    return behavior_identity(
        definition_kind=ContentDefinitionKind.SPELL,
        runtime_behavior_kind=RuntimeBehaviorKind.SPELL,
        pack_id="content.srd_5_1_cc",
        content_id=content_id,
        version=1,
        descriptor=ContentDescriptorSpec(
            display_name=display_name,
            description=description,
            tags=(level_tag, school, "spell", "srd"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                icon_key=icon_key or content_id,
                visual_variant_key=content_id.removeprefix("spell."),
                vfx_profile=content_id,
                ui_group=f"spells.{school}",
            ),
            ordering=ContentOrdering(
                sort_group=f"spells.level_{level}.{school}",
                sort_order=sort_order,
            ),
        ),
        provenance=ContentProvenance(
            primary_source_id="wotc.srd_5_1_cc",
            source_anchor=(
                f"SRD 5.1 (CC-BY-4.0), p. {source_page}, "
                f"Spell Descriptions: {display_name}"
            ),
            relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.REVIEWED,
            notes=(
                "Existing playable spell behavior; metadata identity does not "
                "claim that every rules edge case is complete."
            ),
        ),
        dependencies=dependencies,
    )


def srd_action_identity(
    *,
    content_id: str,
    display_name: str,
    description: str,
    parent_spell_name: str,
    source_page: int,
    sort_order: int,
    dependencies: tuple[ContentDependency, ...] = (),
) -> Callable[[_DefinitionT], _DefinitionT]:
    """Declare an SRD spell-granted action as exact authored content.

    Maintained spells may expose actions after the initial cast.  Those
    actions are independently attributable runtime behaviors, while their
    dependency edges retain the spell that granted them.
    """
    return behavior_identity(
        definition_kind=ContentDefinitionKind.ACTION,
        runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
        pack_id="content.srd_5_1_cc",
        content_id=content_id,
        version=1,
        descriptor=ContentDescriptorSpec(
            display_name=display_name,
            description=description,
            tags=("action", "spell", "srd"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                icon_key=content_id,
                visual_variant_key=content_id.removeprefix("action."),
                vfx_profile=content_id,
                ui_group="actions.action",
            ),
            ordering=ContentOrdering(
                sort_group="actions.action",
                sort_order=sort_order,
            ),
        ),
        provenance=ContentProvenance(
            primary_source_id="wotc.srd_5_1_cc",
            source_anchor=(
                f"SRD 5.1 (CC-BY-4.0), p. {source_page}, "
                f"Spell Descriptions: {parent_spell_name}"
            ),
            relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.REVIEWED,
            notes=(
                "Existing maintained-spell action preserved as an exact "
                "authored runtime behavior."
            ),
        ),
        dependencies=dependencies,
    )


def srd_reaction_identity(
    *,
    content_id: str,
    display_name: str,
    description: str,
    source_page: int,
    sort_order: int,
    icon_key: str | None = None,
) -> Callable[[_DefinitionT], _DefinitionT]:
    """Declare one SRD reaction handler as exact metadata-only content."""
    return behavior_identity(
        definition_kind=ContentDefinitionKind.REACTION,
        runtime_behavior_kind=RuntimeBehaviorKind.REACTION,
        pack_id="content.srd_5_1_cc",
        content_id=content_id,
        version=1,
        descriptor=ContentDescriptorSpec(
            display_name=display_name,
            description=description,
            tags=("reaction", "spell", "srd"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                icon_key=icon_key or content_id,
                visual_variant_key=content_id.removeprefix("reaction."),
                vfx_profile=content_id,
                ui_group="reactions.spells",
            ),
            ordering=ContentOrdering(
                sort_group="reactions.spells",
                sort_order=sort_order,
            ),
        ),
        provenance=ContentProvenance(
            primary_source_id="wotc.srd_5_1_cc",
            source_anchor=(
                f"SRD 5.1 (CC-BY-4.0), p. {source_page}, "
                f"Spell Descriptions: {display_name}"
            ),
            relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.REVIEWED,
            notes=(
                "Existing playable reaction behavior; metadata identity does "
                "not claim that every rules edge case is complete."
            ),
        ),
    )


def neurodragon_spell_identity(
    *,
    content_id: str,
    display_name: str,
    description: str,
    school: str,
    level: int,
    sort_order: int,
    icon_key: str | None = None,
) -> Callable[[_DefinitionT], _DefinitionT]:
    """Declare one original Neurodragon spell as metadata-only content."""
    level_tag = "cantrip" if level == 0 else f"level_{level}"
    return behavior_identity(
        definition_kind=ContentDefinitionKind.SPELL,
        runtime_behavior_kind=RuntimeBehaviorKind.SPELL,
        pack_id="content.neurodragon",
        content_id=content_id,
        version=1,
        descriptor=ContentDescriptorSpec(
            display_name=display_name,
            description=description,
            tags=(level_tag, school, "neurodragon", "spell"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                icon_key=icon_key or content_id,
                visual_variant_key=content_id.removeprefix("spell."),
                vfx_profile=content_id,
                ui_group=f"spells.{school}",
            ),
            ordering=ContentOrdering(
                sort_group=f"spells.level_{level}.{school}",
                sort_order=sort_order,
            ),
        ),
        provenance=ContentProvenance(
            primary_source_id="neurodragon.original_b2b3930",
            source_anchor=(
                "Neurodragon original content baseline: "
                f"{display_name}"
            ),
            relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
            fidelity=ContentFidelity.COMPLETE,
            review_status=ContentReviewStatus.REVIEWED,
            notes="Original playable spell behavior preserved exactly.",
        ),
    )
