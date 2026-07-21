"""Live watcher transport checks for the Elo matrix evaluator."""

import json
from typing import Any

import httpx

from ai.evaluation.elo_runner import HttpMirroringEloGauntletEventStream


def test_elo_event_mirror_reuses_shared_watcher_with_explicit_event_family() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"events": [], "count": 1, "total": 1, "next_cursor": 1})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://testserver",
    )
    stream = HttpMirroringEloGauntletEventStream("http://testserver", client=client)

    event = stream.append(
        event_type="ELO_MATCH_COMPLETED",
        matrix_id="matrix-1",
        match_id="matrix-1-0001",
        match_index=1,
        status="encounter_ended",
        payload={"outcome": "heroes", "eligible": True},
    )

    mirrored = requests[0]["events"][0]
    assert event.cursor == 1
    assert stream.since(0) == [event]
    assert mirrored["event_type"] == "MATCH_COMPLETED"
    assert mirrored["gauntlet_id"] == "matrix-1"
    assert mirrored["payload"]["event_family"] == "elo"
    assert mirrored["payload"]["elo_event_type"] == "ELO_MATCH_COMPLETED"
    assert mirrored["payload"]["outcome"] == "heroes"
