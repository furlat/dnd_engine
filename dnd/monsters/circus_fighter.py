from dnd.core.modifiers import NumericalModifier, DamageType, AdvantageModifier, AdvantageStatus
from dnd.core.values import ModifiableValue
from dnd.blocks.base_block import BaseBlock
from dnd.blocks.abilities import (AbilityConfig,AbilityScoresConfig, AbilityScores)
from dnd.blocks.saving_throws import (SavingThrowConfig,SavingThrowSetConfig,SavingThrowSet)
from dnd.blocks.health import (HealthConfig,Health,HitDiceConfig)
from dnd.blocks.equipment import (EquipmentConfig,Equipment,WeaponSlot,WeaponProperty, Range, Shield, Weapon, BodyArmor, ArmorType, BodyPart)
from dnd.blocks.action_economy import (ActionEconomyConfig,ActionEconomy)
from dnd.blocks.skills import (SkillSetConfig,SkillSet,SkillConfig)
from dnd.core.events import SavingThrowEvent,RangeType, AbilityName, SkillName
from dnd.conditions import Blinded
from dnd.monsters.circus_fighter_conditions import (
    DualWielder, ElementalWeaponMastery, ElementalAffinity, CircusPerformer
)

from dnd.entity import Entity, EntityConfig
    
from uuid import uuid4, UUID
from typing import Optional

def create_dagger(source_id: UUID) -> Weapon:
    """Creates a rusty dagger weapon with disadvantage"""
    dagger = Weapon(
        source_entity_uuid=source_id,
        name="Rusty Dagger",
        description="A poorly maintained dagger with a rusty blade. The ornate hilt is still beautiful, but the blade has seen better days, making it harder to strike accurately.",
        damage_dice=4,  # d4
        dice_numbers=1,  # 1d4
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT, WeaponProperty.THROWN],
        range=Range(type=RangeType.REACH, normal=5),
        # Initialize empty lists for extra damage
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[],
        # Initialize attack bonus with the same source_id
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=0,
            value_name="Attack Bonus"
        )
    )
    
    # Add static disadvantage to the attack bonus
    dagger.attack_bonus.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=source_id,
            target_entity_uuid=None,  # No specific target
            name="Rusty Blade",
            value=AdvantageStatus.DISADVANTAGE
        )
    )
    
    return dagger

def create_flaming_scimitar(source_id: UUID) -> Weapon:
    """Creates a magical flaming scimitar with extra fire damage"""
    # Create the base weapon
    return Weapon(
        source_entity_uuid=source_id,
        name="Flaming Scimitar",
        description="An elegant curved blade enchanted with magical flames. The blade dances with fire during performances, leaving trails of light in its wake. The flames intensify when the wielder performs acrobatic maneuvers.",
        damage_dice=6,  # d6
        dice_numbers=1,  # 1d6
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT],
        range=Range(type=RangeType.REACH, normal=5),
        # Initialize attack bonus with the same source_id
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=0,
            value_name="Attack Bonus"
        ),
        # Add the extra fire damage - all lists must be the same length
        extra_damage_dices=[6],  # d6 fire damage
        extra_damage_dices_numbers=[1],  # 1d6
        extra_damage_bonus=[ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=0,
            value_name="Fire Damage Bonus"
        )],
        extra_damage_type=[DamageType.FIRE]
    )

def create_light_armor(source_id: UUID) -> BodyArmor:
    """Creates a set of light armor suitable for an acrobatic fighter"""
    return BodyArmor(
        source_entity_uuid=source_id,
        name="Performer's Leather Armor",
        description="A masterfully crafted set of leather armor adorned with intricate circus motifs. The armor is specially designed to allow maximum flexibility for acrobatic performances while providing protection. Gold and silver thread accents catch the light during movement.",
        type=ArmorType.LIGHT,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=11,
            value_name="Armor Class"
        ),
        max_dex_bonus=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=5,
            value_name="Max Dex Bonus"
        )
    )

def create_longsword_plus_one(source_id: UUID) -> Weapon:
    """Creates a magical +1 longsword"""
    weapon = Weapon(
        source_entity_uuid=source_id,
        name="Longsword +1",
        description="A finely crafted magical longsword that grants a +1 bonus to attack and damage rolls.",
        damage_dice=8,  # d8
        dice_numbers=1,  # 1d8
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.VERSATILE],
        range=Range(type=RangeType.REACH, normal=5),
        # Initialize attack bonus with +1
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=1,
            value_name="Attack Bonus"
        ),
        # Initialize damage bonus with +1
        damage_bonus=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=1,
            value_name="Damage Bonus"
        ),
        # Initialize empty lists for extra damage since this weapon doesn't have any
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )
    return weapon

def create_self_blinded(source_id: UUID) -> Blinded:
    blinded = Blinded(source_entity_uuid=source_id, target_entity_uuid=source_id)
    return blinded

    


def create_morningstar(source_id: UUID) -> Weapon:
    """Creates a morningstar with necrotic damage"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Soul-Draining Morningstar",
        description="A wicked morningstar imbued with necrotic energy that drains the life force of its victims.",
        damage_dice=8,  # d8
        dice_numbers=1,  # 1d8
        damage_type=DamageType.PIERCING,
        properties=[],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=0,
            value_name="Attack Bonus"
        ),
        # Add necrotic damage
        extra_damage_dices=[4],  # d4
        extra_damage_dices_numbers=[1],  # 1d4
        extra_damage_bonus=[ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=0,
            value_name="Necrotic Damage"
        )],
        extra_damage_type=[DamageType.NECROTIC]
    )

#realistic scores for a level 4 fighter character with a past in the circus and spiked claws for hands
# setting up configs
# Ability scores
def create_warrior(source_id: UUID=uuid4(),proficiency_bonus: int=0, name: str="Ganger",blinded: bool=False) -> Entity:
    """Creates a level 4 fighter character with a past in the circus and spiked claws for hands"""
    # Ability scores
    strength_config = AbilityConfig(ability_score=15, ability_scores_modifiers=[("level 4 talent",1)], modifier_bonus=1, modifier_bonus_modifiers=[])
    dexterity_config = AbilityConfig(ability_score=12)
    constitution_config = AbilityConfig(ability_score=15, ability_scores_modifiers=[("level 4 talent",1)])
    intelligence_config = AbilityConfig(ability_score=10)
    wisdom_config = AbilityConfig(ability_score=10)
    charisma_config = AbilityConfig(ability_score=10)
    ability_scores_config = AbilityScoresConfig(strength=strength_config, dexterity=dexterity_config, constitution=constitution_config, intelligence=intelligence_config, wisdom=wisdom_config, charisma=charisma_config)

    # Skills - only keep proficiency settings, modifiers will come from CircusPerformer condition
    acrobatics_config = SkillConfig(expertise=True, proficiency=True)
    history_config = SkillConfig(expertise=False, proficiency=False)
    skill_set_config = SkillSetConfig(acrobatics=acrobatics_config, history=history_config)

    # Saving throws - only keep proficiency settings, modifiers will come from CircusPerformer condition
    strength_st_config = SavingThrowConfig(proficiency=True)
    intelligence_st_config = SavingThrowConfig()
    saving_throw_set_config = SavingThrowSetConfig(strength_saving_throw=strength_st_config, intelligence_saving_throw=intelligence_st_config)

    # Health
    warrior_hitpoints_config = HitDiceConfig(hit_dice_value=10,hit_dice_count=4,mode="average", ignore_first_level=False)
    gang_hitpoints_config = HitDiceConfig(hit_dice_value=8,hit_dice_count=1,mode="average", ignore_first_level=True)
    health_config = HealthConfig(hit_dices=[warrior_hitpoints_config,gang_hitpoints_config],
                                damage_reduction=1,
                                temporary_hit_points_modifiers=[("permanentfalse_life", 10)],
                                )

    # Action economy - base values only, modifiers will come from CircusPerformer condition
    action_economy_config = ActionEconomyConfig()

    # Equipment - base values only, modifiers will come from CircusPerformer condition
    equipment_config = EquipmentConfig(
        unarmed_damage_type=DamageType.PIERCING,
    )

    # Entity config - no modifiers here, they'll come from conditions
    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        skill_set=skill_set_config,
        saving_throws=saving_throw_set_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        proficiency_bonus=proficiency_bonus,
        )
    
    description = """A level 4 fighter character with a past in the circus and spiked claws for hands."""
    entity = Entity.create(name=name, source_entity_uuid=source_id, description=description, config=entity_config)
    
    # Create and equip weapons and armor
    dagger = create_dagger(entity.uuid)
    flaming_scimitar = create_flaming_scimitar(entity.uuid)
    light_armor = create_light_armor(entity.uuid)
    longsword = create_longsword_plus_one(entity.uuid)
    morningstar = create_morningstar(entity.uuid)

    entity.equipment.equip(light_armor)
    entity.equipment.equip(flaming_scimitar, WeaponSlot.MAIN_HAND)
    entity.equipment.equip(dagger, WeaponSlot.OFF_HAND)

    # Add conditions
    dual_wielder = DualWielder(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    elemental_mastery = ElementalWeaponMastery(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    elemental_affinity = ElementalAffinity(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    circus_performer = CircusPerformer(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)

    entity.add_condition(dual_wielder)
    entity.add_condition(elemental_mastery)
    entity.add_condition(elemental_affinity)
    entity.add_condition(circus_performer)

    if blinded:
        blinded_condition = Blinded(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
        entity.add_condition(blinded_condition)

    return entity

if __name__ == "__main__":
    source_id = uuid4()
    proficiency_bonus = 2
    entity = create_warrior(source_id,proficiency_bonus)
