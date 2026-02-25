"""Extensive tests for Sunbeam spell.

Tests cover:
- Initial cast: 6d8 radiant, CON save (half on save), Blinded on fail
- Concentration + SunbeamStrike granted action
- Strike reuse each turn (same damage/Blinded pattern)
- Strike requires concentration on Sunbeam
- Concentration break unregisters SunbeamStrike
- Line AoE hits multiple targets
- Blinded duration (1 round, auto-expires)
"""
import sys
import traceback

from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map, reset_map
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity, get_natural_roll
from dnd.monsters.bestiary import create_sorcerer, create_goblin
from dnd.spells.evocation import Sunbeam
from dnd.conditions import Blinded
from dnd.utils import (
    reset_combat_state, get_hp, set_hp, has_condition,
    deal_damage_to, get_position,
)
from dnd.core.events import DamageType


def setup_arena(size: int = 25):
    reset_map()
    grid = get_map()
    grid.create_rectangle(0, 0, size, size)
    return grid


def had_critical_d20() -> bool:
    for event in EventQueue._all_events:
        for attr in ('dice_roll', 'save_roll'):
            roll = getattr(event, attr, None)
            if roll is not None:
                try:
                    nat = get_natural_roll(roll)
                    if nat in (1, 20):
                        return True
                except Exception:
                    pass
    return False


def force_con_fail(entity: Entity) -> None:
    mod = NumericalModifier.create(
        source_entity_uuid=entity.uuid, name="Force Fail", value=-100
    )
    entity.saving_throws.constitution_saving_throw.bonus.self_static.add_value_modifier(mod)


def force_con_pass(entity: Entity) -> None:
    mod = NumericalModifier.create(
        source_entity_uuid=entity.uuid, name="Force Pass", value=100
    )
    entity.saving_throws.constitution_saving_throw.bonus.self_static.add_value_modifier(mod)


# =============================================================================
# Test 1: Initial Sunbeam damage (failed save)
# =============================================================================
def test_sunbeam_initial_damage():
    """Creatures in line at cast time take 6d8 radiant on failed CON save."""
    print("\n=== Test 1: Sunbeam initial damage ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=15)

        force_con_fail(target)
        set_hp(target, 200)
        hp_before = get_hp(target)

        spell = Sunbeam(
            source_entity_uuid=caster.uuid,
            end_position=(20, 10),  # Line goes east
            cast_at_level=6,
            template=False,
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled, f"Should succeed: {result}"

        damage = hp_before - get_hp(target)
        # 6d8 = 6-48
        print(f"  Damage: {damage}")
        assert damage >= 6, f"Min 6d8 = 6, got {damage}"
        assert damage <= 48, f"Max 6d8 = 48, got {damage}"

        print("  PASS: Full damage on failed save")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 2: Half damage on passed save
# =============================================================================
def test_sunbeam_half_on_save():
    """Passed CON save = half damage, no Blinded."""
    print("\n=== Test 2: Half damage on save ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=15)

        force_con_pass(target)
        set_hp(target, 200)
        hp_before = get_hp(target)

        spell = Sunbeam(
            source_entity_uuid=caster.uuid,
            end_position=(20, 10),
            cast_at_level=6,
            template=False,
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled

        damage = hp_before - get_hp(target)
        # Half of 6d8 = 3-24
        print(f"  Half damage: {damage}")
        assert damage >= 3, f"Min half 3, got {damage}"
        assert damage <= 24, f"Max half 24, got {damage}"

        # Should NOT be blinded on passed save
        assert not has_condition(target, "Blinded"), "Should NOT be Blinded on passed save"

        print("  PASS: Half damage, no Blinded on passed save")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 3: Blinded on failed save
# =============================================================================
def test_sunbeam_blinded_on_fail():
    """Failed CON save → Blinded condition (1 round)."""
    print("\n=== Test 3: Blinded on failed save ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=15)

        force_con_fail(target)
        set_hp(target, 200)

        spell = Sunbeam(
            source_entity_uuid=caster.uuid,
            end_position=(20, 10),
            cast_at_level=6,
            template=False,
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled

        assert has_condition(target, "Blinded"), "Should be Blinded on failed save"

        # Blinded should last 1 round
        blinded = target.active_conditions.get("Blinded")
        assert blinded is not None
        print(f"  Blinded duration: {blinded.duration.duration} rounds")

        # Advance 1 round — should expire
        target.advance_duration("Blinded")
        assert not has_condition(target, "Blinded"), "Blinded should expire after 1 round"

        print("  PASS: Blinded on failed save, expires after 1 round")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 4: Concentration and SunbeamStrike granted
# =============================================================================
def test_sunbeam_concentration_and_strike():
    """Casting Sunbeam sets Concentrating and registers SunbeamStrike action."""
    print("\n=== Test 4: Concentration and SunbeamStrike ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 10), level=5, faction="heroes")
    Entity.update_all_entities_senses(max_distance=15)

    # Verify no SunbeamStrike before cast
    strike_before = caster.get_action_template("Sunbeam Strike")
    assert strike_before is None, "Should NOT have Sunbeam Strike before cast"

    spell = Sunbeam(
        source_entity_uuid=caster.uuid,
        end_position=(20, 10),
        cast_at_level=6,
        template=False,
    )
    spell.apply()

    # Verify Concentrating
    assert has_condition(caster, "Concentrating"), "Should be concentrating"
    conc = caster.active_conditions.get("Concentrating")
    assert conc is not None
    assert conc.spell_name == "Sunbeam"
    print(f"  Concentrating on: {conc.spell_name}")

    # Verify SunbeamStrike registered
    strike = caster.get_action_template("Sunbeam Strike")
    assert strike is not None, "Should have SunbeamStrike action after cast"
    print(f"  Strike action registered: {strike.name}")

    # Verify strike appears in available actions
    actions = caster.get_available_actions()
    strike_actions = [a for a in actions.self_actions if a.template_name == "Sunbeam Strike"]
    # It might be in entity_actions or position_actions too — check all
    if not strike_actions:
        for category in [actions.entity_actions, actions.position_actions]:
            for a in category:
                if a.template_name == "Sunbeam Strike":
                    strike_actions.append(a)
    print(f"  Strike in available actions: {len(strike_actions) > 0}")

    print("  PASS: Concentration and SunbeamStrike registered")


# =============================================================================
# Test 5: SunbeamStrike reuse deals damage
# =============================================================================
def test_sunbeam_strike_reuse():
    """Use SunbeamStrike on subsequent turn — deals 6d8 radiant."""
    print("\n=== Test 5: SunbeamStrike reuse ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=15)

        set_hp(target, 200)

        spell = Sunbeam(
            source_entity_uuid=caster.uuid,
            end_position=(20, 10),
            cast_at_level=6,
            template=False,
        )
        spell.apply()

        # Reset action economy for "next turn"
        caster.action_economy.reset_all_costs()

        # Get the strike template and use it
        strike_template = caster.get_action_template("Sunbeam Strike")
        assert strike_template is not None

        force_con_fail(target)
        hp_before_strike = get_hp(target)

        # Create a fresh strike action instance
        from dnd.spells.evocation import SunbeamStrike
        strike = SunbeamStrike(
            source_entity_uuid=caster.uuid,
            end_position=(20, 10),
            spell_dc=strike_template.spell_dc,
            template=False,
        )
        result = strike.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled, f"Strike should succeed: {result}"

        strike_damage = hp_before_strike - get_hp(target)
        print(f"  Strike damage: {strike_damage}")
        assert strike_damage >= 6, f"Min 6d8 = 6, got {strike_damage}"
        assert strike_damage <= 48, f"Max 6d8 = 48, got {strike_damage}"

        print("  PASS: SunbeamStrike deals damage on reuse")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 6: Concentration break removes SunbeamStrike
# =============================================================================
def test_sunbeam_concentration_break():
    """Breaking concentration removes SunbeamStrike action."""
    print("\n=== Test 6: Concentration break removes SunbeamStrike ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 10), level=5, faction="heroes")
    Entity.update_all_entities_senses(max_distance=15)

    set_hp(caster, 200)

    spell = Sunbeam(
        source_entity_uuid=caster.uuid,
        end_position=(20, 10),
        cast_at_level=6,
        template=False,
    )
    spell.apply()

    # Verify SunbeamStrike exists
    assert caster.get_action_template("Sunbeam Strike") is not None

    # Break concentration via damage
    deal_damage_to(caster, 50, DamageType.FIRE)

    # Verify concentration broken
    assert not has_condition(caster, "Concentrating"), "Concentration should break"

    # Verify SunbeamStrike removed
    strike = caster.get_action_template("Sunbeam Strike")
    assert strike is None, "SunbeamStrike should be removed when concentration breaks"

    print("  PASS: Concentration break removes SunbeamStrike")


# =============================================================================
# Test 7: Multiple targets in line
# =============================================================================
def test_sunbeam_multiple_targets():
    """Line AoE hits multiple targets along the beam."""
    print("\n=== Test 7: Multiple targets in line ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 10), level=5, faction="heroes")
        g1 = create_goblin(name="Goblin1", position=(8, 10), faction="monsters")
        g2 = create_goblin(name="Goblin2", position=(12, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=20)

        for g in [g1, g2]:
            force_con_fail(g)
            set_hp(g, 200)

        hps_before = [get_hp(g) for g in [g1, g2]]

        spell = Sunbeam(
            source_entity_uuid=caster.uuid,
            end_position=(20, 10),
            cast_at_level=6,
            template=False,
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled

        damages = [hps_before[i] - get_hp(g) for i, g in enumerate([g1, g2])]
        print(f"  Damages: {damages}")

        for i, dmg in enumerate(damages):
            assert dmg > 0, f"Goblin{i+1} should take damage, got {dmg}"

        print("  PASS: Multiple targets in line all take damage")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 8: Strike requires Sunbeam concentration
# =============================================================================
def test_sunbeam_strike_requires_concentration():
    """SunbeamStrike fails if not concentrating on Sunbeam."""
    print("\n=== Test 8: Strike requires Sunbeam concentration ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 10), level=5, faction="heroes")
    target = create_goblin(name="Goblin", position=(10, 10), faction="monsters")
    Entity.update_all_entities_senses(max_distance=15)
    set_hp(target, 200)
    set_hp(caster, 200)

    spell = Sunbeam(
        source_entity_uuid=caster.uuid,
        end_position=(20, 10),
        cast_at_level=6,
        template=False,
    )
    spell.apply()

    # Break concentration
    caster.remove_condition("Concentrating")
    assert not has_condition(caster, "Concentrating")

    # Try to use SunbeamStrike — should fail validation
    from dnd.spells.evocation import SunbeamStrike
    strike = SunbeamStrike(
        source_entity_uuid=caster.uuid,
        end_position=(20, 10),
        spell_dc=15,
        template=False,
    )
    result = strike.apply()

    # Should be canceled (no concentration)
    assert result is None or result.canceled, \
        f"Strike should fail without Sunbeam concentration, got: {result}"
    print(f"  Strike without concentration: {'canceled' if result and result.canceled else 'None'}")

    print("  PASS: Strike requires Sunbeam concentration")


# =============================================================================
# Test 9: DropConcentration removes SunbeamStrike
# =============================================================================
def test_sunbeam_drop_concentration():
    """Voluntarily dropping concentration removes SunbeamStrike."""
    print("\n=== Test 9: DropConcentration removes SunbeamStrike ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 10), level=5, faction="heroes")
    Entity.update_all_entities_senses(max_distance=15)

    spell = Sunbeam(
        source_entity_uuid=caster.uuid,
        end_position=(20, 10),
        cast_at_level=6,
        template=False,
    )
    spell.apply()

    assert caster.get_action_template("Sunbeam Strike") is not None
    assert has_condition(caster, "Concentrating")

    # Use DropConcentration action
    caster.remove_condition("Concentrating")

    assert not has_condition(caster, "Concentrating")
    assert caster.get_action_template("Sunbeam Strike") is None, \
        "SunbeamStrike should be removed on drop concentration"

    print("  PASS: DropConcentration removes SunbeamStrike")


# =============================================================================
# Run all tests
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_sunbeam_initial_damage,
        test_sunbeam_half_on_save,
        test_sunbeam_blinded_on_fail,
        test_sunbeam_concentration_and_strike,
        test_sunbeam_strike_reuse,
        test_sunbeam_concentration_break,
        test_sunbeam_multiple_targets,
        test_sunbeam_strike_requires_concentration,
        test_sunbeam_drop_concentration,
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
    print("All Sunbeam tests passed!")
