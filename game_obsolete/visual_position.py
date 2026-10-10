"""Playback placement relative to an unchanged authoritative contact."""

from dataclasses import dataclass, replace

from game.animation import ActorContact


@dataclass(frozen=True, slots=True)
class VisualPosition:
    legal_grid: tuple[float, float]
    grid: tuple[float, float]
    elevation_steps: float
    lift_px: float = 0


def placed_contact(contact: ActorContact, position: VisualPosition | None) -> ActorContact:
    """Overlay geometry only; a later legal relocation supersedes the placement."""
    if position is None or position.legal_grid != contact.grid:
        return contact
    return replace(contact, grid=position.grid, elevation_steps=position.elevation_steps,
                   body_lift_px=position.lift_px)
