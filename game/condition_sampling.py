"""Pure atlas samples for authored condition tracks, independent of the drawer."""

from dataclasses import dataclass, replace
from math import floor

from game.animation_types import AnimationData
from game.condition_media import ResolvedConditionLayer


@dataclass(frozen=True, slots=True)
class ConditionMediaSample:
    asset_id: str
    frame: int
    alpha: float
    removal_mask: tuple[str, int] | None = None


def _loop_samples(identity: str, age: float, fps: float, frames: int, opacity: float,
                  crossfade_ms: float, mask: tuple[str, int] | None) -> tuple[ConditionMediaSample, ...]:
    duration = frames * 1000 / fps
    if crossfade_ms >= duration:
        raise ValueError("condition loop crossfade must be shorter than its loop")
    clock = max(0., age)
    local = (clock % duration if not crossfade_ms or clock < duration else
        crossfade_ms + (clock - duration) % (duration - crossfade_ms))
    frame = floor(local * fps / 1000)
    if not crossfade_ms or local < duration - crossfade_ms:
        return (ConditionMediaSample(identity, frame, opacity, mask),)
    overlap = local - (duration - crossfade_ms)
    alpha = overlap / crossfade_ms
    return (ConditionMediaSample(identity, frame, opacity * (1 - alpha), mask),
            ConditionMediaSample(identity, floor(overlap * fps / 1000), opacity * alpha, mask))


def sample_condition_media(data: AnimationData, resolved: ResolvedConditionLayer) -> tuple[ConditionMediaSample, ...]:
    layer, media = resolved.layer, resolved.media
    age = resolved.age_ms - (layer.startOffsetMs if resolved.application else 0)
    if age < 0 or media.asset_id is None:
        return ()
    if resolved.removal_age_ms is not None and media.removal_asset_id is not None:
        release = data.projectile_assets[media.removal_asset_id]
        phase = release.phases.impact
        assert phase is not None
        if phase.loop:
            raise ValueError("color release requires a finite bank")
        release_age = resolved.removal_age_ms
        duration = phase.frames * 1000 / (phase.fps or release.fps)
        if media.removal_crossfade_ms > duration:
            raise ValueError("color release crossfade exceeds its finite duration")
        if release_age < 0 or release_age >= duration:
            return ()
        blend = min(1., release_age / media.removal_crossfade_ms) if media.removal_crossfade_ms else 1.
        # The lifetime supplies the age at removal, so an interrupted binding
        # never finishes forming during the outgoing side of this transition.
        outgoing = sample_condition_media(data, replace(resolved, removal_age_ms=None)) if blend < 1 else ()
        return (*(replace(sample, alpha=sample.alpha * (1 - blend)) for sample in outgoing if sample.alpha),
                *((ConditionMediaSample(media.removal_asset_id,
                    floor(release_age * (phase.fps or release.fps) / 1000), resolved.alpha * blend),)
                    if blend else ()))
    age += layer.phaseOffsetMs if resolved.application else 0
    opacity = resolved.alpha
    if resolved.application and layer.fadeInMs:
        fade_age = age if resolved.fade_in_age_ms is None else min(age, resolved.fade_in_age_ms)
        opacity *= max(0., min(1., fade_age / layer.fadeInMs))
    mask = None
    if resolved.removal_age_ms is not None and media.removal_mask_asset_id is not None:
        asset = data.projectile_assets[media.removal_mask_asset_id]
        phase = asset.phases.impact
        assert phase is not None
        frame = floor(resolved.removal_age_ms * (phase.fps or asset.fps) / 1000)
        if frame >= phase.frames:
            return ()
        mask = media.removal_mask_asset_id, max(0, frame)
    if media.application_mode == "sequence" and media.application_asset_id is not None and not resolved.finite:
        identity = media.asset_id
        if resolved.application:
            application = data.projectile_assets[media.application_asset_id]
            phase = application.phases.impact
            assert phase is not None
            duration = phase.frames * 1000 / (phase.fps or application.fps)
            if age < duration:
                identity = media.application_asset_id
            else:
                age -= duration
        asset = data.projectile_assets[identity]
        phase = asset.phases.impact
        assert phase is not None
        frame = floor(age * (phase.fps or asset.fps) / 1000)
        if identity == media.asset_id:
            return _loop_samples(identity, age, phase.fps or asset.fps, phase.frames,
                opacity, media.loop_crossfade_ms, mask)
        return (ConditionMediaSample(identity, frame, opacity, mask),)
    start, end = media.application_fade_ms
    blend = max(0., min(1., (age - start) / (end - start))) if end > start else 1.
    if not resolved.application or media.application_asset_id is None or resolved.finite:
        blend = 1.
    result = []
    for identity, alpha, loop in ((media.application_asset_id, 1 - blend, False),
                                   (media.asset_id, blend, not resolved.finite)):
        if identity is None or alpha * opacity <= 0:
            continue
        phase = data.projectile_assets[identity].phases.impact
        assert phase is not None
        local_age = age - media.sustain_start_ms if loop and resolved.application else age
        frame = floor(max(0., local_age) * layer.fps / 1000)
        if loop:
            result.extend(_loop_samples(identity, local_age, layer.fps, phase.frames,
                alpha * opacity, media.loop_crossfade_ms, mask))
            continue
        elif frame >= phase.frames:
            continue
        result.append(ConditionMediaSample(identity, frame, alpha * opacity, mask))
    return tuple(result)
