"""Explicit policy and instrumentation composition for the reference service."""

from __future__ import annotations

from dataclasses import dataclass

from dnd.ai.instrumentation import (
    AIInstrumentationSink,
    BoundedAIInstrumentationSink,
)
from dnd.ai.policies.basic import CanonicalPolicyRegistry
from dnd.ai.registry import PolicyRegistry
from server.external_ai_registry import ExternalAIProviderRegistry
from services.ai_policy_server.policies import (
    register_external_basic_policy,
    register_external_tactical_policy,
)


DEFAULT_PROVIDER_ID = "reference.local"
DEFAULT_PROVIDER_CAPACITY = 32
DEFAULT_RESPONSE_CACHE_SIZE = 64


@dataclass(frozen=True, slots=True)
class AIPolicyServiceRuntime:
    """In-process seam shared by the HTTP app and integration tests."""

    provider: ExternalAIProviderRegistry
    policy_registry: CanonicalPolicyRegistry
    instrumentation_sink: AIInstrumentationSink

    def shutdown(self) -> None:
        """Close every provider assignment exactly once."""
        self.provider.shutdown()


def create_reference_policy_registry() -> CanonicalPolicyRegistry:
    """Compose provider-owned identities over reusable policy logic."""
    registry: CanonicalPolicyRegistry = PolicyRegistry()
    register_external_basic_policy(registry)
    register_external_tactical_policy(registry)
    return registry


def create_ai_policy_service_runtime(
    *,
    provider_id: str = DEFAULT_PROVIDER_ID,
    capacity: int = DEFAULT_PROVIDER_CAPACITY,
    response_cache_size: int = DEFAULT_RESPONSE_CACHE_SIZE,
    policy_registry: CanonicalPolicyRegistry | None = None,
    instrumentation_sink: AIInstrumentationSink | None = None,
) -> AIPolicyServiceRuntime:
    """Create one isolated provider runtime without opening a socket."""
    policies = policy_registry or create_reference_policy_registry()
    sink = instrumentation_sink or BoundedAIInstrumentationSink()
    provider = ExternalAIProviderRegistry(
        provider_id=provider_id,
        capacity=capacity,
        policy_registry=policies,
        response_cache_size=response_cache_size,
        instrumentation_sink=sink,
    )
    return AIPolicyServiceRuntime(
        provider=provider,
        policy_registry=policies,
        instrumentation_sink=sink,
    )


__all__ = [
    "AIPolicyServiceRuntime",
    "DEFAULT_PROVIDER_CAPACITY",
    "DEFAULT_PROVIDER_ID",
    "DEFAULT_RESPONSE_CACHE_SIZE",
    "create_ai_policy_service_runtime",
    "create_reference_policy_registry",
]
