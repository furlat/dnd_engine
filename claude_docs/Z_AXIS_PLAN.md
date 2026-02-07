# Z-Axis / Verticality - Design Plan

Design doc for adding 3D verticality to the spatial system. This is a late feature that should be tackled after the vision/hiding/cover systems are complete.

---

## Section 1: Current Infrastructure

| Component | File | Status |
|-----------|------|--------|
| `Tile.height` | `dnd/core/base_tiles.py:98` | `int = 0`, declared but unused - no code reads it |
| `MovementMode.FLYING` | `dnd/core/base_tiles.py:24` | Enum value exists, pathfinding supports flying cost |
| `MovementMode.SWIMMING` | `dnd/core/base_tiles.py:25` | Enum value exists, pathfinding supports swimming cost |
| `MovementMode.BURROWING` | `dnd/core/base_tiles.py:26` | Enum value exists, pathfinding supports burrowing cost |
| Tile per-mode costs | `dnd/core/base_tiles.py` | `walking_cost`, `flying_cost`, `swimming_cost`, `burrowing_cost` as ModifiableValues |
| Dijkstra `cost_func` | `dnd/core/dijkstra.py` | Accepts mode-specific cost function |
| Position format | everywhere | Always `Tuple[int, int]` - no Z coordinate |

The pathfinding already uses mode-specific tile costs, and flying mode ignores ground-based difficult terrain. But there is no actual Z coordinate - flying is currently just a 2D movement mode with different cost rules.

---

## Section 2: What Z-Axis Enables

### Gameplay Features

- **Elevation**: Height differences affecting range, cover, and advantage
- **Flying movement**: True 3D pathfinding (not just "flying cost" on 2D tiles)
- **Falling damage**: 1d6 bludgeoning per 10ft fallen
- **Vertical spells**: Fly, Levitate, Reverse Gravity
- **Height advantage**: Higher ground advantage on ranged attacks (BG3-style, not SRD-official but popular)
- **Terrain interaction**: Cliffs, pits, multi-story buildings

### Spells Blocked Until Z-Axis

| Spell | Level | Reason |
|-------|-------|--------|
| Fly | 3rd | Grants 60ft fly speed, needs 3D movement |
| Levitate | 2nd | Raises creature 20ft, needs Z position |
| Reverse Gravity | 7th | Inverts gravity in cylinder, needs Z-axis |
| Water Breathing | 3rd | Underwater exploration, needs depth |
| Water Walk | 3rd | Walk on liquid surfaces, needs surface/depth distinction |
| Feather Fall | 1st (reaction) | Reduces falling damage, needs fall detection |

---

## Section 3: Architectural Decisions Needed

### Position Format

**Option A: Extend tuple to `(x, y, z)`**
- All position references change from `Tuple[int, int]` to `Tuple[int, int, int]`
- Pro: explicit, type-safe
- Con: massive refactor - every `(x, y)` in the codebase needs updating

**Option B: Z on entity, not in position**
- Positions stay `(x, y)`, entity gets `z: int` field
- Pro: minimal refactor, 2D map still works, Z is optional
- Con: spatial lookups need both position + Z, two entities at same (x,y) but different Z harder to track

**Option C: Z on tile, entities inherit**
- `Tile.height` already exists - entity Z = tile height + offset
- Flying entity: offset above tile height
- Pro: ground entities just use tile height automatically
- Con: multiple entities at different heights on same tile still needs entity-level Z

### 3D FOV

**Option A: Layer-based shadowcast**
- Run 2D shadowcast per Z-layer
- Entities on higher tiles can see over lower walls
- Pro: reuses existing shadowcast
- Con: doesn't handle diagonal 3D LOS (looking down a cliff)

**Option B: True 3D shadowcast extension**
- Extend octant-based shadowcast to octants in 3D (48 sectors instead of 8)
- Pro: accurate 3D LOS
- Con: significant algorithm complexity

**Option C: 2D shadowcast + vertical check**
- Keep 2D FOV, add separate vertical LOS check between observer and target
- If 2D FOV says visible AND vertical check passes → visible
- Pro: simple, mostly reuses existing code
- Con: doesn't handle cases like seeing through a gap in a wall from elevation

### 3D Pathfinding

- Extend Dijkstra with vertical neighbors (up/down connections between tiles)
- Flying: can move to any adjacent tile including vertically
- Walking: can only move to tiles with connected heights (stairs, ladders, slopes)
- Cost: vertical movement costs extra (e.g., climbing = 2x movement cost per SRD)

### Visualization

Options for displaying Z-axis in terminal:
- **Layer view**: Show one Z-level at a time, cycle with keys
- **Side view**: Toggle to cross-section view
- **Height indicators**: Numbers/colors on 2D map showing elevation
- **BG3-style**: Just show 2D map with height numbers, flying entities get icon

### Fall Detection

- When entity loses flying (concentration broken, incapacitated while flying)
- When entity is pushed off a ledge (Shove, Thunderwave)
- When entity walks off an edge without flying
- 1d6 bludgeoning per 10ft fallen, land prone

---

## Section 4: Estimated Scope

This is a major architectural change - converting the spatial system from 2D to 2.5D/3D. Key areas affected:

| Area | Impact |
|------|--------|
| Position types | Every `Tuple[int, int]` reference |
| GridMap | Entity tracking, spatial events, tile lookup |
| Shadowcast | FOV computation |
| Dijkstra | Pathfinding with vertical neighbors |
| Senses | Entity visibility with height |
| Move action | Vertical movement, falling |
| AoE shapes | 3D shape calculations |
| CLI visualization | Displaying height information |
| Entity creation | Z position in factories |

Should be tackled as a standalone project after the vision/hiding/cover systems are complete, since those systems establish the Senses pipeline patterns that Z-axis will extend.

---

## Section 5: Related Documentation

- `TERRAIN_MOVEMENT_SYSTEM.md` - Current 2D terrain and movement system
- `VISION_HIDING_COVER_PLAN.md` - Vision systems that Z-axis will extend
- `AOE_TARGETING_REFERENCE.md` - AoE shapes that will need 3D versions
