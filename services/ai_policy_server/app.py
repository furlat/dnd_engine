"""FastAPI transport for the reference registered-policy provider."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from dnd.ai.instrumentation import AIInstrumentationSink
from dnd.ai.policies.basic import CanonicalPolicyRegistry
from server.external_ai_protocol import (
    ExternalAIAssignmentCloseRequest,
    ExternalAIAssignmentCloseResponse,
    ExternalAIAssignmentLease,
    ExternalAIAssignmentOpenRequest,
    ExternalAIDecisionRequest,
    ExternalAIDecisionResponse,
    ExternalAIPolicyProviderHandshake,
)
from server.external_ai_registry import ExternalAIRegistryError
from services.ai_policy_server.composition import (
    AIPolicyServiceRuntime,
    DEFAULT_PROVIDER_CAPACITY,
    DEFAULT_PROVIDER_ID,
    DEFAULT_RESPONSE_CACHE_SIZE,
    create_ai_policy_service_runtime,
)


def create_ai_policy_service(
    *,
    provider_id: str = DEFAULT_PROVIDER_ID,
    capacity: int = DEFAULT_PROVIDER_CAPACITY,
    response_cache_size: int = DEFAULT_RESPONSE_CACHE_SIZE,
    policy_registry: CanonicalPolicyRegistry | None = None,
    instrumentation_sink: AIInstrumentationSink | None = None,
    runtime: AIPolicyServiceRuntime | None = None,
) -> FastAPI:
    """Create an HTTP adapter over one reusable provider runtime."""
    if runtime is not None and (
        provider_id != DEFAULT_PROVIDER_ID
        or capacity != DEFAULT_PROVIDER_CAPACITY
        or response_cache_size != DEFAULT_RESPONSE_CACHE_SIZE
        or policy_registry is not None
        or instrumentation_sink is not None
    ):
        raise ValueError(
            "runtime cannot be combined with provider construction options"
        )
    service_runtime = runtime or create_ai_policy_service_runtime(
        provider_id=provider_id,
        capacity=capacity,
        response_cache_size=response_cache_size,
        policy_registry=policy_registry,
        instrumentation_sink=instrumentation_sink,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        del application
        try:
            yield
        finally:
            service_runtime.shutdown()

    service = FastAPI(
        title="D&D External AI Policy Provider",
        version="1",
        lifespan=lifespan,
    )
    service.state.ai_policy_runtime = service_runtime

    @service.exception_handler(ExternalAIRegistryError)
    async def handle_registry_error(
        request: Request,
        error: ExternalAIRegistryError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": error.detail()},
        )

    @service.get(
        "/handshake",
        response_model=ExternalAIPolicyProviderHandshake,
    )
    def handshake() -> ExternalAIPolicyProviderHandshake:
        return service_runtime.provider.handshake()

    @service.post(
        "/assignments/open",
        response_model=ExternalAIAssignmentLease,
    )
    def open_assignment(
        request: ExternalAIAssignmentOpenRequest,
    ) -> ExternalAIAssignmentLease:
        return service_runtime.provider.open_assignment(request)

    @service.post(
        "/assignments/decide",
        response_model=ExternalAIDecisionResponse,
    )
    def decide(
        request: ExternalAIDecisionRequest,
    ) -> ExternalAIDecisionResponse:
        return service_runtime.provider.decide(request)

    @service.post(
        "/assignments/close",
        response_model=ExternalAIAssignmentCloseResponse,
    )
    def close_assignment(
        request: ExternalAIAssignmentCloseRequest,
    ) -> ExternalAIAssignmentCloseResponse:
        return service_runtime.provider.close_assignment(request)

    return service


app = create_ai_policy_service()


__all__ = ["app", "create_ai_policy_service"]

