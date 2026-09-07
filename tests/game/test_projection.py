"""Pure camera, isometric projection, painter, and support-picking proofs."""

from uuid import uuid4

import pytest

from game.projection import (
    Camera,
    HEIGHT_STEP_PIXELS,
    MAP_CENTER,
    PickCandidate,
    TILE_HEIGHT,
    TILE_WIDTH,
    ZOOM_LEVELS,
    camera_axis_vectors,
    camera_pose,
    inverse_plane,
    painter_key,
    pick_support,
    project_screen,
    project_world,
    rotate_position,
)


def _prior_rotate_position(
    position: tuple[float, float],
    quadrant: int,
) -> tuple[float, float]:
    x = position[0] - MAP_CENTER[0]
    y = position[1] - MAP_CENTER[1]
    if quadrant == 0:
        rotated = x, y
    elif quadrant == 1:
        rotated = -y, x
    elif quadrant == 2:
        rotated = -x, -y
    elif quadrant == 3:
        rotated = y, -x
    else:
        raise ValueError("quadrant must be 0 through 3")
    return rotated[0] + MAP_CENTER[0], rotated[1] + MAP_CENTER[1]


def test_shared_rotation_coefficients_equal_prior_formulas_over_full_map() -> None:
    for quadrant in range(4):
        for x in range(64):
            for y in range(64):
                position = x, y
                prior_x, prior_y = _prior_rotate_position(position, quadrant)
                assert rotate_position(position, quadrant) == (prior_x, prior_y)
                for elevation_steps in (0, 1, 3):
                    assert project_world(
                        position,
                        elevation_steps=elevation_steps,
                        quadrant=quadrant,
                    ) == (
                        (prior_x - prior_y) * (TILE_WIDTH / 2),
                        (prior_x + prior_y) * (TILE_HEIGHT / 2)
                        - elevation_steps * HEIGHT_STEP_PIXELS,
                    )


def test_pick_consumes_every_candidate_and_reports_each_height_once() -> None:
    camera = Camera(zoom=0.5).with_focus((20, 20))
    rows = tuple(
        PickCandidate((index, 20), index % 3, uuid4())
        for index in range(64)
    )
    consumed = 0

    def candidates():
        nonlocal consumed
        for row in rows:
            consumed += 1
            yield row

    _, tested = pick_support((-1000, -1000), camera, candidates())

    assert consumed == len(rows)
    assert tested == (0, 1, 2)


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("elevation", (0, 1, 3))
def test_projection_round_trips_all_views_and_heights(quadrant: int, elevation: int) -> None:
    camera = Camera(quadrant=quadrant, zoom=0.75, pan=(233.0, -71.0))
    position = (17, 42)
    screen = project_screen(position, camera, elevation_steps=elevation)
    recovered = inverse_plane(screen, camera, elevation_steps=elevation)
    assert recovered == pytest.approx(position)


def test_height_aware_pick_uses_disclosed_candidates_only() -> None:
    camera = Camera(zoom=0.5).with_focus((20, 20), elevation_steps=2)
    elevated = PickCandidate((20, 20), 2, uuid4())
    ground = PickCandidate((21, 21), 0, uuid4())
    screen = project_screen(elevated.position, camera, elevation_steps=2)
    chosen, tested = pick_support(screen, camera, (ground, elevated))
    assert chosen == elevated
    assert tested == (0, 2)


def test_height_aware_pick_breaks_a_true_multi_height_screen_overlap_by_ground_depth() -> None:
    camera = Camera(zoom=0.5).with_focus((20, 20), elevation_steps=1)
    elevated = PickCandidate((20, 20), 1, uuid4())
    ground = PickCandidate((19, 19), 0, uuid4())
    cursor = project_screen(elevated.position, camera, elevation_steps=1)

    assert cursor == project_screen(ground.position, camera, elevation_steps=0)
    chosen, tested = pick_support(cursor, camera, (elevated, ground))

    assert chosen == elevated
    assert tested == (0, 1)


def test_camera_pose_uses_explicit_four_view_family() -> None:
    assert {
        direction: tuple(camera_pose(direction, quadrant) for quadrant in range(4))
        for direction in ("north", "east", "south", "west")
    } == {
        "north": ("s", "w", "n", "e"),
        "east": ("e", "s", "w", "n"),
        "south": ("n", "e", "s", "w"),
        "west": ("w", "n", "e", "s"),
    }


def test_compass_axes_come_from_the_same_projection_in_all_cameras() -> None:
    assert tuple(camera_axis_vectors(quadrant) for quadrant in range(4)) == (
        ((-64.0, 32.0), (64.0, 32.0)),
        ((-64.0, -32.0), (-64.0, 32.0)),
        ((64.0, -32.0), (-64.0, -32.0)),
        ((64.0, 32.0), (64.0, -32.0)),
    )


@pytest.mark.parametrize("quadrant", range(4))
def test_zoom_and_quarter_turn_preserve_their_screen_anchors(quadrant: int) -> None:
    camera = Camera(
        quadrant=quadrant,
        zoom=0.5,
        pan=(173.0, -91.0),
        viewport=(960, 540),
    )
    anchor = (401.5, 219.25)
    before = (
        (anchor[0] - camera.pan[0]) / camera.zoom,
        (anchor[1] - camera.pan[1]) / camera.zoom,
    )
    zoomed = camera.with_zoom_at(1.0, anchor)
    after = (
        (anchor[0] - zoomed.pan[0]) / zoomed.zoom,
        (anchor[1] - zoomed.pan[1]) / zoomed.zoom,
    )
    assert after == pytest.approx(before)

    center = camera.viewport[0] / 2, camera.viewport[1] / 2
    focus = inverse_plane(center, camera)
    turned = camera.quarter_turned(1)
    assert inverse_plane(center, turned) == pytest.approx(focus)


@pytest.mark.parametrize("quadrant", range(4))
def test_screen_pan_and_rotation_keep_one_explicit_camera_authority(
    quadrant: int,
) -> None:
    camera = Camera(
        quadrant=quadrant,
        zoom=0.5,
        pan=(123.456, -789.123),
        viewport=(960, 540),
    )
    position = (27.25, 36.75)
    before = project_screen(position, camera)
    panned = camera.with_screen_pan((37.0, -19.0))
    after = project_screen(position, panned)
    assert (after[0] - before[0], after[1] - before[1]) == pytest.approx((37.0, -19.0))

    center = camera.viewport[0] / 2, camera.viewport[1] / 2
    panned_anchor = inverse_plane(center, panned)
    turned = panned.quarter_turned(1)
    assert inverse_plane(center, turned) == pytest.approx(panned_anchor, abs=1e-9)

    cycled = camera
    for _ in range(4):
        cycled = cycled.quarter_turned(1)
    assert cycled.quadrant == camera.quadrant
    assert cycled.zoom == camera.zoom
    assert cycled.viewport == camera.viewport
    assert cycled.pan == pytest.approx(camera.pan, abs=1e-9)


@pytest.mark.parametrize("quadrant", range(4))
def test_wasd_screen_displacements_remain_inverse_after_a_turn(quadrant: int) -> None:
    camera = Camera(
        quadrant=quadrant,
        zoom=0.5,
        pan=(123.0, -87.0),
        viewport=(960, 540),
    ).quarter_turned(1)
    position = (26.25, 39.75)
    before = project_screen(position, camera)
    speed = 240.0
    elapsed = 0.125
    step = speed * elapsed
    displacements = {
        "w": (0.0, step),
        "s": (0.0, -step),
        "a": (step, 0.0),
        "d": (-step, 0.0),
    }
    observed = {}
    for key, delta in displacements.items():
        after = project_screen(position, camera.with_screen_pan(delta))
        observed[key] = after[0] - before[0], after[1] - before[1]

    assert observed["w"] == pytest.approx((0.0, step))
    assert observed["s"] == pytest.approx((0.0, -step))
    assert observed["a"] == pytest.approx((step, 0.0))
    assert observed["d"] == pytest.approx((-step, 0.0))
    assert tuple(sum(parts) for parts in zip(observed["w"], observed["s"])) == pytest.approx((0.0, 0.0))
    assert tuple(sum(parts) for parts in zip(observed["a"], observed["d"])) == pytest.approx((0.0, 0.0))


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize(
    ("before_zoom", "after_zoom"),
    tuple(zip(ZOOM_LEVELS[:-1], ZOOM_LEVELS[1:], strict=True)),
)
def test_every_adjacent_zoom_preserves_the_mouse_anchor(
    quadrant: int,
    before_zoom: float,
    after_zoom: float,
) -> None:
    camera = Camera(
        quadrant=quadrant,
        zoom=before_zoom,
        pan=(173.0, -91.0),
        viewport=(960, 540),
    )
    mouse = (401.5, 219.25)
    before = inverse_plane(mouse, camera)
    after = inverse_plane(mouse, camera.with_zoom_at(after_zoom, mouse))
    assert after == pytest.approx(before, abs=1e-9)


@pytest.mark.parametrize("quadrant", range(4))
def test_overview_zoom_fits_the_complete_unlifted_map(quadrant: int) -> None:
    zoom = 0.15
    contacts = [
        project_world(position, quadrant=quadrant)
        for position in ((0, 0), (0, 63), (63, 0), (63, 63))
    ]
    width = (max(row[0] for row in contacts) - min(row[0] for row in contacts) + TILE_WIDTH) * zoom
    height = (max(row[1] for row in contacts) - min(row[1] for row in contacts) + TILE_HEIGHT) * zoom
    camera = Camera(quadrant=quadrant, zoom=zoom).with_focus(MAP_CENTER)

    assert width == pytest.approx(1228.8)
    assert height == pytest.approx(614.4)
    assert width <= camera.viewport[0]
    assert height <= camera.viewport[1]


def test_painter_key_is_stable_and_role_ordered() -> None:
    identity = uuid4()
    water = painter_key((31, 33), elevation_steps=0, quadrant=0, role="water", identity=identity)
    wall = painter_key((31, 33), elevation_steps=0, quadrant=0, role="wall", identity=identity)
    flame = painter_key((31, 33), elevation_steps=0, quadrant=0, role="torch_flame", identity=identity)
    assert water < wall < flame


def test_painter_depth_ignores_visual_lift_and_identity_is_always_comparable() -> None:
    identity = uuid4()
    ground = painter_key(
        (31, 33),
        elevation_steps=0,
        quadrant=0,
        role="wall",
        identity=identity,
        direction="e",
    )
    elevated = painter_key(
        (31, 33),
        elevation_steps=3,
        quadrant=0,
        role="wall",
        identity=identity,
        direction="e",
    )
    corner = painter_key(
        (31, 33),
        elevation_steps=0,
        quadrant=0,
        role="wall",
        identity=(str(uuid4()), str(uuid4())),
        direction="s",
    )

    assert ground == elevated
    assert sorted((corner, ground)) == [ground, corner]
