"""External AI subprocess support for NeuroDragon controllers."""

from ai.external.policy import AgentCommand, AgentCommandType, choose_external_melee_command
from ai.external.state import (
    ExternalActionRow,
    ExternalActionTarget,
    ExternalAgentState,
    ExternalEntity,
    ExternalKnownObject,
    reduce_external_agent_state,
)

__all__ = [
    "AgentCommand",
    "AgentCommandType",
    "ExternalActionRow",
    "ExternalActionTarget",
    "ExternalAgentState",
    "ExternalEntity",
    "ExternalKnownObject",
    "choose_external_melee_command",
    "reduce_external_agent_state",
]
