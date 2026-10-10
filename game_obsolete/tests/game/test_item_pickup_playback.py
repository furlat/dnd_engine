"""Recorded pickup removes exactly its floor item through the shared compositor."""

from math import ceil

import pygame

from game.animation_data import load_animation_data
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.choreography import bind_choreography
from game.choreography_draw import load_choreography_media
from game.playback_frame import sample_playback_frame
from dnd.player.facts import ActionFact
from dnd.player.reduction import reduce_lineage
from game.projection import Camera
from game.scene import load_scene_media
from game.scene_actors import scene_actors
from tests.game.item_appearance_scenarios import item_transfer_history
from tests.game.player_helpers import player_history


def test_pickup_clears_ground_dagger_in_every_playback_view_and_preserves_spare_robe(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    _, _, identity, history, _ = item_transfer_history()
    initial, roots = player_history(history, role="holder")
    data = load_animation_data()
    state = initial
    observed_actors = list(scene_actors(state, data, {}))
    for root in roots:
        state = reduce_lineage(state, root)
        observed_actors.extend(scene_actors(state, data, {}))
    spare, = (key for key, obj in state.objects.items() if obj.item.item_id == "apparel.robes.wizard")
    assert identity not in state.objects

    pygame.init()
    try:
        screen = pygame.display.set_mode((800, 560))
        body_rows = {}
        media = load_scene_media(tuple(observed_actors), data, body_rows=body_rows)
        fonts = tuple(pygame.font.SysFont(style.fontFamily, round(style.fontSizePx), bold=True)
                      for style in (data.number_style, data.badge_style))
        catalog = load_catalog()
        cache = SurfaceCache(catalog)
        before = initial
        picked_up = saw_floor_pile = False
        for root in roots:
            after = reduce_lineage(before, root)
            fact = root.root.fact
            pickup = isinstance(fact, ActionFact) and fact.name == "Pick Up" and fact.target_entity_uuid == identity
            if pickup:
                assert identity in before.objects and spare in before.objects
                assert identity not in after.objects and spare in after.objects
                picked_up = True
            if not picked_up and not (identity in after.objects and spare in after.objects):
                before = after
                continue
            group = bind_choreography(before, root, data)
            assert not group.gaps
            group_media = load_choreography_media(group, body_rows=body_rows)
            # The real gallery runs at 24 fps. Include the exact authored
            # pickup contact so a one-frame delay cannot hide between ticks.
            contact = next((cue.effect_ms for cue in group.body_actions if cue.event_uuid == root.root.uuid), 0.)
            times = {min(tick * 1000 / 24, group.complete_ms)
                     for tick in range(ceil(group.complete_ms * 24 / 1000) + 1)}
            if pickup:
                times.update((max(0., contact - .001), contact))
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((3.5, 3))
                for elapsed in sorted(times):
                    frame = sample_playback_frame(before, after, data, elapsed, elapsed, camera, {}, media,
                        *fonts, choreography=group, choreography_media=group_media)
                    expected_dagger = not picked_up or pickup and elapsed < contact
                    assert (identity in frame.displayed.objects) is expected_dagger
                    assert spare in frame.displayed.objects
                    evidence = draw_frame(screen, frame.displayed, catalog, cache, camera, elapsed / 1000,
                        show_grid=False, show_debug=False, mouse_position=None, extra_commands=frame.commands,
                        world_transitions=frame.world_transitions, residue_reveals=frame.residue_reveals,
                        deposited_materials=frame.deposited_materials, collect_evidence=True).evidence
                    assert evidence is not None and evidence.matches
                    ground_items = {row[0] for row in evidence.actual_draws if len(row) == 4}
                    assert (str(identity) in ground_items) is expected_dagger
                    assert str(spare) in ground_items
                    saw_floor_pile |= not picked_up
            before = after
        assert picked_up and saw_floor_pile
        assert identity not in before.objects and set(before.objects) == {spare}
    finally:
        pygame.quit()
