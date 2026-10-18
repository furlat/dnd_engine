"""Dependency-neutral physical contact and provider passage facts."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class PhysicalAccess(StrEnum):
    HAND = "hand"
    LIGHT_WEAPON = "light_weapon"
    WEAPON = "weapon"
    NATURAL = "natural"
    BODY = "body"
    PROJECTILE = "projectile"


class ContactPassage(StrEnum):
    STRUCTURAL = "structural"
    CLEAR = "clear"
    BLOCKED = "blocked"
    LIGHT_WEAPONS = "light_weapons"
    HAND_AND_LIGHT_WEAPONS = "hand_and_light_weapons"


def contact_passage_allows(
    policy: ContactPassage, access: PhysicalAccess, *, blocks_movement: bool,
) -> bool:
    """Evaluate contact only; projectiles use the provider's propagation channel."""
    if policy is ContactPassage.STRUCTURAL:
        return not blocks_movement
    if policy is ContactPassage.CLEAR:
        return True
    if policy is ContactPassage.LIGHT_WEAPONS:
        return access is PhysicalAccess.LIGHT_WEAPON
    if policy is ContactPassage.HAND_AND_LIGHT_WEAPONS:
        return access in (PhysicalAccess.HAND, PhysicalAccess.LIGHT_WEAPON)
    return False


@dataclass(frozen=True, slots=True)
class ObjectContact:
    """One `GridMap.attack_object_contact` result (`position`, None: no contact) with the arguments it was traced with."""

    requester_uuid: UUID
    object_uuid: UUID
    range_feet: int
    access: PhysicalAccess
    subjective: bool
    origin: tuple[int, int]
    position: tuple[int, int] | None
