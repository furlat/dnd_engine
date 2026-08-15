"""Versioned contracts for objective terminal game evidence."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
from typing import Annotated, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.types.life import LifeState


class FrozenSummaryModel(BaseModel):
    """Immutable base contract for persisted summary values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class MetricAvailability(str, Enum):
    """Degree to which retained engine evidence supports a metric."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class GameOutcomeResolution(str, Enum):
    """Objective terminal resolution derivable from retained state."""

    VICTORY = "victory"
    DRAW = "draw"
    INDETERMINATE = "indeterminate"


class SummaryCompletenessStatus(str, Enum):
    """Completeness of supplied evidence under the v1 contract."""

    COMPLETE = "complete"
    PARTIAL = "partial"


class EntitySnapshotV1(FrozenSummaryModel):
    """Typed objective state retained for one combatant at one boundary."""

    schema_version: Literal[1] = Field(default=1, description="Entity snapshot schema version.")
    entity_uuid: UUID = Field(description="Stable runtime identity of the combatant.")
    name: str = Field(description="Display name captured at the snapshot boundary.")
    side_id: str = Field(description="Stable side or faction identity used for outcome aggregation.")
    normal_hit_points: int = Field(description="Normal hit points at the snapshot boundary.")
    maximum_hit_points: int = Field(ge=0, description="Maximum normal hit points at the snapshot boundary.")
    temporary_hit_points: int = Field(default=0, ge=0, description="Temporary hit points at the snapshot boundary.")
    life_state: Optional[LifeState] = Field(
        default=None,
        description=(
            "Authoritative entity lifecycle state. None is reserved for legacy v1 "
            "snapshots written before lifecycle state was retained."
        ),
    )
    is_defeated: bool = Field(description="Whether the engine considers the combatant defeated.")
    position: Optional[tuple[int, int]] = Field(default=None, description="Objective grid position when retained.")
    condition_semantic_keys: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Sorted semantic identities of active conditions.",
    )
    resources: dict[str, int] = Field(
        default_factory=dict,
        description="Named resource balances retained at the snapshot boundary.",
    )

    @model_validator(mode="after")
    def validate_lifecycle_projection(self) -> EntitySnapshotV1:
        """Keep the legacy defeated projection consistent with LifeState."""
        if (
            self.life_state is not None
            and self.is_defeated != (self.life_state is LifeState.DEAD)
        ):
            raise ValueError("is_defeated must equal whether life_state is dead")
        return self


class TerminalCursorV1(FrozenSummaryModel):
    """Exclusive evidence cursors at the terminal game boundary."""

    event_cursor: int = Field(ge=0, description="Exclusive engine event-version cursor.")
    combat_log_cursor: int = Field(ge=0, description="Exclusive top-level combat-log cursor.")


class GameSummaryEvidenceV1(FrozenSummaryModel):
    """Caller-declared completeness and cursor metadata for reduction."""

    schema_version: Literal[1] = Field(default=1, description="Summary evidence envelope schema version.")
    terminal_cursor: TerminalCursorV1 = Field(description="Terminal cursors supplied by the authoritative worker.")
    event_history_complete: bool = Field(
        default=True,
        description="Whether event history begins at the game evidence origin and ends at terminal_cursor.",
    )
    combat_log_complete: bool = Field(
        default=True,
        description="Whether combat logs begin at the game evidence origin and end at terminal_cursor.",
    )
    initial_snapshot_complete: bool = Field(
        default=True,
        description="Whether every initial combatant is present in the initial snapshot.",
    )
    final_snapshot_complete: bool = Field(
        default=True,
        description="Whether every terminal combatant is present in the final snapshot.",
    )


class UsageCountV1(FrozenSummaryModel):
    """Lifecycle counts for one typed action, spell, or item identity."""

    attempted: int = Field(default=0, ge=0, description="Terminal action lineages observed, including cancellation.")
    completed: int = Field(default=0, ge=0, description="Action lineages that reached completion.")
    canceled: int = Field(default=0, ge=0, description="Action lineages that ended in cancellation.")


class AttackStatisticsV1(FrozenSummaryModel):
    """Resolved attack-lineage aggregates."""

    attempted: int = Field(default=0, ge=0, description="Attack lineages that reached a terminal phase.")
    resolved: int = Field(default=0, ge=0, description="Completed attacks carrying a typed attack outcome.")
    hits: int = Field(default=0, ge=0, description="Resolved non-critical and critical hits.")
    misses: int = Field(default=0, ge=0, description="Resolved misses, including critical misses.")
    critical_hits: int = Field(default=0, ge=0, description="Resolved critical hits.")
    critical_misses: int = Field(default=0, ge=0, description="Resolved critical misses.")
    canceled: int = Field(default=0, ge=0, description="Attack lineages canceled before completion.")
    opportunity_attacks: Optional[int] = Field(
        default=None,
        ge=0,
        description="Opportunity attacks identified by structured AttackLogData, or null when logs are incomplete.",
    )


class DamageStatisticsV1(FrozenSummaryModel):
    """Damage amounts distinguishable from current typed event evidence."""

    incoming_raw: int = Field(
        default=0,
        ge=0,
        description="Damage presented to TakeDamageEvent before defenses and hit-point pools.",
    )
    applied: int = Field(
        default=0,
        ge=0,
        description="Positive damage absorbed by temporary or normal hit points.",
    )
    normal_hit_point_damage: int = Field(default=0, ge=0, description="Damage removed from normal hit points.")
    temporary_hit_point_damage: int = Field(default=0, ge=0, description="Damage absorbed by temporary hit points.")
    unapplied_remainder: int = Field(
        default=0,
        ge=0,
        description=(
            "Raw incoming damage not represented as applied damage. Current evidence cannot split this among "
            "resistance, immunity, flat reduction, blockers, survival caps, or overkill."
        ),
    )
    incoming_packets: int = Field(default=0, ge=0, description="Terminal TakeDamageEvent lineages.")
    applied_packets: int = Field(default=0, ge=0, description="Completed positive DamageAppliedEvent lineages.")
    blocked_packets: int = Field(default=0, ge=0, description="Canceled TakeDamageEvent lineages.")
    applied_by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Applied damage grouped by the typed primary DamageType.",
    )


class HealingStatisticsV1(FrozenSummaryModel):
    """Requested and actually restored hit points."""

    requested: int = Field(default=0, ge=0, description="Healing requested before caps or blockers.")
    applied: int = Field(default=0, ge=0, description="Normal hit points actually restored.")
    events: int = Field(default=0, ge=0, description="Terminal HealEvent lineages.")
    blocked_events: int = Field(default=0, ge=0, description="HealEvent lineages explicitly marked blocked.")


class MovementStatisticsV1(FrozenSummaryModel):
    """Movement grouped by authoritative concrete event type."""

    voluntary_events: int = Field(default=0, ge=0, description="Completed path MovementEvent lineages excluding JumpEvent.")
    voluntary_feet: int = Field(default=0, ge=0, description="Traversed voluntary path distance in feet.")
    jump_events: int = Field(default=0, ge=0, description="Completed JumpEvent lineages.")
    jump_feet: int = Field(default=0, ge=0, description="Authoritative jump distance in feet.")
    forced_events: int = Field(default=0, ge=0, description="Completed ForcedMovementEvent lineages.")
    forced_feet: int = Field(default=0, ge=0, description="Actual forced displacement in feet.")


class CombatStatisticsV1(FrozenSummaryModel):
    """Objective aggregate shared by combatants, sides, and unattributed sources."""

    turns_started: int = Field(default=0, ge=0, description="Completed TurnStartEvent lineages.")
    turns_ended: int = Field(default=0, ge=0, description="Completed TurnEndEvent lineages.")
    attacks: AttackStatisticsV1 = Field(default_factory=AttackStatisticsV1, description="Attack aggregates.")
    damage_dealt: DamageStatisticsV1 = Field(default_factory=DamageStatisticsV1, description="Damage sourced by this aggregate.")
    damage_taken: DamageStatisticsV1 = Field(default_factory=DamageStatisticsV1, description="Damage targeting this aggregate.")
    healing_done: HealingStatisticsV1 = Field(default_factory=HealingStatisticsV1, description="Healing sourced by this aggregate.")
    healing_received: HealingStatisticsV1 = Field(default_factory=HealingStatisticsV1, description="Healing targeting this aggregate.")
    movement: MovementStatisticsV1 = Field(default_factory=MovementStatisticsV1, description="Movement of this aggregate.")
    action_usage: dict[str, UsageCountV1] = Field(default_factory=dict, description="ActionEvent usage by typed event name.")
    spell_usage: dict[str, UsageCountV1] = Field(default_factory=dict, description="SpellEvent usage by spell_id.")
    item_action_usage: dict[str, UsageCountV1] = Field(
        default_factory=dict,
        description="Item-bound action usage by runtime item UUID.",
    )
    item_charges_spent: dict[str, int] = Field(
        default_factory=dict,
        description="Finite item charges consumed by item semantic key.",
    )
    action_economy_spent: dict[str, int] = Field(
        default_factory=dict,
        description="Actions, bonus actions, reactions, and movement costs spent by completed actions.",
    )
    resources_spent: dict[str, int] = Field(
        default_factory=dict,
        description="Spell slots and named resources spent by completed actions.",
    )
    conditions_applied: dict[str, int] = Field(
        default_factory=dict,
        description="Conditions applied to members of this aggregate by semantic key.",
    )
    conditions_removed: dict[str, int] = Field(
        default_factory=dict,
        description="Conditions removed from members of this aggregate by semantic key.",
    )
    kills: int = Field(default=0, ge=0, description="DeathEvent lineages naming a member as killer.")
    deaths: int = Field(default=0, ge=0, description="DeathEvent lineages naming a member as defeated.")


class EntitySummaryV1(FrozenSummaryModel):
    """Boundary states and objective aggregates for one combatant."""

    entity_uuid: UUID = Field(description="Combatant identity.")
    side_id: str = Field(description="Side identity used for aggregation.")
    name: str = Field(description="Final display name, falling back to the initial name.")
    initial: Optional[EntitySnapshotV1] = Field(default=None, description="Initial objective state when supplied.")
    final: Optional[EntitySnapshotV1] = Field(default=None, description="Terminal objective state when supplied.")
    statistics: CombatStatisticsV1 = Field(description="Objective event-derived statistics.")


class SideSummaryV1(FrozenSummaryModel):
    """Objective aggregate for one game side."""

    side_id: str = Field(description="Stable side or faction identity.")
    entity_uuids: tuple[UUID, ...] = Field(description="Sorted combatants assigned to this side.")
    initial_combatant_count: int = Field(ge=0, description="Combatants present in the initial snapshot.")
    final_combatant_count: int = Field(ge=0, description="Combatants present in the final snapshot.")
    surviving_combatant_count: int = Field(ge=0, description="Final combatants not marked defeated.")
    statistics: CombatStatisticsV1 = Field(description="Sum of member statistics.")


class GameOutcomeV1(FrozenSummaryModel):
    """Terminal result derived from final side survival and EncounterEndEvent."""

    terminal_event_observed: bool = Field(description="Whether a terminal EncounterEndEvent lineage was retained.")
    resolution: GameOutcomeResolution = Field(description="Victory, draw, or indeterminate result.")
    reason: Optional[str] = Field(default=None, description="Typed EncounterEndEvent reason when supplied.")
    winning_side_ids: tuple[str, ...] = Field(default_factory=tuple, description="Sides objectively winning the game.")
    losing_side_ids: tuple[str, ...] = Field(default_factory=tuple, description="Sides objectively losing the game.")
    surviving_side_ids: tuple[str, ...] = Field(default_factory=tuple, description="Sides with a non-defeated final member.")


class MetricProvenanceV1(FrozenSummaryModel):
    """Evidence source and limitations for one metric family."""

    metric: str = Field(description="Stable metric family identity.")
    availability: MetricAvailability = Field(description="Availability under supplied evidence.")
    sources: tuple[str, ...] = Field(default_factory=tuple, description="Typed evidence sources used by the reducer.")
    note: str = Field(description="Precise interpretation or limitation of the retained evidence.")


class SummaryCompletenessV1(FrozenSummaryModel):
    """Whether the supplied evidence satisfies the v1 reduction contract."""

    status: SummaryCompletenessStatus = Field(description="Complete or partial evidence status.")
    issues: tuple[str, ...] = Field(default_factory=tuple, description="Sorted machine-readable completeness issues.")


class SummaryProvenanceV1(FrozenSummaryModel):
    """Counts and semantics of evidence consumed by the reducer."""

    reducer_id: str = Field(default="dnd.analytics.game_summary.v1", description="Stable reducer implementation identity.")
    event_model: str = Field(
        default="dnd.core.events.events_registry.Event",
        description="Typed event base consumed by the reducer.",
    )
    combat_log_model: str = Field(
        default="dnd.core.combat_log.CombatLogEntry",
        description="Typed structured combat-log model consumed without prose parsing.",
    )
    initial_snapshot_count: int = Field(ge=0, description="Initial entity snapshots supplied.")
    final_snapshot_count: int = Field(ge=0, description="Final entity snapshots supplied.")
    event_versions_seen: int = Field(ge=0, description="Event phase versions supplied.")
    event_lineages_seen: int = Field(ge=0, description="Distinct event lineages supplied.")
    terminal_lineages_reduced: int = Field(ge=0, description="Lineages reaching completion or cancellation.")
    top_level_combat_logs_seen: int = Field(ge=0, description="Top-level combat logs supplied.")
    structured_combat_logs_seen: int = Field(ge=0, description="Top-level and nested structured logs inspected.")
    metric_provenance: tuple[MetricProvenanceV1, ...] = Field(description="Provenance for every summary metric family.")


class GameSummaryV1(FrozenSummaryModel):
    """Canonical objective terminal summary for one game."""

    schema_name: Literal["dnd.game-summary"] = Field(default="dnd.game-summary", description="Stable schema identity.")
    schema_version: Literal[1] = Field(default=1, description="Game summary schema version.")
    game_id: str = Field(description="Hosted game identity supplied by the caller.")
    encounter_uuid: UUID = Field(description="Authoritative encounter identity.")
    started_at: Optional[datetime] = Field(default=None, description="EncounterStartEvent timestamp when retained.")
    ended_at: Optional[datetime] = Field(default=None, description="EncounterEndEvent timestamp when retained.")
    duration_seconds: Optional[float] = Field(
        default=None,
        ge=0,
        description="Elapsed event time between retained encounter start and end.",
    )
    rounds_started: int = Field(default=0, ge=0, description="Highest completed RoundStartEvent round number.")
    terminal_cursor: TerminalCursorV1 = Field(description="Exclusive event and combat-log terminal cursors.")
    outcome: GameOutcomeV1 = Field(description="Objective terminal result.")
    entities: tuple[EntitySummaryV1, ...] = Field(description="Entity summaries sorted by UUID.")
    sides: tuple[SideSummaryV1, ...] = Field(description="Side summaries sorted by side identity.")
    unattributed_statistics: CombatStatisticsV1 = Field(
        description="Evidence whose source or target is outside the supplied combatant snapshots.",
    )
    completeness: SummaryCompletenessV1 = Field(description="Completeness of the supplied evidence.")
    provenance: SummaryProvenanceV1 = Field(description="Evidence counts, sources, and limitations.")
    canonical_sha256: str = Field(
        min_length=64,
        max_length=64,
        description="SHA-256 of canonical JSON with this field excluded.",
    )


class DamagePreventionStatisticsV2(FrozenSummaryModel):
    """Exact prevention and amplification categories retained by damage resolution."""

    event_prevented: int = Field(
        default=0,
        ge=0,
        description="Damage removed by reactive event handlers before health resolution.",
    )
    resistance_prevented: int = Field(
        default=0,
        ge=0,
        description="Damage prevented by typed resistance affinities.",
    )
    immunity_prevented: int = Field(
        default=0,
        ge=0,
        description="Damage prevented by typed immunity affinities.",
    )
    flat_reduction_prevented: int = Field(
        default=0,
        ge=0,
        description="Damage prevented by flat packet-level reduction.",
    )
    survival_cap_prevented: int = Field(
        default=0,
        ge=0,
        description="Damage prevented by effects that cap normal hit-point loss.",
    )
    blocked_damage: int = Field(
        default=0,
        ge=0,
        description="Declared damage on packets canceled before health resolution.",
    )
    vulnerability_bonus: int = Field(
        default=0,
        ge=0,
        description="Additional damage created by typed vulnerability affinities.",
    )
    event_amplification: int = Field(
        default=0,
        ge=0,
        description="Additional damage created by event handlers before health resolution.",
    )


class DamageStatisticsV2(DamageStatisticsV1):
    """Damage statistics with exact mitigation and attribution evidence."""

    effective_normal_hit_point_damage: int = Field(
        default=0,
        ge=0,
        description="Normal hit points that existed and were actually removed.",
    )
    overkill_damage: int = Field(
        default=0,
        ge=0,
        description="Applied normal-HP damage beyond available normal hit points.",
    )
    prevention: DamagePreventionStatisticsV2 = Field(
        default_factory=DamagePreventionStatisticsV2,
        description="Typed damage prevention and amplification breakdown.",
    )
    incoming_by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Damage entering health resolution grouped by component DamageType.",
    )
    after_affinity_by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Component damage after resistance, immunity, or vulnerability.",
    )
    applied_by_counterparty: dict[str, int] = Field(
        default_factory=dict,
        description="Applied damage grouped by opposing source or target entity UUID.",
    )
    applied_by_effect: dict[str, int] = Field(
        default_factory=dict,
        description="Applied damage grouped by the nearest typed effect, spell, or action identity.",
    )


class OutcomeCountV2(FrozenSummaryModel):
    """Resolved outcome counts for one saving-throw ability or skill."""

    attempted: int = Field(default=0, ge=0, description="Terminal roll lineages observed.")
    resolved: int = Field(default=0, ge=0, description="Lineages carrying a boolean result.")
    successes: int = Field(default=0, ge=0, description="Resolved successful outcomes.")
    failures: int = Field(default=0, ge=0, description="Resolved failed outcomes.")


class ResolutionStatisticsV2(OutcomeCountV2):
    """Success and failure counts for saving throws or skill checks."""

    by_kind: dict[str, OutcomeCountV2] = Field(
        default_factory=dict,
        description="Outcomes grouped by ability or skill identity.",
    )


class RollLuckStatisticsV2(FrozenSummaryModel):
    """Observed dice outcomes compared with their mechanic-conditioned expectation."""

    roll_events: int = Field(default=0, ge=0, description="Distinct roll events reduced.")
    outcome_samples: int = Field(
        default=0,
        ge=0,
        description="Selected d20 outcomes or individual damage/healing dice measured.",
    )
    random_faces_rolled: int = Field(
        default=0,
        ge=0,
        description="Random die faces generated, including alternatives from advantage.",
    )
    observed_total: int = Field(default=0, description="Sum of natural selected outcomes.")
    expected_total: float = Field(default=0.0, description="Expected total under each roll mechanic.")
    variance_total: float = Field(
        default=0.0,
        ge=0,
        description="Sum of theoretical variances used to normalize luck.",
    )
    average_observed: Optional[float] = Field(
        default=None,
        description="Observed average per selected outcome sample.",
    )
    average_expected: Optional[float] = Field(
        default=None,
        description="Expected average per selected outcome sample.",
    )
    luck_delta: float = Field(
        default=0.0,
        description="Observed total minus mechanic-conditioned expected total.",
    )
    luck_z_score: Optional[float] = Field(
        default=None,
        description="Luck delta divided by theoretical standard deviation.",
    )
    natural_ones: int = Field(default=0, ge=0, description="Selected natural d20 results of one.")
    natural_twenties: int = Field(default=0, ge=0, description="Selected natural d20 results of twenty.")
    advantage_events: int = Field(default=0, ge=0, description="Rolls resolved with advantage.")
    disadvantage_events: int = Field(default=0, ge=0, description="Rolls resolved with disadvantage.")
    modified_events: int = Field(
        default=0,
        ge=0,
        description="Roll-result events changed by an explicit engine processor.",
    )


class DiceStatisticsV2(FrozenSummaryModel):
    """Luck summaries partitioned by D&D roll category."""

    all_d20: RollLuckStatisticsV2 = Field(
        default_factory=RollLuckStatisticsV2,
        description="All attack, saving-throw, and skill-check d20 outcomes.",
    )
    attack_d20: RollLuckStatisticsV2 = Field(
        default_factory=RollLuckStatisticsV2,
        description="Attack d20 outcomes.",
    )
    saving_throw_d20: RollLuckStatisticsV2 = Field(
        default_factory=RollLuckStatisticsV2,
        description="Saving-throw d20 outcomes.",
    )
    skill_check_d20: RollLuckStatisticsV2 = Field(
        default_factory=RollLuckStatisticsV2,
        description="Skill-check d20 outcomes.",
    )
    damage: RollLuckStatisticsV2 = Field(
        default_factory=RollLuckStatisticsV2,
        description="Individual damage-die outcomes before explicit reroll processors.",
    )
    healing: RollLuckStatisticsV2 = Field(
        default_factory=RollLuckStatisticsV2,
        description="Individual healing-die outcomes before explicit roll processors.",
    )


class CombatStatisticsV2(CombatStatisticsV1):
    """V2 objective aggregate with attribution, resolution, and dice evidence."""

    damage_dealt: DamageStatisticsV2 = Field(default_factory=DamageStatisticsV2)
    damage_taken: DamageStatisticsV2 = Field(default_factory=DamageStatisticsV2)
    saving_throws: ResolutionStatisticsV2 = Field(default_factory=ResolutionStatisticsV2)
    skill_checks: ResolutionStatisticsV2 = Field(default_factory=ResolutionStatisticsV2)
    dice: DiceStatisticsV2 = Field(default_factory=DiceStatisticsV2)


class EntitySummaryV2(EntitySummaryV1):
    """V2 combatant summary with expanded objective statistics."""

    statistics: CombatStatisticsV2 = Field(description="Objective event-derived V2 statistics.")


class SideSummaryV2(SideSummaryV1):
    """V2 side summary with expanded objective statistics."""

    statistics: CombatStatisticsV2 = Field(description="Sum of member V2 statistics.")


class GameSummaryV2(GameSummaryV1):
    """Canonical objective terminal summary with deep post-match analysis."""

    schema_version: Literal[2] = Field(default=2, description="Game summary schema version.")
    entities: tuple[EntitySummaryV2, ...] = Field(description="V2 entity summaries sorted by UUID.")
    sides: tuple[SideSummaryV2, ...] = Field(description="V2 side summaries sorted by side identity.")
    unattributed_statistics: CombatStatisticsV2 = Field(
        description="V2 evidence whose source or target is outside supplied snapshots.",
    )


GameSummary = Annotated[
    Union[GameSummaryV1, GameSummaryV2],
    Field(discriminator="schema_version"),
]


def canonical_summary_bytes(summary: GameSummaryV1 | GameSummaryV2) -> bytes:
    """Serialize a summary deterministically without its self-referential digest.

    Args:
        summary: Summary to serialize.

    Returns:
        Canonical UTF-8 JSON bytes.
    """
    payload = summary.model_dump(mode="json", exclude={"canonical_sha256"})
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def compute_summary_digest(summary: GameSummaryV1 | GameSummaryV2) -> str:
    """Compute the canonical SHA-256 digest for a summary.

    Args:
        summary: Summary whose digest field is ignored.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """
    return sha256(canonical_summary_bytes(summary)).hexdigest()


def summary_digest_is_valid(summary: GameSummaryV1 | GameSummaryV2) -> bool:
    """Return whether the stored digest matches canonical summary content.

    Args:
        summary: Summary to validate.

    Returns:
        True when canonical content hashes to canonical_sha256.
    """
    return compute_summary_digest(summary) == summary.canonical_sha256
