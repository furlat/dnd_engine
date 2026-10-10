"""Tests for specialized skeleton units: Warrior, Archer, Warlock.

Tests cover:
- Factory creation and stats
- Eldritch Blast cantrip
- Acid Flask throwable AoE
- Mark Target ability
- Arcane Staff weapon
- Scroll of Invisibility
- Warlock spellcasting integration
- Full arena integration
"""

from dnd.utils import (
    reset_combat_state, setup_combat_arena,
    get_hp, get_max_hp, set_hp, deal_damage_to,
    force_attack_hit, remove_attack_modifier,
)
from dnd.entity import Entity
from dnd.actions_functional import get_available_actions, execute_by_index
from dnd.core.events import WeaponSlot
from dnd.core.modifiers import (
    AutoHitModifier, AutoHitStatus,
    AdvantageStatus,
    DamageType,
)
from dnd.core.gridmap import get_map
from dnd.core.base_block import SenseMode, SensesType

from dnd.core.combat_log import CombatLogEntryType

from dnd.monsters.bestiary import (
    create_skeleton, create_skeleton_warrior,
    create_skeleton_archer, create_skeleton_warlock,
)
from dnd.monsters.skeleton_abilities import MarkTargetAction
from dnd.spells.evocation import EldritchBlast
from dnd.conditions import Invisible, Hidden, InvisibilityEffect



def force_spell_hit(entity: Entity):
    """Add AUTOHIT to spell attack bonus, return modifier UUID for cleanup."""
    mod = AutoHitModifier(
        name="Forced Spell Hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid
    )
    return entity.spellcasting.spell_attack_bonus.self_static.add_auto_hit_modifier(mod)


def force_spell_miss(entity: Entity):
    """Add AUTOMISS to spell attack bonus, return modifier UUID for cleanup."""
    mod = AutoHitModifier(
        name="Forced Spell Miss",
        value=AutoHitStatus.AUTOMISS,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid
    )
    return entity.spellcasting.spell_attack_bonus.self_static.add_auto_hit_modifier(mod)


def remove_spell_modifier(entity: Entity, mod_uuid):
    """Remove a spell attack modifier."""
    entity.spellcasting.spell_attack_bonus.self_static.remove_modifier(mod_uuid)


def action_names(entity: Entity) -> list:
    """Return list of available action template names."""
    avail = get_available_actions(entity)
    names = []
    for a in avail.entity_actions:
        names.append(a.template_name)
    for a in avail.self_actions:
        names.append(a.template_name)
    for a in avail.position_actions:
        names.append(a.template_name)
    for a in avail.object_actions:
        names.append(a.template_name)
    return names


def has_action_variant(names: list, base_name: str) -> bool:
    """Return whether an action list contains a base template or slot variant."""
    return base_name in names or any(name.startswith(f"{base_name}__slot_") for name in names)


def setup_pair(creator_fn, target_pos=(5, 0), creator_pos=(0, 0), **kwargs):
    """Create entity from factory + a basic target, return (entity, target)."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 15)

    entity = creator_fn(position=creator_pos, faction="monsters", **kwargs)
    target = create_skeleton(name="Target", position=target_pos, faction="heroes")
    Entity.update_all_entities_senses()
    return entity, target


passed = 0
failed = 0


def check(condition: bool, test_name: str) -> bool:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {test_name}")
        return True
    else:
        failed += 1
        print(f"  FAIL: {test_name}")
        return False



def test_skeleton_warrior_creation():
    print("\n=== Test: Skeleton Warrior Creation ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    warrior = create_skeleton_warrior(name="Test Warrior", position=(0, 0), faction="monsters")
    create_skeleton(name="Target", position=(1, 0), faction="heroes")
    Entity.update_all_entities_senses()

    warrior_hp = get_max_hp(warrior)
    check(warrior_hp > 20, f"HP > 20 (got {warrior_hp})")
    check(warrior.ac_bonus().normalized_score == 15, f"AC == 15 (got {warrior.ac_bonus().normalized_score})")

    main_weapon = warrior.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
    check(main_weapon is not None and main_weapon.name == "Longsword", "Has Longsword in MELEE_MAIN")

    off_item = warrior.equipment.get_item_by_slot(WeaponSlot.MELEE_OFF)
    check(off_item is not None and off_item.name == "Wooden Shield", "Has Wooden Shield in MELEE_OFF")

    flask_names = [item.name for item in warrior.inventory.items.values()]
    check("Acid Flask" in flask_names, "Has Acid Flask in inventory")

    names = action_names(warrior)
    check("Attack_MELEE_MAIN" in names, f"Available actions include melee attack (got: {names})")

    return warrior_hp


def test_skeleton_archer_creation():
    print("\n=== Test: Skeleton Archer Creation ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    archer = create_skeleton_archer(name="Test Archer", position=(0, 0), faction="monsters")
    create_skeleton(name="Target", position=(5, 0), faction="heroes")
    Entity.update_all_entities_senses()

    archer_hp = get_max_hp(archer)
    check(archer_hp > 15, f"HP > 15 (got {archer_hp})")
    check(archer.ac_bonus().normalized_score == 13, f"AC == 13 (got {archer.ac_bonus().normalized_score})")
    check(archer.ability_scores.dexterity.modifier == 3, f"DEX modifier == +3 (got {archer.ability_scores.dexterity.modifier})")

    ranged = archer.equipment._get_weapon_by_slot(WeaponSlot.RANGED_MAIN)
    check(ranged is not None and ranged.name == "Shortbow", "Has Shortbow in RANGED_MAIN")

    main_melee = archer.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
    check(main_melee is not None and main_melee.name == "Dagger", "Has Dagger in MELEE_MAIN")

    off_melee = archer.equipment._get_weapon_by_slot(WeaponSlot.MELEE_OFF)
    check(off_melee is not None and off_melee.name == "Dagger", "Has Dagger in MELEE_OFF")

    names = action_names(archer)
    check("Mark Target" in names, f"Available actions include Mark Target (got: {names})")
    check("Attack_RANGED_MAIN" in names, f"Available actions include ranged attack (got: {names})")

    return archer_hp


def test_skeleton_warlock_creation():
    print("\n=== Test: Skeleton Warlock Creation ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 15)

    warlock = create_skeleton_warlock(name="Test Warlock", position=(0, 0), faction="monsters")
    create_skeleton(name="Target", position=(2, 0), faction="heroes")
    Entity.update_all_entities_senses()

    warlock_hp = get_max_hp(warlock)
    check(warlock_hp > 0, f"HP > 0 (got {warlock_hp})")
    check(warlock.ac_bonus().normalized_score == 13, f"AC == 13 (got {warlock.ac_bonus().normalized_score})")
    check(warlock.ability_scores.charisma.modifier == 2, f"CHA modifier == +2 (got {warlock.ability_scores.charisma.modifier})")

    main_weapon = warlock.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
    check(main_weapon is not None and main_weapon.name == "Arcane Staff", "Has Arcane Staff in MELEE_MAIN")
    check(warlock.equipment.helmet is not None and warlock.equipment.helmet.name == "Crown", "Has Crown in helmet slot")

    check(warlock.is_spellcaster, "Is spellcaster")
    l1_slots = warlock.action_economy._get_spell_slot_value(1).normalized_score
    check(l1_slots == 2, f"Has 2x L1 spell slots (got {l1_slots})")

    scroll_names = [item.name for item in warlock.inventory.items.values()]
    check("Scroll of Invisibility" in scroll_names, "Has Scroll of Invisibility in inventory")

    names = action_names(warlock)
    check("Eldritch Blast" in names, f"Available actions include Eldritch Blast (got: {names})")
    check(has_action_variant(names, "Burning Hands"), f"Available actions include Burning Hands (got: {names})")
    check(has_action_variant(names, "Thunderwave"), f"Available actions include Thunderwave (got: {names})")

    return warlock_hp



def test_eldritch_blast_hit():
    print("\n=== Test: Eldritch Blast Hit ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 15)

    warlock = create_skeleton_warlock(name="Warlock", position=(0, 0), faction="monsters")
    target = create_skeleton(name="Target", position=(10, 0), faction="heroes")
    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)
    mod_uuid = force_spell_hit(warlock)

    blast = EldritchBlast(
        source_entity_uuid=warlock.uuid,
        target_entity_uuid=target.uuid,
        caster_level=1
    )
    result = blast.apply()

    remove_spell_modifier(warlock, mod_uuid)

    check(result is not None and not result.canceled, "Eldritch Blast executed successfully")
    check(get_hp(target) < initial_hp, f"Target took damage (HP {initial_hp} -> {get_hp(target)})")

    check(warlock.action_economy._get_spell_slot_value(1).normalized_score == 2, "No spell slot consumed (cantrip)")


def test_eldritch_blast_miss():
    print("\n=== Test: Eldritch Blast Miss ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 15)

    warlock = create_skeleton_warlock(name="Warlock", position=(0, 0), faction="monsters")
    target = create_skeleton(name="Target", position=(10, 0), faction="heroes")
    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)
    mod_uuid = force_spell_miss(warlock)

    blast = EldritchBlast(
        source_entity_uuid=warlock.uuid,
        target_entity_uuid=target.uuid,
        caster_level=1
    )
    blast.apply()

    remove_spell_modifier(warlock, mod_uuid)

    check(get_hp(target) == initial_hp, f"Target took no damage (HP unchanged at {initial_hp})")


def test_eldritch_blast_range():
    print("\n=== Test: Eldritch Blast Range ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 30)

    warlock = create_skeleton_warlock(name="Warlock", position=(0, 0), faction="monsters")
    target = create_skeleton(name="Target", position=(25, 0), faction="heroes")
    Entity.update_all_entities_senses()

    blast = EldritchBlast(
        source_entity_uuid=warlock.uuid,
        target_entity_uuid=target.uuid,
        caster_level=1
    )
    result = blast.apply()

    check(result is not None and result.canceled, "Eldritch Blast canceled — out of range")



def test_acid_flask_single_target():
    print("\n=== Test: Acid Flask Single Target ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    warrior = create_skeleton_warrior(name="Warrior", position=(0, 0), faction="monsters")
    target = create_skeleton(name="Target", position=(5, 5), faction="heroes")
    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)

    from dnd.items.test_items import AcidFlaskSpell
    spell = AcidFlaskSpell(
        source_entity_uuid=warrior.uuid,
        caster_level=1,
        end_position=(5, 5)
    )
    spell.apply()

    check(get_hp(target) < initial_hp, f"Target took acid damage (HP {initial_hp} -> {get_hp(target)})")


def test_acid_flask_aoe_multiple_targets():
    print("\n=== Test: Acid Flask AoE Multiple Targets ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    warrior = create_skeleton_warrior(name="Warrior", position=(0, 0), faction="monsters")
    target1 = create_skeleton(name="Target 1", position=(5, 5), faction="heroes")
    target2 = create_skeleton(name="Target 2", position=(5, 6), faction="heroes")
    Entity.update_all_entities_senses()

    initial_hp1 = get_hp(target1)
    initial_hp2 = get_hp(target2)

    from dnd.items.test_items import AcidFlaskSpell
    spell = AcidFlaskSpell(
        source_entity_uuid=warrior.uuid,
        caster_level=1,
        end_position=(5, 5)
    )
    spell.apply()

    check(get_hp(target1) < initial_hp1, f"Target 1 took damage (HP {initial_hp1} -> {get_hp(target1)})")
    check(get_hp(target2) < initial_hp2, f"Target 2 took damage (HP {initial_hp2} -> {get_hp(target2)})")


def test_acid_flask_consumable():
    print("\n=== Test: Acid Flask Consumable ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    warrior = create_skeleton_warrior(name="Warrior", position=(0, 0), faction="monsters")
    Entity.update_all_entities_senses()

    inventory_before = [item.name for item in warrior.inventory.items.values()]
    check("Acid Flask" in inventory_before, "Acid Flask in inventory before use")

    from dnd.blocks.base_item import UsableItem
    flask = next((item for item in warrior.inventory.items.values() if item.name == "Acid Flask"), None)
    check(flask is not None, "Found Acid Flask")
    if flask and isinstance(flask, UsableItem):
        check(flask.charges == 1, f"Flask has 1 charge (got {flask.charges})")
        check(flask.is_consumable, "Flask is consumable")



def test_mark_applies_condition():
    print("\n=== Test: Mark Target Applies Condition ===")
    archer, target = setup_pair(create_skeleton_archer)

    encounter = setup_combat_arena(archer, target)
    encounter.start_encounter()
    encounter.start_turn()

    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    result = mark.apply()

    check(result is not None and not result.canceled, "Mark Target executed successfully")
    check("Marked" in target.active_conditions, "Target has Marked condition")
    check("Concentrating" in archer.active_conditions, "Archer has Concentrating condition")


def test_mark_grants_advantage():
    print("\n=== Test: Mark Target Grants Advantage ===")
    archer, target = setup_pair(create_skeleton_archer)

    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark.apply()

    ac = target.equipment.ac_bonus
    advantage_mods = list(ac.to_target_static.advantage_modifiers.values())
    has_adv = any(m.value == AdvantageStatus.ADVANTAGE and m.name == "Marked" for m in advantage_mods)
    check(has_adv, "Target AC has 'Marked' ADVANTAGE modifier in to_target_static")


def test_mark_strips_existing_invisibility():
    print("\n=== Test: Mark Strips Existing Invisibility ===")
    archer, target = setup_pair(create_skeleton_archer)

    archer.senses.sense_modes.append(SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60))
    Entity.update_all_entities_senses()

    invis = Invisible(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(invis)
    Entity.update_all_entities_senses()
    check(target.is_invisible, "Target is invisible before mark")

    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark.apply()

    check("Invisible" not in target.active_conditions, "Invisible removed after mark")
    check(not target.is_invisible, "Target is_invisible == False after mark")


def test_mark_strips_existing_hidden():
    print("\n=== Test: Mark Strips Existing Hidden ===")
    archer, target = setup_pair(create_skeleton_archer)

    hidden = Hidden(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        stealth_result=8,
    )
    target.add_condition(hidden)
    Entity.update_all_entities_senses()
    check(target.stealth_dc is not None, "Target has stealth_dc before mark")

    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark.apply()

    check("Hidden" not in target.active_conditions, "Hidden removed after mark")
    check(target.stealth_dc is None, "Target stealth_dc is None after mark")


def test_mark_prevents_future_invisibility():
    print("\n=== Test: Mark Prevents Future Invisibility ===")
    archer, target = setup_pair(create_skeleton_archer)

    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark.apply()
    check("Marked" in target.active_conditions, "Target is marked")

    invis = InvisibilityEffect(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(invis)

    check("Invisible" not in target.active_conditions, "Invisible prevented by Mark (immunity)")
    check(not target.is_invisible, "is_invisible still False")


def test_mark_prevents_future_hidden():
    print("\n=== Test: Mark Prevents Future Hidden ===")
    archer, target = setup_pair(create_skeleton_archer)

    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark.apply()

    hidden = Hidden(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        stealth_result=20,
    )
    target.add_condition(hidden)

    check("Hidden" not in target.active_conditions, "Hidden prevented by Mark (immunity)")
    check(target.stealth_dc is None, "stealth_dc still None")


def test_mark_concentration_break():
    print("\n=== Test: Mark Concentration Break ===")
    archer, target = setup_pair(create_skeleton_archer)

    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark.apply()

    check("Marked" in target.active_conditions, "Target has Marked")
    check("Concentrating" in archer.active_conditions, "Archer concentrating")

    archer.remove_condition("Concentrating")

    check("Marked" not in target.active_conditions, "Marked removed from target after concentration break")
    check("Concentrating" not in archer.active_conditions, "Concentrating removed from archer")

    ac = target.equipment.ac_bonus
    advantage_mods = list(ac.to_target_static.advantage_modifiers.values())
    has_marked = any(m.name == "Marked" for m in advantage_mods)
    check(not has_marked, "Marked advantage modifier cleaned up from target AC")


def test_mark_concentration_break_from_damage():
    print("\n=== Test: Mark Concentration Break From Damage ===")
    archer, target = setup_pair(create_skeleton_archer)

    encounter = setup_combat_arena(archer, target)
    encounter.start_encounter()
    encounter.start_turn()

    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark.apply()

    check("Marked" in target.active_conditions, "Target has Marked before damage")
    check("Concentrating" in archer.active_conditions, "Archer concentrating before damage")

    set_hp(archer, 500)

    log_before = len(encounter.combat_log)

    deal_damage_to(archer, 100, DamageType.SLASHING, target.uuid)

    check("Concentrating" not in archer.active_conditions,
          "Concentrating removed after failed CON save from damage")
    check("Marked" not in target.active_conditions,
          "Marked removed from target (linked condition cleanup)")

    ac = target.equipment.ac_bonus
    advantage_mods = list(ac.to_target_static.advantage_modifiers.values())
    has_marked = any(m.name == "Marked" for m in advantage_mods)
    check(not has_marked, "Marked advantage modifier cleaned up from target AC")

    hidden_immune = target.check_condition_immunity("Hidden")
    invis_immune = target.check_condition_immunity("Invisible")
    check(not hidden_immune, "Hidden immunity removed after mark broken")
    check(not invis_immune, "Invisible immunity removed after mark broken")

    new_logs = encounter.combat_log[log_before:]
    check(len(new_logs) > 0, "Combat log has entries after damage")

    damage_log = None
    for entry in new_logs:
        if entry.entry_type == CombatLogEntryType.DAMAGE_TAKEN:
            damage_log = entry
            break
    check(damage_log is not None, "Found DAMAGE_TAKEN log entry")

    if damage_log:
        save_sub = [s for s in damage_log.sub_entries if s.entry_type == CombatLogEntryType.SAVING_THROW]
        check(len(save_sub) > 0, f"Concentration CON save appears as sub-entry in damage log (found {len(damage_log.sub_entries)} sub-entries)")
        if save_sub:
            save_text = save_sub[0].compact
            check("CON" in save_text or "con" in save_text.lower(), f"Save log mentions CON: {save_text}")


def test_mark_concentration_break_on_death():
    print("\n=== Test: Mark Concentration Break On Death ===")
    archer, target = setup_pair(create_skeleton_archer)

    encounter = setup_combat_arena(archer, target)
    encounter.start_encounter()
    encounter.start_turn()

    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark.apply()

    check("Marked" in target.active_conditions, "Target has Marked before death")
    check("Concentrating" in archer.active_conditions, "Archer concentrating before death")

    log_before = len(encounter.combat_log)

    deal_damage_to(archer, 9999, DamageType.SLASHING, target.uuid)

    check(not archer.has_hp, "Archer is dead")
    check("Concentrating" not in archer.active_conditions,
          "Concentrating removed on death")
    check("Marked" not in target.active_conditions,
          "Marked removed from target (linked condition cleanup on death)")

    ac = target.equipment.ac_bonus
    advantage_mods = list(ac.to_target_static.advantage_modifiers.values())
    has_marked = any(m.name == "Marked" for m in advantage_mods)
    check(not has_marked, "Marked advantage modifier cleaned up after archer death")

    new_logs = encounter.combat_log[log_before:]
    check(len(new_logs) > 0, "Combat log has entries after death")

    all_sub_types = []
    for entry in new_logs:
        for sub in entry.sub_entries:
            all_sub_types.append(sub.entry_type)
            for subsub in sub.sub_entries:
                all_sub_types.append(subsub.entry_type)

    has_condition_removed = CombatLogEntryType.CONDITION_REMOVED in all_sub_types
    check(has_condition_removed, f"Concentration removal appears in combat log sub-entries (types: {all_sub_types})")


def test_mark_bonus_action_cost():
    print("\n=== Test: Mark Target Bonus Action Cost ===")
    archer, target = setup_pair(create_skeleton_archer)

    encounter = setup_combat_arena(archer, target)
    encounter.start_encounter()
    encounter.start_turn()

    ba_before = archer.action_economy.bonus_actions.normalized_score
    check(ba_before >= 1, f"Has bonus action before mark (got {ba_before})")

    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark.apply()

    ba_after = archer.action_economy.bonus_actions.normalized_score
    check(ba_after < ba_before, f"Bonus action consumed (before={ba_before}, after={ba_after})")


def test_mark_one_use_per_rest():
    print("\n=== Test: Mark Target One Use Per Rest ===")
    archer, target = setup_pair(create_skeleton_archer)
    target2 = create_skeleton(name="Target 2", position=(3, 0), faction="heroes")
    Entity.update_all_entities_senses()

    mark1 = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark1.apply()
    check("Mark Cooldown" in archer.active_conditions, "Has Mark Cooldown after first use")

    archer.remove_condition("Concentrating")

    mark2 = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target2.uuid,
    )
    check(not mark2.pre_validate(), "pre_validate returns False (mark on cooldown)")


def test_mark_range():
    print("\n=== Test: Mark Target Range ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 15)

    archer = create_skeleton_archer(name="Archer", position=(0, 0), faction="monsters")
    target = create_skeleton(name="Target", position=(13, 0), faction="heroes")
    Entity.update_all_entities_senses()

    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    result = mark.apply()

    check(result is not None and result.canceled, "Mark Target canceled — out of range")



def test_arcane_staff_spell_attack_bonus():
    print("\n=== Test: Arcane Staff Spell Attack Bonus ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    warlock = create_skeleton_warlock(name="Warlock", position=(0, 0), faction="monsters")
    Entity.update_all_entities_senses()

    bonus_with = warlock.spellcasting.spell_attack_bonus.normalized_score
    check(bonus_with >= 1, f"Spell attack bonus >= 1 with staff (got {bonus_with})")

    staff = warlock.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
    check(staff is not None and staff.name == "Arcane Staff", "Has Arcane Staff equipped")
    if staff:
        warlock.equipment.unequip(WeaponSlot.MELEE_MAIN)
        bonus_without = warlock.spellcasting.spell_attack_bonus.normalized_score
        check(bonus_without == bonus_with - 1, f"Spell attack drops by 1 after unequip (with={bonus_with}, without={bonus_without})")

        warlock.equipment.equip(staff, WeaponSlot.MELEE_MAIN)
        bonus_re = warlock.spellcasting.spell_attack_bonus.normalized_score
        check(bonus_re == bonus_with, f"Spell attack restored after re-equip (got {bonus_re})")


def test_arcane_staff_melee():
    print("\n=== Test: Arcane Staff Melee Attack ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    warlock = create_skeleton_warlock(name="Warlock", position=(0, 0), faction="monsters")
    target = create_skeleton(name="Target", position=(1, 0), faction="heroes")
    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)

    mod_uuid = force_attack_hit(warlock)

    avail = get_available_actions(warlock)
    staff_actions = [a for a in avail.entity_actions if a.template_name == "Attack_MELEE_MAIN"]
    check(len(staff_actions) > 0, "Arcane Staff melee attack available")

    if staff_actions:
        execute_by_index(warlock, "Attack_MELEE_MAIN", 0)

    remove_attack_modifier(warlock, mod_uuid)
    check(get_hp(target) < initial_hp, f"Target took melee damage (HP {initial_hp} -> {get_hp(target)})")



def test_scroll_of_invisibility_use():
    print("\n=== Test: Scroll of Invisibility Use ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    warlock = create_skeleton_warlock(name="Warlock", position=(0, 0), faction="monsters")
    Entity.update_all_entities_senses()

    scroll = next((item for item in warlock.inventory.items.values() if item.name == "Scroll of Invisibility"), None)
    check(scroll is not None, "Scroll of Invisibility in inventory")

    if scroll:
        from dnd.actions_functional import execute_use_action
        from dnd.core.base_actions import AvailableTarget
        target = AvailableTarget(index=0, target_uuid=warlock.uuid, target_name=warlock.name)
        execute_use_action(warlock, scroll.uuid, "Invisibility", target)

        check("Invisible" in warlock.active_conditions, "Warlock gained Invisible condition")
        check(warlock.is_invisible, "Warlock is_invisible == True")


def test_scroll_no_spell_slot():
    print("\n=== Test: Scroll Does Not Consume Spell Slot ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    warlock = create_skeleton_warlock(name="Warlock", position=(0, 0), faction="monsters")
    Entity.update_all_entities_senses()

    slots_before = warlock.action_economy._get_spell_slot_value(1).normalized_score

    scroll = next((item for item in warlock.inventory.items.values() if item.name == "Scroll of Invisibility"), None)
    if scroll:
        from dnd.actions_functional import execute_use_action
        from dnd.core.base_actions import AvailableTarget
        target = AvailableTarget(index=0, target_uuid=warlock.uuid, target_name=warlock.name)
        execute_use_action(warlock, scroll.uuid, "Invisibility", target)

    slots_after = warlock.action_economy._get_spell_slot_value(1).normalized_score
    check(slots_after == slots_before, f"Spell slots unchanged (before={slots_before}, after={slots_after})")



def test_warlock_burning_hands():
    print("\n=== Test: Warlock Burning Hands ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    warlock = create_skeleton_warlock(name="Warlock", position=(5, 5), faction="monsters")
    target = create_skeleton(name="Target", position=(6, 5), faction="heroes")
    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)
    slots_before = warlock.action_economy._get_spell_slot_value(1).normalized_score

    from dnd.spells.evocation import BurningHands
    spell = BurningHands(
        source_entity_uuid=warlock.uuid,
        caster_level=1,
        end_position=(6, 5),
        cast_at_level=1,
    )
    spell.apply()

    check(get_hp(target) < initial_hp, f"Target took fire damage (HP {initial_hp} -> {get_hp(target)})")
    slots_after = warlock.action_economy._get_spell_slot_value(1).normalized_score
    check(slots_after == slots_before - 1, f"L1 slot consumed (before={slots_before}, after={slots_after})")


def test_warlock_slot_exhaustion():
    print("\n=== Test: Warlock Slot Exhaustion ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    warlock = create_skeleton_warlock(name="Warlock", position=(5, 5), faction="monsters")
    _target = create_skeleton(name="Target", position=(6, 5), faction="heroes")
    Entity.update_all_entities_senses()

    from dnd.spells.evocation import BurningHands
    for _ in range(2):
        set_hp(_target, get_max_hp(_target))
        warlock.action_economy.reset_all_costs()
        spell = BurningHands(
            source_entity_uuid=warlock.uuid,
            caster_level=1,
            end_position=(6, 5),
            cast_at_level=1,
        )
        spell.apply()

    slots_remaining = warlock.action_economy._get_spell_slot_value(1).normalized_score
    check(slots_remaining == 0, f"All L1 slots consumed (got {slots_remaining})")

    set_hp(_target, get_max_hp(_target))
    warlock.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()

    avail = get_available_actions(warlock)
    all_actions = avail.entity_actions + avail.self_actions + avail.position_actions + avail.object_actions
    eb_actions = [a for a in all_actions if a.template_name == "Eldritch Blast"]
    check(len(eb_actions) > 0, "Eldritch Blast still available (cantrip)")

    bh_l1_actions = [a for a in all_actions if a.template_name == "Burning Hands__slot_1"]
    tw_l1_actions = [a for a in all_actions if a.template_name == "Thunderwave__slot_1"]
    bh_l2_actions = [a for a in all_actions if a.template_name == "Burning Hands__slot_2"]
    tw_l2_actions = [a for a in all_actions if a.template_name == "Thunderwave__slot_2"]
    check(len(bh_l1_actions) == 0 or not bh_l1_actions[0].can_afford, "Burning Hands L1 NOT castable (no L1 slots)")
    check(len(tw_l1_actions) == 0 or not tw_l1_actions[0].can_afford, "Thunderwave L1 NOT castable (no L1 slots)")
    check(len(bh_l2_actions) > 0 and bh_l2_actions[0].can_afford, "Burning Hands L2 remains castable")
    check(len(tw_l2_actions) > 0 and tw_l2_actions[0].can_afford, "Thunderwave L2 remains castable")



def test_arena_specialized_skeletons():
    print("\n=== Test: Specialized Skeletons Together ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 15)

    warrior = create_skeleton_warrior(name="Skeleton Warrior", position=(12, 5), faction="monsters", darkvision=True)
    archer = create_skeleton_archer(name="Skeleton Archer", position=(12, 7), faction="monsters", darkvision=True)
    warlock = create_skeleton_warlock(name="Skeleton Warlock", position=(12, 9), faction="monsters", darkvision=True)
    hero = create_skeleton(name="Hero", position=(3, 7), faction="heroes")
    Entity.update_all_entities_senses()

    check(warrior.faction == "monsters", "Warrior faction == monsters")
    check(archer.faction == "monsters", "Archer faction == monsters")
    check(warlock.faction == "monsters", "Warlock faction == monsters")
    check(hero.faction == "heroes", "Hero faction == heroes")

    check(warrior.position == (12, 5), f"Warrior at (12,5) (got {warrior.position})")
    check(archer.position == (12, 7), f"Archer at (12,7) (got {archer.position})")
    check(warlock.position == (12, 9), f"Warlock at (12,9) (got {warlock.position})")

    check(get_max_hp(warrior) > get_max_hp(archer), f"Warrior HP > Archer HP ({get_max_hp(warrior)} > {get_max_hp(archer)})")
    check(get_max_hp(archer) > get_max_hp(warlock), f"Archer HP > Warlock HP ({get_max_hp(archer)} > {get_max_hp(warlock)})")

    check(hero.uuid in warrior.senses.entities, "Warrior can see hero")
    check(hero.uuid in archer.senses.entities, "Archer can see hero")
    check(hero.uuid in warlock.senses.entities, "Warlock can see hero")



if __name__ == "__main__":
    print("=" * 60)
    print("SKELETON UNITS TEST SUITE")
    print("=" * 60)

    test_skeleton_warrior_creation()
    test_skeleton_archer_creation()
    test_skeleton_warlock_creation()

    test_eldritch_blast_hit()
    test_eldritch_blast_miss()
    test_eldritch_blast_range()

    test_acid_flask_single_target()
    test_acid_flask_aoe_multiple_targets()
    test_acid_flask_consumable()

    test_mark_applies_condition()
    test_mark_grants_advantage()
    test_mark_strips_existing_invisibility()
    test_mark_strips_existing_hidden()
    test_mark_prevents_future_invisibility()
    test_mark_prevents_future_hidden()
    test_mark_concentration_break()
    test_mark_concentration_break_from_damage()
    test_mark_concentration_break_on_death()
    test_mark_bonus_action_cost()
    test_mark_one_use_per_rest()
    test_mark_range()

    test_arcane_staff_spell_attack_bonus()
    test_arcane_staff_melee()

    test_scroll_of_invisibility_use()
    test_scroll_no_spell_slot()

    test_warlock_burning_hands()
    test_warlock_slot_exhaustion()

    test_arena_specialized_skeletons()

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    if failed > 0:
        exit(1)
