"""What a hidden thing's concealing condition records: its DC and who knows it.

A dependency-neutral leaf: the frozen record and the pure rule every reader asks. The concealing
condition holds the record as data; one GridMap function replaces it.
"""

from enum import Enum
from typing import Iterable, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dnd.types.abilities import SkillName
from dnd.types.world_placement import BoundaryStructure

KnowerKey = Union[str, UUID]


class ConcealedAspect(str, Enum):
    """What a concealing condition hides."""

    HAZARD = "hazard"        # the condition itself, a trap or hazard
    PRESENCE = "presence"    # its host object or creature: not perceived until known
    ACTIONS = "actions"      # what its host does: a secret door, a hidden button
    CONTENTS = "contents"    # what its host holds: a desk's drawer, a false back
    CAMOUFLAGE = "camouflage"  # its host, seen as something else while closed and intact: a secret door as wall


NOTICED_ON_OBJECTS = frozenset({ConcealedAspect.PRESENCE, ConcealedAspect.ACTIONS, ConcealedAspect.CAMOUFLAGE})
# (contents only by Search Inside)


class Camouflage(BaseModel):
    """What a seat that doesn't know a camouflaged object is shown of it: renderer data only."""

    model_config = ConfigDict(frozen=True)

    item_id: str
    visual_variant_id: Optional[str] = None
    name: str
    map_char: str
    boundary_structure: Optional[BoundaryStructure] = None


class KnowerScope(str, Enum):
    """Whose knowledge a record keeps: a finder's whole party (its faction), or the finder alone."""

    PARTY = "party"
    CREATURE = "creature"


class Concealment(BaseModel):
    """A hidden thing's DC, who knows it, and who searched for it and missed."""

    model_config = ConfigDict(frozen=True)

    dc: int
    aspect: ConcealedAspect = ConcealedAspect.HAZARD
    knowers: KnowerScope = KnowerScope.PARTY
    skill: SkillName = "perception"  # the check that finds it by searching
    known_by: frozenset[KnowerKey] = frozenset()
    failed_by: frozenset[UUID] = frozenset()
    in_plain_view: bool = False  # for now noticed by anyone who sees it (raised spikes, an open hatch)
    shows: Optional[Camouflage] = None  # a CAMOUFLAGE record's


def knower_key(record: Concealment, faction: Optional[str], uuid: UUID) -> KnowerKey:
    """A finder's party (its faction), or the finder itself when it has none or the record is per creature."""
    return faction if faction is not None and record.knowers is KnowerScope.PARTY else uuid


def knows(record: Optional[Concealment], faction: Optional[str], uuid: UUID) -> bool:
    """Whether a creature knows the hidden thing; a thing never hidden is known to all."""
    return record is None or knower_key(record, faction, uuid) in record.known_by


def notices(record: Concealment, passive: int) -> bool:
    """Passive Perception notices a hidden thing when it meets the DC, or whenever it is in plain view."""
    return record.in_plain_view or passive >= record.dc


def with_knowers(record: Concealment, keys: Iterable[KnowerKey]) -> Concealment:
    return record.model_copy(update={"known_by": record.known_by | frozenset(keys)})


def with_failure(record: Concealment, uuid: UUID) -> Concealment:
    return record.model_copy(update={"failed_by": record.failed_by | {uuid}})


def with_plain_view(record: Concealment, in_plain_view: bool) -> Concealment:
    return record.model_copy(update={"in_plain_view": in_plain_view})


def concealment(dc: Optional[int], aspect: ConcealedAspect = ConcealedAspect.HAZARD, *, skill: SkillName = "perception",
                in_plain_view: bool = False, shows: Optional[Camouflage] = None) -> Optional[Concealment]:
    """The record an authored hidden DC makes; None when nothing is hidden."""
    return None if dc is None else Concealment(dc=dc, aspect=aspect, skill=skill, in_plain_view=in_plain_view,
                                                shows=shows)
