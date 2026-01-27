"""
Test Frenzy Rage Maintenance - Barbarian vs Skeleton

Reproduces the bug where rage disappears after attacking when using Frenzy.
"""

from dnd.entity import Entity
from dnd.core.events import EventQueue
from dnd.monsters.bestiary import create_skeleton
from dnd.classes.barbarian_factory import create_barbarian, BarbarianConfig, PrimalPathChoice
from dnd.actions_functional import get_available_actions, execute_action

def test_frenzy_maintenance():
    """
    Test scenario:
    1. Create L3+ Berserker barbarian (has FrenzyFeature)
    2. Create skeleton target
    3. Barbarian uses Frenzy action
    4. Barbarian attacks skeleton
    5. End turn
    6. Start new turn
    7. Check: Does barbarian still have Raging and Frenzied?
    """
    print("\n=== Test: Frenzy Rage Maintenance ===")

    # Clear state
    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    # Create combatants - L5 Berserker barbarian
    config = BarbarianConfig(
        name="Test Barbarian",
        level=5,
        primal_path=PrimalPathChoice.BERSERKER,
        position=(0, 0),
        asi_4=[("strength", 2)]  # Required for level 5
    )
    barbarian = create_barbarian(config)
    _skeleton = create_skeleton(name="Target Skeleton", position=(1, 0))

    Entity.update_all_entities_senses()

    # Debug: Show initial conditions
    print(f"  Initial conditions: {list(barbarian.active_conditions.keys())}")
    print(f"  Has FrenzyFeature: {'FrenzyFeature' in barbarian.active_conditions}")
    print(f"  Has RageFeature: {'RageFeature' in barbarian.active_conditions}")

    # Step 1: Use Frenzy action
    available = get_available_actions(barbarian)
    print(f"  Available actions: {[a.template_name for a in available.self_actions]}")

    frenzy_action = next((a for a in available.self_actions if a.template_name == "Frenzy"), None)
    if not frenzy_action:
        print("  ERROR: Frenzy action not available!")
        return False

    result = execute_action(barbarian, "Frenzy", barbarian.uuid)
    print(f"  Frenzy result: {result.status_message if result else 'Failed'}")

    # Check conditions after Frenzy
    print(f"  After Frenzy conditions: {list(barbarian.active_conditions.keys())}")
    has_raging = "Raging" in barbarian.active_conditions
    has_frenzied = "Frenzied" in barbarian.active_conditions
    print(f"  Raging: {has_raging}, Frenzied: {has_frenzied}")

    if not has_raging or not has_frenzied:
        print("  ERROR: Frenzy did not apply both conditions!")
        return False

    # Debug: Check registered handlers
    from dnd.core.base_object import BaseObject
    handlers = [BaseObject.get(h) for h in barbarian.event_handlers]
    print(f"  Registered handlers: {[h.name for h in handlers if h]}")
    rage_attack_handler = next((h for h in handlers if h and "Rage Attack" in h.name), None)
    print(f"  Rage Attack Tracker handler present: {rage_attack_handler is not None}")

    # Step 2: Attack skeleton
    available = get_available_actions(barbarian)
    attack_info = next((a for a in available.entity_actions if "Attack" in a.template_name), None)
    if not attack_info or not attack_info.valid_targets:
        print("  ERROR: No attack action available!")
        return False

    result = execute_action(barbarian, attack_info.template_name, attack_info.valid_targets[0])
    print(f"  Attack result: {result.status_message if result else 'Failed/Missed'}")

    # Check for KeepRage marker
    print(f"  After attack conditions: {list(barbarian.active_conditions.keys())}")
    has_keep_rage = "KeepRage" in barbarian.active_conditions
    has_has_attacked = "HasAttacked" in barbarian.active_conditions
    print(f"  KeepRage: {has_keep_rage}, HasAttacked: {has_has_attacked}")

    if not has_keep_rage:
        print("  BUG FOUND: KeepRage marker NOT applied after attacking!")
        print("  This is why rage ends - the rage_attack_tracker handler isn't working")

    # Step 3: End turn
    print("\n  --- Ending turn ---")
    turn_end_event = barbarian.on_turn_end()
    print(f"  Turn end: {turn_end_event.status_message if turn_end_event else 'No event'}")

    # Check conditions after turn end
    print(f"  After turn end conditions: {list(barbarian.active_conditions.keys())}")
    still_raging = "Raging" in barbarian.active_conditions
    still_frenzied = "Frenzied" in barbarian.active_conditions
    print(f"  Still Raging: {still_raging}, Still Frenzied: {still_frenzied}")

    # Step 4: Start new turn
    print("\n  --- Starting new turn ---")
    _turn_start_event = barbarian.on_turn_start()

    # Final state
    print(f"  After turn start conditions: {list(barbarian.active_conditions.keys())}")
    final_raging = "Raging" in barbarian.active_conditions
    final_frenzied = "Frenzied" in barbarian.active_conditions
    print(f"  Final Raging: {final_raging}, Final Frenzied: {final_frenzied}")

    # Verdict
    if final_raging and final_frenzied:
        print("\n  ✓ PASS: Rage maintained after attacking")
        return True
    else:
        print("\n  ✗ FAIL: Rage ended despite attacking!")
        return False


if __name__ == "__main__":
    test_frenzy_maintenance()
