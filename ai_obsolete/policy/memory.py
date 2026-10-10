"""Actor-scoped policy memory that never stores world or epoch rows."""

from __future__ import annotations

from typing import Dict, Optional, Set, Tuple

from pydantic import BaseModel, Field

from ai.policy.contracts import (
    PolicyContext,
    PolicyControlMemoryView,
    PolicyExecutionConstraints,
    RememberedContactSearchState,
)
from dnd.ai.contracts.semantics import ActionTag, CapabilitySelector, TargetAllocation


class SemanticActionGoal(BaseModel):
    """Future action meaning retained without guessing a legal row id."""

    required_tags: frozenset[ActionTag] = Field(description="Semantic tags required from the future legal row.")
    target_uuid: str = Field(description="Subjective target identity the future row must affect.")
    required_target_allocation: Optional[TargetAllocation] = Field(
        default=None,
        description="Target-allocation shape required from the fresh authoritative row.",
    )
    minimum_selected_targets: int = Field(
        default=1,
        ge=1,
        description="Minimum target selections required from the fresh proposal.",
    )


class RoutineProgress(BaseModel):
    """Accepted multi-epoch progress retained through revalidation and exhaustion."""

    routine_id: str = Field(description="Stable routine definition id.")
    step_id: str = Field(description="Current abstract step id.")
    started_epoch_index: int = Field(ge=0, description="Epoch where the routine started.")
    target_uuid: Optional[str] = Field(default=None, description="Subjective target identity when relevant.")
    target_position: Optional[Tuple[int, int]] = Field(default=None, description="Subjective target position when relevant.")
    goal: Optional[SemanticActionGoal] = Field(default=None, description="Abstract follow-up action goal when relevant.")
    enablers_used: int = Field(default=0, ge=0, description="Accepted enabling commands used by this routine.")
    started_round_number: Optional[int] = Field(default=None, ge=0, description="Round where same-turn progress began.")
    started_turn_index: Optional[int] = Field(default=None, ge=0, description="Turn index where same-turn progress began.")
    consumption_selector: Optional[CapabilitySelector] = Field(
        default=None,
        description="Accepted action shape that consumes a temporary capability transformation.",
    )
    last_target_distance_feet: Optional[int] = Field(
        default=None,
        ge=0,
        description="Distance after the latest accepted progress step when the routine pursues a target.",
    )
    mobility_extensions_used_this_turn: int = Field(
        default=0,
        ge=0,
        description="Accepted mobility-extension commands used in the currently recorded turn.",
    )
    mobility_extension_round_number: Optional[int] = Field(
        default=None,
        ge=0,
        description="Round associated with the per-turn mobility-extension counter.",
    )
    mobility_extension_turn_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Turn index associated with the per-turn mobility-extension counter.",
    )


class MaintainMinimumDistanceIntention(BaseModel):
    """Accepted same-turn intent to preserve distance from one known target."""

    target_uuid: str = Field(description="Subjective target identity anchoring the floor.")
    target_position: Tuple[int, int] = Field(description="Latest visible or remembered target position.")
    minimum_distance_cells: int = Field(
        ge=0,
        description="Minimum actor-target grid distance retained for this turn.",
    )
    started_round_number: int = Field(ge=0, description="Round where the spacing command was accepted.")
    started_turn_index: int = Field(ge=0, description="Turn index where the spacing command was accepted.")


class ActorPolicyMemory(BaseModel):
    """Non-derivable control memory owned by one actor and policy."""

    session_id: str = Field(description="Owning controller session.")
    actor_uuid: str = Field(description="Actor whose control state is stored.")
    policy_id: str = Field(description="Policy definition owning this memory.")
    active_routine: Optional[RoutineProgress] = Field(default=None, description="Current abstract routine.")
    last_routine_revalidation_status: Optional[str] = Field(
        default=None,
        description="Most recent typed routine revalidation outcome.",
    )
    last_routine_revalidation_reason: Optional[str] = Field(
        default=None,
        description="Explanation for the most recent routine revalidation.",
    )
    remembered_search_failures: Dict[str, int] = Field(default_factory=dict, description="Bounded failed search counts by contact UUID.")
    remembered_search_positions: Dict[str, Tuple[int, int]] = Field(default_factory=dict, description="Positions associated with search counts.")
    remembered_search_visited_positions: Dict[str, Set[Tuple[int, int]]] = Field(
        default_factory=dict,
        description="Subjective destinations already inspected for each remembered contact.",
    )
    failed_action_round_number: Optional[int] = Field(
        default=None,
        ge=0,
        description="Round owning turn-local canceled-action exclusions.",
    )
    failed_action_turn_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Turn index owning turn-local canceled-action exclusions.",
    )
    canceled_row_ids: Set[str] = Field(
        default_factory=set,
        description="Rows whose admitted engine action canceled during the current turn.",
    )
    canceled_semantic_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Canceled attempts by semantic family during the current turn.",
    )
    same_turn_spacing_intention: Optional[MaintainMinimumDistanceIntention] = Field(
        default=None,
        description="Accepted maintain-minimum-distance intent for the current turn.",
    )


class PolicyMemoryStore:
    """In-memory policy state isolated by session, actor, and policy id."""

    def __init__(self) -> None:
        """Create an empty actor-scoped store."""
        self._memories: dict[tuple[str, str, str], ActorPolicyMemory] = {}

    def for_actor(self, session_id: str, actor_uuid: str, policy_id: str) -> ActorPolicyMemory:
        """Return mutable memory owned exclusively by one actor-policy tuple."""
        key = (session_id, actor_uuid, policy_id)
        memory = self._memories.get(key)
        if memory is None:
            memory = ActorPolicyMemory(session_id=session_id, actor_uuid=actor_uuid, policy_id=policy_id)
            self._memories[key] = memory
        return memory

    def clear_session(self, session_id: str) -> None:
        """Remove policy memories for one controller session."""
        for key in [key for key in self._memories if key[0] == session_id]:
            self._memories.pop(key, None)


def reconcile_policy_memory(
    context: PolicyContext,
    memory: ActorPolicyMemory,
) -> None:
    """Reconcile bounded remembered-contact search with current subjective facts."""
    context.validate_alignment()
    visible_uuids = set(context.facts.contacts.visible_hostile_uuids)
    for entity_uuid in visible_uuids:
        memory.remembered_search_failures.pop(entity_uuid, None)
        memory.remembered_search_positions.pop(entity_uuid, None)
        memory.remembered_search_visited_positions.pop(entity_uuid, None)

    remembered_positions = {
        entity_uuid: entity.position
        for entity_uuid in context.facts.contacts.remembered_hostile_uuids
        for entity in [context.world.known_entities.get(entity_uuid)]
        if entity is not None and entity.position is not None
    }
    for entity_uuid, position in remembered_positions.items():
        previous_position = memory.remembered_search_positions.get(entity_uuid)
        if previous_position is None:
            memory.remembered_search_positions[entity_uuid] = position
            memory.remembered_search_visited_positions.setdefault(entity_uuid, set())
        elif previous_position != position:
            memory.remembered_search_failures.pop(entity_uuid, None)
            memory.remembered_search_positions[entity_uuid] = position
            memory.remembered_search_visited_positions[entity_uuid] = set()
    for entity_uuid in list(memory.remembered_search_positions):
        if entity_uuid not in remembered_positions and entity_uuid not in visible_uuids:
            memory.remembered_search_failures.pop(entity_uuid, None)
            memory.remembered_search_positions.pop(entity_uuid, None)
            memory.remembered_search_visited_positions.pop(entity_uuid, None)


def reconcile_turn_action_failures(
    context: PolicyContext,
    memory: ActorPolicyMemory,
) -> None:
    """Reset admitted-but-canceled exclusions when the authoritative turn changes."""
    context.validate_alignment()
    epoch = context.world.current_epoch
    if epoch is None:
        return
    if (
        memory.failed_action_round_number == epoch.round_number
        and memory.failed_action_turn_index == epoch.turn_index
    ):
        return
    memory.failed_action_round_number = epoch.round_number
    memory.failed_action_turn_index = epoch.turn_index
    memory.canceled_row_ids.clear()
    memory.canceled_semantic_counts.clear()


def execution_constraints_with_memory(
    supplied: PolicyExecutionConstraints,
    memory: ActorPolicyMemory,
) -> PolicyExecutionConstraints:
    """Merge caller exclusions with authoritative canceled-action memory."""
    blocked_semantics = {
        semantic_key
        for semantic_key, count in memory.canceled_semantic_counts.items()
        if count >= 2
    }
    return PolicyExecutionConstraints(
        blocked_row_ids=supplied.blocked_row_ids | frozenset(memory.canceled_row_ids),
        blocked_semantic_keys=supplied.blocked_semantic_keys | frozenset(blocked_semantics),
        blocked_action_categories=supplied.blocked_action_categories,
    )


def record_canceled_action(
    memory: ActorPolicyMemory,
    *,
    row_id: str,
    semantic_key: Optional[str],
) -> None:
    """Retain one admitted engine cancellation for current-turn re-ranking."""
    memory.canceled_row_ids.add(row_id)
    if semantic_key is not None:
        memory.canceled_semantic_counts[semantic_key] = (
            memory.canceled_semantic_counts.get(semantic_key, 0) + 1
        )


def record_remembered_investigation(
    memory: ActorPolicyMemory,
    *,
    entity_uuid: str,
    destination: Tuple[int, int],
) -> None:
    """Record one completed movement that did not yet reacquire a contact."""
    memory.remembered_search_failures[entity_uuid] = (
        memory.remembered_search_failures.get(entity_uuid, 0) + 1
    )
    memory.remembered_search_visited_positions.setdefault(entity_uuid, set()).add(destination)


def policy_control_memory_view(memory: ActorPolicyMemory) -> PolicyControlMemoryView:
    """Freeze mutable actor memory into the shared policy input contract."""
    searches = [
        RememberedContactSearchState(
            entity_uuid=entity_uuid,
            last_known_position=position,
            completed_investigations=memory.remembered_search_failures.get(entity_uuid, 0),
            investigated_positions=tuple(sorted(
                memory.remembered_search_visited_positions.get(entity_uuid, set())
            )),
        )
        for entity_uuid, position in memory.remembered_search_positions.items()
    ]
    return PolicyControlMemoryView(
        remembered_contact_searches=tuple(sorted(searches, key=lambda state: state.entity_uuid)),
    )


def revalidate_same_turn_spacing_intention(
    context: PolicyContext,
    memory: ActorPolicyMemory,
) -> Optional[MaintainMinimumDistanceIntention]:
    """Refresh one same-turn spacing target or expire invalid memory."""
    context.validate_alignment()
    intention = memory.same_turn_spacing_intention
    if intention is None:
        return None
    epoch = context.world.current_epoch
    assert epoch is not None
    if (
        epoch.round_number != intention.started_round_number
        or epoch.turn_index != intention.started_turn_index
    ):
        memory.same_turn_spacing_intention = None
        return None
    known_hostiles = {
        *context.facts.contacts.visible_hostile_uuids,
        *context.facts.contacts.remembered_hostile_uuids,
    }
    target = context.world.known_entities.get(intention.target_uuid)
    if (
        intention.target_uuid not in known_hostiles
        or target is None
        or target.is_dead is True
        or target.position is None
    ):
        memory.same_turn_spacing_intention = None
        return None
    if target.position != intention.target_position:
        intention = intention.model_copy(update={"target_position": target.position})
        memory.same_turn_spacing_intention = intention
    return intention


def suppressed_remembered_enemy_uuids(
    memory: ActorPolicyMemory,
    remembered_search_limit: int,
) -> set[str]:
    """Return contacts whose bounded exact-position investigation is exhausted."""
    return {
        entity_uuid
        for entity_uuid, count in memory.remembered_search_failures.items()
        if count >= remembered_search_limit
    }


def policy_memory_trace(
    memory: ActorPolicyMemory,
    remembered_search_limit: int = 3,
) -> dict[str, object]:
    """Serialize actor policy memory without world or affordance copies."""
    return {
        "remembered_search_limit": remembered_search_limit,
        "remembered_search_failures": dict(memory.remembered_search_failures),
        "remembered_search_positions": dict(memory.remembered_search_positions),
        "remembered_search_visited_positions": {
            entity_uuid: sorted(positions)
            for entity_uuid, positions in memory.remembered_search_visited_positions.items()
        },
        "suppressed_remembered_enemy_uuids": sorted(
            suppressed_remembered_enemy_uuids(memory, remembered_search_limit)
        ),
        "active_routine": (
            memory.active_routine.model_dump(mode="json")
            if memory.active_routine is not None
            else None
        ),
        "last_routine_revalidation_status": memory.last_routine_revalidation_status,
        "last_routine_revalidation_reason": memory.last_routine_revalidation_reason,
        "turn_local_canceled_row_ids": sorted(memory.canceled_row_ids),
        "turn_local_canceled_semantic_counts": dict(memory.canceled_semantic_counts),
        "same_turn_spacing_intention": (
            memory.same_turn_spacing_intention.model_dump(mode="json")
            if memory.same_turn_spacing_intention is not None
            else None
        ),
    }
