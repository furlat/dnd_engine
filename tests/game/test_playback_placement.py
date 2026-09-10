"""A stopped actor keeps its visible pose when the historical head is released.

Real native walk/jump with a save-based sword rider in; sampled scene commands
and unchanged reduced state out. Test the head boundary that gallery review
exposed, including all four cameras and a living paralyzed target.
"""

from dataclasses import replace

import pygame
import pytest

from game.animation import ActorContact
from game.animation_data import load_animation_data
from game.animation_types import AnimationData
from game.choreography_draw import load_choreography_media
from game.combat import actor_contact
from game.motion import bind_motion, sample_motion
from game.playback_frame import sample_playback_frame
from game.presentation import reduce_lineage
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from game.visual_position import VisualPosition, placed_contact
from tests.game.scenarios import movement_with_paralysis


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data()


@pytest.mark.parametrize("behavior", ["action.move", "action.jump"])
@pytest.mark.parametrize(("seed", "maximum_hp"), [(0, 80), (5, 4)])
def test_interrupted_pose_survives_completion_and_idle_in_every_camera(
    data: AnimationData, behavior: str, seed: int, maximum_hp: int,
) -> None:
    before, lineage = movement_with_paralysis(seed, maximum_hp, movement_behavior=behavior)
    after = reduce_lineage(before, lineage)
    motion = bind_motion(before, lineage, data)
    assert motion is not None
    reaction, = motion.reactions
    held = sample_motion(motion, data, reaction.end_ms - .001)
    identity = motion.actor.actor_uuid
    pygame.init()
    try:
        pygame.display.set_mode((960, 640))
        actors = scene_actors(before, data, {})
        media = load_scene_media(actors, data)
        reactions = {reaction.choreography.root_uuid: load_choreography_media(reaction.choreography)}
        font, badge = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                       for style in (data.number_style, data.badge_style))
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=(960, 640)).with_focus((3, 3))
            completed = sample_playback_frame(before, after, data, motion.complete_ms, 3000,
                camera, {}, media, font, badge, motion=motion, reaction_media=reactions)
            idle = sample_playback_frame(after, None, data, 0, 3000,
                camera, completed.facings, media, font, badge, positions=completed.positions)
            later = sample_playback_frame(after, None, data, 0, 4000,
                camera, idle.facings, media, font, badge, positions=idle.positions)
            for frame in (completed, idle, later):
                contact = next(actor.contact for actor in frame.actors if actor.contact.actor_uuid == identity)
                assert contact.grid == held.contact.grid != motion.actor.grid
                assert contact.elevation_steps == held.contact.elevation_steps
                assert contact.body_lift_px == held.lift_px
                assert contact.hp == after.actors[lineage.root.source_entity_uuid].normal_hp
                assert frame.displayed == after
            # Same global time at head release: neither position nor idle/Die
            # frame, body pixels, support shadow or painter depth changes.
            idle_commands = {(command[4][0], command[4][6]): command for command in idle.commands}
            for command in completed.commands:
                if command[4][0] != identity:
                    continue
                next_command = idle_commands[command[4][0], command[4][6]]
                assert command[0] == next_command[0]
                assert command[2:] == next_command[2:]
                assert pygame.image.tobytes(command[1], "RGBA") == pygame.image.tobytes(next_command[1], "RGBA")
        legal = actor_contact(after, after.actors[lineage.root.source_entity_uuid], data)
        assert legal.grid == (3, 3) and legal.body_lift_px == 0
        assert reduce_lineage(before, lineage) == after
    finally:
        pygame.quit()


def test_visual_placement_keeps_fresh_facts_and_yields_to_a_real_relocation() -> None:
    original = ActorContact("actor", (3, 3), "S", 1, hp=80)
    position = VisualPosition(original.grid, (2.664, 3), 0, 19)
    changed = replace(original, hp=73, facing="NW")
    visible = placed_contact(changed, position)
    assert (visible.hp, visible.facing) == (73, "NW")
    assert (visible.grid, visible.body_lift_px) == ((2.664, 3), 19)
    relocated = replace(changed, grid=(2, 3), elevation_steps=1)
    assert placed_contact(relocated, position) == relocated


@pytest.mark.parametrize("behavior", ["action.move", "action.jump"])
def test_committed_movement_starts_from_its_existing_visual_pose(data: AnimationData, behavior: str) -> None:
    before, lineage = movement_with_paralysis(17, movement_behavior=behavior)
    original = actor_contact(before, before.actors[lineage.root.source_entity_uuid], data)
    prior_pose = placed_contact(original, VisualPosition(original.grid, (2.664, 3), 0, 19))
    normal = bind_motion(before, lineage, data)
    moving = bind_motion(before, lineage, data, contacts={prior_pose.actor_uuid: prior_pose})
    assert normal is not None and moving is not None
    start = sample_motion(moving, data, 0)
    assert start.contact.grid == prior_pose.grid and start.lift_px == prior_pose.body_lift_px
    # The actual Step and source contexts still own duration and destination.
    assert moving.complete_ms == normal.complete_ms
    final = sample_motion(moving, data, moving.complete_ms)
    assert final.contact.grid == (2, 3) and final.contact.body_lift_px == final.lift_px == 0
