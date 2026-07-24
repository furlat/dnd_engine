"""Manual Chapter 16 checks for monsters and preset actors."""

from dnd.blocks.base_item import UsableItem
from dnd.conditions import Exhaustion, Poisoned
from dnd.core.base_block import BaseBlock, SensesType
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.base_actions import (
    ActionSetupDuration,
    ActionSetupMaintenanceFailure,
    ActionSetupMaintenanceTrigger,
)
from dnd.core.base_object import BaseObject
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.modifiers import (
    AdvantageStatus,
    CreatureType,
    DamageType,
    ResistanceStatus,
)
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
from dnd.monsters.skeleton_abilities import MarkTargetAction


def reset_monster_preset_state(width: int = 30, height: int = 15) -> None:
    """Clear global state and create a rectangular monster arena."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    SpellProtectionRegistry.reset()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, width, height)


def action_template_names(entity: Entity) -> set[str]:
    """Return registered action-template names for an entity."""
    return {action.name for action in entity.registered_actions if action.name}


def inventory_item_names(entity: Entity) -> set[str]:
    """Return item names directly stored in an entity inventory."""
    return {item.name for item in entity.inventory.items.values() if item.name}


def equipped_item_name(entity: Entity, slot: WeaponSlot) -> str:
    """Return the name of the equipped item in a weapon slot."""
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


def test_first_monster_example_prints_stat_block_actor_state(capsys) -> None:
    """The opening monster example prints factory-created actor state."""
    reset_monster_preset_state()

    goblin = create_goblin(name="Manual Goblin", position=(1, 1), faction="monsters")
    skeleton = create_skeleton(
        name="Manual Skeleton",
        position=(3, 1),
        faction="monsters",
    )
    skeleton_without_darkvision = create_skeleton(
        name="Manual Skeleton Without Darkvision",
        position=(5, 1),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=30)

    poisoned_event = skeleton.add_condition(
        Poisoned(source_entity_uuid=skeleton.uuid, target_entity_uuid=skeleton.uuid)
    )
    exhaustion_event = skeleton.add_condition(
        Exhaustion(source_entity_uuid=skeleton.uuid, target_entity_uuid=skeleton.uuid)
    )

    readout_lines = [
        (
            f"goblin: hp={goblin.get_max_hp()}, "
            f"ac={goblin.ac_bonus().normalized_score}, "
            f"dex_mod={goblin.ability_scores.dexterity.modifier}, "
            f"darkvision={'yes' if has_darkvision(goblin) else 'no'}"
        ),
        (
            "goblin loadout: "
            f"melee={equipped_item_name(goblin, WeaponSlot.MELEE_MAIN)}, "
            f"ranged={equipped_item_name(goblin, WeaponSlot.RANGED_MAIN)}"
        ),
        (
            "goblin actions: "
            f"melee={'yes' if 'Attack_MELEE_MAIN' in action_template_names(goblin) else 'no'}, "
            f"ranged={'yes' if 'Attack_RANGED_MAIN' in action_template_names(goblin) else 'no'}, "
            f"nimble_hide={'yes' if 'Nimble Escape: Hide' in action_template_names(goblin) else 'no'}"
        ),
        (
            f"skeleton: hp={skeleton.get_max_hp()}, "
            f"type={skeleton.creature_type.value}, "
            f"darkvision={'yes' if has_darkvision(skeleton) else 'no'}, "
            f"opt_out_darkvision="
            f"{'yes' if has_darkvision(skeleton_without_darkvision) else 'no'}"
        ),
        (
            "skeleton loadout: "
            f"melee={equipped_item_name(skeleton, WeaponSlot.MELEE_MAIN)}, "
            f"ranged={equipped_item_name(skeleton, WeaponSlot.RANGED_MAIN)}"
        ),
        (
            "skeleton traits: "
            f"bludgeoning={skeleton.health.get_resistance(DamageType.BLUDGEONING).value}, "
            f"poison={skeleton.health.get_resistance(DamageType.POISON).value}"
        ),
        (
            "skeleton condition gates: "
            f"poisoned={'yes' if skeleton.check_condition_immunity('Poisoned') else 'no'}, "
            f"exhaustion={'yes' if skeleton.check_condition_immunity('Exhaustion') else 'no'}"
        ),
        (
            "condition attempts canceled: "
            f"poisoned={'yes' if poisoned_event is not None and poisoned_event.canceled else 'no'}, "
            f"exhaustion={'yes' if exhaustion_event is not None and exhaustion_event.canceled else 'no'}"
        ),
        (
            "active blocked conditions: "
            f"Poisoned={'yes' if 'Poisoned' in skeleton.active_conditions else 'no'}, "
            f"Exhaustion={'yes' if 'Exhaustion' in skeleton.active_conditions else 'no'}"
        ),
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "goblin: hp=10, ac=15, dex_mod=2, darkvision=yes",
        "goblin loadout: melee=Scimitar, ranged=Shortbow",
        "goblin actions: melee=yes, ranged=yes, nimble_hide=yes",
        "skeleton: hp=17, type=undead, darkvision=yes, opt_out_darkvision=no",
        "skeleton loadout: melee=Shortsword, ranged=Shortbow",
        "skeleton traits: bludgeoning=Vulnerability, poison=Immunity",
        "skeleton condition gates: poisoned=yes, exhaustion=yes",
        "condition attempts canceled: poisoned=yes, exhaustion=yes",
        "active blocked conditions: Poisoned=no, Exhaustion=no",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_base_goblin_and_skeleton_factories_encode_monster_state(capsys) -> None:
    """Base monster factories produce ready-to-use enemy entities."""
    reset_monster_preset_state()

    goblin = create_goblin(name="Manual Goblin", position=(1, 1), faction="monsters")
    skeleton = create_skeleton(name="Manual Skeleton", position=(3, 1), faction="monsters")
    skeleton_without_darkvision = create_skeleton(
        name="Manual Skeleton Without Darkvision",
        position=(5, 1),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=30)

    assert goblin.get_max_hp() == 10
    assert goblin.ac_bonus().normalized_score == 15
    assert goblin.ability_scores.dexterity.modifier == 2
    assert has_darkvision(goblin)
    assert equipped_item_name(goblin, WeaponSlot.MELEE_MAIN) == "Scimitar"
    assert equipped_item_name(goblin, WeaponSlot.RANGED_MAIN) == "Shortbow"
    assert "Attack_MELEE_MAIN" in action_template_names(goblin)
    assert "Attack_RANGED_MAIN" in action_template_names(goblin)

    assert skeleton.get_max_hp() == 17
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

    poisoned_event = skeleton.add_condition(
        Poisoned(source_entity_uuid=skeleton.uuid, target_entity_uuid=skeleton.uuid)
    )
    exhaustion_event = skeleton.add_condition(
        Exhaustion(source_entity_uuid=skeleton.uuid, target_entity_uuid=skeleton.uuid)
    )

    assert poisoned_event is not None
    assert poisoned_event.canceled
    assert exhaustion_event is not None
    assert exhaustion_event.canceled
    assert "Poisoned" not in skeleton.active_conditions
    assert "Exhaustion" not in skeleton.active_conditions

    readout_lines = [
        (
            f"goblin base: hp={goblin.get_max_hp()}, "
            f"ac={goblin.ac_bonus().normalized_score}, "
            f"dex_mod={goblin.ability_scores.dexterity.modifier}, "
            f"darkvision={has_darkvision(goblin)}, "
            f"melee={equipped_item_name(goblin, WeaponSlot.MELEE_MAIN)}, "
            f"ranged={equipped_item_name(goblin, WeaponSlot.RANGED_MAIN)}"
        ),
        (
            f"goblin actions: melee={'Attack_MELEE_MAIN' in action_template_names(goblin)}, "
            f"ranged={'Attack_RANGED_MAIN' in action_template_names(goblin)}, "
            f"nimble={'Nimble Escape: Hide' in action_template_names(goblin)}"
        ),
        (
            f"skeleton base: hp={skeleton.get_max_hp()}, "
            f"type={skeleton.creature_type.value}, "
            f"darkvision={has_darkvision(skeleton)}, "
            f"opt_out={has_darkvision(skeleton_without_darkvision)}, "
            f"melee={equipped_item_name(skeleton, WeaponSlot.MELEE_MAIN)}, "
            f"ranged={equipped_item_name(skeleton, WeaponSlot.RANGED_MAIN)}"
        ),
        (
            "skeleton traits: "
            f"bludgeoning={skeleton.health.get_resistance(DamageType.BLUDGEONING).value}, "
            f"poison={skeleton.health.get_resistance(DamageType.POISON).value}, "
            f"poisoned_gate={skeleton.check_condition_immunity('Poisoned')}, "
            f"exhaustion_gate={skeleton.check_condition_immunity('Exhaustion')}"
        ),
        (
            f"blocked conditions: poisoned_event={poisoned_event.canceled}, "
            f"exhaustion_event={exhaustion_event.canceled}, "
            f"active_poisoned={'Poisoned' in skeleton.active_conditions}, "
            f"active_exhaustion={'Exhaustion' in skeleton.active_conditions}"
        ),
    ]
    readout_lines = [
        line.replace("True", "yes").replace("False", "no")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        (
            "goblin base: hp=10, ac=15, dex_mod=2, darkvision=yes, "
            "melee=Scimitar, ranged=Shortbow"
        ),
        "goblin actions: melee=yes, ranged=yes, nimble=yes",
        (
            "skeleton base: hp=17, type=undead, darkvision=yes, opt_out=no, "
            "melee=Shortsword, ranged=Shortbow"
        ),
        (
            "skeleton traits: bludgeoning=Vulnerability, poison=Immunity, "
            "poisoned_gate=yes, exhaustion_gate=yes"
        ),
        (
            "blocked conditions: poisoned_event=yes, exhaustion_event=yes, "
            "active_poisoned=no, active_exhaustion=no"
        ),
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_goblin_nimble_escape_registers_bonus_action_variants(capsys) -> None:
    """Nimble Escape gives the goblin bonus-action Hide and Disengage rows."""
    reset_monster_preset_state()

    goblin = create_goblin(name="Manual Goblin", position=(1, 1), faction="monsters")
    Entity.update_all_entities_senses(max_distance=30)

    hide_template = goblin.get_action_template("Hide")
    disengage_template = goblin.get_action_template("Disengage")
    nimble_hide = goblin.get_action_template("Nimble Escape: Hide")
    nimble_disengage = goblin.get_action_template("Nimble Escape: Disengage")

    assert hide_template is not None
    assert disengage_template is not None
    assert nimble_hide is not None
    assert nimble_disengage is not None
    assert [cost.cost_type for cost in hide_template.effective_costs] == ["actions"]
    assert [cost.cost_type for cost in disengage_template.effective_costs] == ["actions"]
    assert [cost.cost_type for cost in nimble_hide.effective_costs] == ["bonus_actions"]
    assert [cost.cost_type for cost in nimble_disengage.effective_costs] == ["bonus_actions"]
    readout_lines = [
        (
            f"standard costs: hide={[cost.cost_type for cost in hide_template.effective_costs]}, "
            f"disengage={[cost.cost_type for cost in disengage_template.effective_costs]}"
        ),
        (
            f"nimble costs: hide={[cost.cost_type for cost in nimble_hide.effective_costs]}, "
            f"disengage={[cost.cost_type for cost in nimble_disengage.effective_costs]}"
        ),
    ]

    nimble_event = nimble_disengage.instantiate().apply()

    assert nimble_event is not None
    assert not nimble_event.canceled
    assert goblin.action_economy.actions.normalized_score == 1
    assert goblin.action_economy.bonus_actions.normalized_score == 0
    assert "Disengaging" in goblin.active_conditions
    readout_lines.append(
        (
            f"nimble disengage: canceled={nimble_event.canceled}, "
            f"actions={goblin.action_economy.actions.normalized_score}, "
            f"bonus={goblin.action_economy.bonus_actions.normalized_score}, "
            f"condition={'Disengaging' in goblin.active_conditions}"
        )
    )
    readout_lines = [
        line.replace("True", "yes").replace("False", "no")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "standard costs: hide=['actions'], disengage=['actions']",
        "nimble costs: hide=['bonus_actions'], disengage=['bonus_actions']",
        "nimble disengage: canceled=no, actions=1, bonus=0, condition=yes",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_generic_caster_preset_wires_spells_reaction_gear_and_potions(capsys) -> None:
    """The generic caster preset composes spellcasting and inventory support."""
    reset_monster_preset_state()

    caster = create_caster(name="Manual Caster", position=(1, 1), faction="heroes", level=5)
    Entity.update_all_entities_senses(max_distance=30)

    action_names = action_template_names(caster)
    hit_dice = caster.health.hit_dices[0]
    shield_handler = caster.get_event_handler_by_name("Shield")
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
    expected_spell_slots = {1: 4, 2: 3, 3: 2, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0}

    assert caster.is_spellcaster
    assert caster.spellcasting.spellcasting_ability == "charisma"
    assert caster.ability_scores.charisma.modifier == 4
    assert caster.proficiency_bonus.normalized_score == 3
    assert caster.spell_attack_bonus().normalized_score == 7
    assert caster.spell_save_dc() == 15
    assert hit_dice.mode == "maximums"
    assert hit_dice.hit_dice_value.score == 6
    assert hit_dice.hit_dice_count.score == 5
    assert caster.get_max_hp() == 40
    assert {
        slot_level: caster.action_economy._get_spell_slot_value(slot_level).normalized_score
        for slot_level in range(1, 10)
    } == expected_spell_slots
    assert expected_spell_actions <= action_names
    assert equipped_item_name(caster, WeaponSlot.MELEE_MAIN) == "Dagger"
    assert "Attack_MELEE_MAIN" in action_names
    assert shield_handler is not None
    assert shield_handler.player_toggleable

    invisibility_potion = get_inventory_item(caster, "Potion of Greater Invisibility")
    haste_potion = get_inventory_item(caster, "Potion of Haste")
    invisibility_actions = invisibility_potion.get_use_actions(caster.uuid)
    haste_actions = haste_potion.get_use_actions(caster.uuid)
    available = caster.get_available_actions()
    potion_rows = {
        row.source_item_uuid: row
        for row in available.self_actions
        if row.source_item_uuid in {invisibility_potion.uuid, haste_potion.uuid}
    }

    assert invisibility_potion.is_consumable
    assert len(invisibility_actions) == 1
    assert invisibility_actions[0].name == "Drink Greater Invisibility Potion"
    assert invisibility_actions[0].source_item_uuid == invisibility_potion.uuid
    assert len(invisibility_actions[0].effective_costs) == 1
    assert invisibility_actions[0].effective_costs[0].cost_type == "bonus_actions"
    assert invisibility_actions[0].effective_costs[0].cost == 1
    assert haste_potion.is_consumable
    assert len(haste_actions) == 1
    assert haste_actions[0].name == "Drink Haste Potion"
    assert haste_actions[0].source_item_uuid == haste_potion.uuid
    assert len(haste_actions[0].effective_costs) == 1
    assert haste_actions[0].effective_costs[0].cost_type == "bonus_actions"
    assert haste_actions[0].effective_costs[0].cost == 1
    invisibility_profile = potion_rows[invisibility_potion.uuid].self_setup_profile
    haste_profile = potion_rows[haste_potion.uuid].self_setup_profile
    assert invisibility_profile is not None
    assert invisibility_profile.semantic_id == "setup.greater_invisibility"
    assert invisibility_profile.active_condition_semantic_keys == frozenset({
        "dnd.conditions.GreaterInvisibilityEffect",
    })
    maintenance = invisibility_profile.maintenance
    stealth_bonus = caster.skill_bonus(target_entity_uuid=None, skill_name="stealth")
    assert maintenance is not None
    assert maintenance.trigger is ActionSetupMaintenanceTrigger.REVEALING_ACTION
    assert maintenance.skill_name == "stealth"
    assert maintenance.initial_dc == 15
    assert maintenance.dc_increment_per_success == 1
    assert maintenance.check_bonus == stealth_bonus.normalized_score
    assert maintenance.check_advantage is stealth_bonus.advantage
    assert maintenance.failure is ActionSetupMaintenanceFailure.REMOVE_SETUP
    assert haste_profile is not None
    assert haste_profile.semantic_id == "setup.haste"
    assert haste_profile.duration is ActionSetupDuration.UNTIL_REMOVED
    assert haste_profile.maximum_duration_rounds == 10
    assert haste_profile.extra_actions_per_turn == 1

    readout_lines = [
        (
            f"caster numbers: spellcaster={caster.is_spellcaster}, "
            f"ability={caster.spellcasting.spellcasting_ability}, "
            f"cha_mod={caster.ability_scores.charisma.modifier}, "
            f"prof={caster.proficiency_bonus.normalized_score}, "
            f"attack={caster.spell_attack_bonus().normalized_score}, "
            f"dc={caster.spell_save_dc()}"
        ),
        (
            f"caster durability: hit_dice={hit_dice.hit_dice_count.score}"
            f"d{hit_dice.hit_dice_value.score}, mode={hit_dice.mode}, "
            f"hp={caster.get_max_hp()}, "
            f"level3_slots={caster.action_economy.spell_slot_3.normalized_score}"
        ),
        (
            f"caster actions: spells={len(expected_spell_actions & action_names)}/"
            f"{len(expected_spell_actions)}, "
            f"dagger={equipped_item_name(caster, WeaponSlot.MELEE_MAIN)}, "
            f"attack={'Attack_MELEE_MAIN' in action_names}, "
            f"shield_handler={shield_handler is not None and shield_handler.player_toggleable}"
        ),
        (
            f"caster potions: invisibility={invisibility_actions[0].name}, "
            f"invisibility_costs={len(invisibility_actions[0].effective_costs)}, "
            f"haste={haste_actions[0].name}, "
            f"haste_costs={len(haste_actions[0].effective_costs)}"
        ),
    ]
    readout_lines = [
        line.replace("True", "yes").replace("False", "no")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        (
            "caster numbers: spellcaster=yes, ability=charisma, cha_mod=4, "
            "prof=3, attack=7, dc=15"
        ),
        "caster durability: hit_dice=5d6, mode=maximums, hp=40, level3_slots=2",
        "caster actions: spells=9/9, dagger=Dagger, attack=yes, shield_handler=yes",
        (
            "caster potions: invisibility=Drink Greater Invisibility Potion, "
            "invisibility_costs=1, haste=Drink Haste Potion, haste_costs=1"
        ),
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_skeleton_role_presets_compose_equipment_items_actions_and_spells(capsys) -> None:
    """Game-specific skeleton presets create distinct tactical roles."""
    reset_monster_preset_state()

    warrior = create_skeleton_warrior(name="Manual Warrior", position=(1, 1), faction="monsters")
    archer = create_skeleton_archer(name="Manual Archer", position=(3, 1), faction="monsters")
    warlock = create_skeleton_warlock(name="Manual Warlock", position=(5, 1), faction="monsters")
    create_skeleton(name="Manual Target", position=(8, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)

    assert warrior.get_max_hp() > archer.get_max_hp() > warlock.get_max_hp()
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
    assert warlock.action_economy.spell_slot_1.normalized_score == 2
    assert warlock.action_economy.spell_slot_2.normalized_score == 1
    assert equipped_item_name(warlock, WeaponSlot.MELEE_MAIN) == "Arcane Staff"
    assert "Scroll of Invisibility" in inventory_item_names(warlock)
    assert {"Eldritch Blast", "Burning Hands", "Thunderwave", "Necrotic Bless"} <= action_template_names(warlock)

    warlock_spells = {
        "Eldritch Blast",
        "Burning Hands",
        "Thunderwave",
        "Necrotic Bless",
    } <= action_template_names(warlock)
    readout_lines = [
        (
            f"warrior: hp={warrior.get_max_hp()}, "
            f"ac={warrior.ac_bonus().normalized_score}, "
            f"melee={equipped_item_name(warrior, WeaponSlot.MELEE_MAIN)} + "
            f"{equipped_item_name(warrior, WeaponSlot.MELEE_OFF)}, "
            f"acid={'Acid Flask' in inventory_item_names(warrior)}, "
            f"attack={'Attack_MELEE_MAIN' in action_template_names(warrior)}"
        ),
        (
            f"archer: hp={archer.get_max_hp()}, "
            f"ac={archer.ac_bonus().normalized_score}, "
            f"dex_mod={archer.ability_scores.dexterity.modifier}, "
            f"ranged={equipped_item_name(archer, WeaponSlot.RANGED_MAIN)}, "
            f"melee={equipped_item_name(archer, WeaponSlot.MELEE_MAIN)} + "
            f"{equipped_item_name(archer, WeaponSlot.MELEE_OFF)}, "
            f"mark={'Mark Target' in action_template_names(archer)}"
        ),
        (
            f"warlock: hp={warlock.get_max_hp()}, "
            f"cha_mod={warlock.ability_scores.charisma.modifier}, "
            f"slots=1:{warlock.action_economy.spell_slot_1.normalized_score}/"
            f"2:{warlock.action_economy.spell_slot_2.normalized_score}, "
            f"melee={equipped_item_name(warlock, WeaponSlot.MELEE_MAIN)}, "
            f"scroll={'Scroll of Invisibility' in inventory_item_names(warlock)}"
        ),
        (
            f"role spread: hp_order={warrior.get_max_hp()}>{archer.get_max_hp()}>"
            f"{warlock.get_max_hp()}, warlock_spells={warlock_spells}, "
            "target=Manual Target"
        ),
    ]
    readout_lines = [
        line.replace("True", "yes").replace("False", "no")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "warrior: hp=31, ac=15, melee=Longsword + Wooden Shield, acid=yes, attack=yes",
        "archer: hp=24, ac=13, dex_mod=3, ranged=Shortbow, melee=Dagger + Dagger, mark=yes",
        "warlock: hp=17, cha_mod=2, slots=1:2/2:1, melee=Arcane Staff, scroll=yes",
        "role spread: hp_order=31>24>17, warlock_spells=yes, target=Manual Target",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_mark_target_creates_concentration_owned_target_state(capsys) -> None:
    """Skeleton archer Mark Target links target state to archer concentration."""
    reset_monster_preset_state()

    archer = create_skeleton_archer(name="Manual Archer", position=(1, 1), faction="monsters")
    target = create_skeleton(name="Manual Target", position=(5, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)

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
    readout_lines = [
        (
            f"mark target: canceled={event.canceled}, "
            f"marked={'Marked' in target.active_conditions}, "
            f"concentrating={'Concentrating' in archer.active_conditions}, "
            f"cooldown={'Mark Cooldown' in archer.active_conditions}, "
            f"bonus={archer.action_economy.bonus_actions.normalized_score}"
        ),
        (
            f"mark ownership: linked={(target.uuid, marked.uuid) in concentrating.linked_conditions}, "
            f"attacker_advantage={any(modifier.name == 'Marked' and modifier.value == AdvantageStatus.ADVANTAGE for modifier in advantage_modifiers)}, "
            f"blocks_invisible={target.check_condition_immunity('Invisible')}, "
            f"blocks_hidden={target.check_condition_immunity('Hidden')}"
        ),
    ]

    archer.remove_condition("Concentrating")

    assert "Concentrating" not in archer.active_conditions
    assert "Marked" not in target.active_conditions
    assert not target.check_condition_immunity("Invisible")
    assert not target.check_condition_immunity("Hidden")
    assert not any(
        modifier.name == "Marked"
        for modifier in target.equipment.ac_bonus.to_target_static.advantage_modifiers.values()
    )
    readout_lines.append(
        (
            f"after concentration cleanup: concentrating="
            f"{'Concentrating' in archer.active_conditions}, "
            f"marked={'Marked' in target.active_conditions}, "
            f"blocks_invisible={target.check_condition_immunity('Invisible')}, "
            f"blocks_hidden={target.check_condition_immunity('Hidden')}, "
            f"marked_modifier={any(modifier.name == 'Marked' for modifier in target.equipment.ac_bonus.to_target_static.advantage_modifiers.values())}"
        )
    )
    readout_lines = [
        line.replace("True", "yes").replace("False", "no")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "mark target: canceled=no, marked=yes, concentrating=yes, cooldown=yes, bonus=0",
        (
            "mark ownership: linked=yes, attacker_advantage=yes, "
            "blocks_invisible=yes, blocks_hidden=yes"
        ),
        (
            "after concentration cleanup: concentrating=no, marked=no, "
            "blocks_invisible=no, blocks_hidden=no, marked_modifier=no"
        ),
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"
