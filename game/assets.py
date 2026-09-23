"""Exact local asset catalogs and finite pygame Surface caches."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping, cast

from game.asset_types import AssetSpec as AssetSpec, image_resources
from game.animation_types import ParticleMediaAsset, PropAnimation, TetherAnimation
from game.residue_media import region_media_assets
from game.world_animation import WorldTransitionSample, prop_animation
from game.surface_residue import LiquidSurfaceStyle, ResidueSurfaceCache, ResidueSurfaceStyle, WallFace
from dnd.types.residues import ResidueEllipse

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
    assets: dict[str, object], bindings: dict[str, object]
) -> AssetCatalog:
    """Assemble the checked-in catalog values without filesystem validation."""
    raw_resources = cast(dict, assets["resources"])
    animations = cast(dict, assets["animations"])
    flame = cast(dict, animations["torch.flame"])
    resources = image_resources(raw_resources, ASSET_ROOT)
    props = {}
    for item_id, row in cast(dict, bindings["props"]).items():
        loop = animations[row["lit_animation"]] if row["lit_animation"] is not None else None
        props[item_id] = PropBinding(
            body_by_pose=MappingProxyType(row["body_by_pose"]),
            lit_animation=None if loop is None else LitAnimation(tuple(loop["frames"]), loop["fps"]),
            state_field=row.get("state_field"),
            active_body_by_pose=(MappingProxyType(row["active_body_by_pose"])
                                 if "active_body_by_pose" in row else None),
            transition=prop_animation(row["transition"]) if "transition" in row else None,
        )
    wall_faces = cast(dict, bindings.get("residue_wall_faces", {}))
    face_profiles = {identity: MappingProxyType({pose: tuple(
        WallFace(tuple(face["origin"]), tuple(face["across"]), tuple(face["down"]), face.get("reverse", False))
        for face in faces) for pose, faces in poses.items()})
        for identity, poses in wall_faces.get("profiles", {}).items()}
    return AssetCatalog(
        resources=MappingProxyType(resources),
        bindings=MappingProxyType(bindings),
        flame_frames=tuple(flame["frames"]),
        flame_fps=flame["fps"],
        water=MappingProxyType(cast(dict, assets["water"])),
        props=MappingProxyType(props),
        spatial_effects=MappingProxyType({identity: prop_animation(row)
            for identity, row in cast(dict, bindings.get("spatial_effects", {})).items()}),
        spatial_tethers=MappingProxyType({identity: TetherAnimation(
            MappingProxyType({facing: tuple(frames) for facing, frames in row["tether"]["frames_by_facing"].items()}),
            MappingProxyType({facing: ((points[0][0], points[0][1]), (points[1][0], points[1][1]))
                              for facing, points in row["tether"]["endpoints_by_facing"].items()}),
            row["tether"]["fps"],
        ) for identity, row in cast(dict, bindings.get("spatial_effects", {})).items() if "tether" in row}),
        spatial_residue_overlays=MappingProxyType({
            (identity, residue): MappingProxyType({pose: tuple(frames) for pose, frames in poses.items()})
            for identity, row in cast(dict, bindings.get("spatial_effects", {})).items()
            for residue, poses in row.get("residue_overlays", {}).items()
        }),
        residue_particles=MappingProxyType({identity: region_media_assets()[asset]
            for identity, asset in cast(dict, bindings.get("residue_particles", {})).items()}),
        residue_ground=MappingProxyType({identity: MappingProxyType(poses)
            for identity, poses in cast(dict, bindings.get("residue_ground", {})).items()}),
        residue_surfaces=MappingProxyType({identity: ResidueSurfaceStyle(**row)
            for identity, row in cast(dict, bindings.get("residue_surfaces", {})).items()}),
        residue_wall_faces=MappingProxyType({identity: face_profiles[profile]
            for identity, profile in wall_faces.get("assets", {}).items()}),
        liquid_surfaces=MappingProxyType({identity: LiquidSurfaceStyle(
            asset=region_media_assets()[row["asset_id"]],
            ellipse=ResidueEllipse.model_validate(row["ellipse"]), opacity=row["opacity"],
        ) for identity, row in cast(dict, bindings.get("liquid_surfaces", {})).items()}),
    )


def load_catalog() -> AssetCatalog:
    """Read bundled catalog values; decode each used raster in the presentation session."""
    return catalog_from_documents(
        json.loads((DATA_ROOT / "assets.json").read_text(encoding="utf-8")),
        json.loads((DATA_ROOT / "world_bindings.json").read_text(encoding="utf-8")),
    )


class SurfaceCache:
    """Canonical decoded Surfaces plus finite scaled/tinted derivatives."""

    def __init__(self, catalog: AssetCatalog) -> None:
        if pygame.display.get_surface() is None:
            raise RuntimeError("pygame display must be initialized before asset loading")
        self.catalog = catalog
        self.surface_residues = ResidueSurfaceCache()
        self._canonical: dict[str, pygame.Surface] = {}
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

    def canonical(self, asset_id: str) -> pygame.Surface:
        """Decode a requested world raster once in this presentation session."""
        cached = self._canonical.get(asset_id)
        if cached is not None:
            return cached
        spec = self.catalog.resources[asset_id]
        try:
            surface = pygame.image.load(spec.path).convert_alpha()
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
