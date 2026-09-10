"""Playable encounter: independent engine intake and one historical head.

The session owns commands. Retained lineages own subjective facts. Imported
contexts own presentation time. This frame pump connects those existing owners;
the renderer receives neither live entities nor an engine clock.
"""

import asyncio
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable, Mapping, Sequence
from uuid import UUID

import pygame

from dnd.actions import AttackEvent, JumpEvent, MovementEvent
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.core.base_actions import AvailableActionsResult
from dnd.core.events import EventQueue, StepMovementEvent
from game.animation_data import load_animation_data
from game.animation_types import Facing8
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.choreography import BoundChoreography, bind_choreography
from game.choreography_draw import ChoreographyMedia, load_choreography_media
from game.feedback import FeedbackTrack, choreography_feedback, motion_feedback
from game.controls import ActionSelection, EndTurn, MenuState, draw_menu, draw_target_preview, handle_menu_event
from game.motion import MotionTimeline, bind_motion
from game.playback_frame import sample_playback_frame
from game.presentation import (
    CompletedLineage, PresentationTarget, capture_interval, capture_lineage,
    reduce_interval, reduce_lineage, seed_actors,
)
from game.projection import Camera, ZOOM_LEVELS
from game.scene import draw_actor_labels, load_scene_media, scene_actors
from game.session import (
    Operation, advance_controller, close_session, create_session, discover_player_actions,
    end_player_turn, execute_player_action,
)
from game.visual_position import VisualPosition


@dataclass(frozen=True, slots=True)
class GameFrame:
    index: int
    latest_cursor: int
    historical_cursor: int
    pending: int
    root_uuid: UUID | None
    elapsed_ms: float
    paused: bool
    input_ready: bool
    positions: tuple[tuple[str, tuple[float, float]], ...]
    hit_points: tuple[tuple[str, int | None], ...]


@dataclass(frozen=True, slots=True)
class GameSummary:
    latest: PresentationTarget
    historical: PresentationTarget
    frames: tuple[GameFrame, ...]
    lineages: tuple[CompletedLineage, ...]
    player_commands: int
    presentation_gaps: tuple[tuple[UUID, str], ...]
    encounter_ended: bool


PlayerInput = Callable[[PresentationTarget, AvailableActionsResult], ActionSelection | EndTurn | None]


def _log_lines(lineage: CompletedLineage) -> tuple[str, ...]:
    # These are already projected at capture. Never use an objective event name
    # or the live combat log as a replacement for undisclosed narrative.
    return tuple(dict.fromkeys(re.sub(r"\{[a-z ]+:([^{}]*)\}", r"\1", event.combat_log.compact)
                               for event in lineage.events if event.combat_log is not None))


async def _run(
    *, frame_deltas: Sequence[float] | None, frame_events: Mapping[int, Sequence[pygame.event.Event]],
    max_frames: int | None, window_size: tuple[int, int], quadrant: int,
    capture_dir: Path | None, player_input: PlayerInput | None, stop_after_commands: int | None,
    exit_when_ended: bool,
    player_positions: tuple[tuple[int, int], tuple[int, int]],
    enemy_positions: tuple[tuple[int, int], tuple[int, int]],
) -> GameSummary:
    pygame.init()
    screen = pygame.display.set_mode(window_size)
    pygame.display.set_caption("D&D Engine — Goblin skirmish")
    session = create_session(player_positions=player_positions, enemy_positions=enemy_positions)
    try:
        observer = session.game.entities[session.player_uuids[0]]
        cursor = EventQueue.event_cursor()
        startup = capture_interval(
            name="encounter startup", start_cursor=0, end_cursor=cursor,
            observer_uuid=observer.uuid, battlefield_id="battlefield.open_floor_bright",
            seed_cursor=cursor, seed_snapshot=capture_senses_snapshot(observer.senses),
        )
        baseline, _ = reduce_interval(None, startup)
        latest = historical = seed_actors(baseline, session.births, active_weapon_sets={
            actor.uuid: actor.equipment.active_weapon_set for actor in session.game.entities.values()
        })
        data = load_animation_data(rig_files=(Path(__file__).parent / "data/rigs/goblin01.json",))
        number_font, badge_font = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx),
                                                       bold=style.fontWeight == "bold")
                                   for style in (data.number_style, data.badge_style))
        facings: dict[str, Facing8] = {}
        positions: dict[str, VisualPosition] = {}
        actors = scene_actors(historical, data, facings)
        body_media = load_scene_media(actors, data)
        catalog = load_catalog()
        cache = SurfaceCache(catalog)
        panel_rect = pygame.Rect(0, 0, 345, window_size[1] - 145)
        feedback_viewport = pygame.Rect(panel_rect.right, 0, window_size[0] - panel_rect.right, panel_rect.height)
        focus = (sum(actor.contact.grid[0] for actor in actors) / len(actors),
                 sum(actor.contact.grid[1] for actor in actors) / len(actors))
        camera = Camera(quadrant=quadrant, zoom=1.0, viewport=window_size).with_focus(focus)
        camera = camera.with_screen_pan((panel_rect.width / 2, -45))
        pending: deque[CompletedLineage] = deque()
        retained: list[CompletedLineage] = []
        frames: list[GameFrame] = []
        gaps: list[tuple[UUID, str]] = []
        active: CompletedLineage | None = None
        after = historical
        choreography: BoundChoreography | None = None
        motion: MotionTimeline | None = None
        choreography_media: ChoreographyMedia | None = None
        reaction_media: dict[UUID, ChoreographyMedia] = {}
        feedback: list[FeedbackTrack] = []
        choices: AvailableActionsResult | None = None
        menu = MenuState()
        logs: deque[str] = deque(maxlen=20)
        waiting_for_player = encounter_ended = paused = show_debug = False
        show_grid = False
        running = True
        frame = issued = 0
        elapsed_ms = presentation_ms = 0.0
        clock = pygame.time.Clock()
        if capture_dir is not None:
            capture_dir.mkdir(parents=True, exist_ok=True)

        def receive(operation: Operation) -> None:
            nonlocal latest
            for root in operation.roots:
                lineage = capture_lineage(root, observer_uuid=observer.uuid)
                latest = reduce_lineage(latest, lineage)
                pending.append(lineage)
                retained.append(lineage)
                classes = {row.event_uuid: row.event_class for row in lineage.objective_rows}
                gaps.extend((identity, f"Unprojected state payload: {classes[identity]}")
                            for identity, _ in lineage.dispositions)

        while running and (max_frames is None or frame < max_frames):
            delta = (clock.tick(60) / 1000 if frame_deltas is None
                     else frame_deltas[min(frame, len(frame_deltas) - 1)])
            if not paused:
                presentation_ms += delta * 1000
            ready = waiting_for_player and active is None and not pending and not paused
            if ready and choices is None:
                actor_uuid = historical.current_actor_uuid
                if actor_uuid is None:
                    raise RuntimeError("human boundary lacks its displayed turn owner")
                choices = discover_player_actions(session, actor_uuid)
                menu = MenuState()
            command: ActionSelection | EndTurn | None = None
            for event in frame_events.get(frame, ()):
                pygame.event.post(event)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key == pygame.K_g:
                        show_grid = not show_grid
                    elif event.key == pygame.K_F3:
                        show_debug = not show_debug
                    elif event.key in (pygame.K_q, pygame.K_e):
                        camera = camera.quarter_turned(-1 if event.key == pygame.K_q else 1)
                elif event.type == pygame.MOUSEWHEEL and not panel_rect.collidepoint(pygame.mouse.get_pos()):
                    zoom_index = max(0, min(len(ZOOM_LEVELS) - 1, ZOOM_LEVELS.index(camera.zoom) + event.y))
                    camera = camera.with_zoom_at(ZOOM_LEVELS[zoom_index], pygame.mouse.get_pos())
                if ready and not paused and command is None:
                    menu, command = handle_menu_event(
                        menu, event, choices, camera,
                        (tile for position, tile in historical.tiles.items()
                         if historical.senses is not None and position in historical.senses.visible),
                        panel_rect=panel_rect,
                    )
            if not running:
                break
            if ready and not paused and command is None and player_input is not None and choices is not None:
                if stop_after_commands is None or issued < stop_after_commands:
                    command = player_input(historical, choices)
            if command is not None and choices is not None:
                actor_uuid = historical.current_actor_uuid
                assert actor_uuid is not None
                match command:
                    case EndTurn():
                        operation = end_player_turn(session, actor_uuid)
                    case ActionSelection():
                        action = choices.all_actions[command.action_index]
                        selected = tuple(next(target for target in action.valid_targets if target.index == index)
                                         for index in command.target_indices)
                        if not selected:
                            raise ValueError("player command requires its discovered target")
                        operation = execute_player_action(
                            session, actor_uuid, action, selected[0],
                            extra_target_uuids=tuple(target.target_uuid for target in selected[1:]
                                                     if target.target_uuid is not None),
                        )
                receive(operation)
                choices = None
                waiting_for_player = False
                issued += 1

            # Independent process: a native decision can run while history is
            # paused or animating. No rendered duration enters the rules engine.
            if not waiting_for_player and not encounter_ended:
                operation = advance_controller(session)
                receive(operation)
                assert operation.boundary is not None
                if operation.boundary.status == "error":
                    raise RuntimeError("encounter has no valid controller action boundary")
                waiting_for_player = operation.boundary.status == "waiting_for_human"
                encounter_ended = operation.boundary.status == "encounter_ended"
            await asyncio.sleep(0)

            started = False
            if active is None and pending and not paused:
                active = pending.popleft()
                after = reduce_lineage(historical, active)
                choreography = None
                choreography_media = None
                contacts = {actor.contact.actor_uuid: actor.contact
                            for actor in scene_actors(historical, data, facings, positions)}
                motion = bind_motion(historical, active, data, contacts=contacts)
                reaction_media = {}
                if motion is not None:
                    for reaction in motion.reactions:
                        group = reaction.choreography
                        reaction_media[group.root_uuid] = load_choreography_media(group)
                        gaps.extend(group.gaps)
                    feedback.extend(motion_feedback(motion, data, presentation_ms))
                else:
                    if isinstance(active.root, (MovementEvent, JumpEvent)) and any(
                        isinstance(event, AttackEvent) or (isinstance(event, StepMovementEvent) and event.committed)
                        for event in active.events
                    ):
                        gaps.append((active.root.uuid, "Movement reaction choreography is not bound"))
                    choreography = bind_choreography(historical, active, data, facings=facings, contacts=contacts)
                    choreography_media = load_choreography_media(choreography)
                    gaps.extend(choreography.gaps)
                    feedback.extend(choreography_feedback(choreography, data, presentation_ms, contacts=contacts))
                elapsed_ms = 0
                started = True
                clock.tick()
            if active is not None and not started and not paused:
                elapsed_ms += delta * 1000
            keys = pygame.key.get_pressed()
            camera = camera.with_screen_pan(((keys[pygame.K_a] - keys[pygame.K_d]) * 320 * delta,
                                             (keys[pygame.K_w] - keys[pygame.K_s]) * 320 * delta))
            feedback[:] = [track for track in feedback if presentation_ms < track.start_ms + track.duration_ms]
            playback = sample_playback_frame(
                historical, after if active is not None else None, data, elapsed_ms, presentation_ms,
                camera, facings, body_media, number_font, badge_font,
                choreography=choreography, choreography_media=choreography_media,
                motion=motion, reaction_media=reaction_media, feedback=feedback,
                positions=positions, feedback_viewport=feedback_viewport,
            )
            displayed, actors, commands = playback.displayed, playback.actors, playback.commands
            complete, shown_hp = playback.complete, playback.shown_hp
            facings = dict(playback.facings)
            positions = dict(playback.positions)
            draw_frame(screen, displayed, catalog, cache, camera, presentation_ms / 1000,
                       show_grid=show_grid, show_debug=show_debug, mouse_position=None,
                       objective_lines=tuple(f"[{identity}] {reason}" for identity, reason in gaps[-8:]),
                       extra_commands=commands,
                       revisions=(latest.reducer_cursor, latest.reducer_cursor, historical.reducer_cursor))
            ready = waiting_for_player and active is None and not pending and not paused
            if ready:
                draw_target_preview(screen, menu, choices, camera,
                                    (tile for position, tile in displayed.tiles.items()
                                     if displayed.senses is not None and position in displayed.senses.visible))
            draw_actor_labels(screen, cache.debug_font, actors, displayed, camera,
                              shown_hp=shown_hp, active_uuid=displayed.current_actor_uuid,
                              commands=commands, viewport=feedback_viewport)
            actor = displayed.actors.get(displayed.current_actor_uuid) if displayed.current_actor_uuid else None
            draw_menu(screen, cache.debug_font, menu, choices if ready else None,
                      panel_rect=panel_rect, enabled=ready and not paused,
                      actor_name=actor.name if actor else "Encounter",
                      waiting_text="Encounter ended" if encounter_ended and not pending and active is None
                      else "Paused" if paused else "Waiting for animation")
            panel = pygame.Surface((screen.width, 145))
            panel.fill((16, 21, 29))
            state = "Paused" if paused else "Encounter ended" if encounter_ended and not pending and active is None else "Your turn" if ready else "Playing history"
            lines = [f"Round {displayed.round_number} · {state} · view: {historical.actors[observer.uuid].name}",
                     "Space pause · Q/E rotate · WASD pan · G grid · F3 details · N end turn · Esc close"]
            current_lines = _log_lines(active) if active is not None and complete else ()
            lines.extend((*logs, *current_lines)[-4:])
            for index, line in enumerate(lines):
                panel.blit(cache.debug_font.render(line[:170], True, (226, 229, 235)), (16, 8 + index * 22))
            screen.blit(panel, (0, screen.height - panel.height))
            pygame.display.flip()
            frames.append(GameFrame(
                frame, latest.reducer_cursor, historical.reducer_cursor, len(pending),
                active.root.uuid if active is not None else None, elapsed_ms, paused, ready and not paused,
                tuple((actor.contact.actor_uuid, actor.contact.grid) for actor in actors),
                tuple((actor.contact.actor_uuid, shown_hp.get(actor.contact.actor_uuid, actor.contact.hp)) for actor in actors),
            ))
            if capture_dir is not None and (frame % 6 == 0 or complete):
                pygame.image.save(screen, capture_dir / f"frame-{frame:05}.png")
            if active is not None and complete and not paused:
                historical = after
                logs.extend(_log_lines(active))
                active = None
                choreography = None
                motion = None
            frame += 1
            if (stop_after_commands is not None and issued >= stop_after_commands
                    and active is None and not pending and (waiting_for_player or encounter_ended)):
                break
            if exit_when_ended and encounter_ended and active is None and not pending:
                break
        return GameSummary(latest, historical, tuple(frames), tuple(retained), issued, tuple(gaps), encounter_ended)
    finally:
        close_session(session)
        pygame.quit()


def run(
    *, frame_deltas: Sequence[float] | None = None,
    frame_events: Mapping[int, Sequence[pygame.event.Event]] | None = None,
    max_frames: int | None = None, window_size: tuple[int, int] = (1280, 800), quadrant: int = 0,
    capture_dir: Path | None = None, player_input: PlayerInput | None = None,
    stop_after_commands: int | None = None,
    exit_when_ended: bool = False,
    player_positions: tuple[tuple[int, int], tuple[int, int]] = ((10, 10), (10, 12)),
    enemy_positions: tuple[tuple[int, int], tuple[int, int]] = ((14, 10), (14, 12)),
) -> GameSummary:
    """Run real Pygame input, or the same command boundary with deterministic inputs."""
    if frame_deltas is not None and (not frame_deltas or any(delta <= 0 for delta in frame_deltas)):
        raise ValueError("frame deltas must be positive")
    return asyncio.run(_run(
        frame_deltas=frame_deltas, frame_events=frame_events or {}, max_frames=max_frames,
        window_size=window_size, quadrant=quadrant, capture_dir=capture_dir,
        player_input=player_input, stop_after_commands=stop_after_commands,
        exit_when_ended=exit_when_ended,
        player_positions=player_positions, enemy_positions=enemy_positions,
    ))
