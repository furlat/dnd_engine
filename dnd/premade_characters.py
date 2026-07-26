"""Canonical content declarations for the three approved premade characters."""

from __future__ import annotations

from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from dnd.blocks.equipment import Armor, Weapon
import dnd.classes.barbarian as barbarian
import dnd.classes.fighter as fighter
import dnd.classes.rage as rage
import dnd.classes.sorcerer as sorcerer
from dnd.classes.barbarian_factory import (
    BarbarianConfig,
    PrimalPathChoice,
    create_barbarian,
)
from dnd.classes.fighter_factory import FighterConfig, create_fighter
from dnd.classes.sorcerer_factory import SorcererConfig, create_sorcerer
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.content_system.item_runtime_materialization import (
    materialize_item_from_installed_runtime,
)
from dnd.core.base_conditions import BaseCondition
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
from dnd.core.content.materialization import (
    CreatureBuildContext,
    CreaturePossessionMode,
)
from dnd.core.content.premade_characters import (
    PremadeCharacterTemplate,
    StarterHoldingTemplate,
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
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.entity import Entity
from dnd.items.armors import (
    CHAIN_MAIL_RECIPE,
    CLOTH_SHOES_RECIPE,
    LEATHER_ARMOR_RECIPE,
    LEATHER_BOOTS_RECIPE,
    SHIELD_RECIPE,
)
from dnd.items.apparel_presets import (
    BLUE_CLOTH_SHOES_PRESET,
    BROWN_BOOTS_PRESET,
    PIT_FIGHTER_WRAP_PRESET,
    RED_CLOTH_SHOES_PRESET,
    RED_MAGE_ROBE_PRESET,
    RED_WIZARD_HAT_PRESET,
    STEEL_HELMET_PRESET,
    WIZARD_ROBE_PRESET,
)
from dnd.items.consumables import HASTE_POTION_RECIPE, HEALING_POTION_RECIPE
from dnd.items.torches import TORCH_RECIPE, Torch
from dnd.items.weapons import (
    DAGGER_RECIPE,
    GREATAXE_RECIPE,
    HANDAXE_RECIPE,
    JAVELIN_RECIPE,
    LONGBOW_RECIPE,
    LONGSWORD_RECIPE,
    QUARTERSTAFF_RECIPE,
)


BARBARIAN_L5_BERSERKER_TORCH_PREMADE_ID = (
    "hero.barbarian_l5_berserker_torch"
)
FIGHTER_L5_SHIELD_TORCH_PREMADE_ID = "hero.fighter_l5_shield_torch"
SORCERER_L5_STANDARD_TORCH_PREMADE_ID = (
    "hero.sorcerer_l5_standard_torch"
)

PREMADE_LEVEL_5_SORCERER_SPELLS = (
    "Fire Bolt",
    "Ray of Frost",
    "Magic Missile",
    "Burning Hands",
    "Thunderwave",
    "Scorching Ray",
    "Hold Person",
    "Shatter",
    "Invisibility",
    "Fireball",
    "Lightning Bolt",
)


class PremadeCreatureParameters(BaseModel):
    """The approved premade roots have no client-selectable build parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)


_FIGHTER_EQUIPPED_BOOTS_RECIPE = BROWN_BOOTS_PRESET.recipe
_FIGHTER_SPARE_HELMET_RECIPE = STEEL_HELMET_PRESET.recipe
_BARBARIAN_COSTUME_RECIPE = PIT_FIGHTER_WRAP_PRESET.recipe
_SORCERER_EQUIPPED_ROBES_RECIPE = RED_MAGE_ROBE_PRESET.recipe
_SORCERER_EQUIPPED_SHOES_RECIPE = RED_CLOTH_SHOES_PRESET.recipe
_SORCERER_SPARE_ROBES_RECIPE = WIZARD_ROBE_PRESET.recipe
_SORCERER_SPARE_SHOES_RECIPE = BLUE_CLOTH_SHOES_PRESET.recipe
_SORCERER_SPARE_HAT_RECIPE = RED_WIZARD_HAT_PRESET.recipe


BARBARIAN_L5_BERSERKER_TORCH_STARTER_HOLDINGS = (
    StarterHoldingTemplate(
        recipe=GREATAXE_RECIPE,
        equipped_slot=WeaponSlot.MELEE_MAIN,
    ),
    StarterHoldingTemplate(recipe=HASTE_POTION_RECIPE),
    StarterHoldingTemplate(recipe=HEALING_POTION_RECIPE, quantity=2),
    StarterHoldingTemplate(recipe=HANDAXE_RECIPE),
    StarterHoldingTemplate(recipe=JAVELIN_RECIPE),
    StarterHoldingTemplate(recipe=DAGGER_RECIPE),
    StarterHoldingTemplate(recipe=LONGSWORD_RECIPE),
    StarterHoldingTemplate(recipe=SHIELD_RECIPE),
    StarterHoldingTemplate(
        recipe=_BARBARIAN_COSTUME_RECIPE,
        equipped_slot=BodyPart.BODY,
    ),
    StarterHoldingTemplate(
        recipe=LEATHER_BOOTS_RECIPE,
        equipped_slot=BodyPart.FEET,
    ),
    StarterHoldingTemplate(recipe=TORCH_RECIPE),
)

FIGHTER_L5_SHIELD_TORCH_STARTER_HOLDINGS = (
    StarterHoldingTemplate(
        recipe=CHAIN_MAIL_RECIPE,
        equipped_slot=BodyPart.BODY,
    ),
    StarterHoldingTemplate(
        recipe=LONGSWORD_RECIPE,
        equipped_slot=WeaponSlot.MELEE_MAIN,
    ),
    StarterHoldingTemplate(
        recipe=SHIELD_RECIPE,
        equipped_slot=WeaponSlot.MELEE_OFF,
    ),
    StarterHoldingTemplate(
        recipe=_FIGHTER_EQUIPPED_BOOTS_RECIPE,
        equipped_slot=BodyPart.FEET,
    ),
    StarterHoldingTemplate(recipe=HASTE_POTION_RECIPE),
    StarterHoldingTemplate(recipe=HEALING_POTION_RECIPE, quantity=2),
    StarterHoldingTemplate(recipe=CLOTH_SHOES_RECIPE),
    StarterHoldingTemplate(recipe=_FIGHTER_SPARE_HELMET_RECIPE),
    StarterHoldingTemplate(recipe=HANDAXE_RECIPE),
    StarterHoldingTemplate(recipe=JAVELIN_RECIPE),
    StarterHoldingTemplate(recipe=DAGGER_RECIPE),
    StarterHoldingTemplate(recipe=LEATHER_ARMOR_RECIPE),
    StarterHoldingTemplate(
        recipe=LONGBOW_RECIPE,
        equipped_slot=WeaponSlot.RANGED_MAIN,
    ),
    StarterHoldingTemplate(recipe=TORCH_RECIPE),
)

SORCERER_L5_STANDARD_TORCH_STARTER_HOLDINGS = (
    StarterHoldingTemplate(
        recipe=DAGGER_RECIPE,
        equipped_slot=WeaponSlot.MELEE_MAIN,
    ),
    StarterHoldingTemplate(
        recipe=_SORCERER_EQUIPPED_ROBES_RECIPE,
        equipped_slot=BodyPart.BODY,
    ),
    StarterHoldingTemplate(
        recipe=_SORCERER_EQUIPPED_SHOES_RECIPE,
        equipped_slot=BodyPart.FEET,
    ),
    StarterHoldingTemplate(recipe=HASTE_POTION_RECIPE),
    StarterHoldingTemplate(recipe=HEALING_POTION_RECIPE, quantity=2),
    StarterHoldingTemplate(recipe=_SORCERER_SPARE_ROBES_RECIPE),
    StarterHoldingTemplate(recipe=_SORCERER_SPARE_SHOES_RECIPE),
    StarterHoldingTemplate(recipe=_SORCERER_SPARE_HAT_RECIPE),
    StarterHoldingTemplate(recipe=QUARTERSTAFF_RECIPE),
    StarterHoldingTemplate(recipe=TORCH_RECIPE),
)


def _descriptor(
    *,
    display_name: str,
    class_tag: str,
    visual_variant_key: str,
    sort_order: int,
) -> ContentDescriptorSpec:
    """Build public catalog metadata for one approved player-capable root."""
    return ContentDescriptorSpec(
        display_name=display_name,
        description=(
            "Approved level-five player-capable premade character structure."
        ),
        tags=(
            class_tag,
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
    """Return reviewed project provenance for a premade composition."""
    return ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon original content baseline: approved premade "
            f"{display_name}"
        ),
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Exact existing level-five class build and starter loadout "
            "composition."
        ),
    )


def _holding_dependencies(
    holdings: tuple[StarterHoldingTemplate, ...],
) -> tuple[ContentDependency, ...]:
    """Declare every item definition constructed by a full premade build."""
    by_identity: dict[str, StarterHoldingTemplate] = {}
    equipped_identities: set[str] = set()
    for holding in holdings:
        identity = holding.recipe.ref.identity_key
        by_identity.setdefault(identity, holding)
        if holding.equipped_slot is not None:
            equipped_identities.add(identity)
    return tuple(
        ContentDependency(
            relation=(
                ContentDependencyRelation.EQUIPS_ITEM
                if identity in equipped_identities
                else ContentDependencyRelation.CREATES_ITEM
            ),
            target_ref=by_identity[identity].recipe.ref,
            phase=ContentDependencyPhase.CONSTRUCTION,
            notes="Approved premade default-possession dependency.",
        )
        for identity in sorted(by_identity)
    )


def _feature_dependencies(
    *condition_types: type[BaseCondition],
) -> tuple[ContentDependency, ...]:
    """Declare root-owned feature conditions installed by a premade."""
    return tuple(
        ContentDependency(
            relation=ContentDependencyRelation.APPLIES_CONDITION,
            target_ref=CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
                condition_type
            ].ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Installed by this exact premade character composition.",
        )
        for condition_type in condition_types
    )


def _equip_addition(
    entity: Entity,
    recipe: ContentRecipe,
    slot: BodyPart | WeaponSlot,
) -> None:
    """Materialize and equip one catalog-authored premade augmentation."""
    item = materialize_item_from_installed_runtime(
        recipe,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=(Weapon if isinstance(slot, WeaponSlot) else Armor),
    )
    if not entity.equipment.equip(item, slot):
        raise ValueError(
            f"Premade equipment rejected {recipe.ref.identity_key} in "
            f"{slot.value}",
        )


def _grant_lit_torch(entity: Entity) -> None:
    """Grant the catalog torch and reproduce its ephemeral opening light."""
    torch = materialize_item_from_installed_runtime(
        TORCH_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Torch,
    )
    if not entity.loot_item(torch):
        raise ValueError("Premade inventory rejected the portable torch")
    torch.ignite(entity.uuid)


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.premade.barbarian_l5_berserker_torch",
    version=1,
    parameters=PremadeCreatureParameters,
    descriptor=_descriptor(
        display_name="Level 5 Berserker With Torch",
        class_tag="barbarian",
        visual_variant_key="barbarian_l5_berserker_torch",
        sort_order=10,
    ),
    provenance=_provenance("Level 5 Berserker With Torch"),
    dependencies=(
        *_holding_dependencies(
            BARBARIAN_L5_BERSERKER_TORCH_STARTER_HOLDINGS,
        ),
        *_feature_dependencies(
            barbarian.RecklessAttackFeature,
            fighter.ExtraAttackFeature,
            rage.FrenzyFeature,
            rage.RageFeature,
        ),
    ),
)
def _build_barbarian_l5_berserker_torch(
    raw_context: object,
    parameters: PremadeCreatureParameters,
) -> Entity:
    """Construct the exact approved Berserker body and optional loadout."""
    _ = parameters
    context = CreatureBuildContext.model_validate(raw_context)
    entity = create_barbarian(
        BarbarianConfig(
            level=5,
            name=context.display_name,
            position=context.position,
            faction=context.faction,
            primal_path=PrimalPathChoice.BERSERKER,
            equipment_preset="greataxe",
            asi_4=[("strength", 2)],
        ),
        source_id=context.runtime_entity_uuid,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )
    if (
        context.possession_mode
        == CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
    ):
        _equip_addition(
            entity,
            _BARBARIAN_COSTUME_RECIPE,
            BodyPart.BODY,
        )
        _equip_addition(entity, LEATHER_BOOTS_RECIPE, BodyPart.FEET)
        _grant_lit_torch(entity)
    return entity


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.premade.fighter_l5_shield_torch",
    version=1,
    parameters=PremadeCreatureParameters,
    descriptor=_descriptor(
        display_name="Level 5 Shield Fighter With Longbow And Torch",
        class_tag="fighter",
        visual_variant_key="fighter_l5_shield_torch",
        sort_order=20,
    ),
    provenance=_provenance(
        "Level 5 Shield Fighter With Longbow And Torch",
    ),
    dependencies=(
        *_holding_dependencies(
            FIGHTER_L5_SHIELD_TORCH_STARTER_HOLDINGS,
        ),
        *_feature_dependencies(
            fighter.ActionSurgeFeature,
            fighter.ExtraAttackFeature,
            fighter.SecondWindFeature,
        ),
    ),
)
def _build_fighter_l5_shield_torch(
    raw_context: object,
    parameters: PremadeCreatureParameters,
) -> Entity:
    """Construct the exact approved shield Fighter and optional loadout."""
    _ = parameters
    context = CreatureBuildContext.model_validate(raw_context)
    entity = create_fighter(
        FighterConfig(
            level=5,
            name=context.display_name,
            position=context.position,
            faction=context.faction,
            fighting_style="dueling",
            equipment_preset="sword_shield",
            asi_4=[("strength", 2)],
        ),
        source_id=context.runtime_entity_uuid,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )
    if (
        context.possession_mode
        == CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
    ):
        _equip_addition(
            entity,
            LONGBOW_RECIPE,
            WeaponSlot.RANGED_MAIN,
        )
        _grant_lit_torch(entity)
    return entity


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.premade.sorcerer_l5_standard_torch",
    version=1,
    parameters=PremadeCreatureParameters,
    descriptor=_descriptor(
        display_name="Level 5 Sorcerer With Torch",
        class_tag="sorcerer",
        visual_variant_key="sorcerer_l5_standard_torch",
        sort_order=30,
    ),
    provenance=_provenance("Level 5 Sorcerer With Torch"),
    dependencies=(
        *_holding_dependencies(
            SORCERER_L5_STANDARD_TORCH_STARTER_HOLDINGS,
        ),
        *_feature_dependencies(
            sorcerer.SorceryPointsFeature,
        ),
    ),
)
def _build_sorcerer_l5_standard_torch(
    raw_context: object,
    parameters: PremadeCreatureParameters,
) -> Entity:
    """Construct the exact approved Sorcerer body and optional loadout."""
    _ = parameters
    context = CreatureBuildContext.model_validate(raw_context)
    entity = create_sorcerer(
        SorcererConfig(
            level=5,
            name=context.display_name,
            position=context.position,
            faction=context.faction,
            metamagic_choices=["quickened", "twinned"],
            spell_names=list(PREMADE_LEVEL_5_SORCERER_SPELLS),
            equipment_preset="dagger",
            asi_4=[("charisma", 2)],
        ),
        source_id=context.runtime_entity_uuid,
        possession_mode=context.possession_mode,
        content_ref=context.requested_ref,
    )
    if (
        context.possession_mode
        == CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
    ):
        _grant_lit_torch(entity)
    return entity


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

PREMADE_CHARACTER_TEMPLATES = MappingProxyType(
    {
        BARBARIAN_L5_BERSERKER_TORCH_PREMADE_ID: (
            PremadeCharacterTemplate.create(
                premade_id=BARBARIAN_L5_BERSERKER_TORCH_PREMADE_ID,
                creature_recipe=BARBARIAN_L5_BERSERKER_TORCH_RECIPE,
                starter_holdings=(
                    BARBARIAN_L5_BERSERKER_TORCH_STARTER_HOLDINGS
                ),
            )
        ),
        FIGHTER_L5_SHIELD_TORCH_PREMADE_ID: (
            PremadeCharacterTemplate.create(
                premade_id=FIGHTER_L5_SHIELD_TORCH_PREMADE_ID,
                creature_recipe=FIGHTER_L5_SHIELD_TORCH_RECIPE,
                starter_holdings=FIGHTER_L5_SHIELD_TORCH_STARTER_HOLDINGS,
            )
        ),
        SORCERER_L5_STANDARD_TORCH_PREMADE_ID: (
            PremadeCharacterTemplate.create(
                premade_id=SORCERER_L5_STANDARD_TORCH_PREMADE_ID,
                creature_recipe=SORCERER_L5_STANDARD_TORCH_RECIPE,
                starter_holdings=SORCERER_L5_STANDARD_TORCH_STARTER_HOLDINGS,
            )
        ),
    },
)


__all__ = [
    "BARBARIAN_L5_BERSERKER_TORCH_DECLARATION",
    "BARBARIAN_L5_BERSERKER_TORCH_PREMADE_ID",
    "BARBARIAN_L5_BERSERKER_TORCH_RECIPE",
    "BARBARIAN_L5_BERSERKER_TORCH_STARTER_HOLDINGS",
    "FIGHTER_L5_SHIELD_TORCH_DECLARATION",
    "FIGHTER_L5_SHIELD_TORCH_PREMADE_ID",
    "FIGHTER_L5_SHIELD_TORCH_RECIPE",
    "FIGHTER_L5_SHIELD_TORCH_STARTER_HOLDINGS",
    "NEURODRAGON_PREMADE_CREATURE_DECLARATIONS",
    "PREMADE_CHARACTER_TEMPLATES",
    "PREMADE_LEVEL_5_SORCERER_SPELLS",
    "PremadeCreatureParameters",
    "SORCERER_L5_STANDARD_TORCH_DECLARATION",
    "SORCERER_L5_STANDARD_TORCH_PREMADE_ID",
    "SORCERER_L5_STANDARD_TORCH_RECIPE",
    "SORCERER_L5_STANDARD_TORCH_STARTER_HOLDINGS",
]
