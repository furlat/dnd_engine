# Fighter Implementation Plan

## Overview

This document analyzes all Fighter class features and plans their implementation using existing primitives (conditions, actions, event handlers, resources, modifiers).

**Status**: Planning phase - brainstorming implementation approaches.

---

## Current State (What's Done)

### Resource System (Phase 1) - COMPLETE

| Component | Location | Status |
|-----------|----------|--------|
| `RechargeType` enum | `dnd/blocks/action_economy.py` | ✅ Done |
| `Resource` model | `dnd/blocks/action_economy.py` | ✅ Done |
| `ActionEconomy.resources` | `dnd/blocks/action_economy.py` | ✅ Done |
| `add_resource()`, `consume_resource()` | `dnd/blocks/action_economy.py` | ✅ Done |
| `on_short_rest()`, `on_long_rest()` | `dnd/blocks/action_economy.py` | ✅ Done |
| `BaseCost.resource_name/resource_cost` | `dnd/core/base_actions.py` | ✅ Done |
| Resource validation in `check_costs()` | `dnd/core/base_actions.py` | ✅ Done |
| Resource consumption in cost applier | `dnd/actions.py` | ✅ Done |

### Second Wind Proof of Concept - COMPLETE

| Component | Location | Status |
|-----------|----------|--------|
| `SecondWind` action | `examples/test_second_wind.py` | ✅ Done |
| Integration test | `examples/test_second_wind.py` | ✅ Done |

---

## Event System Constraints

### IMPORTANT: Event Handler Timing

**Handlers can only respond BEFORE the COMPLETION phase.**

Once an event reaches COMPLETION:
- It cannot be modified
- It cannot spawn sub-events (like reactions)
- It is finalized in the event history

**Implication for reactions**:
- Protection, Indomitable, etc. must trigger on DECLARATION or EXECUTION phase
- The reaction becomes a child event of the original event
- Original event waits for reaction to complete before proceeding

```
Attack Event Phases:
  DECLARATION ─── Handlers can intercept here (Protection)
       │
  EXECUTION ───── Handlers can intercept here (modify attack)
       │
  EFFECT ──────── Handlers can intercept here (Indomitable on saves)
       │
  COMPLETION ──── Too late! Event is finalized.
```

---

## Fighter Features - Complete Table

### Level 1

| Feature | Type | Difficulty | Approach |
|---------|------|------------|----------|
| **Archery** | Fighting Style | Simple | Static +2 modifier on ranged attack |
| **Defense** | Fighting Style | Simple | Contextual +1 AC if armor equipped |
| **Dueling** | Fighting Style | Simple | Contextual +2 melee damage if one-handed |
| **Great Weapon Fighting** | Fighting Style | Complex | EventHandler on damage dice, reroll 1s/2s |
| **Protection** | Fighting Style | Medium | Auto-reaction EventHandler on ally attacked |
| **Two-Weapon Fighting** | Fighting Style | Simple | Enable ability mod on off-hand damage |
| **Second Wind** | Class Feature | Done | Resource + Action |

### Level 2

| Feature | Type | Difficulty | Approach |
|---------|------|------------|----------|
| **Action Surge** | Class Feature | Simple | Resource + Action that adds +1 action |

### Level 3 (Champion Archetype)

| Feature | Type | Difficulty | Approach |
|---------|------|------------|----------|
| **Improved Critical** | Archetype | Medium | New `crit_threshold` ModifiableValue |

### Level 4, 6, 8, 12, 14, 16, 19

| Feature | Type | Difficulty | Approach |
|---------|------|------------|----------|
| **Ability Score Improvement** | Class Feature | Simple | Permanent modifiers on ability scores |

### Level 5, 11, 20

| Feature | Type | Difficulty | Approach |
|---------|------|------------|----------|
| **Extra Attack** | Class Feature | Medium | HasAttacked condition + ExtraAttack action + resource |

### Level 7 (Champion)

| Feature | Type | Difficulty | Approach |
|---------|------|------------|----------|
| **Remarkable Athlete** | Archetype | Medium | Half-proficiency to non-proficient physical checks |

### Level 9, 13, 17

| Feature | Type | Difficulty | Approach |
|---------|------|------------|----------|
| **Indomitable** | Class Feature | Medium | Auto-reroll EventHandler on failed save |

### Level 10 (Champion)

| Feature | Type | Difficulty | Approach |
|---------|------|------------|----------|
| **Additional Fighting Style** | Archetype | Simple | Add second fighting style condition |

### Level 15 (Champion)

| Feature | Type | Difficulty | Approach |
|---------|------|------------|----------|
| **Superior Critical** | Archetype | Simple | Same as Improved, stacks to 18-20 |

### Level 17

| Feature | Type | Difficulty | Approach |
|---------|------|------------|----------|
| **Action Surge (2 uses)** | Class Feature | Simple | Increase resource max to 2 |

### Level 18 (Champion)

| Feature | Type | Difficulty | Approach |
|---------|------|------------|----------|
| **Survivor** | Archetype | Medium | Turn start healing if below half HP |

---

## Detailed Implementation Plans

### Simple Features (Existing Primitives Only)

#### Archery
```python
# Condition that adds +2 to ranged attack rolls
class FightingStyleArchery(BaseCondition):
    name = "Fighting Style: Archery"
    tags = ["class:fighter", "level:1", "feature:fighting_style"]

    def _apply(self, event):
        target = Entity.get(self.target_entity_uuid)
        modifier = NumericalModifier.create(..., name="Archery", value=2)
        # Add to ranged attack bonus (need to verify this exists)
        mod_uuid = target.equipment.ranged_attack_bonus.self_static.add_value_modifier(modifier)
        return [(target.equipment.ranged_attack_bonus.uuid, mod_uuid)], [], [], event
```

#### Defense
```python
# Condition that adds +1 AC when wearing armor
def has_armor(source_uuid, target_uuid, context):
    entity = Entity.get(source_uuid)
    if entity and entity.equipment.armor is not None:
        return NumericalModifier.create(..., name="Defense", value=1)
    return None

class FightingStyleDefense(BaseCondition):
    name = "Fighting Style: Defense"
    tags = ["class:fighter", "level:1", "feature:fighting_style"]

    def _apply(self, event):
        target = Entity.get(self.target_entity_uuid)
        modifier = ContextualNumericalModifier(..., callable=has_armor)
        mod_uuid = target.equipment.ac_bonus.self_contextual.add_value_modifier(modifier)
        return [(target.equipment.ac_bonus.uuid, mod_uuid)], [], [], event
```

#### Action Surge
```python
# Resource: "action_surge" (max=1, recharge=SHORT_REST)
# Action: Grants +1 action

class ActionSurgeAction(BaseAction):
    name = "Action Surge"
    target_type = TargetType.SELF
    costs = [Cost(resource_name="action_surge", resource_cost=1)]  # No action cost!

    def _apply(self, event):
        entity = Entity.get(self.source_entity_uuid)
        # Add +1 to actions via modifier
        modifier = NumericalModifier.create(..., name="Action Surge", value=1)
        entity.action_economy.actions.self_static.add_value_modifier(modifier)
        # Note: This modifier should be removed at end of turn
        return event.phase_to(EventPhase.COMPLETION)
```

---

### Medium Features (Small Extensions Needed)

#### Extra Attack

**Design**: Use existing primitives - condition as marker, event handler, separate action.

**Components**:

1. **HasAttacked Condition** (marker, no modifiers)
```python
class HasAttacked(BaseCondition):
    name = "HasAttacked"
    duration: int = 1  # Removed at start of next turn

    def _apply(self, event):
        # No modifiers, just a marker
        return [], [], [], event.phase_to(EventPhase.EFFECT)
```

2. **EventHandler** (applies HasAttacked on attack)
```python
EventHandler(
    trigger=Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT),
    # Note: EFFECT phase, not COMPLETION (per constraint above)
    event_processor=lambda event, source_uuid: apply_has_attacked(event, source_uuid)
)

def apply_has_attacked(event, source_uuid):
    entity = Entity.get(event.source_entity_uuid)
    if entity:
        has_attacked = HasAttacked(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        )
        entity.add_condition(has_attacked)
    return event  # Don't modify the attack event
```

3. **ExtraAttack Action** (separate from Attack)
```python
class ExtraAttack(Attack):  # Inherit from Attack
    name = "Extra Attack"
    costs = [Cost(resource_name="extra_attack", resource_cost=1)]  # Resource, not action

    def _validate(self, event):
        entity = Entity.get(self.source_entity_uuid)

        # Must have attacked this turn
        if "HasAttacked" not in entity.active_conditions:
            return event.cancel(status_message="Must attack first")

        # Parent validation (range, LOS, etc.)
        return super()._validate(event)
```

4. **ExtraAttackFeature Condition** (sets up resource + handler + action)
```python
class ExtraAttackFeature(BaseCondition):
    name = "Extra Attack"
    tags = ["class:fighter", "level:5"]
    num_extra_attacks: int = 1  # 1 at level 5, 2 at level 11, 3 at level 20

    def _apply(self, event):
        target = Entity.get(self.target_entity_uuid)

        # Add resource
        target.action_economy.add_resource(
            "extra_attack",
            maximum=self.num_extra_attacks,
            recharge_type=RechargeType.TURN_START
        )

        # Add event handler for HasAttacked
        handler = EventHandler(...)
        target.add_event_handler(handler)

        # Register ExtraAttack action template
        target.register_action(ExtraAttack(
            source_entity_uuid=target.uuid,
            template=True
        ))

        # Return tracked items for auto-cleanup
        return [], [handler.uuid], [], event
```

**Level Scaling**:
- Level 5: `num_extra_attacks=1` (2 attacks total)
- Level 11: `num_extra_attacks=2` (3 attacks total)
- Level 20: `num_extra_attacks=3` (4 attacks total)

---

#### Improved/Superior Critical

**Design**: Add `crit_threshold` ModifiableValue to Entity. Crit range = `20 - threshold`.

**New Field on Entity**:
```python
class Entity(BaseBlock):
    # ... existing fields ...
    crit_threshold: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=0,  # Default: crit on 20
            value_name="crit_threshold"
        )
    )
```

**Modified Attack Outcome Check**:
```python
def determine_attack_outcome(roll, ac, attacker):
    # Get crit threshold (0 = crit on 20, 1 = crit on 19-20, 2 = crit on 18-20)
    threshold = attacker.crit_threshold.normalized_score
    crit_minimum = 20 - threshold

    if roll.results >= crit_minimum:
        return AttackOutcome.CRIT
    # ... rest of logic
```

**Improved Critical Condition** (Champion Level 3):
```python
class ImprovedCritical(BaseCondition):
    name = "Improved Critical"
    tags = ["class:fighter", "archetype:champion", "level:3"]

    def _apply(self, event):
        target = Entity.get(self.target_entity_uuid)
        modifier = NumericalModifier.create(..., name="Improved Critical", value=1)
        mod_uuid = target.crit_threshold.self_static.add_value_modifier(modifier)
        return [(target.crit_threshold.uuid, mod_uuid)], [], [], event
```

**Superior Critical Condition** (Champion Level 15):
```python
class SuperiorCritical(BaseCondition):
    name = "Superior Critical"
    tags = ["class:fighter", "archetype:champion", "level:15"]

    def _apply(self, event):
        target = Entity.get(self.target_entity_uuid)
        # Adds another +1 (stacks with Improved Critical for 18-20)
        modifier = NumericalModifier.create(..., name="Superior Critical", value=1)
        mod_uuid = target.crit_threshold.self_static.add_value_modifier(modifier)
        return [(target.crit_threshold.uuid, mod_uuid)], [], [], event
```

---

#### Protection (Auto-Reaction)

**Design**: EventHandler on ATTACK declaration, auto-triggers reaction.

```python
class ProtectionHandler:
    """
    When a creature attacks an ally within 5ft, impose disadvantage.
    Uses reaction, requires shield.
    """

    def create_handler(self, source_entity_uuid):
        return EventHandler(
            source_entity_uuid=source_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.DECLARATION  # Before completion!
                )
            ],
            event_processor=self.process_attack
        )

    def process_attack(self, event, source_uuid):
        protector = Entity.get(source_uuid)
        attacker = Entity.get(event.source_entity_uuid)
        target = Entity.get(event.target_entity_uuid)

        # Conditions:
        # 1. Target is not self
        if target.uuid == protector.uuid:
            return event

        # 2. Target is within 5ft of protector
        distance = protector.senses.get_feet_distance(target.position)
        if distance > 5:
            return event

        # 3. Protector can see attacker
        if attacker.uuid not in protector.senses.entities:
            return event

        # 4. Protector has shield equipped
        if protector.equipment.shield is None:
            return event

        # 5. Protector has reaction available
        if not protector.action_economy.can_afford("reactions", 1):
            return event

        # All conditions met - impose disadvantage and consume reaction
        protector.action_economy.consume("reactions", 1)

        # Add disadvantage to attack (modify event's attack_bonus)
        # This requires the attack_bonus to be on the event or accessible
        # May need to add disadvantage modifier to attacker's attack

        return event  # Return modified event
```

**Challenge**: How to inject disadvantage into an attack that's in progress?

**Options**:
1. Modify `event.attack_bonus` directly (if it's on the event)
2. Add a temporary condition to the attacker
3. Store "pending disadvantages" that get applied during attack resolution

---

#### Indomitable (Auto Save Reroll)

**Design**: EventHandler on SAVING_THROW effect phase, auto-rerolls failed saves.

```python
class IndomitableHandler:
    def process_save(self, event, source_uuid):
        entity = Entity.get(source_uuid)

        # Only trigger on own saves
        if event.source_entity_uuid != source_uuid:
            return event

        # Check if save failed
        if event.success:  # Assuming SavingThrowEvent has this
            return event

        # Check resource
        if not entity.action_economy.can_afford_resource("indomitable", 1):
            return event

        # Consume resource and reroll
        entity.action_economy.consume_resource("indomitable", 1)

        # Reroll the save
        new_roll = entity.roll_d20(event.save_bonus, RollType.SAVE)

        # Use new result (even if worse, per RAW)
        modified_event = event.model_copy(update={
            "dice_roll": new_roll,
            "success": new_roll.total >= event.dc,
            "status_message": f"Indomitable reroll: {new_roll.total}"
        })

        return modified_event
```

---

### Complex Features (New Primitives Needed)

#### Great Weapon Fighting (Dice Reroll)

**What's Needed**: Event fired between "dice rolled" and "damage applied".

**New Event Type**: `DAMAGE_ROLLED`

**New Event Class**:
```python
class DamageRolledEvent(Event):
    event_type = EventType.DAMAGE_ROLLED
    weapon_slot: WeaponSlot
    dice_results: List[int]  # Mutable - handlers can modify
    damage_type: DamageType
    is_critical: bool
```

**Modified Attack Flow**:
```python
# In Attack._apply(), after determining hit:
if attack_outcome in [AttackOutcome.HIT, AttackOutcome.CRIT]:
    # Roll damage dice
    damage_roll = weapon.damage_dice.roll

    # Fire DAMAGE_ROLLED event (handlers can modify dice_results)
    damage_event = DamageRolledEvent(
        source_entity_uuid=self.source_entity_uuid,
        target_entity_uuid=self.target_entity_uuid,
        weapon_slot=self.weapon_slot,
        dice_results=damage_roll.results,  # List of individual die results
        is_critical=(attack_outcome == AttackOutcome.CRIT)
    )
    # Event handlers modify dice_results

    # Apply final damage using (possibly modified) results
    final_damage = sum(damage_event.dice_results) + damage_bonus
    target.health.take_damage(final_damage, damage_type)
```

**Great Weapon Fighting Handler**:
```python
def process_damage_rolled(event, source_uuid):
    entity = Entity.get(source_uuid)

    # Only own attacks
    if event.source_entity_uuid != source_uuid:
        return event

    # Check weapon is two-handed or versatile
    weapon = entity.equipment._get_weapon_by_slot(event.weapon_slot)
    if not weapon:
        return event

    has_two_handed = WeaponProperty.TWO_HANDED in weapon.properties
    has_versatile = WeaponProperty.VERSATILE in weapon.properties
    if not (has_two_handed or has_versatile):
        return event

    # Reroll 1s and 2s
    new_results = []
    for result in event.dice_results:
        if result <= 2:
            # Reroll (must use new result even if still 1-2)
            new_result = random.randint(1, weapon.damage_dice_value)
            new_results.append(new_result)
        else:
            new_results.append(result)

    return event.model_copy(update={"dice_results": new_results})
```

---

#### Survivor (Turn Start Healing)

**What's Needed**: Turn start event or hook.

**Option 1**: Add to Encounter turn management
```python
# In Encounter.start_turn(entity):
def start_turn(self, entity):
    # Reset action economy
    entity.action_economy.reset_all_costs()
    entity.action_economy.on_turn_start()  # Recharge TURN_START resources

    # Fire TURN_START event
    turn_event = TurnStartEvent(source_entity_uuid=entity.uuid)
    # Handlers can react (Survivor healing, etc.)
```

**Option 2**: Condition with `on_turn_start()` method
```python
class BaseCondition:
    def on_turn_start(self):
        """Called at the start of the condition holder's turn."""
        pass

class Survivor(BaseCondition):
    def on_turn_start(self):
        entity = Entity.get(self.target_entity_uuid)
        current_hp = entity.get_hp()
        max_hp = entity.health.max_hit_points

        if current_hp > 0 and current_hp <= max_hp // 2:
            healing = 5 + entity.ability_scores.constitution.modifier
            entity.health.heal(healing)
```

---

## What's Missing - Summary

### New ModifiableValues

| Field | Location | Purpose |
|-------|----------|---------|
| `crit_threshold` | Entity | Expand crit range (0=20, 1=19-20, 2=18-20) |
| `extra_crit_dice` | Entity | Additional dice on critical hits (future) |

### New Event Types

| Event | When Fired | Purpose |
|-------|------------|---------|
| `DAMAGE_ROLLED` | After damage dice, before apply | Enable dice manipulation (GWF) |
| `TURN_START` | Start of entity's turn | Enable turn-start effects (Survivor) |

### New Condition Methods

| Method | Purpose |
|--------|---------|
| `on_turn_start()` | Called at turn start for effects like Survivor |

### New Tracking

| Field | Location | Reset |
|-------|----------|-------|
| (none needed with HasAttacked approach) | | |

---

## Implementation Priority

### Phase 1: Simple Fighting Styles
1. Archery (static modifier)
2. Defense (contextual modifier)
3. Dueling (contextual modifier)
4. Two-Weapon Fighting (flag/modifier)

### Phase 2: Core Class Features
5. Second Wind - ✅ DONE
6. Action Surge (resource + action)
7. Extra Attack (HasAttacked + ExtraAttack action + resource)

### Phase 3: Critical System
8. Add `crit_threshold` to Entity
9. Improved Critical condition
10. Superior Critical condition

### Phase 4: Reactions
11. Protection (auto-reaction handler)
12. Indomitable (auto-reroll handler)

### Phase 5: Complex Features
13. Great Weapon Fighting (DAMAGE_ROLLED event)
14. Survivor (turn start hook)
15. Remarkable Athlete (half-proficiency check)

---

## Open Questions

1. **Equipment ModifiableValues**: Do we have separate `ranged_attack_bonus` vs `melee_attack_bonus`? Need to verify.

2. **Reaction choice**: For now, auto-trigger. Later, may need player/AI choice mechanism.

3. **Turn start hooks**: Use event or condition method? Event is more flexible.

4. **Condition tags**: Not yet implemented. Needed for `remove_conditions_by_tag("class:fighter")`.

5. **Off-hand damage ability mod**: How is this currently blocked? Need to find and add override.
