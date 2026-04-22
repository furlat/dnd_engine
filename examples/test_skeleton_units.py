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
    NumericalModifier, AdvantageStatus,
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


# =============================================================================
# Helpers
# =============================================================================

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
    """Add -100 to spell attack bonus, return modifier UUID for cleanup."""
    mod = NumericalModifier.create(
        source_entity_uuid=entity.uuid,
        name="Forced Spell Miss",
        value=-100
    )
    return entity.spellcasting.spell_attack_bonus.self_static.add_value_modifier(mod)


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


# =============================================================================
# Test Group 1: Factory Creation & Stats
# =============================================================================

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

    # Check weapon in MELEE_MAIN
    main_weapon = warrior.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
    check(main_weapon is not None and main_weapon.name == "Longsword", "Has Longsword in MELEE_MAIN")

    # Check shield in MELEE_OFF
    off_item = warrior.equipment.get_item_by_slot(WeaponSlot.MELEE_OFF)
    check(off_item is not None and off_item.name == "Wooden Shield", "Has Wooden Shield in MELEE_OFF")

    # Check acid flask in inventory
    flask_names = [item.name for item in warrior.inventory.items.values()]
    check("Acid Flask" in flask_names, "Has Acid Flask in inventory")

    # Check available actions include melee attack
    names = action_names(warrior)
    check("Attack_MELEE_MAIN" in names, f"Available actions include melee attack (got: {names})")

    return warrior_hp  # For HP ordering check


def test_skeleton_archer_creation():
    print("\n=== Test: Skeleton Archer Creation ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    archer = create_skeleton_archer(name="Test Archer", position=(0, 0), faction="monsters")
    # Need a target for available actions
    create_skeleton(name="Target", position=(5, 0), faction="heroes")
    Entity.update_all_entities_senses()

    archer_hp = get_max_hp(archer)
    check(archer_hp > 15, f"HP > 15 (got {archer_hp})")
    check(archer.ac_bonus().normalized_score == 13, f"AC == 13 (got {archer.ac_bonus().normalized_score})")
    check(archer.ability_scores.dexterity.modifier == 3, f"DEX modifier == +3 (got {archer.ability_scores.dexterity.modifier})")

    # Check weapons
    ranged = archer.equipment._get_weapon_by_slot(WeaponSlot.RANGED_MAIN)
    check(ranged is not None and ranged.name == "Shortbow", "Has Shortbow in RANGED_MAIN")

    main_melee = archer.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
    check(main_melee is not None and main_melee.name == "Dagger", "Has Dagger in MELEE_MAIN")

    off_melee = archer.equipment._get_weapon_by_slot(WeaponSlot.MELEE_OFF)
    check(off_melee is not None and off_melee.name == "Dagger", "Has Dagger in MELEE_OFF")

    # Check Mark Target in available actions
    names = action_names(archer)
    check("Mark Target" in names, f"Available actions include Mark Target (got: {names})")
    check("Attack_RANGED_MAIN" in names, f"Available actions include ranged attack (got: {names})")

    return archer_hp  # For HP ordering check


def test_skeleton_warlock_creation():
    print("\n=== Test: Skeleton Warlock Creation ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 15)

    warlock = create_skeleton_warlock(name="Test Warlock", position=(0, 0), faction="monsters")
    # Target at (2,0) = 10ft, within Burning Hands cone (15ft) and Thunderwave cube (15ft)
    create_skeleton(name="Target", position=(2, 0), faction="heroes")
    Entity.update_all_entities_senses()

    warlock_hp = get_max_hp(warlock)
    check(warlock_hp > 0, f"HP > 0 (got {warlock_hp})")
    check(warlock.ac_bonus().normalized_score == 13, f"AC == 13 (got {warlock.ac_bonus().normalized_score})")
    check(warlock.ability_scores.charisma.modifier == 2, f"CHA modifier == +2 (got {warlock.ability_scores.charisma.modifier})")

    # Check arcane staff
    main_weapon = warlock.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
    check(main_weapon is not None and main_weapon.name == "Arcane Staff", "Has Arcane Staff in MELEE_MAIN")
    check(warlock.equipment.helmet is not None and warlock.equipment.helmet.name == "Crown", "Has Crown in helmet slot")

    # Check spellcaster
    check(warlock.is_spellcaster, "Is spellcaster")
    l1_slots = warlock.action_economy._get_spell_slot_value(1).normalized_score
    check(l1_slots == 2, f"Has 2x L1 spell slots (got {l1_slots})")

    # Check scroll in inventory
    scroll_names = [item.name for item in warlock.inventory.items.values()]
    check("Scroll of Invisibility" in scroll_names, "Has Scroll of Invisibility in inventory")

    # Check available actions include spells
    names = action_names(warlock)
    check("Eldritch Blast" in names, f"Available actions include Eldritch Blast (got: {names})")
    check("Burning Hands" in names, f"Available actions include Burning Hands (got: {names})")
    check("Thunderwave" in names, f"Available actions include Thunderwave (got: {names})")

    return warlock_hp  # For HP ordering check


# =============================================================================
# Test Group 2: Eldritch Blast
# =============================================================================

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

    # Execute Eldritch Blast
    blast = EldritchBlast(
        source_entity_uuid=warlock.uuid,
        target_entity_uuid=target.uuid,
        caster_level=1
    )
    result = blast.apply()

    remove_spell_modifier(warlock, mod_uuid)

    check(result is not None and not result.canceled, "Eldritch Blast executed successfully")
    check(get_hp(target) < initial_hp, f"Target took damage (HP {initial_hp} -> {get_hp(target)})")

    # Check no spell slot consumed (cantrip)
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
    # 25 cells = 125ft, out of 120ft range
    target = create_skeleton(name="Target", position=(25, 0), faction="heroes")
    Entity.update_all_entities_senses()

    blast = EldritchBlast(
        source_entity_uuid=warlock.uuid,
        target_entity_uuid=target.uuid,
        caster_level=1
    )
    result = blast.apply()

    check(result is not None and result.canceled, "Eldritch Blast canceled — out of range")


# =============================================================================
# Test Group 3: Acid Flask
# =============================================================================

def test_acid_flask_single_target():
    print("\n=== Test: Acid Flask Single Target ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    warrior = create_skeleton_warrior(name="Warrior", position=(0, 0), faction="monsters")
    target = create_skeleton(name="Target", position=(5, 5), faction="heroes")
    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)

    # Direct spell cast (simulates using the item)
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

    # Check flask is in inventory
    inventory_before = [item.name for item in warrior.inventory.items.values()]
    check("Acid Flask" in inventory_before, "Acid Flask in inventory before use")

    from dnd.blocks.base_item import UsableItem
    flask = next((item for item in warrior.inventory.items.values() if item.name == "Acid Flask"), None)
    check(flask is not None, "Found Acid Flask")
    if flask and isinstance(flask, UsableItem):
        check(flask.charges == 1, f"Flask has 1 charge (got {flask.charges})")
        check(flask.is_consumable, "Flask is consumable")


# =============================================================================
# Test Group 4: Mark Target
# =============================================================================

def test_mark_applies_condition():
    print("\n=== Test: Mark Target Applies Condition ===")
    archer, target = setup_pair(create_skeleton_archer)

    encounter = setup_combat_arena(archer, target)
    encounter.start_encounter()
    encounter.start_turn()

    # Execute Mark Target
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

    # Check to_target_static on target's AC has advantage modifier
    ac = target.equipment.ac_bonus
    advantage_mods = list(ac.to_target_static.advantage_modifiers.values())
    has_adv = any(m.value == AdvantageStatus.ADVANTAGE and m.name == "Marked" for m in advantage_mods)
    check(has_adv, "Target AC has 'Marked' ADVANTAGE modifier in to_target_static")


def test_mark_strips_existing_invisibility():
    print("\n=== Test: Mark Strips Existing Invisibility ===")
    archer, target = setup_pair(create_skeleton_archer)

    # Give archer truesight so it can see invisible targets
    archer.senses.sense_modes.append(SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60))
    Entity.update_all_entities_senses()

    # Apply Invisible condition first
    invis = Invisible(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(invis)
    Entity.update_all_entities_senses()
    check(target.is_invisible, "Target is invisible before mark")

    # Mark target — archer has truesight, so LOS check passes
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

    # Apply Hidden with low stealth so archer can still perceive target
    # Archer passive perception = 10 + WIS(-1) = 9, so use stealth_result=8
    hidden = Hidden(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        stealth_result=8,
    )
    target.add_condition(hidden)
    Entity.update_all_entities_senses()
    check(target.stealth_dc is not None, "Target has stealth_dc before mark")

    # Mark target — archer can perceive hidden target (passive perception 9 > stealth 8)
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

    # Mark first
    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark.apply()
    check("Marked" in target.active_conditions, "Target is marked")

    # Try to apply InvisibilityEffect — should be blocked by condition immunity
    invis = InvisibilityEffect(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(invis)

    # Condition immunity blocks the application
    check("Invisible" not in target.active_conditions, "Invisible prevented by Mark (immunity)")
    check(not target.is_invisible, "is_invisible still False")


def test_mark_prevents_future_hidden():
    print("\n=== Test: Mark Prevents Future Hidden ===")
    archer, target = setup_pair(create_skeleton_archer)

    # Mark first
    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark.apply()

    # Try to apply Hidden — should be blocked by condition immunity
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

    # Break concentration by removing Concentrating
    archer.remove_condition("Concentrating")

    check("Marked" not in target.active_conditions, "Marked removed from target after concentration break")
    check("Concentrating" not in archer.active_conditions, "Concentrating removed from archer")

    # Verify advantage modifier cleaned up
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

    # Apply Mark
    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark.apply()

    check("Marked" in target.active_conditions, "Target has Marked before damage")
    check("Concentrating" in archer.active_conditions, "Archer concentrating before damage")

    # Give archer tons of HP so they survive
    set_hp(archer, 500)

    # Record log position before damage
    log_before = len(encounter.combat_log)

    # Deal 100 damage → DC = max(10, 100//2) = 50
    # Archer CON save = +2 modifier, impossible to pass DC 50
    deal_damage_to(archer, 100, DamageType.SLASHING, target.uuid)

    check("Concentrating" not in archer.active_conditions,
          "Concentrating removed after failed CON save from damage")
    check("Marked" not in target.active_conditions,
          "Marked removed from target (linked condition cleanup)")

    # Verify advantage modifier cleaned up
    ac = target.equipment.ac_bonus
    advantage_mods = list(ac.to_target_static.advantage_modifiers.values())
    has_marked = any(m.name == "Marked" for m in advantage_mods)
    check(not has_marked, "Marked advantage modifier cleaned up from target AC")

    # Verify condition immunities cleaned up (target can hide/go invisible again)
    hidden_immune = target.check_condition_immunity("Hidden")
    invis_immune = target.check_condition_immunity("Invisible")
    check(not hidden_immune, "Hidden immunity removed after mark broken")
    check(not invis_immune, "Invisible immunity removed after mark broken")

    # Verify combat log contains the concentration save as a sub-entry of damage
    new_logs = encounter.combat_log[log_before:]
    check(len(new_logs) > 0, "Combat log has entries after damage")

    # Find the damage log entry and check for concentration save sub-entry
    damage_log = None
    for entry in new_logs:
        if entry.entry_type == CombatLogEntryType.DAMAGE_TAKEN:
            damage_log = entry
            break
    check(damage_log is not None, "Found DAMAGE_TAKEN log entry")

    if damage_log:
        # Look for saving throw sub-entry (concentration CON save)
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

    # Apply Mark
    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark.apply()

    check("Marked" in target.active_conditions, "Target has Marked before death")
    check("Concentrating" in archer.active_conditions, "Archer concentrating before death")

    # Record log position before kill
    log_before = len(encounter.combat_log)

    # Kill the archer via damage (triggers DeathEvent)
    deal_damage_to(archer, 9999, DamageType.SLASHING, target.uuid)

    check(not archer.has_hp, "Archer is dead")
    check("Concentrating" not in archer.active_conditions,
          "Concentrating removed on death")
    check("Marked" not in target.active_conditions,
          "Marked removed from target (linked condition cleanup on death)")

    # Verify advantage modifier cleaned up
    ac = target.equipment.ac_bonus
    advantage_mods = list(ac.to_target_static.advantage_modifiers.values())
    has_marked = any(m.name == "Marked" for m in advantage_mods)
    check(not has_marked, "Marked advantage modifier cleaned up after archer death")

    # Verify combat log has death entry with concentration removal as sub-entry
    new_logs = encounter.combat_log[log_before:]
    check(len(new_logs) > 0, "Combat log has entries after death")

    # Find condition removal sub-entries across all logs
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

    # Check bonus action available
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

    # First mark
    mark1 = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    mark1.apply()
    check("Mark Cooldown" in archer.active_conditions, "Has Mark Cooldown after first use")

    # Break concentration
    archer.remove_condition("Concentrating")

    # Try second mark — pre_validate should return False
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
    # 13 cells = 65ft, beyond 60ft range
    target = create_skeleton(name="Target", position=(13, 0), faction="heroes")
    Entity.update_all_entities_senses()

    mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    )
    result = mark.apply()

    check(result is not None and result.canceled, "Mark Target canceled — out of range")


# =============================================================================
# Test Group 5: Arcane Staff
# =============================================================================

def test_arcane_staff_spell_attack_bonus():
    print("\n=== Test: Arcane Staff Spell Attack Bonus ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    warlock = create_skeleton_warlock(name="Warlock", position=(0, 0), faction="monsters")
    Entity.update_all_entities_senses()

    # Check spell attack bonus includes +1 from staff
    bonus_with = warlock.spellcasting.spell_attack_bonus.normalized_score
    check(bonus_with >= 1, f"Spell attack bonus >= 1 with staff (got {bonus_with})")

    # Unequip staff
    staff = warlock.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
    check(staff is not None and staff.name == "Arcane Staff", "Has Arcane Staff equipped")
    if staff:
        warlock.equipment.unequip(WeaponSlot.MELEE_MAIN)
        bonus_without = warlock.spellcasting.spell_attack_bonus.normalized_score
        check(bonus_without == bonus_with - 1, f"Spell attack drops by 1 after unequip (with={bonus_with}, without={bonus_without})")

        # Re-equip
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

    # Force melee hit
    mod_uuid = force_attack_hit(warlock)

    # Execute melee attack with Arcane Staff
    avail = get_available_actions(warlock)
    staff_actions = [a for a in avail.entity_actions if a.template_name == "Attack_MELEE_MAIN"]
    check(len(staff_actions) > 0, "Arcane Staff melee attack available")

    if staff_actions:
        execute_by_index(warlock, "Attack_MELEE_MAIN", 0)

    remove_attack_modifier(warlock, mod_uuid)
    check(get_hp(target) < initial_hp, f"Target took melee damage (HP {initial_hp} -> {get_hp(target)})")


# =============================================================================
# Test Group 6: Scroll of Invisibility
# =============================================================================

def test_scroll_of_invisibility_use():
    print("\n=== Test: Scroll of Invisibility Use ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    warlock = create_skeleton_warlock(name="Warlock", position=(0, 0), faction="monsters")
    Entity.update_all_entities_senses()

    # Check scroll in inventory
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


# =============================================================================
# Test Group 7: Warlock Spellcasting Integration
# =============================================================================

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

    # Cast 2x L1 spells to exhaust slots
    from dnd.spells.evocation import BurningHands
    for _ in range(2):
        set_hp(_target, get_max_hp(_target))  # Full heal so target survives
        warlock.action_economy.reset_all_costs()  # Reset action economy so we can cast again
        spell = BurningHands(
            source_entity_uuid=warlock.uuid,
            caster_level=1,
            end_position=(6, 5),
            cast_at_level=1,
        )
        spell.apply()

    slots_remaining = warlock.action_economy._get_spell_slot_value(1).normalized_score
    check(slots_remaining == 0, f"All L1 slots consumed (got {slots_remaining})")

    # Heal target, reset actions (spent by 2nd cast), and update senses
    set_hp(_target, get_max_hp(_target))
    warlock.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()

    # Eldritch Blast should still be available (cantrip, no slot needed)
    avail = get_available_actions(warlock)
    all_actions = avail.entity_actions + avail.self_actions + avail.position_actions + avail.object_actions
    eb_actions = [a for a in all_actions if a.template_name == "Eldritch Blast"]
    check(len(eb_actions) > 0, "Eldritch Blast still available (cantrip)")

    # L1 spells should not be castable (no slots, can_afford=False)
    bh_actions = [a for a in all_actions if a.template_name == "Burning Hands"]
    tw_actions = [a for a in all_actions if a.template_name == "Thunderwave"]
    check(len(bh_actions) == 0 or not bh_actions[0].can_afford, "Burning Hands NOT castable (no slots)")
    check(len(tw_actions) == 0 or not tw_actions[0].can_afford, "Thunderwave NOT castable (no slots)")


# =============================================================================
# Test Group 8: Full Arena Integration
# =============================================================================

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

    # Verify all created with correct factions
    check(warrior.faction == "monsters", "Warrior faction == monsters")
    check(archer.faction == "monsters", "Archer faction == monsters")
    check(warlock.faction == "monsters", "Warlock faction == monsters")
    check(hero.faction == "heroes", "Hero faction == heroes")

    # Verify positions
    check(warrior.position == (12, 5), f"Warrior at (12,5) (got {warrior.position})")
    check(archer.position == (12, 7), f"Archer at (12,7) (got {archer.position})")
    check(warlock.position == (12, 9), f"Warlock at (12,9) (got {warlock.position})")

    # Verify HP ordering: warrior > archer > warlock
    check(get_max_hp(warrior) > get_max_hp(archer), f"Warrior HP > Archer HP ({get_max_hp(warrior)} > {get_max_hp(archer)})")
    check(get_max_hp(archer) > get_max_hp(warlock), f"Archer HP > Warlock HP ({get_max_hp(archer)} > {get_max_hp(warlock)})")

    # Verify they can see the hero
    check(hero.uuid in warrior.senses.entities, "Warrior can see hero")
    check(hero.uuid in archer.senses.entities, "Archer can see hero")
    check(hero.uuid in warlock.senses.entities, "Warlock can see hero")


# =============================================================================
# Run all tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SKELETON UNITS TEST SUITE")
    print("=" * 60)

    # Group 1: Factory Creation
    test_skeleton_warrior_creation()
    test_skeleton_archer_creation()
    test_skeleton_warlock_creation()

    # Group 2: Eldritch Blast
    test_eldritch_blast_hit()
    test_eldritch_blast_miss()
    test_eldritch_blast_range()

    # Group 3: Acid Flask
    test_acid_flask_single_target()
    test_acid_flask_aoe_multiple_targets()
    test_acid_flask_consumable()

    # Group 4: Mark Target
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

    # Group 5: Arcane Staff
    test_arcane_staff_spell_attack_bonus()
    test_arcane_staff_melee()

    # Group 6: Scroll of Invisibility
    test_scroll_of_invisibility_use()
    test_scroll_no_spell_slot()

    # Group 7: Warlock Spellcasting
    test_warlock_burning_hands()
    test_warlock_slot_exhaustion()

    # Group 8: Full Integration
    test_arena_specialized_skeletons()

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    if failed > 0:
        exit(1)
