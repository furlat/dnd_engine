# BaseBlock Refactor — Design Document

This document describes the BaseBlock refactor: a **pre-requisite** independent from the items system. It pushes two responsibilities down from Entity/GridMap to BaseBlock:

1. **Unified Spatial Blocking** — polymorphic `blocks_walking()`/`blocks_vision()` on BaseBlock
2. **Condition Ownership & Management** — tree traversal, removal, duration progression on BaseBlock

---

## Table of Contents

1. [Part 1: Unified Spatial Blocking & GridMap Integration](#part-1-unified-spatial-blocking--gridmap-integration)
2. [Part 2: Condition Ownership — Unifying Condition Management on BaseBlock](#part-2-condition-ownership--unifying-condition-management-on-baseblock)
3. [Part 3: Implementation Phases](#part-3-implementation-phases)

---

## Part 1: Unified Spatial Blocking & GridMap Integration

### 1.1 The Problem

Blocking logic is scattered and hardcoded in GridMap. Each spatial predicate knows about specific types:

- `is_walkable(x, y, mode)` — checks `tile.get_movement_cost(mode) > 0` (tile-only)
- `is_walkable_for(x, y, entity_uuid, mode)` — adds entity occupancy check via `_entities_by_position` + `_non_blocking_entities` set
- `is_blocking(x, y)` — checks `tile is None or not tile.visible` (tile-only, used by shadowcast)
- `is_visible(x, y)` — checks `tile is not None and tile.visible` (tile-only)

When items arrive on the grid, every predicate needs modification. The algorithms (shadowcast, dijkstra) receive position-based callbacks but no polymorphism — adding a new spatial type means editing GridMap methods, not implementing an interface.

**Goal**: One polymorphic interface on BaseBlock. GridMap aggregates. Algorithms unchanged.

> **STATUS: IMPLEMENTED** — Phase A complete. Tiles, Entities, and GridMap predicates all use the polymorphic `blocks_walking()`/`blocks_vision()` interface. Entity occupancy blocking unified under the same dispatch — `_non_blocking_entities` set eliminated.

### 1.2 Import Dependencies

**Current dependency chain:**
```
base_conditions.py  (no core imports up)
      ↑
base_block.py       → values, base_conditions, events
      ↑
base_tiles.py       → base_block, values, modifiers  (MovementMode lives HERE)
      ↑
gridmap.py          → shadowcast, dijkstra, base_tiles, events
```

**After refactor:**
```
base_conditions.py  (no core imports up)
      ↑
base_block.py       → values, base_conditions, events  (MovementMode moves HERE)
      ↑
base_tiles.py       → base_block, values, modifiers    (imports MovementMode FROM base_block)
      ↑
gridmap.py          → shadowcast, dijkstra, base_tiles, events
```

**Why no cycles arise:**
- `MovementMode` is a plain `str, Enum` with zero imports — moving it from `base_tiles.py` to `base_block.py` adds no new dependencies to `base_block.py`
- `base_tiles.py` already imports `base_block` — importing `MovementMode` back from `base_block` is the same import, just adding a name
- `gridmap.py` already imports from `base_tiles` — no change needed (it can still get `MovementMode` from `base_tiles` which re-exports, or switch to importing from `base_block`)
- `shadowcast` and `dijkstra` are pure algorithm functions with stdlib-only imports — completely decoupled

**Files that import `MovementMode` from `base_tiles` (need updating):**
- `dnd/core/gridmap.py` — `from dnd.core.base_tiles import Tile, MovementMode`
- `dnd/actions.py` — `from dnd.core.base_tiles import MovementMode`
- `examples/test_terrain_movement_system.py`
- `examples/test_difficult_terrain.py`

All can switch to `from dnd.core.base_block import MovementMode` or `base_tiles` can re-export it.

### 1.3 The Unified Interface on BaseBlock

```python
# In BaseBlock — default implementations (non-spatial blocks return False)
class BaseBlock:
    def blocks_walking(self, requesting_entity_uuid: Optional[UUID] = None,
                       mode: MovementMode = MovementMode.WALKING) -> bool:
        """Whether this block prevents walking through its position.
        Non-spatial blocks (Equipment, Health, etc.) inherit this default."""
        return False

    def blocks_vision(self, requesting_entity_uuid: Optional[UUID] = None) -> bool:
        """Whether this block prevents vision through its position.
        Non-spatial blocks inherit this default."""
        return False
```

**Key design decision**: These are boolean gates ("can you pass?"), NOT cost functions. Movement cost granularity stays on Tile (see §1.7).

### 1.4 Per-Type Overrides

**Tile** (wraps existing `get_movement_cost` and `visible`):
```python
class Tile(BaseBlock):
    def blocks_walking(self, requesting_entity_uuid=None,
                       mode=MovementMode.WALKING):
        return self.get_movement_cost(mode) <= 0

    def blocks_vision(self, requesting_entity_uuid=None):
        return not self.visible
```

**Entity** (flag-driven, handler sets state):
```python
# dnd/entity.py — field declaration (line 144)
non_blocking: bool = Field(default=False, description="When True, entity does not block movement through its cell")

# dnd/entity.py — override (lines 1528-1535)
class Entity(BaseBlock):
    def blocks_walking(self, requesting_entity_uuid=None,
                       mode=MovementMode.WALKING):
        if requesting_entity_uuid == self.uuid:
            return False          # Self-avoidance
        if self.non_blocking:
            return False          # Dead, incorporeal, etc.
        return True
```

**Key design decision**: Entity does NOT check condition names (no `"Dead" in self.active_conditions`). Instead, the death handler sets `entity.non_blocking = True`. This keeps Entity ignorant of specific conditions — any handler can flip the flag:

```python
# dnd/conditions.py — death_processor (line 936)
entity.add_condition(dead_condition, check_save_throw=False)
entity.non_blocking = True  # Handler owns the decision, not Entity
```

Future handlers (Incorporeal, Gaseous Form, etc.) set the same flag — Entity.blocks_walking() doesn't change.

**Future BaseItem** (delegates to fields):
```python
class BaseItem(BaseBlock):
    blocks_movement: bool = False
    blocks_vision_field: bool = False

    def blocks_walking(self, requesting_entity_uuid=None,
                       mode=MovementMode.WALKING):
        return self.blocks_movement

    def blocks_vision(self, requesting_entity_uuid=None):
        return self.blocks_vision_field
```

### 1.5 GridMap Aggregation

GridMap becomes the aggregator. Algorithms stay unchanged — they still receive position-based callbacks. The predicates get richer inside:

```python
# GridMap.is_walkable() — tile-only, uses polymorphic interface (line 254)
def is_walkable(self, x, y, mode=MovementMode.WALKING):
    tile = self._tiles.get((x, y))
    if tile is None:
        return False
    return not tile.blocks_walking(mode=mode)

# GridMap.is_walkable_for() — tile + entity blocking via polymorphic dispatch (line 268)
def is_walkable_for(self, x, y, requesting_entity_uuid=None,
                    mode=MovementMode.WALKING):
    if not self.is_walkable(x, y, mode):
        return False
    for entity_uuid in self._entities_by_position.get((x, y), set()):
        block = BaseBlock.get(entity_uuid)
        if block is not None and block.blocks_walking(requesting_entity_uuid, mode):
            return False
    return True

# GridMap.is_blocking() — vision check, uses polymorphic interface (line 294)
def is_blocking(self, x, y):
    tile = self._tiles.get((x, y))
    return tile is None or tile.blocks_vision()
```

**Note**: `is_walkable_for()` now uses polymorphic dispatch — `BaseBlock.get(uuid).blocks_walking()` routes to Entity, Tile, or future item overrides. GridMap stays type-unaware. When the items system adds objects to the grid, the same loop can iterate objects at a position with no predicate changes.

**The algorithms don't change.** `compute_fov(origin, self.is_blocking, ...)` and `dijkstra(start, walkable_check, ...)` keep receiving the same callback signatures. The callbacks internally become polymorphic.

### 1.6 `requesting_entity_uuid` Parameter

Both methods accept `requesting_entity_uuid: Optional[UUID] = None`. **Now actively used** by `Entity.blocks_walking()` for self-avoidance: an entity at position (5,5) doesn't block itself from occupying (5,5). `GridMap.is_walkable_for()` passes `requesting_entity_uuid` through to `blocks_walking()`, which Entity checks against `self.uuid`.

**Future use cases** (unchanged):
- **Invisibility**: Entity A is invisible to Entity B but not to Entity C (has See Invisibility)
- **Darkvision**: A creature with darkvision can see through dim light that blocks normal vision
- **Hiding**: A hidden entity doesn't "block" vision for entities that can't detect it
- **Ethereal**: Ethereal entities pass through solid objects

### 1.7 Movement Cost Stays Separate

`blocks_walking()` is a **boolean gate**: "can you enter this cell at all?"
`Tile.get_movement_cost(mode)` is a **granular cost**: "how much movement does it cost?"

These serve different purposes:
- Dijkstra needs costs for optimal pathfinding (difficult terrain = cost 2, normal = cost 1)
- Blocking check needs a yes/no answer for occupancy/walls
- A tile with cost 2 (difficult terrain) does NOT block walking — it just costs more

The boolean gate delegates to the cost function: `blocks_walking() → get_movement_cost(mode) <= 0`. But they're conceptually separate interfaces.

### 1.8 Object Registries (Future — Items System)

When items land on the grid, GridMap needs new registries:
```python
_object_positions: Dict[UUID, Tuple[int, int]] = {}
_objects_by_position: DefaultDict[Tuple[int, int], Set[UUID]] = defaultdict(set)
```

New methods: `place_object()`, `remove_object()`, `get_objects_at()`, `get_object_position()`.

Updates to predicates: `is_walkable_for()` checks objects via `blocks_walking()`, FOV checks objects via `blocks_vision()`.

**Not part of this refactor** — this is documented here for completeness and implemented in the items system.

### 1.9 Senses Changes (Future — Items System)

Add `objects: Dict[UUID, Tuple[int, int]]` field to Senses (same pattern as `entities`). Senses does NOT import BaseItem — stores UUID + position only. `Entity.update_entity_senses()` queries GridMap for visible objects.

**Not part of this refactor.**

---

## Part 2: Condition Ownership — Unifying Condition Management on BaseBlock

### Key Architectural Discovery

`BaseBlock._registry` (line 144 in `base_block.py`) contains ALL BaseBlock instances — entities, tiles, AND (future) items. `BaseBlock.get(uuid)` can find any of them. This means `_remove_condition_tree()` CAN move to BaseBlock using `BaseBlock.get()` for cross-object lookups, with no circular imports.

### Current State

| Feature | BaseBlock | Entity |
|---------|-----------|--------|
| `add_condition()` | Yes (line 585) | Yes (override — adds saving throw check) |
| `remove_condition()` | Yes (line 555, sub-conditions only) | Yes (override — full tree traversal, line 389) |
| `_remove_condition_tree()` | No | Yes (line 347 — handles external_conditions, terrain_conditions) |
| `remove_condition_by_uuid()` | No | Yes (line 422 — UUID lookup → `remove_condition(name)`) |
| `advance_duration_condition()` | No | Yes (line 436 — turn-based with removal saves) |

### The Refactor: Move Condition Management DOWN to BaseBlock

This makes tiles and (future) items first-class condition hosts with full cross-object cleanup.

**What moves to BaseBlock:**

1. **`remove_condition_by_uuid()`** — simple UUID lookup in `active_conditions_by_uuid` → delegates to `self.remove_condition(name)`. No imports needed.

2. **`_remove_condition_tree()`** — uses `BaseBlock.get(target_uuid)` instead of `Entity.get()`:

```python
# In BaseBlock — NO Entity import needed
def _remove_condition_tree(self, condition, expire=False, parent_event=None):
    # Sub-conditions (same block)
    for sub_uuid in list(condition.sub_conditions):
        sub = BaseCondition.get(sub_uuid)
        if sub is not None and isinstance(sub, BaseCondition):
            self._remove_condition_tree(sub, expire, parent_event)

    # External conditions (ANY BaseBlock — entities, items, tiles)
    for target_uuid, cond_uuid in condition.external_conditions:
        target = BaseBlock.get(target_uuid)
        if target is not None:
            target.remove_condition_by_uuid(cond_uuid)

    # Terrain conditions (tiles — also BaseBlocks)
    for tile_uuid, cond_uuid in condition.terrain_conditions:
        target = BaseBlock.get(tile_uuid)
        if target is not None:
            target.remove_condition_by_uuid(cond_uuid)

    # Own state cleanup (modifiers, handlers)
    condition.cleanup_own_state(expire, parent_event)
```

**Why this works**: Entity, Tile, and (future) BaseItem all inherit BaseBlock. They all register in `BaseBlock._registry` via `__init__()`. `BaseBlock.get(uuid)` finds any of them.

3. **`remove_condition()` upgrade** — BaseBlock's version (line 555) currently handles sub-conditions with `cleanup_own_state()` but NOT cross-object cleanup. After refactor, it calls `_remove_condition_tree()` for full cleanup:

```python
# BaseBlock.remove_condition() — now with full tree traversal
def remove_condition(self, condition_name, expire=False, parent_event=None):
    condition = self.active_conditions.pop(condition_name)
    all_subs = self._collect_all_sub_conditions(condition)
    for sub in all_subs:
        self._remove_condition_from_dicts(sub)
    self._remove_condition_from_dicts(condition)
    self._remove_condition_tree(condition, expire, parent_event)  # Full tree
```

Entity's override still adds Entity-specific logic (saving throw checks, additional tracking) while tree traversal is inherited.

**What stays on Entity:**
- `advance_duration_condition()` — calls `self.saving_throw()` which is Entity-specific
- `add_condition()` override — Entity adds saving throw checks before application

### Key Implications

**For tiles**: Currently tiles only get same-block sub-condition cleanup. With this refactor, if a tile condition creates `external_conditions` on entities (e.g., a trap that applies Poisoned), removing the tile condition now properly cleans up the entity conditions too.

**For items**: Same benefit. If a magic item's condition creates `external_conditions` on the wielder, destroying the item (which calls `destroy` → `remove_condition`) now properly cleans up the entity conditions via the tree.

### Condition Progression — Two Tracks

| Track | What | When | How |
|-------|------|------|-----|
| **Entity turn** | Entity conditions + conditions on equipped/inventory items | During entity's `on_turn_start()` | `Entity.advance_duration_condition()` for own conditions. Entity iterates equipped items + inventory items and calls `advance_duration()` on their conditions |
| **Environment step** | Conditions on tiles + conditions on floor items (items on GridMap) | End of full round | `Encounter._environment_step()` iterates GridMap tiles and floor objects, calls `advance_duration()` on their conditions |

**Why this split**: Equipped/inventory items are "part of" their owner entity — their conditions progress on the owner's turn (e.g., a Magic Weapon spell duration ticks when the wielder's turn starts). Floor items and tiles have no owner — they need an "environment step" after all combatants have acted.

**`advance_duration()` on BaseBlock** (simpler than Entity's `advance_duration_condition`):
```python
# On BaseBlock — no saving throws, just duration ticking
def advance_duration(self, parent_event=None):
    for cond_name, condition in list(self.active_conditions.items()):
        if condition.duration is not None:
            condition.duration -= 1
            if condition.duration <= 0:
                self.remove_condition(cond_name, expire=True, parent_event=parent_event)
```

### Environment Step — New Encounter Lifecycle Concept

The environment step is a first-class concept in the Encounter lifecycle. Environmental dynamics happen independently of any entity: fire spreads from ignited oil, terrain changes, floor objects react, conditions progress.

**Encounter round lifecycle after this change:**
```
Round N:
  Entity 1 Turn → Entity 2 Turn → ... → Entity N Turn
  → ROUND_END event
  → ENVIRONMENT STEP ← NEW
      1. Tile conditions advance_duration()
      2. Floor item conditions advance_duration()
      3. Environmental dynamics (fire spreads, objects react)
  → round_number++
  → ROUND_START event
Round N+1: ...
```

**Insertion point**: `Encounter._advance_round()` (line 428) — between `_fire_round_end()` and `round_number += 1`:

```python
def _advance_round(self) -> None:
    self._fire_round_end()
    self._environment_step()  # NEW
    self.round_number += 1
    self.current_turn_index = 0
    for combatant in self.combatants.values():
        combatant.has_acted_this_round = False
    self._fire_round_start()
```

### Conditions on Items Use Case

Magic Weapon spell → applies `MagicWeaponCondition` to the Weapon block (not the entity!) → adds +1 to `weapon.attack_bonus` ModifiableValue. Concentration on caster links via `external_conditions` → breaking concentration removes weapon condition via `_remove_condition_tree` on BaseBlock. The weapon is found via `BaseBlock.get(weapon_uuid)` — works because Weapon inherits from EquippableItem → BaseItem → BaseBlock.

---

## Part 3: Implementation Phases

### Phase A: Spatial Blocking

**A.1: Move `MovementMode` enum from `base_tiles.py` to `base_block.py`** ✓ DONE
- Cut `MovementMode` class from `dnd/core/base_tiles.py`
- Paste into `dnd/core/base_block.py` (before `BaseBlock` class, after imports)
- Update `base_tiles.py` to import: `from dnd.core.base_block import BaseBlock, MovementMode`
- Update all other importers: `dnd/actions.py`, `dnd/core/gridmap.py`, test files
- Alternatively: keep re-exporting from `base_tiles.py` for backwards compat
- File targets: `dnd/core/base_block.py`, `dnd/core/base_tiles.py`, `dnd/actions.py`, `dnd/core/gridmap.py`
- Test: `pytest` — all tests pass, no import errors

**A.2: Add `blocks_walking()`/`blocks_vision()` defaults to BaseBlock** ✓ DONE
- Add both methods to `BaseBlock` class, both return `False`
- `blocks_walking` signature: `(self, requesting_entity_uuid=None, mode=MovementMode.WALKING) -> bool`
- `blocks_vision` signature: `(self, requesting_entity_uuid=None) -> bool`
- File: `dnd/core/base_block.py`
- Test: `pytest` — all tests pass (methods are additive, no behavior change)

**A.3: Override in Tile** ✓ DONE
- Add `blocks_walking()` override: `return self.get_movement_cost(mode) <= 0`
- Add `blocks_vision()` override: `return not self.visible`
- File: `dnd/core/base_tiles.py`
- Test: `pytest` + manual verification that Tile overrides match existing behavior

**A.4: Update GridMap predicates to use polymorphic methods** ✓ DONE
- `is_walkable()`: Replace `tile.get_movement_cost(mode) > 0` with `not tile.blocks_walking(mode=mode)`
- `is_blocking()`: Replace `tile is None or not tile.visible` with `tile is None or tile.blocks_vision()`
- `is_visible()`: Replace `tile is not None and tile.visible` with `tile is not None and not tile.blocks_vision()`
- **Danger**: Ensure semantics are preserved (is_blocking returns True when blocking, blocks_vision returns True when blocking — same polarity)
- File: `dnd/core/gridmap.py`
- Test: Full `pytest`. Verify FOV and pathfinding produce identical results.

**A.5: Entity `blocks_walking()` override + GridMap unification** ✓ DONE
- Added `non_blocking: bool` field to Entity (default False)
- Added `blocks_walking()` override: checks self-avoidance + non_blocking flag
- Rewrote `is_walkable_for()` to use `BaseBlock.get(uuid).blocks_walking()` polymorphic dispatch
- Removed `_non_blocking_entities` set from GridMap (`__init__`, `unregister_entity`, `clear`)
- Removed `set_entity_blocking()` method from GridMap
- Death handler (`conditions.py`) sets `entity.non_blocking = True` instead of `get_map().set_entity_blocking()`
- Removed `get_map` import from `conditions.py` (was only used for set_entity_blocking)
- Files: `dnd/entity.py`, `dnd/core/gridmap.py`, `dnd/conditions.py`
- New test: `examples/test_entity_blocking.py` (6 tests: blocks others, self-avoidance, dead body, pathfinding, polymorphic dispatch, no-requester)
- Ancillary fix: `EventQueue.reset()` now clears `_on_event_callbacks` (was leaking between tests)
- Test: `pytest examples/test_entity_blocking.py examples/test_spike_zone.py examples/spatial_events_test.py` — 22/22 pass

### Phase B: Condition Management — DONE

Pushed condition management down from Entity to BaseBlock. Entity deletes its overrides and inherits.

**What changed:**
- `external_conditions` + `terrain_conditions` unified into `linked_conditions` on BaseCondition
- `add_external_condition()` + `add_terrain_condition()` → `add_linked_condition()`
- `remove_condition_by_uuid()` moved to BaseBlock (Entity deletes override)
- `_remove_condition_tree()` moved to BaseBlock (Entity deletes override)
- `remove_condition()` upgraded on BaseBlock with full tree traversal (Entity deletes override)
- `advance_duration()` added to BaseBlock (no saving throws — Entity keeps `advance_duration_condition()` for saves)
- `Encounter._environment_step()` advances tile condition durations at round end
- `GridMap.get_tiles_with_conditions()` added for environment step
- Test: `examples/test_tile_condition_duration.py`

### Phase Dependency

```
Phase A (Spatial Blocking) — DONE     Phase B (Condition Management) — DONE
  A.1 → A.2 → A.3 → A.4               B.1 → B.2 → B.3 → B.4 → B.5 → B.6
```

Both phases complete. Tiles and entities are now first-class BaseBlock condition hosts with shared cleanup logic.

Both phases must be fully stable before any items system work begins.

**Phase A Status: COMPLETE** — All 5 steps (A.1–A.5) implemented and tested. Tiles and Entities both use polymorphic `blocks_walking()`/`blocks_vision()` via BaseBlock interface. GridMap predicates are fully polymorphic. Ready for items system extension.
