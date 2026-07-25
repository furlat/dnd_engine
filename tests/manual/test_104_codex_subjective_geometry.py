"""Typed local geometry contracts for the hot Codex runtime."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from ai.codex_tools.hot_runtime import (
    HotCodexGeometryRequest,
    HotCodexSession,
    HotCodexStaleRevisionError,
    create_hot_codex_app,
)
from ai.codex_tools.representation.geometry import (
    GeometryOperation,
    GeometryQuery,
    GeometryResultKind,
)
from dnd.ai.contracts.semantics import TruthValue
from tests.manual.test_49_hot_codex_runtime import _FakeRuntime, _door_policy_world


def test_distance_and_line_of_sight_use_only_subjective_topology() -> None:
    """Local raycasts propagate unknown directional information instead of guessing."""
    session = _session()
    turn = session.bootstrap()

    distance = session.geometry(HotCodexGeometryRequest(
        revision=turn.revision,
        query=GeometryQuery(
            operation=GeometryOperation.DISTANCE,
            origin=(0, 0),
            target=(3, 0),
        ),
    ))
    line = session.geometry(HotCodexGeometryRequest(
        revision=turn.revision,
        query=GeometryQuery(
            operation=GeometryOperation.LINE_OF_SIGHT,
            origin=(0, 0),
            target=(3, 0),
        ),
    ))

    assert distance.result.result_kind is GeometryResultKind.KNOWN_DISTANCE
    assert distance.result.truth is TruthValue.TRUE
    assert distance.result.distance_feet == 15
    assert distance.result.unknown_positions == tuple()
    assert line.result.result_kind is GeometryResultKind.KNOWN_TOPOLOGY_RAYCAST
    assert line.result.truth is TruthValue.UNKNOWN
    assert line.result.topology_digest == distance.result.topology_digest
    assert line.result.capability_digest == distance.result.capability_digest


def test_row_route_returns_authoritative_epoch_witness_and_cost() -> None:
    """Movement geometry comes from the legal row rather than client pathfinding."""
    session = _session()
    turn = session.bootstrap()

    view = session.geometry(HotCodexGeometryRequest(
        revision=turn.revision,
        query=GeometryQuery(
            operation=GeometryOperation.ROW_ROUTE,
            row_id="move-row",
        ),
    ))

    assert view.result.result_kind is GeometryResultKind.AUTHORITATIVE_ROW_ROUTE
    assert view.result.truth is TruthValue.TRUE
    assert view.result.positions == ((0, 0), (1, 0), (2, 0))
    assert view.result.path_cost_feet == 10
    assert view.result.authoritative_row_id == "move-row"
    assert view.result.unknown_positions == tuple()


def test_missing_route_is_explicitly_unknown_and_revision_fenced() -> None:
    """Absent route witnesses and stale worlds never become speculative paths."""
    runtime = _FakeRuntime(_door_policy_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim",
        faction="monsters",
        controlled_entity_uuids=("actor",),
    )
    turn = session.bootstrap()
    missing = session.geometry(HotCodexGeometryRequest(
        revision=turn.revision,
        query=GeometryQuery(
            operation=GeometryOperation.ROW_ROUTE,
            row_id="missing-row",
        ),
    ))

    assert missing.result.truth is TruthValue.UNKNOWN
    assert missing.result.unavailable_reason is not None

    runtime.store.world = runtime.store.world.model_copy(update={"observation_cursor": 6})
    with pytest.raises(HotCodexStaleRevisionError):
        session.geometry(HotCodexGeometryRequest(
            revision=turn.revision,
            query=GeometryQuery(
                operation=GeometryOperation.ROW_ROUTE,
                row_id="move-row",
            ),
        ))


def test_geometry_http_route_is_typed_and_authenticated() -> None:
    """The local daemon exposes geometry without adding an upstream server read."""
    runtime = _FakeRuntime(_door_policy_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim",
        faction="monsters",
        controlled_entity_uuids=("actor",),
    )
    turn = session.bootstrap()
    app = create_hot_codex_app(session, bearer_token="token")
    request = {
        "revision": turn.revision.model_dump(mode="json"),
        "query": {"operation": "row_route", "row_id": "move-row"},
    }

    with TestClient(app) as client:
        unauthorized = client.post("/v1/geometry/query", json=request)
        response = client.post(
            "/v1/geometry/query",
            headers={"Authorization": "Bearer token"},
            json=request,
        )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json()["result"]["authoritative_row_id"] == "move-row"
    assert runtime.snapshot_fetch_calls == 1


def _session() -> HotCodexSession:
    """Build one bootstrappable runtime over a known corridor."""
    return HotCodexSession(
        runtime=_FakeRuntime(_door_policy_world()),
        claim_id="claim",
        faction="monsters",
        controlled_entity_uuids=("actor",),
    )
