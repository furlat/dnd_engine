"""Pure reduction of typed terminal game evidence into GameSummaryV2."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import sqrt
from typing import Callable, Iterable, Optional, Sequence, TypeVar
from uuid import UUID

from dnd.actions import AttackEvent, JumpEvent, MovementEvent, SpellEvent
from dnd.analytics.models import (
    AttackStatisticsV1,
    CombatStatisticsV2,
    DamagePreventionStatisticsV2,
    DamageStatisticsV2,
    DiceStatisticsV2,
    EntitySnapshotV1,
    EntitySummaryV2,
    GameOutcomeV1,
    GameSummaryEvidenceV1,
    GameSummaryV2,
    HealingStatisticsV1,
    MetricAvailability,
    MetricProvenanceV1,
    MovementStatisticsV1,
    GameOutcomeResolution,
    OutcomeCountV2,
    ResolutionStatisticsV2,
    RollLuckStatisticsV2,
    SideSummaryV2,
    SummaryCompletenessStatus,
    SummaryCompletenessV1,
    SummaryProvenanceV1,
    UsageCountV1,
    compute_summary_digest,
)
from dnd.blocks.base_item import ItemChargeConsumptionEvent
from dnd.core.base_actions import ActionEvent
from dnd.core.base_conditions import (
    BaseCondition,
    ConditionApplicationEvent,
    ConditionRemovalEvent,
)
from dnd.core.combat_log import AttackLogData, CombatLogEntry, CombatLogEntryType
from dnd.core.dice import AttackOutcome, DiceRoll, RollType
from dnd.core.events import (
    DamageAppliedEvent,
    DamageRollResultEvent,
    D20Event,
    D20RollResultEvent,
    DeathEvent,
    EncounterEvent,
    EncounterEndEvent,
    EncounterStartEvent,
    Event,
    EventPhase,
    ForcedMovementEvent,
    HealEvent,
    HealRollResultEvent,
    RoundStartEvent,
    SavingThrowEvent,
    SkillCheckEvent,
    TakeDamageEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from dnd.core.modifiers import AdvantageStatus, ResistanceStatus


_ECONOMY_COST_TYPES = frozenset({"actions", "bonus_actions", "reactions", "movement"})
EncounterBoundaryEventT = TypeVar("EncounterBoundaryEventT", bound=EncounterEvent)


@dataclass
class _UsageCounter:
    attempted: int = 0
    completed: int = 0
    canceled: int = 0

    def record(self, phase: EventPhase) -> None:
        """Record one terminal lifecycle phase.

        Args:
            phase: Completion or cancellation phase.
        """
        self.attempted += 1
        if phase == EventPhase.COMPLETION:
            self.completed += 1
        elif phase == EventPhase.CANCEL:
            self.canceled += 1

    def merge(self, other: "_UsageCounter") -> None:
        """Add another usage counter.

        Args:
            other: Counter to add.
        """
        self.attempted += other.attempted
        self.completed += other.completed
        self.canceled += other.canceled

    def freeze(self) -> UsageCountV1:
        """Return the immutable public contract."""
        return UsageCountV1(
            attempted=self.attempted,
            completed=self.completed,
            canceled=self.canceled,
        )


@dataclass
class _AttackCounter:
    attempted: int = 0
    resolved: int = 0
    hits: int = 0
    misses: int = 0
    critical_hits: int = 0
    critical_misses: int = 0
    canceled: int = 0
    opportunity_attacks: int = 0

    def merge(self, other: "_AttackCounter") -> None:
        """Add another attack counter.

        Args:
            other: Counter to add.
        """
        for field_name in (
            "attempted",
            "resolved",
            "hits",
            "misses",
            "critical_hits",
            "critical_misses",
            "canceled",
            "opportunity_attacks",
        ):
            setattr(self, field_name, getattr(self, field_name) + getattr(other, field_name))

    def freeze(self, opportunity_attacks_available: bool) -> AttackStatisticsV1:
        """Return the immutable public contract.

        Args:
            opportunity_attacks_available: Whether structured logs are complete and valid.

        Returns:
            Frozen attack statistics.
        """
        return AttackStatisticsV1(
            attempted=self.attempted,
            resolved=self.resolved,
            hits=self.hits,
            misses=self.misses,
            critical_hits=self.critical_hits,
            critical_misses=self.critical_misses,
            canceled=self.canceled,
            opportunity_attacks=(self.opportunity_attacks if opportunity_attacks_available else None),
        )


@dataclass
class _DamageCounter:
    incoming_raw: int = 0
    applied: int = 0
    normal_hit_point_damage: int = 0
    temporary_hit_point_damage: int = 0
    incoming_packets: int = 0
    applied_packets: int = 0
    blocked_packets: int = 0
    applied_by_type: dict[str, int] = field(default_factory=dict)
    effective_normal_hit_point_damage: int = 0
    overkill_damage: int = 0
    event_prevented: int = 0
    resistance_prevented: int = 0
    immunity_prevented: int = 0
    flat_reduction_prevented: int = 0
    survival_cap_prevented: int = 0
    blocked_damage: int = 0
    vulnerability_bonus: int = 0
    event_amplification: int = 0
    incoming_by_type: dict[str, int] = field(default_factory=dict)
    after_affinity_by_type: dict[str, int] = field(default_factory=dict)
    applied_by_counterparty: dict[str, int] = field(default_factory=dict)
    applied_by_effect: dict[str, int] = field(default_factory=dict)

    def merge(self, other: "_DamageCounter") -> None:
        """Add another damage counter.

        Args:
            other: Counter to add.
        """
        self.incoming_raw += other.incoming_raw
        self.applied += other.applied
        self.normal_hit_point_damage += other.normal_hit_point_damage
        self.temporary_hit_point_damage += other.temporary_hit_point_damage
        self.incoming_packets += other.incoming_packets
        self.applied_packets += other.applied_packets
        self.blocked_packets += other.blocked_packets
        self.effective_normal_hit_point_damage += other.effective_normal_hit_point_damage
        self.overkill_damage += other.overkill_damage
        self.event_prevented += other.event_prevented
        self.resistance_prevented += other.resistance_prevented
        self.immunity_prevented += other.immunity_prevented
        self.flat_reduction_prevented += other.flat_reduction_prevented
        self.survival_cap_prevented += other.survival_cap_prevented
        self.blocked_damage += other.blocked_damage
        self.vulnerability_bonus += other.vulnerability_bonus
        self.event_amplification += other.event_amplification
        _merge_int_map(self.applied_by_type, other.applied_by_type)
        _merge_int_map(self.incoming_by_type, other.incoming_by_type)
        _merge_int_map(self.after_affinity_by_type, other.after_affinity_by_type)
        _merge_int_map(self.applied_by_counterparty, other.applied_by_counterparty)
        _merge_int_map(self.applied_by_effect, other.applied_by_effect)

    def freeze(self) -> DamageStatisticsV2:
        """Return the immutable public contract."""
        return DamageStatisticsV2(
            incoming_raw=self.incoming_raw,
            applied=self.applied,
            normal_hit_point_damage=self.normal_hit_point_damage,
            temporary_hit_point_damage=self.temporary_hit_point_damage,
            unapplied_remainder=max(0, self.incoming_raw - self.applied),
            incoming_packets=self.incoming_packets,
            applied_packets=self.applied_packets,
            blocked_packets=self.blocked_packets,
            applied_by_type=dict(sorted(self.applied_by_type.items())),
            effective_normal_hit_point_damage=self.effective_normal_hit_point_damage,
            overkill_damage=self.overkill_damage,
            prevention=DamagePreventionStatisticsV2(
                event_prevented=self.event_prevented,
                resistance_prevented=self.resistance_prevented,
                immunity_prevented=self.immunity_prevented,
                flat_reduction_prevented=self.flat_reduction_prevented,
                survival_cap_prevented=self.survival_cap_prevented,
                blocked_damage=self.blocked_damage,
                vulnerability_bonus=self.vulnerability_bonus,
                event_amplification=self.event_amplification,
            ),
            incoming_by_type=dict(sorted(self.incoming_by_type.items())),
            after_affinity_by_type=dict(sorted(self.after_affinity_by_type.items())),
            applied_by_counterparty=dict(sorted(self.applied_by_counterparty.items())),
            applied_by_effect=dict(sorted(self.applied_by_effect.items())),
        )


@dataclass
class _HealingCounter:
    requested: int = 0
    applied: int = 0
    events: int = 0
    blocked_events: int = 0

    def merge(self, other: "_HealingCounter") -> None:
        """Add another healing counter.

        Args:
            other: Counter to add.
        """
        self.requested += other.requested
        self.applied += other.applied
        self.events += other.events
        self.blocked_events += other.blocked_events

    def freeze(self) -> HealingStatisticsV1:
        """Return the immutable public contract."""
        return HealingStatisticsV1(
            requested=self.requested,
            applied=self.applied,
            events=self.events,
            blocked_events=self.blocked_events,
        )


@dataclass
class _MovementCounter:
    voluntary_events: int = 0
    voluntary_feet: int = 0
    jump_events: int = 0
    jump_feet: int = 0
    forced_events: int = 0
    forced_feet: int = 0

    def merge(self, other: "_MovementCounter") -> None:
        """Add another movement counter.

        Args:
            other: Counter to add.
        """
        self.voluntary_events += other.voluntary_events
        self.voluntary_feet += other.voluntary_feet
        self.jump_events += other.jump_events
        self.jump_feet += other.jump_feet
        self.forced_events += other.forced_events
        self.forced_feet += other.forced_feet

    def freeze(self) -> MovementStatisticsV1:
        """Return the immutable public contract."""
        return MovementStatisticsV1(
            voluntary_events=self.voluntary_events,
            voluntary_feet=self.voluntary_feet,
            jump_events=self.jump_events,
            jump_feet=self.jump_feet,
            forced_events=self.forced_events,
            forced_feet=self.forced_feet,
        )


@dataclass
class _OutcomeCounter:
    attempted: int = 0
    resolved: int = 0
    successes: int = 0
    failures: int = 0
    by_kind: dict[str, "_OutcomeCounter"] = field(default_factory=dict)

    def record(self, kind: str, result: Optional[bool]) -> None:
        """Record one typed saving throw or skill check outcome."""
        self.attempted += 1
        if result is not None:
            self.resolved += 1
            if result:
                self.successes += 1
            else:
                self.failures += 1
        nested = self.by_kind.setdefault(kind, _OutcomeCounter())
        nested.attempted += 1
        if result is not None:
            nested.resolved += 1
            if result:
                nested.successes += 1
            else:
                nested.failures += 1

    def merge(self, other: "_OutcomeCounter") -> None:
        """Add another outcome counter."""
        self.attempted += other.attempted
        self.resolved += other.resolved
        self.successes += other.successes
        self.failures += other.failures
        for kind, counter in other.by_kind.items():
            self.by_kind.setdefault(kind, _OutcomeCounter()).merge(counter)

    def freeze_count(self) -> OutcomeCountV2:
        """Return one immutable non-nested count."""
        return OutcomeCountV2(
            attempted=self.attempted,
            resolved=self.resolved,
            successes=self.successes,
            failures=self.failures,
        )

    def freeze(self) -> ResolutionStatisticsV2:
        """Return the immutable public resolution aggregate."""
        return ResolutionStatisticsV2(
            attempted=self.attempted,
            resolved=self.resolved,
            successes=self.successes,
            failures=self.failures,
            by_kind={
                kind: counter.freeze_count()
                for kind, counter in sorted(self.by_kind.items())
            },
        )


@dataclass
class _RollLuckCounter:
    roll_events: int = 0
    outcome_samples: int = 0
    random_faces_rolled: int = 0
    observed_total: int = 0
    expected_total: float = 0.0
    variance_total: float = 0.0
    natural_ones: int = 0
    natural_twenties: int = 0
    advantage_events: int = 0
    disadvantage_events: int = 0
    modified_events: int = 0

    def record_d20(self, roll: DiceRoll, *, modified: bool) -> None:
        """Record one selected d20 outcome with advantage-aware expectation."""
        die_size = roll.die_size or 20
        observed = roll.total - roll.bonus
        expected, variance = _selected_die_moments(die_size, roll.advantage_status)
        self.roll_events += 1
        self.outcome_samples += 1
        self.random_faces_rolled += roll.random_faces_rolled or (
            2 if roll.advantage_status != AdvantageStatus.NONE else 1
        )
        self.observed_total += observed
        self.expected_total += expected
        self.variance_total += variance
        self.natural_ones += int(observed == 1)
        self.natural_twenties += int(observed == 20)
        self.advantage_events += int(roll.advantage_status == AdvantageStatus.ADVANTAGE)
        self.disadvantage_events += int(roll.advantage_status == AdvantageStatus.DISADVANTAGE)
        self.modified_events += int(modified)

    def record_polyhedral(self, roll: DiceRoll, *, modified: bool) -> None:
        """Record individual damage or healing dice against uniform expectation."""
        self.roll_events += 1
        self.random_faces_rolled += roll.random_faces_rolled or 0
        self.modified_events += int(modified)
        if roll.die_size is None:
            return
        values = roll.results if isinstance(roll.results, list) else [roll.results]
        count = roll.effective_dice_count or len(values)
        if count != len(values):
            return
        self.outcome_samples += count
        self.observed_total += sum(values)
        self.expected_total += count * ((roll.die_size + 1) / 2)
        self.variance_total += count * (((roll.die_size ** 2) - 1) / 12)

    def merge(self, other: "_RollLuckCounter") -> None:
        """Add another roll-luck counter."""
        for field_name in (
            "roll_events",
            "outcome_samples",
            "random_faces_rolled",
            "observed_total",
            "expected_total",
            "variance_total",
            "natural_ones",
            "natural_twenties",
            "advantage_events",
            "disadvantage_events",
            "modified_events",
        ):
            setattr(self, field_name, getattr(self, field_name) + getattr(other, field_name))

    def freeze(self) -> RollLuckStatisticsV2:
        """Return the immutable public luck aggregate."""
        delta = self.observed_total - self.expected_total
        return RollLuckStatisticsV2(
            roll_events=self.roll_events,
            outcome_samples=self.outcome_samples,
            random_faces_rolled=self.random_faces_rolled,
            observed_total=self.observed_total,
            expected_total=round(self.expected_total, 6),
            variance_total=round(self.variance_total, 6),
            average_observed=(
                round(self.observed_total / self.outcome_samples, 6)
                if self.outcome_samples > 0
                else None
            ),
            average_expected=(
                round(self.expected_total / self.outcome_samples, 6)
                if self.outcome_samples > 0
                else None
            ),
            luck_delta=round(delta, 6),
            luck_z_score=(
                round(delta / sqrt(self.variance_total), 6)
                if self.variance_total > 0
                else None
            ),
            natural_ones=self.natural_ones,
            natural_twenties=self.natural_twenties,
            advantage_events=self.advantage_events,
            disadvantage_events=self.disadvantage_events,
            modified_events=self.modified_events,
        )


@dataclass
class _DiceCounter:
    all_d20: _RollLuckCounter = field(default_factory=_RollLuckCounter)
    attack_d20: _RollLuckCounter = field(default_factory=_RollLuckCounter)
    saving_throw_d20: _RollLuckCounter = field(default_factory=_RollLuckCounter)
    skill_check_d20: _RollLuckCounter = field(default_factory=_RollLuckCounter)
    damage: _RollLuckCounter = field(default_factory=_RollLuckCounter)
    healing: _RollLuckCounter = field(default_factory=_RollLuckCounter)

    def record_d20(self, category: RollType, roll: DiceRoll, *, modified: bool) -> None:
        """Record a d20 in the all-roll and category-specific aggregates."""
        self.all_d20.record_d20(roll, modified=modified)
        if category == RollType.ATTACK:
            self.attack_d20.record_d20(roll, modified=modified)
        elif category == RollType.SAVE:
            self.saving_throw_d20.record_d20(roll, modified=modified)
        elif category == RollType.CHECK:
            self.skill_check_d20.record_d20(roll, modified=modified)

    def merge(self, other: "_DiceCounter") -> None:
        """Add another dice aggregate."""
        self.all_d20.merge(other.all_d20)
        self.attack_d20.merge(other.attack_d20)
        self.saving_throw_d20.merge(other.saving_throw_d20)
        self.skill_check_d20.merge(other.skill_check_d20)
        self.damage.merge(other.damage)
        self.healing.merge(other.healing)

    def freeze(self) -> DiceStatisticsV2:
        """Return the immutable public dice aggregate."""
        return DiceStatisticsV2(
            all_d20=self.all_d20.freeze(),
            attack_d20=self.attack_d20.freeze(),
            saving_throw_d20=self.saving_throw_d20.freeze(),
            skill_check_d20=self.skill_check_d20.freeze(),
            damage=self.damage.freeze(),
            healing=self.healing.freeze(),
        )


@dataclass
class _MutableStatistics:
    turns_started: int = 0
    turns_ended: int = 0
    attacks: _AttackCounter = field(default_factory=_AttackCounter)
    damage_dealt: _DamageCounter = field(default_factory=_DamageCounter)
    damage_taken: _DamageCounter = field(default_factory=_DamageCounter)
    healing_done: _HealingCounter = field(default_factory=_HealingCounter)
    healing_received: _HealingCounter = field(default_factory=_HealingCounter)
    movement: _MovementCounter = field(default_factory=_MovementCounter)
    saving_throws: _OutcomeCounter = field(default_factory=_OutcomeCounter)
    skill_checks: _OutcomeCounter = field(default_factory=_OutcomeCounter)
    dice: _DiceCounter = field(default_factory=_DiceCounter)
    action_usage: dict[str, _UsageCounter] = field(default_factory=dict)
    spell_usage: dict[str, _UsageCounter] = field(default_factory=dict)
    item_action_usage: dict[str, _UsageCounter] = field(default_factory=dict)
    item_charges_spent: dict[str, int] = field(default_factory=dict)
    action_economy_spent: dict[str, int] = field(default_factory=dict)
    resources_spent: dict[str, int] = field(default_factory=dict)
    conditions_applied: dict[str, int] = field(default_factory=dict)
    conditions_removed: dict[str, int] = field(default_factory=dict)
    kills: int = 0
    deaths: int = 0

    def merge(self, other: "_MutableStatistics") -> None:
        """Add all metrics from another aggregate.

        Args:
            other: Aggregate to add.
        """
        self.turns_started += other.turns_started
        self.turns_ended += other.turns_ended
        self.attacks.merge(other.attacks)
        self.damage_dealt.merge(other.damage_dealt)
        self.damage_taken.merge(other.damage_taken)
        self.healing_done.merge(other.healing_done)
        self.healing_received.merge(other.healing_received)
        self.movement.merge(other.movement)
        self.saving_throws.merge(other.saving_throws)
        self.skill_checks.merge(other.skill_checks)
        self.dice.merge(other.dice)
        _merge_usage_map(self.action_usage, other.action_usage)
        _merge_usage_map(self.spell_usage, other.spell_usage)
        _merge_usage_map(self.item_action_usage, other.item_action_usage)
        _merge_int_map(self.item_charges_spent, other.item_charges_spent)
        _merge_int_map(self.action_economy_spent, other.action_economy_spent)
        _merge_int_map(self.resources_spent, other.resources_spent)
        _merge_int_map(self.conditions_applied, other.conditions_applied)
        _merge_int_map(self.conditions_removed, other.conditions_removed)
        self.kills += other.kills
        self.deaths += other.deaths

    def freeze(self, opportunity_attacks_available: bool) -> CombatStatisticsV2:
        """Return the immutable public contract.

        Args:
            opportunity_attacks_available: Whether structured attack logs are complete.

        Returns:
            Frozen combat statistics.
        """
        return CombatStatisticsV2(
            turns_started=self.turns_started,
            turns_ended=self.turns_ended,
            attacks=self.attacks.freeze(opportunity_attacks_available),
            damage_dealt=self.damage_dealt.freeze(),
            damage_taken=self.damage_taken.freeze(),
            healing_done=self.healing_done.freeze(),
            healing_received=self.healing_received.freeze(),
            movement=self.movement.freeze(),
            saving_throws=self.saving_throws.freeze(),
            skill_checks=self.skill_checks.freeze(),
            dice=self.dice.freeze(),
            action_usage=_freeze_usage_map(self.action_usage),
            spell_usage=_freeze_usage_map(self.spell_usage),
            item_action_usage=_freeze_usage_map(self.item_action_usage),
            item_charges_spent=dict(sorted(self.item_charges_spent.items())),
            action_economy_spent=dict(sorted(self.action_economy_spent.items())),
            resources_spent=dict(sorted(self.resources_spent.items())),
            conditions_applied=dict(sorted(self.conditions_applied.items())),
            conditions_removed=dict(sorted(self.conditions_removed.items())),
            kills=self.kills,
            deaths=self.deaths,
        )


def reduce_game_summary(
    *,
    game_id: str,
    encounter_uuid: UUID,
    initial_entities: Sequence[EntitySnapshotV1],
    final_entities: Sequence[EntitySnapshotV1],
    event_history: Sequence[Event],
    combat_logs: Sequence[CombatLogEntry],
    evidence: GameSummaryEvidenceV1,
) -> GameSummaryV2:
    """Reduce typed objective evidence into a canonical terminal summary.

    The reducer reads concrete event fields and structured combat-log data. It
    never reads compact, verbose, or detailed combat-log prose.

    Args:
        game_id: Hosted game identity supplied by the control plane.
        encounter_uuid: Encounter whose evidence is being reduced.
        initial_entities: Objective combatant state at encounter start.
        final_entities: Objective combatant state at the terminal boundary.
        event_history: Typed event phase versions through the terminal cursor.
        combat_logs: Typed top-level combat logs through the terminal cursor.
        evidence: Cursor and completeness declarations from the worker.

    Returns:
        Immutable GameSummaryV2 with a canonical SHA-256 digest.
    """
    initial_by_uuid = _index_snapshots(initial_entities, "initial")
    final_by_uuid = _index_snapshots(final_entities, "final")
    all_entity_uuids = sorted(set(initial_by_uuid) | set(final_by_uuid), key=str)
    stats_by_uuid = {entity_uuid: _MutableStatistics() for entity_uuid in all_entity_uuids}
    unattributed = _MutableStatistics()
    terminal_events, lineage_count = _terminal_events(event_history)
    effect_for_event = _build_effect_resolver(event_history)
    is_accounting_action = _build_action_accounting_filter(event_history)
    missing_damage_resolutions = sum(
        isinstance(event, TakeDamageEvent)
        and event.phase == EventPhase.COMPLETION
        and not event.canceled
        and event.resolution is None
        for event in terminal_events
    )
    missing_roll_metadata = _count_rolls_missing_metadata(terminal_events)

    def statistics_for(entity_uuid: Optional[UUID]) -> _MutableStatistics:
        if entity_uuid is None:
            return unattributed
        return stats_by_uuid.get(entity_uuid, unattributed)

    for event in terminal_events:
        _reduce_terminal_event(
            event,
            statistics_for,
            effect_for_event,
            is_accounting_action,
        )
    _reduce_roll_evidence(terminal_events, statistics_for)

    flattened_logs = tuple(_flatten_combat_logs(combat_logs))
    malformed_attack_logs = _reduce_attack_log_supplements(
        flattened_logs,
        statistics_for,
    )
    canceled_action_lineages = sum(
        isinstance(event, ActionEvent)
        and event.phase == EventPhase.CANCEL
        and is_accounting_action(event)
        for event in terminal_events
    )
    opportunity_attacks_available = evidence.combat_log_complete and malformed_attack_logs == 0

    entity_summaries = tuple(
        _build_entity_summary(
            entity_uuid,
            initial_by_uuid.get(entity_uuid),
            final_by_uuid.get(entity_uuid),
            stats_by_uuid[entity_uuid],
            opportunity_attacks_available,
        )
        for entity_uuid in all_entity_uuids
    )
    side_summaries = _build_side_summaries(
        entity_summaries,
        opportunity_attacks_available,
    )
    encounter_start = _last_event_of_type(terminal_events, EncounterStartEvent, encounter_uuid)
    encounter_end = _last_event_of_type(terminal_events, EncounterEndEvent, encounter_uuid)
    outcome = _build_outcome(side_summaries, encounter_end)
    issues = _completeness_issues(
        initial_by_uuid,
        final_by_uuid,
        evidence,
        encounter_end,
        malformed_attack_logs,
        missing_damage_resolutions,
        missing_roll_metadata,
    )
    metric_provenance = _metric_provenance(
        evidence,
        malformed_attack_logs,
        encounter_end is not None,
        canceled_action_lineages,
        missing_damage_resolutions,
        missing_roll_metadata,
    )
    rounds_started = max(
        (
            event.round_number
            for event in terminal_events
            if isinstance(event, RoundStartEvent) and event.phase == EventPhase.COMPLETION
        ),
        default=0,
    )
    started_at = _utc_timestamp(encounter_start.timestamp) if encounter_start is not None else None
    ended_at = _utc_timestamp(encounter_end.timestamp) if encounter_end is not None else None
    duration_seconds = _duration_seconds(started_at, ended_at)

    summary = GameSummaryV2(
        game_id=game_id,
        encounter_uuid=encounter_uuid,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        rounds_started=rounds_started,
        terminal_cursor=evidence.terminal_cursor,
        outcome=outcome,
        entities=entity_summaries,
        sides=side_summaries,
        unattributed_statistics=unattributed.freeze(opportunity_attacks_available),
        completeness=SummaryCompletenessV1(
            status=(SummaryCompletenessStatus.COMPLETE if not issues else SummaryCompletenessStatus.PARTIAL),
            issues=tuple(sorted(issues)),
        ),
        provenance=SummaryProvenanceV1(
            reducer_id="dnd.analytics.game_summary.v2",
            initial_snapshot_count=len(initial_entities),
            final_snapshot_count=len(final_entities),
            event_versions_seen=len(event_history),
            event_lineages_seen=lineage_count,
            terminal_lineages_reduced=len(terminal_events),
            top_level_combat_logs_seen=len(combat_logs),
            structured_combat_logs_seen=len(flattened_logs),
            metric_provenance=metric_provenance,
        ),
        canonical_sha256="0" * 64,
    )
    return summary.model_copy(update={"canonical_sha256": compute_summary_digest(summary)})


def _index_snapshots(
    snapshots: Sequence[EntitySnapshotV1],
    boundary: str,
) -> dict[UUID, EntitySnapshotV1]:
    """Index snapshots while rejecting duplicate identities.

    Args:
        snapshots: Snapshots to index.
        boundary: Boundary label used in validation errors.

    Returns:
        Snapshot mapping keyed by entity UUID.

    Raises:
        ValueError: If an entity appears more than once.
    """
    indexed: dict[UUID, EntitySnapshotV1] = {}
    for snapshot in snapshots:
        if snapshot.entity_uuid in indexed:
            raise ValueError(f"duplicate {boundary} snapshot for {snapshot.entity_uuid}")
        indexed[snapshot.entity_uuid] = snapshot
    return indexed


def _terminal_events(event_history: Sequence[Event]) -> tuple[tuple[Event, ...], int]:
    """Select one terminal version from every completed or canceled lineage.

    Args:
        event_history: Event phase versions in any order.

    Returns:
        Chronological terminal versions and the distinct lineage count.
    """
    by_lineage: dict[UUID, list[Event]] = defaultdict(list)
    for event in event_history:
        by_lineage[event.lineage_uuid].append(event)
    terminal: list[Event] = []
    phase_rank = {EventPhase.CANCEL: 0, EventPhase.COMPLETION: 1}
    for lineage_events in by_lineage.values():
        candidates = [event for event in lineage_events if event.phase in phase_rank]
        if candidates:
            terminal.append(
                max(
                    candidates,
                    key=lambda event: (
                        event.timestamp,
                        phase_rank[event.phase],
                        str(event.uuid),
                    ),
                )
            )
    terminal.sort(key=lambda event: (event.timestamp, str(event.lineage_uuid), str(event.uuid)))
    return tuple(terminal), len(by_lineage)


def _build_effect_resolver(event_history: Sequence[Event]) -> Callable[[Event], str]:
    """Build a parent-chain resolver for stable damage-source attribution."""
    events_by_uuid = {event.uuid: event for event in event_history}

    def resolve(event: Event) -> str:
        effect_id = getattr(event, "effect_id", None)
        if isinstance(effect_id, str) and effect_id:
            return f"effect:{effect_id}"
        current = event
        visited: set[UUID] = set()
        while current.parent_event is not None and current.parent_event not in visited:
            visited.add(current.parent_event)
            parent = events_by_uuid.get(current.parent_event)
            if parent is None:
                break
            if isinstance(parent, SpellEvent):
                return f"spell:{parent.spell_id or parent.name}"
            if isinstance(parent, ActionEvent):
                return f"action:{parent.name}"
            parent_effect_id = getattr(parent, "effect_id", None)
            if isinstance(parent_effect_id, str) and parent_effect_id:
                return f"effect:{parent_effect_id}"
            current = parent
        return "unattributed"

    return resolve


def _build_action_accounting_filter(
    event_history: Sequence[Event],
) -> Callable[[ActionEvent], bool]:
    """Return a predicate that excludes per-target convolution lineages.

    A multi-target action creates one child ActionEvent lineage per target so
    target effects remain independently observable. Those children inherit
    the root action's name and costs, but they do not spend those costs again.
    Nested reactions remain accounting actions because their parent is a
    different action or event.
    """
    events_by_uuid = {event.uuid: event for event in event_history}

    def is_accounting_action(event: ActionEvent) -> bool:
        if event.parent_event is None:
            return True
        parent = events_by_uuid.get(event.parent_event)
        return not (
            isinstance(parent, ActionEvent)
            and parent.name == event.name
            and parent.source_entity_uuid == event.source_entity_uuid
        )

    return is_accounting_action


def _reduce_roll_evidence(
    terminal_events: Sequence[Event],
    statistics_for: "StatisticsResolver",
) -> None:
    """Reduce portable roll evidence once per concrete roll UUID."""
    seen_roll_uuids: set[UUID] = set()

    for event in terminal_events:
        if isinstance(event, D20RollResultEvent):
            roll = event.original_roll
            statistics_for(roll.source_entity_uuid).dice.record_d20(
                roll.roll_type,
                roll,
                modified=(event.final_roll is not None or bool(event.roll_modifications)),
            )
            seen_roll_uuids.add(roll.roll_uuid)
            if event.final_roll is not None:
                seen_roll_uuids.add(event.final_roll.roll_uuid)
        elif isinstance(event, DamageRollResultEvent):
            modified = bool(event.roll_modifications)
            for packet in event.damage_packets:
                roll = packet.original_roll
                statistics_for(roll.source_entity_uuid).dice.damage.record_polyhedral(
                    roll,
                    modified=modified,
                )
                seen_roll_uuids.add(roll.roll_uuid)
            seen_roll_uuids.update(
                packet.final_roll.roll_uuid
                for packet in event.damage_packets
            )
        elif isinstance(event, HealRollResultEvent):
            roll = event.original_roll
            statistics_for(roll.source_entity_uuid).dice.healing.record_polyhedral(
                roll,
                modified=(event.final_roll.roll_uuid != roll.roll_uuid or bool(event.roll_modifications)),
            )
            seen_roll_uuids.add(roll.roll_uuid)
            seen_roll_uuids.add(event.final_roll.roll_uuid)

    for event in terminal_events:
        d20_roll: Optional[DiceRoll] = None
        d20_category: Optional[RollType] = None
        if isinstance(event, D20Event) and event.dice_roll is not None:
            d20_roll = event.dice_roll
            d20_category = event.dice_roll.roll_type
        elif isinstance(event, (AttackEvent, SpellEvent)) and event.dice_roll is not None:
            d20_roll = event.dice_roll
            d20_category = RollType.ATTACK
        if (
            d20_roll is not None
            and d20_category is not None
            and d20_roll.roll_uuid not in seen_roll_uuids
        ):
            statistics_for(d20_roll.source_entity_uuid).dice.record_d20(
                d20_category,
                d20_roll,
                modified=False,
            )
            seen_roll_uuids.add(d20_roll.roll_uuid)

        if isinstance(event, (AttackEvent, SpellEvent)) and event.damage_rolls:
            for roll in event.damage_rolls:
                if roll.roll_uuid in seen_roll_uuids:
                    continue
                statistics_for(roll.source_entity_uuid).dice.damage.record_polyhedral(
                    roll,
                    modified=False,
                )
                seen_roll_uuids.add(roll.roll_uuid)


def _selected_die_moments(
    die_size: int,
    advantage_status: AdvantageStatus,
) -> tuple[float, float]:
    """Return expectation and variance for one selected die outcome."""
    if advantage_status == AdvantageStatus.NONE:
        mean = (die_size + 1) / 2
        return mean, ((die_size ** 2) - 1) / 12
    outcomes = [
        (
            max(first, second)
            if advantage_status == AdvantageStatus.ADVANTAGE
            else min(first, second)
        )
        for first in range(1, die_size + 1)
        for second in range(1, die_size + 1)
    ]
    mean = sum(outcomes) / len(outcomes)
    variance = sum((outcome - mean) ** 2 for outcome in outcomes) / len(outcomes)
    return mean, variance


def _count_rolls_missing_metadata(terminal_events: Sequence[Event]) -> int:
    """Count damage/healing roll events lacking portable die-size metadata."""
    roll_uuids: set[UUID] = set()
    missing = 0
    for event in terminal_events:
        rolls: Sequence[DiceRoll] = ()
        if isinstance(event, DamageRollResultEvent):
            rolls = tuple(
                packet.original_roll
                for packet in event.damage_packets
            )
        elif isinstance(event, HealRollResultEvent):
            rolls = (event.original_roll,)
        elif isinstance(event, (AttackEvent, SpellEvent)) and event.damage_rolls:
            rolls = event.damage_rolls
        for roll in rolls:
            if roll.roll_uuid in roll_uuids:
                continue
            roll_uuids.add(roll.roll_uuid)
            missing += int(roll.die_size is None)
    return missing


def _reduce_terminal_event(
    event: Event,
    statistics_for: "StatisticsResolver",
    effect_for_event: Callable[[Event], str],
    is_accounting_action: Callable[[ActionEvent], bool],
) -> None:
    """Apply one terminal typed event to mutable aggregates.

    Args:
        event: Completion or cancellation event selected for its lineage.
        statistics_for: Resolver for roster and unattributed aggregates.
        effect_for_event: Resolver for nearest typed action or effect identity.
        is_accounting_action: Predicate excluding per-target convolution children.
    """
    source_stats = statistics_for(event.source_entity_uuid)
    target_stats = statistics_for(event.target_entity_uuid)

    if isinstance(event, ActionEvent) and is_accounting_action(event):
        _record_usage(source_stats.action_usage, event.name, event.phase)
        if event.source_item_uuid is not None:
            _record_usage(source_stats.item_action_usage, str(event.source_item_uuid), event.phase)
        if isinstance(event, SpellEvent):
            spell_key = event.spell_id or f"unclassified:{event.name}"
            _record_usage(source_stats.spell_usage, spell_key, event.phase)
        if event.phase == EventPhase.COMPLETION:
            _record_completed_costs(source_stats, event)

    if isinstance(event, AttackEvent):
        _record_attack(source_stats.attacks, event)
    elif (
        isinstance(event, SpellEvent)
        and event.phase == EventPhase.COMPLETION
        and event.attack_outcome is not None
    ):
        _record_resolved_attack_outcome(source_stats.attacks, event.attack_outcome)
    if isinstance(event, TakeDamageEvent):
        _record_incoming_damage(source_stats.damage_dealt, target_stats.damage_taken, event)
    if isinstance(event, DamageAppliedEvent) and event.phase == EventPhase.COMPLETION:
        _record_applied_damage(
            source_stats.damage_dealt,
            target_stats.damage_taken,
            event,
            effect_key=effect_for_event(event),
        )
    if isinstance(event, HealEvent):
        _record_healing(source_stats.healing_done, target_stats.healing_received, event)
    if isinstance(event, JumpEvent) and event.phase == EventPhase.COMPLETION:
        source_stats.movement.jump_events += 1
        source_stats.movement.jump_feet += max(0, event.jump_distance)
    elif isinstance(event, MovementEvent) and event.phase == EventPhase.COMPLETION:
        source_stats.movement.voluntary_events += 1
        source_stats.movement.voluntary_feet += max(0, (len(event.path or []) - 1) * 5)
    elif isinstance(event, ForcedMovementEvent) and event.phase == EventPhase.COMPLETION:
        target_stats.movement.forced_events += 1
        target_stats.movement.forced_feet += max(0, event.actual_distance)
    if isinstance(event, ConditionApplicationEvent) and event.phase == EventPhase.COMPLETION:
        condition_key = _condition_key(event.condition)
        _increment(target_stats.conditions_applied, condition_key)
    if isinstance(event, ConditionRemovalEvent) and event.phase == EventPhase.COMPLETION:
        condition_key = _condition_key(event.condition)
        _increment(target_stats.conditions_removed, condition_key)
    if isinstance(event, ItemChargeConsumptionEvent) and event.phase == EventPhase.COMPLETION:
        _increment(source_stats.item_charges_spent, event.item_id, event.amount)
    if isinstance(event, TurnStartEvent) and event.phase == EventPhase.COMPLETION:
        statistics_for(event.entity_uuid).turns_started += 1
    if isinstance(event, TurnEndEvent) and event.phase == EventPhase.COMPLETION:
        statistics_for(event.entity_uuid).turns_ended += 1
    if isinstance(event, SavingThrowEvent) and event.phase == EventPhase.COMPLETION:
        saving_entity_uuid = event.target_entity_uuid or event.source_entity_uuid
        statistics_for(saving_entity_uuid).saving_throws.record(
            event.ability_name,
            event.result,
        )
    if isinstance(event, SkillCheckEvent) and event.phase == EventPhase.COMPLETION:
        statistics_for(event.source_entity_uuid).skill_checks.record(
            event.skill_name,
            event.result,
        )
    if isinstance(event, DeathEvent) and event.phase == EventPhase.COMPLETION:
        statistics_for(event.entity_uuid).deaths += 1
        statistics_for(event.killer_uuid).kills += 1


def _record_attack(counter: _AttackCounter, event: AttackEvent) -> None:
    """Record one terminal attack event.

    Args:
        counter: Destination aggregate.
        event: Terminal attack event.
    """
    counter.attempted += 1
    if event.phase == EventPhase.CANCEL:
        counter.canceled += 1
        return
    if event.phase != EventPhase.COMPLETION or event.attack_outcome is None:
        return
    _record_resolved_attack_outcome(counter, event.attack_outcome, increment_attempt=False)


def _record_resolved_attack_outcome(
    counter: _AttackCounter,
    outcome: AttackOutcome,
    *,
    increment_attempt: bool = True,
) -> None:
    """Record one typed weapon or spell attack-roll outcome.

    Args:
        counter: Destination aggregate.
        outcome: Resolved attack outcome.
        increment_attempt: Whether this call represents an attempt not already counted.
    """
    if increment_attempt:
        counter.attempted += 1
    counter.resolved += 1
    if outcome in (AttackOutcome.HIT, AttackOutcome.CRIT):
        counter.hits += 1
    else:
        counter.misses += 1
    if outcome == AttackOutcome.CRIT:
        counter.critical_hits += 1
    elif outcome == AttackOutcome.CRIT_MISS:
        counter.critical_misses += 1


def _record_incoming_damage(
    dealt: _DamageCounter,
    taken: _DamageCounter,
    event: TakeDamageEvent,
) -> None:
    """Record raw incoming damage from a terminal TakeDamageEvent.

    Args:
        dealt: Source aggregate.
        taken: Target aggregate.
        event: Terminal incoming damage event.
    """
    amount = max(0, event.total_damage)
    for counter in (dealt, taken):
        counter.incoming_raw += amount
        counter.incoming_packets += 1
        if event.phase == EventPhase.CANCEL or event.canceled:
            counter.blocked_packets += 1
            counter.blocked_damage += amount
            continue
        resolution = event.resolution
        if resolution is None:
            continue
        counter.event_prevented += resolution.event_prevented_damage
        counter.event_amplification += resolution.event_amplified_damage
        counter.flat_reduction_prevented += resolution.flat_reduction_damage
        counter.survival_cap_prevented += resolution.survival_cap_prevented_damage
        counter.vulnerability_bonus += resolution.vulnerability_bonus_damage
        for component in resolution.components:
            type_key = component.damage_type.value
            _increment(counter.incoming_by_type, type_key, component.incoming_damage)
            _increment(
                counter.after_affinity_by_type,
                type_key,
                component.after_affinity_damage,
            )
            if component.resistance_status == ResistanceStatus.RESISTANCE:
                counter.resistance_prevented += component.affinity_prevented_damage
            elif component.resistance_status == ResistanceStatus.IMMUNITY:
                counter.immunity_prevented += component.affinity_prevented_damage


def _record_applied_damage(
    dealt: _DamageCounter,
    taken: _DamageCounter,
    event: DamageAppliedEvent,
    *,
    effect_key: str,
) -> None:
    """Record exact hit-point-pool damage from DamageAppliedEvent.

    Args:
        dealt: Source aggregate.
        taken: Target aggregate.
        event: Completed factual damage event.
        effect_key: Nearest typed effect, spell, or action identity.
    """
    damage_type = event.damage_type.value
    if event.resolution is not None and len(event.resolution.components) > 1:
        damage_type = "Mixed"
    for counter in (dealt, taken):
        counter.applied += event.applied_damage
        counter.normal_hit_point_damage += event.normal_hit_point_damage
        counter.temporary_hit_point_damage += event.temporary_hit_point_damage
        counter.applied_packets += 1
        _increment(counter.applied_by_type, damage_type, event.applied_damage)
        counter.effective_normal_hit_point_damage += (
            event.resolution.effective_normal_hit_point_damage
            if event.resolution is not None
            else event.normal_hit_point_damage
        )
        counter.overkill_damage += (
            event.resolution.overkill_damage
            if event.resolution is not None
            else 0
        )
        _increment(counter.applied_by_effect, effect_key, event.applied_damage)
    if event.target_entity_uuid is not None:
        _increment(
            dealt.applied_by_counterparty,
            str(event.target_entity_uuid),
            event.applied_damage,
        )
    if event.source_entity_uuid is not None:
        _increment(
            taken.applied_by_counterparty,
            str(event.source_entity_uuid),
            event.applied_damage,
        )


def _record_healing(
    done: _HealingCounter,
    received: _HealingCounter,
    event: HealEvent,
) -> None:
    """Record one terminal healing event.

    Args:
        done: Source aggregate.
        received: Target aggregate.
        event: Terminal healing event.
    """
    for counter in (done, received):
        counter.requested += max(0, event.total_healing)
        counter.applied += max(0, event.actual_healing)
        counter.events += 1
        if event.was_blocked:
            counter.blocked_events += 1


def _record_completed_costs(statistics: _MutableStatistics, event: ActionEvent) -> None:
    """Record costs proven spent by a completed action lineage.

    Args:
        statistics: Acting entity aggregate.
        event: Completed action event carrying serialized costs.
    """
    for cost in event.costs:
        if cost.cost > 0:
            destination = (
                statistics.action_economy_spent
                if cost.cost_type in _ECONOMY_COST_TYPES
                else statistics.resources_spent
            )
            _increment(destination, cost.cost_type, cost.cost)
        if cost.resource_name and cost.resource_cost > 0:
            _increment(statistics.resources_spent, cost.resource_name, cost.resource_cost)


def _condition_key(condition: BaseCondition) -> str:
    """Return the condition's canonical registered semantic identity."""
    return condition.get_semantic_key()


def _flatten_combat_logs(logs: Sequence[CombatLogEntry]) -> Iterable[CombatLogEntry]:
    """Yield top-level and nested structured combat-log entries.

    Args:
        logs: Top-level encounter combat logs.

    Yields:
        Every structured entry in depth-first order.
    """
    for log in logs:
        yield log
        yield from _flatten_combat_logs(log.sub_entries)


def _reduce_attack_log_supplements(
    logs: Sequence[CombatLogEntry],
    statistics_for: "StatisticsResolver",
) -> int:
    """Read opportunity-attack evidence unavailable on AttackEvent itself.

    Args:
        logs: Flattened typed combat logs.
        statistics_for: Resolver for roster and unattributed aggregates.

    Returns:
        Number of malformed structured attack payloads.
    """
    malformed = 0
    for log in logs:
        if log.entry_type != CombatLogEntryType.ATTACK:
            continue
        try:
            attack = AttackLogData.model_validate(log.data)
        except ValueError:
            malformed += 1
            continue
        if attack.is_opportunity_attack:
            statistics_for(_parse_uuid(attack.attacker_uuid)).attacks.opportunity_attacks += 1
    return malformed


def _parse_uuid(value: str) -> Optional[UUID]:
    """Parse a structured runtime UUID without accepting prose fallbacks.

    Args:
        value: UUID string from structured log data.

    Returns:
        UUID when valid, otherwise None.
    """
    try:
        return UUID(value)
    except ValueError:
        return None


def _build_entity_summary(
    entity_uuid: UUID,
    initial: Optional[EntitySnapshotV1],
    final: Optional[EntitySnapshotV1],
    statistics: _MutableStatistics,
    opportunity_attacks_available: bool,
) -> EntitySummaryV2:
    """Build one immutable entity summary.

    Args:
        entity_uuid: Combatant identity.
        initial: Optional initial boundary state.
        final: Optional final boundary state.
        statistics: Reduced objective aggregate.
        opportunity_attacks_available: Whether structured attack logs are complete.

    Returns:
        Frozen entity summary.
    """
    identity = final or initial
    if identity is None:
        raise ValueError(f"entity {entity_uuid} has no boundary snapshot")
    return EntitySummaryV2(
        entity_uuid=entity_uuid,
        side_id=identity.side_id,
        name=identity.name,
        initial=initial,
        final=final,
        statistics=statistics.freeze(opportunity_attacks_available),
    )


def _build_side_summaries(
    entities: Sequence[EntitySummaryV2],
    opportunity_attacks_available: bool,
) -> tuple[SideSummaryV2, ...]:
    """Aggregate immutable entity summaries by side.

    Args:
        entities: Entity summaries to aggregate.
        opportunity_attacks_available: Whether opportunity-attack metrics are complete.

    Returns:
        Side summaries sorted by side identity.
    """
    grouped: dict[str, list[EntitySummaryV2]] = defaultdict(list)
    for entity in entities:
        grouped[entity.side_id].append(entity)
    summaries: list[SideSummaryV2] = []
    for side_id in sorted(grouped):
        members = sorted(grouped[side_id], key=lambda entity: str(entity.entity_uuid))
        aggregate = _MutableStatistics()
        for member in members:
            aggregate.merge(_thaw_statistics(member.statistics))
        summaries.append(
            SideSummaryV2(
                side_id=side_id,
                entity_uuids=tuple(member.entity_uuid for member in members),
                initial_combatant_count=sum(member.initial is not None for member in members),
                final_combatant_count=sum(member.final is not None for member in members),
                surviving_combatant_count=sum(
                    member.final is not None and not member.final.is_defeated
                    for member in members
                ),
                statistics=aggregate.freeze(opportunity_attacks_available),
            )
        )
    return tuple(summaries)


def _thaw_statistics(value: CombatStatisticsV2) -> _MutableStatistics:
    """Convert a frozen aggregate into an internal additive representation.

    Args:
        value: Frozen statistics to convert.

    Returns:
        Mutable additive copy.
    """
    return _MutableStatistics(
        turns_started=value.turns_started,
        turns_ended=value.turns_ended,
        attacks=_AttackCounter(
            attempted=value.attacks.attempted,
            resolved=value.attacks.resolved,
            hits=value.attacks.hits,
            misses=value.attacks.misses,
            critical_hits=value.attacks.critical_hits,
            critical_misses=value.attacks.critical_misses,
            canceled=value.attacks.canceled,
            opportunity_attacks=value.attacks.opportunity_attacks or 0,
        ),
        damage_dealt=_thaw_damage(value.damage_dealt),
        damage_taken=_thaw_damage(value.damage_taken),
        healing_done=_thaw_healing(value.healing_done),
        healing_received=_thaw_healing(value.healing_received),
        movement=_thaw_movement(value.movement),
        saving_throws=_thaw_outcomes(value.saving_throws),
        skill_checks=_thaw_outcomes(value.skill_checks),
        dice=_thaw_dice(value.dice),
        action_usage=_thaw_usage_map(value.action_usage),
        spell_usage=_thaw_usage_map(value.spell_usage),
        item_action_usage=_thaw_usage_map(value.item_action_usage),
        item_charges_spent=dict(value.item_charges_spent),
        action_economy_spent=dict(value.action_economy_spent),
        resources_spent=dict(value.resources_spent),
        conditions_applied=dict(value.conditions_applied),
        conditions_removed=dict(value.conditions_removed),
        kills=value.kills,
        deaths=value.deaths,
    )


def _thaw_damage(value: DamageStatisticsV2) -> _DamageCounter:
    """Convert frozen damage statistics into an additive counter.

    Args:
        value: Frozen damage statistics.

    Returns:
        Mutable damage counter.
    """
    return _DamageCounter(
        incoming_raw=value.incoming_raw,
        applied=value.applied,
        normal_hit_point_damage=value.normal_hit_point_damage,
        temporary_hit_point_damage=value.temporary_hit_point_damage,
        incoming_packets=value.incoming_packets,
        applied_packets=value.applied_packets,
        blocked_packets=value.blocked_packets,
        applied_by_type=dict(value.applied_by_type),
        effective_normal_hit_point_damage=value.effective_normal_hit_point_damage,
        overkill_damage=value.overkill_damage,
        event_prevented=value.prevention.event_prevented,
        resistance_prevented=value.prevention.resistance_prevented,
        immunity_prevented=value.prevention.immunity_prevented,
        flat_reduction_prevented=value.prevention.flat_reduction_prevented,
        survival_cap_prevented=value.prevention.survival_cap_prevented,
        blocked_damage=value.prevention.blocked_damage,
        vulnerability_bonus=value.prevention.vulnerability_bonus,
        event_amplification=value.prevention.event_amplification,
        incoming_by_type=dict(value.incoming_by_type),
        after_affinity_by_type=dict(value.after_affinity_by_type),
        applied_by_counterparty=dict(value.applied_by_counterparty),
        applied_by_effect=dict(value.applied_by_effect),
    )


def _thaw_outcomes(value: ResolutionStatisticsV2) -> _OutcomeCounter:
    """Convert frozen outcome statistics into an additive counter."""
    counter = _OutcomeCounter(
        attempted=value.attempted,
        resolved=value.resolved,
        successes=value.successes,
        failures=value.failures,
    )
    counter.by_kind = {
        kind: _OutcomeCounter(
            attempted=outcome.attempted,
            resolved=outcome.resolved,
            successes=outcome.successes,
            failures=outcome.failures,
        )
        for kind, outcome in value.by_kind.items()
    }
    return counter


def _thaw_roll(value: RollLuckStatisticsV2) -> _RollLuckCounter:
    """Convert frozen luck statistics into an additive counter."""
    return _RollLuckCounter(
        roll_events=value.roll_events,
        outcome_samples=value.outcome_samples,
        random_faces_rolled=value.random_faces_rolled,
        observed_total=value.observed_total,
        expected_total=value.expected_total,
        variance_total=value.variance_total,
        natural_ones=value.natural_ones,
        natural_twenties=value.natural_twenties,
        advantage_events=value.advantage_events,
        disadvantage_events=value.disadvantage_events,
        modified_events=value.modified_events,
    )


def _thaw_dice(value: DiceStatisticsV2) -> _DiceCounter:
    """Convert frozen dice statistics into an additive counter."""
    return _DiceCounter(
        all_d20=_thaw_roll(value.all_d20),
        attack_d20=_thaw_roll(value.attack_d20),
        saving_throw_d20=_thaw_roll(value.saving_throw_d20),
        skill_check_d20=_thaw_roll(value.skill_check_d20),
        damage=_thaw_roll(value.damage),
        healing=_thaw_roll(value.healing),
    )


def _thaw_healing(value: HealingStatisticsV1) -> _HealingCounter:
    """Convert frozen healing statistics into an additive counter.

    Args:
        value: Frozen healing statistics.

    Returns:
        Mutable healing counter.
    """
    return _HealingCounter(
        requested=value.requested,
        applied=value.applied,
        events=value.events,
        blocked_events=value.blocked_events,
    )


def _thaw_movement(value: MovementStatisticsV1) -> _MovementCounter:
    """Convert frozen movement statistics into an additive counter.

    Args:
        value: Frozen movement statistics.

    Returns:
        Mutable movement counter.
    """
    return _MovementCounter(
        voluntary_events=value.voluntary_events,
        voluntary_feet=value.voluntary_feet,
        jump_events=value.jump_events,
        jump_feet=value.jump_feet,
        forced_events=value.forced_events,
        forced_feet=value.forced_feet,
    )


def _build_outcome(
    sides: Sequence[SideSummaryV2],
    encounter_end: Optional[EncounterEndEvent],
) -> GameOutcomeV1:
    """Derive terminal outcome from final side survival.

    Args:
        sides: Objective side summaries.
        encounter_end: Retained terminal encounter event, if any.

    Returns:
        Typed outcome with explicit indeterminate states.
    """
    surviving = tuple(sorted(side.side_id for side in sides if side.surviving_combatant_count > 0))
    all_sides = tuple(sorted(side.side_id for side in sides))
    if encounter_end is None:
        resolution = GameOutcomeResolution.INDETERMINATE
        winners: tuple[str, ...] = ()
        losers: tuple[str, ...] = ()
    elif len(all_sides) >= 2 and len(surviving) == 1:
        resolution = GameOutcomeResolution.VICTORY
        winners = surviving
        losers = tuple(side_id for side_id in all_sides if side_id not in surviving)
    elif len(all_sides) >= 2 and not surviving:
        resolution = GameOutcomeResolution.DRAW
        winners = ()
        losers = all_sides
    else:
        resolution = GameOutcomeResolution.INDETERMINATE
        winners = ()
        losers = ()
    return GameOutcomeV1(
        terminal_event_observed=encounter_end is not None,
        resolution=resolution,
        reason=encounter_end.reason if encounter_end is not None else None,
        winning_side_ids=winners,
        losing_side_ids=losers,
        surviving_side_ids=surviving,
    )


def _last_event_of_type(
    events: Sequence[Event],
    event_class: type[EncounterBoundaryEventT],
    encounter_uuid: UUID,
) -> Optional[EncounterBoundaryEventT]:
    """Return the latest matching encounter boundary event.

    Args:
        events: Terminal event versions.
        event_class: Encounter event subtype to select.
        encounter_uuid: Encounter identity to match.

    Returns:
        Latest matching event, or None.
    """
    matching = [
        event
        for event in events
        if isinstance(event, event_class)
        and event.encounter_uuid == encounter_uuid
        and event.phase == EventPhase.COMPLETION
    ]
    return max(matching, key=lambda event: (event.timestamp, str(event.uuid)), default=None)


def _completeness_issues(
    initial: dict[UUID, EntitySnapshotV1],
    final: dict[UUID, EntitySnapshotV1],
    evidence: GameSummaryEvidenceV1,
    encounter_end: Optional[EncounterEndEvent],
    malformed_attack_logs: int,
    missing_damage_resolutions: int,
    missing_roll_metadata: int,
) -> set[str]:
    """Return machine-readable evidence completeness issues.

    Args:
        initial: Initial snapshots by identity.
        final: Final snapshots by identity.
        evidence: Caller-declared completeness.
        encounter_end: Retained terminal event, if any.
        malformed_attack_logs: Structured attack logs that failed validation.
        missing_damage_resolutions: Completed packets lacking typed resolution.
        missing_roll_metadata: Polyhedral rolls lacking portable die metadata.

    Returns:
        Set of issue codes.
    """
    issues: set[str] = set()
    if not evidence.event_history_complete:
        issues.add("event_history_incomplete")
    if not evidence.combat_log_complete:
        issues.add("combat_log_incomplete")
    if not evidence.initial_snapshot_complete:
        issues.add("initial_snapshot_declared_incomplete")
    if not evidence.final_snapshot_complete:
        issues.add("final_snapshot_declared_incomplete")
    if set(initial) != set(final):
        issues.add("snapshot_rosters_differ")
    if any(
        entity_uuid in final and snapshot.side_id != final[entity_uuid].side_id
        for entity_uuid, snapshot in initial.items()
    ):
        issues.add("entity_side_changed")
    if encounter_end is None:
        issues.add("encounter_end_missing")
    if malformed_attack_logs:
        issues.add("structured_attack_log_invalid")
    if missing_damage_resolutions:
        issues.add("damage_resolution_missing")
    if missing_roll_metadata:
        issues.add("roll_metadata_missing")
    return issues


def _metric_provenance(
    evidence: GameSummaryEvidenceV1,
    malformed_attack_logs: int,
    terminal_event_observed: bool,
    canceled_action_lineages: int,
    missing_damage_resolutions: int,
    missing_roll_metadata: int,
) -> tuple[MetricProvenanceV1, ...]:
    """Build explicit evidence semantics for every metric family.

    Args:
        evidence: Caller-declared completeness.
        malformed_attack_logs: Number of invalid attack payloads.
        terminal_event_observed: Whether EncounterEndEvent was retained.
        canceled_action_lineages: Canceled action lineages whose cost commitment is ambiguous.
        missing_damage_resolutions: Completed packets lacking typed resolution.
        missing_roll_metadata: Polyhedral rolls lacking portable die metadata.

    Returns:
        Metric provenance sorted by metric identity.
    """
    event_availability = (
        MetricAvailability.AVAILABLE
        if evidence.event_history_complete
        else MetricAvailability.PARTIAL
    )
    opportunity_availability = (
        MetricAvailability.AVAILABLE
        if evidence.combat_log_complete and malformed_attack_logs == 0
        else MetricAvailability.UNAVAILABLE
    )
    outcome_availability = (
        MetricAvailability.AVAILABLE
        if terminal_event_observed and evidence.final_snapshot_complete
        else MetricAvailability.PARTIAL
    )
    action_cost_availability = (
        MetricAvailability.PARTIAL
        if canceled_action_lineages or not evidence.event_history_complete
        else MetricAvailability.AVAILABLE
    )
    damage_detail_availability = (
        MetricAvailability.AVAILABLE
        if evidence.event_history_complete and missing_damage_resolutions == 0
        else MetricAvailability.PARTIAL
    )
    dice_availability = (
        MetricAvailability.AVAILABLE
        if evidence.event_history_complete and missing_roll_metadata == 0
        else MetricAvailability.PARTIAL
    )
    metrics = (
        MetricProvenanceV1(
            metric="outcome",
            availability=outcome_availability,
            sources=("final_entity_snapshots", "EncounterEndEvent"),
            note="Victory requires one surviving side and a retained terminal encounter event.",
        ),
        MetricProvenanceV1(
            metric="attacks",
            availability=event_availability,
            sources=("AttackEvent", "SpellEvent"),
            note="Weapon attacks use terminal AttackEvent lineages; spell attack rolls use typed SpellEvent outcomes.",
        ),
        MetricProvenanceV1(
            metric="opportunity_attacks",
            availability=opportunity_availability,
            sources=("AttackLogData",),
            note="The current AttackEvent lacks an explicit opportunity-attack field; structured logs supply it.",
        ),
        MetricProvenanceV1(
            metric="damage",
            availability=event_availability,
            sources=("TakeDamageEvent", "DamageAppliedEvent"),
            note="Raw incoming, applied, normal-HP, and temporary-HP damage are independently retained.",
        ),
        MetricProvenanceV1(
            metric="damage_prevention_decomposition",
            availability=damage_detail_availability,
            sources=("TakeDamageEvent.resolution", "DamageAppliedEvent.resolution"),
            note=(
                "Typed damage resolution separates event prevention, resistance, immunity, flat reduction, "
                "survival caps, vulnerability amplification, temporary HP, and overkill."
            ),
        ),
        MetricProvenanceV1(
            metric="overkill_damage",
            availability=damage_detail_availability,
            sources=("TakeDamageEvent.resolution",),
            note="Overkill is normal-HP damage beyond normal hit points available before the packet.",
        ),
        MetricProvenanceV1(
            metric="damage_attribution",
            availability=event_availability,
            sources=("DamageAppliedEvent", "Event.parent_event"),
            note="Counterparties use entity UUIDs; effects use explicit effect_id or nearest typed parent action.",
        ),
        MetricProvenanceV1(
            metric="dice_luck",
            availability=dice_availability,
            sources=("D20RollResultEvent", "DamageRollResultEvent", "HealRollResultEvent"),
            note=(
                "Luck compares original natural outcomes with mechanic-conditioned expectation; advantage and "
                "disadvantage use their selected-outcome distributions and explicit rerolls are not called luck."
            ),
        ),
        MetricProvenanceV1(
            metric="healing",
            availability=event_availability,
            sources=("HealEvent",),
            note="Requested, applied, and explicitly blocked healing are retained.",
        ),
        MetricProvenanceV1(
            metric="movement",
            availability=event_availability,
            sources=("MovementEvent", "JumpEvent", "ForcedMovementEvent"),
            note="Concrete event types distinguish voluntary paths, jumps, and forced displacement.",
        ),
        MetricProvenanceV1(
            metric="conditions",
            availability=event_availability,
            sources=("ConditionApplicationEvent", "ConditionRemovalEvent"),
            note="Condition semantic_key is preferred, with typed name or class identity as fallback.",
        ),
        MetricProvenanceV1(
            metric="actions_spells_items_resources",
            availability=action_cost_availability,
            sources=("ActionEvent", "SpellEvent", "ItemChargeConsumptionEvent"),
            note=(
                "Completed action costs prove ordinary economy, spell-slot, and named-resource spending; "
                "canceled lineages do not currently prove whether costs were committed."
            ),
        ),
    )
    return tuple(sorted(metrics, key=lambda metric: metric.metric))


def _duration_seconds(started_at: Optional[datetime], ended_at: Optional[datetime]) -> Optional[float]:
    """Compute non-negative event-time duration.

    Args:
        started_at: Retained encounter start time.
        ended_at: Retained encounter end time.

    Returns:
        Elapsed seconds, or None when either boundary is absent.
    """
    if started_at is None or ended_at is None:
        return None
    return max(0.0, (ended_at - started_at).total_seconds())


def _utc_timestamp(value: datetime) -> datetime:
    """Normalize legacy naive engine timestamps at the analytics boundary."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _record_usage(
    destination: dict[str, _UsageCounter],
    key: str,
    phase: EventPhase,
) -> None:
    """Record one lifecycle result in a usage map.

    Args:
        destination: Usage map to update.
        key: Typed action, spell, or item identity.
        phase: Terminal lifecycle phase.
    """
    counter = destination.setdefault(key, _UsageCounter())
    counter.record(phase)


def _freeze_usage_map(source: dict[str, _UsageCounter]) -> dict[str, UsageCountV1]:
    """Freeze and sort a usage map.

    Args:
        source: Mutable usage counters.

    Returns:
        Deterministically ordered immutable values.
    """
    return {key: source[key].freeze() for key in sorted(source)}


def _thaw_usage_map(source: dict[str, UsageCountV1]) -> dict[str, _UsageCounter]:
    """Convert public usage contracts into mutable counters.

    Args:
        source: Frozen usage values.

    Returns:
        Mutable counter mapping.
    """
    return {
        key: _UsageCounter(
            attempted=value.attempted,
            completed=value.completed,
            canceled=value.canceled,
        )
        for key, value in source.items()
    }


def _merge_usage_map(
    destination: dict[str, _UsageCounter],
    source: dict[str, _UsageCounter],
) -> None:
    """Add all usage counters into a destination map.

    Args:
        destination: Usage map to update.
        source: Usage map to add.
    """
    for key, value in source.items():
        destination.setdefault(key, _UsageCounter()).merge(value)


def _increment(destination: dict[str, int], key: str, amount: int = 1) -> None:
    """Increment one integer-map entry.

    Args:
        destination: Mapping to update.
        key: Entry identity.
        amount: Non-negative amount to add.
    """
    destination[key] = destination.get(key, 0) + amount


def _merge_int_map(destination: dict[str, int], source: dict[str, int]) -> None:
    """Add all integer-map entries.

    Args:
        destination: Mapping to update.
        source: Mapping to add.
    """
    for key, value in source.items():
        _increment(destination, key, value)


StatisticsResolver = Callable[[Optional[UUID]], _MutableStatistics]
