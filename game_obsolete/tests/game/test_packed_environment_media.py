"""Page storage preserves registered environment color, depth and loose resources."""

from dataclasses import replace
import json
from pathlib import Path
from uuid import UUID

import numpy as np
import pygame
import pytest

from game.asset_types import image_resources
from game.assets import SurfaceCache, load_catalog
from game.draw_commands import DrawCommand
from game.environment_art import environment_art_from_document
from game.environment_draw import environment_command, environment_depth_sample
from game.fixture_depth import split_actor_fixtures
from game.projection import Camera, ZOOM_LEVELS


@pytest.fixture(scope="module")
def display():
    pygame.init()
    yield pygame.display.set_mode((500, 400))
    pygame.quit()


def pack_cells(sheet, cell, poses, count, output, name):
    """A small independent test packer deliberately rearranges the source cells."""
    width, height = cell
    capacity, columns = 16, 4
    addresses = {pose: [] for pose in poses}
    pages = {}
    for row, pose in enumerate(poses):
        for frame in range(count):
            index = row * count + frame
            page_index, slot = divmod(index, capacity)
            slot = capacity - 1 - slot
            path = f"{name}-{page_index}.png"
            if path not in pages:
                pages[path] = pygame.Surface((columns * (width + 2), 4 * (height + 3)), pygame.SRCALPHA)
            left, top = (slot % columns) * (width + 2), (slot // columns) * (height + 3)
            pages[path].blit(sheet, (left, top), (frame * width, row * height, width, height))
            addresses[pose].append({"path": path, "rect": [left, top, width, height]})
    for path, page in pages.items():
        pygame.image.save(page, output / path)
    return addresses


def banks_from_row(row, output):
    source = {"version": 1, "banks": {"bank": row}, "doors": {}, "traps": {}, "wrecks": {}}
    return environment_art_from_document(source, output).banks["bank"]


def paired_banks(row, source_root, output):
    if "path" not in row:
        # Retain this comparison after production selects pages: reconstruct the
        # old strip layout from the selected genuine pixels, only inside this test.
        pages = {}
        def strip(addresses, cell, count, name):
            image = pygame.Surface((cell[0] * count, cell[1] * len(row["rows"])), pygame.SRCALPHA)
            for row_index, pose in enumerate(row["rows"]):
                for frame, address in enumerate(addresses[pose]):
                    path = source_root / address["path"]
                    if path not in pages:
                        pages[path] = pygame.image.load(path).convert_alpha()
                    image.blit(pages[path], (frame * cell[0], row_index * cell[1]), address["rect"])
            pygame.image.save(image, output / name)
            return name
        legacy = {key: value for key, value in row.items()
                  if key not in ("frames_by_pose", "depth_frames_by_pose", "frame_regions_by_pose")}
        legacy["path"] = strip(row["frames_by_pose"], row["cell"], row["frame_count"], "restored-color.png")
        legacy["actor_depth"] = {**row["actor_depth"], "path": strip(row["depth_frames_by_pose"],
            row["actor_depth"]["cell"], row["frame_count"], "restored-depth.png")}
        if "frame_regions_by_pose" in row:
            legacy["frame_path"] = strip({pose: [address] for pose, address in row["frame_regions_by_pose"].items()},
                                         row["cell"], 1, "restored-static.png")
        row, source_root = legacy, output
    old = banks_from_row(row, source_root)
    sheet = pygame.image.load(source_root / row["path"]).convert_alpha()
    depth = pygame.image.load(source_root / row["actor_depth"]["path"]).convert_alpha()
    packed = {**row, "frames_by_pose": pack_cells(sheet, row["cell"], row["rows"], row["frame_count"], output, "color"),
              "depth_frames_by_pose": pack_cells(depth, row["actor_depth"]["cell"], row["rows"], row["frame_count"], output, "depth"),
              "actor_depth": {key: value for key, value in row["actor_depth"].items() if key != "path"}}
    del packed["path"]
    if "frame_path" in row:
        static = pygame.image.load(source_root / row["frame_path"]).convert_alpha()
        frames = pack_cells(static, row["cell"], row["rows"], 1, output, "static")
        packed["frame_regions_by_pose"] = {pose: regions[0] for pose, regions in frames.items()}
        del packed["frame_path"]
    return old, banks_from_row(packed, output)


@pytest.fixture(scope="module")
def tiny_banks(display, tmp_path_factory):
    output = tmp_path_factory.mktemp("packed-environment")
    cell, depth_cell, poses, count = (12, 16), (6, 8), ["e", "s", "w", "n"], 3
    color = pygame.Surface((cell[0] * count, cell[1] * 4), pygame.SRCALPHA)
    depth = pygame.Surface((depth_cell[0] * count, depth_cell[1] * 4), pygame.SRCALPHA)
    for row in range(4):
        for frame in range(count):
            for x in range(cell[0]):
                for y in range(cell[1]):
                    color.set_at((frame * cell[0] + x, row * cell[1] + y),
                                 (25 + row * 50, 35 + frame * 80, 20 + x * 13, 128 if y % 2 else 255))
            for x in range(depth_cell[0]):
                for y in range(depth_cell[1]):
                    encoded = 1 + x * 8000 + y * 1000 + row * 1000 + frame * 100
                    depth.set_at((frame * depth_cell[0] + x, row * depth_cell[1] + y),
                                 (encoded % 256, encoded // 256, 0, 255))
    pygame.image.save(color, output / "wide.png")
    pygame.image.save(depth, output / "wide-depth.png")
    row = {"path": "wide.png", "frame_path": "wide.png", "cell": cell, "ground_pivot": [6, 14],
           "pivots_by_pose": {pose: [6, 14] for pose in poses}, "rows": poses, "scale": 2,
           "frame_count": count, "fps": 12, "duration_ms": 250,
           "actor_depth": {"path": "wide-depth.png", "cell": depth_cell, "depth_range": [-4, 4],
                           "pixels_per_unit_by_pose": {pose: 8 for pose in poses}}}
    return paired_banks(row, output, output)


def pictures(bank, pose, camera, frame, *, frame_only=False):
    command = environment_command(bank, frame, identity=UUID(int=1), position=(0, 0), elevation=0,
        pose=pose, boundary_pose=None, camera=camera, multiplier=(.8, .9, 1), frame_only=frame_only)
    sample = environment_depth_sample(command, 0, bank, pose, frame, camera, position=(0, 0))
    assert sample is not None
    peer = pygame.Surface(command.surface.get_size(), pygame.SRCALPHA)
    peer.fill((180, 40, 230, 255))
    peer_command = DrawCommand((command.key[0], command.key[1] + 1, *command.key[2:]), peer,
                               command.destination, 0, ())
    pieces = split_actor_fixtures([command, peer_command], [sample])
    canvas = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    for part in sorted(pieces, key=lambda part: part.key):
        canvas.blit(part.surface, part.destination)
    return command, pygame.image.tobytes(canvas, "RGBA")


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("zoom", ZOOM_LEVELS)
def test_packed_color_and_independent_depth_cells_preserve_four_views_and_all_zooms(tiny_banks, quadrant, zoom):
    old, packed = tiny_banks
    camera = Camera(quadrant=quadrant, zoom=zoom, viewport=(500, 400)).with_focus((0, 0))
    pose = old.rows[quadrant]
    for frame in (0, 1, 2):
        before, before_scene = pictures(old, pose, camera, frame)
        after, after_scene = pictures(packed, pose, camera, frame)
        assert after.destination == before.destination
        assert pygame.image.tobytes(after.surface, "RGBA") == pygame.image.tobytes(before.surface, "RGBA")
        assert after_scene == before_scene, "Depth partitioning must stay registered after page packing."
    before, _ = pictures(old, pose, camera, 0, frame_only=True)
    after, _ = pictures(packed, pose, camera, 0, frame_only=True)
    assert pygame.image.tobytes(after.surface, "RGBA") == pygame.image.tobytes(before.surface, "RGBA")


def test_genuine_nonuniform_door_bank_preserves_sampled_color_depth_and_frame_only(display, tmp_path):
    root = Path(__file__).resolve().parents[2] / "game"
    document = json.loads((root / "data/environment_art.json").read_text())
    row = document["banks"]["door.indoor-door-shabby.inward"]
    old, packed = paired_banks(row, root / "assets", tmp_path)
    assert packed.frame_times_ms == old.frame_times_ms
    for quadrant, pose in enumerate(old.rows):
        camera = Camera(quadrant=quadrant, zoom=.75, viewport=(500, 400)).with_focus((0, 0))
        for frame in (0, 12, 23):
            before, before_scene = pictures(old, pose, camera, frame)
            after, after_scene = pictures(packed, pose, camera, frame)
            assert after.destination == before.destination
            assert pygame.image.tobytes(after.surface, "RGBA") == pygame.image.tobytes(before.surface, "RGBA")
            assert after_scene == before_scene
        before, _ = pictures(old, pose, camera, 0, frame_only=True)
        after, _ = pictures(packed, pose, camera, 0, frame_only=True)
        assert pygame.image.tobytes(after.surface, "RGBA") == pygame.image.tobytes(before.surface, "RGBA")


def test_loose_regions_share_one_page_decode_and_keep_unscaled_registration(display, tmp_path, monkeypatch):
    page = pygame.Surface((40, 30), pygame.SRCALPHA)
    page.fill((200, 30, 40, 255), (2, 3, 12, 16))
    page.fill((20, 150, 90, 128), (20, 5, 12, 16))
    pygame.image.save(page, tmp_path / "page.png")
    resources = image_resources({identity: {"path": "page.png", "rect": rect,
        "native_size": [12, 16], "pivot": [6, 14], "scale": .75}
        for identity, rect in (("a", [2, 3, 12, 16]), ("b", [20, 5, 12, 16]))}, tmp_path)
    cache = SurfaceCache(replace(load_catalog(), resources=resources))
    load, reads = pygame.image.load, []
    def tracked(path):
        reads.append(path)
        return load(path)
    monkeypatch.setattr(pygame.image, "load", tracked)
    for zoom in ZOOM_LEVELS:
        for identity in resources:
            assert cache.scaled(identity, zoom).get_size() == (max(1, round(12 * .75 * zoom)), max(1, round(16 * .75 * zoom)))
            assert cache.blit_position(identity, zoom, (100, 100)) == (round(100 - 6 * .75 * zoom), round(100 - 14 * .75 * zoom))
    assert len(reads) == 1
    assert cache.canonical("a").get_at((0, 0)) == (200, 30, 40, 255)
    assert cache.canonical("b").get_at((0, 0)) == (20, 150, 90, 128)
