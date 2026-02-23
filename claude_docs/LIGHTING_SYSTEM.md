# Lighting System (Layer 2) — Implementation Reference

## Status

**Implemented and tested** — 77 tests pass (`examples/test_lighting_system.py`), 130 stealth tests pass (no regressions).

Performance profiling done (`examples/test_light_source_perf.py`). Scaling issues identified with multiple observers — see [Performance Problems](#performance-problems) section.

---

## Architecture Overview

```
Spells / Light Sources / GridMap        Tile light storage (two dicts)
+-------------------------------+       +----------------------------------------+
| Darkness spell                |--add->| _obscurements: Dict[UUID, LightLevel]  |
| FogCloud                      |--add->|                                        |
| GridMap.add_light_source()    |--add->| _illuminations: Dict[UUID, LightLevel] |
| Torch._on_ignite()           |--add->| default_light: LightLevel              |
+-------------------------------+       +----------------------------------------+
                                                    |
                                                    v property
                                        resolved_light_level
                                        = MAX(default, illuminations)
                                          then MIN(result, obscurements)
                                                    |
                                                    v per-observer query
                                        Tile.get_effective_light_for(observer_uuid)
                                                    |
                                   Tile calls observer.get_sense_modes()
                                   via BaseBlock polymorphism
```

### Two Fundamentally Different Light Effects

**This distinction is critical for understanding the system and its performance characteristics.**

| Effect | Mechanism | What Changes | Example |
|--------|-----------|-------------|---------|
| **Normal light change** (DARKNESS ↔ DIM ↔ BRIGHT ↔ VERY_BRIGHT) | Visibility + entity/object filtering | `senses.visible` updated (dark tiles removed, lit tiles added), entities and objects re-filtered. FOV geometry unchanged. | Torch lit/extinguished, Fog Cloud |
| **Magical darkness** (MAGICAL_DARKNESS) | FOV geometry change | `blocks_vision()` returns True → tiles behind it become invisible. Like a temporary wall for vision. | Darkness spell |

Normal light changes are cheap to process — no shadowcast needed, just per-position light checks on `senses.visible`, entities, and objects. Magical darkness is expensive — it changes FOV geometry, potentially hiding tiles that were previously visible (and revealing them when removed).

---

## LightLevel Enum (`base_tiles.py:30-37`)

```python
class LightLevel(int, Enum):
    MAGICAL_DARKNESS = 0   # Darkness spell — blocks FOV (like wall for vision)
    DARKNESS = 1           # No light — entities invisible, tiles still in FOV
    DIM_LIGHT = 2          # Shadows — entities visible, hide action relaxed
    BRIGHT_LIGHT = 3       # Normal daylight — standard rules
    VERY_BRIGHT = 4        # Daylight spell — auto-reveals Hidden
```

Int values are for ordering comparisons only. Darkvision shifting uses explicit mapping (NOT arithmetic):

```python
_DARKVISION_SHIFT = {
    LightLevel.DARKNESS: LightLevel.DIM_LIGHT,
    LightLevel.DIM_LIGHT: LightLevel.BRIGHT_LIGHT,
}
```

---

## Tile Light Storage (`base_tiles.py:159-163`)

Two separate dictionaries on Tile, keyed by source UUID:

```python
default_light: LightLevel = LightLevel.BRIGHT_LIGHT  # Base level (outdoor=BRIGHT, dungeon=DARKNESS)
_illuminations: Dict[UUID, LightLevel]  # Light sources that brighten (torch, Light spell)
_obscurements: Dict[UUID, LightLevel]   # Darkness effects that darken (Fog Cloud, Darkness spell)
```

**Resolution** (`resolved_light_level` property, `base_tiles.py:243-253`):
```
result = MAX(default_light, all illuminations)    # Lights can only brighten
result = MIN(result, darkest obscurement)          # Darkness overrides everything
```

**Examples:**
- Dark dungeon (DARKNESS) + torch (BRIGHT): MAX(1,3)=3 → **BRIGHT**
- Dark dungeon + torch + Fog Cloud (DARKNESS obscurement): MAX(1,3)=3, MIN(3,1)=1 → **DARKNESS**
- Bright outdoor + Darkness spell (MAGICAL_DARKNESS obscurement): MAX(3)=3, MIN(3,0)=0 → **MAGICAL_DARKNESS**

### Tile Light Methods

All return `bool` (whether resolved level changed) and accept `fire_event: bool = True`:

| Method | Purpose |
|--------|---------|
| `add_illumination(uuid, level)` | Add light source (torch, Light spell) |
| `add_obscurement(uuid, level)` | Add darkness effect (Fog Cloud, Darkness spell) |
| `remove_light_modifier(uuid)` | Remove from either dict by UUID |

The `fire_event` parameter enables **batch operations**: GridMap passes `fire_event=False` when modifying many tiles, then fires a single consolidated event afterward.

### _notify_light_changed() (`base_tiles.py:313-329`)

Fires full `SPATIAL_LIGHT_CHANGED` event lifecycle (DECLARATION → EXECUTION → EFFECT → COMPLETION). Same pattern as `BaseBlock._notify_perceivability_changed()`.

---

## Observer-Subjective Light (`base_tiles.py:255-311`)

`Tile.get_effective_light_for(observer_uuid, observer_position)` resolves what a specific observer sees at this tile. Resolution order:

1. Start with `resolved_light_level` (objective)
2. **Truesight/Blindsight** (within range): upgrade to at least BRIGHT_LIGHT
3. **Devil's Sight** (within range): MAGICAL_DARKNESS/DARKNESS → BRIGHT_LIGHT (see normally)
4. **Darkvision** (within range): DARKNESS → DIM_LIGHT, DIM_LIGHT → BRIGHT_LIGHT
5. **Adjacent rule** (last): minimum DIM_LIGHT at Chebyshev distance ≤ 1, natural DARKNESS only (not magical)

### Magical Darkness Blocks FOV (`base_tiles.py:184-200`)

`blocks_vision(requesting_entity_uuid)` now checks magical darkness:

```python
if self.resolved_light_level == LightLevel.MAGICAL_DARKNESS:
    # Blocked unless observer has TRUESIGHT or DEVILS_SIGHT
    sense_modes = observer.get_sense_modes()
    if not any(sm.sense_type in (SensesType.TRUESIGHT, SensesType.DEVILS_SIGHT) ...):
        return True  # Blocks vision like a wall
```

This is threaded through `GridMap.is_blocking()` and `GridMap.compute_fov()` via `observer_uuid` parameter.

---

## Sense Modes

### Types (`base_tiles.py:44-55`)

```python
class SensesType(str, Enum):
    BLINDSIGHT = "Blindsight"      # See without sight, ignores all darkness
    DARKVISION = "Darkvision"      # See in dark as dim, dim as bright (not magical darkness)
    TREMORSENSE = "Tremorsense"    # Detect via vibrations
    TRUESIGHT = "Truesight"        # See through everything including magical darkness
    DEVILS_SIGHT = "Devils Sight"  # Pierces magical darkness specifically

class SenseMode(BaseModel):
    sense_type: SensesType
    range_feet: int = 0  # 0 = unlimited
```

### Override Chain (BaseBlock polymorphism)

```
BaseBlock.get_sense_modes()    → []                        (base_block.py)
Senses.get_sense_modes()       → self.sense_modes          (sensory.py)
Entity.get_sense_modes()       → self.senses.get_sense_modes()  (entity.py)
```

Tile calls `BaseBlock.get(observer_uuid).get_sense_modes()` — gets Entity → relays to Senses block.

### Senses Block (`sensory.py`)

```python
sense_modes: List[SenseMode] = Field(default_factory=list)

def has_sense(self, sense_type: SensesType) -> bool
def has_sense_in_range(self, sense_type: SensesType, distance_feet: int) -> bool
def get_sense_range(self, sense_type: SensesType) -> int  # -1 = not present, 0 = unlimited
```

---

## Light Sources (`gridmap.py`)

### LightSourceData (`gridmap.py:25-33`)

```python
class LightSourceData(BaseModel):
    uuid: UUID
    position: Tuple[int, int]
    bright_radius_feet: int
    dim_radius_feet: int
    anchor_uuid: Optional[UUID] = None     # Follows this BaseBlock's movement
    affected_tiles: Dict[pos, LightLevel]  # Current tile → level mapping
    is_active: bool = True
```

### GridMap Methods

| Method | What it does |
|--------|-------------|
| `add_light_source(pos, bright_r, dim_r, anchor_uuid)` | Create light source, apply illumination to tiles via FOV |
| `remove_light_source(uuid)` | Remove all tile illumination, detach from anchor |
| `move_light_source(uuid, new_pos)` | **Delta-based**: only touches tiles that actually change |
| `toggle_light_source(uuid, active)` | Enable/disable without destroying |

### Delta-Based Movement (`gridmap.py:726-769`)

For a 1-tile move of a torch (20ft bright + 40ft dim):
- **Naive approach**: remove 266 tiles + add 266 tiles = 532 tile modifications
- **Delta approach**: ~73 tiles actually change (edges of old/new light circles)
- Tiles in the overlap with same light level are untouched (no events)

```
Old light circle    New light circle     Delta (what actually changes)
    ████████            ████████         ░░ = removed (old only)
  ████████████        ████████████       ▓▓ = added (new only)
  ████████████        ████████████       ██ = level changed (overlap)
  ████████████   →    ████████████       -- = same level (skip!)
  ████████████        ████████████
    ████████            ████████
```

### Anchored Light Movement (`gridmap.py:884-897`)

GridMap registers an `on_event_callback` for `SPATIAL_ENTITY_ENTERED`. When an entity with attached light sources moves, `move_light_source()` is called automatically for each attached light.

Attachment tracking lives on `BaseBlock._attached_light_sources: Set[UUID]` (`base_block.py`).

### Batch Event Firing (`gridmap.py:837-875`)

Two-tier strategy for batch light changes:

1. **Tier 1 (rare)**: Full event lifecycle (DECLARATION → COMPLETION) for positions where entities are standing. Needed for Hidden reveal handler at EFFECT phase.
2. **Tier 2 (always)**: Single COMPLETION event at one representative position. Triggers senses re-evaluation for subscribed observers.

---

## Senses Integration

### Pipeline (`entity.py` — `compute_senses_from_position`)

```
grid.compute_fov(observer_uuid)  → visible_positions  (walls + MAGICAL_DARKNESS block FOV)
        ↓
entity/object loop per tile      → light pre-check    (tile.get_effective_light_for())
        ↓                          if <= DARKNESS: skip entity (too dark to see them)
entity.is_perceivable_by()       → stealth/invis check (stealth_dc, is_invisible)
        ↓
visible_entities dict            → final result
```

**Key**: `senses.visible` is light-filtered — dark tiles are removed from `senses.visible` (but stay in `senses.seen` for memory/fog-of-war). Normal light changes update `senses.visible`, entities, and objects at affected positions via `_update_visibility_at()`.

### SpatialSensesCallback (`sensory.py:157-392`)

Registered as `EventQueue.add_on_event_callback()`. Fires for ALL events, filters to spatial events at **COMPLETION phase only**. Uses the **incremental senses update system** — callbacks NEVER run Dijkstra. All updates are lightweight:

- **Self-movement** (any `SPATIAL_ENTITY_ENTERED`/`LEFT` where `entity_uuid == owner_uuid`): calls `update_visibility_func()` (FOV only) + sets `_paths_dirty = True`
- **Other spatial events**: reads `SensesUpdateHint` from the event and applies targeted updates:
  - `requires_fov`: recompute FOV via `update_visibility_func()` (for magical darkness, door vision blocking)
  - `requires_paths`: set `_paths_dirty = True` (deferred to turn start or movement end)
  - `entity_entered`/`entity_left`: O(1) dict add/remove on `senses.entities`
  - `light_changed_positions`: update `senses.visible`, entities, and objects at changed positions (`_update_visibility_at()`)
  - `perceivability_entity`: re-check one entity's visibility
  - `object_placed`/`object_removed`: O(1) dict add/remove on `senses.objects`
- **Fallback** (events without hints): check position subscription, visibility-only + `_paths_dirty = True`

See [Incremental Senses Update System](#incremental-senses-update-system) section below for full details.

---

## Stealth Interactions

### Hide Action (`actions.py`)

| Light Level | Hide Rule |
|---|---|
| **VERY_BRIGHT** | Cannot hide — action always fails |
| **BRIGHT_LIGHT** | Current behavior — need cover/LOS break from enemies |
| **DIM_LIGHT or darker** | Relaxed — can attempt hide even with enemies watching |

### Hidden Auto-Reveal (`conditions.py`)

Hidden condition has triggers for:
- `SPATIAL_LIGHT_CHANGED` at EFFECT phase — checks if tile under entity became VERY_BRIGHT
- `SPATIAL_ENTITY_ENTERED` at EFFECT phase — checks if entity moved into VERY_BRIGHT tile

Both call `entity.remove_condition("Hidden", parent_event=event)` if VERY_BRIGHT detected.

---

## Zone Spell Light (`tile_conditions.py`)

`ZoneControlCondition` has optional light fields:

```python
sets_light_level: Optional[LightLevel] = None
light_is_obscurement: bool = False  # True = add_obscurement(), False = add_illumination()
_light_modifier_uuids: Dict[pos, UUID]  # Tracks per-tile modifiers for cleanup
```

Methods: `_apply_light_modifiers()`, `_remove_light_modifiers()`. Wired into `_apply()`, `_remove()`, `move_zone()`.

### Implemented Zone Spells

| Spell | Level | Light Effect | Type |
|-------|-------|-------------|------|
| Fog Cloud | 1 | DARKNESS obscurement | Blocks darkvision |
| Darkness | 2 | MAGICAL_DARKNESS obscurement | Blocks FOV entirely |
| Daylight | 3 | VERY_BRIGHT illumination | Auto-reveals Hidden |

---

## Torch Item

`Torch` in `dnd/items/test_items.py` — UsableItem with Ignite/Extinguish use actions.

- **IgniteTorchAction**: calls `GridMap.add_light_source()` with `anchor_uuid=owner.uuid`
- **ExtinguishTorchAction**: calls `GridMap.remove_light_source()`
- Light follows carrier via anchored movement callback
- Auto-extinguish on drop via `_on_drop()` lifecycle hook

---

## Files Modified

| File | Changes |
|---|---|
| `dnd/core/base_tiles.py` | +LightLevel, +SensesType, +SenseMode, Tile light storage/methods/resolution, get_effective_light_for(), blocks_vision() magical darkness, _notify_light_changed(), adjacent rule |
| `dnd/core/base_block.py` | +get_sense_modes() default, +_attached_light_sources tracking |
| `dnd/blocks/sensory.py` | sense_modes field (replaces old extra_senses), get_sense_modes() override, SPATIAL_LIGHT_CHANGED in SPATIAL_EVENTS, COMPLETION phase filter |
| `dnd/core/events.py` | +SPATIAL_LIGHT_CHANGED, +SpatialChangeType.LIGHT_CHANGED, +factory |
| `dnd/core/gridmap.py` | +observer_uuid in is_blocking/compute_fov, +LightSourceData, +add/remove/move/toggle_light_source, +_compute_light_tiles, +_fire_light_batch_events, +movement callback |
| `dnd/entity.py` | +get_sense_modes() relay, light filtering in compute_senses_from_position, can_bypass_invisibility() migration |
| `dnd/actions.py` | Hide._validate() light-level check |
| `dnd/conditions.py` | Hidden reveal handler: SPATIAL_LIGHT_CHANGED + SPATIAL_ENTITY_ENTERED triggers, VERY_BRIGHT check in processor |
| `dnd/tile_conditions.py` | ZoneControlCondition: sets_light_level, light_is_obscurement, _apply/_remove_light_modifiers |
| `dnd/spells/conjuration.py` | +FogCloud, +DarknessSpell, +Daylight (zone pattern) |
| `dnd/items/test_items.py` | +Torch with Ignite/Extinguish use actions |
| `examples/test_lighting_system.py` | 77 tests |
| `examples/test_light_source_perf.py` | Performance profiling |

---

## Incremental Senses Update System — IMPLEMENTED

### Performance Results (20x20 dark grid, torch 20ft bright + 40ft dim)

**Before (full recompute per observer per event):**

| Observers | add_light | move_light | entity_move |
|-----------|-----------|------------|-------------|
| 1 | 0.044s | 0.023s | 0.072s |
| 2 | 0.123s | 0.043s | 0.131s |
| 5 | 0.595s | 0.297s | 0.305s |
| 10 | 1.851s | 0.584s | 0.590s |

**After (incremental hint-based updates, no Dijkstra in callbacks):**

| Scenario | Before | After | Improvement |
|----------|--------|-------|-------------|
| 10 observers, add_light_source | 1.851s | 0.0072s | **257x** |
| 10 observers, move_light_source | 0.584s | 0.0044s | **133x** |
| 10 observers, entity_move with torch | 0.590s | 0.0148s | **40x** |

### Root Cause (Fixed)

Every spatial event triggered a **full senses recompute** (FOV + Dijkstra + entity filter) for every subscribed observer. Normal light changes don't affect FOV geometry or walkability — only entity visibility filtering changes. 10 observers × 3 events per step = 30 Dijkstra runs per movement tile.

### Architecture: SensesUpdateHint (`events.py`)

Every spatial event now carries a `SensesUpdateHint` telling observers exactly what to update:

```python
class SensesUpdateHint(BaseModel):
    """Carried by spatial events — tells observers what to update incrementally."""
    requires_fov: bool = False       # Vision geometry changed (magical darkness, wall, door)
    requires_paths: bool = False     # Path topology changed (entity moved, walkability changed)

    entity_entered: Optional[Tuple[UUID, Tuple[int,int]]] = None   # O(1) dict add
    entity_left: Optional[Tuple[UUID, Tuple[int,int]]] = None      # O(1) dict remove
    entity_died: Optional[Tuple[UUID, Tuple[int,int]]] = None      # Dict remove + paths dirty

    light_changed_positions: Optional[Set[Tuple[int,int]]] = None  # Update visible + entities + objects here
    perceivability_entity: Optional[UUID] = None                    # Re-check one entity

    object_placed: Optional[Tuple[UUID, Tuple[int,int]]] = None    # O(1) dict add
    object_removed: Optional[Tuple[UUID, Tuple[int,int]]] = None   # O(1) dict remove
```

The `senses_hint` field on `SpatialChangeEvent` is populated by ALL factory methods: `entity_entered()`, `entity_left()`, `tile_changed()`, `light_changed()`, `perceivability_changed()`, `object_placed()`, `object_removed()`, `object_changed()`.

### Three Separated Concerns

```
FOV (geometry)     — only recompute when requires_fov=True (magical darkness, wall, door vision blocking)
Paths (movement)   — only set _paths_dirty when requires_paths=True (deferred to turn start/movement end)
Entity filtering   — only re-filter at specific positions (light_changed_positions, entity entered/left)
```

### The _paths_dirty Pattern

Dijkstra is the most expensive operation (~30-50ms). Callbacks **NEVER** run Dijkstra — they only set `_paths_dirty = True` on the Senses block. Full Dijkstra runs only when actually needed:

1. **Turn start**: `Encounter.start_turn()` → `entity.update_entity_senses()` (clears flag)
2. **Movement end**: `Move._apply()` finally block → `entity.update_entity_senses()` (clears flag)
3. **On-demand**: Reactions that need walkability check `grid.is_walkable_for()` per cell (O(1) per cell, no Dijkstra)

### Hint Per Event Type

| Event / Change | Hint | Cost |
|----------------|------|------|
| Entity enters cell | `requires_paths=True, entity_entered=(uuid, pos)` | O(1) dict add |
| Entity leaves cell | `requires_paths=True, entity_left=(uuid, pos)` | O(1) dict remove |
| Light changed (batch) | `light_changed_positions={changed positions}` | O(changed × entities_per_tile) |
| Light changed (magical darkness) | `requires_fov=True, light_changed_positions={...}` | O(visible_cells) FOV |
| Perceivability changed | `perceivability_entity=uuid` | O(1) re-check |
| Object placed (blocks vision) | `requires_fov=True, object_placed=(uuid, pos)` | O(visible_cells) FOV |
| Object placed (blocks walking) | `requires_paths=True, object_placed=(uuid, pos)` | O(1) + paths dirty |
| Object changed (door open/close) | `requires_fov=True/False, requires_paths=True/False` | FOV + paths dirty |
| Tile changed (walkable) | `requires_paths=True` | Paths dirty |
| Tile changed (visible) | `requires_fov=True` | O(visible_cells) FOV |
| Entity death | `entity_died=(uuid, pos), requires_paths=True` | O(1) + paths dirty |

### SPATIAL_OBJECT_CHANGED Event

New event type for objects changing blocking state (doors opening/closing):

```python
# events.py
EventType.SPATIAL_OBJECT_CHANGED = "spatial_object_changed"
SpatialChangeType.OBJECT_CHANGED = "object_changed"

# Factory: SpatialChangeEvent.object_changed(position, object_uuid,
#            blocks_vision_changed=False, blocks_walking_changed=False)
```

Used by `BaseItem._notify_blocking_changed()` — standard pattern for items to notify blocking state changes. Door actions (OpenDoorAction, CloseDoorAction, InteractDoorAction) call this instead of `Entity.update_all_entities_senses()`.

### Bug Fixes Applied

1. **Light callback phase filter** (`gridmap.py`): `_on_light_movement_event()` returns early if `phase != EventPhase.COMPLETION`. Reduces `move_light_source()` from 4x to 1x per movement step.
2. **Removed `is_moving` flag**: No more mutable state on Senses. Self-movement detected by UUID comparison in callbacks. All movement types (walking, teleport, forced) handled uniformly.
3. **Batch light hint**: `_fire_light_batch_events()` builds `SensesUpdateHint` with `light_changed_positions` from batch, detects magical darkness for `requires_fov`.
4. **Object blocking hints**: `place_object()`/`remove_object()` look up object blocking properties and populate hints.

### Zone Light/Terrain Batching

- `ZoneControlCondition._apply_terrain_modifiers()` fires batched `SPATIAL_TILE_CHANGED` with `requires_paths=True` hint after modifying tiles
- `ZoneControlCondition._apply_light_modifiers()` uses `fire_event=False` per tile + `grid._fire_light_batch_events(changed_positions)` batch after

### Files Modified (Incremental Senses)

| File | Changes |
|------|---------|
| `dnd/core/events.py` | +SensesUpdateHint model, +senses_hint on SpatialChangeEvent, +SPATIAL_OBJECT_CHANGED, hints on all factories |
| `dnd/blocks/sensory.py` | Remove `is_moving` field, +_paths_dirty flag, refactor SpatialSensesCallback (no Dijkstra, _apply_hint + helpers) |
| `dnd/core/gridmap.py` | Fix light callback phase filter, populate hints in _fire_light_batch_events, detect magical darkness |
| `dnd/actions.py` | Remove `is_moving` flag set/clear from Move._apply() |
| `dnd/blocks/base_item.py` | +_notify_blocking_changed() method |
| `dnd/items/test_items.py` | Door actions: use _notify_blocking_changed() instead of update_all_entities_senses() |
| `dnd/tile_conditions.py` | Zone terrain: fire batched path event. Zone light: batch pattern. |

### Observer Perception Change Detection

`SpatialSensesCallback` also handles `CONDITION_APPLICATION` / `CONDITION_REMOVAL` events on self (not just spatial events). When a condition changes the observer's perception capabilities, cached senses are re-evaluated:

**Snapshot fields on Senses**:
- `_last_passive_perception: int` — stored after each `update_entity_senses()`
- `_last_sense_modes_hash: int` — hash of `(sense_type, range)` tuples

**Flow**: Condition added/removed on self → `_handle_own_perception_change()`:
1. Compare current perception vs snapshot
2. If sense modes changed (Darkvision, Truesight gained/lost) → full `update_visibility_func()` recompute
3. If only passive perception changed → `_refilter_all_visible_entities()` (lighter, only re-checks entities in visible area)
4. Either way → `_paths_dirty = True` (safe paths may change)

### Light-Driven Stealth Detection Combat Logs

When light changes (torch movement, light spell, light toggle) cause `_refilter_entities_at()` to run, newly visible hidden entities (those with `stealth_dc` set) generate `ENTITY_SPOTTED` combat logs via `EventQueue.push_combat_log()`.

When perception changes reveal hidden hazards (`condition_stealth_dc`), `HAZARD_DETECTED` combat logs are generated via `_log_newly_detected_hazards()`.

**Tests**: `examples/test_lighting_stealth_integration.py` Section 8 (light-driven stealth detection logs), `examples/test_perception_staleness.py` (observer perception changes).