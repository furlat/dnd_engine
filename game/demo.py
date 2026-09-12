"""Explicit native door/light regression demonstration and its diagnostic loop."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterator, Mapping, Sequence, cast
from uuid import uuid4

import pygame

from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.core.events import Event, EventPhase, EventQueue, SpatialChangeEvent, WorldInitializedEvent
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.environment import CloseDirectionalDoorAction, DirectionalDoor, OpenDirectionalDoorAction
from dnd.items.torches import StandingTorch
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.app import BACKGROUND, WINDOW_SIZE, FrameEvidence, draw_frame
from game.assets import SurfaceCache, load_catalog
from game.presentation import (
    Disposition, IntervalEnvelope, IntervalTerminal, PresentationTarget, ReducedInterval,
    capture_interval, reduce_interval, settle_dispositions,
)
from game.projection import Camera, ZOOM_LEVELS

BATTLEFIELD_ID = "battlefield.visual_vertical_seam"
DISPLAY_HOLD_SECONDS = 0.75


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Primitive final status returned by both the real and dummy entry path."""

    engine_cursor: int
    reducer_cursor: int
    display_cursor: int
    terminal_count: int
    settled: bool
    revision_samples: tuple[tuple[int, int, int], ...]
    terminals: tuple[IntervalTerminal, ...]


def _successful(event: Event | None, action: str) -> Event:
    if event is None or event.canceled or event.phase is not EventPhase.COMPLETION:
        raise RuntimeError(f"{action} did not complete successfully")
    return event


def _iter_demo_intervals() -> Iterator[IntervalEnvelope]:
    """Run each scripted mechanic and yield its completed event interval."""
    reset_engine_runtime()
    startup_start = EventQueue.event_cursor()
    built = build_battlefield(BATTLEFIELD_ID)
    door = cast(DirectionalDoor | None, DirectionalDoor.get(built.object_uuids["door"]))
    standing_torch = cast(
        StandingTorch | None,
        StandingTorch.get(built.object_uuids["standing_torch"]),
    )
    if door is None or standing_torch is None or not standing_torch.is_lit:
        raise RuntimeError("visual battlefield did not settle its authored fixture")

    observer = Entity.create(
        source_entity_uuid=uuid4(),
        name="Visual observer",
        config=EntityConfig(
            position=built.notable_positions["observer"],
            faction="heroes",
            has_ordinary_sight=True,
        ),
    )
    observer.compose_entity()
    if len(standing_torch.get_attached_light_sources()) != 1:
        raise RuntimeError("standing fixture must own one active light")

    game = Game()
    game.deploy_entity(observer, built.notable_positions["observer"])
    startup_end = EventQueue.event_cursor()
    yield capture_interval(
        name="startup",
        start_cursor=startup_start,
        end_cursor=startup_end,
        observer_uuid=observer.uuid,
        battlefield_id=BATTLEFIELD_ID,
        door_uuid=door.uuid,
        standing_torch_uuid=standing_torch.uuid,
    )

    open_start = startup_end
    _successful(
        OpenDirectionalDoorAction(
            source_entity_uuid=observer.uuid,
            source_item_uuid=door.uuid,
            template=False,
        ).apply(),
        "open door",
    )
    if not door.is_open:
        raise RuntimeError("Open Door completed without opening its door")
    open_end = EventQueue.event_cursor()
    yield capture_interval(
        name="open",
        start_cursor=open_start,
        end_cursor=open_end,
        observer_uuid=observer.uuid,
        battlefield_id=BATTLEFIELD_ID,
        door_uuid=door.uuid,
        standing_torch_uuid=standing_torch.uuid,
    )

    close_start = open_end
    _successful(
        CloseDirectionalDoorAction(
            source_entity_uuid=observer.uuid,
            source_item_uuid=door.uuid,
            template=False,
        ).apply(),
        "close door",
    )
    if door.is_open:
        raise RuntimeError("Close Door completed without closing its door")
    close_end = EventQueue.event_cursor()
    yield capture_interval(
        name="close",
        start_cursor=close_start,
        end_cursor=close_end,
        observer_uuid=observer.uuid,
        battlefield_id=BATTLEFIELD_ID,
        door_uuid=door.uuid,
        standing_torch_uuid=standing_torch.uuid,
    )


def build_demo_intervals() -> tuple[IntervalEnvelope, IntervalEnvelope, IntervalEnvelope]:
    """Return the three intervals produced by the one scripted mechanics path."""
    startup, opened, closed = tuple(_iter_demo_intervals())
    return startup, opened, closed


async def _produce_intervals(queue: asyncio.Queue[IntervalEnvelope]) -> None:
    """Yield completed mechanics intervals without renderer pacing."""
    for envelope in _iter_demo_intervals():
        queue.put_nowait(envelope)
        await asyncio.sleep(0)


def _display_sources(
    reduced: ReducedInterval,
    evidence: FrameEvidence,
) -> tuple[set[int], set[int]]:
    represented: set[int] = set()
    not_disclosed: set[int] = set()
    draws = evidence.actual_draws
    for index, event in reduced.envelope.admitted:
        if index not in reduced.pending_display:
            continue
        if type(event) is WorldInitializedEvent:
            (represented if draws else not_disclosed).add(index)
        elif type(event) is ItemLocationStateEvent:
            shown = any(row and row[0] == reduced.envelope.standing_torch_uuid for row in draws)
            (represented if shown else not_disclosed).add(index)
        elif type(event) is SpatialChangeEvent:
            placement = event.placement
            shown = placement is not None and any(
                len(row) > 8
                and row[6] == "door_leaf"
                and row[0] == event.object_uuid
                and row[1] == (
                    placement.position,
                    placement.boundary_direction.value
                    if placement.boundary_direction is not None
                    else None,
                )
                and row[7] == placement.base_height_steps
                and row[8] == event.object_is_open
                for row in draws
            )
            (represented if shown else not_disclosed).add(index)
        else:
            raise RuntimeError("reduced interval has an unknown display obligation")
    return represented, not_disclosed


def _rail_lines(
    reduced: ReducedInterval,
    dispositions: Mapping[int, Disposition],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    objective = tuple(
        f"[{dispositions[row.source_index].value}] #{row.source_index} {row.event_class}:{row.phase}"
        for row in reduced.envelope.objective_rows
    )
    subjective = tuple(
        f"[subjective] #{row.source_index} {row.text}"
        for row in reduced.envelope.subjective_rows
    )
    return objective, subjective


async def _run(
    *,
    frame_deltas: Sequence[float] | None,
    display_hold_seconds: float,
    max_frames: int | None,
    window_size: tuple[int, int],
) -> RunSummary:
    if display_hold_seconds < 0:
        raise ValueError("display hold must be nonnegative")
    pygame.init()
    screen = pygame.display.set_mode(window_size)
    pygame.display.set_caption("D&D Engine — Visual Vertical Seam")
    screen.fill(BACKGROUND)
    pygame.display.flip()
    catalog = load_catalog()
    cache = SurfaceCache(catalog)
    camera = Camera(viewport=window_size).with_focus((31, 31))
    intervals: asyncio.Queue[IntervalEnvelope] = asyncio.Queue(maxsize=3)
    terminals: asyncio.Queue[IntervalTerminal] = asyncio.Queue(maxsize=3)
    producer = asyncio.create_task(_produce_intervals(intervals))
    clock = pygame.time.Clock()
    target: PresentationTarget | None = None
    current: ReducedInterval | None = None
    dispositions: dict[int, Disposition] = {}
    presentation_time = 0.0
    displayed_at: float | None = None
    display_cursor = 0
    terminal_count = 0
    show_grid = True
    running = True
    frame = 0
    objective_lines: tuple[str, ...] = ()
    subjective_lines: tuple[str, ...] = ()
    revision_samples: list[tuple[int, int, int]] = []
    try:
        while running:
            if max_frames is not None and frame >= max_frames:
                if terminal_count < 3:
                    raise RuntimeError("frame limit reached before all intervals settled")
                break
            if producer.done():
                producer_failure = producer.exception()
                if producer_failure is not None:
                    raise producer_failure
            for pygame_event in pygame.event.get():
                if pygame_event.type == pygame.QUIT:
                    running = False
                elif pygame_event.type == pygame.KEYDOWN:
                    if pygame_event.key == pygame.K_ESCAPE:
                        running = False
                    elif pygame_event.key == pygame.K_g:
                        show_grid = not show_grid
                    elif pygame_event.key in (pygame.K_q, pygame.K_e):
                        step = -1 if pygame_event.key == pygame.K_q else 1
                        camera = camera.quarter_turned(step)
                elif pygame_event.type == pygame.MOUSEWHEEL:
                    index = ZOOM_LEVELS.index(camera.zoom)
                    next_index = max(0, min(len(ZOOM_LEVELS) - 1, index + pygame_event.y))
                    next_zoom = ZOOM_LEVELS[next_index]
                    if next_zoom != camera.zoom:
                        camera = camera.with_zoom_at(next_zoom, pygame.mouse.get_pos())
            keys = pygame.key.get_pressed()
            pan_speed = 320.0
            if frame_deltas is None:
                delta = clock.tick(60) / 1000.0
            else:
                delta = frame_deltas[min(frame, len(frame_deltas) - 1)] if frame_deltas else 0.0
            pan_x = (keys[pygame.K_a] - keys[pygame.K_d]) * pan_speed * delta
            pan_y = (keys[pygame.K_w] - keys[pygame.K_s]) * pan_speed * delta
            if pan_x or pan_y:
                camera = camera.with_screen_pan((pan_x, pan_y))
            presentation_time += delta

            await asyncio.sleep(0)
            if current is None:
                try:
                    envelope = intervals.get_nowait()
                except asyncio.QueueEmpty:
                    envelope = None
                if envelope is not None:
                    target, current = reduce_interval(target, envelope)
                    dispositions = dict(current.dispositions)
                    objective_lines, subjective_lines = _rail_lines(current, dispositions)
                    displayed_at = None

            if target is None:
                screen.fill(BACKGROUND)
                pygame.display.flip()
                frame += 1
                continue
            engine_cursor = EventQueue.event_cursor()
            displayed_subjective_lines = subjective_lines
            if terminal_count == 3:
                displayed_subjective_lines = (
                    *displayed_subjective_lines,
                    "script complete — Esc closes",
                )
            evidence = draw_frame(
                screen,
                target,
                catalog,
                cache,
                camera,
                presentation_time,
                show_grid=show_grid,
                collect_evidence=True,
                mouse_position=pygame.mouse.get_pos(),
                objective_lines=objective_lines,
                subjective_lines=displayed_subjective_lines,
                revisions=(engine_cursor, target.reducer_cursor, display_cursor),
            )
            assert evidence is not None
            if not evidence.matches:
                raise RuntimeError("calculated and post-blit frame evidence differ")
            revision_samples.append((
                engine_cursor,
                target.reducer_cursor,
                display_cursor,
            ))
            pygame.display.flip()
            if current is not None and displayed_at is None:
                represented, hidden = _display_sources(current, evidence)
                dispositions = settle_dispositions(
                    current,
                    represented=represented,
                    not_disclosed=hidden,
                )
                objective_lines, subjective_lines = _rail_lines(current, dispositions)
                display_cursor = current.envelope.end_cursor
                displayed_at = presentation_time
            if (
                current is not None
                and displayed_at is not None
                and presentation_time - displayed_at >= display_hold_seconds
            ):
                terminals.put_nowait(IntervalTerminal(
                    generation=current.envelope.generation,
                    name=current.envelope.name,
                    start_cursor=current.envelope.start_cursor,
                    end_cursor=current.envelope.end_cursor,
                    settled=True,
                    failed=False,
                    cancelled=False,
                ))
                terminal_count += 1
                current = None
                displayed_at = None
            frame += 1

        if not running and terminal_count < 3:
            raise RuntimeError("pygame closed before the scripted intervals settled")
        await producer
        reducer_cursor = target.reducer_cursor if target is not None else 0
        terminal_values = tuple(
            terminals.get_nowait()
            for _ in range(terminal_count)
        )
        summary = RunSummary(
            engine_cursor=EventQueue.event_cursor(),
            reducer_cursor=reducer_cursor,
            display_cursor=display_cursor,
            terminal_count=terminal_count,
            settled=terminal_count == 3 and reducer_cursor == display_cursor,
            revision_samples=tuple(revision_samples),
            terminals=terminal_values,
        )
        return summary
    finally:
        if not producer.done():
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)
        pygame.quit()
        reset_engine_runtime()


def run(
    *,
    frame_deltas: Sequence[float] | None = None,
    display_hold_seconds: float = DISPLAY_HOLD_SECONDS,
    max_frames: int | None = None,
    window_size: tuple[int, int] = WINDOW_SIZE,
) -> RunSummary:
    """Run the same application entry for manual and deterministic smoke use."""
    summary = asyncio.run(_run(
        frame_deltas=frame_deltas,
        display_hold_seconds=display_hold_seconds,
        max_frames=max_frames,
        window_size=window_size,
    ))
    print(
        f"E={summary.engine_cursor} R={summary.reducer_cursor} "
        f"D={summary.display_cursor} terminals={summary.terminal_count} "
        f"settled={summary.settled}"
    )
    return summary

