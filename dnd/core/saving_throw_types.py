"""Dependency-neutral cause facts for saving-throw rules."""

from enum import Enum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationInfo,
    field_validator,
    model_validator,
)

from dnd.core.content.identities import validate_namespaced_id


SAVING_THROW_CONTEXT_KEY = "saving_throw_context"


class SavingThrowEffectTag(str, Enum):
    """Closed rule semantics used by contextual saving-throw features."""

    CHARM = "charm"
    FEAR = "fear"
    POISON = "poison"


class SavingThrowContext(BaseModel):
    """Exact authored cause of one saving throw.

    `cause_id` identifies the action, spell, item, trait, or other authored
    definition that requested the save. `effect_id` distinguishes one stable
    effect within that definition. `condition_id` is present only when the
    save gates one exact condition definition.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    cause_id: str
    effect_id: str
    condition_id: str | None = None
    is_magical: bool
    effect_tags: tuple[SavingThrowEffectTag, ...] = ()

    @field_validator("cause_id", "effect_id", "condition_id")
    @classmethod
    def _validate_semantic_id(
        cls,
        value: str | None,
        info: ValidationInfo,
    ) -> str | None:
        if value is None:
            return None
        return validate_namespaced_id(value, info.field_name)

    @model_validator(mode="after")
    def _validate_exact_facts(self) -> Self:
        if self.effect_tags != tuple(
            sorted(set(self.effect_tags), key=lambda tag: tag.value),
        ):
            raise ValueError("effect tags must be unique and ordered")
        return self


__all__ = [
    "SAVING_THROW_CONTEXT_KEY",
    "SavingThrowContext",
    "SavingThrowEffectTag",
]
