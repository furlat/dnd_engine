"""Schema-16 world wire values: what a seat perceives of tiles, objects, containers and connectors change.

EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 §3.3 (keyed changes), §3.4 (entering perception sends the current state in
full), §3.5 (static content once per kind and id). A record perceived before and after an occurrence travels as that
occurrence's keyed change; a record entering perception (a cell coming into view, a tile replaced in view, an object
newly observed, a container newly opened to it) travels whole; leaving perception sends nothing. For the cells it
enters, an update is authoritative: the client drops what it held there and keeps what the update carries.

Staging (coordinator, 2026-10-18): only the client reference fold (`world_reduction`), its codec (`world_columns`)
and its vector tooling import this module. At the projector switch these types move into `dnd.player.facts`,
replace its schema-15 `WorldUpdate`, `TileFieldUpdate` and the world part of `PlayerState`, and this module is
deleted in the same commit.
"""

from dataclasses import dataclass, field
from typing import Annotated, TypedDict, TypeVar
from uuid import UUID

from pydantic import ConfigDict, Field, with_config
from pydantic.dataclasses import dataclass as packed_dataclass

from dnd.core.item_types import ItemConcentrationSlot, ItemEffectPresentationState, ItemIntegrity, ItemRemnantState
from dnd.core.item_types import DoorMechanism, DoorSwing
from dnd.core.presentation_geometry import AoEPresentationGeometry
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.player.facts import PlayerObject, _no_rows, _unflagged, _unset, _zero
from dnd.types.cells import EMPTY_CELLS, EMPTY_VALUES, PACKED, CellMask, CellMaskField, CellValuesField
from dnd.types.event_facts import WorldConnectorState, WorldTileState
from dnd.types.materials import TileSurface
from dnd.types.physical_access import ContactPassage
from dnd.types.residues import ObjectResidueState, ResidueContribution
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.world import CardinalDirection, LightLevel
from dnd.types.world_placement import BoundaryStructure, WorldObjectPlacement

Row = TypeVar("Row")
# A row list holding no rows is left out of a dump (the facts.py convention).
Rows = Annotated[tuple[Row, ...], Field(exclude_if=_no_rows)]


@dataclass(frozen=True, slots=True, kw_only=True)
class TileStatic:
    """A tile's fixed part, sent once per tile uuid: no writer changes it for one uuid (a replaced tile has a new
    uuid)."""

    position: tuple[int, int]
    tile_uuid: UUID
    surface: TileSurface
    name: str


@packed_dataclass(frozen=True, slots=True, kw_only=True, config=PACKED)
class TileColumns:
    """The changeable scalars of the entered cells that hold a tile, one byte per cell per column in `cells` order
    (x, then y: the `CellValues` order). `flags` holds blocks_optics (bit 0), blocks_propagation (bit 1), the
    surface kind (bits 2-3: ordinary, stairs, ramp) and the slope axis (bits 4-5: none, north-south, east-west).
    `elevation_steps` is empty when every cell is at 0."""

    cells: CellMask
    walking_cost: bytes
    flying_cost: bytes
    swimming_cost: bytes
    burrowing_cost: bytes
    flags: bytes
    default_light: bytes
    resolved_light: bytes
    elevation_steps: Annotated[tuple[int, ...], Field(exclude_if=_no_rows)] = ()


@with_config(ConfigDict(extra="forbid"))
class TileScalarChanges(TypedDict, total=False):
    """A perceived tile's changed scalars, each with its after-value; its conditions and residues change through
    their own rows and its static part never changes."""

    blocks_optics: bool
    blocks_propagation: bool
    walking_cost: Annotated[int, Field(ge=0)]
    flying_cost: Annotated[int, Field(ge=0)]
    swimming_cost: Annotated[int, Field(ge=0)]
    burrowing_cost: Annotated[int, Field(ge=0)]
    elevation_steps: int
    surface_kind: ElevationSurfaceKind
    slope_axis: SlopeAxis | None
    default_light: LightLevel


@dataclass(frozen=True, slots=True, kw_only=True)
class TileFieldUpdate:
    position: tuple[int, int]
    changes: TileScalarChanges


@dataclass(frozen=True, slots=True, kw_only=True)
class TileConditions:
    """A tile's own condition names after the occurrence (never its residues' names), in the tile's order."""

    position: tuple[int, int]
    names: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ResidueMaterial:
    """A residue material's fixed part, sent once per residue id."""

    residue_id: str
    name: str
    description: str
    max_amount: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ContributionRow:
    """One contribution of a residue, set at its index (the index after the last appends one)."""

    index: Annotated[int, Field(ge=0)]
    contribution: ResidueContribution


@dataclass(frozen=True, slots=True, kw_only=True)
class ResidueRow:
    """One material on one tile: whole for a key the client does not hold (its condition uuid present), else the
    occurrence's change (`amount` None: unchanged; the contributions it set)."""

    position: tuple[int, int]
    residue_id: str
    condition_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    amount: Annotated[int | None, Field(exclude_if=_unset)] = None
    contributions: Rows[ContributionRow] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ResidueKey:
    position: tuple[int, int]
    residue_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectLook:
    """A floor item's fixed part, sent once per item uuid: no writer changes these fields for one uuid (a census of
    every gallery case's world fold; a broken object's visual name changes, so it is state)."""

    item_uuid: UUID
    item_id: str
    visual_variant_id: Annotated[str | None, Field(exclude_if=_unset)] = None
    contact_passage: ContactPassage = ContactPassage.STRUCTURAL
    supported_by_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    door_mechanism: Annotated[DoorMechanism | None, Field(exclude_if=_unset)] = None
    door_swing: Annotated[DoorSwing | None, Field(exclude_if=_unset)] = None
    maximum_hit_points: Annotated[int | None, Field(exclude_if=_unset)] = None
    concentration_capacity: Annotated[int, Field(exclude_if=_zero)] = 0
    construction_owner_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    construction_geometry: Annotated[AoEPresentationGeometry | None, Field(exclude_if=_unset)] = None
    known_to_creator: Annotated[bool, Field(exclude_if=_unflagged)] = False


def _one(count: int) -> bool:
    return count == 1


def _picked(flag: bool) -> bool:
    return flag


def _intact(integrity: ItemIntegrity) -> bool:
    return integrity is ItemIntegrity.INTACT


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectState:
    """A floor item's changeable part, its value at the occurrence; a field holding its default is left out."""

    name: str
    visual_item_name: str
    map_char: str
    boundary_structure: Annotated[BoundaryStructure | None, Field(exclude_if=_unset)] = None
    is_open: Annotated[bool | None, Field(exclude_if=_unset)] = None
    is_lit: Annotated[bool | None, Field(exclude_if=_unset)] = None
    very_bright_radius_feet: Annotated[int | None, Field(exclude_if=_unset)] = None
    bright_radius_feet: Annotated[int | None, Field(exclude_if=_unset)] = None
    dim_radius_feet: Annotated[int | None, Field(exclude_if=_unset)] = None
    stack_count: Annotated[int, Field(exclude_if=_one)] = 1
    is_pickable: Annotated[bool, Field(exclude_if=_picked)] = True
    item_effects: Annotated[tuple[ItemEffectPresentationState, ...], Field(exclude_if=_no_rows)] = ()
    blocks_propagation: Annotated[bool, Field(exclude_if=_unflagged)] = False
    is_engaged: Annotated[bool | None, Field(exclude_if=_unset)] = None
    surface_residues: Annotated[tuple[ObjectResidueState, ...], Field(exclude_if=_no_rows)] = ()
    current_hit_points: Annotated[int | None, Field(exclude_if=_unset)] = None
    concentration_slots: Annotated[tuple[ItemConcentrationSlot, ...], Field(exclude_if=_no_rows)] = ()
    remnant_state: Annotated[ItemRemnantState | None, Field(exclude_if=_unset)] = None
    integrity: Annotated[ItemIntegrity, Field(exclude_if=_intact)] = ItemIntegrity.INTACT
    destruction_outcome: Annotated[str | None, Field(exclude_if=_unset)] = None
    construction_suppressions: Annotated[tuple[SpellSuppression, ...], Field(exclude_if=_no_rows)] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectRow:
    """A world object the seat observes.

    An entering row carries its state, placement and the faces its residues are authoritative for (those whose
    viewing cell some member sees); a perceived object's change carries its state, and its placement when it moved.
    A row without a state changes only which members observe the object. `members`: bit i is the audience's
    `observers[i]`; a seat with one observer leaves it out.
    """

    item_uuid: UUID
    members: Annotated[int | None, Field(ge=1, exclude_if=_unset)] = None
    state: Annotated[ObjectState | None, Field(exclude_if=_unset)] = None
    placement: Annotated[WorldObjectPlacement | None, Field(exclude_if=_unset)] = None
    observed_faces: Annotated[tuple[CardinalDirection, ...], Field(exclude_if=_no_rows)] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ContainedItem:
    item_uuid: UUID
    state: ObjectState


@dataclass(frozen=True, slots=True, kw_only=True)
class ContainerContents:
    """A container's whole contents, on gaining sight of them (looks once, through `object_looks`)."""

    container_uuid: UUID
    items: Rows[ContainedItem] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ContentsChange:
    """A seen container's contents changing while the seat sees them."""

    container_uuid: UUID
    upserted: Rows[ContainedItem] = ()
    removed: Rows[UUID] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class WorldUpdate:
    """The world a seat perceives change at one occurrence.

    `entered` is the update's authoritative scope: for those cells the client drops everything it holds and keeps
    only what this update carries, their tiles, every object touching them (`placement_support_cells`) and every
    connector with an endpoint there; no object or connector there means none. Every other row is the keyed change
    of a record the seat perceived before and after the occurrence. Static rows come once per (kind, id) per seat.
    """

    occurrence: int
    entered: CellMaskField = EMPTY_CELLS
    tile_statics: Rows[TileStatic] = ()
    tile_columns: Annotated[TileColumns | None, Field(exclude_if=_unset)] = None
    tile_conditions: Rows[TileConditions] = ()
    tile_changes: Rows[TileFieldUpdate] = ()
    resolved_light: CellValuesField = EMPTY_VALUES
    residue_materials: Rows[ResidueMaterial] = ()
    residues: Rows[ResidueRow] = ()
    residues_removed: Rows[ResidueKey] = ()
    object_looks: Rows[ObjectLook] = ()
    objects: Rows[ObjectRow] = ()
    objects_removed: Rows[UUID] = ()
    contents: Rows[ContainerContents] = ()
    contents_changed: Rows[ContentsChange] = ()
    connectors: Rows[WorldConnectorState] = ()
    connectors_removed: Rows[UUID] = ()


@dataclass(slots=True, kw_only=True)
class WorldStatic:
    """The static rows the client was sent, never pruned: tiles by cell (the latest uuid there), residue
    materials by id, object looks by item uuid."""

    tiles: dict[tuple[int, int], TileStatic] = field(default_factory=dict)
    residues: dict[str, ResidueMaterial] = field(default_factory=dict)
    object_looks: dict[UUID, ObjectLook] = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class WorldMemory:
    """The client's world: what it holds of tiles, objects, the members observing each, and connectors.

    Its fields join `PlayerState` at the switch (tiles and objects are already there).
    """

    tiles: dict[tuple[int, int], WorldTileState] = field(default_factory=dict)
    objects: dict[UUID, PlayerObject] = field(default_factory=dict)
    object_members: dict[UUID, int] = field(default_factory=dict)
    connectors: dict[UUID, WorldConnectorState] = field(default_factory=dict)
    static: WorldStatic = field(default_factory=WorldStatic)
