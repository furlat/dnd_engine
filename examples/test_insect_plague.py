"""Extensive tests for Insect Plague spell.

Tests cover:
- Initial cast damages creatures in zone (CON save, 4d10 piercing, half on save)
- Entry damage when moving into zone
- Turn start damage for creatures in zone
- Concentration lifecycle (break removes zone)
- Upcasting adds dice (+1d10 per level above 5th)
- Zone condition and spatial handlers
"""
import sys
import traceback

from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map, reset_map
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity, get_natural_roll
from dnd.monsters.bestiary import create_sorcerer, create_goblin
from dnd.spells.conjuration import InsectPlague, InsectPlagueZone
from dnd.utils import (
    reset_combat_state, get_hp, set_hp, has_condition,
)


def setup_arena(size: int = 20):
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


def force_con_save_fail(entity: Entity) -> None:
    mod = NumericalModifier.create(
        source_entity_uuid=entity.uuid, name="Force Fail", value=-100
    )
    entity.saving_throws.constitution_saving_throw.bonus.self_static.add_value_modifier(mod)


def force_con_save_pass(entity: Entity) -> None:
    mod = NumericalModifier.create(
        source_entity_uuid=entity.uuid, name="Force Pass", value=100
    )
    entity.saving_throws.constitution_saving_throw.bonus.self_static.add_value_modifier(mod)


# =============================================================================
# Test 1: Insect Plague - initial cast damages creatures in zone
# =============================================================================
def test_insect_plague_initial_damage():
    """Creatures in the zone at cast time take 4d10 piercing (CON save, half on save)."""
    print("\n=== Test 1: Insect Plague initial damage ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        # Target at the center of where we'll cast
        target = create_goblin(name="Goblin", position=(10, 5), faction="monsters")
        Entity.update_all_entities_senses(max_distance=15)

        force_con_save_fail(target)
        set_hp(target, 200)
        hp_before = get_hp(target)

        spell = InsectPlague(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=5,
            template=False,
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled, f"Should succeed: {result}"

        damage = hp_before - get_hp(target)
        # 4d10 = 4-40
        print(f"  Initial damage: {damage}")
        assert damage >= 4, f"Min damage 4, got {damage}"
        assert damage <= 40, f"Max damage 40, got {damage}"

        print("  PASS: Initial cast damages creatures in zone")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 2: Insect Plague - zone and concentration created
# =============================================================================
def test_insect_plague_zone_created():
    """Casting creates zone condition on caster and Concentrating."""
    print("\n=== Test 2: Zone and concentration created ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    Entity.update_all_entities_senses(max_distance=15)

    spell = InsectPlague(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=5,
        template=False,
    )
    result = spell.apply()
    assert result is not None and not result.canceled, f"Should succeed: {result}"

    assert has_condition(caster, "Insect Plague Zone"), "Should have zone condition"
    assert has_condition(caster, "Concentrating"), "Should be concentrating"

    zone = caster.active_conditions.get("Insect Plague Zone")
    assert isinstance(zone, InsectPlagueZone)
    print(f"  Zone center: {zone.zone_center}")
    print(f"  Zone positions count: {len(zone.affected_positions)}")
    assert len(zone.affected_positions) > 0, "Zone should have affected positions"

    print("  PASS: Zone and concentration created")


# =============================================================================
# Test 3: Entry damage when moving into zone
# =============================================================================
def test_insect_plague_entry_damage():
    """Moving a creature into the zone triggers entry damage."""
    print("\n=== Test 3: Entry damage ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(18, 5), faction="monsters")
        Entity.update_all_entities_senses(max_distance=20)

        # Cast zone at (10, 5), target is outside
        spell = InsectPlague(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=5,
            template=False,
        )
        spell.apply()

        # Force fail saves for the entry damage
        force_con_save_fail(target)
        set_hp(target, 200)
        hp_before = get_hp(target)

        # Move target INTO the zone
        Entity.update_entity_position(target, (10, 5))

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        damage = hp_before - get_hp(target)
        print(f"  Entry damage: {damage}")
        assert damage > 0, f"Target should take entry damage, got {damage}"
        assert damage <= 40, f"Max 4d10 = 40, got {damage}"

        print("  PASS: Entry damage works")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 4: Turn start damage for creatures in zone
# =============================================================================
def test_insect_plague_turn_start_damage():
    """Creature starting turn in zone takes damage."""
    print("\n=== Test 4: Turn start damage ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 5), faction="monsters")
        Entity.update_all_entities_senses(max_distance=15)

        # Cast with target inside
        set_hp(target, 200)
        spell = InsectPlague(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=5,
            template=False,
        )
        spell.apply()

        # Note initial damage already occurred - record HP after cast
        force_con_save_fail(target)
        hp_after_cast = get_hp(target)
        print(f"  HP after cast: {hp_after_cast}")

        # Trigger turn start
        target.on_turn_start()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        turn_damage = hp_after_cast - get_hp(target)
        print(f"  Turn start damage: {turn_damage}")
        assert turn_damage > 0, f"Should take turn start damage, got {turn_damage}"

        print("  PASS: Turn start damage works")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 5: Half damage on passed save
# =============================================================================
def test_insect_plague_half_on_save():
    """Passed CON save = half damage."""
    print("\n=== Test 5: Half damage on save ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 5), faction="monsters")
        Entity.update_all_entities_senses(max_distance=15)

        force_con_save_pass(target)
        set_hp(target, 200)
        hp_before = get_hp(target)

        spell = InsectPlague(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=5,
            template=False,
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled

        damage = hp_before - get_hp(target)
        # Half of 4d10 = 2-20
        print(f"  Half damage: {damage}")
        assert damage >= 2, f"Min half damage 2, got {damage}"
        assert damage <= 20, f"Max half damage 20, got {damage}"

        print("  PASS: Half damage on passed save")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 6: Concentration break removes zone
# =============================================================================
def test_insect_plague_concentration_break():
    """Breaking concentration removes the zone."""
    print("\n=== Test 6: Concentration break ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    Entity.update_all_entities_senses(max_distance=15)

    spell = InsectPlague(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=5,
        template=False,
    )
    spell.apply()

    assert has_condition(caster, "Insect Plague Zone")
    assert has_condition(caster, "Concentrating")

    # Break concentration
    caster.remove_condition("Concentrating")

    assert not has_condition(caster, "Concentrating"), "Concentrating should be removed"
    assert not has_condition(caster, "Insect Plague Zone"), "Zone should be removed"

    print("  PASS: Concentration break removes zone")


# =============================================================================
# Test 7: Upcasting adds dice
# =============================================================================
def test_insect_plague_upcast():
    """At level 7: 6d10 piercing (base 4 + 2 upcast)."""
    print("\n=== Test 7: Upcasting ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 5), faction="monsters")
        Entity.update_all_entities_senses(max_distance=15)

        force_con_save_fail(target)
        set_hp(target, 300)
        hp_before = get_hp(target)

        # Cast at level 7: 6d10 (4 base + 2 upcast)
        spell = InsectPlague(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=7,
            template=False,
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled

        damage = hp_before - get_hp(target)
        # 6d10 = 6-60
        print(f"  Level 7 damage: {damage}")
        assert damage >= 6, f"Min 6d10 = 6, got {damage}"
        assert damage <= 60, f"Max 6d10 = 60, got {damage}"

        print("  PASS: Upcast adds dice")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 8: Exit zone - no damage on leaving
# =============================================================================
def test_insect_plague_exit_no_damage():
    """Moving OUT of the zone should not trigger additional damage."""
    print("\n=== Test 8: Exit zone - no additional damage ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 5), faction="monsters")
        Entity.update_all_entities_senses(max_distance=15)

        set_hp(target, 300)
        force_con_save_fail(target)

        # Cast - target takes initial damage
        spell = InsectPlague(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=5,
            template=False,
        )
        spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        hp_after_initial = get_hp(target)
        print(f"  HP after initial damage: {hp_after_initial}")

        # Move target OUT of zone (far away)
        Entity.update_entity_position(target, (18, 5))
        hp_after_exit = get_hp(target)
        print(f"  HP after exiting zone: {hp_after_exit}")

        assert hp_after_exit == hp_after_initial, \
            f"Should NOT take damage on exit: {hp_after_initial} -> {hp_after_exit}"

        print("  PASS: No damage on exit")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 9: Re-enter zone triggers new entry damage
# =============================================================================
def test_insect_plague_reenter_damage():
    """Leaving and re-entering the zone triggers entry damage again."""
    print("\n=== Test 9: Re-enter triggers entry damage ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(18, 5), faction="monsters")
        Entity.update_all_entities_senses(max_distance=20)

        # Cast zone - target is outside
        spell = InsectPlague(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=5,
            template=False,
        )
        spell.apply()

        force_con_save_fail(target)
        set_hp(target, 300)

        # Enter zone - takes entry damage
        Entity.update_entity_position(target, (10, 5))
        hp_after_first_entry = get_hp(target)
        first_entry_damage = 300 - hp_after_first_entry
        print(f"  First entry damage: {first_entry_damage}")

        # Exit zone
        Entity.update_entity_position(target, (18, 5))
        hp_after_exit = get_hp(target)

        # Re-enter - should take entry damage again
        Entity.update_entity_position(target, (10, 5))

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        hp_after_reenter = get_hp(target)
        reentry_damage = hp_after_exit - hp_after_reenter
        print(f"  Re-entry damage: {reentry_damage}")

        assert first_entry_damage > 0, "Should take first entry damage"
        assert reentry_damage > 0, "Should take re-entry damage"

        print("  PASS: Re-entry triggers new damage")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 10: Entity present at cast vs moved in - both take damage
# =============================================================================
def test_insect_plague_present_vs_entering():
    """Entity already in zone at cast time AND entity moved in both take damage."""
    print("\n=== Test 10: Present at cast vs entering ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        # Present at cast
        present = create_goblin(name="Present", position=(10, 5), faction="monsters")
        # Will move in later
        outsider = create_goblin(name="Outsider", position=(18, 5), faction="monsters")
        Entity.update_all_entities_senses(max_distance=20)

        for g in [present, outsider]:
            force_con_save_fail(g)
            set_hp(g, 300)

        # Cast - present takes immediate damage
        spell = InsectPlague(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=5,
            template=False,
        )
        spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        present_dmg = 300 - get_hp(present)
        outsider_dmg = 300 - get_hp(outsider)
        print(f"  Present damage at cast: {present_dmg}")
        print(f"  Outsider damage at cast: {outsider_dmg}")
        assert present_dmg > 0, "Present entity should take initial damage"
        assert outsider_dmg == 0, "Outsider should NOT take initial damage"

        # Move outsider in
        Entity.update_entity_position(outsider, (10, 6))
        outsider_entry_dmg = 300 - get_hp(outsider)
        print(f"  Outsider damage after entering: {outsider_entry_dmg}")
        assert outsider_entry_dmg > 0, "Outsider should take entry damage"

        print("  PASS: Present at cast and entering both damaged correctly")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 11: After concentration break, entry no longer damages
# =============================================================================
def test_insect_plague_no_damage_after_removal():
    """After concentration breaks, moving into former zone area does nothing."""
    print("\n=== Test 11: No damage after zone removal ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    target = create_goblin(name="Goblin", position=(18, 5), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    set_hp(target, 200)

    spell = InsectPlague(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=5,
        template=False,
    )
    spell.apply()

    # Break concentration
    caster.remove_condition("Concentrating")
    assert not has_condition(caster, "Insect Plague Zone")

    hp_before_move = get_hp(target)
    # Move target into former zone area
    Entity.update_entity_position(target, (10, 5))
    hp_after_move = get_hp(target)

    assert hp_after_move == hp_before_move, \
        f"Should NOT take damage after zone removed: {hp_before_move} -> {hp_after_move}"

    # Also no turn start damage
    target.on_turn_start()
    hp_after_turn = get_hp(target)
    assert hp_after_turn == hp_before_move, \
        f"Should NOT take turn start damage after zone removed: {hp_before_move} -> {hp_after_turn}"

    print("  PASS: No damage after zone removal")


# =============================================================================
# Run all tests
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_insect_plague_initial_damage,
        test_insect_plague_zone_created,
        test_insect_plague_entry_damage,
        test_insect_plague_turn_start_damage,
        test_insect_plague_half_on_save,
        test_insect_plague_concentration_break,
        test_insect_plague_upcast,
        test_insect_plague_exit_no_damage,
        test_insect_plague_reenter_damage,
        test_insect_plague_present_vs_entering,
        test_insect_plague_no_damage_after_removal,
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
    print("All Insect Plague tests passed!")
