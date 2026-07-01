# Remaining Fighter Features - Complete Implementation Plan

## Overview

This document provides complete implementation plans for all remaining Fighter features. Each plan includes exact code, files to modify, and test verification.

---

## Status Summary

### Completed
| Feature | Level | Location |
|---------|-------|----------|
| Second Wind | 1 | `dnd/actions.py`, `examples/test_second_wind.py` |
| Great Weapon Fighting | 1 | `dnd/classes/fighter.py` |
| Protection | 1 | `dnd/classes/fighter.py` |
| Extra Attack | 5/11/20 | `dnd/classes/fighter.py` |
| Improved Critical | 3 | `dnd/classes/fighter.py` |
| Superior Critical | 15 | `dnd/classes/fighter.py` |
| Action Surge | 2/17 | `dnd/conditions.py`, `dnd/actions.py`, `dnd/classes/fighter.py` |
| Indomitable | 9/13/17 | `dnd/classes/fighter.py` |

### Remaining
| Feature | Level | Difficulty | Est. Time |
|---------|-------|------------|-----------|
| Archery | 1 | Simple | 15 min |
| Defense | 1 | Simple | 20 min |
| Dueling | 1 | Simple | 20 min |
| Two-Weapon Fighting | 1 | Simple | 25 min |
| Survivor | 18 | Simple | 30 min |

**Skipped**: Remarkable Athlete (L7 Champion) - low priority, niche feature

---

## Simple Fighting Styles

### 1. Archery Fighting Style

**Effect**: +2 bonus to attack rolls with ranged weapons.

**Target ModifiableValue**: `equipment.ranged_attack_bonus.self_static`

**Implementation**:

```python
# dnd/classes/fighter.py

class FightingStyleArchery(BaseCondition):
    """
    Fighter Fighting Style: Archery

    You gain a +2 bonus to attack rolls you make with ranged weapons.
    """
    name: str = "Fighting Style: Archery"
    description: str = "+2 bonus to attack rolls with ranged weapons"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(
                status_message="Target entity not found"
            )

        outs = []

        # Add +2 to ranged attack bonus
        modifier = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Archery",
            value=2
        )
        mod_uuid = target.equipment.ranged_attack_bonus.self_static.add_value_modifier(modifier)
        outs.append((target.equipment.ranged_attack_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Archery fighting style to {target.name}"
        )

        return outs, [], [], effect_event
```

**Test**:
```python
def test_archery():
    fighter = create_goblin(name="Archer", position=(0, 0))
    initial_bonus = fighter.equipment.ranged_attack_bonus.normalized_score

    archery = FightingStyleArchery(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(archery)

    new_bonus = fighter.equipment.ranged_attack_bonus.normalized_score
    assert new_bonus == initial_bonus + 2, f"Expected +2, got {new_bonus - initial_bonus}"

    # Verify removal
    fighter.remove_condition("Fighting Style: Archery")
    assert fighter.equipment.ranged_attack_bonus.normalized_score == initial_bonus
```

---

### 2. Defense Fighting Style

**Effect**: +1 AC while wearing armor.

**Challenge**: Must check if `body_armor` exists and is not CLOTH type.

**Target ModifiableValue**: `equipment.ac_bonus.self_contextual`

**Implementation**:

```python
# dnd/classes/fighter.py

from dnd.core.modifiers import ContextualNumericalModifier

def defense_ac_bonus(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID],
    context: Optional[Dict]
) -> Optional[NumericalModifier]:
    """Returns +1 AC if wearing armor (not unarmored or cloth)."""
    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Check if wearing real armor (not unarmored)
    if entity.equipment.is_unarmored():
        return None

    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Defense",
        value=1
    )


class FightingStyleDefense(BaseCondition):
    """
    Fighter Fighting Style: Defense

    While you are wearing armor, you gain a +1 bonus to AC.
    """
    name: str = "Fighting Style: Defense"
    description: str = "+1 AC while wearing armor"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(
                status_message="Target entity not found"
            )

        outs = []

        # Add contextual +1 AC (only when wearing armor)
        modifier = ContextualNumericalModifier(
            source_entity_uuid=self.target_entity_uuid,
            name="Defense",
            callable=defense_ac_bonus
        )
        mod_uuid = target.equipment.ac_bonus.self_contextual.add_value_modifier(modifier)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Defense fighting style to {target.name}"
        )

        return outs, [], [], effect_event
```

**Test**:
```python
def test_defense():
    # Fighter with armor
    fighter = create_skeleton(name="Defender", position=(0, 0))  # Has armor
    initial_ac = fighter.equipment.get_ac(fighter.ability_scores)

    defense = FightingStyleDefense(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(defense)

    # Verify +1 AC with armor
    armored_ac = fighter.equipment.get_ac(fighter.ability_scores)
    assert armored_ac == initial_ac + 1

    # Remove armor, verify no bonus
    fighter.equipment.body_armor = None
    unarmored_ac = fighter.equipment.get_ac(fighter.ability_scores)
    # Defense doesn't apply without armor
```

---

### 3. Dueling Fighting Style

**Effect**: +2 damage when wielding a melee weapon in one hand and no other weapons.

**Challenge**: Must check:
- Main hand has melee weapon (not ranged)
- Off-hand is empty OR has shield (not another weapon)

**Target ModifiableValue**: `equipment.melee_damage_bonus.self_contextual`

**Implementation**:

```python
# dnd/classes/fighter.py

def dueling_damage_bonus(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID],
    context: Optional[Dict]
) -> Optional[NumericalModifier]:
    """Returns +2 damage if wielding single melee weapon (shield OK)."""
    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Check main hand has melee weapon
    main_hand = entity.equipment.weapon_melee_main
    if main_hand is None:
        return None
    if isinstance(main_hand, Shield):
        return None  # Shield in main hand doesn't count

    # Check weapon is melee (not ranged)
    if WeaponProperty.RANGED in main_hand.properties:
        return None

    # Check off-hand: must be empty or shield (not another weapon)
    off_hand = entity.equipment.weapon_melee_off
    if off_hand is not None and not isinstance(off_hand, Shield):
        return None  # Has second weapon, no dueling bonus

    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Dueling",
        value=2
    )


class FightingStyleDueling(BaseCondition):
    """
    Fighter Fighting Style: Dueling

    When you are wielding a melee weapon in one hand and no other weapons,
    you gain a +2 bonus to damage rolls with that weapon.
    """
    name: str = "Fighting Style: Dueling"
    description: str = "+2 damage with single one-handed melee weapon"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(
                status_message="Target entity not found"
            )

        outs = []

        # Add contextual +2 melee damage
        modifier = ContextualNumericalModifier(
            source_entity_uuid=self.target_entity_uuid,
            name="Dueling",
            callable=dueling_damage_bonus
        )
        mod_uuid = target.equipment.melee_damage_bonus.self_contextual.add_value_modifier(modifier)
        outs.append((target.equipment.melee_damage_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Dueling fighting style to {target.name}"
        )

        return outs, [], [], effect_event
```

---

### 4. Two-Weapon Fighting Fighting Style

**Effect**: When you engage in two-weapon fighting, you can add your ability modifier to the damage of the off-hand attack.

**Challenge**: By default, off-hand attacks don't add ability modifier to damage. This fighting style enables it.

**Current State Check Needed**: How is off-hand damage currently calculated? Does it already exclude ability mod?

**Implementation Approach**:
The off-hand damage calculation needs to check if this condition exists. If yes, add ability modifier.

**Implementation**:

```python
# This requires checking how off-hand damage is calculated in equipment.py
# The fighting style adds a flag that the damage calculation checks

class FightingStyleTwoWeaponFighting(BaseCondition):
    """
    Fighter Fighting Style: Two-Weapon Fighting

    When you engage in two-weapon fighting, you can add your ability
    modifier to the damage of the second attack.
    """
    name: str = "Fighting Style: Two-Weapon Fighting"
    description: str = "Add ability modifier to off-hand damage"

    # This is a flag condition - its presence enables the bonus
    # The damage calculation in Entity/Equipment checks for this condition

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        # No modifiers to add - this is a flag condition
        # The Entity.get_damages() method checks for this condition
        # when calculating off-hand damage

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Two-Weapon Fighting style"
        )

        return [], [], [], effect_event
```

**Required Change in `Entity.get_damages()` or `Equipment.get_damage()`**:
```python
# In the damage calculation for off-hand attacks:
def get_damages(self, weapon_slot: WeaponSlot, target_entity_uuid: UUID) -> List[Damage]:
    # ... existing code ...

    # For off-hand attacks, check if Two-Weapon Fighting is active
    is_off_hand = weapon_slot in [WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_OFF]
    has_twf = "Fighting Style: Two-Weapon Fighting" in self.active_conditions

    if is_off_hand and not has_twf:
        # Don't add ability modifier to off-hand damage
        ability_bonus = 0
    else:
        ability_bonus = self.ability_scores.get_ability(ability_name).modifier
```

---

## Medium Features

### 5. Action Surge (Level 2) - ✅ IMPLEMENTED

**Status**: Complete. See `dnd/conditions.py` (ActionSurging), `dnd/actions.py` (ActionSurge), `dnd/classes/fighter.py` (ActionSurgeFeature).

**Effect**: On your turn, you can take one additional action. Once used, must finish short/long rest.

**Resource**: `action_surge` (max=1, recharge=SHORT_REST; max=2 at level 17)

**Pattern**: Same as Dashing - apply a 1-round condition that adds +1 action. Expires at start of next turn.

**Implementation**:

```python
# dnd/classes/fighter.py

class ActionSurging(BaseCondition):
    """
    Temporary condition applied when Action Surge is used.
    Adds +1 action for this turn, expires at start of next turn.
    """
    name: str = "Action Surging"
    description: str = "+1 action this turn"
    duration: int = Field(default=1)  # 1 round, expires at start of next turn

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(
                status_message="Target entity not found"
            )

        outs = []

        # Add +1 action
        modifier = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Action Surge",
            value=1
        )
        mod_uuid = target.action_economy.actions.self_static.add_value_modifier(modifier)
        outs.append((target.action_economy.actions.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} surges with extra action!"
        )

        return outs, [], [], effect_event


class ActionSurge(BaseAction):
    """
    Fighter Feature: Action Surge

    On your turn, take one additional action.
    Free to activate (no action cost), only resource cost.
    """
    name: str = Field(default="Action Surge")
    description: str = Field(default="Take one additional action on your turn")
    target_type: TargetType = Field(default=TargetType.SELF)

    # Free action - only resource cost
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(
            name="Action Surge",
            cost_type=None,
            cost=0,
            resource_name="action_surge",
            resource_cost=1,
            evaluator=entity_action_economy_cost_evaluator
        )
    ])

    def _validate(self, declaration_event):
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if not entity.action_economy.can_afford_resource("action_surge", 1):
            return declaration_event.cancel(status_message="Action Surge not available")

        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event):
        entity = Entity.get(self.source_entity_uuid)

        # Apply ActionSurging condition (1 round duration, adds +1 action)
        surging = ActionSurging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        entity.add_condition(surging)

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{entity.name} uses Action Surge!"
        )

        return effect_event.phase_to(EventPhase.COMPLETION)


class ActionSurgeFeature(BaseCondition):
    """
    Fighter Level 2 Feature: Action Surge

    Grants the Action Surge resource and action.
    """
    name: str = "Action Surge Feature"
    description: str = "Take one additional action on your turn (1/short rest)"
    num_uses: int = Field(default=1)  # 1 at L2, 2 at L17

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(
                status_message="Target entity not found"
            )

        # Add resource
        target.action_economy.add_resource(
            name="action_surge",
            maximum=self.num_uses,
            recharge_type=RechargeType.SHORT_REST
        )

        # Register action template
        action_surge = ActionSurge(
            source_entity_uuid=target.uuid,
            template=True
        )
        target.register_action(action_surge)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Action Surge feature to {target.name}"
        )

        return [], [], [], effect_event
```

---

### 6. Indomitable (Level 9/13/17) - ✅ IMPLEMENTED

**Status**: Complete. See `dnd/classes/fighter.py` (Indomitable, indomitable_processor, create_indomitable_handler).

**Effect**: Reroll a failed saving throw. Must use new roll. Uses: 1 at L9, 2 at L13, 3 at L17.

**Pattern**: Same as Protection - EventHandler on SAVING_THROW at EFFECT phase.

**Implementation**:

```python
# dnd/classes/fighter.py

def indomitable_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """
    Event processor for Indomitable.

    Triggers on SAVING_THROW events at EFFECT phase.
    Rerolls failed saves if resource available.
    """
    # Only process own saves
    if event.target_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Check if save failed (result is False for failure)
    if event.result is True or event.result is None:
        return None  # Save succeeded or not yet resolved

    # Check resource available
    if not entity.action_economy.can_afford_resource("indomitable", 1):
        return None  # No uses left

    # Consume resource
    entity.action_economy.consume_resource("indomitable", 1)

    # Reroll the save
    save_bonus = entity.saving_throw_bonus(event.source_entity_uuid, event.ability_name)
    new_roll = entity.roll_d20(save_bonus, RollType.SAVE)

    # Determine new result
    dc = event.get_dc()
    new_success = new_roll.total >= dc if dc else False

    # Return modified event with new roll
    return event.model_copy(update={
        "dice_roll": new_roll,
        "result": new_success,
        "modified": True,
        "status_message": f"{entity.name} uses Indomitable! Reroll: {new_roll.total} vs DC {dc}"
    })


def create_indomitable_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create an EventHandler for Indomitable."""
    return EventHandler(
        name="Indomitable",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.SAVING_THROW,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=indomitable_processor
    )


class Indomitable(BaseCondition):
    """
    Fighter Level 9 Feature: Indomitable

    You can reroll a saving throw that you fail.
    You must use the new roll.
    """
    name: str = "Indomitable"
    description: str = "Reroll a failed saving throw"
    num_uses: int = Field(default=1)  # 1 at L9, 2 at L13, 3 at L17

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(
                status_message="Target entity not found"
            )

        # Add resource (recharges on long rest)
        target.action_economy.add_resource(
            name="indomitable",
            maximum=self.num_uses,
            recharge_type=RechargeType.LONG_REST
        )

        # Register event handler
        handler = create_indomitable_handler(target.uuid)
        EventQueue.add_event_handler(handler)
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Indomitable feature to {target.name}"
        )

        return [], [handler.uuid], [], effect_event
```

**Challenge**: The `event.result` field may not be set at EFFECT phase. Need to verify when save success is determined.

**Alternative**: Trigger on COMPLETION phase if result isn't available at EFFECT. However, per documentation, COMPLETION is closed to modification. May need to trigger earlier and compute success ourselves.

---

### 7. Survivor (Level 18 Champion)

**Effect**: At the start of your turn, if you have no more than half your HP and at least 1 HP, regain HP equal to 5 + CON modifier.

**Pattern**: EventHandler on TURN_START event.

**Implementation**:

```python
# dnd/classes/fighter.py

def survivor_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """
    Event processor for Survivor.

    Triggers on TURN_START events.
    Heals if below half HP but above 0.
    """
    # Only process own turn starts
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    current_hp = entity.get_hp()
    max_hp = entity.health.max_hit_points.normalized_score

    # Must be above 0 HP and at or below half HP
    if current_hp <= 0 or current_hp > max_hp // 2:
        return None

    # Calculate healing: 5 + CON modifier
    con_mod = entity.ability_scores.get_ability("constitution").modifier
    healing = 5 + con_mod

    # Apply healing
    entity.health.heal(healing)

    return event.model_copy(update={
        "modified": True,
        "status_message": f"{entity.name}'s Survivor heals {healing} HP"
    })


def create_survivor_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create an EventHandler for Survivor."""
    return EventHandler(
        name="Survivor",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=survivor_processor
    )


class Survivor(BaseCondition):
    """
    Champion Fighter Level 18 Feature: Survivor

    At the start of each of your turns, you regain hit points equal
    to 5 + your Constitution modifier if you have no more than half
    of your hit points left.
    """
    name: str = "Survivor"
    description: str = "Heal 5 + CON mod at turn start when below half HP"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(
                status_message="Target entity not found"
            )

        # Register event handler
        handler = create_survivor_handler(target.uuid)
        EventQueue.add_event_handler(handler)
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Survivor feature to {target.name}"
        )

        return [], [handler.uuid], [], effect_event
```

---

### 8. Remarkable Athlete (Level 7 Champion)

**SKIPPED** - Low priority, niche feature. Can implement later if needed.

---

## Files to Modify

| File | Changes |
|------|---------|
| `dnd/classes/fighter.py` | Add all new conditions and processors |
| `dnd/classes/__init__.py` | Export new classes |
| `dnd/entity.py` | Possibly modify `get_damages()` for Two-Weapon Fighting |
| `examples/test_fighting_styles.py` | New test file for all fighting styles |
| `examples/test_action_surge.py` | New test file for Action Surge |
| `examples/test_indomitable.py` | New test file for Indomitable |
| `examples/test_survivor.py` | New test file for Survivor |

---

## Implementation Order

### Phase 1: Simple Fighting Styles
1. **Archery** - Static modifier on ranged_attack_bonus
2. **Defense** - Contextual modifier checking armor
3. **Dueling** - Contextual modifier checking single weapon
4. **Two-Weapon Fighting** - Flag condition + damage calc check

### Phase 2: Action Features - ✅ COMPLETE
5. **Action Surge** - ✅ DONE - `ActionSurging` + `ActionSurge` + `ActionSurgeFeature`
6. **Indomitable** - ✅ DONE - EventHandler on SAVING_THROW EFFECT phase

### Phase 3: Turn-Start Effects
7. **Survivor** - Turn start handler (needs TurnStartEvent fix)

---

## Potential Challenges

### 1. Two-Weapon Fighting - Damage Calculation
Need to verify how off-hand damage currently works. May need to modify `Entity.get_damages()` or `Equipment.get_damage()` to check for the condition.

### 2. Survivor - Turn Start Event Timing
TurnStartEvent fires at COMPLETION phase (closed to handlers). Need to either:
- Fire at EFFECT phase first, then transition to COMPLETION
- Or verify handlers can observe COMPLETION events for healing purposes

---

## Action Surge + Extra Attack Interaction - ✅ SOLVED

**Status**: Implemented in `has_attacked_processor` - each Attack action adds `num_extra_attacks` to the resource.

### Original Problem

Current Extra Attack uses `extra_attacks` resource that recharges at TURN_START. With Action Surge:

1. Attack action → use extra_attacks for bonus attacks
2. Action Surge → +1 action
3. Second Attack action → **extra_attacks already depleted!**

This breaks D&D rules where each Attack action should grant full Extra Attack benefits.

### Solution

Refresh `extra_attacks` resource when a new Attack action is taken (action-cost attacks only).

**Modify `has_attacked_processor` in `dnd/classes/fighter.py`:**

```python
def has_attacked_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """
    Tracks when entity has attacked using an action-costing attack.
    Also refreshes extra_attacks resource for Action Surge compatibility.
    """
    # Only track attacks from the handler owner
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Only track action-costing attacks (not OA, not bonus action attacks)
    # Check if this attack cost an action
    is_action_cost = False
    if hasattr(event, 'costs'):
        for cost in event.costs:
            if cost.cost_type == "actions" and cost.cost > 0:
                is_action_cost = True
                break

    if not is_action_cost:
        return None

    # Apply HasAttacked marker if not present
    if "HasAttacked" not in entity.active_conditions:
        has_attacked = HasAttacked(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        )
        entity.add_condition(has_attacked)

    # REFRESH extra_attacks resource for this Attack action
    # This allows Action Surge to grant full Extra Attack benefits
    extra_attack_resource = entity.action_economy.resources.get("extra_attacks")
    if extra_attack_resource:
        extra_attack_resource.current = extra_attack_resource.maximum

    return None  # Don't modify the attack event
```

### Why This Works

1. First Attack action → HasAttacked applied, extra_attacks refreshed to max
2. Use ExtraAttack actions (consume extra_attacks)
3. Action Surge → +1 action
4. Second Attack action → HasAttacked already present, **extra_attacks refreshed again**
5. Use ExtraAttack actions again

Each Attack action gets its full complement of Extra Attacks, exactly per D&D rules.

---

## Verification Commands

```bash
# Test all fighting styles
python examples/test_fighting_styles.py

# Test individual features
python examples/test_action_surge.py
python examples/test_indomitable.py
python examples/test_survivor.py

# Run all fighter tests
python -m pytest examples/test_*.py -k fighter -v
```
