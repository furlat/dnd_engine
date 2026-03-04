"""
Test suite for Haste spell (3rd-level Transmutation, Concentration).

Tests:
1. Haste applies all buffs (speed doubled, +2 AC, DEX advantage, +1 action)
2. Extra Attack suppression on last (haste) action — 3 total hits
3. Haste + Action Surge — 5 total hits
4. Lethargy on concentration break (target gets Incapacitated)
5. Lethargy on ally (haste cast on ally, ally gets lethargy)
6. Haste + Slow interaction (net effects)
7. Haste + Slow + Action Surge (3 actions, no EA on any)
"""

from typing import cast as type_cast
from uuid import uuid4, UUID
from dnd.utils import (
    reset_combat_state, set_hp, has_condition, get_hp,
    force_attack_hit, remove_attack_modifier, deal_damage_to
)
from dnd.core.gridmap import get_map
from dnd.core.events import AbilityName
from dnd.core.modifiers import DamageType, NumericalModifier, AdvantageStatus
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.spells import Haste, Slow
from dnd.actions_functional import setup_standard_actions, get_available_actions, execute_action
from dnd.core.base_actions import AvailableTarget
from dnd.core.events import WeaponSlot
from dnd.items.weapons import create_longsword, create_greatsword
from dnd.encounter import Encounter
from dnd.controller import HumanController
from dnd.classes.fighter import ExtraAttackFeature, ActionSurgeFeature, ActionSurge
from dnd.actions import DropConcentration


# =============================================================================
# Helpers
# =============================================================================

def force_save_fail(entity: Entity, ability: str = "wisdom") -> UUID:
    """Add -100 to saving throw to guarantee failure. Returns modifier UUID."""
    save = entity.saving_throws.get_saving_throw(type_cast(AbilityName, ability))
    mod = NumericalModifier(name="Force Fail", value=-100,
                            source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    save.bonus.self_static.add_value_modifier(mod)
    return mod.uuid


def force_save_succeed(entity: Entity, ability: str = "wisdom") -> UUID:
    """Add +100 to saving throw to guarantee success. Returns modifier UUID."""
    save = entity.saving_throws.get_saving_throw(type_cast(AbilityName, ability))
    mod = NumericalModifier(name="Force Succeed", value=100,
                            source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    save.bonus.self_static.add_value_modifier(mod)
    return mod.uuid


def remove_save_modifier(entity: Entity, mod_uuid: UUID, ability: str = "wisdom"):
    """Remove a force save modifier."""
    save = entity.saving_throws.get_saving_throw(type_cast(AbilityName, ability))
    save.bonus.self_static.remove_value_modifier(mod_uuid)


def create_caster(name: str, position: tuple, faction: str = "party") -> Entity:
    """Create a caster with high WIS for spell DC."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=20),
        ),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3, 3: 3},
        ),
        spellcasting=SpellcastingConfig(spellcasting_ability="wisdom"),
        proficiency_bonus=4,
        position=position,
        faction=faction
    )
    caster = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(caster)
    return caster


def create_target(name: str, position: tuple, faction: str = "party") -> Entity:
    """Create a target with a weapon and health."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
            wisdom=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=20, mode="maximums"
        )]),
        proficiency_bonus=4,
        position=position,
        faction=faction
    )
    target = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(target)
    weapon = create_greatsword(target.uuid)
    target.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    return target


def create_fighter(name: str, position: tuple, faction: str = "party",
                   action_surge: bool = False) -> Entity:
    """Create a fighter with Extra Attack (and optionally Action Surge)."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
            wisdom=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=20, mode="maximums"
        )]),
        proficiency_bonus=4,
        position=position,
        faction=faction
    )
    fighter = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(fighter)
    weapon = create_greatsword(fighter.uuid)
    fighter.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)

    # Extra Attack
    ea = ExtraAttackFeature(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        extra_attacks=1
    )
    fighter.add_condition(ea)

    # Action Surge
    if action_surge:
        asf = ActionSurgeFeature(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=fighter.uuid,
            num_uses=1
        )
        fighter.add_condition(asf)

    return fighter


def create_dummy(name: str, position: tuple, faction: str = "enemies") -> Entity:
    """Create a punching bag (different faction, high HP)."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=50, mode="maximums"
        )]),
        proficiency_bonus=2,
        position=position,
        faction=faction
    )
    dummy = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(dummy)
    weapon = create_longsword(dummy.uuid)
    dummy.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    return dummy


def cast_haste(caster: Entity, target: Entity):
    """Cast Haste on a target."""
    haste = Haste(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, template=False)
    return haste.apply()


def cast_slow(caster: Entity, position: tuple):
    """Cast Slow centered on a position."""
    slow = Slow(source_entity_uuid=caster.uuid, end_position=position, template=False)
    return slow.apply()


def setup_encounter(*entities: Entity) -> Encounter:
    """Create and start an encounter."""
    encounter = Encounter(name="Test Haste", source_entity_uuid=uuid4())
    for e in entities:
        encounter.add_combatant(e, HumanController(source_entity_uuid=e.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    return encounter


def _attack_until_done(fighter, dummy):
    """Execute melee attacks until fighter runs out. Returns number of hits.

    Prioritizes Extra Attack over regular Attack (Extra Attack is free,
    regular Attack costs an action and should only be used when no EA available).
    """
    hits = 0
    set_hp(dummy, 500)
    for _ in range(10):
        available = get_available_actions(fighter)
        attack_infos = [a for a in available.entity_actions
                        if "Attack" in a.template_name]
        if not attack_infos:
            break
        actions_left = fighter.action_economy.actions.normalized_score
        ea = fighter.action_economy.resources.get("extra_attacks")
        ea_left = ea.current if ea else 0
        if actions_left <= 0 and ea_left <= 0:
            break
        # Prioritize Extra Attack (free) over regular Attack (costs action)
        ea_actions = [a for a in attack_infos if "Extra" in a.template_name]
        regular_actions = [a for a in attack_infos if "Extra" not in a.template_name]
        chosen = ea_actions[0] if ea_actions else regular_actions[0]
        hp_before = get_hp(dummy)
        execute_action(fighter, chosen.template_name,
                       AvailableTarget(index=0, target_uuid=dummy.uuid))
        if get_hp(dummy) < hp_before:
            hits += 1
    return hits


def _navigate_to_turn(encounter: Encounter, entity: Entity):
    """Navigate encounter to the given entity's turn."""
    encounter.start_turn()
    while (ce := encounter.get_current_entity()) and ce.uuid != entity.uuid:
        encounter.end_turn()
        encounter.next_turn()


# =============================================================================
# Test 1: Haste applies all buffs
# =============================================================================
def test_1_haste_applies_buffs():
    """Verify speed doubled, +2 AC, DEX save advantage, +1 action."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    target = create_target("Fighter", (3, 0))
    Entity.update_all_entities_senses()

    base_speed = target.action_economy.movement.normalized_score
    base_ac = target.equipment.ac_bonus.normalized_score
    base_actions = target.action_economy.actions.normalized_score

    cast_haste(caster, target)

    assert has_condition(target, "Haste"), "Target should have Haste"
    assert has_condition(caster, "Concentrating"), "Caster should be Concentrating"

    # Speed doubled
    hasted_speed = target.action_economy.movement.normalized_score
    assert hasted_speed == base_speed * 2, \
        f"Speed should be doubled: {hasted_speed} != {base_speed * 2}"

    # +2 AC
    hasted_ac = target.equipment.ac_bonus.normalized_score
    assert hasted_ac == base_ac + 2, \
        f"AC should be +2: {hasted_ac} != {base_ac + 2}"

    # DEX save advantage
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    assert dex_save.bonus.advantage == AdvantageStatus.ADVANTAGE, \
        f"DEX save should have advantage, got {dex_save.bonus.advantage}"

    # +1 action
    hasted_actions = target.action_economy.actions.normalized_score
    assert hasted_actions == base_actions + 1, \
        f"Actions should be +1: {hasted_actions} != {base_actions + 1}"

    print("PASSED: test_1_haste_applies_buffs")


# =============================================================================
# Test 2: Extra Attack suppression on haste action
# =============================================================================
def test_2_haste_extra_attack_suppression():
    """Hasted fighter: 1st action gets EA (2 swings), 2nd (haste) does not (1 swing) = 3 total."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    fighter = create_fighter("Fighter", (3, 0))
    dummy = create_dummy("Dummy", (4, 0))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(caster, fighter, dummy)
    cast_haste(caster, fighter)

    # Navigate to fighter's turn
    _navigate_to_turn(encounter, fighter)

    hit_mod = force_attack_hit(fighter)
    hits = _attack_until_done(fighter, dummy)
    remove_attack_modifier(fighter, hit_mod)

    print(f"Hasted fighter hits: {hits}")
    assert hits == 3, f"Hasted fighter should get 3 hits (2+1), got {hits}"

    print("PASSED: test_2_haste_extra_attack_suppression")


# =============================================================================
# Test 3: Haste + Action Surge = 5 hits
# =============================================================================
def test_3_haste_action_surge():
    """Hasted fighter with Action Surge (surge first): 1st EA (2), 2nd EA (2), 3rd no EA (1) = 5.

    NOTE: This test uses Surge FIRST (3 actions upfront), so suppression only fires
    on the 3rd attack. The mid-turn Surge bug (test_10) is not triggered here.
    """
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    fighter = create_fighter("Fighter", (3, 0), action_surge=True)
    dummy = create_dummy("Dummy", (4, 0))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(caster, fighter, dummy)
    cast_haste(caster, fighter)

    _navigate_to_turn(encounter, fighter)

    # Use Action Surge first (free action)
    surge = ActionSurge(source_entity_uuid=fighter.uuid)
    surge.apply()

    # Now fighter should have 3 actions: 1 base + 1 haste + 1 surge
    actions = fighter.action_economy.actions.normalized_score
    print(f"Actions after Haste + Surge: {actions}")
    assert actions == 3, f"Should have 3 actions, got {actions}"

    hit_mod = force_attack_hit(fighter)
    hits = _attack_until_done(fighter, dummy)
    remove_attack_modifier(fighter, hit_mod)

    print(f"Haste + Action Surge hits: {hits}")
    assert hits == 5, f"Should get 5 hits (2+2+1), got {hits}"

    print("PASSED: test_3_haste_action_surge")


# =============================================================================
# Test 4: Lethargy on concentration break
# =============================================================================
def test_4_lethargy_on_concentration_break():
    """Breaking concentration applies Incapacitated to the haste target."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    target = create_target("Fighter", (3, 0))
    Entity.update_all_entities_senses()

    cast_haste(caster, target)
    assert has_condition(target, "Haste"), "Target should have Haste"

    # Break concentration by killing the caster
    set_hp(caster, 1)
    deal_damage_to(caster, 100, DamageType.FORCE, uuid4())

    assert not has_condition(caster, "Concentrating"), "Caster should not be Concentrating"
    assert not has_condition(target, "Haste"), "Target should no longer have Haste"
    assert has_condition(target, "Incapacitated"), \
        "Target should be Incapacitated (lethargy)"

    # Verify lethargy blocks actions and movement
    assert target.action_economy.actions.normalized_score == 0, \
        "Incapacitated should zero actions"
    assert target.action_economy.movement.normalized_score == 0, \
        "Incapacitated should zero movement"

    print("PASSED: test_4_lethargy_on_concentration_break")


# =============================================================================
# Test 5: Lethargy on ally
# =============================================================================
def test_5_lethargy_on_ally():
    """Haste cast on ally — ally gets lethargy, not caster."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    ally = create_target("Ally", (3, 0))
    Entity.update_all_entities_senses()

    cast_haste(caster, ally)
    assert has_condition(ally, "Haste")

    # Break concentration via DropConcentration (non-lethal)
    drop = DropConcentration(source_entity_uuid=caster.uuid)
    drop.apply()

    assert not has_condition(ally, "Haste"), "Ally should lose Haste"
    assert has_condition(ally, "Incapacitated"), "Ally should be Incapacitated"
    assert not has_condition(caster, "Incapacitated"), "Caster should NOT be Incapacitated"

    print("PASSED: test_5_lethargy_on_ally")


# =============================================================================
# Test 6: Haste + Slow interaction
# =============================================================================
def test_6_haste_slow_interaction():
    """Haste + Slow on same target — net effects stack through modifiers."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    haste_caster = create_caster("Haste Wizard", (0, 0), faction="party")
    slow_caster = create_caster("Slow Wizard", (8, 0), faction="enemies")
    fighter = create_fighter("Fighter", (3, 0), faction="party")
    dummy = create_dummy("Dummy", (4, 0))
    Entity.update_all_entities_senses()

    base_speed = fighter.action_economy.movement.normalized_score
    base_ac = fighter.equipment.ac_bonus.normalized_score

    # Apply Haste
    cast_haste(haste_caster, fighter)
    assert has_condition(fighter, "Haste")

    # Apply Slow
    fail_mod = force_save_fail(fighter)
    cast_slow(slow_caster, (3, 0))
    remove_save_modifier(fighter, fail_mod)
    assert has_condition(fighter, "Slowed")

    # Net speed: +base - base/2 = +base/2
    net_speed = fighter.action_economy.movement.normalized_score
    expected_speed = base_speed + base_speed - (base_speed // 2)
    assert net_speed == expected_speed, \
        f"Net speed: {net_speed} != {expected_speed}"

    # Net AC: +2 - 2 = 0
    net_ac = fighter.equipment.ac_bonus.normalized_score
    assert net_ac == base_ac, \
        f"Net AC: {net_ac} != {base_ac}"

    # Actions: base(1) + haste(1) = 2 total
    net_actions = fighter.action_economy.actions.normalized_score
    assert net_actions == 2, f"Should have 2 actions (base + haste), got {net_actions}"

    # Reactions: blocked by Slow (max 0)
    assert fighter.action_economy.reactions.normalized_score == 0, \
        "Reactions should be blocked by Slow"

    # Slow's No EA handler suppresses ALL extra attacks
    encounter = setup_encounter(haste_caster, slow_caster, fighter, dummy)
    _navigate_to_turn(encounter, fighter)

    hit_mod = force_attack_hit(fighter)
    hits = _attack_until_done(fighter, dummy)
    remove_attack_modifier(fighter, hit_mod)

    print(f"Haste + Slow hits: {hits}")
    # Slow suppresses ALL EA → 2 actions = 2 single attacks
    assert hits == 2, f"Haste+Slow should get 2 hits (no EA), got {hits}"

    print("PASSED: test_6_haste_slow_interaction")


# =============================================================================
# Test 7: Haste + Slow + Action Surge
# =============================================================================
def test_7_haste_slow_action_surge():
    """Triple interaction: 3 actions, no EA on any, lockout applies."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    haste_caster = create_caster("Haste Wizard", (0, 0), faction="party")
    slow_caster = create_caster("Slow Wizard", (8, 0), faction="enemies")
    fighter = create_fighter("Fighter", (3, 0), faction="party", action_surge=True)
    dummy = create_dummy("Dummy", (4, 0))
    Entity.update_all_entities_senses()

    # Apply Haste
    cast_haste(haste_caster, fighter)

    # Apply Slow
    fail_mod = force_save_fail(fighter)
    cast_slow(slow_caster, (3, 0))
    remove_save_modifier(fighter, fail_mod)

    assert has_condition(fighter, "Haste")
    assert has_condition(fighter, "Slowed")

    encounter = setup_encounter(haste_caster, slow_caster, fighter, dummy)
    _navigate_to_turn(encounter, fighter)

    # Action Surge
    surge = ActionSurge(source_entity_uuid=fighter.uuid)
    surge.apply()

    actions = fighter.action_economy.actions.normalized_score
    print(f"Actions (Haste+Slow+Surge): {actions}")
    assert actions == 3, f"Should have 3 actions (1+1+1), got {actions}"

    hit_mod = force_attack_hit(fighter)
    hits = _attack_until_done(fighter, dummy)
    remove_attack_modifier(fighter, hit_mod)

    print(f"Haste+Slow+Surge hits: {hits}")
    # Slow suppresses ALL EA → 3 single attacks
    assert hits == 3, f"Should get 3 hits (no EA on any), got {hits}"

    # Note: Slow lockout only fires on BASE_ACTION events (Dodge, Dash, etc.)
    # Attack events use ATTACK event type, so no lockout from attacks alone.

    print("PASSED: test_7_haste_slow_action_surge")


# =============================================================================
# Test 8: Lethargy on direct removal (dispel)
# =============================================================================
def test_8_lethargy_on_dispel():
    """Directly removing HasteEffect triggers lethargy."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    target = create_target("Fighter", (3, 0))
    Entity.update_all_entities_senses()

    cast_haste(caster, target)
    assert has_condition(target, "Haste")

    # Directly remove HasteEffect (simulating dispel magic)
    target.remove_condition("Haste")

    assert not has_condition(target, "Haste"), "Haste should be removed"
    assert has_condition(target, "Incapacitated"), \
        "Lethargy should fire on direct removal too"

    print("PASSED: test_8_lethargy_on_dispel")


# =============================================================================
# Test 9: Lethargy on duration expiry
# =============================================================================
def test_9_lethargy_on_expiry():
    """Haste expires after duration — lethargy still applies."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    target = create_target("Fighter", (3, 0))
    dummy = create_dummy("Dummy", (5, 0))
    Entity.update_all_entities_senses()

    cast_haste(caster, target)
    assert has_condition(target, "Haste"), "Should have Haste after cast"

    encounter = setup_encounter(caster, target, dummy)

    # Navigate to target's first turn
    encounter.start_turn()
    while (ce := encounter.get_current_entity()) and ce.uuid != target.uuid:
        encounter.end_turn()
        encounter.next_turn()

    # Haste should still be active (concentration, permanent duration)
    assert has_condition(target, "Haste"), "Haste should still be active"

    # NOW set it to expire in 1 round (will tick on next turn start)
    haste_cond = target.active_conditions.get("Haste")
    assert haste_cond is not None
    from dnd.core.base_conditions import DurationType
    haste_cond.duration.duration_type = DurationType.ROUNDS
    haste_cond.duration.duration = 1

    # End target's turn, cycle through other entities, back to target
    encounter.end_turn()
    encounter.next_turn()
    while (ce := encounter.get_current_entity()) and ce.uuid != target.uuid:
        encounter.end_turn()
        encounter.next_turn()

    # Haste should have expired at this turn start
    assert not has_condition(target, "Haste"), "Haste should expire after 1 round"
    assert has_condition(target, "Incapacitated"), \
        "Lethargy should fire on duration expiry"

    print("PASSED: test_9_lethargy_on_expiry")


# =============================================================================
# Test 10: Haste + mid-turn Action Surge gets EA on surge action
# =============================================================================
def test_10_haste_mid_turn_action_surge():
    """Attack→EA→Haste Attack→Action Surge→Attack→EA = 5 hits.

    Regression test: the suppression handler used to fire twice when Action Surge
    was used mid-turn (remaining_actions goes back to 1 after surge). The fix
    tracks a per-turn flag so suppression only fires once.
    """
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    fighter = create_fighter("Fighter", (3, 0), action_surge=True)
    dummy = create_dummy("Dummy", (4, 0))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(caster, fighter, dummy)
    cast_haste(caster, fighter)

    _navigate_to_turn(encounter, fighter)

    hit_mod = force_attack_hit(fighter)

    # Fighter has 2 actions (1 base + 1 haste). Do NOT surge first.
    actions = fighter.action_economy.actions.normalized_score
    assert actions == 2, f"Should have 2 actions, got {actions}"

    def _find_attack(name_contains: str):
        available = get_available_actions(fighter)
        matches = [a for a in available.entity_actions if name_contains in a.template_name]
        return matches[0] if matches else None

    def _do_attack(name_contains: str) -> int:
        info = _find_attack(name_contains)
        assert info is not None, f"Expected to find action containing '{name_contains}'"
        set_hp(dummy, 500)
        hp_before = get_hp(dummy)
        execute_action(fighter, info.template_name,
                       AvailableTarget(index=0, target_uuid=dummy.uuid))
        return 1 if get_hp(dummy) < hp_before else 0

    # Attack #1 (costs 1 action, remaining=2): EA should be available
    hit1 = _do_attack("Attack")
    # Extra Attack (free, uses extra_attacks resource)
    hit2 = _do_attack("Extra Attack")

    # Attack #2 (haste action, remaining=1): EA suppressed
    hit3 = _do_attack("Attack")

    # Verify no Extra Attack available after haste action
    assert _find_attack("Extra Attack") is None, \
        "No Extra Attack should be available after haste action"

    # Action Surge mid-turn (remaining actions: 0 → 1)
    surge = ActionSurge(source_entity_uuid=fighter.uuid)
    surge.apply()
    actions_after_surge = fighter.action_economy.actions.normalized_score
    assert actions_after_surge == 1, f"Should have 1 action after surge, got {actions_after_surge}"

    # Attack #3 (surge action, remaining=1): EA should NOT be suppressed
    hit4 = _do_attack("Attack")
    # Extra Attack from surge action
    hit5 = _do_attack("Extra Attack")

    remove_attack_modifier(fighter, hit_mod)

    total_hits = hit1 + hit2 + hit3 + hit4 + hit5
    print(f"Mid-turn surge hits: {total_hits} (expected 5)")
    assert total_hits == 5, f"Should get 5 hits (2+1+2), got {total_hits}"

    print("PASSED: test_10_haste_mid_turn_action_surge")


# =============================================================================
# Run all tests
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_1_haste_applies_buffs,
        test_2_haste_extra_attack_suppression,
        test_3_haste_action_surge,
        test_4_lethargy_on_concentration_break,
        test_5_lethargy_on_ally,
        test_6_haste_slow_interaction,
        test_7_haste_slow_action_surge,
        test_8_lethargy_on_dispel,
        test_9_lethargy_on_expiry,
        test_10_haste_mid_turn_action_surge,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            print(f"\n{'='*60}")
            print(f"Running: {test.__name__}")
            print(f"{'='*60}")
            test()
            passed += 1
        except Exception as e:
            print(f"FAILED: {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    print(f"{'='*60}")
