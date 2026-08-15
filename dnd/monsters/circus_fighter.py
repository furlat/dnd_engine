"""Retained NeuroDragon circus-warrior construction."""

from uuid import UUID, uuid4

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import (
    BodyArmor,
    EquipmentConfig,
    Weapon,
)
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.saving_throws import SavingThrowConfig, SavingThrowSetConfig
from dnd.blocks.skills import SkillConfig, SkillSetConfig
from dnd.conditions import Blinded
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.types.damage import DamageType
from dnd.types.equipment import WeaponSlot
from dnd.entity import Entity, EntityConfig
from dnd.monsters.circus_fighter_conditions import (
    CircusPerformer,
    DualWielder,
    ElementalAffinity,
    ElementalWeaponMastery,
)
from dnd.monsters.circus_fighter_items import (
    FLAMING_SCIMITAR_RECIPE,
    PERFORMER_LEATHER_RECIPE,
    RUSTY_DAGGER_RECIPE,
)
from dnd.actions.reactions import add_opportunity_attack_handler


def create_warrior(
    source_id: UUID | None = None,
    proficiency_bonus: int = 0,
    name: str = "Ganger",
    blinded: bool = False,
    position: tuple[int, int] = (0, 0),
    sprite_name: str | None = None,
) -> Entity:
    """Creates a level 4 fighter character with a past in the circus and spiked claws for hands"""
    if source_id is None:
        source_id = uuid4()

    strength_config = AbilityConfig(
        ability_score=15,
        ability_scores_modifiers=[("level 4 talent", 1)],
        modifier_bonus=1,
        modifier_bonus_modifiers=[],
    )
    dexterity_config = AbilityConfig(ability_score=12)
    constitution_config = AbilityConfig(
        ability_score=15, ability_scores_modifiers=[("level 4 talent", 1)]
    )
    intelligence_config = AbilityConfig(ability_score=10)
    wisdom_config = AbilityConfig(ability_score=10)
    charisma_config = AbilityConfig(ability_score=10)
    ability_scores_config = AbilityScoresConfig(
        strength=strength_config,
        dexterity=dexterity_config,
        constitution=constitution_config,
        intelligence=intelligence_config,
        wisdom=wisdom_config,
        charisma=charisma_config,
    )

    acrobatics_config = SkillConfig(expertise=True, proficiency=True)
    history_config = SkillConfig(expertise=False, proficiency=False)
    skill_set_config = SkillSetConfig(
        acrobatics=acrobatics_config, history=history_config
    )

    strength_st_config = SavingThrowConfig(proficiency=True)
    intelligence_st_config = SavingThrowConfig()
    saving_throw_set_config = SavingThrowSetConfig(
        strength_saving_throw=strength_st_config,
        intelligence_saving_throw=intelligence_st_config,
    )

    warrior_hitpoints_config = HitDiceConfig(
        hit_dice_value=10, hit_dice_count=4, mode="average", ignore_first_level=False
    )
    gang_hitpoints_config = HitDiceConfig(
        hit_dice_value=8, hit_dice_count=1, mode="average", ignore_first_level=True
    )
    health_config = HealthConfig(
        hit_dices=[warrior_hitpoints_config, gang_hitpoints_config],
        damage_reduction=1,
        temporary_hit_points_modifiers=[("permanentfalse_life", 10)],
    )

    action_economy_config = ActionEconomyConfig()

    equipment_config = EquipmentConfig(
        unarmed_damage_type=DamageType.PIERCING,
    )

    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        skill_set=skill_set_config,
        saving_throws=saving_throw_set_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        proficiency_bonus=proficiency_bonus,
        sprite_name=sprite_name,
        position=position,
    )

    description = """A level 4 fighter character with a past in the circus and spiked claws for hands."""
    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        description=description,
        config=entity_config,
    )

    dagger = materialize_item(
        RUSTY_DAGGER_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    flaming_scimitar = materialize_item(
        FLAMING_SCIMITAR_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    light_armor = materialize_item(
        PERFORMER_LEATHER_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )

    entity.equipment.equip(light_armor)
    entity.equipment.equip(flaming_scimitar, WeaponSlot.MELEE_MAIN)
    entity.equipment.equip(dagger, WeaponSlot.MELEE_OFF)

    dual_wielder = DualWielder(
        source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid
    )
    elemental_mastery = ElementalWeaponMastery(
        source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid
    )
    elemental_affinity = ElementalAffinity(
        source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid
    )
    circus_performer = CircusPerformer(
        source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid
    )

    entity.add_condition(dual_wielder)
    entity.add_condition(elemental_mastery)
    entity.add_condition(elemental_affinity)
    entity.add_condition(circus_performer)

    if blinded:
        blinded_condition = Blinded(
            source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid
        )
        entity.add_condition(blinded_condition)

    add_opportunity_attack_handler(entity)
    return entity
