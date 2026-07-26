"""Manual Chapter 18 checks for class features, feats, and factories."""

from collections.abc import Callable, Iterable
from unittest.mock import patch
from uuid import uuid4

from dnd.actions import Attack, SpellEvent
from dnd.actions_functional import (
    execute_by_index,
    get_available_actions,
    register_spell,
    setup_standard_actions,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import Weapon
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.classes.feats import LuckyFeature
from dnd.classes.fighter import ActionSurge, ActionSurgeFeature, SecondWind, SecondWindFeature
from dnd.classes.fighter_factory import FighterConfig, create_fighter
from dnd.classes.rage import Rage, RageFeature
from dnd.classes.sorcerer import QuickenedSpell, SorceryPointsFeature
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.dice import AttackOutcome
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import D20RollResultEvent, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.items.weapons import LONGSWORD_RECIPE
from dnd.spells import FireBolt
from dnd.utils import reset_combat_state


def reset_class_tutorial_state(width: int = 12, height: int = 6) -> None:
    """Clear global state and create a rectangular class-feature arena."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    get_map().create_rectangle(0, 0, width, height)


def create_class_actor(
    name: str,
    position: tuple[int, int],
    faction: str = "heroes",
    spell_slots: dict[int, int] | None = None,
) -> Entity:
    """Create an actor with stable martial and spellcasting stats."""
    actor_id = uuid4()
    return Entity.create(
        source_entity_uuid=actor_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=16),
                dexterity=AbilityConfig(ability_score=14),
                constitution=AbilityConfig(ability_score=14),
                intelligence=AbilityConfig(ability_score=10),
                wisdom=AbilityConfig(ability_score=12),
                charisma=AbilityConfig(ability_score=18),
            ),
            action_economy=ActionEconomyConfig(spell_slots=spell_slots or {}),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=3,
                        mode="maximums",
                    )
                ],
            ),
            proficiency_bonus=3,
            spellcasting=SpellcastingConfig(spellcasting_ability="charisma"),
            position=position,
            faction=faction,
        ),
    )


def fixed_class_randint(
    d20_values: Iterable[int] = (),
    d4_value: int = 3,
    d8_value: int = 4,
    d10_value: int = 4,
) -> Callable[[int, int], int]:
    """Return deterministic dice values by die size for class-feature examples."""
    d20_iter = iter(d20_values)

    def fake_randint(low: int, high: int) -> int:
        if high == 20:
            return next(d20_iter)
        if high == 4:
            return d4_value
        if high == 8:
            return d8_value
        if high == 10:
            return d10_value
        return low

    return fake_randint


def test_second_wind_feature_grants_action_resource_healing_and_cleanup() -> None:
    """A feature condition can grant an action and resource, then clean them up."""
    reset_class_tutorial_state()
    fighter = create_class_actor("Second Wind Fighter", (0, 0))
    feature = SecondWindFeature(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        fighter_level=3,
    )

    fighter.add_condition(feature)

    assert "Second Wind Feature" in fighter.active_conditions
    assert fighter.get_action_template("Second Wind") is not None
    assert fighter.action_economy.resources["second_wind"].maximum == 1
    assert fighter.action_economy.resources["second_wind"].current == 1

    fighter.receive_damage(8, DamageType.SLASHING, fighter.uuid)
    wounded_hp = fighter.get_hp()

    with patch(
        "dnd.core.dice.random.randint",
        side_effect=fixed_class_randint(d10_value=4),
    ):
        event = SecondWind(
            source_entity_uuid=fighter.uuid,
            fighter_level=3,
        ).apply()

    assert event is not None
    assert not event.canceled
    assert event.status_message == "Second Wind complete - healed 7 HP"
    assert fighter.get_hp() == wounded_hp + 7
    assert fighter.action_economy.bonus_actions.normalized_score == 0
    assert fighter.action_economy.resources["second_wind"].current == 0

    fighter.action_economy.on_short_rest()

    assert fighter.action_economy.resources["second_wind"].current == 1

    fighter.remove_condition("Second Wind Feature")

    assert "second_wind" not in fighter.action_economy.resources
    assert fighter.get_action_template("Second Wind") is None


def test_action_surge_feature_spends_resource_to_grant_one_temporary_action() -> None:
    """Action Surge is a feature-granted action that writes a temporary modifier."""
    reset_class_tutorial_state()
    fighter = create_class_actor("Action Surge Fighter", (0, 0))
    fighter.add_condition(ActionSurgeFeature(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        num_uses=1,
    ))
    actions_before = fighter.action_economy.actions.normalized_score

    event = ActionSurge(source_entity_uuid=fighter.uuid).apply()

    assert event is not None
    assert not event.canceled
    assert "Action Surge Feature" in fighter.active_conditions
    assert "ActionSurging" in fighter.active_conditions
    assert fighter.action_economy.actions.normalized_score == actions_before + 1
    assert fighter.action_economy.resources["action_surge"].current == 0

    fighter.action_economy.on_short_rest()

    assert fighter.action_economy.resources["action_surge"].current == 1


def test_rage_feature_grants_bonus_action_state_resistance_and_handlers() -> None:
    """Rage grants actions and a resource; the active state owns modifiers and handlers."""
    reset_class_tutorial_state()
    barbarian = create_class_actor("Rage Barbarian", (0, 0))
    barbarian.add_condition(RageFeature(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_uses=2,
        rage_damage=2,
    ))

    assert "Rage Feature" in barbarian.active_conditions
    assert barbarian.get_action_template("Rage") is not None
    assert barbarian.get_action_template("End Rage") is not None
    assert barbarian.action_economy.resources["rage"].current == 2

    event = Rage(source_entity_uuid=barbarian.uuid, rage_damage=2).apply()
    hp_before_damage = barbarian.get_hp()
    actual_damage = barbarian.receive_damage(10, DamageType.SLASHING, barbarian.uuid)

    assert event is not None
    assert not event.canceled
    assert "Raging" in barbarian.active_conditions
    assert barbarian.action_economy.resources["rage"].current == 1
    assert barbarian.action_economy.bonus_actions.normalized_score == 0
    assert actual_damage == 5
    assert barbarian.get_hp() == hp_before_damage - 5
    assert barbarian.get_event_handler_by_name("Rage Maintenance") is not None
    assert barbarian.get_event_handler_by_name("Rage Armor Watch") is not None
    assert barbarian.get_event_handler_by_name("Rage Death End") is not None


def test_lucky_feat_adds_resource_and_modifies_a_low_d20_attack_roll() -> None:
    """A feat can add a resource and register a d20 result-event handler."""
    reset_class_tutorial_state()
    attacker = create_class_actor("Lucky Duelist", (0, 0))
    target = create_class_actor("Training Target", (1, 0), "monsters")
    sword = materialize_item(
        LONGSWORD_RECIPE,
        attacker.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    attacker.loot_item(sword)
    attacker.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
    setup_standard_actions(attacker)
    attacker.add_condition(LuckyFeature(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=attacker.uuid,
    ))
    Entity.update_all_entities_senses(max_distance=30)
    target_hp = target.get_hp()

    with patch(
        "dnd.core.dice.random.randint",
        side_effect=fixed_class_randint(d20_values=[1, 20], d8_value=4),
    ):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    modified_d20_events = [
        roll_event
        for roll_event in EventQueue.get_events_by_type(EventType.ATTACK_D20_ROLL_RESULT)
        if isinstance(roll_event, D20RollResultEvent)
        and roll_event.phase == EventPhase.COMPLETION
        and roll_event.roll_modifications
    ]

    assert event is not None
    assert not event.canceled
    assert event.attack_outcome == AttackOutcome.CRIT
    assert target.get_hp() == target_hp - 11
    assert attacker.action_economy.resources["luck_points"].current == 2

    assert len(modified_d20_events) == 1
    assert modified_d20_events[0].roll.total == 7
    assert modified_d20_events[0].get_effective_roll().total == 26
    assert modified_d20_events[0].roll_modifications[0][0] == "Lucky"


def test_quickened_spell_uses_feature_resource_to_override_spell_template_until_cast() -> None:
    """Metamagic uses a condition to override registered spell templates temporarily."""
    reset_class_tutorial_state()
    sorcerer = create_class_actor("Quickened Sorcerer", (0, 0), spell_slots={1: 1})
    target = create_class_actor("Spell Target", (1, 0), "monsters")
    register_spell(sorcerer, FireBolt, caster_level=1)
    sorcerer.add_condition(SorceryPointsFeature(
        source_entity_uuid=sorcerer.uuid,
        target_entity_uuid=sorcerer.uuid,
        sorcery_points=5,
        metamagic_choices=["quickened"],
    ))
    fire_bolt_template = sorcerer.get_action_template("Fire Bolt")

    assert fire_bolt_template is not None
    assert fire_bolt_template.alt_cost_type is None
    assert sorcerer.get_action_template("Quickened Spell") is not None
    assert sorcerer.action_economy.resources["sorcery_points"].current == 5

    quickened_event = QuickenedSpell(source_entity_uuid=sorcerer.uuid).apply()

    assert quickened_event is not None
    assert not quickened_event.canceled
    assert "MetamagicActive" in sorcerer.active_conditions
    assert fire_bolt_template.alt_cost_type == "bonus_actions"
    assert sorcerer.action_economy.resources["sorcery_points"].current == 3

    Entity.update_all_entities_senses(max_distance=30)
    available = get_available_actions(sorcerer)
    target_hp = target.get_hp()

    with patch(
        "dnd.core.dice.random.randint",
        side_effect=fixed_class_randint(d20_values=[12, 11], d10_value=5),
    ):
        spell_event = execute_by_index(
            sorcerer,
            "Fire Bolt",
            0,
            available=available,
        )

    assert isinstance(spell_event, SpellEvent)
    assert not spell_event.canceled
    assert "MetamagicActive" not in sorcerer.active_conditions
    assert fire_bolt_template.alt_cost_type is None
    assert sorcerer.action_economy.actions.normalized_score == 1
    assert sorcerer.action_economy.bonus_actions.normalized_score == 0
    assert sorcerer.action_economy.resources["sorcery_points"].current == 3
    assert spell_event.dice_roll is not None
    assert spell_event.dice_roll.results == [12, 11]
    assert target.get_hp() == target_hp - 5


def test_fighter_factory_builds_level_five_character_with_level_gated_content() -> None:
    """A class factory turns a configuration into a fully playable entity."""
    reset_class_tutorial_state()

    fighter = create_fighter(FighterConfig(
        level=5,
        name="Manual Fighter",
        position=(0, 0),
        faction="heroes",
        fighting_style="defense",
        equipment_preset="sword_shield",
        asi_4=[("strength", 2)],
    ))

    assert fighter.name == "Manual Fighter"
    assert fighter.description == "Level 5 Fighter (Champion)"
    assert fighter.proficiency_bonus.normalized_score == 3
    assert fighter.ability_scores.strength.ability_score.score == 19
    assert fighter.get_hp() == 44
    assert fighter.ac_bonus().normalized_score == 19

    assert "Fighting Style: Defense" in fighter.active_conditions
    assert "Second Wind Feature" in fighter.active_conditions
    assert "Action Surge Feature" in fighter.active_conditions
    assert "Improved Critical" in fighter.active_conditions
    assert "Extra Attack" in fighter.active_conditions

    assert fighter.action_economy.resources["second_wind"].maximum == 1
    assert fighter.action_economy.resources["action_surge"].maximum == 1
    assert fighter.action_economy.resources["extra_attacks"].maximum == 1

    assert fighter.get_action_template("Second Wind") is not None
    assert fighter.get_action_template("Action Surge") is not None
    assert fighter.get_action_template("Extra Attack_MELEE_MAIN") is not None

    assert [item.name for item in fighter.equipment.get_all_equipped_items()] == [
        "Longsword",
        "Shield",
        "Chain Mail",
        "Leather Boots",
    ]
