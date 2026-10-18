"""Schema-16 sensory wire values: a seat's composed perception change, one per settlement.

EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 §3.1 (composition, member bitsets per row: Q1 (a)), §3.2 (visible part
only), §3.6 (nothing restated). A seat receives one `SensoryFact` per settlement: the change of the view its
members compose, never member by member. Records it perceived before and after travel as changes (patched light
rows and sightings carry only their changed fields); records entering its perception travel whole; leaving
perception sends the key only.

Staging (coordinator, 2026-10-18): only the client reference fold and its vector tests import this module. At the
projector switch these types move into `dnd.player.facts`, replace its schema-15 `SensoryFact`, `SensoryRows`,
`LightRow` and `SpatialEffectSighting`, and this module is deleted in the same commit.
"""

from dataclasses import dataclass, field
from typing import Annotated, Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, with_config

from dnd.core.condition_types import ConditionDurationSummary
from dnd.core.creature_types import DamageType
from dnd.core.presentation_geometry import AoEPresentationGeometry, WallAssemblyPresentationGeometry
from dnd.player.facts import (RowIndex, RowIndices, SensoryFlag, SensoryNumber, SpatialEffectContent, _neutral,
    _no_rows, _unflagged, _unset, _zero)
from dnd.types.cells import EMPTY_CELLS, NO_ROWS, CellMask, CellMaskField, CellValues, RowBitsField
from dnd.types.class_features import DraconicPresenceMode
from dnd.types.material_deposits import MaterialDepositSource
from dnd.types.senses import SenseMode, SensesType, VolumeSurfaceSight
from dnd.types.spatial_effects import AreaPropagation
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.traps import TrapState

# The seat members perceiving a row: bit i is the initialization audience's `observers[i]`; a perceived row has one.
MemberBits = Annotated[int, Field(ge=1)]
# An upper volume surface's key: its cell and planes (`VolumeSurfaceSight`).
VolumeSurfaceKey = tuple[tuple[int, int], tuple[tuple[float, float, float], ...]]


class SpatialEffectSighting(BaseModel):
    """An effect the seat perceives, as it enters perception: its visible part (plan §3.2), without static content.

    `positions` are the effect's cells some member sees now (its own cells or seen volume cells),
    `visible_volume_positions` the seen volume cells among them. The seat's native revision of the effect is not
    sent. A field holding its default is left out.
    """

    model_config = ConfigDict(frozen=True)
    duration: ConditionDurationSummary | None = Field(default=None, exclude_if=_unset)
    positions: CellMask
    apparent_presence: bool = Field(default=False, exclude_if=_unflagged)
    trap_state: TrapState | None = Field(default=None, exclude_if=_unset)
    pressed: bool | None = Field(default=None, exclude_if=_unset)
    direction: tuple[int, int] | None = Field(default=None, exclude_if=_unset)
    anchor_item_uuid: UUID | None = Field(default=None, exclude_if=_unset)
    anchor_entity_uuid: UUID | None = Field(default=None, exclude_if=_unset)
    energy_type: DamageType | None = Field(default=None, exclude_if=_unset)
    presence_mode: DraconicPresenceMode | None = Field(default=None, exclude_if=_unset)
    sustainer_item_uuid: UUID | None = Field(default=None, exclude_if=_unset)
    concentration_slot_uuid: UUID | None = Field(default=None, exclude_if=_unset)
    anchor_position: tuple[int, int] | None = Field(default=None, exclude_if=_unset)
    anchor_elevation_steps: int | None = Field(default=None, exclude_if=_unset)
    area_geometry: AoEPresentationGeometry | None = Field(default=None, exclude_if=_unset)
    construction_sections: tuple[WallAssemblyPresentationGeometry, ...] = Field(default=(), exclude_if=_no_rows)
    area_propagation: AreaPropagation | None = Field(default=None, exclude_if=_unset)
    deposit_source: MaterialDepositSource | None = Field(default=None, exclude_if=_unset)
    visible_volume_positions: CellMaskField = EMPTY_CELLS
    upper_volume_surfaces: tuple[VolumeSurfaceSight, ...] = Field(default=(), exclude_if=_no_rows)
    suppressions: tuple[SpellSuppression, ...] = Field(default=(), exclude_if=_no_rows)


@with_config(ConfigDict(extra="forbid"))
class SightingChanges(TypedDict, total=False):
    """A perceived effect's changed fields, each with its after-value (None: it became unset); its cell sets and
    volume surfaces change through `SpatialEffectPatch`'s added and removed sets."""


    duration: ConditionDurationSummary | None
    apparent_presence: bool
    trap_state: TrapState | None
    pressed: bool | None
    direction: tuple[int, int] | None
    anchor_item_uuid: UUID | None
    anchor_entity_uuid: UUID | None
    energy_type: DamageType | None
    presence_mode: DraconicPresenceMode | None
    sustainer_item_uuid: UUID | None
    concentration_slot_uuid: UUID | None
    anchor_position: tuple[int, int] | None
    anchor_elevation_steps: int | None
    area_geometry: AoEPresentationGeometry | None
    construction_sections: tuple[WallAssemblyPresentationGeometry, ...]
    area_propagation: AreaPropagation | None
    deposit_source: MaterialDepositSource | None
    suppressions: tuple[SpellSuppression, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class SpatialEffectPatch:
    """The change of an effect perceived before and after the settlement: visible cells and seen volume cells
    added and removed, upper volume surfaces added and removed by key, the member bitset when it changed, and the
    other changed fields. A field holding its default is left out."""

    positions_added: CellMaskField = EMPTY_CELLS
    positions_removed: CellMaskField = EMPTY_CELLS
    volume_added: CellMaskField = EMPTY_CELLS
    volume_removed: CellMaskField = EMPTY_CELLS
    upper_added: Annotated[tuple[VolumeSurfaceSight, ...], Field(exclude_if=_no_rows)] = ()
    upper_removed: Annotated[tuple[VolumeSurfaceKey, ...], Field(exclude_if=_no_rows)] = ()
    members: Annotated[MemberBits | None, Field(exclude_if=_unset)] = None
    changes: Annotated[SightingChanges, Field(exclude_if=_no_rows)] = field(default_factory=SightingChanges)


@dataclass(frozen=True, slots=True, kw_only=True)
class LightRow:
    """A light source entering the seat's perception (an emitter lighting a cell it sees); its identities name
    the group's `uuids`. A field holding its default is left out."""

    source: RowIndex
    position: tuple[int, int]
    base_height_steps: Annotated[int, Field(exclude_if=_zero)] = 0
    very_bright_radius_feet: int
    bright_radius_feet: int
    dim_radius_feet: int
    appearance: Annotated[Literal["torch", "neutral"], Field(exclude_if=_neutral)] = "neutral"
    actor_anchored: SensoryFlag = False
    anchor_entity: Annotated[RowIndex | None, Field(exclude_if=_unset)] = None
    anchor_item: Annotated[RowIndex | None, Field(exclude_if=_unset)] = None


@with_config(ConfigDict(extra="forbid"))
class LightChanges(TypedDict, total=False):
    """A perceived light source's changed fields with their after-values; an anchor is a `uuids` index, None when
    it became undisclosed."""


    position: tuple[int, int]
    base_height_steps: int
    very_bright_radius_feet: int
    bright_radius_feet: int
    dim_radius_feet: int
    appearance: Literal["torch", "neutral"]
    actor_anchored: bool
    anchor_entity: RowIndex | None
    anchor_item: RowIndex | None


@dataclass(frozen=True, slots=True, kw_only=True)
class LightPatch:
    """The change of a light source perceived before and after: its changed fields (a walking torch: its position)."""

    source: RowIndex
    changes: LightChanges

    def __post_init__(self) -> None:
        if not self.changes:
            raise ValueError("A light patch changes at least one field")


@dataclass(frozen=True, slots=True, kw_only=True)
class SensoryRows:
    """The values a group's sensory facts name, as columns.

    Every identity a row or a removed list names is in `uuids` once. Contact row i is the entity or object
    `uuids[contact_uuid_index[i]]` perceived at `contact_positions[i]`, visually if row i is in `contact_visual`,
    with special senses `contact_special_senses[i]` (empty column: none has any), by the members
    `contact_members[i]`. Sighting row i is the effect `uuids[sighting_uuid_index[i]]` entering perception as
    `sightings[i]`, by the members `sighting_members[i]`. Patch row i changes the perceived effect
    `uuids[patch_uuid_index[i]]` by `sighting_patches[i]`. Retired row i: the effect `uuids[retired_uuid_index[i]]`
    left the cells `retired_cells[i]` as a member saw them (plan D1 (a)). `light_sources[i]` is a source entering
    perception, `light_patches[i]` the change of one perceived before and after.

    A seat with one observer leaves out both member columns: every row is perceived by that observer. Otherwise
    each member column has one entry per row of its table.

    Three row tables hold the cells the facts' cell lists name, each once (unchanged from schema 15): `cells` the
    rows of the visible lists (its cells in cell order); `light_levels` the rows of the light lists and `hazards`
    those of the hazard lists, each table the distinct (cell, value) pairs by cell in cell order, then by value.
    Layer k of a table holds, for each cell with more than k values in the group, its (k+1)-th smallest.
    """

    uuids: Annotated[tuple[UUID, ...], Field(exclude_if=_no_rows)] = ()
    contact_uuid_index: RowIndices = ()
    contact_positions: Annotated[tuple[tuple[int, int], ...], Field(exclude_if=_no_rows)] = ()
    contact_visual: RowBitsField = NO_ROWS
    contact_special_senses: Annotated[tuple[tuple[SensesType, ...], ...], Field(exclude_if=_no_rows)] = ()
    contact_members: Annotated[tuple[MemberBits, ...], Field(exclude_if=_no_rows)] = ()
    sighting_uuid_index: RowIndices = ()
    sightings: Annotated[tuple[SpatialEffectSighting, ...], Field(exclude_if=_no_rows)] = ()
    sighting_members: Annotated[tuple[MemberBits, ...], Field(exclude_if=_no_rows)] = ()
    patch_uuid_index: RowIndices = ()
    sighting_patches: Annotated[tuple[SpatialEffectPatch, ...], Field(exclude_if=_no_rows)] = ()
    retired_uuid_index: RowIndices = ()
    retired_cells: Annotated[tuple[CellMask, ...], Field(exclude_if=_no_rows)] = ()
    light_sources: Annotated[tuple[LightRow, ...], Field(exclude_if=_no_rows)] = ()
    light_patches: Annotated[tuple[LightPatch, ...], Field(exclude_if=_no_rows)] = ()
    cells: CellMaskField = EMPTY_CELLS
    light_levels: Annotated[tuple[CellValues, ...], Field(exclude_if=_no_rows)] = ()
    hazards: Annotated[tuple[CellValues, ...], Field(exclude_if=_no_rows)] = ()

    def __post_init__(self) -> None:
        contacts = len(self.contact_positions)
        names = (*self.contact_uuid_index, *self.sighting_uuid_index, *self.patch_uuid_index,
                 *self.retired_uuid_index,
                 *(index for row in self.light_sources for index in (row.source, row.anchor_entity, row.anchor_item)
                   if index is not None),
                 *(index for row in self.light_patches
                   for index in (row.source, row.changes.get("anchor_entity"), row.changes.get("anchor_item"))
                   if index is not None))
        if (len(self.contact_uuid_index) != contacts
                or self.contact_special_senses and len(self.contact_special_senses) != contacts
                or self.contact_members and len(self.contact_members) != contacts
                or len(self.sighting_uuid_index) != len(self.sightings)
                or self.sighting_members and len(self.sighting_members) != len(self.sightings)
                or len(self.patch_uuid_index) != len(self.sighting_patches)
                or len(self.retired_uuid_index) != len(self.retired_cells)
                or any(index >= len(self.uuids) for index in names)):
            raise ValueError("Sensory rows pair equal-length columns and name only their own uuids")


NO_SENSORY_ROWS = SensoryRows()


@dataclass(frozen=True, slots=True, kw_only=True)
class SensoryFact:
    """A settlement's change of the seat's composed perception; its values are rows of its group's `SensoryRows`.

    The cells are the composed view's (Q1 (a)): `visible_cells_added` / `_removed` are subsets of the group's
    `cells`, `effective_light_levels_changed` of `light_levels` and `hazardous_cells_changed` of `hazards` (a value
    list names one row per cell; a cell entering view without a value reads 0). The seen cells are not sent: the
    client's seen cells are every cell it has seen visible. `entity_contacts_changed` / `object_contacts_changed`
    index contact rows (set: entering, changed, or perceived by other members); `spatial_effects_added` sighting
    rows; `spatial_effects_patched` patch rows; `spatial_effect_cells_retired` retired rows; `light_sources_added`
    light source rows; `light_sources_patched` light patch rows. The removed lists (`*_removed`) index `uuids`:
    those records left the seat's perception. A list never names two rows of one identity.

    `observer_position` and the capability scalars are the anchor member's (the stream observer once it perceives):
    `observer_position` is present only when it changed, or `initial` (the seat's first perception, carrying every
    scalar). `spatial_effect_content` is the static content of each effect the seat has not received yet.
    """

    kind: Literal["sensory"] = "sensory"
    initial: SensoryFlag = False
    observer_position: Annotated[tuple[int, int] | None, Field(exclude_if=_unset)] = None
    visible_cells_added: RowBitsField = NO_ROWS
    visible_cells_removed: RowBitsField = NO_ROWS
    effective_light_levels_changed: RowBitsField = NO_ROWS
    hazardous_cells_changed: RowBitsField = NO_ROWS
    entity_contacts_changed: RowIndices = ()
    entity_contacts_removed: RowIndices = ()
    object_contacts_changed: RowIndices = ()
    object_contacts_removed: RowIndices = ()
    sense_modes_changed: SensoryFlag = False
    sense_modes: Annotated[tuple[SenseMode, ...] | None, Field(exclude_if=_unset)] = None
    passive_perception_changed: SensoryFlag = False
    passive_perception: SensoryNumber = None
    visual_access_changed: SensoryFlag = False
    visual_access: SensoryNumber = None
    paths_dirty: SensoryFlag = False
    spatial_effects_added: RowIndices = ()
    spatial_effects_patched: RowIndices = ()
    spatial_effects_removed: RowIndices = ()
    spatial_effect_cells_retired: RowIndices = ()
    spatial_effect_content: Annotated[dict[UUID, SpatialEffectContent], Field(exclude_if=_no_rows)] = field(
        default_factory=dict)
    light_sources_added: RowIndices = ()
    light_sources_patched: RowIndices = ()
    light_sources_removed: RowIndices = ()

    def __post_init__(self) -> None:
        if self.initial and (self.observer_position is None or not self.sense_modes_changed
                or self.sense_modes is None or not self.passive_perception_changed
                or self.passive_perception is None or not self.visual_access_changed or self.visual_access is None):
            raise ValueError("An initial sensory fact carries the position and every capability after-value")
