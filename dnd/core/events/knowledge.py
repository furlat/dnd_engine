"""Detached, path-level knowledge over the engine's real event classes.

This module does not define a presentation event schema.  It captures closed
source events by value, preserves their concrete classes, and controls which
existing model paths a consumer may read.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import date, datetime, time
from enum import Enum
from typing import Any, Generic, TypeAlias, TypeVar, cast
from uuid import UUID

from pydantic import BaseModel

from dnd.core.events.events_registry import Event, EventQueue


EventT = TypeVar("EventT", bound=Event)
ValueT = TypeVar("ValueT")
ResultT = TypeVar("ResultT")
ReadPath: TypeAlias = tuple[Hashable, ...]


class UnknownReason(str, Enum):
    """Stable reasons that an event value was not returned."""

    PATH_NOT_READABLE = "path_not_readable"
    PATH_NOT_FOUND = "path_not_found"
    NOT_COLD_VALUE = "not_cold_value"
    NO_CLASS_POLICY = "no_class_policy"
    TYPE_MISMATCH = "type_mismatch"


@dataclass(frozen=True, slots=True)
class Known(Generic[ValueT]):
    """A readable value, including an explicitly readable ``None``."""

    value: ValueT


@dataclass(frozen=True, slots=True)
class Unknown:
    """A path whose source value is not readable in this knowledge context."""

    reason: UnknownReason
    path: ReadPath = ()
    detail: str | None = None


Knowledge: TypeAlias = Known[ValueT] | Unknown


@dataclass(frozen=True, slots=True)
class KnowledgeDiagnostic:
    """Payload-free diagnostic for routing and policy failures."""

    reason: UnknownReason
    source_index: int
    event_class: str
    detail: str


@dataclass(frozen=True, slots=True)
class KnowledgeMask:
    """Readable paths over one unchanged concrete event value."""

    paths: frozenset[ReadPath] = frozenset()
    collection_paths: frozenset[ReadPath] = frozenset()
    allow_all: bool = False

    @classmethod
    def top(cls) -> KnowledgeMask:
        """Return objective knowledge, still subject to cold-value admission."""
        return cls(allow_all=True)

    @classmethod
    def from_paths(
        cls,
        *paths: ReadPath,
        collection_paths: Sequence[ReadPath] = (),
    ) -> KnowledgeMask:
        """Build a mask from explicit existing event paths."""
        return cls(
            paths=frozenset(paths),
            collection_paths=frozenset(collection_paths),
        )

    def permits(self, path: ReadPath, *, collection: bool = False) -> bool:
        """Return whether this mask admits the requested operation."""
        if self.allow_all:
            return True
        admitted = self.collection_paths if collection else self.paths
        return path in admitted

    def union(self, other: KnowledgeMask) -> KnowledgeMask:
        """Join two readers without changing any source value."""
        if self.allow_all or other.allow_all:
            return KnowledgeMask.top()
        return KnowledgeMask(
            paths=self.paths | other.paths,
            collection_paths=self.collection_paths | other.collection_paths,
        )

    def intersection(self, other: KnowledgeMask) -> KnowledgeMask:
        """Narrow readable paths without changing any source value."""
        if self.allow_all:
            return other
        if other.allow_all:
            return self
        return KnowledgeMask(
            paths=self.paths & other.paths,
            collection_paths=self.collection_paths & other.collection_paths,
        )


@dataclass(frozen=True, slots=True)
class CapturedEvent(Generic[EventT]):
    """One archive-owned detached snapshot at its original stream slot."""

    generation_id: UUID
    source_index: int
    _snapshot: EventT

    @property
    def event_class(self) -> type[EventT]:
        """Return the preserved concrete class without exposing the value."""
        return type(self._snapshot)

    @property
    def event_uuid(self) -> UUID:
        """Return source identity used for correlation and diagnostics."""
        return self._snapshot.uuid

    @property
    def lineage_uuid(self) -> UUID:
        """Return the unchanged source lineage identity."""
        return self._snapshot.lineage_uuid


_FORBIDDEN_ROOT_FIELDS = frozenset(
    {
        "attack_bonus",
        "combat_log",
        "condition",
        "context",
        "damage_rolls",
        "damages",
        "dice_roll",
        "event_handlers",
        "resolution",
        "source_item_state",
    }
)


def _path_value(root: object, path: ReadPath) -> tuple[bool, object]:
    current = root
    for component in path:
        if isinstance(current, BaseModel):
            model = cast(BaseModel, current)
            if not isinstance(component, str) or component not in type(model).model_fields:
                return False, None
            current = getattr(model, component)
            continue
        if isinstance(current, Mapping):
            if component not in current:
                return False, None
            current = current[component]
            continue
        if (
            isinstance(current, Sequence)
            and not isinstance(current, (str, bytes, bytearray))
            and isinstance(component, int)
        ):
            try:
                current = current[component]
            except IndexError:
                return False, None
            continue
        return False, None
    return True, current


def _frozen_dataclass(value: object) -> bool:
    parameters = getattr(type(value), "__dataclass_params__", None)
    return bool(is_dataclass(value) and parameters is not None and parameters.frozen)


def _cold_value(value: object) -> tuple[bool, object]:
    if value is None or isinstance(
        value,
        (bool, int, float, str, bytes, UUID, datetime, date, time, Enum),
    ):
        return True, value
    if isinstance(value, tuple):
        frozen: list[object] = []
        for item in value:
            admitted, cold = _cold_value(item)
            if not admitted:
                return False, None
            frozen.append(cold)
        return True, tuple(frozen)
    if isinstance(value, frozenset):
        frozen_items: list[object] = []
        for item in value:
            admitted, cold = _cold_value(item)
            if not admitted:
                return False, None
            frozen_items.append(cold)
        return True, frozenset(frozen_items)
    if isinstance(value, BaseModel) and value.model_config.get("frozen") is True:
        model = cast(BaseModel, value)
        updates: dict[str, object] = {}
        for name in type(model).model_fields:
            admitted, cold = _cold_value(getattr(model, name))
            if not admitted:
                return False, None
            updates[name] = cold
        return True, model.model_copy(update=updates, deep=True)
    if _frozen_dataclass(value):
        updates = {}
        for field in fields(cast(Any, value)):
            admitted, cold = _cold_value(getattr(value, field.name))
            if not admitted:
                return False, None
            updates[field.name] = cold
        return True, replace(cast(Any, value), **updates)
    return False, None


def _stable_key(value: object) -> tuple[str, str]:
    return type(value).__qualname__, str(value)


@dataclass(frozen=True, slots=True)
class EventKnowledge(Generic[EventT]):
    """Path-level read capability over one captured real event."""

    captured: CapturedEvent[EventT]
    mask: KnowledgeMask

    @property
    def event_class(self) -> type[EventT]:
        return self.captured.event_class

    def read(self, path: ReadPath) -> Knowledge[object]:
        """Read one admitted cold value from the captured source event."""
        if path and path[0] in _FORBIDDEN_ROOT_FIELDS:
            return Unknown(UnknownReason.NOT_COLD_VALUE, path)
        if not self.mask.permits(path):
            return Unknown(UnknownReason.PATH_NOT_READABLE, path)
        exists, value = _path_value(self.captured._snapshot, path)
        if not exists:
            return Unknown(UnknownReason.PATH_NOT_FOUND, path)
        admitted, cold = _cold_value(value)
        if not admitted:
            return Unknown(UnknownReason.NOT_COLD_VALUE, path)
        return Known(cold)

    def known_items(self, path: ReadPath) -> Knowledge[tuple[object, ...]]:
        """Read a mutable source collection as a detached immutable sequence."""
        if path and path[0] in _FORBIDDEN_ROOT_FIELDS:
            return Unknown(UnknownReason.NOT_COLD_VALUE, path)
        if not self.mask.permits(path, collection=True):
            return Unknown(UnknownReason.PATH_NOT_READABLE, path)
        exists, value = _path_value(self.captured._snapshot, path)
        if not exists:
            return Unknown(UnknownReason.PATH_NOT_FOUND, path)

        source_items: list[object]
        if isinstance(value, Mapping):
            source_items = []
            for key in sorted(value, key=_stable_key):
                admitted_key, cold_key = _cold_value(key)
                admitted_value, cold_value = _cold_value(value[key])
                if not admitted_key or not admitted_value:
                    return Unknown(UnknownReason.NOT_COLD_VALUE, path)
                source_items.append((cold_key, cold_value))
            return Known(tuple(source_items))
        if isinstance(value, (set, frozenset)):
            iterable = sorted(value, key=_stable_key)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            iterable = value
        else:
            return Unknown(UnknownReason.NOT_COLD_VALUE, path)
        source_items = []
        for item in iterable:
            admitted, cold = _cold_value(item)
            if not admitted:
                return Unknown(UnknownReason.NOT_COLD_VALUE, path)
            source_items.append(cold)
        return Known(tuple(source_items))

    def require_class(self, expected: type[EventT]) -> KnowledgeDiagnostic | None:
        """Return a structured diagnostic when a policy expects another class."""
        if self.event_class is expected:
            return None
        return KnowledgeDiagnostic(
            reason=UnknownReason.TYPE_MISMATCH,
            source_index=self.captured.source_index,
            event_class=self.event_class.__qualname__,
            detail=f"expected exact class {expected.__qualname__}",
        )


@dataclass(frozen=True, slots=True)
class EventDelivery(Generic[EventT]):
    """One consumer delivery backed by one captured real event."""

    knowledge: EventKnowledge[EventT]
    delivery_id: tuple[tuple[UUID, int, int], int] | None = None
    batch_id: tuple[UUID, int, int] | None = None
    disclosure_cause_source_index: int | None = None

    @classmethod
    def create(
        cls,
        knowledge: EventKnowledge[EventT],
        *,
        delivery_id: tuple[tuple[UUID, int, int], int] | None = None,
        batch_id: tuple[UUID, int, int] | None = None,
        disclosure_cause_source_index: int | None = None,
    ) -> EventDelivery[EventT]:
        return cls(
            knowledge=knowledge,
            delivery_id=delivery_id,
            batch_id=batch_id,
            disclosure_cause_source_index=disclosure_cause_source_index,
        )


BatchId: TypeAlias = tuple[UUID, int, int]
DeliveryId: TypeAlias = tuple[BatchId, int]


class SourceDisposition(str, Enum):
    """Payload-free disposition for one captured source slot."""

    DELIVERED = "delivered"
    INTENTIONALLY_SILENT = "intentionally_silent"
    HIDDEN = "hidden"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class SourceCoverage:
    """Accounting metadata owned by one current captured source slot."""

    generation_id: UUID
    source_index: int
    event_uuid: UUID
    disposition: SourceDisposition
    delivery_ids: tuple[DeliveryId, ...] = ()


@dataclass(frozen=True, slots=True)
class EventBatch:
    """One ordered closed source range prepared for consumption."""

    generation_id: UUID
    start: int
    stop: int
    deliveries: tuple[EventDelivery[Event], ...]
    coverage: tuple[SourceCoverage, ...] = ()
    diagnostics: tuple[KnowledgeDiagnostic, ...] = ()

    @property
    def batch_id(self) -> BatchId:
        """Return the stable identity of this closed source range."""
        return (self.generation_id, self.start, self.stop)


class EventArchive:
    """An immutable detached capture of one closed EventQueue range."""

    def __init__(self, entries: tuple[CapturedEvent[Event], ...]) -> None:
        self._entries = entries
        self._by_source_index = {entry.source_index: entry for entry in entries}

    @property
    def entries(self) -> tuple[CapturedEvent[Event], ...]:
        """Return metadata handles; archive-owned event values remain private."""
        return self._entries

    def get(self, source_index: int) -> CapturedEvent[Event]:
        return self._by_source_index[source_index]

    @classmethod
    def capture_queue_range(cls, start: int, stop: int | None = None) -> EventArchive:
        """Detach one exact stable range from the current EventQueue generation."""
        generation = EventQueue.generation_id()
        cursor = EventQueue.event_cursor()
        resolved_stop = cursor if stop is None else stop
        if not 0 <= start <= resolved_stop <= cursor:
            raise ValueError(
                f"invalid event range [{start}, {resolved_stop}) for cursor {cursor}"
            )

        source = [
            (index, event)
            for index, event in EventQueue.iter_events_since(start)
            if index < resolved_stop
        ]
        expected_indexes = list(range(start, resolved_stop))
        if [index for index, _ in source] != expected_indexes:
            raise RuntimeError("event source range is not contiguous")
        entries = tuple(
            CapturedEvent(
                generation_id=generation,
                source_index=index,
                _snapshot=cast(Event, event.model_copy(deep=True)),
            )
            for index, event in source
        )
        event_uuids = [entry.event_uuid for entry in entries]
        if len(event_uuids) != len(set(event_uuids)):
            raise RuntimeError("event source range contains duplicate UUIDs")
        if EventQueue.generation_id() != generation:
            raise RuntimeError("event queue generation changed during capture")
        if EventQueue.event_cursor() != cursor:
            raise RuntimeError("event queue cursor changed during capture")
        return cls(entries)


KnowledgeHandler: TypeAlias = Callable[[EventKnowledge[Event]], ResultT]


class EventKnowledgeRouter(Generic[ResultT]):
    """Exact concrete-event-class routing with no parallel kind system."""

    def __init__(self) -> None:
        self._handlers: dict[type[Event], KnowledgeHandler[ResultT]] = {}

    def register(
        self,
        event_class: type[EventT],
        handler: Callable[[EventKnowledge[EventT]], ResultT],
    ) -> None:
        if event_class in self._handlers:
            raise ValueError(f"handler already registered for {event_class.__qualname__}")
        self._handlers[event_class] = cast(KnowledgeHandler[ResultT], handler)

    def covered_classes(self) -> frozenset[type[Event]]:
        return frozenset(self._handlers)

    def dispatch(
        self,
        knowledge: EventKnowledge[Event],
    ) -> ResultT | KnowledgeDiagnostic:
        handler = self._handlers.get(knowledge.event_class)
        if handler is None:
            return KnowledgeDiagnostic(
                reason=UnknownReason.NO_CLASS_POLICY,
                source_index=knowledge.captured.source_index,
                event_class=knowledge.event_class.__qualname__,
                detail="no exact concrete-event-class policy",
            )
        return handler(knowledge)
