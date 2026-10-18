"""The actor scan: one precomputed per-call value every admission check reads (plan §14.2).

Frozen data only: it imports neither Entity nor Senses. `Entity.action_scan`
builds it once per discovery call or performed action; rules keep full world
access, the scan only makes the common checks (range, sight, faction, reach)
lookups.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import FrozenSet, Optional, Tuple
from uuid import UUID

from dnd.core.action_types import RestrictedActionGrant
from dnd.core.creature_types import CreatureType, Size
from dnd.core.life_types import LifeState

Position = Tuple[int, int]


class Relationship(StrEnum):
    """How a target stands to the acting creature."""

    SELF = "self"
    ALLY = "ally"
    ENEMY = "enemy"


def relationship(source_uuid: UUID, source_faction: Optional[str],
                 target_uuid: UUID, target_faction: Optional[str]) -> Relationship:
    """Same faction is an ally; a missing faction is an enemy to everyone else."""
    if target_uuid == source_uuid:
        return Relationship.SELF
    if source_faction is None or target_faction is None or source_faction != target_faction:
        return Relationship.ENEMY
    return Relationship.ALLY


@dataclass(frozen=True, slots=True)
class CreatureFacts:
    """Target-only facts the rules read, independent of any observer."""

    uuid: UUID
    position: Position
    creature_type: CreatureType
    life_state: LifeState
    condition_names: FrozenSet[str]
    blocks_external_contact: bool
    faction: Optional[str]
    size: Size
    has_positive_hp: bool


@dataclass(frozen=True, slots=True)
class ScanRecord:
    """One perceived creature: its facts, where and how this actor perceives it, and the relationship."""

    facts: CreatureFacts
    position: Position
    visual: bool
    relationship: Relationship


@dataclass(frozen=True, slots=True)
class ObjectRecord:
    """One perceived object at its perceived contact position."""

    uuid: UUID
    position: Position


@dataclass(frozen=True, slots=True)
class ActorScan:
    """Everything the base admission checks read for one actor at one instant.

    `subjective` is the knowledge every check reads the world with: discovery
    and preview see what the actor perceives, execution sees the world.

    `reach_cells` and `threat_domains` are navigation: only a
    discovery scan carries them; an executed action's scan leaves them empty.
    """

    actor_uuid: UUID
    subjective: bool
    position: Position
    visible: FrozenSet[Position]
    creatures: Mapping[UUID, ScanRecord]
    objects: Mapping[UUID, ObjectRecord]
    carried_items: FrozenSet[UUID]
    reach_cells: FrozenSet[Position]
    threat_domains: Mapping[UUID, FrozenSet[Position]]
    slot_capacity: Mapping[int, int]
    restricted_grants: Tuple[RestrictedActionGrant, ...]
    free_cast_grants: FrozenSet[UUID]
    source_item_charges: Mapping[UUID, int]
    active_encounter_uuid: Optional[UUID]
