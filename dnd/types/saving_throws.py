"""Dependency-neutral saving-throw cause vocabulary and context."""

from enum import Enum
from typing import Optional, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


SAVING_THROW_CONTEXT_KEY = "saving_throw_context"


class SavingThrowEffectTag(str, Enum):
    """Closed rule semantics used by contextual saving-throw features."""

    CHARM = "charm"
    FEAR = "fear"
    POISON = "poison"


def _validate_semantic_id(value: str, field_name: str) -> str:
    if not value or value.strip() != value or "." not in value:
        raise ValueError(f"{field_name} must be a non-empty namespaced ID")
    return value


class SavingThrowContext(BaseModel):
    """Direct semantic cause and rule tags for one saving throw."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cause_id: str
    effect_id: str
    condition_id: Optional[str] = None
    is_magical: bool
    effect_tags: tuple[SavingThrowEffectTag, ...] = ()

    @field_validator("cause_id", "effect_id", "condition_id")
    @classmethod
    def _validate_ids(cls, value: Optional[str], info) -> Optional[str]:
        if value is None:
            return None
        return _validate_semantic_id(value, info.field_name)

    @model_validator(mode="after")
    def _validate_effect_tags(self) -> Self:
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
