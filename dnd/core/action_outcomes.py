"""Dependency-neutral stochastic action outcome contracts."""

from enum import Enum
from typing import Any, Literal, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from dnd.types.rolls import AdvantageStatus


class OutcomeResolution(str, Enum):
    """Mechanism that determines whether one modeled application occurs."""

    AUTOMATIC = "automatic"
    ATTACK_ROLL = "attack_roll"
    SAVING_THROW = "saving_throw"
    UNKNOWN = "unknown"


class OutcomeApplicationScope(str, Enum):
    """How repeated applications map onto selected or affected entities."""

    ALLOCATED_TARGETS = "allocated_targets"
    EACH_AFFECTED_ENTITY = "each_affected_entity"


class DamageRollProfile(BaseModel):
    """Actor-known dice formula for one damage component in an action."""

    model_config = ConfigDict(frozen=True)

    dice_count: int = Field(ge=0, description="Number of dice rolled per application.")
    die_size: int = Field(ge=1, description="Number of faces on each damage die.")
    flat_bonus: int = Field(default=0, description="Flat bonus added once per application.")
    damage_type: str = Field(description="Damage type applied to this component.")


class ActionOutcomeProfile(BaseModel):
    """Actor-baseline stochastic rule shared by engine and policy surfaces."""

    model_config = ConfigDict(frozen=True)

    effect_id: Optional[str] = Field(
        default=None,
        description="Stable identity of the modeled effect for typed interactions.",
    )
    resolution: OutcomeResolution = Field(
        description="Roll mechanism used by each application."
    )
    applications: int = Field(
        default=1,
        ge=1,
        description="Independent repeated applications such as rays or darts.",
    )
    application_scope: OutcomeApplicationScope = Field(
        default=OutcomeApplicationScope.ALLOCATED_TARGETS,
        description=(
            "Whether applications are allocated among targets or applied to "
            "every affected entity."
        ),
    )
    damage_rolls: Sequence[DamageRollProfile] = Field(
        default_factory=tuple,
        description="Damage components rolled per application.",
    )
    attack_bonus: Optional[int] = Field(
        default=None,
        description="Actor-baseline d20 attack bonus when applicable.",
    )
    advantage: AdvantageStatus = Field(
        default=AdvantageStatus.NONE,
        description="Actor-baseline attack advantage state.",
    )
    critical_threshold: int = Field(
        default=20,
        ge=1,
        le=20,
        description="Natural d20 threshold for a critical hit.",
    )
    critical_extra_dice: int = Field(
        default=0,
        ge=0,
        description="Extra critical dice beyond doubling base dice.",
    )
    save_dc: Optional[int] = Field(
        default=None,
        description="Saving throw DC when the action uses a save.",
    )
    save_ability: Optional[str] = Field(
        default=None,
        description="Saving throw ability when known.",
    )
    half_damage_on_save: bool = Field(
        default=False,
        description="Whether a successful save retains half damage.",
    )
    scope: Literal["actor_baseline"] = Field(
        default="actor_baseline",
        description="Explicit boundary of facts represented by this profile.",
    )

    def model_post_init(self, __context: Any) -> None:
        """Freeze the disclosed damage-component sequence."""
        object.__setattr__(self, "damage_rolls", tuple(self.damage_rolls))
