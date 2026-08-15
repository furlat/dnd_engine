"""Exact authored spell-catalog projection for design-time clients."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from dnd.content_system.spell_catalog_composition import (
    SPELL_CATALOG_COMPOSITION_ROWS,
    SpellCatalogCompositionRow,
)
from dnd.spells.content_metadata import get_spell_catalog_metadata
from server.api_models import (
    SpellCatalogEntry,
    SpellCatalogMultiTarget,
    SpellCatalogResponse,
    SpellCatalogSavingThrow,
    SpellCatalogVfx,
)


CATALOG_VERSION = "2026-07-26.2"


@lru_cache(maxsize=1)
def build_spell_catalog() -> SpellCatalogResponse:
    """Project the complete reviewed built-in public spell ledger."""
    spells = [
        build_spell_catalog_entry(row)
        for row in SPELL_CATALOG_COMPOSITION_ROWS
    ]
    return SpellCatalogResponse(
        version=CATALOG_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        spells=spells,
    )


def build_spell_catalog_entry(
    composition: SpellCatalogCompositionRow,
) -> SpellCatalogEntry:
    """Project one exact ledger row without constructing or inspecting code."""
    declaration = composition.declaration
    metadata = composition.metadata
    if (
        composition.spell_type is not None
        and get_spell_catalog_metadata(composition.spell_type) != metadata
    ):
        raise ValueError(
            f"Spell class {composition.spell_type!r} lost its authored "
            "catalog metadata",
        )

    area = metadata.aoe
    multi_target = (
        SpellCatalogMultiTarget(
            min_targets=metadata.multi_target.min_targets,
            max_targets=metadata.multi_target.max_targets,
            allow_same_target=metadata.multi_target.allow_same_target,
            projectiles_per_cast=(
                metadata.multi_target.projectiles_per_cast
            ),
        )
        if metadata.multi_target is not None
        else None
    )
    saving_throws = tuple(
        SpellCatalogSavingThrow(
            ability=save.ability,
            dc_source=save.dc_source,
        )
        for save in metadata.saving_throws
    )

    return SpellCatalogEntry(
        id=metadata.catalog_id,
        content_ref=declaration.ref,
        name=composition.display_name,
        level=composition.level,
        school=composition.school,
        description=metadata.description,
        target_type=metadata.target_type,
        range_type=metadata.range_type,
        range_ft=metadata.range_ft,
        projectile_type=metadata.projectile_type,
        aoe_shape_type=area.shape if area is not None else None,
        aoe_radius_ft=area.radius_ft if area is not None else None,
        aoe_length_ft=area.length_ft if area is not None else None,
        aoe_width_ft=area.width_ft if area is not None else None,
        aoe_height_ft=area.height_ft if area is not None else None,
        damage_types=[
            damage_type.value
            for damage_type in metadata.damage_types
        ],
        healing=metadata.healing,
        attack_roll=metadata.attack_roll,
        saving_throws=saving_throws,
        concentration=metadata.concentration,
        ritual=metadata.ritual,
        verbal=metadata.verbal,
        somatic=metadata.somatic,
        material=metadata.material,
        classes=list(metadata.classes),
        subclasses=list(metadata.subclasses),
        source=declaration.provenance.primary_source_id,
        multi_target=multi_target,
        vfx=SpellCatalogVfx(
            projectile_type=metadata.projectile_type,
            aoe_shape_type=area.shape if area is not None else None,
            route_hint=metadata.delivery,
            recommended_asset_tags=list(
                metadata.recommended_asset_tags,
            ),
        ),
    )
