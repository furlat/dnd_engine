"""Extensive tests for sense-buff spells: Darkvision, See Invisibility, True Seeing.

Tests cover:
- Condition application and removal
- Actual sense mode changes (darkvision, see invisible, truesight)
- Concentration lifecycle (Darkvision only)
- Duration expiry (See Invisibility, True Seeing)
- Interaction with invisible entities
- Interaction with darkness tiles
- Touch range validation
- Self-targeting vs ally targeting
"""
import sys
import traceback
from uuid import uuid4

from dnd.core.events import EventQueue, EventPhase
from dnd.core.gridmap import get_map, reset_map
from dnd.core.base_block import SensesType, LightLevel
from dnd.core.base_tiles import dark_floor_factory
from dnd.core.base_conditions import DurationType
from dnd.core.modifiers import DamageType
from dnd.entity import Entity, get_natural_roll
from dnd.monsters.bestiary import create_sorcerer, create_goblin
from dnd.conditions import Concentrating, Invisible
from dnd.spells.transmutation import DarkvisionSpell, DarkvisionEffect
from dnd.spells.divination import SeeInvisibility, SeeInvisibilityEffect, TrueSeeing, TrueSeeingEffect
from dnd.actions_functional import setup_standard_actions
from dnd.utils import (
    reset_combat_state, get_hp, set_hp, has_condition,
    deal_damage_to, move_entity,
)


def setup_arena(size: int = 20):
    """Create a walkable floor arena."""
    reset_map()
    grid = get_map()
    grid.create_rectangle(0, 0, size, size)
    return grid


def had_critical_d20() -> bool:
    """Check if any d20 roll had nat 1 or 20."""
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


# =============================================================================
# Test 1: Darkvision spell - basic application and concentration
# =============================================================================
def test_darkvision_basic():
    """Cast Darkvision on self, verify sense mode added, break concentration, verify removed."""
    print("\n=== Test 1: Darkvision basic application and concentration ===")
    reset_combat_state()
    setup_arena()

    # Create sorcerer without darkvision
    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5)
    Entity.update_all_entities_senses()

    # Verify no darkvision initially
    has_dv = any(sm.sense_type == SensesType.DARKVISION for sm in caster.senses.sense_modes)
    print(f"  Has darkvision before cast: {has_dv}")
    assert not has_dv, "Sorcerer should not have darkvision initially"

    # Cast Darkvision on self
    spell = DarkvisionSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        cast_at_level=2,
        template=False,
        costs=DarkvisionSpell(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    result = spell.apply()
    assert result is not None and not result.canceled, f"Darkvision should succeed, got: {result}"

    # Verify sense mode added
    has_dv = any(sm.sense_type == SensesType.DARKVISION for sm in caster.senses.sense_modes)
    print(f"  Has darkvision after cast: {has_dv}")
    assert has_dv, "Should have darkvision after casting"

    # Verify concentration
    assert has_condition(caster, "Concentrating"), "Should be concentrating"
    conc = caster.active_conditions.get("Concentrating")
    assert isinstance(conc, Concentrating)
    assert conc.spell_name == "Darkvision"

    # Verify effect condition
    assert has_condition(caster, "Darkvision"), "Should have Darkvision effect"

    # Break concentration via massive damage (DC 25, impossible to pass)
    deal_damage_to(caster, 50, DamageType.FIRE)

    # Verify darkvision removed
    has_dv = any(sm.sense_type == SensesType.DARKVISION for sm in caster.senses.sense_modes)
    print(f"  Has darkvision after concentration break: {has_dv}")
    assert not has_dv, "Darkvision should be removed after concentration break"
    assert not has_condition(caster, "Darkvision"), "Darkvision effect should be removed"
    assert not has_condition(caster, "Concentrating"), "Should not be concentrating"

    print("  PASS: Darkvision basic lifecycle works")


# =============================================================================
# Test 2: Darkvision on ally - touch range validation
# =============================================================================
def test_darkvision_on_ally():
    """Cast Darkvision on ally within touch range; verify out-of-range fails."""
    print("\n=== Test 2: Darkvision on ally and range checks ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    ally = create_sorcerer(name="Cleric", position=(6, 5), level=5, faction="heroes")
    Entity.update_all_entities_senses()

    # Cast on adjacent ally (5ft = 1 tile)
    spell = DarkvisionSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=2,
        template=False,
        costs=DarkvisionSpell(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    result = spell.apply()
    assert result is not None and not result.canceled, "Should succeed on adjacent ally"

    # Verify ally has darkvision, caster is concentrating
    has_dv = any(sm.sense_type == SensesType.DARKVISION for sm in ally.senses.sense_modes)
    assert has_dv, "Ally should have darkvision"
    assert has_condition(caster, "Concentrating"), "Caster should concentrate"
    assert has_condition(ally, "Darkvision"), "Ally should have effect"

    print("  PASS: Darkvision on adjacent ally works")

    # Now test out-of-range (10ft away)
    reset_combat_state()
    setup_arena()

    caster2 = create_sorcerer(name="Wizard2", position=(5, 5), level=5, faction="heroes")
    far_ally = create_sorcerer(name="Far Cleric", position=(7, 5), level=5, faction="heroes")
    Entity.update_all_entities_senses()

    spell2 = DarkvisionSpell(
        source_entity_uuid=caster2.uuid,
        target_entity_uuid=far_ally.uuid,
        cast_at_level=2,
        template=False,
        costs=DarkvisionSpell(source_entity_uuid=caster2.uuid)._get_costs_for_level(2)
    )
    result2 = spell2.apply()
    assert result2 is not None and result2.canceled, \
        f"Should fail at 10ft range (touch range), got: {result2.status_message}"
    print(f"  Out-of-range message: {result2.status_message}")

    # Verify nothing applied
    assert not has_condition(far_ally, "Darkvision"), "Far ally should NOT have darkvision"
    assert not has_condition(caster2, "Concentrating"), "Caster should NOT be concentrating"

    print("  PASS: Touch range validation works")


# =============================================================================
# Test 3: Darkvision - concentration replacement
# =============================================================================
def test_darkvision_concentration_replacement():
    """Casting another concentration spell should remove Darkvision."""
    print("\n=== Test 3: Darkvision concentration replacement ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    ally = create_sorcerer(name="Cleric", position=(6, 5), level=5, faction="heroes")
    target = create_goblin(name="Goblin", position=(8, 5), faction="monsters")
    Entity.update_all_entities_senses()

    # Cast Darkvision on ally
    dv_spell = DarkvisionSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=2,
        template=False,
        costs=DarkvisionSpell(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    dv_spell.apply()
    assert has_condition(ally, "Darkvision"), "Ally should have darkvision"

    # Cast another concentration spell (e.g., Invisibility on self)
    from dnd.spells.illusion import Invisibility as InvisibilitySpell
    caster.action_economy.reset_all_costs()
    invis_spell = InvisibilitySpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        cast_at_level=2,
        template=False,
        costs=InvisibilitySpell(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    invis_spell.apply()

    # Darkvision should be gone from ally
    has_dv = any(sm.sense_type == SensesType.DARKVISION for sm in ally.senses.sense_modes)
    print(f"  Ally has darkvision after new conc spell: {has_dv}")
    assert not has_dv, "Darkvision should be removed when new concentration spell replaces it"
    assert not has_condition(ally, "Darkvision"), "Darkvision effect should be removed"

    # New concentration should be active
    conc = caster.active_conditions.get("Concentrating")
    if conc:
        print(f"  Now concentrating on: {conc.spell_name}")

    print("  PASS: Concentration replacement removes darkvision")


# =============================================================================
# Test 4: See Invisibility - sees invisible creatures
# =============================================================================
def test_see_invisibility_basic():
    """Cast See Invisibility, verify invisible creatures become visible."""
    print("\n=== Test 4: See Invisibility basic ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    enemy = create_goblin(name="Sneaky Goblin", position=(8, 5), faction="monsters")
    Entity.update_all_entities_senses()

    # Verify enemy is visible initially
    assert enemy.uuid in caster.senses.entities, "Enemy should be visible initially"

    # Make enemy invisible — reactive pipeline should update caster's senses
    invis = Invisible(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=enemy.uuid,
    )
    enemy.add_condition(invis)

    # Verify enemy is now invisible to caster (reactive: SPATIAL_PERCEIVABILITY_CHANGED)
    enemy_visible = enemy.uuid in caster.senses.entities
    print(f"  Enemy visible while invisible: {enemy_visible}")
    assert not enemy_visible, "Enemy should NOT be visible while invisible (reactive)"

    # Cast See Invisibility — reactive pipeline should update caster's senses
    spell = SeeInvisibility(
        source_entity_uuid=caster.uuid,
        cast_at_level=2,
        template=False,
        costs=SeeInvisibility(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    result = spell.apply()
    assert result is not None and not result.canceled, "See Invisibility should succeed"

    # Verify SEE_INVISIBLE sense mode added
    has_si = any(sm.sense_type == SensesType.SEE_INVISIBLE for sm in caster.senses.sense_modes)
    print(f"  Has See Invisible sense: {has_si}")
    assert has_si, "Should have SEE_INVISIBLE sense mode"

    # Verify enemy is now visible (reactive: sense mode change detected)
    enemy_visible = enemy.uuid in caster.senses.entities
    print(f"  Enemy visible after See Invisibility: {enemy_visible}")
    assert enemy_visible, "Enemy should be visible with See Invisibility active"

    # Verify NOT concentration
    assert not has_condition(caster, "Concentrating"), "See Invisibility is NOT concentration"

    # Verify has duration
    si_effect = caster.active_conditions.get("See Invisibility")
    assert si_effect is not None
    assert si_effect.duration.duration_type == DurationType.ROUNDS
    assert si_effect.duration.duration == 10
    print(f"  Duration: {si_effect.duration.duration} rounds")

    print("  PASS: See Invisibility reveals invisible creatures")


# =============================================================================
# Test 5: See Invisibility - duration expiry
# =============================================================================
def test_see_invisibility_duration():
    """See Invisibility expires after 10 rounds, enemy becomes invisible again."""
    print("\n=== Test 5: See Invisibility duration expiry ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    enemy = create_goblin(name="Sneaky", position=(8, 5), faction="monsters")
    Entity.update_all_entities_senses()

    # Make enemy invisible — reactive update
    invis = Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid)
    enemy.add_condition(invis)

    # Cast See Invisibility — reactive update
    spell = SeeInvisibility(
        source_entity_uuid=caster.uuid,
        cast_at_level=2,
        template=False,
        costs=SeeInvisibility(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    spell.apply()

    # Verify enemy visible (reactive: sense mode change)
    assert enemy.uuid in caster.senses.entities, "Enemy should be visible with See Invis (reactive)"

    # Tick 9 rounds — should still be active
    for i in range(9):
        caster.advance_duration("See Invisibility")
    assert has_condition(caster, "See Invisibility"), "Should still be active after 9 rounds"

    # Tick 10th round — should expire (reactive: sense mode removed → senses update)
    caster.advance_duration("See Invisibility")

    has_si = has_condition(caster, "See Invisibility")
    print(f"  Has See Invisibility after 10 rounds: {has_si}")
    assert not has_si, "See Invisibility should expire after 10 rounds"

    # Verify sense mode removed
    has_si_sense = any(sm.sense_type == SensesType.SEE_INVISIBLE for sm in caster.senses.sense_modes)
    assert not has_si_sense, "SEE_INVISIBLE sense should be removed"

    # Verify enemy invisible again (reactive: sense mode removal triggers refilter)
    enemy_visible = enemy.uuid in caster.senses.entities
    print(f"  Enemy visible after expiry: {enemy_visible}")
    assert not enemy_visible, "Enemy should be invisible again after See Invis expires"

    print("  PASS: See Invisibility expires correctly")


# =============================================================================
# Test 6: True Seeing - grants truesight, sees invisible, touch range
# =============================================================================
def test_true_seeing_basic():
    """Cast True Seeing on ally, verify truesight sense mode and invisible perception."""
    print("\n=== Test 6: True Seeing basic ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    ally = create_sorcerer(name="Fighter", position=(6, 5), level=5, faction="heroes")
    enemy = create_goblin(name="Sneaky", position=(9, 5), faction="monsters")
    Entity.update_all_entities_senses()

    # Make enemy invisible — reactive update
    invis = Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid)
    enemy.add_condition(invis)

    # Verify ally can't see invisible enemy (reactive: SPATIAL_PERCEIVABILITY_CHANGED)
    assert enemy.uuid not in ally.senses.entities, "Ally shouldn't see invisible enemy (reactive)"

    # Cast True Seeing on ally (touch range) — reactive update
    spell = TrueSeeing(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=6,
        template=False,
        costs=TrueSeeing(source_entity_uuid=caster.uuid)._get_costs_for_level(6)
    )
    result = spell.apply()
    assert result is not None and not result.canceled, "True Seeing should succeed"

    # Verify TRUESIGHT sense mode on ally
    has_ts = any(sm.sense_type == SensesType.TRUESIGHT and sm.range_feet == 120
                 for sm in ally.senses.sense_modes)
    print(f"  Ally has truesight: {has_ts}")
    assert has_ts, "Ally should have 120ft truesight"

    # Verify NOT concentration
    assert not has_condition(caster, "Concentrating"), "True Seeing is NOT concentration"

    # Verify ally can now see invisible enemy (reactive: sense mode change)
    enemy_visible = enemy.uuid in ally.senses.entities
    print(f"  Ally sees invisible enemy: {enemy_visible}")
    assert enemy_visible, "Ally with truesight should see invisible enemy"

    # Verify duration
    ts_effect = ally.active_conditions.get("True Seeing")
    assert ts_effect is not None
    assert ts_effect.duration.duration_type == DurationType.ROUNDS
    assert ts_effect.duration.duration == 10

    print("  PASS: True Seeing grants truesight and reveals invisible")


# =============================================================================
# Test 7: True Seeing - duration expiry
# =============================================================================
def test_true_seeing_duration():
    """True Seeing expires after 10 rounds, truesight is removed."""
    print("\n=== Test 7: True Seeing duration expiry ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    ally = create_sorcerer(name="Fighter", position=(6, 5), level=5, faction="heroes")
    Entity.update_all_entities_senses()

    spell = TrueSeeing(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=6,
        template=False,
        costs=TrueSeeing(source_entity_uuid=caster.uuid)._get_costs_for_level(6)
    )
    spell.apply()

    # Tick through 10 rounds
    for i in range(10):
        ally.advance_duration("True Seeing")

    assert not has_condition(ally, "True Seeing"), "True Seeing should expire after 10 rounds"
    has_ts = any(sm.sense_type == SensesType.TRUESIGHT for sm in ally.senses.sense_modes)
    assert not has_ts, "Truesight sense should be removed"

    print("  PASS: True Seeing duration expiry works")


# =============================================================================
# Test 8: True Seeing - out of range fails
# =============================================================================
def test_true_seeing_range():
    """True Seeing fails if target is more than 5ft away."""
    print("\n=== Test 8: True Seeing range validation ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    far_ally = create_sorcerer(name="Far Ally", position=(8, 5), level=5, faction="heroes")
    Entity.update_all_entities_senses()

    spell = TrueSeeing(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=far_ally.uuid,
        cast_at_level=6,
        template=False,
        costs=TrueSeeing(source_entity_uuid=caster.uuid)._get_costs_for_level(6)
    )
    result = spell.apply()
    assert result is not None and result.canceled, \
        f"True Seeing at 15ft should fail, got: {result.status_message}"
    print(f"  Out-of-range message: {result.status_message}")

    assert not has_condition(far_ally, "True Seeing"), "Far ally should NOT have True Seeing"
    print("  PASS: Touch range validation works for True Seeing")


# =============================================================================
# Test 9: Darkvision - effect condition cleanup chain
# =============================================================================
def test_darkvision_cleanup_chain():
    """Verify cleanup chain: removing Darkvision effect also removes Concentrating via parent link."""
    print("\n=== Test 9: Darkvision cleanup chain ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    ally = create_sorcerer(name="Cleric", position=(6, 5), level=5, faction="heroes")
    Entity.update_all_entities_senses()

    spell = DarkvisionSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=2,
        template=False,
        costs=DarkvisionSpell(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    spell.apply()

    assert has_condition(caster, "Concentrating"), "Caster should concentrate"
    assert has_condition(ally, "Darkvision"), "Ally should have effect"

    # Remove effect directly from ally (simulating dispel magic)
    ally.remove_condition("Darkvision")

    # Concentration should auto-remove via parent_link reverse cleanup
    assert not has_condition(ally, "Darkvision"), "Effect should be gone"
    assert not has_condition(caster, "Concentrating"), \
        "Concentrating should auto-remove when linked child is removed"

    # Sense mode should be cleaned up
    has_dv = any(sm.sense_type == SensesType.DARKVISION for sm in ally.senses.sense_modes)
    assert not has_dv, "Darkvision sense should be removed"

    print("  PASS: Cleanup chain works correctly")


# =============================================================================
# Test 10: Multiple sense buffs don't interfere
# =============================================================================
def test_multiple_sense_buffs():
    """Apply multiple sense buff effects, verify they coexist and clean up independently."""
    print("\n=== Test 10: Multiple sense buffs ===")
    reset_combat_state()
    setup_arena()

    entity = create_sorcerer(name="MultiSense", position=(5, 5), level=5)
    Entity.update_all_entities_senses()

    # Apply See Invisibility (duration-based)
    si_spell = SeeInvisibility(
        source_entity_uuid=entity.uuid,
        cast_at_level=2,
        template=False,
        costs=SeeInvisibility(source_entity_uuid=entity.uuid)._get_costs_for_level(2)
    )
    si_spell.apply()

    # Apply True Seeing (duration-based)
    entity.action_economy.reset_all_costs()
    ts_spell = TrueSeeing(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        cast_at_level=6,
        template=False,
        costs=TrueSeeing(source_entity_uuid=entity.uuid)._get_costs_for_level(6)
    )
    ts_spell.apply()

    # Verify both active
    has_si = any(sm.sense_type == SensesType.SEE_INVISIBLE for sm in entity.senses.sense_modes)
    has_ts = any(sm.sense_type == SensesType.TRUESIGHT for sm in entity.senses.sense_modes)
    print(f"  Has See Invisible: {has_si}, Has Truesight: {has_ts}")
    assert has_si, "Should have See Invisible"
    assert has_ts, "Should have Truesight"

    # Remove See Invisibility, True Seeing should remain
    entity.remove_condition("See Invisibility")
    has_si = any(sm.sense_type == SensesType.SEE_INVISIBLE for sm in entity.senses.sense_modes)
    has_ts = any(sm.sense_type == SensesType.TRUESIGHT for sm in entity.senses.sense_modes)
    print(f"  After removing SI - See Invisible: {has_si}, Truesight: {has_ts}")
    assert not has_si, "See Invisible should be gone"
    assert has_ts, "Truesight should remain"

    print("  PASS: Multiple sense buffs coexist and clean up independently")


# =============================================================================
# Helper: create all-dark grid
# =============================================================================
def create_dark_grid(width: int, height: int):
    """Create a grid where all tiles are DARKNESS (no ambient light)."""
    reset_map()
    grid = get_map()
    for x in range(width):
        for y in range(height):
            tile = dark_floor_factory((x, y))
            grid.set_tile(x, y, tile=tile, fire_event=False)
    return grid


# =============================================================================
# Test 11: Darkvision + darkness - REACTIVE senses update
# =============================================================================
def test_darkvision_darkness_reactive():
    """Cast Darkvision in a dark environment - verify enemy becomes visible
    through the reactive senses update pipeline (no manual update_entity_senses).

    Pipeline: condition._apply() adds SenseMode → CONDITION_APPLICATION event fires
    → SpatialSensesCallback._handle_own_perception_change() detects sense hash change
    → calls update_visibility_func() → full visibility recompute with darkvision
    → dark tiles now resolve to DIM_LIGHT → entities at those positions become visible.
    """
    print("\n=== Test 11: Darkvision + darkness reactive senses ===")
    reset_combat_state()
    grid = create_dark_grid(15, 5)

    # Place observer and target in the dark, 3 tiles apart (15ft)
    observer = create_sorcerer(name="Wizard", position=(2, 2), level=5, faction="heroes")
    enemy = create_goblin(name="Goblin", position=(5, 2), faction="monsters")

    # Initial senses setup - establishes baseline snapshot for change detection
    Entity.update_all_entities_senses()

    # Verify observer CANNOT see enemy in darkness (no darkvision)
    assert enemy.uuid not in observer.senses.entities, \
        "Observer without darkvision should NOT see enemy in darkness"
    print(f"  Before cast - enemy visible: {enemy.uuid in observer.senses.entities}")

    # Also verify the tile is actually dark from observer's perspective
    tile_at_enemy = grid.get_tile(5, 2)
    assert tile_at_enemy is not None
    eff_light = tile_at_enemy.get_effective_light_for(observer.uuid, observer.position)
    print(f"  Effective light at enemy tile (no DV): {eff_light}")
    assert eff_light.value <= LightLevel.DARKNESS.value, \
        f"Should be DARKNESS without darkvision, got {eff_light}"

    # Cast Darkvision on self
    spell = DarkvisionSpell(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        cast_at_level=2,
        template=False,
        costs=DarkvisionSpell(source_entity_uuid=observer.uuid)._get_costs_for_level(2)
    )
    result = spell.apply()
    assert result is not None and not result.canceled, f"Darkvision should succeed: {result}"

    # *** CRITICAL: Do NOT call update_entity_senses() here ***
    # The reactive senses pipeline should have already updated visibility

    # Verify the effective light changed (darkvision shifts DARKNESS → DIM_LIGHT)
    eff_light_after = tile_at_enemy.get_effective_light_for(observer.uuid, observer.position)
    print(f"  Effective light at enemy tile (with DV): {eff_light_after}")
    assert eff_light_after.value > LightLevel.DARKNESS.value, \
        f"Darkvision should shift DARKNESS to DIM_LIGHT, got {eff_light_after}"

    # Verify enemy is NOW visible through reactive senses update
    enemy_visible = enemy.uuid in observer.senses.entities
    print(f"  After cast (reactive) - enemy visible: {enemy_visible}")
    assert enemy_visible, \
        "Enemy should be visible after casting Darkvision (reactive senses update)"

    # Break concentration (massive damage)
    deal_damage_to(observer, 50, DamageType.FIRE)

    # Verify darkvision removed
    assert not has_condition(observer, "Darkvision"), "Darkvision effect should be removed"

    # *** Again, do NOT call update_entity_senses() ***
    # The reactive pipeline should remove visibility when darkvision is lost

    enemy_visible_after = enemy.uuid in observer.senses.entities
    print(f"  After conc break (reactive) - enemy visible: {enemy_visible_after}")
    assert not enemy_visible_after, \
        "Enemy should NOT be visible after darkvision removed (reactive senses update)"

    print("  PASS: Darkvision + darkness reactive senses lifecycle works")


# =============================================================================
# Test 12: See Invisibility - REACTIVE senses update
# =============================================================================
def test_see_invisibility_reactive():
    """Cast See Invisibility - verify invisible enemy becomes visible
    through the reactive senses update pipeline (no manual update_entity_senses).

    Pipeline: condition._apply() adds SEE_INVISIBLE SenseMode
    → CONDITION_APPLICATION event → _handle_own_perception_change()
    → sense hash change detected → update_visibility_func()
    → _refilter at visible positions → is_perceivable_by() now passes for invisible entity.
    """
    print("\n=== Test 12: See Invisibility reactive senses ===")
    reset_combat_state()
    setup_arena()  # Bright light grid

    observer = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    enemy = create_goblin(name="Sneaky", position=(8, 5), faction="monsters")

    # Initial senses - enemy visible in bright light
    Entity.update_all_entities_senses()
    assert enemy.uuid in observer.senses.entities, "Enemy should be visible initially"

    # Make enemy invisible - this fires SPATIAL_PERCEIVABILITY_CHANGED reactively
    invis = Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid)
    enemy.add_condition(invis)

    # Verify enemy is now invisible (reactive from Invisible condition's perceivability change)
    enemy_visible = enemy.uuid in observer.senses.entities
    print(f"  After invisibility (reactive) - enemy visible: {enemy_visible}")
    assert not enemy_visible, \
        "Enemy should NOT be visible after becoming invisible (reactive update)"

    # Cast See Invisibility
    spell = SeeInvisibility(
        source_entity_uuid=observer.uuid,
        cast_at_level=2,
        template=False,
        costs=SeeInvisibility(source_entity_uuid=observer.uuid)._get_costs_for_level(2)
    )
    result = spell.apply()
    assert result is not None and not result.canceled, "See Invisibility should succeed"

    # *** CRITICAL: Do NOT call update_entity_senses() here ***
    # Reactive pipeline should make invisible enemy visible

    enemy_visible = enemy.uuid in observer.senses.entities
    print(f"  After See Invisibility (reactive) - enemy visible: {enemy_visible}")
    assert enemy_visible, \
        "Invisible enemy should be visible after casting See Invisibility (reactive)"

    # Expire the condition (10 rounds)
    for _ in range(10):
        observer.advance_duration("See Invisibility")

    assert not has_condition(observer, "See Invisibility"), "Should expire"

    # *** No manual senses update - reactive removal should hide enemy again ***
    enemy_visible = enemy.uuid in observer.senses.entities
    print(f"  After expiry (reactive) - enemy visible: {enemy_visible}")
    assert not enemy_visible, \
        "Invisible enemy should NOT be visible after See Invisibility expires (reactive)"

    print("  PASS: See Invisibility reactive senses lifecycle works")


# =============================================================================
# Test 13: True Seeing - REACTIVE in darkness + invisibility
# =============================================================================
def test_true_seeing_reactive():
    """True Seeing should reveal invisible enemy in darkness, all reactively.

    Truesight grants: see through darkness (including magical), see invisible,
    see through illusions. Tests the full combo.
    """
    print("\n=== Test 13: True Seeing reactive senses (darkness + invisibility) ===")
    reset_combat_state()
    grid = create_dark_grid(15, 5)

    caster = create_sorcerer(name="Wizard", position=(2, 2), level=5, faction="heroes")
    ally = create_sorcerer(name="Fighter", position=(3, 2), level=5, faction="heroes")
    enemy = create_goblin(name="Ghost", position=(6, 2), faction="monsters")

    Entity.update_all_entities_senses()

    # Verify ally can't see enemy (dark + no special senses)
    assert enemy.uuid not in ally.senses.entities, "Ally can't see in darkness"

    # Make enemy invisible too (double concealment)
    invis = Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid)
    enemy.add_condition(invis)

    # Cast True Seeing on ally (touch range, adjacent)
    spell = TrueSeeing(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=6,
        template=False,
        costs=TrueSeeing(source_entity_uuid=caster.uuid)._get_costs_for_level(6)
    )
    result = spell.apply()
    assert result is not None and not result.canceled, "True Seeing should succeed"

    # *** CRITICAL: No manual update_entity_senses() ***
    # Truesight should pierce both darkness and invisibility reactively

    # Verify truesight sense mode
    has_ts = any(sm.sense_type == SensesType.TRUESIGHT for sm in ally.senses.sense_modes)
    assert has_ts, "Ally should have truesight"

    # Verify ally can now see the invisible enemy in darkness
    enemy_visible = enemy.uuid in ally.senses.entities
    print(f"  After True Seeing (reactive) - ally sees enemy: {enemy_visible}")
    assert enemy_visible, \
        "Truesight should reveal invisible enemy in darkness (reactive)"

    # Expire True Seeing
    for _ in range(10):
        ally.advance_duration("True Seeing")

    assert not has_condition(ally, "True Seeing"), "Should expire"

    # Enemy should vanish again (dark + invisible, no special senses)
    enemy_visible = enemy.uuid in ally.senses.entities
    print(f"  After expiry (reactive) - ally sees enemy: {enemy_visible}")
    assert not enemy_visible, \
        "Enemy should vanish when True Seeing expires (reactive)"

    print("  PASS: True Seeing reactive senses (darkness + invisibility) works")


# =============================================================================
# Test 14: Darkvision on ally - REACTIVE senses update
# =============================================================================
def test_darkvision_ally_reactive():
    """Cast Darkvision on an ally in darkness - ally should see enemies reactively."""
    print("\n=== Test 14: Darkvision on ally - reactive senses ===")
    reset_combat_state()
    grid = create_dark_grid(15, 5)

    caster = create_sorcerer(name="Wizard", position=(2, 2), level=5, faction="heroes")
    ally = create_sorcerer(name="Fighter", position=(3, 2), level=5, faction="heroes")
    enemy = create_goblin(name="Goblin", position=(6, 2), faction="monsters")

    Entity.update_all_entities_senses()

    # Ally cannot see enemy in dark
    assert enemy.uuid not in ally.senses.entities, "Ally can't see in darkness"

    # Cast Darkvision on ally (touch range)
    spell = DarkvisionSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=2,
        template=False,
        costs=DarkvisionSpell(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    result = spell.apply()
    assert result is not None and not result.canceled, "Should succeed on adjacent ally"

    # *** No manual update ***
    enemy_visible = enemy.uuid in ally.senses.entities
    print(f"  After Darkvision on ally (reactive) - ally sees enemy: {enemy_visible}")
    assert enemy_visible, \
        "Ally with darkvision should see enemy in darkness (reactive)"

    # Break caster's concentration → darkvision removed from ally
    deal_damage_to(caster, 50, DamageType.FIRE)

    assert not has_condition(ally, "Darkvision"), "Darkvision should be removed"

    # *** No manual update ***
    enemy_visible = enemy.uuid in ally.senses.entities
    print(f"  After conc break (reactive) - ally sees enemy: {enemy_visible}")
    assert not enemy_visible, \
        "Ally should lose vision when darkvision removed (reactive)"

    print("  PASS: Darkvision on ally reactive senses works")


# =============================================================================
# Test 15: Darkvision - deep integration: attack and available actions
# =============================================================================
def test_darkvision_attack_integration():
    """After gaining darkvision in darkness, verify:
    1. get_available_actions() shows the enemy as a valid attack target
    2. An attack can actually be executed against the now-visible enemy
    3. After concentration breaks, enemy disappears from available actions
    """
    print("\n=== Test 15: Darkvision - attack and available actions integration ===")
    reset_combat_state()
    grid = create_dark_grid(15, 5)

    from dnd.actions_functional import execute_by_index

    # Place observer and enemy 3 tiles apart (15ft) - beyond adjacent rule (1 tile)
    # Adjacent rule: within 1 tile, DARKNESS → DIM_LIGHT, so must use distance > 1
    observer = create_sorcerer(name="Wizard", position=(2, 2), level=5, faction="heroes")
    enemy = create_goblin(name="Goblin", position=(5, 2), faction="monsters")

    Entity.update_all_entities_senses()

    # Verify enemy is NOT visible in darkness (beyond adjacent rule distance)
    assert enemy.uuid not in observer.senses.entities, "Enemy should not be visible in darkness"

    # Before darkvision: enemy not in available actions targets
    avail = observer.get_available_actions()
    enemy_is_target = any(
        enemy.uuid in [t.target_uuid for t in info.valid_targets]
        for info in avail.entity_actions
        if hasattr(info, 'valid_targets') and info.valid_targets
    )
    print(f"  Before DV - enemy is attack target: {enemy_is_target}")
    assert not enemy_is_target, "Enemy should NOT be a valid target in darkness"

    # Cast Darkvision
    spell = DarkvisionSpell(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        cast_at_level=2,
        template=False,
        costs=DarkvisionSpell(source_entity_uuid=observer.uuid)._get_costs_for_level(2)
    )
    spell.apply()

    # After darkvision: enemy should appear in available actions (reactive)
    observer.action_economy.reset_all_costs()
    avail = observer.get_available_actions()
    enemy_is_target = any(
        enemy.uuid in [t.target_uuid for t in info.valid_targets]
        for info in avail.entity_actions
        if hasattr(info, 'valid_targets') and info.valid_targets
    )
    print(f"  After DV - enemy is attack target: {enemy_is_target}")
    assert enemy_is_target, "Enemy SHOULD be a valid target after gaining darkvision"

    # Actually cast a spell at the enemy (Fire Bolt — uses senses for targeting)
    hp_before = get_hp(enemy)
    set_hp(enemy, 100)
    hp_before = get_hp(enemy)
    observer.action_economy.reset_all_costs()
    result = execute_by_index(observer, "Fire Bolt", 0)
    assert result is not None and not result.canceled, f"Fire Bolt should succeed: {result}"
    print(f"  Fire Bolt succeeded, enemy HP: {hp_before} → {get_hp(enemy)}")

    # Break concentration
    observer.action_economy.reset_all_costs()
    deal_damage_to(observer, 50, DamageType.FIRE)

    # After losing darkvision: enemy should disappear from targets
    observer.action_economy.reset_all_costs()
    avail = observer.get_available_actions()
    enemy_is_target = any(
        enemy.uuid in [t.target_uuid for t in info.valid_targets]
        for info in avail.entity_actions
        if hasattr(info, 'valid_targets') and info.valid_targets
    )
    print(f"  After conc break - enemy is attack target: {enemy_is_target}")
    assert not enemy_is_target, "Enemy should NOT be a target after losing darkvision"

    print("  PASS: Darkvision attack and available actions integration works")


# =============================================================================
# Test 16: See Invisibility - deep integration: spell targeting
# =============================================================================
def test_see_invisibility_spell_targeting():
    """After casting See Invisibility, verify:
    1. An invisible enemy appears in get_available_actions() entity targets
    2. A spell can be targeted at the now-visible invisible enemy
    3. After See Invisibility expires, enemy vanishes from targets
    """
    print("\n=== Test 16: See Invisibility - spell targeting integration ===")
    reset_combat_state()
    setup_arena()

    from dnd.actions_functional import register_spell, execute_by_index
    from dnd.spells.evocation import FireBolt

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    enemy = create_goblin(name="Sneaky", position=(8, 5), faction="monsters")
    Entity.update_all_entities_senses()

    # Register Fire Bolt for targeting test
    register_spell(caster, FireBolt, caster_level=5)

    # Enemy visible initially - Fire Bolt should target them
    avail = caster.get_available_actions()
    fire_bolt_targets = []
    for info in avail.entity_actions:
        if info.template_name == "Fire Bolt" and info.valid_targets:
            fire_bolt_targets = [t.target_uuid for t in info.valid_targets]
    assert enemy.uuid in fire_bolt_targets, "Enemy should be Fire Bolt target initially"

    # Make enemy invisible
    invis = Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid)
    enemy.add_condition(invis)

    # Enemy should vanish from Fire Bolt targets (reactive)
    caster.action_economy.reset_all_costs()
    avail = caster.get_available_actions()
    fire_bolt_targets = []
    for info in avail.entity_actions:
        if info.template_name == "Fire Bolt" and info.valid_targets:
            fire_bolt_targets = [t.target_uuid for t in info.valid_targets]
    print(f"  After invisibility - enemy in Fire Bolt targets: {enemy.uuid in fire_bolt_targets}")
    assert enemy.uuid not in fire_bolt_targets, "Invisible enemy should NOT be a Fire Bolt target"

    # Cast See Invisibility
    spell = SeeInvisibility(
        source_entity_uuid=caster.uuid,
        cast_at_level=2,
        template=False,
        costs=SeeInvisibility(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    spell.apply()

    # Enemy should reappear in Fire Bolt targets (reactive)
    caster.action_economy.reset_all_costs()
    avail = caster.get_available_actions()
    fire_bolt_targets = []
    for info in avail.entity_actions:
        if info.template_name == "Fire Bolt" and info.valid_targets:
            fire_bolt_targets = [t.target_uuid for t in info.valid_targets]
    print(f"  After See Invis - enemy in Fire Bolt targets: {enemy.uuid in fire_bolt_targets}")
    assert enemy.uuid in fire_bolt_targets, \
        "Invisible enemy SHOULD be a Fire Bolt target with See Invisibility"

    # Actually cast Fire Bolt at the invisible enemy
    hp_before = get_hp(enemy)
    set_hp(enemy, 100)
    hp_before = get_hp(enemy)
    caster.action_economy.reset_all_costs()

    # Find and execute Fire Bolt targeting the enemy
    result = execute_by_index(caster, "Fire Bolt", 0)
    assert result is not None and not result.canceled, f"Fire Bolt should succeed: {result}"
    print(f"  Fire Bolt at invisible enemy succeeded, HP: {hp_before} → {get_hp(enemy)}")

    # Expire See Invisibility (10 rounds)
    for _ in range(10):
        caster.advance_duration("See Invisibility")

    # Enemy should vanish from targets again
    caster.action_economy.reset_all_costs()
    avail = caster.get_available_actions()
    fire_bolt_targets = []
    for info in avail.entity_actions:
        if info.template_name == "Fire Bolt" and info.valid_targets:
            fire_bolt_targets = [t.target_uuid for t in info.valid_targets]
    print(f"  After expiry - enemy in Fire Bolt targets: {enemy.uuid in fire_bolt_targets}")
    assert enemy.uuid not in fire_bolt_targets, \
        "Enemy should vanish from targets after See Invisibility expires"

    print("  PASS: See Invisibility spell targeting integration works")


# =============================================================================
# Run all tests
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_darkvision_basic,
        test_darkvision_on_ally,
        test_darkvision_concentration_replacement,
        test_see_invisibility_basic,
        test_see_invisibility_duration,
        test_true_seeing_basic,
        test_true_seeing_duration,
        test_true_seeing_range,
        test_darkvision_cleanup_chain,
        test_multiple_sense_buffs,
        test_darkvision_darkness_reactive,
        test_see_invisibility_reactive,
        test_true_seeing_reactive,
        test_darkvision_ally_reactive,
        test_darkvision_attack_integration,
        test_see_invisibility_spell_targeting,
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
    print("All sense buff spell tests passed!")
