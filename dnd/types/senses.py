"""Dependency-neutral values shared by perception components and events."""

from dnd.core.condition_types import ConditionDurationSummary

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dnd.types.cells import EMPTY_VALUES, CellMask, CellValues
from dnd.types.world import LightLevel
from dnd.core.content.identities import ContentRef
from dnd.core.creature_types import DamageType
from dnd.core.presentation_geometry import AoEPresentationGeometry, WallAssemblyPresentationGeometry
from dnd.types.traps import TrapState
from dnd.types.material_deposits import MaterialDepositSource
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.spatial_effects import AreaPropagation
from dnd.types.class_features import DraconicPresenceMode


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
    contribution_owner_uuid: UUID | None = Field(default=None, exclude=True)


class OpticalObscurement(str, Enum):
    """Observer-relative optical obstruction contributed by world mechanics."""

    HEAVY = "heavy"
    MAGICAL_DARKNESS = "magical_darkness"


# One bit per obscurement value, and the value set of every bit mask (vectorized routes).
OBSCUREMENT_BITS = {value: 1 << index for index, value in enumerate(OpticalObscurement)}
OBSCUREMENT_SETS = tuple(frozenset(value for value, bit in OBSCUREMENT_BITS.items() if mask & bit)
                         for mask in range(1 << len(OBSCUREMENT_BITS)))


class PerceivedContact(BaseModel):
    """One identified entity or object perceived by an observer."""

    model_config = ConfigDict(frozen=True)

    position: tuple[int, int] = Field(description="Observed grid position.")
    visual: bool = Field(description="Whether a visual route establishes this contact.")
    special_senses: tuple[SensesType, ...] = Field(
        default=(),
        description="Special senses which independently establish this contact.",
    )


class VolumeSurfaceSight(BaseModel):
    """Upper volume permission; never permission to see its ground or occupants.

    A sample is visible above every plane: height > a*x + b*y + c.
    Coordinates and height use native grid/elevation steps, before animation.
    Multiple entries for the same cell represent alternative observations:
    satisfying one complete entry is sufficient; planes within it remain AND.
    """

    model_config = ConfigDict(frozen=True)
    position: tuple[int, int]
    lower_height_planes: tuple[tuple[float, float, float], ...] = Field(min_length=1)


class PerceivedSpatialEffect(BaseModel):
    """Last observed spatial effect and only its discovered footprint cells."""

    model_config = ConfigDict(frozen=True)
    duration: ConditionDurationSummary | None = None


    content_ref: ContentRef
    name: str
    description: str
    positions: tuple[tuple[int, int], ...]
    owner_revision: int | None = Field(default=None, ge=0)
    apparent_presence: bool = False
    trap_state: TrapState | None = None
    pressed: bool | None = None
    direction: tuple[int, int] | None = None
    anchor_item_uuid: UUID | None = None
    anchor_entity_uuid: UUID | None = None
    energy_type: DamageType | None = None
    presence_mode: DraconicPresenceMode | None = None
    sustainer_item_uuid: UUID | None = None
    concentration_slot_uuid: UUID | None = None
    anchor_position: tuple[int, int] | None = None
    anchor_elevation_steps: int | None = None
    area_geometry: AoEPresentationGeometry | None = None
    construction_sections: tuple[WallAssemblyPresentationGeometry, ...] = ()
    area_propagation: AreaPropagation | None = None  # Absent in historical recordings.
    deposit_source: MaterialDepositSource | None = None
    visible_volume_positions: tuple[tuple[int, int], ...] = ()
    upper_volume_surfaces: tuple[VolumeSurfaceSight, ...] = ()
    suppressions: tuple[SpellSuppression, ...] = ()


class PerceivedLightSource(BaseModel):
    """One optical emitter, without undisclosed actor or inventory identities.

    Footprint levels are this source's actual occluded contribution before
    tile MAX/caps; WorldTileState.resolved_light is the final objective level.
    """
    model_config = ConfigDict(frozen=True)
    source_uuid: UUID
    revision: int = Field(ge=0)
    position: tuple[int, int]
    base_height_steps: int
    very_bright_radius_feet: int
    bright_radius_feet: int
    dim_radius_feet: int
    appearance: Literal["torch", "neutral"] = "neutral"
    actor_anchored: bool = False
    anchor_entity_uuid: UUID | None = None
    anchor_item_uuid: UUID | None = None
    affected_tiles: dict[str, LightLevel] = Field(default_factory=dict)


class SensesView(Protocol):
    """Minimal perception surface exposed upward by an observing block."""

    position: tuple[int, int]
    cells: Any  # the published cells, a dnd.core.view.PerceivedCells (numpy stays out of dnd/types)
    entities: Mapping[UUID, PerceivedContact]
    objects: Mapping[UUID, PerceivedContact]
    spatial_effects: Mapping[UUID, PerceivedSpatialEffect]

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
    def visible_cells_added(self) -> CellMask: ...
    @property
    def visible_cells_removed(self) -> CellMask: ...
    @property
    def seen_cells_added(self) -> CellMask: ...
    @property
    def entity_contacts_changed(self) -> Mapping[UUID, PerceivedContact]: ...
    @property
    def entity_contacts_removed(self) -> Set[UUID]: ...
    @property
    def object_contacts_changed(self) -> Mapping[UUID, PerceivedContact]: ...
    @property
    def object_contacts_removed(self) -> Set[UUID]: ...
    @property
    def effective_light_levels_changed(self) -> CellValues: ...
    @property
    def hazardous_cells_changed(self) -> CellValues: ...
    @property
    def spatial_effects_changed(self) -> Mapping[UUID, PerceivedSpatialEffect]: ...
    @property
    def spatial_effects_removed(self) -> Set[UUID]: ...
    @property
    def light_sources_changed(self) -> Mapping[UUID, PerceivedLightSource]: ...
    @property
    def light_sources_removed(self) -> Mapping[UUID, int]: ...
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


@dataclass(frozen=True)
class SensesSnapshot:
    """Observer snapshot: packed cell sets, and contact and effect containers owned by its fold.

    `effective_light_levels` holds each visible cell's `LightLevel`,
    `hazardous_cells` 1 for each visible cell known hazardous, else 0.
    """

    position: tuple[int, int]
    visible: CellMask
    seen: CellMask
    entities: dict[UUID, PerceivedContact]
    objects: dict[UUID, PerceivedContact]
    effective_light_levels: CellValues
    paths_dirty: bool
    passive_perception: int
    sense_modes_hash: int
    sense_modes: tuple[SenseMode, ...]
    visual_access: int
    hazardous_cells: CellValues = EMPTY_VALUES
    spatial_effects: dict[UUID, PerceivedSpatialEffect] = field(default_factory=dict)
    light_sources: dict[UUID, PerceivedLightSource] = field(default_factory=dict)
    light_source_removals: dict[UUID, int] = field(default_factory=dict)


__all__ = [
    "OpticalObscurement",
    "PerceivedContact",
    "PerceivedSpatialEffect",
    "SenseMode",
    "SensesType",
    "SensesView",
    "SensoryDelta",
    "SensesSnapshot",
]
