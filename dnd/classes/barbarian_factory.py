"""
Barbarian Factory - Create Barbarian characters at any level (1-20).

Implements BG3-style configuration with base ability scores, level 1 bonuses,
and ASI choices at appropriate levels. All features are automatically applied
based on level.
"""

from typing import Optional, List, Tuple, Dict, Literal
from uuid import UUID, uuid4
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator

from dnd.entity import Entity, EntityConfig
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.saving_throws import SavingThrowConfig, SavingThrowSetConfig
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import EquipmentConfig, WeaponSlot, UnarmoredAc
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.core.events import AbilityName

# Import items
from dnd.items import (
    create_greataxe,
    create_handaxe,
    create_longsword,
    create_shield,
    create_javelin,
    create_dagger,
)
from dnd.items.test_items import create_potion_of_haste, create_healing_potion

# Import rage/frenzy features (from rage.py)
from dnd.classes.rage import (
    RageFeature,
    FrenzyFeature,
)

# Import other barbarian features
from dnd.classes.barbarian import (
    # Level 2
    RecklessAttackFeature,
    DangerSense,
    # Level 5
    FastMovement,
    # Level 6 (Berserker)
    MindlessRage,
    # Level 7
    FeralInstinct,
    # Level 9/13/17
    BrutalCritical,
    # Level 10 (Berserker)
    IntimidatingPresenceFeature,
    # Level 11
    RelentlessRage,
    # Level 14 (Berserker)
    Retaliation,
    # Level 15
    PersistentRage,
    # Level 18
    IndomitableMight,
    # Level 20
    PrimalChampion,
)

# Reuse Fighter's ExtraAttackFeature for Extra Attack
from dnd.classes.fighter import ExtraAttackFeature


# =============================================================================
# PRIMAL PATH
# =============================================================================

class PrimalPathChoice(str, Enum):
    BERSERKER = "berserker"
    # TOTEM_WARRIOR = "totem_warrior"  # Future


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_proficiency_bonus(level: int) -> int:
    """Returns proficiency bonus for character level."""
    return 2 + (level - 1) // 4


def get_rage_uses(level: int) -> int:
    """
    Rage uses per long rest by level.
    - Level 1-2: 2 uses
    - Level 3-5: 3 uses
    - Level 6-11: 4 uses
    - Level 12-16: 5 uses
    - Level 17-19: 6 uses
    - Level 20: Unlimited (999)
    """
    if level < 3:
        return 2
    if level < 6:
        return 3
    if level < 12:
        return 4
    if level < 17:
        return 5
    if level < 20:
        return 6
    return 999  # Unlimited at L20


def get_rage_damage(level: int) -> int:
    """
    Rage damage bonus by level.
    - Level 1-8: +2
    - Level 9-15: +3
    - Level 16+: +4
    """
    if level < 9:
        return 2
    if level < 16:
        return 3
    return 4


def get_brutal_critical_dice(level: int) -> int:
    """
    Brutal Critical extra dice by level.
    - Level 1-8: 0
    - Level 9-12: 1
    - Level 13-16: 2
    - Level 17+: 3
    """
    if level < 9:
        return 0
    if level < 13:
        return 1
    if level < 17:
        return 2
    return 3


def get_extra_attacks(level: int) -> int:
    """Barbarians get 1 extra attack at level 5."""
    if level < 5:
        return 0
    return 1


# =============================================================================
# EQUIPMENT PRESETS
# =============================================================================

EquipmentPreset = Literal["greataxe", "dual_axes", "sword_shield"]

EQUIPMENT_PRESETS = {
    "greataxe": {
        "melee_main": "greataxe",
        "melee_off": None,
    },
    "dual_axes": {
        "melee_main": "handaxe",
        "melee_off": "handaxe",
    },
    "sword_shield": {
        "melee_main": "longsword",
        "melee_off": "shield",
    },
}


# =============================================================================
# BARBARIAN CONFIG
# =============================================================================

class BarbarianConfig(BaseModel):
    """
    Configuration for creating a Barbarian at a specific level.

    BG3-style: base stats + level 1 bonuses + ASI choices at feat levels.
    """

    # Core
    level: int = Field(ge=1, le=20, default=1)
    name: str = "Barbarian"
    position: Tuple[int, int] = (0, 0)
    faction: Optional[str] = Field(default=None, description="Faction identifier. None = enemy to everyone")

    # ==========================================================================
    # ABILITY SCORES (BG3 Style)
    # ==========================================================================

    # Base scores (like standard array or point buy result)
    base_strength: int = Field(default=15, ge=8, le=15)
    base_dexterity: int = Field(default=13, ge=8, le=15)
    base_constitution: int = Field(default=14, ge=8, le=15)
    base_intelligence: int = Field(default=8, ge=8, le=15)
    base_wisdom: int = Field(default=12, ge=8, le=15)
    base_charisma: int = Field(default=10, ge=8, le=15)

    # Level 1 "racial" bonuses: +2 to one, +1 to another
    bonus_plus_2: AbilityName = "strength"
    bonus_plus_1: AbilityName = "constitution"

    # ==========================================================================
    # PRIMAL PATH (Level 3+)
    # ==========================================================================
    primal_path: Optional[PrimalPathChoice] = None

    # ==========================================================================
    # ASI CHOICES AT LEVELS 4, 8, 12, 16, 19
    # ==========================================================================
    # Each entry is (+2 to one stat) OR (+1 to two stats)
    # Format: [("strength", 2)] or [("strength", 1), ("constitution", 1)]
    asi_4: Optional[List[Tuple[AbilityName, int]]] = None
    asi_8: Optional[List[Tuple[AbilityName, int]]] = None
    asi_12: Optional[List[Tuple[AbilityName, int]]] = None
    asi_16: Optional[List[Tuple[AbilityName, int]]] = None
    asi_19: Optional[List[Tuple[AbilityName, int]]] = None

    # ==========================================================================
    # EQUIPMENT
    # ==========================================================================
    equipment_preset: EquipmentPreset = "greataxe"

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

    @field_validator("primal_path")
    @classmethod
    def validate_primal_path(cls, v: Optional[PrimalPathChoice], info) -> Optional[PrimalPathChoice]:
        """Validate primal path is specified at level 3+."""
        level = info.data.get("level", 1)
        if level >= 3 and v is None:
            raise ValueError("Primal path required at level 3+")
        if level < 3 and v is not None:
            raise ValueError("Cannot choose primal path before level 3")
        return v

    @model_validator(mode="after")
    def validate_asis_for_level(self):
        """Validate that ASIs are specified for reached levels."""
        asi_levels = {
            4: self.asi_4,
            8: self.asi_8,
            12: self.asi_12,
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

def calculate_final_ability_scores(config: BarbarianConfig) -> Dict[AbilityName, int]:
    """
    Calculate final scores: base + L1 bonuses + all ASIs.

    Example for L5 barbarian:
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
        8: config.asi_8,
        12: config.asi_12,
        16: config.asi_16,
        19: config.asi_19
    }
    for lvl, asi in asi_map.items():
        if config.level >= lvl and asi:
            for ability, bonus in asi:
                scores[ability] += bonus

    # Cap at 20 (unless Primal Champion at L20 raises it)
    # Primal Champion adds +4 to STR and CON later, and raises max to 24
    # So we don't cap at 20 here - the condition handles the boost
    return {k: min(v, 20) for k, v in scores.items()}


# =============================================================================
# EQUIPMENT APPLICATION
# =============================================================================

def apply_equipment(entity: Entity, preset: EquipmentPreset):
    """Apply equipment based on preset. Barbarians typically don't wear armor."""
    preset_config = EQUIPMENT_PRESETS[preset]

    # Melee main
    melee_main = preset_config.get("melee_main")
    if melee_main == "greataxe":
        weapon = create_greataxe(entity.uuid)
        entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    elif melee_main == "handaxe":
        weapon = create_handaxe(entity.uuid)
        entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    elif melee_main == "longsword":
        weapon = create_longsword(entity.uuid)
        entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)

    # Melee off
    melee_off = preset_config.get("melee_off")
    if melee_off == "handaxe":
        weapon = create_handaxe(entity.uuid)
        entity.equipment.equip(weapon, WeaponSlot.MELEE_OFF)
    elif melee_off == "shield":
        shield = create_shield(entity.uuid)
        entity.equipment.equip(shield, WeaponSlot.MELEE_OFF)


# =============================================================================
# FEATURE APPLICATION
# =============================================================================

def apply_barbarian_features(entity: Entity, config: BarbarianConfig):
    """Apply all Barbarian features appropriate for the level."""
    level = config.level
    rage_damage = get_rage_damage(level)

    # L1: Rage (with level-scaled uses and damage)
    entity.add_condition(RageFeature(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        rage_uses=get_rage_uses(level),
        rage_damage=rage_damage
    ))

    # L2+: Reckless Attack
    if level >= 2:
        entity.add_condition(RecklessAttackFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    # L2+: Danger Sense
    if level >= 2:
        entity.add_condition(DangerSense(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    # L3+: Primal Path features
    if level >= 3 and config.primal_path == PrimalPathChoice.BERSERKER:
        # L3: Frenzy
        entity.add_condition(FrenzyFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            rage_damage=rage_damage
        ))

        # L6: Mindless Rage
        if level >= 6:
            entity.add_condition(MindlessRage(
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid
            ))

        # L10: Intimidating Presence
        if level >= 10:
            entity.add_condition(IntimidatingPresenceFeature(
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid
            ))

        # L14: Retaliation
        if level >= 14:
            entity.add_condition(Retaliation(
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid
            ))

    # L5+: Extra Attack (using Fighter's implementation)
    if level >= 5:
        entity.add_condition(ExtraAttackFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            extra_attacks=get_extra_attacks(level)
        ))

    # L5+: Fast Movement
    if level >= 5:
        entity.add_condition(FastMovement(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    # L7+: Feral Instinct
    if level >= 7:
        entity.add_condition(FeralInstinct(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    # L9/13/17: Brutal Critical
    brutal_dice = get_brutal_critical_dice(level)
    if brutal_dice > 0:
        entity.add_condition(BrutalCritical(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            extra_dice=brutal_dice
        ))

    # L11+: Relentless Rage
    if level >= 11:
        entity.add_condition(RelentlessRage(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    # L15+: Persistent Rage
    if level >= 15:
        entity.add_condition(PersistentRage(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    # L18+: Indomitable Might
    if level >= 18:
        entity.add_condition(IndomitableMight(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    # L20: Primal Champion
    if level >= 20:
        entity.add_condition(PrimalChampion(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_barbarian(config: BarbarianConfig, source_id: Optional[UUID] = None) -> Entity:
    """
    Create a Barbarian entity at the specified level with all features applied.

    Flow:
    1. Calculate final ability scores (base + L1 bonus + ASIs)
    2. Calculate proficiency bonus from level
    3. Create base Entity with EntityConfig (includes HP from d12 hit dice)
    4. Setup standard actions (Move, Dash, Dodge, etc.)
    5. Equip weapons based on preset (no armor - Unarmored Defense)
    6. Apply all Barbarian features for the level
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
    # Barbarian hit dice: d12
    # Level 1: 12 + CON mod
    # Level 2+: (12 + CON_mod) + (level-1) * (7 + CON_mod) [average]
    # We use average mode which handles first level maximum automatically
    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=12,
            hit_dice_count=config.level,
            mode="average",
            ignore_first_level=False
        )]
    )

    # 5. Create entity config
    equipment_config = EquipmentConfig(unarmored_ac_type=UnarmoredAc.BARBARIAN)
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
        faction=config.faction
    )

    # 6. Create entity
    path_name = f" ({config.primal_path.value.title()})" if config.primal_path else ""
    entity = Entity.create(
        name=config.name,
        source_entity_uuid=source_id,
        description=f"Level {config.level} Barbarian{path_name}",
        config=entity_config
    )

    # 7. Setup standard actions (Move, Dash, Dodge, etc.)
    setup_standard_actions(entity)

    # 8. Apply equipment (no armor for Unarmored Defense)
    apply_equipment(entity, config.equipment_preset)

    # 9. Apply all barbarian features
    apply_barbarian_features(entity, config)

    # 10. Add starter inventory items
    haste_potion = create_potion_of_haste(entity.uuid)
    entity.loot_item(haste_potion)
    entity.loot_item(create_healing_potion(entity.uuid))
    entity.loot_item(create_healing_potion(entity.uuid))

    # Spare weapons — avoid duplicating equipped gear
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

    # Spare shield
    if "Shield" not in equipped_names:
        entity.loot_item(create_shield(entity.uuid))

    return entity


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "BarbarianConfig",
    "PrimalPathChoice",
    "EquipmentPreset",
    "create_barbarian",
    "get_proficiency_bonus",
    "get_rage_uses",
    "get_rage_damage",
    "get_brutal_critical_dice",
    "get_extra_attacks",
    "calculate_final_ability_scores",
]
