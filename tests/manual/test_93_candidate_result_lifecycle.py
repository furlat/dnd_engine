"""Candidate command-result lifecycle gates for non-pathological intent memory."""

from __future__ import annotations

from ai.policy.contracts import ExecuteIntent, PolicyGoal
from ai.policy.generations.current_commitments import CurrentCandidatePolicyHost, create_generation_policy_host
from ai.policy.generations.registry import CANDIDATE_GENERATION_ID, get_policy_implementation
from ai.policy.host import PolicyResultDisposition
from server.agent_protocol.control import ActionResolutionStatus, CommandResult, CommandResultStatus
from tests.manual.test_44_typed_agent_policy import _world


def _candidate_host_with_pending(command_id: str) -> tuple[CurrentCandidatePolicyHost, str, str]:
    """Create one candidate host, decision, and pending command."""
    host = create_generation_policy_host(get_policy_implementation(CANDIDATE_GENERATION_ID))
    assert isinstance(host, CurrentCandidatePolicyHost)
    world = _world()
    decision = host.decide(world)
    assert decision.selected.goal is PolicyGoal.DIRECT_PRESSURE
    assert isinstance(decision.selected.intent, ExecuteIntent)
    epoch = world.current_epoch
    assert epoch is not None
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id=epoch.epoch_id,
        command_id=command_id,
    )
    return host, epoch.epoch_id, decision.selected.intent.row_id


def _result(
    *,
    command_id: str,
    epoch_id: str,
    row_id: str,
    status: CommandResultStatus,
    resolution: ActionResolutionStatus | None = None,
) -> CommandResult:
    """Build one correlated authoritative command result."""
    return CommandResult(
        status=status,
        command_id=command_id,
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id=epoch_id,
        current_epoch_id="epoch-after",
        row_id=row_id,
        action_resolution=resolution,
    )


def _accepted_steps(host: CurrentCandidatePolicyHost) -> int:
    """Return retained candidate progress for the current test session."""
    commitment = host.commitment_store.session("session", CANDIDATE_GENERATION_ID)
    assert commitment is not None
    return commitment.accepted_steps


def test_completed_acceptance_advances_commitment_once() -> None:
    """Only one matching accepted completed result counts as progress."""
    host, epoch_id, row_id = _candidate_host_with_pending("cmd-complete")

    first = host.record_result(_result(
        command_id="cmd-complete",
        epoch_id=epoch_id,
        row_id=row_id,
        status=CommandResultStatus.ACCEPTED,
        resolution=ActionResolutionStatus.COMPLETED,
    ))
    duplicate = host.record_result(_result(
        command_id="cmd-complete",
        epoch_id=epoch_id,
        row_id=row_id,
        status=CommandResultStatus.ACCEPTED,
        resolution=ActionResolutionStatus.COMPLETED,
    ))

    assert first.disposition is PolicyResultDisposition.ACCEPTED
    assert duplicate.disposition is PolicyResultDisposition.ALREADY_RECORDED
    assert _accepted_steps(host) == 1


def test_rejected_and_stale_results_do_not_advance_commitments() -> None:
    """Controller-protocol failures cannot create tactical progress."""
    for status in (CommandResultStatus.REJECTED, CommandResultStatus.STALE):
        host, epoch_id, row_id = _candidate_host_with_pending(f"cmd-{status.value}")

        record = host.record_result(_result(
            command_id=f"cmd-{status.value}",
            epoch_id=epoch_id,
            row_id=row_id,
            status=status,
        ))

        assert record.disposition.value == status.value
        assert _accepted_steps(host) == 0


def test_canceled_or_interrupted_acceptance_does_not_advance_commitments() -> None:
    """Partial or canceled engine outcomes must force reassessment, not progress."""
    for resolution in (ActionResolutionStatus.CANCELED, ActionResolutionStatus.INTERRUPTED):
        host, epoch_id, row_id = _candidate_host_with_pending(f"cmd-{resolution.value}")

        record = host.record_result(_result(
            command_id=f"cmd-{resolution.value}",
            epoch_id=epoch_id,
            row_id=row_id,
            status=CommandResultStatus.ACCEPTED,
            resolution=resolution,
        ))

        assert record.disposition is PolicyResultDisposition.ACCEPTED
        assert _accepted_steps(host) == 0


def test_mismatched_result_preserves_pending_submission_and_no_progress() -> None:
    """A wrong row result is ignored until the matching command result arrives."""
    host, epoch_id, row_id = _candidate_host_with_pending("cmd-mismatch")

    mismatch = host.record_result(_result(
        command_id="cmd-mismatch",
        epoch_id=epoch_id,
        row_id="wrong-row",
        status=CommandResultStatus.ACCEPTED,
        resolution=ActionResolutionStatus.COMPLETED,
    ))
    matching = host.record_result(_result(
        command_id="cmd-mismatch",
        epoch_id=epoch_id,
        row_id=row_id,
        status=CommandResultStatus.ACCEPTED,
        resolution=ActionResolutionStatus.COMPLETED,
    ))

    assert mismatch.disposition is PolicyResultDisposition.UNMATCHED
    assert matching.disposition is PolicyResultDisposition.ACCEPTED
    assert _accepted_steps(host) == 1
