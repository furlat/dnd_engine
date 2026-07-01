# Serialization Reference — Frontend Client Guide

This document describes the serialized data structures produced by the D&D engine after the serialization refactor. Use this as a reference for parsing `entity.model_dump(mode='json')` output and combat log entries.

---

## What Changed (Summary)

The engine now produces **crash-free JSON** from any entity at any point in the game. Previously, `model_dump()` would fail on ~13 callable fields and various internal lookup dicts. The refactor:

1. **Excludes non-serializable internals** — Callable fields (`event_processor`, `evaluator`, `prerequisites`, `consequences`, etc.) and redundant lookup indices (`active_conditions_by_uuid`, `event_handlers_by_trigger`, etc.) are excluded from serialization.
2. **Caches contextual modifier results** — When a contextual modifier (e.g., "Frightened gives disadvantage when frightener is visible") is evaluated during gameplay, the result is cached in `cached_results` indexed by `"source_uuid|target_uuid|lineage_uuid"`. The frontend can read these cached results to understand *why* advantage/disadvantage applied.
3. **Adds advantage breakdowns to combat logs** — `AttackLogData`, `SavingThrowLogData`, and `SpellSaveLogData` now carry an `advantage_breakdown` field listing each advantage/disadvantage source by name.
4. **Serializes callable durations** — Conditions with callable durations (e.g., "until frightener is no longer visible") serialize as `"conditional"` instead of crashing.
5. **Adds computed summary fields** — `contextual_immunity_names` on entities, `prerequisite_names`/`consequence_names` on structured actions.

---

## Entity Serialization

Call `entity.model_dump(mode='json')` → valid JSON dict. Top-level structure:

### Core Identity

| Field | Type | Description |
|-------|------|-------------|
| `uuid` | `string` | Entity UUID |
| `name` | `string` | Display name |
| `source_entity_uuid` | `string` | Creator/owner UUID |
| `position` | `[int, int]` | Grid position |
| `faction` | `string \| null` | Faction name (`null` = enemy to all) |
| `weight` | `int` | Weight in pounds |
| `creature_type` | `string` | e.g., `"humanoid"`, `"undead"` |
| `size` | `string` | `"Tiny"` through `"Gargantuan"` |
| `sprite_name` | `string` | Sprite identifier for rendering |
| `is_my_turn` | `bool` | Whether it's this entity's turn |
| `non_blocking` | `bool` | Doesn't block movement if true |

### Component Blocks

| Field | Type | Description |
|-------|------|-------------|
| `ability_scores` | `AbilityScores` | STR, DEX, CON, INT, WIS, CHA (each has `score`, `modifier`) |
| `skill_set` | `SkillSet` | 18 D&D 5e skills |
| `saving_throws` | `SavingThrowSet` | 6 saves |
| `health` | `Health` | `current_hp`, `max_hit_points`, `temp_hp`, resistances |
| `equipment` | `Equipment` | Weapons (4 slots), armor, shield, `attack_bonus`, `ac_bonus` |
| `inventory` | `Inventory` | Item storage |
| `action_economy` | `ActionEconomy` | `actions`, `bonus_actions`, `reactions`, `movement` (each a `ModifiableValue`) |
| `senses` | `Senses` | `visible` cells, `entities`, `objects`, `paths` |
| `spellcasting` | `SpellcastingBlock` | Spell slots, spell attack/DC bonuses |
| `proficiency_bonus` | `ModifiableValue` | Proficiency bonus |

### Conditions

```json
{
  "active_conditions": {
    "Frightened": {
      "name": "Frightened",
      "uuid": "...",
      "source_entity_uuid": "...",
      "target_entity_uuid": "...",
      "condition_category": "condition",
      "duration": { "duration": 3, "duration_type": "rounds", ... },
      "applied": true,
      "sub_conditions": ["uuid-of-child"],
      "linked_conditions": [["target_block_uuid", "condition_uuid"]],
      "parent_condition": null,
      "parent_link": null,
      "child_removal_policy": "none",
      "hazard_filter": "all",
      "condition_stealth_dc": null,
      "tags": ["magical"]
    }
  }
}
```

**Duration serialization:**

| `duration_type` | `duration` field value |
|-----------------|----------------------|
| `"rounds"` | `int` (number of rounds remaining) |
| `"permanent"` | `null` |
| `"until_long_rest"` | `null` |
| `"on_condition"` | `"conditional"` (was a callable, serialized as string) |

### Event Handlers

```json
{
  "event_handlers": {
    "handler-uuid": {
      "name": "Opportunity Attack",
      "uuid": "...",
      "enabled": true,
      "player_toggleable": false,
      "trigger_conditions": [
        {
          "name": "Trigger",
          "event_type": "step_movement",
          "event_phase": "effect",
          "event_source_entity_uuid": null,
          "event_target_entity_uuid": null
        }
      ]
    }
  }
}
```

**Excluded from handlers:** `event_processor` (the callable). Only metadata is serialized.

**Key fields for UI:**
- `enabled` — Show toggle state. Greyed out handlers are disabled.
- `player_toggleable` — If `true`, the player can toggle this handler on/off (e.g., reactions like Shield, Divine Smite).
- `trigger_conditions` — What events this handler reacts to.

### Actions (registered_actions)

```json
{
  "registered_actions": [
    {
      "name": "Attack_MELEE_MAIN",
      "action_category": "attack",
      "target_type": "entity",
      "costs": [{ "cost_type": "actions", "cost": 1, "resource_name": null }],
      "template": true,
      "valid_target_filter": "enemies"
    }
  ]
}
```

**Excluded from actions:** `evaluator`, `resource_evaluator` (on Cost), `prerequisites`, `consequences`, `cost_applier` (on StructuredAction).

**Added computed fields:** `prerequisite_names: List[str]`, `consequence_names: List[str]` — human-readable lists of what an action checks/does.

### Excluded Fields (Not in JSON)

These internal lookup indices are excluded — they're redundant with `active_conditions` and `event_handlers`:

- `active_conditions_by_uuid`
- `active_conditions_by_source`
- `event_handlers_by_trigger`
- `event_handlers_by_simple_trigger`
- `contextual_condition_immunities`

**Replacement:** `contextual_immunity_names: Dict[str, List[str]]` is a computed field that provides condition immunity names without the callable references.

---

## Contextual Modifier Cache (`cached_results`)

### What Are Contextual Modifiers?

Some modifiers depend on game state at evaluation time. For example:
- **Frightened**: Gives disadvantage on attacks *only when the frightener is visible*
- **Prone**: Gives advantage to melee attackers (within 5ft) but disadvantage to ranged attackers
- **Paralyzed**: Grants auto-crit to attackers *within 5ft only*

These are stored as `ContextualAdvantageModifier`, `ContextualNumericalModifier`, etc. on the `self_contextual` or `to_target_contextual` channels of a `ModifiableValue`.

### How the Cache Works

When a contextual modifier is evaluated during gameplay (attack, save, spell), the result is cached:

```json
{
  "name": "Frightened: disadvantage when source visible",
  "uuid": "...",
  "cached_results": {
    "goblin-uuid|hero-uuid|event-lineage-uuid": {
      "name": "Frightened",
      "uuid": "...",
      "value": "Disadvantage",
      "numerical_value": -1,
      "source_entity_uuid": "...",
      "target_entity_uuid": "..."
    }
  }
}
```

**Cache key format:** `"source_uuid|target_uuid|lineage_uuid"`
- `source_uuid` — Entity that owns this modifier
- `target_uuid` — Target entity (or `"none"`)
- `lineage_uuid` — Event lineage UUID (or `"none"` if evaluated outside an event)

**Cache value:** The full Pydantic model of the result modifier (`AdvantageModifier`, `NumericalModifier`, etc.), not a lossy dict.

### Multi-Target / Multi-Hit Scenarios

| Scenario | Cache Entries | Key Difference |
|----------|---------------|----------------|
| Single attack | 1 entry | `"attacker\|target\|lineageA"` |
| Magic Missile 3 darts, same target | 3 entries | Different `lineage_uuid` per dart |
| Fireball 3 targets | 3 entries | Different `target_uuid` per target |
| No active event (at rest) | `"entity\|none\|none"` | Serialization-time evaluation |

### Where to Find Cached Results

In the entity dump, navigate to:
```
entity.equipment.attack_bonus.self_contextual.advantage_modifiers.<uuid>.cached_results
entity.equipment.attack_bonus.self_contextual.value_modifiers.<uuid>.cached_results
entity.equipment.ac_bonus.to_target_contextual.advantage_modifiers.<uuid>.cached_results
entity.equipment.ac_bonus.to_target_contextual.critical_modifiers.<uuid>.cached_results
```

Each `ModifiableValue` has 4 main channels:
- `self_static` — Always-on modifiers on self (no cache, plain values)
- `self_contextual` — Conditional modifiers on self (has `cached_results`)
- `to_target_static` — Always-on modifiers affecting attackers/opponents
- `to_target_contextual` — Conditional modifiers affecting attackers/opponents (has `cached_results`)

And 2 propagated channels (populated during cross-entity evaluation, cleared after):
- `from_target_static` — Copy of opponent's `to_target_static`
- `from_target_contextual` — Copy of opponent's `to_target_contextual`

---

## Combat Log Data Models

Combat logs are delivered as `CombatLogEntry` objects. The `data` field contains type-specific structured data.

### CombatLogEntry

```typescript
interface CombatLogEntry {
  entry_type: CombatLogEntryType;  // "attack", "saving_throw", etc.
  source_name: string;
  source_uuid: string;
  target_name?: string;
  target_uuid?: string;

  // Three verbosity levels (Rich markdown formatted)
  compact: string;   // "{cyan:Hero} {green:hits} {yellow:Skeleton} for {red:7} damage"
  verbose: string;   // Multi-line with roll details
  detailed: string;  // Full modifier breakdowns

  data: Record<string, any>;  // Type-specific structured data (see below)
  success?: boolean;

  // Hierarchical children (AoE sub-events, etc.)
  sub_entries: CombatLogEntry[];

  // Visibility: which entity UUIDs could see this event
  perceiver_uuids: Set<string>;
  // Entities revealed during this event chain
  revealed_entity_uuids: Set<string>;
}
```

### Entry Types

| `entry_type` | `data` Model | Description |
|--------------|-------------|-------------|
| `"attack"` | `AttackLogData` | Melee/ranged attack |
| `"saving_throw"` | `SavingThrowLogData` | Standalone saving throw |
| `"skill_check"` | `SkillCheckLogData` | Skill check |
| `"spell_save"` | `SpellSaveLogData` | Save-based spell effect per target |
| `"spell_damage"` | (dict) | Auto-hit spell damage (Magic Missile dart) |
| `"multi_entity_action"` | `MultiEntityLogData` | AoE/multi-target parent |
| `"movement"` | `MovementLogData` | Movement |
| `"action"` | `SelfActionLogData` | Dash, Dodge, Disengage |
| `"condition_applied"` | (dict) | Condition added |
| `"condition_removed"` | (dict) | Condition removed |
| `"damage_taken"` | (dict) | Damage received |
| `"heal"` | `HealLogData` | Healing |
| `"death"` | (dict) | Entity death |
| `"turn_start"` / `"turn_end"` | `TurnLogData` | Turn boundaries |
| `"entity_spotted"` | `EntitySpottedLogData` | Observer spots hidden entity |
| `"hazard_detected"` | `HazardDetectedLogData` | Observer detects hidden hazard |

### AttackLogData (NEW: `advantage_breakdown`)

```typescript
interface AttackLogData {
  attacker_name: string;
  attacker_uuid: string;
  target_name: string;
  target_uuid: string;
  weapon_name: string;
  weapon_slot?: string;

  // Attack roll
  attack_roll: DiceRollDisplay;
  attack_breakdown: ModifierBreakdown[];  // [{ name: "Prof", value: 2 }, { name: "DEX", value: 2 }]

  // Target AC
  target_ac: number;
  ac_breakdown: ModifierBreakdown[];

  // Outcome
  outcome: "hit" | "miss" | "crit" | "crit_miss";
  is_hit: boolean;
  is_crit: boolean;

  // Damage (only on hit)
  damage_rolls: DamageRollDisplay[];
  total_damage: number;
  target_hp?: number;

  // NEW: Advantage/disadvantage sources
  advantage_breakdown: ModifierBreakdown[];
  // Example: [{ name: "Frightened", value: -1, source: "self_contextual" },
  //           { name: "Prone", value: 1, source: "from_target_contextual" }]
  // value: 1 = advantage, -1 = disadvantage

  // Flags
  is_opportunity_attack: boolean;
  is_long_range: boolean;
  is_threatened: boolean;
}
```

### SavingThrowLogData (NEW: `advantage_breakdown`)

```typescript
interface SavingThrowLogData {
  entity_name: string;
  entity_uuid: string;
  ability: string;  // "strength", "dexterity", etc.
  dc: number;
  roll: DiceRollDisplay;
  bonus_breakdown: ModifierBreakdown[];
  advantage_breakdown: ModifierBreakdown[];  // NEW
  success: boolean;
  source_name?: string;
}
```

### SpellSaveLogData (NEW: `save_advantage_breakdown`)

```typescript
interface SpellSaveLogData {
  caster_name: string;
  caster_uuid: string;
  target_name: string;
  target_uuid: string;
  spell_name: string;
  spell_level: number;

  save_ability: string;
  save_dc: number;
  save_roll: DiceRollDisplay;
  save_bonus_breakdown: ModifierBreakdown[];
  save_advantage_breakdown: ModifierBreakdown[];  // NEW
  save_success: boolean;

  damage_rolls: DamageRollDisplay[];
  base_damage: number;
  final_damage: number;
  damage_type: string;
  target_hp_after?: number;
}
```

### Supporting Types

```typescript
interface ModifierBreakdown {
  name: string;   // "Prof", "DEX", "Frightened", "Prone", etc.
  value: number;  // +2, -1, etc. For advantage: 1 = ADV, -1 = DIS
  source: string; // "self", "from_target", "self_contextual", "from_target_contextual"
}

interface DiceRollDisplay {
  dice_str: string;           // "d20", "1d6"
  results: number[];          // Individual die results
  bonus: number;              // Total bonus
  total: number;              // Final total
  all_d20_rolls?: number[];   // All d20 rolls (when adv/dis)
  d20_used?: number;          // Which d20 was selected
  advantage_status?: string;  // "advantage", "disadvantage", or null
}

interface DamageRollDisplay {
  dice_str: string;                   // "1d6", "2d8"
  dice_results: number[];             // Individual die results
  bonus: number;                      // Damage bonus
  total: number;                      // Total damage
  damage_type: string;                // "Slashing", "Fire", etc.
  bonus_breakdown: ModifierBreakdown[];
}
```

---

## How to Use `advantage_breakdown`

The `advantage_breakdown` array in `AttackLogData` / `SavingThrowLogData` tells the frontend exactly *why* a roll had advantage or disadvantage:

```json
{
  "advantage_breakdown": [
    { "name": "Frightened", "value": -1, "source": "self_contextual" },
    { "name": "Prone", "value": 1, "source": "from_target_contextual" },
    { "name": "Long Range", "value": -1, "source": "self" }
  ]
}
```

- **`value: 1`** = This source grants **advantage**
- **`value: -1`** = This source imposes **disadvantage**
- Net sum > 0 → advantage roll. Net sum < 0 → disadvantage roll. Net sum = 0 → normal roll.

**Display suggestion:** Show each source as a pill/tag next to the roll:
```
Attack: d20(15, 8→8) -1 DIS
  Sources: Frightened [-], Prone [+], Long Range [-]
```

The `source` field indicates where the modifier lives:
- `"self"` / `"self_contextual"` — On the attacker/roller (e.g., Frightened)
- `"from_target"` / `"from_target_contextual"` — From the target (e.g., Prone, Invisible)

---

## Markdown Formatting in Text Fields

The `compact`, `verbose`, and `detailed` text fields use a custom markdown syntax for Rich terminal rendering:

| Syntax | Meaning | Example |
|--------|---------|---------|
| `{cyan:Hero}` | Colored text | Entity names |
| `{green:HIT}` | Green text | Success outcomes |
| `{red:MISS}` | Red text | Failure outcomes |
| `{bold yellow:CRIT!}` | Bold colored | Critical hits |
| `{bold red:15}` | Bold red | Damage numbers |
| `**text**` | Bold | Emphasis |

The frontend should strip or convert these tags to its own styling system.
