"""Canonical recipes for parameterized player-class creature factories."""

from __future__ import annotations

from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field

from dnd.actions import CORE_STANDARD_ACTION_DECLARATIONS
import dnd.classes.barbarian as barbarian
import dnd.classes.fighter as fighter
import dnd.classes.rage as rage
import dnd.classes.sorcerer as sorcerer
from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.core.base_conditions import BaseCondition
from dnd.classes.barbarian_factory import (
    BarbarianConfig,
    EquipmentPreset as BarbarianEquipmentPreset,
    PrimalPathChoice,
    create_barbarian,
)
from dnd.classes.fighter_factory import (
    EquipmentPreset as FighterEquipmentPreset,
    FighterConfig,
    FightingStyleChoice,
    create_fighter,
)
from dnd.classes.sorcerer_factory import (
    SorcererConfig,
    SorcererEquipmentPreset,
    SorcererOriginChoice,
    create_sorcerer,
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
from dnd.core.events import AbilityName
from dnd.entity import Entity
from dnd.items.armors import (
    CHAIN_MAIL_RECIPE,
    CLOTH_SHOES_RECIPE,
    IRON_HELMET_RECIPE,
    LEATHER_ARMOR_RECIPE,
    LEATHER_BOOTS_RECIPE,
    ROBES_RECIPE,
    SHIELD_RECIPE,
    STUDDED_LEATHER_RECIPE,
    WIZARD_HAT_RECIPE,
)
from dnd.items.consumables import HASTE_POTION_RECIPE, HEALING_POTION_RECIPE
from dnd.items.weapons import (
    DAGGER_RECIPE,
    GREATAXE_RECIPE,
    GREATSWORD_RECIPE,
    HANDAXE_RECIPE,
    JAVELIN_RECIPE,
    LONGBOW_RECIPE,
    LONGSWORD_RECIPE,
    QUARTERSTAFF_RECIPE,
    SHORTSWORD_RECIPE,
)


AbilityScoreIncrease = list[tuple[AbilityName, int]] | None


class BarbarianCreatureParameters(BaseModel):
    """Durable Barbarian structure without runtime placement or ownership."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: int = Field(default=1, ge=1, le=20)
    base_strength: int = Field(default=15, ge=8, le=15)
    base_dexterity: int = Field(default=13, ge=8, le=15)
    base_constitution: int = Field(default=14, ge=8, le=15)
    base_intelligence: int = Field(default=8, ge=8, le=15)
    base_wisdom: int = Field(default=12, ge=8, le=15)
    base_charisma: int = Field(default=10, ge=8, le=15)
    bonus_plus_2: AbilityName = "strength"
    bonus_plus_1: AbilityName = "constitution"
    primal_path: PrimalPathChoice | None = None
    asi_4: AbilityScoreIncrease = None
    asi_8: AbilityScoreIncrease = None
    asi_12: AbilityScoreIncrease = None
    asi_16: AbilityScoreIncrease = None
    asi_19: AbilityScoreIncrease = None
    equipment_preset: BarbarianEquipmentPreset = "greataxe"


class FighterCreatureParameters(BaseModel):
    """Durable Fighter structure without runtime placement or ownership."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: int = Field(default=1, ge=1, le=20)
    base_strength: int = Field(default=15, ge=8, le=15)
    base_dexterity: int = Field(default=14, ge=8, le=15)
    base_constitution: int = Field(default=13, ge=8, le=15)
    base_intelligence: int = Field(default=10, ge=8, le=15)
    base_wisdom: int = Field(default=12, ge=8, le=15)
    base_charisma: int = Field(default=8, ge=8, le=15)
    bonus_plus_2: AbilityName = "strength"
    bonus_plus_1: AbilityName = "constitution"
    fighting_style: FightingStyleChoice = "defense"
    second_fighting_style: FightingStyleChoice | None = None
    asi_4: AbilityScoreIncrease = None
    asi_6: AbilityScoreIncrease = None
    asi_8: AbilityScoreIncrease = None
    asi_12: AbilityScoreIncrease = None
    asi_14: AbilityScoreIncrease = None
    asi_16: AbilityScoreIncrease = None
    asi_19: AbilityScoreIncrease = None
    equipment_preset: FighterEquipmentPreset = "sword_shield"


class SorcererCreatureParameters(BaseModel):
    """Durable Sorcerer structure without runtime placement or ownership."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: int = Field(default=1, ge=1, le=20)
    base_strength: int = Field(default=8, ge=8, le=15)
    base_dexterity: int = Field(default=14, ge=8, le=15)
    base_constitution: int = Field(default=13, ge=8, le=15)
    base_intelligence: int = Field(default=10, ge=8, le=15)
    base_wisdom: int = Field(default=12, ge=8, le=15)
    base_charisma: int = Field(default=15, ge=8, le=15)
    bonus_plus_2: AbilityName = "charisma"
    bonus_plus_1: AbilityName = "constitution"
    origin: SorcererOriginChoice = SorcererOriginChoice.DRACONIC_BLOODLINE
    draconic_damage_type: str = "Fire"
    metamagic_choices: list[str] | None = None
    asi_4: AbilityScoreIncrease = None
    asi_8: AbilityScoreIncrease = None
    asi_12: AbilityScoreIncrease = None
    asi_16: AbilityScoreIncrease = None
    asi_19: AbilityScoreIncrease = None
    equipment_preset: SorcererEquipmentPreset = "dagger"
    spell_names: list[str] | None = None


def _descriptor(
    *,
    class_id: str,
    display_name: str,
    description: str,
    sort_order: int,
) -> ContentDescriptorSpec:
    """Build stable public metadata for one parameterized class root."""
    content_id = f"creature.player.{class_id}"
    return ContentDescriptorSpec(
        display_name=display_name,
        description=description,
        tags=("class_build", "creature", class_id, "neurodragon", "player_capable"),
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
    """Describe the project-authored parameterized class implementation."""
    return ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon original content baseline: parameterized "
            f"{display_name} class factory"
        ),
        relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,
        adapted_from_source_id="wotc.srd_5_1_cc",
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Existing playable 2014-compatible class progression with "
            "project-authored build and loadout conventions."
        ),
    )


def _standard_action_dependencies() -> tuple[ContentDependency, ...]:
    return tuple(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=declaration.ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Installed by setup_standard_actions.",
        )
        for declaration in sorted(
            CORE_STANDARD_ACTION_DECLARATIONS,
            key=lambda row: row.ref.identity_key,
        )
    )


def _class_feature_dependencies(
    *condition_types: type[BaseCondition],
) -> tuple[ContentDependency, ...]:
    """Declare every root-owned feature condition a class can install."""
    return tuple(
        ContentDependency(
            relation=ContentDependencyRelation.APPLIES_CONDITION,
            target_ref=CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
                condition_type
            ].ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Installed by the parameterized class factory.",
        )
        for condition_type in condition_types
    )


def _possession_dependencies(
    *,
    equipped: tuple[ContentRecipe, ...],
    inventory: tuple[ContentRecipe, ...],
) -> tuple[ContentDependency, ...]:
    """Describe the complete union of selectable/default class possessions."""
    relations = {
        recipe.ref.identity_key: (
            ContentDependencyRelation.EQUIPS_ITEM,
            recipe.ref,
        )
        for recipe in equipped
    }
    for recipe in inventory:
        relations.setdefault(
            recipe.ref.identity_key,
            (ContentDependencyRelation.CREATES_ITEM, recipe.ref),
        )
    return tuple(
        ContentDependency(
            relation=relation,
            target_ref=ref,
            phase=ContentDependencyPhase.CONSTRUCTION,
            notes="Selectable or always-granted class-factory possession.",
        )
        for _, (relation, ref) in sorted(relations.items())
    )


_STANDARD_ACTION_DEPENDENCIES = _standard_action_dependencies()


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.player.barbarian",
    version=1,
    parameters=BarbarianCreatureParameters,
    descriptor=_descriptor(
        class_id="barbarian",
        display_name="Parameterized Barbarian",
        description="A level 1–20 Barbarian build with selectable path and loadout.",
        sort_order=10,
    ),
    provenance=_provenance("Barbarian"),
    dependencies=(
        *_STANDARD_ACTION_DEPENDENCIES,
        *_class_feature_dependencies(
            barbarian.IntimidatingPresenceFeature,
            barbarian.RecklessAttackFeature,
            fighter.ExtraAttackFeature,
            rage.FrenzyFeature,
            rage.RageFeature,
        ),
        *_possession_dependencies(
            equipped=(
                GREATAXE_RECIPE,
                HANDAXE_RECIPE,
                LONGSWORD_RECIPE,
                SHIELD_RECIPE,
            ),
            inventory=(
                HASTE_POTION_RECIPE,
                HEALING_POTION_RECIPE,
                HANDAXE_RECIPE,
                JAVELIN_RECIPE,
                DAGGER_RECIPE,
                LONGSWORD_RECIPE,
                SHIELD_RECIPE,
            ),
        ),
    ),
)
def _build_barbarian(
    raw_context: object,
    parameters: BarbarianCreatureParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    config = BarbarianConfig.model_validate({
        **parameters.model_dump(),
        "name": context.display_name,
        "position": context.position,
        "faction": context.faction,
    })
    return create_barbarian(
        config,
        source_id=context.runtime_entity_uuid,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.player.fighter",
    version=1,
    parameters=FighterCreatureParameters,
    descriptor=_descriptor(
        class_id="fighter",
        display_name="Parameterized Fighter",
        description="A level 1–20 Champion Fighter build and selectable loadout.",
        sort_order=20,
    ),
    provenance=_provenance("Fighter"),
    dependencies=(
        *_STANDARD_ACTION_DEPENDENCIES,
        *_class_feature_dependencies(
            fighter.ActionSurgeFeature,
            fighter.ExtraAttackFeature,
            fighter.SecondWindFeature,
        ),
        *_possession_dependencies(
            equipped=(
                CHAIN_MAIL_RECIPE,
                STUDDED_LEATHER_RECIPE,
                LEATHER_BOOTS_RECIPE,
                LONGSWORD_RECIPE,
                GREATSWORD_RECIPE,
                SHORTSWORD_RECIPE,
                LONGBOW_RECIPE,
                SHIELD_RECIPE,
            ),
            inventory=(
                HASTE_POTION_RECIPE,
                HEALING_POTION_RECIPE,
                CLOTH_SHOES_RECIPE,
                IRON_HELMET_RECIPE,
                HANDAXE_RECIPE,
                JAVELIN_RECIPE,
                DAGGER_RECIPE,
                LONGSWORD_RECIPE,
                LEATHER_ARMOR_RECIPE,
                CHAIN_MAIL_RECIPE,
                SHIELD_RECIPE,
            ),
        ),
    ),
)
def _build_fighter(
    raw_context: object,
    parameters: FighterCreatureParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    config = FighterConfig.model_validate({
        **parameters.model_dump(),
        "name": context.display_name,
        "position": context.position,
        "faction": context.faction,
    })
    return create_fighter(
        config,
        source_id=context.runtime_entity_uuid,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.player.sorcerer",
    version=1,
    parameters=SorcererCreatureParameters,
    descriptor=_descriptor(
        class_id="sorcerer",
        display_name="Parameterized Sorcerer",
        description="A level 1–20 Sorcerer build with selectable origin and spells.",
        sort_order=30,
    ),
    provenance=_provenance("Sorcerer"),
    dependencies=(
        *_STANDARD_ACTION_DEPENDENCIES,
        *_class_feature_dependencies(
            sorcerer.SorceryPointsFeature,
        ),
        *_possession_dependencies(
            equipped=(
                DAGGER_RECIPE,
                QUARTERSTAFF_RECIPE,
                ROBES_RECIPE,
                CLOTH_SHOES_RECIPE,
            ),
            inventory=(
                HASTE_POTION_RECIPE,
                HEALING_POTION_RECIPE,
                ROBES_RECIPE,
                CLOTH_SHOES_RECIPE,
                WIZARD_HAT_RECIPE,
                DAGGER_RECIPE,
                QUARTERSTAFF_RECIPE,
            ),
        ),
    ),
)
def _build_sorcerer(
    raw_context: object,
    parameters: SorcererCreatureParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    config = SorcererConfig.model_validate({
        **parameters.model_dump(),
        "name": context.display_name,
        "position": context.position,
        "faction": context.faction,
    })
    return create_sorcerer(
        config,
        source_id=context.runtime_entity_uuid,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )


PLAYER_CLASS_CREATURE_DECLARATIONS: tuple[ContentDeclaration, ...] = tuple(
    get_content_declaration(factory)
    for factory in (
        _build_barbarian,
        _build_fighter,
        _build_sorcerer,
    )
)
PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID = MappingProxyType({
    declaration.ref.content_id.removeprefix("creature.player."): declaration
    for declaration in PLAYER_CLASS_CREATURE_DECLARATIONS
})
PLAYER_CLASS_CREATURE_RECIPES_BY_ID = MappingProxyType({
    class_id: ContentRecipe.create(
        ref=declaration.ref,
        parameters={},
    )
    for class_id, declaration
    in PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID.items()
})
