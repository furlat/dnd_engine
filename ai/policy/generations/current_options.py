"""Mechanical option-level contracts derived from authored policy routines."""

from __future__ import annotations

from ai.planning.composition import compose_option
from ai.planning.contracts import LogicalStep, OptionContract
from ai.policy.routines import (
    APPROACH_OPEN_REASSESS,
    REGISTERED_ROUTINES,
    RoutineContract,
)
from dnd.ai.contracts.semantics import (
    FactExpression,
    FactOperator,
)


def compose_routine_option(contract: RoutineContract) -> OptionContract:
    """Derive option prerequisites and consequences from one routine."""
    logical_steps = tuple(
        LogicalStep(
            step_id=f"{contract.routine_id}:{step.step_id}",
            description=step.description,
            preconditions=_all(
                contract.applicability if index == 0 else contract.invariants,
                step.preconditions,
            ),
            guaranteed_effects=step.expected_effects,
            explicit_observation_barrier=_step_requires_observation(
                contract,
                step.step_id,
            ),
        )
        for index, step in enumerate(contract.steps)
    )
    return compose_option(
        contract.routine_id,
        logical_steps,
        completion=contract.completion,
        invalidation=FactExpression(
            operator=FactOperator.NOT,
            operands=(contract.invariants,),
        ),
    )


def compose_registered_routine_options() -> tuple[OptionContract, ...]:
    """Compile all authored routines in stable registry order."""
    return tuple(
        compose_routine_option(registered.contract)
        for registered in REGISTERED_ROUTINES
    )


def option_for_routine(routine_id: str) -> OptionContract:
    """Return one compiled routine option or reject an unknown identity."""
    for option in compose_registered_routine_options():
        if option.option_id == routine_id:
            return option
    raise ValueError(f"Unknown routine option: {routine_id}")


def _step_requires_observation(
    contract: RoutineContract,
    step_id: str,
) -> bool:
    """Mark explicit reassessment and door-open sensory boundaries."""
    return (
        step_id == "reassess"
        or (
            contract.routine_id == APPROACH_OPEN_REASSESS.routine_id
            and step_id == "open"
        )
    )


def _all(
    *expressions: FactExpression,
) -> FactExpression:
    """Build one conjunction without changing authored expressions."""
    return FactExpression(
        operator=FactOperator.ALL,
        operands=expressions,
    )

