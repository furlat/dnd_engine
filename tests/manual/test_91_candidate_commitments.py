"""Candidate-only tactical commitment persistence and isolation."""

from __future__ import annotations

from ai.knowledge import derive_agent_facts
from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationEntityFact,
    SubjectiveWorldState,
)
from ai.policy.candidates import PolicyCandidateSet
from ai.policy.contracts import (
    ExplorationEvidence,
    PolicyContext,
    PolicyEvidence,
    PolicyGoal,
    PolicyProposal,
    TargetPlanEvidence,
)
from dnd.ai.contracts.decision import ExecuteIntent
from ai.policy.generations.current_commitments import (
    CandidateCommitmentEvaluator,
    CommitmentStatus,
    CommitmentTransitionKind,
    CurrentCandidatePolicyHost,
    create_generation_policy_host,
)
from ai.policy.generations.registry import (
    ACTIVE_GENERATION_ID,
    get_active_policy_implementation,
)
from dnd.ai.contracts.control import (
    ActionResolutionStatus,
    CommandResult,
    CommandResultStatus,
)
from tests.manual.test_44_typed_agent_policy import _world


def _context(world: object) -> PolicyContext:
    """Derive a strictly aligned context from one subjective test world."""

    assert isinstance(world, SubjectiveWorldState)
    return PolicyContext(world=world, facts=derive_agent_facts(world).facts)


def _pressure(
    target_uuid: str,
    score: float,
    *,
    row_id: str | None = None,
) -> PolicyProposal:
    """Build one typed direct-pressure proposal."""
    return PolicyProposal(
        intent=ExecuteIntent(row_id=row_id or f"attack-{target_uuid}"),
        goal=PolicyGoal.DIRECT_PRESSURE,
        source_node="Test/Pressure",
        reason=f"pressure_{target_uuid}",
        score=score,
        evidence=PolicyEvidence(target_plan=TargetPlanEvidence(
            primary_target_uuid=target_uuid,
            selected_target_uuids=(target_uuid,),
            affected_entity_uuids=(target_uuid,),
            hostile_entity_uuids=(target_uuid,),
        )),
    )


def _search(target_uuid: str, score: float) -> PolicyProposal:
    """Build one remembered-contact investigation proposal."""
    return PolicyProposal(
        intent=ExecuteIntent(row_id=f"search-{target_uuid}"),
        goal=PolicyGoal.INFORMATION_GATHERING,
        source_node="Test/Search",
        reason="investigate_remembered_contact",
        score=score,
        evidence=PolicyEvidence(exploration=ExplorationEvidence(
            anchor_position=(3, 0),
            movement_cost=15,
            unknown_frontier_count=1,
            remembered_target_uuid=target_uuid,
            hazardous_route=False,
            slow_path_cells=0,
        )),
    )


def _survival(score: float) -> PolicyProposal:
    """Build one explicit survival-recovery proposal."""
    return PolicyProposal(
        intent=ExecuteIntent(row_id="healing"),
        goal=PolicyGoal.SURVIVAL_RECOVERY,
        source_node="Test/Healing",
        reason="recover_critical_hp",
        score=score,
    )


def _candidates(
    *,
    pressure: tuple[PolicyProposal, ...] = (),
    healing: tuple[PolicyProposal, ...] = (),
    exploration: tuple[PolicyProposal, ...] = (),
) -> PolicyCandidateSet:
    """Build a compact candidate set for commitment arbitration."""
    return PolicyCandidateSet(
        direct_damage=pressure,
        healing=healing,
        control=(),
        control_preservation=(),
        target_effects=(),
        self_setup=(),
        spacing=(),
        exploration=exploration,
    )


def _two_target_world() -> object:
    """Add a second visible hostile without exposing objective data."""
    world = _world()
    entities = dict(world.known_entities)
    entities["enemy-b"] = entities["visible-enemy"].model_copy(update={
        "uuid": "enemy-b",
        "name": "Second Skeleton",
        "position": (3, 0),
        "hp": 12,
        "max_hp": 12,
    })
    return world.model_copy(update={"known_entities": entities})


def test_commitment_retains_target_across_small_utility_fluctuation() -> None:
    """A marginal alternative cannot erase unfinished tactical intention."""
    evaluator = CandidateCommitmentEvaluator(policy_id="candidate")
    context = _context(_two_target_world())

    first = evaluator(
        context,
        (),
        _candidates(pressure=(_pressure("visible-enemy", 100.0),)),
    )
    second = evaluator(
        context,
        (),
        _candidates(pressure=(
            _pressure("enemy-b", 80.0),
            _pressure("visible-enemy", 70.0),
        )),
    )

    assert first.decision is not None
    assert second.decision is not None
    assert second.decision.selected.evidence.target_plan is not None
    assert second.decision.selected.evidence.target_plan.primary_target_uuid == "visible-enemy"
    commitment = evaluator.store.session("session", "candidate")
    assert commitment is not None
    assert commitment.subject.subject_uuid == "visible-enemy"
    transition = evaluator.store.last_transition_by_session[("session", "candidate")]
    assert transition.kind is CommitmentTransitionKind.RETAIN
    assert transition.required_switch_advantage == 18.0
    assert any(
        "alternative_did_not_exceed_explicit_switch_threshold" in step.detail
        for step in second.decision.trace
    )


def test_commitment_switches_when_material_dominance_exceeds_all_costs() -> None:
    """A materially superior target may replace the incumbent with a trace."""
    evaluator = CandidateCommitmentEvaluator(policy_id="candidate")
    context = _context(_two_target_world())
    evaluator(
        context,
        (),
        _candidates(pressure=(_pressure("visible-enemy", 100.0),)),
    )

    evaluation = evaluator(
        context,
        (),
        _candidates(pressure=(
            _pressure("enemy-b", 100.0),
            _pressure("visible-enemy", 70.0),
        )),
    )

    assert evaluation.decision is not None
    assert evaluation.decision.selected.evidence.target_plan is not None
    assert evaluation.decision.selected.evidence.target_plan.primary_target_uuid == "enemy-b"
    commitment = evaluator.store.session("session", "candidate")
    assert commitment is not None
    assert commitment.subject.subject_uuid == "enemy-b"
    transition = evaluator.store.last_transition_by_session[("session", "candidate")]
    assert transition.kind is CommitmentTransitionKind.SWITCH


def test_known_target_death_completes_and_releases_commitment() -> None:
    """Known death should complete immediately rather than becoming uncertainty."""
    evaluator = CandidateCommitmentEvaluator(policy_id="candidate")
    world = _world()
    evaluator(
        _context(world),
        (),
        _candidates(pressure=(_pressure("visible-enemy", 100.0),)),
    )
    entities = dict(world.known_entities)
    entities["visible-enemy"] = entities["visible-enemy"].model_copy(
        update={"is_dead": True, "hp": 0}
    )
    dead_world = world.model_copy(update={"known_entities": entities})

    evaluator(_context(dead_world), (), _candidates())

    assert evaluator.store.session("session", "candidate") is None
    transition = evaluator.store.last_transition_by_session[("session", "candidate")]
    assert transition.kind is CommitmentTransitionKind.COMPLETE


def test_remembered_target_suspends_pressure_and_permits_only_search() -> None:
    """Last-known position supports investigation but not direct targeting."""
    evaluator = CandidateCommitmentEvaluator(policy_id="candidate")
    world = _world()
    evaluator(
        _context(world),
        (),
        _candidates(pressure=(_pressure("visible-enemy", 100.0),)),
    )
    entities = dict(world.known_entities)
    entities["visible-enemy"] = entities["visible-enemy"].model_copy(
        update={"knowledge_state": KnowledgeState.REMEMBERED}
    )
    remembered_world = world.model_copy(update={"known_entities": entities})

    evaluation = evaluator(
        _context(remembered_world),
        (),
        _candidates(
            pressure=(_pressure("visible-enemy", 500.0),),
            exploration=(_search("visible-enemy", 30.0),),
        ),
    )

    assert evaluation.decision is not None
    assert evaluation.decision.selected.goal is PolicyGoal.INFORMATION_GATHERING
    commitment = evaluator.store.session("session", "candidate")
    assert commitment is not None
    assert commitment.status is CommitmentStatus.SUSPENDED


def test_low_hp_survival_is_explicit_interrupt_not_goal_erasure() -> None:
    """Critical recovery may interrupt while preserving the team objective."""
    evaluator = CandidateCommitmentEvaluator(policy_id="candidate")
    world = _world()
    evaluator(
        _context(world),
        (),
        _candidates(pressure=(_pressure("visible-enemy", 100.0),)),
    )
    entities = dict(world.known_entities)
    entities["actor"] = entities["actor"].model_copy(
        update={"hp": 5, "normal_hp": 5, "max_hp": 20}
    )
    critical_world = world.model_copy(update={"known_entities": entities})

    evaluation = evaluator(
        _context(critical_world),
        (),
        _candidates(
            pressure=(_pressure("visible-enemy", 70.0),),
            healing=(_survival(120.0),),
        ),
    )

    assert evaluation.decision is not None
    assert evaluation.decision.selected.goal is PolicyGoal.SURVIVAL_RECOVERY
    commitment = evaluator.store.session("session", "candidate")
    assert commitment is not None
    assert commitment.subject.subject_uuid == "visible-enemy"
    transition = evaluator.store.last_transition_by_session[("session", "candidate")]
    assert transition.kind is CommitmentTransitionKind.INTERRUPT


def test_session_commitment_is_shared_across_controlled_actors() -> None:
    """A second controlled actor should bind to the same team objective."""
    evaluator = CandidateCommitmentEvaluator(policy_id="candidate")
    world = _world()
    evaluator(
        _context(world),
        (),
        _candidates(pressure=(_pressure("visible-enemy", 100.0),)),
    )
    epoch = world.current_epoch
    assert epoch is not None
    entities = dict(world.known_entities)
    entities["actor-b"] = ObservationEntityFact(
        uuid="actor-b",
        name="Second Controller",
        knowledge_state=KnowledgeState.VISIBLE,
        controlled=True,
        position=(0, 1),
        hp=20,
        max_hp=20,
        faction="heroes",
    )
    session = world.session.model_copy(update={
        "controlled_entity_uuids": ("actor", "actor-b"),
        "active_entity_uuid": "actor-b",
        "active_entity_name": "Second Controller",
    })
    affordances = epoch.affordances.model_copy(update={"actor_uuid": "actor-b"})
    second_epoch = epoch.model_copy(update={
        "epoch_id": "epoch-actor-b",
        "actor_uuid": "actor-b",
        "economy": epoch.economy.model_copy(update={"actor_uuid": "actor-b"}),
        "affordances": affordances,
    })
    second_world = world.model_copy(update={
        "session": session,
        "known_entities": entities,
        "current_epoch": second_epoch,
    })

    evaluator(
        _context(second_world),
        (),
        _candidates(pressure=(_pressure("visible-enemy", 70.0),)),
    )

    session_commitment = evaluator.store.session("session", "candidate")
    actor_commitment = evaluator.store.actor("session", "actor-b", "candidate")
    assert session_commitment is not None
    assert actor_commitment is not None
    assert actor_commitment.parent_commitment_id == session_commitment.commitment_id


def test_candidate_stores_are_isolated_and_contain_no_epoch_rows_or_worlds() -> None:
    """Candidate control state must be session-local and contain no world copies."""
    first = CandidateCommitmentEvaluator(policy_id="candidate-a")
    second = CandidateCommitmentEvaluator(policy_id="candidate-b")
    context = _context(_world())
    first(
        context,
        (),
        _candidates(pressure=(_pressure("visible-enemy", 100.0),)),
    )

    assert second.store.session("session", "candidate-b") is None
    commitment = first.store.session("session", "candidate-a")
    assert commitment is not None
    payload = commitment.model_dump(mode="json")
    serialized = str(payload)
    assert "row_id" not in serialized
    assert "known_entities" not in serialized
    assert "current_epoch" not in serialized


def test_active_policy_host_owns_commitment_behavior() -> None:
    """The sole advanced policy uses the commitment-aware host."""
    implementation = get_active_policy_implementation()
    host = create_generation_policy_host(implementation)

    assert isinstance(host, CurrentCandidatePolicyHost)
    assert "ai/policy/generations/current_commitments.py" in implementation.identity.implementation_paths


def test_authoritative_result_gate_advances_only_completed_acceptance() -> None:
    """Rejected or stale commands cannot advance candidate progress."""
    implementation = get_active_policy_implementation()
    host = create_generation_policy_host(implementation)
    assert isinstance(host, CurrentCandidatePolicyHost)
    world = _world()
    decision = host.decide(world)
    assert decision.selected.goal is PolicyGoal.DIRECT_PRESSURE
    epoch = world.current_epoch
    assert epoch is not None
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id=epoch.epoch_id,
        command_id="accepted-command",
    )
    intent = decision.selected.intent
    assert isinstance(intent, ExecuteIntent)

    host.record_result(CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="accepted-command",
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id=epoch.epoch_id,
        current_epoch_id="epoch-2",
        row_id=intent.row_id,
        action_resolution=ActionResolutionStatus.COMPLETED,
    ))

    commitment = host.commitment_store.session(
        "session",
        ACTIVE_GENERATION_ID,
    )
    assert commitment is not None
    assert commitment.accepted_steps == 1
