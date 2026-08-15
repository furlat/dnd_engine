"""Content-bound saving-throw context retained until ContentRef removal."""

from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from dnd.core.content.identities import (
    ContentDefinitionKind,
    ContentRef,
    validate_namespaced_id,
)
from dnd.types.saving_throws import SavingThrowEffectTag


class SavingThrowContext(BaseModel):
    """Exact authored cause of one saving throw.

    `cause_ref` identifies the action, spell, item, trait, or other authored
    definition that requested the save. `effect_id` distinguishes one stable
    effect within that definition. `condition_ref` is present only when the
    save gates one exact condition definition.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    cause_ref: ContentRef
    effect_id: str
    condition_ref: ContentRef | None = None
    is_magical: bool
    effect_tags: tuple[SavingThrowEffectTag, ...] = ()

    @field_validator("effect_id")
    @classmethod
    def _validate_effect_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "effect_id")

    @model_validator(mode="after")
    def _validate_exact_facts(self) -> Self:
        if (
            self.condition_ref is not None
            and self.condition_ref.definition_kind
            is not ContentDefinitionKind.CONDITION
        ):
            raise ValueError("condition_ref must identify a condition")
        if self.effect_tags != tuple(
            sorted(set(self.effect_tags), key=lambda tag: tag.value),
        ):
            raise ValueError("effect tags must be unique and ordered")
        return self


__all__ = ["SavingThrowContext"]
