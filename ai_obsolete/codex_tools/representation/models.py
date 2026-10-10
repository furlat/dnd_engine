"""Typed contracts for reproducible Codex subjective representations."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
import math
import re
from typing import Generic, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    computed_field,
    field_validator,
    model_validator,
)


_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$")


class RepresentationModel(BaseModel):
    """Immutable base model for representation contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RepresentationRole(str, Enum):
    """Epistemic or operational role played by a representation component."""

    STATE_SELECTION = "state_selection"
    STATE_INDEX = "state_index"
    DETERMINISTIC_DERIVATION = "deterministic_derivation"
    BELIEF_DERIVATION = "belief_derivation"
    COMPUTATIONAL_AUGMENTATION = "computational_augmentation"
    ATTENTION_CONTROL = "attention_control"
    POLICY_ADVICE = "policy_advice"
    LEARNING_FEEDBACK = "learning_feedback"
    PRESENTATION = "presentation"
    TELEMETRY = "telemetry"


class InformationTransform(str, Enum):
    """Transformation applied to component source information."""

    IDENTITY = "identity"
    SELECT = "select"
    FILTER = "filter"
    PARTITION = "partition"
    GROUP = "group"
    AGGREGATE = "aggregate"
    TRUNCATE = "truncate"
    INFER = "infer"
    PREDICT = "predict"
    RANK = "rank"
    RENDER = "render"


class ExposureTiming(str, Enum):
    """Lifecycle boundary at which a component may reach agent context."""

    NEVER = "never"
    BOOTSTRAP = "bootstrap"
    DECISION_EPOCH = "decision_epoch"
    AFTER_ACTION = "after_action"
    AFTER_RESULT = "after_result"
    END_TURN = "end_turn"
    END_ENCOUNTER = "end_encounter"
    ON_DEMAND = "on_demand"


class Recoverability(str, Enum):
    """Mechanism by which omitted local information can be recovered."""

    NOT_APPLICABLE = "not_applicable"
    LOCAL_GET = "local_get"
    LOCAL_SELECT = "local_select"
    LOCAL_SEARCH = "local_search"
    LOCAL_EXPORT = "local_export"
    NOT_RECOVERABLE = "not_recoverable"


class SemanticIntent(str, Enum):
    """Stable experimental intention of a representation component."""

    PRESERVE_REVISION_IDENTITY = "preserve_revision_identity"
    PRESERVE_TURN_STATE = "preserve_turn_state"
    CLASSIFY_CONTACT_KNOWLEDGE = "classify_contact_knowledge"
    INDEX_KNOWN_OBJECTS = "index_known_objects"
    INDEX_KNOWN_TOPOLOGY = "index_known_topology"
    SUMMARIZE_SPATIAL_CONTEXT = "summarize_spatial_context"
    INDEX_LEGAL_AFFORDANCES = "index_legal_affordances"
    SUMMARIZE_RECENT_EVENTS = "summarize_recent_events"
    PRESERVE_DECISION_DELTA = "preserve_decision_delta"
    EXPOSE_COMBAT_BELIEFS = "expose_combat_beliefs"
    FOCUS_LOGICAL_STATE = "focus_logical_state"
    SURFACE_RUNTIME_WARNINGS = "surface_runtime_warnings"
    PROVIDE_POLICY_ADVICE = "provide_policy_advice"
    RECORD_RUNTIME_TELEMETRY = "record_runtime_telemetry"
    SUMMARIZE_ENCOUNTER_OUTCOME = "summarize_encounter_outcome"
    PRESERVE_TYPED_PRESENTATION = "preserve_typed_presentation"


class RepresentationInputDomain(str, Enum):
    """Typed local source domain available to representation components."""

    REVISION = "revision"
    SESSION = "session"
    ENCOUNTER = "encounter"
    OBSERVERS = "observers"
    KNOWN_ENTITIES = "known_entities"
    KNOWN_OBJECTS = "known_objects"
    KNOWN_TILES = "known_tiles"
    DECISION_EPOCH = "decision_epoch"
    COMBAT_LOGS = "combat_logs"
    AGENT_FACTS = "agent_facts"
    PREDICATE_LEDGER = "predicate_ledger"
    GEOMETRY = "geometry"
    POLICY_ORACLE = "policy_oracle"
    RUNTIME_TELEMETRY = "runtime_telemetry"


class SubjectivityScope(str, Enum):
    """Permitted information boundary for a representation component."""

    SESSION_SUBJECTIVE = "session_subjective"


class ParameterValueType(str, Enum):
    """JSON value category accepted by a component parameter."""

    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    STRING = "string"
    STRING_LIST = "string_list"


class SubjectivityContract(RepresentationModel):
    """Machine-readable promise that a component remains session subjective."""

    scope: SubjectivityScope = Field(
        default=SubjectivityScope.SESSION_SUBJECTIVE,
        description="Information scope the component is allowed to inspect.",
    )
    permits_objective_state: Literal[False] = Field(
        default=False,
        description="Whether the component may consult objective server state; always false.",
    )
    preserves_knowledge_distinctions: bool = Field(
        default=True,
        description="Whether visible, remembered, known-false, and unknown remain distinguishable.",
    )
    description: str = Field(
        min_length=1,
        description="Human-readable explanation of the component's subjectivity boundary.",
    )


class OmissionContract(RepresentationModel):
    """Declare information removed by a representation transformation."""

    source_domains: tuple[RepresentationInputDomain, ...] = Field(
        min_length=1,
        description="Source domains from which information may be omitted.",
    )
    omitted_paths: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Canonical paths or path patterns omitted from automatic presentation.",
    )
    filtering_predicate: str | None = Field(
        default=None,
        description="Stable description of any predicate used to filter source records.",
    )
    ordering_rule: str | None = Field(
        default=None,
        description="Deterministic ordering applied before any limits or truncation.",
    )
    item_limit: int | None = Field(
        default=None,
        ge=0,
        description="Maximum automatically emitted items, where zero means no finite limit.",
    )
    depth_limit: int | None = Field(
        default=None,
        ge=0,
        description="Maximum automatically emitted nesting depth, where zero means no finite limit.",
    )
    omitted_counts_reported: bool = Field(
        default=False,
        description="Whether component output reports the number of omitted records.",
    )
    recoverability: tuple[Recoverability, ...] = Field(
        min_length=1,
        description="Mechanisms available to recover omitted local information.",
    )
    rationale: str = Field(
        min_length=1,
        description="Reason the automatic representation performs this omission.",
    )

    @property
    def removes_information(self) -> bool:
        """Return whether the contract describes a lossy transformation."""
        return bool(
            self.omitted_paths
            or self.filtering_predicate
            or self.item_limit is not None
            or self.depth_limit is not None
        )

    @model_validator(mode="after")
    def validate_recovery_shape(self) -> "OmissionContract":
        """Keep lossless and lossy recovery declarations unambiguous."""
        if len(set(self.source_domains)) != len(self.source_domains):
            raise ValueError("Omission source domains must be unique")
        if len(set(self.recoverability)) != len(self.recoverability):
            raise ValueError("Recoverability methods must be unique")
        if self.removes_information:
            if Recoverability.NOT_APPLICABLE in self.recoverability:
                raise ValueError("Lossy omissions cannot use not_applicable recoverability")
        elif self.recoverability != (Recoverability.NOT_APPLICABLE,):
            raise ValueError("Lossless components must use only not_applicable recoverability")
        return self


class RepresentationParameterSpec(RepresentationModel):
    """Typed schema for one configurable component parameter."""

    parameter_id: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Stable parameter identifier within the component.",
    )
    value_type: ParameterValueType = Field(description="JSON value category accepted by the parameter.")
    description: str = Field(min_length=1, description="Meaning and experimental effect of the parameter.")
    required: bool = Field(default=False, description="Whether a profile must explicitly provide the parameter.")
    has_default: bool = Field(default=False, description="Whether default_value is part of the parameter contract.")
    default_value: JsonValue = Field(default=None, description="Default JSON value used when the profile omits it.")
    allowed_values: tuple[JsonValue, ...] = Field(
        default_factory=tuple,
        description="Optional closed set of accepted JSON values.",
    )
    minimum: float | None = Field(default=None, description="Optional inclusive numeric lower bound.")
    maximum: float | None = Field(default=None, description="Optional inclusive numeric upper bound.")

    @model_validator(mode="after")
    def validate_definition(self) -> "RepresentationParameterSpec":
        """Validate defaults, bounds, and the declared JSON value category."""
        if self.required and self.has_default:
            raise ValueError("A required parameter cannot also define a default")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Parameter minimum cannot exceed maximum")
        if self.has_default:
            self.validate_value(self.default_value)
        for value in self.allowed_values:
            self.validate_value(value)
        return self

    def validate_value(self, value: JsonValue) -> None:
        """Validate one profile value against this parameter specification.

        Args:
            value: JSON-compatible parameter value supplied by a profile.

        Raises:
            ValueError: If the value violates the declared type or constraints.
        """
        if not _matches_parameter_type(value, self.value_type):
            raise ValueError(
                f"Parameter {self.parameter_id} requires {self.value_type.value}"
            )
        if self.allowed_values and value not in self.allowed_values:
            raise ValueError(
                f"Parameter {self.parameter_id} must be one of {self.allowed_values}"
            )
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                raise ValueError(f"Parameter {self.parameter_id} must be finite")
            if self.minimum is not None and numeric_value < self.minimum:
                raise ValueError(f"Parameter {self.parameter_id} is below its minimum")
            if self.maximum is not None and numeric_value > self.maximum:
                raise ValueError(f"Parameter {self.parameter_id} exceeds its maximum")


class RepresentationComponentSpec(RepresentationModel):
    """Semantic definition of one independently ablatable representation step."""

    component_id: str = Field(description="Stable namespaced component identifier.")
    version: str = Field(description="Semantic version of the component definition.")
    title: str = Field(min_length=1, description="Short human-readable component title.")
    description: str = Field(min_length=1, description="Complete description of component behavior.")
    role: RepresentationRole = Field(description="Epistemic or operational role of the component.")
    semantic_intent: SemanticIntent = Field(description="Stable intention represented in ablation evidence.")
    input_domains: tuple[RepresentationInputDomain, ...] = Field(
        min_length=1,
        description="Local subjective domains consumed by the component.",
    )
    output_model: str = Field(min_length=1, description="Qualified identity of the component output model.")
    transform: InformationTransform = Field(description="Information transformation performed by the component.")
    omission_contract: OmissionContract = Field(description="Explicit information-loss and recovery contract.")
    subjectivity_contract: SubjectivityContract = Field(description="Information boundary enforced by the component.")
    deterministic: bool = Field(description="Whether equal inputs and parameters produce equal output.")
    required: bool = Field(
        default=False,
        description="Whether failure makes the complete representation unavailable.",
    )
    default_exposure: ExposureTiming = Field(description="Default lifecycle exposure for the component.")
    supported_exposures: tuple[ExposureTiming, ...] = Field(
        min_length=1,
        description="All lifecycle exposures supported by the implementation.",
    )
    parameter_schema: tuple[RepresentationParameterSpec, ...] = Field(
        default_factory=tuple,
        description="Typed configurable parameters accepted by this component.",
    )
    implementation_ref: str = Field(
        min_length=1,
        description="Stable qualified reference to the component implementation.",
    )

    @field_validator("component_id")
    @classmethod
    def validate_component_id(cls, value: str) -> str:
        """Reject unstable or display-oriented component identifiers."""
        if _IDENTIFIER_PATTERN.fullmatch(value) is None:
            raise ValueError("Component id must be a stable lowercase namespaced identifier")
        return value

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        """Require a semantic component version."""
        if _VERSION_PATTERN.fullmatch(value) is None:
            raise ValueError("Component version must use semantic version syntax")
        return value

    @model_validator(mode="after")
    def validate_component_contract(self) -> "RepresentationComponentSpec":
        """Validate domains, exposures, parameters, and canonical recovery."""
        if len(set(self.input_domains)) != len(self.input_domains):
            raise ValueError("Component input domains must be unique")
        if len(set(self.supported_exposures)) != len(self.supported_exposures):
            raise ValueError("Supported exposures must be unique")
        if self.default_exposure not in self.supported_exposures:
            raise ValueError("Default exposure must be supported by the component")
        parameter_ids = [parameter.parameter_id for parameter in self.parameter_schema]
        if len(set(parameter_ids)) != len(parameter_ids):
            raise ValueError("Component parameter ids must be unique")
        if not set(self.omission_contract.source_domains).issubset(self.input_domains):
            raise ValueError("Omission domains must be included in component input domains")
        canonical_domains = set(self.input_domains) - {
            RepresentationInputDomain.POLICY_ORACLE,
            RepresentationInputDomain.RUNTIME_TELEMETRY,
        }
        if (
            self.omission_contract.removes_information
            and canonical_domains.intersection(self.omission_contract.source_domains)
            and Recoverability.NOT_RECOVERABLE in self.omission_contract.recoverability
        ):
            raise ValueError("Canonical subjective omissions must remain locally recoverable")
        if self.role is RepresentationRole.POLICY_ADVICE and self.transform is not InformationTransform.RANK:
            raise ValueError("Policy advice components must declare a rank transform")
        if self.role is RepresentationRole.PRESENTATION and self.transform is not InformationTransform.RENDER:
            raise ValueError("Presentation components must declare a render transform")
        return self


class RepresentationComponentSelection(RepresentationModel):
    """Experiment-specific activation and parameters for one component."""

    component_id: str = Field(description="Registered component selected by the profile.")
    enabled: bool = Field(default=True, description="Whether the component participates in this profile.")
    exposure: ExposureTiming = Field(description="Lifecycle timing selected for this profile.")
    parameters: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Explicit component parameter overrides for this profile.",
    )

    @field_validator("component_id")
    @classmethod
    def validate_component_id(cls, value: str) -> str:
        """Require the same stable identity grammar as component definitions."""
        if _IDENTIFIER_PATTERN.fullmatch(value) is None:
            raise ValueError("Component id must be a stable lowercase namespaced identifier")
        return value

    @model_validator(mode="after")
    def validate_activation(self) -> "RepresentationComponentSelection":
        """Prevent disabled components from declaring an active exposure."""
        if not self.enabled and self.exposure is not ExposureTiming.NEVER:
            raise ValueError("Disabled components must use never exposure")
        return self


class RepresentationCompatibility(RepresentationModel):
    """Compatibility promises carried by a representation profile."""

    legacy_response_model: str | None = Field(
        default=None,
        description="Qualified legacy response model reproduced by this profile, if any.",
    )
    preserves_eager_policy_lifecycle: bool = Field(
        default=False,
        description="Whether eager policy evaluation and matching-row lifecycle are preserved.",
    )
    notes: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Additional stable compatibility declarations.",
    )


class RepresentationProfile(RepresentationModel):
    """Ordered experiment choices over independently registered components."""

    profile_id: str = Field(description="Stable namespaced profile identifier.")
    version: str = Field(description="Semantic version of the profile definition.")
    description: str = Field(min_length=1, description="Purpose and intended experimental use of the profile.")
    component_selections: tuple[RepresentationComponentSelection, ...] = Field(
        min_length=1,
        description="Ordered component choices defining automatic and on-demand representation.",
    )
    compatibility: RepresentationCompatibility = Field(
        default_factory=RepresentationCompatibility,
        description="Compatibility behavior promised by this profile.",
    )

    @field_validator("profile_id")
    @classmethod
    def validate_profile_id(cls, value: str) -> str:
        """Reject unstable or display-oriented profile identifiers."""
        if _IDENTIFIER_PATTERN.fullmatch(value) is None:
            raise ValueError("Profile id must be a stable lowercase namespaced identifier")
        return value

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        """Require a semantic profile version."""
        if _VERSION_PATTERN.fullmatch(value) is None:
            raise ValueError("Profile version must use semantic version syntax")
        return value

    @model_validator(mode="after")
    def validate_unique_components(self) -> "RepresentationProfile":
        """Ensure one profile cannot configure a component twice."""
        component_ids = [selection.component_id for selection in self.component_selections]
        if len(set(component_ids)) != len(component_ids):
            raise ValueError("Profile component selections must be unique")
        return self


class ResolvedRepresentationComponent(RepresentationModel):
    """One registered definition paired with its resolved profile choice."""

    order: int = Field(ge=0, description="Zero-based deterministic component order.")
    spec: RepresentationComponentSpec = Field(description="Registered semantic component definition.")
    enabled: bool = Field(description="Whether the component participates in the resolved profile.")
    exposure: ExposureTiming = Field(description="Resolved lifecycle exposure.")
    parameters: dict[str, JsonValue] = Field(description="Defaults and overrides resolved to concrete values.")


class ResolvedRepresentationManifest(RepresentationModel):
    """Auditable resolved profile with a deterministic content identity."""

    profile_id: str = Field(description="Identity of the selected profile.")
    profile_version: str = Field(description="Semantic version of the selected profile.")
    profile_description: str = Field(description="Purpose copied from the selected profile.")
    components: tuple[ResolvedRepresentationComponent, ...] = Field(
        description="Components in exact execution and presentation order.",
    )
    created_at: datetime = Field(description="Timestamp at which this manifest instance was resolved.")
    compatibility: RepresentationCompatibility = Field(description="Resolved compatibility promises.")

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        """Require an offset-aware audit timestamp."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Manifest creation timestamp must be timezone aware")
        return value

    @model_validator(mode="after")
    def validate_component_order(self) -> "ResolvedRepresentationManifest":
        """Require contiguous order matching serialized component order."""
        expected = tuple(range(len(self.components)))
        actual = tuple(component.order for component in self.components)
        if actual != expected:
            raise ValueError("Resolved component order must be contiguous and serialized in order")
        return self

    @computed_field(description="Component ids in deterministic execution order.")
    @property
    def component_order(self) -> tuple[str, ...]:
        """Return component identities in resolved order."""
        return tuple(component.spec.component_id for component in self.components)

    @computed_field(description="SHA-256 identity of all behavior-affecting manifest content.")
    @property
    def manifest_digest(self) -> str:
        """Return a deterministic digest that excludes the audit timestamp."""
        canonical_payload = {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "profile_description": self.profile_description,
            "components": [
                component.model_dump(mode="json")
                for component in self.components
            ],
            "compatibility": self.compatibility.model_dump(mode="json"),
        }
        encoded = json.dumps(
            canonical_payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


class RecoveryInstruction(RepresentationModel):
    """Concrete local operation that recovers omitted representation data."""

    method: Recoverability = Field(description="Local recovery mechanism to use.")
    endpoint: str = Field(min_length=1, description="Local typed endpoint or Python API path.")
    description: str = Field(min_length=1, description="Information recovered by this operation.")

    @field_validator("method")
    @classmethod
    def validate_method(cls, value: Recoverability) -> Recoverability:
        """Require an actionable local recovery mechanism."""
        if value in {Recoverability.NOT_APPLICABLE, Recoverability.NOT_RECOVERABLE}:
            raise ValueError("A recovery instruction requires an actionable local method")
        return value


PayloadT = TypeVar("PayloadT", bound=BaseModel)


class RepresentationBlock(RepresentationModel, Generic[PayloadT]):
    """Typed output from one component at one subjective revision."""

    component_id: str = Field(description="Identity of the component that emitted the block.")
    component_version: str = Field(description="Version of the component that emitted the block.")
    role: RepresentationRole = Field(description="Epistemic or operational role of the block.")
    transform: InformationTransform = Field(description="Transformation applied to source information.")
    observation_cursor: int = Field(ge=0, description="Subjective observation cursor represented by the block.")
    epoch_id: str | None = Field(default=None, description="Decision epoch represented by the block, when active.")
    generated_at: datetime = Field(description="Offset-aware block generation timestamp.")
    payload: PayloadT = Field(description="Validated Pydantic payload emitted by the component.")
    source_paths: tuple[str, ...] = Field(description="Canonical local paths used to construct the payload.")
    omitted_item_count: int = Field(ge=0, description="Known number of source items omitted from the payload.")
    recovery_hints: tuple[RecoveryInstruction, ...] = Field(
        default_factory=tuple,
        description="Typed local operations that recover omitted source information.",
    )
    timing_ms: float = Field(ge=0, description="Local component evaluation duration in milliseconds.")
    payload_bytes: int = Field(ge=0, description="Canonical serialized payload size in bytes.")
    warnings: tuple[str, ...] = Field(default_factory=tuple, description="Non-fatal component warnings.")

    @field_validator("component_id")
    @classmethod
    def validate_component_id(cls, value: str) -> str:
        """Require a stable component identity on emitted blocks."""
        if _IDENTIFIER_PATTERN.fullmatch(value) is None:
            raise ValueError("Component id must be a stable lowercase namespaced identifier")
        return value

    @field_validator("component_version")
    @classmethod
    def validate_component_version(cls, value: str) -> str:
        """Require a semantic component version on emitted blocks."""
        if _VERSION_PATTERN.fullmatch(value) is None:
            raise ValueError("Component version must use semantic version syntax")
        return value

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        """Require an offset-aware block timestamp."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Block generation timestamp must be timezone aware")
        return value

    @field_validator("timing_ms")
    @classmethod
    def validate_timing(cls, value: float) -> float:
        """Reject non-finite timing values that cannot be reproduced in JSON."""
        if not math.isfinite(value):
            raise ValueError("Block timing must be finite")
        return value


def _matches_parameter_type(value: JsonValue, value_type: ParameterValueType) -> bool:
    """Return whether a JSON value matches one declared parameter category."""
    if value_type is ParameterValueType.BOOLEAN:
        return isinstance(value, bool)
    if value_type is ParameterValueType.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type is ParameterValueType.NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type is ParameterValueType.STRING:
        return isinstance(value, str)
    if value_type is ParameterValueType.STRING_LIST:
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    return False
