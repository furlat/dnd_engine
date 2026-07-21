"""Evaluator-only lifecycle evidence for engine rules content."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dnd.blocks.base_item import BaseItem, ItemChargeConsumptionEvent
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.base_object import BaseObject
from dnd.core.content import HandlerDispatchEvidence
from dnd.core.events import Event, EventPhase, EventQueue


class MatchContentCoverageEvidence(BaseModel):
    """Compact objective coverage evidence retained outside controller inputs."""

    model_config = ConfigDict(frozen=True)

    event_lifecycle_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Stored engine event versions counted by event type and phase.",
    )
    handler_opportunity_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Matched handler invocations by stable semantic key.",
    )
    handler_effect_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Handler invocations that modified, canceled, or emitted engine events.",
    )
    handler_metadata: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="Display names and typed content roles keyed by handler identity.",
    )
    condition_application_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Completed condition applications by stable condition identity.",
    )
    condition_removal_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Completed condition removals by stable condition identity.",
    )
    condition_metadata: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="Condition display names and content roles keyed by identity.",
    )
    item_consumption_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Completed finite item charge consumption by stable item identity.",
    )
    item_metadata: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="Consumed item display names keyed by stable item identity.",
    )


class MatchContentCoverageCollector:
    """Observe one match without changing event dispatch or agent subjectivity."""

    def __init__(self) -> None:
        self._event_lifecycle_counts: Counter[str] = Counter()
        self._handler_opportunity_counts: Counter[str] = Counter()
        self._handler_effect_counts: Counter[str] = Counter()
        self._handler_metadata: dict[str, dict[str, str]] = {}
        self._condition_application_counts: Counter[str] = Counter()
        self._condition_removal_counts: Counter[str] = Counter()
        self._condition_metadata: dict[str, dict[str, str]] = {}
        self._item_consumption_counts: Counter[str] = Counter()
        self._item_metadata: dict[str, dict[str, str]] = {}
        self._attached = False

    def attach(self) -> None:
        """Attach passive callbacks after arena construction and runtime reset."""
        if self._attached:
            return
        EventQueue.add_on_event_callback(self._on_event)
        EventQueue.add_on_handler_dispatch_callback(self._on_handler_dispatch)
        self._attached = True

    def detach(self) -> None:
        """Detach passive callbacks while preserving accumulated evidence."""
        if not self._attached:
            return
        EventQueue.remove_on_event_callback(self._on_event)
        EventQueue.remove_on_handler_dispatch_callback(self._on_handler_dispatch)
        self._attached = False

    def build(self) -> MatchContentCoverageEvidence:
        """Return an immutable, deterministically ordered evidence payload."""
        return MatchContentCoverageEvidence(
            event_lifecycle_counts=dict(sorted(self._event_lifecycle_counts.items())),
            handler_opportunity_counts=dict(sorted(self._handler_opportunity_counts.items())),
            handler_effect_counts=dict(sorted(self._handler_effect_counts.items())),
            handler_metadata=dict(sorted(self._handler_metadata.items())),
            condition_application_counts=dict(sorted(self._condition_application_counts.items())),
            condition_removal_counts=dict(sorted(self._condition_removal_counts.items())),
            condition_metadata=dict(sorted(self._condition_metadata.items())),
            item_consumption_counts=dict(sorted(self._item_consumption_counts.items())),
            item_metadata=dict(sorted(self._item_metadata.items())),
        )

    def _on_handler_dispatch(self, evidence: HandlerDispatchEvidence) -> None:
        key = evidence.handler_semantic_key
        self._handler_opportunity_counts[key] += 1
        if evidence.effected:
            self._handler_effect_counts[key] += 1
        self._handler_metadata[key] = {
            "display_name": evidence.handler_name,
            "content_kind": evidence.content_kind.value,
        }

    def _on_event(self, event: Event) -> None:
        self._event_lifecycle_counts[f"{event.event_type.value}:{event.phase.value}"] += 1
        if event.phase != EventPhase.COMPLETION:
            return
        if isinstance(event, ConditionApplicationEvent):
            self._record_condition(event.condition, self._condition_application_counts)
        elif isinstance(event, ConditionRemovalEvent):
            self._record_condition(event.condition, self._condition_removal_counts)
        elif isinstance(event, ItemChargeConsumptionEvent):
            item = BaseObject.get(event.item_uuid)
            key = event.item_semantic_key
            self._item_consumption_counts[key] += event.amount
            self._item_metadata[key] = {
                "display_name": str(item.name) if isinstance(item, BaseItem) else event.item_name,
                "content_kind": item.content_kind.value if isinstance(item, BaseItem) else "item",
            }

    def _record_condition(self, condition: Any, counter: Counter[str]) -> None:
        get_key = getattr(condition, "get_semantic_key", None)
        raw_key = get_key() if callable(get_key) else None
        key = raw_key if isinstance(raw_key, str) else f"{type(condition).__module__}.{type(condition).__name__}"
        counter[key] += 1
        get_kind = getattr(condition, "get_content_kind", None)
        raw_kind = get_kind() if callable(get_kind) else getattr(condition, "content_kind", None)
        kind = getattr(raw_kind, "value", "condition")
        self._condition_metadata[key] = {
            "display_name": str(getattr(condition, "name", type(condition).__name__)),
            "content_kind": str(kind),
        }
