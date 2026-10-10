# Vision, Hiding, and Cover Systems - Design Plan

This document covers 4 interconnected systems that all feed into the Senses pipeline: **lighting/obscurement**, **invisibility integration**, **hiding/stealth**, and **cover**.

```
Light System → Obscurement → Hiding → Cover
     │              │           │        │
     ▼              ▼           ▼        ▼
 Tile property  FOV filter   Entity    Attack/save
 (per tile)     (visibility) state     modifier
                     │
                     └──► All feed into Entity.update_entity_senses()
```

The core architectural challenge: all 4 systems need to interact with the Senses pipeline, which is a low-level routine that wants to be ignorant of high-level game concepts. The key question is: *where does the filtering logic live?*

---

## Section 1: Current Visibility Pipeline

### Existing Flow

```
Tile.visible (bool) → GridMap.is_blocking(x,y) → shadowcast compute_fov()
  → visible_positions → Entity.compute_senses_from_position()
  → Senses.update_senses(entities, visible, walkable, paths)
```

### Existing Infrastructure

| Component | File | Line | Status |
|-----------|------|------|--------|
| `SensesType` enum | `dnd/blocks/sensory.py` | 15-19 | Declared: BLINDSIGHT, DARKVISION, TREMORSENSE, TRUESIGHT |
| `Senses.extra_senses` | `dnd/blocks/sensory.py` | 27 | `List[SensesType]`, populated manually |
| `Invisible.can_see_invisible()` | `dnd/conditions.py` | 509-511 | Static method, checks TRUESIGHT + TREMORSENSE |
| `Tile.visible` | `dnd/core/base_tiles.py` | 54 | Binary (wall/not wall), no gradations |
| `Armor.stealth_disadvantage` | `dnd/blocks/equipment.py` | 151-154 | `Optional[bool]` field, never applied as modifier |
| `GridMap.is_blocking()` | `dnd/core/gridmap.py` | 304-307 | Binary, checks `Tile.visible` |
| `Entity.update_entity_senses()` | `dnd/entity.py` | 1590-1617 | Full FOV + paths recompute |
| `Entity.update_entity_visibility()` | `dnd/entity.py` | 1625-1645 | FOV-only (during movement) |
| `Entity.passive_skill()` | `dnd/entity.py` | - | `10 + skill bonus + advantage modifier` (exists) |

**Key observations:**
- `Invisible` condition adds contextual advantage/disadvantage to attack/AC modifiers but is **not connected to senses** - an invisible entity still appears in `senses.entities`
- `TileEffectCondition` in `dnd/tile_conditions.py` does NOT have `heavily_obscured`/`lightly_obscured` fields (contrary to original plan notes - these need to be added)
- `Tile.visible` is purely binary (wall vs. not wall) - no light/obscurement gradations exist

---

## Section 2: D&D 5e SRD Rules Reference

### 2a. Light Levels (3 tiers)

| Level | Obscurement | Effect |
|-------|-------------|--------|
| Bright Light | None | Normal vision |
| Dim Light | Lightly Obscured | Disadvantage on Perception (sight) |
| Darkness | Heavily Obscured | Effectively Blinded |

### 2b. Obscurement (2 tiers)

- **Lightly Obscured** (dim light, patchy fog, moderate foliage): Disadvantage on Perception checks relying on sight
- **Heavily Obscured** (darkness, opaque fog, dense foliage): Blocks vision entirely - creature effectively has Blinded condition for seeing into/through area

### 2c. Special Senses

| Sense | Bypasses | Limitation |
|-------|----------|------------|
| Darkvision | Darkness → dim light, dim light → bright light | Still disadvantage on Perception in what was darkness (now treated as dim) |
| Blindsight | All visual obscurement | Specific radius only |
| Tremorsense | All visual obscurement | Must share ground, can't detect flying |
| Truesight | Everything (darkness, magical darkness, invisibility, illusions) | Specific radius |

### 2d. Hiding (Stealth vs Perception)

- Requires: not clearly visible to observer (obscurement, cover, etc.)
- Dexterity (Stealth) check vs Wisdom (Perception) check or passive Perception
- Invisible creatures can always try to hide
- Attacking (hit or miss) reveals location
- Unseen attacker: advantage on attacks
- Attacking unseen target: disadvantage on attacks

### 2e. Cover

| Type | AC Bonus | DEX Save Bonus | Notes |
|------|----------|----------------|-------|
| Half Cover | +2 | +2 | Low wall, creature, tree trunk |
| Three-Quarters | +5 | +5 | Portcullis, arrow slit |
| Total Cover | Can't be targeted | N/A | Full wall, fully concealed |

- Another creature (ally or enemy) provides half cover
- Only highest cover applies (don't stack)

### 2f. Invisibility (SRD)

- Impossible to see without magic/special sense
- For hiding: treated as heavily obscured
- Attack rolls against: disadvantage
- Invisible creature's attacks: advantage
- Can always try to hide
- Still detectable by noise/tracks

---

## Section 3: Obscurement System

### Core Concept

Add **per-tile obscurement level** that feeds into the visibility pipeline.

```python
class ObscurementLevel(str, Enum):
    NONE = "none"              # Bright light, clear
    LIGHTLY_OBSCURED = "light" # Dim light, patchy fog
    HEAVILY_OBSCURED = "heavy" # Darkness, opaque fog, Fog Cloud
```

### 3a. Tile-Level Changes

- Add `obscurement: ObscurementLevel = ObscurementLevel.NONE` to Tile
- Zone spells (Fog Cloud, Darkness, Cloudkill) set this via tile conditions
- TileEffectCondition gets `heavily_obscured: bool` and `lightly_obscured: bool` fields that set tile obscurement on apply

### 3b. Light Sources - Two Design Options

How do light sources (torches, Light cantrip, Daylight spell) set tile obscurement?

**Option A: AoE zone pattern** (like existing zone spells)
- Light = ZoneControlCondition with a sphere shape
- Spatial handlers fire on entry/exit to update tile conditions
- Pro: reuses existing pattern
- Con: heavy for something as common as light, event-driven overhead

**Option B: Mini-shadowcast from light position** (preferred)
- Light source computes its own FOV via `compute_fov(light_position, light_radius)`
- All tiles in that FOV get `obscurement` set to NONE (bright) or LIGHTLY_OBSCURED (dim, at edge)
- Runs at GridMap level, not event-driven
- Pro: naturally handles walls blocking light, efficient, low-level
- Con: needs to track light sources for cleanup/movement

**Why Option B feels right**: Light is fundamentally a spatial property - it follows LOS rules (walls block it). A light source is not a "zone effect on entry" - it's a property of tiles computed from a point. The shadowcast infrastructure already exists. The light source would:
1. On creation: run `compute_fov(position, radius)` → set tiles to bright/dim
2. On movement: re-run from new position, clean up old tiles
3. On removal: reset tiles to default obscurement
4. This could be a lightweight GridMap-level system, not condition/event-driven

### 3c. GridMap Changes - Two-Tier Visibility

- `is_blocking(x, y)` stays binary (walls block LOS completely)
- NEW: `get_obscurement(x, y) -> ObscurementLevel` for post-FOV filtering
- Shadowcast still computes raw FOV (what tiles you CAN see through)
- Post-FOV: each visible tile's obscurement level determines HOW you see it

### 3d. Entity.update_entity_senses() Integration

This is the key integration point. The filtering lives at Entity level, not Senses level.

```
1. compute_fov() → raw visible positions (unchanged)
2. NEW: For each visible position, check obscurement level
3. NEW: Apply entity's special senses to override obscurement:
   - Darkvision: heavily_obscured (darkness) → lightly_obscured within range
   - Blindsight: ignore all obscurement within range
   - Truesight: ignore all obscurement within range
   - Tremorsense: ignore obscurement for grounded entities within range
4. NEW: Filter entities by obscurement:
   - Entity in heavily_obscured tile AND no bypass sense → NOT in senses.entities
   - Entity in lightly_obscured tile → still visible but flagged
5. Result: senses.entities only contains entities you can actually perceive
```

### 3e. Invisible Condition Integration

Current `Invisible` condition adds contextual advantage/disadvantage to attack/AC modifiers.
Problem: It's **not connected to senses at all** - an invisible entity still appears in `senses.entities`.

Proposed fix:
- Invisible entities treated as "heavily obscured" for visibility purposes
- `Entity.update_entity_senses()` checks: does the observed entity have Invisible condition?
  - If yes AND observer lacks TRUESIGHT/BLINDSIGHT/TREMORSENSE → exclude from senses.entities
  - The advantage/disadvantage modifiers on attacks remain as-is (for when you know location via other means)

**Note**: This means `Entity.update_entity_senses()` needs to check conditions on OTHER entities. Currently it only queries GridMap. This is where the integration lives - Entity level, not Senses level.

---

## Section 4: Hiding System

### 4a. Hidden State

- New condition: `Hidden` (marker condition like HasAttacked)
- Applied via `Hide` action (uses Dexterity Stealth check)
- Stores stealth roll result on the condition
- Ends when: attack (hit or miss), no longer obscured/behind cover, or detected

### 4b. Detection

- Passive Perception: `10 + WIS modifier + Perception proficiency` (already exists as `Entity.passive_skill("perception")`)
- If `stealth_result > passive_perception` → hidden
- Active search: Perception check vs stealth roll (uses existing `skill_check` system)

### 4c. Requirements to Hide

- Must be in lightly/heavily obscured area, OR behind cover, OR invisible
- Can't hide from creature that can see you clearly

### 4d. Combat Effects

Already partially handled by Unseen Attacker/Target rules:
- Hidden + attacking: advantage (then reveal location)
- Attacking hidden creature: disadvantage (or auto-miss if wrong position)

### 4e. Armor Stealth Disadvantage

- `Armor.stealth_disadvantage` field exists (`dnd/blocks/equipment.py:151-154`) but isn't applied
- When armor is equipped with `stealth_disadvantage=True`: add disadvantage modifier to Stealth skill via `self_static` channel

---

## Section 5: Cover System

### 5a. Cover Calculation

- Raycasting from attacker to target through grid
- Check obstacles between attacker and target position
- Another creature in path → half cover

### 5b. Implementation Options

**Option A: Simple creature-based cover only**
- Check if any creature occupies a cell between attacker and target
- Quick to implement, covers common tactical case
- No terrain geometry needed

**Option B: Full raycasting cover**
- Tile property: `provides_cover: CoverType` (NONE, HALF, THREE_QUARTERS, TOTAL)
- Ray from attacker center to target corners (SRD: check at least 1 corner unblocked for any targeting)
- More complex but complete

### 5c. Total Cover = LOS Block for Targeting

- Total cover functions like a non-visible tile: entity CANNOT be targeted
- This means total cover should remove the entity from valid_targets in `get_available_actions`
- Implementation: either exclude from `senses.entities` (like heavily obscured) or filter in targeting

### 5d. Modifier Application (Half/Three-Quarters)

- Cover provides AC bonus → target's `ac_bonus` gets numerical modifier
- Cover provides DEX save bonus → target's DEX save gets numerical modifier
- Computed at attack time (like cross-entity propagation) or cached in senses

### 5e. Integration with Attack Action

- Attack action already does cross-entity modifier propagation
- Cover would add to `ac_bonus.from_target_static` channel (like other target-based modifiers)
- Or: computed during `_validate()` and added as temporary modifier

---

## Section 6: Impact on get_available_actions / Targeting

Currently `get_available_actions()` builds valid_targets from `senses.entities` (what you can see). Every system here affects this:

| System | Effect on Targeting |
|--------|-------------------|
| **Obscurement** | Heavily obscured entities excluded from `senses.entities` → not valid targets |
| **Invisibility** | Invisible entities excluded from `senses.entities` (unless observer has bypass sense) → not valid targets |
| **Total Cover** | Entity behind total cover excluded from valid targets (can't be targeted at all) |
| **Half/Three-Quarters Cover** | Entity IS a valid target, but AC/DEX save modifiers apply during attack resolution |
| **Hiding** | Hidden entity not in `senses.entities` → not valid target |

**Key insight**: Most of this filtering happens **upstream** in `Entity.update_entity_senses()`, so `get_available_actions` doesn't need to change much - it already depends on `senses.entities` for targeting. The exceptions are:
- Cover modifiers: applied during attack, not during targeting
- AoE spells: may still affect entities you can't directly target (SRD: "total cover can't be targeted directly, but some spells can reach by including in area of effect")

---

## Section 7: Light Source Design

### Mini-Shadowcast Approach (Option B from Section 3b)

Light sources compute their own FOV to determine which tiles they illuminate.

### Light Source Tracking

- Registry on GridMap: `Dict[UUID, LightSource]` mapping source UUID → light data
- `LightSource` data: position, bright_radius, dim_radius, is_magical, source_uuid
- GridMap methods: `add_light_source()`, `remove_light_source()`, `move_light_source()`

### How It Works

1. **Creation**: `compute_fov(position, bright_radius + dim_radius)` → set tiles
   - Tiles within `bright_radius`: `obscurement = NONE`
   - Tiles between `bright_radius` and `bright_radius + dim_radius`: `obscurement = LIGHTLY_OBSCURED`
2. **Movement** (entity carrying torch): re-run from new position, reset old tiles to default
3. **Removal**: reset all illuminated tiles to default obscurement
4. **Default obscurement**: configurable per-map (dungeon = HEAVILY_OBSCURED, outdoors = NONE)

### Conflicting Light Sources

- Multiple sources can overlap - **brightest wins**
- Track light contributions per tile (list of source UUIDs) for cleanup
- When a source is removed, recalculate affected tiles from remaining sources

### Magical Darkness

- Flag on obscurement: `is_magical_darkness: bool` on tile
- Normal light sources cannot override magical darkness
- Magical darkness overrides normal light
- Only Truesight/Blindsight bypass magical darkness (Darkvision does NOT)
- Spells: Darkness (15ft radius magical darkness), Daylight (counters Darkness if ≥3rd level)

### Light Spells

| Spell | Bright Radius | Dim Radius | Notes |
|-------|--------------|------------|-------|
| Light (cantrip) | 20ft | 20ft | Attached to object |
| Dancing Lights (cantrip) | 10ft | 10ft | Up to 4 sources, concentration |
| Daylight (3rd level) | 60ft | 60ft | Dispels darkness ≤3rd level |
| Continual Flame (2nd level) | 20ft | 20ft | Permanent, not sunlight |

---

## Section 8: Spells Requiring These Systems

| Spell | Systems Needed | Notes |
|-------|---------------|-------|
| **Fog Cloud** | Obscurement (heavily obscured zone) | ZoneControlCondition pattern, no damage, just obscurement |
| **Darkness** | Obscurement + magical darkness flag | Darkvision doesn't help, only Truesight/Blindsight |
| **Faerie Fire** | Anti-invisibility + advantage | Outlined creatures can't benefit from invisibility, attacks have advantage |
| **Light** (cantrip) | Light source system | Bright light in 20ft radius, dim light 20ft beyond |
| **See Invisibility** | Senses interaction | Grant ability to see invisible creatures (add to extra_senses or similar) |
| **Daylight** | Light source + darkness counter | Bright 60ft, dim 60ft, dispels Darkness |

---

## Section 9: Implementation Priority

Recommended order (each builds on previous):

1. **Obscurement on tiles** - Add `ObscurementLevel` to Tile, add fields to TileEffectCondition
2. **Senses integration** - `Entity.update_entity_senses()` checks obscurement + special senses
3. **Light sources** - Mini-shadowcast approach to illuminate tiles
4. **Invisible → Senses hookup** - Remove invisible entities from `senses.entities` when not perceivable
5. **Fog Cloud + Darkness spells** - First consumers of obscurement system
6. **Cover system** - Independent of above, can be done in parallel after step 1
7. **Hiding system** - Builds on obscurement + cover (needs both to determine "where can you hide")
8. **Armor stealth disadvantage** - Small, wire up existing field

---

## Section 10: Open Design Questions

1. **Where does cover live?** Cached in senses (recomputed on position changes) or computed at attack time?
2. **AoE and total cover**: Should AoE spells check cover per-target? SRD says yes for some spells.
3. **Hiding and AoE**: Can you target a hidden creature's known position with an AoE spell?
4. **Light source tracking**: Per-tile contribution list vs. full recompute on any light change?
5. **Default map lighting**: Per-map setting (dungeon vs. outdoor) or per-tile default?
