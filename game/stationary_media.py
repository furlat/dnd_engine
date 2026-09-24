"""Finite registered media at a disclosed, immutable world contact."""

from dataclasses import dataclass
from uuid import UUID

from game.animation import media_track_duration, media_track_frame, view_facing
from game.animation_types import AnimationData, Facing8, StudioMediaTrack
from game.draw_commands import DrawCommand
from game.projection import Camera, TILE_WIDTH, painter_key, project_screen, rotate_position, inverse_rotate_position
from game.registered_media import registered_media_blits


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
            track.bodyOffsetsByFacing, track.emissionPointByFacing)):
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

    def __post_init__(self) -> None:
        if limitations := stationary_media_limitations(self.track):
            raise ValueError(f"{self.track.id}: {'; '.join(limitations)}")

    @property
    def end_ms(self) -> float:
        return self.start_ms + media_track_duration(self.data, self.track)


def stationary_media_draw_commands(cues: tuple[StationaryMediaCue, ...], elapsed_ms: float,
                                    camera: Camera) -> tuple[DrawCommand, ...]:
    commands = []
    for cue in cues:
        if not cue.start_ms <= elapsed_ms < cue.end_ms:
            continue
        data, track = cue.data, cue.track
        facing = view_facing(track.viewFacing or cue.facing, camera.quadrant, data)
        frame = media_track_frame(data, track, elapsed_ms-cue.start_ms, facing)
        anchor = project_screen(cue.position, camera, elevation_steps=cue.elevation_steps)
        contact = rotate_position(cue.position, camera.quadrant)
        depth_position = inverse_rotate_position((contact[0] + cue.depth_offset_cells,
                                                  contact[1] + cue.depth_offset_cells), camera.quadrant)
        key = painter_key(depth_position, elevation_steps=cue.elevation_steps, quadrant=camera.quadrant,
            role="ground_effect" if track.depth == "ground" else "actor",
            identity=(str(cue.event_uuid), track.id))
        if track.depth in ("behind_body", "front_body"):
            key = (*key[:3], key[3]+(-1 if track.depth == "behind_body" else 1), key[4])
        for image, destination, blend in registered_media_blits(data, track.assetId, track.assetPhase,
                frame, facing, scale=track.scale*TILE_WIDTH/data.rig.TILE_W*camera.zoom,
                anchor=anchor, rows={}, alpha=track.alpha):
            commands.append(DrawCommand(key, image, destination, blend,
                (str(cue.event_uuid), cue.position, track.assetId, "current", None, "authored",
                 "stationary_media", cue.elevation_steps, track.id, frame)))
    return tuple(commands)
