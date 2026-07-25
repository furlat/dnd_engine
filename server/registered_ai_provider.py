"""Main-server ownership of registered external AI policy providers.

This module is the transport boundary between server orchestration and an
external policy host.  It owns provider authentication, opaque assignment
fences, monotonic decision ids, bounded idempotent retries, and wait timing.
It never owns player credentials or objective game state.
"""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from dnd.ai.contracts.observation import SubjectiveWorldState
from dnd.ai.instrumentation import (
    AIExecutionPhase,
    AIInstrumentation,
    AIInstrumentationContext,
    AIInstrumentationSink,
)
from dnd.ai.policy import PolicyDescriptor
from server.external_ai_protocol import (
    EXTERNAL_AI_PROTOCOL_VERSION,
    ExternalAIAssignmentCloseRequest,
    ExternalAIAssignmentCloseResponse,
    ExternalAIAssignmentLease,
    ExternalAIAssignmentOpenRequest,
    ExternalAIDecisionFeedback,
    ExternalAIDecisionRequest,
    ExternalAIDecisionResponse,
    ExternalAIPolicyProviderHandshake,
    ExternalAIProtocolIdentity,
)


ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)

_PROVIDER_TRANSPORT_DESCRIPTOR = PolicyDescriptor(
    policy_id="external.provider.transport",
    version=str(EXTERNAL_AI_PROTOCOL_VERSION),
    display_name="External provider transport",
    description=(
        "Server-owned provider registration and assignment transport timing."
    ),
)


class RegisteredAIProviderError(RuntimeError):
    """Base failure for the main-server registered-provider boundary."""


class RegisteredAIProviderClosedError(RegisteredAIProviderError):
    """The catalog, provider, or assignment no longer accepts work."""


class RegisteredAIProviderCollisionError(RegisteredAIProviderError):
    """A provider or policy identity is already owned."""


class RegisteredAIProviderNotFoundError(RegisteredAIProviderError):
    """A requested provider or advertised policy is not registered."""


class RegisteredAIProviderCapacityError(RegisteredAIProviderError):
    """The selected provider has no advertised assignment capacity."""


class RegisteredAIProviderBusyError(RegisteredAIProviderError):
    """The provider still owns live game assignments."""


class RegisteredAIProviderProtocolError(RegisteredAIProviderError):
    """A provider response failed closed contract or fence validation."""


class RegisteredAIProviderTransportError(RegisteredAIProviderError):
    """A bounded HTTP operation could not produce a valid response."""


class RegisteredAIDecisionOrderError(RegisteredAIProviderError):
    """A caller attempted to skip or rewrite a decision sequence."""


class RegisteredAIHTTPClientFactory(Protocol):
    """Injectable construction surface for owned async HTTP clients."""

    def __call__(
        self,
        *,
        base_url: str,
        timeout: httpx.Timeout,
        transport: httpx.AsyncBaseTransport | None,
    ) -> httpx.AsyncClient:
        """Create one provider-scoped client owned by the catalog."""
        ...


def _default_http_client_factory(
    *,
    base_url: str,
    timeout: httpx.Timeout,
    transport: httpx.AsyncBaseTransport | None,
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout,
        transport=transport,
    )


@dataclass(frozen=True, slots=True)
class RegisteredAIProviderInfo:
    """Stable provider catalog row with current locally-known capacity."""

    provider_id: str
    base_url: str
    policies: tuple[PolicyDescriptor, ...]
    capacity: int
    active_assignments: int

    @property
    def available_capacity(self) -> int:
        """Return non-negative capacity after known active assignments."""
        return max(0, self.capacity - self.active_assignments)


class _RegisteredAIHTTP:
    """Typed bounded HTTP adapter shared by every provider operation."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        maximum_attempts: int,
        instrumentation: AIInstrumentation,
    ) -> None:
        self._client = client
        self._maximum_attempts = maximum_attempts
        self._instrumentation = instrumentation

    async def request(
        self,
        *,
        method: str,
        path: str,
        response_model: type[ResponseModelT],
        context: AIInstrumentationContext,
        phase: AIExecutionPhase,
        payload: BaseModel | None = None,
    ) -> ResponseModelT:
        """Run one logical request with exact-payload bounded retries."""
        json_payload = (
            payload.model_dump(mode="json")
            if payload is not None
            else None
        )
        final_transport_error: httpx.TransportError | None = None
        with self._instrumentation.measure(context=context, phase=phase):
            for attempt in range(1, self._maximum_attempts + 1):
                try:
                    if json_payload is None:
                        response = await self._client.request(method, path)
                    else:
                        response = await self._client.request(
                            method,
                            path,
                            json=json_payload,
                        )
                except httpx.TransportError as error:
                    final_transport_error = error
                    if attempt < self._maximum_attempts:
                        continue
                    raise RegisteredAIProviderTransportError(
                        f"{method} {path} failed after "
                        f"{self._maximum_attempts} attempts: "
                        f"{type(error).__name__}"
                    ) from error

                if response.status_code >= 500:
                    if attempt < self._maximum_attempts:
                        continue
                    raise RegisteredAIProviderTransportError(
                        f"{method} {path} returned HTTP "
                        f"{response.status_code} after "
                        f"{self._maximum_attempts} attempts"
                    )
                if response.status_code < 200 or response.status_code >= 300:
                    raise RegisteredAIProviderTransportError(
                        f"{method} {path} returned HTTP "
                        f"{response.status_code}; client errors are not retried"
                    )
                try:
                    response_payload = response.json()
                    if (
                        response_model
                        is ExternalAIPolicyProviderHandshake
                        and isinstance(response_payload, dict)
                    ):
                        response_payload = _normalize_handshake_payload(
                            response_payload
                        )
                    return response_model.model_validate(response_payload)
                except (ValueError, ValidationError) as error:
                    raise RegisteredAIProviderProtocolError(
                        f"{method} {path} response could not decode as "
                        f"{response_model.__name__}"
                    ) from error

        raise RegisteredAIProviderTransportError(
            f"{method} {path} failed without a response: "
            f"{type(final_transport_error).__name__}"
        )


class _RegisteredAIProvider:
    """One authenticated provider connection and its live assignments."""

    def __init__(
        self,
        *,
        handshake: ExternalAIPolicyProviderHandshake,
        base_url: str,
        client: httpx.AsyncClient,
        http: _RegisteredAIHTTP,
    ) -> None:
        self.handshake = handshake
        self.base_url = base_url
        self.client = client
        self.http = http
        self.assignments: set[RegisteredAIAssignment] = set()
        self._lifecycle_lock = asyncio.Lock()
        self._closing = False
        self._closed = False

    @property
    def info(self) -> RegisteredAIProviderInfo:
        return RegisteredAIProviderInfo(
            provider_id=self.handshake.provider_id,
            base_url=self.base_url,
            policies=self.handshake.policies,
            capacity=self.handshake.capacity,
            active_assignments=(
                self.handshake.active_assignments + len(self.assignments)
            ),
        )

    async def open_assignment(
        self,
        *,
        request: ExternalAIAssignmentOpenRequest,
        descriptor: PolicyDescriptor,
        on_closed: "_AssignmentClosedCallback",
    ) -> "RegisteredAIAssignment":
        async with self._lifecycle_lock:
            self._require_open()
            context = AIInstrumentationContext(
                game_id=request.game_id,
                assignment_id=request.assignment_id,
                actor_uuid=request.controlled_entity_uuids[0],
                decision_id=(
                    f"{request.assignment_id}:{request.generation}:"
                    "provider-open"
                ),
                policy=descriptor,
            )
            lease = await self.http.request(
                method="POST",
                path="/assignments/open",
                response_model=ExternalAIAssignmentLease,
                context=context,
                phase=AIExecutionPhase.PROVIDER_ASSIGNMENT_OPEN_WAIT,
                payload=request,
            )
            _validate_open_response(
                request=request,
                lease=lease,
                descriptor=descriptor,
            )
            assignment = RegisteredAIAssignment(
                provider=self,
                lease=lease,
                on_closed=on_closed,
            )
            self.assignments.add(assignment)
            return assignment

    def discard_assignment(
        self,
        assignment: "RegisteredAIAssignment",
    ) -> None:
        self.assignments.discard(assignment)

    async def close(self) -> None:
        async with self._lifecycle_lock:
            if self._closed:
                return
            self._closing = True
            assignments = tuple(self.assignments)

        first_error: Exception | None = None
        for assignment in assignments:
            try:
                await assignment.close()
            except Exception as error:
                if first_error is None:
                    first_error = error
                assignment._force_closed()
        await self.client.aclose()
        async with self._lifecycle_lock:
            self._closed = True
            self._closing = False
        if first_error is not None:
            raise RegisteredAIProviderTransportError(
                "provider client closed after assignment teardown failed"
            ) from first_error

    def _require_open(self) -> None:
        if self._closing or self._closed:
            raise RegisteredAIProviderClosedError(
                f"provider {self.handshake.provider_id!r} is closing"
            )


class _AssignmentClosedCallback(Protocol):
    def __call__(self, assignment: "RegisteredAIAssignment") -> None:
        """Release one locally closed assignment from catalog ownership."""
        ...


class RegisteredAIAssignment:
    """One remote policy/memory assignment behind a server-owned fence."""

    def __init__(
        self,
        *,
        provider: _RegisteredAIProvider,
        lease: ExternalAIAssignmentLease,
        on_closed: _AssignmentClosedCallback,
    ) -> None:
        self._provider = provider
        self._lease = lease
        self._on_closed = on_closed
        self._next_decision_id = 1
        self._pending_decision: ExternalAIDecisionRequest | None = None
        self._closed = False
        self._decision_lock = asyncio.Lock()

    @property
    def provider_id(self) -> str:
        return self._provider.handshake.provider_id

    @property
    def assignment_id(self) -> str:
        return self._lease.assignment_id

    @property
    def generation(self) -> int:
        return self._lease.generation

    @property
    def assignment_token(self) -> str:
        return self._lease.assignment_token

    @property
    def game_id(self) -> str:
        return self._lease.game_id

    @property
    def controlled_entity_uuids(self) -> tuple[str, ...]:
        return self._lease.controlled_entity_uuids

    @property
    def policy(self) -> PolicyDescriptor:
        return self._lease.policy

    @property
    def next_decision_id(self) -> int:
        return self._next_decision_id

    @property
    def closed(self) -> bool:
        return self._closed

    async def decide(
        self,
        *,
        state: SubjectiveWorldState,
        feedback: tuple[ExternalAIDecisionFeedback, ...] = (),
        decision_id: int | None = None,
    ) -> ExternalAIDecisionResponse:
        """Request exactly the next decision, preserving ambiguous retries."""
        async with self._decision_lock:
            self._require_open()
            requested_id = (
                self._next_decision_id
                if decision_id is None
                else decision_id
            )
            if requested_id != self._next_decision_id:
                raise RegisteredAIDecisionOrderError(
                    "decision id must be contiguous; expected "
                    f"{self._next_decision_id}, received {requested_id}"
                )
            request = ExternalAIDecisionRequest(
                protocol=ExternalAIProtocolIdentity(),
                assignment_id=self.assignment_id,
                generation=self.generation,
                assignment_token=self.assignment_token,
                decision_id=requested_id,
                state=state,
                feedback=feedback,
            )
            if (
                self._pending_decision is not None
                and request != self._pending_decision
            ):
                raise RegisteredAIDecisionOrderError(
                    "an uncertain decision may only retry the exact same "
                    "idempotent request"
                )
            self._pending_decision = request
            actor_uuid = (
                state.current_epoch.actor_uuid
                if state.current_epoch is not None
                else self.controlled_entity_uuids[0]
            )
            context = AIInstrumentationContext(
                game_id=self.game_id,
                assignment_id=self.assignment_id,
                actor_uuid=actor_uuid,
                decision_id=(
                    f"{self.assignment_id}:{self.generation}:"
                    f"{requested_id}"
                ),
                policy=self.policy,
            )
            response = await self._provider.http.request(
                method="POST",
                path="/assignments/decide",
                response_model=ExternalAIDecisionResponse,
                context=context,
                phase=AIExecutionPhase.PROVIDER_DECISION_WAIT,
                payload=request,
            )
            _validate_decision_response(
                request=request,
                response=response,
                descriptor=self.policy,
            )
            self._pending_decision = None
            self._next_decision_id += 1
            return response

    async def close(self) -> ExternalAIAssignmentCloseResponse:
        """Close the exact assignment generation idempotently."""
        async with self._decision_lock:
            if self._closed:
                return ExternalAIAssignmentCloseResponse(
                    protocol=ExternalAIProtocolIdentity(),
                    assignment_id=self.assignment_id,
                    generation=self.generation,
                    assignment_token=self.assignment_token,
                )
            request = ExternalAIAssignmentCloseRequest(
                protocol=ExternalAIProtocolIdentity(),
                assignment_id=self.assignment_id,
                generation=self.generation,
                assignment_token=self.assignment_token,
            )
            context = AIInstrumentationContext(
                game_id=self.game_id,
                assignment_id=self.assignment_id,
                actor_uuid=self.controlled_entity_uuids[0],
                decision_id=(
                    f"{self.assignment_id}:{self.generation}:"
                    "provider-close"
                ),
                policy=self.policy,
            )
            response = await self._provider.http.request(
                method="POST",
                path="/assignments/close",
                response_model=ExternalAIAssignmentCloseResponse,
                context=context,
                phase=AIExecutionPhase.PROVIDER_ASSIGNMENT_CLOSE_WAIT,
                payload=request,
            )
            _validate_close_response(request=request, response=response)
            self._mark_closed()
            return response

    def _require_open(self) -> None:
        if self._closed:
            raise RegisteredAIProviderClosedError(
                f"assignment {self.assignment_id!r} is closed"
            )

    def _mark_closed(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._pending_decision = None
        self._provider.discard_assignment(self)
        self._on_closed(self)

    def _force_closed(self) -> None:
        self._mark_closed()


class RegisteredAIProviderCatalog:
    """Authenticated provider/policy catalog and assignment fence issuer."""

    def __init__(
        self,
        *,
        reserved_policy_ids: set[str] | frozenset[str] = frozenset(),
        timeout_seconds: float = 10.0,
        max_attempts: int = 2,
        client_factory: RegisteredAIHTTPClientFactory = (
            _default_http_client_factory
        ),
        instrumentation_sink: AIInstrumentationSink | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_attempts < 1 or max_attempts > 8:
            raise ValueError("max_attempts must be between 1 and 8")
        self._reserved_policy_ids = frozenset(reserved_policy_ids)
        self._timeout = httpx.Timeout(timeout_seconds)
        self._max_attempts = max_attempts
        self._client_factory = client_factory
        self._instrumentation = AIInstrumentation(
            sink=instrumentation_sink
        )
        self._providers: dict[str, _RegisteredAIProvider] = {}
        self._policies: dict[str, _RegisteredAIProvider] = {}
        self._active_assignment_ids: dict[
            str,
            RegisteredAIAssignment,
        ] = {}
        self._opening_assignment_ids: set[str] = set()
        self._assignment_generations: dict[str, int] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    async def register(
        self,
        *,
        provider_id: str,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> RegisteredAIProviderInfo:
        """Authenticate and atomically add one provider catalog."""
        if not provider_id:
            raise ValueError("provider_id must not be empty")
        if not base_url:
            raise ValueError("base_url must not be empty")
        async with self._lock:
            self._require_open()
            if provider_id in self._providers:
                raise RegisteredAIProviderCollisionError(
                    f"provider {provider_id!r} is already registered"
                )

        client = self._client_factory(
            base_url=base_url,
            timeout=self._timeout,
            transport=transport,
        )
        http = _RegisteredAIHTTP(
            client=client,
            maximum_attempts=self._max_attempts,
            instrumentation=self._instrumentation,
        )
        context = AIInstrumentationContext(
            game_id="provider-registry",
            assignment_id=f"provider:{provider_id}",
            actor_uuid=provider_id,
            decision_id="provider-handshake",
            policy=_PROVIDER_TRANSPORT_DESCRIPTOR,
        )
        try:
            handshake = await http.request(
                method="GET",
                path="/handshake",
                response_model=ExternalAIPolicyProviderHandshake,
                context=context,
                phase=AIExecutionPhase.PROVIDER_HANDSHAKE_WAIT,
            )
            if handshake.provider_id != provider_id:
                raise RegisteredAIProviderProtocolError(
                    "provider handshake identity does not match registration: "
                    f"expected {provider_id!r}, received "
                    f"{handshake.provider_id!r}"
                )
            connection = _RegisteredAIProvider(
                handshake=handshake,
                base_url=base_url,
                client=client,
                http=http,
            )
            async with self._lock:
                self._require_open()
                self._validate_registration_collisions(handshake)
                self._providers[provider_id] = connection
                for descriptor in handshake.policies:
                    self._policies[descriptor.policy_id] = connection
                return connection.info
        except BaseException:
            await client.aclose()
            raise

    async def unregister(
        self,
        provider_id: str,
        *,
        force: bool = False,
    ) -> None:
        """Remove one provider after all owned game assignments are closed."""
        async with self._lock:
            provider = self._providers.get(provider_id)
            if provider is None:
                raise RegisteredAIProviderNotFoundError(
                    f"provider {provider_id!r} is not registered"
                )
            if provider.assignments and not force:
                raise RegisteredAIProviderBusyError(
                    f"provider {provider_id!r} still owns "
                    f"{len(provider.assignments)} live assignments"
                )
            self._providers.pop(provider_id)
            for descriptor in provider.handshake.policies:
                self._policies.pop(descriptor.policy_id, None)
            for assignment in tuple(provider.assignments):
                self._active_assignment_ids.pop(
                    assignment.assignment_id,
                    None,
                )
        await provider.close()

    @property
    def closed(self) -> bool:
        """Return whether lifecycle teardown permanently closed this catalog."""
        return self._closed

    def providers(self) -> tuple[RegisteredAIProviderInfo, ...]:
        """Return stable provider rows ordered by provider identity."""
        return tuple(
            self._providers[provider_id].info
            for provider_id in sorted(self._providers)
        )

    def provider(self, provider_id: str) -> RegisteredAIProviderInfo:
        """Return current information for one exact provider."""
        provider = self._providers.get(provider_id)
        if provider is None:
            raise RegisteredAIProviderNotFoundError(
                f"provider {provider_id!r} is not registered"
            )
        return provider.info

    def provider_for_policy(
        self,
        policy_id: str,
    ) -> RegisteredAIProviderInfo:
        """Resolve the one authenticated provider that owns a policy id."""
        provider = self._policies.get(policy_id)
        if provider is None:
            raise RegisteredAIProviderNotFoundError(
                f"policy {policy_id!r} is not registered externally"
            )
        return provider.info

    def policy_descriptor(self, policy_id: str) -> PolicyDescriptor:
        """Return the frozen descriptor authenticated during registration."""
        provider = self._policies.get(policy_id)
        if provider is None:
            raise RegisteredAIProviderNotFoundError(
                f"policy {policy_id!r} is not registered externally"
            )
        for descriptor in provider.handshake.policies:
            if descriptor.policy_id == policy_id:
                return descriptor
        raise RegisteredAIProviderProtocolError(
            f"provider policy index lost descriptor {policy_id!r}"
        )

    async def open_assignment(
        self,
        *,
        policy_id: str,
        game_id: str,
        controlled_entity_uuids: tuple[str, ...],
        assignment_id: str | None = None,
    ) -> RegisteredAIAssignment:
        """Issue a fresh opaque generation fence and open one assignment."""
        logical_id = assignment_id or (
            f"external-assignment-{secrets.token_urlsafe(18)}"
        )
        async with self._lock:
            self._require_open()
            provider = self._policies.get(policy_id)
            if provider is None:
                raise RegisteredAIProviderNotFoundError(
                    f"policy {policy_id!r} is not registered externally"
                )
            if (
                logical_id in self._active_assignment_ids
                or logical_id in self._opening_assignment_ids
            ):
                raise RegisteredAIProviderCollisionError(
                    f"assignment {logical_id!r} is already active"
                )
            if provider.info.available_capacity < 1:
                raise RegisteredAIProviderCapacityError(
                    f"provider {provider.handshake.provider_id!r} "
                    "has no advertised capacity"
                )
            generation = self._assignment_generations.get(logical_id, 0) + 1
            self._assignment_generations[logical_id] = generation
            self._opening_assignment_ids.add(logical_id)
            descriptor = self.policy_descriptor(policy_id)

        request = ExternalAIAssignmentOpenRequest(
            protocol=ExternalAIProtocolIdentity(),
            assignment_id=logical_id,
            generation=generation,
            assignment_token=secrets.token_urlsafe(32),
            game_id=game_id,
            controlled_entity_uuids=controlled_entity_uuids,
            policy_id=policy_id,
        )
        assignment: RegisteredAIAssignment | None = None
        try:
            assignment = await provider.open_assignment(
                request=request,
                descriptor=descriptor,
                on_closed=self._assignment_closed,
            )
            async with self._lock:
                self._opening_assignment_ids.discard(logical_id)
                self._require_open()
                if (
                    self._providers.get(provider.handshake.provider_id)
                    is not provider
                ):
                    raise RegisteredAIProviderClosedError(
                        "provider was unregistered while opening assignment"
                    )
                self._active_assignment_ids[logical_id] = assignment
            return assignment
        except BaseException:
            async with self._lock:
                self._opening_assignment_ids.discard(logical_id)
            if assignment is not None and not assignment.closed:
                await assignment.close()
            raise

    async def close(self) -> None:
        """Close all providers once and reject future registrations."""
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            providers = tuple(self._providers.values())
            self._providers.clear()
            self._policies.clear()
            self._active_assignment_ids.clear()
            self._opening_assignment_ids.clear()

        first_error: Exception | None = None
        for provider in providers:
            try:
                await provider.close()
            except Exception as error:
                if first_error is None:
                    first_error = error
        if first_error is not None:
            raise RegisteredAIProviderTransportError(
                "provider catalog closed after teardown failure"
            ) from first_error

    def _validate_registration_collisions(
        self,
        handshake: ExternalAIPolicyProviderHandshake,
    ) -> None:
        if handshake.provider_id in self._providers:
            raise RegisteredAIProviderCollisionError(
                f"provider {handshake.provider_id!r} is already registered"
            )
        policy_ids = {row.policy_id for row in handshake.policies}
        reserved = policy_ids & self._reserved_policy_ids
        if reserved:
            raise RegisteredAIProviderCollisionError(
                "external provider policy ids collide with reserved native "
                f"policy ids: {sorted(reserved)!r}"
            )
        existing = policy_ids & self._policies.keys()
        if existing:
            raise RegisteredAIProviderCollisionError(
                "external provider policy ids are already registered: "
                f"{sorted(existing)!r}"
            )

    def _assignment_closed(
        self,
        assignment: RegisteredAIAssignment,
    ) -> None:
        current = self._active_assignment_ids.get(
            assignment.assignment_id
        )
        if current is assignment:
            self._active_assignment_ids.pop(assignment.assignment_id, None)

    def _require_open(self) -> None:
        if self._closed:
            raise RegisteredAIProviderClosedError(
                "registered AI provider catalog is closed"
            )


def _validate_open_response(
    *,
    request: ExternalAIAssignmentOpenRequest,
    lease: ExternalAIAssignmentLease,
    descriptor: PolicyDescriptor,
) -> None:
    if (
        lease.assignment_id != request.assignment_id
        or lease.generation != request.generation
        or lease.assignment_token != request.assignment_token
        or lease.game_id != request.game_id
        or lease.controlled_entity_uuids
        != request.controlled_entity_uuids
    ):
        raise RegisteredAIProviderProtocolError(
            "assignment-open response did not echo the exact server fence"
        )
    if lease.policy != descriptor or lease.policy.policy_id != request.policy_id:
        raise RegisteredAIProviderProtocolError(
            "assignment-open response policy does not match the catalog"
        )


def _normalize_handshake_payload(
    payload: dict[str, object],
) -> dict[str, object]:
    """Validate and remove the serialized read-only computed capacity field."""
    normalized = dict(payload)
    serialized_available = normalized.pop("available_capacity", None)
    if serialized_available is None:
        return normalized
    capacity = normalized.get("capacity")
    active_assignments = normalized.get("active_assignments")
    if (
        not isinstance(capacity, int)
        or isinstance(capacity, bool)
        or not isinstance(active_assignments, int)
        or isinstance(active_assignments, bool)
        or serialized_available != capacity - active_assignments
    ):
        raise ValueError(
            "provider handshake available_capacity is inconsistent"
        )
    return normalized


def _validate_decision_response(
    *,
    request: ExternalAIDecisionRequest,
    response: ExternalAIDecisionResponse,
    descriptor: PolicyDescriptor,
) -> None:
    if (
        response.assignment_id != request.assignment_id
        or response.generation != request.generation
        or response.assignment_token != request.assignment_token
        or response.decision_id != request.decision_id
    ):
        raise RegisteredAIProviderProtocolError(
            "decision response did not echo the exact assignment fence"
        )
    if response.policy != descriptor:
        raise RegisteredAIProviderProtocolError(
            "decision response policy does not match the opened assignment"
        )


def _validate_close_response(
    *,
    request: ExternalAIAssignmentCloseRequest,
    response: ExternalAIAssignmentCloseResponse,
) -> None:
    if (
        response.assignment_id != request.assignment_id
        or response.generation != request.generation
        or response.assignment_token != request.assignment_token
        or response.closed is not True
    ):
        raise RegisteredAIProviderProtocolError(
            "assignment-close response did not echo the exact server fence"
        )


__all__ = [
    "RegisteredAIAssignment",
    "RegisteredAIDecisionOrderError",
    "RegisteredAIHTTPClientFactory",
    "RegisteredAIProviderCapacityError",
    "RegisteredAIProviderBusyError",
    "RegisteredAIProviderCatalog",
    "RegisteredAIProviderClosedError",
    "RegisteredAIProviderCollisionError",
    "RegisteredAIProviderError",
    "RegisteredAIProviderInfo",
    "RegisteredAIProviderNotFoundError",
    "RegisteredAIProviderProtocolError",
    "RegisteredAIProviderTransportError",
]
