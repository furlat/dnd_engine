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
from dnd.blocks.equipment import EquipmentConfig
from dnd.core.equipment_types import UnarmoredAc, WeaponSlot
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.core.events import AbilityName

from dnd.items import (
    create_greataxe,
    create_handaxe,
    create_longsword,
    create_shield,
    create_javelin,
    create_dagger,
)
from dnd.items.test_items import create_potion_of_haste, create_healing_potion

from dnd.classes.rage import (
    RageFeature,
    FrenzyFeature,
)

from dnd.classes.barbarian import (
    RecklessAttackFeature,
    DangerSense,
    FastMovement,
    MindlessRage,
    FeralInstinct,
    BrutalCritical,
    IntimidatingPresenceFeature,
    RelentlessRage,
    Retaliation,
    PersistentRage,
    IndomitableMight,
    PrimalChampion,
)

from dnd.classes.fighter import ExtraAttackFeature


class PrimalPathChoice(str, Enum):
    BERSERKER = "berserker"


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
    return 999


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


class BarbarianConfig(BaseModel):
    """Configuration for creating a Barbarian at a specific level.

    Attributes:
        level: Barbarian level used to gate features, resources, subclass choice, and required ASIs.
        name: Display name for the created barbarian entity.
        position: Initial grid position for the created barbarian entity.
        faction: Faction identifier. None = enemy to everyone.
        base_strength: Base Strength score before level-one bonuses and ASI choices.
        base_dexterity: Base Dexterity score before level-one bonuses and ASI choices.
        base_constitution: Base Constitution score before level-one bonuses and ASI choices.
        base_intelligence: Base Intelligence score before level-one bonuses and ASI choices.
        base_wisdom: Base Wisdom score before level-one bonuses and ASI choices.
        base_charisma: Base Charisma score before level-one bonuses and ASI choices.
        bonus_plus_2: Ability that receives the level-one +2 bonus.
        bonus_plus_1: Ability that receives the level-one +1 bonus.
        primal_path: Barbarian primal path, required by the factory at level three and above.
        asi_4: Ability score improvements selected at Barbarian level four.
        asi_8: Ability score improvements selected at Barbarian level eight.
        asi_12: Ability score improvements selected at Barbarian level twelve.
        asi_16: Ability score improvements selected at Barbarian level sixteen.
        asi_19: Ability score improvements selected at Barbarian level nineteen.
        equipment_preset: Starter equipment preset equipped by the Barbarian factory.
    """

    level: int = Field(
        ge=1,
        le=20,
        default=1,
        description="Barbarian level used to gate features, resources, subclass choice, and required ASIs.",
    )
    name: str = Field(default="Barbarian", description="Display name for the created barbarian entity.")
    position: Tuple[int, int] = Field(
        default=(0, 0),
        description="Initial grid position for the created barbarian entity.",
    )
    faction: Optional[str] = Field(default=None, description="Faction identifier. None = enemy to everyone")

    base_strength: int = Field(
        default=15,
        ge=8,
        le=15,
        description="Base Strength score before level-one bonuses and ASI choices.",
    )
    base_dexterity: int = Field(
        default=13,
        ge=8,
        le=15,
        description="Base Dexterity score before level-one bonuses and ASI choices.",
    )
    base_constitution: int = Field(
        default=14,
        ge=8,
        le=15,
        description="Base Constitution score before level-one bonuses and ASI choices.",
    )
    base_intelligence: int = Field(
        default=8,
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
        default=10,
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

    primal_path: Optional[PrimalPathChoice] = Field(
        default=None,
        description="Barbarian primal path, required by the factory at level three and above.",
    )

    asi_4: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Barbarian level four.",
    )
    asi_8: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Barbarian level eight.",
    )
    asi_12: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Barbarian level twelve.",
    )
    asi_16: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Barbarian level sixteen.",
    )
    asi_19: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Barbarian level nineteen.",
    )

    equipment_preset: EquipmentPreset = Field(
        default="greataxe",
        description="Starter equipment preset equipped by the Barbarian factory.",
    )

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

    scores[config.bonus_plus_2] += 2
    scores[config.bonus_plus_1] += 1

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

    return {k: min(v, 20) for k, v in scores.items()}


def apply_equipment(entity: Entity, preset: EquipmentPreset):
    """Apply equipment based on preset. Barbarians typically don't wear armor."""
    preset_config = EQUIPMENT_PRESETS[preset]

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

    melee_off = preset_config.get("melee_off")
    if melee_off == "handaxe":
        weapon = create_handaxe(entity.uuid)
        entity.equipment.equip(weapon, WeaponSlot.MELEE_OFF)
    elif melee_off == "shield":
        shield = create_shield(entity.uuid)
        entity.equipment.equip(shield, WeaponSlot.MELEE_OFF)


def apply_barbarian_features(entity: Entity, config: BarbarianConfig):
    """Apply all Barbarian features appropriate for the level."""
    level = config.level
    rage_damage = get_rage_damage(level)

    entity.add_condition(RageFeature(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        rage_uses=get_rage_uses(level),
        rage_damage=rage_damage
    ))

    if level >= 2:
        entity.add_condition(RecklessAttackFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    if level >= 2:
        entity.add_condition(DangerSense(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    if level >= 3 and config.primal_path == PrimalPathChoice.BERSERKER:
        entity.add_condition(FrenzyFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            rage_damage=rage_damage
        ))

        if level >= 6:
            entity.add_condition(MindlessRage(
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid
            ))

        if level >= 10:
            entity.add_condition(IntimidatingPresenceFeature(
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid
            ))

        if level >= 14:
            entity.add_condition(Retaliation(
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid
            ))

    if level >= 5:
        entity.add_condition(ExtraAttackFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            extra_attacks=get_extra_attacks(level)
        ))

    if level >= 5:
        entity.add_condition(FastMovement(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    if level >= 7:
        entity.add_condition(FeralInstinct(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    brutal_dice = get_brutal_critical_dice(level)
    if brutal_dice > 0:
        entity.add_condition(BrutalCritical(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            extra_dice=brutal_dice
        ))

    if level >= 11:
        entity.add_condition(RelentlessRage(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    if level >= 15:
        entity.add_condition(PersistentRage(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    if level >= 18:
        entity.add_condition(IndomitableMight(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    if level >= 20:
        entity.add_condition(PrimalChampion(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))


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
            hit_dice_value=12,
            hit_dice_count=config.level,
            mode="average",
            ignore_first_level=False
        )]
    )

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
        faction=config.faction,
        appearance=AppearanceConfig(
            body_category="NakedBody",
            skin_tint=0xD4AA78,
            head_category="Head9",
            hair_tint=0xD0BFA1,
            has_beard=False,
            beard_tint=0,
        ),
    )

    path_name = f" ({config.primal_path.value.title()})" if config.primal_path else ""
    entity = Entity.create(
        name=config.name,
        source_entity_uuid=source_id,
        description=f"Level {config.level} Barbarian{path_name}",
        config=entity_config
    )

    setup_standard_actions(entity)

    apply_equipment(entity, config.equipment_preset)

    apply_barbarian_features(entity, config)

    haste_potion = create_potion_of_haste(entity.uuid)
    entity.loot_item(haste_potion)
    entity.loot_item(create_healing_potion(entity.uuid))
    entity.loot_item(create_healing_potion(entity.uuid))

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

    if "Shield" not in equipped_names:
        entity.loot_item(create_shield(entity.uuid))

    return entity

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
