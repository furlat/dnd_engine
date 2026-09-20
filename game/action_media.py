"""Absolute sampling of NeuroStudio's existing action-media strip tracks."""

from dataclasses import dataclass
from uuid import UUID

from dnd.types.residues import BodyReleaseResult
from dnd.types.world import OccupancyLayer
from game.animation import ActorContact
from game.animation_types import ActionMediaAsset, AnimationData, MovementMediaTrack, ParticleMediaAsset


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


@dataclass(frozen=True, slots=True)
class ActionStripSample:
    cue: ActionStripCue
    frame: int
    elapsed_ms: float = 0


def bind_action_strips(event_uuid: UUID, contact: ActorContact,
                       tracks: tuple[MovementMediaTrack, ...], data: AnimationData,
                       *, start_ms: float, direction: tuple[float, float] = (1.0, 0.0),
                       release: BodyReleaseResult | None = None) -> tuple[ActionStripCue, ...]:
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
        cues.append(ActionStripCue(event_uuid, contact, track, asset, start,
                                   start + asset.frames * 1000 / track.fps, data, direction, release))
    return tuple(cues)


def sample_action_strip(cue: ActionStripCue, elapsed_ms: float) -> ActionStripSample | None:
    """One play through the authored frames; seeking has no side effects."""
    if not cue.start_ms <= elapsed_ms < cue.end_ms:
        return None
    frame = min(cue.asset.frames - 1, int((elapsed_ms - cue.start_ms) * cue.track.fps / 1000))
    return ActionStripSample(cue, cue.asset.frames - 1 - frame if cue.track.reversed else frame,
                             elapsed_ms - cue.start_ms)
