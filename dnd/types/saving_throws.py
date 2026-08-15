"""Dependency-neutral saving-throw cause vocabulary."""

from enum import Enum


SAVING_THROW_CONTEXT_KEY = "saving_throw_context"


class SavingThrowEffectTag(str, Enum):
    """Closed rule semantics used by contextual saving-throw features."""

    CHARM = "charm"
    FEAR = "fear"
    POISON = "poison"


__all__ = ["SAVING_THROW_CONTEXT_KEY", "SavingThrowEffectTag"]

