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
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .

# Run tests
pytest

# Run combat examples (for quick local testing without server)
python examples/combat_basic.py        # Basic attack exchange
python examples/combat_conditions.py   # All condition effects tested

# Type checking
pyright
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

**Key Entity Methods:**
- `passive_skill(skill_name)` - Returns `10 + skill bonus + advantage modifier` (for contested checks like Shove)
- `is_ally(other)` / `is_enemy(other)` - Faction-based relationship checks
- `get_visible_enemies()` / `get_visible_allies()` - Filtered visibility by faction
- `loot_item(item)` / `drop_item(item_uuid)` - Pick up / drop items (with lifecycle hooks)
- `equip_item(item_uuid, slot)` / `unequip_item(slot)` - Move items between inventory and equipment

### Item Hierarchy

```
BaseBlock
└── BaseItem (dnd/blocks/base_item.py)
    │   Location tracking: owner_uuid, stored_in_uuid, tile_uuid, is_equipped
    │   Lifecycle hooks: _on_loot(), _on_drop(), _on_destroy()
    │   Health/damage for breakable items, GridMap integration
    │
    ├── EquippableItem
    │   │   Equip/unequip hooks: _on_equip(slot, entity_uuid), _on_unequip(slot, entity_uuid)
    │   │   is_equippable=True, is_pickable=True
    │   │
    │   ├── Weapon (dnd/blocks/equipment.py)
    │   ├── Armor (+ subtypes: BodyArmor, Helmet, Gloves, Boots, Cloak, Amulet)
    │   └── Shield
    │
    └── UsableItem (stub — for Use action, future)
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
| `SPATIAL_ENTITY_ENTERED` | Entity moved into cell |

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

**Entry types**: `ATTACK`, `MOVEMENT`, `ACTION`, `SAVING_THROW`, `SKILL_CHECK`, `CONDITION_APPLIED`/`REMOVED`, `DAMAGE_TAKEN`, `HEAL`, `DEATH`, `TURN_START`/`END`, `MULTI_ENTITY_ACTION`, `SPELL_SAVE`, `SPELL_DAMAGE`

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

**Functional API** (`dnd/actions_functional.py`):
- `setup_standard_actions(entity)` - Registers Move, Jump, Dash, Dodge, Disengage + weapon attacks
- `execute_by_index(entity, name, idx)` - Execute by target index

### Attack Action

Attack validates range and LOS, then:
1. Cross-propagate modifiers via `set_from_target()`
2. Roll d20 with attack bonus vs AC
3. Apply damage on hit

**AttackEvent fields**: `dice_roll`, `attack_outcome`, `damages`, `damage_rolls`

### Cost Types

`actions`, `bonus_actions`, `reactions`, `movement` + optional `resource_name/resource_cost`

## Implemented Features

### Conditions

All conditions in `dnd/conditions.py`:

| Condition | Self Effects | Effects on Attackers | Sub-conditions |
|-----------|--------------|---------------------|----------------|
| **Blinded** | Disadvantage attacks, auto-fail sight skills | Advantage | - |
| **Charmed** | Auto-miss vs charmer | Charmer: advantage social skills | - |
| **Dashing** | +movement = base speed | - | - |
| **Deafened** | Auto-fail hearing skills | - | - |
| **Disengaging** | Movement doesn't provoke OA | - | - |
| **Dodging** | Advantage DEX saves | Disadvantage | - |
| **Frightened** | Disadvantage attacks/checks (contextual), speed=0 | - | - |
| **Grappled** | Speed max = 0 | - | - |
| **HasAttacked** | Marker for rage maintenance (tracks ANY attack) | - | - |
| **HasTakenDamage** | Marker for rage maintenance (tracks damage taken) | - | - |
| **Incapacitated** | All action economy = 0 | - | - |
| **Invisible** | Advantage attacks (contextual) | Disadvantage (contextual) | - |
| **Paralyzed** | Auto-fail STR/DEX saves | Advantage, auto-crit ≤5ft | Incapacitated |
| **Poisoned** | Disadvantage all attacks/checks | - | - |
| **Prone** | Disadvantage attacks | ≤5ft: advantage, >5ft: disadvantage | - |
| **Restrained** | Speed=0, disadvantage attacks, fail DEX | Advantage | - |
| **Stunned** | Auto-fail STR/DEX saves | Advantage | Incapacitated |
| **Unconscious** | Auto-fail STR/DEX saves | Advantage, auto-crit ≤5ft, prone-like | Incapacitated |
| **Dead** | Entity is dead | - | - |
| **NoReactions** | Reactions = 0 | - | - |

### Spell Conditions (in `dnd/conditions.py` and `dnd/spells/`)

| Condition | Effect | Notes |
|-----------|--------|-------|
| **Concentrating** | Tracks spell being concentrated on | CON save on damage (DC = max(10, dmg/2)), one-spell limit, uses `linked_conditions` for cleanup |
| **MageArmorCondition** | AC = 13 + DEX when unarmored | Ends if armor equipped |
| **HoldPersonEffect** | Spell effect for Hold Person | Has Paralyzed as sub-condition, allows spell-specific immunity (in `dnd/spells/enchantment.py`) |

### Fighter Conditions (in `dnd/classes/fighter.py`)

| Condition | Effect | Notes |
|-----------|--------|-------|
| **ActionSurging** | +1 action this turn (1 round duration) | Applied by Action Surge |
| **FightingStyleArchery** | +2 ranged attack bonus | Modifier on attack rolls |
| **FightingStyleDefense** | +1 AC when wearing armor | AC modifier |
| **FightingStyleDueling** | +2 damage with one-handed weapon | Damage modifier |
| **GreatWeaponFighting** | Reroll 1s and 2s on damage dice | EventHandler on DAMAGE_ROLL_RESULT |
| **FightingStyleProtection** | Impose disadvantage on attacks vs allies | EventHandler, uses reaction |
| **FightingStyleTwoWeaponFighting** | Add ability mod to off-hand damage | Damage modifier |
| **SecondWindFeature** | Grants Second Wind action + resource | Level-based healing |
| **ActionSurgeFeature** | Grants Action Surge action + resource | Once per turn enforcement |
| **ExtraAttackFeature** | Grants Extra Attack actions + resource | 1/2/3 at L5/L11/L20 |
| **ExtraAttacksGranted** | Marker for Extra Attack (action-cost attacks only) | Applied by extra_attack_resource_processor |
| **ImprovedCritical** | Crit on 19-20 | Critical modifier |
| **SuperiorCritical** | Crit on 18-20 | Critical modifier |
| **Indomitable** | Reroll failed saves | EventHandler on SAVING_THROW |
| **Survivor** | Heal 5+CON at turn start when HP ≤ 50% | EventHandler on TURN_START |

### Barbarian Conditions (in `dnd/classes/barbarian.py` and `dnd/classes/rage.py`)

| Condition | Effect | Notes |
|-----------|--------|-------|
| **RageFeature** | Grants Rage + End Rage actions, rage resource | Level-scaled uses and damage |
| **Raging** | STR adv, rage damage, B/P/S resistance | Maintained by HasAttacked/HasTakenDamage |
| **UnarmoredDefense** | AC = 10 + DEX + CON when unarmored | Contextual modifier |
| **RecklessAttackFeature** | Grants Reckless Attack action | Free action |
| **RecklessAttacking** | Adv on melee attacks, attackers have adv | 1-round duration |
| **DangerSense** | Adv on DEX saves vs visible effects | Contextual, disabled when blind/deaf/incap |
| **FrenzyFeature** | Grants Frenzy action | Berserker L3 |
| **Frenzied** | Rage + bonus action melee attacks | BG3-style, no exhaustion |
| **FastMovement** | +10 speed when not in heavy armor | Contextual modifier |
| **MindlessRage** | Immune to charm/frighten while raging | Contextual immunity |
| **FeralInstinct** | Advantage on initiative | Modifier |
| **BrutalCritical** | +1/2/3 extra melee crit dice | L9/13/17 |
| **IntimidatingPresenceFeature** | Grants Intimidating Presence actions | Berserker L10 |
| **IntimidatingPresenceImmunity** | 24h immunity after successful save | Applied on save success |
| **RelentlessRage** | CON save to drop to 1 HP instead of 0 | Escalating DC |
| **Retaliation** | Reaction melee attack when hit | Berserker L14 |
| **PersistentRage** | Rage doesn't end from inactivity | Marker condition |
| **IndomitableMight** | STR checks can't be below STR score | EventHandler |
| **PrimalChampion** | +4 STR and CON | L20 capstone |

### Class System

Two character classes are fully implemented:

- **Fighter** (L1-L18) + Champion archetype: `dnd/classes/fighter.py`, `dnd/classes/fighter_factory.py`
- **Barbarian** (L1-L20) + Berserker path: `dnd/classes/barbarian.py`, `dnd/classes/barbarian_factory.py`

See `claude_docs/CLASS_SYSTEM.md` for feature details and `claude_docs/IMPLEMENTATION_GUIDE.md` for implementation patterns.

### Spell System

Generic spell infrastructure supporting attack spells, save spells, and buff spells.

#### Architecture

```
dnd/spells/
├── __init__.py      # Exports + CANTRIPS through LEVEL_9_SPELLS + ALL_SPELLS dicts
├── base.py          # Re-exports SpellAction, SpellEvent from actions.py
├── evocation.py     # FireBolt, Fireball, LightningBolt, Thunderwave, etc.
├── abjuration.py    # MageArmor, ProtectionFromEnergy, Stoneskin
├── enchantment.py   # HoldPerson, HoldMonster, CharmPerson, Sleep, etc.
├── conjuration.py   # CallLightning, Grease, Web, Cloudkill, SpiritGuardians, etc.
├── necromancy.py    # ChillTouch, FalseLife, Blight, BlindnessDeafness
├── illusion.py      # Blur, Fear, HypnoticPattern, ColorSpray
└── transmutation.py # SpikeGrowth
```

**Base classes in `dnd/actions.py`:**
- `SpellEvent(ActionEvent)` - Event for spell casting with spell-specific fields
- `SpellAction(BaseAction)` - Base class with variant generation for upcasting

#### Entity Spell Methods

Entity provides helper methods for spell calculations:

```python
# Attack/DC calculation
entity.spell_attack_bonus(target_uuid) -> ModifiableValue  # prof + ability + bonuses
entity.spell_save_dc() -> int                               # 8 + prof + ability + bonuses

# Crit handling (stacks with equipment)
entity.get_spell_crit_threshold() -> int      # Default 20
entity.get_spell_crit_extra_dice() -> int     # Extra dice on crit

# Damage and slots
entity.get_spell_damage_bonus() -> ModifiableValue
entity.has_spell_slot(level) -> bool
entity.get_lowest_spell_slot(min_level) -> int | None
entity.is_spellcaster -> bool  # Property
```

#### Spell Registration

```python
from dnd.actions_functional import register_spell, register_spells_by_name
from dnd.spells import FireBolt, ALL_SPELLS

# Register individual spell
register_spell(entity, FireBolt, caster_level=5)

# Register multiple by name
register_spells_by_name(entity, ["Fire Bolt", "Magic Missile"], caster_level=5)
```

#### Implemented Spells (40+ total)

See `dnd/spells/__init__.py` for complete spell dictionaries (`CANTRIPS` through `LEVEL_9_SPELLS`).

**Representative spells by school:**

| Spell | Level | School | Type | Effect |
|-------|-------|--------|------|--------|
| Fire Bolt | Cantrip | Evocation | Attack | 1d10 fire, scales with level |
| Sacred Flame | Cantrip | Evocation | DEX Save | 1d8 radiant, scales with level |
| Chill Touch | Cantrip | Necromancy | Attack | 1d8 necrotic, no healing 1 round |
| Magic Missile | 1 | Evocation | Auto-hit | 3 darts (1d4+1 each), +1 dart/upcast |
| Mage Armor | 1 | Abjuration | Buff | AC = 13 + DEX (ends on armor equip) |
| Sleep | 1 | Enchantment | Auto | 5d8 HP pool, lowest HP first |
| False Life | 1 | Necromancy | Buff | 1d4+4 temp HP |
| Burning Hands | 1 | Evocation | DEX Save + AoE | 3d6 fire in 15ft cone |
| Grease | 1 | Conjuration | DEX Save + Zone | Prone on fail, difficult terrain |
| Hold Person | 2 | Enchantment | WIS Save + Conc. | Paralyzed, repeat save each turn |
| Blur | 2 | Illusion | Buff + Conc. | Attackers have disadvantage |
| Spike Growth | 2 | Transmutation | Zone + Conc. | 2d4 piercing per 5ft moved |
| Web | 2 | Conjuration | DEX Save + Zone | Restrained, repeat save each turn |
| Fireball | 3 | Evocation | DEX Save + AoE | 8d6 fire in 20ft sphere |
| Call Lightning | 3 | Conjuration | DEX Save + Conc. | 3d10 lightning, grants strike each turn |
| Fear | 3 | Illusion | WIS Save + Conc. | Frightened, 30ft cone |
| Blight | 4 | Necromancy | CON Save | 8d8 necrotic |
| Cone of Cold | 5 | Evocation | CON Save + AoE | 8d8 cold in 60ft cone |
| Power Word Stun | 8 | Enchantment | Auto | Stunned if ≤150 HP |
| Power Word Kill | 9 | Enchantment | Auto | Instant death if ≤100 HP |

#### SpellcastingBlock

`dnd/blocks/spellcasting.py` provides spell-specific modifiers:
- `spell_attack_bonus` - Wand of War Mage, etc.
- `spell_damage_bonus` - Elemental Affinity, etc.
- `spell_dc_bonus` - Robe of Archmagi, etc.
- `spell_crit_threshold` - Spell Sniper, etc.
- `spell_crit_extra_dice` - Custom features
- `spellcasting_ability` - "intelligence", "wisdom", or "charisma"

#### Concentration System

Concentration spells are fully implemented:
- **One spell limit**: Casting a new concentration spell ends the old one
- **CON saves on damage**: DC = max(10, damage/2)
- **Automatic cleanup**: Uses `linked_conditions` to clean up spell effects on targets when concentration breaks
- **Spell-specific effects**: Each concentration spell creates a spell-specific condition (e.g., `HoldPersonEffect`) with the actual effect (e.g., `Paralyzed`) as a sub-condition

See `examples/test_concentration.py` and `examples/test_concentration_spells.py` for tests.

#### AoE System

AoE spells use `TargetType.POSITION_AOE` with an `aoe_shape` field.

**Implemented Shapes** (`dnd/core/aoe.py`):

| Shape | Origin | Example |
|-------|--------|---------|
| Sphere | target position | Fireball (20ft) |
| Cone | caster position | Burning Hands (15ft) |
| Line | caster position | Lightning Bolt (100ft×5ft) |
| Cube | varies | Thunderwave (15ft) |

**Target Filtering:**
- `include_self`: Caster affected? (default False for most spells)
- `valid_target_filter`: `"all"`, `"enemies"`, `"allies"`
- `include_dead`: Target dead entities? (default False)

**Implemented AoE Spells:** Fireball, Burning Hands, Lightning Bolt, Thunderwave, Shatter

See `claude_docs/AOE_TARGETING_REFERENCE.md` for full implementation guide.

#### Not Yet Implemented

- **Spell duration/expiration** - Long rest, short rest, timed durations
- **Terrain effects** - Fog Cloud, Wall of Fire (see `claude_docs/VISION_HIDING_COVER_PLAN.md`)

## Code Quality

### Code Verification Rules

**CRITICAL: Before writing any code that uses existing classes/methods:**

1. **Never assume method/attribute names** - Always read the actual class definition first
2. **Check existing examples** - Look at `examples/combat_basic.py` or `examples/combat_conditions.py` for correct usage patterns
3. **Verify imports exist** - Grep for `class ClassName` to find where things are defined
4. **Check Config classes** - Many classes have `*Config` counterparts with different field structures (e.g., `AbilityConfig` vs raw int)
5. **Test imports before running** - Run `python -c "import module_name"` to catch import errors early

**Common pitfalls in this codebase:**
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
| `reportCallIssue: No parameter named X` | Pydantic inheritance not recognized | Explicitly redeclare the field in subclass |

#### Pydantic + Pylance Gotchas

Pylance sometimes doesn't understand Pydantic model inheritance. If you get "No parameter named X" when X is inherited:

```python
# BAD: Pylance may not see inherited `costs` field
class MovementEvent(ActionEvent):
    name: str = Field(...)
    # costs is inherited from ActionEvent but Pylance complains

# GOOD: Explicitly redeclare for Pylance
class MovementEvent(ActionEvent):
    name: str = Field(...)
    costs: List[BaseCost] = Field(default_factory=list)  # Redeclare for Pylance
```

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

### Factory Function Pattern (`dnd/monsters/bestiary.py`)

```python
def create_goblin(
    source_id: Optional[UUID] = None,
    name: str = "Goblin",
    position: Tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
    weight: int = 40
) -> Entity:
    if source_id is None:
        source_id = uuid4()

    # 1. Create config with ability scores and health
    entity_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=8),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=10),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=8),
            charisma=AbilityConfig(ability_score=8)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=6, hit_dice_count=2, mode="average"
        )]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position
    )

    # 2. Create entity
    entity = Entity.create(name=name, source_entity_uuid=source_id, config=entity_config)

    # 3. Set up action templates (Move, Dash, Dodge, etc.)
    setup_standard_actions(entity)

    # 4. Create and equip weapons/armor
    scimitar = create_scimitar(entity.uuid)  # Helper function
    leather_armor = create_leather_armor(entity.uuid)
    shield = create_wooden_shield(entity.uuid)

    entity.equipment.equip(leather_armor)
    entity.equipment.equip(scimitar, WeaponSlot.MELEE_MAIN)
    entity.equipment.equip(shield, WeaponSlot.MELEE_OFF)

    return entity
```

**Key pattern**: Create entity first, then equip weapons via `entity.equipment.equip(item, slot)`.

### Available Factories

All factories use **keyword args** and share this signature pattern:

```python
def create_skeleton(
    source_id: Optional[UUID] = None,   # Auto-generated if None
    name: str = "Skeleton",
    position: Tuple[int, int] = (0, 0),
    faction: Optional[str] = None,      # None = enemy to everyone
    weight: int = 120
) -> Entity:
```

**Bestiary factories** in `dnd/monsters/bestiary.py`:
- `create_goblin(weight=40)` - CR 1/4, AC 15 (leather+shield), Scimitar 1d6+2
- `create_skeleton(weight=120)` - CR 1/4, AC 13, Shortsword 1d6+2, undead
- `create_goblin_archer(weight=40)` - Dual wield + shortbow
- `create_sorcerer(level=5)` - CHA 18 caster with Fireball, Magic Missile, etc.

**Character class factories** in `dnd/classes/`:
- `create_fighter(level, name, position, faction)` - Fighter with Champion archetype
- `create_barbarian(level, name, position, faction)` - Barbarian with Berserker path

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

**Spatial events**: `SPATIAL_ENTITY_ENTERED`, `SPATIAL_ENTITY_LEFT`, `SPATIAL_TILE_CHANGED` - fired automatically by GridMap.

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

## CLI and Server Architecture

### Overview

The D&D Engine uses a terminal-based CLI for gameplay. Two CLIs are provided:
- **Human CLI** (`cli/main.py`): Rich terminal interface for human players
- **Agent CLI** (`cli/agent.py`): Simple command interface for Claude to play as opponent

Both connect to a FastAPI server that manages game state, sessions, and combat.

### Game Modes

| Mode | Command | Description |
|------|---------|-------------|
| Human vs AI | `python -m cli play` | Human controls heroes faction, AI controls monsters faction |
| Human vs Claude PvP | `python -m cli playpvp` | Human controls heroes, Claude controls monsters via agent CLI |

**Multi-Entity Combat**: Both modes support multi-entity encounters (e.g., 2 heroes vs 3 monsters). Entities are assigned to players by faction.

### Session-Based Authority System

PvP mode uses session-based authentication (`server/session.py`):

- **PlayerSession**: A connected client (HUMAN, CLAUDE, or AI) that controls entities
- **GameSession**: Active game with players and entity ownership mappings
- **SessionManager**: Singleton managing all sessions and games

Key endpoints:
- `POST /session/create` - Create player session
- `POST /game/join` - Join game with session, get assigned entities
- `POST /action/*` - All actions require `session_id` + `entity_uuid`
- `GET /pvp/status` - Check whose turn, who's connected
- `GET /combat-log?since=N` - Get server-side combat log entries

### PvP CLI Loop (PRIMARY WORKFLOW)

The primary way to develop and test features is through **live PvP combat** between the user and Claude. This provides immediate feedback and allows testing specific scenarios.

#### Quick Start

```bash
# Terminal 1: Start server
source .venv/bin/activate
uvicorn server.event_server:app --reload

# Terminal 2: User plays as Hero
python -m cli playpvp

# Claude connects and plays as Skeleton (see Agent Commands below)
```

#### Claude Agent Commands

```bash
# Connect to game (creates session, joins as Skeleton)
python -m cli.agent connect

# Watch for your turn (BLOCKS until it's your turn, shows opponent actions)
python -m cli.agent watch

# View current state
python -m cli.agent state

# View available actions
python -m cli.agent actions

# Take actions
python -m cli.agent move X Y      # Move to position
python -m cli.agent attack 0      # Attack target by index
python -m cli.agent dash          # Dash action (double movement)
python -m cli.agent dodge         # Dodge action
python -m cli.agent disengage     # Disengage action
python -m cli.agent end           # End turn

# Disconnect (clear session for new game)
python -m cli.agent disconnect
```

#### Turn Flow

**CRITICAL**: After `end`, you MUST run `watch` again to stay connected!

```bash
connect → watch → [state/actions/move/attack/end] → watch → repeat
```

`watch` blocks until your turn, shows opponent actions, detects game end.

To restart: User restarts `playpvp`, Claude runs `disconnect` → `connect` → `watch`

### Agent CLI Session Persistence

Session stored in `/tmp/dnd_agent_session.txt`, persists between commands. `connect` creates it, `disconnect` removes it.

### Agent CLI: The `watch` Command

Polls server every 2s, shows opponent actions, blocks until Claude's turn, detects game end. Flow: `connect` → `watch` → take actions → `end` → `watch` → repeat

### CLI Files

| File | Purpose |
|------|---------|
| `cli/main.py` | Human player CLI with `play` and `playpvp` commands, position action routing |
| `cli/agent.py` | Claude agent CLI (connect, watch, state, actions, move, attack, jump, end) |
| `cli/api_client.py` | HTTP client wrapper with session management |
| `cli/display.py` | Rich terminal rendering (map, entities, combat log, action results) |
| `cli/commands.py` | Command parsing and execution for human CLI |

## Reference

### Key Files Reference

| Purpose | Location |
|---------|----------|
| **Core** | |
| Entity (main game object) | `dnd/entity.py` |
| ModifiableValue system | `dnd/core/values.py` |
| Modifiers (Advantage, Critical, etc.) | `dnd/core/modifiers.py` |
| Base classes | `dnd/core/base_object.py`, `base_block.py` |
| Event system | `dnd/core/events.py` |
| Combat log (CombatLogEntry, verbosity, markdown) | `dnd/core/combat_log.py` |
| Dice rolling | `dnd/core/dice.py` |
| **Spatial System** | |
| GridMap (central spatial manager) | `dnd/core/gridmap.py` |
| Tile class (BaseBlock, can have conditions) | `dnd/core/base_tiles.py` |
| Shadowcast FOV algorithm | `dnd/core/shadowcast.py` |
| Dijkstra pathfinding | `dnd/core/dijkstra.py` |
| **Encounter & Combat** | |
| Encounter/turn management | `dnd/encounter.py` |
| **Actions & Registry** | |
| Base action class + data models | `dnd/core/base_actions.py` |
| Attack, Move, Jump, Shove, Dash, Dodge, etc. | `dnd/actions.py` |
| Functional API (setup, execute) | `dnd/actions_functional.py` |
| Opportunity attack handler | `dnd/reactions.py` |
| **Conditions** | |
| Base condition class | `dnd/core/base_conditions.py` |
| All D&D conditions | `dnd/conditions.py` |
| **Entity Blocks** | |
| Ability scores | `dnd/blocks/abilities.py` |
| Skills | `dnd/blocks/skills.py` |
| Saving throws | `dnd/blocks/saving_throws.py` |
| Health/HP | `dnd/blocks/health.py` |
| Equipment (weapons, armor) | `dnd/blocks/equipment.py` |
| Action economy | `dnd/blocks/action_economy.py` |
| Senses (vision, position) | `dnd/blocks/sensory.py` |
| **Character Classes** | |
| Fighter class (all features + Champion) | `dnd/classes/fighter.py` |
| Fighter factory (create L1-20 fighters) | `dnd/classes/fighter_factory.py` |
| Barbarian class (all features + Berserker) | `dnd/classes/barbarian.py` |
| Barbarian factory (create L1-20 barbarians) | `dnd/classes/barbarian_factory.py` |
| Rage system (Raging, RageFeature, Frenzied) | `dnd/classes/rage.py` |
| Feats (Lucky) | `dnd/classes/feats.py` |
| Dice processor utilities | `dnd/classes/dice_processor_utils.py` |
| Class module exports | `dnd/classes/__init__.py` |
| **Items** | |
| BaseItem, EquippableItem, UsableItem | `dnd/blocks/base_item.py` |
| Inventory block | `dnd/blocks/inventory.py` |
| Weapon factories (WEAPONS dict) | `dnd/items/weapons.py` |
| Armor factories (ARMORS, SHIELDS dicts) | `dnd/items/armors.py` |
| Items Phase 1 tests (27) | `examples/test_items_phase1.py` |
| Items Phase 1 advanced tests (36) | `examples/test_items_phase1_advanced.py` |
| Items lifecycle hooks tests (22) | `examples/test_items_lifecycle_hooks.py` |
| Items equip/unequip hooks tests (15) | `examples/test_items_equip_hooks.py` |
| **Spells** | |
| Spell module exports + dicts | `dnd/spells/__init__.py` |
| SpellAction, SpellEvent base (in actions.py) | `dnd/actions.py` |
| Evocation spells (FireBolt, SacredFlame, MagicMissile) | `dnd/spells/evocation.py` |
| Abjuration spells (MageArmor) | `dnd/spells/abjuration.py` |
| Enchantment spells (HoldPerson, HoldPersonEffect) | `dnd/spells/enchantment.py` |
| Conjuration spells (CallLightning, Grease, Web, etc.) | `dnd/spells/conjuration.py` |
| Necromancy spells (ChillTouch, Blight, etc.) | `dnd/spells/necromancy.py` |
| Illusion spells (Blur, Fear, HypnoticPattern, etc.) | `dnd/spells/illusion.py` |
| Transmutation spells (SpikeGrowth) | `dnd/spells/transmutation.py` |
| Spellcasting block | `dnd/blocks/spellcasting.py` |
| Spell system tests | `examples/test_spell_system.py` |
| **Utilities** | |
| Test/debug utilities | `dnd/utils/test_utils.py` |
| **Monsters & Examples** | |
| Creature factories (create_goblin, create_skeleton, create_goblin_archer, create_sorcerer) | `dnd/monsters/bestiary.py` |
| Complex creature example | `dnd/monsters/circus_fighter.py` |
| Circus fighter custom conditions | `dnd/monsters/circus_fighter_conditions.py` |
| Basic combat demo | `examples/combat_basic.py` |
| Condition tests | `examples/combat_conditions.py` |
| Spatial events test | `examples/spatial_events_test.py` |
| Dice processor tests | `examples/test_dice_processors.py` |
| Great Weapon Fighting tests | `examples/test_great_weapon_fighting.py` |
| Second Wind tests | `examples/test_second_wind.py` |
| Action Surge tests | `examples/test_action_surge.py` |
| Extra Attack tests | `examples/test_extra_attack.py` |
| Indomitable tests | `examples/test_indomitable.py` |
| Protection tests | `examples/test_protection.py` |
| Survivor tests | `examples/test_survivor.py` |
| Barbarian rage tests | `examples/test_barbarian_rage.py` |
| Barbarian frenzy tests | `examples/test_barbarian_frenzy.py` |
| Barbarian features tests | `examples/test_barbarian_srd_features.py` |
| Faction system tests | `examples/test_faction_system.py` |
| Barbarian vs Fighter combat | `examples/test_barbarian_fighter_combat.py` |
| Concentration system tests | `examples/test_concentration.py` |
| Concentration spells tests | `examples/test_concentration_spells.py` |
| Jump action tests | `examples/test_jump.py` |
| Jump API tests | `examples/test_jump_api.py` |
| Shove action tests | `examples/test_shove.py` |
| **Server & CLI** | |
| FastAPI server | `server/event_server.py` |
| Session management | `server/session.py` |
| Human CLI (play/playpvp) | `cli/main.py` |
| Claude agent CLI | `cli/agent.py` |
| API client | `cli/api_client.py` |
| Display/rendering | `cli/display.py` |
| Command parsing | `cli/commands.py` |

### Documentation Folders

#### claude_docs/

Contains focused implementation guides:

| File | Purpose |
|------|---------|
| `MASTER_SUMMARY.md` | Project status, what's implemented, roadmap |
| `CLI_GUIDE.md` | How to use CLI and Agent commands |
| `IMPLEMENTATION_GUIDE.md` | **READ FIRST** - How to implement conditions, actions, event handlers |
| `CLASS_SYSTEM.md` | Class system patterns, Fighter/Barbarian/Sorcerer, spellcasting infrastructure |
| `ITEMS_PLAN.md` | Items system implementation plan (phases a-e), current status |
| ~~`EXAMPLE_PATTERNS.md`~~ | Merged into `IMPLEMENTATION_GUIDE.md` (Section 14) |
| `archive/` | Completed planning docs (historical reference) |

#### interactive_ruleset/

Contains D&D 5e SRD markdown (cloned from OldManUmby/DND.SRD.Wiki) with `*_NOTES.md` analysis files:

```
interactive_ruleset/
├── Gameplay/
│   ├── Abilities.md + Abilities_NOTES.md    # Ability system analysis
│   ├── Combat.md + Combat_NOTES.md          # Combat mechanics gaps
│   └── Adventuring.md + Adventuring_NOTES.md # Turn structure needed
├── Equipment/
│   └── Equipment_NOTES.md                   # ARPG-style already done
├── Gamemastering/
│   └── Gamemastering_NOTES.md               # Conditions, traps, objects
└── (other SRD folders: Spells, Monsters, etc.)
```

The `*_NOTES.md` files compare SRD rules against our implementation, identifying gaps and implementation approaches.

### Dependencies

- **pydantic**: Validation and serialization for all models
- **pytest**: Testing framework
- **pyright**: Type checking
- **fastapi/uvicorn**: API server
- **websockets**: WebSocket client library
- **httpx**: HTTP client for testing

### Project Status

See `claude_docs/MASTER_SUMMARY.md` for current state and roadmap.
