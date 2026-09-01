"""Dependency-neutral item presentation and location contracts."""

from enum import Enum
from typing import Optional, Protocol, Tuple, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dnd.types.world_placement import BoundaryStructure

class ItemRarity(str, Enum):
    """Stable rarity labels carried by item definitions and presentation facts."""

    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    LEGENDARY = "legendary"


class EquippedVisualPolicy(str, Enum):
    """Whether equipped gear contributes a separate actor-rendering layer."""

    VISIBLE = "visible"
    HIDDEN = "hidden"


class ItemPresentationKind(str, Enum):
    """Small renderer/UI-facing item family classification."""

    ITEM = "item"
    USABLE = "usable"
    WEAPON = "weapon"
    ARMOR = "armor"
    SHIELD = "shield"


class ItemLocation(str, Enum):
    """Authoritative placement represented by an item location-state fact."""

    FLOOR = "floor"
    INVENTORY = "inventory"
    EQUIPMENT = "equipment"
    MERGED = "merged"
    DESTROYED = "destroyed"


class ItemPresentationState(BaseModel):
    """Immutable item data needed to materialize an equipment/inventory row.

    The model deliberately contains only primitive values and dependency-leaf
    enums. It can therefore be carried by cold event/replay contracts without
    importing concrete items, Entity, runtime registries, or server DTOs.
    Location and equipped-slot membership live on the surrounding event.
    """

    model_config = ConfigDict(frozen=True)

    item_uuid: UUID = Field(description="Stable item instance identity.")
    item_id: str = Field(
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
        description="Direct authored item species identity.",
    )
    name: str = Field(description="Human-readable item name.")
    description: Optional[str] = Field(default=None, description="Optional rules/UI description.")
    item_kind: ItemPresentationKind = Field(description="Renderer/UI item family.")
    rarity: ItemRarity = Field(description="Item rarity.")
    weight: float = Field(description="Weight of one represented item in pounds.")
    value: int = Field(default=0, description="Value in gold pieces.")
    tags: Tuple[str, ...] = Field(default=(), description="Stable item query tags.")
    is_pickable: bool = True
    is_equippable: bool = False
    is_usable: bool = False
    is_targetable: bool = False
    stack_id: Optional[str] = None
    visual_item_name: str = Field(description="Renderer item-catalog key.")
    visual_variant_id: Optional[str] = Field(default=None, description="Renderer variant key.")
    equipped_visual_policy: EquippedVisualPolicy = Field(
        description="Whether the equipped item contributes its own actor layer."
    )
    damage_dice: Optional[str] = Field(default=None, description="Weapon damage dice label.")
    damage_type: Optional[str] = Field(default=None, description="Weapon damage type label.")
    weapon_properties: Tuple[str, ...] = Field(
        default=(),
        description="Weapon properties in definition order.",
    )
    armor_type: Optional[str] = Field(default=None, description="Armor weight category.")
    armor_ac: Optional[int] = Field(default=None, description="Armor base AC.")
    shield_ac_bonus: Optional[int] = Field(default=None, description="Shield AC bonus.")
    charges: Optional[int] = Field(default=None, ge=-1, description="Current charges; -1 is unlimited.")
    max_charges: Optional[int] = Field(default=None, ge=-1, description="Maximum charges; -1 is unlimited.")
    stack_count: int = Field(ge=0, description="Copies represented after the fact.")
    max_stack: int = Field(ge=1, description="Maximum mergeable copies.")
    is_consumable: bool = Field(description="Whether successful use consumes a charge/item.")
    map_char: str = Field(default="φ", description="Text-map presentation glyph.")
    include_in_senses_objects: bool = True
    include_in_adjacent_senses_objects: bool = False
    include_in_available_object_actions: bool = True
    current_hit_points: Optional[int] = Field(default=None, ge=0)
    maximum_hit_points: Optional[int] = Field(default=None, ge=0)
    boundary_structure: Optional[BoundaryStructure] = None
    linked_spatial_condition_uuid: Optional[UUID] = None
    is_open: Optional[bool] = None
    blocks_movement: bool = False
    blocks_optics: bool = False
    blocks_propagation: bool = False
    is_lit: Optional[bool] = None
    very_bright_radius_feet: Optional[int] = Field(default=None, ge=0)
    bright_radius_feet: Optional[int] = Field(default=None, ge=0)
    dim_radius_feet: Optional[int] = Field(default=None, ge=0)


@runtime_checkable
class ItemPresentationProvider(Protocol):
    """Structural leaf surface for capturing cold item presentation state."""

    def to_item_presentation_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemPresentationState:
        """Return the item's immutable presentation snapshot."""
        ...


@runtime_checkable
class FiniteChargeProvider(Protocol):
    """Structural boundary for an item-backed finite action cost."""

    charges: int

    def consume_charge_with_event(
        self,
        amount: int,
        source_entity_uuid: UUID,
        parent_event: "Event",
    ) -> "Event":
        """Consume finite charges through the item's ordinary child event."""
        ...


__all__ = [
    "EquippedVisualPolicy",
    "FiniteChargeProvider",
    "ItemLocation",
    "ItemPresentationKind",
    "ItemPresentationProvider",
    "ItemPresentationState",
    "ItemRarity",
]
