"""Native healing commits at entry; body recovery and feedback have separate clocks."""

from dataclasses import replace
import json
from pathlib import Path

import pygame
import pytest

from devtools.animation_review import capture as review
from dnd.core.events import HealEvent, LifeStateChangeEvent
from dnd.core.life_types import LifeState
from game.animation_draw import LoadedBodyRows
from game.animation_data import load_animation_data
from game.animation_types import AnimationData, HealingContext, MovementMediaTrack
from game.choreography import bind_choreography
from game.choreography_draw import load_choreography_media
from game.combat import actor_contact
from game.feedback import choreography_feedback, sample_feedback
from game.playback_frame import sample_playback_frame
from game.player_reduction import reduce_lineage
from tests.game.player_helpers import player_history
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from game.visual_position import VisualPosition
from tests.game.scenarios import healing_history


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data()


@pytest.mark.parametrize("dying", [False, True])
def test_native_heal_commits_at_entry_while_recovery_and_feedback_finish_independently(
    data: AnimationData, dying: bool,
) -> None:
    captured = healing_history(dying=dying)
    before, (lineage,) = player_history(captured)
    event = captured.lineages[0].root
    assert isinstance(event, HealEvent) and event.target_entity_uuid is not None
    target = event.target_entity_uuid
    after = reduce_lineage(before, lineage)
    group = bind_choreography(before, lineage, data)
    assert group.nodes == ()
    if dying:
        life, = (row for row in captured.lineages[0].events if isinstance(row, LifeStateChangeEvent))
        assert (life.previous_state, life.new_state) == (LifeState.DYING, LifeState.ALIVE)
        recovery, = group.lifecycle
        assert recovery.body is not None and recovery.body.reversed
        authored = data.life_state_context.bodyPoses["dying"].removalBody
        assert authored is not None and recovery.body.clip == authored.bodyClip
        assert group.complete_ms == recovery.body_end_ms == recovery.body.frames * 1000 / recovery.body.fps
    else:
        assert group.complete_ms == 0 and group.lifecycle == ()
    assert group.gaps == ()
    context = data.healing_context
    original = json.loads(data.context_source_json)["contexts"]["vital_effect"]["healing"]
    assert context.model_dump(mode="json") == original
    assert (context.bodyClip, context.media, context.feedbackDurationMs) == ("none", (), 900)

    legal = actor_contact(before, before.actors[target], data)
    placed = replace(legal, grid=(legal.grid[0] + .25, legal.grid[1]), body_lift_px=20)
    positions = {placed.actor_uuid: VisualPosition(legal.grid, placed.grid, placed.elevation_steps, placed.body_lift_px)}
    start = 5000.0
    tracks = choreography_feedback(group, data, start, contacts={placed.actor_uuid: placed})
    track, = (row for row in tracks if row.kind == "number")
    badges = tuple(row for row in tracks if row.kind == "badge")
    assert len(badges) == int(dying)
    if dying:
        assert (badges[0].label, badges[0].contact) == ("Revived", placed)
    assert track.contact == placed
    assert (track.start_ms, track.duration_ms, track.value, track.label, track.color) == (
        start, 900, event.actual_healing, "Heal", 4521796)
    assert track.style == data.number_style
    assert sample_feedback(track, start - 1) is None
    assert sample_feedback(track, start + 899.99) is not None
    assert sample_feedback(track, start + 900) is None

    pygame.init()
    try:
        pygame.display.set_mode((960, 640))
        body_rows: LoadedBodyRows = {}
        media = load_scene_media(scene_actors(before, data, {}, positions), data, body_rows=body_rows)
        group_media = load_choreography_media(group, body_rows=body_rows)
        number_font, badge_font = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                                   for style in (data.number_style, data.badge_style))
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=(960, 640)).with_focus(legal.grid)
            entry = sample_playback_frame(before, after, data, 0, start, camera, {}, media,
                number_font, badge_font, choreography=group, choreography_media=group_media,
                feedback=(track,), positions=positions)
            assert entry.complete is (not dying)
            # Values commit at entry; a finite body's causal head retires later.
            assert replace(entry.displayed, reducer_cursor=after.reducer_cursor) == after
            assert entry.displayed.reducer_cursor <= after.reducer_cursor
            actor = next(row for row in entry.actors if row.contact.actor_uuid == placed.actor_uuid)
            assert actor.contact.hp == event.resulting_normal_hp
            assert actor.contact.life_state is LifeState.ALIVE
            assert (actor.contact.grid, actor.contact.body_lift_px) == (placed.grid, placed.body_lift_px)
            assert entry.positions == positions
            for elapsed in sorted({0, 450, 900, group.complete_ms / 2, group.complete_ms, group.complete_ms + 100}):
                recovering = elapsed < group.complete_ms
                frame = sample_playback_frame(before if recovering else after, after if recovering else None,
                    data, elapsed if recovering else 0, start + elapsed, camera, {}, media,
                    number_font, badge_font, choreography=group if recovering else None,
                    choreography_media=group_media if recovering else None,
                    feedback=(track,), positions=positions)
                assert replace(frame.displayed, reducer_cursor=after.reducer_cursor) == after
                assert frame.positions == positions
                if recovering:
                    assert not frame.complete and frame.displayed.reducer_cursor < after.reducer_cursor
                else:
                    assert frame.displayed == after
                body, = (command for command in frame.commands if command.evidence[0] == placed.actor_uuid
                         and command.evidence[6] == "actor")
                assert body.evidence[8] == ("Die" if recovering else "Idle")
                if dying and elapsed == 0:
                    assert body.evidence[9] == 14
                elif dying and elapsed == group.complete_ms / 2:
                    assert body.evidence[9] == 7
                numbers = [command for command in frame.commands if command[4][6] == "floating_number"]
                assert len(numbers) == (1 if elapsed < 900 else 0)
            finished = sample_playback_frame(before, after, data, group.complete_ms, start + group.complete_ms,
                camera, {}, media, number_font, badge_font, choreography=group,
                choreography_media=group_media, feedback=(track,), positions=positions)
            assert finished.complete and finished.displayed == after and finished.positions == positions
            # An absolute seek restores entry's reversed-body frame and placed feedback.
            revisited = sample_playback_frame(before, after, data, 0, start, camera, {}, media,
                number_font, badge_font, choreography=group, choreography_media=group_media,
                feedback=(track,), positions=positions)
            assert revisited.displayed == entry.displayed and revisited.positions == entry.positions
            assert [command.evidence for command in revisited.commands] == [command.evidence for command in entry.commands]
    finally:
        pygame.quit()


@pytest.mark.parametrize("dying", [False, True])
def test_selected_healing_feedback_controls_and_unsupported_body_media_are_explicit(
    data: AnimationData, dying: bool,
) -> None:
    captured = healing_history(dying=dying)
    before, (lineage,) = player_history(captured)
    ordinary = bind_choreography(before, lineage, data)
    quiet = replace(data, healing_context=data.healing_context.model_copy(update={"feedbackEnabled": False}))
    quiet_group = bind_choreography(before, lineage, quiet)
    assert not any(track.kind == "number" for track in choreography_feedback(quiet_group, quiet, 0))
    assert quiet_group.complete_ms == ordinary.complete_ms and quiet_group.after == reduce_lineage(before, lineage)

    zero = replace(data, healing_context=HealingContext.model_validate_json(json.dumps({
        **data.healing_context.model_dump(mode="json"), "feedbackDurationMs": 0,
    })))
    zero_group = bind_choreography(before, lineage, zero)
    zero_track, = (track for track in choreography_feedback(zero_group, zero, 0) if track.kind == "number")
    assert sample_feedback(zero_track, 0) is None and zero_group.complete_ms == ordinary.complete_ms

    media = MovementMediaTrack(id="healing-test", role="source_vfx", assetId="selected-healing-media",
        attachment="body", tint=0xFFFFFF, tint2=None, startFrame=0, fps=24, loop=False,
        reversed=False, scale=1, offsetX=0, offsetY=0)
    changed = replace(data, healing_context=HealingContext.model_validate_json(json.dumps({
        **data.healing_context.model_dump(mode="json"), "bodyClip": "Taunt",
        "feedbackDurationMs": 1250, "media": [media.model_dump(mode="json")],
    })))
    group = bind_choreography(before, lineage, changed)
    assert {detail for _, detail in group.gaps} == {
        "Healing bodyClip 'Taunt' is not bound", "Healing media tracks are not bound"}
    track, = (track for track in choreography_feedback(group, changed, 0) if track.kind == "number")
    assert track.duration_ms == 1250 and sample_feedback(track, 1000) is not None
    assert sample_feedback(track, 1250) is None
    assert group.complete_ms == ordinary.complete_ms


def test_healing_gallery_records_native_entry_and_decorative_tail_in_all_corners(tmp_path: Path) -> None:
    assert review.main(["--tag", "healing", "--fps", "12", "--width", "640", "--height", "480",
                        "--output", str(tmp_path)]) == 0
    run = tmp_path / "runs" / json.loads((tmp_path / "latest.json").read_text())["run"]
    for case in ("healing-capped", "healing-capped--recipient", "healing-dying", "healing-dying--recipient"):
        trace = json.loads((run / "cases" / case / "trace.json").read_text())
        root = trace["lineages"][0]["root"]
        target = root["fact"]["target_entity_uuid"]
        head, = trace["heads"]
        dying = case.startswith("healing-dying")
        if dying:
            recovery, = head["composition"]["lifecycle"]
            body = recovery["body"]
            assert body["clip"] == "Die" and body["reversed"]
            assert head["duration_ms"] == recovery["body_end_ms"] == body["frames"] * 1000 / body["fps"]
        else:
            assert head["duration_ms"] == 0
        entry = next(frame for frame in trace["frames"] if frame["root_uuid"] == root["uuid"])
        assert entry["state"]["actors"][target]["hp"] == root["fact"]["resulting_normal_hp"]
        assert entry["state"]["actors"][target]["life"] == LifeState.ALIVE.value
        assert entry["complete"] is (not dying)
        tail = [frame for frame in trace["frames"] if frame["root_uuid"] is None
                and frame["video_ms"] > head["video_start_ms"]]
        assert tail and trace["frames"][-1]["state"] == trace["latest"]
        historical = [frame for frame in trace["frames"] if frame["video_ms"] >= head["video_start_ms"]]
        if dying:
            assert any(900 <= frame["elapsed_ms"] < head["duration_ms"] for frame in historical
                       if frame["root_uuid"] == root["uuid"])
        for frame in historical:
            age = frame["presentation_ms"] - head["presentation_start_ms"]
            assert frame["state"]["actors"][target] == trace["latest"]["actors"][target]
            assert [view["quadrant"] for view in frame["views"]] == [0, 1, 2, 3]
            for view in frame["views"]:
                healing = [draw for draw in view["draws"] if draw["evidence"][6] == "floating_number"
                           and draw["evidence"][2] == "Heal"]
                assert len(healing) == (1 if 0 <= age < 900 else 0)
                actor, = (draw for draw in view["draws"] if draw["evidence"][0] == target
                          and draw["evidence"][6] == "actor")
                assert actor["evidence"][8] == ("Die" if age < head["duration_ms"] else "Idle")
                if frame is entry and dying:
                    assert actor["evidence"][9] == 14
        assert all(check["passed"] for check in trace["checks"])
        assert trace["gaps"] == []
