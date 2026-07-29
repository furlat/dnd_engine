"""NeuroDragon presentation compositions over exact SRD creature mechanics."""

from __future__ import annotations

from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from dnd.content_system.creature_possessions import (
    CreaturePossessionDisposition,
    CreaturePossessionGrant,
    apply_creature_possessions,
    creature_possession_dependencies,
)
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentVisibility,
)
from dnd.core.content.materialization import CreatureBuildContext
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    ContentDeclaration,
    creature_factory,
    get_content_declaration,
)
from dnd.core.equipment_types import BodyPart
from dnd.entity import Entity
from dnd.items.armors import (
    ARMORED_BOOTS_RECIPE,
    LEATHER_BOOTS_RECIPE,
)
from dnd.items.apparel_presets import (
    ACOLYTE_VESTMENTS_PRESET,
    BLUE_CLOTH_SHOES_PRESET,
    BROWN_BOOTS_PRESET,
    BROWN_LEATHER_SHOES_PRESET,
    DARK_BOOTS_PRESET,
    FARMHAND_TUNIC_PRESET,
    PEASANT_RAGS_PRESET,
    ROPE_SANDALS_PRESET,
    THIEF_GARB_PRESET,
    WIZARD_ROBE_PRESET,
)
from dnd.monsters.srd_roster import (
    SRD_CREATURE_DECLARATIONS_BY_ID,
    SRD_CREATURE_RECIPES_BY_ID,
    construct_srd_creature,
)


class ConfiguredSrdCreatureParameters(BaseModel):
    """Fixed NeuroDragon presentation compositions have no open parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _equipped(
    recipe: ContentRecipe,
    slot: BodyPart,
) -> CreaturePossessionGrant:
    return CreaturePossessionGrant(
        recipe=recipe,
        disposition=CreaturePossessionDisposition.EQUIPPED,
        equipment_slot=slot,
    )


_LEATHER_BOOTS = (_equipped(LEATHER_BOOTS_RECIPE, BodyPart.FEET),)
_DARK_BOOTS = (_equipped(DARK_BOOTS_PRESET.recipe, BodyPart.FEET),)
_ARMORED_BOOTS = (_equipped(ARMORED_BOOTS_RECIPE, BodyPart.FEET),)


CONFIGURED_SRD_CREATURE_WARDROBE_GRANTS_BY_ID = MappingProxyType({
    "commoner": (
        _equipped(FARMHAND_TUNIC_PRESET.recipe, BodyPart.BODY),
        _equipped(BROWN_LEATHER_SHOES_PRESET.recipe, BodyPart.FEET),
    ),
    "bandit": _DARK_BOOTS,
    "cultist": _DARK_BOOTS,
    "guard": _LEATHER_BOOTS,
    "tribal_warrior": _LEATHER_BOOTS,
    "kobold": (
        _equipped(PEASANT_RAGS_PRESET.recipe, BodyPart.BODY),
        _equipped(ROPE_SANDALS_PRESET.recipe, BodyPart.FEET),
    ),
    "acolyte": (
        _equipped(ACOLYTE_VESTMENTS_PRESET.recipe, BodyPart.BODY),
        _equipped(ROPE_SANDALS_PRESET.recipe, BodyPart.FEET),
    ),
    "scout": (_equipped(BROWN_BOOTS_PRESET.recipe, BodyPart.FEET),),
    "thug": _LEATHER_BOOTS,
    "spy": (
        _equipped(THIEF_GARB_PRESET.recipe, BodyPart.BODY),
        _equipped(DARK_BOOTS_PRESET.recipe, BodyPart.FEET),
    ),
    "berserker": _LEATHER_BOOTS,
    "bandit_captain": _DARK_BOOTS,
    "priest": _LEATHER_BOOTS,
    "cult_fanatic": _DARK_BOOTS,
    "knight": _ARMORED_BOOTS,
    "veteran": _ARMORED_BOOTS,
    "mage": (
        _equipped(WIZARD_ROBE_PRESET.recipe, BodyPart.BODY),
        _equipped(BLUE_CLOTH_SHOES_PRESET.recipe, BodyPart.FEET),
    ),
    "orc": _LEATHER_BOOTS,
    "hobgoblin": _ARMORED_BOOTS,
    "bugbear": _DARK_BOOTS,
    "gnoll": _LEATHER_BOOTS,
})


def _declare_configured_srd_creature(
    creature_id: str,
    grants: tuple[CreaturePossessionGrant, ...],
    sort_order: int,
) -> ContentDeclaration:
    """Declare one exact downstream composition without mutating the SRD root."""
    base = SRD_CREATURE_DECLARATIONS_BY_ID[creature_id]
    presentation = base.descriptor.presentation.model_copy(update={
        "icon_key": None,
        "ui_group": "creatures.neurodragon.configured_srd",
    })
    descriptor = ContentDescriptorSpec(
        display_name=base.descriptor.display_name,
        description=(
            f"{base.descriptor.description} NeuroDragon presentation "
            "composition with exact creature-owned wardrobe."
        ),
        tags=tuple(sorted({
            *base.descriptor.tags,
            "configured",
            "neurodragon",
        })),
        visibility=ContentVisibility.PUBLIC,
        presentation=presentation,
        ordering=ContentOrdering(
            sort_group="creatures.neurodragon.configured_srd",
            sort_order=sort_order,
        ),
    )
    provenance = ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "NeuroDragon configured SRD creature presentation: "
            f"{base.descriptor.display_name}"
        ),
        relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,
        adapted_from_source_id="wotc.srd_5_1_cc",
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Reuses the exact SRD mechanical creature construction and owns "
            "only NeuroDragon presentation possessions."
        ),
    )

    def factory(
        raw_context: object,
        parameters: ConfiguredSrdCreatureParameters,
    ) -> Entity:
        _ = parameters
        context = CreatureBuildContext.model_validate(raw_context)
        entity = construct_srd_creature(context, creature_id)
        apply_creature_possessions(
            entity,
            grants,
            possession_mode=context.possession_mode,
        )
        return entity

    factory.__name__ = f"_build_configured_srd_{creature_id}"
    factory.__qualname__ = factory.__name__
    declared_factory = creature_factory(
        pack_id="content.neurodragon",
        content_id=f"creature.configured_srd.{creature_id}",
        version=1,
        parameters=ConfiguredSrdCreatureParameters,
        descriptor=descriptor,
        provenance=provenance,
        dependencies=(
            ContentDependency(
                relation=ContentDependencyRelation.CONFIGURES_CREATURE,
                target_ref=base.ref,
                phase=ContentDependencyPhase.CONSTRUCTION,
                notes=(
                    "Exact SRD mechanical creature configured by this "
                    "NeuroDragon presentation root."
                ),
            ),
            *creature_possession_dependencies(grants),
        ),
    )(factory)
    return get_content_declaration(declared_factory)


CONFIGURED_SRD_CREATURE_DECLARATIONS = tuple(
    _declare_configured_srd_creature(creature_id, grants, sort_order)
    for sort_order, (creature_id, grants) in enumerate(
        CONFIGURED_SRD_CREATURE_WARDROBE_GRANTS_BY_ID.items(),
        start=1,
    )
)
CONFIGURED_SRD_CREATURE_DECLARATIONS_BY_ID = MappingProxyType({
    declaration.ref.content_id.removeprefix("creature.configured_srd."):
        declaration
    for declaration in CONFIGURED_SRD_CREATURE_DECLARATIONS
})
CONFIGURED_SRD_CREATURE_RECIPES_BY_ID = MappingProxyType({
    creature_id: ContentRecipe.create(
        ref=declaration.ref,
        parameters={},
    )
    for creature_id, declaration
    in CONFIGURED_SRD_CREATURE_DECLARATIONS_BY_ID.items()
})
PLAYABLE_SRD_CREATURE_DECLARATIONS_BY_ID = MappingProxyType({
    creature_id: CONFIGURED_SRD_CREATURE_DECLARATIONS_BY_ID.get(
        creature_id,
        declaration,
    )
    for creature_id, declaration in SRD_CREATURE_DECLARATIONS_BY_ID.items()
})
PLAYABLE_SRD_CREATURE_RECIPES_BY_ID = MappingProxyType({
    creature_id: CONFIGURED_SRD_CREATURE_RECIPES_BY_ID.get(
        creature_id,
        recipe,
    )
    for creature_id, recipe in SRD_CREATURE_RECIPES_BY_ID.items()
})


__all__ = [
    "CONFIGURED_SRD_CREATURE_DECLARATIONS",
    "CONFIGURED_SRD_CREATURE_DECLARATIONS_BY_ID",
    "CONFIGURED_SRD_CREATURE_RECIPES_BY_ID",
    "CONFIGURED_SRD_CREATURE_WARDROBE_GRANTS_BY_ID",
    "ConfiguredSrdCreatureParameters",
    "PLAYABLE_SRD_CREATURE_DECLARATIONS_BY_ID",
    "PLAYABLE_SRD_CREATURE_RECIPES_BY_ID",
]
