"""Canonical recipes for the active NeuroDragon bestiary factories."""

from __future__ import annotations

from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dnd.actions import CORE_STANDARD_ACTION_DECLARATIONS
from dnd.content_system.action_definitions import (
    ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.content_system.creature_possessions import (
    CreaturePossessionDisposition,
    CreaturePossessionGrant,
    apply_creature_possessions,
    creature_possession_dependencies,
)
from dnd.core.base_actions import BaseAction
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
from dnd.core.equipment_types import BodyPart
from dnd.entity import Entity
from dnd.items.armors import (
    CLOTH_SHOES_RECIPE,
    CROWN_RECIPE,
    LEATHER_ARMOR_RECIPE,
    WOODEN_SHIELD_RECIPE,
)
from dnd.items.apparel_presets import (
    DARK_CLOTH_SHOES_PRESET,
    DARK_BOOTS_PRESET,
    DARK_CULTIST_ROBES_PRESET,
    HEDGE_WIZARD_ROBE_PRESET,
    NECROMANCER_ROBE_PRESET,
    PRIEST_VESTMENTS_PRESET,
    ROPE_SANDALS_PRESET,
)
from dnd.items.consumables import (
    GREATER_INVISIBILITY_POTION_RECIPE,
    HASTE_POTION_RECIPE,
)
from dnd.items.spell_items import (
    ACID_FLASK_RECIPE,
    INVISIBILITY_SCROLL_RECIPE,
)
from dnd.items.weapons import (
    ARCANE_STAFF_RECIPE,
    DAGGER_RECIPE,
    LONGSWORD_RECIPE,
    SCIMITAR_RECIPE,
    SHORTBOW_RECIPE,
    SHORTSWORD_RECIPE,
)
from dnd.monsters.bestiary import (
    create_caster,
    create_goblin,
    create_goblin_archer,
    create_goblin_caster,
    create_skeleton,
    create_skeleton_archer,
    create_skeleton_warlock,
    create_skeleton_warrior,
)
from dnd.monsters.bestiary_items import ARMOR_SCRAPS_RECIPE
from dnd.monsters.skeleton_abilities import MarkTargetAction
from dnd.spells.evocation import BurningHands, FireBolt, Fireball, MagicMissile
from dnd.spells.illusion import Invisibility


class GoblinParameters(BaseModel):
    """Durable authored parameters for the active Goblin root."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    weight: int = Field(default=40, ge=1)


class SkeletonParameters(BaseModel):
    """Durable authored parameters for the active Skeleton root."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    weight: int = Field(default=120, ge=1)
    darkvision: bool = True


class GoblinArcherParameters(BaseModel):
    """Durable authored parameters for the Goblin Archer variant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    weight: int = Field(default=40, ge=1)


class GenericCasterParameters(BaseModel):
    """Durable authored parameters for the classless full-caster variant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: int = Field(default=5, ge=1, le=20)
    wardrobe: Literal[
        "arcane",
        "dark",
        "divine",
        "necromancer",
    ] = "arcane"


class GoblinCasterParameters(BaseModel):
    """Durable authored parameters for the goblin full-caster variant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: int = Field(default=5, ge=1, le=20)
    weight: int = Field(default=40, ge=1)


class SkeletonVariantParameters(BaseModel):
    """Shared durable parameters for the three skeleton variants."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    weight: int = Field(default=120, ge=1)
    darkvision: bool = False


def _descriptor(
    *,
    content_id: str,
    display_name: str,
    description: str,
    tags: tuple[str, ...],
    sort_order: int,
    pack_group: str,
) -> ContentDescriptorSpec:
    """Build stable cold metadata without using display names as identity."""
    variant = content_id.removeprefix("creature.")
    return ContentDescriptorSpec(
        display_name=display_name,
        description=description,
        tags=tuple(sorted({"creature", *tags})),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key=content_id,
            portrait_key=content_id,
            visual_variant_key=variant,
            ui_group=pack_group,
        ),
        ordering=ContentOrdering(
            sort_group=pack_group,
            sort_order=sort_order,
        ),
    )


def _srd_provenance(
    *,
    display_name: str,
    source_anchor: str,
) -> ContentProvenance:
    """Describe an existing project loadout adapted from an SRD stat block."""
    return ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=source_anchor,
        relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,
        adapted_from_source_id="wotc.srd_5_1_cc",
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            f"Canonicalized existing {display_name} factory; full stat-block "
            "parity remains measured by the SRD source ledger."
        ),
    )


def _original_provenance(display_name: str) -> ContentProvenance:
    """Describe one project-authored combat-role variant."""
    return ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon original content baseline: active bestiary "
            f"{display_name}"
        ),
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes="Exact existing factory mechanics and default loadout.",
    )


def _standard_action_dependencies() -> tuple[ContentDependency, ...]:
    """Declare the common action templates installed by every root."""
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


def _possession_dependencies(
    *,
    equipped: tuple[ContentRecipe, ...] = (),
    inventory: tuple[ContentRecipe, ...] = (),
) -> tuple[ContentDependency, ...]:
    """Declare every exact default-possession recipe used by a root."""
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
            notes="Authored bestiary default possession.",
        )
        for _, (relation, ref) in sorted(relations.items())
    )


def _spell_dependencies(
    *spell_types: type[object],
) -> tuple[ContentDependency, ...]:
    """Declare currently authenticated spells installed by a caster root."""
    declarations = sorted(
        (get_content_declaration(spell_type) for spell_type in spell_types),
        key=lambda row: row.ref.identity_key,
    )
    return tuple(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_SPELL,
            target_ref=declaration.ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Registered as a creature spell action.",
        )
        for declaration in declarations
    )


def _grants_action(
    action_type: type[BaseAction],
) -> ContentDependency:
    """Declare one non-universal action installed by a creature root."""
    return ContentDependency(
        relation=ContentDependencyRelation.GRANTS_ACTION,
        target_ref=ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[action_type].ref,
        phase=ContentDependencyPhase.RUNTIME_REFERENCE,
        notes="Installed by this exact bestiary creature composition.",
    )


_STANDARD_ACTION_DEPENDENCIES = _standard_action_dependencies()


def _wardrobe_item(
    recipe: ContentRecipe,
    slot: BodyPart,
) -> CreaturePossessionGrant:
    return CreaturePossessionGrant(
        recipe=recipe,
        disposition=CreaturePossessionDisposition.EQUIPPED,
        equipment_slot=slot,
    )


_GOBLIN_WARDROBE = (
    _wardrobe_item(DARK_BOOTS_PRESET.recipe, BodyPart.FEET),
)
_GENERIC_CASTER_WARDROBES = MappingProxyType({
    "arcane": (
        _wardrobe_item(HEDGE_WIZARD_ROBE_PRESET.recipe, BodyPart.BODY),
        _wardrobe_item(CLOTH_SHOES_RECIPE, BodyPart.FEET),
    ),
    "dark": (
        _wardrobe_item(DARK_CULTIST_ROBES_PRESET.recipe, BodyPart.BODY),
        _wardrobe_item(DARK_CLOTH_SHOES_PRESET.recipe, BodyPart.FEET),
    ),
    "divine": (
        _wardrobe_item(PRIEST_VESTMENTS_PRESET.recipe, BodyPart.BODY),
        _wardrobe_item(ROPE_SANDALS_PRESET.recipe, BodyPart.FEET),
    ),
    "necromancer": (
        _wardrobe_item(NECROMANCER_ROBE_PRESET.recipe, BodyPart.BODY),
        _wardrobe_item(DARK_CLOTH_SHOES_PRESET.recipe, BodyPart.FEET),
    ),
})
_GOBLIN_CASTER_WARDROBE = (
    _wardrobe_item(HEDGE_WIZARD_ROBE_PRESET.recipe, BodyPart.BODY),
    _wardrobe_item(DARK_CLOTH_SHOES_PRESET.recipe, BodyPart.FEET),
)
BESTIARY_CREATURE_WARDROBE_GRANTS_BY_KEY = MappingProxyType({
    "goblin": _GOBLIN_WARDROBE,
    "goblin_archer": _GOBLIN_WARDROBE,
    **{
        f"generic_caster.{variant}": grants
        for variant, grants in _GENERIC_CASTER_WARDROBES.items()
    },
    "goblin_caster": _GOBLIN_CASTER_WARDROBE,
})


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.goblin",
    version=1,
    parameters=GoblinParameters,
    descriptor=_descriptor(
        content_id="creature.goblin",
        display_name="Goblin",
        description="A small darkvision skirmisher with Nimble Escape.",
        tags=("darkvision", "goblinoid", "small", "srd_adaptation"),
        sort_order=1,
        pack_group="creatures.neurodragon.bestiary",
    ),
    provenance=_srd_provenance(
        display_name="Goblin",
        source_anchor="SRD 5.1 (CC-BY-4.0), p. 315, Monsters A-Z: Goblin",
    ),
    dependencies=(
        *_STANDARD_ACTION_DEPENDENCIES,
        *_possession_dependencies(
            equipped=(
                SCIMITAR_RECIPE,
                SHORTBOW_RECIPE,
                LEATHER_ARMOR_RECIPE,
                WOODEN_SHIELD_RECIPE,
            ),
        ),
        *creature_possession_dependencies(_GOBLIN_WARDROBE),
    ),
)
def _build_goblin(
    raw_context: object,
    parameters: GoblinParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    entity = create_goblin(
        source_id=context.runtime_entity_uuid,
        name=context.display_name,
        position=context.position,
        faction=context.faction,
        weight=parameters.weight,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )
    apply_creature_possessions(
        entity,
        _GOBLIN_WARDROBE,
        possession_mode=context.possession_mode,
    )
    return entity


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.skeleton",
    version=1,
    parameters=SkeletonParameters,
    descriptor=_descriptor(
        content_id="creature.skeleton",
        display_name="Skeleton",
        description="An undead archer and swordsman vulnerable to bludgeoning.",
        tags=("darkvision", "srd_adaptation", "undead"),
        sort_order=2,
        pack_group="creatures.neurodragon.bestiary",
    ),
    provenance=_srd_provenance(
        display_name="Skeleton",
        source_anchor=(
            "SRD 5.1 (CC-BY-4.0), p. 346, Monsters A-Z: Skeleton"
        ),
    ),
    dependencies=(
        *_STANDARD_ACTION_DEPENDENCIES,
        *_possession_dependencies(
            equipped=(
                SHORTSWORD_RECIPE,
                SHORTBOW_RECIPE,
                ARMOR_SCRAPS_RECIPE,
            ),
        ),
    ),
)
def _build_skeleton(
    raw_context: object,
    parameters: SkeletonParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    return create_skeleton(
        source_id=context.runtime_entity_uuid,
        name=context.display_name,
        position=context.position,
        faction=context.faction,
        weight=parameters.weight,
        darkvision=parameters.darkvision,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.goblin_archer",
    version=1,
    parameters=GoblinArcherParameters,
    descriptor=_descriptor(
        content_id="creature.goblin_archer",
        display_name="Goblin Archer",
        description="A dual-wielding goblin ranged skirmisher.",
        tags=("goblinoid", "neurodragon", "ranged", "small"),
        sort_order=10,
        pack_group="creatures.neurodragon.bestiary",
    ),
    provenance=_original_provenance("Goblin Archer"),
    dependencies=(
        *_STANDARD_ACTION_DEPENDENCIES,
        *_possession_dependencies(
            equipped=(
                SHORTBOW_RECIPE,
                SCIMITAR_RECIPE,
                DAGGER_RECIPE,
                LEATHER_ARMOR_RECIPE,
            ),
        ),
        *creature_possession_dependencies(_GOBLIN_WARDROBE),
    ),
)
def _build_goblin_archer(
    raw_context: object,
    parameters: GoblinArcherParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    entity = create_goblin_archer(
        source_id=context.runtime_entity_uuid,
        name=context.display_name,
        position=context.position,
        faction=context.faction,
        weight=parameters.weight,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )
    apply_creature_possessions(
        entity,
        _GOBLIN_WARDROBE,
        possession_mode=context.possession_mode,
    )
    return entity


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.generic_caster",
    version=1,
    parameters=GenericCasterParameters,
    descriptor=_descriptor(
        content_id="creature.generic_caster",
        display_name="Generic Caster",
        description="A classless full caster for authored combat scenarios.",
        tags=("caster", "neurodragon", "spellcasting"),
        sort_order=20,
        pack_group="creatures.neurodragon.bestiary",
    ),
    provenance=_original_provenance("Generic Caster"),
    dependencies=(
        *_STANDARD_ACTION_DEPENDENCIES,
        *_possession_dependencies(
            equipped=(DAGGER_RECIPE,),
            inventory=(
                GREATER_INVISIBILITY_POTION_RECIPE,
                HASTE_POTION_RECIPE,
            ),
        ),
        *creature_possession_dependencies(
            grant
            for grants in _GENERIC_CASTER_WARDROBES.values()
            for grant in grants
        ),
        *_spell_dependencies(
            FireBolt,
            MagicMissile,
            Fireball,
            BurningHands,
            Invisibility,
        ),
    ),
)
def _build_generic_caster(
    raw_context: object,
    parameters: GenericCasterParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    entity = create_caster(
        source_id=context.runtime_entity_uuid,
        name=context.display_name,
        position=context.position,
        faction=context.faction,
        level=parameters.level,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )
    apply_creature_possessions(
        entity,
        _GENERIC_CASTER_WARDROBES[parameters.wardrobe],
        possession_mode=context.possession_mode,
    )
    return entity


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.goblin_caster",
    version=1,
    parameters=GoblinCasterParameters,
    descriptor=_descriptor(
        content_id="creature.goblin_caster",
        display_name="Goblin Caster",
        description=(
            "A small darkvision hedge caster with goblinoid mobility."
        ),
        tags=("caster", "goblinoid", "neurodragon", "small", "spellcasting"),
        sort_order=21,
        pack_group="creatures.neurodragon.bestiary",
    ),
    provenance=_original_provenance("Goblin Caster"),
    dependencies=(
        *_STANDARD_ACTION_DEPENDENCIES,
        *_possession_dependencies(
            equipped=(
                DAGGER_RECIPE,
            ),
            inventory=(
                GREATER_INVISIBILITY_POTION_RECIPE,
                HASTE_POTION_RECIPE,
            ),
        ),
        *creature_possession_dependencies(_GOBLIN_CASTER_WARDROBE),
        *_spell_dependencies(
            FireBolt,
            MagicMissile,
            Fireball,
            BurningHands,
            Invisibility,
        ),
    ),
)
def _build_goblin_caster(
    raw_context: object,
    parameters: GoblinCasterParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    entity = create_goblin_caster(
        source_id=context.runtime_entity_uuid,
        name=context.display_name,
        position=context.position,
        faction=context.faction,
        level=parameters.level,
        weight=parameters.weight,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )
    apply_creature_possessions(
        entity,
        _GOBLIN_CASTER_WARDROBE,
        possession_mode=context.possession_mode,
    )
    return entity


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.skeleton_warrior",
    version=1,
    parameters=SkeletonVariantParameters,
    descriptor=_descriptor(
        content_id="creature.skeleton_warrior",
        display_name="Skeleton Warrior",
        description="A shielded skeleton carrying an acid flask.",
        tags=("defender", "neurodragon", "undead"),
        sort_order=30,
        pack_group="creatures.neurodragon.bestiary",
    ),
    provenance=_original_provenance("Skeleton Warrior"),
    dependencies=(
        *_STANDARD_ACTION_DEPENDENCIES,
        *_possession_dependencies(
            equipped=(
                LONGSWORD_RECIPE,
                WOODEN_SHIELD_RECIPE,
                ARMOR_SCRAPS_RECIPE,
            ),
            inventory=(ACID_FLASK_RECIPE,),
        ),
    ),
)
def _build_skeleton_warrior(
    raw_context: object,
    parameters: SkeletonVariantParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    return create_skeleton_warrior(
        source_id=context.runtime_entity_uuid,
        name=context.display_name,
        position=context.position,
        faction=context.faction,
        weight=parameters.weight,
        darkvision=parameters.darkvision,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.skeleton_archer",
    version=1,
    parameters=SkeletonVariantParameters,
    descriptor=_descriptor(
        content_id="creature.skeleton_archer",
        display_name="Skeleton Archer",
        description="A ranged skeleton that marks targets for allies.",
        tags=("neurodragon", "ranged", "support", "undead"),
        sort_order=40,
        pack_group="creatures.neurodragon.bestiary",
    ),
    provenance=_original_provenance("Skeleton Archer"),
    dependencies=(
        *_STANDARD_ACTION_DEPENDENCIES,
        _grants_action(MarkTargetAction),
        *_possession_dependencies(
            equipped=(
                SHORTBOW_RECIPE,
                DAGGER_RECIPE,
                ARMOR_SCRAPS_RECIPE,
            ),
        ),
    ),
)
def _build_skeleton_archer(
    raw_context: object,
    parameters: SkeletonVariantParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    return create_skeleton_archer(
        source_id=context.runtime_entity_uuid,
        name=context.display_name,
        position=context.position,
        faction=context.faction,
        weight=parameters.weight,
        darkvision=parameters.darkvision,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.skeleton_warlock",
    version=1,
    parameters=SkeletonVariantParameters,
    descriptor=_descriptor(
        content_id="creature.skeleton_warlock",
        display_name="Skeleton Warlock",
        description="An undead spellcaster with an arcane staff.",
        tags=("caster", "neurodragon", "undead"),
        sort_order=50,
        pack_group="creatures.neurodragon.bestiary",
    ),
    provenance=_original_provenance("Skeleton Warlock"),
    dependencies=(
        *_STANDARD_ACTION_DEPENDENCIES,
        *_possession_dependencies(
            equipped=(
                ARCANE_STAFF_RECIPE,
                ARMOR_SCRAPS_RECIPE,
                CROWN_RECIPE,
            ),
            inventory=(INVISIBILITY_SCROLL_RECIPE,),
        ),
        *_spell_dependencies(BurningHands),
    ),
)
def _build_skeleton_warlock(
    raw_context: object,
    parameters: SkeletonVariantParameters,
) -> Entity:
    context = CreatureBuildContext.model_validate(raw_context)
    return create_skeleton_warlock(
        source_id=context.runtime_entity_uuid,
        name=context.display_name,
        position=context.position,
        faction=context.faction,
        weight=parameters.weight,
        darkvision=parameters.darkvision,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )


BESTIARY_CREATURE_DECLARATIONS: tuple[ContentDeclaration, ...] = tuple(
    get_content_declaration(factory)
    for factory in (
        _build_goblin,
        _build_skeleton,
        _build_goblin_archer,
        _build_generic_caster,
        _build_goblin_caster,
        _build_skeleton_warrior,
        _build_skeleton_archer,
        _build_skeleton_warlock,
    )
)
BESTIARY_CREATURE_DECLARATIONS_BY_ID = MappingProxyType({
    declaration.ref.content_id.removeprefix("creature."): declaration
    for declaration in BESTIARY_CREATURE_DECLARATIONS
})
BESTIARY_CREATURE_RECIPES_BY_ID = MappingProxyType({
    creature_id: ContentRecipe.create(
        ref=declaration.ref,
        parameters={},
    )
    for creature_id, declaration
    in BESTIARY_CREATURE_DECLARATIONS_BY_ID.items()
})
