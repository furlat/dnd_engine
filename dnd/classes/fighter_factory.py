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
from dnd.blocks.equipment import EquipmentConfig, WeaponSlot
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.core.events import AbilityName
from dnd.core.base_conditions import BaseCondition

# Import items
from dnd.items import (
    create_longsword,
    create_greatsword,
    create_shortsword,
    create_longbow,
    create_chain_mail,
    create_studded_leather,
    create_shield,
    create_dagger,
    create_handaxe,
    create_javelin,
)
from dnd.items.armors import create_cloth_shoes, create_iron_helmet, create_leather_armor, create_leather_boots
from dnd.items.test_items import create_potion_of_haste, create_healing_potion

# Import fighter features
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


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

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


# =============================================================================
# FIGHTING STYLE TYPES AND MAPPING
# =============================================================================

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


# =============================================================================
# EQUIPMENT PRESETS
# =============================================================================

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


# =============================================================================
# FIGHTER CONFIG
# =============================================================================

class FighterConfig(BaseModel):
    """
    Configuration for creating a Fighter at a specific level.

    BG3-style: base stats + level 1 bonuses + ASI choices at feat levels.
    """

    # Core
    level: int = Field(ge=1, le=20, default=1)
    name: str = "Fighter"
    position: Tuple[int, int] = (0, 0)
    faction: Optional[str] = Field(default=None, description="Faction identifier. None = enemy to everyone")

    # ==========================================================================
    # ABILITY SCORES (BG3 Style)
    # ==========================================================================

    # Base scores (like standard array or point buy result)
    base_strength: int = Field(default=15, ge=8, le=15)
    base_dexterity: int = Field(default=14, ge=8, le=15)
    base_constitution: int = Field(default=13, ge=8, le=15)
    base_intelligence: int = Field(default=10, ge=8, le=15)
    base_wisdom: int = Field(default=12, ge=8, le=15)
    base_charisma: int = Field(default=8, ge=8, le=15)

    # Level 1 "racial" bonuses: +2 to one, +1 to another
    bonus_plus_2: AbilityName = "strength"
    bonus_plus_1: AbilityName = "constitution"

    # ==========================================================================
    # CHOICES AT SPECIFIC LEVELS
    # ==========================================================================

    # Level 1: Fighting Style (required)
    fighting_style: FightingStyleChoice = "defense"

    # Level 10: Second Fighting Style (Champion) - None if not L10+ yet
    second_fighting_style: Optional[FightingStyleChoice] = None

    # ASI choices at levels 4, 6, 8, 12, 14, 16, 19
    # Each entry is (+2 to one stat) OR (+1 to two stats)
    # Format: [("strength", 2)] or [("strength", 1), ("constitution", 1)]
    asi_4: Optional[List[Tuple[AbilityName, int]]] = None
    asi_6: Optional[List[Tuple[AbilityName, int]]] = None
    asi_8: Optional[List[Tuple[AbilityName, int]]] = None
    asi_12: Optional[List[Tuple[AbilityName, int]]] = None
    asi_14: Optional[List[Tuple[AbilityName, int]]] = None
    asi_16: Optional[List[Tuple[AbilityName, int]]] = None
    asi_19: Optional[List[Tuple[AbilityName, int]]] = None

    # ==========================================================================
    # EQUIPMENT
    # ==========================================================================
    equipment_preset: EquipmentPreset = "sword_shield"

    # ==========================================================================
    # VALIDATORS
    # ==========================================================================

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


# =============================================================================
# ABILITY SCORE CALCULATION
# =============================================================================

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

    # Apply L1 bonuses
    scores[config.bonus_plus_2] += 2
    scores[config.bonus_plus_1] += 1

    # Apply ASIs for reached levels
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

    # Cap at 20
    return {k: min(v, 20) for k, v in scores.items()}


# =============================================================================
# EQUIPMENT APPLICATION
# =============================================================================

def apply_equipment(entity: Entity, preset: EquipmentPreset):
    """Apply equipment based on preset."""
    preset_config = EQUIPMENT_PRESETS[preset]

    # Armor
    armor_name = preset_config.get("armor")
    if armor_name == "chain_mail":
        armor = create_chain_mail(entity.uuid)
        entity.equipment.equip(armor)
    elif armor_name == "studded_leather":
        armor = create_studded_leather(entity.uuid)
        entity.equipment.equip(armor)

    # Melee main
    melee_main = preset_config.get("melee_main")
    if melee_main == "longsword":
        weapon = create_longsword(entity.uuid)
        entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    elif melee_main == "greatsword":
        weapon = create_greatsword(entity.uuid)
        entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    elif melee_main == "shortsword":
        weapon = create_shortsword(entity.uuid)
        entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)

    # Melee off
    melee_off = preset_config.get("melee_off")
    if melee_off == "shield":
        shield = create_shield(entity.uuid)
        entity.equipment.equip(shield, WeaponSlot.MELEE_OFF)
    elif melee_off == "shortsword":
        weapon = create_shortsword(entity.uuid)
        entity.equipment.equip(weapon, WeaponSlot.MELEE_OFF)

    # Ranged main
    ranged_main = preset_config.get("ranged_main")
    if ranged_main == "longbow":
        weapon = create_longbow(entity.uuid)
        entity.equipment.equip(weapon, WeaponSlot.RANGED_MAIN)


# =============================================================================
# FIGHTING STYLE APPLICATION
# =============================================================================

def apply_fighting_style(entity: Entity, style: FightingStyleChoice):
    """Apply a fighting style condition to the entity."""
    condition_class = FIGHTING_STYLE_MAP[style]
    entity.add_condition(condition_class(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid
    ))


# =============================================================================
# FEATURE APPLICATION
# =============================================================================

def apply_fighter_features(entity: Entity, config: FighterConfig):
    """Apply all Fighter features appropriate for the level."""
    level = config.level

    # L1: Fighting Style
    apply_fighting_style(entity, config.fighting_style)

    # L1: Second Wind (healing scales with level)
    entity.add_condition(SecondWindFeature(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        fighter_level=level
    ))

    # L2+: Action Surge
    if level >= 2:
        entity.add_condition(ActionSurgeFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            num_uses=get_action_surge_uses(level)
        ))

    # L3-14: Improved Critical (Champion)
    # Note: At L15, Superior Critical replaces this
    if 3 <= level < 15:
        entity.add_condition(ImprovedCritical(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    # L5+: Extra Attack
    if level >= 5:
        entity.add_condition(ExtraAttackFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            extra_attacks=get_extra_attacks(level)
        ))

    # L9+: Indomitable
    if level >= 9:
        entity.add_condition(Indomitable(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            num_uses=get_indomitable_uses(level)
        ))

    # L10+: Second Fighting Style (Champion)
    if level >= 10 and config.second_fighting_style:
        apply_fighting_style(entity, config.second_fighting_style)

    # L15+: Superior Critical (replaces Improved Critical)
    if level >= 15:
        entity.add_condition(SuperiorCritical(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    # L18+: Survivor (Champion)
    if level >= 18:
        entity.add_condition(Survivor(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_fighter(config: FighterConfig, source_id: Optional[UUID] = None) -> Entity:
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

    # 1. Calculate final ability scores
    final_scores = calculate_final_ability_scores(config)

    # 2. Calculate proficiency bonus
    prof_bonus = get_proficiency_bonus(config.level)

    # 3. Create ability scores config
    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=final_scores["strength"]),
        dexterity=AbilityConfig(ability_score=final_scores["dexterity"]),
        constitution=AbilityConfig(ability_score=final_scores["constitution"]),
        intelligence=AbilityConfig(ability_score=final_scores["intelligence"]),
        wisdom=AbilityConfig(ability_score=final_scores["wisdom"]),
        charisma=AbilityConfig(ability_score=final_scores["charisma"])
    )

    # 4. Calculate HP
    # Fighter hit dice: d10
    # Level 1: 10 + CON mod
    # Level 2+: (10 + CON_mod) + (level-1) * (6 + CON_mod)
    # We use average mode which handles first level maximum automatically
    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=10,
            hit_dice_count=config.level,
            mode="average",
            ignore_first_level=False
        )]
    )

    # 5. Create entity config
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

    # 6. Create entity
    entity = Entity.create(
        name=config.name,
        source_entity_uuid=source_id,
        description=f"Level {config.level} Fighter (Champion)",
        config=entity_config
    )

    # 7. Setup standard actions (Move, Dash, Dodge, etc.)
    setup_standard_actions(entity)

    # 8. Apply equipment
    apply_equipment(entity, config.equipment_preset)
    entity.equipment.equip(create_leather_boots(entity.uuid, visual_variant_id="b0000009"))

    # 9. Apply all fighter features
    apply_fighter_features(entity, config)

    # 10. Add starter inventory items
    haste_potion = create_potion_of_haste(entity.uuid)
    entity.loot_item(haste_potion)
    entity.loot_item(create_healing_potion(entity.uuid))
    entity.loot_item(create_healing_potion(entity.uuid))
    entity.loot_item(create_cloth_shoes(entity.uuid))
    entity.loot_item(create_iron_helmet(entity.uuid, visual_variant_id="h0000008"))

    # Spare weapons — items NOT duplicating equipped gear
    # Check what's equipped to avoid exact duplicates
    equipped_names = {i.name for i in entity.equipment.get_all_equipped_items()}
    spare_weapons = [
        ("Handaxe", create_handaxe),
        ("Javelin", create_javelin),
        ("Dagger", create_dagger),
        ("Longsword", create_longsword),
    ]
    for weapon_name, factory_fn in spare_weapons:
        if weapon_name not in equipped_names:
            entity.loot_item(factory_fn(entity.uuid))

    # Spare armor — only if different from equipped
    if "Leather Armor" not in equipped_names and "Studded Leather" not in equipped_names:
        entity.loot_item(create_leather_armor(entity.uuid))
    if "Chain Mail" not in equipped_names:
        entity.loot_item(create_chain_mail(entity.uuid))

    # Spare shield
    if "Shield" not in equipped_names:
        entity.loot_item(create_shield(entity.uuid))

    return entity


# =============================================================================
# EXPORTS
# =============================================================================

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
