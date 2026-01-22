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
- Debugging TypeScript when the bug was in Python event flow
- Not studying backend code before writing frontend code
- Assuming WebSocket message delivery was reliable (it wasn't)
- Continuing to flail instead of asking for help

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

# Run combat examples
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
├── equipment: Equipment              # Weapons, armor, shield, AC calculation
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

attack_bonus = attacker.attack_bonus(WeaponSlot.MAIN_HAND, target.uuid)
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

Actions (`dnd/core/base_actions.py`, `dnd/actions.py`) are the primary way to modify game state. All actions go through events, enabling reactions and modifications.

### Two Implementation Patterns

| Pattern | Use Case | Example |
|---------|----------|---------|
| **BaseAction** | Direct override of `_validate()` and `_apply()` | `Attack`, `Move` |
| **StructuredAction** | Pipeline with `prerequisites` and `consequences` OrderedDicts | `attack_factory()` |

### BaseAction Flow

```
BaseAction.apply()
    │
    ├── check_costs() → CostEvaluator callable validates affordability
    │
    ├── _create_declaration_event() → ActionEvent in DECLARATION phase
    │
    ├── _validate() → Check prerequisites
    │       └── Returns event in EXECUTION phase if valid
    │       └── Returns canceled event if invalid
    │
    ├── _apply() → Execute the action logic
    │       └── EXECUTION → EFFECT → COMPLETION phases
    │
    └── _apply_costs() → Deduct from action economy
            └── entity.action_economy.consume(cost_type, cost)
```

### Cost System

Actions have costs validated before execution and applied after completion:

```python
from dnd.actions import Cost, entity_action_economy_cost_evaluator

# Define a cost
Cost(
    name="Attack Cost",
    cost_type="actions",      # "actions" | "bonus_actions" | "reactions" | "movement"
    cost=1,
    evaluator=entity_action_economy_cost_evaluator  # Checks can_afford()
)

# Cost evaluator signature
def entity_action_economy_cost_evaluator(source_entity_uuid: UUID, cost_type: CostType, cost: int) -> bool:
    entity = Entity.get(source_entity_uuid)
    return entity.action_economy.can_afford(cost_type, cost)
```

### Attack Action (Complete Flow)

```python
from dnd.actions import Attack
from dnd.blocks.equipment import WeaponSlot

# Create and execute an attack
attack = Attack(
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MAIN_HAND,
    name="Scimitar Attack"
)
event = attack.apply()  # Returns AttackEvent with all results

# AttackEvent contains:
event.dice_roll        # DiceRoll object
event.attack_bonus     # ModifiableValue used for the roll
event.ac               # Target's AC as ModifiableValue
event.attack_outcome   # AttackOutcome.HIT, MISS, CRIT, CRIT_MISS
event.damages          # List[Damage] - damage specs
event.damage_rolls     # List[DiceRoll] - actual damage rolled
event.canceled         # bool - True if attack was canceled
event.status_message   # str - description of what happened
```

### Attack Validation Pipeline

```python
# In Attack._validate():
1. validate_range()          # Check weapon range vs distance to target
2. validate_line_of_sight()  # Check target in source's senses.entities
```

### Attack Execution (attack_consequences)

```python
# In Attack._apply() → attack_consequences():

# 1. Set up cross-entity targeting
source_entity.set_target_entity(target_entity_uuid)
target_entity.set_target_entity(source_entity_uuid)

# 2. Get bonuses
attack_bonus = source_entity.attack_bonus(weapon_slot, target_entity_uuid)
ac = target_entity.ac_bonus(source_entity.uuid)

# 3. Cross-propagate modifiers (KEY STEP!)
ac.set_from_target(attack_bonus)
attack_bonus.set_from_target(ac)

# 4. Roll and determine outcome
dice_roll = source_entity.roll_d20(attack_bonus, RollType.ATTACK)
attack_outcome = determine_attack_outcome(dice_roll, ac)

# 5. Apply damage on hit
if attack_outcome in [AttackOutcome.HIT, AttackOutcome.CRIT]:
    damages = source_entity.get_damages(weapon_slot, target_entity_uuid)
    damage_rolls = target_entity.take_damage(damages, attack_outcome)

# 6. Clean up
ac.reset_from_target()
attack_bonus.reset_from_target()
source_entity.clear_target_entity()
target_entity.clear_target_entity()
```

### Move Action

```python
from dnd.actions import Move

# Move to a position (path computed automatically from senses.paths)
move = Move(
    source_entity_uuid=entity.uuid,
    end_position=(5, 3),
    use_movement_cost=True  # Deducts from action_economy.movement
)
event = move.apply()

# MovementEvent contains:
event.start_position   # Where movement started
event.end_position     # Where movement ended
event.path             # List of positions traversed
```

### StructuredAction Pattern

Alternative way to define actions using pipelines:

```python
from dnd.actions import StructuredAction, Attack, validate_line_of_sight
from collections import OrderedDict

attack = StructuredAction(
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=target.uuid,
    name="Attack",
    description="An attack action",
    costs=[Cost(name="Attack Cost", cost_type="actions", cost=1,
                evaluator=entity_action_economy_cost_evaluator)],
    prerequisites=OrderedDict({
        "validate_range": Attack.validate_range,
        "validate_line_of_sight": validate_line_of_sight
    }),
    consequences=OrderedDict({
        "attack_consequences": Attack.attack_consequences
    }),
    cost_applier=entity_action_economy_cost_applier
)
event = attack.apply()
```

### Implementing a New Action

```python
class MyAction(BaseAction):
    name: str = Field(default="MyAction")
    description: str = Field(default="Does something")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Action Cost", cost_type="actions", cost=1,
             evaluator=entity_action_economy_cost_evaluator)
    ])

    # Custom fields for this action
    my_param: int = Field(description="Custom parameter")

    def _create_declaration_event(self, parent_event=None, use_register=True):
        return ActionEvent(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            costs=[BaseCost.model_validate(c) for c in self.costs],
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register
        )

    def _validate(self, declaration_event):
        # Check prerequisites, return canceled event if invalid
        source = Entity.get(self.source_entity_uuid)
        if not source:
            return declaration_event.cancel(status_message="Source not found")

        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Validated"
        )

    def _apply(self, execution_event):
        # Do the thing
        effect_event = execution_event.phase_to(EventPhase.EFFECT, status_message="Applying")

        # ... actual logic here ...

        return effect_event.phase_to(EventPhase.COMPLETION, status_message="Done")

    def _apply_costs(self, completion_event):
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)
```

### Pre-validation (UI Support)

Check if an action can be performed without executing it:

```python
attack = Attack(source_entity_uuid=..., target_entity_uuid=..., weapon_slot=...)

if attack.pre_validate():
    # Action is valid, can show as enabled in UI
    event = attack.apply()
else:
    # Action would fail, show as disabled
    pass
```

## Creating Monsters/Entities

### Factory Function Pattern (`dnd/monsters/bestiary.py`)

```python
def create_goblin(name: str = "Goblin", position: Tuple[int, int] = (0, 0)) -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=8, dexterity=14, constitution=10,
            intelligence=10, wisdom=8, charisma=8
        ),
        health=HealthConfig(hit_dice_count=2, hit_dice_value=6),
        equipment=EquipmentConfig(
            weapon_main_hand=Weapon(
                name="Scimitar",
                damage_dice=6, damage_type=DamageType.SLASHING,
                attack_bonus=0, damage_bonus=0,
                properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT],
                range=Range(type=RangeType.REACH, normal=5)
            ),
            armor=Armor(name="Leather", base_ac=11, armor_type=ArmorType.LIGHT),
            shield=Shield(name="Shield", ac_bonus=2)
        ),
        action_economy=ActionEconomyConfig(movement=30),
        proficiency_bonus=2,
        position=position
    )
    return Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
```

## Key Files Reference

| Purpose | Location |
|---------|----------|
| **Core** | |
| Entity (main game object) | `dnd/entity.py` |
| ModifiableValue system | `dnd/core/values.py` |
| Modifiers (Advantage, Critical, etc.) | `dnd/core/modifiers.py` |
| Base classes | `dnd/core/base_object.py`, `base_block.py` |
| Event system | `dnd/core/events.py` |
| Dice rolling | `dnd/core/dice.py` |
| **Spatial System** | |
| GridMap (central spatial manager) | `dnd/core/gridmap.py` |
| Tile class (BaseBlock, can have conditions) | `dnd/core/base_tiles.py` |
| Shadowcast FOV algorithm | `dnd/core/shadowcast.py` |
| Dijkstra pathfinding | `dnd/core/dijkstra.py` |
| **Conditions & Actions** | |
| Base condition class | `dnd/core/base_conditions.py` |
| All D&D conditions | `dnd/conditions.py` |
| Base action class | `dnd/core/base_actions.py` |
| Attack, Move actions | `dnd/actions.py` |
| **Entity Blocks** | |
| Ability scores | `dnd/blocks/abilities.py` |
| Skills | `dnd/blocks/skills.py` |
| Saving throws | `dnd/blocks/saving_throws.py` |
| Health/HP | `dnd/blocks/health.py` |
| Equipment (weapons, armor) | `dnd/blocks/equipment.py` |
| Action economy | `dnd/blocks/action_economy.py` |
| Senses (vision, position) | `dnd/blocks/sensory.py` |
| **Monsters & Examples** | |
| Simple creatures (Goblin, Skeleton) | `dnd/monsters/bestiary.py` |
| Complex creature example | `dnd/monsters/circus_fighter.py` |
| Basic combat demo | `examples/combat_basic.py` |
| Condition tests | `examples/combat_conditions.py` |
| Spatial events test | `examples/spatial_events_test.py` |

## Implemented Conditions

All conditions in `dnd/conditions.py`:

| Condition | Self Effects | Effects on Attackers | Sub-conditions |
|-----------|--------------|---------------------|----------------|
| **Blinded** | Disadvantage attacks, auto-fail sight skills | Advantage | - |
| **Charmed** | Auto-miss vs charmer | Charmer: advantage social skills | - |
| **Dashing** | +movement = base speed | - | - |
| **Deafened** | Auto-fail hearing skills | - | - |
| **Dodging** | Advantage DEX saves | Disadvantage | - |
| **Frightened** | Disadvantage attacks/checks (contextual), speed=0 | - | - |
| **Grappled** | Speed max = 0 | - | - |
| **Incapacitated** | All action economy = 0 | - | - |
| **Invisible** | Advantage attacks (contextual) | Disadvantage (contextual) | - |
| **Paralyzed** | Auto-fail STR/DEX saves | Advantage, auto-crit ≤5ft | Incapacitated |
| **Poisoned** | Disadvantage all attacks/checks | - | - |
| **Prone** | Disadvantage attacks | ≤5ft: advantage, >5ft: disadvantage | - |
| **Restrained** | Speed=0, disadvantage attacks, fail DEX | Advantage | - |
| **Stunned** | Auto-fail STR/DEX saves | Advantage | Incapacitated |
| **Unconscious** | Auto-fail STR/DEX saves | Advantage, auto-crit ≤5ft, prone-like | Incapacitated |

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

The `GridMap` (`dnd/core/gridmap.py`) is a singleton that centralizes all spatial data management. It replaces scattered tile loops with efficient lookups.

### GridMap Architecture

```
GridMap (singleton via get_map())
├── Tile Storage
│   ├── _tiles: Dict[Tuple[int,int], Tile]         # Tile objects (BaseBlock, can have conditions)
│   └── _bounds_dirty + cached min/max             # Lazy bounds calculation
│
├── Entity Position Tracking
│   ├── _entity_positions: Dict[UUID, position]    # Entity → position
│   └── _entities_by_position: Dict[pos, Set[UUID]]# Position → entities
│
├── Cell Subscription System
│   ├── _cell_subscribers: Dict[pos, Set[UUID]]    # Cell → subscribed entities
│   └── _entity_subscriptions: Dict[UUID, Set[pos]]# Entity → subscribed cells
│
└── Spatial Algorithms
    ├── compute_fov(origin, max_distance)                           # Shadowcast
    └── compute_paths(start, max_distance, requesting_entity_uuid)  # Dijkstra with occupancy
```

### Basic Usage

```python
from dnd.core.gridmap import get_map, reset_map

grid = get_map()  # Get singleton instance

# Create tiles
grid.create_rectangle(0, 0, 10, 10)  # 10x10 floor
grid.create_room(0, 0, 10, 10)       # Room with walls

# Query tiles
grid.is_walkable(5, 5)                      # bool - tile property only
grid.is_walkable_for(5, 5, entity_uuid)     # bool - tile + occupancy check
grid.is_visible(5, 5)                       # bool (can see through)
grid.get_tile(5, 5)                         # Tile object or None

# Entity position tracking (auto-registered on Entity creation)
grid.get_entity_position(entity_uuid)  # Tuple[int, int]
grid.get_entities_at((5, 5))           # Set[UUID]
grid.move_entity(uuid, (new_x, new_y)) # Updates + fires events

# Spatial queries (with occupancy awareness)
grid.compute_fov((5, 5), max_distance=10)                    # List of visible positions
grid.compute_paths((5, 5), max_distance=20)                  # Tile-only walkability
grid.compute_paths((5, 5), max_distance=20, entity_uuid)     # Excludes occupied cells
grid.get_visible_entities((5, 5), max_distance)              # Dict[UUID, position]

# Tiles can have conditions (fire, traps, difficult terrain)
tile = grid.get_tile(5, 5)
tile.add_condition(OnFire(source_entity_uuid=caster.uuid, target_entity_uuid=tile.uuid))
```

### Cell Subscription System

Entities subscribe to cells they can see. When something changes in a subscribed cell, `SpatialChangeEvent`s are fired, enabling reactive updates.

```python
# Entities auto-subscribe when updating senses
entity.update_entity_senses(max_distance=10)
# This internally calls: get_map().subscribe_to_cells(entity.uuid, visible_cells)

# Query subscriptions
grid.get_entity_subscriptions(entity.uuid)  # Set of cells entity watches
grid.get_subscribers_at((5, 5))             # Set of entities watching cell

# Manual subscription (rarely needed)
grid.subscribe_to_cells(entity.uuid, {(1,1), (1,2), (2,1)})
grid.unsubscribe_entity(entity.uuid)
```

### Spatial Events

GridMap fires `SpatialChangeEvent`s when spatial state changes:

| Event Type | Fired When | Key Fields |
|------------|------------|------------|
| `SPATIAL_ENTITY_ENTERED` | Entity moves into a cell | `position`, `entity_uuid`, `old_position` |
| `SPATIAL_ENTITY_LEFT` | Entity leaves a cell | `position`, `entity_uuid`, `old_position` (new pos) |
| `SPATIAL_TILE_CHANGED` | Tile walkable/visible changes | `position`, `tile_walkable`, `tile_visible` |

```python
# Events are fired automatically by GridMap methods:
grid.move_entity(uuid, new_pos)  # Fires LEFT for old pos, ENTERED for new pos
grid.set_tile(x, y, walkable=False)  # Fires TILE_CHANGED if properties differ
Entity.update_entity_position(entity, new_pos)  # Also fires events

# Events go through EventQueue and can be queried:
from dnd.core.events import EventQueue, EventType

entered_events = EventQueue.get_events_by_type(EventType.SPATIAL_ENTITY_ENTERED)
```

### Shadowcast FOV Algorithm

`dnd/core/shadowcast.py` implements recursive shadowcasting for field-of-view:

```python
from dnd.core.shadowcast import compute_fov

def is_blocking(x, y) -> bool:
    return not grid.is_visible(x, y)  # Walls block vision

visible = []
def mark_visible(x, y):
    visible.append((x, y))

compute_fov(origin=(5, 5), is_blocking=is_blocking,
            mark_visible=mark_visible, max_distance=10)
```

### Dijkstra Pathfinding Algorithm

`dnd/core/dijkstra.py` implements Dijkstra's algorithm with diagonal movement:

```python
from dnd.core.dijkstra import dijkstra

distances, paths = dijkstra(
    start=(0, 0),
    is_walkable=lambda x, y: grid.is_walkable(x, y),
    grid_width=20,
    grid_height=20,
    diagonal=True,      # Allow diagonal movement
    max_distance=30     # Stop after this distance
)

# distances: Dict[pos, int] - walking distance to each reachable cell
# paths: Dict[pos, List[pos]] - full path to each reachable cell
```

### Tile as BaseBlock

`Tile` (`dnd/core/base_tiles.py`) is now a proper `BaseBlock` that can have conditions:

```python
from dnd.core.base_tiles import Tile, floor_factory, wall_factory

# Create tiles via GridMap (recommended)
grid.create_rectangle(0, 0, 10, 10)

# Or create individual tiles
tile = Tile.create(position=(5, 5), walkable=True, visible=True, name="Floor")

# Tiles can have conditions attached
tile.add_condition(OnFire(...))       # Tile is on fire
tile.add_condition(DifficultTerrain())  # Costs double movement
tile.add_condition(TrapCondition(...))  # Triggered on entry
```

## The Event System (Deep Dive)

The event system (`dnd/core/events.py`) is the backbone of the engine. **All game state changes flow through events**, enabling reactions, logging, and external consumers (like websockets).

### Event Architecture

```
EventQueue (static class)
├── Storage Indices (all events stored in multiple lookups)
│   ├── _events_by_uuid: Dict[UUID, Event]
│   ├── _events_by_lineage: Dict[UUID, List[Event]]    # Event history
│   ├── _events_by_type: Dict[EventType, List[Event]]
│   ├── _events_by_phase: Dict[EventPhase, List[Event]]
│   ├── _events_by_source: Dict[UUID, List[Event]]
│   ├── _events_by_target: Dict[UUID, List[Event]]
│   ├── _events_by_timestamp: Dict[datetime, List[Event]]
│   └── _all_events: List[Event]                       # Chronological
│
├── Handler Registry
│   ├── _event_handlers: Dict[UUID, EventHandler]
│   ├── _event_handlers_by_trigger: Dict[Trigger, List[EventHandler]]
│   └── _event_handlers_by_simple_trigger: Dict[Trigger, List[EventHandler]]
│
└── Core Methods
    ├── register(event) → Event    # Store + notify handlers
    ├── add_event_handler(handler) # Subscribe to events
    └── remove_event_handler(handler)
```

### Event Lifecycle

```
1. DECLARATION  ──┐
                  │  event.phase_to() creates new event with next phase
2. EXECUTION   ───┤  (new UUID, same lineage_uuid)
                  │
3. EFFECT      ───┤  At each phase, EventQueue notifies matching handlers
                  │
4. COMPLETION  ───┘  Final state, no further transitions
       │
       └── CANCEL (alternative end state)
```

### Event Class Hierarchy

```
Event (BaseObject)
├── name, event_type, phase, timestamp
├── lineage_uuid (shared across phases)
├── parent_event, children_events
├── modified, canceled, status_message
│
├── phase_to(new_phase) → Event    # Transition to next phase
├── cancel(message) → Event        # Cancel the event
├── post(**updates) → Event        # Update and re-broadcast
│
└── Subclasses
    ├── ActionEvent          # Base for all action events
    ├── AttackEvent          # Attack-specific fields
    ├── MovementEvent        # Movement-specific fields
    ├── SpatialChangeEvent   # GridMap spatial changes
    ├── D20Event             # Base for dice-based events
    │   ├── SavingThrowEvent
    │   └── SkillCheckEvent
    └── (more in dnd/core/events.py)
```

### Event Registration Flow

```python
# When an event is created with use_register=True (default):
event = AttackEvent(source_entity_uuid=..., target_entity_uuid=..., ...)

# In Event.__init__():
if self.use_register:
    EventQueue.register(self)

# EventQueue.register():
1. Store event in all indices (_events_by_uuid, _events_by_type, etc.)
2. Find matching handlers via Trigger matching
3. Call each handler, which may return modified event
4. Return final event (possibly modified by handlers)
```

### Triggers and EventHandlers

Triggers define when a handler should fire:

```python
from dnd.core.events import Trigger, EventHandler, EventType, EventPhase

# A trigger matches events by type, phase, and optionally source/target
trigger = Trigger(
    event_type=EventType.ATTACK,
    event_phase=EventPhase.EXECUTION,
    event_source_entity_uuid=attacker.uuid,  # Optional: only from this entity
    event_target_entity_uuid=None             # Optional: only targeting this entity
)

# Handler with trigger
def my_reaction(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    # Can modify event, cancel it, or return None (no change)
    return event.model_copy(update={"modified": True, "status_message": "Reacted!"})

handler = EventHandler(
    source_entity_uuid=reactor.uuid,
    trigger_conditions=[trigger],
    event_processor=my_reaction
)

# Register handler
EventQueue.add_event_handler(handler)

# Now when a matching event occurs, my_reaction is called
```

### Simple vs Complex Triggers

```python
# Simple trigger: only type + phase (most common)
simple = Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT)
simple.is_simple()  # True

# Complex trigger: includes source/target filters
complex = Trigger(
    event_type=EventType.ATTACK,
    event_phase=EventPhase.EFFECT,
    event_source_entity_uuid=enemy.uuid  # Only attacks FROM this enemy
)
complex.is_simple()  # False

# EventQueue uses separate indices for fast lookup:
# - Simple triggers: _event_handlers_by_simple_trigger
# - Complex triggers: _event_handlers_by_trigger (checked after simple)
```

### Event History (Lineage)

Events maintain history via `lineage_uuid`:

```python
# Initial event
attack = AttackEvent(...)  # Gets new uuid AND new lineage_uuid

# Phase transition creates new event with SAME lineage_uuid
execution_event = attack.phase_to(EventPhase.EXECUTION)
# execution_event.uuid != attack.uuid (new UUID)
# execution_event.lineage_uuid == attack.lineage_uuid (same lineage)

# Get full history of an event
history = EventQueue.get_event_history(execution_event.uuid)
# Returns all events with same lineage_uuid, sorted by timestamp
```

### Parent-Child Events

Events can have parent-child relationships (different from lineage):

```python
# Attack spawns damage events as children
attack_event = AttackEvent(...)

damage_event = DamageEvent(
    parent_event=attack_event.uuid,  # Links to parent
    ...
)
attack_event.add_child_event(damage_event)

# Query relationships
attack_event.get_children_events()  # List of child events
damage_event.get_parent_event()     # The attack event
```

### Key EventTypes

| Type | Purpose |
|------|---------|
| `ATTACK` | Attack action |
| `MOVEMENT` | Move action |
| `TAKE_DAMAGE` | Damage application |
| `HEAL` | Healing |
| `CONDITION_APPLICATION` | Condition added |
| `CONDITION_REMOVAL` | Condition removed |
| `SAVING_THROW` | Save requested/resolved |
| `SKILL_CHECK` | Skill check requested/resolved |
| `SPATIAL_ENTITY_ENTERED` | Entity moved into cell |
| `SPATIAL_ENTITY_LEFT` | Entity left cell |
| `SPATIAL_TILE_CHANGED` | Tile properties changed |
| `TRIGGER_EVENT` | An event handler triggered |

### Querying Events

```python
from dnd.core.events import EventQueue, EventType, EventPhase

# By type
attacks = EventQueue.get_events_by_type(EventType.ATTACK)

# By phase
completed = EventQueue.get_events_by_phase(EventPhase.COMPLETION)

# By source/target entity
from_attacker = EventQueue.get_events_by_source(attacker.uuid)
targeting_defender = EventQueue.get_events_by_target(defender.uuid)

# Chronological
recent = EventQueue.get_latest_events(count=10)
all_events = EventQueue.get_events_chronological()
time_range = EventQueue.get_events_chronological(start_time=t1, end_time=t2)

# Single event by UUID
event = EventQueue.get_event_by_uuid(some_uuid)
```

### Creating Custom Events

```python
from dnd.core.events import Event, EventType, EventPhase

class MyCustomEvent(Event):
    name: str = Field(default="My Custom Event")
    event_type: EventType = Field(default=EventType.BASE_ACTION)  # Or add new type

    # Custom fields
    custom_data: str = Field(description="Whatever you need")
    result: Optional[int] = Field(default=None)

    @classmethod
    def create(cls, source_uuid: UUID, data: str) -> 'MyCustomEvent':
        return cls(
            source_entity_uuid=source_uuid,
            custom_data=data,
            phase=EventPhase.DECLARATION
        )
```

### Event System Best Practices

1. **Always use events for state changes** - Don't modify entity state directly
2. **Let events flow through phases** - DECLARATION → EXECUTION → EFFECT → COMPLETION
3. **Use handlers for reactions** - Don't poll; subscribe to relevant event types
4. **Clean up handlers** - Call `handler.remove()` when done
5. **Query via EventQueue** - Don't store events yourself; use the indices

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
- **No `get_weapon()` method**: Use `entity.equipment.weapon_main_hand` directly
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

## Dependencies

- **pydantic**: Validation and serialization for all models
- **pytest**: Testing framework
- **pyright**: Type checking
- **fastapi/uvicorn**: API server
- **websockets**: WebSocket client library
- **httpx**: HTTP client for testing

## Documentation Folders

### claude_docs/

Contains high-level architecture documents and implementation plans created during Claude sessions:

| File | Purpose |
|------|---------|
| `MASTER_SUMMARY.md` | High-level implementation plan for encounter system, lists what exists vs what's needed, proposed new modules |
| `CODEBASE_ANALYSIS.md` | Deep dive into existing primitives (Entity, Senses, GridMap, Events, Actions), how they integrate, and what's needed for turn-based combat |
| `EXAMPLE_PATTERNS.md` | **IMPORTANT**: Correct patterns for writing examples and tests - read before writing any new example code |
| `AVAILABLE_ACTIONS_DESIGN.md` | Design document for the available actions query system |
| `UI_ARCHITECTURE.md` | **ABANDONED** - Design doc for a web UI that was never completed. Keep for reference only. |
| `FRONTEND_POSTMORTEM.md` | **LESSONS LEARNED** - Post-mortem of failed UI attempt. Documents what went wrong (too autonomous, no user validation, debugging wrong layer). Read this to understand how NOT to work on this codebase. |

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

## Next Steps: Encounter Module

Based on codebase analysis, the next major feature is turn-based combat. Key components needed:

### 1. EncounterManager (new: `dnd/encounter.py`)
- Track combatants, initiative order, current turn, round number
- `start_turn()` must call `entity.action_economy.reset_all_costs()`
- `end_turn()` must call `entity.advance_duration_condition()` for all conditions
- Fire `TURN_START`, `TURN_END`, `ROUND_START`, `ROUND_END` events

### 2. Available Actions Query
- `get_attack_targets(entity)` - entities in weapon range from `senses.entities`
- `get_movement_positions(entity)` - reachable cells from `senses.paths` filtered by remaining movement
- Critical for both UI rendering and future AI decision-making

### 3. Perception/Stealth System
- Hidden state tracking on Entity
- Passive Perception = 10 + perception skill bonus
- Filter `senses.entities` to exclude hidden entities

### 4. Interactables (new: `dnd/interactables.py`)
- `DestructibleObject` - HP, AC, damage threshold
- `Trap` - trigger on spatial events, perception DC, disable DC
- `PickableItem` - inventory integration

### Integration Points Already Working
- `ActionEconomy.reset_all_costs()` exists, just needs to be called at turn start
- `GridMap` fires spatial events on movement (for trap triggers)
- `EventHandler` system supports turn-based condition processing
- `Senses` already tracks everything needed for available actions query
