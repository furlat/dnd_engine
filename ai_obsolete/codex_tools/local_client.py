"""Typed HTTP client for one authenticated hot Codex runtime."""

from __future__ import annotations

from typing import Any, Optional, TypeVar

import httpx
from pydantic import BaseModel, Field

from ai.codex_tools.hot_runtime import (
    HotCodexCommandView,
    HotCodexComponentCatalog,
    HotCodexEndTurnRequest,
    HotCodexExecuteRequest,
    HotCodexGeometryRequest,
    HotCodexGeometryView,
    HotCodexHealth,
    HotCodexInspectionCatalogView,
    HotCodexInspectionDiffRequest,
    HotCodexInspectionDiffView,
    HotCodexInspectionExportView,
    HotCodexInspectionGetRequest,
    HotCodexInspectionGetView,
    HotCodexInspectionSchemaView,
    HotCodexInspectionSearchRequest,
    HotCodexInspectionSearchView,
    HotCodexOracleRequest,
    HotCodexOracleView,
    HotCodexPredicateCatalog,
    HotCodexPredicateEvaluateRequest,
    HotCodexPredicateFocusRequest,
    HotCodexPredicateRegisterRequest,
    HotCodexProfileSelectRequest,
    HotCodexProfileView,
    HotCodexQueryRequest,
    HotCodexQueryResult,
    HotCodexReleaseView,
    HotCodexRepresentationView,
    HotCodexTurnIndex,
)
from ai.codex_tools.representation.predicates import (
    PredicateDefinition,
    PredicateFocusProfile,
    PredicateLedgerSnapshot,
)


ModelT = TypeVar("ModelT", bound=BaseModel)


class HotCodexClientFailure(BaseModel):
    """Structured local-daemon failure retained by the typed client."""

    code: str = Field(description="Machine-readable failure identity.")
    message: str = Field(description="Human-readable failure message.")
    status_code: int = Field(description="HTTP status returned by the local daemon.")


class HotCodexClientError(RuntimeError):
    """Raised when authenticated hot-runtime transport fails."""

    def __init__(self, failure: HotCodexClientFailure) -> None:
        """Create an exception retaining the typed daemon failure."""
        super().__init__(failure.message)
        self.failure = failure


class HotCodexLocalClient:
    """Typed transport over the task-local Codex API only."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        *,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        """Create an authenticated client.

        Args:
            base_url: Loopback hot-runtime URL, not the game-server URL.
            bearer_token: Runtime-specific bearer token printed by ``hot-serve``.
            transport: Optional HTTPX transport used by focused tests.
        """
        self.base_url = base_url.rstrip("/")
        timeout = httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0)
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {bearer_token}"},
        )

    def close(self) -> None:
        """Close the underlying connection pool."""
        self.client.close()

    def __enter__(self) -> "HotCodexLocalClient":
        """Return this client for context-manager use."""
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        """Close the client and propagate any exception."""
        self.close()
        return False

    def health(self) -> HotCodexHealth:
        """Return daemon health and current revision identity."""
        return self._request("GET", "/v1/health", HotCodexHealth)

    def turn(self) -> HotCodexTurnIndex:
        """Return the current compatibility turn view."""
        return self._request("GET", "/v1/turn", HotCodexTurnIndex)

    def watch(self) -> HotCodexTurnIndex:
        """Wait until the controlled session owns a decision epoch."""
        return self._request("POST", "/v1/watch", HotCodexTurnIndex)

    def query(self, request: HotCodexQueryRequest) -> HotCodexQueryResult:
        """Select complete typed details from the local subjective world."""
        return self._request("POST", "/v1/query", HotCodexQueryResult, request=request)

    def profile(self) -> HotCodexProfileView:
        """Return the active representation profile and resolved manifest."""
        return self._request("GET", "/v1/representation/profile", HotCodexProfileView)

    def select_profile(self, request: HotCodexProfileSelectRequest) -> HotCodexProfileView:
        """Select one profile at an exact local revision."""
        return self._request(
            "POST",
            "/v1/representation/profile/select",
            HotCodexProfileView,
            request=request,
        )

    def components(self) -> HotCodexComponentCatalog:
        """Return all discoverable component and profile definitions."""
        return self._request(
            "GET",
            "/v1/representation/components",
            HotCodexComponentCatalog,
        )

    def representation(self) -> HotCodexRepresentationView:
        """Return the current profile-driven automatic representation."""
        return self._request(
            "GET",
            "/v1/representation/current",
            HotCodexRepresentationView,
        )

    def oracle(self, request: HotCodexOracleRequest) -> HotCodexOracleView:
        """Request explicitly separated traditional-policy advice."""
        return self._request(
            "POST",
            "/v1/representation/oracle",
            HotCodexOracleView,
            request=request,
        )

    def geometry(self, request: HotCodexGeometryRequest) -> HotCodexGeometryView:
        """Evaluate one local subjective geometry operation."""
        return self._request(
            "POST",
            "/v1/geometry/query",
            HotCodexGeometryView,
            request=request,
        )

    def predicate_catalog(self) -> HotCodexPredicateCatalog:
        """Return all derived-fact and declarative-predicate definitions."""
        return self._request("GET", "/v1/predicates/catalog", HotCodexPredicateCatalog)

    def register_predicate(
        self,
        request: HotCodexPredicateRegisterRequest,
    ) -> PredicateDefinition:
        """Register one validated JSON-native predicate."""
        return self._request(
            "POST",
            "/v1/predicates/register",
            PredicateDefinition,
            request=request,
        )

    def evaluate_predicates(
        self,
        request: HotCodexPredicateEvaluateRequest,
    ) -> PredicateLedgerSnapshot:
        """Evaluate the complete logical ledger at one revision."""
        return self._request(
            "POST",
            "/v1/predicates/evaluate",
            PredicateLedgerSnapshot,
            request=request,
        )

    def predicate_focus(self) -> PredicateFocusProfile:
        """Return automatic logical-attention configuration."""
        return self._request("GET", "/v1/predicates/focus", PredicateFocusProfile)

    def set_predicate_focus(
        self,
        request: HotCodexPredicateFocusRequest,
    ) -> PredicateFocusProfile:
        """Replace automatic logical attention at one revision."""
        return self._request(
            "POST",
            "/v1/predicates/focus",
            PredicateFocusProfile,
            request=request,
        )

    def inspection_catalog(self) -> HotCodexInspectionCatalogView:
        """Return immutable local inspection roots and operations."""
        return self._request("GET", "/v1/inspect/catalog", HotCodexInspectionCatalogView)

    def inspection_get(
        self,
        request: HotCodexInspectionGetRequest,
    ) -> HotCodexInspectionGetView:
        """Read exact canonical subjective JSON pointers."""
        return self._request("POST", "/v1/inspect/get", HotCodexInspectionGetView, request=request)

    def inspection_search(
        self,
        request: HotCodexInspectionSearchRequest,
    ) -> HotCodexInspectionSearchView:
        """Search bounded canonical subjective paths and scalar values."""
        return self._request(
            "POST",
            "/v1/inspect/search",
            HotCodexInspectionSearchView,
            request=request,
        )

    def inspection_diff(
        self,
        request: HotCodexInspectionDiffRequest,
    ) -> HotCodexInspectionDiffView:
        """Compare two retained immutable local inspection documents."""
        return self._request("POST", "/v1/inspect/diff", HotCodexInspectionDiffView, request=request)

    def inspection_schema(self) -> HotCodexInspectionSchemaView:
        """Return typed schemas and open-JSON declarations."""
        return self._request("GET", "/v1/inspect/schema", HotCodexInspectionSchemaView)

    def inspection_export(self) -> HotCodexInspectionExportView:
        """Return one complete canonical subjective artifact."""
        return self._request("GET", "/v1/inspect/export", HotCodexInspectionExportView)

    def execute(self, request: HotCodexExecuteRequest) -> HotCodexCommandView:
        """Execute one current server-issued row."""
        return self._request("POST", "/v1/execute", HotCodexCommandView, request=request)

    def end_turn(self, request: HotCodexEndTurnRequest) -> HotCodexCommandView:
        """End the exact current controlled epoch."""
        return self._request("POST", "/v1/end-turn", HotCodexCommandView, request=request)

    def release(self) -> HotCodexReleaseView:
        """Release the task-local runtime and its takeover claim."""
        return self._request("POST", "/v1/release", HotCodexReleaseView)

    def _request(
        self,
        method: str,
        path: str,
        response_model: type[ModelT],
        *,
        request: Optional[BaseModel] = None,
    ) -> ModelT:
        """Send one typed request and validate its complete response."""
        try:
            response = self.client.request(
                method,
                path,
                json=request.model_dump(mode="json") if request is not None else None,
            )
        except httpx.RequestError as exc:
            raise HotCodexClientError(HotCodexClientFailure(
                code="request_error",
                message=str(exc),
                status_code=0,
            )) from exc
        if response.status_code >= 400:
            raise HotCodexClientError(_failure(response))
        return response_model.model_validate(response.json())


def _failure(response: httpx.Response) -> HotCodexClientFailure:
    """Decode FastAPI and hot-runtime structured failures consistently."""
    try:
        payload: Any = response.json()
    except ValueError:
        payload = response.text
    body = payload.get("error", payload.get("detail", payload)) if isinstance(payload, dict) else payload
    if isinstance(body, dict):
        code = str(body.get("code", "http_error"))
        message = str(body.get("message", body))
    else:
        code = "http_error"
        message = str(body)
    return HotCodexClientFailure(
        code=code,
        message=message,
        status_code=response.status_code,
    )
