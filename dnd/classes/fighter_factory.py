"""
Fighter Factory - Create Fighter characters at any level (1-20).

Implements BG3-style configuration with base ability scores, level 1 bonuses,
and ASI choices at appropriate levels. All features are automatically applied
based on level.
"""

from typing import Optional, List, Tuple, Dict, Literal, Type
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator, model_validator

from dnd.entity import Entity, EntityConfig
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.saving_throws import SavingThrowConfig, SavingThrowSetConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import (
    BodyArmor,
    Boots,
    EquipmentConfig,
    Helmet,
    Shield,
    Weapon,
)
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_runtime_materialization import (
    materialize_item_from_installed_runtime,
)
from dnd.core.content.identities import ContentRef
from dnd.core.content.materialization import CreaturePossessionMode
from dnd.core.equipment_types import WeaponSlot
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.core.events import AbilityName
from dnd.core.base_conditions import BaseCondition

from dnd.items.armors import (
    CHAIN_MAIL_RECIPE,
    CLOTH_SHOES_RECIPE,
    LEATHER_ARMOR_RECIPE,
    SHIELD_RECIPE,
    STUDDED_LEATHER_RECIPE,
)
from dnd.items.apparel_presets import (
    BROWN_BOOTS_PRESET,
    STEEL_HELMET_PRESET,
)
from dnd.items.consumables import (
    HASTE_POTION_RECIPE,
    HEALING_POTION_RECIPE,
)
from dnd.items.weapons import (
    DAGGER_RECIPE,
    GREATSWORD_RECIPE,
    HANDAXE_RECIPE,
    JAVELIN_RECIPE,
    LONGBOW_RECIPE,
    LONGSWORD_RECIPE,
    SHORTSWORD_RECIPE,
)

from dnd.classes.fighter import (
    FightingStyleArchery,
    FightingStyleDefense,
    FightingStyleDueling,
    GreatWeaponFighting,
    FightingStyleProtection,
    FightingStyleTwoWeaponFighting,
    SecondWindFeature,
    ActionSurgeFeature,
    ImprovedCritical,
    SuperiorCritical,
    ExtraAttackFeature,
    Indomitable,
    Survivor,
)


def get_proficiency_bonus(level: int) -> int:
    """Returns proficiency bonus for character level."""
    return 2 + (level - 1) // 4


def get_extra_attacks(level: int) -> int:
    """0 at L1-4, 1 at L5-10, 2 at L11-19, 3 at L20."""
    if level < 5:
        return 0
    if level < 11:
        return 1
    if level < 20:
        return 2
    return 3


def get_action_surge_uses(level: int) -> int:
    """1 at L2-16, 2 at L17+."""
    if level < 2:
        return 0
    if level < 17:
        return 1
    return 2


def get_indomitable_uses(level: int) -> int:
    """1 at L9-12, 2 at L13-16, 3 at L17+."""
    if level < 9:
        return 0
    if level < 13:
        return 1
    if level < 17:
        return 2
    return 3

FightingStyleChoice = Literal[
    "archery", "defense", "dueling",
    "great_weapon", "protection", "two_weapon"
]

FIGHTING_STYLE_MAP: Dict[FightingStyleChoice, Type[BaseCondition]] = {
    "archery": FightingStyleArchery,
    "defense": FightingStyleDefense,
    "dueling": FightingStyleDueling,
    "great_weapon": GreatWeaponFighting,
    "protection": FightingStyleProtection,
    "two_weapon": FightingStyleTwoWeaponFighting,
}

EquipmentPreset = Literal["sword_shield", "greatsword", "dual_wield", "archery"]

EQUIPMENT_PRESETS = {
    "sword_shield": {
        "melee_main": "longsword",
        "melee_off": "shield",
        "armor": "chain_mail",
    },
    "greatsword": {
        "melee_main": "greatsword",
        "melee_off": None,
        "armor": "chain_mail",
    },
    "dual_wield": {
        "melee_main": "shortsword",
        "melee_off": "shortsword",
        "armor": "chain_mail",
    },
    "archery": {
        "melee_main": "shortsword",
        "ranged_main": "longbow",
        "armor": "studded_leather",
    },
}

_FIGHTER_LEATHER_BOOTS_RECIPE = BROWN_BOOTS_PRESET.recipe
_FIGHTER_IRON_HELMET_RECIPE = STEEL_HELMET_PRESET.recipe


class FighterConfig(BaseModel):
    """Configuration for creating a Fighter at a specific level.

    Attributes:
        level: Fighter level used to gate features, resources, and required ASI choices.
        name: Display name for the created fighter entity.
        position: Initial grid position for the created fighter entity.
        faction: Faction identifier. None = enemy to everyone.
        base_strength: Base Strength score before level-one bonuses and ASI choices.
        base_dexterity: Base Dexterity score before level-one bonuses and ASI choices.
        base_constitution: Base Constitution score before level-one bonuses and ASI choices.
        base_intelligence: Base Intelligence score before level-one bonuses and ASI choices.
        base_wisdom: Base Wisdom score before level-one bonuses and ASI choices.
        base_charisma: Base Charisma score before level-one bonuses and ASI choices.
        bonus_plus_2: Ability that receives the level-one +2 bonus.
        bonus_plus_1: Ability that receives the level-one +1 bonus.
        fighting_style: Primary Fighter fighting style applied at level one.
        second_fighting_style: Champion level-ten fighting style; must differ from the primary style.
        asi_4: Ability score improvements selected at Fighter level four.
        asi_6: Ability score improvements selected at Fighter level six.
        asi_8: Ability score improvements selected at Fighter level eight.
        asi_12: Ability score improvements selected at Fighter level twelve.
        asi_14: Ability score improvements selected at Fighter level fourteen.
        asi_16: Ability score improvements selected at Fighter level sixteen.
        asi_19: Ability score improvements selected at Fighter level nineteen.
        equipment_preset: Starter equipment preset equipped by the Fighter factory.
    """

    level: int = Field(
        ge=1,
        le=20,
        default=1,
        description="Fighter level used to gate features, resources, and required ASI choices.",
    )
    name: str = Field(default="Fighter", description="Display name for the created fighter entity.")
    position: Tuple[int, int] = Field(
        default=(0, 0),
        description="Initial grid position for the created fighter entity.",
    )
    faction: Optional[str] = Field(default=None, description="Faction identifier. None = enemy to everyone")

    base_strength: int = Field(
        default=15,
        ge=8,
        le=15,
        description="Base Strength score before level-one bonuses and ASI choices.",
    )
    base_dexterity: int = Field(
        default=14,
        ge=8,
        le=15,
        description="Base Dexterity score before level-one bonuses and ASI choices.",
    )
    base_constitution: int = Field(
        default=13,
        ge=8,
        le=15,
        description="Base Constitution score before level-one bonuses and ASI choices.",
    )
    base_intelligence: int = Field(
        default=10,
        ge=8,
        le=15,
        description="Base Intelligence score before level-one bonuses and ASI choices.",
    )
    base_wisdom: int = Field(
        default=12,
        ge=8,
        le=15,
        description="Base Wisdom score before level-one bonuses and ASI choices.",
    )
    base_charisma: int = Field(
        default=8,
        ge=8,
        le=15,
        description="Base Charisma score before level-one bonuses and ASI choices.",
    )

    bonus_plus_2: AbilityName = Field(
        default="strength",
        description="Ability that receives the level-one +2 bonus.",
    )
    bonus_plus_1: AbilityName = Field(
        default="constitution",
        description="Ability that receives the level-one +1 bonus.",
    )

    fighting_style: FightingStyleChoice = Field(
        default="defense",
        description="Primary Fighter fighting style applied at level one.",
    )
    second_fighting_style: Optional[FightingStyleChoice] = Field(
        default=None,
        description="Champion level-ten fighting style; must differ from the primary style.",
    )

    asi_4: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Fighter level four.",
    )
    asi_6: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Fighter level six.",
    )
    asi_8: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Fighter level eight.",
    )
    asi_12: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Fighter level twelve.",
    )
    asi_14: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Fighter level fourteen.",
    )
    asi_16: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Fighter level sixteen.",
    )
    asi_19: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Fighter level nineteen.",
    )

    equipment_preset: EquipmentPreset = Field(
        default="sword_shield",
        description="Starter equipment preset equipped by the Fighter factory.",
    )

    @field_validator("bonus_plus_1")
    @classmethod
    def validate_different_bonuses(cls, v: AbilityName, info) -> AbilityName:
        """Ensure +2 and +1 go to different abilities."""
        bonus_plus_2 = info.data.get("bonus_plus_2")
        if bonus_plus_2 is not None and v == bonus_plus_2:
            raise ValueError("bonus_plus_2 and bonus_plus_1 must be different abilities")
        return v

    @field_validator("second_fighting_style")
    @classmethod
    def validate_second_style(cls, v: Optional[FightingStyleChoice], info) -> Optional[FightingStyleChoice]:
        if v is not None:
            level = info.data.get("level", 1)
            if level < 10:
                raise ValueError("Second fighting style requires level 10+")
            first = info.data.get("fighting_style")
            if v == first:
                raise ValueError("Cannot take same fighting style twice")
        return v

    @model_validator(mode="after")
    def validate_asis_for_level(self):
        """Validate that ASIs are specified for reached levels."""
        asi_levels = {
            4: self.asi_4,
            6: self.asi_6,
            8: self.asi_8,
            12: self.asi_12,
            14: self.asi_14,
            16: self.asi_16,
            19: self.asi_19
        }

        for lvl, asi in asi_levels.items():
            if self.level >= lvl and asi is None:
                raise ValueError(f"Level {self.level} requires asi_{lvl} to be specified")
            if self.level < lvl and asi is not None:
                raise ValueError(f"asi_{lvl} specified but level is only {self.level}")
            if asi is not None:
                total = sum(inc[1] for inc in asi)
                if total != 2:
                    raise ValueError(f"asi_{lvl} must total +2, got {total}")

        return self


def calculate_final_ability_scores(config: FighterConfig) -> Dict[AbilityName, int]:
    """
    Calculate final scores: base + L1 bonuses + all ASIs.

    Example for L5 fighter:
    - base_strength=15, bonus_plus_2="strength", asi_4=[("strength", 2)]
    - Final STR = 15 + 2 + 2 = 19
    """
    scores: Dict[AbilityName, int] = {
        "strength": config.base_strength,
        "dexterity": config.base_dexterity,
        "constitution": config.base_constitution,
        "intelligence": config.base_intelligence,
        "wisdom": config.base_wisdom,
        "charisma": config.base_charisma,
    }

    scores[config.bonus_plus_2] += 2
    scores[config.bonus_plus_1] += 1

    asi_map = {
        4: config.asi_4,
        6: config.asi_6,
        8: config.asi_8,
        12: config.asi_12,
        14: config.asi_14,
        16: config.asi_16,
        19: config.asi_19
    }
    for lvl, asi in asi_map.items():
        if config.level >= lvl and asi:
            for ability, bonus in asi:
                scores[ability] += bonus

    return {k: min(v, 20) for k, v in scores.items()}


def apply_equipment(entity: Entity, preset: EquipmentPreset):
    """Apply equipment based on preset."""
    preset_config = EQUIPMENT_PRESETS[preset]

    armor_name = preset_config.get("armor")
    if armor_name == "chain_mail":
        armor = materialize_item_from_installed_runtime(
            CHAIN_MAIL_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=BodyArmor,
        )
        entity.equipment.equip(armor)
    elif armor_name == "studded_leather":
        armor = materialize_item_from_installed_runtime(
            STUDDED_LEATHER_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=BodyArmor,
        )
        entity.equipment.equip(armor)

    melee_main = preset_config.get("melee_main")
    if melee_main == "longsword":
        weapon = materialize_item_from_installed_runtime(
            LONGSWORD_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        )
        entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    elif melee_main == "greatsword":
        weapon = materialize_item_from_installed_runtime(
            GREATSWORD_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        )
        entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    elif melee_main == "shortsword":
        weapon = materialize_item_from_installed_runtime(
            SHORTSWORD_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        )
        entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)

    melee_off = preset_config.get("melee_off")
    if melee_off == "shield":
        shield = materialize_item_from_installed_runtime(
            SHIELD_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Shield,
        )
        entity.equipment.equip(shield, WeaponSlot.MELEE_OFF)
    elif melee_off == "shortsword":
        weapon = materialize_item_from_installed_runtime(
            SHORTSWORD_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        )
        entity.equipment.equip(weapon, WeaponSlot.MELEE_OFF)

    ranged_main = preset_config.get("ranged_main")
    if ranged_main == "longbow":
        weapon = materialize_item_from_installed_runtime(
            LONGBOW_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        )
        entity.equipment.equip(weapon, WeaponSlot.RANGED_MAIN)


def apply_fighting_style(entity: Entity, style: FightingStyleChoice):
    """Apply a fighting style condition to the entity."""
    condition_class = FIGHTING_STYLE_MAP[style]
    entity.add_condition(condition_class(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid
    ))


def apply_fighter_features(entity: Entity, config: FighterConfig):
    """Apply all Fighter features appropriate for the level."""
    level = config.level

    apply_fighting_style(entity, config.fighting_style)

    entity.add_condition(SecondWindFeature(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        fighter_level=level
    ))

    if level >= 2:
        entity.add_condition(ActionSurgeFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            num_uses=get_action_surge_uses(level)
        ))

    if 3 <= level < 15:
        entity.add_condition(ImprovedCritical(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    if level >= 5:
        entity.add_condition(ExtraAttackFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            extra_attacks=get_extra_attacks(level)
        ))

    if level >= 9:
        entity.add_condition(Indomitable(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            num_uses=get_indomitable_uses(level)
        ))

    if level >= 10 and config.second_fighting_style:
        apply_fighting_style(entity, config.second_fighting_style)

    if level >= 15:
        entity.add_condition(SuperiorCritical(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    if level >= 18:
        entity.add_condition(Survivor(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))


def create_fighter(
    config: FighterConfig,
    source_id: Optional[UUID] = None,
    *,
    possession_mode: CreaturePossessionMode = (
        CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
    ),
    content_ref: ContentRef | None = None,
) -> Entity:
    """
    Create a Fighter entity at the specified level with all features applied.

    Flow:
    1. Calculate final ability scores (base + L1 bonus + ASIs)
    2. Calculate proficiency bonus from level
    3. Create base Entity with EntityConfig (includes HP from hit dice)
    4. Setup standard actions (Move, Dash, Dodge, etc.)
    5. Equip weapons/armor based on preset
    6. Apply all Fighter features for the level
    """
    if source_id is None:
        source_id = uuid4()

    final_scores = calculate_final_ability_scores(config)

    prof_bonus = get_proficiency_bonus(config.level)

    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=final_scores["strength"]),
        dexterity=AbilityConfig(ability_score=final_scores["dexterity"]),
        constitution=AbilityConfig(ability_score=final_scores["constitution"]),
        intelligence=AbilityConfig(ability_score=final_scores["intelligence"]),
        wisdom=AbilityConfig(ability_score=final_scores["wisdom"]),
        charisma=AbilityConfig(ability_score=final_scores["charisma"])
    )

    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=10,
            hit_dice_count=config.level,
            mode="average",
            ignore_first_level=False
        )]
    )

    equipment_config = EquipmentConfig()
    action_economy_config = ActionEconomyConfig()
    saving_throws_config = SavingThrowSetConfig(
        strength_saving_throw=SavingThrowConfig(proficiency=True),
        constitution_saving_throw=SavingThrowConfig(proficiency=True),
    )

    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        saving_throws=saving_throws_config,
        proficiency_bonus=prof_bonus,
        position=config.position,
        faction=config.faction,
        appearance=AppearanceConfig(
            body_category="NakedBody",
            skin_tint=0xE6BC98,
            head_category="Head9",
            hair_tint=0x993F00,
            has_beard=True,
            beard_tint=0x993F00,
        ),
    )

    entity = Entity.create(
        name=config.name,
        source_entity_uuid=source_id,
        description=f"Level {config.level} Fighter (Champion)",
        config=entity_config,
        content_ref=content_ref,
    )

    setup_standard_actions(entity)

    if (
        possession_mode
        == CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
    ):
        apply_fighter_features(entity, config)
        return entity

    apply_equipment(entity, config.equipment_preset)
    entity.equipment.equip(
        materialize_item_from_installed_runtime(
            _FIGHTER_LEATHER_BOOTS_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Boots,
        ),
    )

    apply_fighter_features(entity, config)

    haste_potion = materialize_item_from_installed_runtime(
        HASTE_POTION_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    entity.loot_item(haste_potion)
    entity.loot_item(
        materialize_item_from_installed_runtime(
            HEALING_POTION_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
        )
    )
    entity.loot_item(
        materialize_item_from_installed_runtime(
            HEALING_POTION_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
        )
    )
    entity.loot_item(
        materialize_item_from_installed_runtime(
            CLOTH_SHOES_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Boots,
        ),
    )
    entity.loot_item(
        materialize_item_from_installed_runtime(
            _FIGHTER_IRON_HELMET_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Helmet,
        ),
    )

    equipped_names = {i.name for i in entity.equipment.get_all_equipped_items()}
    spare_weapons = [
        ("Handaxe", HANDAXE_RECIPE),
        ("Javelin", JAVELIN_RECIPE),
        ("Dagger", DAGGER_RECIPE),
        ("Longsword", LONGSWORD_RECIPE),
    ]
    for weapon_name, recipe in spare_weapons:
        if weapon_name not in equipped_names:
            entity.loot_item(
                materialize_item_from_installed_runtime(
                    recipe,
                    entity.uuid,
                    origin=ItemRuntimeOrigin.STARTER,
                    expected_type=Weapon,
                ),
            )

    if "Leather Armor" not in equipped_names and "Studded Leather" not in equipped_names:
        entity.loot_item(
            materialize_item_from_installed_runtime(
                LEATHER_ARMOR_RECIPE,
                entity.uuid,
                origin=ItemRuntimeOrigin.STARTER,
                expected_type=BodyArmor,
            ),
        )
    if "Chain Mail" not in equipped_names:
        entity.loot_item(
            materialize_item_from_installed_runtime(
                CHAIN_MAIL_RECIPE,
                entity.uuid,
                origin=ItemRuntimeOrigin.STARTER,
                expected_type=BodyArmor,
            ),
        )

    if "Shield" not in equipped_names:
        entity.loot_item(
            materialize_item_from_installed_runtime(
                SHIELD_RECIPE,
                entity.uuid,
                origin=ItemRuntimeOrigin.STARTER,
                expected_type=Shield,
            ),
        )

    return entity

__all__ = [
    "FighterConfig",
    "FightingStyleChoice",
    "EquipmentPreset",
    "create_fighter",
    "get_proficiency_bonus",
    "get_extra_attacks",
    "get_action_surge_uses",
    "get_indomitable_uses",
    "calculate_final_ability_scores",
]
