# D&D 5e Game Engine Architecture Guide

For `codex/july-reconstruction`, start with the
[current branch design guide](agent_docs/CURRENT_BRANCH_DESIGN_GUIDE.md).
It records current ownership, the Pygame recovery sequence, superseded
historical ideas, and known limits. The examples below span earlier designs;
use the current guide and the applicable bounded plan when they disagree.

## 1. Core Architecture Overview

This D&D 5e game engine is built on a sophisticated event-driven architecture with component-based entities. The system models D&D mechanics through several interacting subsystems:

- **Registry System**: UUID-based global object registry for all game objects
- **Entity-Component Framework**: Entities composed of specialized component "blocks"
- **Value System**: Modifiable values with multiple modification sources
- **Event System**: Event-driven architecture for game state changes
- **Condition System**: Source-owned effects, modifiers, handlers, and explicit condition relationships
- **Action Framework**: Structured approach to character actions

The fundamental principle is that **all game state changes flow through events**, allowing for interception, modification, and reaction at every stage.

## 2. Registry System

All game objects are globally accessible through a UUID-based registry system.

### Key Concepts:

- Every game object has a unique UUID that serves as its global identifier
- Objects register themselves in class-level registries upon creation
- Any object can be retrieved from anywhere using its UUID
- This enables decoupled communication between components

### Implementation Pattern:

```python
class BaseObject(BaseModel):
    uuid: UUID = Field(default_factory=uuid4)
    _registry: ClassVar[Dict[UUID, 'BaseObject']] = {}
    
    def __init__(self, **data):
        super().__init__(**data)
        self.__class__._registry[self.uuid] = self
        
    @classmethod
    def get(cls, uuid: UUID) -> Optional['BaseObject']:
        return cls._registry.get(uuid)
```

This pattern enables any object to look up any other object without direct references, which is foundational for the event system.

## 3. Value System

The value system is the foundation for all game mechanics.

### 3.1 ModifiableValue

`ModifiableValue` is the core building block that represents any value that can be modified (ability scores, AC, saving throws, etc.).

Key features:
- Base value that can be modified through different channels
- Multiple modification sources with different priorities
- Support for special statuses (advantage, critical, auto-hit)
- Propagation of effects between entities

### 3.2 Modification Channels

Each value has four channels for modifications:

1. **self_static**: Direct modifiers applied to the value
2. **self_contextual**: Context-dependent modifiers based on situation
3. **to_target_static**: Outgoing modifiers applied to others
4. **to_target_contextual**: Outgoing situational modifiers

```
ModifiableValue
├── self_static         (always applies to self)
├── self_contextual     (applies to self based on context)
├── to_target_static    (always applies to targets)
└── to_target_contextual (applies to targets based on context)
```

### 3.3 Modifier Types

The system supports different types of modifiers:

- **NumericalModifier**: Changes a value by addition
- **AdvantageModifier**: Applies advantage or disadvantage
- **CriticalModifier**: Modifies critical hit chances
- **AutoHitModifier**: Forces automatic hits or misses
- **ResistanceModifier**: Changes damage resistances/vulnerabilities

### 3.4 Cross-Entity Propagation

Values can interact across entities using `set_from_target()` and `reset_from_target()`:

```python
# During an attack
target_ac.set_from_target(attacker_bonus)  # AC affected by attacker's abilities
attacker_bonus.set_from_target(target_ac)  # Attack roll affected by target's defenses
```

## 4. Entity-Component Framework

Entities are composed of specialized component "blocks" that provide different functionality.

### 4.1 BaseBlock

All blocks inherit from `BaseBlock`, which provides:
- Registry integration
- Value management
- Target propagation
- Context handling

### 4.2 Entity Structure

```
Entity
├── ability_scores    (STR, DEX, CON, INT, WIS, CHA)
├── skill_set         (Perception, Stealth, etc.)
├── saving_throws     (Saving throw capabilities)
├── health            (HP, damage handling)
├── equipment         (Weapons, armor, items)
├── action_economy    (Actions, bonus actions, reactions)
├── senses            (Position, vision, awareness)
└── active_conditions (Current effects on entity)
```

### 4.3 Component Interaction

Components interact through:
1. Direct method calls when immediate response is needed
2. Event system for reactions and interrupts
3. Value cross-propagation for mutual effects

### 4.4 Specialized Components

Each component specializes in one aspect of game mechanics:
- **AbilityScores**: Base attributes and modifiers
- **SkillSet**: Skill proficiencies and bonuses
- **Health**: Damage tracking and resistances
- **Equipment**: Weapons, armor, and item effects
- **ActionEconomy**: Action resource management

## 5. Event System

The event system is the nervous system of the game engine, enabling decoupled communication between components.

### 5.1 Events

Events are self-contained objects that represent something happening in the game:

```python
class Event(BaseObject):
    name: str
    event_type: EventType  # ATTACK, MOVEMENT, DAMAGE, etc.
    phase: EventPhase      # DECLARATION, EXECUTION, EFFECT, COMPLETION
    source_entity_uuid: UUID
    target_entity_uuid: Optional[UUID]
    parent_event: Optional[UUID]
    # Event-specific data...
```

### 5.2 Event Lifecycle

Events progress through phases:
1. **DECLARATION**: Initial intent (e.g., "I want to attack")
2. **EXECUTION**: Action execution (e.g., rolling dice)
3. **EFFECT**: Applying effects (e.g., dealing damage)
4. **COMPLETION**: Finalizing (e.g., updating state)

```
DECLARATION → EXECUTION → EFFECT → COMPLETION
```

Events transition using `phase_to()`, which creates a new event with updated phase and data:

```python
def phase_to(self, new_phase: EventPhase, **kwargs) -> 'Event':
    updated_data = self.model_dump()
    updated_data.update(kwargs)
    updated_data["phase"] = new_phase
    updated_data["modified"] = True
    return self.__class__(**updated_data)
```

### 5.3 Event Handlers

Event handlers respond to specific event patterns:

```python
class EventHandler(BaseObject):
    trigger_conditions: List[Trigger]
    handler_function: EventProcessor
    entity_uuid: UUID
```

### 5.4 Triggers

Triggers define when handlers activate:

```python
class Trigger:
    event_types: List[EventType]
    phases: List[EventPhase]
    source_entity_uuids: Optional[List[UUID]]
    target_entity_uuids: Optional[List[UUID]]
    # Other conditions...
```

### 5.5 Handler Registration

Use `entity.add_event_handler(handler)` for entity-owned handlers. It both
tracks the handler for cleanup and registers it with EventQueue; do not also
call `EventQueue.add_event_handler()` for the same handler.

Equipment uses an explicit transactional boundary. Matching DECLARATION or
EXECUTION handlers must declare `validation_only=True` before they may run in
`EventQueue.preflight()`, and those validators may not mutate state or emit
events. Once every transition is accepted, `publish_preflighted()` stores each
proposal exactly once and stateful equipment reactions run at EFFECT.

## 6. Condition System

Conditions are effects applied to entities (like Blinded, Charmed, Raging).

### 6.1 Direct Mechanical Ownership

Each concrete condition owns all of the mechanics stated by that rule. Its
`_apply()` result records the exact modifier, event-handler, sub-condition, and
spatial-handler UUIDs that BaseBlock must clean up later. Reusable capability
transforms live in `dnd/creature_transforms.py`; they operate on a structural
creature surface and deliberately do not import `Entity`.

`Paralyzed`, `Stunned`, `Petrified`, and `Unconscious` apply their action,
movement, save, perception, and attack transforms directly. They do not create
a synthetic `Incapacitated` child merely to share code.

### 6.2 Explicit Condition Relationships

Sub-conditions are reserved for rules that genuinely apply a distinct named
condition. For example, a spell-specific `HoldPersonEffect` wrapper may own a
`Paralyzed` sub-condition while the wrapper controls spell duration and
concentration. Cross-block effects use linked conditions plus reverse parent
links, so cleanup works both from parent to child and from child back to parent.

### 6.3 BaseBlock-Driven Cleanup

`BaseBlock.remove_condition()` removes same-block sub-conditions, removes
cross-block linked conditions, calls the condition's own modifier/handler
cleanup, and then applies the configured reverse-link removal policy. The block
pops its indexes before recursion, preventing parent/child cleanup loops.

### 6.4 Life State Is Not a Condition

`Health.life_state` is the sole creature-lifecycle truth and uses the neutral
`LifeState` enum. Entity is its only production writer. `DYING`, `STABLE`, and
`DEAD` are not mirrored as concrete conditions or repaired by a lifecycle
handler; Entity derives their capability transforms atomically and emits a
`LifeStateChangeEvent` completion fact after the causal damage, death, healing,
or revival event has been accepted.

## 7. Action Framework

Actions represent complex player/monster abilities.

### 7.1 Action Structure

```python
class Action(BaseObject):
    name: str
    description: str
    prerequisites: OrderedDict[str, EventProcessor]  # Checks before action
    consequences: OrderedDict[str, EventProcessor]   # Effects of action
    cost_type: CostType  # actions, bonus_actions, reactions, movement
    cost: int
```

### 7.2 Action Flow

1. **Declaration**: Create an event declaring intent
2. **Prerequisites**: Check if action can be performed
3. **Consequences**: Apply effects in order
4. **Revalidation**: Check prerequisites again after each consequence (optional)

```python
def apply(self, parent_event: Optional[Event] = None) -> Optional[Event]:
    # 1. Declare action
    event = self.create_declaration_event(parent_event)
    
    # 2. Check prerequisites
    if event.canceled:
        return event
    event = self.check_prerequisites(event)
    
    # 3. Apply consequences if prerequisites met
    if event.canceled:
        return event
    return self.apply_consequences(event)
```

### 7.3 Action Phases

Actions automatically handle event phases:

```python
def apply_consequences(self, event: Event) -> Optional[Event]:
    # Move to EXECUTION phase
    event = event.phase_to(EventPhase.EXECUTION)
    
    # Apply each consequence in sequence
    for consequence_name, consequence_func in self.consequences.items():
        event = consequence_func(event, event.source_entity_uuid)
        if event.canceled:
            return event
        
        # Optional revalidation of prerequisites
        if self.revalidate_prerequisites:
            event = self.check_prerequisites(event)
            if event.canceled:
                return event
    
    # Move to COMPLETION phase
    return event.phase_to(EventPhase.COMPLETION)
```

## 8. System Integration

Understanding how these systems work together is key to creating complex interactions.

### 8.1 The Complete Flow

A typical game action flows through the system like this:

```
Action
  └── Creates Declaration Event
      └── Triggers Event Handlers
          └── May Create/Modify Conditions
              └── Apply Modifiers to Values
                  └── Affect Dice Rolls/Outcomes
                      └── Determine Action Results
                          └── Apply Effects
                              └── Trigger More Events
```

### 8.2 Common Patterns

#### Pattern 1: Dynamic Condition Response

```
Parent Condition
├── Creates Event Handlers (on apply)
└── Handlers Create/Remove Subconditions (on events)
    └── Subconditions Apply/Remove Modifiers (on apply/remove)
```

Example: Adaptive Armor responding to damage types

#### Pattern 2: Stacking Bonuses

```
Parent Condition
├── Creates Event Handlers (on apply)
│   └── Handlers Track Progress/State
│       └── Create New Subconditions with Greater Effect
└── Subconditions Apply Bonuses Based on Level (on apply)
```

Example: Battle trance improving with successive hits

#### Pattern 3: Triggered Effects

```
Parent Condition
├── Applies Base Effect (on apply)
└── Creates Event Handlers (on apply)
    └── Handlers Trigger Special Effect Subconditions (on events)
        └── Effect Subconditions Apply Short-term Modifiers (on apply)
```

Example: Counterspelling a spell being cast

### 8.3 Implementation Guidelines

1. **Separation of Concerns**
   - Parent conditions handle lifecycle and event registration
   - Subconditions handle actual modification application
   - Event handlers coordinate subcondition creation/removal

2. **Clean Removal**
   - All effects must be removable
   - Register all event handlers and subconditions
   - Use UUIDs rather than direct references

3. **State Management**
   - Never modify condition state after application
   - Use subconditions to represent state changes
   - Use `partial` for handlers that need to maintain state

4. **Event Propagation**
   - Respect event phase progression
   - Create new events rather than modifying existing ones
   - Use event hierarchies (parent/child) for related effects

## 9. Advanced Techniques

### 9.1 Complex Condition Interactions

For conditions that interact with each other (like invisibility ending when attacking):

1. Create a parent condition with subcondition for the effect
2. Add event handlers that monitor for triggering events
3. Have handlers remove the parent condition directly

```python
class InvisibilitySpell(BaseCondition):
    def _apply(self, event):
        # Create invisibility effect subcondition
        invisible = InvisibleCondition(...)
        invisible.apply(event)
        sub_conditions_uuids.append(invisible.uuid)
        
        # Add event handler to end invisibility on attack
        end_handler = EventHandler(
            trigger_conditions=[
                Trigger(event_types=[EventType.ATTACK], 
                        phases=[EventPhase.DECLARATION],
                        source_entity_uuids=[self.target_entity_uuid])
            ],
            handler_function=self.end_invisibility
        )
        # ... register handler
```

### 9.2 Conditional Modifiers

For modifiers that only apply in certain situations:

1. Use contextual modifier channels
2. Define functions that determine when modifier applies
3. Pass these functions to the modifier registration

```python
# Create a conditional modifier function
def only_against_dragons(source_uuid, target_uuid, context):
    target = Entity.get(target_uuid)
    if "dragon" in target.type.lower():
        return NumericalModifier(name="Dragon Slayer", value=3)
    return None

# Register with contextual channel
weapon.damage_bonus.self_contextual.add_value_modifier(
    ContextualNumericalModifier(callable=only_against_dragons)
)
```

### 9.3 Temporary Effects

For effects that should last for one attack or action:

1. Create a subcondition with specific duration
2. Use an event handler to clean up after the event completes
3. Possibly use `DurationType.ON_CONDITION` for automatic cleanup

```python
# Create temporary condition
temp_effect = TemporaryBoostCondition(
    duration=Duration(
        duration=1,
        duration_type=DurationType.ON_CONDITION
    )
)
temp_effect.apply(event)

# Add cleanup handler
cleanup_handler = EventHandler(
    trigger_conditions=[
        Trigger(
            event_types=[EventType.ATTACK],
            phases=[EventPhase.COMPLETION],
            specific_event_uuid=event.uuid  # Only this specific event
        )
    ],
    handler_function=lambda e, uuid: entity.remove_condition(temp_effect.name)
)
```

## 10. Summary

The power of this architecture comes from the elegant way these systems interact:

1. **Registry System** provides global object access
2. **Value System** enables complex modification paths
3. **Entity-Component Framework** organizes functionality
4. **Event System** enables reactions and interactions
5. **Condition System** allows complex, layered effects
6. **Action Framework** structures player/monster abilities

Remember these key principles:

1. All game state changes flow through events
2. Conditions manage effects through subconditions
3. Event handlers orchestrate condition changes
4. Modifiers affect values, not conditions directly
5. Clean registration ensures proper cleanup

By mastering these patterns, you can create arbitrarily complex game mechanics that accurately model D&D's rich interactions.
