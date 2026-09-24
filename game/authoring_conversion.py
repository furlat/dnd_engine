"""Convert supported Studio v6/local-v1 attachments at the authoring boundary.

Current records describe placements directly. Imported historical documents stay
unchanged; neither playback nor the raster adapter branches on their version.
"""

from math import isclose
from typing import Mapping

from game.animation_types import (AuthoredProjectileAsset, Point, SourceAnchor, StudioSpellDraft,
                                  ProjectileStorage, SpatialMediaBinding)


def explicit_attachments(draft: StudioSpellDraft,
                         assets: Mapping[str, AuthoredProjectileAsset]) -> StudioSpellDraft:
    projectile = draft.projectile
    if projectile is None:
        return draft
    sprite = projectile.sprite
    compensation = (0.0, 0.0)
    if sprite is not None:
        offsets = []
        for phase in (projectile.prepare, projectile.travel, projectile.impact):
            if not phase.enabled:
                continue
            asset = assets[phase.assetId or sprite.assetId]
            if asset.anchorsByFacing is not None:
                offsets.append((0.0, 0.0))
                continue
            pivot = sprite.anchor or asset.anchor
            scale = phase.scale if phase.scale is not None else projectile.scale
            offsets.append((sprite.offsetX + (.5 - pivot.x) * asset.frame.width * scale,
                            sprite.offsetY + (.5 - pivot.y) * asset.frame.height * scale))
        if offsets:
            compensation = offsets[0]
            if any(not all(isclose(a, b, abs_tol=1e-9) for a, b in zip(offset, compensation))
                   for offset in offsets):
                raise ValueError("legacy phase-dependent attachment compensation requires explicit authoring")
        if compensation != (0, 0):
            if compensation[0] or projectile.sourceSockets is not None:
                raise ValueError("legacy socket/horizontal canvas compensation requires explicit authoring")
            sprite = sprite.model_copy(update={"anchor": Point(x=.5, y=.5), "offsetX": 0, "offsetY": 0})

    def source(anchor: SourceAnchor) -> SourceAnchor:
        return anchor.model_copy(update={
            "basis": "tileCenter" if projectile.geometry.enabled else "rigRoot",
            "liftY": anchor.liftY + compensation[1],
        })

    target = projectile.targetAnchor
    target = target.model_copy(update={
        "basis": ("body" if target.basis == "body" else
                  "tileCenter" if projectile.geometry.enabled else "rigRoot"),
        "liftY": target.liftY + compensation[1],
        "axisPx": target.forwardPx if target.basis != "body" else 0,
        "forwardPx": target.forwardPx if target.basis == "body" else 0,
    })
    return draft.model_copy(update={"projectile": projectile.model_copy(update={
        "sourceAnchor": source(projectile.sourceAnchor), "targetAnchor": target,
        "sourceAnchorsByFacing": ({facing: source(anchor) for facing, anchor in projectile.sourceAnchorsByFacing.items()}
                                  if projectile.sourceAnchorsByFacing is not None else None),
        "sprite": sprite,
    })})


def explicit_composition(draft: StudioSpellDraft, storage: Mapping[str, ProjectileStorage]) -> StudioSpellDraft:
    """Local v1/v2 inferred composition from delivery storage; normalize once."""
    def mode(asset_id: str, phase: str) -> str:
        selected = storage.get(asset_id)
        return ("xyz_volume" if selected is not None and phase in selected.phases
                and selected.phases[phase].surfaceFrames is not None else "billboard")

    projectile = draft.projectile
    updates = {}
    if projectile is not None and projectile.sprite is not None:
        phases = {}
        for name, phase in (("prepare", projectile.prepare), ("travel", projectile.travel), ("impact", projectile.impact)):
            if mode(phase.assetId or projectile.sprite.assetId, phase.assetPhase) == "xyz_volume":
                phases[name] = phase.model_copy(update={"composition": "xyz_volume"})
        if phases:
            updates["projectile"] = projectile.model_copy(update=phases)
    if any(mode(track.assetId, track.assetPhase) == "xyz_volume" for track in draft.media):
        updates["media"] = tuple(track.model_copy(update={"composition": "xyz_volume"})
            if mode(track.assetId, track.assetPhase) == "xyz_volume" else track for track in draft.media)
    return draft.model_copy(update=updates) if updates else draft


def explicit_spatial_composition(binding: SpatialMediaBinding,
                                  storage: Mapping[str, ProjectileStorage]) -> SpatialMediaBinding:
    layers = []
    for layer in binding.layers:
        mode = layer.composition
        if mode == "legacy":
            selected = storage.get(layer.assetId)
            mode = ("xyz_volume" if selected is not None and binding.assetPhase in selected.phases
                and selected.phases[binding.assetPhase].surfaceFrames is not None else "billboard")
        layers.append(layer.model_copy(update={"composition": mode}))
    return binding.model_copy(update={"layers": tuple(layers)})


def validate_composition(draft: StudioSpellDraft, storage: Mapping[str, ProjectileStorage]) -> None:
    """Check the selected in-memory contract; never inspect or validate media files."""
    uses = [(track.assetId, track.assetPhase, track.composition) for track in draft.media]
    projectile = draft.projectile
    if projectile is not None and projectile.sprite is not None:
        uses.extend((phase.assetId or projectile.sprite.assetId, phase.assetPhase, phase.composition)
                    for phase in (projectile.prepare, projectile.travel, projectile.impact) if phase.enabled)
        if projectile.prepare.composition == "xyz_volume" or projectile.travel.composition == "xyz_volume":
            raise ValueError("XYZ projectile composition requires a registered impact, not an actor-local flight")
    for asset, phase, mode in uses:
        selected = storage.get(asset)
        if mode == "xyz_volume" and (selected is None or phase not in selected.phases
                                    or selected.phases[phase].surfaceFrames is None):
            raise ValueError(f"XYZ composition requires a paired surface source: {asset}/{phase}")
    for track in draft.media:
        if track.composition == "xyz_volume" and (track.orientation != "authored" or track.scaleWithActor):
            raise ValueError(f"XYZ cast media requires authored world orientation and scale: {track.id}")
