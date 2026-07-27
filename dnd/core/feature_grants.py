"""Dependency-safe structural feature grants with closed combination rules."""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from dnd.core.content.identities import ContentRef


class FeatureCombinationGroup(str, Enum):
    """Core-owned feature families whose grants require combination."""

    EXTRA_ATTACK = "extra_attack"


class AttackMultiplicityApplicability(str, Enum):
    """Closed attack-action families eligible for multiplicity grants."""

    ORDINARY_ATTACK = "ordinary_attack"


@dataclass(frozen=True, slots=True)
class AttackMultiplicityGrant:
    """One source-owned entitlement to attacks within an Attack action.

    ``attacks_per_attack_action`` is the total number of attacks, not the
    additional count. Required tags and action refs narrow future grants such
    as pact-weapon-only multiplicity without changing the ordinary Fighter,
    Barbarian, Monk, Paladin, or Ranger family.
    """

    grant_id: UUID
    provider_ref: ContentRef
    attacks_per_attack_action: int
    acquisition_ordinal: int
    applicability: AttackMultiplicityApplicability = (
        AttackMultiplicityApplicability.ORDINARY_ATTACK
    )
    required_weapon_tags: frozenset[str] = frozenset()
    required_body_tags: frozenset[str] = frozenset()
    required_action_refs: tuple[ContentRef, ...] = ()
    combination_group: FeatureCombinationGroup = (
        FeatureCombinationGroup.EXTRA_ATTACK
    )

    def __post_init__(self) -> None:
        """Reject malformed multiplicity grants before runtime ownership."""
        if self.attacks_per_attack_action < 2:
            raise ValueError(
                "attack multiplicity must grant at least two attacks",
            )
        if self.acquisition_ordinal < 1:
            raise ValueError("acquisition_ordinal must be positive")
        if self.combination_group != FeatureCombinationGroup.EXTRA_ATTACK:
            raise ValueError(
                "AttackMultiplicityGrant requires the extra_attack group",
            )
        action_keys = tuple(
            ref.identity_key for ref in self.required_action_refs
        )
        if action_keys != tuple(sorted(set(action_keys))):
            raise ValueError(
                "required action refs must be unique and identity ordered",
            )

    def applies_to(
        self,
        *,
        applicability: AttackMultiplicityApplicability,
        weapon_tags: frozenset[str] = frozenset(),
        body_tags: frozenset[str] = frozenset(),
        action_ref: ContentRef | None = None,
    ) -> bool:
        """Return whether the typed attack context satisfies this grant."""
        if self.applicability != applicability:
            return False
        if not self.required_weapon_tags.issubset(weapon_tags):
            return False
        if not self.required_body_tags.issubset(body_tags):
            return False
        if self.required_action_refs:
            return (
                action_ref is not None
                and action_ref in self.required_action_refs
            )
        return True


__all__ = [
    "AttackMultiplicityApplicability",
    "AttackMultiplicityGrant",
    "FeatureCombinationGroup",
]
