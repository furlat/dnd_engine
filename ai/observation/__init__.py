"""Session-subjective observation data for AI and controller integrations."""

from ai.observation.materializer import apply_observation_frame, materialize_snapshot
from ai.observation.models import (
    KnowledgeState,
    ObservationCombatantState,
    ObservationEncounterState,
    ObservationEntityFact,
    ObservationFrame,
    ObservationFramesResponse,
    ObservationFrameType,
    ObservationMaterializedState,
    ObservationObjectFact,
    ObservationObserverState,
    ObservationPatch,
    ObservationPatchType,
    ObservationSessionState,
    ObservationSnapshot,
    ObservationTileFact,
)
from ai.observation.projector import (
    ObservationAccessError,
    build_observation_snapshot,
    clear_observation_projection_cache,
    get_observation_cursor,
    iter_observation_frames,
)

__all__ = [
    "KnowledgeState",
    "ObservationAccessError",
    "ObservationCombatantState",
    "ObservationEncounterState",
    "ObservationEntityFact",
    "ObservationFrame",
    "ObservationFramesResponse",
    "ObservationFrameType",
    "ObservationMaterializedState",
    "ObservationObjectFact",
    "ObservationObserverState",
    "ObservationPatch",
    "ObservationPatchType",
    "ObservationSessionState",
    "ObservationSnapshot",
    "ObservationTileFact",
    "apply_observation_frame",
    "build_observation_snapshot",
    "clear_observation_projection_cache",
    "get_observation_cursor",
    "iter_observation_frames",
    "materialize_snapshot",
]
