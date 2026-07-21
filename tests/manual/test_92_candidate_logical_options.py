"""Candidate logical annotations and authored routine option compilation."""

from ai.planning.contracts import RequirementKind
from ai.planning.registry import (
    contract_for_policy_method,
    registered_policy_method_contracts,
)
from ai.policy.generations.current_candidate import (
    _generic_semantic_candidates,
    _plan_position_then_pressure_routine,
    build_current_candidate_set,
    plan_current_routines,
)
from ai.policy.generations.current_options import (
    compose_registered_routine_options,
    option_for_routine,
)
from ai.policy.routines import APPROACH_OPEN_REASSESS, REGISTERED_ROUTINES
from ai.protocol.semantics import EffectOperation


def test_every_current_candidate_entry_method_has_logical_contract() -> None:
    """Production candidate entry methods must expose executable metadata."""
    methods = (
        build_current_candidate_set,
        plan_current_routines,
        _generic_semantic_candidates,
        _plan_position_then_pressure_routine,
    )

    contracts = tuple(contract_for_policy_method(method) for method in methods)

    assert {contract.method_id for contract in contracts} == {
        "current.build_candidates",
        "current.plan_routines",
        "current.admit_typed_effects",
        "current.position_then_pressure",
    }
    assert all(contract.preconditions is not None for contract in contracts)
    assert all(contract.completion is not None for contract in contracts)
    assert all(contract.invalidation is not None for contract in contracts)


def test_registered_annotation_catalog_is_stable_and_unique() -> None:
    """The logical registry should expose each method contract exactly once."""
    contracts = registered_policy_method_contracts()
    identities = tuple(contract.method_id for contract in contracts)

    assert identities == tuple(sorted(set(identities)))
    assert "current.position_then_pressure" in identities


def test_every_authored_routine_compiles_to_option_contract() -> None:
    """Routine prerequisites and effects should compose mechanically."""
    options = compose_registered_routine_options()

    assert tuple(option.option_id for option in options) == tuple(
        registered.contract.routine_id
        for registered in REGISTERED_ROUTINES
    )
    assert all(option.proof.prerequisites for option in options)
    assert all(option.completion is not None for option in options)
    assert all(option.invalidation is not None for option in options)


def test_door_option_stops_at_open_for_real_sensory_feedback() -> None:
    """The compiler cannot predict entities or cells revealed behind a door."""
    option = option_for_routine(APPROACH_OPEN_REASSESS.routine_id)

    assert option.requires_observation
    barrier = option.proof.observation_barriers[0]
    assert barrier.after_step_id == f"{APPROACH_OPEN_REASSESS.routine_id}:open"
    reassess = next(
        proof
        for proof in option.proof.prerequisites
        if proof.step_id.endswith(":reassess")
    )
    assert reassess.kind is RequirementKind.OBSERVATION_DEFERRED
    assert all(
        effect.fact_id != "enemy.visible"
        for effect in option.guaranteed_effects
    )
    assert any(
        effect.fact_id == "routine.target.open"
        and effect.operation is EffectOperation.SET
        for effect in option.guaranteed_effects
    )



def test_commitment_descriptor_uses_authored_routine_option() -> None:
    """Routine-backed proposals retain option-level consequences in live traces."""
    from ai.knowledge import derive_agent_facts
    from ai.policy.contracts import PolicyContext, PolicyGoal
    from ai.policy.generations.current_commitments import describe_proposal
    from ai.policy.routines import RoutinePlan, RoutinePlanStatus
    from tests.manual.test_91_candidate_commitments import _pressure
    from tests.manual.test_44_typed_agent_policy import _world

    world = _world()
    proposal = _pressure("visible-enemy", 75.0).model_copy(
        update={"goal": PolicyGoal.ROUTINE}
    )
    routine_plan = RoutinePlan(
        routine_id=APPROACH_OPEN_REASSESS.routine_id,
        purpose=APPROACH_OPEN_REASSESS.purpose,
        status=RoutinePlanStatus.PROPOSED,
        step_id="open",
        target_uuid="visible-enemy",
        proposal=proposal,
        reason="test_routine_descriptor",
    )
    context = PolicyContext(world=world, facts=derive_agent_facts(world).facts)

    descriptor = describe_proposal(context, proposal, routine_plan)

    assert descriptor.option_id == APPROACH_OPEN_REASSESS.routine_id
    assert descriptor.logical_option is not None
    assert descriptor.logical_option.option_id == APPROACH_OPEN_REASSESS.routine_id
    assert descriptor.logical_option.requires_observation
