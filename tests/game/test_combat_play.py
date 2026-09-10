"""Actual SDL input, reduction, authored sampling, map draw and publication."""

import os
from uuid import UUID

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from dnd.core.life_types import LifeState
from game.animation import sample_cast
from game.play import run


def test_second_legal_cast_reduces_during_first_displayed_travel() -> None:
    summary = run(frame_deltas=(0.1,), max_frames=100,
                  exit_when_complete=True, window_size=(960, 640))

    assert summary.completed_casts == 2
    assert summary.latest == summary.historical
    first, second = summary.timelines
    assert first.source.caster.elevation_steps == 0
    assert first.source.applications[0].target.elevation_steps == 2
    assert (first.source.applications[0].target.hp, first.source.applications[0].resulting_hp,
            second.source.applications[0].target.hp, second.source.applications[0].resulting_hp) == (80, 73, 73, 66)
    assert any(
        frame.cast_number == 1 and frame.reduced_casts == 2
        and frame.latest_vitals[0].hp == 66 and frame.sample.vitals[0].hp == 80
        and any(effect.phase == "travel" for effect in frame.sample.projectiles)
        for frame in summary.frames
    )
    for frame in summary.frames:
        # Later reduction cannot alter the published historical sample or time.
        assert frame.sample == sample_cast(summary.timelines[frame.cast_number - 1], frame.elapsed_ms)
    first_last = next(frame for frame in summary.frames if frame.cast_number == 1 and frame.sample.complete)
    second_start = next(frame for frame in summary.frames if frame.cast_number == 2)
    assert first_last.sample.vitals[0].hp == second_start.sample.vitals[0].hp == 73
    assert first_last.completed_casts == 1
    assert second_start.elapsed_ms == 0
    assert summary.frames[-1].sample.vitals[0].hp == 66


def test_paused_playback_keeps_its_sample_while_input_and_reduction_advance() -> None:
    summary = run(
        frame_deltas=(0.1,), max_frames=120, exit_when_complete=True,
        window_size=(960, 640),
        frame_events={
            7: (pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),),
            18: (pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),),
        },
    )
    paused = [frame for frame in summary.frames if 800 <= frame.input_ms <= 1800]
    assert len(paused) > 2
    assert len({frame.elapsed_ms for frame in paused}) == 1
    assert all(frame.sample == paused[0].sample for frame in paused)
    assert paused[0].latest_vitals[0].hp == 73
    assert paused[-1].latest_vitals[0].hp == 66
    assert paused[-1].sample.vitals[0].hp == 80
    assert summary.completed_casts == 2 and summary.latest == summary.historical


def test_second_miss_uses_the_same_map_playback_without_a_hit_consequence() -> None:
    summary = run(frame_deltas=(0.1,), max_frames=100, exit_when_complete=True,
                  window_size=(960, 640), miss_second=True)
    second = summary.timelines[1]
    assert not second.source.applications[0].damage_applied
    assert second.applications[0].hp_ms is None
    frames = [frame for frame in summary.frames if frame.cast_number == 2]
    assert any(effect.phase == "travel" for frame in frames for effect in frame.sample.projectiles)
    assert all(frame.sample.vitals[0].hp == 73 for frame in frames)
    assert all(not frame.sample.numbers and frame.sample.vitals[0].flash is None for frame in frames)
    assert all(frame.sample.bodies[1].clip == "Idle" for frame in frames)
    assert summary.completed_casts == 2 and summary.latest == summary.historical


@pytest.mark.parametrize("lethal, final_hp, final_life", [
    (False, 3, LifeState.ALIVE),
    (True, -4, LifeState.DEAD),
])
def test_canonical_goblin_uses_fixed_rig_and_actual_gear_health_on_the_map(
    lethal: bool, final_hp: int, final_life: LifeState,
) -> None:
    summary = run(frame_deltas=(0.1,), max_frames=100, exit_when_complete=True,
                  window_size=(960, 640), goblin_recipient=True, lethal_second=lethal)
    first, second = summary.timelines
    assert first.source.caster.rig_id == "neuroclient.modular"
    assert first.source.applications[0].target.rig_id == "smallscale.goblin01"
    assert first.source.applications[0].target.visual_scale == 0.82
    assert first.source.applications[0].target.elevation_steps == 2
    assert (first.source.applications[0].target.hp, first.source.applications[0].resulting_hp, second.source.applications[0].target.hp) == (10, 3, 3)
    assert second.source.applications[0].damage_applied is lethal
    actor = summary.latest.actors[UUID(first.source.applications[0].target.actor_uuid)]
    assert actor.creature_content_ref == "content.neurodragon:creature:creature.goblin@1"
    assert actor.items and actor.equipment
    assert actor.normal_hp == final_hp and actor.life_state is final_life
    assert any(frame.cast_number == 1 and frame.sample.bodies[1].clip == "TakeDamage"
               for frame in summary.frames)
    assert summary.completed_casts == 2 and summary.latest == summary.historical
    if lethal:
        assert any(
            frame.cast_number == 1 and frame.reduced_casts == 2
            and frame.latest_vitals[0].life_state is LifeState.DEAD
            and frame.sample.vitals[0].life_state is LifeState.ALIVE
            for frame in summary.frames
        )
        assert second.source.applications[0].target.hp == 3 and second.source.applications[0].target.life_state is LifeState.ALIVE
        assert summary.frames[-1].sample.vitals[0].life_state is LifeState.DEAD
        assert summary.frames[-1].sample.bodies[1].clip == "Die"
        assert summary.frames[-1].sample.bodies[1].frame == 14
        assert summary.latest.senses is not None and actor.uuid not in summary.latest.senses.entities
