from typing import Literal

from ai.evaluation.constants import REQUIRED_SUBJECTIVITY_VALIDATOR
from ai.evaluation.elo_contract import ArenaManifest
from ai.evaluation.elo_ratings import (
    EloLedgerBook,
    audit_evaluator_rating_eligibility,
    audit_rating_eligibility,
    build_match_participants,
)
from ai.evaluation.tournament import Outcome, TournamentMatchRecord


def test_clean_match_updates_independent_ledgers() -> None:
    manifest = _manifest()
    participants = build_match_participants(
        manifest=manifest,
        controller_profile="unified_ai_current",
        policy_version="v-test",
    )
    record = _record(outcome="heroes", status="encounter_ended")
    eligibility = audit_rating_eligibility(record)
    book = EloLedgerBook()

    updates = book.update_from_match(
        match_index=0,
        match_id="m0",
        outcome=record.outcome,
        participants=participants,
    )
    ledgers = book.ledgers()

    assert eligibility.rating_eligible
    assert "setup_side" in updates
    assert "arena_balance" in updates
    assert "policy_side" in updates
    assert "roster" in updates
    assert "policy_global" not in updates
    assert ledgers["setup_side"].eligible_match_count == 1
    setup_ratings = ledgers["setup_side"].ratings
    hero_rating = next(value for key, value in setup_ratings.items() if "side=heroes" in key)
    monster_rating = next(value for key, value in setup_ratings.items() if "side=monsters" in key)
    assert hero_rating > monster_rating
    assert ledgers["arena_balance"].ratings != ledgers["setup_side"].ratings
    assert all("policy=" not in participant_id for participant_id in ledgers["arena_balance"].ratings)
    assert all("controller=" not in participant_id for participant_id in ledgers["arena_balance"].ratings)


def test_rating_series_records_only_participants_updated_by_each_match() -> None:
    first_manifest = _manifest()
    second_manifest = first_manifest.model_copy(update={
        "arena_id": "arena-two",
        "roster_hash_by_side": {
            "heroes": "hero-roster-two",
            "monsters": "monster-roster-two",
        },
        "manifest_hash": "manifest-two",
    })
    book = EloLedgerBook()

    for match_index, manifest in enumerate((first_manifest, second_manifest)):
        book.update_from_match(
            match_index=match_index,
            match_id=f"m{match_index}",
            outcome="heroes",
            participants=build_match_participants(
                manifest=manifest,
                controller_profile="unified_ai_current",
                policy_version="v-test",
            ),
        )

    series = book.ledgers()["setup_side"].rating_series

    assert len(series) == 4
    assert [row.match_index for row in series] == [0, 0, 1, 1]
    assert len({row.participant_id for row in series}) == 4


def test_abnormal_match_is_retained_but_not_rating_eligible() -> None:
    manifest = _manifest()
    participants = build_match_participants(
        manifest=manifest,
        controller_profile="unified_ai_current",
        policy_version="v-test",
    )
    record = _record(outcome="monsters", status="command_cap_reached")
    eligibility = audit_rating_eligibility(record)
    book = EloLedgerBook()

    book.record_skip(participants)
    ledgers = book.ledgers()

    assert not eligibility.rating_eligible
    assert "command_cap_reached" in eligibility.reasons
    assert ledgers["setup_side"].ratings == {}
    assert ledgers["setup_side"].skipped_match_count == 1


def test_monster_win_and_draw_update_results_and_standings() -> None:
    manifest = _manifest()
    participants = build_match_participants(
        manifest=manifest,
        controller_profile="unified_ai_current",
        policy_version="v-test",
    )
    monster_book = EloLedgerBook()
    draw_book = EloLedgerBook()

    monster_book.update_from_match(
        match_index=0,
        match_id="monster-win",
        outcome="monsters",
        participants=participants,
    )
    draw_book.update_from_match(
        match_index=0,
        match_id="draw",
        outcome="draw",
        participants=participants,
    )

    monster_standings = monster_book.ledgers()["setup_side"].standings
    draw_standings = draw_book.ledgers()["setup_side"].standings
    monster_row = next(row for row in monster_standings if "side=monsters" in row.participant_id)
    hero_row = next(row for row in monster_standings if "side=heroes" in row.participant_id)

    assert monster_row.rating > hero_row.rating
    assert monster_row.wins == 1
    assert hero_row.losses == 1
    assert {row.rating for row in draw_standings} == {1000.0}
    assert all(row.draws == 1 for row in draw_standings)
    assert all({"low_sample", "unstable"}.issubset(row.warnings) for row in draw_standings)


def test_subjectivity_failure_is_never_eligible() -> None:
    record = _record(
        outcome="heroes",
        status="encounter_ended",
        subjectivity_status="failed",
        subjectivity_violation_count=1,
    )

    eligibility = audit_rating_eligibility(record)

    assert not eligibility.rating_eligible
    assert "subjectivity:failed" in eligibility.reasons
    assert "subjectivity_violations" in eligibility.reasons


def test_evaluator_eligibility_requires_manifest_participants_hp_and_artifact(tmp_path) -> None:
    manifest = _manifest()
    participants = build_match_participants(
        manifest=manifest,
        controller_profile="unified_ai_current",
        policy_version="v-test",
    )
    artifact = tmp_path / "run.json"
    artifact.write_text("{}", encoding="utf-8")
    record = _record(outcome="heroes", status="encounter_ended").model_copy(
        update={"run_artifact_path": str(artifact)}
    )

    eligible = audit_evaluator_rating_eligibility(
        record,
        manifest=manifest,
        participants=participants,
        artifact_paths=[str(artifact)],
        expected_policy_version="v-test",
        runtime_policy_version="v-test",
        expected_controller_profile="unified_ai_current",
        runtime_controller_profile="unified_ai_current",
        runtime_subjectivity_validator=REQUIRED_SUBJECTIVITY_VALIDATOR,
    )
    missing = audit_evaluator_rating_eligibility(
        record.model_copy(update={"faction_hp": {}}),
        manifest=None,
        participants=[],
        artifact_paths=[],
        expected_policy_version="v-test",
        runtime_policy_version="other-policy",
        expected_controller_profile="unified_ai_current",
        runtime_controller_profile="other-controller",
        runtime_subjectivity_validator=None,
    )

    assert eligible.rating_eligible is True
    assert missing.rating_eligible is False
    assert {
        "missing_participants",
        "missing_participant_ledgers",
        "missing_arena_manifest",
        "missing_final_faction_hp",
        "missing_run_artifact",
        "unlinked_run_artifact",
        "policy_version_mismatch",
        "controller_profile_mismatch",
        "subjectivity_validator_mismatch",
    }.issubset(missing.reasons)


def _manifest() -> ArenaManifest:
    return ArenaManifest(
        arena_id="arena",
        title="Arena",
        hero_role="hero",
        tags=("test",),
        expected_pressure=(),
        map_notes=(),
        notable_positions={},
        map_size=(3, 3),
        map_bounds=(0, 0, 2, 2),
        terrain_summary={},
        object_summary=[],
        entity_rosters={},
        roster_hash_by_side={"heroes": "hero-roster", "monsters": "monster-roster"},
        manifest_hash="manifest",
    )


def _record(
    *,
    outcome: Outcome,
    status: str,
    subjectivity_status: Literal["not_run", "passed", "failed"] = "passed",
    subjectivity_violation_count: int = 0,
) -> TournamentMatchRecord:
    return TournamentMatchRecord(
        match_id="m0",
        arena_id="arena",
        random_seed=1,
        hero_first=True,
        status=status,
        command_count=3,
        elapsed_ms=12.0,
        outcome=outcome,
        faction_hp={"heroes": 10, "monsters": 0},
        command_status_counts={"accepted": 3},
        subjectivity_status=subjectivity_status,
        subjectivity_violation_count=subjectivity_violation_count,
    )
