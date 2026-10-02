"""Explicit hand substitutions and sampled ground media over existing item identity."""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from dnd.core.equipment_types import VisualLoadoutSlot
from dnd.items.authored_variant_inventory import AuthoredItemEquipmentLayer


class HandAppearance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    category: str
    variant: str | None = None
    slot: VisualLoadoutSlot
    layers: tuple[AuthoredItemEquipmentLayer, ...]
    notes: str


class GroundAppearance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    category: str
    variant: str | None = None
    sprite_key: str
    layers: tuple[AuthoredItemEquipmentLayer, ...] = ()
    clip: str = "Idle"
    frame: int = Field(default=0, ge=0)
    rows_by_camera: tuple[int, int, int, int]
    cell: tuple[int, int] = (128, 128)
    pivots_by_camera: tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]
    scale: float = Field(gt=0)
    reference_tile_width: float = Field(gt=0)
    tint: int = Field(ge=0, le=0xFFFFFF)
    rotation: float = 0
    shadow_sprite_key: str | None = None
    shadow_scale: float = Field(default=.18, gt=0)
    notes: str


class ItemAppearanceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: int
    hands: tuple[HandAppearance, ...]
    ground: tuple[GroundAppearance, ...]


class SourcePalette(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    category: str
    colors: tuple[int, ...]
    isGray: tuple[bool, ...]


class SourcePaletteDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: int
    entries: tuple[SourcePalette, ...]


@lru_cache(maxsize=1)
def item_source_palettes() -> dict[str, tuple[int, ...]]:
    path = Path(__file__).parent / "data/neuroclient/source/src/render/data/animation/paletteMap.json"
    document = SourcePaletteDocument.model_validate_json(path.read_text())
    return {entry.category: entry.colors for entry in document.entries}


@lru_cache(maxsize=1)
def load_item_appearances() -> ItemAppearanceDocument:
    document = ItemAppearanceDocument.model_validate_json(
        (Path(__file__).parent / "data/item_appearances.json").read_text())
    hands = [(row.category, row.variant, row.slot) for row in document.hands]
    ground = [(row.category, row.variant) for row in document.ground]
    if len(hands) != len(set(hands)) or len(ground) != len(set(ground)):
        raise ValueError("duplicate item appearance identity/slot")
    return document


def hand_appearance(category: str, variant: str | None,
                    slot: VisualLoadoutSlot) -> HandAppearance | None:
    return next((row for row in load_item_appearances().hands
                 if (row.category, row.variant, row.slot) == (category, variant, slot)), None)


def ground_appearance(category: str, variant: str | None) -> GroundAppearance | None:
    return next((row for row in load_item_appearances().ground
                 if (row.category, row.variant) == (category, variant)), None)
