"""Runtime behavior identities and passive handler-dispatch evidence."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dnd.core.content.identities import validate_namespaced_id


class RuntimeBehaviorKind(str, Enum):
    """Engine behavior families with distinct runtime evidence lifecycles."""

    ACTION = "action"
    SPELL = "spell"
    REACTION = "reaction"
    TRAIT = "trait"
    FEAT = "feat"
    CLASS_FEATURE = "class_feature"
    CONDITION = "condition"
    ITEM = "item"
    ENVIRONMENT_INTERACTION = "environment_interaction"
    SYSTEM = "system"
    UNCLASSIFIED = "unclassified"


class BehaviorBinding(BaseModel):
    """Immutable semantic identity attached to one live rules behavior.

    The binding deliberately separates the behavior's own meaning from the
    definition that provided it and from an optional durable root. Runtime
    owner UUIDs remain encounter-local correlation facts; they are never
    durable content identity.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    behavior_id: str = Field(
        description="Namespaced identity of the executable rule.",
    )
    provided_by_id: str = Field(
        description="Namespaced identity that installed or granted the rule.",
    )
    origin_root_id: str | None = Field(
        default=None,
        description="Optional durable semantic root of the provider chain.",
    )
    runtime_owner_uuid: UUID = Field(
        description=(
            "Encounter-local UUID of the entity, item, condition, or other "
            "block that owns this behavior instance."
        ),
    )

    @field_validator("behavior_id", "provided_by_id", "origin_root_id")
    @classmethod
    def _validate_semantic_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_namespaced_id(value, "behavior identity")


class RuntimeBehaviorBindingGateway(Protocol):
    """Dependency-neutral adapter implemented by the installed content system."""

    def bind_independent(
        self,
        behavior: object,
        *,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding | None:
        """Bind one directly declared behavior with itself as provider."""
        ...

    def bind_child(
        self,
        behavior: object,
        *,
        provider_binding: BehaviorBinding,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        """Bind one runtime child through an exact active provider."""
        ...

    def bind_root_owned(
        self,
        behavior: object,
        *,
        origin_root_id: str,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding | None:
        """Bind an explicitly root-owned behavior or decline ordinary ones."""
        ...

    def bind_direct_child(
        self,
        behavior: object,
        *,
        provided_by_id: str,
        origin_root_id: str | None,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        """Bind one child through explicit primitive provider facts."""
        ...


_runtime_behavior_binding_gateway: RuntimeBehaviorBindingGateway | None = None
_runtime_behavior_binding_content_set_digest: str | None = None
_runtime_behavior_context_generation = 0
_active_behavior_binding: ContextVar[
    tuple[int, BehaviorBinding | None]
] = ContextVar(
    "dnd_active_behavior_binding",
    default=(0, None),
)
_scoped_behavior_binding_gateway: ContextVar[
    tuple[int, RuntimeBehaviorBindingGateway | None]
] = ContextVar(
    "dnd_scoped_behavior_binding_gateway",
    default=(0, None),
)


def install_runtime_behavior_binding_gateway(
    gateway: RuntimeBehaviorBindingGateway,
    *,
    content_set_digest: str,
) -> RuntimeBehaviorBindingGateway:
    """Install the one content-authenticated behavior gateway for this process.

    Equivalent content-system bootstraps are idempotent. A different content
    set cannot silently replace the behavior authority already used by live
    engine objects.
    """
    global _runtime_behavior_binding_gateway
    global _runtime_behavior_binding_content_set_digest

    existing = _runtime_behavior_binding_gateway
    if existing is None:
        _runtime_behavior_binding_gateway = gateway
        _runtime_behavior_binding_content_set_digest = content_set_digest
        return gateway
    if _runtime_behavior_binding_content_set_digest == content_set_digest:
        return existing
    raise RuntimeError(
        "A runtime behavior binding gateway is already installed for a "
        "different content set",
    )


@contextmanager
def runtime_behavior_binding_gateway(
    gateway: RuntimeBehaviorBindingGateway,
) -> Iterator[None]:
    """Use one isolated runtime's cold behavior admission during materialization."""
    generation = _runtime_behavior_context_generation
    token = _scoped_behavior_binding_gateway.set((generation, gateway))
    try:
        yield
    finally:
        if generation == _runtime_behavior_context_generation:
            _scoped_behavior_binding_gateway.reset(token)
        else:
            _scoped_behavior_binding_gateway.set((
                _runtime_behavior_context_generation,
                None,
            ))


def _current_behavior_binding_gateway(
) -> RuntimeBehaviorBindingGateway | None:
    generation, scoped = _scoped_behavior_binding_gateway.get()
    if generation != _runtime_behavior_context_generation:
        scoped = None
    if scoped is not None:
        return scoped
    return _runtime_behavior_binding_gateway


def bind_runtime_behavior(
    behavior: object,
    *,
    current_binding: BehaviorBinding | None,
    runtime_owner_uuid: UUID,
) -> BehaviorBinding | None:
    """Bind through installed cold admission, otherwise remain explicit/unbound."""
    if current_binding is not None:
        if current_binding.runtime_owner_uuid != runtime_owner_uuid:
            raise ValueError(
                "Runtime behavior is already bound to a different owner",
            )
        return current_binding
    gateway = _current_behavior_binding_gateway()
    if gateway is None:
        return None
    return gateway.bind_independent(
        behavior,
        runtime_owner_uuid=runtime_owner_uuid,
    )


def bind_runtime_root_owned_behavior(
    behavior: object,
    *,
    current_binding: BehaviorBinding | None,
    origin_root_id: str | None,
    runtime_owner_uuid: UUID,
) -> BehaviorBinding | None:
    """Bind explicit root-owned behavior, otherwise preserve independence."""
    if current_binding is not None:
        if current_binding.runtime_owner_uuid != runtime_owner_uuid:
            raise ValueError(
                "Runtime behavior is already bound to a different owner",
            )
        return current_binding
    if origin_root_id is None:
        return bind_runtime_behavior(
            behavior,
            current_binding=current_binding,
            runtime_owner_uuid=runtime_owner_uuid,
        )
    gateway = _current_behavior_binding_gateway()
    if gateway is None:
        raise RuntimeError(
            "Content system is not installed for declared runtime behavior",
        )
    binding = gateway.bind_root_owned(
        behavior,
        origin_root_id=origin_root_id,
        runtime_owner_uuid=runtime_owner_uuid,
    )
    if binding is not None:
        return binding
    return gateway.bind_independent(
        behavior,
        runtime_owner_uuid=runtime_owner_uuid,
    )


def bind_runtime_behavior_child(
    behavior: object,
    *,
    provider_binding: BehaviorBinding | None = None,
    provided_by_id: str | None = None,
    origin_root_id: str | None = None,
    runtime_owner_uuid: UUID,
) -> BehaviorBinding:
    """Explicitly bind one declared child through an authenticated provider.

    This operation is intentionally not implicit in ``bind_runtime_behavior``.
    Provider-owned actions and conditions require a reviewed dependency edge;
    ordinary direct application continues to bind independently until each
    provider graph is migrated.
    """
    gateway = _current_behavior_binding_gateway()
    if gateway is None:
        raise RuntimeError(
            "Content system is not installed for provider-owned behavior",
        )
    if provider_binding is not None:
        if provided_by_id is not None or origin_root_id is not None:
            raise ValueError("Use either a provider binding or direct IDs")
        return gateway.bind_child(
            behavior,
            provider_binding=provider_binding,
            runtime_owner_uuid=runtime_owner_uuid,
        )
    if provided_by_id is None:
        raise ValueError("Direct behavior child requires provided_by_id")
    return gateway.bind_direct_child(
        behavior,
        provided_by_id=provided_by_id,
        origin_root_id=origin_root_id,
        runtime_owner_uuid=runtime_owner_uuid,
    )


@contextmanager
def runtime_behavior_provider(
    binding: BehaviorBinding | None,
) -> Iterator[None]:
    """Expose one immutable behavior fact while it creates causal children.

    An intentionally undeclared internal behavior is still a causal boundary.
    It must not let an outer action, condition, or handler become the implicit
    provider of private children created inside that behavior.
    """
    generation = _runtime_behavior_context_generation
    token = _active_behavior_binding.set((generation, binding))
    try:
        yield
    finally:
        if generation == _runtime_behavior_context_generation:
            _active_behavior_binding.reset(token)
        else:
            _active_behavior_binding.set((
                _runtime_behavior_context_generation,
                None,
            ))


def active_runtime_behavior_binding() -> BehaviorBinding | None:
    """Return the exact binding of the behavior active in this causal scope.

    Events use this read-only leaf to freeze authored identity before queue
    admission.  The runtime behavior object itself never crosses the event or
    transport boundary.
    """
    generation, binding = _active_behavior_binding.get()
    if generation != _runtime_behavior_context_generation:
        return None
    return binding


def reset_runtime_behavior_context() -> None:
    """Clear encounter-local behavior scopes without uninstalling cold content."""
    global _runtime_behavior_context_generation

    _runtime_behavior_context_generation += 1
    cleared = (_runtime_behavior_context_generation, None)
    _active_behavior_binding.set(cleared)
    _scoped_behavior_binding_gateway.set(cleared)


def bind_runtime_action_before_admission(
    action: object,
    *,
    current_binding: BehaviorBinding | None,
    runtime_owner_uuid: UUID,
    origin_root_id: str | None = None,
) -> BehaviorBinding | None:
    """Bind an independent or provider-granted action before registration.

    An action created while a bound action or condition is the active causal
    provider retains its own exact definition and names that provider as the
    grant source. Ordinary entity-composition actions bind independently.
    """
    if current_binding is not None:
        if current_binding.runtime_owner_uuid != runtime_owner_uuid:
            raise ValueError(
                "Runtime behavior is already bound to a different owner",
            )
        return current_binding

    provider_binding = active_runtime_behavior_binding()
    if provider_binding is None:
        return bind_runtime_root_owned_behavior(
            action,
            current_binding=current_binding,
            origin_root_id=origin_root_id,
            runtime_owner_uuid=runtime_owner_uuid,
        )
    gateway = _current_behavior_binding_gateway()
    if gateway is None:
        raise RuntimeError(
            "Content system is not installed for a bound behavior provider",
        )
    return gateway.bind_child(
        action,
        provider_binding=provider_binding,
        runtime_owner_uuid=runtime_owner_uuid,
    )


def bind_runtime_handler_before_admission(
    handler: object,
    *,
    current_binding: BehaviorBinding | None,
    runtime_owner_uuid: UUID,
) -> BehaviorBinding | None:
    """Bind a declared or provider-owned handler before any runtime index sees it."""
    if current_binding is not None:
        if current_binding.runtime_owner_uuid != runtime_owner_uuid:
            raise ValueError(
                "Runtime behavior is already bound to a different owner",
            )
        return current_binding

    provider_binding = active_runtime_behavior_binding()
    if provider_binding is None:
        return bind_runtime_behavior(
            handler,
            current_binding=current_binding,
            runtime_owner_uuid=runtime_owner_uuid,
        )
    gateway = _current_behavior_binding_gateway()
    if gateway is None:
        raise RuntimeError(
            "Content system is not installed for a bound behavior provider",
        )
    return gateway.bind_child(
        handler,
        provider_binding=provider_binding,
        runtime_owner_uuid=runtime_owner_uuid,
    )


class HandlerDispatchOutcome(str, Enum):
    """Observable result of one handler invocation by the event queue."""

    NO_EFFECT = "no_effect"
    EMITTED_EVENTS = "emitted_events"
    MODIFIED_EVENT = "modified_event"
    CANCELED_EVENT = "canceled_event"


class HandlerDispatchEvidence(BaseModel):
    """Passive evidence for one matched event or spatial handler invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dispatch_index: int = Field(
        ge=0,
        description="Monotonic handler-dispatch index in the active engine runtime.",
    )
    handler_semantic_key: str = Field(
        min_length=1,
        description="Stable semantic identity declared by the handler.",
    )
    handler_name: str = Field(
        min_length=1,
        description="Human-readable handler name retained for diagnosis.",
    )
    content_kind: RuntimeBehaviorKind = Field(
        description="Rules-behavior family represented by the handler.",
    )
    behavior_id: str | None = Field(
        default=None,
        description="Primitive identity of the dispatched handler rule.",
    )
    provided_by_id: str | None = Field(
        default=None,
        description="Primitive identity of the handler's semantic provider.",
    )
    origin_root_id: str | None = Field(
        default=None,
        description="Optional durable primitive root of the provider chain.",
    )
    handler_uuid: str = Field(
        min_length=1,
        description="Runtime handler UUID used only for within-match correlation.",
    )
    source_entity_uuid: Optional[str] = Field(
        default=None,
        description="Runtime UUID of the entity or block that owns the handler.",
    )
    event_uuid: str = Field(
        min_length=1,
        description="Runtime UUID of the event version supplied to the handler.",
    )
    lineage_uuid: str = Field(
        min_length=1,
        description="Runtime causal-lineage UUID of the triggering event.",
    )
    event_type: str = Field(
        min_length=1,
        description="Engine event type that matched the handler.",
    )
    event_phase: str = Field(
        min_length=1,
        description="Engine event phase that matched the handler.",
    )
    outcome: HandlerDispatchOutcome = Field(
        description="Observable effect class of the invocation.",
    )
    emitted_event_count: int = Field(
        ge=0,
        description="Number of engine event versions appended during the handler call.",
    )

    @field_validator("behavior_id", "provided_by_id", "origin_root_id")
    @classmethod
    def _validate_behavior_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_namespaced_id(value, "handler dispatch identity")

    @model_validator(mode="after")
    def _validate_behavior_fact(self) -> "HandlerDispatchEvidence":
        if (self.behavior_id is None) != (self.provided_by_id is None):
            raise ValueError(
                "behavior_id and provided_by_id must be present together"
            )
        if self.behavior_id is None and self.origin_root_id is not None:
            raise ValueError("origin_root_id requires a behavior identity")
        return self

    @property
    def effected(self) -> bool:
        """Whether the invocation produced an observable engine effect."""
        return self.outcome != HandlerDispatchOutcome.NO_EFFECT


@dataclass(frozen=True, slots=True)
class EffectiveHandlerPresentation:
    """Exact internal evidence for one reaction that changed engine state.

    This is deliberately not a transport model. The subjective mapper consumes
    it while the authoritative event batch is live and emits the closed,
    privacy-checked presentation DTO. Persisted subjective replays store that
    projected DTO rather than reconstructing handler execution later.
    """

    dispatch_index: int
    handler_name: str
    behavior_id: str
    provided_by_id: str
    origin_root_id: str | None
    source_entity_uuid: UUID
    triggering_event_uuid: UUID
    triggering_lineage_uuid: UUID
    emitted_lineage_uuids: tuple[UUID, ...]
    outcome: HandlerDispatchOutcome
