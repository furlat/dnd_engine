"""Manual Chapter 17 checks for representative spell families."""

from collections.abc import Callable, Iterable
from unittest.mock import patch
from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.conditions import Poisoned
from dnd.core.base_actions import TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.combat_log import CombatLogEntryType
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.spells import (
    ALL_SPELLS,
    CureWounds,
    FalseLife,
    Fireball,
    Invisibility,
    LesserRestoration,
    MageArmor,
    MistyStep,
    SpikeGrowth,
)
from dnd.utils import reset_combat_state


def reset_spell_family_state(width: int = 12, height: int = 8) -> None:
    """Clear global state and create a rectangular spell-family arena."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    get_map().create_rectangle(0, 0, width, height)


def create_spell_family_actor(
    name: str,
    position: tuple[int, int],
    faction: str,
    spell_slots: dict[int, int] | None = None,
    intelligence: int = 18,
    dexterity: int = 14,
    proficiency_bonus: int = 3,
) -> Entity:
    """Create an actor with stable spellcasting, HP, and grid position."""
    actor_id = uuid4()
    return Entity.create(
        source_entity_uuid=actor_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=dexterity),
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
            spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
            position=position,
            faction=faction,
        ),
    )


def fixed_spell_family_randint(
    d20_values: Iterable[int] = (),
    d4_value: int = 3,
    d6_value: int = 4,
    d8_value: int = 6,
) -> Callable[[int, int], int]:
    """Return deterministic dice values by die size for spell examples."""
    d20_iter = iter(d20_values)

    def fake_randint(low: int, high: int) -> int:
        if high == 20:
            return next(d20_iter)
        if high == 4:
            return d4_value
        if high == 6:
            return d6_value
        if high == 8:
            return d8_value
        return low

    return fake_randint


def test_spell_catalog_entries_expose_family_shape_metadata() -> None:
    """The public spell catalog exposes representative families by runtime shape."""
    reset_spell_family_state()

    representatives = {
        "Fireball": (Fireball, 3, "evocation", TargetType.POSITION_AOE),
        "Cure Wounds": (CureWounds, 1, "evocation", TargetType.ENTITY),
        "Mage Armor": (MageArmor, 1, "abjuration", TargetType.ENTITY),
        "Lesser Restoration": (LesserRestoration, 2, "abjuration", TargetType.ENTITY),
        "Misty Step": (MistyStep, 2, "conjuration", TargetType.POSITION),
        "Invisibility": (Invisibility, 2, "illusion", TargetType.ENTITY),
        "False Life": (FalseLife, 1, "necromancy", TargetType.SELF),
        "Spike Growth": (SpikeGrowth, 2, "transmutation", TargetType.POSITION),
    }

    for spell_name, (spell_class, level, school, target_type) in representatives.items():
        spell = ALL_SPELLS[spell_name](source_entity_uuid=uuid4())

        assert ALL_SPELLS[spell_name] is spell_class
        assert spell.spell_level == level
        assert spell.spell_school == school
        assert spell.target_type == target_type
        if level > 0:
            assert any(cost.cost_type == f"spell_slot_{level}" for cost in spell.costs)


def test_area_damage_family_fireball_resolves_each_creature_under_one_parent_event() -> None:
    """A positional AoE spell creates per-target work and a multi-entity parent."""
    reset_spell_family_state()
    caster = create_spell_family_actor("Evoker", (0, 0), "heroes", spell_slots={3: 1})
    first_enemy = create_spell_family_actor("First Goblin", (5, 0), "monsters")
    second_enemy = create_spell_family_actor("Second Goblin", (6, 0), "monsters")
    Entity.update_all_entities_senses(max_distance=60)
    first_hp = first_enemy.get_hp()
    second_hp = second_enemy.get_hp()
    caster_hp = caster.get_hp()

    with patch(
        "dnd.core.dice.random.randint",
        side_effect=fixed_spell_family_randint(d20_values=[5, 18], d6_value=4),
    ):
        event = Fireball(
            source_entity_uuid=caster.uuid,
            end_position=(5, 0),
        ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert event.total_targets == 2
    assert event.total_damage == 48
    assert sorted([first_hp - first_enemy.get_hp(), second_hp - second_enemy.get_hp()]) == [16, 32]
    assert caster.get_hp() == caster_hp
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_3.normalized_score == 0
    assert event.combat_log is not None
    assert event.combat_log.entry_type == CombatLogEntryType.MULTI_ENTITY_ACTION
    assert len(event.combat_log.sub_entries) == 2


def test_healing_family_cure_wounds_restores_normal_hp_and_spends_a_slot() -> None:
    """Healing spells roll healing, cap at missing HP, and pay spell costs."""
    reset_spell_family_state()
    caster = create_spell_family_actor("Field Cleric", (0, 0), "heroes", spell_slots={1: 1})
    ally = create_spell_family_actor("Wounded Ally", (1, 0), "heroes")
    Entity.update_all_entities_senses(max_distance=30)
    ally.receive_damage(10, DamageType.SLASHING, caster.uuid)
    wounded_hp = ally.get_hp()

    with patch(
        "dnd.core.dice.random.randint",
        side_effect=fixed_spell_family_randint(d8_value=6),
    ):
        event = CureWounds(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
        ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert wounded_hp == 17
    assert ally.get_hp() == 27
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 0
    assert event.status_message == "Cure Wounds heals Wounded Ally for 10 HP"


def test_self_survival_family_false_life_adds_temporary_hp() -> None:
    """A self spell can mutate the caster's survivability without a target."""
    reset_spell_family_state()
    caster = create_spell_family_actor("Necromancer", (0, 0), "heroes", spell_slots={1: 1})

    with patch(
        "dnd.core.dice.random.randint",
        side_effect=fixed_spell_family_randint(d4_value=3),
    ):
        event = FalseLife(source_entity_uuid=caster.uuid).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert event.temp_hp_gained == 7
    assert caster.health.temporary_hit_points.normalized_score == 7
    assert caster.get_hp() == 34
    assert caster.action_economy.spell_slot_1.normalized_score == 0


def test_protection_and_restoration_families_apply_and_remove_conditions() -> None:
    """Defensive and cleansing spells write through the condition system."""
    reset_spell_family_state()
    caster = create_spell_family_actor("Abjurer", (0, 0), "heroes", spell_slots={1: 1, 2: 1})
    ally = create_spell_family_actor("Ward Ally", (1, 0), "heroes", dexterity=14)
    Entity.update_all_entities_senses(max_distance=30)
    ac_before = ally.ac_bonus().normalized_score

    mage_armor_event = MageArmor(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
    ).apply()

    assert isinstance(mage_armor_event, SpellEvent)
    assert not mage_armor_event.canceled
    assert "Mage Armor" in ally.active_conditions
    assert ally.ac_bonus().normalized_score == ac_before + 3
    assert caster.action_economy.spell_slot_1.normalized_score == 0

    caster.action_economy.reset_all_costs()
    ally.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))

    lesser_restoration_event = LesserRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
    ).apply()

    assert isinstance(lesser_restoration_event, SpellEvent)
    assert not lesser_restoration_event.canceled
    assert "Mage Armor" in ally.active_conditions
    assert "Poisoned" not in ally.active_conditions
    assert lesser_restoration_event.status_message == "Lesser Restoration: Removed Poisoned"
    assert caster.action_economy.spell_slot_2.normalized_score == 0


def test_movement_family_misty_step_teleports_and_uses_bonus_action() -> None:
    """Movement magic mutates position while paying its own action economy cost."""
    reset_spell_family_state()
    caster = create_spell_family_actor("Traveler", (0, 0), "heroes", spell_slots={2: 2})
    Entity.update_all_entities_senses(max_distance=60)

    event = MistyStep(
        source_entity_uuid=caster.uuid,
        end_position=(3, 0),
    ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert caster.position == (3, 0)
    assert caster.senses.position == (3, 0)
    assert event.distance_feet == 15
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.bonus_actions.normalized_score == 0
    assert caster.action_economy.spell_slot_2.normalized_score == 1


def test_visibility_family_invisibility_links_target_effect_to_concentration() -> None:
    """Invisibility applies a target condition owned by caster concentration."""
    reset_spell_family_state()
    caster = create_spell_family_actor("Illusionist", (0, 0), "heroes", spell_slots={2: 1})
    ally = create_spell_family_actor("Scout", (1, 0), "heroes")
    Entity.update_all_entities_senses(max_distance=30)

    event = Invisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert "Concentrating" in caster.active_conditions
    assert "Invisible" in ally.active_conditions
    assert caster.active_conditions["Concentrating"].linked_conditions == [
        (ally.uuid, ally.active_conditions["Invisible"].uuid)
    ]
    assert caster.action_economy.spell_slot_2.normalized_score == 0

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert "Invisible" not in ally.active_conditions


def test_zone_family_spike_growth_owns_spatial_damage_and_concentration_cleanup() -> None:
    """Zone spells register spatial behavior and clean it through concentration."""
    reset_spell_family_state(width=16, height=4)
    caster = create_spell_family_actor("Druid", (0, 0), "heroes", spell_slots={2: 1})
    enemy = create_spell_family_actor("Intruder", (10, 0), "monsters")
    Entity.update_all_entities_senses(max_distance=80)
    enemy_hp = enemy.get_hp()

    event = SpikeGrowth(
        source_entity_uuid=caster.uuid,
        end_position=(5, 0),
    ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert "Spike Growth Zone" in caster.active_conditions
    assert "Concentrating" in caster.active_conditions
    assert caster.active_conditions["Concentrating"].linked_conditions == [
        (caster.uuid, caster.active_conditions["Spike Growth Zone"].uuid)
    ]
    assert caster.action_economy.spell_slot_2.normalized_score == 0

    with patch(
        "dnd.core.dice.random.randint",
        side_effect=fixed_spell_family_randint(d4_value=3),
    ):
        Entity.update_entity_position(enemy, (5, 0))

    assert enemy.get_hp() == enemy_hp - 6

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert "Spike Growth Zone" not in caster.active_conditions
