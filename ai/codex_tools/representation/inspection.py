"""Safe local inspection over immutable session-subjective JSON documents.

The inspection slice deliberately operates on canonical JSON bytes rather than
live Pydantic objects. This keeps historical views immutable, makes digests
reproducible, and prevents inspection from becoming a Python object traversal
or execution surface.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
import math
import re
from threading import RLock
from typing import Any, Optional, TypeAlias, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, model_validator

from ai.knowledge.models import AgentFacts
from ai.observation.models import ObservationFrame
from ai.observation.models import SubjectiveWorldState
from ai.subjective.models import AgentState, Alert, BriefEmission, TraceEmission


InspectionSource: TypeAlias = BaseModel | Mapping[str, object]

_MAX_DOCUMENT_DEPTH = 128
_MAX_DOCUMENT_NODES = 1_000_000
_INVALID_POINTER_ESCAPE = re.compile(r"~(?:[^01]|$)")
_MISSING = object()
_OPEN_JSON_PATHS = (
    "/world/observers/*/sense_modes/*",
    "/world/known_objects/*/state",
    "/world/combat_logs/*",
    "/observation_frames/*/patches/*/data",
    "/observation_frames/*/combat_log",
    "/agent_state/variables",
    "/agent_state/briefs/*/data",
    "/agent_state/alerts/*/data",
    "/agent_state/trace/*/data",
)
_DEFAULT_SEARCH_ROOTS = (
    "world",
    "observation_frames",
    "agent_state",
    "predicates",
    "representation",
)


class InspectionError(RuntimeError):
    """Base error for invalid or unavailable local inspection operations."""


class InspectionSerializationError(InspectionError):
    """Raised when an input cannot be represented as finite canonical JSON."""


class InspectionDocumentTooLarge(InspectionError):
    """Raised when one immutable document exceeds its archive byte budget."""


class InspectionModel(BaseModel):
    """Immutable base for local inspection contracts."""

    model_config = ConfigDict(frozen=True)


class InspectionAgentWorkspace(InspectionModel):
    """Inspectable subjective derivations with policy recommendations excluded."""

    facts: Optional[AgentFacts] = Field(default=None, description="Typed facts derived from the subjective world.")
    variables: dict[str, Any] = Field(default_factory=dict, description="Named postprocessor outputs.")
    briefs: tuple[BriefEmission, ...] = Field(default_factory=tuple, description="Postprocessor text and data emissions.")
    alerts: tuple[Alert, ...] = Field(default_factory=tuple, description="Postprocessor alerts.")
    trace: tuple[TraceEmission, ...] = Field(default_factory=tuple, description="Postprocessor trace records.")
    omitted_policy_hint_count: int = Field(
        default=0,
        ge=0,
        description="Policy recommendations deliberately excluded from subjective inspection.",
    )


class JsonValueType(str, Enum):
    """JSON value categories reported without inspecting Python object types."""

    NULL = "null"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    STRING = "string"
    ARRAY = "array"
    OBJECT = "object"


class InspectionRevision(InspectionModel):
    """Identity of one immutable subjective inspection materialization."""

    session_id: str = Field(description="Controller session represented by the document.")
    encounter_uuid: Optional[str] = Field(default=None, description="Subjectively known encounter UUID.")
    observation_cursor: int = Field(ge=0, description="Highest subjective cursor represented.")
    epoch_id: Optional[str] = Field(default=None, description="Current decision epoch, when present.")
    actor_uuid: Optional[str] = Field(default=None, description="Current epoch actor, when present.")
    materialization_generation: int = Field(
        default=0,
        ge=0,
        description="Generation incremented when the local materializer is replaced or resynced.",
    )
    processor_generation: int = Field(
        default=0,
        ge=0,
        description="Generation of the processor and predicate inputs.",
    )
    profile_digest: str = Field(description="Digest identifying the representation manifest.")
    schema_digest: str = Field(description="Digest identifying the serialization schemas.")
    document_digest: str = Field(description="SHA-256 digest of the exact canonical document bytes.")


class InspectionSchemaBundle(InspectionModel):
    """Versioned schemas and explicitly open JSON paths for an inspection view."""

    schema_digest: str = Field(description="SHA-256 digest of schemas and open-path declarations.")
    schemas: dict[str, JsonValue] = Field(description="Serialization schemas keyed by inspection root.")
    open_json_paths: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Paths whose upstream contracts intentionally contain open JSON values.",
    )


class InspectionGetStatus(str, Enum):
    """Outcome of one exact JSON Pointer lookup."""

    FOUND = "found"
    MISSING = "missing"
    INVALID_POINTER = "invalid_pointer"
    RESPONSE_LIMIT = "response_limit"


class InspectionGetRequest(InspectionModel):
    """Bounded exact lookups over one immutable document."""

    pointers: tuple[str, ...] = Field(description="RFC 6901 JSON Pointers to retrieve.")
    max_depth: int = Field(default=64, ge=1, le=_MAX_DOCUMENT_DEPTH, description="Maximum pointer depth.")
    max_response_bytes: int = Field(
        default=256_000,
        ge=64,
        le=8_000_000,
        description="Maximum canonical bytes returned across found values.",
    )

    @model_validator(mode="after")
    def validate_pointer_count(self) -> "InspectionGetRequest":
        """Keep exact lookup batches bounded and non-empty."""
        if not self.pointers:
            raise ValueError("At least one JSON Pointer is required")
        if len(self.pointers) > 64:
            raise ValueError("At most 64 JSON Pointers may be requested")
        return self


class InspectionGetItem(InspectionModel):
    """Result for one exact JSON Pointer."""

    pointer: str = Field(description="Requested JSON Pointer.")
    status: InspectionGetStatus = Field(description="Lookup result.")
    value_type: Optional[JsonValueType] = Field(default=None, description="Type of a found JSON value.")
    value: Optional[JsonValue] = Field(default=None, description="Found value; use status to distinguish null from missing.")
    value_bytes: int = Field(default=0, ge=0, description="Canonical byte size of a found value.")
    message: Optional[str] = Field(default=None, description="Structured failure explanation.")


class InspectionGetResult(InspectionModel):
    """Revision-fenced results for a batch of exact lookups."""

    revision: InspectionRevision = Field(description="Immutable document revision queried.")
    items: tuple[InspectionGetItem, ...] = Field(description="Results in request order.")
    returned_bytes: int = Field(ge=0, description="Canonical bytes returned across found values.")


class InspectionSearchMode(str, Enum):
    """Safe literal matching modes supported by local search."""

    CONTAINS = "contains"
    EXACT = "exact"
    PREFIX = "prefix"


class InspectionSearchMatchKind(str, Enum):
    """Which part of a canonical node matched a search pattern."""

    PATH = "path"
    VALUE = "value"
    PATH_AND_VALUE = "path_and_value"


class InspectionSearchRequest(InspectionModel):
    """Bounded literal search over canonical paths and scalar values."""

    pattern: str = Field(min_length=1, max_length=256, description="Literal search pattern.")
    mode: InspectionSearchMode = Field(default=InspectionSearchMode.CONTAINS, description="Literal match mode.")
    roots: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Top-level names or JSON Pointer roots; empty selects all inspectable roots.",
    )
    match_paths: bool = Field(default=True, description="Match canonical JSON Pointer paths.")
    match_values: bool = Field(default=True, description="Match canonical scalar renderings.")
    case_sensitive: bool = Field(default=False, description="Preserve case during matching.")
    scalar_types: tuple[JsonValueType, ...] = Field(
        default_factory=tuple,
        description="Optional accepted scalar types for value matches.",
    )
    offset: int = Field(default=0, ge=0, description="Zero-based match offset.")
    limit: int = Field(default=50, ge=1, le=200, description="Maximum returned hits.")
    max_nodes: int = Field(default=100_000, ge=16, le=_MAX_DOCUMENT_NODES, description="Maximum nodes scanned.")

    @model_validator(mode="after")
    def validate_search_targets(self) -> "InspectionSearchRequest":
        """Require at least one bounded search target."""
        if not self.match_paths and not self.match_values:
            raise ValueError("Search must match paths, values, or both")
        if len(self.roots) > 32:
            raise ValueError("At most 32 search roots may be requested")
        return self


class InspectionSearchHit(InspectionModel):
    """One deterministic canonical search match."""

    pointer: str = Field(description="JSON Pointer identifying the matched node.")
    root: str = Field(description="Requested root that produced the match.")
    match_kind: InspectionSearchMatchKind = Field(description="Whether path, value, or both matched.")
    value_type: JsonValueType = Field(description="JSON type at the matched node.")
    preview: str = Field(description="Bounded human-readable value preview.")


class InspectionSearchResult(InspectionModel):
    """Bounded deterministic search results for one immutable revision."""

    revision: InspectionRevision = Field(description="Immutable document revision searched.")
    hits: tuple[InspectionSearchHit, ...] = Field(description="Matches after offset and limit.")
    scanned_nodes: int = Field(ge=0, description="Canonical nodes visited.")
    total_matches: int = Field(ge=0, description="Matches observed before paging.")
    total_matches_is_exact: bool = Field(description="Whether the node budget allowed a complete count.")
    truncated: bool = Field(description="Whether paging or the node budget omitted matches.")
    unknown_roots: tuple[str, ...] = Field(default_factory=tuple, description="Requested roots absent or invalid.")


class InspectionExport(InspectionModel):
    """Complete canonical subjective document suitable for local jq or rg use."""

    revision: InspectionRevision = Field(description="Exported immutable revision.")
    document_digest: str = Field(description="SHA-256 digest of canonical_json UTF-8 bytes.")
    byte_count: int = Field(ge=0, description="Canonical document byte count.")
    canonical_json: str = Field(description="Complete canonical JSON document.")


class InspectionRootSummary(InspectionModel):
    """Discoverable canonical root and its immediate item count."""

    name: str = Field(description="Stable catalog name.")
    pointer: str = Field(description="JSON Pointer for this root.")
    value_type: JsonValueType = Field(description="JSON type at the root.")
    item_count: int = Field(ge=0, description="Immediate child count or scalar presence count.")


class InspectionCatalog(InspectionModel):
    """Discoverability metadata for one immutable subjective document."""

    revision: InspectionRevision = Field(description="Cataloged immutable revision.")
    roots: tuple[InspectionRootSummary, ...] = Field(description="Allowlisted inspection roots.")
    schemas: tuple[str, ...] = Field(description="Available schema names.")
    open_json_paths: tuple[str, ...] = Field(description="Explicitly open upstream JSON paths.")
    supported_operations: tuple[str, ...] = Field(description="Pure local operations supported by this slice.")


class ArchiveLookupStatus(str, Enum):
    """Retention state of a canonical document digest."""

    RETAINED = "retained"
    EVICTED = "evicted"
    UNKNOWN = "unknown"


class InspectionDiffOperation(str, Enum):
    """Structural canonical JSON changes."""

    ADD = "add"
    REMOVE = "remove"
    REPLACE = "replace"


class InspectionDiffRequest(InspectionModel):
    """Bounded structural comparison between two retained documents."""

    before_digest: str = Field(min_length=64, max_length=64, description="Earlier document digest.")
    after_digest: str = Field(min_length=64, max_length=64, description="Later document digest.")
    root: str = Field(default="", description="Optional JSON Pointer limiting the comparison.")
    offset: int = Field(default=0, ge=0, description="Zero-based change offset.")
    limit: int = Field(default=100, ge=1, le=500, description="Maximum returned changes.")
    max_depth: int = Field(
        default=64,
        ge=1,
        le=_MAX_DOCUMENT_DEPTH,
        description="Maximum structural recursion depth.",
    )
    max_nodes: int = Field(
        default=100_000,
        ge=16,
        le=_MAX_DOCUMENT_NODES,
        description="Maximum compared JSON nodes.",
    )
    max_response_bytes: int = Field(
        default=512_000,
        ge=256,
        le=8_000_000,
        description="Maximum canonical bytes retained across returned changes.",
    )


class InspectionDiffEntry(InspectionModel):
    """One deterministic structural change with explicit value presence."""

    operation: InspectionDiffOperation = Field(description="Structural change kind.")
    pointer: str = Field(description="Canonical path of the changed value.")
    before_present: bool = Field(description="Whether the value existed before.")
    after_present: bool = Field(description="Whether the value exists after.")
    before: Optional[JsonValue] = Field(default=None, description="Earlier value, including explicit JSON null.")
    after: Optional[JsonValue] = Field(default=None, description="Later value, including explicit JSON null.")
    values_omitted: bool = Field(
        default=False,
        description="Whether large before or after values were omitted by the response-byte budget.",
    )


class InspectionDiffResult(InspectionModel):
    """Availability and bounded changes for an archive comparison."""

    before_status: ArchiveLookupStatus = Field(description="Retention state of the earlier digest.")
    after_status: ArchiveLookupStatus = Field(description="Retention state of the later digest.")
    available: bool = Field(description="Whether both requested revisions were compared.")
    root: str = Field(description="Requested comparison root.")
    changes: tuple[InspectionDiffEntry, ...] = Field(default_factory=tuple, description="Paged changes.")
    total_changes: int = Field(default=0, ge=0, description="Total deterministic changes before paging.")
    total_changes_is_exact: bool = Field(
        default=True,
        description="Whether traversal completed before its node or depth budget.",
    )
    scanned_nodes: int = Field(default=0, ge=0, description="Compared JSON nodes.")
    returned_bytes: int = Field(default=0, ge=0, description="Canonical bytes retained in returned changes.")
    truncated: bool = Field(default=False, description="Whether paging omitted changes.")
    error: Optional[str] = Field(default=None, description="Reason comparison was unavailable.")


@dataclass(frozen=True, slots=True)
class InspectionDocument:
    """Immutable canonical bytes and metadata for one subjective revision."""

    revision: InspectionRevision
    canonical_bytes: bytes
    schema_bytes: bytes

    def value(self) -> dict[str, JsonValue]:
        """Return a fresh JSON tree so callers cannot mutate archived state."""
        parsed = _decode_canonical_json(self.canonical_bytes)
        if not isinstance(parsed, dict):
            raise InspectionSerializationError("Inspection document root is not an object")
        return parsed

    def schema_bundle(self) -> InspectionSchemaBundle:
        """Return a fresh validated schema bundle."""
        parsed = _decode_canonical_json(self.schema_bytes)
        if not isinstance(parsed, dict):
            raise InspectionSerializationError("Inspection schema root is not an object")
        return InspectionSchemaBundle.model_validate(parsed)

    def export(self) -> InspectionExport:
        """Return the complete canonical artifact and its exact digest."""
        return InspectionExport(
            revision=self.revision,
            document_digest=self.revision.document_digest,
            byte_count=len(self.canonical_bytes),
            canonical_json=self.canonical_bytes.decode("utf-8"),
        )

    def catalog(self) -> InspectionCatalog:
        """Describe allowlisted roots without exposing Python object internals."""
        value = self.value()
        root_specs = (
            ("world.session", "/world/session"),
            ("world.encounter", "/world/encounter"),
            ("world.observers", "/world/observers"),
            ("world.known_entities", "/world/known_entities"),
            ("world.known_objects", "/world/known_objects"),
            ("world.known_tiles", "/world/known_tiles"),
            ("world.current_epoch", "/world/current_epoch"),
            ("world.combat_logs", "/world/combat_logs"),
            ("observation_frames", "/observation_frames"),
            ("agent_state", "/agent_state"),
            ("predicates", "/predicates"),
            ("representation", "/representation"),
        )
        summaries: list[InspectionRootSummary] = []
        for name, pointer in root_specs:
            found, root_value = _resolve_pointer(value, _parse_json_pointer(pointer))
            if not found:
                continue
            summaries.append(InspectionRootSummary(
                name=name,
                pointer=pointer,
                value_type=_json_value_type(root_value),
                item_count=_immediate_item_count(root_value),
            ))
        schema = self.schema_bundle()
        return InspectionCatalog(
            revision=self.revision,
            roots=tuple(summaries),
            schemas=tuple(sorted(schema.schemas)),
            open_json_paths=schema.open_json_paths,
            supported_operations=("catalog", "get", "search", "export", "schema", "archive", "diff"),
        )

    def get(self, request: InspectionGetRequest) -> InspectionGetResult:
        """Resolve exact RFC 6901 pointers against canonical JSON only."""
        value = self.value()
        items: list[InspectionGetItem] = []
        returned_bytes = 0
        for pointer in request.pointers:
            try:
                tokens = _parse_json_pointer(pointer)
                if not tokens:
                    raise ValueError("Root retrieval is available through export, not exact get")
                if len(tokens) > request.max_depth:
                    raise ValueError("Pointer exceeds max_depth")
            except ValueError as error:
                items.append(InspectionGetItem(
                    pointer=pointer,
                    status=InspectionGetStatus.INVALID_POINTER,
                    message=str(error),
                ))
                continue
            found, selected = _resolve_pointer(value, tokens)
            if not found:
                items.append(InspectionGetItem(pointer=pointer, status=InspectionGetStatus.MISSING))
                continue
            encoded = _canonical_json_bytes(selected)
            if returned_bytes + len(encoded) > request.max_response_bytes:
                items.append(InspectionGetItem(
                    pointer=pointer,
                    status=InspectionGetStatus.RESPONSE_LIMIT,
                    value_type=_json_value_type(selected),
                    value_bytes=len(encoded),
                    message="Found value exceeds the remaining response byte budget",
                ))
                continue
            returned_bytes += len(encoded)
            items.append(InspectionGetItem(
                pointer=pointer,
                status=InspectionGetStatus.FOUND,
                value_type=_json_value_type(selected),
                value=selected,
                value_bytes=len(encoded),
            ))
        return InspectionGetResult(
            revision=self.revision,
            items=tuple(items),
            returned_bytes=returned_bytes,
        )

    def search(self, request: InspectionSearchRequest) -> InspectionSearchResult:
        """Search canonical paths and scalar renderings without regular expressions."""
        document = self.value()
        roots, unknown_roots = _resolve_search_roots(document, request.roots)
        pattern = request.pattern if request.case_sensitive else request.pattern.casefold()
        accepted_scalar_types = set(request.scalar_types)
        hits: list[InspectionSearchHit] = []
        total_matches = 0
        scanned_nodes = 0
        node_budget_exhausted = False

        for root_pointer, root_value in roots:
            for pointer, node in _walk_json(root_value, root_pointer):
                if scanned_nodes >= request.max_nodes:
                    node_budget_exhausted = True
                    break
                scanned_nodes += 1
                path_text = pointer if request.case_sensitive else pointer.casefold()
                path_matches = request.match_paths and _literal_matches(path_text, pattern, request.mode)
                node_type = _json_value_type(node)
                scalar_text = _scalar_text(node)
                value_matches = False
                if request.match_values and scalar_text is not None:
                    type_allowed = not accepted_scalar_types or node_type in accepted_scalar_types
                    candidate = scalar_text if request.case_sensitive else scalar_text.casefold()
                    value_matches = type_allowed and _literal_matches(candidate, pattern, request.mode)
                if not path_matches and not value_matches:
                    continue
                match_kind = (
                    InspectionSearchMatchKind.PATH_AND_VALUE
                    if path_matches and value_matches
                    else InspectionSearchMatchKind.PATH
                    if path_matches
                    else InspectionSearchMatchKind.VALUE
                )
                if request.offset <= total_matches < request.offset + request.limit:
                    hits.append(InspectionSearchHit(
                        pointer=pointer,
                        root=root_pointer,
                        match_kind=match_kind,
                        value_type=node_type,
                        preview=_preview(node),
                    ))
                total_matches += 1
            if node_budget_exhausted:
                break

        paging_omitted = total_matches > request.offset + len(hits)
        return InspectionSearchResult(
            revision=self.revision,
            hits=tuple(hits),
            scanned_nodes=scanned_nodes,
            total_matches=total_matches,
            total_matches_is_exact=not node_budget_exhausted,
            truncated=node_budget_exhausted or paging_omitted,
            unknown_roots=unknown_roots,
        )


class InspectionArchive:
    """Thread-safe bounded retention of immutable inspection documents."""

    def __init__(self, *, max_documents: int = 32, max_bytes: int = 64 * 1024 * 1024) -> None:
        """Create a count- and byte-bounded archive."""
        if max_documents < 1:
            raise ValueError("max_documents must be positive")
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        self.max_documents = max_documents
        self.max_bytes = max_bytes
        self._documents: OrderedDict[str, InspectionDocument] = OrderedDict()
        self._evicted: OrderedDict[str, None] = OrderedDict()
        self._total_bytes = 0
        self._lock = RLock()

    @property
    def total_bytes(self) -> int:
        """Return retained canonical document bytes."""
        with self._lock:
            return self._total_bytes

    def add(self, document: InspectionDocument) -> tuple[str, ...]:
        """Retain a document and return digests evicted by the bounds."""
        digest = document.revision.document_digest
        size = len(document.canonical_bytes)
        if size > self.max_bytes:
            raise InspectionDocumentTooLarge(
                f"Document requires {size} bytes but archive allows {self.max_bytes}"
            )
        with self._lock:
            if digest in self._documents:
                return tuple()
            self._documents[digest] = document
            self._total_bytes += size
            evicted: list[str] = []
            while len(self._documents) > self.max_documents or self._total_bytes > self.max_bytes:
                old_digest, old_document = self._documents.popitem(last=False)
                self._total_bytes -= len(old_document.canonical_bytes)
                evicted.append(old_digest)
                self._evicted[old_digest] = None
            tombstone_limit = max(16, self.max_documents * 4)
            while len(self._evicted) > tombstone_limit:
                self._evicted.popitem(last=False)
            return tuple(evicted)

    def lookup(self, digest: str) -> tuple[ArchiveLookupStatus, Optional[InspectionDocument]]:
        """Return a retained immutable document or its known retention status."""
        with self._lock:
            document = self._documents.get(digest)
            if document is not None:
                return ArchiveLookupStatus.RETAINED, document
            if digest in self._evicted:
                return ArchiveLookupStatus.EVICTED, None
            return ArchiveLookupStatus.UNKNOWN, None

    def diff(self, request: InspectionDiffRequest) -> InspectionDiffResult:
        """Compare two retained canonical documents structurally."""
        before_status, before_document = self.lookup(request.before_digest)
        after_status, after_document = self.lookup(request.after_digest)
        if before_document is None or after_document is None:
            return InspectionDiffResult(
                before_status=before_status,
                after_status=after_status,
                available=False,
                root=request.root,
                error="Both document digests must be retained for diff",
            )
        try:
            tokens = _parse_json_pointer(request.root)
        except ValueError as error:
            return InspectionDiffResult(
                before_status=before_status,
                after_status=after_status,
                available=False,
                root=request.root,
                error=str(error),
            )
        before_found, before_value = _resolve_pointer(before_document.value(), tokens)
        after_found, after_value = _resolve_pointer(after_document.value(), tokens)
        accumulator = _DiffAccumulator(request=request)
        _diff_json(
            before_value if before_found else _MISSING,
            after_value if after_found else _MISSING,
            request.root,
            accumulator,
        )
        return InspectionDiffResult(
            before_status=before_status,
            after_status=after_status,
            available=True,
            root=request.root,
            changes=tuple(accumulator.changes),
            total_changes=accumulator.total_changes,
            total_changes_is_exact=not accumulator.exhausted,
            scanned_nodes=accumulator.scanned_nodes,
            returned_bytes=accumulator.returned_bytes,
            truncated=(
                accumulator.exhausted
                or accumulator.total_changes > request.offset + len(accumulator.changes)
                or any(change.values_omitted for change in accumulator.changes)
            ),
        )


def capture_inspection_document(
    *,
    world: SubjectiveWorldState,
    agent_state: AgentState,
    observation_frames: Sequence[ObservationFrame] = (),
    predicates: InspectionSource,
    representation: InspectionSource,
    materialization_generation: int = 0,
    processor_generation: int = 0,
    profile_digest: Optional[str] = None,
) -> InspectionDocument:
    """Capture one immutable allowlisted local subjective document.

    Args:
        world: Complete locally materialized session-subjective state.
        agent_state: Derived local agent workspace for the same revision.
        observation_frames: Complete locally retained subjective envelopes.
        predicates: Predicate ledger or JSON-compatible predicate manifest.
        representation: Resolved representation manifest or JSON mapping.
        materialization_generation: Local materializer/resync generation.
        processor_generation: Local processor and predicate generation.
        profile_digest: Explicit resolved profile digest; defaults to the
            canonical representation input digest.

    Returns:
        Immutable canonical document containing only the allowlisted inputs.

    Raises:
        InspectionSerializationError: If an input is not finite canonical JSON.
    """
    world_json = _normalize_json(world)
    inspectable_agent_state = InspectionAgentWorkspace(
        facts=agent_state.facts,
        variables=agent_state.variables,
        briefs=tuple(agent_state.briefs),
        alerts=tuple(agent_state.alerts),
        trace=tuple(agent_state.trace),
        omitted_policy_hint_count=len(agent_state.hints),
    )
    agent_state_json = _normalize_json(inspectable_agent_state)
    observation_frames_json = _normalize_json(tuple(observation_frames))
    predicates_json = _normalize_json(predicates)
    representation_json = _normalize_json(representation)
    if not isinstance(world_json, dict) or not isinstance(agent_state_json, dict):
        raise InspectionSerializationError("World and agent_state must serialize as objects")
    if not isinstance(predicates_json, dict) or not isinstance(representation_json, dict):
        raise InspectionSerializationError("Predicates and representation must serialize as objects")

    schema_payload = {
        "schemas": {
            "world": _normalize_json(SubjectiveWorldState.model_json_schema(mode="serialization")),
            "observation_frames": _normalize_json(
                TypeAdapter(tuple[ObservationFrame, ...]).json_schema(mode="serialization")
            ),
            "agent_state": _normalize_json(InspectionAgentWorkspace.model_json_schema(mode="serialization")),
            "predicates": _source_schema(predicates),
            "representation": _source_schema(representation),
            "inspection_get_request": _normalize_json(InspectionGetRequest.model_json_schema(mode="serialization")),
            "inspection_get_result": _normalize_json(InspectionGetResult.model_json_schema(mode="serialization")),
            "inspection_search_request": _normalize_json(InspectionSearchRequest.model_json_schema(mode="serialization")),
            "inspection_search_result": _normalize_json(InspectionSearchResult.model_json_schema(mode="serialization")),
            "inspection_diff_request": _normalize_json(InspectionDiffRequest.model_json_schema(mode="serialization")),
            "inspection_diff_result": _normalize_json(InspectionDiffResult.model_json_schema(mode="serialization")),
        },
        "open_json_paths": list(_OPEN_JSON_PATHS),
    }
    schema_digest = _sha256_bytes(_canonical_json_bytes(schema_payload))
    schema_bundle = InspectionSchemaBundle(
        schema_digest=schema_digest,
        schemas=cast(dict[str, JsonValue], schema_payload["schemas"]),
        open_json_paths=_OPEN_JSON_PATHS,
    )
    schema_bytes = _canonical_json_bytes(schema_bundle)

    epoch = world.current_epoch
    encounter = world.encounter
    resolved_profile_digest = profile_digest or _sha256_bytes(_canonical_json_bytes(representation_json))
    revision_payload: dict[str, JsonValue] = {
        "session_id": world.session.session_id,
        "encounter_uuid": encounter.uuid if encounter is not None else None,
        "observation_cursor": world.observation_cursor,
        "epoch_id": epoch.epoch_id if epoch is not None else None,
        "actor_uuid": epoch.actor_uuid if epoch is not None else None,
        "materialization_generation": materialization_generation,
        "processor_generation": processor_generation,
        "profile_digest": resolved_profile_digest,
        "schema_digest": schema_digest,
    }
    document_value: dict[str, JsonValue] = {
        "revision": revision_payload,
        "world": world_json,
        "observation_frames": observation_frames_json,
        "agent_state": agent_state_json,
        "predicates": predicates_json,
        "representation": representation_json,
    }
    canonical_bytes = _canonical_json_bytes(document_value)
    document_digest = _sha256_bytes(canonical_bytes)
    revision = InspectionRevision(
        session_id=world.session.session_id,
        encounter_uuid=encounter.uuid if encounter is not None else None,
        observation_cursor=world.observation_cursor,
        epoch_id=epoch.epoch_id if epoch is not None else None,
        actor_uuid=epoch.actor_uuid if epoch is not None else None,
        materialization_generation=materialization_generation,
        processor_generation=processor_generation,
        profile_digest=resolved_profile_digest,
        schema_digest=schema_digest,
        document_digest=document_digest,
    )
    return InspectionDocument(
        revision=revision,
        canonical_bytes=canonical_bytes,
        schema_bytes=schema_bytes,
    )


def _normalize_json(value: object, *, _depth: int = 0, _nodes: Optional[list[int]] = None) -> JsonValue:
    """Convert supported typed inputs into deterministic finite JSON values."""
    nodes = _nodes if _nodes is not None else [0]
    nodes[0] += 1
    if nodes[0] > _MAX_DOCUMENT_NODES:
        raise InspectionSerializationError("Inspection input exceeds the node limit")
    if _depth > _MAX_DOCUMENT_DEPTH:
        raise InspectionSerializationError("Inspection input exceeds the depth limit")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InspectionSerializationError("Inspection input contains a non-finite float")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise InspectionSerializationError("Inspection input contains a non-finite decimal")
        return str(value)
    if isinstance(value, Enum):
        return _normalize_json(value.value, _depth=_depth + 1, _nodes=nodes)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return _normalize_json(
            value.model_dump(mode="python", round_trip=True, warnings=False),
            _depth=_depth + 1,
            _nodes=nodes,
        )
    if isinstance(value, Mapping):
        normalized: dict[str, JsonValue] = {}
        for key, child in value.items():
            json_key = _normalize_json_key(key)
            if json_key in normalized:
                raise InspectionSerializationError(f"JSON key collision after normalization: {json_key}")
            normalized[json_key] = _normalize_json(child, _depth=_depth + 1, _nodes=nodes)
        return {key: normalized[key] for key in sorted(normalized)}
    if isinstance(value, (set, frozenset)):
        normalized_items = [
            _normalize_json(item, _depth=_depth + 1, _nodes=nodes)
            for item in value
        ]
        return sorted(normalized_items, key=_canonical_json_bytes)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _normalize_json(item, _depth=_depth + 1, _nodes=nodes)
            for item in value
        ]
    raise InspectionSerializationError(
        f"Unsupported inspection value type: {type(value).__module__}.{type(value).__qualname__}"
    )


def _normalize_json_key(key: object) -> str:
    """Convert only Pydantic-compatible scalar mapping keys to JSON object keys."""
    if isinstance(key, str):
        return key
    if isinstance(key, Enum):
        value = key.value
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            return str(value)
    if isinstance(key, UUID):
        return str(key)
    if isinstance(key, int) and not isinstance(key, bool):
        return str(key)
    raise InspectionSerializationError(f"Unsupported JSON object key type: {type(key).__qualname__}")


def _source_schema(source: InspectionSource) -> JsonValue:
    """Return a concrete source schema or an explicit open-object schema."""
    if isinstance(source, BaseModel):
        return _normalize_json(type(source).model_json_schema(mode="serialization"))
    return {
        "type": "object",
        "additionalProperties": True,
        "description": "JSON-compatible mapping supplied by the local representation runtime.",
    }


def _canonical_json_bytes(value: object) -> bytes:
    """Serialize a normalized value into one stable finite JSON representation."""
    normalized = value if _is_normalized_json(value) else _normalize_json(value)
    return json.dumps(
        normalized,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _is_normalized_json(value: object) -> bool:
    """Return whether a value is already a finite plain JSON tree."""
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_normalized_json(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_normalized_json(item) for key, item in value.items())
    return False


def _decode_canonical_json(payload: bytes) -> JsonValue:
    """Decode trusted canonical bytes into a fresh plain JSON tree."""
    return cast(JsonValue, json.loads(payload.decode("utf-8")))


def _sha256_bytes(payload: bytes) -> str:
    """Return the lowercase SHA-256 digest of exact bytes."""
    return sha256(payload).hexdigest()


def _parse_json_pointer(pointer: str) -> tuple[str, ...]:
    """Parse an RFC 6901 JSON Pointer and reject malformed escapes."""
    if pointer == "":
        return tuple()
    if not pointer.startswith("/"):
        raise ValueError("JSON Pointer must be empty or begin with '/'")
    tokens: list[str] = []
    for token in pointer[1:].split("/"):
        if _INVALID_POINTER_ESCAPE.search(token):
            raise ValueError("JSON Pointer contains an invalid '~' escape")
        tokens.append(token.replace("~1", "/").replace("~0", "~"))
    return tuple(tokens)


def _escape_pointer_token(token: str) -> str:
    """Escape one object key for an RFC 6901 JSON Pointer."""
    return token.replace("~", "~0").replace("/", "~1")


def _resolve_pointer(root: JsonValue, tokens: tuple[str, ...]) -> tuple[bool, JsonValue]:
    """Resolve tokens through dictionaries and arrays without Python attributes."""
    current = root
    for token in tokens:
        if isinstance(current, dict):
            if token not in current:
                return False, None
            current = current[token]
            continue
        if isinstance(current, list):
            if not token.isdigit():
                return False, None
            index = int(token)
            if index >= len(current):
                return False, None
            current = current[index]
            continue
        return False, None
    return True, current


def _json_value_type(value: JsonValue) -> JsonValueType:
    """Classify a plain JSON value, preserving bool versus integer."""
    if value is None:
        return JsonValueType.NULL
    if isinstance(value, bool):
        return JsonValueType.BOOLEAN
    if isinstance(value, int):
        return JsonValueType.INTEGER
    if isinstance(value, float):
        return JsonValueType.NUMBER
    if isinstance(value, str):
        return JsonValueType.STRING
    if isinstance(value, list):
        return JsonValueType.ARRAY
    return JsonValueType.OBJECT


def _immediate_item_count(value: JsonValue) -> int:
    """Count immediate children, with present scalars counting as one."""
    if value is None:
        return 0
    if isinstance(value, (dict, list)):
        return len(value)
    return 1


def _literal_matches(candidate: str, pattern: str, mode: InspectionSearchMode) -> bool:
    """Apply one safe literal search mode."""
    if mode is InspectionSearchMode.EXACT:
        return candidate == pattern
    if mode is InspectionSearchMode.PREFIX:
        return candidate.startswith(pattern)
    return pattern in candidate


def _scalar_text(value: JsonValue) -> Optional[str]:
    """Render a scalar exactly as a searchable JSON value."""
    if isinstance(value, (dict, list)):
        return None
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _preview(value: JsonValue, *, limit: int = 160) -> str:
    """Return a bounded deterministic preview without exposing object reprs."""
    if isinstance(value, dict):
        rendered = f"{{{len(value)} keys}}"
    elif isinstance(value, list):
        rendered = f"[{len(value)} items]"
    else:
        rendered = _scalar_text(value) or ""
    return rendered if len(rendered) <= limit else rendered[:limit - 1] + "…"


def _walk_json(value: JsonValue, pointer: str):
    """Yield canonical nodes in deterministic depth-first order."""
    yield pointer, value
    if isinstance(value, dict):
        for key in sorted(value):
            child_pointer = f"{pointer}/{_escape_pointer_token(key)}"
            yield from _walk_json(value[key], child_pointer)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_json(child, f"{pointer}/{index}")


def _resolve_search_roots(
    document: dict[str, JsonValue],
    requested_roots: tuple[str, ...],
) -> tuple[tuple[tuple[str, JsonValue], ...], tuple[str, ...]]:
    """Resolve, sort, deduplicate, and de-overlap safe search roots."""
    raw_roots = requested_roots or _DEFAULT_SEARCH_ROOTS
    resolved: list[tuple[str, JsonValue]] = []
    unknown: list[str] = []
    for raw_root in sorted(set(raw_roots)):
        pointer = raw_root if raw_root.startswith("/") else f"/{_escape_pointer_token(raw_root)}"
        try:
            tokens = _parse_json_pointer(pointer)
        except ValueError:
            unknown.append(raw_root)
            continue
        found, value = _resolve_pointer(document, tokens)
        if not found:
            unknown.append(raw_root)
            continue
        if any(pointer == parent or pointer.startswith(parent + "/") for parent, _ in resolved):
            continue
        resolved = [
            (existing_pointer, existing_value)
            for existing_pointer, existing_value in resolved
            if not existing_pointer.startswith(pointer + "/")
        ]
        resolved.append((pointer, value))
        resolved.sort(key=lambda item: item[0])
    return tuple(resolved), tuple(unknown)


@dataclass(slots=True)
class _DiffAccumulator:
    """Bounded structural-diff traversal and page state."""

    request: InspectionDiffRequest
    changes: list[InspectionDiffEntry] = field(default_factory=list)
    scanned_nodes: int = 0
    total_changes: int = 0
    returned_bytes: int = 0
    exhausted: bool = False

    def add_change(self, change: InspectionDiffEntry) -> None:
        """Count one change and retain it only inside the requested bounded page."""
        change_index = self.total_changes
        self.total_changes += 1
        if not (
            self.request.offset <= change_index
            < self.request.offset + self.request.limit
        ):
            return
        encoded = _canonical_json_bytes(change)
        if self.returned_bytes + len(encoded) > self.request.max_response_bytes:
            change = change.model_copy(update={
                "before": None,
                "after": None,
                "values_omitted": True,
            })
            encoded = _canonical_json_bytes(change)
        if self.returned_bytes + len(encoded) > self.request.max_response_bytes:
            self.exhausted = True
            return
        self.changes.append(change)
        self.returned_bytes += len(encoded)


def _diff_json(
    before: object,
    after: object,
    pointer: str,
    accumulator: _DiffAccumulator,
    *,
    depth: int = 0,
) -> None:
    """Traverse deterministic changes while enforcing the caller's budgets."""
    if accumulator.exhausted:
        return
    if depth > accumulator.request.max_depth or accumulator.scanned_nodes >= accumulator.request.max_nodes:
        accumulator.exhausted = True
        return
    accumulator.scanned_nodes += 1
    if before is _MISSING:
        accumulator.add_change(InspectionDiffEntry(
            operation=InspectionDiffOperation.ADD,
            pointer=pointer,
            before_present=False,
            after_present=True,
            after=cast(JsonValue, after),
        ))
        return
    if after is _MISSING:
        accumulator.add_change(InspectionDiffEntry(
            operation=InspectionDiffOperation.REMOVE,
            pointer=pointer,
            before_present=True,
            after_present=False,
            before=cast(JsonValue, before),
        ))
        return
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            child_pointer = f"{pointer}/{_escape_pointer_token(key)}"
            _diff_json(
                before.get(key, _MISSING),
                after.get(key, _MISSING),
                child_pointer,
                accumulator,
                depth=depth + 1,
            )
            if accumulator.exhausted:
                break
        return
    if isinstance(before, list) and isinstance(after, list):
        for index in range(max(len(before), len(after))):
            child_pointer = f"{pointer}/{index}"
            before_item = before[index] if index < len(before) else _MISSING
            after_item = after[index] if index < len(after) else _MISSING
            _diff_json(
                before_item,
                after_item,
                child_pointer,
                accumulator,
                depth=depth + 1,
            )
            if accumulator.exhausted:
                break
        return
    if before != after:
        accumulator.add_change(InspectionDiffEntry(
            operation=InspectionDiffOperation.REPLACE,
            pointer=pointer,
            before_present=True,
            after_present=True,
            before=cast(JsonValue, before),
            after=cast(JsonValue, after),
        ))
