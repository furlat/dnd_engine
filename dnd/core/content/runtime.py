"""Runtime behavior identities and passive handler-dispatch evidence."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dnd.core.content.identities import ContentRef


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
    SPATIAL_EFFECT = "spatial_effect"
    SYSTEM = "system"
    UNCLASSIFIED = "unclassified"


class BehaviorBinding(BaseModel):
    """Immutable authored identity attached to one live rules behavior.

    The binding deliberately separates the behavior's own meaning from the
    definition that provided it and from an optional durable root. Runtime
    owner UUIDs remain encounter-local correlation facts; they are never
    durable content identity.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    definition_ref: ContentRef = Field(
        description="Exact authored definition describing this behavior.",
    )
    provided_by_ref: ContentRef = Field(
        description="Exact definition that installed or granted the behavior.",
    )
    origin_root_ref: ContentRef | None = Field(
        default=None,
        description=(
            "Optional constructible durable root from which the provider "
            "closure originated."
        ),
    )
    runtime_owner_uuid: UUID = Field(
        description=(
            "Encounter-local UUID of the entity, item, condition, or other "
            "block that owns this behavior instance."
        ),
    )


class RuntimeBehaviorOwner(Protocol):
    """Owned runtime surface shared by actions, conditions, and handlers."""

    behavior_binding: BehaviorBinding | None


class RuntimeHandlerOwner(RuntimeBehaviorOwner, Protocol):
    """Runtime behavior that additionally declares its exact owner UUID."""

    source_entity_uuid: UUID


class RuntimeItemBehaviorProvider(Protocol):
    """Minimal item surface permitted to own granted runtime behavior."""

    uuid: UUID
    content_ref: ContentRef | None


RuntimeBehaviorProvider = (
    RuntimeBehaviorOwner | RuntimeItemBehaviorProvider
)


class AuthoredBehaviorAttribution(BaseModel):
    """Transport-safe authored identity of one discoverable live behavior.

    This immutable projection intentionally excludes the encounter-local
    runtime owner. Action and handler discovery can therefore join directly
    to the content catalog without treating a transient UUID, display label,
    semantic key, or Python type as durable identity.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    definition_ref: ContentRef = Field(
        description="Exact authored definition describing the behavior.",
    )
    provided_by_ref: ContentRef = Field(
        description="Exact authored definition that installed the behavior.",
    )
    origin_root_ref: ContentRef | None = Field(
        default=None,
        description=(
            "Optional durable constructible root from which the provider "
            "closure originated."
        ),
    )

    @classmethod
    def from_binding(
        cls,
        binding: BehaviorBinding,
    ) -> "AuthoredBehaviorAttribution":
        """Drop runtime correlation while preserving exact authored closure."""
        return cls(
            definition_ref=binding.definition_ref,
            provided_by_ref=binding.provided_by_ref,
            origin_root_ref=binding.origin_root_ref,
        )


class RuntimeBehaviorBindingGateway(Protocol):
    """Dependency-neutral adapter implemented by the installed content system."""

    def bind_independent(
        self,
        behavior: RuntimeBehaviorOwner,
        *,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        """Bind one directly declared behavior with itself as provider."""
        ...

    def bind_child(
        self,
        behavior: RuntimeBehaviorOwner,
        *,
        provider: RuntimeBehaviorProvider,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        """Bind one runtime child through an exact active provider."""
        ...

    def bind_root_owned(
        self,
        behavior: RuntimeBehaviorOwner,
        *,
        origin_root_ref: ContentRef,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding | None:
        """Bind an explicitly root-owned behavior or decline ordinary ones."""
        ...


_DECLARATION_ATTRIBUTE = "__dnd_content_declaration__"
_runtime_behavior_binding_gateway: RuntimeBehaviorBindingGateway | None = None
_runtime_behavior_binding_content_set_digest: str | None = None
_active_behavior_provider: ContextVar[RuntimeBehaviorOwner | None] = ContextVar(
    "dnd_active_behavior_provider",
    default=None,
)
_scoped_behavior_binding_gateway: ContextVar[
    RuntimeBehaviorBindingGateway | None
] = ContextVar(
    "dnd_scoped_behavior_binding_gateway",
    default=None,
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


def has_direct_behavior_declaration(
    behavior: RuntimeBehaviorOwner,
) -> bool:
    """Return whether the runtime class owns an exact declaration."""
    namespace = getattr(type(behavior), "__dict__", None)
    return (
        namespace is not None
        and namespace.get(_DECLARATION_ATTRIBUTE) is not None
    )


@contextmanager
def runtime_behavior_binding_gateway(
    gateway: RuntimeBehaviorBindingGateway,
) -> Iterator[None]:
    """Use one isolated runtime's registry during its materialization call."""
    token = _scoped_behavior_binding_gateway.set(gateway)
    try:
        yield
    finally:
        _scoped_behavior_binding_gateway.reset(token)


def _current_behavior_binding_gateway(
) -> RuntimeBehaviorBindingGateway | None:
    scoped = _scoped_behavior_binding_gateway.get()
    if scoped is not None:
        return scoped
    return _runtime_behavior_binding_gateway


def bind_runtime_behavior(
    behavior: RuntimeBehaviorOwner,
    *,
    runtime_owner_uuid: UUID,
) -> BehaviorBinding | None:
    """Bind a migrated behavior, leaving undeclared residuals explicit.

    Decorated behaviors fail closed when startup did not install the content
    gateway. Undecorated legacy/custom behaviors remain visibly unbound rather
    than acquiring a Python-path identity disguised as authored content.
    """
    existing = behavior.behavior_binding
    if isinstance(existing, BehaviorBinding):
        if existing.runtime_owner_uuid != runtime_owner_uuid:
            raise ValueError(
                "Runtime behavior is already bound to a different owner",
            )
        return existing
    if not has_direct_behavior_declaration(behavior):
        return None
    gateway = _current_behavior_binding_gateway()
    if gateway is None:
        raise RuntimeError(
            "Content system is not installed for declared runtime behavior",
        )
    return gateway.bind_independent(
        behavior,
        runtime_owner_uuid=runtime_owner_uuid,
    )


def bind_runtime_root_owned_behavior(
    behavior: RuntimeBehaviorOwner,
    *,
    origin_root_ref: ContentRef | None,
    runtime_owner_uuid: UUID,
) -> BehaviorBinding | None:
    """Bind explicit root-owned behavior, otherwise preserve independence."""
    existing = behavior.behavior_binding
    if isinstance(existing, BehaviorBinding):
        if existing.runtime_owner_uuid != runtime_owner_uuid:
            raise ValueError(
                "Runtime behavior is already bound to a different owner",
            )
        return existing
    if origin_root_ref is None or not has_direct_behavior_declaration(behavior):
        return bind_runtime_behavior(
            behavior,
            runtime_owner_uuid=runtime_owner_uuid,
        )
    gateway = _current_behavior_binding_gateway()
    if gateway is None:
        raise RuntimeError(
            "Content system is not installed for declared runtime behavior",
        )
    binding = gateway.bind_root_owned(
        behavior,
        origin_root_ref=origin_root_ref,
        runtime_owner_uuid=runtime_owner_uuid,
    )
    if binding is not None:
        return binding
    return gateway.bind_independent(
        behavior,
        runtime_owner_uuid=runtime_owner_uuid,
    )


def bind_runtime_behavior_child(
    behavior: RuntimeBehaviorOwner,
    *,
    provider: RuntimeBehaviorProvider,
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
    return gateway.bind_child(
        behavior,
        provider=provider,
        runtime_owner_uuid=runtime_owner_uuid,
    )


@contextmanager
def runtime_behavior_provider(
    behavior: RuntimeBehaviorOwner,
) -> Iterator[None]:
    """Expose one behavior while it creates children, masking unbound scopes.

    An intentionally undeclared internal behavior is still a causal boundary.
    It must not let an outer action, condition, or handler become the implicit
    provider of private children created inside that behavior.
    """
    binding = behavior.behavior_binding
    provider = behavior if isinstance(binding, BehaviorBinding) else None
    token = _active_behavior_provider.set(provider)
    try:
        yield
    finally:
        _active_behavior_provider.reset(token)


def active_runtime_behavior_binding() -> BehaviorBinding | None:
    """Return the exact binding of the behavior active in this causal scope.

    Events use this read-only leaf to freeze authored identity before queue
    admission.  The runtime behavior object itself never crosses the event or
    transport boundary.
    """
    provider = _active_behavior_provider.get()
    binding = None if provider is None else provider.behavior_binding
    return binding if isinstance(binding, BehaviorBinding) else None


def bind_runtime_action_before_admission(
    action: RuntimeBehaviorOwner,
    *,
    runtime_owner_uuid: UUID,
    origin_root_ref: ContentRef | None = None,
) -> BehaviorBinding | None:
    """Bind an independent or provider-granted action before registration.

    An action created while a bound action or condition is the active causal
    provider retains its own exact definition and names that provider as the
    grant source. Ordinary entity-composition actions bind independently.
    """
    existing = action.behavior_binding
    if isinstance(existing, BehaviorBinding):
        if existing.runtime_owner_uuid != runtime_owner_uuid:
            raise ValueError(
                "Runtime behavior is already bound to a different owner",
            )
        return existing

    provider = _active_behavior_provider.get()
    if provider is None:
        return bind_runtime_root_owned_behavior(
            action,
            origin_root_ref=origin_root_ref,
            runtime_owner_uuid=runtime_owner_uuid,
        )

    provider_binding = provider.behavior_binding
    if not isinstance(provider_binding, BehaviorBinding):
        raise RuntimeError("Active runtime action provider is not bound")
    gateway = _current_behavior_binding_gateway()
    if gateway is None:
        raise RuntimeError(
            "Content system is not installed for a bound behavior provider",
        )
    return gateway.bind_child(
        action,
        provider=provider,
        runtime_owner_uuid=runtime_owner_uuid,
    )


def bind_runtime_handler_before_admission(
    handler: RuntimeHandlerOwner,
) -> BehaviorBinding | None:
    """Bind a declared or provider-owned handler before any runtime index sees it."""
    owner_uuid = handler.source_entity_uuid
    existing = handler.behavior_binding
    if isinstance(existing, BehaviorBinding):
        if existing.runtime_owner_uuid != owner_uuid:
            raise ValueError(
                "Runtime behavior is already bound to a different owner",
            )
        return existing

    provider = _active_behavior_provider.get()
    if provider is None:
        return bind_runtime_behavior(
            handler,
            runtime_owner_uuid=owner_uuid,
        )

    provider_binding = provider.behavior_binding
    if not isinstance(provider_binding, BehaviorBinding):
        raise RuntimeError("Active runtime behavior provider is not bound")
    gateway = _current_behavior_binding_gateway()
    if gateway is None:
        raise RuntimeError(
            "Content system is not installed for a bound behavior provider",
        )
    return gateway.bind_child(
        handler,
        provider=provider,
        runtime_owner_uuid=owner_uuid,
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
    behavior_binding: BehaviorBinding
    source_entity_uuid: UUID
    triggering_event_uuid: UUID
    triggering_lineage_uuid: UUID
    emitted_lineage_uuids: tuple[UUID, ...]
    outcome: HandlerDispatchOutcome
