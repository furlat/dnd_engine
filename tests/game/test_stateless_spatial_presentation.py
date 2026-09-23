"""Observed constant-state footprints use the existing spatial floor painter."""

from dataclasses import replace

import numpy as np
import pygame

from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.projection import Camera, camera_pose
from game.world_animation import prop_animation
from tests.game.player_helpers import player_history
from tests.game.trap_scenarios import trap_history


def test_observed_effect_without_trap_state_draws_its_authored_frame_until_removed() -> None:
    state, _ = player_history(trap_history(detected=True), role="walker")
    assert state.senses is not None
    identity, observed = next(iter(state.senses.spatial_effects.items()))
    content = "spatial_effect.test.constant_ground"
    observed = observed.model_copy(update={
        "content_ref": observed.content_ref.model_copy(update={"content_id": content}),
        "trap_state": None,
    })
    state = replace(state, senses=replace(state.senses, spatial_effects={identity: observed}))
    absent = replace(state, senses=replace(state.senses, spatial_effects={}))
    catalog = load_catalog()
    # Existing seven-frame art makes a nonzero default frame observable; no
    # trap state or synthetic activation event selects that picture.
    art = catalog.spatial_effects["spatial_effect.environment.spike_trap"]
    binding = prop_animation({"frames_by_pose": dict(art.frames_by_pose), "fps": art.fps,
                              "state_frames": {}, "default_frame": 6})
    catalog = replace(catalog, spatial_effects={content: binding})
    pygame.init()
    try:
        screen = pygame.display.set_mode((800, 600))
        cache = SurfaceCache(catalog)
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((5, 3))

            def render(snapshot, time):
                evidence = draw_frame(screen, snapshot, catalog, cache, camera, time,
                    show_grid=False, show_debug=False, mouse_position=None, collect_evidence=True)
                assert evidence is not None and evidence.matches
                return evidence.actual_draws, pygame.surfarray.array3d(screen)

            absent_rows, bare = render(absent, 0)
            assert not any(len(row) > 6 and row[6] == "spatial_effect" for row in absent_rows)
            rows, drawn = render(state, 0)
            effects = [row for row in rows if len(row) > 6 and row[6] == "spatial_effect"]
            assert {row[1] for row in effects} == set(observed.positions)
            assert all(row[2] == f"spikes.{camera_pose('east', quadrant)}.6" and row[7] == 6
                       for row in effects)
            assert np.any(drawn != bare), "Observed floor effect must contribute actual pixels"
            _, settled = render(state, 10)
            assert np.array_equal(drawn, settled)
            _, removed = render(absent, 10)
            assert np.array_equal(bare, removed)
    finally:
        pygame.quit()
