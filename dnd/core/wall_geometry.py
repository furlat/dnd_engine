"""Pure wall-shell and one-sided band rasterization on five-foot cells."""

from math import ceil, floor, hypot

from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallDome, WallPolyline, WallPresentationGeometry, WallRing, WallSegment


def _segment_intersects_cell(path: WallSegment, x: int, y: int, half_width: float) -> bool:
    """Clip the finite centerline against the cell expanded by physical thickness."""
    start, end = path.start, path.end
    lower, upper = 0.0, 1.0
    for coordinate, delta, center in zip(start, (end[0] - start[0], end[1] - start[1]), (x, y)):
        low, high = center - .5 - half_width, center + .5 + half_width
        if delta == 0:
            if not low <= coordinate <= high:
                return False
            continue
        first, last = sorted(((low - coordinate) / delta, (high - coordinate) / delta))
        lower, upper = max(lower, first), min(upper, last)
        if lower > upper:
            return False
    return True


def wall_shell_cells(geometry: WallPresentationGeometry | WallAssemblyPresentationGeometry) -> set[tuple[int, int]]:
    """Return cells intersected by the physical shell, without map or propagation data."""
    path, half_width = geometry.path, geometry.width_feet / 10
    if isinstance(path, WallPolyline):
        return set().union(*(wall_shell_cells(WallAssemblyPresentationGeometry(
            path=WallSegment(start=first, end=second), base_height_steps=geometry.base_height_steps,
            width_feet=geometry.width_feet, height_feet=geometry.height_feet,
        )) for first, second in zip(path.points, path.points[1:])))
    if isinstance(path, WallSegment):
        bounds = (min(path.start[0], path.end[0]), max(path.start[0], path.end[0]),
                  min(path.start[1], path.end[1]), max(path.start[1], path.end[1]))
    else:
        radius = path.radius_feet / 5
        bounds = (path.center[0] - radius, path.center[0] + radius,
                  path.center[1] - radius, path.center[1] + radius)
    positions = set()
    for x in range(floor(bounds[0] - half_width - .5), ceil(bounds[1] + half_width + .5) + 1):
        for y in range(floor(bounds[2] - half_width - .5), ceil(bounds[3] + half_width + .5) + 1):
            if isinstance(path, WallSegment):
                intersects = _segment_intersects_cell(path, x, y, half_width)
            else:
                dx, dy = abs(x - path.center[0]), abs(y - path.center[1])
                nearest = hypot(max(0, dx - .5), max(0, dy - .5))
                farthest = hypot(dx + .5, dy + .5)
                intersects = nearest <= radius + half_width and farthest >= max(0, radius - half_width)
            if intersects:
                positions.add((x, y))
    if isinstance(geometry, WallAssemblyPresentationGeometry):
        positions = {position for position in positions if not any(
            volume.contains_band(position, geometry.base_height_steps)
            and (volume.base_height_steps + 2) * 5 >= geometry.base_height_steps * 5 + geometry.height_feet
            for volume in geometry.removed_sections)}
    return positions


def wall_side_cells(
    geometry: WallPresentationGeometry, side: str, reach_feet: int,
) -> set[tuple[int, int]]:
    """Return cell centers within a selected side's band, excluding flame cells."""
    shell = wall_shell_cells(geometry)
    if not shell:
        return set()
    reach = reach_feet / 5
    path = geometry.path
    positions = set()
    for x in range(floor(min(p[0] for p in shell) - reach), ceil(max(p[0] for p in shell) + reach) + 1):
        for y in range(floor(min(p[1] for p in shell) - reach), ceil(max(p[1] for p in shell) + reach) + 1):
            if (x, y) in shell:
                continue
            if isinstance(path, WallRing):
                distance = hypot(x - path.center[0], y - path.center[1])
                radius = path.radius_feet / 5
                on_side = distance < radius if side == "inside" else distance > radius
                within_reach = abs(distance - radius) <= reach
            else:
                dx, dy = path.end[0] - path.start[0], path.end[1] - path.start[1]
                rx, ry = x - path.start[0], y - path.start[1]
                projection = max(0.0, min(1.0, (rx * dx + ry * dy) / (dx * dx + dy * dy)))
                distance = hypot(rx - projection * dx, ry - projection * dy)
                cross = dx * ry - dy * rx
                on_side = cross > 0 if side == "left" else cross < 0
                within_reach = distance <= reach
            if on_side and within_reach:
                positions.add((x, y))
    return positions


def wall_crosses_path(geometry: WallAssemblyPresentationGeometry,
                      start: tuple[float, float], end: tuple[float, float]) -> bool:
    """Clip the existing shell by its retained full-height native apertures."""
    volumes = tuple(volume for volume in geometry.removed_sections
        if volume.base_height_steps <= geometry.base_height_steps
        and (volume.base_height_steps + 2) * 5 >= geometry.base_height_steps * 5 + geometry.height_feet)
    if not volumes:
        return _uncut_wall_crosses_path(geometry, start, end)
    delta = end[0] - start[0], end[1] - start[1]
    times = {0., 1.}
    for volume in volumes:
        for axis in (0, 1):
            if delta[axis] == 0:
                continue
            for boundary in (volume.minimum_position[axis] - .5, volume.minimum_position[axis] + 1.5):
                t = (boundary - start[axis]) / delta[axis]
                if 0 < t < 1:
                    times.add(t)
    ordered = sorted(times)
    for low, high in zip(ordered, ordered[1:]):
        midpoint = (start[0] + delta[0] * (low + high) / 2, start[1] + delta[1] * (low + high) / 2)
        if any(volume.contains_point(midpoint) for volume in volumes):
            continue
        first = start[0] + delta[0] * low, start[1] + delta[1] * low
        last = start[0] + delta[0] * high, start[1] + delta[1] * high
        if _uncut_wall_crosses_path(geometry, first, last):
            return True
    return False


def _uncut_wall_crosses_path(geometry: WallAssemblyPresentationGeometry,
                      start: tuple[float, float], end: tuple[float, float]) -> bool:
    """Actual shell intersection; same-side and hollow-interior legs remain clear."""
    if start == end:
        return False
    path = geometry.path
    if isinstance(path, WallPolyline):
        return any(wall_crosses_path(geometry.model_copy(update={
            "path": WallSegment(start=a, end=b)}), start, end)
            for a, b in zip(path.points, path.points[1:]))
    if isinstance(path, (WallRing, WallDome)):
        radius = path.radius_feet / 5
        dx, dy = end[0] - start[0], end[1] - start[1]
        rx, ry = start[0] - path.center[0], start[1] - path.center[1]
        quadratic = dx * dx + dy * dy
        projection = max(0., min(1., -(rx * dx + ry * dy) / quadratic))
        nearest = hypot(rx + projection * dx, ry + projection * dy)
        farthest = max(hypot(rx, ry), hypot(end[0] - path.center[0], end[1] - path.center[1]))
        return nearest <= radius + geometry.width_feet / 10 and farthest >= radius - geometry.width_feet / 10
    dx, dy = path.end[0] - path.start[0], path.end[1] - path.start[1]
    ax, ay = end[0] - start[0], end[1] - start[1]
    denominator = ax * dy - ay * dx
    if abs(denominator) < 1e-9:
        # A leg running along a sheet intersects its thickness, too.
        distance = abs(dx * (start[1] - path.start[1]) - dy * (start[0] - path.start[0])) / hypot(dx, dy)
        projection = ((start[0] - path.start[0]) * dx + (start[1] - path.start[1]) * dy) / (dx * dx + dy * dy)
        end_projection = ((end[0] - path.start[0]) * dx + (end[1] - path.start[1]) * dy) / (dx * dx + dy * dy)
        return distance <= geometry.width_feet / 10 and max(projection, end_projection) >= 0 and min(projection, end_projection) <= 1
    rx, ry = path.start[0] - start[0], path.start[1] - start[1]
    t = (rx * dy - ry * dx) / denominator
    u = (rx * ay - ry * ax) / denominator
    return 0 <= t <= 1 and 0 <= u <= 1


def wall_path_contact(geometry: WallAssemblyPresentationGeometry,
                      start: tuple[float, float], end: tuple[float, float],
                      admitted: set[tuple[int, int]] | None = None) -> tuple[float, float] | None:
    """First physical intersection in admitted cells, independent of raster endpoints."""
    if start == end:
        return None
    delta = end[0] - start[0], end[1] - start[1]
    boundaries = {0., 1.}
    for axis in (0, 1):
        if delta[axis] == 0:
            continue
        for cell in range(floor(min(start[axis], end[axis]) - .5),
                          ceil(max(start[axis], end[axis]) - .5) + 1):
            t = (cell + .5 - start[axis]) / delta[axis]
            if 0 < t < 1:
                boundaries.add(t)
    times = sorted(boundaries)
    for low, high in zip(times, times[1:]):
        midpoint = tuple(start[i] + delta[i] * (low + high) / 2 for i in (0, 1))
        cell = floor(midpoint[0] + .5), floor(midpoint[1] + .5)
        if admitted is not None and cell not in admitted:
            continue
        first = start[0] + delta[0] * low, start[1] + delta[1] * low
        last = start[0] + delta[0] * high, start[1] + delta[1] * high
        if not wall_crosses_path(geometry, first, last):
            continue
        left, right = low, high
        for _ in range(30):
            mid = (left + right) / 2
            point = start[0] + delta[0] * mid, start[1] + delta[1] * mid
            if wall_crosses_path(geometry, first, point):
                right = mid
            else:
                left = mid
        return start[0] + delta[0] * right, start[1] + delta[1] * right
    return None
