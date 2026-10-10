"""Exact local asset catalogs and finite pygame Surface caches."""

from __future__ import annotations

from dataclasses import dataclass
from collections import OrderedDict
import json
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping


from game.asset_types import AssetSpec as AssetSpec, image_resources
from game.animation_types import ParticleMediaAsset, PropAnimation, TetherAnimation
from game.residue_media import region_media_assets
from game.world_animation import WorldTransitionSample, prop_animation
from game.surface_residue import LiquidSurfaceStyle, ResidueSurfaceCache, ResidueSurfaceStyle, WallFace
from game.world_binding_types import AssetDocument, WorldBindingsSource

import numpy as np
import pygame


PACKAGE_ROOT = Path(__file__).resolve().parent
ASSET_ROOT = PACKAGE_ROOT / "assets"
DATA_ROOT = PACKAGE_ROOT / "data"


@dataclass(frozen=True, slots=True)
class LitAnimation:
    """A prop's optional flame loop, selected by its recorded lit state."""

    frames: tuple[str, ...]
    fps: int


@dataclass(frozen=True, slots=True)
class PropBinding:
    body_by_pose: Mapping[str, str]
    lit_animation: LitAnimation | None
    state_field: Literal["is_open", "is_engaged"] | None
    active_body_by_pose: Mapping[str, str] | None
    transition: PropAnimation | None = None


@dataclass(frozen=True, slots=True)
class AssetCatalog:
    """Direct resources, bindings, animation, and Water constants."""

    world_source: WorldBindingsSource
    resources: Mapping[str, AssetSpec]
    bindings: Mapping[str, object]
    flame_frames: tuple[str, ...]
    flame_fps: int
    water: Mapping[str, object]
    props: Mapping[str, PropBinding]
    spatial_effects: Mapping[str, PropAnimation]
    spatial_tethers: Mapping[str, TetherAnimation]
    spatial_residue_overlays: Mapping[tuple[str, str], Mapping[str, tuple[str, ...]]]
    residue_particles: Mapping[str, ParticleMediaAsset]
    residue_ground: Mapping[str, Mapping[str, str]]
    residue_surfaces: Mapping[str, ResidueSurfaceStyle]
    residue_wall_faces: Mapping[str, Mapping[str, tuple[WallFace, ...]]]
    liquid_surfaces: Mapping[str, LiquidSurfaceStyle]


def prop_animation_frame(animation: PropAnimation, pose: str, state: str | None,
                         transition: WorldTransitionSample | None = None) -> tuple[str, int]:
    """Sample the same finite picture sequence for props and ground devices."""
    frame = animation.default_frame if state is None else animation.state_frames[state]
    if transition is not None:
        change = transition.transition
        if transition.elapsed_ms < 0 and change.previous is not None:
            frame = animation.state_frames[change.previous]
            return animation.frames_by_pose[pose][frame], frame
        sequence = ()
        if change.field == "activation":
            sequence = animation.activation_frames
        elif change.current == state:
            sequence = animation.transition_frames.get(f"{change.previous}:{change.current}", ())
        if sequence:
            index = min(len(sequence) - 1, int(max(0, transition.elapsed_ms) * animation.fps / 1000))
            frame = sequence[index]
            return animation.frames_by_pose[pose][frame], frame
        if change.field == "activation":
            return animation.frames_by_pose[pose][frame], frame
    if transition is not None and (transition.transition.field == "creation" or transition.transition.current == state):
        if transition.transition.field == "creation":
            start = animation.creation_start_frame
        else:
            assert transition.transition.previous is not None
            start = animation.state_frames[transition.transition.previous]
        if start is None:
            return animation.frames_by_pose[pose][frame], frame
        advance = int(max(0, transition.elapsed_ms) * animation.fps / 1000)
        frame = start + min(abs(frame - start), advance) * (1 if frame >= start else -1)
    return animation.frames_by_pose[pose][frame], frame


def catalog_from_documents(
    assets: dict[str, object], bindings: dict[str, object] | WorldBindingsSource
) -> AssetCatalog:
    """Assemble the checked-in catalog values without filesystem validation."""
    source = AssetDocument.model_validate(assets)
    world = (bindings if isinstance(bindings, WorldBindingsSource)
             else WorldBindingsSource.model_validate_json(json.dumps(bindings)))
    flame = source.animations["torch.flame"]
    resources = image_resources(source.resources, ASSET_ROOT)
    props = {}
    for item_id, row in world.props.items():
        loop = source.animations[row.lit_animation] if row.lit_animation is not None else None
        props[item_id] = PropBinding(
            body_by_pose=MappingProxyType(row.body_by_pose),
            lit_animation=None if loop is None else LitAnimation(loop.frames, loop.fps),
            state_field=row.state_field,
            active_body_by_pose=(MappingProxyType(row.active_body_by_pose)
                                 if row.active_body_by_pose is not None else None),
            transition=prop_animation(row.transition) if row.transition is not None else None,
        )
    face_profiles = {identity: MappingProxyType({pose: tuple(
        WallFace(face.origin, face.across, face.down, face.reverse)
        for face in faces) for pose, faces in poses.items()})
        for identity, poses in world.residue_wall_faces.profiles.items()}
    return AssetCatalog(
        world_source=world,
        resources=MappingProxyType(resources),
        bindings=MappingProxyType(world.model_dump(mode="json")),
        flame_frames=flame.frames,
        flame_fps=flame.fps,
        # Existing material consumers use JSON vector arrays; retain that public shape.
        water=MappingProxyType(source.water.model_dump(mode="json")),
        props=MappingProxyType(props),
        spatial_effects=MappingProxyType({identity: prop_animation(row)
            for identity, row in world.spatial_effects.items()}),
        spatial_tethers=MappingProxyType({identity: TetherAnimation(
            MappingProxyType(row.tether.frames_by_facing), MappingProxyType(row.tether.endpoints_by_facing),
            row.tether.fps,
        ) for identity, row in world.spatial_effects.items() if row.tether is not None}),
        spatial_residue_overlays=MappingProxyType({
            (identity, residue): MappingProxyType(poses)
            for identity, row in world.spatial_effects.items()
            for residue, poses in row.residue_overlays.items()
        }),
        residue_particles=MappingProxyType({identity: region_media_assets()[asset]
            for identity, asset in world.residue_particles.items()}),
        residue_ground=MappingProxyType({identity: MappingProxyType(poses)
            for identity, poses in world.residue_ground.items()}),
        residue_surfaces=MappingProxyType({identity: ResidueSurfaceStyle(
            row.floor_atlas, row.wall_atlas, row.floor_opacity, row.wall_opacity)
            for identity, row in world.residue_surfaces.items()}),
        residue_wall_faces=MappingProxyType({identity: face_profiles[profile]
            for identity, profile in world.residue_wall_faces.assets.items()}),
        liquid_surfaces=MappingProxyType({identity: LiquidSurfaceStyle(
            asset=region_media_assets()[row.asset_id], ellipse=row.ellipse, opacity=row.opacity,
        ) for identity, row in world.liquid_surfaces.items()}),
    )


def load_catalog() -> AssetCatalog:
    """Read bundled catalog values; decode each used raster in the presentation session."""
    return catalog_from_documents(
        json.loads((DATA_ROOT / "assets.json").read_text(encoding="utf-8")),
        json.loads((DATA_ROOT / "world_bindings.json").read_text(encoding="utf-8")),
    )


class SurfaceCache:
    """Canonical decoded Surfaces plus finite scaled/tinted derivatives."""

    def __init__(self, catalog: AssetCatalog, *, coverage_limit_bytes: int = 16 * 1024 * 1024) -> None:
        if pygame.display.get_surface() is None:
            raise RuntimeError("pygame display must be initialized before asset loading")
        self.catalog = catalog
        self.surface_residues = ResidueSurfaceCache()
        self._canonical: dict[str, pygame.Surface] = {}
        self._source_pages: dict[Path, pygame.Surface] = {}
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
        self.coverage_limit_bytes = coverage_limit_bytes
        self.coverage_bytes = 0
        self.coverage_evictions = 0
        self._coverage: OrderedDict[tuple[object, ...], np.ndarray] = OrderedDict()

    def _retain_coverage(self, key: tuple[object, ...], mask: np.ndarray) -> np.ndarray:
        mask.setflags(write=False)
        if mask.nbytes <= self.coverage_limit_bytes:
            while self._coverage and self.coverage_bytes + mask.nbytes > self.coverage_limit_bytes:
                _, old = self._coverage.popitem(last=False)
                self.coverage_bytes -= old.nbytes
                self.coverage_evictions += 1
            self._coverage[key] = mask
            self.coverage_bytes += mask.nbytes
        self.cache_rebuilds += 1
        return mask

    def coverage(self, asset_id: str, zoom: float, *, cropped: bool = True) -> np.ndarray:
        """Physical alpha is shared by all RGB/light treatments of this source."""
        key = ('alpha', asset_id, zoom, cropped)
        value = self._coverage.get(key)
        if value is not None:
            self._coverage.move_to_end(key)
            self.cache_hits += 1
            return value
        image = self.scaled(asset_id, zoom)
        if cropped:
            image = image.subsurface(self.alpha_bounds(asset_id, zoom))
        return self._retain_coverage(key, pygame.surfarray.array_alpha(image) > 0)

    def support_coverage(self, asset_id: str, zoom: float,
                         vertices: tuple[tuple[int, int], ...]) -> np.ndarray:
        """Cache only exact local raster geometry, including pan-rounding phase."""
        key = ('support', asset_id, zoom, vertices)
        value = self._coverage.get(key)
        if value is not None:
            self._coverage.move_to_end(key)
            self.cache_hits += 1
            return value
        physical = self.coverage(asset_id, zoom)
        polygon = pygame.Surface(physical.shape, pygame.SRCALPHA)
        pygame.draw.polygon(polygon, 'white', vertices)
        return self._retain_coverage(key, (pygame.surfarray.array_alpha(polygon) > 0) & physical)

    def canonical(self, asset_id: str) -> pygame.Surface:
        """Decode a requested world raster once in this presentation session."""
        cached = self._canonical.get(asset_id)
        if cached is not None:
            return cached
        spec = self.catalog.resources[asset_id]
        try:
            page = self._source_pages.get(spec.path)
            if page is None:
                page = pygame.image.load(spec.path).convert_alpha()
                self._source_pages[spec.path] = page
            surface = page if spec.rect is None else page.subsurface(spec.rect)
        except pygame.error as exc:
            raise ValueError(f"cannot decode asset {asset_id}: {exc}") from exc
        self._canonical[asset_id] = surface
        return surface

    def rgb(self, asset_id: str) -> np.ndarray:
        """Return one cached x-major RGB sample array for a canonical texture."""
        cached = self._rgb.get(asset_id)
        if cached is not None:
            self.cache_hits += 1
            return cached
        values = pygame.surfarray.array3d(self.canonical(asset_id)).astype(np.float32)
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
        source = self.canonical(asset_id)
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
