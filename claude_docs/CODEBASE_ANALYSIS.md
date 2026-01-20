# Codebase Analysis for Encounter Module

## Purpose

This document analyzes the existing codebase primitives and how they should integrate to build a proper turn-based encounter system. The goal is to understand what we have, what we need, and how to wire everything together.

---

## Part 1: Existing Primitives Inventory

### 1.1 Entity System (`entity.py`)

The `Entity` class is the central game object, composed of specialized blocks:

```
Entity (BaseBlock)
├── ability_scores: AbilityScores     # STR, DEX, CON, INT, WIS, CHA
├── skill_set: SkillSet               # 18 skills
├── saving_throws: SavingThrowSet     # 6 saves
├── health: Health                    # HP, temp HP, damage
├── equipment: Equipment              # Weapons, armor, 11 slots
├── action_economy: ActionEconomy     # actions, bonus, reactions, movement
├── senses: Senses                    # position, FOV, paths, visible entities
├── proficiency_bonus: ModifiableValue
├── active_conditions: Dict[str, BaseCondition]
└── sprite_name: Optional[str]
```

**Key Methods Relevant to Encounter:**
| Method | Purpose | Event Integration |
|--------|---------|-------------------|
| `update_entity_senses(max_distance)` | Recompute FOV, paths, visible entities | Subscribes to cells in GridMap |
| `update_all_entities_senses()` | Batch update all entities | Called after movement |
| `move(new_position)` | Move entity and update senses | Uses `update_entity_position()` |
| `add_condition(condition)` | Apply condition with save throw | Fires condition events |
| `advance_duration_condition(name)` | Progress condition (for turns) | Checks removal saves |
| `saving_throw(request)` | Make a save | Returns outcome tuple |
| `skill_check(request)` | Make a skill check | Returns outcome tuple |

**Class-Level Registries:**
- `_entity_registry: Dict[UUID, Entity]` - All entities by UUID
- `_entity_by_position: Dict[Tuple, List[Entity]]` - Entities by grid position

### 1.2 Senses System (`blocks/sensory.py`)

The `Senses` block tracks what an entity perceives:

```python
class Senses(BaseBlock):
    position: Tuple[int, int]                              # Current location
    entities: Dict[UUID, Tuple[int,int]] = {}              # Visible entities + positions
    visible: Dict[Tuple[int,int], bool] = {}               # Visible cells
    walkable: Dict[Tuple[int,int], bool] = {}              # Walkable cells
    paths: DefaultDict[Tuple, List[Tuple]] = defaultdict() # Paths to positions
    seen: Set[Tuple[int,int]] = set()                      # Historical seen cells
    extra_senses: List[SensesType] = []                    # Blindsight, Darkvision, etc.
```

**Key Methods:**
| Method | Purpose | Use in Encounter |
|--------|---------|------------------|
| `get_distance(position)` | Grid distance | Range validation |
| `get_feet_distance(position)` | Distance in feet (×5) | D&D range checking |
| `get_threathened_positions()` | Adjacent visible cells | Opportunity attacks, threatened area |
| `update_senses(entities, visible, walkable, paths)` | Full update | After movement/FOV change |

**SensesType Enum:**
```python
BLINDSIGHT = "blindsight"
DARKVISION = "darkvision"
TREMORSENSE = "tremorsense"
TRUESIGHT = "truesight"
```

### 1.3 GridMap System (`core/gridmap.py`)

Singleton spatial manager for all tile and entity position data:

```python
class GridMap:
    # Tile storage
    _tiles: Dict[Tuple[int,int], TileData]

    # Entity tracking
    _entity_positions: Dict[UUID, Tuple[int,int]]
    _entities_by_position: Dict[Tuple, Set[UUID]]

    # Cell subscriptions (for reactive updates)
    _cell_subscribers: Dict[Tuple, Set[UUID]]
    _entity_subscriptions: Dict[UUID, Set[Tuple]]
```

**Key Methods:**
| Method | Purpose | Event Integration |
|--------|---------|-------------------|
| `get_map()` | Get singleton instance | Global access |
| `move_entity(uuid, new_pos)` | Move entity + fire events | Fires `SPATIAL_ENTITY_ENTERED/LEFT` |
| `subscribe_to_cells(entity_uuid, cells)` | Watch cells for changes | Entity FOV subscription |
| `compute_fov(origin, max_distance)` | Shadowcast algorithm | Called by Senses |
| `compute_paths(start, max_distance)` | Dijkstra algorithm | Called by Senses |
| `get_visible_entities(origin, max_distance)` | Entities in FOV | Quick entity lookup |
| `_fire_spatial_event(event_type, ...)` | Fire spatial change | Internal, triggers handlers |

**TileData Structure:**
```python
class TileData:
    walkable: bool = True
    visible: bool = True  # Can see through
    name: str = "Floor"
    sprite_name: Optional[str] = None
```

**What's Missing in TileData:**
- `difficult: bool` - For difficult terrain
- `light_level: str` - For darkness/dim/bright
- `movement_cost: int` - For custom terrain costs
- `elevation: int` - For 3D movement

### 1.4 Action Economy (`blocks/action_economy.py`)

Tracks resources available each turn:

```python
class ActionEconomy(BaseBlock):
    actions: ModifiableValue        # Default 1
    bonus_actions: ModifiableValue  # Default 1
    reactions: ModifiableValue      # Default 1
    movement: ModifiableValue       # Default 30
```

**Key Methods:**
| Method | Purpose | Turn Integration |
|--------|---------|------------------|
| `can_afford(cost_type, amount)` | Check if action is possible | Pre-validation |
| `consume(cost_type, amount, name)` | Deduct resource | Post-action |
| `reset_all_costs()` | Clear consumed costs | **CRITICAL: Call at turn start** |
| `get_cost_modifiers(cost_type)` | Get consumption history | Debug/UI |

**CostType Literal:**
```python
CostType = Literal["actions", "bonus_actions", "reactions", "movement"]
```

### 1.5 Action System (`core/base_actions.py`, `actions.py`)

Two patterns for actions:

**BaseAction (Direct Override):**
```python
class BaseAction(BaseObject):
    costs: List[Cost]

    def check_costs() -> bool          # Validate affordability
    def pre_validate() -> bool         # Quick validation without events
    def _create_declaration_event()    # Create initial event
    def _validate(declaration) -> Event  # Check prerequisites
    def _apply(execution) -> Event     # Execute action
    def _apply_costs(completion)       # Deduct costs
    def apply() -> Event               # Main entry point
```

**StructuredAction (Pipeline):**
```python
class StructuredAction(BaseAction):
    prerequisites: OrderedDict[str, EventProcessor]
    consequences: OrderedDict[str, EventProcessor]
    cost_applier: Optional[EventProcessor]
```

**Action Flow:**
```
apply()
├── check_costs() → Can afford?
├── _create_declaration_event() → DECLARATION phase
├── _validate() → Check prerequisites
│   └── Returns EXECUTION phase or CANCEL
├── _apply() → Execute action
│   └── EXECUTION → EFFECT → COMPLETION
└── _apply_costs() → Deduct from action economy
```

**Implemented Actions:**
| Action | Class | Cost | Notes |
|--------|-------|------|-------|
| **Attack** | `Attack` | 1 action | Full validation (range, LOS) |
| **Move** | `Move` | movement | Auto-path from senses |

**Validation Helpers:**
```python
validate_line_of_sight(event, source_uuid)  # Check target in senses.entities
Attack.validate_range(event, source_uuid)   # Check weapon range vs distance
Move.validate_path(event, source_uuid)      # Check path validity
```

### 1.6 Event System (`core/events.py`)

Central nervous system - all game state changes flow through events.

**Event Phases:**
```python
class EventPhase(str, Enum):
    DECLARATION = "Declaration"   # Intent announced
    EXECUTION = "Execution"       # Being processed
    EFFECT = "Effect"             # Effects applied
    COMPLETION = "Completion"     # Finished
    CANCEL = "Cancel"             # Aborted
```

**EventQueue (Static Class):**
```python
class EventQueue:
    # Storage indices
    _events_by_uuid: Dict[UUID, Event]
    _events_by_lineage: Dict[UUID, List[Event]]
    _events_by_type: Dict[EventType, List[Event]]
    _events_by_phase: Dict[EventPhase, List[Event]]
    _events_by_source: Dict[UUID, List[Event]]
    _events_by_target: Dict[UUID, List[Event]]
    _all_events: List[Event]

    # Handler registry
    _event_handlers: Dict[UUID, EventHandler]
    _event_handlers_by_trigger: Dict[Trigger, List[EventHandler]]
    _event_handlers_by_simple_trigger: Dict[Trigger, List[EventHandler]]

    # Passive monitoring
    _on_event_callbacks: List[Callable[[Event], None]]
```

**Key Methods:**
| Method | Purpose | Use Case |
|--------|---------|----------|
| `register(event)` | Store + notify handlers | Every event goes here |
| `add_event_handler(handler)` | Subscribe to events | Reactions, conditions |
| `remove_event_handler(handler)` | Unsubscribe | Cleanup |
| `add_on_event_callback(callback)` | Passive monitoring | UI, logging, websocket |
| `get_events_by_type(type)` | Query by type | History lookup |
| `get_event_history(uuid)` | Full lineage | Event chain analysis |

**EventHandler Structure:**
```python
class EventHandler(BaseObject):
    name: str
    source_entity_uuid: UUID              # Who owns this handler
    trigger_conditions: List[Trigger]     # When to fire
    event_processor: EventProcessor       # What to do
```

**Trigger Structure:**
```python
class Trigger(BaseModel):
    name: str
    event_type: EventType                 # Match event type
    event_phase: EventPhase               # Match phase
    event_source_entity_uuid: Optional[UUID]  # Filter by source
    event_target_entity_uuid: Optional[UUID]  # Filter by target
```

**EventProcessor Type:**
```python
EventProcessor = Callable[[Event, UUID], Optional[Event]]
# (event, source_entity_uuid) -> modified event or None
```

### 1.7 Reactions System (`reactions.py`)

Currently only opportunity attacks are implemented:

```python
def opportunity_attack_processor(event: MovementEvent, source_entity_uuid: UUID) -> Optional[MovementEvent]:
    """
    Triggers when:
    1. Movement event in EFFECT phase
    2. Source starts in threatened position
    3. Path exits threatened area
    4. Reaction can afford cost
    """

def create_opportunity_attack_handler(source_entity_uuid: UUID) -> EventHandler:
    # Creates handler with MOVEMENT + EFFECT trigger

def add_opportunity_attack_handler(entity: Entity):
    # Convenience method to add handler to entity
```

**Key Pattern:** Handler fires on MOVEMENT events at EFFECT phase, checks if movement leaves threatened squares, creates Attack with reaction cost.

### 1.8 Conditions System (`conditions.py`, `core/base_conditions.py`)

15 conditions implemented with the `_apply` pattern:

```python
class BaseCondition(BaseBlock):
    name: str
    description: str
    duration: Optional[int]                           # Turns remaining
    application_saving_throw: Optional[SavingThrowEvent]
    removal_saving_throw: Optional[SavingThrowEvent]
    parent_condition: Optional[UUID]                  # For sub-conditions

    def apply(declaration_event) -> Event             # Apply modifiers
    def remove() -> None                              # Clean up modifiers
    def progress() -> bool                            # Advance duration, return if removed
```

**Condition Effects via Modifiers:**
| Condition | Self Effects | Target Effects |
|-----------|-------------|----------------|
| Blinded | Disadvantage attacks | Attackers advantage |
| Charmed | Auto-miss vs charmer | Charmer social advantage |
| Frightened | Contextual disadvantage | - |
| Paralyzed | Auto-fail STR/DEX saves | Advantage, auto-crit ≤5ft |
| etc. | | |

---

## Part 2: What's Needed for Encounter Module

### 2.1 CombatManager / EncounterManager

The core orchestrator for turn-based combat.

**Required State:**
```python
class EncounterManager:
    combatants: List[UUID]           # Entities in combat
    initiative_order: List[UUID]     # Sorted by initiative
    current_turn_index: int          # Whose turn
    round_number: int                # Current round
    is_active: bool                  # Combat ongoing
```

**Required Methods:**
| Method | Purpose | Events Fired |
|--------|---------|--------------|
| `start_encounter(entities)` | Roll initiative, begin | `ENCOUNTER_START` |
| `end_encounter()` | Clean up, return to exploration | `ENCOUNTER_END` |
| `start_turn()` | Reset resources, fire hooks | `TURN_START` |
| `end_turn()` | Check conditions, advance | `TURN_END` |
| `next_turn()` | Move to next combatant | Calls end_turn + start_turn |
| `get_current_entity()` | Who's turn is it | - |
| `remove_combatant(uuid)` | Entity dies/flees | - |

**Integration Points:**
- `start_turn()` must call `entity.action_economy.reset_all_costs()`
- `end_turn()` must call `entity.advance_duration_condition()` for all active conditions
- Events must go through EventQueue for handler reactions

### 2.2 Initiative System

**Needed on Entity:**
```python
# In Entity or separate block
initiative: ModifiableValue  # Base = DEX mod, can have bonuses (Alert feat)
initiative_roll_result: Optional[int]  # Stored roll for current combat

def roll_initiative() -> int:
    """Roll d20 + initiative modifier, store result"""
```

**In EncounterManager:**
```python
def _roll_all_initiatives(self) -> List[Tuple[UUID, int]]:
    """Roll for all combatants, return sorted list"""

def _handle_initiative_tie(a: UUID, b: UUID) -> int:
    """Tie-breaker: higher DEX, then coin flip"""
```

### 2.3 Turn Events

New event types needed:

```python
class EventType(str, Enum):
    # ... existing ...
    ENCOUNTER_START = "EncounterStart"
    ENCOUNTER_END = "EncounterEnd"
    TURN_START = "TurnStart"
    TURN_END = "TurnEnd"
    ROUND_START = "RoundStart"
    ROUND_END = "RoundEnd"

class TurnEvent(Event):
    round_number: int
    entity_uuid: UUID
    turn_index: int
```

**Handler Registration for Turn Events:**
```python
# Conditions can register for turn events
def frightened_turn_start_check(event: TurnEvent, source_uuid: UUID) -> Optional[TurnEvent]:
    """Check if frightener still visible, update condition"""
```

### 2.4 Available Actions System

**Critical for both UI and AI** - determine what actions an entity can currently take.

**AvailableActions Structure:**
```python
@dataclass
class AvailableAction:
    action_class: Type[BaseAction]
    name: str
    cost_type: CostType
    cost: int
    can_afford: bool
    valid_targets: List[UUID]      # For targeted actions
    valid_positions: List[Tuple]   # For movement

class AvailableActionsQuery:
    entity: Entity

    def get_attack_targets(self) -> List[UUID]:
        """Entities in weapon range and LOS"""

    def get_movement_positions(self) -> List[Tuple]:
        """Positions reachable with remaining movement"""

    def get_all_available(self) -> List[AvailableAction]:
        """All actions entity can currently take"""
```

**Computation Logic:**
```python
def get_attack_targets(entity: Entity, weapon_slot: WeaponSlot) -> List[UUID]:
    weapon_range = entity.get_weapon_range(weapon_slot)
    targets = []

    for target_uuid, position in entity.senses.entities.items():
        if target_uuid == entity.uuid:
            continue
        distance = entity.senses.get_feet_distance(position)

        if weapon_range.type == RangeType.REACH:
            if distance <= 5:  # Melee reach
                targets.append(target_uuid)
        else:  # RangeType.RANGE
            if distance <= weapon_range.normal:
                targets.append(target_uuid)

    return targets
```

### 2.5 Perception/Stealth System

**Hidden State Tracking:**
```python
# On Entity or Senses
is_hidden: bool = False
hidden_from: Set[UUID] = set()  # Entities can't see this one
stealth_check_result: Optional[int] = None

def attempt_hide(target_positions: Optional[List[Tuple]] = None) -> bool:
    """
    1. Must have cover/concealment from targets
    2. Make Stealth check vs target Passive Perception
    3. If success, add to hidden_from
    """

def reveal() -> None:
    """No longer hidden"""
```

**Passive Perception:**
```python
def get_passive_perception(entity: Entity) -> int:
    return 10 + entity.skill_bonus(None, "perception").normalized_score
```

**Integration with Senses:**
```python
def update_senses(...):
    # Filter out entities we can't see due to stealth
    visible_entities = {
        uuid: pos for uuid, pos in raw_visible.items()
        if uuid not in self._hidden_entities_set
        or passive_perception >= hidden_stealth[uuid]
    }
```

### 2.6 Interactables System

**Interactable Object Base:**
```python
class Interactable(BaseBlock):
    position: Tuple[int, int]
    interaction_range: int = 5  # feet

    def get_available_interactions(self, entity: Entity) -> List[str]:
        """What can this entity do with this object?"""

    def interact(self, entity: Entity, interaction: str) -> Event:
        """Perform interaction"""
```

**Destructible Objects:**
```python
class DestructibleObject(Interactable):
    material: Material  # Determines AC
    size: Size          # Determines HP
    hp: ModifiableValue
    damage_threshold: int = 0
    immunities: List[DamageType] = [POISON, PSYCHIC]

    def take_damage(self, damage: int, damage_type: DamageType) -> int:
        """Apply damage respecting immunities and threshold"""
```

**Traps:**
```python
class Trap(Interactable):
    trigger_type: str  # "pressure_plate", "trip_wire", "proximity"
    perception_dc: int
    disable_dc: int
    save_type: AbilityName
    save_dc: int
    damage_dice: int
    damage_type: DamageType
    triggered: bool = False

    def check_trigger(self, entity: Entity) -> bool:
        """Should this entity trigger the trap?"""

    def activate(self, target: Entity) -> Event:
        """Fire the trap"""
```

**Pickable Items:**
```python
class PickableItem(Interactable):
    item_data: Any  # What you get when picked up

    def pickup(self, entity: Entity) -> Event:
        """Add to inventory, remove from world"""
```

---

## Part 3: Integration Architecture

### 3.1 Event Flow for Turn-Based Combat

```
ENCOUNTER_START
└── Roll all initiatives
    └── Sort combatants
        └── ROUND_START (round 1)
            ├── TURN_START (entity A)
            │   ├── Reset action_economy
            │   ├── Trigger turn-start condition effects
            │   └── (Player/AI makes decisions)
            │       ├── ATTACK event → target takes damage
            │       ├── MOVEMENT event → triggers opportunity attacks
            │       └── etc.
            │
            └── TURN_END (entity A)
                ├── Advance condition durations
                ├── Check removal saves
                └── TURN_START (entity B)
                    └── ...
                        └── TURN_END (last entity)
                            └── ROUND_END (round 1)
                                └── ROUND_START (round 2)
```

### 3.2 Senses + Available Actions Integration

```python
# When it's entity's turn:
1. entity.update_entity_senses()
2. Query available actions:
   - Attack targets = entity.senses.entities filtered by range
   - Movement positions = entity.senses.paths keys filtered by cost
   - Interactables = objects at positions in entity.senses.visible

3. Present to UI/AI:
   {
     "attack_targets": [uuid1, uuid2],
     "movement_positions": [(5,3), (5,4), (6,3)],
     "interactables": [{"uuid": trap_uuid, "actions": ["disarm", "trigger"]}],
     "other_actions": ["dash", "dodge", "disengage", "hide"]
   }
```

### 3.3 GridMap + Spatial Events Integration

**Current Flow:**
```
Entity.move()
    └── Entity.update_entity_position()
        └── get_map().move_entity(uuid, new_pos)
            ├── _fire_spatial_event(SPATIAL_ENTITY_LEFT, old_pos)
            └── _fire_spatial_event(SPATIAL_ENTITY_ENTERED, new_pos)
                └── EventQueue.register(SpatialChangeEvent)
                    └── Triggers handlers watching these cells
```

**Needed Enhancement:**
```python
# When entity enters a cell with a trap:
class TrapTriggerHandler(EventHandler):
    trigger = Trigger(
        event_type=EventType.SPATIAL_ENTITY_ENTERED,
        event_phase=EventPhase.EFFECT
    )

    def process(event: SpatialChangeEvent, source_uuid: UUID):
        trap = get_trap_at(event.position)
        if trap and trap.check_trigger(Entity.get(event.entity_uuid)):
            trap.activate(Entity.get(event.entity_uuid))
```

### 3.4 Condition + Turn Event Integration

**Conditions with Turn-Based Effects:**
```python
# Frightened: Check visibility at turn start
# Paralyzed: Check removal save at turn end
# Poison: Apply damage at turn start
# Regeneration: Heal at turn start

class ConditionTurnHandler:
    def __init__(self, condition: BaseCondition, entity: Entity):
        self.handler = EventHandler(
            name=f"{condition.name}_turn_handler",
            source_entity_uuid=entity.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=entity.uuid
                )
            ],
            event_processor=self.on_turn_start
        )

    def on_turn_start(self, event: TurnEvent, source_uuid: UUID):
        # Condition-specific logic
```

### 3.5 Action Economy Reset Flow

**CRITICAL**: Must happen at turn start:

```python
class EncounterManager:
    def start_turn(self):
        entity = self.get_current_entity()

        # 1. Reset all action resources
        entity.action_economy.reset_all_costs()

        # 2. Fire turn start event
        turn_event = TurnEvent(
            event_type=EventType.TURN_START,
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            round_number=self.round_number,
            turn_index=self.current_turn_index
        )
        # Event handlers will process conditions, etc.
```

### 3.6 Reaction Timing

**Current:** Opportunity attacks trigger on MOVEMENT EFFECT phase.

**Needed:** Generic reaction framework:

```python
class ReactionTiming(str, Enum):
    BEFORE_ATTACK_ROLL = "before_attack_roll"     # Shield spell
    AFTER_ATTACK_ROLL = "after_attack_roll"       # Cutting Words
    BEFORE_DAMAGE = "before_damage"               # Uncanny Dodge
    WHEN_HIT = "when_hit"                         # Hellish Rebuke
    ON_MOVEMENT = "on_movement"                   # Opportunity Attack
    ON_SPELL_CAST = "on_spell_cast"               # Counterspell

class Reaction(BaseAction):
    timing: ReactionTiming
    trigger_event_type: EventType
    trigger_condition: Callable[[Event], bool]  # Extra filter
```

---

## Part 4: Event System Deep Integration

### 4.1 Event Handler Lifecycle

```
1. Handler created and registered:
   handler = EventHandler(...)
   EventQueue.add_event_handler(handler)
   → Stored in _event_handlers[handler.uuid]
   → Indexed in _event_handlers_by_trigger[trigger]

2. Event occurs:
   EventQueue.register(event)
   → Stored in all indices
   → Find matching handlers via _matching_handlers()
   → Call each handler's event_processor(event, handler.source_entity_uuid)
   → Handler can modify event or return None (no change)

3. Handler removed:
   handler.remove()
   → Removed from _event_handlers
   → Removed from trigger indices
```

### 4.2 Simple vs Complex Triggers

```python
# Simple: Only type + phase (fast lookup)
simple_trigger = Trigger(
    event_type=EventType.ATTACK,
    event_phase=EventPhase.EXECUTION
)

# Complex: Also filters by source/target (slower, checked after simple)
complex_trigger = Trigger(
    event_type=EventType.ATTACK,
    event_phase=EventPhase.EXECUTION,
    event_target_entity_uuid=defender.uuid  # Only attacks on this target
)
```

### 4.3 Event Lineage for History

```python
# Events in same chain share lineage_uuid
attack_declaration = AttackEvent(...)
# lineage_uuid = new UUID

attack_execution = attack_declaration.phase_to(EventPhase.EXECUTION)
# attack_execution.uuid = new UUID
# attack_execution.lineage_uuid = attack_declaration.lineage_uuid

# Query full chain:
history = EventQueue.get_event_history(attack_execution.uuid)
# Returns: [attack_declaration, attack_execution, ...]
```

### 4.4 Passive Event Monitoring

```python
# For UI, logging, websocket broadcast
def on_any_event(event: Event):
    websocket.broadcast(event.model_dump_json())

EventQueue.add_on_event_callback(on_any_event)

# This callback is called for EVERY event registered
# Doesn't modify events, just observes
```

---

## Part 5: Implementation Roadmap

### Phase 1: Turn Structure (Foundation)
1. Add initiative ModifiableValue to Entity
2. Create EncounterManager with start/end/next_turn
3. Add TURN_START/TURN_END event types
4. Wire action_economy.reset_all_costs() to turn start
5. Wire condition duration advancement to turn end

### Phase 2: Available Actions Query
1. Create AvailableActionsQuery class
2. Implement get_attack_targets() using senses
3. Implement get_movement_positions() using senses.paths
4. Create unified get_all_available() for UI/AI

### Phase 3: Perception/Stealth
1. Add hidden state to Entity
2. Implement passive perception calculation
3. Create Hide action
4. Modify senses update to filter hidden entities
5. Wire reveal on attack/etc.

### Phase 4: Interactables
1. Create Interactable base class
2. Implement DestructibleObject
3. Implement Trap with spatial trigger
4. Implement PickableItem
5. Wire to available actions query

### Phase 5: Advanced Reactions
1. Create ReactionTiming enum
2. Generalize reaction handler pattern
3. Implement common reactions (Shield, Counterspell patterns)

---

## Part 6: Code Location Quick Reference

| System | Primary File | Key Class/Function |
|--------|-------------|-------------------|
| Entity composition | `entity.py` | `Entity`, `EntityConfig` |
| Senses/perception | `blocks/sensory.py` | `Senses` |
| Spatial/tiles | `core/gridmap.py` | `GridMap`, `get_map()` |
| FOV algorithm | `core/shadowcast.py` | `compute_fov()` |
| Pathfinding | `core/dijkstra.py` | `dijkstra()` |
| Events | `core/events.py` | `EventQueue`, `EventHandler`, `Trigger` |
| Spatial events | `core/events.py` | `SpatialChangeEvent` |
| Actions base | `core/base_actions.py` | `BaseAction`, `StructuredAction` |
| Attack/Move | `actions.py` | `Attack`, `Move` |
| Action economy | `blocks/action_economy.py` | `ActionEconomy` |
| Reactions | `reactions.py` | `opportunity_attack_processor` |
| Conditions | `conditions.py` | All 15 conditions |
| Condition base | `core/base_conditions.py` | `BaseCondition` |
| Modifiers | `core/modifiers.py` | All modifier types |
| ModifiableValue | `core/values.py` | `ModifiableValue`, 6 channels |
| Health/damage | `blocks/health.py` | `Health` |
| Equipment | `blocks/equipment.py` | `Equipment`, `Weapon`, `Armor` |
| Abilities | `blocks/abilities.py` | `AbilityScores` |
| Skills | `blocks/skills.py` | `SkillSet` |
| Saves | `blocks/saving_throws.py` | `SavingThrowSet` |
