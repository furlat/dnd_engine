"""A finite hop between retained contacts, driven by a real saved retreat."""

from dataclasses import dataclass, replace
from uuid import UUID

from game.animation import ActorContact, BodySample, body_clip
from game.animation_types import AnimationData, SaveHop
from game.player_facts import ForcedMovementFact, MechanismActivationFact, PlayerNode, SavingThrowFact


@dataclass(frozen=True, slots=True)
class BodyHopCue:
    event_uuid: UUID
    movement_event_uuid: UUID
    contact: ActorContact
    landing: ActorContact
    body_clip: str
    frames: int
    height_px: float
    start_ms: float
    end_ms: float
    data: AnimationData


def bind_save_hop(activation: PlayerNode, children: tuple[PlayerNode, ...],
                  recipe: SaveHop, contact: ActorContact, contact_ms: float,
                  data: AnimationData, *, landing_elevation_steps: float) -> BodyHopCue | None:
    """Bind the exact successful avoidance; damage absence is not evidence."""
    mechanism = activation.fact
    if not isinstance(mechanism, MechanismActivationFact) or not mechanism.committed:
        return None
    save = next((node for node in children if node.parent_lineage == activation.lineage_uuid
        and not node.canceled and isinstance(node.fact, SavingThrowFact)
        and node.fact.succeeded and node.fact.effect_id == recipe.effect_id
        and str(node.fact.target_entity_uuid) == contact.actor_uuid), None)
    if save is None:
        return None
    movement = next((node for node in children if node.parent_lineage == activation.lineage_uuid
        and not node.canceled and isinstance(node.fact, ForcedMovementFact)
        and str(node.fact.target_entity_uuid) == contact.actor_uuid
        and node.fact.actual_distance > 0 and node.fact.start_position != node.fact.end_position), None)
    if movement is None or not isinstance(movement.fact, ForcedMovementFact):
        return None
    landing = replace(contact, grid=movement.fact.end_position,
        elevation_steps=landing_elevation_steps, body_lift_px=0)
    metadata = body_clip(data, contact, recipe.body_clip)
    return BodyHopCue(save.uuid, movement.uuid, contact, landing, recipe.body_clip, metadata.frames,
        recipe.height_px,
        contact_ms - recipe.duration_ms / 2, contact_ms + recipe.duration_ms / 2, data)


def sample_body_hop(cue: BodyHopCue, elapsed_ms: float) -> tuple[BodySample, ActorContact] | None:
    """One visual cycle between native contacts, with no simulated displacement."""
    if elapsed_ms < cue.start_ms or elapsed_ms > cue.end_ms:
        return None
    progress = (elapsed_ms - cue.start_ms) / (cue.end_ms - cue.start_ms)
    if progress == 1:
        return BodySample(cue.landing.actor_uuid, "Idle", 0, cue.landing.facing), cue.landing
    frame = min(cue.frames - 1, int(progress * cue.frames))
    arc = 4 * progress * (1 - progress)
    contact = replace(cue.contact,
        grid=(cue.contact.grid[0]+(cue.landing.grid[0]-cue.contact.grid[0])*progress,
              cue.contact.grid[1]+(cue.landing.grid[1]-cue.contact.grid[1])*progress),
        elevation_steps=cue.contact.elevation_steps+(cue.landing.elevation_steps-cue.contact.elevation_steps)*progress,
        body_lift_px=cue.contact.body_lift_px*(1-progress) + cue.height_px*arc)
    return BodySample(contact.actor_uuid, cue.body_clip, frame, contact.facing), contact
