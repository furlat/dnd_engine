"""Real held and dropped weapon pixels expose their retained coating."""

from dataclasses import replace

import numpy as np
import pygame

from game.animation import BodySample
from game.animation_data import DATA_ROOT, load_animation_data
from game.animation_draw import actor_draw_commands
from game.item_draw import item_ground_commands
from game.item_effects import item_material
from game.item_appearance import ground_appearance, item_source_palettes
from game.player_reduction import reduce_lineage
from game.projection import TILE_WIDTH, Camera, project_screen
from game.scene import load_scene_media
from game.scene_actors import scene_actors
from tests.game.item_appearance_scenarios import item_transfer_history
from tests.game.player_helpers import player_history


def test_item_colors_swap_reviewed_zones_without_darkening_other_materials(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    try:
        pygame.display.set_mode((10, 10))
        source = pygame.Surface((2, 1), pygame.SRCALPHA)
        color = item_source_palettes()["Melee1"][0]
        source.set_at((0, 0), (color >> 16 & 255, color >> 8 & 255, color & 255, 173))
        source.set_at((1, 0), (60, 30, 10, 221))
        dyed = item_material(source, (), "weapon", {}, category="Melee1", base_tint=0x334455)
        assert dyed.get_at((0, 0)) == (0x33, 0x44, 0x55, 173)
        assert dyed.get_at((1, 0)) == source.get_at((1, 0))
        assert source.get_at((0, 0))[:3] != dyed.get_at((0, 0))[:3]
    finally:
        pygame.quit()


def test_real_dagger_coating_is_visible_in_both_hands_on_floor_and_after_pickup(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    original, recipient, identity, recorded, _ = item_transfer_history(include_floor_robe=False)
    before, roots = player_history(recorded, role="holder")
    data = load_animation_data()
    pygame.init()
    try:
        pygame.display.set_mode((600, 400))
        seen = set()
        rows = {}
        state = before
        for root in roots:
            state = reduce_lineage(state, root)
            actors = scene_actors(state, data, {})
            media = load_scene_media(actors, data, body_rows=rows)
            for actor in actors:
                hand = next((layer.slot for layer in actor.layers if layer.item_effects), None)
                if hand is None:
                    continue
                stage = (actor.contact.actor_uuid, hand)
                if stage in seen:
                    continue
                plain = tuple(replace(layer, item_effects=()) for layer in actor.layers)
                body = BodySample(actor.contact.actor_uuid, "Idle", 0, actor.contact.facing)
                for quadrant in range(4):
                    camera = Camera(quadrant=quadrant, zoom=1, viewport=(600, 400)).with_focus(actor.contact.grid)
                    coated = actor_draw_commands(data, body, actor.contact, actor.layers, media, camera)
                    uncoated = actor_draw_commands(data, body, actor.contact, plain, media, camera)
                    assert len(coated) == len(uncoated)
                    differences = [np.abs(pygame.surfarray.array3d(left.surface).astype(int)
                                          - pygame.surfarray.array3d(right.surface).astype(int))
                                   for left, right in zip(coated, uncoated)]
                    assert max(difference.max() for difference in differences) >= 50
                    for left, right in zip(coated, uncoated):
                        assert np.array_equal(pygame.surfarray.array_alpha(left.surface),
                                              pygame.surfarray.array_alpha(right.surface))
                seen.add(stage)
            if identity in state.objects and "floor" not in seen:
                obj = state.objects[identity]
                plain = replace(obj, item=replace(obj.item, item_effects=()))
                for quadrant in range(4):
                    camera = Camera(quadrant=quadrant, zoom=1, viewport=(600, 400))
                    coated = item_ground_commands(obj, camera)[-1]
                    uncoated = item_ground_commands(plain, camera)[-1]
                    assert coated.destination == uncoated.destination
                    delta = np.abs(pygame.surfarray.array3d(coated.surface).astype(int)
                                   - pygame.surfarray.array3d(uncoated.surface).astype(int))
                    assert delta.max() >= 50
                    assert np.array_equal(pygame.surfarray.array_alpha(coated.surface),
                                          pygame.surfarray.array_alpha(uncoated.surface))
                seen.add("floor")
        assert {(str(original), "weapon"), (str(original), "offhand"),
                (str(recipient), "offhand"), "floor"} <= seen
        assert identity not in state.objects
        held = next(layer for layer in state.actors[recipient].visual_loadout.layers if layer.item_uuid == identity)
        assert not held.item_effects
    finally:
        pygame.quit()


def test_native_dropped_dagger_keeps_vendor_size_and_floor_pivot_in_every_camera(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    original, _, identity, recorded, _ = item_transfer_history(include_floor_robe=False)
    before, roots = player_history(recorded, role="holder")
    data = load_animation_data()
    state = before
    for root in roots:
        state = reduce_lineage(state, root)
        if identity in state.objects:
            break
    obj = state.objects[identity]
    binding = ground_appearance(obj.item.visual_item_name, obj.item.visual_variant_id)
    assert binding is not None
    assert binding.scale == .75
    assert binding.reference_tile_width == data.rig.TILE_W == 64
    assert TILE_WIDTH == 128

    pygame.init()
    try:
        pygame.display.set_mode((600, 400))
        actors = scene_actors(before, data, {})
        actor = next(row for row in actors if row.contact.actor_uuid == str(original))
        layers = tuple(layer for layer in actor.layers if layer.item_uuid == identity)
        assert len(layers) == 1 and layers[0].category == binding.sprite_key
        media = load_scene_media(actors, data, body_rows={})
        directory = DATA_ROOT.parent.parent / "assets/neuroclient/spritesheets"
        sheet = pygame.image.load(directory / binding.sprite_key / f"{binding.clip}.png").convert_alpha()
        shadow_sheet = pygame.image.load(directory / "Shadow/Idle.png").convert_alpha()
        source_shadow = shadow_sheet.subsurface((0, 2 * 128, 128, 128))
        source_shadow = source_shadow.subsurface(source_shadow.get_bounding_rect(min_alpha=1))
        width, height = binding.cell
        for zoom in (.5, 1.):
            # The ordinary held drawer supplies the vendor-to-map scale. The
            # authored floor silhouette must remain three quarters of that size.
            source_scale = TILE_WIDTH / data.rig.TILE_W * zoom
            floor_scale = binding.scale * source_scale
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, zoom=zoom, viewport=(600, 400)).with_focus(obj.placement.position)
                held, = actor_draw_commands(data,
                    BodySample(actor.contact.actor_uuid, "Idle", 0, "S"),
                    actor.contact, layers, media, camera)
                shadow, floor = item_ground_commands(obj, camera)
                held_bounds = held.surface.get_bounding_rect(min_alpha=1)
                floor_bounds = floor.surface.get_bounding_rect(min_alpha=1)
                assert abs(floor_bounds.width - held_bounds.width * binding.scale) <= 2
                assert abs(floor_bounds.height - held_bounds.height * binding.scale) <= 2

                source = sheet.subsurface((binding.frame * width,
                    binding.rows_by_camera[quadrant] * height, width, height))
                scaled = pygame.transform.scale(source,
                    (round(width * floor_scale), round(height * floor_scale)))
                crop_bounds = scaled.get_bounding_rect(min_alpha=1)
                expected = scaled.subsurface(crop_bounds)
                assert np.array_equal(pygame.surfarray.array_alpha(floor.surface),
                                      pygame.surfarray.array_alpha(expected))
                ground = project_screen(obj.placement.position, camera,
                    elevation_steps=obj.placement.base_height_steps)
                pivot = binding.pivots_by_camera[quadrant]
                restored_contact = (floor.destination[0] + pivot[0] * floor_scale - crop_bounds.x,
                                    floor.destination[1] + pivot[1] * floor_scale - crop_bounds.y)
                assert abs(restored_contact[0] - ground[0]) <= 1
                assert abs(restored_contact[1] - ground[1]) <= 1
                expected_shadow = pygame.transform.scale_by(source_shadow,
                    binding.shadow_scale * source_scale)
                assert shadow.surface.get_size() == expected_shadow.get_size()
                assert abs(shadow.destination[0] + shadow.surface.width / 2 - ground[0]) <= .5
                assert abs(shadow.destination[1] + shadow.surface.height / 2 - ground[1]) <= .5
    finally:
        pygame.quit()
