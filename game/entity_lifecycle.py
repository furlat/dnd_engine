"""Finite body presence and registered media from witnessed lifecycle facts."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from dnd.types.summoning import SummonDepartureCause, SummonManifestation
from game.animation import ActorContact, body_rig, sample_idle_body
from game.animation_data import resolve_player_layers
from game.animation_types import AnimationData, EntityLifecyclePhase
from game.body_pose_types import ActorPose, SceneActor
from game.condition_animation import condition_body_pose, resolve_condition_appearance
from game.player_facts import FactionFact, PlayerActor, PlayerFact, SpatialFact
from game.stationary_media import StationaryMediaCue
from game.timing_evidence import TimingEvidence, TimingOperand, TimingReference


@dataclass(frozen=True, slots=True)
class EntityLifecycleCue:
    event_uuid: UUID
    phase: Literal["arrival", "departure", "bond"]
    actor: SceneActor
    start_ms: float
    recipe: EntityLifecyclePhase
    data: AnimationData
    timing_evidence: tuple[TimingEvidence, ...] = ()

    @property
    def body_end_ms(self) -> float:
        return self.start_ms + (self.recipe.bodyFadeMs[1] if self.recipe.bodyFadeMs else 0.)


def lifecycle_phase(fact: PlayerFact | None) -> Literal["arrival", "departure", "bond"] | None:
    if isinstance(fact, SpatialFact):
        if fact.creation is not None:
            return "arrival"
        if fact.terminal_cause in (SummonDepartureCause.EXPIRED, SummonDepartureCause.DISMISSED,
                                  SummonDepartureCause.DEFEATED, SummonDepartureCause.SUSTAIN_LOST):
            return "departure"
    if isinstance(fact, FactionFact) and fact.control_lost:
        return "bond"
    return None


def bind_entity_lifecycle(event_uuid: UUID, phase: Literal["arrival", "departure", "bond"],
                          actor: PlayerActor, contact: ActorContact, data: AnimationData,
                          start_ms: float) -> tuple[EntityLifecycleCue, tuple[StationaryMediaCue, ...]] | None:
    recipe = data.entity_lifecycle_media.get(phase)
    if recipe is None or actor.manifestation is None:
        return None
    if phase == "bond" and actor.manifestation is not SummonManifestation.FEY_SPIRIT:
        return None
    tracks = recipe.tracksByManifestation.get(actor.manifestation.value, ())
    if not tracks:
        return None
    appearance = resolve_condition_appearance(actor.conditions, data.condition_recipes, data.condition_media)
    scene_actor = SceneActor(contact, resolve_player_layers(data, actor, rig_id=contact.rig_id), appearance)
    body_duration = recipe.bodyFadeMs[1] if recipe.bodyFadeMs else 0.
    evidence = (TimingEvidence(0, TimingReference('event', event_uuid, 'body_end'), 'body_end', 'offset',
        (TimingOperand(TimingReference('event', event_uuid, 'start'), start_ms, offset_ms=body_duration,
            authored_field=f'entity_lifecycle.{phase}.bodyFadeMs[1]' if recipe.bodyFadeMs else None),), start_ms + body_duration),)
    cue = EntityLifecycleCue(event_uuid, phase, scene_actor, start_ms, recipe, data, evidence)
    scale = body_rig(data, contact).lifecycle_scale
    media = tuple(StationaryMediaCue(event_uuid, track.model_copy(update={"scale": track.scale * scale}),
        contact.grid, contact.elevation_steps, contact.facing, start_ms + track.startOffsetMs,
        data, native_pixels=True) for track in tracks)
    return cue, media


def lifecycle_body_progress(cue: EntityLifecycleCue, elapsed_ms: float) -> float:
    """Body/shadow coverage on the original absolute clock; no mutable fade state."""
    fade = cue.recipe.bodyFadeMs
    if fade is None:
        return 1.
    begin, end = fade
    if elapsed_ms >= cue.body_end_ms:
        return 1. if cue.phase == "arrival" else 0.
    progress = min(1., max(0., (elapsed_ms - cue.start_ms - begin) / (end - begin)))
    return progress if cue.phase == "arrival" else 1. - progress


def retiring_pose(cue: EntityLifecycleCue, elapsed_ms: float) -> ActorPose | None:
    if cue.phase != "departure" or not cue.start_ms <= elapsed_ms < cue.body_end_ms:
        return None
    body = condition_body_pose(cue.data, sample_idle_body(cue.data, cue.actor.contact, 0.),
                               cue.actor.contact, cue.actor.condition)
    return ActorPose(cue.actor, body, lifecycle_body_progress(cue, elapsed_ms), cue.actor.condition)
