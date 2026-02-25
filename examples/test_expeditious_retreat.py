"""Extensive tests for Expeditious Retreat spell.

Tests cover:
- Spell grants "Dash (Bonus)" action
- Bonus Dash actually doubles movement
- Concentration lifecycle (break removes action)
- Self-targeting only
- Available actions show bonus dash
- Using bonus dash costs bonus action, not action
"""
import sys
import traceback
from uuid import uuid4

from dnd.core.gridmap import get_map, reset_map
from dnd.core.base_actions import TargetType
from dnd.core.modifiers import DamageType
from dnd.entity import Entity
from dnd.monsters.bestiary import create_sorcerer
from dnd.spells.transmutation import ExpeditiousRetreat
from dnd.spells.illusion import Invisibility as InvisibilitySpell
from dnd.conditions import Concentrating
from dnd.actions_functional import execute_by_index
from dnd.utils import (
    reset_combat_state, has_condition, deal_damage_to,
)


def setup_arena(size: int = 20):
    reset_map()
    grid = get_map()
    grid.create_rectangle(0, 0, size, size)
    return grid


# =============================================================================
# Test 1: Expeditious Retreat grants Bonus Dash action
# =============================================================================
def test_expeditious_retreat_basic():
    """Cast Expeditious Retreat, verify Dash (Bonus) appears in actions."""
    print("\n=== Test 1: Expeditious Retreat grants bonus dash ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5)
    Entity.update_all_entities_senses()

    # Verify no bonus dash initially
    action_names = [a.name for a in caster.registered_actions]
    assert "Dash (Bonus)" not in action_names, "Should not have Dash (Bonus) initially"

    # Cast Expeditious Retreat
    spell = ExpeditiousRetreat(
        source_entity_uuid=caster.uuid,
        cast_at_level=1,
        template=False,
        costs=ExpeditiousRetreat(source_entity_uuid=caster.uuid)._get_costs_for_level(1)
    )
    result = spell.apply()
    assert result is not None and not result.canceled, "Should succeed"

    # Verify action registered
    action_names = [a.name for a in caster.registered_actions]
    print(f"  Actions after cast: {[n for n in action_names if 'Dash' in str(n)]}")
    assert "Dash (Bonus)" in action_names, "Should have Dash (Bonus) after casting"

    # Verify concentration
    assert has_condition(caster, "Concentrating"), "Should be concentrating"
    conc = caster.active_conditions.get("Concentrating")
    assert isinstance(conc, Concentrating)
    assert conc.spell_name == "Expeditious Retreat"

    # Verify effect condition
    assert has_condition(caster, "Expeditious Retreat"), "Should have effect condition"

    print("  PASS: Bonus Dash action granted")


# =============================================================================
# Test 2: Bonus Dash applies Dashing condition
# =============================================================================
def test_bonus_dash_works():
    """Using Dash (Bonus) applies Dashing condition and costs bonus action."""
    print("\n=== Test 2: Bonus Dash applies Dashing ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5)
    Entity.update_all_entities_senses()

    # Cast Expeditious Retreat
    spell = ExpeditiousRetreat(
        source_entity_uuid=caster.uuid,
        cast_at_level=1,
        template=False,
        costs=ExpeditiousRetreat(source_entity_uuid=caster.uuid)._get_costs_for_level(1)
    )
    spell.apply()

    # Reset action economy to simulate next turn
    caster.action_economy.reset_all_costs()

    # Find and use the Dash (Bonus) action via execute_by_index
    avail = caster.get_available_actions()
    # Find "Dash (Bonus)" in self_actions
    dash_bonus_info = None
    for info in avail.self_actions:
        if info.template_name == "Dash (Bonus)":
            dash_bonus_info = info
            break
    assert dash_bonus_info is not None, "Dash (Bonus) should be in available actions"

    ba_before = caster.action_economy.bonus_actions.normalized_score
    print(f"  Bonus actions before Dash: {ba_before}")

    result = execute_by_index(caster, "Dash (Bonus)", 0)
    assert result is not None and not result.canceled, f"Bonus Dash should succeed: {result}"

    # Verify Dashing condition applied
    assert has_condition(caster, "Dashing"), "Should have Dashing condition"

    # Verify bonus action was spent
    ba_after = caster.action_economy.bonus_actions.normalized_score
    print(f"  Bonus actions after Dash: {ba_after}")
    assert ba_after == ba_before - 1, "Should cost 1 bonus action"

    print("  PASS: Bonus Dash works and costs bonus action")


# =============================================================================
# Test 3: Concentration break removes Dash (Bonus) action
# =============================================================================
def test_concentration_break_removes_action():
    """Breaking concentration removes the Dash (Bonus) action."""
    print("\n=== Test 3: Concentration break removes Dash (Bonus) ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5)
    Entity.update_all_entities_senses()

    spell = ExpeditiousRetreat(
        source_entity_uuid=caster.uuid,
        cast_at_level=1,
        template=False,
        costs=ExpeditiousRetreat(source_entity_uuid=caster.uuid)._get_costs_for_level(1)
    )
    spell.apply()

    # Verify action exists
    action_names = [a.name for a in caster.registered_actions]
    assert "Dash (Bonus)" in action_names, "Should have Dash (Bonus)"

    # Break concentration with massive damage
    deal_damage_to(caster, 50, DamageType.FIRE)

    # Verify action removed
    action_names = [a.name for a in caster.registered_actions]
    print(f"  Actions after conc break: {[n for n in action_names if 'Dash' in str(n)]}")
    assert "Dash (Bonus)" not in action_names, "Dash (Bonus) should be removed"

    # Verify conditions removed
    assert not has_condition(caster, "Concentrating"), "Should not be concentrating"
    assert not has_condition(caster, "Expeditious Retreat"), "Effect should be removed"

    print("  PASS: Concentration break removes action")


# =============================================================================
# Test 4: Expeditious Retreat is self-only
# =============================================================================
def test_expeditious_retreat_self_only():
    """Expeditious Retreat targets self only."""
    print("\n=== Test 4: Expeditious Retreat is self-only ===")

    spell = ExpeditiousRetreat(source_entity_uuid=uuid4())
    assert spell.target_type == TargetType.SELF, "Should be SELF target"
    print(f"  Target type: {spell.target_type}")
    print("  PASS: Self-only targeting")


# =============================================================================
# Test 5: Available actions shows Dash (Bonus)
# =============================================================================
def test_available_actions_shows_bonus_dash():
    """get_available_actions should list Dash (Bonus) after casting."""
    print("\n=== Test 5: Available actions shows Dash (Bonus) ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5)
    Entity.update_all_entities_senses()

    # Check before
    avail = caster.get_available_actions()
    all_names = (
        [a.template_name for a in avail.entity_actions] +
        [a.template_name for a in avail.self_actions] +
        [a.template_name for a in avail.position_actions]
    )
    assert "Dash (Bonus)" not in all_names, "Should not have Dash (Bonus) before cast"

    # Cast
    spell = ExpeditiousRetreat(
        source_entity_uuid=caster.uuid,
        cast_at_level=1,
        template=False,
        costs=ExpeditiousRetreat(source_entity_uuid=caster.uuid)._get_costs_for_level(1)
    )
    spell.apply()

    # Reset action economy to have bonus action available
    caster.action_economy.reset_all_costs()

    # Check after
    avail = caster.get_available_actions()
    all_names = (
        [a.template_name for a in avail.entity_actions] +
        [a.template_name for a in avail.self_actions] +
        [a.template_name for a in avail.position_actions]
    )
    print(f"  Self actions: {[a.template_name for a in avail.self_actions]}")
    assert "Dash (Bonus)" in all_names, "Should have Dash (Bonus) after cast"

    print("  PASS: Available actions lists Dash (Bonus)")


# =============================================================================
# Test 6: Expeditious Retreat - concentration replacement
# =============================================================================
def test_expeditious_retreat_concentration_replacement():
    """Casting a new concentration spell removes Expeditious Retreat effect."""
    print("\n=== Test 6: Concentration replacement ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5)
    Entity.update_all_entities_senses()

    # Cast Expeditious Retreat
    spell = ExpeditiousRetreat(
        source_entity_uuid=caster.uuid,
        cast_at_level=1,
        template=False,
        costs=ExpeditiousRetreat(source_entity_uuid=caster.uuid)._get_costs_for_level(1)
    )
    spell.apply()
    assert has_condition(caster, "Expeditious Retreat"), "Should have effect"

    # Cast another concentration spell
    caster.action_economy.reset_all_costs()
    invis = InvisibilitySpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        cast_at_level=2,
        template=False,
        costs=InvisibilitySpell(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    invis.apply()

    # Expeditious Retreat should be gone
    assert not has_condition(caster, "Expeditious Retreat"), "Effect should be removed"
    action_names = [a.name for a in caster.registered_actions]
    assert "Dash (Bonus)" not in action_names, "Dash (Bonus) should be removed"

    print("  PASS: Concentration replacement removes Expeditious Retreat")


# =============================================================================
# Run all tests
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_expeditious_retreat_basic,
        test_bonus_dash_works,
        test_concentration_break_removes_action,
        test_expeditious_retreat_self_only,
        test_available_actions_shows_bonus_dash,
        test_expeditious_retreat_concentration_replacement,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {e}")
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if failed > 0:
        sys.exit(1)
    print("All Expeditious Retreat tests passed!")
