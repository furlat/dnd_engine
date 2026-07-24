"""Profile-driven projection of local subjective state into typed Codex blocks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import time
from typing import Callable, Literal, Mapping, Optional, Sequence, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from ai.codex_tools.representation.components import (
    ActionFamilyBlock,
    ActionFamilyPayload,
    ActionFamilySummary,
    ActionCapabilitySummary,
    ActionSemanticCoverage,
    AdviceBlock,
    AdvicePayload,
    CodexRepresentationBlock,
    CodexTurnRepresentation,
    CombatHypothesisBlock,
    CombatHypothesisPayload,
    CombatLogChildSummary,
    CombatLogSummary,
    ComponentErrorBlock,
    ComponentErrorPayload,
    ComponentExposureOmission,
    ContactLedgerBlock,
    ContactLedgerPayload,
    CoreRevisionBlock,
    CoreRevisionPayload,
    DecisionDeltaBlock,
    DecisionDeltaPayload,
    EncounterSummaryBlock,
    EncounterSummaryPayload,
    EntityRevisionChange,
    KnownObjectSummary,
    MultiTargetActionSummary,
    ObjectLedgerBlock,
    ObjectLedgerPayload,
    ObjectRevisionChange,
    PredicateFocusBlock,
    PredicateFocusPayload,
    RecentCombatLogsBlock,
    RecentCombatLogsPayload,
    RepresentationTelemetryBlock,
    RepresentationTelemetryPayload,
    RepresentationWarning,
    RuntimeTelemetryInput,
    SpatialSceneBlock,
    SpatialScenePayload,
    SubjectiveFrameSummary,
    TileRevisionChange,
    TopologySummaryBlock,
    TopologySummaryPayload,
    TurnCoreBlock,
    TurnCorePayload,
    TypedJsonPresentationBlock,
    TypedJsonPresentationPayload,
    WarningBlock,
    WarningPayload,
)
from ai.codex_tools.representation.models import (
    ExposureTiming,
    Recoverability,
    RecoveryInstruction,
    RepresentationBlock,
    ResolvedRepresentationComponent,
    ResolvedRepresentationManifest,
)
from ai.codex_tools.representation.predicates import PredicateLedgerSnapshot
from server.agent_protocol.observation import (
    KnowledgeState,
    ObservationEntityFact,
    ObservationFrame,
    SubjectiveWorldState,
)
from server.agent_protocol.control import ActionAffordance
from server.agent_protocol.semantics import SemanticProvenanceKind
from ai.subjective.models import AgentState


_ACTION_BUCKET_ORDER = (
    "entity_actions",
    "position_actions",
    "self_actions",
    "object_actions",
    "special_commands",
)
_PolicyDetail = Literal["selected_only", "ranked", "full_trace"]
_ExposureOmissionReason = Literal["disabled", "exposure_mismatch"]


class RequiredRepresentationComponentError(RuntimeError):
    """Raised when a required component cannot produce a valid payload."""

    def __init__(self, component_id: str, error_type: str) -> None:
        """Create a non-sensitive required-component failure."""
        super().__init__(f"Required representation component {component_id!r} failed")
        self.component_id = component_id
        self.error_type = error_type


class ComponentProjectionEvent(BaseModel):
    """Typed observational lifecycle event for one projection component."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    phase: Literal["started", "completed", "failed"] = Field(
        description="Observed component lifecycle phase.",
    )
    component_id: str = Field(description="Component being projected.")
    component_version: str = Field(description="Version of the component definition.")
    required: bool = Field(description="Whether component failure aborts the envelope.")
    timing_ms: float = Field(default=0.0, ge=0.0, description="Elapsed local projection time.")
    payload_bytes: int = Field(default=0, ge=0, description="Validated payload size when completed.")
    error_type: Optional[str] = Field(
        default=None,
        description="Exception class when projection failed, without exception arguments.",
    )


ComponentProjectionObserver = Callable[[ComponentProjectionEvent], None]


class RepresentationProjectionInput(BaseModel):
    """Complete local inputs available to one representation projection."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    world: SubjectiveWorldState = Field(
        description="Canonical current session-subjective world state.",
    )
    agent_state: AgentState = Field(
        default_factory=AgentState,
        description="Current derived local agent workspace.",
    )
    predicate_snapshot: Optional[PredicateLedgerSnapshot] = Field(
        default=None,
        description="Complete predicate ledger aligned to the current subjective revision.",
    )
    previous_world: Optional[SubjectiveWorldState] = Field(
        default=None,
        description="Optional prior decision-boundary world used for typed deltas.",
    )
    previous_agent_state: Optional[AgentState] = Field(
        default=None,
        description="Optional prior derived workspace used for changed-only beliefs.",
    )
    observation_frames: tuple[ObservationFrame, ...] = Field(
        default_factory=tuple,
        description="Ordered locally retained subjective envelopes after the prior boundary.",
    )
    policy_advice: Optional[AdvicePayload] = Field(
        default=None,
        description="Optional already-converted policy advice; projection never invokes policy.",
    )
    runtime_telemetry: Optional[RuntimeTelemetryInput] = Field(
        default=None,
        description="Optional observational runtime telemetry supplied by the caller.",
    )

    @model_validator(mode="after")
    def validate_revision_alignment(self) -> "RepresentationProjectionInput":
        """Reject derived inputs that belong to a different subjective revision."""
        facts = self.agent_state.facts
        epoch_id = self.world.current_epoch.epoch_id if self.world.current_epoch is not None else None
        if facts is not None:
            if facts.observation_cursor != self.world.observation_cursor:
                raise ValueError("AgentFacts observation cursor must match SubjectiveWorldState")
            if facts.epoch_id != epoch_id:
                raise ValueError("AgentFacts epoch id must match SubjectiveWorldState")
        if self.predicate_snapshot is not None:
            if self.predicate_snapshot.observation_cursor != self.world.observation_cursor:
                raise ValueError("Predicate snapshot cursor must match SubjectiveWorldState")
            if self.predicate_snapshot.epoch_id != epoch_id:
                raise ValueError("Predicate snapshot epoch id must match SubjectiveWorldState")
        if (
            self.previous_world is not None
            and self.previous_world.observation_cursor > self.world.observation_cursor
        ):
            raise ValueError("Previous world cannot be newer than the projected world")
        frame_cursors = tuple(frame.observation_cursor for frame in self.observation_frames)
        if frame_cursors != tuple(sorted(set(frame_cursors))):
            raise ValueError("observation_frames must have unique increasing cursors")
        if frame_cursors and frame_cursors[-1] > self.world.observation_cursor:
            raise ValueError("observation_frames cannot be newer than the projected world")
        if (
            frame_cursors
            and self.previous_world is not None
            and frame_cursors[0] <= self.previous_world.observation_cursor
        ):
            raise ValueError("observation_frames must follow the previous decision boundary")
        if self.policy_advice is not None and self.policy_advice.available:
            basis = self.policy_advice.basis
            epoch = self.world.current_epoch
            if basis is None or epoch is None:
                raise ValueError("Available policy advice requires a current matching epoch")
            if (
                basis.session_id != self.world.session.session_id
                or basis.observation_cursor != self.world.observation_cursor
                or basis.epoch_id != epoch.epoch_id
                or basis.actor_uuid != epoch.actor_uuid
            ):
                raise ValueError("policy_advice does not match the subjective world revision")
        return self


@dataclass(frozen=True, slots=True)
class _PayloadBuild:
    """Internal payload plus omission evidence produced by one component."""

    payload: BaseModel
    source_paths: tuple[str, ...]
    omitted_item_count: int = 0
    warnings: tuple[str, ...] = ()


_BlockType = type[RepresentationBlock[BaseModel]]
_Builder = Callable[
    [RepresentationProjectionInput, Mapping[str, JsonValue], tuple[str, ...]],
    _PayloadBuild,
]


_BLOCK_TYPES: dict[str, _BlockType] = {
    "core.revision": cast(_BlockType, CoreRevisionBlock),
    "core.turn": cast(_BlockType, TurnCoreBlock),
    "contacts.partition": cast(_BlockType, ContactLedgerBlock),
    "objects.known": cast(_BlockType, ObjectLedgerBlock),
    "topology.summary": cast(_BlockType, TopologySummaryBlock),
    "spatial.scene": cast(_BlockType, SpatialSceneBlock),
    "actions.index": cast(_BlockType, ActionFamilyBlock),
    "events.recent_logs": cast(_BlockType, RecentCombatLogsBlock),
    "events.decision_delta": cast(_BlockType, DecisionDeltaBlock),
    "memory.combat_hypotheses": cast(_BlockType, CombatHypothesisBlock),
    "predicates.focused": cast(_BlockType, PredicateFocusBlock),
    "attention.current_warnings": cast(_BlockType, WarningBlock),
    "oracle.policy": cast(_BlockType, AdviceBlock),
    "telemetry.runtime": cast(_BlockType, RepresentationTelemetryBlock),
    "encounter.summary": cast(_BlockType, EncounterSummaryBlock),
    "presentation.typed_json": cast(_BlockType, TypedJsonPresentationBlock),
}


class CodexRepresentationProjector:
    """Execute a resolved profile over one complete local subjective revision."""

    def __init__(self) -> None:
        """Create the closed built-in component implementation registry."""
        self._builders: dict[str, _Builder] = {
            "core.revision": _build_core_revision,
            "core.turn": _build_turn_core,
            "contacts.partition": _build_contacts,
            "objects.known": _build_objects,
            "topology.summary": _build_topology,
            "spatial.scene": _build_spatial_scene,
            "actions.index": _build_actions,
            "events.recent_logs": _build_recent_logs,
            "events.decision_delta": _build_decision_delta,
            "memory.combat_hypotheses": _build_combat_hypotheses,
            "predicates.focused": _build_predicates,
            "attention.current_warnings": _build_warnings,
            "oracle.policy": _build_advice,
            "telemetry.runtime": _build_runtime_telemetry,
            "encounter.summary": _build_encounter_summary,
            "presentation.typed_json": _build_presentation,
        }

    def project(
        self,
        manifest: ResolvedRepresentationManifest,
        inputs: RepresentationProjectionInput,
        *,
        exposure: ExposureTiming = ExposureTiming.DECISION_EPOCH,
        component_observer: Optional[ComponentProjectionObserver] = None,
    ) -> CodexTurnRepresentation:
        """Project enabled profile components at one lifecycle exposure.

        Args:
            manifest: Fully resolved component definitions and parameters.
            inputs: Aligned local subjective, derived, predicate, and optional advice data.
            exposure: Lifecycle boundary being rendered.
            component_observer: Optional observational component lifecycle sink.

        Returns:
            Ordered typed representation envelope for the exact local revision.

        Raises:
            ValueError: If the manifest references an unimplemented built-in component.
        """
        started = time.perf_counter()
        generated_at = datetime.now(timezone.utc)
        blocks: list[CodexRepresentationBlock] = []
        omissions: list[ComponentExposureOmission] = []
        envelope_warnings: list[str] = []
        for component in manifest.components:
            if not component.enabled:
                omissions.append(_exposure_omission(component, exposure, "disabled"))
                continue
            if component.exposure is not exposure:
                omissions.append(_exposure_omission(component, exposure, "exposure_mismatch"))
                continue
            builder = self._builders.get(component.spec.component_id)
            block_type = _BLOCK_TYPES.get(component.spec.component_id)
            if builder is None or block_type is None:
                raise ValueError(
                    f"No projector registered for component {component.spec.component_id}"
                )
            component_started = time.perf_counter()
            _notify_component(component_observer, ComponentProjectionEvent(
                phase="started",
                component_id=component.spec.component_id,
                component_version=component.spec.version,
                required=component.spec.required,
            ))
            emitted_ids = tuple(block.component_id for block in blocks)
            try:
                build = builder(inputs, component.parameters, emitted_ids)
            except Exception as exc:
                failure_timing_ms = _elapsed_ms(component_started)
                _notify_component(component_observer, ComponentProjectionEvent(
                    phase="failed",
                    component_id=component.spec.component_id,
                    component_version=component.spec.version,
                    required=component.spec.required,
                    timing_ms=failure_timing_ms,
                    error_type=type(exc).__name__,
                ))
                if component.spec.required:
                    raise RequiredRepresentationComponentError(
                        component.spec.component_id,
                        type(exc).__name__,
                    ) from exc
                error_payload = ComponentErrorPayload(
                    failed_component_id=component.spec.component_id,
                    failed_component_version=component.spec.version,
                    error_type=type(exc).__name__,
                    message="Optional representation component projection failed.",
                    recoverable=True,
                )
                error_block = ComponentErrorBlock(
                    component_version=component.spec.version,
                    role=component.spec.role,
                    transform=component.spec.transform,
                    observation_cursor=inputs.world.observation_cursor,
                    epoch_id=(
                        inputs.world.current_epoch.epoch_id
                        if inputs.world.current_epoch is not None
                        else None
                    ),
                    generated_at=generated_at,
                    payload=error_payload,
                    source_paths=tuple(),
                    omitted_item_count=0,
                    recovery_hints=_recovery_hints(component),
                    timing_ms=failure_timing_ms,
                    payload_bytes=_payload_bytes(error_payload),
                    warnings=(
                        f"Optional component {component.spec.component_id} failed; "
                        "use local recovery paths for source facts.",
                    ),
                )
                blocks.append(error_block)
                envelope_warnings.extend(error_block.warnings)
                continue
            timing_ms = _elapsed_ms(component_started)
            payload_bytes = _payload_bytes(build.payload)
            block = block_type(
                component_id=component.spec.component_id,
                component_version=component.spec.version,
                role=component.spec.role,
                transform=component.spec.transform,
                observation_cursor=inputs.world.observation_cursor,
                epoch_id=(
                    inputs.world.current_epoch.epoch_id
                    if inputs.world.current_epoch is not None
                    else None
                ),
                generated_at=generated_at,
                payload=build.payload,
                source_paths=build.source_paths,
                omitted_item_count=build.omitted_item_count,
                recovery_hints=_recovery_hints(component),
                timing_ms=timing_ms,
                payload_bytes=payload_bytes,
                warnings=build.warnings,
            )
            blocks.append(cast(CodexRepresentationBlock, block))
            _notify_component(component_observer, ComponentProjectionEvent(
                phase="completed",
                component_id=component.spec.component_id,
                component_version=component.spec.version,
                required=component.spec.required,
                timing_ms=timing_ms,
                payload_bytes=payload_bytes,
            ))
            envelope_warnings.extend(
                f"{component.spec.component_id}: {warning}"
                for warning in build.warnings
            )
        epoch = inputs.world.current_epoch
        return CodexTurnRepresentation(
            profile_id=manifest.profile_id,
            profile_version=manifest.profile_version,
            manifest_digest=manifest.manifest_digest,
            exposure=exposure,
            observation_cursor=inputs.world.observation_cursor,
            epoch_id=epoch.epoch_id if epoch is not None else None,
            generated_at=generated_at,
            blocks=tuple(blocks),
            exposure_omissions=tuple(omissions),
            total_timing_ms=_elapsed_ms(started),
            warnings=tuple(envelope_warnings),
        )


def _payload_bytes(payload: BaseModel) -> int:
    """Return canonical JSON byte size for one validated component payload."""
    payload_json = payload.model_dump(mode="json", exclude_none=False)
    return len(
        json.dumps(
            payload_json,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def _notify_component(
    observer: Optional[ComponentProjectionObserver],
    event: ComponentProjectionEvent,
) -> None:
    """Deliver optional telemetry without allowing the sink to affect projection."""
    if observer is None:
        return
    try:
        observer(event)
    except Exception:
        return


def project_codex_representation(
    manifest: ResolvedRepresentationManifest,
    inputs: RepresentationProjectionInput,
    *,
    exposure: ExposureTiming = ExposureTiming.DECISION_EPOCH,
    component_observer: Optional[ComponentProjectionObserver] = None,
) -> CodexTurnRepresentation:
    """Project one representation with the closed built-in projector.

    Args:
        manifest: Fully resolved representation manifest.
        inputs: Aligned local projection inputs.
        exposure: Lifecycle boundary being rendered.
        component_observer: Optional observational component lifecycle sink.

    Returns:
        Typed ordered Codex representation envelope.
    """
    return CodexRepresentationProjector().project(
        manifest,
        inputs,
        exposure=exposure,
        component_observer=component_observer,
    )


def _build_core_revision(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Build exact subjective revision identity without raw source cursors."""
    del parameters, emitted_ids
    world = inputs.world
    encounter = world.encounter
    epoch = world.current_epoch
    return _PayloadBuild(
        payload=CoreRevisionPayload(
            session_id=world.session.session_id,
            encounter_uuid=encounter.uuid if encounter is not None else None,
            observation_cursor=world.observation_cursor,
            epoch_id=epoch.epoch_id if epoch is not None else None,
            epoch_index=epoch.epoch_index if epoch is not None else None,
            active_entity_uuid=world.session.active_entity_uuid,
            actor_uuid=epoch.actor_uuid if epoch is not None else None,
            round_number=encounter.round_number if encounter is not None else None,
            turn_index=encounter.current_turn_index if encounter is not None else None,
            encounter_state=encounter.state if encounter is not None else None,
            is_my_turn=world.session.is_my_turn,
        ),
        source_paths=("/world/session", "/world/encounter", "/world/current_epoch"),
    )


def _build_turn_core(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Build complete controlled-team and action-economy state."""
    del parameters, emitted_ids
    world = inputs.world
    epoch = world.current_epoch
    actor = world.known_entities.get(epoch.actor_uuid) if epoch is not None else None
    controlled = tuple(sorted(
        (entity for entity in world.known_entities.values() if entity.controlled),
        key=lambda entity: entity.uuid,
    ))
    return _PayloadBuild(
        payload=TurnCorePayload(
            encounter=world.encounter,
            actor=actor,
            controlled_entities=controlled,
            economy=epoch.economy if epoch is not None else None,
            is_terminal=world.encounter is not None and world.encounter.state == "ended",
        ),
        source_paths=("/world/encounter", "/world/known_entities", "/world/current_epoch"),
    )


def _build_contacts(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Partition known contacts without inferring unknown relationships."""
    del emitted_ids
    include_remembered_allies = _bool_parameter(parameters, "include_remembered_allies")
    preserve_detail = _bool_parameter(parameters, "preserve_knowledge_detail")
    groups = _partition_contacts(inputs.world)
    remembered_allies = groups[4] if include_remembered_allies else tuple()
    return _PayloadBuild(
        payload=ContactLedgerPayload(
            controlled_entities=groups[0],
            visible_hostiles=groups[1],
            remembered_hostiles=groups[2],
            visible_allies=groups[3],
            remembered_allies=remembered_allies,
            visible_unknown_relationship=groups[5],
            remembered_unknown_relationship=groups[6],
            known_dead_contacts=groups[7],
            unknown_contacts=groups[8],
            knowledge_detail_preserved=preserve_detail,
        ),
        source_paths=("/world/known_entities",),
        omitted_item_count=len(groups[4]) - len(remembered_allies),
    )


def _build_objects(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Build typed object summaries while leaving open state locally inspectable."""
    del emitted_ids
    max_items = _int_parameter(parameters, "max_items")
    include_full_objects = _bool_parameter(parameters, "include_full_objects")
    objects = sorted(inputs.world.known_objects.values(), key=lambda item: item.uuid)
    retained = objects if max_items == 0 else objects[:max_items]
    summaries = tuple(
        KnownObjectSummary(
            uuid=item.uuid,
            name=item.name,
            knowledge_state=item.knowledge_state,
            observer_uuids=tuple(item.observer_uuids),
            position=item.position,
            map_char=item.map_char,
            is_open=(
                item.state.get("is_open")
                if isinstance(item.state.get("is_open"), bool)
                else None
            ),
            state_keys=tuple(sorted(item.state)),
        )
        for item in retained
    )
    warnings = (
        (
            "Object state values are summarized by typed fields and remain available "
            "through local inspection.",
        )
        if any(item.state for item in retained)
        else tuple()
    )
    return _PayloadBuild(
        payload=ObjectLedgerPayload(
            total_known_objects=len(objects),
            objects=summaries,
            complete_objects=tuple(objects) if include_full_objects else None,
        ),
        source_paths=("/world/known_objects",),
        omitted_item_count=len(objects) - len(retained),
        warnings=warnings,
    )


def _build_topology(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Aggregate known topology classes without ranking destinations."""
    del parameters, emitted_ids
    tiles = tuple(inputs.world.known_tiles.values())
    return _PayloadBuild(
        payload=TopologySummaryPayload(
            known_tile_count=len(tiles),
            hazardous_positions=tuple(sorted(
                tile.position for tile in tiles if tile.is_hazardous is True
            )),
            slow_positions=tuple(sorted(
                tile.position
                for tile in tiles
                if tile.walking_cost is not None and tile.walking_cost > 5
            )),
            blocked_positions=tuple(sorted(
                tile.position for tile in tiles if tile.walkable is False
            )),
            vision_blocker_positions=tuple(sorted(
                tile.position
                for tile in tiles
                if any(tile.directional_blocks_vision.values())
            )),
        ),
        source_paths=("/world/known_tiles",),
    )


def _build_spatial_scene(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Build a bounded scene around known entities without choosing destinations."""
    del emitted_ids
    radius = _int_parameter(parameters, "scene_radius")
    include_unknown = _bool_parameter(parameters, "include_unknown_cells")
    anchors = tuple(sorted({
        entity.position
        for entity in inputs.world.known_entities.values()
        if entity.position is not None
    }))

    def inside(position: tuple[int, int]) -> bool:
        return any(
            max(abs(position[0] - anchor[0]), abs(position[1] - anchor[1])) <= radius
            for anchor in anchors
        )

    entities = tuple(sorted(
        (
            entity
            for entity in inputs.world.known_entities.values()
            if entity.position is not None and inside(entity.position)
        ),
        key=lambda entity: entity.uuid,
    ))
    objects = tuple(sorted(
        (
            item
            for item in inputs.world.known_objects.values()
            if item.position is not None and inside(item.position)
        ),
        key=lambda item: item.uuid,
    ))
    known_tiles = tuple(sorted(
        (tile for tile in inputs.world.known_tiles.values() if inside(tile.position)),
        key=lambda tile: tile.position,
    ))
    unknown_positions: tuple[tuple[int, int], ...] = tuple()
    if include_unknown and anchors:
        known_positions = {tile.position for tile in known_tiles}
        candidate_positions = {
            (x, y)
            for anchor_x, anchor_y in anchors
            for x in range(anchor_x - radius, anchor_x + radius + 1)
            for y in range(anchor_y - radius, anchor_y + radius + 1)
        }
        unknown_positions = tuple(sorted(candidate_positions - known_positions))
    omitted_tiles = len(inputs.world.known_tiles) - len(known_tiles)
    return _PayloadBuild(
        payload=SpatialScenePayload(
            radius=radius,
            anchor_positions=anchors,
            entities=entities,
            objects=objects,
            known_tiles=known_tiles,
            unknown_positions=unknown_positions,
        ),
        source_paths=(
            "/world/known_entities",
            "/world/known_objects",
            "/world/known_tiles",
        ),
        omitted_item_count=omitted_tiles,
    )


def _build_actions(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Preserve complete legal rows and add only neutral deterministic indexes."""
    del emitted_ids
    epoch = inputs.world.current_epoch
    if epoch is None:
        return _PayloadBuild(
            payload=ActionFamilyPayload(
                epoch_id=None,
                actor_uuid=None,
                economy=None,
                complete_affordances=None,
                total_rows=0,
                affordable_rows=0,
            ),
            source_paths=("/world/current_epoch",),
            warnings=("No controlled decision epoch supplies legal affordances.",),
        )
    rows = tuple(epoch.affordances.all_rows)
    rows_by_bucket = tuple(
        (bucket, sum(1 for row in rows if row.bucket == bucket))
        for bucket in _ACTION_BUCKET_ORDER
    )
    tag_counts: dict[str, int] = {}
    family_rows: dict[str, list[ActionAffordance]] = {}
    family_tags: dict[str, set[str]] = {}
    for row in rows:
        semantics = epoch.affordances.semantics_for(row)
        for tag in semantics.tags:
            tag_counts[tag.value] = tag_counts.get(tag.value, 0) + 1
        key = row.source_action_id
        family_rows.setdefault(key, []).append(row)
        family_tags.setdefault(key, set()).update(tag.value for tag in semantics.tags)
    all_families = tuple(
        ActionFamilySummary(
            source_action_id=key,
            semantic_key=grouped_rows[0].semantic_key,
            template_name=grouped_rows[0].template_name,
            base_template_name=grouped_rows[0].base_template_name,
            display_name=grouped_rows[0].display_name,
            semantic_id=grouped_rows[0].semantic_id,
            semantics_ref=grouped_rows[0].semantics_ref,
            semantic_provenance=epoch.affordances.semantics_for(grouped_rows[0]).provenance,
            bucket=grouped_rows[0].bucket,
            action_category=grouped_rows[0].action_category,
            target_type=grouped_rows[0].target_type,
            row_count=len(grouped_rows),
            direct_row_id=grouped_rows[0].row_id if len(grouped_rows) == 1 else None,
            affordable_row_count=sum(1 for row in grouped_rows if row.can_afford),
            cost=grouped_rows[0].cost,
            target_option_count=len(grouped_rows[0].target_options),
            allocation_count=grouped_rows[0].num_projectiles,
            allow_same_target=grouped_rows[0].allow_same_target,
            spell_level=grouped_rows[0].spell_level,
            cast_at_level=grouped_rows[0].cast_at_level,
            requires_concentration=grouped_rows[0].requires_concentration,
            tags=tuple(sorted(family_tags[key])),
        )
        for key, grouped_rows in family_rows.items()
    )
    provenance_counts = {
        kind: sum(
            1
            for family in all_families
            if family.semantic_provenance.kind is kind
        )
        for kind in SemanticProvenanceKind
    }
    family_limit = _int_parameter(parameters, "family_limit")
    families = all_families if family_limit == 0 else all_families[:family_limit]
    multi_rows = tuple(_multi_target_summary(row) for row in rows if _is_multi_target(row))
    multi_limit = _int_parameter(parameters, "multi_target_row_limit")
    retained_multi = multi_rows if multi_limit == 0 else multi_rows[:multi_limit]
    include_full_rows = _bool_parameter(parameters, "include_full_rows")
    expanded_rows = rows if include_full_rows else tuple()
    all_capabilities = tuple(epoch.affordances.capabilities)
    semantic_coverage = ActionSemanticCoverage(
        source_action_count=len(all_families),
        exact_count=provenance_counts[SemanticProvenanceKind.EXACT],
        structured_profile_count=provenance_counts[SemanticProvenanceKind.STRUCTURED_PROFILE],
        category_fallback_count=provenance_counts[SemanticProvenanceKind.CATEGORY_FALLBACK],
        unknown_count=provenance_counts[SemanticProvenanceKind.UNKNOWN],
        unknown_semantic_keys=tuple(sorted({
            family.semantic_key
            for family in all_families
            if family.semantic_provenance.kind is SemanticProvenanceKind.UNKNOWN
        })),
        capability_count=len(all_capabilities),
        unknown_capability_count=sum(
            capability.semantic_id == "action.unknown"
            for capability in all_capabilities
        ),
        unknown_capability_semantic_keys=tuple(sorted({
            capability.semantic_key
            for capability in all_capabilities
            if capability.semantic_id == "action.unknown"
        })),
    )
    capability_limit = _int_parameter(parameters, "capability_limit")
    retained_capabilities = (
        all_capabilities
        if capability_limit == 0
        else all_capabilities[:capability_limit]
    )
    capabilities = tuple(
        ActionCapabilitySummary(
            capability_id=capability.capability_id,
            semantic_key=capability.semantic_key,
            action_category=capability.action_category,
            target_type=capability.target_type,
            cost=capability.cost,
            range_type=capability.range_type,
            normal_range_feet=capability.normal_range_feet,
            long_range_feet=capability.long_range_feet,
            requires_line_of_sight=capability.requires_line_of_sight,
            valid_target_filter=capability.valid_target_filter,
            weapon_slot=capability.weapon_slot,
            base_spell_level=capability.base_spell_level,
            cast_at_level=capability.cast_at_level,
            source_item_uuid=capability.source_item_uuid,
            semantic_id=capability.semantic_id,
            semantics_ref=capability.semantics_ref,
            tags=tuple(capability.tags),
        )
        for capability in retained_capabilities
    )
    omitted_automatic_rows = len(rows) - len(expanded_rows)
    omitted_multi_rows = len(multi_rows) - len(retained_multi)
    omitted_families = len(all_families) - len(families)
    omitted_capabilities = len(all_capabilities) - len(capabilities)
    return _PayloadBuild(
        payload=ActionFamilyPayload(
            epoch_id=epoch.epoch_id,
            actor_uuid=epoch.actor_uuid,
            economy=epoch.economy,
            complete_affordances=epoch.affordances if include_full_rows else None,
            total_rows=len(rows),
            affordable_rows=sum(1 for row in rows if row.can_afford),
            semantic_coverage=semantic_coverage,
            rows_by_bucket=rows_by_bucket,
            rows_by_tag=tuple(sorted(tag_counts.items())),
            total_family_count=len(all_families),
            omitted_family_count=omitted_families,
            families=families,
            multi_target_rows=retained_multi,
            automatically_expanded_rows=expanded_rows,
            capabilities=capabilities,
            total_capability_count=len(all_capabilities),
            omitted_capability_count=omitted_capabilities,
        ),
        source_paths=("/world/current_epoch",),
        omitted_item_count=(
            omitted_automatic_rows
            + omitted_multi_rows
            + omitted_families
            + omitted_capabilities
        ),
    )


def _build_recent_logs(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Build the compatibility bounded recent subjective-log view."""
    del emitted_ids
    log_limit = _int_parameter(parameters, "log_limit")
    child_limit = _int_parameter(parameters, "child_limit")
    rows = inputs.world.combat_logs
    retained = rows[-log_limit:]
    return _PayloadBuild(
        payload=RecentCombatLogsPayload(
            source_log_count=len(rows),
            logs=tuple(_combat_log_summary(row, child_limit=child_limit) for row in retained),
        ),
        source_paths=("/world/combat_logs",),
        omitted_item_count=len(rows) - len(retained),
    )


def _build_decision_delta(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Build typed additions, removals, and replacements from a prior boundary."""
    del parameters, emitted_ids
    current = inputs.world
    previous = inputs.previous_world
    frames = tuple(
        frame
        for frame in inputs.observation_frames
        if frame.observation_cursor <= current.observation_cursor
    )
    frame_summaries = tuple(_subjective_frame_summary(frame) for frame in frames)
    if previous is None:
        return _PayloadBuild(
            payload=DecisionDeltaPayload(
                baseline=True,
                to_observation_cursor=current.observation_cursor,
                to_epoch_id=(
                    current.current_epoch.epoch_id
                    if current.current_epoch is not None
                    else None
                ),
                session_changed=False,
                encounter_changed=False,
                subjective_frames=frame_summaries,
            ),
            source_paths=("/observation_frames", "/world"),
            warnings=("No prior decision boundary was supplied; this delta is a baseline.",),
        )
    frame_cursors = tuple(frame.observation_cursor for frame in frames)
    expected_cursors = tuple(range(previous.observation_cursor + 1, current.observation_cursor + 1))
    history_gap = frame_cursors != expected_cursors
    entities = tuple(
        EntityRevisionChange(
            entity_uuid=key,
            before=previous.known_entities.get(key),
            after=current.known_entities.get(key),
        )
        for key in sorted(set(previous.known_entities) | set(current.known_entities))
        if previous.known_entities.get(key) != current.known_entities.get(key)
    )
    objects = tuple(
        ObjectRevisionChange(
            object_uuid=key,
            before=previous.known_objects.get(key),
            after=current.known_objects.get(key),
        )
        for key in sorted(set(previous.known_objects) | set(current.known_objects))
        if previous.known_objects.get(key) != current.known_objects.get(key)
    )
    tiles = tuple(
        TileRevisionChange(
            tile_key=key,
            before=previous.known_tiles.get(key),
            after=current.known_tiles.get(key),
        )
        for key in sorted(set(previous.known_tiles) | set(current.known_tiles))
        if previous.known_tiles.get(key) != current.known_tiles.get(key)
    )
    common_log_count = _common_prefix_length(previous.combat_logs, current.combat_logs)
    new_logs = tuple(
        _combat_log_summary(row, child_limit=0)
        for row in current.combat_logs[common_log_count:]
    )
    return _PayloadBuild(
        payload=DecisionDeltaPayload(
            baseline=False,
            history_gap=history_gap,
            used_state_diff_fallback=history_gap,
            from_observation_cursor=previous.observation_cursor,
            to_observation_cursor=current.observation_cursor,
            from_epoch_id=(
                previous.current_epoch.epoch_id
                if previous.current_epoch is not None
                else None
            ),
            to_epoch_id=(
                current.current_epoch.epoch_id
                if current.current_epoch is not None
                else None
            ),
            session_changed=previous.session != current.session,
            encounter_changed=previous.encounter != current.encounter,
            entities=entities,
            objects=objects,
            tiles=tiles,
            new_combat_logs=new_logs,
            subjective_frames=frame_summaries,
        ),
        source_paths=("/observation_frames", "/world"),
        warnings=(
            ("Subjective envelope history is incomplete; final-state changes supplement the delta.",)
            if history_gap
            else tuple()
        ),
    )


def _subjective_frame_summary(frame: ObservationFrame) -> SubjectiveFrameSummary:
    """Reduce one retained envelope without losing causal identity or order."""
    return SubjectiveFrameSummary(
        observation_cursor=frame.observation_cursor,
        frame_type=frame.frame_type.value,
        source_kind=frame.source_kind.value if frame.source_kind is not None else None,
        source_command_id=frame.source_command_id,
        event_type=frame.event_type,
        event_uuid=frame.event_uuid,
        lineage_uuid=frame.lineage_uuid,
        phase=frame.phase,
        patch_types=tuple(patch.patch_type.value for patch in frame.patches),
        entity_uuids=tuple(
            dict.fromkeys(
                patch.entity_uuid for patch in frame.patches if patch.entity_uuid is not None
            )
        ),
        object_uuids=tuple(
            dict.fromkeys(
                patch.object_uuid for patch in frame.patches if patch.object_uuid is not None
            )
        ),
        tile_keys=tuple(
            dict.fromkeys(
                patch.tile_key for patch in frame.patches if patch.tile_key is not None
            )
        ),
        has_combat_log=frame.combat_log is not None,
        command_status=(
            frame.command_result.status.value
            if frame.command_result is not None
            else None
        ),
        decision_epoch_id=(
            frame.decision_epoch.epoch_id
            if frame.decision_epoch is not None
            else None
        ),
    )


def _build_combat_hypotheses(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Expose current subjective combat hypotheses without adding inference."""
    del emitted_ids
    facts = inputs.agent_state.facts
    if facts is None:
        return _PayloadBuild(
            payload=CombatHypothesisPayload(source_log_count=0),
            source_paths=("/agent_state/facts/combat_memory",),
            warnings=("AgentFacts are unavailable for this subjective revision.",),
        )
    hypotheses = facts.combat_memory.hypotheses
    changed_only = _bool_parameter(parameters, "changed_only")
    if changed_only:
        previous_facts = (
            inputs.previous_agent_state.facts
            if inputs.previous_agent_state is not None
            else None
        )
        previous_by_key = (
            previous_facts.combat_memory.by_target_effect
            if previous_facts is not None
            else {}
        )
        retained = tuple(
            hypothesis
            for hypothesis in hypotheses
            if previous_by_key.get(
                _hypothesis_key(hypothesis.target_uuid, hypothesis.effect_id)
            ) != hypothesis
        )
    else:
        retained = hypotheses
    return _PayloadBuild(
        payload=CombatHypothesisPayload(
            source_log_count=facts.combat_memory.source_log_count,
            hypotheses=retained,
        ),
        source_paths=("/agent_state/facts/combat_memory",),
        omitted_item_count=len(hypotheses) - len(retained),
    )


def _build_predicates(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Apply automatic focus without deleting the complete local ledger."""
    del emitted_ids
    snapshot = inputs.predicate_snapshot
    if snapshot is None:
        return _PayloadBuild(
            payload=PredicateFocusPayload(
                complete_fact_count=0,
                complete_predicate_count=0,
            ),
            source_paths=("/predicates",),
            warnings=("No predicate ledger snapshot was supplied.",),
        )
    include_changed = _bool_parameter(parameters, "include_changed")
    limit = _int_parameter(parameters, "max_automatic_items")
    selected: list = list(snapshot.focus.selected) if snapshot.focus is not None else []
    selected_ids = {evaluation.predicate_id for evaluation in selected}
    if include_changed:
        for evaluation in snapshot.predicates:
            if evaluation.changed and evaluation.predicate_id not in selected_ids:
                selected.append(evaluation)
                selected_ids.add(evaluation.predicate_id)
    selected = selected[:limit]
    changed_facts = tuple(
        observation for observation in snapshot.facts if include_changed and observation.changed
    )[:limit]
    return _PayloadBuild(
        payload=PredicateFocusPayload(
            facts=changed_facts,
            predicates=tuple(selected),
            complete_fact_count=len(snapshot.facts),
            complete_predicate_count=len(snapshot.predicates),
        ),
        source_paths=("/predicates",),
        omitted_item_count=(
            len(snapshot.facts)
            + len(snapshot.predicates)
            - len(changed_facts)
            - len(selected)
        ),
    )


def _build_warnings(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Reproduce current interface warnings as stable typed attention facts."""
    del parameters, emitted_ids
    world = inputs.world
    groups = _partition_contacts(world)
    warnings: list[RepresentationWarning] = []
    if (
        world.current_epoch is None
        and world.encounter is not None
        and world.encounter.state != "ended"
    ):
        warnings.append(RepresentationWarning(
            code="control.no_active_epoch",
            message="No controlled decision epoch is active.",
            evidence_refs=("/world/current_epoch", "/world/encounter/state"),
        ))
    if groups[2] and not groups[1]:
        warnings.append(RepresentationWarning(
            code="contacts.remembered_only",
            message="No hostile is currently visible; remembered positions are last-known facts.",
            evidence_refs=("/world/known_entities",),
        ))
    return _PayloadBuild(
        payload=WarningPayload(warnings=tuple(warnings)),
        source_paths=("/world/current_epoch", "/world/encounter", "/world/known_entities"),
    )


def _build_advice(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Project only caller-supplied policy data at the profile-selected detail."""
    del emitted_ids
    detail = _string_parameter(parameters, "detail")
    if detail not in {"selected_only", "ranked", "full_trace"}:
        raise ValueError(f"Unsupported policy detail {detail}")
    advice = inputs.policy_advice
    if advice is None:
        return _PayloadBuild(
            payload=AdvicePayload(
                available=False,
                detail=cast(_PolicyDetail, detail),
            ),
            source_paths=("/policy_oracle",),
            warnings=("No policy oracle result was supplied; projection did not invoke one.",),
        )
    candidates = advice.candidates if detail in {"ranked", "full_trace"} else tuple()
    trace = advice.trace if detail == "full_trace" else tuple()
    return _PayloadBuild(
        payload=AdvicePayload(
            available=advice.available,
            detail=cast(_PolicyDetail, detail),
            basis=advice.basis,
            evaluation_ms=advice.evaluation_ms,
            unavailable_reason=advice.unavailable_reason,
            selected=advice.selected,
            candidates=candidates,
            trace=trace,
        ),
        source_paths=("/policy_oracle",),
        omitted_item_count=(
            len(advice.candidates)
            - len(candidates)
            + len(advice.trace)
            - len(trace)
        ),
    )


def _build_runtime_telemetry(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Copy optional observational telemetry without deriving gameplay state."""
    del parameters, emitted_ids
    return _PayloadBuild(
        payload=RepresentationTelemetryPayload(
            supplied=inputs.runtime_telemetry is not None,
            telemetry=inputs.runtime_telemetry,
        ),
        source_paths=("/runtime_telemetry",),
        warnings=(
            ("No runtime telemetry was supplied.",)
            if inputs.runtime_telemetry is None
            else tuple()
        ),
    )


def _build_encounter_summary(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Aggregate conservative match statistics from subjective evidence."""
    del parameters, emitted_ids
    world = inputs.world
    encounter = world.encounter
    controlled = tuple(sorted(
        (entity for entity in world.known_entities.values() if entity.controlled),
        key=lambda entity: entity.uuid,
    ))
    controlled_ids = {entity.uuid for entity in controlled}
    surviving_controlled = tuple(
        entity.uuid for entity in controlled if entity.is_dead is not True
    )
    defeated_controlled = tuple(
        entity.uuid for entity in controlled if entity.is_dead is True
    )
    controlled_factions = {
        entity.faction for entity in controlled if entity.faction is not None
    }
    hostile_deaths = tuple(sorted(
        entity.uuid
        for entity in world.known_entities.values()
        if not entity.controlled
        and entity.is_dead is True
        and entity.faction is not None
        and bool(controlled_factions)
        and entity.faction not in controlled_factions
    ))
    ended = encounter is not None and encounter.state == "ended"
    if not ended:
        outcome: Literal[
            "ongoing",
            "controlled_survived",
            "controlled_defeated",
            "mixed_or_unknown",
        ] = "ongoing"
    elif controlled and len(defeated_controlled) == len(controlled):
        outcome = "controlled_defeated"
    elif surviving_controlled:
        outcome = "controlled_survived"
    else:
        outcome = "mixed_or_unknown"

    subjective_winning_faction: Optional[str] = None
    winner_basis: Literal[
        "ongoing",
        "controlled_survival",
        "known_survivor",
        "unknown",
    ]
    if not ended:
        winner_basis = "ongoing"
    elif outcome == "controlled_survived" and len(controlled_factions) == 1:
        subjective_winning_faction = next(iter(controlled_factions))
        winner_basis = "controlled_survival"
    elif outcome == "controlled_defeated":
        known_survivor_factions = {
            entity.faction
            for entity in world.known_entities.values()
            if not entity.controlled
            and entity.is_dead is False
            and entity.faction is not None
        }
        if len(known_survivor_factions) == 1:
            subjective_winning_faction = next(iter(known_survivor_factions))
            winner_basis = "known_survivor"
        else:
            winner_basis = "unknown"
    else:
        winner_basis = "unknown"

    flattened_logs = tuple(_flatten_combat_logs(world.combat_logs))
    event_counts: dict[str, int] = {}
    observed_damage_dealt = 0
    observed_damage_taken = 0
    observed_healing_received = 0
    turn_starts = 0
    for row in flattened_logs:
        entry_type = row.get("entry_type") or row.get("type")
        if isinstance(entry_type, str):
            event_counts[entry_type] = event_counts.get(entry_type, 0) + 1
            if entry_type == "turn_start":
                turn_starts += 1
        data = row.get("data")
        structured = data if isinstance(data, dict) else {}
        if entry_type == "damage_taken":
            damage = structured.get("damage")
            amount = damage if isinstance(damage, int) and not isinstance(damage, bool) else 0
            source_uuid = row.get("source_uuid")
            target_uuid = row.get("target_uuid")
            if source_uuid in controlled_ids:
                observed_damage_dealt += max(0, amount)
            if target_uuid in controlled_ids:
                observed_damage_taken += max(0, amount)
        elif entry_type == "heal":
            amount_value = structured.get("amount")
            amount = (
                amount_value
                if isinstance(amount_value, int) and not isinstance(amount_value, bool)
                else 0
            )
            target_uuid = structured.get("entity_uuid") or row.get("target_uuid") or row.get("source_uuid")
            if target_uuid in controlled_ids:
                observed_healing_received += max(0, amount)

    telemetry = inputs.runtime_telemetry
    predicate_count = (
        len(inputs.predicate_snapshot.predicates)
        if inputs.predicate_snapshot is not None
        else 0
    )
    incomplete = [
        "resources_spent",
        "temporary_hp_gained",
        "condition_names",
        "unperceived_events",
    ]
    if not controlled_factions:
        incomplete.append("hostile_relationships")
    return _PayloadBuild(
        payload=EncounterSummaryPayload(
            available=ended,
            outcome=outcome,
            subjective_winning_faction=subjective_winning_faction,
            winner_basis=winner_basis,
            rounds_observed=max(0, encounter.round_number if encounter is not None else 0),
            turn_starts_observed=turn_starts,
            surviving_controlled_entity_uuids=surviving_controlled,
            defeated_controlled_entity_uuids=defeated_controlled,
            known_hostile_death_uuids=hostile_deaths,
            observed_damage_dealt=observed_damage_dealt,
            observed_damage_taken=observed_damage_taken,
            observed_healing_received=observed_healing_received,
            observed_conditions_applied=tuple(),
            observed_event_families=tuple(sorted(event_counts.items())),
            command_count=telemetry.command_count if telemetry is not None else 0,
            inspection_count=telemetry.inspection_count if telemetry is not None else 0,
            predicate_count=predicate_count,
            incomplete_statistics=tuple(incomplete),
        ),
        source_paths=(
            "/world/encounter",
            "/world/known_entities",
            "/world/combat_logs",
            "/predicates",
            "/runtime_telemetry",
        ),
        warnings=(
            (
                "Encounter statistics are subjective and explicitly incomplete; no "
                "objective post-match reveal was used."
            ),
        ),
    )


def _build_presentation(
    inputs: RepresentationProjectionInput,
    parameters: Mapping[str, JsonValue],
    emitted_ids: tuple[str, ...],
) -> _PayloadBuild:
    """Mark the preceding validated blocks as canonical typed JSON."""
    del inputs, parameters
    return _PayloadBuild(
        payload=TypedJsonPresentationPayload(emitted_component_ids=emitted_ids),
        source_paths=("/representation/blocks",),
    )


def _flatten_combat_logs(rows: Sequence[dict[str, object]]) -> Sequence[dict[str, object]]:
    """Return deterministic depth-first subjective log rows without mutation."""
    flattened: list[dict[str, object]] = []
    stack = list(reversed(rows))
    while stack:
        row = stack.pop()
        flattened.append(row)
        children = row.get("sub_entries")
        if isinstance(children, (list, tuple)):
            stack.extend(
                reversed([child for child in children if isinstance(child, dict)])
            )
    return flattened


def _partition_contacts(
    world: SubjectiveWorldState,
) -> tuple[
    tuple[ObservationEntityFact, ...],
    tuple[ObservationEntityFact, ...],
    tuple[ObservationEntityFact, ...],
    tuple[ObservationEntityFact, ...],
    tuple[ObservationEntityFact, ...],
    tuple[ObservationEntityFact, ...],
    tuple[ObservationEntityFact, ...],
    tuple[ObservationEntityFact, ...],
    tuple[ObservationEntityFact, ...],
]:
    """Return stable contact groups without turning unknown faction into hostility."""
    epoch = world.current_epoch
    actor = world.known_entities.get(epoch.actor_uuid) if epoch is not None else None
    actor_faction = actor.faction if actor is not None else None
    buckets: list[list[ObservationEntityFact]] = [[] for _ in range(9)]
    for entity in sorted(world.known_entities.values(), key=lambda item: item.uuid):
        if entity.controlled:
            buckets[0].append(entity)
            continue
        if entity.is_dead is True:
            buckets[7].append(entity)
            continue
        visible = entity.knowledge_state is KnowledgeState.VISIBLE
        remembered = entity.knowledge_state in {KnowledgeState.SEEN, KnowledgeState.REMEMBERED}
        if entity.knowledge_state is KnowledgeState.UNKNOWN:
            buckets[8].append(entity)
            continue
        relationship_known = actor_faction is not None and entity.faction is not None
        if not relationship_known:
            if visible:
                buckets[5].append(entity)
            elif remembered:
                buckets[6].append(entity)
            else:
                buckets[8].append(entity)
        elif entity.faction == actor_faction:
            if visible:
                buckets[3].append(entity)
            elif remembered:
                buckets[4].append(entity)
        elif visible:
            buckets[1].append(entity)
        elif remembered:
            buckets[2].append(entity)
    return (
        tuple(buckets[0]),
        tuple(buckets[1]),
        tuple(buckets[2]),
        tuple(buckets[3]),
        tuple(buckets[4]),
        tuple(buckets[5]),
        tuple(buckets[6]),
        tuple(buckets[7]),
        tuple(buckets[8]),
    )


def _is_multi_target(row: ActionAffordance) -> bool:
    """Return whether a row exposes a multi-target allocation contract."""
    return (
        (row.num_projectiles is not None and row.num_projectiles > 1)
        or row.allow_same_target is not None
        or row.target_type == "multi_entity"
    )


def _multi_target_summary(row: ActionAffordance) -> MultiTargetActionSummary:
    """Build one neutral multi-target allocation summary."""
    primary = row.targets[0] if row.targets else None
    extra_slots = (
        max(0, row.num_projectiles - len(row.targets))
        if row.num_projectiles is not None
        else None
    )
    return MultiTargetActionSummary(
        row_id=row.row_id,
        display_name=row.display_name,
        semantic_id=row.semantic_id,
        primary_target_uuid=primary.target_uuid if primary is not None else None,
        primary_target_name=primary.target_name if primary is not None else None,
        selectable_target_count=len(row.target_options),
        allocation_count=row.num_projectiles,
        extra_target_slots=extra_slots,
        allow_same_target=row.allow_same_target,
    )


def _combat_log_summary(
    row: Mapping[str, object],
    *,
    child_limit: int,
) -> CombatLogSummary:
    """Convert one already-subjective open log row into a closed typed summary."""
    raw_children = row.get("sub_entries", ())
    child_rows: Sequence[object] = (
        raw_children
        if isinstance(raw_children, Sequence)
        and not isinstance(raw_children, (str, bytes))
        else tuple()
    )
    children = tuple(
        child for child in child_rows if isinstance(child, Mapping)
    )
    retained = children[:child_limit]
    return CombatLogSummary(
        entry_type=_log_text(row, "entry_type", "type"),
        source_name=_log_text(row, "source_name"),
        source_uuid=_log_text(row, "source_uuid"),
        target_name=_log_text(row, "target_name"),
        target_uuid=_log_text(row, "target_uuid"),
        compact=_log_text(row, "compact"),
        verbose=_log_text(row, "verbose"),
        success=_log_bool(row, "success"),
        sub_entries=tuple(
            CombatLogChildSummary(
                entry_type=_log_text(child, "entry_type", "type"),
                source_name=_log_text(child, "source_name"),
                source_uuid=_log_text(child, "source_uuid"),
                target_name=_log_text(child, "target_name"),
                target_uuid=_log_text(child, "target_uuid"),
                compact=_log_text(child, "compact"),
                success=_log_bool(child, "success"),
            )
            for child in retained
        ),
        omitted_sub_entry_count=len(children) - len(retained),
    )


def _log_text(row: Mapping[str, object], *keys: str) -> Optional[str]:
    """Return the first present text value from a subjective log row."""
    for key in keys:
        value = row.get(key)
        if value is not None:
            return str(value)
    return None


def _log_bool(row: Mapping[str, object], key: str) -> Optional[bool]:
    """Return one boolean log value without coercion."""
    value = row.get(key)
    return value if isinstance(value, bool) else None


def _common_prefix_length(
    before: Sequence[Mapping[str, object]],
    after: Sequence[Mapping[str, object]],
) -> int:
    """Return the exact common subjective-log prefix length."""
    count = 0
    for left, right in zip(before, after):
        if left != right:
            break
        count += 1
    return count


def _hypothesis_key(target_uuid: str, effect_id: str) -> str:
    """Build the collision-safe combat-memory lookup key."""
    return f"{len(target_uuid)}:{target_uuid}{effect_id}"


def _recovery_hints(
    component: ResolvedRepresentationComponent,
) -> tuple[RecoveryInstruction, ...]:
    """Translate semantic recovery declarations into local typed operations."""
    endpoints = {
        Recoverability.LOCAL_GET: (
            "/v1/inspect/get",
            "Read exact canonical JSON pointers from the retained local revision.",
        ),
        Recoverability.LOCAL_SELECT: (
            "/v1/query",
            "Select typed subjective entities, objects, tiles, rows, or logs locally.",
        ),
        Recoverability.LOCAL_SEARCH: (
            "/v1/inspect/search",
            "Search bounded canonical local JSON without server access.",
        ),
        Recoverability.LOCAL_EXPORT: (
            "/v1/inspect/export",
            "Export the complete immutable canonical local revision.",
        ),
    }
    return tuple(
        RecoveryInstruction(
            method=method,
            endpoint=endpoints[method][0],
            description=endpoints[method][1],
        )
        for method in component.spec.omission_contract.recoverability
        if method in endpoints
    )


def _exposure_omission(
    component: ResolvedRepresentationComponent,
    requested: ExposureTiming,
    reason: str,
) -> ComponentExposureOmission:
    """Build one typed exposure omission record."""
    return ComponentExposureOmission(
        component_id=component.spec.component_id,
        configured_exposure=component.exposure,
        requested_exposure=requested,
        reason=cast(_ExposureOmissionReason, reason),
    )


def _bool_parameter(parameters: Mapping[str, JsonValue], key: str) -> bool:
    """Read one already-resolved boolean component parameter."""
    value = parameters[key]
    if not isinstance(value, bool):
        raise ValueError(f"Resolved parameter {key} is not boolean")
    return value


def _int_parameter(parameters: Mapping[str, JsonValue], key: str) -> int:
    """Read one already-resolved integer component parameter."""
    value = parameters[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Resolved parameter {key} is not an integer")
    return value


def _string_parameter(parameters: Mapping[str, JsonValue], key: str) -> str:
    """Read one already-resolved string component parameter."""
    value = parameters[key]
    if not isinstance(value, str):
        raise ValueError(f"Resolved parameter {key} is not a string")
    return value


def _elapsed_ms(started: float) -> float:
    """Return a finite non-negative local duration in milliseconds."""
    return max(0.0, (time.perf_counter() - started) * 1000.0)
