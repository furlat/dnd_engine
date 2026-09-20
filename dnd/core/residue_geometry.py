"""Small geometric operations for deposited material, independent of world owners."""

from math import cos, floor, sin, sqrt

from dnd.types.residues import ResidueEllipse


def ellipse_intersects_tile(ellipse: ResidueEllipse, position: tuple[int, int]) -> bool:
    """Positive-area ellipse/square intersection, including a narrow edge crossing."""
    x0, y0 = position[0] - .5 - ellipse.center[0], position[1] - .5 - ellipse.center[1]
    x1, y1 = x0 + 1, y0 + 1
    if x0 <= 0 <= x1 and y0 <= 0 <= y1:
        return True
    co, si = cos(ellipse.angle), sin(ellipse.angle)
    rx2, ry2 = ellipse.radius_x ** 2, ellipse.radius_y ** 2
    a, b, c = co * co / rx2 + si * si / ry2, co * si * (1 / rx2 - 1 / ry2), si * si / rx2 + co * co / ry2
    for x in (x0, x1):
        y = min(y1, max(y0, -b * x / c))
        if a * x * x + 2 * b * x * y + c * y * y < 1:
            return True
    for y in (y0, y1):
        x = min(x1, max(x0, -b * y / a))
        if a * x * x + 2 * b * x * y + c * y * y < 1:
            return True
    return False


def ellipse_tiles(ellipse: ResidueEllipse) -> tuple[tuple[int, int], ...]:
    co, si = cos(ellipse.angle), sin(ellipse.angle)
    ex = sqrt((ellipse.radius_x * co) ** 2 + (ellipse.radius_y * si) ** 2)
    ey = sqrt((ellipse.radius_x * si) ** 2 + (ellipse.radius_y * co) ** 2)
    return tuple((x, y)
        for x in range(floor(ellipse.center[0] - ex + .5), floor(ellipse.center[0] + ex + .5) + 1)
        for y in range(floor(ellipse.center[1] - ey + .5), floor(ellipse.center[1] + ey + .5) + 1)
        if ellipse_intersects_tile(ellipse, (x, y)))


def place_ellipse(ellipse: ResidueEllipse, origin: tuple[int, int], angle: float) -> ResidueEllipse:
    co, si = cos(angle), sin(angle)
    x, y = ellipse.center
    return ResidueEllipse(center=(origin[0] + co * x - si * y, origin[1] + si * x + co * y),
        radius_x=ellipse.radius_x, radius_y=ellipse.radius_y, angle=ellipse.angle + angle)


def local_ellipse(ellipse: ResidueEllipse, position: tuple[int, int]) -> ResidueEllipse:
    return ResidueEllipse(center=(ellipse.center[0] - position[0], ellipse.center[1] - position[1]),
        radius_x=ellipse.radius_x, radius_y=ellipse.radius_y, angle=ellipse.angle)
