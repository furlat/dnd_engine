"""Generated review artifacts carry the real frames and their debugging evidence.

Boundary: catalog IDs in, playable MP4s + a manifest + retained traces out.
The second case checks a recording failure stays exportable in the gallery.
"""

import json
from pathlib import Path

import pytest

from devtools.animation_review import __main__ as review


def latest_run(output: Path) -> Path:
    return output / "runs" / json.loads((output / "latest.json").read_text())["run"]


def test_generated_clips_retain_their_frames_lineages_and_authored_maps(tmp_path: Path) -> None:
    assert review.main(["--case", "ranged-hit", "--case", "walk-paralyzed", "--case", "firebolt-level", "--fps", "12",
                        "--width", "640", "--height", "480", "--output", str(tmp_path)]) == 0
    output = latest_run(tmp_path)
    manifest = json.loads((output / "manifest.json").read_text())
    assert {case["id"] for case in manifest["cases"]} == {"ranged-hit", "walk-paralyzed", "firebolt-level"}
    assert (output / "index.html").is_file() and (output / "gallery.js").is_file()
    for case in manifest["cases"]:
        trace = json.loads((output / case["trace"]).read_text())
        assert trace["case"]["id"] == case["id"]
        assert trace["run"] == manifest["run"]
        assert trace["sources"]["source_hash"] == manifest["run"]["source_hash"]
        assert case["status"] == "passed" and all(check["passed"] for check in case["checks"])
        assert (output / case["video"]).stat().st_size > 1000
        assert int(trace["video"]["nb_read_frames"]) == len(trace["frames"]) == case["frame_count"]
        assert (trace["video"]["width"], trace["video"]["height"]) == (1280, 960)
        assert manifest["run"]["layout"] == "four-corners-2x2"
        assert [camera["quadrant"] for camera in trace["cameras"]] == [0, 1, 2, 3]
        assert all([view["quadrant"] for view in frame["views"]] == [0, 1, 2, 3] for frame in trace["frames"])
        assert [frame["index"] for frame in trace["frames"]] == list(range(case["frame_count"]))
        assert trace["frames"][-1]["state"] == trace["latest"]
        root = trace["lineages"][0]
        assert trace["heads"][0]["root_uuid"] == root["root"]["uuid"]
        assert any(frame["root_uuid"] == root["root"]["uuid"] for frame in trace["frames"])
        assert all(child in {event["lineage_uuid"] for event in root["events"]}
                   for event in root["events"] for child in event["children_lineages"])
        if case["id"] == "walk-paralyzed":
            mover = trace["latest"]["actors"][root["root"]["source_entity_uuid"]]
            assert mover["hp"] == 73
            assert "Paralyzed" in {condition["name"] for condition in mover["conditions"]}
            assert trace["heads"][0]["composition"]["reactions"]
        elif case["id"] == "ranged-hit":
            attack = trace["heads"][0]["composition"]["nodes"][0]["timeline"]
            assert attack["release_ms"] < attack["contact_ms"]
            assert attack["projectile"] is not None
        else:
            # Fire Bolt contains FrozenMap authoring; schema serializers must
            # preserve it in the debug trace rather than fail on mappingproxy.
            cast = trace["heads"][0]["composition"]["nodes"][0]
            assert cast["primitive"] == "cast" and cast["timeline"]["recipe"]
            assert cast["timeline"]["release_ms"] < cast["timeline"]["applications"][0]["travel_end_ms"]


def test_recording_failure_remains_in_manifest_with_exportable_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable_encoder(*args, **kwargs):
        raise RuntimeError("encoder unavailable during capture")

    monkeypatch.setattr(review, "record_case", unavailable_encoder)
    assert review.main(["--case", "melee-hit", "--output", str(tmp_path)]) == 1
    output = latest_run(tmp_path)
    manifest = json.loads((output / "manifest.json").read_text())
    case, = manifest["cases"]
    assert case["id"] == "melee-hit" and case["status"] == "failed"
    assert case["video"] is None and "encoder unavailable" in case["error"]
    trace = json.loads((output / case["trace"]).read_text())
    assert "encoder unavailable" in trace["error"]
    assert trace["run"]["id"] == manifest["run"]["id"]
