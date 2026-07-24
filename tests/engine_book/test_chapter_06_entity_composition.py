"""Engine book parity tests for entity composition."""

from contextlib import contextmanager
from typing import Iterator
from unittest.mock import patch
from uuid import uuid4
import random

from dnd.actions import Attack
from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig, RechargeType
from dnd.core.equipment_types import WeaponSlot
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.saving_throws import SavingThrowConfig, SavingThrowSetConfig
from dnd.blocks.skills import SkillConfig, SkillSetConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import DurationType
from dnd.core.base_object import BaseObject
from dnd.core.dice import AttackOutcome, RollType
from dnd.core.events import (
    EventPhase,
    EventQueue,
    EventType,
    SavingThrowD20RollResultEvent,
    SavingThrowEvent,
    SkillCheckD20RollResultEvent,
    SkillCheckEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.core.modifiers import CreatureType, DamageType, NumericalModifier, Size
from dnd.core.values import AdvantageStatus, BaseValue, ModifiableValue
from dnd.conditions import Exhaustion
from dnd.entity import Entity, EntityConfig
from dnd.items.weapons import create_shortsword
from dnd.spells.evocation import FireBolt
from dnd.utils import get_max_hp, reset_combat_state


def reset_entity_state() -> None:
    """Clear global state touched by these entity examples."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()


@contextmanager
def fixed_randint(*results: int) -> Iterator[None]:
    """Temporarily replace random.randint with a deterministic sequence."""
    queued = list(results)
    original_randint = random.randint

    def deterministic_randint(low: int, high: int) -> int:
        if not queued:
            raise AssertionError("No deterministic random values left")
        value = queued.pop(0)
        assert low <= value <= high
        return value

    random.randint = deterministic_randint
    try:
        yield
    finally:
        random.randint = original_randint


def configured_entity(
    name: str = "Engine Book Hero",
    position: tuple[int, int] = (2, 3),
    faction: str | None = "heroes",
) -> Entity:
    """Create a deterministic entity with non-default composition."""
    source_uuid = uuid4()
    config = EntityConfig(
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
        position=position,
        faction=faction,
        weight=180,
        creature_type=CreatureType.HUMANOID,
        size=Size.MEDIUM,
    )
    return Entity.create(source_entity_uuid=source_uuid, name=name, config=config)


def entity_action_target_uuids(entity: Entity, template_name: str, target_filter: str) -> set:
    """Return valid entity target UUIDs for a named available action."""
    available = entity.get_available_actions(target_filter=target_filter)
    for action in available.entity_actions:
        if action.template_name == template_name:
            return {target.target_uuid for target in action.valid_targets}
    return set()


def test_eb_06_001_entity_create_wires_identity_registries_and_blocks() -> None:
    """EB-06-001: Entity.create builds an entity and all core blocks."""
    reset_entity_state()
    entity = configured_entity()

    assert entity.uuid == entity.source_entity_uuid
    assert Entity.get(entity.uuid) is entity
    assert BaseBlock.get(entity.uuid) is entity
    assert entity in Entity.get_all_entities_at_position((2, 3))
    assert get_map().get_entity_position(entity.uuid) == (2, 3)

    top_level_blocks = [
        entity.ability_scores,
        entity.skill_set,
        entity.saving_throws,
        entity.health,
        entity.equipment,
        entity.action_economy,
        entity.senses,
        entity.inventory,
        entity.appearance,
        entity.spellcasting,
    ]
    assert {block.uuid for block in top_level_blocks}.issubset(
        {block.uuid for block in entity.get_blocks()}
    )
    assert all(block.source_entity_uuid == entity.uuid for block in top_level_blocks)
    assert entity.ability_scores.strength.source_entity_uuid == entity.uuid
    assert entity.skill_set.athletics.source_entity_uuid == entity.uuid
    assert entity.saving_throws.dexterity_saving_throw.source_entity_uuid == entity.uuid
    assert entity.senses.position == (2, 3)
    assert entity.faction == "heroes"
    assert entity.weight == 180


def test_eb_06_002_abilities_skills_saves_and_passives_compose() -> None:
    """EB-06-002: entity methods combine abilities, proficiency, and bonuses."""
    reset_entity_state()
    entity = configured_entity()

    assert entity.ability_scores.get_modifier_from_name("strength") == 3
    assert entity.ability_scores.get_modifier_from_name("dexterity") == 2
    assert entity.ability_scores.get_modifier_from_name("charisma") == 4
    assert entity.proficiency_bonus.normalized_score == 3
    assert entity.initiative.normalized_score == 7

    athletics = entity.skill_bonus(None, "athletics")
    perception = entity.skill_bonus(None, "perception")
    dex_save = entity.saving_throw_bonus(None, "dexterity")
    self_targeted_athletics = entity.skill_bonus(entity.uuid, "athletics")
    self_targeted_dex_save = entity.saving_throw_bonus(entity.uuid, "dexterity")

    assert athletics.normalized_score == 10
    assert entity.passive_skill("athletics") == 20
    assert perception.normalized_score == 6
    assert entity.get_passive_perception() == 16
    assert dex_save.normalized_score == 6
    assert self_targeted_athletics.normalized_score == athletics.normalized_score
    assert self_targeted_dex_save.normalized_score == dex_save.normalized_score


def test_eb_06_003_health_action_economy_and_spellcasting_compose() -> None:
    """EB-06-003: health, slots, and spellcasting are entity-level composites."""
    reset_entity_state()
    entity = configured_entity()

    assert entity.get_hp() == 37
    assert entity.action_economy.actions.normalized_score == 1
    assert entity.action_economy.bonus_actions.normalized_score == 1
    assert entity.action_economy.reactions.normalized_score == 1
    assert entity.action_economy.movement.normalized_score == 35

    assert entity.has_spell_slot(1) is True
    assert entity.has_spell_slot(2) is False
    assert entity.has_spell_slot(3) is True
    assert entity.get_lowest_spell_slot(2) == 3
    assert entity.is_spellcaster is True

    assert entity.spell_save_dc() == 16
    assert entity.spell_attack_bonus().normalized_score == 9
    assert entity.get_spell_damage_bonus().normalized_score == 4


def test_eb_06_004_action_economy_resources_recharge_by_type() -> None:
    """EB-06-004: entity action economy owns reusable named resources."""
    reset_entity_state()
    entity = configured_entity()
    economy = entity.action_economy

    economy.add_resource("second_wind", maximum=1, recharge_type=RechargeType.SHORT_REST)
    economy.add_resource("daily_power", maximum=1, recharge_type=RechargeType.LONG_REST)
    economy.add_resource("turn_pulse", maximum=2, recharge_type=RechargeType.TURN_START)

    assert economy.can_afford_resource("second_wind") is True
    assert economy.consume_resource("second_wind") is True
    assert economy.consume_resource("daily_power") is True
    assert economy.get_resource_current("second_wind") == 0
    assert economy.get_resource_current("daily_power") == 0
    economy.on_short_rest()
    assert economy.get_resource_current("second_wind") == 1
    assert economy.get_resource_current("daily_power") == 0

    assert economy.consume_resource("second_wind") is True
    economy.on_long_rest()
    assert economy.get_resource_current("second_wind") == 1
    assert economy.get_resource_current("daily_power") == 1

    assert economy.consume_resource("turn_pulse", 2) is True
    assert economy.get_resource_current("turn_pulse") == 0
    economy.on_turn_start()
    assert economy.get_resource_current("turn_pulse") == 2


def test_eb_06_005_factions_define_allies_and_enemies() -> None:
    """EB-06-005: faction logic drives ally/enemy classification."""
    reset_entity_state()
    hero = configured_entity("Hero", (0, 0), "heroes")
    ally = configured_entity("Ally", (1, 0), "heroes")
    enemy = configured_entity("Enemy", (2, 0), "monsters")
    neutral = configured_entity("Neutral", (3, 0), None)

    assert hero.is_ally(hero) is True
    assert hero.is_enemy(hero) is False
    assert hero.is_ally(ally) is True
    assert hero.is_enemy(ally) is False
    assert hero.is_ally(enemy) is False
    assert hero.is_enemy(enemy) is True
    assert hero.is_ally(neutral) is False
    assert hero.is_enemy(neutral) is True
    assert Entity.get_entities_by_faction("heroes") == [hero, ally]
    assert Entity.get_alive_by_faction("heroes") == [hero, ally]
    assert hero.is_enemy_of(enemy.uuid) is True


def test_eb_06_006_targeted_skill_bonus_imports_target_outgoing_modifiers() -> None:
    """EB-06-006: high-level skill bonuses apply target outgoing channels."""
    reset_entity_state()
    actor = configured_entity("Actor", (0, 0), "heroes")
    target = configured_entity("Target", (1, 0), "monsters")
    base_athletics = actor.skill_bonus(None, "athletics").normalized_score

    target.skill_set.athletics.skill_bonus.to_target_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            target_entity_uuid=actor.uuid,
            name="Slippery Target",
            value=-2,
        )
    )

    targeted_athletics = actor.skill_bonus(target.uuid, "athletics")

    assert targeted_athletics.normalized_score == base_athletics - 2
    assert actor.target_entity_uuid is None
    assert actor.skill_set.athletics.skill_bonus.from_target_static is None


def test_eb_06_007_standard_actions_register_templates_and_handlers() -> None:
    """EB-06-007: setup_standard_actions registers reusable action templates."""
    reset_entity_state()
    get_map().create_rectangle(0, 0, 8, 8)
    entity = configured_entity("Actor", (1, 1), "heroes")

    setup_standard_actions(entity)

    template_names = {action.name for action in entity.registered_actions}
    assert {
        "Move",
        "Jump",
        "Dash",
        "Dodge",
        "Disengage",
        "Hide",
        "Drop Concentration",
        "Shake Awake",
        "Shove",
        "Pick Up",
        "Attack Object",
    }.issubset(template_names)
    assert entity.get_action_template("Dash") is not None
    assert entity.get_event_handler_by_name("Prone Auto-Stand") is not None
    assert entity.get_event_handler_by_name("Death Condition Handler") is None

    available = entity.get_available_actions()
    self_action_names = {action.template_name for action in available.self_actions}
    assert {"Dash", "Dodge", "Disengage"}.issubset(self_action_names)
    assert available.entity_uuid == entity.uuid
    assert available.remaining_movement == 35


def test_eb_06_008_registered_spell_action_defines_spellcaster_status() -> None:
    """EB-06-008: registered spell actions make is_spellcaster true."""
    reset_entity_state()
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Cantrip Only",
        config=EntityConfig(
            action_economy=ActionEconomyConfig(spell_slots={}),
            spellcasting=SpellcastingConfig(spellcasting_ability="charisma"),
        ),
    )

    assert entity.has_spell_slot(1) is False
    assert entity.is_spellcaster is False

    register_spell(entity, FireBolt, caster_level=5)
    spell_template = entity.get_action_template("Fire Bolt")

    assert spell_template is not None
    assert spell_template.is_spell is True
    assert entity.has_spell_slot(1) is False
    assert entity.is_spellcaster is True


def test_eb_06_009_bare_entity_creation_registers_and_normalizes_defaults() -> None:
    """EB-06-009: bare entity creation normalizes default child ownership."""
    reset_entity_state()
    source_uuid = uuid4()

    entity = Entity.create(source_entity_uuid=source_uuid, name="Bare Entity")

    assert entity.uuid == source_uuid
    assert entity.source_entity_uuid == source_uuid
    assert Entity.get(source_uuid) is entity
    assert get_map().get_entity_position(source_uuid) == (0, 0)
    assert entity.appearance.source_entity_uuid == source_uuid
    assert entity.ability_scores.source_entity_uuid == source_uuid
    assert entity.health.source_entity_uuid == source_uuid
    assert all(block.source_entity_uuid == source_uuid for block in entity.blocks.values())
    assert all(value.source_entity_uuid == source_uuid for value in entity.values.values())
    assert entity.proficiency_bonus.normalized_score == 2
    assert entity.get_hp() == 6


def test_eb_06_010_configured_entity_defaults_to_zero_hit_points() -> None:
    """EB-06-010: configured entities have no HP unless health config grants it."""
    reset_entity_state()

    no_hit_dice = Entity.create(
        source_entity_uuid=uuid4(),
        name="No Hit Dice",
        config=EntityConfig(),
    )
    bonus_only = Entity.create(
        source_entity_uuid=uuid4(),
        name="Bonus Only",
        config=EntityConfig(
            health=HealthConfig(max_hit_points_bonus=3, temporary_hit_points=2)
        ),
    )

    assert no_hit_dice.health.hit_dices == []
    assert no_hit_dice.get_hp() == 0
    assert no_hit_dice.has_hp is False
    assert no_hit_dice.is_active is False

    assert bonus_only.health.hit_dices == []
    assert bonus_only.get_hp() == 5
    assert bonus_only.has_hp is True
    assert bonus_only.is_active is True


def test_eb_06_011_visible_entities_filter_into_allies_and_enemies() -> None:
    """EB-06-011: senses entities are filtered through faction relationships."""
    reset_entity_state()
    get_map().create_rectangle(0, 0, 8, 8)
    hero = configured_entity("Hero", (2, 2), "heroes")
    ally = configured_entity("Ally", (2, 3), "heroes")
    enemy = configured_entity("Enemy", (3, 2), "monsters")
    neutral = configured_entity("Neutral", (3, 3), None)

    Entity.update_all_entities_senses()
    setup_standard_actions(hero)

    assert hero.senses.entities == {
        enemy.uuid: (3, 2),
        neutral.uuid: (3, 3),
        ally.uuid: (2, 3),
    }
    assert hero.get_visible_allies() == {ally.uuid: (2, 3)}
    assert hero.get_visible_enemies() == {
        enemy.uuid: (3, 2),
        neutral.uuid: (3, 3),
    }

    assert entity_action_target_uuids(hero, "Shove", "enemies") == {
        enemy.uuid,
        neutral.uuid,
    }
    assert entity_action_target_uuids(hero, "Shove", "allies") == {ally.uuid}
    assert entity_action_target_uuids(hero, "Shove", "all") == {
        ally.uuid,
        enemy.uuid,
        neutral.uuid,
    }


def test_eb_06_012_equipped_weapons_create_and_remove_attack_templates() -> None:
    """EB-06-012: weapon equip events keep attack templates synchronized."""
    reset_entity_state()
    get_map().create_rectangle(0, 0, 8, 8)
    entity = configured_entity("Actor", (1, 1), "heroes")
    setup_standard_actions(entity)

    assert entity.get_action_template("Attack_MELEE_MAIN") is None

    sword = create_shortsword(entity.uuid)
    assert entity.loot_item(sword) is True
    assert sword.uuid in entity.inventory.items
    assert entity.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN) is True

    template = entity.get_action_template("Attack_MELEE_MAIN")
    assert template is not None
    assert isinstance(template, Attack)
    assert template.is_attack is True
    assert template.weapon_slot == WeaponSlot.MELEE_MAIN
    assert template.valid_target_filter == "enemies"
    assert entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN) is sword
    assert sword.uuid not in entity.inventory.items

    unequipped = entity.unequip_item(WeaponSlot.MELEE_MAIN)

    assert unequipped is sword
    assert sword.uuid in entity.inventory.items
    assert entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN) is None
    assert entity.get_action_template("Attack_MELEE_MAIN") is None


def test_eb_06_013_saving_throw_and_skill_check_execute_event_phases() -> None:
    """EB-06-013: entity checks run full request and d20 event histories."""
    reset_entity_state()
    source = configured_entity("Caller", (0, 0), "heroes")
    target = configured_entity("Target", (1, 0), "heroes")

    save_request = source.create_saving_throw_request(
        target_entity_uuid=target.uuid,
        ability_name="dexterity",
        dc=15,
    )
    with fixed_randint(9):
        save_outcome, save_roll, save_success = target.saving_throw(save_request)

    save_history = EventQueue.get_event_history(save_request.uuid)
    save_roll_events = EventQueue.get_events_by_type(EventType.SAVE_D20_ROLL_RESULT)

    assert save_outcome == AttackOutcome.HIT
    assert save_roll.results == [9]
    assert save_roll.total == 15
    assert save_success is True
    assert [event.phase for event in save_history] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    save_execution_event = save_history[1]
    save_completion_event = save_history[-1]
    assert isinstance(save_execution_event, SavingThrowEvent)
    assert isinstance(save_completion_event, SavingThrowEvent)
    assert isinstance(save_execution_event.bonus, ModifiableValue)
    assert save_execution_event.bonus.normalized_score == 6
    assert save_completion_event.dice_roll is save_roll
    assert save_completion_event.result is True
    typed_save_roll_events = [
        event for event in save_roll_events
        if isinstance(event, SavingThrowD20RollResultEvent)
    ]
    assert len(typed_save_roll_events) == len(save_roll_events)
    assert [event.phase for event in save_roll_events] == [
        EventPhase.DECLARATION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert all(event.parent_event == save_request.uuid for event in typed_save_roll_events)
    assert all(event.ability_name == "dexterity" for event in typed_save_roll_events)
    assert all(event.roll_type == RollType.SAVE for event in typed_save_roll_events)

    skill_request = source.create_skill_check_request(
        target_entity_uuid=target.uuid,
        skill_name="athletics",
        dc=15,
    )
    with fixed_randint(4):
        skill_outcome, skill_roll, skill_success = target.skill_check(skill_request)

    skill_history = EventQueue.get_event_history(skill_request.uuid)
    skill_roll_events = EventQueue.get_events_by_type(EventType.CHECK_D20_ROLL_RESULT)

    assert skill_outcome == AttackOutcome.MISS
    assert skill_roll.results == [4]
    assert skill_roll.total == 14
    assert skill_success is False
    assert [event.phase for event in skill_history] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    skill_execution_event = skill_history[1]
    skill_completion_event = skill_history[-1]
    assert isinstance(skill_execution_event, SkillCheckEvent)
    assert isinstance(skill_completion_event, SkillCheckEvent)
    assert isinstance(skill_execution_event.bonus, ModifiableValue)
    assert skill_execution_event.bonus.normalized_score == 10
    assert skill_completion_event.dice_roll is skill_roll
    assert skill_completion_event.result is False
    typed_skill_roll_events = [
        event for event in skill_roll_events
        if isinstance(event, SkillCheckD20RollResultEvent)
    ]
    assert len(typed_skill_roll_events) == len(skill_roll_events)
    assert [event.phase for event in skill_roll_events] == [
        EventPhase.DECLARATION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert all(event.parent_event == skill_request.uuid for event in typed_skill_roll_events)
    assert all(event.skill_name == "athletics" for event in typed_skill_roll_events)
    assert all(event.roll_type == RollType.CHECK for event in typed_skill_roll_events)


def test_eb_06_014_repeated_standard_action_setup_replaces_handlers() -> None:
    """EB-06-014: setup_standard_actions is idempotent for standard handlers."""
    reset_entity_state()
    entity = configured_entity("Actor", (0, 0), "heroes")

    setup_standard_actions(entity)
    first_global_handlers = list(EventQueue._event_handlers_by_source_entity_uuid[entity.uuid])
    first_local_handler_names = sorted(
        handler.name for handler in entity.event_handlers.values()
    )
    first_global_handler_names = sorted(handler.name for handler in first_global_handlers)

    setup_standard_actions(entity)
    second_global_handlers = list(EventQueue._event_handlers_by_source_entity_uuid[entity.uuid])
    second_local_handler_names = sorted(
        handler.name for handler in entity.event_handlers.values()
    )
    second_global_handler_names = sorted(handler.name for handler in second_global_handlers)

    assert len(first_global_handlers) == 5
    assert len(first_local_handler_names) == 3
    assert first_global_handler_names.count(f"WeaponEquipHandler_{entity.uuid}") == 1
    assert first_global_handler_names.count(f"WeaponUnequipHandler_{entity.uuid}") == 1

    assert len(second_global_handlers) == 5
    assert len(second_local_handler_names) == 3
    assert second_global_handler_names.count(f"WeaponEquipHandler_{entity.uuid}") == 1
    assert second_global_handler_names.count(f"WeaponUnequipHandler_{entity.uuid}") == 1
    assert second_local_handler_names.count("HasAttacked Tracker") == 1
    assert second_local_handler_names.count("HasTakenDamage Tracker") == 1
    assert second_local_handler_names.count("Death Condition Handler") == 0
    assert second_local_handler_names.count("Prone Auto-Stand") == 1
    assert second_global_handler_names == first_global_handler_names
    assert second_local_handler_names == first_local_handler_names


def test_eb_06_015_entity_long_rest_and_revival_reduce_exhaustion() -> None:
    """EB-06-015: entity rest and revival lifecycle reduces Exhaustion."""
    reset_entity_state()
    source = configured_entity("Rest Source", (0, 0), "heroes")
    entity = configured_entity("Resting Hero", (1, 0), "heroes")
    setup_standard_actions(entity)
    base_movement = entity.action_economy.movement.normalized_score

    entity.action_economy.add_resource(
        "daily_power",
        maximum=1,
        recharge_type=RechargeType.LONG_REST,
    )
    entity.action_economy.consume_resource("daily_power")
    entity.action_economy.consume("spell_slot_1", 1)
    long_rest_marker = BaseCondition(
        name="Long Rest Marker",
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        duration=Duration(duration_type=DurationType.UNTIL_LONG_REST),
    )
    entity.add_condition(long_rest_marker)
    entity.add_condition(
        Exhaustion(
            source_entity_uuid=source.uuid,
            target_entity_uuid=entity.uuid,
            level=3,
        )
    )

    assert entity.action_economy.get_resource_current("daily_power") == 0
    assert entity.action_economy.spell_slot_1.normalized_score == 1
    assert "Long Rest Marker" in entity.active_conditions
    assert entity.action_economy.movement.normalized_score == base_movement // 2
    assert entity.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE

    entity.on_long_rest()

    active_exhaustion = entity.active_conditions["Exhaustion"]
    assert isinstance(active_exhaustion, Exhaustion)
    assert active_exhaustion.level == 2
    assert entity.action_economy.get_resource_current("daily_power") == 1
    assert entity.action_economy.spell_slot_1.normalized_score == 2
    assert "Long Rest Marker" not in entity.active_conditions
    assert entity.action_economy.movement.normalized_score == base_movement // 2
    assert entity.equipment.attack_bonus.advantage == AdvantageStatus.NONE

    damage_to_zero = entity.get_hp()
    entity.receive_damage(damage_to_zero, DamageType.SLASHING, source.uuid)
    assert entity.health.life_state is LifeState.DEAD
    assert entity.blocks_walking() is False

    assert entity.revive(hit_points=1) is True

    active_exhaustion = entity.active_conditions["Exhaustion"]
    assert isinstance(active_exhaustion, Exhaustion)
    assert active_exhaustion.level == 1
    assert entity.health.life_state is LifeState.ALIVE
    assert "Incapacitated" not in entity.active_conditions
    assert entity.blocks_walking() is True
    assert entity.get_hp() == 1


def test_eb_06_016_long_rest_restores_hp_and_expires_temporary_hp() -> None:
    """EB-06-016: long rest restores normal HP and expires temporary HP."""
    reset_entity_state()
    source = configured_entity("Rest Source", (0, 0), "heroes")
    entity = configured_entity("Wounded Hero", (1, 0), "heroes")
    normal_max_hp = get_max_hp(entity)

    assert entity.get_hp() == normal_max_hp + 5
    assert entity.health.temporary_hit_points.normalized_score == 5

    entity.receive_damage(12, DamageType.SLASHING, source.uuid)

    assert entity.health.temporary_hit_points.normalized_score == 0
    assert entity.health.damage_taken == 7
    assert entity.get_hp() == normal_max_hp - 7

    entity.health.add_temporary_hit_points(4, source.uuid)

    assert entity.health.temporary_hit_points.normalized_score == 4
    assert entity.get_hp() == normal_max_hp - 3

    assert entity.on_long_rest() is True

    assert entity.health.damage_taken == 0
    assert entity.health.temporary_hit_points.normalized_score == 0
    assert entity.get_hp() == normal_max_hp

    dead_entity = configured_entity("Dead Rester", (2, 0), "heroes")
    setup_standard_actions(dead_entity)
    dead_entity.action_economy.consume("spell_slot_1", 1)
    dead_entity.receive_damage(dead_entity.get_hp(), DamageType.SLASHING, source.uuid)

    assert dead_entity.health.life_state is LifeState.DEAD
    assert dead_entity.on_long_rest() is False
    assert dead_entity.health.life_state is LifeState.DEAD
    assert dead_entity.action_economy.spell_slot_1.normalized_score == 1
    assert dead_entity.get_hp() <= 0


def test_eb_06_017_hit_dice_spend_for_short_rest_and_recover_on_long_rest() -> None:
    """EB-06-017: Hit Dice can be spent to heal and recovered on long rest."""
    reset_entity_state()
    source = configured_entity("Rest Source", (0, 0), "heroes")
    entity = configured_entity("Hit Dice Hero", (1, 0), "heroes")
    normal_max_hp = get_max_hp(entity)
    hit_dice = entity.health.hit_dices[0]

    assert hit_dice.hit_dice_count.normalized_score == 3
    assert hit_dice.spent_hit_dice == 0
    assert hit_dice.available_hit_dice == 3

    entity.receive_damage(20, DamageType.SLASHING, source.uuid)

    assert entity.health.temporary_hit_points.normalized_score == 0
    assert entity.health.damage_taken == 15
    assert entity.get_hp() == normal_max_hp - 15

    with patch("dnd.blocks.health.randint", side_effect=[5, 2]):
        first_results = entity.spend_hit_dice(count=2)

    assert [result.roll for result in first_results] == [5, 2]
    assert [result.constitution_modifier for result in first_results] == [2, 2]
    assert [result.total_healing for result in first_results] == [7, 4]
    assert [result.actual_healing for result in first_results] == [7, 4]
    assert hit_dice.spent_hit_dice == 2
    assert hit_dice.available_hit_dice == 1
    assert entity.health.damage_taken == 4
    assert entity.get_hp() == normal_max_hp - 4

    with patch("dnd.blocks.health.randint", return_value=8):
        capped_result = entity.spend_hit_dice()[0]

    assert capped_result.roll == 8
    assert capped_result.total_healing == 10
    assert capped_result.actual_healing == 4
    assert hit_dice.spent_hit_dice == 3
    assert hit_dice.available_hit_dice == 0
    assert entity.health.damage_taken == 0
    assert entity.get_hp() == normal_max_hp

    try:
        entity.spend_hit_dice()
    except ValueError as error:
        assert "Not enough hit dice" in str(error)
    else:
        raise AssertionError("Expected spending unavailable Hit Dice to fail")

    assert entity.on_long_rest() is True
    assert hit_dice.spent_hit_dice == 2
    assert hit_dice.available_hit_dice == 1

    entity.on_long_rest()
    assert hit_dice.spent_hit_dice == 1
    assert hit_dice.available_hit_dice == 2


if __name__ == "__main__":
    test_eb_06_001_entity_create_wires_identity_registries_and_blocks()
    test_eb_06_002_abilities_skills_saves_and_passives_compose()
    test_eb_06_003_health_action_economy_and_spellcasting_compose()
    test_eb_06_004_action_economy_resources_recharge_by_type()
    test_eb_06_005_factions_define_allies_and_enemies()
    test_eb_06_006_targeted_skill_bonus_imports_target_outgoing_modifiers()
    test_eb_06_007_standard_actions_register_templates_and_handlers()
    test_eb_06_008_registered_spell_action_defines_spellcaster_status()
    test_eb_06_009_bare_entity_creation_registers_and_normalizes_defaults()
    test_eb_06_010_configured_entity_defaults_to_zero_hit_points()
    test_eb_06_011_visible_entities_filter_into_allies_and_enemies()
    test_eb_06_012_equipped_weapons_create_and_remove_attack_templates()
    test_eb_06_013_saving_throw_and_skill_check_execute_event_phases()
    test_eb_06_014_repeated_standard_action_setup_replaces_handlers()
    test_eb_06_015_entity_long_rest_and_revival_reduce_exhaustion()
    test_eb_06_016_long_rest_restores_hp_and_expires_temporary_hp()
    test_eb_06_017_hit_dice_spend_for_short_rest_and_recover_on_long_rest()
    print("PASS: engine book entity composition tests")
