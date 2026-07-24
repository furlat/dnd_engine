"""Cold wire contracts shared by live timelines and archived replays.

This module intentionally does not import the engine event graph.  Objective
events cross this boundary as validated JSON values, so reading an archive can
never instantiate an :class:`Event`, touch a registry, or execute engine
construction logic.  The checked-in generated event manifest remains the
authority for every accepted discriminator, field, and JSON value shape.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any, Final, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.core.combat_log import CombatLogEntry


_EVENT_CONTRACT_PATH = Path(__file__).with_name("event_contract.generated.json")


class TimelineContractError(ValueError):
    """Raised when cold timeline data violates its checked-in wire contract."""


def _load_event_contract() -> dict[str, Any]:
    """Load and authenticate the generated manifest without importing Event."""
    contract = json.loads(_EVENT_CONTRACT_PATH.read_text(encoding="utf-8"))
    expected_hash = contract.get("contract_hash")
    unhashed = {key: value for key, value in contract.items() if key != "contract_hash"}
    canonical = json.dumps(unhashed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    actual_hash = hashlib.sha256(canonical).hexdigest()
    if expected_hash != actual_hash:
        raise TimelineContractError(
            "Generated event contract hash mismatch; regenerate the contract before reading timelines."
        )
    return contract


_EVENT_CONTRACT: Final[dict[str, Any]] = _load_event_contract()
EVENT_CONTRACT_VERSION: Final[int] = int(_EVENT_CONTRACT["contract_version"])
EVENT_CONTRACT_HASH: Final[str] = str(_EVENT_CONTRACT["contract_hash"])

TIMELINE_CONTRACT_VERSION: Final[int] = 1
TIMELINE_CONTRACT_HASH: Final[str]


class TimelineModel(BaseModel):
    """Immutable, closed base for timeline transport values."""

    model_config = ConfigDict(frozen=True, extra="forbid")


def _fail(path: str, expectation: str) -> None:
    raise TimelineContractError(f"{path} must be {expectation}")


def _validate_json_value(value: Any, path: str) -> None:
    """Reject Python objects that are not already cold JSON values."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail(path, "a finite JSON number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                _fail(path, "a JSON object with string keys")
            _validate_json_value(item, f"{path}.{key}")
        return
    _fail(path, "a cold JSON value")


def _validate_model(value: Any, model_ref: str, path: str) -> None:
    if not isinstance(value, dict):
        _fail(path, f"an object matching {model_ref}")
    model_contract = _EVENT_CONTRACT["models"].get(model_ref)
    if model_contract is None:
        raise TimelineContractError(f"Generated event contract references unknown model {model_ref!r}")
    fields = model_contract["fields"]
    expected_fields = set(fields)
    actual_fields = set(value)
    if actual_fields != expected_fields:
        missing = sorted(expected_fields - actual_fields)
        unexpected = sorted(actual_fields - expected_fields)
        raise TimelineContractError(
            f"{path} drifted from {model_ref}: missing={missing}, unexpected={unexpected}"
        )
    for field_name, descriptor in fields.items():
        _validate_descriptor(value[field_name], descriptor, f"{path}.{field_name}")


def _validate_descriptor(value: Any, descriptor: Mapping[str, Any], path: str) -> None:
    """Validate one JSON value against a generated recursive descriptor."""
    kind = descriptor.get("kind")
    if kind == "json":
        _validate_json_value(value, path)
        return
    if kind == "null":
        if value is not None:
            _fail(path, "null")
        return
    if kind == "string":
        if not isinstance(value, str):
            _fail(path, "a string")
        return
    if kind == "boolean":
        if not isinstance(value, bool):
            _fail(path, "a boolean")
        return
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _fail(path, "a number")
        if isinstance(value, float) and not math.isfinite(value):
            _fail(path, "a finite number")
        return
    if kind == "literal":
        expected = descriptor.get("value")
        if value != expected or type(value) is not type(expected):
            _fail(path, f"the literal {expected!r}")
        return
    if kind == "enum":
        enum_ref = descriptor.get("ref")
        enum_contract = _EVENT_CONTRACT["enums"].get(enum_ref)
        if enum_contract is None:
            raise TimelineContractError(
                f"Generated event contract references unknown enum {enum_ref!r}"
            )
        if value not in enum_contract["values"]:
            _fail(path, f"one of {enum_contract['values']!r}")
        return
    if kind == "model":
        _validate_model(value, str(descriptor.get("ref")), path)
        return
    if kind == "array":
        if not isinstance(value, list):
            _fail(path, "an array")
        for index, item in enumerate(value):
            _validate_descriptor(item, descriptor["items"], f"{path}[{index}]")
        return
    if kind == "record":
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            _fail(path, "an object with string keys")
        for key, item in value.items():
            _validate_descriptor(item, descriptor["values"], f"{path}.{key}")
        return
    if kind == "tuple":
        if not isinstance(value, list):
            _fail(path, "a JSON tuple array")
        items = descriptor["items"]
        if len(value) != len(items):
            _fail(path, f"a tuple array of length {len(items)}")
        for index, (item, item_descriptor) in enumerate(zip(value, items)):
            _validate_descriptor(item, item_descriptor, f"{path}[{index}]")
        return
    if kind == "union":
        for item_descriptor in descriptor["items"]:
            try:
                _validate_descriptor(value, item_descriptor, path)
            except TimelineContractError:
                continue
            return
        _fail(path, "one of the generated union alternatives")
    raise TimelineContractError(f"Unknown generated event descriptor kind {kind!r} at {path}")


class WireEvent(BaseModel):
    """A frozen concrete event represented entirely by validated JSON.

    Concrete event fields remain flat beside ``wire_type`` to preserve the
    generated transport shape byte-for-byte at the object level.  Extra fields
    are accepted by Pydantic only after the before-validator proves that they
    are exactly the fields declared for the concrete discriminator.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    wire_type: str = Field(min_length=1, description="Generated concrete event discriminator.")
    event_type: str = Field(min_length=1, description="Semantic engine event category.")

    @model_validator(mode="before")
    @classmethod
    def validate_generated_event(cls, value: Any) -> Any:
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            _fail("event", "a JSON object")
        payload = dict(value)
        _validate_json_value(payload, "event")

        wire_type = payload.get("wire_type")
        if not isinstance(wire_type, str):
            _fail("event.wire_type", "a string")
        event_contract = _EVENT_CONTRACT["event_classes"].get(wire_type)
        if event_contract is None:
            raise TimelineContractError(
                f"Event class {wire_type!r} is absent from the generated event contract"
            )

        model_ref = str(event_contract["model"])
        event_payload = {key: item for key, item in payload.items() if key != "wire_type"}
        _validate_model(event_payload, model_ref, "event")
        if event_payload["event_type"] not in event_contract["event_types"]:
            raise TimelineContractError(
                f"Event class {wire_type!r} cannot carry semantic type "
                f"{event_payload['event_type']!r}"
            )
        return payload


class TimelineProtocolIdentity(TimelineModel):
    """Portable decoder identity shared by live streams and replay manifests."""

    timeline_contract_version: int = Field(default=TIMELINE_CONTRACT_VERSION, ge=1)
    timeline_contract_hash: str = Field(
        default_factory=lambda: TIMELINE_CONTRACT_HASH,
        min_length=1,
    )
    event_contract_version: int = Field(default=EVENT_CONTRACT_VERSION, ge=1)
    event_contract_hash: str = Field(default=EVENT_CONTRACT_HASH, min_length=1)

    @model_validator(mode="after")
    def validate_compatible_decoder(self) -> "TimelineProtocolIdentity":
        if self.timeline_contract_version != TIMELINE_CONTRACT_VERSION:
            raise ValueError("unsupported timeline contract version")
        if self.timeline_contract_hash != TIMELINE_CONTRACT_HASH:
            raise ValueError("timeline contract hash mismatch")
        if self.event_contract_version != EVENT_CONTRACT_VERSION:
            raise ValueError("unsupported generated event contract version")
        if self.event_contract_hash != EVENT_CONTRACT_HASH:
            raise ValueError("generated event contract hash mismatch")
        return self


class GameEventFrame(TimelineModel):
    """One exact objective event slot in a source timeline."""

    source_stream_id: str = Field(min_length=1, description="Timeline namespace owning the cursor.")
    generation_id: str = Field(min_length=1, description="Event generation containing this slot.")
    event_index: int = Field(ge=0, description="Zero-based authoritative storage index.")
    event_cursor: int = Field(ge=1, description="Consumed event cursor after this slot.")
    combat_log_cursor: int = Field(
        ge=0,
        description="Objective combat-log cursor captured with this event slot.",
    )
    event: WireEvent = Field(description="Cold generated-contract event payload.")

    @model_validator(mode="after")
    def validate_slot_identity(self) -> "GameEventFrame":
        if self.event_cursor != self.event_index + 1:
            raise ValueError("event_cursor must equal event_index + 1")
        return self


class GameEventFramesResponse(TimelineModel):
    """Exact retained cursor window of objective game-event frames."""

    source_stream_id: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    retained_from_cursor: int = Field(
        ge=0,
        description="Oldest consumed cursor from which exact replay is retained.",
    )
    from_cursor: int = Field(
        ge=0,
        description="Consumed event cursor immediately before this window.",
    )
    through_cursor: int = Field(
        ge=0,
        description="Exact event cursor represented through this response.",
    )
    frames: Tuple[GameEventFrame, ...] = Field(default_factory=tuple)
    total: int = Field(ge=0, description="Captured objective event cursor.")

    @model_validator(mode="after")
    def validate_exact_window(self) -> "GameEventFramesResponse":
        if self.retained_from_cursor > self.from_cursor:
            raise ValueError("from_cursor precedes retained event history")
        if self.from_cursor > self.through_cursor:
            raise ValueError("from_cursor must not exceed through_cursor")
        if self.through_cursor > self.total:
            raise ValueError("through_cursor must not exceed total")
        if len(self.frames) != self.through_cursor - self.from_cursor:
            raise ValueError("game-event frames must cover the exact cursor window")

        previous_combat_log_cursor = -1
        for expected_cursor, frame in enumerate(
            self.frames,
            start=self.from_cursor + 1,
        ):
            if frame.event_cursor != expected_cursor:
                raise ValueError("game-event frames must be contiguous and ordered")
            if frame.source_stream_id != self.source_stream_id:
                raise ValueError("game-event frame source stream does not match response")
            if frame.generation_id != self.generation_id:
                raise ValueError("game-event frame generation does not match response")
            if frame.combat_log_cursor < previous_combat_log_cursor:
                raise ValueError("game-event combat-log cursors must be nondecreasing")
            previous_combat_log_cursor = frame.combat_log_cursor
        return self


class CombatLogProjection(str, Enum):
    """Knowledge projection applied to a combat-log source slot."""

    SUBJECTIVE = "subjective"
    OBJECTIVE = "objective"


class _CombatLogFrameCore(TimelineModel):
    """Shared cursor and projection identity for cold combat-log slots."""

    source_stream_id: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    perspective_epoch_id: str = Field(
        min_length=1,
        description="Opaque identity of the authority that produced this projection.",
    )
    projection: CombatLogProjection
    combat_log_cursor: int = Field(ge=1)
    event_cursor: int = Field(
        ge=0,
        description="Causal source-event cursor forming the presentation barrier.",
    )


class CombatLogFrame(_CombatLogFrameCore):
    """One exact combat-log source slot under an explicit projection."""

    entry: Optional[CombatLogEntry] = Field(
        default=None,
        description="Projected entry, or a hidden subjective source slot.",
    )

    @model_validator(mode="after")
    def validate_projection_content(self) -> "CombatLogFrame":
        if self.projection is CombatLogProjection.OBJECTIVE and self.entry is None:
            raise ValueError("objective combat-log frames must contain an entry")
        return self


class CombatLogFramesResponse(TimelineModel):
    """Exact retained source-cursor window of projected combat-log frames."""

    source_stream_id: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    perspective_epoch_id: str = Field(min_length=1)
    projection: CombatLogProjection
    retained_from_cursor: int = Field(
        ge=0,
        description="Oldest consumed cursor from which exact replay is retained.",
    )
    from_cursor: int = Field(
        ge=0,
        description="Consumed source cursor immediately before this window.",
    )
    through_cursor: int = Field(
        ge=0,
        description="Exact source cursor represented through this response.",
    )
    frames: Tuple[CombatLogFrame, ...] = Field(default_factory=tuple)
    total: int = Field(ge=0, description="Captured source combat-log cursor.")

    @model_validator(mode="after")
    def validate_exact_window(self) -> "CombatLogFramesResponse":
        if self.retained_from_cursor > self.from_cursor:
            raise ValueError("from_cursor precedes retained combat-log history")
        if self.from_cursor > self.through_cursor:
            raise ValueError("from_cursor must not exceed through_cursor")
        if self.through_cursor > self.total:
            raise ValueError("through_cursor must not exceed total")
        if len(self.frames) != self.through_cursor - self.from_cursor:
            raise ValueError("combat-log frames must cover the exact cursor window")

        previous_event_cursor = -1
        for expected_cursor, frame in enumerate(
            self.frames,
            start=self.from_cursor + 1,
        ):
            if frame.combat_log_cursor != expected_cursor:
                raise ValueError("combat-log frames must be contiguous and ordered")
            if frame.source_stream_id != self.source_stream_id:
                raise ValueError("combat-log frame source stream does not match response")
            if frame.generation_id != self.generation_id:
                raise ValueError("combat-log frame generation does not match response")
            if frame.perspective_epoch_id != self.perspective_epoch_id:
                raise ValueError("combat-log frame perspective epoch does not match response")
            if frame.projection is not self.projection:
                raise ValueError("combat-log frame projection does not match response")
            if frame.event_cursor < previous_event_cursor:
                raise ValueError("combat-log event cursors must be nondecreasing")
            previous_event_cursor = frame.event_cursor
        return self


class ObjectiveCombatLogFrame(_CombatLogFrameCore):
    """Compile-time closed objective combat-log slot with a concrete entry."""

    perspective_epoch_id: Literal["objective"] = "objective"
    projection: Literal[CombatLogProjection.OBJECTIVE] = CombatLogProjection.OBJECTIVE
    entry: CombatLogEntry


class ObjectiveCombatLogFramesResponse(CombatLogFramesResponse):
    """Compile-time closed objective combat-log window."""

    perspective_epoch_id: Literal["objective"] = "objective"
    projection: Literal[CombatLogProjection.OBJECTIVE] = CombatLogProjection.OBJECTIVE
    frames: Tuple[ObjectiveCombatLogFrame, ...] = Field(default_factory=tuple)


_TIMELINE_CONTRACT_SEMANTICS: Final[dict[str, Any]] = {
    "event_payload": "cold generated-event JSON with wire_type discriminator",
    "game_event_window": (
        "retained_from <= from <= through <= total; exact contiguous frames"
    ),
    "combat_log_projection": ("subjective", "objective"),
    "combat_log_window": (
        "retained_from <= from <= through <= total; exact contiguous frames"
    ),
    "objective_combat_log_entry": "non-null",
    "subjective_combat_log_entry": "nullable hidden source slot",
}


def timeline_wire_schema() -> dict[str, Any]:
    """Return the complete transitive schema authenticated by the timeline hash."""
    return {
        "contract_version": TIMELINE_CONTRACT_VERSION,
        "event_contract_version": EVENT_CONTRACT_VERSION,
        "event_contract_hash": EVENT_CONTRACT_HASH,
        "semantics": _TIMELINE_CONTRACT_SEMANTICS,
        "protocol": TimelineProtocolIdentity.model_json_schema(mode="serialization"),
        "wire_event": WireEvent.model_json_schema(mode="serialization"),
        "game_event_frame": GameEventFrame.model_json_schema(mode="serialization"),
        "game_event_window": GameEventFramesResponse.model_json_schema(
            mode="serialization"
        ),
        "combat_log_frame": CombatLogFrame.model_json_schema(mode="serialization"),
        "combat_log_window": CombatLogFramesResponse.model_json_schema(
            mode="serialization"
        ),
        "objective_combat_log_frame": ObjectiveCombatLogFrame.model_json_schema(
            mode="serialization"
        ),
        "objective_combat_log_window": (
            ObjectiveCombatLogFramesResponse.model_json_schema(mode="serialization")
        ),
    }


TIMELINE_CONTRACT_HASH = hashlib.sha256(
    json.dumps(
        timeline_wire_schema(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


def timeline_contract_summary() -> dict[str, Any]:
    """Return the portable decoder identity for metadata and diagnostics."""
    return TimelineProtocolIdentity().model_dump(mode="json")


__all__ = [
    "CombatLogFrame",
    "CombatLogFramesResponse",
    "CombatLogProjection",
    "EVENT_CONTRACT_HASH",
    "EVENT_CONTRACT_VERSION",
    "GameEventFrame",
    "GameEventFramesResponse",
    "ObjectiveCombatLogFrame",
    "ObjectiveCombatLogFramesResponse",
    "TIMELINE_CONTRACT_HASH",
    "TIMELINE_CONTRACT_VERSION",
    "TimelineContractError",
    "TimelineModel",
    "TimelineProtocolIdentity",
    "WireEvent",
    "timeline_contract_summary",
    "timeline_wire_schema",
]
