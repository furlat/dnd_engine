# Available Actions System Design

## Purpose

Query system to determine what actions an entity can currently perform, given:
- Current action economy state (remaining actions, bonus actions, reactions, movement)
- Active conditions (Incapacitated, Grappled, etc.)
- Equipment (weapons determine attack options)
- Senses (visible targets, reachable positions)

This feeds into:
- **UI**: Show player what they can do, highlight valid targets/positions
- **AI**: Decision-making input for automated controllers
- **Pre-validation**: Quick check before attempting an action

---

## Complete D&D 5e Action Reference (from SRD)

### Standard Actions (Cost: 1 Action)

| Action | SRD Effect | Target | Implementation Status |
|--------|------------|--------|----------------------|
| **Attack** | Make one melee or ranged attack | Entity in range + LOS | ✅ Implemented |
| **Cast a Spell** | Cast a spell with 1 action casting time | Varies | ❌ Future (spells) |
| **Dash** | Gain extra movement = your speed | Self | 🔶 Condition exists, need action class |
| **Disengage** | Movement doesn't provoke OAs this turn | Self | ❌ Not implemented |
| **Dodge** | Attackers disadvantage, advantage on DEX saves | Self | 🔶 Condition exists, need action class |
| **Help** | Ally gets advantage on next check/attack vs target | Ally within 5ft | ❌ Not implemented |
| **Hide** | Stealth check to become hidden | Self | ❌ Not implemented (needs stealth system) |
| **Ready** | Hold action for trigger, use reaction | Varies | ❌ Complex, skip for now |
| **Search** | Perception or Investigation check | Area | ❌ Not implemented |
| **Use an Object** | Interact with item requiring action | Object | ❌ Not implemented |

### Special Attack Options (Replace one attack in Attack action)

| Action | SRD Effect | Target | Implementation Status |
|--------|------------|--------|----------------------|
| **Grapple** | Athletics vs Athletics/Acrobatics, target Grappled | Creature ≤1 size larger, in reach | ❌ Not implemented |
| **Shove** | Athletics vs Athletics/Acrobatics, prone OR push 5ft | Creature ≤1 size larger, in reach | ❌ Not implemented |

### Bonus Actions

| Action | SRD Effect | Requirement | Implementation Status |
|--------|------------|-------------|----------------------|
| **Two-Weapon Fighting** | Attack with light off-hand weapon (no ability mod to damage) | Attacked with light weapon in main hand this turn | ❌ Not implemented |
| **Class abilities** | Cunning Action (Rogue), etc. | Class feature | ❌ Future |

### Reactions (Cost: 1 Reaction)

| Action | SRD Trigger | Effect | Implementation Status |
|--------|-------------|--------|----------------------|
| **Opportunity Attack** | Hostile creature leaves your reach | One melee attack | ✅ Implemented |

### Movement Options (Cost: Movement, not actions)

| Action | Cost | Effect | Implementation Status |
|--------|------|--------|----------------------|
| **Move** | 5ft per tile | Move to reachable position | ✅ Implemented |
| **Stand Up** | Half your speed | Remove Prone condition | ❌ Need to implement |
| **Drop Prone** | 0 (free) | Gain Prone condition | ❌ Need to implement |
| **Mount/Dismount** | Half your speed | Get on/off mount | ❌ Future |

### Free Actions (No cost, once per turn)

| Action | Effect | Implementation Status |
|--------|--------|----------------------|
| **Object Interaction** | Draw weapon, open door, etc. | ❌ Future |
| **Communicate** | Brief utterance | N/A (flavor) |

---

## What We'll Implement Now

### Phase 1: Core Query System

| Action | Cost | Targeting | Priority |
|--------|------|-----------|----------|
| **Attack** | 1 action | Entity (weapon range + LOS) | ✅ Query only |
| **Move** | movement | Position (from senses.paths) | ✅ Query only |
| **Dash** | 1 action | Self | ✅ Query + Action class |
| **Dodge** | 1 action | Self | ✅ Query + Action class |
| **Disengage** | 1 action | Self | ✅ Query + Action class |
| **Stand Up** | half movement | Self (if Prone) | ✅ Query + Action class |
| **Drop Prone** | 0 | Self (if not Prone) | ✅ Query + Action class |

### Phase 2: Later

| Action | Notes |
|--------|-------|
| **Help** | Needs ally tracking |
| **Search** | Needs perception system |
| **Hide** | Needs stealth system |
| **Grapple/Shove** | Needs contest system |
| **Two-Weapon Fighting** | Needs attack tracking per turn |

---

## Current Implementation State

### Existing Actions

| Action | Class | Cost Type | Cost Amount | Target Type |
|--------|-------|-----------|-------------|-------------|
| Attack | `Attack` | actions | 1 | Entity (UUID) |
| Move | `Move` | movement | path length × 5 | Position (Tuple) |

### Condition-Based "Actions"

These are conditions applied to self, not traditional actions:

| Condition | Effect | How Applied |
|-----------|--------|-------------|
| `Dashing` | +movement equal to base speed | Needs Dash action |
| `Dodging` | Advantage DEX saves, attackers disadvantage | Needs Dodge action |

### Conditions That Block Actions

| Condition | Effect on Action Economy |
|-----------|-------------------------|
| `Incapacitated` | All economy set to 0 (can't do anything) |
| `Grappled` | Speed max = 0 (can't move) |
| `Restrained` | Speed = 0, disadvantage attacks |
| `Stunned` | Includes Incapacitated |
| `Paralyzed` | Includes Incapacitated |
| `Unconscious` | Includes Incapacitated |
| `Prone` | Movement costs double to stand |

### Action Economy State

From `ActionEconomy`:
```python
actions: ModifiableValue        # Default 1
bonus_actions: ModifiableValue  # Default 1
reactions: ModifiableValue      # Default 1
movement: ModifiableValue       # Default 30

can_afford(cost_type, amount) -> bool
```

### Senses State

From `Senses`:
```python
entities: Dict[UUID, Tuple[int,int]]  # Visible entities + positions
paths: Dict[Tuple[int,int], List[Tuple[int,int]]]  # Reachable positions + paths
position: Tuple[int,int]  # Current position

get_feet_distance(position) -> int  # Distance in feet
```

---

## Design

### Core Data Structure

```python
from pydantic import BaseModel
from typing import List, Dict, Optional, Tuple, Literal
from uuid import UUID

ActionCategory = Literal["action", "bonus_action", "reaction", "movement", "free"]

class AvailableAction(BaseModel):
    """Represents a single action the entity can take."""

    # Identity
    action_id: str  # Unique identifier: "attack_main_hand", "move", "dash", etc.
    name: str       # Display name: "Attack (Longsword)", "Move", "Dash"
    description: str

    # Cost
    cost_type: CostType  # "actions", "bonus_actions", "reactions", "movement"
    cost_amount: int     # How much it costs
    can_afford: bool     # Can entity currently afford this?

    # Targeting - one of these will be populated based on action type
    requires_target: bool = False
    valid_targets: List[UUID] = []           # For targeted actions (Attack)
    valid_positions: List[Tuple[int, int]] = []  # For movement

    # Metadata for UI/AI
    category: ActionCategory  # Grouping for UI display
    weapon_slot: Optional[WeaponSlot] = None  # For attacks

    # Pre-computed outcomes (optional, for AI evaluation)
    # These would be filled by a separate evaluation function
    # hit_chance: Optional[float] = None
    # expected_damage: Optional[float] = None
```

### Main Query Interface

```python
class AvailableActionsResult(BaseModel):
    """Complete result of available actions query."""

    entity_uuid: UUID

    # Grouped by category for easy UI rendering
    attacks: List[AvailableAction] = []
    movement: List[AvailableAction] = []  # Single item with all valid positions
    other_actions: List[AvailableAction] = []  # Dash, Dodge, etc.
    bonus_actions: List[AvailableAction] = []
    reactions: List[AvailableAction] = []
    free_actions: List[AvailableAction] = []

    # Summary
    can_attack: bool = False
    can_move: bool = False
    remaining_movement: int = 0

    # Blocking conditions (for UI display: "You are Incapacitated")
    blocking_conditions: List[str] = []


def get_available_actions(entity: Entity) -> AvailableActionsResult:
    """
    Main entry point. Returns all actions available to entity.
    """
```

### Implementation Logic

#### Step 1: Check Blocking Conditions

```python
def _get_blocking_conditions(entity: Entity) -> Tuple[bool, bool, List[str]]:
    """
    Returns:
        can_act: bool - Can take any actions at all
        can_move: bool - Can move
        blocking: List[str] - Names of blocking conditions
    """
    blocking = []
    can_act = True
    can_move = True

    # Incapacitated and its sub-conditions
    if "Incapacitated" in entity.active_conditions:
        can_act = False
        can_move = False
        blocking.append("Incapacitated")

    # These include Incapacitated
    for cond in ["Stunned", "Paralyzed", "Unconscious"]:
        if cond in entity.active_conditions:
            can_act = False
            can_move = False
            blocking.append(cond)

    # Movement blockers
    if "Grappled" in entity.active_conditions:
        can_move = False
        blocking.append("Grappled")

    if "Restrained" in entity.active_conditions:
        can_move = False
        blocking.append("Restrained")

    return can_act, can_move, blocking
```

#### Step 2: Get Attack Options

```python
def _get_attack_options(entity: Entity) -> List[AvailableAction]:
    """Get all attack actions available."""
    attacks = []

    # Check if can afford action
    can_afford_action = entity.action_economy.can_afford("actions", 1)

    # Check each weapon slot
    for slot in [WeaponSlot.MAIN_HAND, WeaponSlot.OFF_HAND]:
        weapon = entity.equipment.get_weapon(slot)
        if weapon is None:
            continue

        # Get valid targets
        valid_targets = _get_valid_attack_targets(entity, weapon)

        attacks.append(AvailableAction(
            action_id=f"attack_{slot.value.lower().replace(' ', '_')}",
            name=f"Attack ({weapon.name})",
            description=f"{weapon.dice_numbers}d{weapon.damage_dice} {weapon.damage_type.value}",
            cost_type="actions",
            cost_amount=1,
            can_afford=can_afford_action and len(valid_targets) > 0,
            requires_target=True,
            valid_targets=valid_targets,
            category="action",
            weapon_slot=slot
        ))

    # Unarmed strike (always available if no weapons)
    if not attacks:
        valid_targets = _get_valid_melee_targets(entity, reach=5)
        attacks.append(AvailableAction(
            action_id="attack_unarmed",
            name="Unarmed Strike",
            description="1 + STR modifier bludgeoning",
            cost_type="actions",
            cost_amount=1,
            can_afford=can_afford_action and len(valid_targets) > 0,
            requires_target=True,
            valid_targets=valid_targets,
            category="action"
        ))

    return attacks


def _get_valid_attack_targets(entity: Entity, weapon: Weapon) -> List[UUID]:
    """Get entities that can be attacked with this weapon."""
    targets = []
    weapon_range = weapon.range

    for target_uuid, target_pos in entity.senses.entities.items():
        if target_uuid == entity.uuid:
            continue  # Can't attack self

        distance = entity.senses.get_feet_distance(target_pos)

        if weapon_range.type == RangeType.REACH:
            # Melee: within 5ft (or weapon reach)
            if distance <= weapon_range.normal:
                targets.append(target_uuid)
        else:
            # Ranged: within normal range (no disadvantage check here)
            if distance <= weapon_range.long:
                targets.append(target_uuid)

    return targets
```

#### Step 3: Get Movement Options

```python
def _get_movement_options(entity: Entity, can_move: bool) -> List[AvailableAction]:
    """Get movement action with all valid positions."""
    if not can_move:
        return []

    remaining = entity.action_economy.movement.normalized_score
    if remaining <= 0:
        return []

    # Check for Prone (costs double to move)
    is_prone = "Prone" in entity.active_conditions
    movement_multiplier = 2 if is_prone else 1

    # Filter paths by remaining movement
    valid_positions = []
    for pos, path in entity.senses.paths.items():
        cost = len(path) * 5 * movement_multiplier
        if cost <= remaining:
            valid_positions.append(pos)

    if not valid_positions:
        return []

    return [AvailableAction(
        action_id="move",
        name="Move",
        description=f"{remaining}ft remaining",
        cost_type="movement",
        cost_amount=0,  # Variable, depends on destination
        can_afford=True,
        requires_target=False,
        valid_positions=valid_positions,
        category="movement"
    )]
```

#### Step 4: Get Other Standard Actions

```python
def _get_other_actions(entity: Entity, can_act: bool) -> List[AvailableAction]:
    """Get Dash, Dodge, Disengage, etc."""
    if not can_act:
        return []

    can_afford = entity.action_economy.can_afford("actions", 1)
    actions = []

    # Dash - always available if can act
    base_movement = entity.action_economy.get_base_value("movement")
    actions.append(AvailableAction(
        action_id="dash",
        name="Dash",
        description=f"Gain {base_movement}ft extra movement",
        cost_type="actions",
        cost_amount=1,
        can_afford=can_afford,
        category="action"
    ))

    # Dodge - always available if can act
    actions.append(AvailableAction(
        action_id="dodge",
        name="Dodge",
        description="Attackers have disadvantage, advantage on DEX saves",
        cost_type="actions",
        cost_amount=1,
        can_afford=can_afford,
        category="action"
    ))

    # Disengage - always available if can act
    actions.append(AvailableAction(
        action_id="disengage",
        name="Disengage",
        description="Movement doesn't provoke opportunity attacks",
        cost_type="actions",
        cost_amount=1,
        can_afford=can_afford,
        category="action"
    ))

    # Help - needs ally within 5ft (future)
    # Hide - needs cover/concealment (future)
    # Search - always available (future)
    # Use Object - always available (future)
    # Ready - always available (future)

    return actions


def _get_prone_actions(entity: Entity, can_move: bool) -> List[AvailableAction]:
    """Get Stand Up and Drop Prone actions."""
    actions = []
    is_prone = "Prone" in entity.active_conditions
    remaining_movement = entity.action_economy.movement.normalized_score
    base_movement = entity.action_economy.get_base_value("movement")
    half_movement = base_movement // 2

    if is_prone and can_move:
        # Stand Up - costs half your base movement
        can_stand = remaining_movement >= half_movement
        actions.append(AvailableAction(
            action_id="stand_up",
            name="Stand Up",
            description=f"Costs {half_movement}ft movement",
            cost_type="movement",
            cost_amount=half_movement,
            can_afford=can_stand,
            category="movement"
        ))
    elif not is_prone:
        # Drop Prone - always free
        actions.append(AvailableAction(
            action_id="drop_prone",
            name="Drop Prone",
            description="Drop to the ground (free)",
            cost_type="movement",
            cost_amount=0,
            can_afford=True,
            category="free"
        ))

    return actions
```

#### Step 5: Main Query Function

```python
def get_available_actions(entity: Entity) -> AvailableActionsResult:
    """Get all available actions for an entity."""

    # Step 1: Check blocking conditions
    can_act, can_move, blocking = _get_blocking_conditions(entity)

    # Step 2: Get action economy state
    remaining_movement = entity.action_economy.movement.normalized_score

    # Step 3: Gather actions by category
    attacks = _get_attack_options(entity) if can_act else []
    movement = _get_movement_options(entity, can_move)
    other_actions = _get_other_actions(entity, can_act)
    prone_actions = _get_prone_actions(entity, can_move)

    # Separate prone actions into movement vs free
    movement_actions = [a for a in prone_actions if a.category == "movement"]
    free_actions = [a for a in prone_actions if a.category == "free"]

    # Combine movement with stand up if applicable
    all_movement = movement + movement_actions

    # Determine can_attack and can_move flags
    can_attack = any(a.can_afford and a.valid_targets for a in attacks)
    has_movement = len(movement) > 0 and movement[0].valid_positions

    return AvailableActionsResult(
        entity_uuid=entity.uuid,
        attacks=attacks,
        movement=all_movement,
        other_actions=other_actions,
        bonus_actions=[],  # Future: two-weapon fighting, etc.
        reactions=[],      # Future: opportunity attack readiness
        free_actions=free_actions,
        can_attack=can_attack,
        can_move=has_movement,
        remaining_movement=remaining_movement,
        blocking_conditions=blocking
    )
```

---

## File Location

New file: `dnd/available_actions.py`

This keeps it separate from the action execution code in `actions.py`. The query system is read-only - it doesn't execute actions, just reports what's possible.

---

## Integration with Encounter

```python
# In Encounter or Controller

def get_turn_options(entity: Entity) -> AvailableActionsResult:
    """Called at turn start or when UI needs to refresh options."""
    # Make sure senses are up to date
    entity.update_entity_senses()
    return get_available_actions(entity)

# In TurnContext (controller.py)
class TurnContext(BaseObject):
    # ... existing fields ...
    available_actions: Optional[AvailableActionsResult] = None
```

---

## What We're NOT Doing (Yet)

1. **AI Evaluation** - Computing hit chance, expected damage. That's a separate layer on top.
2. **Bonus Actions** - Two-weapon fighting, cunning action, etc. Need attack tracking per turn.
3. **Reactions** - Opportunity attacks are event-driven, not queried.
4. **Complex Targeting** - Area effects, multi-target. Only single-target attacks for now.
5. **Difficult Terrain** - Would affect movement cost calculation.
6. **Cover/Concealment** - Would affect attack validity.
7. **Help Action** - Needs ally tracking (who is friendly vs hostile).
8. **Hide Action** - Needs stealth/perception system.
9. **Grapple/Shove** - Needs contest system (opposed skill checks).
10. **Ready Action** - Complex trigger system, holds action for reaction.

---

## Implementation Order

### Part A: Query System (`available_actions.py`)

1. **Data structures** - `AvailableAction`, `AvailableActionsResult`
2. **Blocking conditions check** - `_get_blocking_conditions()`
3. **Attack options** - `_get_attack_options()`, `_get_valid_attack_targets()`
4. **Movement options** - `_get_movement_options()`
5. **Other actions** - `_get_other_actions()` (Dash, Dodge, Disengage)
6. **Prone actions** - `_get_prone_actions()` (Stand Up, Drop Prone)
7. **Main query** - `get_available_actions()`

### Part B: New Action Classes (`actions.py`)

We need action classes that apply the conditions:

| Action | Applies Condition | Duration | Notes |
|--------|-------------------|----------|-------|
| `Dash` | `Dashing` | 1 round | Condition already adds movement |
| `Dodge` | `Dodging` | 1 round | Condition already adds defensive bonuses |
| `Disengage` | `Disengaging` | 1 round | Need new condition that prevents OA triggers |
| `StandUp` | Removes `Prone` | N/A | Costs half movement |
| `DropProne` | Adds `Prone` | Permanent | Free action (until you stand up) |

**Action Implementation Pattern:**

```python
class Dash(BaseAction):
    """Take the Dash action - gain extra movement equal to your speed."""
    name: str = Field(default="Dash")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Dash Cost", cost_type="actions", cost=1,
             evaluator=entity_action_economy_cost_evaluator)
    ])

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)

        # Create condition with 1 round duration
        dashing = Dashing(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid  # Self-targeted
        )
        dashing.duration.duration_type = DurationType.ROUNDS
        dashing.duration.duration = 1

        entity.add_condition(dashing)

        return execution_event.phase_to(EventPhase.COMPLETION, ...)
```

### Part C: New Conditions (`conditions.py`)

| Condition | Effect | Duration |
|-----------|--------|----------|
| `Disengaging` | Movement doesn't provoke opportunity attacks | 1 round |

**Duration Design Decision:**
- All turn-based conditions (Dashing, Dodging, Disengaging) use `duration_type=ROUNDS, duration=1`
- Conditions are advanced at **START of turn** (not end)
- Effect: Condition lasts from when applied until start of your next turn
- This is SRD-accurate for Dodge, slightly buffs Dash/Disengage (acceptable)

### Part D: Integration

1. **Move condition advancement to start of turn** (`encounter.py`)
   - Currently: `_advance_entity_conditions()` called in `end_turn()`
   - Change: Call it in `start_turn()` instead
   - This makes Dodge work correctly per SRD

2. **Update `reactions.py`** to check for `Disengaging` condition:
   ```python
   # In opportunity_attack_processor, after checking same entity:
   if "Disengaging" in event_source_entity.active_conditions:
       return event  # Disengage prevents opportunity attacks
   ```

3. Add `available_actions` to `TurnContext`
4. Test with encounter system

---

## Open Questions

1. **Should we create actual Action objects or just descriptors?**
   - **Decision**: Descriptors only. Controller creates actual Action when chosen.
   - Rationale: Lighter weight, avoids creating objects that may never be used.

2. **How to handle movement to specific positions?**
   - **Decision**: Return list of all valid positions, let UI/AI pick one.
   - Rationale: UI can highlight all options, AI can evaluate each.

3. **Should Dash/Dodge/Disengage be actual Action classes?**
   - **Decision**: Yes. Create `Dash`, `Dodge`, `Disengage`, `StandUp`, `DropProne` action classes.
   - These apply the corresponding conditions and consume appropriate costs.

4. **How to track "attacked this turn" for Two-Weapon Fighting?**
   - **Defer**: This requires turn-level state tracking. Not implementing now.
   - Could add `attacks_this_turn: List[UUID]` to TurnContext later.

---

## Dependencies

Uses existing:
- `Entity`, `Entity.senses`, `Entity.action_economy`, `Entity.active_conditions`
- `Weapon`, `WeaponSlot`, `RangeType`, `Range`
- `CostType` from `base_actions.py`
- `Dashing`, `Dodging`, `Prone` conditions

New:
- `Disengaging` condition (needs to be created)

---

## Summary

### Files to Create/Modify

| File | Changes |
|------|---------|
| `dnd/available_actions.py` | **NEW** - Query system |
| `dnd/actions.py` | Add `Dash`, `Dodge`, `Disengage`, `StandUp`, `DropProne` actions |
| `dnd/conditions.py` | Add `Disengaging` condition |
| `dnd/reactions.py` | Check for `Disengaging` in opportunity attack logic |
| `dnd/controller.py` | Add `available_actions` to `TurnContext` |

### Action Summary Table

| Action ID | Cost Type | Cost | Requires Target | Notes |
|-----------|-----------|------|-----------------|-------|
| `attack_main_hand` | actions | 1 | Yes (entity) | Weapon attack |
| `attack_off_hand` | actions | 1 | Yes (entity) | Weapon attack |
| `attack_unarmed` | actions | 1 | Yes (entity) | 1 + STR bludgeoning |
| `move` | movement | varies | Yes (position) | 5ft per tile |
| `dash` | actions | 1 | No | Applies Dashing |
| `dodge` | actions | 1 | No | Applies Dodging |
| `disengage` | actions | 1 | No | Applies Disengaging |
| `stand_up` | movement | half base | No | Removes Prone, requires Prone |
| `drop_prone` | free | 0 | No | Applies Prone, requires not Prone |
