"""Contracts for complete Elo matrix gauntlet evaluation."""

from __future__ import annotations

from typing import Any, Literal, Optional, Protocol

from pydantic import BaseModel, Field

from ai.evaluation.tournament import EloConfig, TournamentMatchRecord


EloMatrixMode = Literal["elo_smoke", "elo_matrix", "elo_matrix_large", "elo_regression"]
EloCompletionStatus = Literal["not_run", "partial", "completed"]
EloGateStatus = Literal["not_run", "passed", "failed"]
EloEligibilityStatus = Literal["eligible", "skipped"]
EloLedgerName = Literal["setup_side", "arena_balance", "policy_side", "policy_global", "roster"]
EloGauntletEventType = Literal[
    "ELO_GAUNTLET_STARTED",
    "ELO_MATCH_RETRY_SCHEDULED",
    "ELO_MATCH_STARTED",
    "ELO_MATCH_ARTIFACT_WRITTEN",
    "ELO_MATCH_COMPLETED",
    "ELO_MATCH_SKIPPED_FROM_RATING",
    "ELO_RATINGS_UPDATED",
    "ELO_CHECKPOINT_WRITTEN",
    "ELO_GAUNTLET_COMPLETED",
    "ELO_GAUNTLET_FAILED",
]


class EloMatrixScheduleEntry(BaseModel):
    """One deterministic row in an Elo matrix schedule."""

    match_index: int = Field(description="Zero-based row index.")
    arena_id: str = Field(description="Validation arena id.")
    random_seed: int = Field(description="Deterministic random seed.")
    hero_first: bool = Field(description="Whether heroes open the encounter.")
    side_order_id: str = Field(description="Stable side-order label.")
    controller_profile: str = Field(description="Controller profile requested for both sides.")
    policy_version: Optional[str] = Field(default=None, description="Policy version or source hash under evaluation.")
    requested_hero_profile: Optional[str] = Field(
        default=None,
        description="Requested hero profile label; not treated as runtime truth without manifest support.",
    )
    requested_monster_profile: Optional[str] = Field(
        default=None,
        description="Requested monster profile label; not treated as runtime truth without manifest support.",
    )
    tags: tuple[str, ...] = Field(default_factory=tuple, description="Schedule tags copied from the arena and evaluator mode.")
    schedule_group: str = Field(default="all_arenas", description="Logical schedule group.")
    repeat_key: str = Field(description="Stable key for detecting duplicate planned rows.")


class EloMatrixSchedule(BaseModel):
    """Deterministic matrix schedule for Elo evaluation."""

    schema_version: Literal[1] = Field(default=1, description="Schedule schema version.")
    matrix_id: str = Field(description="Stable matrix batch id.")
    mode: EloMatrixMode = Field(description="Evaluator mode.")
    created_at: str = Field(description="UTC creation timestamp.")
    arena_catalog_hash: str = Field(description="Hash of arena ids and metadata used for this schedule.")
    policy_catalog_hash: str = Field(description="Hash of controller and policy identity inputs.")
    seed_policy: str = Field(description="Human-readable seed policy.")
    side_order_policy: str = Field(description="Human-readable side-order policy.")
    entries: list[EloMatrixScheduleEntry] = Field(default_factory=list, description="Scheduled matrix rows.")
    schedule_hash: str = Field(description="Stable hash of scheduled rows and evaluator inputs.")


class EntityRosterRow(BaseModel):
    """Stable summary of one constructed combatant."""

    stable_name: str = Field(description="Display name without relying on UUID.")
    faction: Optional[str] = Field(default=None, description="Faction at arena construction time.")
    controller_type: Optional[str] = Field(default=None, description="Installed precombat controller type.")
    position: Optional[tuple[int, int]] = Field(default=None, description="Starting position.")
    class_or_monster: str = Field(description="Python class or semantic monster/class label.")
    level_or_cr: Optional[str] = Field(default=None, description="Level or challenge rating when available.")
    max_hp: Optional[int] = Field(default=None, description="Maximum hit points when available.")
    current_hp: Optional[int] = Field(default=None, description="Starting hit points when available.")
    ac: Optional[int] = Field(default=None, description="Starting Armor Class when available.")
    speed: Optional[int] = Field(default=None, description="Starting movement speed when available.")
    senses: dict[str, Any] = Field(default_factory=dict, description="Stable senses summary.")
    ability_summary: dict[str, int] = Field(default_factory=dict, description="Ability scores or modifiers.")
    saving_throw_summary: dict[str, int] = Field(default_factory=dict, description="Saving throw bonuses when available.")
    resistances: list[str] = Field(default_factory=list, description="Damage resistances.")
    immunities: list[str] = Field(default_factory=list, description="Damage immunities.")
    vulnerabilities: list[str] = Field(default_factory=list, description="Damage vulnerabilities.")
    conditions_at_start: list[str] = Field(default_factory=list, description="Active condition names at match start.")
    condition_summary: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Typed active-condition identities and categories at match start.",
    )
    equipment_summary: list[dict[str, Any]] = Field(default_factory=list, description="Equipped item summaries.")
    inventory_summary: list[dict[str, Any]] = Field(default_factory=list, description="Inventory item summaries.")
    spell_summary: list[str] = Field(default_factory=list, description="Registered spell/action names.")
    action_template_summary: list[dict[str, Any]] = Field(default_factory=list, description="Registered action template summaries.")
    trait_summary: list[str] = Field(default_factory=list, description="Trait or handler names.")
    handler_summary: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Typed event-handler identities, roles, and trigger contracts.",
    )


class ArenaManifest(BaseModel):
    """Runtime truth for one constructed arena before self-play begins."""

    schema_version: Literal[1] = Field(default=1, description="Manifest schema version.")
    arena_id: str = Field(description="Validation arena id.")
    title: str = Field(description="Human-readable arena title.")
    hero_role: str = Field(description="Hero role from the validation spec.")
    tags: tuple[str, ...] = Field(default_factory=tuple, description="Validation spec tags.")
    expected_pressure: tuple[str, ...] = Field(default_factory=tuple, description="Expected behavior pressure.")
    map_notes: tuple[str, ...] = Field(default_factory=tuple, description="Arena map notes.")
    notable_positions: dict[str, tuple[int, int]] = Field(default_factory=dict, description="Named important positions.")
    map_size: tuple[int, int] = Field(description="Grid size as width and height.")
    map_bounds: tuple[int, int, int, int] = Field(description="Grid bounds as min_x, min_y, max_x, max_y.")
    opening_faction: Optional[str] = Field(default=None, description="Faction of the first initiative entry.")
    initiative_order: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Stable precombat initiative rows in actual opening order.",
    )
    terrain_summary: dict[str, Any] = Field(default_factory=dict, description="Terrain and tile counts.")
    object_summary: list[dict[str, Any]] = Field(default_factory=list, description="Placed object summaries.")
    entity_rosters: dict[str, list[EntityRosterRow]] = Field(default_factory=dict, description="Roster rows grouped by faction.")
    roster_hash_by_side: dict[str, str] = Field(default_factory=dict, description="Stable roster hash by faction.")
    manifest_hash: str = Field(description="Stable content hash for this manifest.")


class EloMatchFailureArtifact(BaseModel):
    """Durable forensic evidence for a match that crashed or timed out."""

    schema_version: Literal[1] = Field(default=1, description="Failure artifact schema version.")
    matrix_id: str = Field(description="Owning Elo matrix id.")
    match_id: str = Field(description="Stable scheduled match id.")
    match_index: int = Field(description="Schedule row index.")
    attempt_number: int = Field(ge=1, description="One-based execution attempt.")
    generated_at: str = Field(description="UTC failure timestamp.")
    status: Literal["crashed", "timeout"] = Field(description="Terminal evaluator failure status.")
    exception_type: str = Field(description="Raised exception class name.")
    message: str = Field(description="Raised exception message.")
    traceback: str = Field(description="Formatted exception traceback.")
    elapsed_ms: float = Field(ge=0, description="Elapsed evaluator time before failure.")
    max_commands: int = Field(ge=1, description="Configured command cap for the match.")
    timeout_seconds: float = Field(gt=0, description="Configured wall-clock deadline.")
    schedule_entry: EloMatrixScheduleEntry = Field(description="Exact scheduled row that failed.")
    arena_manifest: Optional[ArenaManifest] = Field(
        default=None,
        description="Exact precombat manifest when construction reached that boundary.",
    )
    runtime_policy_version: Optional[str] = Field(default=None, description="Runtime policy version.")
    runtime_policy_source_hash: Optional[str] = Field(default=None, description="Runtime policy source hash.")
    runtime_controller_profile: Optional[str] = Field(default=None, description="Runtime controller profile.")


class EloParticipant(BaseModel):
    """Rated participant identity for one ledger."""

    participant_id: str = Field(description="Stable rated participant id.")
    ledger: EloLedgerName = Field(description="Ledger this participant belongs to.")
    side: str = Field(description="Faction or side label.")
    policy_version: Optional[str] = Field(default=None, description="Policy version under evaluation.")
    controller_profile: str = Field(description="Controller profile.")
    arena_id: Optional[str] = Field(default=None, description="Arena id when the ledger is arena-scoped.")
    roster_hash: Optional[str] = Field(default=None, description="Roster hash when the ledger is roster-scoped.")
    faction: Optional[str] = Field(default=None, description="Source faction label.")
    tags: tuple[str, ...] = Field(default_factory=tuple, description="Participant tags.")
    display_name: str = Field(description="Human-readable participant label.")


class EloEligibility(BaseModel):
    """Rating eligibility audit for one match."""

    status: EloEligibilityStatus = Field(description="Whether the match can update official Elo ledgers.")
    rating_eligible: bool = Field(description="Convenience boolean for eligibility.")
    reasons: list[str] = Field(default_factory=list, description="Reasons the row is not eligible.")
    subjectivity_status: str = Field(description="Subjectivity audit status.")
    runner_status: str = Field(description="Self-play runner status.")
    command_status_counts: dict[str, int] = Field(default_factory=dict, description="Command status counts.")
    encounter_finished: bool = Field(description="Whether the encounter reached a natural end.")
    command_cap_reached: bool = Field(description="Whether the command cap stopped the match.")
    crashed: bool = Field(default=False, description="Whether the row crashed.")
    timed_out: bool = Field(default=False, description="Whether the row timed out.")
    has_unknown_outcome: bool = Field(description="Whether the inferred outcome was unknown.")


class EloRatingUpdate(BaseModel):
    """Before/after rating movement for one ledger pair."""

    ledger: EloLedgerName = Field(description="Ledger updated by this result.")
    participant_a: str = Field(description="First participant id.")
    participant_b: str = Field(description="Second participant id.")
    rating_before: dict[str, float] = Field(description="Ratings before the update.")
    rating_after: dict[str, float] = Field(description="Ratings after the update.")
    rating_delta: dict[str, float] = Field(description="Delta caused by this match.")


class EloRatingSnapshot(BaseModel):
    """One point in a ledger rating time series."""

    match_index: int = Field(description="Schedule row index.")
    match_id: str = Field(description="Match that produced this snapshot.")
    ledger: EloLedgerName = Field(description="Rating ledger.")
    participant_id: str = Field(description="Rated participant id.")
    rating: float = Field(description="Rating after the match.")


class EloStanding(BaseModel):
    """Ranking row for one participant in one ledger."""

    rank: int = Field(description="One-based rank by rating.")
    participant_id: str = Field(description="Rated participant id.")
    display_name: str = Field(description="Human-readable name.")
    rating: float = Field(description="Current rating.")
    games: int = Field(description="Rating-eligible games.")
    wins: int = Field(default=0, description="Wins in this ledger.")
    losses: int = Field(default=0, description="Losses in this ledger.")
    draws: int = Field(default=0, description="Draws in this ledger.")
    skipped: int = Field(default=0, description="Skipped or abnormal rows touching this participant.")
    latest_delta: float = Field(default=0.0, description="Most recent rating movement.")
    warnings: list[str] = Field(default_factory=list, description="Confidence warnings.")
    tags: tuple[str, ...] = Field(default_factory=tuple, description="Participant tags.")


class EloRatingLedger(BaseModel):
    """Complete rating table and time series for one ledger."""

    ledger_name: EloLedgerName = Field(description="Ledger identity.")
    elo_config: EloConfig = Field(description="Elo configuration.")
    ratings: dict[str, float] = Field(default_factory=dict, description="Current ratings.")
    standings: list[EloStanding] = Field(default_factory=list, description="Sorted standings.")
    rating_series: list[EloRatingSnapshot] = Field(default_factory=list, description="Rating time series.")
    match_count_by_participant: dict[str, int] = Field(default_factory=dict, description="Eligible games by participant.")
    eligible_match_count: int = Field(default=0, description="Eligible update count.")
    skipped_match_count: int = Field(default=0, description="Skipped rows touching this ledger.")


class EloMatchRecord(BaseModel):
    """One retained Elo evaluator match record."""

    schema_version: Literal[1] = Field(default=1, description="Match record schema version.")
    match_id: str = Field(description="Stable match id.")
    match_index: int = Field(description="Schedule index.")
    attempt_number: int = Field(default=1, ge=1, description="One-based execution attempt for this schedule row.")
    prior_attempt_record_paths: list[str] = Field(
        default_factory=list,
        description="Archived match-record paths for superseded attempts.",
    )
    runtime_policy_version: Optional[str] = Field(default=None, description="Policy version captured by the raw artifact.")
    runtime_policy_source_hash: Optional[str] = Field(
        default=None,
        description="Composite policy source hash captured by the raw artifact.",
    )
    runtime_controller_profile: Optional[str] = Field(
        default=None,
        description="Controller profile captured by the raw artifact.",
    )
    runtime_subjectivity_validator: Optional[str] = Field(
        default=None,
        description="Independent perception witness captured by the raw artifact.",
    )
    schedule_entry: EloMatrixScheduleEntry = Field(description="Scheduled row.")
    arena_manifest: Optional[ArenaManifest] = Field(default=None, description="Constructed arena truth when available.")
    base_record: Optional[TournamentMatchRecord] = Field(default=None, description="Existing tournament-compatible match record.")
    participants: list[EloParticipant] = Field(default_factory=list, description="Rated participants touched by this row.")
    eligibility: EloEligibility = Field(description="Rating eligibility audit.")
    rating_updates_by_ledger: dict[EloLedgerName, EloRatingUpdate] = Field(
        default_factory=dict,
        description="Official rating updates applied by ledger.",
    )
    artifact_paths: list[str] = Field(default_factory=list, description="Raw artifact paths retained for this row.")
    friction_flags: list[str] = Field(default_factory=list, description="High-level friction or failure flags.")
    policy_trace_summary: dict[str, Any] = Field(default_factory=dict, description="Compact policy trace summary.")


class EloCoverageSummary(BaseModel):
    """Coverage evidence for one matrix run."""

    arena_ids_scheduled: list[str] = Field(default_factory=list, description="Scheduled arena ids.")
    arena_ids_completed: list[str] = Field(default_factory=list, description="Arena ids with at least one completed row.")
    arena_ids_missing: list[str] = Field(default_factory=list, description="Scheduled arenas without completed rows.")
    seeds_scheduled: list[int] = Field(default_factory=list, description="Scheduled seeds.")
    side_orders_scheduled: list[str] = Field(default_factory=list, description="Scheduled side-order ids.")
    side_order_counts: dict[str, int] = Field(default_factory=dict, description="Completed counts by side order.")
    tags_covered: list[str] = Field(default_factory=list, description="Arena tags present in scheduled rows.")
    roster_hashes_covered: list[str] = Field(default_factory=list, description="Roster hashes retained in manifests.")


class EloGauntletEvent(BaseModel):
    """Cursor-addressed event for live Elo gauntlet watchers."""

    cursor: int = Field(description="Monotonic event cursor within the run.")
    event_type: EloGauntletEventType = Field(description="Event type.")
    matrix_id: str = Field(description="Matrix id.")
    match_id: Optional[str] = Field(default=None, description="Related match id when present.")
    match_index: Optional[int] = Field(default=None, description="Related schedule index when present.")
    status: Optional[str] = Field(default=None, description="Compact status.")
    message: Optional[str] = Field(default=None, description="Human-readable event note.")
    payload: dict[str, Any] = Field(default_factory=dict, description="Typed event payload.")
    created_at: str = Field(description="UTC timestamp.")


class EloGauntletEventSink(Protocol):
    """Transport-neutral destination for Elo evaluator watcher events."""

    def append(
        self,
        *,
        event_type: EloGauntletEventType,
        matrix_id: str,
        match_id: Optional[str] = None,
        match_index: Optional[int] = None,
        status: Optional[str] = None,
        message: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> EloGauntletEvent:
        """Append one cursor-addressed evaluator event."""
        ...

    def since(self, cursor: int = 0) -> list[EloGauntletEvent]:
        """Return locally retained evaluator events after a cursor."""
        ...


class EloGauntletCheckpoint(BaseModel):
    """Compact resumable progress state for an Elo matrix run."""

    schema_version: Literal[1] = Field(default=1, description="Checkpoint schema version.")
    matrix_id: str = Field(description="Matrix id.")
    generated_at: str = Field(description="UTC timestamp.")
    schedule_hash: str = Field(description="Hash of the exact schedule being resumed.")
    scheduled_count: int = Field(description="Total scheduled rows.")
    completed_count: int = Field(description="Rows with retained match records.")
    eligible_count: int = Field(description="Rows eligible for Elo updates.")
    skipped_rating_count: int = Field(description="Rows retained but excluded from ratings.")
    failed_count: int = Field(description="Rows with abnormal or ineligible results.")
    pending_count: int = Field(description="Rows not yet retained.")
    completion_status: EloCompletionStatus = Field(description="Run completion state.")
    gate_status: EloGateStatus = Field(description="Current evaluator gate state.")
    gate_reasons: list[str] = Field(default_factory=list, description="Current gate failures.")
    completed_match_indices: list[int] = Field(
        default_factory=list,
        description="Sorted schedule indices backed by individual match files.",
    )
    latest_match_id: Optional[str] = Field(default=None, description="Most recently retained match id.")


class EloGauntletSummary(BaseModel):
    """Complete retained summary for an Elo matrix evaluator run."""

    schema_version: Literal[1] = Field(default=1, description="Summary schema version.")
    matrix_id: str = Field(description="Matrix id.")
    mode: EloMatrixMode = Field(description="Evaluator mode.")
    generated_at: str = Field(description="UTC timestamp.")
    schedule_hash: str = Field(description="Schedule hash.")
    arena_catalog_hash: str = Field(description="Arena catalog hash.")
    policy_catalog_hash: str = Field(description="Policy catalog hash.")
    scheduled_count: int = Field(description="Scheduled row count.")
    completed_count: int = Field(description="Rows with retained match records.")
    eligible_count: int = Field(description="Rows used for official Elo updates.")
    skipped_rating_count: int = Field(description="Rows retained but skipped from ratings.")
    failed_count: int = Field(description="Rows with abnormal status.")
    pending_count: int = Field(description="Rows not yet attempted.")
    completion_status: EloCompletionStatus = Field(description="Run completion state.")
    gate_status: EloGateStatus = Field(description="Evaluator gate status.")
    gate_reasons: list[str] = Field(default_factory=list, description="Reasons the evaluator result is not clean.")
    schedule: EloMatrixSchedule = Field(description="Schedule used for this run.")
    matches: list[EloMatchRecord] = Field(default_factory=list, description="Retained match records.")
    ledgers: dict[EloLedgerName, EloRatingLedger] = Field(default_factory=dict, description="Rating ledgers.")
    failure_rows: list[dict[str, Any]] = Field(default_factory=list, description="Visible abnormal rows.")
    subjectivity_summary: dict[str, Any] = Field(default_factory=dict, description="Subjectivity audit aggregate.")
    performance: dict[str, Any] = Field(default_factory=dict, description="Batch-level performance aggregate.")
    coverage: EloCoverageSummary = Field(default_factory=EloCoverageSummary, description="Coverage summary.")
    dashboard_projection: dict[str, Any] = Field(default_factory=dict, description="Precomputed dashboard slices.")
    events: list[EloGauntletEvent] = Field(default_factory=list, description="Watcher events.")
