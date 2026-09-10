"""Two public A/B/A volleys share the actual single historical playback queue."""

import os
from uuid import UUID

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from game.animation import ProjectileSample, sample_cast
from game.play import run


@pytest.mark.parametrize("replace_weapon", [False, True])
def test_ordered_volley_plays_behind_latest_without_losing_repeated_target(replace_weapon: bool) -> None:
    summary = run(
        magic_missile=True, replace_weapon=replace_weapon,
        frame_deltas=(0.05,), max_frames=240, exit_when_complete=True, window_size=(960, 640),
        frame_events={
            4: (pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),),
            35: (pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),),
        },
    )
    first, second = summary.timelines
    a1, b1, a2 = first.source.applications
    actor_a, actor_b = a1.target.actor_uuid, b1.target.actor_uuid
    assert a2.target.actor_uuid == actor_a != actor_b
    assert len({application.application_id for application in first.source.applications}) == 3
    assert tuple(application.damage_total for application in first.source.applications) == (5, 5, 2)
    assert tuple(application.resulting_hp for application in first.source.applications) == (75, 75, 73)
    assert tuple(application.resulting_hp for application in second.source.applications) == (70, 73, 66)
    assert first.release_ms == pytest.approx(2000 / 3)
    assert tuple(application.travel_start_ms - first.release_ms for application in first.applications) == pytest.approx((0, 80, 160))
    assert summary.completed_casts == 2
    assert summary.completed_lineages == (6 if replace_weapon else 2)
    assert summary.historical == summary.latest
    assert summary.latest.actors[UUID(actor_a)].normal_hp == 66
    assert summary.latest.actors[UUID(actor_b)].normal_hp == 73

    first_frames = [frame for frame in summary.frames if frame.cast_number == 1]
    second_frames = [frame for frame in summary.frames if frame.cast_number == 2]
    paused = [frame for frame in first_frames if 250 <= frame.input_ms <= 1750]
    assert len(paused) > 2
    assert all(frame.sample == paused[0].sample and frame.elapsed_ms == paused[0].elapsed_ms
               for frame in paused)
    assert tuple(vital.hp for vital in paused[-1].latest_vitals) == (66, 73)
    assert tuple(vital.hp for vital in paused[-1].sample.vitals) == (80, 80)
    assert paused[-1].reduced_casts == 2

    assert {next(vital.hp for vital in frame.sample.vitals if vital.actor_uuid == actor_a)
            for frame in first_frames} == {80, 75, 73}
    assert {next(vital.hp for vital in frame.sample.vitals if vital.actor_uuid == actor_b)
            for frame in first_frames} == {80, 75}
    assert any(
        {a1.application_id, a2.application_id} <= {number.application_id for number in frame.sample.numbers}
        for frame in first_frames
    )
    assert any(len(frame.sample.projectiles) == 3 for frame in first_frames)
    assert tuple(vital.hp for vital in first_frames[-1].sample.vitals) == (73, 75)
    assert tuple(vital.hp for vital in second_frames[0].sample.vitals) == (73, 75)
    assert second_frames[0].elapsed_ms == 0
    for frame in summary.frames:
        assert frame.sample == sample_cast(summary.timelines[frame.cast_number - 1], frame.elapsed_ms)
        assert {body.actor_uuid for body in frame.sample.bodies} == {first.source.caster.actor_uuid, actor_a, actor_b}
        assert len(frame.sample.bodies) == 3
        assert all(isinstance(effect, ProjectileSample) for effect in frame.sample.projectiles)
        assert all("rune-dart" in effect.asset_id for effect in frame.sample.projectiles)
    if replace_weapon:
        assert len(summary.equipment_timelines) == 1
        assert all(len(frame.bodies) == 3 for frame in summary.equipment_frames)
        for frames, category in ((first_frames, "Melee1"), (second_frames, "Melee3")):
            assert all(next(layer.category for layer in frame.appearances[first.source.caster.actor_uuid]
                            if layer.slot == "weapon") == category for frame in frames)
