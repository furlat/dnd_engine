"""A committed, independently disclosed crossing on the historical clock."""

from dataclasses import dataclass, replace
from uuid import UUID

from dnd.core.events import MovementTrajectory
from dnd.types.world import MovementMode
from game.animation import (ActorContact, BodySample, body_context, resolve_body_context,
                            sample_context_body, sample_idle_body)
from game.animation_types import AnimationData, MovementBodyQualifier
from game.portal_art import PortalArt, DoorwayArt


@dataclass(frozen=True, slots=True)
class PortalTransferCue:
    event_uuid: UUID
    portal_uuid: UUID | None
    actor_uuid: str
    departure: ActorContact | None
    arrival: ActorContact | None
    art: PortalArt | DoorwayArt
    start_ms: float
    fall_start_ms: float
    disappear_ms: float
    exit_open_ms: float
    arrival_ms: float
    settled_ms: float
    exit_close_ms: float
    complete_ms: float
    data: AnimationData


def bind_portal_transfer(event_uuid: UUID, portal_uuid: UUID | None, actor_uuid: str,
                         departure: ActorContact | None, arrival: ActorContact | None,
                         art: PortalArt | DoorwayArt, start_ms: float, opening_ms: float | None, data: AnimationData,
                         ) -> PortalTransferCue:
    if isinstance(art, DoorwayArt):
        begin = start_ms + art.walkingDelayMs
        vanish = begin + art.strideMs
        arrive = vanish + art.transitMs
        settled = arrive + art.strideMs
        close = settled + 80
        return PortalTransferCue(event_uuid, portal_uuid, actor_uuid, departure, arrival, art,
            start_ms, begin, vanish, start_ms, arrive, settled, close, close+art.closingMs, data)
    fall = max(start_ms, opening_ms + art.fall_delay_ms) if opening_ms is not None else start_ms
    disappear = fall + art.fall_ms if departure is not None else start_ms
    exit_open = max(start_ms, disappear - art.exit.opening_frames * 1000 / art.exit.fps)
    arrival_ms = max(disappear + (art.transit_ms if departure is not None else 0),
                     exit_open + art.exit.opening_frames * 1000 / art.exit.fps)
    settled = arrival_ms + art.emerge_ms
    close = settled + art.exit_hold_ms
    end = close + art.exit.closing_frames * 1000 / art.exit.fps if arrival is not None else disappear
    return PortalTransferCue(event_uuid, portal_uuid, actor_uuid, departure, arrival, art,
        start_ms, fall, disappear, exit_open, arrival_ms, settled, close, end, data)


def portal_departure_contact(cue: PortalTransferCue, elapsed_ms: float) -> ActorContact | None:
    if cue.departure is None or not cue.start_ms <= elapsed_ms < cue.disappear_ms:
        return None
    if isinstance(cue.art, DoorwayArt):
        fraction = max(0., (elapsed_ms-cue.fall_start_ms)/cue.art.strideMs)
        return replace(cue.departure, facing='N',
            grid=(cue.departure.grid[0],cue.departure.grid[1]-cue.art.strideCells*fraction))
    fraction = max(0, (elapsed_ms - cue.fall_start_ms) / cue.art.fall_ms)
    return replace(cue.departure,
        body_lift_px=cue.departure.body_lift_px - cue.art.fall_depth_px * fraction * fraction)


def portal_arrival_contact(cue: PortalTransferCue, elapsed_ms: float) -> ActorContact | None:
    if cue.arrival is None or not cue.arrival_ms <= elapsed_ms < cue.settled_ms:
        return None
    if isinstance(cue.art, DoorwayArt):
        remaining = (cue.settled_ms-elapsed_ms)/cue.art.strideMs
        return replace(cue.arrival, facing='S',
            grid=(cue.arrival.grid[0],cue.arrival.grid[1]-cue.art.strideCells*remaining))
    remaining = (cue.settled_ms - elapsed_ms) / cue.art.emerge_ms
    return replace(cue.arrival,
        body_lift_px=cue.arrival.body_lift_px - cue.art.fall_depth_px * remaining * remaining)


def portal_actor_hidden(cue: PortalTransferCue, elapsed_ms: float) -> bool:
    return cue.start_ms <= elapsed_ms and (cue.departure is None or elapsed_ms >= cue.disappear_ms) and (
        cue.arrival is None or elapsed_ms < cue.arrival_ms)


def portal_body(cue: PortalTransferCue, elapsed_ms: float) -> BodySample | None:
    if not isinstance(cue.art, DoorwayArt):
        return None
    contact = portal_departure_contact(cue,elapsed_ms) or portal_arrival_contact(cue,elapsed_ms)
    if contact is None:
        return None
    walking = elapsed_ms >= cue.fall_start_ms
    if not walking:
        return sample_idle_body(cue.data,contact,elapsed_ms)
    context = resolve_body_context(cue.data,contact,'movement',
        MovementBodyQualifier(movement_mode=MovementMode.WALKING,trajectory=MovementTrajectory.PATH,
                              connector_presentation_key=None),
        body_context(cue.data.movement_context.walkClip,loop=True))
    return sample_context_body(cue.data,contact,context,max(0.,elapsed_ms-cue.fall_start_ms))
