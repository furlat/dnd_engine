"""Small deterministic bundled policy expressed entirely as typed data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Generic, Sequence, TypeVar

from dnd.ai.contracts.control import ActionAffordance
from dnd.ai.contracts.decision import EndTurnIntent, ExecuteIntent, PolicyIntent
from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationEntityFact,
    SubjectiveWorldState,
)
from dnd.ai.contracts.semantics import (
    ActionSemantics,
    ActionTag,
    EffectOperation,
)
from dnd.ai.feedback import NativeAIDecisionFeedback, NativeAIDecisionOutcome
from dnd.ai.policy import PolicyDescriptor, StatelessPolicyMemory
from dnd.ai.registry import PolicyRegistry
from dnd.ai.specification import (
    DataDrivenPolicy,
    PolicyCandidate,
    PolicyMetric,
    PolicyMetricThreshold,
    PolicyMetricValue,
    PolicyRuleSpec,
    PolicyScoreTerm,
    PolicySpec,
)


StateT = TypeVar("StateT")
MemoryT = TypeVar("MemoryT")
DecisionT = TypeVar("DecisionT")

BASIC_POLICY_ID = "builtin.basic"
BASIC_POLICY_DESCRIPTOR = PolicyDescriptor(
    policy_id=BASIC_POLICY_ID,
    version="2",
    display_name="Basic",
    description=(
        "Deterministic bounded policy for recovery, immediate pressure, "
        "defense, interaction, movement, and exploration."
    ),
)


BASIC_POLICY_SPEC = PolicySpec(
    descriptor=BASIC_POLICY_DESCRIPTOR,
    maximum_decisions_per_turn=32,
    rules=(
        PolicyRuleSpec(
            rule_id="urgent_recovery",
            required_tags=(ActionTag.SUPPORT_HEAL,),
            forbidden_tags=(ActionTag.TURN_END,),
            thresholds=(
                PolicyMetricThreshold(
                    metric=PolicyMetric.URGENCY,
                    minimum=0.000_001,
                ),
            ),
            score_terms=(
                PolicyScoreTerm(metric=PolicyMetric.URGENCY, weight=100.0),
                PolicyScoreTerm(
                    metric=PolicyMetric.EXPECTED_HEALING,
                    weight=1.0,
                ),
                PolicyScoreTerm(metric=PolicyMetric.RESOURCE_COST, weight=-1.0),
            ),
        ),
        PolicyRuleSpec(
            rule_id="urgent_support",
            any_tags=(ActionTag.SUPPORT_BUFF, ActionTag.DEFENSE_SELF),
            forbidden_tags=(ActionTag.TURN_END,),
            thresholds=(
                PolicyMetricThreshold(
                    metric=PolicyMetric.URGENCY,
                    minimum=0.000_001,
                ),
                PolicyMetricThreshold(
                    metric=PolicyMetric.DEFENSE_VALUE,
                    minimum=0.000_001,
                ),
            ),
            score_terms=(
                PolicyScoreTerm(metric=PolicyMetric.URGENCY, weight=50.0),
                PolicyScoreTerm(metric=PolicyMetric.DEFENSE_VALUE, weight=1.0),
                PolicyScoreTerm(metric=PolicyMetric.RESOURCE_COST, weight=-1.0),
            ),
        ),
        PolicyRuleSpec(
            rule_id="hostile_control",
            any_tags=(
                ActionTag.CONTROL_HARD,
                ActionTag.CONTROL_SOFT,
            ),
            forbidden_tags=(ActionTag.TURN_END,),
            thresholds=(
                PolicyMetricThreshold(
                    metric=PolicyMetric.CONTROL_VALUE,
                    minimum=0.000_001,
                ),
            ),
            score_terms=(
                PolicyScoreTerm(metric=PolicyMetric.CONTROL_VALUE, weight=1.0),
                PolicyScoreTerm(metric=PolicyMetric.RESOURCE_COST, weight=-0.25),
                PolicyScoreTerm(metric=PolicyMetric.RISK, weight=-1.0),
            ),
        ),
        PolicyRuleSpec(
            rule_id="direct_damage",
            any_tags=(
                ActionTag.DAMAGE_SINGLE_TARGET,
                ActionTag.DAMAGE_MULTI_TARGET,
                ActionTag.DAMAGE_AREA,
            ),
            forbidden_tags=(ActionTag.TURN_END,),
            thresholds=(
                PolicyMetricThreshold(
                    metric=PolicyMetric.EXPECTED_DAMAGE,
                    minimum=0.000_001,
                ),
            ),
            score_terms=(
                PolicyScoreTerm(
                    metric=PolicyMetric.EXPECTED_DAMAGE,
                    weight=1.0,
                ),
                PolicyScoreTerm(metric=PolicyMetric.RESOURCE_COST, weight=-0.25),
                PolicyScoreTerm(metric=PolicyMetric.RISK, weight=-1.0),
            ),
        ),
        PolicyRuleSpec(
            rule_id="self_setup",
            any_tags=(
                ActionTag.SETUP_SELF,
                ActionTag.DEFENSE_SELF,
                ActionTag.SUPPORT_BUFF,
            ),
            forbidden_tags=(ActionTag.TURN_END,),
            thresholds=(
                PolicyMetricThreshold(
                    metric=PolicyMetric.DEFENSE_VALUE,
                    minimum=0.000_001,
                ),
            ),
            score_terms=(
                PolicyScoreTerm(metric=PolicyMetric.DEFENSE_VALUE, weight=1.0),
                PolicyScoreTerm(metric=PolicyMetric.RESOURCE_COST, weight=-0.5),
            ),
        ),
        PolicyRuleSpec(
            rule_id="open_blocking_door",
            required_tags=(ActionTag.INTERACTION_DOOR_OPEN,),
            forbidden_tags=(ActionTag.TURN_END,),
            score_terms=(
                PolicyScoreTerm(metric=PolicyMetric.PROGRESS, weight=1.0),
                PolicyScoreTerm(metric=PolicyMetric.RISK, weight=-1.0),
            ),
        ),
        PolicyRuleSpec(
            rule_id="advance",
            required_tags=(ActionTag.MOVEMENT_VOLUNTARY,),
            forbidden_tags=(ActionTag.TURN_END,),
            thresholds=(
                PolicyMetricThreshold(
                    metric=PolicyMetric.PROGRESS,
                    minimum=0.000_001,
                ),
            ),
            score_terms=(
                PolicyScoreTerm(metric=PolicyMetric.PROGRESS, weight=1.0),
                PolicyScoreTerm(metric=PolicyMetric.RISK, weight=-1.0),
            ),
        ),
        PolicyRuleSpec(
            rule_id="gather_information",
            any_tags=(
                ActionTag.INFORMATION_REVEAL,
                ActionTag.INFORMATION_EXPLORE,
            ),
            forbidden_tags=(ActionTag.TURN_END,),
            score_terms=(
                PolicyScoreTerm(
                    metric=PolicyMetric.INFORMATION_VALUE,
                    weight=1.0,
                ),
                PolicyScoreTerm(metric=PolicyMetric.RISK, weight=-1.0),
            ),
        ),
        PolicyRuleSpec(
            rule_id="affordable_fallback",
            forbidden_tags=(
                ActionTag.TURN_END,
                ActionTag.SUPPORT_HEAL,
                ActionTag.DAMAGE_SINGLE_TARGET,
                ActionTag.DAMAGE_MULTI_TARGET,
                ActionTag.DAMAGE_AREA,
                ActionTag.ATTACK_WEAPON,
                ActionTag.ATTACK_SPELL,
                ActionTag.CONTROL_HARD,
                ActionTag.CONTROL_SOFT,
            ),
            score_terms=(
                PolicyScoreTerm(metric=PolicyMetric.PROGRESS, weight=1.0),
                PolicyScoreTerm(metric=PolicyMetric.RESOURCE_COST, weight=-1.0),
                PolicyScoreTerm(metric=PolicyMetric.RISK, weight=-1.0),
            ),
        ),
    ),
)


_MAXIMUM_RETAINED_TURN_FACTS = 64
_NONREPEATABLE_TAGS = frozenset(
    {
        ActionTag.CAPABILITY_TRANSFORM,
        ActionTag.DEFENSE_SELF,
        ActionTag.MOBILITY_EXTEND,
        ActionTag.SETUP_SELF,
    }
)
_MOVEMENT_TAGS = frozenset(
    {
        ActionTag.MOVEMENT_TELEPORT,
        ActionTag.MOVEMENT_VOLUNTARY,
    }
)


@dataclass(frozen=True, slots=True)
class _BasicRowFact:
    """Decision metadata retained only until authoritative feedback arrives."""

    semantic_id: str
    tags: frozenset[ActionTag]
    destination_positions: tuple[tuple[int, int], ...]


@dataclass(slots=True)
class BasicActorMemory:
    """Bounded per-turn policy facts for one controlled actor."""

    turn_key: tuple[int, int] | None = None
    visited_positions: tuple[tuple[int, int], ...] = ()
    completed_nonrepeatable_semantic_ids: tuple[str, ...] = ()
    completed_movement_semantic_ids: tuple[str, ...] = ()
    blocked_row_ids: tuple[str, ...] = ()
    current_rows: dict[str, _BasicRowFact] = field(default_factory=dict)

    def reset_for_turn(self, turn_key: tuple[int, int]) -> None:
        """Drop prior-turn suppression while preserving actor isolation."""
        self.turn_key = turn_key
        self.visited_positions = ()
        self.completed_nonrepeatable_semantic_ids = ()
        self.completed_movement_semantic_ids = ()
        self.blocked_row_ids = ()
        self.current_rows.clear()


@dataclass(slots=True)
class BasicPolicyMemory:
    """Assignment-owned state used to prevent repeated no-progress choices."""

    actors: dict[str, BasicActorMemory] = field(default_factory=dict)

    def actor(self, actor_uuid: str) -> BasicActorMemory:
        """Return the reducer-owned memory for one controlled actor."""
        memory = self.actors.get(actor_uuid)
        if memory is None:
            memory = BasicActorMemory()
            self.actors[actor_uuid] = memory
        return memory

    def known_actor(self, actor_uuid: str) -> BasicActorMemory | None:
        """Read actor memory without mutating policy state."""
        return self.actors.get(actor_uuid)


class BasicPolicy(
    DataDrivenPolicy[StateT, MemoryT, DecisionT],
    Generic[StateT, MemoryT, DecisionT],
):
    """Bundled policy whose runtime adapter supplies canonical candidates."""

    def __init__(
        self,
        *,
        candidate_provider: Callable[
            [StateT, MemoryT],
            Sequence[PolicyCandidate[DecisionT]],
        ],
        end_turn_factory: Callable[[StateT], DecisionT],
    ) -> None:
        super().__init__(
            specification=BASIC_POLICY_SPEC,
            candidate_provider=candidate_provider,
            end_turn_factory=end_turn_factory,
        )


CanonicalBasicPolicy = BasicPolicy[
    SubjectiveWorldState,
    BasicPolicyMemory,
    PolicyIntent,
]
CanonicalPolicyRegistry = PolicyRegistry[
    SubjectiveWorldState,
    PolicyIntent,
]


def create_basic_policy() -> CanonicalBasicPolicy:
    """Create the bundled policy over canonical subjective contracts."""
    return BasicPolicy(
        candidate_provider=build_basic_candidates,
        end_turn_factory=lambda _state: EndTurnIntent(),
    )


def register_basic_policy(registry: CanonicalPolicyRegistry) -> None:
    """Register the bundled policy in the canonical policy registry."""
    registry.register(
        descriptor=BASIC_POLICY_DESCRIPTOR,
        policy_factory=create_basic_policy,
        memory_factory=BasicPolicyMemory,
        reduce_state=reduce_basic_state,
        reduce_feedback=reduce_basic_feedback,
    )


def reduce_basic_state(
    memory: BasicPolicyMemory,
    state: SubjectiveWorldState,
) -> None:
    """Refresh current row facts and bounded turn-local progress memory."""
    epoch = state.current_epoch
    if epoch is None:
        return
    actor_memory = memory.actor(epoch.actor_uuid)
    turn_key = (epoch.round_number, epoch.turn_index)
    if actor_memory.turn_key != turn_key:
        actor_memory.reset_for_turn(turn_key)
    actor = state.known_entities.get(epoch.actor_uuid)
    if actor is not None and actor.position is not None:
        actor_memory.visited_positions = _remember_bounded(
            actor_memory.visited_positions,
            actor.position,
        )
    actor_memory.current_rows = {
        row.row_id: _row_memory_fact(
            row,
            epoch.affordances.semantics_for(row),
        )
        for row in epoch.affordances.all_rows
    }


def reduce_basic_feedback(
    memory: BasicPolicyMemory,
    feedback: NativeAIDecisionFeedback,
) -> None:
    """Commit only authoritative outcomes into bounded suppression memory."""
    if feedback.row_id is None:
        return
    actor_memory = memory.known_actor(feedback.actor_uuid)
    if actor_memory is None:
        return
    fact = actor_memory.current_rows.get(feedback.row_id)
    if feedback.outcome in {
        NativeAIDecisionOutcome.CANCELED,
        NativeAIDecisionOutcome.FAILED,
        NativeAIDecisionOutcome.REJECTED,
    }:
        actor_memory.blocked_row_ids = _remember_bounded(
            actor_memory.blocked_row_ids,
            feedback.row_id,
        )
        return
    if feedback.outcome is not NativeAIDecisionOutcome.EXECUTED or fact is None:
        return
    if fact.tags.intersection(_NONREPEATABLE_TAGS):
        actor_memory.completed_nonrepeatable_semantic_ids = (
            _remember_bounded(
                actor_memory.completed_nonrepeatable_semantic_ids,
                fact.semantic_id,
            )
        )
    if fact.tags.intersection(_MOVEMENT_TAGS):
        actor_memory.completed_movement_semantic_ids = _remember_bounded(
            actor_memory.completed_movement_semantic_ids,
            fact.semantic_id,
        )
        for position in fact.destination_positions:
            actor_memory.visited_positions = _remember_bounded(
                actor_memory.visited_positions,
                position,
            )


def build_basic_candidates(
    state: SubjectiveWorldState,
    memory: BasicPolicyMemory | StatelessPolicyMemory,
) -> tuple[PolicyCandidate[PolicyIntent], ...]:
    """Derive bounded policy candidates from one canonical subjective epoch."""
    epoch = state.current_epoch
    if epoch is None or epoch.actor_uuid != state.session.active_entity_uuid:
        return ()
    actor = state.known_entities.get(epoch.actor_uuid)
    candidates: list[PolicyCandidate[PolicyIntent]] = []
    actor_memory = (
        memory.known_actor(epoch.actor_uuid)
        if isinstance(memory, BasicPolicyMemory)
        else None
    )
    for row in epoch.affordances.all_rows:
        semantics = epoch.affordances.semantics_for(row)
        tags = _canonical_tags(row, semantics)
        metrics = _candidate_metrics(
            state=state,
            actor=actor,
            row=row,
            semantics=semantics,
            tags=tags,
        )
        if _candidate_suppressed(
            actor_memory=actor_memory,
            actor=actor,
            row=row,
            semantics=semantics,
            tags=tags,
        ):
            continue
        if not _has_positive_policy_utility(tags, metrics):
            continue
        candidates.append(
            PolicyCandidate(
                candidate_id=row.row_id,
                decision=ExecuteIntent(row_id=row.row_id, prefer_safe=True),
                semantic_tags=tags,
                metrics=metrics,
                replay_key=(semantics.semantic_id, row.semantic_key, row.row_id),
                affordable=(
                    row.can_afford
                    and row.cost.affordability != "unaffordable"
                ),
            )
        )
    return tuple(candidates)


def _canonical_tags(
    row: ActionAffordance,
    semantics: ActionSemantics,
) -> frozenset[ActionTag]:
    """Merge canonical semantic tags with validated row-local tag values."""
    tags = set(semantics.tags)
    for raw_tag in row.tags:
        try:
            tags.add(ActionTag(raw_tag))
        except ValueError:
            continue
    return frozenset(tags)


def _candidate_metrics(
    *,
    state: SubjectiveWorldState,
    actor: ObservationEntityFact | None,
    row: ActionAffordance,
    semantics: ActionSemantics,
    tags: frozenset[ActionTag],
) -> tuple[PolicyMetricValue, ...]:
    """Compute conservative subjective values without inspecting engine state."""
    recipients = _row_entity_facts(state, row)
    hostile_recipients = tuple(
        fact
        for fact in recipients
        if _is_hostile(actor, fact)
    )
    allied_recipients = tuple(
        fact
        for fact in recipients
        if _is_ally(actor, fact)
    )
    urgency = _healing_urgency(actor, allied_recipients, semantics, tags)
    expected_healing = _literal_healing(semantics, allied_recipients, actor)
    expected_damage = _expected_damage(row, tags, hostile_recipients)
    control_value = (
        float(len(hostile_recipients))
        * (
            2.0
            if ActionTag.CONTROL_HARD in tags
            else 1.0
            if ActionTag.CONTROL_SOFT in tags
            else 0.0
        )
    )
    defense_value = _defense_value(semantics)
    progress = _progress_value(state, actor, row, tags)
    information_value = _information_value(row, tags)
    risk = _risk_value(row, allied_recipients, tags)
    resource_cost = float(
        (row.cost.spell_slot_cost or 0)
        + sum(row.cost.resource_costs.values())
        + sum(row.cost.item_charge_costs.values())
    )
    return (
        PolicyMetricValue(metric=PolicyMetric.URGENCY, value=urgency),
        PolicyMetricValue(
            metric=PolicyMetric.EXPECTED_DAMAGE,
            value=expected_damage,
        ),
        PolicyMetricValue(
            metric=PolicyMetric.EXPECTED_HEALING,
            value=expected_healing,
        ),
        PolicyMetricValue(
            metric=PolicyMetric.CONTROL_VALUE,
            value=control_value,
        ),
        PolicyMetricValue(
            metric=PolicyMetric.DEFENSE_VALUE,
            value=defense_value,
        ),
        PolicyMetricValue(metric=PolicyMetric.PROGRESS, value=progress),
        PolicyMetricValue(
            metric=PolicyMetric.INFORMATION_VALUE,
            value=information_value,
        ),
        PolicyMetricValue(
            metric=PolicyMetric.RESOURCE_COST,
            value=resource_cost,
        ),
        PolicyMetricValue(metric=PolicyMetric.RISK, value=risk),
    )


def _row_entity_facts(
    state: SubjectiveWorldState,
    row: ActionAffordance,
) -> tuple[ObservationEntityFact, ...]:
    """Resolve explicitly disclosed target and affected-entity facts."""
    uuids: list[str] = []
    for target in row.targets:
        if target.target_uuid is not None:
            uuids.append(target.target_uuid)
        uuids.extend(target.affected_entity_uuids)
    return tuple(
        state.known_entities[entity_uuid]
        for entity_uuid in dict.fromkeys(uuids)
        if entity_uuid in state.known_entities
    )


def _is_ally(
    actor: ObservationEntityFact | None,
    other: ObservationEntityFact,
) -> bool:
    if other.controlled:
        return True
    return (
        actor is not None
        and actor.faction is not None
        and other.faction == actor.faction
    )


def _is_hostile(
    actor: ObservationEntityFact | None,
    other: ObservationEntityFact,
) -> bool:
    if other.controlled or other.is_dead is True:
        return False
    if actor is None or actor.faction is None:
        return True
    return other.faction != actor.faction


def _missing_hp_fraction(entity: ObservationEntityFact | None) -> float:
    if (
        entity is None
        or entity.normal_hp is None
        or entity.max_hp is None
        or entity.max_hp <= 0
        or entity.healing_blocked is not False
        or entity.is_dead is True
    ):
        return 0.0
    return max(
        0.0,
        min(
            1.0,
            float(entity.max_hp - entity.normal_hp) / float(entity.max_hp),
        ),
    )


def _healing_urgency(
    actor: ObservationEntityFact | None,
    allied_recipients: tuple[ObservationEntityFact, ...],
    semantics: ActionSemantics,
    tags: frozenset[ActionTag],
) -> float:
    if ActionTag.SUPPORT_HEAL in tags:
        recipients = allied_recipients
        if any(effect.fact_id == "actor.hp" for effect in semantics.guaranteed_effects):
            recipients = (*recipients, actor) if actor is not None else recipients
        return max(
            (_missing_hp_fraction(entity) for entity in recipients),
            default=0.0,
        )
    if tags.intersection(
        {ActionTag.SUPPORT_BUFF, ActionTag.DEFENSE_SELF, ActionTag.SETUP_SELF}
    ):
        return _missing_hp_fraction(actor)
    return 0.0


def _literal_healing(
    semantics: ActionSemantics,
    allied_recipients: tuple[ObservationEntityFact, ...],
    actor: ObservationEntityFact | None,
) -> float:
    for effect in semantics.guaranteed_effects:
        if (
            effect.fact_id in {"actor.hp", "selected_target.hp"}
            and effect.operation is EffectOperation.INCREASE
            and isinstance(effect.value, (int, float))
            and not isinstance(effect.value, bool)
            and effect.value > 0
        ):
            recipient = (
                actor
                if effect.fact_id == "actor.hp"
                else allied_recipients[0]
                if allied_recipients
                else None
            )
            if (
                recipient is None
                or recipient.normal_hp is None
                or recipient.max_hp is None
            ):
                return 0.0
            return min(
                float(effect.value),
                float(max(0, recipient.max_hp - recipient.normal_hp)),
            )
    return 0.0


def _expected_damage(
    row: ActionAffordance,
    tags: frozenset[ActionTag],
    hostile_recipients: tuple[ObservationEntityFact, ...],
) -> float:
    if not tags.intersection(
        {
            ActionTag.DAMAGE_SINGLE_TARGET,
            ActionTag.DAMAGE_MULTI_TARGET,
            ActionTag.DAMAGE_AREA,
        }
    ):
        return 0.0
    if row.targets and not hostile_recipients:
        return 0.0
    profile = row.outcome_profile
    if profile is None:
        return float(len(hostile_recipients) or 1)
    per_application = sum(
        float(component.dice_count) * float(component.die_size + 1) / 2.0
        + float(component.flat_bonus)
        for component in profile.damage_rolls
    )
    recipient_count = (
        len(hostile_recipients)
        if ActionTag.DAMAGE_AREA in tags
        else 1
    )
    return max(
        0.0,
        per_application
        * float(profile.applications)
        * float(max(1, recipient_count)),
    )


def _defense_value(semantics: ActionSemantics) -> float:
    setup = semantics.self_setup
    if setup is None:
        return 0.0
    return float(
        setup.armor_class_bonus
        + setup.extra_actions_per_turn * 2
        + int(setup.increases_weapon_damage) * 2
        + len(setup.resistance_damage_types)
        + int(setup.grants_bonus_action_attack) * 2
        + int(setup.grants_incoming_attack_disadvantage) * 2
        + int(setup.grants_outgoing_attack_advantage)
        + int(setup.grants_invisibility) * 2
        + max(0.0, setup.movement_speed_multiplier - 1.0)
    )


def _information_value(
    row: ActionAffordance,
    tags: frozenset[ActionTag],
) -> float:
    """Prefer one useful complete route over repeated one-cell exploration."""
    if not tags.intersection(
        {ActionTag.INFORMATION_REVEAL, ActionTag.INFORMATION_EXPLORE}
    ):
        return 0.0
    route_values = tuple(
        float(
            max(
                len(target.safe_path or target.path),
                target.safe_path_cost or target.path_cost or 0,
            )
        )
        for target in row.targets
    )
    return max((1.0, *route_values))


def _row_memory_fact(
    row: ActionAffordance,
    semantics: ActionSemantics,
) -> _BasicRowFact:
    tags = _canonical_tags(row, semantics)
    return _BasicRowFact(
        semantic_id=semantics.semantic_id,
        tags=tags,
        destination_positions=tuple(
            target.position
            for target in row.targets
            if target.position is not None
        ),
    )


def _candidate_suppressed(
    *,
    actor_memory: BasicActorMemory | None,
    actor: ObservationEntityFact | None,
    row: ActionAffordance,
    semantics: ActionSemantics,
    tags: frozenset[ActionTag],
) -> bool:
    """Reject only proven no-progress repeats; attacks remain repeatable."""
    setup_or_defense_tags = tags.intersection(
        {
            ActionTag.CAPABILITY_TRANSFORM,
            ActionTag.DEFENSE_SELF,
            ActionTag.SETUP_SELF,
        }
    )
    if setup_or_defense_tags and _defense_value(semantics) <= 0.0:
        return True
    setup = semantics.self_setup
    active_condition_keys = (
        frozenset(actor.condition_semantic_keys or ())
        if actor is not None
        else frozenset()
    )
    if (
        setup is not None
        and setup.active_condition_semantic_keys.intersection(
            active_condition_keys
        )
    ):
        return True
    if actor_memory is None:
        return False
    if row.row_id in actor_memory.blocked_row_ids:
        return True
    if (
        tags.intersection(_NONREPEATABLE_TAGS)
        and semantics.semantic_id
        in actor_memory.completed_nonrepeatable_semantic_ids
    ):
        return True
    if tags.intersection(_MOVEMENT_TAGS):
        if (
            semantics.semantic_id
            in actor_memory.completed_movement_semantic_ids
        ):
            return True
        destinations = tuple(
            target.position
            for target in row.targets
            if target.position is not None
        )
        if destinations and any(
            position in actor_memory.visited_positions
            for position in destinations
        ):
            return True
    return False


def _has_positive_policy_utility(
    tags: frozenset[ActionTag],
    metrics: tuple[PolicyMetricValue, ...],
) -> bool:
    """Require typed positive utility before the permissive fallback rule."""
    values = {
        metric.metric: metric.value
        for metric in metrics
    }

    def positive(*metric_names: PolicyMetric) -> bool:
        return any(values.get(metric_name, 0.0) > 0.0 for metric_name in metric_names)

    if ActionTag.SUPPORT_HEAL in tags and positive(
        PolicyMetric.URGENCY,
        PolicyMetric.EXPECTED_HEALING,
    ):
        return True
    if tags.intersection(
        {
            ActionTag.DAMAGE_AREA,
            ActionTag.DAMAGE_MULTI_TARGET,
            ActionTag.DAMAGE_SINGLE_TARGET,
        }
    ) and positive(PolicyMetric.EXPECTED_DAMAGE):
        return True
    if tags.intersection(
        {ActionTag.CONTROL_HARD, ActionTag.CONTROL_SOFT}
    ) and positive(PolicyMetric.CONTROL_VALUE):
        return True
    if tags.intersection(
        {
            ActionTag.CAPABILITY_TRANSFORM,
            ActionTag.DEFENSE_SELF,
            ActionTag.SETUP_SELF,
            ActionTag.SUPPORT_BUFF,
        }
    ) and positive(PolicyMetric.DEFENSE_VALUE):
        return True
    if tags.intersection(
        {
            ActionTag.INFORMATION_EXPLORE,
            ActionTag.INFORMATION_REVEAL,
            ActionTag.INTERACTION_DOOR_OPEN,
            ActionTag.INTERACTION_HAZARD_DEACTIVATE,
            ActionTag.MOVEMENT_TELEPORT,
            ActionTag.MOVEMENT_VOLUNTARY,
        }
    ) and positive(
        PolicyMetric.INFORMATION_VALUE,
        PolicyMetric.PROGRESS,
    ):
        return True
    return False


def _remember_bounded(
    values: tuple[StateT, ...],
    value: StateT,
) -> tuple[StateT, ...]:
    """Append one unique value while retaining a deterministic fixed bound."""
    if value in values:
        return values
    return (*values, value)[-_MAXIMUM_RETAINED_TURN_FACTS:]


def _progress_value(
    state: SubjectiveWorldState,
    actor: ObservationEntityFact | None,
    row: ActionAffordance,
    tags: frozenset[ActionTag],
) -> float:
    if ActionTag.INTERACTION_DOOR_OPEN in tags:
        return 1.0
    if (
        ActionTag.MOVEMENT_VOLUNTARY not in tags
        or actor is None
        or actor.position is None
    ):
        return 0.0
    destinations = tuple(
        target.position
        for target in row.targets
        if target.position is not None
    )
    contacts = tuple(
        entity
        for entity in state.known_entities.values()
        if entity.position is not None
        and entity.knowledge_state
        in {KnowledgeState.VISIBLE, KnowledgeState.REMEMBERED}
        and _is_hostile(actor, entity)
    )
    if not destinations or not contacts:
        return 0.0
    before = min(
        _grid_distance(actor.position, contact.position)
        for contact in contacts
        if contact.position is not None
    )
    after = min(
        _grid_distance(destination, contact.position)
        for destination in destinations
        for contact in contacts
        if contact.position is not None
    )
    return float(max(0, before - after))


def _grid_distance(
    left: tuple[int, int],
    right: tuple[int, int],
) -> int:
    return max(abs(left[0] - right[0]), abs(left[1] - right[1]))


def _risk_value(
    row: ActionAffordance,
    allied_recipients: tuple[ObservationEntityFact, ...],
    tags: frozenset[ActionTag],
) -> float:
    risk = 0.0
    if tags.intersection(
        {
            ActionTag.DAMAGE_SINGLE_TARGET,
            ActionTag.DAMAGE_MULTI_TARGET,
            ActionTag.DAMAGE_AREA,
            ActionTag.CONTROL_HARD,
            ActionTag.CONTROL_SOFT,
        }
    ):
        risk += float(len(allied_recipients)) * 100.0
    for target in row.targets:
        if target.safe_path:
            risk += float(len(target.safe_path_opportunity_attack_exposures)) * 5.0
        else:
            risk += float(len(target.opportunity_attack_exposures)) * 5.0
            risk += 5.0 if target.is_path_hazardous else 0.0
    return risk
