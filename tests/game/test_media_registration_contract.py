"""Storage changes must preserve sampled pixels, registration and authored timing."""

from dataclasses import replace
import gzip
import json
import struct
from zipfile import ZipFile, ZIP_STORED

import numpy as np
import pygame
import pytest
from pydantic import ValidationError

from game.animation import ActorContact, CastApplication, CastInput, compile_cast, sample_cast
from game.animation_data import load_animation_data
from game.animation_types import (PackedSurfaceFrames, ProjectileFrameLayer, ProjectileFrameStorage,
                                  ProjectileStorage, StudioMediaTrack, SurfaceArchive)
from game.projectile_media import ProjectileFrameCache, projectile_frame_layers
from tests.game.test_projectile_media import sample_data


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((8, 8))
    yield load_animation_data(authored_bundles=())
    pygame.quit()


def test_shared_packet_address_keeps_each_owners_registration_and_archive_member(data, tmp_path):
    data, asset, visual = sample_data(data, tmp_path)
    raw = struct.pack("<HHhh", 1, 1, -2, -3) + bytes((90, 80, 70, 255))
    raw += np.array((0, 32768, 65535), dtype=">u2").tobytes() + bytes((3,))
    encoded = gzip.compress(raw)
    (tmp_path / "sample.gz").write_bytes(encoded)
    other = raw[:8] + bytes((1, 2, 3, 255)) + raw[12:]
    with ZipFile(tmp_path / "frames.zip", "w", compression=ZIP_STORED) as archive:
        archive.writestr("E/0.gz", encoded)
        archive.writestr("E/1.gz", gzip.compress(other))
    cache = ProjectileFrameCache()
    sources = []
    for bounds, vertical, position, archived, frame in (
        ((-2., 2.), 1., 1., False, 0), ((-4., 8.), 2., .5, False, 0),
        ((-2., 2.), 1., 1., True, 0), ((-2., 2.), 1., 1., True, 1),
        ((-2., 2.), 1., 1., False, 0),
    ):
        packet = PackedSurfaceFrames(pattern=None if archived else "sample.gz",
            archive=SurfaceArchive(file="frames.zip", memberPattern="{direction}/{frame}.gz") if archived else None,
            frameIndices=tuple(range(asset.phases.impact.frames)), bounds=bounds, verticalScale=vertical,
            positionScale=position, blendModes=("normal",))
        current = replace(data, projectile_storage={asset.assetId: ProjectileStorage(
            phases={"impact": ProjectileFrameStorage(surfaceFrames=packet)})})
        image, = projectile_frame_layers(current, asset, "impact", frame, "E", visual, {}, cache=cache)
        assert image.positions is not None
        assert (image.positions.bounds, image.positions.vertical_scale, image.positions.position_scale) == (
            bounds, vertical, position)
        sources.append((pygame.image.tobytes(image.image, "RGBA"), image.offset,
                        image.positions.coordinates.tobytes(), image.positions.ownership.tobytes()))
    assert sources[0] == sources[1] == sources[2] == sources[4]
    assert sources[3][0] != sources[0][0] and sources[3][1:] == sources[0][1:]


@pytest.mark.parametrize("value", [
    {"blendMode": "normal"},
    {"blendMode": "normal", "pattern": "x", "parts": []},
    {"blendMode": "normal", "pages": {}},
    {"blendMode": "normal", "partsByFacing": {"E": []}},
])
def test_frame_layer_rejects_ambiguous_or_empty_sources_without_files(value):
    with pytest.raises(ValidationError):
        ProjectileFrameLayer.model_validate_json(json.dumps(value))


def test_phase_and_packet_sources_are_exclusive():
    with pytest.raises(ValidationError):
        ProjectileFrameStorage()
    with pytest.raises(ValidationError):
        PackedSurfaceFrames(pattern="x", archive=SurfaceArchive(file="a.zip", memberPattern="x"),
            frameIndices=(0,), bounds=(-1., 1.), verticalScale=1, blendModes=("normal",))
    with pytest.raises(ValidationError):
        PackedSurfaceFrames(pattern="x", frameIndices=(0,), bounds=(1., -1.),
                            verticalScale=1, blendModes=("normal",))
    with pytest.raises(ValidationError):
        PackedSurfaceFrames.model_validate_json(json.dumps({"pattern": "", "frameIndices": [0],
            "bounds": [-1., 1.], "verticalScale": 1, "blendModes": ["normal"]}))


def test_finite_media_tail_joins_projectile_before_recovery(data):
    caster = ActorContact("caster", (0, 0), "E", .5)
    target = ActorContact("target", (1, 0), "W", .5)
    source = CastInput("cast", caster, (CastApplication("hit", target, False, None, None),))
    original = compile_cast(data, "spell.fire_bolt", source)
    draft = original.recipe
    assert draft.projectile is not None and draft.projectile.sprite is not None
    track = StudioMediaTrack(id="finite-tail", assetId=draft.projectile.sprite.assetId,
        attachment="target_ground", durationMs=original.complete_ms + 1000)
    altered = draft.model_copy(update={"media": (track,), "cast": draft.cast.model_copy(update={
        "recovery": draft.cast.recovery.model_copy(update={"enabled": True})})})
    timeline = compile_cast(replace(data, drafts={"spell.fire_bolt": altered}), "spell.fire_bolt", source)
    assert track.durationMs is not None
    expected = timeline.release_ms + track.durationMs
    assert timeline.recovery_start_ms == pytest.approx(expected)
    assert timeline.complete_ms > expected
    assert next(body for body in sample_cast(timeline, expected).bodies if body.actor_uuid == "caster").clip == draft.cast.recovery.bodyClip
    assert original.recipe.media == ()
