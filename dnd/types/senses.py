"""Dependency-neutral values shared by perception components and events."""

from collections.abc import Mapping, Sequence, Set
from enum import Enum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SensesType(str, Enum):
    """Special sense categories supported by the perception pipeline."""

    BLINDSIGHT = "Blindsight"
    DARKVISION = "Darkvision"
    TREMORSENSE = "Tremorsense"
    TRUESIGHT = "Truesight"
    DEVILS_SIGHT = "Devils Sight"
    SEE_INVISIBLE = "See Invisible"


class SenseMode(BaseModel):
    """A special sense and its effective range in feet; zero is unlimited."""

    sense_type: SensesType = Field(description="Special sense category.")
    range_feet: int = Field(default=0, description="Range in feet; zero means unlimited.")


class OpticalObscurement(str, Enum):
    """Observer-relative optical obstruction contributed by world mechanics."""

    HEAVY = "heavy"
    MAGICAL_DARKNESS = "magical_darkness"


class PerceivedContact(BaseModel):
    """One identified entity or object perceived by an observer."""

    model_config = ConfigDict(frozen=True)

    position: tuple[int, int] = Field(description="Observed grid position.")
    visual: bool = Field(description="Whether a visual route establishes this contact.")
    special_senses: tuple[SensesType, ...] = Field(
        default=(),
        description="Special senses which independently establish this contact.",
    )


class SensesView(Protocol):
    """Minimal perception surface exposed upward by an observing block."""

    position: tuple[int, int]
    visible: Mapping[tuple[int, int], object]
    entities: Mapping[UUID, PerceivedContact]
    objects: Mapping[UUID, PerceivedContact]

    def get_feet_distance(self, position: tuple[int, int]) -> int:
        """Return grid distance to one position in rules feet."""
        ...


class SensoryDelta(Protocol):
    """Recorded observer after-values consumed by the shared sensory reducer.

    Native events and public player facts expose the same values. Reduction
    needs neither native event construction nor its source/handler metadata.
    """

    @property
    def observer_uuid(self) -> UUID: ...
    @property
    def initial(self) -> bool: ...
    @property
    def observer_position(self) -> tuple[int, int]: ...
    @property
    def observer_position_changed(self) -> bool: ...
    @property
    def visible_cells_added(self) -> Sequence[tuple[int, int]]: ...
    @property
    def visible_cells_removed(self) -> Sequence[tuple[int, int]]: ...
    @property
    def seen_cells_added(self) -> Sequence[tuple[int, int]]: ...
    @property
    def entity_contacts_changed(self) -> Mapping[UUID, PerceivedContact]: ...
    @property
    def entity_contacts_removed(self) -> Set[UUID]: ...
    @property
    def object_contacts_changed(self) -> Mapping[UUID, PerceivedContact]: ...
    @property
    def object_contacts_removed(self) -> Set[UUID]: ...
    @property
    def effective_light_levels_changed(self) -> Mapping[str, int]: ...
    @property
    def sense_modes_changed(self) -> bool: ...
    @property
    def sense_modes(self) -> Sequence[SenseMode] | None: ...
    @property
    def passive_perception_changed(self) -> bool: ...
    @property
    def passive_perception(self) -> int | None: ...
    @property
    def visual_access_changed(self) -> bool: ...
    @property
    def visual_access(self) -> int | None: ...
    @property
    def paths_dirty(self) -> bool: ...


__all__ = [
    "OpticalObscurement",
    "PerceivedContact",
    "SenseMode",
    "SensesType",
    "SensesView",
    "SensoryDelta",
]
