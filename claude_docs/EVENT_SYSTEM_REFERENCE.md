# Event System Deep-Dive — D&D 5e Combat Engine

> **Purpose**: This document explains how the event system works at the data level. A frontend developer reading this can understand exactly what events fire for every gameplay scenario, what data each event carries, and how to use the event stream to maintain client-side game state reactively — without polling the REST API for every change.
>
> **Companion to**: `BACKEND_REFERENCE.md` (REST API, data models, system overview)
>
> **Core thesis**: Listening to the event stream is sufficient to track all causal game state changes (HP, position, conditions, turns). Computed state (available actions, movement paths, FOV) still requires REST queries.

---

## Table of Contents

1. [Event Architecture](#1-event-architecture)
2. [WebSocket Event Delivery](#2-websocket-event-delivery)
3. [Complete Event Type Catalog](#3-complete-event-type-catalog)
4. [Attack Event Flow](#4-attack-event-flow)
5. [Spell Event Flows](#5-spell-event-flows)
6. [AoE & Multi-Target Event Flow](#6-aoe--multi-target-event-flow)
7. [Movement Event Flow](#7-movement-event-flow)
8. [Trap & Zone Entry Event Flows](#8-trap--zone-entry-event-flows)
9. [Reactive Sensory Cascades](#9-reactive-sensory-cascades)
10. [Client State Reconstruction Guide](#10-client-state-reconstruction-guide)
11. [Event Phase Timing Reference](#11-event-phase-timing-reference)

---

## 1. Event Architecture

### The Event Base Class

Every event in the system inherits from `Event` with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `uuid` | string | Unique event identifier |
| `name` | string | Human-readable name (e.g., "Attack", "Movement") |
| `lineage_uuid` | string | **Shared across all phases** of the same action. Also shared by all child events. Key for grouping related events. |
| `timestamp` | datetime | When the event was created |
| `event_type` | string | EventType enum value (e.g., `"attack"`, `"movement"`) |
| `phase` | string | Current phase: `"declaration"`, `"execution"`, `"effect"`, `"completion"`, or `"cancel"` |
| `source_entity_uuid` | string | Entity originating the event |
| `target_entity_uuid` | string or null | Entity affected by the event |
| `source_entity_name` | string or null | Source entity's display name |
| `target_entity_name` | string or null | Target entity's display name |
| `modified` | bool | Whether handlers modified this event |
| `canceled` | bool | Whether this event was cancelled |
| `parent_event` | string or null | UUID of parent event (for nested events) |
| `status_message` | string or null | Explains phase transitions or cancellations |
| `is_first` | bool | True if first event of this phase in this lineage |
| `is_last` | bool | True if last event of this phase in this lineage |
| `lineage_children_events` | list of string | All children across all phases |
| `children_events` | list of string | Children during current phase only |
| `combat_log` | **EXCLUDED** | Generated at COMPLETION but excluded from serialization |

### Phase Lifecycle

Every event progresses through phases:

```
DECLARATION → EXECUTION → EFFECT → COMPLETION
                                  ↘ (or CANCEL)
```

Each `phase_to()` call creates a **new event copy** with the same `lineage_uuid` but incremented phase. The original event at the previous phase remains in storage.

| Phase | What Happens | Handlers Fire? |
|-------|-------------|----------------|
| **DECLARATION** | Intent announced. "I want to attack." Handlers can cancel. | Yes |
| **EXECUTION** | Action begins. Costs committed. Dice rolled. | Yes |
| **EFFECT** | Effects applied. Damage dealt. Conditions added. Last chance for reactions. | Yes |
| **COMPLETION** | Finished. Combat log generated. **No handlers fire.** | **No** |
| **CANCEL** | Aborted by a handler. No effects applied. | No |

**Critical rule**: COMPLETION deliberately skips all EventHandlers. This separates the causal chain (DECLARATION → EFFECT, where handlers react and modify) from observation (COMPLETION, where the combat log captures what happened). If you register a handler on COMPLETION, it will **never fire**.

### EventQueue Internals

The `EventQueue` is the central event bus. When an event is registered:

1. **Handler processing** — Matching EventHandlers fire (DECLARATION/EXECUTION/EFFECT only)
2. **Storage** — Event stored in **8 indices** for fast lookup:
   - By UUID, by lineage, by type, by phase, by source entity, by target entity, by timestamp, chronological (`_all_events`)
   - Parent-child relationships are tracked via fields on the Event object itself (`children_events`, `lineage_children_events`), not as a separate index
3. **Passive callbacks** — All registered `on_event_callbacks` fire (including WebSocket broadcast)
4. **Combat log callback** — If COMPLETION phase and event has combat_log, the Encounter's callback fires

**Passive callbacks vs EventHandlers**:
- **EventHandlers** react to specific event types/phases, can modify or cancel events
- **Passive callbacks** fire for ALL events, cannot modify them — used for monitoring, logging, WebSocket

### Lineage System

The `lineage_uuid` is the key to understanding event relationships:

- **Same action, different phases**: A movement's DECLARATION, EXECUTION, EFFECT, and COMPLETION events all share the same `lineage_uuid`
- **Parent-child events**: When an attack triggers an opportunity attack, the OA event has a different `lineage_uuid` but its `parent_event` points to the step movement event that triggered it
- **Multi-target actions**: Each target in a Fireball gets its own child event with its own `lineage_uuid` for independent tracking, but all share the same `parent_event` pointing to the Fireball parent

### Event Serialization

Events serialize via Pydantic `model_dump(mode='json')`. What gets serialized:

| Serialized | Not Serialized |
|-----------|---------------|
| All base Event fields | `combat_log` (CombatLogEntry — excluded) |
| DiceRoll objects (results, bonus, total) | ModifiableValue internals (only computed values visible) |
| Damage objects (type, dice, bonus) | |
| Range objects (type, normal, long) | |
| Costs list | |
| Nested Pydantic models | |
| UUIDs as strings | |
| Enums as string values | |

**Key implication**: The client receives dice rolls, damage values, and outcomes directly on events — but NOT the combat log text. Combat log must be fetched separately via REST or from `ActionResult.combat_log_entries`.

---

## 2. WebSocket Event Delivery

### Connection

```
ws://localhost:8000/ws
```

On connect, server sends:
```json
{
  "type": "connected",
  "message": "Connected to D&D Engine Event Server",
  "event_count": 47
}
```

### Event Messages (Server → Client)

Every event in the system is broadcast to all connected WebSocket clients:

```json
{
  "type": "event",
  "event": {
    "uuid": "550e8400-...",
    "name": "Attack",
    "event_type": "attack",
    "phase": "completion",
    "source_entity_uuid": "abc-123",
    "target_entity_uuid": "def-456",
    "source_entity_name": "Fighter",
    "target_entity_name": "Goblin",
    "lineage_uuid": "789-...",
    "canceled": false,
    "modified": false,
    "weapon_slot": "MELEE_MAIN",
    "dice_roll": {"results": [17], "bonus": 5, "total": 22},
    "attack_outcome": "HIT",
    "damage_rolls": [{"results": [4], "bonus": 3, "total": 7}],
    ...
  }
}
```

**ALL phases are broadcast** — you'll see DECLARATION, EXECUTION, EFFECT, and COMPLETION for every event. The client should typically only act on COMPLETION-phase events for final state.

### Client Commands (Client → Server)

| Command | Purpose | Example |
|---------|---------|---------|
| `ping` | Keep-alive | `{"type": "ping"}` → `{"type": "pong"}` |
| `filter` | Filter by event types | `{"type": "filter", "event_types": ["attack", "movement", "take_damage"]}` → `{"type": "filter_set", "event_types": [...]}` |
| `filter` (clear) | Remove filter | `{"type": "filter"}` (no event_types) → `{"type": "filter_cleared"}` |
| `get_history` | Replay past events | `{"type": "get_history", "limit": 50}` → stream of event messages |

### Queue Overflow

Each client has an `asyncio.Queue(maxsize=100)`. If a client is slow and the queue fills, events are **silently dropped**. The client won't know it missed events. Recovery: call `get_history` to catch up, or fetch full state via REST.

### What's NOT on WebSocket

The `combat_log` field on events is **excluded from serialization**. Combat log entries are:
- Available via `GET /combat-log?since=N` (polling)
- Included in `ActionResult.combat_log_entries` (after action execution via REST)
- Generated at COMPLETION phase but only delivered to the Encounter via internal callback

### Event Cursor Endpoint

`GET /events?since=<cursor>&limit=0&phase=completion` returns events from a known cursor position:

```json
{
  "events": [...],
  "count": 12,
  "total": 59       // ← use as cursor for next request
}
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `since` | 0 | `0` = return last `limit` events (backwards-compatible). `> 0` = cursor mode, returns events from index onward. |
| `limit` | 50 | Max events to return. `0` = unlimited (recommended for cursor mode). |
| `event_type` | null | Filter by event type (e.g., `"attack"`, `"movement"`) |
| `phase` | null | Filter by event phase (e.g., `"completion"`) |

The `total` field equals `event_count` from both `GET /` and the WebSocket handshake — use any as your cursor.

**Cursor mode gives exactly-once delivery**: store `total` from each response, pass it as `since` next poll. Zero overlap, zero duplicates, no need for UUID-based deduplication.

### Recommended Client Patterns

**Pattern A — Polling only (recommended for simplicity):**

```
1. GET /state                                        → Full snapshot
2. GET /events?since=0&limit=0                       → Grab total as initial cursor
3. Start polling: GET /events?since=<cursor>&limit=0&phase=completion  (every ~400ms)
4. Each response: apply events, set cursor = total
5. On error / unknown entity in event → GET /state + reset cursor
```

**Pattern B — WebSocket with cursor recovery:**

```
1. GET /state                                        → Full snapshot + note event_count
2. Connect to ws://host/ws                           → Handshake returns event_count
3. GET /events?since=<state_count>                   → Catch up on events fired between 1 and 2
4. Send filter (optional)                            → Only receive event types you care about
5. Listen for live events                            → Apply incremental state updates
6. On queue overflow / reconnect                     → GET /events?since=<last_total> to catch up
```

Pattern A is simpler and sufficient for turn-based combat. Pattern B offers lower latency for real-time scenarios.

---

## 3. Complete Event Type Catalog

### ActionEvent (Base for All Action Events)

Defined in `dnd/core/base_actions.py`. All attack, spell, movement, and ability events inherit from `ActionEvent`:

| Field | Type | Description |
|-------|------|-------------|
| `costs` | list of Cost | Action economy costs (type + amount) |
| `description` | string | Action description |
| `total_targets` | int | Number of targets (populated for multi-target at EFFECT) |
| `total_damage` | int | Aggregate damage (populated for multi-target at EFFECT) |
| `aoe_position` | `[x, y]` or null | Center position for AoE actions |

### AttackEvent

| Field | Type | When Set | Description |
|-------|------|----------|-------------|
| `weapon_slot` | string | Creation | `"MELEE_MAIN"`, `"MELEE_OFF"`, `"RANGED_MAIN"`, `"RANGED_OFF"` |
| `range` | Range or null | DECLARATION | Weapon range (type, normal, long distances) |
| `is_long_range` | bool | DECLARATION | True if target beyond normal range |
| `is_threatened` | bool | DECLARATION | True if ranged attacker has hostile within 5ft |
| `attack_bonus` | ModifiableValue or null | EXECUTION | Attacker's total bonus (cross-propagated with target AC) |
| `ac` | ModifiableValue or null | EXECUTION | Target's AC (cross-propagated with attack bonus) |
| `dice_roll` | DiceRoll or null | Post-EXECUTION | d20 roll result with advantage/disadvantage |
| `attack_outcome` | string or null | Post-EXECUTION | `"HIT"`, `"MISS"`, `"CRIT"`, `"CRIT_MISS"` |
| `damages` | list of Damage or null | EFFECT | Damage specifications (type, dice, bonus) |
| `damage_rolls` | list of DiceRoll or null | EFFECT | Rolled damage dice results |
| `weapon_name` | string or null | Creation | Weapon display name |
| `override_ability` | string or null | Creation | Override ability for attack (True Strike) |

### SpellEvent

Inherits all AttackEvent fields plus:

| Field | Type | When Set | Description |
|-------|------|----------|-------------|
| `spell_level` | int | Creation | Base spell level (0 = cantrip) |
| `cast_at_level` | int | Creation | Actual slot level used (upcasting) |
| `spell_school` | string | Creation | `"evocation"`, `"abjuration"`, etc. |
| `verbal` | bool | Creation | Has verbal component |
| `save_ability` | string or null | EXECUTION | Ability for save: `"dexterity"`, `"wisdom"`, etc. |
| `save_dc` | int or null | EXECUTION | DC for the saving throw |
| `save_success` | bool or null | EFFECT | Whether target saved |
| `save_roll` | DiceRoll or null | EFFECT | The save roll result |
| `save_bonus` | int or null | EFFECT | Target's save bonus |

**Note**: Attack spells (Fire Bolt) use the attack fields (dice_roll, attack_outcome). Save spells (Fireball) use the save fields (save_dc, save_success). Both can have damages/damage_rolls.

### MovementEvent

| Field | Type | Description |
|-------|------|-------------|
| `start_position` | `[x, y]` | Position before movement |
| `end_position` | `[x, y]` | Final position after movement |
| `path` | list of `[x, y]` or null | Full path including start and end |
| `costs` | list of Cost | Movement cost in feet |

### StepMovementEvent

Fires for **each individual cell transition** during movement:

| Field | Type | Description |
|-------|------|-------------|
| `from_position` | `[x, y]` | Position before this step |
| `to_position` | `[x, y]` | Position after this step |
| `path_index` | int | Index in overall path (0-based) |
| `total_path_length` | int | Total positions in path |
| `movement_cost` | float | Cost in feet for this step (5.0 normal, 10.0 difficult terrain) |

**Why this matters**: Opportunity attack handlers fire on StepMovementEvent at EFFECT phase. The step can be cancelled by a handler (e.g., OA kills the mover), stopping the rest of the movement.

### ForcedMovementEvent

Used for push/pull effects (Shove, Thunderwave). Does **NOT** trigger opportunity attacks:

| Field | Type | Description |
|-------|------|-------------|
| `start_position` | `[x, y]` | Position before push |
| `end_position` | `[x, y]` | Position after push |
| `direction` | `[dx, dy]` | Push direction |
| `intended_distance` | int | How far the push tried to go (feet) |
| `actual_distance` | int | How far the entity actually moved |
| `blocked_by_obstacle` | bool | Whether push was stopped by a wall/entity |
| `blocked_by` | string or null | Description of what blocked the push |

### TakeDamageEvent

| Field | Type | Description |
|-------|------|-------------|
| `total_damage` | int | Damage before handler modifications |
| `final_damage` | int or null | Damage after handlers reduce it (e.g., Relentless Rage). If null, use `total_damage`. |
| `damage_rolls` | list of DiceRoll | The damage dice results |
| `damages` | list of Damage | Damage type specifications |

**`get_effective_damage()`**: Returns `final_damage` if set, otherwise `total_damage`. This is the actual HP reduction.

### HealEvent

| Field | Type | Description |
|-------|------|-------------|
| `total_healing` | int | Requested healing amount |
| `actual_healing` | int | Actual HP restored (capped at max HP) |
| `was_blocked` | bool | True if healing was negated (e.g., Chill Touch) |
| `spell_level` | int | Spell level that caused healing (0 = non-spell) |
| `source_description` | string | Description: `"Second Wind: d10(7)+1"` |

### D20RollResultEvent

Fires after a d20 is rolled but before the outcome is determined. Handlers can intercept (Lucky, Portent):

| Field | Type | Description |
|-------|------|-------------|
| `roll` | DiceRoll | The d20 roll |
| `original_roll` | DiceRoll | Immutable copy of original roll |
| `final_roll` | DiceRoll or null | Modified roll (if handler changed it) |
| `dc` | int or null | DC if applicable |
| `bonus` | ModifiableValue or null | All modifiers applied |
| `result` | bool or null | Success/failure (set after outcome) |

### DamageRollResultEvent

Fires after damage dice are rolled but before damage is applied. Handlers can reroll (Great Weapon Fighting):

| Field | Type | Description |
|-------|------|-------------|
| `weapon_slot` | string | Weapon slot used |
| `attack_outcome` | string | HIT, CRIT, MISS |
| `damages` | list of Damage | Read-only damage specs |
| `original_rolls` | list of DiceRoll | Immutable original rolls |
| `final_rolls` | list of DiceRoll | **Mutable** — handlers replace entries here |
| `roll_modifications` | list of tuples | Audit trail: `(handler_name, roll_index, old_total, new_total, reason)` |

### SavingThrowEvent

| Field | Type | Description |
|-------|------|-------------|
| `ability_name` | string | `"strength"`, `"dexterity"`, `"constitution"`, etc. |
| `dc` | int | DC to beat |
| `roll_result` | DiceRoll or null | The save roll |

### SkillCheckEvent

| Field | Type | Description |
|-------|------|-------------|
| `skill_name` | string | `"perception"`, `"athletics"`, `"stealth"`, etc. |
| `dc` | int or null | DC (may not have one for contested checks) |
| `roll_result` | DiceRoll or null | The skill check roll |

### ConditionApplicationEvent

Defined in `dnd/core/base_conditions.py` (not events.py).

| Field | Type | Description |
|-------|------|-------------|
| `condition` | BaseCondition | Full condition object (name, description, category, duration, etc.) |
| `source_entity_name` | string or null | Who applied it |
| `target_entity_name` | string or null | Who it was applied to |

### ConditionRemovalEvent

Defined in `dnd/core/base_conditions.py` (not events.py).

| Field | Type | Description |
|-------|------|-------------|
| `condition` | BaseCondition | Full condition object |
| `expired` | bool | True if removed due to duration expiry (vs. explicit removal) |
| `source_entity_name` | string or null | Original source |
| `target_entity_name` | string or null | Who it was on |

### SpatialChangeEvent

The event type for all grid-level changes:

| Field | Type | Description |
|-------|------|-------------|
| `change_type` | string | `"entity_entered"`, `"entity_left"`, `"tile_changed"`, `"object_placed"`, `"object_removed"`, `"light_changed"`, `"perceivability_changed"`, `"object_changed"` |
| `position` | `[x, y]` | Grid position of change |
| `entity_uuid` | string or null | Entity involved |
| `object_uuid` | string or null | Object (item) involved |
| `old_position` | `[x, y]` or null | Previous position (for movement) |
| `tile_walkable` | bool or null | New walkability (for tile changes) |
| `tile_visible` | bool or null | New visibility (for tile changes) |
| `senses_hint` | SensesUpdateHint or null | Hint for incremental senses updates |

### SensesUpdateHint

Carried on SpatialChangeEvents to tell observers exactly what to update:

| Field | Type | Description |
|-------|------|-------------|
| `requires_fov` | bool | Vision geometry changed (walls, doors, magical darkness) — full FOV recompute |
| `requires_paths` | bool | Path topology changed (entity moved, walkability changed) — mark paths dirty |
| `entity_entered` | `[uuid, [x, y]]` or null | Entity entered this cell — O(1) dict add |
| `entity_left` | `[uuid, [x, y]]` or null | Entity left this cell — O(1) dict remove |
| `entity_died` | `[uuid, [x, y]]` or null | Entity died at this position — unblock cell |
| `light_changed_positions` | set of `[x, y]` or null | Positions where light level changed — refilter visibility |
| `perceivability_entity` | string or null | Entity whose hidden/invisible state changed — O(1) re-check |
| `object_placed` | `[uuid, [x, y]]` or null | Object placed on floor — O(1) dict add |
| `object_removed` | `[uuid, [x, y]]` or null | Object removed from floor — O(1) dict remove |

### Encounter Lifecycle Events

| Event | Key Fields | When |
|-------|-----------|------|
| **EncounterStartEvent** | `encounter_uuid`, `combatant_uuids`, `initiative_order` | Combat begins |
| **EncounterEndEvent** | `encounter_uuid`, `combatant_uuids`, `reason` | Combat ends |
| **RoundStartEvent** | `encounter_uuid`, `round_number` | New round begins |
| **RoundEndEvent** | `encounter_uuid`, `round_number` | Round ends |
| **TurnStartEvent** | `encounter_uuid`, `combatant_uuids`, `turn_index`, `current_entity_uuid` | Entity's turn begins |
| **TurnEndEvent** | `encounter_uuid`, `combatant_uuids`, `turn_index` | Entity's turn ends |
| **DeathEvent** | `encounter_uuid`, `entity_uuid` | Entity reduced to 0 HP |

### DiceRoll Object (Serialized on Events)

When an event carries a `DiceRoll`, it serializes as:

| Field | Type | Description |
|-------|------|-------------|
| `results` | list of int | Individual die results: `[17]` for d20, `[3, 5, 2, 4]` for 4d6 |
| `bonus` | int | Total bonus applied |
| `total` | int | Final total (sum of results + bonus) |
| `dice_count` | int | Number of dice rolled |
| `dice_type` | int | Die type (20, 6, 8, etc.) |
| `advantage` | string or null | `"advantage"`, `"disadvantage"`, or null |
| `all_rolls` | list of int or null | All d20 rolls when advantage/disadvantage (both dice) |

---

## 4. Attack Event Flow

This section traces a complete melee attack, showing exactly what data is on the event at each phase.

### Scenario: Fighter attacks Goblin with Longsword

```
Fighter (STR 16, Prof +2, Longsword 1d8+3)
  attacks
Goblin (AC 15, 7 HP)
```

### Phase 1: DECLARATION

The attack action creates its first event:

```json
{
  "event_type": "attack",
  "phase": "declaration",
  "source_entity_uuid": "fighter-uuid",
  "target_entity_uuid": "goblin-uuid",
  "lineage_uuid": "attack-lineage-1",
  "weapon_slot": "MELEE_MAIN",
  "weapon_name": "Longsword",
  "range": {"type": "MELEE", "normal": 5, "long": null},
  "is_long_range": false,
  "is_threatened": false,
  "attack_bonus": null,
  "ac": null,
  "dice_roll": null,
  "attack_outcome": null,
  "damages": null,
  "damage_rolls": null
}
```

At DECLARATION, only the intent is known. Validation runs (range check, LOS). Handlers can cancel here (e.g., Charmed can't attack charmer → CANCEL).

### Phase 2: EXECUTION

Cross-entity modifier propagation happens now:
1. Fighter's `attack_bonus` calls `set_from_target(goblin.ac_bonus)` — pulls in any "affects attackers" modifiers from the Goblin (Blinded → advantage, Prone → advantage if melee ≤5ft)
2. Goblin's `ac_bonus` calls `set_from_target(fighter.attack_bonus)` — pulls in any reverse modifiers

```json
{
  "phase": "execution",
  "attack_bonus": {
    "normalized_score": 5,
    "advantage": "NONE"
  },
  "ac": {
    "normalized_score": 15,
    "advantage": "NONE"
  }
}
```

### Post-EXECUTION: D20 Roll

The d20 is rolled. A `D20RollResultEvent` fires as a child event, allowing handlers (Lucky, Portent) to intercept and replace the roll.

```json
{
  "dice_roll": {
    "results": [17],
    "bonus": 5,
    "total": 22,
    "dice_count": 1,
    "dice_type": 20,
    "advantage": null
  },
  "attack_outcome": "HIT"
}
```

With advantage, you'd see:
```json
{
  "dice_roll": {
    "results": [17],
    "bonus": 5,
    "total": 22,
    "all_rolls": [17, 8],
    "advantage": "advantage"
  }
}
```

### Phase 3: EFFECT

On hit, damage is rolled. A `DamageRollResultEvent` fires as a child, allowing handlers (Great Weapon Fighting, Savage Attacker) to reroll damage dice.

```json
{
  "phase": "effect",
  "damages": [
    {"damage_type": "slashing", "dice_count": 1, "dice_type": 8, "bonus": 3}
  ],
  "damage_rolls": [
    {"results": [6], "bonus": 3, "total": 9, "dice_count": 1, "dice_type": 8}
  ]
}
```

Then damage is applied: `target.receive_damage()` fires a **child** `TakeDamageEvent`:

```json
{
  "event_type": "take_damage",
  "phase": "effect",
  "target_entity_uuid": "goblin-uuid",
  "parent_event": "attack-event-effect-uuid",
  "total_damage": 9,
  "final_damage": null,
  "damages": [{"damage_type": "slashing", "dice_count": 1, "dice_type": 8, "bonus": 3}]
}
```

If the Goblin has resistance to slashing, `total_damage` would be 4 (halved). If a handler like Relentless Rage modifies damage, `final_damage` is set.

### Phase 3b: Death Check

If Goblin HP ≤ 0 (7 - 9 = -2), a **grandchild** `DeathEvent` fires:

```json
{
  "event_type": "death",
  "phase": "effect",
  "source_entity_uuid": "goblin-uuid",
  "parent_event": "take-damage-event-uuid"
}
```

Plus a `ConditionApplicationEvent` for the "Dead" condition.

### Phase 4: COMPLETION

The attack event reaches COMPLETION. No handlers fire. The combat log is generated internally (but not serialized on the event). The event now carries all final data:

```json
{
  "phase": "completion",
  "weapon_slot": "MELEE_MAIN",
  "weapon_name": "Longsword",
  "dice_roll": {"results": [17], "bonus": 5, "total": 22},
  "attack_outcome": "HIT",
  "damages": [{"damage_type": "slashing", "dice_count": 1, "dice_type": 8, "bonus": 3}],
  "damage_rolls": [{"results": [6], "bonus": 3, "total": 9}]
}
```

### What the Client Can Extract

From the COMPLETION-phase AttackEvent alone:
- **Who attacked whom**: `source_entity_uuid`, `target_entity_uuid`
- **Weapon**: `weapon_name`, `weapon_slot`
- **Attack roll**: `dice_roll.total` (22) vs implicit AC
- **Outcome**: `attack_outcome` ("HIT")
- **Damage**: `damage_rolls[0].total` (9), `damages[0].damage_type` ("slashing")

From the child TakeDamageEvent:
- **Actual damage taken**: `get_effective_damage()` → `total_damage` or `final_damage`
- **Target HP change**: Apply this to tracked HP

From the grandchild DeathEvent:
- **Death**: `event_type == "death"`, entity UUID

### Ranged Attack Variant

Same flow, but at DECLARATION:
- `is_long_range = true` if target beyond normal range → disadvantage applied
- `is_threatened = true` if hostile within 5ft of ranged attacker → disadvantage applied

### Critical Hit Variant

At post-EXECUTION:
- `attack_outcome = "CRIT"` — natural 20 or below crit threshold
- At EFFECT: damage dice are **doubled** (roll twice as many dice)
- `damage_rolls` reflects the doubled dice

---

## 5. Spell Event Flows

### Attack Spell (Fire Bolt)

A `SpellEvent` with attack fields populated. Same flow as a weapon attack but using spell stats:

```
DECLARATION:
  spell_level: 0 (cantrip)
  cast_at_level: 0
  spell_school: "evocation"
  verbal: true
  range: {type: "RANGED", normal: 120, long: null}

EXECUTION:
  attack_bonus: {normalized_score: 5}  (proficiency + spellcasting modifier)
  ac: {normalized_score: 15}

Post-EXECUTION:
  dice_roll: {results: [14], bonus: 5, total: 19}
  attack_outcome: "HIT"

EFFECT:
  damages: [{damage_type: "fire", dice_count: 1, dice_type: 10, bonus: 0}]
  damage_rolls: [{results: [7], bonus: 0, total: 7}]
  → Child TakeDamageEvent with total_damage: 7
```

**Cantrip scaling**: At caster_level 5, Fire Bolt rolls 2d10 instead of 1d10. At 11, 3d10. At 17, 4d10. The `damages` and `damage_rolls` fields reflect the scaled dice.

### Save-Based Spell (Hold Person)

Save spells use the save fields instead of attack fields:

```
DECLARATION:
  spell_level: 2
  cast_at_level: 2
  spell_school: "enchantment"
  concentration: true

EXECUTION:
  save_ability: "wisdom"
  save_dc: 13

EFFECT:
  → Child SavingThrowEvent fires:
    ability_name: "wisdom"
    dc: 13
    roll_result: {results: [8], bonus: 1, total: 9}

  save_success: false (9 < 13)
  save_roll: {results: [8], bonus: 1, total: 9}

  → Child ConditionApplicationEvent: HoldPersonEffect on target
    → Sub-condition: Paralyzed

  → ConditionApplicationEvent: Concentrating on caster
    → linked_conditions: [(target_uuid, hold_person_effect_uuid)]
```

### Concentration System Events

When a concentrating caster takes damage:

```
1. TakeDamageEvent fires on caster
2. Concentration handler fires at EFFECT phase
3. CON save: DC = max(10, damage / 2)
4. SavingThrowEvent fires as child:
   - ability_name: "constitution"
   - dc: calculated DC
   - roll_result: {results: [7], bonus: 2, total: 9}

5. If save FAILS:
   → ConditionRemovalEvent: Concentrating removed from caster
   → ConditionRemovalEvent: HoldPersonEffect removed from target (via linked_conditions)
   → ConditionRemovalEvent: Paralyzed removed from target (via sub_conditions)
```

The client sees three `ConditionRemovalEvent`s in sequence — the full cleanup chain.

### Spell Slot Consumption

Leveled spells include a spell slot cost in `ActionEvent.costs`:

```json
{
  "costs": [
    {"cost_type": "actions", "amount": 1},
    {"cost_type": "spell_slot", "level": 2, "amount": 1}
  ]
}
```

---

## 6. AoE & Multi-Target Event Flow

### The Convolution Pattern

For `POSITION_AOE` (Fireball) and `MULTI_ENTITY` (Magic Missile) actions, the engine creates:
- **1 parent event** — represents the overall spell
- **N child events** — one per target, each with its own `lineage_uuid`

This allows each target to have independent saves, damage rolls, and handler interactions.

### Fireball Example (3 Targets)

```
Parent SpellEvent (DECLARATION)
  lineage_uuid: "fireball-parent"
  event_type: "attack"  (SpellEvent)
  spell_level: 3
  cast_at_level: 3
  aoe_position: [10, 5]

Parent SpellEvent (EXECUTION)
  save_dc: 15
  save_ability: "dexterity"

─── Per-Target Loop ───

  Child 1: Skeleton A
    lineage_uuid: "child-1"  (NEW, independent)
    parent_event: "fireball-parent-execution-uuid"

    SavingThrowEvent:
      dc: 15, ability: "dexterity"
      roll_result: {results: [8], bonus: 1, total: 9}  → FAIL

    SpellEvent (EFFECT):
      save_success: false
      damages: [{damage_type: "fire", dice_count: 8, dice_type: 6}]
      damage_rolls: [{results: [3,5,2,6,4,1,5,3], total: 29}]

    TakeDamageEvent: total_damage: 29

  Child 2: Skeleton B
    lineage_uuid: "child-2"  (NEW, independent)
    parent_event: "fireball-parent-execution-uuid"

    SavingThrowEvent:
      dc: 15, ability: "dexterity"
      roll_result: {results: [16], bonus: 2, total: 18}  → SAVE

    SpellEvent (EFFECT):
      save_success: true
      damages: [{damage_type: "fire", dice_count: 8, dice_type: 6}]
      damage_rolls: [{results: [3,5,2,6,4,1,5,3], total: 29}]
      → Damage halved on save: TakeDamageEvent total_damage: 14

    TakeDamageEvent: total_damage: 14

  Child 3: Goblin
    lineage_uuid: "child-3"
    parent_event: "fireball-parent-execution-uuid"
    ... (similar pattern)

─── End Per-Target Loop ───

Parent SpellEvent (EFFECT)
  total_targets: 3
  total_damage: 72  (sum of all targets)

Parent SpellEvent (COMPLETION)
  → Combat log: MULTI_ENTITY_ACTION with 3 SPELL_SAVE sub_entries
```

### Key Details

- **Independent lineage_uuid per target**: Each target's save, damage, and reactions are tracked independently
- **Parent aggregates at EFFECT**: `total_targets` and `total_damage` summarize the spell's impact
- **_finalize_aoe()**: Called after per-target loop for zone spells — sets up SpatialHandlers on affected tiles
- **Combat log hierarchy**: Parent MULTI_ENTITY_ACTION entry has per-target sub_entries

### Magic Missile Variant (MULTI_ENTITY)

Magic Missile uses `MULTI_ENTITY` target type instead of `POSITION_AOE`:
- `num_projectiles = 3` (at base level)
- `allow_same_target = true` (all darts can hit same target)
- `extra_target_uuids` carries additional targets beyond primary
- Each dart is a child event with auto-hit damage (no attack roll, no save)
- Per-dart child event_type is `"attack"` with `attack_outcome = "HIT"` (auto)

---

## 7. Movement Event Flow

This section traces how a 30-foot movement (6 cells) generates events.

### The Step-by-Step Loop

Movement is NOT atomic. The entity moves one cell at a time, and at each step, handlers can react (opportunity attacks, zone damage, interceptions).

```
Move._apply() with path = [(0,0), (1,0), (2,0), (3,0), (4,0), (5,0), (6,0)]

MovementEvent (DECLARATION)
  start_position: [0, 0]
  end_position: [6, 0]
  path: [[0,0], [1,0], [2,0], [3,0], [4,0], [5,0], [6,0]]

MovementEvent (EXECUTION)
  → Costs checked, movement begins

MovementEvent (EFFECT)
  → Step-by-step loop starts:

  ┌─────────────────────────────────────────────────────┐
  │ STEP 1: (0,0) → (1,0)                              │
  │                                                     │
  │ 1. Check walkability of (1,0) ✓                     │
  │ 2. Calculate cost: walking_cost=1 × 5 = 5 feet      │
  │ 3. Check movement remaining: 30 ≥ 5 ✓               │
  │ 4. Fire StepMovementEvent:                          │
  │      from_position: [0,0]                           │
  │      to_position: [1,0]                             │
  │      path_index: 1                                  │
  │      movement_cost: 5.0                             │
  │      → OA handlers check: entity leaving threat?    │
  │      → If OA fires: AttackEvent as child            │
  │ 5. Re-check walkability (handler may have blocked)  │
  │ 6. Move entity: GridMap.move_entity()               │
  │      → SPATIAL_ENTITY_LEFT @ (0,0)                  │
  │      → SPATIAL_ENTITY_ENTERED @ (1,0)               │
  │        → Zone handlers fire (Spike Growth damage?)  │
  │ 7. Step → COMPLETION                                │
  │ 8. Death check (zone damage may have killed)        │
  │ 9. Consume 5 feet of movement (25 remaining)        │
  └─────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────┐
  │ STEP 2: (1,0) → (2,0)                              │
  │ ... (same pattern)                                  │
  │ If difficult terrain: movement_cost = 10.0          │
  └─────────────────────────────────────────────────────┘

  ... (steps 3-6) ...

  Finally (even if movement interrupted):
    entity.update_entity_senses()  → Full Dijkstra + FOV recompute

MovementEvent (COMPLETION)
  start_position: [0, 0]
  end_position: [6, 0]   (or earlier if interrupted)
  → Combat log generated with all child events
```

### Opportunity Attack During Movement

When a step leaves an enemy's threat range:

```
Step 3: (2,0) → (3,0)

  StepMovementEvent fires at EFFECT phase
    → OA handler detects: mover was adjacent to Enemy at (2,1), now leaving threat
    → OA handler fires AttackEvent as CHILD of StepMovementEvent:

      AttackEvent (child):
        source_entity_uuid: "enemy-uuid" (the reactor)
        target_entity_uuid: "mover-uuid"
        parent_event: "step-event-uuid"
        weapon_slot: "MELEE_MAIN"
        ... (full attack flow: d20, damage, etc.)

      If OA kills the mover:
        → DeathEvent fires
        → Dead condition applied
        → Back in Move._apply(): death check catches it
        → Movement loop breaks
        → Finally block: senses recompute still runs
```

### Movement Collision

When an invisible entity blocks a cell:

```
Step 4: (3,0) → (4,0)

  1. is_walkable_for((4,0), subjective=True) → True (can't see blocker)
  2. is_walkable_for((4,0), subjective=False) → False (objective: occupied by invisible entity)

  → MOVEMENT_COLLISION event fires:
    position: [4, 0]
    entity_uuid: mover UUID

  → Entity is NOT moved to (4,0)
  → Position (4,0) added to senses.collision_blocked
  → Movement continues to try remaining path (may find alternate route at next senses update)
```

### Forced Movement (Shove, Thunderwave)

```
ForcedMovementEvent:
  start_position: [5, 5]
  end_position: [7, 5]
  direction: [1, 0]  (pushed east)
  intended_distance: 15  (3 cells × 5 feet)
  actual_distance: 10    (hit wall at (8,5))
  blocked_by_obstacle: true
  blocked_by: "Wall"

→ No StepMovementEvent (no OA triggers)
→ Spatial events STILL fire:
  SPATIAL_ENTITY_LEFT @ (5,5)
  SPATIAL_ENTITY_ENTERED @ (7,5)
    → Zone handlers STILL fire (pushed into Spike Growth = damage)
```

---

## 8. Trap & Zone Entry Event Flows

### How Zone Spells Register

When a zone spell (Spike Growth, Web, Spirit Guardians) is cast, its condition's `_apply()` method creates a `SpatialHandler`:

```
SpellAction._apply() → creates zone condition
  → ZoneControlCondition._apply():
    1. Compute affected positions from zone shape/radius
    2. Create zone entry handler (processor callback)
    3. Register with EventQueue:
       EventQueue.add_spatial_handler(
         handler,
         affected_positions,
         EventType.SPATIAL_ENTITY_ENTERED,
         EventPhase.EFFECT
       )
    4. Handler stored in position-indexed registry:
       _spatial_handlers_by_position[(SPATIAL_ENTITY_ENTERED, EFFECT)][position]
```

The handler is now **permanently registered** at those positions until the spell ends (condition removed).

### Zone Entry: Spike Growth

When an entity walks through Spike Growth:

```
Step 3: (4,5) → (5,5) where (5,5) is in Spike Growth zone

1. StepMovementEvent fires at EFFECT
   → No OA (not leaving threat)

2. Entity moves: GridMap.move_entity()
   → SPATIAL_ENTITY_LEFT @ (4,5)
   → SPATIAL_ENTITY_ENTERED @ (5,5) fires through phases:

     DECLARATION → EXECUTION → EFFECT:
       → EventQueue looks up spatial handlers at (SPATIAL_ENTITY_ENTERED, EFFECT, (5,5))
       → Spike Growth handler found (O(1) lookup)
       → Handler processor fires:
         - Checks: is entity the caster? (skip if yes)
         - Rolls 2d4 piercing damage
         - Calls entity.receive_damage()
           → TakeDamageEvent fires as CHILD of SPATIAL_ENTITY_ENTERED:
             total_damage: 5
             damages: [{damage_type: "piercing"}]

     COMPLETION:
       → SpatialSensesCallback processes (visibility updates)
       → Combat log collects child TakeDamageEvent

3. Back in Move._apply():
   → Death check: if entity has "Dead" condition → break movement loop
   → Otherwise continue to next step
```

### Zone Entry: Web

```
Entity enters Web zone at (3, 7):

SPATIAL_ENTITY_ENTERED @ (3,7) at EFFECT:
  → Web handler fires:
    - SavingThrowEvent (child): DEX save vs spell DC
      dc: 13, ability: "dexterity"
      roll_result: {results: [7], bonus: 1, total: 8}

    - Save FAILS (8 < 13):
      → ConditionApplicationEvent: Restrained applied to entity
        → Speed = 0 (movement stops after this step)
        → Disadvantage on DEX saves and attacks
        → Attackers have advantage
```

### Hidden Traps

Some zone conditions have `condition_stealth_dc` — a DC for detecting the hazard:

```
SpikeTrapCondition on tile (8, 3):
  hazard_filter: ALL
  condition_stealth_dc: 15
```

**Detection**: Only entities with `passive_perception ≥ 15` can see this hazard.

**Pathfinding impact**:
- Entities who CAN detect it: pathfinder avoids this tile (appears in `safe_paths`)
- Entities who CANNOT detect it: pathfinder treats tile as normal (doesn't know it's there)

**Detection event**: When an observer's perception changes (WIS buff, Darkvision gained) and now beats the DC:

```
SpatialSensesCallback._refilter_all_visible_entities():
  → Checks all tiles for hazards
  → If new_passive_perception >= condition_stealth_dc:
    → Generate HAZARD_DETECTED combat log:
      {
        entry_type: "hazard_detected",
        data: {
          observer_name: "Fighter",
          hazard_name: "Spike Trap",
          position: [8, 3],
          passive_perception: 16,
          stealth_dc: 15
        }
      }
```

### Hazard Pathfinding

The pathfinder has two modes:

```
Standard path (walk_in_danger=True):
  Shortest route, ignores hazards
  Stored in: senses.paths

Safe path (walk_in_danger=False):
  Avoids hazardous tiles (extra cost or detour)
  Stored in: senses.safe_paths

Available action response includes both:
  is_path_hazardous: true       ← normal path crosses hazard
  path_cost: 15                 ← normal path cost
  safe_path_cost: 25            ← safe path cost (longer)
  safe_path: [[0,0], [0,1], ...]← safe path cells
```

The `prefer_safe` flag on `ExecuteByIndexRequest` controls which path is used.

---

## 9. Reactive Sensory Cascades

The sensory system is the most complex reactive chain in the engine. It determines what each entity can see, detect, and path to — and updates incrementally as the game state changes.

### SpatialSensesCallback

Every entity has a `SpatialSensesCallback` registered as a passive event callback. It fires on **ALL events** but only processes:
- **Spatial events** (8 types) at **COMPLETION phase**
- **CONDITION_APPLICATION / CONDITION_REMOVAL** on the owning entity (perception changes)
- **DEATH** events (remove dead entity from visible dict)

### Three Processing Paths

#### Path A: Hint-Based Incremental Update

Most spatial events carry a `SensesUpdateHint`. The callback reads it and applies targeted updates:

```
Hint Processing Priority:

1. requires_fov = true?
   → Full FOV recompute (shadowcast from entity position)
   → Refilter all entities and objects at visible positions
   → Mark _paths_dirty = true

2. light_changed_positions not empty?
   → For each position in overlap with entity's subscribed cells:
     → _update_visibility_at(position)
       → Is tile now visible? (light ≥ threshold for entity's senses)
       → _refilter_entities_at(position)
         → For each entity at position: perceivability check
         → Generates ENTITY_SPOTTED logs for newly visible enemies
       → _refilter_objects_at(position)
         → For each object at position: visibility check

3. entity_entered?
   → _try_add_visible_entity(uuid, position)
     → Check: is position in entity's FOV?
     → Check: is target perceivable? (not hidden/invisible, or observer can bypass)
     → If yes: add to senses.entities dict
     → Generates ENTITY_SPOTTED log if enemy

4. entity_left?
   → Remove from senses.entities dict (O(1))

5. perceivability_entity?
   → _recheck_entity_perceivability(uuid)
     → Re-evaluate: can observer see this entity now?
     → If newly visible: add to senses.entities, generate ENTITY_SPOTTED
     → If newly hidden: remove from senses.entities

6. object_placed / object_removed?
   → O(1) dict add/remove on senses.objects

7. requires_paths = true?
   → Mark _paths_dirty = true (defer Dijkstra)
```

**Key design**: Callbacks NEVER run Dijkstra. They only set `_paths_dirty = true`. Full Dijkstra runs only at:
- Turn start (`Encounter.start_turn()`)
- Movement end (`Move._apply()` finally block)

#### Path B: Self-Movement

When the owning entity moves:
```
entity_entered with entity_uuid == owner_uuid:
  → update_visibility_func()  (FOV recompute for new position)
  → Mark _paths_dirty = true
```

#### Path C: Owner Perception Change

When a condition on the owning entity changes its perception capabilities:

```
CONDITION_APPLICATION on self (e.g., WIS buff, Darkvision gained):
  → _handle_own_perception_change():
    → Compare snapshots:
      - _last_passive_perception vs current passive_perception
      - _last_sense_modes_hash vs current sense modes hash

    → If sense modes changed (Darkvision gained/lost):
      → update_visibility_func()  (FOV recompute — light filtering changes)
      → Mark _paths_dirty = true

    → If only passive perception changed:
      → _refilter_all_visible_entities(old_pp, new_pp)
        → For each visible position: re-check all entities
        → If new_pp > old_pp:
          → Entities with stealth_dc between old and new PP become visible
          → Generate ENTITY_SPOTTED logs
        → If new_pp < old_pp:
          → Entities with stealth_dc above new PP become invisible
      → _log_newly_detected_hazards(old_pp, new_pp)
        → Check tile conditions for stealth_dc between old and new PP
        → Generate HAZARD_DETECTED logs
```

### Cascade Scenario 1: Torch Lit in Dark Room

```
Action: Player lights a torch (light source added at position (5,5))

1. GridMap.add_light_source(position=(5,5), bright_radius=20ft, dim_radius=40ft)

2. _apply_light_source(): Compute affected tiles
   → Tiles within 20ft get BRIGHT_LIGHT illumination
   → Tiles within 40ft get DIM_LIGHT illumination
   → For each tile: tile.add_illumination(source_uuid, level)
   → Collect changed_positions (tiles that actually changed light level)

3. _fire_light_batch_events(changed_positions):

   Tier 1 — Positions with entities (need reveal handlers):
     For position (7,5) which has a Hidden Goblin:
       → SpatialChangeEvent.light_changed(position=(7,5))
       → Full lifecycle: DECLARATION → EXECUTION → EFFECT → COMPLETION
       → At EFFECT: Hidden reveal handler checks if tile is now VERY_BRIGHT
         → If VERY_BRIGHT: remove Hidden condition → Goblin revealed
         → If just BRIGHT: Hidden stays (not bright enough to auto-reveal)

   Tier 2 — Single batch event for senses refresh:
     → SpatialChangeEvent.light_changed(batch_hint):
       light_changed_positions: {(3,5), (4,5), (5,5), (6,5), (7,5), ...}
     → Register at COMPLETION phase only

4. SpatialSensesCallback processes Tier 2 event:
   → For each position in light_changed_positions ∩ subscribed_cells:
     → _update_visibility_at(position):
       → Tile now has BRIGHT_LIGHT (was DARKNESS)
       → senses.visible[(7,5)] = true (was false)
       → _refilter_entities_at((7,5)):
         → Goblin is at (7,5)
         → Was not in senses.entities (dark, couldn't see)
         → Now: check perceivability
           → If Goblin is Hidden with stealth_dc=14 and observer PP=12: still not perceivable
           → If Goblin is NOT Hidden: perceivable → add to senses.entities
         → Generate ENTITY_SPOTTED combat log if newly visible

Result: Observer now sees the lit area. Hidden enemies may or may not be spotted depending on perception.
```

### Cascade Scenario 2: Entity Hides

```
Action: Rogue uses Hide action (Stealth check result: 17)

1. Hide._apply():
   → Roll Stealth check: d20 + DEX + Proficiency = 17
   → Apply Hidden condition with stealth_dc = 17

2. Hidden._apply():
   → entity.set_stealth_dc(17)
   → BaseBlock._notify_perceivability_changed()

3. _notify_perceivability_changed():
   → SpatialChangeEvent.perceivability_changed(position=rogue_pos, entity_uuid=rogue_uuid)
   → Hint: perceivability_entity = rogue_uuid
   → Full lifecycle: DECLARATION → EXECUTION → EFFECT → COMPLETION

4. At COMPLETION, each observer's SpatialSensesCallback fires:
   → hint.perceivability_entity = rogue_uuid
   → _recheck_entity_perceivability(rogue_uuid):
     → Observer PP = 14, stealth_dc = 17
     → 14 < 17 → NOT perceivable
     → Remove rogue from senses.entities

   → Another observer PP = 18, stealth_dc = 17
     → 18 ≥ 17 → STILL perceivable
     → Rogue stays in senses.entities (this observer sees through the hide)

Result: Some observers lose sight of the Rogue, others don't. Each observer's senses update independently.
```

### Cascade Scenario 3: Invisible Entity Attacks

```
State: Rogue has InvisibilityEffect condition (is_invisible = true)

Action: Rogue attacks Goblin

1. AttackEvent fires (DECLARATION → EXECUTION → EFFECT)
   → At EFFECT phase, invisibility reveal handler fires:
     → event.event_type == ATTACK and is_last == true
     → Check: lineage_uuid != creation_lineage_uuid (yes, attack ≠ invisibility spell)
     → Remove condition: entity.remove_condition("Invisible", parent_event=attack_event)

2. InvisibilityEffect removed:
   → entity.set_invisible(false)
   → _notify_perceivability_changed()
   → SPATIAL_PERCEIVABILITY_CHANGED event fires
   → Hint: perceivability_entity = rogue_uuid

3. All observers' SpatialSensesCallback fire:
   → _recheck_entity_perceivability(rogue_uuid):
     → is_invisible = false now
     → Standard visibility check (light + LOS)
     → If visible: add to senses.entities
     → Generate ENTITY_SPOTTED combat log:
       "Fighter spots Rogue at (5, 3)!"

4. Attack continues at EFFECT:
   → Damage applied to Goblin
   → AttackEvent → COMPLETION

Result: Rogue is revealed, attack resolves, all observers updated.
```

### Cascade Scenario 4: Darkness Spell Cast

```
Action: Caster casts Darkness at position (10, 10), 15ft radius sphere

1. Darkness spell creates zone condition on affected tiles
   → For each tile in sphere: tile.add_obscurement(source_uuid, MAGICAL_DARKNESS)
   → Resolved light: MAX(default + illuminations) then MIN(result, MAGICAL_DARKNESS) = MAGICAL_DARKNESS

2. _fire_light_batch_events(affected_positions):

   Tier 1 — Positions with entities:
     → Full lifecycle per position
     → Hidden reveal handler: MAGICAL_DARKNESS ≠ VERY_BRIGHT, no reveal

   Tier 2 — Batch senses refresh:
     → SpatialChangeEvent.light_changed(batch_hint):
       light_changed_positions: {all positions in sphere}
       requires_fov: true  (MAGICAL_DARKNESS blocks vision for non-Truesight/Devil's Sight)

3. Each observer's SpatialSensesCallback:
   → hint.requires_fov = true
   → update_visibility_func():
     → Full FOV recompute (shadowcast)
     → MAGICAL_DARKNESS tiles treated as vision-blocking (like walls)
       Exception: observers with Truesight or Devil's Sight see through
     → senses.visible updated: positions in Darkness zone = false (for normal observers)
   → _refilter based on new visibility:
     → Entities in Darkness zone removed from senses.entities (can't see them)
     → Entities outside zone unaffected
   → Mark _paths_dirty = true

Result: Normal observers can't see into the Darkness zone. Entities with special senses maintain visibility.
```

### The _paths_dirty Pattern

A critical performance optimization. Dijkstra pathfinding is expensive. The sensory cascade **never** runs Dijkstra — it only sets a flag:

```
Spatial event with requires_paths=true:
  → senses._paths_dirty = true
  → NO Dijkstra runs

Flag is cleared (Dijkstra runs) at exactly two points:
  1. Encounter.start_turn() → entity.update_entity_senses()
  2. Move._apply() finally block → entity.update_entity_senses()
```

This means: between turn start and the entity's first movement, paths are fresh. During movement, paths are dirty (updated in the finally block after movement completes). Between movements, the entity's available position targets reflect the most recent recompute.

---

## 10. Client State Reconstruction Guide

### State Trackable from Events

| State | Event(s) | How to Track |
|-------|---------|-------------|
| **Entity position** | `SPATIAL_ENTITY_ENTERED` (at COMPLETION) | Update position dict when `entity_entered` hint fires |
| **Entity HP** | `TakeDamageEvent` (COMPLETION), `HealEvent` (COMPLETION) | Subtract `get_effective_damage()` or add `actual_healing` |
| **Active conditions** | `CONDITION_APPLICATION` (COMPLETION), `CONDITION_REMOVAL` (COMPLETION) | Add/remove condition name from entity's condition list |
| **Entity death** | `DeathEvent` (COMPLETION) | Mark entity as dead |
| **Turn ownership** | `TurnStartEvent` (COMPLETION) | `current_entity_uuid` tells whose turn it is |
| **Round number** | `RoundStartEvent` (COMPLETION) | `round_number` field |
| **Encounter state** | `EncounterStartEvent`, `EncounterEndEvent` | Start/end tracking |
| **Equipment changes** | `WEAPON_EQUIP`, `ARMOR_EQUIP`, etc. (COMPLETION) | Track equipped items per slot |
| **Light level changes** | `SPATIAL_LIGHT_CHANGED` (COMPLETION) | `light_changed_positions` in hint |
| **Entity visibility** | `SPATIAL_PERCEIVABILITY_CHANGED` (COMPLETION) | `perceivability_entity` in hint |
| **Floor objects** | `SPATIAL_OBJECT_PLACED`, `SPATIAL_OBJECT_REMOVED` (COMPLETION) | `object_placed`/`object_removed` in hint |
| **Dice rolls** | On AttackEvent, SpellEvent, SavingThrowEvent | `dice_roll`, `damage_rolls`, `roll_result` fields |
| **Attack outcomes** | AttackEvent (COMPLETION) | `attack_outcome`: HIT/MISS/CRIT/CRIT_MISS |
| **Save outcomes** | SpellEvent (COMPLETION) | `save_success`: true/false |
| **Spell slots** | SpellEvent costs | Decrement from `costs` list |
| **Action economy** | TurnStartEvent (reset), ActionEvent costs | Reset on turn start, decrement per action |

### State NOT Trackable from Events (Requires REST)

| State | Why | REST Endpoint |
|-------|-----|--------------|
| **Initial game state** | Events only carry changes, not absolute state | `GET /state` |
| **Current AC** | Computed from equipment + conditions + modifiers across 6 channels | `GET /entity/{uuid}` |
| **Current attack bonus** | Computed from ability + proficiency + equipment + conditions | Not directly exposed; implied by AttackEvent |
| **Available actions** | Depends on action economy, conditions, range, LOS, targets | `GET /entity/{uuid}/available-actions` |
| **Movement paths** | Dijkstra computation on server (terrain, entity blocking, hazards) | Included in available-actions response |
| **FOV / visible cells** | Shadowcast computation on server | `GET /visibility` |
| **Condition duration** | Duration countdown not serialized on events | `GET /entity/{uuid}` (condition_details) |
| **Modifier breakdowns** | 6-channel system internals not on events | Combat log `data` field has breakdowns |

### Recommended Architecture

```
┌─────────────────────────────────────────────┐
│                  Frontend                    │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Entity   │  │ Grid     │  │ Turn     │  │
│  │ State    │  │ State    │  │ State    │  │
│  │ (HP,pos, │  │ (tiles,  │  │ (whose   │  │
│  │  conds)  │  │  light)  │  │  turn)   │  │
│  └────▲─────┘  └────▲─────┘  └────▲─────┘  │
│       │              │              │        │
│  ┌────┴──────────────┴──────────────┴────┐  │
│  │     Event Cursor Poller (~400ms)      │  │
│  │  GET /events?since=N&phase=completion │  │
│  │  Exactly-once: cursor = total         │  │
│  └────────────────▲──────────────────────┘  │
│                   │                          │
│  ┌────────────────┴──────────────────────┐  │
│  │         REST Layer                     │  │
│  │  (bootstrap, ping, available-actions,  │  │
│  │   visibility, resync)                  │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
                    │
                REST API
                    │
┌───────────────────┴─────────────────────────┐
│              Backend Server                  │
└─────────────────────────────────────────────┘
```

**Event-driven primary**: Position, HP, conditions, turns tracked from cursor-based event polling (`GET /events?since=<cursor>&phase=completion`). Exactly-once delivery — store `total` from each response as the next cursor. No UUID-based deduplication needed.
**REST fallback**: Available actions queried when it's your turn. On errors or unknown entities in events, `GET /state` to resync + reset cursor from `GET /events` response `total`.

### Phase Trust Rule

**Only act on COMPLETION-phase events for state updates.**

Events at DECLARATION, EXECUTION, and EFFECT are in-flight — handlers can still modify or cancel them. A client that updates state on EFFECT-phase events might apply damage that gets cancelled by a reaction.

Exception: you might want to show DECLARATION events as "intent" animations (e.g., showing the attack arc before the roll resolves), but don't commit state changes until COMPLETION.

### Lineage Grouping

Use `lineage_uuid` to group related events:

```
All events with lineage_uuid "abc-123" belong to the same action:
  - AttackEvent at DECLARATION (intent)
  - AttackEvent at EXECUTION (rolling)
  - AttackEvent at EFFECT (damage)
  - AttackEvent at COMPLETION (final)

Child events (TakeDamageEvent, DeathEvent) have DIFFERENT lineage_uuids
but share parent_event pointing to the attack.
```

For multi-target spells, each target's child events have their own lineage_uuid. Group by `parent_event` to reconstruct the full spell.

---

## 11. Event Phase Timing Reference

### When Fields Are Populated

| Event Type | Field | Phase |
|-----------|-------|-------|
| **AttackEvent** | `range`, `is_long_range`, `is_threatened` | DECLARATION |
| | `attack_bonus`, `ac` | EXECUTION |
| | `dice_roll`, `attack_outcome` | Post-EXECUTION (before EFFECT) |
| | `damages`, `damage_rolls` | EFFECT |
| **SpellEvent** | `spell_level`, `spell_school` | Creation |
| | `save_dc`, `save_ability` | EXECUTION |
| | `save_success`, `save_roll`, `save_bonus` | EFFECT |
| | `damages`, `damage_rolls` | EFFECT |
| **MovementEvent** | `start_position`, `end_position`, `path` | DECLARATION |
| | Step events fire during | EFFECT |
| | Final position (may differ from end_position if interrupted) | COMPLETION |
| **TakeDamageEvent** | `total_damage`, `damages` | EFFECT |
| | `final_damage` (if handler modified) | EFFECT |
| **HealEvent** | `total_healing`, `actual_healing` | EFFECT |
| **SavingThrowEvent** | `ability_name`, `dc` | DECLARATION |
| | `roll_result` | EFFECT |
| **ConditionApplicationEvent** | `condition` (full object) | DECLARATION |
| **ConditionRemovalEvent** | `condition`, `expired` | DECLARATION |
| **SpatialChangeEvent** | `position`, `entity_uuid`, `senses_hint` | DECLARATION |

### Cancel Semantics

When an event is cancelled at any phase:

```
event.canceled = true
event.status_message = "Reason for cancellation"
```

- All subsequent phases are skipped
- The event is stored with `canceled = true`
- Parent events check child cancellation and may adjust behavior
- Example: Charmed entity tries to attack charmer → cancelled at DECLARATION

### Handler Interception Points

| Event Type | Phase | What Handlers Do |
|-----------|-------|-----------------|
| **ATTACK** | DECLARATION | Charmed → cancel if target is charmer |
| | EXECUTION | Shield spell → +5 AC (modifies ac) |
| | EFFECT | Uncanny Dodge → halve damage |
| **MOVEMENT** | EFFECT (per step) | Opportunity Attack → attack on leave |
| | EFFECT (per step) | Sentinel → stop movement on OA hit |
| **TAKE_DAMAGE** | EFFECT | Relentless Rage → survive at 1 HP |
| | EFFECT | Concentration → force CON save |
| **D20_ROLL_RESULT** | EFFECT | Lucky → reroll d20 |
| | EFFECT | Portent → replace d20 with predetermined roll |
| **DAMAGE_ROLL_RESULT** | EFFECT | Great Weapon Fighting → reroll 1s and 2s |
| | EFFECT | Savage Attacker → reroll all damage dice |
| **CONDITION_APPLICATION** | DECLARATION | Immunity check → cancel if immune |
| **SAVING_THROW** | EFFECT | Indomitable → reroll failed save |
| **CAST_SPELL** | EFFECT | Hidden/Invisible reveal → remove condition |
| **BASE_ACTION** | EFFECT | Hidden reveal → remove if non-whitelisted action |

### Non-Revealing Actions

These actions do NOT break Hidden or Invisible:

```
"Dash", "Dodge", "Disengage", "Hide", "Stand Up", "Drop Prone"
```

All other actions trigger the reveal handler check.
