"""Pure isometric projection, painter ordering, and support picking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, TypeVar
from uuid import UUID


MAP_CENTER = (31.5, 31.5)
TILE_WIDTH = 128.0
TILE_HEIGHT = 64.0
HEIGHT_STEP_PIXELS = 64.0
ZOOM_LEVELS = (0.15, 0.35, 0.5, 0.75, 1.0)
_ROTATION_COEFFICIENTS = (
    (1.0, 0.0, 0.0, 1.0),
    (0.0, -1.0, 1.0, 0.0),
    (-1.0, 0.0, 0.0, -1.0),
    (0.0, 1.0, -1.0, 0.0),
)


@dataclass(frozen=True, slots=True)
class Camera:
    """Small immutable screen-space camera value."""

    quadrant: int = 0
    zoom: float = 0.5
    pan: tuple[float, float] = (0.0, 0.0)
    viewport: tuple[int, int] = (1280, 720)

    def __post_init__(self) -> None:
        if self.quadrant not in range(4):
            raise ValueError("camera quadrant must be 0 through 3")
        if self.zoom not in ZOOM_LEVELS:
            raise ValueError("camera zoom is not one of the finite zoom levels")
        if self.viewport[0] <= 0 or self.viewport[1] <= 0:
            raise ValueError("camera viewport dimensions must be positive")

    def with_focus(
        self,
        position: tuple[float, float],
        *,
        elevation_steps: int = 0,
    ) -> "Camera":
        """Return a camera whose viewport center is the supplied contact."""
        world_x, world_y = project_world(
            position,
            elevation_steps=elevation_steps,
            quadrant=self.quadrant,
        )
        return Camera(
            quadrant=self.quadrant,
            zoom=self.zoom,
            pan=(
                self.viewport[0] / 2 - world_x * self.zoom,
                self.viewport[1] / 2 - world_y * self.zoom,
            ),
            viewport=self.viewport,
        )

    def with_zoom_at(
        self,
        zoom: float,
        screen_anchor: tuple[float, float],
    ) -> "Camera":
        """Change finite zoom while preserving the map pixel under the cursor."""
        world_x = (screen_anchor[0] - self.pan[0]) / self.zoom
        world_y = (screen_anchor[1] - self.pan[1]) / self.zoom
        return Camera(
            quadrant=self.quadrant,
            zoom=zoom,
            pan=(
                screen_anchor[0] - world_x * zoom,
                screen_anchor[1] - world_y * zoom,
            ),
            viewport=self.viewport,
        )

    def with_screen_pan(self, delta: tuple[float, float]) -> "Camera":
        """Translate projected content by one screen-space delta."""
        return Camera(
            quadrant=self.quadrant,
            zoom=self.zoom,
            pan=(self.pan[0] + delta[0], self.pan[1] + delta[1]),
            viewport=self.viewport,
        )

    def quarter_turned(self, step: int) -> "Camera":
        """Quarter-turn while preserving the engine plane at screen center."""
        center = self.viewport[0] / 2, self.viewport[1] / 2
        focus = inverse_plane(center, self)
        return Camera(
            quadrant=(self.quadrant + step) % 4,
            zoom=self.zoom,
            viewport=self.viewport,
        ).with_focus(focus)


def rotate_position(
    position: tuple[float, float],
    quadrant: int,
) -> tuple[float, float]:
    """Rotate an engine coordinate around the fixed 64-by-64 map center."""
    if not 0 <= quadrant < len(_ROTATION_COEFFICIENTS):
        raise ValueError("quadrant must be 0 through 3")
    x = position[0] - MAP_CENTER[0]
    y = position[1] - MAP_CENTER[1]
    xx, xy, yx, yy = _ROTATION_COEFFICIENTS[quadrant]
    return (
        xx * x + xy * y + MAP_CENTER[0],
        yx * x + yy * y + MAP_CENTER[1],
    )


def inverse_rotate_position(
    position: tuple[float, float],
    quadrant: int,
) -> tuple[float, float]:
    """Undo one camera-quarter rotation around the map center."""
    return rotate_position(position, (-quadrant) % 4)


def project_world(
    position: tuple[float, float],
    *,
    elevation_steps: int = 0,
    quadrant: int = 0,
) -> tuple[float, float]:
    """Project one engine support contact into unscaled map pixels."""
    if not 0 <= quadrant < len(_ROTATION_COEFFICIENTS):
        raise ValueError("quadrant must be 0 through 3")
    x = position[0] - MAP_CENTER[0]
    y = position[1] - MAP_CENTER[1]
    xx, xy, yx, yy = _ROTATION_COEFFICIENTS[quadrant]
    camera_x = xx * x + xy * y + MAP_CENTER[0]
    camera_y = yx * x + yy * y + MAP_CENTER[1]
    return (
        (camera_x - camera_y) * (TILE_WIDTH / 2),
        (camera_x + camera_y) * (TILE_HEIGHT / 2)
        - elevation_steps * HEIGHT_STEP_PIXELS,
    )


def project_screen(
    position: tuple[float, float],
    camera: Camera,
    *,
    elevation_steps: int = 0,
) -> tuple[float, float]:
    """Project one engine support contact into framebuffer pixels."""
    world_x, world_y = project_world(
        position,
        elevation_steps=elevation_steps,
        quadrant=camera.quadrant,
    )
    return (
        world_x * camera.zoom + camera.pan[0],
        world_y * camera.zoom + camera.pan[1],
    )


def inverse_plane(
    screen: tuple[float, float],
    camera: Camera,
    *,
    elevation_steps: int = 0,
) -> tuple[float, float]:
    """Invert a screen point onto one candidate support-elevation plane."""
    world_x = (screen[0] - camera.pan[0]) / camera.zoom
    world_y = (
        (screen[1] - camera.pan[1]) / camera.zoom
        + elevation_steps * HEIGHT_STEP_PIXELS
    )
    camera_x = world_x / TILE_WIDTH + world_y / TILE_HEIGHT
    camera_y = world_y / TILE_HEIGHT - world_x / TILE_WIDTH
    return inverse_rotate_position((camera_x, camera_y), camera.quadrant)


def contains_support_diamond(
    screen: tuple[float, float],
    contact: tuple[float, float],
    zoom: float,
) -> bool:
    """Return whether a screen pixel lies in one 128-by-64 support diamond."""
    half_width = TILE_WIDTH * zoom / 2
    half_height = TILE_HEIGHT * zoom / 2
    if half_width <= 0 or half_height <= 0:
        return False
    return (
        abs(screen[0] - contact[0]) / half_width
        + abs(screen[1] - contact[1]) / half_height
        <= 1.0
    )


COMPOSITION_PHASES = {
    "water": 10,
    "terrain": 40,
    "terrain_bed": 40,
    "cliff": 20,
    "stairs": 60,
    "frame": 100,
    "wall": 100,
    "object": 100,
    "torch_body": 100,
    "leaf": 110,
    "torch_flame": 120,
}

POSE_RANKS = {pose: rank for rank, pose in enumerate(("e", "s", "w", "n"))}


def painter_key(
    position: tuple[int, int],
    *,
    elevation_steps: int,
    quadrant: int,
    role: str,
    identity: UUID | str | tuple[str, ...],
    direction: str | None = None,
) -> tuple[int, float, float, int, tuple[str, ...]]:
    """Return the deterministic semantic painter key for one draw candidate."""
    projected = project_world(
        position,
        elevation_steps=0,
        quadrant=quadrant,
    )
    stable_identity = (
        identity
        if type(identity) is tuple
        else (str(identity),)
    )
    direction_rank = POSE_RANKS[direction] if direction is not None else len(POSE_RANKS)
    # Low ground is the planar background. Raised surfaces participate in
    # physical depth with cliffs and objects; role orders only local overlap.
    plane = (10 if role == "water" else 40 if role == "terrain_bed"
             or (role == "terrain" and elevation_steps == 0) else 100)
    return (
        plane,
        projected[1],
        projected[0],
        COMPOSITION_PHASES[role] * 5 + direction_rank,
        stable_identity,
    )


@dataclass(frozen=True, slots=True)
class PickCandidate:
    """Disclosed engine support considered by height-aware picking."""

    position: tuple[int, int]
    elevation_steps: int
    tile_uuid: UUID


class PickableSupport(Protocol):
    """Detached support fields consumed by the pure picking calculation."""

    position: tuple[int, int]
    elevation_steps: int
    tile_uuid: UUID


PickableSupportT = TypeVar("PickableSupportT", bound=PickableSupport)


def pick_support(
    screen: tuple[float, float],
    camera: Camera,
    candidates: Iterable[PickableSupportT],
) -> tuple[PickableSupportT | None, tuple[int, ...]]:
    """Pick the foremost disclosed support without querying engine state."""
    support_coordinates: dict[int, tuple[int, int]] = {}
    matches: list[PickableSupportT] = []
    for candidate in candidates:
        coordinate = support_coordinates.get(candidate.elevation_steps)
        if coordinate is None:
            estimate = inverse_plane(
                screen,
                camera,
                elevation_steps=candidate.elevation_steps,
            )
            coordinate = round(estimate[0]), round(estimate[1])
            support_coordinates[candidate.elevation_steps] = coordinate
        if coordinate != candidate.position:
            continue
        contact = project_screen(
            candidate.position,
            camera,
            elevation_steps=candidate.elevation_steps,
        )
        if contains_support_diamond(screen, contact, camera.zoom):
            matches.append(candidate)
    if not matches:
        return None, tuple(sorted(support_coordinates))
    matches.sort(key=lambda candidate: (
        project_world(candidate.position, quadrant=camera.quadrant)[1],
        project_world(candidate.position, quadrant=camera.quadrant)[0],
        str(candidate.tile_uuid),
    ))
    return matches[-1], tuple(sorted(support_coordinates))


def camera_pose(boundary: str, quadrant: int) -> str:
    """Map one engine boundary direction to an authored four-view pose."""
    base_pose_index = {
        "north": 2,
        "east": 1,
        "south": 0,
        "west": 3,
    }
    try:
        base_index = base_pose_index[boundary.lower()]
    except KeyError as exc:
        raise ValueError(f"unknown boundary direction {boundary!r}") from exc
    return ("n", "e", "s", "w")[(base_index + quadrant) % 4]


def camera_axis_vectors(
    quadrant: int,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return projected screen deltas for one map-N and map-E step."""
    origin = project_world(MAP_CENTER, quadrant=quadrant)
    north = project_world(
        (MAP_CENTER[0], MAP_CENTER[1] + 1),
        quadrant=quadrant,
    )
    east = project_world(
        (MAP_CENTER[0] + 1, MAP_CENTER[1]),
        quadrant=quadrant,
    )
    return (
        (north[0] - origin[0], north[1] - origin[1]),
        (east[0] - origin[0], east[1] - origin[1]),
    )


__all__ = [
    "Camera",
    "HEIGHT_STEP_PIXELS",
    "MAP_CENTER",
    "PickCandidate",
    "TILE_HEIGHT",
    "TILE_WIDTH",
    "ZOOM_LEVELS",
    "camera_axis_vectors",
    "camera_pose",
    "contains_support_diamond",
    "inverse_plane",
    "inverse_rotate_position",
    "painter_key",
    "pick_support",
    "project_screen",
    "project_world",
    "rotate_position",
]
