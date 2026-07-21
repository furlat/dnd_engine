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
from dnd.blocks.appearance import AppearanceConfig
from dnd.core.events import AbilityName
from dnd.core.modifiers import DamageType
from dnd.core.progression import full_caster_spell_slots_for_level, proficiency_bonus_for_level

from dnd.items.weapons import create_dagger, create_quarterstaff
from dnd.items.armors import create_cloth_shoes, create_robes, create_wizard_hat
from dnd.items.test_items import create_healing_potion, create_potion_of_haste

from dnd.classes.sorcerer import (
    DraconicResilience,
    ElementalAffinity,
    SorceryPointsFeature,
)

from dnd.spells.abjuration import register_shield_reaction


class SorcererOriginChoice(str, Enum):
    DRACONIC_BLOODLINE = "draconic_bloodline"


def get_proficiency_bonus(level: int) -> int:
    """Returns proficiency bonus for character level."""
    return proficiency_bonus_for_level(level)


def get_sorcery_points(level: int) -> int:
    """Sorcery points = sorcerer level (0 at L1, since SP unlocks at L2)."""
    return level if level >= 2 else 0


def get_sorcerer_spell_slots(level: int) -> Dict[int, int]:
    """SRD spell slot table for full casters (same as wizard)."""
    return full_caster_spell_slots_for_level(level)


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
    spells = ["Fire Bolt", "Ray of Frost"]
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

SorcererEquipmentPreset = Literal["dagger", "quarterstaff"]

EQUIPMENT_PRESETS = {
    "dagger": {"melee_main": "dagger"},
    "quarterstaff": {"melee_main": "quarterstaff"},
}


class SorcererConfig(BaseModel):
    """Configuration for creating a Sorcerer at a specific level.

    Attributes:
        level: Sorcerer level used to gate spellcasting, metamagic, resources, and required ASIs.
        name: Display name for the created sorcerer entity.
        position: Initial grid position for the created sorcerer entity.
        faction: Faction identifier. None = enemy to everyone.
        base_strength: Base Strength score before level-one bonuses and ASI choices.
        base_dexterity: Base Dexterity score before level-one bonuses and ASI choices.
        base_constitution: Base Constitution score before level-one bonuses and ASI choices.
        base_intelligence: Base Intelligence score before level-one bonuses and ASI choices.
        base_wisdom: Base Wisdom score before level-one bonuses and ASI choices.
        base_charisma: Base Charisma score before level-one bonuses and ASI choices.
        bonus_plus_2: Ability that receives the level-one +2 bonus.
        bonus_plus_1: Ability that receives the level-one +1 bonus.
        origin: Sorcerous origin applied by the factory.
        draconic_damage_type: Damage type used by Draconic Bloodline Elemental Affinity.
        metamagic_choices: Metamagic choices required by the factory at levels three and above.
        asi_4: Ability score improvements selected at Sorcerer level four.
        asi_8: Ability score improvements selected at Sorcerer level eight.
        asi_12: Ability score improvements selected at Sorcerer level twelve.
        asi_16: Ability score improvements selected at Sorcerer level sixteen.
        asi_19: Ability score improvements selected at Sorcerer level nineteen.
        equipment_preset: Starter equipment preset equipped by the Sorcerer factory.
        spell_names: Explicit spell names registered by the Sorcerer factory; defaults are level-derived.
    """

    level: int = Field(
        ge=1,
        le=20,
        default=1,
        description="Sorcerer level used to gate spellcasting, metamagic, resources, and required ASIs.",
    )
    name: str = Field(default="Sorcerer", description="Display name for the created sorcerer entity.")
    position: Tuple[int, int] = Field(
        default=(0, 0),
        description="Initial grid position for the created sorcerer entity.",
    )
    faction: Optional[str] = Field(default=None, description="Faction identifier. None = enemy to everyone")

    base_strength: int = Field(
        default=8,
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
        default=15,
        ge=8,
        le=15,
        description="Base Charisma score before level-one bonuses and ASI choices.",
    )

    bonus_plus_2: AbilityName = Field(
        default="charisma",
        description="Ability that receives the level-one +2 bonus.",
    )
    bonus_plus_1: AbilityName = Field(
        default="constitution",
        description="Ability that receives the level-one +1 bonus.",
    )

    origin: SorcererOriginChoice = Field(
        default=SorcererOriginChoice.DRACONIC_BLOODLINE,
        description="Sorcerous origin applied by the factory.",
    )
    draconic_damage_type: str = Field(
        default="Fire",
        description="Damage type used by Draconic Bloodline Elemental Affinity.",
    )

    metamagic_choices: Optional[List[str]] = Field(
        default=None,
        description="Metamagic choices required by the factory at levels three and above.",
    )

    asi_4: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Sorcerer level four.",
    )
    asi_8: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Sorcerer level eight.",
    )
    asi_12: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Sorcerer level twelve.",
    )
    asi_16: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Sorcerer level sixteen.",
    )
    asi_19: Optional[List[Tuple[AbilityName, int]]] = Field(
        default=None,
        description="Ability score improvements selected at Sorcerer level nineteen.",
    )

    equipment_preset: SorcererEquipmentPreset = Field(
        default="dagger",
        description="Starter equipment preset equipped by the Sorcerer factory.",
    )

    spell_names: Optional[List[str]] = Field(
        default=None,
        description="Explicit spell names registered by the Sorcerer factory; defaults are level-derived.",
    )

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

    scores[config.bonus_plus_2] += 2
    scores[config.bonus_plus_1] += 1

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


def apply_sorcerer_features(entity: Entity, config: SorcererConfig) -> None:
    """Apply all Sorcerer features appropriate for the level."""
    level = config.level

    if config.origin == SorcererOriginChoice.DRACONIC_BLOODLINE:
        entity.add_condition(DraconicResilience(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            hp_bonus=level,
        ))

    if level >= 2:
        metamagic = config.metamagic_choices or []
        entity.add_condition(SorceryPointsFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            sorcery_points=get_sorcery_points(level),
            metamagic_choices=metamagic,
        ))

    if level >= 6 and config.origin == SorcererOriginChoice.DRACONIC_BLOODLINE:
        entity.add_condition(ElementalAffinity(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            damage_type=DamageType(config.draconic_damage_type),
        ))


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

    final_scores = calculate_final_ability_scores(config)

    prof_bonus = get_proficiency_bonus(config.level)

    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=final_scores["strength"]),
        dexterity=AbilityConfig(ability_score=final_scores["dexterity"]),
        constitution=AbilityConfig(ability_score=final_scores["constitution"]),
        intelligence=AbilityConfig(ability_score=final_scores["intelligence"]),
        wisdom=AbilityConfig(ability_score=final_scores["wisdom"]),
        charisma=AbilityConfig(ability_score=final_scores["charisma"]),
    )

    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=6,
            hit_dice_count=config.level,
            mode="average",
            ignore_first_level=False,
        )]
    )

    action_economy_config = ActionEconomyConfig(
        spell_slots=get_sorcerer_spell_slots(config.level),
    )

    spellcasting_config = SpellcastingConfig(
        spellcasting_ability="charisma",
    )

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
        appearance=AppearanceConfig(
            body_category="NakedBody",
            skin_tint=0xE6BC98,
            head_category="Head9",
            hair_tint=0x993F00,
            has_beard=False,
            beard_tint=0,
        ),
    )

    origin_name = f" ({config.origin.value.replace('_', ' ').title()})" if config.origin else ""
    entity = Entity.create(
        name=config.name,
        source_entity_uuid=source_id,
        description=f"Level {config.level} Sorcerer{origin_name}",
        config=entity_config,
    )

    setup_standard_actions(entity)

    apply_equipment(entity, config.equipment_preset)
    entity.equipment.equip(create_robes(entity.uuid, visual_variant_id="81000005"))
    entity.equipment.equip(create_cloth_shoes(entity.uuid, visual_variant_id="b0000004"))

    apply_sorcerer_features(entity, config)

    spell_list = config.spell_names or get_default_spells(config.level)
    register_spells_by_name(entity, spell_list, caster_level=config.level)

    register_shield_reaction(entity)

    entity.loot_item(create_potion_of_haste(entity.uuid))
    entity.loot_item(create_healing_potion(entity.uuid))
    entity.loot_item(create_healing_potion(entity.uuid))
    entity.loot_item(create_robes(entity.uuid, visual_variant_id="81000001"))
    entity.loot_item(create_cloth_shoes(entity.uuid, visual_variant_id="b0000005"))
    entity.loot_item(create_wizard_hat(entity.uuid, visual_variant_id="h0000011"))

    equipped_names = {i.name for i in entity.equipment.get_all_equipped_items()}
    if "Dagger" not in equipped_names:
        entity.loot_item(create_dagger(entity.uuid))
    if "Quarterstaff" not in equipped_names:
        entity.loot_item(create_quarterstaff(entity.uuid))

    return entity

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
