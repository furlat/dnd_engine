"""Engine semantic tests for monsters and preset actors."""

from uuid import uuid4

from dnd.actions_functional import execute_use_action, get_available_actions
from dnd.blocks.base_item import UsableItem
from dnd.blocks.equipment import Weapon
from dnd.conditions import Exhaustion, Hidden, InvisibilityEffect, Invisible, Poisoned
from dnd.core.base_block import BaseBlock, SenseMode, SensesType
from dnd.core.base_object import BaseObject
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.modifiers import (
    AdvantageStatus,
    ResistanceStatus,
)
from dnd.core.values import BaseValue
from dnd.entity import Entity
from dnd.game import Game
from dnd.items.consumables import (
    GREATER_INVISIBILITY_POTION_RECIPE,
    HASTE_POTION_RECIPE,
)
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
from dnd.spells.evocation import EldritchBlast
from tests.engine.support import (
    force_spell_attack_hit,
    get_hp,
    get_max_hp,
    remove_spell_attack_modifier,
    reset_combat_state,
)


_monster_game: Game | None = None


def reset_monster_state(width: int = 30, height: int = 15) -> None:
    """Clear global state and create a rectangular monster test grid."""
    global _monster_game
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    get_map().create_rectangle(0, 0, width, height)
    _monster_game = Game()


def deploy(entity: Entity) -> Entity:
    """Explicitly compose and place one monster for a live-world test."""
    if _monster_game is None:
        raise RuntimeError("reset_monster_state must run before deployment")
    entity.compose_entity()
    _monster_game.deploy_entity(entity, entity.position)
    return entity


def action_template_names(entity: Entity) -> set[str]:
    """Return registered action-template names for an entity."""
    return {action.name for action in entity.registered_actions if action.name is not None}


def inventory_item_names(entity: Entity) -> set[str]:
    """Return item names directly stored in an entity inventory."""
    return {item.name for item in entity.inventory.items.values() if item.name is not None}


def equipped_item_name(entity: Entity, slot: WeaponSlot) -> str:
    """Return the name of the item equipped in a weapon slot."""
    item = entity.equipment.get_item_by_slot(slot)
    assert item is not None
    assert item.name is not None
    return item.name


def has_darkvision(entity: Entity) -> bool:
    """Return whether the entity has a darkvision sense mode."""
    return any(mode.sense_type == SensesType.DARKVISION for mode in entity.senses.sense_modes)


def get_inventory_item(entity: Entity, name: str) -> UsableItem:
    """Return a named usable inventory item."""
    for item in entity.inventory.items.values():
        if item.name == name:
            assert isinstance(item, UsableItem)
            return item
    raise AssertionError(f"{entity.name} does not have {name}")


def available_item_template_names(entity: Entity) -> set[str]:
    """Return available item-use template names for an entity."""
    available = get_available_actions(entity)
    return {
        action.template_name
        for bucket in (
            available.entity_actions,
            available.self_actions,
            available.position_actions,
            available.object_actions,
        )
        for action in bucket
        if action.is_item_use and action.template_name is not None
    }


def test_eb_17_001_goblin_and_skeleton_factories_encode_srd_trait_state() -> None:
    """EB-17-001: basic monster factories encode SRD-facing trait state."""
    reset_monster_state()

    goblin = deploy(create_goblin(name="Book Goblin", position=(1, 1), faction="monsters"))
    skeleton = deploy(create_skeleton(name="Book Skeleton", position=(3, 1), faction="monsters"))
    skeleton_without_darkvision = deploy(create_skeleton(
        name="Book Skeleton Without Darkvision",
        position=(5, 1),
        faction="monsters",
        darkvision=False,
    ))
    Entity.update_all_entities_senses()

    assert get_max_hp(goblin) == 10
    assert goblin.ac_bonus().normalized_score == 15
    assert goblin.ability_scores.dexterity.modifier == 2
    assert has_darkvision(goblin)
    assert equipped_item_name(goblin, WeaponSlot.MELEE_MAIN) == "Scimitar"
    assert equipped_item_name(goblin, WeaponSlot.RANGED_MAIN) == "Shortbow"
    assert "Attack_MELEE_MAIN" in action_template_names(goblin)
    assert "Attack_RANGED_MAIN" in action_template_names(goblin)

    assert get_max_hp(skeleton) == 17
    assert skeleton.creature_type == CreatureType.UNDEAD
    assert skeleton.health.get_resistance(DamageType.BLUDGEONING) == ResistanceStatus.VULNERABILITY
    assert skeleton.health.get_resistance(DamageType.POISON) == ResistanceStatus.IMMUNITY
    assert equipped_item_name(skeleton, WeaponSlot.MELEE_MAIN) == "Shortsword"
    assert equipped_item_name(skeleton, WeaponSlot.RANGED_MAIN) == "Shortbow"
    assert "Attack_RANGED_MAIN" in action_template_names(skeleton)
    assert skeleton.check_condition_immunity("Poisoned")
    assert skeleton.check_condition_immunity("Exhaustion")
    assert has_darkvision(skeleton)
    assert not has_darkvision(skeleton_without_darkvision)


def test_eb_17_007_base_goblin_factory_models_srd_senses_attacks_and_nimble_escape() -> None:
    """EB-17-007: base goblin factory models SRD senses, attacks, and Nimble Escape."""
    reset_monster_state()

    goblin = deploy(create_goblin(name="Book Goblin", position=(1, 1), faction="monsters"))
    Entity.update_all_entities_senses()

    action_names = action_template_names(goblin)
    hide_template = goblin.get_action_template("Hide")
    disengage_template = goblin.get_action_template("Disengage")
    nimble_hide = goblin.get_action_template("Nimble Escape: Hide")
    nimble_disengage = goblin.get_action_template("Nimble Escape: Disengage")

    assert has_darkvision(goblin)
    assert equipped_item_name(goblin, WeaponSlot.RANGED_MAIN) == "Shortbow"
    assert "Attack_RANGED_MAIN" in action_names
    assert {"Nimble Escape: Hide", "Nimble Escape: Disengage"} <= action_names

    assert {"Hide", "Disengage"} <= action_names
    assert hide_template is not None
    assert disengage_template is not None
    assert nimble_hide is not None
    assert nimble_disengage is not None
    assert [cost.cost_type for cost in hide_template.effective_costs] == ["actions"]
    assert [cost.cost_type for cost in disengage_template.effective_costs] == ["actions"]
    assert [cost.cost_type for cost in nimble_hide.effective_costs] == ["bonus_actions"]
    assert [cost.cost_type for cost in nimble_disengage.effective_costs] == ["bonus_actions"]

    nimble_event = nimble_disengage.instantiate().apply()
    assert nimble_event is not None
    assert not nimble_event.canceled
    assert goblin.action_economy.actions.normalized_score == 1
    assert goblin.action_economy.bonus_actions.normalized_score == 0
    assert "Disengaging" in goblin.active_conditions


def test_eb_17_008_base_skeleton_factory_models_srd_senses_attacks_and_immunities() -> None:
    """EB-17-008: base skeleton factory models SRD senses, attacks, and immunities."""
    reset_monster_state()

    skeleton = deploy(create_skeleton(name="Book Skeleton", position=(1, 1), faction="monsters"))
    skeleton_without_darkvision = deploy(create_skeleton(
        name="Book Skeleton Without Darkvision",
        position=(3, 1),
        faction="monsters",
        darkvision=False,
    ))
    Entity.update_all_entities_senses()

    action_names = action_template_names(skeleton)
    poisoned_event = skeleton.add_condition(
        Poisoned(source_entity_uuid=skeleton.uuid, target_entity_uuid=skeleton.uuid)
    )
    exhaustion_event = skeleton.add_condition(
        Exhaustion(source_entity_uuid=skeleton.uuid, target_entity_uuid=skeleton.uuid)
    )

    assert has_darkvision(skeleton)
    assert not has_darkvision(skeleton_without_darkvision)
    assert equipped_item_name(skeleton, WeaponSlot.RANGED_MAIN) == "Shortbow"
    assert "Attack_RANGED_MAIN" in action_names

    assert skeleton.health.get_resistance(DamageType.POISON) == ResistanceStatus.IMMUNITY
    assert skeleton.check_condition_immunity("Poisoned")
    assert skeleton.check_condition_immunity("Exhaustion")
    assert poisoned_event is not None
    assert poisoned_event.canceled
    assert exhaustion_event is not None
    assert exhaustion_event.canceled
    assert "Poisoned" not in skeleton.active_conditions
    assert "Exhaustion" not in skeleton.active_conditions


def test_eb_17_009_monster_average_hit_dice_use_first_die_maximum() -> None:
    """EB-17-009: monster average HP uses maximum first die plus fixed averages."""
    reset_monster_state()

    goblin = deploy(create_goblin(name="Book Goblin", position=(1, 1), faction="monsters"))
    skeleton = deploy(create_skeleton(name="Book Skeleton", position=(3, 1), faction="monsters"))

    goblin_hit_dice = goblin.health.hit_dices[0]
    skeleton_hit_dice = skeleton.health.hit_dices[0]

    assert goblin_hit_dice.mode == "average"
    assert not goblin_hit_dice.ignore_first_level
    assert goblin_hit_dice.hit_dice_value.score == 6
    assert goblin_hit_dice.hit_dice_count.score == 2
    assert goblin_hit_dice.hit_points == 10
    assert goblin.ability_scores.constitution.modifier == 0
    assert get_max_hp(goblin) == 10

    assert skeleton_hit_dice.mode == "average"
    assert not skeleton_hit_dice.ignore_first_level
    assert skeleton_hit_dice.hit_dice_value.score == 8
    assert skeleton_hit_dice.hit_dice_count.score == 2
    assert skeleton_hit_dice.hit_points == 13
    assert skeleton.ability_scores.constitution.modifier == 2
    assert skeleton.health.get_max_hit_dices_points(constitution_modifier=2) == 17
    assert get_max_hp(skeleton) == 17


def test_eb_17_010_create_caster_wires_generic_spellcaster_state() -> None:
    """EB-17-010: create_caster wires a generic engine spellcaster."""
    reset_monster_state()

    caster = deploy(create_caster(name="Book Caster", position=(1, 1), faction="heroes", level=5))
    Entity.update_all_entities_senses()

    action_names = action_template_names(caster)
    hit_dice = caster.health.hit_dices[0]
    shield_handler = caster.get_event_handler_by_name("Shield")
    expected_spell_slots = {1: 4, 2: 3, 3: 2, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0}
    expected_spell_actions = {
        "Fire Bolt",
        "Magic Missile",
        "Fireball",
        "Burning Hands",
        "Lightning Bolt",
        "Shatter",
        "Thunderwave",
        "Invisibility",
        "Greater Invisibility",
    }

    assert caster.is_spellcaster
    assert caster.spellcasting.spellcasting_ability == "charisma"
    assert caster.ability_scores.charisma.modifier == 4
    assert caster.proficiency_bonus.normalized_score == 3
    assert caster.spell_attack_bonus().normalized_score == 7
    assert caster.spell_save_dc() == 15

    assert hit_dice.mode == "maximums"
    assert hit_dice.hit_dice_value.score == 6
    assert hit_dice.hit_dice_count.score == 5
    assert hit_dice.hit_points == 30
    assert caster.ability_scores.constitution.modifier == 2
    assert get_max_hp(caster) == 40

    for slot_level, slot_count in expected_spell_slots.items():
        assert caster.action_economy.spell_slot_value(slot_level).normalized_score == slot_count

    assert expected_spell_actions <= action_names
    assert equipped_item_name(caster, WeaponSlot.MELEE_MAIN) == "Dagger"
    assert "Attack_MELEE_MAIN" in action_names
    assert shield_handler is not None
    assert shield_handler.player_toggleable


def test_eb_17_011_create_caster_inventory_potions_are_item_use_actions() -> None:
    """EB-17-011: create_caster potions expose bonus-action item use."""
    reset_monster_state()

    caster = deploy(create_caster(name="Book Caster", position=(1, 1), faction="heroes", level=5))
    Entity.update_all_entities_senses()

    invisibility_potion = get_inventory_item(caster, "Potion of Greater Invisibility")
    haste_potion = get_inventory_item(caster, "Potion of Haste")
    invisibility_actions = invisibility_potion.get_use_actions(caster.uuid)
    haste_actions = haste_potion.get_use_actions(caster.uuid)
    available_item_names = available_item_template_names(caster)

    assert invisibility_potion.is_consumable
    assert invisibility_potion.charges == 1
    assert (
        invisibility_potion.stack_id
        == GREATER_INVISIBILITY_POTION_RECIPE.recipe_digest
    )
    assert len(invisibility_actions) == 1
    assert invisibility_actions[0].name == "Drink Greater Invisibility Potion"
    assert invisibility_actions[0].source_item_uuid == invisibility_potion.uuid
    assert [
        (cost.cost_type, cost.cost)
        for cost in invisibility_actions[0].effective_costs
    ] == [("bonus_actions", 1)]

    assert haste_potion.is_consumable
    assert haste_potion.charges == 1
    assert haste_potion.stack_id == HASTE_POTION_RECIPE.recipe_digest
    assert len(haste_actions) == 1
    assert haste_actions[0].name == "Drink Haste Potion"
    assert haste_actions[0].source_item_uuid == haste_potion.uuid
    assert [
        (cost.cost_type, cost.cost)
        for cost in haste_actions[0].effective_costs
    ] == [("bonus_actions", 1)]

    assert any(name.startswith("Drink Greater Invisibility Potion") for name in available_item_names)
    assert any(name.startswith("Drink Haste Potion") for name in available_item_names)

    invisibility_event = execute_use_action(
        caster,
        invisibility_potion.uuid,
        "Drink Greater Invisibility Potion",
    )
    blocked_haste_event = execute_use_action(
        caster,
        haste_potion.uuid,
        "Drink Haste Potion",
    )

    assert invisibility_event is not None
    assert not invisibility_event.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.bonus_actions.normalized_score == 0
    assert "Invisible" in caster.active_conditions
    assert invisibility_potion.uuid not in caster.inventory.items
    assert BaseBlock.get(invisibility_potion.uuid) is None
    assert blocked_haste_event is None
    assert "Haste" not in caster.active_conditions
    assert haste_potion.uuid in caster.inventory.items
    assert haste_potion.charges == 1


def test_eb_17_012_circus_warrior_preset_applies_custom_condition_bundle() -> None:
    """EB-17-012: circus warrior preset applies legacy custom condition bundle."""
    reset_monster_state()

    performer = create_warrior(
        source_id=uuid4(),
        proficiency_bonus=2,
        name="Book Performer",
        position=(1, 1),
    )
    Entity.update_all_entities_senses()

    main_weapon = performer.equipment.get_item_by_slot(WeaponSlot.MELEE_MAIN)
    off_weapon = performer.equipment.get_item_by_slot(WeaponSlot.MELEE_OFF)
    hit_dice_summary = [
        (hit_dice.hit_dice_value.score, hit_dice.hit_dice_count.score, hit_dice.mode, hit_dice.ignore_first_level, hit_dice.hit_points)
        for hit_dice in performer.health.hit_dices
    ]

    assert action_template_names(performer) == set()
    assert performer.get_event_handler_by_name("Opportunity Attack Handler") is not None
    assert set(performer.active_conditions) == {
        "Circus Performer",
        "Dual Wielder",
        "Elemental Affinity",
        "Elemental Weapon Mastery",
    }

    assert hit_dice_summary == [
        (10, 4, "average", False, 28),
        (8, 1, "average", True, 5),
    ]
    assert performer.ability_scores.constitution.modifier == 3
    assert get_max_hp(performer) == 48
    assert get_hp(performer) == 58
    assert performer.health.temporary_hit_points.score == 10
    assert performer.health.damage_reduction.normalized_score == 1

    assert performer.ability_scores.strength.ability_score.score == 16
    assert performer.ability_scores.strength.modifier == 4
    assert performer.ability_scores.dexterity.modifier == 1
    assert performer.proficiency_bonus.normalized_score == 1

    assert equipped_item_name(performer, WeaponSlot.MELEE_MAIN) == "Flaming Scimitar"
    assert equipped_item_name(performer, WeaponSlot.MELEE_OFF) == "Rusty Dagger"
    assert isinstance(main_weapon, Weapon)
    assert isinstance(off_weapon, Weapon)
    assert main_weapon.extra_damage_type == [DamageType.FIRE]
    assert main_weapon.extra_damage_dices == [6]
    assert off_weapon.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE

    assert performer.ac_bonus().normalized_score == 14
    assert performer.health.get_resistance(DamageType.FIRE) == ResistanceStatus.RESISTANCE
    assert performer.health.get_resistance(DamageType.COLD) == ResistanceStatus.VULNERABILITY
    performer.remove_condition("Elemental Affinity")
    assert performer.health.get_resistance(DamageType.FIRE) == ResistanceStatus.NONE
    assert performer.health.get_resistance(DamageType.COLD) == ResistanceStatus.NONE
    assert performer.action_economy.actions.normalized_score == 100
    assert performer.action_economy.reactions.normalized_score == 3
    assert performer.action_economy.movement.normalized_score == 25
    assert performer.skill_set.get_skill("acrobatics").skill_bonus.normalized_score == 7
    assert performer.skill_set.get_skill("history").skill_bonus.normalized_score == -2
    assert performer.saving_throws.get_saving_throw("strength").bonus.normalized_score == 1
    assert performer.saving_throws.get_saving_throw("intelligence").bonus.normalized_score == -1
    assert performer.equipment.unarmed_damage_bonus.normalized_score == 1


def test_circus_warrior_defaults_to_fresh_identity_without_debug_handler() -> None:
    """The retained circus actor factory has no import-time identity or print hook."""
    reset_monster_state()

    first = create_warrior(blinded=True)
    second = create_warrior(blinded=True)

    assert first.uuid != second.uuid
    assert first.get_event_handler_by_name("Attack Handler") is None
    assert second.get_event_handler_by_name("Attack Handler") is None


def test_eb_17_002_specialized_skeleton_presets_wire_equipment_items_and_actions() -> None:
    """EB-17-002: specialized skeleton presets compose equipment, items, and actions."""
    reset_monster_state()

    warrior = deploy(create_skeleton_warrior(name="Book Warrior", position=(1, 1), faction="monsters"))
    archer = deploy(create_skeleton_archer(name="Book Archer", position=(3, 1), faction="monsters"))
    warlock = deploy(create_skeleton_warlock(name="Book Warlock", position=(5, 1), faction="monsters"))
    deploy(create_skeleton(name="Target", position=(8, 1), faction="heroes"))
    Entity.update_all_entities_senses()

    assert get_max_hp(warrior) > get_max_hp(archer) > get_max_hp(warlock)
    assert warrior.ac_bonus().normalized_score == 15
    assert equipped_item_name(warrior, WeaponSlot.MELEE_MAIN) == "Longsword"
    assert equipped_item_name(warrior, WeaponSlot.MELEE_OFF) == "Wooden Shield"
    assert "Acid Flask" in inventory_item_names(warrior)
    assert "Attack_MELEE_MAIN" in action_template_names(warrior)

    assert archer.ac_bonus().normalized_score == 13
    assert archer.ability_scores.dexterity.modifier == 3
    assert equipped_item_name(archer, WeaponSlot.RANGED_MAIN) == "Shortbow"
    assert equipped_item_name(archer, WeaponSlot.MELEE_MAIN) == "Dagger"
    assert equipped_item_name(archer, WeaponSlot.MELEE_OFF) == "Dagger"
    assert "Mark Target" in action_template_names(archer)
    assert "Attack_RANGED_MAIN" in action_template_names(archer)

    assert warlock.is_spellcaster
    assert warlock.ability_scores.charisma.modifier == 2
    assert warlock.action_economy.spell_slot_value(1).normalized_score == 2
    assert warlock.action_economy.spell_slot_value(2).normalized_score == 1
    assert equipped_item_name(warlock, WeaponSlot.MELEE_MAIN) == "Arcane Staff"
    assert "Scroll of Invisibility" in inventory_item_names(warlock)
    assert {"Eldritch Blast", "Burning Hands", "Thunderwave", "Necrotic Bless"} <= action_template_names(warlock)


def test_eb_17_003_mark_target_creates_concentration_link_and_cleans_target_state() -> None:
    """EB-17-003: Mark Target creates linked concentration and cleans on removal."""
    reset_monster_state()
    archer = deploy(create_skeleton_archer(name="Book Archer", position=(1, 1), faction="monsters"))
    target = deploy(create_skeleton(name="Book Target", position=(5, 1), faction="heroes"))
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
    assert (target.uuid, marked.uuid) in concentrating.linked_conditions

    advantage_modifiers = target.equipment.ac_bonus.to_target_static.advantage_modifiers.values()
    assert any(
        modifier.name == "Marked" and modifier.value == AdvantageStatus.ADVANTAGE
        for modifier in advantage_modifiers
    )
    assert target.check_condition_immunity("Invisible")
    assert target.check_condition_immunity("Hidden")

    archer.remove_condition("Concentrating")

    assert "Concentrating" not in archer.active_conditions
    assert "Marked" not in target.active_conditions
    assert not target.check_condition_immunity("Invisible")
    assert not target.check_condition_immunity("Hidden")
    assert not any(
        modifier.name == "Marked"
        for modifier in target.equipment.ac_bonus.to_target_static.advantage_modifiers.values()
    )


def test_eb_17_004_mark_target_strips_and_blocks_hidden_or_invisible_state() -> None:
    """EB-17-004: Mark Target strips existing stealth state and blocks future stealth state."""
    reset_monster_state()
    archer = deploy(create_skeleton_archer(name="Book Archer", position=(1, 1), faction="monsters"))
    target = deploy(create_skeleton(name="Book Target", position=(5, 1), faction="heroes"))
    archer.senses.sense_modes.append(SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60))
    target.add_condition(Invisible(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    Entity.update_all_entities_senses()

    assert target.is_invisible

    event = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    ).apply()

    assert event is not None
    assert not event.canceled
    assert "Marked" in target.active_conditions
    assert "Invisible" not in target.active_conditions
    assert not target.is_invisible

    target.add_condition(InvisibilityEffect(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    target.add_condition(Hidden(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid, stealth_result=20))

    assert "Invisible" not in target.active_conditions
    assert "Hidden" not in target.active_conditions
    assert not target.is_invisible
    assert target.stealth_dc is None


def test_eb_17_005_warlock_eldritch_blast_and_scroll_are_action_driven() -> None:
    """EB-17-005: skeleton warlock spells and scroll use normal action machinery."""
    reset_monster_state()
    warlock = deploy(create_skeleton_warlock(name="Book Warlock", position=(1, 1), faction="monsters"))
    target = deploy(create_skeleton(name="Book Target", position=(8, 1), faction="heroes"))
    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)
    modifier_uuid = force_spell_attack_hit(warlock)
    try:
        event = EldritchBlast(
            source_entity_uuid=warlock.uuid,
            target_entity_uuid=target.uuid,
            caster_level=1,
        ).apply()
    finally:
        remove_spell_attack_modifier(warlock, modifier_uuid)

    assert event is not None
    assert not event.canceled
    assert get_hp(target) < initial_hp
    assert warlock.action_economy.spell_slot_value(1).normalized_score == 2

    scroll = get_inventory_item(warlock, "Scroll of Invisibility")
    scroll_actions = scroll.get_use_actions(warlock.uuid)
    assert len(scroll_actions) == 1
    assert scroll_actions[0].name == "Invisibility"
    assert scroll_actions[0].source_item_uuid == scroll.uuid
    assert not any(cost.cost_type.startswith("spell_slot") for cost in scroll_actions[0].effective_costs)

    warlock.action_economy.reset_all_costs()
    available = get_available_actions(warlock)
    item_use_actions = [
        action
        for bucket in (
            available.entity_actions,
            available.self_actions,
            available.position_actions,
            available.object_actions,
        )
        for action in bucket
        if action.is_item_use
    ]
    assert any(
        action.template_name.startswith("Invisibility") and action.source_item_uuid == scroll.uuid
        for action in item_use_actions
    )


def test_eb_17_006_warrior_acid_flask_is_a_consumable_spell_item() -> None:
    """EB-17-006: Acid Flask is inventory-backed and applies item spell damage."""
    reset_monster_state()
    warrior = deploy(create_skeleton_warrior(name="Book Warrior", position=(1, 1), faction="monsters"))
    target = deploy(create_skeleton(name="Book Target", position=(5, 5), faction="heroes"))
    Entity.update_all_entities_senses()

    flask = get_inventory_item(warrior, "Acid Flask")
    use_actions = flask.get_use_actions(warrior.uuid)
    initial_hp = get_hp(target)
    action = use_actions[0].instantiate(end_position=target.position)
    event = action.apply()

    assert flask.is_consumable
    assert flask.charges == 0
    assert BaseBlock.get(flask.uuid) is None
    assert flask.uuid not in warrior.inventory.items
    assert len(use_actions) == 1
    assert action.name == "Acid Flask"
    assert action.source_item_uuid == flask.uuid
    assert event is not None
    assert not event.canceled
    assert get_hp(target) < initial_hp


def run_all_tests() -> None:
    """Run all Chapter 17 parity examples as a script."""
    tests = [
        test_eb_17_001_goblin_and_skeleton_factories_encode_srd_trait_state,
        test_eb_17_007_base_goblin_factory_models_srd_senses_attacks_and_nimble_escape,
        test_eb_17_008_base_skeleton_factory_models_srd_senses_attacks_and_immunities,
        test_eb_17_009_monster_average_hit_dice_use_first_die_maximum,
        test_eb_17_010_create_caster_wires_generic_spellcaster_state,
        test_eb_17_011_create_caster_inventory_potions_are_item_use_actions,
        test_eb_17_012_circus_warrior_preset_applies_custom_condition_bundle,
        test_eb_17_002_specialized_skeleton_presets_wire_equipment_items_and_actions,
        test_eb_17_003_mark_target_creates_concentration_link_and_cleans_target_state,
        test_eb_17_004_mark_target_strips_and_blocks_hidden_or_invisible_state,
        test_eb_17_005_warlock_eldritch_blast_and_scroll_are_action_driven,
        test_eb_17_006_warrior_acid_flask_is_a_consumable_spell_item,
    ]
    for test in tests:
        test()
    print("Chapter 17 monster and preset engine book examples passed.")


if __name__ == "__main__":
    run_all_tests()
