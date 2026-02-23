# Vision, Hiding & Cover — Layered Design

Three systems, each building on the previous. Same polymorphic pattern as Dijkstra/walking.

```
Layer 1: Stealth      Pure LOS + stealth vs perception. No light.     [DONE]
Layer 2: Light         Per-tile light levels. Entity visibility filtering. [DONE]
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
Entity.compute_senses_from_position(entity_uuid)       <- filters entities/objects via is_perceivable_by()  entity.py:1674-1691
Entity.update_entity_visibility()                       <- filters entities/objects via is_perceivable_by()  entity.py:1774-1789
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
| `Entity.compute_senses_from_position()` | `entity.py:1561-1691` | FOV + paths + entity/object collection (now filtered) |
| `Entity.update_entity_visibility()` | `entity.py:1751-1830` | FOV-only during movement (now filtered, + newly-spotted detection) |
| `Entity.passive_skill(skill)` | `entity.py` | Returns `10 + skill bonus + advantage mod` |
| `EventType.CAST_SPELL` | `events.py:135` | Used by Hidden/Invisible reveal handlers |
| `EventType.BASE_ACTION` | `events.py:124` | Used by Hidden/Invisible reveal handlers (non-whitelisted actions) |
| `Invisible.can_see_invisible()` | `conditions.py:522` | Checks TRUESIGHT + TREMORSENSE (BLINDSIGHT handled by senses filtering) |
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
- `SpatialChangeEvent.perceivability_changed()` factory — events.py:1642-1650

```python
# events.py:1642-1650
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

**Observer overrides** (entity.py:685-693):
```python
def get_passive_perception(self) -> int:
    return self.passive_skill("perception")

def can_bypass_invisibility(self) -> bool:
    return (SensesType.TRUESIGHT in self.senses.extra_senses or
            SensesType.BLINDSIGHT in self.senses.extra_senses or
            SensesType.TREMORSENSE in self.senses.extra_senses)
```

**Perception filter in `compute_senses_from_position()`** (entity.py:1674-1691):
```python
# Entities (entity.py:1674-1682)
visible_entities: Dict[UUID, Tuple[int, int]] = {}
for pos in visible_positions:
    entities = Entity.get_all_entities_at_position(pos)
    for entity in entities:
        if entity_uuid and entity.uuid == entity_uuid:
            continue
        if entity.is_perceivable_by(entity_uuid):
            visible_entities[entity.uuid] = pos

# Objects (entity.py:1684-1691)
visible_objects: Dict[UUID, Tuple[int, int]] = {}
for pos in visible_positions:
    for obj_uuid in grid.get_objects_at(pos):
        obj = BaseBlock.get(obj_uuid)
        if obj and not obj.is_perceivable_by(entity_uuid):
            continue
        visible_objects[obj_uuid] = pos
```

**Perception filter in `update_entity_visibility()`** (entity.py:1774-1789):
Same pattern using `block.is_perceivable_by(self.uuid)` for both entities and objects.

Senses are now always subjective — each entity gets a different `senses.entities` dict based on their own perception.

### 1d. Invisible Condition Changes

**`Invisible._apply()`** (conditions.py:492-512):
- Calls `target_entity.set_invisible(True)` (line 498) — sets flag + fires perceivability event
- Uses shared `unseen_attacker_advantage()` callable for self_contextual attack advantage
- Uses shared `unseen_target_disadvantage()` callable for to_target_contextual AC disadvantage

**`Invisible._remove()`** (conditions.py:514-519):
- Calls `target.set_invisible(False)` (line 515) — clears flag + fires perceivability event
- Uses `BaseBlock.get()` (not Entity.get()) since we only need `set_invisible()`

**`can_see_invisible()`** (conditions.py:522):
- Kept as-is: checks TRUESIGHT + TREMORSENSE
- BLINDSIGHT not added here because senses filtering via `can_bypass_invisibility()` handles it. The `can_see_invisible()` method may still be used elsewhere for non-senses checks.

**Shared advantage functions** (conditions.py:527-544):
```python
# conditions.py:527-533
def unseen_attacker_advantage(source_entity_uuid, target_entity_uuid=None, context=None):
    """Advantage if attacker is NOT in target's senses. Used by both Hidden and Invisible."""
    if target_entity_uuid:
        target_entity = Entity.get(target_entity_uuid)
        if isinstance(target_entity, Entity) and source_entity_uuid not in target_entity.senses.entities:
            return AdvantageModifier(name="Unseen Attacker", value=AdvantageStatus.ADVANTAGE, ...)
    return None

# conditions.py:536-544
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

New in `dnd/conditions.py:1150-1231`.

```python
# conditions.py:1150-1163
class Hidden(BaseCondition):
    name: str = "Hidden"
    description: str = "Hidden from observers via Stealth"
    stealth_result: int = Field(default=0, description="Stealth check result used as perception DC")
    creation_lineage_uuid: Optional[UUID] = Field(default=None, description="Lineage UUID of the event that created this condition")
```

**`_apply()`** (conditions.py:1166-1222):
1. Sets flag: `target_entity.set_stealth_dc(self.stealth_result)` (line 1178) — fires perceivability event
2. Adds Unseen Attacker advantage via shared `unseen_attacker_advantage` callable on `attack_bonus.self_contextual` (lines 1181-1189)
3. Registers reveal handler with 5 triggers (lines 1198-1216):
   - `EventType.ATTACK` at EFFECT phase (self as source) — attacking reveals
   - `EventType.TAKE_DAMAGE` at EFFECT phase (self as target) — taking damage reveals
   - `EventType.CONDITION_APPLICATION` at EFFECT phase (self as target) — becoming Incapacitated reveals
   - `EventType.CAST_SPELL` at EFFECT phase (self as source) — casting a spell reveals
   - `EventType.BASE_ACTION` at EFFECT phase (self as source) — non-whitelisted actions reveal

**`_remove()`** (conditions.py:1226-1231):
- Calls `target.set_stealth_dc(None)` (line 1230) — clears flag + fires perceivability event
- Uses `BaseBlock.get()` (not Entity.get())

**`hidden_reveal_processor()`** (conditions.py:1238-1264):
- Checks `creation_lineage_uuid` to avoid self-triggering (the Hide action applying Hidden doesn't immediately reveal)
- For CONDITION_APPLICATION: only breaks on Incapacitated (other conditions don't reveal)
- For BASE_ACTION: checks against `NON_REVEALING_ACTIONS` set — Dash, Dodge, Disengage, Hide, Stand Up, Drop Prone don't reveal
- For CAST_SPELL: always reveals
- Calls `entity.remove_condition("Hidden", parent_event=event)` — threads parent_event for combat log hierarchy

**ConditionType.HIDDEN** added at conditions.py:1558.

**Detection is per-observer, removal is global:**
- `is_perceivable_by()` is checked per-observer (Entity A with perception 15 sees you, Entity B with perception 8 doesn't) — this is just senses filtering, not removal
- Hidden condition removal (attack/damage/condition received) removes it for everyone
- Passive perception only — no Search action for now

### 1e-bis. NON_REVEALING_ACTIONS

Defined at `conditions.py:1235`:
```python
NON_REVEALING_ACTIONS = {"Dash", "Dodge", "Disengage", "Hide", "Stand Up", "Drop Prone"}
```

Used by all three reveal processors (`hidden_reveal_processor`, `invisibility_reveal_processor`, `greater_invisibility_check_processor`) to whitelist safe actions that don't break stealth/invisibility when triggered via `EventType.BASE_ACTION`.

### 1e-ter. InvisibilityEffect (Spell-Based Invisibility)

New in `dnd/conditions.py:1267-1346`. Spell-based variant of Invisible that auto-removes on action.

```python
# conditions.py:1267-1280
class InvisibilityEffect(BaseCondition):
    name: str = "Invisible"  # Same name as base Invisible — overloaded condition name
    description: str = "Invisible (spell effect) - ends on attack or spell cast"
    creation_lineage_uuid: Optional[UUID] = Field(default=None)
```

**Key differences from basic `Invisible`:**
- Has `creation_lineage_uuid` field to avoid self-triggering
- Registers EventHandler with 3 triggers (conditions.py:1324-1331):
  - `EventType.ATTACK` at EFFECT phase (self as source) — attacking reveals
  - `EventType.CAST_SPELL` at EFFECT phase (self as source) — casting a spell reveals
  - `EventType.BASE_ACTION` at EFFECT phase (self as source) — non-whitelisted actions reveal
- **NO `TAKE_DAMAGE` trigger** (unlike Hidden) — taking damage does NOT break spell invisibility
- **NO `CONDITION_APPLICATION` trigger** — becoming incapacitated doesn't break it either
- Uses `invisibility_reveal_processor` (conditions.py:1349-1370)
- Same `name: str = "Invisible"` — uses overloaded condition name so `remove_condition("Invisible")` removes it

**`invisibility_reveal_processor()`** (conditions.py:1349-1370):
- Checks `creation_lineage_uuid` to avoid self-triggering
- For BASE_ACTION: checks against `NON_REVEALING_ACTIONS` set
- Calls `entity.remove_condition("Invisible", parent_event=event)`

### 1e-quater. GreaterInvisibilityEffect (BG3-Style)

New in `dnd/conditions.py:1373-1455`. BG3-style invisibility that rolls Stealth check to maintain.

```python
# conditions.py:1373-1392
class GreaterInvisibilityEffect(BaseCondition):
    name: str = "Invisible"  # Same overloaded name
    description: str = "Greater Invisibility (BG3-style) - Stealth check to maintain on action"
    creation_lineage_uuid: Optional[UUID] = Field(default=None)
    check_count: int = Field(default=0, description="Number of successful Stealth checks")
    base_dc: int = Field(default=15, description="Base DC for Stealth check")
```

**Key features:**
- Instead of auto-removing on action, rolls Stealth check vs escalating DC
- DC = `base_dc + check_count` (escalates by 1 per successful check)
- Same 3 triggers as InvisibilityEffect (ATTACK, CAST_SPELL, BASE_ACTION) at conditions.py:1433-1440
- Uses `greater_invisibility_check_processor` (conditions.py:1458-1527)
- On success: `check_count += 1`, stays invisible
- On failure: removes "Invisible" condition
- Generates its own combat log entry with stealth check roll display

**`greater_invisibility_check_processor()`** (conditions.py:1458-1527):
- Same `creation_lineage_uuid` and `NON_REVEALING_ACTIONS` checks
- Rolls Stealth skill check vs current DC
- On success: increments `check_count`, invisible persists
- On failure: calls `entity.remove_condition("Invisible", parent_event=event)`

**Three Invisible variants summary:**

| Variant | Class | Trigger | Behavior |
|---------|-------|---------|----------|
| `Invisible` | Basic permanent | None | Must be manually removed |
| `InvisibilityEffect` | Spell, auto-remove | ATTACK, CAST_SPELL, BASE_ACTION | Auto-removed on action |
| `GreaterInvisibilityEffect` | Spell, Stealth check | ATTACK, CAST_SPELL, BASE_ACTION | Rolls Stealth vs DC to maintain |

All three share `name="Invisible"` and use the same BaseBlock `is_invisible` flag.

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

### 1h. "Newly Spotted" and "Hazard Detected" Combat Logs

`ENTITY_SPOTTED` logs are generated from three code paths:

1. **Movement** — `update_entity_visibility()` (entity.py:1906-1934) compares old vs new `senses.entities` during step-by-step movement. Fires when moving entity's passive perception exceeds a hidden entity's stealth DC.

2. **Light changes** — `SpatialSensesCallback._refilter_entities_at()` (sensory.py) generates logs when light changes (torch movement, light spell, light toggle) reveal a hidden entity that the observer can perceive.

3. **Observer perception changes** — `SpatialSensesCallback._refilter_all_visible_entities()` (sensory.py) generates logs when conditions on the observer change their perception capabilities (WIS buff, Darkvision gained, etc.) and previously invisible hidden enemies become detectable.

`HAZARD_DETECTED` logs are generated when perception changes reveal hidden tile hazards:
- `SpatialSensesCallback._log_newly_detected_hazards()` — compares old vs new passive perception against `condition_stealth_dc` on tile conditions.

Both use `EventQueue.push_combat_log()` for standalone delivery. Entry types: `CombatLogEntryType.ENTITY_SPOTTED` with `EntitySpottedLogData`, `CombatLogEntryType.HAZARD_DETECTED` with `HazardDetectedLogData`.

### 1h-2. Observer Perception Change Detection

When conditions are added/removed on an entity, the `SpatialSensesCallback` detects changes to perception capabilities via snapshot comparison:

- `Senses._last_passive_perception` / `_last_sense_modes_hash` — snapshots stored after each `update_entity_senses()`
- `_handle_own_perception_change()` fires on `CONDITION_APPLICATION`/`CONDITION_REMOVAL` at COMPLETION phase when `target_entity_uuid == self.owner_uuid`
- **Sense modes changed** (Darkvision, Truesight gained/lost) → full visibility recompute
- **Passive perception changed** → `_refilter_all_visible_entities()` (lighter, re-checks visible area only)
- Both paths set `_paths_dirty = True` (safe paths may change with perception)

**Tests**: `examples/test_perception_staleness.py` (37 tests), `examples/test_lighting_stealth_integration.py` Section 8 (light-driven stealth detection logs)

### 1h-3. `condition_stealth_dc` on BaseCondition

Separate from `stealth_dc` on BaseBlock (which is for entity/item perceivability), `condition_stealth_dc` on BaseCondition gates **hazard detection** at the condition level. Used by hidden traps and zone spells. When set, the observer's passive perception must be ≥ the DC to detect the hazard for safe pathfinding. See `claude_docs/TERRAIN_MOVEMENT_SYSTEM.md` for hazard system details.

### 1i. Tests

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

### 1j. Files Modified

| File | Changes |
|------|---------|
| `dnd/core/events.py` | +EventType, +SpatialChangeType, +factory method |
| `dnd/blocks/sensory.py` | +SPATIAL_EVENTS entry, +self-perceivability early return |
| `dnd/core/base_block.py` | +fields, +setter methods, +observer queries, +is_perceivable_by() |
| `dnd/entity.py` | +SensesType import, +overrides, +perception filter in senses methods |
| `dnd/conditions.py` | +Field/BaseBlock imports, refactored Invisible, +Hidden, +InvisibilityEffect, +GreaterInvisibilityEffect, +NON_REVEALING_ACTIONS, +shared functions, +reveal processors |
| `dnd/actions.py` | +Hidden import, +Hide action class |
| `dnd/actions_functional.py` | +Hide import, +registration |
| `dnd/items/armors.py` | +StealthDisadvantageBodyArmor, +imports, updated 7 factories |
| `examples/test_stealth_system.py` | New: 44 tests |
| `examples/test_lighting_stealth_integration.py` | New: 98 tests (light+stealth cross-cutting, light-driven combat logs) |
| `examples/test_perception_staleness.py` | New: 37 tests (observer perception change detection) |

### 1k. Design Decisions (Divergences from Original Plan)

| Original Plan | Actual Implementation | Reason |
|---------------|----------------------|--------|
| `is_perceivable_by(passive_perception, extra_senses)` | `is_perceivable_by(requesting_entity_uuid)` | Matches `blocks_walking(requesting_entity_uuid)` pattern. Observer data via polymorphic overrides, not params |
| `Entity.update_all_entities_senses()` after state changes | `SPATIAL_PERCEIVABILITY_CHANGED` event via EventQueue | More efficient: only observers subscribed to affected cell recompute, not all entities |
| `_stealth_dc`, `_is_invisible` (private) | `stealth_dc`, `is_invisible` (public, `exclude=True`) | Pydantic field pattern, accessed via setter methods |
| `Invisible` checks `can_see_invisible()` for advantage | Senses-based: `source not in target.senses.entities` | Automatically handles all bypass senses since senses are already filtered |
| `Armor._on_equip()` in equipment.py | `StealthDisadvantageBodyArmor` subclass in armors.py | equipment.py can't import Entity (dependency direction). No hasattr hacks |
| `Dice.roll()` static call for stealth roll | `entity.roll_d20(skill_bonus, RollType.CHECK)` | `Dice.roll` is a cached_property, not static. `roll_d20` properly fires D20RollResultEvent |

---

## Layer 2: Light / Obscurement — DONE

Fully implemented. See `claude_docs/LIGHTING_SYSTEM.md` for complete documentation.

**What was built** (different from original plan above — implemented as a per-tile lighting system instead of ObscurementLevel enum):

- **LightLevel enum**: MAGICAL_DARKNESS (0) → DARKNESS (1) → DIM_LIGHT (2) → BRIGHT_LIGHT (3) → VERY_BRIGHT (4)
- **Tile light storage**: Two modifier dicts (`_illuminations`, `_obscurements`) + resolution logic (MAX illuminations, MIN obscurements)
- **Observer-subjective light**: `Tile.get_effective_light_for(observer_uuid)` — applies Darkvision, Truesight, Devil's Sight, Blindsight, adjacent rule
- **Magical darkness blocks FOV**: `blocks_vision()` checks MAGICAL_DARKNESS, threaded through GridMap/Shadowcast
- **Light sources on GridMap**: `add_light_source()`, `remove_light_source()`, `move_light_source()` (delta-based), `toggle_light_source()`, anchored light movement
- **Zone spell light**: `ZoneControlCondition` has `sets_light_level` + `light_is_obscurement` fields. Fog Cloud (DARKNESS), Darkness spell (MAGICAL_DARKNESS), Daylight (VERY_BRIGHT)
- **Torch item**: UsableItem with Ignite/Extinguish actions, auto-extinguish on drop
- **Stealth interactions**: Hide fails in VERY_BRIGHT, Hidden auto-revealed when entering VERY_BRIGHT
- **Incremental senses updates**: SensesUpdateHint-based system — 40-257x faster than original full-recompute approach

**77 tests** in `examples/test_lighting_system.py`, 130 stealth tests pass (no regressions).

### Original Plan Below (Kept for Reference)

The original plan proposed `ObscurementLevel` enum approach. The actual implementation uses `LightLevel` enum with per-tile illumination/obscurement modifier stacks, which is more flexible and supports dynamic light sources.

<details>
<summary>Original Layer 2 plan (superseded)</summary>

#### 2a. ObscurementLevel Enum

```python
class ObscurementLevel(str, Enum):
    NONE = "none"
    LIGHTLY_OBSCURED = "light"
    HEAVILY_OBSCURED = "heavy"
```

#### 2b-2i. (See LIGHTING_SYSTEM.md for actual implementation)

The original plan envisioned static obscurement on tiles set by zone spells. The actual implementation uses a full dynamic lighting system with light sources, anchored movement, batch events, and incremental senses updates.

</details>

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
- [x] Hidden reveals on attack/damage/incapacitated/spell/action via EventHandler (conditions.py:1198-1216)
- [x] SPATIAL_PERCEIVABILITY_CHANGED event triggers senses re-evaluation (not update_all_entities_senses)
- [x] 44 tests passing (examples/test_stealth_system.py)

### Layer 2 (Light/Obscurement) — DONE
- [x] Each layer independently testable and doesn't break previous layers (77 lighting tests + 130 stealth tests)
- [x] Entity visibility filtered by light level via `Tile.get_effective_light_for()` in senses pipeline
- [x] SensesUpdateHint incremental system: 40-257x performance improvement over full recompute
- [x] See `claude_docs/LIGHTING_SYSTEM.md` for full documentation

### Layer 3 (Cover)
- [ ] Cover computed at attack/save time (not cached in senses)
