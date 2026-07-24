"""Manual Chapter 16 checks for spellcasting core."""

from unittest.mock import patch
from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.actions_functional import get_available_actions, register_spell
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.base_actions import ActionCategory, AvailableActionInfo
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.combat_log import CombatLogEntryType
from dnd.core.dice import AttackOutcome
from dnd.core.events import EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.spells import FireBolt, Haste, MagicMissile
from dnd.utils import reset_combat_state


def reset_spell_tutorial_state(width: int = 10, height: int = 6) -> None:
    """Clear global state and create a small spell tutorial arena."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    get_map().create_rectangle(0, 0, width, height)


def create_spell_actor(
    name: str,
    position: tuple[int, int],
    faction: str,
    spell_slots: dict[int, int] | None = None,
    intelligence: int = 18,
    proficiency_bonus: int = 3,
    spellcasting: SpellcastingConfig | None = None,
) -> Entity:
    """Create an actor with spellcasting stats, HP, and optional spell slots."""
    actor_id = uuid4()
    return Entity.create(
        source_entity_uuid=actor_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=10),
                constitution=AbilityConfig(ability_score=12),
                intelligence=AbilityConfig(ability_score=intelligence),
                wisdom=AbilityConfig(ability_score=12),
                charisma=AbilityConfig(ability_score=10),
            ),
            action_economy=ActionEconomyConfig(spell_slots=spell_slots or {}),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=8,
                        hit_dice_count=3,
                        mode="maximums",
                    )
                ],
            ),
            proficiency_bonus=proficiency_bonus,
            spellcasting=spellcasting or SpellcastingConfig(spellcasting_ability="intelligence"),
            position=position,
            faction=faction,
        ),
    )


def find_action(actions, template_name: str) -> AvailableActionInfo:
    """Return the discovered action row with the requested template name."""
    for action_info in actions.all_actions:
        if action_info.template_name == template_name:
            return action_info
    raise AssertionError(f"{template_name} was not discovered")


def test_spell_slots_are_action_economy_values_and_reset_separately() -> None:
    """Spell slots are spendable action-economy values, not spellcasting fields."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Slot Mage",
        (0, 0),
        "heroes",
        spell_slots={1: 2, 2: 1},
    )

    assert caster.action_economy.spell_slot_1.normalized_score == 2
    assert caster.action_economy.spell_slot_2.normalized_score == 1
    assert caster.has_spell_slot(1)
    assert caster.has_spell_slot(2)
    assert not caster.has_spell_slot(3)
    assert caster.get_lowest_spell_slot(1) == 1
    assert caster.get_lowest_spell_slot(3) is None
    assert not hasattr(caster.spellcasting, "spell_slot_1")

    caster.action_economy.consume("spell_slot_1", 1)

    assert caster.action_economy.spell_slot_1.normalized_score == 1

    caster.action_economy.reset_all_costs()

    assert caster.action_economy.spell_slot_1.normalized_score == 1

    caster.action_economy.reset_spell_slot_costs()

    assert caster.action_economy.spell_slot_1.normalized_score == 2


def test_spell_numbers_compose_from_ability_proficiency_and_spellcasting_modifiers() -> None:
    """Entity spell helpers combine ability, proficiency, equipment, and spell modifiers."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Focused Mage",
        (0, 0),
        "heroes",
        spellcasting=SpellcastingConfig(
            spellcasting_ability="intelligence",
            spell_attack_modifiers=[("Wand", 2)],
            spell_damage_modifiers=[("Elemental Affinity", 3)],
            spell_dc_modifiers=[("Arcane Focus", 1)],
            spell_crit_threshold_modifiers=[("Spell Sniper", 1)],
            spell_crit_extra_dice_modifiers=[("Arcane Surge", 2)],
        ),
    )

    assert caster.spell_attack_bonus().normalized_score == 9
    assert caster.spell_save_dc() == 16
    assert caster.get_spell_damage_bonus().normalized_score == 3
    assert caster.get_spell_crit_threshold() == 19
    assert caster.get_spell_crit_extra_dice() == 2


def test_registered_spells_surface_cantrips_and_slot_variants_in_discovery() -> None:
    """Registered spell templates generate the rows a UI or controller can select."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Menu Mage",
        (0, 0),
        "heroes",
        spell_slots={1: 1, 2: 1, 3: 1},
    )
    enemy = create_spell_actor("Training Goblin", (1, 0), "monsters")
    ally = create_spell_actor("Haste Ally", (0, 1), "heroes")
    register_spell(caster, FireBolt, caster_level=5)
    register_spell(caster, MagicMissile, caster_level=5)
    register_spell(caster, Haste, caster_level=5)
    Entity.update_all_entities_senses(max_distance=30)

    available = get_available_actions(caster)
    fire_bolt = find_action(available, "Fire Bolt")
    missile_1 = find_action(available, "Magic Missile__slot_1")
    missile_2 = find_action(available, "Magic Missile__slot_2")
    missile_3 = find_action(available, "Magic Missile__slot_3")
    haste = find_action(available, "Haste__slot_3")

    assert fire_bolt.action_category == ActionCategory.SPELL
    assert fire_bolt.spell_level == 0
    assert fire_bolt.cast_at_level == 0
    assert not fire_bolt.is_spell_variant
    assert [target.target_uuid for target in fire_bolt.valid_targets] == [enemy.uuid]

    assert missile_1.base_template_name == "Magic Missile"
    assert missile_1.display_name == "Magic Missile (Level 1)"
    assert missile_1.cast_at_level == 1
    assert missile_1.num_projectiles == 3
    assert missile_1.allow_same_target is True
    assert missile_2.cast_at_level == 2
    assert missile_2.num_projectiles == 4
    assert missile_3.cast_at_level == 3
    assert missile_3.num_projectiles == 5

    assert haste.base_template_name == "Haste"
    assert haste.cast_at_level == 3
    assert {target.target_uuid for target in haste.valid_targets} == {enemy.uuid, ally.uuid}


def test_fire_bolt_uses_spell_attack_bonus_cantrip_scaling_and_damage() -> None:
    """An adjacent cantrip attack rolls disadvantage and scales its damage."""
    reset_spell_tutorial_state()
    caster = create_spell_actor("Pyromancer", (0, 0), "heroes")
    enemy = create_spell_actor("Training Goblin", (1, 0), "monsters")
    Entity.update_all_entities_senses(max_distance=30)
    hp_before = enemy.get_hp()

    with patch("dnd.core.dice.random.randint", side_effect=[14, 12, 5, 6]):
        event = FireBolt(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=enemy.uuid,
            caster_level=5,
        ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert event.attack_outcome == AttackOutcome.HIT
    assert event.dice_roll is not None
    assert event.dice_roll.results == [14, 12]
    assert event.dice_roll.total == 19
    assert event.damage_rolls is not None
    assert event.damage_rolls[0].results == [5, 6]
    assert event.damage_rolls[0].total == 11
    assert enemy.get_hp() == hp_before - 11
    assert caster.action_economy.actions.normalized_score == 0
    assert event.combat_log is not None
    assert event.combat_log.entry_type == CombatLogEntryType.ATTACK
    assert event.combat_log.data["outcome"] == "hit"


def test_magic_missile_auto_hits_multiple_darts_and_spends_slot() -> None:
    """A leveled multi-target spell creates dart children and consumes its slot."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Missile Mage",
        (0, 0),
        "heroes",
        spell_slots={1: 1},
    )
    enemy = create_spell_actor("Training Goblin", (1, 0), "monsters")
    Entity.update_all_entities_senses(max_distance=30)
    hp_before = enemy.get_hp()

    with patch("dnd.core.dice.random.randint", side_effect=[2, 3, 4]):
        event = MagicMissile(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=enemy.uuid,
        ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert event.total_targets == 3
    assert event.total_damage == 12
    assert enemy.get_hp() == hp_before - 12
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 0
    assert event.combat_log is not None
    assert event.combat_log.entry_type == CombatLogEntryType.MULTI_ENTITY_ACTION
    assert len(event.combat_log.sub_entries) == 3


def test_haste_links_spell_effect_to_concentration_and_cleans_up_when_broken() -> None:
    """A concentration spell links target effects to the caster's Concentrating condition."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Time Mage",
        (0, 0),
        "heroes",
        spell_slots={3: 1},
    )
    ally = create_spell_actor("Haste Ally", (1, 0), "heroes")
    Entity.update_all_entities_senses(max_distance=30)
    movement_before = ally.action_economy.movement.normalized_score
    actions_before = ally.action_economy.actions.normalized_score
    ac_before = ally.ac_bonus().normalized_score

    event = Haste(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert "Concentrating" in caster.active_conditions
    assert "Haste" in ally.active_conditions
    assert ally.action_economy.movement.normalized_score == movement_before * 2
    assert ally.action_economy.actions.normalized_score == actions_before
    assert ally.action_economy.resources["haste_action"].current == 1
    assert ally.ac_bonus().normalized_score == ac_before + 2
    assert caster.action_economy.spell_slot_3.normalized_score == 0

    concentrating = caster.active_conditions["Concentrating"]
    assert concentrating.linked_conditions == [(ally.uuid, ally.active_conditions["Haste"].uuid)]

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert "Haste" not in ally.active_conditions
    assert "haste_action" not in ally.action_economy.resources
    assert "Haste Lethargy" in ally.active_conditions
    assert "Incapacitated" not in ally.active_conditions
    assert ally.action_economy.action_permission.normalized_score == 0
    assert ally.ac_bonus().normalized_score == ac_before
