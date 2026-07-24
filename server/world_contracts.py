"""Dependency-neutral transport contracts for projected game worlds.

These models describe reducer state only.  They do not know how to inspect
engine registries, entities, items, encounters, or grids; producer modules own
that projection policy.  Keeping the contract graph cold makes it safe for
subjective replication, objective diagnostics, replay validation, and SDK
generation to share the exact same DTO identities.
"""

from enum import Enum
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, JsonValue, RootModel, model_validator

from dnd.core.life_types import LifeState
from dnd.core.senses import SenseMode


class APIItemSummary(BaseModel):
    """Lightweight item metadata for inventory and equipment views."""

    uuid: str = Field(description="Stable item UUID serialized as text.")
    name: str = Field(description="Display name of the item.")
    description: Optional[str] = Field(
        default=None,
        description="Optional player-facing item description.",
    )
    item_type: str = Field(description="API category for the concrete item kind.")
    rarity: str = Field(description="Item rarity value.")
    weight: float = Field(description="Item weight in pounds.")
    is_equipped: bool = Field(description="Whether the item is currently equipped.")
    equipped_slot: Optional[str] = Field(
        default=None,
        description="Equipment slot name when the item is equipped.",
    )
    visual_item_name: str = Field(description="Effective renderer registry key for the item.")
    visual_variant_id: Optional[str] = Field(
        default=None,
        description="Renderer variant identifier for the item, if any.",
    )
    equipped_visual_policy: Literal["visible", "hidden"] = Field(
        description="Whether the equipped item contributes a separate actor layer."
    )
    damage_dice: Optional[str] = Field(
        default=None,
        description="Weapon damage dice such as 1d8 or 2d6.",
    )
    damage_type: Optional[str] = Field(default=None, description="Weapon damage type.")
    weapon_properties: List[str] = Field(
        default_factory=list,
        description="Weapon property names.",
    )
    armor_type: Optional[str] = Field(
        default=None,
        description="Armor category such as light, medium, or heavy.",
    )
    armor_ac: Optional[int] = Field(
        default=None,
        description="Base armor class value from worn armor.",
    )
    shield_ac_bonus: Optional[int] = Field(
        default=None,
        description="Armor class bonus granted by a shield.",
    )
    charges: Optional[int] = Field(
        default=None,
        description="Current usable-item charges, with -1 meaning unlimited.",
    )
    max_charges: Optional[int] = Field(
        default=None,
        description="Maximum usable-item charges.",
    )
    stack_count: Optional[int] = Field(
        default=None,
        description="Number of items represented by this stack.",
    )
    is_consumable: bool = Field(
        default=False,
        description="Whether use consumes the item or stack.",
    )


class APIEquipmentSlot(BaseModel):
    """One equipment slot and its current item."""

    slot: str = Field(description="Stable API slot name.")
    slot_type: str = Field(description="Slot category for client grouping.")
    item: Optional[APIItemSummary] = Field(
        default=None,
        description="Equipped item summary when the slot is occupied.",
    )


class APIEquipmentOverview(BaseModel):
    """Equipped slots, armor class, and carried inventory."""

    slots: List[APIEquipmentSlot] = Field(description="Equipment slots in stable display order.")
    ac: int = Field(description="Current armor class after equipment and modifiers.")
    inventory: List[APIItemSummary] = Field(description="Unequipped inventory item summaries.")


class APIAppearance(BaseModel):
    """Passive renderer identity metadata projected for one creature."""

    portrait_key: Optional[str] = Field(
        default=None,
        description="Stable authored-portrait key assigned by scenario composition.",
    )
    presentation_kind: Literal["layered", "placeholder"] = Field(
        default="layered",
        description="Renderer strategy for the actor body.",
    )
    visual_scale: float = Field(
        default=1.0,
        gt=0,
        le=4.0,
        description="Presentation-only actor scale independent of rules size.",
    )
    placeholder_tint: int = Field(
        default=0x36FF62,
        ge=0,
        le=0xFFFFFF,
        description="RGB body tint used by placeholder presentation.",
    )
    body_category: Literal["NakedBody", "NakedBody2", "NakedBody3"] = Field(
        default="NakedBody",
        description="Renderer body taxonomy key.",
    )
    skin_tint: int = Field(
        default=0xDDAA88,
        ge=0,
        le=0xFFFFFF,
        description="RGB tint applied to exposed skin or body material.",
    )
    head_category: Optional[
        Literal["Head1", "Head9", "Head10", "Head16", "Head17", "Head22"]
    ] = Field(
        default=None,
        description="Optional renderer head taxonomy key.",
    )
    hair_tint: int = Field(
        default=0,
        ge=0,
        le=0xFFFFFF,
        description="RGB tint applied to hair layers.",
    )
    has_beard: bool = Field(
        default=False,
        description="Whether the renderer includes the beard overlay.",
    )
    beard_tint: int = Field(
        default=0,
        ge=0,
        le=0xFFFFFF,
        description="RGB tint applied to the beard overlay.",
    )


class APIConditionSummary(BaseModel):
    """Authoritative public presentation for one live condition."""

    semantic_key: str = Field(
        min_length=1,
        description="Stable backend-authored rules identity for the condition.",
    )
    name: str = Field(min_length=1, description="Player-facing condition name.")
    description: str = Field(
        min_length=1,
        description="Player-facing rules summary from the live condition.",
    )
    category: str = Field(description="Condition category value.")
    duration_type: str = Field(description="Live condition duration mode.")
    remaining_rounds: Optional[int] = Field(
        default=None,
        description="Rounds remaining only for round-based durations.",
    )


class APIEntitySummary(BaseModel):
    """Lightweight renderer-complete entity snapshot."""

    uuid: str = Field(description="Stable entity UUID serialized as a string.")
    name: str = Field(description="Display name for the entity.")
    position: Tuple[int, int] = Field(description="Current grid position as an (x, y) pair.")
    hp: int = Field(description="Current hit points.")
    max_hp: int = Field(description="Maximum hit points after constitution and bonus HP.")
    ac: int = Field(description="Current armor class.")
    conditions: List[str] = Field(description="Active condition names keyed on the entity.")
    condition_details: List[APIConditionSummary] = Field(
        default_factory=list,
        description="Active condition names and categories for UI filters.",
    )
    life_state: LifeState = Field(description="Authoritative creature lifecycle state.")
    is_dead: bool = Field(description="Whether the authoritative lifecycle state is dead.")
    faction: Optional[str] = Field(
        default=None,
        description="Optional faction identifier used for ally/enemy grouping.",
    )
    creature_type: str = Field(description="D&D creature taxonomy value.")
    size: str = Field(description="D&D rules size value.")
    appearance: APIAppearance = Field(description="Passive renderer identity metadata.")

    @model_validator(mode="after")
    def validate_condition_name_projection(self) -> "APIEntitySummary":
        """Keep the temporary name list derived from authoritative detail rows."""
        detail_names = [detail.name for detail in self.condition_details]
        if self.conditions != detail_names:
            raise ValueError("conditions must equal condition detail names in order")
        return self


class APIDirectionalBlockMap(BaseModel):
    """Blocking flags for the four cardinal directions."""

    north: bool = Field(description="Whether passage toward north is blocked.")
    south: bool = Field(description="Whether passage toward south is blocked.")
    east: bool = Field(description="Whether passage toward east is blocked.")
    west: bool = Field(description="Whether passage toward west is blocked.")


class StructuralEdgeKind(str, Enum):
    """Privacy-safe visual identity for one tile boundary."""

    WALL = "wall"
    DOOR = "door"


class StructuralEdgeAppearance(BaseModel):
    """Renderer-safe boundary facts without an object identity or hidden-cell payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: StructuralEdgeKind = Field(
        description="Small visual family sufficient to distinguish a wall from a door."
    )
    is_open: Optional[bool] = Field(
        default=None,
        description="Explicit open state for a door; always null for a wall.",
    )

    @model_validator(mode="after")
    def validate_open_state(self) -> "StructuralEdgeAppearance":
        if self.kind is StructuralEdgeKind.DOOR:
            if self.is_open is None:
                raise ValueError("door structural edge requires explicit open state")
        elif self.is_open is not None:
            raise ValueError("wall structural edge cannot carry open state")
        return self


class DirectionalStructuralEdgeMap(BaseModel):
    """Privacy-safe structural appearance keyed by tile-local cardinal side."""

    north: Optional[StructuralEdgeAppearance] = None
    south: Optional[StructuralEdgeAppearance] = None
    east: Optional[StructuralEdgeAppearance] = None
    west: Optional[StructuralEdgeAppearance] = None


class APITile(BaseModel):
    """Single public tile snapshot."""

    x: int = Field(description="Tile x-coordinate.")
    y: int = Field(description="Tile y-coordinate.")
    visual_key: str = Field(
        min_length=1,
        description=(
            "Canonical terrain sprite key; display names are never used for "
            "renderer dispatch."
        ),
    )
    walkable: bool = Field(description="Whether the tile is passable before entity and object checks.")
    visible: bool = Field(description="Whether the tile is visible in the current map view.")
    name: str = Field(default="Floor", description="Tile terrain name.")
    walking_cost: int = Field(default=1, description="Normalized movement cost for entering the tile.")
    is_hazardous: bool = Field(
        default=False,
        description="Whether the tile is hazardous for the requesting entity.",
    )
    conditions: List[str] = Field(
        default_factory=list,
        description="Public condition names visible on the tile.",
    )
    condition_details: List[APIConditionSummary] = Field(
        default_factory=list,
        description="Authoritative public condition details visible on the tile.",
    )
    light_level: int = Field(default=3, description="Resolved light level enum value.")
    directional_blocks_movement: APIDirectionalBlockMap = Field(
        description="Directional movement blockers keyed by compass direction."
    )
    directional_blocks_vision: APIDirectionalBlockMap = Field(
        description="Directional vision blockers keyed by compass direction."
    )
    directional_blocks_light: APIDirectionalBlockMap = Field(
        description="Directional light blockers keyed by compass direction."
    )
    directional_blocks_propagation: APIDirectionalBlockMap = Field(
        description="Directional propagation blockers keyed by compass direction."
    )
    directional_structural_edges: DirectionalStructuralEdgeMap = Field(
        default_factory=DirectionalStructuralEdgeMap,
        description=(
            "Privacy-safe visual identity for authorized structural boundaries. "
            "Rows never carry object UUIDs, names, or hidden-cell payloads."
        ),
    )

    @model_validator(mode="after")
    def validate_condition_name_projection(self) -> "APITile":
        """Keep tile names synchronized with the authorized detail rows."""
        detail_names = [detail.name for detail in self.condition_details]
        if self.conditions != detail_names:
            raise ValueError("conditions must equal condition detail names in order")
        return self


class APIGrid(BaseModel):
    """Public grid snapshot with inclusive bounds."""

    min_x: int = Field(description="Minimum x-coordinate included in the grid bounds.")
    min_y: int = Field(description="Minimum y-coordinate included in the grid bounds.")
    max_x: int = Field(description="Maximum x-coordinate included in the grid bounds.")
    max_y: int = Field(description="Maximum y-coordinate included in the grid bounds.")
    tiles: List[APITile] = Field(description="Serialized tiles in the grid.")


class APICombatant(BaseModel):
    """Combatant in objective initiative order."""

    uuid: str = Field(description="Stable combatant entity UUID serialized as a string.")
    name: str = Field(description="Combatant display name.")
    initiative: int = Field(description="Initiative total used for turn ordering.")
    life_state: Optional[LifeState] = Field(
        default=None,
        description="Authoritative lifecycle state when the entity still resolves.",
    )
    is_dead: bool = Field(description="Whether the authoritative lifecycle state is dead.")


class APIEncounter(BaseModel):
    """Objective encounter combat state."""

    uuid: str = Field(description="Stable encounter UUID serialized as a string.")
    name: str = Field(description="Encounter display name.")
    state: str = Field(description="Encounter lifecycle state value.")
    round_number: int = Field(description="Current combat round number.")
    current_turn_index: int = Field(
        description="Index of the acting combatant in initiative order."
    )
    current_entity_uuid: Optional[str] = Field(
        default=None,
        description="UUID of the current acting entity, if any.",
    )
    initiative_order: List[APICombatant] = Field(
        description="Combatants ordered by initiative."
    )


class APIFloorObject(BaseModel):
    """Objective floor object or item on the ground."""

    uuid: str = Field(description="Stable object UUID serialized as a string.")
    name: str = Field(description="Object display name.")
    position: Tuple[int, int] = Field(
        description="Grid position serialized as an (x, y) pair."
    )
    map_char: str = Field(default="φ", description="Map glyph used to render the object.")
    state: Dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Object-specific JSON state keyed by the concrete item model.",
    )


class APIGameState(BaseModel):
    """Complete objective game-state snapshot."""

    grid: APIGrid = Field(description="Public grid snapshot.")
    entities: List[APIEntitySummary] = Field(
        description="Lightweight entity summaries visible to the client."
    )
    encounter: Optional[APIEncounter] = Field(
        default=None,
        description="Active encounter snapshot, if combat is active.",
    )
    floor_objects: List[APIFloorObject] = Field(
        default_factory=list,
        description="Public floor-object summaries.",
    )


class APIEntityVisibility(BaseModel):
    """Current perception state for one observing entity."""

    name: str = Field(description="Observer display name.")
    position: Tuple[int, int] = Field(description="Observer grid position.")
    visible_cells: List[Tuple[int, int]] = Field(description="Cells visible now.")
    visible_entities: List[str] = Field(description="Entity UUIDs visible now.")
    visible_objects: List[str] = Field(description="Object UUIDs visible now.")
    seen_cells: List[Tuple[int, int]] = Field(
        description="Cells observed previously or currently."
    )
    sense_modes: List[SenseMode] = Field(description="Active special senses.")
    effective_light_levels: Dict[str, int] = Field(
        description=(
            "Backend-resolved subjective light levels for currently visible cells, "
            "keyed as 'x,y'."
        )
    )


class APIVisibilityResponse(RootModel[Dict[str, APIEntityVisibility]]):
    """Visibility rows keyed by observer UUID."""


__all__ = [
    "APIAppearance",
    "APICombatant",
    "APIConditionSummary",
    "APIDirectionalBlockMap",
    "DirectionalStructuralEdgeMap",
    "APIEncounter",
    "APIEntitySummary",
    "APIEntityVisibility",
    "APIEquipmentOverview",
    "APIEquipmentSlot",
    "APIFloorObject",
    "APIGameState",
    "APIGrid",
    "APIItemSummary",
    "APITile",
    "APIVisibilityResponse",
    "StructuralEdgeAppearance",
    "StructuralEdgeKind",
]
