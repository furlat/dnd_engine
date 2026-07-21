"""Typed transport contracts for the task-local Codex daemon."""

from __future__ import annotations

import json

import httpx
import pytest

from ai.codex_tools.hot_runtime import (
    HotCodexGeometryRequest,
    HotCodexInspectionGetRequest,
    HotCodexReleaseView,
    HotCodexSession,
)
from ai.codex_tools.local_client import HotCodexClientError, HotCodexLocalClient
from ai.codex_tools.representation.geometry import GeometryOperation, GeometryQuery
from ai.codex_tools.representation.inspection import InspectionGetRequest
from tests.manual.test_49_hot_codex_runtime import _FakeRuntime, _door_policy_world


def test_typed_client_validates_turn_geometry_and_inspection_responses() -> None:
    """Representative local operations never expose anonymous response dictionaries."""
    session = HotCodexSession(
        runtime=_FakeRuntime(_door_policy_world()),
        claim_id="claim",
        faction="monsters",
        controlled_entity_uuids=("actor",),
    )
    turn = session.bootstrap()
    geometry_request = HotCodexGeometryRequest(
        revision=turn.revision,
        query=GeometryQuery(operation=GeometryOperation.ROW_ROUTE, row_id="move-row"),
    )
    geometry = session.geometry(geometry_request)
    inspection_request = HotCodexInspectionGetRequest(
        revision=turn.revision,
        query=InspectionGetRequest(pointers=("/world/session/session_id",)),
    )
    inspection = session.inspection_get(inspection_request)
    expected_authorization = "Bearer local-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == expected_authorization
        if request.url.path == "/v1/turn":
            return httpx.Response(200, json=turn.model_dump(mode="json"))
        payload = json.loads(request.content) if request.content else None
        if request.url.path == "/v1/geometry/query":
            assert payload == geometry_request.model_dump(mode="json")
            return httpx.Response(200, json=geometry.model_dump(mode="json"))
        if request.url.path == "/v1/inspect/get":
            assert payload == inspection_request.model_dump(mode="json")
            return httpx.Response(200, json=inspection.model_dump(mode="json"))
        if request.url.path == "/v1/release":
            return httpx.Response(200, json={
                "status": "released",
                "claim_id": "claim",
                "upstream_status": "released",
            })
        return httpx.Response(404, json={"detail": "missing"})

    with HotCodexLocalClient(
        "http://127.0.0.1:8765",
        "local-secret",
        transport=httpx.MockTransport(handler),
    ) as client:
        typed_turn = client.turn()
        typed_geometry = client.geometry(geometry_request)
        typed_inspection = client.inspection_get(inspection_request)
        typed_release = client.release()

    assert typed_turn == turn
    assert typed_geometry == geometry
    assert typed_inspection == inspection
    assert typed_geometry.result.authoritative_row_id == "move-row"
    assert typed_inspection.result.items[0].value == "session"
    assert typed_release == HotCodexReleaseView(
        status="released",
        claim_id="claim",
        upstream_status="released",
    )


def test_typed_client_preserves_structured_runtime_failures() -> None:
    """Revision and profile failures remain machine-readable at the operator boundary."""
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={
            "error": {
                "code": "stale_revision",
                "message": "Viewed revision is stale.",
            }
        })

    with HotCodexLocalClient(
        "http://127.0.0.1:8765",
        "local-secret",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(HotCodexClientError) as captured:
            client.turn()

    assert captured.value.failure.code == "stale_revision"
    assert captured.value.failure.status_code == 409
    assert captured.value.failure.message == "Viewed revision is stale."
