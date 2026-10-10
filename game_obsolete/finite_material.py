"""Finite authored materials sampled on the existing causal head clock."""

from dataclasses import dataclass
from uuid import UUID

from game.animation_types import BodyMaterialSample, StudioBodyMaterialTrack


@dataclass(frozen=True, slots=True)
class BodyMaterialCue:
    event_uuid: UUID
    actor_uuid: str
    start_ms: float
    track: StudioBodyMaterialTrack

    @property
    def end_ms(self) -> float:
        return self.start_ms + self.track.startOffsetMs + self.track.points[-1].elapsedMs


def sample_material_track(track: StudioBodyMaterialTrack, elapsed_ms: float) -> BodyMaterialSample | None:
    age = elapsed_ms - track.startOffsetMs
    if not 0 <= age < track.points[-1].elapsedMs:
        return None
    first, last = next((a, b) for a, b in zip(track.points, track.points[1:]) if a.elapsedMs <= age < b.elapsedMs)
    t = (age-first.elapsedMs)/(last.elapsedMs-first.elapsedMs)
    t = t*t*(3-2*t)
    return BodyMaterialSample(track.material, first.strength+(last.strength-first.strength)*t,
        first.pulse+(last.pulse-first.pulse)*t, age)
