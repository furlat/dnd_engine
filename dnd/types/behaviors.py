"""Dependency-leaf identities and evidence for executable rules behavior."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RuntimeBehaviorKind(str, Enum):
    """Engine behavior families with distinct runtime evidence lifecycles."""

    ACTION = "action"
    SPELL = "spell"
    REACTION = "reaction"
    TRAIT = "trait"
    FEAT = "feat"
    CLASS_FEATURE = "class_feature"
    CONDITION = "condition"
    ITEM = "item"
    ENVIRONMENT_INTERACTION = "environment_interaction"
    SYSTEM = "system"
    UNCLASSIFIED = "unclassified"


def validate_behavior_id(value: str, field_name: str = "behavior_id") -> str:
    """Validate one direct, renderer-independent semantic behavior identity."""
    if not value or value.strip() != value or "." not in value:
        raise ValueError(f"{field_name} must be a non-empty namespaced ID")
    return value


class HandlerDispatchOutcome(str, Enum):
    """Observable result of one handler invocation by the event queue."""

    NO_EFFECT = "no_effect"
    EMITTED_EVENTS = "emitted_events"
    MODIFIED_EVENT = "modified_event"
    CANCELED_EVENT = "canceled_event"


class HandlerDispatchEvidence(BaseModel):
    """Passive evidence for one matched event or spatial handler invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dispatch_index: int = Field(ge=0)
    handler_semantic_key: str = Field(min_length=1)
    handler_name: str = Field(min_length=1)
    content_kind: RuntimeBehaviorKind
    handler_uuid: str = Field(min_length=1)
    source_entity_uuid: Optional[str] = None
    event_uuid: str = Field(min_length=1)
    lineage_uuid: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    event_phase: str = Field(min_length=1)
    outcome: HandlerDispatchOutcome
    emitted_event_count: int = Field(ge=0)

    @property
    def effected(self) -> bool:
        """Whether the invocation produced an observable engine effect."""
        return self.outcome != HandlerDispatchOutcome.NO_EFFECT


@dataclass(frozen=True, slots=True)
class EffectiveHandlerPresentation:
    """Internal direct identity for one reaction that changed engine state."""

    dispatch_index: int
    handler_name: str
    behavior_id: str
    provided_by_id: str
    origin_root_id: Optional[str]
    source_entity_uuid: UUID
    triggering_event_uuid: UUID
    triggering_lineage_uuid: UUID
    emitted_lineage_uuids: tuple[UUID, ...]
    outcome: HandlerDispatchOutcome


__all__ = [
    "EffectiveHandlerPresentation",
    "HandlerDispatchEvidence",
    "HandlerDispatchOutcome",
    "RuntimeBehaviorKind",
    "validate_behavior_id",
]
