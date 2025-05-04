from dnd.core.modifiers import NumericalModifier, DamageType
from dnd.core.values import ModifiableValue
from dnd.blocks.base_block import BaseBlock
from dnd.blocks.abilities import (AbilityConfig,AbilityScoresConfig, AbilityScores)
from dnd.blocks.saving_throws import (SavingThrowConfig,SavingThrowSetConfig,SavingThrowSet)
from dnd.blocks.health import (HealthConfig,Health,HitDiceConfig)
from dnd.blocks.equipment import (EquipmentConfig,Equipment,WeaponSlot,WeaponProperty, Range, Shield, Weapon, BodyArmor, ArmorType, BodyPart)
from dnd.blocks.action_economy import (ActionEconomyConfig,ActionEconomy)
from dnd.blocks.skills import (SkillSetConfig,SkillSet,SkillConfig)
from dnd.core.events import SavingThrowEvent,RangeType, AbilityName, SkillName

from dnd.entity import Entity, EntityConfig
    
from uuid import uuid4, UUID
from typing import Optional

def create_dagger(source_id: UUID) -> Weapon:
    """Creates a standard dagger weapon"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Dagger",
        description="A well-balanced dagger with an ornate hilt, perfect for quick strikes and acrobatic maneuvers. Its blade gleams with a performer's polish.",
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

#realistic scores for a level 4 fighter character with a past in the circus and spiked claws for hands
# setting up configs
# Ability scores
def create_warrior(source_id: UUID=uuid4(),proficiency_bonus: int=0, name: str="Ganger") -> Entity:
    strength_config = AbilityConfig(ability_score=15, ability_scores_modifiers=[("level 4 talent",1)], modifier_bonus=1, modifier_bonus_modifiers=[])
    dexterity_config = AbilityConfig(ability_score=12)
    constitution_config = AbilityConfig(ability_score=15, ability_scores_modifiers=[("level 4 talent",1)])
    intelligence_config = AbilityConfig(ability_score=10)
    wisdom_config = AbilityConfig(ability_score=10)
    charisma_config = AbilityConfig(ability_score=10)
    ability_scores_config = AbilityScoresConfig(strength=strength_config, dexterity=dexterity_config, constitution=constitution_config, intelligence=intelligence_config, wisdom=wisdom_config, charisma=charisma_config)

    # Skills
    acrobatics_config = SkillConfig(skill_bonus = 0, skill_bonus_modifiers=[("a past in the circus", 7)],expertise = True, proficiency = True)
    history_config = SkillConfig(skill_bonus = 0, skill_bonus_modifiers=[("a past in the circus", -2)],expertise = False, proficiency = False)
    skill_set_config = SkillSetConfig(acrobatics=acrobatics_config, history=history_config)

    # Saving throws
    strength_st_config = SavingThrowConfig(bonus_modifiers=[("a past in the circus", 1)],proficiency=True)
    intelligence_st_config = SavingThrowConfig(bonus_modifiers=[("a past in the circus", -1)])

    saving_throw_set_config = SavingThrowSetConfig(strength_saving_throw=strength_st_config, intelligence_saving_throw=intelligence_st_config)

    #Health
    warrior_hitpoints_config = HitDiceConfig(hit_dice_value=10,hit_dice_count=4,mode="average", ignore_first_level=False)
    gang_hitpoints_config = HitDiceConfig(hit_dice_value=8,hit_dice_count=1,mode="average", ignore_first_level=True)

    health_config = HealthConfig(hit_dices=[warrior_hitpoints_config,gang_hitpoints_config],
                                damage_reduction=1,
                                resistances=[DamageType.FIRE],
                                vulnerabilities=[DamageType.COLD],
                                temporary_hit_points_modifiers=[("permanentfalse_life", 10)],
                                )

    #Action economy
    action_economy_config = ActionEconomyConfig(
        reactions_modifiers=[("a past in the circus", 2)],)

    #Equipment
    equipment_config = EquipmentConfig(
        ac_bonus_modifiers=[("a past in the circus", 1)],
        unarmed_damage_bonus=1,
        unarmed_damage_type=DamageType.PIERCING,
        unarmed_damage_bonus_modifiers=[("a past in the circus", 1)],
        )

    #wrapp into entity config
    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        skill_set=skill_set_config,
        saving_throws=saving_throw_set_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        proficiency_bonus=proficiency_bonus,
        proficiency_bonus_modifiers=[("a past in the circus", -1)],
        )
    
    description = "A level 4 fighter character with a past in the circus and spiked claws for hands"
    entity = Entity.create(name=name, source_entity_uuid=source_id, description=description, config=entity_config)
    
    # Create and equip weapons and armor
    dagger = create_dagger(source_id)
    flaming_scimitar = create_flaming_scimitar(source_id)
    light_armor = create_light_armor(source_id)
    
    # Equip the items
    entity.equipment.equip(light_armor)  # Equip the light armor
    entity.equipment.equip(flaming_scimitar, WeaponSlot.MAIN_HAND)  # Equip the scimitar in main hand
    entity.equipment.equip(dagger, WeaponSlot.OFF_HAND)  # Equip the dagger in off hand

    return entity

if __name__ == "__main__":
    source_id = uuid4()
    proficiency_bonus = 2
    entity = create_warrior(source_id,proficiency_bonus)
    print(entity)
