"""Public equipment commands through the real intake/sample/map/flip loop."""

import os
from uuid import UUID

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from game.animation import sample_cast, sample_equipment
from game.play import run


@pytest.mark.parametrize("pause_first", [False, True])
def test_replacement_keeps_historical_gear_until_its_gesture_completes(pause_first: bool) -> None:
    summary = run(
        replace_weapon=True, frame_deltas=(0.05,), max_frames=240,
        exit_when_complete=True, window_size=(960, 640),
        frame_events={
            7: (pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),),
            38: (pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),),
        } if pause_first else {},
    )
    first, second = summary.timelines
    caster_id = first.source.caster.actor_uuid
    caster_uuid = UUID(caster_id)
    latest = summary.latest.actors[caster_uuid]
    first_frames = [frame for frame in summary.frames if frame.cast_number == 1]
    second_frames = [frame for frame in summary.frames if frame.cast_number == 2]
    assert len(summary.equipment_timelines) == 1
    equipment = summary.equipment_timelines[0]
    assert equipment.actor.facing == first_frames[-1].sample.bodies[0].facing
    assert equipment.actor.elevation_steps == first.source.caster.elevation_steps
    assert summary.completed_lineages == 6  # two casts and four independent gear roots
    assert summary.completed_casts == 2 and summary.latest == summary.historical
    assert second.source.applications[0].target.hp == 73 and second.source.applications[0].resulting_hp == 66

    assert any(
        frame.latest_equipment == latest.equipment and frame.reduced_casts == 2
        and frame.latest_vitals[0].hp == 66 and not frame.sample.complete
        for frame in first_frames
    )
    assert first_frames[0].latest_equipment != latest.equipment
    for frame in first_frames + second_frames:
        assert frame.sample == sample_cast(summary.timelines[frame.cast_number - 1], frame.elapsed_ms)
        expected = "Melee1" if frame.cast_number == 1 else "Melee3"
        assert next(layer.category for layer in frame.appearances[caster_id]
                    if layer.slot == "weapon") == expected

    assert len(summary.equipment_frames) > 2
    assert summary.equipment_frames[0].elapsed_ms == second_frames[0].elapsed_ms == 0
    for frame in summary.equipment_frames:
        assert frame.root_event_uuid == equipment.root_event_uuid
        assert frame.sample == sample_equipment(equipment, frame.elapsed_ms)
        assert frame.latest_equipment == latest.equipment
        assert frame.sample.body.facing == equipment.actor.facing
        assert not frame.sample.body.hide_weapon
        expected = "Melee3" if frame.sample.complete else "Melee1"
        assert next(layer.category for layer in frame.appearances[caster_id]
                    if layer.slot == "weapon") == expected
        assert {body.actor_uuid for body in frame.bodies} == {caster_id, first.source.applications[0].target.actor_uuid}
        assert next(body.clip for body in frame.bodies if body.actor_uuid != caster_id) == "Idle"
    assert summary.equipment_frames[-1].sample.complete

    if pause_first:
        paused = [frame for frame in first_frames if 400 <= frame.input_ms <= 1900]
        assert len(paused) > 2
        assert all(frame.sample == paused[0].sample and frame.elapsed_ms == paused[0].elapsed_ms
                   for frame in paused)
        assert paused[0].latest_equipment != latest.equipment
        assert paused[-1].latest_equipment == latest.equipment
        assert paused[0].latest_vitals[0].hp == 73 and paused[-1].latest_vitals[0].hp == 66
