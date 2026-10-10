"""Finite registered media at a disclosed, immutable world contact."""

from dataclasses import dataclass
from uuid import UUID

from game.animation import media_track_duration
from game.animation_types import AnimationData, Facing8, StudioMediaTrack


def stationary_media_limitations(track: StudioMediaTrack) -> tuple[str, ...]:
    """Check transforms still owned by this sampler, after attachment resolution.

    The producer supplies the immutable contact and height, including body
    attachment heights for condition reactions. Attachment is no longer a
    sampling decision here.
    """
    unsupported = []
    if track.composition != "billboard":
        unsupported.append("world contact media supports billboard composition")
    if track.scaleWithActor or track.orientation != "authored":
        unsupported.append("world contact media has a fixed authored size and orientation")
    if any(value is not None for value in (track.worldOffsetsByFacing,
            track.bodyOffsetsByFacing)):
        unsupported.append("world contact media uses its received contact without socket offsets")
    return tuple(unsupported)


@dataclass(frozen=True, slots=True)
class StationaryMediaCue:
    event_uuid: UUID
    track: StudioMediaTrack
    position: tuple[float, float]
    elevation_steps: float
    facing: Facing8
    start_ms: float
    data: AnimationData
    depth_offset_cells: float = 0
    native_pixels: bool = False
    fade_out_ms: tuple[float, float] | None = None
    actor_uuid: str | None = None

    def __post_init__(self) -> None:
        if limitations := stationary_media_limitations(self.track):
            raise ValueError(f"{self.track.id}: {'; '.join(limitations)}")

    @property
    def end_ms(self) -> float:
        duration = media_track_duration(self.data, self.track)
        return self.start_ms + (min(duration, self.fade_out_ms[1]) if self.fade_out_ms else duration)
