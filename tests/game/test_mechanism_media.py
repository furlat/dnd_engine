"""Authored workshop poses play finite pulses and distinct plate release motion."""

from uuid import UUID
from math import cos, sin

import pygame
import pytest

from game.animation import ActorContact
from game.animation_data import load_animation_data
from game.assets import SurfaceCache, load_catalog, prop_animation_frame
from game.mechanism_projectile import (MechanismProjectileCue, mechanism_projectile_duration,
    mechanism_projectile_draw_command, mechanism_projectile_target, sample_mechanism_projectile)
from game.projection import Camera, project_screen
from game.world_animation import WorldTransition, WorldTransitionSample


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture(scope="module")
def animation_data():
    return load_animation_data()


@pytest.fixture(scope="module")
def surfaces(catalog):
    pygame.init()
    pygame.display.set_mode((640, 480))
    yield SurfaceCache(catalog)
    pygame.quit()


@pytest.mark.parametrize("pose", ("e", "s", "w", "n"))
def test_plate_press_and_release_follow_their_authored_motion(catalog, pose):
    animation = catalog.spatial_effects["spatial_effect.environment.pressure_plate"]
    press = WorldTransition(UUID(int=1), "pressed", "false", "true", 0)
    release = WorldTransition(UUID(int=1), "pressed", "true", "false", 500)

    def picture(change, elapsed):
        return prop_animation_frame(animation, pose, change.current,
                                    WorldTransitionSample(change, elapsed))[1]

    assert picture(press, 0) == 0
    assert picture(press, 250) == 3
    assert picture(press, 500) == 5
    assert picture(release, 0) == 6
    assert picture(release, 250) == 9
    assert picture(release, 500) == 11
    assert picture(release, 5000) == 11, "Release holds its end instead of looping."
    assert picture(press, 250) == 3, "Seeking backwards must restore the pressed motion."
    assert prop_animation_frame(animation, pose, "false")[1] == 0
    assert prop_animation_frame(animation, pose, "true")[1] == 5


@pytest.mark.parametrize("identity,contact", (("dart_launcher", 3), ("swinging_blade", 5), ("crusher", 5)))
@pytest.mark.parametrize("pose", ("e", "s", "w", "n"))
def test_ready_to_ready_activation_is_visible_and_does_not_replay(catalog, identity, contact, pose):
    animation = catalog.spatial_effects[f"spatial_effect.environment.{identity}"]
    pulse = WorldTransition(UUID(int=1), "activation", None, None, 100)

    def picture(elapsed):
        return prop_animation_frame(animation, pose, "ready", WorldTransitionSample(pulse, elapsed))

    assert animation.contact_frame == contact
    assert picture(0)[1] == 0
    assert picture(contact * 1000 / 12 + .01)[1] == contact
    assert picture(1000)[1] == 11
    assert picture(5000)[1] == 11
    assert picture(contact * 1000 / 12 + .01)[1] == contact
    assert prop_animation_frame(animation, pose, "ready")[1] == 0
    assert picture(0)[0] in catalog.resources
    assert picture(1000)[0] in catalog.resources


def test_existing_spike_state_interpolation_is_preserved(catalog):
    animation = catalog.spatial_effects["spatial_effect.environment.spike_trap"]
    rising = WorldTransition(UUID(int=1), "trap_state", "ready", "activated", 0)
    falling = WorldTransition(UUID(int=1), "trap_state", "activated", "deactivated", 0)
    assert prop_animation_frame(animation, "e", "activated", WorldTransitionSample(rising, 125))[1] == 3
    assert prop_animation_frame(animation, "e", "deactivated", WorldTransitionSample(falling, 125))[1] == 3
    assert prop_animation_frame(animation, "e", "activated", WorldTransitionSample(rising, 1000))[1] == 6
    assert prop_animation_frame(animation, "e", "deactivated", WorldTransitionSample(falling, 1000))[1] == 0


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("direction,column", (((1, 0), 0), ((0, 1), 2), ((-1, 0), 4), ((0, -1), 6)))
def test_dart_keeps_muzzle_body_and_heading_registered(catalog, animation_data, surfaces, quadrant, direction, column):
    art = catalog.spatial_effects["spatial_effect.environment.dart_launcher"].projectile
    assert art is not None
    origin = (8, 8)
    end = (8 + direction[0] * 4, 8 + direction[1] * 4)
    target = ActorContact("target", end, "S", 1.25, elevation_steps=2)
    duration = mechanism_projectile_duration(origin, end, 0, 2, art)
    cue = MechanismProjectileCue(UUID(int=1), UUID(int=2), origin, 0, end, 2,
                                 direction, art, 250, 250 + duration,
                                 mechanism_projectile_target(target, animation_data))
    camera = Camera(quadrant=quadrant, zoom=.5).with_focus(origin)
    released = sample_mechanism_projectile(cue, 250, camera)
    halfway = sample_mechanism_projectile(cue, 250 + duration / 2, camera)
    arrival = sample_mechanism_projectile(cue, cue.arrival_ms - .000001, camera)
    assert released is not None and halfway is not None and arrival is not None
    assert released.asset_id == f"trap-workshop.dart-projectile.{('e', 's', 'w', 'n')[quadrant]}.{column}"
    # The delivered middle barrel is .106066 tiles forward of the fixture pivot.
    assert released.grid == pytest.approx((8 + direction[0]*.106066,
                                          8 + direction[1]*.106066), abs=.00001)
    # The torso is the existing rig attachment, including actual scale/elevation.
    rig = animation_data.rigs[target.rig_id]
    socket = rig.body_anchor
    assert socket is not None
    ground = project_screen(end, camera, elevation_steps=2)
    factor = 128 / animation_data.rig.TILE_W * target.visual_scale * camera.zoom
    torso = (ground[0] + (socket.x - rig.cell_width / 2) * factor,
             ground[1] + (socket.y - rig.cell_height + rig.origin_y_from_ground) * factor)
    assert arrival.anchor == pytest.approx(torso, abs=.001)
    assert halfway.anchor == pytest.approx(tuple((a+b)/2 for a, b in zip(released.anchor, torso)))
    assert project_screen(halfway.grid, camera, elevation_steps=halfway.elevation_steps) == pytest.approx(halfway.anchor)
    vx, vy = art.tip_offsets_by_pose[("e", "s", "w", "n")[quadrant]][column]
    aimed = (vx*cos(halfway.rotation)-vy*sin(halfway.rotation),
             vx*sin(halfway.rotation)+vy*cos(halfway.rotation))
    trajectory = (torso[0]-released.anchor[0], torso[1]-released.anchor[1])
    assert aimed[0]*trajectory[1] - aimed[1]*trajectory[0] == pytest.approx(0, abs=.00001)
    assert aimed[0]*trajectory[0] + aimed[1]*trajectory[1] > 0
    image = surfaces.scaled(halfway.asset_id, camera.zoom)
    command = mechanism_projectile_draw_command(cue, halfway, image, catalog.resources[halfway.asset_id], camera)
    assert command.surface.get_bounding_rect().width > 0
    assert command.evidence[6] == "mechanism_projectile"
    assert sample_mechanism_projectile(cue, 249, camera) is None
    assert sample_mechanism_projectile(cue, cue.arrival_ms, camera) is None
    assert sample_mechanism_projectile(cue, 250, camera) == released


@pytest.mark.parametrize("quadrant", range(4))
def test_hidden_launcher_uses_only_disclosed_lane_and_no_apparatus_socket(catalog, animation_data, quadrant):
    art = catalog.spatial_effects["spatial_effect.environment.dart_launcher"].projectile
    assert art is not None
    cue = MechanismProjectileCue(UUID(int=1), None, (5, 3), 1, (8, 3), 1,
                                 (1, 0), art, 0, 250, muzzle_visible=False)
    camera = Camera(quadrant=quadrant).with_focus((5, 3))
    start = sample_mechanism_projectile(cue, 0, camera)
    assert start is not None
    assert start.anchor == pytest.approx(project_screen((5, 3), camera,
        elevation_steps=1 + art.muzzle_height_steps))
    assert start.grid == pytest.approx((5, 3))


@pytest.mark.parametrize("pose", ("e", "s", "w", "n"))
def test_closed_jaw_holds_until_native_reset_and_uses_authored_opening(catalog, pose):
    animation = catalog.spatial_effects["spatial_effect.environment.jaw_trap"]
    pulse = WorldTransition(UUID(int=1), "activation", None, None, 0)
    assert prop_animation_frame(animation, pose, "activated", WorldTransitionSample(pulse, 0))[1] == 0
    assert prop_animation_frame(animation, pose, "activated", WorldTransitionSample(pulse, 500))[1] == 5
    assert prop_animation_frame(animation, pose, "activated", WorldTransitionSample(pulse, 5000))[1] == 5
    assert prop_animation_frame(animation, pose, "activated")[1] == 5
    for state in ("ready", "deactivated"):
        reset = WorldTransition(UUID(int=1), "trap_state", "activated", state, 0)
        assert prop_animation_frame(animation, pose, state, WorldTransitionSample(reset, 0))[1] == 6
        assert prop_animation_frame(animation, pose, state, WorldTransitionSample(reset, 250))[1] == 9
        assert prop_animation_frame(animation, pose, state, WorldTransitionSample(reset, 5000))[1] == 11


@pytest.mark.parametrize("pose", ("e", "s", "w", "n"))
@pytest.mark.parametrize("identity,state", (("gas_vent", "ready"), ("tripwire", None)))
def test_vent_and_wire_play_once_without_restarting(catalog, identity, state, pose):
    animation = catalog.spatial_effects[f"spatial_effect.environment.{identity}"]
    pulse = WorldTransition(UUID(int=1), "activation", None, None, 0)
    assert prop_animation_frame(animation, pose, state, WorldTransitionSample(pulse, 250))[1] == 3
    assert prop_animation_frame(animation, pose, state, WorldTransitionSample(pulse, 5000))[1] == 11
