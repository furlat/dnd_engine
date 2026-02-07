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

**Entity** — deferred. Currently GridMap handles entity blocking via `_entities_by_position` + `_non_blocking_entities`. This works and doesn't need to change for the BaseBlock refactor. Entity override can be added later when needed.

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
# GridMap.is_walkable() — currently tile-only, becomes:
def is_walkable(self, x, y, mode=MovementMode.WALKING):
    tile = self._tiles.get((x, y))
    if tile is None:
        return False
    if tile.blocks_walking(mode=mode):
        return False
    # Future: check objects at position
    # for obj_uuid in self._objects_by_position.get((x, y), set()):
    #     obj = BaseBlock.get(obj_uuid)
    #     if obj and obj.blocks_walking(mode=mode):
    #         return False
    return True

# GridMap.is_blocking() — currently tile-only, becomes:
def is_blocking(self, x, y):
    tile = self._tiles.get((x, y))
    if tile is None:
        return True  # No tile = blocks vision
    if tile.blocks_vision():
        return True
    # Future: check objects at position
    return False
```

**The algorithms don't change.** `compute_fov(origin, self.is_blocking, ...)` and `dijkstra(start, walkable_check, ...)` keep receiving the same callback signatures. The callbacks internally become polymorphic.

### 1.6 `requesting_entity_uuid` Parameter

Both methods accept `requesting_entity_uuid: Optional[UUID] = None`. Currently unused — always returns the same answer regardless of who's asking.

**Future use cases:**
- **Invisibility**: Entity A is invisible to Entity B but not to Entity C (has See Invisibility)
- **Darkvision**: A creature with darkvision can see through dim light that blocks normal vision
- **Hiding**: A hidden entity doesn't "block" vision for entities that can't detect it
- **Ethereal**: Ethereal entities pass through solid objects

This parameter is a **future-proofing slot**. Current implementations ignore it.

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

**A.1: Move `MovementMode` enum from `base_tiles.py` to `base_block.py`**
- Cut `MovementMode` class from `dnd/core/base_tiles.py`
- Paste into `dnd/core/base_block.py` (before `BaseBlock` class, after imports)
- Update `base_tiles.py` to import: `from dnd.core.base_block import BaseBlock, MovementMode`
- Update all other importers: `dnd/actions.py`, `dnd/core/gridmap.py`, test files
- Alternatively: keep re-exporting from `base_tiles.py` for backwards compat
- File targets: `dnd/core/base_block.py`, `dnd/core/base_tiles.py`, `dnd/actions.py`, `dnd/core/gridmap.py`
- Test: `pytest` — all tests pass, no import errors

**A.2: Add `blocks_walking()`/`blocks_vision()` defaults to BaseBlock**
- Add both methods to `BaseBlock` class, both return `False`
- `blocks_walking` signature: `(self, requesting_entity_uuid=None, mode=MovementMode.WALKING) -> bool`
- `blocks_vision` signature: `(self, requesting_entity_uuid=None) -> bool`
- File: `dnd/core/base_block.py`
- Test: `pytest` — all tests pass (methods are additive, no behavior change)

**A.3: Override in Tile**
- Add `blocks_walking()` override: `return self.get_movement_cost(mode) <= 0`
- Add `blocks_vision()` override: `return not self.visible`
- File: `dnd/core/base_tiles.py`
- Test: `pytest` + manual verification that Tile overrides match existing behavior

**A.4: Update GridMap predicates to use polymorphic methods**
- `is_walkable()`: Replace `tile.get_movement_cost(mode) > 0` with `not tile.blocks_walking(mode=mode)`
- `is_blocking()`: Replace `tile is None or not tile.visible` with `tile is None or tile.blocks_vision()`
- `is_visible()`: Replace `tile is not None and tile.visible` with `tile is not None and not tile.blocks_vision()`
- **Danger**: Ensure semantics are preserved (is_blocking returns True when blocking, blocks_vision returns True when blocking — same polarity)
- File: `dnd/core/gridmap.py`
- Test: Full `pytest`. Verify FOV and pathfinding produce identical results.

### Phase B: Condition Management

Delicate refactor — touches core condition lifecycle. Incremental steps with tests after each.

**B.1: Add `remove_condition_by_uuid()` to BaseBlock**
- Simple method: look up in `active_conditions_by_uuid`, delegate to `self.remove_condition(name)`
- Verify Entity's version can be replaced by calling `super()`
- File: `dnd/core/base_block.py`
- Test: Full `pytest` suite

**B.2: Move `_remove_condition_tree()` to BaseBlock**
- Copy from Entity, replace `Entity.get()` with `BaseBlock.get()`, replace tile GridMap lookup with `BaseBlock.get(tile_uuid)`
- Keep Entity's version as pass-through to `super()`
- **Danger**: Don't change `BaseBlock.remove_condition()` yet — only `Entity.remove_condition()` should call the tree
- Files: `dnd/core/base_block.py`, `dnd/entity.py`
- Test: Full `pytest`. Concentration spell cleanup, zone spell cleanup, sub-condition chains.

**B.3: Upgrade `BaseBlock.remove_condition()` to use `_remove_condition_tree()`**
- `BaseBlock.remove_condition()` now calls `_remove_condition_tree()` for full cross-object cleanup
- `Entity.remove_condition()` override still adds Entity-specific logic but delegates tree traversal
- **Danger**: Avoid double-cleanup — ensure override is clean
- Files: `dnd/core/base_block.py`, `dnd/entity.py`
- Test: Full `pytest`. Tile with condition that has `external_conditions` on entity → remove → verify cleanup.

**B.4: Add `advance_duration()` to BaseBlock**
- Simple duration ticking: decrement, remove if expired. No saving throws.
- File: `dnd/core/base_block.py`
- Test: Tile with duration=3 condition, advance 3 times, verify removed.

**B.5: Add Environment Step in Encounter**
- New `Encounter._environment_step()` called from `_advance_round()` (line 428)
- Queries GridMap for tiles and floor objects with active conditions
- Calls `advance_duration()` on each
- May need new GridMap iterators: `get_all_tiles_with_conditions()`, `get_all_objects_with_conditions()`
- Files: `dnd/encounter.py`, `dnd/core/gridmap.py`
- Test: Apply 2-round condition to tile, run 2 full rounds, verify expired after round 2's environment step.

### Phase Dependency

```
Phase A (Spatial Blocking)     Phase B (Condition Management)
  A.1 → A.2 → A.3 → A.4        B.1 → B.2 → B.3 → B.4 → B.5
```

Phases A and B are **independent** — can be done in either order or interleaved. Each step within a phase depends on the previous step.

Both phases must be fully stable before any items system work begins.
