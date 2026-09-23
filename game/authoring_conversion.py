"""Convert supported Studio v6/local-v1 attachments at the authoring boundary.

Current records describe placements directly. Imported historical documents stay
unchanged; neither playback nor the raster adapter branches on their version.
"""

from math import isclose
from typing import Mapping

from game.animation_types import AuthoredProjectileAsset, Point, SourceAnchor, StudioSpellDraft


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
