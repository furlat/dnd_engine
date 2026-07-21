"""Forward composition of typed logical action and routine contracts."""

from __future__ import annotations

from collections import defaultdict
import json
from typing import Iterable, Mapping, Optional, Sequence

from ai.planning.contracts import (
    CompositionProof,
    ContingentBranch,
    EffectProvenance,
    LogicalConflict,
    LogicalStep,
    ObservationBarrier,
    OptionContract,
    PrerequisiteProof,
    RequirementKind,
    ResourceProjection,
)
from ai.protocol.semantics import (
    EffectOperation,
    FactExpression,
    FactOperator,
    FactPredicate,
    FactValue,
    LogicalEffect,
    ResourceOperation,
    TruthValue,
    evaluate_fact_expression,
)


def compose_option(
    option_id: str,
    steps: Sequence[LogicalStep],
    *,
    completion: Optional[FactExpression] = None,
    invalidation: Optional[FactExpression] = None,
    initial_facts: Optional[Mapping[str, FactValue]] = None,
) -> OptionContract:
    """Derive an option contract from an ordered logical chain.

    Guaranteed effects propagate only until the first observation barrier.
    Later declared steps remain inspectable but require fresh subjective
    observations before they can be composed soundly.
    """
    ordered_steps = tuple(steps)
    facts: dict[str, FactValue] = dict(initial_facts or {})
    initial_fact_ids = frozenset(facts)
    provenance: dict[str, EffectProvenance] = {}
    prerequisite_proofs: list[PrerequisiteProof] = []
    external_requirements: list[FactExpression] = []
    conflicts: list[LogicalConflict] = []
    branches: list[ContingentBranch] = []
    barriers: list[ObservationBarrier] = []
    possible_fact_providers: dict[str, set[str]] = defaultdict(set)
    resource_operations: dict[str, list[tuple[ResourceOperation, int]]] = defaultdict(list)
    barrier_active = False

    for step in ordered_steps:
        referenced = referenced_fact_ids(step.preconditions)
        established_by = tuple(sorted({
            provenance[fact_id].step_id
            for fact_id in referenced
            if fact_id in provenance
        }))
        if barrier_active:
            truth = TruthValue.UNKNOWN
            kind = RequirementKind.OBSERVATION_DEFERRED
            detail = "fresh_subjective_observation_required"
        else:
            truth = evaluate_fact_expression(step.preconditions, facts)
            if truth is TruthValue.TRUE:
                kind = RequirementKind.SATISFIED
                detail = (
                    "satisfied_by_initial_subjective_facts"
                    if referenced and referenced.issubset(initial_fact_ids)
                    else "satisfied_by_guaranteed_chain_prefix"
                )
            elif truth is TruthValue.FALSE:
                kind = RequirementKind.CONFLICT
                detail = "guaranteed_chain_prefix_contradicts_step_precondition"
                conflicts.append(LogicalConflict(
                    step_id=step.step_id,
                    expression=step.preconditions,
                    referenced_fact_ids=tuple(sorted(referenced)),
                    detail=detail,
                ))
            elif any(fact_id in possible_fact_providers for fact_id in referenced):
                kind = RequirementKind.CONTINGENT
                detail = "precondition_depends_on_conditional_or_stochastic_effect"
            else:
                kind = RequirementKind.EXTERNAL
                detail = "precondition_must_hold_before_option_execution"
                _append_unique_expression(external_requirements, step.preconditions)
        prerequisite_proofs.append(PrerequisiteProof(
            step_id=step.step_id,
            expression=step.preconditions,
            truth=truth,
            kind=kind,
            referenced_fact_ids=tuple(sorted(referenced)),
            established_by_step_ids=established_by,
            detail=detail,
        ))

        for conditional in step.conditional_effects:
            branches.append(ContingentBranch(
                source_step_id=step.step_id,
                branch_kind="conditional",
                condition=conditional.condition,
                effects=conditional.effects,
            ))
            for effect in conditional.effects:
                possible_fact_providers[effect.fact_id].add(step.step_id)
        for stochastic in step.stochastic_effects:
            branches.append(ContingentBranch(
                source_step_id=step.step_id,
                branch_kind="stochastic",
                outcome_kind=stochastic.outcome_kind.value,
                probability=stochastic.probability,
                effects=stochastic.effects,
            ))
            for effect in stochastic.effects:
                possible_fact_providers[effect.fact_id].add(step.step_id)

        if barrier_active or kind is RequirementKind.CONFLICT:
            continue

        for effect in step.guaranteed_effects:
            resulting_value = apply_logical_effect(facts, effect)
            provenance[effect.fact_id] = EffectProvenance(
                fact_id=effect.fact_id,
                step_id=step.step_id,
                effect=effect,
                resulting_value=resulting_value,
            )
        for resource in step.resource_effects:
            resource_operations[resource.resource_id].append(
                (resource.operation, resource.amount)
            )

        barrier = _observation_barrier_for(step)
        if barrier is not None:
            barriers.append(barrier)
            barrier_active = True

    proof = CompositionProof(
        prerequisites=tuple(prerequisite_proofs),
        effect_provenance=tuple(provenance[key] for key in sorted(provenance)),
        conflicts=tuple(conflicts),
        contingent_branches=tuple(branches),
        observation_barriers=tuple(barriers),
        resources=_project_resources(resource_operations),
    )
    return OptionContract(
        option_id=option_id,
        steps=ordered_steps,
        initial_preconditions=tuple(external_requirements),
        guaranteed_effects=tuple(
            provenance[key].effect
            for key in sorted(provenance)
        ),
        final_known_facts=facts,
        completion=completion or FactExpression.true(),
        invalidation=invalidation or _false_expression(),
        proof=proof,
        consistent=not conflicts,
        requires_observation=bool(barriers),
    )


def apply_logical_effect(
    facts: dict[str, FactValue],
    effect: LogicalEffect,
) -> FactValue:
    """Apply one guaranteed effect without inventing an unknown value."""
    fact_id = effect.fact_id
    value: FactValue = None
    if effect.operation is EffectOperation.SET:
        if effect.value_ref is not None:
            if effect.value_ref not in facts:
                facts.pop(fact_id, None)
                return None
            value = facts[effect.value_ref]
        else:
            value = effect.value
        facts[fact_id] = value
        return value
    if effect.operation is EffectOperation.SET_FROM_TARGET:
        if effect.value_ref is not None and effect.value_ref in facts:
            value = facts[effect.value_ref]
            facts[fact_id] = value
            return value
        facts.pop(fact_id, None)
        return None
    if effect.operation in {EffectOperation.INCREASE, EffectOperation.DECREASE}:
        current = facts.get(fact_id)
        delta = effect.value
        if (
            isinstance(current, (int, float))
            and not isinstance(current, bool)
            and isinstance(delta, (int, float))
            and not isinstance(delta, bool)
        ):
            value = (
                current + delta
                if effect.operation is EffectOperation.INCREASE
                else current - delta
            )
            facts[fact_id] = value
            return value
        facts.pop(fact_id, None)
        return None
    if effect.operation in {
        EffectOperation.ADD,
        EffectOperation.REMOVE,
        EffectOperation.INVALIDATE,
    }:
        facts.pop(fact_id, None)
        return None
    raise ValueError(f"Unsupported logical effect operation: {effect.operation}")


def referenced_fact_ids(expression: FactExpression) -> frozenset[str]:
    """Return every subjective fact read by an expression."""
    if expression.operator is FactOperator.PREDICATE:
        predicate = expression.predicate
        if predicate is None:
            return frozenset()
        references = {predicate.fact_id}
        if predicate.expected_fact_id is not None:
            references.add(predicate.expected_fact_id)
        return frozenset(references)
    references: set[str] = set()
    for operand in expression.operands:
        references.update(referenced_fact_ids(operand))
    return frozenset(references)


def expression_predicates(expression: FactExpression) -> tuple[FactPredicate, ...]:
    """Return leaf predicates in stable traversal order."""
    if expression.operator is FactOperator.PREDICATE:
        return (expression.predicate,) if expression.predicate is not None else ()
    return tuple(
        predicate
        for operand in expression.operands
        for predicate in expression_predicates(operand)
    )


def _append_unique_expression(
    expressions: list[FactExpression],
    expression: FactExpression,
) -> None:
    """Append a structurally unique requirement while preserving order."""
    identity = json.dumps(expression.model_dump(mode="json"), sort_keys=True)
    if any(
        json.dumps(existing.model_dump(mode="json"), sort_keys=True) == identity
        for existing in expressions
    ):
        return
    expressions.append(expression)


def _observation_barrier_for(step: LogicalStep) -> Optional[ObservationBarrier]:
    """Return a barrier when fresh perception can change downstream facts."""
    vision_topology = tuple(
        effect
        for effect in step.topology_effects
        if effect.affects_vision
    )
    reasons: list[str] = []
    if step.explicit_observation_barrier:
        reasons.append("explicit_reassessment")
    reasons.extend(
        f"information:{effect.operation.value}"
        for effect in step.information_effects
    )
    reasons.extend(
        f"vision_topology:{effect.operation.value}"
        for effect in vision_topology
    )
    if not reasons:
        return None
    return ObservationBarrier(
        after_step_id=step.step_id,
        reasons=tuple(reasons),
        information_effects=step.information_effects,
        topology_effects=vision_topology,
    )


def _project_resources(
    operations_by_resource: Mapping[
        str,
        Iterable[tuple[ResourceOperation, int]],
    ],
) -> tuple[ResourceProjection, ...]:
    """Compute minimum initial resources from deterministic prefix deficits."""
    projections: list[ResourceProjection] = []
    for resource_id in sorted(operations_by_resource):
        balance = 0
        minimum_balance = 0
        consumed = 0
        restored = 0
        for operation, amount in operations_by_resource[resource_id]:
            if operation is ResourceOperation.CONSUME:
                balance -= amount
                consumed += amount
            else:
                balance += amount
                restored += amount
            minimum_balance = min(minimum_balance, balance)
        projections.append(ResourceProjection(
            resource_id=resource_id,
            minimum_initial_amount=-minimum_balance,
            final_delta=balance,
            total_consumed=consumed,
            total_restored_or_acquired=restored,
        ))
    return tuple(projections)


def _false_expression() -> FactExpression:
    """Return an expression that is always false."""
    return FactExpression(
        operator=FactOperator.CONSTANT,
        constant=TruthValue.FALSE,
    )
