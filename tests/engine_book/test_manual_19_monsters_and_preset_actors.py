"""Manual Chapter 19 checks for monsters and preset actors."""

from uuid import uuid4

from dnd.actions_functional import get_available_actions
from dnd.conditions import Exhaustion, Poisoned
from dnd.core.base_block import BaseBlock, SensesType
from dnd.core.base_object import BaseObject
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.modifiers import AdvantageStatus, CreatureType, DamageType, ResistanceStatus
from dnd.core.values import BaseValue
from dnd.entity import Entity
from dnd.monsters.bestiary import (
    create_caster,
    create_goblin,
    create_skeleton,
    create_skeleton_archer,
    create_skeleton_warlock,
    create_skeleton_warrior,
)
from dnd.monsters.circus_fighter import create_warrior
from dnd.monsters.skeleton_abilities import MarkTargetAction
from dnd.utils import reset_combat_state


def reset_monster_tutorial_state(width: int = 30, height: int = 15) -> None:
    """Clear global state and create a rectangular monster tutorial arena."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    get_map().create_rectangle(0, 0, width, height)


def action_template_names(entity: Entity) -> set[str]:
    """Return registered action-template names for an entity."""
    return {action.name for action in entity.registered_actions if action.name is not None}


def inventory_item_names(entity: Entity) -> set[str]:
    """Return names of items stored directly in an entity inventory."""
    return {item.name for item in entity.inventory.items.values() if item.name is not None}


def equipped_item_name(entity: Entity, slot: WeaponSlot) -> str:
    """Return the name of the item equipped in a weapon slot."""
    item = entity.equipment.get_item_by_slot(slot)
    assert item is not None
    assert item.name is not None
    return item.name


def has_darkvision(entity: Entity) -> bool:
    """Return whether an entity has a darkvision sense mode."""
    return any(mode.sense_type == SensesType.DARKVISION for mode in entity.senses.sense_modes)


def item_use_action_names(entity: Entity) -> set[str]:
    """Return names for inventory item-use rows currently available to an entity."""
    available = get_available_actions(entity)
    return {
        action.template_name
        for action in available.all_actions
        if action.is_item_use and action.template_name is not None
    }


def test_base_goblin_and_skeleton_factories_encode_stat_block_traits() -> None:
    """Base monster factories turn stat-block traits into live entity state."""
    reset_monster_tutorial_state()

    goblin = create_goblin(name="Manual Goblin", position=(1, 1), faction="monsters")
    skeleton = create_skeleton(name="Manual Skeleton", position=(3, 1), faction="monsters")
    skeleton_without_darkvision = create_skeleton(
        name="Skeleton Without Darkvision",
        position=(5, 1),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses()

    assert goblin.get_hp() == 10
    assert goblin.ac_bonus().normalized_score == 15
    assert goblin.ability_scores.dexterity.modifier == 2
    assert has_darkvision(goblin)
    assert equipped_item_name(goblin, WeaponSlot.MELEE_MAIN) == "Scimitar"
    assert equipped_item_name(goblin, WeaponSlot.RANGED_MAIN) == "Shortbow"
    assert "Attack_MELEE_MAIN" in action_template_names(goblin)
    assert "Attack_RANGED_MAIN" in action_template_names(goblin)

    assert skeleton.get_hp() == 17
    assert skeleton.creature_type == CreatureType.UNDEAD
    assert skeleton.health.get_resistance(DamageType.BLUDGEONING) == ResistanceStatus.VULNERABILITY
    assert skeleton.health.get_resistance(DamageType.POISON) == ResistanceStatus.IMMUNITY
    assert skeleton.check_condition_immunity("Poisoned")
    assert skeleton.check_condition_immunity("Exhaustion")
    assert has_darkvision(skeleton)
    assert not has_darkvision(skeleton_without_darkvision)
    assert equipped_item_name(skeleton, WeaponSlot.MELEE_MAIN) == "Shortsword"
    assert equipped_item_name(skeleton, WeaponSlot.RANGED_MAIN) == "Shortbow"

    poisoned_event = skeleton.add_condition(
        Poisoned(source_entity_uuid=skeleton.uuid, target_entity_uuid=skeleton.uuid)
    )
    exhaustion_event = skeleton.add_condition(
        Exhaustion(source_entity_uuid=skeleton.uuid, target_entity_uuid=skeleton.uuid)
    )

    assert poisoned_event is not None and poisoned_event.canceled
    assert exhaustion_event is not None and exhaustion_event.canceled
    assert "Poisoned" not in skeleton.active_conditions
    assert "Exhaustion" not in skeleton.active_conditions


def test_goblin_nimble_escape_adds_bonus_action_versions_of_standard_actions() -> None:
    """Monster traits can register alternate-cost versions of ordinary actions."""
    reset_monster_tutorial_state()

    goblin = create_goblin(name="Nimble Goblin", position=(1, 1), faction="monsters")
    normal_disengage = goblin.get_action_template("Disengage")
    nimble_disengage = goblin.get_action_template("Nimble Escape: Disengage")
    nimble_hide = goblin.get_action_template("Nimble Escape: Hide")

    assert normal_disengage is not None
    assert nimble_disengage is not None
    assert nimble_hide is not None
    assert [cost.cost_type for cost in normal_disengage.effective_costs] == ["actions"]
    assert [cost.cost_type for cost in nimble_disengage.effective_costs] == ["bonus_actions"]
    assert [cost.cost_type for cost in nimble_hide.effective_costs] == ["bonus_actions"]

    event = nimble_disengage.instantiate().apply()

    assert event is not None
    assert not event.canceled
    assert goblin.action_economy.actions.normalized_score == 1
    assert goblin.action_economy.bonus_actions.normalized_score == 0
    assert "Disengaging" in goblin.active_conditions


def test_skeleton_role_presets_compose_equipment_items_actions_and_spells() -> None:
    """Specialized monster presets express combat roles through composed content."""
    reset_monster_tutorial_state()

    warrior = create_skeleton_warrior(name="Manual Warrior", position=(1, 1), faction="monsters")
    archer = create_skeleton_archer(name="Manual Archer", position=(3, 1), faction="monsters")
    warlock = create_skeleton_warlock(name="Manual Warlock", position=(5, 1), faction="monsters")
    create_skeleton(name="Target", position=(8, 1), faction="heroes")
    Entity.update_all_entities_senses()

    assert warrior.get_hp() == 31
    assert warrior.ac_bonus().normalized_score == 15
    assert equipped_item_name(warrior, WeaponSlot.MELEE_MAIN) == "Longsword"
    assert equipped_item_name(warrior, WeaponSlot.MELEE_OFF) == "Wooden Shield"
    assert "Acid Flask" in inventory_item_names(warrior)
    assert "Attack_MELEE_MAIN" in action_template_names(warrior)

    assert archer.get_hp() == 24
    assert archer.ac_bonus().normalized_score == 13
    assert archer.ability_scores.dexterity.modifier == 3
    assert equipped_item_name(archer, WeaponSlot.RANGED_MAIN) == "Shortbow"
    assert equipped_item_name(archer, WeaponSlot.MELEE_MAIN) == "Dagger"
    assert equipped_item_name(archer, WeaponSlot.MELEE_OFF) == "Dagger"
    assert "Mark Target" in action_template_names(archer)
    assert "Attack_RANGED_MAIN" in action_template_names(archer)

    assert warlock.get_hp() == 17
    assert warlock.ac_bonus().normalized_score == 13
    assert warlock.is_spellcaster
    assert warlock.ability_scores.charisma.modifier == 2
    assert warlock.action_economy.spell_slot_1.normalized_score == 2
    assert warlock.action_economy.spell_slot_2.normalized_score == 1
    assert equipped_item_name(warlock, WeaponSlot.MELEE_MAIN) == "Arcane Staff"
    assert "Scroll of Invisibility" in inventory_item_names(warlock)
    assert {"Eldritch Blast", "Burning Hands", "Thunderwave", "Necrotic Bless"} <= action_template_names(warlock)


def test_mark_target_links_target_condition_to_archer_concentration() -> None:
    """A preset action can create linked target state and concentration cleanup."""
    reset_monster_tutorial_state()
    archer = create_skeleton_archer(name="Manual Archer", position=(1, 1), faction="monsters")
    target = create_skeleton(name="Manual Target", position=(5, 1), faction="heroes")
    Entity.update_all_entities_senses()

    event = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    ).apply()

    assert event is not None
    assert not event.canceled
    assert "Marked" in target.active_conditions
    assert "Concentrating" in archer.active_conditions
    assert "Mark Cooldown" in archer.active_conditions
    assert archer.action_economy.bonus_actions.normalized_score == 0

    marked = target.active_conditions["Marked"]
    concentrating = archer.active_conditions["Concentrating"]

    assert concentrating.linked_conditions == [(target.uuid, marked.uuid)]
    assert target.check_condition_immunity("Invisible")
    assert target.check_condition_immunity("Hidden")
    assert any(
        modifier.name == "Marked" and modifier.value == AdvantageStatus.ADVANTAGE
        for modifier in target.equipment.ac_bonus.to_target_static.advantage_modifiers.values()
    )

    archer.remove_condition("Concentrating")

    assert "Concentrating" not in archer.active_conditions
    assert "Marked" not in target.active_conditions
    assert not target.check_condition_immunity("Invisible")
    assert not target.check_condition_immunity("Hidden")


def test_generic_caster_preset_wires_spellcasting_reactions_and_item_actions() -> None:
    """A spellcaster preset can register spells, reactions, slots, gear, and items."""
    reset_monster_tutorial_state()

    caster = create_caster(name="Manual Caster", position=(1, 1), faction="monsters", level=5)
    Entity.update_all_entities_senses()

    assert caster.is_spellcaster
    assert caster.spellcasting.spellcasting_ability == "charisma"
    assert caster.spell_attack_bonus().normalized_score == 7
    assert caster.spell_save_dc() == 15
    assert caster.get_hp() == 40
    assert caster.action_economy.spell_slot_1.normalized_score == 4
    assert caster.action_economy.spell_slot_2.normalized_score == 3
    assert caster.action_economy.spell_slot_3.normalized_score == 2
    assert equipped_item_name(caster, WeaponSlot.MELEE_MAIN) == "Dagger"
    assert {"Fire Bolt", "Magic Missile", "Fireball", "Invisibility", "Greater Invisibility"} <= action_template_names(caster)

    shield_handler = caster.get_event_handler_by_name("Shield")

    assert shield_handler is not None
    assert shield_handler.player_toggleable
    assert {"Potion of Greater Invisibility", "Potion of Haste"} <= inventory_item_names(caster)
    assert any(name.startswith("Drink Greater Invisibility Potion") for name in item_use_action_names(caster))
    assert any(name.startswith("Drink Haste Potion") for name in item_use_action_names(caster))


def test_custom_preset_actor_can_bundle_items_conditions_and_modifiers() -> None:
    """A game-specific preset can bundle bespoke gear, conditions, and modifiers."""
    reset_monster_tutorial_state()

    performer = create_warrior(
        source_id=uuid4(),
        proficiency_bonus=2,
        name="Manual Performer",
        position=(1, 1),
    )
    Entity.update_all_entities_senses()
    main_weapon = performer.equipment.get_item_by_slot(WeaponSlot.MELEE_MAIN)
    off_weapon = performer.equipment.get_item_by_slot(WeaponSlot.MELEE_OFF)

    assert action_template_names(performer) == set()
    assert performer.get_event_handler_by_name("Opportunity Attack Handler") is not None
    assert set(performer.active_conditions) == {
        "Circus Performer",
        "Dual Wielder",
        "Elemental Affinity",
        "Elemental Weapon Mastery",
    }
    assert performer.get_hp() == 58
    assert performer.health.temporary_hit_points.score == 10
    assert performer.ac_bonus().normalized_score == 14
    assert performer.action_economy.actions.normalized_score == 100
    assert performer.action_economy.reactions.normalized_score == 3
    assert performer.action_economy.movement.normalized_score == 25
    assert performer.skill_set.get_skill("acrobatics").skill_bonus.normalized_score == 7
    assert equipped_item_name(performer, WeaponSlot.MELEE_MAIN) == "Flaming Scimitar"
    assert equipped_item_name(performer, WeaponSlot.MELEE_OFF) == "Rusty Dagger"

    assert main_weapon is not None
    assert off_weapon is not None
    assert main_weapon.extra_damage_type == [DamageType.FIRE]
    assert off_weapon.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert performer.health.get_resistance(DamageType.FIRE) == ResistanceStatus.RESISTANCE
    assert performer.health.get_resistance(DamageType.COLD) == ResistanceStatus.VULNERABILITY
