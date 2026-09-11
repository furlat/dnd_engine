"""Native life histories use original badges and one body owner while seeking."""

from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
from typing import Iterator

import pygame
import pytest

from dnd.core.events import LifeStateChangeEvent
from dnd.core.life_types import LifeState
from dnd.runtime_reset import reset_engine_runtime
from game.animation import body_clip, sample_cast, sample_idle_body
from game.animation_data import load_animation_data
from game.animation_draw import AnimationDrawCommand, actor_draw_commands
from game.animation_types import AnimationData, Facing8
from game.attack import BoundAttack, bind_attack, sample_attack
from game.choreography import bind_choreography, sample_choreography
from game.choreography_draw import load_choreography_media
from game.combat import actor_contact, bind_cast
from game.combat_demo import iter_combat_demo
from game.feedback import choreography_feedback, motion_feedback, sample_feedback
from game.motion import bind_motion, sample_motion
from game.playback_frame import PlaybackFrame, sample_playback_frame
from game.presentation import CompletedLineage, PresentationTarget, reduce_lineage, IntervalEnvelope, reduce_interval
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from game.visual_position import VisualPosition
from tests.game.scenarios import attack_history, lifecycle_history


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data(rig_files=(Path("game/data/rigs/goblin01.json"),))


@pytest.fixture(scope="module")
def pygame_runtime() -> Iterator[None]:
    pygame.init()
    pygame.display.set_mode((960, 640))
    yield
    pygame.quit()


def actor_body(frame: PlaybackFrame, identity: str) -> AnimationDrawCommand:
    command, = (row for row in frame.commands if row[4][0] == identity and row[4][6] == "actor")
    return command


@pytest.mark.parametrize(("seeds", "heal_after", "labels"), [
    ((0,), False, ("Death save",)),
    ((1,), False, ("Death save failed",)),
    ((31,), False, ("Critical failure",)),
    ((5,), False, ("Critical death save!", "Revived")),
    ((0, 0, 0), True, ("Death save", "Death save", "Death save", "Stable", "Revived")),
])
def test_native_lifecycle_badges_keep_original_text_color_and_decorative_lifetime(
    data: AnimationData, seeds: tuple[int, ...], heal_after: bool, labels: tuple[str, ...],
) -> None:
    source = json.loads(data.context_source_json)["contexts"]["lifecycle"]
    assert data.death_save_context.model_dump(mode="json") == source["deathSave"]
    assert data.life_state_context.model_dump(mode="json") == source["lifeState"]
    authored = {row["text"]: row for category in ("deathSave", "lifeState") for row in source[category].values()}
    assert len(authored) == 7
    captured = lifecycle_history(save_seeds=seeds, heal_after=heal_after)
    before, roots = captured.before, captured.lineages
    seen: list[str] = []
    longer = replace(data, badge_style=data.badge_style.model_copy(update={"durationMs": 2 * data.badge_style.durationMs}))
    for lineage in roots:
        group = bind_choreography(before, lineage, data)
        assert group.gaps == () and group.complete_ms == 0
        assert bind_choreography(before, lineage, longer).complete_ms == 0
        assert not sample_choreography(group, 0).bodies
        tracks = tuple(track for track in choreography_feedback(group, data, 5000) if track.kind == "badge")
        for track in tracks:
            seen.append(track.label)
            assert authored[track.label]["enabled"] and track.color == authored[track.label]["color"]
            assert track.value is None and track.style == data.badge_style
            assert track.start_ms == 5000 and track.duration_ms == data.badge_style.durationMs
            assert sample_feedback(track, 4999) is None
            assert sample_feedback(track, 5000) is not None
            assert sample_feedback(track, 5000 + track.duration_ms - .001) is not None
            assert sample_feedback(track, 5000 + track.duration_ms) is None
        before = reduce_lineage(before, lineage)
    assert Counter(seen) == Counter(labels)


def test_native_death_plays_once_then_corpse_and_revival_preserve_pose_in_four_cameras(
    data: AnimationData, pygame_runtime: None,
) -> None:
    captured = lifecycle_history(save_seeds=(1, 0, 31), revive_after=True)
    before, roots = captured.before, captured.lineages
    target, = (actor.uuid for actor in before.actors.values() if actor.life_state is LifeState.DYING)
    legal = actor_contact(before, before.actors[target], data, "NW")
    identity = legal.actor_uuid
    held = replace(legal, grid=(4.25, 3), body_lift_px=19)
    positions = {identity: VisualPosition(legal.grid, held.grid, held.elevation_steps, held.body_lift_px)}
    facings: dict[str, Facing8] = {identity: "NW"}
    media = load_scene_media(scene_actors(before, data, facings, positions), data)
    number, badge = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                     for style in (data.number_style, data.badge_style))
    cameras = tuple(Camera(quadrant=q, viewport=(960, 640)).with_focus(legal.grid) for q in range(4))
    death_seen = revival_seen = False
    corpse_boundaries = 0
    corpse_pixels: dict[int, tuple[tuple[int, int], bytes]] = {}
    first_death_pixels: dict[int, bytes] = {}
    for lineage in roots:
        after = reduce_lineage(before, lineage)
        contacts = {actor.contact.actor_uuid: actor.contact for actor in scene_actors(before, data, facings, positions)}
        group = bind_choreography(before, lineage, data, facings=facings, contacts=contacts)
        assert group.gaps == ()
        group_media = load_choreography_media(group)
        deaths = tuple(cue for cue in group.lifecycle if isinstance(cue.event, LifeStateChangeEvent)
                       and cue.event.new_state is LifeState.DEAD)
        revival = before.actors[target].life_state is LifeState.DEAD and after.actors[target].life_state is LifeState.ALIVE
        if deaths:
            death, = deaths
            assert not death.state_owned and death.contact.life_state is LifeState.DYING
            assert death.start_ms == 0 and death.death_end_ms == group.complete_ms
            unplaced = bind_choreography(before, lineage, data)
            assert unplaced.gaps == () and unplaced.complete_ms == group.complete_ms
            assert sample_choreography(unplaced, 0).bodies[0].frame == 0
            clip = body_clip(data, held, data.death_context.bodyClip)
            interval = 1000 / (clip.fps * data.death_context.bodyPlaybackSpeed)
            assert group.complete_ms == pytest.approx((clip.frames - 1) * interval)
            samples = tuple(sample_choreography(group, time) for time in (0, interval, group.complete_ms))
            assert [sample.bodies[0].frame for sample in samples] == [0, 1, clip.frames - 1]
            assert all(len(sample.bodies) == 1 and sample.bodies[0].clip == data.death_context.bodyClip
                       for sample in samples)
            # An absolute seek back to entry restarts the same retained body.
            assert sample_choreography(group, 0) == samples[0]
            assert not samples[0].complete and samples[-1].complete
            death_seen = True
        else:
            assert group.complete_ms == 0 and not sample_choreography(group, 0).bodies
        if before.actors[target].life_state is LifeState.DEAD and not revival:
            corpse_boundaries += 1
        for camera in cameras:
            times = (0, group.complete_ms / 2, group.complete_ms) if deaths else (0,)
            for time in times:
                frame = sample_playback_frame(before, after, data, time, 5000 + time, camera, facings,
                    media, number, badge, choreography=group, choreography_media=group_media, positions=positions)
                contact = next(actor.contact for actor in frame.actors if actor.contact.actor_uuid == identity)
                assert (contact.grid, contact.elevation_steps, contact.body_lift_px) == (
                    held.grid, held.elevation_steps, held.body_lift_px)
                assert frame.positions == positions
                command = actor_body(frame, identity)
                if deaths:
                    assert command[4][8] == data.death_context.bodyClip
                    if time == 0:
                        assert command[4][9] == 0
                        first_death_pixels[camera.quadrant] = pygame.image.tobytes(command[1], "RGBA")
                    if time == group.complete_ms:
                        assert command[4][9] == body_clip(data, held, data.death_context.bodyClip).frames - 1
                        assert pygame.image.tobytes(command[1], "RGBA") != first_death_pixels[camera.quadrant]
                if time == group.complete_ms:
                    assert frame.complete and frame.displayed == after
                    assert contact.hp == after.actors[target].normal_hp
                    idle = sample_playback_frame(after, None, data, 0, 5000 + time, camera, facings,
                        media, number, badge, positions=frame.positions)
                    idle_body = actor_body(idle, identity)
                    assert command[2:] == idle_body[2:]
                    assert pygame.image.tobytes(command[1], "RGBA") == pygame.image.tobytes(idle_body[1], "RGBA")
                    if after.actors[target].life_state is LifeState.DEAD:
                        rendered = (command[2], pygame.image.tobytes(command[1], "RGBA"))
                        if camera.quadrant in corpse_pixels:
                            assert rendered == corpse_pixels[camera.quadrant]
                        corpse_pixels[camera.quadrant] = rendered
                    if revival:
                        assert contact.life_state is LifeState.ALIVE and contact.hp == 3
                        assert command[4][8] == "Idle"
                        actor = next(actor for actor in frame.actors if actor.contact.actor_uuid == identity)
                        expected, = (row for row in actor_draw_commands(data,
                            sample_idle_body(data, actor.contact, 5000), actor.contact, actor.layers, media, camera)
                            if row[4][6] == "actor")
                        assert pygame.image.tobytes(command[1], "RGBA") == pygame.image.tobytes(expected[1], "RGBA")
                        revival_seen = True
        before = after
    assert death_seen and revival_seen and corpse_boundaries >= 2
    assert before.actors[target].normal_hp == 3 and before.actors[target].life_state is LifeState.ALIVE


def lethal_cast_history() -> tuple[PresentationTarget, CompletedLineage]:
    script = iter_combat_demo(goblin_recipient=True, second_attack_seed=17)
    try:
        initialization = next(script)
        assert isinstance(initialization, IntervalEnvelope)
        before, _ = reduce_interval(None, initialization)
        first, second = next(script), next(script)
        assert isinstance(before, PresentationTarget)
        assert isinstance(first, CompletedLineage) and isinstance(second, CompletedLineage)
        return reduce_lineage(before, first), second
    finally:
        script.close()
        reset_engine_runtime()


@pytest.mark.parametrize("family", ("attack", "cast"))
def test_owned_lethal_delivery_keeps_its_original_timing_and_exactly_one_body(
    data: AnimationData, pygame_runtime: None, family: str,
) -> None:
    if family == "attack":
        captured = attack_history("weapon.longsword", 17, opportunity=True, maximum_hp=4)
        before, lineage = captured.before, captured.lineages[0]
        bound = bind_attack(before, lineage, data)
        assert bound is not None
    else:
        before, lineage = lethal_cast_history()
        bound = bind_cast(before, lineage, data)
    group = bind_choreography(before, lineage, data)
    assert len(group.nodes) == 1 and group.nodes[0].bound.timeline == bound.timeline
    assert group.complete_ms == bound.timeline.complete_ms
    death, = (cue for cue in group.lifecycle if isinstance(cue.event, LifeStateChangeEvent)
              and cue.event.new_state is LifeState.DEAD)
    assert death.state_owned and death.death_end_ms is None
    assert death.event.uuid in bound.owned_life_events
    media = load_scene_media(scene_actors(before, data, {}), data)
    group_media = load_choreography_media(group)
    number, badge = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                     for style in (data.number_style, data.badge_style))
    for time in (0, death.start_ms, group.complete_ms):
        sample = sample_choreography(group, time)
        expected = sample_attack(bound.timeline, time) if isinstance(bound, BoundAttack) else sample_cast(bound.timeline, time)
        assert sample.bodies == () and sample.clips[0].sample == expected
        for quadrant in range(4):
            frame = sample_playback_frame(before, group.after, data, time, time + 5000,
                Camera(quadrant=quadrant, viewport=(960, 640)).with_focus(death.contact.grid), {}, media,
                number, badge, choreography=group, choreography_media=group_media)
            for body in expected.bodies:
                command = actor_body(frame, body.actor_uuid)
                assert command[4][8:10] == (body.clip, body.frame)


def test_opportunity_downing_keeps_hit_recovery_and_original_dying_child_badge(
    data: AnimationData, pygame_runtime: None,
) -> None:
    captured = attack_history("weapon.longsword", 17, opportunity=True, whole_movement=True,
                                     maximum_hp=4, uses_death_saves=True)
    before, lineage = captured.before, captured.lineages[0]
    motion = bind_motion(before, lineage, data)
    assert motion is not None
    reaction, = motion.reactions
    group = reaction.choreography
    node, = group.nodes
    assert isinstance(node.bound, BoundAttack)
    attack = node.bound.timeline
    timing = attack.damage_timing
    assert timing is not None
    cue, = (row for row in group.lifecycle if isinstance(row.event, LifeStateChangeEvent)
            and row.event.new_state is LifeState.DYING)
    assert isinstance(cue.event, LifeStateChangeEvent)
    clip = body_clip(data, attack.target, data.damage_context.bodyClip)
    assert cue.start_ms == pytest.approx(timing.start_ms +
        data.damage_context.conditionFrame * 1000 / (clip.fps * data.damage_context.bodyPlaybackSpeed))
    assert cue.death_end_ms is None and group.complete_ms == attack.complete_ms
    tracks = motion_feedback(motion, data, 5000)
    dying, = (track for track in tracks if track.label == "Dying")
    source = json.loads(data.context_source_json)["contexts"]["lifecycle"]["lifeState"]["dying"]
    assert dying.color == source["color"] and dying.kind == "badge" and dying.value is None
    assert dying.start_ms == pytest.approx(5000 + reaction.start_ms + cue.start_ms)
    assert dying.duration_ms == data.badge_style.durationMs
    assert sample_feedback(dying, dying.start_ms - .001) is None
    assert sample_feedback(dying, dying.start_ms) is not None
    assert sample_feedback(dying, dying.start_ms + dying.duration_ms) is None
    hit = sample_choreography(group, timing.start_ms)
    recovered = sample_choreography(group, timing.end_ms)
    assert not hit.bodies and not recovered.bodies
    assert hit.clips[0].sample.bodies[1].clip == data.damage_context.bodyClip
    assert recovered.clips[0].sample.bodies[1].clip == "Idle"
    target_uuid = cue.event.entity_uuid
    pending = sample_choreography(group, timing.hp_ms - .001)
    assert pending.displayed.actors[target_uuid].normal_hp == 4
    assert pending.displayed.actors[target_uuid].life_state is LifeState.ALIVE
    damage_number, = (track for track in tracks if track.kind == "number")
    assert damage_number.value == attack.damage_total == 6
    for time in (timing.hp_ms, timing.end_ms, group.complete_ms):
        displayed = sample_choreography(group, time)
        vital, = (value for value in displayed.vitals if value.actor_uuid == str(target_uuid))
        assert vital.hp == displayed.displayed.actors[target_uuid].normal_hp == cue.event.normal_hit_points == 0
        assert vital.life_state is LifeState.DYING
    after = reduce_lineage(before, lineage)
    final = sample_motion(motion, data, motion.complete_ms)
    assert final.contact.life_state is LifeState.DYING and final.contact.grid != motion.actor.grid
    assert final.body.clip == "Idle" and motion.complete_ms == reaction.end_ms
    media = load_scene_media(scene_actors(before, data, {}), data)
    reactions = {group.root_uuid: load_choreography_media(group)}
    number, badge = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                     for style in (data.number_style, data.badge_style))
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=(960, 640)).with_focus((3, 3))
        frame = sample_playback_frame(before, after, data, motion.complete_ms, 5000, camera, {},
            media, number, badge, motion=motion, reaction_media=reactions)
        idle = sample_playback_frame(after, None, data, 0, 5000, camera, frame.facings,
            media, number, badge, positions=frame.positions)
        command, idle_command = actor_body(frame, final.contact.actor_uuid), actor_body(idle, final.contact.actor_uuid)
        assert frame.shown_hp[final.contact.actor_uuid] == idle.displayed.actors[target_uuid].normal_hp == 0
        assert command[4][8] == "Idle" and command[2:] == idle_command[2:]
        assert pygame.image.tobytes(command[1], "RGBA") == pygame.image.tobytes(idle_command[1], "RGBA")
