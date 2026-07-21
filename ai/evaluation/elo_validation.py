"""Consistency validation for retained Elo evaluator summaries."""

from pathlib import Path

from ai.evaluation.constants import REQUIRED_SUBJECTIVITY_VALIDATOR
from ai.evaluation.elo_contract import EloGauntletSummary


def validate_elo_summary(summary: EloGauntletSummary) -> EloGauntletSummary:
    """Validate counters and rating references in a retained summary.

    Args:
        summary: Summary to validate.

    Returns:
        The same summary when consistent.

    Raises:
        ValueError: If aggregate counters or rating references contradict the
            retained match records.
    """
    if summary.completed_count != len(summary.matches):
        raise ValueError("completed_count does not match retained matches")
    if summary.completed_count + summary.pending_count != summary.scheduled_count:
        raise ValueError("completed_count + pending_count does not match scheduled_count")
    eligible_count = sum(1 for match in summary.matches if match.eligibility.rating_eligible)
    if summary.eligible_count != eligible_count:
        raise ValueError("eligible_count does not match retained eligibility")
    skipped_count = len(summary.matches) - eligible_count
    if summary.skipped_rating_count != skipped_count:
        raise ValueError("skipped_rating_count does not match retained eligibility")
    failed_count = sum(
        1
        for match in summary.matches
        if not match.eligibility.rating_eligible or match.base_record is None
    )
    if summary.failed_count != failed_count:
        raise ValueError("failed_count does not match retained rows")
    expected_entries = {entry.match_index: entry for entry in summary.schedule.entries}
    seen_indices: set[int] = set()
    for match in summary.matches:
        if match.match_index in seen_indices:
            raise ValueError(f"duplicate retained match index: {match.match_index}")
        seen_indices.add(match.match_index)
        if expected_entries.get(match.match_index) != match.schedule_entry:
            raise ValueError(f"retained schedule row mismatch at index {match.match_index}")
        if not match.eligibility.rating_eligible:
            continue
        if match.arena_manifest is None:
            raise ValueError(f"eligible match lacks arena manifest: {match.match_id}")
        if not {"heroes", "monsters"}.issubset(
            {participant.side for participant in match.participants}
        ):
            raise ValueError(f"eligible match lacks both participant sides: {match.match_id}")
        if match.runtime_policy_version != match.schedule_entry.policy_version:
            raise ValueError(f"eligible match policy identity mismatch: {match.match_id}")
        if match.runtime_controller_profile != match.schedule_entry.controller_profile:
            raise ValueError(f"eligible match controller identity mismatch: {match.match_id}")
        if not match.runtime_policy_source_hash:
            raise ValueError(f"eligible match lacks policy source hash: {match.match_id}")
        if match.runtime_subjectivity_validator != REQUIRED_SUBJECTIVITY_VALIDATOR:
            raise ValueError(f"eligible match lacks the independent subjectivity witness: {match.match_id}")
        if not match.artifact_paths or any(not Path(path).is_file() for path in match.artifact_paths):
            raise ValueError(f"eligible match lacks a valid raw artifact: {match.match_id}")
    expected_failure_ids = {
        match.match_id
        for match in summary.matches
        if not match.eligibility.rating_eligible or match.base_record is None
    }
    retained_failure_ids = {str(row.get("match_id")) for row in summary.failure_rows}
    if retained_failure_ids != expected_failure_ids:
        raise ValueError("failure_rows do not match abnormal retained rows")
    known_participants = {
        participant.participant_id
        for match in summary.matches
        for participant in match.participants
    }
    for ledger in summary.ledgers.values():
        previous_index = -1
        for snapshot in ledger.rating_series:
            if snapshot.participant_id not in known_participants:
                raise ValueError(
                    f"rating series references unknown participant: {snapshot.participant_id}"
                )
            if snapshot.match_index < previous_index:
                raise ValueError(f"rating series is not schedule ordered: {ledger.ledger_name}")
            previous_index = snapshot.match_index
    event_cursors = [event.cursor for event in summary.events]
    if event_cursors != sorted(set(event_cursors)):
        raise ValueError("watcher event cursors are not strictly monotonic")
    return summary
