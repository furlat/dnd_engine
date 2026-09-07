"""Source-faithful Unity Water oracle and material invariants."""

import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
import pygame

from game.assets import SurfaceCache, load_catalog
from game.projection import Camera, ZOOM_LEVELS, project_screen
from game.water import (
    WaterSupportInput,
    render_water_batch,
    shade_water_packed,
    water_source_origin,
)


ORACLE = Path(__file__).parent / "data" / "unity_water_oracle.json"

PRE_REPAIR_WATER_DIGESTS = {
    0.15: (
        ((38, 38), (650, 343), "959fd8c216d9c434854abb1ef36bd02a88cbfdad9a85c7e06adf2f0313f7e92b", "54317425993c37de779fd2b5a89e32ff4ee2636d8d7a7ce604e5856dc7438cdb"),
        ((38, 38), (678, 396), "f4841dbd032635cc748b846b5066fca9af2e3a1c3e1f417854a8f44ed3fcab98", "f0bc7baa279ab51805a2b01e385b8c06cd59f1c46800058b0097a8bb1b9970bd"),
    ),
    0.35: (
        ((90, 90), (662, 321), "5046f874238c42b8e781a9792900bd19b4f64df1d2a7ef7a6d98839480882c81", "fd26ecc00c007566f1dc67279cb8344e49d1799e30ad0861a107ae6621c74ef6"),
        ((90, 90), (730, 444), "47491fe361b68d665cb56a23c48704288f0b5cb12c1d5633d34542bb927d83da", "14aaa62646edd9b8ddb562361224b98e51910815e31dc27b6cb49511eaa79350"),
    ),
    0.5: (
        ((128, 128), (672, 304), "3ceee944a963537c73dac04eb0178c4ad5e509eace75b6cdd554281c56afa465", "a2f47f3959798154136e7641f92f5dcb740802c54106cfba76f38573d239fa37"),
        ((128, 128), (768, 480), "1e98e52d27cf65671dd65602cf2b2ad025fb676e4b35aa545f7a9b2d25792877", "810372fc69ba344e9eac07c56e9fc04a5b6718ef5faf420850f8fe9e88f18c38"),
    ),
    0.75: (
        ((192, 192), (688, 276), "b448d974ca4516de93f9368284c098f6f3c61d4702a1425566e7ab13710c8438", "320865b15c46265d4c325a47a7029079515ddc43d5c7117dd806553e4f94f71c"),
        ((192, 192), (832, 540), "37ed17bc7abe97539cddfefecda904badf1ae831d846d4d1b747484ea39a4831", "cb6c3338d6e8d6ab407ef976f056adda9ab94de7b8dee98c5d6c19d7db0cd82a"),
    ),
    1.0: (
        ((256, 256), (704, 248), "ab3b35ad1b84f54741068a4588a85872889221231ae1ae1d72f1750b8854a537", "c34fb73213656551ce3be4d95945fb7ba42074658e5e6c8a2c71129429e1b7ee"),
        ((256, 256), (896, 600), "f7d5ad755e1f319fc079060d55f3d7b4edea242402fc52f54c0324d344c90177", "e96976dd4d562a19b64f00c7dc8932120bcfab0278a22d1f54fe85b7453231e8"),
    ),
}


def _maximum_channel_delta(left: np.ndarray, right: np.ndarray) -> int:
    return int(np.abs(left.astype(np.int16) - right.astype(np.int16)).max(initial=0))


def test_water_kernel_and_real_blend_match_frozen_ts_oracle() -> None:
    oracle = json.loads(ORACLE.read_text(encoding="utf-8"))
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        catalog = load_catalog()
        cache = SurfaceCache(catalog)
        ripple = pygame.surfarray.array3d(cache.canonical["water.ripple"])
        normal = pygame.surfarray.array3d(cache.canonical["water.normal"])
        inputs = np.asarray(oracle["input_pixels"], dtype=np.float32)
        origins = np.repeat(
            np.asarray([oracle["source_origin_px"]], dtype=np.float32),
            len(inputs),
            axis=0,
        )
        globals_xy = np.asarray(oracle["global_framebuffer_pixels"], dtype=np.float32)
        masks = np.asarray(oracle["mask_alpha"], dtype=np.float32)
        for time_row in oracle["times"]:
            raw = shade_water_packed(
                mask_alpha=masks,
                input_pixels=inputs,
                source_origins_px=origins,
                global_framebuffer_pixels=globals_xy,
                framebuffer_size=tuple(oracle["framebuffer_size"]),
                tile_width_px=oracle["tile_width_px"],
                render_scale=oracle["render_scale"],
                time_seconds=time_row["time"],
                ripple_texture=ripple,
                normal_texture=normal,
                material=catalog.water,
            )
            expected_raw = np.asarray(time_row["raw_rgba"], dtype=np.uint8)
            assert _maximum_channel_delta(raw, expected_raw) <= 1
            actual_composite = []
            for pixel in raw:
                destination = pygame.Surface((1, 1), pygame.SRCALPHA, 32).convert_alpha()
                destination.fill(tuple(oracle["destination_rgba"]))
                source = pygame.Surface((1, 1), pygame.SRCALPHA, 32).convert_alpha()
                source.fill(tuple(int(channel) for channel in pixel))
                destination.blit(source, (0, 0), special_flags=pygame.BLEND_PREMULTIPLIED)
                actual_composite.append(destination.get_at((0, 0)))
            expected_composite = np.asarray(time_row["composited_rgba"], dtype=np.uint8)
            assert _maximum_channel_delta(np.asarray(actual_composite), expected_composite) <= 1
    finally:
        pygame.quit()


def test_world_phase_is_translation_independent_but_sheen_uses_screen_position() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        catalog = load_catalog()
        cache = SurfaceCache(catalog)
        ripple = pygame.surfarray.array3d(cache.canonical["water.ripple"])
        normal = pygame.surfarray.array3d(cache.canonical["water.normal"])
        common = dict(
            mask_alpha=np.ones(1, dtype=np.float32),
            input_pixels=np.asarray([[17, 23]], dtype=np.float32),
            source_origins_px=np.asarray([[128, 256]], dtype=np.float32),
            framebuffer_size=(640, 360),
            tile_width_px=128,
            render_scale=0.5,
            time_seconds=0.1,
            ripple_texture=ripple,
            normal_texture=normal,
            material=catalog.water,
        )
        centered = shade_water_packed(
            global_framebuffer_pixels=np.asarray([[320, 180]], dtype=np.float32),
            **common,
        )
        edge = shade_water_packed(
            global_framebuffer_pixels=np.asarray([[10, 10]], dtype=np.float32),
            **common,
        )
        later = shade_water_packed(
            global_framebuffer_pixels=np.asarray([[320, 180]], dtype=np.float32),
            **{**common, "time_seconds": 1.25},
        )
        assert not np.array_equal(centered[:, :3], edge[:, :3])
        assert centered[:, 3].tolist() == edge[:, 3].tolist()
        assert not np.array_equal(centered, later)
    finally:
        pygame.quit()


def test_chunk_split_and_unsplit_scatter_identical_support_pixels() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        catalog = load_catalog()
        cache = SurfaceCache(catalog)
        camera = Camera(zoom=0.5, pan=(320.0, -820.0), viewport=(640, 360))
        mask_id = catalog.water["mask"]
        mask = cache.scaled(mask_id, camera.zoom)
        spec = catalog.resources[mask_id]
        supports = tuple(
            WaterSupportInput(
                source_origin_px=water_source_origin(
                    position,
                    pivot=spec.pivot,
                    asset_scale=spec.scale,
                ),
                destination_px=cache.blit_position(
                    mask_id,
                    camera.zoom,
                    project_screen(position, camera),
                ),
                multiplier=multiplier,
            )
            for position, multiplier in (
                ((31, 33), (1.08, 1.08, 1.04)),
                ((32, 33), (0.65, 0.68, 0.78)),
            )
        )
        arguments = dict(
            mask_surface=mask,
            ripple_texture=cache.rgb(catalog.water["ripple"]),
            normal_texture=cache.rgb(catalog.water["normal"]),
            framebuffer_size=camera.viewport,
            tile_width_px=128.0,
            render_scale=camera.zoom,
            time_seconds=1.25,
            material=catalog.water,
        )
        together = render_water_batch(supports=supports, **arguments)
        split_batches = tuple(
            render_water_batch(supports=(support,), **arguments)
            for support in supports
        )
        for index, (combined, split_batch) in enumerate(
            zip(together.surfaces, split_batches, strict=True)
        ):
            separate = split_batch.surfaces[0]
            assert np.array_equal(
                pygame.surfarray.array3d(combined),
                pygame.surfarray.array3d(separate),
            )
            assert np.array_equal(
                pygame.surfarray.array_alpha(combined),
                pygame.surfarray.array_alpha(separate),
            )
            assert together.destinations[index] == split_batch.destinations[0]
        width, height = mask.get_size()
        assert together.destination_bounds == (
            min(row.destination_px[0] for row in supports),
            min(row.destination_px[1] for row in supports),
            max(row.destination_px[0] + width for row in supports),
            max(row.destination_px[1] + height for row in supports),
        )
    finally:
        pygame.quit()


def test_cropped_water_surfaces_preserve_full_mask_composition_at_all_zooms() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        catalog = load_catalog()
        cache = SurfaceCache(catalog)
        mask_id = catalog.water["mask"]
        spec = catalog.resources[mask_id]
        for zoom in ZOOM_LEVELS:
            camera = Camera(
                zoom=zoom,
                viewport=(720, 480),
            ).with_focus((31.5, 33.0))
            mask = cache.scaled(mask_id, zoom)
            supports = tuple(
                WaterSupportInput(
                    source_origin_px=water_source_origin(
                        position,
                        pivot=spec.pivot,
                        asset_scale=spec.scale,
                    ),
                    destination_px=cache.blit_position(
                        mask_id,
                        zoom,
                        project_screen(position, camera),
                    ),
                    multiplier=multiplier,
                )
                for position, multiplier in (
                    ((31, 33), (1.08, 1.08, 1.04)),
                    ((32, 33), (0.38, 0.40, 0.46)),
                )
            )
            for time_seconds in (0.2, 1.25):
                batch = render_water_batch(
                    mask_surface=mask,
                    ripple_texture=cache.rgb(catalog.water["ripple"]),
                    normal_texture=cache.rgb(catalog.water["normal"]),
                    supports=supports,
                    framebuffer_size=camera.viewport,
                    tile_width_px=128.0,
                    render_scale=zoom,
                    time_seconds=time_seconds,
                    material=catalog.water,
                )
                for support, cropped, destination in zip(
                    supports,
                    batch.surfaces,
                    batch.destinations,
                    strict=True,
                ):
                    offset = (
                        destination[0] - support.destination_px[0],
                        destination[1] - support.destination_px[1],
                    )
                    full = pygame.Surface(
                        mask.get_size(), pygame.SRCALPHA, 32
                    ).convert_alpha()
                    full.blit(cropped, offset)
                    direct = pygame.Surface(camera.viewport, pygame.SRCALPHA, 32).convert_alpha()
                    restored = pygame.Surface(camera.viewport, pygame.SRCALPHA, 32).convert_alpha()
                    direct.blit(
                        cropped,
                        destination,
                        special_flags=pygame.BLEND_PREMULTIPLIED,
                    )
                    restored.blit(
                        full,
                        support.destination_px,
                        special_flags=pygame.BLEND_PREMULTIPLIED,
                    )
                    assert np.array_equal(
                        pygame.surfarray.array3d(direct),
                        pygame.surfarray.array3d(restored),
                    )
                    assert np.array_equal(
                        pygame.surfarray.array_alpha(direct),
                        pygame.surfarray.array_alpha(restored),
                    )
    finally:
        pygame.quit()


def test_water_output_matches_frozen_pre_repair_full_raster_digests() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        catalog = load_catalog()
        cache = SurfaceCache(catalog)
        mask_id = catalog.water["mask"]
        spec = catalog.resources[mask_id]
        representatives = (
            ((34, 31), (1.08, 1.08, 1.04)),
            ((41, 35), (0.38, 0.40, 0.46)),
        )
        for zoom in ZOOM_LEVELS:
            camera = Camera(
                quadrant=0,
                zoom=zoom,
                viewport=(1280, 720),
            ).with_focus((31, 31))
            mask = cache.scaled(mask_id, zoom)
            for representative_index, (position, multiplier) in enumerate(
                representatives
            ):
                support = WaterSupportInput(
                    source_origin_px=water_source_origin(
                        position,
                        pivot=spec.pivot,
                        asset_scale=spec.scale,
                    ),
                    destination_px=cache.blit_position(
                        mask_id,
                        zoom,
                        project_screen(position, camera),
                    ),
                    multiplier=multiplier,
                )
                size, expected_destination, *expected_digests = (
                    PRE_REPAIR_WATER_DIGESTS[zoom][representative_index]
                )
                assert mask.get_size() == size
                assert support.destination_px == expected_destination
                for time_seconds, expected_digest in zip(
                    (0.2, 1.25), expected_digests, strict=True
                ):
                    batch = render_water_batch(
                        mask_surface=mask,
                        ripple_texture=cache.rgb(catalog.water["ripple"]),
                        normal_texture=cache.rgb(catalog.water["normal"]),
                        supports=(support,),
                        framebuffer_size=camera.viewport,
                        tile_width_px=128.0,
                        render_scale=zoom,
                        time_seconds=time_seconds,
                        material=catalog.water,
                    )
                    assert batch.destination_bounds == (
                        expected_destination[0],
                        expected_destination[1],
                        expected_destination[0] + size[0],
                        expected_destination[1] + size[1],
                    )
                    cropped = batch.surfaces[0]
                    offset = (
                        batch.destinations[0][0] - expected_destination[0],
                        batch.destinations[0][1] - expected_destination[1],
                    )
                    restored = np.zeros((*size, 4), dtype=np.uint8)
                    width, height = cropped.get_size()
                    crop = (
                        slice(offset[0], offset[0] + width),
                        slice(offset[1], offset[1] + height),
                    )
                    restored[*crop, :3] = pygame.surfarray.array3d(cropped)
                    restored[*crop, 3] = pygame.surfarray.array_alpha(cropped)
                    assert hashlib.sha256(restored.tobytes(order="C")).hexdigest() == (
                        expected_digest
                    )
    finally:
        pygame.quit()


def test_zoom_preserves_world_sample_and_view_or_height_cannot_shift_origin() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        catalog = load_catalog()
        cache = SurfaceCache(catalog)
        ripple = pygame.surfarray.array3d(cache.canonical["water.ripple"])
        normal = pygame.surfarray.array3d(cache.canonical["water.normal"])
        position = (31, 33)
        origin = water_source_origin(
            position,
            pivot=(128.0, 64.0),
            asset_scale=1.0,
        )
        assert origin == (-256.0, 1984.0)
        common = dict(
            mask_alpha=np.ones(1, dtype=np.float32),
            source_origins_px=np.asarray([origin], dtype=np.float32),
            global_framebuffer_pixels=np.asarray([[320, 180]], dtype=np.float32),
            framebuffer_size=(640, 360),
            tile_width_px=128,
            time_seconds=0.7,
            ripple_texture=ripple,
            normal_texture=normal,
            material=catalog.water,
        )
        half_zoom = shade_water_packed(
            input_pixels=np.asarray([[10, 14]], dtype=np.float32),
            render_scale=0.5,
            **common,
        )
        full_zoom = shade_water_packed(
            input_pixels=np.asarray([[20, 28]], dtype=np.float32),
            render_scale=1.0,
            **common,
        )
        assert np.array_equal(half_zoom, full_zoom)
    finally:
        pygame.quit()
