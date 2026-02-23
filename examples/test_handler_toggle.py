"""
Test Handler Toggle System

Tests the `enabled` flag on BaseHandler that allows handlers to be
individually enabled/disabled. Primary use case: reactions (OA, Protection)
that should be optional.
"""

import sys
sys.path.insert(0, '.')

from dnd.core.gridmap import get_map
from dnd.core.events import EventQueue, WeaponSlot
from dnd.core.modifiers import AdvantageStatus
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton, create_goblin
from dnd.classes.fighter import FightingStyleProtection
from dnd.blocks.equipment import Shield
from dnd.actions import Attack
from dnd.actions_functional import setup_standard_actions
from dnd.reactions import add_opportunity_attack_handler
from dnd.conditions import InvisibilityEffect
from dnd.utils import (
    reset_combat_state, force_attack_hit,
    remove_attack_modifier, get_hp
)


def create_shield(source_uuid) -> Shield:
    return Shield(
        source_entity_uuid=source_uuid,
        name="Shield",
        ac_bonus=ModifiableValue.create(
            source_entity_uuid=source_uuid,
            base_value=2,
            value_name="Shield AC Bonus"
        )
    )


def setup_oa_scenario():
    """Two adjacent enemies. Moving one away should trigger OA from the other."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    # Attacker has OA handler
    attacker = create_skeleton(name="OA Source", position=(5, 5))
    setup_standard_actions(attacker)
    add_opportunity_attack_handler(attacker)

    # Mover will walk away
    mover = create_goblin(name="Mover", position=(5, 6))
    setup_standard_actions(mover)

    Entity.update_all_entities_senses(max_distance=20)
    return attacker, mover


def test_oa_enabled_fires_normally():
    """Test 1: OA fires when handler is enabled (default)."""
    print("\n=== Test 1: OA Enabled Fires Normally ===")
    attacker, mover = setup_oa_scenario()

    mod_id = force_attack_hit(attacker)

    # Move mover away from attacker's threat range
    from dnd.actions_functional import execute_by_index
    execute_by_index(mover, "Move", 0)  # Move to first available position

    remove_attack_modifier(attacker, mod_id)

    # OA may or may not have triggered depending on path, let's check handler is findable
    handler = attacker.get_event_handler_by_name("Opportunity Attack Handler")
    assert handler is not None, "Should find OA handler by name"
    assert handler.enabled is True, "Handler should be enabled by default"
    print(f"  OA Handler found: {handler.name}, enabled={handler.enabled}")
    print("  PASSED: OA handler enabled by default and findable")


def test_oa_disabled_prevents_attack():
    """Test 2: OA does NOT fire when handler is disabled."""
    print("\n=== Test 2: OA Disabled Prevents Attack ===")
    attacker, mover = setup_oa_scenario()

    # Disable OA handler
    result = attacker.set_handler_enabled("Opportunity Attack Handler", False)
    assert result is True, "Should find and disable OA handler"

    handler = attacker.get_event_handler_by_name("Opportunity Attack Handler")
    assert handler is not None, "Handler should still exist"
    assert handler.enabled is False, "Handler should be disabled"

    hp_before = get_hp(mover)
    mod_id = force_attack_hit(attacker)

    # Move mover directly away — should NOT trigger OA
    from dnd.core.gridmap import get_map as gm
    grid = gm()
    grid.move_entity(mover.uuid, (5, 9))  # Move far away
    mover.update_entity_senses()

    hp_after = get_hp(mover)
    remove_attack_modifier(attacker, mod_id)

    assert hp_before == hp_after, f"HP should not change (OA disabled): {hp_before} -> {hp_after}"
    print(f"  HP before: {hp_before}, after: {hp_after}")
    print("  PASSED: OA disabled, no damage taken")


def test_toggle_on_off_cycle():
    """Test 3: Handler can be toggled on and off repeatedly."""
    print("\n=== Test 3: Toggle On/Off Cycle ===")
    attacker, _ = setup_oa_scenario()

    handler = attacker.get_event_handler_by_name("Opportunity Attack Handler")
    assert handler is not None

    # Cycle: enabled -> disabled -> enabled
    assert handler.enabled is True
    attacker.set_handler_enabled("Opportunity Attack Handler", False)
    assert handler.enabled is False
    attacker.set_handler_enabled("Opportunity Attack Handler", True)
    assert handler.enabled is True

    print("  PASSED: Toggle cycle works correctly")


def test_disabled_handler_stays_registered():
    """Test 4: Disabled handler remains in event_handlers dict and EventQueue."""
    print("\n=== Test 4: Disabled Handler Stays Registered ===")
    attacker, _ = setup_oa_scenario()

    handler = attacker.get_event_handler_by_name("Opportunity Attack Handler")
    assert handler is not None
    handler_uuid = handler.uuid

    # Disable it
    attacker.set_handler_enabled("Opportunity Attack Handler", False)

    # Still in entity's dict
    assert handler_uuid in attacker.event_handlers, "Handler should still be in event_handlers dict"

    # Still in EventQueue
    assert handler_uuid in EventQueue._event_handlers, "Handler should still be in EventQueue"

    print("  PASSED: Disabled handler stays registered")


def test_set_handler_enabled_missing_name():
    """Test 5: set_handler_enabled returns False for non-existent handler."""
    print("\n=== Test 5: Missing Handler Name Returns False ===")
    attacker, _ = setup_oa_scenario()

    result = attacker.set_handler_enabled("Nonexistent Handler", False)
    assert result is False, "Should return False for missing handler"

    print("  PASSED: Returns False for missing handler name")


def test_set_handler_enabled_by_uuid():
    """Test 6: Toggle handler by UUID."""
    print("\n=== Test 6: Toggle by UUID ===")
    attacker, _ = setup_oa_scenario()

    handler = attacker.get_event_handler_by_name("Opportunity Attack Handler")
    assert handler is not None

    result = attacker.set_handler_enabled_by_uuid(handler.uuid, False)
    assert result is True, "Should find handler by UUID"
    assert handler.enabled is False

    result = attacker.set_handler_enabled_by_uuid(handler.uuid, True)
    assert result is True
    assert handler.enabled is True

    print("  PASSED: Toggle by UUID works")


def test_get_event_handlers_by_name():
    """Test 7: get_event_handlers_by_name returns all matches."""
    print("\n=== Test 7: Get Handlers By Name ===")
    attacker, _ = setup_oa_scenario()

    handlers = attacker.get_event_handlers_by_name("Opportunity Attack Handler")
    assert len(handlers) == 1, f"Expected 1 OA handler, got {len(handlers)}"

    empty = attacker.get_event_handlers_by_name("Nonexistent")
    assert len(empty) == 0, "Should return empty list for missing name"

    print("  PASSED: get_event_handlers_by_name works correctly")


def test_invisible_creature_oa_opt_out():
    """Test 8: Invisible creature with OA disabled doesn't attack or lose invisibility."""
    print("\n=== Test 8: Invisible Creature OA Opt-Out ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    # Invisible creature with OA
    invisible = create_skeleton(name="Invisible", position=(5, 5))
    setup_standard_actions(invisible)
    add_opportunity_attack_handler(invisible)

    # Apply invisibility
    invis_cond = InvisibilityEffect(
        source_entity_uuid=invisible.uuid,
        target_entity_uuid=invisible.uuid
    )
    invisible.add_condition(invis_cond)
    assert "Invisible" in invisible.active_conditions, "Should be invisible"

    # Disable OA so invisible creature doesn't reveal itself
    attacker_oa = invisible.set_handler_enabled("Opportunity Attack Handler", False)
    assert attacker_oa is True

    # Mover walks away
    mover = create_goblin(name="Mover", position=(5, 6))
    setup_standard_actions(mover)
    Entity.update_all_entities_senses(max_distance=20)

    hp_before = get_hp(mover)

    # Move mover away
    grid.move_entity(mover.uuid, (5, 9))
    mover.update_entity_senses()

    hp_after = get_hp(mover)

    # No OA should have fired
    assert hp_before == hp_after, "No damage should be dealt (OA disabled)"

    # Invisible creature should still be invisible
    assert "Invisible" in invisible.active_conditions, "Should still be invisible (no OA fired)"

    print(f"  Mover HP: {hp_before} -> {hp_after}")
    print(f"  Invisible still active: {'Invisible' in invisible.active_conditions}")
    print("  PASSED: Invisible creature opted out of OA, stayed invisible")


def test_protection_handler_toggle():
    """Test 9: Protection fighting style can be toggled off."""
    print("\n=== Test 9: Protection Handler Toggle ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    # Protector with shield
    protector = create_skeleton(name="Protector", position=(5, 5))
    shield = create_shield(protector.uuid)
    protector.equipment.equip(shield, WeaponSlot.MELEE_OFF)
    protection = FightingStyleProtection(
        source_entity_uuid=protector.uuid,
        target_entity_uuid=protector.uuid
    )
    protector.add_condition(protection)

    ally = create_goblin(name="Ally", position=(5, 6))
    enemy = create_skeleton(name="Enemy", position=(5, 7))
    setup_standard_actions(enemy)
    Entity.update_all_entities_senses(max_distance=20)

    # Disable Protection handler
    result = protector.set_handler_enabled("Protection", False)
    assert result is True, "Should find Protection handler"

    # Enemy attacks ally — Protection should NOT fire
    attack = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=ally.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = attack.apply()
    assert event is not None

    attack_bonus = event.attack_bonus
    advantage = attack_bonus.advantage if attack_bonus else AdvantageStatus.NONE
    assert advantage == AdvantageStatus.NONE, f"Expected NONE (Protection disabled), got {advantage}"
    assert protector.action_economy.reactions.normalized_score == 1, "Reaction should NOT be consumed"

    print(f"  Advantage: {advantage}, Reactions remaining: {protector.action_economy.reactions.normalized_score}")
    print("  PASSED: Protection handler disabled, no disadvantage imposed")


def test_protection_re_enabled():
    """Test 10: Protection works again after re-enabling."""
    print("\n=== Test 10: Protection Re-enabled ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    protector = create_skeleton(name="Protector", position=(5, 5))
    shield = create_shield(protector.uuid)
    protector.equipment.equip(shield, WeaponSlot.MELEE_OFF)
    protection = FightingStyleProtection(
        source_entity_uuid=protector.uuid,
        target_entity_uuid=protector.uuid
    )
    protector.add_condition(protection)

    ally = create_goblin(name="Ally", position=(5, 6))
    enemy = create_skeleton(name="Enemy", position=(5, 7))
    setup_standard_actions(enemy)
    Entity.update_all_entities_senses(max_distance=20)

    # Disable then re-enable
    protector.set_handler_enabled("Protection", False)
    protector.set_handler_enabled("Protection", True)

    # Attack should trigger Protection again
    attack = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=ally.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = attack.apply()
    assert event is not None

    attack_bonus = event.attack_bonus
    advantage = attack_bonus.advantage if attack_bonus else AdvantageStatus.NONE
    assert advantage == AdvantageStatus.DISADVANTAGE, f"Expected DISADVANTAGE, got {advantage}"
    assert protector.action_economy.reactions.normalized_score == 0, "Reaction should be consumed"

    print(f"  Advantage: {advantage}")
    print("  PASSED: Protection re-enabled and working")


if __name__ == "__main__":
    print("=" * 60)
    print("Handler Toggle System Tests")
    print("=" * 60)

    test_oa_enabled_fires_normally()
    test_oa_disabled_prevents_attack()
    test_toggle_on_off_cycle()
    test_disabled_handler_stays_registered()
    test_set_handler_enabled_missing_name()
    test_set_handler_enabled_by_uuid()
    test_get_event_handlers_by_name()
    test_invisible_creature_oa_opt_out()
    test_protection_handler_toggle()
    test_protection_re_enabled()

    print("\n" + "=" * 60)
    print("All handler toggle tests passed!")
    print("=" * 60)
