"""Real Shortbow histories draw the shared attack family on the existing map."""

import random
from dataclasses import replace
from pathlib import Path
from typing import Iterator
from uuid import UUID

import numpy as np
import pygame
import pytest

from dnd.core.equipment_types import WeaponSlot
from dnd.runtime_reset import reset_engine_runtime
from game.animation_data import load_animation_data
from game.animation_draw import BodyRows, attack_draw_commands, load_attack_media
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.attack import BoundAttack, bind_attack, sample_attack
from game.presentation import PresentationTarget
from game.projection import Camera
from tests.game.scenarios import attack_history


@pytest.fixture(scope="module", params=[
    (False, 17, 80, (7, 3)), (False, 1, 80, (6, 6)),
    (True, 17, 80, (7, 3)), (True, 1, 80, (6, 6)), (True, 5, 4, (7, 5)),
], ids=["modular-hit", "modular-miss", "goblin-hit", "goblin-miss", "goblin-lethal"])
def ranged_scene(request: pytest.FixtureRequest) -> Iterator[tuple[PresentationTarget, BoundAttack, BodyRows]]:
    random_state = random.getstate()
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((960, 720))
        try:
            goblin_source, seed, maximum_hp, position = request.param
            before, lineage = attack_history("weapon.shortbow", seed, weapon_slot=WeaponSlot.RANGED_MAIN,
                goblin_source=goblin_source, maximum_hp=maximum_hp, watcher_positions=(position,))
            data = load_animation_data(rig_files=(Path("game/data/rigs/goblin01.json"),))
            bound = bind_attack(before, lineage, data)
            assert bound is not None and bound.timeline.projectile is not None
            yield before, bound, load_attack_media(bound.timeline, bound.appearances)
        finally:
            pygame.quit()
            random.setstate(random_state)
            reset_engine_runtime()


@pytest.mark.parametrize("quadrant", range(4))
def test_real_shortbow_pixels_cross_the_map_and_retire_at_contact(
    ranged_scene: tuple[PresentationTarget, BoundAttack, BodyRows], quadrant: int, tmp_path: Path,
) -> None:
    before, bound, media = ranged_scene
    timeline, data = bound.timeline, bound.timeline.data
    assert timeline.projectile is not None
    screen = pygame.display.get_surface()
    assert screen is not None
    camera = Camera(quadrant=quadrant, zoom=1, viewport=screen.get_size()).with_focus((
        (timeline.source.grid[0] + timeline.target.grid[0]) / 2,
        (timeline.source.grid[1] + timeline.target.grid[1]) / 2,
    ))
    catalog = load_catalog()
    cache = SurfaceCache(catalog)
    font = pygame.font.SysFont(data.number_style.fontFamily, round(data.number_style.fontSizePx))
    badge_font = pygame.font.SysFont(data.badge_style.fontFamily, round(data.badge_style.fontSizePx))
    for progress in (.1, .5, .9):
        elapsed = timeline.projectile.start_ms + (timeline.contact_ms - timeline.projectile.start_ms) * progress
        sample = sample_attack(timeline, elapsed)
        commands = attack_draw_commands(timeline, sample, bound.appearances, media, font, badge_font, camera)
        projectile = next(command for command in commands if command[4][6] == "projectile")
        # Compare actual final map pixels with the same frozen bodies but no bolt.
        bare = attack_draw_commands(timeline, replace(sample, projectiles=()), bound.appearances,
                                    media, font, badge_font, camera)
        draw_frame(screen, before, catalog, cache, camera, 0, show_grid=False,
                   mouse_position=None, extra_commands=bare)
        without_bolt = pygame.surfarray.array3d(screen)
        evidence = draw_frame(screen, before, catalog, cache, camera, 0, show_grid=False,
                             mouse_position=None, extra_commands=commands)
        assert evidence.actual_draws == evidence.expected_draws
        with_bolt = pygame.surfarray.array3d(screen)
        mask_layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        mask_layer.blit(projectile[1], projectile[2])
        mask = pygame.surfarray.array_alpha(mask_layer) > 100
        pygame.image.save(screen, tmp_path / f"travel-{progress:.1f}.png")
        # Near the attachments the original low semantic anchor can sit
        # behind a body. Mid-flight it must visibly cross the ordinary map.
        if progress == .5:
            assert np.count_nonzero(mask & np.any(with_bolt != without_bolt, axis=2)) > 5
    contact = sample_attack(timeline, timeline.contact_ms)
    commands = attack_draw_commands(timeline, contact, bound.appearances, media, font, badge_font, camera)
    assert not any(command[4][6] == "projectile" for command in commands)
    assert contact.numbers
    assert contact.vitals[0].hp == bound.after.actors[UUID(timeline.target.actor_uuid)].normal_hp
    draw_frame(screen, before, catalog, cache, camera, 0, show_grid=False,
               mouse_position=None, extra_commands=commands)
    pygame.image.save(screen, tmp_path / "contact.png")
    completed = sample_attack(timeline, timeline.complete_ms)
    assert completed.complete and not completed.projectiles
    assert completed.vitals[0].life_state is bound.after.actors[UUID(timeline.target.actor_uuid)].life_state
    draw_frame(screen, bound.after, catalog, cache, camera, 0, show_grid=False,
        mouse_position=None, extra_commands=attack_draw_commands(
            timeline, completed, bound.appearances, media, font, badge_font, camera))
    pygame.image.save(screen, tmp_path / "completed.png")
