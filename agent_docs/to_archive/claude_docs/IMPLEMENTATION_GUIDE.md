# Implementation Guide

How to implement features using the D&D Engine's patterns. Read this before writing new conditions, actions, or event handlers.

---

## Section 1: Working With This Codebase

**The user (Tommaso) is the architect.** Claude assists, not drives.

### Required Behavior

1. **One change, one checkpoint.** Make a single change, report what you did, ask if correct before the next change.
2. **Ask before assuming.** If unsure how something should work, ASK. Don't guess.
3. **Study Python first.** Trace through backend code before touching other layers.
4. **Report failures immediately.** Say so and ask for guidance. Don't silently try alternatives.
5. **No "know-it-all" behavior.** Uncertainty means stopping and asking.

### What Killed Previous Sessions

- Making 5+ speculative fixes without validation
- Not studying backend code before changes
- Continuing to flail instead of asking for help
- Not using the PvP test loop to validate changes immediately

### The Right Pattern

```
Claude: I made change X. Does this look right?
User: No, try Y instead.
Claude: Done. Here's the result. Should I continue?
User: Yes, now do Z.
```

---

## Section 2: Core Concepts Quick Reference

### Entity Composition

```
Entity
├── ability_scores: AbilityScores     # STR, DEX, CON, INT, WIS, CHA
├── skill_set: SkillSet               # 18 D&D skills
├── saving_throws: SavingThrowSet     # 6 saves
├── health: Health                    # HP, temp HP, damage
├── equipment: Equipment              # Weapons, armor, AC
├── inventory: Inventory              # Item storage (slots, weight, stacking, use actions)
├── action_economy: ActionEconomy     # actions, bonus_actions, reactions, movement
├── senses: Senses                    # position, FOV, paths, visible entities, visible objects
├── active_conditions: Dict[str, BaseCondition]
└── action_templates: Dict[str, BaseAction]
```

### ModifiableValue 6-Channel System

Every modifiable stat uses 6 channels for modifiers:

| Channel | Set By | Purpose |
|---------|--------|---------|
| `self_static` | Conditions | Always applies to self |
| `self_contextual` | Conditions | Conditional, evaluated at runtime |
| `to_target_static` | Conditions | Always applies to entities targeting this entity |
| `to_target_contextual` | Conditions | Conditional for targeting entities |
| `from_target_static` | `set_from_target()` | Copies target's `to_target_static` |
| `from_target_contextual` | `set_from_target()` | Copies target's `to_target_contextual` |

**Cross-entity propagation**: When attacking, call `attack_bonus.set_from_target(ac)` to get target's defensive modifiers.

### Event Lifecycle

```
DECLARATION → EXECUTION → EFFECT → COMPLETION (or CANCEL)
```

- `DECLARATION`: Intent announced, can be intercepted
- `EXECUTION`: Being processed (handlers can modify)
- `EFFECT`: Effects applied (hit detection, damage)
- `COMPLETION`: Finished. **No handlers fire** - reserved for combat log generation via callback.

Each `phase_to()` creates a new event UUID but preserves the same `lineage_uuid`. Events track parent-child relationships through `parent_event` (causal hierarchy between different events) and `lineage_uuid` (same event across phases). See Section 3 for details.

### Condition Lifecycle

```
1. Create: condition = MyCondition(source_entity_uuid=..., target_entity_uuid=...)
2. Apply:  target.add_condition(condition) → calls condition.apply()
3. Effect: Modifiers added to appropriate channels
4. Remove: target.remove_condition("MyCondition") → BaseBlock drives recursive cleanup tree
```

BaseBlock is responsible for all cross-object cleanup. The condition only cleans up its own modifiers/handlers via `cleanup_own_state()`.

---

## Section 3: The Event Parent-Child System

The event system tracks two distinct UUID relationships for linking events together. Understanding both is critical for combat log generation and event tree traversal.

### Two UUID Fields

| Field | Type | Purpose | When Changes |
|-------|------|---------|--------------|
| `lineage_uuid` | UUID | Same event across phases (DECLARATION → COMPLETION) | Never - preserved across all `phase_to()` calls |
| `parent_event` | Optional[UUID] | Causal hierarchy between DIFFERENT events | Set at creation - links child to parent |

**`lineage_uuid`**: When you call `event.phase_to(EventPhase.EFFECT)`, the new event gets a new `uuid` but the SAME `lineage_uuid`. This lets you track a single logical event through its lifecycle.

**`parent_event`**: When an Attack event causes a TakeDamage event, TakeDamage sets `parent_event=attack_event.uuid`. This creates causal trees linking different events.

### Child Event Tracking

Events track children in two lists:

| Field | Purpose | Lifecycle |
|-------|---------|-----------|
| `children_events` | Children of the CURRENT phase | Reset on each `phase_to()` - merged into `lineage_children_events` |
| `lineage_children_events` | ALL children accumulated across ALL phases | Grows through entire event lifetime |

In `phase_to()`:
```python
# phase_to() merges current children into lineage before clearing:
phase_updates['lineage_children_events'] = self.lineage_children_events + self.children_events
phase_updates['children_events'] = []
```

### Auto-Linking in EventQueue._store_event()

When an event is registered with `parent_event` set, EventQueue automatically adds the child to the parent's `children_events`:

```python
# In EventQueue._store_event():
if event.parent_event:
    parent_event = cls.get_event_by_uuid(parent_uuid)
    if parent_event and parent_event.uuid not in event.children_events:
        parent_event.add_child_event(event)
```

### Combat Log Collection

At COMPLETION phase, `phase_to()` calls `_collect_child_combat_logs()` which iterates `lineage_children_events` and de-duplicates by `lineage_uuid`:

```python
def _collect_child_combat_logs(self) -> List[CombatLogEntry]:
    child_logs = []
    seen_lineages: Set[UUID] = set()
    for child_uuid in self.lineage_children_events:
        child = EventQueue.get_event_by_uuid(child_uuid)
        if child and child.combat_log and child.lineage_uuid not in seen_lineages:
            child_logs.append(child.combat_log)
            seen_lineages.add(child.lineage_uuid)
    return child_logs
```

### Callback Mechanism

Only **top-level events** (`parent_event=None`) fire the Encounter combat log callback at COMPLETION:

```python
# In phase_to(), at COMPLETION:
if self.parent_event is None and EventQueue._combat_log_callback:
    EventQueue._combat_log_callback(final_event)
```

### Pattern: Always Pass parent_event

**Critical**: Always pass `parent_event` when creating child events, or the combat log hierarchy breaks.

```python
# In action _apply():
target.receive_damage(..., parent_event=effect_event.uuid)

# In spell saves:
SavingThrowEvent(..., parent_event=execution_event.uuid)

# In zone handlers:
entity.receive_damage(..., parent_event=event.uuid)

# In condition application:
entity.add_condition(condition, parent_event=effect_event)
```

### Event Trees for Common Scenarios

**1. Attack → Hit → TakeDamage**
```
AttackEvent (lineage_uuid=A)
├── DECLARATION (uuid=1, lineage=A)
├── EXECUTION (uuid=2, lineage=A) — rolls d20
├── EFFECT (uuid=3, lineage=A) — determines hit
│   └── TakeDamageEvent (uuid=4, lineage=B, parent_event=3)
│       ├── EFFECT (uuid=5, lineage=B) — applies damage
│       └── COMPLETION (uuid=6, lineage=B) — generates damage log
└── COMPLETION (uuid=7, lineage=A) — generates attack log, collects TakeDamage as sub_entry
```

**2. Fireball (POSITION_AOE) → Per-Target Children**
```
SpellEvent (lineage=A, parent_event=None)  ← TOP LEVEL, fires callback
├── EXECUTION (lineage=A)
│   ├── Child SpellEvent target_1 (lineage=B, parent_event=execution.uuid)
│   │   ├── EFFECT → SavingThrow + TakeDamage (children of B)
│   │   └── COMPLETION → generates per-target log
│   ├── Child SpellEvent target_2 (lineage=C, parent_event=execution.uuid)
│   │   └── ...
│   └── Child SpellEvent target_3 (lineage=D, parent_event=execution.uuid)
│       └── ...
└── COMPLETION (lineage=A) → generates summary, collects B/C/D as sub_entries
```

Each per-target child gets a **NEW lineage_uuid** (isolated save/damage tracking). The parent COMPLETION collects them via `_collect_child_combat_logs()`.

**3. Movement → StepMovement → Spatial Zone → TakeDamage**
```
MovementEvent (lineage=A)
├── EFFECT (lineage=A)
│   ├── StepMovementEvent step_1 (lineage=B, parent_event=A.effect.uuid)
│   │   └── EFFECT → SpatialHandler fires → TakeDamageEvent (lineage=C, parent_event=B)
│   ├── StepMovementEvent step_2 (lineage=D, parent_event=A.effect.uuid)
│   │   └── ...
│   └── ...
└── COMPLETION (lineage=A) → collects step logs as sub_entries
```

---

## Section 4: How to Implement a Condition

### 4a. Basic Structure

```python
from dnd.core.base_conditions import BaseCondition, DurationType
from dnd.core.events import Event, EventPhase
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus
from dnd.entity import Entity
from typing import List, Tuple, Optional
from uuid import UUID

class MyCondition(BaseCondition):
    name: str = "MyCondition"
    description: str = "Description here"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # effect event (NOT completion - completion handled by caller)
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        # Add modifiers to appropriate channels
        mod_uuid = target.equipment.attack_bonus.self_static.add_advantage_modifier(
            AdvantageModifier(
                name="MyCondition",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=self.target_entity_uuid,
                target_entity_uuid=self.source_entity_uuid
            )
        )
        outs.append((target.equipment.attack_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied MyCondition to {target.name}"
        )
        return outs, [], [], [], effect_event
```

**The 5-tuple return**: `_apply()` always returns exactly 5 elements. The caller (`BaseCondition.apply()`) uses these to register cleanup data:
- **modifiers** `List[Tuple[UUID, UUID]]`: Stored in `modifers_uuids` for auto-removal
- **handler_uuids** `List[UUID]`: Stored in `event_handlers_uuids` for auto-removal
- **sub_condition_uuids** `List[UUID]`: Stored in `sub_conditions` for tree traversal
- **spatial_handler_uuids** `List[UUID]`: Stored in `spatial_handler_uuids` for auto-removal
- **effect_event** `Optional[Event]`: The event after EFFECT phase (completion handled externally)

### 4b. Duration System

Conditions have a `Duration` object controlling when they expire:

```python
from dnd.core.base_conditions import DurationType

# DurationType enum values:
# ROUNDS - expires after N rounds (decremented at turn boundaries)
# PERMANENT - never expires automatically
# UNTIL_LONG_REST - expires on long rest
# ON_CONDITION - expires when callable returns True

# Set duration BEFORE add_condition():
condition = Dashing(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
condition.duration.duration_type = DurationType.ROUNDS
condition.duration.duration = 1  # Expires after 1 round
entity.add_condition(condition)
```

**Duration class fields:**
- `duration`: `Optional[Union[int, ContextAwareCondition]]` - Round count or callable
- `duration_type`: `DurationType` - How expiration works
- `long_rested`: `bool` - Tracks if long rest occurred
- `owned_by_condition`: `Optional[UUID]` - Links to owning condition

**Checking expiration**: `duration.is_expired` computed property, `duration.progress()` decrements counter.

### 4c. Marker Conditions

Some conditions carry no modifiers - they just mark that something happened. Used for checking state.

```python
class HasAttacked(BaseCondition):
    """Marker: entity attacked this turn."""
    name: str = "HasAttacked"
    description: str = "Has made an attack this turn"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        # No modifiers - just a marker
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Marked as HasAttacked"
        )
        return [], [], [], [], effect_event
```

**Usage pattern**: Auto-applied via EventHandlers on specific events, 1-round duration:

```python
def has_attacked_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    entity = Entity.get(source_entity_uuid)
    if not entity or event.source_entity_uuid != source_entity_uuid:
        return None
    if "HasAttacked" not in entity.active_conditions:
        has_attacked = HasAttacked(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid
        )
        has_attacked.duration.duration_type = DurationType.ROUNDS
        has_attacked.duration.duration = 1
        entity.add_condition(has_attacked)
    return None
```

**Real uses**: `HasAttacked` and `HasTakenDamage` are used by rage maintenance - at turn start, the system checks `"HasAttacked" in entity.active_conditions` to decide if rage continues.

### 4d. Condition Removal Architecture

**BaseBlock drives all cleanup. Conditions only clean up their own state.**

```
Entity.remove_condition(name) → BaseBlock._remove_condition_tree(condition)
  ├── 1. Recurse into sub_conditions (same block, parent-child)
  ├── 2. Recurse into linked_conditions (other blocks via block.remove_condition_by_uuid)
  ├── 3. Call condition.cleanup_own_state() (removes own modifiers/handlers/spatial_handlers only)
  └── 4. Notify parent via reverse link (parent_link + child_removal_policy)
```

**BaseBlock._remove_condition_tree():**
```python
def _remove_condition_tree(self, condition: BaseCondition, expire: bool = False, parent_event: Optional[Event] = None) -> None:
    # 1. Handle sub_conditions (same block)
    for sub_uuid in list(condition.sub_conditions):
        sub = BaseCondition.get(sub_uuid)
        if sub is not None and isinstance(sub, BaseCondition):
            self._remove_condition_tree(sub, expire=expire, parent_event=parent_event)

    # 2. Handle linked_conditions (other blocks: entities, tiles, etc.)
    for target_block_uuid, cond_uuid in condition.linked_conditions:
        target_block = BaseBlock.get(target_block_uuid)
        if target_block:
            target_block.remove_condition_by_uuid(cond_uuid)

    # 3. Clean up this condition's OWN state only
    condition.cleanup_own_state(expire=expire, parent_event=parent_event)

    # 4. Notify linked parent of child removal (reverse link)
    if condition.parent_link is not None:
        parent_block_uuid, parent_cond_uuid = condition.parent_link
        parent_cond = BaseCondition.get(parent_cond_uuid)
        if (parent_cond and parent_cond.applied and parent_cond.name):
            parent_block = BaseBlock.get(parent_block_uuid)
            if parent_block and parent_cond.name in parent_block.active_conditions:
                policy = parent_cond.child_removal_policy
                if policy == "any":
                    parent_block.remove_condition(parent_cond.name, parent_event=parent_event)
                elif policy == "last":
                    remaining = sum(1 for _, cid in parent_cond.linked_conditions
                                    if (c := BaseCondition.get(cid)) and c.applied)
                    if remaining == 0:
                        parent_block.remove_condition(parent_cond.name, parent_event=parent_event)
```

**cleanup_own_state()** removes:
- All modifiers via `remove_condition_modifiers()`
- All event handlers via `remove_event_handlers()`
- All spatial handlers via `remove_spatial_handlers()`
- Sets `self.applied = False`

**Step 4 recursion safety**: `remove_condition()` pops from `active_conditions` BEFORE calling `_remove_condition_tree()`. The reverse link guard checks `parent_cond.name in parent_block.active_conditions` — if parent is mid-removal (already popped), guard skips. No infinite loops.

**Important**: Never call the old `condition.remove()` directly - use `Entity.remove_condition(name)`.

### 4e. Condition Immunity

Entity has two immunity systems:

```python
# Static immunities: List[Tuple[str, Dict]]
# (condition_name, metadata)
entity.condition_immunities = [("Poisoned", {}), ("Frightened", {})]

# Contextual immunities: Dict[str, List[Tuple[str, Callable]]]
# condition_name → [(name, check_function)]
entity.contextual_condition_immunities = {
    "Charmed": [("MindlessRage", lambda self, target, context: "Raging" in self.active_conditions)]
}
```

**Checked in `Entity.add_condition()` BEFORE `_apply()` runs:**

```python
def add_condition(self, condition, ...):
    declaration_event = condition.declare_event(parent_event)

    if self.check_condition_immunity(condition.name):
        return declaration_event.cancel(status_message=f"Condition {condition.name} is immune")

    # ... saving throw check, then apply
```

### 4f. Max Constraints

Use `add_max_constraint()` to cap a ModifiableValue at a maximum:

**Static max constraint** (always applies):
```python
# Grappled: speed max = 0
speed_obj = target.action_economy.movement
mod_uuid = speed_obj.self_static.add_max_constraint(
    constraint=NumericalModifier(
        name="Grappled",
        value=0,
        source_entity_uuid=self.target_entity_uuid,
        target_entity_uuid=self.source_entity_uuid
    )
)
outs.append((speed_obj.uuid, mod_uuid))
```

**Contextual max constraint** (conditional):
```python
# Frightened: speed = 0 only when frightener visible
movement_value = target.action_economy.movement
mod_uuid = movement_value.self_contextual.add_max_constraint(
    constraint=ContextualNumericalModifier(
        name="Frightened",
        source_entity_uuid=self.target_entity_uuid,
        target_entity_uuid=self.source_entity_uuid,
        callable=self.get_frigthener_in_senses_zero_max_speed()
    )
)
outs.append((movement_value.uuid, mod_uuid))
```

### 4g. Contextual Modifiers with partial()

For conditions that need runtime checks (entity visible? specific target?), use the `@staticmethod` + `partial()` pattern:

**The pattern:**
1. `@staticmethod` takes the bound UUID as first parameter, then standard `(source_entity_uuid, target_entity_uuid, context)` signature
2. `get_*()` instance method creates a `partial()` with the UUID baked in
3. The partial is passed as `callable` to a `Contextual*Modifier`

**Full example from Charmed:**

```python
class Charmed(BaseCondition):
    name: str = "Charmed"

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        target_entity = Entity.get(self.target_entity_uuid)
        outs = []

        # Prevent attacking the charmer - uses contextual auto-hit
        charmed_attack_check = self.get_charmed_attack_check()
        mod_uuid = target_entity.equipment.attack_bonus.self_contextual.add_auto_hit_modifier(
            modifier=ContextualAutoHitModifier(
                name="Charmed",
                source_entity_uuid=self.target_entity_uuid,
                target_entity_uuid=self.source_entity_uuid,
                callable=charmed_attack_check
            )
        )
        outs.append((target_entity.equipment.attack_bonus.uuid, mod_uuid))
        # ...

    @staticmethod
    def charmed_attack_check(
        charmer_id: UUID,           # ← Bound via partial()
        source_entity_uuid: UUID,    # ← Standard: the entity being checked
        target_entity_uuid: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[AutoHitModifier]:
        """Returns AUTOMISS if attacking the charmer."""
        if target_entity_uuid:
            entity = Entity.get(target_entity_uuid)
            if entity and entity.uuid == charmer_id:
                return AutoHitModifier(
                    name="Charmed",
                    value=AutoHitStatus.AUTOMISS,
                    source_entity_uuid=source_entity_uuid,
                    target_entity_uuid=target_entity_uuid
                )
        return None

    def get_charmed_attack_check(self) -> ContextAwareAutoHit:
        """Bind charmer UUID into the callable via partial()."""
        return partial(self.charmed_attack_check, self.source_entity_uuid)
```

**Other real uses of this pattern:**
- `Frightened`: Disadvantage only when frightener visible in senses
- `Invisible`: Advantage only when target can't see you
- `Paralyzed`: Auto-crit only when attacker is within 5ft (distance-based)

### Modifier Placement Guide

| Effect Type | Channel | Method | Example |
|-------------|---------|--------|---------|
| Affects own rolls | `self_static` | `add_advantage_modifier()` | Poisoned: disadvantage on attacks |
| Affects own rolls conditionally | `self_contextual` | `add_advantage_modifier()` | Frightened: only when frightener visible |
| Affects attackers | `to_target_static` | `add_advantage_modifier()` | Blinded: attackers have advantage |
| Affects attackers conditionally | `to_target_contextual` | `add_advantage_modifier()` | Prone: advantage if ≤5ft, disadvantage if >5ft |
| Numerical bonus/penalty | `self_static` | `add_value_modifier()` | Dashing: +30 movement |
| Max constraint | `self_static` | `add_max_constraint()` | Grappled: speed max = 0 |
| Contextual max constraint | `self_contextual` | `add_max_constraint()` | Frightened: speed=0 when frightener visible |

### Modifier Types

| Type | Values | Used For |
|------|--------|----------|
| `NumericalModifier` | int | Bonuses, penalties |
| `AdvantageModifier` | ADVANTAGE (+1), DISADVANTAGE (-1) | Attack rolls, checks |
| `CriticalModifier` | AUTOCRIT, NOCRIT | Paralyzed auto-crit |
| `AutoHitModifier` | AUTOHIT, AUTOMISS | Charmed can't attack charmer |
| `ResistanceModifier` | RESISTANCE, VULNERABILITY, IMMUNITY | Damage types |

Each has a `Contextual*` variant taking a callable that returns the modifier or None.

---

## Section 5: Sub-conditions & Linked Conditions

### Sub-conditions Pattern (Same Block)

Sub-conditions are child conditions on the **same block**. When the parent is removed, all sub-conditions are automatically removed via `_remove_condition_tree()`.

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

return outs, [], sub_conditions_uuids, [], effect_event
# When Paralyzed is removed, Incapacitated is automatically removed too
```

### Linked Conditions Pattern (Cross-Block)

Use `linked_conditions` when Block A causes a condition on Block B, and removing A's condition should clean up B's. This unified field replaces the old `external_conditions` and `terrain_conditions` -- both are now `linked_conditions` since both Entity and Tile are BaseBlock subclasses.

**Use cases:**
- Concentration spells (caster's Concentrating → target's spell effect)
- Grappling (grappler's condition → target's Grappled)
- Auras (paladin's condition → allies' AuraBonus)
- Zone spells (caster's condition → tile conditions)

```python
# BaseCondition fields:
linked_conditions: List[Tuple[UUID, UUID]] = []  # (target_block_uuid, condition_uuid)
parent_link: Optional[Tuple[UUID, UUID]] = None   # (parent_block_uuid, parent_condition_uuid) — auto-set
child_removal_policy: Literal["none", "any", "last"] = "none"  # parent notification policy

# Categorization:
condition_category: ConditionCategory = ConditionCategory.CONDITION  # CONDITION, STATUS, or INTERNAL
# CONDITION = D&D conditions (Blinded, Paralyzed). STATUS = engine states (Dashing, ShieldBuff). INTERNAL = markers (HasAttacked) — suppressed from combat logs.

# Hazard awareness (for tile conditions):
hazard_filter: Optional[HazardFilter] = None  # ALL, ENEMIES, NON_SOURCE — marks condition as hazardous
condition_stealth_dc: Optional[int] = None     # Perception DC to detect (hidden traps)

# Methods:
condition.add_linked_condition(target_block_uuid, effect_condition_uuid)
# ^^ also auto-sets child.parent_link = (self.target_entity_uuid, self.uuid)
```

**Reverse link system**: `add_linked_condition()` automatically sets `parent_link` on the child condition, enabling child→parent notification. The `child_removal_policy` on the parent controls what happens:
- `"none"` (default) — No notification. Use for fire-and-forget links.
- `"any"` — Remove parent when any child removed. Cascades to all remaining siblings.
- `"last"` — Remove parent when the last applied child removed. Used by `Concentrating`.

**Example - Concentration Spell:**
```python
# Structure (bidirectional):
# Caster: Concentrating ──linked_conditions──► Target: SpellEffect ──sub_conditions──► Paralyzed
#                        ◄──parent_link───────

# In spell's _apply():
# 1. Apply spell-specific effect to target
spell_effect = HoldPersonEffect(source=caster.uuid, target=target.uuid)
target.add_condition(spell_effect)

# 2. Apply Concentrating to caster
concentration = Concentrating(source=caster.uuid, target=caster.uuid, spell_name="Hold Person")
caster.add_condition(concentration)
# Concentrating has child_removal_policy="last" by default

# 3. Link via linked_conditions (auto-sets spell_effect.parent_link)
concentration.add_linked_condition(target.uuid, spell_effect.uuid)

# Forward cleanup (concentration breaks from damage/new spell/death):
# caster.remove_condition("Concentrating") → _remove_condition_tree()
#   → removes HoldPersonEffect from target via linked_conditions
#   → Paralyzed removed as sub-condition
#   → step 4: child's parent_link checked, but parent already popped → guard skips (no loop)

# Reverse cleanup (target saves/dispelled/effect removed):
# target.remove_condition("Hold Person") → _remove_condition_tree()
#   → Paralyzed removed as sub-condition
#   → cleanup_own_state()
#   → step 4: parent_link → Concentrating, policy "last", remaining=0
#     → caster.remove_condition("Concentrating")
#       → linked_conditions tries HoldPersonEffect (by_uuid=None, already removed) → no-op
```

**Example - Zone Spell (Tile Conditions):**
```python
# linked_conditions works for tiles too, since Tile is a BaseBlock:
condition.add_linked_condition(tile.uuid, tile_condition.uuid)
```

When the condition is removed, `_remove_condition_tree()` iterates `linked_conditions` and removes each linked condition from its target block (whether Entity or Tile). If the child has a `parent_link`, it can notify the parent via `child_removal_policy`.

### Three Linkage Types Summary

| Field | Target | Direction | Use Case | Cleanup |
|-------|--------|-----------|----------|---------|
| `sub_conditions` | Same block | Parent→child (`parent_condition` reverse) | Paralyzed → Incapacitated | BaseBlock recurses same-block |
| `linked_conditions` | Other blocks | Parent→child (forward) | Concentrating → spell effect, zone → tiles | `target_block.remove_condition_by_uuid()` |
| `parent_link` | Parent block | Child→parent (reverse) | SpellEffect → Concentrating | Step 4: check `child_removal_policy` |

---

## Section 6: How to Implement an Action

### 6a. Full apply() Lifecycle

```
apply(parent_event)
├── check_costs() → validates all BaseCost items are affordable
├── _create_declaration_event(parent_event) → ActionEvent at DECLARATION phase
├── _validate(declaration_event) → returns EXECUTION event or CANCEL
├── [MULTI_ENTITY/POSITION_AOE]: convolution loop per target
│   └── _apply(per_target_event) → EFFECT → COMPLETION per target
├── [Single target]: _apply(execution_event) → EFFECT → COMPLETION
└── _apply_costs(completion_event) → deducts action economy + resources
```

**Key**: `parent_event` threads through the entire chain for combat log hierarchy.

### 6b. Multi-Target Convolution Loop

For `MULTI_ENTITY` and `POSITION_AOE` actions, `apply()` runs a convolution loop:

```python
# In BaseAction.apply(), simplified:
all_target_uuids = self.get_all_targets()

for target_uuid in all_target_uuids:
    self.target_entity_uuid = target_uuid

    # KEY: Each target gets a NEW lineage_uuid (isolated tracking)
    per_target_event = execution_event.model_copy(update={
        'uuid': uuid4(),
        'lineage_uuid': uuid4(),        # NEW lineage per target
        'parent_event': execution_event.uuid,  # Child of parent
        'target_entity_uuid': target_uuid,
        'children_events': [],
        'lineage_children_events': [],
    })
    per_target_event = cast(ActionEvent, EventQueue.register(per_target_event))

    result_event = self._apply(per_target_event)
    total_damage += getattr(result_event, 'total_damage', 0) or 0

# Parent completion collects per-target children as sub_entries
completion_event = execution_event.phase_to(
    EventPhase.COMPLETION,
    total_targets=len(all_target_uuids),
    total_damage=total_damage,
)
```

### 6c. ActionCategory & Cost System

Every action has an `action_category` field (`dnd/core/base_actions.py`):

```python
class ActionCategory(str, Enum):
    ABILITY = "ability"      # Default: Dash, Dodge, Disengage, etc.
    ATTACK = "attack"        # Attack, Extra Attack, Retaliation, Frenzied Strike
    SPELL = "spell"          # SpellAction (Fire Bolt, Fireball, etc.)
    MOVEMENT = "movement"    # Move, Jump
```

Set `action_category=ActionCategory.ATTACK` on your action class. Properties `is_attack`, `is_spell`, `is_movement` are available for checks. Do NOT use `_is_attack` or `_is_spell` private attributes (removed).

Actions have dual costs: turn-based (action economy) and resource-based:

```python
class BaseCost(BaseModel):
    name: str
    cost_type: CostType  # "actions", "bonus_actions", "reactions", "movement", "spell_slot_N"
    cost: int
    resource_name: Optional[str] = None  # e.g., "second_wind"
    resource_cost: int = 0               # Amount of resource to consume

# Example: Second Wind costs 1 bonus action + 1 second_wind resource
Cost(
    name="Second Wind Cost",
    cost_type="bonus_actions",
    cost=1,
    resource_name="second_wind",
    resource_cost=1,
    evaluator=entity_action_economy_cost_evaluator
)

# Example: Extra Attack costs 0 actions + 1 extra_attacks resource
Cost(
    name="Extra Attack Cost",
    cost_type="actions",
    cost=0,
    resource_name="extra_attacks",
    resource_cost=1,
    evaluator=entity_action_economy_cost_evaluator
)
```

**check_costs()** validates both: `evaluator(source_uuid, cost_type, cost)` for turn-based, `action_economy.can_afford_resource(name, amount)` for resources.

**_apply_costs()** is typically: `return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)`

### 6d. Template Instantiation

Actions are registered as templates (`template=True`) and instantiated for execution:

```python
# Register template
action = SecondWind(source_entity_uuid=entity.uuid, template=True)
entity.register_action(action)

# Instantiate for use (deep copy with new UUID)
instance = action.instantiate(target_entity_uuid=target.uuid)
instance.apply()
```

Move actions override `instantiate()` to recompute path and costs from terrain.

### 6e. pre_validate()

Creates an unregistered event for cheap validation without side effects:

```python
# Pattern from reactions.py:
reaction_attack = Attack(
    source_entity_uuid=source_uuid,
    target_entity_uuid=event.source_entity_uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
    use_register=False,  # Don't register yet
    costs=[Cost(name="OA", cost_type="reactions", cost=1, evaluator=entity_action_economy_cost_evaluator)]
)

if reaction_attack.pre_validate():       # Cheap check
    reaction_attack.add_to_register()     # Now register
    reaction_attack.apply(parent_event=event)  # Execute
```

### 6f. AvailableActionsResult

`Entity.get_available_actions()` returns grouped actions:

```python
class AvailableActionsResult(BaseModel):
    entity_uuid: UUID
    entity_actions: List[AvailableActionInfo]    # Attacks with valid_targets
    position_actions: List[AvailableActionInfo]  # Move, Jump (position-based)
    self_actions: List[AvailableActionInfo]       # Dash, Dodge, Disengage

class AvailableActionInfo(BaseModel):
    template_name: str          # Name for execution
    target_type: TargetType
    valid_targets: List[AvailableTarget]  # Indexed list of targets
    range: Optional[Range]
    is_attack: bool
    is_spell: bool
    weapon_slot: Optional[str]
    weapon_name: Optional[str]
```

### 6g. Per-Step Movement

Movement processes the path cell-by-cell, not as a single transaction:

```python
# In Move._apply(), simplified:
try:
    for i in range(1, total_path_length):
        from_pos = path[i - 1]
        to_pos = path[i]

        # 1. Check terrain cost
        tile = grid.get_tile(*to_pos)
        step_cost_feet = int(tile.get_movement_cost(MovementMode.WALKING) * 5)

        # 2. Check remaining movement
        if source_entity.action_economy.movement.normalized_score < step_cost_feet:
            break

        # 3. Fire StepMovementEvent at EFFECT phase
        step_event = StepMovementEvent(
            source_entity_uuid=self.source_entity_uuid,
            from_position=from_pos,
            to_position=to_pos,
            movement_cost=step_cost_feet,
            phase=EventPhase.EFFECT,
            parent_event=effect_event.uuid
        )
        processed_step = step_event.post()

        # 4. Check if step was canceled (by OA or trap)
        if processed_step.canceled:
            break

        # 5. Re-check walkability (handlers may have changed the map, e.g. Intercept)
        if not grid.is_walkable_for(to_pos[0], to_pos[1], source_entity.uuid):
            break

        # 6. Actually move the entity
        Entity.update_entity_position(source_entity, to_pos, parent_event=processed_step.uuid)

        # 7. Complete step (generates combat log)
        processed_step.phase_to(EventPhase.COMPLETION)

        # 8. Deduct movement cost
        source_entity.action_economy.consume("movement", step_cost_feet)

        # 9. Check death during movement
        if "Dead" in source_entity.active_conditions:
            break
finally:
    source_entity.update_entity_senses(max_distance=20)
```

**Key**: The `StepMovementEvent` at EFFECT phase is what triggers OA handlers and zone spatial handlers.

### Template-Based Action Example

```python
class SecondWind(BaseAction):
    name: str = "Second Wind"
    target_type: TargetType = TargetType.SELF
    costs: List[Cost] = []

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Second Wind Cost",
                cost_type="bonus_actions",
                cost=1,
                resource_name="second_wind",
                resource_cost=1,
                evaluator=entity_action_economy_cost_evaluator
            )
        ]

    def _create_declaration_event(self, parent_event=None, use_register=True):
        return ActionEvent(name=self.name, ...)

    def _validate(self, declaration_event):
        # Return EXECUTION phase or CANCEL
        return declaration_event.phase_to(EventPhase.EXECUTION, ...)

    def _apply(self, execution_event):
        # Execute the action, return EFFECT → COMPLETION
        effect_event = execution_event.phase_to(EventPhase.EFFECT, ...)
        return effect_event.phase_to(EventPhase.COMPLETION, ...)

    def _apply_costs(self, completion_event):
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)
```

### TargetType Enum

| Type | Used For |
|------|----------|
| `SELF` | Dash, Dodge, Disengage, Second Wind |
| `ENTITY` | Attack, Extra Attack, Shove |
| `POSITION_PATH` | Move (requires contiguous path via senses.paths) |
| `POSITION_LOS` | Jump, Teleport (visible + range only) |
| `POSITION_AOE` | AoE spells (position + affected entities preview) |
| `MULTI_ENTITY` | Multi-target spells (targets list of entities) |

### Resource System

Limited-use features use the resource system:

```python
# In feature condition's _apply():
target.action_economy.add_resource(
    name="second_wind",
    maximum=1,
    recharge_type=RechargeType.SHORT_REST  # or LONG_REST, TURN_START, NEVER
)

# Register action template
action = SecondWind(source_entity_uuid=target.uuid, template=True)
target.register_action(action)
```

---

## Section 7: How to Implement an Event Handler

Event handlers react to game events (damage rolls, turn start, attacks, etc.).

### Basic Structure

```python
def my_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    # Only process relevant events
    if event.source_entity_uuid != source_entity_uuid:
        return None

    # Do something...

    # Return modified event or None (no-op)
    return event.model_copy(update={"modified": True})

def create_my_handler(source_entity_uuid: UUID) -> EventHandler:
    return EventHandler(
        name="MyHandler",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.DAMAGE_ROLL_RESULT,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=my_processor
    )
```

### Registering Handlers

```python
# In condition _apply():
handler = create_my_handler(target.uuid)
target.add_event_handler(handler)  # Also registers with EventQueue
# IMPORTANT: Only call entity.add_event_handler() - it auto-registers with EventQueue.
# Do NOT also call EventQueue.add_event_handler() or the handler fires twice!

# Return handler UUID for auto-cleanup
return [], [handler.uuid], [], [], effect_event
```

### Double-Registration Warning

`entity.add_event_handler(handler)` calls `EventQueue.add_event_handler(handler)` internally. If you ALSO call `EventQueue.add_event_handler(handler)` directly, the handler fires **twice** for every matching event.

### Multiple Handlers Per Condition

Complex conditions can register multiple handlers. Example from Raging:

```python
# Raging registers 3 handlers:
handler_uuids = []

# 1. Rage maintenance handler (checks HasAttacked/HasTakenDamage markers)
maintenance_handler = create_rage_maintenance_handler(target.uuid)
target.add_event_handler(maintenance_handler)
handler_uuids.append(maintenance_handler.uuid)

# 2. Armor watch handler (ends rage if heavy armor equipped)
armor_handler = create_rage_armor_watch_handler(target.uuid)
target.add_event_handler(armor_handler)
handler_uuids.append(armor_handler.uuid)

# 3. Death watch handler (ends rage on death)
death_handler = create_rage_death_watch_handler(target.uuid)
target.add_event_handler(death_handler)
handler_uuids.append(death_handler.uuid)

return outs, handler_uuids, [], [], effect_event
```

### Phase Timing: TURN_START Ordering

**Critical**: `TURN_START`/`EXECUTION` fires BEFORE conditions expire at `TURN_START`/`EFFECT`. This ordering is essential for rage maintenance:

```
TURN_START/EXECUTION → rage maintenance checks HasAttacked/HasTakenDamage markers
TURN_START/EFFECT    → HasAttacked/HasTakenDamage expire (1-round duration)
```

If you check at EFFECT instead of EXECUTION, the markers are already gone.

### Type Narrowing in Handlers

Use `isinstance()` before accessing event-specific fields:

```python
def armor_watch_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    # Type-narrow to access armor-specific fields
    if isinstance(event, ArmorEquipEvent):
        if event.armor_type == ArmorType.HEAVY:
            # End rage
            ...
    return None
```

### Common Trigger Points

| EventType | Phase | Use Case |
|-----------|-------|----------|
| `ATTACK` | `EXECUTION` | Protection (impose disadvantage before roll) |
| `DAMAGE_ROLL_RESULT` | `EFFECT` | Great Weapon Fighting (reroll dice) |
| `SAVING_THROW` | `EFFECT` | Indomitable (reroll failed save) |
| `TURN_START` | `EXECUTION` | Survivor (heal), rage maintenance (pre-expiration) |
| `TAKE_DAMAGE` | `EFFECT` | HasTakenDamage marker, concentration checks |
| `STEP_MOVEMENT` | `EFFECT` | Opportunity attacks |

**Important**: `COMPLETION` phase is closed to handlers - they will never fire.

---

## Section 8: Spatial Handlers (Zone Spells)

Spatial handlers are position-indexed variants of event handlers for zone effects. Instead of matching by trigger conditions, they fire at specific grid positions via O(1) lookup.

### SpatialHandler vs EventHandler

| Feature | EventHandler | SpatialHandler |
|---------|-------------|----------------|
| Matching | Trigger conditions (type, phase, source/target) | Position index (O(1) by grid position) |
| Registry | `_event_handlers` | `_spatial_handlers` (separate) |
| Registration | `entity.add_event_handler(handler)` | `EventQueue.add_spatial_handler(handler, positions, event_type, event_phase)` |
| Use case | Reactions, dice manipulation, turn effects | Zone entry/exit effects |

### SpatialHandler Class

```python
class SpatialHandler(BaseHandler):
    name: str = "SpatialHandler"
    positions: Set[Tuple[int, int]] = Field(default_factory=set)
    event_type: EventType = Field(default=EventType.SPATIAL_ENTITY_ENTERED)
    event_phase: EventPhase = Field(default=EventPhase.EFFECT)

    # No trigger_conditions - position filtering done by registry lookup
    def __call__(self, event: Event, source_entity_uuid=None) -> Optional[Event]:
        if source_entity_uuid is None:
            source_entity_uuid = self.source_entity_uuid
        return self.event_processor(event, source_entity_uuid)
```

### Using ZoneControlCondition (Preferred)

For zone spells, extend `ZoneControlCondition` from `dnd/tile_conditions.py`:

```python
from dnd.tile_conditions import ZoneControlCondition

class MyZone(ZoneControlCondition):
    name: str = "My Zone"
    zone_shape: str = Field(default="sphere")     # sphere, cone, line, cube
    zone_radius_feet: int = Field(default=20)
    adds_difficult_terrain: bool = Field(default=True)
    spell_dc: int = Field(default=10)

    def _has_entry_effect(self) -> bool:
        return True

    def _has_exit_effect(self) -> bool:
        return False

    def _has_turn_start_effect(self) -> bool:
        return False

    def _create_zone_entry_handler(self) -> EventHandler:
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            entity_uuid = getattr(event, 'entity_uuid', None)
            if not entity_uuid:
                return None
            entity = Entity.get(entity_uuid)
            if not entity or entity.uuid == source_uuid:
                return None
            # Apply zone effect (damage, save, condition, etc.)
            ...
            return None

        return EventHandler(
            name="My Zone Entry",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )
```

### ZoneControlCondition._apply() Flow

The base `_apply()` handles all registration:

```python
def _apply(self, declaration_event):
    handler_uuids = []
    spatial_handler_uuids = []

    # Compute affected positions from shape
    self.affected_positions = self._compute_affected_positions()

    # Register entry handler (if subclass enables it)
    if self._has_entry_effect():
        handler = self._create_zone_entry_handler()
        EventQueue.add_spatial_handler(handler, self.affected_positions,
                                       EventType.SPATIAL_ENTITY_ENTERED, EventPhase.EFFECT)
        spatial_handler_uuids.append(handler.uuid)

    # Register exit handler
    if self._has_exit_effect():
        handler = self._create_zone_exit_handler()
        EventQueue.add_spatial_handler(handler, self.affected_positions,
                                       EventType.SPATIAL_ENTITY_LEFT, EventPhase.EFFECT)
        spatial_handler_uuids.append(handler.uuid)

    # Register turn start handler (NOT spatial - uses EventHandler)
    if self._has_turn_start_effect():
        handler = self._create_zone_turn_start_handler()
        EventQueue.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

    # Apply terrain modifiers (difficult terrain)
    terrain_modifiers = self._apply_terrain_modifiers()

    effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
    return terrain_modifiers, handler_uuids, [], spatial_handler_uuids, effect_event
```

### Zone Movement

For zones that move (like Spirit Guardians following the caster):

```python
def move_zone(self, new_center: Tuple[int, int]) -> bool:
    self._remove_terrain_modifiers()
    self.zone_center = new_center
    new_positions = self._compute_affected_positions()

    # Efficient batch update - O(delta) not O(total)
    EventQueue.update_spatial_handler_positions(
        self._entry_handler_uuid, new_positions,
        EventType.SPATIAL_ENTITY_ENTERED, EventPhase.EFFECT
    )
    self.affected_positions = new_positions
    self._apply_terrain_modifiers()
    return True
```

### Reference Implementations

| Zone | File | Features |
|------|------|----------|
| `SpikeGrowthZone` | `dnd/spells/transmutation.py` | Entry damage (2d4 per 5ft) |
| `WebZone` | `dnd/spells/conjuration.py` | Entry save or Restrained |
| `GreaseZone` | `dnd/spells/conjuration.py` | Entry + turn-start saves, Prone |
| `ZoneControlCondition` | `dnd/tile_conditions.py` | Base class with all override points |

---

## Section 9: Dice Manipulation Pattern (DAMAGE_ROLL_RESULT)

For abilities that modify dice results (Great Weapon Fighting, Elemental Adept):

```python
def my_dice_processor(event: DamageRollResultEvent, source_entity_uuid: UUID) -> Optional[DamageRollResultEvent]:
    if event.source_entity_uuid != source_entity_uuid:
        return None

    # Check conditions (weapon type, damage type, etc.)
    entity = Entity.get(source_entity_uuid)
    weapon = entity.equipment._get_weapon_by_slot(event.weapon_slot)
    if not meets_requirements(weapon):
        return None

    # Process each roll
    any_modified = False
    for i, original_roll in enumerate(event.final_rolls):
        new_roll = manipulate_dice(original_roll)
        if new_roll.results != original_roll.results:
            event.replace_roll(i, new_roll, "Handler Name", "Reason")
            any_modified = True

    return event.model_copy(update={"modified": True}) if any_modified else None
```

**Key**: Original rolls are immutable. Create new DiceRoll objects:

```python
from dnd.classes.fighter import create_modified_dice_roll

new_roll = create_modified_dice_roll(original_roll, [6, 4, 5])
```

### Available Dice Utilities

In `dnd/classes/dice_processor_utils.py`:

| Function | Description |
|----------|-------------|
| `floor_results(roll, min)` | No result below minimum (Elemental Adept) |
| `reroll_below_and_substitute(roll, threshold, dice_size)` | Reroll low dice, must use new (GWF) |
| `reroll_below_keep_best(roll, threshold, dice_size)` | Reroll low dice, keep best (Lucky) |

---

## Section 10: Spell System Patterns

### SpellAction Class

```python
class SpellAction(BaseAction):
    spell_level: int = 0           # Base spell level (0 = cantrip)
    spell_school: str = "evocation"
    concentration: bool = False
    spell_range: Range = ...       # Spell-specific range
    cast_at_level: int = 0         # Actual slot level used
    is_variant: bool = False       # Whether this is an upcast variant
    caster_level: int = 1          # For cantrip scaling
```

### Spell Registration

```python
from dnd.actions_functional import register_spell, register_spells_by_name
from dnd.spells import FireBolt, ALL_SPELLS

# Register individual spell
register_spell(entity, FireBolt, caster_level=5)

# Register multiple by name (looks up in ALL_SPELLS dict)
register_spells_by_name(entity, ["Fire Bolt", "Magic Missile", "Fireball"], caster_level=5)
```

### Variant Generation (Upcasting)

`generate_variants()` creates one variant per available spell slot:

```python
def generate_variants(self, entity: Entity) -> List[SpellAction]:
    variants = []
    if self.spell_level == 0:
        # Cantrip - single variant, no slot cost
        variants.append(self._create_variant(cast_at_level=0))
    else:
        # Leveled spell - variant per available slot
        for slot_level in range(self.spell_level, 10):
            if entity.has_spell_slot(slot_level):
                variants.append(self._create_variant(cast_at_level=slot_level))
    return variants
```

Costs include action + spell slot: `[Cost("Cast Spell", "actions", 1), Cost("Spell Slot L3", "spell_slot_3", 1)]`

### Entity Spell Methods

```python
entity.spell_attack_bonus(target_uuid)  # prof + ability + bonuses → ModifiableValue
entity.spell_save_dc()                  # 8 + prof + ability + bonuses → int
entity.get_spell_crit_threshold()       # Default 20
entity.get_spell_crit_extra_dice()      # Extra dice on crit
entity.has_spell_slot(level)            # Check availability
entity.is_spellcaster                   # Property
```

### Save Spell Pattern

```python
def _apply(self, execution_event):
    target = Entity.get(self.target_entity_uuid)
    caster = Entity.get(self.source_entity_uuid)
    dc = caster.spell_save_dc()

    save_request = SavingThrowEvent(
        ability_name="dexterity",
        dc=dc,
        source_entity_uuid=self.source_entity_uuid,
        target_entity_uuid=self.target_entity_uuid,
        parent_event=execution_event.uuid,  # Link to parent!
    )
    _, _, success = target.saving_throw(save_request)

    if success:
        # Half damage on save
        damage = total_damage // 2
    else:
        # Full damage on fail
        damage = total_damage

    target.receive_damage(damage, DamageType.FIRE, caster.uuid,
                          parent_event=execution_event.uuid)
```

### Attack Spell Pattern

```python
def _apply(self, execution_event):
    caster = Entity.get(self.source_entity_uuid)
    target = Entity.get(self.target_entity_uuid)

    # 1. Cross-propagate attack/AC modifiers
    attack_bonus = caster.spell_attack_bonus(target.uuid)
    ac = target.ac_bonus(caster.uuid)
    ac.set_from_target(attack_bonus)
    attack_bonus.set_from_target(ac)

    # 2. Roll attack
    dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK)
    crit_threshold = caster.get_spell_crit_threshold()
    outcome = determine_attack_outcome(dice_roll, ac, crit_threshold)

    # 3. Clean up cross-propagation
    ac.reset_from_target()
    attack_bonus.reset_from_target()

    if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
        return ...  # miss handling

    # 4. Roll damage — CRITICAL: do NOT manually double dice_numbers!
    #    Pass un-doubled dice count; get_dice() handles crit doubling internally.
    num_dice = ...  # base dice count (e.g., _get_cantrip_dice_count)
    is_crit = outcome == AttackOutcome.CRIT
    crit_extra = caster.get_spell_crit_extra_dice() if is_crit else 0

    damage = Damage(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        damage_dice=10,           # die size (d10)
        dice_numbers=num_dice,    # UN-DOUBLED base count
        damage_bonus=caster.get_spell_damage_bonus(),
        damage_type=DamageType.FIRE
    )
    damage_dice = damage.get_dice(attack_outcome=outcome, crit_extra_dice=crit_extra)
    damage_roll = damage_dice.roll

    target.receive_damage(
        amount=damage_roll.total, damage_type=DamageType.FIRE,
        source_entity_uuid=caster.uuid, parent_event=effect_event.uuid
    )
```

**WRONG (double-doubling bug):** `dice_numbers=num_dice * (2 if is_crit else 1)` then `get_dice(attack_outcome=outcome)` — this doubles twice (4x on crit).
**CORRECT:** `dice_numbers=num_dice` (un-doubled) then `get_dice(attack_outcome=outcome, crit_extra_dice=crit_extra)` — `Dice._roll()` handles the single doubling.

### Concentration Pattern

Full lifecycle for concentration spells:

```python
# 1. Apply spell effect on target
spell_effect = HoldPersonEffect(source=caster.uuid, target=target.uuid)
target.add_condition(spell_effect, parent_event=execution_event)

# 2. Apply Concentrating on caster (auto-ends previous concentration)
concentration = Concentrating(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=caster.uuid,
    spell_name="Hold Person"
)
caster.add_condition(concentration)

# 3. Link via linked_conditions for cleanup chain
concentration.add_linked_condition(target.uuid, spell_effect.uuid)
```

**CON save on damage**: `Concentrating` registers a handler on `TAKE_DAMAGE/EFFECT` that makes a CON save with DC = max(10, damage/2). Failed save removes the condition.

---

## Section 11: Opportunity Attacks / Reactions

### Handler Setup

OA triggers on `STEP_MOVEMENT/EFFECT`:

```python
def create_opportunity_attack_handler(source_entity_uuid: UUID) -> EventHandler:
    return EventHandler(
        name="Opportunity Attack Handler",
        trigger_conditions=[Trigger(
            name="Opportunity Attack Trigger",
            event_type=EventType.STEP_MOVEMENT,
            event_phase=EventPhase.EFFECT
        )],
        event_processor=opportunity_attack_processor,
        source_entity_uuid=source_entity_uuid
    )

def add_opportunity_attack_handler(entity: Entity):
    entity.add_event_handler(create_opportunity_attack_handler(entity.uuid))
```

### OA Processor Logic

```python
def opportunity_attack_processor(event: StepMovementEvent, source_entity_uuid: UUID) -> Optional[StepMovementEvent]:
    reaction_source = Entity.get(source_entity_uuid)  # The watcher
    moving_entity = Entity.get(event.source_entity_uuid)  # The mover

    # Can't OA yourself
    if reaction_source.uuid == moving_entity.uuid:
        return event

    # Disengage prevents OA
    if "Disengaging" in moving_entity.active_conditions:
        return event

    threatened = reaction_source.senses.get_threathened_positions()

    # OA triggers when step LEAVES threatened area
    if event.from_position in threatened and event.to_position not in threatened:
        reaction_attack = Attack(
            name="Opportunity Attack",
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=event.source_entity_uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
            use_register=False,
            costs=[Cost(name="OA", cost_type="reactions", cost=1,
                       evaluator=entity_action_economy_cost_evaluator)]
        )
        if reaction_attack.pre_validate():
            reaction_attack.add_to_register()
            reaction_attack.apply(parent_event=event)

    return event
```

**Key pattern**:
1. Check `Disengaging` on moving entity
2. Check from_position in threat AND to_position NOT in threat
3. `pre_validate()` → `add_to_register()` → `apply(parent_event=event)` for proper event chain

---

## Section 12: Combat Log Generation

Events auto-generate combat log entries at COMPLETION phase via `generate_combat_log()`.

### Basic Pattern

```python
class MyActionEvent(ActionEvent):
    name: str = Field(default="My Action")
    event_type: EventType = Field(default=EventType.BASE_ACTION)
    my_result: int = Field(default=0)

    def generate_combat_log(self) -> CombatLogEntry:
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"

        compact_text = f"{md_color(source_name, 'cyan')} does something to {md_color(target_name, 'yellow')}"
        verbose_text = compact_text + f"\n  Result: {self.my_result}"
        detailed_text = verbose_text + f"\n  More details..."

        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data={"my_result": self.my_result},
            success=self.my_result > 0
        )
```

### Key Points

1. **Entity names must be set at event creation** (not looked up in `generate_combat_log()`):
   ```python
   return MyActionEvent(
       source_entity_name=source.name,
       target_entity_name=target.name,
       ...
   )
   ```

2. **Parent-child hierarchy**: `_collect_child_combat_logs()` traverses `lineage_children_events`, de-duplicates by `lineage_uuid`, builds `sub_entries` tree automatically.

3. **Multi-target pattern**: Parent COMPLETION collects per-target child combat logs into `sub_entries`:
   ```
   Fireball → "3 targets, 42 total damage"
   ├── sub_entry → "Skeleton 1: DEX save FAIL, 15 fire damage"
   ├── sub_entry → "Skeleton 2: DEX save SAVE, 7 fire damage (half)"
   └── sub_entry → "Skeleton 3: DEX save FAIL, 15 fire damage"
   ```

4. **Callback**: Only `parent_event=None` events fire the Encounter callback at COMPLETION.

### CombatLogEntryType Values

`ATTACK`, `MOVEMENT`, `ACTION`, `SAVING_THROW`, `SKILL_CHECK`, `CONDITION_APPLIED`, `CONDITION_REMOVED`, `DAMAGE_TAKEN`, `HEAL`, `DEATH`, `TURN_START`, `TURN_END`, `MULTI_ENTITY_ACTION`, `SPELL_SAVE`, `SPELL_DAMAGE`

### Markdown Helpers (`dnd/core/combat_log.py`)

| Function | Output | Description |
|----------|--------|-------------|
| `md_color(text, color)` | `{color:text}` | Rich color rendering |
| `md_bold(text)` | `**text**` | Bold markdown |
| `md_outcome(outcome)` | `{green:HIT}` / `{red:MISS}` / `{bold yellow:CRIT!}` | Color-coded outcome |
| `md_d20_roll(roll)` | `d20({cyan:15})` or `ADV d20(15,8→{green:15})` | Format d20 with advantage |
| `md_breakdown(modifiers)` | `[Prof +2, DEX +2]` | Format modifier list |

### Structured Data Models

| Model | Fields |
|-------|--------|
| `AttackLogData` | attacker/target names+uuids, weapon, attack_roll, target_ac, outcome, damage_rolls, total_damage |
| `SpellSaveLogData` | caster/target, spell_name, save_ability, save_dc, save_roll, save_success, damage |
| `MultiEntityLogData` | action_name, total_targets, total_damage, saves_succeeded/failed, aoe_shape |
| `MovementLogData` | entity, from/to positions, path, movement_cost |
| `SavingThrowLogData` | entity, ability, dc, roll, success |
| `SkillCheckLogData` | entity, skill, roll, success |

### Three Verbosity Levels

- `compact`: One-line summary (for quick log view)
- `verbose`: Summary + key details (default display)
- `detailed`: Full modifier breakdowns (for debugging)

---

## Section 13: Entity & Equipment Factories

### 13a. Entity Creation Flow

```python
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.actions_functional import setup_standard_actions

# 1. Build config
entity_config = EntityConfig(
    ability_scores=AbilityScoresConfig(
        strength=AbilityConfig(ability_score=14),
        dexterity=AbilityConfig(ability_score=12),
        constitution=AbilityConfig(ability_score=13),
        intelligence=AbilityConfig(ability_score=10),
        wisdom=AbilityConfig(ability_score=10),
        charisma=AbilityConfig(ability_score=8)
    ),
    health=HealthConfig(hit_dices=[HitDiceConfig(
        hit_dice_value=8, hit_dice_count=3, mode="average"
    )]),
    equipment=EquipmentConfig(),
    action_economy=ActionEconomyConfig(),
    proficiency_bonus=2,
    position=(5, 5),
    faction="heroes",
    weight=150
)

# 2. Create entity (uuid == source_entity_uuid)
entity = Entity.create(
    name="Fighter",
    source_entity_uuid=source_id,
    config=entity_config
)

# 3. Register standard actions (Move, Dash, Dodge, Disengage, attacks)
setup_standard_actions(entity)

# 4. CRITICAL: Update senses after all entities created
Entity.update_all_entities_senses()
```

### 13b. Config Classes Reference

**AbilityConfig**: `AbilityConfig(ability_score=14)` - NOT raw int!

**HealthConfig / HitDiceConfig:**
```python
HealthConfig(
    hit_dices=[HitDiceConfig(
        hit_dice_value=10,   # d10
        hit_dice_count=5,    # 5 levels
        mode="average",      # "average", "maximums", or "roll"
        ignore_first_level=False
    )],
    vulnerabilities=[DamageType.BLUDGEONING],
    immunities=[DamageType.POISON],
    resistances=[]
)
```

**ActionEconomyConfig:**
```python
ActionEconomyConfig(
    actions=1,         # Default
    bonus_actions=1,
    reactions=1,
    movement=30,       # In feet
    spell_slots={1: 4, 2: 3, 3: 2}  # For spellcasters
)
```

**SpellcastingConfig:** `SpellcastingConfig(spellcasting_ability="charisma")` - "intelligence", "wisdom", or "charisma"

### 13c. Bestiary Factory Pattern

Full pattern from `dnd/monsters/bestiary.py`:

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

    entity_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=8),
            dexterity=AbilityConfig(ability_score=14),
            # ...
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=6, hit_dice_count=2, mode="average"
        )]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position, faction=faction, weight=weight
    )

    entity = Entity.create(name=name, source_entity_uuid=source_id, config=entity_config)
    setup_standard_actions(entity)

    # Create and equip
    scimitar = create_scimitar(entity.uuid)
    leather_armor = create_leather_armor(entity.uuid)
    shield = create_wooden_shield(entity.uuid)

    entity.equipment.equip(leather_armor)
    entity.equipment.equip(scimitar, WeaponSlot.MELEE_MAIN)
    entity.equipment.equip(shield, WeaponSlot.MELEE_OFF)
    return entity
```

**Available factories** (all use keyword args):
- `create_goblin(weight=40)` - CR 1/4, AC 15, Scimitar 1d6+2
- `create_skeleton(weight=120)` - CR 1/4, AC 13, Shortsword, vulnerability bludgeoning, immunity poison
- `create_goblin_archer(weight=40)` - Dual wield + shortbow
- `create_sorcerer(level=5)` - CHA 18, spell slots, 6 registered spells

### 13d. Class Factory Pattern

From `dnd/classes/fighter_factory.py`:

```python
class FighterConfig(BaseModel):
    level: int = Field(ge=1, le=20, default=1)
    name: str = "Fighter"
    position: Tuple[int, int] = (0, 0)
    faction: Optional[str] = None

    # Base abilities (BG3 style)
    base_strength: int = Field(default=15, ge=8, le=15)
    base_dexterity: int = Field(default=14, ge=8, le=15)
    # ...

    # Level 1 bonuses: +2 to one, +1 to another
    bonus_plus_2: AbilityName = "strength"
    bonus_plus_1: AbilityName = "constitution"

    # Fighting Style
    fighting_style: FightingStyleChoice = "defense"

    # ASI choices at levels 4, 6, 8, 12, 14, 16, 19
    asi_4: Optional[List[Tuple[AbilityName, int]]] = None
    # ...

    equipment_preset: EquipmentPreset = "sword_shield"
```

**create_fighter() flow:**
1. `calculate_final_ability_scores(config)` - base + L1 bonuses + ASIs, capped at 20
2. Build `EntityConfig` with calculated scores
3. `Entity.create()` → `setup_standard_actions()`
4. `apply_equipment(entity, config.equipment_preset)` - equip weapons/armor
5. `apply_fighter_features(entity, config)` - level-gated condition application

**apply_fighter_features()** applies conditions by level:
```python
def apply_fighter_features(entity, config):
    level = config.level
    apply_fighting_style(entity, config.fighting_style)  # L1
    entity.add_condition(SecondWindFeature(...))          # L1
    if level >= 2: entity.add_condition(ActionSurgeFeature(...))  # L2
    if level >= 3: entity.add_condition(ImprovedCritical(...))    # L3
    if level >= 5: entity.add_condition(ExtraAttackFeature(...))  # L5
    if level >= 9: entity.add_condition(Indomitable(...))         # L9
    if level >= 15: entity.add_condition(SuperiorCritical(...))   # L15
    if level >= 18: entity.add_condition(Survivor(...))           # L18
```

### 13e. Weapon Factories

From `dnd/items/weapons.py`:

```python
def create_scimitar(source_id: UUID) -> Weapon:
    return Weapon(
        source_entity_uuid=source_id,
        name="Scimitar",
        damage_dice=6,           # d6
        dice_numbers=1,          # 1d6
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )

# Multi-dice weapon (2d6):
def create_greatsword(source_id: UUID) -> Weapon:
    return Weapon(
        ...,
        damage_dice=6,
        dice_numbers=2,  # 2d6
        properties=[WeaponProperty.HEAVY, WeaponProperty.TWO_HANDED, WeaponProperty.MARTIAL],
        ...
    )
```

**WeaponProperty values**: `LIGHT`, `FINESSE`, `THROWN`, `VERSATILE`, `HEAVY`, `TWO_HANDED`, `MARTIAL`, `RANGED`, `REACH`

**Range**: `RangeType.REACH` (melee, normal=5) vs `RangeType.RANGE` (ranged, normal/long distances)

### 13f. Armor & Shield Factories

From `dnd/items/armors.py`:

```python
def create_leather_armor(source_id: UUID) -> BodyArmor:
    return BodyArmor(
        source_entity_uuid=source_id,
        name="Leather Armor",
        type=ArmorType.LIGHT,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=11, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Max Dex Bonus"),
    )

def create_chain_mail(source_id: UUID) -> BodyArmor:
    return BodyArmor(
        ...,
        type=ArmorType.HEAVY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=16, ...),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, ...),
        strength_requirement=13,
        stealth_disadvantage=True
    )

def create_shield(source_id: UUID) -> Shield:
    return Shield(
        source_entity_uuid=source_id,
        name="Shield",
        ac_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=2, ...),
    )
```

**ArmorType**: `LIGHT`, `MEDIUM`, `HEAVY`

### 13g. Equipment.equip() Rules

```python
# Weapons require explicit slot
entity.equipment.equip(scimitar, WeaponSlot.MELEE_MAIN)
entity.equipment.equip(dagger, WeaponSlot.MELEE_OFF)     # Off-hand requires LIGHT property
entity.equipment.equip(longbow, WeaponSlot.RANGED_MAIN)

# Shields always go to MELEE_OFF
entity.equipment.equip(shield, WeaponSlot.MELEE_OFF)

# Armor auto-determined from body_part
entity.equipment.equip(leather_armor)  # Goes to BodyPart.BODY

# equip() updates source_entity_uuid on item and all its ModifiableValues
```

---

## Section 14: Test Setup & Utilities

### Test Structure Pattern

```python
class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def check(self, condition: bool, message: str) -> bool:
        if condition:
            self.passed += 1
            print(f"    ✓ {message}")
            return True
        else:
            self.failed += 1
            self.failures.append(message)
            print(f"    ✗ FAILED: {message}")
            return False

    def summary(self) -> bool:
        print(f"\n  Results: {self.passed}/{self.passed + self.failed} passed")
        return self.failed == 0


def test_something():
    print("\n=== Test: Something ===")
    result = TestResult()
    from dnd.utils import reset_combat_state
    reset_combat_state()

    goblin = create_goblin(name="Goblin", position=(0, 0))
    Entity.update_all_entities_senses()

    result.check(goblin.get_hp() > 0, f"Goblin has HP (got {goblin.get_hp()})")
    return result.summary()
```

### Reset State

**Always start tests with a clean slate:**

```python
from dnd.utils import reset_combat_state
reset_combat_state()  # Clears EventQueue, Entity registries, GridMap
```

### Update Senses (MANDATORY)

After creating entities, update their senses so they can see each other:

```python
Entity.update_all_entities_senses()  # Must call after creating entities!
```

This populates:
- `entity.senses.visible` - currently visible cells
- `entity.senses.paths` - paths to reachable cells
- `entity.senses.entities` - visible entities

### Accessing Entity Properties

**HP:**
```python
hp = entity.get_hp()  # Returns int
```

**AC:**
```python
ac = entity.ac_bonus().normalized_score              # Basic AC
ac_bonus = entity.ac_bonus(attacker.uuid)             # With target context
```

**Attack Bonus:**
```python
from dnd.core.events import WeaponSlot
attack_bonus = entity.attack_bonus(WeaponSlot.MELEE_MAIN)
bonus = attack_bonus.normalized_score
```

**Ability Scores:**
```python
str_mod = entity.ability_scores.strength.modifier  # Returns int, NOT ModifiableValue
dex_mod = entity.ability_scores.get_modifier_from_name("dexterity")
str_score = entity.ability_scores.strength.ability_score.normalized_score
```

**Movement:**
```python
movement = entity.action_economy.movement.normalized_score  # Current after modifiers
```

**Action Economy:**
```python
actions = entity.action_economy.actions.normalized_score
bonus_actions = entity.action_economy.bonus_actions.normalized_score
reactions = entity.action_economy.reactions.normalized_score
entity.action_economy.reset_all_costs()  # Reset for new turn
```

**Weapons:**
```python
weapon = entity.equipment.weapon_melee_main   # Main melee
off_hand = entity.equipment.weapon_melee_off  # Off-hand (Weapon or Shield)
weapon = entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)  # By slot
```

### Cross-Entity Targeting

```python
def get_defense_modifiers(defender: Entity, attacker: Entity):
    defender.set_target_entity(attacker.uuid)
    attacker.set_target_entity(defender.uuid)

    attack_bonus = attacker.attack_bonus(WeaponSlot.MELEE_MAIN, defender.uuid)
    ac_bonus = defender.ac_bonus(attacker.uuid)
    attack_bonus.set_from_target(ac_bonus)  # Propagate to_target modifiers

    defender.clear_target_entity()
    attacker.clear_target_entity()
    return attack_bonus
```

### Creating and Executing Actions

```python
from dnd.actions import Attack, Move, Dash, Dodge, Disengage, StandUp, DropProne
from dnd.core.events import WeaponSlot

# Attack
attack = Attack(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid,
                weapon_slot=WeaponSlot.MELEE_MAIN, name="Scimitar Attack")
event = attack.apply()

# Move
move = Move(source_entity_uuid=entity.uuid, end_position=(5, 3))
event = move.apply()

# Self-actions (apply conditions with 1-round duration)
dash = Dash(source_entity_uuid=entity.uuid)
dash.apply()
assert "Dashing" in entity.active_conditions

# Prone
drop = DropProne(source_entity_uuid=entity.uuid)
drop.apply()
stand = StandUp(source_entity_uuid=entity.uuid)
stand.apply()
```

### Working with Conditions

```python
from dnd.conditions import Blinded, Dashing
from dnd.core.base_conditions import DurationType

# Apply
blinded = Blinded(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
target.add_condition(blinded)

# Check
if "Blinded" in entity.active_conditions:
    blinded = entity.active_conditions["Blinded"]

# Remove
entity.remove_condition("Blinded")

# Set duration
condition = Dashing(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
condition.duration.duration_type = DurationType.ROUNDS
condition.duration.duration = 1
entity.add_condition(condition)
```

### Working with Encounters

```python
from uuid import uuid4
from dnd.encounter import Encounter
from dnd.controller import PassController, HumanController, MeleeAIController

encounter = Encounter(name="Test Encounter", source_entity_uuid=uuid4())
encounter.add_combatant(goblin, PassController(source_entity_uuid=goblin.uuid))
encounter.add_combatant(skeleton, PassController(source_entity_uuid=skeleton.uuid))

encounter.roll_initiative()
encounter.start_encounter()
encounter.start_turn()
# ... actions ...
encounter.next_turn()  # end_turn + start_turn for next combatant
```

**Controllers**: `HumanController`/`ClaudeController` (exit turn loop for API control), `MeleeAIController` (auto-attacks), `PassController` (ends turn immediately)

### Zone Spell Testing

```python
# Setup arena with explicit tiles
reset_combat_state()
grid = get_map()
for x in range(20):
    for y in range(20):
        grid.set_tile(x, y, walkable=True, name="Floor")

caster = create_skeleton(name="Caster", position=(0, 0))
target = create_skeleton(name="Target", position=(8, 5))
Entity.update_all_entities_senses()

# Cast spell
spell = SpikeGrowth(source_entity_uuid=caster.uuid, end_position=(5, 5))
result = spell.apply()

# Verify
assert has_condition(caster, "Concentrating")
assert has_condition(caster, "Spike Growth Zone")
center_tile = grid.get_tile(5, 5)
assert center_tile.walking_cost.normalized_score == 2  # Difficult terrain

# Test entry via movement
hp_before = target.get_hp()
move = Move(source_entity_uuid=target.uuid, end_position=(5, 5))
move.apply()
assert target.get_hp() < hp_before

# Test cleanup via concentration break
deal_damage_to(caster, 999, DamageType.FORCE, caster.uuid)
assert not has_condition(caster, "Concentrating")
assert center_tile.walking_cost.normalized_score == 1  # Restored
```

### Faction System

```python
hero1 = create_skeleton(name="Hero 1", position=(0, 0), faction="heroes")
enemy1 = create_skeleton(name="Enemy 1", position=(5, 0), faction="monsters")

hero1.is_ally(hero2)    # True - same faction
hero1.is_enemy(enemy1)  # True - different faction
enemies = hero1.get_visible_enemies()  # Dict[UUID, Tuple[int, int]]
allies = hero1.get_visible_allies()

# Actions filtered by faction
actions = hero1.get_available_actions(target_filter="enemies")
```

### Test Utilities (`dnd.utils`)

```python
from dnd.utils import (
    reset_combat_state, setup_combat_arena, run_turn_until_end,
    get_hp, get_max_hp, set_hp, heal_entity, deal_damage_to,
    force_attack_hit, force_attack_miss, force_attack_crit, remove_attack_modifier,
    get_position, move_entity,
    has_condition, count_conditions,
    print_combat_state,
)

# Force deterministic outcomes
mod_uuid = force_attack_hit(entity)     # +100 attack bonus
mod_uuid = force_attack_miss(entity)    # -100 attack penalty
mod_uuid = force_attack_crit(entity)    # AUTOCRIT modifier
remove_attack_modifier(entity, mod_uuid)  # Cleanup

# Deal damage (fires TakeDamageEvent - triggers handlers!)
deal_damage_to(entity, 20, DamageType.SLASHING, source_uuid)

# Set HP directly
set_hp(entity, 5)

# Quick combat setup
encounter = setup_combat_arena(entity_a, entity_b)  # Returns Encounter, NOT started
encounter.start_encounter()
```

**CRITICAL**: `deal_damage_to()` fires `TakeDamageEvent` via `entity.receive_damage()`, triggering handlers (RelentlessRage, Concentration checks, etc.). It's not just setting HP.

### Multi-Entity Encounters

```python
reset_combat_state()
hero1 = create_skeleton(name="Hero 1", position=(0, 0), faction="heroes")
hero2 = create_skeleton(name="Hero 2", position=(1, 0), faction="heroes")
enemy1 = create_skeleton(name="Enemy 1", position=(5, 0), faction="monsters")
enemy2 = create_skeleton(name="Enemy 2", position=(5, 1), faction="monsters")
Entity.update_all_entities_senses()

encounter = Encounter(name="Team Battle", source_entity_uuid=uuid4())
for entity in [hero1, hero2, enemy1, enemy2]:
    encounter.add_combatant(entity, PassController(source_entity_uuid=entity.uuid))

encounter.roll_initiative()
encounter.start_encounter()
encounter.start_turn()
# Encounter ends when only one faction has survivors
```

---

## Section 15: Common Pitfalls

### Critical Mistakes

| Mistake | Fix |
|---------|-----|
| Missing `parent_event` in child events | **Always pass parent_event** - broken combat logs = missing parent_event |
| Calling `EventQueue.add_event_handler()` AND `entity.add_event_handler()` | Only call `entity.add_event_handler()` - it auto-registers |
| Registering rage maintenance at `TURN_START/EFFECT` | Use `TURN_START/EXECUTION` - markers expire at EFFECT |
| Calling `condition.remove()` directly | Use `Entity.remove_condition(name)` - BaseBlock drives the full cleanup tree |
| `AbilityScoresConfig(strength=14)` | `AbilityScoresConfig(strength=AbilityConfig(ability_score=14))` |
| `create_goblin("Name", ...)` | `create_goblin(name="Name", ...)` - keyword args required |
| `entity.ability_scores.strength.modifier.value` | `entity.ability_scores.strength.modifier` returns int directly |
| `entity.health.current_hit_points` | `entity.get_hp()` |
| Importing WeaponSlot from equipment | `from dnd.core.events import WeaponSlot` |
| Manual registry clearing | `reset_combat_state()` from `dnd.utils` |
| Forgetting `Entity.update_all_entities_senses()` | Call after ALL entities created, before any targeting |

### Circular Imports

**Never use late imports, TYPE_CHECKING, or import-inside-function.** Dependencies flow DOWN:

```
Entity (high-level)
   ↓
Blocks (Senses, Equipment, Health)
   ↓
Primitives (ModifiableValue, Modifiers)
   ↓
Base classes (BaseObject, BaseBlock)
```

If you need to import "up", the method is in the wrong place. Move it to the higher-level class or pass data as parameters.

### Event Handler Phase Selection

| Phase | When to Use |
|-------|-------------|
| `EXECUTION` | Modify before roll (Protection), track state (HasAttacked) |
| `EFFECT` | After roll (Indomitable reroll, GWF dice manipulation, OA on step) |
| `COMPLETION` | **Don't use** - handlers never fire at this phase |

### Cross-Entity Targeting Sequence

```python
attacker.set_target_entity(target.uuid)
target.set_target_entity(attacker.uuid)

attack_bonus = attacker.attack_bonus(slot, target.uuid)
ac = target.ac_bonus(attacker.uuid)
attack_bonus.set_from_target(ac)  # Propagate defensive modifiers

# ... do attack logic ...

attack_bonus.reset_from_target()
attacker.clear_target_entity()
target.clear_target_entity()
```

---

## Section 16: Fighter / Barbarian Feature Reference

### Fighter (Champion) - `dnd/classes/fighter.py`

| Level | Feature | Type | Notes |
|-------|---------|------|-------|
| 1 | Fighting Styles | Condition | Archery, Defense, Dueling, GWF, Protection, TWF |
| 1 | Second Wind | Resource + Action | 1d10+level heal, bonus action, short rest |
| 2 | Action Surge | Resource + Action | +1 action, short rest |
| 3 | Improved Critical | Condition | Crit on 19-20 |
| 5 | Extra Attack | Feature + Handler | 1 extra attack (2 at L11, 3 at L20) |
| 9 | Indomitable | Resource + Handler | Reroll failed save, long rest |
| 15 | Superior Critical | Condition | Crit on 18-20 |
| 18 | Survivor | Handler | Heal 5+CON at turn start when HP ≤ 50% |

### Barbarian (Berserker) - `dnd/classes/barbarian.py`, `dnd/classes/rage.py`

| Level | Feature | Type | Notes |
|-------|---------|------|-------|
| 1 | Rage | Resource + Action | STR adv, bonus damage, B/P/S resistance |
| 1 | Unarmored Defense | Condition | AC = 10 + DEX + CON (contextual) |
| 2 | Reckless Attack | Action | Adv on melee attacks, attackers have adv, 1 round |
| 2 | Danger Sense | Condition | Adv on DEX saves (contextual, disabled when blind/deaf) |
| 3 | Frenzy | Action | Bonus action melee attacks while raging |
| 5 | Extra Attack | Feature + Handler | Same as Fighter L5 |
| 5 | Fast Movement | Condition | +10 speed (contextual, not in heavy armor) |
| 6 | Mindless Rage | Condition | Immune to charm/frighten while raging |
| 7 | Feral Instinct | Condition | Advantage on initiative |
| 9 | Brutal Critical | Condition | +1/2/3 extra crit dice (L9/13/17) |
| 10 | Intimidating Presence | Action | WIS save or Frightened |
| 11 | Relentless Rage | Handler | CON save to drop to 1 HP instead of 0 |
| 14 | Retaliation | Handler | Reaction melee attack when hit |
| 15 | Persistent Rage | Marker | Rage doesn't end from inactivity |
| 18 | Indomitable Might | Handler | STR checks can't be below STR score |
| 20 | Primal Champion | Condition | +4 STR and CON |

Use these as reference patterns for implementing similar features.

---

## Section 17: Items System — UsableItem, Equip Hooks, Inventory Actions

The items system is fully implemented. This section covers how to create new items using the existing patterns.

### 17a. Item Class Hierarchy

```
BaseItem (dnd/blocks/base_item.py)
│   Foundation: location tracking, lifecycle hooks, health/damage, stacking
│
├── EquippableItem — Gear occupying equipment slots
│   Hook: _on_equip(slot, entity_uuid) / _on_unequip(slot, entity_uuid)
│   Subclasses: Weapon, Armor (BodyArmor, Helmet, Boots, etc.), Shield
│
└── UsableItem — Items providing actions via get_use_actions()
    Charges: charges (-1=unlimited), consume_charge(), is_consumable
    Patterns: use_action_templates field OR override get_use_actions()
```

**Key rule**: An item is NEVER both equippable AND usable. If an equipped item needs to grant actions, it does so through `_on_equip` (direct action registration or condition).

### 17b. Creating a UsableItem — Template Pattern (Simplest)

For items where the action name doesn't change with state:

```python
from dnd.blocks.base_item import UsableItem

class HealingPotion(UsableItem):
    name: str = "Healing Potion"
    is_consumable: bool = True  # Destroyed after use
    is_pickable: bool = True
    charges: int = 1
    max_charges: int = 1
    stack_id: Optional[str] = "healing_potion"  # Same stack_id = merge in inventory
    max_stack: int = 10

# Factory function
def create_healing_potion(source_uuid: UUID) -> HealingPotion:
    return HealingPotion(
        source_entity_uuid=source_uuid,
        use_action_templates=[
            DrinkPotionAction(
                source_entity_uuid=source_uuid,
                name="Drink Potion",
                template=True,
                target_type=TargetType.SELF,
                costs=[Cost(name="Use Item", cost_type="actions", cost=1)],
            )
        ],
    )
```

`get_use_actions()` default implementation:
1. Returns `[]` if `charges == 0`
2. Returns `model_copy()` of each template with `source_entity_uuid` and `source_item_uuid` injected

### 17c. Creating a UsableItem — Override Pattern (State-Dependent)

For items where different states surface different action classes:

```python
class Door(UsableItem):
    is_pickable: bool = False  # Environment object
    is_open: bool = False
    blocks_movement: bool = True
    blocks_vision_field: bool = True

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        if self.charges == 0:
            return []
        if self.is_open:
            return [CloseDoorAction(
                source_entity_uuid=user_entity_uuid,
                source_item_uuid=self.uuid, template=True,
            )]
        return [OpenDoorAction(
            source_entity_uuid=user_entity_uuid,
            source_item_uuid=self.uuid, template=True,
        )]
```

### 17d. SpellScroll Pattern — Wrapping Existing Spells

SpellScroll (`dnd/items/test_items.py`) wraps any SpellAction as a consumable item:

```python
class SpellScroll(UsableItem):
    is_consumable: bool = True
    is_pickable: bool = True
    scroll_cast_level: int = 0

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        if self.charges == 0:
            return []
        result = []
        for template in self.use_action_templates:
            if isinstance(template, SpellAction):
                variant = template._create_variant(
                    cast_at_level=self.scroll_cast_level,
                    costs=[Cost(name="Use Item", cost_type="actions", cost=1)],
                    source_item_uuid=self.uuid,
                )
                variant.source_entity_uuid = user_entity_uuid
                result.append(variant)
            else:
                # Non-spell actions
                action = template.model_copy(deep=True, update={...})
                result.append(action)
        return result
```

Key: No spell slot consumed — costs are `[Cost("actions", 1)]` only. Spell level set by `scroll_cast_level`.

### 17e. Variable Charge Costs — Wand Pattern

Wands use `charge_cost` on the action template:

```python
def create_wand_of_fire(source_uuid: UUID) -> SpellScroll:
    return SpellScroll(
        source_entity_uuid=source_uuid,
        name="Wand of Fire",
        is_consumable=False,  # Not destroyed when depleted
        charges=7, max_charges=7,
        use_action_templates=[
            BurningHands(source_entity_uuid=source_uuid, template=True,
                         charge_cost=1),   # 1 charge
            Fireball(source_entity_uuid=source_uuid, template=True,
                     charge_cost=3),       # 3 charges
        ],
    )
```

`execute_use_action()` reads `charge_cost` from the template and passes to `consume_charge()`.

### 17f. WeaponCoat Pattern — Conditions on Items

WeaponCoat applies a condition to an equipped weapon:

```python
class WeaponCoatCondition(BaseCondition):
    """Applied to the WEAPON (not the entity). Adds extra damage dice."""
    weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN
    damage_dice: int = 6
    damage_type: DamageType = DamageType.FIRE

    def _apply(self, declaration_event):
        weapon = BaseBlock.get(self.target_entity_uuid)  # target is a weapon
        weapon.extra_damage_dices.append(self.damage_dice)
        weapon.extra_damage_type.append(self.damage_type)
        # ... return modifiers tuple
```

Three coat variants exist: permanent, concentration-based, and timed duration.

### 17g. EquippableItem Hooks — Three Approaches

All hooks receive `(slot: EquipmentSlot, entity_uuid: UUID)`:

**Approach 1 — Direct modifiers** (simplest, static bonuses):
```python
class DefenderSword(Weapon):
    _ac_modifier_uuid: Optional[UUID] = None

    def _on_equip(self, slot, entity_uuid):
        entity = Entity.get(entity_uuid)
        self._ac_modifier_uuid = entity.equipment.ac_bonus.self_static.add_value_modifier(
            NumericalModifier(name="Defender AC", value=1, ...)
        )

    def _on_unequip(self, slot, entity_uuid):
        entity = Entity.get(entity_uuid)
        if self._ac_modifier_uuid:
            entity.equipment.ac_bonus.self_static.remove_modifier(self._ac_modifier_uuid)
```

**Approach 2 — Direct action registration** (for granted actions):
```python
class WandOfFireBolt(EquippableItem):
    def _on_equip(self, slot, entity_uuid):
        entity = Entity.get(entity_uuid)
        entity.register_action(FireBolt(source_entity_uuid=entity.uuid, template=True, name="Fire Bolt (Wand)"))

    def _on_unequip(self, slot, entity_uuid):
        entity = Entity.get(entity_uuid)
        entity.unregister_action("Fire Bolt (Wand)")
```

**Approach 3 — Condition pattern** (complex effects, many modifiers):
```python
class CloakOfProtection(EquippableItem):
    def _on_equip(self, slot, entity_uuid):
        entity = Entity.get(entity_uuid)
        entity.add_condition(CloakOfProtectionCondition(
            source_entity_uuid=entity_uuid, target_entity_uuid=entity_uuid))

    def _on_unequip(self, slot, entity_uuid):
        entity = Entity.get(entity_uuid)
        if "CloakOfProtectionCondition" in entity.active_conditions:
            entity.remove_condition("CloakOfProtectionCondition")
```

### 17h. When Equip Hooks Are NOT Needed

- **Weapon attack/damage bonus**: Use `weapon.attack_bonus` / `weapon.damage_bonus` at creation (`base_value=1` for +1). Automatic Level 1 scoping.
- **Standard armor AC**: `BodyArmor.ac` already consumed by `Entity.ac_bonus()`.
- **Standard shield AC**: `Shield.ac_bonus` already consumed by `Entity.ac_bonus()`.

### 17i. Stacking System

Items merge in inventory when they share the same `stack_id`:

```python
# Same stack_id → merge when looted
scroll1 = create_scroll_of_fireball(entity.uuid)  # stack_id="scroll_fireball_3"
scroll2 = create_scroll_of_fireball(entity.uuid)  # stack_id="scroll_fireball_3"
entity.loot_item(scroll1)  # stack_count=1
entity.loot_item(scroll2)  # merged → stack_count=2, scroll2 unregistered
```

Stack consumption (`consume_charge()`):
- `stack_count > 1`: decrement `stack_count`, reset `charges = max_charges`
- `stack_count == 1`: destroy item (if `is_consumable`)

Action deduplication: 3 stacked scrolls show 1 "Fireball" action, display name includes "x3".

### 17j. Environment Objects

Non-pickable UsableItems placed on GridMap:

```python
machine_gun = SpellScroll(
    name="Arcane Machine Gun",
    is_pickable=False,  # Environment object
    charges=-1,         # Unlimited
    use_action_templates=[MagicMissile(...)],
)
gridmap.place_object(machine_gun.uuid, (5, 5))
```

Discovered via `senses.objects` → `isinstance(obj, UsableItem)` → within 5ft → `get_use_actions()`.

### 17k. Three-Source Action Discovery

`Entity.get_available_actions()` gathers use actions from three sources:

| Source | Method | Items |
|--------|--------|-------|
| 1. Registered | `entity.registered_actions` | Static templates (Move, Attack, etc.) |
| 2. Inventory | `entity.inventory.get_all_use_actions(uuid)` | Potions, scrolls, wands in inventory |
| 3. Environment | `senses.objects` filtered to UsableItem, ≤5ft | Doors, levers, chests, cannons on floor |

All three sources merge into `AvailableActionsResult`. Use actions have:
- `is_item_use=True` on `AvailableActionInfo`
- `source_item_uuid` pointing to the providing item
- `item_stack_count` for display (inventory items only)

`execute_by_index()` auto-routes `is_item_use` actions to `execute_use_action()`.

### 17l. Test Files Reference

| File | Tests | Coverage |
|------|-------|---------|
| `examples/test_usable_items.py` | 19 | Doors (2 patterns), lever, chest, campfire, charges, vision/movement blocking |
| `examples/test_inventory_use_actions.py` | 65+ | Spell scrolls (all target types), potions, wands, weapon coats (3 variants), environment objects, prerequisites |
| `examples/test_items_equip_hooks.py` | 15 | DefenderSword, CloakOfProtection, Flaming sword, location tracking, reparenting |
| `examples/test_items_lifecycle_hooks.py` | 22 | OilBarrel, CursedGem, AuraStone, HealingHerb, hook parameters |
| `examples/test_stackable_items.py` | 15 | Merge, consumption, deduplication, limits, weight, non-stackable |

---

## Section 18: Test Setup Patterns and Encounter Lifecycle

This section documents the correct patterns for setting up tests, managing encounter turns, and working with spatial systems. Getting these wrong causes silent failures, confusing state, or `ValueError` crashes.

### 18a. Standard Test Setup Boilerplate

Every test MUST start with a clean state. Here is the canonical pattern:

```python
from dnd.utils import reset_combat_state
from dnd.entity import Entity
from dnd.core.gridmap import get_map
from dnd.monsters.bestiary import create_skeleton
from dnd.actions_functional import setup_standard_actions

def test_my_feature():
    print("\n=== Test: My Feature ===")
    result = TestResult()

    # 1. ALWAYS first: reset all global state
    reset_combat_state()

    # 2. Create grid (bright tiles by default)
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    # 3. Create entities using factory functions (keyword args!)
    attacker = create_skeleton(name="Attacker", position=(3, 3), faction="heroes")
    target = create_skeleton(name="Target", position=(4, 3), faction="monsters")

    # 4. MANDATORY: Update senses after ALL entities are created
    Entity.update_all_entities_senses()

    # 5. Now test logic...
    result.check(attacker.get_hp() > 0, "Attacker has HP")
    return result.summary()
```

**Why each step matters:**
- `reset_combat_state()` clears EventQueue, Entity registries, GridMap, and BaseObject registry. Without this, state from previous tests leaks.
- `create_rectangle()` creates tiles. Without tiles, entities cannot see each other and pathfinding returns empty.
- `Entity.update_all_entities_senses()` populates `senses.entities`, `senses.visible`, and `senses.paths`. Without this, targeting fails silently (entities report no valid targets).

### 18b. Encounter Turn Lifecycle (CRITICAL)

The correct sequence for setting up and running encounters:

```python
from uuid import uuid4
from dnd.encounter import Encounter
from dnd.controller import HumanController, PassController

# --- Setup ---
encounter = Encounter(name="Test", source_entity_uuid=uuid4())
encounter.add_combatant(entity_a, PassController(source_entity_uuid=entity_a.uuid))
encounter.add_combatant(entity_b, PassController(source_entity_uuid=entity_b.uuid))
encounter.roll_initiative()

# --- Start ---
encounter.start_encounter()  # Sets state to ACTIVE, fires round start
                             # Does NOT start a turn!
encounter.start_turn()       # Starts first entity's turn
                             # MUST call after start_encounter()
```

**Advancing turns:**

```python
# CORRECT: next_turn() handles everything
encounter.next_turn()  # Internally: end_turn() + advance index + start_turn()

# WRONG: manual end + next + start causes double start_turn
encounter.end_turn()      # Ends current turn
encounter.next_turn()     # This calls end_turn() AGAIN (harmless) then start_turn()
encounter.start_turn()    # CRASH: "Turn already in progress, call end_turn first"
```

**Key rule**: `next_turn()` does three things atomically:
1. Calls `end_turn()` if turn is in progress
2. Advances `current_turn_index` (handles round rollover)
3. Calls `start_turn()` for the new entity

Never call `end_turn()` then `start_turn()` manually when `next_turn()` exists.

**Getting the current entity:**

```python
current = encounter.get_current_entity()    # Returns Optional[Entity]
combatant = encounter.get_current_combatant()  # Returns Optional[CombatantState]

# There is no encounter.current_entity_uuid attribute - use get_current_entity()
```

**Ensuring a specific entity's turn:**

```python
encounter.start_turn()
current = encounter.get_current_entity()
if current is None or current.uuid != desired_entity.uuid:
    encounter.next_turn()  # Advances to next entity, auto starts their turn
```

**Method behaviors:**

| Method | Precondition | On Bad State |
|--------|-------------|--------------|
| `start_encounter()` | State must be `NOT_STARTED` | `ValueError` |
| `start_turn()` | No turn in progress | `ValueError` if turn already in progress |
| `end_turn()` | Turn in progress | Returns `None` silently if no turn |
| `next_turn()` | Encounter is ACTIVE | Calls `end_turn()` if needed, then advances |

### 18c. GridMap Light Source API

Light sources illuminate tiles using FOV (blocked by walls).

```python
grid = get_map()
light_uuid = grid.add_light_source(
    position=(5, 5),
    bright_radius_feet=20,
    dim_radius_feet=20,
    anchor_uuid=entity.uuid  # Optional: light follows this entity
)
```

**CRITICAL: `dim_radius_feet` is ADDITIVE on top of `bright_radius_feet`.** The total illuminated range is `bright + dim`, not just `dim`.

| bright_radius_feet | dim_radius_feet | Bright Range | Total Range |
|-------------------|-----------------|-------------|-------------|
| 20 | 20 | 20ft (4 tiles) | 40ft (8 tiles) |
| 20 | 40 | 20ft (4 tiles) | 60ft (12 tiles) |
| 30 | 10 | 30ft (6 tiles) | 40ft (8 tiles) |

**Distance conversion**: 1 tile = 5 feet. So `bright_radius_feet=20` illuminates tiles within 4 tiles of the source.

Light uses FOV computation, so walls block light propagation. The `anchor_uuid` parameter makes the light source follow an entity when it moves.

### 18d. Dark Tile Creation

`GridMap.create_rectangle()` creates `BRIGHT_LIGHT` tiles by default (outdoor/well-lit). For dungeon scenarios or lighting tests, create dark tiles manually:

```python
from dnd.core.base_tiles import dark_floor_factory
from dnd.core.gridmap import get_map

grid = get_map()
for x in range(width):
    for y in range(height):
        tile = dark_floor_factory((x, y))
        grid.set_tile(x, y, tile=tile, fire_event=False)
```

**Helper pattern** (copy into test files that need it):

```python
def create_dark_grid(width: int, height: int) -> None:
    """Create an all-dark tile grid."""
    grid = get_map()
    for x in range(width):
        for y in range(height):
            tile = dark_floor_factory((x, y))
            grid.set_tile(x, y, tile=tile, fire_event=False)
```

`dark_floor_factory()` creates a walkable floor tile with `default_light=LightLevel.DARKNESS`. Without a light source, entities cannot see tiles or other entities in darkness (unless they have darkvision or truesight).

### 18e. Melee vs Ranged Range for Attack Tests

When testing attacks, entity placement matters:

| Weapon Type | Range | Required Spacing |
|-------------|-------|-----------------|
| Melee (most) | 5ft reach | 1 tile apart (adjacent) |
| Melee (reach) | 10ft reach | 1-2 tiles apart |
| Ranged (shortbow) | 80/320ft | Within 16/64 tiles |
| Ranged (longbow) | 150/600ft | Within 30/120 tiles |

**Example**: Skeleton has a Shortsword with `Range(type=RangeType.REACH, normal=5)`. For melee tests, place attacker and target 1 tile apart:

```python
attacker = create_skeleton(name="Attacker", position=(3, 3))
target = create_skeleton(name="Target", position=(4, 3))  # 1 tile = 5ft
```

If entities are too far apart, `get_available_actions()` returns no valid targets for melee attacks, and `Attack.apply()` fails validation silently.

### 18f. Reactive Senses Pipeline

The senses system updates incrementally via events. You do NOT need to call `Entity.update_all_entities_senses()` for these changes --- they propagate automatically:

| Change | Mechanism | Automatic? |
|--------|-----------|-----------|
| Hidden condition applied | `set_stealth_dc()` fires `SPATIAL_PERCEIVABILITY_CHANGED` | Yes |
| Invisible condition applied | `set_invisible()` fires `SPATIAL_PERCEIVABILITY_CHANGED` | Yes |
| Light source added/removed | `grid.add_light_source()` fires batch `SPATIAL_LIGHT_CHANGED` | Yes |
| Tile obscurement/illumination | `tile.add_obscurement()`/`add_illumination()` fires `SPATIAL_LIGHT_CHANGED` | Yes |
| Entity enters/leaves cell | GridMap fires `SPATIAL_ENTITY_ENTERED`/`SPATIAL_ENTITY_LEFT` | Yes |
| Door opened/closed | `BaseItem._notify_blocking_changed()` fires `SPATIAL_OBJECT_CHANGED` | Yes |

**Testing reactive updates**: To verify the reactive pipeline works, explicitly do NOT call `update_all_entities_senses()` after the change, then check that senses updated:

```python
# Apply Hidden - should reactively update observers
target.add_condition(Hidden(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))

# Do NOT call Entity.update_all_entities_senses() here!

# Verify observer can no longer see target (if stealth DC > passive perception)
result.check(
    target.uuid not in observer.senses.entities,
    "Observer lost sight of hidden target via reactive pipeline"
)
```

**When you MUST call `update_all_entities_senses()` manually:**

| Change | Why Manual Required |
|--------|-------------------|
| Sense mode added (darkvision, truesight) | No event exists for sense mode changes |
| After entity creation | New entity needs initial senses populated |
| After grid topology changes (walls added/removed) | FOV geometry changed fundamentally |

### 18g. setup_combat_arena Shortcut

For simple two-entity tests, use the shortcut:

```python
from dnd.utils import setup_combat_arena

encounter = setup_combat_arena(entity_a, entity_b)
# This does: create Encounter, add both as HumanController, roll initiative
# Does NOT start the encounter!
encounter.start_encounter()
encounter.start_turn()
```

**For multi-entity or custom controller scenarios**, build the encounter manually as shown in Section 18b.

### 18h. Common Test Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Forgot `reset_combat_state()` | State from previous test leaks, entities appear in wrong places | Always call first |
| Forgot `create_rectangle()` | Entities can't see each other, no paths, targeting returns empty | Create grid before entities |
| Forgot `Entity.update_all_entities_senses()` | `senses.entities` is empty, all attacks fail validation | Call after ALL entities created |
| Called `start_turn()` after `next_turn()` | `ValueError: Turn already in progress` | `next_turn()` already calls `start_turn()` |
| Called `end_turn()` then `next_turn()` then `start_turn()` | `ValueError: Turn already in progress` | Just call `next_turn()` |
| Placed entities too far apart for melee | Attack returns no valid targets | Place 1 tile apart for 5ft reach |
| Created dark grid, forgot light source | Entities can't see each other in darkness | Add light source or use bright grid |
| Used `encounter.current_entity_uuid` | `AttributeError` | Use `encounter.get_current_entity()` |
| Called `update_all_entities_senses()` expecting paths to update after terrain change mid-turn | Paths not updated (only `_paths_dirty` flag set) | Paths recompute at turn start or movement end, not mid-turn |
