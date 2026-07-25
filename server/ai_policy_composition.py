"""Explicit native-policy composition for shipped server applications."""

from dnd.ai.policies.basic import (
    BASIC_POLICY_ID,
    CanonicalPolicyRegistry,
    register_basic_policy,
)
from dnd.ai.registry import PolicyRegistry

from custom_ai.tactical import register_tactical_policy


DEFAULT_NATIVE_POLICY_ID = BASIC_POLICY_ID


def create_server_native_policy_registry() -> CanonicalPolicyRegistry:
    """Build the factory-only registry shared by one server process."""
    registry: CanonicalPolicyRegistry = PolicyRegistry()
    register_basic_policy(registry)
    register_tactical_policy(registry)
    return registry


SERVER_NATIVE_POLICY_REGISTRY = create_server_native_policy_registry()
SERVER_NATIVE_POLICY_DESCRIPTORS = SERVER_NATIVE_POLICY_REGISTRY.descriptors()
