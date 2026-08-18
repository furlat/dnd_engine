"""Dependency-neutral structural facts granted by character origins."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.types.abilities import AbilityName
from dnd.core.content.durable_characters import ProficiencySubject
from dnd.types.damage import DamageType
from dnd.types import creatures as creature_types
from dnd.types.saving_throws import SavingThrowEffectTag
from dnd.types.senses import SenseMode


class OriginSavingThrowAdvantageRule(BaseModel):
    """One exact contextual origin advantage over saving throws."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    abilities: tuple[AbilityName, ...] = ()
    requires_magical: bool | None = None
    effect_tags: tuple[SavingThrowEffectTag, ...] = ()

    @model_validator(mode="after")
    def _validate_rule(self) -> Self:
        if self.abilities != tuple(
            ability
            for ability in AbilityName
            if ability in set(self.abilities)
        ):
            raise ValueError("saving throw abilities must be unique and ordered")
        if self.effect_tags != tuple(
            sorted(set(self.effect_tags), key=lambda row: row.value),
        ):
            raise ValueError(
                "saving throw effect tags must be unique and ordered",
            )
        if (
            not self.abilities
            and self.requires_magical is None
            and not self.effect_tags
        ):
            raise ValueError(
                "saving throw advantage rule requires an exact selector",
            )
        return self

    @property
    def identity_key(self) -> tuple[
        tuple[str, ...],
        int,
        tuple[str, ...],
    ]:
        return (
            tuple(row.value for row in self.abilities),
            (
                -1
                if self.requires_magical is None
                else int(self.requires_magical)
            ),
            tuple(row.value for row in self.effect_tags),
        )


class OriginStructuralFeatureDefinition(BaseModel):
    """Closed, data-driven passive contribution installed by one origin trait."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    automatic_proficiencies: tuple[ProficiencySubject, ...] = ()
    sense_modes: tuple[SenseMode, ...] = ()
    damage_resistances: tuple[DamageType, ...] = ()
    size: creature_types.Size | None = None
    walking_speed_feet: int | None = Field(default=None, ge=0)
    maximum_hit_points_per_character_level: int = Field(default=0, ge=0)
    melee_critical_extra_dice: int = Field(default=0, ge=0)
    capabilities: tuple[creature_types.OriginCapability, ...] = ()
    saving_throw_advantages: tuple[
        OriginSavingThrowAdvantageRule,
        ...,
    ] = ()

    @model_validator(mode="after")
    def _validate_rows(self) -> Self:
        proficiency_keys = tuple(
            (row.subject_kind.value, row.identity_key)
            for row in self.automatic_proficiencies
        )
        if proficiency_keys != tuple(sorted(set(proficiency_keys))):
            raise ValueError(
                "automatic proficiencies must be unique and ordered",
            )

        sense_keys = tuple(
            (row.sense_type.value, row.range_feet)
            for row in self.sense_modes
        )
        if any(row.range_feet < 0 for row in self.sense_modes):
            raise ValueError("sense modes cannot have a negative range")
        if (
            len({row.sense_type for row in self.sense_modes})
            != len(self.sense_modes)
            or sense_keys != tuple(sorted(sense_keys))
        ):
            raise ValueError(
                "sense modes must be unique by type and ordered",
            )

        if self.damage_resistances != tuple(
            sorted(set(self.damage_resistances), key=lambda row: row.value),
        ):
            raise ValueError(
                "damage resistances must be unique and ordered",
            )
        if self.capabilities != tuple(
            sorted(set(self.capabilities), key=lambda row: row.value),
        ):
            raise ValueError("capabilities must be unique and ordered")
        advantage_keys = tuple(
            rule.identity_key for rule in self.saving_throw_advantages
        )
        if advantage_keys != tuple(sorted(set(advantage_keys))):
            raise ValueError(
                "saving throw advantages must be unique and ordered",
            )
        return self


__all__ = [
    "OriginSavingThrowAdvantageRule",
    "OriginStructuralFeatureDefinition",
]
