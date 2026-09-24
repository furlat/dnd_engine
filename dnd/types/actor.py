"""Recorded actor values shared by native producers and event consumers."""

from uuid import UUID
from typing import Literal

from dnd.core.creature_types import DamageType, Size
from dnd.types.abilities import AbilityName

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from dnd.core.condition_types import (
    ConditionAgencyDenial, ConditionCategory, ConditionRemovalTrigger, ConditionTag,
)


class OutcomeProtection(BaseModel):
    """Condition-owned rule that blocks specifically identified effects."""

    model_config = ConfigDict(frozen=True)

    protection_id: str
    blocked_effect_ids: frozenset[str] = Field(default_factory=frozenset)

    @field_serializer("blocked_effect_ids", when_used="json")
    def serialize_blocked_effect_ids(self, value: frozenset[str]) -> list[str]:
        return sorted(value)


class ConditionState(BaseModel):
    """Committed condition semantics without its executable runtime owner."""

    model_config = ConfigDict(frozen=True)

    condition_uuid: UUID
    name: str
    category: ConditionCategory
    semantic_key: str
    tags: tuple[ConditionTag, ...]
    removal_triggers: tuple[ConditionRemovalTrigger, ...]
    agency_denial: ConditionAgencyDenial
    outcome_protections: tuple[OutcomeProtection, ...]
    applied_source_event_cursor: int | None = None
    duplicate_count: int | None = Field(default=None, ge=0)
    size_change: Literal["enlarge", "reduce"] | None = None
    energy_type: DamageType | None = None
    enhanced_ability: AbilityName | None = None


class TemporaryHitPointsGrant(BaseModel):
    """Identity of the accepted temporary-HP pool, without its private donor."""

    model_config = ConfigDict(frozen=True)

    instance_uuid: UUID
    source_id: str | None = None


class EntityStatsState(BaseModel):
    """Native evaluated actor after-values; consumers do not reevaluate modifiers."""

    model_config = ConfigDict(frozen=True)

    normal_hp: int
    maximum_hp: int
    temporary_hp: int
    temporary_hp_grant: TemporaryHitPointsGrant | None = None
    armor_class: int
    healing_blocked: bool
    damage_affinities: tuple[tuple[str, str], ...]
    resolved_size: Size | None = None
