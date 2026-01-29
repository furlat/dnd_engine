# Implementation Guide

How to implement features using the D&D Engine's patterns. Read this before writing new conditions, actions, or event handlers.

---

## Working With This Codebase

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

## Core Concepts Quick Reference

### Entity Composition

```
Entity
├── ability_scores: AbilityScores     # STR, DEX, CON, INT, WIS, CHA
├── skill_set: SkillSet               # 18 D&D skills
├── saving_throws: SavingThrowSet     # 6 saves
├── health: Health                    # HP, temp HP, damage
├── equipment: Equipment              # Weapons, armor, AC
├── action_economy: ActionEconomy     # actions, bonus_actions, reactions, movement
├── senses: Senses                    # position, FOV, paths
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
- `COMPLETION`: Finished, handlers closed

### Condition Lifecycle

```
1. Create: condition = MyCondition(source_entity_uuid=..., target_entity_uuid=...)
2. Apply:  target.add_condition(condition) → calls condition.apply()
3. Effect: Modifiers added to appropriate channels
4. Remove: target.remove_condition("MyCondition") → modifiers auto-cleaned
```

---

## How to Implement a Condition

### Basic Structure

```python
class MyCondition(BaseCondition):
    name: str = "MyCondition"
    description: str = "Description here"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        Optional[Event]           # completion event
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        # Add modifiers...
        mod_uuid = target.equipment.attack_bonus.self_static.add_advantage_modifier(...)
        outs.append((target.equipment.attack_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return outs, [], [], effect_event
```

### Modifier Placement Guide

| Effect Type | Channel | Example |
|-------------|---------|---------|
| Affects own rolls | `self_static` | Poisoned: disadvantage on attacks |
| Affects own rolls conditionally | `self_contextual` | Frightened: only when frightener visible |
| Affects attackers | `to_target_static` | Blinded: attackers have advantage |
| Affects attackers conditionally | `to_target_contextual` | Prone: advantage if ≤5ft, disadvantage if >5ft |

### Modifier Types

| Type | Values | Used For |
|------|--------|----------|
| `NumericalModifier` | int | Bonuses, penalties |
| `AdvantageModifier` | ADVANTAGE (+1), DISADVANTAGE (-1) | Attack rolls, checks |
| `CriticalModifier` | AUTOCRIT, NOCRIT | Paralyzed auto-crit |
| `AutoHitModifier` | AUTOHIT, AUTOMISS | Charmed can't attack charmer |

Each has a `Contextual*` variant taking a callable that returns the modifier or None.

### Contextual Modifier Example

```python
def my_contextual_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    entity = Entity.get(source_entity_uuid)
    if entity and meets_condition(entity):
        return NumericalModifier.create(source_entity_uuid, "MyBonus", value=2)
    return None

# In condition _apply():
mod = ContextualNumericalModifier(
    name="MyBonus",
    source_entity_uuid=self.target_entity_uuid,
    target_entity_uuid=self.target_entity_uuid,
    callable=my_contextual_check
)
mod_uuid = target.equipment.ac_bonus.self_contextual.add_value_modifier(mod)
```

### Sub-conditions Pattern (Same Entity)

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

### External Conditions Pattern (Cross-Entity)

Use `external_conditions` when Entity A causes a condition on Entity B, and removing A's condition should clean up B's.

**Use cases:**
- Concentration spells (caster's Concentrating → target's spell effect)
- Grappling (grappler's GrapplingCondition → target's Grappled)
- Auras (paladin's AuraCondition → allies' AuraBonus)
- Any causal relationship between entities

```python
# BaseCondition has:
external_conditions: List[Tuple[UUID, UUID]] = []  # (target_entity_uuid, condition_uuid)

# Methods:
condition.add_external_condition(target_entity_uuid, effect_condition_uuid)
condition.remove_external_conditions()  # Called automatically on removal
```

**Example - Concentration Spell:**
```python
# Structure:
# Caster: Concentrating → external_conditions → Target: SpellEffect → sub_conditions → Paralyzed

# In spell's _apply():
# 1. Apply spell-specific effect to target (Paralyzed is its sub-condition)
spell_effect = HoldPersonEffect(source=caster.uuid, target=target.uuid)
target.add_condition(spell_effect)

# 2. Apply Concentrating to caster
concentration = Concentrating(source=caster.uuid, target=caster.uuid, spell_name="Hold Person")
caster.add_condition(concentration)

# 3. Link via external_conditions
concentration.add_external_condition(target.uuid, spell_effect.uuid)

# Cleanup chain when concentration breaks:
# Concentrating.remove() → remove_external_conditions() → HoldPersonEffect.remove() → remove_sub_conditions() → Paralyzed.remove()
```

**Benefits of spell-specific effect conditions:**
- **Spell-specific immunity**: Target can be immune to "Hold Person" but not all paralysis
- **Dispel Magic**: Can target the spell condition directly
- **Identification**: Know "this paralysis is from Hold Person" vs other sources

---

## How to Implement an Action

### Template-Based Actions

Actions are registered as templates on entities with `template=True`:

```python
class SecondWind(BaseAction):
    name: str = "Second Wind"
    target_type: TargetType = TargetType.SELF
    costs: List[Cost] = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
        ...

    def _apply(self, execution_event):
        # Execute the action, return EFFECT → COMPLETION
        ...

    def _apply_costs(self, completion_event):
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)
```

### TargetType Enum

| Type | Used For |
|------|----------|
| `SELF` | Dash, Dodge, Disengage, Second Wind |
| `ENTITY` | Attack, Extra Attack, Shove |
| `POSITION` | Move, Jump |

### Resource System

Limited-use features use the resource system:

```python
# In feature condition's _apply():
target.action_economy.add_resource(
    name="second_wind",
    maximum=1,
    recharge_type=RechargeType.SHORT_REST  # or LONG_REST, TURN_START
)

# Register action template
action = SecondWind(source_entity_uuid=target.uuid, template=True)
target.register_action(action)
```

**RechargeTypes**: `TURN_START`, `SHORT_REST`, `LONG_REST`, `NEVER`

---

## How to Implement an Event Handler

Event handlers react to game events (damage rolls, turn start, attacks, etc.).

### Basic Structure

```python
def my_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    # Only process relevant events
    if event.source_entity_uuid != source_entity_uuid:
        return None

    # Do something...

    # Return modified event or None
    return event.model_copy(update={"modified": True})

def create_my_handler(source_entity_uuid: UUID) -> EventHandler:
    return EventHandler(
        name="MyHandler",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.DAMAGE_ROLLED,
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

# Return handler UUID for auto-cleanup
return [], [handler.uuid], [], effect_event
```

### Common Trigger Points

| EventType | Phase | Use Case |
|-----------|-------|----------|
| `ATTACK` | `EXECUTION` | Protection (impose disadvantage before roll) |
| `DAMAGE_ROLLED` | `EFFECT` | Great Weapon Fighting (reroll dice) |
| `SAVING_THROW` | `EFFECT` | Indomitable (reroll failed save) |
| `TURN_START` | `EXECUTION` | Survivor (heal at turn start) |

**Important**: `COMPLETION` phase is closed to handlers.

---

## Dice Manipulation Pattern (DAMAGE_ROLLED)

For abilities that modify dice results (Great Weapon Fighting, Elemental Adept):

```python
def my_dice_processor(event: DamageRolledEvent, source_entity_uuid: UUID) -> Optional[DamageRolledEvent]:
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

## Common Pitfalls

### Method/Attribute Naming

**Always read actual class definitions before using methods.**

| Wrong | Correct |
|-------|---------|
| `entity.health.current_hit_points` | `entity.get_hp()` |
| `AbilityScoresConfig(strength=10)` | `AbilityScoresConfig(strength=AbilityConfig(score=10))` |
| `create_goblin("Name", (0,0))` | `create_goblin(name="Name", position=(0,0))` |
| `entity.equipment.weapon_main_hand` | `entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)` |

### Circular Imports

**Never use late imports.** Dependencies flow DOWN:

```
Entity (high-level)
   ↓
Blocks (Senses, Equipment, Health)
   ↓
Primitives (ModifiableValue, Modifiers)
   ↓
Base classes (BaseObject, BaseBlock)
```

If you need to import "up", the method is in the wrong place.

### Cross-Entity Targeting

Always follow the propagation sequence:

```python
attacker.set_target_entity(target.uuid)
target.set_target_entity(attacker.uuid)

attack_bonus = attacker.attack_bonus(slot, target.uuid)
ac = target.ac_bonus(attacker.uuid)
attack_bonus.set_from_target(ac)  # Propagate defensive modifiers

# Do attack logic...

attack_bonus.reset_from_target()
attacker.clear_target_entity()
target.clear_target_entity()
```

### Event Handler Phase Selection

| Phase | When to Use |
|-------|-------------|
| `EXECUTION` | Modify attack before roll (Protection), track attack happened (HasAttacked) |
| `EFFECT` | After roll/result known (Indomitable reroll, GWF dice manipulation) |
| `COMPLETION` | **Don't use** - handlers are closed |

### Senses Updates

**Always call `Entity.update_all_entities_senses()`** after creating entities for LOS to work.

---

## Fighter Implementation Reference

All Fighter + Champion features are implemented in `dnd/classes/fighter.py`:

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

Use these as reference patterns for implementing similar features.

---

## How to Add Combat Log Generation to an Event

Events auto-generate combat log entries at COMPLETION phase via `generate_combat_log()`. The base `Event` class returns `None` by default - subclasses override to provide their own formatting.

### Basic Pattern

```python
class MyActionEvent(ActionEvent):
    """Event for my custom action."""
    name: str = Field(default="My Action")
    event_type: EventType = Field(default=EventType.BASE_ACTION)

    # Add action-specific fields
    my_result: int = Field(default=0)

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log for this event.

        IMPORTANT: Use self.* fields only - no external Entity.get() lookups.
        Entity names must be populated when the event is created.
        """
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"

        # Build three verbosity levels with markdown
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
            data={"my_result": self.my_result},  # Structured data for programmatic access
            success=self.my_result > 0
        )
```

### Key Points

1. **Entity names must be set at event creation**, not looked up in `generate_combat_log()`:
   ```python
   # In action's _create_declaration_event():
   return MyActionEvent(
       source_entity_name=source.name,  # Set here
       target_entity_name=target.name,  # Set here
       ...
   )
   ```

2. **Use markdown helpers** from `dnd/core/combat_log.py`:
   - `md_color(text, color)` - `{color:text}` for Rich rendering
   - `md_d20_roll(roll)` - Format d20 with advantage/disadvantage
   - `md_breakdown(modifiers)` - Format `[Prof +2, DEX +2]`
   - `md_outcome(outcome)` - Color HIT/MISS/CRIT appropriately

3. **Three verbosity levels**:
   - `compact`: One-line summary (for quick log view)
   - `verbose`: Summary + key details (default display)
   - `detailed`: Full modifier breakdowns (for debugging)

4. **Structured data** in the `data` field for programmatic access - use typed models when possible:
   - `AttackLogData`, `MovementLogData`, `SavingThrowLogData`, `SkillCheckLogData`

### Example: Shove Event Combat Log

```python
def generate_combat_log(self) -> CombatLogEntry:
    source_name = self.source_entity_name or "Unknown"
    target_name = self.target_entity_name or "Unknown"

    # COMPACT: Just the outcome
    if self.contest_success is False:
        compact_text = f"{md_color(source_name, 'cyan')} fails to shove {md_color(target_name, 'yellow')}"
    elif self.push_distance > 0:
        compact_text = f"{md_color(source_name, 'cyan')} shoves {md_color(target_name, 'yellow')} {md_color(f'{self.push_distance}ft', 'green')}"

    # VERBOSE: Add roll info
    verbose_text = compact_text
    if self.dice_roll:
        success_str = md_color("success", "green") if self.contest_success else md_color("fail", "red")
        verbose_text += f"\n  Athletics: d20({self.dice_roll.total}) vs DC {self.target_passive} → {success_str}"

    # DETAILED: Add more context
    detailed_text = verbose_text
    detailed_text += f"\n  Direction: {self.push_direction}"

    return CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name=source_name,
        source_uuid=str(self.source_entity_uuid),
        target_name=target_name,
        target_uuid=str(self.target_entity_uuid),
        compact=compact_text,
        verbose=verbose_text,
        detailed=detailed_text,
        data={
            "action_type": "shove",
            "contest_success": self.contest_success,
            "push_distance": self.push_distance,
        },
        success=self.contest_success or False
    )
```
