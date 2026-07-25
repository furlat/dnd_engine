"""Reference multi-assignment external AI policy provider."""

from services.ai_policy_server.app import (
    app,
    create_ai_policy_service,
)
from services.ai_policy_server.composition import (
    AIPolicyServiceRuntime,
    create_ai_policy_service_runtime,
)
from services.ai_policy_server.policies import (
    EXTERNAL_BASIC_POLICY_DESCRIPTOR,
    EXTERNAL_BASIC_POLICY_ID,
    EXTERNAL_TACTICAL_POLICY_DESCRIPTOR,
    EXTERNAL_TACTICAL_POLICY_ID,
)


__all__ = [
    "AIPolicyServiceRuntime",
    "EXTERNAL_BASIC_POLICY_DESCRIPTOR",
    "EXTERNAL_BASIC_POLICY_ID",
    "EXTERNAL_TACTICAL_POLICY_DESCRIPTOR",
    "EXTERNAL_TACTICAL_POLICY_ID",
    "app",
    "create_ai_policy_service",
    "create_ai_policy_service_runtime",
]
