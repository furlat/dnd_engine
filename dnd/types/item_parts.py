"""The parts of an item a seat may know, shared by the change records and the player wire.

`ItemLook` and `ItemProfile` are static for an item instance and travel once per
seat; `ItemState` is what its use and the world change, and changes travel as
`ItemStateChanges`.
"""

from dataclasses import dataclass
from typing import Annotated, TypedDict
from uuid import UUID

from pydantic import ConfigDict, Field, with_config

from dnd.core.item_types import (DoorMechanism, DoorSwing, EquippedVisualPolicy, ItemConcentrationSlot,
    ItemIntegrity, ItemPresentationKind, ItemRarity, ItemRemnantState)
from dnd.core.presentation_geometry import AoEPresentationGeometry
from dnd.types.physical_access import ContactPassage
from dnd.types.residues import ObjectResidueState
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.world_placement import BoundaryStructure


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemLook:
    """What any viewer of an equipped item sees of it, the same for the item's life: sent once per seat. Its
    effects are dynamic (`ItemRecord.effects`); `is_lit` travels in its layer."""

    item_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")]
    item_kind: ItemPresentationKind
    visual_item_name: str
    visual_variant_id: str | None
    equipped_visual_policy: EquippedVisualPolicy
    very_bright_radius_feet: Annotated[int, Field(ge=0)] | None
    bright_radius_feet: Annotated[int, Field(ge=0)] | None
    dim_radius_feet: Annotated[int, Field(ge=0)] | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemProfile:
    """What a controlled item is: the fields its use does not change."""

    name: str
    description: str | None
    rarity: ItemRarity
    weight: float
    value: int
    tags: tuple[str, ...]
    is_pickable: bool
    is_equippable: bool
    is_usable: bool
    is_targetable: bool
    door_mechanism: DoorMechanism | None
    door_swing: DoorSwing | None
    stack_id: str | None
    damage_dice: str | None
    damage_type: str | None
    weapon_properties: tuple[str, ...]
    armor_type: str | None
    armor_ac: int | None
    shield_ac_bonus: int | None
    max_charges: Annotated[int, Field(ge=-1)] | None
    max_stack: Annotated[int, Field(ge=1)]
    is_consumable: bool
    map_char: str
    include_in_senses_objects: bool
    include_in_adjacent_senses_objects: bool
    include_in_available_object_actions: bool
    maximum_hit_points: Annotated[int, Field(ge=0)] | None
    concentration_capacity: Annotated[int, Field(ge=0)]
    boundary_structure: BoundaryStructure | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemState:
    """What a controlled item's use and the world change."""

    stack_count: Annotated[int, Field(ge=0)]
    charges: Annotated[int, Field(ge=-1)] | None
    integrity: ItemIntegrity
    destruction_outcome: str | None
    remnant_state: ItemRemnantState | None
    current_hit_points: Annotated[int, Field(ge=0)] | None
    concentration_slots: tuple[ItemConcentrationSlot, ...]
    construction_owner_uuid: UUID | None
    construction_geometry: AoEPresentationGeometry | None
    construction_suppressions: tuple[SpellSuppression, ...]
    known_to_creator: bool
    supported_by_uuid: UUID | None
    contact_passage: ContactPassage
    surface_residues: tuple[ObjectResidueState, ...]
    linked_spatial_condition_uuid: UUID | None
    is_open: bool | None
    is_engaged: bool | None
    blocks_movement: bool
    blocks_optics: bool
    blocks_propagation: bool
    is_lit: bool | None


@with_config(ConfigDict(extra="forbid"))
class ItemStateChanges(TypedDict, total=False):
    """The `ItemState` fields one change replaces; omitted fields are unchanged."""

    stack_count: Annotated[int, Field(ge=0)]
    charges: Annotated[int, Field(ge=-1)] | None
    integrity: ItemIntegrity
    destruction_outcome: str | None
    remnant_state: ItemRemnantState | None
    current_hit_points: Annotated[int, Field(ge=0)] | None
    concentration_slots: tuple[ItemConcentrationSlot, ...]
    construction_owner_uuid: UUID | None
    construction_geometry: AoEPresentationGeometry | None
    construction_suppressions: tuple[SpellSuppression, ...]
    known_to_creator: bool
    supported_by_uuid: UUID | None
    contact_passage: ContactPassage
    surface_residues: tuple[ObjectResidueState, ...]
    linked_spatial_condition_uuid: UUID | None
    is_open: bool | None
    is_engaged: bool | None
    blocks_movement: bool
    blocks_optics: bool
    blocks_propagation: bool
    is_lit: bool | None


@dataclass(frozen=True, slots=True, kw_only=True)
class VisualItem:
    """One equipped layer; the item's look is in the seat's record of `item_uuid`."""

    slot: str
    item_uuid: UUID
    item_id: str
    is_lit: bool | None = None
