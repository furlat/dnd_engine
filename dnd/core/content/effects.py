"""Dependency-neutral authored condition-effect contracts.

These models describe what an authored definition can do.  They are not live
condition instances and they do not replace event lineage: runtime events
remain the authority for what actually happened.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from dnd.core.condition_types import (
    ConditionAgencyDenial,
    ConditionApplicationPolicy,
    ConditionRemovalTrigger,
    ConditionTag,
)
from dnd.core.content.identities import ContentRef


ConditionSaveAbility = Literal[
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
]


class ConditionEffectOperation(str, Enum):
    """Authored condition mutation performed by one effect."""

    APPLY = "apply"
    REMOVE = "remove"
    CLEANSE = "cleanse"
    REDUCE = "reduce"


class ConditionEffectCoverage(str, Enum):
    """How one authored definition participates in condition mutation."""

    PROFILED = "profiled"
    NONE = "none"
    INDIRECT = "indirect"
    INTERNAL_ONLY = "internal_only"
    LIFECYCLE_ONLY = "lifecycle_only"


class ConditionEffectTarget(str, Enum):
    """Stable target role used by authored condition effects."""

    ACTOR = "actor"
    SELECTED_TARGET = "selected_target"
    EACH_AFFECTED_ENTITY = "each_affected_entity"
    SELECTED_OBJECT = "selected_object"
    SOURCE_ITEM = "source_item"
    EQUIPPED_ITEM = "equipped_item"
    WORLD_POSITION = "world_position"
    CREATED_SPATIAL_EFFECT = "created_spatial_effect"


class ConditionEffectDisposition(str, Enum):
    """Tactical direction of an effect for its recipient."""

    BENEFICIAL = "beneficial"
    HARMFUL = "harmful"
    NEUTRAL = "neutral"


class ConditionAttackOutcome(str, Enum):
    """Attack outcomes usable as authored condition-effect gates."""

    HIT = "hit"
    CRITICAL = "critical"
    MISS = "miss"


class ConditionSaveOutcome(str, Enum):
    """Saving-throw outcomes usable as authored condition-effect gates."""

    FAILED = "failed"
    SUCCEEDED = "succeeded"


class ConditionActionOutcome(str, Enum):
    """Action or contest outcomes usable as authored effect gates."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ConditionSaveDCSource(str, Enum):
    """Authored origin of a condition-effect saving throw DC."""

    ACTOR_SPELL_SAVE_DC = "actor_spell_save_dc"
    ACTOR_ACTION_DC = "actor_action_dc"
    FIXED = "fixed"


class AutomaticConditionEffectGate(BaseModel):
    """Unconditional authored gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["automatic"] = "automatic"


class AttackOutcomeConditionEffectGate(BaseModel):
    """Gate requiring one of the listed attack outcomes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["attack_outcome"] = "attack_outcome"
    outcomes: tuple[ConditionAttackOutcome, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_unique_outcomes(self) -> Self:
        if len(self.outcomes) != len(set(self.outcomes)):
            raise ValueError("attack outcomes must be unique")
        return self


class SavingThrowConditionEffectGate(BaseModel):
    """Gate requiring an exact saving-throw outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["saving_throw"] = "saving_throw"
    ability: ConditionSaveAbility
    outcome: ConditionSaveOutcome
    dc_source: ConditionSaveDCSource
    fixed_dc: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_dc_source(self) -> Self:
        if self.dc_source is ConditionSaveDCSource.FIXED:
            if self.fixed_dc is None:
                raise ValueError("fixed saving-throw gates require fixed_dc")
        elif self.fixed_dc is not None:
            raise ValueError(
                "fixed_dc is valid only for a fixed saving-throw gate",
            )
        return self


class ActionOutcomeConditionEffectGate(BaseModel):
    """Gate requiring an action or contest outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["action_outcome"] = "action_outcome"
    outcomes: tuple[ConditionActionOutcome, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_unique_outcomes(self) -> Self:
        if len(self.outcomes) != len(set(self.outcomes)):
            raise ValueError("action outcomes must be unique")
        return self


class ConfigurationConditionEffectGate(BaseModel):
    """Gate selecting one exact authored configuration branch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["configuration"] = "configuration"
    configuration_key: str = Field(min_length=1)
    values: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_unique_values(self) -> Self:
        if len(self.values) != len(set(self.values)):
            raise ValueError("configuration gate values must be unique")
        return self


class OriginRootConditionEffectGate(BaseModel):
    """Gate requiring one exact item/object root that provided the behavior."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["origin_root"] = "origin_root"
    origin_root_refs: tuple[ContentRef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_unique_refs(self) -> Self:
        if len(self.origin_root_refs) != len(set(self.origin_root_refs)):
            raise ValueError("origin-root refs must be unique")
        return self


ConditionEffectGate = Annotated[
    AutomaticConditionEffectGate
    | AttackOutcomeConditionEffectGate
    | SavingThrowConditionEffectGate
    | ActionOutcomeConditionEffectGate
    | ConfigurationConditionEffectGate
    | OriginRootConditionEffectGate,
    Field(discriminator="kind"),
]


class ConditionEffectSelector(BaseModel):
    """Typed installed-content selector for an open-ended cleanse rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    required_tags: tuple[ConditionTag, ...] = ()
    required_removal_triggers: tuple[ConditionRemovalTrigger, ...] = ()
    resolved_condition_refs: tuple[ContentRef, ...] = ()

    @field_validator("required_tags", "required_removal_triggers", mode="before")
    @classmethod
    def _canonicalize_enum_values(cls, value):
        return tuple(sorted(
            value,
            key=lambda item: str(getattr(item, "value", item)),
        ))

    @model_validator(mode="after")
    def _validate_selector(self) -> Self:
        if not self.required_tags and not self.required_removal_triggers:
            raise ValueError(
                "condition effect selectors require tags or removal triggers",
            )
        return self


class AuthoredConditionEffect(BaseModel):
    """One ordered, exact condition mutation authored by a definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_id: str = Field(min_length=1)
    source_ref: ContentRef
    operation: ConditionEffectOperation
    condition_ref: ContentRef | None = None
    selector: ConditionEffectSelector | None = None
    target: ConditionEffectTarget

    @model_validator(mode="after")
    def _validate_condition_target(self) -> Self:
        if (self.condition_ref is None) == (self.selector is None):
            raise ValueError(
                "condition effects require exactly one exact condition ref "
                "or typed selector",
            )
        if (
            self.operation is ConditionEffectOperation.APPLY
            and self.condition_ref is None
        ):
            raise ValueError(
                "condition applications require one exact condition ref",
            )
        return self


class AuthoredConditionEffectBranch(BaseModel):
    """One applicability branch with an authoritative ordered effect list."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    branch_id: str = Field(min_length=1)
    disposition: ConditionEffectDisposition
    included_creature_types: tuple[str, ...] = ()
    excluded_creature_types: tuple[str, ...] = ()
    gates: tuple[ConditionEffectGate, ...] = Field(min_length=1)
    effects: tuple[AuthoredConditionEffect, ...] = Field(min_length=1)

    @field_validator(
        "included_creature_types",
        "excluded_creature_types",
        mode="before",
    )
    @classmethod
    def _canonicalize_creature_types(cls, value):
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _validate_branch(self) -> Self:
        overlap = (
            set(self.included_creature_types)
            & set(self.excluded_creature_types)
        )
        if overlap:
            raise ValueError(
                "included and excluded creature types cannot overlap",
            )
        gate_kinds = [gate.kind for gate in self.gates]
        if len(gate_kinds) != len(set(gate_kinds)):
            raise ValueError(
                "a condition effect branch cannot repeat a gate kind",
            )
        return self


class AuthoredConditionLifecycle(BaseModel):
    """Static lifecycle facts owned by one condition-capable definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    application_policy: ConditionApplicationPolicy = (
        ConditionApplicationPolicy.REPLACE_EXISTING
    )
    tags: tuple[ConditionTag, ...] = ()
    removal_triggers: tuple[ConditionRemovalTrigger, ...] = ()
    agency_denial: ConditionAgencyDenial = ConditionAgencyDenial.NONE

    @field_validator("tags", "removal_triggers", mode="before")
    @classmethod
    def _canonicalize_enum_values(cls, value):
        return tuple(sorted(
            value,
            key=lambda item: str(getattr(item, "value", item)),
        ))


class AuthoredConditionEffectProfile(BaseModel):
    """Complete authored condition behavior for one source definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    branches: tuple[AuthoredConditionEffectBranch, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> Self:
        branch_ids = [branch.branch_id for branch in self.branches]
        if len(branch_ids) != len(set(branch_ids)):
            raise ValueError("condition effect branch ids must be unique")
        effect_ids = [
            effect.effect_id
            for branch in self.branches
            for effect in branch.effects
        ]
        if len(effect_ids) != len(set(effect_ids)):
            raise ValueError(
                "condition effect ids must be unique across the profile",
            )
        return self

    @property
    def effects(self) -> tuple[AuthoredConditionEffect, ...]:
        """Return the authoritative branch/effect traversal order."""
        return tuple(
            effect
            for branch in self.branches
            for effect in branch.effects
        )


__all__ = [
    "AuthoredConditionEffect",
    "AuthoredConditionEffectBranch",
    "AuthoredConditionEffectProfile",
    "AuthoredConditionLifecycle",
    "ActionOutcomeConditionEffectGate",
    "AttackOutcomeConditionEffectGate",
    "AutomaticConditionEffectGate",
    "ConditionApplicationPolicy",
    "ConditionActionOutcome",
    "ConditionAttackOutcome",
    "ConditionEffectDisposition",
    "ConditionEffectCoverage",
    "ConditionEffectGate",
    "ConditionEffectOperation",
    "ConditionEffectSelector",
    "ConditionEffectTarget",
    "ConditionSaveDCSource",
    "ConditionSaveAbility",
    "ConditionSaveOutcome",
    "SavingThrowConditionEffectGate",
    "ConfigurationConditionEffectGate",
    "OriginRootConditionEffectGate",
]
