"""Canonical damage identities and affinity states."""

from enum import Enum


class DamageType(str, Enum):
    """Closed damage-type vocabulary shared by rules and transport."""

    ACID = "Acid"
    BLUDGEONING = "Bludgeoning"
    COLD = "Cold"
    FIRE = "Fire"
    FORCE = "Force"
    LIGHTNING = "Lightning"
    NECROTIC = "Necrotic"
    PIERCING = "Piercing"
    POISON = "Poison"
    PSYCHIC = "Psychic"
    RADIANT = "Radiant"
    SLASHING = "Slashing"
    THUNDER = "Thunder"


class ResistanceStatus(str, Enum):
    """Resolved affinity applied to one damage type."""

    NONE = "None"
    RESISTANCE = "Resistance"
    IMMUNITY = "Immunity"
    VULNERABILITY = "Vulnerability"


__all__ = ["DamageType", "ResistanceStatus"]
