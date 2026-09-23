"""Absolute sampling of NeuroStudio's existing action-media strip tracks."""

from dataclasses import dataclass
from uuid import UUID

from dnd.types.residues import BodyReleaseResult
from dnd.types.world import OccupancyLayer
from game.animation import ActorContact
from game.animation_types import ActionMediaAsset, AnimationData, MovementMediaTrack, ParticleMediaAsset, BloodResponse
from game.residue_media import particle_schedule, surface_start_time


@dataclass(frozen=True, slots=True)
class ActionStripCue:
    event_uuid: UUID
    contact: ActorContact
    track: MovementMediaTrack
    asset: ActionMediaAsset | ParticleMediaAsset
    start_ms: float
    end_ms: float
    data: AnimationData
    direction: tuple[float, float] = (1.0, 0.0)
    release: BodyReleaseResult | None = None
    particle_colors: tuple[int, int] | None = None
    response: BloodResponse | None = None


@dataclass(frozen=True, slots=True)
class ActionStripSample:
    cue: ActionStripCue
    frame: int
    elapsed_ms: float = 0


def bind_action_strips(event_uuid: UUID, contact: ActorContact,
                       tracks: tuple[MovementMediaTrack, ...], data: AnimationData,
                       *, start_ms: float, direction: tuple[float, float] = (1.0, 0.0),
                       release: BodyReleaseResult | None = None,
                       spell_color: int | None = None) -> tuple[ActionStripCue, ...]:
    """Resolve selected media once, at the causal owner's supplied anchor."""
    cues = []
    for track in tracks:
        if track.loop or track.tint2 is not None or track.attachment != "body":
            raise NotImplementedError("One-shot body strips do not support ground attachment, loops or two-color mapping")
        asset = data.action_media_assets[track.assetId]
        if (isinstance(asset, ParticleMediaAsset) and asset.region is not None
                and (release is None or release.pattern is None or release.occupancy_layer is OccupancyLayer.AIR) and asset.legacyAssetId is not None):
            asset = data.action_media_assets[asset.legacyAssetId]
        if isinstance(asset, ParticleMediaAsset) and (
                track.reversed or track.tint != 0xFFFFFF or track.offsetX or track.offsetY):
            raise NotImplementedError("Particle media uses forward motion, its authored palette and world origin")
        start = start_ms + track.startFrame * 1000 / data.rig.ANIM_FPS
        response = (data.blood_responses.get(release.primary_damage_type.value)
            if release is not None and release.release_id == "body.blood" and release.primary_damage_type is not None else None)
        duration_ms = asset.frames * 1000 / track.fps
        if response is not None and isinstance(asset, ParticleMediaAsset) and asset.region is not None and release is not None:
            family = asset.region.families[release.pattern or "blunt"]
            schedule = tuple((p, particle_schedule(p, family, response, copy))
                for template in asset.region.templates for p in template.particles
                for copy in range(asset.region.criticalCopies if release.critical_hit else 1))
            last = max((max(delay + flight + melt,
                delay + flight * response.vapor.startFraction + (response.vapor.count - 1) * response.vapor.interval
                    + response.vapor.life if response.vapor is not None and p.id % response.vapor.every == 0 else 0)
                for p, (delay, flight, melt) in schedule), default=0)
            if response.surfaceSeconds:
                last = max(last, surface_start_time(asset.assetId, release.pattern or "blunt", response)
                           + response.surfaceSeconds)
            duration_ms = max(duration_ms, last * 1000 * asset.defaultFps / track.fps)
        colors = None
        base_colors = response.colors if response is not None else asset.colors if isinstance(asset, ParticleMediaAsset) else None
        if (response is None and base_colors is not None and release is not None
                and release.release_id == "body.blood" and release.secondary_damage_type is not None):
            rider = data.blood_responses.get(release.secondary_damage_type.value)
            if rider is not None:
                # One light rider accent preserves the physical primary's approved motion.
                accent = sum(round((base_colors[1] >> shift & 255) * .94
                    + (rider.colors[1] >> shift & 255) * .06) << shift for shift in (16, 8, 0))
                colors = base_colors = (base_colors[0], accent)
        if isinstance(asset, ParticleMediaAsset) and spell_color is not None and track.spellTintStrength:
            def tinted(color: int) -> int:
                return sum(round((color >> shift & 255) * (1 - track.spellTintStrength)
                    + (spell_color >> shift & 255) * track.spellTintStrength) << shift for shift in (16, 8, 0))
            assert base_colors is not None
            colors = (tinted(base_colors[0]), tinted(base_colors[1]))
        cues.append(ActionStripCue(event_uuid, contact, track, asset, start,
                                   start + duration_ms, data, direction, release, colors, response))
    return tuple(cues)


def sample_action_strip(cue: ActionStripCue, elapsed_ms: float) -> ActionStripSample | None:
    """One play through the authored frames; seeking has no side effects."""
    if not cue.start_ms <= elapsed_ms < cue.end_ms:
        return None
    frame = min(cue.asset.frames - 1, int((elapsed_ms - cue.start_ms) * cue.track.fps / 1000))
    return ActionStripSample(cue, cue.asset.frames - 1 - frame if cue.track.reversed else frame,
                             elapsed_ms - cue.start_ms)
