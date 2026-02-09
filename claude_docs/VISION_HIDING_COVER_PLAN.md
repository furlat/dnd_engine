# Vision, Hiding & Cover — Layered Design

Three systems, each building on the previous. Same polymorphic pattern as Dijkstra/walking.

```
Layer 1: Stealth      Pure LOS + stealth vs perception. No light.
Layer 2: Light         Per-tile obscurement. Extends stealth detection.
Layer 3: Cover         Raycast partial cover. AC/DEX save mods. Cover enables hiding.
```

---

## Architecture: Same Pattern as Dijkstra

Walking uses this pipeline:
```
BaseBlock.blocks_walking(requesting_uuid)        ← polymorphic, base_block.py:328
GridMap.is_walkable_for(x, y, requesting_uuid)    ← calls BaseBlock.get(uuid).blocks_walking()  gridmap.py:272
Entity.compute_senses_from_position(entity_uuid)  ← grid.compute_paths(entity_uuid)  entity.py:1561
```

New perception pipeline, same shape:
```
BaseBlock.is_perceivable_by(observer_uuid)              ← polymorphic, base_block.py, default True
GridMap.get_perceivable_entities(origin, dist, observer) ← calls BaseBlock.get(uuid).is_perceivable_by()
Entity.compute_senses_from_position(entity_uuid)         ← grid.get_perceivable_entities()  entity.py:1597-1602
```

**No new import paths.** Only extensions of existing imports from same modules:

```
base_block.py  ← add ObscurementLevel, CoverType enums + is_perceivable_by(), provides_cover()
    ↑ (already imported by entity.py:18, base_tiles.py)
base_tiles.py  ← extend import to include ObscurementLevel, CoverType
gridmap.py     ← no new imports, add get_perceivable_entities()
sensory.py     ← no changes (SensesType already defined: line 15-19)
    ↑ (already imported by entity.py:25)
entity.py      ← extend 'from sensory import Senses' to include SensesType
               ← extend 'from base_block import ...' to include ObscurementLevel
               ← override is_perceivable_by()
```

---

## Existing Infrastructure

| Component | File : Line | Status |
|-----------|-------------|--------|
| `SensesType` enum (BLINDSIGHT, DARKVISION, TREMORSENSE, TRUESIGHT) | `sensory.py:15-19` | Declared, populated manually |
| `Senses.extra_senses: List[SensesType]` | `sensory.py:27` | Used by Invisible checks |
| `BaseBlock.blocks_walking(requesting_uuid)` | `base_block.py:328-332` | Polymorphic, default False |
| `BaseBlock.blocks_vision(requesting_uuid)` | `base_block.py:334-337` | Polymorphic, default False |
| `Tile.blocks_vision()` | `base_tiles.py:105-107` | Returns `not self.visible` |
| `GridMap.is_blocking(x, y)` | `gridmap.py:305-315` | Checks tile + objects for LOS |
| `GridMap.get_visible_entities(origin, max_dist)` | `gridmap.py:615-625` | FOV → entity dict, no filtering |
| `GridMap.is_walkable_for(x, y, uuid)` | `gridmap.py:272-298` | Entity + object occupancy check |
| `Entity.compute_senses_from_position()` | `entity.py:1561-1613` | FOV + paths + entity collection |
| `Entity.update_entity_visibility()` | `entity.py:1668-1698` | FOV-only (during movement) |
| `Entity.passive_skill(skill)` | `entity.py` | Returns `10 + skill bonus + advantage mod` |
| `Invisible.can_see_invisible()` | `conditions.py:507-510` | Checks TRUESIGHT + TREMORSENSE (missing BLINDSIGHT) |
| `Armor.stealth_disadvantage: Optional[bool]` | `equipment.py:135-138` | Field exists, never applied |
| `bresenham_line(start, end)` | `geometry.py:49-82` | Returns `List[Tuple[int,int]]` |

**Key gaps:**
- Invisible condition adds attack advantage/disadvantage but is **not connected to senses** — invisible entities still appear in `senses.entities`
- Tile has binary `visible` flag (wall/not wall) — no obscurement gradations
- `Armor.stealth_disadvantage` exists but is never wired to a modifier

---

## Layer 1: Stealth (no light)

Pure LOS + senses range. If entity is in your FOV, you see them — UNLESS they have stealth/invisibility flags set.

### Design Principle: Flags on BaseBlock, Not Condition Knowledge

The perceivability system uses **condition-agnostic flags** on BaseBlock. Conditions (Hidden, Invisible, or future effects) set/unset these flags. The perception pipeline reads them without knowing what set them. This means items can also be hidden/invisible (a trap with `_stealth_dc=15`, an invisible chest).

```
Condition layer (conditions.py)          BaseBlock flags (base_block.py)
┌──────────────────────┐                ┌─────────────────────────┐
│ Hidden._apply()      │───sets────────►│ _stealth_dc: int = 15   │
│ Hidden.cleanup()     │───unsets──────►│ _stealth_dc: None       │
│ Invisible._apply()   │───sets────────►│ _is_invisible: True     │
│ Invisible.cleanup()  │───unsets──────►│ _is_invisible: False    │
│ (future conditions)  │───sets────────►│ (same flags)            │
└──────────────────────┘                └─────────────────────────┘
                                                    │
                                                    ▼ read by
                                        ┌─────────────────────────┐
                                        │ is_perceivable_by(      │
                                        │   passive_perception,   │
                                        │   extra_senses          │
                                        │ )                       │
                                        └─────────────────────────┘
```

No Entity importing conditions. No conditions importing Entity. Flags are the interface.

### 1a. BaseBlock Perceivability Fields + Method

Add to `base_block.py` next to `blocks_walking()` and `blocks_vision()`:

```python
# Fields
_stealth_dc: Optional[int] = Field(default=None, exclude=True)
_is_invisible: bool = Field(default=False, exclude=True)

# Method
def is_perceivable_by(self,
                      passive_perception: int = 0,
                      extra_senses: Optional[List['SensesType']] = None) -> bool:
    """Whether this block can be perceived by an observer with given perception.
    Reads _stealth_dc and _is_invisible flags. Conditions set these flags."""
    senses = extra_senses or []

    if self._is_invisible:
        if not (SensesType.TRUESIGHT in senses or
                SensesType.BLINDSIGHT in senses or
                SensesType.TREMORSENSE in senses):
            return False

    if self._stealth_dc is not None:
        if self._stealth_dc > passive_perception:
            return False

    return True
```

**Key**: The method takes observer data as parameters, not an observer UUID. The caller extracts its own perception data and passes it down. BaseBlock never looks up the observer.

### 1b. No GridMap Changes

GridMap does NOT need a new method. The existing entity collection loops in `Entity.compute_senses_from_position()` and `Entity.update_entity_visibility()` add the perception filter directly. GridMap stays unchanged.

### 1c. Entity Senses Integration

Add perception filter to the two methods that collect visible entities:

**`compute_senses_from_position()`** (entity.py:1597-1602):

```python
# Replace the entity collection loop with:
visible_entities: Dict[UUID, Tuple[int, int]] = {}

# Get observer perception data (if entity_uuid provided)
obs_perception = 0
obs_senses: List[SensesType] = []
if entity_uuid:
    observer = Entity.get(entity_uuid)
    if observer and isinstance(observer, Entity):
        obs_perception = observer.passive_skill("perception")
        obs_senses = observer.senses.extra_senses

for pos in visible_positions:
    entities = Entity.get_all_entities_at_position(pos)
    for entity in entities:
        if entity_uuid and entity.uuid == entity_uuid:
            continue  # Skip self
        if entity.is_perceivable_by(obs_perception, obs_senses):
            visible_entities[entity.uuid] = pos
```

**`update_entity_visibility()`** (entity.py:1691-1696):

```python
# Replace the entity collection loop with:
visible_entities: Dict[UUID, Tuple[int, int]] = {}
my_perception = self.passive_skill("perception")
my_senses = self.senses.extra_senses

for pos in visible_positions:
    for ent_uuid in grid.get_entities_at(pos):
        if ent_uuid != self.uuid:
            block = BaseBlock.get(ent_uuid)
            if block and block.is_perceivable_by(my_perception, my_senses):
                visible_entities[ent_uuid] = pos
```

Senses are now always subjective — each entity gets a different `senses.entities` dict based on their own perception.

Import addition in entity.py: `from dnd.blocks.sensory import Senses, SensesType`

### 1d. Invisible Condition Changes

`Invisible._apply()` gains one line: `target._is_invisible = True`
`Invisible` cleanup (or a custom `_on_remove` callback): `target._is_invisible = False`

- Fix `can_see_invisible()` (conditions.py:507-510): add BLINDSIGHT to the check
- Keep existing attack advantage/disadvantage contextual modifiers (these still matter for combat rolls even when invisible entity is perceived via special senses)
- After applying/removing Invisible: `Entity.update_all_entities_senses()`

### 1e. Hidden Condition

New in `dnd/conditions.py`:

```python
class Hidden(BaseCondition):
    name: str = "Hidden"
    description: str = "Hidden from observers via Stealth"
    stealth_result: int = 0  # From Stealth check at Hide time
```

**`_apply()`**:
1. Set flag: `target._stealth_dc = self.stealth_result`
2. Unseen Attacker advantage: `self_contextual` AdvantageModifier on `attack_bonus` — callable checks `self.uuid not in target.senses.entities` (if the target can't see the attacker in their senses, attacker gets advantage). This naturally captures ALL perceivability effects since `senses.entities` is already filtered by `is_perceivable_by()`.
3. Register removal handlers (see below)

**Cleanup**: `target._stealth_dc = None` + `Entity.update_all_entities_senses()`

**Removal triggers**:
- EventHandler on ATTACK at EFFECT phase (self as source) → remove Hidden
- EventHandler on TAKE_DAMAGE at EFFECT phase (self as target) → remove Hidden
- EventHandler on CONDITION_APPLICATION at EFFECT phase (self as target, condition name == "Incapacitated") → remove Hidden

**Detection is per-observer, removal is global:**
- `is_perceivable_by()` is checked per-observer (Entity A with perception 15 sees you, Entity B with perception 8 doesn't) — this is just senses filtering, not removal
- Hidden condition removal (attack/damage/condition received) removes it for everyone
- Passive perception only — no Search action for now

### 1f. Hide Action

New in `dnd/actions.py`:

- Cost: 1 action
- Target: SELF
- Execution: Roll Stealth skill check → apply Hidden condition with `stealth_result` = roll result
- After: `Entity.update_all_entities_senses()`
- Register in `setup_standard_actions()` (actions_functional.py)

### 1g. Armor Stealth Disadvantage

Wire up `Armor.stealth_disadvantage` field (equipment.py:135-138):
- In `Armor._on_equip()`: if `stealth_disadvantage`, add DISADVANTAGE modifier to the entity's Stealth skill via `self_static`
- In `Armor._on_unequip()`: remove the modifier
- Track modifier UUID for cleanup (same pattern as other equip hooks)

### 1h. Implementation Steps

1. Add `_stealth_dc`, `_is_invisible` fields + `is_perceivable_by()` to BaseBlock
2. Add perception filter to `compute_senses_from_position()` entity loop
3. Add perception filter to `update_entity_visibility()` entity loop
4. Extend entity.py import: `from dnd.blocks.sensory import Senses, SensesType`
5. Update `Invisible._apply()` to set `_is_invisible` flag + cleanup to unset
6. Fix `Invisible.can_see_invisible()` to include BLINDSIGHT
7. Add Hidden condition (sets `_stealth_dc`, handlers for attack/damage removal)
8. Add Hide action + register in `setup_standard_actions()`
9. Wire up `Armor.stealth_disadvantage`

**Files**: `dnd/core/base_block.py`, `dnd/entity.py`, `dnd/conditions.py`, `dnd/actions.py`, `dnd/actions_functional.py`, `dnd/blocks/equipment.py`
**Tests**: `examples/test_stealth_system.py`

---

## Layer 2: Light / Obscurement

Extends Layer 1. Adds per-tile obscurement that affects stealth detection.

### 2a. ObscurementLevel Enum

Add to `base_block.py` (next to `MovementMode`):

```python
class ObscurementLevel(str, Enum):
    NONE = "none"              # Bright light, clear area
    LIGHTLY_OBSCURED = "light" # Dim light, patchy fog
    HEAVILY_OBSCURED = "heavy" # Darkness, opaque fog
```

### 2b. Tile Fields

Add to Tile in `base_tiles.py`:

```python
obscurement: ObscurementLevel = Field(default=ObscurementLevel.NONE)
is_magical_darkness: bool = Field(default=False)
```

### 2c. GridMap

Add default obscurement field:

```python
default_obscurement: ObscurementLevel = ObscurementLevel.NONE  # Per-map (dungeon=HEAVY, outdoor=NONE)
```

### 2d. TileEffectCondition

Add to `TileEffectCondition` in `tile_conditions.py`:

```python
sets_obscurement: Optional[ObscurementLevel] = None
sets_magical_darkness: bool = False
```

On `_apply()`: set `tile.obscurement` (and `is_magical_darkness` if flagged).
On removal: reset to `GridMap.default_obscurement`.

### 2e. Entity.is_perceivable_by() — Layer 2 extension

The Hidden check gains obscurement awareness. Insert between the existing Hidden check and the return:

```python
# Hidden check (extends Layer 1)
hidden = self.active_conditions.get("Hidden")
if hidden:
    observer = Entity.get(observer_uuid)
    if observer and isinstance(observer, Entity):
        tile = get_map().get_tile(*self.position)
        tile_obs = tile.obscurement if tile else ObscurementLevel.NONE

        # Compute effective obscurement (senses can downgrade it)
        effective_obs = self._compute_effective_obscurement(
            tile_obs, tile.is_magical_darkness if tile else False, observer
        )

        if effective_obs == ObscurementLevel.HEAVILY_OBSCURED:
            return False  # Auto-hidden in heavy obscurement
        elif effective_obs == ObscurementLevel.LIGHTLY_OBSCURED:
            # Lightly obscured: stealth vs perception still applies
            return hidden.stealth_result <= observer.passive_skill("perception")
        else:
            # No obscurement: stealth vs perception
            return hidden.stealth_result <= observer.passive_skill("perception")

return True
```

**Helper on Entity:**

```python
@staticmethod
def _compute_effective_obscurement(
    tile_obs: ObscurementLevel,
    is_magical: bool,
    observer: 'Entity'
) -> ObscurementLevel:
    extra = observer.senses.extra_senses

    # Truesight/Blindsight: ignore all obscurement
    if SensesType.TRUESIGHT in extra or SensesType.BLINDSIGHT in extra:
        return ObscurementLevel.NONE

    # Magical darkness: Darkvision doesn't help
    if is_magical:
        return tile_obs

    # Normal obscurement: Darkvision downgrades by 1
    if SensesType.DARKVISION in extra:
        if tile_obs == ObscurementLevel.HEAVILY_OBSCURED:
            return ObscurementLevel.LIGHTLY_OBSCURED
        elif tile_obs == ObscurementLevel.LIGHTLY_OBSCURED:
            return ObscurementLevel.NONE
    return tile_obs
```

Layer 1 behavior preserved: when `tile_obs` is NONE, no obscurement effect.

### 2f. Heavily Obscured Without Hidden

Entities in heavily obscured tiles are auto-hidden even without the Hidden condition. Add to `is_perceivable_by()` before the Hidden check:

```python
# Heavily obscured tile: auto-hidden (even without Hidden condition)
tile = get_map().get_tile(*self.position)
if tile:
    effective_obs = self._compute_effective_obscurement(
        tile.obscurement, tile.is_magical_darkness, observer
    )
    if effective_obs == ObscurementLevel.HEAVILY_OBSCURED:
        return False
```

This is the SRD rule: "A creature in a heavily obscured area effectively can't be seen" — you don't need to take the Hide action.

### 2g. Zone Spells

**Fog Cloud** (conjuration.py): Zone spell, concentration.
- Heavily obscured zone within sphere radius
- Uses `ZoneControlCondition` pattern
- `TileEffectCondition` with `sets_obscurement=ObscurementLevel.HEAVILY_OBSCURED`

**Darkness** (conjuration.py): Zone spell, concentration.
- Heavily obscured + `sets_magical_darkness=True`
- Darkvision doesn't help, only Truesight/Blindsight bypass

### 2h. Light Sources — DEFERRED

No dynamic light computation yet. Obscurement set manually on tiles or via zone spells. Future light source system would use mini-shadowcast from light position (compute FOV, set bright/dim tiles within radii).

### 2i. Implementation Steps

1. Add `ObscurementLevel` enum to `base_block.py`
2. Add `obscurement` + `is_magical_darkness` fields to Tile
3. Add `default_obscurement` to GridMap
4. Add `sets_obscurement` / `sets_magical_darkness` to `TileEffectCondition`
5. Extend entity.py import to include `ObscurementLevel`
6. Add `_compute_effective_obscurement()` helper to Entity
7. Extend `Entity.is_perceivable_by()` with obscurement logic (heavy = auto-hidden)
8. Implement Fog Cloud and Darkness spells

**Files**: `dnd/core/base_block.py`, `dnd/core/base_tiles.py`, `dnd/core/gridmap.py`, `dnd/tile_conditions.py`, `dnd/entity.py`, `dnd/spells/conjuration.py`
**Tests**: `examples/test_obscurement_system.py`

---

## Layer 3: Cover

Extends Layer 2. Raycast-based partial cover provides AC/DEX save bonuses.

### 3a. CoverType Enum

Add to `base_block.py` (next to `ObscurementLevel`):

```python
class CoverType(str, Enum):
    NONE = "none"
    HALF = "half"                       # +2 AC, +2 DEX saves
    THREE_QUARTERS = "three_quarters"   # +5 AC, +5 DEX saves
    TOTAL = "total"                     # Can't be targeted (= LOS block, already handled by blocks_vision)
```

### 3b. BaseBlock.provides_cover() → CoverType

Polymorphic, default NONE. Same pattern as `blocks_walking()`, `blocks_vision()`:

```python
def provides_cover(self) -> 'CoverType':
    """What level of cover this block provides. Default NONE."""
    return CoverType.NONE
```

Override points:
- **Tile**: NONE by default (walls already block vision entirely via `blocks_vision`)
- **BaseItem**: New `provides_cover_type: CoverType` field (for barricades, low walls, furniture)
- **Entity**: HALF cover (alive entity between attacker and target)

### 3c. Cover Computation

New utility function (in `dnd/core/geometry.py` or `dnd/actions.py`):

```python
def compute_cover(attacker_pos: Tuple[int, int],
                  target_pos: Tuple[int, int],
                  attacker_uuid: UUID,
                  target_uuid: UUID) -> CoverType:
    """Compute best cover between attacker and target using Bresenham raycast."""
    grid = get_map()
    cells = bresenham_line(attacker_pos, target_pos)
    best_cover = CoverType.NONE

    for cell in cells[1:-1]:  # Exclude endpoints
        # Check tile cover
        tile = grid.get_tile(*cell)
        if tile:
            tile_cover = tile.provides_cover()
            best_cover = max(best_cover, tile_cover)

        # Check object cover
        for obj_uuid in grid.get_objects_at(cell):
            block = BaseBlock.get(obj_uuid)
            if block:
                best_cover = max(best_cover, block.provides_cover())

        # Check entity cover (alive entity = HALF)
        for ent_uuid in grid.get_entities_at(cell):
            if ent_uuid != attacker_uuid and ent_uuid != target_uuid:
                best_cover = max(best_cover, CoverType.HALF)

        if best_cover == CoverType.TOTAL:
            break  # Can't get worse

    return best_cover
```

Uses existing `bresenham_line()` from `geometry.py:49-82`.

### 3d. Cover Modifiers

| Cover | AC Bonus | DEX Save Bonus |
|-------|----------|----------------|
| Half | +2 | +2 |
| Three-Quarters | +5 | +5 |
| Total | Can't target | N/A |

Applied as temporary `NumericalModifier` during attack/save resolution:

**Attack** (`dnd/actions.py` in `attack_consequences()`):
- Compute cover between attacker and target
- If TOTAL: attack auto-fails (can't target)
- If HALF/THREE_QUARTERS: add NumericalModifier to target's `ac_bonus` during resolution
- Clean up modifier after attack resolves

**Saving throws** (`entity.py` in `saving_throw()`):
- For DEX saves with a source position: compute cover, add bonus
- Only applies to saves that have a spatial origin (spell caster position)

### 3e. Cover + Hiding Interaction

Cover from an enemy satisfies the "not clearly visible" requirement for hiding:
- Hide action prerequisites: has cover from at least one enemy, OR in obscured tile, OR invisible
- `is_perceivable_by()` can also check cover: if observer has no clear line to target (TOTAL cover), target is not perceivable

### 3f. Cover + Light Interaction (FUTURE)

When light source system is implemented:
- THREE_QUARTERS cover dims light passing through → LIGHTLY_OBSCURED behind it
- TOTAL cover blocks light → HEAVILY_OBSCURED behind (already via shadowcast blocking)
- HALF cover → no dimming

### 3g. Implementation Steps

1. Add `CoverType` enum to `base_block.py`
2. Add `provides_cover()` to BaseBlock (default NONE)
3. Override in Tile (default NONE), Entity (HALF for alive entities)
4. Add `provides_cover_type: CoverType` field to BaseItem
5. Add `compute_cover()` utility using `bresenham_line()`
6. Integrate into `Attack.attack_consequences()` (AC bonus)
7. Integrate into `Entity.saving_throw()` (DEX save bonus, requires source position)

**Files**: `dnd/core/base_block.py`, `dnd/core/base_tiles.py`, `dnd/blocks/base_item.py`, `dnd/core/geometry.py`, `dnd/actions.py`, `dnd/entity.py`
**Tests**: `examples/test_cover_system.py`

---

## D&D 5e SRD Rules Reference

### Obscurement

| Light Level | Obscurement | Effect |
|-------------|-------------|--------|
| Bright Light | None | Normal vision |
| Dim Light | Lightly Obscured | Disadvantage on Perception (sight) |
| Darkness | Heavily Obscured | Effectively Blinded |

- **Lightly Obscured**: Disadvantage on Perception checks relying on sight
- **Heavily Obscured**: Blocks vision entirely — creature effectively has Blinded condition for seeing into area

### Special Senses

| Sense | Bypasses | Limitation |
|-------|----------|------------|
| Darkvision | Darkness → dim, dim → bright | Still disadvantage in former darkness |
| Blindsight | All visual obscurement | Specific radius only |
| Tremorsense | All visual obscurement | Must share ground, can't detect flying |
| Truesight | Everything (darkness, magical, invisibility, illusions) | Specific radius |

### Hiding

- Requires: not clearly visible (obscurement, cover, or invisible)
- Stealth check vs passive Perception (or active Perception check)
- Attacking (hit or miss) reveals location
- Unseen attacker: advantage on attacks
- Invisible creatures can always try to hide

### Cover

| Type | AC Bonus | DEX Save Bonus | Notes |
|------|----------|----------------|-------|
| Half | +2 | +2 | Low wall, creature, tree trunk |
| Three-Quarters | +5 | +5 | Portcullis, arrow slit |
| Total | Can't target | N/A | Full wall, fully concealed |

- Another creature provides half cover
- Only highest cover applies (don't stack)

### Invisibility

- Impossible to see without magic/special sense
- For hiding: treated as heavily obscured
- Attack rolls against: disadvantage
- Invisible creature's attacks: advantage
- Can always try to hide

---

## Verification Checklist

- [ ] No new import paths (only extensions of existing imports from same modules)
- [ ] Perception pattern mirrors Dijkstra pattern (BaseBlock polymorphism → GridMap dispatch → Entity passes UUID)
- [ ] GridMap stays type-unaware (only uses `BaseBlock.get()`)
- [ ] Each layer independently testable and doesn't break previous layers
- [ ] Entity.is_perceivable_by() handles: Invisible, Hidden, Obscurement (layered)
- [ ] Cover computed at attack/save time (not cached in senses)
- [ ] Armor.stealth_disadvantage wired to actual modifier
- [ ] Hidden reveals on attack via EventHandler
- [ ] update_all_entities_senses() called after Invisible/Hidden state changes
