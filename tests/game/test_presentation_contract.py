"""Portable JSON examples exercise existing projection, clocks and registration."""

from dataclasses import replace
import gzip
import json
from pathlib import Path
import struct

import numpy as np
import pygame
import pytest

from game.animation import body_frame, finite_media_end, media_track_duration, media_track_frame, view_facing
from game.animation_data import load_animation_data
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage, StudioMediaTrack
from game.projection import project_world
from game.registered_media import registered_media_samples


VALUES = json.loads((Path(__file__).parent / "fixtures/presentation-values.json").read_text())


@pytest.fixture(scope="module")
def contract_data(tmp_path_factory):
    data = load_animation_data(authored_bundles=())
    asset = AuthoredProjectileAsset.model_validate_json(json.dumps(VALUES["asset"]))
    packet = VALUES["packet"]
    root = tmp_path_factory.mktemp("presentation-contract")
    payload = struct.pack("<HHhh", packet["width"], packet["height"], *packet["offset"])
    payload += np.array(packet["rgbaRows"], dtype=np.uint8).tobytes()
    payload += np.array(packet["xyzRows"], dtype=">u2").tobytes()
    payload += np.array(packet["ownerRows"], dtype=np.uint8).tobytes()
    (root / "sample.gz").write_bytes(gzip.compress(payload))
    storage = ProjectileStorage.model_validate_json(json.dumps({"phases": {"impact": {"surfaceFrames": {
        "pattern": "sample.gz", "frameIndices": [0, 0, 0, 0], "bounds": packet["bounds"],
        "verticalScale": 1, "positionScale": packet["positionScale"], "blendModes": ["normal"]}}}}))
    with pytest.MonkeyPatch.context() as env:
        env.setenv("SDL_VIDEODRIVER", "dummy"); env.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init(); pygame.display.set_mode((8, 8))
        yield replace(data, media_root=root, projectile_assets={asset.assetId: asset},
                      projectile_storage={asset.assetId: storage})
        pygame.quit()


@pytest.mark.parametrize("quadrant", range(4))
def test_portable_camera_projection_and_bank_values(contract_data, quadrant):
    row = VALUES["projection"]
    assert project_world(tuple(row["grid"]), elevation_steps=row["heightSteps"], quadrant=quadrant) == tuple(
        row["expectedByQuadrant"][quadrant])
    row = VALUES["facing"]
    assert view_facing(row["world"], quadrant, contract_data) == row["expectedByQuadrant"][quadrant]


def test_portable_source_frame_and_finite_join_values(contract_data):
    uniform = VALUES["uniformFrames"]
    for sample in uniform["samples"]:
        for loop, field in ((True, "loop"), (False, "finite")):
            assert body_frame(sample["ms"], uniform["fps"], uniform["count"], loop=loop) == sample[field]
    track = StudioMediaTrack.model_validate_json(json.dumps(VALUES["mappedTrack"]))
    assert media_track_duration(contract_data, track) == 500
    for sample in VALUES["mappedSamples"]:
        for facing in ("E", "N"):
            assert media_track_frame(contract_data, track, sample["ms"], facing) == sample[facing]
    join = VALUES["finiteJoin"]
    tracks = tuple(StudioMediaTrack.model_validate_json(json.dumps(row)) for row in join["tracks"])
    assert finite_media_end(contract_data, tracks, join["releaseMs"]) == join["expectedMs"]


@pytest.mark.parametrize("sample", VALUES["registeredSamples"])
def test_portable_crop_rounding_and_paired_nearest_samples(contract_data, sample):
    registered, = registered_media_samples(contract_data, "contract.sample", "impact", 0, "E",
        scale=sample["scale"], zoom=sample["zoom"], anchor=tuple(sample["anchor"]), rows={})
    assert registered.destination == tuple(sample["destination"])
    assert registered.image.get_size() == (len(sample["xIndices"]), len(sample["yIndices"]))
    packet = VALUES["packet"]
    assert registered.positions is not None and registered.ownership is not None
    for x, source_x in enumerate(sample["xIndices"]):
        for y, source_y in enumerate(sample["yIndices"]):
            assert tuple(registered.image.get_at((x, y))) == tuple(packet["rgbaRows"][source_y][source_x])
            assert registered.ownership[x, y] == packet["ownerRows"][source_y][source_x]
            np.testing.assert_allclose(registered.positions[x, y],
                np.array(packet["decodedRows"][source_y][source_x]) * sample["worldScale"], atol=2e-7)


@pytest.mark.parametrize("case", VALUES["nearestAxisCases"])
def test_portable_nearest_ties_match_color_xyz_and_ownership(contract_data, tmp_path, case):
    width = case["source"]
    asset = contract_data.projectile_assets["contract.sample"]
    asset = asset.model_copy(update={"frame": asset.frame.model_copy(update={"width": width, "height": width})})
    header = struct.pack("<HHhh", width, width, -round(width / 2), -round(width / 2))
    rgba = bytes(component for _ in range(width) for i in range(width) for component in (i, i, i, 255))
    xyz = np.array([[(i * 1000, i * 1000, i * 1000) for i in range(width)]] * width, dtype=">u2")
    owners = bytes(range(1, width + 1)) * width
    (tmp_path / "sample.gz").write_bytes(gzip.compress(header + rgba + xyz.tobytes() + owners))
    data = replace(contract_data, media_root=tmp_path, projectile_assets={asset.assetId: asset})
    scale = case["output"] / width
    sample, = registered_media_samples(data, asset.assetId, "impact", 0, "E",
        scale=scale, zoom=scale, anchor=(round(width / 2) * scale,) * 2, rows={})
    assert sample.image.width == case["output"]
    assert sample.positions is not None and sample.ownership is not None
    for x, expected in enumerate(case["indices"]):
        assert sample.image.get_at((x, 0)).r == expected
        assert sample.ownership[x, 0] == expected + 1
        np.testing.assert_allclose(sample.positions[x, 0], -1 + expected * 2000 / 65535, atol=2e-7)
