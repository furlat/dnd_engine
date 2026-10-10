"""Clicks follow displayed physical pixels, including windows and foreground cuts."""

from dataclasses import replace
from math import isfinite

import numpy as np
import pygame
import pytest

from game.animation import BodySample
from game.animation_data import load_animation_data, resolve_player_layers
from game.animation_draw import actor_draw_commands, load_actor_media
from game.app import draw_frame
from game.demo import build_demo_intervals
from dnd.player.capture import reduce_interval
from tests.game.test_boundary_rendering import _wall_target
from game.assets import SurfaceCache, load_catalog
from game.combat import actor_contact
from game.choreography import bind_choreography, sample_motion
from dnd.player.facts import MovementFact
from game.draw_commands import DrawCommand
from game.fixture_depth import partition_world_depth
from game.floor_composition import compose_floor_coverings
from game.interaction_frame import compose_interaction_frame, draw_highlights, pick_world
from game.interaction_types import SelectionCoverage, WorldHit
from game.projection import Camera
from dnd.types.world import CardinalDirection
from dnd.types.senses import PerceivedContact
from game.construction_media import construction_media_draw_commands
from tests.game.construction_scenarios import construction_history
from dnd.player.reduction import reduce_lineage
from dnd.core.item_types import ItemIntegrity
from game.condition_animation import ConditionAppearance
from tests.game.test_environment_presentation import _saved
from tests.game.window_scenarios import window_history


@pytest.fixture(scope="module")
def raster():
    pygame.init()
    screen = pygame.display.set_mode((640, 480))
    yield screen, load_catalog(), load_animation_data()
    pygame.quit()


def image(size, filled=True):
    result = pygame.Surface(size, pygame.SRCALPHA)
    if filled:
        result.fill("white")
    return result


def command(surface, depth, identity, *, kind="actor", mask=None, occludes=True):
    coverage = pygame.surfarray.array_alpha(surface) > 0 if mask is None else mask
    return DrawCommand((0, depth, 0., 0, (identity,)), surface, (2, 2), 0, (),
        selection=(SelectionCoverage(WorldHit(kind, identity, (0, 0), 0), coverage),),
        selection_occluder=occludes)


def test_foreground_surface_blocks_click_and_outline_even_when_not_an_action_target(raster):
    actor = command(image((10, 10)), 0, "actor")
    wall = DrawCommand((0, 1., 0., 0, ("wall",)), image((5, 10)), (2, 2), 0, (), selection_occluder=True)
    frame = compose_interaction_frame((actor, wall), (20, 20))
    assert pick_world(frame, (3, 5)) is None
    assert pick_world(frame, (9, 5)).identity == "actor"
    canvas = pygame.Surface((20, 20), pygame.SRCALPHA)
    draw_highlights(canvas, frame, ((actor.selection[0].hit, (255, 200, 0)),))
    assert not np.any(pygame.surfarray.array_alpha(canvas)[2:7, 2:12])


def test_empty_window_aperture_offers_passage_but_visible_body_has_priority(raster):
    wall_image = image((12, 12))
    wall_image.fill((0, 0, 0, 0), (3, 3, 6, 6))
    opening = np.zeros((12, 12), dtype=bool)
    opening[3:9, 3:9] = True
    wall = command(wall_image, 1, "window", kind="object")
    wall = wall._replace(selection=(*wall.selection,
        SelectionCoverage(WorldHit("aperture", "window", (0, 0), 0), opening)))
    actor = command(image((12, 12)), 0, "actor")
    assert pick_world(compose_interaction_frame((wall,), (20, 20)), (7, 7)).kind == "aperture"
    assert pick_world(compose_interaction_frame((actor, wall), (20, 20)), (7, 7)).identity == "actor"
    assert pick_world(compose_interaction_frame((actor, wall), (20, 20)), (3, 3)).identity == "window"


def test_transferred_floor_pixels_do_not_intercept_the_visible_covering(raster):
    ground = command(image((14, 12)), 2, "tile", kind="ground")._replace(role="terrain_floor")
    rug = command(image((8, 8)), 1, "rug", kind="object")._replace(role="environment_floor")
    composed = compose_floor_coverings([ground, rug])
    frame = compose_interaction_frame(sorted(composed, key=lambda row: row.key), (20, 20))
    assert pick_world(frame, (4, 4)).identity == "rug"
    assert pick_world(frame, (13, 4)).identity == "tile"


def test_ground_is_available_only_through_surviving_top_pixels(raster):
    ground = command(image((14, 12)), 0, "tile", kind="ground")
    wall_image = image((10, 12))
    wall_image.fill((0, 0, 0, 0), (4, 3, 4, 6))
    opening = np.zeros((10, 12), dtype=bool)
    opening[4:8, 3:9] = True
    wall = DrawCommand((0, 1., 0., 0, ("unknown-wall",)), wall_image, (2, 2), 0, (),
        selection=(SelectionCoverage(WorldHit("aperture", "passage", (0, 0), 0), opening),),
        selection_occluder=True)
    frame = compose_interaction_frame((ground, wall), (20, 20))
    assert pick_world(frame, (3, 5)) is None
    assert pick_world(frame, (7, 6)).identity == "passage"
    assert pick_world(frame, (14, 6)).identity == "tile"


def test_transparent_aperture_depth_band_retains_finite_sorting_and_selection(raster):
    surface = image((12, 12), False)
    surface.fill("white", (0, 0, 3, 12))
    opening = np.zeros((12, 12), dtype=bool)
    opening[6:10, 3:9] = True
    wall = command(surface, 0, "window", kind="aperture", mask=opening)
    depth = np.broadcast_to(np.arange(12)[:, None], (12, 12))
    parts = partition_world_depth(wall, depth, [4., 8.])
    assert all(isfinite(part.key[1]) for part in parts)
    assert pick_world(compose_interaction_frame(sorted(parts, key=lambda p:p.key), (20, 20)), (9, 7)).kind == "aperture"


@pytest.mark.parametrize("quadrant", range(4))
def test_native_window_frame_emits_post_cut_actor_coverage_without_changing_scene_pixels(raster, quadrant):
    state, lineages = _saved(window_history().views["attacker"])
    screen, catalog, data = raster
    # Reuse the real native crawl through the already-broken insert, including
    # its registered sill height, tucked body and passage point.
    for lineage in lineages:
        if isinstance(lineage.root.fact, MovementFact) and lineage.root.fact.connector_presentation_key == "window":
            group = bind_choreography(state, lineage, data)
            timeline = group.movements[0].timeline
            middle = sample_motion(timeline, data, timeline.complete_ms / 2)
            assert middle.body is not None and middle.contact is not None
            contact, body = middle.contact, middle.body
            break
        state = reduce_lineage(state, lineage)
    else:
        pytest.fail("Native recording lacks its window crawl")
    camera = Camera(quadrant=quadrant, zoom=1, viewport=screen.get_size()).with_focus((5.5, 4))
    actor = state.actors[state.observer_uuid]
    layers = resolve_player_layers(data, actor, rig_id=contact.rig_id)
    media = load_actor_media(data, ((contact, layers, ("Rolling",)),), all_facings=True)
    commands = actor_draw_commands(data, body, contact, layers, media, camera)
    cache = SurfaceCache(catalog)
    draw_frame(screen, state, catalog, cache, camera, 0, show_grid=False,
               mouse_position=None, show_debug=False, extra_commands=commands)
    original = pygame.surfarray.array3d(screen)
    result = draw_frame(screen, state, catalog, cache, camera, 0, show_grid=False,
        mouse_position=None, show_debug=False, extra_commands=commands, collect_interaction=True)
    np.testing.assert_array_equal(pygame.surfarray.array3d(screen), original)
    assert result.interaction is not None
    actor_regions = tuple(r for r in result.interaction.regions if r.hit.identity == contact.actor_uuid)
    assert actor_regions, "The actual body is visible inside the aperture in every camera"
    for region in actor_regions:
        assert not region.mask.flags.writeable
        local = np.argwhere(region.mask)[len(np.argwhere(region.mask)) // 2]
        hit = pick_world(result.interaction, (int(local[0])+region.destination[0], int(local[1])+region.destination[1]))
        assert hit is not None and hit.identity == contact.actor_uuid
    assert any(r.hit.kind == "aperture" for r in result.interaction.regions)
    assert not any(r.hit.kind == "object" and r.hit.identity not in {str(i) for i in state.senses.objects}
                   for r in result.interaction.regions)


def test_spell_overlays_and_shadow_are_not_physical_actor_coverage(raster):
    state, _ = _saved(window_history().views["attacker"])
    screen, _, data = raster
    actor = state.actors[state.observer_uuid]
    contact = actor_contact(state, actor, data)
    layers = resolve_player_layers(data, actor, rig_id=contact.rig_id)
    # These are the actual authored overlay categories, not artificial hitbox sprites.
    aura = replace(layers[0], slot="aura", category="Effect4", alpha=1.)
    decorated = (*layers, aura)
    media = load_actor_media(data, ((contact, decorated, ("Attack5",)),), all_facings=True)
    camera = Camera(viewport=screen.get_size()).with_focus(contact.grid)
    body = BodySample(contact.actor_uuid, "Attack5", 6, contact.facing)
    plain = actor_draw_commands(data, body, contact, layers, media, camera)
    glow = actor_draw_commands(data, body, contact, decorated, media, camera)
    assert not plain[0].selection and not glow[0].selection
    np.testing.assert_array_equal(plain[-1].selection[0].mask, glow[-1].selection[0].mask)
    assert np.count_nonzero(pygame.surfarray.array_alpha(glow[-1].surface)) > np.count_nonzero(glow[-1].selection[0].mask)


def test_fully_faded_body_is_not_clickable_or_a_pick_occluder(raster):
    state, _ = _saved(window_history().views["attacker"])
    screen, _, data = raster
    actor = state.actors[state.observer_uuid]
    contact = actor_contact(state, actor, data)
    layers = resolve_player_layers(data, actor, rig_id=contact.rig_id)
    media = load_actor_media(data, ((contact, layers, ("Idle",)),), all_facings=True)
    camera = Camera(viewport=screen.get_size()).with_focus(contact.grid)
    commands = actor_draw_commands(data, BodySample(contact.actor_uuid, "Idle", 0, contact.facing),
        contact, layers, media, camera, condition=ConditionAppearance(alpha=0.))
    assert not compose_interaction_frame(commands, screen.get_size()).regions


def test_merged_corner_retains_each_real_wall_identity(raster):
    screen, catalog, data = raster
    base, _ = reduce_interval(None, build_demo_intervals()[0])
    state, identities = _wall_target(base,(CardinalDirection.NORTH,CardinalDirection.EAST))
    assert state.senses is not None and base.senses is not None
    state.senses = replace(state.senses,objects={identity:PerceivedContact(position=(20,20),visual=True) for identity in identities})
    corner=state.objects
    cache = SurfaceCache(catalog)
    for q in range(4):
        camera = Camera(quadrant=q, viewport=screen.get_size()).with_focus((20,20))
        result = draw_frame(screen,state,catalog,cache,camera,0,show_grid=False,
            show_debug=False,mouse_position=None,collect_interaction=True,collect_evidence=True)
        assert result.evidence is not None
        assert any("wall_corner" in row for row in result.evidence.actual_draws)
        assert result.interaction is not None
        masks = {}
        for region in result.interaction.regions:
            if region.hit.kind != "object":
                continue
            mask = masks.setdefault(region.hit.identity,np.zeros(screen.get_size(),dtype=bool))
            dx,dy = region.destination
            w,h=region.mask.shape
            mask[max(dx,0):min(dx+w,screen.width),max(dy,0):min(dy+h,screen.height)] |= region.mask[
                max(-dx,0):min(w,screen.width-dx),max(-dy,0):min(h,screen.height-dy)]
        assert set(masks) == {str(identity) for identity in corner}
        first,second=masks.values()
        assert np.any(first & ~second) and np.any(second & ~first)


def test_merged_force_surface_uses_each_native_sections_real_xyz(raster):
    screen, _, data = raster
    state, roots = _saved(construction_history(material='force',break_section=False).views['caster'])
    for root in roots:
        after = reduce_lineage(state,root)
        if any(obj.item.construction_geometry is not None for obj in after.objects.values()):
            state=after
            break
        state=after
    members={str(identity) for identity,obj in state.objects.items() if obj.item.construction_geometry is not None}
    assert len(members)>1
    for q in range(4):
        camera=Camera(quadrant=q,viewport=screen.get_size()).with_focus((10,10))
        commands=construction_media_draw_commands(state,data,3000,camera,{})
        masks={}
        for command in commands:
            for row in command.selection:
                assert np.any(row.mask), row.hit.identity
                masks.setdefault(row.hit.identity,[]).append(row.mask)
        assert set(masks)==members
        # Adjacent members are independently selected even when one material
        # command draws the complete merged wall. Boundaries may share pixels.
        for command in commands:
            if len(command.selection)>1:
                first,second=command.selection[:2]
                assert np.any(first.mask & ~second.mask)
                assert np.any(second.mask & ~first.mask)
