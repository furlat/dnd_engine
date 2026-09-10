"""Native recovery histories stay coherent across every rendered root boundary.

The engine produces and closes a real encounter first. Playback then uses only
retained facts, imported authoring and the same frame compositor as the game.
"""

import json
from pathlib import Path
from uuid import UUID

import pygame
import pytest

from devtools.animation_review import __main__ as review
from game.animation import sample_idle_body
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands
from game.animation_types import AnimationData, Facing8
from game.choreography import bind_choreography
from game.choreography_draw import load_choreography_media
from game.combat import actor_contact
from game.motion import bind_motion, sample_motion
from game.playback_frame import PlaybackFrame, sample_playback_frame
from game.presentation import reduce_lineage
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from game.visual_position import VisualPosition
from tests.game.scenarios import paralysis_lifecycle


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data()


def body_pixels(frame: PlaybackFrame, identity: str) -> tuple[tuple[int, int], bytes]:
    command, = (row for row in frame.commands if row[4][0] == identity and row[4][6] == "actor")
    return command[2], pygame.image.tobytes(command[1], "RGBA")


@pytest.mark.parametrize(("behavior", "seeds", "resume"), [
    ("action.move", (0,), True),
    ("action.jump", (0,), True),
    ("action.move", (1,), False),
    ("action.move", (1, 0), True),
])
def test_actual_condition_recovery_preserves_pose_through_turns_and_next_motion(
    data: AnimationData, behavior: str, seeds: tuple[int, ...], resume: bool,
) -> None:
    before, lineages = paralysis_lifecycle(repeat_save_seeds=seeds, movement_behavior=behavior, resume=resume)
    latest = before
    for lineage in lineages:
        latest = reduce_lineage(latest, lineage)
    initial = bind_motion(before, lineages[0], data)
    assert initial is not None
    held = sample_motion(initial, data, initial.reactions[0].end_ms - .001).contact
    identity, mover = held.actor_uuid, UUID(held.actor_uuid)
    # The exact native wrapper and child identities, after the initial root.
    owned = {fact.condition_uuid for fact in reduce_lineage(before, lineages[0]).actors[mover].conditions}
    assert len(owned) == 2
    pygame.init()
    try:
        pygame.display.set_mode((960, 640))
        cameras = tuple(Camera(quadrant=q, viewport=(960, 640)).with_focus((3, 3)) for q in range(4))
        media = load_scene_media(scene_actors(before, data, {}), data)
        number_font, badge_font = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                                   for style in (data.number_style, data.badge_style))
        positions: dict[str, VisualPosition] = {}
        facings: dict[str, Facing8] = {}
        removed = resumed = False
        for index, lineage in enumerate(lineages):
            after = reduce_lineage(before, lineage)
            contacts = {actor.contact.actor_uuid: actor.contact for actor in scene_actors(before, data, facings, positions)}
            motion = bind_motion(before, lineage, data, contacts=contacts)
            group = None if motion is not None else bind_choreography(before, lineage, data,
                                                                     facings=facings, contacts=contacts)
            group_media = load_choreography_media(group) if group is not None else None
            reactions = {row.choreography.root_uuid: load_choreography_media(row.choreography)
                         for row in motion.reactions} if motion is not None else {}
            duration = motion.complete_ms if motion is not None else group.complete_ms if group else 0
            # Same absolute idle time isolates geometry/color from Idle's phase.
            clock = 5000.0
            final_frames = []
            for camera in cameras:
                idle_before = sample_playback_frame(before, None, data, 0, clock, camera, facings,
                    media, number_font, badge_font, positions=positions)
                entry = sample_playback_frame(before, after, data, 0, clock, camera, facings,
                    media, number_font, badge_font, positions=positions, motion=motion,
                    reaction_media=reactions, choreography=group, choreography_media=group_media)
                final = sample_playback_frame(before, after, data, duration, clock, camera, facings,
                    media, number_font, badge_font, positions=positions, motion=motion,
                    reaction_media=reactions, choreography=group, choreography_media=group_media)
                final_frames.append(final)
                assert final.displayed == after
                if index > 0 and not resumed:
                    contact = next(actor.contact for actor in entry.actors if actor.contact.actor_uuid == identity)
                    assert (contact.grid, contact.elevation_steps, contact.body_lift_px) == (
                        held.grid, held.elevation_steps, held.body_lift_px)
                    assert body_pixels(idle_before, identity)[0] == body_pixels(entry, identity)[0]
                if index > 0 and motion is None and not resumed:
                    assert body_pixels(idle_before, identity)[0] == body_pixels(final, identity)[0]
                    prior_members = {fact.condition_uuid for fact in before.actors[mover].conditions}
                    next_members = {fact.condition_uuid for fact in after.actors[mover].conditions}
                    if owned <= prior_members and prior_members == next_members:
                        assert body_pixels(idle_before, identity) == body_pixels(final, identity)
                    if owned <= prior_members and not owned & next_members:
                        # Removing real paralysis restores body color at entry;
                        # the neutral-alpha recipe introduces no extra wait.
                        assert duration == 0
                        assert body_pixels(idle_before, identity)[1] != body_pixels(final, identity)[1]
                        actor = next(actor for actor in final.actors if actor.contact.actor_uuid == identity)
                        neutral, = (command for command in actor_draw_commands(data,
                            sample_idle_body(data, actor.contact, clock), actor.contact, actor.layers, media, camera)
                            if command[4][6] == "actor")
                        assert body_pixels(final, identity) == (neutral[2], pygame.image.tobytes(neutral[1], "RGBA"))
                        removed = True
            positions, facings = dict(final_frames[0].positions), dict(final_frames[0].facings)
            if index > 0 and motion is not None:
                resumed = True
                assert removed
                legal_motion = bind_motion(before, lineage, data)
                assert legal_motion is not None and motion.complete_ms == legal_motion.complete_ms
                final_contact = next(actor.contact for actor in final_frames[0].actors if actor.contact.actor_uuid == identity)
                legal = actor_contact(after, after.actors[mover], data)
                assert final_contact.grid == legal.grid == (2, 3)
                assert final_contact.body_lift_px == 0 and identity not in positions
            before = after
        assert before == latest
        assert removed is resume and resumed is resume
        if not resume:
            assert owned <= {fact.condition_uuid for fact in latest.actors[mover].conditions}
            assert positions[identity].grid == held.grid
    finally:
        pygame.quit()


def test_paused_lifecycle_clip_keeps_applied_membership_while_latest_has_recovered(tmp_path: Path) -> None:
    assert review.main(["--case", "recovery-paused", "--fps", "12", "--width", "640", "--height", "480",
                        "--output", str(tmp_path)]) == 0
    run = tmp_path / "runs" / json.loads((tmp_path / "latest.json").read_text())["run"]
    trace = json.loads((run / "cases/recovery-paused/trace.json").read_text())
    first = trace["lineages"][0]
    mover = first["root"]["source_entity_uuid"]
    applied = trace["heads"][0]["after"]["actors"][mover]["conditions"]
    owned = {fact["uuid"] for fact in applied}
    assert len(owned) == 2
    assert not owned & {fact["uuid"] for fact in trace["latest"]["actors"][mover]["conditions"]}
    paused = [frame for frame in trace["frames"] if frame["paused"]]
    assert len(paused) > 1
    for frame in paused:
        assert frame["root_uuid"] == first["root"]["uuid"]
        assert owned <= {fact["uuid"] for fact in frame["state"]["actors"][mover]["conditions"]}
        assert frame["views"] == paused[0]["views"]
        assert frame["pixel_sha256"] == paused[0]["pixel_sha256"]
        assert frame["latest_cursor"] > frame["state"]["cursor"]
        assert [view["quadrant"] for view in frame["views"]] == [0, 1, 2, 3]
    end = next(contact for contact in trace["frames"][-1]["contacts"] if contact["actor_uuid"] == mover)
    assert end["grid"] == [2, 3] and end["body_lift_px"] == 0
