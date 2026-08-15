"""Canonical item definitions for SRD stat-block-specific possessions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from dnd.presentation import EquippedVisualPolicy
from dnd.types.rolls import DieSize
from dnd.blocks.equipment import (
    BodyArmor,
    Weapon,
)
from dnd.core.events.resolution_events import (
    Range,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.item_definitions import (
    ItemDefinition,
    ItemPersistencePolicy,
)
from dnd.core.content.materialization import ItemBuildContext
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    ContentDeclaration,
    get_content_declaration,
)
from dnd.types.equipment import ArmorType, BodyPart, WeaponProperty
from dnd.core.events.resolution_events import (
    RangeType,
)
from dnd.types.damage import DamageType
from dnd.core.values import ModifiableValue
from dnd.items.authored_presentations import (
    authored_item_factory as item_factory,
)


class SrdCreaturePossessionParameters(BaseModel):
    """Stat-block possessions have one exact authored construction."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class _WeaponSpec(BaseModel):
    """Cold authored facts for one exact SRD creature weapon profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    content_id: str
    display_name: str
    creature_name: str
    damage_dice: DieSize
    dice_numbers: int
    damage_type: DamageType
    range_type: RangeType = RangeType.REACH
    normal_range: int = 5
    long_range: int | None = None
    properties: tuple[WeaponProperty, ...] = ()
    visual_item_name: str | None = None
    equipped_visual_policy: EquippedVisualPolicy = (
        EquippedVisualPolicy.VISIBLE
    )
    persistence_policy: ItemPersistencePolicy = (
        ItemPersistencePolicy.POSSESSION
    )


class _NaturalArmorSpec(BaseModel):
    """Cold authored facts for one creature's exact fixed-AC armor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    content_id: str
    creature_name: str
    armor_class: int


_WEAPON_SPECS = (
    _WeaponSpec(
        key="kobold_sling",
        content_id="weapon.creature.kobold_sling",
        display_name="Sling",
        creature_name="Kobold",
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        range_type=RangeType.RANGE,
        normal_range=30,
        long_range=120,
        properties=(WeaponProperty.RANGED,),
        visual_item_name="Sling",
    ),
    _WeaponSpec(
        key="spy_hand_crossbow",
        content_id="weapon.creature.spy_hand_crossbow",
        display_name="Hand Crossbow",
        creature_name="Spy",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        range_type=RangeType.RANGE,
        normal_range=30,
        long_range=120,
        properties=(WeaponProperty.RANGED,),
        visual_item_name="Light Crossbow",
    ),
    _WeaponSpec(
        key="bandit_captain_thrown_dagger",
        content_id="weapon.creature.bandit_captain_thrown_dagger",
        display_name="Thrown Dagger",
        creature_name="Bandit Captain",
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        range_type=RangeType.RANGE,
        normal_range=20,
        long_range=60,
        properties=(WeaponProperty.RANGED,),
        visual_item_name="Dagger",
    ),
    _WeaponSpec(
        key="thrown_javelin",
        content_id="weapon.creature.thrown_javelin",
        display_name="Thrown Javelin",
        creature_name="Orc and Bugbear",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        range_type=RangeType.RANGE,
        normal_range=30,
        long_range=120,
        properties=(WeaponProperty.RANGED,),
        visual_item_name="Javelin",
    ),
    _WeaponSpec(
        key="bugbear_morningstar",
        content_id="weapon.creature.bugbear_morningstar",
        display_name="Morningstar",
        creature_name="Bugbear",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        visual_item_name="Morningstar",
    ),
    _WeaponSpec(
        key="ogre_greatclub",
        content_id="weapon.creature.ogre_greatclub",
        display_name="Greatclub",
        creature_name="Ogre",
        damage_dice=8,
        dice_numbers=2,
        damage_type=DamageType.BLUDGEONING,
        visual_item_name="Club",
    ),
    _WeaponSpec(
        key="ogre_thrown_javelin",
        content_id="weapon.creature.ogre_thrown_javelin",
        display_name="Thrown Javelin",
        creature_name="Ogre",
        damage_dice=6,
        dice_numbers=2,
        damage_type=DamageType.PIERCING,
        range_type=RangeType.RANGE,
        normal_range=30,
        long_range=120,
        properties=(WeaponProperty.RANGED,),
        visual_item_name="Javelin",
    ),
    _WeaponSpec(
        key="wolf_bite",
        content_id="weapon.creature.wolf_bite",
        display_name="Bite",
        creature_name="Wolf",
        damage_dice=4,
        dice_numbers=2,
        damage_type=DamageType.PIERCING,
        equipped_visual_policy=EquippedVisualPolicy.HIDDEN,
        persistence_policy=ItemPersistencePolicy.INTRINSIC,
    ),
    _WeaponSpec(
        key="dire_wolf_bite",
        content_id="weapon.creature.dire_wolf_bite",
        display_name="Bite",
        creature_name="Dire Wolf",
        damage_dice=6,
        dice_numbers=2,
        damage_type=DamageType.PIERCING,
        equipped_visual_policy=EquippedVisualPolicy.HIDDEN,
        persistence_policy=ItemPersistencePolicy.INTRINSIC,
    ),
    _WeaponSpec(
        key="zombie_slam",
        content_id="weapon.creature.zombie_slam",
        display_name="Slam",
        creature_name="Zombie",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        equipped_visual_policy=EquippedVisualPolicy.HIDDEN,
        persistence_policy=ItemPersistencePolicy.INTRINSIC,
    ),
    _WeaponSpec(
        key="ogre_zombie_morningstar",
        content_id="weapon.creature.ogre_zombie_morningstar",
        display_name="Morningstar",
        creature_name="Ogre Zombie",
        damage_dice=8,
        dice_numbers=2,
        damage_type=DamageType.BLUDGEONING,
        visual_item_name="Morningstar",
    ),
    _WeaponSpec(
        key="ghoul_claws",
        content_id="weapon.creature.ghoul_claws",
        display_name="Claws",
        creature_name="Ghoul",
        damage_dice=4,
        dice_numbers=2,
        damage_type=DamageType.SLASHING,
        equipped_visual_policy=EquippedVisualPolicy.HIDDEN,
        persistence_policy=ItemPersistencePolicy.INTRINSIC,
    ),
    _WeaponSpec(
        key="ghoul_bite",
        content_id="weapon.creature.ghoul_bite",
        display_name="Bite",
        creature_name="Ghoul",
        damage_dice=6,
        dice_numbers=2,
        damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.LIGHT,),
        equipped_visual_policy=EquippedVisualPolicy.HIDDEN,
        persistence_policy=ItemPersistencePolicy.INTRINSIC,
    ),
)

_NATURAL_ARMOR_SPECS = (
    _NaturalArmorSpec(
        key="wolf_natural_armor",
        content_id="armor.creature.wolf_natural",
        creature_name="Wolf",
        armor_class=13,
    ),
    _NaturalArmorSpec(
        key="dire_wolf_natural_armor",
        content_id="armor.creature.dire_wolf_natural",
        creature_name="Dire Wolf",
        armor_class=14,
    ),
)


def _provenance(
    *,
    creature_name: str,
    item_name: str,
) -> ContentProvenance:
    return ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=(
            f"SRD 5.1 (CC-BY-4.0), {creature_name} stat block: {item_name}"
        ),
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Exact runtime profile retained from the reviewed SRD roster "
            "implementation."
        ),
    )


def _declare_weapon(
    spec: _WeaponSpec,
    *,
    sort_order: int,
) -> tuple[ContentDeclaration, ContentRecipe]:
    @item_factory(
        pack_id="content.srd_5_1_cc",
        content_id=spec.content_id,
        version=1,
        parameters=SrdCreaturePossessionParameters,
        descriptor=ContentDescriptorSpec(
            display_name=spec.display_name,
            description=f"SRD-derived {spec.display_name.lower()} attack.",
            tags=("creature_possession", "srd", "weapon"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                icon_key=f"creature_possession.{spec.key}",
                sprite_key=spec.visual_item_name,
                ui_group="creature_possessions.weapons",
            ),
            ordering=ContentOrdering(
                sort_group="creature_possessions.weapons",
                sort_order=sort_order,
            ),
        ),
        provenance=_provenance(
            creature_name=spec.creature_name,
            item_name=spec.display_name,
        ),
        item_definition=ItemDefinition(
            persistence_policy=spec.persistence_policy,
        ),
    )
    def build_weapon(
        raw_context: object,
        parameters: SrdCreaturePossessionParameters,
    ) -> Weapon:
        _ = parameters
        context = ItemBuildContext.model_validate(raw_context)
        return Weapon(
            source_entity_uuid=context.source_entity_uuid,
            content_ref=context.requested_ref,
            name=spec.display_name,
            description=f"SRD-derived {spec.display_name.lower()} attack.",
            damage_dice=spec.damage_dice,
            dice_numbers=spec.dice_numbers,
            damage_type=spec.damage_type,
            properties=list(spec.properties),
            range=Range(
                type=spec.range_type,
                normal=spec.normal_range,
                long=spec.long_range,
            ),
            attack_bonus=ModifiableValue.create(
                source_entity_uuid=context.source_entity_uuid,
                base_value=0,
                value_name="Attack Bonus",
            ),
            extra_damage_dices=[],
            extra_damage_dices_numbers=[],
            extra_damage_bonus=[],
            extra_damage_type=[],
            visual_item_name=spec.visual_item_name,
            equipped_visual_policy=spec.equipped_visual_policy,
        )

    declaration = get_content_declaration(build_weapon)
    return declaration, ContentRecipe.create(
        ref=declaration.ref,
        parameters={},
    )


def _declare_natural_armor(
    spec: _NaturalArmorSpec,
    *,
    sort_order: int,
) -> tuple[ContentDeclaration, ContentRecipe]:
    @item_factory(
        pack_id="content.srd_5_1_cc",
        content_id=spec.content_id,
        version=1,
        parameters=SrdCreaturePossessionParameters,
        descriptor=ContentDescriptorSpec(
            display_name="Natural Armor",
            description=f"Fixed AC {spec.armor_class} natural protection.",
            tags=("armor", "creature_possession", "intrinsic", "srd"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                icon_key=f"creature_possession.{spec.key}",
                ui_group="creature_possessions.armor",
            ),
            ordering=ContentOrdering(
                sort_group="creature_possessions.armor",
                sort_order=sort_order,
            ),
        ),
        provenance=_provenance(
            creature_name=spec.creature_name,
            item_name="Natural Armor",
        ),
        item_definition=ItemDefinition(
            persistence_policy=ItemPersistencePolicy.INTRINSIC,
        ),
    )
    def build_natural_armor(
        raw_context: object,
        parameters: SrdCreaturePossessionParameters,
    ) -> BodyArmor:
        _ = parameters
        context = ItemBuildContext.model_validate(raw_context)
        return BodyArmor(
            source_entity_uuid=context.source_entity_uuid,
            content_ref=context.requested_ref,
            name="Natural Armor",
            description=f"Fixed AC {spec.armor_class} natural protection.",
            type=ArmorType.LIGHT,
            body_part=BodyPart.BODY,
            ac=ModifiableValue.create(
                source_entity_uuid=context.source_entity_uuid,
                base_value=spec.armor_class,
                value_name="Armor Class",
            ),
            max_dex_bonus=ModifiableValue.create(
                source_entity_uuid=context.source_entity_uuid,
                base_value=0,
                value_name="Max Dex Bonus",
            ),
            equipped_visual_policy=EquippedVisualPolicy.HIDDEN,
        )

    declaration = get_content_declaration(build_natural_armor)
    return declaration, ContentRecipe.create(
        ref=declaration.ref,
        parameters={},
    )


_WEAPON_DECLARATION_RECIPE_ROWS = tuple(
    _declare_weapon(spec, sort_order=index * 10)
    for index, spec in enumerate(_WEAPON_SPECS, start=1)
)
_ARMOR_DECLARATION_RECIPE_ROWS = tuple(
    _declare_natural_armor(spec, sort_order=index * 10)
    for index, spec in enumerate(_NATURAL_ARMOR_SPECS, start=1)
)

SRD_CREATURE_POSSESSION_ITEM_DECLARATIONS = tuple(
    declaration
    for declaration, _ in (
        *_WEAPON_DECLARATION_RECIPE_ROWS,
        *_ARMOR_DECLARATION_RECIPE_ROWS,
    )
)
SRD_CREATURE_POSSESSION_RECIPES = {
    spec.key: recipe
    for spec, (_, recipe) in zip(
        (*_WEAPON_SPECS, *_NATURAL_ARMOR_SPECS),
        (*_WEAPON_DECLARATION_RECIPE_ROWS, *_ARMOR_DECLARATION_RECIPE_ROWS),
        strict=True,
    )
}
