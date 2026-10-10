"""Authored ground fall displacement changes overlap, never placement or altitude."""

from dataclasses import replace
from types import MappingProxyType

import pygame
import pytest

from dnd.core.life_types import LifeState
from game.animation import ActorContact, BodySample
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands, load_actor_media
from game.animation_types import RigLayer
from game.condition_animation import ConditionAppearance
from game.projection import Camera, painter_key


@pytest.fixture(scope="module")
def rendering():
    pygame.init()
    pygame.display.set_mode((1, 1))
    data = load_animation_data()
    yield data
    pygame.quit()


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("life", (LifeState.ALIVE, LifeState.DEAD))
def test_prone_and_dead_overlap_follow_original_ground_fall_without_moving_pixels(rendering, quadrant, life):
    data = rendering
    contact = ActorContact("falling", (8, 6), "S", 1, life_state=life)
    layers = (RigLayer("shadow", "Shadow", alpha=.5), RigLayer("body", "NakedBody"))
    media = load_actor_media(data, ((contact, layers, ("Idle", "Die")),), all_facings=True)
    rig = data.rigs[data.root_rig]
    # Same production art with the depth track absent is the old standing-anchor behavior.
    old_rig = rig.model_copy(update={"pose_sockets": MappingProxyType({
        name: points for name, points in rig.pose_sockets.items() if name != "ground_depth"})})
    old = replace(data, rigs=MappingProxyType({**data.rigs, data.root_rig: old_rig}))
    camera = Camera(quadrant=quadrant).with_focus(contact.grid)
    appearance = ConditionAppearance(body_pose="Die") if life is LifeState.ALIVE else None
    # Include backward seeking and compare fall entry/hold/final-pose sampling.
    for frame in (0, 7, 14, 7, 0):
        pose = BodySample(contact.actor_uuid, "Die", frame, contact.facing)
        actual = actor_draw_commands(data, pose, contact, layers, media, camera, condition=appearance)
        baseline = actor_draw_commands(old, pose, contact, layers, media, camera, condition=appearance)
        for draw, previous in zip(actual, baseline, strict=True):
            assert draw.destination == previous.destination
            assert pygame.image.tobytes(draw.surface, "RGBA") == pygame.image.tobytes(previous.surface, "RGBA")
            assert draw.evidence == previous.evidence
            assert draw.support_height_steps == 0
            assert draw.key[:1] == previous.key[:1] and draw.key[3:] == previous.key[3:]
        if frame == 14:
            # S-facing fall moves up in camera0, down in camera2; source art proves both.
            if quadrant == 0:
                assert actual[-1].key[1] < baseline[-1].key[1] - 30
            elif quadrant == 2:
                assert actual[-1].key[1] > baseline[-1].key[1] + 40
            else:
                assert abs(actual[-1].key[2] - baseline[-1].key[2]) > 35
            # A peer between old and real footprint must sort on the opposite side.
            midpoint = (actual[-1].key[1] + baseline[-1].key[1]) / 2
            peer = (baseline[-1].key[0], midpoint, baseline[-1].key[2], 504, ("peer",))
            assert (actual[-1].key > peer) != (baseline[-1].key > peer)
    idle = BodySample(contact.actor_uuid, "Idle", 0, contact.facing)
    for draw in actor_draw_commands(data, idle, contact, layers, media, camera):
        assert draw.key == painter_key(contact.grid, elevation_steps=0,
            quadrant=quadrant, role=draw.role, identity=contact.actor_uuid)
