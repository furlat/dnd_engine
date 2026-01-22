# Example and Test Writing Patterns

This document describes the correct patterns for writing examples and tests in this codebase. **Read this before writing any new example or test code.**

---

## Entity Creation

### Using Bestiary Factories

```python
from dnd.monsters.bestiary import create_goblin, create_skeleton

# CORRECT: Use keyword arguments
goblin = create_goblin(name="Goblin Scout", position=(0, 0))
skeleton = create_skeleton(name="Skeleton Warrior", position=(1, 0))

# WRONG: Positional arguments (first arg is source_id, not name!)
# goblin = create_goblin("Goblin Scout", position=(0, 0))  # ERROR!
```

### Clearing State Between Tests

```python
from dnd.entity import Entity

def reset_state():
    """Clear entity registries for a fresh test."""
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
```

Note: GridMap also needs resetting if used:
```python
from dnd.core.gridmap import reset_map
reset_map()
```

### Updating Senses

After creating entities, update their senses so they can see each other:

```python
# Update all entities at once
Entity.update_all_entities_senses()

# Or update a single entity
goblin.update_entity_senses()
```

This populates:
- `entity.senses.visible` - currently visible cells
- `entity.senses.paths` - paths to reachable cells
- `entity.senses.entities` - visible entities
- `entity.senses.seen` - memory of all cells ever seen (fog of war)

---

## Accessing Entity Properties

### Hit Points

```python
hp = entity.get_hp()  # Returns int
```

### Armor Class

```python
# Basic AC (no target context)
ac = entity.ac_bonus().normalized_score

# AC with target context (for contextual modifiers)
ac_bonus = entity.ac_bonus(attacker.uuid)
ac = ac_bonus.normalized_score
```

### Attack Bonus

```python
from dnd.blocks.equipment import WeaponSlot

# Basic attack bonus
attack_bonus = entity.attack_bonus(WeaponSlot.MAIN_HAND)
bonus = attack_bonus.normalized_score

# With target context
attack_bonus = entity.attack_bonus(WeaponSlot.MAIN_HAND, target.uuid)
```

### Ability Scores and Modifiers

```python
# Get strength modifier (returns int, NOT ModifiableValue)
str_mod = entity.ability_scores.strength.modifier

# Get any ability modifier by name
dex_mod = entity.ability_scores.get_modifier_from_name("dexterity")

# Get the underlying ability score value
str_score = entity.ability_scores.strength.ability_score.normalized_score
```

### Movement

```python
# Current movement (after conditions/modifiers)
movement = entity.action_economy.movement.normalized_score

# Base movement value
base_mod = entity.action_economy.movement.get_base_modifier()
base_speed = base_mod.value if base_mod else 30

# Check if can afford movement cost
can_move = entity.action_economy.can_afford("movement", cost)
```

### Action Economy

```python
# Check remaining resources
actions = entity.action_economy.actions.normalized_score
bonus_actions = entity.action_economy.bonus_actions.normalized_score
reactions = entity.action_economy.reactions.normalized_score

# Check affordability
can_attack = entity.action_economy.can_afford("actions", 1)

# Reset for new turn
entity.action_economy.reset_all_costs()
```

---

## Accessing Weapons

```python
from dnd.blocks.equipment import Weapon

# CORRECT: Access weapon attributes directly
weapon = entity.equipment.weapon_main_hand  # Returns Weapon or None
off_hand = entity.equipment.weapon_off_hand  # Returns Weapon, Shield, or None

# Check if off-hand is a weapon (not shield)
if isinstance(entity.equipment.weapon_off_hand, Weapon):
    off_hand_weapon = entity.equipment.weapon_off_hand

# WRONG: There is no get_weapon() method
# weapon = entity.equipment.get_weapon(WeaponSlot.MAIN_HAND)  # ERROR!
```

### Weapon Properties

```python
weapon = entity.equipment.weapon_main_hand
if weapon:
    name = weapon.name
    damage_dice = weapon.damage_dice
    damage_type = weapon.damage_type
    weapon_range = weapon.range
    properties = weapon.properties
```

---

## Cross-Entity Targeting (for Contextual Modifiers)

When testing conditions that have contextual effects (e.g., Frightened disadvantage only when frightener visible), you need to set up targeting:

```python
def get_attack_modifiers(attacker: Entity, target: Entity):
    """Get attack bonus with proper target setup."""
    attacker.set_target_entity(target.uuid)
    target.set_target_entity(attacker.uuid)

    attack_bonus = attacker.attack_bonus(WeaponSlot.MAIN_HAND, target.uuid)

    attacker.clear_target_entity()
    target.clear_target_entity()
    return attack_bonus


def get_defense_modifiers(defender: Entity, attacker: Entity):
    """
    Get combined modifiers when attacking a defender.
    Propagates to_target modifiers from defender to attacker.
    """
    defender.set_target_entity(attacker.uuid)
    attacker.set_target_entity(defender.uuid)

    attack_bonus = attacker.attack_bonus(WeaponSlot.MAIN_HAND, defender.uuid)
    ac_bonus = defender.ac_bonus(attacker.uuid)

    # KEY: Propagate to_target modifiers from defender to attacker
    attack_bonus.set_from_target(ac_bonus)

    defender.clear_target_entity()
    attacker.clear_target_entity()
    return attack_bonus
```

---

## Creating and Executing Actions

### Attack Action

```python
from dnd.actions import Attack
from dnd.blocks.equipment import WeaponSlot

attack = Attack(
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MAIN_HAND,
    name="Scimitar Attack"
)
event = attack.apply()

# Check result
if event.canceled:
    print(f"Attack canceled: {event.status_message}")
else:
    print(f"Outcome: {event.attack_outcome}")
    if event.damage_rolls:
        total_damage = sum(roll.total for roll in event.damage_rolls)
```

### Move Action

```python
from dnd.actions import Move

move = Move(
    source_entity_uuid=entity.uuid,
    end_position=(5, 3)
)
event = move.apply()

if event.canceled:
    print(f"Move canceled: {event.status_message}")
else:
    print(f"Moved to {entity.position}")
```

### Turn-Based Actions (Dash, Dodge, Disengage)

```python
from dnd.actions import Dash, Dodge, Disengage

# These apply conditions with 1-round duration
dash = Dash(source_entity_uuid=entity.uuid)
event = dash.apply()

# Check condition was applied
assert "Dashing" in entity.active_conditions
```

### Prone Actions

```python
from dnd.actions import StandUp, DropProne

# Drop prone (free action)
drop = DropProne(source_entity_uuid=entity.uuid)
drop.apply()
assert "Prone" in entity.active_conditions

# Stand up (costs half movement)
stand = StandUp(source_entity_uuid=entity.uuid)
stand.apply()
assert "Prone" not in entity.active_conditions
```

---

## Working with Conditions

### Applying Conditions

```python
from dnd.conditions import Blinded, Prone, Dashing

# Create condition (source = who caused it, target = who has it)
blinded = Blinded(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid
)
target.add_condition(blinded)

# Self-applied conditions
dashing = Dashing(
    source_entity_uuid=entity.uuid,
    target_entity_uuid=entity.uuid
)
entity.add_condition(dashing)
```

### Checking Conditions

```python
# Check by name
if "Blinded" in entity.active_conditions:
    blinded = entity.active_conditions["Blinded"]

# Check for any condition
has_any = len(entity.active_conditions) > 0
```

### Removing Conditions

```python
entity.remove_condition("Blinded")
```

### Setting Duration

```python
from dnd.core.base_conditions import DurationType

condition = Dashing(
    source_entity_uuid=entity.uuid,
    target_entity_uuid=entity.uuid
)
condition.duration.duration_type = DurationType.ROUNDS
condition.duration.duration = 1

entity.add_condition(condition)
```

---

## Working with Encounters

```python
from uuid import uuid4
from dnd.encounter import Encounter
from dnd.controller import PassController

# Create encounter (requires source_entity_uuid from BaseObject)
encounter = Encounter(name="Test Encounter", source_entity_uuid=uuid4())

# Add combatants with controllers
goblin_controller = PassController(source_entity_uuid=goblin.uuid)
skeleton_controller = PassController(source_entity_uuid=skeleton.uuid)

encounter.add_combatant(goblin, goblin_controller)
encounter.add_combatant(skeleton, skeleton_controller)

# Start combat
encounter.roll_initiative()
encounter.start_encounter()

# Start first turn
encounter.start_turn()
# ... entity takes actions ...

# Move to next combatant (ends current turn + starts next)
encounter.next_turn()

# NOTE: next_turn() calls end_turn() and start_turn() internally
# Don't call start_turn() after next_turn()!
```

---

## Test Structure Pattern

```python
class TestResult:
    """Tracks test results."""
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
    """Test description."""
    print("\n=== Test: Something ===")
    result = TestResult()

    # Setup
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    goblin = create_goblin(name="Goblin", position=(0, 0))
    Entity.update_all_entities_senses()

    # Test
    result.check(
        goblin.get_hp() > 0,
        f"Goblin has HP (got {goblin.get_hp()})"
    )

    return result.summary()
```

---

## Common Mistakes

| Mistake | Correct |
|---------|---------|
| `create_goblin("Name", ...)` | `create_goblin(name="Name", ...)` |
| `entity.equipment.get_weapon(slot)` | `entity.equipment.weapon_main_hand` |
| `entity.ability_scores.strength.modifier.normalized_score` | `entity.ability_scores.strength.modifier` |
| `EventQueue.clear_all()` | Clear individual registries or don't clear |
| Forgetting `update_entity_senses()` | Always call after creating entities |
| Using `attacker.attack_bonus(slot)` for contextual checks | Use `set_target_entity()` first |

---

## GridMap Setup

```python
from dnd.core.gridmap import reset_map, get_map

reset_map()  # Clear previous state
grid = get_map()

# Create a simple rectangular floor
grid.create_rectangle(0, 0, 15, 15)

# Create a room with walls
grid.create_room(0, 0, 10, 10)
```
