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
| **Normal light change** (DARKNESS ↔ DIM ↔ BRIGHT ↔ VERY_BRIGHT) | Entity/object filtering only | Which entities are visible at already-known tile positions. FOV geometry unchanged. | Torch lit/extinguished, Fog Cloud |
| **Magical darkness** (MAGICAL_DARKNESS) | FOV geometry change | `blocks_vision()` returns True → tiles behind it become invisible. Like a temporary wall for vision. | Darkness spell |

Normal light changes are cheap to process — the set of visible tiles stays the same, only the "can I see entities here?" filter changes. Magical darkness is expensive — it changes FOV geometry, potentially hiding tiles that were previously visible (and revealing them when removed).

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
3. **Devil's Sight**: MAGICAL_DARKNESS → DARKNESS (darkvision can then help)
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

**Key**: `senses.visible` (geometric FOV) is unchanged by normal light — dark tiles are still "known" for movement/map awareness. Only entity/object **filtering** is affected by DARKNESS/DIM_LIGHT.

### SpatialSensesCallback (`sensory.py:157-392`)

Registered as `EventQueue.add_on_event_callback()`. Fires for ALL events, filters to spatial events at **COMPLETION phase only**. Uses the **incremental senses update system** — callbacks NEVER run Dijkstra. All updates are lightweight:

- **Self-movement** (any `SPATIAL_ENTITY_ENTERED`/`LEFT` where `entity_uuid == owner_uuid`): calls `update_visibility_func()` (FOV only) + sets `_paths_dirty = True`
- **Other spatial events**: reads `SensesUpdateHint` from the event and applies targeted updates:
  - `requires_fov`: recompute FOV via `update_visibility_func()` (for magical darkness, door vision blocking)
  - `requires_paths`: set `_paths_dirty = True` (deferred to turn start or movement end)
  - `entity_entered`/`entity_left`: O(1) dict add/remove on `senses.entities`
  - `light_changed_positions`: re-filter entities at changed positions only (light + perceivability check)
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

## Performance Problems

### Measured Performance (20x20 dark grid, torch 20ft bright + 40ft dim)

**Single observer:**
| Operation | Time |
|---|---|
| add_light_source (266 tiles) | 0.044s |
| move_light_source (delta, ~73 tiles change) | 0.023s |
| Entity.update_entity_position (move + light + senses) | 0.072s |

**Multi-observer scaling (linear):**
| Observers | add_light | move_light | entity_move |
|-----------|-----------|------------|-------------|
| 1 | 0.044s | 0.023s | 0.072s |
| 2 | 0.123s | 0.043s | 0.131s |
| 5 | 0.595s | 0.297s | 0.305s |
| 10 | 1.851s | 0.584s | 0.590s |

### Root Cause: Full Recomputation Per Observer

When a `SPATIAL_LIGHT_CHANGED` event fires at COMPLETION phase, **every subscribed observer runs a full senses recompute**:

```
SPATIAL_LIGHT_CHANGED (COMPLETION)
    → SpatialSensesCallback fires for each subscribed observer
        → update_senses_func()
            → compute_senses_from_position()
                → grid.compute_fov()          ← Shadowcast FOV (medium cost)
                → grid.compute_paths()        ← Dijkstra pathfinding (HIGH cost)
                → entity/object filtering     ← Light + perceivability (low cost)
                → subscribe_to_cells()        ← Subscription update (low cost)
```

**The problem**: A normal light change (torch moved) doesn't affect FOV geometry or walkability. Only entity visibility filtering changes. But every observer recomputes everything from scratch.

### Three Categories of Spatial Change

| Change Type | Affects FOV? | Affects Paths? | Affects Entity Visibility? | Example |
|---|---|---|---|---|
| **Normal light** (DARKNESS↔DIM↔BRIGHT↔VERY_BRIGHT) | No | No | Yes | Torch lit, Fog Cloud |
| **Magical darkness** (MAGICAL_DARKNESS added/removed) | **Yes** (blocks vision like wall) | No | Yes | Darkness spell |
| **Entity/tile movement** | No | **Yes** (entities block paths) | Yes | Entity moved, wall placed |

Currently ALL three trigger the same full recompute. This is the core architectural problem.

### Cascade Problem During Entity Movement

When an entity carrying a torch moves one tile, the event cascade is:

```
Entity.update_entity_position(carrier, new_pos)
    → SPATIAL_ENTITY_LEFT (old_pos)          ← Other observers: full senses recompute
    → SPATIAL_ENTITY_ENTERED (new_pos)       ← Other observers: full senses recompute
        → _on_light_movement_event()
            → move_light_source(delta)
                → _fire_light_batch_events()
                    → SPATIAL_LIGHT_CHANGED   ← Other observers: full senses recompute (AGAIN)
```

That's potentially **3 full senses recomputes per observer per tile of movement**. For a 6-tile move with 5 observers, that's 90 Dijkstra runs.

### The Single COMPLETION Event Limitation

`_fire_light_batch_events()` fires one COMPLETION event at a single position. Only observers subscribed to THAT specific position get triggered. Observers subscribed to OTHER changed tiles (but not this one) may miss the update entirely. This is a correctness concern — some observers might have stale entity visibility until their next senses refresh.

---

## Proposed Architecture: Event-Carried Incremental Updates

### Core Insight

The current system uses events as **triggers for full recomputation**. The event says "something changed at position X" and the observer throws away all cached state and recomputes from scratch.

Instead, events should **carry the information needed for incremental updates**. The event already knows what changed — it should tell observers exactly what to update, so they don't need to recompute anything.

### Design Direction

**Events carry delta information:**

```python
# Instead of: "light changed at (5,3)" → observer recomputes everything
# Do: "light changed at (5,3): DARKNESS → DIM_LIGHT" → observer updates entity filter for (5,3)

class SensesUpdatePayload:
    """Carried by spatial events — tells observers exactly what to update."""
    # For light changes:
    light_changes: Dict[pos, Tuple[LightLevel, LightLevel]]  # pos → (old, new)

    # For entity movement:
    entity_entered: Optional[Tuple[UUID, pos]]
    entity_left: Optional[Tuple[UUID, pos]]

    # For FOV-affecting changes (magical darkness, wall placed):
    requires_fov_recompute: bool = False

    # For path-affecting changes (entity moved, wall placed):
    requires_path_recompute: bool = False
```

**Observer processes delta instead of recomputing:**

```python
# In SpatialSensesCallback:
def _process_light_delta(self, light_changes):
    """Update entity visibility at changed tiles only."""
    for pos, (old_level, new_level) in light_changes.items():
        if new_level <= DARKNESS:
            # Remove entities at this tile from visible set
            self.senses.entities = {k:v for k,v in self.senses.entities.items() if v != pos}
        elif old_level <= DARKNESS and new_level > DARKNESS:
            # Tile became visible — check entities at this tile
            for entity in Entity.get_all_entities_at_position(pos):
                if entity.is_perceivable_by(self.owner_uuid):
                    self.senses.entities[entity.uuid] = pos
```

### What Each Change Type Needs

| Change | Observer Update | Cost |
|---|---|---|
| **Normal light change** | Re-filter entities at changed tiles only | O(changed_tiles × entities_per_tile) |
| **Magical darkness added** | Full FOV recompute (geometry changed) | O(visible_cells) for FOV, then re-filter |
| **Magical darkness removed** | Full FOV recompute | Same as above |
| **Entity entered tile** | Add to visible entities if perceivable + light OK | O(1) |
| **Entity left tile** | Remove from visible entities | O(1) |
| **Entity moved (own movement)** | FOV from new position + entity filter | O(visible_cells) — no paths during movement |
| **Tile walkability changed** | Path recompute only | O(cells × log cells) for Dijkstra |

### Key Principle: Separate the Three Concerns

```
FOV (geometry)     — only recompute when vision-blocking changes (walls, magical darkness)
Paths (movement)   — only recompute when walkability changes (entities move, walls placed)
Entity filtering   — only re-filter when light or perceivability changes at specific tiles
```

Currently all three are bundled in `update_entity_senses()`. Splitting them allows each spatial event to trigger only the minimal work needed.

### Coalescing During Movement

When an entity with a torch moves 6 tiles, instead of 3 events × 6 tiles × N observers = 18N recomputes, the system should:

1. **Batch the movement**: carrier's `is_moving` flag already exists
2. **Accumulate deltas**: collect all light changes across the 6-tile movement
3. **Single update at end**: apply the accumulated delta to each observer once
4. **FOV only during movement**: for the moving entity (already implemented via `update_visibility_func`)

This reduces 18N recomputes to N incremental updates + 1 FOV per moving entity step.