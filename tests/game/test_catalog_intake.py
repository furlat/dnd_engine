"""Authored catalog intake rejects unusable metadata and preserves explicit timing."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from game.asset_types import image_resources
from game.assets import catalog_from_documents
from game.condition_media import load_condition_media
from game.device_art import DeviceDocument
from game.environment_art import environment_art_from_document, sample_environment_frame
from game.portal_art import PortalDocument
from game.world_animation import prop_animation


DATA = Path(__file__).resolve().parents[2] / "game/data"


def environment_document(bank):
    return {"version": 1, "banks": {"door": bank}, "doors": {}, "traps": {}, "wrecks": {}}


def test_explicit_environment_sample_times_and_static_banks_need_no_invented_fps(tmp_path):
    bank = {"path": "door.png", "cell": [16, 32], "ground_pivot": [8, 28],
            "pivots_by_pose": {"e": [8, 28]}, "rows": ["e"], "scale": .75,
            "frame_count": 3, "sample_times_ms": [0, 80, 260], "duration_ms": 400,
            "state_change_frame": 2}
    art = environment_art_from_document(environment_document(bank), tmp_path).banks["door"]
    assert [sample_environment_frame(art, at) for at in (0, 79, 80, 259, 260, 800)] == [0, 0, 1, 1, 2, 2]
    assert art.ground_origins_by_pose == {"e": (8, 28)}
    assert art.scale == .75 and art.state_change_frame == 2
    static = {**bank, "frame_count": 1, "sample_times_ms": [0], "duration_ms": 0,
              "state_change_frame": 0}
    assert environment_art_from_document(environment_document(static), tmp_path).banks["door"].duration_ms == 0
    with pytest.raises(ValidationError, match="sample times must be ordered"):
        environment_art_from_document(environment_document({**bank, "sample_times_ms": [0, 80, 70]}), tmp_path)


def test_environment_uniform_timing_remains_the_explicit_fps_fallback(tmp_path):
    bank = {"path": "door.png", "cell": [16, 32], "ground_pivot": [8, 28],
            "pivots_by_pose": {"e": [8, 28]}, "rows": ["e"], "scale": .75,
            "frame_count": 3, "fps": 5, "duration_ms": 600}
    art = environment_art_from_document(environment_document(bank), tmp_path).banks["door"]
    assert art.frame_times_ms == (0, 200, 400)
    assert art.state_change_frame == 0


@pytest.mark.parametrize("change", ({"native_size": [0, 32]}, {"pivot": [8]}, {"scale": float("nan")}))
def test_image_registration_rejects_unusable_geometry_without_opening_rasters(tmp_path, change):
    row = {"path": "absent.png", "native_size": [16, 32], "pivot": [8, 28], "scale": .75}
    spec = image_resources({"body": row}, tmp_path)["body"]
    assert spec.path == tmp_path / "absent.png"
    assert (spec.native_size, spec.pivot, spec.scale) == ((16, 32), (8, 28), .75)
    with pytest.raises(ValidationError):
        image_resources({"body": {**row, **change}}, tmp_path)


def test_prop_transition_markers_must_index_every_authored_pose():
    row = {"frames_by_pose": {"e": ["a", "b"], "s": ["c", "d"]}, "fps": 10,
           "state_frames": {"false": 0, "true": 1}, "transition_frames": {"false:true": [0, 1]}}
    animation = prop_animation(row)
    assert animation.transition_frames == {"false:true": (0, 1)}
    assert animation.placement == "cell" and animation.origin_offset == (0, 0)
    with pytest.raises(ValidationError, match="frame markers"):
        prop_animation({**row, "contact_frame": 2})


def test_condition_media_keeps_authored_lifecycle_and_checks_fade_order(tmp_path):
    source = tmp_path / "conditions.json"
    resources = tmp_path / "resources.json"
    resources.write_text(json.dumps({"resources": {}}))
    layer = {"category": "sleep", "animation": "static", "asset_id": "sleep.loop",
             "scale": .37, "world_basis": "SE", "application_fade_ms": [200, 700],
             "sustain_start_ms": 125, "removal_fade_ms": 240}
    document = {"schema": "dnd.conditionLayerMedia", "version": 1, "layers": {"sleep": layer}}
    source.write_text(json.dumps(document))
    media = load_condition_media(source, resources, tmp_path)["sleep"]
    assert (media.scale, media.world_basis, media.application_fade_ms) == (.37, "SE", (200, 700))
    assert (media.sustain_start_ms, media.removal_fade_ms) == (125, 240)
    layer["application_fade_ms"] = [700, 200]
    source.write_text(json.dumps(document))
    with pytest.raises(ValidationError, match="fade end"):
        load_condition_media(source, resources, tmp_path)


def test_device_release_contacts_must_exist_in_the_registered_bank():
    document = json.loads((DATA / "spell_devices.json").read_text())
    row = next(iter(document["devices"].values()))
    row["releaseFrame"] = row["frameCount"]
    with pytest.raises(ValidationError, match="releaseFrame"):
        DeviceDocument.model_validate(document)


def test_portal_finite_markers_must_fit_the_camera_pages():
    document = json.loads((DATA / "portals.json").read_text())
    bank = next(iter(document["banks"].values()))
    bank["pages"][0] = []
    with pytest.raises(ValidationError, match="portal pages"):
        PortalDocument.model_validate(document)


def test_world_catalog_checks_the_active_material_and_prop_shapes():
    assets = json.loads((DATA / "assets.json").read_text())
    bindings = json.loads((DATA / "world_bindings.json").read_text())
    assets["water"]["normalPanA"] = [0, 0, 0]
    with pytest.raises(ValidationError, match="normalPanA"):
        catalog_from_documents(assets, bindings)
    assets["water"]["normalPanA"] = [0, 0]
    prop = next(iter(bindings["props"].values()))
    prop["state_field"] = "renderer_invents_state"
    with pytest.raises(ValidationError, match="state_field"):
        catalog_from_documents(assets, bindings)
