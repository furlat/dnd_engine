"""Local server composition with one isolated AI process per session."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from ai.service_identity import ISOLATED_SUBJECTIVE_SERVICE_ID
from server import event_server
from server.agent_runtime.service import AgentLaunchRequest
from server.agent_runtime.subprocess_service import (
    AgentProcessSpec,
    SubprocessAgentService,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_AGENT_MODULE = "ai.external_agent"


class LocalSubjectiveProcessSpecBuilder:
    """Build isolated process specifications for the bundled policy."""

    service_id = ISOLATED_SUBJECTIVE_SERVICE_ID

    def preflight(self, required_agents: int) -> None:
        """Verify the bundled executable source before game replacement."""
        if required_agents <= 0:
            raise ValueError("required_agents must be positive")
        agent_source = Path(__file__).with_name("external_agent.py")
        if not agent_source.is_file():
            raise RuntimeError(f"Bundled agent entry point is missing: {agent_source}")

    def build_process_spec(self, request: AgentLaunchRequest) -> AgentProcessSpec:
        """Build the exact direct-attachment agent command."""
        argv = (
            sys.executable,
            "-m",
            EXTERNAL_AGENT_MODULE,
            "--base-url",
            request.base_url.rstrip("/"),
            "--session-id",
            request.session_id,
            "--spawned-at",
            str(request.spawned_at),
        )
        if request.unix_socket_path is not None:
            argv = (*argv, "--unix-socket", request.unix_socket_path)
        if request.readiness_token is None:
            raise ValueError("Managed agent launch request has no readiness token")
        argv = (*argv, "--readiness-token", request.readiness_token)
        return AgentProcessSpec(argv=argv, cwd=REPOSITORY_ROOT)


isolated_agent_service = SubprocessAgentService(
    LocalSubjectiveProcessSpecBuilder()
)
event_server.agent_service_manager.register_service(isolated_agent_service)

app = event_server.app


def main(argv: Sequence[str] | None = None) -> None:
    """Run the isolated-agent local game server."""
    event_server.main(argv)


if __name__ == "__main__":
    main()
