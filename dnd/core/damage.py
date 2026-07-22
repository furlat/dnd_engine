"""Typed factual breakdowns for damage resolution."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.core.modifiers import DamageType, ResistanceStatus


class DamageResolutionModel(BaseModel):
    """Immutable base contract for one resolved damage packet."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DamageComponentResolution(DamageResolutionModel):
    """Affinity resolution for one typed component of a damage packet."""

    damage_type: DamageType = Field(description="Damage type of this component.")
    incoming_damage: int = Field(ge=0, description="Component damage before type affinity.")
    resistance_status: ResistanceStatus = Field(
        description="Resolved vulnerability, resistance, immunity, or neutral affinity.",
    )
    multiplier: float = Field(
        ge=0,
        description="Type-affinity multiplier applied by the engine.",
    )
    after_affinity_damage: int = Field(
        ge=0,
        description="Integer component damage after type affinity and engine rounding.",
    )
    affinity_prevented_damage: int = Field(
        ge=0,
        description="Damage prevented by resistance or immunity for this component.",
    )
    vulnerability_bonus_damage: int = Field(
        ge=0,
        description="Additional damage created by vulnerability for this component.",
    )


class DamageResolution(DamageResolutionModel):
    """Complete post-handler damage resolution before and across hit-point pools."""

    declared_damage: int = Field(
        ge=0,
        description="Damage declared on TakeDamageEvent before event handlers.",
    )
    incoming_damage: int = Field(
        ge=0,
        description="Damage entering health resolution after event handlers.",
    )
    event_prevented_damage: int = Field(
        ge=0,
        description="Damage removed by event handlers before health affinities.",
    )
    event_amplified_damage: int = Field(
        ge=0,
        description="Damage added by event handlers before health affinities.",
    )
    components: tuple[DamageComponentResolution, ...] = Field(
        description="Typed component affinity outcomes in source order.",
    )
    after_affinity_damage: int = Field(
        ge=0,
        description="Packet damage after all component affinities.",
    )
    affinity_prevented_damage: int = Field(
        ge=0,
        description="Damage prevented specifically by resistance or immunity.",
    )
    vulnerability_bonus_damage: int = Field(
        ge=0,
        description="Damage added specifically by vulnerability.",
    )
    flat_reduction_damage: int = Field(
        ge=0,
        description="Damage prevented by packet-level flat damage reduction.",
    )
    mitigated_damage: int = Field(
        ge=0,
        description="Damage remaining after affinities and flat reduction.",
    )
    temporary_hit_point_damage: int = Field(
        ge=0,
        description="Temporary hit points consumed by this packet.",
    )
    normal_hit_point_damage: int = Field(
        ge=0,
        description="Normal hit-point damage applied after temporary HP and survival caps.",
    )
    survival_cap_prevented_damage: int = Field(
        ge=0,
        description="Damage prevented by effects that cap normal hit-point loss.",
    )
    effective_normal_hit_point_damage: int = Field(
        ge=0,
        description="Normal hit points that existed and were actually removed.",
    )
    overkill_damage: int = Field(
        ge=0,
        description="Applied normal-HP damage beyond the target's available normal HP.",
    )

    @property
    def applied_damage(self) -> int:
        """Return temporary plus normal hit-point damage applied by the engine."""
        return self.temporary_hit_point_damage + self.normal_hit_point_damage

    @model_validator(mode="after")
    def validate_conservation(self) -> "DamageResolution":
        """Validate the arithmetic conservation laws of the resolution."""
        component_incoming = sum(component.incoming_damage for component in self.components)
        component_after_affinity = sum(
            component.after_affinity_damage for component in self.components
        )
        if component_incoming != self.incoming_damage:
            raise ValueError("damage components do not sum to incoming_damage")
        if component_after_affinity != self.after_affinity_damage:
            raise ValueError("damage components do not sum to after_affinity_damage")
        if self.declared_damage + self.event_amplified_damage - self.event_prevented_damage != self.incoming_damage:
            raise ValueError("event-level damage adjustment does not conserve damage")
        if self.after_affinity_damage - self.flat_reduction_damage != self.mitigated_damage:
            raise ValueError("flat damage reduction does not conserve damage")
        if (
            self.temporary_hit_point_damage
            + self.normal_hit_point_damage
            + self.survival_cap_prevented_damage
            != self.mitigated_damage
        ):
            raise ValueError("hit-point allocation does not conserve mitigated damage")
        if self.effective_normal_hit_point_damage + self.overkill_damage != self.normal_hit_point_damage:
            raise ValueError("effective and overkill damage do not sum to normal hit-point damage")
        return self
