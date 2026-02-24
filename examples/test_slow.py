"""
Test suite for Slow spell (3rd-level Transmutation, Concentration).

Tests:
1. Slow applies all debuffs on failed WIS save
2. Action OR bonus action lockout (not both)
3. No Extra Attack (fighter with Extra Attack gets only 1 swing)
4. Repeat WIS save at turn end removes Slowed on success
5. Concentration break removes all Slowed effects
6. Multiple targets linked to concentration
"""

from uuid import uuid4, UUID
from dnd.utils import (
    reset_combat_state, set_hp, has_condition, get_hp,
    force_attack_hit, remove_attack_modifier, deal_damage_to
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.conditions import Concentrating
from dnd.spells import Slow
from dnd.spells.transmutation import SlowedEffect
from dnd.actions_functional import setup_standard_actions, get_available_actions, execute_action
from dnd.core.base_actions import AvailableTarget
from dnd.core.events import WeaponSlot
from dnd.items.weapons import create_longsword, create_greatsword
from dnd.encounter import Encounter
from dnd.controller import HumanController
from dnd.classes.fighter import ExtraAttackFeature, ActionSurgeFeature, ActionSurge
from dnd.core.modifiers import NumericalModifier


def force_save_fail(entity: Entity, ability: str = "wisdom") -> UUID:
    """Add -100 to saving throw to guarantee failure. Returns modifier UUID."""
    save = entity.saving_throws.get_saving_throw(ability)
    mod = NumericalModifier(name="Force Fail", value=-100,
                            source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    save.bonus.self_static.add_value_modifier(mod)
    return mod.uuid


def force_save_succeed(entity: Entity, ability: str = "wisdom") -> UUID:
    """Add +100 to saving throw to guarantee success. Returns modifier UUID."""
    save = entity.saving_throws.get_saving_throw(ability)
    mod = NumericalModifier(name="Force Succeed", value=100,
                            source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    save.bonus.self_static.add_value_modifier(mod)
    return mod.uuid


def remove_save_modifier(entity: Entity, mod_uuid: UUID, ability: str = "wisdom"):
    """Remove a force save modifier."""
    save = entity.saving_throws.get_saving_throw(ability)
    save.bonus.self_static.remove_value_modifier(mod_uuid)


def create_caster(name: str, position: tuple) -> Entity:
    """Create a caster with high WIS for spell DC."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=20),  # +5 → DC = 8+4+5 = 17
        ),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3, 3: 3},
        ),
        spellcasting=SpellcastingConfig(spellcasting_ability="wisdom"),
        proficiency_bonus=4,
        position=position
    )
    caster = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(caster)
    return caster


def create_target(name: str, position: tuple, wis: int = 6) -> Entity:
    """Create a target with low WIS to fail saves."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=wis),
            dexterity=AbilityConfig(ability_score=14),  # +2 DEX
            strength=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=20, mode="maximums"
        )]),
        proficiency_bonus=2,
        position=position
    )
    target = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(target)
    weapon = create_longsword(target.uuid)
    target.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    return target


def create_fighter_target(name: str, position: tuple) -> Entity:
    """Create a fighter with Extra Attack."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
            wisdom=AbilityConfig(ability_score=6),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=20, mode="maximums"
        )]),
        proficiency_bonus=4,
        position=position
    )
    fighter = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(fighter)
    weapon = create_greatsword(fighter.uuid)
    fighter.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    ea = ExtraAttackFeature(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        extra_attacks=1
    )
    fighter.add_condition(ea)
    return fighter


def cast_slow(caster: Entity, position: tuple):
    """Cast Slow centered on a position."""
    slow = Slow(source_entity_uuid=caster.uuid, end_position=position, template=False)
    return slow.apply()


def setup_encounter(*entities: Entity) -> Encounter:
    """Create and start an encounter."""
    encounter = Encounter(name="Test Slow", source_entity_uuid=uuid4())
    for e in entities:
        encounter.add_combatant(e, HumanController(source_entity_uuid=e.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    return encounter


# =============================================================================
# Test 1: Static debuffs
# =============================================================================
def test_1_slow_applies_debuffs():
    """Verify speed halved, -2 AC, -2 DEX save, no reactions."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    target = create_target("Goblin", (3, 0))
    Entity.update_all_entities_senses()

    base_speed = target.action_economy.movement.normalized_score
    base_ac = target.equipment.ac_bonus.normalized_score
    base_dex_save = target.saving_throws.get_saving_throw("dexterity").bonus.normalized_score

    fail_mod = force_save_fail(target)
    cast_slow(caster, (3, 0))
    remove_save_modifier(target, fail_mod)
    assert has_condition(target, "Slowed"), "Target should be Slowed"
    assert has_condition(caster, "Concentrating"), "Caster should be Concentrating"

    assert target.action_economy.movement.normalized_score == base_speed // 2, \
        f"Speed should be halved: {target.action_economy.movement.normalized_score} != {base_speed // 2}"
    assert target.equipment.ac_bonus.normalized_score == base_ac - 2, \
        f"AC should be -2: {target.equipment.ac_bonus.normalized_score}"
    assert target.saving_throws.get_saving_throw("dexterity").bonus.normalized_score == base_dex_save - 2, \
        f"DEX save should be -2"
    assert target.action_economy.reactions.normalized_score == 0, \
        f"Reactions should be 0"

    print("PASSED: test_1_slow_applies_debuffs")


# =============================================================================
# Test 2: Action/Bonus lockout
# =============================================================================
def test_2_action_bonus_lockout():
    """Using an action should lock bonus actions."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    target = create_target("Goblin", (3, 0))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(caster, target)

    fail_mod = force_save_fail(target)
    cast_slow(caster, (3, 0))
    remove_save_modifier(target, fail_mod)
    assert has_condition(target, "Slowed"), "Target should be Slowed"

    # Navigate to target's turn
    encounter.start_turn()
    while encounter.get_current_entity().uuid != target.uuid:
        encounter.end_turn()
        encounter.next_turn()

    # Baseline checks
    assert target.action_economy.actions.normalized_score >= 1
    assert target.action_economy.bonus_actions.normalized_score >= 1

    # Use Dodge (costs 1 action)
    execute_action(target, "Dodge", AvailableTarget(index=0))

    # Bonus actions should now be locked to 0
    bonus_after = target.action_economy.bonus_actions.normalized_score
    assert bonus_after == 0, f"Bonus should be locked to 0 after action, got {bonus_after}"

    # End turn and go to target's next turn — lockout should reset
    encounter.end_turn()
    encounter.next_turn()
    while encounter.get_current_entity().uuid != target.uuid:
        encounter.end_turn()
        encounter.next_turn()

    bonus_reset = target.action_economy.bonus_actions.normalized_score
    assert bonus_reset >= 1, f"Bonus should be restored after turn reset, got {bonus_reset}"

    print("PASSED: test_2_action_bonus_lockout")


# =============================================================================
# Test 3: No Extra Attack while Slowed
# =============================================================================
def _attack_until_done(fighter, dummy):
    """Execute melee attacks until fighter runs out. Returns number of hits."""
    hits = 0
    set_hp(dummy, 500)  # Ensure target survives all attacks
    for _ in range(10):  # Safety limit
        available = get_available_actions(fighter)
        attack_infos = [a for a in available.entity_actions
                        if "Attack" in a.template_name]
        if not attack_infos:
            break
        # Check we have actions or extra attacks left
        actions_left = fighter.action_economy.actions.normalized_score
        ea = fighter.action_economy.resources.get("extra_attacks")
        ea_left = ea.current if ea else 0
        if actions_left <= 0 and ea_left <= 0:
            break
        hp_before = get_hp(dummy)
        execute_action(fighter, attack_infos[0].template_name,
                       AvailableTarget(index=0, target_uuid=dummy.uuid))
        if get_hp(dummy) < hp_before:
            hits += 1
    return hits


def test_3_no_extra_attack():
    """A Slowed fighter should not get Extra Attack — actually attack and count hits."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    fighter = create_fighter_target("Fighter", (3, 0))
    dummy = create_target("Dummy", (4, 0))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(caster, fighter, dummy)

    # --- Phase 1: Attack WITHOUT Slow (should get 2 hits: 1 normal + 1 Extra Attack) ---
    encounter.start_turn()
    while encounter.get_current_entity().uuid != fighter.uuid:
        encounter.end_turn()
        encounter.next_turn()

    hit_mod = force_attack_hit(fighter)

    hits_normal = _attack_until_done(fighter, dummy)
    print(f"Hits without Slow: {hits_normal}")
    assert hits_normal == 2, f"Fighter with Extra Attack should get 2 hits, got {hits_normal}"

    remove_attack_modifier(fighter, hit_mod)
    encounter.end_turn()

    # --- Phase 2: Apply Slow and attack again (should get only 1 hit) ---
    fail_mod = force_save_fail(fighter)
    cast_slow(caster, (3, 0))
    remove_save_modifier(fighter, fail_mod)
    assert has_condition(fighter, "Slowed"), "Fighter should be Slowed"

    # Cycle to fighter's turn
    encounter.next_turn()
    while encounter.get_current_entity().uuid != fighter.uuid:
        encounter.end_turn()
        encounter.next_turn()

    hit_mod = force_attack_hit(fighter)

    hits_slowed = _attack_until_done(fighter, dummy)
    print(f"Hits with Slow: {hits_slowed}")
    assert hits_slowed == 1, f"Slowed fighter should get only 1 hit, got {hits_slowed}"

    remove_attack_modifier(fighter, hit_mod)
    print("PASSED: test_3_no_extra_attack")


# =============================================================================
# Test 4: Repeat WIS save
# =============================================================================
def test_4_repeat_save():
    """Target with high WIS should eventually save out of Slow."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    target = create_target("Paladin", (3, 0), wis=20)
    Entity.update_all_entities_senses()

    encounter = setup_encounter(caster, target)

    # Force initial save to fail so we can test repeat saves
    fail_mod = force_save_fail(target)
    cast_slow(caster, (3, 0))
    remove_save_modifier(target, fail_mod)
    assert has_condition(target, "Slowed"), "Target should be Slowed after forced fail"

    # Force repeat saves to succeed
    succeed_mod = force_save_succeed(target)

    # Run turns until target saves
    saved = False
    encounter.start_turn()
    for _ in range(20):
        if encounter.get_current_entity().uuid == target.uuid:
            encounter.end_turn()
            if not has_condition(target, "Slowed"):
                saved = True
                print("Target saved out of Slow on repeat save")
                break
            encounter.next_turn()
        else:
            encounter.end_turn()
            encounter.next_turn()

    remove_save_modifier(target, succeed_mod)
    assert saved, "Target should save with forced success"
    print("PASSED: test_4_repeat_save")


# =============================================================================
# Test 5: Concentration break
# =============================================================================
def test_5_concentration_break():
    """Breaking concentration removes all Slowed effects."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    target1 = create_target("Goblin 1", (3, 0))
    target2 = create_target("Goblin 2", (3, 1))
    Entity.update_all_entities_senses()

    fail_mod1 = force_save_fail(target1)
    fail_mod2 = force_save_fail(target2)
    cast_slow(caster, (3, 0))
    remove_save_modifier(target1, fail_mod1)
    remove_save_modifier(target2, fail_mod2)

    t1_slowed = has_condition(target1, "Slowed")
    t2_slowed = has_condition(target2, "Slowed")
    print(f"After cast: T1={t1_slowed}, T2={t2_slowed}")
    assert t1_slowed and t2_slowed, "Both should be Slowed"
    assert has_condition(caster, "Concentrating")

    # Break concentration by killing the caster
    set_hp(caster, 1)
    deal_damage_to(caster, 100, DamageType.FORCE, uuid4())

    assert not has_condition(target1, "Slowed"), "T1 should no longer be Slowed"
    assert not has_condition(target2, "Slowed"), "T2 should no longer be Slowed"
    assert not has_condition(caster, "Concentrating"), "Caster should not be Concentrating"

    print("PASSED: test_5_concentration_break")


# =============================================================================
# Test 6: Multiple targets linked to concentration
# =============================================================================
def test_6_multiple_targets():
    """Slow affects multiple targets, all linked to concentration."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))
    targets = [create_target(f"Goblin {i}", (3, i)) for i in range(3)]
    Entity.update_all_entities_senses()

    fail_mods = [force_save_fail(t) for t in targets]
    cast_slow(caster, (3, 1))
    for t, mod in zip(targets, fail_mods):
        remove_save_modifier(t, mod)

    slowed_count = sum(1 for t in targets if has_condition(t, "Slowed"))
    print(f"Slowed targets: {slowed_count}/{len(targets)}")
    assert slowed_count == 3, f"All 3 should be Slowed, got {slowed_count}"

    conc = caster.active_conditions.get("Concentrating")
    assert conc is not None and isinstance(conc, Concentrating)
    assert len(conc.linked_conditions) == slowed_count, \
        f"Should have {slowed_count} linked conditions, got {len(conc.linked_conditions)}"

    print("PASSED: test_6_multiple_targets")


# =============================================================================
# Test 7: Slow + Action Surge
# =============================================================================
def test_7_slow_action_surge():
    """Slowed fighter with Action Surge: 2 actions, no EA on either."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (0, 0))

    # Fighter with Extra Attack + Action Surge
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
            wisdom=AbilityConfig(ability_score=6),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=20, mode="maximums"
        )]),
        proficiency_bonus=4,
        position=(3, 0)
    )
    fighter = Entity.create(source_entity_uuid=uuid4(), name="Fighter", config=config)
    setup_standard_actions(fighter)
    weapon = create_greatsword(fighter.uuid)
    fighter.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    ea = ExtraAttackFeature(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        extra_attacks=1
    )
    fighter.add_condition(ea)
    asf = ActionSurgeFeature(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        num_uses=1
    )
    fighter.add_condition(asf)

    dummy = create_target("Dummy", (4, 0))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(caster, fighter, dummy)

    # Apply Slow
    fail_mod = force_save_fail(fighter)
    cast_slow(caster, (3, 0))
    remove_save_modifier(fighter, fail_mod)
    assert has_condition(fighter, "Slowed"), "Fighter should be Slowed"

    # Navigate to fighter's turn
    encounter.start_turn()
    while encounter.get_current_entity().uuid != fighter.uuid:
        encounter.end_turn()
        encounter.next_turn()

    # Use Action Surge
    surge = ActionSurge(source_entity_uuid=fighter.uuid)
    surge.apply()

    actions = fighter.action_economy.actions.normalized_score
    print(f"Actions with Slow + Surge: {actions}")
    assert actions == 2, f"Should have 2 actions (1 base + 1 surge), got {actions}"

    hit_mod = force_attack_hit(fighter)
    hits = _attack_until_done(fighter, dummy)
    remove_attack_modifier(fighter, hit_mod)

    print(f"Slow + Action Surge hits: {hits}")
    # Slow suppresses ALL EA → each action = 1 single attack
    assert hits == 2, f"Should get 2 hits (no EA on either), got {hits}"

    print("PASSED: test_7_slow_action_surge")


# =============================================================================
# Run all tests
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_1_slow_applies_debuffs,
        test_2_action_bonus_lockout,
        test_3_no_extra_attack,
        test_4_repeat_save,
        test_5_concentration_break,
        test_6_multiple_targets,
        test_7_slow_action_surge,
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
