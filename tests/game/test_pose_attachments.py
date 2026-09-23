"""Condition attachments follow the visible body pose, not its standing origin."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pygame
import pytest

from game.animation import ActorContact, BodySample, view_facing
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands, load_actor_media
from game.animation_types import RigLayer
from game.asset_types import AssetSpec
from game.condition_animation import ConditionAppearance
from game.condition_media import ConditionLayerMedia, ResolvedConditionLayer
from game.condition_types import ConditionColors, ConditionLayer
from game.projection import Camera, TILE_WIDTH, project_screen


@pytest.fixture(scope="module")
def pose_media():
    pygame.init()
    pygame.display.set_mode((640, 480))
    data = load_animation_data()
    contact = ActorContact("socket-recipient", (3, 5), "SW", 1, elevation_steps=2, visual_scale_x=.9)
    appearance = (RigLayer("body", "NakedBody"), RigLayer("head", "Head22"))
    rows = {}
    load_actor_media(data, ((contact, appearance, ("Idle", "Run", "Die", "Special1")),),
                     body_rows=rows, all_facings=True)
    # A visible calibration dot makes the attachment position observable through
    # ordinary actor drawing without depending on an orbit effect's changing art.
    marker = pygame.Surface((3, 3), pygame.SRCALPHA)
    marker.fill((255, 0, 255, 255))
    asset = AssetSpec("pose-marker", Path("unused.png"), (3, 3), (1.5, 1.5), 1)
    media = ConditionLayerMedia("calibration", "marker", {facing: asset for facing in data.rig.FACING_ROW})
    for facing in data.rig.FACING_ROW:
        rows[("condition", "pose-marker", facing, 0)] = marker
    yield data, contact, appearance, rows, media
    pygame.quit()


@pytest.mark.parametrize("attachment,clip,frames", [
    ("head", "Run", (0, 4, 8, 14)),
    ("head", "Special1", (0, 7, 14)),
    ("face", "Die", (0, 4, 8, 14, 8, 4, 0)),
])
@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("facing", ("S", "SW"))
def test_head_and_sleep_face_follow_current_body_frame(pose_media, attachment, clip, frames, quadrant, facing):
    data, contact, appearance, rows, media = pose_media
    contact = replace(contact, facing=facing)
    rig = data.rigs[data.root_rig]
    camera = Camera(quadrant=quadrant, zoom=.75).with_focus(contact.grid)
    layer = ConditionLayer(id="marker", assetId="pose-marker", category="calibration", animation="marker",
        fps=12, attachment=attachment, activeDuring=("idle",), priority=1,
        colors=ConditionColors(primary=0xFFFFFF, secondary=0xFFFFFF, tertiary=0xFFFFFF))
    condition = ConditionAppearance(layers=(ResolvedConditionLayer(layer, media),))
    observed = []
    for frame in frames:
        body = BodySample(contact.actor_uuid, clip, frame, contact.facing)
        command, = actor_draw_commands(data, body, contact, appearance, rows, camera, condition=condition)
        pixels = pygame.surfarray.array3d(command.surface)
        xs, ys = np.where(np.all(pixels == (255, 0, 255), axis=2))
        assert len(xs), (attachment, clip, frame, quadrant)
        actual = (command.destination[0] + xs.mean() + .5, command.destination[1] + ys.mean() + .5)
        point = rig.pose_sockets[attachment][clip][view_facing(contact.facing, quadrant, data)][frame]
        ground = project_screen(contact.grid, camera, elevation_steps=contact.elevation_steps)
        factor = contact.visual_scale * camera.zoom * TILE_WIDTH / data.rig.TILE_W
        expected = (ground[0] + (point.x - 64) * factor * contact.visual_scale_x,
                    ground[1] + (point.y - 87) * factor)
        assert actual == pytest.approx(expected, abs=1)
        observed.append(actual)
    assert len(set(observed)) > 1  # Neither a standing guess nor a held final face.
    if clip == "Die":
        assert observed[0] == observed[-1] and observed[1] == observed[-2]


def test_unmeasured_clip_omits_socket_instead_of_using_standing_pose(pose_media):
    data, contact, appearance, rows, media = pose_media
    rig = data.rigs[data.root_rig]
    partial = rig.model_copy(update={"pose_sockets": {"head": {"Idle": rig.pose_sockets["head"]["Idle"]}}})
    partial_data = replace(data, rigs={data.root_rig: partial})
    layer = ConditionLayer(id="marker", assetId="pose-marker", category="calibration", animation="marker",
        fps=12, attachment="head", activeDuring=("idle",), priority=1,
        colors=ConditionColors(primary=0xFFFFFF, secondary=0xFFFFFF, tertiary=0xFFFFFF))
    body = BodySample(contact.actor_uuid, "Run", 7, contact.facing)
    bare, = actor_draw_commands(partial_data, body, contact, appearance, rows, Camera())
    adorned, = actor_draw_commands(partial_data, body, contact, appearance, rows, Camera(),
                                  condition=ConditionAppearance(layers=(ResolvedConditionLayer(layer, media),)))
    assert adorned.destination == bare.destination
    assert pygame.image.tobytes(adorned.surface, "RGBA") == pygame.image.tobytes(bare.surface, "RGBA")
