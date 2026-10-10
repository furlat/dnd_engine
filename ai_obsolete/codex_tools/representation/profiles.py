"""Built-in Codex representation component and profile definitions."""

from __future__ import annotations

from pydantic import JsonValue

from ai.codex_tools.representation.models import (
    ExposureTiming,
    InformationTransform,
    OmissionContract,
    ParameterValueType,
    Recoverability,
    RepresentationCompatibility,
    RepresentationComponentSelection,
    RepresentationComponentSpec,
    RepresentationInputDomain,
    RepresentationParameterSpec,
    RepresentationProfile,
    RepresentationRole,
    SemanticIntent,
    SubjectivityContract,
)
from ai.codex_tools.representation.registry import RepresentationRegistry


CURRENT_V1_PROFILE_ID = "codex.current-v1"
BALANCED_V2_PROFILE_ID = "codex.balanced-v2"
_VERSION = "1.0.0"
_SUBJECTIVE = SubjectivityContract(
    description=(
        "Reads only the session-subjective local materialization and preserves explicit "
        "knowledge-state distinctions unless the omission contract says otherwise."
    )
)
_AUTOMATIC_EXPOSURES = (
    ExposureTiming.BOOTSTRAP,
    ExposureTiming.DECISION_EPOCH,
    ExposureTiming.AFTER_ACTION,
    ExposureTiming.AFTER_RESULT,
    ExposureTiming.END_TURN,
    ExposureTiming.END_ENCOUNTER,
    ExposureTiming.ON_DEMAND,
)


def _parameter(
    parameter_id: str,
    value_type: ParameterValueType,
    description: str,
    default_value: JsonValue,
    *,
    minimum: float | None = None,
    allowed_values: tuple[JsonValue, ...] = (),
) -> RepresentationParameterSpec:
    """Build one typed optional parameter with an explicit default."""
    return RepresentationParameterSpec(
        parameter_id=parameter_id,
        value_type=value_type,
        description=description,
        has_default=True,
        default_value=default_value,
        minimum=minimum,
        allowed_values=allowed_values,
    )


def _lossless(*domains: RepresentationInputDomain) -> OmissionContract:
    """Build an omission contract for a lossless component."""
    return OmissionContract(
        source_domains=domains,
        recoverability=(Recoverability.NOT_APPLICABLE,),
        rationale="The component preserves its selected source information without omission.",
    )


def _lossy(
    *domains: RepresentationInputDomain,
    omitted_paths: tuple[str, ...],
    filtering_predicate: str | None = None,
    ordering_rule: str | None = None,
    item_limit: int | None = None,
    depth_limit: int | None = None,
    omitted_counts_reported: bool = True,
    recoverability: tuple[Recoverability, ...] = (
        Recoverability.LOCAL_SELECT,
        Recoverability.LOCAL_EXPORT,
    ),
    rationale: str,
) -> OmissionContract:
    """Build an explicit recoverable omission contract."""
    return OmissionContract(
        source_domains=domains,
        omitted_paths=omitted_paths,
        filtering_predicate=filtering_predicate,
        ordering_rule=ordering_rule,
        item_limit=item_limit,
        depth_limit=depth_limit,
        omitted_counts_reported=omitted_counts_reported,
        recoverability=recoverability,
        rationale=rationale,
    )


BUILTIN_COMPONENT_SPECS = (
    RepresentationComponentSpec(
        component_id="core.revision",
        version=_VERSION,
        title="Subjective revision",
        description="Select runtime, session, cursor, epoch, and active actor identity.",
        role=RepresentationRole.STATE_SELECTION,
        semantic_intent=SemanticIntent.PRESERVE_REVISION_IDENTITY,
        input_domains=(
            RepresentationInputDomain.REVISION,
            RepresentationInputDomain.SESSION,
            RepresentationInputDomain.ENCOUNTER,
            RepresentationInputDomain.DECISION_EPOCH,
        ),
        output_model="codex.representation.CoreRevisionBlock",
        transform=InformationTransform.SELECT,
        omission_contract=_lossy(
            RepresentationInputDomain.REVISION,
            omitted_paths=("world.source_event_cursor", "world.source_combat_log_cursor"),
            recoverability=(Recoverability.LOCAL_GET, Recoverability.LOCAL_EXPORT),
            rationale="Automatic context needs decision identity but not source-stream debugging cursors.",
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        required=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=_AUTOMATIC_EXPOSURES,
        implementation_ref="ai.codex_tools.representation.components.CoreRevisionComponent",
    ),
    RepresentationComponentSpec(
        component_id="core.turn",
        version=_VERSION,
        title="Complete turn core",
        description="Preserve encounter turn state, actor facts, economy, resources, and controlled team.",
        role=RepresentationRole.STATE_SELECTION,
        semantic_intent=SemanticIntent.PRESERVE_TURN_STATE,
        input_domains=(
            RepresentationInputDomain.ENCOUNTER,
            RepresentationInputDomain.KNOWN_ENTITIES,
            RepresentationInputDomain.DECISION_EPOCH,
        ),
        output_model="codex.representation.TurnCoreBlock",
        transform=InformationTransform.SELECT,
        omission_contract=_lossless(
            RepresentationInputDomain.ENCOUNTER,
            RepresentationInputDomain.KNOWN_ENTITIES,
            RepresentationInputDomain.DECISION_EPOCH,
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        required=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=_AUTOMATIC_EXPOSURES,
        implementation_ref="ai.codex_tools.representation.components.TurnCoreComponent",
    ),
    RepresentationComponentSpec(
        component_id="contacts.partition",
        version=_VERSION,
        title="Contact knowledge partition",
        description="Partition contacts by control, visibility, memory, relationship, and death knowledge.",
        role=RepresentationRole.DETERMINISTIC_DERIVATION,
        semantic_intent=SemanticIntent.CLASSIFY_CONTACT_KNOWLEDGE,
        input_domains=(RepresentationInputDomain.KNOWN_ENTITIES,),
        output_model="codex.representation.ContactLedgerBlock",
        transform=InformationTransform.PARTITION,
        omission_contract=_lossy(
            RepresentationInputDomain.KNOWN_ENTITIES,
            omitted_paths=("world.known_entities.*.unselected_fields",),
            filtering_predicate="Controlled by include_remembered_allies and preserve_knowledge_detail parameters.",
            recoverability=(
                Recoverability.LOCAL_GET,
                Recoverability.LOCAL_SELECT,
                Recoverability.LOCAL_SEARCH,
                Recoverability.LOCAL_EXPORT,
            ),
            rationale="Automatic contact groups are compact while exact subjective entity facts remain inspectable.",
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=_AUTOMATIC_EXPOSURES,
        parameter_schema=(
            _parameter(
                "include_remembered_allies",
                ParameterValueType.BOOLEAN,
                "Retain remembered allied contacts in automatic context.",
                False,
            ),
            _parameter(
                "preserve_knowledge_detail",
                ParameterValueType.BOOLEAN,
                "Preserve explicit visibility and memory distinctions in each partition.",
                False,
            ),
        ),
        implementation_ref="ai.codex_tools.representation.components.ContactLedgerComponent",
    ),
    RepresentationComponentSpec(
        component_id="objects.known",
        version=_VERSION,
        title="Known object index",
        description="Expose known subjective objects without inferring untyped object state.",
        role=RepresentationRole.STATE_INDEX,
        semantic_intent=SemanticIntent.INDEX_KNOWN_OBJECTS,
        input_domains=(RepresentationInputDomain.KNOWN_OBJECTS,),
        output_model="codex.representation.ObjectLedgerBlock",
        transform=InformationTransform.SELECT,
        omission_contract=_lossy(
            RepresentationInputDomain.KNOWN_OBJECTS,
            omitted_paths=("world.known_objects.*.state",),
            item_limit=0,
            recoverability=(Recoverability.LOCAL_GET, Recoverability.LOCAL_SELECT, Recoverability.LOCAL_EXPORT),
            rationale="Automatic object rows may be bounded while full object state remains locally inspectable.",
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=_AUTOMATIC_EXPOSURES,
        parameter_schema=(
            _parameter(
                "max_items",
                ParameterValueType.INTEGER,
                "Maximum automatic object rows, where zero means unbounded.",
                0,
                minimum=0,
            ),
            _parameter(
                "include_full_objects",
                ParameterValueType.BOOLEAN,
                "Include complete subjective object facts in automatic context.",
                False,
            ),
        ),
        implementation_ref="ai.codex_tools.representation.components.ObjectLedgerComponent",
    ),
    RepresentationComponentSpec(
        component_id="topology.summary",
        version=_VERSION,
        title="Known topology summary",
        description="Index known hazards, slow cells, blockers, and vision blockers.",
        role=RepresentationRole.STATE_INDEX,
        semantic_intent=SemanticIntent.INDEX_KNOWN_TOPOLOGY,
        input_domains=(RepresentationInputDomain.KNOWN_TILES,),
        output_model="codex.representation.TopologySummaryBlock",
        transform=InformationTransform.AGGREGATE,
        omission_contract=_lossy(
            RepresentationInputDomain.KNOWN_TILES,
            omitted_paths=(
                "world.known_tiles.*.light",
                "world.known_tiles.*.conditions",
                "world.known_tiles.*.movement_cost",
                "world.known_tiles.*.knowledge_state",
            ),
            recoverability=(Recoverability.LOCAL_GET, Recoverability.LOCAL_SELECT, Recoverability.LOCAL_EXPORT),
            rationale="The bounded turn view carries topology classes while exact tile records remain inspectable.",
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=_AUTOMATIC_EXPOSURES,
        implementation_ref="ai.codex_tools.representation.components.TopologySummaryComponent",
    ),
    RepresentationComponentSpec(
        component_id="spatial.scene",
        version=_VERSION,
        title="Neutral spatial scene",
        description="Build a bounded non-ranking scene from known topology and contacts.",
        role=RepresentationRole.COMPUTATIONAL_AUGMENTATION,
        semantic_intent=SemanticIntent.SUMMARIZE_SPATIAL_CONTEXT,
        input_domains=(
            RepresentationInputDomain.KNOWN_ENTITIES,
            RepresentationInputDomain.KNOWN_OBJECTS,
            RepresentationInputDomain.KNOWN_TILES,
            RepresentationInputDomain.GEOMETRY,
        ),
        output_model="codex.representation.SpatialSceneBlock",
        transform=InformationTransform.SELECT,
        omission_contract=_lossy(
            RepresentationInputDomain.KNOWN_ENTITIES,
            RepresentationInputDomain.KNOWN_OBJECTS,
            RepresentationInputDomain.KNOWN_TILES,
            omitted_paths=("world.known_tiles.outside_scene",),
            filtering_predicate="Known positions within scene_radius of controlled actors or known contacts.",
            recoverability=(Recoverability.LOCAL_SELECT, Recoverability.LOCAL_EXPORT),
            rationale="A bounded spatial workspace avoids dumping the full known map at every decision.",
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=_AUTOMATIC_EXPOSURES,
        parameter_schema=(
            _parameter(
                "scene_radius",
                ParameterValueType.INTEGER,
                "Grid radius around controlled actors and contacts included automatically.",
                12,
                minimum=1,
            ),
            _parameter(
                "include_unknown_cells",
                ParameterValueType.BOOLEAN,
                "Represent unknown cells explicitly rather than omitting them from scene bounds.",
                True,
            ),
        ),
        implementation_ref="ai.codex_tools.representation.components.SpatialSceneComponent",
    ),
    RepresentationComponentSpec(
        component_id="actions.index",
        version=_VERSION,
        title="Legal affordance index",
        description="Group current server-issued rows by typed action semantics and costs.",
        role=RepresentationRole.STATE_INDEX,
        semantic_intent=SemanticIntent.INDEX_LEGAL_AFFORDANCES,
        input_domains=(RepresentationInputDomain.DECISION_EPOCH,),
        output_model="codex.representation.ActionFamilyBlock",
        transform=InformationTransform.GROUP,
        omission_contract=_lossy(
            RepresentationInputDomain.DECISION_EPOCH,
            omitted_paths=("world.current_epoch.affordances.*.full_row",),
            item_limit=0,
            recoverability=(Recoverability.LOCAL_GET, Recoverability.LOCAL_SELECT, Recoverability.LOCAL_EXPORT),
            rationale="Automatic action families remain bounded while every executable row stays locally selectable.",
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        required=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=_AUTOMATIC_EXPOSURES,
        parameter_schema=(
            _parameter(
                "multi_target_row_limit",
                ParameterValueType.INTEGER,
                "Maximum expanded multi-target rows, where zero means unbounded.",
                8,
                minimum=0,
            ),
            _parameter(
                "include_full_rows",
                ParameterValueType.BOOLEAN,
                "Include complete executable rows in automatic context.",
                False,
            ),
            _parameter(
                "family_limit",
                ParameterValueType.INTEGER,
                "Maximum source-action families in automatic context, where zero means unbounded.",
                24,
                minimum=0,
            ),
            _parameter(
                "capability_limit",
                ParameterValueType.INTEGER,
                "Maximum non-executable actor capabilities in automatic context, where zero means unbounded.",
                24,
                minimum=0,
            ),
        ),
        implementation_ref="ai.codex_tools.representation.components.ActionFamilyComponent",
    ),
    RepresentationComponentSpec(
        component_id="events.recent_logs",
        version=_VERSION,
        title="Bounded recent combat logs",
        description="Reproduce the current bounded recent subjective combat-log projection.",
        role=RepresentationRole.STATE_SELECTION,
        semantic_intent=SemanticIntent.SUMMARIZE_RECENT_EVENTS,
        input_domains=(RepresentationInputDomain.COMBAT_LOGS,),
        output_model="codex.representation.RecentCombatLogsBlock",
        transform=InformationTransform.TRUNCATE,
        omission_contract=_lossy(
            RepresentationInputDomain.COMBAT_LOGS,
            omitted_paths=("world.combat_logs.before_limit", "world.combat_logs.*.deep_children"),
            ordering_rule="Preserve subjective log order and retain the newest top-level records.",
            item_limit=3,
            depth_limit=1,
            recoverability=(Recoverability.LOCAL_SELECT, Recoverability.LOCAL_SEARCH, Recoverability.LOCAL_EXPORT),
            rationale="Compatibility mode reproduces the bounded log view while declaring recoverable omissions.",
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=_AUTOMATIC_EXPOSURES,
        parameter_schema=(
            _parameter(
                "log_limit",
                ParameterValueType.INTEGER,
                "Maximum recent top-level subjective combat logs.",
                3,
                minimum=1,
            ),
            _parameter(
                "child_limit",
                ParameterValueType.INTEGER,
                "Maximum direct child log entries retained per top-level record.",
                8,
                minimum=0,
            ),
        ),
        implementation_ref="ai.codex_tools.representation.components.RecentCombatLogsComponent",
    ),
    RepresentationComponentSpec(
        component_id="events.decision_delta",
        version=_VERSION,
        title="Decision-boundary subjective delta",
        description="Preserve ordered subjective changes since the preceding Codex decision boundary.",
        role=RepresentationRole.STATE_SELECTION,
        semantic_intent=SemanticIntent.PRESERVE_DECISION_DELTA,
        input_domains=(RepresentationInputDomain.REVISION, RepresentationInputDomain.COMBAT_LOGS),
        output_model="codex.representation.DecisionDeltaBlock",
        transform=InformationTransform.GROUP,
        omission_contract=_lossless(
            RepresentationInputDomain.REVISION,
            RepresentationInputDomain.COMBAT_LOGS,
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=_AUTOMATIC_EXPOSURES,
        implementation_ref="ai.codex_tools.representation.components.DecisionDeltaComponent",
    ),
    RepresentationComponentSpec(
        component_id="memory.combat_hypotheses",
        version=_VERSION,
        title="Subjective combat hypotheses",
        description="Expose bounded uncertain effect-block hypotheses derived from perceived combat evidence.",
        role=RepresentationRole.BELIEF_DERIVATION,
        semantic_intent=SemanticIntent.EXPOSE_COMBAT_BELIEFS,
        input_domains=(RepresentationInputDomain.AGENT_FACTS,),
        output_model="codex.representation.CombatHypothesisBlock",
        transform=InformationTransform.INFER,
        omission_contract=_lossy(
            RepresentationInputDomain.AGENT_FACTS,
            omitted_paths=("agent_facts.non_combat_memory", "agent_facts.combat_memory.unchanged"),
            filtering_predicate="Controlled by changed_only parameter.",
            recoverability=(Recoverability.LOCAL_GET, Recoverability.LOCAL_EXPORT),
            rationale="Automatic context emphasizes changed beliefs while the full derived ledger remains inspectable.",
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=_AUTOMATIC_EXPOSURES,
        parameter_schema=(
            _parameter(
                "changed_only",
                ParameterValueType.BOOLEAN,
                "Expose only hypotheses materially changed at the current decision boundary.",
                False,
            ),
        ),
        implementation_ref="ai.codex_tools.representation.components.CombatHypothesisComponent",
    ),
    RepresentationComponentSpec(
        component_id="predicates.focused",
        version=_VERSION,
        title="Focused logical state",
        description="Expose selected three-valued predicates without removing them from the complete ledger.",
        role=RepresentationRole.ATTENTION_CONTROL,
        semantic_intent=SemanticIntent.FOCUS_LOGICAL_STATE,
        input_domains=(RepresentationInputDomain.PREDICATE_LEDGER,),
        output_model="codex.representation.PredicateFocusBlock",
        transform=InformationTransform.FILTER,
        omission_contract=_lossy(
            RepresentationInputDomain.PREDICATE_LEDGER,
            omitted_paths=("predicates.not_focused",),
            filtering_predicate="Predicate focus profile and change state.",
            item_limit=64,
            recoverability=(Recoverability.LOCAL_GET, Recoverability.LOCAL_SEARCH, Recoverability.LOCAL_EXPORT),
            rationale="Attention controls automatic exposure only; every evaluation remains in the ledger.",
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=_AUTOMATIC_EXPOSURES,
        parameter_schema=(
            _parameter(
                "max_automatic_items",
                ParameterValueType.INTEGER,
                "Maximum focused predicate evaluations emitted automatically.",
                64,
                minimum=1,
            ),
            _parameter(
                "include_changed",
                ParameterValueType.BOOLEAN,
                "Automatically expose predicates whose value changed.",
                True,
            ),
        ),
        implementation_ref="ai.codex_tools.representation.components.PredicateFocusComponent",
    ),
    RepresentationComponentSpec(
        component_id="attention.current_warnings",
        version=_VERSION,
        title="Compatibility warnings",
        description="Reproduce the two hardcoded warnings in the current Codex turn index.",
        role=RepresentationRole.ATTENTION_CONTROL,
        semantic_intent=SemanticIntent.SURFACE_RUNTIME_WARNINGS,
        input_domains=(RepresentationInputDomain.ENCOUNTER, RepresentationInputDomain.KNOWN_ENTITIES),
        output_model="codex.representation.WarningBlock",
        transform=InformationTransform.FILTER,
        omission_contract=_lossy(
            RepresentationInputDomain.ENCOUNTER,
            RepresentationInputDomain.KNOWN_ENTITIES,
            omitted_paths=("agent_state.alerts.except_current_hardcoded_checks",),
            filtering_predicate="No controlled epoch or remembered non-visible hostile.",
            recoverability=(Recoverability.LOCAL_GET, Recoverability.LOCAL_EXPORT),
            rationale="Compatibility mode exposes only warnings produced by the current interface.",
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=_AUTOMATIC_EXPOSURES,
        implementation_ref="ai.codex_tools.representation.components.CurrentWarningsComponent",
    ),
    RepresentationComponentSpec(
        component_id="oracle.policy",
        version=_VERSION,
        title="Traditional policy oracle",
        description="Optionally expose tactical opinion from the unchanged traditional policy host.",
        role=RepresentationRole.POLICY_ADVICE,
        semantic_intent=SemanticIntent.PROVIDE_POLICY_ADVICE,
        input_domains=(RepresentationInputDomain.POLICY_ORACLE,),
        output_model="codex.representation.AdviceBlock",
        transform=InformationTransform.RANK,
        omission_contract=_lossy(
            RepresentationInputDomain.POLICY_ORACLE,
            omitted_paths=("policy.candidates.not_selected", "policy.trace.detail"),
            recoverability=(Recoverability.LOCAL_GET,),
            rationale="Selected-only advice is compact; complete candidates and trace are available on demand.",
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        default_exposure=ExposureTiming.ON_DEMAND,
        supported_exposures=(
            ExposureTiming.NEVER,
            ExposureTiming.DECISION_EPOCH,
            ExposureTiming.AFTER_RESULT,
            ExposureTiming.END_TURN,
            ExposureTiming.END_ENCOUNTER,
            ExposureTiming.ON_DEMAND,
        ),
        parameter_schema=(
            _parameter(
                "detail",
                ParameterValueType.STRING,
                "Amount of policy output exposed to Codex.",
                "selected_only",
                allowed_values=("selected_only", "ranked", "full_trace"),
            ),
            _parameter(
                "advance_lifecycle_on_match",
                ParameterValueType.BOOLEAN,
                "Advance oracle policy memory when Codex executes the recommended row.",
                False,
            ),
        ),
        implementation_ref="ai.codex_tools.representation.oracle.TraditionalPolicyOracle",
    ),
    RepresentationComponentSpec(
        component_id="telemetry.runtime",
        version=_VERSION,
        title="Representation runtime telemetry",
        description="Record timings, payload sizes, inspections, and command lifecycle without gameplay authority.",
        role=RepresentationRole.TELEMETRY,
        semantic_intent=SemanticIntent.RECORD_RUNTIME_TELEMETRY,
        input_domains=(RepresentationInputDomain.RUNTIME_TELEMETRY,),
        output_model="codex.representation.RepresentationTelemetryBlock",
        transform=InformationTransform.AGGREGATE,
        omission_contract=_lossless(RepresentationInputDomain.RUNTIME_TELEMETRY),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=False,
        default_exposure=ExposureTiming.NEVER,
        supported_exposures=(ExposureTiming.NEVER, ExposureTiming.DECISION_EPOCH, ExposureTiming.ON_DEMAND),
        implementation_ref="ai.codex_tools.representation.components.RuntimeTelemetryComponent",
    ),
    RepresentationComponentSpec(
        component_id="encounter.summary",
        version=_VERSION,
        title="Subjective encounter summary",
        description=(
            "Summarize post-match outcome and observed combat statistics without an "
            "objective reveal."
        ),
        role=RepresentationRole.DETERMINISTIC_DERIVATION,
        semantic_intent=SemanticIntent.SUMMARIZE_ENCOUNTER_OUTCOME,
        input_domains=(
            RepresentationInputDomain.ENCOUNTER,
            RepresentationInputDomain.KNOWN_ENTITIES,
            RepresentationInputDomain.COMBAT_LOGS,
            RepresentationInputDomain.PREDICATE_LEDGER,
            RepresentationInputDomain.RUNTIME_TELEMETRY,
        ),
        output_model="codex.representation.EncounterSummaryBlock",
        transform=InformationTransform.AGGREGATE,
        omission_contract=_lossy(
            RepresentationInputDomain.COMBAT_LOGS,
            RepresentationInputDomain.KNOWN_ENTITIES,
            omitted_paths=(
                "world.combat_logs.*.full_entry",
                "world.known_entities.*.full_fact",
            ),
            recoverability=(Recoverability.LOCAL_GET, Recoverability.LOCAL_EXPORT),
            rationale=(
                "The summary aggregates visible evidence while canonical subjective records "
                "remain locally inspectable."
            ),
        ),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=(
            ExposureTiming.DECISION_EPOCH,
            ExposureTiming.END_ENCOUNTER,
            ExposureTiming.ON_DEMAND,
        ),
        implementation_ref="ai.codex_tools.representation.components.EncounterSummaryComponent",
    ),
    RepresentationComponentSpec(
        component_id="presentation.typed_json",
        version=_VERSION,
        title="Canonical typed JSON presentation",
        description="Preserve validated component blocks in one deterministic machine-readable envelope.",
        role=RepresentationRole.PRESENTATION,
        semantic_intent=SemanticIntent.PRESERVE_TYPED_PRESENTATION,
        input_domains=(RepresentationInputDomain.REVISION,),
        output_model="codex.representation.CodexTurnRepresentation",
        transform=InformationTransform.RENDER,
        omission_contract=_lossless(RepresentationInputDomain.REVISION),
        subjectivity_contract=_SUBJECTIVE,
        deterministic=True,
        required=True,
        default_exposure=ExposureTiming.DECISION_EPOCH,
        supported_exposures=_AUTOMATIC_EXPOSURES,
        parameter_schema=(
            _parameter(
                "include_command_follow_up",
                ParameterValueType.BOOLEAN,
                "Include the resulting bounded turn brief in compact command receipts.",
                True,
            ),
        ),
        implementation_ref="ai.codex_tools.representation.components.TypedJsonPresentationComponent",
    ),
)


CURRENT_V1_PROFILE = RepresentationProfile(
    profile_id=CURRENT_V1_PROFILE_ID,
    version="1.0.0",
    description="Compatibility profile reproducing the current bounded HotCodexTurnIndex semantics.",
    component_selections=(
        RepresentationComponentSelection(component_id="core.revision", exposure=ExposureTiming.DECISION_EPOCH),
        RepresentationComponentSelection(component_id="core.turn", exposure=ExposureTiming.DECISION_EPOCH),
        RepresentationComponentSelection(
            component_id="contacts.partition",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={"include_remembered_allies": False, "preserve_knowledge_detail": False},
        ),
        RepresentationComponentSelection(
            component_id="objects.known",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={"max_items": 0, "include_full_objects": True},
        ),
        RepresentationComponentSelection(component_id="topology.summary", exposure=ExposureTiming.DECISION_EPOCH),
        RepresentationComponentSelection(
            component_id="actions.index",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={
                "multi_target_row_limit": 8,
                "include_full_rows": True,
                "family_limit": 0,
                "capability_limit": 0,
            },
        ),
        RepresentationComponentSelection(
            component_id="events.recent_logs",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={"log_limit": 3, "child_limit": 8},
        ),
        RepresentationComponentSelection(
            component_id="memory.combat_hypotheses",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={"changed_only": False},
        ),
        RepresentationComponentSelection(
            component_id="attention.current_warnings",
            exposure=ExposureTiming.DECISION_EPOCH,
        ),
        RepresentationComponentSelection(
            component_id="oracle.policy",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={"detail": "selected_only", "advance_lifecycle_on_match": True},
        ),
        RepresentationComponentSelection(component_id="telemetry.runtime", exposure=ExposureTiming.DECISION_EPOCH),
        RepresentationComponentSelection(component_id="encounter.summary", exposure=ExposureTiming.DECISION_EPOCH),
        RepresentationComponentSelection(
            component_id="presentation.typed_json",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={"include_command_follow_up": True},
        ),
    ),
    compatibility=RepresentationCompatibility(
        legacy_response_model="ai.codex_tools.hot_runtime.HotCodexTurnIndex",
        preserves_eager_policy_lifecycle=True,
        notes=(
            "Preserves current contact omissions, three-log limit, eight-child limit, and eager oracle advice.",
        ),
    ),
)


BALANCED_V2_PROFILE = RepresentationProfile(
    profile_id=BALANCED_V2_PROFILE_ID,
    version="2.0.0",
    description="Neutral automatic Codex context with complete local recovery and no pre-action advice.",
    component_selections=(
        RepresentationComponentSelection(component_id="core.revision", exposure=ExposureTiming.DECISION_EPOCH),
        RepresentationComponentSelection(component_id="core.turn", exposure=ExposureTiming.DECISION_EPOCH),
        RepresentationComponentSelection(
            component_id="contacts.partition",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={"include_remembered_allies": True, "preserve_knowledge_detail": True},
        ),
        RepresentationComponentSelection(
            component_id="objects.known",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={"max_items": 64, "include_full_objects": False},
        ),
        RepresentationComponentSelection(component_id="topology.summary", exposure=ExposureTiming.DECISION_EPOCH),
        RepresentationComponentSelection(
            component_id="spatial.scene",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={"scene_radius": 12, "include_unknown_cells": True},
        ),
        RepresentationComponentSelection(
            component_id="actions.index",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={
                "multi_target_row_limit": 8,
                "include_full_rows": False,
                "family_limit": 24,
                "capability_limit": 24,
            },
        ),
        RepresentationComponentSelection(
            component_id="events.recent_logs",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={"log_limit": 3, "child_limit": 8},
        ),
        RepresentationComponentSelection(
            component_id="events.decision_delta",
            exposure=ExposureTiming.DECISION_EPOCH,
        ),
        RepresentationComponentSelection(
            component_id="memory.combat_hypotheses",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={"changed_only": True},
        ),
        RepresentationComponentSelection(
            component_id="predicates.focused",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={"max_automatic_items": 64, "include_changed": True},
        ),
        RepresentationComponentSelection(
            component_id="oracle.policy",
            exposure=ExposureTiming.ON_DEMAND,
            parameters={"detail": "selected_only", "advance_lifecycle_on_match": False},
        ),
        RepresentationComponentSelection(component_id="telemetry.runtime", exposure=ExposureTiming.NEVER),
        RepresentationComponentSelection(component_id="encounter.summary", exposure=ExposureTiming.DECISION_EPOCH),
        RepresentationComponentSelection(
            component_id="presentation.typed_json",
            exposure=ExposureTiming.DECISION_EPOCH,
            parameters={"include_command_follow_up": True},
        ),
    ),
    compatibility=RepresentationCompatibility(
        notes=(
            "Traditional policy remains available only on demand and is not part of automatic decision context.",
        ),
    ),
)


def build_builtin_representation_registry() -> RepresentationRegistry:
    """Return a fresh registry containing all built-in definitions and profiles."""
    registry = RepresentationRegistry()
    for spec in BUILTIN_COMPONENT_SPECS:
        registry.register_component(spec)
    registry.register_profile(CURRENT_V1_PROFILE)
    registry.register_profile(BALANCED_V2_PROFILE)
    return registry
