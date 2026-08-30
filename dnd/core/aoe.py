"""Area-of-effect shape models for targeting and spell execution."""
from __future__ import annotations

from math import gcd
from typing import AbstractSet, Optional, Set, Tuple
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
from dnd.core.presentation_geometry import (
    AoEPresentationGeometry,
    ConePresentationGeometry,
    CubePresentationGeometry,
    CylinderPresentationGeometry,
    LinePresentationGeometry,
    SpherePresentationGeometry,
)
from dnd.blocks.sensory import Senses


class AoEShape(BaseObject):
    """Base model for geometric AoE shapes.

    `compute_subjective()` uses caster senses for previews. `compute_objective()`
    recomputes propagation from the shape origin for execution. Both methods
    store affected positions and entity UUIDs on the shape instance.
    """

    use_register: bool = Field(default=False, description="AoE preview objects are not registered by default.")
    target: Tuple[int, int] = Field(default=(0, 0), description="Target or direction point for the shape.")
    origin_override: Optional[Tuple[int, int]] = Field(default=None, description="Explicit origin used instead of the shape default.")
    computed_origin: Optional[Tuple[int, int]] = Field(default=None, description="Origin used by the last computation.")
    affected_positions: Set[Tuple[int, int]] = Field(default_factory=set, description="Positions affected by the last computation.")
    affected_entity_uuids: Set[UUID] = Field(default_factory=set, description="Entity UUIDs affected by the last computation.")

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
        """Return the explicit or default origin for this shape."""
        return self.origin_override or self._default_origin(caster_pos)

    def footprint_target_key(self, caster_pos: Tuple[int, int]) -> Tuple[object, ...]:
        """Return the target coordinate identity that determines this footprint."""
        return ("target", *self.target)

    def _normalized_direction_key(
        self,
        caster_pos: Tuple[int, int],
    ) -> Tuple[object, ...]:
        """Return a canonical integer ray from this shape's current origin."""
        origin_x, origin_y = self.get_origin(caster_pos)
        delta_x = self.target[0] - origin_x
        delta_y = self.target[1] - origin_y
        divisor = gcd(abs(delta_x), abs(delta_y)) or 1
        return ("ray", delta_x // divisor, delta_y // divisor)

    def compute_subjective(
        self,
        caster_pos: Tuple[int, int],
        senses: "Senses",
        fov_cache: Optional[dict[tuple[tuple[int, int], int], Set[tuple[int, int]]]] = None,
        barrier_positions: Optional[Set[Tuple[int, int]]] = None,
        caster_uuid: Optional[UUID] = None,
        caster_visible_positions: Optional[AbstractSet[Tuple[int, int]]] = None,
    ) -> "AoEShape":
        """Compute affected positions using caster-visible state.

        For shapes where origin != caster position (e.g., Fireball exploding
        at target location), we compute FOV from the origin and intersect
        with caster's FOV. This ensures preview matches actual execution.

        AoE propagation uses physical barriers only (walls, closed doors);
        magical darkness does NOT block AoE spread per D&D 5e rules.

        Args:
            caster_pos: Caster's current position.
            senses: Caster's Senses block with pre-computed visibility.
            fov_cache: Optional cache for FOV computations keyed by (origin, radius).
                When provided, avoids redundant propagation FOV calls.
            barrier_positions: Optional pre-computed set of positions that block AoE
                propagation.
            caster_uuid: Optional caster UUID that is always known to the caster.
            caster_visible_positions: Optional immutable visibility snapshot shared
                by every candidate in one action-discovery query.

        Returns:
            Self for chaining.
        """
        self.computed_origin = self.get_origin(caster_pos)

        caster_fov = (
            caster_visible_positions
            if caster_visible_positions is not None
            else {pos for pos, visible in senses.visible.items() if visible}
        )

        if self.computed_origin != caster_pos:
            geometric = self._get_positions_in_shape(self.computed_origin)

            if barrier_positions is not None and geometric.isdisjoint(barrier_positions):
                origin_fov = geometric
            else:
                cache_key = (self.computed_origin, self._get_max_radius_tiles())
                if fov_cache is not None and cache_key in fov_cache:
                    origin_fov = fov_cache[cache_key]
                else:
                    grid = get_map()
                    origin_fov = set(
                        grid.compute_propagation_fov(
                            self.computed_origin, self._get_max_radius_tiles()
                        )
                    )
                    if fov_cache is not None:
                        fov_cache[cache_key] = origin_fov

            if origin_fov is geometric:
                self.affected_positions = geometric.intersection(caster_fov)
            else:
                self.affected_positions = geometric.intersection(caster_fov, origin_fov)
        else:
            geometric = self._get_positions_in_shape(self.computed_origin)
            self.affected_positions = geometric.intersection(caster_fov)

        self._resolve_subjective_entities(caster_pos, senses, caster_uuid)
        return self

    def set_subjective_footprint(
        self,
        caster_pos: Tuple[int, int],
        senses: "Senses",
        affected_positions: Set[Tuple[int, int]],
        caster_uuid: Optional[UUID] = None,
    ) -> "AoEShape":
        """Restore a cached footprint and resolve current perceived occupants.

        Args:
            caster_pos: Caster position used to resolve this shape's origin.
            senses: Current caster senses used to authorize affected entities.
            affected_positions: Cached geometry and propagation result.
            caster_uuid: Optional caster UUID that remains self-perceivable.

        Returns:
            Self with current subjective entity occupancy applied.
        """
        self.computed_origin = self.get_origin(caster_pos)
        self.affected_positions = set(affected_positions)
        self._resolve_subjective_entities(caster_pos, senses, caster_uuid)
        return self

    def _resolve_subjective_entities(
        self,
        caster_pos: Tuple[int, int],
        senses: "Senses",
        caster_uuid: Optional[UUID],
    ) -> None:
        """Populate perceived occupants for the current subjective footprint."""
        self.affected_entity_uuids = {
            entity_uuid
            for entity_uuid, contact in senses.entities.items()
            for pos in (contact.position,)
            if pos in self.affected_positions
        }
        if (
            self.computed_origin != caster_pos
            and caster_uuid is not None
            and caster_pos in self.affected_positions
        ):
            self.affected_entity_uuids.add(caster_uuid)

    def compute_objective(self, caster_pos: Tuple[int, int]) -> "AoEShape":
        """Compute affected positions from actual propagation state.

        This is more accurate (uses actual FOV from origin) but slower.
        Use for actual spell effects.

        AoE propagation uses physical barriers only (walls, closed doors);
        magical darkness does NOT block AoE spread per D&D 5e rules.

        Args:
            caster_pos: Caster's current position for determining origin.

        Returns:
            Self for chaining.
        """
        grid = get_map()
        self.computed_origin = self.get_origin(caster_pos)

        geometric = self._get_positions_in_shape(self.computed_origin)

        barriers = grid.get_barrier_positions()
        if geometric.isdisjoint(barriers):
            self.affected_positions = geometric
        else:
            fov_from_origin = set(
                grid.compute_propagation_fov(
                    self.computed_origin, self._get_max_radius_tiles()
                )
            )
            self.affected_positions = geometric.intersection(fov_from_origin)

        self.affected_entity_uuids = set()
        for pos in self.affected_positions:
            for uuid in grid.get_entities_at(pos):
                self.affected_entity_uuids.add(uuid)

        return self


class Sphere(AoEShape):
    """Circular area centered on target position.

    D&D 5e: "A sphere's point of origin is included in the sphere's area of effect."
    """

    name: str = Field(default="Sphere", description="AoE shape name.")
    radius_feet: int = Field(default=20, description="Sphere radius in feet.")

    def _default_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        return self.target

    def _get_max_radius_tiles(self) -> int:
        return self.radius_feet // 5

    def _get_positions_in_shape(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        return circle_positions(origin, self.radius_feet // 5, include_center=True)


class Cone(AoEShape):
    """Cone emanating from caster toward target.

    D&D 5e: "A cone extends in a direction you choose from its point of origin.
    A cone's width at a given point along its length is equal to that point's
    distance from the point of origin. A cone's area of effect specifies its
    maximum length."
    """

    name: str = Field(default="Cone", description="AoE shape name.")
    length_feet: int = Field(default=15, description="Cone maximum length in feet.")
    angle_degrees: int = Field(default=53, description="Cone angle in degrees.")

    def _default_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        return caster_pos

    def _get_max_radius_tiles(self) -> int:
        return self.length_feet // 5

    def footprint_target_key(self, caster_pos: Tuple[int, int]) -> Tuple[object, ...]:
        """Return the canonical cone ray because distance does not alter its area."""
        return self._normalized_direction_key(caster_pos)

    def _get_positions_in_shape(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        return cone_positions(
            origin, self.target, self.length_feet // 5, self.angle_degrees
        )


class Line(AoEShape):
    """Line from caster toward target.

    D&D 5e: "A line extends from its point of origin in a straight path up to
    its length and covers an area defined by its width."
    """

    name: str = Field(default="Line", description="AoE shape name.")
    length_feet: int = Field(default=100, description="Line length in feet.")
    width_feet: int = Field(default=5, description="Line width in feet.")

    def _default_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        return caster_pos

    def _get_max_radius_tiles(self) -> int:
        return self.length_feet // 5

    def footprint_target_key(self, caster_pos: Tuple[int, int]) -> Tuple[object, ...]:
        """Return the canonical line ray because distance does not alter its area."""
        return self._normalized_direction_key(caster_pos)

    def _get_positions_in_shape(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        width_tiles = max(1, self.width_feet // 5)
        return line_positions(origin, self.target, self.length_feet // 5, width_tiles)


class Cube(AoEShape):
    """Square/cube area.

    D&D 5e: "You select a cube's point of origin, which lies anywhere on a face
    of the cubic effect. The cube's size is expressed as the length of each side."

    Can be centered on target (for effects like Spirit Guardians) or extend
    from caster toward target (for effects like Thunderwave).
    """

    name: str = Field(default="Cube", description="AoE shape name.")
    size_feet: int = Field(default=15, description="Cube side length in feet.")
    centered: bool = Field(default=False, description="Whether the cube is centered on target.")

    def _default_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        return self.target if self.centered else caster_pos

    def _get_max_radius_tiles(self) -> int:
        return self.size_feet // 5

    def footprint_target_key(self, caster_pos: Tuple[int, int]) -> Tuple[object, ...]:
        """Return the center or cardinal extension that determines this cube."""
        if self.centered:
            return super().footprint_target_key(caster_pos)
        origin_x, origin_y = self.get_origin(caster_pos)
        delta_x = self.target[0] - origin_x
        delta_y = self.target[1] - origin_y
        if abs(delta_x) >= abs(delta_y):
            return ("axis", "x", 1 if delta_x >= 0 else -1)
        return ("axis", "y", 1 if delta_y >= 0 else -1)

    def _get_positions_in_shape(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        direction = None if self.centered else self.target
        return rectangle_positions(origin, self.size_feet // 5, direction, self.centered)


class Cylinder(AoEShape):
    """Cylindrical area centered on target position.

    On 2D grid: identical to Sphere (circle of given radius).
    Height stored for future Z-axis support.

    IMPORTANT: Cylinders come from above/below, so they ignore physical
    barriers (walls) within the area — no shadowcast/LOS filtering.
    A cylinder hits everything in its geometric circle, even behind corners.
    """

    name: str = Field(default="Cylinder", description="AoE shape name.")
    radius_feet: int = Field(default=20, description="Cylinder radius in feet.")
    height_feet: int = Field(default=40, description="Cylinder height in feet.")

    def _default_origin(self, caster_pos: Tuple[int, int]) -> Tuple[int, int]:
        return self.target

    def _get_max_radius_tiles(self) -> int:
        return self.radius_feet // 5

    def _get_positions_in_shape(self, origin: Tuple[int, int]) -> Set[Tuple[int, int]]:
        return circle_positions(origin, self.radius_feet // 5, include_center=True)

    def compute_subjective(
        self,
        caster_pos: Tuple[int, int],
        senses: "Senses",
        fov_cache: Optional[dict[tuple[tuple[int, int], int], Set[tuple[int, int]]]] = None,
        barrier_positions: Optional[Set[Tuple[int, int]]] = None,
        caster_uuid: Optional[UUID] = None,
        caster_visible_positions: Optional[AbstractSet[Tuple[int, int]]] = None,
    ) -> "AoEShape":
        """Compute cylinder previews using full footprint and perceived entities."""
        return self.compute_for_targeting(
            caster_pos,
            senses,
            fov_cache=fov_cache,
            barrier_positions=barrier_positions,
            caster_uuid=caster_uuid,
            caster_visible_positions=caster_visible_positions,
        )

    def compute_for_targeting(
        self,
        caster_pos: Tuple[int, int],
        senses: "Senses",
        fov_cache: Optional[dict[tuple[tuple[int, int], int], Set[tuple[int, int]]]] = None,
        barrier_positions: Optional[Set[Tuple[int, int]]] = None,
        caster_uuid: Optional[UUID] = None,
        caster_visible_positions: Optional[AbstractSet[Tuple[int, int]]] = None,
    ) -> "AoEShape":
        """Cylinder ignores barriers — hits full geometric area from above/below.

        Only filters entities by caster perception (can't target what you can't see).
        """
        self.computed_origin = self.get_origin(caster_pos)
        geometric = self._get_positions_in_shape(self.computed_origin)
        self.affected_positions = geometric

        self.affected_entity_uuids = set()
        grid = get_map()
        for pos in self.affected_positions:
            for entity_uuid in grid.get_entities_at(pos):
                if entity_uuid in senses.entities or entity_uuid == caster_uuid:
                    self.affected_entity_uuids.add(entity_uuid)

        return self

    def compute_objective(self, caster_pos: Tuple[int, int]) -> "AoEShape":
        """Cylinder ignores barriers — hits full geometric area from above/below.

        No shadowcast/LOS filtering: the effect rains down vertically.
        """
        self.computed_origin = self.get_origin(caster_pos)
        geometric = self._get_positions_in_shape(self.computed_origin)
        self.affected_positions = geometric

        grid = get_map()
        self.affected_entity_uuids = set()
        for pos in self.affected_positions:
            for uuid in grid.get_entities_at(pos):
                self.affected_entity_uuids.add(uuid)

        return self


def snapshot_aoe_presentation_geometry(
    shape: AoEShape,
    caster_position: Tuple[int, int],
    *,
    target_override: Optional[Tuple[int, int]] = None,
) -> AoEPresentationGeometry:
    """Return the exact immutable presentation geometry for one declared AoE.

    Position-targeted action instances keep their selected cell separately
    from the reusable shape template. ``target_override`` therefore takes the
    declared action target without mutating or copying the runtime shape.

    Args:
        shape: Runtime area shape owned by the action definition.
        caster_position: Caster position at declaration time.
        target_override: Selected action position, when different from the
            reusable shape template's default target.

    Returns:
        A strict shape-specific cold geometry fact.

    Raises:
        TypeError: If a new runtime shape has no presentation contract.
    """
    target = shape.target if target_override is None else target_override
    if shape.origin_override is not None:
        origin = shape.origin_override
    elif isinstance(shape, (Sphere, Cylinder)):
        origin = target
    elif isinstance(shape, Cube) and shape.centered:
        origin = target
    else:
        origin = caster_position

    direction = (target[0] - origin[0], target[1] - origin[1])
    if isinstance(shape, Sphere):
        return SpherePresentationGeometry(
            center=origin,
            radius_feet=shape.radius_feet,
        )
    if isinstance(shape, Cone):
        return ConePresentationGeometry(
            origin=origin,
            direction=direction,
            length_feet=shape.length_feet,
            angle_degrees=shape.angle_degrees,
        )
    if isinstance(shape, Line):
        return LinePresentationGeometry(
            origin=origin,
            direction=direction,
            length_feet=shape.length_feet,
            width_feet=shape.width_feet,
        )
    if isinstance(shape, Cube):
        return CubePresentationGeometry(
            origin=origin,
            direction=None if shape.centered else direction,
            size_feet=shape.size_feet,
            centered=shape.centered,
        )
    if isinstance(shape, Cylinder):
        return CylinderPresentationGeometry(
            center=origin,
            radius_feet=shape.radius_feet,
            height_feet=shape.height_feet,
        )
    raise TypeError(
        f"AoE shape {type(shape).__name__} has no presentation geometry contract"
    )
