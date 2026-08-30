"""Dependency-neutral semantic Tile surface values."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Material(StrEnum):
    """Authored materials used by world builders and physical content."""

    EARTH = "earth"
    SAND = "sand"
    STONE = "stone"
    WOOD = "wood"
    METAL = "metal"
    FABRIC = "fabric"
    GLASS = "glass"
    WATER = "water"
    ICE = "ice"
    VEGETATION = "vegetation"


class SurfaceLayer(BaseModel):
    """One ordered semantic layer above a Tile base material."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    material: Material
    description: str = ""


class TileSurface(BaseModel):
    """Immutable semantic composition of one support Tile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_material: Material
    layers: tuple[SurfaceLayer, ...] = ()
    description: str = ""


__all__ = ["Material", "SurfaceLayer", "TileSurface"]
