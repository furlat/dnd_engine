# Zone Spells Implementation Plan

## Status: Infrastructure COMPLETE

The spatial handler infrastructure is fully implemented and tested. This document describes how to implement zone spells using the **subclass pattern** - each spell creates its own condition subclass with custom `_apply()` logic.

---

## Implemented Infrastructure

### SpatialHandler System (COMPLETE)

- `BaseHandler` class in `dnd/core/events.py`
- `SpatialHandler` class for position-indexed handlers
- Separate registries: `_spatial_handlers`, `_spatial_handlers_by_position`
- Methods: `add_spatial_handler()`, `remove_spatial_handler()`, `update_spatial_handler_positions()`
- 5-tuple return signature for `_apply()`: `(modifiers, handlers, sub_conditions, spatial_handlers, event)`
- `spatial_handler_uuids` field on `BaseCondition`
- All 56 conditions updated to new signature

### Base Classes (MINIMAL - No Spell-Specific Fields)

From `dnd/tile_conditions.py`:

```python
# TileEffectCondition - MINIMAL base class (actual code)
class TileEffectCondition(BaseCondition):
    """
    Base condition applied to tiles by zone spells.

    The target_entity_uuid is the tile's UUID.
    Subclasses override _apply() to add specific effects (terrain modifiers,
    damage handlers, obscurement, etc.).

    This is a minimal base class - spell-specific logic belongs in subclasses.
    """
    name: str = "Tile Effect"
    description: str = "A tile effect from a zone spell"

    model_config = {"arbitrary_types_allowed": True}

    def get_tile(self) -> Optional[Tile]:
        """Helper to get the tile this condition is applied to."""
        if self.target_entity_uuid is None:
            return None
        grid = get_map()
        return grid.get_tile_by_uuid(self.target_entity_uuid)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Subclasses must override to add specific effects.

        Default implementation does nothing - returns empty lists.
        """
        effect_event = None
        if declaration_event is not None:
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return [], [], [], [], effect_event
```

`ZoneControlCondition` retains more structure because it manages a zone of tiles:
- `zone_center`, `zone_shape`, `zone_radius_feet` - geometry fields
- `adds_difficult_terrain` - convenience for terrain modifier on all tiles
- Override points: `_has_entry_effect()`, `_create_zone_entry_handler()`, etc.

### Verification Commands (ALL PASS)

```bash
python examples/test_spatial_handler_registry.py
python examples/spatial_events_test.py
python examples/test_terrain_movement_system.py
python examples/test_legacy_migration.py
```

---

## Architecture Patterns

### Pattern 1: Static Tile-Based (Spike Growth, Grease, Web)

Zone is fixed at cast position. Each spell creates:
- A `ZoneControlCondition` subclass that manages the zone
- A `TileEffectCondition` subclass with custom `_apply()` for tile-level effects

```
Caster: Concentrating(spell_name="Web")
    └── external_conditions ──► WebZone (on caster)
                                    └── terrain_conditions ──► WebTileEffect (on each tile)
```

### Pattern 2: Controlled Movement (Cloudkill)

Zone can move automatically. The zone subclass adds a TURN_START handler.

```
Caster: Concentrating(spell_name="Cloudkill")
    └── external_conditions ──► CloudkillZone (on caster)
                                    ├── terrain_conditions ──► CloudkillTileEffect
                                    └── EventHandler: TURN_START → move_zone()
```

### Pattern 3: Caster-Centered (Spirit Guardians)

Zone follows caster using `move_zone()` which is now efficient thanks to `update_spatial_handler_positions()`.

```
Caster: Concentrating(spell_name="Spirit Guardians")
    └── external_conditions ──► SpiritGuardiansZone (on caster)
                                    ├── SpatialHandler: SPATIAL_ENTITY_ENTERED (damage on entry)
                                    ├── EventHandler: TURN_START (damage if still in zone)
                                    ├── EventHandler: caster SPATIAL_ENTITY_ENTERED → move_zone()
                                    └── Speed modifiers on affected entities
```

---

## The Subclass Pattern

**CRITICAL**: Spell-specific logic belongs in subclasses, NOT in base class fields.

### Example: Spike Growth Tile Effect

```python
# In dnd/spells/transmutation.py
class SpikeGrowthTileEffect(TileEffectCondition):
    """Spike Growth - deals 2d4 piercing per 5ft traveled."""
    name: str = "Spike Growth"
    description: str = "Camouflaged ground covered with spikes"

    # Spell-specific fields (NOT on base class)
    spell_dc: int = 10
    damage_dice: str = "2d4"

    def _apply(self, declaration_event) -> Tuple[...]:
        """Add difficult terrain modifier and entry damage handler."""
        outs = []
        spatial_handler_uuids = []
        tile = self.get_tile()

        if tile:
            # 1. Add difficult terrain modifier
            mod = NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                name="Spike Growth Difficult Terrain",
                value=1
            )
            mod_uuid = tile.walking_cost.self_static.add_value_modifier(mod)
            outs.append((tile.walking_cost.uuid, mod_uuid))

            # 2. Create entry damage handler
            handler = self._create_spike_damage_handler(tile)
            EventQueue.add_spatial_handler(handler)
            spatial_handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(EventPhase.EFFECT) if declaration_event else None
        return outs, [], [], spatial_handler_uuids, effect_event

    def _create_spike_damage_handler(self, tile: Tile) -> SpatialHandler:
        """Create handler for spike damage on entry."""
        def processor(event: Event, _) -> Optional[Event]:
            entity_uuid = getattr(event, 'entity_uuid', None)
            if not entity_uuid:
                return None
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            # Deal 2d4 piercing damage
            count, value = parse_dice_string(self.damage_dice)
            damage = sum(random.randint(1, value) for _ in range(count))
            entity.health.take_damage(damage, DamageType.PIERCING, source_entity_uuid=self.source_entity_uuid)
            return None

        return SpatialHandler(
            name="Spike Growth Entry Damage",
            source_entity_uuid=tile.uuid,
            positions={tile.position},
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT,
            event_processor=processor
        )
```

### Example: Web Tile Effect (with Save)

```python
class WebTileEffect(TileEffectCondition):
    """Web - DEX save or Restrained."""
    name: str = "Web"
    spell_dc: int = 13  # Set from caster's spell DC

    def _apply(self, declaration_event) -> Tuple[...]:
        outs = []
        spatial_handler_uuids = []
        tile = self.get_tile()

        if tile:
            # 1. Difficult terrain
            mod = NumericalModifier.create(...)
            mod_uuid = tile.walking_cost.self_static.add_value_modifier(mod)
            outs.append((tile.walking_cost.uuid, mod_uuid))

            # 2. Entry save handler
            handler = self._create_web_entry_handler(tile)
            EventQueue.add_spatial_handler(handler)
            spatial_handler_uuids.append(handler.uuid)

        return outs, [], [], spatial_handler_uuids, effect_event

    def _create_web_entry_handler(self, tile: Tile) -> SpatialHandler:
        """DEX save or become Restrained."""
        def processor(event: Event, _) -> Optional[Event]:
            entity = Entity.get(getattr(event, 'entity_uuid', None))
            if not entity:
                return None

            # Make DEX save
            save_result = entity.saving_throw(SavingThrowRequest(
                ability="dexterity",
                dc=self.spell_dc,
                source_entity_uuid=self.source_entity_uuid
            ))

            if not save_result.success:
                # Apply WebRestrained (which has Restrained as sub-condition)
                restrained = WebRestrained(
                    source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=entity.uuid,
                    spell_dc=self.spell_dc
                )
                entity.add_condition(restrained)

            return None

        return SpatialHandler(...)
```

### Working Reference: Test Subclasses

The actual working implementations are in `examples/test_terrain_movement_system.py`.

**TestDifficultTerrain** - Adds terrain modifier:
```python
class TestDifficultTerrain(TileEffectCondition):
    name: str = "Test Difficult"
    description: str = "Test difficult terrain effect"

    def _apply(self, declaration_event):
        from dnd.core.events import EventPhase
        outs = []
        tile = self.get_tile()
        if tile:
            mod = NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                name=f"{self.name} Difficult Terrain",
                value=1  # +1 to walking cost (total = 2)
            )
            mod_uuid = tile.walking_cost.self_static.add_value_modifier(mod)
            outs.append((tile.walking_cost.uuid, mod_uuid))

        effect_event = None
        if declaration_event is not None:
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return outs, [], [], [], effect_event
```

**TestFireTile** - Entry damage with SpatialHandler:
```python
class TestFireTile(TileEffectCondition):
    name: str = "Test Fire"
    description: str = "Burns entities that enter"

    def _apply(self, declaration_event):
        from dnd.core.events import EventPhase, EventQueue
        spatial_handler_uuids = []
        tile = self.get_tile()
        if tile:
            handler = self._create_entry_damage_handler(tile, "1d6", DamageType.FIRE)
            EventQueue.add_spatial_handler(handler)
            spatial_handler_uuids.append(handler.uuid)

        effect_event = None
        if declaration_event is not None:
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return [], [], [], spatial_handler_uuids, effect_event

    def _create_entry_damage_handler(self, tile, damage_dice_str, damage_type):
        from dnd.core.events import EventType, EventPhase, SpatialHandler
        from dnd.tile_conditions import parse_dice_string
        import random

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
```

**TestSpikedFloor** - Turn start damage with EventHandler:
```python
class TestSpikedFloor(TileEffectCondition):
    name: str = "Test Spikes"
    description: str = "Damages at turn start"

    def _apply(self, declaration_event):
        from dnd.core.events import EventPhase, EventQueue
        handler_uuids = []
        tile = self.get_tile()
        if tile:
            handler = self._create_turn_start_damage_handler(tile.uuid, "1d4", DamageType.PIERCING)
            EventQueue.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

        effect_event = None
        if declaration_event is not None:
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return [], handler_uuids, [], [], effect_event

    def _create_turn_start_damage_handler(self, tile_uuid, damage_dice_str, damage_type):
        from dnd.core.events import EventType, EventPhase, EventHandler, Trigger
        from dnd.tile_conditions import parse_dice_string
        import random

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
```

Also see `examples/test_legacy_migration.py` for:
- `TestEntryDamageTile` - Entry damage with configurable dice/type
- `TestTurnStartDamageTile` - Turn start damage with configurable dice/type

---

## Design Decisions (Formerly "Open Questions")

### D1: Per-5ft Damage

Use `SPATIAL_ENTITY_ENTERED` - it fires per cell via Move action. Each tile's `_apply()` creates a SpatialHandler at its position.

### D2: "First Time on a Turn" Tracking

Apply a marker condition (e.g., `SpiritGuardiansTriggered`) to the entity when damaged. Entry handler checks `entity.has_condition("SpiritGuardiansTriggered")` before applying damage. Marker is removed at entity's turn end (1-round duration).

### D3: Speed Halving (Spirit Guardians)

Apply a condition (e.g., `SpiritGuardiansSlowed`) to entities when they enter the zone. Exit handler removes the condition. The condition itself contains the speed modifier - no separate tracking needed.

### D4: Escape Action Linking

1. `WebTileEffect` creates `WebRestrained` on entity
2. `WebRestrained._apply()` creates `EscapeRestrainedAction` template
3. Action stores `restraining_condition_uuid`
4. On success: action removes condition, condition removal removes action template
5. On dispel: condition removal removes action template

### D5: Initial Cast Saves

In zone's `_apply()`, iterate `affected_positions`, find entities at each position via `Entity.get_entities_at_position()`, trigger saves immediately.

---

## Spell Implementations

### Spike Growth (Transmutation)

**File**: `dnd/spells/transmutation.py`

**Components**:
- `SpikeGrowthTileEffect(TileEffectCondition)` - Custom `_apply()` with terrain + entry damage
- `SpikeGrowthZone(ZoneControlCondition)` - Creates tile effects at positions
- `SpikeGrowth(SpellAction)` - Creates zone, links to Concentrating

### Grease (Conjuration)

**File**: `dnd/spells/conjuration.py`

**Components**:
- `GreaseTileEffect(TileEffectCondition)` - Custom `_apply()` with DEX save on entry + turn end
- `GreaseZone(ZoneControlCondition)` - Creates tile effects, handles initial saves
- `Grease(SpellAction)` - Creates zone, links to Concentrating

### Web (Conjuration)

**File**: `dnd/spells/conjuration.py`

**Components**:
- `WebTileEffect(TileEffectCondition)` - Custom `_apply()` with DEX save on entry
- `WebRestrained(BaseCondition)` - Has Restrained as sub-condition, grants escape action
- `EscapeRestrainedAction(BaseAction)` - STR check to escape
- `WebZone(ZoneControlCondition)` - Creates tile effects
- `Web(SpellAction)` - Creates zone, links to Concentrating

### Cloudkill (Conjuration)

**File**: `dnd/spells/conjuration.py`

**Components**:
- `CloudkillTileEffect(TileEffectCondition)` - Custom `_apply()` with CON save + damage on entry/turn
- `CloudkillZone(ZoneControlCondition)` - Override `_apply()` to add TURN_START movement handler
- `Cloudkill(SpellAction)` - Creates zone, links to Concentrating

### Spirit Guardians (Conjuration)

**File**: `dnd/spells/conjuration.py`

**Components**:
- `SpiritGuardiansZone(ZoneControlCondition)` - Zone that follows caster
- `SpiritGuardiansTriggered(BaseCondition)` - Marker (1-round), prevents repeat damage
- `SpiritGuardiansSlowed(BaseCondition)` - Has speed halving modifier
- Override `_apply()` to:
  - Call `super()._apply()` for standard zone setup
  - Add EventHandler for caster's `SPATIAL_ENTITY_ENTERED` → calls `move_zone()`
- Override `_has_entry_effect()` → True, `_has_exit_effect()` → True
- Entry handler:
  - Skip if `entity.has_condition("SpiritGuardiansTriggered")`
  - WIS save + damage
  - Apply `SpiritGuardiansTriggered` marker
  - Apply `SpiritGuardiansSlowed` condition
- Exit handler:
  - Remove `SpiritGuardiansSlowed` condition
- `SpiritGuardians(SpellAction)` - Creates zone, links to Concentrating

---

## File Changes Summary

### New Files
- `dnd/spells/transmutation.py` - Spike Growth

### Modified Files
- `dnd/spells/conjuration.py` - Grease, Web, Cloudkill, Spirit Guardians
- `dnd/spells/__init__.py` - exports
- `dnd/actions.py` - `EscapeRestrainedAction`
- `dnd/tile_conditions.py` - **NO CHANGES** (base classes stay minimal)

### Test Files
- `examples/test_spike_growth.py`
- `examples/test_grease.py`
- `examples/test_web.py`
- `examples/test_cloudkill.py`
- `examples/test_spirit_guardians.py`

---

## Key Principles

1. **Base classes are minimal** - Only helpers like `get_tile()`, no spell-specific fields
2. **Subclasses own their logic** - Each spell's `_apply()` does exactly what that spell needs
3. **No field bloat** - Don't add 15 fields to handle every possible spell variation
4. **Test subclasses as examples** - See `examples/test_terrain_movement_system.py` for patterns
5. **Spatial handlers for position-based** - Use `SpatialHandler` for efficient O(1) lookup
6. **Event handlers for non-spatial** - Use `EventHandler` for turn start/end effects
