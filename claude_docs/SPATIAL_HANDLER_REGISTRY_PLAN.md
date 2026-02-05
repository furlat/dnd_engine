# Spatial Handler Registry - Position-Indexed Implementation Plan

## STATUS: COMPLETE ✓

This infrastructure has been fully implemented and tested.

**Next step:** Implement zone spells using this infrastructure. See `claude_docs/ZONE_SPELLS_IMPLEMENTATION_PLAN.md`.

**Key implementation differences from original plan:**
- Used `SpatialHandler` class instead of generic `EventHandler` with position registration
- Method names: `add_spatial_handler()` instead of `register_spatial_handler()`
- Registries: `_spatial_handlers`, `_spatial_handlers_by_position`, `_handler_positions`
- `_apply()` returns 5-tuple: `(modifiers, handlers, sub_conditions, spatial_handlers, event)`
- `BaseCondition` has `spatial_handler_uuids` field for tracking
- `TileEffectCondition` is now minimal - subclasses implement their own `_apply()`

**Verification (ALL PASS):**
```bash
python examples/test_spatial_handler_registry.py
python examples/spatial_events_test.py
python examples/test_terrain_movement_system.py
python examples/test_legacy_migration.py
```

---

## Problem Statement (SOLVED)

### Current Architecture

```python
class EventQueue:
    _event_handlers: Dict[UUID, EventHandler]
    _event_handlers_by_trigger: Dict[Trigger, List[EventHandler]]
    _event_handlers_by_simple_trigger: Dict[Trigger, List[EventHandler]]  # (type, phase) only
    _event_handlers_by_source_entity_uuid: Dict[UUID, List[EventHandler]]
```

**No position indexing.** When a spatial event fires:

```python
def _get_handlers_for_event(cls, event: Event) -> List[EventHandler]:
    simple_trigger = Trigger(event_type=event.event_type, event_phase=event.phase)
    simple_handlers = cls._event_handlers_by_simple_trigger.get(simple_trigger, [])
    # Then iterates ALL handlers checking trigger match
```

**Result:** Every handler for `SPATIAL_ENTITY_ENTERED` fires for every entity movement, then each manually filters by position.

### Current Tile Effect Pattern

```python
# ZoneControlCondition creates N TileEffectConditions
# Each TileEffectCondition creates 1+ EventHandlers
# Each handler captures its tile's position in closure and checks:

def entry_damage_processor(event: Event, _) -> Optional[Event]:
    position = getattr(event, 'position', None)
    if position != tile.position:  # Manual position filter
        return None
    # ... process
```

**Cost:** O(tiles_in_all_zones × movements)

---

## Proposed Architecture

### New Index in EventQueue

```python
class EventQueue:
    # Existing indices...

    # NEW: Position-indexed spatial handlers
    # position -> handler_uuid -> handler
    _spatial_handlers_by_position: Dict[Tuple[int,int], Dict[UUID, EventHandler]] = defaultdict(dict)

    # NEW: Reverse lookup for batch operations
    # handler_uuid -> set of positions
    _positions_by_spatial_handler: Dict[UUID, Set[Tuple[int,int]]] = defaultdict(set)
```

### New Registration API

```python
class EventQueue:
    @classmethod
    def register_spatial_handler(
        cls,
        handler: EventHandler,
        positions: Set[Tuple[int, int]]
    ) -> None:
        """Register a handler for specific positions.

        The handler will ONLY be invoked for spatial events at these positions.
        Much more efficient than simple trigger matching.
        """
        # Store handler in main registry
        cls._event_handlers[handler.uuid] = handler
        cls._event_handlers_by_source_entity_uuid[handler.source_entity_uuid].append(handler)

        # Index by positions
        for pos in positions:
            cls._spatial_handlers_by_position[pos][handler.uuid] = handler
        cls._positions_by_spatial_handler[handler.uuid] = positions.copy()

    @classmethod
    def update_spatial_handler_positions(
        cls,
        handler_uuid: UUID,
        new_positions: Set[Tuple[int, int]]
    ) -> None:
        """Update the positions a spatial handler responds to.

        Efficiently computes delta and updates indices.
        Used when zones move.
        """
        old_positions = cls._positions_by_spatial_handler.get(handler_uuid, set())
        handler = cls._event_handlers.get(handler_uuid)
        if not handler:
            return

        # Remove from positions we're leaving
        for pos in old_positions - new_positions:
            cls._spatial_handlers_by_position[pos].pop(handler_uuid, None)
            # Clean up empty position entries
            if not cls._spatial_handlers_by_position[pos]:
                del cls._spatial_handlers_by_position[pos]

        # Add to new positions
        for pos in new_positions - old_positions:
            cls._spatial_handlers_by_position[pos][handler_uuid] = handler

        # Update reverse lookup
        cls._positions_by_spatial_handler[handler_uuid] = new_positions.copy()

    @classmethod
    def remove_spatial_handler(cls, handler_uuid: UUID) -> None:
        """Remove a spatial handler and clean up all position indices."""
        positions = cls._positions_by_spatial_handler.pop(handler_uuid, set())
        for pos in positions:
            cls._spatial_handlers_by_position[pos].pop(handler_uuid, None)
            if not cls._spatial_handlers_by_position[pos]:
                del cls._spatial_handlers_by_position[pos]

        # Also remove from main registries
        handler = cls._event_handlers.pop(handler_uuid, None)
        if handler:
            cls._event_handlers_by_source_entity_uuid[handler.source_entity_uuid].remove(handler)
```

### Modified Event Dispatch for Spatial Events

```python
class EventQueue:
    @classmethod
    def _get_handlers_for_event(cls, event: Event) -> List[EventHandler]:
        """Get all handlers that should process this event."""

        # Check if this is a spatial event with position
        if cls._is_spatial_event(event):
            return cls._get_spatial_handlers_for_event(event)

        # Original logic for non-spatial events...
        simple_trigger = Trigger(event_type=event.event_type, event_phase=event.phase)
        simple_handlers = cls._event_handlers_by_simple_trigger.get(simple_trigger, [])
        # ... rest of existing logic

    @classmethod
    def _is_spatial_event(cls, event: Event) -> bool:
        """Check if event is a spatial event type."""
        return event.event_type in (
            EventType.SPATIAL_ENTITY_ENTERED,
            EventType.SPATIAL_ENTITY_LEFT,
            EventType.SPATIAL_TILE_CHANGED
        )

    @classmethod
    def _get_spatial_handlers_for_event(cls, event: Event) -> List[EventHandler]:
        """Get handlers for a spatial event using position index.

        O(1) lookup by position instead of O(all_handlers).
        """
        position = getattr(event, 'position', None)
        if position is None:
            return []

        # Get handlers registered for this specific position
        position_handlers = cls._spatial_handlers_by_position.get(position, {})

        # Filter by event type and phase
        matching = []
        for handler in position_handlers.values():
            for trigger in handler.trigger_conditions:
                if trigger.event_type == event.event_type and trigger.event_phase == event.phase:
                    matching.append(handler)
                    break

        return matching
```

### Reset Method Update

```python
@classmethod
def reset(cls) -> None:
    """Clear all events and handlers."""
    # ... existing clears ...

    # NEW: Clear spatial indices
    cls._spatial_handlers_by_position.clear()
    cls._positions_by_spatial_handler.clear()
```

---

## Zone-Level Centralized Control

### Updated ZoneControlCondition

Instead of creating one handler per tile, the zone creates ONE handler and manages its positions:

```python
class ZoneControlCondition(BaseCondition):
    """Base condition for controlling a zone of tile effects."""

    # Geometry (existing)
    zone_center: Tuple[int, int]
    zone_shape: str  # "sphere", "cone", "line", "cube"
    zone_radius_feet: int
    zone_direction: Optional[Tuple[int, int]] = None

    # Computed positions (existing)
    affected_positions: Set[Tuple[int, int]] = Field(default_factory=set)

    # NEW: Zone-level handler UUIDs (instead of per-tile)
    _entry_handler_uuid: Optional[UUID] = None
    _turn_start_handler_uuid: Optional[UUID] = None
    _turn_end_handler_uuid: Optional[UUID] = None
    _movement_handler_uuid: Optional[UUID] = None  # For per-5ft damage

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        """Apply zone - compute positions and register zone-level handlers."""
        # Compute affected positions using shapes API
        self.affected_positions = self._compute_affected_positions()

        # Create zone-level handlers (NOT per-tile)
        handlers = self._create_zone_handlers()
        handler_uuids = []

        for handler in handlers:
            # Register with position indexing
            EventQueue.register_spatial_handler(handler, self.affected_positions)
            handler_uuids.append(handler.uuid)

        # Apply tile modifications (difficult terrain, etc.) - still per-tile
        self._apply_tile_modifications()

        return [], handler_uuids, [], effect_event

    def _create_zone_handlers(self) -> List[EventHandler]:
        """Create zone-level handlers. Override in subclasses."""
        handlers = []

        if self._has_entry_effect():
            handler = self._create_entry_handler()
            self._entry_handler_uuid = handler.uuid
            handlers.append(handler)

        if self._has_turn_start_effect():
            handler = self._create_turn_start_handler()
            self._turn_start_handler_uuid = handler.uuid
            handlers.append(handler)

        # etc.
        return handlers

    def _create_entry_handler(self) -> EventHandler:
        """Create handler for entry effects. No position check needed!"""
        zone_uuid = self.uuid

        def entry_processor(event: Event, _) -> Optional[Event]:
            # Position already verified by EventQueue dispatch!
            # Just process the effect
            entity_uuid = getattr(event, 'entity_uuid', None)
            if not entity_uuid:
                return None

            # Get zone and apply effect
            zone = BaseObject.get(zone_uuid)
            if zone:
                zone._apply_entry_effect(entity_uuid, event.position)
            return None

        return EventHandler(
            name=f"{self.name} Entry Effect",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=entry_processor
        )

    def move_zone(self, new_center: Tuple[int, int]) -> None:
        """Move the zone to a new position.

        Updates position index efficiently - no handler recreation needed.
        """
        old_positions = self.affected_positions

        # Recompute affected positions
        self.zone_center = new_center
        new_positions = self._compute_affected_positions()
        self.affected_positions = new_positions

        # Update handler positions in EventQueue
        for handler_uuid in self._get_handler_uuids():
            if handler_uuid:
                EventQueue.update_spatial_handler_positions(handler_uuid, new_positions)

        # Update tile modifications (difficult terrain)
        self._update_tile_modifications(old_positions, new_positions)

    def _get_handler_uuids(self) -> List[Optional[UUID]]:
        """Get all handler UUIDs managed by this zone."""
        return [
            self._entry_handler_uuid,
            self._turn_start_handler_uuid,
            self._turn_end_handler_uuid,
            self._movement_handler_uuid
        ]

    def remove(self) -> None:
        """Remove zone and all associated handlers."""
        # Remove handlers from spatial registry
        for handler_uuid in self._get_handler_uuids():
            if handler_uuid:
                EventQueue.remove_spatial_handler(handler_uuid)

        # Remove tile modifications
        self._remove_tile_modifications()

        # Call parent remove
        super().remove()
```

### Tile Modifications (Separate from Handlers)

Tile modifications (difficult terrain, obscurement) are still applied per-tile, but simpler:

```python
def _apply_tile_modifications(self) -> None:
    """Apply non-handler modifications to tiles (difficult terrain, etc.)."""
    grid = get_map()
    for pos in self.affected_positions:
        tile = grid.get_tile(*pos)
        if tile and self._modifies_terrain():
            # Add difficult terrain modifier
            mod = NumericalModifier.create(
                source_entity_uuid=self.uuid,  # Zone is the source
                name=f"{self.name} Difficult Terrain",
                value=1
            )
            mod_uuid = tile.walking_cost.self_static.add_value_modifier(mod)
            self._tile_modifier_uuids.append((tile.uuid, mod_uuid))

def _update_tile_modifications(
    self,
    old_positions: Set[Tuple[int,int]],
    new_positions: Set[Tuple[int,int]]
) -> None:
    """Update tile modifications when zone moves."""
    grid = get_map()

    # Remove from tiles we're leaving
    for pos in old_positions - new_positions:
        tile = grid.get_tile(*pos)
        if tile:
            self._remove_modifier_from_tile(tile)

    # Add to new tiles
    for pos in new_positions - old_positions:
        tile = grid.get_tile(*pos)
        if tile:
            self._add_modifier_to_tile(tile)
```

---

## Integration with Shapes API

The zone uses AoE shapes to compute affected positions:

```python
def _compute_affected_positions(self) -> Set[Tuple[int, int]]:
    """Compute affected positions using shapes API."""
    from dnd.core.aoe import Sphere, Cone, Line, Cube

    shape_classes = {
        "sphere": Sphere,
        "cone": Cone,
        "line": Line,
        "cube": Cube,
    }

    ShapeClass = shape_classes.get(self.zone_shape, Sphere)

    # Create shape instance
    if self.zone_shape in ("cone", "line") and self.zone_direction:
        shape = ShapeClass(
            source_entity_uuid=self.source_entity_uuid,
            target=self.zone_center,
            radius_feet=self.zone_radius_feet,
            direction=self.zone_direction
        )
    else:
        shape = ShapeClass(
            source_entity_uuid=self.source_entity_uuid,
            target=self.zone_center,
            radius_feet=self.zone_radius_feet
        )

    shape.compute_objective(self.zone_center)
    return set(shape.affected_positions)
```

---

## Spirit Guardians - Now Simple

With this infrastructure, Spirit Guardians is just another zone that updates on caster movement:

```python
class SpiritGuardiansZone(ZoneControlCondition):
    """Zone that follows the caster."""
    name: str = "Spirit Guardians"
    zone_shape: str = "sphere"
    zone_radius_feet: int = 15

    # Track entities affected this round (once per turn mechanic)
    _triggered_this_round: Set[UUID] = Field(default_factory=set)

    # Handler for tracking caster movement
    _caster_movement_handler_uuid: Optional[UUID] = None

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        # Standard zone setup
        result = super()._apply(declaration_event)

        # ALSO register handler for caster movement
        caster_handler = self._create_caster_movement_handler()
        EventQueue.add_event_handler(caster_handler)  # Regular handler, not spatial
        self._caster_movement_handler_uuid = caster_handler.uuid

        # Register handler to clear triggered set at caster's turn start
        clear_handler = self._create_round_clear_handler()
        EventQueue.add_event_handler(clear_handler)

        return result

    def _create_caster_movement_handler(self) -> EventHandler:
        """Handler that moves zone when caster moves."""
        zone_uuid = self.uuid
        caster_uuid = self.source_entity_uuid

        def caster_moved_processor(event: Event, _) -> Optional[Event]:
            # Only react to caster's movement
            if getattr(event, 'entity_uuid', None) != caster_uuid:
                return None

            # Get new position from event
            new_position = getattr(event, 'position', None)
            if not new_position:
                return None

            # Move the zone
            zone = BaseObject.get(zone_uuid)
            if zone:
                zone.move_zone(new_position)

            return None

        return EventHandler(
            name=f"{self.name} Follow Caster",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.COMPLETION  # After movement completes
            )],
            event_processor=caster_moved_processor
        )

    def _apply_entry_effect(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
        """Apply damage when enemy enters (once per turn)."""
        # Check once per turn
        if entity_uuid in self._triggered_this_round:
            return

        # Check if enemy
        entity = Entity.get(entity_uuid)
        caster = Entity.get(self.source_entity_uuid)
        if not caster.is_enemy(entity):
            return

        # Apply save and damage
        # ...

        # Mark as triggered
        self._triggered_this_round.add(entity_uuid)
```

---

## Cloudkill - Auto-Movement

```python
class CloudkillZone(ZoneControlCondition):
    """Zone that auto-moves away from caster each turn."""
    name: str = "Cloudkill"
    zone_shape: str = "sphere"
    zone_radius_feet: int = 20

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        result = super()._apply(declaration_event)

        # Register handler for caster's turn start to move zone
        auto_move_handler = self._create_auto_move_handler()
        EventQueue.add_event_handler(auto_move_handler)
        self._auto_move_handler_uuid = auto_move_handler.uuid

        return result

    def _create_auto_move_handler(self) -> EventHandler:
        """Handler that moves zone 10ft away from caster at turn start."""
        zone_uuid = self.uuid
        caster_uuid = self.source_entity_uuid

        def auto_move_processor(event: Event, _) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None
            if event.source_entity_uuid != caster_uuid:
                return None

            zone = BaseObject.get(zone_uuid)
            if zone:
                caster = Entity.get(caster_uuid)
                new_center = zone._calculate_position_away_from(
                    caster.senses.position,
                    distance_feet=10
                )
                zone.move_zone(new_center)

            return None

        return EventHandler(
            name=f"{self.name} Auto Move",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=caster_uuid
            )],
            event_processor=auto_move_processor
        )
```

---

## Methods Affected in EventQueue

### New Methods

| Method | Purpose |
|--------|---------|
| `register_spatial_handler(handler, positions)` | Register handler with position index |
| `update_spatial_handler_positions(uuid, new_positions)` | Batch update positions |
| `remove_spatial_handler(uuid)` | Remove and clean up indices |
| `_is_spatial_event(event)` | Check if event is spatial type |
| `_get_spatial_handlers_for_event(event)` | O(1) position lookup |

### Modified Methods

| Method | Change |
|--------|--------|
| `_get_handlers_for_event(event)` | Check for spatial events first |
| `reset()` | Clear new spatial indices |

### Unchanged Methods

| Method | Notes |
|--------|-------|
| `add_event_handler()` | Still works for non-spatial handlers |
| `remove_event_handler()` | Still works, but `remove_spatial_handler` preferred for spatial |
| `register()` | No change - dispatches to handlers |
| `_store_event()` | No change |

---

## Implementation Order

### Phase 1: EventQueue Spatial Registry (Foundation) ✓ COMPLETE

1. ✓ Added new class attributes:
   - `_spatial_handlers: Dict[UUID, SpatialHandler]`
   - `_spatial_handlers_by_position: Dict[(EventType, EventPhase), Dict[pos, Set[UUID]]]`
   - `_handler_positions: Dict[UUID, (Set[pos], EventType, EventPhase)]`

2. ✓ Added new methods:
   - `add_spatial_handler(handler, positions?, event_type?, event_phase?)`
   - `update_spatial_handler_positions(uuid, new_positions, event_type, event_phase)`
   - `remove_spatial_handler(uuid)`

3. ✓ Modified `_get_handlers_for_event()` to check spatial events

4. ✓ Modified `reset()` to clear spatial indices

5. ✓ **Tested:** `examples/test_spatial_handler_registry.py`

### Phase 2: Update ZoneControlCondition ✓ COMPLETE

1. ✓ `TileEffectCondition` is now minimal (just `get_tile()` helper)
2. ✓ Zone-level handler management in `ZoneControlCondition`
3. ✓ `move_zone()` uses `update_spatial_handler_positions()`
4. ✓ Terrain modifiers separate from handlers

5. ✓ **Tested:** `examples/test_terrain_movement_system.py`

### Phase 3: Update Existing Tile Conditions ✓ COMPLETE

1. ✓ `TileEffectCondition` base class is minimal - subclasses implement `_apply()`
2. ✓ Test subclasses in `examples/test_terrain_movement_system.py` refactored
3. ✓ Test subclasses in `examples/test_legacy_migration.py` refactored
4. ✓ Entry damage, turn start damage verified working

### Phase 4: Implement Zone Spells - PENDING

See `claude_docs/ZONE_SPELLS_IMPLEMENTATION_PLAN.md` for spell implementation details.

1. Spike Growth (static zone, per-5ft damage)
2. Grease (static zone, turn-end handler)
3. Web (static zone, escape action)
4. Cloudkill (auto-moving zone)
5. Spirit Guardians (caster-following zone)

---

## Backward Compatibility

The old `TileEffectCondition._create_entry_damage_handler()` pattern can still work:
- Handlers registered via `add_event_handler()` still fire for all spatial events
- They still manually check position in processor
- Just less efficient

New code should use `register_spatial_handler()` for efficiency.

---

## Performance Analysis

### Before (Current)
- Zone with N tiles creates N handlers
- Each movement fires N handlers
- Each handler checks position: O(N) per movement
- Total: O(zones × tiles_per_zone × movements)

### After (Proposed)
- Zone creates 1 handler, registered for N positions
- Movement at position P only fires handlers registered for P
- Lookup: O(1) via position dict
- Total: O(handlers_at_position × movements)

For typical case (few overlapping zones): **O(1) per movement**

---

## Open Questions Resolved

**Q: How to handle "first time on a turn"?**
A: Store `_triggered_this_round: Set[UUID]` on zone, clear at caster's turn start.

**Q: Speed halving in Spirit Guardians?**
A: Apply modifier when entity enters zone (track in `_entities_in_aura`), remove when they leave. Zone-level handler for SPATIAL_ENTITY_LEFT handles removal.

**Q: Escape action for Web?**
A: When WebRestrained is applied, also register action template. Condition tracks action UUID for cleanup.
