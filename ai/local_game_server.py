"""Playable standalone server with the embedded subjective AI registered.

Importing this composition loads the policy once during backend startup.  Game
creation then starts only lightweight, independently owned policy threads.
"""

from __future__ import annotations

from typing import Sequence

from ai.in_process_agent_service import EmbeddedSubjectiveAgentService
from server import event_server


embedded_agent_service = EmbeddedSubjectiveAgentService()
event_server.agent_service_manager.register_service(embedded_agent_service)

app = event_server.app


def main(argv: Sequence[str] | None = None) -> None:
    """Run the configured local game server."""
    event_server.main(argv)


if __name__ == "__main__":
    main()
