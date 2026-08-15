"""Temporary quarantine for backend-owned renderer and projection contracts.

These contracts remain active because events and item snapshots still carry
them.  They are intentionally excluded from :mod:`dnd.types`: they mix
renderer vocabulary, content authentication, and rule facts and must be
decomposed during the later presentation-boundary cut.
"""

from enum import Enum
from typing import Literal, Optional, Protocol, Tuple, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dnd.types.items import ItemRarity


class ActionPresentationKind(str, Enum):
    """Stable presentation semantics for an action event."""

    DEFAULT = "default"
    DRINK = "drink"


class VisualLoadoutSlot(str, Enum):
    """Dependency-neutral actor presentation slots shared with transport."""

    WEAPON_MELEE_MAIN = "weapon_melee_main"
    WEAPON_MELEE_OFF = "weapon_melee_off"
    WEAPON_RANGED_MAIN = "weapon_ranged_main"
    WEAPON_RANGED_OFF = "weapon_ranged_off"
    HELMET = "helmet"
    BODY_ARMOR = "body_armor"
    GAUNTLETS = "gauntlets"
    GREAVES = "greaves"
    BOOTS = "boots"
    AMULET = "amulet"
    CLOAK = "cloak"
    RING_LEFT = "ring_left"
    RING_RIGHT = "ring_right"


class EquipmentRenderLayer(str, Enum):
    """Dependency-neutral renderer layers contributed by equipped items."""

    BELT = "belt"
    CHEST = "chest"
    HANDS = "hands"
    HELMET = "helmet"
    LEGS = "legs"
    OFFHAND = "offhand"
    SHOES = "shoes"
    WEAPON = "weapon"


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


class ItemContentRefSnapshot(BaseModel):
    """Dependency-neutral cold copy of one authenticated item definition ref."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_id: str = Field(pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
    definition_kind: Literal["item", "environment_object"]
    content_id: str = Field(pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
    content_version: int = Field(ge=1)
    definition_contract_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ItemPresentationState(BaseModel):
    """Immutable item data needed to materialize an equipment/inventory row.

    The model deliberately contains only primitive values and dependency-leaf
    enums. It can therefore be carried by cold event/replay contracts without
    importing concrete items, Entity, runtime registries, or server DTOs.
    Location and equipped-slot membership live on the surrounding event.
    """

    model_config = ConfigDict(frozen=True)

    item_uuid: UUID = Field(description="Stable item instance identity.")
    content_ref: Optional[ItemContentRefSnapshot] = Field(
        default=None,
        description=(
            "Exact authenticated authored definition when this item was "
            "materialized through the content registry."
        ),
    )
    semantic_key: str = Field(description="Stable rules-content identity.")
    name: str = Field(description="Human-readable item name.")
    description: Optional[str] = Field(default=None, description="Optional rules/UI description.")
    item_kind: ItemPresentationKind = Field(description="Renderer/UI item family.")
    rarity: ItemRarity = Field(description="Item rarity.")
    weight: float = Field(description="Weight of one represented item in pounds.")
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


__all__ = [
    "ActionPresentationKind",
    "EquipmentRenderLayer",
    "EquippedVisualPolicy",
    "ItemContentRefSnapshot",
    "ItemPresentationKind",
    "ItemPresentationProvider",
    "ItemPresentationState",
    "VisualLoadoutSlot",
]
