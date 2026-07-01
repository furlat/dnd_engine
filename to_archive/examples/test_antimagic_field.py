#!/usr/bin/env python
"""
Test Antimagic Field spell (8th-level Abjuration, Concentration).

Tests:
1. Zone basics - created centered on caster, positions correct
2. Spell blocking - spells from outside targeting inside zone are blocked
3. Suppression - existing magical conditions suppressed on cast
4. Restoration - suppressed conditions restored when AMF ends
5. Entry/exit - suppress on entry, restore on exit
6. Caster self-effects - caster's own magical conditions suppressed
7. Zone movement - follows caster, suppress/unsuppress deltas
8. Concentration spell suppression - parent_link preserved
9. Haste no lethargy on suppression
10. Non-magical conditions unaffected
11. Concentrating not suppressed
12. Multiple conditions suppressed and restored
"""

from dnd.utils import reset_combat_state, has_condition
from dnd.monsters.bestiary import create_goblin, create_caster
from dnd.entity import Entity
from dnd.spells.abjuration import AntimagicField, AntimagicFieldZone
from dnd.spells.enchantment import BlessEffect
from dnd.spells.transmutation import Haste
from dnd.spells.evocation import FireBolt
from dnd.conditions import Poisoned, Frightened, Blinded
from dnd.core.base_conditions import ConditionTag
from dnd.core.gridmap import get_map, reset_map


def setup_arena(size: int = 30):
    """Set up a simple floor arena for testing."""
    reset_map()
    grid = get_map()
    for x in range(size):
        for y in range(size):
            grid.set_tile(x, y, walkable=True, name="Floor")
    return grid


# =============================================================================
# 1. Zone Basics
# =============================================================================

def test_zone_creation():
    """Test that AMF creates a zone centered on caster."""
    print("=" * 60)
    print("TEST: Zone Creation")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(10, 10), faction="heroes")
    caster.update_entity_senses(max_distance=30)

    spell = AntimagicField(source_entity_uuid=caster.uuid)
    result = spell.apply()

    assert result is not None, "Spell should succeed"
    assert not result.canceled, f"Spell should not be canceled: {result.status_message}"

    # Check concentration
    assert has_condition(caster, "Concentrating"), "Should be concentrating"
    assert has_condition(caster, "Antimagic Field Zone"), "Should have zone condition"

    # Check zone positions include caster position
    zone = caster.active_conditions["Antimagic Field Zone"]
    assert isinstance(zone, AntimagicFieldZone)
    assert (10, 10) in zone.affected_positions, "Caster position should be in zone"

    # 10ft radius = 2 tiles. Check a nearby position is in zone
    assert (11, 10) in zone.affected_positions, "(11,10) should be in zone (5ft away)"
    assert (12, 10) in zone.affected_positions, "(12,10) should be in zone (10ft away)"

    # Check a far position is NOT in zone
    assert (15, 10) not in zone.affected_positions, "(15,10) should be outside zone"

    print("   PASSED: Zone created correctly")


# =============================================================================
# 2. Spell Blocking
# =============================================================================

def test_spell_blocked_targeting_inside_zone():
    """Test that spells targeting inside the zone from outside are blocked."""
    print("=" * 60)
    print("TEST: Spell Blocked Targeting Inside Zone")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # AMF caster at center, enemy caster far away
    amf_caster = create_caster(name="Wizard", position=(10, 10), faction="heroes")
    enemy_caster = create_caster(name="Enemy Mage", position=(20, 10), faction="enemies")
    target = create_goblin(name="Goblin", position=(11, 10), faction="heroes")  # Inside AMF zone
    Entity.update_all_entities_senses()

    # Cast AMF
    amf = AntimagicField(source_entity_uuid=amf_caster.uuid)
    amf.apply()

    # Enemy tries to cast Fire Bolt at target inside zone
    firebolt = FireBolt(
        source_entity_uuid=enemy_caster.uuid,
        target_entity_uuid=target.uuid,
    )
    result = firebolt.apply()

    assert result is not None
    assert result.canceled, "Fire Bolt targeting inside AMF should be canceled"
    print(f"   Spell blocked: {result.status_message}")
    print("   PASSED: Spells targeting inside zone are blocked")


def test_spell_blocked_from_inside_zone():
    """Test that spells cast from inside the zone are blocked.

    Uses a separate enemy caster inside the zone (not the AMF caster,
    who already used their action for AMF).
    """
    print("=" * 60)
    print("TEST: Spell Blocked From Inside Zone")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    amf_caster = create_caster(name="Wizard", position=(10, 10), faction="heroes")
    inside_caster = create_caster(name="Inner Mage", position=(11, 10), faction="enemies")
    target = create_goblin(name="Goblin", position=(20, 10), faction="enemies")
    Entity.update_all_entities_senses()

    # Cast AMF
    amf = AntimagicField(source_entity_uuid=amf_caster.uuid)
    amf.apply()

    # Inner caster tries Fire Bolt from inside zone
    firebolt = FireBolt(
        source_entity_uuid=inside_caster.uuid,
        target_entity_uuid=target.uuid,
    )
    result = firebolt.apply()

    assert result is not None
    assert result.canceled, "Fire Bolt from inside AMF should be canceled"
    print(f"   Spell blocked: {result.status_message}")
    print("   PASSED: Spells from inside zone are blocked")


# =============================================================================
# 3. Suppression and Restoration
# =============================================================================

def test_suppress_existing_conditions_on_cast():
    """Test that existing magical conditions are suppressed when AMF is cast."""
    print("=" * 60)
    print("TEST: Suppress Existing Conditions On Cast")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(10, 10), faction="heroes")
    target = create_goblin(name="Goblin", position=(11, 10), faction="enemies")
    Entity.update_all_entities_senses()

    # Apply Blinded with magical tag to target
    blinded = Blinded(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        tags={ConditionTag.MAGICAL}
    )
    target.add_condition(blinded)
    assert has_condition(target, "Blinded"), "Should have Blinded before AMF"

    # Cast AMF
    amf = AntimagicField(source_entity_uuid=caster.uuid)
    amf.apply()

    # Blinded should be suppressed (removed)
    assert not has_condition(target, "Blinded"), "Blinded should be suppressed"
    # Should have suppression marker (unique name includes condition name)
    assert has_condition(target, "Antimagic Suppression: Blinded"), "Should have suppression marker"

    print("   PASSED: Existing magical conditions suppressed")


def test_restore_conditions_on_amf_end():
    """Test that suppressed conditions are restored when AMF concentration breaks."""
    print("=" * 60)
    print("TEST: Restore Conditions On AMF End")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(10, 10), faction="heroes")
    target = create_goblin(name="Goblin", position=(11, 10), faction="enemies")
    Entity.update_all_entities_senses()

    # Apply magical Blinded to target
    blinded = Blinded(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        tags={ConditionTag.MAGICAL}
    )
    target.add_condition(blinded)
    assert has_condition(target, "Blinded")

    # Cast AMF → suppresses Blinded
    amf = AntimagicField(source_entity_uuid=caster.uuid)
    amf.apply()
    assert not has_condition(target, "Blinded")

    # Break concentration → should restore Blinded
    caster.remove_condition("Concentrating")
    assert not has_condition(caster, "Concentrating"), "Concentration should be broken"
    assert not has_condition(caster, "Antimagic Field Zone"), "Zone should be removed"
    assert has_condition(target, "Blinded"), "Blinded should be restored after AMF ends"

    print("   PASSED: Conditions restored on AMF end")


def test_suppress_on_entry_restore_on_exit():
    """Test that conditions are suppressed when entering and restored when leaving."""
    print("=" * 60)
    print("TEST: Suppress On Entry, Restore On Exit")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(10, 10), faction="heroes")
    target = create_goblin(name="Goblin", position=(20, 10), faction="enemies")  # Far away
    Entity.update_all_entities_senses()

    # Apply magical Blinded to target while outside zone
    blinded = Blinded(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        tags={ConditionTag.MAGICAL}
    )
    target.add_condition(blinded)
    assert has_condition(target, "Blinded")

    # Cast AMF (target is outside)
    amf = AntimagicField(source_entity_uuid=caster.uuid)
    amf.apply()
    assert has_condition(target, "Blinded"), "Target outside zone should keep conditions"

    # Move target into zone
    grid = get_map()
    grid.move_entity(target.uuid, (11, 10))
    Entity.update_all_entities_senses()
    assert not has_condition(target, "Blinded"), "Blinded should be suppressed on entry"

    # Move target back out
    grid.move_entity(target.uuid, (20, 10))
    Entity.update_all_entities_senses()
    assert has_condition(target, "Blinded"), "Blinded should be restored on exit"

    print("   PASSED: Suppress on entry, restore on exit")


# =============================================================================
# 4. Caster Self-Effects
# =============================================================================

def test_caster_magical_conditions_suppressed():
    """Test that caster's own magical conditions are suppressed."""
    print("=" * 60)
    print("TEST: Caster Magical Conditions Suppressed")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(10, 10), faction="heroes")
    ally_caster = create_caster(name="Ally Mage", position=(20, 10), faction="heroes")
    Entity.update_all_entities_senses()

    # Ally casts Bless on wizard (magical condition)
    bless_effect = BlessEffect(
        source_entity_uuid=ally_caster.uuid,
        target_entity_uuid=caster.uuid,
        tags={ConditionTag.MAGICAL}
    )
    caster.add_condition(bless_effect)
    assert has_condition(caster, "Bless"), "Caster should have Bless"

    # Wizard casts AMF → Bless should be suppressed on self
    amf = AntimagicField(source_entity_uuid=caster.uuid)
    amf.apply()

    assert not has_condition(caster, "Bless"), "Caster's Bless should be suppressed"
    print("   PASSED: Caster's magical conditions suppressed")


# =============================================================================
# 5. Zone Movement (Follow Caster)
# =============================================================================

def test_zone_follows_caster():
    """Test that zone follows caster and updates suppressions."""
    print("=" * 60)
    print("TEST: Zone Follows Caster")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(10, 10), faction="heroes")
    target = create_goblin(name="Goblin", position=(11, 10), faction="enemies")
    Entity.update_all_entities_senses()

    # Apply magical Blinded to target
    blinded = Blinded(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        tags={ConditionTag.MAGICAL}
    )
    target.add_condition(blinded)

    # Cast AMF → suppresses target's Blinded (target at 11,10 is inside zone)
    amf = AntimagicField(source_entity_uuid=caster.uuid)
    amf.apply()
    assert not has_condition(target, "Blinded"), "Blinded should be suppressed"

    # Move caster FAR away so target is clearly outside the new zone
    grid = get_map()
    grid.move_entity(caster.uuid, (25, 10))
    Entity.update_all_entities_senses()

    # Target at (11,10) should now be outside zone centered at (25,10)
    zone = caster.active_conditions.get("Antimagic Field Zone")
    assert isinstance(zone, AntimagicFieldZone)
    assert (11, 10) not in zone.affected_positions, "Old position should be outside new zone"
    assert has_condition(target, "Blinded"), "Blinded should be restored when zone moves away"

    print("   PASSED: Zone follows caster")


# =============================================================================
# 6. Complex Scenarios
# =============================================================================

def test_concentration_spell_suppressed_and_restored():
    """Test that a concentration spell effect is suppressed and restored correctly.

    When AMF suppresses a linked spell effect, the Concentrating condition
    on the caster should NOT break. When AMF ends, the effect should restore
    and re-link to Concentrating.

    Uses Haste (no save, always applies) for deterministic testing.
    """
    print("=" * 60)
    print("TEST: Concentration Spell Suppressed And Restored")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # AMF caster far away, haste caster close to target
    amf_caster = create_caster(name="AMF Wizard", position=(10, 10), faction="heroes")
    # Haste caster outside AMF zone, but target inside
    haste_caster = create_caster(name="Haste Mage", position=(15, 10), faction="heroes")
    # Target inside AMF zone (within 10ft of amf_caster at 10,10)
    target = create_caster(name="Fighter", position=(11, 10), faction="heroes")
    Entity.update_all_entities_senses()

    # Haste caster casts Haste on target (no save, always applies)
    haste = Haste(
        source_entity_uuid=haste_caster.uuid,
        target_entity_uuid=target.uuid,
    )
    haste.apply()

    assert has_condition(target, "Haste"), "Target should have Haste"
    assert has_condition(haste_caster, "Concentrating"), "Haste caster should be concentrating"
    print(f"   Pre-AMF: Hasted={has_condition(target, 'Haste')}, Concentrating={has_condition(haste_caster, 'Concentrating')}")

    # Cast AMF (target at 11,10 is inside zone centered at 10,10)
    amf = AntimagicField(source_entity_uuid=amf_caster.uuid)
    amf.apply()

    # Target's Hasted should be suppressed
    assert not has_condition(target, "Haste"), "Hasted should be suppressed"
    # Haste caster should STILL be concentrating (parent_link was detached)
    assert has_condition(haste_caster, "Concentrating"), \
        "Haste caster should still concentrate (parent_link detached)"

    # Break AMF concentration → restore suppressed conditions
    amf_caster.remove_condition("Concentrating")

    # Target should get Hasted back
    assert has_condition(target, "Haste"), "Hasted should be restored after AMF ends"
    print(f"   After AMF ends: Hasted={has_condition(target, 'Haste')}")

    # Haste caster should still be concentrating with restored link
    assert has_condition(haste_caster, "Concentrating"), "Haste caster should still concentrate"

    print("   PASSED: Concentration spell suppressed and restored")


def test_haste_no_lethargy_on_suppression():
    """Test that HasteEffect does not apply lethargy when suppressed by AMF."""
    print("=" * 60)
    print("TEST: Haste No Lethargy On Suppression")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    amf_caster = create_caster(name="AMF Wizard", position=(10, 10), faction="heroes")
    # Haste caster close to target (Haste is 30ft range)
    haste_caster = create_caster(name="Haste Mage", position=(15, 10), faction="heroes")
    # Target inside AMF zone
    target = create_goblin(name="Fighter", position=(11, 10), faction="heroes")
    Entity.update_all_entities_senses()

    # Haste caster casts Haste on target
    haste = Haste(
        source_entity_uuid=haste_caster.uuid,
        target_entity_uuid=target.uuid,
    )
    result = haste.apply()
    print(f"   Haste cast result: {result.status_message if result else 'None'}")
    assert has_condition(target, "Haste"), "Target should have Haste"

    # Cast AMF → suppresses Haste (target is inside zone)
    amf = AntimagicField(source_entity_uuid=amf_caster.uuid)
    amf.apply()

    # Haste should be suppressed, NO lethargy (Incapacitated)
    assert not has_condition(target, "Haste"), "Haste should be suppressed"
    assert not has_condition(target, "Incapacitated"), \
        "Should NOT have lethargy (Incapacitated) from AMF suppression"

    print("   PASSED: No lethargy on Haste suppression")


def test_nonmagical_conditions_untouched():
    """Test that non-magical conditions are not affected by AMF."""
    print("=" * 60)
    print("TEST: Non-magical Conditions Untouched")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(10, 10), faction="heroes")
    target = create_goblin(name="Goblin", position=(11, 10), faction="enemies")
    Entity.update_all_entities_senses()

    # Apply non-magical Poisoned
    poisoned = Poisoned(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(poisoned)
    assert has_condition(target, "Poisoned")

    # Cast AMF
    amf = AntimagicField(source_entity_uuid=caster.uuid)
    amf.apply()

    # Poisoned should still be there
    assert has_condition(target, "Poisoned"), "Non-magical Poisoned should survive AMF"
    print("   PASSED: Non-magical conditions untouched")


def test_concentrating_not_suppressed():
    """Test that the Concentrating condition itself is not suppressed.

    Uses Haste (no save, always applies) for deterministic testing.
    """
    print("=" * 60)
    print("TEST: Concentrating Not Suppressed")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    amf_caster = create_caster(name="AMF Wizard", position=(10, 10), faction="heroes")
    other_caster = create_caster(name="Other Mage", position=(11, 10), faction="heroes")
    # Target outside AMF zone but within Haste range of other_caster
    target = create_caster(name="Fighter", position=(15, 10), faction="heroes")
    Entity.update_all_entities_senses()

    # Other caster casts Haste on target (starts concentrating)
    haste = Haste(
        source_entity_uuid=other_caster.uuid,
        target_entity_uuid=target.uuid,
    )
    haste.apply()
    assert has_condition(other_caster, "Concentrating"), "Haste caster should concentrate"
    assert has_condition(target, "Haste"), "Target should have Haste"

    # AMF caster casts AMF (other_caster at 11,10 is inside zone centered at 10,10)
    amf = AntimagicField(source_entity_uuid=amf_caster.uuid)
    amf.apply()

    # Concentrating should NOT be suppressed (it's explicitly excluded)
    assert has_condition(other_caster, "Concentrating"), \
        "Concentrating should not be suppressed by AMF"

    print("   PASSED: Concentrating not suppressed")


def test_multiple_conditions_suppressed():
    """Test that multiple magical conditions on same entity are all suppressed."""
    print("=" * 60)
    print("TEST: Multiple Conditions Suppressed")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(10, 10), faction="heroes")
    target = create_goblin(name="Goblin", position=(11, 10), faction="enemies")
    Entity.update_all_entities_senses()

    # Apply multiple magical conditions
    blinded = Blinded(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        tags={ConditionTag.MAGICAL}
    )
    target.add_condition(blinded)

    frightened = Frightened(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        tags={ConditionTag.MAGICAL}
    )
    target.add_condition(frightened)

    assert has_condition(target, "Blinded")
    assert has_condition(target, "Frightened")

    # Cast AMF
    amf = AntimagicField(source_entity_uuid=caster.uuid)
    amf.apply()

    assert not has_condition(target, "Blinded"), "Blinded should be suppressed"
    assert not has_condition(target, "Frightened"), "Frightened should be suppressed"

    # Break AMF → both restored
    caster.remove_condition("Concentrating")
    assert has_condition(target, "Blinded"), "Blinded should be restored"
    assert has_condition(target, "Frightened"), "Frightened should be restored"

    print("   PASSED: Multiple conditions suppressed and restored")


def test_zone_movement_suppress_new_entity():
    """Test that moving zone over new entity suppresses their conditions."""
    print("=" * 60)
    print("TEST: Zone Movement Suppress New Entity")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(5, 10), faction="heroes")
    target = create_goblin(name="Goblin", position=(15, 10), faction="enemies")
    Entity.update_all_entities_senses()

    # Apply magical Blinded to target
    blinded = Blinded(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        tags={ConditionTag.MAGICAL}
    )
    target.add_condition(blinded)

    # Cast AMF (target at 15,10 is outside zone centered at 5,10, distance 10 tiles = 50ft)
    amf = AntimagicField(source_entity_uuid=caster.uuid)
    amf.apply()
    assert has_condition(target, "Blinded"), "Target should still have Blinded (outside zone)"

    # Move caster next to target → zone now covers target
    grid = get_map()
    grid.move_entity(caster.uuid, (15, 11))
    Entity.update_all_entities_senses()

    # Target should now be suppressed
    zone = caster.active_conditions.get("Antimagic Field Zone")
    assert isinstance(zone, AntimagicFieldZone)
    print(f"   Zone center: {zone.zone_center}")
    print(f"   Target position: {target.position}")
    print(f"   Target in zone: {target.position in zone.affected_positions}")
    assert not has_condition(target, "Blinded"), "Blinded should be suppressed when zone moves over"

    print("   PASSED: Zone movement suppresses new entities")


# =============================================================================
# Run all tests
# =============================================================================

if __name__ == "__main__":
    tests = [
        test_zone_creation,
        test_spell_blocked_targeting_inside_zone,
        test_spell_blocked_from_inside_zone,
        test_suppress_existing_conditions_on_cast,
        test_restore_conditions_on_amf_end,
        test_suppress_on_entry_restore_on_exit,
        test_caster_magical_conditions_suppressed,
        test_zone_follows_caster,
        test_concentration_spell_suppressed_and_restored,
        test_haste_no_lethargy_on_suppression,
        test_nonmagical_conditions_untouched,
        test_concentrating_not_suppressed,
        test_multiple_conditions_suppressed,
        test_zone_movement_suppress_new_entity,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"   FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    print("=" * 60)
    if failed > 0:
        exit(1)
