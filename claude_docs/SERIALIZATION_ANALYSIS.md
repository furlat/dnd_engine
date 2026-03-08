# Serialization Pipeline Analysis

## The Problem Statement

The engine's serialization pipeline **strips callable fields** (`exclude=True`), meaning the frontend receives an incomplete picture of the backend state. Contextual modifiers — which make up roughly half of the modifier system — are particularly affected: the client gets the aggregate result but loses the per-modifier breakdown explaining *why* a value is what it is.

---

## Architecture: The Full Serialization Chain

### Three Serialization Paths

```
                            Backend (Python)
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   1. API Models            2. Event Stream          3. Raw model_dump
   (server/api_models.py)   (EventMonitor)          (entity_snapshot.json)
        │                        │                        │
   Hand-crafted DTOs        event.model_dump()       Entity.model_dump()
   APIEntitySummary          mode='json'              mode='json'
   APIEntityFull                 │                        │
   APIGrid, etc.                 │                        │
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 │
                            Frontend (JSON)
```

**Path 1 — API Models** (`server/api_models.py`): Hand-crafted DTOs that extract specific values from entities. These call `.normalized_score`, `.get_hp()`, etc. at creation time. The frontend gets clean ints/strings but zero modifier detail.

**Path 2 — Event Stream** (`event_monitor._on_event`): Every event gets `event.model_dump(mode='json')` and is broadcast via WebSocket. Events themselves serialize fine (they mostly contain UUIDs, enums, roll results). But events reference entities/values by UUID, not inline.

**Path 3 — Raw model_dump**: Used by `entity_snapshot.json` and `_get_floor_object_state()`. Triggers Pydantic's full serialization tree including computed fields.

---

## What Gets Serialized vs What Gets Lost

### Layer 1: ModifiableValue (6-Channel System)

```
ModifiableValue
├── self_static: StaticValue          ✅ FULLY serializable
├── to_target_static: StaticValue     ✅ FULLY serializable
├── self_contextual: ContextualValue  ⚠️  PARTIALLY serializable
├── to_target_contextual: ContextualValue ⚠️  PARTIALLY serializable
├── from_target_contextual: Optional  ⚠️  Usually None (populated only during cross-entity ops)
├── from_target_static: Optional      ✅ Usually None (populated only during cross-entity ops)
│
├── computed: normalized_score        ✅ Serialized (calls callables at dump time)
├── computed: advantage               ✅ Serialized (calls callables at dump time)
├── computed: critical                ✅ Serialized (calls callables at dump time)
├── computed: auto_hit                ✅ Serialized (calls callables at dump time)
└── computed: resistance              ✅ Serialized (calls callables at dump time)
```

**Key insight**: The **aggregate computed fields ARE correct** at serialization time because Pydantic evaluates `@computed_field` properties during `model_dump()`, which triggers the callable execution. The client gets the right `normalized_score` and `advantage` status.

**What's lost**: The per-modifier breakdown within contextual channels.

### Layer 2: Static Modifiers (FULLY serializable)

```python
# StaticValue channels — everything serializes
NumericalModifier:  name, uuid, value, normalized_value    ✅
AdvantageModifier:  name, uuid, value, numerical_value     ✅
CriticalModifier:   name, uuid, value                      ✅
AutoHitModifier:    name, uuid, value                      ✅
ResistanceModifier: name, uuid, value, damage_type         ✅

# ONLY exclusion:
NumericalModifier.score_normalizer: Callable  ❌ exclude=True
# But normalized_value computed_field captures the result  ✅
```

### Layer 3: Contextual Modifiers (THE MAIN PROBLEM)

```python
# ContextualValue channels — callables stripped
ContextualNumericalModifier:
    name, uuid                          ✅ Serialized
    callable_arguments (tuple)          ✅ Serialized (source_uuid, target_uuid, context)
    callable: ContextAwareNumerical     ❌ exclude=True — THE FUNCTION IS GONE

ContextualAdvantageModifier:
    name, uuid                          ✅ Serialized
    callable_arguments                  ✅ Serialized
    callable: ContextAwareAdvantage     ❌ exclude=True — THE FUNCTION IS GONE

# Same pattern for Critical, AutoHit, Size, DamageType, Resistance
```

**What the frontend sees for a contextual modifier**:
```json
{
    "name": "Frightened: disadvantage when source visible",
    "uuid": "abc-123",
    "callable_arguments": ["entity-uuid", "source-uuid", null],
    "source_entity_uuid": "...",
    "target_entity_uuid": "..."
}
```

**What's missing**: The actual function that determines the result. The `callable_arguments` are present but useless without the callable. There's no `value` or `current_result` field to show the evaluated state.

### Layer 4: EventHandler / SpatialHandler (NOT serializable at all)

```python
class BaseHandler(BaseObject):
    event_processor: EventProcessor    # ❌ NOT marked exclude=True
    # EventProcessor = Callable[[Event, UUID], Optional[Event]]
```

**Problem**: `event_processor` is a callable that is NOT excluded. This means:
- `handler.model_dump(mode='json')` will **fail** (can't JSON-serialize a function)
- Handlers stored on entities (`entity.event_handlers`) make full entity serialization fragile
- The server works around this by never calling `entity.model_dump()` directly — it uses API models that cherry-pick specific fields

### Layer 5: Conditions (Mixed)

```python
class BaseCondition(BaseObject):
    name, description, duration         ✅ Mostly serializable
    condition_category                  ✅
    hazard_filter, condition_stealth_dc ✅

    # BUT: duration can be a callable
    duration: Optional[Union[int, ContextAwareCondition]]  # ⚠️ No exclude!
    # If duration is a ContextAwareCondition (callable), serialization will fail
```

### Layer 6: BaseBlock Perceivability Flags

```python
# These are INTENTIONALLY excluded — security concern
stealth_dc: Optional[int]     ❌ exclude=True  (don't leak DC to clients)
is_invisible: bool             ❌ exclude=True  (don't leak invisibility state)
```

### Layer 7: Senses (NEVER serialized directly)

```python
# Senses block has:
visible: Dict[Tuple[int,int], bool]     # FOV data
paths: Dict[Tuple[int,int], List]       # Dijkstra paths
entities: Dict[UUID, Tuple[int,int]]    # Visible entities
objects: Dict[UUID, Tuple[int,int]]     # Visible objects
```

These are handled via dedicated `/visibility` endpoint, never through raw serialization.

---

## The Normalized Score Problem (Aggregation)

### How normalized_score is Computed

```
ModifiableValue.normalized_score
    = sum of channel.normalized_score for each non-None channel

Where each channel's normalized_score:
    StaticValue:     sum(modifier.normalized_value for modifier in value_modifiers)
    ContextualValue: sum(modifier.callable(args).value for modifier in value_modifiers)
                     ↑ CALLS THE CALLABLE AT EVAL TIME
```

**At serialization time**: Pydantic calls the `@computed_field` property, which triggers callable execution. The JSON output contains the **correct current value** of `normalized_score`.

**Problem**: This is a **snapshot**. The frontend can't re-evaluate if game state changes. And the frontend has no way to ask "what would this be if the target were different?" because the contextual callables are gone.

### What get_breakdown() Does vs Could Do

Currently (`values.py:2227-2248`):
```python
# ONLY extracts from static components
static_components = [
    (self.self_static, "self"),
    (self.from_target_static, "from_target"),
]
# Comment: "contextual modifiers can't be reliably re-evaluated later
# (context may have changed) and their effects are already reflected
# in normalized_score"
```

This means `get_breakdown()` gives an **incomplete breakdown**. If Frightened adds -2 via a contextual modifier, that -2 IS in `normalized_score` but NOT in `get_breakdown()`.

---

## Information Loss Summary

### What the Frontend Gets Today

| Data | Source | Quality |
|------|--------|---------|
| HP, Max HP | APIEntitySummary | ✅ Complete |
| AC | `.ac_bonus().normalized_score` | ✅ Correct value, no breakdown |
| Conditions list | `entity.active_conditions.keys()` | ✅ Names only |
| Condition details | `{name, category}` | ⚠️ Missing: duration, source, effects |
| Action economy | `actions/bonus/reactions/movement .normalized_score` | ✅ Correct values |
| Ability scores | `ability_score.normalized_score` | ✅ Correct values |
| Position | `entity.position` | ✅ Complete |
| Attack bonus | NOT sent | ❌ Missing entirely |
| Damage bonus | NOT sent | ❌ Missing entirely |
| Spell DC | NOT sent | ❌ Missing entirely |
| Advantage/disadvantage state | NOT sent | ❌ Missing entirely |
| Modifier breakdown | NOT sent (get_breakdown exists but unused in API) | ❌ Missing entirely |
| Event handlers (what reactions entity has) | NOT sent | ❌ Missing entirely |

### What's Lost at Each Level

```
Level 1 — API Models (server/api_models.py):
    ❌ No modifier breakdowns
    ❌ No advantage/disadvantage state per value
    ❌ No attack/damage/spell bonuses
    ❌ No handler list (Shield reaction, OA, etc.)
    ❌ No condition effects detail
    ❌ No equipped items detail (just weapon_name)

Level 2 — Contextual Callable Exclusion:
    ❌ Contextual modifier functions stripped (exclude=True)
    ❌ No way to show "Frightened: disadvantage when source visible"
    ❌ No way to show "Prone: advantage if ≤5ft, disadvantage if >5ft"
    ✅ But aggregate computed results ARE included

Level 3 — Handler/Processor Exclusion:
    ❌ EventProcessor callables not serializable
    ❌ Can't serialize handler descriptions
    ❌ Can't tell client "this entity has Shield reaction available"

Level 4 — Internal Registries:
    ❌ BaseObject._registry (ClassVar, never serialized — correct)
    ❌ Entity._entity_registry (ClassVar — correct)
    ❌ EventQueue state (handlers, spatial handlers — never serialized)
```

---

## The Root Causes

### 1. Contextual Modifiers Store Logic, Not Data

The core issue is that `ContextualModifier.callable` is a Python function. It encodes **game rules** like "Frightened gives disadvantage when the frightener is visible." This logic can't be JSON-serialized.

**Current approach**: Strip the callable, keep `callable_arguments`, include computed results.

**What's missing**: A way to represent the **evaluated result** of each contextual modifier as serializable data.

### 2. No "Snapshot" Field on ContextualModifier

When a contextual modifier is evaluated, its result (e.g., `AdvantageModifier(DISADVANTAGE)`) is ephemeral — computed inline and discarded. There's no field to cache the last-evaluated result for serialization.

### 3. get_breakdown() Deliberately Skips Contextual

The `get_breakdown()` and `get_advantage_breakdown()` methods explicitly skip contextual channels (lines 2227-2229, 2262-2270). The comment says the effects "are already reflected in normalized_score" — but the per-modifier attribution is lost.

### 4. API Models Are Too Thin

`APIEntitySummary` and `APIEntityFull` extract minimal data. They don't call `get_breakdown()`, don't serialize modifier state, don't include advantage/disadvantage, don't list handlers/reactions.

---

## Improvement Opportunities

### Approach A: Snapshot Contextual Results at Evaluation Time

Add a `last_result` field to `ContextualModifier` that caches the most recent callable evaluation:

```python
class ContextualModifier(BaseObject):
    callable: ... = Field(exclude=True)
    callable_arguments: ...
    last_result: Optional[Dict[str, Any]] = Field(default=None)
    # Populated by execute_callable() with {"type": "advantage", "value": "DISADVANTAGE"}
```

**Pros**: Zero overhead at serialization, captures the result when it's naturally computed.
**Cons**: Stale if game state changes between evaluation and serialization. But for D&D this rarely matters — contextual modifiers are re-evaluated at action time.

### Approach B: Evaluate-and-Embed at Serialization Time

Override `model_dump()` on ContextualValue to evaluate callables and embed results:

```python
# During model_dump, call each contextual modifier's callable and include the result
# alongside the modifier metadata
```

**Pros**: Always fresh at serialization time.
**Cons**: Requires callable_arguments to be set (they aren't always — contextual channels need `set_from_target()` first).

### Approach C: Rich Breakdown in API Models

Add a `get_full_breakdown()` method that includes contextual modifier results:

```python
def get_full_breakdown(self) -> List[Dict[str, Any]]:
    result = []
    # Static modifiers (same as today)
    for modifier in self.self_static.value_modifiers.values():
        result.append({"name": ..., "value": ..., "source": "self", "type": "static"})

    # Contextual modifiers — evaluate now and include result
    for modifier in self.self_contextual.value_modifiers.values():
        try:
            evaluated = modifier.callable(
                self.source_entity_uuid, self.target_entity_uuid, self.context
            )
            if evaluated:
                result.append({
                    "name": modifier.name,
                    "value": evaluated.value if hasattr(evaluated, 'value') else evaluated.normalized_value,
                    "source": "self",
                    "type": "contextual",
                    "active": True
                })
            else:
                result.append({
                    "name": modifier.name,
                    "source": "self",
                    "type": "contextual",
                    "active": False  # Callable returned None — condition not met
                })
        except:
            result.append({"name": modifier.name, "type": "contextual", "active": "unknown"})
    return result
```

**Pros**: Full picture including "this modifier exists but isn't active right now."
**Cons**: Must handle exceptions from callables, needs target context.

### Approach D: Richer API Models

Extend `APIEntityFull` with modifier breakdowns and handler info:

```python
class APIEntityFull(APIEntitySummary):
    # ... existing fields ...

    # New fields
    attack_bonus: Optional[int] = None
    attack_breakdown: List[dict] = []
    damage_bonus: Optional[int] = None
    ac_breakdown: List[dict] = []
    advantage_status: Optional[str] = None
    advantage_breakdown: List[dict] = []

    # Reactions/handlers
    available_reactions: List[str] = []  # ["Shield", "Opportunity Attack", ...]

    # Condition details
    conditions_full: List[dict] = []  # [{name, description, duration, source_name, effects}]

    # Spell info
    spell_dc: Optional[int] = None
    spell_attack_bonus: Optional[int] = None
    spell_slots: Optional[dict] = None  # {level: remaining}
```

---

## Weak Points Summary

| Weak Point | Severity | Impact |
|------------|----------|--------|
| Contextual modifier callables excluded | HIGH | Frontend can't show why advantage/disadvantage applies |
| get_breakdown() skips contextual channels | HIGH | Incomplete modifier attribution |
| EventHandler.event_processor not excluded | MEDIUM | Raw entity.model_dump() would crash |
| API models too thin | HIGH | Frontend missing attack/damage/spell/reaction data |
| Condition duration as callable | LOW | Edge case, rarely used |
| No handler/reaction listing | MEDIUM | Frontend can't show available reactions |
| stealth_dc/is_invisible excluded | LOW | Intentional security — but per-observer filtering needed |
| from_target channels usually None | LOW | Only populated during cross-entity ops, not in resting state |

---

## Files Referenced

- `dnd/core/values.py` — ModifiableValue, StaticValue, ContextualValue, get_breakdown()
- `dnd/core/modifiers.py` — All modifier types, `exclude=True` on callables
- `dnd/core/base_object.py` — BaseObject, `arbitrary_types_allowed=True`
- `dnd/core/base_block.py` — BaseBlock, condition storage, perceivability flags
- `dnd/core/base_conditions.py` — BaseCondition, callable duration
- `dnd/core/events.py` — Event, EventHandler, SpatialHandler, EventProcessor
- `server/api_models.py` — APIEntitySummary, APIEntityFull, APIGrid
- `server/event_server.py` — EventMonitor, state endpoints, floor object serialization
