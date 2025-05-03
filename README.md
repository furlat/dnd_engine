# D&D 5e Game Engine Architecture Guide

## 1. Core Architecture Overview

This D&D 5e game engine is built on a sophisticated event-driven architecture with component-based entities. The system models D&D mechanics through several interacting subsystems:

- **Registry System**: UUID-based global object registry for all game objects
- **Entity-Component Framework**: Entities composed of specialized component "blocks"
- **Value System**: Modifiable values with multiple modification sources
- **Event System**: Event-driven architecture for game state changes
- **Condition System**: Effects that modify entities through subconditions
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

Handlers are registered with entities:

```python
def add_event_handler(self, event_handler: EventHandler) -> None:
    self.event_handlers[event_handler.uuid] = event_handler
    for trigger in event_handler.trigger_conditions:
        self.event_handlers_by_trigger[trigger].append(event_handler)
```

## 6. Condition System

Conditions are effects applied to entities (like Blinded, Charmed, Raging).

### 6.1 Condition Hierarchy

The key insight is that conditions use a **parent-child hierarchy**:

```
BaseCondition (parent)
└── SubConditions (children)
```

The parent condition:
- Manages the overall effect lifecycle
- Registers event handlers
- Tracks subconditions

The subconditions:
- Apply actual modifiers to the entity
- Are removed when the parent is removed
- Can be added/removed dynamically

### 6.2 Condition Registration

Conditions must be registered with their parent:

```python
def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
    # Returns:
    # - List of (block_uuid, modifier_uuid) tuples
    # - List of event handler UUIDs
    # - List of subcondition UUIDs
    # - Modified event
```

### 6.3 Condition-Event Interaction Pattern

This is the critical pattern for dynamic condition behavior:

1. **Parent condition** sets up event handlers during application
2. **Event handlers** create events that trigger application/removal of subconditions
3. **Subconditions** apply the actual modifiers to the entity

Example flow:

```
1. AdaptiveArmorCondition applies
   └── Sets up "damage taken" event handler
   └── Creates AdaptiveArmorBaseCondition (basic AC bonus)

2. Entity takes fire damage
   └── Event handler triggers
   └── Creates a "apply resistance" event

3. "Apply resistance" event
   └── Removes old resistance subcondition (if any)
   └── Creates FireResistanceCondition subcondition
```

### 6.4. Condition Removal Cascade

When a parent condition is removed:
1. It removes all registered subconditions
2. It removes all registered event handlers
3. Each subcondition removes its modifiers

This ensures clean cleanup and prevents dangling effects.

### 6.5 Condition State Management

**CRITICAL POINT**: Conditions themselves should be immutable after application. Any state changes must happen through the creation/removal of subconditions.

❌ WRONG:
```python
def event_handler(event, entity_uuid):
    condition.some_value += 1  # WRONG! Directly modifying condition state
```

✅ CORRECT:
```python
def event_handler(event, entity_uuid):
    # Create an event that will create/remove subconditions
    new_event = Event(...)
    subcondition = SomeSubcondition(...)
    subcondition.apply(new_event)
```

### 6.6 Event Handler State Pattern

When event handlers need to maintain state between calls, use the `partial` function:

```python
from functools import partial

# During condition application
image_iterator = cycle(subcondition_uuids)
handler = EventHandler(
    handler_function=partial(self.handle_missed_attack, image_iterator)
)
```

This ensures the state is tied to the specific event handler instance.

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