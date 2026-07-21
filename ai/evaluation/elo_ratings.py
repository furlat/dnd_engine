"""Rating ledgers and eligibility rules for Elo matrix evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from ai.evaluation.constants import REQUIRED_SUBJECTIVITY_VALIDATOR
from ai.evaluation.elo_contract import (
    ArenaManifest,
    EloEligibility,
    EloLedgerName,
    EloParticipant,
    EloRatingLedger,
    EloRatingSnapshot,
    EloRatingUpdate,
    EloStanding,
)
from ai.evaluation.tournament import EloConfig, Outcome, TournamentMatchRecord, update_elo_pair


LEDGER_NAMES: tuple[EloLedgerName, ...] = (
    "setup_side",
    "arena_balance",
    "policy_side",
    "policy_global",
    "roster",
)


@dataclass
class _LedgerState:
    ratings: dict[str, float] = field(default_factory=dict)
    participants: dict[str, EloParticipant] = field(default_factory=dict)
    games: dict[str, int] = field(default_factory=dict)
    wins: dict[str, int] = field(default_factory=dict)
    losses: dict[str, int] = field(default_factory=dict)
    draws: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)
    latest_delta: dict[str, float] = field(default_factory=dict)
    series: list[EloRatingSnapshot] = field(default_factory=list)
    eligible_match_count: int = 0
    skipped_match_count: int = 0


class EloLedgerBook:
    """Mutable collection of independent Elo rating ledgers."""

    def __init__(self, *, elo_config: Optional[EloConfig] = None) -> None:
        """Create an empty ledger book.

        Args:
            elo_config: Elo configuration for every ledger.
        """
        self.elo_config = elo_config or EloConfig()
        self._ledgers: dict[EloLedgerName, _LedgerState] = {
            ledger_name: _LedgerState()
            for ledger_name in LEDGER_NAMES
        }

    def record_skip(self, participants: Iterable[EloParticipant]) -> None:
        """Record that a retained match touched participants but skipped rating.

        Args:
            participants: Participants generated for the skipped match.
        """
        seen_ledgers: set[EloLedgerName] = set()
        for participant in participants:
            state = self._ledgers[participant.ledger]
            state.participants.setdefault(participant.participant_id, participant)
            state.skipped[participant.participant_id] = state.skipped.get(participant.participant_id, 0) + 1
            seen_ledgers.add(participant.ledger)
        for ledger_name in seen_ledgers:
            self._ledgers[ledger_name].skipped_match_count += 1

    def update_from_match(
        self,
        *,
        match_index: int,
        match_id: str,
        outcome: Outcome,
        participants: Iterable[EloParticipant],
    ) -> dict[EloLedgerName, EloRatingUpdate]:
        """Update all ledgers touched by one eligible match.

        Args:
            match_index: Schedule row index.
            match_id: Stable match id.
            outcome: Heroes, monsters, or draw.
            participants: Rated participants for the match.

        Returns:
            Rating updates keyed by ledger.
        """
        by_ledger: dict[EloLedgerName, dict[str, EloParticipant]] = {}
        for participant in participants:
            by_ledger.setdefault(participant.ledger, {})[participant.side] = participant
        updates: dict[EloLedgerName, EloRatingUpdate] = {}
        for ledger_name, side_participants in by_ledger.items():
            hero = side_participants.get("heroes")
            monster = side_participants.get("monsters")
            if hero is None or monster is None:
                continue
            if hero.participant_id == monster.participant_id:
                continue
            updates[ledger_name] = self._update_pair(
                ledger_name=ledger_name,
                match_index=match_index,
                match_id=match_id,
                outcome=outcome,
                hero=hero,
                monster=monster,
            )
        return updates

    def ledgers(self) -> dict[EloLedgerName, EloRatingLedger]:
        """Return immutable ledger summaries."""
        return {
            ledger_name: self._ledger_summary(ledger_name, state)
            for ledger_name, state in self._ledgers.items()
        }

    def _update_pair(
        self,
        *,
        ledger_name: EloLedgerName,
        match_index: int,
        match_id: str,
        outcome: Outcome,
        hero: EloParticipant,
        monster: EloParticipant,
    ) -> EloRatingUpdate:
        state = self._ledgers[ledger_name]
        state.participants.setdefault(hero.participant_id, hero)
        state.participants.setdefault(monster.participant_id, monster)
        before = {
            hero.participant_id: state.ratings.get(hero.participant_id, self.elo_config.initial_rating),
            monster.participant_id: state.ratings.get(monster.participant_id, self.elo_config.initial_rating),
        }
        hero_score, monster_score = _scores_for_outcome(outcome)
        hero_after, monster_after = update_elo_pair(
            before[hero.participant_id],
            before[monster.participant_id],
            hero_score,
            monster_score,
            k_factor=self.elo_config.k_factor,
        )
        after = {
            hero.participant_id: round(hero_after, 3),
            monster.participant_id: round(monster_after, 3),
        }
        state.ratings.update(after)
        delta = {
            participant_id: round(after[participant_id] - before[participant_id], 3)
            for participant_id in before
        }
        for participant_id in (hero.participant_id, monster.participant_id):
            state.games[participant_id] = state.games.get(participant_id, 0) + 1
            state.latest_delta[participant_id] = delta[participant_id]
        _record_result_counts(state, outcome, hero.participant_id, monster.participant_id)
        state.eligible_match_count += 1
        for participant_id in sorted((hero.participant_id, monster.participant_id)):
            state.series.append(
                EloRatingSnapshot(
                    match_index=match_index,
                    match_id=match_id,
                    ledger=ledger_name,
                    participant_id=participant_id,
                    rating=round(state.ratings[participant_id], 3),
                )
            )
        return EloRatingUpdate(
            ledger=ledger_name,
            participant_a=hero.participant_id,
            participant_b=monster.participant_id,
            rating_before={key: round(value, 3) for key, value in before.items()},
            rating_after=after,
            rating_delta=delta,
        )

    def _ledger_summary(
        self,
        ledger_name: EloLedgerName,
        state: _LedgerState,
    ) -> EloRatingLedger:
        standings = [
            _standing_row(index + 1, participant_id, state)
            for index, participant_id in enumerate(
                sorted(state.ratings, key=lambda key: (-state.ratings[key], key))
            )
        ]
        return EloRatingLedger(
            ledger_name=ledger_name,
            elo_config=self.elo_config,
            ratings={participant_id: round(rating, 3) for participant_id, rating in sorted(state.ratings.items())},
            standings=standings,
            rating_series=list(state.series),
            match_count_by_participant=dict(sorted(state.games.items())),
            eligible_match_count=state.eligible_match_count,
            skipped_match_count=state.skipped_match_count,
        )


def build_match_participants(
    *,
    manifest: ArenaManifest,
    controller_profile: str,
    policy_version: Optional[str],
) -> list[EloParticipant]:
    """Build rated participant identities from a constructed arena manifest.

    Args:
        manifest: Constructed arena manifest.
        controller_profile: Controller profile under evaluation.
        policy_version: Optional policy version.

    Returns:
        Participants for every supported ledger.
    """
    participants: list[EloParticipant] = []
    for side in ("heroes", "monsters"):
        roster_hash = manifest.roster_hash_by_side.get(side)
        if roster_hash is None:
            continue
        participants.extend([
            _participant(
                ledger="setup_side",
                side=side,
                controller_profile=controller_profile,
                policy_version=policy_version,
                arena_id=manifest.arena_id,
                roster_hash=roster_hash,
                tags=manifest.tags,
                display=f"{manifest.arena_id} {side} setup",
            ),
            _participant(
                ledger="arena_balance",
                side=side,
                controller_profile=controller_profile,
                policy_version=policy_version,
                arena_id=manifest.arena_id,
                roster_hash=None,
                tags=manifest.tags,
                display=f"{manifest.arena_id} {side}",
                include_policy_identity=False,
                include_controller_identity=False,
            ),
            _participant(
                ledger="policy_side",
                side=side,
                controller_profile=controller_profile,
                policy_version=policy_version,
                arena_id=None,
                roster_hash=None,
                tags=(side,),
                display=f"{controller_profile} {side}",
            ),
            _participant(
                ledger="policy_global",
                side=side,
                controller_profile=controller_profile,
                policy_version=policy_version,
                arena_id=None,
                roster_hash=None,
                tags=("global",),
                display=f"{controller_profile}",
                collapse_side=True,
            ),
            _participant(
                ledger="roster",
                side=side,
                controller_profile=controller_profile,
                policy_version=policy_version,
                arena_id=None,
                roster_hash=roster_hash,
                tags=manifest.tags,
                display=f"{side} roster {roster_hash}",
            ),
        ])
    return participants


def audit_rating_eligibility(record: TournamentMatchRecord) -> EloEligibility:
    """Return official-rating eligibility for one retained match.

    Args:
        record: Tournament-compatible match record.

    Returns:
        Eligibility audit.
    """
    reasons: list[str] = []
    if record.status != "encounter_ended":
        reasons.append(f"runner_status:{record.status}")
    if record.subjectivity_status != "passed":
        reasons.append(f"subjectivity:{record.subjectivity_status}")
    if record.subjectivity_violation_count:
        reasons.append("subjectivity_violations")
    if record.outcome == "unknown":
        reasons.append("unknown_outcome")
    if record.status == "command_cap_reached":
        reasons.append("command_cap_reached")
    for status_name, count in record.command_status_counts.items():
        if status_name not in {"accepted"} and count > 0:
            reasons.append(f"command_status:{status_name}")
    rating_eligible = not reasons
    return EloEligibility(
        status="eligible" if rating_eligible else "skipped",
        rating_eligible=rating_eligible,
        reasons=sorted(set(reasons)),
        subjectivity_status=record.subjectivity_status,
        runner_status=record.status,
        command_status_counts=dict(record.command_status_counts),
        encounter_finished=record.status == "encounter_ended",
        command_cap_reached=record.status == "command_cap_reached",
        crashed=record.status == "crashed",
        timed_out=record.status == "timeout",
        has_unknown_outcome=record.outcome == "unknown",
    )


def audit_evaluator_rating_eligibility(
    record: TournamentMatchRecord,
    *,
    manifest: Optional[ArenaManifest],
    participants: Iterable[EloParticipant],
    artifact_paths: Iterable[str],
    expected_policy_version: Optional[str],
    runtime_policy_version: str,
    expected_controller_profile: str,
    runtime_controller_profile: str,
    runtime_subjectivity_validator: Optional[str],
) -> EloEligibility:
    """Audit the complete evaluator row, including durable evidence identity.

    Args:
        record: Tournament-compatible gameplay result.
        manifest: Objective pre-combat measurement manifest.
        participants: Rated identities derived from the manifest.
        artifact_paths: Raw run artifacts retained for the row.
        expected_policy_version: Policy version declared by the schedule.
        runtime_policy_version: Policy version embedded in the run artifact.
        expected_controller_profile: Controller profile declared by the schedule.
        runtime_controller_profile: Controller profile embedded in the artifact.
        runtime_subjectivity_validator: Independent perception witness embedded
            in the artifact.

    Returns:
        Eligibility that includes both gameplay and evaluator-evidence gates.
    """
    base = audit_rating_eligibility(record)
    reasons = set(base.reasons)
    participant_rows = list(participants)
    participant_sides = {participant.side for participant in participant_rows}
    if not {"heroes", "monsters"}.issubset(participant_sides):
        reasons.add("missing_participants")
    participant_ledgers = {participant.ledger for participant in participant_rows}
    if not set(LEDGER_NAMES).issubset(participant_ledgers):
        reasons.add("missing_participant_ledgers")
    if manifest is None:
        reasons.add("missing_arena_manifest")
    elif not {"heroes", "monsters"}.issubset(manifest.roster_hash_by_side):
        reasons.add("missing_roster_identity")
    if not {"heroes", "monsters"}.issubset(record.faction_hp):
        reasons.add("missing_final_faction_hp")
    retained_paths = list(artifact_paths)
    if not retained_paths:
        reasons.add("missing_run_artifact")
    elif any(not Path(path).is_file() for path in retained_paths):
        reasons.add("invalid_run_artifact_path")
    if record.run_artifact_path is None or record.run_artifact_path not in retained_paths:
        reasons.add("unlinked_run_artifact")
    if expected_policy_version != runtime_policy_version:
        reasons.add("policy_version_mismatch")
    if expected_controller_profile != runtime_controller_profile:
        reasons.add("controller_profile_mismatch")
    if runtime_subjectivity_validator != REQUIRED_SUBJECTIVITY_VALIDATOR:
        reasons.add("subjectivity_validator_mismatch")
    rating_eligible = not reasons
    return base.model_copy(update={
        "status": "eligible" if rating_eligible else "skipped",
        "rating_eligible": rating_eligible,
        "reasons": sorted(reasons),
    })


def _participant(
    *,
    ledger: EloLedgerName,
    side: str,
    controller_profile: str,
    policy_version: Optional[str],
    arena_id: Optional[str],
    roster_hash: Optional[str],
    tags: tuple[str, ...],
    display: str,
    collapse_side: bool = False,
    include_policy_identity: bool = True,
    include_controller_identity: bool = True,
) -> EloParticipant:
    version = policy_version or "unversioned"
    identity_side = "global" if collapse_side else side
    parts = [ledger]
    if include_policy_identity:
        parts.append(f"policy={version}")
    if include_controller_identity:
        parts.append(f"controller={controller_profile}")
    parts.append(f"side={identity_side}")
    if arena_id is not None:
        parts.append(f"arena={arena_id}")
    if roster_hash is not None:
        parts.append(f"roster={roster_hash}")
    participant_id = "|".join(parts)
    return EloParticipant(
        participant_id=participant_id,
        ledger=ledger,
        side=side,
        policy_version=policy_version,
        controller_profile=controller_profile,
        arena_id=arena_id,
        roster_hash=roster_hash,
        faction=side,
        tags=tags,
        display_name=display,
    )


def _standing_row(rank: int, participant_id: str, state: _LedgerState) -> EloStanding:
    participant = state.participants.get(participant_id)
    games = state.games.get(participant_id, 0)
    warnings: list[str] = []
    if games < 10:
        warnings.append("low_sample")
    if games < 30:
        warnings.append("unstable")
    return EloStanding(
        rank=rank,
        participant_id=participant_id,
        display_name=participant.display_name if participant is not None else participant_id,
        rating=round(state.ratings[participant_id], 3),
        games=games,
        wins=state.wins.get(participant_id, 0),
        losses=state.losses.get(participant_id, 0),
        draws=state.draws.get(participant_id, 0),
        skipped=state.skipped.get(participant_id, 0),
        latest_delta=round(state.latest_delta.get(participant_id, 0.0), 3),
        warnings=warnings,
        tags=participant.tags if participant is not None else (),
    )


def _record_result_counts(
    state: _LedgerState,
    outcome: Outcome,
    hero_id: str,
    monster_id: str,
) -> None:
    if outcome == "heroes":
        state.wins[hero_id] = state.wins.get(hero_id, 0) + 1
        state.losses[monster_id] = state.losses.get(monster_id, 0) + 1
    elif outcome == "monsters":
        state.wins[monster_id] = state.wins.get(monster_id, 0) + 1
        state.losses[hero_id] = state.losses.get(hero_id, 0) + 1
    else:
        state.draws[hero_id] = state.draws.get(hero_id, 0) + 1
        state.draws[monster_id] = state.draws.get(monster_id, 0) + 1


def _scores_for_outcome(outcome: Outcome) -> tuple[float, float]:
    if outcome == "heroes":
        return 1.0, 0.0
    if outcome == "monsters":
        return 0.0, 1.0
    return 0.5, 0.5
