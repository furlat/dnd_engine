"""Four-camera portal banks and local falling-body occlusion."""

from functools import lru_cache
from pathlib import Path

import numpy as np
import pygame

from game.animation_types import AnimationData
from game.draw_commands import DrawCommand
from game.player_facts import PlayerState
from game.portal_animation import PortalTransferCue
from game.portal_art import PortalBank, PortalHatch, portal_frame
from game.projection import Camera, painter_key, project_screen
from game.world_animation import WorldTransitionSample


@lru_cache(maxsize=8)
def _page(path: Path) -> pygame.Surface:
    return pygame.image.load(path).convert_alpha()


@lru_cache(maxsize=128)
def _crop(path: Path, rect: tuple[int, int, int, int], scale: float) -> pygame.Surface:
    image = _page(path).subsurface(rect)
    return pygame.transform.scale(image, (max(1, round(rect[2] * scale)), max(1, round(rect[3] * scale))))


def _bank_image(bank: PortalBank, frame: int, camera: Camera, scale: float) -> pygame.Surface:
    local = frame % bank.frames_per_page
    width, height = bank.cell
    return _crop(bank.pages[camera.quadrant][frame // bank.frames_per_page],
        ((local % bank.columns) * width, (local // bank.columns) * height, width, height), scale)


def _hatch_image(hatch: PortalHatch, frame: int, camera: Camera, scale: float,
                  *, front: bool = False) -> pygame.Surface:
    width, height = hatch.cell
    return _crop(hatch.front if front else hatch.sheet,
        (frame * width, camera.quadrant * height, width, height), scale)


def hatch_frame(hatch: PortalHatch, active: bool, elapsed_ms: float | None) -> int:
    frames = hatch.opening if active else hatch.closing
    return frames[-1] if elapsed_ms is None else frames[min(len(frames) - 1,
        max(0, int(elapsed_ms * hatch.fps / 1000)))]


def _command(identity: str, position: tuple[float, float], height: float, image: pygame.Surface,
              pivot: tuple[float, float], scale: float, camera: Camera, role: str, frame: int) -> DrawCommand:
    point = project_screen(position, camera, elevation_steps=height)
    return DrawCommand(painter_key(position, elevation_steps=height, quadrant=camera.quadrant,
        role="ground_effect", identity=(identity, role)), image,
        (round(point[0] - pivot[0] * scale), round(point[1] - pivot[1] * scale)), 0,
        (identity, position, role, "current", None, "authored", role, height, frame))


def portal_draw_commands(state: PlayerState, data: AnimationData, presentation_ms: float,
                          camera: Camera, transitions: tuple[WorldTransitionSample, ...],
                          transfers: tuple[tuple[PortalTransferCue, float], ...],
                          ) -> tuple[DrawCommand, ...]:
    commands = []
    changes = {row.transition.identity: row for row in transitions if row.transition.field == "trap_state"}
    if state.senses is not None:
        for identity, effect in state.senses.spatial_effects.items():
            art = data.portals.get(effect.content_ref.content_id)
            if art is None or effect.trap_state is None:
                continue
            active = effect.trap_state.value == "activated"
            change = changes.get(identity)
            changed = change is not None and change.transition.current == effect.trap_state.value
            elapsed = change.elapsed_ms if changed and change is not None else None
            scale = art.scale * camera.zoom
            for position in effect.positions:
                if position not in state.senses.visible or position not in state.tiles:
                    continue
                height = state.tiles[position].elevation_steps
                if active or changed and elapsed is not None and elapsed < art.entrance.closing_frames * 1000 / art.entrance.fps:
                    phase_time = elapsed if elapsed is not None else (
                        presentation_ms + art.entrance.opening_frames * 1000 / art.entrance.fps)
                    frame = portal_frame(art.entrance, phase_time, closing=not active)
                    commands.append(_command(str(identity), position, height,
                        _bank_image(art.entrance, frame, camera, scale), art.entrance.pivot,
                        scale, camera, "portal_energy", frame))
                if art.hatch is not None:
                    frame = hatch_frame(art.hatch, active, elapsed)
                    commands.append(_command(str(identity), position, height,
                        _hatch_image(art.hatch, frame, camera, scale), art.hatch.pivot,
                        scale, camera, "portal_hatch", frame))
    for cue, elapsed in transfers:
        if cue.arrival is None or not cue.exit_open_ms <= elapsed < cue.complete_ms:
            continue
        # Endpoint permission does not turn the entrance view into a remote
        # window. An exit witness sees opening; the traveler sees the already
        # open exit when the recorded arrival admits that part of the world.
        if state.senses is None or cue.arrival.grid not in state.senses.visible:
            continue
        bank, scale = cue.art.exit, cue.art.scale * camera.zoom
        closing = elapsed >= cue.exit_close_ms
        frame = portal_frame(bank, elapsed - (cue.exit_close_ms if closing else cue.exit_open_ms), closing=closing)
        contact = cue.arrival
        commands.append(_command(str(cue.event_uuid), contact.grid, contact.elevation_steps,
            _bank_image(bank, frame, camera, scale), bank.pivot, scale, camera, "portal_exit", frame))
    return tuple(commands)


def clip_portal_bodies(commands: tuple[DrawCommand, ...], camera: Camera,
                       transfers: tuple[tuple[PortalTransferCue, float], ...],
                       hidden: frozenset[str]) -> tuple[DrawCommand, ...]:
    """Clip only a descending body; cached actor/hardware rasters stay immutable."""
    falling = {cue.actor_uuid: (cue, elapsed) for cue, elapsed in transfers
        if cue.departure is not None and cue.fall_start_ms < elapsed < cue.disappear_ms}
    emerging = {cue.actor_uuid: (cue, elapsed) for cue, elapsed in transfers
        if cue.arrival is not None and cue.arrival_ms <= elapsed < cue.settled_ms}
    result = []
    for command in commands:
        role, identity = command.role, command.owner
        if role not in ("actor", "actor_shadow", "body_copy", "body_contour", "body_trail"):
            result.append(command)
            continue
        if identity in hidden or role == "actor_shadow" and (identity in falling or identity in emerging):
            continue
        falling_sample = falling.get(identity) or emerging.get(identity)
        if falling_sample is None:
            result.append(command)
            continue
        cue, elapsed = falling_sample
        contact = cue.departure if identity in falling else cue.arrival
        assert contact is not None
        art, hatch = cue.art, cue.art.hatch if identity in falling else None
        scale = art.scale * camera.zoom
        ground = project_screen(contact.grid, camera, elevation_steps=contact.elevation_steps)
        image = command.surface.copy()
        xs = np.arange(image.width)[:, None] + command.destination[0] + .5 - ground[0]
        ys = np.arange(image.height)[None, :] + command.destination[1] + .5 - ground[1]
        # The front aperture edges are projected geometry. Upper body pixels
        # remain intact; pixels below the floor outside its opening disappear.
        aperture = art.entrance_aperture if identity in falling else art.exit_aperture
        relative_x = np.abs(xs) / (aperture.half_width_px * scale)
        lip = aperture.half_height_px * scale * (1-relative_x if aperture.shape == "diamond"
            else np.sqrt(np.maximum(0, 1-relative_x**2)))
        pygame.surfarray.pixels_alpha(image)[ys > lip] = 0
        if hatch is None:
            result.append(command._replace(surface=image))
            continue
        opening_age = elapsed - cue.start_ms if cue.fall_start_ms > cue.start_ms else None
        frame = hatch_frame(hatch, True, opening_age)
        front = _hatch_image(hatch, frame, camera, scale, front=True)
        origin = (round(ground[0] - hatch.pivot[0] * scale), round(ground[1] - hatch.pivot[1] * scale))
        overlap = image.get_rect(topleft=command.destination).clip(front.get_rect(topleft=origin))
        if overlap.width and overlap.height:
            local = overlap.move(-command.destination[0], -command.destination[1])
            cover = overlap.move(-origin[0], -origin[1])
            alpha = pygame.surfarray.pixels_alpha(image)
            mask = pygame.surfarray.array_alpha(front)[cover.left:cover.right, cover.top:cover.bottom]
            area = alpha[local.left:local.right, local.top:local.bottom]
            area[:] = (area.astype(np.uint16) * (255 - mask.astype(np.uint16)) // 255).astype(np.uint8)
            del alpha, area
        result.append(command._replace(surface=image))
    return tuple(result)
