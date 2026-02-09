# Vision, Hiding & Cover — Layered Design

Three systems, each building on the previous. Same polymorphic pattern as Dijkstra/walking.

```
Layer 1: Stealth      Pure LOS + stealth vs perception. No light.     [DONE]
Layer 2: Light         Per-tile obscurement. Extends stealth detection.
Layer 3: Cover         Raycast partial cover. AC/DEX save mods. Cover enables hiding.
```

---

## Architecture: Same Pattern as Dijkstra

Walking uses this pipeline:
```
BaseBlock.blocks_walking(requesting_uuid)        <- polymorphic, base_block.py:328
GridMap.is_walkable_for(x, y, requesting_uuid)    <- calls BaseBlock.get(uuid).blocks_walking()  gridmap.py:272
Entity.compute_senses_from_position(entity_uuid)  <- grid.compute_paths(entity_uuid)  entity.py:1561
```

Perception pipeline, same shape:
```
BaseBlock.is_perceivable_by(requesting_entity_uuid)   <- polymorphic, base_block.py:388-407
Entity.compute_senses_from_position(entity_uuid)       <- filters entities/objects via is_perceivable_by()  entity.py:1607-1624
Entity.update_entity_visibility()                       <- filters entities/objects via is_perceivable_by()  entity.py:1707-1723
```

**No GridMap changes needed.** The perception filter is applied directly in Entity's senses methods, not in GridMap. GridMap stays type-unaware.

**Import paths (no new modules, only extensions of existing imports):**

```
base_block.py  <- add SpatialChangeEvent, EventPhase imports from events.py (already imported)
               <- add stealth_dc, is_invisible fields + perceivability methods
sensory.py     <- add SPATIAL_PERCEIVABILITY_CHANGED to SPATIAL_EVENTS tuple
entity.py      <- extend 'from sensory import Senses' to include SensesType
               <- add get_passive_perception(), can_bypass_invisibility() overrides
conditions.py  <- add BaseBlock import (for _remove() hooks)
               <- add Field import from pydantic
armors.py      <- add Entity, AdvantageModifier, AdvantageStatus imports
               <- add StealthDisadvantageBodyArmor subclass
```

---

## Existing Infrastructure

| Component | File : Line | Status |
|-----------|-------------|--------|
| `SensesType` enum (BLINDSIGHT, DARKVISION, TREMORSENSE, TRUESIGHT) | `sensory.py:15-19` | Used by `can_bypass_invisibility()` |
| `Senses.extra_senses: List[SensesType]` | `sensory.py:27` | Used by Entity.can_bypass_invisibility() |
| `BaseBlock.blocks_walking(requesting_uuid)` | `base_block.py:328-332` | Polymorphic, default False |
| `BaseBlock.blocks_vision(requesting_uuid)` | `base_block.py:334-337` | Polymorphic, default False |
| `Tile.blocks_vision()` | `base_tiles.py:105-107` | Returns `not self.visible` |
| `GridMap.is_blocking(x, y)` | `gridmap.py:305-315` | Checks tile + objects for LOS |
| `GridMap.get_visible_entities(origin, max_dist)` | `gridmap.py:615-625` | FOV -> entity dict, no filtering |
| `GridMap.is_walkable_for(x, y, uuid)` | `gridmap.py:272-298` | Entity + object occupancy check |
| `Entity.compute_senses_from_position()` | `entity.py:1561-1624` | FOV + paths + entity/object collection (now filtered) |
| `Entity.update_entity_visibility()` | `entity.py:1668-1723` | FOV-only during movement (now filtered) |
| `Entity.passive_skill(skill)` | `entity.py` | Returns `10 + skill bonus + advantage mod` |
| `Invisible.can_see_invisible()` | `conditions.py:518-521` | Checks TRUESIGHT + TREMORSENSE (BLINDSIGHT handled by senses filtering) |
| `Armor.stealth_disadvantage: Optional[bool]` | `equipment.py:135-138` | **DONE** — wired via `StealthDisadvantageBodyArmor` in armors.py |
| `bresenham_line(start, end)` | `geometry.py:49-82` | Returns `List[Tuple[int,int]]` |

**Key gaps (Layer 1 status):**
- ~~Invisible condition adds attack advantage/disadvantage but is not connected to senses~~ **FIXED** — `set_invisible(True)` sets flag, senses filter via `is_perceivable_by()`
- Tile has binary `visible` flag (wall/not wall) — no obscurement gradations (Layer 2)
- ~~`Armor.stealth_disadvantage` exists but is never wired to a modifier~~ **FIXED** — `StealthDisadvantageBodyArmor` subclass in `armors.py:12-39`

---

## Layer 1: Stealth (no light) — DONE

Pure LOS + senses range. If entity is in your FOV, you see them — UNLESS they have stealth/invisibility flags set.

### Design Principle: Flags on BaseBlock, Not Condition Knowledge

The perceivability system uses **condition-agnostic flags** on BaseBlock. Conditions (Hidden, Invisible, or future effects) set/unset these flags via setter methods. The perception pipeline reads them without knowing what set them. This means items can also be hidden/invisible (a trap with `stealth_dc=15`, an invisible chest).

```
Condition layer (conditions.py)          BaseBlock flags (base_block.py)
+----------------------+                +-------------------------+
| Hidden._apply()      |---sets------->| stealth_dc: int = 15    |
| Hidden._remove()     |---unsets----->| stealth_dc: None        |
| Invisible._apply()   |---sets------->| is_invisible: True      |
| Invisible._remove()  |---unsets----->| is_invisible: False     |
| (future conditions)  |---sets------->| (same flags)            |
+----------------------+                +-------------------------+
         via set_stealth_dc()                      |
         via set_invisible()                       v read by
         (fire PERCEIVABILITY_CHANGED)  +-------------------------+
                                        | is_perceivable_by(      |
                                        |   requesting_entity_uuid|
                                        | )                       |
                                        +-------------------------+
                                                   |
                                                   v delegates to
                                        observer.get_passive_perception()
                                        observer.can_bypass_invisibility()
```

**Key design choice**: `is_perceivable_by()` takes `requesting_entity_uuid` (not `passive_perception, extra_senses` params). This matches the `blocks_walking(requesting_entity_uuid)` pattern. Observer data is accessed via polymorphic method calls (`get_passive_perception()`, `can_bypass_invisibility()`) that BaseBlock defaults to 0/False, and Entity overrides with real values.

No Entity importing conditions. No conditions importing Entity (conditions import BaseBlock for `_remove()` hooks). Flags are the interface.

### 1a. New Event Type: SPATIAL_PERCEIVABILITY_CHANGED

**Why a new event**: Reusing `SPATIAL_ENTITY_LEFT`/`ENTERED` for hiding would be semantically wrong (entity didn't physically move) and would trigger zone effects (Spike Growth, Web, etc.) via SpatialHandlers. We need a lighter event that only triggers senses re-evaluation.

**`dnd/core/events.py`:**
- `EventType.SPATIAL_PERCEIVABILITY_CHANGED` — events.py:172
- `SpatialChangeType.PERCEIVABILITY_CHANGED` — events.py:193
- `SpatialChangeEvent.perceivability_changed()` factory — events.py:1611-1627

```python
# events.py:1611-1627
@classmethod
def perceivability_changed(cls, position: Tuple[int, int], entity_uuid: UUID,
                           source_entity_uuid: Optional[UUID] = None) -> 'SpatialChangeEvent':
    return cls(
        source_entity_uuid=source_entity_uuid or entity_uuid,
        event_type=EventType.SPATIAL_PERCEIVABILITY_CHANGED,
        change_type=SpatialChangeType.PERCEIVABILITY_CHANGED,
        position=position, entity_uuid=entity_uuid,
        phase=EventPhase.DECLARATION, use_register=False,
    )
```

**`dnd/blocks/sensory.py`:**
- Added to `SpatialSensesCallback.SPATIAL_EVENTS` tuple — sensory.py:161-168
- Self-perceivability early return (entity's own hiding doesn't affect its own senses) — sensory.py:198-201

```python
# sensory.py:198-201
entity_uuid = getattr(event, 'entity_uuid', None)
if entity_uuid == self.owner_uuid and event.event_type == EventType.SPATIAL_PERCEIVABILITY_CHANGED:
    return
```

**Flow**: `set_stealth_dc()`/`set_invisible()` -> `_notify_perceivability_changed()` -> fires `SPATIAL_PERCEIVABILITY_CHANGED` through EventQueue -> `SpatialSensesCallback` on subscribed observers fires `update_senses_func()` -> observers re-run `compute_senses_from_position()` -> `is_perceivable_by()` filter kicks in.

### 1b. BaseBlock Perceivability Fields + Methods

All in `dnd/core/base_block.py`. Import: `SpatialChangeEvent, EventPhase` from events.py (line 7, same import already used).

**Fields** (base_block.py:142-145):
```python
stealth_dc: Optional[int] = Field(default=None, exclude=True,
    description="Stealth DC required to perceive. Set by Hidden condition.")
is_invisible: bool = Field(default=False, exclude=True,
    description="Whether invisible. Set by Invisible condition.")
```

`exclude=True` prevents serialization (runtime state, not persisted).

**Setter methods** that encapsulate flag-setting + event notification:

| Method | Lines | Purpose |
|--------|-------|---------|
| `set_stealth_dc(value)` | 347-350 | Sets `stealth_dc` + fires perceivability event |
| `set_invisible(value)` | 352-355 | Sets `is_invisible` + fires perceivability event |
| `_notify_perceivability_changed()` | 357-376 | Fires `SPATIAL_PERCEIVABILITY_CHANGED` through full event lifecycle |

**Observer query methods** (BaseBlock defaults, Entity overrides):

| Method | Lines | Default | Entity Override |
|--------|-------|---------|-----------------|
| `get_passive_perception()` | 378-381 | Returns 0 | `self.passive_skill("perception")` |
| `can_bypass_invisibility()` | 383-386 | Returns False | Checks TRUESIGHT/BLINDSIGHT/TREMORSENSE |

**Perceivability query** (base_block.py:388-407):
```python
def is_perceivable_by(self, requesting_entity_uuid: Optional[UUID] = None) -> bool:
    if requesting_entity_uuid is None:
        return True
    observer = BaseBlock.get(requesting_entity_uuid)
    if observer is None:
        return True
    if self.is_invisible:
        if not observer.can_bypass_invisibility():
            return False
    if self.stealth_dc is not None:
        if self.stealth_dc > observer.get_passive_perception():
            return False
    return True
```

### 1c. Entity Senses Integration

**Import** (entity.py:25): `from dnd.blocks.sensory import Senses, SensesType`

**Observer overrides** (entity.py:678-686):
```python
def get_passive_perception(self) -> int:
    return self.passive_skill("perception")

def can_bypass_invisibility(self) -> bool:
    return (SensesType.TRUESIGHT in self.senses.extra_senses or
            SensesType.BLINDSIGHT in self.senses.extra_senses or
            SensesType.TREMORSENSE in self.senses.extra_senses)
```

**Perception filter in `compute_senses_from_position()`** (entity.py:1607-1624):
```python
# Entities (entity.py:1607-1615)
visible_entities: Dict[UUID, Tuple[int, int]] = {}
for pos in visible_positions:
    entities = Entity.get_all_entities_at_position(pos)
    for entity in entities:
        if entity_uuid and entity.uuid == entity_uuid:
            continue
        if entity.is_perceivable_by(entity_uuid):
            visible_entities[entity.uuid] = pos

# Objects (entity.py:1617-1624)
visible_objects: Dict[UUID, Tuple[int, int]] = {}
for pos in visible_positions:
    for obj_uuid in grid.get_objects_at(pos):
        obj = BaseBlock.get(obj_uuid)
        if obj and not obj.is_perceivable_by(entity_uuid):
            continue
        visible_objects[obj_uuid] = pos
```

**Perception filter in `update_entity_visibility()`** (entity.py:1707-1723):
Same pattern using `block.is_perceivable_by(self.uuid)` for both entities and objects.

Senses are now always subjective — each entity gets a different `senses.entities` dict based on their own perception.

### 1d. Invisible Condition Changes

**`Invisible._apply()`** (conditions.py:489-509):
- Calls `target_entity.set_invisible(True)` (line 498) — sets flag + fires perceivability event
- Uses shared `unseen_attacker_advantage()` callable for self_contextual attack advantage
- Uses shared `unseen_target_disadvantage()` callable for to_target_contextual AC disadvantage

**`Invisible._remove()`** (conditions.py:511-516):
- Calls `target.set_invisible(False)` (line 515) — clears flag + fires perceivability event
- Uses `BaseBlock.get()` (not Entity.get()) since we only need `set_invisible()`

**`can_see_invisible()`** (conditions.py:518-521):
- Kept as-is: checks TRUESIGHT + TREMORSENSE
- BLINDSIGHT not added here because senses filtering via `can_bypass_invisibility()` handles it. The `can_see_invisible()` method may still be used elsewhere for non-senses checks.

**Shared advantage functions** (conditions.py:524-541):
```python
# conditions.py:524-530
def unseen_attacker_advantage(source_entity_uuid, target_entity_uuid=None, context=None):
    """Advantage if attacker is NOT in target's senses. Used by both Hidden and Invisible."""
    if target_entity_uuid:
        target_entity = Entity.get(target_entity_uuid)
        if isinstance(target_entity, Entity) and source_entity_uuid not in target_entity.senses.entities:
            return AdvantageModifier(name="Unseen Attacker", value=AdvantageStatus.ADVANTAGE, ...)
    return None

# conditions.py:533-541
def unseen_target_disadvantage(source_entity_uuid, target_entity_uuid=None, context=None):
    """Disadvantage for attacker if defender is NOT in attacker's senses."""
    if target_entity_uuid:
        attacker = Entity.get(target_entity_uuid)
        if isinstance(attacker, Entity) and source_entity_uuid not in attacker.senses.entities:
            return AdvantageModifier(name="Unseen Target", value=AdvantageStatus.DISADVANTAGE, ...)
    return None
```

**Key insight**: These check `source_entity_uuid not in target.senses.entities`. Since `senses.entities` is already filtered by `is_perceivable_by()`, this naturally handles ALL bypass senses (TRUESIGHT, BLINDSIGHT, TREMORSENSE) — no special-case logic needed.

### 1e. Hidden Condition

New in `dnd/conditions.py:1145-1230`.

```python
# conditions.py:1145-1158
class Hidden(BaseCondition):
    name: str = "Hidden"
    description: str = "Hidden from observers via Stealth"
    stealth_result: int = Field(default=0, description="Stealth check result used as perception DC")
```

**`_apply()`** (conditions.py:1160-1209):
1. Sets flag: `target_entity.set_stealth_dc(self.stealth_result)` (line 1171) — fires perceivability event
2. Adds Unseen Attacker advantage via shared `unseen_attacker_advantage` callable on `attack_bonus.self_contextual` (lines 1174-1182)
3. Registers reveal handler with 3 triggers (lines 1191-1205):
   - `EventType.ATTACK` at EFFECT phase (self as source)
   - `EventType.TAKE_DAMAGE` at EFFECT phase (self as target)
   - `EventType.CONDITION_APPLICATION` at EFFECT phase (self as target)

**`_remove()`** (conditions.py:1211-1216):
- Calls `target.set_stealth_dc(None)` (line 1215) — clears flag + fires perceivability event
- Uses `BaseBlock.get()` (not Entity.get())

**`hidden_reveal_processor()`** (conditions.py:1219-1230):
- For CONDITION_APPLICATION: only breaks on Incapacitated (other conditions don't reveal)
- Calls `entity.remove_condition("Hidden")`

**ConditionType.HIDDEN** added at conditions.py:1244.

**Detection is per-observer, removal is global:**
- `is_perceivable_by()` is checked per-observer (Entity A with perception 15 sees you, Entity B with perception 8 doesn't) — this is just senses filtering, not removal
- Hidden condition removal (attack/damage/condition received) removes it for everyone
- Passive perception only — no Search action for now

### 1f. Hide Action

New in `dnd/actions.py:1288-1356`.

- Cost: 1 action
- Target: SELF
- Uses `entity.roll_d20(skill_bonus, RollType.CHECK, skill_name="stealth")` for proper dice event firing
- Applies Hidden condition with `stealth_result` = roll total (d20 + stealth bonus + advantage)
- No duration — removed by triggers (attack/damage/incapacitated)

Registered in `setup_standard_actions()` at `actions_functional.py:61`:
```python
entity.register_action(Hide(source_entity_uuid=entity.uuid, template=True))
```

### 1g. Armor Stealth Disadvantage

Implemented via `StealthDisadvantageBodyArmor` subclass in `dnd/items/armors.py:12-39`.

**Design choice**: The original plan proposed hooks on `Armor._on_equip()` in equipment.py, but equipment.py cannot import Entity (dependency direction: Entity -> Equipment, not reverse). Using `hasattr()` was rejected. Instead, a proper subclass in armors.py where Entity is available.

```python
# armors.py:12-39
class StealthDisadvantageBodyArmor(BodyArmor):
    """BodyArmor subclass that applies stealth disadvantage on equip."""
    _stealth_mod_uuid: Optional[UUID] = None
    _stealth_mod_value_uuid: Optional[UUID] = None

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if entity and isinstance(entity, Entity):
            self._stealth_mod_uuid = entity.skill_set.stealth.skill_bonus.self_static.add_advantage_modifier(
                AdvantageModifier(name=f"{self.name} Stealth Disadvantage",
                                  value=AdvantageStatus.DISADVANTAGE,
                                  source_entity_uuid=entity_uuid))
            self._stealth_mod_value_uuid = entity.skill_set.stealth.skill_bonus.uuid

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        if self._stealth_mod_uuid:
            entity = Entity.get(entity_uuid)
            if entity and isinstance(entity, Entity):
                entity.skill_set.stealth.skill_bonus.self_static.remove_modifier(self._stealth_mod_uuid)
            self._stealth_mod_uuid = None
            self._stealth_mod_value_uuid = None
```

**7 armor factories** use `StealthDisadvantageBodyArmor`: padded (L46), scale mail (L116), half plate (L143), ring mail (L161), chain mail (L175), splint (L190), plate (L205).

### 1h. Tests

All in `examples/test_stealth_system.py` — 44 tests, all passing.

| Test | Checks |
|------|--------|
| `test_baseblock_perceivability_defaults` | 4: default values, always perceivable |
| `test_invisible_flag` | 6: invisible blocks perception, TRUESIGHT/BLINDSIGHT/TREMORSENSE bypass |
| `test_stealth_dc_flag` | 3: stealth DC vs passive perception thresholds |
| `test_senses_filtering_hidden` | 3: hidden entity filtered from observer senses |
| `test_invisible_condition_senses` | 7: Invisible condition apply/remove cycle, TRUESIGHT bypass |
| `test_hidden_condition` | 4: Hidden apply, unseen attacker advantage, removal on attack |
| `test_hidden_removal_on_damage` | 3: Hidden removed when entity takes damage |
| `test_hidden_removal_on_incapacitated` | 3: Hidden removed when entity becomes incapacitated |
| `test_hide_action` | 4: action available, applies Hidden with stealth roll |
| `test_armor_stealth_disadvantage` | 3: chain mail equip/unequip stealth disadvantage |
| `test_armor_no_stealth_disadvantage` | 1: leather armor has no disadvantage |
| `test_object_perceivability` | 3: BaseItem with stealth_dc filtered from observer senses |

### 1i. Files Modified

| File | Changes |
|------|---------|
| `dnd/core/events.py` | +EventType, +SpatialChangeType, +factory method |
| `dnd/blocks/sensory.py` | +SPATIAL_EVENTS entry, +self-perceivability early return |
| `dnd/core/base_block.py` | +fields, +setter methods, +observer queries, +is_perceivable_by() |
| `dnd/entity.py` | +SensesType import, +overrides, +perception filter in senses methods |
| `dnd/conditions.py` | +Field/BaseBlock imports, refactored Invisible, +Hidden, +shared functions |
| `dnd/actions.py` | +Hidden import, +Hide action class |
| `dnd/actions_functional.py` | +Hide import, +registration |
| `dnd/items/armors.py` | +StealthDisadvantageBodyArmor, +imports, updated 7 factories |
| `examples/test_stealth_system.py` | New: 44 tests |

### 1j. Design Decisions (Divergences from Original Plan)

| Original Plan | Actual Implementation | Reason |
|---------------|----------------------|--------|
| `is_perceivable_by(passive_perception, extra_senses)` | `is_perceivable_by(requesting_entity_uuid)` | Matches `blocks_walking(requesting_entity_uuid)` pattern. Observer data via polymorphic overrides, not params |
| `Entity.update_all_entities_senses()` after state changes | `SPATIAL_PERCEIVABILITY_CHANGED` event via EventQueue | More efficient: only observers subscribed to affected cell recompute, not all entities |
| `_stealth_dc`, `_is_invisible` (private) | `stealth_dc`, `is_invisible` (public, `exclude=True`) | Pydantic field pattern, accessed via setter methods |
| `Invisible` checks `can_see_invisible()` for advantage | Senses-based: `source not in target.senses.entities` | Automatically handles all bypass senses since senses are already filtered |
| `Armor._on_equip()` in equipment.py | `StealthDisadvantageBodyArmor` subclass in armors.py | equipment.py can't import Entity (dependency direction). No hasattr hacks |
| `Dice.roll()` static call for stealth roll | `entity.roll_d20(skill_bonus, RollType.CHECK)` | `Dice.roll` is a cached_property, not static. `roll_d20` properly fires D20RollResultEvent |

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

The `is_perceivable_by()` method on Entity (which overrides BaseBlock's version) would add obscurement awareness. The obscurement check happens between the existing invisible/stealth checks:

```python
# Check tile obscurement at this block's position
tile = get_map().get_tile(*self.position)
if tile:
    effective_obs = self._compute_effective_obscurement(
        tile.obscurement, tile.is_magical_darkness, observer
    )
    if effective_obs == ObscurementLevel.HEAVILY_OBSCURED:
        return False  # Auto-hidden in heavy obscurement
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
5. Override `is_perceivable_by()` on Entity with obscurement logic
6. Add `_compute_effective_obscurement()` helper to Entity
7. Implement Fog Cloud and Darkness spells

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

### 3b. BaseBlock.provides_cover() -> CoverType

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
- THREE_QUARTERS cover dims light passing through -> LIGHTLY_OBSCURED behind it
- TOTAL cover blocks light -> HEAVILY_OBSCURED behind (already via shadowcast blocking)
- HALF cover -> no dimming

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
| Darkvision | Darkness -> dim, dim -> bright | Still disadvantage in former darkness |
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

### Layer 1 (Stealth)
- [x] No new import paths (only extensions of existing imports from same modules)
- [x] Perception pattern mirrors Dijkstra pattern (BaseBlock polymorphism -> Entity passes UUID)
- [x] GridMap stays type-unaware (unchanged — filtering done in Entity senses methods)
- [x] Invisible condition sets `is_invisible` flag via `set_invisible()` + fires perceivability event
- [x] Hidden condition sets `stealth_dc` flag via `set_stealth_dc()` + fires perceivability event
- [x] `is_perceivable_by()` handles both Invisible and Hidden flags
- [x] Senses filtering applied to both entities AND objects in both senses methods
- [x] Armor.stealth_disadvantage wired via StealthDisadvantageBodyArmor subclass (armors.py:12-39)
- [x] Hidden reveals on attack/damage/incapacitated via EventHandler (conditions.py:1191-1205)
- [x] SPATIAL_PERCEIVABILITY_CHANGED event triggers senses re-evaluation (not update_all_entities_senses)
- [x] 44 tests passing (examples/test_stealth_system.py)

### Layer 2 (Light/Obscurement)
- [ ] Each layer independently testable and doesn't break previous layers
- [ ] Entity.is_perceivable_by() handles: Invisible, Hidden, Obscurement (layered)

### Layer 3 (Cover)
- [ ] Cover computed at attack/save time (not cached in senses)
