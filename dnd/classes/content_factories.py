"""Schema-2-backed catalog roots for the three implemented player classes.

These roots retain exact historic creature identities for authored scenarios.
They are not a second class implementation: every factory composes an
authenticated ``CharacterDefinitionRevisionV2`` and delegates to the canonical
character materializer.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dnd.content_system.builtin_character_builds import (
    DEFAULT_CHARACTER_RULESET_DIGEST,
    BuiltinCharacterBuild,
    BuiltinSingleClassBuild,
    compose_builtin_character_revisions,
)
from dnd.content_system.character_materialization import materialize_character
from dnd.content_system.creature_bindings import CreatureRuntimeBindingRegistry
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.durable_characters import (
    AbilityScoreName,
    CharacterHoldingsRevision,
)
from dnd.core.content.materialization import (
    CreatureBuildContext,
    CreaturePossessionMode,
)
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


AbilityIncrease = tuple[tuple[AbilityScoreName, int], ...]


class BarbarianCreatureParameters(BaseModel):
    """Authored schema-2 Barbarian fixture inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: int = Field(default=1, ge=1, le=20)
    equipment_preset: Literal[
        "greataxe",
        "dual_axes",
        "sword_shield",
    ] = "greataxe"
    asi_4: AbilityIncrease = ()
    asi_8: AbilityIncrease = ()


class FighterCreatureParameters(BaseModel):
    """Authored schema-2 Fighter fixture inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: int = Field(default=1, ge=1, le=20)
    fighting_style: Literal[
        "archery",
        "defense",
        "dueling",
        "great_weapon",
        "protection",
        "two_weapon",
    ] = "defense"
    equipment_preset: Literal[
        "sword_shield",
        "greatsword",
        "dual_wield",
        "archery",
    ] = "sword_shield"
    asi_4: AbilityIncrease = ()
    asi_6: AbilityIncrease = ()
    asi_8: AbilityIncrease = ()


class SorcererCreatureParameters(BaseModel):
    """Authored schema-2 Sorcerer fixture inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: int = Field(default=1, ge=1, le=20)
    equipment_preset: Literal["dagger", "quarterstaff"] = "dagger"
    metamagic_choices: tuple[
        Literal["distant", "quickened", "twinned"],
        ...,
    ] = ()
    spell_names: tuple[str, ...] = ()
    asi_4: AbilityIncrease = ()
    asi_8: AbilityIncrease = ()


def _descriptor(
    *,
    class_id: str,
    display_name: str,
    sort_order: int,
) -> ContentDescriptorSpec:
    content_id = f"creature.player.{class_id}"
    return ContentDescriptorSpec(
        display_name=display_name,
        description=(
            "Engine-owned schema-2 class fixture. Player character creation "
            "uses the class definition and additive level ledger directly."
        ),
        tags=("class_build", "creature", class_id, "neurodragon"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key=content_id,
            portrait_key=content_id,
            visual_variant_key=class_id,
            ui_group="creatures.player_classes",
        ),
        ordering=ContentOrdering(
            sort_group="creatures.player_classes",
            sort_order=sort_order,
        ),
    )


def _provenance(display_name: str) -> ContentProvenance:
    return ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon schema-2 authored scenario root: "
            f"{display_name}"
        ),
        relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,
        adapted_from_source_id="wotc.srd_5_1_cc",
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Exact catalog identity delegates to the canonical additive "
            "character definition, validator, holdings, and materializer."
        ),
    )


def materialize_authored_class_root(
    *,
    context: CreatureBuildContext,
    build: BuiltinCharacterBuild,
) -> Entity:
    """Materialize one catalog root without installing a parallel body path."""
    runtime = SERVER_CONTENT_SYSTEM_RUNTIME
    revisions = compose_builtin_character_revisions(
        character_id=context.runtime_entity_uuid,
        build=build,
        content_system=runtime.require(),
    )
    holdings = revisions.holdings
    if (
        context.possession_mode
        == CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
    ):
        holdings = CharacterHoldingsRevision.create(
            character_id=context.runtime_entity_uuid,
            holdings_revision=1,
        )
    result = materialize_character(
        definition=revisions.definition,
        holdings=holdings,
        loadout=revisions.loadout,
        runtime_entity_uuid=context.runtime_entity_uuid,
        display_name=context.display_name,
        faction=context.faction,
        position=context.position,
        deployment_role=context.deployment_role,
        expected_ruleset_digest=DEFAULT_CHARACTER_RULESET_DIGEST,
        creature_binding_registry=CreatureRuntimeBindingRegistry(),
        runtime_content_ref=context.requested_ref,
        runtime=runtime,
    )
    return result.entity


def _asi_rows(
    *rows: tuple[int, AbilityIncrease],
) -> tuple[tuple[int, AbilityIncrease], ...]:
    return tuple((level, increases) for level, increases in rows if increases)


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.player.barbarian",
    version=1,
    parameters=BarbarianCreatureParameters,
    descriptor=_descriptor(
        class_id="barbarian",
        display_name="Schema-2 Barbarian Fixture",
        sort_order=10,
    ),
    provenance=_provenance("Barbarian"),
)
def _build_barbarian(
    raw_context: object,
    parameters: BarbarianCreatureParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    return materialize_authored_class_root(
        context=context,
        build=BuiltinSingleClassBuild(
            class_id="barbarian",
            level=parameters.level,
            equipment_preset=parameters.equipment_preset,
            asi_by_level=_asi_rows(
                (4, parameters.asi_4),
                (8, parameters.asi_8),
            ),
        ),
    )


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.player.fighter",
    version=1,
    parameters=FighterCreatureParameters,
    descriptor=_descriptor(
        class_id="fighter",
        display_name="Schema-2 Fighter Fixture",
        sort_order=20,
    ),
    provenance=_provenance("Fighter"),
)
def _build_fighter(
    raw_context: object,
    parameters: FighterCreatureParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    return materialize_authored_class_root(
        context=context,
        build=BuiltinSingleClassBuild(
            class_id="fighter",
            level=parameters.level,
            equipment_preset=parameters.equipment_preset,
            fighting_style=parameters.fighting_style,
            asi_by_level=_asi_rows(
                (4, parameters.asi_4),
                (6, parameters.asi_6),
                (8, parameters.asi_8),
            ),
        ),
    )


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.player.sorcerer",
    version=1,
    parameters=SorcererCreatureParameters,
    descriptor=_descriptor(
        class_id="sorcerer",
        display_name="Schema-2 Sorcerer Fixture",
        sort_order=30,
    ),
    provenance=_provenance("Sorcerer"),
)
def _build_sorcerer(
    raw_context: object,
    parameters: SorcererCreatureParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    return materialize_authored_class_root(
        context=context,
        build=BuiltinSingleClassBuild(
            class_id="sorcerer",
            level=parameters.level,
            equipment_preset=parameters.equipment_preset,
            metamagic_choices=parameters.metamagic_choices,
            spell_names=parameters.spell_names,
            asi_by_level=_asi_rows(
                (4, parameters.asi_4),
                (8, parameters.asi_8),
            ),
        ),
    )


PLAYER_CLASS_CREATURE_DECLARATIONS: tuple[ContentDeclaration, ...] = tuple(
    get_content_declaration(factory)
    for factory in (_build_barbarian, _build_fighter, _build_sorcerer)
)
PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID = MappingProxyType({
    declaration.ref.content_id.removeprefix("creature.player."): declaration
    for declaration in PLAYER_CLASS_CREATURE_DECLARATIONS
})
PLAYER_CLASS_CREATURE_RECIPES_BY_ID = MappingProxyType({
    class_id: ContentRecipe.create(ref=declaration.ref, parameters={})
    for class_id, declaration
    in PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID.items()
})


__all__ = [
    "BarbarianCreatureParameters",
    "FighterCreatureParameters",
    "PLAYER_CLASS_CREATURE_DECLARATIONS",
    "PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID",
    "PLAYER_CLASS_CREATURE_RECIPES_BY_ID",
    "SorcererCreatureParameters",
    "materialize_authored_class_root",
]
