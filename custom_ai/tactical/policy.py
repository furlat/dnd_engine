"""Stateful tactical policy using only canonical subjective AI contracts."""

from __future__ import annotations

from dnd.ai.contracts.control import ActionAffordance
from dnd.ai.contracts.decision import EndTurnIntent, PolicyIntent
from dnd.ai.contracts.observation import SubjectiveWorldState
from dnd.ai.contracts.semantics import ActionTag
from dnd.ai.policies.basic import (
    build_policy_candidates,
)
from dnd.ai.policy import PolicyDescriptor, StatelessPolicyMemory
from dnd.ai.registry import PolicyRegistry
from dnd.ai.specification import (
    PolicyCandidate,
    PolicyMetric,
    policy_candidate_rank_key,
)

from custom_ai.tactical.memory import (
    TacticalPolicyMemory,
    reduce_tactical_feedback,
    reduce_tactical_state,
)


TACTICAL_POLICY_ID = "custom.tactical"
TACTICAL_POLICY_DESCRIPTOR = PolicyDescriptor(
    policy_id=TACTICAL_POLICY_ID,
    version="1",
    display_name="Tactical",
    description=(
        "Stateful focus-fire policy with bounded failure memory and "
        "deterministic subjective target selection."
    ),
)

_OFFENSIVE_TAGS = frozenset(
    {
        ActionTag.DAMAGE_SINGLE_TARGET,
        ActionTag.DAMAGE_MULTI_TARGET,
        ActionTag.DAMAGE_AREA,
        ActionTag.CONTROL_HARD,
        ActionTag.CONTROL_SOFT,
    }
)


class TacticalPolicy:
    """Focus-fire example whose state mutations live only in reducers."""

    descriptor = TACTICAL_POLICY_DESCRIPTOR

    def decide(
        self,
        state: SubjectiveWorldState,
        memory: TacticalPolicyMemory,
    ) -> PolicyIntent:
        epoch = state.current_epoch
        if (
            epoch is None
            or epoch.actor_uuid != state.session.active_entity_uuid
        ):
            return EndTurnIntent()
        actor_memory = memory.known_actor(epoch.actor_uuid)
        blocked = (
            actor_memory.blocked_row_ids
            if actor_memory is not None
            else set()
        )
        candidates = tuple(
            candidate
            for candidate in build_policy_candidates(
                state,
                StatelessPolicyMemory(),
            )
            if candidate.candidate_id not in blocked
            and candidate.affordable
            and ActionTag.TURN_END not in candidate.semantic_tags
        )
        urgent_recovery = tuple(
            candidate
            for candidate in candidates
            if ActionTag.SUPPORT_HEAL in candidate.semantic_tags
            and candidate.metric_value(PolicyMetric.URGENCY) >= 0.5
        )
        if urgent_recovery:
            return _select(urgent_recovery).decision

        focused_target_uuid = (
            actor_memory.focused_target_uuid
            if actor_memory is not None
            else None
        )
        focused_pressure = tuple(
            candidate
            for candidate in candidates
            if candidate.semantic_tags.intersection(_OFFENSIVE_TAGS)
            and _candidate_has_positive_pressure(candidate)
            and focused_target_uuid is not None
            and _row_affects_target(
                epoch.affordances.row_by_id(candidate.candidate_id),
                focused_target_uuid,
            )
        )
        if focused_pressure:
            return _select(focused_pressure).decision

        general_pressure = tuple(
            candidate
            for candidate in candidates
            if candidate.semantic_tags.intersection(_OFFENSIVE_TAGS)
            and _candidate_has_positive_pressure(candidate)
        )
        if general_pressure:
            return _select(general_pressure).decision

        advancing = tuple(
            candidate
            for candidate in candidates
            if ActionTag.MOVEMENT_VOLUNTARY in candidate.semantic_tags
            and candidate.metric_value(PolicyMetric.PROGRESS) > 0.0
        )
        if advancing:
            return _select(advancing).decision

        useful = tuple(
            candidate
            for candidate in candidates
            if not candidate.semantic_tags.intersection(_OFFENSIVE_TAGS)
            and ActionTag.SUPPORT_HEAL not in candidate.semantic_tags
        )
        return _select(useful).decision if useful else EndTurnIntent()


def register_tactical_policy(
    registry: PolicyRegistry[SubjectiveWorldState, PolicyIntent],
) -> None:
    """Register the example with fresh typed memory and core-owned reducers."""
    registry.register(
        descriptor=TACTICAL_POLICY_DESCRIPTOR,
        policy_factory=TacticalPolicy,
        memory_factory=TacticalPolicyMemory,
        reduce_state=reduce_tactical_state,
        reduce_feedback=reduce_tactical_feedback,
    )


def _candidate_has_positive_pressure(
    candidate: PolicyCandidate[PolicyIntent],
) -> bool:
    return (
        candidate.metric_value(PolicyMetric.EXPECTED_DAMAGE) > 0.0
        or candidate.metric_value(PolicyMetric.CONTROL_VALUE) > 0.0
    )


def _row_affects_target(
    row: ActionAffordance | None,
    target_uuid: str,
) -> bool:
    if row is None:
        return False
    return any(
        target.target_uuid == target_uuid
        or target_uuid in target.affected_entity_uuids
        for target in row.targets
    )


def _select(
    candidates: tuple[PolicyCandidate[PolicyIntent], ...],
) -> PolicyCandidate[PolicyIntent]:
    return min(
        candidates,
        key=lambda candidate: policy_candidate_rank_key(
            candidate,
            _candidate_score(candidate),
        ),
    )


def _candidate_score(candidate: PolicyCandidate[PolicyIntent]) -> float:
    return (
        candidate.metric_value(PolicyMetric.URGENCY) * 100.0
        + candidate.metric_value(PolicyMetric.EXPECTED_HEALING) * 2.0
        + candidate.metric_value(PolicyMetric.EXPECTED_DAMAGE) * 2.0
        + candidate.metric_value(PolicyMetric.CONTROL_VALUE) * 4.0
        + candidate.metric_value(PolicyMetric.DEFENSE_VALUE) * 2.0
        + candidate.metric_value(PolicyMetric.PROGRESS)
        + candidate.metric_value(PolicyMetric.INFORMATION_VALUE)
        - candidate.metric_value(PolicyMetric.RESOURCE_COST)
        - candidate.metric_value(PolicyMetric.RISK) * 2.0
    )
