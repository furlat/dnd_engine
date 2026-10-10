"""Pure directional bank selection and disclosed wall-profile capability checks."""

from math import cos, hypot, isclose, radians
from typing import Collection
from dnd.core.presentation_geometry import AoEPresentationGeometry, WallPresentationGeometry, WallSegment, WallRing
from dnd.core.wall_geometry import wall_shell_cells
from game.animation_types import SpatialMediaBinding, SpatialMediaLayer, WallAxisMedia

_AXIS_TANGENTS = {"x": (1, 0), "y": (0, 1),
                  "diagonal_positive": (1, 1), "diagonal_negative": (1, -1)}


def select_wall_bank(layer: SpatialMediaLayer, path: WallSegment) -> WallAxisMedia | None:
    dx, dy = path.end[0]-path.start[0], path.end[1]-path.start[1]
    length = hypot(dx, dy)
    def alignment(bank: WallAxisMedia) -> float:
        x, y = _AXIS_TANGENTS[bank.axis]
        return abs(dx*x+dy*y)/(length*hypot(x, y))
    bank = max(layer.wallAxes, key=alignment)
    return bank if alignment(bank)+1e-9 >= cos(radians(bank.maxAngleDegrees)) else None


def wall_media_limitation(geometry: AoEPresentationGeometry | None,
                         binding: SpatialMediaBinding | None = None, *,
                         positions: Collection[tuple[int, int]] | None = None,
                         suppressed: bool = False) -> str | None:
    """Missing native directional coverage remains an explicit presentation gap."""
    if not isinstance(geometry, WallPresentationGeometry):
        return "Wall module media requires retained wall geometry"
    if isinstance(geometry.path, WallRing):
        if binding is None or any(layer.wallRing is None for layer in binding.layers
                                 if layer.composition == "wall_modules"):
            return "Curved wall media has not been delivered"
        if any(not isclose(layer.wallRing.radiusFeet, geometry.path.radius_feet)
               or not isclose(layer.wallRing.widthFeet, geometry.width_feet)
               for layer in binding.layers if layer.wallRing is not None):
            return "Ring media does not match the recorded radius/width"
        if suppressed or positions is not None and not wall_shell_cells(geometry) <= set(positions):
            return "Whole-ring media requires a complete disclosed, unprotected shell"
        return None
    if binding is not None:
        if any(select_wall_bank(layer, geometry.path) is None for layer in binding.layers
               if layer.composition == "wall_modules"):
            return "Diagonal directional wall modules have not been delivered for this angle"
    elif not (isclose(geometry.path.start[0], geometry.path.end[0])
              or isclose(geometry.path.start[1], geometry.path.end[1])):
        return "Diagonal directional wall modules have not been delivered"
    return None


