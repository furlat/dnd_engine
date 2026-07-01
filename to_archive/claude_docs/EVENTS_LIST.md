# Events List

Complete reference for every event type in the codebase. Organized by category with class hierarchy, fields, combat log support, and usage patterns.

---

## Table of Contents

1. [Event Phase Lifecycle](#1-event-phase-lifecycle)
2. [Core Events](#2-core-events)
3. [Equipment Events](#3-equipment-events)
4. [Spatial Events](#4-spatial-events)
5. [Dice Roll Events](#5-dice-roll-events)
6. [Damage and Heal Events](#6-damage-and-heal-events)
7. [Combat Action Events](#7-combat-action-events)
8. [Encounter Lifecycle Events](#8-encounter-lifecycle-events)
9. [Death Event](#9-death-event)
10. [Condition Events](#10-condition-events)
11. [D20 Legacy Events](#11-d20-legacy-events)
12. [Serialization Patterns](#12-serialization-patterns)
13. [EventType Enum Reference](#13-eventtype-enum-reference)

---

## 1. Event Phase Lifecycle

Every event progresses through phases:

```
DECLARATION -> EXECUTION -> EFFECT -> COMPLETION
                                        (or CANCEL at any point)
```

| Phase | Purpose |
|-------|---------|
| `DECLARATION` | Initial creation. Handlers can intercept and cancel before costs are committed. |
| `EXECUTION` | Main action begins. Costs are committed at this point. |
| `EFFECT` | Effects are applied. Last chance for reactions to modify or block. Multiple EFFECT events possible per lineage (e.g., Attack fires EFFECT for damage resolution, then again post-damage). |
| `COMPLETION` | Event is done. **Skips all EventHandlers by design.** Only used for combat log generation via callback. |
| `CANCEL` | Event was canceled. No further processing. |

**CRITICAL**: `EventQueue.register()` returns early for `COMPLETION` phase events (line 748 in events.py) -- no handlers fire. This separates the causal chain (DECLARATION-EFFECT) from observational output (COMPLETION/combat log). If you register a handler on `EventPhase.COMPLETION`, it will **never fire**.

---

## 2. Core Events

### `Event` (Base Class)

**File**: `dnd/core/events.py` (line 214)
**Parent**: `BaseObject`
**EventType**: Varies (set by subclasses)
**Combat Log**: Returns `self.combat_log` (pre-set if any). Subclasses override `generate_combat_log()`.

All events inherit from this class. It provides the phase lifecycle, parent-child tracking, lineage history, and combat log generation.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Name of the event (default: `"Event"`) |
| `lineage_uuid` | `UUID` | Shared across all phase transitions of the same logical event |
| `timestamp` | `datetime` | When the event was created |
| `event_type` | `EventType` | Enum value classifying the event |
| `phase` | `EventPhase` | Current phase (DECLARATION, EXECUTION, EFFECT, COMPLETION, CANCEL) |
| `source_entity_name` | `Optional[str]` | Name of the source entity (for combat log, populated at creation) |
| `target_entity_name` | `Optional[str]` | Name of the target entity (for combat log, populated at creation) |
| `modified` | `bool` | Whether the event was modified by a handler |
| `canceled` | `bool` | Whether the event was canceled |
| `parent_event` | `Optional[UUID]` | UUID of the parent event (for sub-action tracking) |
| `status_message` | `Optional[str]` | Human-readable status message |
| `is_first` | `bool` | True if first event of this phase in this lineage |
| `is_last` | `bool` | True if last event of this phase in this lineage |
| `lineage_children_events` | `List[UUID]` | All children throughout event lifetime |
| `children_events` | `List[UUID]` | Children during current phase |
| `combat_log` | `Optional[CombatLogEntry]` | Auto-generated at COMPLETION (excluded from serialization) |

**Inherited from BaseObject**: `uuid`, `source_entity_uuid`, `target_entity_uuid`, `use_register`

**Key Methods**:
- `phase_to(new_phase, **updates)` -- Create copy at next phase, post through EventQueue
- `cancel(status_message)` -- Mark canceled, post through EventQueue
- `post(**updates)` -- Update and rebroadcast (new UUID, same lineage)
- `get_affected_positions()` -- Override in subclasses for perceiver computation

---

### `ActionEvent` (Base Class for Actions)

**File**: `dnd/core/base_actions.py` (line 72)
**Parent**: `Event`
**EventType**: `BASE_ACTION` (default)
**Combat Log**: Yes -- generates `ACTION` or `MULTI_ENTITY_ACTION` log entries.

Base event for all action-related events. Created by `BaseAction._create_declaration_event()`. Subclassed by `AttackEvent`, `MovementEvent`, `SpellEvent`, `ShoveEvent`, `JumpEvent`.

| Field | Type | Description |
|-------|------|-------------|
| `costs` | `List[BaseCost]` | Costs for the action (action, bonus_action, movement, spell slots, resources) |
| `event_type` | `EventType` | Default `BASE_ACTION` |
| `description` | `str` | Action description for combat log |
| `total_targets` | `int` | Number of targets affected (for multi-target actions) |
| `total_damage` | `int` | Total damage dealt across all targets |
| `aoe_position` | `Optional[Tuple[int, int]]` | Target position for AoE actions |

**Combat Log Behavior**: When `total_targets > 0`, generates `MULTI_ENTITY_ACTION` summary. Otherwise generates `ACTION` log with entity name and action name. Self-targeting actions (Dash, Dodge, Disengage) use this directly.

**Usage**: Created by `Dash`, `Dodge`, `Disengage`, `Hide`, `StandUp`, `DropProne`, `DropConcentration` actions as their declaration event.

---

## 3. Equipment Events

**File**: `dnd/blocks/equipment.py` (lines 17-56)

**IMPORTANT**: These events currently embed full Pydantic objects (`Weapon`, `Armor`, `Shield`) instead of UUIDs. This is a known serialization concern -- `model_dump(mode='json')` will serialize the entire nested object.

### `EquipmentEvent` (Base)

**Parent**: `Event`
**EventType**: Varies by subclass

| Field | Type | Description |
|-------|------|-------------|
| `slot` | `Union[BodyPart, RingSlot, WeaponSlot]` | The equipment slot being affected |

---

### `WeaponEquipEvent`

**Parent**: `EquipmentEvent`
**EventType**: `WEAPON_EQUIP`
**Combat Log**: No

| Field | Type | Description |
|-------|------|-------------|
| `weapon` | `Weapon` | The weapon being equipped (**full object, not UUID**) |

**Fired by**: `Equipment.equip()` when equipping a weapon.

---

### `WeaponUnequipEvent`

**Parent**: `EquipmentEvent`
**EventType**: `WEAPON_UNEQUIP`
**Combat Log**: No

| Field | Type | Description |
|-------|------|-------------|
| `weapon` | `Weapon` | The weapon being unequipped (**full object, not UUID**) |

**Fired by**: `Equipment.unequip()` when removing a weapon, or `Equipment.equip()` when replacing an existing weapon.

---

### `ArmorEquipEvent`

**Parent**: `EquipmentEvent`
**EventType**: `ARMOR_EQUIP`
**Combat Log**: No

| Field | Type | Description |
|-------|------|-------------|
| `armor` | `Armor` | The armor being equipped (**full object, not UUID**) |

**Fired by**: `Equipment.equip()` when equipping armor.

---

### `ArmorUnequipEvent`

**Parent**: `EquipmentEvent`
**EventType**: `ARMOR_UNEQUIP`
**Combat Log**: No

| Field | Type | Description |
|-------|------|-------------|
| `armor` | `Armor` | The armor being unequipped (**full object, not UUID**) |

**Fired by**: `Equipment.unequip()` when removing armor.

---

### `ShieldEquipEvent`

**Parent**: `EquipmentEvent`
**EventType**: `SHIELD_EQUIP`
**Combat Log**: No

| Field | Type | Description |
|-------|------|-------------|
| `shield` | `Shield` | The shield being equipped (**full object, not UUID**) |

**Fired by**: `Equipment.equip()` when equipping a shield.

---

### `ShieldUnequipEvent`

**Parent**: `EquipmentEvent`
**EventType**: `SHIELD_UNEQUIP`
**Combat Log**: No

| Field | Type | Description |
|-------|------|-------------|
| `shield` | `Shield` | The shield being unequipped (**full object, not UUID**) |

**Fired by**: `Equipment.unequip()` when removing a shield.

---

## 4. Spatial Events

### `SensesUpdateHint`

**File**: `dnd/core/events.py` (line 1571)
**Not an Event** -- a data model carried on `SpatialChangeEvent.senses_hint` to tell observers what to update incrementally.

| Field | Type | Description |
|-------|------|-------------|
| `requires_fov` | `bool` | Vision geometry changed (wall, magical darkness, door blocking) |
| `requires_paths` | `bool` | Path topology changed (entity moved, walkability changed) |
| `entity_entered` | `Optional[Tuple[UUID, Tuple[int, int]]]` | Entity UUID and position |
| `entity_left` | `Optional[Tuple[UUID, Tuple[int, int]]]` | Entity UUID and position |
| `light_changed_positions` | `Optional[Set[Tuple[int, int]]]` | Positions where light level changed |
| `perceivability_entity` | `Optional[UUID]` | Entity whose perceivability changed |
| `object_placed` | `Optional[Tuple[UUID, Tuple[int, int]]]` | Object UUID and position |
| `object_removed` | `Optional[Tuple[UUID, Tuple[int, int]]]` | Object UUID and position |
| `entity_died` | `Optional[Tuple[UUID, Tuple[int, int]]]` | Entity UUID and position (stopped blocking) |

---

### `SpatialChangeEvent`

**File**: `dnd/core/events.py` (line 1603)
**Parent**: `Event`
**EventType**: Varies -- one of `SPATIAL_ENTITY_ENTERED`, `SPATIAL_ENTITY_LEFT`, `SPATIAL_TILE_CHANGED`, `SPATIAL_OBJECT_PLACED`, `SPATIAL_OBJECT_REMOVED`, `SPATIAL_PERCEIVABILITY_CHANGED`, `SPATIAL_LIGHT_CHANGED`, `SPATIAL_OBJECT_CHANGED`, `MOVEMENT_COLLISION`
**Combat Log**: No

Fired by `GridMap` when something changes at a grid position. Always created with `use_register=False` and registered via `GridMap._fire_spatial_event()`.

| Field | Type | Description |
|-------|------|-------------|
| `change_type` | `SpatialChangeType` | Specific type of spatial change |
| `position` | `Tuple[int, int]` | Grid position where change occurred |
| `entity_uuid` | `Optional[UUID]` | UUID of entity involved |
| `object_uuid` | `Optional[UUID]` | UUID of object involved |
| `old_position` | `Optional[Tuple[int, int]]` | Previous position (for movement) |
| `tile_walkable` | `Optional[bool]` | New walkable state (for tile changes) |
| `tile_visible` | `Optional[bool]` | New visible state (for tile changes) |
| `senses_hint` | `Optional[SensesUpdateHint]` | Hint for incremental senses updates |

**Factory methods** (each creates a specialized `SpatialChangeEvent`):

| Method | EventType | Usage |
|--------|-----------|-------|
| `entity_entered()` | `SPATIAL_ENTITY_ENTERED` | Entity moved into a cell |
| `entity_left()` | `SPATIAL_ENTITY_LEFT` | Entity left a cell |
| `tile_changed()` | `SPATIAL_TILE_CHANGED` | Tile properties changed (walkable/visible) |
| `object_placed()` | `SPATIAL_OBJECT_PLACED` | Object placed on grid |
| `object_removed()` | `SPATIAL_OBJECT_REMOVED` | Object removed from grid |
| `perceivability_changed()` | `SPATIAL_PERCEIVABILITY_CHANGED` | Entity hidden/invisible state changed |
| `light_changed()` | `SPATIAL_LIGHT_CHANGED` | Tile resolved light level changed |
| `object_changed()` | `SPATIAL_OBJECT_CHANGED` | Object blocking state changed (door open/close) |
| `movement_collision()` | `MOVEMENT_COLLISION` | Entity bumped into imperceivable blocker |

---

### `ForcedMovementEvent`

**File**: `dnd/core/events.py` (line 1875)
**Parent**: `Event`
**EventType**: `FORCED_MOVEMENT`
**Combat Log**: Yes -- generates `MOVEMENT` log entry.

Forced movement (push/pull) that does NOT trigger opportunity attacks. `target_entity_uuid` (inherited from Event) is the entity being pushed.

| Field | Type | Description |
|-------|------|-------------|
| `start_position` | `Tuple[int, int]` | Position before push |
| `end_position` | `Tuple[int, int]` | Position after push |
| `direction` | `Tuple[int, int]` | Push direction as (dx, dy) |
| `intended_distance` | `int` | How far we tried to push (feet) |
| `actual_distance` | `int` | How far they actually moved |
| `blocked_by_obstacle` | `bool` | Stopped by wall/entity |
| `blocked_by` | `Optional[str]` | What blocked the push (e.g., "Wall", "Skeleton 1") |
| `cause` | `str` | What caused this: "shove", "thunderwave", etc. |

**Fired by**: `Shove._apply()`, Thunderwave, repelling effects.

---

### `StepMovementEvent`

**File**: `dnd/core/events.py` (line 1964)
**Parent**: `Event`
**EventType**: `STEP_MOVEMENT`
**Combat Log**: Yes -- generates `MOVEMENT` log entry (usually not logged individually).

Single cell transition within a movement path. Fired for each step during cell-by-cell movement. Opportunity attacks and terrain effects trigger on this event type.

| Field | Type | Description |
|-------|------|-------------|
| `from_position` | `Tuple[int, int]` | Position before this step |
| `to_position` | `Tuple[int, int]` | Position after this step |
| `path_index` | `int` | Index of this step in the overall path |
| `total_path_length` | `int` | Total number of positions in path |
| `movement_cost` | `float` | Movement cost in feet for this step |

**CRITICAL**: Created with `use_register=False`, then `post(use_register=True)` is the single registration point. This prevents double-registration and ensures handler cancellation propagates correctly.

**Fired by**: `Move._apply()` and `Jump._apply()` for each step in the movement path.

---

## 5. Dice Roll Events

### `DiceRollResultEvent` (Base)

**File**: `dnd/core/events.py` (line 2086)
**Parent**: `Event`
**EventType**: `DICE_ROLL_RESULT`
**Combat Log**: No

Base class for all dice roll result events. Provides unified handler interception.

| Field | Type | Description |
|-------|------|-------------|
| `roll_type` | `RollType` | ATTACK, SAVE, CHECK, or DAMAGE |
| `context` | `Dict[str, Any]` | Arbitrary handler context data |
| `roll_modifications` | `List[Tuple[str, str]]` | [(handler_name, reason)] audit trail |

---

### `D20RollResultEvent`

**File**: `dnd/core/events.py` (line 2115)
**Parent**: `DiceRollResultEvent`
**EventType**: `D20_ROLL_RESULT`
**Combat Log**: No

Base class for d20 roll results. Handlers like Lucky register for this base type to catch ALL d20 rolls.

| Field | Type | Description |
|-------|------|-------------|
| `roll` | `DiceRoll` | The initial roll result |
| `original_roll` | `DiceRoll` | Immutable copy for audit trail |
| `final_roll` | `Optional[DiceRoll]` | After handler modifications |
| `dc` | `Optional[int]` | Difficulty class if known |
| `bonus` | `Optional[ModifiableValue]` | All modifiers applied |
| `result` | `Optional[bool]` | Success/failure (set after outcome) |

**Key Methods**:
- `replace_roll(new_roll, handler_name, reason)` -- Replace roll result with audit trail
- `get_effective_roll()` -- Returns final_roll if modified, otherwise original

---

### `AttackD20RollResultEvent`

**File**: `dnd/core/events.py` (line 2148)
**Parent**: `D20RollResultEvent`
**EventType**: `ATTACK_D20_ROLL_RESULT`
**Combat Log**: No

| Field | Type | Description |
|-------|------|-------------|
| `roll_type` | `RollType` | Always `ATTACK` |
| `weapon_slot` | `Optional[WeaponSlot]` | Weapon used for attack |

**Fired by**: `Entity.roll_d20()` during attack rolls.

---

### `SavingThrowD20RollResultEvent`

**File**: `dnd/core/events.py` (line 2161)
**Parent**: `D20RollResultEvent`
**EventType**: `SAVE_D20_ROLL_RESULT`
**Combat Log**: No

| Field | Type | Description |
|-------|------|-------------|
| `roll_type` | `RollType` | Always `SAVE` |
| `ability_name` | `AbilityName` | The ability being saved against (e.g., "dexterity") |

**Fired by**: `Entity.roll_d20()` during saving throw rolls.

---

### `SkillCheckD20RollResultEvent`

**File**: `dnd/core/events.py` (line 2174)
**Parent**: `D20RollResultEvent`
**EventType**: `CHECK_D20_ROLL_RESULT`
**Combat Log**: No

| Field | Type | Description |
|-------|------|-------------|
| `roll_type` | `RollType` | Always `CHECK` |
| `skill_name` | `SkillName` | The skill being checked (e.g., "athletics") |

**Fired by**: `Entity.roll_d20()` during skill check rolls.

---

### `DamageRollResultEvent`

**File**: `dnd/core/events.py` (line 2191)
**Parent**: `DiceRollResultEvent`
**EventType**: `DAMAGE_ROLL_RESULT`
**Combat Log**: No

Fired after damage dice are rolled but before damage is applied. Enables Great Weapon Fighting, Savage Attacker, Elemental Adept, etc.

| Field | Type | Description |
|-------|------|-------------|
| `roll_type` | `RollType` | Always `DAMAGE` |
| `weapon_slot` | `WeaponSlot` | Weapon slot used |
| `attack_outcome` | `AttackOutcome` | HIT, CRIT, etc. |
| `damages` | `List[Damage]` | Damage specifications (types, dice) |
| `original_rolls` | `List[DiceRoll]` | **Immutable** -- original rolls before modifications |
| `final_rolls` | `List[DiceRoll]` | **Mutable** -- handlers replace entries here |
| `roll_modifications` | `List[Tuple[str, int, int, int, str]]` | Audit trail: (handler_name, roll_index, old_total, new_total, reason) |

**Key Method**: `replace_roll(index, new_roll, handler_name, reason)` -- Replace a specific roll and track the change.

**Fired by**: `Attack.attack_consequences()` after rolling damage dice.

---

### `HealRollResultEvent`

**File**: `dnd/core/events.py` (line 2233)
**Parent**: `DiceRollResultEvent`
**EventType**: `HEAL_ROLL_RESULT`
**Combat Log**: No

Fired after healing dice are rolled but before healing is applied. Enables Beacon of Hope (maximize healing), etc.

| Field | Type | Description |
|-------|------|-------------|
| `roll_type` | `RollType` | Always `HEAL` |
| `spell_name` | `str` | Name of the healing spell |
| `original_roll` | `DiceRoll` | **Immutable** -- original roll |
| `final_roll` | `DiceRoll` | **Mutable** -- handlers replace this |

**Key Method**: `replace_roll(new_roll, handler_name, reason)` -- Replace healing roll.

---

### `DamageRolledEvent` (DEPRECATED)

**File**: `dnd/core/events.py` (line 2264)
**Parent**: `Event`
**EventType**: `DAMAGE_ROLLED`
**Combat Log**: No

**DEPRECATED**: Use `DamageRollResultEvent` instead. Kept for backward compatibility. Has the same fields as `DamageRollResultEvent` but does not inherit from `DiceRollResultEvent`.

| Field | Type | Description |
|-------|------|-------------|
| `weapon_slot` | `WeaponSlot` | Weapon slot used |
| `attack_outcome` | `AttackOutcome` | HIT, CRIT, etc. |
| `damages` | `List[Damage]` | Damage specifications |
| `original_rolls` | `List[DiceRoll]` | Immutable original rolls |
| `final_rolls` | `List[DiceRoll]` | Mutable current best rolls |
| `roll_modifications` | `List[Tuple[str, int, int, int, str]]` | Audit trail |

---

## 6. Damage and Heal Events

### `TakeDamageEvent`

**File**: `dnd/core/events.py` (line 2309)
**Parent**: `Event`
**EventType**: `TAKE_DAMAGE`
**Combat Log**: Yes -- generates `DAMAGE_TAKEN` log entry.

Fired when an entity is about to take damage. Enables damage tracking (rage maintenance), modification (resistance/vulnerability), cancellation (immunity), and reactions to lethal damage (Relentless Rage).

| Field | Type | Description |
|-------|------|-------------|
| `total_damage` | `int` | Total damage before modifications |
| `damage_rolls` | `List[DiceRoll]` | Individual damage rolls |
| `damages` | `List[Damage]` | Damage specifications (types, dice) |
| `final_damage` | `Optional[int]` | Modified damage after handlers (None = use total_damage) |

**Key Method**: `get_effective_damage()` -- Returns `final_damage` if set, otherwise `total_damage`.

**Fired by**: `Entity.receive_damage()` which is called by `Attack.attack_consequences()`, spell damage, terrain damage, and `deal_damage_to()` test utility.

---

### `HealEvent`

**File**: `dnd/core/events.py` (line 2427)
**Parent**: `Event`
**EventType**: `HEAL`
**Combat Log**: Yes -- generates `HEAL` log entry.

Fired when an entity receives healing.

| Field | Type | Description |
|-------|------|-------------|
| `total_healing` | `int` | Healing amount requested |
| `actual_healing` | `int` | Actual HP restored (after cap at max HP) |
| `source_description` | `str` | Description of healing source (e.g., "Second Wind: d10(7)+1") |
| `was_blocked` | `bool` | True if healing was blocked (e.g., Chill Touch) |
| `spell_level` | `int` | Spell level used (0 = non-spell healing) |

**Fired by**: `Entity.receive_healing()`.

---

## 7. Combat Action Events

### `MovementEvent`

**File**: `dnd/actions.py` (line 86)
**Parent**: `ActionEvent`
**EventType**: `MOVEMENT`
**Combat Log**: Yes -- generates `MOVEMENT` log entry.

Represents a movement action (the whole path, not individual steps).

| Field | Type | Description |
|-------|------|-------------|
| `start_position` | `Tuple[int, int]` | Starting position |
| `end_position` | `Tuple[int, int]` | Target position |
| `path` | `Optional[List[Tuple[int, int]]]` | The full path |

**Fired by**: `Move._create_declaration_event()`.

---

### `AttackEvent`

**File**: `dnd/actions.py` (line 541)
**Parent**: `ActionEvent`
**EventType**: `ATTACK`
**Combat Log**: Yes -- generates `ATTACK` log entry with full roll details, breakdowns, and damage.

| Field | Type | Description |
|-------|------|-------------|
| `weapon_slot` | `WeaponSlot` | Slot of weapon used |
| `range` | `Optional[Range]` | Range of the attack |
| `is_long_range` | `bool` | True if beyond normal range (disadvantage) |
| `is_threatened` | `bool` | True if attacker has hostile within 5ft (ranged disadvantage) |
| `attack_bonus` | `Optional[ModifiableValue]` | Attack bonus with all modifiers |
| `ac` | `Optional[ModifiableValue]` | Target's AC with all modifiers |
| `dice_roll` | `Optional[DiceRoll]` | The d20 roll result |
| `attack_outcome` | `Optional[AttackOutcome]` | HIT, MISS, CRIT, or CRIT_MISS |
| `damages` | `Optional[List[Damage]]` | Damage specifications |
| `damage_rolls` | `Optional[List[DiceRoll]]` | Damage roll results |
| `weapon_name` | `Optional[str]` | Name of weapon used (for combat log) |
| `override_ability` | `Optional[AbilityName]` | Override ability for True Strike |

**Fired by**: `Attack._create_declaration_event()`. The `Attack.attack_consequences()` static method drives it through EXECUTION and EFFECT phases.

---

### `SpellEvent`

**File**: `dnd/actions.py` (line 2493)
**Parent**: `ActionEvent`
**EventType**: `CAST_SPELL`
**Combat Log**: Yes -- generates `SPELL_SAVE`, `ATTACK` (via attack spell log), `MULTI_ENTITY_ACTION`, or `ACTION` log entries depending on spell type.

Represents a spell being cast. Supports attack spells, save-based spells, auto-hit spells (Magic Missile), and multi-target spells.

| Field | Type | Description |
|-------|------|-------------|
| `spell_level` | `int` | Base spell level (0 = cantrip) |
| `cast_at_level` | `int` | Actual slot level used (0 = cantrip) |
| `spell_school` | `str` | School of magic (e.g., "evocation") |
| `verbal` | `bool` | Whether spell has a verbal component |
| `attack_bonus` | `Optional[ModifiableValue]` | Spell attack bonus (attack spells) |
| `ac` | `Optional[ModifiableValue]` | Target's AC (attack spells) |
| `dice_roll` | `Optional[DiceRoll]` | Attack roll result (attack spells) |
| `attack_outcome` | `Optional[AttackOutcome]` | Attack outcome (attack spells) |
| `save_ability` | `Optional[str]` | Ability for saving throw (save spells) |
| `save_dc` | `Optional[int]` | Save DC (save spells) |
| `save_success` | `Optional[bool]` | Whether save succeeded (save spells) |
| `save_roll` | `Optional[DiceRoll]` | Save roll result (save spells) |
| `save_bonus` | `Optional[int]` | Target's save bonus (save spells) |
| `damages` | `Optional[List[Damage]]` | Damage specifications |
| `damage_rolls` | `Optional[List[DiceRoll]]` | Damage roll results |

**Combat log dispatch** (in `generate_combat_log()`):
1. `total_targets > 0` -> `_generate_multi_target_log()` (AoE summary)
2. `save_dc is not None` -> `_generate_save_spell_log()` (save-based)
3. `attack_outcome is not None` -> `_generate_attack_spell_log()` (attack roll)
4. `damage_rolls and target_entity_name` -> `_generate_autohit_spell_log()` (Magic Missile)
5. Fallback -> generic `ActionEvent.generate_combat_log()`

**Fired by**: `SpellAction._create_declaration_event()` in `dnd/spells/base.py` (and spell subclasses).

---

### `JumpEvent`

**File**: `dnd/actions.py` (line 1685)
**Parent**: `ActionEvent`
**EventType**: `MOVEMENT`
**Combat Log**: Yes -- generates `MOVEMENT` log entry.

Represents a jump movement. Uses `MOVEMENT` event type (same as regular movement).

| Field | Type | Description |
|-------|------|-------------|
| `start_position` | `Tuple[int, int]` | Starting position |
| `end_position` | `Tuple[int, int]` | Landing position |
| `jump_distance` | `int` | Distance jumped in feet |
| `path` | `Optional[List[Tuple[int, int]]]` | Straight-line path through air |

**Fired by**: `Jump._create_declaration_event()`.

---

### `ShoveEvent`

**File**: `dnd/actions.py` (line 2089)
**Parent**: `ActionEvent`
**EventType**: `BASE_ACTION`
**Combat Log**: Yes -- generates `ACTION` log entry with shove-specific data.

BG3-style shove action. Note: uses `BASE_ACTION` event type, not a dedicated `SHOVE` type.

| Field | Type | Description |
|-------|------|-------------|
| `target_weight` | `int` | Target's weight in pounds |
| `max_shove_weight` | `int` | Max weight shover can push (STR x 12) |
| `shover_athletics` | `Optional[ModifiableValue]` | Shover's Athletics bonus |
| `target_passive` | `int` | Target's passive Athletics or Acrobatics |
| `target_resistance_skill` | `str` | Which skill target used ("athletics" or "acrobatics") |
| `dice_roll` | `Optional[DiceRoll]` | Shover's Athletics check roll |
| `contest_success` | `Optional[bool]` | Whether the contest was won |
| `push_distance` | `int` | How far target was pushed (feet) |
| `push_direction` | `Tuple[int, int]` | Direction of push (dx, dy) |
| `end_position` | `Optional[Tuple[int, int]]` | Target's final position after push |
| `knocked_prone` | `bool` | Whether target was knocked prone instead of pushed |
| `blocked_by` | `Optional[str]` | What blocked the push |
| `is_ally` | `bool` | Whether target is an ally (auto-succeed) |

**Fired by**: `Shove._create_declaration_event()`.

---

## 8. Encounter Lifecycle Events

### `EncounterEvent` (Base)

**File**: `dnd/core/events.py` (line 2486)
**Parent**: `Event`
**Combat Log**: No (base class)

| Field | Type | Description |
|-------|------|-------------|
| `encounter_uuid` | `UUID` | UUID of the encounter |
| `combatant_uuids` | `List[UUID]` | UUIDs of all combatants |

---

### `EncounterStartEvent`

**File**: `dnd/core/events.py` (line 2493)
**Parent**: `EncounterEvent`
**EventType**: `ENCOUNTER_START`
**Combat Log**: No

| Field | Type | Description |
|-------|------|-------------|
| `initiative_order` | `List[UUID]` | Combatants sorted by initiative |

**Fired by**: `Encounter.start_encounter()`.

---

### `EncounterEndEvent`

**File**: `dnd/core/events.py` (line 2500)
**Parent**: `EncounterEvent`
**EventType**: `ENCOUNTER_END`
**Combat Log**: No

| Field | Type | Description |
|-------|------|-------------|
| `reason` | `Optional[str]` | Why the encounter ended |

**Fired by**: `Encounter.end_encounter()`.

---

### `RoundEvent` (Base)

**File**: `dnd/core/events.py` (line 2507)
**Parent**: `Event`
**Combat Log**: No (base class)

| Field | Type | Description |
|-------|------|-------------|
| `encounter_uuid` | `UUID` | UUID of the encounter |
| `round_number` | `int` | Current round number (1-indexed) |

---

### `RoundStartEvent`

**File**: `dnd/core/events.py` (line 2514)
**Parent**: `RoundEvent`
**EventType**: `ROUND_START`
**Combat Log**: No

**Fired by**: `Encounter.start_turn()` when a new round begins.

---

### `RoundEndEvent`

**File**: `dnd/core/events.py` (line 2520)
**Parent**: `RoundEvent`
**EventType**: `ROUND_END`
**Combat Log**: No

**Fired by**: `Encounter.end_round()`.

---

### `TurnEvent` (Base)

**File**: `dnd/core/events.py` (line 2526)
**Parent**: `Event`
**Combat Log**: No (base class)

| Field | Type | Description |
|-------|------|-------------|
| `encounter_uuid` | `UUID` | UUID of the encounter |
| `entity_uuid` | `UUID` | UUID of entity whose turn it is |
| `round_number` | `int` | Current round number |
| `turn_index` | `int` | Position in initiative order (0-indexed) |

---

### `TurnStartEvent`

**File**: `dnd/core/events.py` (line 2535)
**Parent**: `TurnEvent`
**EventType**: `TURN_START`
**Combat Log**: Yes -- generates `TURN_START` log entry.

| Field | Type | Description |
|-------|------|-------------|
| `actions_available` | `int` | Actions available this turn |
| `bonus_actions_available` | `int` | Bonus actions available |
| `movement_available` | `int` | Movement available in feet |
| `reaction_available` | `int` | Reaction available |

**Fired by**: `Encounter.start_turn()`.

---

### `TurnEndEvent`

**File**: `dnd/core/events.py` (line 2567)
**Parent**: `TurnEvent`
**EventType**: `TURN_END`
**Combat Log**: Yes -- generates `TURN_END` log entry.

| Field | Type | Description |
|-------|------|-------------|
| `actions_used` | `int` | Actions used this turn |
| `bonus_actions_used` | `int` | Bonus actions used |
| `movement_used` | `int` | Movement used in feet |

**Fired by**: `Encounter.end_turn()`.

---

## 9. Death Event

### `DeathEvent`

**File**: `dnd/core/events.py` (line 2598)
**Parent**: `Event`
**EventType**: `DEATH`
**Combat Log**: Yes -- generates `DEATH` log entry with dramatic formatting.

| Field | Type | Description |
|-------|------|-------------|
| `entity_uuid` | `UUID` | UUID of the entity that died |
| `entity_name` | `str` | Name of the entity that died |
| `killer_uuid` | `Optional[UUID]` | UUID of entity that dealt killing blow |
| `killer_name` | `str` | Name of killer if known |
| `final_hp` | `int` | Final HP value (typically negative) |
| `encounter_uuid` | `Optional[UUID]` | UUID of encounter if in combat |

**Fired by**: `Entity.receive_damage()` when HP drops to 0 or below.

---

## 10. Condition Events

### `ConditionApplicationEvent`

**File**: `dnd/core/base_conditions.py` (line 104)
**Parent**: `Event`
**EventType**: `CONDITION_APPLICATION`
**Combat Log**: Yes -- generates `CONDITION_APPLIED` log entry. Suppressed for `ConditionCategory.INTERNAL` conditions.

| Field | Type | Description |
|-------|------|-------------|
| `condition` | `BaseCondition` | The condition being applied (**full object, not UUID**) |
| `source_entity_name` | `Optional[str]` | Name of the source entity |
| `target_entity_name` | `Optional[str]` | Name of the target entity |

**Fired by**: `BaseBlock.add_condition()` after condition is applied.

**Note**: The `condition` field embeds a full `BaseCondition` object. This is necessary because handlers need to inspect condition properties (name, category, duration) at event processing time.

---

### `ConditionRemovalEvent`

**File**: `dnd/core/base_conditions.py` (line 151)
**Parent**: `Event`
**EventType**: `CONDITION_REMOVAL`
**Combat Log**: Yes -- generates `CONDITION_REMOVED` log entry. Suppressed for `ConditionCategory.INTERNAL` conditions.

| Field | Type | Description |
|-------|------|-------------|
| `condition` | `BaseCondition` | The condition being removed (**full object, not UUID**) |
| `expired` | `bool` | Whether removal was due to expiration |
| `source_entity_name` | `Optional[str]` | Name of the source entity |
| `target_entity_name` | `Optional[str]` | Name of the target entity |

**Fired by**: `BaseBlock._remove_condition_tree()` during condition cleanup.

---

## 11. D20 Legacy Events

These are the original d20 event classes used for saving throws and skill checks before the unified dice roll event hierarchy was created. They are still actively used for save/check resolution and have `generate_combat_log()` methods.

### `D20Event`

**File**: `dnd/core/events.py` (line 1321)
**Parent**: `Event`
**EventType**: Not set (base class)
**Combat Log**: No

Base class for d20-based resolution events.

| Field | Type | Description |
|-------|------|-------------|
| `dc` | `Optional[Union[int, ModifiableValue]]` | Difficulty class |
| `bonus` | `Optional[Union[int, ModifiableValue]]` | Bonus to the roll |
| `dice` | `Optional[Dice]` | Dice object used for the roll |
| `dice_roll` | `Optional[DiceRoll]` | The roll result |
| `result` | `Optional[bool]` | Whether the check succeeded |

**Key Method**: `get_dc()` -- Returns DC as int (resolves `ModifiableValue` if needed).

---

### `SavingThrowEvent`

**File**: `dnd/core/events.py` (line 1338)
**Parent**: `D20Event`
**EventType**: `SAVING_THROW`
**Combat Log**: Yes -- generates `SAVING_THROW` log entry with roll details, breakdown, and success/failure.

| Field | Type | Description |
|-------|------|-------------|
| `ability_name` | `AbilityName` | The ability being saved against (e.g., "dexterity") |

**Fired by**: `Entity.saving_throw()` during save resolution (spell saves, condition saves, etc.).

---

### `SkillCheckEvent`

**File**: `dnd/core/events.py` (line 1451)
**Parent**: `D20Event`
**EventType**: `SKILL_CHECK`
**Combat Log**: Yes -- generates `SKILL_CHECK` log entry with roll details.

| Field | Type | Description |
|-------|------|-------------|
| `skill_name` | `SkillName` | The skill being checked (e.g., "athletics", "stealth") |

**Fired by**: `Entity.skill_check()` during skill check resolution, and directly by `Hide._apply()` for stealth checks.

---

## 12. Serialization Patterns

Events must be JSON-serializable via `model_dump(mode='json')` for the server API (`server/event_server.py`).

### UUID-Based References (Correct Pattern)

Event fields should store UUIDs to reference other objects, not embed full objects:

```python
# GOOD: Store UUID reference
target_entity_uuid: UUID  # Inherited from Event
parent_event: Optional[UUID]  # UUID of parent event
killer_uuid: Optional[UUID]  # UUID of killer
```

### Known Serialization Issues

**Equipment events** embed full objects instead of UUIDs:

```python
# CURRENT (problematic for serialization):
class WeaponEquipEvent(EquipmentEvent):
    weapon: Weapon  # Full Pydantic object embedded

# PREFERRED (not yet refactored):
class WeaponEquipEvent(EquipmentEvent):
    weapon_uuid: UUID  # UUID reference
```

This applies to all six equipment event types (`WeaponEquipEvent`, `WeaponUnequipEvent`, `ArmorEquipEvent`, `ArmorUnequipEvent`, `ShieldEquipEvent`, `ShieldUnequipEvent`).

**Condition events** embed full `BaseCondition` objects:

```python
class ConditionApplicationEvent(Event):
    condition: BaseCondition  # Full object, needed by handlers
```

This is intentional -- handlers need to inspect condition properties at event processing time.

### ModifiableValue Fields

Several events carry `ModifiableValue` objects (`AttackEvent.attack_bonus`, `AttackEvent.ac`, `SpellEvent.attack_bonus`, etc.). These are snapshot values captured at event creation time and serialize correctly via Pydantic.

### Combat Log Exclusion

The `combat_log` field on `Event` is marked `exclude=True` so it does not appear in `model_dump()` output:

```python
combat_log: Optional[CombatLogEntry] = Field(default=None, exclude=True)
```

Combat logs are generated on-demand at COMPLETION phase and delivered via callback, not serialized with the event.

---

## 13. EventType Enum Reference

**File**: `dnd/core/events.py` (line 122)

Complete listing of all `EventType` enum values and which event classes use them.

### Core Action Events

| Value | Event Class(es) |
|-------|-----------------|
| `BASE_ACTION` | `ActionEvent`, `ShoveEvent` |
| `ATTACK` | `AttackEvent` |
| `MOVEMENT` | `MovementEvent`, `JumpEvent` |
| `STEP_MOVEMENT` | `StepMovementEvent` |
| `FORCED_MOVEMENT` | `ForcedMovementEvent` |
| `CAST_SPELL` | `SpellEvent` |
| `TAKE_DAMAGE` | `TakeDamageEvent` |
| `HEAL` | `HealEvent` |

### D20 / Dice Events

| Value | Event Class(es) |
|-------|-----------------|
| `SAVING_THROW` | `SavingThrowEvent` |
| `SKILL_CHECK` | `SkillCheckEvent` |
| `ABILITY_CHECK` | (not yet used by a specific event class) |
| `DICE_ROLL` | (not yet used by a specific event class) |
| `DICE_ROLL_RESULT` | `DiceRollResultEvent` (base) |
| `D20_ROLL_RESULT` | `D20RollResultEvent` |
| `ATTACK_D20_ROLL_RESULT` | `AttackD20RollResultEvent` |
| `SAVE_D20_ROLL_RESULT` | `SavingThrowD20RollResultEvent` |
| `CHECK_D20_ROLL_RESULT` | `SkillCheckD20RollResultEvent` |
| `DAMAGE_ROLL_RESULT` | `DamageRollResultEvent` |
| `HEAL_ROLL_RESULT` | `HealRollResultEvent` |
| `DAMAGE_ROLLED` | `DamageRolledEvent` **(DEPRECATED)** |

### Attack Outcome Events (EventType only, no dedicated classes)

| Value | Used By |
|-------|---------|
| `INFLICT_DAMAGE` | (handler triggers only) |
| `ATTACK_MISS` | (handler triggers only) |
| `ATTACK_HIT` | (handler triggers only) |
| `ATTACK_CRITICAL` | (handler triggers only) |

### Equipment Events

| Value | Event Class |
|-------|-------------|
| `WEAPON_EQUIP` | `WeaponEquipEvent` |
| `WEAPON_UNEQUIP` | `WeaponUnequipEvent` |
| `ARMOR_EQUIP` | `ArmorEquipEvent` |
| `ARMOR_UNEQUIP` | `ArmorUnequipEvent` |
| `SHIELD_EQUIP` | `ShieldEquipEvent` |
| `SHIELD_UNEQUIP` | `ShieldUnequipEvent` |

### Condition Events

| Value | Event Class |
|-------|-------------|
| `CONDITION_APPLICATION` | `ConditionApplicationEvent` |
| `CONDITION_REMOVAL` | `ConditionRemovalEvent` |

### Spatial Events

| Value | Created By |
|-------|------------|
| `SPATIAL_ENTITY_ENTERED` | `SpatialChangeEvent.entity_entered()` |
| `SPATIAL_ENTITY_LEFT` | `SpatialChangeEvent.entity_left()` |
| `SPATIAL_TILE_CHANGED` | `SpatialChangeEvent.tile_changed()` |
| `SPATIAL_OBJECT_PLACED` | `SpatialChangeEvent.object_placed()` |
| `SPATIAL_OBJECT_REMOVED` | `SpatialChangeEvent.object_removed()` |
| `SPATIAL_PERCEIVABILITY_CHANGED` | `SpatialChangeEvent.perceivability_changed()` |
| `SPATIAL_LIGHT_CHANGED` | `SpatialChangeEvent.light_changed()` |
| `SPATIAL_OBJECT_CHANGED` | `SpatialChangeEvent.object_changed()` |
| `MOVEMENT_COLLISION` | `SpatialChangeEvent.movement_collision()` |

### Encounter Lifecycle Events

| Value | Event Class |
|-------|-------------|
| `ENCOUNTER_START` | `EncounterStartEvent` |
| `ENCOUNTER_END` | `EncounterEndEvent` |
| `ROUND_START` | `RoundStartEvent` |
| `ROUND_END` | `RoundEndEvent` |
| `TURN_START` | `TurnStartEvent` |
| `TURN_END` | `TurnEndEvent` |
| `DEATH` | `DeathEvent` |

### Other EventTypes (Triggers Only)

| Value | Description |
|-------|-------------|
| `TRIGGER_EVENT` | Generic trigger used by `BaseHandler.get_declaration_event()` |
| `ENEMY_SPOTTED` | Combat awareness (handler triggers) |
| `ENEMY_KILLED` | Kill tracking (handler triggers) |
| `ENEMY_ENGAGED` | Engagement tracking (handler triggers) |

---

## Class Hierarchy Summary

```
BaseObject
└── Event (dnd/core/events.py)
    ├── ActionEvent (dnd/core/base_actions.py)
    │   ├── MovementEvent (dnd/actions.py)
    │   ├── AttackEvent (dnd/actions.py)
    │   ├── SpellEvent (dnd/actions.py)
    │   ├── JumpEvent (dnd/actions.py)
    │   └── ShoveEvent (dnd/actions.py)
    │
    ├── EquipmentEvent (dnd/blocks/equipment.py)
    │   ├── WeaponEquipEvent
    │   ├── WeaponUnequipEvent
    │   ├── ArmorEquipEvent
    │   ├── ArmorUnequipEvent
    │   ├── ShieldEquipEvent
    │   └── ShieldUnequipEvent
    │
    ├── SpatialChangeEvent (dnd/core/events.py)
    ├── ForcedMovementEvent (dnd/core/events.py)
    ├── StepMovementEvent (dnd/core/events.py)
    │
    ├── DiceRollResultEvent (dnd/core/events.py)
    │   ├── D20RollResultEvent
    │   │   ├── AttackD20RollResultEvent
    │   │   ├── SavingThrowD20RollResultEvent
    │   │   └── SkillCheckD20RollResultEvent
    │   ├── DamageRollResultEvent
    │   └── HealRollResultEvent
    │
    ├── DamageRolledEvent (DEPRECATED)
    ├── TakeDamageEvent (dnd/core/events.py)
    ├── HealEvent (dnd/core/events.py)
    │
    ├── D20Event (dnd/core/events.py)
    │   ├── SavingThrowEvent
    │   └── SkillCheckEvent
    │
    ├── EncounterEvent (dnd/core/events.py)
    │   ├── EncounterStartEvent
    │   └── EncounterEndEvent
    │
    ├── RoundEvent (dnd/core/events.py)
    │   ├── RoundStartEvent
    │   └── RoundEndEvent
    │
    ├── TurnEvent (dnd/core/events.py)
    │   ├── TurnStartEvent
    │   └── TurnEndEvent
    │
    ├── DeathEvent (dnd/core/events.py)
    │
    ├── ConditionApplicationEvent (dnd/core/base_conditions.py)
    └── ConditionRemovalEvent (dnd/core/base_conditions.py)
```
