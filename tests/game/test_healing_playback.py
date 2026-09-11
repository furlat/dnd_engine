"""Native healing commits at entry; original feedback outlives the empty head."""

from dataclasses import replace
import json
from pathlib import Path

import pygame
import pytest

from devtools.animation_review import __main__ as review
from dnd.core.events import HealEvent, LifeStateChangeEvent
from dnd.core.life_types import LifeState
from game.animation_data import load_animation_data
from game.animation_types import AnimationData, HealingContext, MovementMediaTrack
from game.choreography import bind_choreography
from game.choreography_draw import load_choreography_media
from game.combat import actor_contact
from game.feedback import choreography_feedback, sample_feedback
from game.playback_frame import sample_playback_frame
from game.presentation import reduce_lineage
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from game.visual_position import VisualPosition
from tests.game.scenarios import healing_history


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data()


@pytest.mark.parametrize("dying", [False, True])
def test_native_heal_changes_hp_at_entry_and_keeps_placed_feedback_after_completion(
    data: AnimationData, dying: bool,
) -> None:
    captured = healing_history(dying=dying)
    before, lineage = captured.before, captured.lineages[0]
    event = lineage.root
    assert isinstance(event, HealEvent) and event.target_entity_uuid is not None
    target = event.target_entity_uuid
    after = reduce_lineage(before, lineage)
    group = bind_choreography(before, lineage, data)
    assert group.complete_ms == 0 and group.nodes == ()
    if dying:
        life, = (row for row in lineage.events if isinstance(row, LifeStateChangeEvent))
        assert (life.previous_state, life.new_state) == (LifeState.DYING, LifeState.ALIVE)
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
        media = load_scene_media(scene_actors(before, data, {}, positions), data)
        group_media = load_choreography_media(group)
        number_font, badge_font = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                                   for style in (data.number_style, data.badge_style))
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=(960, 640)).with_focus(legal.grid)
            entry = sample_playback_frame(before, after, data, 0, start, camera, {}, media,
                number_font, badge_font, choreography=group, choreography_media=group_media,
                feedback=(track,), positions=positions)
            assert entry.complete and entry.displayed == after
            actor = next(row for row in entry.actors if row.contact.actor_uuid == placed.actor_uuid)
            assert actor.contact.hp == event.resulting_normal_hp
            assert actor.contact.life_state is LifeState.ALIVE
            assert (actor.contact.grid, actor.contact.body_lift_px) == (placed.grid, placed.body_lift_px)
            assert entry.positions == positions
            for elapsed in (0, 450, 900):
                # The caller has released the head; only ordinary decoration remains.
                idle = sample_playback_frame(after, None, data, 0, start + elapsed, camera, {}, media,
                    number_font, badge_font, feedback=(track,), positions=positions)
                assert idle.displayed == after and idle.positions == positions
                numbers = [command for command in idle.commands if command[4][6] == "floating_number"]
                assert len(numbers) == (1 if elapsed < 900 else 0)
    finally:
        pygame.quit()


def test_selected_healing_feedback_controls_and_unsupported_body_media_are_explicit(data: AnimationData) -> None:
    captured = healing_history()
    before, lineage = captured.before, captured.lineages[0]
    quiet = replace(data, healing_context=data.healing_context.model_copy(update={"feedbackEnabled": False}))
    quiet_group = bind_choreography(before, lineage, quiet)
    assert choreography_feedback(quiet_group, quiet, 0) == ()
    assert quiet_group.complete_ms == 0 and quiet_group.after == reduce_lineage(before, lineage)

    zero = replace(data, healing_context=HealingContext.model_validate_json(json.dumps({
        **data.healing_context.model_dump(mode="json"), "feedbackDurationMs": 0,
    })))
    zero_group = bind_choreography(before, lineage, zero)
    zero_track, = choreography_feedback(zero_group, zero, 0)
    assert sample_feedback(zero_track, 0) is None and zero_group.complete_ms == 0

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
    track, = choreography_feedback(group, changed, 0)
    assert track.duration_ms == 1250 and sample_feedback(track, 1000) is not None
    assert sample_feedback(track, 1250) is None


def test_healing_gallery_records_native_entry_and_decorative_tail_in_all_corners(tmp_path: Path) -> None:
    assert review.main(["--capture", "--tag", "healing", "--fps", "12", "--width", "640", "--height", "480",
                        "--output", str(tmp_path)]) == 0
    run = tmp_path / "runs" / json.loads((tmp_path / "latest.json").read_text())["run"]
    for case in ("healing-capped", "healing-dying"):
        trace = json.loads((run / "cases" / case / "trace.json").read_text())
        root = trace["lineages"][0]["root"]
        target = root["target_entity_uuid"]
        head, = trace["heads"]
        assert head["duration_ms"] == 0
        entry = next(frame for frame in trace["frames"] if frame["root_uuid"] == root["uuid"])
        assert entry["state"]["actors"][target]["hp"] == root["resulting_normal_hp"]
        assert entry["state"]["actors"][target]["life"] == LifeState.ALIVE.value
        tail = [frame for frame in trace["frames"] if frame["root_uuid"] is None
                and frame["video_ms"] > head["video_start_ms"]]
        assert tail and any(any(command["evidence"][6] == "floating_number"
                              for command in frame["views"][0]["draws"]) for frame in tail)
        assert all([view["quadrant"] for view in frame["views"]] == [0, 1, 2, 3] for frame in tail)
        assert all(check["passed"] for check in trace["checks"])
        assert trace["gaps"] == []
