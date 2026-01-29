# Movement and AoE Targeting Plan

## Overview

This document plans systems that will unlock a large portion of sorcerer spells and improve combat mechanics significantly.

### Systems to Implement (This Plan)

1. **Jump Action** - Bonus action movement without path requirement (foundational for AoE targeting)
2. **Shove Action** - Contested push with forced movement
3. **AoE Targeting System** - Cone, sphere, line, cube targeting for spells

### Out of Scope (Future Spatial Systems)

The following are deferred to a unified "3D Spatial System" implementation:

1. **Terrain Effects** - Ground hazards, difficult terrain, tile conditions (Fog Cloud, Web, Wall of Fire)
2. **Swimming/Burrowing/Flying** - Alternative movement types requiring terrain/elevation
3. **Light System + Hiding + Cover + Z-Axis/Verticality** - All require 3D spatial consideration; implement once together

---

## Current Targeting Model

```
Movement: source_position → target_position + path (contiguous walkable tiles)
Attack:   source_entity → target_entity (with range/LOS check)
Spell:    source_entity → target_entity OR self (single target)
```

### Proposed Targeting Model Evolution

```
1. Jump:     source_position → target_position (visible + walkable, NO path required)
2. Shove:    source_entity → target_entity → forced_position (push direction + distance)
3. AoE:      source_position → target_position + shape → affected_positions[]
```

---

## Phase 1: Jump Action (BG3-Style)

### Mechanics

| Property | Value |
|----------|-------|
| **Cost** | Bonus Action + Movement (distance jumped) |
| **Base Range** | 15 ft (3 tiles) |
| **Scaling** | +5 ft per 2 STR above 10 |
| **Requirements** | Target must be visible + walkable + unoccupied |
| **Does NOT require** | Path to destination |

### Range Calculation

```python
def get_jump_range(entity: Entity) -> int:
    """Return jump range in feet."""
    base_range = 15
    str_score = entity.ability_scores.strength.score
    str_bonus = max(0, (str_score - 10) // 2) * 5  # +5ft per 2 STR above 10

    # Apply modifiers from conditions (Enhance Leap, Athlete, etc.)
    jump_range = entity.jump_range  # ModifiableValue
    jump_range.base_value = base_range + str_bonus

    return jump_range.normalized_score
```

### Example Ranges by Strength

| STR | Base | Bonus | Total Range |
|-----|------|-------|-------------|
| 8   | 15ft | 0     | 15 ft |
| 10  | 15ft | 0     | 15 ft |
| 12  | 15ft | 5ft   | 20 ft |
| 14  | 15ft | 10ft  | 25 ft |
| 16  | 15ft | 15ft  | 30 ft |
| 18  | 15ft | 20ft  | 35 ft |
| 20  | 15ft | 25ft  | 40 ft |

### Implementation Components

#### 1. New Targeting Type: PositionInRange

```python
class PositionTargeting(Enum):
    PATH_REQUIRED = "path_required"      # Current movement
    LOS_ONLY = "los_only"                # Jump, teleport
    ANY_IN_RANGE = "any_in_range"        # Some AoE origins
```

#### 2. Senses Extension

```python
# In Senses block, add:
def get_jumpable_positions(self, max_range: int) -> Dict[Tuple[int, int], bool]:
    """
    Return positions that can be jumped to.
    Requirements: visible + walkable + unoccupied + within range.
    Does NOT require path.
    """
    jumpable = {}
    for pos in self.visible:
        if not self.visible[pos]:
            continue
        distance = self.get_feet_distance(pos)
        if distance > max_range:
            continue
        if not GridMap.get_map().is_walkable_for(self.owner.uuid, pos):
            continue
        if GridMap.get_map().get_entities_at(pos):
            continue  # Occupied
        jumpable[pos] = True
    return jumpable
```

#### 3. Jump Action

```python
class Jump(BaseAction):
    name: str = "Jump"
    description: str = "Jump to a visible location within range"
    costs: List[BaseCost] = [BonusActionCost()]

    def _validate(self, event: ActionEvent) -> EventPhase:
        entity = Entity.get(self.source_entity_uuid)
        target_pos = event.target_position

        jump_range = get_jump_range(entity)
        distance = entity.senses.get_feet_distance(target_pos)

        # Check movement cost
        if distance > entity.action_economy.movement.normalized_score:
            return EventPhase.CANCEL  # Not enough movement

        # Check jumpable
        jumpable = entity.senses.get_jumpable_positions(jump_range)
        if target_pos not in jumpable:
            return EventPhase.CANCEL

        return EventPhase.EXECUTION

    def _apply(self, event: ActionEvent) -> Event:
        entity = Entity.get(self.source_entity_uuid)
        distance = entity.senses.get_feet_distance(event.target_position)

        # Deduct movement
        entity.action_economy.movement.base_value -= distance

        # Move entity (no path, direct placement)
        GridMap.get_map().move_entity(entity.uuid, event.target_position)
        entity.senses.position = event.target_position

        # Fire spatial events
        # SPATIAL_ENTITY_LEFT for old position
        # SPATIAL_ENTITY_ENTERED for new position

        return event.phase_to(EventPhase.COMPLETION)
```

#### 4. JumpEvent

```python
class JumpEvent(ActionEvent):
    name: str = "Jump"
    target_position: Tuple[int, int]
    distance_feet: int
    # No path field - that's the key difference from MovementEvent
```

### Modifiers for Jump Range

Conditions that can modify jump range (via `entity.jump_range` ModifiableValue):

| Condition | Effect | Implementation |
|-----------|--------|----------------|
| EnhanceLeap | +200% range | Multiplier modifier |
| Athlete | +50% range | Multiplier modifier |
| Encumbered | -50% range | Multiplier modifier |
| Jump (spell) | x3 range | Multiplier modifier |

### Why Jump is Foundational for AoE

Jump introduces **"target a position without a path"** which is the same targeting model needed for:
- Fireball (target point in range)
- Lightning Bolt (target direction/endpoint)
- Fog Cloud (target point for center)
- Teleport spells (Misty Step, Dimension Door)

---

## Phase 2: Shove Action (BG3-Style)

### Mechanics

| Property | Value |
|----------|-------|
| **Cost** | Bonus Action |
| **Range** | 5 ft (adjacent only) |
| **Check** | Athletics (attacker) vs Athletics/Acrobatics (defender) |
| **Effect** | Push target up to X feet away |
| **Max Weight** | STR × 12 lbs |

### Distance Calculation

```python
def get_shove_distance(shover: Entity, target: Entity) -> int:
    """
    Calculate shove distance based on STR and target weight.
    Min: 5 ft, Max: 20 ft
    """
    str_score = shover.ability_scores.strength.score
    target_weight = target.weight  # Need to add weight to entities

    # Base formula: higher STR and lower weight = more distance
    base_distance = 10  # 2 tiles
    str_bonus = (str_score - 10) // 2 * 5  # +5ft per 2 STR above 10
    weight_penalty = (target_weight // 50) * 5  # -5ft per 50 lbs

    distance = base_distance + str_bonus - weight_penalty
    return max(5, min(20, distance))  # Clamp to 5-20 ft
```

### Contested Check

```python
def resolve_shove(shover: Entity, target: Entity) -> Tuple[bool, int]:
    """
    Resolve shove attempt.
    Returns (success, distance_feet).
    """
    # Shover rolls Athletics
    shover_roll = shover.skill_check(SkillCheckRequest(
        skill="athletics",
        source_entity_uuid=shover.uuid,
        target_entity_uuid=target.uuid
    ))

    # Target uses higher of Athletics or Acrobatics (passive)
    target_athletics = 10 + target.skill_set.athletics.modifier
    target_acrobatics = 10 + target.skill_set.acrobatics.modifier
    dc = max(target_athletics, target_acrobatics)

    if shover_roll.total >= dc:
        distance = get_shove_distance(shover, target)
        return True, distance
    return False, 0
```

### Shove Direction and Forced Movement

```python
def calculate_push_destination(
    source_pos: Tuple[int, int],
    target_pos: Tuple[int, int],
    distance_feet: int
) -> Tuple[int, int]:
    """
    Calculate where target ends up after being pushed.
    Push direction is away from source.
    """
    dx = target_pos[0] - source_pos[0]
    dy = target_pos[1] - source_pos[1]

    # Normalize to unit direction
    length = max(abs(dx), abs(dy))
    if length == 0:
        return target_pos  # Same position, no push

    unit_dx = dx / length
    unit_dy = dy / length

    # Calculate tiles to push (5 ft per tile)
    tiles = distance_feet // 5

    # Find valid landing position
    final_pos = target_pos
    for i in range(1, tiles + 1):
        new_x = target_pos[0] + int(unit_dx * i)
        new_y = target_pos[1] + int(unit_dy * i)
        new_pos = (new_x, new_y)

        if not GridMap.get_map().is_walkable(new_pos):
            break  # Hit obstacle, stop here
        if GridMap.get_map().get_entities_at(new_pos):
            break  # Hit another entity, stop here

        final_pos = new_pos

    return final_pos
```

### Shove Action

```python
class Shove(BaseAction):
    name: str = "Shove"
    description: str = "Push a creature away from you"
    costs: List[BaseCost] = [BonusActionCost()]

    def _validate(self, event: ActionEvent) -> EventPhase:
        shover = Entity.get(self.source_entity_uuid)
        target = Entity.get(event.target_entity_uuid)

        # Must be adjacent (5 ft)
        distance = shover.senses.get_feet_distance(target.senses.position)
        if distance > 5:
            return EventPhase.CANCEL

        # Check weight limit
        max_weight = shover.ability_scores.strength.score * 12
        if target.weight > max_weight:
            return EventPhase.CANCEL  # Too heavy

        return EventPhase.EXECUTION

    def _apply(self, event: ActionEvent) -> Event:
        shover = Entity.get(self.source_entity_uuid)
        target = Entity.get(event.target_entity_uuid)

        success, distance = resolve_shove(shover, target)

        if success:
            new_pos = calculate_push_destination(
                shover.senses.position,
                target.senses.position,
                distance
            )

            # Move target (forced movement)
            GridMap.get_map().move_entity(target.uuid, new_pos)
            target.senses.position = new_pos

            # Fire FORCED_MOVEMENT event (for terrain hazards to react)
            # Fire SPATIAL_ENTITY_ENTERED for new position

        return ShoveEvent(
            success=success,
            distance_pushed=distance if success else 0,
            final_position=new_pos if success else target.senses.position
        ).phase_to(EventPhase.COMPLETION)
```

### Forced Movement Event Type

```python
class EventType(Enum):
    # ... existing ...
    FORCED_MOVEMENT = "forced_movement"  # NEW: For shove, thunderwave, etc.

class ForcedMovementEvent(Event):
    event_type: EventType = EventType.FORCED_MOVEMENT
    source_entity_uuid: UUID  # Who caused the push
    target_entity_uuid: UUID  # Who was pushed
    start_position: Tuple[int, int]
    end_position: Tuple[int, int]
    distance_feet: int
    cause: str  # "shove", "thunderwave", "gust_of_wind", etc.
```

### Shove Modifiers

| Condition | Effect |
|-----------|--------|
| Advantage on Athletics | +5 to passive DC |
| Disadvantage on Athletics | -5 to passive DC |
| Enlarged | Shove heavier targets (×2.35 weight limit) |
| Reduced | Shove lighter targets only (×0.425 weight limit) |
| Immovable (e.g., Helldusk Boots) | Cannot be shoved |

---

## Phase 3: AoE Targeting System

### AoE Shapes

| Shape | Parameters | Example Spells |
|-------|------------|----------------|
| **Cone** | origin, direction, length, angle | Burning Hands (15ft), Cone of Cold (60ft) |
| **Sphere** | center, radius | Fireball (20ft), Shatter (10ft) |
| **Cube** | corner or center, size | Thunderwave (15ft), Hypnotic Pattern (30ft) |
| **Line** | origin, direction, length, width | Lightning Bolt (100ft×5ft), Sunbeam (60ft×5ft) |
| **Cylinder** | center, radius, height | Ice Storm (20ft×40ft), Sleet Storm (40ft×20ft) |

### Core AoE Classes

```python
from abc import ABC, abstractmethod
from typing import Set, Tuple

class AoEShape(ABC):
    """Base class for area of effect shapes."""

    @abstractmethod
    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return all grid positions affected by this AoE."""
        pass

    @abstractmethod
    def contains(self, position: Tuple[int, int]) -> bool:
        """Check if a position is within the AoE."""
        pass


class Cone(AoEShape):
    """Cone emanating from a point in a direction."""

    def __init__(
        self,
        origin: Tuple[int, int],
        direction: Tuple[int, int],  # Unit vector or target point
        length_feet: int,
        angle_degrees: int = 90  # Standard D&D cone
    ):
        self.origin = origin
        self.direction = direction
        self.length_tiles = length_feet // 5
        self.angle = angle_degrees

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        # Algorithm: For each tile in range, check if angle from
        # origin->tile is within cone angle from origin->direction
        positions = set()
        # ... implementation using vector math ...
        return positions


class Sphere(AoEShape):
    """Sphere centered on a point."""

    def __init__(self, center: Tuple[int, int], radius_feet: int):
        self.center = center
        self.radius_tiles = radius_feet // 5

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        positions = set()
        for dx in range(-self.radius_tiles, self.radius_tiles + 1):
            for dy in range(-self.radius_tiles, self.radius_tiles + 1):
                # Use Euclidean distance for sphere
                if dx*dx + dy*dy <= self.radius_tiles * self.radius_tiles:
                    positions.add((self.center[0] + dx, self.center[1] + dy))
        return positions


class Line(AoEShape):
    """Line from origin in a direction."""

    def __init__(
        self,
        origin: Tuple[int, int],
        direction: Tuple[int, int],
        length_feet: int,
        width_feet: int = 5
    ):
        self.origin = origin
        self.direction = direction
        self.length_tiles = length_feet // 5
        self.width_tiles = width_feet // 5

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        # Bresenham's line algorithm + width
        positions = set()
        # ... implementation ...
        return positions


class Cube(AoEShape):
    """Cube area."""

    def __init__(
        self,
        origin: Tuple[int, int],
        size_feet: int,
        origin_is_corner: bool = True
    ):
        self.origin = origin
        self.size_tiles = size_feet // 5
        self.origin_is_corner = origin_is_corner

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        positions = set()
        if self.origin_is_corner:
            for dx in range(self.size_tiles):
                for dy in range(self.size_tiles):
                    positions.add((self.origin[0] + dx, self.origin[1] + dy))
        else:
            # Origin is center
            half = self.size_tiles // 2
            for dx in range(-half, half + 1):
                for dy in range(-half, half + 1):
                    positions.add((self.origin[0] + dx, self.origin[1] + dy))
        return positions
```

### AoE Spell Resolution

```python
def resolve_aoe_spell(
    caster: Entity,
    shape: AoEShape,
    save_ability: str,  # "dexterity", "constitution", etc.
    damage_dice: str,
    damage_type: DamageType,
    half_on_save: bool = True
) -> List[SpellEffectResult]:
    """
    Resolve an AoE spell against all creatures in the area.
    """
    results = []
    dc = caster.spell_save_dc()
    affected_positions = shape.get_affected_positions()

    # Find all entities in affected area
    for pos in affected_positions:
        entities_at = GridMap.get_map().get_entities_at(pos)
        for entity_uuid in entities_at:
            target = Entity.get(entity_uuid)
            if target.uuid == caster.uuid:
                continue  # Usually don't affect self

            # Make saving throw
            save_result = target.saving_throw(SavingThrowRequest(
                ability=save_ability,
                dc=dc,
                source_entity_uuid=caster.uuid
            ))

            # Calculate damage
            damage = roll_dice(damage_dice)
            if save_result.success and half_on_save:
                damage = damage // 2
            elif save_result.success and not half_on_save:
                damage = 0

            # Apply damage
            if damage > 0:
                target.take_damage(damage, damage_type, caster.uuid)

            results.append(SpellEffectResult(
                target_uuid=target.uuid,
                save_success=save_result.success,
                damage_dealt=damage
            ))

    return results
```

### Available Actions Extension

```python
class AvailableActionsResult:
    entity_actions: List[EntityAction]      # Attacks with targets
    position_actions: List[PositionAction]  # Movement
    self_actions: List[SelfAction]          # Dash, Dodge

    # NEW:
    aoe_actions: List[AoEAction]            # Spells with shape targeting
    jump_actions: List[JumpAction]          # Jump to position (no path)

class AoEAction:
    action: BaseAction
    shape_type: str  # "cone", "sphere", "line", "cube"
    shape_params: Dict  # Parameters for the shape
    valid_origins: Set[Tuple[int, int]]  # Where caster can place the AoE
```

---

## Spells Unlocked by Each Phase

### Phase 1: Jump
- Jump (spell) - Enhance jump range
- Expeditious Retreat (partial) - Enables movement combos
- Misty Step (foundation) - Same targeting model

### Phase 2: Shove
- Thunderwave - Forced movement component
- Gust of Wind - Forced movement
- All spells with "push" effects

### Phase 3: AoE Targeting
- Burning Hands, Thunderwave (Cone)
- Fireball, Shatter, Circle of Death (Sphere)
- Lightning Bolt, Sunbeam (Line)
- Hypnotic Pattern, Slow (Cube)
- Ice Storm, Cone of Cold, Sleet Storm (Cylinder/Cone)
- Chain Lightning (Multi-target)
- **~30 spells unlocked**

---

## Implementation Order

### Step 1: Jump Action
1. Add `jump_range` ModifiableValue to Entity/ActionEconomy
2. Add `get_jumpable_positions()` to Senses
3. Implement Jump action class
4. Add to `get_available_actions()`
5. Test with CLI

### Step 2: Shove Action
1. Add `weight` field to Entity
2. Implement contested roll helper
3. Implement Shove action class
4. Add FORCED_MOVEMENT event type
5. Add to `get_available_actions()`
6. Test with CLI

### Step 3: AoE Shapes
1. Implement AoEShape base class
2. Implement Sphere (simplest)
3. Implement Cone
4. Implement Line
5. Implement Cube
6. Unit tests for each shape

### Step 4: AoE Spell Integration
1. Create `AoESpellAction` base class
2. Implement Fireball as first test
3. Add `aoe_actions` to AvailableActionsResult
4. Update CLI to handle AoE targeting
5. Implement more AoE spells

---

## Future Work (Not This Plan)

These systems are deferred to a unified "3D Spatial System" implementation:

### 1. Terrain Effects
- Ground hazards, difficult terrain, tile conditions
- Spells: Fog Cloud, Web, Wall of Fire, Cloudkill, Stinking Cloud
- Requires: Tile condition system, spatial event handlers

### 2. Swimming/Burrowing/Flying
- Alternative movement types requiring terrain/elevation
- Requires: Terrain types (water, earth, air), movement mode tracking
- For: Water Breathing, Water Walk, Fly, burrowing creatures

### 3. Light System + Hiding + Cover + Z-Axis/Verticality
All require 3D spatial consideration; implement once together:
- **Light System**: Darkvision, See Invisibility, Light cantrip, darkness levels
- **Hiding**: Stealth mechanics, concealment, invisibility interactions
- **Cover**: Half/three-quarters/full cover from obstacles
- **Z-Axis**: Fly, Levitate, Reverse Gravity, 3D pathfinding, 3D raycasting
- Problem: ASCII visualization for 3D

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `dnd/actions.py` | Add Jump, Shove actions |
| `dnd/core/events.py` | Add FORCED_MOVEMENT event type, JumpEvent, ShoveEvent |
| `dnd/core/aoe.py` | NEW: AoE shape classes |
| `dnd/blocks/sensory.py` | Add `get_jumpable_positions()` |
| `dnd/blocks/action_economy.py` | Add `jump_range` if needed |
| `dnd/entity.py` | Add `weight` field, `jump_range` accessor |
| `dnd/actions_functional.py` | Update `get_available_actions()` for jump/shove/aoe |
| `dnd/spells/evocation.py` | Add Fireball, Lightning Bolt, etc. |
