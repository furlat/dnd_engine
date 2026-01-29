# Movement and AoE Targeting Plan

## Current Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Jump | ✓ COMPLETE | BG3-style jump action working in CLI |
| Phase 2: Shove | ✓ COMPLETE | BG3-style shove with Athletics contest, forced movement |
| Phase 3: AoE Targeting | IN PROGRESS | Infrastructure ✓ (geometry.py, aoe.py, shapes, tests), AoESpellAction TODO, Spells TODO |
| Phase 4: Multi-Entity Targeting | ✓ COMPLETE | Magic Missile, multi-target spells, ally/enemy filtering |

## Overview

This document plans systems that will unlock a large portion of sorcerer spells and improve combat mechanics significantly.

### Systems to Implement (This Plan)

1. **Jump Action** - Bonus action movement without path requirement (foundational for AoE targeting)
2. **Shove Action** - Contested push with forced movement
3. **AoE Targeting System** - Cone, sphere, line, cube targeting for spells
4. **Multi-Entity Targeting** - Target multiple specific entities (Magic Missile, Bless, Scorching Ray)

### Out of Scope (Future Spatial Systems)

The following are deferred to a unified "3D Spatial System" implementation:

1. **Terrain Effects** - Ground hazards, difficult terrain, tile conditions (Fog Cloud, Web, Wall of Fire)
2. **Swimming/Burrowing/Flying** - Alternative movement types requiring terrain/elevation
3. **Light System + Hiding + Cover + Z-Axis/Verticality** - All require 3D spatial consideration; implement once together

---

## Current Targeting Model

```
Movement:     source_position → target_position + path (contiguous walkable tiles)
Attack:       source_entity → target_entity (with range/LOS check)
Spell:        source_entity → target_entity OR self (single target)
Multi-target: source_entity → [target_entities] → per-target results (Magic Missile, Bless)
Jump:         source_position → target_position (visible + walkable, NO path required)
Shove:        source_entity → target_entity → forced_position (Athletics contest)
```

### Proposed Targeting Model Evolution

```
1. Jump:        source_position → target_position (visible + walkable, NO path required)
2. Shove:       source_entity → target_entity → forced_position (push direction + distance)
3. AoE:         source_position → target_position + shape → affected_positions[]
4. Multi-Entity: source_entity → [target_entities] → per-target results (convolution)
```

---

## Phase 1: Jump Action (BG3-Style) - IMPLEMENTED ✓

### Mechanics

| Property | Value |
|----------|-------|
| **Cost** | Bonus Action + Movement (distance jumped) |
| **Base Range** | 15 ft (3 tiles) |
| **Scaling** | +5 ft per STR modifier above 0 |
| **Requirements** | Target must be visible + walkable + unoccupied |
| **Does NOT require** | Path to destination |

### Implementation

The Jump action is implemented in `dnd/actions.py` with these key components:

**JumpEvent** (`dnd/actions.py:1324`): Event class with combat log support
```python
class JumpEvent(ActionEvent):
    name: str = "Jump"
    target_position: Optional[Tuple[int, int]] = None
    distance_feet: int = 0
    start_position: Optional[Tuple[int, int]] = None
```

**Jump Action** (`dnd/actions.py:1375`): Uses `Jump.get_valid_positions()` for targeting

**Range Calculation** (in `Jump.get_range()`):
```python
def get_range(self) -> int:
    """Calculate jump range based on STR modifier."""
    entity = Entity.get(self.source_entity_uuid)
    str_mod = entity.ability_scores.strength.modifier
    return 15 + (str_mod * 5)  # 15ft base + 5ft per STR mod
```

**Valid Positions** (in `Jump.get_valid_positions()`):
- Checks visible + walkable + unoccupied + within range
- Does NOT require path (key difference from Move)
- Movement cost is dynamically added via `_setup_movement_cost()`

### Example Ranges by Strength

| STR | Modifier | Base | Bonus | Total Range |
|-----|----------|------|-------|-------------|
| 8   | -1       | 15ft | -5ft  | 10 ft |
| 10  | 0        | 15ft | 0     | 15 ft |
| 12  | +1       | 15ft | +5ft  | 20 ft |
| 14  | +2       | 15ft | +10ft | 25 ft |
| 16  | +3       | 15ft | +15ft | 30 ft |
| 18  | +4       | 15ft | +20ft | 35 ft |
| 20  | +5       | 15ft | +25ft | 40 ft |

### Why Jump is Foundational for AoE

Jump introduces **"target a position without a path"** which is the same targeting model needed for:
- Fireball (target point in range)
- Lightning Bolt (target direction/endpoint)
- Fog Cloud (target point for center)
- Teleport spells (Misty Step, Dimension Door)

---

## Phase 2: Shove Action (BG3-Style) - IMPLEMENTED ✓

### Mechanics

| Property | Value |
|----------|-------|
| **Cost** | Bonus Action |
| **Range** | 5 ft (adjacent only) |
| **Check** | Athletics (attacker) vs passive Athletics/Acrobatics (defender) |
| **Effect** | Push target up to X feet away |
| **Max Weight** | STR × 12 lbs |

### Implementation

The Shove action is implemented in `dnd/actions.py` with these key components:

**ShoveEvent** (`dnd/actions.py:1654`): Event class with combat log support
**Shove Action** (`dnd/actions.py:1747`): Full implementation with contests

**Key Methods:**
- `Entity.passive_skill(skill_name)` (`dnd/entity.py:570`) - Returns `10 + skill bonus + advantage modifier`
- `Shove.get_max_shove_weight()` - Returns `STR × 12` lbs
- `Shove.get_push_distance()` - Calculates push distance based on STR and target weight

### Distance Calculation

```python
def get_push_distance(self) -> int:
    """Actual implementation in Shove class."""
    shover = Entity.get(self.source_entity_uuid)
    target = Entity.get(self.target_entity_uuid)

    str_score = shover.ability_scores.strength.score
    target_weight = target.weight

    base_distance = 10
    str_bonus = (str_score - 10) // 2 * 5
    weight_penalty = (target_weight // 50) * 5

    return max(5, min(20, base_distance + str_bonus - weight_penalty))
```

### Contested Check (Actual Implementation)

The actual implementation uses `Entity.passive_skill()` for cleaner code:

```python
# In Shove._apply():
# Shover rolls Athletics
shover_roll = shover.skill_check(SkillCheckRequest(...))

# Target uses passive skill (10 + skill bonus + advantage modifier)
# passive_skill() handles the higher-of-athletics-or-acrobatics logic
dc = target.passive_skill("athletics")  # or acrobatics, whichever is higher
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

## Phase 4: Multi-Entity Targeting (MULTI_ENTITY) - IMPLEMENTED ✓

Multi-Entity targeting enables spells/abilities that target multiple specific entities (not positions). Unlike AoE which affects all entities in a shape, MULTI_ENTITY lets the caster choose specific targets.

### Use Cases

| Spell/Ability | Targets | Behavior |
|---------------|---------|----------|
| **Magic Missile** | Up to 3+ enemies | Each dart can hit same or different target |
| **Bless** | Up to 3 allies | Buff multiple party members |
| **Scorching Ray** | Up to 3 enemies | Each ray targets separately |
| **Eldritch Blast** | Multiple enemies | Each beam can target different |
| **Healing Word (Mass)** | Multiple allies | Heal party members |

### Design Principles

1. **Convolution Pattern**: `apply()` loops over targets, calling `_apply()` for each
2. **Per-target Events**: Each target gets its own result event with combat log
3. **Aggregate Tracking**: Final event has `total_targets` and `total_damage`
4. **Validation Filters**: Actions can restrict valid targets (enemies, allies, etc.)
5. **Same-target Control**: Some spells allow targeting same entity multiple times

### Implementation

#### TargetType.MULTI_ENTITY

Added to `dnd/core/base_actions.py`:

```python
class TargetType(str, Enum):
    # ... existing types ...
    MULTI_ENTITY = "multi_entity"  # Multi-target spells - targets list of entities
```

#### BaseAction Fields

```python
class BaseAction(BaseObject):
    # ... existing fields ...

    # Multi-target fields (for MULTI_ENTITY actions)
    extra_target_entity_uuids: List[UUID] = Field(
        default_factory=list,
        description="Additional targets beyond primary target_entity_uuid"
    )
    allow_same_target: bool = Field(
        default=True,
        description="If False, same entity cannot appear multiple times"
    )
    valid_target_filter: str = Field(
        default="enemies",
        description="Which entities are valid: 'enemies', 'allies', 'self_or_allies', 'all'"
    )
```

#### ActionEvent Aggregate Fields

```python
class ActionEvent(Event):
    # ... existing fields ...

    # Multi-target result fields
    target_results: Optional[List[Event]] = Field(
        default=None,
        description="Results from each per-target _apply() call"
    )
    total_targets: int = Field(default=0, description="Number of targets affected")
    total_damage: int = Field(default=0, description="Total damage dealt across all targets")
    description: str = Field(default="", description="Action description for combat log")
```

#### Convolution in apply()

The `BaseAction.apply()` method handles MULTI_ENTITY automatically:

```python
def apply(self, parent_event: Optional[Event] = None) -> Optional[Event]:
    # ... validation ...

    if self.target_type == TargetType.MULTI_ENTITY:
        all_target_uuids = self.get_all_targets()
        original_target = self.target_entity_uuid

        # CONVOLUTION: Call _apply() for each target IN ORDER
        all_results: List[ActionEvent] = []
        total_damage = 0

        for target_uuid in all_target_uuids:
            self.target_entity_uuid = target_uuid
            result_event = self._apply(execution_event)
            if result_event:
                all_results.append(result_event)
                # CONTRACT: _apply() must set total_damage if it deals damage
                damage = getattr(result_event, 'total_damage', 0) or 0
                total_damage += damage

        self.target_entity_uuid = original_target

        # Aggregate into final completion event
        completion_event = execution_event.phase_to(
            EventPhase.COMPLETION,
            target_results=all_results,
            total_targets=len(all_results),
            total_damage=total_damage,
            status_message=f"{self.name} affected {len(all_results)} targets for {total_damage} total damage"
        )
    else:
        # Single-target flow
        completion_event = self._apply(execution_event)
```

#### get_all_targets() Override Pattern

Actions can customize target resolution:

```python
class MagicMissile(SpellAction):
    """Magic Missile fills remaining darts with primary target."""

    def get_all_targets(self) -> List[UUID]:
        # Start with explicitly selected targets
        targets = super().get_all_targets()

        # Fill remaining darts with primary target
        total_darts = 3 + max(0, self.cast_at_level - 1)
        while len(targets) < total_darts and self.target_entity_uuid:
            targets.append(self.target_entity_uuid)

        return targets
```

#### Target Filter Validation

`_validate_target_filter()` enforces ally/enemy restrictions:

| Filter | Description | Valid Targets |
|--------|-------------|---------------|
| `"enemies"` | Different faction | Only enemies |
| `"allies"` | Same faction, not self | Only allies (excluding self) |
| `"self_or_allies"` | Same faction or self | Self + allies |
| `"all"` | Any visible entity | All entities |

Validation runs in `_validate()` for MULTI_ENTITY actions.

### Combat Log Integration

Each per-target `_apply()` generates its own combat log entry. The `ActionEvent.generate_combat_log()` was fixed to:

1. Use correct `CombatLogEntry` API (`compact`, `verbose`, `detailed` fields)
2. Use `self.description` from the action instead of hardcoded strings
3. Remove damage extraction fallback - `_apply()` must set `total_damage`

### Example: Magic Missile Multi-Target

```python
# Create Magic Missile targeting 3 different enemies
missile = MagicMissile(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=goblin1.uuid,
    extra_target_entity_uuids=[goblin2.uuid, goblin3.uuid],
    cast_at_level=1  # 3 darts
)

result = missile.apply()

# Result contains aggregate info
print(f"Total targets: {result.total_targets}")  # 3
print(f"Total damage: {result.total_damage}")    # Sum of all darts

# Individual results available
for per_target_event in result.target_results:
    print(f"  {per_target_event.target_entity_name}: {per_target_event.total_damage} damage")
```

### Example: Bless Multi-Target (Allies)

```python
class TestBless(SpellAction):
    """Test spell that targets self + allies."""
    target_type: TargetType = TargetType.MULTI_ENTITY
    valid_target_filter: str = "self_or_allies"  # Can target self and allies
    allow_same_target: bool = False  # Can't bless same entity twice
    max_targets: int = 3

    def get_all_targets(self) -> List[UUID]:
        targets = super().get_all_targets()
        # Enforce max targets
        return targets[:self.max_targets]
```

### Test Files

| File | Tests |
|------|-------|
| `examples/test_magic_missile_multi.py` | Single target, split targets, upcast darts, enemy-only validation |
| `examples/test_multi_target_allies.py` | Self+allies filter, enemy rejection, duplicate prevention, max targets |

### Design Decisions

1. **No damage fallback**: Removed code that extracted damage from `damage_rolls`. Contract: `_apply()` MUST set `total_damage` if damage is dealt.

2. **Description on ActionEvent**: Added `description` field to `ActionEvent` so combat log can use action descriptions without hardcoding.

3. **Per-target logging**: Each target gets its own combat log entry. No aggregate summary log is generated (UI can aggregate if needed from `target_results`).

4. **Filter at validation**: Target filtering happens in `_validate()`, not `apply()`. Invalid targets cause the entire action to cancel with a clear message.

5. **Order preservation**: Targets are processed in order: `[target_entity_uuid] + extra_target_entity_uuids`.

---

## Phase 3: AoE Targeting System - PARTIALLY IMPLEMENTED

**Status:** Infrastructure ✓ COMPLETE | AoE Spell Base TODO | Spells TODO

### What's Implemented ✓

| Component | File | Status |
|-----------|------|--------|
| Pure geometry functions | `dnd/core/geometry.py` | ✓ Done |
| AoEShape base + Sphere/Cone/Line/Cube | `dnd/core/aoe.py` | ✓ Done |
| `TargetType.POSITION_AOE` | `dnd/core/base_actions.py:25` | ✓ Done |
| `aoe_shape` field on BaseAction | `dnd/core/base_actions.py:123` | ✓ Done |
| `Entity.get_aoe_affected_entities()` | `dnd/entity.py:1041` | ✓ Done |
| Geometry unit tests | `examples/test_geometry.py` | ✓ 14 tests |
| Shape + wall blocking tests | `examples/test_aoe_shapes.py` | ✓ 9 tests |
| Entity integration tests | `examples/test_aoe_integration.py` | ✓ 2 tests |

### What's NOT Implemented (TODO)

| Component | Status |
|-----------|--------|
| `AoESpellAction` base class | TODO - Design below |
| Fireball spell | TODO - Design below |
| Other AoE spells (Burning Hands, Lightning Bolt, etc.) | TODO |

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
    angle_degrees: int = Field(default=53)  # D&D 5e standard (~53° for equilateral spread)

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

### AoE Spell Action Base - TODO (Design Only)

> **⚠️ NOT YET IMPLEMENTED** - The following is the planned design for the AoESpellAction base class.

```python
# PLANNED for dnd/actions.py - NOT YET IMPLEMENTED

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

### Example: Fireball Implementation - TODO (Design Only)

> **⚠️ NOT YET IMPLEMENTED** - The following is the planned design for the Fireball spell.

```python
# PLANNED for dnd/spells/evocation.py - NOT YET IMPLEMENTED

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

### Phase 3: AoE Targeting (IN PROGRESS)
- Burning Hands, Thunderwave (Cone)
- Fireball, Shatter, Circle of Death (Sphere)
- Lightning Bolt, Sunbeam (Line)
- Hypnotic Pattern, Slow (Cube)
- Ice Storm, Cone of Cold, Sleet Storm (Cylinder/Cone)
- **~30 spells unlocked**

### Phase 4: Multi-Entity Targeting ✓ COMPLETE
- **Magic Missile** - Auto-hit darts, split across targets
- **Scorching Ray** - Multiple attack rolls against different targets
- **Eldritch Blast** - Each beam targets separately (at higher levels)
- **Bless/Bane** - Buff/debuff multiple allies/enemies
- **Healing Word (Mass)** - Heal multiple party members
- **Cure Wounds (Mass)** - Touch-based multi-heal
- **Chain Lightning** - Primary + bounce targets (needs MULTI_ENTITY + chaining logic)
- **~15 spells unlocked**

---

## Implementation Order

### Step 1: Jump Action ✓ COMPLETE
1. ✓ Implement Jump action class in `dnd/actions.py` (with `get_range()` and `get_valid_positions()`)
2. ✓ Add to `get_available_actions()` as position action
3. ✓ Test with CLI (human CLI: `jump X Y` / `j X Y`, agent CLI: `jump X Y`)
4. ✓ Combat log integration with JumpEvent

### Step 2: Shove Action ✓ COMPLETE
1. ✓ Add `weight` field to Entity (default 150 lbs)
2. ✓ Implement `passive_skill()` method for contested checks
3. ✓ Implement Shove action class with ShoveEvent
4. ✓ Add FORCED_MOVEMENT event type + ForcedMovementEvent
5. ✓ Add to `get_available_actions()` with weight/adjacency filtering
6. ✓ Test with CLI and examples/test_shove.py

### Step 3: AoE Shape System ✓ COMPLETE
1. ✓ Create `dnd/core/geometry.py` - Pure geometry functions (not in original plan, better separation)
2. ✓ Create `dnd/core/aoe.py` with AoEShape base class (extends BaseObject, use_register=False)
3. ✓ Implement `compute_subjective(caster_pos, senses)` - uses Senses data
4. ✓ Implement `compute_objective(caster_pos)` - uses GridMap directly
5. ✓ Implement Sphere shape (origin=target pattern)
6. ✓ Implement Cone shape (origin=caster, direction math, angle=53° for D&D 5e)
7. ✓ Implement Line shape (Bresenham + width via geometry.py)
8. ✓ Implement Cube shape (centered vs face-origin modes)
9. ✓ Unit tests: `examples/test_geometry.py`, `examples/test_aoe_shapes.py`

**Design decisions made during implementation:**
- Extracted geometry to `geometry.py` for purity and testability
- Used `origin_override` field + `_default_origin()` method pattern
- Changed `affected_entity_uuids` from `List[UUID]` to `Set[UUID]` (no duplicates)
- Cone uses 53° angle (D&D 5e standard) not 90°

### Step 4: Entity Integration ✓ COMPLETE
1. ✓ Add `Entity.get_aoe_affected_entities(shape)` helper method
2. ✓ Helper has `use_objective` param to choose computation mode
3. ✓ Helper converts UUIDs to Entity objects, filters dead/self
4. ✓ Test: `examples/test_aoe_integration.py`

### Step 4.5: POSITION_AOE Target Type ✓ COMPLETE (not in original plan)
1. ✓ Added `TargetType.POSITION_AOE` to `base_actions.py`
2. ✓ Added `aoe_shape: Optional[AoEShape]` field to `BaseAction`
3. ✓ Extended `AvailableTarget` with `affected_entity_uuids/names/count`
4. ✓ Added POSITION_AOE handling in `Entity.get_available_actions()`
5. ✓ Type safety fix: replaced `Any` with proper `AoEShape` imports

### Step 4.6: Multi-Entity Targeting System ✓ COMPLETE
1. ✓ Added `TargetType.MULTI_ENTITY` to `base_actions.py`
2. ✓ Added `extra_target_entity_uuids`, `allow_same_target`, `valid_target_filter` fields to `BaseAction`
3. ✓ Added `target_results`, `total_targets`, `total_damage`, `description` fields to `ActionEvent`
4. ✓ Implemented convolution loop in `BaseAction.apply()` for MULTI_ENTITY actions
5. ✓ Implemented `get_all_targets()` method with override pattern
6. ✓ Implemented `_validate_target_filter()` for ally/enemy validation
7. ✓ Fixed `ActionEvent.generate_combat_log()` to use correct CombatLogEntry API
8. ✓ Fixed `ActionEconomy.can_afford()` to use `value.normalized_score` (not just self_static)
9. ✓ Created Magic Missile spell with multi-target support
10. ✓ Test: `examples/test_magic_missile_multi.py`, `examples/test_multi_target_allies.py`

**Design decisions made during implementation:**
- Removed damage extraction fallback - `_apply()` must set `total_damage` explicitly
- Added `description` field to ActionEvent for combat log generation
- Per-target logging (each _apply generates own log), no aggregate summary
- Target filter validation happens in `_validate()`, not `apply()`
- Fixed `can_afford()` bug that ignored max constraints from Incapacitated

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
| `dnd/actions.py` | Add Jump, Shove actions (with JumpEvent, ShoveEvent) | ✓ Done |
| `dnd/core/events.py` | Add FORCED_MOVEMENT event type | ✓ Done |
| `dnd/entity.py` | Add `weight` field, `passive_skill()` method | ✓ Done |
| `dnd/actions_functional.py` | Update `get_available_actions()` for jump/shove/aoe | ✓ Jump/Shove done |
| `cli/main.py` | Position action routing via ShortcutRegistry | ✓ Done |
| `cli/agent.py` | Jump command support | ✓ Done |

### Phase 3 Files (AoE Shapes)

| File | Changes | Status |
|------|---------|--------|
| `dnd/core/geometry.py` | NEW: Pure geometry functions (circle, line, cone, rectangle) | ✓ Done |
| `dnd/core/aoe.py` | NEW: AoEShape base + Sphere, Cone, Line, Cube | ✓ Done |
| `dnd/core/base_actions.py` | POSITION_AOE target type, aoe_shape field, AvailableTarget extensions | ✓ Done |
| `dnd/entity.py` | `get_aoe_affected_entities()` helper, POSITION_AOE in get_available_actions() | ✓ Done |
| `examples/test_geometry.py` | NEW: Pure geometry unit tests | ✓ Done |
| `examples/test_aoe_shapes.py` | NEW: Shape + wall blocking tests | ✓ Done |
| `examples/test_aoe_integration.py` | NEW: POSITION_AOE + Entity helper tests | ✓ Done |
| `dnd/actions.py` | Add `AoESpellAction` base class | TODO |
| `dnd/spells/evocation.py` | Add Fireball, Lightning Bolt, Burning Hands, Shatter | TODO |
| `examples/test_fireball.py` | NEW: Integration test for Fireball | TODO |

### Phase 4 Files (Multi-Entity Targeting)

| File | Changes | Status |
|------|---------|--------|
| `dnd/core/base_actions.py` | MULTI_ENTITY target type, extra_target_entity_uuids, allow_same_target, valid_target_filter fields, convolution in apply(), get_all_targets(), _validate_target_filter(), ActionEvent.description field, fixed generate_combat_log() | ✓ Done |
| `dnd/blocks/action_economy.py` | Fixed can_afford() to use value.normalized_score (not self_static) | ✓ Done |
| `dnd/actions.py` | Updated Dash/Dodge/Disengage/StandUp/DropProne to populate description in events | ✓ Done |
| `dnd/spells/evocation.py` | Magic Missile with multi-target support, get_all_targets() override | ✓ Done |
| `examples/test_magic_missile_multi.py` | NEW: Multi-target Magic Missile tests | ✓ Done |
| `examples/test_multi_target_allies.py` | NEW: Ally filter and TestBless tests | ✓ Done |
| `examples/test_available_actions.py` | Fixed test to check affordable_self_actions instead of all self_actions | ✓ Done |
