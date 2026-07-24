"""Dependency-neutral hosted-worker profiles for bundled AI placement."""

from server.agent_runtime.service import AgentExecutionMode
from server.hosted_worker import HostedWorkerApplication

from ai.service_identity import (
    EMBEDDED_SUBJECTIVE_SERVICE_ID,
    ISOLATED_SUBJECTIVE_SERVICE_ID,
)


EMBEDDED_AI_WORKER_APPLICATION = HostedWorkerApplication(
    import_path="ai.local_game_server:app",
    expected_agent_service_id=EMBEDDED_SUBJECTIVE_SERVICE_ID,
    expected_agent_execution_mode=AgentExecutionMode.EMBEDDED_THREAD,
)

ISOLATED_AI_WORKER_APPLICATION = HostedWorkerApplication(
    import_path="ai.isolated_game_server:app",
    expected_agent_service_id=ISOLATED_SUBJECTIVE_SERVICE_ID,
    expected_agent_execution_mode=AgentExecutionMode.ISOLATED_PROCESS,
)
