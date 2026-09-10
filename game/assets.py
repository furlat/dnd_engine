"""Exact local asset catalogs and finite pygame Surface caches."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, cast

import numpy as np
import pygame


PACKAGE_ROOT = Path(__file__).resolve().parent
ASSET_ROOT = PACKAGE_ROOT / "assets"
DATA_ROOT = PACKAGE_ROOT / "data"


@dataclass(frozen=True, slots=True)
class AssetSpec:
    """One local raster resource used by the pygame presentation."""

    asset_id: str
    path: Path
    native_size: tuple[int, int]
    pivot: tuple[float, float]
    scale: float


@dataclass(frozen=True, slots=True)
class AssetCatalog:
    """Validated direct resources, bindings, animation, and Water constants."""

    resources: Mapping[str, AssetSpec]
    bindings: Mapping[str, object]
    flame_frames: tuple[str, ...]
    flame_fps: int
    water: Mapping[str, object]


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read asset data {path.name}: {exc}") from exc
    if type(value) is not dict:
        raise ValueError(f"asset data {path.name} must be an object")
    return value


def _contained_asset_path(relative: object) -> Path:
    if type(relative) is not str or not relative:
        raise ValueError("asset path must be a nonempty relative string")
    candidate = (ASSET_ROOT / relative).resolve()
    try:
        candidate.relative_to(ASSET_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"asset path escapes game/assets: {relative!r}") from exc
    return candidate


def _pair(value: object, *, name: str) -> tuple[float, float]:
    if (
        type(value) is not list
        or len(value) != 2
        or any(type(part) not in (int, float) for part in value)
    ):
        raise ValueError(f"{name} must contain exactly two numbers")
    return float(value[0]), float(value[1])


def _validate_bindings(bindings: dict[str, object]) -> None:
    """Require the exact finite tables used by this vertical seam."""
    poses = {"e", "n", "s", "w"}
    cliff = bindings.get("terrain_cliff")
    stairs = bindings.get("terrain_stairs")
    if type(cliff) is not dict or type(stairs) is not dict:
        raise ValueError("terrain requires direct cliff and stair profiles")
    for profile, role, tables in ((cliff, "cliff", ("straight", "corner")),
                                   (stairs, "stairs", ("poses",))):
        if profile.get("role") != role or profile.get("rise_steps") != 2:
            raise ValueError(f"{role} profile requires its role and two-step rise")
        for table_name in tables:
            table = profile.get(table_name)
            if type(table) is not dict or set(table) != poses:
                raise ValueError(f"{role}/{table_name} requires four exact poses")
    if cliff.get("upper_support_offset") != [0, 0]:
        raise ValueError("cliffs must support their owner Tile")
    if cliff.get("bed_material") != "earth":
        raise ValueError("rock cliffs require an earth bed")
    if stairs.get("support_offsets") != [[0, 0, 0], [-1, 0, 1], [-2, 0, 2]]:
        raise ValueError("stairs require the supported three-Tile straight run")
    terrain = bindings.get("terrain")
    items = bindings.get("items")
    treatments = bindings.get("treatments")
    if type(terrain) is not dict or set(terrain) != {"earth", "wood", "stone", "water"}:
        raise ValueError("terrain bindings require exact earth, wood, stone, and water rows")
    for material in ("earth", "wood", "stone"):
        table = terrain[material]
        if type(table) is not dict or set(table) != poses:
            raise ValueError(f"terrain {material} bindings require four exact poses")
    if terrain["water"] != "water.unity":
        raise ValueError("terrain water requires the direct Water material binding")
    for table_name in (
        "stone_wall_straight",
        "stone_wall_corner",
        "wood_wall_straight",
        "wood_wall_corner",
        "stone_door_frame",
        "wood_door_closed",
        "wood_door_open",
    ):
        table = bindings.get(table_name)
        if type(table) is not dict or set(table) != poses:
            raise ValueError(f"{table_name} bindings require four exact poses")
    if (
        type(items) is not dict
        or set(items) != {"environment.standing_torch"}
    ):
        raise ValueError("item bindings require the exact standing torch row")
    if type(treatments) is not dict or set(treatments) != {
        "0", "1", "2", "3", "4", "memory", "authored"
    }:
        raise ValueError("treatments require five light rows, memory, and authored")
    for treatment_id, treatment in treatments.items():
        if type(treatment) is not dict or type(treatment.get("id")) is not str:
            raise ValueError(f"treatment {treatment_id} requires a direct ID")
        rgb = treatment.get("rgb")
        if (
            type(rgb) is not list
            or len(rgb) != 3
            or any(type(channel) not in (int, float) for channel in rgb)
        ):
            raise ValueError(f"treatment {treatment_id} rgb requires three numbers")


def load_catalog() -> AssetCatalog:
    """Validate the two direct JSON catalogs and every copied file."""
    assets = _read_json(DATA_ROOT / "assets.json")
    bindings = _read_json(DATA_ROOT / "world_bindings.json")
    if assets.get("schema_version") != 1 or bindings.get("schema_version") != 1:
        raise ValueError("unsupported game asset schema version")
    raw_resources = assets.get("resources")
    raw_animations = assets.get("animations")
    raw_water = assets.get("water")
    if type(raw_resources) is not dict or type(raw_animations) is not dict:
        raise ValueError("assets.json lacks direct resources or animations")
    if type(raw_water) is not dict:
        raise ValueError("assets.json lacks Water material constants")

    resources: dict[str, AssetSpec] = {}
    for asset_id, raw in raw_resources.items():
        if type(asset_id) is not str or type(raw) is not dict:
            raise ValueError("every resource must be an ID/object pair")
        path = _contained_asset_path(raw.get("path"))
        if not path.is_file():
            raise ValueError(f"missing asset {asset_id}: {path}")
        raw_native_size = raw.get("native_size")
        if (
            type(raw_native_size) is not list
            or len(raw_native_size) != 2
            or any(type(part) is not int or part <= 0 for part in raw_native_size)
        ):
            raise ValueError(f"{asset_id} native_size must contain two positive integers")
        native_size = raw_native_size[0], raw_native_size[1]
        pivot = _pair(raw.get("pivot"), name=f"{asset_id} pivot")
        scale = raw.get("scale")
        if type(scale) not in (int, float):
            raise ValueError(f"{asset_id} scale must be positive")
        numeric_scale = cast(float | int, scale)
        if numeric_scale <= 0:
            raise ValueError(f"{asset_id} scale must be positive")
        resources[asset_id] = AssetSpec(
            asset_id=asset_id,
            path=path,
            native_size=native_size,
            pivot=pivot,
            scale=float(numeric_scale),
        )

    flame = raw_animations.get("torch.flame")
    if type(flame) is not dict:
        raise ValueError("torch.flame animation is missing")
    frames = flame.get("frames")
    fps = flame.get("fps")
    if (
        type(frames) is not list
        or len(frames) != 16
        or len(set(frames)) != 16
        or any(type(frame) is not str or frame not in resources for frame in frames)
        or type(fps) is not int
        or fps <= 0
    ):
        raise ValueError("torch.flame requires 16 unique ordered frames and positive fps")

    expected_bindings = {
        "terrain_cliff",
        "terrain_stairs",
        "terrain",
        "stone_wall_straight",
        "stone_wall_corner",
        "wood_wall_straight",
        "wood_wall_corner",
        "stone_door_frame",
        "wood_door_closed",
        "wood_door_open",
        "items",
        "treatments",
    }
    if set(bindings) != {"schema_version", *expected_bindings}:
        raise ValueError("world_bindings.json has an unknown or missing direct table")
    _validate_bindings(bindings)
    referenced = _binding_asset_ids(bindings)
    unknown = referenced - set(resources) - {"water.unity"}
    if unknown:
        raise ValueError(f"unknown bound asset IDs: {sorted(unknown)}")
    for key in ("mask", "ripple", "normal"):
        if raw_water.get(key) not in resources:
            raise ValueError(f"Water {key} resource is missing")

    stairs = cast(dict, bindings["terrain_stairs"])
    contacts = stairs.get("contacts_px")
    if type(contacts) is not dict or set(contacts) != {"e", "n", "s", "w"}:
        raise ValueError("stairs require contacts for each pose")
    for pose, asset_id in stairs["poses"].items():
        points = contacts[pose]
        if type(points) is not list or len(points) != 3:
            raise ValueError("stairs require entry, mid and upper contacts")
        pairs = tuple(_pair(point, name="stair contact") for point in points)
        if pairs[0] != resources[asset_id].pivot:
            raise ValueError("stair pivot must attach to its lower contact")

    return AssetCatalog(
        resources=MappingProxyType(resources),
        bindings=MappingProxyType(bindings),
        flame_frames=tuple(frames),
        flame_fps=fps,
        water=MappingProxyType(raw_water),
    )


def _binding_asset_ids(bindings: dict[str, object]) -> set[str]:
    result: set[str] = set()
    stack = [
        bindings[key]
        for key in (
            "terrain",
            "stone_wall_straight",
            "stone_wall_corner",
            "wood_wall_straight",
            "wood_wall_corner",
            "stone_door_frame",
            "wood_door_closed",
            "wood_door_open",
            "items",
        )
    ]
    cliff = cast(dict, bindings["terrain_cliff"])
    stairs = cast(dict, bindings["terrain_stairs"])
    stack.extend((cliff["straight"], cliff["corner"], stairs["poses"]))
    while stack:
        value = stack.pop()
        if type(value) is dict:
            stack.extend(value.values())
        elif type(value) is str:
            result.add(value)
        else:
            raise ValueError("asset binding leaves must be direct string IDs")
    return result


class SurfaceCache:
    """Canonical decoded Surfaces plus finite scaled/tinted derivatives."""

    def __init__(self, catalog: AssetCatalog) -> None:
        if pygame.display.get_surface() is None:
            raise RuntimeError("pygame display must be initialized before asset loading")
        self.catalog = catalog
        canonical: dict[str, pygame.Surface] = {}
        for asset_id, spec in catalog.resources.items():
            try:
                surface = pygame.image.load(spec.path).convert_alpha()
            except pygame.error as exc:
                raise ValueError(f"cannot decode asset {asset_id}: {exc}") from exc
            if surface.get_size() != spec.native_size:
                raise ValueError(
                    f"asset dimension mismatch for {asset_id}: "
                    f"{surface.get_size()} != {spec.native_size}"
                )
            canonical[asset_id] = surface
        self.canonical: Mapping[str, pygame.Surface] = MappingProxyType(canonical)
        self._scaled: dict[tuple[str, float], pygame.Surface] = {}
        self._treated: dict[tuple[str, float, tuple[float, float, float]], pygame.Surface] = {}
        self._alpha_bounds: dict[tuple[str, float], tuple[int, int, int, int]] = {}
        self._cropped_treated: dict[
            tuple[str, float, tuple[float, float, float]], pygame.Surface
        ] = {}
        self._rgb: dict[str, np.ndarray] = {}
        self._qualified_alpha_counts: dict[tuple[str, float, float], int] = {}
        self.debug_font = pygame.font.Font(None, 18)
        self.cache_hits = 0
        self.cache_rebuilds = 0

    def rgb(self, asset_id: str) -> np.ndarray:
        """Return one cached x-major RGB sample array for a canonical texture."""
        cached = self._rgb.get(asset_id)
        if cached is not None:
            self.cache_hits += 1
            return cached
        values = pygame.surfarray.array3d(self.canonical[asset_id]).astype(np.float32)
        values *= np.float32(1.0 / 255.0)
        values.setflags(write=False)
        self._rgb[asset_id] = values
        self.cache_rebuilds += 1
        return values

    def qualified_alpha_pixels(
        self,
        asset_id: str,
        zoom: float,
        cutoff: float,
    ) -> int:
        """Count cached scaled-mask pixels admitted by one material cutoff."""
        key = asset_id, zoom, cutoff
        cached = self._qualified_alpha_counts.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        alpha = pygame.surfarray.array_alpha(self.scaled(asset_id, zoom))
        count = int(np.count_nonzero(alpha.astype(np.float32) / 255.0 >= cutoff))
        self._qualified_alpha_counts[key] = count
        self.cache_rebuilds += 1
        return count

    def scaled(self, asset_id: str, zoom: float) -> pygame.Surface:
        """Return a nearest-neighbor scaled immutable-source derivative."""
        key = asset_id, zoom
        cached = self._scaled.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        spec = self.catalog.resources[asset_id]
        source = self.canonical[asset_id]
        factor = zoom * spec.scale
        size = (
            max(1, round(spec.native_size[0] * factor)),
            max(1, round(spec.native_size[1] * factor)),
        )
        scaled = pygame.transform.scale(source, size)
        self._scaled[key] = scaled
        self.cache_rebuilds += 1
        return scaled

    def treated(
        self,
        asset_id: str,
        zoom: float,
        multiplier: tuple[float, float, float],
    ) -> pygame.Surface:
        """Multiply only RGB channels while preserving copied alpha."""
        key = asset_id, zoom, multiplier
        cached = self._treated.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        result = self.scaled(asset_id, zoom).copy()
        pixels = pygame.surfarray.pixels3d(result)
        multiplied = np.clip(
            pixels.astype(np.float32) * np.asarray(multiplier, dtype=np.float32),
            0,
            255,
        ).astype(np.uint8)
        pixels[...] = multiplied
        del pixels
        self._treated[key] = result
        self.cache_rebuilds += 1
        return result

    def alpha_bounds(self, asset_id: str, zoom: float) -> tuple[int, int, int, int]:
        """Return the cached nontransparent bound within one scaled raster."""
        key = asset_id, zoom
        cached = self._alpha_bounds.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        rect = self.scaled(asset_id, zoom).get_bounding_rect(min_alpha=1)
        if rect.width <= 0 or rect.height <= 0:
            raise ValueError(f"asset {asset_id} has no nontransparent pixels")
        bounds = rect.x, rect.y, rect.width, rect.height
        self._alpha_bounds[key] = bounds
        self.cache_rebuilds += 1
        return bounds

    def cropped_treated(
        self,
        asset_id: str,
        zoom: float,
        multiplier: tuple[float, float, float],
    ) -> pygame.Surface:
        """Return a treated raster cropped only around zero-alpha margins."""
        key = asset_id, zoom, multiplier
        cached = self._cropped_treated.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        bounds = self.alpha_bounds(asset_id, zoom)
        cropped = self.treated(asset_id, zoom, multiplier).subsurface(bounds)
        self._cropped_treated[key] = cropped
        self.cache_rebuilds += 1
        return cropped

    def blit_position(
        self,
        asset_id: str,
        zoom: float,
        contact: tuple[float, float],
    ) -> tuple[int, int]:
        """Resolve the authored pivot against one projected support contact."""
        spec = self.catalog.resources[asset_id]
        factor = zoom * spec.scale
        return (
            round(contact[0] - spec.pivot[0] * factor),
            round(contact[1] - spec.pivot[1] * factor),
        )


def flame_frame_index(time_seconds: float, *, frame_count: int = 16, fps: int = 10) -> int:
    """Select the exact authored flame frame from the shared presentation clock."""
    return int(max(0.0, time_seconds) * fps) % frame_count


__all__ = [
    "ASSET_ROOT",
    "AssetCatalog",
    "AssetSpec",
    "SurfaceCache",
    "flame_frame_index",
    "load_catalog",
]
