"""Manual Chapter 07 checks for entity composition."""

from uuid import uuid4

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.saving_throws import SavingThrowConfig, SavingThrowSetConfig
from dnd.blocks.skills import SkillConfig, SkillSetConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.gridmap import get_map
from dnd.core.modifiers import CreatureType, Size
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.utils import reset_combat_state


def reset_entity_state() -> None:
    """Clear global state touched by entity composition examples."""
    reset_combat_state()
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()


def create_tutorial_hero() -> Entity:
    """Create the configured actor used by this chapter."""
    hero_id = uuid4()
    hero_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=14),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=12),
            charisma=AbilityConfig(ability_score=18),
        ),
        skill_set=SkillSetConfig(
            athletics=SkillConfig(skill_bonus=1, proficiency=True, expertise=True),
            perception=SkillConfig(skill_bonus=2, proficiency=True),
        ),
        saving_throws=SavingThrowSetConfig(
            dexterity_saving_throw=SavingThrowConfig(proficiency=True, bonus=1),
            wisdom_saving_throw=SavingThrowConfig(proficiency=True),
        ),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(hit_dice_value=8, hit_dice_count=3, mode="maximums")
            ],
            max_hit_points_bonus=2,
            temporary_hit_points=5,
        ),
        action_economy=ActionEconomyConfig(
            movement=35,
            spell_slots={1: 2, 3: 1},
        ),
        spellcasting=SpellcastingConfig(
            spellcasting_ability="charisma",
            spell_attack_modifiers=[("Wand", 2)],
            spell_dc_modifiers=[("Focus", 1)],
            spell_damage_modifiers=[("Elemental Affinity", 4)],
        ),
        proficiency_bonus=3,
        initiative_modifiers=[("Alert", 5)],
        position=(2, 3),
        faction="heroes",
        weight=180,
        creature_type=CreatureType.HUMANOID,
        size=Size.MEDIUM,
    )

    return Entity.create(
        source_entity_uuid=hero_id,
        name="Tutorial Hero",
        config=hero_config,
    )


def test_configured_entity_registers_identity_position_and_blocks() -> None:
    """A configured entity is registered as an actor, block, and map occupant."""
    reset_entity_state()

    hero = create_tutorial_hero()

    assert hero.uuid == hero.source_entity_uuid
    assert hero.name == "Tutorial Hero"
    assert Entity.get(hero.uuid) is hero
    assert BaseBlock.get(hero.uuid) is hero
    assert hero in Entity.get_all_entities_at_position((2, 3))
    assert get_map().get_entity_position(hero.uuid) == (2, 3)

    owned_blocks = [
        hero.ability_scores,
        hero.skill_set,
        hero.saving_throws,
        hero.health,
        hero.equipment,
        hero.action_economy,
        hero.senses,
        hero.inventory,
        hero.appearance,
        hero.spellcasting,
    ]

    assert all(block.source_entity_uuid == hero.uuid for block in owned_blocks)
    assert hero.ability_scores.strength.source_entity_uuid == hero.uuid
    assert hero.skill_set.athletics.source_entity_uuid == hero.uuid
    assert hero.saving_throws.dexterity_saving_throw.source_entity_uuid == hero.uuid
    assert hero.senses.position == (2, 3)


def test_entity_methods_compose_abilities_skills_saves_and_passives() -> None:
    """Entity-level methods combine abilities, proficiency, and configured bonuses."""
    reset_entity_state()

    hero = create_tutorial_hero()

    assert hero.ability_scores.get_modifier_from_name("strength") == 3
    assert hero.ability_scores.get_modifier_from_name("dexterity") == 2
    assert hero.ability_scores.get_modifier_from_name("constitution") == 2
    assert hero.ability_scores.get_modifier_from_name("charisma") == 4
    assert hero.proficiency_bonus.normalized_score == 3
    assert hero.initiative.normalized_score == 7

    assert hero.skill_bonus(None, "athletics").normalized_score == 10
    assert hero.skill_bonus(None, "perception").normalized_score == 6
    assert hero.saving_throw_bonus(None, "dexterity").normalized_score == 6
    assert hero.passive_skill("athletics") == 20
    assert hero.get_passive_perception() == 16


def test_entity_methods_compose_health_actions_and_spellcasting() -> None:
    """Health, turn resources, slots, and spellcasting surface through the entity."""
    reset_entity_state()

    hero = create_tutorial_hero()

    assert hero.get_max_hp() == 32
    assert hero.get_hp() == 37
    assert hero.health.temporary_hit_points.normalized_score == 5

    assert hero.action_economy.actions.normalized_score == 1
    assert hero.action_economy.bonus_actions.normalized_score == 1
    assert hero.action_economy.reactions.normalized_score == 1
    assert hero.action_economy.movement.normalized_score == 35
    assert hero.action_economy.spell_slot_1.normalized_score == 2
    assert hero.action_economy.spell_slot_2.normalized_score == 0
    assert hero.action_economy.spell_slot_3.normalized_score == 1

    assert hero.is_spellcaster is True
    assert hero.spell_save_dc() == 16
    assert hero.spell_attack_bonus().normalized_score == 9
    assert hero.get_spell_damage_bonus().normalized_score == 4


def test_entity_position_updates_stay_in_sync() -> None:
    """The official movement helper updates the entity, senses, index, and map."""
    reset_entity_state()

    hero = create_tutorial_hero()

    Entity.update_entity_position(hero, (4, 5))

    assert hero.position == (4, 5)
    assert hero.senses.position == (4, 5)
    assert hero not in Entity.get_all_entities_at_position((2, 3))
    assert hero in Entity.get_all_entities_at_position((4, 5))
    assert get_map().get_entity_position(hero.uuid) == (4, 5)
