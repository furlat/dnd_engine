"""
Test suite for Mirror Image spell (2nd-level Illusion, BG3 version).

BG3 mechanics:
- 3 duplicates, each gives +3 AC (total +9)
- When attack misses (evaded), one duplicate disappears
- Duration: 10 turns, no concentration

Tests:
1. Mirror Image applies +9 AC with 3 duplicates
2. Attack miss destroys one duplicate, AC drops by 3
3. All duplicates destroyed removes condition
4. Attack hit does NOT destroy a duplicate
5. No concentration required
6. Duration expires after 10 rounds
"""

from uuid import uuid4, UUID
from dnd.utils import (
    reset_combat_state, set_hp, has_condition, get_hp,
    force_attack_hit, force_attack_miss, remove_attack_modifier
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.spells import MirrorImage
from dnd.spells.illusion import MirrorImageEffect
from dnd.actions_functional import setup_standard_actions, execute_action
from dnd.core.base_actions import AvailableTarget
from dnd.core.events import WeaponSlot
from dnd.items.weapons import create_longsword
from dnd.encounter import Encounter
from dnd.controller import HumanController


# =============================================================================
# Helpers
# =============================================================================

def create_caster(name: str, position: tuple) -> Entity:
    """Create a caster who can cast Mirror Image."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            dexterity=AbilityConfig(ability_score=14),
            wisdom=AbilityConfig(ability_score=16),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=8, hit_dice_count=10, mode="maximums"
        )]),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3},
        ),
        spellcasting=SpellcastingConfig(spellcasting_ability="wisdom"),
        proficiency_bonus=4,
        position=position,
        faction="party"
    )
    caster = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(caster)
    weapon = create_longsword(caster.uuid)
    caster.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    return caster


def create_attacker(name: str, position: tuple) -> Entity:
    """Create an attacker."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=20, mode="maximums"
        )]),
        proficiency_bonus=4,
        position=position,
        faction="enemies"
    )
    attacker = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(attacker)
    weapon = create_longsword(attacker.uuid)
    attacker.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    return attacker


def cast_mirror_image(caster: Entity):
    """Cast Mirror Image on self."""
    mi = MirrorImage(source_entity_uuid=caster.uuid, template=False)
    return mi.apply()


def setup_encounter(*entities: Entity) -> Encounter:
    """Create and start an encounter."""
    encounter = Encounter(name="Test Mirror Image", source_entity_uuid=uuid4())
    for e in entities:
        encounter.add_combatant(e, HumanController(source_entity_uuid=e.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    return encounter


def get_mirror_condition(entity: Entity) -> MirrorImageEffect:
    """Get the MirrorImageEffect condition."""
    cond = entity.active_conditions.get("Mirror Image")
    assert cond is not None and isinstance(cond, MirrorImageEffect)
    return cond


def navigate_to_turn(encounter: Encounter, entity: Entity):
    """Navigate to the given entity's turn."""
    encounter.start_turn()
    while encounter.get_current_entity().uuid != entity.uuid:
        encounter.end_turn()
        encounter.next_turn()


# =============================================================================
# Test 1: Mirror Image applies +9 AC
# =============================================================================
def test_1_mirror_image_applies():
    """Verify 3 duplicates and +9 AC."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (3, 0))
    Entity.update_all_entities_senses()

    base_ac = caster.equipment.ac_bonus.normalized_score
    cast_mirror_image(caster)

    assert has_condition(caster, "Mirror Image"), "Should have Mirror Image"

    cond = get_mirror_condition(caster)
    assert cond.duplicates == 3, f"Should have 3 duplicates, got {cond.duplicates}"

    buffed_ac = caster.equipment.ac_bonus.normalized_score
    assert buffed_ac == base_ac + 9, \
        f"AC should be +9: {buffed_ac} != {base_ac + 9}"

    print("PASSED: test_1_mirror_image_applies")


# =============================================================================
# Test 2: Attack miss destroys one duplicate
# =============================================================================
def test_2_miss_destroys_duplicate():
    """Attack miss removes one duplicate, AC drops by 3."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (3, 0))
    attacker = create_attacker("Fighter", (4, 0))
    Entity.update_all_entities_senses()

    cast_mirror_image(caster)
    base_ac = caster.equipment.ac_bonus.normalized_score  # includes +9

    encounter = setup_encounter(attacker, caster)

    # Force attack to miss
    miss_mod = force_attack_miss(attacker)

    navigate_to_turn(encounter, attacker)
    execute_action(attacker, "Attack_MELEE_MAIN",
                   AvailableTarget(index=0, target_uuid=caster.uuid))

    remove_attack_modifier(attacker, miss_mod)

    cond = get_mirror_condition(caster)
    assert cond.duplicates == 2, \
        f"Should have 2 duplicates after miss, got {cond.duplicates}"

    new_ac = caster.equipment.ac_bonus.normalized_score
    assert new_ac == base_ac - 3, \
        f"AC should drop by 3: {new_ac} != {base_ac - 3}"

    print("PASSED: test_2_miss_destroys_duplicate")


# =============================================================================
# Test 3: All duplicates destroyed removes condition
# =============================================================================
def test_3_all_duplicates_destroyed():
    """3 misses destroy all duplicates and remove condition."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (3, 0))
    attacker = create_attacker("Fighter", (4, 0))
    Entity.update_all_entities_senses()

    base_ac = caster.equipment.ac_bonus.normalized_score  # without mirror image
    cast_mirror_image(caster)
    assert has_condition(caster, "Mirror Image")

    encounter = setup_encounter(attacker, caster)

    miss_mod = force_attack_miss(attacker)

    # First turn
    navigate_to_turn(encounter, attacker)
    for i in range(3):
        execute_action(attacker, "Attack_MELEE_MAIN",
                       AvailableTarget(index=0, target_uuid=caster.uuid))
        # Cycle to next attacker turn (except after last attack)
        if i < 2:
            encounter.end_turn()
            encounter.next_turn()
            while encounter.get_current_entity().uuid != attacker.uuid:
                encounter.end_turn()
                encounter.next_turn()

    remove_attack_modifier(attacker, miss_mod)

    assert not has_condition(caster, "Mirror Image"), \
        "Mirror Image should be removed after all duplicates destroyed"

    restored_ac = caster.equipment.ac_bonus.normalized_score
    assert restored_ac == base_ac, \
        f"AC should be restored to base: {restored_ac} != {base_ac}"

    print("PASSED: test_3_all_duplicates_destroyed")


# =============================================================================
# Test 4: Attack hit does NOT destroy a duplicate
# =============================================================================
def test_4_hit_keeps_duplicate():
    """Attack that hits does not destroy a duplicate."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (3, 0))
    attacker = create_attacker("Fighter", (4, 0))
    Entity.update_all_entities_senses()

    cast_mirror_image(caster)
    hp_before = get_hp(caster)

    encounter = setup_encounter(attacker, caster)

    # Force attack to hit (overcomes even +9 AC)
    hit_mod = force_attack_hit(attacker)

    navigate_to_turn(encounter, attacker)
    execute_action(attacker, "Attack_MELEE_MAIN",
                   AvailableTarget(index=0, target_uuid=caster.uuid))

    remove_attack_modifier(attacker, hit_mod)

    # Caster takes damage
    assert get_hp(caster) < hp_before, "Attack should hit through mirror images"

    # Duplicates unchanged
    cond = get_mirror_condition(caster)
    assert cond.duplicates == 3, \
        f"Duplicates should still be 3 after hit, got {cond.duplicates}"

    print("PASSED: test_4_hit_keeps_duplicate")


# =============================================================================
# Test 5: No concentration required
# =============================================================================
def test_5_no_concentration():
    """Mirror Image does NOT require concentration."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (3, 0))
    Entity.update_all_entities_senses()

    cast_mirror_image(caster)

    assert has_condition(caster, "Mirror Image")
    assert not has_condition(caster, "Concentrating"), \
        "Should NOT require concentration"

    print("PASSED: test_5_no_concentration")


# =============================================================================
# Test 6: Duration expires after 10 rounds
# =============================================================================
def test_6_duration_expires():
    """Mirror Image expires after 10 rounds."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Wizard", (3, 0))
    attacker = create_attacker("Fighter", (4, 0))
    Entity.update_all_entities_senses()

    base_ac = caster.equipment.ac_bonus.normalized_score
    cast_mirror_image(caster)
    assert has_condition(caster, "Mirror Image")

    encounter = setup_encounter(caster, attacker)

    # Run 10 full rounds — advance_duration ticks at turn start for the condition owner
    navigate_to_turn(encounter, caster)
    for i in range(10):
        encounter.end_turn()
        encounter.next_turn()
        # Attacker's turn
        encounter.end_turn()
        encounter.next_turn()
        # Back to caster's turn (advance_duration fires here)
        if has_condition(caster, "Mirror Image"):
            continue
        else:
            break

    assert not has_condition(caster, "Mirror Image"), \
        "Mirror Image should expire after 10 rounds"

    restored_ac = caster.equipment.ac_bonus.normalized_score
    assert restored_ac == base_ac, \
        f"AC should be restored after expiry: {restored_ac} != {base_ac}"

    print("PASSED: test_6_duration_expires")


# =============================================================================
# Run all tests
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_1_mirror_image_applies,
        test_2_miss_destroys_duplicate,
        test_3_all_duplicates_destroyed,
        test_4_hit_keeps_duplicate,
        test_5_no_concentration,
        test_6_duration_expires,
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
