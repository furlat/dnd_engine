# Movement and AoE Targeting Plan

## Current Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Jump | ✓ COMPLETE | BG3-style jump action working in CLI |
| Phase 2: Shove | ✓ COMPLETE | BG3-style shove with Athletics contest, forced movement |
| Phase 3: AoE Targeting | TODO | Cone, sphere, line, cube shapes |

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

## Phase 1: Jump Action (BG3-Style) - IMPLEMENTED ✓

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

### Design Principles

**Key insight**: AoE effects need FOV computed from the SPELL'S ORIGIN, not from the caster's position.

Example: Fireball centered at (5,5) should spread based on what's visible FROM (5,5), not from caster at (0,0).

**Two computation modes**:
| Mode | Data Source | Use Case |
|------|-------------|----------|
| **Subjective** | Senses (caster's perception) | Targeting, pre_validate, UI preview |
| **Objective** | GridMap (actual spatial reality) | Spell application, actual effect |

### Import Hierarchy (No Circularity)

```
GridMap (lowest - positions, tiles, UUIDs only)
    ↑
Senses (data container - visible positions, entity UUIDs)
    ↑
Shape (imports GridMap + Senses, NOT Entity)
    ↑
Entity (imports Shape, converts UUIDs to Entity objects)
    ↑
Action (imports Entity, Shape - orchestrates spell execution)
```

Shape is the **transaction layer** between actions and spatial systems. It only knows positions, UUIDs, and senses data - never Entity objects.

### Origin and Target Model

Every AoE has two positions:
- **target**: Where the spell is aimed (always provided by player)
- **origin**: Where the effect emanates from (for FOV/LOS calculation)

Origin can be:
- **Implicit** (default): Calculated from caster position or target
- **Explicit**: Player provides both positions (e.g., Wall of Fire endpoints)

| Shape | Default Origin | Examples |
|-------|----------------|----------|
| Sphere | origin = target (center) | Fireball, Shatter |
| Cone | origin = caster (apex) | Burning Hands, Cone of Cold |
| Line | origin = caster (start) | Lightning Bolt, Sunbeam |
| Cube (centered) | origin = target | Hypnotic Pattern |
| Cube (from face) | origin = caster | Thunderwave |
| Wall/Line (explicit) | origin = first endpoint | Wall of Fire |

### AoE Shapes

| Shape | Parameters | Example Spells |
|-------|------------|----------------|
| **Sphere** | center, radius | Fireball (20ft), Shatter (10ft) |
| **Cone** | apex, direction, length, angle | Burning Hands (15ft), Cone of Cold (60ft) |
| **Line** | start, end, length, width | Lightning Bolt (100ft×5ft), Sunbeam (60ft×5ft) |
| **Cube** | origin, size, centered flag | Thunderwave (15ft), Hypnotic Pattern (30ft) |
| **Cylinder** | center, radius, height | Ice Storm (20ft×40ft), Sleet Storm (40ft×20ft) |

### Core AoE Classes

```python
# dnd/core/aoe.py
from pydantic import Field
from typing import Set, Tuple, List, Optional
from uuid import UUID

from dnd.core.base_object import BaseObject
from dnd.blocks.sensory import Senses
from dnd.core.gridmap import get_map


class AoEShape(BaseObject):
    """
    Base class for AoE shapes. Extends BaseObject for registry/UUID support.

    Shape is the transaction layer between actions and spatial systems.
    It knows about GridMap and Senses, but NOT Entity.
    Returns positions and UUIDs - caller converts to Entity objects.

    Two computation modes:
    - compute_subjective(): Uses Senses (caster's perception) - for targeting/UI
    - compute_objective(): Uses GridMap (reality) - for spell application
    """

    # Target position (where spell is aimed - always required)
    target: Tuple[int, int] = Field(description="Target position (where aimed)")

    # Explicit origin override (if None, uses _default_origin)
    origin: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Explicit origin override. If None, computed from _default_origin()"
    )

    # Computed results (populated by compute methods)
    computed_origin: Optional[Tuple[int, int]] = Field(default=None)
    affected_positions: Set[Tuple[int, int]] = Field(default_factory=set)
    affected_entity_uuids: List[UUID] = Field(default_factory=list)

    def _default_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        """
        Default origin calculation. Override in subclasses.
        Base implementation: origin at caster position.
        """
        return caster_pos

    def get_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        """Get origin - explicit if set, else default."""
        if self.origin is not None:
            return self.origin
        return self._default_origin(caster_pos)

    def _get_max_radius_tiles(self) -> int:
        """Max radius for FOV computation. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement _get_max_radius_tiles()")

    def _get_geometric_positions(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        """
        Get positions within shape geometry (ignoring walls).
        Override in subclasses.
        """
        raise NotImplementedError("Subclasses must implement _get_geometric_positions()")

    def compute_subjective(self, caster_pos: Tuple[int, int], senses: Senses) -> "AoEShape":
        """
        Compute from Senses - what caster perceives.

        Use for: targeting validation, pre_validate, UI preview

        Args:
            caster_pos: Caster's current position
            senses: Caster's current senses (their perception)

        Returns: self (for chaining)
        """
        self.computed_origin = self.get_origin(caster_pos)

        # FOV = what caster can see (their perception)
        fov = set(pos for pos, visible in senses.visible.items() if visible)

        # Geometry intersected with caster's perception
        geometric = self._get_geometric_positions(self.computed_origin)
        self.affected_positions = geometric & fov

        # Entities caster can see in affected area
        self.affected_entity_uuids = [
            uuid for uuid, pos in senses.entities.items()
            if pos in self.affected_positions
        ]

        return self

    def compute_objective(self, caster_pos: Tuple[int, int]) -> "AoEShape":
        """
        Compute from GridMap - actual spatial reality.

        Use for: spell application, actual effect execution

        Computes FOV from the SHAPE'S ORIGIN (not caster), so walls
        block spread correctly even for point-origin spells like Fireball.

        Args:
            caster_pos: Caster's position (for origin calculation)

        Returns: self (for chaining)
        """
        grid = get_map()
        self.computed_origin = self.get_origin(caster_pos)
        radius = self._get_max_radius_tiles()

        # FOV computed from ORIGIN point (objective reality)
        fov_from_origin = grid.compute_fov(self.computed_origin, radius)

        # Geometry intersected with actual FOV from origin
        geometric = self._get_geometric_positions(self.computed_origin)
        self.affected_positions = geometric & fov_from_origin

        # All entities actually at affected positions
        self.affected_entity_uuids = []
        for pos in self.affected_positions:
            for uuid in grid.get_entities_at(pos[0], pos[1]):
                if uuid not in self.affected_entity_uuids:
                    self.affected_entity_uuids.append(uuid)

        return self


class Sphere(AoEShape):
    """
    Sphere/circle centered on target.
    Origin defaults to TARGET (center of explosion), not caster.
    """
    radius_feet: int = Field(default=20)

    def _default_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        return self.target  # Sphere centers on target

    def _get_max_radius_tiles(self) -> int:
        return self.radius_feet // 5

    def _get_geometric_positions(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        r = self.radius_feet // 5
        positions = set()
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if dx*dx + dy*dy <= r*r:  # Euclidean distance
                    positions.add((origin[0] + dx, origin[1] + dy))
        return positions


class Cone(AoEShape):
    """
    Cone emanating from caster toward target.
    Origin defaults to CASTER (apex of cone).
    """
    length_feet: int = Field(default=15)
    angle_degrees: int = Field(default=90)  # Standard D&D cone

    # Uses base _default_origin (caster position)

    def _get_max_radius_tiles(self) -> int:
        return self.length_feet // 5

    def _get_geometric_positions(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        import math

        positions = set()
        length_tiles = self.length_feet // 5
        half_angle = math.radians(self.angle_degrees / 2)

        # Direction from origin to target
        dx = self.target[0] - origin[0]
        dy = self.target[1] - origin[1]
        if dx == 0 and dy == 0:
            return positions  # No direction

        base_angle = math.atan2(dy, dx)

        # Check each tile in range
        for tx in range(-length_tiles, length_tiles + 1):
            for ty in range(-length_tiles, length_tiles + 1):
                if tx == 0 and ty == 0:
                    continue

                dist = math.sqrt(tx*tx + ty*ty)
                if dist > length_tiles:
                    continue

                # Angle from origin to this tile
                tile_angle = math.atan2(ty, tx)
                angle_diff = abs(tile_angle - base_angle)
                # Normalize angle difference
                if angle_diff > math.pi:
                    angle_diff = 2 * math.pi - angle_diff

                if angle_diff <= half_angle:
                    positions.add((origin[0] + tx, origin[1] + ty))

        return positions


class Line(AoEShape):
    """
    Line from caster toward target.
    Origin defaults to CASTER (start of line).
    """
    length_feet: int = Field(default=100)
    width_feet: int = Field(default=5)

    # Uses base _default_origin (caster position)

    def _get_max_radius_tiles(self) -> int:
        return self.length_feet // 5

    def _get_geometric_positions(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        import math

        positions = set()
        length_tiles = self.length_feet // 5
        width_tiles = max(1, self.width_feet // 5)

        # Direction from origin to target
        dx = self.target[0] - origin[0]
        dy = self.target[1] - origin[1]
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0:
            return positions

        # Normalize direction
        ndx, ndy = dx / dist, dy / dist

        # Perpendicular for width
        px, py = -ndy, ndx

        # Walk along line
        for i in range(length_tiles + 1):
            cx = origin[0] + ndx * i
            cy = origin[1] + ndy * i

            # Add width
            for w in range(-(width_tiles // 2), (width_tiles // 2) + 1):
                px_pos = int(round(cx + px * w))
                py_pos = int(round(cy + py * w))
                positions.add((px_pos, py_pos))

        return positions


class Cube(AoEShape):
    """
    Cube area. Can be centered on target or originating from caster face.
    """
    size_feet: int = Field(default=15)
    centered: bool = Field(default=False)  # If True, origin = target (centered)

    def _default_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        if self.centered:
            return self.target  # Centered cube
        return caster_pos  # Face at caster

    def _get_max_radius_tiles(self) -> int:
        return self.size_feet // 5

    def _get_geometric_positions(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        positions = set()
        size_tiles = self.size_feet // 5

        if self.centered:
            # Origin is center
            half = size_tiles // 2
            for dx in range(-half, half + 1):
                for dy in range(-half, half + 1):
                    positions.add((origin[0] + dx, origin[1] + dy))
        else:
            # Origin is on face, cube extends toward target
            dx = self.target[0] - origin[0]
            dy = self.target[1] - origin[1]

            # Determine primary direction
            if abs(dx) >= abs(dy):
                dir_x = 1 if dx >= 0 else -1
                for i in range(size_tiles):
                    for j in range(-(size_tiles // 2), (size_tiles // 2) + 1):
                        positions.add((origin[0] + dir_x * i, origin[1] + j))
            else:
                dir_y = 1 if dy >= 0 else -1
                for i in range(size_tiles):
                    for j in range(-(size_tiles // 2), (size_tiles // 2) + 1):
                        positions.add((origin[0] + j, origin[1] + dir_y * i))

        return positions
```

### Entity Helper Method

Entity provides a helper to convert shape UUIDs to Entity objects:

```python
# In dnd/entity.py

def get_aoe_affected_entities(
    self,
    shape: "AoEShape",
    exclude_self: bool = True,
    alive_only: bool = True
) -> Tuple[Set[Tuple[int, int]], List["Entity"]]:
    """
    Compute AoE using objective mode and return affected entities.

    Entity handles: computing the shape, converting UUIDs to Entity objects.
    Shape handles: spatial computation (positions, UUIDs).

    Args:
        shape: The AoE shape to compute
        exclude_self: If True, exclude caster from results
        alive_only: If True, only return living entities

    Returns:
        (affected_positions, affected_entities)
    """
    # Compute objective (actual spatial reality)
    shape.compute_objective(self.position)

    # Convert UUIDs to Entity objects
    entities = []
    for uuid in shape.affected_entity_uuids:
        if exclude_self and uuid == self.uuid:
            continue
        entity = Entity.get(uuid)
        if entity and (not alive_only or entity.is_alive):
            entities.append(entity)

    return shape.affected_positions, entities
```

### AoE Spell Action Base

```python
# In dnd/actions.py

class AoESpellAction(SpellAction):
    """Base class for AoE spells."""

    target_type: TargetType = Field(default=TargetType.POSITION_LOS)

    # Shape configuration (override in subclasses)
    aoe_shape_class: type = Field(default=None, exclude=True)  # Sphere, Cone, etc.

    # Save configuration
    save_ability: str = Field(default="dexterity")
    half_on_save: bool = Field(default=True)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        from dnd.entity import Entity

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        # Create shape with spell parameters
        shape = self._create_shape(execution_event.target_position)

        # Get affected entities (Entity handles the heavy lifting)
        affected_positions, affected_entities = caster.get_aoe_affected_entities(shape)

        # Apply effect to each entity
        dc = caster.spell_save_dc()
        results = []

        for target in affected_entities:
            result = self._apply_to_single_target(caster, target, dc)
            results.append(result)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            affected_positions=list(affected_positions),
            aoe_results=results,
            status_message=f"{self.name} affected {len(affected_entities)} creatures"
        )

    def _create_shape(self, target_pos: Tuple[int, int]) -> "AoEShape":
        """Create shape instance. Override in subclasses."""
        raise NotImplementedError

    def _apply_to_single_target(self, caster, target, dc) -> dict:
        """Apply effect to one target. Override in subclasses."""
        raise NotImplementedError
```

### Example: Fireball Implementation

```python
# In dnd/spells/evocation.py

class Fireball(AoESpellAction):
    """Fireball - 3rd level evocation

    A bright streak flashes from your pointing finger to a point you choose
    within range and then blossoms with a low roar into an explosion of flame.
    Each creature in a 20-foot-radius sphere centered on that point must make
    a DEX save. Takes 8d6 fire damage on failed save, half on success.
    """
    name: str = Field(default="Fireball")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="evocation")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=150))

    save_ability: str = "dexterity"
    half_on_save: bool = True

    # Damage scales with upcasting
    base_damage_dice: int = Field(default=8)  # 8d6

    def _create_shape(self, target_pos: Tuple[int, int]) -> Sphere:
        from dnd.core.aoe import Sphere
        return Sphere(
            source_entity_uuid=self.source_entity_uuid,
            target=target_pos,
            radius_feet=20
        )

    def _apply_to_single_target(self, caster, target, dc) -> dict:
        # Roll save
        save_result = target.saving_throw(SavingThrowRequest(
            ability=self.save_ability,
            dc=dc,
            source_entity_uuid=caster.uuid
        ))

        # Roll damage (8d6 base, +1d6 per level above 3rd)
        num_dice = self.base_damage_dice + max(0, self.cast_at_level - 3)
        damage_roll = Dice(sides=6, count=num_dice).roll()
        damage = damage_roll.total

        if save_result.success:
            damage = damage // 2

        # Apply damage
        if damage > 0:
            target.health.take_damage(damage, DamageType.FIRE, caster.uuid)

        return {
            "target_uuid": str(target.uuid),
            "target_name": target.name,
            "save_success": save_result.success,
            "damage_dealt": damage
        }
```

### Targeting in get_available_actions

AoE spells use `POSITION_LOS` target type - they fit into existing `position_actions`:

```python
# In Entity.get_available_actions() - no changes needed!
# AoE spells with target_type=POSITION_LOS are already handled:

# POSITION_LOS actions (Jump, Teleport, AoE spells)
for template in self.position_actions:
    if template.target_type != TargetType.POSITION_LOS:
        continue

    valid_pos_list = template.get_valid_positions()  # Inherited from BaseAction
    # ... rest of existing code ...
```

No new action category needed. AoE spells just use position targeting.

---

## Spells Unlocked by Each Phase

### Phase 1: Jump ✓ COMPLETE
- Jump (spell) - Enhance jump range (ready to implement)
- Expeditious Retreat (partial) - Enables movement combos
- Misty Step (foundation) - Same targeting model (position without path)

### Phase 2: Shove ✓ COMPLETE
- Thunderwave - Forced movement component (ForcedMovementEvent ready)
- Gust of Wind - Forced movement
- All spells with "push" effects
- Repelling Blast (Eldritch Blast invocation)

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

### Step 1: Jump Action ✓ COMPLETE
1. ✓ Add `jump_range` ModifiableValue to Entity/ActionEconomy
2. ✓ Add `get_jumpable_positions()` to Senses
3. ✓ Implement Jump action class in `dnd/actions.py`
4. ✓ Add to `get_available_actions()` as position action
5. ✓ Test with CLI (human CLI: `jump X Y` / `j X Y`, agent CLI: `jump X Y`)
6. ✓ Combat log integration with JumpEvent

### Step 2: Shove Action ✓ COMPLETE
1. ✓ Add `weight` field to Entity (default 150 lbs)
2. ✓ Implement `passive_skill()` method for contested checks
3. ✓ Implement Shove action class with ShoveEvent
4. ✓ Add FORCED_MOVEMENT event type + ForcedMovementEvent
5. ✓ Add to `get_available_actions()` with weight/adjacency filtering
6. ✓ Test with CLI and examples/test_shove.py

### Step 3: AoE Shape System
1. Create `dnd/core/aoe.py` with AoEShape base class (extends BaseObject)
2. Implement `compute_subjective(caster_pos, senses)` - uses Senses data
3. Implement `compute_objective(caster_pos)` - uses GridMap directly
4. Implement Sphere shape (simplest, tests origin=target pattern)
5. Unit tests for Sphere with both compute modes
6. Implement Cone shape (tests origin=caster, direction math)
7. Implement Line shape (tests Bresenham + width)
8. Implement Cube shape (tests centered vs face-origin modes)
9. Unit tests for all shapes

### Step 4: Entity Integration
1. Add `Entity.get_aoe_affected_entities(shape)` helper method
2. Helper computes shape objective mode and converts UUIDs to Entity objects
3. Test helper with Sphere shape

### Step 5: AoE Spell Action Base
1. Create `AoESpellAction` base class in `dnd/actions.py`
2. Base class: creates shape, calls entity helper, iterates targets
3. Subclasses override: `_create_shape()`, `_apply_to_single_target()`

### Step 6: First AoE Spell - Fireball
1. Implement Fireball in `dnd/spells/evocation.py`
2. Test targeting (uses existing POSITION_LOS flow)
3. Test damage application to multiple targets
4. Test wall blocking (FOV from spell center)
5. Create `examples/test_fireball.py`

### Step 7: More AoE Spells
1. Burning Hands (Cone) - tests cone geometry
2. Lightning Bolt (Line) - tests line geometry
3. Thunderwave (Cube from caster) - tests cube + forced movement integration
4. Shatter (Sphere) - another sphere spell for validation

### Step 8: CLI Preview (Deferred)
- Show affected area before confirming AoE spell
- Highlight affected tiles on map
- This can be done after core mechanics work

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

| File | Changes | Status |
|------|---------|--------|
| `dnd/actions.py` | Add Jump, Shove actions | ✓ Done |
| `dnd/core/events.py` | Add FORCED_MOVEMENT event type, JumpEvent, ShoveEvent, ForcedMovementEvent | ✓ Done |
| `dnd/blocks/sensory.py` | Add `get_jumpable_positions()` | ✓ Done |
| `dnd/blocks/action_economy.py` | Add `jump_range` ModifiableValue | ✓ Done |
| `dnd/entity.py` | Add `weight` field, `passive_skill()` method | ✓ Done |
| `dnd/actions_functional.py` | Update `get_available_actions()` for jump/shove/aoe | ✓ Jump/Shove done |
| `cli/main.py` | Position action routing via ShortcutRegistry | ✓ Done |
| `cli/agent.py` | Jump command support | ✓ Done |

### Phase 3 Files (TODO)

| File | Changes | Status |
|------|---------|--------|
| `dnd/core/aoe.py` | NEW: AoEShape base + Sphere, Cone, Line, Cube | TODO |
| `dnd/entity.py` | Add `get_aoe_affected_entities(shape)` helper | TODO |
| `dnd/actions.py` | Add `AoESpellAction` base class | TODO |
| `dnd/spells/evocation.py` | Add Fireball, Lightning Bolt, Burning Hands, Shatter | TODO |
| `examples/test_aoe_shapes.py` | NEW: Unit tests for shape geometry | TODO |
| `examples/test_fireball.py` | NEW: Integration test for Fireball | TODO |
