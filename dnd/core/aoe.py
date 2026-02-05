"""
Area of Effect (AoE) shape classes.

These are thin wrappers around geometry.py functions that add:
1. Wall blocking via GridMap FOV calculations
2. Entity detection via GridMap entity tracking
3. Subjective (from caster's perspective) and objective (from shape origin) computation

Usage:
    from dnd.core.aoe import Sphere, Cone, Line, Cube

    # Create shape targeting a position
    shape = Sphere(source_entity_uuid=caster.uuid, target=(5, 5), radius_feet=20)

    # Compute affected positions and entities
    shape.compute_objective(caster_pos=(0, 0))

    # Check results
    print(shape.affected_positions)
    print(shape.affected_entity_uuids)
"""
from __future__ import annotations

from typing import Optional, Set, Tuple
from uuid import UUID

from pydantic import Field

from dnd.core.base_object import BaseObject
from dnd.core.geometry import (
    circle_positions,
    cone_positions,
    line_positions,
    rectangle_positions,
)
from dnd.core.gridmap import get_map
from dnd.blocks.sensory import Senses


class AoEShape(BaseObject):
    """
    Base class for AoE shapes - thin wrapper around geometry functions.

    Shapes compute affected positions by:
    1. Getting geometric positions from geometry.py functions
    2. Filtering by line-of-sight from origin (using GridMap.compute_fov)
    3. Finding entities at affected positions

    Two computation modes:
    - `compute_subjective()`: Uses caster's existing senses (fast, for previews)
    - `compute_objective()`: Computes fresh FOV from shape origin (accurate, for actual effects)
    """

    use_register: bool = Field(default=False)
    target: Tuple[int, int] = Field(default=(0, 0))
    origin_override: Optional[Tuple[int, int]] = Field(default=None)

    # Computed results (populated by compute_* methods)
    computed_origin: Optional[Tuple[int, int]] = Field(default=None)
    affected_positions: Set[Tuple[int, int]] = Field(default_factory=set)
    affected_entity_uuids: Set[UUID] = Field(default_factory=set)

    def _default_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        """Return default origin for this shape type. Override in subclasses."""
        raise NotImplementedError

    def _get_max_radius_tiles(self) -> int:
        """Return maximum radius in tiles for FOV calculation. Override in subclasses."""
        raise NotImplementedError

    def _get_positions_in_shape(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        """Call geometry function to get positions. Override in subclasses."""
        raise NotImplementedError

    def get_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        """Get the effective origin for this shape."""
        return self.origin_override or self._default_origin(caster_pos)

    def compute_subjective(
        self, caster_pos: Tuple[int, int], senses: "Senses"
    ) -> "AoEShape":
        """
        Compute affected positions using caster's existing senses.

        For shapes where origin != caster position (e.g., Fireball exploding
        at target location), we compute FOV from the origin and intersect
        with caster's FOV. This ensures preview matches actual execution.

        Args:
            caster_pos: Caster's current position
            senses: Caster's Senses block with pre-computed visibility

        Returns:
            Self for chaining
        """
        self.computed_origin = self.get_origin(caster_pos)

        # Get positions visible to caster
        caster_fov = {pos for pos, vis in senses.visible.items() if vis}

        # If origin differs from caster, also compute origin's FOV
        # This handles cases like Fireball where explosion spreads from target
        if self.computed_origin != caster_pos:
            grid = get_map()
            origin_fov = set(
                grid.compute_fov(self.computed_origin, self._get_max_radius_tiles())
            )
            # Preview shows intersection: what caster sees AND what origin can hit
            perceived_fov = caster_fov & origin_fov
        else:
            perceived_fov = caster_fov

        # Get geometric positions in shape
        geometric = self._get_positions_in_shape(self.computed_origin)

        # Intersection: only positions both in shape AND in perceived FOV
        self.affected_positions = geometric & perceived_fov

        # Find entities at affected positions
        # When origin != caster, use GridMap for fresh entity data
        if self.computed_origin != caster_pos:
            grid = get_map()
            self.affected_entity_uuids = set()
            for pos in self.affected_positions:
                for uuid in grid.get_entities_at(pos):
                    self.affected_entity_uuids.add(uuid)
        else:
            # Use caster's perception (fast path)
            self.affected_entity_uuids = {
                uuid
                for uuid, pos in senses.entities.items()
                if pos in self.affected_positions
            }

        return self

    def compute_objective(self, caster_pos: Tuple[int, int]) -> "AoEShape":
        """
        Compute affected positions with fresh FOV from shape origin.

        This is more accurate (uses actual FOV from origin) but slower.
        Use for actual spell effects.

        Args:
            caster_pos: Caster's current position (for determining origin)

        Returns:
            Self for chaining
        """
        grid = get_map()
        self.computed_origin = self.get_origin(caster_pos)

        # Compute fresh FOV from shape origin
        fov_from_origin = set(
            grid.compute_fov(self.computed_origin, self._get_max_radius_tiles())
        )

        # Get geometric positions in shape
        geometric = self._get_positions_in_shape(self.computed_origin)

        # Intersection: only positions both in shape AND visible from origin
        self.affected_positions = geometric & fov_from_origin

        # Find all entities at affected positions
        self.affected_entity_uuids = set()
        for pos in self.affected_positions:
            for uuid in grid.get_entities_at(pos):
                self.affected_entity_uuids.add(uuid)

        return self


class Sphere(AoEShape):
    """
    Circular area centered on target position.

    D&D 5e: "A sphere's point of origin is included in the sphere's area of effect."
    """

    name: str = "Sphere"
    radius_feet: int = Field(default=20)

    def _default_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        return self.target

    def _get_max_radius_tiles(self) -> int:
        return self.radius_feet // 5

    def _get_positions_in_shape(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        return circle_positions(origin, self.radius_feet // 5, include_center=True)


class Cone(AoEShape):
    """
    Cone emanating from caster toward target.

    D&D 5e: "A cone extends in a direction you choose from its point of origin.
    A cone's width at a given point along its length is equal to that point's
    distance from the point of origin. A cone's area of effect specifies its
    maximum length."
    """

    name: str = "Cone"
    length_feet: int = Field(default=15)
    angle_degrees: int = Field(default=53)  # D&D 5e standard for "width = length"

    def _default_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        return caster_pos

    def _get_max_radius_tiles(self) -> int:
        return self.length_feet // 5

    def _get_positions_in_shape(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        return cone_positions(
            origin, self.target, self.length_feet // 5, self.angle_degrees
        )


class Line(AoEShape):
    """
    Line from caster toward target.

    D&D 5e: "A line extends from its point of origin in a straight path up to
    its length and covers an area defined by its width."
    """

    name: str = "Line"
    length_feet: int = Field(default=100)
    width_feet: int = Field(default=5)

    def _default_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        return caster_pos

    def _get_max_radius_tiles(self) -> int:
        return self.length_feet // 5

    def _get_positions_in_shape(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        width_tiles = max(1, self.width_feet // 5)
        return line_positions(origin, self.target, self.length_feet // 5, width_tiles)


class Cube(AoEShape):
    """
    Square/cube area.

    D&D 5e: "You select a cube's point of origin, which lies anywhere on a face
    of the cubic effect. The cube's size is expressed as the length of each side."

    Can be centered on target (for effects like Spirit Guardians) or extend
    from caster toward target (for effects like Thunderwave).
    """

    name: str = "Cube"
    size_feet: int = Field(default=15)
    centered: bool = Field(default=False)

    def _default_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        return self.target if self.centered else caster_pos

    def _get_max_radius_tiles(self) -> int:
        return self.size_feet // 5

    def _get_positions_in_shape(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        direction = None if self.centered else self.target
        return rectangle_positions(origin, self.size_feet // 5, direction, self.centered)
