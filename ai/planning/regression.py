"""Bounded backward regression over typed logical steps."""

from __future__ import annotations

import json
from typing import Mapping, Sequence

from ai.planning.composition import compose_option
from ai.planning.contracts import LogicalStep, RegressionCandidate
from server.agent_protocol.semantics import (
    ComparisonOperator,
    EffectOperation,
    FactExpression,
    FactOperator,
    FactPredicate,
    FactValue,
    LogicalEffect,
    TruthValue,
    evaluate_fact_expression,
)


def regress_options(
    goal: FactExpression,
    available_steps: Sequence[LogicalStep],
    *,
    initial_facts: Mapping[str, FactValue] | None = None,
    max_depth: int = 4,
    max_candidates: int = 32,
) -> tuple[RegressionCandidate, ...]:
    """Find short chains whose guaranteed effects can establish a goal.

    Regression is intentionally bounded. Authored routines remain the primary
    method library; this function verifies or fills short missing chains.
    """
    if max_depth < 1:
        raise ValueError("max_depth must be at least one")
    facts = dict(initial_facts or {})
    steps = tuple(available_steps)
    results: list[RegressionCandidate] = []
    visited: set[tuple[tuple[str, ...], str]] = set()

    def search(
        unresolved: tuple[FactExpression, ...],
        reverse_chain: tuple[LogicalStep, ...],
    ) -> None:
        if len(results) >= max_candidates:
            return
        normalized = _remove_satisfied(unresolved, facts)
        producible_index = next(
            (
                index
                for index, expression in enumerate(normalized)
                if any(_step_establishes(step, expression) for step in steps)
            ),
            None,
        )
        if producible_index is None:
            if not reverse_chain:
                return
            ordered = tuple(reversed(reverse_chain))
            option = compose_option(
                "regressed:" + "->".join(step.step_id for step in ordered),
                ordered,
                completion=goal,
                initial_facts=facts,
            )
            if option.consistent:
                results.append(RegressionCandidate(
                    step_ids=tuple(step.step_id for step in ordered),
                    remaining_preconditions=normalized,
                    option=option,
                ))
            return
        if len(reverse_chain) >= max_depth:
            return

        target = normalized[producible_index]
        residual = (
            *normalized[:producible_index],
            *normalized[producible_index + 1 :],
        )
        for step in steps:
            if step in reverse_chain or not _step_establishes(step, target):
                continue
            next_unresolved = (
                *_flatten_conjunction(step.preconditions),
                *residual,
            )
            next_chain = (*reverse_chain, step)
            key = (
                tuple(candidate.step_id for candidate in next_chain),
                _expressions_identity(next_unresolved),
            )
            if key in visited:
                continue
            visited.add(key)
            search(next_unresolved, next_chain)

    search(_flatten_conjunction(goal), ())
    return tuple(sorted(
        results,
        key=lambda candidate: (len(candidate.step_ids), candidate.step_ids),
    ))


def _step_establishes(step: LogicalStep, expression: FactExpression) -> bool:
    """Return whether a guaranteed step effect proves one simple predicate."""
    if expression.operator is FactOperator.CONSTANT:
        return expression.constant is TruthValue.TRUE
    if expression.operator is not FactOperator.PREDICATE or expression.predicate is None:
        return False
    predicate = expression.predicate
    return any(
        _effect_establishes_predicate(effect, predicate)
        for effect in step.guaranteed_effects
    )


def _effect_establishes_predicate(effect: object, predicate: FactPredicate) -> bool:
    """Match one literal guaranteed effect to one requested predicate."""
    if not isinstance(effect, LogicalEffect) or effect.fact_id != predicate.fact_id:
        return False
    if effect.operation is not EffectOperation.SET or effect.value_ref is not None:
        return False
    actual = effect.value
    expected = predicate.expected_value
    if predicate.expected_fact_id is not None:
        return False
    if predicate.comparison is ComparisonOperator.EQUALS:
        return actual == expected
    if predicate.comparison is ComparisonOperator.NOT_EQUALS:
        return actual != expected
    if (
        actual is None
        or expected is None
        or not isinstance(actual, (int, float))
        or isinstance(actual, bool)
        or not isinstance(expected, (int, float))
        or isinstance(expected, bool)
    ):
        return False
    if predicate.comparison is ComparisonOperator.GREATER_THAN:
        return actual > expected
    if predicate.comparison is ComparisonOperator.GREATER_OR_EQUAL:
        return actual >= expected
    if predicate.comparison is ComparisonOperator.LESS_THAN:
        return actual < expected
    if predicate.comparison is ComparisonOperator.LESS_OR_EQUAL:
        return actual <= expected
    return predicate.comparison is ComparisonOperator.EXISTS


def _remove_satisfied(
    expressions: tuple[FactExpression, ...],
    facts: Mapping[str, FactValue],
) -> tuple[FactExpression, ...]:
    """Remove requirements already true in the supplied subjective state."""
    return tuple(
        expression
        for expression in expressions
        if evaluate_fact_expression(expression, facts) is not TruthValue.TRUE
    )


def _flatten_conjunction(expression: FactExpression) -> tuple[FactExpression, ...]:
    """Flatten only conjunctions while retaining disjunction semantics."""
    if expression.operator is not FactOperator.ALL:
        return (expression,)
    return tuple(
        nested
        for operand in expression.operands
        for nested in _flatten_conjunction(operand)
    )


def _expressions_identity(expressions: tuple[FactExpression, ...]) -> str:
    """Return a deterministic search key for unresolved requirements."""
    payload = [
        expression.model_dump(mode="json")
        for expression in expressions
    ]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
