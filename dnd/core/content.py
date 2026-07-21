"""Stable semantic identities used by content coverage and tooling."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ContentKind(str, Enum):
    """Engine content families with distinct runtime evidence lifecycles."""

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


class HandlerDispatchOutcome(str, Enum):
    """Observable result of one handler invocation by the event queue."""

    NO_EFFECT = "no_effect"
    EMITTED_EVENTS = "emitted_events"
    MODIFIED_EVENT = "modified_event"
    CANCELED_EVENT = "canceled_event"


class HandlerDispatchEvidence(BaseModel):
    """Passive evidence for one matched event or spatial handler invocation."""

    model_config = ConfigDict(frozen=True)

    dispatch_index: int = Field(ge=0, description="Monotonic handler-dispatch index in the active engine runtime.")
    handler_semantic_key: str = Field(description="Stable semantic identity declared by the handler.")
    handler_name: str = Field(description="Human-readable handler name retained for diagnosis.")
    content_kind: ContentKind = Field(description="Rules-content family represented by the handler.")
    handler_uuid: str = Field(description="Runtime handler UUID used only for within-match correlation.")
    source_entity_uuid: Optional[str] = Field(
        default=None,
        description="Runtime UUID of the entity or block that owns the handler.",
    )
    event_uuid: str = Field(description="Runtime UUID of the event version supplied to the handler.")
    lineage_uuid: str = Field(description="Runtime causal-lineage UUID of the triggering event.")
    event_type: str = Field(description="Engine event type that matched the handler.")
    event_phase: str = Field(description="Engine event phase that matched the handler.")
    outcome: HandlerDispatchOutcome = Field(description="Observable effect class of the invocation.")
    emitted_event_count: int = Field(
        ge=0,
        description="Number of engine event versions appended during the handler call.",
    )

    @property
    def effected(self) -> bool:
        """Whether the invocation produced an observable engine effect."""
        return self.outcome != HandlerDispatchOutcome.NO_EFFECT
