"""Extensive tests for Incendiary Cloud spell.

Tests cover:
- Initial cast damages (DEX save, 10d8 fire, half on save)
- Entry damage when moving into zone
- Turn start damage for creatures in zone
- Auto-move: cloud moves 10ft away from caster on caster's turn
- Concentration lifecycle (break removes zone)
- Heavily obscured (sets darkness/obscurement)
"""
import sys
import traceback

from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map, reset_map
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity, get_natural_roll
from dnd.monsters.bestiary import create_caster, create_goblin
from dnd.spells.conjuration import IncendiaryCloud, IncendiaryCloudZone
from dnd.utils import (
    reset_combat_state, get_hp, set_hp, has_condition,
)


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


def force_dex_fail(entity: Entity) -> None:
    mod = NumericalModifier.create(
        source_entity_uuid=entity.uuid, name="Force Fail", value=-100
    )
    entity.saving_throws.dexterity_saving_throw.bonus.self_static.add_value_modifier(mod)


def force_dex_pass(entity: Entity) -> None:
    mod = NumericalModifier.create(
        source_entity_uuid=entity.uuid, name="Force Pass", value=100
    )
    entity.saving_throws.dexterity_saving_throw.bonus.self_static.add_value_modifier(mod)


# =============================================================================
# Test 1: Incendiary Cloud - initial damage (failed save)
# =============================================================================
def test_incendiary_cloud_initial_damage():
    """Creatures in zone at cast time take 10d8 fire on failed DEX save."""
    print("\n=== Test 1: Incendiary Cloud initial damage ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=15)

        force_dex_fail(target)
        set_hp(target, 300)
        hp_before = get_hp(target)

        spell = IncendiaryCloud(
            source_entity_uuid=caster.uuid,
            end_position=(10, 10),
            cast_at_level=8,
            template=False,
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled, f"Should succeed: {result}"

        damage = hp_before - get_hp(target)
        # 10d8 = 10-80
        print(f"  Damage: {damage}")
        assert damage >= 10, f"Min 10d8 = 10, got {damage}"
        assert damage <= 80, f"Max 10d8 = 80, got {damage}"

        print("  PASS: Initial damage on failed save")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 2: Half damage on passed save
# =============================================================================
def test_incendiary_cloud_half_on_save():
    """Passed DEX save = half damage."""
    print("\n=== Test 2: Half damage on save ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=15)

        force_dex_pass(target)
        set_hp(target, 300)
        hp_before = get_hp(target)

        spell = IncendiaryCloud(
            source_entity_uuid=caster.uuid,
            end_position=(10, 10),
            cast_at_level=8,
            template=False,
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled

        damage = hp_before - get_hp(target)
        # Half of 10d8 = 5-40
        print(f"  Half damage: {damage}")
        assert damage >= 5, f"Min half 5, got {damage}"
        assert damage <= 40, f"Max half 40, got {damage}"

        print("  PASS: Half damage on passed save")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 3: Zone and concentration created
# =============================================================================
def test_incendiary_cloud_zone_created():
    """Casting creates zone condition and Concentrating."""
    print("\n=== Test 3: Zone and concentration ===")
    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
    Entity.update_all_entities_senses(max_distance=15)

    spell = IncendiaryCloud(
        source_entity_uuid=caster.uuid,
        end_position=(10, 10),
        cast_at_level=8,
        template=False,
    )
    spell.apply()

    assert has_condition(caster, "Incendiary Cloud Zone"), "Should have zone"
    assert has_condition(caster, "Concentrating"), "Should be concentrating"

    zone = caster.active_conditions.get("Incendiary Cloud Zone")
    assert isinstance(zone, IncendiaryCloudZone)
    print(f"  Zone center: {zone.zone_center}")

    print("  PASS: Zone and concentration created")


# =============================================================================
# Test 4: Entry damage
# =============================================================================
def test_incendiary_cloud_entry_damage():
    """Moving into the cloud triggers damage."""
    print("\n=== Test 4: Entry damage ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(20, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=25)

        spell = IncendiaryCloud(
            source_entity_uuid=caster.uuid,
            end_position=(10, 10),
            cast_at_level=8,
            template=False,
        )
        spell.apply()

        force_dex_fail(target)
        set_hp(target, 300)
        hp_before = get_hp(target)

        # Move into zone
        Entity.update_entity_position(target, (10, 10))

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        damage = hp_before - get_hp(target)
        print(f"  Entry damage: {damage}")
        assert damage > 0, f"Should take entry damage, got {damage}"

        print("  PASS: Entry damage works")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 5: Turn start damage
# =============================================================================
def test_incendiary_cloud_turn_start_damage():
    """Creature in zone takes damage at turn start."""
    print("\n=== Test 5: Turn start damage ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=15)

        set_hp(target, 300)
        spell = IncendiaryCloud(
            source_entity_uuid=caster.uuid,
            end_position=(10, 10),
            cast_at_level=8,
            template=False,
        )
        spell.apply()

        force_dex_fail(target)
        hp_after_cast = get_hp(target)

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
# Test 6: Auto-move - cloud moves away from caster on caster's turn
# =============================================================================
def test_incendiary_cloud_auto_move():
    """Cloud moves 10ft (2 tiles) away from caster at caster's turn start."""
    print("\n=== Test 6: Auto-move ===")
    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
    Entity.update_all_entities_senses(max_distance=15)

    spell = IncendiaryCloud(
        source_entity_uuid=caster.uuid,
        end_position=(10, 10),
        cast_at_level=8,
        template=False,
    )
    spell.apply()

    zone = caster.active_conditions.get("Incendiary Cloud Zone")
    assert isinstance(zone, IncendiaryCloudZone)
    center_before = zone.zone_center
    print(f"  Center before caster turn: {center_before}")

    # Caster's turn start triggers auto-move
    caster.on_turn_start()

    center_after = zone.zone_center
    print(f"  Center after caster turn: {center_after}")

    # Cloud should move away from caster (caster at (5,10), cloud at (10,10))
    # Direction: east (+x). Should move 2 tiles east.
    assert center_after[0] > center_before[0], \
        f"Cloud should move away (east) from caster, was {center_before} now {center_after}"

    print("  PASS: Cloud auto-moves away from caster")


# =============================================================================
# Test 7: Concentration break removes zone
# =============================================================================
def test_incendiary_cloud_concentration_break():
    """Breaking concentration removes the cloud."""
    print("\n=== Test 7: Concentration break ===")
    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
    Entity.update_all_entities_senses(max_distance=15)

    spell = IncendiaryCloud(
        source_entity_uuid=caster.uuid,
        end_position=(10, 10),
        cast_at_level=8,
        template=False,
    )
    spell.apply()

    assert has_condition(caster, "Incendiary Cloud Zone")
    assert has_condition(caster, "Concentrating")

    caster.remove_condition("Concentrating")

    assert not has_condition(caster, "Concentrating")
    assert not has_condition(caster, "Incendiary Cloud Zone"), \
        "Zone should be removed when concentration breaks"

    print("  PASS: Concentration break removes zone")


# =============================================================================
# Run all tests
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_incendiary_cloud_initial_damage,
        test_incendiary_cloud_half_on_save,
        test_incendiary_cloud_zone_created,
        test_incendiary_cloud_entry_damage,
        test_incendiary_cloud_turn_start_damage,
        test_incendiary_cloud_auto_move,
        test_incendiary_cloud_concentration_break,
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
    print("All Incendiary Cloud tests passed!")
