"""Identity-independent ordering keys for deterministic subjective replay."""

from __future__ import annotations

from typing import Optional

from server.agent_protocol.observation import ObservationEntityFact, ObservationObjectFact


Position = tuple[int, int]


def position_replay_token(position: Optional[Position]) -> str:
    """Return a stable key for one disclosed or unknown position."""
    if position is None:
        return "position=unknown"
    return f"position={position[0]},{position[1]}"


def entity_fact_replay_token(entity: ObservationEntityFact) -> str:
    """Return the semantic identity disclosed for entity tie ordering."""
    return "|".join((
        "entity",
        position_replay_token(entity.position),
        f"name={entity.name.casefold()}",
    ))


def object_fact_replay_token(obj: ObservationObjectFact) -> str:
    """Return the semantic identity disclosed for object tie ordering."""
    return "|".join((
        "object",
        position_replay_token(obj.position),
        f"name={obj.name.casefold()}",
    ))
