"""Logical method contracts owned exclusively by the current candidate."""

from ai.planning.registry import PolicyMethodContract
from dnd.ai.contracts.semantics import (
    ComparisonOperator,
    EffectOperation,
    FactExpression,
    FactOperator,
    FactPredicate,
    FactValue,
    LogicalEffect,
    TruthValue,
)


def _predicate(
    fact_id: str,
    expected_value: FactValue,
    comparison: ComparisonOperator = ComparisonOperator.EQUALS,
) -> FactExpression:
    """Build one current-generation method predicate."""
    return FactExpression(
        operator=FactOperator.PREDICATE,
        predicate=FactPredicate(
            fact_id=fact_id,
            expected_value=expected_value,
            comparison=comparison,
        ),
    )


def _false() -> FactExpression:
    """Return an always-false invalidation condition."""
    return FactExpression(
        operator=FactOperator.CONSTANT,
        constant=TruthValue.FALSE,
    )


BUILD_CURRENT_CANDIDATES_CONTRACT = PolicyMethodContract(
    method_id="current.build_candidates",
    preconditions=_predicate("actor.is_active", True),
    progress_effects=(),
    completion=FactExpression.true(),
    invalidation=_predicate("actor.is_active", False),
)

PLAN_CURRENT_ROUTINES_CONTRACT = PolicyMethodContract(
    method_id="current.plan_routines",
    preconditions=_predicate("actor.is_active", True),
    progress_effects=(LogicalEffect(
        fact_id="actor.option_method_available",
        operation=EffectOperation.SET,
        value=True,
    ),),
    completion=_predicate("actor.option_method_available", True),
    invalidation=_predicate("actor.is_active", False),
)

GENERIC_SEMANTIC_ADMISSION_CONTRACT = PolicyMethodContract(
    method_id="current.admit_typed_effects",
    preconditions=_predicate("actor.legal_affordance_count", 0, ComparisonOperator.GREATER_THAN),
    progress_effects=(LogicalEffect(
        fact_id="actor.typed_effect_coverage_audited",
        operation=EffectOperation.SET,
        value=True,
    ),),
    completion=_predicate("actor.typed_effect_coverage_audited", True),
    invalidation=_false(),
)

POSITION_THEN_PRESSURE_CONTRACT = PolicyMethodContract(
    method_id="current.position_then_pressure",
    preconditions=_predicate("visible_hostile.count", 0, ComparisonOperator.GREATER_THAN),
    progress_effects=(LogicalEffect(
        fact_id="actor.route_deficit_to_capability_envelope",
        operation=EffectOperation.DECREASE,
    ),),
    completion=_predicate("routine.semantic_goal.legal", True),
    invalidation=_predicate("routine.target.visible", False),
)

