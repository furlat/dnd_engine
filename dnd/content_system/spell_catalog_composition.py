"""Deployment-safe composition of built-in spell-catalog rows.

The core ``dnd.spells`` package owns its native public spell inventory and
must remain importable while ``dnd.actions_functional`` is still initializing.
Extension spells are joined here, above both the spell and extension packages,
so a native spell module never imports an extension package.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from dnd.actions import SpellAction
from dnd.content_system.action_definitions import (
    ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.core.content.registration import ContentDeclaration
from dnd.extensions.aegis_spark import AegisSpark
from dnd.spells.catalog_content import (
    SPELL_CATALOG_METADATA_BY_CLASS,
    SPELL_CONTENT_DECLARATIONS_BY_CLASS,
    SPELL_CONTENT_IDENTITY_SPECS,
)
from dnd.spells.content_metadata import (
    SpellCatalogMetadata,
    attach_spell_catalog_metadata,
)
from dnd.spells.reaction_spell_content import (
    LEARNED_REACTION_SPELL_SPECS,
    LearnedReactionHandlerFactory,
)


@dataclass(frozen=True, slots=True)
class SpellCatalogCompositionRow:
    """One exact runtime class, declaration, and authored catalog record."""

    display_name: str
    spell_type: type[SpellAction] | None
    declaration: ContentDeclaration
    metadata: SpellCatalogMetadata
    school: str
    level: int
    catalog_order: int
    reaction_handler_factory: LearnedReactionHandlerFactory | None = None

    def __post_init__(self) -> None:
        if (self.spell_type is None) == (
            self.reaction_handler_factory is None
        ):
            raise ValueError(
                "Spell composition must own exactly one playable runtime "
                "surface",
            )


_NATIVE_ROWS: tuple[SpellCatalogCompositionRow, ...] = tuple(
    SpellCatalogCompositionRow(
        display_name=spec.display_name,
        spell_type=spec.spell_type,
        declaration=SPELL_CONTENT_DECLARATIONS_BY_CLASS[spec.spell_type],
        metadata=SPELL_CATALOG_METADATA_BY_CLASS[spec.spell_type],
        school=spec.school,
        level=spec.level,
        catalog_order=spec.sort_order,
    )
    for spec in SPELL_CONTENT_IDENTITY_SPECS
)

_AEGIS_SPARK_METADATA = SpellCatalogMetadata(
    catalog_id="aegis_spark",
    description="Ward yourself or a visible ally with +2 Armor Class",
    target_type="entity",
    range_type="ranged",
    range_ft=30,
    delivery="none",
    projectile_type=None,
    aoe=None,
    damage_types=(),
    healing=False,
    attack_roll=False,
    saving_throws=(),
    concentration=False,
    ritual=False,
    verbal=True,
    somatic=None,
    material=None,
    classes=(),
    subclasses=(),
    multi_target=None,
    recommended_asset_tags=("abjuration", "ward"),
)
attach_spell_catalog_metadata(AegisSpark, _AEGIS_SPARK_METADATA)
_AEGIS_SPARK_ROW = SpellCatalogCompositionRow(
    display_name="Aegis Spark",
    spell_type=AegisSpark,
    declaration=ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[AegisSpark],
    metadata=_AEGIS_SPARK_METADATA,
    school="abjuration",
    level=0,
    catalog_order=125,
)

_LEARNED_REACTION_ROWS: tuple[SpellCatalogCompositionRow, ...] = tuple(
    SpellCatalogCompositionRow(
        display_name=spec.display_name,
        spell_type=None,
        declaration=spec.declaration,
        metadata=spec.metadata,
        school=spec.school,
        level=spec.level,
        catalog_order=spec.catalog_order,
        reaction_handler_factory=spec.handler_factory,
    )
    for spec in LEARNED_REACTION_SPELL_SPECS
)

# Keep the explicit authored public order without making an extension a
# dependency of the native spell package.
SPELL_CATALOG_COMPOSITION_ROWS: tuple[
    SpellCatalogCompositionRow,
    ...,
] = tuple(sorted(
    (*_NATIVE_ROWS, _AEGIS_SPARK_ROW, *_LEARNED_REACTION_ROWS),
    key=lambda row: row.catalog_order,
))
SPELL_CATALOG_COMPOSITION_BY_CLASS = MappingProxyType({
    cast(type[SpellAction], row.spell_type): row
    for row in SPELL_CATALOG_COMPOSITION_ROWS
    if row.spell_type is not None
})
SPELL_CATALOG_COMPOSITION_BY_NAME = MappingProxyType({
    row.display_name: row
    for row in SPELL_CATALOG_COMPOSITION_ROWS
})
SPELL_CATALOG_COMPOSITION_BY_ID = MappingProxyType({
    row.metadata.catalog_id: row
    for row in SPELL_CATALOG_COMPOSITION_ROWS
})

if not (
    len(SPELL_CATALOG_COMPOSITION_ROWS)
    == len(SPELL_CATALOG_COMPOSITION_BY_NAME)
    == len(SPELL_CATALOG_COMPOSITION_BY_ID)
):
    raise ValueError("Spell catalog composition contains duplicate identities")
if len(SPELL_CATALOG_COMPOSITION_BY_CLASS) != sum(
    row.spell_type is not None
    for row in SPELL_CATALOG_COMPOSITION_ROWS
):
    raise ValueError("Spell catalog composition contains duplicate classes")
if (
    _AEGIS_SPARK_ROW.declaration.ref.definition_kind.value != "spell"
    or _AEGIS_SPARK_ROW.declaration.runtime_behavior_kind is None
    or _AEGIS_SPARK_ROW.declaration.runtime_behavior_kind.value != "spell"
):
    raise ValueError("Aegis Spark catalog row lost its exact spell declaration")


__all__ = [
    "SPELL_CATALOG_COMPOSITION_BY_CLASS",
    "SPELL_CATALOG_COMPOSITION_BY_ID",
    "SPELL_CATALOG_COMPOSITION_BY_NAME",
    "SPELL_CATALOG_COMPOSITION_ROWS",
    "SpellCatalogCompositionRow",
]
