# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

D&D 5e game engine with event-driven architecture and component-based entities. The engine models D&D mechanics through interconnected subsystems: registry, entity-component framework, modifiable values, events, conditions, and actions.

**Core Principle**: All game state changes flow through events.

## Working With This Codebase (CRITICAL)

**The user (Tommaso) is the architect and designer of this codebase.** Claude is here to assist, not to drive. Past sessions have failed badly when Claude acted autonomously, made multiple speculative fixes without validation, or tried to "know better" than the designer.

### Required Behavior

1. **One change, one checkpoint.** Make a single change, then report what you did and ask if it's correct before making the next change. Do NOT chain 5 fixes hoping one works.

2. **Ask before assuming.** If you're unsure how something should work, ASK. Don't guess based on "common patterns" - this codebase has specific design decisions.

3. **Study Python first.** When debugging cross-system issues, trace through the Python backend before touching other layers. The source of truth is always the Python code.

4. **Report failures immediately.** If something doesn't work, say so and ask for guidance. Don't silently try alternative approaches.

5. **No "know-it-all" behavior.** Phrases like "I'll just fix this" or "This should work" followed by 5 failed attempts are not acceptable. Uncertainty means stopping and asking.

### What Killed Previous Sessions

- Making 5+ speculative fixes without user validation
- Not studying backend code before making changes
- Continuing to flail instead of asking for help
- Not using the PvP test loop to validate changes immediately

### The Right Pattern

```
Claude: I made change X. Does this look right?
User: No, try Y instead.
Claude: Done. Here's the result. Should I continue?
User: Yes, now do Z.
```

NOT:

```
Claude: I'll fix this. [change 1] Hmm that didn't work. [change 2] Still broken. [change 3] [change 4] [change 5]
User: What are you doing? That's all wrong.
```

### Dependency Direction (NO CIRCULAR IMPORTS)

**CRITICAL**: Never use "late imports" or "import inside function" to avoid circular imports. If you need a late import, it means the design is wrong - the circular dependency still exists, you're just hiding it.

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

## Development & Testing: PvP CLI Loop (PRIMARY WORKFLOW)

The primary way to develop and test features is through **live PvP combat** between the user and Claude. This provides immediate feedback and allows testing specific scenarios.

### Quick Start

```bash
# Terminal 1: Start server
source .venv/bin/activate
uvicorn server.event_server:app --reload

# Terminal 2: User plays as Hero
python -m cli playpvp

# Claude connects and plays as Skeleton (see Agent Commands below)
```

### Claude Agent Commands

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

### Turn Flow

**CRITICAL**: After `end`, you MUST run `watch` again to stay connected!

```bash
connect → watch → [state/actions/move/attack/end] → watch → repeat
```

`watch` blocks until your turn, shows opponent actions, detects game end.

To restart: User restarts `playpvp`, Claude runs `disconnect` → `connect` → `watch`

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
├── action_economy: ActionEconomy     # actions, bonus_actions, reactions, movement
├── senses: Senses                    # position, visible cells, paths, visible entities
├── proficiency_bonus: ModifiableValue
├── active_conditions: Dict[str, BaseCondition]
└── active_conditions_by_uuid / by_source (lookup dicts)
```

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

## Cross-Entity Modifier Propagation

**Critical Pattern**: When one entity affects another, `to_target` modifiers must be propagated via `set_from_target()`.

```python
# Example: Attacker attacks a Blinded target
# Blinded adds ADVANTAGE to target.equipment.ac_bonus.to_target_static

attacker.set_target_entity(target.uuid)
target.set_target_entity(attacker.uuid)

attack_bonus = attacker.attack_bonus(WeaponSlot.MELEE_MAIN, target.uuid)
ac = target.ac_bonus(attacker.uuid)

# KEY: Propagate to_target modifiers between entities
attack_bonus.set_from_target(ac)  # Now attack_bonus.advantage includes Blinded's ADVANTAGE

# Roll and determine outcome
roll = attacker.roll_d20(attack_bonus, RollType.ATTACK)
outcome = determine_attack_outcome(roll, ac)

# Clean up
attack_bonus.reset_from_target()
attacker.clear_target_entity()
target.clear_target_entity()
```

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
4. **Removal**: `target.remove_condition("Blinded")` → modifiers cleaned up

### Implementing a Condition

```python
class MyCondition(BaseCondition):
    name: str = "MyCondition"
    description: str = "Description here"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids (for parent-child tracking)
        Optional[Event]           # completion event
    ]:
        target = Entity.get(self.target_entity_uuid)
        outs = []

        # Add modifier to appropriate channel
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
        return outs, [], [], effect_event
```

### Sub-conditions Pattern

Conditions like Paralyzed include Incapacitated as a sub-condition:

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

return outs, [], sub_conditions_uuids, effect_event
# When Paralyzed is removed, Incapacitated is automatically removed too
```

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
    ├── position_actions (movement)
    └── self_actions (dash, dodge, disengage)
```

**Functional API** (`dnd/actions_functional.py`):
- `setup_standard_actions(entity)` - Registers Move, Dash, Dodge, Disengage + weapon attacks
- `execute_by_index(entity, name, idx)` - Execute by target index

### Attack Action

Attack validates range and LOS, then:
1. Cross-propagate modifiers via `set_from_target()`
2. Roll d20 with attack bonus vs AC
3. Apply damage on hit

**AttackEvent fields**: `dice_roll`, `attack_outcome`, `damages`, `damage_rolls`

### Cost Types

`actions`, `bonus_actions`, `reactions`, `movement` + optional `resource_name/resource_cost`

## Creating Monsters/Entities

### Factory Function Pattern (`dnd/monsters/bestiary.py`)

```python
def create_goblin(
    source_id: Optional[UUID] = None,
    name: str = "Goblin",
    position: Tuple[int, int] = (0, 0)
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

## Key Files Reference

| Purpose | Location |
|---------|----------|
| **Core** | |
| Entity (main game object) | `dnd/entity.py` |
| ModifiableValue system | `dnd/core/values.py` |
| Modifiers (Advantage, Critical, etc.) | `dnd/core/modifiers.py` |
| Base classes | `dnd/core/base_object.py`, `base_block.py` |
| Event system | `dnd/core/events.py` |
| Combat log models | `dnd/core/combat_log.py` |
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
| Attack, Move, Dash, Dodge, etc. | `dnd/actions.py` |
| Functional API (setup, execute) | `dnd/actions_functional.py` |
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
| Dice processor utilities | `dnd/classes/dice_processor_utils.py` |
| Class module exports | `dnd/classes/__init__.py` |
| **Monsters & Examples** | |
| Simple creatures (Goblin, Skeleton) | `dnd/monsters/bestiary.py` |
| Complex creature example | `dnd/monsters/circus_fighter.py` |
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
| **Server & CLI** | |
| FastAPI server | `server/event_server.py` |
| Session management | `server/session.py` |
| Human CLI (play/playpvp) | `cli/main.py` |
| Claude agent CLI | `cli/agent.py` |
| API client | `cli/api_client.py` |
| Display/rendering | `cli/display.py` |
| Command parsing | `cli/commands.py` |

## Implemented Conditions

All conditions in `dnd/conditions.py`:

| Condition | Self Effects | Effects on Attackers | Sub-conditions |
|-----------|--------------|---------------------|----------------|
| **ActionSurging** | +1 action this turn (1 round duration) | - | - |
| **Blinded** | Disadvantage attacks, auto-fail sight skills | Advantage | - |
| **Charmed** | Auto-miss vs charmer | Charmer: advantage social skills | - |
| **Dashing** | +movement = base speed | - | - |
| **Deafened** | Auto-fail hearing skills | - | - |
| **Disengaging** | Movement doesn't provoke OA | - | - |
| **Dodging** | Advantage DEX saves | Disadvantage | - |
| **Frightened** | Disadvantage attacks/checks (contextual), speed=0 | - | - |
| **Grappled** | Speed max = 0 | - | - |
| **HasAttacked** | Marker for Extra Attack (no modifiers) | - | - |
| **Incapacitated** | All action economy = 0 | - | - |
| **Invisible** | Advantage attacks (contextual) | Disadvantage (contextual) | - |
| **Paralyzed** | Auto-fail STR/DEX saves | Advantage, auto-crit ≤5ft | Incapacitated |
| **Poisoned** | Disadvantage all attacks/checks | - | - |
| **Prone** | Disadvantage attacks | ≤5ft: advantage, >5ft: disadvantage | - |
| **Restrained** | Speed=0, disadvantage attacks, fail DEX | Advantage | - |
| **Stunned** | Auto-fail STR/DEX saves | Advantage | Incapacitated |
| **Unconscious** | Auto-fail STR/DEX saves | Advantage, auto-crit ≤5ft, prone-like | Incapacitated |

### Fighter Conditions (in `dnd/classes/fighter.py`)

| Condition | Effect | Notes |
|-----------|--------|-------|
| **FightingStyleArchery** | +2 ranged attack bonus | Modifier on attack rolls |
| **FightingStyleDefense** | +1 AC when wearing armor | AC modifier |
| **FightingStyleDueling** | +2 damage with one-handed weapon | Damage modifier |
| **GreatWeaponFighting** | Reroll 1s and 2s on damage dice | EventHandler on DAMAGE_ROLLED |
| **FightingStyleProtection** | Impose disadvantage on attacks vs allies | EventHandler, uses reaction |
| **FightingStyleTwoWeaponFighting** | Add ability mod to off-hand damage | Damage modifier |
| **SecondWindFeature** | Grants Second Wind action + resource | Level-based healing |
| **ActionSurgeFeature** | Grants Action Surge action + resource | Once per turn enforcement |
| **ExtraAttackFeature** | Grants Extra Attack actions + resource | 1/2/3 at L5/L11/L20 |
| **ImprovedCritical** | Crit on 19-20 | Critical modifier |
| **SuperiorCritical** | Crit on 18-20 | Critical modifier |
| **Indomitable** | Reroll failed saves | EventHandler on SAVING_THROW |
| **Survivor** | Heal 5+CON at turn start when HP ≤ 50% | EventHandler on TURN_START |

## Global Registries

- `BaseObject._registry: Dict[UUID, BaseObject]` - All objects by UUID
- `Entity._entity_registry: Dict[UUID, Entity]` - All entities
- `Entity._entity_by_position: DefaultDict[Tuple[int,int], List[Entity]]` - Entities by grid position

## Senses and Vision

The `Senses` block tracks what an entity can see and where it can move:

```python
entity.update_entity_senses(max_distance=10)  # Updates visibility and paths
Entity.update_all_entities_senses()            # Updates all entities

# After update:
entity.senses.entities      # Dict[UUID, position] - visible entities
entity.senses.visible       # Dict[position, bool] - visible cells
entity.senses.paths         # Dict[position, List[position]] - paths to reachable cells
entity.senses.get_feet_distance(target.position)  # Distance in feet (1 grid = 5ft)
```

## Spatial System (GridMap)

`GridMap` (`dnd/core/gridmap.py`) is a singleton centralizing spatial data.

```
GridMap (get_map())
├── _tiles: Dict[pos, Tile]              # Tile objects (can have conditions)
├── _entity_positions: Dict[UUID, pos]   # Entity → position
├── _entities_by_position: Dict[pos, Set[UUID]]
└── compute_fov(), compute_paths()       # Shadowcast + Dijkstra
```

**Key methods**: `is_walkable()`, `is_walkable_for()`, `get_entities_at()`, `move_entity()`, `compute_fov()`, `compute_paths()`

**Spatial events**: `SPATIAL_ENTITY_ENTERED`, `SPATIAL_ENTITY_LEFT`, `SPATIAL_TILE_CHANGED` - fired automatically by GridMap.

**Tiles** are `BaseBlock` objects that can have conditions (fire, traps, difficult terrain).

## The Event System

The event system (`dnd/core/events.py`) is the backbone of the engine. **All game state changes flow through events**.

### Event Lifecycle

```
DECLARATION → EXECUTION → EFFECT → COMPLETION (or CANCEL)
```

Each `phase_to()` creates new event with same `lineage_uuid`. EventQueue notifies matching handlers at each phase.

### Key EventTypes

| Type | Purpose |
|------|---------|
| `ATTACK` | Attack action |
| `MOVEMENT` | Move action |
| `DAMAGE_ROLLED` | After dice rolled, before applied (for dice manipulation) |
| `TAKE_DAMAGE` | Damage application |
| `SAVING_THROW` | Save requested/resolved |
| `CONDITION_APPLICATION` | Condition added |
| `SPATIAL_ENTITY_ENTERED` | Entity moved into cell |

### EventHandlers

Handlers subscribe to events via `Trigger(event_type, event_phase, source_uuid?, target_uuid?)`. Register with `EventQueue.add_event_handler()`.

For dice manipulation patterns (Great Weapon Fighting, etc.), see `claude_docs/IMPLEMENTATION_GUIDE.md`.

## Code Verification Rules

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
- **Weapon slots**: Use `entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)` to get weapons. 4 slots: `MELEE_MAIN`, `MELEE_OFF` (can hold shield), `RANGED_MAIN`, `RANGED_OFF`
- **Ability modifier is int**: `entity.ability_scores.strength.modifier` returns `int`, not `ModifiableValue`
- **Always call `Entity.update_all_entities_senses()`** after creating entities for LOS to work

**For writing examples and tests**, see `claude_docs/EXAMPLE_PATTERNS.md` for complete patterns.

**Before running any new script:**
1. `python -m py_compile script.py` - Check syntax
2. `python -c "import script"` - Check imports resolve
3. Only then run the actual script

## Type Checking and Linting

This project uses **Pylance** (VS Code's Python language server) with strict type checking enabled. All code should pass Pylance checks with zero errors.

### Getting Pylance Errors

**IMPORTANT FOR FUTURE CLAUDE SESSIONS**: Currently there's no automated way to access Pylance diagnostics from the CLI. The user must copy/paste errors from VS Code. Future Claude sessions should investigate:
- VS Code extensions or APIs that export diagnostics to a file
- Using `pylsp` (Python Language Server Protocol) from CLI
- Pylance CLI mode or diagnostic export features
- Integration with `pyright` (Pylance's underlying type checker): `pyright --outputjson`

For now, ask the user to paste Pylance errors if you need them.

### Common Type Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `reportUnusedVariable` | Variable assigned but never read | Rename to `_` (e.g., `for _, value in items()`) |
| `reportUnusedImport` | Import not used in file | Remove the import (but verify it's truly unused first!) |
| `reportArgumentType` | Wrong type passed to function | Use `cast()`, add type narrowing with `isinstance()`, or fix the type |
| `reportAssignmentType` | Assigning wrong type to typed variable | Use `cast()` or fix the assignment |
| `reportCallIssue: No parameter named X` | Pydantic inheritance not recognized | Explicitly redeclare the field in subclass |

### Pydantic + Pylance Gotchas

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

### Type Narrowing Patterns

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

### TYPE_CHECKING Import Pattern

For imports only needed for type hints (avoids circular imports):

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dnd.core.events import SpatialChangeEvent  # Only imported for type hints

def process(event: "SpatialChangeEvent") -> None:  # Use string annotation
    ...
```

### Files with Known Legacy Issues

`examples/old_examples/*.py` - These files import from `dnd.interfaces` which no longer exists. They are legacy/deprecated and have unresolvable type errors without refactoring or removal.

## CLI and Server Architecture

### Overview

The D&D Engine uses a terminal-based CLI for gameplay. Two CLIs are provided:
- **Human CLI** (`cli/main.py`): Rich terminal interface for human players
- **Agent CLI** (`cli/agent.py`): Simple command interface for Claude to play as opponent

Both connect to a FastAPI server that manages game state, sessions, and combat.

### Game Modes

| Mode | Command | Description |
|------|---------|-------------|
| Human vs AI | `python -m cli play` | Human controls Hero, AI controls Skeleton automatically |
| Human vs Claude | `python -m cli playpvp` | Human controls Hero, Claude controls Skeleton via agent CLI |

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
- `GET /combat-log` - Get server-side combat log entries

### Server-Side Combat Log

The server maintains a unified combat log using `CombatLogEntry` objects (`dnd/core/combat_log.py`). Events auto-generate their combat log entries at COMPLETION phase via `generate_combat_log()`.

**CombatLogEntry Structure:**
```python
class CombatLogEntry(BaseModel):
    entry_type: CombatLogEntryType  # "attack", "movement", "action", etc.
    source_name: str
    source_uuid: str
    target_name: Optional[str]
    target_uuid: Optional[str]
    summary: str                    # One-line summary for display
    detail_lines: List[str]         # Verbose breakdown lines
    data: Dict[str, Any]            # Typed data (AttackLogData, MovementLogData, etc.)
    success: Optional[bool]
```

**Entry Types** (`CombatLogEntryType`):
- `ATTACK`, `MOVEMENT`, `ACTION` (Dash/Dodge/Disengage)
- `SAVING_THROW`, `SKILL_CHECK`
- `CONDITION_APPLIED`, `CONDITION_REMOVED`
- `DAMAGE_TAKEN`, `HEAL`, `DEATH`
- `TURN_START`, `TURN_END`

**Typed Data Models** (in `data` field):
- `AttackLogData`: attacker_name, target_name, weapon_name, attack_roll (DiceRollDisplay), attack_breakdown, target_ac, ac_breakdown, outcome, damage_rolls, total_damage
- `MovementLogData`: entity_name, start_position, end_position, path, distance_feet
- `SavingThrowLogData`: entity_name, ability, dc, roll, bonus_breakdown, success
- `SkillCheckLogData`: entity_name, skill, dc, roll, bonus_breakdown, success

**API Endpoints:**
- `GET /combat-log?since=N` - Returns `CombatLogEntry.to_dict()` (raw `model_dump()`)
- CLI uses proper field names: `entry_type`, `summary`, `data["entity_name"]`, etc.

**Modifier Breakdown System** (`dnd/core/values.py`):
- `ModifiableValue.get_breakdown()` - Extracts numerical modifiers with cleaned names
- `ModifiableValue.get_advantage_breakdown()` - Extracts advantage/disadvantage sources
- Name cleanup: `"proficiency_bonus_base_value"` → `"Prof"`, `"dexterity Ability Score_base_value"` → `"DEX"`

### Agent CLI Session Persistence

The agent CLI stores session info in `/tmp/dnd_agent_session.txt` so session persists between commands:

```bash
# First command creates session
python -m cli.agent connect    # Creates session, saves to /tmp/dnd_agent_session.txt

# Subsequent commands load session automatically
python -m cli.agent state      # Loads session from file
python -m cli.agent attack 0   # Uses same session

# Clear session for new game
python -m cli.agent disconnect # Removes session file
```

### Agent CLI: The `watch` Command

The `watch` command is the primary way Claude stays engaged with the game:

```bash
python -m cli.agent watch
```

Behavior:
1. Polls server every 2 seconds
2. Shows opponent actions from combat log as they happen (attacks, moves, deaths)
3. When it becomes Claude's turn, displays full state + available actions
4. Detects encounter end (by HP check or encounter state) and exits cleanly
5. Ctrl+C to interrupt manually

This enables a smooth flow: `connect` → `watch` → take actions → `end` → `watch` → repeat

### CLI Files

| File | Purpose |
|------|---------|
| `cli/main.py` | Human player CLI with `play` and `playpvp` commands |
| `cli/agent.py` | Claude agent CLI (connect, watch, state, actions, move, attack, end) |
| `cli/api_client.py` | HTTP client wrapper with session management |
| `cli/display.py` | Rich terminal rendering (map, entities, combat log, action results) |
| `cli/commands.py` | Command parsing and execution for human CLI |

## Dependencies

- **pydantic**: Validation and serialization for all models
- **pytest**: Testing framework
- **pyright**: Type checking
- **fastapi/uvicorn**: API server
- **websockets**: WebSocket client library
- **httpx**: HTTP client for testing

## Documentation Folders

### claude_docs/

Contains focused implementation guides:

| File | Purpose |
|------|---------|
| `MASTER_SUMMARY.md` | Project status, what's implemented, roadmap |
| `CLI_GUIDE.md` | How to use CLI and Agent commands |
| `IMPLEMENTATION_GUIDE.md` | **READ FIRST** - How to implement conditions, actions, event handlers |
| `CLASS_SYSTEM.md` | Fighter implementation, feature condition patterns, dice processors |
| `EXAMPLE_PATTERNS.md` | Code snippets for writing examples/tests |
| `archive/` | Completed planning docs (historical reference) |

### interactive_ruleset/

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

## Class System

Fighter + Champion archetype fully implemented (L1-L18). See `dnd/classes/fighter.py` and `claude_docs/IMPLEMENTATION_GUIDE.md` for patterns.

## Project Status

See `claude_docs/MASTER_SUMMARY.md` for current state and roadmap.
