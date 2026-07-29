"""Executable contracts for logical option composition and regression."""

from __future__ import annotations

import pytest

from ai.planning.composition import compose_option
from ai.planning.contracts import LogicalStep, RequirementKind
from ai.planning.registry import (
    PolicyMethodContract,
    contract_for_policy_method,
    logical_policy_method,
    registered_policy_method_contracts,
)
from dnd.ai.contracts.semantics import (
    ComparisonOperator,
    EffectCertainty,
    EffectOperation,
    FactExpression,
    FactOperator,
    FactPredicate,
    FactValue,
    InformationEffect,
    InformationOperation,
    LogicalEffect,
    OutcomeKind,
    ResourceEffect,
    ResourceOperation,
    StochasticEffect,
    TruthValue,
    WorldEffectAnchor,
    WorldEffectScope,
)


def _fact(
    fact_id: str,
    expected_value: FactValue = True,
    comparison: ComparisonOperator = ComparisonOperator.EQUALS,
) -> FactExpression:
    """Build one test predicate."""
    return FactExpression(
        operator=FactOperator.PREDICATE,
        predicate=FactPredicate(
            fact_id=fact_id,
            expected_value=expected_value,
            comparison=comparison,
        ),
    )


def _all(*expressions: FactExpression) -> FactExpression:
    """Build one conjunction."""
    return FactExpression(operator=FactOperator.ALL, operands=expressions)


def _set(fact_id: str, value: FactValue) -> LogicalEffect:
    """Build one literal guaranteed effect."""
    return LogicalEffect(
        fact_id=fact_id,
        operation=EffectOperation.SET,
        value=value,
    )


def test_forward_composition_proves_move_enables_attack() -> None:
    """A prior effect should discharge a later range prerequisite."""
    move = LogicalStep(
        step_id="move",
        preconditions=_fact("actor.can_act"),
        guaranteed_effects=(_set("target.in_range", True),),
    )
    attack = LogicalStep(
        step_id="attack",
        preconditions=_all(
            _fact("actor.can_act"),
            _fact("target.in_range"),
        ),
        guaranteed_effects=(_set("target.damaged", True),),
    )

    option = compose_option(
        "pressure.move_then_attack",
        (move, attack),
        completion=_fact("target.damaged"),
        initial_facts={"actor.can_act": True},
    )

    assert option.consistent
    assert not option.initial_preconditions
    assert option.final_known_facts["target.damaged"] is True
    assert option.proof.prerequisites[1].kind is RequirementKind.SATISFIED
    assert option.proof.prerequisites[1].established_by_step_ids == ("move",)


def test_forward_composition_reports_guaranteed_conflict() -> None:
    """A guaranteed contradiction must invalidate the deterministic chain."""
    close_route = LogicalStep(
        step_id="close_route",
        preconditions=FactExpression.true(),
        guaranteed_effects=(_set("route.open", False),),
    )
    traverse = LogicalStep(
        step_id="traverse",
        preconditions=_fact("route.open"),
        guaranteed_effects=(_set("actor.crossed", True),),
    )

    option = compose_option("invalid.closed_route", (close_route, traverse))

    assert not option.consistent
    assert option.proof.prerequisites[1].kind is RequirementKind.CONFLICT
    assert option.proof.conflicts[0].step_id == "traverse"
    assert "actor.crossed" not in option.final_known_facts


def test_stochastic_effect_creates_contingent_continuation() -> None:
    """A possible effect cannot masquerade as a guaranteed prerequisite."""
    control = LogicalStep(
        step_id="hold_person",
        preconditions=FactExpression.true(),
        stochastic_effects=(StochasticEffect(
            outcome_kind=OutcomeKind.SAVING_THROW,
            probability=0.55,
            effects=(_set("target.paralyzed", True),),
        ),),
    )
    exploit = LogicalStep(
        step_id="exploit_control",
        preconditions=_fact("target.paralyzed"),
        guaranteed_effects=(_set("target.exploited", True),),
    )

    option = compose_option("control.then_exploit", (control, exploit))

    assert option.consistent
    assert option.proof.prerequisites[1].kind is RequirementKind.CONTINGENT
    assert "target.paralyzed" not in option.final_known_facts
    assert option.proof.contingent_branches[0].probability == 0.55


def test_resource_projection_uses_maximum_prefix_deficit() -> None:
    """Option requirements should reflect resource order, not only final delta."""
    steps = (
        LogicalStep(
            step_id="spend",
            preconditions=FactExpression.true(),
            resource_effects=(ResourceEffect(
                resource_id="actions",
                operation=ResourceOperation.CONSUME,
                amount=1,
            ),),
        ),
        LogicalStep(
            step_id="restore",
            preconditions=FactExpression.true(),
            resource_effects=(ResourceEffect(
                resource_id="actions",
                operation=ResourceOperation.RESTORE,
                amount=1,
            ),),
        ),
        LogicalStep(
            step_id="spend_again",
            preconditions=FactExpression.true(),
            resource_effects=(ResourceEffect(
                resource_id="actions",
                operation=ResourceOperation.CONSUME,
                amount=1,
            ),),
        ),
    )

    projection = compose_option("resource.prefix", steps).proof.resources[0]

    assert projection.minimum_initial_amount == 1
    assert projection.final_delta == -1
    assert projection.total_consumed == 2
    assert projection.total_restored_or_acquired == 1


def test_information_effect_stops_prediction_at_observation_barrier() -> None:
    """Door revelation must defer downstream logic to real sensory feedback."""
    open_door = LogicalStep(
        step_id="open_door",
        preconditions=_fact("door.closed"),
        guaranteed_effects=(_set("door.open", True),),
        information_effects=(InformationEffect(
            operation=InformationOperation.REVEAL_FRONTIER,
            certainty=EffectCertainty.POTENTIAL,
            anchor=WorldEffectAnchor.SELECTED_OBJECT,
            scope=WorldEffectScope.FRONTIER,
            scope_ref="door.far_side",
        ),),
    )
    attack_revealed = LogicalStep(
        step_id="attack_revealed",
        preconditions=_fact("enemy.visible"),
        guaranteed_effects=(_set("enemy.damaged", True),),
    )

    option = compose_option(
        "door.open_then_reassess",
        (open_door, attack_revealed),
        initial_facts={"door.closed": True},
    )

    assert option.requires_observation
    assert option.proof.observation_barriers[0].after_step_id == "open_door"
    assert option.proof.prerequisites[1].kind is RequirementKind.OBSERVATION_DEFERRED
    assert option.final_known_facts["door.open"] is True
    assert "enemy.visible" not in option.final_known_facts
    assert "enemy.damaged" not in option.final_known_facts


def test_policy_method_annotations_are_executable_metadata_not_wrappers() -> None:
    """Logical annotations should preserve call identity and expose contracts."""
    contract = PolicyMethodContract(
        method_id="pressure.test",
        preconditions=_fact("actor.can_act"),
        progress_effects=(_set("target.pressured", True),),
        completion=_fact("target.pressured"),
        invalidation=FactExpression(
            operator=FactOperator.CONSTANT,
            constant=TruthValue.FALSE,
        ),
    )

    @logical_policy_method(contract)
    def propose(value: int) -> int:
        return value + 1

    assert propose(2) == 3
    assert contract_for_policy_method(propose) is contract
    assert contract in registered_policy_method_contracts()


def test_composition_final_facts_are_stable_and_immutable() -> None:
    """Derived fact maps retain deterministic insertion order and immutability."""
    option = compose_option(
        "stable",
        (LogicalStep(
            step_id="set",
            preconditions=FactExpression.true(),
            guaranteed_effects=(_set("fact.b", True), _set("fact.a", True)),
        ),),
    )

    assert tuple(option.final_known_facts) == ("fact.b", "fact.a")
    with pytest.raises(TypeError):
        option.final_known_facts["fact.c"] = True
