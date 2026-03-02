# Backend Reference — D&D 5e Combat Engine

> **Purpose**: This document is a complete, self-contained reference for frontend developers building a UI for the D&D 5e combat engine. You should be able to read this single document and fully understand the backend without looking at the Python source code.
>
> **Scope**: REST API + polling. WebSocket coverage is omitted (not currently working). Focus is on what data the backend exposes, how systems interact, and what every API response field means.

---

## Table of Contents

1. [Overview & Core Concepts](#1-overview--core-concepts)
2. [Entity Model](#2-entity-model)
3. [The Event System](#3-the-event-system)
4. [The ModifiableValue System](#4-the-modifiablevalue-system)
5. [The Condition System](#5-the-condition-system)
6. [The Action System](#6-the-action-system)
7. [Available Actions — What the Frontend Displays](#7-available-actions--what-the-frontend-displays)
8. [Senses & Reactive Updates](#8-senses--reactive-updates)
9. [The Combat Log System](#9-the-combat-log-system)
10. [The Grid & Spatial System](#10-the-grid--spatial-system)
11. [REST API Reference](#11-rest-api-reference)
12. [Encounter & Turn Flow](#12-encounter--turn-flow)
13. [API Data Models](#13-api-data-models)

---

## 1. Overview & Core Concepts

### What This Engine Is

A D&D 5e turn-based combat engine. It models combat encounters: entities on a grid, taking turns to move, attack, cast spells, and use abilities. Everything that happens in the game — damage dealt, conditions applied, movement — flows through an event system.

### Core Architecture

The engine is built on four pillars:

1. **Event-Driven State Changes** — All game state changes flow through events. An attack creates an `ATTACK` event that progresses through phases (DECLARATION → EXECUTION → EFFECT → COMPLETION). Handlers can react to, modify, or cancel events at each phase.

2. **Component-Based Entities** — An `Entity` (a character or monster) is composed of specialized blocks: `Health`, `Equipment`, `ActionEconomy`, `Senses`, etc. Each block owns its own state and modifiers.

3. **Global Registries** — Every game object has a UUID. Objects are tracked in:
   - `BaseObject._registry` — All objects by UUID (conditions, modifiers, handlers, etc.)
   - `Entity._entity_registry` — All entities by UUID
   - `Entity._entity_by_position` — Entities indexed by grid position

4. **The Grid** — A 2D grid of tiles. Each tile is a `(x, y)` position. 1 grid cell = 5 feet. Tiles can be walkable (Floor), blocking (Wall), or special (Water). The grid tracks entity positions, object positions (items on the floor), and light sources.

### Key Identifiers

Everything is identified by UUID (v4, string format: `"550e8400-e29b-41d4-a716-446655440000"`). The API serializes UUIDs as strings. Positions are `[x, y]` integer arrays.

---

## 2. Entity Model

An entity represents any creature on the battlefield — a player character, monster, or NPC.

### Entity Composition

An entity is built from specialized blocks, each managing a domain of game state:

| Block | Purpose | Key Data |
|-------|---------|----------|
| `ability_scores` | STR, DEX, CON, INT, WIS, CHA | Each has `score` (raw value) and `modifier` (derived: `(score - 10) / 2`) |
| `health` | Hit points, damage, resistances | Current HP, max HP, temp HP, damage taken, resistances/immunities |
| `equipment` | Weapons, armor, shield, AC | Equipped items in slots, attack bonuses, damage bonuses, AC computation |
| `action_economy` | Actions per turn | Actions, bonus actions, reactions, movement (feet), spell slots, custom resources |
| `senses` | Vision and awareness | Visible cells, visible entities, movement paths, sense modes (Darkvision, etc.) |
| `inventory` | Item storage | Items carried but not equipped |
| `spellcasting` | Spell stats | Spell attack bonus, spell save DC, spellcasting ability |
| `skill_set` | 18 D&D 5e skills | Each skill linked to an ability, proficiency flag |
| `saving_throws` | 6 ability saves | Each save linked to an ability, proficiency flag |
| `proficiency_bonus` | Proficiency bonus | Scales with level (typically +2 to +6) |

### Key Entity Properties

| Property | Type | Description |
|----------|------|-------------|
| `uuid` | string | Unique identifier |
| `name` | string | Display name |
| `position` | `[x, y]` | Current grid position |
| `faction` | string or null | Faction identifier. `null` = enemy to everyone |
| `has_hp` | bool | True if HP > 0 (alive) |
| `is_active` | bool | True if functional (alive, not destroyed) |
| `is_my_turn` | bool | True when this entity's turn is active in the encounter |
| `weight` | int | Weight in pounds (default 150) |
| `size` | string | "Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan" |
| `creature_type` | string | "humanoid", "undead", "beast", etc. |
| `is_spellcaster` | bool | True if entity has spell slots or spellcasting block |

### Faction System

- `faction = null` → Enemy to **everyone** (including other null-faction entities)
- Same faction string → Allies
- Different faction string → Enemies
- The encounter ends when only one faction has living members

### HP and Death

- `get_hp()` returns current HP (max HP minus damage taken, plus temp HP effects)
- When HP drops to 0, entity dies. A `Dead` condition is applied.
- Dead entities remain on the grid but can't act. They're tracked as `is_dead: true` in API responses.

### Damage Resistances

The `Health` block tracks resistances per damage type:
- **Resistance** — Half damage from that type (multiplier: 0.5)
- **Immunity** — Zero damage from that type (multiplier: 0.0)
- **Vulnerability** — Double damage from that type (multiplier: 2.0)

Damage types: Acid, Bludgeoning, Cold, Fire, Force, Lightning, Necrotic, Piercing, Poison, Psychic, Radiant, Slashing, Thunder.

### Equipment Slots

Entities have these equipment slots:

**Weapon Slots**: `MELEE_MAIN`, `MELEE_OFF` (can hold shield), `RANGED_MAIN`, `RANGED_OFF`

**Body Slots**: `HELMET`, `BODY_ARMOR`, `GAUNTLETS`, `BOOTS`, `CLOAK`, `AMULET`

**Ring Slots**: `RING_LEFT`, `RING_RIGHT`

---

## 3. The Event System

The event system is the backbone of the engine. Every game state change — attacks, movement, damage, conditions — flows through events. This allows handlers (passive abilities, reactions, zone effects) to react to, modify, or cancel any game action.

### Event Lifecycle

Every event progresses through phases:

```
DECLARATION → EXECUTION → EFFECT → COMPLETION
                                  ↘ (or CANCEL)
```

| Phase | Purpose | What Happens |
|-------|---------|--------------|
| `DECLARATION` | Announcing intent | "I want to attack this target." Handlers can cancel here. |
| `EXECUTION` | Action begins | Costs are committed. Dice are rolled. |
| `EFFECT` | Effects applied | Damage applied. Conditions added. Last chance for reactions. |
| `COMPLETION` | Finished | Event complete. **No handlers fire.** Combat log generated. |
| `CANCEL` | Aborted | Event was cancelled by a handler. No effects applied. |

**Critical detail**: The COMPLETION phase deliberately skips all EventHandlers. This separates the causal chain (DECLARATION → EFFECT) from observation (COMPLETION). The combat log callback fires at COMPLETION — it's purely observational.

### Event Types

| EventType | Triggered By |
|-----------|-------------|
| `ATTACK` | Attack action (weapon or spell attack roll) |
| `MOVEMENT` | Move action (walking with terrain costs) |
| `STEP_MOVEMENT` | Each individual cell transition during movement (triggers opportunity attacks) |
| `FORCED_MOVEMENT` | Push/pull/teleport (does NOT trigger opportunity attacks) |
| `TAKE_DAMAGE` | Damage applied to entity |
| `INFLICT_DAMAGE` | Damage dealt by entity (source-side event) |
| `SAVING_THROW` | Saving throw requested |
| `SKILL_CHECK` | Skill check (e.g., Athletics contest for Shove) |
| `CAST_SPELL` | Spell cast (triggers Hidden/Invisible reveal) |
| `BASE_ACTION` | Any action execution (triggers reveal for non-whitelisted actions) |
| `CONDITION_APPLICATION` | Condition added to entity |
| `CONDITION_REMOVAL` | Condition removed from entity |
| `D20_ROLL_RESULT` | After d20 rolled, before outcome decided (for Lucky, Portent, etc.) |
| `DAMAGE_ROLL_RESULT` | After damage dice rolled, before applied (for Great Weapon Fighting rerolls) |
| `SPATIAL_ENTITY_ENTERED` | Entity moved into a grid cell (triggers zone effects) |
| `SPATIAL_ENTITY_LEFT` | Entity left a grid cell |
| `SPATIAL_LIGHT_CHANGED` | Tile's light level changed |
| `SPATIAL_PERCEIVABILITY_CHANGED` | Entity's hidden/invisible state changed |
| `TURN_START` / `TURN_END` | Turn begins/ends for an entity |
| `ROUND_START` / `ROUND_END` | Combat round begins/ends |
| `DEATH` | Entity reduced to 0 HP |
| `HEAL` | Entity healed |

### EventHandlers

An `EventHandler` wraps a callback function and a set of trigger conditions. When a matching event fires, the handler's callback executes.

**Trigger matching**: Each handler has trigger conditions specifying:
- `event_type` — Which event type to react to
- `event_phase` — Which phase (DECLARATION, EXECUTION, or EFFECT)
- `event_source_entity_uuid` — Optional: only fire for events from this source
- `event_target_entity_uuid` — Optional: only fire for events targeting this entity

**Handler processing**: The callback receives the event and can:
- Return `None` — No-op, event continues unchanged
- Return the event — Event continues (possibly modified)
- Return a cancelled event — Event is cancelled, no further handlers fire

**Handler toggle**: Every handler has an `enabled: bool` flag. The frontend can toggle handlers on/off via the API (e.g., disabling Shield reaction or opportunity attacks).

### SpatialHandlers (Zone Effects)

`SpatialHandler` is a position-indexed variant for zone effects (Spike Growth, Web, Spirit Guardians). Instead of matching by trigger conditions, it fires at specific grid positions via O(1) lookup.

When an entity enters a cell, the engine checks if any SpatialHandlers are registered at that position. If so, their callbacks fire (applying damage, forcing saves, etc.).

### Event Lineage

Events form parent-child trees. A `lineage_uuid` groups related events. For example:
- A Fireball creates one parent event (MULTI_ENTITY_ACTION)
- Each target gets a child event with its own `lineage_uuid` for independent save/damage tracking
- The parent collects child results into `sub_entries` for the combat log

---

## 4. The ModifiableValue System

`ModifiableValue` is the core building block for any stat that can be modified by conditions, equipment, spells, or cross-entity effects. Attack bonuses, AC, movement speed, skill checks — all use ModifiableValue.

### Why Six Channels?

D&D has effects that affect your own rolls (Poisoned: disadvantage on YOUR attacks) and effects that affect rolls others make against you (Blinded: attackers have advantage against YOU). These must be tracked separately on the target entity, then combined at roll time.

### The Six Channels

#### Four Primary Channels (set by conditions/effects on the entity)

| Channel | When It Applies | Example |
|---------|----------------|---------|
| `self_static` | Always applies to own rolls | Poisoned: disadvantage on attacks |
| `self_contextual` | Conditional, evaluated at runtime | Frightened: disadvantage only when frightener is visible |
| `to_target_static` | Always applies to entities targeting THIS entity | Blinded: attackers have advantage |
| `to_target_contextual` | Conditional for targeting entities | Prone: melee attackers have advantage, ranged have disadvantage |

#### Two Propagation Channels (populated during cross-entity interactions)

| Channel | Populated By | Purpose |
|---------|-------------|---------|
| `from_target_static` | `set_from_target()` copies target's `to_target_static` | Pulling target's always-on modifiers into attacker's roll |
| `from_target_contextual` | `set_from_target()` copies target's `to_target_contextual` | Pulling target's conditional modifiers into attacker's roll |

### How Cross-Entity Propagation Works

When entity A attacks entity B:
1. Entity B's AC has `to_target_static` modifiers (e.g., Blinded → advantage for attackers)
2. Entity A's attack bonus calls `set_from_target(B.ac_bonus)` to pull in those modifiers
3. Now A's attack bonus includes B's "affects attackers" modifiers
4. After the roll, `reset_from_target()` clears the propagation channels

This is why the frontend doesn't need to understand the 6-channel system — the backend handles all propagation automatically. The API exposes computed values (final attack bonus, final AC, etc.).

### Computed Properties

Each ModifiableValue computes final values by aggregating all 6 channels:

| Property | Type | Description |
|----------|------|-------------|
| `normalized_score` | int | Sum of all value modifiers across all channels (clamped by min/max) |
| `advantage` | enum | `ADVANTAGE` if sum > 0, `DISADVANTAGE` if < 0, `NONE` if 0 |
| `critical` | enum | `AUTOCRIT`, `NOCRIT`, or `NONE` |
| `auto_hit` | enum | `AUTOHIT`, `AUTOMISS`, or `NONE` |

**Advantage aggregation**: Each advantage modifier contributes +1 (advantage) or -1 (disadvantage). The sum determines the result: positive = advantage, negative = disadvantage, zero = none. Multiple sources of advantage don't stack — they just ensure the net is positive.

### Modifier Types

| Type | Values | Use Case |
|------|--------|----------|
| `NumericalModifier` | int | Bonuses/penalties (Proficiency +2, Bless +1d4) |
| `AdvantageModifier` | ADVANTAGE (+1) / DISADVANTAGE (-1) | Attack rolls, ability checks |
| `CriticalModifier` | AUTOCRIT / NOCRIT | Paralyzed → auto-crit on melee |
| `AutoHitModifier` | AUTOHIT / AUTOMISS | Charmed → can't attack charmer |
| `ResistanceModifier` | RESISTANCE / VULNERABILITY / IMMUNITY | Damage type resistance |

Each has a **Contextual** variant that takes a callable returning the modifier (or None). Contextual modifiers are evaluated at runtime — e.g., Frightened only applies disadvantage when the frightener is visible.

### Resistance Stacking

- Resistance + Resistance = Resistance (doesn't stack to immunity)
- Resistance + Vulnerability = Neither (they cancel)
- Immunity overrides everything

### Full Attack Roll Example

When entity A attacks entity B with a melee weapon:

```
A's attack bonus (ModifiableValue) aggregates:
├── self_static: [Proficiency +2, STR +3, Magic Weapon +1]
├── self_contextual: [Frightened → disadvantage if frightener visible]
├── from_target_static: [copied from B's AC to_target_static: Blinded → advantage]
├── from_target_contextual: [copied from B's AC to_target_contextual: Prone → advantage if ≤5ft]
└── Final: normalized_score = +6, advantage = ADVANTAGE (from Blinded)

B's AC (ModifiableValue) aggregates:
├── self_static: [Base AC 10, DEX +2, Armor +5, Shield +2]
├── to_target_static: [Blinded → advantage for attackers] ← propagated to A
└── Final: normalized_score = 19

Roll: d20 + 6 vs AC 19
  With advantage: roll twice, take higher
```

---

## 5. The Condition System

Conditions are temporary (or permanent) effects on entities or tiles that modify game state. They range from standard D&D conditions (Blinded, Paralyzed) to spell effects (HoldPersonEffect) to internal bookkeeping (HasAttacked, Concentrating).

### Condition Lifecycle

1. **Creation** — Condition object created with source/target entity UUIDs
2. **Application** — `entity.add_condition(condition)` calls `condition._apply()`:
   - Adds modifiers to ModifiableValues
   - Registers event handlers
   - Creates sub-conditions
   - Returns a 5-tuple tracking everything it created
3. **Active** — Condition modifies game state for its duration
4. **Removal** — `entity.remove_condition(name)` drives cleanup:
   - Removes all modifiers, handlers, sub-conditions
   - Removes linked conditions on other entities
   - Notifies parent if this was a linked child

### The 5-Tuple Return from `_apply()`

Every condition's `_apply()` method returns exactly what it created, for automatic cleanup:

```
(
  modifiers:          [(modifiable_value_uuid, modifier_uuid), ...],  # Modifier pairs
  handler_uuids:      [uuid, ...],                                     # Event handlers
  sub_condition_uuids:[uuid, ...],                                     # Sub-conditions (same entity)
  spatial_handler_uuids: [uuid, ...],                                  # Zone effect handlers
  effect_event:       Event or None                                    # The EFFECT phase event
)
```

### Condition Categories

| Category | Purpose | Examples |
|----------|---------|---------|
| `CONDITION` | Real D&D conditions | Blinded, Paralyzed, Prone, Grappled |
| `STATUS` | Turn-scoped or spell effects | Dashing, Dodging, Concentrating |
| `INTERNAL` | Engine bookkeeping | HasAttacked, ExtraAttacksGranted |

The API exposes `condition_details` with both `name` and `category` for each active condition, so the frontend can filter display (e.g., show CONDITION and STATUS but hide INTERNAL).

### Condition Relationships

#### Sub-conditions (Same Entity)

A parent condition can include child conditions on the **same entity**. Example: Paralyzed includes Incapacitated as a sub-condition. When Paralyzed is removed, Incapacitated is automatically removed too.

#### Linked Conditions (Cross-Entity)

A condition on one entity can link to conditions on **other entities**. Example: when a caster concentrates on Hold Person:

```
Caster: Concentrating (spell_name="Hold Person")
    │ linked_conditions
    └──► Target: HoldPersonEffect
                │ sub_conditions
                └──► Paralyzed
```

#### Cleanup Chains

**Forward (parent → child)**: Concentration breaks → removes HoldPersonEffect via linked_conditions → removes Paralyzed as sub-condition.

**Reverse (child → parent)**: Target saves against Hold Person → HoldPersonEffect removed → `parent_link` notification → `child_removal_policy="last"` → if no more linked children, Concentrating auto-removed from caster.

**`child_removal_policy`** on parent condition:
- `"none"` — No notification when child removed (default)
- `"any"` — Remove parent when ANY child removed (cascading)
- `"last"` — Remove parent when LAST child removed (used by Concentrating)

### Concentration System

- Only one concentration spell active at a time
- Casting a new concentration spell ends the previous one
- Taking damage forces a CON save: DC = max(10, damage / 2)
- Breaking concentration removes all linked spell effects on all targets
- A `DropConcentration` action (free, 0 cost) allows voluntary end

### Duration System

Conditions have a `Duration` object:

| Duration Type | Behavior |
|--------------|----------|
| `ROUNDS` | Counts down each turn. Auto-removed when expired. |
| `PERMANENT` | Never expires (removed explicitly) |
| `UNTIL_LONG_REST` | Removed on long rest |
| `ON_CONDITION` | Callable evaluated each turn; removed when returns True |

### Standard D&D Conditions

| Condition | Key Effects |
|-----------|------------|
| **Blinded** | Can't see; disadvantage on own attacks; attackers have advantage |
| **Charmed** | Can't attack charmer; charmer has advantage on social checks |
| **Deafened** | Can't hear |
| **Frightened** | Disadvantage on ability checks and attacks while frightener is visible |
| **Grappled** | Speed = 0; can escape with Athletics/Acrobatics check |
| **Incapacitated** | Can't take actions, bonus actions, or reactions |
| **Invisible** | Can't be seen without special senses; advantage on attacks; attackers have disadvantage |
| **Paralyzed** | Incapacitated (sub-condition); auto-fail STR/DEX saves; melee attacks within 5ft auto-crit |
| **Petrified** | Incapacitated; resistance to all damage; immune to poison/disease |
| **Poisoned** | Disadvantage on attack rolls and ability checks |
| **Prone** | Disadvantage on attacks; melee attackers within 5ft have advantage, ranged have disadvantage; standing costs half movement |
| **Restrained** | Speed = 0; disadvantage on DEX saves and attacks; attackers have advantage |
| **Stunned** | Incapacitated; auto-fail STR/DEX saves |
| **Unconscious** | Incapacitated; can't move/speak; melee within 5ft = auto-crit |

### Turn-Scoped Conditions (STATUS category)

| Condition | Effect | Duration |
|-----------|--------|----------|
| **Dashing** | Movement doubled | Removed at start of next turn |
| **Dodging** | Attackers have disadvantage; advantage on DEX saves | Removed at start of next turn |
| **Disengaging** | Movement doesn't provoke opportunity attacks | Removed at start of next turn |
| **Concentrating** | Tracking concentration on a spell; CON save on damage | Until broken or dropped |

### Hazard-Related Condition Fields

| Field | Type | Description |
|-------|------|-------------|
| `hazard_filter` | enum or null | `ALL` (everyone), `ENEMIES` (only enemies of source), `NON_SOURCE` (everyone except caster) |
| `condition_stealth_dc` | int or null | Perception DC to detect the hazard. `null` = always visible. |
| `magical_origin` | bool | Set by spells (for Dispel Magic, Globe of Invulnerability interaction) |

---

## 6. The Action System

Actions are how entities interact with the game world. Every action — attacking, moving, casting a spell, using an item — follows the same framework.

### BaseAction Flow

```
BaseAction.apply()
├── 1. check_costs()    → Can entity afford this? (actions, bonus actions, movement, spell slots)
├── 2. _validate()      → Is the action valid? (range, LOS, target alive, etc.)
│   └── Returns EXECUTION event or CANCEL
├── 3. _apply()         → Execute the action (roll dice, apply damage, add conditions)
│   └── EXECUTION → EFFECT → COMPLETION
└── 4. _apply_costs()   → Deduct costs from action economy
```

### ActionCategory

Every action is classified by type:

| Category | Examples |
|----------|---------|
| `ABILITY` | Dash, Dodge, Disengage, Hide, Shove, Pick Up |
| `ATTACK` | Weapon attacks, Extra Attack, opportunity attacks |
| `SPELL` | Fire Bolt, Fireball, Hold Person, Healing Word |
| `MOVEMENT` | Move, Jump |

### Cost Types

Actions consume resources from the entity's action economy:

| Cost Type | Per Turn Default | Examples |
|-----------|-----------------|---------|
| `actions` | 1 | Attack, Cast Spell, Dash, Dodge |
| `bonus_actions` | 1 | Two-Weapon Fighting, some spells |
| `reactions` | 1 | Opportunity Attack, Shield spell |
| `movement` | 30 feet (6 cells) | Move action (per cell) |
| `resource_name` / `resource_cost` | Varies | Sorcery Points, Rage uses, spell slots |

### Template System

Actions are stored as **templates** on entities. A template defines the action's parameters but has no target. When the player selects a target, the engine creates an **instance** from the template with the specific target filled in, then applies it.

```
Template (stored on entity, no target)
    → instantiate(target) → Instance (has target, ready to apply)
        → apply() → Event (result)
```

### Three Sources of Actions

`get_available_actions()` discovers actions from three sources:

| Source | Mechanism | Examples |
|--------|-----------|---------|
| **Registered Templates** | Actions registered on the entity | Weapon attacks, Dash, Dodge, Disengage, spells |
| **Inventory Items** | `UsableItem.get_use_actions()` on items in inventory | Healing Potion, Spell Scroll |
| **Environment Objects** | Items on the floor within 5ft | Doors, levers, chests, Pick Up |

### Attack Action Flow

1. **Validate** — Check range, line of sight, target alive
2. **Cross-propagate modifiers** — `attacker.attack_bonus.set_from_target(target.ac_bonus)` to pull in target's "affects attackers" modifiers
3. **Roll d20** — Apply attack bonus, check for advantage/disadvantage
4. **Compare to AC** — Hit, miss, critical hit, or critical miss
5. **On hit: roll damage** — Weapon dice + modifiers, doubled on crit
6. **Apply damage** — Target takes damage (with resistance/immunity applied)
7. **Clean up** — Reset cross-entity propagation

### Spell System

Spells are `SpellAction` subclasses with additional fields:

| Field | Type | Description |
|-------|------|-------------|
| `spell_level` | int | 0 = cantrip, 1-9 = leveled spell |
| `spell_school` | string | evocation, abjuration, conjuration, etc. |
| `concentration` | bool | Requires concentration |
| `verbal` | bool | Has verbal component |
| `spell_range` | Range | Range in feet |
| `cast_at_level` | int | Actual slot level used (upcasting) |
| `caster_level` | int | For cantrip scaling (damage increases at levels 5, 11, 17) |

**Spell slots**: Casting a leveled spell consumes a spell slot of that level or higher. Cantrips (level 0) are free. The frontend shows available spell slots via the action economy API.

**AoE spells**: Target a position, compute affected area using a shape (Sphere, Cone, Line, Cube). Each entity in the area gets its own save/damage resolution.

### Multi-Target Convolution

For `MULTI_ENTITY` (Magic Missile) and `POSITION_AOE` (Fireball) actions:
1. One parent event created
2. Per-target child events with independent `lineage_uuid` for isolated save/damage tracking
3. Parent event aggregates results: `total_targets`, `total_damage`
4. Combat log shows hierarchical structure: parent entry with per-target sub-entries

### Action Override Pattern (Metamagic)

Conditions can temporarily modify action templates via "alt" fields:

| Alt Field | Overrides | Example |
|-----------|----------|---------|
| `alt_cost_type` | Cost type | Quickened Spell: action → bonus action |
| `alt_target_type` | Target type | Twinned Spell: single target → multi-target |
| `alt_target_count` | Number of targets | Twinned: 1 → 2 |
| `alt_range` | Spell range | Distant Spell: range × 2 |
| `alt_skip_slot` | Spell slot consumption | Subtle Spell: no verbal component |

These are temporary — cleared after the action is used or the condition expires.

---

## 7. Available Actions — What the Frontend Displays

This is the most critical section for frontend development. `get_available_actions()` returns everything the UI needs to present action choices to the player.

### AvailableActionsResult

The top-level response groups actions into four categories:

| Field | Contains | UI Presentation |
|-------|----------|----------------|
| `entity_actions` | Actions targeting other entities (Attack, targeted spells) | Show target list with names/distances |
| `position_actions` | Actions targeting grid positions (Move, AoE spells) | Show grid overlay with reachable/targetable positions |
| `self_actions` | Self-targeting actions (Dash, Dodge, Disengage) | Simple buttons, no target selection needed |
| `object_actions` | Actions targeting floor objects (Pick Up, use door) | Show object list with names |

Plus resource info:
- `remaining_movement` — Feet of movement remaining
- `handler_details` — Toggleable handlers `[{name, uuid, enabled, trigger_event}]`

### AvailableActionInfo

Each action in the result has:

| Field | Type | Description |
|-------|------|-------------|
| `template_name` | string | Unique action identifier (e.g., `"Attack_MELEE_MAIN"`, `"Fire Bolt"`, `"Move"`) |
| `display_name` | string | Human-readable name (e.g., `"Scimitar"`, `"Fire Bolt"`, `"Move"`) |
| `description` | string | Action description text |
| `target_type` | enum | What kind of target is needed (see below) |
| `valid_targets` | list | All valid targets with selection indices |
| `can_afford` | bool | Whether entity can pay the cost right now |
| `cost_type` | string | `"actions"`, `"bonus_actions"`, `"reactions"`, `"movement"` |
| `cost_amount` | int | How much it costs (e.g., 1 action, 30 movement) |
| `action_category` | enum | `ABILITY`, `ATTACK`, `SPELL`, `MOVEMENT` |
| `weapon_slot` | string or null | For attacks: `"MELEE_MAIN"`, `"RANGED_MAIN"`, etc. |
| `weapon_name` | string or null | For attacks: weapon name |
| `is_item_use` | bool | True if this is a use action from an item |
| `source_item_uuid` | string or null | UUID of item providing this action |
| `item_stack_count` | int or null | Stack count for stackable items |
| `num_projectiles` | int or null | For MULTI_ENTITY: number of projectiles (e.g., 3 for Magic Missile) |
| `allow_same_target` | bool or null | For MULTI_ENTITY: can same target be selected multiple times |

### AvailableTarget

Each valid target for an action:

| Field | Type | Description |
|-------|------|-------------|
| `index` | int | **Selection index** — pass this to `execute_by_index` |
| `target_uuid` | string or null | For entity/object targets: target UUID |
| `target_name` | string or null | For entity/object targets: display name |
| `position` | `[x, y]` or null | For position targets: grid position |
| `distance` | int or null | Distance in feet to target |

**Path info** (for POSITION_PATH actions like Move):

| Field | Type | Description |
|-------|------|-------------|
| `path_cost` | int or null | Movement cost in feet for shortest path |
| `path` | list of `[x, y]` or null | Ordered cells to walk |
| `is_path_hazardous` | bool | Whether shortest path crosses a hazardous tile |
| `safe_path_cost` | int or null | Cost of alternative safe path (null if none exists) |
| `safe_path` | list of `[x, y]` or null | Alternative path avoiding hazards |

**AoE info** (for POSITION_AOE actions like Fireball):

| Field | Type | Description |
|-------|------|-------------|
| `affected_entity_uuids` | list of strings or null | UUIDs of entities in AoE |
| `affected_entity_names` | list of strings or null | Names of entities in AoE |
| `affected_count` | int or null | Number of affected entities |
| `affected_positions` | list of `[x, y]` or null | All positions in the AoE shape |

**Multi-target info** (for MULTI_ENTITY actions like Magic Missile):

| Field | Type | Description |
|-------|------|-------------|
| `extra_target_uuids` | list of strings or null | Additional targets beyond primary |

### Target Types

| TargetType | What It Means | UI Behavior |
|-----------|---------------|-------------|
| `SELF` | No target needed | One-click button |
| `ENTITY` | Select one entity | Show entity list with distances |
| `MULTI_ENTITY` | Select primary + extra targets | Show entity list, allow multiple selections |
| `POSITION_PATH` | Select reachable position (walking) | Show reachable cells on grid, with path preview |
| `POSITION_LOS` | Select visible position (line of sight) | Show visible cells within range |
| `POSITION_AOE` | Select center position for area effect | Show AoE preview at cursor position |
| `OBJECT` | Select floor object | Show object list |

### Target Discovery (How Valid Targets Are Found)

| TargetType | Filter Logic |
|-----------|-------------|
| **ENTITY** | Visible entities (via senses) + faction filter (enemies/allies/all) + range check + LOS |
| **MULTI_ENTITY** | Same as ENTITY; `num_projectiles` determines how many targets to select |
| **POSITION_PATH** | Reachable positions via Dijkstra pathfinding (terrain costs, entity blocking, hazard awareness) |
| **POSITION_LOS** | Visible positions (shadowcast FOV) within spell range |
| **POSITION_AOE** | All visible positions within range. Each position pre-computes affected entities. |
| **OBJECT** | Floor items within 5ft of entity |

### Execution Flow (Frontend → Backend)

1. **Get available actions**: `GET /entity/{entity_uuid}/available-actions`
2. **Player selects an action**: Pick from entity_actions, position_actions, self_actions, or object_actions
3. **Player selects a target**: Pick from `valid_targets` by `index`
4. **Execute**: `POST /action/execute` with `template_name` + `target_index`

```json
POST /action/execute
{
  "session_id": "...",
  "entity_uuid": "...",
  "template_name": "Attack_MELEE_MAIN",
  "target_index": 0,
  "prefer_safe": true
}
```

The response includes:
- `success` — Whether action succeeded
- `combat_log_entries` — What happened (formatted text + structured data)
- `available_actions` — Updated available actions after execution
- `state` — Full game state snapshot

### Hazard Pathfinding

When `is_path_hazardous` is true for a movement target, the frontend should indicate danger. The `safe_path_cost` and `safe_path` fields offer an alternative route avoiding hazards.

The `prefer_safe` flag on the execute request controls which path is used:
- `true` (default) — Use safe path when available
- `false` — Force shortest path even through hazards

---

## 8. Senses & Reactive Updates

Each entity has a `Senses` block tracking what it can see and where it can move. The senses system handles fog of war, hidden entities, and incremental updates.

### Senses Data

| Field | Type | Description |
|-------|------|-------------|
| `entities` | dict: UUID → position | Visible entities (filtered by perceivability) |
| `objects` | dict: UUID → position | Visible floor objects (items, doors) |
| `visible` | dict: position → bool | Which grid cells this entity can see |
| `paths` | dict: position → path | Movement paths to reachable positions |
| `safe_paths` | dict: position → path | Paths avoiding hazardous tiles |
| `sense_modes` | list | Special senses: Darkvision, Blindsight, Truesight, Devil's Sight (with ranges) |
| `seen` | set of positions | All positions ever seen (memory/fog of war) |
| `collision_blocked` | set of positions | Positions blocked by invisible entities (bump detection) |

### How Senses Update

Senses are **not** recomputed every frame. They update:

1. **At turn start** — Full recompute: FOV (shadowcast), paths (Dijkstra), entity filtering
2. **After movement** — Full recompute for the moving entity
3. **On spatial events** — Incremental updates via `SensesUpdateHint`:
   - Light change → update visibility at affected positions
   - Entity enters/leaves → O(1) dict add/remove
   - Door opens/closes → recompute FOV
   - Perception change → refilter all visible entities

### Light System

Each tile has a **resolved light level** computed from:
- **Default light** — Base illumination (Floor = BRIGHT_LIGHT, dungeon = DARKNESS)
- **Illuminations** — Light sources (torches, Light spell) that brighten tiles
- **Obscurements** — Darkness effects (Darkness spell, Fog Cloud) that darken tiles

Resolution: `MAX(default + illuminations)` then `MIN(result + obscurements)`

**Light levels** (ordinal 0-4):

| Level | Value | Description |
|-------|-------|-------------|
| `MAGICAL_DARKNESS` | 0 | Impenetrable darkness (Darkness spell). Only Truesight/Devil's Sight can see through. |
| `DARKNESS` | 1 | Normal darkness. Darkvision sees as dim light. |
| `DIM_LIGHT` | 2 | Dim light. Darkvision sees as bright light. |
| `BRIGHT_LIGHT` | 3 | Normal bright light. Everyone can see. |
| `VERY_BRIGHT` | 4 | Very bright (inner radius of powerful sources). |

**Effective light per observer**: Different entities see different light levels at the same tile based on their sense modes:
- **Normal vision** — Sees raw resolved light level
- **Darkvision** — Within range: darkness → dim, dim → bright (NOT magical darkness)
- **Devil's Sight** — Sees normally in ALL darkness (including magical) within range
- **Blindsight** — Sees regardless of light within range
- **Truesight** — Sees through everything within range

**Adjacent rule**: An entity always has minimum DIM_LIGHT at distance ≤ 1 from itself (you can always see what's right next to you in natural darkness).

### Perceivability (Stealth & Invisibility)

An entity might be visible in terms of light but still hidden or invisible:

| Mechanism | How It Works |
|-----------|-------------|
| **Hidden** | Entity has `stealth_dc`. Observer's `passive_perception` must beat it to see the entity. |
| **Invisible** | Entity has `is_invisible` flag. Only special senses (Truesight, See Invisibility, Blindsight) can detect it. |

The senses system filters entities through perceivability checks after visibility checks. The result in `senses.entities` only includes entities that are both visible (light/LOS) AND perceivable (not hidden/invisible, or observer can bypass).

### Observer Perception Changes

When an entity's perception capabilities change (e.g., gains Darkvision, WIS modifier changes from a buff):
- The system detects the change via snapshot comparison
- All visible entities are refiltered with new perception
- `ENTITY_SPOTTED` combat logs are generated when newly detected enemies are found
- `HAZARD_DETECTED` logs generated when hidden traps become visible

---

## 9. The Combat Log System

The combat log provides formatted, hierarchical text descriptions of everything that happens in combat. Each log entry has three verbosity levels and structured data for programmatic access.

### CombatLogEntry Structure

| Field | Type | Description |
|-------|------|-------------|
| `entry_type` | string | Type of entry (see table below) |
| `source_name` | string | Actor performing the action |
| `source_uuid` | string | UUID of actor |
| `target_name` | string or null | Target of the action |
| `target_uuid` | string or null | UUID of target |
| `compact` | string | One-line summary with markdown formatting |
| `verbose` | string | Summary + key details (roll values, DC, etc.) |
| `detailed` | string | Full breakdown with all modifier sources |
| `data` | dict | Type-specific structured data (see typed data models below) |
| `success` | bool or null | Success indicator for attacks, saves, checks |
| `sub_entries` | list of CombatLogEntry | Hierarchical child entries |
| `perceiver_uuids` | set of strings | Entity UUIDs that could perceive this event. Empty = show to everyone. |
| `revealed_entity_uuids` | set of strings | Entity UUIDs revealed during this event chain (Hidden/Invisible removed) |

### Entry Types

| Entry Type | When Generated |
|-----------|---------------|
| `attack` | Weapon or spell attack roll |
| `movement` | Entity moves |
| `action` | Self-targeting action (Dash, Dodge, Disengage) |
| `saving_throw` | Saving throw made |
| `skill_check` | Skill check made |
| `condition_applied` | Condition added to entity |
| `condition_removed` | Condition removed from entity |
| `damage_taken` | Entity takes damage |
| `heal` | Entity healed |
| `death` | Entity dies |
| `turn_start` | Entity's turn begins |
| `turn_end` | Entity's turn ends |
| `multi_entity_action` | AoE or multi-target spell (parent entry) |
| `spell_save` | Save-based spell effect on single target |
| `spell_damage` | Auto-hit spell damage (Magic Missile dart) |
| `entity_spotted` | Observer spots a hiding entity |
| `hazard_detected` | Observer detects a hidden hazard |

### Markdown Formatting

The `compact`, `verbose`, and `detailed` text fields use markdown-style formatting:

| Syntax | Renders As | Example |
|--------|-----------|---------|
| `**text**` | Bold | `**critical hit**` |
| `*text*` | Italic | `*miss*` |
| `{color:text}` | Colored text | `{cyan:Hero}`, `{red:MISS}`, `{green:HIT}` |

Common colors used: `cyan` (entity names), `yellow` (target names), `green` (positive outcomes), `red` (negative outcomes/damage), `dim` (supplementary info).

### Hierarchical Sub-Entries

Sub-entries mirror the parent-child event tree. Example for Fireball:

```
Fireball (multi_entity_action)
  "Wizard uses Fireball → 3 targets, 42 total damage"
  ├── sub_entry (spell_save)
  │     "Skeleton 1: DEX save FAIL, 15 fire damage"
  │     └── sub_entry (damage_taken)
  ├── sub_entry (spell_save)
  │     "Skeleton 2: DEX save SAVE, 7 fire damage (half)"
  │     └── sub_entry (damage_taken)
  └── sub_entry (spell_save)
        "Skeleton 3: DEX save FAIL, 15 fire damage"
        └── sub_entry (damage_taken)
```

### Perceiver Filtering

`perceiver_uuids` controls who sees each log entry:
- **Non-empty set** — Only show to clients controlling entities in this set
- **Empty set** — Legacy entry, show to everyone

`revealed_entity_uuids` prevents anonymizing entities that were just revealed. Example: an AoE spell breaks Hidden on a target — the target name should still appear in the combat log even though they were hidden at the start.

### Typed Data Models

Each entry type has a structured `data` field. Here are the key ones:

#### AttackLogData

| Field | Type | Description |
|-------|------|-------------|
| `attacker_name` / `attacker_uuid` | string | Attacker identity |
| `target_name` / `target_uuid` | string | Target identity |
| `weapon_name` | string | Weapon used |
| `weapon_slot` | string or null | Slot (MELEE_MAIN, RANGED_OFF, etc.) |
| `attack_roll` | DiceRollDisplay | Attack roll details |
| `attack_breakdown` | list of ModifierBreakdown | Attack bonus sources |
| `target_ac` | int | Target's AC |
| `ac_breakdown` | list of ModifierBreakdown | AC bonus sources |
| `outcome` | string | `"hit"`, `"miss"`, `"crit"`, `"crit_miss"` |
| `is_hit` | bool | Whether attack hit |
| `is_crit` | bool | Whether it was a critical |
| `damage_rolls` | list of DamageRollDisplay | Damage dice and results |
| `total_damage` | int | Total damage dealt |
| `target_hp` | int or null | Target HP after attack |
| `is_opportunity_attack` | bool | Whether this was an opportunity attack |

#### DiceRollDisplay

| Field | Type | Description |
|-------|------|-------------|
| `dice_str` | string | Dice notation: `"d20"`, `"1d6"`, `"2d8"` |
| `results` | list of int | Individual die results |
| `bonus` | int | Total bonus applied |
| `total` | int | Final total |
| `all_d20_rolls` | list of int or null | All d20 rolls when advantage/disadvantage |
| `d20_used` | int or null | Which d20 was used |
| `advantage_status` | string or null | `"advantage"`, `"disadvantage"`, or null |

#### DamageRollDisplay

| Field | Type | Description |
|-------|------|-------------|
| `dice_str` | string | Damage dice: `"1d6"`, `"2d8"` |
| `dice_results` | list of int | Individual die results |
| `bonus` | int | Damage bonus |
| `total` | int | Total damage |
| `damage_type` | string | Type: `"slashing"`, `"fire"`, etc. |
| `bonus_breakdown` | list of ModifierBreakdown | Damage bonus sources |

#### ModifierBreakdown

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Modifier name: `"Prof"`, `"DEX"`, `"Bless"` |
| `value` | int | Modifier value: +2, -1, etc. |
| `source` | string | Where it comes from (default: `"self"`) |

#### MovementLogData

| Field | Type | Description |
|-------|------|-------------|
| `entity_name` / `entity_uuid` | string | Moving entity |
| `start_position` / `end_position` | `[x, y]` | Start and end positions |
| `path` | list of `[x, y]` | Full path traveled |
| `distance_feet` | int | Distance in feet |
| `movement_cost` | int | Actual movement cost (may differ from distance due to terrain) |

#### SavingThrowLogData

| Field | Type | Description |
|-------|------|-------------|
| `entity_name` / `entity_uuid` | string | Entity making save |
| `ability` | string | Ability used: `"strength"`, `"dexterity"`, etc. |
| `dc` | int | DC to beat |
| `roll` | DiceRollDisplay | The d20 roll |
| `bonus_breakdown` | list of ModifierBreakdown | Save bonus sources |
| `success` | bool | Whether save succeeded |

#### SpellSaveLogData

| Field | Type | Description |
|-------|------|-------------|
| `caster_name` / `caster_uuid` | string | Caster identity |
| `target_name` / `target_uuid` | string | Target identity |
| `spell_name` | string | Spell name |
| `spell_level` | int | Spell level (0-9) |
| `save_ability` | string | Ability for save |
| `save_dc` | int | Save DC |
| `save_roll` | DiceRollDisplay | The save roll |
| `save_success` | bool | Whether save succeeded |
| `damage_rolls` | list of DamageRollDisplay | Damage rolls |
| `base_damage` | int | Damage before save modification |
| `final_damage` | int | Damage after save modification (half on success) |
| `damage_type` | string | Damage type |
| `target_hp_after` | int or null | Target HP after |

#### MultiEntityLogData

| Field | Type | Description |
|-------|------|-------------|
| `action_name` | string | Spell/action name |
| `caster_name` | string | Caster name |
| `total_targets` | int | Number of targets |
| `target_names` | list of string | Target names |
| `total_damage` | int | Aggregate damage |
| `saves_succeeded` / `saves_failed` | int | Save counts |
| `aoe_shape` | string or null | `"Sphere"`, `"Cone"`, `"Line"`, `"Cube"` |
| `aoe_center` | `[x, y]` or null | Center position of AoE |

#### EntitySpottedLogData

| Field | Type | Description |
|-------|------|-------------|
| `observer_name` / `observer_uuid` | string | Who spotted |
| `target_name` / `target_uuid` | string | Who was spotted |
| `target_position` | `[x, y]` | Where |
| `passive_perception` | int | Observer's passive perception |
| `stealth_dc` | int | Target's stealth DC |

#### HazardDetectedLogData

| Field | Type | Description |
|-------|------|-------------|
| `observer_name` / `observer_uuid` | string | Who detected |
| `hazard_name` | string | Hazard name |
| `position` | `[x, y]` | Where |
| `passive_perception` | int | Observer's perception |
| `stealth_dc` | int | Hazard's stealth DC |

#### Other Data Models

| Model | Entry Type | Key Fields |
|-------|-----------|-----------|
| `HealLogData` | `heal` | `entity_name`, `amount`, `source_description` |
| `SelfActionLogData` | `action` | `entity_name`, `action_name`, `effect_description` |
| `TurnLogData` | `turn_start`/`turn_end` | `entity_name`, `round_number`, `turn_index` |
| `SkillCheckLogData` | `skill_check` | `entity_name`, `skill`, `dc`, `roll`, `success` |

---

## 10. The Grid & Spatial System

### GridMap

The grid is a singleton managing all spatial data. It stores tiles, entity positions, object positions, and light sources.

**Core data structures**:
- `_tiles: Dict[position, Tile]` — Tile objects at each grid position
- `_entity_positions: Dict[UUID, position]` — Entity → grid position
- `_entities_by_position: Dict[position, Set[UUID]]` — Reverse: position → entity UUIDs
- `_object_positions: Dict[UUID, position]` — Object (item) → grid position
- `_objects_by_position: Dict[position, Set[UUID]]` — Reverse: position → object UUIDs
- `_light_sources: Dict[UUID, LightSourceData]` — Active light sources

### Tiles

Each grid position has a `Tile` object. Tiles are the fundamental spatial unit.

**Tile types** (via `name` field):

| Name | Walkable | Blocks Vision | Map Char | Description |
|------|----------|--------------|----------|-------------|
| `"Floor"` | Yes | No | `.` | Normal walkable tile |
| `"Wall"` | No | Yes | `#` | Blocks movement and vision |
| `"Water"` | No | No | `~` | Blocks movement, allows vision |

**Tile properties**:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Tile type identifier |
| `walkable` | bool | Whether entities can walk on it |
| `visible` | bool | Whether vision passes through |
| `walking_cost` | int | Movement cost: 1 = normal, 2 = difficult terrain, 0 = impassable |
| `height` | int | Elevation in 5ft increments (0 = ground level) |
| `default_light` | LightLevel | Base illumination before light sources |
| `conditions` | list | Active conditions on this tile (fire, traps, zone spells) |

**Movement modes**: Walking (default), Flying, Swimming, Burrowing. Each tile has independent costs per mode.

**Border system**: Tiles can restrict entry from specific directions (`border_north`, `border_south`, `border_east`, `border_west`). Used for one-way passages.

### Entity Blocking

Entities block movement for other entities. A cell occupied by an enemy is impassable. The pathfinding system accounts for this when computing reachable positions.

An entity's own cell is always walkable for itself. Allies may or may not block depending on game rules.

### Light Sources

Light sources illuminate tiles around a position:

| Field | Description |
|-------|-------------|
| `position` | Center position of light source |
| `very_bright_radius_feet` | Inner radius: VERY_BRIGHT light |
| `bright_radius_feet` | Middle radius: BRIGHT_LIGHT |
| `dim_radius_feet` | Outer radius: DIM_LIGHT |
| `anchor_uuid` | Entity or item this light is attached to (moves with it) |

Light sources can be added, removed, moved, and toggled on/off. Moving a light source uses delta computation — only touches tiles that actually changed.

### Hazard System

Tiles (or tile conditions) can be hazardous. The hazard system determines which entities consider a tile dangerous:

**HazardFilter** on tile conditions:
- `ALL` — Hazardous to everyone
- `ENEMIES` — Only hazardous to enemies of the condition's source
- `NON_SOURCE` — Hazardous to everyone except the caster

**Stealth DC** (`condition_stealth_dc`): If set, the hazard is hidden. Only entities whose passive perception ≥ DC can detect it. Hidden hazards don't appear in the observer's `safe_paths` computation (they don't know it's there).

**Pathfinding integration**: The Dijkstra pathfinder has a `walk_in_danger` flag. When false, hazardous tiles are excluded from paths. The `senses.safe_paths` dict stores hazard-avoiding routes.

### Tile Conditions

Tiles can have conditions (like entities), used for zone spells and environmental effects:

| Example | Mechanism |
|---------|-----------|
| Spike Growth | Tiles deal damage to entities entering |
| Web | Tiles apply Restrained condition |
| Fog Cloud | Tiles add obscurement (darkness) |
| Difficult Terrain | Tiles have `walking_cost = 2` |
| Spike Trap | Hidden hazard (condition_stealth_dc set) |

### FOV and Pathfinding

**Field of View (FOV)** — Computed via shadowcasting algorithm. Determines which cells an entity can see based on walls and blocking objects.

**Pathfinding** — Computed via Dijkstra's algorithm. Determines reachable positions considering:
- Terrain costs (difficult terrain = 2x)
- Entity blocking (enemies block, allies may not)
- Hazard avoidance (when `walk_in_danger=false`)
- Maximum distance (movement remaining)

---

## 11. REST API Reference

Base URL: `http://localhost:8000` (default uvicorn)

CORS: All origins allowed.

### Health & Info

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/` | Server status | `{status, listeners, event_count, has_encounter, paused}` |

### Game State

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/state` | Full game state snapshot | `APIGameState` |
| GET | `/entities` | All entities (summary) | `{entities: [APIEntitySummary]}` |
| GET | `/entity/{entity_uuid}` | Single entity (detailed) | `APIEntityFull` |
| GET | `/grid` | Grid data with tiles | `APIGrid` |
| GET | `/tile/{x}/{y}` | Single tile details | Tile detail object (see below) |
| GET | `/encounter` | Encounter state | `{active: bool, encounter: APIEncounter}` |
| GET | `/combat-log?since=0` | Combat log entries | `{entries: [CombatLogEntry], count, total}` |
| GET | `/visibility` | All entities' visibility data | `{uuid: {name, position, visible_cells, visible_entities, seen_cells, sense_modes}}` |

**Tile detail response** (`GET /tile/{x}/{y}`):

```json
{
  "position": [5, 3],
  "name": "Floor",
  "walkable": true,
  "visible": true,
  "walking_cost": 1,
  "conditions": ["Spike Growth"],
  "handlers": [...],
  "entities": ["entity-uuid-1"],
  "objects": ["item-uuid-1"],
  "height": 0,
  "light_level": 3,
  "light_level_name": "BRIGHT_LIGHT",
  "default_light": 3,
  "illumination_count": 1
}
```

### Session Management

| Method | Path | Request Body | Response |
|--------|------|-------------|----------|
| POST | `/session/create` | `{player_type, name?}` | `{session_id, player_type, name}` |
| POST | `/session/{session_id}/ping` | — | `SessionPingResponse` |
| DELETE | `/session/{session_id}` | — | `{status: "deleted", session_id}` |
| POST | `/game/join` | `{session_id, entity_uuids?, faction?}` | `JoinGameResponse` |
| GET | `/game/status` | — | Game status with sessions |
| GET | `/session/{session_id}/entities` | — | Controlled entities list |

### Turn & Actions

| Method | Path | Request Body | Response |
|--------|------|-------------|----------|
| GET | `/encounter/current-turn` | — | `APICurrentTurn` |
| GET | `/entity/{entity_uuid}/available-actions` | — | Available actions result |
| GET | `/entity/{entity_uuid}/handlers` | — | Handler list |
| POST | `/entity/{entity_uuid}/handlers/{handler_name}/toggle` | `{session_id, entity_uuid, enabled}` | Toggle result |

### Action Execution (Session-Validated)

All action endpoints validate: session exists → session owns entity → entity's turn in progress.

| Method | Path | Request Body | Response |
|--------|------|-------------|----------|
| POST | `/action/execute` | `ExecuteByIndexRequest` | `ActionResult` |
| POST | `/action/end-turn` | `{session_id, entity_uuid}` | End-turn result |
| POST | `/action/self` | `{session_id, entity_uuid, action_name}` | `ActionResult` |
| POST | `/action/entity` | `{session_id, entity_uuid, action_name, target_uuid}` | `ActionResult` |
| POST | `/action/position` | `{session_id, entity_uuid, action_name, position}` | `ActionResult` |
| POST | `/action/position/preview` | `{session_id, entity_uuid, action_name, position}` | `AoEPreviewResult` |

**Recommended execution endpoint**: Use `/action/execute` with `ExecuteByIndexRequest` for all actions. It handles all target types uniformly via template_name + target_index.

### Arena Setup

| Method | Path | Query Params | Description |
|--------|------|-------------|-------------|
| POST | `/simulation/start-human` | `character_class=fighter` | Start PvE encounter |
| POST | `/simulation/start-pvp` | `character_class=fighter` | Start PvP encounter |
| POST | `/simulation/start-aoe-test` | — | Start AoE test encounter |
| POST | `/simulation/reset` | — | Reset all state |

### Simulation Control

| Method | Path | Description |
|--------|------|-------------|
| POST | `/simulation/start` | Start AI-vs-AI simulation |
| POST | `/simulation/pause` | Pause simulation |
| POST | `/simulation/resume` | Resume simulation |
| POST | `/simulation/step` | Advance one step |
| POST | `/simulation/set-delay?delay=1.0` | Set turn delay |
| GET | `/simulation/status` | Simulation status |

### Event Debugging

| Method | Path | Description |
|--------|------|-------------|
| GET | `/events?limit=50&event_type=&phase=` | Recent events |
| GET | `/event-types` | All event types and phases |

### PvP Status

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pvp/status` | PvP game status |

### Error Codes

| Code | Meaning |
|------|---------|
| 400 | Invalid request format, no active game, turn not in progress |
| 401 | Invalid or disconnected session |
| 403 | Session doesn't own entity, or not entity's turn |
| 404 | Entity or resource not found |

### Session Authority Model

1. **Create session**: `POST /session/create` with `player_type` ("human" or "claude") → get `session_id`
2. **Join game**: `POST /game/join` with `session_id` and either `entity_uuids` or `faction` → get assigned entities
3. **All action requests** include `session_id` and `entity_uuid` in the body
4. **Validation**: Server checks session is valid, entity belongs to session, and it's that entity's turn

### Polling Pattern

The frontend uses polling to detect turn changes:

1. Poll `POST /session/{id}/ping` periodically
2. Response includes `is_my_turn: bool` and `active_entity_uuid`
3. When `is_my_turn` becomes true, fetch available actions and present UI
4. After executing actions, call `POST /action/end-turn`
5. End-turn response advances through AI turns and returns when the next human turn begins (or encounter ends)

---

## 12. Encounter & Turn Flow

### Encounter States

```
NOT_STARTED → ACTIVE → ENDED
                ↕
              PAUSED
```

| State | Description |
|-------|-------------|
| `NOT_STARTED` (`"not_started"`) | Encounter created but not yet started |
| `ACTIVE` (`"in_progress"`) | Combat in progress |
| `PAUSED` (`"paused"`) | Simulation paused (not used in PvP) |
| `ENDED` (`"finished"`) | Combat finished (one faction standing) |

### Initiative

At encounter start, each combatant rolls initiative: `d20 + DEX modifier + feats`. Combatants are sorted by total (highest first). Ties broken by modifier.

### Turn Flow

Each round consists of turns in initiative order:

```
Round N:
  ├── Entity A's turn: start_turn → [actions] → end_turn
  ├── Entity B's turn: start_turn → [actions] → end_turn
  ├── Entity C's turn: start_turn → [actions] → end_turn
  └── Round end → Environment step → Round N+1 start
```

**Turn start** (`start_turn`):
- Skip if entity is dead or surprised (round 1 only)
- Fire `TURN_START` event
- Reset action economy: actions, bonus actions, reactions reset to max; movement resets
- Advance condition durations (auto-remove expired conditions)
- Recompute senses (full Dijkstra + FOV)

**During turn**:
- Entity executes actions (attack, move, cast spells, use items)
- Each action costs resources from the action economy
- Available actions update after each action

**Turn end** (`end_turn`):
- Fire `TURN_END` event
- Handlers can react (end-of-turn effects)
- Mark entity as having acted this round

**Next turn** (`next_turn`):
- End current turn if still in progress
- Advance to next combatant in initiative
- If all combatants acted → advance round
- Start new turn for next entity

### Action Economy Per Turn

| Resource | Default | Resets |
|----------|---------|-------|
| Actions | 1 | Per turn |
| Bonus Actions | 1 | Per turn |
| Reactions | 1 | Per turn |
| Movement | 30 feet (6 cells) | Per turn |
| Spell Slots | Varies by level | Per long rest |

Some abilities modify these (Action Surge gives +1 action, Haste gives +1 action with restrictions, Dash doubles movement).

### Round End — Environment Step

At the end of each round:
1. Fire `ROUND_END` event
2. **Environment step**: Advance durations on all tile conditions and floor item conditions
3. Increment round number
4. Reset "has acted" flags for all combatants
5. Fire `ROUND_START` event

### Death Handling

After each action, `check_deaths()` is called:
1. Check all combatants for HP ≤ 0
2. Apply `Dead` condition to newly dead entities
3. Fire `DEATH` event per dead entity
4. Check if encounter should end (only one faction has survivors)

### Encounter End Condition

The encounter ends when:
- Only one faction has living members
- `faction = null` entities are each their own "faction" — so if two null-faction entities survive, the encounter continues

### Controller Types

Each combatant has a controller that determines how their turn is played:

| Controller | Behavior | Use Case |
|-----------|----------|----------|
| `HumanController` | Exits turn loop, waits for API input | Human player via frontend |
| `ClaudeController` | Exits turn loop, waits for agent CLI input | Claude AI player in PvP |
| `MeleeAIController` | Auto-attacks nearest enemy | Simple enemy AI |
| `PassController` | Immediately ends turn | Testing |

### End-Turn Response Behavior

When the frontend calls `/action/end-turn`:
1. Current entity's turn ends
2. Engine advances through AI turns (MeleeAIController, PassController) automatically
3. Response returns when:
   - Next human/Claude turn begins (frontend gets control)
   - OR encounter ends
4. Response includes `ai_actions` — combat log entries from AI turns that happened

---

## 13. API Data Models

All API models are Pydantic `BaseModel` subclasses. Each has a `.create()` classmethod that converts internal game objects to serializable API models.

### Serialization Rules

- **UUIDs**: Serialized as strings (`"550e8400-e29b-41d4-a716-446655440000"`)
- **Positions**: Serialized as `[x, y]` integer arrays
- **Enums**: Serialized as string values (e.g., `"ADVANTAGE"`, `"melee_main"`)
- **Optional fields**: Serialized as `null` when not set
- **Lists**: Empty list `[]` when no items

### APIEntitySummary

Lightweight entity for list views. Used in `APIGameState.entities`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `uuid` | string | — | Entity unique identifier |
| `name` | string | — | Entity name |
| `position` | `[int, int]` | — | Grid position |
| `hp` | int | — | Current hit points |
| `max_hp` | int | — | Maximum hit points |
| `ac` | int | — | Armor class |
| `conditions` | list of string | — | Active condition names (e.g., `["Blinded", "Prone"]`) |
| `condition_details` | list of dict | `[]` | Detailed conditions: `[{name: "Blinded", category: "condition"}, ...]` |
| `is_dead` | bool | — | Whether entity is dead |
| `faction` | string or null | null | Faction identifier |

### APIEntityFull

Extends `APIEntitySummary` with detailed data. Used for single-entity queries.

| Additional Field | Type | Description |
|-----------------|------|-------------|
| `action_economy` | dict | `{actions: int, bonus_actions: int, reactions: int, movement: int}` |
| `ability_scores` | dict | `{strength: int, dexterity: int, constitution: int, intelligence: int, wisdom: int, charisma: int}` (scores, not modifiers) |
| `weapon_name` | string or null | Name of equipped main-hand weapon |

### APITile

Single tile data.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | int | — | X coordinate |
| `y` | int | — | Y coordinate |
| `walkable` | bool | — | Whether passable |
| `visible` | bool | — | Whether visible to requesting entity |
| `name` | string | `"Floor"` | Tile type |
| `walking_cost` | int | 1 | Movement cost (1=normal, 2=difficult, 0=impassable) |
| `is_hazardous` | bool | false | Whether tile has hazardous conditions |
| `conditions` | list of string | `[]` | Active condition names on tile |
| `light_level` | int | 3 | Light level (0=MAGICAL_DARKNESS to 4=VERY_BRIGHT) |

### APIGrid

Grid/map data. The `.create()` method accepts an optional `requesting_entity_uuid` for perception-filtered hazard and condition visibility.

| Field | Type | Description |
|-------|------|-------------|
| `min_x` | int | Minimum x coordinate |
| `min_y` | int | Minimum y coordinate |
| `max_x` | int | Maximum x coordinate |
| `max_y` | int | Maximum y coordinate |
| `tiles` | list of APITile | All tiles |

### APICombatant

Combatant in initiative order.

| Field | Type | Description |
|-------|------|-------------|
| `uuid` | string | Combatant UUID |
| `name` | string | Combatant name |
| `initiative` | int | Initiative total |
| `is_dead` | bool | Whether dead |

### APIEncounter

Encounter state.

| Field | Type | Description |
|-------|------|-------------|
| `uuid` | string | Encounter UUID |
| `name` | string | Encounter name |
| `state` | string | `"waiting_to_start"`, `"in_progress"`, or `"finished"` |
| `round_number` | int | Current round (1-indexed) |
| `current_turn_index` | int | Index in initiative order |
| `current_entity_uuid` | string or null | UUID of entity whose turn it is |
| `initiative_order` | list of APICombatant | All combatants in order |

### APIFloorObject

Item on the ground.

| Field | Type | Description |
|-------|------|-------------|
| `uuid` | string | Object UUID |
| `name` | string | Object name |
| `position` | `[int, int]` | Grid position |
| `map_char` | string | Display character (default: `"φ"`) |

### APIGameState

Full state snapshot. Returned by `GET /state` and in `ActionResult.state`.

| Field | Type | Description |
|-------|------|-------------|
| `grid` | APIGrid | Current grid/map state |
| `entities` | list of APIEntitySummary | All entities |
| `encounter` | APIEncounter or null | Encounter state (null if none) |
| `floor_objects` | list of APIFloorObject | Items on floor |

### APICurrentTurn

Current turn information. Used for turn polling.

| Field | Type | Description |
|-------|------|-------------|
| `encounter_active` | bool | Whether encounter is in progress |
| `round_number` | int | Current round |
| `turn_index` | int | Index in initiative order |
| `current_entity_uuid` | string or null | Current acting entity UUID |
| `current_entity_name` | string or null | Current acting entity name |
| `is_human_turn` | bool | Whether it's a human player's turn |
| `waiting_for_input` | bool | Whether waiting for player input |
| `controller_type` | string or null | `"HumanController"`, `"ClaudeController"`, etc. |
| `actions_remaining` | int | Actions left this turn |
| `bonus_actions_remaining` | int | Bonus actions left |
| `reactions_remaining` | int | Reactions left |
| `movement_remaining` | int | Movement in feet left |

### APISimulationStatus

| Field | Type | Description |
|-------|------|-------------|
| `has_encounter` | bool | Whether encounter exists |
| `paused` | bool | Whether simulation paused |
| `encounter_state` | string or null | Encounter state |
| `round_number` | int or null | Current round |
| `turn_delay` | float | Delay between turns (seconds) |

### Session Models

**CreateSessionRequest**:

| Field | Type | Description |
|-------|------|-------------|
| `player_type` | string | `"human"` or `"claude"` |
| `name` | string or null | Display name |

**CreateSessionResponse**:

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Assigned session UUID |
| `player_type` | string | Confirmed type |
| `name` | string | Display name |

**SessionPingResponse**:

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Status message |
| `session_id` | string | Session UUID |
| `connection_status` | string | `"connected"`, `"disconnected"`, `"waiting"` |
| `is_my_turn` | bool | Whether it's this session's turn |
| `active_entity_uuid` | string or null | Current active entity |
| `active_entity_name` | string or null | Current active entity name |
| `controlled_entities` | list of string | Entity UUIDs controlled by this session |

**JoinGameRequest**:

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session UUID |
| `entity_uuids` | list of string or null | Specific entities to control |
| `faction` | string or null | Assign all entities of this faction |

**JoinGameResponse**:

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether join succeeded |
| `game_id` | string | Game UUID |
| `session_id` | string | Session UUID |
| `controlled_entities` | list of string | Assigned entity UUIDs |
| `message` | string | Status message |

### Action Request Models

**ExecuteByIndexRequest** (recommended for all actions):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `session_id` | string | — | Session UUID |
| `entity_uuid` | string | — | Acting entity UUID |
| `template_name` | string | — | Action template name (from `AvailableActionInfo.template_name`) |
| `target_index` | int | — | Target index (from `AvailableTarget.index`) |
| `extra_target_uuids` | list of string or null | null | Additional targets for MULTI_ENTITY actions |
| `prefer_safe` | bool | true | Use safe path for movement (avoid hazards) |

**SimpleActionRequest** (for end-turn):

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session UUID |
| `entity_uuid` | string | Entity UUID |

**SelfActionRequest**:

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session UUID |
| `entity_uuid` | string | Entity UUID |
| `action_name` | string | Template name (e.g., `"Dash"`) |

**EntityActionRequest**:

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session UUID |
| `entity_uuid` | string | Acting entity UUID |
| `action_name` | string | Template name |
| `target_uuid` | string | Target entity UUID |

**PositionActionRequest**:

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session UUID |
| `entity_uuid` | string | Entity UUID |
| `action_name` | string | Template name |
| `position` | `[int, int]` | Target position |

**ToggleHandlerRequest**:

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session UUID |
| `entity_uuid` | string | Entity UUID |
| `enabled` | bool | Enable or disable |

### ActionResult

Response from action execution endpoints.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `success` | bool | — | Whether action succeeded |
| `message` | string | — | Result message |
| `event_type` | string or null | null | Event type (e.g., `"ATTACK"`, `"MOVEMENT"`) |
| `event_data` | dict or null | null | Event details (attack roll, damage rolls, etc.) |
| `entity_hp` | int or null | null | Acting entity's HP after action |
| `target_hp` | int or null | null | Target's HP after action |
| `deaths` | list of string | `[]` | Names of entities that died |
| `triggered_reactions` | list of dict | `[]` | Reactions triggered (opportunity attacks during movement) |
| `turn_continues` | bool | true | False if turn ended or entity died |
| `encounter_ended` | bool | false | Whether encounter ended |
| `combat_log_entries` | list of dict | `[]` | Combat log entries (CombatLogEntry.to_dict()) |
| `available_actions` | dict or null | null | Updated available actions after execution |
| `state` | APIGameState or null | null | Full game state snapshot after action |

### AoEPreviewResult

Preview of AoE effect without executing.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `success` | bool | — | Whether preview succeeded |
| `message` | string | `""` | Status message |
| `affected_positions` | list of `[int, int]` | `[]` | Positions in AoE |
| `affected_entity_names` | list of string | `[]` | Names of entities in AoE |
| `affected_count` | int | 0 | Number of affected entities |

### Available Actions Response

Response from `GET /entity/{entity_uuid}/available-actions`:

```json
{
  "entity_uuid": "...",
  "entity_actions": [AvailableActionInfo, ...],
  "position_actions": [AvailableActionInfo, ...],
  "self_actions": [AvailableActionInfo, ...],
  "object_actions": [AvailableActionInfo, ...],
  "remaining_movement": 30,
  "actions_remaining": 1,
  "bonus_actions_remaining": 1,
  "reactions_remaining": 1,
  "extra_attacks_remaining": 0,
  "handler_details": [{"name": "Opportunity Attack", "uuid": "...", "enabled": true, "trigger_event": "STEP_MOVEMENT"}],
  "spell_slots": {"1": {"current": 4, "max": 4}, "2": {"current": 3, "max": 3}, "3": {"current": 2, "max": 2}},
  "resources": {"Sorcery Points": {"current": 5, "max": 5}}
}
```

Each `AvailableActionInfo` serializes as described in [Section 7](#availableactioninfo). Each `AvailableTarget` serializes as described in [Section 7](#availabletarget).

---

## Quick Reference: Frontend Integration Flow

### 1. Create Session and Join Game

```
POST /session/create {player_type: "human", name: "Player 1"}
  → {session_id: "abc-123"}

POST /simulation/start-human?character_class=fighter
  → {hero_uuid: "hero-456", encounter_uuid: "enc-789"}

POST /game/join {session_id: "abc-123", entity_uuids: ["hero-456"]}
  → {success: true, controlled_entities: ["hero-456"]}
```

### 2. Poll for Turn

```
POST /session/abc-123/ping
  → {is_my_turn: true, active_entity_uuid: "hero-456"}
```

### 3. Get Available Actions

```
GET /entity/hero-456/available-actions
  → {entity_actions: [...], position_actions: [...], self_actions: [...], ...}
```

### 4. Execute Action

```
POST /action/execute {
  session_id: "abc-123",
  entity_uuid: "hero-456",
  template_name: "Attack_MELEE_MAIN",
  target_index: 0
}
  → ActionResult {success: true, combat_log_entries: [...], state: {...}}
```

### 5. End Turn

```
POST /action/end-turn {session_id: "abc-123", entity_uuid: "hero-456"}
  → {status: "turn_ended", ai_actions: [...], new_log_since: 5}
```

### 6. Repeat from Step 2
