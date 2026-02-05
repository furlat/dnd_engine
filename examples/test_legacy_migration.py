"""
Comprehensive tests validating the complete migration from legacy spatial handlers
to position-indexed spatial handlers.

Tests verify:
1. TileEffectCondition entry handlers fire only at correct positions
2. Multiple tile effects are efficient (no O(N) firing)
3. TileEffectCondition and ZoneControlCondition coexist
4. Condition cleanup removes spatial handlers
5. Non-spatial handlers (OA, turn start) still work
6. Backward compatibility for any remaining legacy patterns
"""

from uuid import uuid4, UUID
from typing import List, Tuple, Optional
import random

from dnd.utils import reset_combat_state, get_hp, get_position, move_entity
from dnd.core.events import EventQueue, EventType, EventPhase, Event, EventHandler, Trigger, SpatialHandler
from dnd.core.gridmap import get_map
from dnd.tile_conditions import TileEffectCondition, ZoneControlCondition, parse_dice_string
from dnd.core.modifiers import DamageType
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity
from dnd.encounter import Encounter
from dnd.controller import PassController
from pydantic import PrivateAttr


# ============================================================================
# Test Subclasses - Proper _apply() implementations
# ============================================================================

class TestEntryDamageTile(TileEffectCondition):
    """Test tile effect with entry damage.

    Implements _apply() to create entry damage handler.
    """
    name: str = "Test Entry Damage"
    description: str = "Deals damage when entities enter"

    # Spell-specific fields
    damage_dice: str = "2d6"
    damage_type: DamageType = DamageType.FIRE

    # Track handler UUID for tests
    _entry_handler_uuid: Optional[UUID] = PrivateAttr(default=None)

    def _apply(self, declaration_event):
        """Apply entry damage handler to the tile."""
        spatial_handler_uuids = []
        tile = self.get_tile()
        if tile:
            handler = self._create_entry_damage_handler(tile)
            EventQueue.add_spatial_handler(handler)
            self._entry_handler_uuid = handler.uuid
            spatial_handler_uuids.append(handler.uuid)

        effect_event = None
        if declaration_event is not None:
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return [], [], [], spatial_handler_uuids, effect_event

    def _create_entry_damage_handler(self, tile):
        """Create a spatial handler that deals damage when entities enter this tile."""
        damage_dice_str = self.damage_dice
        damage_type = self.damage_type
        source_uuid = self.source_entity_uuid

        def entry_damage_processor(event, _handler_source_uuid):
            entity_uuid = getattr(event, 'entity_uuid', None)
            if not entity_uuid:
                return None
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            count, value = parse_dice_string(damage_dice_str)
            damage = sum(random.randint(1, value) for _ in range(count))
            entity.health.take_damage(damage, damage_type, source_entity_uuid=source_uuid)
            return None

        return SpatialHandler(
            name=f"{self.name} Entry Damage",
            source_entity_uuid=tile.uuid,
            positions={tile.position},
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT,
            event_processor=entry_damage_processor
        )


class TestTurnStartDamageTile(TileEffectCondition):
    """Test tile effect with turn start damage.

    Implements _apply() to create turn start damage handler.
    """
    name: str = "Test Turn Start Damage"
    description: str = "Deals damage at turn start"

    # Spell-specific fields
    damage_dice: str = "1d6"
    damage_type: DamageType = DamageType.FIRE

    def _apply(self, declaration_event):
        """Apply turn start damage handler."""
        handler_uuids = []
        tile = self.get_tile()
        if tile:
            handler = self._create_turn_start_damage_handler(tile.uuid)
            EventQueue.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

        effect_event = None
        if declaration_event is not None:
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return [], handler_uuids, [], [], effect_event

    def _create_turn_start_damage_handler(self, tile_uuid):
        """Create an event handler that deals damage at turn start if entity is on tile."""
        damage_dice_str = self.damage_dice
        damage_type = self.damage_type
        source_uuid = self.source_entity_uuid

        def turn_start_damage_processor(event, _handler_source_uuid):
            if event.event_type != EventType.TURN_START:
                return None

            entity = Entity.get(event.source_entity_uuid)
            if not entity:
                return None

            grid = get_map()
            tile = grid.get_tile_by_uuid(tile_uuid)
            if not tile:
                return None

            if entity.senses.position != tile.position:
                return None

            count, value = parse_dice_string(damage_dice_str)
            damage = sum(random.randint(1, value) for _ in range(count))
            entity.health.take_damage(damage, damage_type, source_entity_uuid=source_uuid)
            return None

        return EventHandler(
            name=f"{self.name} Turn Start Damage",
            source_entity_uuid=tile_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=turn_start_damage_processor
        )


# ============================================================================
# Test 1: TileEffectCondition entry fires only at correct position
# ============================================================================

def test_tile_effect_entry_fires_only_at_correct_position():
    """TileEffectCondition entry handler fires only at its registered position."""
    print("\n" + "=" * 60)
    print("TEST: TileEffectCondition Entry Fires Only At Correct Position")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a simple grid
    for x in range(10):
        for y in range(2):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Create entity at (0, 0)
    entity = create_skeleton(name="Walker", position=(0, 0))
    Entity.update_all_entities_senses()

    initial_hp = get_hp(entity)
    print(f"Initial HP: {initial_hp}")

    # Create tile effect with entry damage at (5, 0)
    fire_tile = grid.get_tile(5, 0)
    assert fire_tile is not None
    fire_effect = TestEntryDamageTile(
        source_entity_uuid=uuid4(),
        target_entity_uuid=fire_tile.uuid,
        damage_dice="2d6",
        damage_type=DamageType.FIRE,
    )
    fire_tile.add_condition(fire_effect)

    print(f"Fire tile at: {fire_tile.position}")
    print(f"Handler registered: {fire_effect._entry_handler_uuid is not None}")

    # Move to (2, 0) - should NOT trigger damage
    print("\n--- Moving to (2, 0) ---")
    grid.move_entity(entity.uuid, (2, 0))
    entity.senses._position = (2, 0)
    Entity.update_all_entities_senses()
    hp_at_2 = get_hp(entity)
    print(f"HP at (2, 0): {hp_at_2}")
    assert hp_at_2 == initial_hp, f"Should not have taken damage! HP: {initial_hp} -> {hp_at_2}"

    # Move to (4, 0) - still should NOT trigger damage
    print("\n--- Moving to (4, 0) ---")
    grid.move_entity(entity.uuid, (4, 0))
    entity.senses._position = (4, 0)
    Entity.update_all_entities_senses()
    hp_at_4 = get_hp(entity)
    print(f"HP at (4, 0): {hp_at_4}")
    assert hp_at_4 == initial_hp, f"Should not have taken damage! HP: {initial_hp} -> {hp_at_4}"

    # Move to (5, 0) - SHOULD trigger damage
    print("\n--- Moving to (5, 0) - fire tile ---")
    grid.move_entity(entity.uuid, (5, 0))
    entity.senses._position = (5, 0)
    Entity.update_all_entities_senses()
    hp_at_5 = get_hp(entity)
    print(f"HP at (5, 0): {hp_at_5}")
    assert hp_at_5 < initial_hp, f"Should have taken damage! HP: {initial_hp} -> {hp_at_5}"

    print(f"\nDamage taken: {initial_hp - hp_at_5}")
    print("\n[PASS] Entry handler fires only at correct position!")


# ============================================================================
# Test 2: Multiple TileEffectConditions are efficient
# ============================================================================

def test_multiple_tile_effects_efficient():
    """Multiple TileEffectConditions don't all fire on every movement."""
    print("\n" + "=" * 60)
    print("TEST: Multiple TileEffectConditions Efficiency")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a row of tiles
    for x in range(20):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    # Create entity at (0, 0)
    entity = create_skeleton(name="Walker", position=(0, 0))
    Entity.update_all_entities_senses()

    # Track handler invocations
    invocation_count = [0]
    original_processors = {}

    # Create 10 tile effects at positions 10-19 with tracking
    for i in range(10):
        x = 10 + i
        tile = grid.get_tile(x, 0)
        assert tile is not None
        effect = TestEntryDamageTile(
            source_entity_uuid=uuid4(),
            target_entity_uuid=tile.uuid,
            damage_dice="1d4",
            damage_type=DamageType.FIRE,
        )
        tile.add_condition(effect)

    print(f"Created 10 tile effects at positions (10,0) to (19,0)")

    # Check spatial index state
    key = (EventType.SPATIAL_ENTITY_ENTERED, EventPhase.EFFECT)
    handlers_per_position = {}
    if key in EventQueue._spatial_handlers_by_position:
        for pos, handlers in EventQueue._spatial_handlers_by_position[key].items():
            handlers_per_position[pos] = len(handlers)
    print(f"Handlers registered by position: {handlers_per_position}")

    # Verify each position has exactly 1 handler
    for x in range(10, 20):
        assert (x, 0) in handlers_per_position, f"Position ({x}, 0) should have a handler"
        assert handlers_per_position[(x, 0)] == 1, f"Position ({x}, 0) should have exactly 1 handler"

    print("\n[PASS] Multiple tile effects registered efficiently (1 handler per position)!")


# ============================================================================
# Test 3: TileEffectCondition and ZoneControlCondition coexist
# ============================================================================

class TestEntryZone(ZoneControlCondition):
    """Test zone that tracks entries."""
    name: str = "Test Entry Zone"
    entries_tracked: List[Tuple[int, int]] = []

    def _has_entry_effect(self) -> bool:
        return True

    def _create_zone_entry_handler(self) -> EventHandler:
        zone = self

        def track_entry(event: Event, _: UUID) -> None:
            pos = getattr(event, 'position', None)
            if pos:
                zone.entries_tracked.append(pos)
            return None

        return EventHandler(
            name=f"{self.name} Entry Tracker",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=track_entry
        )


def test_tile_effect_and_zone_coexist():
    """TileEffectCondition and ZoneControlCondition work together."""
    print("\n" + "=" * 60)
    print("TEST: TileEffectCondition and ZoneControlCondition Coexist")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a larger grid
    for x in range(15):
        for y in range(15):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Create entity at (0, 0)
    entity = create_skeleton(name="Walker", position=(0, 0))
    Entity.update_all_entities_senses()

    initial_hp = get_hp(entity)
    print(f"Initial HP: {initial_hp}")

    # Create a zone at (3, 3) with radius 10ft (2 tiles)
    zone = TestEntryZone(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        zone_center=(3, 3),
        zone_radius_feet=10
    )
    entity.add_condition(zone)

    # Create a tile effect at (10, 10)
    far_tile = grid.get_tile(10, 10)
    assert far_tile is not None
    tile_effect = TestEntryDamageTile(
        source_entity_uuid=uuid4(),
        target_entity_uuid=far_tile.uuid,
        damage_dice="2d6",
        damage_type=DamageType.FIRE,
    )
    far_tile.add_condition(tile_effect)

    print(f"Zone center: (3, 3), radius: 10ft")
    print(f"Zone affected positions: {sorted(zone.affected_positions)}")
    print(f"Tile effect at: (10, 10)")

    # Move through zone
    print("\n--- Moving to (3, 3) - zone center ---")
    grid.move_entity(entity.uuid, (3, 3))
    entity.senses._position = (3, 3)
    Entity.update_all_entities_senses()
    print(f"Zone entries: {zone.entries_tracked}")
    hp_in_zone = get_hp(entity)
    assert hp_in_zone == initial_hp, "Zone should not damage"
    assert len(zone.entries_tracked) > 0, "Zone should have tracked entry"

    # Move out of zone
    print("\n--- Moving to (7, 7) - outside zone ---")
    grid.move_entity(entity.uuid, (7, 7))
    entity.senses._position = (7, 7)
    Entity.update_all_entities_senses()

    # Move to tile effect
    print("\n--- Moving to (10, 10) - fire tile ---")
    grid.move_entity(entity.uuid, (10, 10))
    entity.senses._position = (10, 10)
    Entity.update_all_entities_senses()
    hp_on_fire = get_hp(entity)
    assert hp_on_fire < initial_hp, f"Should have taken fire damage! HP: {initial_hp} -> {hp_on_fire}"

    print(f"\nDamage taken from tile effect: {initial_hp - hp_on_fire}")
    print(f"Total zone entries tracked: {len(zone.entries_tracked)}")
    print("\n[PASS] Zone and tile effects coexist correctly!")


# ============================================================================
# Test 4: Cleanup removes spatial handler
# ============================================================================

def test_tile_effect_cleanup_removes_spatial_handler():
    """Removing TileEffectCondition removes its spatial handler."""
    print("\n" + "=" * 60)
    print("TEST: TileEffectCondition Cleanup Removes Spatial Handler")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a simple grid
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    # Create entity at (0, 0)
    entity = create_skeleton(name="Walker", position=(0, 0))
    Entity.update_all_entities_senses()

    initial_hp = get_hp(entity)

    # Create tile effect at (2, 0)
    fire_tile = grid.get_tile(2, 0)
    assert fire_tile is not None
    fire_effect = TestEntryDamageTile(
        source_entity_uuid=uuid4(),
        target_entity_uuid=fire_tile.uuid,
        damage_dice="2d6",
        damage_type=DamageType.FIRE,
    )
    fire_tile.add_condition(fire_effect)
    handler_uuid = fire_effect._entry_handler_uuid

    print(f"Handler UUID: {handler_uuid}")

    # Verify handler is in spatial index
    key = (EventType.SPATIAL_ENTITY_ENTERED, EventPhase.EFFECT)
    assert key in EventQueue._spatial_handlers_by_position
    assert (2, 0) in EventQueue._spatial_handlers_by_position[key]
    print("Handler is registered in spatial index")

    # Remove the condition
    fire_tile.remove_condition(fire_effect.name)
    print("Condition removed")

    # Verify handler is no longer in spatial index
    if key in EventQueue._spatial_handlers_by_position:
        assert (2, 0) not in EventQueue._spatial_handlers_by_position[key] or \
               len(EventQueue._spatial_handlers_by_position[key][(2, 0)]) == 0, \
               "Handler should be removed from spatial index"
    print("Handler no longer in spatial index")

    # Verify handler UUID is no longer in handler_positions
    assert handler_uuid not in EventQueue._handler_positions, \
           "Handler should be removed from position tracking"
    print("Handler no longer in position tracking")

    # Move to the position - should NOT take damage
    print("\n--- Moving to (2, 0) after cleanup ---")
    grid.move_entity(entity.uuid, (2, 0))
    entity.senses._position = (2, 0)
    Entity.update_all_entities_senses()
    final_hp = get_hp(entity)
    assert final_hp == initial_hp, f"Should not take damage after cleanup! HP: {initial_hp} -> {final_hp}"

    print(f"HP unchanged: {final_hp}")
    print("\n[PASS] Cleanup correctly removes spatial handler!")


# ============================================================================
# Test 5: Turn start handler still works (not spatial)
# ============================================================================

def test_turn_start_damage_still_works():
    """Turn start damage on tiles still functions correctly."""
    print("\n" + "=" * 60)
    print("TEST: Turn Start Damage Still Works")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a simple grid
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    # Create entity at (2, 0)
    entity = create_skeleton(name="Standing in Fire", position=(2, 0))
    Entity.update_all_entities_senses()

    initial_hp = get_hp(entity)
    print(f"Initial HP: {initial_hp}")

    # Create tile effect with turn start damage at (2, 0)
    fire_tile = grid.get_tile(2, 0)
    assert fire_tile is not None
    fire_effect = TestTurnStartDamageTile(
        source_entity_uuid=uuid4(),
        target_entity_uuid=fire_tile.uuid,
        damage_dice="1d6",
        damage_type=DamageType.FIRE,
    )
    fire_tile.add_condition(fire_effect)

    print(f"Entity standing on fire tile at (2, 0)")

    # Create an encounter and trigger turn start
    encounter = Encounter(name="Test Encounter", source_entity_uuid=uuid4())
    controller = PassController(source_entity_uuid=entity.uuid)
    encounter.add_combatant(entity, controller)
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()  # Must explicitly start turn to trigger TURN_START event

    # Check HP after turn start
    hp_after_turn_start = get_hp(entity)
    print(f"HP after turn start: {hp_after_turn_start}")

    assert hp_after_turn_start < initial_hp, \
           f"Should have taken turn start damage! HP: {initial_hp} -> {hp_after_turn_start}"

    print(f"Damage taken: {initial_hp - hp_after_turn_start}")
    print("\n[PASS] Turn start damage still works correctly!")


# ============================================================================
# Test 6: Backward compatibility with legacy handlers
# ============================================================================

def test_backward_compatibility_legacy_handlers():
    """Legacy handlers using add_event_handler with spatial triggers still work."""
    print("\n" + "=" * 60)
    print("TEST: Backward Compatibility with Legacy Handlers")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a simple grid
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    # Create entity at (0, 0)
    entity = create_skeleton(name="Walker", position=(0, 0))
    Entity.update_all_entities_senses()

    # Create a legacy-style handler (uses add_event_handler, not add_spatial_handler)
    legacy_fires = [0]

    def legacy_processor(event: Event, _: uuid4) -> None:
        legacy_fires[0] += 1
        return None

    legacy_handler = EventHandler(
        name="Legacy Spatial Handler",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT
        )],
        event_processor=legacy_processor
    )

    # Register using legacy method
    EventQueue.add_event_handler(legacy_handler)

    print("Registered legacy handler (fires for ALL positions)")

    # Move twice
    grid.move_entity(entity.uuid, (1, 0))
    entity.senses._position = (1, 0)
    Entity.update_all_entities_senses()

    grid.move_entity(entity.uuid, (2, 0))
    entity.senses._position = (2, 0)
    Entity.update_all_entities_senses()

    print(f"Legacy handler fired {legacy_fires[0]} times for 2 moves")
    assert legacy_fires[0] == 2, f"Legacy handler should fire for each move, got {legacy_fires[0]}"

    print("\n[PASS] Legacy handlers still work via backward compatibility!")


# ============================================================================
# Main
# ============================================================================

def main():
    """Run all migration tests."""
    print("=" * 60)
    print("LEGACY SPATIAL HANDLER MIGRATION TESTS")
    print("=" * 60)

    tests = [
        test_tile_effect_entry_fires_only_at_correct_position,
        test_multiple_tile_effects_efficient,
        test_tile_effect_and_zone_coexist,
        test_tile_effect_cleanup_removes_spatial_handler,
        test_turn_start_damage_still_works,
        test_backward_compatibility_legacy_handlers,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n[FAIL] {e}")
            failed += 1
        except Exception as e:
            print(f"\n[ERROR] {type(e).__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\nAll migration tests passed!")
    else:
        print("\nSome tests failed!")
        exit(1)


if __name__ == "__main__":
    main()
