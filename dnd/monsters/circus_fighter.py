from dnd.core.modifiers import NumericalModifier, DamageType

from dnd.blocks.base_block import BaseBlock
from dnd.blocks.abilities import (AbilityConfig,AbilityScoresConfig, AbilityScores,AbilityName)
from dnd.blocks.saving_throws import (SavingThrowConfig,SavingThrowSetConfig,SavingThrowSet)
from dnd.blocks.health import (HealthConfig,Health,HitDiceConfig)
from dnd.blocks.equipment import (EquipmentConfig,Equipment,WeaponSlot,RangeType,WeaponProperty, Range, Shield)
from dnd.blocks.action_economy import (ActionEconomyConfig,ActionEconomy)
from dnd.blocks.skills import (SkillSetConfig,SkillSet,SkillName,SkillConfig)

from dnd.entity import Entity, EntityConfig
    
from uuid import uuid4, UUID
from typing import Optional



#realistic scores for a level 4 fighter character with a past in the circus and spiked claws for hands
# setting up configs
# Ability scores
def create_warrior(source_id: UUID=uuid4(),proficiency_bonus: int=0) -> Entity:
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
    entity = Entity.create(name="Gang Member", source_entity_uuid=source_id, description=description, config=entity_config)
    
    #here we can equip some gear later

    return entity


if __name__ == "__main__":
    source_id = uuid4()
    proficiency_bonus = 2
    entity = create_warrior(source_id,proficiency_bonus)
    print(entity)
