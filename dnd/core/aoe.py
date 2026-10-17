"""Area-of-effect shapes as frozen values, and the one objective footprint.

A shape holds only its definition. The aim and the source an area spreads from
are call inputs, so one shape value serves every aim, template and zone that
declares the same area.
"""
from __future__ import annotations

from math import ceil, gcd, sqrt
from typing import AbstractSet, ClassVar, FrozenSet, Literal, Optional, Set, Tuple

from pydantic import BaseModel, ConfigDict, Field

from dnd.core.geometry import (
    circle_positions,
    cube_axis,
    cone_positions,
    line_positions,
    rectangle_positions,
)
from dnd.core.gridmap import get_map
from dnd.core.presentation_geometry import (
    AoEAimingGeometry,
    AoEPresentationGeometry,
    ConePresentationGeometry,
    CubePresentationGeometry,
    CylinderPresentationGeometry,
    LinePresentationGeometry,
    SpherePresentationGeometry,
)
from dnd.types.spatial_effects import AreaPropagation

Position = Tuple[int, int]
FootprintIdentity = Tuple["AoEShape", Optional[Position], Tuple[object, ...]]


class AoEShape(BaseModel):
    """One immutable area definition; aims and sources are never stored."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ClassVar[Literal["sphere", "cone", "line", "cube", "cylinder"]]
    propagation: AreaPropagation = Field(
        default="line_of_effect",
        description="How the area spreads from its origin through the map.",
    )

    def emanates_from_aim(self) -> bool:
        """Whether the aim is the area's origin rather than its direction."""
        raise NotImplementedError

    def max_radius_tiles(self) -> int:
        """Largest authored distance from the origin, in tiles."""
        raise NotImplementedError

    def extent_feet(self) -> int:
        """The authored size presented as the area's extent."""
        raise NotImplementedError

    def positions_from(self, origin: Position, aim: Position) -> Set[Position]:
        """Return the geometric envelope spreading from ``origin`` toward ``aim``."""
        raise NotImplementedError

    def presentation_from(self, origin: Position, aim: Position) -> AoEPresentationGeometry:
        """Return the cold presentation geometry from ``origin`` toward ``aim``."""
        raise NotImplementedError

    def get_origin(self, aim: Position, source_pos: Position) -> Position:
        """Return the cell the area spreads from."""
        return aim if self.emanates_from_aim() else source_pos

    def geometric_positions(self, aim: Position, source_pos: Position) -> Set[Position]:
        """Return the finite envelope before barriers or protection."""
        return self.positions_from(self.get_origin(aim, source_pos), aim)

    def presentation_geometry(self, aim: Position, source_pos: Position) -> AoEPresentationGeometry:
        """Return the exact immutable geometry of this area at one aim."""
        return self.presentation_from(self.get_origin(aim, source_pos), aim)

    def footprint_target_key(self, aim: Position, source_pos: Position) -> Tuple[object, ...]:
        """Return the aim identity that determines this footprint."""
        return ("target", *aim)

    def _ray_key(self, aim: Position, source_pos: Position) -> Tuple[object, ...]:
        """Return the canonical integer ray from the source through the aim."""
        delta_x = aim[0] - source_pos[0]
        delta_y = aim[1] - source_pos[1]
        divisor = gcd(abs(delta_x), abs(delta_y)) or 1
        return ("ray", delta_x // divisor, delta_y // divisor)


class Sphere(AoEShape):
    """Circular area centered on the aim; its origin is in the area."""

    kind: ClassVar[Literal["sphere"]] = "sphere"
    radius_feet: int = Field(default=20, description="Sphere radius in feet.")

    def emanates_from_aim(self) -> bool:
        return True

    def max_radius_tiles(self) -> int:
        return self.radius_feet // 5

    def extent_feet(self) -> int:
        return self.radius_feet

    def positions_from(self, origin: Position, aim: Position) -> Set[Position]:
        return circle_positions(origin, self.max_radius_tiles(), include_center=True)

    def presentation_from(self, origin: Position, aim: Position) -> AoEPresentationGeometry:
        return SpherePresentationGeometry(center=origin, radius_feet=self.radius_feet)


class Cone(AoEShape):
    """Cone extending from the source toward the aim, up to its length."""

    kind: ClassVar[Literal["cone"]] = "cone"
    length_feet: int = Field(default=15, description="Cone maximum length in feet.")
    angle_degrees: int = Field(default=53, description="Cone angle in degrees.")

    def emanates_from_aim(self) -> bool:
        return False

    def max_radius_tiles(self) -> int:
        return self.length_feet // 5

    def extent_feet(self) -> int:
        return self.length_feet

    def footprint_target_key(self, aim: Position, source_pos: Position) -> Tuple[object, ...]:
        """Distance along the ray does not alter a cone's area."""
        return self._ray_key(aim, source_pos)

    def positions_from(self, origin: Position, aim: Position) -> Set[Position]:
        return cone_positions(origin, aim, self.max_radius_tiles(), self.angle_degrees)

    def presentation_from(self, origin: Position, aim: Position) -> AoEPresentationGeometry:
        return ConePresentationGeometry(origin=origin, direction=(aim[0] - origin[0], aim[1] - origin[1]),
            length_feet=self.length_feet, angle_degrees=self.angle_degrees)


class Line(AoEShape):
    """Line extending from the source toward the aim, with a width."""

    kind: ClassVar[Literal["line"]] = "line"
    length_feet: int = Field(default=100, description="Line length in feet.")
    width_feet: int = Field(default=5, description="Line width in feet.")

    def emanates_from_aim(self) -> bool:
        return False

    def max_radius_tiles(self) -> int:
        return self.length_feet // 5

    def extent_feet(self) -> int:
        return self.length_feet

    def footprint_target_key(self, aim: Position, source_pos: Position) -> Tuple[object, ...]:
        """Distance along the ray does not alter a line's area."""
        return self._ray_key(aim, source_pos)

    def positions_from(self, origin: Position, aim: Position) -> Set[Position]:
        return line_positions(origin, aim, self.max_radius_tiles(), max(1, self.width_feet // 5))

    def presentation_from(self, origin: Position, aim: Position) -> AoEPresentationGeometry:
        return LinePresentationGeometry(origin=origin, direction=(aim[0] - origin[0], aim[1] - origin[1]),
            length_feet=self.length_feet, width_feet=self.width_feet)


class Cube(AoEShape):
    """Square area centered on the aim, or extending from the source toward it."""

    kind: ClassVar[Literal["cube"]] = "cube"
    size_feet: int = Field(default=15, description="Cube side length in feet.")
    centered: bool = Field(default=False, description="Whether the cube is centered on the aim.")

    def emanates_from_aim(self) -> bool:
        return self.centered

    def max_radius_tiles(self) -> int:
        return self.size_feet // 5

    def extent_feet(self) -> int:
        return self.size_feet

    def footprint_target_key(self, aim: Position, source_pos: Position) -> Tuple[object, ...]:
        """Return the center, or the cardinal side an extended cube grows toward."""
        if self.centered:
            return super().footprint_target_key(aim, source_pos)
        return ("axis", *cube_axis(source_pos, aim))

    def positions_from(self, origin: Position, aim: Position) -> Set[Position]:
        return rectangle_positions(origin, self.max_radius_tiles(), None if self.centered else aim, self.centered)

    def presentation_from(self, origin: Position, aim: Position) -> AoEPresentationGeometry:
        return CubePresentationGeometry(origin=origin,
            direction=None if self.centered else (aim[0] - origin[0], aim[1] - origin[1]),
            size_feet=self.size_feet, centered=self.centered)


class Cylinder(AoEShape):
    """Circle centered on the aim, falling from above or rising from below.

    By default a cylinder ignores lateral barriers: it hits its whole circle,
    even behind walls. Height is retained for presentation only.
    """

    kind: ClassVar[Literal["cylinder"]] = "cylinder"
    propagation: AreaPropagation = Field(
        default="ignore_barriers",
        description="How the area spreads from its origin through the map.",
    )
    radius_feet: int = Field(default=20, description="Cylinder radius in feet.")
    height_feet: int = Field(default=40, description="Cylinder height in feet.")

    def emanates_from_aim(self) -> bool:
        return True

    def max_radius_tiles(self) -> int:
        return self.radius_feet // 5

    def extent_feet(self) -> int:
        return self.radius_feet

    def positions_from(self, origin: Position, aim: Position) -> Set[Position]:
        return circle_positions(origin, self.max_radius_tiles(), include_center=True)

    def presentation_from(self, origin: Position, aim: Position) -> AoEPresentationGeometry:
        return CylinderPresentationGeometry(center=origin, radius_feet=self.radius_feet,
            height_feet=self.height_feet)


def objective_footprint(shape: AoEShape, aim: Position, source_pos: Position) -> FrozenSet[Position]:
    """Return the map cells an area reaches, before spell protection.

    The footprint reads only the map, never a perceiver; callers derive
    occupants from it and GridMap occupancy at their own call site.

    Args:
        shape: Area definition.
        aim: Selected aim: the origin of aim-centered shapes, else the direction.
        source_pos: Cell that source-centered shapes (cones, lines, extended
            cubes) spread from.

    Returns:
        Existing map cells of the envelope that the area's propagation reaches.
    """
    origin = shape.get_origin(aim, source_pos)
    envelope = shape.positions_from(origin, aim)
    grid = get_map()
    if shape.propagation == "connected":
        return frozenset(grid.connected_propagation_positions(origin, envelope))
    if shape.propagation == "ignore_barriers":
        return frozenset(cell for cell in envelope if grid.has_tile(*cell))
    return line_of_effect_reach(origin, envelope)


def line_of_effect_reach(origin: Position, cells: AbstractSet[Position]) -> FrozenSet[Position]:
    """Return the cells the native propagation ray from ``origin`` reaches.

    The reach radius covers the farthest cell; a widened or rounded line
    ends slightly beyond its authored length.
    """
    farthest = max(((x - origin[0]) ** 2 + (y - origin[1]) ** 2 for x, y in cells), default=0)
    return frozenset(get_map().compute_propagation_fov(origin, ceil(sqrt(farthest)))).intersection(cells)


def footprint_identity(shape: AoEShape, aim: Position, source_pos: Position) -> FootprintIdentity:
    """Return the identity two aimed casts share exactly when their footprints are equal.

    A source-centered area also depends on where its source stands.
    """
    return (shape, None if shape.emanates_from_aim() else source_pos, shape.footprint_target_key(aim, source_pos))


def snapshot_aoe_aiming_geometry(shape: AoEShape, source_pos: Position) -> AoEAimingGeometry:
    """Describe native aiming at a reference aim one cell east of the source."""
    reference = (source_pos[0] + 1, source_pos[1])
    return AoEAimingGeometry(geometry=shape.presentation_geometry(reference, source_pos),
        reference_target=reference, origin_mode="aim" if shape.emanates_from_aim() else "fixed",
        propagation=shape.propagation)
