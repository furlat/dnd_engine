"""Typed takeover transport used by the persistent Codex runtime."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from ai.codex_tools.contracts import (
    TakeoverClaimInfo,
    TakeoverHeartbeatResult,
    ToolError,
)


class CodexToolHTTPError(RuntimeError):
    """Raised when takeover transport fails."""

    def __init__(self, error: ToolError) -> None:
        """Create an exception from a structured tool error."""
        super().__init__(error.message)
        self.error = error


class CodexToolClient:
    """Typed HTTP transport for takeover lease ownership only."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000") -> None:
        """Create a takeover transport client."""
        self.base_url = base_url.rstrip("/")
        timeout = httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0)
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()

    def __enter__(self) -> "CodexToolClient":
        """Return this client for context-manager use."""
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        """Close the client and allow exceptions to propagate."""
        self.close()
        return False

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
        """Claim combatants for one persistent Codex runtime."""
        return self._request("POST", "/ai/takeover", json={
            "faction": faction,
            "entity_uuids": entity_uuids,
            "session_id": session_id,
            "name": name,
            "force": force,
            "lease_seconds": lease_seconds,
        })

    def resolve_control_claim(
        self,
        *,
        faction: str = "monsters",
        entity_uuids: Optional[list[str]] = None,
        claim_id: Optional[str] = None,
        session_id: Optional[str] = None,
        name: str = "Codex",
        force: bool = False,
        lease_seconds: float = 120.0,
    ) -> TakeoverClaimInfo:
        """Create a claim or renew and adopt one exact existing claim."""
        if claim_id is not None:
            if force:
                raise CodexToolHTTPError(ToolError(
                    code="invalid_takeover_claim_options",
                    message="force cannot be combined with exact claim adoption",
                    status_code=400,
                    detail={"claim_id": claim_id},
                ))
            claim = TakeoverHeartbeatResult.model_validate(self.heartbeat(claim_id)).claim
            if session_id is not None and claim.session_id != session_id:
                raise CodexToolHTTPError(ToolError(
                    code="takeover_claim_session_mismatch",
                    message="The takeover claim belongs to a different Codex session",
                    status_code=409,
                    detail={
                        "claim_id": claim.claim_id,
                        "claim_session_id": claim.session_id,
                        "requested_session_id": session_id,
                    },
                ))
            return claim
        return TakeoverClaimInfo.model_validate(self.takeover(
            faction=faction,
            entity_uuids=entity_uuids,
            session_id=session_id,
            name=name,
            force=force,
            lease_seconds=lease_seconds,
        ))

    def release(self, claim_id: str) -> dict[str, Any]:
        """Release a takeover claim."""
        return self._request("POST", f"/ai/takeover/{claim_id}/release")

    def heartbeat(self, claim_id: str) -> dict[str, Any]:
        """Refresh a takeover lease."""
        return self._request("POST", f"/ai/takeover/{claim_id}/heartbeat")

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Send a request and return JSON or raise a structured transport error."""
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise CodexToolHTTPError(ToolError(
                code="request_error",
                message=str(exc),
                detail={"method": method, "path": path},
            )) from exc
        if response.status_code >= 400:
            raise CodexToolHTTPError(_tool_error(response))
        return response.json()


def _tool_error(response: httpx.Response) -> ToolError:
    """Decode one structured server error response."""
    try:
        detail: Any = response.json()
    except ValueError:
        detail = response.text
    payload = detail.get("detail", detail) if isinstance(detail, dict) else detail
    if isinstance(payload, dict):
        code = str(payload.get("code", "http_error"))
        message = str(payload.get("message", payload))
    else:
        code = "http_error"
        message = str(payload)
    return ToolError(
        code=code,
        message=message,
        status_code=response.status_code,
        detail=detail,
    )
