"""
Test suite for Potion of Haste.

Verifies the potion applies Haste effect without concentration or lethargy:
1. Drinking applies all Haste buffs (+speed, +2 AC, DEX advantage, +1 action)
2. No concentration required
3. No lethargy when effect expires
4. Potion consumed after use
5. EA suppression works on potion Haste (last action = haste action)
"""

from uuid import uuid4
from dnd.utils import (
    reset_combat_state, has_condition, get_hp,
    force_attack_hit, remove_attack_modifier,
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import AdvantageStatus
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.actions_functional import setup_standard_actions, execute_action, get_available_actions
from dnd.core.base_actions import AvailableTarget
from dnd.core.events import WeaponSlot
from dnd.items.weapons import create_longsword
from dnd.items.test_items import create_potion_of_haste
from dnd.classes.fighter import ExtraAttackFeature
from dnd.encounter import Encounter
from dnd.controller import HumanController


# =============================================================================
# Helpers
# =============================================================================

def create_fighter(name: str, position: tuple) -> Entity:
    """Create a fighter with Extra Attack."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=20, mode="maximums"
        )]),
        proficiency_bonus=4,
        position=position,
        faction="party"
    )
    fighter = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(fighter)
    weapon = create_longsword(fighter.uuid)
    fighter.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)

    # Extra Attack via condition (same as test_haste.py)
    ea = ExtraAttackFeature(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        extra_attacks=1
    )
    fighter.add_condition(ea)
    return fighter


def create_target(name: str, position: tuple) -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=20, mode="maximums"
        )]),
        proficiency_bonus=2,
        position=position,
        faction="enemies"
    )
    target = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(target)
    weapon = create_longsword(target.uuid)
    target.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    return target


def setup_encounter(*entities: Entity) -> Encounter:
    encounter = Encounter(name="Test Haste Potion", source_entity_uuid=uuid4())
    for e in entities:
        encounter.add_combatant(e, HumanController(source_entity_uuid=e.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    return encounter


def navigate_to_turn(encounter: Encounter, entity: Entity):
    encounter.start_turn()
    while (ce := encounter.get_current_entity()) and ce.uuid != entity.uuid:
        encounter.end_turn()
        encounter.next_turn()


def _attack_until_done(attacker: Entity, target: Entity) -> int:
    """Execute attacks until no more available, return hit count."""
    hits = 0
    hp_before = get_hp(target)
    for _ in range(10):  # safety limit
        actions = get_available_actions(attacker)
        # Prioritize Extra Attack over regular Attack
        attack_name = None
        for a in actions.entity_actions:
            if "Extra Attack" in a.template_name:
                attack_name = a.template_name
                break
        if not attack_name:
            for a in actions.entity_actions:
                if "Attack" in a.template_name:
                    attack_name = a.template_name
                    break
        if not attack_name:
            break
        execute_action(attacker, attack_name,
                       AvailableTarget(index=0, target_uuid=target.uuid))
        new_hp = get_hp(target)
        if new_hp < hp_before:
            hits += 1
            hp_before = new_hp
    return hits


# =============================================================================
# Test 1: Potion applies Haste buffs
# =============================================================================
def test_1_potion_applies_buffs():
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    fighter = create_fighter("Hero", (3, 0))
    Entity.update_all_entities_senses()

    base_speed = fighter.action_economy.movement.normalized_score
    base_ac = fighter.equipment.ac_bonus.normalized_score
    base_actions = fighter.action_economy.actions.normalized_score
    dex_save = fighter.saving_throws.get_saving_throw("dexterity")
    _base_dex_adv = dex_save.bonus.advantage

    # Give potion and add to inventory
    potion = create_potion_of_haste(fighter.uuid)
    fighter.loot_item(potion)

    # Use the potion via the item action system
    from dnd.actions_functional import execute_use_action
    execute_use_action(fighter, potion.uuid, "Drink Haste Potion")

    assert has_condition(fighter, "Haste"), "Should have Haste condition"

    # Speed doubled
    new_speed = fighter.action_economy.movement.normalized_score
    assert new_speed == base_speed * 2, \
        f"Speed should double: {new_speed} != {base_speed * 2}"

    # +2 AC
    new_ac = fighter.equipment.ac_bonus.normalized_score
    assert new_ac == base_ac + 2, \
        f"AC should be +2: {new_ac} != {base_ac + 2}"

    # +1 action
    new_actions = fighter.action_economy.actions.normalized_score
    assert new_actions == base_actions + 1, \
        f"Actions should be +1: {new_actions} != {base_actions + 1}"

    # DEX save advantage
    new_dex_adv = dex_save.bonus.advantage
    assert new_dex_adv == AdvantageStatus.ADVANTAGE, \
        f"Should have DEX advantage, got {new_dex_adv}"

    print("PASSED: test_1_potion_applies_buffs")


# =============================================================================
# Test 2: No concentration
# =============================================================================
def test_2_no_concentration():
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    fighter = create_fighter("Hero", (3, 0))
    Entity.update_all_entities_senses()

    potion = create_potion_of_haste(fighter.uuid)
    fighter.loot_item(potion)

    from dnd.actions_functional import execute_use_action
    execute_use_action(fighter, potion.uuid, "Drink Haste Potion")

    assert has_condition(fighter, "Haste"), "Should have Haste"
    assert not has_condition(fighter, "Concentrating"), "Should NOT require concentration"

    print("PASSED: test_2_no_concentration")


# =============================================================================
# Test 3: No lethargy when effect expires
# =============================================================================
def test_3_lethargy_on_expiry():
    """Lethargy (Incapacitated 1 round) when potion Haste expires."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    fighter = create_fighter("Hero", (3, 0))
    target = create_target("Dummy", (4, 0))
    Entity.update_all_entities_senses()

    base_ac = fighter.equipment.ac_bonus.normalized_score

    potion = create_potion_of_haste(fighter.uuid)
    fighter.loot_item(potion)

    from dnd.actions_functional import execute_use_action
    execute_use_action(fighter, potion.uuid, "Drink Haste Potion")
    assert has_condition(fighter, "Haste")

    encounter = setup_encounter(fighter, target)

    # Run 10 full rounds to expire the effect
    navigate_to_turn(encounter, fighter)
    for _ in range(10):
        encounter.end_turn()
        encounter.next_turn()
        # Other entity's turn
        encounter.end_turn()
        encounter.next_turn()
        # Back to fighter's turn (advance_duration fires here)
        if not has_condition(fighter, "Haste"):
            break

    assert not has_condition(fighter, "Haste"), "Haste should expire after 10 rounds"
    assert has_condition(fighter, "Incapacitated"), \
        "Should have lethargy (Incapacitated) when Haste ends"

    # AC should reflect Incapacitated, not Haste
    restored_ac = fighter.equipment.ac_bonus.normalized_score
    assert restored_ac == base_ac, \
        f"Haste AC bonus should be gone: {restored_ac} != {base_ac}"

    print("PASSED: test_3_lethargy_on_expiry")


# =============================================================================
# Test 4: Potion consumed after use
# =============================================================================
def test_4_potion_consumed():
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    fighter = create_fighter("Hero", (3, 0))
    Entity.update_all_entities_senses()

    potion = create_potion_of_haste(fighter.uuid)
    fighter.loot_item(potion)
    potion_uuid = potion.uuid

    assert fighter.inventory.has_item(potion_uuid), "Should have potion in inventory"

    from dnd.actions_functional import execute_use_action
    execute_use_action(fighter, potion.uuid, "Drink Haste Potion")

    assert not fighter.inventory.has_item(potion_uuid), \
        "Potion should be consumed (removed from inventory)"

    print("PASSED: test_4_potion_consumed")


# =============================================================================
# Test 5: EA suppression on haste action
# =============================================================================
def test_5_ea_suppression():
    """With potion Haste: 2 actions. 1st gets EA (2 swings), 2nd no EA (1 swing) = 3 total."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    fighter = create_fighter("Hero", (3, 0))
    target = create_target("Dummy", (4, 0))
    Entity.update_all_entities_senses()

    potion = create_potion_of_haste(fighter.uuid)
    fighter.loot_item(potion)

    from dnd.actions_functional import execute_use_action
    execute_use_action(fighter, potion.uuid, "Drink Haste Potion")

    encounter = setup_encounter(fighter, target)
    navigate_to_turn(encounter, fighter)

    hit_mod = force_attack_hit(fighter)
    hits = _attack_until_done(fighter, target)
    remove_attack_modifier(fighter, hit_mod)

    print(f"Haste potion hits: {hits}")
    assert hits == 3, f"Expected 3 hits (EA on 1st action, none on 2nd), got {hits}"

    print("PASSED: test_5_ea_suppression")


# =============================================================================
# Run all tests
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_1_potion_applies_buffs,
        test_2_no_concentration,
        test_3_lethargy_on_expiry,
        test_4_potion_consumed,
        test_5_ea_suppression,
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
