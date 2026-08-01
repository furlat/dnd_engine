"""Typed geometry queries over one immutable session-subjective world."""

from __future__ import annotations

from enum import Enum
from hashlib import sha256
import json
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai.knowledge.topology import (
    KnownLineOfSightWorkspace,
    grid_distance_feet,
    known_line_of_sight,
)
from dnd.ai.contracts.observation import KnowledgeState, SubjectiveWorldState
from dnd.ai.contracts.control import ActionAffordance, ActionTarget
from dnd.ai.contracts.semantics import TruthValue
from dnd.core.geometry import supercover_line


Position = Tuple[int, int]


class GeometryOperation(str, Enum):
    """Supported read-only subjective geometry operations."""

    DISTANCE = "distance"
    LINE_OF_SIGHT = "line_of_sight"
    ROW_ROUTE = "row_route"


class GeometryResultKind(str, Enum):
    """Authority class of one geometry result."""

    KNOWN_DISTANCE = "known_distance"
    KNOWN_TOPOLOGY_RAYCAST = "known_topology_raycast"
    AUTHORITATIVE_ROW_ROUTE = "authoritative_row_route"


class GeometryQuery(BaseModel):
    """One bounded local geometry query against an exact world revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: GeometryOperation = Field(description="Geometry operation to evaluate.")
    origin: Optional[Position] = Field(
        default=None,
        description="Known origin for distance or line-of-sight evaluation.",
    )
    target: Optional[Position] = Field(
        default=None,
        description="Known target for distance or line-of-sight evaluation.",
    )
    row_id: Optional[str] = Field(
        default=None,
        description="Current epoch row whose disclosed route is requested.",
    )
    target_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Engine target index selecting one route-bearing row target.",
    )
    prefer_safe: bool = Field(
        default=True,
        description="Prefer a disclosed safe route when the row supplies one.",
    )

    @model_validator(mode="after")
    def validate_operation_arguments(self) -> "GeometryQuery":
        """Require exactly the inputs used by the selected operation."""
        if self.operation in {GeometryOperation.DISTANCE, GeometryOperation.LINE_OF_SIGHT}:
            if self.origin is None or self.target is None:
                raise ValueError(f"{self.operation.value} requires origin and target")
            if self.row_id is not None or self.target_index is not None:
                raise ValueError(f"{self.operation.value} does not accept row selectors")
        elif self.operation is GeometryOperation.ROW_ROUTE:
            if self.row_id is None:
                raise ValueError("row_route requires row_id")
            if self.origin is not None or self.target is not None:
                raise ValueError("row_route does not accept explicit origin or target")
        return self


class GeometryResult(BaseModel):
    """Auditable result produced only from one session-subjective revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: GeometryOperation = Field(description="Evaluated operation.")
    result_kind: GeometryResultKind = Field(description="Authority class of the result.")
    truth: TruthValue = Field(description="Three-valued answer supported by known information.")
    positions: Tuple[Position, ...] = Field(
        default_factory=tuple,
        description="Ordered line or route positions used by the result.",
    )
    distance_feet: Optional[int] = Field(
        default=None,
        ge=0,
        description="Known geometric distance in feet.",
    )
    path_cost_feet: Optional[int] = Field(
        default=None,
        ge=0,
        description="Server-disclosed route cost in feet.",
    )
    unknown_positions: Tuple[Position, ...] = Field(
        default_factory=tuple,
        description="Touched positions lacking a currently visible subjective tile fact.",
    )
    known_hazard_positions: Tuple[Position, ...] = Field(
        default_factory=tuple,
        description="Touched positions subjectively known to be hazardous.",
    )
    known_slow_positions: Tuple[Position, ...] = Field(
        default_factory=tuple,
        description="Touched positions subjectively known to cost more than five feet.",
    )
    opportunity_reactor_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Visible reactors disclosed by the selected route witness.",
    )
    topology_digest: str = Field(description="Digest of the subjective topology evaluated.")
    capability_digest: str = Field(description="Digest of actor and epoch capabilities evaluated.")
    algorithm_id: str = Field(description="Stable geometry implementation identity.")
    algorithm_version: str = Field(description="Geometry implementation version.")
    authoritative_row_id: Optional[str] = Field(
        default=None,
        description="Server-issued row supporting an authoritative route witness.",
    )
    used_safe_route: bool = Field(
        default=False,
        description="Whether the selected route came from the row's safe-path witness.",
    )
    unavailable_reason: Optional[str] = Field(
        default=None,
        description="Why the requested result could not be established.",
    )


class SubjectiveGeometry:
    """Read-only geometry workspace bound to one subjective world revision."""

    _ALGORITHM_VERSION = "1.0.0"

    def __init__(self, world: SubjectiveWorldState) -> None:
        """Build revision-local indexes and digests.

        Args:
            world: Canonical session-subjective world materialization.
        """
        self.world = world
        self.line_of_sight_workspace = KnownLineOfSightWorkspace.from_world(world)
        self.topology_digest = _topology_digest(world)
        self.capability_digest = _capability_digest(world)

    def evaluate(self, query: GeometryQuery) -> GeometryResult:
        """Evaluate one typed operation without contacting the game server."""
        if query.operation is GeometryOperation.DISTANCE:
            assert query.origin is not None and query.target is not None
            positions = tuple(supercover_line(query.origin, query.target))
            return self._result(
                query,
                result_kind=GeometryResultKind.KNOWN_DISTANCE,
                truth=TruthValue.TRUE,
                positions=positions,
                distance_feet=grid_distance_feet(query.origin, query.target),
                algorithm_id="engine.grid_distance",
            )
        if query.operation is GeometryOperation.LINE_OF_SIGHT:
            assert query.origin is not None and query.target is not None
            positions = tuple(supercover_line(query.origin, query.target))
            return self._result(
                query,
                result_kind=GeometryResultKind.KNOWN_TOPOLOGY_RAYCAST,
                truth=known_line_of_sight(
                    self.world,
                    query.origin,
                    query.target,
                    workspace=self.line_of_sight_workspace,
                ),
                positions=positions,
                distance_feet=grid_distance_feet(query.origin, query.target),
                algorithm_id="subjective.known_line_of_sight",
            )
        return self._row_route(query)

    def _row_route(self, query: GeometryQuery) -> GeometryResult:
        """Return one server-issued route witness from the current epoch."""
        epoch = self.world.current_epoch
        row = epoch.affordances.row_by_id(query.row_id or "") if epoch is not None else None
        target = _route_target(row, query.target_index)
        if row is None or target is None:
            return self._result(
                query,
                result_kind=GeometryResultKind.AUTHORITATIVE_ROW_ROUTE,
                truth=TruthValue.UNKNOWN,
                algorithm_id="server.affordance_route_witness",
                authoritative_row_id=query.row_id,
                unavailable_reason="The current epoch does not disclose a route for that row target.",
            )
        use_safe = query.prefer_safe and bool(target.safe_path)
        positions = tuple(target.safe_path if use_safe else target.path)
        if not positions:
            return self._result(
                query,
                result_kind=GeometryResultKind.AUTHORITATIVE_ROW_ROUTE,
                truth=TruthValue.UNKNOWN,
                algorithm_id="server.affordance_route_witness",
                authoritative_row_id=row.row_id,
                unavailable_reason="The selected legal row has no disclosed movement route.",
            )
        exposures = (
            target.safe_path_opportunity_attack_exposures
            if use_safe
            else target.opportunity_attack_exposures
        )
        return self._result(
            query,
            result_kind=GeometryResultKind.AUTHORITATIVE_ROW_ROUTE,
            truth=TruthValue.TRUE,
            positions=positions,
            distance_feet=target.distance,
            path_cost_feet=(target.safe_path_cost if use_safe else target.path_cost),
            opportunity_reactor_uuids=tuple(row.reactor_uuid for row in exposures),
            algorithm_id="server.affordance_route_witness",
            authoritative_row_id=row.row_id,
            used_safe_route=use_safe,
        )

    def _result(
        self,
        query: GeometryQuery,
        *,
        result_kind: GeometryResultKind,
        truth: TruthValue,
        algorithm_id: str,
        positions: Tuple[Position, ...] = tuple(),
        distance_feet: Optional[int] = None,
        path_cost_feet: Optional[int] = None,
        opportunity_reactor_uuids: Tuple[str, ...] = tuple(),
        authoritative_row_id: Optional[str] = None,
        used_safe_route: bool = False,
        unavailable_reason: Optional[str] = None,
    ) -> GeometryResult:
        """Attach shared subjective provenance to one operation result."""
        known_tiles = {tile.position: tile for tile in self.world.known_tiles.values()}
        unknown = tuple(
            position
            for position in positions
            if position not in known_tiles
            or known_tiles[position].knowledge_state is not KnowledgeState.VISIBLE
        )
        hazards = tuple(
            position
            for position in positions
            if position in known_tiles and known_tiles[position].is_hazardous is True
        )
        slow = tuple(
            position
            for position in positions
            if position in known_tiles and _is_slow(known_tiles[position].walking_cost)
        )
        return GeometryResult(
            operation=query.operation,
            result_kind=result_kind,
            truth=truth,
            positions=positions,
            distance_feet=distance_feet,
            path_cost_feet=path_cost_feet,
            unknown_positions=unknown,
            known_hazard_positions=hazards,
            known_slow_positions=slow,
            opportunity_reactor_uuids=opportunity_reactor_uuids,
            topology_digest=self.topology_digest,
            capability_digest=self.capability_digest,
            algorithm_id=algorithm_id,
            algorithm_version=self._ALGORITHM_VERSION,
            authoritative_row_id=authoritative_row_id,
            used_safe_route=used_safe_route,
            unavailable_reason=unavailable_reason,
        )


def _route_target(
    row: Optional[ActionAffordance],
    target_index: Optional[int],
) -> Optional[ActionTarget]:
    """Select one route-bearing target deterministically."""
    if row is None:
        return None
    if target_index is not None:
        return next((target for target in row.targets if target.index == target_index), None)
    return next((target for target in row.targets if target.path or target.safe_path), None)


def _is_slow(walking_cost: Optional[int]) -> bool:
    """Return whether one known movement cost exceeds a normal grid step."""
    return walking_cost is not None and walking_cost > 5


def _topology_digest(world: SubjectiveWorldState) -> str:
    """Hash only topology facts available to this subjective session."""
    payload = [
        tile.model_dump(mode="json")
        for tile in sorted(world.known_tiles.values(), key=lambda item: item.position)
    ]
    blockers = [
        item.model_dump(mode="json")
        for item in sorted(world.known_objects.values(), key=lambda item: item.uuid)
        if item.knowledge_state is KnowledgeState.VISIBLE
        and item.state.blocks_vision
    ]
    return _digest({"tiles": payload, "visible_blockers": blockers})


def _capability_digest(world: SubjectiveWorldState) -> str:
    """Hash actor, economy, capabilities, and legal-row route witnesses."""
    epoch = world.current_epoch
    if epoch is None:
        return _digest(None)
    return _digest({
        "actor_uuid": epoch.actor_uuid,
        "economy": epoch.economy.model_dump(mode="json"),
        "capabilities": [row.model_dump(mode="json") for row in epoch.affordances.capabilities],
        "routes": [
            {
                "row_id": row.row_id,
                "targets": [
                    {
                        "index": target.index,
                        "path": target.path,
                        "safe_path": target.safe_path,
                        "path_cost": target.path_cost,
                        "safe_path_cost": target.safe_path_cost,
                    }
                    for target in row.targets
                ],
            }
            for row in epoch.affordances.all_rows
        ],
    })


def _digest(value: object) -> str:
    """Return a deterministic SHA-256 digest for JSON-compatible content."""
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return sha256(raw).hexdigest()
