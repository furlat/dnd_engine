"""Sample an optional witnessed intro, then a shared sustained media window."""

from math import floor

from game.animation_types import AnimationData, SpatialMediaBinding, SpatialMediaLayer


def maintained_media_alpha(binding: SpatialMediaBinding, layer: SpatialMediaLayer,
                           now_ms: float, removed_ms: float | None) -> float:
    """An authored uniform clear fades the continuing phase, never restarts it."""
    if removed_ms is None or now_ms < removed_ms or layer.removalAssetId is not None:
        return 1.
    if not binding.removalFadeMs:
        return 0.
    progress = min(1., (now_ms - removed_ms) / binding.removalFadeMs)
    if binding.removalEasing == "smoothstep":
        progress = progress * progress * (3 - 2 * progress)
    return 1 - progress


def maintained_media_frame(data: AnimationData, binding: SpatialMediaBinding,
                           layer: SpatialMediaLayer, now_ms: float,
                           applied_ms: float | None, removed_ms: float | None = None) -> tuple[str, int] | None:
    if removed_ms is not None and now_ms >= removed_ms + layer.delayMs and layer.removalAssetId is not None:
        asset = data.projectile_assets[layer.removalAssetId]
        phase = {"cast": asset.phases.cast, "travel": asset.phases.travel,
                 "impact": asset.phases.impact}[binding.assetPhase]
        assert phase is not None
        frame = floor((now_ms - removed_ms - layer.delayMs) * (phase.fps or asset.fps) / 1000)
        return (layer.removalAssetId, frame) if frame < phase.frames else None
    if applied_ms is not None:
        applied_ms += layer.delayMs
    if applied_ms is not None and now_ms < applied_ms:
        return None
    age = now_ms - applied_ms if applied_ms is not None else now_ms
    duration = 0.
    if layer.applicationAssetId is not None:
        asset = data.projectile_assets[layer.applicationAssetId]
        phase = {"cast": asset.phases.cast, "travel": asset.phases.travel,
                 "impact": asset.phases.impact}[binding.assetPhase]
        assert phase is not None
        fps = phase.fps or asset.fps
        duration = phase.frames * 1000 / fps
        if applied_ms is not None and age < duration:
            return layer.applicationAssetId, floor(age * fps / 1000)
    sustained_age = age - duration if applied_ms is not None else age
    return layer.assetId, binding.holdStartFrame + floor(sustained_age * binding.fps / 1000) % binding.holdFrames


def maintained_removal_duration(data: AnimationData, binding: SpatialMediaBinding) -> float:
    """Retain only the authored clear media or existing fallback fade tail."""
    duration = binding.removalFadeMs
    for layer in binding.layers:
        if layer.removalAssetId is None:
            continue
        asset = data.projectile_assets[layer.removalAssetId]
        phase = {"cast": asset.phases.cast, "travel": asset.phases.travel,
                 "impact": asset.phases.impact}[binding.assetPhase]
        assert phase is not None
        duration = max(duration, layer.delayMs + phase.frames * 1000 / (phase.fps or asset.fps))
    return duration
