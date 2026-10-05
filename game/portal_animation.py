"""A committed, independently disclosed crossing on the historical clock."""

from dataclasses import dataclass, replace
from uuid import UUID

from dnd.types.event_facts import MovementTrajectory
from dnd.types.world import MovementMode
from game.animation import (ActorContact, BodySample, body_context, resolve_body_context,
                            sample_context_body, sample_idle_body)
from game.animation_types import AnimationData, MovementBodyQualifier
from game.portal_art import PortalArt, DoorwayArt
from game.timing_evidence import TimingEvidence, TimingOperand, TimingReference, TimingMeasurement, record_timing


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
    timing_evidence: tuple[TimingEvidence, ...] = ()


def bind_portal_transfer(event_uuid: UUID, portal_uuid: UUID | None, actor_uuid: str,
                         departure: ActorContact | None, arrival: ActorContact | None,
                         art: PortalArt | DoorwayArt, start_ms: float, opening_ms: float | None, data: AnimationData,
                         ) -> PortalTransferCue:
    evidence: list[TimingEvidence] = []
    start = TimingOperand(TimingReference('event', event_uuid, 'start'), start_ms)
    if isinstance(art, DoorwayArt):
        begin = start_ms + art.walkingDelayMs
        vanish = begin + art.strideMs
        arrive = vanish + art.transitMs
        settled = arrive + art.strideMs
        close = settled + 80
        began = record_timing(evidence, TimingReference('event', event_uuid, 'launch'), 'portal_fall',
            (replace(start, offset_ms=art.walkingDelayMs, authored_field='portal.walkingDelayMs'),), begin)
        vanished = record_timing(evidence, TimingReference('event', event_uuid, 'disappear'), 'portal_fall',
            (replace(began, offset_ms=art.strideMs, authored_field='portal.strideMs'),), vanish)
        arrived = record_timing(evidence, TimingReference('event', event_uuid, 'arrival'), 'portal_arrival',
            (replace(vanished, offset_ms=art.transitMs, authored_field='portal.transitMs'),), arrive)
        settled_at = record_timing(evidence, TimingReference('event', event_uuid, 'settled'), 'portal_settled',
            (replace(arrived, offset_ms=art.strideMs, authored_field='portal.strideMs'),), settled)
        record_timing(evidence, TimingReference('event', event_uuid, 'complete'), 'portal_settled',
            (replace(settled_at, offset_ms=80+art.closingMs, authored_field='portal.closingMs',
                measurements=(TimingMeasurement('portal.close_lead_ms', 80),)),), close+art.closingMs)
        return PortalTransferCue(event_uuid, portal_uuid, actor_uuid, departure, arrival, art,
            start_ms, begin, vanish, start_ms, arrive, settled, close, close+art.closingMs, data, tuple(evidence))
    fall = max(start_ms, opening_ms + art.fall_delay_ms) if opening_ms is not None else start_ms
    disappear = fall + art.fall_ms if departure is not None else start_ms
    exit_open = max(start_ms, disappear - art.exit.opening_frames * 1000 / art.exit.fps)
    arrival_ms = max(disappear + (art.transit_ms if departure is not None else 0),
                     exit_open + art.exit.opening_frames * 1000 / art.exit.fps)
    settled = arrival_ms + art.emerge_ms
    close = settled + art.exit_hold_ms
    end = close + art.exit.closing_frames * 1000 / art.exit.fps if arrival is not None else disappear
    fall_inputs = (start, TimingOperand(TimingReference('spatial', portal_uuid, 'start'), opening_ms,
        offset_ms=art.fall_delay_ms, authored_field='portal.fall_delay_ms')) if opening_ms is not None and portal_uuid is not None else (start,)
    # A caller may disclose the opening clock without disclosing portal identity.
    if opening_ms is not None and portal_uuid is None:
        fall_inputs = (start, TimingOperand(TimingReference('event', event_uuid, 'opening'), opening_ms,
            offset_ms=art.fall_delay_ms, authored_field='portal.fall_delay_ms'))
    falling = record_timing(evidence, TimingReference('event', event_uuid, 'launch'), 'portal_fall', fall_inputs, fall, 'maximum')
    vanished = record_timing(evidence, TimingReference('event', event_uuid, 'disappear'), 'portal_fall',
        (replace(falling, offset_ms=art.fall_ms, authored_field='portal.fall_ms'),) if departure is not None else (start,), disappear)
    open_duration = art.exit.opening_frames * 1000 / art.exit.fps
    opened = record_timing(evidence, TimingReference('event', event_uuid, 'exit_open'), 'portal_exit',
        (start, replace(vanished, offset_ms=-open_duration, authored_field='portal.exit.opening_frames',
            measurements=(TimingMeasurement('portal.exit.opening_frames', art.exit.opening_frames),
                          TimingMeasurement('portal.exit.fps', art.exit.fps)))), exit_open, 'maximum')
    arrived = record_timing(evidence, TimingReference('event', event_uuid, 'arrival'), 'portal_arrival',
        (replace(vanished, offset_ms=art.transit_ms if departure is not None else 0, authored_field='portal.transit_ms'),
         replace(opened, offset_ms=open_duration, authored_field='portal.exit.opening_duration_ms')), arrival_ms, 'maximum')
    settled_at = record_timing(evidence, TimingReference('event', event_uuid, 'settled'), 'portal_settled',
        (replace(arrived, offset_ms=art.emerge_ms, authored_field='portal.emerge_ms'),), settled)
    record_timing(evidence, TimingReference('event', event_uuid, 'complete'), 'portal_settled',
        (replace(settled_at, offset_ms=art.exit_hold_ms+art.exit.closing_frames*1000/art.exit.fps,
            authored_field='portal.exit_hold_ms+exit.closing_duration_ms', measurements=(
                TimingMeasurement('portal.exit_hold_ms', art.exit_hold_ms),
                TimingMeasurement('portal.exit.closing_frames', art.exit.closing_frames),
                TimingMeasurement('portal.exit.fps', art.exit.fps))),) if arrival is not None else (vanished,), end)
    return PortalTransferCue(event_uuid, portal_uuid, actor_uuid, departure, arrival, art,
        start_ms, fall, disappear, exit_open, arrival_ms, settled, close, end, data, tuple(evidence))


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
