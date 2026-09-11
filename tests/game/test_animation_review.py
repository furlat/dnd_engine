"""Generated review artifacts carry the real frames and their debugging evidence.

Boundary: saved gameplay bytes in, playable MP4s + a manifest + retained traces
out. Native generation is explicit and unavailable during repeat playback.
"""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from devtools.animation_review import __main__ as review


def latest_run(output: Path) -> Path:
    return output / "runs" / json.loads((output / "latest.json").read_text())["run"]


def test_generated_clips_retain_their_frames_lineages_and_authored_maps(tmp_path: Path) -> None:
    assert review.main(["--capture", "--case", "ranged-hit", "--case", "walk-paralyzed", "--case", "firebolt-level",
                        "--case", "equipment-remove-active-weapon", "--fps", "12",
                        "--width", "640", "--height", "480", "--output", str(tmp_path)]) == 0
    output = latest_run(tmp_path)
    manifest = json.loads((output / "manifest.json").read_text())
    assert {case["id"] for case in manifest["cases"]} == {
        "ranged-hit", "walk-paralyzed", "firebolt-level", "equipment-remove-active-weapon"}
    assert (output / "index.html").is_file() and (output / "gallery.js").is_file()
    for case in manifest["cases"]:
        trace = json.loads((output / case["trace"]).read_text())
        assert trace["case"]["id"] == case["id"]
        assert trace["run"] == manifest["run"]
        assert trace["sources"]["source_hash"] == manifest["run"]["source_hash"]
        assert (output / case["input"]).read_bytes() == (tmp_path / "inputs" / case["id"] / "input.json").read_bytes()
        assert trace["mode"].startswith("decoded-recorded-input")
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
        elif case["id"] == "firebolt-level":
            # Fire Bolt contains FrozenMap authoring; schema serializers must
            # preserve it in the debug trace rather than fail on mappingproxy.
            cast = trace["heads"][0]["composition"]["nodes"][0]
            assert cast["primitive"] == "cast" and cast["timeline"]["recipe"]
            assert cast["timeline"]["release_ms"] < cast["timeline"]["applications"][0]["travel_end_ms"]
        else:
            actor = trace["latest"]["observer_uuid"]
            equipment_head, = (head for head in trace["heads"] if head["composition"]["equipment"])
            cue, = equipment_head["composition"]["equipment"]
            timeline = cue["timeline"]
            assert timeline["recipe"]["bodyClip"] == "Taunt" and timeline["recipe"]["commitFrame"] == 4
            assert 0 < timeline["commit_ms"] < timeline["complete_ms"]
            held = [frame for frame in trace["frames"] if frame["root_uuid"] == equipment_head["root_uuid"]
                    and frame["elapsed_ms"] < timeline["commit_ms"]]
            committed = [frame for frame in trace["frames"] if frame["root_uuid"] == equipment_head["root_uuid"]
                         and timeline["commit_ms"] <= frame["elapsed_ms"] < timeline["complete_ms"]]
            assert held and committed
            assert all(frame["state"]["actors"][actor]["active_weapon_set"] == "melee" for frame in held)
            assert all(frame["state"]["actors"][actor]["active_weapon_set"] == "ranged" for frame in committed)
            attack, = (head for head in trace["heads"] if head["composition"]["nodes"]
                       and head["composition"]["nodes"][0]["timeline"]["projectile"] is not None)
            assert attack["before"]["actors"][actor]["active_weapon_set"] == "ranged"
            assert "MELEE_MAIN" not in dict(attack["before"]["actors"][actor]["equipment"])


def test_recording_failure_remains_in_manifest_with_exportable_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable_encoder(*args, **kwargs):
        raise RuntimeError("encoder unavailable during capture")

    monkeypatch.setattr(review, "record_case", unavailable_encoder)
    assert review.main(["--capture", "--case", "melee-hit", "--output", str(tmp_path)]) == 1
    output = latest_run(tmp_path)
    manifest = json.loads((output / "manifest.json").read_text())
    case, = manifest["cases"]
    assert case["id"] == "melee-hit" and case["status"] == "failed"
    assert case["video"] is None and "encoder unavailable" in case["error"]
    trace = json.loads((output / case["trace"]).read_text())
    assert "encoder unavailable" in trace["error"]
    assert trace["run"]["id"] == manifest["run"]["id"]


def test_four_camera_framing_keeps_the_airborne_body_below_the_header(tmp_path: Path) -> None:
    assert review.main(["--capture", "--case", "jump-midflight-continue", "--fps", "12", "--width", "640",
                        "--height", "480", "--output", str(tmp_path)]) == 0
    run = latest_run(tmp_path)
    trace = json.loads((run / "cases/jump-midflight-continue/trace.json").read_text())
    framed, = (check for check in trace["checks"] if check["name"] == "visible-bodies-in-frame")
    assert framed["passed"]
    assert any(contact["body_lift_px"] > 0 for frame in trace["frames"] for contact in frame["contacts"])
    assert len(trace["cameras"]) == 4 and len({camera["zoom"] for camera in trace["cameras"]}) == 1


def test_paused_death_pixels_remain_historical_while_latest_has_revived(tmp_path: Path) -> None:
    assert review.main(["--capture", "--case", "death-save-revival-paused", "--fps", "12", "--width", "640",
                        "--height", "480", "--output", str(tmp_path)]) == 0
    run = latest_run(tmp_path)
    trace = json.loads((run / "cases/death-save-revival-paused/trace.json").read_text())
    target, = (identity for identity in trace["latest"]["actors"] if identity != trace["latest"]["observer_uuid"])
    assert (trace["latest"]["actors"][target]["life"], trace["latest"]["actors"][target]["hp"]) == ("alive", 3)
    held = [frame for frame in trace["frames"] if frame["paused"]]
    assert len(held) > 1 and len({frame["pixel_sha256"] for frame in held}) == 1
    for frame in held:
        assert frame["state"]["actors"][target]["life"] == "dead"
        assert frame["state"]["actors"][target]["hp"] == 0
        assert frame["state"]["cursor"] < frame["latest_cursor"]
        assert frame["presentation_ms"] == held[0]["presentation_ms"]
        assert frame["contacts"] == held[0]["contacts"] and frame["views"] == held[0]["views"]
        assert [view["quadrant"] for view in frame["views"]] == [0, 1, 2, 3]
        for view in frame["views"]:
            body, = (draw["evidence"] for draw in view["draws"]
                     if draw["evidence"][0] == target and draw["evidence"][6] == "actor")
            assert body[8] == "Die" and body[9] > 0
    last = trace["frames"][-1]
    assert last["state"] == trace["latest"]
    for view in last["views"]:
        body, = (draw["evidence"] for draw in view["draws"]
                 if draw["evidence"][0] == target and draw["evidence"][6] == "actor")
        assert body[8] == "Idle"
    assert trace["gaps"] == [] and all(check["passed"] for check in trace["checks"])


def test_saved_and_exported_input_replay_without_native_generation(tmp_path: Path) -> None:
    options = ["--case", "walk-recovery", "--fps", "12", "--width", "640", "--height", "480", "--output", str(tmp_path)]
    assert review.main(["--capture", *options]) == 0
    first = latest_run(tmp_path)
    manifest = json.loads((first / "manifest.json").read_text())
    item, = manifest["cases"]
    original = json.loads((first / item["trace"]).read_text())
    input_bytes = (first / item["input"]).read_bytes()
    exported = tmp_path / "review.json"
    exported.write_text(json.dumps({
        "schema_version": 1, "kind": "dnd-animation-review", "run": manifest["run"],
        "selections": [{"case": item, "review": {"verdict": "issue", "at_ms": 1200, "notes": "Retest this frame"},
                        "trace": original, "recorded_input": json.loads(input_bytes)}],
    }))
    # A fresh receiving process has no installed content or prior engine world.
    # Tripwires on the native entry points establish that replay cannot quietly
    # regenerate a scenario. The real decoder, reducer, sampler and encoder run.
    receiving_process = """
import sys
from devtools.animation_review import __main__ as review
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.events import EventQueue

def unavailable(*args, **kwargs):
    raise AssertionError("native generation is unavailable in the replay process")

review.produce = unavailable
review.bootstrap_content_system = unavailable
if "--review" in sys.argv:
    review.load_cases = unavailable
assert not SERVER_CONTENT_SYSTEM_RUNTIME.is_installed
assert EventQueue.event_cursor() == 0
result = review.main(sys.argv[1:])
assert not SERVER_CONTENT_SYSTEM_RUNTIME.is_installed
assert EventQueue.event_cursor() == 0
raise SystemExit(result)
"""
    for args in (options, ["--review", str(exported), "--fps", "12", "--width", "640", "--height", "480",
                          "--output", str(tmp_path / "from-export")]):
        result = subprocess.run([sys.executable, "-c", receiving_process, *args],
                                cwd=review.REPO, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        replay_output = Path(args[args.index("--output") + 1])
        run = latest_run(replay_output)
        repeated = json.loads((run / item["trace"]).read_text())
        assert (run / item["input"]).read_bytes() == input_bytes
        assert repeated["input"] == original["input"]
        assert repeated["initial"] == original["initial"]
        assert repeated["lineages"] == original["lineages"]
        assert repeated["heads"] == original["heads"]
        assert repeated["latest"] == original["latest"]
        assert repeated["frames"] == original["frames"]
    assert (tmp_path / "inputs/walk-recovery/input.json").read_bytes() == input_bytes


def test_replay_requires_saved_input_and_rejects_old_diagnostic_exports(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as missing:
        review.main(["--case", "melee-hit", "--output", str(tmp_path)])
    assert missing.value.code == 2
    assert "use --capture" in capsys.readouterr().err
    exported = tmp_path / "old-review.json"
    exported.write_text(json.dumps({"kind": "dnd-animation-review", "selections": [{"case": {"id": "melee-hit"},
                                                                                  "trace": {"initial": {}, "lineages": []}}]}))
    with pytest.raises(SystemExit) as old:
        review.main(["--review", str(exported), "--output", str(tmp_path)])
    assert old.value.code == 2
    assert "old traces cannot be faithfully replayed" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()
