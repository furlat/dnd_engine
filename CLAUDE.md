# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

D&D 5e game engine with event-driven architecture and component-based entities. The engine models D&D mechanics through interconnected subsystems: registry, entity-component framework, modifiable values, events, conditions, and actions.

**Core Principle**: All game state changes flow through events.

## Working With This Codebase (CRITICAL)

**The user (Tommaso) is the architect and designer of this codebase.** Claude is here to assist, not to drive. This codebase has specific design decisions - ask before assuming.

### Workflow: Plan → Explore → Implement → Test

1. **Use Plan Mode for non-trivial tasks.** Before writing code, enter plan mode to explore the codebase and design an approach. Present the plan for user approval before implementing.

2. **Use sub-agents aggressively for context gathering.** Dispatch parallel Explore agents to read related files, grep for patterns, and understand existing code. Don't try to hold everything in your head - delegate research to sub-agents and synthesize their findings.

3. **Test after every change.** Run the relevant `examples/test_*.py` files to validate. If a test doesn't exist for what you're changing, write one first.

4. **Document bugs found during implementation.** When running tests for a feature, if you discover failing tests or suspect bugs in unrelated code, **dispatch a background sub-agent** to document them in `KNOWN_ISSUES.md` (next to CLAUDE.md) while you keep working. Don't stop your flow - log it and move on.

5. **Report failures immediately.** If something doesn't work, say so and ask for guidance. Don't silently try alternative approaches or chain speculative fixes.

### Sub-Agent Patterns (USE THESE)

| Pattern | When |
|---------|------|
| **Parallel Explore agents** | Starting a task - dispatch 2-4 agents to read related files simultaneously |
| **Background bug documentation** | Found a failing test unrelated to your task - background agent writes to KNOWN_ISSUES.md |
| **Plan agent** | Complex feature - let a Plan agent design the approach before you implement |
| **Test runner agent** | After implementation - agent runs tests and reports results |

### Testing Rules

- **NEVER run `pytest` on the entire test suite.** It takes hours and hangs. Always run individual test files: `python examples/test_<feature>.py`
- **NEVER run server tests** (`examples/server_tests/`) in batch — they require a running server and will hang.
- **Always run tests** for the feature you're modifying: `python examples/test_<feature>.py`
- **To validate regressions**, run a few specific related test files individually, NOT `pytest` with no arguments.
- **When tests fail** on code you didn't touch: don't fix them silently. Document in `KNOWN_ISSUES.md` with the test file, error, and your hypothesis. Dispatch a background sub-agent for this.
- **Write new tests** for new features using patterns from `claude_docs/IMPLEMENTATION_GUIDE.md` (Section 14)

### Dependency Direction (NO CIRCULAR IMPORTS)

**CRITICAL**: Never use "late imports", "import inside function", or `TYPE_CHECKING` to avoid circular imports. These all hide the design problem instead of fixing it. Zero late imports. Zero circular dependencies. If you feel the need for any of these, the code is in the wrong place.

**The Rule**: Dependencies flow DOWN the hierarchy, never UP.

```
Entity (high-level)
   ↓ owns
Senses, Equipment, Health (blocks/components)
   ↓ uses
ModifiableValue, Modifiers (primitives)
   ↓ uses
BaseObject, BaseBlock (base classes)
```

**Correct**: `Entity` imports and uses `Senses` (owner uses component)
**Wrong**: `Senses` imports `Entity` (component reaching back to owner)

**Example - where to put `is_threatened()`**:
- This method needs to query other entities via `Entity.get()`
- `Senses` cannot import `Entity` (circular!)
- Therefore `is_threatened()` belongs on `Entity`, not `Senses`
- Entity can call `other_entity.senses.get_threathened_positions()` - that direction is fine

**If you find yourself wanting to import "up" the hierarchy**:
1. STOP - the method is in the wrong place
2. Move it to the higher-level class that already has access to both
3. Or pass the needed data as parameters instead of importing

## Common Commands

```bash
source .venv/bin/activate              # Activate venv
pip install -e .                        # Install dev mode
python examples/test_<feature>.py      # Run specific test (NEVER use pytest on full suite)
pyright                                 # Type checking
```

## Architecture Overview

### Three-Tier Ownership Hierarchy

```
BaseObject (dnd/core/base_object.py)
    │   Global registry, UUID-based lookup
    │   All objects have: uuid, source_entity_uuid, target_entity_uuid
    │
    └── BaseBlock (dnd/core/base_block.py)
            │   Container for ModifiableValues
            │   Manages conditions, handlers, context
            │   Condition lifecycle: add_condition(), remove_condition(), _remove_condition_tree()
            │   advance_duration() - ticks condition durations and auto-removes expired ones
            │
            └── Entity (dnd/entity.py)
                    Main game object composed of specialized blocks
                    Class-level registries: _entity_registry, _entity_by_position
```

### Entity Composition

```
Entity
├── ability_scores: AbilityScores     # STR, DEX, CON, INT, WIS, CHA (each has score + modifier)
├── skill_set: SkillSet               # 18 D&D 5e skills, linked to abilities
├── saving_throws: SavingThrowSet     # 6 saves, linked to abilities
├── health: Health                    # HP, hit dice, temp HP, damage resistances
├── equipment: Equipment              # Weapons (4 slots: MELEE_MAIN/OFF, RANGED_MAIN/OFF), armor, shield, AC
├── inventory: Inventory              # Item storage (slots, weight capacity, find/transfer)
├── action_economy: ActionEconomy     # actions, bonus_actions, reactions, movement
├── senses: Senses                    # position, visible cells, paths, visible entities, visible objects
├── proficiency_bonus: ModifiableValue
├── weight: int                       # Weight in pounds (default 150, used for Shove weight limit)
├── faction: Optional[str]            # Faction name for ally/enemy detection (None = enemy to all)
├── active_conditions: Dict[str, BaseCondition]
└── active_conditions_by_uuid / by_source (lookup dicts)
```

### Item Hierarchy

```
BaseBlock
└── BaseItem (dnd/blocks/base_item.py)
    │   Location tracking: owner_uuid, stored_in_uuid, tile_uuid, is_equipped
    │   Lifecycle hooks: _on_loot(), _on_drop(), _on_destroy()
    │   Health/damage for breakable items, GridMap integration
    │   Stacking: stack_id, stack_count, max_stack
    │
    ├── EquippableItem
    │   │   Equip/unequip hooks: _on_equip(slot, entity_uuid), _on_unequip(slot, entity_uuid)
    │   │   is_equippable=True, is_pickable=True
    │   │   Three hook approaches: direct modifiers, action registration, conditions
    │   │
    │   ├── Weapon (dnd/blocks/equipment.py)
    │   ├── Armor (+ subtypes: BodyArmor, Helmet, Gloves, Boots, Cloak, Amulet)
    │   └── Shield
    │
    └── UsableItem (dnd/blocks/base_item.py)
        │   is_usable=True, provides actions via get_use_actions(user_entity_uuid)
        │   Two patterns: use_action_templates field (default) or override get_use_actions()
        │   Charges: charges (-1=unlimited, 0=depleted), consume_charge(), is_consumable
        │   Stack-aware consumption: pops from stack_count before destroying
        │
        ├── SpellScroll (dnd/items/test_items.py) — consumable, wraps SpellAction
        ├── HealingPotion — consumable, SELF target, stackable
        ├── WeaponCoat — consumable, applies condition to equipped weapon
        └── Environment objects (is_pickable=False): doors, levers, chests, cannons
```

**Location tracking fields on BaseItem:**
- `owner_uuid` — Entity or item (e.g. chest) that owns this; position defers to owner
- `stored_in_uuid` — Container block UUID (Inventory block or Equipment block)
- `tile_uuid` — Tile UUID when on floor (item has its own position)
- `is_equipped` — Boolean flag
- `equipped_slot` — String value of the slot enum when equipped

**Slot enums** (`dnd/core/events.py`): `WeaponSlot`, `BodyPart`, `RingSlot`, `EquipmentSlot` (union of all three)

### Global Registries

- `BaseObject._registry: Dict[UUID, BaseObject]` - All objects by UUID
- `Entity._entity_registry: Dict[UUID, Entity]` - All entities
- `Entity._entity_by_position: DefaultDict[Tuple[int,int], List[Entity]]` - Entities by grid position

## The Event System

The event system (`dnd/core/events.py`) is the backbone of the engine. **All game state changes flow through events**.

### Event Lifecycle

```
DECLARATION → EXECUTION → EFFECT → COMPLETION (or CANCEL)
```

Each `phase_to()` creates new event with same `lineage_uuid`. EventQueue notifies matching handlers at each phase **except COMPLETION**.

**CRITICAL: COMPLETION phase skips all EventHandlers.** This is by design - it separates the causal boundary:
- **DECLARATION → EFFECT**: Handlers can react, modify, or spawn child events (e.g., opportunity attacks on MOVEMENT, reroll on DAMAGE_ROLL_RESULT). These are inside the causal chain.
- **COMPLETION**: No handlers fire. Instead, a **callback** generates the combat log and delivers it to the Encounter. This is *after* the causal chain - purely observational.

**Why this matters**: If you register a handler on `EventPhase.COMPLETION`, it will **never fire**. EventQueue line 631 explicitly returns early. Use EFFECT phase for reactions, COMPLETION is reserved for combat log generation via callback.

### Key EventTypes

| Type | Purpose |
|------|---------|
| `ATTACK` | Attack action |
| `MOVEMENT` | Move action (triggers OA when leaving threat) |
| `FORCED_MOVEMENT` | Push/pull movement (does NOT trigger OA) - used by Shove, Thunderwave |
| `D20_ROLL_RESULT` | After d20 rolled, before outcome (for Lucky, Portent, etc.) |
| `DAMAGE_ROLL_RESULT` | After damage dice rolled, before applied (for GWF, Savage Attacker) |
| `TAKE_DAMAGE` | Damage application |
| `SAVING_THROW` | Save requested/resolved |
| `SKILL_CHECK` | Skill check (e.g., Athletics contest for Shove) |
| `CONDITION_APPLICATION` | Condition added |
| `CONDITION_REMOVAL` | Condition removed |
| `CAST_SPELL` | Spell cast (triggers Hidden/Invisible reveal) |
| `BASE_ACTION` | Any action execution (triggers Hidden/Invisible reveal for non-whitelisted actions) |
| `SPATIAL_ENTITY_ENTERED` | Entity moved into cell |
| `SPATIAL_PERCEIVABILITY_CHANGED` | Entity's perceivability changed (hidden/revealed/invisible) — triggers senses re-evaluation, NOT zone effects |

### EventHandlers

An `EventHandler` wraps a callback (`EventProcessor`) and a list of `Trigger` conditions that determine when it fires.

```python
# EventProcessor signature:
Callable[[Event, UUID], Optional[Event]]  # (event, source_entity_uuid) -> Optional[Event]

# Trigger fields:
Trigger(
    name: str,
    event_type: EventType,              # ATTACK, MOVEMENT, DAMAGE_ROLL_RESULT, etc.
    event_phase: EventPhase,            # DECLARATION, EXECUTION, EFFECT
    event_source_entity_uuid: Optional[UUID],  # Filter by event source
    event_target_entity_uuid: Optional[UUID],  # Filter by event target
)
```

When an event is registered with EventQueue, it finds matching handlers by trigger and calls their processor. The processor can return None (no-op), the same event, or a modified/canceled event.

**Registration (IMPORTANT - only use ONE method):**
- `entity.add_event_handler(handler)` - **Preferred**. Auto-registers with EventQueue AND tracks on the entity for cleanup.
- `EventQueue.add_event_handler(handler)` - Direct registration, doesn't track on entity.

**DO NOT call both** - this registers the handler twice and it will fire twice!

For dice manipulation patterns (Great Weapon Fighting, etc.), see `claude_docs/IMPLEMENTATION_GUIDE.md`.

### SpatialHandlers (Zone Spells)

`SpatialHandler` is a position-indexed variant of `EventHandler` for zone effects (Spike Growth, Web, Spirit Guardians). Instead of matching by trigger conditions, it fires at specific grid positions via O(1) lookup.

**Key differences from EventHandler:**
- No `trigger_conditions` - position filtering replaces trigger matching
- Stored in a **separate registry** (`_spatial_handlers`, not `_event_handlers`)
- Found via position index: `_spatial_handlers_by_position[(event_type, phase)][position]`

```python
SpatialHandler(
    positions: Set[Tuple[int, int]],     # Grid positions this handler fires at
    event_type: EventType,                # Usually SPATIAL_ENTITY_ENTERED or SPATIAL_ENTITY_LEFT
    event_phase: EventPhase,              # Usually EFFECT
    event_processor: EventProcessor,      # Same callback signature as EventHandler
)
```

**Registration**: `EventQueue.add_spatial_handler(handler, positions, event_type, event_phase)`
**Zone movement**: `EventQueue.update_spatial_handler_positions(handler_uuid, new_positions, ...)` - uses delta computation (only adds/removes changed positions)

**Flow when entity enters a zone:**
1. GridMap fires `SPATIAL_ENTITY_ENTERED` event with `position` and `entity_uuid`
2. EventQueue detects spatial event type, does O(1) lookup by position
3. All SpatialHandlers registered at that position fire their processor
4. Processor performs zone effect (damage, save, condition application)

**Conditions return spatial handler UUIDs** from `_apply()` in the 4th tuple position. The condition stores these for cleanup when removed:

```python
# In ZoneControlCondition._apply():
handler = self._create_zone_entry_handler()
EventQueue.add_spatial_handler(handler, self.affected_positions, ...)
spatial_handler_uuids.append(handler.uuid)
return modifiers, handler_uuids, sub_conditions, spatial_handler_uuids, effect_event
```

See `dnd/tile_conditions.py` (`ZoneControlCondition`) and `dnd/spells/transmutation.py` (`SpikeGrowthZone`) for full examples.

### Combat Log System (`dnd/core/combat_log.py`)

**How it works**: Each Event subclass overrides `generate_combat_log()` → returns a `CombatLogEntry` (or None). At COMPLETION phase, `Event.phase_to()` automatically:
1. Calls `generate_combat_log()` on the event
2. Collects child event logs via `_collect_child_combat_logs()` → populates `sub_entries`
3. If top-level event (no `parent_event`), fires the callback set by Encounter

**Hierarchical sub_entries** mirror the parent-child event tree. This is how AoE/multi-target works:

```
Fireball (MULTI_ENTITY_ACTION) → "Wizard uses Fireball → 3 targets, 42 total damage"
├── sub_entry (SPELL_SAVE) → "Skeleton 1: DEX save FAIL, 15 fire damage"
│   └── sub_entry (DAMAGE_TAKEN)
├── sub_entry (SPELL_SAVE) → "Skeleton 2: DEX save SAVE, 7 fire damage (half)"
│   └── sub_entry (DAMAGE_TAKEN)
└── sub_entry (SPELL_SAVE) → "Skeleton 3: DEX save FAIL, 15 fire damage"
    └── sub_entry (DAMAGE_TAKEN)
```

The convolution loop in `BaseAction.apply()` creates a child event per target (each with its own `lineage_uuid`). The parent event's `_collect_child_combat_logs()` gathers them, de-duplicating by `lineage_uuid`.

**Three verbosity levels** with Rich markdown (`{color:text}`, `**bold**`):
- `compact`: `"{cyan:Hero} {green:hits} {yellow:Skeleton} for {red:7} damage"`
- `verbose`: Adds roll details: `"Attack: d20(15) +4 = 19 vs AC 13 → HIT"`
- `detailed`: Full modifier breakdowns: `"[Prof +2, DEX +2]"`

**parent_event threading**: All `add_condition()`/`remove_condition()` calls pass `parent_event=event` so condition logs appear as nested sub-entries of the action that triggered them (not standalone top-level entries). `ConditionApplicationEvent` and `ConditionRemovalEvent` both implement `generate_combat_log()`.

**Entry types**: `ATTACK`, `MOVEMENT`, `ACTION`, `SAVING_THROW`, `SKILL_CHECK`, `CONDITION_APPLIED`/`REMOVED`, `DAMAGE_TAKEN`, `HEAL`, `DEATH`, `TURN_START`/`END`, `MULTI_ENTITY_ACTION`, `SPELL_SAVE`, `SPELL_DAMAGE`, `ENTITY_SPOTTED`

**Typed data models** in `data` field: `AttackLogData`, `MovementLogData`, `SavingThrowLogData`, `SpellSaveLogData`, `MultiEntityLogData`, etc.

- `ModifiableValue.get_breakdown()` / `get_advantage_breakdown()` - For modifier display

## The ModifiableValue System

`ModifiableValue` (`dnd/core/values.py`) is the core building block for any modifiable stat. It has **6 modification channels**:

### Four Primary Channels (set by conditions/effects)

| Channel | Purpose | Example |
|---------|---------|---------|
| `self_static` | Always applies to self | Poisoned: disadvantage on attacks |
| `self_contextual` | Conditional, evaluated at runtime | Frightened: disadvantage only when frightener visible |
| `to_target_static` | Always applies to entities targeting this entity | Blinded: attackers have advantage |
| `to_target_contextual` | Conditional for targeting entities | Prone: advantage if ≤5ft, disadvantage if >5ft |

### Two Propagation Channels (populated via set_from_target)

| Channel | Populated By |
|---------|--------------|
| `from_target_static` | `set_from_target()` copies target's `to_target_static` |
| `from_target_contextual` | `set_from_target()` copies target's `to_target_contextual` |

### Computed Properties

Each ModifiableValue computes final values by aggregating all 6 channels:

- `normalized_score` - Final numerical value (sum of all value modifiers, clamped by min/max)
- `advantage` - Final advantage status (ADVANTAGE if sum > 0, DISADVANTAGE if < 0, NONE if 0)
- `critical` - Critical status (AUTOCRIT, NOCRIT, or NONE)
- `auto_hit` - Auto-hit status (AUTOHIT, AUTOMISS, or NONE)

### Modifier Types (`dnd/core/modifiers.py`)

| Type | Values | Used For |
|------|--------|----------|
| `NumericalModifier` | int | Bonuses, penalties, DC values |
| `AdvantageModifier` | ADVANTAGE (+1), DISADVANTAGE (-1) | Attack rolls, ability checks |
| `CriticalModifier` | AUTOCRIT, NOCRIT | Paralyzed auto-crit |
| `AutoHitModifier` | AUTOHIT, AUTOMISS | Charmed can't attack charmer |
| `ResistanceModifier` | RESISTANCE, VULNERABILITY, IMMUNITY | Damage types |

Each has a **Contextual** variant (e.g., `ContextualAdvantageModifier`) that takes a callable returning the modifier or None.

### Cross-Entity Modifier Propagation

**Critical Pattern**: When one entity affects another, `to_target` modifiers must be propagated via `set_from_target()`. Example: Blinded adds ADVANTAGE to `ac_bonus.to_target_static` → attacker calls `attack_bonus.set_from_target(ac)` to pull in that advantage. Always `reset_from_target()` + `clear_target_entity()` after.

### Entity Methods: Low vs High Level

| Method | Level | Handles Propagation | Use Case |
|--------|-------|---------------------|----------|
| `attack_bonus(slot, target)` | Low | No | Building blocks |
| `ac_bonus(target)` | Low | No | Building blocks |
| `skill_bonus(target, skill)` | **High** | **Yes** | Direct use |
| `saving_throw_bonus(target, ability)` | **High** | **Yes** | Direct use |
| `skill_bonus_cross(target, skill)` | **High** | **Yes** | Returns both parties' bonuses |
| `saving_throw(request)` | **High** | **Yes** | Full save execution |
| `skill_check(request)` | **High** | **Yes** | Full check execution |

The **Attack action** (`dnd/actions.py`) handles propagation for combat.

## The Condition System

### Condition Lifecycle

1. **Creation**: `condition = Blinded(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)`
2. **Application**: `target.add_condition(condition)` → calls `condition.apply()`
3. **Effect**: Modifiers are added to appropriate channels
4. **Removal**: `target.remove_condition("Blinded")` → BaseBlock drives full cleanup tree

### Implementing a Condition

```python
class MyCondition(BaseCondition):
    name: str = "MyCondition"
    description: str = "Description here"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
    ]:
        target = Entity.get(self.target_entity_uuid)
        outs = []

        modifier_uuid = target.equipment.attack_bonus.self_static.add_advantage_modifier(
            AdvantageModifier(
                name="MyCondition",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=self.target_entity_uuid,
                target_entity_uuid=self.source_entity_uuid
            )
        )
        outs.append((target.equipment.attack_bonus.uuid, modifier_uuid))

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return outs, [], [], [], effect_event  # 5-tuple
```

See `claude_docs/IMPLEMENTATION_GUIDE.md` for full condition implementation patterns.

### Sub-conditions Pattern (Same Entity)

Conditions like Paralyzed include Incapacitated as a sub-condition on the **same entity**:

```python
# In Paralyzed._apply():
sub_conditions_uuids: List[UUID] = []
incapacitated = Incapacitated(
    source_entity_uuid=self.source_entity_uuid,
    target_entity_uuid=self.target_entity_uuid,
    parent_condition=self.uuid  # Links child to parent
)
target.add_condition(incapacitated)
sub_conditions_uuids.append(incapacitated.uuid)

return outs, [], sub_conditions_uuids, [], effect_event  # 5-tuple
# When Paralyzed is removed, Incapacitated is automatically removed too
```

### Condition Removal (BaseBlock-Driven)

**IMPORTANT**: Condition removal is a **BaseBlock responsibility**, not a BaseCondition responsibility. Since both Entity and Tile inherit from BaseBlock, this provides unified condition removal across all block types.

```
BaseBlock.remove_condition(name) → BaseBlock._remove_condition_tree(condition)
  ├── Recurse into sub_conditions (same block, parent-child)
  ├── Recurse into linked_conditions (other BaseBlocks via BaseBlock.remove_condition_by_uuid)
  └── Call condition.cleanup_own_state() (removes own modifiers/handlers only)
```

**Two condition linkage types on BaseCondition:**
- `sub_conditions: List[UUID]` - Child conditions on **same block** (e.g., Paralyzed → Incapacitated)
- `linked_conditions: List[Tuple[UUID, UUID]]` - Conditions on **other BaseBlocks** (entities, tiles, items) (e.g., Concentrating → HoldPersonEffect on target, zone spells → tile conditions). Added via `add_linked_condition(target_block_uuid, condition_uuid)`.

**Example - Concentration Spell cleanup chain:**
```
Caster: Concentrating(spell_name="Hold Person")
            │ linked_conditions
            └──► Target: HoldPersonEffect
                        │ sub_conditions
                        └──► Paralyzed
```
When concentration breaks, `BaseBlock._remove_condition_tree()` traverses the entire tree: removes HoldPersonEffect from target, which removes Paralyzed as sub-condition.

### Modifier Placement Guide

| Effect Type | Channel | Example |
|-------------|---------|---------|
| Affects own rolls | `self_static` | Poisoned: disadvantage on own attacks |
| Affects own rolls conditionally | `self_contextual` | Frightened: only when frightener visible |
| Affects attackers | `to_target_static` | Blinded: attackers have advantage |
| Affects attackers conditionally | `to_target_contextual` | Prone: melee=advantage, ranged=disadvantage |
| Numerical bonus/penalty | `self_static.add_value_modifier()` | Dashing: +30 movement |
| Max constraint | `self_static.add_max_constraint()` | Grappled: speed max = 0 |

## The Action System

Actions (`dnd/core/base_actions.py`, `dnd/actions.py`) modify game state through events.

### ActionCategory Enum

Every action has an `action_category` field that classifies it. Replaces the old duck-typing pattern (`_is_attack`/`_is_spell` getattr hacks).

```python
class ActionCategory(str, Enum):
    ABILITY = "ability"      # Default: Dash, Dodge, Disengage, etc.
    ATTACK = "attack"        # Attack, Extra Attack, Retaliation, Frenzied Strike
    SPELL = "spell"          # SpellAction (Fire Bolt, Fireball, etc.)
    MOVEMENT = "movement"    # Move, Jump
```

Properties on BaseAction: `is_attack`, `is_spell`, `is_movement` — type-safe checks.

### BaseAction Flow

```
BaseAction.apply()
├── check_costs() → validates affordability
├── _validate() → returns EXECUTION or CANCEL
├── _apply() → EXECUTION → EFFECT → COMPLETION
└── _apply_costs() → deducts from action_economy
```

### Template-Based Actions

Actions are registered as templates on entities with `template=True`:

```
Entity.action_templates → get_available_actions() → AvailableActionsResult
    ├── entity_actions (attacks with valid_targets)
    ├── position_actions (Move, Jump - position-based actions)
    ├── self_actions (dash, dodge, disengage)
    └── object_actions (Pick Up, Attack Object - targeting floor items)
```

### Three-Source Action Discovery

`get_available_actions()` gathers actions from three sources:

| Source | Mechanism | Discovery Time |
|--------|-----------|----------------|
| 1. Registered | `entity.registered_actions` (templates) | At registration |
| 2. Inventory | `entity.inventory.get_all_use_actions(uuid)` | Query time |
| 3. Environment | `senses.objects` → `obj.get_use_actions(uuid)`, ≤5ft | Query time |

Use actions have `is_item_use=True` and `source_item_uuid` on `AvailableActionInfo`. They are routed by `execute_by_index()` to `execute_use_action()` automatically.

**Functional API** (`dnd/actions_functional.py`):
- `setup_standard_actions(entity)` - Registers Move, Jump, Dash, Dodge, Disengage + weapon attacks
- `execute_by_index(entity, name, idx)` - Execute by target index (routes item use actions automatically)
- `execute_use_action(entity, item_uuid, action_name, target)` - Execute a use action from a UsableItem

### Attack Action

Attack validates range and LOS, then:
1. Cross-propagate modifiers via `set_from_target()`
2. Roll d20 with attack bonus vs AC
3. Apply damage on hit

**AttackEvent fields**: `dice_roll`, `attack_outcome`, `damages`, `damage_rolls`

### Cost Types

`actions`, `bonus_actions`, `reactions`, `movement` + optional `resource_name/resource_cost`

## Implemented Features

### Conditions & Class Features

All D&D conditions are in `dnd/conditions.py` — read the class definitions for effect details (self effects, attacker effects, sub-conditions).

Fighter features (L1-18 + Champion): `dnd/classes/fighter.py`, `dnd/classes/fighter_factory.py`. Barbarian features (L1-20 + Berserker): `dnd/classes/barbarian.py`, `dnd/classes/barbarian_factory.py`, `dnd/classes/rage.py`.

See `claude_docs/CLASS_SYSTEM.md` for complete feature tables, the `_remove()` cleanup pattern, and implementation examples.

### Spell System

40+ spells across 7 schools. See `dnd/spells/__init__.py` for `CANTRIPS` through `LEVEL_9_SPELLS` dictionaries and `ALL_SPELLS` lookup.

**Base classes**: `SpellAction(BaseAction)` and `SpellEvent(ActionEvent)` in `dnd/actions.py`.

**Registration**:

```python
from dnd.actions_functional import register_spell, register_spells_by_name
register_spell(entity, FireBolt, caster_level=5)
register_spells_by_name(entity, ["Fire Bolt", "Magic Missile"], caster_level=5)
```

**Entity spell API**: `spell_attack_bonus(target_uuid)`, `spell_save_dc()`, `has_spell_slot(level)`, `is_spellcaster`. See `dnd/entity.py` for full list.

**SpellcastingBlock** (`dnd/blocks/spellcasting.py`): Holds `spell_attack_bonus`, `spell_damage_bonus`, `spell_dc_bonus`, `spell_crit_threshold`, `spellcasting_ability`.

**AoE**: `TargetType.POSITION_AOE` + `aoe_shape` (Sphere, Cone, Line, Cube). See `claude_docs/archive/AOE_TARGETING_REFERENCE.md`.

#### Concentration System

Concentration spells are fully implemented:
- **One spell limit**: Casting a new concentration spell ends the old one
- **CON saves on damage**: DC = max(10, damage/2)
- **Automatic cleanup**: Uses `linked_conditions` to clean up spell effects on targets when concentration breaks
- **Spell-specific effects**: Each concentration spell creates a spell-specific condition (e.g., `HoldPersonEffect`) with the actual effect (e.g., `Paralyzed`) as a sub-condition

See `examples/test_concentration.py` and `examples/test_concentration_spells.py` for tests.

#### Stealth System (Layer 1)

Perceivability filtering on senses. See `claude_docs/VISION_HIDING_COVER_PLAN.md` for full details.

- **BaseBlock flags**: `stealth_dc`, `is_invisible` — condition-agnostic, set by Hidden/Invisible conditions
- **`is_perceivable_by(requesting_entity_uuid)`** — polymorphic on BaseBlock, delegates to `get_passive_perception()` / `can_bypass_invisibility()` overrides
- **SPATIAL_PERCEIVABILITY_CHANGED event** — lightweight event that triggers senses re-evaluation without firing SpatialHandlers
- **Hidden condition** — sets `stealth_dc` flag, grants unseen attacker advantage, removed on attack/damage/incapacitated
- **Hide action** — costs 1 action, rolls Stealth check, applies Hidden condition
- **Invisible condition** — sets `is_invisible` flag, senses-based advantage/disadvantage (shared `unseen_attacker_advantage`/`unseen_target_disadvantage` callables)
- **Armor stealth disadvantage** — `StealthDisadvantageBodyArmor` subclass in `armors.py` applies DISADVANTAGE to stealth skill on equip
- **InvisibilityEffect** — spell-based `Invisible`, auto-removed on attack/spell/revealing action via `invisibility_reveal_processor`
- **GreaterInvisibilityEffect** — BG3-style, rolls Stealth check vs escalating DC (base 15) to maintain invisibility on action
- **NON_REVEALING_ACTIONS** — `{"Dash", "Dodge", "Disengage", "Hide", "Stand Up", "Drop Prone"}` — whitelisted actions that don't break Hidden/Invisible
- **Three Invisible variants**: `Invisible` (basic permanent), `InvisibilityEffect` (spell, auto-remove), `GreaterInvisibilityEffect` (spell, Stealth check) — all share `name="Invisible"` and use same BaseBlock `is_invisible` flag
- **creation_lineage_uuid** — Hidden/InvisibilityEffect/GreaterInvisibilityEffect store the lineage UUID of the event that created them, preventing self-triggering (e.g., Hide action applying Hidden doesn't immediately reveal)
- **Reveal handler pattern** — EventHandler with triggers on ATTACK/CAST_SPELL/BASE_ACTION at EFFECT phase, processor checks `NON_REVEALING_ACTIONS`, verifies lineage, calls `remove_condition` with `parent_event=event`

#### Lighting System (Layer 2) — IMPLEMENTED

Per-tile light levels with dynamic light sources, sense modes (Darkvision, Truesight, etc.), zone spell light effects, and incremental senses updates. See `claude_docs/LIGHTING_SYSTEM.md` for full documentation.

#### Not Yet Implemented

- **Spell duration/expiration** - Long rest, short rest, timed durations
- **Cover** - Layer 3 of stealth system (see `claude_docs/VISION_HIDING_COVER_PLAN.md`)

## Code Quality

### Code Verification Rules

**CRITICAL: Before writing any code that uses existing classes/methods:**

1. **Never assume method/attribute names** - Always read the actual class definition first
2. **Check existing examples** - Look at `examples/combat_basic.py` or `examples/combat_conditions.py` for correct usage patterns
3. **Verify imports exist** - Grep for `class ClassName` to find where things are defined
4. **Check Config classes** - Many classes have `*Config` counterparts with different field structures (e.g., `AbilityConfig` vs raw int)
5. **Test imports before running** - Run `python -c "import module_name"` to catch import errors early

**Common pitfalls in this codebase:**
- `entity.has_hp` — boolean property, True if HP > 0. Only on Entity and BaseItem (things with health).
- `block.is_active` — boolean property, universal on BaseBlock. True if functional (Entity delegates to `has_hp`, non-health blocks always True). Use for polymorphic filtering.
- `entity.get_hp()` — int, actual HP value. Use only when you need the number. Never use `get_hp() > 0` for filtering — use `has_hp` or `is_active`.
- `Entity.get_hp()` returns current HP, NOT `entity.health.current_hit_points` (doesn't exist)
- `AbilityScoresConfig` takes `AbilityConfig` objects, not raw integers
- `Weapon` requires `source_entity_uuid`, `dice_numbers`, and proper `ModifiableValue` for bonuses
- `RangeType` is in `dnd/core/events.py`, not `dnd/blocks/equipment.py`
- Always use bestiary factories (`create_goblin`, `create_skeleton`) as reference for entity creation
- **Bestiary factories use keyword args**: `create_goblin(name="Name", position=(0,0))` NOT `create_goblin("Name", ...)`
- **Weapon slots**: Use `entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)` to get weapons. 4 slots: `MELEE_MAIN`, `MELEE_OFF` (can hold shield), `RANGED_MAIN`, `RANGED_OFF`. Use `entity.equipment.get_item_by_slot(slot)` for any slot type (WeaponSlot, BodyPart, RingSlot).
- **Slot enums**: `WeaponSlot`, `BodyPart`, `RingSlot`, `EquipmentSlot` are ALL in `dnd/core/events.py` (not equipment.py)
- **Weapon/Armor/Shield inherit from EquippableItem** (not BaseBlock). They have location tracking and equip hooks.
- **Ability modifier is int**: `entity.ability_scores.strength.modifier` returns `int`, not `ModifiableValue`
- **Always call `Entity.update_all_entities_senses()`** after creating entities for LOS to work
- **EventHandler registration**: Only call `entity.add_event_handler(handler)` - it auto-registers with EventQueue. Do NOT also call `EventQueue.add_event_handler()` or handler fires twice!
- **ActionCategory enum**: Use `action_category=ActionCategory.ATTACK` (not `_is_attack=True`). Duck typing removed. Enum values: `ABILITY`, `ATTACK`, `SPELL`, `MOVEMENT`.
- **UsableItem actions**: `get_use_actions()` returns fresh copies with `source_entity_uuid` injected. Never modify templates in place.
- **Item use routing**: `execute_by_index()` auto-routes `is_item_use` actions to `execute_use_action()`. Don't call both.
- **SpellScroll pattern**: Uses `_create_variant()` to wrap SpellAction with item costs (action only, no spell slot). Set `charge_cost` for variable charge consumption.

**For writing examples and tests**, see `claude_docs/IMPLEMENTATION_GUIDE.md` (Section 14) for complete patterns.

### Type Checking and Linting

This project uses **Pylance** (VS Code's Python language server) with strict type checking enabled. All code should pass Pylance checks with zero errors.

#### Getting Pylance Errors

**Two ways to access diagnostics:**
- **`mcp__ide__getDiagnostics`** tool - Returns Pylance diagnostics directly from VS Code (preferred, structured output with file/line/severity)
- **`pyright`** CLI - Installed in `.venv/bin/pyright`, configured in `pyproject.toml` (typeCheckingMode: "basic")
- The user may also paste errors directly from VS Code

#### Common Type Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `reportUnusedVariable` | Variable assigned but never read | Rename to `_` (e.g., `for _, value in items()`) |
| `reportUnusedImport` | Import not used in file | Remove the import (but verify it's truly unused first!) |
| `reportArgumentType` | Wrong type passed to function | Use `cast()`, add type narrowing with `isinstance()`, or fix the type |
| `reportAssignmentType` | Assigning wrong type to typed variable | Use `cast()` or fix the assignment |
| `reportCallIssue: No parameter named X` | Custom `__init__(self, **kwargs)` hides Pydantic's field-aware signature | Use `model_post_init` instead of `__init__` (see below) |

#### Pydantic + Pylance: Use `model_post_init`, NEVER `__init__`

**CRITICAL**: Never define `def __init__(self, **kwargs)` on Pydantic models. This overrides Pydantic's auto-generated `__init__`, making Pylance see `(**kwargs)` instead of named field parameters — causing "No parameter named X" errors everywhere.

Instead, use `model_post_init` — Pydantic v2's official post-init hook:

```python
# BAD: Overrides Pydantic's __init__, breaks Pylance
class MyAction(BaseAction):
    costs: List[Cost] = []
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.costs = [Cost(...)]

# GOOD: Preserves Pydantic's field-aware __init__
class MyAction(BaseAction):
    costs: List[Cost] = []
    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [Cost(...)]
```

All base classes (`BaseObject`, `BaseBlock`, `Event`, `Entity`) use `model_post_init` for registry registration. Subclasses that need post-init logic MUST also use `model_post_init` and call `super().model_post_init(__context)`.

#### Type Narrowing Patterns

```python
# For Union types, use isinstance() or assert for narrowing
slot: Union[BodyPart, RingSlot, WeaponSlot]
if slot in slot_mapping:  # Pylance doesn't narrow from this
    assert isinstance(slot, BodyPart)  # This narrows the type
    name = slot_mapping[slot]  # Now Pylance is happy

# For Callable type aliases, use callable() not isinstance()
# BAD: isinstance(x, ContextAwareCondition)  # Doesn't work with type aliases
# GOOD: callable(x)

# For Literal types in loops, cast inside the loop
for skill_str in ["perception", "athletics"]:
    skill_name = cast(SkillName, skill_str)  # Cast inside loop body
    entity.get_skill(skill_name)
```

#### TYPE_CHECKING Is NOT An Escape Hatch

**DO NOT use `TYPE_CHECKING` to work around circular imports.** If you need `TYPE_CHECKING` to import something from up the hierarchy, the code is in the wrong place - same as late imports. Both are symptoms of wrong dependency direction.

```python
# BAD - hiding a circular dependency behind TYPE_CHECKING
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from dnd.entity import Entity  # Still means this module depends on Entity!

# GOOD - move the code to where it has natural access, or pass data as parameters
```

The rule from the Dependency Direction section applies fully: dependencies flow DOWN, never UP. `TYPE_CHECKING` doesn't fix the design problem, it just hides it from the runtime.

## Creating Entities & Running Tests

### Factory Function Pattern

**Key pattern**: EntityConfig → `Entity.create()` → `setup_standard_actions()` → create & equip items. See `dnd/monsters/bestiary.py` for full examples.

```python
# 1. EntityConfig with AbilityScoresConfig(AbilityConfig), HealthConfig, etc.
entity = Entity.create(name=name, source_entity_uuid=source_id, config=entity_config)
# 2. Register standard actions (Move, Dash, Dodge, etc.)
setup_standard_actions(entity)
# 3. Create and equip items
scimitar = create_scimitar(entity.uuid)
entity.equipment.equip(scimitar, WeaponSlot.MELEE_MAIN)
```

### Available Factories

All factories use **keyword args**: `create_goblin(name="Name", position=(0,0), faction=None)`

**Bestiary** (`dnd/monsters/bestiary.py`): `create_goblin`, `create_skeleton`, `create_goblin_archer`, `create_sorcerer(level=5)`
**Classes** (`dnd/classes/`): `create_fighter(level, name, position, faction)`, `create_barbarian(level, name, position, faction)`

### Setting Up Tests

#### Step 1: Reset State

**Always start tests with a clean slate:**

```python
from dnd.utils import reset_combat_state
reset_combat_state()  # Clears EventQueue, Entity registries, GridMap
```

#### Step 2: Create Entities

Use the factories above, then **update senses** (MANDATORY):

```python
Entity.update_all_entities_senses()  # Must call after creating entities!
```

Without this, entities can't see each other and all targeting fails.

#### Step 3: Set Up Encounter

```python
from dnd.utils import setup_combat_arena

# Quick setup (2 entities, rolls initiative, does NOT start encounter)
encounter = setup_combat_arena(attacker, target)
encounter.start_encounter()  # You must call this yourself!
```

**Or manual setup** for multi-entity or custom scenarios:

```python
from dnd.encounter import Encounter
from dnd.controller import HumanController, PassController, MeleeAIController
from uuid import uuid4

encounter = Encounter(name="Test Combat", source_entity_uuid=uuid4())
encounter.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid))
encounter.roll_initiative()
encounter.start_encounter()
```

**Controllers**: `HumanController`/`ClaudeController` (exit turn loop for API control), `MeleeAIController` (auto-attacks), `PassController` (ends turn immediately)

#### Step 4: Run Turns

```python
encounter.start_turn()      # Fires TurnStartEvent, resets action economy
# ... execute actions ...
encounter.end_turn()         # Fires TurnEndEvent
encounter.check_deaths()     # Check for deaths, may end encounter
encounter.next_turn()        # Advance to next combatant
```

Or use `run_turn_until_end(encounter, entity)` from test_utils for simpler tests.

### Test Utilities (`dnd/utils/test_utils.py`)

**USE THESE** instead of writing your own. All exported from `dnd.utils`:

```python
from dnd.utils import (
    # State & encounter
    reset_combat_state, setup_combat_arena, run_turn_until_end,

    # HP: get_hp, get_max_hp, set_hp, heal_entity
    # deal_damage_to(entity, amount, damage_type, source_uuid) - fires TakeDamageEvent!
    get_hp, get_max_hp, set_hp, heal_entity, deal_damage_to,

    # Deterministic attack forcing
    force_attack_hit,        # +100 attack bonus → returns modifier UUID
    force_attack_miss,       # -100 attack penalty
    force_attack_crit,       # AUTOCRIT modifier
    remove_attack_modifier,  # Cleanup with UUID from above

    # Position, conditions, debug
    get_position, move_entity,
    has_condition, count_conditions,
    print_combat_state,
)
```

**CRITICAL**: `deal_damage_to()` fires `TakeDamageEvent` via `entity.receive_damage()`, triggering handlers (RelentlessRage, Concentration checks, etc.). It's not just setting HP.

### Faction System

- `faction=None` (default) = enemy to everyone
- Same faction = allies, different faction = enemies
- `entity.is_ally(other)` / `entity.is_enemy(other)` / `entity.get_visible_enemies()` / `entity.get_visible_allies()`
- `get_available_actions(target_filter="enemies"|"allies"|"all")` filters valid targets
- Encounter ends when only one faction has survivors

## Spatial System

### GridMap (`dnd/core/gridmap.py`)

`GridMap` is a singleton centralizing spatial data.

```
GridMap (get_map())
├── _tiles: Dict[pos, Tile]              # Tile objects (can have conditions)
├── _entity_positions: Dict[UUID, pos]   # Entity → position
├── _entities_by_position: Dict[pos, Set[UUID]]
├── _object_positions: Dict[UUID, pos]   # Object (item) → position
├── _objects_by_position: Dict[pos, Set[UUID]]
└── compute_fov(), compute_paths()       # Shadowcast + Dijkstra
```

**Key methods**: `is_walkable()`, `is_walkable_for()`, `get_entities_at()`, `move_entity()`, `compute_fov()`, `compute_paths()`
**Object methods**: `place_object()`, `remove_object()`, `get_object_position()`, `get_objects_at()`, `get_objects_with_conditions()`

**Spatial events**: `SPATIAL_ENTITY_ENTERED`, `SPATIAL_ENTITY_LEFT`, `SPATIAL_TILE_CHANGED`, `SPATIAL_LIGHT_CHANGED`, `SPATIAL_OBJECT_PLACED`, `SPATIAL_OBJECT_REMOVED`, `SPATIAL_OBJECT_CHANGED`, `SPATIAL_PERCEIVABILITY_CHANGED` - fired automatically by GridMap and BaseBlock. All carry `SensesUpdateHint` for incremental senses updates.

**Tiles** are `BaseBlock` objects that can have conditions (fire, traps, difficult terrain).

**Tile Types**: Tiles have a `name` field serialized via API:
- `"Floor"` - walkable, rendered as `.`
- `"Wall"` - blocks movement and vision, rendered as `#`
- `"Water"` - blocks movement, allows vision, rendered as `~` (blue)

### Senses and Vision

The `Senses` block tracks what an entity can see and where it can move:

```python
entity.update_entity_senses(max_distance=10)  # Updates visibility and paths
Entity.update_all_entities_senses()            # Updates all entities

# After update:
entity.senses.entities      # Dict[UUID, position] - visible entities
entity.senses.objects       # Dict[UUID, position] - visible objects (items on floor)
entity.senses.visible       # Dict[position, bool] - visible cells
entity.senses.paths         # Dict[position, List[position]] - paths to reachable cells
entity.senses.get_feet_distance(target.position)  # Distance in feet (1 grid = 5ft)
```

### Incremental Senses Update System

Senses are updated incrementally via the `SensesUpdateHint` system (40-257x faster than full recompute). See `claude_docs/LIGHTING_SYSTEM.md` for full details.

**Core design**: Every spatial event carries a `SensesUpdateHint` on its `senses_hint` field, telling observers exactly what to update. The `SpatialSensesCallback` (registered on `EventQueue`) reads hints and applies targeted updates.

**Three separated concerns**:
- **FOV (geometry)**: Recomputed only when `requires_fov=True` (magical darkness, door vision blocking)
- **Paths (movement)**: NEVER recomputed from callbacks. `_paths_dirty = True` flag set, cleared at turn start and movement end
- **Entity filtering**: Re-filter at specific positions only (`light_changed_positions`, `entity_entered`/`entity_left`)

**Key rule**: Callbacks NEVER run Dijkstra. All callback paths use `update_visibility_func()` (FOV only) + `_paths_dirty = True`. Full Dijkstra only runs at:
1. Turn start (`Encounter.start_turn()` → `entity.update_entity_senses()`)
2. Movement end (`Move._apply()` finally → `entity.update_entity_senses()`)

**New event type**: `SPATIAL_OBJECT_CHANGED` — fired when objects change blocking state (doors). Carries `requires_fov` and `requires_paths` hints.

**BaseItem._notify_blocking_changed()**: Standard method for items to fire `SPATIAL_OBJECT_CHANGED` when blocking properties change. Used by door actions instead of `Entity.update_all_entities_senses()`.

### StepMovementEvent and the use_register Pattern

In `Move._apply()`, each movement step fires a `StepMovementEvent` that handlers (OA, Intercept, terrain effects) can react to. **Critical implementation detail**:

```python
# StepMovementEvent created with use_register=False (no model_post_init auto-registration)
step_event = StepMovementEvent(..., use_register=False)
# post() is the SINGLE registration point where handlers fire and cancellation propagates
processed_step = step_event.post(use_register=True)
```

**Why**: `Event.model_post_init` normally auto-registers with `EventQueue.register()`, and `post()` creates a copy and registers again — causing handlers to fire **twice** with the first cancellation discarded. The `use_register=False` pattern prevents this double-registration.

After step event processing, a **walkability re-check** catches map changes by handlers (e.g., an interceptor charged into `to_pos`, a door closed):

```python
if not grid.is_walkable_for(to_pos[0], to_pos[1], source_entity.uuid):
    break  # Map changed during step event — stop movement
```

### Reactions

**`dnd/reactions.py`**: Contains the opportunity attack handler (fires on `STEP_MOVEMENT` at `EFFECT` phase).

**`dnd/items/test_reactions.py`**: Homebrew reaction definitions proving the `_paths_dirty` incremental senses pattern works:
- **Intercept** (action-setup reaction): Player spends 1 action + movement to declare a charge destination. When an enemy steps into that cell, interceptor charges there first, occupies the cell (blocking enemy path), and makes a melee attack. Uses per-cell `is_walkable_for()` checks at reaction time.
- **Dodge Roll** (passive reaction): When attacked, moves up to 2 cells away from attacker and imposes disadvantage. Uses per-cell `is_walkable_for()` checks.

Both validate that environment changes (door open/close) correctly propagate through `_paths_dirty` to affect reaction-time walkability checks. Tests: `examples/test_intercept_dodge_roll.py` (52 assertions).

## CLI and Server Architecture

Two CLIs connect to a FastAPI server (`server/event_server.py`) with session-based authority (`server/session.py`):
- **Human CLI** (`cli/main.py`): Rich terminal interface — `python -m cli play` (vs AI) or `python -m cli playpvp` (vs Claude)
- **Agent CLI** (`cli/agent.py`): Claude's command interface for PvP

**PvP Quick Start**: Start server (`uvicorn server.event_server:app --reload`), user runs `python -m cli playpvp`, Claude connects via agent CLI.

**Agent turn flow** — **CRITICAL**: After `end`, you MUST run `watch` again!

```bash
connect → watch → [state/actions/move/attack/end] → watch → repeat
```

To restart: User restarts `playpvp`, Claude runs `disconnect` → `connect` → `watch`

See `claude_docs/CLI_GUIDE.md` for full agent command reference and session details.

## Reference

### Key Files

**Core**: `dnd/core/` — `base_object.py`, `base_block.py`, `events.py`, `values.py`, `modifiers.py`, `dice.py`, `gridmap.py`, `base_actions.py`, `combat_log.py`
**Entity & Blocks**: `dnd/entity.py`, `dnd/blocks/` (abilities, skills, saving_throws, health, equipment, inventory, action_economy, sensory, spellcasting, base_item)
**Actions**: `dnd/actions.py`, `dnd/actions_functional.py`, `dnd/reactions.py`
**Conditions**: `dnd/conditions.py`, `dnd/core/base_conditions.py`
**Classes**: `dnd/classes/` (fighter, barbarian, rage, feats, dice_processor_utils + factories)
**Items**: `dnd/items/` (weapons, armors, test_items, test_reactions)
**Spells**: `dnd/spells/` (evocation, abjuration, enchantment, conjuration, necromancy, illusion, transmutation)
**Spatial**: `dnd/core/gridmap.py`, `dnd/core/shadowcast.py`, `dnd/core/dijkstra.py`, `dnd/tiles.py`, `dnd/tile_conditions.py`
**Monsters**: `dnd/monsters/bestiary.py` (create_goblin, create_skeleton, create_goblin_archer, create_sorcerer)
**Server/CLI**: `server/event_server.py`, `server/session.py`, `cli/agent.py`, `cli/display.py`, `cli/commands.py`
**Tests**: `examples/test_*.py` — named by feature (e.g., `test_barbarian_rage.py`, `test_fireball.py`)

### Documentation

| Doc | Read when... |
|-----|-------------|
| `claude_docs/IMPLEMENTATION_GUIDE.md` | Implementing any condition, action, or event handler (**read first**) |
| `claude_docs/CLASS_SYSTEM.md` | Working on Fighter/Barbarian features or adding a new class |
| `claude_docs/LIGHTING_SYSTEM.md` | Working on lighting, darkvision, or incremental senses updates |
| `claude_docs/VISION_HIDING_COVER_PLAN.md` | Working on stealth, invisibility, or cover |
| `claude_docs/TERRAIN_MOVEMENT_SYSTEM.md` | Working on terrain, movement costs, or zone spells |
| `claude_docs/CLI_GUIDE.md` | Using or modifying the CLI or agent commands |
| `claude_docs/archive/MASTER_SUMMARY.md` | Project status, what's implemented, roadmap |

**SRD reference**: `interactive_ruleset/` contains D&D 5e rules with `*_NOTES.md` gap analysis files.

**Dependencies**: pydantic, pytest, pyright, fastapi/uvicorn, websockets, httpx
