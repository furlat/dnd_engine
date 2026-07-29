"""Approved schema-2 premade character build data.

Premades are durable character definitions, not alternate creature factories.
Their bodies, class grants, and possessions therefore flow through the same
schema-2 validator and materializer as player-authored characters.
"""

from __future__ import annotations

from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from dnd.classes.content_factories import materialize_authored_class_root
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    BuiltinCharacterBuild,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
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
from dnd.entity import Entity


BARBARIAN_L5_BERSERKER_TORCH_PREMADE_ID = (
    "hero.barbarian_l5_berserker_torch"
)
FIGHTER_L5_SHIELD_TORCH_PREMADE_ID = "hero.fighter_l5_shield_torch"
FIGHTER_2_SORCERER_3_SPELLBLADE_PREMADE_ID = (
    "hero.fighter_2_sorcerer_3_spellblade"
)
SORCERER_L5_STANDARD_TORCH_PREMADE_ID = (
    "hero.sorcerer_l5_standard_torch"
)

PREMADE_CHARACTER_BUILDS: MappingProxyType[
    str,
    BuiltinCharacterBuild,
] = MappingProxyType(dict(BUILTIN_PREMADE_BUILDS))


class PremadeCreatureParameters(BaseModel):
    """Approved premade roots have no variable build parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _descriptor(
    *,
    display_name: str,
    class_id: str,
    visual_variant_key: str,
    sort_order: int,
) -> ContentDescriptorSpec:
    return ContentDescriptorSpec(
        display_name=display_name,
        description=(
            "Approved schema-2 level-five premade character and starter "
            "holdings."
        ),
        tags=(
            class_id,
            "creature",
            "level_5",
            "neurodragon",
            "player_capable",
            "premade",
        ),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key=f"creature.premade.{visual_variant_key}",
            portrait_key=f"creature.premade.{visual_variant_key}",
            visual_variant_key=visual_variant_key,
            ui_group="creatures.premade",
        ),
        ordering=ContentOrdering(
            sort_group="creatures.premade",
            sort_order=sort_order,
        ),
    )


def _provenance(display_name: str) -> ContentProvenance:
    return ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon schema-2 approved premade: "
            f"{display_name}"
        ),
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Exact durable build and holdings delegate to the canonical "
            "schema-2 validator and character materializer."
        ),
    )


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.premade.barbarian_l5_berserker_torch",
    version=1,
    parameters=PremadeCreatureParameters,
    descriptor=_descriptor(
        display_name="Level 5 Berserker With Torch",
        class_id="barbarian",
        visual_variant_key="barbarian_l5_berserker_torch",
        sort_order=10,
    ),
    provenance=_provenance("Level 5 Berserker With Torch"),
)
def _build_barbarian_l5_berserker_torch(
    raw_context: object,
    parameters: PremadeCreatureParameters,
) -> Entity:
    _ = parameters
    return materialize_authored_class_root(
        context=CreatureBuildContext.model_validate(raw_context),
        build=PREMADE_CHARACTER_BUILDS[
            BARBARIAN_L5_BERSERKER_TORCH_PREMADE_ID
        ],
    )


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.premade.fighter_l5_shield_torch",
    version=1,
    parameters=PremadeCreatureParameters,
    descriptor=_descriptor(
        display_name="Level 5 Shield Fighter With Longbow And Torch",
        class_id="fighter",
        visual_variant_key="fighter_l5_shield_torch",
        sort_order=20,
    ),
    provenance=_provenance(
        "Level 5 Shield Fighter With Longbow And Torch",
    ),
)
def _build_fighter_l5_shield_torch(
    raw_context: object,
    parameters: PremadeCreatureParameters,
) -> Entity:
    _ = parameters
    return materialize_authored_class_root(
        context=CreatureBuildContext.model_validate(raw_context),
        build=PREMADE_CHARACTER_BUILDS[
            FIGHTER_L5_SHIELD_TORCH_PREMADE_ID
        ],
    )


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.premade.sorcerer_l5_standard_torch",
    version=1,
    parameters=PremadeCreatureParameters,
    descriptor=_descriptor(
        display_name="Level 5 Sorcerer With Torch",
        class_id="sorcerer",
        visual_variant_key="sorcerer_l5_standard_torch",
        sort_order=30,
    ),
    provenance=_provenance("Level 5 Sorcerer With Torch"),
)
def _build_sorcerer_l5_standard_torch(
    raw_context: object,
    parameters: PremadeCreatureParameters,
) -> Entity:
    _ = parameters
    return materialize_authored_class_root(
        context=CreatureBuildContext.model_validate(raw_context),
        build=PREMADE_CHARACTER_BUILDS[
            SORCERER_L5_STANDARD_TORCH_PREMADE_ID
        ],
    )


BARBARIAN_L5_BERSERKER_TORCH_DECLARATION = get_content_declaration(
    _build_barbarian_l5_berserker_torch,
)
FIGHTER_L5_SHIELD_TORCH_DECLARATION = get_content_declaration(
    _build_fighter_l5_shield_torch,
)
SORCERER_L5_STANDARD_TORCH_DECLARATION = get_content_declaration(
    _build_sorcerer_l5_standard_torch,
)
BARBARIAN_L5_BERSERKER_TORCH_RECIPE = ContentRecipe.create(
    ref=BARBARIAN_L5_BERSERKER_TORCH_DECLARATION.ref,
    parameters={},
)
FIGHTER_L5_SHIELD_TORCH_RECIPE = ContentRecipe.create(
    ref=FIGHTER_L5_SHIELD_TORCH_DECLARATION.ref,
    parameters={},
)
SORCERER_L5_STANDARD_TORCH_RECIPE = ContentRecipe.create(
    ref=SORCERER_L5_STANDARD_TORCH_DECLARATION.ref,
    parameters={},
)
NEURODRAGON_PREMADE_CREATURE_DECLARATIONS: tuple[
    ContentDeclaration,
    ...,
] = (
    BARBARIAN_L5_BERSERKER_TORCH_DECLARATION,
    FIGHTER_L5_SHIELD_TORCH_DECLARATION,
    SORCERER_L5_STANDARD_TORCH_DECLARATION,
)

__all__ = [
    "BARBARIAN_L5_BERSERKER_TORCH_DECLARATION",
    "BARBARIAN_L5_BERSERKER_TORCH_PREMADE_ID",
    "BARBARIAN_L5_BERSERKER_TORCH_RECIPE",
    "FIGHTER_L5_SHIELD_TORCH_DECLARATION",
    "FIGHTER_2_SORCERER_3_SPELLBLADE_PREMADE_ID",
    "FIGHTER_L5_SHIELD_TORCH_PREMADE_ID",
    "FIGHTER_L5_SHIELD_TORCH_RECIPE",
    "NEURODRAGON_PREMADE_CREATURE_DECLARATIONS",
    "PREMADE_CHARACTER_BUILDS",
    "PremadeCreatureParameters",
    "SORCERER_L5_STANDARD_TORCH_DECLARATION",
    "SORCERER_L5_STANDARD_TORCH_PREMADE_ID",
    "SORCERER_L5_STANDARD_TORCH_RECIPE",
]
