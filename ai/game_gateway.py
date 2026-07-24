"""Multi-game gateway whose isolated workers embed the bundled AI policy.

Each hosted game already owns a dedicated worker process.  Importing the
policy inside that worker preserves game-level process isolation while
avoiding a second Python interpreter and policy import for every AI side.
"""

from __future__ import annotations

from ai.game_server_profiles import EMBEDDED_AI_WORKER_APPLICATION
from server.game_gateway import create_gateway_app

app = create_gateway_app(
    worker_application=EMBEDDED_AI_WORKER_APPLICATION,
)
