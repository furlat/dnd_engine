"""Dependency-safe structural feature grants."""

from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True, slots=True)
class AttackMultiplicityGrant:
    """One source-owned entitlement to attacks within an Attack action.

    ``attacks_per_attack_action`` is the total number of attacks, not the
    additional count. Multiple class sources combine by strongest entitlement,
    never by addition.
    """

    grant_id: UUID
    provider_id: str
    attacks_per_attack_action: int
    acquisition_ordinal: int

    def __post_init__(self) -> None:
        """Reject malformed multiplicity grants before runtime ownership."""
        if self.attacks_per_attack_action < 2:
            raise ValueError(
                "attack multiplicity must grant at least two attacks",
            )
        if self.acquisition_ordinal < 1:
            raise ValueError("acquisition_ordinal must be positive")
        if not self.provider_id or "." not in self.provider_id:
            raise ValueError("provider_id must be a namespaced semantic ID")


__all__ = ["AttackMultiplicityGrant"]
