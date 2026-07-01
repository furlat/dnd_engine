"""Typed HTTP client for Codex controller tools."""

from __future__ import annotations

import json
from typing import Any, Optional, Tuple

import httpx

from ai.codex_tools.contracts import (
    ActionChoice,
    ActionTargetChoice,
    ActionsResult,
    BriefEntity,
    BriefObject,
    BriefResult,
    ExecuteResult,
    ToolError,
    WatchResult,
)
from ai.observation.materializer import apply_observation_frame, materialize_snapshot
from ai.observation.models import ObservationFrame, ObservationMaterializedState


ACTION_BUCKETS = ("entity_actions", "position_actions", "self_actions", "object_actions")


class CodexToolHTTPError(RuntimeError):
    """Raised when a Codex tool HTTP request fails."""

    def __init__(self, error: ToolError) -> None:
        """Create an exception from a structured tool error."""
        super().__init__(error.message)
        self.error = error


class CodexToolClient:
    """Typed client for Codex takeover and session-control endpoints."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000") -> None:
        """Create a Codex tool client."""
        self.base_url = base_url.rstrip("/")
        timeout = httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0)
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()

    def takeover(
        self,
        *,
        faction: str = "monsters",
        entity_uuids: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        name: str = "Codex Monsters",
        force: bool = False,
        lease_seconds: float = 120.0,
    ) -> dict[str, Any]:
        """Claim combatants for Codex control."""
        payload = {
            "faction": faction,
            "entity_uuids": entity_uuids,
            "session_id": session_id,
            "name": name,
            "force": force,
            "lease_seconds": lease_seconds,
        }
        return self._request("POST", "/ai/takeover", json=payload)

    def release(self, claim_id: str) -> dict[str, Any]:
        """Release a takeover claim."""
        return self._request("POST", f"/ai/takeover/{claim_id}/release")

    def heartbeat(self, claim_id: str) -> dict[str, Any]:
        """Refresh a takeover lease."""
        return self._request("POST", f"/ai/takeover/{claim_id}/heartbeat")

    def fetch_materialized(self, session_id: str) -> ObservationMaterializedState:
        """Fetch and materialize a subjective snapshot."""
        payload = self._request("GET", f"/ai/sessions/{session_id}/observation/snapshot")
        return materialize_snapshot(payload)

    def brief(self, session_id: str) -> BriefResult:
        """Return a compact subjective brief for the Codex session."""
        materialized = self.fetch_materialized(session_id)
        return build_brief(materialized)

    def actions(
        self,
        session_id: str,
        entity_uuid: str,
        basis_cursor: Optional[int] = None,
    ) -> ActionsResult:
        """Return normalized executable action choices for one entity."""
        params = {"basis_cursor": basis_cursor} if basis_cursor is not None else None
        payload = self._request(
            "GET",
            f"/ai/sessions/{session_id}/entities/{entity_uuid}/available-actions",
            params=params,
        )
        return normalize_actions(session_id, entity_uuid, payload)

    def execute(
        self,
        session_id: str,
        entity_uuid: str,
        row_id: str,
        prefer_safe: bool = True,
    ) -> ExecuteResult:
        """Resolve and execute one CLI action row id."""
        actions = self.actions(session_id, entity_uuid)
        choice = find_choice(actions, row_id)
        if choice is None:
            return ExecuteResult(
                status="stale_action",
                row_id=row_id,
                refreshed_actions=actions,
                error=ToolError(
                    code="stale_action",
                    message="Row id was not found in fresh available actions",
                ),
            )
        payload = {
            "session_id": session_id,
            "entity_uuid": entity_uuid,
            "template_name": choice.template_name,
            "target_index": choice.target.target_index,
            "prefer_safe": prefer_safe,
            "extra_target_uuids": None,
            "return_available_actions": False,
        }
        try:
            result = self._request("POST", "/action/execute", json=payload)
        except CodexToolHTTPError as exc:
            return ExecuteResult(status="error", row_id=row_id, error=exc.error)
        return ExecuteResult(status="executed", row_id=row_id, payload=result)

    def end_turn(self, session_id: str, entity_uuid: str) -> dict[str, Any]:
        """End the active turn for one controlled entity."""
        return self._request(
            "POST",
            "/action/end-turn",
            json={"session_id": session_id, "entity_uuid": entity_uuid},
        )

    def watch(
        self,
        session_id: str,
        *,
        claim_id: Optional[str] = None,
        since: int = 0,
        read_timeout_seconds: float = 15.0,
    ) -> WatchResult:
        """Block until the session has a subjective update or active turn."""
        cursor = max(0, since)
        while True:
            if claim_id is not None:
                self.heartbeat(claim_id)
            brief = self.brief(session_id)
            cursor = max(cursor, brief.observation_cursor)
            if brief.is_my_turn:
                return WatchResult(
                    status="ready",
                    session_id=session_id,
                    observation_cursor=brief.observation_cursor,
                    event="turn_ready",
                    brief=brief,
                )
            try:
                stream_result = self._watch_stream_once(
                    session_id,
                    claim_id=claim_id,
                    since=cursor,
                    read_timeout_seconds=read_timeout_seconds,
                )
            except httpx.ReadTimeout:
                continue
            if stream_result is not None:
                return stream_result

    def _watch_stream_once(
        self,
        session_id: str,
        *,
        claim_id: Optional[str],
        since: int,
        read_timeout_seconds: float,
    ) -> Optional[WatchResult]:
        """Read one SSE stream until a subjective frame arrives."""
        timeout = httpx.Timeout(connect=5.0, read=read_timeout_seconds, write=10.0, pool=5.0)
        with self.client.stream(
            "GET",
            f"/ai/sessions/{session_id}/observation/subscribe",
            params={"since": since},
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            event_name: Optional[str] = None
            data_lines: list[str] = []
            for line in response.iter_lines():
                if line == "":
                    payload = _decode_sse_data(data_lines)
                    if event_name == "observation_frame" and payload is not None:
                        if claim_id is not None:
                            self.heartbeat(claim_id)
                        frame = ObservationFrame.model_validate(payload)
                        materialized = self.fetch_materialized(session_id)
                        materialized = apply_observation_frame(materialized, frame)
                        brief = build_brief(materialized)
                        return WatchResult(
                            status="frame",
                            session_id=session_id,
                            observation_cursor=brief.observation_cursor,
                            event=event_name,
                            brief=brief,
                            frame=frame.model_dump(mode="json"),
                        )
                    event_name = None
                    data_lines = []
                    continue
                if line.startswith("event: "):
                    event_name = line.removeprefix("event: ").strip()
                elif line.startswith("data: "):
                    data_lines.append(line.removeprefix("data: "))
        return None

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Send a request and return JSON or raise a structured tool error."""
        response = self.client.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise CodexToolHTTPError(_tool_error(response))
        return response.json()


def build_brief(materialized: ObservationMaterializedState) -> BriefResult:
    """Build a compact Codex brief from materialized subjective state."""
    entities = [
        _brief_entity(entity)
        for entity in materialized.known_entities.values()
    ]
    objects = [
        BriefObject(
            uuid=obj.uuid,
            name=obj.name,
            position=obj.position,
            knowledge_state=obj.knowledge_state.value,
            state=obj.state,
        )
        for obj in materialized.known_objects.values()
    ]
    return BriefResult(
        session_id=materialized.session.session_id,
        observation_cursor=materialized.observation_cursor,
        is_my_turn=materialized.session.is_my_turn,
        active_entity_uuid=materialized.session.active_entity_uuid,
        active_entity_name=materialized.session.active_entity_name,
        controlled_entities=[
            entity for entity in entities
            if entity.controlled
        ],
        visible_entities=[
            entity for entity in entities
            if entity.knowledge_state == "visible"
        ],
        known_objects=objects,
        recent_combat_logs=materialized.combat_logs[-10:],
    )


def normalize_actions(
    session_id: str,
    entity_uuid: str,
    payload: dict[str, Any],
) -> ActionsResult:
    """Normalize available-actions payload into executable choices."""
    choices: list[ActionChoice] = []
    for bucket in ACTION_BUCKETS:
        for row in payload.get(bucket, []):
            if not isinstance(row, dict):
                continue
            targets = row.get("valid_targets", [])
            if not targets:
                choices.append(_choice_from_target(bucket, row, {"index": 0}))
                continue
            for target in targets:
                if isinstance(target, dict):
                    choices.append(_choice_from_target(bucket, row, target))
    return ActionsResult(
        session_id=session_id,
        entity_uuid=entity_uuid,
        basis_cursor=payload.get("basis_cursor"),
        computed_at_observation_cursor=payload.get("computed_at_observation_cursor"),
        choices=choices,
        raw_counts={
            bucket: len(payload.get(bucket, []))
            for bucket in ACTION_BUCKETS
        },
    )


def find_choice(actions: ActionsResult, row_id: str) -> Optional[ActionChoice]:
    """Find an action choice by row id."""
    return next((choice for choice in actions.choices if choice.row_id == row_id), None)


def _choice_from_target(bucket: str, row: dict[str, Any], target: dict[str, Any]) -> ActionChoice:
    """Create one executable choice from an action row and target row."""
    normalized_target = ActionTargetChoice(
        target_index=int(target.get("index", 0)),
        target_uuid=target.get("target_uuid"),
        target_name=target.get("target_name"),
        position=_optional_position(target.get("position")),
        distance=target.get("distance"),
    )
    template_name = str(row.get("template_name", ""))
    return ActionChoice(
        row_id=_row_id(bucket, template_name, normalized_target),
        bucket=bucket,
        template_name=template_name,
        display_name=str(row.get("display_name") or template_name),
        action_category=str(row.get("action_category", "")),
        target_type=str(row.get("target_type", "")),
        can_afford=bool(row.get("can_afford", False)),
        target=normalized_target,
        is_item_use=bool(row.get("is_item_use", False)),
        source_item_uuid=row.get("source_item_uuid"),
    )


def _row_id(bucket: str, template_name: str, target: ActionTargetChoice) -> str:
    """Build a stable row id from semantic action target data."""
    if target.target_uuid:
        target_key = f"uuid={target.target_uuid}"
    elif target.position is not None:
        target_key = f"pos={target.position[0]},{target.position[1]}"
    else:
        target_key = f"index={target.target_index}"
    return f"{bucket}|{template_name}|{target_key}"


def _brief_entity(entity: Any) -> BriefEntity:
    """Convert an observation entity fact to a brief entity row."""
    return BriefEntity(
        uuid=entity.uuid,
        name=entity.name,
        position=entity.position,
        hp=entity.hp,
        max_hp=entity.max_hp,
        ac=entity.ac,
        faction=entity.faction,
        knowledge_state=entity.knowledge_state.value,
        controlled=entity.controlled,
        is_dead=entity.is_dead,
    )


def _optional_position(value: Any) -> Optional[Tuple[int, int]]:
    """Normalize a JSON position into a tuple."""
    if value is None:
        return None
    return (int(value[0]), int(value[1]))


def _decode_sse_data(data_lines: list[str]) -> Optional[dict[str, Any]]:
    """Decode accumulated SSE data lines."""
    if not data_lines:
        return None
    return json.loads("\n".join(data_lines))


def _tool_error(response: httpx.Response) -> ToolError:
    """Build a structured error from an HTTP response."""
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = response.text
    if isinstance(detail, dict):
        code = str(detail.get("code", "http_error"))
        message = str(detail.get("message", response.text))
    else:
        code = "http_error"
        message = str(detail)
    return ToolError(
        code=code,
        message=message,
        status_code=response.status_code,
        detail=detail,
    )
