"""Saved attacks keep authored facing while motion changes remain presentation."""

import json
import os
import shutil

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from dnd.core.events import EventQueue
from devtools.animation_review.cases import RecordedInput, ReviewSequence, load_cases
from devtools.animation_review.record import record_case
from game.player_facts import AttackFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence
from tests.game.body_residue_scenarios import body_residue_history


def test_same_saved_attack_can_face_defender_forward_or_away_without_changing_gameplay(tmp_path):
    history = body_residue_history(hits=1, critical=True, crossings=False)
    encoded = encode_player_sequence(project_sequence(history.views["walker"]))
    cases = {case.id: case for case in load_cases()}
    traces = []
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg is not None
    for case_id in ("release-regions-piercing-critical", "weapon-dagger-rear-critical"):
        # The review pose travels with the input, while the same public gameplay
        # packet is decoded afresh. No native world or damage rerun during rendering.
        recorded = RecordedInput(case=cases[case_id], captured_at="test", sources={},
                                 sequence=json.loads(encoded), sequence_format="player-v1")
        saved = tmp_path / case_id
        saved.mkdir()
        path = saved / "input.json"
        path.write_text(recorded.model_dump_json())
        restored = RecordedInput.model_validate_json(path.read_bytes())
        sequence = ReviewSequence(*decode_player_sequence(json.dumps(restored.sequence).encode()))
        trace = {}
        result = record_case(restored.case, saved, trace, sequence=sequence,
                             fps=6, size=(400, 300), ffmpeg=ffmpeg)
        assert result["status"] == "passed"
        assert len(trace["cameras"]) == 4
        assert not trace["gaps"]
        assert EventQueue.event_cursor() == 0
        traces.append(trace)
    front, rear = traces
    assert front["initial"] == rear["initial"] and front["latest"] == rear["latest"]
    assert front["lineages"] == rear["lineages"]
    assert [frame["state"] for frame in front["frames"]] == [frame["state"] for frame in rear["frames"]]
    sequence = ReviewSequence(*decode_player_sequence(encoded))
    attack = next(root.root.fact for root in sequence.lineages if isinstance(root.root.fact, AttackFact))
    source, target = str(attack.source_entity_uuid), str(attack.target_entity_uuid)
    assert front["initial_facings"][source] != front["initial_facings"][target]
    assert rear["initial_facings"][source] == rear["initial_facings"][target]
    for trace in traces:
        assert {contact["facing"] for frame in trace["frames"] for contact in frame["contacts"]
                if contact["actor_uuid"] == target} == {trace["initial_facings"][target]}
        node = next(node for head in trace["heads"] for node in head["composition"]["nodes"]
                    if node["primitive"] == "attack")
        assert node["timeline"]["clip"] == "Attack4"
        assert node["timeline"]["profile_id"] == "dagger-critical-overhead"
    assert [(h["duration_ms"], h["video_start_ms"]) for h in front["heads"]] == [
        (h["duration_ms"], h["video_start_ms"]) for h in rear["heads"]]
