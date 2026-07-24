"""Multi-game gateway with nested process isolation for every AI session."""

from ai.game_server_profiles import ISOLATED_AI_WORKER_APPLICATION
from server.game_gateway import create_gateway_app


app = create_gateway_app(
    worker_application=ISOLATED_AI_WORKER_APPLICATION,
)
