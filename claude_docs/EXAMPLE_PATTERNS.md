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
from dnd.core.events import WeaponSlot

# Basic attack bonus
attack_bonus = entity.attack_bonus(WeaponSlot.MELEE_MAIN)
bonus = attack_bonus.normalized_score

# With target context
attack_bonus = entity.attack_bonus(WeaponSlot.MELEE_MAIN, target.uuid)
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
from dnd.blocks.equipment import Weapon, Shield, WeaponSlot

# Access weapon by slot attribute
weapon = entity.equipment.weapon_melee_main  # Returns Weapon or None
off_hand = entity.equipment.weapon_melee_off  # Returns Weapon, Shield, or None

# 4 weapon slots available:
# - weapon_melee_main: Main melee weapon
# - weapon_melee_off: Off-hand melee weapon OR shield
# - weapon_ranged_main: Main ranged weapon
# - weapon_ranged_off: Off-hand ranged weapon

# Check if off-hand is a weapon (not shield)
if isinstance(entity.equipment.weapon_melee_off, Weapon):
    off_hand_weapon = entity.equipment.weapon_melee_off

# Use _get_weapon_by_slot for slot-based access (internal method)
from dnd.core.events import WeaponSlot
weapon = entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
```

### Weapon Properties

```python
weapon = entity.equipment.weapon_melee_main
if weapon:
    name = weapon.name
    damage_dice = weapon.damage_dice
    damage_type = weapon.damage_type
    weapon_range = weapon.range
    properties = weapon.properties  # List of WeaponProperty enum values
```

---

## Cross-Entity Targeting (for Contextual Modifiers)

When testing conditions that have contextual effects (e.g., Frightened disadvantage only when frightener visible), you need to set up targeting:

```python
def get_attack_modifiers(attacker: Entity, target: Entity):
    """Get attack bonus with proper target setup."""
    from dnd.core.events import WeaponSlot

    attacker.set_target_entity(target.uuid)
    target.set_target_entity(attacker.uuid)

    attack_bonus = attacker.attack_bonus(WeaponSlot.MELEE_MAIN, target.uuid)

    attacker.clear_target_entity()
    target.clear_target_entity()
    return attack_bonus


def get_defense_modifiers(defender: Entity, attacker: Entity):
    """
    Get combined modifiers when attacking a defender.
    Propagates to_target modifiers from defender to attacker.
    """
    from dnd.core.events import WeaponSlot

    defender.set_target_entity(attacker.uuid)
    attacker.set_target_entity(defender.uuid)

    attack_bonus = attacker.attack_bonus(WeaponSlot.MELEE_MAIN, defender.uuid)
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
from dnd.core.events import WeaponSlot

attack = Attack(
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
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
| `entity.equipment.weapon_main_hand` | `entity.equipment.weapon_melee_main` |
| `WeaponSlot.MAIN_HAND` | `WeaponSlot.MELEE_MAIN` |
| `entity.ability_scores.strength.modifier.normalized_score` | `entity.ability_scores.strength.modifier` (returns int) |
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

---

## Faction System

### Creating Entities with Factions

```python
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity

# Create entities with faction assignment
hero1 = create_skeleton(name="Hero 1", position=(0, 0), faction="heroes")
hero2 = create_skeleton(name="Hero 2", position=(1, 0), faction="heroes")
enemy1 = create_skeleton(name="Enemy 1", position=(5, 0), faction="monsters")
enemy2 = create_skeleton(name="Enemy 2", position=(5, 1), faction="monsters")

Entity.update_all_entities_senses()

# Faction relationship checks
hero1.is_ally(hero2)    # True - same faction
hero1.is_enemy(enemy1)  # True - different faction
hero1.is_ally(enemy1)   # False

# Get visible enemies/allies (returns Dict[UUID, Tuple[int, int]])
enemies = hero1.get_visible_enemies()  # {enemy1.uuid: (5,0), enemy2.uuid: (5,1)}
allies = hero1.get_visible_allies()    # {hero2.uuid: (1,0)}

# Include dead entities (for targeting healing spells, etc.)
all_allies = hero1.get_visible_allies(include_dead=True)

# Class methods for faction queries
Entity.get_entities_by_faction("heroes")  # [hero1, hero2]
Entity.get_alive_by_faction("heroes")     # Only alive heroes
```

### Faction-Based Action Targeting

```python
# Get available actions filtered by faction
actions = hero1.get_available_actions(target_filter="enemies")  # Default
ally_actions = hero1.get_available_actions(target_filter="allies")
all_actions = hero1.get_available_actions(target_filter="all")

# Actions include valid_targets filtered by faction
for attack in actions.entity_actions:
    print(f"{attack.name}: targets {attack.valid_targets}")
```

---

## Test Utilities

The `dnd/utils/test_utils.py` module provides reusable helpers. **USE THESE** instead of writing your own.

### Available Functions

```python
from dnd.utils import (
    # State management
    reset_combat_state,      # Clear all registries for fresh test
    setup_combat_arena,      # Create encounter with two entities

    # HP manipulation
    get_hp,                  # Get current HP
    get_max_hp,              # Get max HP
    set_hp,                  # Set HP to specific value
    heal_entity,             # Heal by amount
    deal_damage_to,          # Deal typed damage (fires events)

    # Attack forcing (for deterministic tests)
    force_attack_hit,        # +100 attack bonus
    force_attack_miss,       # -100 attack penalty
    force_attack_crit,       # AUTOCRIT modifier
    remove_attack_modifier,  # Remove forced modifier

    # Position/movement
    get_position,            # Get entity position
    move_entity,             # Teleport entity (bypasses movement)

    # Conditions
    has_condition,           # Check if entity has condition by name
    count_conditions,        # Count conditions with name

    # Debug output
    print_combat_state,      # Print HP and conditions for two entities
)
```

### Example Usage

```python
from dnd.utils import (
    reset_combat_state, setup_combat_arena,
    force_attack_hit, get_hp, set_hp, has_condition
)
from dnd.monsters.bestiary import create_skeleton

# Fresh test setup
reset_combat_state()

attacker = create_skeleton(name="Attacker", position=(0, 0))
target = create_skeleton(name="Target", position=(1, 0))
encounter = setup_combat_arena(attacker, target)

# Force deterministic outcomes
mod_uuid = force_attack_hit(attacker)

# Manipulate HP for specific test scenarios
set_hp(target, 5)  # Low HP for kill test

# Check conditions
if has_condition(target, "Prone"):
    print("Target is prone")

# Clean up forced modifier after test
from dnd.utils import remove_attack_modifier
remove_attack_modifier(attacker, mod_uuid)
```

---

## Multi-Entity Encounters

### Creating a 2v2 Encounter

```python
from uuid import uuid4
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.encounter import Encounter
from dnd.controller import PassController
from dnd.utils import reset_combat_state

reset_combat_state()

# Create teams with factions
hero1 = create_skeleton(name="Hero 1", position=(0, 0), faction="heroes")
hero2 = create_skeleton(name="Hero 2", position=(1, 0), faction="heroes")
enemy1 = create_skeleton(name="Enemy 1", position=(5, 0), faction="monsters")
enemy2 = create_skeleton(name="Enemy 2", position=(5, 1), faction="monsters")

Entity.update_all_entities_senses()

# Build encounter with all combatants
encounter = Encounter(name="Team Battle", source_entity_uuid=uuid4())

combatants = [hero1, hero2, enemy1, enemy2]
for entity in combatants:
    controller = PassController(source_entity_uuid=entity.uuid)
    encounter.add_combatant(entity, controller)

# Start combat
encounter.roll_initiative()
encounter.start_encounter()
encounter.start_turn()

# Get current combatant
current = encounter.get_current_entity()
print(f"Turn: {current.name}")

# Encounter ends when only one faction has survivors
```

### Encounter Turn Flow

```python
# Each combatant's turn
while not encounter.state == EncounterState.ENDED:
    current = encounter.get_current_entity()

    # Get actions targeting enemies only
    actions = current.get_available_actions(target_filter="enemies")

    # ... execute actions ...

    # Advance to next turn (handles death checks, faction victory)
    encounter.next_turn()
```

---

## Untested Scenarios (Supported but Need Verification)

The following multi-entity scenarios are implemented but not thoroughly tested:

- PvP with multiple agents per player
- User + Claude on same team vs AI
- Claude controlling multiple entities
- User controlling multiple entities

Use `examples/test_faction_system.py` as a starting point for testing these.
