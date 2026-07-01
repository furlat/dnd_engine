"""Test Cleric Batch 4: 9 New Spells

Tests for: Resistance, Inflict Wounds, Shield of Faith, Aid, Sanctuary,
           Beacon of Hope, Harm, Divine Word, Heroes' Feast.
Also tests HEAL_ROLL_RESULT infrastructure.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from uuid import uuid4
from dnd.utils import (
    reset_combat_state, get_hp, get_max_hp, set_hp,
    has_condition, force_attack_hit, remove_attack_modifier,
)
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.encounter import Encounter
from dnd.controller import HumanController
from dnd.monsters.bestiary import create_goblin, create_caster
from dnd.actions_functional import setup_standard_actions, register_spell
from dnd.spells import (
    Resistance, ShieldOfFaith, Aid, Sanctuary, BeaconOfHope,
    InflictWounds, Harm, DivineWord, HeroesFeast,
    CureWounds,
)
from dnd.conditions import Poisoned, Frightened
from dnd.core.modifiers import AdvantageStatus, AutoHitModifier, AutoHitStatus, NumericalModifier


passed = 0
failed = 0

def check(label, condition):
    global passed, failed
    if condition:
        print(f"  PASS: {label}")
        passed += 1
    else:
        print(f"  FAIL: {label}")
        failed += 1


def setup_cleric(name="Cleric", position=(5, 5), level=10, hp=80, faction="party"):
    """Create a cleric-like sorcerer entity for testing."""
    cleric = create_caster(name=name, position=position, level=level)
    cleric.faction = faction
    set_hp(cleric, hp)
    return cleric


def setup_encounter(*entities):
    """Setup encounter with all entities."""
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    for e in entities:
        encounter.add_combatant(e, HumanController(source_entity_uuid=e.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    return encounter


# ============================================================
# Test 1: Resistance
# ============================================================
def test_resistance():
    print("\n--- Resistance ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Ally", position=(6, 5))
    target.faction = "party"
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    # Register and cast Resistance
    register_spell(cleric, Resistance, caster_level=10)
    resistance = Resistance(source_entity_uuid=cleric.uuid, target_entity_uuid=target.uuid)
    result = resistance.apply()
    check("Resistance cast successfully", result is not None and not result.canceled)
    check("Target has Resistance condition", has_condition(target, "Resistance"))
    check("Cleric is concentrating", has_condition(cleric, "Concentrating"))

    # The Resistance handler should fire on a saving throw and add 1d4
    # Then self-remove after one use
    # Force a saving throw on the target
    enemy = create_goblin(name="Enemy", position=(7, 5))
    Entity.update_all_entities_senses()

    save_request = enemy.create_saving_throw_request(
        target_entity_uuid=target.uuid,
        ability_name="wisdom",
        dc=5,  # Low DC to not auto-fail
        parent_event=None,
    )
    target.saving_throw(save_request)

    # After one save, Resistance should be consumed
    check("Resistance removed after one use", not has_condition(target, "Resistance"))


# ============================================================
# Test 2: Inflict Wounds
# ============================================================
def test_inflict_wounds():
    print("\n--- Inflict Wounds ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Target", position=(6, 5))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    hp_before = get_hp(target)

    # Force hit via AUTOHIT on equipment.attack_bonus (spell attacks use this, not melee_attack_bonus)
    hit_mod = AutoHitModifier(
        name="Forced Spell Hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=cleric.uuid,
    )
    hit_mod_uuid = cleric.equipment.attack_bonus.self_static.add_auto_hit_modifier(hit_mod)

    register_spell(cleric, InflictWounds, caster_level=10)
    iw = InflictWounds(source_entity_uuid=cleric.uuid, target_entity_uuid=target.uuid)
    result = iw.apply()
    cleric.equipment.attack_bonus.self_static.remove_modifier(hit_mod_uuid)

    check("Inflict Wounds cast successfully", result is not None and not result.canceled)
    check("Target took damage", get_hp(target) < hp_before)

    # Test upcasting: at level 3, should be 5d10 (2 + cast_at_level)
    print("\n--- Inflict Wounds Upcast (L3) ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Target", position=(6, 5))
    Entity.update_all_entities_senses()
    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    set_hp(target, 200)  # Give lots of HP to survive
    hit_mod = AutoHitModifier(
        name="Forced Spell Hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=cleric.uuid,
    )
    hit_mod_uuid = cleric.equipment.attack_bonus.self_static.add_auto_hit_modifier(hit_mod)
    iw3 = InflictWounds(source_entity_uuid=cleric.uuid, target_entity_uuid=target.uuid, cast_at_level=3)
    result = iw3.apply()
    cleric.equipment.attack_bonus.self_static.remove_modifier(hit_mod_uuid)

    damage_dealt = 200 - get_hp(target)
    check("Upcast L3 deals damage", damage_dealt > 0)
    # 5d10 = min 5, max 50. Should generally be more than base 3d10
    check("Upcast damage is reasonable (5d10 range)", 5 <= damage_dealt <= 60)  # +bonus possible

    # Test miss
    print("\n--- Inflict Wounds Miss ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Target", position=(6, 5))
    Entity.update_all_entities_senses()
    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    hp_before = get_hp(target)
    miss_mod = NumericalModifier.create(
        source_entity_uuid=cleric.uuid,
        name="Forced Spell Miss",
        value=-100,
    )
    miss_mod_uuid = cleric.equipment.attack_bonus.self_static.add_value_modifier(miss_mod)
    iw_miss = InflictWounds(source_entity_uuid=cleric.uuid, target_entity_uuid=target.uuid)
    result = iw_miss.apply()
    cleric.equipment.attack_bonus.self_static.remove_modifier(miss_mod_uuid)

    check("Miss deals no damage", get_hp(target) == hp_before)


# ============================================================
# Test 3: Shield of Faith
# ============================================================
def test_shield_of_faith():
    print("\n--- Shield of Faith ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Ally", position=(6, 5))
    target.faction = "party"
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    ac_before = target.equipment.ac_bonus.normalized_score

    register_spell(cleric, ShieldOfFaith, caster_level=10)
    sof = ShieldOfFaith(source_entity_uuid=cleric.uuid, target_entity_uuid=target.uuid)
    result = sof.apply()

    check("Shield of Faith cast successfully", result is not None and not result.canceled)
    check("Target has Shield of Faith", has_condition(target, "Shield of Faith"))
    check("Cleric is concentrating", has_condition(cleric, "Concentrating"))

    ac_after = target.equipment.ac_bonus.normalized_score
    check(f"AC increased by 2 ({ac_before} -> {ac_after})", ac_after == ac_before + 2)

    # Breaking concentration should remove Shield of Faith
    cleric.remove_condition("Concentrating")
    check("Shield of Faith removed on concentration break", not has_condition(target, "Shield of Faith"))

    ac_final = target.equipment.ac_bonus.normalized_score
    check(f"AC restored ({ac_final})", ac_final == ac_before)


# ============================================================
# Test 4: Aid
# ============================================================
def test_aid():
    print("\n--- Aid ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    ally1 = create_goblin(name="Ally1", position=(6, 5))
    ally1.faction = "party"
    ally2 = create_goblin(name="Ally2", position=(7, 5))
    ally2.faction = "party"
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, ally1, ally2)
    encounter.start_turn()

    max_hp_before = get_max_hp(ally1)

    # Cast Aid at level 2 → +5 max HP
    register_spell(cleric, Aid, caster_level=10)
    aid = Aid(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally1.uuid,
        extra_target_entity_uuids=[ally1.uuid, ally2.uuid],
        cast_at_level=2,
    )
    result = aid.apply()

    check("Aid cast successfully", result is not None and not result.canceled)
    check("Ally1 has Aid", has_condition(ally1, "Aid"))
    check("Ally2 has Aid", has_condition(ally2, "Aid"))

    max_hp_after = get_max_hp(ally1)
    check(f"Max HP increased by 5 ({max_hp_before} -> {max_hp_after})", max_hp_after == max_hp_before + 5)

    # Test upcast at L4 → +15 max HP
    print("\n--- Aid Upcast (L4) ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    ally = create_goblin(name="Ally", position=(6, 5))
    ally.faction = "party"
    Entity.update_all_entities_senses()
    encounter = setup_encounter(cleric, ally)
    encounter.start_turn()

    max_hp_before = get_max_hp(ally)
    aid4 = Aid(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        extra_target_entity_uuids=[ally.uuid],
        cast_at_level=4,
    )
    result = aid4.apply()

    max_hp_after = get_max_hp(ally)
    check(f"L4 Aid: Max HP increased by 15 ({max_hp_before} -> {max_hp_after})", max_hp_after == max_hp_before + 15)

    # Aid is NOT concentration
    check("Cleric NOT concentrating (Aid is not concentration)", not has_condition(cleric, "Concentrating"))


# ============================================================
# Test 5: Sanctuary
# ============================================================
def test_sanctuary():
    print("\n--- Sanctuary ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    ally = create_goblin(name="ProtectedAlly", position=(6, 5))
    ally.faction = "party"
    enemy = create_goblin(name="Attacker", position=(7, 5))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, ally, enemy)
    encounter.start_turn()

    register_spell(cleric, Sanctuary, caster_level=10)
    sanct = Sanctuary(source_entity_uuid=cleric.uuid, target_entity_uuid=ally.uuid)
    result = sanct.apply()

    check("Sanctuary cast successfully", result is not None and not result.canceled)
    check("Ally has Sanctuary", has_condition(ally, "Sanctuary"))

    # Sanctuary is NOT concentration
    check("Not concentration", not has_condition(cleric, "Concentrating"))

    # Test: enemy attacks ally — should force WIS save
    # With high DC, enemy likely fails and attack is blocked
    # We can't guarantee the save result, so just check that the condition exists
    # and that attacking triggers the handler

    # Test self-break: when ally attacks an enemy, Sanctuary should break
    print("\n--- Sanctuary Self-Break ---")
    # Switch to ally's turn
    encounter.end_turn()
    encounter.next_turn()
    current = encounter.get_current_entity()
    if current and current.uuid != ally.uuid:
        encounter.end_turn()
        encounter.next_turn()

    # Ally tries to attack enemy
    from dnd.actions import Attack
    from dnd.core.events import WeaponSlot
    setup_standard_actions(ally)

    # Force hit so the attack goes through
    mod_id = force_attack_hit(ally)
    attack = Attack(
        source_entity_uuid=ally.uuid,
        target_entity_uuid=enemy.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    attack.apply()
    remove_attack_modifier(ally, mod_id)

    check("Sanctuary removed after ally attacks enemy", not has_condition(ally, "Sanctuary"))


# ============================================================
# Test 6: Beacon of Hope
# ============================================================
def test_beacon_of_hope():
    print("\n--- Beacon of Hope ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    ally = create_goblin(name="Ally", position=(6, 5))
    ally.faction = "party"
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, ally)
    encounter.start_turn()

    register_spell(cleric, BeaconOfHope, caster_level=10)
    boh = BeaconOfHope(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        extra_target_entity_uuids=[ally.uuid],
    )
    result = boh.apply()

    check("Beacon of Hope cast", result is not None and not result.canceled)
    check("Ally has Beacon of Hope", has_condition(ally, "Beacon of Hope"))
    check("Cleric concentrating", has_condition(cleric, "Concentrating"))

    # Check WIS save advantage
    wis_save = ally.saving_throws.get_saving_throw("wisdom")
    check("WIS save has advantage", wis_save.bonus.advantage == AdvantageStatus.ADVANTAGE)

    # Test healing maximization via HEAL_ROLL_RESULT
    # Need a new turn so cleric has actions to cast CureWounds
    encounter.end_turn()
    encounter.next_turn()
    current = encounter.get_current_entity()
    if current and current.uuid != cleric.uuid:
        encounter.end_turn()
        encounter.next_turn()

    # Damage ally, then heal with Cure Wounds
    set_hp(ally, 1)  # Nearly dead

    register_spell(cleric, CureWounds, caster_level=10)
    # Cast at level 1: 1d8 + mod. With Beacon of Hope, should maximize dice to 8
    cure = CureWounds(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=1,
    )
    cure.apply()

    hp_after = get_hp(ally)
    healing_received = hp_after - 1  # Started at 1 HP
    # With Beacon of Hope, the d8 should be maximized to 8 + spellcasting mod
    # The mod varies but with 1d8 maximized, minimum healing should be 8
    check(f"Healing maximized (healed {healing_received}, expected >= 8)", healing_received >= 8)

    # Concentration break removes Beacon of Hope
    cleric.remove_condition("Concentrating")
    check("Beacon removed on concentration break", not has_condition(ally, "Beacon of Hope"))


# ============================================================
# Test 7: Harm
# ============================================================
def test_harm():
    print("\n--- Harm ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Target", position=(6, 5))
    set_hp(target, 100)
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    hp_before = get_hp(target)
    register_spell(cleric, Harm, caster_level=10)
    harm = Harm(source_entity_uuid=cleric.uuid, target_entity_uuid=target.uuid)
    result = harm.apply()

    check("Harm cast successfully", result is not None and not result.canceled)
    hp_after = get_hp(target)
    damage_dealt = hp_before - hp_after
    check(f"Harm dealt damage ({damage_dealt})", damage_dealt > 0)

    # Test min 1 HP cap
    print("\n--- Harm Min 1 HP Cap ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Target", position=(6, 5))
    set_hp(target, 5)  # Very low HP
    Entity.update_all_entities_senses()
    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    harm2 = Harm(source_entity_uuid=cleric.uuid, target_entity_uuid=target.uuid)
    harm2.apply()

    check(f"Target still alive (HP={get_hp(target)})", get_hp(target) >= 1)


# ============================================================
# Test 8: Divine Word
# ============================================================
def test_divine_word():
    print("\n--- Divine Word HP Thresholds ---")

    # Test 1: >50 HP - no effect
    print("\n  --- Tier: >50 HP (no effect) ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Strong", position=(6, 5))
    set_hp(target, 60)
    Entity.update_all_entities_senses()
    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    register_spell(cleric, DivineWord, caster_level=15)
    dw = DivineWord(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        extra_target_entity_uuids=[target.uuid],
    )
    dw.apply()
    check("No conditions at >50 HP", not has_condition(target, "Blinded") and not has_condition(target, "Deafened"))

    # Test 2: 41-50 HP - Deafened
    print("\n  --- Tier: 41-50 HP (Deafened) ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Medium", position=(6, 5))
    set_hp(target, 45)
    Entity.update_all_entities_senses()
    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    dw2 = DivineWord(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        extra_target_entity_uuids=[target.uuid],
    )
    dw2.apply()
    check("Deafened at 45 HP", has_condition(target, "Deafened"))
    check("Not Blinded at 45 HP", not has_condition(target, "Blinded"))

    # Test 3: 31-40 HP - Blinded + Deafened
    print("\n  --- Tier: 31-40 HP (Blinded + Deafened) ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Weak", position=(6, 5))
    set_hp(target, 35)
    Entity.update_all_entities_senses()
    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    dw3 = DivineWord(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        extra_target_entity_uuids=[target.uuid],
    )
    dw3.apply()
    check("Blinded at 35 HP", has_condition(target, "Blinded"))
    check("Deafened at 35 HP", has_condition(target, "Deafened"))
    check("Not Stunned at 35 HP", not has_condition(target, "Stunned"))

    # Test 4: 21-30 HP - Blinded + Deafened + Stunned
    print("\n  --- Tier: 21-30 HP (Blinded + Deafened + Stunned) ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="VeryWeak", position=(6, 5))
    set_hp(target, 25)
    Entity.update_all_entities_senses()
    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    dw4 = DivineWord(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        extra_target_entity_uuids=[target.uuid],
    )
    dw4.apply()
    check("Blinded at 25 HP", has_condition(target, "Blinded"))
    check("Deafened at 25 HP", has_condition(target, "Deafened"))
    check("Stunned at 25 HP", has_condition(target, "Stunned"))

    # Test 5: ≤20 HP - Killed
    print("\n  --- Tier: ≤20 HP (Killed) ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Dying", position=(6, 5))
    set_hp(target, 15)
    Entity.update_all_entities_senses()
    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    dw5 = DivineWord(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        extra_target_entity_uuids=[target.uuid],
    )
    dw5.apply()
    check(f"Killed at 15 HP (HP={get_hp(target)})", get_hp(target) <= 0 or not target.has_hp)


# ============================================================
# Test 9: Heroes' Feast
# ============================================================
def test_heroes_feast():
    print("\n--- Heroes' Feast ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    ally = create_goblin(name="Ally", position=(6, 5))
    ally.faction = "party"
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, ally)
    encounter.start_turn()

    # Cast Heroes' Feast at position (5, 6) - adjacent to cleric
    register_spell(cleric, HeroesFeast, caster_level=10)
    hf = HeroesFeast(
        source_entity_uuid=cleric.uuid,
        end_position=(5, 6),
    )
    result = hf.apply()

    check("Heroes' Feast cast successfully", result is not None and not result.canceled)

    # Find the feast object on the grid
    grid = get_map()
    objects_at = grid.get_objects_at((5, 6))
    check("Feast object placed on grid", len(objects_at) > 0)

    # Get the feast object
    from dnd.spells.conjuration import HeroesFeastObject
    from dnd.core.base_block import BaseBlock
    feast = None
    for obj_uuid in objects_at:
        obj = BaseBlock.get(obj_uuid)
        if isinstance(obj, HeroesFeastObject):
            feast = obj
            break
    check("Feast object is HeroesFeastObject", feast is not None)
    assert feast is not None

    # Get use actions
    use_actions = feast.get_use_actions(ally.uuid)
    check("Ally can eat from feast", len(use_actions) > 0)

    # Apply Poisoned and Frightened to ally before eating
    poisoned = Poisoned(source_entity_uuid=cleric.uuid, target_entity_uuid=ally.uuid)
    ally.add_condition(poisoned)
    frightened = Frightened(source_entity_uuid=cleric.uuid, target_entity_uuid=ally.uuid)
    ally.add_condition(frightened)
    check("Ally is poisoned before eating", has_condition(ally, "Poisoned"))
    check("Ally is frightened before eating", has_condition(ally, "Frightened"))

    max_hp_before = get_max_hp(ally)

    # Eat from feast
    eat_action = use_actions[0]
    eat_result = eat_action.apply()
    check("Eat action succeeded", eat_result is not None and not eat_result.canceled)

    # Check buff applied
    check("Ally has Heroes' Feast buff", has_condition(ally, "Heroes' Feast"))
    check("Poisoned removed", not has_condition(ally, "Poisoned"))
    check("Frightened removed", not has_condition(ally, "Frightened"))

    # Max HP increased
    max_hp_after = get_max_hp(ally)
    check(f"Max HP increased ({max_hp_before} -> {max_hp_after})", max_hp_after > max_hp_before)

    # WIS save advantage
    wis_save = ally.saving_throws.get_saving_throw("wisdom")
    check("WIS save has advantage from feast", wis_save.bonus.advantage == AdvantageStatus.ADVANTAGE)

    # No stacking: can't eat again
    use_actions2 = feast.get_use_actions(ally.uuid)
    check("Can't eat again (no use actions)", len(use_actions2) == 0)

    # Condition immunity: Poisoned can't be applied
    poisoned2 = Poisoned(source_entity_uuid=cleric.uuid, target_entity_uuid=ally.uuid)
    ally.add_condition(poisoned2)
    check("Poisoned immune (condition doesn't apply)", not has_condition(ally, "Poisoned"))

    # Condition immunity: Frightened can't be applied
    frightened2 = Frightened(source_entity_uuid=cleric.uuid, target_entity_uuid=ally.uuid)
    ally.add_condition(frightened2)
    check("Frightened immune (condition doesn't apply)", not has_condition(ally, "Frightened"))

    # Remove the buff, immunities should go away
    ally.remove_condition("Heroes' Feast")
    check("Heroes' Feast buff removed", not has_condition(ally, "Heroes' Feast"))

    # After removal, Poisoned can be applied again
    poisoned3 = Poisoned(source_entity_uuid=cleric.uuid, target_entity_uuid=ally.uuid)
    ally.add_condition(poisoned3)
    check("Poisoned can be applied after buff removal", has_condition(ally, "Poisoned"))


# ============================================================
# Test 10: HEAL_ROLL_RESULT infrastructure
# ============================================================
def test_heal_roll_result():
    print("\n--- HEAL_ROLL_RESULT Event ---")
    from dnd.core.events import EventType, HealRollResultEvent

    check("HEAL_ROLL_RESULT event type exists", hasattr(EventType, "HEAL_ROLL_RESULT"))
    check("HealRollResultEvent class exists", HealRollResultEvent is not None)

    # Test fire_heal_roll_result
    from dnd.spells.spell_utils import fire_heal_roll_result

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    ally = create_goblin(name="Ally", position=(6, 5))
    ally.faction = "party"
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, ally)
    encounter.start_turn()

    # Fire a heal roll result without any handlers - should return unmodified
    from dnd.core.events import Healing, Event, EventPhase, EventType
    from dnd.core.values import ModifiableValue

    healing = Healing(
        name="Test Healing",
        source_entity_uuid=cleric.uuid,
        healing_dice=8,
        dice_numbers=2,
        healing_bonus=ModifiableValue.create(
            source_entity_uuid=cleric.uuid,
            base_value=3,
            value_name="Test Healing Bonus"
        ),
    )
    parent_event = Event(
        name="Test Parent",
        source_entity_uuid=cleric.uuid,
        event_type=EventType.CAST_SPELL,
        phase=EventPhase.EFFECT,
    )

    roll = fire_heal_roll_result(cleric.uuid, ally.uuid, healing, parent_event, "Test Heal")
    check("fire_heal_roll_result returns DiceRoll", roll is not None)
    check(f"Roll total is reasonable (got {roll.total})", roll.total >= 5)  # 2d8+3, min=5


# ============================================================
# Run all tests
# ============================================================
if __name__ == "__main__":
    test_resistance()
    test_inflict_wounds()
    test_shield_of_faith()
    test_aid()
    test_sanctuary()
    test_beacon_of_hope()
    test_harm()
    test_divine_word()
    test_heroes_feast()
    test_heal_roll_result()

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
    print(f"{'='*60}")

    if failed > 0:
        sys.exit(1)
