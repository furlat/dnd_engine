"""
Sorcerer Factory - Create Sorcerer characters at any level (1-20).

Implements BG3-style configuration with base ability scores, level 1 bonuses,
and ASI choices at appropriate levels. All features are automatically applied
based on level.
"""

from typing import Optional, List, Tuple, Dict, Literal
from uuid import UUID, uuid4
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator

from dnd.entity import Entity, EntityConfig
from dnd.actions_functional import setup_standard_actions, register_spells_by_name
from dnd.blocks.saving_throws import SavingThrowConfig, SavingThrowSetConfig
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import EquipmentConfig, WeaponSlot, UnarmoredAc
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.events import AbilityName
from dnd.core.modifiers import DamageType

# Import items
from dnd.items.weapons import create_dagger, create_quarterstaff
from dnd.items.test_items import create_healing_potion, create_potion_of_haste

# Import sorcerer features
from dnd.classes.sorcerer import (
    DraconicResilience,
    ElementalAffinity,
    SorceryPointsFeature,
)

# Shield reaction
from dnd.spells.abjuration import register_shield_reaction


# =============================================================================
# SORCEROUS ORIGIN
# =============================================================================

class SorcererOriginChoice(str, Enum):
    DRACONIC_BLOODLINE = "draconic_bloodline"
    # WILD_MAGIC = "wild_magic"  # Future


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_proficiency_bonus(level: int) -> int:
    """Returns proficiency bonus for character level."""
    return 2 + (level - 1) // 4


def get_sorcery_points(level: int) -> int:
    """Sorcery points = sorcerer level (0 at L1, since SP unlocks at L2)."""
    return level if level >= 2 else 0


def get_sorcerer_spell_slots(level: int) -> Dict[int, int]:
    """SRD spell slot table for full casters (same as wizard)."""
    TABLE: Dict[int, Dict[int, int]] = {
        1: {1: 2},
        2: {1: 3},
        3: {1: 4, 2: 2},
        4: {1: 4, 2: 3},
        5: {1: 4, 2: 3, 3: 2},
        6: {1: 4, 2: 3, 3: 3},
        7: {1: 4, 2: 3, 3: 3, 4: 1},
        8: {1: 4, 2: 3, 3: 3, 4: 2},
        9: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
        10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
        11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
        12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
        13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
        14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
        15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
        16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
        17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
        18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},
        19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1},
        20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},
    }
    return TABLE.get(level, TABLE[20])


def get_metamagic_count(level: int) -> int:
    """How many metamagic options a sorcerer knows at this level."""
    if level < 3:
        return 0
    if level < 10:
        return 2
    if level < 17:
        return 3
    return 4


def get_default_spells(level: int) -> List[str]:
    """Curated default spell list scaled by level."""
    spells = ["Fire Bolt", "Ray of Frost"]  # cantrips
    if level >= 1:
        spells += ["Magic Missile"]
    if level >= 2:
        spells += ["Burning Hands"]
    if level >= 3:
        spells += ["Hold Person", "Scorching Ray"]
    if level >= 5:
        spells += ["Fireball", "Lightning Bolt"]
    if level >= 7:
        spells += ["Ice Storm"]
    if level >= 9:
        spells += ["Cloudkill"]
    return spells


# =============================================================================
# EQUIPMENT PRESETS
# =============================================================================

SorcererEquipmentPreset = Literal["dagger", "quarterstaff"]

EQUIPMENT_PRESETS = {
    "dagger": {"melee_main": "dagger"},
    "quarterstaff": {"melee_main": "quarterstaff"},
}


# =============================================================================
# SORCERER CONFIG
# =============================================================================

class SorcererConfig(BaseModel):
    """Configuration for creating a Sorcerer at a specific level."""

    # Core
    level: int = Field(ge=1, le=20, default=1)
    name: str = "Sorcerer"
    position: Tuple[int, int] = (0, 0)
    faction: Optional[str] = Field(default=None, description="Faction identifier. None = enemy to everyone")

    # Ability scores (CHA primary, CON secondary)
    base_strength: int = Field(default=8, ge=8, le=15)
    base_dexterity: int = Field(default=14, ge=8, le=15)
    base_constitution: int = Field(default=13, ge=8, le=15)
    base_intelligence: int = Field(default=10, ge=8, le=15)
    base_wisdom: int = Field(default=12, ge=8, le=15)
    base_charisma: int = Field(default=15, ge=8, le=15)

    # Level 1 "racial" bonuses: +2 to one, +1 to another
    bonus_plus_2: AbilityName = "charisma"
    bonus_plus_1: AbilityName = "constitution"

    # Origin (L1)
    origin: SorcererOriginChoice = SorcererOriginChoice.DRACONIC_BLOODLINE
    draconic_damage_type: str = "Fire"  # DamageType value for Draconic Bloodline

    # Metamagic (L3+): choose 2 at L3, +1 at L10, +1 at L17
    metamagic_choices: Optional[List[str]] = None  # e.g., ["quickened", "twinned"]

    # ASI at levels 4, 8, 12, 16, 19
    asi_4: Optional[List[Tuple[AbilityName, int]]] = None
    asi_8: Optional[List[Tuple[AbilityName, int]]] = None
    asi_12: Optional[List[Tuple[AbilityName, int]]] = None
    asi_16: Optional[List[Tuple[AbilityName, int]]] = None
    asi_19: Optional[List[Tuple[AbilityName, int]]] = None

    # Equipment
    equipment_preset: SorcererEquipmentPreset = "dagger"

    # Spells (optional override — default curated list by level)
    spell_names: Optional[List[str]] = None

    # Validators
    @field_validator("bonus_plus_1")
    @classmethod
    def validate_different_bonuses(cls, v: AbilityName, info) -> AbilityName:  # type: ignore[override]
        """Ensure +2 and +1 go to different abilities."""
        bonus_plus_2 = info.data.get("bonus_plus_2")
        if bonus_plus_2 is not None and v == bonus_plus_2:
            raise ValueError("bonus_plus_2 and bonus_plus_1 must be different abilities")
        return v

    @model_validator(mode="after")
    def validate_metamagic_for_level(self):
        """Validate metamagic choices for level."""
        v = self.metamagic_choices
        expected = get_metamagic_count(self.level)
        if self.level < 3:
            if v is not None and len(v) > 0:
                raise ValueError("Cannot choose metamagic before level 3")
            return self
        if v is None or len(v) == 0:
            raise ValueError(f"Level {self.level} sorcerer requires {expected} metamagic choices")
        if len(v) != expected:
            raise ValueError(f"Level {self.level} sorcerer requires exactly {expected} metamagic choices, got {len(v)}")
        valid_options = {"quickened", "twinned", "distant"}
        for choice in v:
            if choice not in valid_options:
                raise ValueError(f"Unknown metamagic: {choice}. Valid: {valid_options}")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate metamagic choices not allowed")
        return self

    @model_validator(mode="after")
    def validate_asis_for_level(self):
        """Validate that ASIs are specified for reached levels."""
        asi_levels = {
            4: self.asi_4,
            8: self.asi_8,
            12: self.asi_12,
            16: self.asi_16,
            19: self.asi_19,
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

def calculate_final_ability_scores(config: SorcererConfig) -> Dict[AbilityName, int]:
    """Calculate final scores: base + L1 bonuses + all ASIs."""
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

    # Apply ASIs
    asi_map = {
        4: config.asi_4,
        8: config.asi_8,
        12: config.asi_12,
        16: config.asi_16,
        19: config.asi_19,
    }
    for lvl, asi in asi_map.items():
        if config.level >= lvl and asi:
            for ability, bonus in asi:
                scores[ability] += bonus

    return {k: min(v, 20) for k, v in scores.items()}


# =============================================================================
# EQUIPMENT APPLICATION
# =============================================================================

def apply_equipment(entity: Entity, preset: SorcererEquipmentPreset) -> None:
    """Apply equipment based on preset."""
    preset_config = EQUIPMENT_PRESETS[preset]
    melee_main = preset_config.get("melee_main")
    if melee_main == "dagger":
        weapon = create_dagger(entity.uuid)
        entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    elif melee_main == "quarterstaff":
        weapon = create_quarterstaff(entity.uuid)
        entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)


# =============================================================================
# FEATURE APPLICATION
# =============================================================================

def apply_sorcerer_features(entity: Entity, config: SorcererConfig) -> None:
    """Apply all Sorcerer features appropriate for the level."""
    level = config.level

    # L1: Origin features
    if config.origin == SorcererOriginChoice.DRACONIC_BLOODLINE:
        entity.add_condition(DraconicResilience(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            hp_bonus=level,  # +1 HP per sorcerer level
        ))

    # L2+: Sorcery Points + Font of Magic + Metamagic
    if level >= 2:
        metamagic = config.metamagic_choices or []
        entity.add_condition(SorceryPointsFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            sorcery_points=get_sorcery_points(level),
            metamagic_choices=metamagic,
        ))

    # L6+: Elemental Affinity (Draconic)
    if level >= 6 and config.origin == SorcererOriginChoice.DRACONIC_BLOODLINE:
        entity.add_condition(ElementalAffinity(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            damage_type=DamageType(config.draconic_damage_type),
        ))


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_sorcerer(config: SorcererConfig, source_id: Optional[UUID] = None) -> Entity:
    """Create a Sorcerer entity at the specified level with all features applied.

    Flow:
    1. Calculate final ability scores (base + L1 bonus + ASIs)
    2. Calculate proficiency bonus from level
    3. Create base Entity with EntityConfig (includes HP from d6 hit dice)
    4. Setup standard actions (Move, Dash, Dodge, etc.)
    5. Equip weapon based on preset
    6. Apply all Sorcerer features for the level
    7. Register spells
    """
    if source_id is None:
        source_id = uuid4()

    # 1. Calculate final ability scores
    final_scores = calculate_final_ability_scores(config)

    # 2. Proficiency bonus
    prof_bonus = get_proficiency_bonus(config.level)

    # 3. Ability scores config
    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=final_scores["strength"]),
        dexterity=AbilityConfig(ability_score=final_scores["dexterity"]),
        constitution=AbilityConfig(ability_score=final_scores["constitution"]),
        intelligence=AbilityConfig(ability_score=final_scores["intelligence"]),
        wisdom=AbilityConfig(ability_score=final_scores["wisdom"]),
        charisma=AbilityConfig(ability_score=final_scores["charisma"]),
    )

    # 4. HP: Sorcerer hit dice = d6
    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=6,
            hit_dice_count=config.level,
            mode="average",
            ignore_first_level=False,
        )]
    )

    # 5. Action economy with spell slots
    action_economy_config = ActionEconomyConfig(
        spell_slots=get_sorcerer_spell_slots(config.level),
    )

    # 6. Spellcasting config
    spellcasting_config = SpellcastingConfig(
        spellcasting_ability="charisma",
    )

    # 7. Entity config
    saving_throws_config = SavingThrowSetConfig(
        constitution_saving_throw=SavingThrowConfig(proficiency=True),
        charisma_saving_throw=SavingThrowConfig(proficiency=True),
    )

    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        health=health_config,
        equipment=EquipmentConfig(unarmored_ac_type=UnarmoredAc.DRACONIC_SORCERER),
        action_economy=action_economy_config,
        spellcasting=spellcasting_config,
        saving_throws=saving_throws_config,
        proficiency_bonus=prof_bonus,
        position=config.position,
        faction=config.faction,
    )

    # 8. Create entity
    origin_name = f" ({config.origin.value.replace('_', ' ').title()})" if config.origin else ""
    entity = Entity.create(
        name=config.name,
        source_entity_uuid=source_id,
        description=f"Level {config.level} Sorcerer{origin_name}",
        config=entity_config,
    )

    # 9. Standard actions
    setup_standard_actions(entity)

    # 10. Equipment
    apply_equipment(entity, config.equipment_preset)

    # 11. Apply class features
    apply_sorcerer_features(entity, config)

    # 12. Register spells
    spell_list = config.spell_names or get_default_spells(config.level)
    register_spells_by_name(entity, spell_list, caster_level=config.level)

    # Shield is a reaction spell, registered separately (not via ALL_SPELLS)
    register_shield_reaction(entity)

    # 13. Add starter inventory items
    entity.loot_item(create_potion_of_haste(entity.uuid))
    entity.loot_item(create_healing_potion(entity.uuid))
    entity.loot_item(create_healing_potion(entity.uuid))

    # Spare weapon — the one NOT equipped (preset picks one, inventory gets the other)
    equipped_names = {i.name for i in entity.equipment.get_all_equipped_items()}
    if "Dagger" not in equipped_names:
        entity.loot_item(create_dagger(entity.uuid))
    if "Quarterstaff" not in equipped_names:
        entity.loot_item(create_quarterstaff(entity.uuid))

    return entity


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "SorcererConfig",
    "SorcererOriginChoice",
    "SorcererEquipmentPreset",
    "create_sorcerer",
    "get_proficiency_bonus",
    "get_sorcery_points",
    "get_sorcerer_spell_slots",
    "get_metamagic_count",
    "get_default_spells",
    "calculate_final_ability_scores",
]
